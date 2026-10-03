from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class RequirementCategory(str, Enum):
    SKILL = "skill"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    DOMAIN = "domain"
    CERTIFICATION = "certification"
    OTHER = "other"

class RequirementPriority(str, Enum):
    REQUIRED = "required"
    PREFERRED = "preferred"

class MatchVerdict(str, Enum):
    MATCHED = "matched"
    PARTIAL = "partial"
    MISSING = "missing"

class JDRequirement(BaseModel):
    id: str
    requirement_text: str
    category: RequirementCategory = RequirementCategory.SKILL
    priority: RequirementPriority = RequirementPriority.REQUIRED
    extracted_keywords: List[str] = Field(default_factory=list)

    # Source Provenance
    source_text: Optional[str] = None
    page_number: Optional[int] = None
    source_section: Optional[str] = None

    # Logical Relationships (OR / AND)
    logical_operator: Optional[str] = None  # e.g., "OR", "AND"
    alternatives: List[str] = Field(default_factory=list)
    is_alternative: bool = False

    # Structured Experience Attributes
    min_years: Optional[float] = None
    max_years: Optional[float] = None
    experience_domain: Optional[str] = None

    # Semantic Signals
    is_negated: bool = False
    extraction_confidence: float = Field(
        default=1.0, 
        description="Confidence that the JD analyzer correctly interpreted/extracted this requirement from the JD text (NOT candidate match confidence)."
    )

    def __init__(self, **data: Any):
        # Support 'confidence' parameter for backwards compatibility
        if "confidence" in data and "extraction_confidence" not in data:
            data["extraction_confidence"] = data.pop("confidence")
        super().__init__(**data)

    @property
    def confidence(self) -> float:
        """Backwards compatibility alias: returns extraction_confidence."""
        return self.extraction_confidence

    @property
    def is_required(self) -> bool:
        return self.priority == RequirementPriority.REQUIRED and not self.is_negated

class JobDescription(BaseModel):
    jd_id: str
    raw_text: str
    title: Optional[str] = None
    normalized_text: Optional[str] = None
    document_id: Optional[str] = None
    requirements: List[JDRequirement] = Field(default_factory=list)

class ResumeDocument(BaseModel):
    candidate_id: str
    raw_text: str
    sections: Dict[str, str] = Field(
        default_factory=dict, 
        description="Parsed sections e.g., 'skills', 'experience', 'projects', 'education'"
    )

class Evidence(BaseModel):
    source_text: str
    source_section: Optional[str] = None
    confidence_score: float
    page_number: Optional[int] = None
    evidence_type: Optional[str] = None

from app.schemas.candidate import CandidateProfile

class RequirementMatch(BaseModel):
    candidate_id: str
    requirement_id: str
    keyword_match_score: float = 0.0
    semantic_match_score: float = 0.0
    verdict: MatchVerdict = MatchVerdict.MISSING
    evidence: Optional[Evidence] = None

class CandidateScore(BaseModel):
    candidate_id: str
    overall_score: float
    required_score: float = 0.0
    preferred_score: float = 0.0
    semantic_score: float = 0.0
    keyword_score: float = 0.0
    experience_score: float = 0.0
    qualification_score: float = 0.0
    penalty_applied: float = 0.0

class CandidateRanking(BaseModel):
    rank: int
    candidate_id: str
    score: CandidateScore
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    explanation: Optional[str] = None
