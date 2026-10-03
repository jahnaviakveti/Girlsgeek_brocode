import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.schemas.candidate import (
    CandidateProfile,
    CandidateExperience,
    CandidateEducation,
    CandidateProject,
    CandidateSkill,
)
from app.schemas.domain import (
    Evidence,
    JobDescription,
    JDRequirement,
    RequirementCategory,
    RequirementPriority,
    MatchVerdict,
)
from app.schemas.job_fit import (
    JobFitAnalysis,
    RequirementStatus,
    GapType,
)
from app.services.coach.career_twin import CareerTwinService
from app.services.coach.evidence import EvidenceVaultService
from app.services.coach.job_fit import JobFitService
from app.db.database import Base
from app.db.repository import Repository

client = TestClient(app)

@pytest.fixture
def candidate_alex():
    cid = "cand_alex_001"
    ev1 = Evidence(source_text="Python, Flask, and PostgreSQL backend development", source_section="Skills", confidence_score=1.0, page_number=1, evidence_type="skill")
    ev2 = Evidence(source_text="Backend Engineer at Acme Corp (Jan 2022 - Present)", source_section="Experience", confidence_score=0.95, page_number=1, evidence_type="experience")
    ev3 = Evidence(source_text="Built Flask backend microservices for automated payment processing.\nOptimized SQL queries.", source_section="Projects", confidence_score=0.92, page_number=2, evidence_type="project")

    skill_python = CandidateSkill(name="Python", raw_name="Python", category="language", evidence=ev1)
    skill_flask = CandidateSkill(name="Flask", raw_name="Flask", category="framework", evidence=ev1)
    skill_sql = CandidateSkill(name="PostgreSQL", raw_name="PostgreSQL", category="database", evidence=ev1)

    exp = CandidateExperience(
        role="Backend Engineer",
        company="Acme Corp",
        start_date="Jan 2022",
        end_date="Present",
        is_current=True,
        duration_months=18.0,
        description="Developed Python services with Flask and PostgreSQL. Handled high-throughput financial transactions.",
        technologies=["Python", "Flask", "PostgreSQL"],
        evidence=ev2
    )

    proj = CandidateProject(
        name="Payment Processing Engine",
        description="Built Flask backend microservices for automated payment processing.\nOptimized SQL queries reducing latency by 30%.",
        technologies=["Flask", "PostgreSQL"],
        evidence=ev3
    )

    profile = CandidateProfile(
        candidate_id=cid,
        filename="alex_resume.pdf",
        name="Alex Chen",
        email="alex.chen@example.com",
        phone="555-0188",
        summary="Backend developer with 1.5 years experience in Python and Flask.",
        sections={"skills": "Python, Flask, PostgreSQL", "experience": "Backend Engineer at Acme Corp", "projects": "Payment Processing Engine"},
        skills=["Python", "Flask", "PostgreSQL"],
        technologies=["Python", "Flask", "PostgreSQL"],
        skill_details=[skill_python, skill_flask, skill_sql],
        experience=[exp],
        projects=[proj],
        evidence=[ev1, ev2, ev3],
        raw_text="Alex Chen\nBackend developer with 1.5 years experience in Python and Flask.\nBackend Engineer at Acme Corp\nPayment Processing Engine"
    )
    return profile

@pytest.fixture
def alex_twin_and_vault(candidate_alex):
    vault_service = EvidenceVaultService()
    twin_service = CareerTwinService()
    vault = vault_service.build_vault(candidate_alex)
    twin = twin_service.build_twin(candidate_alex, vault)
    return twin, vault

# 1. Fully matched JD
def test_fully_matched_jd(candidate_alex, alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    service = JobFitService()

    req1 = JDRequirement(id="req_1", requirement_text="Python programming", category=RequirementCategory.SKILL, priority=RequirementPriority.REQUIRED)
    req2 = JDRequirement(id="req_2", requirement_text="Flask framework", category=RequirementCategory.SKILL, priority=RequirementPriority.REQUIRED)
    jd = JobDescription(jd_id="jd_full", title="Python Flask Engineer", raw_text="Python and Flask required.", requirements=[req1, req2])

    resp = service.evaluate_fit(candidate_alex, jd, twin=twin, vault=vault)
    analysis = resp.job_fit_analysis

    assert analysis is not None
    assert len(analysis.matched_requirements) == 2
    assert len(analysis.missing_requirements) == 0
    assert analysis.fit_summary.evidence_coverage_score == 100.0
    assert analysis.fit_summary.evidence_strength == "Strong"

# 2. Partially matched JD
def test_partially_matched_jd(candidate_alex, alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    service = JobFitService()

    req = JDRequirement(id="req_partial", requirement_text="Python and Docker containerization", category=RequirementCategory.SKILL, priority=RequirementPriority.REQUIRED)
    jd = JobDescription(jd_id="jd_part", title="Software Engineer", raw_text="Python and Docker required.", requirements=[req])

    resp = service.evaluate_fit(candidate_alex, jd, twin=twin, vault=vault)
    analysis = resp.job_fit_analysis

    assert len(analysis.requirements) == 1
    fit_req = analysis.requirements[0]
    assert fit_req.status in {RequirementStatus.PARTIAL, RequirementStatus.MATCHED}
    assert fit_req.combined_score > 0.0

# 3. Missing requirement
def test_missing_requirement(candidate_alex, alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    service = JobFitService()

    req = JDRequirement(id="req_k8s", requirement_text="Kubernetes cluster orchestration", category=RequirementCategory.SKILL, priority=RequirementPriority.REQUIRED)
    jd = JobDescription(jd_id="jd_missing", title="DevOps Engineer", raw_text="Kubernetes required.", requirements=[req])

    resp = service.evaluate_fit(candidate_alex, jd, twin=twin, vault=vault)
    analysis = resp.job_fit_analysis

    assert len(analysis.missing_requirements) == 1
    missing_req = analysis.missing_requirements[0]
    assert missing_req.status == RequirementStatus.MISSING
    assert missing_req.gap_type == GapType.EXPERIENCE_GAP

# 4. Required vs preferred
def test_required_vs_preferred(candidate_alex, alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    service = JobFitService()

    req_mandatory = JDRequirement(id="req_m", requirement_text="Python development", category=RequirementCategory.SKILL, priority=RequirementPriority.REQUIRED)
    req_optional = JDRequirement(id="req_o", requirement_text="Kubernetes deployment", category=RequirementCategory.SKILL, priority=RequirementPriority.PREFERRED)
    jd = JobDescription(jd_id="jd_prio", title="Python Engineer", raw_text="Python required, Kubernetes preferred.", requirements=[req_mandatory, req_optional])

    resp = service.evaluate_fit(candidate_alex, jd, twin=twin, vault=vault)
    analysis = resp.job_fit_analysis

    assert len(analysis.required_requirements) == 1
    assert len(analysis.preferred_requirements) == 1
    assert analysis.required_requirements[0].is_required is True
    assert analysis.preferred_requirements[0].is_required is False

# 5. Experience tenure mismatch
def test_experience_tenure_mismatch(candidate_alex, alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    service = JobFitService()

    # JD requires 3 years Python (36 months), candidate has 18 months
    req = JDRequirement(id="req_tenure", requirement_text="3+ years of Python experience", category=RequirementCategory.EXPERIENCE, priority=RequirementPriority.REQUIRED, min_years=3.0)
    jd = JobDescription(jd_id="jd_tenure", title="Senior Engineer", raw_text="3+ years Python experience required.", requirements=[req])

    resp = service.evaluate_fit(candidate_alex, jd, twin=twin, vault=vault)
    analysis = resp.job_fit_analysis

    tenure_req = analysis.requirements[0]
    assert tenure_req.required_months == 36.0
    assert tenure_req.verified_months is not None
    assert tenure_req.tenure_gap_months is not None
    assert tenure_req.tenure_gap_months > 0.0

# 6. Evidence-backed strength
def test_evidence_backed_strength(candidate_alex, alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    service = JobFitService()

    req = JDRequirement(id="req_py", requirement_text="Python programming", category=RequirementCategory.SKILL, priority=RequirementPriority.REQUIRED)
    jd = JobDescription(jd_id="jd_str", title="Python Developer", raw_text="Python required.", requirements=[req])

    resp = service.evaluate_fit(candidate_alex, jd, twin=twin, vault=vault)
    analysis = resp.job_fit_analysis

    assert len(analysis.strengths) >= 1
    strength = analysis.strengths[0]
    assert "Python" in strength.title
    assert len(strength.supporting_evidence) > 0

# 7. Resume visibility gap
def test_resume_visibility_gap(candidate_alex, alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    service = JobFitService()

    # Candidate has "Flask backend microservices", JD asks for "REST API development with Flask"
    req = JDRequirement(id="req_api", requirement_text="REST API development using Flask", category=RequirementCategory.SKILL, priority=RequirementPriority.REQUIRED)
    jd = JobDescription(jd_id="jd_vis", title="API Developer", raw_text="REST API development using Flask.", requirements=[req])

    resp = service.evaluate_fit(candidate_alex, jd, twin=twin, vault=vault)
    analysis = resp.job_fit_analysis

    fit_req = analysis.requirements[0]
    # If partial, it must be flagged as RESUME_VISIBILITY_GAP
    if fit_req.status != RequirementStatus.MATCHED:
        assert fit_req.gap_type == GapType.RESUME_VISIBILITY_GAP
        assert "visibility gap" in fit_req.explanation.lower()

# 8. Genuine experience gap
def test_genuine_experience_gap(candidate_alex, alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    service = JobFitService()

    req = JDRequirement(id="req_k8s", requirement_text="Kubernetes infrastructure and Helm charts", category=RequirementCategory.SKILL, priority=RequirementPriority.REQUIRED)
    jd = JobDescription(jd_id="jd_exp_gap", title="Cloud Engineer", raw_text="Kubernetes required.", requirements=[req])

    resp = service.evaluate_fit(candidate_alex, jd, twin=twin, vault=vault)
    analysis = resp.job_fit_analysis

    fit_req = analysis.requirements[0]
    assert fit_req.status == RequirementStatus.MISSING
    assert fit_req.gap_type == GapType.EXPERIENCE_GAP
    assert "no supporting evidence" in fit_req.explanation.lower()

# 9. Requirement not verifiable
def test_requirement_not_verifiable(candidate_alex, alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    service = JobFitService()

    req = JDRequirement(id="req_soft", requirement_text="Excellent verbal communication and team collaboration skills", category=RequirementCategory.OTHER, priority=RequirementPriority.PREFERRED)
    jd = JobDescription(jd_id="jd_soft", title="Engineer", raw_text="Excellent communication skills.", requirements=[req])

    resp = service.evaluate_fit(candidate_alex, jd, twin=twin, vault=vault)
    analysis = resp.job_fit_analysis

    fit_req = analysis.requirements[0]
    if fit_req.status != RequirementStatus.MATCHED:
        assert fit_req.gap_type == GapType.NOT_VERIFIABLE
        assert "not verifiable" in fit_req.explanation.lower()

# 10. JD bias warnings
def test_jd_bias_warnings(candidate_alex, alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    service = JobFitService()

    jd_text = "We are seeking a rockstar ninja developer who is a digital native. Must be under 30 with aggressive work ethic."
    req = JDRequirement(id="req_1", requirement_text="Python programming", category=RequirementCategory.SKILL, priority=RequirementPriority.REQUIRED)
    jd = JobDescription(jd_id="jd_bias", title="Developer", raw_text=jd_text, requirements=[req])

    resp = service.evaluate_fit(candidate_alex, jd, twin=twin, vault=vault, raw_jd_text=jd_text)
    assert resp.bias_audit is not None
    assert resp.bias_audit.total_flags > 0

# 11. Evidence references integrity
def test_evidence_references_integrity(candidate_alex, alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    service = JobFitService()

    req = JDRequirement(id="req_1", requirement_text="Python development", category=RequirementCategory.SKILL, priority=RequirementPriority.REQUIRED)
    jd = JobDescription(jd_id="jd_ev", title="Engineer", raw_text="Python required.", requirements=[req])

    resp = service.evaluate_fit(candidate_alex, jd, twin=twin, vault=vault)
    analysis = resp.job_fit_analysis

    assert len(analysis.matched_requirements) > 0
    m_req = analysis.matched_requirements[0]
    assert len(m_req.evidence) > 0
    citation = m_req.evidence[0]
    assert "Python" in citation.source_text

# 12. Candidate ID integration
def test_candidate_id_integration(candidate_alex, alex_twin_and_vault):
    from app.api.routes import coach as coach_routes
    twin, vault = alex_twin_and_vault
    cid = candidate_alex.candidate_id
    coach_routes._in_memory_profiles[cid] = candidate_alex
    coach_routes._in_memory_twins[cid] = twin
    coach_routes._in_memory_vaults[cid] = vault

    resp = client.post(
        "/api/coach/job-fit",
        data={
            "candidate_id": cid,
            "jd_text": "Looking for a Python and Flask backend engineer."
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["candidate_id"] == cid
    assert "job_fit_analysis" in data
    assert data["job_fit_analysis"]["target_role"] is not None

# 13. Persisted Career Twin integration
def test_persisted_career_twin_integration(candidate_alex, alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    repo = Repository(db)
    repo.save_candidate_profile(twin.candidate_id, twin.name, twin.email, twin.phone, twin.summary, twin.model_dump())
    repo.save_evidence_batch(twin.candidate_id, [it.model_dump() for it in vault.items])

    rec = repo.get_candidate_profile(twin.candidate_id)
    assert rec is not None
    assert rec.name == "Alex Chen"

def test_no_fabricated_evidence(candidate_alex, alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    service = JobFitService()

    req = JDRequirement(id="req_k8s", requirement_text="Kubernetes cluster orchestration", category=RequirementCategory.SKILL, priority=RequirementPriority.REQUIRED)
    jd = JobDescription(jd_id="jd_k8s", title="DevOps Engineer", raw_text="Kubernetes required.", requirements=[req])

    resp = service.evaluate_fit(candidate_alex, jd, twin=twin, vault=vault)
    analysis = resp.job_fit_analysis

    assert len(analysis.missing_requirements) > 0, "Missing requirements expected"
    missing = analysis.missing_requirements[0]
    assert len(missing.evidence) == 0, "Missing requirements must never have fabricated evidence citations."
    assert missing.status == RequirementStatus.MISSING

# 15. Job Fit -> Resume Coach handoff
def test_job_fit_to_resume_coach_handoff(candidate_alex, alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    service = JobFitService()

    req1 = JDRequirement(id="req_api", requirement_text="REST API development using Flask", category=RequirementCategory.SKILL, priority=RequirementPriority.REQUIRED)
    req2 = JDRequirement(id="req_k8s", requirement_text="Kubernetes cluster management", category=RequirementCategory.SKILL, priority=RequirementPriority.REQUIRED)
    jd = JobDescription(jd_id="jd_hand", title="Senior Backend Engineer", raw_text="REST API and Kubernetes required.", requirements=[req1, req2])

    resp = service.evaluate_fit(candidate_alex, jd, twin=twin, vault=vault)
    analysis = resp.job_fit_analysis

    assert len(analysis.improvement_opportunities) >= 1
    for opp in analysis.improvement_opportunities:
        payload = opp.handoff_payload
        assert "requirement_id" in payload
        assert "target_role" in payload
        assert "can_rewrite" in payload
        if opp.gap_type == GapType.RESUME_VISIBILITY_GAP:
            assert payload["can_rewrite"] is True
            assert "action_prompt" in payload
        elif opp.gap_type == GapType.EXPERIENCE_GAP:
            assert payload["can_rewrite"] is False
