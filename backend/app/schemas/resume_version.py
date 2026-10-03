from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.resume_coach import ResumeCoachResponse, EvidenceCitation
from app.schemas.job_fit import JobFitRequirement

class ResumeVersionStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"

class ResumeSectionItem(BaseModel):
    item_id: str
    title: Optional[str] = None          # e.g., role / company or project name or degree
    subtitle: Optional[str] = None       # e.g., date range or issuer
    content: str                         # text / bullet content
    evidence_ids: List[str] = Field(default_factory=list)

class ResumeSection(BaseModel):
    section_id: str
    name: str                            # "Summary", "Skills", "Experience", "Projects", "Education", "Certifications", "Achievements"
    content: Optional[str] = None        # for unstructured or text-based sections
    items: List[ResumeSectionItem] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)

class AcceptedSuggestion(BaseModel):
    suggestion_id: str
    requirement_id: str
    target_role: Optional[str] = None
    original_text: str
    suggested_text: str
    evidence_ids: List[str] = Field(default_factory=list)
    validation_status: str = "ACCEPTED"
    what_changed: str = "Improved phrasing and conciseness"
    why_allowed: str = "Strictly verified by Evidence Vault"
    applied_at: str
    section_name: Optional[str] = None
    item_id: Optional[str] = None

class ResumeVersion(BaseModel):
    version_id: str
    candidate_id: str
    parent_version_id: Optional[str] = None
    created_at: str
    updated_at: str
    title: str
    target_role: Optional[str] = None
    source_resume_version: Optional[str] = "v1_original"
    sections: List[ResumeSection] = Field(default_factory=list)
    accepted_suggestions: List[AcceptedSuggestion] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    status: ResumeVersionStatus = ResumeVersionStatus.DRAFT
    raw_text: Optional[str] = None

class ResumeVersionSummary(BaseModel):
    version_id: str
    candidate_id: str
    parent_version_id: Optional[str] = None
    created_at: str
    updated_at: str
    title: str
    target_role: Optional[str] = None
    status: ResumeVersionStatus
    accepted_changes_count: int = 0
    evidence_ids_count: int = 0
    evidence_backed: bool = True

class CreateVersionRequest(BaseModel):
    candidate_id: str
    title: Optional[str] = None
    target_role: Optional[str] = None
    parent_version_id: Optional[str] = None

class CloneVersionRequest(BaseModel):
    title: Optional[str] = None

class ApplySuggestionRequest(BaseModel):
    suggestion: ResumeCoachResponse
    target_version_id: Optional[str] = None
    create_new_version: bool = False
    new_version_title: Optional[str] = None

class ApplySuggestionResponse(BaseModel):
    success: bool
    version_id: str
    candidate_id: str
    applied_suggestion: AcceptedSuggestion
    total_accepted_in_version: int
    version: ResumeVersion
    message: str

class ResumeDiffItem(BaseModel):
    change_id: str
    section: str
    before: str
    after: str
    why: str
    evidence: List[EvidenceCitation] = Field(default_factory=list)
    applied_at: str
    requirement_id: Optional[str] = None

class ResumeVersionDiffResponse(BaseModel):
    version_id: str
    compare_to_version_id: Optional[str] = None
    target_role: Optional[str] = None
    total_changes: int = 0
    changes: List[ResumeDiffItem] = Field(default_factory=list)

class JobFitRecheckRequest(BaseModel):
    job_id: Optional[str] = None
    job_text: Optional[str] = None
    target_role: Optional[str] = None

class JobFitRecheckResponse(BaseModel):
    version_id: str
    target_role: str
    previous_coverage: float
    current_coverage: float
    coverage_delta: float
    requirements_improved: List[JobFitRequirement] = Field(default_factory=list)
    requirements_unchanged: List[JobFitRequirement] = Field(default_factory=list)
    remaining_gaps_count: int = 0
    narrative: str
