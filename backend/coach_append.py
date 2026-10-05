from fastapi import APIRouter, HTTPException, Depends, Header
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.auth import get_current_user, UserRecord
from app.schemas.career_execution import (
    CreateCareerExecutionRequest, StartExecutionRequest,
    UpdateExecutionProgressRequest, BlockExecutionRequest,
    CompleteExecutionRequest, SubmitArtifactRequest,
    VerifyEvidenceRequest, EvidenceVerificationResult,
    CareerExecution
)
from app.schemas.showcase import (
    UpdateShowcaseRequest,
    PublicCareerShowcase,
    CareerShowcase
)

# --- ENDPOINTS TO APPEND ---

@router.get(
    "/career-executions/{candidate_id}",
    response_model=List[CareerExecution],
    summary="List Career Executions",
    description="Returns all execution records for a candidate, optionally filtered by target_id."
)
def list_career_executions(
    candidate_id: str,
    target_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user)
) -> List[CareerExecution]:
    # AUTHENTICATION OVERRIDE
    locals_dict = locals()
    if 'candidate_id' in locals_dict: candidate_id = current_user.id
    if 'payload' in locals_dict and hasattr(locals_dict['payload'], 'candidate_id'): locals_dict['payload'].candidate_id = current_user.id
    
    try:
        return _career_execution_service.list_executions_for_candidate(
            candidate_id=candidate_id,
            target_id=target_id,
            db=db,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/career-executions",
    response_model=CareerExecution,
    summary="Create Career Execution",
    description="Initializes persistent tracking for a career action."
)
def create_career_execution(
    payload: CreateCareerExecutionRequest,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user)
) -> CareerExecution:
    # AUTHENTICATION OVERRIDE
    locals_dict = locals()
    if 'candidate_id' in locals_dict: candidate_id = current_user.id
    if 'payload' in locals_dict and hasattr(locals_dict['payload'], 'candidate_id'): locals_dict['payload'].candidate_id = current_user.id
    
    try:
        return _career_execution_service.create_execution(
            candidate_id=payload.candidate_id,
            action_id=payload.action_id,
            target_id=payload.target_id,
            notes=payload.notes,
            db=db,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get(
    "/career-executions/{candidate_id}/{execution_id}",
    response_model=CareerExecution,
    summary="Get Career Execution Detail",
    description="Returns a single execution record with strict tenant ownership verification."
)
def get_career_execution_detail(
    candidate_id: str,
    execution_id: str,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user)
) -> CareerExecution:
    # AUTHENTICATION OVERRIDE
    locals_dict = locals()
    if 'candidate_id' in locals_dict: candidate_id = current_user.id
    if 'payload' in locals_dict and hasattr(locals_dict['payload'], 'candidate_id'): locals_dict['payload'].candidate_id = current_user.id
    
    try:
        return _career_execution_service.get_execution(
            candidate_id=candidate_id,
            execution_id=execution_id,
            db=db,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/career-executions/{execution_id}/start",
    response_model=CareerExecution,
    summary="Start Career Execution",
    description="Transitions an execution from NOT_STARTED to IN_PROGRESS."
)
def start_career_execution(
    execution_id: str,
    payload: StartExecutionRequest,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user)
) -> CareerExecution:
    # AUTHENTICATION OVERRIDE
    locals_dict = locals()
    if 'candidate_id' in locals_dict: candidate_id = current_user.id
    if 'payload' in locals_dict and hasattr(locals_dict['payload'], 'candidate_id'): locals_dict['payload'].candidate_id = current_user.id
    
    try:
        return _career_execution_service.start_execution(
            candidate_id=payload.candidate_id,
            execution_id=execution_id,
            db=db,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/career-executions/{execution_id}/progress",
    response_model=CareerExecution,
    summary="Update Career Execution Progress",
    description="Updates progress percentage and notes. Never grants skills or verified evidence directly."
)
def update_career_execution_progress(
    execution_id: str,
    payload: UpdateExecutionProgressRequest,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user)
) -> CareerExecution:
    # AUTHENTICATION OVERRIDE
    locals_dict = locals()
    if 'candidate_id' in locals_dict: candidate_id = current_user.id
    if 'payload' in locals_dict and hasattr(locals_dict['payload'], 'candidate_id'): locals_dict['payload'].candidate_id = current_user.id
    
    try:
        return _career_execution_service.update_progress(
            candidate_id=payload.candidate_id,
            execution_id=execution_id,
            progress_percent=payload.progress_percent,
            notes=payload.notes,
            next_step=payload.next_step,
            db=db,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/career-executions/{execution_id}/submit-artifact",
    response_model=CareerExecution,
    summary="Submit Execution Artifact",
    description="Attaches a genuine artifact reference to the execution record."
)
def submit_career_execution_artifact(
    execution_id: str,
    payload: SubmitArtifactRequest,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user)
) -> CareerExecution:
    # AUTHENTICATION OVERRIDE
    locals_dict = locals()
    if 'candidate_id' in locals_dict: candidate_id = current_user.id
    if 'payload' in locals_dict and hasattr(locals_dict['payload'], 'candidate_id'): locals_dict['payload'].candidate_id = current_user.id
    
    try:
        return _career_execution_service.submit_artifact(
            candidate_id=payload.candidate_id,
            execution_id=execution_id,
            name=payload.name,
            artifact_type=payload.artifact_type,
            url_or_path=payload.url_or_path,
            description=payload.description,
            technologies=payload.technologies,
            db=db,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/career-executions/{execution_id}/complete",
    response_model=CareerExecution,
    summary="Complete Career Execution (Self-Reported)",
    description="Marks execution as SELF_REPORTED_COMPLETE. Does NOT alter Evidence Vault or Twin."
)
def complete_career_execution_self_reported(
    execution_id: str,
    payload: CompleteExecutionRequest,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user)
) -> CareerExecution:
    # AUTHENTICATION OVERRIDE
    locals_dict = locals()
    if 'candidate_id' in locals_dict: candidate_id = current_user.id
    if 'payload' in locals_dict and hasattr(locals_dict['payload'], 'candidate_id'): locals_dict['payload'].candidate_id = current_user.id
    
    try:
        return _career_execution_service.complete_self_reported(
            candidate_id=payload.candidate_id,
            execution_id=execution_id,
            notes=payload.notes,
            db=db,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/career-executions/{execution_id}/block",
    response_model=CareerExecution,
    summary="Report Execution Blocker",
    description="Flags execution as BLOCKED with reason and next steps."
)
def block_career_execution(
    execution_id: str,
    payload: BlockExecutionRequest,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user)
) -> CareerExecution:
    # AUTHENTICATION OVERRIDE
    locals_dict = locals()
    if 'candidate_id' in locals_dict: candidate_id = current_user.id
    if 'payload' in locals_dict and hasattr(locals_dict['payload'], 'candidate_id'): locals_dict['payload'].candidate_id = current_user.id
    
    try:
        return _career_execution_service.report_blocker(
            candidate_id=payload.candidate_id,
            execution_id=execution_id,
            blocker_reason=payload.blocker_reason,
            next_step=payload.next_step,
            db=db,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/career-executions/{execution_id}/verify-evidence",
    response_model=EvidenceVerificationResult,
    summary="Verify Execution Evidence",
    description="Validates submitted artifact claims and attaches verified items to Evidence Vault."
)
def verify_career_execution_evidence(
    execution_id: str,
    payload: VerifyEvidenceRequest,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user)
) -> EvidenceVerificationResult:
    # AUTHENTICATION OVERRIDE
    locals_dict = locals()
    if 'candidate_id' in locals_dict: candidate_id = current_user.id
    if 'payload' in locals_dict and hasattr(locals_dict['payload'], 'candidate_id'): locals_dict['payload'].candidate_id = current_user.id
    
    try:
        twin = _get_or_load_twin(payload.candidate_id, db)
        vault = _get_or_load_vault(payload.candidate_id, db)
        return _career_execution_service.verify_evidence(
            candidate_id=payload.candidate_id,
            execution_id=execution_id,
            evidence_claims=payload.evidence_claims,
            artifact_id=payload.artifact_id,
            db=db,
            twin=twin,
            vault=vault,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# =============================================================================
# PHASE 9: CAREER SHOWCASE & PRODUCTION RELEASE ENDPOINTS
# =============================================================================

@router.get(
    "/showcase/{candidate_id}",
    response_model=CareerShowcase,
    summary="Get Private Career Showcase",
    description="Returns the full career showcase for the candidate."
)
def get_career_showcase(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user)
) -> CareerShowcase:
    # AUTHENTICATION OVERRIDE
    locals_dict = locals()
    if 'candidate_id' in locals_dict: candidate_id = current_user.id
    if 'payload' in locals_dict and hasattr(locals_dict['payload'], 'candidate_id'): locals_dict['payload'].candidate_id = current_user.id

    try:
        twin = _get_or_load_twin(candidate_id, db)
        vault = _get_or_load_vault(candidate_id, db) or EvidenceVault(
            vault_id=f"vault_{candidate_id}", candidate_id=candidate_id, items=[], total_items=0
        )
        return _showcase_service.get_candidate_showcase(
            candidate_id=candidate_id,
            twin=twin,
            vault=vault,
            db=db
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/showcase/{candidate_id}",
    response_model=CareerShowcase,
    summary="Update Career Showcase"
)
def update_career_showcase(
    candidate_id: str,
    payload: UpdateShowcaseRequest,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user)
) -> CareerShowcase:
    # AUTHENTICATION OVERRIDE
    locals_dict = locals()
    if 'candidate_id' in locals_dict: candidate_id = current_user.id
    if 'payload' in locals_dict and hasattr(locals_dict['payload'], 'candidate_id'): locals_dict['payload'].candidate_id = current_user.id

    try:
        twin = _get_or_load_twin(candidate_id, db)
        vault = _get_or_load_vault(candidate_id, db) or EvidenceVault(
            vault_id=f"vault_{candidate_id}", candidate_id=candidate_id, items=[], total_items=0
        )
        return _showcase_service.update_showcase(
            candidate_id=candidate_id,
            request=payload,
            twin=twin,
            vault=vault,
            db=db
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/showcase/{candidate_id}/share-token",
    summary="Generate Share Token"
)
def generate_showcase_share_token(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user)
):
    # AUTHENTICATION OVERRIDE
    locals_dict = locals()
    if 'candidate_id' in locals_dict: candidate_id = current_user.id
    if 'payload' in locals_dict and hasattr(locals_dict['payload'], 'candidate_id'): locals_dict['payload'].candidate_id = current_user.id

    try:
        return _showcase_service.generate_share_token(
            candidate_id=candidate_id,
            db=db
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/showcase/{candidate_id}/revoke-share",
    summary="Revoke Share Token"
)
def revoke_showcase_share_token(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user)
):
    # AUTHENTICATION OVERRIDE
    locals_dict = locals()
    if 'candidate_id' in locals_dict: candidate_id = current_user.id
    if 'payload' in locals_dict and hasattr(locals_dict['payload'], 'candidate_id'): locals_dict['payload'].candidate_id = current_user.id

    try:
        return _showcase_service.revoke_share_token(
            candidate_id=candidate_id,
            db=db
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get(
    "/showcase/public/{share_token}",
    response_model=PublicCareerShowcase,
    summary="Get Public/Shareable Career Showcase"
)
def get_public_career_showcase(
    share_token: str,
    db: Session = Depends(get_db)
) -> PublicCareerShowcase:
    try:
        return _showcase_service.get_public_showcase_by_token(
            share_token=share_token,
            db=db
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/showcase/{candidate_id}/export",
    summary="Export Career Showcase"
)
def export_career_showcase(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user)
):
    # AUTHENTICATION OVERRIDE
    locals_dict = locals()
    if 'candidate_id' in locals_dict: candidate_id = current_user.id
    if 'payload' in locals_dict and hasattr(locals_dict['payload'], 'candidate_id'): locals_dict['payload'].candidate_id = current_user.id

    try:
        twin = _get_or_load_twin(candidate_id, db)
        vault = _get_or_load_vault(candidate_id, db) or EvidenceVault(
            vault_id=f"vault_{candidate_id}", candidate_id=candidate_id, items=[], total_items=0
        )
        return _showcase_service.export_showcase_data(
            candidate_id=candidate_id,
            twin=twin,
            vault=vault,
            db=db
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
