import re
from typing import List, Optional
from app.schemas.candidate import CandidateProject
from app.schemas.domain import Evidence
from app.services.jd_analyzer.taxonomy import extract_technologies, extract_all_technologies

class ProjectExtractor:
    """
    Extracts structured candidate project entries with titles, descriptions,
    technologies used, and source provenance.
    """

    @classmethod
    def extract_projects(
        cls,
        projects_text: str,
        section_name: str = "Projects",
        page_number: int = 1
    ) -> List[CandidateProject]:
        if not projects_text.strip():
            return []

        entries: List[CandidateProject] = []
        lines = [l.strip() for l in projects_text.split("\n") if l.strip()]

        current_name: Optional[str] = None
        current_desc_lines: List[str] = []

        def commit_project():
            nonlocal current_name, current_desc_lines
            if current_name:
                desc = "\n".join(current_desc_lines).strip()
                full_text = f"{current_name}\n{desc}".strip()
                techs = extract_all_technologies(full_text)
                ev = Evidence(
                    source_text=full_text,
                    source_section=section_name,
                    confidence_score=0.90,
                    page_number=page_number,
                    evidence_type="project_entry"
                )
                entries.append(
                    CandidateProject(
                        name=current_name,
                        description=desc,
                        technologies=techs,
                        evidence=ev
                    )
                )
            current_name = None
            current_desc_lines = []

        for line in lines:
            # Bullet lines or descriptive lines
            is_bullet = bool(re.match(r'^[•\-\*0-9\.]+', line))
            clean = re.sub(r'^[•\-\*0-9\.]+', '', line).strip()

            # Project title heuristics:
            # Short line, not a bullet, or format "Project Name | Technologies" or "Project Name: Description"
            if not is_bullet and (len(clean.split()) <= 6 or "|" in clean or ":" in clean) and not current_name:
                title = clean.split("|")[0].split(":")[0].strip()
                current_name = title
                # If there's more after delimiter, add to desc
                if "|" in clean:
                    current_desc_lines.append(clean.split("|", 1)[1].strip())
                elif ":" in clean:
                    current_desc_lines.append(clean.split(":", 1)[1].strip())
            elif not is_bullet and len(clean.split()) <= 5 and not clean.endswith((".", ";", ",")):
                # New project title detected
                commit_project()
                current_name = clean
            else:
                if current_name:
                    current_desc_lines.append(clean)
                else:
                    current_name = clean

        commit_project()
        return entries
