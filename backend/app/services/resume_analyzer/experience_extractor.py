import re
from typing import List, Optional, Tuple, Dict
from app.schemas.candidate import CandidateExperience
from app.schemas.domain import Evidence
from app.services.resume_analyzer.date_parser import (
    parse_date_range,
    DATE_RANGE_PATTERN,
    SINGLE_DATE_PATTERN,
)
from app.services.jd_analyzer.taxonomy import extract_technologies

COMMON_ROLES = [
    re.compile(r'\b(software\s+engineer(?:ing)?(?:\s+intern)?)\b', re.IGNORECASE),
    re.compile(r'\b(frontend|backend|full\s*stack|fullstack)\s+(developer|engineer|intern)\b', re.IGNORECASE),
    re.compile(r'\b(web\s+developer|mobile\s+developer|ios\s+developer|android\s+developer)\b', re.IGNORECASE),
    re.compile(r'\b(devops\s+engineer|cloud\s+engineer|systems\s+engineer|sre)\b', re.IGNORECASE),
    re.compile(r'\b(data\s+scientist|data\s+analyst|data\s+engineer|ml\s+engineer)\b', re.IGNORECASE),
    re.compile(r'\b(intern|engineering\s+intern|developer\s+intern|research\s+intern)\b', re.IGNORECASE),
    re.compile(r'\b(team\s+lead|tech\s+lead|technical\s+lead|engineering\s+manager)\b', re.IGNORECASE),
]

class ExperienceExtractor:
    """
    Extracts structured work experience entries from the experience section or general text.
    Identifies job titles, employers, normalized date ranges, durations, and technologies used.
    """

    @classmethod
    def is_experience_header_line(cls, line: str) -> bool:
        """
        Checks if a line contains role/title, company, or date range markers.
        """
        clean = line.strip()
        if not clean:
            return False

        # Has date range
        s_date, e_date, _, _ = parse_date_range(clean)
        if s_date is not None:
            return True

        # Has common role
        for role_re in COMMON_ROLES:
            if role_re.search(clean):
                return True

        # Has delimiter pattern: "Role | Company" or "Role at Company"
        if re.search(r'\b(at|@|\|)\b', clean, re.IGNORECASE):
            return True

        return False

    @classmethod
    def parse_header_line(cls, line: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], bool, Optional[float]]:
        """
        Extracts (role, company, start_date, end_date, is_current, duration_months) from a header line.
        """
        clean = line.strip()
        s_date, e_date, is_cur, dur = parse_date_range(clean)

        # Remove date segment from line to isolate role and company
        line_no_date = clean
        if s_date or e_date:
            line_no_date = DATE_RANGE_PATTERN.sub('', line_no_date)
            line_no_date = SINGLE_DATE_PATTERN.sub('', line_no_date)
            line_no_date = re.sub(r'\(\s*\)', '', line_no_date).strip()
            line_no_date = re.sub(r'^[(\[\{]+|[)\]\}]+$', '', line_no_date).strip().strip("|-,")

        role: Optional[str] = None
        company: Optional[str] = None

        # Try separator splitting: "Role | Company" or "Company | Role"
        if "|" in line_no_date:
            parts = [p.strip() for p in line_no_date.split("|") if p.strip()]
            if len(parts) >= 2:
                # Check which part matches a role
                p0_is_role = any(r.search(parts[0]) for r in COMMON_ROLES)
                if p0_is_role:
                    role, company = parts[0], parts[1]
                else:
                    company, role = parts[0], parts[1]
            elif len(parts) == 1:
                role = parts[0]
        elif re.search(r'\bat\b', line_no_date, re.IGNORECASE):
            parts = re.split(r'\bat\b', line_no_date, flags=re.IGNORECASE)
            role = parts[0].strip().strip("|-,")
            company = parts[1].strip().strip("|-,") if len(parts) > 1 else None
        elif "-" in line_no_date:
            parts = [p.strip() for p in line_no_date.split("-") if p.strip()]
            if len(parts) >= 2:
                p0_is_role = any(r.search(parts[0]) for r in COMMON_ROLES)
                if p0_is_role:
                    role, company = parts[0], parts[1]
                else:
                    company, role = parts[0], parts[1]
            elif len(parts) == 1:
                role = parts[0]
        else:
            # Single phrase
            for r_pat in COMMON_ROLES:
                m = r_pat.search(line_no_date)
                if m:
                    role = m.group(0)
                    break
        if role:
            role = role.strip("()[]-|, ")
            if not role:
                role = None
        else:
            role = None

        if company:
            company = company.strip("()[]-|, ")
            if not company:
                company = None
        else:
            company = None

        return role, company, s_date, e_date, is_cur, dur

    @classmethod
    def extract_experience(
        cls,
        experience_text: str,
        section_name: str = "Experience",
        page_number: int = 1
    ) -> List[CandidateExperience]:
        """
        Extracts structured experience entries from the experience section.
        """
        if not experience_text.strip():
            return []

        entries: List[CandidateExperience] = []
        lines = [l.strip() for l in experience_text.split("\n") if l.strip()]

        current_role: Optional[str] = None
        current_company: Optional[str] = None
        current_start: Optional[str] = None
        current_end: Optional[str] = None
        current_is_current: bool = False
        current_duration: Optional[float] = None
        current_desc_lines: List[str] = []
        current_header_text: str = ""

        def commit_entry():
            nonlocal current_role, current_company, current_start, current_end
            nonlocal current_is_current, current_duration, current_desc_lines, current_header_text
            if current_role or current_company or current_desc_lines:
                desc_text = "\n".join(current_desc_lines).strip()
                full_text = f"{current_header_text}\n{desc_text}".strip()
                techs = extract_technologies(full_text)
                ev = Evidence(
                    source_text=full_text,
                    source_section=section_name,
                    confidence_score=0.95 if current_role and current_start else 0.80,
                    page_number=page_number,
                    evidence_type="experience_entry"
                )
                entries.append(
                    CandidateExperience(
                        role=current_role,
                        company=current_company,
                        start_date=current_start,
                        end_date=current_end,
                        is_current=current_is_current,
                        duration_months=current_duration,
                        description=desc_text,
                        technologies=techs,
                        evidence=ev
                    )
                )
            current_role = None
            current_company = None
            current_start = None
            current_end = None
            current_is_current = False
            current_duration = None
            current_desc_lines = []
            current_header_text = ""

        for line in lines:
            if cls.is_experience_header_line(line):
                # Check if this line is an experience entry header
                r, c, s_d, e_d, is_cur, dur = cls.parse_header_line(line)
                if r or c or s_d:
                    # Multi-line header support:
                    # If we have role/company but no start date, and this line provides start date
                    if (current_role or current_company) and not current_start and s_d and not r:
                        current_start = s_d
                        current_end = e_d
                        current_is_current = is_cur
                        current_duration = dur
                        if c and not current_company:
                            current_company = c
                        current_header_text = f"{current_header_text} | {line}"
                        continue
                    # If we have start date but no role, and this line provides role
                    if current_start and not current_role and r and not s_d:
                        current_role = r
                        if c and not current_company:
                            current_company = c
                        current_header_text = f"{line} | {current_header_text}"
                        continue

                    commit_entry()
                    current_role = r
                    current_company = c
                    current_start = s_d
                    current_end = e_d
                    current_is_current = is_cur
                    current_duration = dur
                    current_header_text = line
                    continue

            # Accumulate description line
            if current_role or current_company or current_start:
                current_desc_lines.append(line)
            else:
                # If we don't have an active header yet, check if this line is a role
                for r_pat in COMMON_ROLES:
                    if r_pat.search(line):
                        current_role = line
                        current_header_text = line
                        break
                if not current_role:
                    current_desc_lines.append(line)

        commit_entry()
        return entries
