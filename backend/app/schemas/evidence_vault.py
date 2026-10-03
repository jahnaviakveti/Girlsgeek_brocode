import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field

class EvidenceType(str, Enum):
    """
    Controlled vocabulary for evidence classification in the Evidence Vault.
    Guarantees consistent categorization across parsing, retrieval, and validation.
    """
    SKILL = "SKILL"
    EXPERIENCE = "EXPERIENCE"
    PROJECT = "PROJECT"
    EDUCATION = "EDUCATION"
    CERTIFICATION = "CERTIFICATION"
    ACHIEVEMENT = "ACHIEVEMENT"
    METRIC = "METRIC"
    TECHNOLOGY = "TECHNOLOGY"
    ROLE = "ROLE"
    DATE = "DATE"
    RESPONSIBILITY = "RESPONSIBILITY"
    SUMMARY = "SUMMARY"

class VaultEvidenceItem(BaseModel):
    """
    Standardized atomic fact or verbatim excerpt from the candidate's resume with strict provenance.
    Acts as the immutable building block for Career Twin claims and AI reasoning.
    """
    evidence_id: str = Field(..., description="Unique deterministic identifier e.g. ev_1a2b3c4d5e6f")
    candidate_id: str
    source_text: str = Field(..., description="Verbatim text from source document")
    normalized_facts: List[str] = Field(default_factory=list, description="Extracted atomic facts directly supported by the text")
    source_document: Optional[str] = Field(default=None, description="Filename or source document identifier")
    source_section: Optional[str] = Field(default=None, description="Resume section heading where evidence occurred")
    page_number: Optional[int] = Field(default=1, description="1-indexed page number in the original PDF")
    evidence_type: str = Field(..., description="Controlled vocabulary evidence type (e.g. SKILL, EXPERIENCE, etc.)")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    
    # Graph relationships
    related_entity: Optional[str] = Field(default=None, description="Primary entity name (e.g. company, degree, project)")
    related_skill: Optional[str] = Field(default=None, description="Associated skill/technology")
    related_project: Optional[str] = Field(default=None, description="Associated project name")
    related_experience: Optional[str] = Field(default=None, description="Associated employer or role")
    related_technologies: List[str] = Field(default_factory=list, description="Technologies directly mentioned")
    
    created_at: Optional[str] = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)

class EvidenceSummary(BaseModel):
    """
    High-level aggregate distribution of evidence across categories.
    """
    total: int = 0
    skills: int = 0
    projects: int = 0
    experience: int = 0
    education: int = 0
    certifications: int = 0
    achievements: int = 0
    metrics: int = 0
    by_type: Dict[str, int] = Field(default_factory=dict)

class ClaimValidationResult(BaseModel):
    """
    Result of evaluating whether a candidate claim or statement is grounded in the Evidence Vault.
    Guarantees no ungrounded facts or hallucinations pass verification.
    """
    claim: str
    supported: bool
    confidence: float = 0.0
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    supporting_evidence: List[VaultEvidenceItem] = Field(default_factory=list)
    matched_facts: List[str] = Field(default_factory=list)
    explanation: str

class EvidenceVault(BaseModel):
    """
    Repository of all verified candidate evidence items with fast inverted lookup indices.
    Serves as the single source of truth for the Career Twin and future coaches.
    """
    vault_id: str
    candidate_id: str
    total_items: int = 0
    items: List[VaultEvidenceItem] = Field(default_factory=list)
    summary: EvidenceSummary = Field(default_factory=EvidenceSummary)
    
    # Inverted Lookup Indices
    section_index: Dict[str, List[str]] = Field(default_factory=dict, description="Section name -> list of evidence_ids")
    technology_index: Dict[str, List[str]] = Field(default_factory=dict, description="Normalized tech -> list of evidence_ids")
    type_index: Dict[str, List[str]] = Field(default_factory=dict, description="Evidence type -> list of evidence_ids")
    skill_index: Dict[str, List[str]] = Field(default_factory=dict, description="Skill name -> list of evidence_ids")
    project_index: Dict[str, List[str]] = Field(default_factory=dict, description="Project name -> list of evidence_ids")
    experience_index: Dict[str, List[str]] = Field(default_factory=dict, description="Role/Company -> list of evidence_ids")
