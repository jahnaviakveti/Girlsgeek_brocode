import datetime
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Boolean
from .database import Base

class CandidateProfileRecord(Base):
    __tablename__ = "candidate_profiles"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(64), nullable=True)
    summary = Column(Text, nullable=True)
    profile_json = Column(Text, nullable=False)  # Complete serialized CandidateProfile / CareerTwin
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class ResumeRecord(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(String(64), index=True, nullable=False)
    filename = Column(String(255), nullable=False)
    page_count = Column(Integer, default=1)
    file_size_bytes = Column(Integer, default=0)
    raw_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class JobTargetRecord(Base):
    __tablename__ = "job_targets"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(64), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    company = Column(String(255), nullable=True)
    raw_text = Column(Text, nullable=False)
    requirements_json = Column(Text, nullable=True)
    bias_audit_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class EvidenceRecord(Base):
    __tablename__ = "evidence_records"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(String(64), index=True, nullable=False)
    evidence_id = Column(String(64), unique=True, index=True, nullable=False)
    source_text = Column(Text, nullable=False)
    source_document = Column(String(255), nullable=True)
    source_section = Column(String(128), nullable=True)
    page_number = Column(Integer, default=1)
    evidence_type = Column(String(64), nullable=False)
    confidence = Column(Float, default=1.0)
    normalized_facts = Column(Text, nullable=True)  # JSON-encoded list of facts
    related_entity = Column(String(255), nullable=True)
    related_skill = Column(String(255), nullable=True)
    related_project = Column(String(255), nullable=True)
    related_experience = Column(String(255), nullable=True)
    related_tech = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class InterviewSessionRecord(Base):
    __tablename__ = "interview_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), unique=True, index=True, nullable=False)
    candidate_id = Column(String(64), index=True, nullable=False)
    job_id = Column(String(64), index=True, nullable=True)
    status = Column(String(32), default="active")  # 'active', 'completed', 'paused'
    transcript_json = Column(Text, default="[]")
    star_evaluations_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class ResumeVersionRecord(Base):
    __tablename__ = "resume_versions"

    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(String(64), unique=True, index=True, nullable=False)
    candidate_id = Column(String(64), index=True, nullable=False)
    parent_version_id = Column(String(64), nullable=True)
    title = Column(String(255), nullable=False)
    target_role = Column(String(255), nullable=True)
    status = Column(String(32), default="DRAFT", nullable=False)  # 'DRAFT', 'ACTIVE', 'ARCHIVED'
    source_resume_version = Column(String(64), nullable=True)
    sections_json = Column(Text, nullable=False)  # JSON-encoded list of ResumeSection
    accepted_suggestions_json = Column(Text, default="[]", nullable=False)
    evidence_ids_json = Column(Text, default="[]", nullable=False)
    raw_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class CareerTargetRecord(Base):
    __tablename__ = "career_targets"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(String(64), unique=True, index=True, nullable=False)
    candidate_id = Column(String(64), index=True, nullable=False)
    target_role = Column(String(255), nullable=False)
    target_company = Column(String(255), nullable=True)
    source_job_fit_id = Column(String(64), nullable=True)
    status = Column(String(32), default="ACTIVE", nullable=False)  # 'ACTIVE', 'ARCHIVED'
    raw_jd_text = Column(Text, nullable=True)
    requirements_json = Column(Text, default="[]", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class CareerActionRecord(Base):
    __tablename__ = "career_actions"

    id = Column(Integer, primary_key=True, index=True)
    action_id = Column(String(64), unique=True, index=True, nullable=False)
    candidate_id = Column(String(64), index=True, nullable=False)
    target_id = Column(String(64), index=True, nullable=False)
    requirement_id = Column(String(64), index=True, nullable=False)
    action_type = Column(String(64), nullable=False)  # RESUME_IMPROVEMENT, DOCUMENT_EVIDENCE, etc.
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    rationale = Column(Text, nullable=False)
    priority = Column(String(32), default="MEDIUM", nullable=False)  # HIGH, MEDIUM, LOW
    status = Column(String(32), default="TODO", nullable=False)  # TODO, IN_PROGRESS, COMPLETED, DISMISSED
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

class InterviewTargetRecord(Base):
    __tablename__ = "interview_targets"

    id = Column(Integer, primary_key=True, index=True)
    interview_target_id = Column(String(64), unique=True, index=True, nullable=False)
    candidate_id = Column(String(64), index=True, nullable=False)
    target_id = Column(String(64), index=True, nullable=True)
    target_role = Column(String(255), nullable=False)
    company = Column(String(255), nullable=True)
    job_fit_id = Column(String(64), nullable=True)
    status = Column(String(32), default="ACTIVE", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class MockInterviewSessionRecord(Base):
    __tablename__ = "mock_interview_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), unique=True, index=True, nullable=False)
    candidate_id = Column(String(64), index=True, nullable=False)
    interview_target_id = Column(String(64), index=True, nullable=False)
    target_role = Column(String(255), nullable=False)
    status = Column(String(32), default="IN_PROGRESS", nullable=False)
    session_data = Column(Text, default="[]", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)



