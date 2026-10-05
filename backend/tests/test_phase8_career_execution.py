import pytest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.repository import Repository
from app.schemas.career_twin import CareerTwin
from app.schemas.evidence_vault import EvidenceVault, VaultEvidenceItem
from app.schemas.candidate import CandidateProfile, CandidateSkill, CandidateProject, CandidateExperience
from app.schemas.career_intelligence import (
    CareerTarget,
    CareerAction,
    ActionType,
    ActionStatus,
    GapPriority,
    TargetStatus,
)
from app.schemas.career_execution import (
    ExecutionStatus,
    ProgressState,
    ArtifactType,
    CareerExecution,
    EvidenceClaimSubmission,
    TimelineEventType,
)
from app.services.coach.career_execution.service import CareerExecutionService
from app.services.coach.evidence.service import EvidenceVaultService
from app.services.coach.job_fit.service import JobFitService
from app.services.coach.evidence.validation import EvidenceValidationService
from app.services.coach.career_intelligence.service import CareerIntelligenceService
from app.services.coach.interview.readiness_service import InterviewReadinessService
from app.schemas.job_fit import GapType


@pytest.fixture
def db_session():
    """Provides an isolated in-memory SQLite database session."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def candidate_jane_twin():
    return CareerTwin(
        twin_id="twin_jane",
        candidate_id="cand_jane",
        name="Jane Doe",
        email="jane@example.com",
        skills=["Python", "Flask", "Docker", "Kubernetes"],
        projects=[
            CandidateProject(
                name="CloudSync Engine",
                description="Built a microservices application using Kubernetes and Docker.",
                technologies=["Python", "Flask", "Docker", "Kubernetes"]
            )
        ],
        experience=[
            CandidateExperience(
                role="Backend Engineer",
                company="TechCorp",
                description="Built Python Flask backend services.",
                technologies=["Python", "Flask"]
            )
        ]
    )


@pytest.fixture
def candidate_jane_vault(candidate_jane_twin):
    service = EvidenceVaultService()
    profile = CandidateProfile(
        candidate_id=candidate_jane_twin.candidate_id,
        name=candidate_jane_twin.name,
        skills=candidate_jane_twin.skills,
        projects=candidate_jane_twin.projects,
        experience=candidate_jane_twin.experience,
        raw_text="Built a microservices application using Kubernetes and Docker. Built Python Flask backend services."
    )
    return service.build_vault(profile)


@pytest.fixture
def execution_service():
    vault_service = EvidenceVaultService()
    job_fit_service = JobFitService()
    validation_service = EvidenceValidationService()
    return CareerExecutionService(
        vault_service=vault_service,
        job_fit_service=job_fit_service,
        validation_service=validation_service,
    )


def test_01_execution_creation(execution_service, db_session):
    repo = Repository(db_session)
    repo.save_career_target(
        target_id="tgt_1",
        candidate_id="cand_jane",
        target_role="Senior Backend Engineer",
        requirements=[{"requirement_id": "req_k8s", "requirement_text": "Production Kubernetes experience", "priority": "REQUIRED"}]
    )
    repo.save_career_action(
        action_id="act_k8s",
        candidate_id="cand_jane",
        target_id="tgt_1",
        requirement_id="req_k8s",
        action_type="BUILD_PROJECT",
        title="Build Kubernetes Deployment Project",
        description="Deploy a project on Kubernetes",
        rationale="Gain hands-on practice",
    )

    exec_record = execution_service.create_execution(
        candidate_id="cand_jane",
        action_id="act_k8s",
        target_id="tgt_1",
        notes="Initial setup planned",
        db=db_session
    )

    assert exec_record.execution_id.startswith("exec_")
    assert exec_record.candidate_id == "cand_jane"
    assert exec_record.action_id == "act_k8s"
    assert exec_record.status == ExecutionStatus.NOT_STARTED
    assert exec_record.progress_state == ProgressState.PLANNED
    assert exec_record.progress_percent == 0
    assert len(exec_record.notes) == 1
    assert "Initial setup planned" in exec_record.notes[0].content


def test_02_candidate_ownership(execution_service, db_session):
    repo = Repository(db_session)
    repo.save_career_target(target_id="tgt_1", candidate_id="cand_jane", target_role="Backend")
    repo.save_career_action(
        action_id="act_1", candidate_id="cand_jane", target_id="tgt_1",
        requirement_id="req_1", action_type="BUILD_PROJECT", title="T", description="D", rationale="R"
    )
    exec_rec = execution_service.create_execution(candidate_id="cand_jane", action_id="act_1", target_id="tgt_1", db=db_session)

    with pytest.raises(PermissionError) as exc:
        execution_service.get_execution(candidate_id="cand_attacker", execution_id=exec_rec.execution_id, db=db_session)
    assert "Security violation" in str(exc.value)


def test_03_action_ownership(execution_service, db_session):
    repo = Repository(db_session)
    repo.save_career_target(target_id="tgt_1", candidate_id="cand_jane", target_role="Backend")
    repo.save_career_action(
        action_id="act_bob", candidate_id="cand_bob", target_id="tgt_1",
        requirement_id="req_1", action_type="BUILD_PROJECT", title="T", description="D", rationale="R"
    )

    with pytest.raises(PermissionError) as exc:
        execution_service.create_execution(candidate_id="cand_jane", action_id="act_bob", target_id="tgt_1", db=db_session)
    assert "does not belong to candidate" in str(exc.value)


def test_04_target_ownership(execution_service, db_session):
    repo = Repository(db_session)
    repo.save_career_target(target_id="tgt_bob", candidate_id="cand_bob", target_role="Backend")
    repo.save_career_action(
        action_id="act_jane", candidate_id="cand_jane", target_id="tgt_bob",
        requirement_id="req_1", action_type="BUILD_PROJECT", title="T", description="D", rationale="R"
    )

    with pytest.raises(PermissionError) as exc:
        execution_service.create_execution(candidate_id="cand_jane", action_id="act_jane", target_id="tgt_bob", db=db_session)
    assert "does not belong to candidate" in str(exc.value)


def test_05_valid_status_transitions(execution_service, db_session):
    repo = Repository(db_session)
    repo.save_career_target(target_id="tgt_1", candidate_id="cand_jane", target_role="Backend")
    repo.save_career_action(
        action_id="act_1", candidate_id="cand_jane", target_id="tgt_1",
        requirement_id="req_1", action_type="BUILD_PROJECT", title="T", description="D", rationale="R"
    )
    ex = execution_service.create_execution("cand_jane", "act_1", "tgt_1", db=db_session)
    assert ex.status == ExecutionStatus.NOT_STARTED

    # Start
    ex = execution_service.start_execution("cand_jane", ex.execution_id, db=db_session)
    assert ex.status == ExecutionStatus.IN_PROGRESS
    assert ex.progress_state == ProgressState.IN_PROGRESS

    # Artifact submit
    ex = execution_service.submit_artifact("cand_jane", ex.execution_id, "Repo", ArtifactType.GITHUB_REPO, "https://github.com/ex", "Repo desc", db=db_session)
    assert ex.status == ExecutionStatus.AWAITING_EVIDENCE
    assert ex.progress_state == ProgressState.EVIDENCE_SUBMITTED

    # Self-report complete
    ex = execution_service.complete_self_reported("cand_jane", ex.execution_id, "All done", db=db_session)
    assert ex.status == ExecutionStatus.COMPLETED
    assert ex.progress_state == ProgressState.SELF_REPORTED_COMPLETE


def test_06_invalid_status_transitions(execution_service, db_session):
    repo = Repository(db_session)
    repo.save_career_target(target_id="tgt_1", candidate_id="cand_jane", target_role="Backend")
    repo.save_career_action(
        action_id="act_1", candidate_id="cand_jane", target_id="tgt_1",
        requirement_id="req_1", action_type="BUILD_PROJECT", title="T", description="D", rationale="R"
    )
    ex = execution_service.create_execution("cand_jane", "act_1", "tgt_1", db=db_session)

    # Cannot complete unstarted action
    with pytest.raises(ValueError) as exc:
        execution_service.complete_self_reported("cand_jane", ex.execution_id, db=db_session)
    assert "has not been started" in str(exc.value)


def test_07_progress_updates(execution_service, db_session):
    repo = Repository(db_session)
    repo.save_career_target(target_id="tgt_1", candidate_id="cand_jane", target_role="Backend")
    repo.save_career_action(
        action_id="act_1", candidate_id="cand_jane", target_id="tgt_1",
        requirement_id="req_1", action_type="BUILD_PROJECT", title="T", description="D", rationale="R"
    )
    ex = execution_service.create_execution("cand_jane", "act_1", "tgt_1", db=db_session)
    ex = execution_service.update_progress("cand_jane", ex.execution_id, 45, notes="Working on manifests", next_step="Deploy cluster", db=db_session)

    assert ex.progress_percent == 45
    assert ex.next_step == "Deploy cluster"
    assert any("Working on manifests" in n.content for n in ex.notes)


def test_08_blocker_workflow(execution_service, db_session, candidate_jane_vault, candidate_jane_twin):
    repo = Repository(db_session)
    repo.save_career_target(target_id="tgt_1", candidate_id="cand_jane", target_role="Backend")
    repo.save_career_action(
        action_id="act_1", candidate_id="cand_jane", target_id="tgt_1",
        requirement_id="req_1", action_type="BUILD_PROJECT", title="T", description="D", rationale="R"
    )
    initial_vault_count = candidate_jane_vault.total_items
    ex = execution_service.create_execution("cand_jane", "act_1", "tgt_1", db=db_session)
    ex = execution_service.report_blocker("cand_jane", ex.execution_id, "Need cloud credentials", next_step="Request access", db=db_session)

    assert ex.status == ExecutionStatus.BLOCKED
    assert ex.blocker_reason == "Need cloud credentials"
    assert ex.next_step == "Request access"
    # Blocker does not alter vault or twin
    assert candidate_jane_vault.total_items == initial_vault_count


def test_09_self_reported_completion(execution_service, db_session):
    repo = Repository(db_session)
    repo.save_career_target(target_id="tgt_1", candidate_id="cand_jane", target_role="Backend")
    repo.save_career_action(
        action_id="act_1", candidate_id="cand_jane", target_id="tgt_1",
        requirement_id="req_1", action_type="BUILD_PROJECT", title="T", description="D", rationale="R"
    )
    ex = execution_service.create_execution("cand_jane", "act_1", "tgt_1", db=db_session)
    execution_service.start_execution("cand_jane", ex.execution_id, db=db_session)
    completed = execution_service.complete_self_reported("cand_jane", ex.execution_id, "I finished the deployment project", db=db_session)

    assert completed.status == ExecutionStatus.COMPLETED
    assert completed.progress_state == ProgressState.SELF_REPORTED_COMPLETE
    assert completed.progress_percent == 100
    assert completed.completed_at is not None


def test_10_artifact_submission(execution_service, db_session):
    repo = Repository(db_session)
    repo.save_career_target(target_id="tgt_1", candidate_id="cand_jane", target_role="Backend")
    repo.save_career_action(
        action_id="act_1", candidate_id="cand_jane", target_id="tgt_1",
        requirement_id="req_1", action_type="BUILD_PROJECT", title="T", description="D", rationale="R"
    )
    ex = execution_service.create_execution("cand_jane", "act_1", "tgt_1", db=db_session)
    ex = execution_service.submit_artifact(
        "cand_jane", ex.execution_id, "Kubernetes Repo", ArtifactType.GITHUB_REPO,
        "https://github.com/jane/k8s-demo", "Contains deployment yamls and services", ["Kubernetes", "Docker"], db=db_session
    )

    assert len(ex.artifact_references) == 1
    assert ex.artifact_references[0].name == "Kubernetes Repo"
    assert ex.artifact_references[0].artifact_type == ArtifactType.GITHUB_REPO
    assert ex.status == ExecutionStatus.AWAITING_EVIDENCE
    assert ex.progress_state == ProgressState.EVIDENCE_SUBMITTED


def test_11_evidence_submission(execution_service, db_session, candidate_jane_twin, candidate_jane_vault):
    repo = Repository(db_session)
    repo.save_career_target(target_id="tgt_1", candidate_id="cand_jane", target_role="Backend")
    repo.save_career_action(
        action_id="act_1", candidate_id="cand_jane", target_id="tgt_1",
        requirement_id="req_1", action_type="BUILD_PROJECT", title="T", description="D", rationale="R"
    )
    ex = execution_service.create_execution("cand_jane", "act_1", "tgt_1", db=db_session)
    claims = [
        EvidenceClaimSubmission(
            claim_text="Configured Kubernetes deployment manifests and ingress controllers",
            source_snippet="Created deployment.yaml with ReplicaSet and ClusterIP service",
            evidence_type="PROJECT",
            related_technologies=["Kubernetes"],
            related_skill="Kubernetes"
        )
    ]
    res = execution_service.verify_evidence(
        candidate_id="cand_jane",
        execution_id=ex.execution_id,
        evidence_claims=claims,
        twin=candidate_jane_twin,
        vault=candidate_jane_vault,
        db=db_session
    )
    assert res.verified is True
    assert len(res.evidence_ids) == 1
    assert "LEVEL 3" in res.claim_scope


def test_12_evidence_validation(execution_service, db_session, candidate_jane_twin, candidate_jane_vault):
    repo = Repository(db_session)
    repo.save_career_target(target_id="tgt_1", candidate_id="cand_jane", target_role="Backend")
    repo.save_career_action(
        action_id="act_1", candidate_id="cand_jane", target_id="tgt_1",
        requirement_id="req_1", action_type="BUILD_PROJECT", title="T", description="D", rationale="R"
    )
    ex = execution_service.create_execution("cand_jane", "act_1", "tgt_1", db=db_session)
    # Empty claim rejected
    claims = [EvidenceClaimSubmission(claim_text="", source_snippet="", evidence_type="PROJECT")]
    res = execution_service.verify_evidence("cand_jane", ex.execution_id, claims, twin=candidate_jane_twin, vault=candidate_jane_vault, db=db_session)
    assert res.verified is False
    assert "failed validation" in res.rejection_reason


def test_13_rejected_evidence(execution_service, db_session, candidate_jane_twin, candidate_jane_vault):
    repo = Repository(db_session)
    repo.save_career_target(target_id="tgt_1", candidate_id="cand_jane", target_role="Backend")
    repo.save_career_action(
        action_id="act_1", candidate_id="cand_jane", target_id="tgt_1",
        requirement_id="req_1", action_type="BUILD_PROJECT", title="T", description="D", rationale="R"
    )
    ex = execution_service.create_execution("cand_jane", "act_1", "tgt_1", db=db_session)
    initial_items = candidate_jane_vault.total_items

    # Unsupported operational claim without snippet proof
    claims = [
        EvidenceClaimSubmission(
            claim_text="Managed production Kubernetes clusters and 24/7 on-call",
            source_snippet="Ran minikube locally on laptop",
            evidence_type="PROJECT",
            related_technologies=["Kubernetes"]
        )
    ]
    res = execution_service.verify_evidence("cand_jane", ex.execution_id, claims, twin=candidate_jane_twin, vault=candidate_jane_vault, db=db_session)
    assert res.verified is False
    assert "Unsupported operational claim" in res.rejection_reason
    # Evidence Vault is NOT mutated
    assert candidate_jane_vault.total_items == initial_items


def test_14_verified_evidence(execution_service, db_session, candidate_jane_twin, candidate_jane_vault):
    repo = Repository(db_session)
    repo.save_career_target(target_id="tgt_1", candidate_id="cand_jane", target_role="Backend")
    repo.save_career_action(
        action_id="act_1", candidate_id="cand_jane", target_id="tgt_1",
        requirement_id="req_1", action_type="BUILD_PROJECT", title="T", description="D", rationale="R"
    )
    ex = execution_service.create_execution("cand_jane", "act_1", "tgt_1", db=db_session)
    claims = [
        EvidenceClaimSubmission(
            claim_text="Implemented Redis caching layer reducing API latency",
            source_snippet="Configured Redis cache with 300s TTL in FastAPI",
            evidence_type="PROJECT",
            related_technologies=["Redis"],
            related_skill="Redis"
        )
    ]
    res = execution_service.verify_evidence("cand_jane", ex.execution_id, claims, twin=candidate_jane_twin, vault=candidate_jane_vault, db=db_session)
    assert res.verified is True
    # Attached to vault
    assert any(it.evidence_id == res.evidence_ids[0] for it in candidate_jane_vault.items)
    # Execution is now VERIFIED
    updated_ex = execution_service.get_execution("cand_jane", ex.execution_id, db=db_session)
    assert updated_ex.progress_state == ProgressState.VERIFIED
    assert updated_ex.status == ExecutionStatus.COMPLETED


def test_15_evidence_provenance(execution_service, db_session, candidate_jane_twin, candidate_jane_vault):
    repo = Repository(db_session)
    repo.save_career_target(target_id="tgt_1", candidate_id="cand_jane", target_role="Backend")
    repo.save_career_action(
        action_id="act_1", candidate_id="cand_jane", target_id="tgt_1",
        requirement_id="req_1", action_type="BUILD_PROJECT", title="T", description="D", rationale="R"
    )
    ex = execution_service.create_execution("cand_jane", "act_1", "tgt_1", db=db_session)
    claims = [
        EvidenceClaimSubmission(
            claim_text="Configured Docker Compose for local PostgreSQL and Redis integration tests",
            source_snippet="docker-compose.test.yml running Postgres and Redis",
            evidence_type="PROJECT",
            source_document="Integration Tests",
            source_section="Testing",
            related_technologies=["Docker", "PostgreSQL", "Redis"],
        )
    ]
    res = execution_service.verify_evidence("cand_jane", ex.execution_id, claims, twin=candidate_jane_twin, vault=candidate_jane_vault, db=db_session)
    assert len(res.provenance) == 1
    prov = res.provenance[0]
    assert prov["evidence_id"] == res.evidence_ids[0]
    assert prov["source_document"] == "Integration Tests"
    assert prov["source_section"] == "Testing"
    assert prov["related_action_id"] == "act_1"
    assert prov["related_target_id"] == "tgt_1"
    assert "Docker" in prov["technologies"]


def test_16_cross_candidate_evidence_rejection(execution_service, db_session):
    repo = Repository(db_session)
    repo.save_career_target(target_id="tgt_1", candidate_id="cand_jane", target_role="Backend")
    repo.save_career_action(
        action_id="act_1", candidate_id="cand_jane", target_id="tgt_1",
        requirement_id="req_1", action_type="BUILD_PROJECT", title="T", description="D", rationale="R"
    )
    ex = execution_service.create_execution("cand_jane", "act_1", "tgt_1", db=db_session)

    # Candidate Bob attempts to verify Jane's execution
    with pytest.raises(PermissionError) as exc:
        execution_service.verify_evidence("cand_bob", ex.execution_id, [EvidenceClaimSubmission(claim_text="Valid claim text", source_snippet="Valid snippet")], db=db_session)
    assert "Security violation" in str(exc.value)


def test_17_forged_evidence_rejection(execution_service, db_session, candidate_jane_twin, candidate_jane_vault):
    repo = Repository(db_session)
    repo.save_career_target(target_id="tgt_1", candidate_id="cand_jane", target_role="Backend")
    repo.save_career_action(
        action_id="act_1", candidate_id="cand_jane", target_id="tgt_1",
        requirement_id="req_1", action_type="BUILD_PROJECT", title="T", description="D", rationale="R"
    )
    ex = execution_service.create_execution("cand_jane", "act_1", "tgt_1", db=db_session)

    # Empty claim list
    res = execution_service.verify_evidence("cand_jane", ex.execution_id, [], twin=candidate_jane_twin, vault=candidate_jane_vault, db=db_session)
    assert res.verified is False
    assert "No evidence claims submitted" in res.rejection_reason


def test_18_action_completion_without_evidence(execution_service, db_session, candidate_jane_twin, candidate_jane_vault):
    repo = Repository(db_session)
    repo.save_career_target(target_id="tgt_1", candidate_id="cand_jane", target_role="Backend")
    repo.save_career_action(
        action_id="act_1", candidate_id="cand_jane", target_id="tgt_1",
        requirement_id="req_1", action_type="BUILD_PROJECT", title="T", description="D", rationale="R"
    )
    ex = execution_service.create_execution("cand_jane", "act_1", "tgt_1", db=db_session)
    execution_service.start_execution("cand_jane", ex.execution_id, db=db_session)

    vault_count_before = candidate_jane_vault.total_items
    execution_service.complete_self_reported("cand_jane", ex.execution_id, "Done", db=db_session)

    # Must NOT add anything to vault
    assert candidate_jane_vault.total_items == vault_count_before


def test_19_no_automatic_skill_granting(execution_service, db_session, candidate_jane_twin):
    repo = Repository(db_session)
    repo.save_career_target(target_id="tgt_1", candidate_id="cand_jane", target_role="Backend")
    repo.save_career_action(
        action_id="act_rust", candidate_id="cand_jane", target_id="tgt_1",
        requirement_id="req_rust", action_type="LEARN_SKILL", title="Learn Rust", description="Study Rust", rationale="Needed"
    )
    ex = execution_service.create_execution("cand_jane", "act_rust", "tgt_1", db=db_session)
    execution_service.start_execution("cand_jane", ex.execution_id, db=db_session)
    execution_service.complete_self_reported("cand_jane", ex.execution_id, "Finished reading Rust book", db=db_session)

    # Rust must NOT appear in candidate twin's verified skills
    assert "Rust" not in candidate_jane_twin.skills


def test_20_no_automatic_experience_granting(execution_service, db_session, candidate_jane_twin):
    repo = Repository(db_session)
    repo.save_career_target(target_id="tgt_1", candidate_id="cand_jane", target_role="Backend")
    repo.save_career_action(
        action_id="act_exp", candidate_id="cand_jane", target_id="tgt_1",
        requirement_id="req_exp", action_type="GAIN_EXPERIENCE", title="Lead DevOps", description="Run DevOps", rationale="Needed"
    )
    ex = execution_service.create_execution("cand_jane", "act_exp", "tgt_1", db=db_session)
    execution_service.start_execution("cand_jane", ex.execution_id, db=db_session)
    execution_service.complete_self_reported("cand_jane", ex.execution_id, "I led devops for 2 years", db=db_session)

    # No new experiences granted to twin
    assert not any("DevOps" in e.role for e in candidate_jane_twin.experience)


def test_21_claim_scope_preservation(execution_service, db_session, candidate_jane_twin, candidate_jane_vault):
    repo = Repository(db_session)
    repo.save_career_target(target_id="tgt_1", candidate_id="cand_jane", target_role="Backend")
    repo.save_career_action(
        action_id="act_1", candidate_id="cand_jane", target_id="tgt_1",
        requirement_id="req_1", action_type="BUILD_PROJECT", title="T", description="D", rationale="R"
    )
    ex = execution_service.create_execution("cand_jane", "act_1", "tgt_1", db=db_session)

    # Submitting Level 3 implementation claim
    claims = [
        EvidenceClaimSubmission(
            claim_text="Configured Kubernetes Helm charts and service accounts",
            source_snippet="Authored values.yaml and deployment manifests with Helm",
            evidence_type="PROJECT",
            related_technologies=["Kubernetes"],
        )
    ]
    res = execution_service.verify_evidence("cand_jane", ex.execution_id, claims, twin=candidate_jane_twin, vault=candidate_jane_vault, db=db_session)
    assert res.verified is True
    # Evaluated scope is LEVEL 3, NOT LEVEL 4
    assert res.claim_scope == "LEVEL 3 — IMPLEMENTATION"


def test_22_kubernetes_presence_vs_deployment(execution_service, db_session, candidate_jane_twin, candidate_jane_vault):
    repo = Repository(db_session)
    repo.save_career_target(
        target_id="tgt_k8s_dep",
        candidate_id="cand_jane",
        target_role="Cloud Engineer",
        requirements=[{"requirement_id": "req_dep", "requirement_text": "Kubernetes deployment and service configuration", "priority": "REQUIRED"}]
    )
    repo.save_career_action(
        action_id="act_dep", candidate_id="cand_jane", target_id="tgt_k8s_dep",
        requirement_id="req_dep", action_type="BUILD_PROJECT", title="T", description="D", rationale="R"
    )
    ex = execution_service.create_execution("cand_jane", "act_dep", "tgt_k8s_dep", db=db_session)
    claims = [
        EvidenceClaimSubmission(
            claim_text="Configured Kubernetes deployment manifests and cluster services for microservices",
            source_snippet="Configured Kubernetes deployment manifests and cluster services",
            evidence_type="PROJECT",
            related_technologies=["Kubernetes"],
        )
    ]
    res = execution_service.verify_evidence("cand_jane", ex.execution_id, claims, twin=candidate_jane_twin, vault=candidate_jane_vault, db=db_session)
    assert res.verified is True
    assert res.claim_scope == "LEVEL 3 — IMPLEMENTATION"


def test_23_deployment_vs_production(execution_service, db_session, candidate_jane_twin, candidate_jane_vault):
    repo = Repository(db_session)
    # Requirement demands Level 4: Experience managing production Kubernetes clusters (EKS/GKE)
    repo.save_career_target(
        target_id="tgt_prod",
        candidate_id="cand_jane",
        target_role="Principal SRE",
        raw_jd_text="Role: Principal SRE\nRequirements:\n- Experience managing production Kubernetes clusters (EKS/GKE)\n",
        requirements=[{"requirement_id": "req_prod", "requirement_text": "Experience managing production Kubernetes clusters (EKS/GKE)", "priority": "REQUIRED"}]
    )
    repo.save_career_action(
        action_id="act_k8s_dep", candidate_id="cand_jane", target_id="tgt_prod",
        requirement_id="req_prod", action_type="BUILD_PROJECT", title="T", description="D", rationale="R"
    )
    ex = execution_service.create_execution("cand_jane", "act_k8s_dep", "tgt_prod", db=db_session)

    # Candidate submits deployment evidence (Level 3)
    claims = [
        EvidenceClaimSubmission(
            claim_text="Deployed microservice applications to Kubernetes cluster",
            source_snippet="kubectl apply -f deployment.yaml in test environment",
            evidence_type="PROJECT",
            related_technologies=["Kubernetes"],
        )
    ]
    res = execution_service.verify_evidence("cand_jane", ex.execution_id, claims, twin=candidate_jane_twin, vault=candidate_jane_vault, db=db_session)
    assert res.verified is True

    # Check target progress: the requirement must NOT be MATCHED because production scope is missing
    target_progress = execution_service.get_target_progress("tgt_prod", "cand_jane", twin=candidate_jane_twin, vault=candidate_jane_vault, db=db_session)
    req_item = next(r for r in target_progress.requirement_progress if r.requirement_id == "req_prod")
    assert req_item.current_state in ["MISSING", "PARTIAL"]
    assert req_item.current_state != "MATCHED"


def test_24_before_after_target_comparison(execution_service, db_session, candidate_jane_twin, candidate_jane_vault):
    repo = Repository(db_session)
    repo.save_career_target(
        target_id="tgt_comp",
        candidate_id="cand_jane",
        target_role="Full Stack Engineer",
        raw_jd_text="Role: Full Stack Engineer\nRequirements:\n- TypeScript\n",
        requirements=[{"requirement_id": "req_ts", "requirement_text": "TypeScript", "priority": "REQUIRED"}]
    )
    repo.save_career_action(
        action_id="act_ts", candidate_id="cand_jane", target_id="tgt_comp",
        requirement_id="req_ts", action_type="BUILD_PROJECT", title="Build TS app", description="D", rationale="R"
    )
    ex = execution_service.create_execution("cand_jane", "act_ts", "tgt_comp", db=db_session)

    # Initial progress: TypeScript is missing
    before_prog = execution_service.get_target_progress("tgt_comp", "cand_jane", twin=candidate_jane_twin, vault=candidate_jane_vault, db=db_session)
    assert before_prog.after_summary["matched"] == 0

    # Submit and verify TypeScript evidence
    claims = [
        EvidenceClaimSubmission(
            claim_text="Developed frontend application in TypeScript with React",
            source_snippet="Built reusable components in TypeScript and React",
            evidence_type="PROJECT",
            related_technologies=["TypeScript", "React"],
            related_skill="TypeScript"
        )
    ]
    res = execution_service.verify_evidence("cand_jane", ex.execution_id, claims, twin=candidate_jane_twin, vault=candidate_jane_vault, db=db_session)
    assert res.verified is True

    # After progress: shows delta and improvement
    after_prog = execution_service.get_target_progress("tgt_comp", "cand_jane", twin=candidate_jane_twin, vault=candidate_jane_vault, db=db_session)
    assert after_prog.after_summary["matched"] >= 1
    assert len(after_prog.delta) >= 1
    assert any(d.requirement_id == "req_ts" and d.new_classification == "MATCHED" for d in after_prog.delta)


def test_25_job_fit_refresh(execution_service, db_session, candidate_jane_twin, candidate_jane_vault):
    repo = Repository(db_session)
    repo.save_career_target(
        target_id="tgt_fit",
        candidate_id="cand_jane",
        target_role="Backend Developer",
        raw_jd_text="Role: Backend Developer\nRequirements:\n- PostgreSQL\n",
        requirements=[{"requirement_id": "req_pg", "requirement_text": "PostgreSQL", "priority": "REQUIRED"}]
    )
    repo.save_career_action(
        action_id="act_pg", candidate_id="cand_jane", target_id="tgt_fit",
        requirement_id="req_pg", action_type="BUILD_PROJECT", title="Postgres app", description="D", rationale="R"
    )
    ex = execution_service.create_execution("cand_jane", "act_pg", "tgt_fit", db=db_session)
    claims = [
        EvidenceClaimSubmission(
            claim_text="Designed relational database schemas in PostgreSQL",
            source_snippet="Created schema migrations in PostgreSQL",
            evidence_type="PROJECT",
            related_technologies=["PostgreSQL"],
            related_skill="PostgreSQL"
        )
    ]
    res = execution_service.verify_evidence("cand_jane", ex.execution_id, claims, twin=candidate_jane_twin, vault=candidate_jane_vault, db=db_session)
    assert res.after_state["matched"] >= 1


def test_26_career_intelligence_refresh(execution_service, db_session, candidate_jane_twin, candidate_jane_vault):
    ci_service = CareerIntelligenceService()
    target = ci_service.create_target(
        candidate_id="cand_jane",
        target_role="Cloud Engineer",
        job_description_text="Requirements:\n- Redis caching and database performance optimization\n",
        twin=candidate_jane_twin,
        vault=candidate_jane_vault,
        db=db_session
    )
    # Target initially has an experience gap for Redis
    intel_before = ci_service.analyze_target_intelligence(target, candidate_jane_twin, candidate_jane_vault, db=db_session)
    assert any("redis" in g.requirement_text.lower() for g in intel_before.experience_gaps)

    # Verify Redis evidence via execution service
    action = intel_before.recommended_next_actions[0]
    ex = execution_service.create_execution("cand_jane", action.action_id, target.target_id, db=db_session)
    claims = [
        EvidenceClaimSubmission(
            claim_text="Implemented Redis caching and database performance optimization",
            source_snippet="Configured Redis cache with 300s TTL",
            evidence_type="PROJECT",
            related_technologies=["Redis"],
            related_skill="Redis"
        )
    ]
    execution_service.verify_evidence("cand_jane", ex.execution_id, claims, twin=candidate_jane_twin, vault=candidate_jane_vault, db=db_session)

    # Re-evaluate career intelligence: Redis moves to verified strengths
    intel_after = ci_service.analyze_target_intelligence(target, candidate_jane_twin, candidate_jane_vault, db=db_session)
    assert any("redis" in s.requirement_text.lower() for s in intel_after.strengths)
    assert not any("redis" in g.requirement_text.lower() for g in intel_after.experience_gaps)


def test_27_interview_readiness_refresh(execution_service, db_session, candidate_jane_twin, candidate_jane_vault):
    ir_service = InterviewReadinessService()
    target = ir_service.create_interview_target(
        candidate_id="cand_jane",
        target_role="Full Stack Engineer",
        job_description_text="Requirements:\n- GraphQL API development and query optimization\n",
        db=db_session
    )
    readiness_before = ir_service.generate_interview_readiness(target, candidate_jane_twin, candidate_jane_vault, db_session)
    # GraphQL is in areas to prepare
    assert any("graphql" in p.requirement_text.lower() for p in readiness_before.areas_to_prepare)

    # Execute and verify GraphQL evidence
    repo = Repository(db_session)
    repo.save_career_action(
        action_id="act_gql", candidate_id="cand_jane", target_id=target.interview_target_id,
        requirement_id="req_gql", action_type="BUILD_PROJECT", title="T", description="D", rationale="R"
    )
    ex = execution_service.create_execution("cand_jane", "act_gql", target.interview_target_id, db=db_session)
    claims = [
        EvidenceClaimSubmission(
            claim_text="Implemented GraphQL resolvers and schema in Python backend",
            source_snippet="Created schema.graphql and query resolvers",
            evidence_type="PROJECT",
            related_technologies=["GraphQL"],
            related_skill="GraphQL"
        )
    ]
    execution_service.verify_evidence("cand_jane", ex.execution_id, claims, twin=candidate_jane_twin, vault=candidate_jane_vault, db=db_session)

    # Re-evaluate Interview Readiness: GraphQL moves to ready to discuss
    readiness_after = ir_service.generate_interview_readiness(target, candidate_jane_twin, candidate_jane_vault, db_session)
    assert any("graphql" in c.requirement_text.lower() for c in readiness_after.ready_to_discuss)


def test_28_timeline_generation(execution_service, db_session, candidate_jane_twin, candidate_jane_vault):
    repo = Repository(db_session)
    repo.save_career_target(target_id="tgt_time", candidate_id="cand_jane", target_role="Backend")
    repo.save_career_action(
        action_id="act_time", candidate_id="cand_jane", target_id="tgt_time",
        requirement_id="req_time", action_type="BUILD_PROJECT", title="T", description="D", rationale="R"
    )
    ex = execution_service.create_execution("cand_jane", "act_time", "tgt_time", db=db_session)
    execution_service.start_execution("cand_jane", ex.execution_id, db=db_session)
    execution_service.submit_artifact("cand_jane", ex.execution_id, "Repo", ArtifactType.GITHUB_REPO, "http://gh", "desc", db=db_session)

    claims = [EvidenceClaimSubmission(claim_text="Implemented microservice in Python", source_snippet="Flask backend", evidence_type="PROJECT", related_technologies=["Python"])]
    execution_service.verify_evidence("cand_jane", ex.execution_id, claims, twin=candidate_jane_twin, vault=candidate_jane_vault, db=db_session)

    prog = execution_service.get_target_progress("tgt_time", "cand_jane", twin=candidate_jane_twin, vault=candidate_jane_vault, db=db_session)
    events = prog.timeline
    event_types = [e.event_type for e in events]

    assert TimelineEventType.ACTION_STARTED in event_types
    assert TimelineEventType.ARTIFACT_SUBMITTED in event_types
    assert TimelineEventType.EVIDENCE_VERIFIED in event_types
    assert TimelineEventType.CAREER_TWIN_REFRESHED in event_types
    assert TimelineEventType.JOB_FIT_REFRESHED in event_types


def test_29_candidate_isolation(execution_service, db_session):
    repo = Repository(db_session)
    repo.save_career_target(target_id="tgt_jane", candidate_id="cand_jane", target_role="Backend")
    repo.save_career_target(target_id="tgt_alice", candidate_id="cand_alice", target_role="Data")

    repo.save_career_action(action_id="act_jane", candidate_id="cand_jane", target_id="tgt_jane", requirement_id="r1", action_type="BUILD_PROJECT", title="T", description="D", rationale="R")
    repo.save_career_action(action_id="act_alice", candidate_id="cand_alice", target_id="tgt_alice", requirement_id="r2", action_type="BUILD_PROJECT", title="T", description="D", rationale="R")

    ex_jane = execution_service.create_execution("cand_jane", "act_jane", "tgt_jane", db=db_session)
    ex_alice = execution_service.create_execution("cand_alice", "act_alice", "tgt_alice", db=db_session)

    jane_list = execution_service.list_executions_for_candidate("cand_jane", db=db_session)
    alice_list = execution_service.list_executions_for_candidate("cand_alice", db=db_session)

    assert len(jane_list) == 1
    assert jane_list[0].execution_id == ex_jane.execution_id
    assert len(alice_list) == 1
    assert alice_list[0].execution_id == ex_alice.execution_id

    # Cross access blocked
    with pytest.raises(PermissionError):
        execution_service.get_execution("cand_jane", ex_alice.execution_id, db=db_session)


def test_30_regression_coverage_phases_1_to_7(execution_service, candidate_jane_twin, candidate_jane_vault):
    # Verify candidate twin and vault schemas and methods remain intact
    assert candidate_jane_twin.candidate_id == "cand_jane"
    assert "Python" in candidate_jane_twin.skills
    assert candidate_jane_vault.total_items > 0
    assert hasattr(execution_service, "verify_evidence")
    assert hasattr(execution_service, "get_target_progress")


# ---------------------------------------------------------------------------
# 31. Requirement Progress & Scope Loaded for Career Target
# ---------------------------------------------------------------------------
def test_31_requirement_progress_and_scope_loaded(execution_service, db_session, candidate_jane_twin, candidate_jane_vault):
    repo = Repository(db_session)
    repo.save_career_target(
        target_id="tgt_req_load",
        candidate_id="cand_jane",
        target_role="Full Stack Engineer",
        raw_jd_text="Role: Full Stack Engineer\nRequirements:\n- Python backend microservices\n- React frontend architecture\n- Kubernetes cluster deployment\n",
        requirements=[
            {"requirement_id": "req_py", "requirement_text": "Python backend microservices", "priority": "REQUIRED"},
            {"requirement_id": "req_react", "requirement_text": "React frontend architecture", "priority": "REQUIRED"},
            {"requirement_id": "req_k8s", "requirement_text": "Kubernetes cluster deployment", "priority": "REQUIRED"},
        ]
    )

    prog = execution_service.get_target_progress("tgt_req_load", "cand_jane", twin=candidate_jane_twin, vault=candidate_jane_vault, db=db_session)

    # Must provide requirements via both `requirement_progress` and `requirements`
    assert len(prog.requirement_progress) == 3
    assert len(prog.requirements) == 3
    assert prog.requirements == prog.requirement_progress

    # Check requirement detail fields
    req_ids = [r.requirement_id for r in prog.requirements]
    assert "req_py" in req_ids
    assert "req_react" in req_ids
    assert "req_k8s" in req_ids

    py_item = next(r for r in prog.requirements if r.requirement_id == "req_py")
    assert py_item.current_state in ["MATCHED", "PARTIAL", "MISSING"]
    assert py_item.claim_scope.startswith("LEVEL")
    assert py_item.requirement_text == "Python backend microservices"


# ---------------------------------------------------------------------------
# 32. Target Before / After Delta Populated from Job Fit State
# ---------------------------------------------------------------------------
def test_32_before_after_delta_populated(execution_service, db_session, candidate_jane_twin, candidate_jane_vault):
    repo = Repository(db_session)
    repo.save_career_target(
        target_id="tgt_delta_pop",
        candidate_id="cand_jane",
        target_role="Backend Developer",
        raw_jd_text="Role: Backend Developer\nRequirements:\n- Python backend\n- Rust systems programming\n",
        requirements=[
            {"requirement_id": "req_p", "requirement_text": "Python backend", "priority": "REQUIRED"},
            {"requirement_id": "req_r", "requirement_text": "Rust systems programming", "priority": "REQUIRED"},
        ]
    )

    prog = execution_service.get_target_progress("tgt_delta_pop", "cand_jane", twin=candidate_jane_twin, vault=candidate_jane_vault, db=db_session)

    # Verify both flat and nested summaries are populated from actual Job Fit state
    assert prog.before_summary is not None
    assert prog.after_summary is not None
    assert isinstance(prog.before_matched, int)
    assert isinstance(prog.before_missing, int)
    assert isinstance(prog.before_experience_gaps, int)
    assert prog.before_matched == prog.before_summary["matched"]
    assert prog.before_partial == prog.before_summary["partial"]
    assert prog.before_missing == prog.before_summary["missing"]
    assert prog.before_visibility_gaps == prog.before_summary["visibility_gaps"]
    assert prog.before_experience_gaps == prog.before_summary["experience_gaps"]

    assert prog.after_matched == prog.after_summary["matched"]
    assert prog.after_partial == prog.after_summary["partial"]
    assert prog.after_missing == prog.after_summary["missing"]
    assert prog.after_visibility_gaps == prog.after_summary["visibility_gaps"]
    assert prog.after_experience_gaps == prog.after_summary["experience_gaps"]

    # Total requirements should be 2
    total = prog.after_matched + prog.after_partial + prog.after_missing
    assert total >= 2

    # deltas list exists and matches delta
    assert prog.deltas == prog.delta


# ---------------------------------------------------------------------------
# 33. Self-Reported 100% Progress Separated from Verified Evidence
# ---------------------------------------------------------------------------
def test_33_self_reported_progress_does_not_verify_requirements_or_grant_skills(
    execution_service, db_session, candidate_jane_twin, candidate_jane_vault
):
    repo = Repository(db_session)
    repo.save_career_target(
        target_id="tgt_unverified",
        candidate_id="cand_jane",
        target_role="Database Specialist",
        raw_jd_text="Role: Database Specialist\nRequirements:\n- Apache Cassandra distributed database\n",
        requirements=[{"requirement_id": "req_cas", "requirement_text": "Apache Cassandra distributed database", "priority": "REQUIRED"}]
    )
    repo.save_career_action(
        action_id="act_cas", candidate_id="cand_jane", target_id="tgt_unverified",
        requirement_id="req_cas", action_type="BUILD_PROJECT", title="Cassandra project", description="D", rationale="R"
    )

    ex = execution_service.create_execution("cand_jane", "act_cas", "tgt_unverified", db=db_session)
    execution_service.start_execution("cand_jane", ex.execution_id, db=db_session)

    # Candidate reports 100% progress
    updated = execution_service.update_progress("cand_jane", ex.execution_id, progress_percent=100, notes="I did everything!", db=db_session)
    assert updated.progress_percent == 100

    # Candidate marks self-reported complete
    completed = execution_service.complete_self_reported("cand_jane", ex.execution_id, notes="Fully finished self-report", db=db_session)
    assert completed.progress_state == ProgressState.SELF_REPORTED_COMPLETE
    assert completed.status == ExecutionStatus.COMPLETED

    # Verified evidence must remain 0
    assert len(completed.evidence_ids) == 0

    # Vault must not have received any Cassandra evidence
    vault_evidence = repo.get_evidence_for_candidate("cand_jane")
    assert not any("cassandra" in str(getattr(item, 'source_text', '')).lower() for item in vault_evidence)
    assert not any("cassandra" in str(item.source_text).lower() for item in candidate_jane_vault.items)

    # Twin skills must not include Cassandra
    profile_rec = repo.get_candidate_profile("cand_jane")
    profile_skills = json.loads(profile_rec.skills_json) if profile_rec and profile_rec.skills_json else []
    assert not any("cassandra" in s.lower() for s in profile_skills)
    assert not any("cassandra" in s.lower() for s in candidate_jane_twin.skills)

    # Target requirements must still be MISSING and have 0 evidence
    prog = execution_service.get_target_progress("tgt_unverified", "cand_jane", twin=candidate_jane_twin, vault=candidate_jane_vault, db=db_session)
    cas_req = next(r for r in prog.requirements if r.requirement_id == "req_cas")
    assert cas_req.current_state in ["MISSING", "PARTIAL"]
    assert cas_req.current_state != "MATCHED"
    assert cas_req.evidence_count == 0


# ---------------------------------------------------------------------------
# 34. Career Intelligence Evidence Coverage Formatting (0.659 -> 65.9%)
# ---------------------------------------------------------------------------
def test_34_career_intelligence_evidence_coverage_formatting_0_659():
    from app.services.coach.career_intelligence.service import (
        normalize_coverage_to_percentage,
        format_coverage_percentage,
    )

    # 1. Decimal 0.659 must convert to 65.9% exactly once, NEVER 6590.0%
    normalized = normalize_coverage_to_percentage(0.659)
    assert normalized == 65.9
    formatted = format_coverage_percentage(0.659)
    assert formatted == "65.9%"
    assert formatted != "6590.0%"
    assert formatted != "6590%"

    # 2. Already converted 65.9 must stay 65.9%
    assert normalize_coverage_to_percentage(65.9) == 65.9
    assert format_coverage_percentage(65.9) == "65.9%"

    # 3. Boundary cases
    assert normalize_coverage_to_percentage(0.0) == 0.0
    assert format_coverage_percentage(0.0) == "0.0%"
    assert normalize_coverage_to_percentage(1.0) == 100.0
    assert format_coverage_percentage(1.0) == "100.0%"
    assert normalize_coverage_to_percentage(None) == 0.0
    assert format_coverage_percentage(None) == "0.0%"


# ---------------------------------------------------------------------------
# 35. Regression: Execution Completion Transitions & Timeline Events
# ---------------------------------------------------------------------------
def test_35_execution_completion_transition_and_timeline(execution_service, db_session):
    repo = Repository(db_session)
    repo.save_career_target(target_id="tgt_comp", candidate_id="cand_jane", target_role="Backend Specialist")
    repo.save_career_action(
        action_id="act_comp", candidate_id="cand_jane", target_id="tgt_comp",
        requirement_id="req_comp", action_type="BUILD_PROJECT", title="Comp Project", description="Desc", rationale="Rat"
    )
    ex = execution_service.create_execution("cand_jane", "act_comp", "tgt_comp", title="Comp Project", db=db_session)
    assert ex.status == ExecutionStatus.NOT_STARTED

    # Transition to IN_PROGRESS
    started = execution_service.start_execution("cand_jane", ex.execution_id, db=db_session)
    assert started.status == ExecutionStatus.IN_PROGRESS
    assert started.progress_state == ProgressState.IN_PROGRESS
    assert started.started_at is not None

    # Mark self-reported complete
    completed = execution_service.complete_self_reported(
        "cand_jane", ex.execution_id, notes="Work completed, ready for verification", db=db_session
    )
    assert completed.status == ExecutionStatus.COMPLETED
    assert completed.progress_state == ProgressState.SELF_REPORTED_COMPLETE
    assert completed.progress_percent == 100
    assert completed.completed_at is not None
    assert any("Work completed" in n.content for n in completed.notes)

    # Persisted in DB as COMPLETED
    rec = repo.get_career_execution(ex.execution_id)
    assert rec.status == "COMPLETED"
    assert rec.progress_state == "SELF_REPORTED_COMPLETE"
    assert rec.progress_percent == 100

    # Linked career action in DB is also marked COMPLETED
    action_rec = repo.get_career_action("act_comp")
    assert action_rec.status == "COMPLETED"

    # Timeline includes ACTION_STARTED and SELF_REPORTED_COMPLETE
    events = execution_service._get_timeline_events("tgt_comp", "cand_jane", db=db_session)
    event_types = [e.event_type for e in events]
    assert TimelineEventType.ACTION_STARTED in event_types
    assert TimelineEventType.SELF_REPORTED_COMPLETE in event_types


# ---------------------------------------------------------------------------
# 36. Regression: Progress Updates (50% -> 100%) Persist and Reload from Database
# ---------------------------------------------------------------------------
def test_36_progress_updates_persist_and_reload(execution_service, db_session):
    repo = Repository(db_session)
    repo.save_career_target(target_id="tgt_prog", candidate_id="cand_jane", target_role="Cloud Architect")
    repo.save_career_action(
        action_id="act_prog", candidate_id="cand_jane", target_id="tgt_prog",
        requirement_id="req_prog", action_type="STUDY_CONCEPT", title="Cloud Security", description="Study IAM", rationale="Important"
    )
    ex = execution_service.create_execution("cand_jane", "act_prog", "tgt_prog", db=db_session)
    execution_service.start_execution("cand_jane", ex.execution_id, db=db_session)

    # Update to 50%
    u50 = execution_service.update_progress("cand_jane", ex.execution_id, progress_percent=50, notes="Halfway through IAM course", db=db_session)
    assert u50.progress_percent == 50

    # Verify DB persistence
    reloaded_50 = execution_service.get_execution("cand_jane", ex.execution_id, db=db_session)
    assert reloaded_50.progress_percent == 50
    assert any("Halfway through IAM course" in n.content for n in reloaded_50.notes)

    # Update to 100%
    u100 = execution_service.update_progress("cand_jane", ex.execution_id, progress_percent=100, notes="Finished all modules", next_step="Submit artifact", db=db_session)
    assert u100.progress_percent == 100
    assert u100.next_step == "Submit artifact"

    # Verify DB persistence after fresh reload
    reloaded_100 = execution_service.get_execution("cand_jane", ex.execution_id, db=db_session)
    assert reloaded_100.progress_percent == 100
    assert reloaded_100.next_step == "Submit artifact"
    assert len(reloaded_100.notes) == 2

    # Timeline contains PROGRESS_UPDATED events
    events = execution_service._get_timeline_events("tgt_prog", "cand_jane", db=db_session)
    prog_events = [e for e in events if e.event_type == TimelineEventType.PROGRESS_UPDATED]
    assert len(prog_events) == 2
    assert prog_events[0].metadata.get("progress_percent") == 50
    assert prog_events[1].metadata.get("progress_percent") == 100


# ---------------------------------------------------------------------------
# 37. Regression: Completion Does NOT Grant Evidence, Skills, or Coverage
# ---------------------------------------------------------------------------
def test_37_completion_does_not_grant_evidence_or_skills_or_coverage(
    execution_service, db_session, candidate_jane_twin, candidate_jane_vault
):
    repo = Repository(db_session)
    initial_skills_count = len(candidate_jane_twin.skills)
    initial_vault_count = len(candidate_jane_vault.items)

    repo.save_career_target(
        target_id="tgt_strict",
        candidate_id="cand_jane",
        target_role="GraphQL Developer",
        raw_jd_text="Role: GraphQL Developer\nRequirements:\n- Apollo GraphQL API architecture\n",
        requirements=[{"requirement_id": "req_gql", "requirement_text": "Apollo GraphQL API architecture", "priority": "REQUIRED"}]
    )
    repo.save_career_action(
        action_id="act_gql", candidate_id="cand_jane", target_id="tgt_strict",
        requirement_id="req_gql", action_type="BUILD_PROJECT", title="Build GraphQL API", description="Build GraphQL API with Apollo", rationale="Fills gap"
    )

    ex = execution_service.create_execution("cand_jane", "act_gql", "tgt_strict", db=db_session)
    execution_service.start_execution("cand_jane", ex.execution_id, db=db_session)

    # Candidate self-reports 100% and completes
    execution_service.update_progress("cand_jane", ex.execution_id, 100, notes="I know GraphQL now", db=db_session)
    completed = execution_service.complete_self_reported("cand_jane", ex.execution_id, notes="Finished project", db=db_session)
    assert completed.status == ExecutionStatus.COMPLETED
    assert completed.progress_percent == 100

    # 1. Twin skills MUST NOT have changed
    assert len(candidate_jane_twin.skills) == initial_skills_count
    assert not any("graphql" in s.lower() for s in candidate_jane_twin.skills)
    assert not any("apollo" in s.lower() for s in candidate_jane_twin.skills)

    # 2. Evidence vault MUST NOT have received any unverified items
    assert len(candidate_jane_vault.items) == initial_vault_count
    assert not any("graphql" in it.source_text.lower() for it in candidate_jane_vault.items)

    # 3. Requirement progress state must remain MISSING with 0 evidence
    progress_before = execution_service.get_target_progress("tgt_strict", "cand_jane", twin=candidate_jane_twin, vault=candidate_jane_vault, db=db_session)
    gql_req = next(r for r in progress_before.requirements if r.requirement_id == "req_gql")
    assert gql_req.current_state in ["MISSING", "PARTIAL"]
    assert gql_req.evidence_count == 0

    # 4. Now submit authentic artifact and verify: ONLY THEN evidence & skills change
    execution_service.submit_artifact(
        "cand_jane", ex.execution_id,
        name="Apollo GraphQL Gateway",
        artifact_type=ArtifactType.GITHUB_REPO,
        url_or_path="https://github.com/janedoe/apollo-gateway",
        description="Production Apollo GraphQL federation gateway with schemas and resolvers.",
        technologies=["GraphQL", "Apollo"],
        db=db_session
    )

    claims = [
        EvidenceClaimSubmission(
            claim_text="Implemented production Apollo GraphQL federation gateway with schemas and resolvers.",
            source_snippet="Implemented production Apollo GraphQL federation gateway with schemas and resolvers at https://github.com/janedoe/apollo-gateway",
            evidence_type="PROJECT",
            source_document="https://github.com/janedoe/apollo-gateway",
            related_technologies=["GraphQL", "Apollo"],
            related_skill="GraphQL",
        )
    ]
    res = execution_service.verify_evidence("cand_jane", ex.execution_id, claims, db=db_session, twin=candidate_jane_twin, vault=candidate_jane_vault)
    assert res.verified is True
    assert res.verified_count == 1

    # Now vault and twin reflect verified evidence
    assert any("graphql" in s.lower() for s in candidate_jane_twin.skills)
    assert any("graphql" in it.source_text.lower() for it in candidate_jane_vault.items)

    # Requirement progress now shows evidence
    progress_after = execution_service.get_target_progress("tgt_strict", "cand_jane", twin=candidate_jane_twin, vault=candidate_jane_vault, db=db_session)
    gql_req_after = next(r for r in progress_after.requirements if r.requirement_id == "req_gql")
    assert gql_req_after.evidence_count >= 1


# ---------------------------------------------------------------------------
# 38. Regression: Execution Timeline Sequence Audit
# ---------------------------------------------------------------------------
def test_38_execution_timeline_sequence_audit(
    execution_service, db_session, candidate_jane_twin, candidate_jane_vault
):
    repo = Repository(db_session)
    repo.save_career_target(target_id="tgt_time", candidate_id="cand_jane", target_role="Site Reliability Engineer")
    repo.save_career_action(
        action_id="act_time", candidate_id="cand_jane", target_id="tgt_time",
        requirement_id="req_sre", action_type="BUILD_PROJECT", title="Prometheus Monitoring", description="Setup alerting", rationale="Essential"
    )
    ex = execution_service.create_execution("cand_jane", "act_time", "tgt_time", db=db_session)

    # 1. Action started
    execution_service.start_execution("cand_jane", ex.execution_id, db=db_session)
    # 2. Progress update
    execution_service.update_progress("cand_jane", ex.execution_id, 50, notes="Halfway", db=db_session)
    # 3. Blocker recorded
    execution_service.report_blocker("cand_jane", ex.execution_id, "Cluster credentials expired", next_step="Request token", db=db_session)
    # 4. Completed (self-reported)
    execution_service.complete_self_reported("cand_jane", ex.execution_id, notes="Alerts configured", db=db_session)
    # 5. Artifact submitted
    execution_service.submit_artifact(
        "cand_jane", ex.execution_id,
        name="Prometheus Config",
        artifact_type=ArtifactType.GITHUB_REPO,
        url_or_path="https://github.com/janedoe/prom-rules",
        description="Prometheus alert rules for cluster monitoring.",
        technologies=["Prometheus"],
        db=db_session
    )
    # 6. Evidence verified
    claims = [
        EvidenceClaimSubmission(
            claim_text="Implemented Prometheus alert rules and metrics collection for cluster monitoring.",
            source_snippet="Implemented Prometheus alert rules and metrics collection at https://github.com/janedoe/prom-rules",
            evidence_type="PROJECT",
            source_document="https://github.com/janedoe/prom-rules",
            related_technologies=["Prometheus"],
            related_skill="Prometheus",
        )
    ]
    execution_service.verify_evidence("cand_jane", ex.execution_id, claims, db=db_session, twin=candidate_jane_twin, vault=candidate_jane_vault)

    # Verify timeline sequence
    prog = execution_service.get_target_progress("tgt_time", "cand_jane", twin=candidate_jane_twin, vault=candidate_jane_vault, db=db_session)
    timeline_types = [e.event_type for e in prog.timeline]

    assert TimelineEventType.ACTION_STARTED in timeline_types
    assert TimelineEventType.PROGRESS_UPDATED in timeline_types
    assert TimelineEventType.BLOCKER_RECORDED in timeline_types
    assert TimelineEventType.SELF_REPORTED_COMPLETE in timeline_types
    assert TimelineEventType.ARTIFACT_SUBMITTED in timeline_types
    assert TimelineEventType.EVIDENCE_VERIFIED in timeline_types
    assert TimelineEventType.CAREER_TWIN_REFRESHED in timeline_types
    assert TimelineEventType.JOB_FIT_REFRESHED in timeline_types

