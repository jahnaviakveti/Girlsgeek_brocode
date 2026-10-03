import re
import uuid
from typing import Optional, List, Set, Tuple
from app.schemas.document import GenericDocument
from app.schemas.candidate import (
    CandidateProfile,
    CandidateSkill,
    CandidateExperience,
    CandidateEducation,
    CandidateCertification,
    CandidateProject,
)
from app.schemas.domain import Evidence, ResumeDocument
from app.services.resume_analyzer.section_extractor import ResumeSectionExtractor
from app.services.resume_analyzer.skill_extractor import SkillExtractor
from app.services.resume_analyzer.experience_extractor import ExperienceExtractor
from app.services.resume_analyzer.education_extractor import EducationExtractor
from app.services.resume_analyzer.certification_extractor import CertificationExtractor
from app.services.resume_analyzer.project_extractor import ProjectExtractor
from app.services.jd_analyzer.taxonomy import extract_technologies

NON_NAME_HEADERS = {
    "resume", "curriculum vitae", "cv", "contact", "profile", "summary",
    "experience", "education", "skills", "projects", "personal info",
    "contact information", "phone", "email", "address"
}

EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
PHONE_PATTERN = re.compile(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')

class ResumeAnalyzer:
    """
    Local, deterministic Resume Analyzer.
    Transforms a GenericDocument into a structured CandidateProfile with complete
    skills, experience, education, certifications, projects, and evidence provenance.
    """

    @classmethod
    def extract_contact_info(cls, document: GenericDocument) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Extracts candidate (name, email, phone) from the document header.
        """
        email: Optional[str] = None
        phone: Optional[str] = None
        name: Optional[str] = None

        full_raw = document.raw_text

        # Email
        e_match = EMAIL_PATTERN.search(full_raw)
        if e_match:
            email = e_match.group(0).strip()

        # Phone
        p_match = PHONE_PATTERN.search(full_raw)
        if p_match:
            phone = p_match.group(0).strip()

        # Name: inspect first page blocks/lines
        if document.pages:
            first_page = document.pages[0]
            lines = [l.strip() for l in first_page.normalized_text.split("\n") if l.strip()]

            for line in lines[:5]:
                # Clean line of email/phone
                clean = re.sub(EMAIL_PATTERN, '', line)
                clean = re.sub(PHONE_PATTERN, '', clean).strip().strip("|,•-")
                words = clean.split()

                if 1 <= len(words) <= 4 and all(w.isalpha() for w in words):
                    if clean.lower() not in NON_NAME_HEADERS and len(clean) >= 3:
                        name = clean
                        break

        if not name:
            # Fallback to filename without extension
            base_fn = document.filename.replace(".pdf", "").replace("_", " ").title()
            if not any(header in base_fn.lower() for header in ["resume", "cv", "document"]):
                name = base_fn

        return name, email, phone

    @classmethod
    def analyze(cls, document: GenericDocument, candidate_id: Optional[str] = None) -> CandidateProfile:
        """
        Analyzes a GenericDocument and produces a structured CandidateProfile.
        """
        cid = candidate_id or f"cand_{uuid.uuid4().hex[:8]}"

        # 1. Contact & Identity Information
        name, email, phone = cls.extract_contact_info(document)

        # 2. Section Segmentation
        sections_map, provenance_map, detected_sections = ResumeSectionExtractor.extract_sections(document.pages)

        # 3. Skills Extraction
        skill_details = SkillExtractor.extract_all_skills(document, sections_map, provenance_map)

        # Unique skill names
        skills_set: Set[str] = {s.name for s in skill_details}

        # 4. Work Experience Extraction
        exp_text = sections_map.get("experience", "")
        exp_prov = provenance_map.get("experience", ("Experience", 1))
        experience_entries = ExperienceExtractor.extract_experience(
            exp_text,
            section_name=exp_prov[0],
            page_number=exp_prov[1]
        )

        # 5. Education Extraction
        edu_text = sections_map.get("education", "")
        edu_prov = provenance_map.get("education", ("Education", 1))
        education_entries = EducationExtractor.extract_education(
            edu_text,
            section_name=edu_prov[0],
            page_number=edu_prov[1]
        )

        # 6. Certification Extraction
        cert_text = sections_map.get("certifications", "")
        cert_prov = provenance_map.get("certifications", ("Certifications", 1))
        certification_entries = CertificationExtractor.extract_certifications(
            cert_text,
            section_name=cert_prov[0],
            page_number=cert_prov[1]
        )

        # 7. Project Extraction
        proj_text = sections_map.get("projects", "")
        proj_prov = provenance_map.get("projects", ("Projects", 1))
        project_entries = ProjectExtractor.extract_projects(
            proj_text,
            section_name=proj_prov[0],
            page_number=proj_prov[1]
        )

        # 8. Technologies Aggregation
        # Combine technologies identified in skills, experience, and projects
        tech_set: Set[str] = set()
        for s in skill_details:
            tech_set.add(s.name)
        for exp in experience_entries:
            for t in exp.technologies:
                tech_set.add(t)
                skills_set.add(t)
        for proj in project_entries:
            for t in proj.technologies:
                tech_set.add(t)
                skills_set.add(t)

        # 9. Evidence Aggregation
        all_evidence: List[Evidence] = []
        for s in skill_details:
            if s.evidence:
                all_evidence.append(s.evidence)
        for exp in experience_entries:
            if exp.evidence:
                all_evidence.append(exp.evidence)
        for edu in education_entries:
            if edu.evidence:
                all_evidence.append(edu.evidence)
        for cert in certification_entries:
            if cert.evidence:
                all_evidence.append(cert.evidence)
        for proj in project_entries:
            if proj.evidence:
                all_evidence.append(proj.evidence)

        # Summary
        summary_text = sections_map.get("summary", None)

        resume_doc = ResumeDocument(
            candidate_id=cid,
            raw_text=document.raw_text,
            sections=sections_map,
        )

        return CandidateProfile(
            candidate_id=cid,
            filename=document.filename,
            name=name,
            email=email,
            phone=phone,
            summary=summary_text,
            sections=sections_map,
            skills=sorted(list(skills_set)),
            technologies=sorted(list(tech_set)),
            skill_details=skill_details,
            experience=experience_entries,
            education=education_entries,
            certifications=certification_entries,
            projects=project_entries,
            evidence=all_evidence,
            raw_text=document.raw_text,
            resume=resume_doc,
        )

def analyze_resume(document: GenericDocument, candidate_id: Optional[str] = None) -> CandidateProfile:
    """
    Convenience function to analyze a GenericDocument into a CandidateProfile.
    """
    return ResumeAnalyzer.analyze(document, candidate_id)
