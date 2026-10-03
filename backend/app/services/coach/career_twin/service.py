import re
import datetime
from typing import List, Optional, Dict, Any, Tuple
from app.schemas.candidate import CandidateProfile, CandidateProject
from app.schemas.career_twin import (
    CareerTwin,
    CareerTimelineEvent,
    CareerSkillNode,
    CareerProjectNode,
    CareerAchievementNode,
)
from app.schemas.evidence_vault import EvidenceVault

METRIC_PATTERNS = [
    re.compile(
        r'(\b\d+(?:\.\d+)?%|\b\d+x\b|\$\d+(?:,\d+)*(?:\.\d+)?|\b\d+\s*(?:ms|seconds|minutes|hours|days|weeks|months|years)\b|\b\d+\+?\s*(?:users|clients|teams|projects|engineers|requests|transactions)\b)',
        re.IGNORECASE
    )
]

class CareerTwinService:
    """
    Transforms a CandidateProfile into a dynamic, queryable, evidence-grounded CareerTwin graph.
    Extracts career timelines, skill nodes, project nodes, and verified achievements without inventing ungrounded facts.
    """

    def build_twin(self, profile: CandidateProfile, vault: Optional[EvidenceVault] = None) -> CareerTwin:
        cid = profile.candidate_id
        twin_id = f"twin_{cid}"

        # 1. Timeline construction with evidence grounding
        timeline = self._build_timeline(profile, vault)

        # 2. Total experience calculation
        total_months = sum((exp.duration_months or 0.0) for exp in profile.experience)

        # 3. Achievements extraction from bullet points with metrics
        achievements = self._extract_achievements(profile, vault)

        # 4. Skill Nodes with tenure, role associations, occurrence count, and evidence references
        skill_nodes = self._build_skill_nodes(profile, vault)

        # 5. Project Nodes with responsibilities, metrics, and evidence references
        project_nodes = self._build_project_nodes(profile, vault)

        # 6. Evidence Summary
        if vault:
            evidence_summary = {
                "total": vault.total_items,
                "skills": vault.summary.skills,
                "projects": vault.summary.projects,
                "experience": vault.summary.experience,
                "education": vault.summary.education,
                "certifications": vault.summary.certifications,
                "achievements": len(achievements),
                "metrics": vault.summary.metrics,
            }
        else:
            evidence_summary = {
                "total": len(profile.evidence),
                "skills": len(profile.skills),
                "projects": len(profile.projects),
                "experience": len(profile.experience),
                "education": len(profile.education),
                "certifications": len(profile.certifications),
                "achievements": len(achievements),
                "metrics": len(achievements),
            }

        twin = CareerTwin(
            twin_id=twin_id,
            candidate_id=cid,
            name=profile.name,
            email=profile.email,
            phone=profile.phone,
            summary=profile.summary,
            skills=profile.skills,
            technologies=profile.technologies,
            skill_nodes=skill_nodes,
            experience=profile.experience,
            education=profile.education,
            certifications=profile.certifications,
            projects=profile.projects,
            project_nodes=project_nodes,
            timeline=timeline,
            achievements=achievements,
            total_experience_months=round(total_months, 1),
            evidence_count=vault.total_items if vault else len(profile.evidence),
            evidence_summary=evidence_summary,
            raw_text=profile.raw_text,
            created_at=datetime.datetime.utcnow().isoformat(),
            candidate_profile=profile,
        )
        return twin

    def _build_timeline(self, profile: CandidateProfile, vault: Optional[EvidenceVault] = None) -> List[CareerTimelineEvent]:
        events: List[CareerTimelineEvent] = []
        idx = 0

        # Work experience events
        for exp in profile.experience:
            idx += 1
            date_disp = f"{exp.start_date or 'Past'} - {exp.end_date or 'Present'}"
            
            # Find evidence references in vault
            ev_refs = []
            if vault:
                exp_key = f"{exp.role or ''} {exp.company or ''}".strip().lower()
                for item in vault.items:
                    if item.related_experience and exp_key in item.related_experience.lower():
                        ev_refs.append(item.evidence_id)
                    elif exp.company and item.related_entity and exp.company.lower() in item.related_entity.lower():
                        ev_refs.append(item.evidence_id)
            
            events.append(
                CareerTimelineEvent(
                    event_id=f"evt_exp_{idx}",
                    date_display=date_disp,
                    title=exp.role or "Software Engineer",
                    organization=exp.company,
                    event_type="work",
                    description=(exp.description[:200] + "...") if len(exp.description) > 200 else exp.description,
                    is_current=exp.is_current,
                    duration_months=exp.duration_months,
                    evidence_id=ev_refs[0] if ev_refs else None,
                    evidence_references=ev_refs[:5]
                )
            )

        # Education events
        for edu in profile.education:
            idx += 1
            date_disp = f"{edu.start_date or ''} - {edu.end_date or 'Completed'}".strip(" -")
            
            ev_refs = []
            if vault:
                edu_key = (edu.institution or edu.degree or "").lower()
                for item in vault.items:
                    if item.evidence_type.upper() == "EDUCATION" and (edu_key in item.source_text.lower() or (item.related_entity and edu_key in item.related_entity.lower())):
                        ev_refs.append(item.evidence_id)

            events.append(
                CareerTimelineEvent(
                    event_id=f"evt_edu_{idx}",
                    date_display=date_disp or "Education Milestone",
                    title=f"{edu.degree or 'Degree'} {edu.field_of_study or ''}".strip(),
                    organization=edu.institution,
                    event_type="education",
                    description=f"Grade/GPA: {edu.grade_or_gpa}" if edu.grade_or_gpa else "",
                    evidence_id=ev_refs[0] if ev_refs else None,
                    evidence_references=ev_refs[:3]
                )
            )

        # Projects
        for proj in profile.projects:
            idx += 1
            ev_refs = []
            if vault:
                p_key = (proj.name or "").lower()
                for item in vault.items:
                    if item.related_project and p_key in item.related_project.lower():
                        ev_refs.append(item.evidence_id)
                    elif p_key in item.source_text.lower():
                        ev_refs.append(item.evidence_id)

            events.append(
                CareerTimelineEvent(
                    event_id=f"evt_prj_{idx}",
                    date_display="Project Milestone",
                    title=proj.name,
                    organization=None,
                    event_type="project",
                    description=(proj.description[:150] + "...") if proj.description and len(proj.description) > 150 else (proj.description or ""),
                    evidence_id=ev_refs[0] if ev_refs else None,
                    evidence_references=ev_refs[:3]
                )
            )

        return events

    def _extract_achievements(self, profile: CandidateProfile, vault: Optional[EvidenceVault] = None) -> List[CareerAchievementNode]:
        achievements: List[CareerAchievementNode] = []
        idx = 0

        # Scan experience descriptions for metric lines
        for exp in profile.experience:
            if not exp.description:
                continue
            for line in exp.description.split("\n"):
                clean = line.strip().strip("•-* ")
                if len(clean) < 15:
                    continue
                # Check for quantifiable metrics
                for pat in METRIC_PATTERNS:
                    match = pat.search(clean)
                    if match:
                        idx += 1
                        metric_val = match.group(0)
                        
                        # Find matching evidence in vault
                        ev_refs = []
                        if vault:
                            for item in vault.items:
                                if metric_val in item.source_text or clean[:30].lower() in item.source_text.lower():
                                    ev_refs.append(item.evidence_id)

                        achievements.append(
                            CareerAchievementNode(
                                achievement_id=f"ach_{idx}",
                                headline=clean[:100] + ("..." if len(clean) > 100 else ""),
                                context=f"{exp.role or 'Role'} at {exp.company or 'Company'}",
                                metric=metric_val,
                                evidence_id=ev_refs[0] if ev_refs else None,
                                evidence_references=ev_refs[:3]
                            )
                        )
                        break

        return achievements

    def _build_skill_nodes(self, profile: CandidateProfile, vault: Optional[EvidenceVault] = None) -> List[CareerSkillNode]:
        nodes: List[CareerSkillNode] = []
        seen = set()

        # Build full text for occurrence counting
        full_resume_text = (profile.raw_text or "").lower()

        for s in profile.skill_details:
            name = s.name or s.raw_name
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())

            # Find roles where this skill was used
            related_roles = []
            verified_tenure = 0.0
            for exp in profile.experience:
                full_exp = f"{exp.role or ''} {exp.company or ''} {exp.description or ''} {' '.join(exp.technologies)}".lower()
                if name.lower() in full_exp:
                    if exp.role and exp.role not in related_roles:
                        related_roles.append(exp.role)
                    if exp.duration_months:
                        verified_tenure += exp.duration_months

            # Find projects where this skill was used
            related_projects = []
            for proj in profile.projects:
                full_proj = f"{proj.name or ''} {proj.description or ''} {' '.join(proj.technologies)}".lower()
                if name.lower() in full_proj and proj.name:
                    related_projects.append(proj.name)

            # Count occurrences across resume text
            escaped_name = re.escape(name.lower())
            occurrences = len(re.findall(rf'(?<![a-zA-Z0-9]){escaped_name}(?![a-zA-Z0-9])', full_resume_text))
            occurrence_count = max(1, occurrences)

            # Look up evidence references in vault
            ev_refs: List[str] = []
            if vault:
                matching_items = vault.technology_index.get(name.lower(), [])
                if not matching_items:
                    matching_items = vault.skill_index.get(name.lower(), [])
                if not matching_items:
                    # Find by text
                    for item in vault.items:
                        if name.lower() in item.source_text.lower() or any(name.lower() == t.lower() for t in item.related_technologies):
                            ev_refs.append(item.evidence_id)
                else:
                    ev_refs = list(matching_items)

            confidence = min(1.0, 0.85 + (0.03 * len(ev_refs))) if ev_refs else 0.80

            nodes.append(
                CareerSkillNode(
                    name=name,
                    category=s.category or "technology",
                    raw_name=s.raw_name,
                    verified_tenure_months=round(verified_tenure, 1) if verified_tenure > 0 else None,
                    occurrence_count=occurrence_count,
                    confidence=round(confidence, 2),
                    related_roles=related_roles,
                    related_projects=related_projects,
                    evidence_id=ev_refs[0] if ev_refs else None,
                    evidence_references=ev_refs
                )
            )

        return nodes

    def _build_project_nodes(self, profile: CandidateProfile, vault: Optional[EvidenceVault] = None) -> List[CareerProjectNode]:
        nodes: List[CareerProjectNode] = []
        for proj in profile.projects:
            responsibilities: List[str] = []
            metrics: List[str] = []
            desc = proj.description or ""

            if "\n" in desc:
                for line in desc.split("\n"):
                    clean = line.strip().strip("•-* ")
                    if len(clean) > 8:
                        responsibilities.append(clean)
                        for pat in METRIC_PATTERNS:
                            m = pat.search(clean)
                            if m:
                                metrics.append(m.group(0))
            elif desc.strip():
                responsibilities.append(desc.strip())
                for pat in METRIC_PATTERNS:
                    m = pat.search(desc)
                    if m:
                        metrics.append(m.group(0))

            # Find matching evidence references
            ev_refs: List[str] = []
            if vault:
                p_name_lower = proj.name.lower()
                for item in vault.items:
                    if item.related_project and p_name_lower in item.related_project.lower():
                        ev_refs.append(item.evidence_id)
                    elif (item.source_section and "project" in item.source_section.lower() and p_name_lower in item.source_text.lower()):
                        ev_refs.append(item.evidence_id)

            nodes.append(
                CareerProjectNode(
                    name=proj.name,
                    description=proj.description,
                    technologies=proj.technologies,
                    responsibilities=responsibilities,
                    metrics=metrics,
                    evidence_references=ev_refs
                )
            )
        return nodes
