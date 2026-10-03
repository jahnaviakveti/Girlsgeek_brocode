import re
from typing import Dict, List, Tuple, Optional
from app.schemas.document import DocumentSection, DocumentPage

# Canonical mappings for common document section aliases
KNOWN_SECTION_ALIASES: Dict[str, str] = {
    # Skills
    "skills": "skills",
    "technical skills": "skills",
    "core competencies": "skills",
    "technologies": "skills",
    "skillset": "skills",
    "key skills": "skills",
    "proficiencies": "skills",
    "competencies": "skills",
    "areas of expertise": "skills",
    # Experience
    "experience": "experience",
    "work experience": "experience",
    "professional experience": "experience",
    "employment history": "experience",
    "work history": "experience",
    "career history": "experience",
    "practical experience": "experience",
    # Education
    "education": "education",
    "academic background": "education",
    "academics": "education",
    "qualifications": "education",
    "academic qualifications": "education",
    "educational background": "education",
    # Projects
    "projects": "projects",
    "key projects": "projects",
    "academic projects": "projects",
    "technical projects": "projects",
    "personal projects": "projects",
    "selected projects": "projects",
    # Certifications
    "certifications": "certifications",
    "certificates": "certifications",
    "licenses": "certifications",
    "courses & certifications": "certifications",
    "credentials": "certifications",
    # Summary / Objective
    "summary": "summary",
    "professional summary": "summary",
    "executive summary": "summary",
    "profile": "summary",
    "personal profile": "summary",
    "objective": "summary",
    "career objective": "summary",
    "about me": "summary",
    "overview": "summary",
    # Responsibilities / Scope
    "responsibilities": "responsibilities",
    "roles & responsibilities": "responsibilities",
    "duties": "responsibilities",
    "job duties": "responsibilities",
    # Achievements / Awards
    "achievements": "achievements",
    "awards": "achievements",
    "honors": "achievements",
    "awards & achievements": "achievements",
    "publications": "achievements",
    "patents": "achievements",
}

class SectionDetector:
    """
    A conservative, generic section detector that identifies structural headings
    and segments document text into distinct sections.
    """

    @staticmethod
    def normalize_heading(raw_heading: str) -> str:
        """
        Maps a detected heading to a canonical identifier.
        If unrecognized, produces a clean snake_case slug.
        """
        cleaned = raw_heading.strip().rstrip(":").lower()
        cleaned = re.sub(r'^[0-9\.\-\•\*\s]+', '', cleaned).strip()

        if cleaned in KNOWN_SECTION_ALIASES:
            return KNOWN_SECTION_ALIASES[cleaned]

        slug = re.sub(r'[^a-z0-9]+', '_', cleaned).strip('_')
        return slug or "unclassified"

    @classmethod
    def is_heading_candidate(cls, line: str) -> bool:
        """
        Determines whether a single line of text represents a plausible section heading.
        Heuristics:
        - Short (<= 50 chars, 1-6 words)
        - No sentence-ending punctuation (. ? !)
        - Matches a known alias OR is ALL CAPS OR Title Case with trailing colon
        """
        line_clean = line.strip()
        if not line_clean:
            return False

        if len(line_clean) > 50:
            return False

        # Ignore lines with typical sentence terminal punctuation
        if line_clean.endswith((".", "?", "!", ";", ",")):
            return False

        # Remove leading list enumeration (e.g., '1.', 'A.', '•')
        unprefixed = re.sub(r'^[0-9\.\-\•\*\s]+', '', line_clean).strip()
        unprefixed_no_colon = unprefixed.rstrip(":")

        words = unprefixed_no_colon.split()
        if not words or len(words) > 6:
            return False

        lower_text = unprefixed_no_colon.lower()

        # Check 1: Known section alias match
        if lower_text in KNOWN_SECTION_ALIASES:
            return True

        # Check 2: All uppercase heading with at least 3 letters
        letters = [c for c in unprefixed_no_colon if c.isalpha()]
        if len(letters) >= 3 and unprefixed_no_colon.isupper():
            return True

        # Check 3: Explicit trailing colon with Title-cased words (e.g. "Core Responsibilities:")
        if line_clean.endswith(":") and all(w[0].isupper() for w in words if w and w[0].isalpha()):
            return True

        return False

    @classmethod
    def detect_sections(cls, pages: List[DocumentPage]) -> Tuple[Dict[str, str], List[DocumentSection]]:
        """
        Detects sections across extracted pages and segments the document text.
        Returns:
            - sections: Dict[str, str] mapping canonical names to section text
            - detected_sections: List[DocumentSection] with provenance (title, canonical_name, start_page, text)
        """
        sections_map: Dict[str, List[str]] = {}
        detected_list: List[DocumentSection] = []

        current_raw_heading: Optional[str] = None
        current_canonical: Optional[str] = None
        current_start_page: int = 1
        current_lines: List[str] = []

        for page in pages:
            # Process line by line from the page's normalized text
            lines = page.normalized_text.split("\n")
            for line in lines:
                clean_line = line.strip()
                if not clean_line:
                    continue

                if cls.is_heading_candidate(clean_line):
                    # Commit previous section if exists
                    if current_canonical:
                        section_text = "\n".join(current_lines).strip()
                        if section_text or current_raw_heading:
                            sections_map.setdefault(current_canonical, []).append(section_text)
                            detected_list.append(
                                DocumentSection(
                                    title=current_raw_heading or current_canonical,
                                    canonical_name=current_canonical,
                                    text=section_text,
                                    start_page=current_start_page
                                )
                            )

                    # Start new section
                    current_raw_heading = clean_line.rstrip(":")
                    current_canonical = cls.normalize_heading(clean_line)
                    current_start_page = page.page_number
                    current_lines = []
                else:
                    if current_canonical:
                        current_lines.append(clean_line)

        # Commit final section
        if current_canonical:
            section_text = "\n".join(current_lines).strip()
            if section_text or current_raw_heading:
                sections_map.setdefault(current_canonical, []).append(section_text)
                detected_list.append(
                    DocumentSection(
                        title=current_raw_heading or current_canonical,
                        canonical_name=current_canonical,
                        text=section_text,
                        start_page=current_start_page
                    )
                )

        # Merge section lines into consolidated string values
        flattened_sections = {
            k: "\n\n".join(filter(None, v)).strip() 
            for k, v in sections_map.items()
        }

        return flattened_sections, detected_list
