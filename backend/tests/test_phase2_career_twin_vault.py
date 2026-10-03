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
    CandidateCertification,
    CandidateSkill,
)
from app.schemas.domain import Evidence
from app.schemas.evidence_vault import EvidenceVault, VaultEvidenceItem, EvidenceType
from app.schemas.career_twin import CareerTwin
from app.services.coach.career_twin import CareerTwinService
from app.services.coach.evidence import EvidenceVaultService, EvidenceValidationService
from app.db.database import Base
from app.db.repository import Repository

client = TestClient(app)

@pytest.fixture
def rich_candidate_profile():
    cid = "cand_phase2_rich"
    ev_skill = Evidence(source_text="Python, Flask, Docker, and PostgreSQL", source_section="Skills", confidence_score=1.0, page_number=1, evidence_type="skill")
    ev_exp = Evidence(source_text="Lead Backend Engineer at CloudScale Tech (2021 - Present)", source_section="Experience", confidence_score=0.95, page_number=1, evidence_type="experience")
    ev_edu = Evidence(source_text="Bachelor of Science in Computer Science at Stanford University (GPA: 3.85)", source_section="Education", confidence_score=1.0, page_number=2, evidence_type="education")
    ev_proj = Evidence(source_text="Vehicle Fleet Tracker: Real-time telemetry dashboard built with Flask and Redis.", source_section="Projects", confidence_score=0.92, page_number=2, evidence_type="project")
    ev_cert = Evidence(source_text="AWS Certified Solutions Architect by Amazon Web Services (2023)", source_section="Certifications", confidence_score=1.0, page_number=2, evidence_type="certification")

    skill_python = CandidateSkill(name="Python", raw_name="Python", category="language", evidence=ev_skill)
    skill_flask = CandidateSkill(name="Flask", raw_name="Flask", category="framework", evidence=ev_skill)
    skill_docker = CandidateSkill(name="Docker", raw_name="Docker", category="devops", evidence=ev_skill)

    exp = CandidateExperience(
        role="Lead Backend Engineer",
        company="CloudScale Tech",
        start_date="Jan 2021",
        end_date="Present",
        is_current=True,
        duration_months=36.0,
        description="Architected distributed microservices in Python and Flask.\nOptimized database queries reducing latency by 45%.\nMentored 6 junior engineers.",
        technologies=["Python", "Flask", "PostgreSQL"],
        evidence=ev_exp
    )

    edu = CandidateEducation(
        degree="Bachelor of Science",
        field_of_study="Computer Science",
        institution="Stanford University",
        start_date="2016",
        end_date="2020",
        grade_or_gpa="3.85",
        evidence=ev_edu
    )

    proj = CandidateProject(
        name="Vehicle Fleet Tracker",
        description="Real-time telemetry dashboard built with Flask and Redis.\nProcessed 100k events/sec with zero downtime.",
        technologies=["Flask", "Redis"],
        evidence=ev_proj
    )

    cert = CandidateCertification(
        name="AWS Certified Solutions Architect",
        issuer="Amazon Web Services",
        date="2023",
        evidence=ev_cert
    )

    return CandidateProfile(
        candidate_id=cid,
        filename="rich_resume.pdf",
        name="Morgan Vance",
        email="morgan.vance@example.com",
        phone="555-0144",
        summary="Distributed systems specialist with 3+ years architecting high-throughput backend services in Python.",
        sections={
            "summary": "Distributed systems specialist...",
            "skills": "Python, Flask, Docker, PostgreSQL",
            "experience": "Lead Backend Engineer at CloudScale Tech",
            "education": "BS in CS from Stanford University",
            "projects": "Vehicle Fleet Tracker",
            "certifications": "AWS Solutions Architect"
        },
        skills=["Python", "Flask", "Docker", "PostgreSQL", "Redis"],
        technologies=["Python", "Flask", "Docker", "PostgreSQL", "Redis"],
        skill_details=[skill_python, skill_flask, skill_docker],
        experience=[exp],
        education=[edu],
        certifications=[cert],
        projects=[proj],
        evidence=[ev_skill, ev_exp, ev_edu, ev_proj, ev_cert],
        raw_text="Morgan Vance\nDistributed systems specialist\nPython, Flask, Docker\nLead Backend Engineer at CloudScale Tech\nReduced latency by 45%"
    )

# 1. Same resume -> same evidence IDs
def test_same_resume_deterministic_evidence_ids(rich_candidate_profile):
    vault_service = EvidenceVaultService()
    vault1 = vault_service.build_vault(rich_candidate_profile)
    vault2 = vault_service.build_vault(rich_candidate_profile)

    assert vault1.total_items == vault2.total_items
    assert len(vault1.items) > 0

    ids1 = [it.evidence_id for it in vault1.items]
    ids2 = [it.evidence_id for it in vault2.items]
    assert ids1 == ids2, "Evidence IDs must be 100% deterministic across repeated parsing of the same profile."

# 2. Evidence source text is preserved verbatim
def test_evidence_source_text_preserved(rich_candidate_profile):
    vault_service = EvidenceVaultService()
    vault = vault_service.build_vault(rich_candidate_profile)

    texts = [it.source_text for it in vault.items]
    assert any("Lead Backend Engineer at CloudScale Tech" in t for t in texts)
    assert any("Stanford University" in t for t in texts)
    assert any("Vehicle Fleet Tracker" in t for t in texts)
    assert any("AWS Certified Solutions Architect" in t for t in texts)

# 3. Page numbers are preserved
def test_page_numbers_preserved(rich_candidate_profile):
    vault_service = EvidenceVaultService()
    vault = vault_service.build_vault(rich_candidate_profile)

    # Page 1 (skills, experience) and Page 2 (education, project, cert)
    page_numbers = {it.page_number for it in vault.items}
    assert 1 in page_numbers
    assert 2 in page_numbers

# 4. Section names are preserved
def test_section_names_preserved(rich_candidate_profile):
    vault_service = EvidenceVaultService()
    vault = vault_service.build_vault(rich_candidate_profile)

    sections = {it.source_section for it in vault.items if it.source_section}
    assert "Skills" in sections
    assert "Experience" in sections
    assert "Education" in sections
    assert "Projects" in sections
    assert "Certifications" in sections

# 5. Unsupported facts are not created & No-hallucination validation
def test_no_unsupported_facts_and_claim_validation(rich_candidate_profile):
    vault_service = EvidenceVaultService()
    validator = EvidenceValidationService()
    vault = vault_service.build_vault(rich_candidate_profile)

    # Check normalized facts in items: only contains supported facts
    for item in vault.items:
        for fact in item.normalized_facts:
            # Fact must be substring of source text or known technology
            assert fact.lower() in item.source_text.lower() or fact in item.related_technologies

    # Positive claim verification
    res_flask = validator.validate_claim(vault, "Flask")
    assert res_flask.supported is True
    assert len(res_flask.supporting_evidence_ids) >= 1

    res_metric = validator.validate_claim(vault, "Optimized database queries reducing latency by 45%")
    assert res_metric.supported is True

    # Negative claim verification (unsupported claims MUST be rejected)
    res_k8s = validator.validate_claim(vault, "Kubernetes")
    assert res_k8s.supported is False
    assert "no supporting evidence" in res_k8s.explanation.lower() or "not found" in res_k8s.explanation.lower()

    res_fake_metric = validator.validate_claim(vault, "Improved performance by 90%")
    assert res_fake_metric.supported is False
    assert "90%" in res_fake_metric.explanation

# 6. Duplicate evidence is controlled
def test_duplicate_evidence_controlled(rich_candidate_profile):
    vault_service = EvidenceVaultService()
    vault = vault_service.build_vault(rich_candidate_profile)

    ids = [it.evidence_id for it in vault.items]
    assert len(ids) == len(set(ids)), "Evidence vault must not contain duplicate evidence IDs."

# 7. Missing sections handled gracefully
def test_missing_sections_handled_gracefully():
    vault_service = EvidenceVaultService()
    twin_service = CareerTwinService()

    minimal_profile = CandidateProfile(
        candidate_id="cand_minimal",
        name="Taylor Quick",
        raw_text="Taylor Quick\nSoftware Developer"
    )

    vault = vault_service.build_vault(minimal_profile)
    twin = twin_service.build_twin(minimal_profile, vault)

    assert vault.total_items == 0
    assert twin.candidate_id == "cand_minimal"
    assert len(twin.skills) == 0
    assert len(twin.experience) == 0
    assert len(twin.projects) == 0
    assert len(twin.education) == 0

# 8. Resume with no projects works
def test_resume_with_no_projects_works(rich_candidate_profile):
    rich_candidate_profile.projects = []
    vault_service = EvidenceVaultService()
    twin_service = CareerTwinService()

    vault = vault_service.build_vault(rich_candidate_profile)
    twin = twin_service.build_twin(rich_candidate_profile, vault)

    assert len(twin.projects) == 0
    assert len(twin.project_nodes) == 0
    assert len(twin.experience) > 0

# 9. Resume with no experience works
def test_resume_with_no_experience_works(rich_candidate_profile):
    rich_candidate_profile.experience = []
    vault_service = EvidenceVaultService()
    twin_service = CareerTwinService()

    vault = vault_service.build_vault(rich_candidate_profile)
    twin = twin_service.build_twin(rich_candidate_profile, vault)

    assert len(twin.experience) == 0
    assert twin.total_experience_months == 0.0
    assert len(twin.projects) > 0

# 10. Resume with no education works
def test_resume_with_no_education_works(rich_candidate_profile):
    rich_candidate_profile.education = []
    vault_service = EvidenceVaultService()
    twin_service = CareerTwinService()

    vault = vault_service.build_vault(rich_candidate_profile)
    twin = twin_service.build_twin(rich_candidate_profile, vault)

    assert len(twin.education) == 0
    assert len(twin.skills) > 0

# 11. Resume with unusual section ordering works
def test_resume_with_unusual_section_ordering_works(rich_candidate_profile):
    rich_candidate_profile.sections = {
        "education": "Stanford BS",
        "certifications": "AWS Cert",
        "skills": "Python, Flask",
        "experience": "Lead Engineer",
    }
    vault_service = EvidenceVaultService()
    twin_service = CareerTwinService()

    vault = vault_service.build_vault(rich_candidate_profile)
    twin = twin_service.build_twin(rich_candidate_profile, vault)

    assert vault.total_items > 0
    assert len(twin.timeline) > 0
    assert twin.name == "Morgan Vance"

# 12. EvidenceValidationService helpers
def test_evidence_validation_service_helpers(rich_candidate_profile):
    vault_service = EvidenceVaultService()
    validator = EvidenceValidationService()
    vault = vault_service.build_vault(rich_candidate_profile)

    skill_ev = validator.get_evidence_for_skill(vault, "Python")
    assert len(skill_ev) >= 1

    proj_ev = validator.get_evidence_for_project(vault, "Vehicle Fleet Tracker")
    assert len(proj_ev) >= 1

    exp_ev = validator.get_evidence_for_experience(vault, "CloudScale Tech")
    assert len(exp_ev) >= 1

# 13. Persistence idempotency
def test_sqlite_persistence_idempotency(rich_candidate_profile):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    repo = Repository(db)
    vault_service = EvidenceVaultService()
    twin_service = CareerTwinService()

    vault = vault_service.build_vault(rich_candidate_profile)
    twin = twin_service.build_twin(rich_candidate_profile, vault)
    items = [it.model_dump() for it in vault.items]

    # Save once
    repo.save_candidate_profile(twin.candidate_id, twin.name, twin.email, twin.phone, twin.summary, twin.model_dump())
    repo.save_resume(twin.candidate_id, "rich_resume.pdf", 2, 1024, twin.raw_text or "")
    saved_batch1 = repo.save_evidence_batch(twin.candidate_id, items)

    # Save second time (reprocessing)
    repo.save_candidate_profile(twin.candidate_id, twin.name, twin.email, twin.phone, twin.summary, twin.model_dump())
    repo.save_resume(twin.candidate_id, "rich_resume.pdf", 2, 1024, twin.raw_text or "")
    saved_batch2 = repo.save_evidence_batch(twin.candidate_id, items)

    all_evidence = repo.get_evidence_for_candidate(twin.candidate_id)
    all_resumes = repo.get_resumes_for_candidate(twin.candidate_id)

    assert len(all_resumes) == 1, "Reprocessing same resume must update existing record without duplicating."
    assert len(all_evidence) == len(items), "Evidence batch must be idempotent without duplicates."

# 14. API: Career Twin and Evidence Querying
def test_career_twin_and_evidence_api(rich_candidate_profile):
    # Prime in-memory state
    from app.api.routes import coach as coach_routes
    vault_service = EvidenceVaultService()
    twin_service = CareerTwinService()

    vault = vault_service.build_vault(rich_candidate_profile)
    twin = twin_service.build_twin(rich_candidate_profile, vault)

    cid = rich_candidate_profile.candidate_id
    coach_routes._in_memory_profiles[cid] = rich_candidate_profile
    coach_routes._in_memory_twins[cid] = twin
    coach_routes._in_memory_vaults[cid] = vault

    # 1. Query Career Twin
    resp_twin = client.post("/api/coach/career-twin", json={"candidate_id": cid})
    assert resp_twin.status_code == 200
    data_twin = resp_twin.json()
    assert data_twin["career_twin"]["name"] == "Morgan Vance"
    assert "evidence_summary" in data_twin
    assert data_twin["evidence_summary"]["total"] == vault.total_items

    # 2. Query Evidence Vault with filters
    resp_ev_all = client.get(f"/api/coach/evidence/{cid}")
    assert resp_ev_all.status_code == 200
    assert resp_ev_all.json()["total"] == vault.total_items

    # Filter by skill
    resp_ev_skill = client.get(f"/api/coach/evidence/{cid}?skill=Python")
    assert resp_ev_skill.status_code == 200
    assert resp_ev_skill.json()["total"] >= 1
    assert all("python" in str(item).lower() for item in resp_ev_skill.json()["evidence"])

    # Filter by type
    resp_ev_type = client.get(f"/api/coach/evidence/{cid}?type=EDUCATION")
    assert resp_ev_type.status_code == 200
    assert resp_ev_type.json()["total"] >= 1
    assert all(item["evidence_type"].upper() == "EDUCATION" for item in resp_ev_type.json()["evidence"])

    # 3. Validate Claim Endpoint
    resp_val_pos = client.post("/api/coach/evidence/validate", json={"candidate_id": cid, "claim": "Flask"})
    assert resp_val_pos.status_code == 200
    assert resp_val_pos.json()["supported"] is True

    resp_val_neg = client.post("/api/coach/evidence/validate", json={"candidate_id": cid, "claim": "Kubernetes"})
    assert resp_val_neg.status_code == 200
    assert resp_val_neg.json()["supported"] is False
