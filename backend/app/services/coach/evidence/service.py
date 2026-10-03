import re
import hashlib
import datetime
from typing import List, Dict, Optional, Any
from app.schemas.candidate import CandidateProfile
from app.schemas.evidence_vault import (
    VaultEvidenceItem,
    EvidenceVault,
    EvidenceType,
    EvidenceSummary,
)

METRIC_PATTERNS = [
    re.compile(
        r'(\b\d+(?:\.\d+)?%|\b\d+x\b|\$\d+(?:,\d+)*(?:\.\d+)?|\b\d+\s*(?:ms|seconds|minutes|hours|days|weeks|months|years)\b|\b\d+\+?\s*(?:users|clients|teams|projects|engineers|requests|transactions)\b)',
        re.IGNORECASE
    )
]

class EvidenceVaultService:
    """
    Manages the candidate's Evidence Vault.
    Converts extracted resume entities into standardized, indexed, verifiable VaultEvidenceItems.
    Serves as the single source of truth for the Career Twin.
    """

    @staticmethod
    def generate_evidence_id(
        candidate_id: str,
        source_text: str = "",
        index: Optional[int] = None,
        source_document: Optional[str] = None,
        page_number: Optional[int] = 1,
        source_section: Optional[str] = None,
        evidence_type: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Generates a stable, reproducible, deterministic evidence ID.
        Hashes canonical representation of:
        (candidate_id, source_document, page_number, source_section, evidence_type, source_text)
        """
        canonical = "|".join([
            str(candidate_id or "").strip().lower(),
            str(source_document or "").strip().lower(),
            str(page_number or 1),
            str(source_section or "").strip().lower(),
            str(evidence_type or "").strip().upper(),
            str(source_text or "").strip().lower(),
        ])
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
        return f"ev_{digest}"

    def extract_normalized_facts(
        self,
        source_text: str,
        known_techs: Optional[List[str]] = None,
        entity_name: Optional[str] = None
    ) -> List[str]:
        """
        Extracts atomic facts supported exclusively by the source text.
        Guarantees no hallucinated facts are introduced.
        """
        if not source_text:
            return []
        
        facts: List[str] = []
        text_lower = source_text.lower()

        # 1. Add primary entity if verbatim present in text
        if entity_name and entity_name.lower() in text_lower:
            facts.append(entity_name.strip())

        # 2. Add explicit metrics found in source text
        for pat in METRIC_PATTERNS:
            for match in pat.finditer(source_text):
                metric_str = match.group(0).strip()
                if metric_str not in facts:
                    facts.append(metric_str)

        # 3. Add recognized technologies that appear as word boundaries in text
        if known_techs:
            for tech in known_techs:
                if not tech or len(tech) < 2:
                    continue
                # Match technology as word or delimiter
                escaped = re.escape(tech)
                if re.search(rf'(?<![a-zA-Z0-9]){escaped}(?![a-zA-Z0-9])', text_lower, re.IGNORECASE):
                    if tech not in facts:
                        facts.append(tech)

        return facts

    def build_vault(self, profile: CandidateProfile) -> EvidenceVault:
        """
        Builds a comprehensive EvidenceVault from a parsed CandidateProfile.
        Extracts atomic facts across skills, experience, education, certifications, and projects.
        Guarantees idempotency and deterministic evidence identifiers.
        """
        cid = profile.candidate_id
        doc_name = profile.filename or "resume.pdf"
        items: List[VaultEvidenceItem] = []
        seen_ids = set()

        section_idx: Dict[str, List[str]] = {}
        tech_idx: Dict[str, List[str]] = {}
        type_idx: Dict[str, List[str]] = {}
        skill_idx: Dict[str, List[str]] = {}
        project_idx: Dict[str, List[str]] = {}
        experience_idx: Dict[str, List[str]] = {}

        # All known skills for fact-checking
        all_candidate_techs = list(set([s.name for s in profile.skill_details if s.name] + profile.skills + profile.technologies))

        def register_item(
            source_text: str,
            source_section: Optional[str],
            page_number: Optional[int],
            evidence_type: str,
            confidence: float = 1.0,
            related_entity: Optional[str] = None,
            related_skill: Optional[str] = None,
            related_project: Optional[str] = None,
            related_experience: Optional[str] = None,
            technologies: Optional[List[str]] = None,
            metadata: Optional[Dict[str, Any]] = None
        ):
            if not source_text or not source_text.strip():
                return
            clean_text = source_text.strip()
            
            ev_id = self.generate_evidence_id(
                candidate_id=cid,
                source_text=clean_text,
                source_document=doc_name,
                page_number=page_number or 1,
                source_section=source_section,
                evidence_type=evidence_type
            )
            
            # Avoid duplicate identical items within the same vault
            if ev_id in seen_ids:
                return
            seen_ids.add(ev_id)

            techs = [t.strip() for t in (technologies or []) if t.strip()]
            
            # Extract grounded atomic facts
            facts = self.extract_normalized_facts(
                source_text=clean_text,
                known_techs=all_candidate_techs,
                entity_name=related_entity or related_skill or related_project
            )

            item = VaultEvidenceItem(
                evidence_id=ev_id,
                candidate_id=cid,
                source_text=clean_text,
                normalized_facts=facts,
                source_document=doc_name,
                source_section=source_section,
                page_number=page_number or 1,
                evidence_type=evidence_type,
                confidence=confidence,
                related_entity=related_entity,
                related_skill=related_skill,
                related_project=related_project,
                related_experience=related_experience,
                related_technologies=techs,
                metadata=metadata or {}
            )
            items.append(item)

            # Inverted indices
            sec_key = (source_section or "general").strip().lower()
            section_idx.setdefault(sec_key, []).append(ev_id)

            type_key = evidence_type.strip().upper()
            type_idx.setdefault(type_key, []).append(ev_id)
            type_idx.setdefault(evidence_type.strip().lower(), []).append(ev_id)

            for t in techs:
                tech_idx.setdefault(t.lower(), []).append(ev_id)

            if related_skill:
                skill_idx.setdefault(related_skill.strip().lower(), []).append(ev_id)
            if related_project:
                project_idx.setdefault(related_project.strip().lower(), []).append(ev_id)
            if related_experience:
                experience_idx.setdefault(related_experience.strip().lower(), []).append(ev_id)

        # 1. Professional Summary
        if profile.summary and profile.summary.strip():
            register_item(
                source_text=profile.summary,
                source_section="Summary",
                page_number=1,
                evidence_type=EvidenceType.SUMMARY.value,
                confidence=1.0,
                related_entity="Summary"
            )

        # 2. Skills
        for skill in profile.skill_details:
            name = skill.name or skill.raw_name
            ev = skill.evidence
            register_item(
                source_text=ev.source_text if ev else name,
                source_section=ev.source_section if ev else "Skills",
                page_number=ev.page_number if ev else 1,
                evidence_type=EvidenceType.SKILL.value,
                confidence=ev.confidence_score if ev else 1.0,
                related_entity=name,
                related_skill=name,
                technologies=[name],
                metadata={"category": skill.category, "canonical_name": skill.name}
            )

        # 3. Work Experience Entries & Bullets
        for exp in profile.experience:
            ev = exp.evidence
            role_header = f"{exp.role or 'Position'} at {exp.company or 'Company'}"
            if exp.start_date:
                role_header += f" ({exp.start_date} - {exp.end_date or 'Present'})"

            exp_name = f"{exp.role or 'Role'} - {exp.company or 'Company'}"

            # Role / Experience entry
            register_item(
                source_text=role_header,
                source_section=ev.source_section if ev else "Experience",
                page_number=ev.page_number if ev else 1,
                evidence_type=EvidenceType.EXPERIENCE.value,
                confidence=0.95,
                related_entity=exp.company,
                related_experience=exp_name,
                technologies=exp.technologies,
                metadata={
                    "role": exp.role,
                    "company": exp.company,
                    "start_date": exp.start_date,
                    "end_date": exp.end_date,
                    "duration_months": exp.duration_months,
                    "is_current": exp.is_current
                }
            )

            # Dates evidence if explicitly present
            if exp.start_date:
                date_text = f"Employed at {exp.company or 'Company'} from {exp.start_date} to {exp.end_date or 'Present'}"
                register_item(
                    source_text=date_text,
                    source_section=ev.source_section if ev else "Experience",
                    page_number=ev.page_number if ev else 1,
                    evidence_type=EvidenceType.DATE.value,
                    confidence=0.95,
                    related_entity=exp.company,
                    related_experience=exp_name,
                    metadata={"start_date": exp.start_date, "end_date": exp.end_date}
                )

            # Individual bullet points
            if exp.description:
                for line in exp.description.split("\n"):
                    clean_line = line.strip().strip("•-* ")
                    if len(clean_line) > 10:
                        # Detect if bullet contains a quantifiable metric
                        has_metric = any(pat.search(clean_line) for pat in METRIC_PATTERNS)
                        ev_type = EvidenceType.METRIC.value if has_metric else EvidenceType.RESPONSIBILITY.value

                        register_item(
                            source_text=clean_line,
                            source_section=ev.source_section if ev else "Experience",
                            page_number=ev.page_number if ev else 1,
                            evidence_type=ev_type,
                            confidence=0.90,
                            related_entity=exp.company,
                            related_experience=exp_name,
                            technologies=exp.technologies,
                            metadata={"parent_role": exp.role, "parent_company": exp.company}
                        )

        # 4. Education
        for edu in profile.education:
            ev = edu.evidence
            edu_text = f"{edu.degree or 'Degree'} in {edu.field_of_study or 'Field'} at {edu.institution or 'Institution'}"
            if edu.grade_or_gpa:
                edu_text += f" (GPA: {edu.grade_or_gpa})"
            register_item(
                source_text=ev.source_text if ev else edu_text,
                source_section=ev.source_section if ev else "Education",
                page_number=ev.page_number if ev else 1,
                evidence_type=EvidenceType.EDUCATION.value,
                confidence=ev.confidence_score if ev else 1.0,
                related_entity=edu.institution,
                metadata={"degree": edu.degree, "field": edu.field_of_study, "gpa": edu.grade_or_gpa}
            )

        # 5. Certifications
        for cert in profile.certifications:
            ev = cert.evidence
            cert_text = f"{cert.name} by {cert.issuer or 'Issuer'}"
            if cert.date:
                cert_text += f" ({cert.date})"
            register_item(
                source_text=ev.source_text if ev else cert_text,
                source_section=ev.source_section if ev else "Certifications",
                page_number=ev.page_number if ev else 1,
                evidence_type=EvidenceType.CERTIFICATION.value,
                confidence=ev.confidence_score if ev else 1.0,
                related_entity=cert.issuer or cert.name,
                metadata={"issuer": cert.issuer, "date": cert.date}
            )

        # 6. Projects
        for proj in profile.projects:
            ev = proj.evidence
            proj_title = proj.name or "Project"
            proj_text = f"{proj_title}: {proj.description or ''}".strip(": ")
            register_item(
                source_text=ev.source_text if ev else proj_text,
                source_section=ev.source_section if ev else "Projects",
                page_number=ev.page_number if ev else 1,
                evidence_type=EvidenceType.PROJECT.value,
                confidence=ev.confidence_score if ev else 0.90,
                related_entity=proj_title,
                related_project=proj_title,
                technologies=proj.technologies,
                metadata={"name": proj.name}
            )

            # Project bullet / responsibilities if description has multiple lines
            if proj.description and "\n" in proj.description:
                for line in proj.description.split("\n"):
                    clean_line = line.strip().strip("•-* ")
                    if len(clean_line) > 10:
                        has_metric = any(pat.search(clean_line) for pat in METRIC_PATTERNS)
                        ev_type = EvidenceType.METRIC.value if has_metric else EvidenceType.RESPONSIBILITY.value
                        register_item(
                            source_text=clean_line,
                            source_section=ev.source_section if ev else "Projects",
                            page_number=ev.page_number if ev else 1,
                            evidence_type=ev_type,
                            confidence=0.88,
                            related_entity=proj_title,
                            related_project=proj_title,
                            technologies=proj.technologies
                        )

        # Build summary counts
        by_type_counts: Dict[str, int] = {}
        for it in items:
            t = it.evidence_type.upper()
            by_type_counts[t] = by_type_counts.get(t, 0) + 1

        summary = EvidenceSummary(
            total=len(items),
            skills=by_type_counts.get(EvidenceType.SKILL.value, 0),
            projects=by_type_counts.get(EvidenceType.PROJECT.value, 0),
            experience=by_type_counts.get(EvidenceType.EXPERIENCE.value, 0) + by_type_counts.get(EvidenceType.RESPONSIBILITY.value, 0),
            education=by_type_counts.get(EvidenceType.EDUCATION.value, 0),
            certifications=by_type_counts.get(EvidenceType.CERTIFICATION.value, 0),
            achievements=by_type_counts.get(EvidenceType.ACHIEVEMENT.value, 0),
            metrics=by_type_counts.get(EvidenceType.METRIC.value, 0),
            by_type=by_type_counts
        )

        vault = EvidenceVault(
            vault_id=f"vault_{cid}",
            candidate_id=cid,
            total_items=len(items),
            items=items,
            summary=summary,
            section_index=section_idx,
            technology_index=tech_idx,
            type_index=type_idx,
            skill_index=skill_idx,
            project_index=project_idx,
            experience_index=experience_idx
        )
        return vault

    def query_evidence_by_technology(self, vault: EvidenceVault, tech_name: str) -> List[VaultEvidenceItem]:
        """Finds all evidence items associated with a given technology or skill."""
        t_clean = tech_name.strip().lower()
        matching_ids = vault.technology_index.get(t_clean, [])
        return [item for item in vault.items if item.evidence_id in matching_ids]

    def query_evidence_by_section(self, vault: EvidenceVault, section_name: str) -> List[VaultEvidenceItem]:
        """Finds all evidence items under a specific section heading."""
        s_clean = section_name.strip().lower()
        matching_ids = vault.section_index.get(s_clean, [])
        return [item for item in vault.items if item.evidence_id in matching_ids]

    def filter_evidence(
        self,
        vault: EvidenceVault,
        section: Optional[str] = None,
        evidence_type: Optional[str] = None,
        skill: Optional[str] = None,
        project: Optional[str] = None,
        experience: Optional[str] = None
    ) -> List[VaultEvidenceItem]:
        """
        Unified filtering method for Evidence Explorer.
        Filters across multiple criteria simultaneously.
        """
        filtered = vault.items

        if section:
            s_clean = section.strip().lower()
            filtered = [
                it for it in filtered
                if it.source_section and s_clean in it.source_section.lower()
            ]

        if evidence_type:
            t_clean = evidence_type.strip().upper()
            filtered = [
                it for it in filtered
                if it.evidence_type.upper() == t_clean
            ]

        if skill:
            sk_clean = skill.strip().lower()
            filtered = [
                it for it in filtered
                if (it.related_skill and sk_clean in it.related_skill.lower())
                or any(sk_clean in t.lower() for t in it.related_technologies)
                or any(sk_clean == f.lower() for f in it.normalized_facts)
                or sk_clean in it.source_text.lower()
            ]

        if project:
            p_clean = project.strip().lower()
            filtered = [
                it for it in filtered
                if (it.related_project and p_clean in it.related_project.lower())
                or (it.source_section and "project" in it.source_section.lower() and p_clean in it.source_text.lower())
            ]

        if experience:
            e_clean = experience.strip().lower()
            filtered = [
                it for it in filtered
                if (it.related_experience and e_clean in it.related_experience.lower())
                or (it.related_entity and e_clean in it.related_entity.lower())
                or (it.source_section and "experience" in it.source_section.lower() and e_clean in it.source_text.lower())
            ]

        return filtered
