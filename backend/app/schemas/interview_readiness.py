import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from app.schemas.job_fit import GapType, RequirementStatus


class InterviewTargetStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class PreparationStatus(str, Enum):
    READY = "READY"
    REVIEW = "REVIEW"
    PREPARE = "PREPARE"
    NOT_VERIFIABLE = "NOT_VERIFIABLE"


class QuestionType(str, Enum):
    EXPERIENCE = "EXPERIENCE"
    PROJECT = "PROJECT"
    TECHNICAL = "TECHNICAL"
    BEHAVIORAL = "BEHAVIORAL"
    REQUIREMENT_DISCUSSION = "REQUIREMENT_DISCUSSION"


class ValidationVerdict(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"


class InterviewTarget(BaseModel):
    """
    Persistent interview preparation target linked to target role and optional career target.
    """
    interview_target_id: str
    candidate_id: str
    target_id: Optional[str] = None
    target_role: str
    company: Optional[str] = None
    job_fit_id: Optional[str] = None
    status: InterviewTargetStatus = InterviewTargetStatus.ACTIVE
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)


class InterviewRequirementMapItem(BaseModel):
    """
    Maps a target requirement to evidence-grounded preparation status.
    READY: Verified evidence exists.
    REVIEW: Evidence exists, but review underlying project/work.
    PREPARE: Genuine experience gap.
    NOT_VERIFIABLE: Evidence is inconclusive.
    """
    requirement_id: str
    requirement_text: str
    priority: str = "REQUIRED"
    job_fit_status: str = "MISSING"
    gap_type: Optional[str] = None
    evidence_ids: List[str] = Field(default_factory=list)
    preparation_status: PreparationStatus
    rationale: str


class EvidenceCitation(BaseModel):
    evidence_id: str
    source_text: str
    source_document: str = "Resume"
    section: Optional[str] = "Experience"
    page_number: Optional[int] = 1


class InterviewQuestion(BaseModel):
    """
    Structured interview question derived from target requirements and candidate evidence.
    Never asserts unsupported candidate claims in the question text.
    """
    question_id: str
    interview_target_id: str
    requirement_id: Optional[str] = None
    question_type: QuestionType
    question: str
    rationale: str
    evidence_ids: List[str] = Field(default_factory=list)
    citations: List[EvidenceCitation] = Field(default_factory=list)
    source_snippets: List[str] = Field(default_factory=list)
    preparation_area: str
    difficulty: str = "STANDARD"
    source: str = "EVIDENCE_VAULT"
    star_prompts: Optional[Dict[str, str]] = None
    experience_gap_note: Optional[str] = None


class ProjectStory(BaseModel):
    """
    Structured STAR story outline for an authentic candidate project from Evidence Vault.
    """
    project_id: str
    project_name: str
    evidence_ids: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)
    documented_outcomes: List[str] = Field(default_factory=list)
    likely_discussion_areas: List[str] = Field(default_factory=list)
    star_preparation_prompts: Dict[str, str] = Field(default_factory=dict)
    star_preparation: Dict[str, str] = Field(default_factory=dict)


class AnswerValidationResult(BaseModel):
    """
    Evidence-locked analysis of candidate's draft interview answer.
    Detects unsupported metrics, technologies, impact, scale, or responsibilities.
    """
    verdict: ValidationVerdict
    supported_claims: List[str] = Field(default_factory=list)
    unsupported_claims: List[str] = Field(default_factory=list)
    supported_technologies: List[str] = Field(default_factory=list)
    unsupported_technologies: List[str] = Field(default_factory=list)
    valid_evidence_ids: List[str] = Field(default_factory=list)
    evidence_ids_used: List[str] = Field(default_factory=list)
    explanation: str
    star_breakdown: Optional[Dict[str, bool]] = None
    coaching_tip: Optional[str] = None
    coaching_recommendations: List[str] = Field(default_factory=list)


class InterviewSessionItem(BaseModel):
    question_id: str
    question_text: str
    requirement_id: Optional[str] = None
    evidence_ids: List[str] = Field(default_factory=list)
    candidate_answer: Optional[str] = None
    validation_result: Optional[AnswerValidationResult] = None
    answered_at: Optional[datetime.datetime] = None


class InterviewSession(BaseModel):
    """
    Candidate-controlled practice interview session tracking questions and answers.
    Tracks preparation activity, NOT candidate hireability or intelligence score.
    """
    session_id: str
    candidate_id: str
    interview_target_id: str
    target_role: str
    status: str = "IN_PROGRESS"
    items: List[InterviewSessionItem] = Field(default_factory=list)
    questions_completed_count: int = 0
    answers_submitted_count: int = 0
    requirements_reviewed_count: int = 0
    supported_claims_count: int = 0
    unsupported_claims_count: int = 0
    requirements_covered_count: int = 0
    total_target_requirements: int = 0
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)


class InterviewReadinessResponse(BaseModel):
    """
    Comprehensive diagnostic response for interview & application readiness.
    """
    interview_target_id: str
    candidate_id: str
    target_id: Optional[str] = None
    target_role: str
    company: Optional[str] = None
    total_requirements: int = 0
    ready_count: int = 0
    review_count: int = 0
    prepare_count: int = 0
    not_verifiable_count: int = 0
    preparation_progress_metric: str = ""
    requirements_map: List[InterviewRequirementMapItem] = Field(default_factory=list)
    requirement_map: List[InterviewRequirementMapItem] = Field(default_factory=list)
    ready_to_discuss: List[InterviewRequirementMapItem] = Field(default_factory=list)
    areas_to_review: List[InterviewRequirementMapItem] = Field(default_factory=list)
    areas_to_prepare: List[InterviewRequirementMapItem] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
    interview_target: Optional[InterviewTarget] = None
    preparation_areas: List[str] = Field(default_factory=list)
    questions: List[InterviewQuestion] = Field(default_factory=list)
    project_stories: List[ProjectStory] = Field(default_factory=list)
    guardrail_notice: str = (
        "Preparation diagnostic only. Does not predict interview questions with certainty, "
        "predict hiring outcomes, or score candidate intelligence."
    )


class CreateInterviewTargetRequest(BaseModel):
    candidate_id: str
    target_role: str
    target_id: Optional[str] = None
    company: Optional[str] = None
    job_description_text: Optional[str] = None


class ValidateAnswerRequest(BaseModel):
    candidate_id: str
    question_id: str
    answer_text: str
    requirement_id: Optional[str] = None
    target_id: Optional[str] = None


class CreateInterviewSessionRequest(BaseModel):
    candidate_id: str
    interview_target_id: str


class SubmitSessionAnswerRequest(BaseModel):
    candidate_id: str
    question_id: str
    answer_text: str
