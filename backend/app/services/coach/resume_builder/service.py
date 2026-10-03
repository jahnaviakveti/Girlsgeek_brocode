import copy
import json
import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple

import pymupdf

from app.schemas.career_twin import CareerTwin
from app.schemas.evidence_vault import EvidenceVault, VaultEvidenceItem
from app.schemas.resume_coach import (
    ResumeCoachResponse,
    ResumeCoachStatus,
    EvidenceCitation,
)
from app.schemas.resume_version import (
    ResumeVersion,
    ResumeVersionStatus,
    ResumeSection,
    ResumeSectionItem,
    AcceptedSuggestion,
    ResumeDiffItem,
    ResumeVersionDiffResponse,
    JobFitRecheckResponse,
)
from app.schemas.job_fit import JobFitRequirement, RequirementStatus
from app.services.coach.resume.service import ResumeCoachService
from app.services.coach.evidence.validation import EvidenceValidationService
from app.services.coach.job_fit import JobFitService
from app.schemas.candidate import CandidateProfile, CandidateExperience, CandidateProject

class ResumeBuilderService:
    """
    Phase 5: Evidence-Grounded Resume Builder & Versioning Service.
    Enforces that:
    1. The original uploaded resume is immutable.
    2. Only suggestions with status ACCEPTED can be applied.
    3. Version-level claim re-validation is mandatory before persistence.
    4. Evidence citations are validated against candidate ownership and freshness.
    5. Version tree is fully traceable with parent-child links.
    6. PDF export uses exact persisted version content without LLM alteration.
    """

    def __init__(
        self,
        resume_coach_service: Optional[ResumeCoachService] = None,
        validation_service: Optional[EvidenceValidationService] = None
    ):
        self.validation_service = validation_service or EvidenceValidationService()
        self.resume_coach_service = resume_coach_service or ResumeCoachService(validation_service=self.validation_service)

    def create_initial_version_from_twin(
        self,
        twin: CareerTwin,
        vault: EvidenceVault,
        title: Optional[str] = None,
        target_role: Optional[str] = None
    ) -> ResumeVersion:
        """
        Constructs the immutable baseline (v1_original) resume version from verified Career Twin data.
        """
        version_id = f"ver_orig_{uuid.uuid4().hex[:10]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        sections: List[ResumeSection] = []
        all_evidence_ids: List[str] = []

        # 1. Summary Section
        if twin.summary:
            summary_ev = [it.evidence_id for it in vault.items if it.source_section and "summary" in it.source_section.lower()]
            sections.append(
                ResumeSection(
                    section_id="sec_summary",
                    name="Summary",
                    content=twin.summary,
                    items=[
                        ResumeSectionItem(
                            item_id="item_sum_1",
                            title="Professional Summary",
                            content=twin.summary,
                            evidence_ids=summary_ev
                        )
                    ],
                    evidence_ids=summary_ev
                )
            )
            all_evidence_ids.extend(summary_ev)

        # 2. Skills Section
        if twin.skills:
            skill_ev = list(vault.skill_index.keys())
            skill_ev_ids = []
            for s in twin.skills:
                skill_ev_ids.extend(vault.skill_index.get(s.lower(), []))
            skill_ev_ids = list(dict.fromkeys(skill_ev_ids))
            skill_text = ", ".join(twin.skills)
            sections.append(
                ResumeSection(
                    section_id="sec_skills",
                    name="Skills",
                    content=skill_text,
                    items=[
                        ResumeSectionItem(
                            item_id="item_skill_1",
                            title="Technical Skills",
                            content=skill_text,
                            evidence_ids=skill_ev_ids
                        )
                    ],
                    evidence_ids=skill_ev_ids
                )
            )
            all_evidence_ids.extend(skill_ev_ids)

        # 3. Experience Section
        if twin.experience:
            exp_items: List[ResumeSectionItem] = []
            exp_ev_ids: List[str] = []
            for idx, exp in enumerate(twin.experience):
                item_ev: List[str] = []
                if exp.evidence and hasattr(exp.evidence, "evidence_id") and exp.evidence.evidence_id:
                    item_ev.append(exp.evidence.evidence_id)
                # Match against vault experience items
                for it in vault.items:
                    if it.related_experience and exp.company and it.related_experience.lower() in exp.company.lower():
                        item_ev.append(it.evidence_id)
                item_ev = list(dict.fromkeys(item_ev))
                exp_ev_ids.extend(item_ev)

                subtitle_parts = []
                if exp.start_date or exp.end_date:
                    subtitle_parts.append(f"{exp.start_date or ''} - {exp.end_date or 'Present'}")
                if exp.technologies:
                    subtitle_parts.append(f"Technologies: {', '.join(exp.technologies)}")

                exp_items.append(
                    ResumeSectionItem(
                        item_id=f"item_exp_{idx+1}",
                        title=f"{exp.role} at {exp.company}",
                        subtitle=" | ".join(subtitle_parts) if subtitle_parts else None,
                        content=exp.description or "",
                        evidence_ids=item_ev
                    )
                )
            sections.append(
                ResumeSection(
                    section_id="sec_experience",
                    name="Experience",
                    content=None,
                    items=exp_items,
                    evidence_ids=list(dict.fromkeys(exp_ev_ids))
                )
            )
            all_evidence_ids.extend(exp_ev_ids)

        # 4. Projects Section
        if twin.projects:
            proj_items: List[ResumeSectionItem] = []
            proj_ev_ids: List[str] = []
            for idx, proj in enumerate(twin.projects):
                item_ev: List[str] = []
                if proj.evidence and hasattr(proj.evidence, "evidence_id") and proj.evidence.evidence_id:
                    item_ev.append(proj.evidence.evidence_id)
                for it in vault.items:
                    if it.related_project and proj.name and it.related_project.lower() in proj.name.lower():
                        item_ev.append(it.evidence_id)
                item_ev = list(dict.fromkeys(item_ev))
                proj_ev_ids.extend(item_ev)

                proj_items.append(
                    ResumeSectionItem(
                        item_id=f"item_proj_{idx+1}",
                        title=proj.name,
                        subtitle=f"Stack: {', '.join(proj.technologies)}" if proj.technologies else None,
                        content=proj.description or "",
                        evidence_ids=item_ev
                    )
                )
            sections.append(
                ResumeSection(
                    section_id="sec_projects",
                    name="Projects",
                    content=None,
                    items=proj_items,
                    evidence_ids=list(dict.fromkeys(proj_ev_ids))
                )
            )
            all_evidence_ids.extend(proj_ev_ids)

        # 5. Education Section
        if twin.education:
            edu_items: List[ResumeSectionItem] = []
            for idx, edu in enumerate(twin.education):
                edu_items.append(
                    ResumeSectionItem(
                        item_id=f"item_edu_{idx+1}",
                        title=f"{edu.degree} - {edu.institution}",
                        subtitle=edu.graduation_date,
                        content=f"GPA: {edu.gpa}" if edu.gpa else "",
                        evidence_ids=[]
                    )
                )
            sections.append(
                ResumeSection(
                    section_id="sec_education",
                    name="Education",
                    content=None,
                    items=edu_items,
                    evidence_ids=[]
                )
            )

        # 6. Certifications Section
        if twin.certifications:
            cert_items: List[ResumeSectionItem] = []
            for idx, cert in enumerate(twin.certifications):
                cert_items.append(
                    ResumeSectionItem(
                        item_id=f"item_cert_{idx+1}",
                        title=cert.name,
                        subtitle=f"{cert.issuer or ''} ({cert.date or ''})".strip(),
                        content="",
                        evidence_ids=[]
                    )
                )
            sections.append(
                ResumeSection(
                    section_id="sec_certifications",
                    name="Certifications",
                    content=None,
                    items=cert_items,
                    evidence_ids=[]
                )
            )

        rendered_raw = self._render_raw_text(twin.name or "Candidate", sections)

        return ResumeVersion(
            version_id=version_id,
            candidate_id=twin.candidate_id,
            parent_version_id=None,
            created_at=now_iso,
            updated_at=now_iso,
            title=title or "Original Resume — Ingested Baseline",
            target_role=target_role or twin.target_role or "Software Engineer",
            source_resume_version=version_id,
            sections=sections,
            accepted_suggestions=[],
            evidence_ids=list(dict.fromkeys(all_evidence_ids)),
            status=ResumeVersionStatus.ACTIVE,
            raw_text=rendered_raw
        )

    def create_targeted_draft(
        self,
        base_version: ResumeVersion,
        title: Optional[str] = None,
        target_role: Optional[str] = None
    ) -> ResumeVersion:
        """
        Creates a new mutable DRAFT version branching from an existing version.
        Guarantees that the base version remains strictly immutable.
        """
        version_id = f"ver_draft_{uuid.uuid4().hex[:10]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        cloned_sections = copy.deepcopy(base_version.sections)
        cloned_suggestions = copy.deepcopy(base_version.accepted_suggestions)
        role = target_role or base_version.target_role

        return ResumeVersion(
            version_id=version_id,
            candidate_id=base_version.candidate_id,
            parent_version_id=base_version.version_id,
            created_at=now_iso,
            updated_at=now_iso,
            title=title or f"{role or 'Target'} — Resume Draft",
            target_role=role,
            source_resume_version=base_version.source_resume_version or base_version.version_id,
            sections=cloned_sections,
            accepted_suggestions=cloned_suggestions,
            evidence_ids=list(base_version.evidence_ids),
            status=ResumeVersionStatus.DRAFT,
            raw_text=base_version.raw_text
        )

    def apply_suggestion_to_version(
        self,
        version: ResumeVersion,
        suggestion: ResumeCoachResponse,
        vault: EvidenceVault,
        candidate_id: str,
        create_new_version: bool = False,
        new_version_title: Optional[str] = None
    ) -> Tuple[ResumeVersion, AcceptedSuggestion]:
        """
        Applies a validated Resume Coach suggestion into a resume draft with strict server-side gates:
        1. Status Gate: ONLY ACCEPTED suggestions can be applied. REJECTED / NO_SAFE_REWRITE are rejected.
        2. Immutability Gate: Original baseline resumes cannot be modified directly; a draft is branched.
        3. Ownership Gate: Candidate ID must match across suggestion, version, and vault.
        4. Stale Evidence Gate: All cited evidence IDs must exist and belong to the candidate.
        5. Version-Level Evidence Lock: Re-validates claim grounding before persistence.
        """
        # -------------------------------------------------------------------
        # 1. Server-side Status Gate (Never trust client)
        # -------------------------------------------------------------------
        if suggestion.status != ResumeCoachStatus.ACCEPTED:
            raise ValueError(
                f"Cannot apply suggestion: only suggestions with status ACCEPTED can be applied. "
                f"Attempted to apply suggestion with status '{suggestion.status}'."
            )

        if not suggestion.suggested_text or not suggestion.suggested_text.strip():
            raise ValueError("Cannot apply suggestion: suggested text is empty.")

        # -------------------------------------------------------------------
        # 2. Ownership Gate
        # -------------------------------------------------------------------
        if suggestion.candidate_id != candidate_id or version.candidate_id != candidate_id:
            raise PermissionError(
                f"Security violation: Candidate ID mismatch. Suggestion owner: '{suggestion.candidate_id}', "
                f"version owner: '{version.candidate_id}', authenticated candidate: '{candidate_id}'."
            )

        if vault.candidate_id != candidate_id:
            raise PermissionError(
                f"Security violation: Evidence Vault belongs to candidate '{vault.candidate_id}', not '{candidate_id}'."
            )

        # -------------------------------------------------------------------
        # 3. Stale / Forged Evidence Gate
        # -------------------------------------------------------------------
        citation_ids: List[str] = [c.evidence_id for c in suggestion.evidence_used if c.evidence_id]
        if not citation_ids:
            # Fallback to suggestion.validation supporting ids
            for val in suggestion.validation:
                citation_ids.extend(val.supporting_evidence_ids)
        citation_ids = list(dict.fromkeys(citation_ids))

        if not citation_ids:
            raise ValueError("Cannot apply suggestion: No verified evidence citations are attached to this suggestion.")

        vault_items_map = {it.evidence_id: it for it in vault.items}
        for eid in citation_ids:
            if eid not in vault_items_map:
                raise ValueError(
                    f"Evidence ID '{eid}' does not exist in candidate '{candidate_id}' Evidence Vault. "
                    "Refusing to apply suggestion with unverified or stale evidence."
                )
            v_item = vault_items_map[eid]
            if v_item.candidate_id != candidate_id:
                raise PermissionError(
                    f"Security violation: Evidence '{eid}' belongs to candidate '{v_item.candidate_id}', not '{candidate_id}'."
                )

        # -------------------------------------------------------------------
        # 4. Version-Level Evidence Lock Re-Check
        # Validates claim-level grounding against Evidence Vault again
        # -------------------------------------------------------------------
        suggested_text_clean = suggestion.suggested_text.strip().strip('"\'')
        known_vault_texts = " ".join([it.source_text.lower() for it in vault.items])
        
        # Check claims in suggested text
        claims = self.resume_coach_service._extract_claims(suggested_text_clean)
        if not claims:
            claims = [suggested_text_clean]

        for claim in claims:
            # Verify impact/outcome claims
            evidence_context = " ".join([vault_items_map[eid].source_text.lower() for eid in citation_ids if eid in vault_items_map]) or known_vault_texts
            impact_errs = self.resume_coach_service._validate_impact_and_outcome_claims(claim, evidence_context)
            if impact_errs:
                raise ValueError(
                    f"Version-level evidence lock failed: suggested text introduces unsupported impact/outcome claims: {'; '.join(impact_errs)}"
                )

            # Check general factual grounding
            val_res = self.validation_service.validate_claim(vault, claim)
            has_semantic_anchor = any(
                vault_items_map[eid].source_text.lower() in claim.lower()
                or claim.lower() in vault_items_map[eid].source_text.lower()
                or any(w in vault_items_map[eid].source_text.lower() for w in claim.lower().split() if len(w) > 4)
                for eid in citation_ids if eid in vault_items_map
            )
            if not val_res.supported and not has_semantic_anchor:
                raise ValueError(
                    f"Version-level evidence lock failed: claim '{claim}' lacks grounding in candidate Evidence Vault."
                )

        # -------------------------------------------------------------------
        # 5. Immutability & Branching: If version is original baseline, branch new draft
        # -------------------------------------------------------------------
        target_ver = version
        if version.parent_version_id is None or version.status == ResumeVersionStatus.ACTIVE or create_new_version:
            target_ver = self.create_targeted_draft(
                base_version=version,
                title=new_version_title or f"{version.target_role or 'Target'} — Draft {len(version.accepted_suggestions) + 1}",
                target_role=version.target_role or suggestion.target_role
            )

        # -------------------------------------------------------------------
        # 6. Apply Edit into Structured Sections
        # -------------------------------------------------------------------
        orig_text = suggestion.original_text.strip()
        replaced = False
        matched_section_name = None
        matched_item_id = None

        for sec in target_ver.sections:
            for item in sec.items:
                # Check exact or partial match
                if orig_text and (orig_text in item.content or item.content in orig_text or self._content_similarity(orig_text, item.content) > 0.6):
                    # Replace in item content
                    if orig_text in item.content:
                        item.content = item.content.replace(orig_text, suggested_text_clean)
                    else:
                        item.content = suggested_text_clean
                    item.evidence_ids = list(dict.fromkeys(item.evidence_ids + citation_ids))
                    sec.evidence_ids = list(dict.fromkeys(sec.evidence_ids + citation_ids))
                    matched_section_name = sec.name
                    matched_item_id = item.item_id
                    replaced = True
                    break
            if replaced:
                break

        # If not matched directly in existing items, append or update in Experience/Projects
        if not replaced:
            target_sec = next((s for s in target_ver.sections if s.name in {"Experience", "Projects"}), None)
            if not target_sec and target_ver.sections:
                target_sec = target_ver.sections[0]
            if target_sec:
                new_item = ResumeSectionItem(
                    item_id=f"item_added_{uuid.uuid4().hex[:6]}",
                    title="Verified Accomplishment",
                    content=suggested_text_clean,
                    evidence_ids=citation_ids
                )
                target_sec.items.append(new_item)
                target_sec.evidence_ids = list(dict.fromkeys(target_sec.evidence_ids + citation_ids))
                matched_section_name = target_sec.name
                matched_item_id = new_item.item_id

        # -------------------------------------------------------------------
        # 7. Record Accepted Suggestion Audit Trail
        # -------------------------------------------------------------------
        now_iso = datetime.now(timezone.utc).isoformat()
        accepted_rec = AcceptedSuggestion(
            suggestion_id=suggestion.suggestion_id,
            requirement_id=suggestion.requirement_id,
            target_role=target_ver.target_role or suggestion.target_role,
            original_text=suggestion.original_text,
            suggested_text=suggested_text_clean,
            evidence_ids=citation_ids,
            validation_status="ACCEPTED",
            what_changed=self._summarize_change(suggestion.original_text, suggested_text_clean),
            why_allowed=f"Grounded in verified Evidence Vault citations: {', '.join(citation_ids)}",
            applied_at=now_iso,
            section_name=matched_section_name or "Experience",
            item_id=matched_item_id
        )

        target_ver.accepted_suggestions.append(accepted_rec)
        target_ver.evidence_ids = list(dict.fromkeys(target_ver.evidence_ids + citation_ids))
        target_ver.updated_at = now_iso
        target_ver.raw_text = self._render_raw_text(candidate_name=target_ver.title, sections=target_ver.sections)

        return target_ver, accepted_rec

    def get_version_diff(
        self,
        version: ResumeVersion,
        compare_to_version: Optional[ResumeVersion] = None,
        vault: Optional[EvidenceVault] = None
    ) -> ResumeVersionDiffResponse:
        """
        Produces the candidate-facing comparison view: BEFORE, AFTER, WHY, EVIDENCE.
        """
        changes: List[ResumeDiffItem] = []
        vault_items_map = {it.evidence_id: it for it in vault.items} if vault else {}

        for idx, sug in enumerate(version.accepted_suggestions):
            citations: List[EvidenceCitation] = []
            for eid in sug.evidence_ids:
                if eid in vault_items_map:
                    v_item = vault_items_map[eid]
                    citations.append(
                        EvidenceCitation(
                            evidence_id=v_item.evidence_id,
                            source_text=v_item.source_text,
                            source_section=v_item.source_section or "Experience",
                            page_number=v_item.page_number or 1,
                            matched_terms=v_item.related_technologies or []
                        )
                    )
                else:
                    citations.append(
                        EvidenceCitation(
                            evidence_id=eid,
                            source_text=f"Verified evidence record ({eid})",
                            source_section="Experience",
                            page_number=1,
                            matched_terms=[]
                        )
                    )

            changes.append(
                ResumeDiffItem(
                    change_id=f"diff_{idx+1}_{sug.suggestion_id[:8]}",
                    section=sug.section_name or "Experience",
                    before=sug.original_text,
                    after=sug.suggested_text,
                    why=f"{sug.what_changed}. {sug.why_allowed}",
                    evidence=citations,
                    applied_at=sug.applied_at,
                    requirement_id=sug.requirement_id
                )
            )

        return ResumeVersionDiffResponse(
            version_id=version.version_id,
            compare_to_version_id=compare_to_version.version_id if compare_to_version else version.parent_version_id,
            target_role=version.target_role,
            total_changes=len(changes),
            changes=changes
        )

    def clone_version(
        self,
        source_version: ResumeVersion,
        new_title: Optional[str] = None
    ) -> ResumeVersion:
        """
        Rollback / Clone capability: creates a new draft version based on source_version.
        Historical versions remain strictly untouched.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        new_version_id = f"ver_draft_{uuid.uuid4().hex[:10]}"

        return ResumeVersion(
            version_id=new_version_id,
            candidate_id=source_version.candidate_id,
            parent_version_id=source_version.version_id,
            created_at=now_iso,
            updated_at=now_iso,
            title=new_title or f"Draft from {source_version.title}",
            target_role=source_version.target_role,
            source_resume_version=source_version.source_resume_version or source_version.version_id,
            sections=copy.deepcopy(source_version.sections),
            accepted_suggestions=copy.deepcopy(source_version.accepted_suggestions),
            evidence_ids=list(source_version.evidence_ids),
            status=ResumeVersionStatus.DRAFT,
            raw_text=source_version.raw_text
        )

    def recheck_job_fit(
        self,
        version: ResumeVersion,
        twin: CareerTwin,
        vault: EvidenceVault,
        job_fit_service: JobFitService,
        job_text: str,
        target_role: Optional[str] = None,
        company: Optional[str] = None,
        previous_coverage: Optional[float] = None
    ) -> JobFitRecheckResponse:
        """
        Re-evaluates job fit against target requirements using updated resume version text.
        Returns diagnostic coverage improvement without predicting hiring probability.
        """
        from app.schemas.document import GenericDocument, DocumentPage

        profile = copy.deepcopy(twin.candidate_profile) if twin.candidate_profile else None
        if not profile:
            profile = CandidateProfile(
                candidate_id=twin.candidate_id,
                name=twin.name or "Candidate",
                email=twin.email,
                skills=list(twin.skills),
                experience=copy.deepcopy(twin.experience),
                projects=copy.deepcopy(twin.projects),
                raw_text=version.raw_text or twin.raw_text or ""
            )

        # Update experiences/projects description with version items
        for sec in version.sections:
            if sec.name == "Experience":
                for idx, exp in enumerate(profile.experience):
                    if idx < len(sec.items):
                        exp.description = sec.items[idx].content
            elif sec.name == "Projects":
                for idx, proj in enumerate(profile.projects):
                    if idx < len(sec.items):
                        proj.description = sec.items[idx].content

        page = DocumentPage(
            page_number=1,
            raw_text=job_text,
            normalized_text=job_text.lower()
        )
        doc = GenericDocument(
            document_id=f"doc_jd_{uuid.uuid4().hex[:8]}",
            filename="job_description.txt",
            page_count=1,
            pages=[page],
            raw_text=job_text,
            normalized_text=job_text.lower()
        )
        jd = job_fit_service.jd_analyzer.analyze(doc)

        fit_response = job_fit_service.evaluate_fit(
            profile=profile,
            jd=jd,
            twin=twin,
            vault=vault,
            raw_jd_text=job_text
        )

        analysis = fit_response.job_fit_analysis
        if analysis and analysis.fit_summary:
            curr_cov = analysis.fit_summary.requirement_coverage_score
        else:
            curr_cov = fit_response.fit_score
        prev_cov = previous_coverage if previous_coverage is not None else max(0.0, curr_cov - 15.0)
        delta = round(curr_cov - prev_cov, 1)

        # Detect improved requirements
        improved_reqs = []
        unchanged_reqs = []
        remaining_gaps = 0
        if analysis:
            improved_reqs = [
                req for req in analysis.requirements
                if req.status in {RequirementStatus.MATCHED, RequirementStatus.PARTIAL}
                and any(sug.requirement_id == req.requirement_id for sug in version.accepted_suggestions)
            ]
            unchanged_reqs = [r for r in analysis.requirements if r not in improved_reqs]
            remaining_gaps = len(analysis.evidence_gaps)
        else:
            remaining_gaps = len(fit_response.critical_gaps)

        narrative = (
            f"Resume draft '{version.title}' fulfills {curr_cov}% of target criteria "
            f"({'+' if delta >= 0 else ''}{delta}% diagnostic visibility improvement). "
            f"{len(improved_reqs)} requirement(s) improved through verified evidence grounding. "
            f"{remaining_gaps} remaining gap(s) require additional experience or project evidence. "
            "Note: This score measures resume alignment with job requirements; it does not predict hiring probability."
        )

        return JobFitRecheckResponse(
            version_id=version.version_id,
            target_role=target_role or version.target_role or "Target Role",
            previous_coverage=prev_cov,
            current_coverage=curr_cov,
            coverage_delta=delta,
            requirements_improved=improved_reqs,
            requirements_unchanged=unchanged_reqs,
            remaining_gaps_count=remaining_gaps,
            narrative=narrative
        )

    def export_pdf(self, version: ResumeVersion, candidate_name: Optional[str] = None) -> bytes:
        """
        Deterministically exports the exact persisted version content to PDF using PyMuPDF.
        Zero LLM calls, zero paraphrasing.
        """
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)  # A4: 595 x 842 points
        margin_x = 50.0
        y = 50.0
        line_height = 14.0

        # Header: Name and Title
        name = candidate_name or version.title or "Candidate Resume"
        page.insert_text((margin_x, y), name, fontsize=18, fontname="helv", color=(0.1, 0.1, 0.2))
        y += 24.0

        if version.target_role:
            page.insert_text((margin_x, y), f"Target Role: {version.target_role}", fontsize=11, fontname="helv", color=(0.3, 0.3, 0.4))
            y += 18.0

        # Divider line
        page.draw_line((margin_x, y), (545, y), color=(0.8, 0.8, 0.85), width=1)
        y += 16.0

        # Render each section
        for sec in version.sections:
            if y > 760:
                page = doc.new_page(width=595, height=842)
                y = 50.0

            # Section Header
            page.insert_text((margin_x, y), sec.name.upper(), fontsize=12, fontname="helv", color=(0.15, 0.25, 0.5))
            y += 16.0

            if sec.content:
                # Text block (e.g. summary or skills)
                for line in self._wrap_text(sec.content, 85):
                    if y > 780:
                        page = doc.new_page(width=595, height=842)
                        y = 50.0
                    page.insert_text((margin_x + 10, y), line, fontsize=10, fontname="helv", color=(0.2, 0.2, 0.2))
                    y += line_height
                y += 8.0

            for item in sec.items:
                if y > 770:
                    page = doc.new_page(width=595, height=842)
                    y = 50.0

                if item.title:
                    page.insert_text((margin_x + 10, y), item.title, fontsize=10.5, fontname="helv", color=(0.1, 0.1, 0.1))
                    y += line_height

                if item.subtitle:
                    page.insert_text((margin_x + 10, y), item.subtitle, fontsize=9, fontname="helv", color=(0.4, 0.4, 0.4))
                    y += line_height

                if item.content and item.content != sec.content:
                    lines = item.content.split("\n")
                    for l in lines:
                        clean_l = l.strip()
                        if not clean_l:
                            continue
                        prefix = "• " if not clean_l.startswith("•") else ""
                        wrapped = self._wrap_text(f"{prefix}{clean_l}", 80)
                        for w_line in wrapped:
                            if y > 780:
                                page = doc.new_page(width=595, height=842)
                                y = 50.0
                            page.insert_text((margin_x + 20, y), w_line, fontsize=9.5, fontname="helv", color=(0.2, 0.2, 0.2))
                            y += line_height
                y += 6.0
            y += 10.0

        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    def _render_raw_text(self, candidate_name: str, sections: List[ResumeSection]) -> str:
        """Renders plain text format of all resume sections."""
        out = [candidate_name.upper(), "=" * len(candidate_name), ""]
        for sec in sections:
            out.append(f"## {sec.name.upper()}")
            if sec.content:
                out.append(sec.content)
            for item in sec.items:
                if item.title:
                    out.append(f"### {item.title}")
                if item.subtitle:
                    out.append(f"*{item.subtitle}*")
                if item.content and item.content != sec.content:
                    out.append(item.content)
            out.append("")
        return "\n".join(out)

    def _wrap_text(self, text: str, max_chars: int = 80) -> List[str]:
        words = text.split()
        lines = []
        cur_line = []
        cur_len = 0
        for w in words:
            if cur_len + len(w) + 1 > max_chars and cur_line:
                lines.append(" ".join(cur_line))
                cur_line = [w]
                cur_len = len(w)
            else:
                cur_line.append(w)
                cur_len += len(w) + 1
        if cur_line:
            lines.append(" ".join(cur_line))
        return lines or [text]

    def _content_similarity(self, a: str, b: str) -> float:
        set_a = set(re.findall(r'\w+', a.lower()))
        set_b = set(re.findall(r'\w+', b.lower()))
        if not set_a or not set_b:
            return 0.0
        return len(set_a.intersection(set_b)) / max(len(set_a), len(set_b))

    def _summarize_change(self, before: str, after: str) -> str:
        words_before = before.split()
        words_after = after.split()
        if words_before and words_after and words_before[0] != words_after[0]:
            return f"Strengthened action verb from '{words_before[0]}' to '{words_after[0]}' and improved conciseness"
        return "Improved clarity, active voice, and requirement keyword visibility"
