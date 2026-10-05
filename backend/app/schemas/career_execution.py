import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from app.schemas.career_intelligence import ActionType, GapPriority


class ExecutionStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    AWAITING_EVIDENCE = "AWAITING_EVIDENCE"
    COMPLETED = "COMPLETED"


class ProgressState(str, Enum):
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    SELF_REPORTED_COMPLETE = "SELF_REPORTED_COMPLETE"
    EVIDENCE_SUBMITTED = "EVIDENCE_SUBMITTED"
    VERIFIED = "VERIFIED"


class ArtifactType(str, Enum):
    GITHUB_REPO = "GITHUB_REPO"
    PROJECT_REPORT = "PROJECT_REPORT"
    DEPLOYED_PROJECT = "DEPLOYED_PROJECT"
    CERTIFICATE = "CERTIFICATE"
    TECHNICAL_DOCUMENT = "TECHNICAL_DOCUMENT"
    PRESENTATION = "PRESENTATION"
    RESEARCH_PAPER = "RESEARCH_PAPER"
    INTERNSHIP_WORK = "INTERNSHIP_WORK"
    COURSE_COMPLETION = "COURSE_COMPLETION"
    PORTFOLIO_ARTIFACT = "PORTFOLIO_ARTIFACT"
    OTHER = "OTHER"


class ArtifactReference(BaseModel):
    artifact_id: str
    name: str
    artifact_type: ArtifactType
    url_or_path: str
    description: str
    technologies: List[str] = Field(default_factory=list)
    submitted_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)


class ExecutionNote(BaseModel):
    note_id: str
    content: str
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)


class CareerExecution(BaseModel):
    execution_id: str
    candidate_id: str
    action_id: str
    target_id: str
    title: Optional[str] = None
    status: ExecutionStatus = ExecutionStatus.NOT_STARTED
    progress_state: ProgressState = ProgressState.PLANNED
    progress_percent: int = Field(default=0, ge=0, le=100)
    started_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None
    notes: List[ExecutionNote] = Field(default_factory=list)
    blocker_reason: Optional[str] = None
    next_step: Optional[str] = None
    artifact_references: List[ArtifactReference] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    claim_scope: Optional[str] = None
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)


class EvidenceClaimSubmission(BaseModel):
    claim_text: str
    source_snippet: str
    evidence_type: str = "PROJECT"
    source_document: Optional[str] = None
    source_section: Optional[str] = None
    related_technologies: List[str] = Field(default_factory=list)
    related_skill: Optional[str] = None
    claimed_scope: Optional[str] = None


class EvidenceVerificationResult(BaseModel):
    verified: bool
    execution_id: str
    evidence_ids: List[str] = Field(default_factory=list)
    verified_count: int = 0
    claim_scope: Optional[str] = None
    provenance: List[Dict[str, Any]] = Field(default_factory=list)
    rejection_reason: Optional[str] = None
    explanation: str
    before_state: Optional[Dict[str, Any]] = None
    after_state: Optional[Dict[str, Any]] = None


class RequirementProgressItem(BaseModel):
    requirement_id: str
    requirement_text: str
    current_state: str  # MATCHED, PARTIAL, MISSING, NOT_VERIFIABLE
    gap_type: Optional[str] = None
    claim_scope: str
    evidence_count: int = 0
    related_actions: List[Any] = Field(default_factory=list)
    latest_verified_evidence: Optional[Dict[str, Any]] = None
    latest_evidence_snippet: Optional[str] = None
    last_updated: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)


class TimelineEventType(str, Enum):
    TARGET_CREATED = "TARGET_CREATED"
    ACTION_STARTED = "ACTION_STARTED"
    PROGRESS_UPDATED = "PROGRESS_UPDATED"
    BLOCKER_RECORDED = "BLOCKER_RECORDED"
    ARTIFACT_SUBMITTED = "ARTIFACT_SUBMITTED"
    SELF_REPORTED_COMPLETE = "SELF_REPORTED_COMPLETE"
    ACTION_COMPLETED = "ACTION_COMPLETED"
    EVIDENCE_VERIFIED = "EVIDENCE_VERIFIED"
    CAREER_TWIN_REFRESHED = "CAREER_TWIN_REFRESHED"
    JOB_FIT_REFRESHED = "JOB_FIT_REFRESHED"
    REQUIREMENT_STATE_CHANGED = "REQUIREMENT_STATE_CHANGED"


class TimelineEvent(BaseModel):
    event_id: str
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    event_type: TimelineEventType
    description: str
    evidence_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TargetRequirementDelta(BaseModel):
    requirement_id: str
    requirement_text: str
    previous_classification: str
    new_classification: str
    previous_claim_scope: Optional[str] = None
    new_claim_scope: Optional[str] = None
    previous_scope: Optional[str] = None
    new_scope: Optional[str] = None
    reason: str
    supporting_evidence_ids: List[str] = Field(default_factory=list)


class TargetProgressComparison(BaseModel):
    target_id: str
    candidate_id: str
    target_role: str
    target_company: Optional[str] = None
    before_summary: Dict[str, Any]
    after_summary: Dict[str, Any]
    before_matched: int = 0
    before_partial: int = 0
    before_missing: int = 0
    before_visibility_gaps: int = 0
    before_experience_gaps: int = 0
    before_not_verifiable: int = 0
    after_matched: int = 0
    after_partial: int = 0
    after_missing: int = 0
    after_visibility_gaps: int = 0
    after_experience_gaps: int = 0
    after_not_verifiable: int = 0
    delta: List[TargetRequirementDelta] = Field(default_factory=list)
    deltas: List[TargetRequirementDelta] = Field(default_factory=list)
    requirement_progress: List[RequirementProgressItem] = Field(default_factory=list)
    requirements: List[RequirementProgressItem] = Field(default_factory=list)
    timeline: List[TimelineEvent] = Field(default_factory=list)


# Request schemas
class CreateCareerExecutionRequest(BaseModel):
    candidate_id: str
    action_id: str
    target_id: str
    title: Optional[str] = None
    notes: Optional[str] = None


class StartExecutionRequest(BaseModel):
    candidate_id: str


class UpdateExecutionProgressRequest(BaseModel):
    candidate_id: str
    progress_percent: int = Field(ge=0, le=100)
    notes: Optional[str] = None
    note: Optional[str] = None
    next_step: Optional[str] = None


class SubmitArtifactRequest(BaseModel):
    candidate_id: str
    name: Optional[str] = None
    title: Optional[str] = None
    artifact_type: Optional[ArtifactType] = None
    url_or_path: Optional[str] = None
    uri: Optional[str] = None
    description: Optional[str] = None
    technologies: Optional[List[str]] = Field(default_factory=list)
    artifact: Optional[Dict[str, Any]] = None


class CompleteExecutionRequest(BaseModel):
    candidate_id: str
    notes: Optional[str] = None
    final_notes: Optional[str] = None


class BlockExecutionRequest(BaseModel):
    candidate_id: str
    blocker_reason: str
    next_step: Optional[str] = None


class VerifyEvidenceRequest(BaseModel):
    candidate_id: str
    artifact_id: Optional[str] = None
    confirm_genuine: Optional[bool] = None
    evidence_claims: List[EvidenceClaimSubmission] = Field(default_factory=list)
