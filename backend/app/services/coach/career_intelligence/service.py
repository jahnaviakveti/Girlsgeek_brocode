import copy
import re
import json
import uuid
import datetime
from typing import List, Optional, Dict, Any

from app.schemas.domain import JDRequirement, RequirementCategory, RequirementPriority

from app.schemas.career_intelligence import (
    TargetStatus,
    GapPriority,
    ActionType,
    ActionStatus,
    CareerTarget,
    CareerTargetSummary,
    CareerStrength,
    RequirementGap,
    CareerAction,
    ProgressSummary,
    CareerIntelligenceResponse,
)
from app.schemas.career_twin import CareerTwin
from app.schemas.evidence_vault import EvidenceVault
from app.schemas.candidate import CandidateProfile, CandidateSkill, CandidateProject, CandidateExperience
from app.schemas.job_fit import GapType, RequirementStatus
from app.schemas.document import GenericDocument, DocumentPage
from app.services.coach.job_fit.service import JobFitService
from app.db.repository import Repository
from sqlalchemy.orm import Session


def normalize_coverage_to_percentage(coverage: Optional[float]) -> float:
    """
    Ensures evidence coverage is converted to a percentage (0.0 to 100.0) exactly once.
    If coverage is provided as a fraction (e.g. 0.659), converts it to 65.9.
    If already a percentage (e.g. 65.9), preserves it.
    """
    if coverage is None:
        return 0.0
    val = float(coverage)
    if 0.0 < val <= 1.0:
        return round(val * 100, 1)
    return round(val, 1)


def format_coverage_percentage(coverage: Optional[float]) -> str:
    """
    Formats evidence coverage value to a percentage string (e.g. 65.9%).
    Ensures a backend value of 0.659 formats as 65.9%, NEVER 6590.0%.
    """
    pct = normalize_coverage_to_percentage(coverage)
    return f"{pct:.1f}%"


class CareerIntelligenceService:
    """
    Career Intelligence & Gap Planning Service (Phase 6).
    Reuses existing CareerTwin, EvidenceVault, and JobFitService.
    Answers: 'What should I work on next to become better aligned with target roles?'
    Strictly diagnostic: never predicts hiring probability or candidate ranking.
    """

    def __init__(self, job_fit_service: Optional[JobFitService] = None):
        self.job_fit_service = job_fit_service or JobFitService()

    def create_target(
        self,
        candidate_id: str,
        target_role: str,
        target_company: Optional[str] = None,
        source_job_fit_id: Optional[str] = None,
        job_description_text: Optional[str] = None,
        twin: Optional[CareerTwin] = None,
        vault: Optional[EvidenceVault] = None,
        db: Optional[Session] = None
    ) -> CareerTarget:
        """
        Creates and persists a new Career Target for the candidate.
        Can be initialized from existing Job Fit or raw Job Description text.
        """
        target_id = f"target_{uuid.uuid4().hex[:10]}"
        now = datetime.datetime.utcnow()

        # Parse requirements if JD text is provided
        extracted_reqs: List[Dict[str, Any]] = []
        raw_text = job_description_text or f"Role: {target_role}"
        if target_company:
            raw_text += f" at {target_company}"

        if job_description_text:
            page = DocumentPage(
                page_number=1,
                raw_text=job_description_text,
                normalized_text=job_description_text.lower()
            )
            doc = GenericDocument(
                document_id=f"doc_target_jd_{uuid.uuid4().hex[:8]}",
                filename="job_description.txt",
                page_count=1,
                pages=[page],
                raw_text=job_description_text,
                normalized_text=job_description_text.lower()
            )
            jd = self.job_fit_service.jd_analyzer.analyze(doc)
            if len(jd.requirements) == 0:
                lines = [l.strip() for l in job_description_text.split("\n") if l.strip()]
                for l in lines:
                    clean = re.sub(r'^[0-9\.\-\•\*\s]+', '', l).strip()
                    if clean and not clean.lower().startswith("requirements") and not clean.lower().startswith("role:"):
                        is_pref = "preferred" in l.lower()
                        extracted_reqs.append({
                            "requirement_id": f"req_{uuid.uuid4().hex[:8]}",
                            "requirement_text": clean,
                            "category": "technical_skill",
                            "priority": "PREFERRED" if is_pref else "REQUIRED",
                            "is_required": not is_pref
                        })
            else:
                for req in jd.requirements:
                    prio_val = req.priority.value if hasattr(req.priority, 'value') else str(req.priority)
                    extracted_reqs.append({
                        "requirement_id": getattr(req, "id", getattr(req, "requirement_id", f"req_{uuid.uuid4().hex[:8]}")),
                        "requirement_text": getattr(req, "requirement_text", getattr(req, "text", "")),
                        "category": req.category.value if hasattr(req.category, 'value') else str(req.category),
                        "priority": prio_val.upper(),
                        "is_required": prio_val.upper() == "REQUIRED"
                    })

        target = CareerTarget(
            target_id=target_id,
            candidate_id=candidate_id,
            target_role=target_role,
            target_company=target_company,
            source_job_fit_id=source_job_fit_id,
            status=TargetStatus.ACTIVE,
            raw_jd_text=job_description_text,
            requirements=extracted_reqs,
            created_at=now,
            updated_at=now
        )

        if db:
            repo = Repository(db)
            repo.save_career_target(
                target_id=target.target_id,
                candidate_id=target.candidate_id,
                target_role=target.target_role,
                target_company=target.target_company,
                source_job_fit_id=target.source_job_fit_id,
                status=target.status.value,
                raw_jd_text=target.raw_jd_text,
                requirements=target.requirements
            )

        return target

    def _calculate_priority(self, is_required: bool, gap_type: GapType, status: str) -> tuple[GapPriority, str]:
        """
        Deterministic prioritization logic.
        Considers REQUIRED vs PREFERRED, status, and gap type.
        Explains why the gap received this action priority.
        """
        if is_required:
            if gap_type == GapType.RESUME_VISIBILITY_GAP:
                return (
                    GapPriority.HIGH,
                    "High priority: Required skill with verified evidence in vault that can be immediately surfaced in your resume."
                )
            elif gap_type == GapType.EXPERIENCE_GAP:
                return (
                    GapPriority.HIGH,
                    "High priority: Core role requirement with no verifiable evidence in vault. Requires genuine project or hands-on practice."
                )
            else:
                return (
                    GapPriority.MEDIUM,
                    "Medium priority: Required requirement with insufficient documentation in vault to confidently evaluate."
                )
        else:
            if gap_type == GapType.RESUME_VISIBILITY_GAP:
                return (
                    GapPriority.MEDIUM,
                    "Medium priority: Preferred qualification with existing evidence that could provide an editorial advantage."
                )
            elif gap_type == GapType.EXPERIENCE_GAP:
                return (
                    GapPriority.LOW,
                    "Low priority: Nice-to-have preferred qualification. Secondary to core required competencies."
                )
            else:
                return (
                    GapPriority.LOW,
                    "Low priority: Preferred qualification with inconclusive documentation."
                )

    def analyze_target_intelligence(
        self,
        target: CareerTarget,
        twin: CareerTwin,
        vault: EvidenceVault,
        db: Optional[Session] = None,
        previous_coverage: Optional[float] = None
    ) -> CareerIntelligenceResponse:
        """
        Core Career Intelligence generation reusing deterministic JobFitService.
        Identifies verified strengths, visibility gaps, experience gaps, not-verifiable gaps,
        and generates safe action recommendations.
        """
        # Security validation: candidate ownership
        if target.candidate_id != twin.candidate_id:
            raise PermissionError(
                f"Security violation: Target owner '{target.candidate_id}' does not match candidate '{twin.candidate_id}'."
            )

        profile = copy.deepcopy(twin.candidate_profile) if twin.candidate_profile else None
        if not profile:
            profile = CandidateProfile(
                candidate_id=twin.candidate_id,
                name=twin.name or "Candidate",
                email=twin.email,
                skills=list(twin.skills),
                experience=copy.deepcopy(twin.experience),
                projects=copy.deepcopy(twin.projects),
                raw_text=twin.raw_text or ""
            )

        # Synchronize skills and project evidence from twin and vault into profile
        existing_skills = {s.name.lower() for s in profile.skill_details if s.name}
        for s in (twin.skills or []):
            if s and s.lower() not in existing_skills:
                profile.skill_details.append(CandidateSkill(name=s, raw_name=s))
                existing_skills.add(s.lower())
                if s not in profile.skills:
                    profile.skills.append(s)

        if vault and vault.items:
            for item in vault.items:
                if item.related_skill and item.related_skill.lower() not in existing_skills:
                    profile.skill_details.append(CandidateSkill(name=item.related_skill, raw_name=item.related_skill))
                    existing_skills.add(item.related_skill.lower())
                    if item.related_skill not in profile.skills:
                        profile.skills.append(item.related_skill)
                for tech in (item.related_technologies or []):
                    if tech and tech.lower() not in existing_skills:
                        profile.skill_details.append(CandidateSkill(name=tech, raw_name=tech))
                        existing_skills.add(tech.lower())
                        if tech not in profile.skills:
                            profile.skills.append(tech)
                if item.source_text:
                    if item.evidence_type == "PROJECT":
                        profile.projects.append(CandidateProject(name="Vault Project", description=item.source_text))
                    elif item.evidence_type == "EXPERIENCE":
                        profile.experience.append(CandidateExperience(role="Role", company="Company", description=item.source_text))
                    if profile.raw_text:
                        profile.raw_text += f"\n{item.source_text}"
                    else:
                        profile.raw_text = item.source_text

        job_text = target.raw_jd_text or f"Role: {target.target_role}\nRequirements:\n"
        if target.requirements and not target.raw_jd_text:
            for req in target.requirements:
                job_text += f"- {req.get('requirement_text', '')}\n"

        page = DocumentPage(
            page_number=1,
            raw_text=job_text,
            normalized_text=job_text.lower()
        )
        doc = GenericDocument(
            document_id=f"doc_target_{uuid.uuid4().hex[:8]}",
            filename="target_jd.txt",
            page_count=1,
            pages=[page],
            raw_text=job_text,
            normalized_text=job_text.lower()
        )
        jd = self.job_fit_service.jd_analyzer.analyze(doc)
        if len(jd.requirements) == 0 and target.requirements:
            for req in target.requirements:
                is_r = req.get("is_required", True) or str(req.get("priority", "")).upper() == "REQUIRED"
                jd.requirements.append(
                    JDRequirement(
                        id=req.get("requirement_id", f"req_{uuid.uuid4().hex[:8]}"),
                        requirement_text=req.get("requirement_text", ""),
                        category=RequirementCategory.SKILL,
                        priority=RequirementPriority.REQUIRED if is_r else RequirementPriority.PREFERRED
                    )
                )

        # Reuse existing deterministic Job Fit engine
        fit_response = self.job_fit_service.evaluate_fit(
            profile=profile,
            jd=jd,
            twin=twin,
            vault=vault,
            raw_jd_text=job_text
        )

        analysis = fit_response.job_fit_analysis
        raw_cov = fit_response.evidence_coverage or (analysis.fit_summary.evidence_coverage_score if analysis else fit_response.fit_score)
        evidence_coverage = normalize_coverage_to_percentage(raw_cov)
        
        # 1. Strengths (Evidence-grounded matches)
        strengths: List[CareerStrength] = []
        if analysis:
            for st in analysis.strengths:
                source_snippets = [ev.source_text for ev in st.supporting_evidence if ev.source_text]
                strengths.append(CareerStrength(
                    requirement_id=st.strength_id,
                    requirement_text=st.title,
                    category="technical_skill",
                    evidence_ids=list(st.evidence_ids),
                    explanation=st.explanation,
                    source_snippets=source_snippets
                ))
            # Also include any fully MATCHED requirements that have verified evidence citations
            for req in analysis.matched_requirements:
                if req.evidence and not any(s.requirement_id == req.requirement_id for s in strengths):
                    e_ids = [ev.evidence_id for ev in req.evidence if ev.evidence_id]
                    snippets = [ev.source_text for ev in req.evidence if ev.source_text]
                    strengths.append(CareerStrength(
                        requirement_id=req.requirement_id,
                        requirement_text=req.requirement_text,
                        category=req.category,
                        evidence_ids=e_ids,
                        explanation=req.explanation,
                        source_snippets=snippets
                    ))

        # 2. Gaps classification (Visibility vs Experience vs Not Verifiable)
        visibility_gaps: List[RequirementGap] = []
        experience_gaps: List[RequirementGap] = []
        not_verifiable_gaps: List[RequirementGap] = []

        if analysis:
            for gap in analysis.evidence_gaps:
                req_obj = next((r for r in analysis.requirements if r.requirement_id == gap.requirement_id), None)
                target_req = next(
                    (tr for tr in (target.requirements or []) if tr.get("requirement_id") == gap.requirement_id or tr.get("requirement_text", "").strip().lower() == gap.requirement_text.strip().lower()),
                    None
                )
                if target_req and "is_required" in target_req:
                    is_req = bool(target_req["is_required"])
                elif target_req and "priority" in target_req:
                    is_req = str(target_req["priority"]).upper() == "REQUIRED"
                elif req_obj:
                    is_req = req_obj.is_required
                else:
                    is_req = True
                cat = req_obj.category if req_obj else "technical_skill"
                cur_status = req_obj.status.value if req_obj else "MISSING"

                prio, rationale = self._calculate_priority(is_req, gap.gap_type, cur_status)
                ev_ids = [ev.evidence_id for ev in gap.existing_related_evidence if ev.evidence_id]

                if gap.gap_type == GapType.RESUME_VISIBILITY_GAP:
                    rec_actions = [
                        "Improve resume wording to highlight verified experience from your Evidence Vault.",
                        "Surface verified accomplishments using the Evidence-Locked Resume Coach."
                    ]
                    visibility_gaps.append(RequirementGap(
                        gap_id=gap.gap_id,
                        candidate_id=twin.candidate_id,
                        target_id=target.target_id,
                        requirement_id=gap.requirement_id,
                        requirement_text=gap.requirement_text,
                        category=cat,
                        priority=prio,
                        priority_rationale=rationale,
                        current_status=cur_status,
                        gap_type=GapType.RESUME_VISIBILITY_GAP,
                        evidence_ids=ev_ids,
                        explanation=gap.explanation,
                        recommended_actions=rec_actions,
                        can_rewrite_resume=True
                    ))
                elif gap.gap_type == GapType.EXPERIENCE_GAP:
                    rec_actions = [
                        "Build a portfolio project demonstrating hands-on proficiency with this skill.",
                        "Gain hands-on experience before adding to resume.",
                        "Document genuine experience when available in Evidence Vault."
                    ]
                    experience_gaps.append(RequirementGap(
                        gap_id=gap.gap_id,
                        candidate_id=twin.candidate_id,
                        target_id=target.target_id,
                        requirement_id=gap.requirement_id,
                        requirement_text=gap.requirement_text,
                        category=cat,
                        priority=prio,
                        priority_rationale=rationale,
                        current_status=cur_status,
                        gap_type=GapType.EXPERIENCE_GAP,
                        evidence_ids=[],
                        explanation=gap.explanation,
                        recommended_actions=rec_actions,
                        can_rewrite_resume=False  # MUST NEVER BE REWRITTEN
                    ))
                elif gap.gap_type == GapType.NOT_VERIFIABLE:
                    rec_actions = [
                        "Add supporting documentation or project artifacts to your Evidence Vault.",
                        "Review relevant projects to substantiate this requirement."
                    ]
                    not_verifiable_gaps.append(RequirementGap(
                        gap_id=gap.gap_id,
                        candidate_id=twin.candidate_id,
                        target_id=target.target_id,
                        requirement_id=gap.requirement_id,
                        requirement_text=gap.requirement_text,
                        category=cat,
                        priority=prio,
                        priority_rationale=rationale,
                        current_status=cur_status,
                        gap_type=GapType.NOT_VERIFIABLE,
                        evidence_ids=ev_ids,
                        explanation=gap.explanation,
                        recommended_actions=rec_actions,
                        can_rewrite_resume=False
                    ))

        # 3. Recommended Actions (Preserving historical DB actions)
        historical_actions: List[CareerAction] = []
        if db:
            repo = Repository(db)
            db_records = repo.get_career_actions_for_candidate(twin.candidate_id, target_id=target.target_id)
            for rec in db_records:
                historical_actions.append(CareerAction(
                    action_id=rec.action_id,
                    candidate_id=rec.candidate_id,
                    target_id=rec.target_id,
                    requirement_id=rec.requirement_id,
                    action_type=ActionType(rec.action_type),
                    title=rec.title,
                    description=rec.description,
                    rationale=rec.rationale,
                    priority=GapPriority(rec.priority),
                    status=ActionStatus(rec.status),
                    created_at=rec.created_at,
                    completed_at=rec.completed_at
                ))

        recommended_actions: List[CareerAction] = list(historical_actions)
        existing_req_ids = {a.requirement_id for a in historical_actions}

        # Generate fresh action items for new gaps
        for v_gap in visibility_gaps:
            if v_gap.requirement_id not in existing_req_ids:
                action = CareerAction(
                    action_id=f"act_{uuid.uuid4().hex[:10]}",
                    candidate_id=twin.candidate_id,
                    target_id=target.target_id,
                    requirement_id=v_gap.requirement_id,
                    action_type=ActionType.RESUME_IMPROVEMENT,
                    title=f"Improve resume wording for '{v_gap.requirement_text}'",
                    description="Highlight existing verified evidence from your Career Twin in your resume bullet points.",
                    rationale=v_gap.priority_rationale,
                    priority=v_gap.priority,
                    status=ActionStatus.TODO
                )
                recommended_actions.append(action)
                if db:
                    repo = Repository(db)
                    repo.save_career_action(
                        action_id=action.action_id,
                        candidate_id=action.candidate_id,
                        target_id=action.target_id,
                        requirement_id=action.requirement_id,
                        action_type=action.action_type.value,
                        title=action.title,
                        description=action.description,
                        rationale=action.rationale,
                        priority=action.priority.value,
                        status=action.status.value
                    )
                existing_req_ids.add(v_gap.requirement_id)

        for e_gap in experience_gaps:
            if e_gap.requirement_id not in existing_req_ids:
                action = CareerAction(
                    action_id=f"act_{uuid.uuid4().hex[:10]}",
                    candidate_id=twin.candidate_id,
                    target_id=target.target_id,
                    requirement_id=e_gap.requirement_id,
                    action_type=ActionType.BUILD_PROJECT,
                    title=f"Build project demonstrating '{e_gap.requirement_text}'",
                    description=f"Create a hands-on technical project that implements {e_gap.requirement_text} to establish verified evidence.",
                    rationale=e_gap.priority_rationale,
                    priority=e_gap.priority,
                    status=ActionStatus.TODO
                )
                recommended_actions.append(action)
                if db:
                    repo = Repository(db)
                    repo.save_career_action(
                        action_id=action.action_id,
                        candidate_id=action.candidate_id,
                        target_id=action.target_id,
                        requirement_id=action.requirement_id,
                        action_type=action.action_type.value,
                        title=action.title,
                        description=action.description,
                        rationale=action.rationale,
                        priority=action.priority.value,
                        status=action.status.value
                    )
                existing_req_ids.add(e_gap.requirement_id)

        for nv_gap in not_verifiable_gaps:
            if nv_gap.requirement_id not in existing_req_ids:
                action = CareerAction(
                    action_id=f"act_{uuid.uuid4().hex[:10]}",
                    candidate_id=twin.candidate_id,
                    target_id=target.target_id,
                    requirement_id=nv_gap.requirement_id,
                    action_type=ActionType.DOCUMENT_EVIDENCE,
                    title=f"Document evidence for '{nv_gap.requirement_text}'",
                    description="Upload supporting documentation or structured examples of your work to substantiate this requirement.",
                    rationale=nv_gap.priority_rationale,
                    priority=nv_gap.priority,
                    status=ActionStatus.TODO
                )
                recommended_actions.append(action)
                if db:
                    repo = Repository(db)
                    repo.save_career_action(
                        action_id=action.action_id,
                        candidate_id=action.candidate_id,
                        target_id=action.target_id,
                        requirement_id=action.requirement_id,
                        action_type=action.action_type.value,
                        title=action.title,
                        description=action.description,
                        rationale=action.rationale,
                        priority=action.priority.value,
                        status=action.status.value
                    )
                existing_req_ids.add(nv_gap.requirement_id)

        # 4. Progress Summary & Comparison
        prev_cov = normalize_coverage_to_percentage(previous_coverage) if previous_coverage is not None else None
        delta = round(evidence_coverage - prev_cov, 1) if prev_cov is not None else None

        improved_reqs = []
        unchanged_reqs = []
        if analysis:
            for req in analysis.requirements:
                if req.status in {RequirementStatus.MATCHED, RequirementStatus.PARTIAL} and req.evidence:
                    improved_reqs.append(req.requirement_text)
                else:
                    unchanged_reqs.append(req.requirement_text)

        matched_count = len(analysis.matched_requirements) if analysis else 0
        partial_count = len(analysis.partial_requirements) if analysis else 0
        missing_count = len(analysis.missing_requirements) if analysis else 0
        not_verifiable_count = len(not_verifiable_gaps)
        total_reqs = len(analysis.requirements) if analysis else 0

        cov_str = f"{evidence_coverage:.1f}%"
        delta_str = f" ({'+' if (delta or 0) >= 0 else ''}{delta:.1f}% change)" if delta is not None else ""
        narrative = (
            f"Target role '{target.target_role}' evidence coverage: {cov_str}{delta_str}. "
            f"{matched_count} requirement(s) verified by evidence in vault, "
            f"{len(visibility_gaps)} visibility gap(s) ready for resume improvement, and "
            f"{len(experience_gaps)} genuine experience gap(s) requiring hands-on project work. "
            "Note: This is a diagnostic representation of resume/evidence alignment; it does not predict hiring probability or recruiter behavior."
        )

        progress = ProgressSummary(
            total_requirements=total_reqs,
            matched=matched_count,
            partial=partial_count,
            missing=missing_count,
            not_verifiable=not_verifiable_count,
            evidence_coverage=evidence_coverage,
            visibility_gaps=len(visibility_gaps),
            experience_gaps=len(experience_gaps),
            previous_evidence_coverage=prev_cov,
            coverage_delta=delta,
            improved_requirements=improved_reqs,
            unchanged_requirements=unchanged_reqs,
            narrative=narrative
        )

        return CareerIntelligenceResponse(
            target_id=target.target_id,
            candidate_id=target.candidate_id,
            target_role=target.target_role,
            target_company=target.target_company,
            status=target.status,
            strengths=strengths,
            visibility_gaps=visibility_gaps,
            experience_gaps=experience_gaps,
            not_verifiable_gaps=not_verifiable_gaps,
            evidence_coverage=evidence_coverage,
            requirement_summary={
                "total": total_reqs,
                "matched": matched_count,
                "partial": partial_count,
                "missing": missing_count,
                "not_verifiable": not_verifiable_count,
                "visibility_gaps": len(visibility_gaps),
                "experience_gaps": len(experience_gaps)
            },
            recommended_next_actions=recommended_actions,
            progress_summary=progress
        )

    def refresh_target_intelligence(
        self,
        target: CareerTarget,
        twin: CareerTwin,
        vault: EvidenceVault,
        db: Optional[Session] = None,
        previous_coverage: Optional[float] = None
    ) -> CareerIntelligenceResponse:
        """
        Re-evaluates Job Fit with current Career Twin & Evidence Vault facts.
        Preserves all historical completed actions.
        """
        return self.analyze_target_intelligence(
            target=target,
            twin=twin,
            vault=vault,
            db=db,
            previous_coverage=previous_coverage
        )

    def complete_action(
        self,
        action_id: str,
        candidate_id: str,
        db: Session
    ) -> CareerAction:
        """
        Marks an action as completed.
        CRITICAL SAFETY GUARANTEE:
        Completing an action DOES NOT automatically grant skills or modify the Evidence Vault.
        Only genuine new verified evidence entering through the evidence ingestion workflow
        can update the Evidence Vault and Job Fit evaluation.
        """
        repo = Repository(db)
        record = repo.get_career_action(action_id)
        if not record:
            raise ValueError(f"Action '{action_id}' not found.")
        if record.candidate_id != candidate_id:
            raise PermissionError(
                f"Security violation: Action owner '{record.candidate_id}' does not match caller '{candidate_id}'."
            )

        now = datetime.datetime.utcnow()
        updated = repo.update_career_action_status(action_id, status=ActionStatus.COMPLETED.value, completed_at=now)
        return CareerAction(
            action_id=updated.action_id,
            candidate_id=updated.candidate_id,
            target_id=updated.target_id,
            requirement_id=updated.requirement_id,
            action_type=ActionType(updated.action_type),
            title=updated.title,
            description=updated.description,
            rationale=updated.rationale,
            priority=GapPriority(updated.priority),
            status=ActionStatus(updated.status),
            created_at=updated.created_at,
            completed_at=updated.completed_at
        )

    def dismiss_action(
        self,
        action_id: str,
        candidate_id: str,
        db: Session
    ) -> CareerAction:
        """
        Dismisses an action from the active plan.
        """
        repo = Repository(db)
        record = repo.get_career_action(action_id)
        if not record:
            raise ValueError(f"Action '{action_id}' not found.")
        if record.candidate_id != candidate_id:
            raise PermissionError(
                f"Security violation: Action owner '{record.candidate_id}' does not match caller '{candidate_id}'."
            )

        updated = repo.update_career_action_status(action_id, status=ActionStatus.DISMISSED.value)
        return CareerAction(
            action_id=updated.action_id,
            candidate_id=updated.candidate_id,
            target_id=updated.target_id,
            requirement_id=updated.requirement_id,
            action_type=ActionType(updated.action_type),
            title=updated.title,
            description=updated.description,
            rationale=updated.rationale,
            priority=GapPriority(updated.priority),
            status=ActionStatus(updated.status),
            created_at=updated.created_at,
            completed_at=updated.completed_at
        )

    def create_action(
        self,
        candidate_id: str,
        target_id: str,
        requirement_id: Optional[str] = None,
        action_type: ActionType = ActionType.LEARN_SKILL,
        title: str = "",
        description: str = "",
        rationale: str = "",
        priority: GapPriority = GapPriority.MEDIUM,
        db: Optional[Session] = None
    ) -> CareerAction:
        """
        Creates a new candidate-specific action plan item.
        """
        action_id = f"act_{uuid.uuid4().hex[:10]}"
        now = datetime.datetime.now()
        act = CareerAction(
            action_id=action_id,
            candidate_id=candidate_id,
            target_id=target_id,
            requirement_id=requirement_id,
            action_type=action_type,
            title=title,
            description=description,
            rationale=rationale,
            priority=priority,
            status=ActionStatus.TODO,
            created_at=now
        )
        if db:
            repo = Repository(db)
            repo.save_career_action(
                action_id=act.action_id,
                candidate_id=act.candidate_id,
                target_id=act.target_id,
                requirement_id=act.requirement_id,
                action_type=act.action_type.value,
                title=act.title,
                description=act.description,
                rationale=act.rationale,
                priority=act.priority.value,
                status=act.status.value
            )
        return act

    def get_actions_for_candidate(
        self,
        candidate_id: str,
        target_id: Optional[str] = None,
        db: Optional[Session] = None
    ) -> List[CareerAction]:
        """
        Retrieves all action items for a candidate.
        """
        if not db:
            return []
        repo = Repository(db)
        records = repo.get_career_actions_for_candidate(candidate_id, target_id)
        res = []
        for r in records:
            res.append(CareerAction(
                action_id=r.action_id,
                candidate_id=r.candidate_id,
                target_id=r.target_id,
                requirement_id=r.requirement_id,
                action_type=ActionType(r.action_type),
                title=r.title,
                description=r.description or "",
                rationale=r.rationale or "",
                priority=GapPriority(r.priority) if r.priority else GapPriority.MEDIUM,
                status=ActionStatus(r.status),
                created_at=r.created_at,
                completed_at=r.completed_at
            ))
        return res

