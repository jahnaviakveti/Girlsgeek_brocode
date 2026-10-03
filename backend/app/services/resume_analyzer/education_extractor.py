import re
from typing import List, Optional
from app.schemas.candidate import CandidateEducation
from app.schemas.domain import Evidence
from app.services.resume_analyzer.date_parser import parse_date_range

DEGREE_PATTERNS = [
    re.compile(r'\b(b\.?tech(?:nology)?|b\.?e\.?|bachelor(?:\s+of\s+[a-zA-Z]+)?(?:\'?s)?(?:\s+degree)?)\b', re.IGNORECASE),
    re.compile(r'\b(m\.?tech(?:nology)?|m\.?s\.?|m\.?sc\.?|master(?:\s+of\s+[a-zA-Z]+)?(?:\'?s)?(?:\s+degree)?)\b', re.IGNORECASE),
    re.compile(r'\b(b\.?s\.?|b\.?sc\.?|bachelor\s+of\s+science)\b', re.IGNORECASE),
    re.compile(r'\b(b\.?a\.?|bachelor\s+of\s+arts)\b', re.IGNORECASE),
    re.compile(r'\b(ph\.?d\.?|doctorate|doctor\s+of\s+philosophy)\b', re.IGNORECASE),
    re.compile(r'\b(associate(?:\'?s)?(?:\s+degree)?|diploma)\b', re.IGNORECASE),
]

MAJOR_PATTERNS = [
    re.compile(r'(?:in|of|-|–)\s+([A-Za-z\s&]+?)(?:,|\.|\(|$|\n|\d)', re.IGNORECASE),
]

INSTITUTION_INDICATORS = [
    "university", "institute", "college", "school", "academy", "polytechnic", "campus"
]

GPA_PATTERN = re.compile(
    r'\b(?:gpa|cgpa|grade|percentage)?\s*(?:[:=])?\s*(\d+(?:\.\d+)?\s*(?:/\s*\d+(?:\.\d+)?)?|\d+%(?:\s*cgpa)?)\b',
    re.IGNORECASE
)

class EducationExtractor:
    """
    Extracts structured education entries (degree, major, institution, dates, GPA).
    """

    @classmethod
    def extract_education(
        cls,
        education_text: str,
        section_name: str = "Education",
        page_number: int = 1
    ) -> List[CandidateEducation]:
        if not education_text.strip():
            return []

        entries: List[CandidateEducation] = []
        lines = [l.strip() for l in education_text.split("\n") if l.strip()]

        current_entry_lines: List[str] = []

        def process_block(block_lines: List[str]):
            if not block_lines:
                return

            full_block = " ".join(block_lines)
            s_date, e_date, _, _ = parse_date_range(full_block)

            # Extract degree and major from the line containing degree
            degree: Optional[str] = None
            major: Optional[str] = None
            for line in block_lines:
                for deg_pat in DEGREE_PATTERNS:
                    m = deg_pat.search(line)
                    if m:
                        degree = m.group(0).strip()
                        remainder = line[m.end():].strip()
                        m_maj = re.search(r'^(?:in|of|-|–)?\s*([A-Za-z\s&]+?)(?:,|\.|\(|$|\||\d)', remainder, re.IGNORECASE)
                        if m_maj:
                            cand_maj = m_maj.group(1).strip()
                            if len(cand_maj) >= 2 and not any(ind in cand_maj.lower() for ind in INSTITUTION_INDICATORS):
                                major = cand_maj
                        break
                if degree:
                    break

            # Extract institution
            institution: Optional[str] = None
            for line in block_lines:
                if any(ind in line.lower() for ind in INSTITUTION_INDICATORS):
                    inst_clean = re.sub(r'\(.*?\)', '', line).strip()
                    institution = inst_clean.split("|")[0].strip()
                    break

            # Extract GPA precisely (e.g. GPA: 3.8/4.0 or GPA: 3.9)
            gpa: Optional[str] = None
            g_match = re.search(
                r'\b(?:gpa|cgpa|grade)\s*[:=]?\s*([0-4](?:\.\d+)?\s*/\s*4(?:\.0)?|[0-9](?:\.\d+)?\s*/\s*10(?:\.0)?|\d+(?:\.\d+)?%?)',
                full_block,
                re.IGNORECASE
            )
            if g_match:
                gpa = g_match.group(1).strip()

            if degree or institution:
                ev = Evidence(
                    source_text="\n".join(block_lines),
                    source_section=section_name,
                    confidence_score=0.95 if degree and institution else 0.85,
                    page_number=page_number,
                    evidence_type="education_entry"
                )
                entries.append(
                    CandidateEducation(
                        degree=degree,
                        field_of_study=major,
                        institution=institution,
                        start_date=s_date,
                        end_date=e_date,
                        grade_or_gpa=gpa,
                        evidence=ev
                    )
                )

        # Chunk lines by blank lines or bullets
        for line in lines:
            is_new_item = bool(re.match(r'^[•\-\*0-9\.]+', line)) or any(deg_pat.search(line) for deg_pat in DEGREE_PATTERNS)
            if is_new_item and current_entry_lines:
                process_block(current_entry_lines)
                current_entry_lines = [line]
            else:
                current_entry_lines.append(line)

        if current_entry_lines:
            process_block(current_entry_lines)

        return entries
