import os
import re
import json
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Optional, Dict, List

from fastapi import APIRouter, UploadFile, File, Form, Query, HTTPException, Depends, status, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.schemas.coach_api import (
    ResumeUploadResponse,
    JobFitAnalysisResponse,
    CareerTwinQueryRequest,
    CareerTwinQueryResponse,
    EvidenceQueryResponse,
    ResumeCoachRequest,
    ResumeCoachResponse,
)
from app.schemas.career_twin import CareerTwin
from app.schemas.evidence_vault import EvidenceVault, VaultEvidenceItem, ClaimValidationResult
from app.schemas.candidate import CandidateProfile
from app.schemas.resume_version import (
    ResumeVersion,
    ResumeVersionSummary,
    CreateVersionRequest,
    CloneVersionRequest,
    ApplySuggestionRequest,
    ApplySuggestionResponse,
    ResumeVersionDiffResponse,
    JobFitRecheckRequest,
    JobFitRecheckResponse,
    ResumeSection,
    AcceptedSuggestion,
    ResumeVersionStatus,
)
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
    CreateCareerTargetRequest,
    CreateCareerActionRequest,
)
from app.services.document_parser import DocumentParser
from app.services.resume_analyzer import ResumeAnalyzer
from app.services.jd_analyzer import JDAnalyzer
from app.services.coach.career_twin import CareerTwinService
from app.services.coach.evidence import EvidenceVaultService, EvidenceValidationService
from app.services.coach.job_fit import JobFitService
from app.services.coach.ats import ATSStressTestService
from app.services.coach.resume import ResumeCoachService
from app.services.coach.resume_builder import ResumeBuilderService
from app.services.coach.career_intelligence import CareerIntelligenceService
from app.schemas.interview_readiness import (
    InterviewTargetStatus,
    PreparationStatus,
    QuestionType,
    ValidationVerdict,
    InterviewTarget,
    InterviewRequirementMapItem,
    InterviewQuestion,
    ProjectStory,
    AnswerValidationResult,
    InterviewSession,
    InterviewSessionItem,
    InterviewReadinessResponse,
    CreateInterviewTargetRequest,
    ValidateAnswerRequest,
    CreateInterviewSessionRequest,
    SubmitSessionAnswerRequest,
)
from app.services.coach.interview import (
    InterviewReadinessService,
    InterviewAnswerCoachService,
    InterviewQuestionService,
)
from app.db.database import get_db, init_db
from app.db.repository import Repository
from app.core.exceptions import DocumentProcessingError

router = APIRouter()

# In-memory session store for rapid retrieval
_in_memory_profiles: Dict[str, CandidateProfile] = {}
_in_memory_twins: Dict[str, CareerTwin] = {}
_in_memory_vaults: Dict[str, EvidenceVault] = {}
_in_memory_versions: Dict[str, ResumeVersion] = {}
_in_memory_targets: Dict[str, CareerTarget] = {}
_in_memory_actions: Dict[str, CareerAction] = {}

# Ensure DB initialized
init_db()

# Service singletons
_parser = DocumentParser()
_resume_analyzer = ResumeAnalyzer()
_jd_analyzer = JDAnalyzer()
_twin_service = CareerTwinService()
_vault_service = EvidenceVaultService()
_validation_service = EvidenceValidationService()
_job_fit_service = JobFitService(jd_analyzer=_jd_analyzer)
_ats_service = ATSStressTestService()
_resume_coach_service = ResumeCoachService(validation_service=_validation_service)
_resume_builder_service = ResumeBuilderService(
    resume_coach_service=_resume_coach_service,
    validation_service=_validation_service
)
_career_intelligence_service = CareerIntelligenceService(job_fit_service=_job_fit_service)
_interview_question_service = InterviewQuestionService()
_interview_answer_coach_service = InterviewAnswerCoachService(evidence_validator=_validation_service)
_interview_readiness_service = InterviewReadinessService(
    career_intelligence_service=_career_intelligence_service,
    question_service=_interview_question_service,
    answer_coach_service=_interview_answer_coach_service,
)

_in_memory_interview_targets: Dict[str, InterviewTarget] = {}
_in_memory_interview_sessions: Dict[str, InterviewSession] = {}

class RefreshTargetRequest(BaseModel):
    candidate_id: str
    previous_coverage: Optional[float] = None

class ActionStatusRequest(BaseModel):
    candidate_id: str

class ClaimValidationRequest(BaseModel):
    candidate_id: str
    claim: str

def _get_or_load_vault(candidate_id: str, db: Session) -> Optional[EvidenceVault]:
    """Helper to retrieve vault from memory or reconstruct from SQLite database."""
    vault = _in_memory_vaults.get(candidate_id)
    if vault:
        return vault

    repo = Repository(db)
    records = repo.get_evidence_for_candidate(candidate_id)
    if not records:
        return None

    items: List[VaultEvidenceItem] = []
    for r in records:
        facts = json.loads(r.normalized_facts) if r.normalized_facts else []
        techs = [t.strip() for t in (r.related_tech or "").split(",") if t.strip()]
        items.append(
            VaultEvidenceItem(
                evidence_id=r.evidence_id,
                candidate_id=r.candidate_id,
                source_text=r.source_text,
                source_document=r.source_document,
                source_section=r.source_section,
                page_number=r.page_number,
                evidence_type=r.evidence_type,
                confidence=r.confidence,
                normalized_facts=facts,
                related_entity=r.related_entity,
                related_skill=r.related_skill,
                related_project=r.related_project,
                related_experience=r.related_experience,
                related_technologies=techs,
            )
        )

    # Reconstruct indices
    section_idx: Dict[str, List[str]] = {}
    tech_idx: Dict[str, List[str]] = {}
    type_idx: Dict[str, List[str]] = {}
    skill_idx: Dict[str, List[str]] = {}
    project_idx: Dict[str, List[str]] = {}
    experience_idx: Dict[str, List[str]] = {}

    for item in items:
        ev_id = item.evidence_id
        if item.source_section:
            section_idx.setdefault(item.source_section.lower(), []).append(ev_id)
        type_idx.setdefault(item.evidence_type.upper(), []).append(ev_id)
        for t in item.related_technologies:
            tech_idx.setdefault(t.lower(), []).append(ev_id)
        if item.related_skill:
            skill_idx.setdefault(item.related_skill.lower(), []).append(ev_id)
        if item.related_project:
            project_idx.setdefault(item.related_project.lower(), []).append(ev_id)
        if item.related_experience:
            experience_idx.setdefault(item.related_experience.lower(), []).append(ev_id)

    vault = EvidenceVault(
        vault_id=f"vault_{candidate_id}",
        candidate_id=candidate_id,
        total_items=len(items),
        items=items,
        section_index=section_idx,
        technology_index=tech_idx,
        type_index=type_idx,
        skill_index=skill_idx,
        project_index=project_idx,
        experience_index=experience_idx
    )
    _in_memory_vaults[candidate_id] = vault
    return vault

def _get_or_load_twin(candidate_id: str, db: Session) -> Optional[CareerTwin]:
    twin = _in_memory_twins.get(candidate_id)
    if twin:
        return twin
    repo = Repository(db)
    rec = repo.get_candidate_profile(candidate_id)
    if not rec:
        return None
    twin_data = json.loads(rec.profile_json)
    twin = CareerTwin(**twin_data)
    _in_memory_twins[candidate_id] = twin
    return twin

def _get_or_load_version(version_id: str, db: Session) -> Optional[ResumeVersion]:
    if version_id in _in_memory_versions:
        return _in_memory_versions[version_id]
    repo = Repository(db)
    rec = repo.get_resume_version(version_id)
    if not rec:
        return None
    sections = [ResumeSection(**s) for s in json.loads(rec.sections_json)]
    suggestions = [AcceptedSuggestion(**s) for s in json.loads(rec.accepted_suggestions_json)]
    evidence_ids = json.loads(rec.evidence_ids_json)
    ver = ResumeVersion(
        version_id=rec.version_id,
        candidate_id=rec.candidate_id,
        parent_version_id=rec.parent_version_id,
        created_at=rec.created_at.isoformat() if rec.created_at else "",
        updated_at=rec.updated_at.isoformat() if rec.updated_at else "",
        title=rec.title,
        target_role=rec.target_role,
        source_resume_version=rec.source_resume_version,
        sections=sections,
        accepted_suggestions=suggestions,
        evidence_ids=evidence_ids,
        status=ResumeVersionStatus(rec.status),
        raw_text=rec.raw_text
    )
    _in_memory_versions[version_id] = ver
    return ver

def _persist_version(version: ResumeVersion, db: Session):
    _in_memory_versions[version.version_id] = version
    repo = Repository(db)
    repo.save_resume_version(
        version_id=version.version_id,
        candidate_id=version.candidate_id,
        title=version.title,
        sections_dict=[s.model_dump() for s in version.sections],
        parent_version_id=version.parent_version_id,
        target_role=version.target_role,
        status=version.status.value if hasattr(version.status, "value") else str(version.status),
        source_resume_version=version.source_resume_version,
        accepted_suggestions_dict=[s.model_dump() for s in version.accepted_suggestions],
        evidence_ids=version.evidence_ids,
        raw_text=version.raw_text
    )

def _get_or_load_target(target_id: str, db: Session) -> Optional[CareerTarget]:
    if target_id in _in_memory_targets:
        return _in_memory_targets[target_id]
    repo = Repository(db)
    rec = repo.get_career_target(target_id)
    if not rec:
        return None
    reqs = json.loads(rec.requirements_json) if rec.requirements_json else []
    target = CareerTarget(
        target_id=rec.target_id,
        candidate_id=rec.candidate_id,
        target_role=rec.target_role,
        target_company=rec.target_company,
        source_job_fit_id=rec.source_job_fit_id,
        status=TargetStatus(rec.status),
        raw_jd_text=rec.raw_jd_text,
        requirements=reqs,
        created_at=rec.created_at,
        updated_at=rec.updated_at
    )
    _in_memory_targets[target_id] = target
    return target

def _persist_target(target: CareerTarget, db: Session):
    _in_memory_targets[target.target_id] = target
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

def _get_or_load_interview_target(interview_target_id: str, db: Session) -> Optional[InterviewTarget]:
    if interview_target_id in _in_memory_interview_targets:
        return _in_memory_interview_targets[interview_target_id]
    repo = Repository(db)
    rec = repo.get_interview_target(interview_target_id)
    if not rec:
        return None
    it = InterviewTarget(
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
    _in_memory_interview_targets[interview_target_id] = it
    return it

def _persist_interview_target(target: InterviewTarget, db: Session):
    _in_memory_interview_targets[target.interview_target_id] = target
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

@router.get("/health", summary="Coach Service Health Check")
def coach_health():
    return {"status": "ok", "service": "Vettora AI Career Coach Layer"}

@router.post(
    "/resume",
    response_model=ResumeUploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest single resume into Career Twin and Evidence Vault",
    description="Parses candidate resume PDF, creates Career Twin and Evidence Vault, runs ATS readability check, and persists profile."
)
async def upload_resume(
    resume_file: UploadFile = File(..., description="Candidate Resume PDF"),
    db: Session = Depends(get_db)
) -> ResumeUploadResponse:
    if not resume_file or not resume_file.filename:
        raise HTTPException(status_code=400, detail="A resume PDF file is required.")

    if not resume_file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    temp_dir = tempfile.mkdtemp(prefix="vettora_coach_")
    try:
        temp_path = Path(temp_dir) / resume_file.filename
        content = await resume_file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Uploaded PDF is empty (0 bytes).")
        with open(temp_path, "wb") as f_out:
            f_out.write(content)

        # 1. Parse document into GenericDocument
        try:
            doc = _parser.parse_pdf(temp_path)
        except DocumentProcessingError as exc:
            raise HTTPException(status_code=400, detail=f"Document parsing error: {exc.message}")

        # 2. Extract CandidateProfile
        profile = _resume_analyzer.analyze(doc)
        cid = profile.candidate_id

        # 3. Build Evidence Vault
        vault = _vault_service.build_vault(profile)

        # 4. Build Career Twin
        twin = _twin_service.build_twin(profile, vault)

        # 5. Run Baseline ATS Readability Check
        ats_audit = _ats_service.audit_resume(doc, profile)

        # Cache in-memory
        _in_memory_profiles[cid] = profile
        _in_memory_twins[cid] = twin
        _in_memory_vaults[cid] = vault

        # Persist to local SQLite
        try:
            repo = Repository(db)
            repo.save_candidate_profile(
                candidate_id=cid,
                name=twin.name,
                email=twin.email,
                phone=twin.phone,
                summary=twin.summary,
                profile_dict=twin.model_dump()
            )
            repo.save_resume(
                candidate_id=cid,
                filename=resume_file.filename,
                page_count=doc.page_count,
                file_size_bytes=len(content),
                raw_text=doc.raw_text
            )
            repo.save_evidence_batch(
                candidate_id=cid,
                items=[item.model_dump() for item in vault.items]
            )

            # Phase 5: Initialize immutable baseline ResumeVersion
            initial_ver = _resume_builder_service.create_initial_version_from_twin(twin, vault)
            _persist_version(initial_ver, db)
        except Exception as db_exc:
            # Non-blocking logging if DB operation encounters transient lock
            pass

        summary = (
            f"Successfully ingested resume for {twin.name or 'Candidate'}. "
            f"Extracted {len(twin.skills)} skills, {len(twin.experience)} experience entries, "
            f"and indexed {vault.total_items} verifiable facts in the Evidence Vault."
        )

        return ResumeUploadResponse(
            candidate_id=cid,
            filename=resume_file.filename,
            career_twin=twin,
            evidence_vault=vault,
            evidence_summary=twin.evidence_summary,
            ats_quick_score=ats_audit["ats_readability_score"],
            summary=summary
        )

    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

@router.post(
    "/job-fit",
    response_model=JobFitAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate Job Fit and Gaps for a Candidate",
    description="Compares the candidate's Career Twin against a target Job Description PDF or text, returning gap analysis, required vs preferred alignment, and JD bias warnings."
)
async def evaluate_job_fit(
    candidate_id: str = Form(..., description="ID of the previously uploaded candidate"),
    jd_file: Optional[UploadFile] = File(None, description="Optional target Job Description PDF"),
    jd_text: Optional[str] = Form(None, description="Optional target Job Description text (if PDF not provided)"),
    db: Session = Depends(get_db)
) -> JobFitAnalysisResponse:
    # 1. Retrieve profile from in-memory cache or DB
    profile = _in_memory_profiles.get(candidate_id)
    if not profile:
        repo = Repository(db)
        record = repo.get_candidate_profile(candidate_id)
        if not record:
            raise HTTPException(
                status_code=404,
                detail=f"Candidate profile '{candidate_id}' not found. Please upload a resume first."
            )
        # Parse profile from stored json
        p_dict = json.loads(record.profile_json)
        profile = CandidateProfile(**p_dict.get("candidate_profile", p_dict))

    # 2. Parse Job Description
    if not jd_file and not jd_text:
        raise HTTPException(
            status_code=400,
            detail="Either a Job Description PDF (jd_file) or raw text (jd_text) must be provided."
        )

    temp_dir = tempfile.mkdtemp(prefix="vettora_fit_")
    try:
        raw_text = ""
        if jd_file and jd_file.filename:
            temp_path = Path(temp_dir) / jd_file.filename
            content = await jd_file.read()
            with open(temp_path, "wb") as f_out:
                f_out.write(content)
            jd_doc = _parser.parse_pdf(temp_path)
            jd = _jd_analyzer.analyze(jd_doc)
            raw_text = jd_doc.raw_text
        else:
            # Construct GenericDocument from text
            from app.schemas.document import GenericDocument, DocumentPage
            norm_text = jd_text.strip()
            page = DocumentPage(page_number=1, raw_text=norm_text, normalized_text=norm_text, blocks=[])
            generic_doc = GenericDocument(
                document_id=f"jd_{uuid.uuid4().hex[:8]}",
                filename="job_description.txt",
                raw_text=norm_text,
                normalized_text=norm_text,
                page_count=1,
                pages=[page]
            )
            jd = _jd_analyzer.analyze(generic_doc)
            raw_text = norm_text

        # 3. Evaluate Fit using persisted Twin & Vault
        twin = _in_memory_twins.get(candidate_id)
        vault = _get_or_load_vault(candidate_id, db)
        fit_response = _job_fit_service.evaluate_fit(
            profile=profile,
            jd=jd,
            twin=twin,
            vault=vault,
            raw_jd_text=raw_text
        )

        # Optionally persist target JD
        try:
            repo = Repository(db)
            repo.save_job_target(
                job_id=jd.jd_id,
                title=jd.title or "Target Job",
                raw_text=raw_text,
                requirements_dict=[r.model_dump() for r in jd.requirements],
                bias_audit_dict=fit_response.bias_audit.model_dump() if fit_response.bias_audit else None
            )
        except Exception:
            pass

        return fit_response

    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

@router.post(
    "/career-twin",
    response_model=CareerTwinQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query Career Twin by Candidate ID"
)
def get_career_twin(
    payload: CareerTwinQueryRequest,
    db: Session = Depends(get_db)
) -> CareerTwinQueryResponse:
    cid = payload.candidate_id
    twin = _in_memory_twins.get(cid)
    vault = _get_or_load_vault(cid, db)

    if not twin:
        repo = Repository(db)
        record = repo.get_candidate_profile(cid)
        if not record:
            raise HTTPException(status_code=404, detail=f"Career Twin '{cid}' not found.")
        twin_data = json.loads(record.profile_json)
        twin = CareerTwin(**twin_data)

    evidence_summary = twin.evidence_summary or (vault.summary.by_type if vault and vault.summary else {})

    return CareerTwinQueryResponse(
        career_twin=twin,
        evidence_vault=vault,
        evidence_summary=evidence_summary
    )

@router.get(
    "/evidence/{candidate_id}",
    response_model=EvidenceQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query and filter candidate Evidence Vault",
    description="Retrieve verified candidate evidence items with optional filters by section, type, skill, project, or experience."
)
def get_candidate_evidence(
    candidate_id: str,
    section: Optional[str] = Query(None, description="Filter by section name"),
    type: Optional[str] = Query(None, description="Filter by evidence type (SKILL, EXPERIENCE, etc.)"),
    skill: Optional[str] = Query(None, description="Filter by skill or technology"),
    project: Optional[str] = Query(None, description="Filter by project"),
    experience: Optional[str] = Query(None, description="Filter by role or organization"),
    db: Session = Depends(get_db)
) -> EvidenceQueryResponse:
    vault = _get_or_load_vault(candidate_id, db)
    if not vault:
        raise HTTPException(
            status_code=404,
            detail=f"Evidence Vault for candidate '{candidate_id}' not found."
        )

    # Use unified vault filter
    filtered_items = _vault_service.filter_evidence(
        vault=vault,
        section=section,
        evidence_type=type,
        skill=skill,
        project=project,
        experience=experience
    )

    filters_applied = {}
    if section:
        filters_applied["section"] = section
    if type:
        filters_applied["type"] = type
    if skill:
        filters_applied["skill"] = skill
    if project:
        filters_applied["project"] = project
    if experience:
        filters_applied["experience"] = experience

    return EvidenceQueryResponse(
        candidate_id=candidate_id,
        total=len(filtered_items),
        filters_applied=filters_applied,
        evidence=filtered_items
    )

@router.post(
    "/evidence/validate",
    response_model=ClaimValidationResult,
    status_code=status.HTTP_200_OK,
    summary="Validate candidate claim against Evidence Vault",
    description="Validates whether a factual claim is grounded in the candidate's verified Evidence Vault."
)
def validate_candidate_claim(
    payload: ClaimValidationRequest,
    db: Session = Depends(get_db)
) -> ClaimValidationResult:
    vault = _get_or_load_vault(payload.candidate_id, db)
    if not vault:
        raise HTTPException(
            status_code=404,
            detail=f"Evidence Vault for candidate '{payload.candidate_id}' not found."
        )

    return _validation_service.validate_claim(vault, payload.claim)

@router.post(
    "/resume-coach",
    response_model=ResumeCoachResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate Evidence-Locked Resume Rewrite",
    description="Improves resume wording anchored strictly to verified Evidence Vault facts. Rejects ungrounded claims."
)
def generate_resume_rewrite(
    payload: ResumeCoachRequest,
    db: Session = Depends(get_db)
) -> ResumeCoachResponse:
    cid = payload.candidate_id
    if not cid:
        raise HTTPException(status_code=400, detail="Candidate ID is required.")

    twin = _in_memory_twins.get(cid)
    if not twin:
        repo = Repository(db)
        record = repo.get_candidate_profile(cid)
        if not record:
            raise HTTPException(
                status_code=404,
                detail=f"Candidate profile '{cid}' not found. Please upload a resume first."
            )
        twin_data = json.loads(record.profile_json)
        twin = CareerTwin(**twin_data)

    vault = _get_or_load_vault(cid, db)
    if not vault:
        raise HTTPException(
            status_code=404,
            detail=f"Evidence Vault for candidate '{cid}' not found."
        )

    return _resume_coach_service.generate_rewrite(
        request=payload,
        twin=twin,
        vault=vault,
        original_resume_text=payload.current_resume_text
    )

# ============================================================
# PHASE 5: RESUME VERSIONING & BUILDER ENDPOINTS
# ============================================================

@router.post(
    "/resume-versions",
    response_model=ResumeVersion,
    status_code=status.HTTP_201_CREATED,
    summary="Create or Initialize Resume Version",
    description="Creates a new targeted resume version or initializes the baseline version from Career Twin."
)
def create_resume_version(
    payload: CreateVersionRequest,
    db: Session = Depends(get_db)
) -> ResumeVersion:
    cid = payload.candidate_id
    if not cid:
        raise HTTPException(status_code=400, detail="Candidate ID is required.")

    twin = _get_or_load_twin(cid, db)
    if not twin:
        raise HTTPException(status_code=404, detail=f"Candidate profile '{cid}' not found. Please upload a resume first.")

    vault = _get_or_load_vault(cid, db)
    if not vault:
        raise HTTPException(status_code=404, detail=f"Evidence Vault for candidate '{cid}' not found.")

    if payload.parent_version_id:
        parent_ver = _get_or_load_version(payload.parent_version_id, db)
        if not parent_ver:
            raise HTTPException(status_code=404, detail=f"Parent version '{payload.parent_version_id}' not found.")
        new_ver = _resume_builder_service.create_targeted_draft(
            base_version=parent_ver,
            title=payload.title,
            target_role=payload.target_role
        )
    else:
        new_ver = _resume_builder_service.create_initial_version_from_twin(
            twin=twin,
            vault=vault,
            title=payload.title,
            target_role=payload.target_role
        )

    _persist_version(new_ver, db)
    return new_ver

@router.get(
    "/resume-versions/{candidate_id}",
    response_model=List[ResumeVersionSummary],
    status_code=status.HTTP_200_OK,
    summary="List Resume Versions for Candidate",
    description="Lists all historical and draft resume versions for a candidate with provenance metadata."
)
def list_resume_versions(
    candidate_id: str,
    db: Session = Depends(get_db)
) -> List[ResumeVersionSummary]:
    repo = Repository(db)
    records = repo.get_resume_versions_for_candidate(candidate_id)

    summaries: List[ResumeVersionSummary] = []
    if records:
        for r in records:
            sugs = json.loads(r.accepted_suggestions_json) if r.accepted_suggestions_json else []
            evs = json.loads(r.evidence_ids_json) if r.evidence_ids_json else []
            summaries.append(
                ResumeVersionSummary(
                    version_id=r.version_id,
                    candidate_id=r.candidate_id,
                    parent_version_id=r.parent_version_id,
                    created_at=r.created_at.isoformat() if r.created_at else "",
                    updated_at=r.updated_at.isoformat() if r.updated_at else "",
                    title=r.title,
                    target_role=r.target_role,
                    status=ResumeVersionStatus(r.status),
                    accepted_changes_count=len(sugs),
                    evidence_ids_count=len(evs),
                    evidence_backed=True
                )
            )
    else:
        # Check in-memory
        for vid, v in _in_memory_versions.items():
            if v.candidate_id == candidate_id:
                summaries.append(
                    ResumeVersionSummary(
                        version_id=v.version_id,
                        candidate_id=v.candidate_id,
                        parent_version_id=v.parent_version_id,
                        created_at=v.created_at,
                        updated_at=v.updated_at,
                        title=v.title,
                        target_role=v.target_role,
                        status=v.status,
                        accepted_changes_count=len(v.accepted_suggestions),
                        evidence_ids_count=len(v.evidence_ids),
                        evidence_backed=True
                    )
                )

    # If still empty, check if candidate exists and initialize baseline version on the fly
    if not summaries:
        twin = _get_or_load_twin(candidate_id, db)
        vault = _get_or_load_vault(candidate_id, db)
        if twin and vault:
            base_ver = _resume_builder_service.create_initial_version_from_twin(twin, vault)
            _persist_version(base_ver, db)
            summaries.append(
                ResumeVersionSummary(
                    version_id=base_ver.version_id,
                    candidate_id=base_ver.candidate_id,
                    parent_version_id=base_ver.parent_version_id,
                    created_at=base_ver.created_at,
                    updated_at=base_ver.updated_at,
                    title=base_ver.title,
                    target_role=base_ver.target_role,
                    status=base_ver.status,
                    accepted_changes_count=0,
                    evidence_ids_count=len(base_ver.evidence_ids),
                    evidence_backed=True
                )
            )

    return summaries

@router.get(
    "/resume-versions/{version_id}/diff",
    response_model=ResumeVersionDiffResponse,
    status_code=status.HTTP_200_OK,
    summary="Resume Diff / Change View",
    description="Returns candidate-facing comparison view showing BEFORE, AFTER, WHY, and EVIDENCE for all modifications."
)
def get_resume_version_diff(
    version_id: str,
    compare_to_version_id: Optional[str] = Query(None, description="Optional parent version ID to compare against"),
    db: Session = Depends(get_db)
) -> ResumeVersionDiffResponse:
    ver = _get_or_load_version(version_id, db)
    if not ver:
        raise HTTPException(status_code=404, detail=f"Resume version '{version_id}' not found.")

    compare_to = None
    if compare_to_version_id:
        compare_to = _get_or_load_version(compare_to_version_id, db)

    vault = _get_or_load_vault(ver.candidate_id, db)
    return _resume_builder_service.get_version_diff(
        version=ver,
        compare_to_version=compare_to,
        vault=vault
    )

@router.get(
    "/resume-versions/{version_id}/export",
    summary="Export Resume Version to PDF (GET)",
    description="Exports the exact persisted resume version content to PDF without LLM alteration."
)
def export_resume_version_get(
    version_id: str,
    format: str = Query("pdf", description="Export format (pdf supported)"),
    db: Session = Depends(get_db)
):
    return _export_resume_version_impl(version_id, db)

@router.post(
    "/resume-versions/{version_id}/export",
    summary="Export Resume Version to PDF (POST)",
    description="Exports the exact persisted resume version content to PDF without LLM alteration."
)
def export_resume_version_post(
    version_id: str,
    db: Session = Depends(get_db)
):
    return _export_resume_version_impl(version_id, db)

def _export_resume_version_impl(version_id: str, db: Session):
    ver = _get_or_load_version(version_id, db)
    if not ver:
        raise HTTPException(status_code=404, detail=f"Resume version '{version_id}' not found.")

    twin = _get_or_load_twin(ver.candidate_id, db)
    candidate_name = twin.name if twin else ver.title

    pdf_bytes = _resume_builder_service.export_pdf(version=ver, candidate_name=candidate_name)
    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', ver.title)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}.pdf"'
        }
    )

@router.get(
    "/resume-versions/{candidate_id}/{version_id}",
    response_model=ResumeVersion,
    status_code=status.HTTP_200_OK,
    summary="Get Resume Version Details",
    description="Retrieves a specific resume version by ID, including structured sections and evidence IDs."
)
def get_resume_version_detail(
    candidate_id: str,
    version_id: str,
    db: Session = Depends(get_db)
) -> ResumeVersion:
    ver = _get_or_load_version(version_id, db)
    if not ver or ver.candidate_id != candidate_id:
        raise HTTPException(
            status_code=404,
            detail=f"Resume version '{version_id}' for candidate '{candidate_id}' not found."
        )
    return ver

@router.post(
    "/resume-versions/{version_id}/apply-suggestion",
    response_model=ApplySuggestionResponse,
    status_code=status.HTTP_200_OK,
    summary="Apply Accepted Suggestion with Version-Level Evidence Lock",
    description="Applies a validated suggestion to a draft resume version. Strictly enforces evidence lock before persisting."
)
def apply_suggestion_to_resume_version(
    version_id: str,
    payload: ApplySuggestionRequest,
    db: Session = Depends(get_db)
) -> ApplySuggestionResponse:
    ver = _get_or_load_version(version_id, db)
    if not ver:
        raise HTTPException(status_code=404, detail=f"Resume version '{version_id}' not found.")

    cid = payload.suggestion.candidate_id
    if cid != ver.candidate_id:
        raise HTTPException(status_code=403, detail="Candidate ID mismatch between suggestion and resume version.")

    vault = _get_or_load_vault(cid, db)
    if not vault:
        raise HTTPException(status_code=404, detail=f"Evidence Vault for candidate '{cid}' not found.")

    try:
        updated_ver, accepted_sug = _resume_builder_service.apply_suggestion_to_version(
            version=ver,
            suggestion=payload.suggestion,
            vault=vault,
            candidate_id=cid,
            create_new_version=payload.create_new_version,
            new_version_title=payload.new_version_title
        )
    except PermissionError as p_err:
        raise HTTPException(status_code=403, detail=str(p_err))
    except ValueError as v_err:
        raise HTTPException(status_code=400, detail=str(v_err))

    # Persist updated or newly branched version
    _persist_version(updated_ver, db)

    return ApplySuggestionResponse(
        success=True,
        version_id=updated_ver.version_id,
        candidate_id=cid,
        applied_suggestion=accepted_sug,
        total_accepted_in_version=len(updated_ver.accepted_suggestions),
        version=updated_ver,
        message="Suggestion successfully validated and applied to resume version."
    )

@router.post(
    "/resume-versions/{version_id}/recheck-job-fit",
    response_model=JobFitRecheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Re-check Job Fit After Changes",
    description="Compares the updated resume draft against target job requirements. Diagnostic only (no hiring prediction)."
)
def recheck_version_job_fit(
    version_id: str,
    payload: JobFitRecheckRequest,
    db: Session = Depends(get_db)
) -> JobFitRecheckResponse:
    ver = _get_or_load_version(version_id, db)
    if not ver:
        raise HTTPException(status_code=404, detail=f"Resume version '{version_id}' not found.")

    twin = _get_or_load_twin(ver.candidate_id, db)
    if not twin:
        raise HTTPException(status_code=404, detail=f"Career Twin for candidate '{ver.candidate_id}' not found.")

    vault = _get_or_load_vault(ver.candidate_id, db)
    if not vault:
        raise HTTPException(status_code=404, detail=f"Evidence Vault for candidate '{ver.candidate_id}' not found.")

    job_text = payload.job_text
    target_role = payload.target_role or ver.target_role
    company = None

    if not job_text and payload.job_id:
        repo = Repository(db)
        job_rec = repo.get_job_target(payload.job_id)
        if job_rec:
            job_text = job_rec.raw_text
            target_role = target_role or job_rec.title
            company = job_rec.company

    if not job_text:
        job_text = f"Role: {target_role or 'Software Engineer'}\nRequirements: Backend microservices, Python, Flask, API development, SQL performance."

    return _resume_builder_service.recheck_job_fit(
        version=ver,
        twin=twin,
        vault=vault,
        job_fit_service=_job_fit_service,
        job_text=job_text,
        target_role=target_role,
        company=company
    )

@router.post(
    "/resume-versions/{version_id}/clone",
    response_model=ResumeVersion,
    status_code=status.HTTP_201_CREATED,
    summary="Clone Resume Version (Rollback / Branch)",
    description="Creates a new draft version from an existing version without mutating historical versions."
)
def clone_resume_version(
    version_id: str,
    payload: Optional[CloneVersionRequest] = None,
    db: Session = Depends(get_db)
) -> ResumeVersion:
    ver = _get_or_load_version(version_id, db)
    if not ver:
        raise HTTPException(status_code=404, detail=f"Resume version '{version_id}' not found.")

    cloned = _resume_builder_service.clone_version(
        source_version=ver,
        new_title=payload.title if payload else None
    )
    _persist_version(cloned, db)
    return cloned

# ===========================================================================
# PHASE 6 — CAREER INTELLIGENCE & GAP PLANNING ENDPOINTS
# ===========================================================================

@router.post(
    "/career-targets",
    response_model=CareerTarget,
    status_code=status.HTTP_201_CREATED,
    summary="Create Career Target",
    description="Creates and persists a target role/company goal for the candidate."
)
def create_career_target(
    payload: CreateCareerTargetRequest,
    db: Session = Depends(get_db)
) -> CareerTarget:
    twin = _get_or_load_twin(payload.candidate_id, db)
    if not twin:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate '{payload.candidate_id}' not found. Please upload resume first."
        )

    vault = _get_or_load_vault(payload.candidate_id, db)
    target = _career_intelligence_service.create_target(
        candidate_id=payload.candidate_id,
        target_role=payload.target_role,
        target_company=payload.target_company,
        source_job_fit_id=payload.source_job_fit_id,
        job_description_text=payload.job_description_text,
        twin=twin,
        vault=vault,
        db=db
    )
    _persist_target(target, db)
    return target

@router.get(
    "/career-targets/{candidate_id}",
    response_model=List[CareerTargetSummary],
    status_code=status.HTTP_200_OK,
    summary="List Career Targets",
    description="Returns all career targets associated with the candidate."
)
def list_career_targets(
    candidate_id: str,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db)
) -> List[CareerTargetSummary]:
    repo = Repository(db)
    records = repo.get_career_targets_for_candidate(candidate_id, status=status_filter)
    summaries = []
    for r in records:
        reqs = json.loads(r.requirements_json) if r.requirements_json else []
        summaries.append(CareerTargetSummary(
            target_id=r.target_id,
            candidate_id=r.candidate_id,
            target_role=r.target_role,
            target_company=r.target_company,
            status=TargetStatus(r.status),
            requirements_count=len(reqs),
            created_at=r.created_at,
            updated_at=r.updated_at
        ))
    return summaries

@router.get(
    "/career-targets/{candidate_id}/{target_id}",
    response_model=CareerTarget,
    status_code=status.HTTP_200_OK,
    summary="Get Career Target Detail",
    description="Returns full details of a specific career target."
)
def get_career_target_detail(
    candidate_id: str,
    target_id: str,
    db: Session = Depends(get_db)
) -> CareerTarget:
    target = _get_or_load_target(target_id, db)
    if not target:
        raise HTTPException(status_code=404, detail=f"Career target '{target_id}' not found.")
    if target.candidate_id != candidate_id:
        raise HTTPException(
            status_code=403,
            detail=f"Security violation: Target '{target_id}' does not belong to candidate '{candidate_id}'."
        )
    return target

@router.get(
    "/career-intelligence/{candidate_id}/{target_id}",
    response_model=CareerIntelligenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Career Intelligence",
    description="Generates comprehensive career intelligence, gap breakdown, and safe action plans."
)
def get_career_intelligence(
    candidate_id: str,
    target_id: str,
    previous_coverage: Optional[float] = Query(None),
    db: Session = Depends(get_db)
) -> CareerIntelligenceResponse:
    target = _get_or_load_target(target_id, db)
    if not target:
        raise HTTPException(status_code=404, detail=f"Career target '{target_id}' not found.")
    if target.candidate_id != candidate_id:
        raise HTTPException(
            status_code=403,
            detail=f"Security violation: Target '{target_id}' does not belong to candidate '{candidate_id}'."
        )

    twin = _get_or_load_twin(candidate_id, db)
    if not twin:
        raise HTTPException(status_code=404, detail=f"Candidate twin for '{candidate_id}' not found.")

    vault = _get_or_load_vault(candidate_id, db)
    if not vault:
        raise HTTPException(status_code=404, detail=f"Evidence vault for '{candidate_id}' not found.")

    try:
        return _career_intelligence_service.analyze_target_intelligence(
            target=target,
            twin=twin,
            vault=vault,
            db=db,
            previous_coverage=previous_coverage
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Career intelligence analysis failed: {str(exc)}")

@router.post(
    "/career-intelligence/{target_id}/refresh",
    response_model=CareerIntelligenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh Career Intelligence",
    description="Re-evaluates Job Fit and career gaps with current Career Twin & Evidence Vault data."
)
def refresh_career_intelligence(
    target_id: str,
    payload: RefreshTargetRequest,
    db: Session = Depends(get_db)
) -> CareerIntelligenceResponse:
    target = _get_or_load_target(target_id, db)
    if not target:
        raise HTTPException(status_code=404, detail=f"Career target '{target_id}' not found.")
    if target.candidate_id != payload.candidate_id:
        raise HTTPException(
            status_code=403,
            detail=f"Security violation: Target '{target_id}' does not belong to candidate '{payload.candidate_id}'."
        )

    twin = _get_or_load_twin(payload.candidate_id, db)
    if not twin:
        raise HTTPException(status_code=404, detail=f"Candidate twin for '{payload.candidate_id}' not found.")

    vault = _get_or_load_vault(payload.candidate_id, db)
    if not vault:
        raise HTTPException(status_code=404, detail=f"Evidence vault for '{payload.candidate_id}' not found.")

    try:
        return _career_intelligence_service.refresh_target_intelligence(
            target=target,
            twin=twin,
            vault=vault,
            db=db,
            previous_coverage=payload.previous_coverage
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Career intelligence refresh failed: {str(exc)}")

@router.post(
    "/career-actions",
    response_model=CareerAction,
    status_code=status.HTTP_201_CREATED,
    summary="Create Career Action",
    description="Adds a specific task to the candidate's action plan."
)
def create_career_action(
    payload: CreateCareerActionRequest,
    db: Session = Depends(get_db)
) -> CareerAction:
    action_id = f"act_{uuid.uuid4().hex[:10]}"
    repo = Repository(db)
    rec = repo.save_career_action(
        action_id=action_id,
        candidate_id=payload.candidate_id,
        target_id=payload.target_id,
        requirement_id=payload.requirement_id,
        action_type=payload.action_type.value,
        title=payload.title,
        description=payload.description,
        rationale=payload.rationale,
        priority=payload.priority.value if payload.priority else "MEDIUM",
        status="TODO"
    )
    return CareerAction(
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
    )

@router.get(
    "/career-actions/{candidate_id}",
    response_model=List[CareerAction],
    status_code=status.HTTP_200_OK,
    summary="List Career Actions",
    description="Retrieves action plan items for a candidate, with optional target filtering."
)
def list_career_actions(
    candidate_id: str,
    target_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db)
) -> List[CareerAction]:
    repo = Repository(db)
    records = repo.get_career_actions_for_candidate(
        candidate_id=candidate_id,
        target_id=target_id,
        status=status_filter
    )
    actions = []
    for rec in records:
        actions.append(CareerAction(
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
    return actions

@router.post(
    "/career-actions/{action_id}/complete",
    response_model=CareerAction,
    status_code=status.HTTP_200_OK,
    summary="Complete Career Action",
    description="Marks an action as completed. Does NOT alter Evidence Vault without verified proof."
)
def complete_career_action(
    action_id: str,
    payload: ActionStatusRequest,
    db: Session = Depends(get_db)
) -> CareerAction:
    try:
        return _career_intelligence_service.complete_action(
            action_id=action_id,
            candidate_id=payload.candidate_id,
            db=db
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

@router.post(
    "/career-actions/{action_id}/dismiss",
    response_model=CareerAction,
    status_code=status.HTTP_200_OK,
    summary="Dismiss Career Action",
    description="Dismisses an action from the candidate's active plan."
)
def dismiss_career_action(
    action_id: str,
    payload: ActionStatusRequest,
    db: Session = Depends(get_db)
) -> CareerAction:
    try:
        return _career_intelligence_service.dismiss_action(
            action_id=action_id,
            candidate_id=payload.candidate_id,
            db=db
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ============================================================
# PHASE 7: INTERVIEW & APPLICATION READINESS ENDPOINTS
# ============================================================

@router.post(
    "/interview-targets",
    response_model=InterviewTarget,
    status_code=status.HTTP_201_CREATED,
    summary="Create Interview Target",
    description="Creates a persistent interview preparation target."
)
def create_interview_target(
    payload: CreateInterviewTargetRequest,
    db: Session = Depends(get_db)
) -> InterviewTarget:
    target = _interview_readiness_service.create_interview_target(
        candidate_id=payload.candidate_id,
        target_role=payload.target_role,
        target_id=payload.target_id,
        company=payload.company,
        job_description_text=payload.job_description_text,
        db=db
    )
    _persist_interview_target(target, db)
    return target


@router.get(
    "/interview-targets/{candidate_id}",
    response_model=List[InterviewTarget],
    summary="List Candidate Interview Targets",
    description="Returns all interview targets for a candidate."
)
def get_candidate_interview_targets(
    candidate_id: str,
    db: Session = Depends(get_db)
) -> List[InterviewTarget]:
    targets = _interview_readiness_service.get_interview_targets_for_candidate(candidate_id, db=db)
    for t in targets:
        _in_memory_interview_targets[t.interview_target_id] = t
    mem_targets = [t for t in _in_memory_interview_targets.values() if t.candidate_id == candidate_id]
    all_targets = {t.interview_target_id: t for t in targets + mem_targets}
    return list(all_targets.values())


@router.get(
    "/interview-targets/{candidate_id}/{target_id}",
    response_model=InterviewTarget,
    summary="Get Interview Target Detail",
    description="Returns interview target details. Enforces candidate ownership."
)
def get_interview_target_detail(
    candidate_id: str,
    target_id: str,
    db: Session = Depends(get_db)
) -> InterviewTarget:
    target = _get_or_load_interview_target(target_id, db)
    if not target:
        raise HTTPException(status_code=404, detail=f"Interview target '{target_id}' not found.")
    if target.candidate_id != candidate_id:
        raise HTTPException(status_code=403, detail="Security violation: Target does not belong to candidate.")
    return target


@router.get(
    "/interview-readiness/{candidate_id}/{target_id}",
    response_model=InterviewReadinessResponse,
    summary="Generate Interview Readiness Diagnostic",
    description="Generates preparation mapping, questions with evidence citations, and project stories."
)
def get_interview_readiness(
    candidate_id: str,
    target_id: str,
    db: Session = Depends(get_db)
) -> InterviewReadinessResponse:
    target = _get_or_load_interview_target(target_id, db)
    if not target:
        raise HTTPException(status_code=404, detail=f"Interview target '{target_id}' not found.")
    if target.candidate_id != candidate_id:
        raise HTTPException(status_code=403, detail="Security violation: Target does not belong to candidate.")

    twin = _get_or_load_twin(candidate_id, db)
    if not twin:
        raise HTTPException(status_code=404, detail=f"Career Twin for '{candidate_id}' not found.")

    vault = _get_or_load_vault(candidate_id, db)
    if not vault:
        raise HTTPException(status_code=404, detail=f"Evidence Vault for '{candidate_id}' not found.")

    try:
        return _interview_readiness_service.generate_interview_readiness(
            interview_target=target,
            twin=twin,
            vault=vault,
            db=db
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Interview readiness generation failed: {str(exc)}")


@router.post(
    "/interview-readiness/{target_id}/refresh",
    response_model=InterviewReadinessResponse,
    summary="Refresh Interview Readiness",
    description="Re-runs readiness analysis against latest Career Twin and Evidence Vault."
)
def refresh_interview_readiness(
    target_id: str,
    candidate_id: str = Query(..., description="Candidate ID"),
    db: Session = Depends(get_db)
) -> InterviewReadinessResponse:
    target = _get_or_load_interview_target(target_id, db)
    if not target:
        raise HTTPException(status_code=404, detail=f"Interview target '{target_id}' not found.")
    if target.candidate_id != candidate_id:
        raise HTTPException(status_code=403, detail="Security violation: Target does not belong to candidate.")

    twin = _get_or_load_twin(candidate_id, db)
    if not twin:
        raise HTTPException(status_code=404, detail="Career Twin not found.")
    vault = _get_or_load_vault(candidate_id, db)
    if not vault:
        raise HTTPException(status_code=404, detail="Evidence Vault not found.")

    try:
        return _interview_readiness_service.generate_interview_readiness(
            interview_target=target,
            twin=twin,
            vault=vault,
            db=db
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Readiness refresh failed: {str(exc)}")


@router.get(
    "/interview-questions/{target_id}",
    response_model=List[InterviewQuestion],
    summary="Get Interview Questions for Target",
    description="Returns evidence-grounded interview questions for target."
)
def get_interview_questions(
    target_id: str,
    candidate_id: str = Query(..., description="Candidate ID"),
    db: Session = Depends(get_db)
) -> List[InterviewQuestion]:
    target = _get_or_load_interview_target(target_id, db)
    if not target:
        raise HTTPException(status_code=404, detail=f"Interview target '{target_id}' not found.")
    if target.candidate_id != candidate_id:
        raise HTTPException(status_code=403, detail="Security violation: Target mismatch.")
    twin = _get_or_load_twin(candidate_id, db)
    vault = _get_or_load_vault(candidate_id, db)
    if not twin or not vault:
        raise HTTPException(status_code=404, detail="Candidate data not found.")
    readiness = _interview_readiness_service.generate_interview_readiness(target, twin, vault, db)
    return readiness.questions


class GenerateQuestionsRequest(BaseModel):
    candidate_id: str
    interview_target_id: str

@router.post(
    "/interview-questions/generate",
    response_model=List[InterviewQuestion],
    summary="Generate Interview Questions",
    description="Generates deterministic questions grounded in evidence."
)
def generate_interview_questions(
    payload: GenerateQuestionsRequest,
    db: Session = Depends(get_db)
) -> List[InterviewQuestion]:
    target = _get_or_load_interview_target(payload.interview_target_id, db)
    if not target:
        raise HTTPException(status_code=404, detail="Interview target not found.")
    if target.candidate_id != payload.candidate_id:
        raise HTTPException(status_code=403, detail="Security violation.")
    twin = _get_or_load_twin(payload.candidate_id, db)
    vault = _get_or_load_vault(payload.candidate_id, db)
    if not twin or not vault:
        raise HTTPException(status_code=404, detail="Candidate data not found.")
    readiness = _interview_readiness_service.generate_interview_readiness(target, twin, vault, db)
    return readiness.questions


@router.post(
    "/interview-answers/validate",
    response_model=AnswerValidationResult,
    summary="Validate Interview Answer",
    description="Validates candidate draft answer against Evidence Vault. Flags unsupported claims."
)
def validate_interview_answer(
    payload: ValidateAnswerRequest,
    db: Session = Depends(get_db)
) -> AnswerValidationResult:
    vault = _get_or_load_vault(payload.candidate_id, db)
    if not vault:
        raise HTTPException(status_code=404, detail=f"Evidence Vault for '{payload.candidate_id}' not found.")
    try:
        return _interview_readiness_service.validate_answer(
            candidate_id=payload.candidate_id,
            answer_text=payload.answer_text,
            vault=vault
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post(
    "/interview-sessions",
    response_model=InterviewSession,
    status_code=status.HTTP_201_CREATED,
    summary="Start Mock Interview Session",
    description="Initializes practice interview session with target questions."
)
def create_interview_session(
    payload: CreateInterviewSessionRequest,
    db: Session = Depends(get_db)
) -> InterviewSession:
    target = _get_or_load_interview_target(payload.interview_target_id, db)
    if not target:
        raise HTTPException(status_code=404, detail="Interview target not found.")
    if target.candidate_id != payload.candidate_id:
        raise HTTPException(status_code=403, detail="Security violation.")
    twin = _get_or_load_twin(payload.candidate_id, db)
    vault = _get_or_load_vault(payload.candidate_id, db)
    if not twin or not vault:
        raise HTTPException(status_code=404, detail="Candidate data not found.")
    readiness = _interview_readiness_service.generate_interview_readiness(target, twin, vault, db)
    sess = _interview_readiness_service.create_mock_session(
        candidate_id=payload.candidate_id,
        interview_target=target,
        questions=readiness.questions,
        db=db
    )
    _in_memory_interview_sessions[sess.session_id] = sess
    return sess


@router.post(
    "/interview-sessions/{session_id}/answer",
    response_model=InterviewSession,
    summary="Submit Session Answer",
    description="Validates candidate answer in mock interview and records progress."
)
def submit_session_answer(
    session_id: str,
    payload: SubmitSessionAnswerRequest,
    db: Session = Depends(get_db)
) -> InterviewSession:
    vault = _get_or_load_vault(payload.candidate_id, db)
    if not vault:
        raise HTTPException(status_code=404, detail="Evidence Vault not found.")
    try:
        updated_sess = _interview_readiness_service.submit_session_answer(
            session_id=session_id,
            candidate_id=payload.candidate_id,
            question_id=payload.question_id,
            answer_text=payload.answer_text,
            vault=vault,
            db=db
        )
        _in_memory_interview_sessions[session_id] = updated_sess
        return updated_sess
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/project-stories/{candidate_id}",
    response_model=List[ProjectStory],
    summary="Get Project Stories",
    description="Returns structured STAR project stories derived from verified candidate projects."
)
def get_project_stories(
    candidate_id: str,
    db: Session = Depends(get_db)
) -> List[ProjectStory]:
    twin = _get_or_load_twin(candidate_id, db)
    vault = _get_or_load_vault(candidate_id, db)
    if not twin or not vault:
        raise HTTPException(status_code=404, detail=f"Candidate data for '{candidate_id}' not found.")
    target = InterviewTarget(
        interview_target_id="temp_target",
        candidate_id=candidate_id,
        target_role="Software Engineer",
        status=InterviewTargetStatus.ACTIVE
    )
    readiness = _interview_readiness_service.generate_interview_readiness(target, twin, vault, db)
    return readiness.project_stories




