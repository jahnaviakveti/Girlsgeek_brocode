from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ResumeCoachStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    NO_SAFE_REWRITE = "NO_SAFE_REWRITE"

class EvidenceCitation(BaseModel):
    evidence_id: str
    source_text: str
    source_section: Optional[str] = "Experience"
    page_number: Optional[int] = 1
    matched_terms: List[str] = Field(default_factory=list)

class ClaimValidationDetail(BaseModel):
    claim: str
    supported: bool
    confidence: float = 0.0
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    matched_facts: List[str] = Field(default_factory=list)
    explanation: str

class ResumeCoachRequest(BaseModel):
    candidate_id: str
    requirement_id: str
    requirement_text: str
    target_role: Optional[str] = None
    priority: Optional[str] = "REQUIRED"
    gap_type: Optional[str] = "RESUME_VISIBILITY_GAP"
    evidence_ids: List[str] = Field(default_factory=list)
    existing_evidence_snippets: List[str] = Field(default_factory=list)
    missing_elements: List[str] = Field(default_factory=list)
    current_resume_text: Optional[str] = None
    action_prompt: Optional[str] = None

class ResumeCoachResponse(BaseModel):
    suggestion_id: str
    candidate_id: str
    requirement_id: str
    status: ResumeCoachStatus
    original_text: str
    suggested_text: Optional[str] = None
    changes: List[str] = Field(default_factory=list)
    evidence_used: List[EvidenceCitation] = Field(default_factory=list)
    unsupported_claims: List[str] = Field(default_factory=list)
    validation: List[ClaimValidationDetail] = Field(default_factory=list)
    explanation: str
    can_rewrite: bool = True
    created_at: Optional[str] = None
