import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.schemas.candidate import CandidateProfile, CandidateExperience, CandidateSkill
from app.schemas.domain import Evidence, JobDescription, JDRequirement, RequirementCategory, RequirementPriority
from app.schemas.career_twin import CareerTwin
from app.schemas.evidence_vault import EvidenceVault
from app.services.coach.career_twin import CareerTwinService
from app.services.coach.evidence import EvidenceVaultService
from app.services.coach.job_fit import JobFitService
from app.services.coach.resume import ResumeCoachService
from app.services.coach.interview import InterviewCoachService
from app.services.coach.ats import ATSStressTestService
from app.services.coach.llm import get_llm_provider, DeterministicFallbackProvider
from app.db.database import Base
from app.db.repository import Repository

client = TestClient(app)

@pytest.fixture
def sample_candidate_profile():
    cid = "cand_test_001"
    ev1 = Evidence(source_text="Python and FastAPI developer", source_section="Skills", confidence_score=1.0, page_number=1, evidence_type="skill")
    ev2 = Evidence(source_text="Senior Backend Engineer at Acme Corp (2022 - Present)", source_section="Experience", confidence_score=0.95, page_number=1, evidence_type="experience")

    skill = CandidateSkill(name="Python", raw_name="Python", category="technology", evidence=ev1)
    exp = CandidateExperience(
        role="Senior Backend Engineer",
        company="Acme Corp",
        start_date="Jan 2022",
        end_date="Present",
        is_current=True,
        duration_months=24.0,
        description="Built scalable REST APIs using Python and Docker. Reduced latency by 35% across 5M requests.",
        technologies=["Python", "Docker"],
        evidence=ev2
    )

    return CandidateProfile(
        candidate_id=cid,
        name="Alex Mercer",
        email="alex.mercer@example.com",
        phone="555-0199",
        summary="Experienced software engineer specializing in backend systems.",
        sections={"skills": "Python, Docker", "experience": "Senior Backend Engineer at Acme Corp"},
        skills=["Python", "Docker"],
        technologies=["Python", "Docker"],
        skill_details=[skill],
        experience=[exp],
        education=[],
        certifications=[],
        projects=[],
        evidence=[ev1, ev2],
        raw_text="Alex Mercer\nSenior Backend Engineer\nPython and FastAPI developer",
    )

@pytest.fixture
def sample_job_description():
    req1 = JDRequirement(
        id="req_1",
        requirement_text="Proficiency in Python backend development",
        category=RequirementCategory.SKILL,
        priority=RequirementPriority.REQUIRED,
        extracted_keywords=["Python"]
    )
    req2 = JDRequirement(
        id="req_2",
        requirement_text="Experience with Docker containerization",
        category=RequirementCategory.SKILL,
        priority=RequirementPriority.PREFERRED,
        extracted_keywords=["Docker"]
    )
    return JobDescription(
        jd_id="jd_test_101",
        title="Senior Python Engineer",
        raw_text="Looking for a Senior Python Engineer with Docker expertise.",
        requirements=[req1, req2]
    )

@pytest.fixture
def in_memory_repo():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    repo = Repository(db)
    yield repo
    db.close()

# 1. Test Evidence Vault Service
def test_evidence_vault_build(sample_candidate_profile):
    vault_service = EvidenceVaultService()
    vault = vault_service.build_vault(sample_candidate_profile)
    assert vault.candidate_id == sample_candidate_profile.candidate_id
    assert vault.total_items > 0
    assert "skills" in vault.section_index or "experience" in vault.section_index
    assert "python" in vault.technology_index
    
    # Query test
    py_items = vault_service.query_evidence_by_technology(vault, "Python")
    assert len(py_items) > 0

# 2. Test Career Twin Service
def test_career_twin_build(sample_candidate_profile):
    vault_service = EvidenceVaultService()
    vault = vault_service.build_vault(sample_candidate_profile)
    
    twin_service = CareerTwinService()
    twin = twin_service.build_twin(sample_candidate_profile, vault)
    
    assert twin.candidate_id == sample_candidate_profile.candidate_id
    assert twin.name == "Alex Mercer"
    assert twin.total_experience_months >= 24.0
    assert len(twin.timeline) >= 1
    assert len(twin.achievements) >= 1
    assert twin.achievements[0].metric == "35%"
    assert any(s.name == "Python" for s in twin.skill_nodes)

# 3. Test Job Fit Service
def test_job_fit_service(sample_candidate_profile, sample_job_description):
    job_fit_service = JobFitService()
    fit = job_fit_service.evaluate_fit(sample_candidate_profile, sample_job_description)
    
    assert fit.candidate_id == sample_candidate_profile.candidate_id
    assert fit.fit_score > 0.0
    assert fit.required_fit_score > 0.0
    assert len(fit.matched_requirements) > 0
    assert fit.coaching_summary != ""

# 4. Test Resume Coach Service
def test_resume_coach_service(sample_candidate_profile):
    twin_service = CareerTwinService()
    twin = twin_service.build_twin(sample_candidate_profile)
    
    coach = ResumeCoachService()
    analysis = coach.analyze_resume_quality(twin)
    assert "overall_resume_health_score" in analysis
    assert analysis["quantified_bullets_percentage"] > 0

# 5. Test Interview Coach Service & STAR Analysis
def test_interview_coach_service(sample_candidate_profile):
    twin_service = CareerTwinService()
    twin = twin_service.build_twin(sample_candidate_profile)
    
    interview_service = InterviewCoachService()
    prep = interview_service.generate_interview_prep(twin)
    assert prep["total_questions_generated"] > 0
    
    # STAR answer analyzer
    star_res = interview_service.evaluate_star_answer(
        "During my time at Acme Corp, I needed to reduce API response times. "
        "I implemented caching using Redis and refactored queries, resulting in a 40% performance gain."
    )
    assert star_res["star_score"] == 100
    assert star_res["components_present"]["result"] is True

# 6. Test ATS Stress Test Service
def test_ats_stress_test_service(sample_candidate_profile):
    from app.schemas.document import GenericDocument, DocumentPage
    page = DocumentPage(page_number=1, raw_text=sample_candidate_profile.raw_text or "", normalized_text=sample_candidate_profile.raw_text or "", blocks=[])
    doc = GenericDocument(
        document_id="doc_test_1",
        filename="resume.pdf",
        raw_text=sample_candidate_profile.raw_text or "Python developer with experience",
        normalized_text=sample_candidate_profile.raw_text or "",
        page_count=1,
        pages=[page]
    )
    ats = ATSStressTestService()
    audit = ats.audit_resume(doc, sample_candidate_profile)
    assert "ats_readability_score" in audit
    assert audit["ats_grade"] in ["A", "B", "C"]

# 7. Test LLM Provider Abstraction
def test_llm_provider_fallback():
    provider = get_llm_provider()
    assert isinstance(provider, DeterministicFallbackProvider)
    text = provider.generate("Give me feedback on my resume")
    assert "Deterministic Coaching Evaluation" in text

# 8. Test Database Persistence & Repository
def test_repository_crud(in_memory_repo, sample_candidate_profile):
    rec = in_memory_repo.save_candidate_profile(
        candidate_id="cand_repo_1",
        name="Taylor Swift",
        email="taylor@example.com",
        phone="555-1234",
        summary="Lead developer",
        profile_dict=sample_candidate_profile.model_dump()
    )
    assert rec.id is not None
    
    retrieved = in_memory_repo.get_candidate_profile("cand_repo_1")
    assert retrieved is not None
    assert retrieved.name == "Taylor Swift"
    
    # Save resume
    res_rec = in_memory_repo.save_resume("cand_repo_1", "taylor_resume.pdf", 2, 1024, "Sample text")
    assert res_rec.id is not None
    
    # Save evidence
    ev_recs = in_memory_repo.save_evidence_batch("cand_repo_1", [
        {"evidence_id": "ev_test_1", "source_text": "Python 5 years", "source_section": "Skills", "page_number": 1, "evidence_type": "skill"}
    ])
    assert len(ev_recs) == 1

# 9. Test Coach API Endpoints
def test_coach_health_endpoint():
    resp = client.get("/api/coach/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

def create_pdf_bytes(text: str) -> bytes:
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    b = doc.tobytes()
    doc.close()
    return b

def test_coach_resume_upload():
    resume_text = """
    Aditi Sharma
    Email: aditi.sharma@example.com
    Phone: 9876543210

    SKILLS
    Python, SQL, PostgreSQL, Docker, Git

    EXPERIENCE
    Software Developer at FinTech Global (Jan 2022 - Present)
    Developed Python backend microservices and optimized SQL queries.
    Reduced processing latency by 25%.
    """
    pdf_bytes = create_pdf_bytes(resume_text)
    resp = client.post(
        "/api/coach/resume",
        files={"resume_file": ("Resume_Aditi_Sharma.pdf", pdf_bytes, "application/pdf")}
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert "career_twin" in data
    assert "evidence_vault" in data
    assert data["career_twin"]["name"] is not None
    assert data["evidence_vault"]["total_items"] > 0
    cid = data["candidate_id"]

    # Test query Career Twin endpoint
    query_resp = client.post("/api/coach/career-twin", json={"candidate_id": cid})
    assert query_resp.status_code == 200
    assert query_resp.json()["career_twin"]["candidate_id"] == cid

    # Test Job Fit endpoint with raw text JD
    fit_resp = client.post(
        "/api/coach/job-fit",
        data={
            "candidate_id": cid,
            "jd_text": "We are seeking a Software Engineer with Python and SQL experience. Required: 1+ year experience."
        }
    )
    assert fit_resp.status_code == 200
    fit_data = fit_resp.json()
    assert "fit_score" in fit_data
    assert "coaching_summary" in fit_data

# 10. Backward Compatibility Test: verify /api/analyze still works
def test_legacy_analyze_compatibility():
    jd_text = """
    Job Title: Backend Engineer
    Required:
    - 2+ years of Python experience
    """
    resume_text = """
    John Doe
    Email: john@example.com
    SKILLS
    Python, FastAPI
    EXPERIENCE
    Backend Engineer at Beta Inc (Jan 2021 - Present)
    Worked with Python for 3 years.
    """
    j_bytes = create_pdf_bytes(jd_text)
    r_bytes = create_pdf_bytes(resume_text)

    resp = client.post(
        "/api/analyze",
        files={
            "jd_file": ("Sample_JD.pdf", j_bytes, "application/pdf"),
            "resume_files": ("Resume_John_Doe.pdf", r_bytes, "application/pdf"),
        }
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["total_ranked"] == 1
    assert "job" in res_data
