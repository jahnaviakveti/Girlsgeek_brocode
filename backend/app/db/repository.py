import json
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from .models import (
    CandidateProfileRecord,
    ResumeRecord,
    JobTargetRecord,
    EvidenceRecord,
    InterviewSessionRecord,
    ResumeVersionRecord,
    CareerTargetRecord,
    CareerActionRecord,
    InterviewTargetRecord,
    MockInterviewSessionRecord,
)

class Repository:
    """
    Data access layer for candidate profiles, resumes, targets, evidence, and interviews.
    Guarantees idempotency: reprocessing the same resume updates records without duplicates.
    """

    def __init__(self, db: Session):
        self.db = db

    # 1. Candidate Profiles
    def save_candidate_profile(
        self,
        candidate_id: str,
        name: Optional[str],
        email: Optional[str],
        phone: Optional[str],
        summary: Optional[str],
        profile_dict: Dict[str, Any]
    ) -> CandidateProfileRecord:
        record = self.db.query(CandidateProfileRecord).filter_by(candidate_id=candidate_id).first()
        profile_json = json.dumps(profile_dict, default=str)
        if record:
            record.name = name
            record.email = email
            record.phone = phone
            record.summary = summary
            record.profile_json = profile_json
        else:
            record = CandidateProfileRecord(
                candidate_id=candidate_id,
                name=name,
                email=email,
                phone=phone,
                summary=summary,
                profile_json=profile_json,
            )
            self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_candidate_profile(self, candidate_id: str) -> Optional[CandidateProfileRecord]:
        return self.db.query(CandidateProfileRecord).filter_by(candidate_id=candidate_id).first()

    # 2. Resumes (Idempotent by candidate_id + filename)
    def save_resume(
        self,
        candidate_id: str,
        filename: str,
        page_count: int,
        file_size_bytes: int,
        raw_text: str
    ) -> ResumeRecord:
        record = self.db.query(ResumeRecord).filter_by(candidate_id=candidate_id, filename=filename).first()
        if record:
            record.page_count = page_count
            record.file_size_bytes = file_size_bytes
            record.raw_text = raw_text
        else:
            record = ResumeRecord(
                candidate_id=candidate_id,
                filename=filename,
                page_count=page_count,
                file_size_bytes=file_size_bytes,
                raw_text=raw_text,
            )
            self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_resumes_for_candidate(self, candidate_id: str) -> List[ResumeRecord]:
        return self.db.query(ResumeRecord).filter_by(candidate_id=candidate_id).order_by(ResumeRecord.created_at.desc()).all()

    # 3. Job Targets
    def save_job_target(
        self,
        job_id: str,
        title: str,
        raw_text: str,
        requirements_dict: Optional[List[Dict[str, Any]]] = None,
        bias_audit_dict: Optional[Dict[str, Any]] = None,
        company: Optional[str] = None
    ) -> JobTargetRecord:
        record = self.db.query(JobTargetRecord).filter_by(job_id=job_id).first()
        reqs_json = json.dumps(requirements_dict, default=str) if requirements_dict else None
        bias_json = json.dumps(bias_audit_dict, default=str) if bias_audit_dict else None
        if record:
            record.title = title
            record.company = company
            record.raw_text = raw_text
            record.requirements_json = reqs_json
            record.bias_audit_json = bias_json
        else:
            record = JobTargetRecord(
                job_id=job_id,
                title=title,
                company=company,
                raw_text=raw_text,
                requirements_json=reqs_json,
                bias_audit_json=bias_json,
            )
            self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_job_target(self, job_id: str) -> Optional[JobTargetRecord]:
        return self.db.query(JobTargetRecord).filter_by(job_id=job_id).first()

    # 4. Evidence Records (Idempotent upsert by deterministic evidence_id)
    def save_evidence_batch(self, candidate_id: str, items: List[Dict[str, Any]]) -> List[EvidenceRecord]:
        records = []
        for item in items:
            ev_id = item["evidence_id"]
            existing = self.db.query(EvidenceRecord).filter_by(evidence_id=ev_id).first()
            norm_facts_json = json.dumps(item.get("normalized_facts", []), default=str)
            related_tech_str = ",".join(item.get("related_technologies", []))

            if existing:
                existing.candidate_id = candidate_id
                existing.source_text = item.get("source_text", "")
                existing.source_document = item.get("source_document")
                existing.source_section = item.get("source_section")
                existing.page_number = item.get("page_number", 1)
                existing.evidence_type = item.get("evidence_type", "general")
                existing.confidence = item.get("confidence", 1.0)
                existing.normalized_facts = norm_facts_json
                existing.related_entity = item.get("related_entity")
                existing.related_skill = item.get("related_skill")
                existing.related_project = item.get("related_project")
                existing.related_experience = item.get("related_experience")
                existing.related_tech = related_tech_str
                records.append(existing)
            else:
                rec = EvidenceRecord(
                    candidate_id=candidate_id,
                    evidence_id=ev_id,
                    source_text=item.get("source_text", ""),
                    source_document=item.get("source_document"),
                    source_section=item.get("source_section"),
                    page_number=item.get("page_number", 1),
                    evidence_type=item.get("evidence_type", "general"),
                    confidence=item.get("confidence", 1.0),
                    normalized_facts=norm_facts_json,
                    related_entity=item.get("related_entity"),
                    related_skill=item.get("related_skill"),
                    related_project=item.get("related_project"),
                    related_experience=item.get("related_experience"),
                    related_tech=related_tech_str,
                )
                self.db.add(rec)
                records.append(rec)
        self.db.commit()
        return records

    def get_evidence_for_candidate(
        self,
        candidate_id: str,
        section: Optional[str] = None,
        evidence_type: Optional[str] = None,
        skill: Optional[str] = None,
        project: Optional[str] = None,
        experience: Optional[str] = None
    ) -> List[EvidenceRecord]:
        query = self.db.query(EvidenceRecord).filter_by(candidate_id=candidate_id)
        if section:
            query = query.filter(EvidenceRecord.source_section.ilike(f"%{section}%"))
        if evidence_type:
            query = query.filter(EvidenceRecord.evidence_type.ilike(evidence_type))
        if skill:
            query = query.filter(
                (EvidenceRecord.related_skill.ilike(f"%{skill}%")) |
                (EvidenceRecord.related_tech.ilike(f"%{skill}%")) |
                (EvidenceRecord.source_text.ilike(f"%{skill}%"))
            )
        if project:
            query = query.filter(
                (EvidenceRecord.related_project.ilike(f"%{project}%")) |
                (EvidenceRecord.source_text.ilike(f"%{project}%"))
            )
        if experience:
            query = query.filter(
                (EvidenceRecord.related_experience.ilike(f"%{experience}%")) |
                (EvidenceRecord.related_entity.ilike(f"%{experience}%")) |
                (EvidenceRecord.source_text.ilike(f"%{experience}%"))
            )
        return query.all()

    # 5. Interview Sessions
    def create_interview_session(self, session_id: str, candidate_id: str, job_id: Optional[str] = None) -> InterviewSessionRecord:
        record = InterviewSessionRecord(
            session_id=session_id,
            candidate_id=candidate_id,
            job_id=job_id,
            status="active",
            transcript_json="[]",
            star_evaluations_json="{}",
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_interview_session(self, session_id: str) -> Optional[InterviewSessionRecord]:
        return self.db.query(InterviewSessionRecord).filter_by(session_id=session_id).first()

    # 6. Resume Versions (Phase 5)
    def save_resume_version(
        self,
        version_id: str,
        candidate_id: str,
        title: str,
        sections_dict: List[Dict[str, Any]],
        parent_version_id: Optional[str] = None,
        target_role: Optional[str] = None,
        status: str = "DRAFT",
        source_resume_version: Optional[str] = "v1_original",
        accepted_suggestions_dict: Optional[List[Dict[str, Any]]] = None,
        evidence_ids: Optional[List[str]] = None,
        raw_text: Optional[str] = None
    ) -> ResumeVersionRecord:
        record = self.db.query(ResumeVersionRecord).filter_by(version_id=version_id).first()
        sec_json = json.dumps(sections_dict, default=str)
        sug_json = json.dumps(accepted_suggestions_dict or [], default=str)
        ev_json = json.dumps(evidence_ids or [], default=str)

        if record:
            record.title = title
            record.parent_version_id = parent_version_id
            record.target_role = target_role
            record.status = status
            record.source_resume_version = source_resume_version
            record.sections_json = sec_json
            record.accepted_suggestions_json = sug_json
            record.evidence_ids_json = ev_json
            record.raw_text = raw_text
        else:
            record = ResumeVersionRecord(
                version_id=version_id,
                candidate_id=candidate_id,
                parent_version_id=parent_version_id,
                title=title,
                target_role=target_role,
                status=status,
                source_resume_version=source_resume_version,
                sections_json=sec_json,
                accepted_suggestions_json=sug_json,
                evidence_ids_json=ev_json,
                raw_text=raw_text
            )
            self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_resume_version(self, version_id: str) -> Optional[ResumeVersionRecord]:
        return self.db.query(ResumeVersionRecord).filter_by(version_id=version_id).first()

    def get_resume_versions_for_candidate(self, candidate_id: str) -> List[ResumeVersionRecord]:
        return self.db.query(ResumeVersionRecord).filter_by(candidate_id=candidate_id).order_by(ResumeVersionRecord.created_at.desc()).all()

    def delete_resume_version(self, version_id: str) -> bool:
        record = self.db.query(ResumeVersionRecord).filter_by(version_id=version_id).first()
        if record:
            self.db.delete(record)
            self.db.commit()
            return True
        return False

    # 7. Career Targets (Phase 6)
    def save_career_target(
        self,
        target_id: str,
        candidate_id: str,
        target_role: str,
        target_company: Optional[str] = None,
        source_job_fit_id: Optional[str] = None,
        status: str = "ACTIVE",
        raw_jd_text: Optional[str] = None,
        requirements: Optional[List[Dict[str, Any]]] = None
    ) -> CareerTargetRecord:
        req_json = json.dumps(requirements or [], default=str)
        record = self.db.query(CareerTargetRecord).filter_by(target_id=target_id).first()
        if record:
            record.target_role = target_role
            record.target_company = target_company
            record.source_job_fit_id = source_job_fit_id
            record.status = status
            record.raw_jd_text = raw_jd_text
            record.requirements_json = req_json
        else:
            record = CareerTargetRecord(
                target_id=target_id,
                candidate_id=candidate_id,
                target_role=target_role,
                target_company=target_company,
                source_job_fit_id=source_job_fit_id,
                status=status,
                raw_jd_text=raw_jd_text,
                requirements_json=req_json
            )
            self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_career_target(self, target_id: str) -> Optional[CareerTargetRecord]:
        return self.db.query(CareerTargetRecord).filter_by(target_id=target_id).first()

    def get_career_targets_for_candidate(self, candidate_id: str, status: Optional[str] = None) -> List[CareerTargetRecord]:
        query = self.db.query(CareerTargetRecord).filter_by(candidate_id=candidate_id)
        if status:
            query = query.filter_by(status=status)
        return query.order_by(CareerTargetRecord.created_at.desc()).all()

    def archive_career_target(self, target_id: str) -> bool:
        record = self.db.query(CareerTargetRecord).filter_by(target_id=target_id).first()
        if record:
            record.status = "ARCHIVED"
            self.db.commit()
            return True
        return False

    # 8. Career Actions (Phase 6)
    def save_career_action(
        self,
        action_id: str,
        candidate_id: str,
        target_id: str,
        requirement_id: str,
        action_type: str,
        title: str,
        description: str,
        rationale: str,
        priority: str = "MEDIUM",
        status: str = "TODO",
        completed_at: Optional[Any] = None
    ) -> CareerActionRecord:
        record = self.db.query(CareerActionRecord).filter_by(action_id=action_id).first()
        if record:
            record.candidate_id = candidate_id
            record.target_id = target_id
            record.requirement_id = requirement_id
            record.action_type = action_type
            record.title = title
            record.description = description
            record.rationale = rationale
            record.priority = priority
            record.status = status
            record.completed_at = completed_at
        else:
            record = CareerActionRecord(
                action_id=action_id,
                candidate_id=candidate_id,
                target_id=target_id,
                requirement_id=requirement_id,
                action_type=action_type,
                title=title,
                description=description,
                rationale=rationale,
                priority=priority,
                status=status,
                completed_at=completed_at
            )
            self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_career_action(self, action_id: str) -> Optional[CareerActionRecord]:
        return self.db.query(CareerActionRecord).filter_by(action_id=action_id).first()

    def get_career_actions_for_candidate(
        self,
        candidate_id: str,
        target_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[CareerActionRecord]:
        query = self.db.query(CareerActionRecord).filter_by(candidate_id=candidate_id)
        if target_id:
            query = query.filter_by(target_id=target_id)
        if status:
            query = query.filter_by(status=status)
        return query.order_by(CareerActionRecord.created_at.desc()).all()

    def update_career_action_status(
        self,
        action_id: str,
        status: str,
        completed_at: Optional[Any] = None
    ) -> Optional[CareerActionRecord]:
        record = self.db.query(CareerActionRecord).filter_by(action_id=action_id).first()
        if record:
            record.status = status
            if completed_at is not None:
                record.completed_at = completed_at
            self.db.commit()
            self.db.refresh(record)
            return record
        return None

    # 8. Interview Targets & Mock Sessions (Phase 7)
    def save_interview_target(
        self,
        interview_target_id: str,
        candidate_id: str,
        target_role: str,
        target_id: Optional[str] = None,
        company: Optional[str] = None,
        job_fit_id: Optional[str] = None,
        status: str = "ACTIVE"
    ) -> InterviewTargetRecord:
        record = self.db.query(InterviewTargetRecord).filter_by(interview_target_id=interview_target_id).first()
        if record:
            record.target_role = target_role
            record.target_id = target_id
            record.company = company
            record.job_fit_id = job_fit_id
            record.status = status
        else:
            record = InterviewTargetRecord(
                interview_target_id=interview_target_id,
                candidate_id=candidate_id,
                target_id=target_id,
                target_role=target_role,
                company=company,
                job_fit_id=job_fit_id,
                status=status
            )
            self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_interview_target(self, interview_target_id: str) -> Optional[InterviewTargetRecord]:
        return self.db.query(InterviewTargetRecord).filter_by(interview_target_id=interview_target_id).first()

    def get_interview_targets_for_candidate(
        self,
        candidate_id: str,
        status: Optional[str] = None
    ) -> List[InterviewTargetRecord]:
        query = self.db.query(InterviewTargetRecord).filter_by(candidate_id=candidate_id)
        if status:
            query = query.filter_by(status=status)
        return query.order_by(InterviewTargetRecord.created_at.desc()).all()

    def save_mock_interview_session(
        self,
        session_id: str,
        candidate_id: str,
        interview_target_id: str,
        target_role: str,
        status: str = "IN_PROGRESS",
        session_data_list: Optional[List[Dict[str, Any]]] = None
    ) -> MockInterviewSessionRecord:
        record = self.db.query(MockInterviewSessionRecord).filter_by(session_id=session_id).first()
        data_json = json.dumps(session_data_list or [], default=str)
        if record:
            record.status = status
            record.session_data = data_json
        else:
            record = MockInterviewSessionRecord(
                session_id=session_id,
                candidate_id=candidate_id,
                interview_target_id=interview_target_id,
                target_role=target_role,
                status=status,
                session_data=data_json
            )
            self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_mock_interview_session(self, session_id: str) -> Optional[MockInterviewSessionRecord]:
        return self.db.query(MockInterviewSessionRecord).filter_by(session_id=session_id).first()

    def update_mock_interview_session(
        self,
        session_id: str,
        session_data_list: List[Dict[str, Any]],
        status: Optional[str] = None
    ) -> Optional[MockInterviewSessionRecord]:
        record = self.db.query(MockInterviewSessionRecord).filter_by(session_id=session_id).first()
        if record:
            record.session_data = json.dumps(session_data_list, default=str)
            if status:
                record.status = status
            self.db.commit()
            self.db.refresh(record)
            return record
        return None

    def get_mock_interview_sessions_for_candidate(
        self,
        candidate_id: str,
        interview_target_id: Optional[str] = None
    ) -> List[MockInterviewSessionRecord]:
        query = self.db.query(MockInterviewSessionRecord).filter_by(candidate_id=candidate_id)
        if interview_target_id:
            query = query.filter_by(interview_target_id=interview_target_id)
        return query.order_by(MockInterviewSessionRecord.created_at.desc()).all()


