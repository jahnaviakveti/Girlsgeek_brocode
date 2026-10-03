import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from app.schemas.job_fit import GapType, RequirementStatus


class TargetStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class GapPriority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ActionType(str, Enum):
    RESUME_IMPROVEMENT = "RESUME_IMPROVEMENT"
    DOCUMENT_EVIDENCE = "DOCUMENT_EVIDENCE"
    LEARN_SKILL = "LEARN_SKILL"
    BUILD_PROJECT = "BUILD_PROJECT"
    GAIN_EXPERIENCE = "GAIN_EXPERIENCE"
    REVIEW_REQUIREMENT = "REVIEW_REQUIREMENT"


class ActionStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    DISMISSED = "DISMISSED"


class CareerTarget(BaseModel):
    """
    Persistent candidate career goal / target role.
    Multiple targets supported, with explicit active/archived state.
    """
    target_id: str
    candidate_id: str
    target_role: str
    target_company: Optional[str] = None
    source_job_fit_id: Optional[str] = None
    status: TargetStatus = TargetStatus.ACTIVE
    raw_jd_text: Optional[str] = None
    requirements: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)


class CareerTargetSummary(BaseModel):
    """
    Lightweight summary for target list views.
    """
    target_id: str
    candidate_id: str
    target_role: str
    target_company: Optional[str] = None
    status: TargetStatus
    requirements_count: int = 0
    created_at: datetime.datetime
    updated_at: datetime.datetime


class CareerStrength(BaseModel):
    """
    Verified strength grounded in candidate's Evidence Vault.
    """
    requirement_id: str
    requirement_text: str
    category: str = "technical_skill"
    evidence_ids: List[str] = Field(default_factory=list)
    explanation: str
    source_snippets: List[str] = Field(default_factory=list)


class RequirementGap(BaseModel):
    """
    Structured representation of a role gap classified into:
    - RESUME_VISIBILITY_GAP (evidence exists, needs surfacing)
    - EXPERIENCE_GAP (genuine experience missing, needs projects/learning)
    - NOT_VERIFIABLE (insufficient evidence in vault)
    """
    gap_id: str
    candidate_id: str
    target_id: str
    requirement_id: str
    requirement_text: str
    category: str = "technical_skill"
    priority: GapPriority = GapPriority.MEDIUM
    priority_rationale: str
    current_status: str  # MATCHED, PARTIAL, MISSING
    gap_type: GapType
    evidence_ids: List[str] = Field(default_factory=list)
    explanation: str
    recommended_actions: List[str] = Field(default_factory=list)
    can_rewrite_resume: bool = False
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)


class CareerAction(BaseModel):
    """
    Concrete learning, experience, or resume improvement task.
    Completing an action DOES NOT automatically grant skills without verified evidence.
    """
    action_id: str
    candidate_id: str
    target_id: str
    requirement_id: str
    action_type: ActionType
    title: str
    description: str
    rationale: str
    priority: GapPriority = GapPriority.MEDIUM
    status: ActionStatus = ActionStatus.TODO
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    completed_at: Optional[datetime.datetime] = None


class ProgressSummary(BaseModel):
    """
    Target-level diagnostic progress tracking.
    Never framed as hiring prediction or probability.
    """
    total_requirements: int = 0
    matched: int = 0
    partial: int = 0
    missing: int = 0
    not_verifiable: int = 0
    evidence_coverage: float = Field(0.0, ge=0.0, le=100.0)
    visibility_gaps: int = 0
    experience_gaps: int = 0
    previous_evidence_coverage: Optional[float] = None
    coverage_delta: Optional[float] = None
    improved_requirements: List[str] = Field(default_factory=list)
    unchanged_requirements: List[str] = Field(default_factory=list)
    narrative: str


class CareerIntelligenceResponse(BaseModel):
    """
    Candidate-facing Career Intelligence diagnostic response.
    Answers: 'What should I work on next to become better aligned with target roles?'
    """
    target_id: str
    candidate_id: str
    target_role: str
    target_company: Optional[str] = None
    status: TargetStatus = TargetStatus.ACTIVE

    strengths: List[CareerStrength] = Field(default_factory=list)
    visibility_gaps: List[RequirementGap] = Field(default_factory=list)
    experience_gaps: List[RequirementGap] = Field(default_factory=list)
    not_verifiable_gaps: List[RequirementGap] = Field(default_factory=list)

    evidence_coverage: float = Field(0.0, ge=0.0, le=100.0)
    requirement_summary: Dict[str, int] = Field(default_factory=dict)
    recommended_next_actions: List[CareerAction] = Field(default_factory=list)
    progress_summary: ProgressSummary


class CreateCareerTargetRequest(BaseModel):
    candidate_id: str
    target_role: str
    target_company: Optional[str] = None
    source_job_fit_id: Optional[str] = None
    job_description_text: Optional[str] = None


class CreateCareerActionRequest(BaseModel):
    candidate_id: str
    target_id: str
    requirement_id: str
    action_type: ActionType
    title: str
    description: str
    rationale: str
    priority: Optional[GapPriority] = GapPriority.MEDIUM
