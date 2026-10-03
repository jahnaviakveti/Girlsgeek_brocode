from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from app.schemas.domain import Evidence, ResumeDocument

class CandidateSkill(BaseModel):
    """
    Extracted candidate skill with canonical name and source evidence.
    """
    name: str = Field(..., description="Canonical or extracted name of the skill/technology")
    raw_name: str = Field(..., description="Original extracted token from the resume")
    category: Optional[str] = Field(default=None, description="e.g. language, framework, database, tool")
    evidence: Optional[Evidence] = Field(default=None, description="Source provenance in the resume")

class CandidateExperience(BaseModel):
    """
    Extracted employment or professional experience entry.
    """
    role: Optional[str] = Field(default=None, description="Job title / role")
    company: Optional[str] = Field(default=None, description="Employer / organization name")
    start_date: Optional[str] = Field(default=None, description="Normalized start date string")
    end_date: Optional[str] = Field(default=None, description="Normalized end date string or 'Present'")
    is_current: bool = Field(default=False, description="True if this is the candidate's current role")
    duration_months: Optional[float] = Field(default=None, description="Calculated duration in months if safely determinable")
    description: str = Field(default="", description="Bullet points or prose describing responsibilities")
    technologies: List[str] = Field(default_factory=list, description="Technologies mentioned within this experience entry")
    evidence: Optional[Evidence] = Field(default=None, description="Provenance for the experience entry")

class CandidateEducation(BaseModel):
    """
    Extracted academic degree or educational qualification.
    """
    degree: Optional[str] = Field(default=None, description="Degree type, e.g. B.Tech, Bachelor of Science, Master's")
    field_of_study: Optional[str] = Field(default=None, description="Major / specialization, e.g. Computer Science")
    institution: Optional[str] = Field(default=None, description="University, college, or school name")
    start_date: Optional[str] = Field(default=None, description="Start date/year if present")
    end_date: Optional[str] = Field(default=None, description="End date/graduation year if present")
    grade_or_gpa: Optional[str] = Field(default=None, description="GPA or grade if listed")
    evidence: Optional[Evidence] = Field(default=None, description="Provenance for education entry")

class CandidateCertification(BaseModel):
    """
    Extracted professional certification or credential.
    """
    name: str = Field(..., description="Certification title, e.g. AWS Certified Solutions Architect")
    issuer: Optional[str] = Field(default=None, description="Issuing organization, e.g. AWS, Microsoft")
    date: Optional[str] = Field(default=None, description="Issue date if listed")
    evidence: Optional[Evidence] = Field(default=None, description="Provenance for certification")

class CandidateProject(BaseModel):
    """
    Extracted candidate project entry.
    """
    name: str = Field(..., description="Project name")
    description: Optional[str] = Field(default=None, description="Project summary / responsibilities")
    technologies: List[str] = Field(default_factory=list, description="Technologies used in this project")
    evidence: Optional[Evidence] = Field(default=None, description="Provenance for project entry")

class CandidateProfile(BaseModel):
    """
    Structured candidate profile representation extracted by the Resume Analyzer.
    Independent of any Job Description or scoring requirements.
    """
    candidate_id: str = Field(..., description="Unique identifier for the candidate")
    filename: Optional[str] = Field(default=None, description="Original resume filename")
    name: Optional[str] = Field(default=None, description="Candidate full name")
    email: Optional[str] = Field(default=None, description="Contact email address")
    phone: Optional[str] = Field(default=None, description="Contact phone number")
    summary: Optional[str] = Field(default=None, description="Professional summary or objective text")
    sections: Dict[str, str] = Field(default_factory=dict, description="Mapped canonical section text")
    skills: List[str] = Field(default_factory=list, description="List of all extracted skills/technologies")
    technologies: List[str] = Field(default_factory=list, description="Normalized technology names")
    skill_details: List[CandidateSkill] = Field(default_factory=list, description="Detailed skill entities with provenance")
    experience: List[CandidateExperience] = Field(default_factory=list, description="Extracted work experience entries")
    education: List[CandidateEducation] = Field(default_factory=list, description="Extracted education entries")
    certifications: List[CandidateCertification] = Field(default_factory=list, description="Extracted certifications")
    projects: List[CandidateProject] = Field(default_factory=list, description="Extracted projects")
    evidence: List[Evidence] = Field(default_factory=list, description="All collected provenance evidence items")
    raw_text: Optional[str] = Field(default=None, description="Full raw resume text")
    resume: Optional[ResumeDocument] = Field(default=None, description="Backwards-compatible ResumeDocument reference")
