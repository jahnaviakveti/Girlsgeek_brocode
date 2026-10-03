import copy
import json
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
from app.schemas.evidence_vault import EvidenceVault, VaultEvidenceItem
from app.schemas.resume_coach import (
    ResumeCoachRequest,
    ResumeCoachResponse,
    ResumeCoachStatus,
    EvidenceCitation,
    ClaimValidationDetail,
)
from app.schemas.resume_version import (
    ResumeVersion,
    ResumeVersionStatus,
    ResumeSection,
    ResumeSectionItem,
    AcceptedSuggestion,
)
from app.services.coach.career_twin import CareerTwinService
from app.services.coach.evidence import EvidenceVaultService, EvidenceValidationService
from app.services.coach.job_fit import JobFitService
from app.services.coach.resume import ResumeCoachService
from app.services.coach.resume_builder import ResumeBuilderService
from app.services.coach.llm import MockLLMProvider
from app.db.database import Base
from app.db.repository import Repository
from app.api.routes.coach import _in_memory_twins, _in_memory_vaults, _in_memory_profiles

client = TestClient(app)

@pytest.fixture
def alex_profile():
    cid = "cand_alex_p5"
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
def sarah_profile():
    cid = "cand_sarah_p5"
    ev_sarah = Evidence(
        source_text="Senior React Frontend Developer with TypeScript at Globex",
        source_section="Experience",
        confidence_score=1.0,
        page_number=1,
        evidence_type="experience"
    )
    profile = CandidateProfile(
        candidate_id=cid,
        filename="sarah_resume.pdf",
        name="Sarah Jenkins",
        email="sarah.j@example.com",
        summary="Frontend React specialist.",
        sections={"experience": "Senior React Frontend Developer at Globex"},
        skills=["React", "TypeScript"],
        technologies=["React", "TypeScript"],
        experience=[
            CandidateExperience(
                role="Frontend Developer",
                company="Globex",
                start_date="2021",
                end_date="Present",
                description="Built React frontends with TypeScript.",
                evidence=ev_sarah
            )
        ],
        evidence=[ev_sarah],
        raw_text="Sarah Jenkins\nSenior React Frontend Developer"
    )
    return profile

@pytest.fixture
def alex_twin_and_vault(alex_profile):
    vault_service = EvidenceVaultService()
    twin_service = CareerTwinService()
    vault = vault_service.build_vault(alex_profile)
    twin = twin_service.build_twin(alex_profile, vault)
    _in_memory_profiles[alex_profile.candidate_id] = alex_profile
    _in_memory_twins[alex_profile.candidate_id] = twin
    _in_memory_vaults[alex_profile.candidate_id] = vault
    return twin, vault

@pytest.fixture
def sarah_twin_and_vault(sarah_profile):
    vault_service = EvidenceVaultService()
    twin_service = CareerTwinService()
    vault = vault_service.build_vault(sarah_profile)
    twin = twin_service.build_twin(sarah_profile, vault)
    _in_memory_profiles[sarah_profile.candidate_id] = sarah_profile
    _in_memory_twins[sarah_profile.candidate_id] = twin
    _in_memory_vaults[sarah_profile.candidate_id] = vault
    return twin, vault

@pytest.fixture
def resume_builder():
    return ResumeBuilderService()

# ---------------------------------------------------------------------------
# 1. Create resume version
# ---------------------------------------------------------------------------
def test_create_initial_resume_version(alex_twin_and_vault, resume_builder):
    twin, vault = alex_twin_and_vault
    version = resume_builder.create_initial_version_from_twin(twin, vault)

    assert version.version_id.startswith("ver_orig_")
    assert version.candidate_id == twin.candidate_id
    assert version.parent_version_id is None
    assert version.status == ResumeVersionStatus.ACTIVE
    assert len(version.sections) >= 3
    assert len(version.evidence_ids) > 0
    assert "Original Resume" in version.title

# ---------------------------------------------------------------------------
# 2. Original resume remains immutable
# ---------------------------------------------------------------------------
def test_original_resume_remains_immutable_on_edit(alex_twin_and_vault, resume_builder):
    twin, vault = alex_twin_and_vault
    orig_version = resume_builder.create_initial_version_from_twin(twin, vault)
    orig_snapshot = copy.deepcopy(orig_version.model_dump())

    # Create a safe accepted suggestion
    cit = EvidenceCitation(
        evidence_id=vault.items[2].evidence_id,
        source_text=vault.items[2].source_text,
        source_section="Projects"
    )
    sug = ResumeCoachResponse(
        suggestion_id="sug_safe_1",
        candidate_id=twin.candidate_id,
        requirement_id="req_flask",
        status=ResumeCoachStatus.ACCEPTED,
        original_text="Built Flask backend microservices for automated payment processing.",
        suggested_text="Engineered Flask backend microservices for automated payment processing.",
        evidence_used=[cit],
        validation=[ClaimValidationDetail(claim="Engineered Flask backend microservices for automated payment processing.", supported=True, explanation="Verified", supporting_evidence_ids=[cit.evidence_id])],
        explanation="Safe rewrite"
    )

    # Applying to orig_version must NOT mutate orig_version; it branches a new draft
    new_version, accepted = resume_builder.apply_suggestion_to_version(
        version=orig_version,
        suggestion=sug,
        vault=vault,
        candidate_id=twin.candidate_id
    )

    # Original version remains completely unchanged
    assert orig_version.model_dump() == orig_snapshot
    assert orig_version.parent_version_id is None
    assert len(orig_version.accepted_suggestions) == 0

    # New version is a DRAFT branched from orig_version
    assert new_version.version_id != orig_version.version_id
    assert new_version.parent_version_id == orig_version.version_id
    assert new_version.status == ResumeVersionStatus.DRAFT
    assert len(new_version.accepted_suggestions) == 1

# ---------------------------------------------------------------------------
# 3. Apply ACCEPTED suggestion
# ---------------------------------------------------------------------------
def test_apply_accepted_suggestion(alex_twin_and_vault, resume_builder):
    twin, vault = alex_twin_and_vault
    base = resume_builder.create_initial_version_from_twin(twin, vault)
    draft = resume_builder.create_targeted_draft(base, title="Backend Engineer Draft")

    cit = EvidenceCitation(
        evidence_id=vault.items[2].evidence_id,
        source_text=vault.items[2].source_text,
        source_section="Projects"
    )
    sug = ResumeCoachResponse(
        suggestion_id="sug_accept_1",
        candidate_id=twin.candidate_id,
        requirement_id="req_flask",
        status=ResumeCoachStatus.ACCEPTED,
        original_text="Built Flask backend microservices for automated payment processing.",
        suggested_text="Engineered Flask backend microservices for automated payment processing.",
        evidence_used=[cit],
        validation=[ClaimValidationDetail(claim="Engineered Flask backend microservices for automated payment processing.", supported=True, explanation="Verified", supporting_evidence_ids=[cit.evidence_id])],
        explanation="Verified safe rewrite"
    )

    updated_ver, accepted_sug = resume_builder.apply_suggestion_to_version(
        version=draft,
        suggestion=sug,
        vault=vault,
        candidate_id=twin.candidate_id
    )

    assert len(updated_ver.accepted_suggestions) == 1
    assert accepted_sug.validation_status == "ACCEPTED"
    assert accepted_sug.suggested_text == "Engineered Flask backend microservices for automated payment processing."
    assert cit.evidence_id in accepted_sug.evidence_ids

# ---------------------------------------------------------------------------
# 4. REJECTED suggestion cannot be applied (Server-side gate)
# ---------------------------------------------------------------------------
def test_rejected_suggestion_cannot_be_applied(alex_twin_and_vault, resume_builder):
    twin, vault = alex_twin_and_vault
    base = resume_builder.create_initial_version_from_twin(twin, vault)
    draft = resume_builder.create_targeted_draft(base)

    sug = ResumeCoachResponse(
        suggestion_id="sug_rej_1",
        candidate_id=twin.candidate_id,
        requirement_id="req_k8s",
        status=ResumeCoachStatus.REJECTED,
        original_text="Built Flask backend microservices.",
        suggested_text="Engineered Kubernetes clusters with Rust and Solidity.",
        unsupported_claims=["Unsupported technology: 'Kubernetes'"],
        explanation="Rejected due to hallucinated technology."
    )

    with pytest.raises(ValueError) as excinfo:
        resume_builder.apply_suggestion_to_version(draft, sug, vault, twin.candidate_id)
    assert "status ACCEPTED" in str(excinfo.value)
    assert len(draft.accepted_suggestions) == 0

# ---------------------------------------------------------------------------
# 5. NO_SAFE_REWRITE cannot be applied (Server-side gate)
# ---------------------------------------------------------------------------
def test_no_safe_rewrite_cannot_be_applied(alex_twin_and_vault, resume_builder):
    twin, vault = alex_twin_and_vault
    base = resume_builder.create_initial_version_from_twin(twin, vault)
    draft = resume_builder.create_targeted_draft(base)

    sug = ResumeCoachResponse(
        suggestion_id="sug_nsr_1",
        candidate_id=twin.candidate_id,
        requirement_id="req_k8s",
        status=ResumeCoachStatus.NO_SAFE_REWRITE,
        original_text="Backend services",
        suggested_text=None,
        can_rewrite=False,
        explanation="No verified evidence exists for this requirement."
    )

    with pytest.raises(ValueError) as excinfo:
        resume_builder.apply_suggestion_to_version(draft, sug, vault, twin.candidate_id)
    assert "status ACCEPTED" in str(excinfo.value)

# ---------------------------------------------------------------------------
# 6. Applied suggestion retains evidence IDs
# ---------------------------------------------------------------------------
def test_applied_suggestion_retains_evidence_ids(alex_twin_and_vault, resume_builder):
    twin, vault = alex_twin_and_vault
    base = resume_builder.create_initial_version_from_twin(twin, vault)
    draft = resume_builder.create_targeted_draft(base)

    target_ev_id = vault.items[2].evidence_id
    cit = EvidenceCitation(evidence_id=target_ev_id, source_text=vault.items[2].source_text)
    sug = ResumeCoachResponse(
        suggestion_id="sug_ev_ret",
        candidate_id=twin.candidate_id,
        requirement_id="req_flask",
        status=ResumeCoachStatus.ACCEPTED,
        original_text="Built Flask backend microservices for automated payment processing.",
        suggested_text="Engineered Flask backend microservices for automated payment processing.",
        evidence_used=[cit],
        validation=[ClaimValidationDetail(claim="Engineered Flask backend microservices for automated payment processing.", supported=True, explanation="Verified", supporting_evidence_ids=[target_ev_id])],
        explanation="Safe"
    )

    updated_ver, accepted = resume_builder.apply_suggestion_to_version(draft, sug, vault, twin.candidate_id)
    assert target_ev_id in accepted.evidence_ids
    assert target_ev_id in updated_ver.evidence_ids

# ---------------------------------------------------------------------------
# 7. Evidence ownership validation (Cross-candidate rejection)
# ---------------------------------------------------------------------------
def test_cross_candidate_evidence_rejected(alex_twin_and_vault, sarah_twin_and_vault, resume_builder):
    twin_alex, vault_alex = alex_twin_and_vault
    twin_sarah, vault_sarah = sarah_twin_and_vault

    base_alex = resume_builder.create_initial_version_from_twin(twin_alex, vault_alex)
    draft_alex = resume_builder.create_targeted_draft(base_alex)

    # Sarah's evidence
    sarah_ev = vault_sarah.items[0]
    cit_sarah = EvidenceCitation(evidence_id=sarah_ev.evidence_id, source_text=sarah_ev.source_text)

    # Malicious attempt: Alex tries to apply a suggestion citing Sarah's evidence
    sug_malicious = ResumeCoachResponse(
        suggestion_id="sug_cross_cand",
        candidate_id=twin_alex.candidate_id,
        requirement_id="req_react",
        status=ResumeCoachStatus.ACCEPTED,
        original_text="Built Flask backend microservices.",
        suggested_text="Engineered React frontend services with TypeScript.",
        evidence_used=[cit_sarah],
        explanation="Spoofed suggestion"
    )

    with pytest.raises((ValueError, PermissionError)) as excinfo:
        resume_builder.apply_suggestion_to_version(draft_alex, sug_malicious, vault_alex, twin_alex.candidate_id)
    assert "does not exist in candidate" in str(excinfo.value) or "Security violation" in str(excinfo.value)

# ---------------------------------------------------------------------------
# 8. Missing evidence prevents application
# ---------------------------------------------------------------------------
def test_missing_evidence_prevents_application(alex_twin_and_vault, resume_builder):
    twin, vault = alex_twin_and_vault
    base = resume_builder.create_initial_version_from_twin(twin, vault)
    draft = resume_builder.create_targeted_draft(base)

    sug = ResumeCoachResponse(
        suggestion_id="sug_no_ev",
        candidate_id=twin.candidate_id,
        requirement_id="req_test",
        status=ResumeCoachStatus.ACCEPTED,
        original_text="Built Flask microservices.",
        suggested_text="Engineered Flask microservices.",
        evidence_used=[],
        validation=[],
        explanation="Missing citations"
    )

    with pytest.raises(ValueError) as excinfo:
        resume_builder.apply_suggestion_to_version(draft, sug, vault, twin.candidate_id)
    assert "No verified evidence citations" in str(excinfo.value)

# ---------------------------------------------------------------------------
# 9. Stale / forged evidence ID prevents application
# ---------------------------------------------------------------------------
def test_forged_evidence_id_prevents_application(alex_twin_and_vault, resume_builder):
    twin, vault = alex_twin_and_vault
    base = resume_builder.create_initial_version_from_twin(twin, vault)
    draft = resume_builder.create_targeted_draft(base)

    fake_cit = EvidenceCitation(evidence_id="ev_forged_fake_9999", source_text="Fake claimed source text")
    sug = ResumeCoachResponse(
        suggestion_id="sug_fake_ev",
        candidate_id=twin.candidate_id,
        requirement_id="req_test",
        status=ResumeCoachStatus.ACCEPTED,
        original_text="Built Flask microservices.",
        suggested_text="Engineered Flask microservices.",
        evidence_used=[fake_cit],
        explanation="Forged evidence"
    )

    with pytest.raises(ValueError) as excinfo:
        resume_builder.apply_suggestion_to_version(draft, sug, vault, twin.candidate_id)
    assert "does not exist in candidate" in str(excinfo.value)

# ---------------------------------------------------------------------------
# 10. Candidate mismatch prevents application
# ---------------------------------------------------------------------------
def test_candidate_mismatch_prevents_application(alex_twin_and_vault, sarah_twin_and_vault, resume_builder):
    twin_alex, vault_alex = alex_twin_and_vault
    twin_sarah, vault_sarah = sarah_twin_and_vault

    base_alex = resume_builder.create_initial_version_from_twin(twin_alex, vault_alex)
    draft_alex = resume_builder.create_targeted_draft(base_alex)

    cit = EvidenceCitation(evidence_id=vault_alex.items[0].evidence_id, source_text=vault_alex.items[0].source_text)
    sug = ResumeCoachResponse(
        suggestion_id="sug_mismatch",
        candidate_id=twin_sarah.candidate_id,  # Sarah's ID on Alex's draft
        requirement_id="req_flask",
        status=ResumeCoachStatus.ACCEPTED,
        original_text="Built Flask microservices.",
        suggested_text="Engineered Flask microservices.",
        evidence_used=[cit],
        explanation="Mismatch"
    )

    with pytest.raises(PermissionError) as excinfo:
        resume_builder.apply_suggestion_to_version(draft_alex, sug, vault_alex, twin_alex.candidate_id)
    assert "Candidate ID mismatch" in str(excinfo.value)

# ---------------------------------------------------------------------------
# 11. Version parent relationship & lineage
# ---------------------------------------------------------------------------
def test_version_parent_lineage(alex_twin_and_vault, resume_builder):
    twin, vault = alex_twin_and_vault
    v1 = resume_builder.create_initial_version_from_twin(twin, vault)
    assert v1.parent_version_id is None

    v2 = resume_builder.create_targeted_draft(v1, title="Draft 2 - Backend Engineer")
    assert v2.parent_version_id == v1.version_id

    v3 = resume_builder.clone_version(v2, new_title="Draft 3 - Full Stack")
    assert v3.parent_version_id == v2.version_id

# ---------------------------------------------------------------------------
# 12. Version history tracking
# ---------------------------------------------------------------------------
def test_version_history_tracking(alex_twin_and_vault, resume_builder):
    twin, vault = alex_twin_and_vault
    v1 = resume_builder.create_initial_version_from_twin(twin, vault)
    v2 = resume_builder.create_targeted_draft(v1, target_role="Backend Engineer")

    cit = EvidenceCitation(evidence_id=vault.items[2].evidence_id, source_text=vault.items[2].source_text)
    sug = ResumeCoachResponse(
        suggestion_id="sug_hist",
        candidate_id=twin.candidate_id,
        requirement_id="req_flask",
        status=ResumeCoachStatus.ACCEPTED,
        original_text="Built Flask backend microservices for automated payment processing.",
        suggested_text="Engineered Flask backend microservices for automated payment processing.",
        evidence_used=[cit],
        explanation="Safe"
    )
    v2_updated, _ = resume_builder.apply_suggestion_to_version(v2, sug, vault, twin.candidate_id)

    diff = resume_builder.get_version_diff(v2_updated, v1, vault)
    assert diff.total_changes == 1
    assert diff.version_id == v2_updated.version_id
    assert diff.compare_to_version_id == v1.version_id

# ---------------------------------------------------------------------------
# 13. Clone previous version (Rollback)
# ---------------------------------------------------------------------------
def test_clone_previous_version(alex_twin_and_vault, resume_builder):
    twin, vault = alex_twin_and_vault
    v1 = resume_builder.create_initial_version_from_twin(twin, vault)
    v2 = resume_builder.create_targeted_draft(v1)

    # Rollback: clone v1 as a new draft v3
    v3 = resume_builder.clone_version(v1, new_title="Draft 3 Rollback to Baseline")
    assert v3.version_id != v1.version_id
    assert v3.parent_version_id == v1.version_id
    assert v3.status == ResumeVersionStatus.DRAFT
    assert len(v3.accepted_suggestions) == 0

# ---------------------------------------------------------------------------
# 14. Diff generation with BEFORE, AFTER, WHY, EVIDENCE
# ---------------------------------------------------------------------------
def test_diff_generation_structure(alex_twin_and_vault, resume_builder):
    twin, vault = alex_twin_and_vault
    base = resume_builder.create_initial_version_from_twin(twin, vault)
    draft = resume_builder.create_targeted_draft(base)

    target_ev = vault.items[2]
    cit = EvidenceCitation(
        evidence_id=target_ev.evidence_id,
        source_text=target_ev.source_text,
        source_section="Projects"
    )
    sug = ResumeCoachResponse(
        suggestion_id="sug_diff_test",
        candidate_id=twin.candidate_id,
        requirement_id="req_flask",
        status=ResumeCoachStatus.ACCEPTED,
        original_text="Built Flask backend microservices for automated payment processing.",
        suggested_text="Engineered Flask backend microservices for automated payment processing.",
        evidence_used=[cit],
        explanation="Strengthened action verb orientation"
    )

    updated_ver, _ = resume_builder.apply_suggestion_to_version(draft, sug, vault, twin.candidate_id)
    diff = resume_builder.get_version_diff(updated_ver, base, vault)

    assert diff.total_changes == 1
    item = diff.changes[0]
    assert item.before == "Built Flask backend microservices for automated payment processing."
    assert item.after == "Engineered Flask backend microservices for automated payment processing."
    assert "action verb" in item.why.lower() or "verified" in item.why.lower()
    assert len(item.evidence) > 0
    assert item.evidence[0].evidence_id == target_ev.evidence_id

# ---------------------------------------------------------------------------
# 15. Re-check Job Fit after modification
# ---------------------------------------------------------------------------
def test_recheck_job_fit_after_modification(alex_twin_and_vault, resume_builder):
    twin, vault = alex_twin_and_vault
    base = resume_builder.create_initial_version_from_twin(twin, vault)
    draft = resume_builder.create_targeted_draft(base)

    cit = EvidenceCitation(evidence_id=vault.items[2].evidence_id, source_text=vault.items[2].source_text)
    sug = ResumeCoachResponse(
        suggestion_id="sug_recheck",
        candidate_id=twin.candidate_id,
        requirement_id="req_flask_api",
        status=ResumeCoachStatus.ACCEPTED,
        original_text="Built Flask backend microservices for automated payment processing.",
        suggested_text="Engineered Flask backend microservices for automated payment processing.",
        evidence_used=[cit],
        explanation="Improved keyword clarity"
    )

    updated_ver, _ = resume_builder.apply_suggestion_to_version(draft, sug, vault, twin.candidate_id)
    job_fit_service = JobFitService()
    job_text = "Role: Backend Engineer\nRequirements:\n- Python and Flask microservice architecture\n- PostgreSQL database queries"

    recheck = resume_builder.recheck_job_fit(
        version=updated_ver,
        twin=twin,
        vault=vault,
        job_fit_service=job_fit_service,
        job_text=job_text,
        target_role="Backend Engineer",
        previous_coverage=60.0
    )

    assert recheck.version_id == updated_ver.version_id
    assert recheck.current_coverage >= 0.0
    assert recheck.previous_coverage == 60.0
    assert isinstance(recheck.coverage_delta, float)

# ---------------------------------------------------------------------------
# 16. Job Fit improvement is diagnostic only (No hiring probability)
# ---------------------------------------------------------------------------
def test_job_fit_is_diagnostic_only(alex_twin_and_vault, resume_builder):
    twin, vault = alex_twin_and_vault
    base = resume_builder.create_initial_version_from_twin(twin, vault)
    job_fit_service = JobFitService()
    recheck = resume_builder.recheck_job_fit(
        version=base,
        twin=twin,
        vault=vault,
        job_fit_service=job_fit_service,
        job_text="Backend Engineer Python Flask"
    )

    # Narrative must not predict hiring chances
    assert "does not predict hiring probability" in recheck.narrative
    assert "hiring chance" not in recheck.narrative.lower()

# ---------------------------------------------------------------------------
# 17. Export uses persisted version exactly
# ---------------------------------------------------------------------------
def test_export_uses_persisted_version_exactly(alex_twin_and_vault, resume_builder):
    twin, vault = alex_twin_and_vault
    base = resume_builder.create_initial_version_from_twin(twin, vault)

    pdf_bytes = resume_builder.export_pdf(base, candidate_name=twin.name)
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF-")

    # Read back PDF using PyMuPDF and verify candidate name and sections are present
    import pymupdf
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    assert len(doc) >= 1
    page_text = doc[0].get_text()
    assert twin.name in page_text
    doc.close()

# ---------------------------------------------------------------------------
# 18. Export does not invoke LLM
# ---------------------------------------------------------------------------
def test_export_does_not_invoke_llm(alex_twin_and_vault, resume_builder, monkeypatch):
    twin, vault = alex_twin_and_vault
    base = resume_builder.create_initial_version_from_twin(twin, vault)

    # Monkeypatch LLM provider to raise an exception if called
    def boom(*args, **kwargs):
        raise RuntimeError("LLM was invoked during PDF export!")

    monkeypatch.setattr(resume_builder.resume_coach_service.llm_provider, "generate", boom)
    monkeypatch.setattr(resume_builder.resume_coach_service.llm_provider, "generate_resume_rewrite", boom)

    # PDF generation must succeed purely deterministically
    pdf_bytes = resume_builder.export_pdf(base, candidate_name=twin.name)
    assert len(pdf_bytes) > 0

# ---------------------------------------------------------------------------
# 19. Historical versions remain unchanged across multiple updates
# ---------------------------------------------------------------------------
def test_historical_versions_remain_unchanged(alex_twin_and_vault, resume_builder):
    twin, vault = alex_twin_and_vault
    v1 = resume_builder.create_initial_version_from_twin(twin, vault)
    v1_raw = v1.raw_text

    v2 = resume_builder.create_targeted_draft(v1, title="Draft 2")
    cit = EvidenceCitation(evidence_id=vault.items[2].evidence_id, source_text=vault.items[2].source_text)
    sug = ResumeCoachResponse(
        suggestion_id="sug_multi_v",
        candidate_id=twin.candidate_id,
        requirement_id="req_flask",
        status=ResumeCoachStatus.ACCEPTED,
        original_text="Built Flask backend microservices for automated payment processing.",
        suggested_text="Engineered Flask backend microservices for automated payment processing.",
        evidence_used=[cit],
        explanation="Safe"
    )
    v2_updated, _ = resume_builder.apply_suggestion_to_version(v2, sug, vault, twin.candidate_id)

    # v1 remains completely unchanged
    assert v1.raw_text == v1_raw
    assert len(v1.accepted_suggestions) == 0
    assert len(v2_updated.accepted_suggestions) == 1

# ---------------------------------------------------------------------------
# 20. Multiple accepted suggestions on same draft
# ---------------------------------------------------------------------------
def test_multiple_accepted_suggestions_on_same_draft(alex_twin_and_vault, resume_builder):
    twin, vault = alex_twin_and_vault
    base = resume_builder.create_initial_version_from_twin(twin, vault)
    draft = resume_builder.create_targeted_draft(base)

    cit1 = EvidenceCitation(evidence_id=vault.items[2].evidence_id, source_text=vault.items[2].source_text)
    sug1 = ResumeCoachResponse(
        suggestion_id="sug_1",
        candidate_id=twin.candidate_id,
        requirement_id="req_1",
        status=ResumeCoachStatus.ACCEPTED,
        original_text="Built Flask backend microservices for automated payment processing.",
        suggested_text="Engineered Flask backend microservices for automated payment processing.",
        evidence_used=[cit1],
        explanation="Verb 1"
    )

    cit2 = EvidenceCitation(evidence_id=vault.items[1].evidence_id, source_text=vault.items[1].source_text)
    sug2 = ResumeCoachResponse(
        suggestion_id="sug_2",
        candidate_id=twin.candidate_id,
        requirement_id="req_2",
        status=ResumeCoachStatus.ACCEPTED,
        original_text="Developed Python services with Flask.",
        suggested_text="Architected Python services with Flask and PostgreSQL.",
        evidence_used=[cit2],
        explanation="Verb 2"
    )

    v, _ = resume_builder.apply_suggestion_to_version(draft, sug1, vault, twin.candidate_id)
    v, _ = resume_builder.apply_suggestion_to_version(v, sug2, vault, twin.candidate_id)

    assert len(v.accepted_suggestions) == 2
    assert v.accepted_suggestions[0].suggestion_id == "sug_1"
    assert v.accepted_suggestions[1].suggestion_id == "sug_2"

# ---------------------------------------------------------------------------
# 21. Version-level evidence lock catches ungrounded claim during apply
# ---------------------------------------------------------------------------
def test_version_level_evidence_lock_blocks_tampered_suggestion(alex_twin_and_vault, resume_builder):
    twin, vault = alex_twin_and_vault
    base = resume_builder.create_initial_version_from_twin(twin, vault)
    draft = resume_builder.create_targeted_draft(base)

    cit = EvidenceCitation(evidence_id=vault.items[2].evidence_id, source_text=vault.items[2].source_text)
    # Attacker sets status=ACCEPTED on a suggestion that introduces an ungrounded efficiency claim
    tampered_sug = ResumeCoachResponse(
        suggestion_id="sug_tampered",
        candidate_id=twin.candidate_id,
        requirement_id="req_1",
        status=ResumeCoachStatus.ACCEPTED,  # Attacker faked accepted status
        original_text="Built Flask backend microservices for automated payment processing.",
        suggested_text="Engineered Flask backend microservices, increasing efficiency across operations.",
        evidence_used=[cit],
        explanation="Tampered"
    )

    with pytest.raises(ValueError) as excinfo:
        resume_builder.apply_suggestion_to_version(draft, tampered_sug, vault, twin.candidate_id)
    assert "evidence lock failed" in str(excinfo.value).lower()

# ---------------------------------------------------------------------------
# 22. API: Create, List, and Detail Resume Versions
# ---------------------------------------------------------------------------
def test_api_resume_version_lifecycle(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault

    # Ingest in coach route memory by calling endpoints
    client.post(
        "/api/coach/resume-coach",
        json={
            "candidate_id": twin.candidate_id,
            "requirement_id": "req_1",
            "requirement_text": "Flask API",
            "gap_type": "RESUME_VISIBILITY_GAP",
            "evidence_ids": [vault.items[0].evidence_id],
            "existing_evidence_snippets": ["Python, Flask, and PostgreSQL backend development"],
            "current_resume_text": "Python, Flask, and PostgreSQL backend development"
        }
    )

    # 1. Create version via API
    res = client.post(
        "/api/coach/resume-versions",
        json={
            "candidate_id": twin.candidate_id,
            "title": "API Targeted Version",
            "target_role": "Backend Engineer"
        }
    )
    assert res.status_code == 201
    data = res.json()
    version_id = data["version_id"]
    assert data["candidate_id"] == twin.candidate_id
    assert len(data["sections"]) > 0

    # 2. List versions for candidate
    list_res = client.get(f"/api/coach/resume-versions/{twin.candidate_id}")
    assert list_res.status_code == 200
    versions = list_res.json()
    assert len(versions) >= 1
    assert any(v["version_id"] == version_id for v in versions)

    # 3. Get version detail
    detail_res = client.get(f"/api/coach/resume-versions/{twin.candidate_id}/{version_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["version_id"] == version_id

# ---------------------------------------------------------------------------
# 23. API: Apply Suggestion with Evidence Lock
# ---------------------------------------------------------------------------
def test_api_apply_suggestion_success(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault

    # Create baseline version
    v_res = client.post(
        "/api/coach/resume-versions",
        json={"candidate_id": twin.candidate_id, "title": "Base for API apply"}
    )
    ver_id = v_res.json()["version_id"]

    # Valid accepted suggestion
    ev_target = vault.items[2]
    payload = {
        "suggestion": {
            "suggestion_id": "sug_api_test",
            "candidate_id": twin.candidate_id,
            "requirement_id": "req_flask",
            "status": "ACCEPTED",
            "original_text": "Built Flask backend microservices for automated payment processing.",
            "suggested_text": "Engineered Flask backend microservices for automated payment processing.",
            "changes": ["Strengthened verb"],
            "evidence_used": [{"evidence_id": ev_target.evidence_id, "source_text": ev_target.source_text}],
            "unsupported_claims": [],
            "validation": [{"claim": "Engineered Flask backend microservices for automated payment processing.", "supported": True, "supporting_evidence_ids": [ev_target.evidence_id], "matched_facts": ["Flask"], "explanation": "Verified"}],
            "explanation": "Safe"
        },
        "create_new_version": False
    }

    apply_res = client.post(f"/api/coach/resume-versions/{ver_id}/apply-suggestion", json=payload)
    assert apply_res.status_code == 200
    res_data = apply_res.json()
    assert res_data["success"] is True
    assert res_data["total_accepted_in_version"] == 1

# ---------------------------------------------------------------------------
# 24. API: Security Gate blocks rejected suggestion
# ---------------------------------------------------------------------------
def test_api_apply_suggestion_security_gate_blocks_rejected(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    v_res = client.post(
        "/api/coach/resume-versions",
        json={"candidate_id": twin.candidate_id, "title": "Base for Security Test"}
    )
    ver_id = v_res.json()["version_id"]

    payload = {
        "suggestion": {
            "suggestion_id": "sug_bad",
            "candidate_id": twin.candidate_id,
            "requirement_id": "req_1",
            "status": "REJECTED",  # Client tries to apply rejected
            "original_text": "Built Flask services",
            "suggested_text": "Engineered Kubernetes Solidity microservices",
            "evidence_used": [{"evidence_id": vault.items[0].evidence_id, "source_text": vault.items[0].source_text}],
            "unsupported_claims": ["Unsupported technology: 'Solidity'"],
            "validation": [],
            "explanation": "Rejected"
        }
    }

    res = client.post(f"/api/coach/resume-versions/{ver_id}/apply-suggestion", json=payload)
    assert res.status_code == 400
    assert "status ACCEPTED" in res.json()["detail"]

# ---------------------------------------------------------------------------
# 25. API: Clone, Diff, and Export PDF
# ---------------------------------------------------------------------------
def test_api_clone_diff_and_export(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    v_res = client.post(
        "/api/coach/resume-versions",
        json={"candidate_id": twin.candidate_id, "title": "Base Version"}
    )
    ver_id = v_res.json()["version_id"]

    # Apply a suggestion
    ev_target = vault.items[2]
    apply_res = client.post(
        f"/api/coach/resume-versions/{ver_id}/apply-suggestion",
        json={
            "suggestion": {
                "suggestion_id": "sug_clone_test",
                "candidate_id": twin.candidate_id,
                "requirement_id": "req_flask",
                "status": "ACCEPTED",
                "original_text": "Built Flask backend microservices for automated payment processing.",
                "suggested_text": "Engineered Flask backend microservices for automated payment processing.",
                "evidence_used": [{"evidence_id": ev_target.evidence_id, "source_text": ev_target.source_text}],
                "validation": [{"claim": "Engineered Flask backend microservices for automated payment processing.", "supported": True, "supporting_evidence_ids": [ev_target.evidence_id], "matched_facts": ["Flask"], "explanation": "Verified"}],
                "explanation": "Safe"
            }
        }
    )
    assert apply_res.status_code == 200
    applied_ver_id = apply_res.json()["version_id"]

    # 1. Diff on applied draft version
    diff_res = client.get(f"/api/coach/resume-versions/{applied_ver_id}/diff")
    assert diff_res.status_code == 200
    diff_data = diff_res.json()
    assert diff_data["total_changes"] >= 1

    # 2. Clone from applied draft version
    clone_res = client.post(f"/api/coach/resume-versions/{applied_ver_id}/clone", json={"title": "Cloned Draft 2"})
    assert clone_res.status_code == 201
    cloned_data = clone_res.json()
    assert cloned_data["parent_version_id"] == applied_ver_id

    # 3. Export PDF
    export_res = client.get(f"/api/coach/resume-versions/{applied_ver_id}/export")
    assert export_res.status_code == 200
    assert export_res.headers["content-type"] == "application/pdf"
    assert len(export_res.content) > 0
    assert export_res.content.startswith(b"%PDF-")
