from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class BiasSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class BiasCategory(str, Enum):
    GENDER_CODED = "gender_coded"
    PEDIGREE_DEGREE = "pedigree_degree"
    UNREALISTIC_EXPERIENCE = "unrealistic_experience"
    AGE_GENERATIONAL = "age_generational"
    ABLEIST_PHYSICAL = "ableist_physical"

class BiasFlag(BaseModel):
    """
    Represents an isolated phrasing issue or bias flag detected in the Job Description.
    """
    id: str = Field(..., description="Unique identifier for the flag")
    category: BiasCategory = Field(..., description="Category of exclusionary phrasing or bias")
    severity: BiasSeverity = Field(..., description="Severity level of the exclusionary impact")
    matched_text: str = Field(..., description="Exact phrasing or term flagged from the JD")
    context_snippet: str = Field(..., description="Surrounding sentence or clause for recruiter context")
    explanation: str = Field(..., description="Explanation of why this phrasing unfairly excludes qualified candidates")
    inclusive_alternative: str = Field(..., description="Recommended inclusive alternative phrasing")

class JDBiasAudit(BaseModel):
    """
    Comprehensive bias and inclusivity audit for a Job Description (Bonus Task 1).
    """
    inclusivity_score: int = Field(..., ge=0, le=100, description="Overall inclusivity score from 0 to 100")
    inclusivity_grade: str = Field(..., description="Letter grade: A+, A, B, C, or D")
    total_flags: int = Field(default=0, description="Total number of exclusionary phrasing flags detected")
    flags: List[BiasFlag] = Field(default_factory=list, description="Detailed list of detected bias flags")
    summary: str = Field(..., description="Executive summary of the JD inclusivity audit")
    bias_free: bool = Field(default=True, description="True if no high/medium bias flags were detected")
