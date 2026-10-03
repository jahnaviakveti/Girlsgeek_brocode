from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.bias import JDBiasAudit

class RequirementStatus(str, Enum):
    MATCHED = "MATCHED"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"

class GapType(str, Enum):
    RESUME_VISIBILITY_GAP = "RESUME_VISIBILITY_GAP"
    EXPERIENCE_GAP = "EXPERIENCE_GAP"
    NOT_VERIFIABLE = "NOT_VERIFIABLE"

class JobFitEvidenceCitation(BaseModel):
    """
    Candidate-readable evidence citation referencing an atomic Evidence Vault item.
    """
    evidence_id: Optional[str] = None
    source_text: str
    source_section: Optional[str] = None
    page_number: Optional[int] = 1
    entity: Optional[str] = None
    matched_terms: List[str] = Field(default_factory=list)

class JobFitRequirement(BaseModel):
    """
    Evaluated job description requirement from candidate perspective.
    Every match or partial match is backed by traceable Evidence Vault citations.
    """
    requirement_id: str
    requirement_text: str
    category: str = "technical_skill"
    priority: str = "REQUIRED"  # REQUIRED or PREFERRED
    is_required: bool = True
    status: RequirementStatus
    lexical_match: bool = False
    semantic_match: bool = False
    combined_score: float = Field(..., ge=0.0, le=1.0)
    evidence: List[JobFitEvidenceCitation] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    explanation: str
    candidate_action: str
    gap_type: Optional[GapType] = None
    
    # Experience / Tenure comparison
    required_months: Optional[float] = None
    verified_months: Optional[float] = None
    tenure_gap_months: Optional[float] = None

class JobFitEvidenceGap(BaseModel):
    """
    Categorized gap distinguishing between resume visibility opportunities and genuine experience deficits.
    """
    gap_id: str
    requirement_id: str
    requirement_text: str
    gap_type: GapType
    priority: str
    missing_elements: List[str] = Field(default_factory=list)
    existing_related_evidence: List[JobFitEvidenceCitation] = Field(default_factory=list)
    explanation: str
    action_recommendation: str
    can_rewrite_resume: bool = False

class JobFitStrength(BaseModel):
    """
    Deterministic, evidence-grounded candidate strength for the target role.
    """
    strength_id: str
    title: str
    explanation: str
    evidence_ids: List[str] = Field(default_factory=list)
    supporting_evidence: List[JobFitEvidenceCitation] = Field(default_factory=list)

class JobFitImprovementOpportunity(BaseModel):
    """
    Actionable next step for improving alignment with target role.
    Includes handoff payload for the Resume Coach.
    """
    opportunity_id: str
    requirement_id: str
    requirement_text: str
    priority: str
    status: RequirementStatus
    gap_type: GapType
    current_evidence: List[JobFitEvidenceCitation] = Field(default_factory=list)
    missing_elements: List[str] = Field(default_factory=list)
    candidate_action: str
    can_improve_via_rewriting: bool = False
    handoff_payload: Dict[str, Any] = Field(default_factory=dict)

class JobFitSummary(BaseModel):
    """
    Holistic candidate-facing summary focused on evidence coverage, not arbitrary hiring predictions.
    """
    evidence_coverage_score: float = Field(..., ge=0.0, le=100.0, description="Percentage of required & preferred criteria supported by evidence")
    requirement_coverage_score: float = Field(..., ge=0.0, le=100.0, description="Weighted requirement fulfillment score")
    evidence_strength: str = Field(..., description="'Strong', 'Moderate', or 'Developing'")
    required_total: int = 0
    required_matched: int = 0
    preferred_total: int = 0
    preferred_matched: int = 0
    visibility_gaps_count: int = 0
    experience_gaps_count: int = 0
    not_verifiable_count: int = 0
    narrative: str

class JobFitAnalysis(BaseModel):
    """
    Complete candidate-facing Resume x Job Fit diagnostic model.
    Acts as the single source of truth for role alignment and resume re-writing handoff.
    """
    target_role: str
    company: Optional[str] = None
    requirements: List[JobFitRequirement] = Field(default_factory=list)
    required_requirements: List[JobFitRequirement] = Field(default_factory=list)
    preferred_requirements: List[JobFitRequirement] = Field(default_factory=list)
    matched_requirements: List[JobFitRequirement] = Field(default_factory=list)
    partial_requirements: List[JobFitRequirement] = Field(default_factory=list)
    missing_requirements: List[JobFitRequirement] = Field(default_factory=list)
    evidence_gaps: List[JobFitEvidenceGap] = Field(default_factory=list)
    strengths: List[JobFitStrength] = Field(default_factory=list)
    improvement_opportunities: List[JobFitImprovementOpportunity] = Field(default_factory=list)
    bias_warnings: Optional[JDBiasAudit] = None
    fit_summary: JobFitSummary
