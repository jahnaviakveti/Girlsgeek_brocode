import copy
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.schemas.candidate import (
    CandidateProfile,
    CandidateExperience,
    CandidateProject,
    CandidateSkill,
)
from app.schemas.domain import Evidence
from app.schemas.career_twin import CareerTwin
from app.schemas.evidence_vault import EvidenceVault
from app.schemas.resume_coach import (
    ResumeCoachRequest,
    ResumeCoachResponse,
    ResumeCoachStatus,
)
from app.services.coach.career_twin import CareerTwinService
from app.services.coach.evidence import EvidenceVaultService, EvidenceValidationService
from app.services.coach.llm import MockLLMProvider, set_llm_provider
from app.services.coach.resume import ResumeCoachService
from app.db.database import Base
from app.db.repository import Repository

client = TestClient(app)

@pytest.fixture
def alex_profile():
    cid = "cand_alex_p4"
    ev1 = Evidence(
        source_text="Python, Flask, and PostgreSQL backend development",
        source_section="Skills",
        confidence_score=1.0,
        page_number=1,
        evidence_type="skill"
    )
    ev2 = Evidence(
        source_text="Backend Engineer at Acme Corp (Jan 2022 - Present). Developed Python services with Flask.",
        source_section="Experience",
        confidence_score=0.95,
        page_number=1,
        evidence_type="experience"
    )
    ev3 = Evidence(
        source_text="Built Flask backend microservices for automated payment processing.\nOptimized SQL queries reducing latency by 30%.",
        source_section="Projects",
        confidence_score=0.92,
        page_number=2,
        evidence_type="project"
    )

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
        description="Developed Python services with Flask and PostgreSQL. Handled financial transactions.",
        technologies=["Python", "Flask", "PostgreSQL"],
        evidence=ev2
    )

    proj = CandidateProject(
        name="Payment Processing Engine",
        description="Built Flask backend microservices for automated payment processing.\nOptimized SQL queries reducing latency by 30%.",
        technologies=["Python", "Flask", "PostgreSQL"],
        evidence=ev3
    )

    profile = CandidateProfile(
        candidate_id=cid,
        filename="alex_resume.pdf",
        name="Alex Chen",
        email="alex.chen@example.com",
        phone="555-0188",
        summary="Backend developer with experience in Python and Flask.",
        sections={
            "skills": "Python, Flask, PostgreSQL",
            "experience": "Backend Engineer at Acme Corp",
            "projects": "Payment Processing Engine"
        },
        skills=["Python", "Flask", "PostgreSQL"],
        technologies=["Python", "Flask", "PostgreSQL"],
        skill_details=[skill_python, skill_flask, skill_sql],
        experience=[exp],
        projects=[proj],
        evidence=[ev1, ev2, ev3],
        raw_text="Alex Chen\nBackend developer with experience in Python and Flask.\nBackend Engineer at Acme Corp\nPayment Processing Engine"
    )
    return profile

@pytest.fixture
def alex_twin_and_vault(alex_profile):
    vault_service = EvidenceVaultService()
    twin_service = CareerTwinService()
    vault = vault_service.build_vault(alex_profile)
    twin = twin_service.build_twin(alex_profile, vault)
    return twin, vault

# 1. visibility gap produces rewrite
def test_visibility_gap_produces_rewrite(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    mock_llm = MockLLMProvider(mode="safe_rewrite")
    service = ResumeCoachService(llm_provider=mock_llm)

    ev_flask = [it.evidence_id for it in vault.items if "flask" in it.source_text.lower()]
    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_flask_api",
        requirement_text="REST API development using Flask",
        target_role="Backend Engineer",
        priority="REQUIRED",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=ev_flask,
        existing_evidence_snippets=["Built Flask backend microservices for automated payment processing."],
        missing_elements=["REST API"],
        current_resume_text="Built Flask backend microservices for automated payment processing.",
        action_prompt="Explicitly surface REST API development within your Flask backend work."
    )

    resp = service.generate_rewrite(req, twin, vault)
    assert resp.status == ResumeCoachStatus.ACCEPTED
    assert resp.suggested_text is not None
    assert len(resp.evidence_used) > 0
    assert len(resp.unsupported_claims) == 0

# 2. experience gap produces NO_SAFE_REWRITE
def test_experience_gap_produces_no_safe_rewrite(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    mock_llm = MockLLMProvider(mode="safe_rewrite")
    service = ResumeCoachService(llm_provider=mock_llm)

    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_k8s",
        requirement_text="Kubernetes cluster orchestration and Helm deployments",
        target_role="DevOps Engineer",
        priority="REQUIRED",
        gap_type="EXPERIENCE_GAP",
        evidence_ids=[],
        existing_evidence_snippets=[],
        missing_elements=["Kubernetes", "Helm"],
        current_resume_text="Developed Python services with Flask.",
        action_prompt="No verified evidence exists."
    )

    resp = service.generate_rewrite(req, twin, vault)
    assert resp.status == ResumeCoachStatus.NO_SAFE_REWRITE
    assert resp.suggested_text is None
    assert resp.can_rewrite is False
    assert "No verified evidence supports" in resp.explanation

# 3. unsupported technology is rejected
def test_unsupported_technology_is_rejected(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    mock_llm = MockLLMProvider(mode="unsupported_tech")
    service = ResumeCoachService(llm_provider=mock_llm)

    ev_flask = [it.evidence_id for it in vault.items if "flask" in it.source_text.lower()]
    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_flask",
        requirement_text="Backend development",
        target_role="Backend Engineer",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=ev_flask,
        existing_evidence_snippets=["Built Flask backend microservices."],
        current_resume_text="Built Flask backend microservices."
    )

    resp = service.generate_rewrite(req, twin, vault)
    assert resp.status == ResumeCoachStatus.REJECTED
    assert len(resp.unsupported_claims) > 0
    assert any("technology" in c.lower() or "kubernetes" in c.lower() or "docker" in c.lower() for c in resp.unsupported_claims)

# 4. unsupported metric is rejected
def test_unsupported_metric_is_rejected(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    mock_llm = MockLLMProvider(mode="unsupported_metric")
    service = ResumeCoachService(llm_provider=mock_llm)

    ev_flask = [it.evidence_id for it in vault.items if "flask" in it.source_text.lower()]
    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_flask",
        requirement_text="Performance optimization",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=ev_flask,
        existing_evidence_snippets=["Built Flask backend microservices."],
        current_resume_text="Built Flask backend microservices."
    )

    resp = service.generate_rewrite(req, twin, vault)
    assert resp.status == ResumeCoachStatus.REJECTED
    assert len(resp.unsupported_claims) > 0
    assert any("metric" in c.lower() or "45%" in c for c in resp.unsupported_claims)

# 5. unsupported responsibility is rejected
def test_unsupported_responsibility_is_rejected(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    mock_llm = MockLLMProvider(mode="unsupported_responsibility")
    service = ResumeCoachService(llm_provider=mock_llm)

    ev_flask = [it.evidence_id for it in vault.items if "flask" in it.source_text.lower()]
    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_leadership",
        requirement_text="Lead Architect role",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=ev_flask,
        existing_evidence_snippets=["Built Flask backend microservices."],
        current_resume_text="Built Flask backend microservices."
    )

    resp = service.generate_rewrite(req, twin, vault)
    assert resp.status == ResumeCoachStatus.REJECTED
    assert any("seniority" in c.lower() or "architect" in c.lower() for c in resp.unsupported_claims)

# 6. unsupported organization is rejected
def test_unsupported_organization_is_rejected(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    mock_llm = MockLLMProvider(mode="unsupported_org")
    service = ResumeCoachService(llm_provider=mock_llm)

    ev_flask = [it.evidence_id for it in vault.items if "flask" in it.source_text.lower()]
    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_org",
        requirement_text="Enterprise collaboration",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=ev_flask,
        existing_evidence_snippets=["Built Flask backend microservices."],
        current_resume_text="Built Flask backend microservices."
    )

    resp = service.generate_rewrite(req, twin, vault)
    assert resp.status == ResumeCoachStatus.REJECTED
    assert any("organization" in c.lower() or "google" in c.lower() for c in resp.unsupported_claims)

# 7. valid rewrite is accepted
def test_valid_rewrite_is_accepted(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    mock_llm = MockLLMProvider(mode="safe_rewrite")
    service = ResumeCoachService(llm_provider=mock_llm)

    ev_flask = [it.evidence_id for it in vault.items if "flask" in it.source_text.lower()]
    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_api",
        requirement_text="Python and Flask microservices",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=ev_flask,
        existing_evidence_snippets=["Built Flask backend microservices for automated payment processing."],
        current_resume_text="Built Flask backend microservices."
    )

    resp = service.generate_rewrite(req, twin, vault)
    assert resp.status == ResumeCoachStatus.ACCEPTED
    assert resp.suggested_text is not None
    assert len(resp.changes) > 0

# 8. every accepted rewrite has evidence IDs
def test_every_accepted_rewrite_has_evidence_ids(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    mock_llm = MockLLMProvider(mode="safe_rewrite")
    service = ResumeCoachService(llm_provider=mock_llm)

    ev_flask = [it.evidence_id for it in vault.items if "flask" in it.source_text.lower()]
    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_api",
        requirement_text="Flask backend development",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=ev_flask,
        existing_evidence_snippets=["Built Flask backend microservices for automated payment processing."],
        current_resume_text="Built Flask backend microservices."
    )

    resp = service.generate_rewrite(req, twin, vault)
    assert resp.status == ResumeCoachStatus.ACCEPTED
    assert len(resp.evidence_used) > 0
    for citation in resp.evidence_used:
        assert citation.evidence_id is not None
        assert len(citation.evidence_id) > 0

# 9. every accepted claim maps to evidence
def test_every_accepted_claim_maps_to_evidence(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    mock_llm = MockLLMProvider(mode="safe_rewrite")
    service = ResumeCoachService(llm_provider=mock_llm)

    ev_flask = [it.evidence_id for it in vault.items if "flask" in it.source_text.lower()]
    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_api",
        requirement_text="Flask development",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=ev_flask,
        existing_evidence_snippets=["Built Flask backend microservices for automated payment processing."],
        current_resume_text="Built Flask backend microservices."
    )

    resp = service.generate_rewrite(req, twin, vault)
    assert resp.status == ResumeCoachStatus.ACCEPTED
    for claim_detail in resp.validation:
        assert claim_detail.supported is True
        assert len(claim_detail.supporting_evidence_ids) > 0

# 10. multi-claim rewrite validation
def test_multi_claim_rewrite_validation(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    # Alex's resume actually contains 30% latency reduction in proj!
    mock_llm = MockLLMProvider(mode="multi_claims")
    service = ResumeCoachService(llm_provider=mock_llm)

    ev_all = [it.evidence_id for it in vault.items]
    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_full",
        requirement_text="Flask microservices and SQL performance",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=ev_all,
        existing_evidence_snippets=["Built Flask backend microservices.", "Optimized SQL queries reducing latency by 30%."],
        current_resume_text="Built Flask backend microservices."
    )

    resp = service.generate_rewrite(req, twin, vault)
    assert resp.status == ResumeCoachStatus.ACCEPTED
    assert len(resp.validation) >= 2
    assert all(c.supported for c in resp.validation)

# 11. empty LLM output
def test_empty_llm_output_handled_safely(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    mock_llm = MockLLMProvider(mode="empty")
    service = ResumeCoachService(llm_provider=mock_llm)

    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_empty",
        requirement_text="Flask",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=[vault.items[0].evidence_id],
        existing_evidence_snippets=["Flask backend."],
        current_resume_text="Flask backend."
    )

    resp = service.generate_rewrite(req, twin, vault)
    assert resp.status == ResumeCoachStatus.NO_SAFE_REWRITE
    assert resp.suggested_text is None

# 12. malformed LLM output
def test_malformed_llm_output_handled_safely(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    mock_llm = MockLLMProvider(mode="malformed")
    service = ResumeCoachService(llm_provider=mock_llm)

    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_malformed",
        requirement_text="Flask",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=[vault.items[0].evidence_id],
        existing_evidence_snippets=["Flask backend."],
        current_resume_text="Flask backend."
    )

    resp = service.generate_rewrite(req, twin, vault)
    assert resp.status == ResumeCoachStatus.REJECTED
    assert "malformed" in resp.explanation.lower()

# 13. candidate ID mismatch / missing in API route
def test_candidate_id_mismatch_api_route():
    resp = client.post(
        "/api/coach/resume-coach",
        json={
            "candidate_id": "non_existent_candidate_9999",
            "requirement_id": "req_1",
            "requirement_text": "Python",
            "gap_type": "RESUME_VISIBILITY_GAP"
        }
    )
    assert resp.status_code == 404

# 14. evidence ID mismatch handled gracefully
def test_evidence_id_mismatch_handled_gracefully(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    mock_llm = MockLLMProvider(mode="safe_rewrite")
    service = ResumeCoachService(llm_provider=mock_llm)

    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_mismatch",
        requirement_text="Python",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=["ev_fake_999999"],
        existing_evidence_snippets=[],
        current_resume_text="Python developer"
    )

    resp = service.generate_rewrite(req, twin, vault)
    # When evidence IDs don't match any vault item and no snippets provided, should yield NO_SAFE_REWRITE
    assert resp.status == ResumeCoachStatus.NO_SAFE_REWRITE

# 15. stale evidence / empty vault handled safely
def test_empty_vault_handled_safely(alex_profile):
    twin_service = CareerTwinService()
    empty_vault = EvidenceVault(vault_id="v_empty_p4", candidate_id=alex_profile.candidate_id, items=[])
    twin = twin_service.build_twin(alex_profile, empty_vault)
    mock_llm = MockLLMProvider(mode="safe_rewrite")
    service = ResumeCoachService(llm_provider=mock_llm)

    req = ResumeCoachRequest(
        candidate_id=alex_profile.candidate_id,
        requirement_id="req_any",
        requirement_text="Python",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=[],
        existing_evidence_snippets=[],
        current_resume_text="Python"
    )

    resp = service.generate_rewrite(req, twin, empty_vault)
    assert resp.status == ResumeCoachStatus.NO_SAFE_REWRITE

# 16. original resume preserved
def test_original_resume_preserved(alex_twin_and_vault, alex_profile):
    twin, vault = alex_twin_and_vault
    original_raw_text = alex_profile.raw_text
    mock_llm = MockLLMProvider(mode="safe_rewrite")
    service = ResumeCoachService(llm_provider=mock_llm)

    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_preserve",
        requirement_text="Flask backend development",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=[vault.items[0].evidence_id],
        existing_evidence_snippets=["Built Flask backend."],
        current_resume_text="Built Flask backend."
    )

    resp = service.generate_rewrite(req, twin, vault)
    assert resp.status == ResumeCoachStatus.ACCEPTED
    assert alex_profile.raw_text == original_raw_text

# 17. no mutation of Evidence Vault
def test_no_mutation_of_evidence_vault(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    vault_item_count_before = len(vault.items)
    vault_dump_before = copy.deepcopy(vault.model_dump())

    mock_llm = MockLLMProvider(mode="safe_rewrite")
    service = ResumeCoachService(llm_provider=mock_llm)

    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_test",
        requirement_text="Flask microservices",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=[vault.items[0].evidence_id],
        existing_evidence_snippets=["Built Flask backend."],
        current_resume_text="Built Flask backend."
    )

    resp = service.generate_rewrite(req, twin, vault)
    assert resp.status == ResumeCoachStatus.ACCEPTED
    assert len(vault.items) == vault_item_count_before
    assert vault.model_dump() == vault_dump_before

# 18. no mutation of Career Twin
def test_no_mutation_of_career_twin(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    twin_dump_before = copy.deepcopy(twin.model_dump())

    mock_llm = MockLLMProvider(mode="safe_rewrite")
    service = ResumeCoachService(llm_provider=mock_llm)

    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_test",
        requirement_text="Flask microservices",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=[vault.items[0].evidence_id],
        existing_evidence_snippets=["Built Flask backend."],
        current_resume_text="Built Flask backend."
    )

    resp = service.generate_rewrite(req, twin, vault)
    assert resp.status == ResumeCoachStatus.ACCEPTED
    assert twin.model_dump() == twin_dump_before

# 19. provider failure handled safely
def test_provider_failure_handled_safely(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    mock_llm = MockLLMProvider(mode="error")
    service = ResumeCoachService(llm_provider=mock_llm)

    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_err",
        requirement_text="Flask",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=[vault.items[0].evidence_id],
        existing_evidence_snippets=["Built Flask backend."],
        current_resume_text="Built Flask backend."
    )

    resp = service.generate_rewrite(req, twin, vault)
    assert resp.status == ResumeCoachStatus.NO_SAFE_REWRITE
    assert "provider error" in resp.explanation.lower()

# 20. deterministic mock provider (test modes and repeatability)
def test_deterministic_mock_provider(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    mock_llm = MockLLMProvider(mode="safe_rewrite")
    service = ResumeCoachService(llm_provider=mock_llm)

    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_det",
        requirement_text="Flask services",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=[vault.items[0].evidence_id],
        existing_evidence_snippets=["Built Flask backend microservices for automated payment processing."],
        current_resume_text="Built Flask backend microservices."
    )

    resp1 = service.generate_rewrite(req, twin, vault)
    resp2 = service.generate_rewrite(req, twin, vault)
    assert resp1.status == resp2.status == ResumeCoachStatus.ACCEPTED
    assert resp1.suggested_text == resp2.suggested_text

# 21. unsupported efficiency claim -> REJECTED
def test_unsupported_efficiency_claim_rejected(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    mock_llm = MockLLMProvider(mode="unsupported_efficiency")
    service = ResumeCoachService(llm_provider=mock_llm)

    ev_flask = [it.evidence_id for it in vault.items if "flask" in it.source_text.lower()]
    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_eff",
        requirement_text="Backend efficiency",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=ev_flask,
        existing_evidence_snippets=["Built Flask backend microservices for automated payment processing."],
        current_resume_text="Built Flask backend microservices for automated payment processing."
    )

    resp = service.generate_rewrite(req, twin, vault)
    assert resp.status == ResumeCoachStatus.REJECTED
    assert len(resp.unsupported_claims) > 0
    assert any("efficiency" in c.lower() for c in resp.unsupported_claims)

# 22. unsupported impact claim -> REJECTED
def test_unsupported_impact_claim_rejected(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    mock_llm = MockLLMProvider(mode="unsupported_impact")
    service = ResumeCoachService(llm_provider=mock_llm)

    ev_flask = [it.evidence_id for it in vault.items if "flask" in it.source_text.lower()]
    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_impact",
        requirement_text="Financial transactions processing",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=ev_flask,
        existing_evidence_snippets=["Built Flask backend microservices for automated payment processing."],
        current_resume_text="Built Flask backend microservices for automated payment processing."
    )

    resp = service.generate_rewrite(req, twin, vault)
    assert resp.status == ResumeCoachStatus.REJECTED
    assert len(resp.unsupported_claims) > 0
    assert any("streamline" in c.lower() or "impact" in c.lower() for c in resp.unsupported_claims)

# 23. unsupported optimization claim -> REJECTED
def test_unsupported_optimization_claim_rejected(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    mock_llm = MockLLMProvider(mode="unsupported_optimization")
    service = ResumeCoachService(llm_provider=mock_llm)

    ev_flask = [it.evidence_id for it in vault.items if "flask" in it.source_text.lower()]
    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_opt",
        requirement_text="Performance optimization",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=ev_flask,
        existing_evidence_snippets=["Built Flask backend microservices for automated payment processing."],
        current_resume_text="Built Flask backend microservices for automated payment processing."
    )

    resp = service.generate_rewrite(req, twin, vault)
    assert resp.status == ResumeCoachStatus.REJECTED
    assert len(resp.unsupported_claims) > 0
    assert any("performance" in c.lower() or "optimization" in c.lower() for c in resp.unsupported_claims)

# 24. explicitly evidenced impact claim -> ACCEPTED
def test_explicitly_evidenced_impact_claim_accepted(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    # Alex's evidence vault (ev3) explicitly contains:
    # "Built Flask backend microservices for automated payment processing.\nOptimized SQL queries reducing latency by 30%."
    mock_llm = MockLLMProvider(mode="multi_claims")
    service = ResumeCoachService(llm_provider=mock_llm)

    ev_all = [it.evidence_id for it in vault.items]
    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_evidenced_impact",
        requirement_text="Database query optimization and latency reduction",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=ev_all,
        existing_evidence_snippets=[
            "Built Flask backend microservices for automated payment processing.",
            "Optimized SQL queries reducing latency by 30%."
        ],
        current_resume_text="Built Flask backend microservices for automated payment processing."
    )

    resp = service.generate_rewrite(req, twin, vault)
    assert resp.status == ResumeCoachStatus.ACCEPTED
    assert resp.suggested_text is not None
    assert len(resp.unsupported_claims) == 0
    assert len(resp.evidence_used) > 0
    assert any("latency" in cit.source_text.lower() or "sql" in cit.source_text.lower() for cit in resp.evidence_used)

# 25. existing safe rewrite -> ACCEPTED
def test_existing_safe_rewrite_accepted(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    mock_llm = MockLLMProvider(mode="safe_rewrite")
    service = ResumeCoachService(llm_provider=mock_llm)

    ev_flask = [it.evidence_id for it in vault.items if "flask" in it.source_text.lower()]
    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_safe",
        requirement_text="Microservice development",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=ev_flask,
        existing_evidence_snippets=["Built Flask backend microservices for automated payment processing."],
        current_resume_text="Built Flask backend microservices for automated payment processing."
    )

    resp = service.generate_rewrite(req, twin, vault)
    assert resp.status == ResumeCoachStatus.ACCEPTED
    assert resp.suggested_text == "Engineered Flask backend microservices for automated payment processing."
    assert len(resp.unsupported_claims) == 0
    assert len(resp.evidence_used) > 0
