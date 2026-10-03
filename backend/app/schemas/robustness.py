from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class PerturbationType(str, Enum):
    LEXICAL_NORMALIZATION = "lexical_normalization"
    KEYWORD_MASKING = "keyword_masking"
    FORMATTING_NORMALIZATION = "formatting_normalization"

class RobustnessClassification(str, Enum):
    ROBUST = "ROBUST"
    MODERATELY_SENSITIVE = "MODERATELY_SENSITIVE"
    HIGHLY_SENSITIVE = "HIGHLY_SENSITIVE"

class CandidateAuditEntry(BaseModel):
    candidate_id: str
    candidate_name: str
    baseline_rank: int
    baseline_score: float
    perturbed_rank: int
    perturbed_score: float
    absolute_rank_displacement: int
    signed_rank_displacement: int
    score_delta: float

class AuditCaseProvenance(BaseModel):
    candidate_id: str
    candidate_name: str
    perturbation_type: PerturbationType
    requirement_id: Optional[str] = None
    requirement_text: Optional[str] = None
    original_text: str
    transformed_text: str
    transformation_reason: str
    baseline_rank: int
    perturbed_rank: int
    rank_displacement: int

class PerturbationRunResult(BaseModel):
    perturbation_type: PerturbationType
    description: str
    total_candidates: int
    perturbed_rankings: List[CandidateAuditEntry]
    top3_overlap: float
    top5_overlap: float
    rank_correlation: float  # Spearman's rho [-1.0, 1.0]
    average_absolute_rank_displacement: float
    max_absolute_rank_displacement: int
    pairwise_ranking_flips: int
    keyword_dependence_indicator: Optional[float] = None  # 0.0 (independent) to 1.0 (purely lexical)
    provenance_cases: List[AuditCaseProvenance] = Field(default_factory=list)

class RankingRobustnessAudit(BaseModel):
    audit_id: str
    timestamp: str
    candidate_count: int
    job_title: str
    baseline_ranking: List[CandidateAuditEntry]
    perturbation_runs: List[PerturbationRunResult]
    overall_top3_overlap: float
    overall_top5_overlap: float
    overall_rank_correlation: float
    overall_average_rank_displacement: float
    overall_max_rank_displacement: int
    total_pairwise_flips: int
    keyword_dependence_indicator: float
    robustness_status: RobustnessClassification
    status_interpretation_note: str
    limitations: List[str]
    audit_cases: List[AuditCaseProvenance]
