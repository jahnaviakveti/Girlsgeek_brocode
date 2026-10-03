import uuid
import json
import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session

from app.schemas.career_twin import CareerTwin
from app.schemas.evidence_vault import EvidenceVault, VaultEvidenceItem
from app.schemas.job_fit import GapType, RequirementStatus
from app.schemas.career_intelligence import CareerTarget
from app.schemas.interview_readiness import (
    InterviewTarget,
    InterviewTargetStatus,
    InterviewRequirementMapItem,
    PreparationStatus,
    InterviewQuestion,
    ProjectStory,
    AnswerValidationResult,
    InterviewSession,
    InterviewSessionItem,
    InterviewReadinessResponse,
)
from app.db.repository import Repository
from app.services.coach.career_intelligence.service import CareerIntelligenceService
from app.services.coach.interview.question_service import InterviewQuestionService
from app.services.coach.interview.answer_coach_service import InterviewAnswerCoachService


class InterviewReadinessService:
    """
    Core orchestration service for Interview & Application Readiness (Phase 7).
    Reuses CareerTwin, EvidenceVault, JobFit, CareerIntelligence, and EvidenceValidationService.
    Answers:
    1. 'What parts of my experience can I confidently discuss?'
    2. 'Which job requirements do I have evidence for?'
    3. 'Which areas require preparation?'
    4. 'What interview topics are likely to arise from this specific role?'
    """

    def __init__(
        self,
        career_intelligence_service: Optional[CareerIntelligenceService] = None,
        question_service: Optional[InterviewQuestionService] = None,
        answer_coach_service: Optional[InterviewAnswerCoachService] = None,
    ):
        self.career_intelligence_service = career_intelligence_service or CareerIntelligenceService()
        self.question_service = question_service or InterviewQuestionService()
        self.answer_coach_service = answer_coach_service or InterviewAnswerCoachService()

    def create_interview_target(
        self,
        candidate_id: str,
        target_role: str,
        target_id: Optional[str] = None,
        company: Optional[str] = None,
        job_description_text: Optional[str] = None,
        db: Optional[Session] = None
    ) -> InterviewTarget:
        """
        Creates a persistent Interview Target linked to a candidate and optional career target.
        """
        target_id_val = target_id
        if not target_id_val:
            # If no target_id provided, create an underlying CareerTarget so requirements are parsed
            c_target = self.career_intelligence_service.create_target(
                candidate_id=candidate_id,
                target_role=target_role,
                target_company=company,
                job_description_text=job_description_text or f"Role: {target_role}",
                db=db
            )
            target_id_val = c_target.target_id

        interview_target_id = f"itarget_{uuid.uuid4().hex[:10]}"
        now = datetime.datetime.utcnow()

        target = InterviewTarget(
            interview_target_id=interview_target_id,
            candidate_id=candidate_id,
            target_id=target_id_val,
            target_role=target_role,
            company=company,
            job_fit_id=None,
            status=InterviewTargetStatus.ACTIVE,
            created_at=now,
            updated_at=now
        )

        if db:
            repo = Repository(db)
            repo.save_interview_target(
                interview_target_id=target.interview_target_id,
                candidate_id=target.candidate_id,
                target_role=target.target_role,
                target_id=target.target_id,
                company=target.company,
                job_fit_id=target.job_fit_id,
                status=target.status.value
            )

        return target

    def get_interview_target(self, interview_target_id: str, db: Optional[Session] = None) -> Optional[InterviewTarget]:
        if not db:
            return None
        repo = Repository(db)
        rec = repo.get_interview_target(interview_target_id)
        if not rec:
            return None
        return InterviewTarget(
            interview_target_id=rec.interview_target_id,
            candidate_id=rec.candidate_id,
            target_id=rec.target_id,
            target_role=rec.target_role,
            company=rec.company,
            job_fit_id=rec.job_fit_id,
            status=InterviewTargetStatus(rec.status),
            created_at=rec.created_at,
            updated_at=rec.updated_at
        )

    def get_interview_targets_for_candidate(self, candidate_id: str, db: Optional[Session] = None) -> List[InterviewTarget]:
        if not db:
            return []
        repo = Repository(db)
        records = repo.get_interview_targets_for_candidate(candidate_id)
        return [
            InterviewTarget(
                interview_target_id=r.interview_target_id,
                candidate_id=r.candidate_id,
                target_id=r.target_id,
                target_role=r.target_role,
                company=r.company,
                job_fit_id=r.job_fit_id,
                status=InterviewTargetStatus(r.status),
                created_at=r.created_at,
                updated_at=r.updated_at
            )
            for r in records
        ]

    def generate_interview_readiness(
        self,
        interview_target: InterviewTarget,
        twin: CareerTwin,
        vault: EvidenceVault,
        db: Optional[Session] = None
    ) -> InterviewReadinessResponse:
        """
        Generates the comprehensive Interview Readiness diagnostic response.
        Reuses deterministic Career Intelligence and Job Fit analysis without re-parsing resume.
        """
        # Security validation: candidate ownership
        if interview_target.candidate_id != twin.candidate_id:
            raise PermissionError(
                f"Security violation: Target owner '{interview_target.candidate_id}' does not match candidate '{twin.candidate_id}'."
            )

        # 1. Load or run underlying Career Target Intelligence
        c_target = None
        if db and interview_target.target_id:
            repo = Repository(db)
            c_rec = repo.get_career_target(interview_target.target_id)
            if c_rec:
                reqs = json.loads(c_rec.requirements_json) if c_rec.requirements_json else []
                c_target = CareerTarget(
                    target_id=c_rec.target_id,
                    candidate_id=c_rec.candidate_id,
                    target_role=c_rec.target_role,
                    target_company=c_rec.target_company,
                    source_job_fit_id=c_rec.source_job_fit_id,
                    status=c_rec.status,
                    raw_jd_text=c_rec.raw_jd_text,
                    requirements=reqs,
                    created_at=c_rec.created_at,
                    updated_at=c_rec.updated_at
                )

        if not c_target:
            c_target = self.career_intelligence_service.create_target(
                candidate_id=twin.candidate_id,
                target_role=interview_target.target_role,
                target_company=interview_target.company,
                job_description_text=f"Role: {interview_target.target_role}",
                db=db
            )

        ci_response = self.career_intelligence_service.analyze_target_intelligence(
            target=c_target,
            twin=twin,
            vault=vault,
            db=db
        )

        # 2. Build Interview Requirement Map (READY, REVIEW, PREPARE, NOT_VERIFIABLE)
        requirements_map: List[InterviewRequirementMapItem] = []
        strength_req_ids = {s.requirement_id for s in ci_response.strengths}
        vis_gap_ids = {g.requirement_id: g for g in ci_response.visibility_gaps}
        exp_gap_ids = {g.requirement_id: g for g in ci_response.experience_gaps}
        nv_gap_ids = {g.requirement_id: g for g in ci_response.not_verifiable_gaps}

        # Collect all requirements from target
        all_reqs = c_target.requirements or []
        if not all_reqs and ci_response.strengths:
            for s in ci_response.strengths:
                all_reqs.append({
                    "requirement_id": s.requirement_id,
                    "requirement_text": s.requirement_text,
                    "priority": "REQUIRED",
                    "is_required": True
                })

        for req in all_reqs:
            rid = req.get("requirement_id", "")
            rtext = req.get("requirement_text", "")
            prio = req.get("priority", "REQUIRED")

            if rid in strength_req_ids:
                s_item = next((s for s in ci_response.strengths if s.requirement_id == rid), None)
                eids = s_item.evidence_ids if s_item else []
                requirements_map.append(InterviewRequirementMapItem(
                    requirement_id=rid,
                    requirement_text=rtext,
                    priority=prio,
                    job_fit_status="MATCHED",
                    gap_type=None,
                    evidence_ids=eids,
                    preparation_status=PreparationStatus.READY,
                    rationale="Verified evidence exists in your Evidence Vault. You can speak to this from concrete documented work."
                ))
            elif rid in vis_gap_ids:
                gap = vis_gap_ids[rid]
                requirements_map.append(InterviewRequirementMapItem(
                    requirement_id=rid,
                    requirement_text=rtext,
                    priority=prio,
                    job_fit_status="PARTIAL",
                    gap_type=GapType.RESUME_VISIBILITY_GAP.value,
                    evidence_ids=gap.evidence_ids,
                    preparation_status=PreparationStatus.REVIEW,
                    rationale="Evidence exists, but you should review your project specifics to articulate your accomplishments clearly."
                ))
            elif rid in exp_gap_ids:
                gap = exp_gap_ids[rid]
                requirements_map.append(InterviewRequirementMapItem(
                    requirement_id=rid,
                    requirement_text=rtext,
                    priority=prio,
                    job_fit_status="MISSING",
                    gap_type=GapType.EXPERIENCE_GAP.value,
                    evidence_ids=[],
                    preparation_status=PreparationStatus.PREPARE,
                    rationale="Genuine knowledge/experience gap. Prepare to explain your current knowledge honestly and demonstrate ramp-up agility."
                ))
            elif rid in nv_gap_ids:
                gap = nv_gap_ids[rid]
                requirements_map.append(InterviewRequirementMapItem(
                    requirement_id=rid,
                    requirement_text=rtext,
                    priority=prio,
                    job_fit_status="NOT_VERIFIABLE",
                    gap_type=GapType.NOT_VERIFIABLE.value,
                    evidence_ids=gap.evidence_ids,
                    preparation_status=PreparationStatus.NOT_VERIFIABLE,
                    rationale="Documentation is inconclusive. Review existing projects or gather supporting materials before interview."
                ))
            else:
                # Default check against vault items using claim scope audit
                from app.services.coach.evidence.claim_scope import evaluate_claim_scope
                candidate_items = [it for it in vault.items if rtext.lower() in it.source_text.lower() or (it.related_skill and it.related_skill.lower() in rtext.lower())]
                ev_texts = [it.source_text for it in candidate_items]
                scope_res = evaluate_claim_scope(ev_texts, rtext)

                if candidate_items and scope_res.scope_satisfied and not (scope_res.demands_higher_scope and not scope_res.scope_satisfied):
                    requirements_map.append(InterviewRequirementMapItem(
                        requirement_id=rid,
                        requirement_text=rtext,
                        priority=prio,
                        job_fit_status="MATCHED",
                        gap_type=None,
                        evidence_ids=[it.evidence_id for it in candidate_items],
                        preparation_status=PreparationStatus.READY,
                        rationale="Evidence exists in your Evidence Vault."
                    ))
                else:
                    requirements_map.append(InterviewRequirementMapItem(
                        requirement_id=rid,
                        requirement_text=rtext,
                        priority=prio,
                        job_fit_status="MISSING",
                        gap_type=GapType.EXPERIENCE_GAP.value,
                        evidence_ids=[],
                        preparation_status=PreparationStatus.PREPARE,
                        rationale="Genuine knowledge/experience gap. Prepare to explain your current knowledge honestly and demonstrate ramp-up agility."
                    ))

        # 3. Generate Project Stories from authentic candidate projects
        import re
        project_stories: List[ProjectStory] = []
        for proj in (twin.projects or []):
            p_name = proj.name or "Engineering Project"
            p_desc = proj.description or ""
            # Link evidence by name, terms, or tech
            p_terms = set(re.findall(r'\w+', p_name.lower())) - {"project", "engine", "system", "app", "application"}
            proj_techs_lower = [t.lower() for t in (proj.technologies or [])]
            ev_items = [
                it for it in vault.items
                if (it.related_project and any(term in it.related_project.lower() for term in p_terms))
                or any(term in it.source_text.lower() for term in p_terms)
                or (it.related_skill and it.related_skill.lower() in proj_techs_lower)
                or any(t.lower() in proj_techs_lower for t in (it.related_technologies or []))
            ]
            ev_ids = [it.evidence_id for it in ev_items]
            techs = list(proj.technologies) if proj.technologies else []
            for it in ev_items:
                if it.related_skill and it.related_skill not in techs:
                    techs.append(it.related_skill)
                for t in (it.related_technologies or []):
                    if t not in techs:
                        techs.append(t)

            # Documented outcomes
            outcomes = [it.source_text for it in ev_items if any(k in it.source_text.lower() for k in ["reduced", "increased", "%", "improved", "optimized", "saved", "accelerated"])]

            # Check if project evidence explicitly documents production operations/cluster management
            has_production_scope = any(
                any(w in it.source_text.lower() for w in ["production", "prod cluster", "cluster management", "managed cluster", "eks", "gke"])
                for it in ev_items
            )

            discussion_areas = [
                f"Architecture and technical choices ({', '.join(techs[:3]) if techs else 'core stack'})",
                "Technical trade-offs and implementation challenges"
            ]
            if has_production_scope:
                discussion_areas.append("Operational reliability and production cluster management")
            else:
                discussion_areas.append(f"Practical hands-on usage and component delivery ({', '.join(techs[:2]) if techs else 'core stack'})")

            star_prompts = {
                "situation": f"What was the business or technical objective behind {p_name}?",
                "task": f"What components were you personally responsible for delivering?",
                "action": f"How did you design and implement the solution using {', '.join(techs[:2]) if techs else 'your stack'}?",
                "result": outcomes[0] if outcomes else "Result not currently supported by verified evidence. Be prepared to share observable feedback."
            }

            project_stories.append(ProjectStory(
                project_id=f"story_{uuid.uuid4().hex[:8]}",
                project_name=p_name,
                evidence_ids=ev_ids,
                technologies=techs,
                responsibilities=[p_desc] if p_desc else [f"Engineering lead for {p_name}"],
                documented_outcomes=outcomes if outcomes else ["No verified quantitative outcomes documented in Evidence Vault."],
                likely_discussion_areas=discussion_areas,
                star_preparation_prompts=star_prompts,
                star_preparation=star_prompts
            ))

        # 4. Generate Interview Questions
        questions = self.question_service.generate_questions_for_target(
            interview_target_id=interview_target.interview_target_id,
            target_role=interview_target.target_role,
            requirement_items=requirements_map,
            twin=twin,
            vault=vault
        )

        # 5. Calculate Diagnostic Counts & Metric
        ready_items = [r for r in requirements_map if r.preparation_status == PreparationStatus.READY]
        review_items = [r for r in requirements_map if r.preparation_status == PreparationStatus.REVIEW]
        prepare_items = [r for r in requirements_map if r.preparation_status == PreparationStatus.PREPARE]
        nv_items = [r for r in requirements_map if r.preparation_status == PreparationStatus.NOT_VERIFIABLE]

        ready_count = len(ready_items)
        review_count = len(review_items)
        prepare_count = len(prepare_items)
        not_verifiable_count = len(nv_items)
        total_reqs = len(requirements_map)

        prep_metric = f"Requirements reviewed: {ready_count + review_count} / {total_reqs}"

        summary_dict = {
            "total_requirements": total_reqs,
            "ready_count": ready_count,
            "review_count": review_count,
            "prepare_count": prepare_count,
            "not_verifiable_count": not_verifiable_count,
            "requirements_reviewed": f"{ready_count + review_count} / {total_reqs}",
        }

        # 6. Preparation Areas
        prep_areas: List[str] = []
        for r in requirements_map:
            if r.preparation_status == PreparationStatus.READY:
                prep_areas.append(f"Strength Discussion: {r.requirement_text}")
            elif r.preparation_status == PreparationStatus.REVIEW:
                prep_areas.append(f"Project Review: {r.requirement_text}")
            elif r.preparation_status == PreparationStatus.PREPARE:
                prep_areas.append(f"Knowledge Preparation: {r.requirement_text}")

        for ps in project_stories[:2]:
            prep_areas.append(f"Story Deep Dive: {ps.project_name}")

        return InterviewReadinessResponse(
            interview_target_id=interview_target.interview_target_id,
            candidate_id=twin.candidate_id,
            target_id=interview_target.target_id,
            target_role=interview_target.target_role,
            company=interview_target.company,
            total_requirements=total_reqs,
            ready_count=ready_count,
            review_count=review_count,
            prepare_count=prepare_count,
            not_verifiable_count=not_verifiable_count,
            preparation_progress_metric=prep_metric,
            requirements_map=requirements_map,
            requirement_map=requirements_map,
            ready_to_discuss=ready_items,
            areas_to_review=review_items,
            areas_to_prepare=prepare_items,
            summary=summary_dict,
            interview_target=interview_target,
            preparation_areas=prep_areas,
            questions=questions,
            project_stories=project_stories,
            guardrail_notice=(
                "Preparation diagnostic only. Does not predict interview questions with certainty, "
                "predict hiring outcomes, or score candidate intelligence."
            )
        )

    def validate_answer(
        self,
        candidate_id: str,
        answer_text: str,
        vault: EvidenceVault,
        question_text: Optional[str] = None
    ) -> AnswerValidationResult:
        """
        Validates a candidate draft response against their Evidence Vault.
        """
        if vault.candidate_id != candidate_id:
            raise PermissionError(
                f"Security violation: Vault owner '{vault.candidate_id}' does not match candidate '{candidate_id}'."
            )
        return self.answer_coach_service.validate_candidate_answer(
            vault=vault,
            answer_text=answer_text,
            question_text=question_text
        )

    def create_mock_session(
        self,
        candidate_id: str,
        interview_target: InterviewTarget,
        questions: List[InterviewQuestion],
        db: Optional[Session] = None
    ) -> InterviewSession:
        """
        Initializes a practice interview session.
        """
        session_id = f"sess_{uuid.uuid4().hex[:10]}"
        now = datetime.datetime.utcnow()

        items = [
            InterviewSessionItem(
                question_id=q.question_id,
                question_text=q.question,
                requirement_id=q.requirement_id,
                evidence_ids=q.evidence_ids
            )
            for q in questions
        ]

        sess = InterviewSession(
            session_id=session_id,
            candidate_id=candidate_id,
            interview_target_id=interview_target.interview_target_id,
            target_role=interview_target.target_role,
            status="IN_PROGRESS",
            items=items,
            requirements_covered_count=0,
            total_target_requirements=len(questions),
            created_at=now,
            updated_at=now
        )

        if db:
            repo = Repository(db)
            repo.save_mock_interview_session(
                session_id=sess.session_id,
                candidate_id=sess.candidate_id,
                interview_target_id=sess.interview_target_id,
                target_role=sess.target_role,
                status=sess.status,
                session_data_list=[i.dict() for i in sess.items]
            )

        return sess

    def submit_session_answer(
        self,
        session_id: str,
        candidate_id: str,
        question_id: str,
        answer_text: str,
        vault: EvidenceVault,
        db: Optional[Session] = None
    ) -> InterviewSession:
        """
        Submits and validates an answer inside an ongoing mock session.
        """
        if vault.candidate_id != candidate_id:
            raise PermissionError("Security violation: Vault does not match candidate.")

        sess_record = None
        if db:
            repo = Repository(db)
            sess_record = repo.get_mock_interview_session(session_id)
            if not sess_record:
                raise ValueError(f"Session '{session_id}' not found.")
            if sess_record.candidate_id != candidate_id:
                raise PermissionError("Security violation: Session candidate mismatch.")

        # Validate answer
        validation_res = self.answer_coach_service.validate_candidate_answer(vault, answer_text)

        items_dict = sess_record.session_data if (sess_record and isinstance(sess_record.session_data, list)) else []
        if sess_record and isinstance(sess_record.session_data, str):
            import json
            items_dict = json.loads(sess_record.session_data)

        # Update matching question
        updated_items = []
        covered_reqs = set()
        for item in items_dict:
            if item.get("question_id") == question_id:
                item["candidate_answer"] = answer_text
                item["validation_result"] = validation_res.dict()
                item["answered_at"] = datetime.datetime.utcnow().isoformat()
            if item.get("candidate_answer"):
                rid = item.get("requirement_id")
                if rid:
                    covered_reqs.add(rid)
            updated_items.append(item)

        if db:
            repo = Repository(db)
            repo.update_mock_interview_session(session_id, updated_items)

        answers_submitted = sum(1 for it in updated_items if it.get("candidate_answer"))
        questions_completed = answers_submitted
        reqs_reviewed = len(covered_reqs)
        supported_cnt = sum(len(it.get("validation_result", {}).get("supported_claims", [])) for it in updated_items if it.get("validation_result"))
        unsupported_cnt = sum(len(it.get("validation_result", {}).get("unsupported_claims", [])) for it in updated_items if it.get("validation_result"))

        now = datetime.datetime.utcnow()
        return InterviewSession(
            session_id=session_id,
            candidate_id=candidate_id,
            interview_target_id=sess_record.interview_target_id if sess_record else "target",
            target_role=sess_record.target_role if sess_record else "Role",
            status="IN_PROGRESS",
            items=[InterviewSessionItem(**i) for i in updated_items],
            questions_completed_count=questions_completed,
            answers_submitted_count=answers_submitted,
            requirements_reviewed_count=reqs_reviewed,
            supported_claims_count=supported_cnt,
            unsupported_claims_count=unsupported_cnt,
            requirements_covered_count=len(covered_reqs),
            total_target_requirements=len(updated_items),
            created_at=sess_record.created_at if sess_record else now,
            updated_at=now
        )
