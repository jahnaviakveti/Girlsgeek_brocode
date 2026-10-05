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

        LINK_LABELS = {
            "project repo link", "repo link", "repository", "github", "github link", 
            "project link", "demo link", "live demo", "video demo link", "doi", "publication link",
            "source code", "link"
        }

        def is_link_label(text: str) -> bool:
            t = text.lower().strip()
            t_clean = re.sub(r'[^a-z0-9\s]', '', t)
            if t_clean in LINK_LABELS:
                return True
            if "://" in t or t.startswith("www."):
                return True
            for prefix in ["github", "link", "demo", "repo", "doi", "http", "project repo link"]:
                if t.startswith(prefix + ":") or t.startswith(prefix + " :") or t.startswith(prefix + "-"):
                    return True
            return False

        for line in lines:
            # Bullet lines or descriptive lines
            is_bullet = bool(re.match(r'^[•\-\*0-9\.–—−\u2013\u2014\u2212\u2022]+', line))
            clean = re.sub(r'^[•\-\*0-9\.–—−\u2013\u2014\u2212\u2022]+', '', line).strip()

            if is_link_label(clean):
                if current_name:
                    current_desc_lines.append(clean)
                else:
                    # If there's no current project, treat as a generic line (maybe a stray link)
                    current_name = clean
                continue

            # Project title heuristics
            is_title = False
            title_candidate = clean
            desc_part = ""

            if not is_bullet and not clean.endswith((".", ";")):
                if "|" in clean or ":" in clean:
                    is_title = True
                    delim = "|" if "|" in clean else ":"
                    title_candidate = clean.split(delim)[0].strip()
                    desc_part = clean.split(delim, 1)[1].strip()
                elif len(clean.split()) <= 10 and clean.count(',') < 2:
                    is_title = True

            if is_title:
                # If we already have a project with some description/bullets, this is definitely a new project
                if current_name and current_desc_lines:
                    commit_project()
                    current_name = title_candidate
                    if desc_part:
                        current_desc_lines.append(desc_part)
                elif not current_name:
                    current_name = title_candidate
                    if desc_part:
                        current_desc_lines.append(desc_part)
                else:
                    # If we have a name but no desc lines yet, this line might just be part of the title or subtitle
                    current_desc_lines.append(clean)
            else:
                if current_name:
                    current_desc_lines.append(clean)
                else:
                    current_name = clean

        commit_project()
        return entries
