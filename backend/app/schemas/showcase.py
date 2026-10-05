import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ShowcaseVisibility(str, Enum):
    PRIVATE = "PRIVATE"
    SHAREABLE = "SHAREABLE"
    PUBLIC = "PUBLIC"


class ShowcaseEvidenceClaim(BaseModel):
    """
    Traceable evidence claim backing a showcase item.
    Guarantees full provenance retention without synthetic data.
    """
    claim_text: str
    evidence_id: str
    evidence_type: str = "RESPONSIBILITY"
    source_document: Optional[str] = None
    source_section: Optional[str] = None
    page_number: Optional[int] = 1
    confidence: float = 1.0
    claim_scope: str = "LEVEL 1 — TECHNOLOGY PRESENCE"


class ShowcaseSkill(BaseModel):
    name: str
    category: str = "technical_skill"
    claim_scope: str = "LEVEL 1 — TECHNOLOGY PRESENCE"
    evidence_count: int = 0
    evidence_claims: List[ShowcaseEvidenceClaim] = Field(default_factory=list)
    verified: bool = True

    @property
    def evidence_ids(self) -> List[str]:
        return [c.evidence_id for c in self.evidence_claims]

    @property
    def source_snippets(self) -> List[str]:
        return [c.claim_text for c in self.evidence_claims]


class ShowcaseExperience(BaseModel):
    title: str
    company: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    verified_responsibilities: List[str] = Field(default_factory=list)
    claim_scope: str = "LEVEL 3 — IMPLEMENTATION"
    evidence_claims: List[ShowcaseEvidenceClaim] = Field(default_factory=list)

    @property
    def organization(self) -> str:
        return self.company

    @property
    def role(self) -> str:
        return self.title

    @property
    def evidence_ids(self) -> List[str]:
        return [c.evidence_id for c in self.evidence_claims]


class ShowcaseProjectStory(BaseModel):
    """
    STAR/CAR honest structure. Never invents results or metrics.
    """
    project_name: Optional[str] = None
    context: str
    problem: str
    approach: str
    implementation: str
    result: Optional[str] = None
    learning: Optional[str] = None


class ShowcaseProject(BaseModel):
    project_id: str
    name: str
    description: Optional[str] = None
    technologies: List[str] = Field(default_factory=list)
    role: Optional[str] = None
    verified_responsibilities: List[str] = Field(default_factory=list)
    verified_outcomes: List[str] = Field(default_factory=list)
    claim_scope: str = "LEVEL 3 — IMPLEMENTATION"
    project_story: Optional[ShowcaseProjectStory] = None
    evidence_claims: List[ShowcaseEvidenceClaim] = Field(default_factory=list)
    is_featured: bool = False

    @property
    def evidence_ids(self) -> List[str]:
        return [c.evidence_id for c in self.evidence_claims]


class ShowcaseEducation(BaseModel):
    degree: str
    institution: str
    year: Optional[str] = None
    evidence_claims: List[ShowcaseEvidenceClaim] = Field(default_factory=list)

    @property
    def evidence_ids(self) -> List[str]:
        return [c.evidence_id for c in self.evidence_claims]


class ShowcaseCertification(BaseModel):
    name: str
    issuer: Optional[str] = None
    date: Optional[str] = None
    claim_scope: str = "LEVEL 2 — USAGE"
    evidence_claims: List[ShowcaseEvidenceClaim] = Field(default_factory=list)

    @property
    def evidence_ids(self) -> List[str]:
        return [c.evidence_id for c in self.evidence_claims]


class ShowcaseTargetAlignment(BaseModel):
    target_id: str
    target_role: str
    company: Optional[str] = None
    verified_strengths: List[Dict[str, Any]] = Field(default_factory=list)
    visibility_gaps: List[Dict[str, Any]] = Field(default_factory=list)
    experience_gaps: List[Dict[str, Any]] = Field(default_factory=list)
    not_verifiable_gaps: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_coverage: float = Field(0.0, ge=0.0, le=100.0)


class CareerShowcase(BaseModel):
    """
    Authoritative candidate-facing Career Showcase.
    Includes only verified data from Career Twin, Evidence Vault, and Target Alignment.
    """
    showcase_id: str
    candidate_id: str
    name: str
    headline: Optional[str] = None
    bio: Optional[str] = None
    visibility: ShowcaseVisibility = ShowcaseVisibility.PRIVATE
    share_token: Optional[str] = None
    selected_target_id: Optional[str] = None
    skills: List[ShowcaseSkill] = Field(default_factory=list)
    experience: List[ShowcaseExperience] = Field(default_factory=list)
    projects: List[ShowcaseProject] = Field(default_factory=list)
    education: List[ShowcaseEducation] = Field(default_factory=list)
    certifications: List[ShowcaseCertification] = Field(default_factory=list)
    target_alignment: Optional[ShowcaseTargetAlignment] = None
    show_provenance: bool = True
    show_target_alignment: bool = True
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    @property
    def candidate_name(self) -> str:
        return self.name

    @property
    def professional_summary(self) -> str:
        return self.bio or ""

    @property
    def verified_skills(self) -> List[ShowcaseSkill]:
        return self.skills

    @property
    def verified_experience(self) -> List[ShowcaseExperience]:
        return self.experience

    @property
    def verified_projects(self) -> List[ShowcaseProject]:
        return self.projects

    @property
    def verified_education(self) -> List[ShowcaseEducation]:
        return self.education

    @property
    def verified_certifications(self) -> List[ShowcaseCertification]:
        return self.certifications

    @property
    def project_stories(self) -> List[ShowcaseProjectStory]:
        return [p.project_story for p in self.projects if p.project_story]


class PublicCareerShowcase(BaseModel):
    """
    Sanitized public/shareable view.
    Zero leakage of internal database IDs, candidate_id, or internal diagnostics.
    """
    share_token: str
    name: str
    headline: Optional[str] = None
    bio: Optional[str] = None
    visibility: ShowcaseVisibility
    skills: List[ShowcaseSkill] = Field(default_factory=list)
    experience: List[ShowcaseExperience] = Field(default_factory=list)
    projects: List[ShowcaseProject] = Field(default_factory=list)
    education: List[ShowcaseEducation] = Field(default_factory=list)
    certifications: List[ShowcaseCertification] = Field(default_factory=list)
    target_alignment: Optional[ShowcaseTargetAlignment] = None
    show_provenance: bool = True
    generated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    @property
    def verified_skills(self) -> List[ShowcaseSkill]:
        return self.skills

    @property
    def verified_experience(self) -> List[ShowcaseExperience]:
        return self.experience

    @property
    def verified_projects(self) -> List[ShowcaseProject]:
        return self.projects

    @property
    def project_stories(self) -> List[ShowcaseProjectStory]:
        return [p.project_story for p in self.projects if p.project_story]


class UpdateShowcaseRequest(BaseModel):
    candidate_id: Optional[str] = None
    headline: Optional[str] = None
    bio: Optional[str] = None
    visibility: Optional[ShowcaseVisibility] = None
    selected_target_id: Optional[str] = None
    featured_project_ids: Optional[List[str]] = None
    featured_skill_ids: Optional[List[str]] = None
    show_provenance: Optional[bool] = None
    show_target_alignment: Optional[bool] = None


class GenerateShareTokenResponse(BaseModel):
    candidate_id: str
    share_token: str
    share_url: str
    visibility: ShowcaseVisibility


class RevokeShareTokenResponse(BaseModel):
    candidate_id: str
    revoked: bool
    visibility: ShowcaseVisibility = ShowcaseVisibility.PRIVATE
    message: str = "Share token successfully revoked. Showcase is now private."
