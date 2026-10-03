import re
from typing import List, Set, Dict, Tuple, Optional
from app.schemas.candidate import CandidateSkill
from app.schemas.domain import Evidence
from app.schemas.document import GenericDocument
from app.services.jd_analyzer.taxonomy import (
    CANONICAL_TECHNOLOGIES,
    extract_technologies,
    extract_unfamiliar_terms,
    extract_all_technologies,
)

# Aspirational / learning cues indicating a skill is NOT yet acquired
ASPIRATIONAL_CUES = [
    re.compile(r'\b(interested\s+in\s+(?:learning|exploring|gaining))\b', re.IGNORECASE),
    re.compile(r'\b(plans?\s+to\s+learn|looking\s+to\s+learn|seeking\s+to\s+learn)\b', re.IGNORECASE),
    re.compile(r'\b(aspiring\s+to\s+learn|hopes?\s+to\s+learn)\b', re.IGNORECASE),
    re.compile(r'\b(future\s+interest|basic\s+theoretical\s+knowledge)\b', re.IGNORECASE),
]

# Generic non-technical soft words to exclude from technical skill extraction
GENERIC_EXCLUSIONS = {
    "communication", "leadership", "teamwork", "collaborative", "hardworking",
    "problem solving", "critical thinking", "management", "flexibility", "punctuality",
    "responsible", "dedication", "motivation", "interpersonal skills", "enthusiastic",
    "passionate", "creative", "presentation", "analytical", "adaptability", "experience",
    "projects", "education", "summary", "responsibilities"
}

class SkillExtractor:
    """
    Extracts, normalizes, and validates candidate skills and technologies.
    Includes false-positive protection against aspirational learning mentions,
    preserves unfamiliar technical terms, and provides evidence provenance.
    """

    @classmethod
    def is_aspirational(cls, text: str) -> bool:
        """
        Checks if a statement expresses future aspiration rather than active skill.
        e.g., 'Interested in learning Python'
        """
        for cue in ASPIRATIONAL_CUES:
            if cue.search(text):
                return True
        return False

    @classmethod
    def extract_skills_from_text(
        cls,
        text: str,
        section_name: str,
        page_number: int = 1
    ) -> List[CandidateSkill]:
        """
        Extracts candidate skills from a text block with evidence tracking.
        """
        extracted: List[CandidateSkill] = []
        seen_names: Set[str] = set()

        lines = text.split("\n")
        for line in lines:
            clean_line = line.strip()
            if not clean_line:
                continue

            # False-positive protection: skip aspirational statements
            if cls.is_aspirational(clean_line):
                continue

            # Strip bullet prefixes
            stripped = re.sub(r'^[0-9\.\-\•\*\s]+', '', clean_line).strip()

            # 1. Extract known canonical technologies
            known_hits = extract_technologies(stripped)
            for tech in known_hits:
                if tech.lower() not in seen_names and tech.lower() not in GENERIC_EXCLUSIONS:
                    seen_names.add(tech.lower())
                    ev = Evidence(
                        source_text=clean_line,
                        source_section=section_name,
                        confidence_score=1.0,
                        page_number=page_number,
                        evidence_type="canonical_match"
                    )
                    extracted.append(
                        CandidateSkill(
                            name=tech,
                            raw_name=tech,
                            category="technology",
                            evidence=ev
                        )
                    )

            # 2. Extract unfamiliar technical terms if in a designated skills context
            if "skill" in section_name.lower() or "tool" in section_name.lower():
                unfamiliar = extract_unfamiliar_terms(stripped)
                for unfam in unfamiliar:
                    if unfam.lower() not in seen_names and unfam.lower() not in GENERIC_EXCLUSIONS:
                        seen_names.add(unfam.lower())
                        ev = Evidence(
                            source_text=clean_line,
                            source_section=section_name,
                            confidence_score=0.85,
                            page_number=page_number,
                            evidence_type="unfamiliar_extracted"
                        )
                        extracted.append(
                            CandidateSkill(
                                name=unfam,
                                raw_name=unfam,
                                category="other_skill",
                                evidence=ev
                            )
                        )

                # Comma-separated or colon-separated skill lists:
                # e.g., "Languages: Python, Go, CustomScript"
                if ":" in stripped:
                    _, rhs = stripped.split(":", 1)
                    tokens = [t.strip().strip(".,;") for t in re.split(r'[,|•]', rhs) if t.strip()]
                    for tok in tokens:
                        # If token is clean 1-3 words, capitalized or identifier-like
                        if (
                            1 <= len(tok.split()) <= 3
                            and len(tok) >= 2
                            and tok.lower() not in seen_names
                            and tok.lower() not in GENERIC_EXCLUSIONS
                            and not tok.lower().startswith(("e.g", "etc", "such as"))
                        ):
                            # Check if known
                            known = extract_technologies(tok)
                            canonical = known[0] if known else tok
                            seen_names.add(canonical.lower())
                            ev = Evidence(
                                source_text=clean_line,
                                source_section=section_name,
                                confidence_score=0.90,
                                page_number=page_number,
                                evidence_type="skill_list_item"
                            )
                            extracted.append(
                                CandidateSkill(
                                    name=canonical,
                                    raw_name=tok,
                                    category="technology" if known else "other_skill",
                                    evidence=ev
                                )
                            )

        return extracted

    @classmethod
    def extract_all_skills(
        cls, 
        document: GenericDocument,
        sections_map: Dict[str, str],
        provenance_map: Dict[str, Tuple[str, int]]
    ) -> List[CandidateSkill]:
        """
        Extracts and dedupes all skills across document sections with preference
        given to Skills section evidence.
        """
        all_skills: List[CandidateSkill] = []
        seen: Set[str] = set()

        # Step 1: Scan Skills section first
        skills_text = sections_map.get("skills", "")
        p_info = provenance_map.get("skills", ("Skills", 1))
        if skills_text:
            sec_skills = cls.extract_skills_from_text(
                skills_text, 
                section_name=p_info[0], 
                page_number=p_info[1]
            )
            for s in sec_skills:
                if s.name.lower() not in seen:
                    seen.add(s.name.lower())
                    all_skills.append(s)

        # Step 2: Scan Experience and Projects sections for mentioned technologies
        for sec_key in ["experience", "projects"]:
            sec_text = sections_map.get(sec_key, "")
            p_info = provenance_map.get(sec_key, (sec_key.title(), 1))
            if sec_text:
                context_skills = cls.extract_skills_from_text(
                    sec_text,
                    section_name=p_info[0],
                    page_number=p_info[1]
                )
                for s in context_skills:
                    if s.name.lower() not in seen:
                        seen.add(s.name.lower())
                        all_skills.append(s)

        # Step 3: If no structured sections found, scan pages directly
        if not all_skills:
            for page in document.pages:
                page_skills = cls.extract_skills_from_text(
                    page.normalized_text,
                    section_name="General Body",
                    page_number=page.page_number
                )
                for s in page_skills:
                    if s.name.lower() not in seen:
                        seen.add(s.name.lower())
                        all_skills.append(s)

        return all_skills
