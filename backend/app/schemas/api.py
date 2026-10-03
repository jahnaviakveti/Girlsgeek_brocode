from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.explanation import CandidateExplanation
from app.schemas.bias import JDBiasAudit

class FailedCandidate(BaseModel):
    """
    Represents a resume that could not be parsed or analyzed.
    Ensures failures are explicitly visible to recruiters rather than silently dropped.
    """
    filename: str = Field(..., description="Original filename of the candidate resume")
    error: str = Field(..., description="Human-readable reason for processing failure")

class JobRequirementSummary(BaseModel):
    """
    Concise representation of an extracted JD requirement.
    """
    id: str
    requirement_text: str
    category: str
    priority: str
    extracted_keywords: List[str] = Field(default_factory=list)

class JobSummary(BaseModel):
    """
    Structured summary of the analyzed Job Description.
    """
    job_id: str
    job_title: Optional[str] = None
    total_requirements: int
    required_count: int
    preferred_count: int
    requirements: List[JobRequirementSummary] = Field(default_factory=list)
    bias_audit: Optional[JDBiasAudit] = None

class AnalysisResponse(BaseModel):
    """
    Authoritative analysis response returned by POST /api/analyze.
    Frontend consumes this strictly for rendering; all scoring and ranking is performed in backend.
    """
    job: JobSummary
    total_resumes_received: int
    total_candidates_processed: int
    total_ranked: int
    ranked_candidates: List[CandidateExplanation] = Field(default_factory=list)
    failed_candidates: List[FailedCandidate] = Field(default_factory=list)
