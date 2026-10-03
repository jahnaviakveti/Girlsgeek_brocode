from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.domain import (
    RequirementCategory,
    RequirementPriority,
    MatchVerdict,
    Evidence,
    RequirementMatch,
    CandidateScore,
    CandidateRanking
)
from app.schemas.keyword_matching import KeywordMatchResult
from app.schemas.semantic_matching import SemanticMatchResult

class RequirementEvaluationResult(BaseModel):
    """
    Detailed requirement-level evaluation combining lexical and semantic evidence.
    """
    requirement_id: str
    requirement_text: str
    category: RequirementCategory
    priority: RequirementPriority
    is_required: bool
    verdict: MatchVerdict
    hybrid_score: float = Field(..., ge=0.0, le=1.0, description="Normalized requirement score [0.0, 1.0]")
    
    # Component Signals
    strongest_lexical: Optional[KeywordMatchResult] = None
    strongest_semantic: Optional[SemanticMatchResult] = None
    all_lexical_matches: List[KeywordMatchResult] = Field(default_factory=list)
    all_semantic_matches: List[SemanticMatchResult] = Field(default_factory=list)
    
    # Experience Verification
    required_years: Optional[float] = None
    candidate_years: Optional[float] = None
    experience_satisfied: Optional[bool] = None
    
    # Evaluation Rationale & Provenance
    rationale: str = Field(default="", description="Structured explanation of how score and verdict were reached")
    is_aspirational_or_negated: bool = False
    evidence: Optional[Evidence] = None

    def to_requirement_match(self, candidate_id: str) -> RequirementMatch:
        """Converts to the existing domain RequirementMatch contract."""
        lex_score = self.strongest_lexical.lexical_score if self.strongest_lexical else 0.0
        sem_score = self.strongest_semantic.similarity_score if self.strongest_semantic else 0.0
        return RequirementMatch(
            candidate_id=candidate_id,
            requirement_id=self.requirement_id,
            keyword_match_score=float(lex_score),
            semantic_match_score=float(sem_score),
            verdict=self.verdict,
            evidence=self.evidence
        )

class ScoreBreakdown(BaseModel):
    """
    Traceable breakdown of how a candidate's final score was computed.
    Supports downstream UI, explainability, and future robustness audits.
    """
    overall_score: float = Field(..., ge=0.0, le=100.0)
    required_score: float = Field(default=0.0, ge=0.0, le=100.0)
    preferred_score: float = Field(default=0.0, ge=0.0, le=100.0)
    keyword_contribution: float = Field(default=0.0, description="Lexical signal contribution across requirements")
    semantic_contribution: float = Field(default=0.0, description="Semantic signal contribution across requirements")
    category_scores: Dict[str, float] = Field(default_factory=dict, description="Score breakdown by requirement category")
    total_requirements: int = 0
    matched_count: int = 0
    partial_count: int = 0
    missing_count: int = 0
    required_matched_count: int = 0
    required_total_count: int = 0

class CandidateRankingResult(BaseModel):
    """
    Comprehensive ranking result for a candidate against a job description.
    """
    rank: int
    candidate_id: str
    candidate_name: Optional[str] = None
    score: CandidateScore
    score_breakdown: ScoreBreakdown
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    evaluations: List[RequirementEvaluationResult] = Field(default_factory=list)
    explanation: Optional[str] = None

    def to_candidate_ranking(self) -> CandidateRanking:
        """Converts to the existing domain CandidateRanking contract."""
        return CandidateRanking(
            rank=self.rank,
            candidate_id=self.candidate_id,
            score=self.score,
            matched_skills=self.matched_skills,
            missing_skills=self.missing_skills,
            explanation=self.explanation
        )
