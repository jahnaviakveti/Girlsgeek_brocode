import re
import uuid
from typing import List, Set, Optional, Tuple
from app.schemas.document import GenericDocument, DocumentPage
from app.schemas.domain import JobDescription, JDRequirement, RequirementCategory, RequirementPriority
from app.services.jd_analyzer.patterns import (
    REQUIREMENT_LEAD_INS,
    REQUIRED_SIGNALS,
    PREFERRED_SIGNALS,
    EXPERIENCE_YEARS_SINGLE,
    EXPERIENCE_YEARS_RANGE,
    EDUCATION_DEGREES,
    CERTIFICATION_SIGNALS,
    REQUIRED_SECTION_NAMES,
    PREFERRED_SECTION_NAMES,
)
from app.services.jd_analyzer.taxonomy import extract_technologies, extract_all_technologies
from app.services.jd_analyzer.granularity import decompose_requirement

# Common boilerplate / non-requirement phrases to filter out for false-positive protection
BOILERPLATE_PATTERNS = [
    re.compile(r'\b(equal\s+opportunity\s+employer|affirmative\s+action)\b', re.IGNORECASE),
    re.compile(r'\b(competitive\s+(?:salary|compensation|benefits)|health\s+insurance|401k)\b', re.IGNORECASE),
    re.compile(r'\b(about\s+(?:us|our\s+company|the\s+team)|who\s+we\s+are|company\s+overview)\b', re.IGNORECASE),
    re.compile(r'\b(we\s+are\s+looking\s+for|we\s+are\s+seeking|our\s+mission\s+is)\b', re.IGNORECASE),
    re.compile(r'\b(working\s+with\s+a\s+collaborative\s+(?:engineering\s+)?team)\b', re.IGNORECASE),
    re.compile(r'\b(fast-paced\s+environment|fun\s+place\s+to\s+work|dynamic\s+workplace)\b', re.IGNORECASE),
]

class JDAnalyzer:
    """
    Local, deterministic, rule-based Job Description Analyzer.
    Extracts structured requirements (skills, experience, education, certifications, domain)
    from a GenericDocument without external APIs or cloud LLMs.
    """

    @classmethod
    def is_actionable_candidate(cls, text: str, section_name: Optional[str] = None) -> bool:
        """
        Determines whether a text snippet represents an actionable job requirement,
        filtering out generic company boilerplate and conversational filler.
        """
        clean = text.strip()
        if not clean or len(clean) < 4:
            return False

        # 1. Filter out obvious boilerplate
        for bp in BOILERPLATE_PATTERNS:
            if bp.search(clean):
                return False

        # 2. If inside a designated requirement section, accept unless it's a heading
        if section_name:
            sec_lower = section_name.lower().strip()
            if sec_lower in REQUIRED_SECTION_NAMES or sec_lower in PREFERRED_SECTION_NAMES or "skill" in sec_lower or "qualification" in sec_lower:
                if len(clean.split()) >= 2:
                    return True

        # 3. Check for requirement lead-ins (e.g. 'experience with', 'knowledge of')
        for lead_in in REQUIREMENT_LEAD_INS:
            if lead_in.search(clean):
                return True

        # 4. Check for explicit priority signals (e.g. 'must have', 'required', 'is a plus')
        for sig in REQUIRED_SIGNALS + PREFERRED_SIGNALS:
            if sig.search(clean):
                return True

        # 5. Check for education, experience, or certification markers
        for edu in EDUCATION_DEGREES:
            if edu.search(clean):
                return True

        if EXPERIENCE_YEARS_SINGLE.search(clean) or EXPERIENCE_YEARS_RANGE.search(clean):
            return True

        for cert in CERTIFICATION_SIGNALS:
            if cert.search(clean):
                return True

        # 6. Check for known or unfamiliar technology tokens accompanied by contextual action
        techs = extract_all_technologies(clean)
        if techs and (len(clean.split()) <= 6 or any(verb in clean.lower() for verb in ["with", "in", "using", "stack", "experience", "knowledge", "platform", "tool"])):
            return True

        return False

    @classmethod
    def reconstruct_sentences(cls, text_block: str) -> List[str]:
        """
        Reconstructs wrapped lines into complete grammatical units and bullet points.
        Handles soft line breaks inside paragraphs.
        """
        raw_lines = [l.strip() for l in text_block.split("\n") if l.strip()]
        reconstructed: List[str] = []
        current = ""

        for line in raw_lines:
            is_bullet = bool(re.match(r'^[0-9\.\-\•\*\s]+', line))
            if not current:
                current = line
            elif is_bullet or current.endswith((".", "?", "!", ":")):
                reconstructed.append(current)
                current = line
            else:
                # Soft wrap inside a sentence
                current += " " + line

        if current:
            reconstructed.append(current)

        final_units: List[str] = []
        for unit in reconstructed:
            clean = re.sub(r'^[0-9\.\-\•\*\s]+', '', unit).strip()
            # If a unit contains multiple complete sentences, split on terminal punctuation
            if ". " in clean and len(clean) > 60:
                sentences = re.split(r'(?<=[.!?])\s+', clean)
                for s in sentences:
                    s_clean = s.strip()
                    if s_clean:
                        final_units.append(s_clean)
            else:
                if clean:
                    final_units.append(clean)

        return final_units

    @classmethod
    def extract_candidates_from_page(cls, page: DocumentPage) -> List[Tuple[str, int, Optional[str]]]:
        """
        Extracts candidate requirement strings from a page while preserving sentence and bullet boundaries.
        Returns list of (candidate_text, page_number, section_name).
        """
        units = cls.reconstruct_sentences(page.normalized_text)
        return [(u, page.page_number, None) for u in units]

    @classmethod
    def analyze(cls, document: GenericDocument) -> JobDescription:
        """
        Analyzes a GenericDocument representing a Job Description and produces a structured JobDescription.
        """
        extracted_requirements: List[JDRequirement] = []
        seen_signatures: Set[str] = set()

        # Phase 1: Process detected sections if available
        for section in document.detected_sections:
            sec_name = section.canonical_name
            units = cls.reconstruct_sentences(section.text)
            for unit in units:
                if cls.is_actionable_candidate(unit, section_name=sec_name):
                    reqs = decompose_requirement(
                        text=unit,
                        source_text=unit,
                        page_number=section.start_page,
                        source_section=section.title
                    )
                    for r in reqs:
                        sig = f"{r.category.value}:{r.requirement_text.lower().strip()}"
                        if sig not in seen_signatures:
                            seen_signatures.add(sig)
                            extracted_requirements.append(r)

        # Phase 2: If few or no requirements found via sections, inspect reconstructed page streams
        if len(extracted_requirements) < 2:
            for page in document.pages:
                raw_candidates = cls.extract_candidates_from_page(page)
                for cand_text, p_num, s_name in raw_candidates:
                    if cls.is_actionable_candidate(cand_text, section_name=s_name):
                        reqs = decompose_requirement(
                            text=cand_text,
                            source_text=cand_text,
                            page_number=p_num,
                            source_section=s_name or "General Body"
                        )
                        for r in reqs:
                            sig = f"{r.category.value}:{r.requirement_text.lower().strip()}"
                            if sig not in seen_signatures:
                                seen_signatures.add(sig)
                                extracted_requirements.append(r)

        jd_id = f"jd_{document.document_id[:8]}" if document.document_id else f"jd_{uuid.uuid4().hex[:8]}"
        title = document.filename.replace(".pdf", "").replace("_", " ").title()

        return JobDescription(
            jd_id=jd_id,
            title=title,
            raw_text=document.raw_text,
            normalized_text=document.normalized_text,
            document_id=document.document_id,
            requirements=extracted_requirements,
        )

def analyze_jd(document: GenericDocument) -> JobDescription:
    """
    Convenience function to analyze a GenericDocument into a structured JobDescription.
    """
    return JDAnalyzer.analyze(document)
