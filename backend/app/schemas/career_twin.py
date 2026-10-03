from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.candidate import (
    CandidateProfile,
    CandidateSkill,
    CandidateExperience,
    CandidateEducation,
    CandidateCertification,
    CandidateProject,
)
from app.schemas.domain import Evidence

class CareerTimelineEvent(BaseModel):
    """
    Chronological career milestone extracted from resume experience or education.
    """
    event_id: str
    date_display: str
    title: str
    organization: Optional[str] = None
    event_type: str = Field(..., description="'work', 'education', 'project', or 'certification'")
    description: str = ""
    is_current: bool = False
    duration_months: Optional[float] = None
    evidence_id: Optional[str] = None
    evidence_references: List[str] = Field(default_factory=list, description="Associated evidence IDs from Evidence Vault")

class CareerSkillNode(BaseModel):
    """
    Skill entity in the Career Twin graph with category, occurrences, and verified context.
    Never infers ungrounded proficiency levels like 'expert' unless explicitly supported.
    """
    name: str
    category: str = "technology"
    raw_name: Optional[str] = None
    verified_tenure_months: Optional[float] = None
    occurrence_count: int = Field(default=1, ge=1, description="Number of supporting occurrences across resume")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    related_roles: List[str] = Field(default_factory=list)
    related_projects: List[str] = Field(default_factory=list)
    evidence_id: Optional[str] = None
    evidence_references: List[str] = Field(default_factory=list, description="All supporting evidence IDs from Evidence Vault")

class CareerProjectNode(BaseModel):
    """
    Project entity in the Career Twin graph with responsibilities, metrics, and evidence references.
    """
    name: str
    description: Optional[str] = None
    technologies: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list, description="Specific tasks or bullet points performed")
    metrics: List[str] = Field(default_factory=list, description="Explicit quantifiable results achieved")
    evidence_references: List[str] = Field(default_factory=list, description="Supporting evidence IDs from Evidence Vault")

class CareerAchievementNode(BaseModel):
    """
    Quantified outcome or high-impact accomplishment extracted from resume bullets.
    """
    achievement_id: str
    headline: str
    context: str
    metric: Optional[str] = None
    evidence_id: Optional[str] = None
    evidence_references: List[str] = Field(default_factory=list, description="Supporting evidence IDs from Evidence Vault")

class CareerTwin(BaseModel):
    """
    Digital twin representing the candidate's complete, verified professional record.
    Extends and organizes CandidateProfile without fabricating new facts.
    Serves as the single source of truth for resume rewriting, job fit, and interview coaching.
    """
    twin_id: str
    candidate_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    summary: Optional[str] = None
    target_role: Optional[str] = None
    
    # Skills & Knowledge Graph
    skills: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)
    skill_nodes: List[CareerSkillNode] = Field(default_factory=list)
    
    # Core Resume Entities (preserved from CandidateProfile)
    experience: List[CandidateExperience] = Field(default_factory=list)
    education: List[CandidateEducation] = Field(default_factory=list)
    certifications: List[CandidateCertification] = Field(default_factory=list)
    projects: List[CandidateProject] = Field(default_factory=list)
    project_nodes: List[CareerProjectNode] = Field(default_factory=list)
    
    # Structured Career Insights
    timeline: List[CareerTimelineEvent] = Field(default_factory=list)
    achievements: List[CareerAchievementNode] = Field(default_factory=list)
    total_experience_months: float = 0.0
    
    # Provenance Tracking
    evidence_count: int = 0
    evidence_summary: Dict[str, int] = Field(default_factory=dict)
    raw_text: Optional[str] = None
    created_at: Optional[str] = None
    
    # Underlying domain profile
    candidate_profile: Optional[CandidateProfile] = None
