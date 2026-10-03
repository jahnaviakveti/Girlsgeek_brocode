from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.career_twin import CareerTwin
from app.schemas.evidence_vault import EvidenceVault, VaultEvidenceItem
from app.schemas.scoring import ScoreBreakdown
from app.schemas.explanation import RequirementExplanation, EvidenceReference
from app.schemas.bias import JDBiasAudit
from app.schemas.job_fit import JobFitAnalysis

class ResumeUploadResponse(BaseModel):
    """
    Response returned when a single candidate resume is ingested into the coaching engine.
    """
    candidate_id: str
    filename: str
    career_twin: CareerTwin
    evidence_vault: EvidenceVault
    evidence_summary: Dict[str, int] = Field(default_factory=dict, description="Distribution of evidence counts")
    ats_quick_score: float = Field(default=95.0, description="Baseline readability and parsing score")
    summary: str

class JobFitAnalysisRequest(BaseModel):
    """
    Request payload to evaluate job fit for an already loaded candidate.
    """
    candidate_id: str
    target_role_title: Optional[str] = None
    jd_text: Optional[str] = None

class JobFitAnalysisResponse(BaseModel):
    """
    Candidate-focused Job Fit analysis response.
    """
    candidate_id: str
    job_title: str
    fit_score: float = Field(..., ge=0.0, le=100.0)
    required_fit_score: float = 0.0
    preferred_fit_score: float = 0.0
    score_breakdown: ScoreBreakdown
    
    # Requirement Evaluations
    matched_requirements: List[RequirementExplanation] = Field(default_factory=list)
    partial_requirements: List[RequirementExplanation] = Field(default_factory=list)
    missing_required: List[RequirementExplanation] = Field(default_factory=list)
    missing_preferred: List[RequirementExplanation] = Field(default_factory=list)
    
    # Actionable Coaching Feedback
    coaching_summary: str
    top_strengths: List[str] = Field(default_factory=list)
    critical_gaps: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    
    # Detailed Candidate-Facing Diagnostic
    evidence_coverage: float = Field(default=0.0, description="Evidence Coverage percentage")
    job_fit_analysis: Optional['JobFitAnalysis'] = Field(default=None, description="Detailed candidate-centric JobFitAnalysis")
    
    # JD Inclusivity Warnings (Alerting candidate to unrealistic or biased JDs)
    bias_audit: Optional[JDBiasAudit] = None

class CareerTwinQueryRequest(BaseModel):
    candidate_id: str

class CareerTwinQueryResponse(BaseModel):
    career_twin: CareerTwin
    evidence_vault: Optional[EvidenceVault] = None
    evidence_summary: Dict[str, int] = Field(default_factory=dict, description="Summary count of evidence items")

class EvidenceQueryResponse(BaseModel):
    """
    Response for candidate-facing Evidence Vault querying and filtering.
    """
    candidate_id: str
    total: int
    filters_applied: Dict[str, Any] = Field(default_factory=dict)
    evidence: List[VaultEvidenceItem] = Field(default_factory=list)

# Re-export Phase 4 Resume Coach models
from app.schemas.resume_coach import (
    ResumeCoachRequest,
    ResumeCoachResponse,
    ResumeCoachStatus,
    ClaimValidationDetail,
    EvidenceCitation,
)

