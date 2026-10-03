import re
from typing import Dict, List, Tuple, Optional
from app.schemas.document import DocumentPage, DocumentSection
from app.services.document_parser.section_detector import KNOWN_SECTION_ALIASES, SectionDetector

# Extended section aliases specific to resumes
RESUME_SECTION_ALIASES: Dict[str, str] = {
    **KNOWN_SECTION_ALIASES,
    # Skills variations
    "skills & technologies": "skills",
    "skills and technologies": "skills",
    "technical proficiencies": "skills",
    "technical expertise": "skills",
    "tools & technologies": "skills",
    "tools and technologies": "skills",
    "programming skills": "skills",
    "it skills": "skills",
    "skills / tools": "skills",
    "key competencies": "skills",
    "technical skillset": "skills",
    # Experience variations
    "employment": "experience",
    "employment history": "experience",
    "work background": "experience",
    "internship experience": "experience",
    "internships": "experience",
    "industry experience": "experience",
    "relevant experience": "experience",
    # Education variations
    "academic history": "education",
    "scholastic background": "education",
    "degrees": "education",
    "higher education": "education",
    # Projects variations
    "project work": "projects",
    "selected projects": "projects",
    "notable projects": "projects",
    "key initiatives": "projects",
    "portfolio": "projects",
    # Certifications variations
    "licenses & certifications": "certifications",
    "training & certifications": "certifications",
    "professional certifications": "certifications",
    "courses & workshops": "certifications",
}

NON_HEADING_KEYWORDS = {
    "gpa", "cgpa", "grade", "phone", "email", "issued", "date", "expires",
    "valid", "address", "location", "tel", "status", "languages", "databases",
    "frameworks", "tools", "libraries", "interests"
}

class ResumeSectionExtractor:
    """
    Extensible section extractor tailored for resumes.
    Identifies non-standard headings, preserves provenance, and segments text.
    """

    @classmethod
    def normalize_resume_heading(cls, raw_heading: str) -> str:
        cleaned = raw_heading.strip().rstrip(":").lower()
        cleaned = re.sub(r'^[0-9\.\-\•\*\s]+', '', cleaned).strip()

        if cleaned in RESUME_SECTION_ALIASES:
            return RESUME_SECTION_ALIASES[cleaned]

        slug = re.sub(r'[^a-z0-9]+', '_', cleaned).strip('_')
        return slug or "unclassified"

    @classmethod
    def is_resume_heading(cls, line: str) -> bool:
        clean = line.strip()
        if not clean or len(clean) > 45:
            return False

        if clean.endswith((".", "?", "!", ";", ",")):
            return False

        unprefixed = re.sub(r'^[0-9\.\-\•\*\s]+', '', clean).strip()

        # If there's a colon, check if it's trailing or followed by inline content
        if ":" in unprefixed:
            parts = unprefixed.split(":", 1)
            # If followed by non-empty text, it's an inline key-value item (e.g. GPA: 3.9, Languages: Python)
            if parts[1].strip():
                return False
            unprefixed = parts[0].strip()

        # Resume section headings do not contain numbers (except perhaps leading section counters stripped above)
        if any(c.isdigit() for c in unprefixed):
            return False

        lower = unprefixed.lower()
        if lower in NON_HEADING_KEYWORDS:
            return False

        if lower in RESUME_SECTION_ALIASES:
            return True

        # Check ALL CAPS or Title Case without terminal punctuation
        words = unprefixed.split()
        if 1 <= len(words) <= 4:
            letters = [c for c in unprefixed if c.isalpha()]
            if len(letters) >= 3 and unprefixed.isupper():
                return True
            if clean.endswith(":") and all(w[0].isupper() for w in words if w and w[0].isalpha()):
                return True

        return False

    @classmethod
    def extract_sections(
        cls, 
        pages: List[DocumentPage]
    ) -> Tuple[Dict[str, str], Dict[str, Tuple[str, int]], List[DocumentSection]]:
        """
        Extracts sections across document pages.
        Returns:
            - sections_map: canonical_name -> accumulated text
            - provenance_map: canonical_name -> (raw_title, start_page)
            - detected_sections: list of DocumentSection objects
        """
        sections_map: Dict[str, List[str]] = {}
        provenance_map: Dict[str, Tuple[str, int]] = {}
        detected_sections: List[DocumentSection] = []

        current_raw: Optional[str] = None
        current_canonical: Optional[str] = None
        current_page: int = 1
        current_lines: List[str] = []

        for page in pages:
            lines = page.normalized_text.split("\n")
            for line in lines:
                clean = line.strip()
                if not clean:
                    continue

                if cls.is_resume_heading(clean):
                    # Commit previous section
                    if current_canonical:
                        sec_text = "\n".join(current_lines).strip()
                        if sec_text or current_raw:
                            sections_map.setdefault(current_canonical, []).append(sec_text)
                            if current_canonical not in provenance_map:
                                provenance_map[current_canonical] = (current_raw or current_canonical, current_page)
                            detected_sections.append(
                                DocumentSection(
                                    title=current_raw or current_canonical,
                                    canonical_name=current_canonical,
                                    text=sec_text,
                                    start_page=current_page,
                                )
                            )

                    # Start new section
                    current_raw = clean.rstrip(":")
                    current_canonical = cls.normalize_resume_heading(clean)
                    current_page = page.page_number
                    current_lines = []
                else:
                    if current_canonical:
                        current_lines.append(clean)

        # Commit final section
        if current_canonical:
            sec_text = "\n".join(current_lines).strip()
            if sec_text or current_raw:
                sections_map.setdefault(current_canonical, []).append(sec_text)
                if current_canonical not in provenance_map:
                    provenance_map[current_canonical] = (current_raw or current_canonical, current_page)
                detected_sections.append(
                    DocumentSection(
                        title=current_raw or current_canonical,
                        canonical_name=current_canonical,
                        text=sec_text,
                        start_page=current_page,
                    )
                )

        flattened = {k: "\n\n".join(filter(None, v)).strip() for k, v in sections_map.items()}
        return flattened, provenance_map, detected_sections
