from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.domain import (
    RequirementCategory,
    RequirementPriority,
    MatchVerdict
)
from app.schemas.scoring import ScoreBreakdown

class EvidenceReference(BaseModel):
    """
    Recruiter-readable reference to a specific piece of candidate evidence with preserved provenance.
    Does NOT contain fabricated evidence IDs.
    """
    evidence_text: str = Field(..., description="Text of the candidate evidence")
    evidence_type: str = Field(..., description="Recruiter-friendly type (e.g. Work Experience, Technical Skill, Project, Education, Certification)")
    source_section: Optional[str] = Field(default=None, description="Resume section where evidence was found")
    page_number: Optional[int] = Field(default=None, description="Page number of evidence if available")
    source_text: Optional[str] = Field(default=None, description="Exact snippet from source document")
    match_method: Optional[str] = Field(default=None, description="EXACT, ALIAS, FUZZY, or SEMANTIC_CONCEPTUAL")
    lexical_score: Optional[float] = Field(default=None, description="Lexical match score if matched lexically")
    semantic_score: Optional[float] = Field(default=None, description="Cosine similarity if matched semantically")

class RequirementExplanation(BaseModel):
    """
    Human-readable explanation of how a specific JD requirement was evaluated for a candidate.
    Every claim is strictly derived from structured evidence.
    """
    requirement_id: str
    requirement_text: str
    category: RequirementCategory
    priority: RequirementPriority
    is_required: bool
    verdict: MatchVerdict
    requirement_score: float = Field(..., ge=0.0, le=1.0, description="Normalized requirement score [0.0, 1.0]")
    contribution_to_score: float = Field(default=0.0, description="Points contributed to overall candidate score (0-100 scale)")
    explanation: str = Field(..., description="Deterministic, evidence-backed natural language explanation")
    supporting_evidence: List[EvidenceReference] = Field(default_factory=list)

class CandidateExplanation(BaseModel):
    """
    Comprehensive, recruiter-readable explanation for a candidate's ranking position.
    Tailored with deep detail for top-3 candidates and concise structure for all candidates.
    """
    candidate_id: str
    candidate_name: Optional[str] = None
    rank: int
    overall_score: float
    is_top_3: bool = False
    
    # Executive narrative sections
    why_ranked_here: str = Field(..., description="Concise explanation of candidate's rank based on score structure")
    summary: str = Field(..., description="High-level evaluation summary")
    strengths: List[str] = Field(default_factory=list, description="Key evidence-backed strengths")
    
    # Requirement groups
    matched_requirements: List[RequirementExplanation] = Field(default_factory=list)
    partial_requirements: List[RequirementExplanation] = Field(default_factory=list)
    missing_required_requirements: List[RequirementExplanation] = Field(default_factory=list)
    missing_preferred_requirements: List[RequirementExplanation] = Field(default_factory=list)
    
    # Traceable score structure
    score_breakdown: ScoreBreakdown
    all_evidence: List[EvidenceReference] = Field(default_factory=list, description="Deduplicated list of supporting evidence references")
