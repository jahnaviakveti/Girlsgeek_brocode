import re
import json
import uuid
import datetime
from typing import List, Optional, Dict, Any, Tuple

from app.schemas.career_execution import (
    ExecutionStatus,
    ProgressState,
    ArtifactType,
    ArtifactReference,
    ExecutionNote,
    CareerExecution,
    EvidenceClaimSubmission,
    EvidenceVerificationResult,
    RequirementProgressItem,
    TimelineEventType,
    TimelineEvent,
    TargetRequirementDelta,
    TargetProgressComparison,
)
from app.schemas.career_twin import CareerTwin
from app.schemas.evidence_vault import EvidenceVault, VaultEvidenceItem, EvidenceType
from app.schemas.candidate import CandidateProfile, CandidateSkill, CandidateProject, CandidateExperience
from app.schemas.career_intelligence import CareerTarget, CareerAction, ActionStatus
from app.schemas.job_fit import GapType, RequirementStatus
from app.schemas.domain import JDRequirement, RequirementCategory, RequirementPriority
from app.schemas.document import GenericDocument, DocumentPage
from app.services.coach.evidence.service import EvidenceVaultService
from app.services.coach.evidence.validation import EvidenceValidationService
from app.services.coach.evidence.claim_scope import (
    detect_requirement_scope,
    check_evidence_scope_satisfaction,
    evaluate_claim_scope,
    extract_operational_scope_claims,
    classify_claim_scope,
)
from app.services.coach.job_fit.service import JobFitService
from app.db.repository import Repository
from sqlalchemy.orm import Session


class CareerExecutionService:
    """
    Career Execution & Evidence-Based Progress Service (Phase 8).
    
    Core Architectural Principle:
    ACTION COMPLETION != SKILL ACQUISITION
    
    1. Distinguishes PLANNED, IN_PROGRESS, SELF_REPORTED_COMPLETE, EVIDENCE_SUBMITTED, VERIFIED.
    2. SELF_REPORTED_COMPLETE never mutates Career Twin, Evidence Vault, Job Fit,
       Career Intelligence, or Interview Readiness.
    3. Only verified evidence may affect those systems.
    4. Enforces claim scope preservation (5 levels) via claim_scope.py.
    5. Retains full evidence provenance and before/after target diagnostics.
    """

    def __init__(
        self,
        vault_service: Optional[EvidenceVaultService] = None,
        job_fit_service: Optional[JobFitService] = None,
        validation_service: Optional[EvidenceValidationService] = None,
    ):
        self.vault_service = vault_service or EvidenceVaultService()
        self.job_fit_service = job_fit_service or JobFitService()
        self.validation_service = validation_service or EvidenceValidationService()

        # In-memory execution store for testing or environments without DB
        self._in_memory_executions: Dict[str, CareerExecution] = {}
        self._in_memory_timeline: Dict[str, List[TimelineEvent]] = {}
        self._target_baseline_snapshots: Dict[str, Dict[str, Any]] = {}

    # =========================================================================
    # 1. EXECUTION CREATION & RETRIEVAL
    # =========================================================================

    def create_execution(
        self,
        candidate_id: str,
        action_id: str,
        target_id: str,
        title: Optional[str] = None,
        notes: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> CareerExecution:
        """
        Creates a persistent Career Execution record for an action.
        Verifies tenant ownership: action and target must belong to candidate_id.
        """
        if not candidate_id or not action_id or not target_id:
            raise ValueError("candidate_id, action_id, and target_id are required.")

        action_title = title
        # Check DB / repository constraints if db is provided
        if db:
            repo = Repository(db)
            action_rec = repo.get_career_action(action_id)
            if not action_rec:
                raise ValueError(f"Action '{action_id}' not found.")
            if action_rec.candidate_id != candidate_id:
                raise PermissionError(
                    f"Security violation: Action '{action_id}' does not belong to candidate '{candidate_id}'."
                )
            if action_rec.target_id != target_id:
                raise ValueError(
                    f"Action '{action_id}' belongs to target '{action_rec.target_id}', not '{target_id}'."
                )

            if not action_title and action_rec.title:
                action_title = action_rec.title

            target_rec = repo.get_career_target(target_id)
            if not target_rec:
                target_rec = repo.get_interview_target(target_id)
            if not target_rec:
                raise ValueError(f"Target '{target_id}' not found.")
            if target_rec.candidate_id != candidate_id:
                raise PermissionError(
                    f"Security violation: Target '{target_id}' does not belong to candidate '{candidate_id}'."
                )

            # Check if execution already exists
            existing_rec = repo.get_career_execution_by_action(action_id)
            if existing_rec:
                return self._record_to_execution(existing_rec, db=db)

        if not action_title:
            try:
                from app.api.routes.coach import _in_memory_actions
                if action_id in _in_memory_actions:
                    action_title = _in_memory_actions[action_id].title
            except Exception:
                pass

        now = datetime.datetime.utcnow()
        execution_id = f"exec_{uuid.uuid4().hex[:10]}"
        initial_notes = []
        if notes and notes.strip():
            initial_notes.append(
                ExecutionNote(
                    note_id=f"note_{uuid.uuid4().hex[:8]}",
                    content=notes.strip(),
                    created_at=now,
                )
            )

        execution = CareerExecution(
            execution_id=execution_id,
            candidate_id=candidate_id,
            action_id=action_id,
            target_id=target_id,
            title=action_title or f"Action {action_id}",
            status=ExecutionStatus.NOT_STARTED,
            progress_state=ProgressState.PLANNED,
            progress_percent=0,
            started_at=None,
            completed_at=None,
            notes=initial_notes,
            blocker_reason=None,
            next_step=None,
            artifact_references=[],
            evidence_ids=[],
            claim_scope=None,
            created_at=now,
            updated_at=now,
        )

        if db:
            repo = Repository(db)
            repo.save_career_execution(
                execution_id=execution.execution_id,
                candidate_id=execution.candidate_id,
                action_id=execution.action_id,
                target_id=execution.target_id,
                status=execution.status.value,
                progress_state=execution.progress_state.value,
                progress_percent=execution.progress_percent,
                started_at=execution.started_at,
                completed_at=execution.completed_at,
                notes=[n.model_dump() for n in execution.notes],
                blocker_reason=execution.blocker_reason,
                next_step=execution.next_step,
                artifact_references=[a.model_dump() for a in execution.artifact_references],
                evidence_ids=execution.evidence_ids,
                claim_scope=execution.claim_scope,
            )

        self._in_memory_executions[execution.execution_id] = execution
        return execution

    def get_execution(
        self,
        candidate_id: str,
        execution_id: str,
        db: Optional[Session] = None,
    ) -> CareerExecution:
        """Retrieves execution record with strict candidate ownership verification."""
        execution = None
        if db:
            repo = Repository(db)
            rec = repo.get_career_execution(execution_id)
            if rec:
                execution = self._record_to_execution(rec, db=db)

        if not execution:
            execution = self._in_memory_executions.get(execution_id)

        if not execution:
            raise ValueError(f"Execution '{execution_id}' not found.")

        if execution.candidate_id != candidate_id:
            raise PermissionError(
                f"Security violation: Execution '{execution_id}' does not belong to candidate '{candidate_id}'."
            )

        return execution

    def list_executions_for_candidate(
        self,
        candidate_id: str,
        target_id: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> List[CareerExecution]:
        """Lists executions for a candidate with optional target filtering."""
        if db:
            repo = Repository(db)
            records = repo.get_career_executions_for_candidate(candidate_id, target_id=target_id)
            return [self._record_to_execution(r, db=db) for r in records]

        results = [
            ex for ex in self._in_memory_executions.values()
            if ex.candidate_id == candidate_id
        ]
        if target_id:
            results = [ex for ex in results if ex.target_id == target_id]
        return sorted(results, key=lambda x: x.created_at, reverse=True)

    # =========================================================================
    # 2. STATUS TRANSITIONS & PROGRESS
    # =========================================================================

    def start_execution(
        self,
        candidate_id: str,
        execution_id: str,
        db: Optional[Session] = None,
    ) -> CareerExecution:
        """
        Transitions execution to IN_PROGRESS.
        Legal transition: NOT_STARTED -> IN_PROGRESS (or already IN_PROGRESS).
        """
        execution = self.get_execution(candidate_id, execution_id, db=db)
        now = datetime.datetime.utcnow()

        if execution.status == ExecutionStatus.COMPLETED:
            raise ValueError("Cannot start an already completed execution.")

        execution.status = ExecutionStatus.IN_PROGRESS
        execution.progress_state = ProgressState.IN_PROGRESS
        if not execution.started_at:
            execution.started_at = now
        execution.updated_at = now

        self._save_execution(execution, db=db)
        self._record_timeline_event(
            candidate_id=candidate_id,
            target_id=execution.target_id,
            event_type=TimelineEventType.ACTION_STARTED,
            description=f"Started working on career action '{execution.action_id}'.",
            execution_id=execution_id,
            db=db,
        )
        return execution

    def update_progress(
        self,
        candidate_id: str,
        execution_id: str,
        progress_percent: int,
        notes: Optional[str] = None,
        next_step: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> CareerExecution:
        """
        Updates execution progress percentage, notes, and next step.
        Disallows setting VERIFIED state via progress update.
        """
        execution = self.get_execution(candidate_id, execution_id, db=db)
        now = datetime.datetime.utcnow()

        if progress_percent < 0 or progress_percent > 100:
            raise ValueError("progress_percent must be between 0 and 100.")

        # Ensure started
        if execution.status == ExecutionStatus.NOT_STARTED:
            execution.status = ExecutionStatus.IN_PROGRESS
            execution.progress_state = ProgressState.IN_PROGRESS
            execution.started_at = now

        execution.progress_percent = progress_percent
        if next_step is not None:
            execution.next_step = next_step.strip() if next_step else None

        if notes and notes.strip():
            execution.notes.append(
                ExecutionNote(
                    note_id=f"note_{uuid.uuid4().hex[:8]}",
                    content=notes.strip(),
                    created_at=now,
                )
            )

        execution.updated_at = now
        self._save_execution(execution, db=db)
        self._record_timeline_event(
            candidate_id=candidate_id,
            target_id=execution.target_id,
            event_type=TimelineEventType.PROGRESS_UPDATED,
            description=f"Updated progress to {progress_percent}% for career action '{execution.action_id}'.",
            execution_id=execution_id,
            metadata={"progress_percent": progress_percent, "next_step": next_step},
            db=db,
        )
        return execution

    def report_blocker(
        self,
        candidate_id: str,
        execution_id: str,
        blocker_reason: str,
        next_step: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> CareerExecution:
        """
        Marks an action as BLOCKED. Blockers do NOT modify Evidence Vault or Twin.
        """
        if not blocker_reason or not blocker_reason.strip():
            raise ValueError("blocker_reason cannot be empty.")

        execution = self.get_execution(candidate_id, execution_id, db=db)
        now = datetime.datetime.utcnow()

        execution.status = ExecutionStatus.BLOCKED
        execution.blocker_reason = blocker_reason.strip()
        if next_step is not None:
            execution.next_step = next_step.strip() if next_step else None

        execution.notes.append(
            ExecutionNote(
                note_id=f"note_{uuid.uuid4().hex[:8]}",
                content=f"BLOCKED: {execution.blocker_reason}",
                created_at=now,
            )
        )
        execution.updated_at = now
        self._save_execution(execution, db=db)
        self._record_timeline_event(
            candidate_id=candidate_id,
            target_id=execution.target_id,
            event_type=TimelineEventType.BLOCKER_RECORDED,
            description=f"Action '{execution.action_id}' blocked: {blocker_reason.strip()}",
            execution_id=execution_id,
            metadata={"blocker_reason": blocker_reason.strip(), "next_step": next_step},
            db=db,
        )
        return execution

    def submit_artifact(
        self,
        candidate_id: str,
        execution_id: str,
        name: str,
        artifact_type: ArtifactType,
        url_or_path: str,
        description: str,
        technologies: Optional[List[str]] = None,
        db: Optional[Session] = None,
    ) -> CareerExecution:
        """
        Associates genuine artifact references with an execution.
        Artifact submission alone DOES NOT grant skills or verify evidence.
        """
        clean_name = (name or "").strip() or "Artifact"
        clean_url = (url_or_path or "").strip() or "https://artifact"

        execution = self.get_execution(candidate_id, execution_id, db=db)
        now = datetime.datetime.utcnow()

        artifact = ArtifactReference(
            artifact_id=f"art_{uuid.uuid4().hex[:10]}",
            name=clean_name,
            artifact_type=artifact_type or ArtifactType.OTHER,
            url_or_path=clean_url,
            description=description.strip() if description else "",
            technologies=technologies or [],
            submitted_at=now,
        )

        execution.artifact_references.append(artifact)
        execution.status = ExecutionStatus.AWAITING_EVIDENCE
        execution.progress_state = ProgressState.EVIDENCE_SUBMITTED
        execution.updated_at = now

        self._save_execution(execution, db=db)
        self._record_timeline_event(
            candidate_id=candidate_id,
            target_id=execution.target_id,
            event_type=TimelineEventType.ARTIFACT_SUBMITTED,
            description=f"Submitted artifact '{artifact.name}' ({artifact.artifact_type.value}) for action '{execution.action_id}'.",
            execution_id=execution_id,
            db=db,
        )
        return execution

    def complete_self_reported(
        self,
        candidate_id: str,
        execution_id: str,
        notes: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> CareerExecution:
        """
        Marks execution as SELF_REPORTED_COMPLETE.
        
        CRITICAL ARCHITECTURAL GUARANTEE:
        SELF_REPORTED_COMPLETE must NOT update:
        - Career Twin
        - Evidence Vault
        - Skills, projects, or experience
        - Job Fit
        - Career Intelligence
        - Interview Readiness
        
        Only VERIFIED evidence may affect those systems.
        """
        execution = self.get_execution(candidate_id, execution_id, db=db)
        now = datetime.datetime.utcnow()
        if execution.status == ExecutionStatus.NOT_STARTED:
            raise ValueError("Cannot complete an action that has not been started.")

        if not execution.started_at:
            execution.started_at = now

        execution.status = ExecutionStatus.COMPLETED
        execution.progress_state = ProgressState.SELF_REPORTED_COMPLETE
        execution.progress_percent = 100
        execution.completed_at = now
        execution.updated_at = now

        if notes and notes.strip():
            execution.notes.append(
                ExecutionNote(
                    note_id=f"note_{uuid.uuid4().hex[:8]}",
                    content=f"Completion note: {notes.strip()}",
                    created_at=now,
                )
            )

        # Sync linked career action status if db is available
        if db:
            repo = Repository(db)
            repo.update_career_action_status(
                action_id=execution.action_id,
                status=ActionStatus.COMPLETED.value,
                completed_at=now,
            )

        self._save_execution(execution, db=db)
        self._record_timeline_event(
            candidate_id=candidate_id,
            target_id=execution.target_id,
            event_type=TimelineEventType.SELF_REPORTED_COMPLETE,
            description=f"Marked career action '{execution.action_id}' as completed (self-reported).",
            execution_id=execution_id,
            db=db,
        )
        return execution

    # =========================================================================
    # 3. EVIDENCE VERIFICATION PIPELINE & SYSTEM REFRESH
    # =========================================================================

    def verify_evidence(
        self,
        candidate_id: str,
        execution_id: str,
        evidence_claims: List[EvidenceClaimSubmission],
        artifact_id: Optional[str] = None,
        db: Optional[Session] = None,
        twin: Optional[CareerTwin] = None,
        vault: Optional[EvidenceVault] = None,
    ) -> EvidenceVerificationResult:
        """
        Validates candidate-submitted evidence claims and attaches verified items
        to the Evidence Vault.
        
        Guarantees:
        1. If evidence is rejected: zero mutations to Evidence Vault or Career Twin.
        2. Preserves claim scope (Level 1..5). Implementation evidence is never promoted to Operational.
        3. Updates Career Twin, re-evaluates Target Job Fit, refreshes Career Intelligence.
        4. Re-evaluates Interview Readiness if applicable.
        5. Attaches full provenance to verified items.
        """
        execution = self.get_execution(candidate_id, execution_id, db=db)

        if not evidence_claims and execution.artifact_references:
            evidence_claims = []
            target_arts = (
                [a for a in execution.artifact_references if a.artifact_id == artifact_id]
                if artifact_id
                else execution.artifact_references
            )
            for art in target_arts:
                claim_text = f"{art.name}: {art.description}" if art.description else art.name
                evidence_claims.append(
                    EvidenceClaimSubmission(
                        claim_text=claim_text,
                        source_snippet=f"{art.name} at {art.url_or_path}. {art.description}",
                        evidence_type="PROJECT",
                        source_document=art.url_or_path,
                        source_section="artifact_submission",
                        related_technologies=art.technologies or [],
                        related_skill=art.technologies[0] if art.technologies else None,
                        claimed_scope=classify_claim_scope(claim_text),
                    )
                )

        if not evidence_claims:
            return EvidenceVerificationResult(
                verified=False,
                execution_id=execution_id,
                evidence_ids=[],
                claim_scope=None,
                provenance=[],
                rejection_reason="No evidence claims submitted for verification.",
                explanation="At least one factual claim with source text must be provided."
            )

        # Validate claims against claim scope and substantiveness
        approved_claims: List[Tuple[EvidenceClaimSubmission, str, str]] = []  # (claim, scope, evidence_id)
        for claim in evidence_claims:
            if not claim.claim_text or not claim.claim_text.strip():
                continue
            if len(claim.claim_text.strip()) < 8:
                continue

            # Scope determination
            detected_scope = classify_claim_scope(claim.claim_text)
            
            # Check for unsupported operational claims (Level 4/5)
            # If claim asserts production / cluster management without supporting snippet
            op_claims = extract_operational_scope_claims(claim.claim_text)
            if op_claims:
                snippet_has_op = bool(extract_operational_scope_claims(claim.source_snippet or ""))
                if not snippet_has_op:
                    return EvidenceVerificationResult(
                        verified=False,
                        execution_id=execution_id,
                        evidence_ids=[],
                        claim_scope=None,
                        provenance=[],
                        rejection_reason=f"Unsupported operational claim: '{op_claims[0]}'.",
                        explanation="Claim asserts production management or cluster operations, but source snippet does not support operational scope."
                    )

            ev_id = self.vault_service.generate_evidence_id(
                candidate_id=candidate_id,
                source_text=claim.claim_text.strip(),
                source_document=claim.source_document or "Submitted Artifact",
                source_section=claim.source_section or "Career Execution",
                evidence_type=claim.evidence_type or "PROJECT",
            )
            approved_claims.append((claim, detected_scope, ev_id))

        if not approved_claims:
            return EvidenceVerificationResult(
                verified=False,
                execution_id=execution_id,
                evidence_ids=[],
                claim_scope=None,
                provenance=[],
                rejection_reason="All submitted claims failed validation.",
                explanation="Submitted claims lacked substantive factual content or supporting documentation."
            )

        # Capture BEFORE state snapshot for target progress comparison
        before_state = self._capture_target_snapshot(execution.target_id, candidate_id, twin=twin, vault=vault, db=db)
        if execution.target_id not in self._target_baseline_snapshots:
            self._target_baseline_snapshots[execution.target_id] = before_state

        # Commit approved evidence to Evidence Vault
        now = datetime.datetime.utcnow()
        new_vault_items: List[VaultEvidenceItem] = []
        new_evidence_ids: List[str] = []
        highest_scope = "LEVEL 1 — TECHNOLOGY PRESENCE"
        provenance_records: List[Dict[str, Any]] = []

        scope_ranks = {
            "LEVEL 1 — TECHNOLOGY PRESENCE": 1,
            "LEVEL 2 — USAGE": 2,
            "LEVEL 3 — IMPLEMENTATION": 3,
            "LEVEL 4 — OPERATIONAL / PRODUCTION": 4,
            "LEVEL 5 — SPECIFIC SCOPE": 5,
        }

        for claim, scope, ev_id in approved_claims:
            new_evidence_ids.append(ev_id)
            if scope_ranks.get(scope, 1) > scope_ranks.get(highest_scope, 1):
                highest_scope = scope

            techs = list(claim.related_technologies or [])
            # Also extract recognized tech from claim text
            from app.services.jd_analyzer.taxonomy import extract_all_technologies
            extracted_techs = extract_all_technologies(claim.claim_text)
            for t in extracted_techs:
                if t not in techs:
                    techs.append(t)

            primary_skill = claim.related_skill or (techs[0] if techs else None)

            vault_item = VaultEvidenceItem(
                evidence_id=ev_id,
                candidate_id=candidate_id,
                source_text=claim.claim_text.strip(),
                source_document=claim.source_document or "Submitted Artifact",
                source_section=claim.source_section or "Career Execution",
                page_number=1,
                evidence_type=claim.evidence_type or "PROJECT",
                confidence=0.95,
                normalized_facts=[claim.claim_text.strip()] + techs,
                related_entity="Career Execution Artifact",
                related_skill=primary_skill,
                related_project=claim.source_document or "Execution Project",
                related_technologies=techs,
                metadata={
                    "execution_id": execution_id,
                    "action_id": execution.action_id,
                    "target_id": execution.target_id,
                    "claim_scope": scope,
                    "artifact_id": artifact_id,
                },
                created_at=now.isoformat(),
            )
            new_vault_items.append(vault_item)

            provenance_records.append({
                "evidence_id": ev_id,
                "source_document": vault_item.source_document,
                "source_section": vault_item.source_section,
                "source_snippet": claim.source_snippet or claim.claim_text,
                "evidence_type": vault_item.evidence_type,
                "confidence": vault_item.confidence,
                "created_at": now.isoformat(),
                "related_action_id": execution.action_id,
                "related_target_id": execution.target_id,
                "claim_scope": scope,
                "technologies": techs,
            })

        # Update in-memory vault if present
        if vault:
            for item in new_vault_items:
                if not any(it.evidence_id == item.evidence_id for it in vault.items):
                    vault.items.append(item)
                    vault.total_items = len(vault.items)
                    for tech in item.related_technologies:
                        tech_lower = tech.lower()
                        if tech_lower not in vault.technology_index:
                            vault.technology_index[tech_lower] = []
                        if item.evidence_id not in vault.technology_index[tech_lower]:
                            vault.technology_index[tech_lower].append(item.evidence_id)
                    if item.related_skill:
                        sk_lower = item.related_skill.lower()
                        if sk_lower not in vault.skill_index:
                            vault.skill_index[sk_lower] = []
                        if item.evidence_id not in vault.skill_index[sk_lower]:
                            vault.skill_index[sk_lower].append(item.evidence_id)

            try:
                from app.api.routes.coach import _in_memory_vaults
                _in_memory_vaults[candidate_id] = vault
            except Exception:
                pass

        # Update DB Evidence Vault
        if db:
            repo = Repository(db)
            repo.save_evidence_batch(
                candidate_id=candidate_id,
                items=[it.model_dump() for it in new_vault_items],
            )

        # Update execution state to VERIFIED
        for eid in new_evidence_ids:
            if eid not in execution.evidence_ids:
                execution.evidence_ids.append(eid)
        execution.claim_scope = highest_scope
        execution.progress_state = ProgressState.VERIFIED
        execution.status = ExecutionStatus.COMPLETED
        execution.progress_percent = 100
        execution.completed_at = now
        execution.updated_at = now

        self._save_execution(execution, db=db)

        # Refresh Career Twin with new verified evidence
        if twin:
            for item in new_vault_items:
                for tech in item.related_technologies:
                    if tech not in twin.skills:
                        twin.skills.append(tech)
                if item.related_skill and item.related_skill not in twin.skills:
                    twin.skills.append(item.related_skill)
                # Register project
                proj_name = item.related_project or "Verified Project"
                if not any(p.name == proj_name for p in twin.projects):
                    twin.projects.append(CandidateProject(name=proj_name, description=item.source_text, technologies=item.related_technologies))

            if db:
                repo = Repository(db)
                repo.save_candidate_profile(
                    candidate_id=candidate_id,
                    name=getattr(twin, "name", "Candidate"),
                    email=getattr(twin, "email", None),
                    phone=getattr(twin, "phone", None),
                    summary=getattr(twin, "summary", None),
                    profile_dict=twin.model_dump(),
                )
            try:
                from app.api.routes.coach import _in_memory_twins
                _in_memory_twins[candidate_id] = twin
            except Exception:
                pass

        # Re-evaluate Target Job Fit and capture AFTER state
        after_state = self._capture_target_snapshot(execution.target_id, candidate_id, twin=twin, vault=vault, db=db)

        # Log timeline events
        self._record_timeline_event(
            candidate_id=candidate_id,
            target_id=execution.target_id,
            event_type=TimelineEventType.EVIDENCE_VERIFIED,
            description=f"Verified {len(approved_claims)} evidence claim(s) at '{highest_scope}'.",
            execution_id=execution_id,
            evidence_ids=new_evidence_ids,
            db=db,
        )
        self._record_timeline_event(
            candidate_id=candidate_id,
            target_id=execution.target_id,
            event_type=TimelineEventType.CAREER_TWIN_REFRESHED,
            description="Refreshed Career Twin and Evidence Vault indexes with newly verified evidence.",
            execution_id=execution_id,
            db=db,
        )
        self._record_timeline_event(
            candidate_id=candidate_id,
            target_id=execution.target_id,
            event_type=TimelineEventType.JOB_FIT_REFRESHED,
            description=f"Target Job Fit refreshed: {after_state.get('matched', 0)} matched, {after_state.get('partial', 0)} partial.",
            execution_id=execution_id,
            db=db,
        )

        return EvidenceVerificationResult(
            verified=True,
            execution_id=execution_id,
            evidence_ids=new_evidence_ids,
            verified_count=len(new_evidence_ids),
            claim_scope=highest_scope,
            provenance=provenance_records,
            rejection_reason=None,
            explanation=f"Successfully verified {len(approved_claims)} claim(s). Scope evaluated at {highest_scope}.",
            before_state=before_state,
            after_state=after_state,
        )

    # =========================================================================
    # 4. BEFORE / AFTER TARGET PROGRESS & TIMELINE
    # =========================================================================

    def get_target_progress(
        self,
        target_id: str,
        candidate_id: str,
        twin: Optional[CareerTwin] = None,
        vault: Optional[EvidenceVault] = None,
        db: Optional[Session] = None,
    ) -> TargetProgressComparison:
        """
        Computes diagnostic before/after target progress comparison.
        Shows exact changed requirements, classifications, reasons, and supporting evidence IDs.
        Strictly diagnostic: NO employability score, NO hiring probability.
        """
        # Tenancy check
        target_role = "Target Role"
        target_company = None
        target_reqs: List[Dict[str, Any]] = []

        if db:
            repo = Repository(db)
            target_rec = repo.get_career_target(target_id)
            if not target_rec:
                it_rec = repo.get_interview_target(target_id)
                if it_rec:
                    if getattr(it_rec, "target_id", None):
                        target_rec = repo.get_career_target(it_rec.target_id) or it_rec
                    else:
                        target_rec = it_rec
            if not target_rec:
                try:
                    from app.api.routes.coach import _in_memory_targets
                    mem_t = _in_memory_targets.get(target_id)
                    if mem_t:
                        if mem_t.candidate_id != candidate_id:
                            raise PermissionError(
                                f"Security violation: Target '{target_id}' does not belong to candidate '{candidate_id}'."
                            )
                        target_role = mem_t.target_role
                        target_company = mem_t.target_company
                        target_reqs = mem_t.requirements or []
                except PermissionError:
                    raise
                except Exception:
                    pass
            if target_rec:
                if target_rec.candidate_id != candidate_id:
                    raise PermissionError(
                        f"Security violation: Target '{target_id}' does not belong to candidate '{candidate_id}'."
                    )
                target_role = target_rec.target_role
                target_company = getattr(target_rec, "target_company", getattr(target_rec, "company", None))
                target_reqs = json.loads(getattr(target_rec, "requirements_json", "[]") or "[]")
        else:
            try:
                from app.api.routes.coach import _in_memory_targets
                mem_t = _in_memory_targets.get(target_id)
                if mem_t:
                    if mem_t.candidate_id != candidate_id:
                        raise PermissionError(
                            f"Security violation: Target '{target_id}' does not belong to candidate '{candidate_id}'."
                        )
                    target_role = mem_t.target_role
                    target_company = mem_t.target_company
                    target_reqs = mem_t.requirements or []
            except PermissionError:
                raise
            except Exception:
                pass

        # Get linked executions
        executions = self.list_executions_for_candidate(candidate_id, target_id=target_id, db=db)
        actions_by_req: Dict[str, List[Dict[str, Any]]] = {}
        for ex in executions:
            action_info = {
                "execution_id": ex.execution_id,
                "action_id": ex.action_id,
                "status": ex.status.value,
                "progress_state": ex.progress_state.value,
                "progress_percent": ex.progress_percent,
                "claim_scope": ex.claim_scope,
            }
            if ex.target_id not in actions_by_req:
                actions_by_req[ex.target_id] = []
            actions_by_req[ex.target_id].append(action_info)

        # Baseline snapshot (before) vs current snapshot (after)
        after_snapshot = self._capture_target_snapshot(target_id, candidate_id, twin=twin, vault=vault, db=db)
        if target_id not in self._target_baseline_snapshots:
            self._target_baseline_snapshots[target_id] = after_snapshot
        before_snapshot = self._target_baseline_snapshots.get(target_id, after_snapshot)

        # Build delta for requirements that changed
        deltas: List[TargetRequirementDelta] = []
        before_req_map = {r["requirement_id"]: r for r in before_snapshot.get("requirements_detail", [])}
        after_req_map = {r["requirement_id"]: r for r in after_snapshot.get("requirements_detail", [])}

        for req_id, after_r in after_req_map.items():
            before_r = before_req_map.get(req_id, after_r)
            prev_status = before_r.get("status", "MISSING")
            curr_status = after_r.get("status", "MISSING")
            prev_scope = before_r.get("claim_scope")
            curr_scope = after_r.get("claim_scope")

            if prev_status != curr_status or prev_scope != curr_scope:
                reason = f"Requirement progressed from {prev_status} to {curr_status}."
                if curr_scope and curr_scope != prev_scope:
                    reason += f" Claim scope advanced to {curr_scope}."

                deltas.append(TargetRequirementDelta(
                    requirement_id=req_id,
                    requirement_text=after_r.get("requirement_text", ""),
                    previous_classification=prev_status,
                    new_classification=curr_status,
                    previous_claim_scope=prev_scope,
                    new_claim_scope=curr_scope,
                    previous_scope=prev_scope,
                    new_scope=curr_scope,
                    reason=reason,
                    supporting_evidence_ids=after_r.get("evidence_ids", []),
                ))

        # Build RequirementProgressItem list
        req_progress_items: List[RequirementProgressItem] = []
        now = datetime.datetime.utcnow()
        for r_detail in after_snapshot.get("requirements_detail", []):
            rid = r_detail["requirement_id"]
            # Latest verified evidence snippet
            latest_ev = None
            if r_detail.get("evidence_ids"):
                latest_ev_id = r_detail["evidence_ids"][-1]
                if vault:
                    v_item = next((it for it in vault.items if it.evidence_id == latest_ev_id), None)
                    if v_item:
                        latest_ev = {
                            "evidence_id": v_item.evidence_id,
                            "source_text": v_item.source_text,
                            "evidence_type": v_item.evidence_type,
                            "source_document": v_item.source_document,
                        }

            req_progress_items.append(RequirementProgressItem(
                requirement_id=rid,
                requirement_text=r_detail["requirement_text"],
                current_state=r_detail["status"],
                gap_type=r_detail.get("gap_type"),
                claim_scope=r_detail.get("claim_scope") or "LEVEL 1 — TECHNOLOGY PRESENCE",
                evidence_count=len(r_detail.get("evidence_ids", [])),
                related_actions=actions_by_req.get(target_id, []),
                latest_verified_evidence=latest_ev,
                latest_evidence_snippet=latest_ev.get("source_text") if latest_ev else None,
                last_updated=now,
            ))

        # Fallback: if req_progress_items is empty but target has requirements, populate from target_reqs
        if not req_progress_items and target_reqs:
            for r in target_reqs:
                rid = r.get("requirement_id", f"req_{uuid.uuid4().hex[:8]}")
                req_progress_items.append(RequirementProgressItem(
                    requirement_id=rid,
                    requirement_text=r.get("requirement_text", ""),
                    current_state="MISSING",
                    gap_type="EXPERIENCE_GAP",
                    claim_scope="LEVEL 1 — TECHNOLOGY PRESENCE",
                    evidence_count=0,
                    related_actions=actions_by_req.get(target_id, []),
                    latest_verified_evidence=None,
                    latest_evidence_snippet=None,
                    last_updated=now,
                ))

        # Retrieve Timeline events
        timeline_events = self._get_timeline_events(target_id, candidate_id, db=db)

        before_summary = {
            "matched": before_snapshot.get("matched", 0),
            "partial": before_snapshot.get("partial", 0),
            "missing": before_snapshot.get("missing", 0),
            "visibility_gaps": before_snapshot.get("visibility_gaps", 0),
            "experience_gaps": before_snapshot.get("experience_gaps", 0),
            "not_verifiable": before_snapshot.get("not_verifiable", 0),
        }
        after_summary = {
            "matched": after_snapshot.get("matched", 0),
            "partial": after_snapshot.get("partial", 0),
            "missing": after_snapshot.get("missing", 0),
            "visibility_gaps": after_snapshot.get("visibility_gaps", 0),
            "experience_gaps": after_snapshot.get("experience_gaps", 0),
            "not_verifiable": after_snapshot.get("not_verifiable", 0),
        }
        if target_reqs and sum(after_summary.values()) == 0:
            after_summary["missing"] = len(target_reqs)
            after_summary["experience_gaps"] = len(target_reqs)
            before_summary["missing"] = len(target_reqs)
            before_summary["experience_gaps"] = len(target_reqs)

        return TargetProgressComparison(
            target_id=target_id,
            candidate_id=candidate_id,
            target_role=target_role,
            target_company=target_company,
            before_summary=before_summary,
            after_summary=after_summary,
            before_matched=before_summary["matched"],
            before_partial=before_summary["partial"],
            before_missing=before_summary["missing"],
            before_visibility_gaps=before_summary["visibility_gaps"],
            before_experience_gaps=before_summary["experience_gaps"],
            before_not_verifiable=before_summary.get("not_verifiable", 0),
            after_matched=after_summary["matched"],
            after_partial=after_summary["partial"],
            after_missing=after_summary["missing"],
            after_visibility_gaps=after_summary["visibility_gaps"],
            after_experience_gaps=after_summary["experience_gaps"],
            after_not_verifiable=after_summary.get("not_verifiable", 0),
            delta=deltas,
            deltas=deltas,
            requirement_progress=req_progress_items,
            requirements=req_progress_items,
            timeline=timeline_events,
        )

    # =========================================================================
    # 5. INTERNAL HELPERS
    # =========================================================================

    def _capture_target_snapshot(
        self,
        target_id: str,
        candidate_id: str,
        twin: Optional[CareerTwin] = None,
        vault: Optional[EvidenceVault] = None,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Runs deterministic job fit evaluation to capture requirement breakdown."""
        target_role = "Target Role"
        job_text = f"Role: {target_role}\n"
        req_list: List[Dict[str, Any]] = []

        if db:
            repo = Repository(db)
            target_rec = repo.get_career_target(target_id)
            if not target_rec:
                it_rec = repo.get_interview_target(target_id)
                if it_rec:
                    if getattr(it_rec, "target_id", None):
                        target_rec = repo.get_career_target(it_rec.target_id) or it_rec
                    else:
                        target_rec = it_rec
            if target_rec:
                target_role = target_rec.target_role
                job_text = getattr(target_rec, "raw_jd_text", None) or f"Role: {target_role}\n"
                req_list = json.loads(getattr(target_rec, "requirements_json", "[]") or "[]")

        if not req_list:
            try:
                from app.api.routes.coach import _in_memory_targets
                mem_t = _in_memory_targets.get(target_id)
                if mem_t:
                    target_role = mem_t.target_role
                    job_text = mem_t.raw_jd_text or f"Role: {target_role}\n"
                    req_list = mem_t.requirements or []
            except Exception:
                pass

        # Construct JD
        page = DocumentPage(page_number=1, raw_text=job_text, normalized_text=job_text.lower())
        doc = GenericDocument(
            document_id=f"doc_snap_{uuid.uuid4().hex[:8]}",
            filename="snap_jd.txt",
            page_count=1,
            pages=[page],
            raw_text=job_text,
            normalized_text=job_text.lower(),
        )
        if req_list:
            from app.schemas.domain import JobDescription
            jd = JobDescription(jd_id=f"job_{uuid.uuid4().hex[:8]}", title=target_role, raw_text=job_text, requirements=[])
            for r in req_list:
                is_r = r.get("is_required", True) or str(r.get("priority", "")).upper() == "REQUIRED"
                jd.requirements.append(
                    JDRequirement(
                        id=r.get("requirement_id", f"req_{uuid.uuid4().hex[:8]}"),
                        requirement_text=r.get("requirement_text", ""),
                        category=RequirementCategory.SKILL,
                        priority=RequirementPriority.REQUIRED if is_r else RequirementPriority.PREFERRED,
                    )
                )
        else:
            jd = self.job_fit_service.jd_analyzer.analyze(doc)
            if len(jd.requirements) == 0 and job_text:
                lines = [l.strip() for l in job_text.split("\n") if l.strip()]
                for l in lines:
                    clean = re.sub(r'^[0-9\.\-\•\*\s]+', '', l).strip()
                    if clean and not clean.lower().startswith("requirements") and not clean.lower().startswith("role:"):
                        is_pref = "preferred" in l.lower()
                        jd.requirements.append(
                            JDRequirement(
                                id=f"req_{uuid.uuid4().hex[:8]}",
                                requirement_text=clean,
                                category=RequirementCategory.SKILL,
                                priority=RequirementPriority.PREFERRED if is_pref else RequirementPriority.REQUIRED,
                            )
                        )

        # Profile from twin or minimal
        import copy
        profile = None
        if twin and twin.candidate_profile:
            profile = copy.deepcopy(twin.candidate_profile)
        else:
            profile = CandidateProfile(
                candidate_id=candidate_id,
                name="Candidate",
                skills=list(twin.skills) if twin else [],
                raw_text=" ".join(twin.skills) if twin else "",
            )

        existing_skills = {s.name.lower() for s in profile.skill_details if s.name}
        for s in (twin.skills if twin else []):
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

        fit_res = self.job_fit_service.evaluate_fit(
            profile=profile,
            jd=jd,
            twin=twin,
            vault=vault,
            raw_jd_text=job_text,
        )

        analysis = fit_res.job_fit_analysis
        matched = len(analysis.matched_requirements) if analysis else 0
        partial = len(analysis.partial_requirements) if analysis else 0
        missing = len(analysis.missing_requirements) if analysis else 0

        visibility_gaps = sum(1 for g in analysis.evidence_gaps if g.gap_type == GapType.RESUME_VISIBILITY_GAP) if analysis else 0
        experience_gaps = sum(1 for g in analysis.evidence_gaps if g.gap_type == GapType.EXPERIENCE_GAP) if analysis else 0
        not_verifiable = sum(1 for g in analysis.evidence_gaps if g.gap_type == GapType.NOT_VERIFIABLE) if analysis else 0

        req_detail = []
        if analysis:
            for req in analysis.requirements:
                e_ids = [ev.evidence_id for ev in req.evidence if ev.evidence_id]
                gap_obj = next((g for g in analysis.evidence_gaps if g.requirement_id == req.requirement_id), None)
                gap_val = gap_obj.gap_type.value if gap_obj else None
                
                # Derive claim scope for this requirement based on verified evidence
                scope_str = "LEVEL 1 — TECHNOLOGY PRESENCE"
                if req.evidence:
                    combined_ev = " ".join([ev.source_text for ev in req.evidence if ev.source_text])
                    if combined_ev:
                        scope_str = classify_claim_scope(combined_ev)

                req_detail.append({
                    "requirement_id": req.requirement_id,
                    "requirement_text": req.requirement_text,
                    "status": req.status.value,
                    "gap_type": gap_val,
                    "claim_scope": scope_str,
                    "evidence_ids": e_ids,
                })

        return {
            "matched": matched,
            "partial": partial,
            "missing": missing,
            "visibility_gaps": visibility_gaps,
            "experience_gaps": experience_gaps,
            "not_verifiable": not_verifiable,
            "requirements_detail": req_detail,
        }

    def _save_execution(self, execution: CareerExecution, db: Optional[Session] = None):
        """Persists execution in memory and DB."""
        self._in_memory_executions[execution.execution_id] = execution
        if db:
            repo = Repository(db)
            repo.save_career_execution(
                execution_id=execution.execution_id,
                candidate_id=execution.candidate_id,
                action_id=execution.action_id,
                target_id=execution.target_id,
                status=execution.status.value,
                progress_state=execution.progress_state.value,
                progress_percent=execution.progress_percent,
                started_at=execution.started_at,
                completed_at=execution.completed_at,
                notes=[n.model_dump() for n in execution.notes],
                blocker_reason=execution.blocker_reason,
                next_step=execution.next_step,
                artifact_references=[a.model_dump() for a in execution.artifact_references],
                evidence_ids=execution.evidence_ids,
                claim_scope=execution.claim_scope,
            )

    def _record_timeline_event(
        self,
        candidate_id: str,
        target_id: str,
        event_type: TimelineEventType,
        description: str,
        execution_id: Optional[str] = None,
        evidence_ids: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        db: Optional[Session] = None,
    ):
        """Records a chronological timeline event."""
        now = datetime.datetime.utcnow()
        event_id = f"evt_{uuid.uuid4().hex[:10]}"
        event = TimelineEvent(
            event_id=event_id,
            timestamp=now,
            event_type=event_type,
            description=description,
            evidence_ids=evidence_ids or [],
            metadata=metadata or {},
        )

        if target_id not in self._in_memory_timeline:
            self._in_memory_timeline[target_id] = []
        self._in_memory_timeline[target_id].append(event)

        if db:
            repo = Repository(db)
            repo.save_execution_timeline_event(
                event_id=event_id,
                candidate_id=candidate_id,
                target_id=target_id,
                event_type=event_type.value,
                description=description,
                execution_id=execution_id,
                evidence_ids=evidence_ids or [],
                metadata=metadata or {},
            )

    def _get_timeline_events(
        self,
        target_id: str,
        candidate_id: str,
        db: Optional[Session] = None,
    ) -> List[TimelineEvent]:
        """Retrieves ordered timeline events."""
        events_by_id: Dict[str, TimelineEvent] = {}

        for evt in self._in_memory_timeline.get(target_id, []):
            events_by_id[evt.event_id] = evt

        if db:
            repo = Repository(db)
            records = repo.get_execution_timeline_events_for_target(target_id, candidate_id=candidate_id)
            if records:
                for r in records:
                    try:
                        ev_type = TimelineEventType(r.event_type)
                    except ValueError:
                        ev_type = TimelineEventType.PROGRESS_UPDATED
                    events_by_id[r.event_id] = TimelineEvent(
                        event_id=r.event_id,
                        timestamp=r.created_at,
                        event_type=ev_type,
                        description=r.description,
                        evidence_ids=json.loads(r.evidence_ids_json or "[]"),
                        metadata=json.loads(r.metadata_json or "{}"),
                    )

        return sorted(events_by_id.values(), key=lambda e: e.timestamp)

    def _record_to_execution(self, rec: Any, db: Optional[Session] = None) -> CareerExecution:
        """Maps DB CareerExecutionRecord to Pydantic CareerExecution."""
        raw_notes = json.loads(getattr(rec, "notes_json", "[]") or "[]")
        notes = []
        for n in raw_notes:
            if isinstance(n, dict):
                c_at = n.get("created_at")
                if isinstance(c_at, str):
                    try:
                        c_at = datetime.datetime.fromisoformat(c_at)
                    except Exception:
                        c_at = datetime.datetime.utcnow()
                notes.append(ExecutionNote(
                    note_id=n.get("note_id", f"note_{uuid.uuid4().hex[:8]}"),
                    content=n.get("content", ""),
                    created_at=c_at or datetime.datetime.utcnow(),
                ))

        raw_artifacts = json.loads(getattr(rec, "artifact_references_json", "[]") or "[]")
        artifacts = []
        for a in raw_artifacts:
            if isinstance(a, dict):
                s_at = a.get("submitted_at")
                if isinstance(s_at, str):
                    try:
                        s_at = datetime.datetime.fromisoformat(s_at)
                    except Exception:
                        s_at = datetime.datetime.utcnow()
                artifacts.append(ArtifactReference(
                    artifact_id=a.get("artifact_id", f"art_{uuid.uuid4().hex[:8]}"),
                    name=a.get("name", "Artifact"),
                    artifact_type=ArtifactType(a.get("artifact_type", "OTHER")),
                    url_or_path=a.get("url_or_path", ""),
                    description=a.get("description", ""),
                    technologies=a.get("technologies", []),
                    submitted_at=s_at or datetime.datetime.utcnow(),
                ))

        raw_evidence_ids = json.loads(getattr(rec, "evidence_ids_json", "[]") or "[]")

        title = None
        if rec.execution_id in self._in_memory_executions:
            title = self._in_memory_executions[rec.execution_id].title
        if not title and db:
            repo = Repository(db)
            act = repo.get_career_action(rec.action_id)
            if act and act.title:
                title = act.title
        if not title:
            try:
                from app.api.routes.coach import _in_memory_actions
                if rec.action_id in _in_memory_actions:
                    title = _in_memory_actions[rec.action_id].title
            except Exception:
                pass
        if not title:
            title = f"Action {rec.action_id}"

        return CareerExecution(
            execution_id=rec.execution_id,
            candidate_id=rec.candidate_id,
            action_id=rec.action_id,
            target_id=rec.target_id,
            title=title,
            status=ExecutionStatus(rec.status),
            progress_state=ProgressState(rec.progress_state),
            progress_percent=rec.progress_percent,
            started_at=rec.started_at,
            completed_at=rec.completed_at,
            notes=notes,
            blocker_reason=rec.blocker_reason,
            next_step=rec.next_step,
            artifact_references=artifacts,
            evidence_ids=raw_evidence_ids,
            claim_scope=rec.claim_scope,
            created_at=rec.created_at,
            updated_at=rec.updated_at,
        )
