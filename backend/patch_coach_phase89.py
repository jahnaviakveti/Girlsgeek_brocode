import re

with open('app/api/routes/coach.py', 'r') as f:
    content = f.read()

# 1. Add missing imports
imports = """
from app.schemas.career_execution import (
    CreateCareerExecutionRequest, StartExecutionRequest,
    UpdateExecutionProgressRequest, BlockExecutionRequest,
    CompleteExecutionRequest, SubmitArtifactRequest,
    VerifyEvidenceRequest, EvidenceVerificationResult,
    CareerExecution
)
from app.services.coach.career_execution.service import CareerExecutionService
from app.schemas.showcase import (
    UpdateShowcaseRequest,
    PublicCareerShowcase,
    CareerShowcase
)
from app.services.coach.showcase.service import CareerShowcaseService
"""
if "CareerExecutionService" not in content:
    content = re.sub(r'(from app.db.database import get_db, init_db)', imports + r'\1', content)

# 2. Add missing singletons
singletons = """
_career_execution_service = CareerExecutionService(
    vault_service=_vault_service,
    job_fit_service=_job_fit_service,
    validation_service=_validation_service,
)
_showcase_service = CareerShowcaseService()
"""
if "_career_execution_service =" not in content:
    content = re.sub(r'(_career_intelligence_service = CareerIntelligenceService\(job_fit_service=_job_fit_service\)\n)', r'\1' + singletons + '\n', content)

# 3. Read the recovered career_execution endpoints (lines 1690 to 1915 from Phase 8 log)
with open('recovered_all.txt', 'r') as f:
    recovered_lines = f.readlines()
    
# Extract lines that start with numbers and reconstruct the python code
recovered_code = ""
for line in recovered_lines:
    if re.match(r'^[0-9]+:\s', line):
        recovered_code += re.sub(r'^[0-9]+:\s', '', line)
    
# 4. Also append the rest of the showcase endpoints
showcase_endpoints = """

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
"""

if "def list_career_executions" not in content:
    # We must patch the recovered_code to add auth dependencies and the override
    # recovered_code has the decorators and function definitions.
    # We will use re.sub on recovered_code
    
    # 1. Inject current_user into args
    recovered_code = re.sub(
        r'(db: Session = Depends\(get_db\))',
        r'\1, current_user: UserRecord = Depends(get_current_user)',
        recovered_code
    )
    
    # 2. Inject AUTHENTICATION OVERRIDE block
    def inject_override(match):
        header = match.group(1)
        body = match.group(2)
        override = """
    # AUTHENTICATION OVERRIDE
    locals_dict = locals()
    if 'candidate_id' in locals_dict: candidate_id = current_user.id
    if 'payload' in locals_dict and hasattr(locals_dict['payload'], 'candidate_id'): locals_dict['payload'].candidate_id = current_user.id
"""
        return header + override + body

    # Match the end of a function definition `:\n`
    recovered_code = re.sub(
        r'((?:->\s*[^:]+)?:\n)(\s+try:)',
        inject_override,
        recovered_code
    )
    
    content = content + "\n\n" + recovered_code + "\n\n" + showcase_endpoints

with open('app/api/routes/coach.py', 'w') as f:
    f.write(content)

print("Patch successful!")
