import pytest
import datetime
import secrets
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db.database import Base, get_db
from app.db.repository import Repository
from app.main import app
from app.api.routes.coach import _in_memory_twins, _in_memory_vaults
from app.schemas.career_twin import CareerTwin, CareerSkillNode, CareerProjectNode
from app.schemas.evidence_vault import EvidenceVault, VaultEvidenceItem
from app.schemas.candidate import (
    CandidateProfile,
    CandidateSkill,
    CandidateProject,
    CandidateExperience,
    CandidateEducation,
    CandidateCertification,
)
from app.schemas.career_intelligence import CareerTarget, TargetStatus
from app.schemas.showcase import (
    ShowcaseVisibility,
    UpdateShowcaseRequest,
    PublicCareerShowcase,
    CareerShowcase,
)
from app.services.coach.showcase.service import CareerShowcaseService


@pytest.fixture
def db_session():
    """Provides an isolated in-memory SQLite database session using StaticPool."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def test_client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def jane_evidence_vault():
    """Verified Evidence Vault for Jane Doe."""
    items = [
        VaultEvidenceItem(
            evidence_id="ev_py_01",
            candidate_id="cand_jane",
            section="experience",
            source_section="experience",
            evidence_type="EXPERIENCE",
            source_text="Developed microservices and RESTful APIs using Python and Flask.",
            confidence=0.98,
            keywords=["Python", "Flask", "microservices"],
            verified=True,
            claim_scope="LEVEL 3 — IMPLEMENTATION",
            related_skill="Python",
            related_experience="DataFlow Systems",
        ),
        VaultEvidenceItem(
            evidence_id="ev_doc_01",
            candidate_id="cand_jane",
            section="experience",
            source_section="experience",
            evidence_type="EXPERIENCE",
            source_text="Containerized services using Docker for local dev and CI pipelines.",
            confidence=0.95,
            keywords=["Docker"],
            verified=True,
            claim_scope="LEVEL 2 — USAGE",
            related_skill="Docker",
            related_experience="DataFlow Systems",
        ),
        VaultEvidenceItem(
            evidence_id="ev_k8s_01",
            candidate_id="cand_jane",
            section="projects",
            source_section="projects",
            evidence_type="PROJECT",
            source_text="Explored Kubernetes technology presence for container orchestration in CloudSync.",
            confidence=0.90,
            keywords=["Kubernetes"],
            verified=True,
            claim_scope="LEVEL 1 — TECHNOLOGY PRESENCE",
            related_skill="Kubernetes",
            related_project="CloudSync Engine",
        ),
        VaultEvidenceItem(
            evidence_id="ev_proj_cs",
            candidate_id="cand_jane",
            section="projects",
            source_section="projects",
            evidence_type="PROJECT",
            source_text="Built CloudSync Engine to synchronize distributed data across worker nodes.",
            confidence=0.96,
            keywords=["Python", "Flask", "Docker", "CloudSync Engine"],
            verified=True,
            claim_scope="LEVEL 3 — IMPLEMENTATION",
            related_project="CloudSync Engine",
        ),
        VaultEvidenceItem(
            evidence_id="ev_edu_01",
            candidate_id="cand_jane",
            section="education",
            source_section="education",
            evidence_type="EDUCATION",
            source_text="B.S. in Computer Science from State University, 2021.",
            confidence=0.99,
            keywords=["Computer Science", "B.S."],
            verified=True,
            claim_scope="LEVEL 3 — IMPLEMENTATION",
        ),
        VaultEvidenceItem(
            evidence_id="ev_cert_01",
            candidate_id="cand_jane",
            section="certifications",
            source_section="certifications",
            evidence_type="CERTIFICATION",
            source_text="Certified Kubernetes Associate (CKA) obtained in 2023.",
            confidence=0.99,
            keywords=["CKA", "Kubernetes"],
            verified=True,
            claim_scope="LEVEL 2 — USAGE",
        ),
    ]
    return EvidenceVault(
        vault_id="vault_cand_jane",
        candidate_id="cand_jane",
        items=items,
        total_items=len(items),
        verified_items=len(items),
    )


@pytest.fixture
def jane_career_twin():
    """Verified Career Twin for Jane Doe."""
    return CareerTwin(
        twin_id="twin_cand_jane",
        candidate_id="cand_jane",
        name="Jane Doe",
        email="jane@example.com",
        summary="Backend Software Engineer with hands-on Python and Docker experience.",
        skills=["Python", "Flask", "Docker", "Kubernetes"],
        skill_nodes=[
            CareerSkillNode(
                name="Python",
                category="technology",
                occurrence_count=4,
                evidence_references=["ev_py_01", "ev_proj_cs"],
            ),
            CareerSkillNode(
                name="Flask",
                category="technology",
                occurrence_count=3,
                evidence_references=["ev_py_01", "ev_proj_cs"],
            ),
            CareerSkillNode(
                name="Docker",
                category="technology",
                occurrence_count=2,
                evidence_references=["ev_doc_01"],
            ),
            CareerSkillNode(
                name="Kubernetes",
                category="technology",
                occurrence_count=1,
                evidence_references=["ev_k8s_01", "ev_cert_01"],
            ),
        ],
        experience=[
            CandidateExperience(
                role="Backend Engineer",
                company="DataFlow Systems",
                start_date="2022-01",
                end_date="Present",
                is_current=True,
                description="Developed microservices and RESTful APIs using Python and Flask. Containerized services using Docker for local dev and CI pipelines.",
                technologies=["Python", "Flask", "Docker"],
            )
        ],
        projects=[
            CandidateProject(
                name="CloudSync Engine",
                description="Built CloudSync Engine to synchronize distributed data across worker nodes.",
                technologies=["Python", "Flask", "Docker", "Kubernetes"],
            )
        ],
        education=[
            CandidateEducation(
                institution="State University",
                degree="B.S. in Computer Science",
                end_date="2021",
            )
        ],
        certifications=[
            CandidateCertification(
                name="Certified Kubernetes Associate (CKA)",
                issuer="Linux Foundation",
                date="2023",
            )
        ],
    )


@pytest.fixture(autouse=True)
def setup_jane_in_db_and_memory(db_session, jane_career_twin, jane_evidence_vault):
    """Seed Jane into DB and in-memory caches."""
    repo = Repository(db_session)
    repo.save_candidate_profile(
        candidate_id="cand_jane",
        name=jane_career_twin.name,
        email=jane_career_twin.email,
        phone=jane_career_twin.phone,
        summary=jane_career_twin.summary,
        profile_dict=jane_career_twin.model_dump(),
    )
    # Save evidence batch
    items_dict = [
        {
            "evidence_id": item.evidence_id,
            "source_text": item.source_text,
            "source_document": item.source_document,
            "source_section": item.source_section,
            "page_number": item.page_number or 1,
            "evidence_type": item.evidence_type or "general",
            "confidence": item.confidence,
            "related_skill": item.related_skill,
            "related_project": item.related_project,
            "related_experience": item.related_experience,
            "related_technologies": item.related_technologies,
            "normalized_facts": item.normalized_facts,
        }
        for item in jane_evidence_vault.items
    ]
    repo.save_evidence_batch("cand_jane", items_dict)
    _in_memory_twins["cand_jane"] = jane_career_twin
    _in_memory_vaults["cand_jane"] = jane_evidence_vault
    yield
    _in_memory_twins.pop("cand_jane", None)
    _in_memory_vaults.pop("cand_jane", None)


# ---------------------------------------------------------------------------
# 1. SHOWCASE CREATION
# ---------------------------------------------------------------------------
def test_01_showcase_creation(db_session, jane_career_twin, jane_evidence_vault):
    service = CareerShowcaseService()
    showcase = service.get_candidate_showcase("cand_jane", jane_career_twin, jane_evidence_vault, db_session)

    assert showcase is not None
    assert showcase.candidate_id == "cand_jane"
    assert showcase.candidate_name == "Jane Doe"
    assert showcase.visibility == ShowcaseVisibility.PRIVATE
    assert showcase.showcase_id.startswith("showcase_")


# ---------------------------------------------------------------------------
# 2. VERIFIED-ONLY SHOWCASE
# ---------------------------------------------------------------------------
def test_02_verified_only_showcase(db_session, jane_career_twin, jane_evidence_vault):
    service = CareerShowcaseService()
    showcase = service.get_candidate_showcase("cand_jane", jane_career_twin, jane_evidence_vault, db_session)

    assert len(showcase.verified_skills) > 0
    for skill in showcase.verified_skills:
        assert len(skill.evidence_ids) > 0
        assert skill.claim_scope != ""

    for exp in showcase.verified_experience:
        assert len(exp.evidence_ids) > 0

    for proj in showcase.verified_projects:
        assert len(proj.evidence_ids) > 0


# ---------------------------------------------------------------------------
# 3. UNSUPPORTED CLAIM REJECTION
# ---------------------------------------------------------------------------
def test_03_unsupported_claim_rejection(db_session, jane_career_twin, jane_evidence_vault):
    # Add an unverified skill with NO evidence in vault
    jane_career_twin.skills.append("Rust")
    service = CareerShowcaseService()
    showcase = service.get_candidate_showcase("cand_jane", jane_career_twin, jane_evidence_vault, db_session)

    skill_names = [s.name for s in showcase.verified_skills]
    assert "Rust" not in skill_names


# ---------------------------------------------------------------------------
# 4. CLAIM SCOPE PRESERVATION
# ---------------------------------------------------------------------------
def test_04_claim_scope_preservation(db_session, jane_career_twin, jane_evidence_vault):
    service = CareerShowcaseService()
    showcase = service.get_candidate_showcase("cand_jane", jane_career_twin, jane_evidence_vault, db_session)

    k8s_skill = next((s for s in showcase.verified_skills if s.name == "Kubernetes"), None)
    assert k8s_skill is not None
    # Must NOT be escalated to Level 4 or Level 5
    assert "OPERATIONAL" not in k8s_skill.claim_scope
    assert "TECHNOLOGY PRESENCE" in k8s_skill.claim_scope or "USAGE" in k8s_skill.claim_scope

    python_skill = next(s for s in showcase.verified_skills if s.name == "Python")
    assert "IMPLEMENTATION" in python_skill.claim_scope


# ---------------------------------------------------------------------------
# 5. PROJECT SHOWCASE
# ---------------------------------------------------------------------------
def test_05_project_showcase(db_session, jane_career_twin, jane_evidence_vault):
    service = CareerShowcaseService()
    showcase = service.get_candidate_showcase("cand_jane", jane_career_twin, jane_evidence_vault, db_session)

    assert len(showcase.verified_projects) == 1
    proj = showcase.verified_projects[0]
    assert proj.name == "CloudSync Engine"
    assert "Python" in proj.technologies
    assert any("ev_proj_cs" in eid or "ev_k8s_01" in eid for eid in proj.evidence_ids)


# ---------------------------------------------------------------------------
# 6. PROJECT STORY BUILDER
# ---------------------------------------------------------------------------
def test_06_project_story_builder(db_session, jane_career_twin, jane_evidence_vault):
    service = CareerShowcaseService()
    showcase = service.get_candidate_showcase("cand_jane", jane_career_twin, jane_evidence_vault, db_session)

    assert len(showcase.project_stories) == 1
    story = showcase.project_stories[0]
    assert story.project_name == "CloudSync Engine"
    assert "CloudSync" in story.context or "Python" in story.context
    assert story.problem != ""
    assert story.approach != ""
    assert story.implementation != ""
    # Should use honest wording and not fabricate arbitrary % metrics
    assert "100M users" not in (story.result or "")
    assert "99.999%" not in (story.result or "")


# ---------------------------------------------------------------------------
# 7. TARGET-ALIGNED SHOWCASE
# ---------------------------------------------------------------------------
def test_07_target_aligned_showcase(db_session, jane_career_twin, jane_evidence_vault):
    repo = Repository(db_session)
    repo.save_career_target(
        target_id="tgt_senior_be",
        candidate_id="cand_jane",
        target_role="Senior Backend Engineer",
        target_company="Cloud Infrastructure",
        status="ACTIVE",
        requirements=[
            {"requirement_id": "req_py", "title": "Python microservices", "type": "skill"},
            {"requirement_id": "req_k8s_prod", "title": "Production Kubernetes management", "type": "experience"},
            {"requirement_id": "req_aws", "title": "AWS Cloud deployment", "type": "skill"},
        ],
    )

    service = CareerShowcaseService()
    service.update_showcase(
        "cand_jane",
        UpdateShowcaseRequest(selected_target_id="tgt_senior_be", show_target_alignment=True),
        jane_career_twin,
        jane_evidence_vault,
        db_session,
    )

    showcase = service.get_candidate_showcase("cand_jane", jane_career_twin, jane_evidence_vault, db_session)
    assert showcase.target_alignment is not None
    assert showcase.target_alignment.target_role == "Senior Backend Engineer"
    assert len(showcase.target_alignment.verified_strengths) > 0
    # Gaps must be honestly visible and NOT suppressed
    assert len(showcase.target_alignment.experience_gaps) > 0 or len(showcase.target_alignment.visibility_gaps) > 0


# ---------------------------------------------------------------------------
# 8. PRIVACY CONTROLS (DEFAULT PRIVATE)
# ---------------------------------------------------------------------------
def test_08_privacy_controls(db_session, jane_career_twin, jane_evidence_vault):
    service = CareerShowcaseService()
    showcase = service.get_candidate_showcase("cand_jane", jane_career_twin, jane_evidence_vault, db_session)
    assert showcase.visibility == ShowcaseVisibility.PRIVATE

    # Update to SHAREABLE
    updated = service.update_showcase(
        "cand_jane",
        UpdateShowcaseRequest(visibility=ShowcaseVisibility.SHAREABLE),
        jane_career_twin,
        jane_evidence_vault,
        db_session,
    )
    assert updated.visibility == ShowcaseVisibility.SHAREABLE


# ---------------------------------------------------------------------------
# 9. SHARE TOKEN CREATION
# ---------------------------------------------------------------------------
def test_09_share_token_creation(db_session):
    service = CareerShowcaseService()
    token_resp = service.generate_share_token("cand_jane", db_session)

    assert token_resp.share_token != ""
    assert token_resp.visibility == ShowcaseVisibility.SHAREABLE
    assert f"/showcase/{token_resp.share_token}" in token_resp.share_url


# ---------------------------------------------------------------------------
# 10. SHARE TOKEN UNPREDICTABILITY
# ---------------------------------------------------------------------------
def test_10_share_token_unpredictability(db_session):
    service = CareerShowcaseService()
    token1 = service.generate_share_token("cand_jane", db_session).share_token
    token2 = service.generate_share_token("cand_jane", db_session).share_token

    assert len(token1) >= 32
    assert len(token2) >= 32
    assert token1 != token2
    assert not token1.isdigit()


# ---------------------------------------------------------------------------
# 11. SHARE TOKEN REVOCATION
# ---------------------------------------------------------------------------
def test_11_share_token_revocation(db_session):
    service = CareerShowcaseService()
    token = service.generate_share_token("cand_jane", db_session).share_token

    revoke_resp = service.revoke_share_token("cand_jane", db_session)
    assert revoke_resp.revoked is True
    assert revoke_resp.visibility == ShowcaseVisibility.PRIVATE

    # Token lookup should now raise PermissionError
    with pytest.raises(PermissionError):
        service.get_public_showcase_by_token(token, db_session)


# ---------------------------------------------------------------------------
# 12. PRIVATE SHOWCASE PROTECTION
# ---------------------------------------------------------------------------
def test_12_private_showcase_protection(test_client):
    res = test_client.get("/api/coach/showcase/public/unknown_token_123")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 13. CANDIDATE ISOLATION
# ---------------------------------------------------------------------------
def test_13_candidate_isolation(test_client):
    # Bob requests Jane's private showcase via authenticated API -> 403 Forbidden
    headers = {"X-Candidate-ID": "cand_bob"}
    res = test_client.get("/api/coach/showcase/cand_jane", headers=headers)
    assert res.status_code == 403
    assert "Access denied" in res.json()["detail"]


# ---------------------------------------------------------------------------
# 14. CROSS-CANDIDATE MUTATION PROTECTION (IDOR)
# ---------------------------------------------------------------------------
def test_14_cross_candidate_mutation_protection(test_client):
    # Bob attempts to update Jane's headline -> 403 Forbidden
    headers = {"X-Candidate-ID": "cand_bob"}
    payload = {"headline": "Hacked headline"}
    res = test_client.put("/api/coach/showcase/cand_jane", json=payload, headers=headers)
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# 15. EXPORT INTEGRITY
# ---------------------------------------------------------------------------
def test_15_export_integrity(db_session, jane_career_twin, jane_evidence_vault):
    service = CareerShowcaseService()
    export_data = service.export_showcase_data("cand_jane", jane_career_twin, jane_evidence_vault, db_session)

    assert export_data["name"] == "Jane Doe"
    assert "skills" in export_data
    assert "projects" in export_data
    assert export_data["provenance_verified"] is True
    for s in export_data["skills"]:
        assert len(s["evidence_claims"]) > 0


# ---------------------------------------------------------------------------
# 16. NO FABRICATED CLAIMS
# ---------------------------------------------------------------------------
def test_16_no_fabricated_claims(db_session, jane_career_twin, jane_evidence_vault):
    service = CareerShowcaseService()
    showcase = service.get_candidate_showcase("cand_jane", jane_career_twin, jane_evidence_vault, db_session)

    # Every item in verified_skills must have a valid non-empty evidence_claims list
    for skill in showcase.verified_skills:
        assert len(skill.evidence_claims) > 0
        for claim in skill.evidence_claims:
            assert claim.evidence_id.startswith("ev_")


# ---------------------------------------------------------------------------
# 17. NO AUTOMATIC SKILL GRANTING
# ---------------------------------------------------------------------------
def test_17_no_automatic_skill_granting(db_session, jane_career_twin, jane_evidence_vault):
    service = CareerShowcaseService()
    showcase = service.get_candidate_showcase("cand_jane", jane_career_twin, jane_evidence_vault, db_session)

    # Jane never mentioned or verified C++, Rust, or Ruby
    names = [s.name for s in showcase.verified_skills]
    assert "C++" not in names
    assert "Rust" not in names
    assert "Ruby" not in names


# ---------------------------------------------------------------------------
# 18. NO AUTOMATIC EXPERIENCE GRANTING
# ---------------------------------------------------------------------------
def test_18_no_automatic_experience_granting(db_session, jane_career_twin, jane_evidence_vault):
    service = CareerShowcaseService()
    showcase = service.get_candidate_showcase("cand_jane", jane_career_twin, jane_evidence_vault, db_session)

    for exp in showcase.verified_experience:
        assert exp.company == "DataFlow Systems"
        assert exp.role == "Backend Engineer"


# ---------------------------------------------------------------------------
# 19. EVIDENCE PROVENANCE RETAINED
# ---------------------------------------------------------------------------
def test_19_evidence_provenance_retained(db_session, jane_career_twin, jane_evidence_vault):
    service = CareerShowcaseService()
    showcase = service.get_candidate_showcase("cand_jane", jane_career_twin, jane_evidence_vault, db_session)

    py = next(s for s in showcase.verified_skills if s.name == "Python")
    assert len(py.source_snippets) > 0
    assert len(py.evidence_ids) > 0
    assert "ev_py_01" in py.evidence_ids


# ---------------------------------------------------------------------------
# 20. TARGET PROGRESS DISPLAY
# ---------------------------------------------------------------------------
def test_20_target_progress_display(db_session, jane_career_twin, jane_evidence_vault):
    repo = Repository(db_session)
    repo.save_career_target(
        target_id="tgt_be",
        candidate_id="cand_jane",
        target_role="Backend Developer",
        target_company="Tech",
        status="ACTIVE",
        requirements=[
            {"requirement_id": "r1", "title": "Python microservices", "type": "skill"},
        ],
    )

    service = CareerShowcaseService()
    service.update_showcase(
        "cand_jane",
        UpdateShowcaseRequest(selected_target_id="tgt_be"),
        jane_career_twin,
        jane_evidence_vault,
        db_session
    )
    showcase = service.get_candidate_showcase("cand_jane", jane_career_twin, jane_evidence_vault, db_session)

    assert showcase.target_alignment is not None
    assert showcase.target_alignment.target_role == "Backend Developer"
    assert len(showcase.target_alignment.verified_strengths) > 0


# ---------------------------------------------------------------------------
# 21. CAREER EXECUTION INTEGRATION
# ---------------------------------------------------------------------------
def test_21_career_execution_integration(db_session, jane_career_twin, jane_evidence_vault):
    # Add a verified evidence item for Redis
    new_ev = VaultEvidenceItem(
        evidence_id="ev_redis_01",
        candidate_id="cand_jane",
        section="projects",
        source_section="projects",
        evidence_type="PROJECT",
        source_text="Implemented Redis distributed caching for performance acceleration.",
        confidence=0.97,
        keywords=["Redis", "caching"],
        verified=True,
        claim_scope="LEVEL 3 — IMPLEMENTATION",
        related_skill="Redis",
    )
    jane_evidence_vault.items.append(new_ev)
    jane_evidence_vault.total_items += 1

    jane_career_twin.skills.append("Redis")
    jane_career_twin.skill_nodes.append(
        CareerSkillNode(name="Redis", evidence_references=["ev_redis_01"])
    )

    service = CareerShowcaseService()
    showcase = service.get_candidate_showcase("cand_jane", jane_career_twin, jane_evidence_vault, db_session)

    redis_skill = next((s for s in showcase.verified_skills if s.name == "Redis"), None)
    assert redis_skill is not None
    assert "ev_redis_01" in redis_skill.evidence_ids


# ---------------------------------------------------------------------------
# 22. INTERVIEW READINESS INTEGRATION
# ---------------------------------------------------------------------------
def test_22_interview_readiness_integration(db_session, jane_career_twin, jane_evidence_vault):
    service = CareerShowcaseService()
    showcase = service.get_candidate_showcase("cand_jane", jane_career_twin, jane_evidence_vault, db_session)

    assert len(showcase.project_stories) >= 1
    story = showcase.project_stories[0]
    assert story.context != ""
    assert story.problem != ""
    assert story.approach != ""
    assert story.implementation != ""
    assert story.result != ""
    assert story.learning != ""


# ---------------------------------------------------------------------------
# 23. RESUME BUILDER INTEGRATION
# ---------------------------------------------------------------------------
def test_23_resume_builder_integration(db_session, jane_career_twin, jane_evidence_vault):
    service = CareerShowcaseService()
    showcase = service.get_candidate_showcase("cand_jane", jane_career_twin, jane_evidence_vault, db_session)

    assert len(showcase.verified_experience) > 0
    exp = showcase.verified_experience[0]
    assert any("microservices" in r.lower() for r in exp.verified_responsibilities)


# ---------------------------------------------------------------------------
# 24. CAREER INTELLIGENCE INTEGRATION
# ---------------------------------------------------------------------------
def test_24_career_intelligence_integration(db_session, jane_career_twin, jane_evidence_vault):
    repo = Repository(db_session)
    repo.save_career_target(
        target_id="tgt_lead",
        candidate_id="cand_jane",
        target_role="Lead Architect",
        target_company="Enterprise",
        status="ACTIVE",
        requirements=[
            {"requirement_id": "r_arch", "title": "Enterprise Architecture", "type": "experience"},
        ],
    )

    service = CareerShowcaseService()
    service.update_showcase(
        "cand_jane",
        UpdateShowcaseRequest(selected_target_id="tgt_lead"),
        jane_career_twin,
        jane_evidence_vault,
        db_session
    )
    showcase = service.get_candidate_showcase("cand_jane", jane_career_twin, jane_evidence_vault, db_session)

    assert showcase.target_alignment is not None
    # Experience gap is identified honestly
    assert len(showcase.target_alignment.experience_gaps) >= 1 or len(showcase.target_alignment.visibility_gaps) >= 1


# ---------------------------------------------------------------------------
# 25. MALFORMED INPUT REJECTION
# ---------------------------------------------------------------------------
def test_25_malformed_input_rejection(test_client):
    headers = {"X-Candidate-ID": "cand_jane"}
    res = test_client.put(
        "/api/coach/showcase/cand_jane",
        json={"visibility": "SUPER_PUBLIC_EVERYWHERE"},
        headers=headers,
    )
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# 26. AUTHORIZATION FAILURES
# ---------------------------------------------------------------------------
def test_26_authorization_failures(test_client):
    res_bad = test_client.post(
        "/api/coach/showcase/cand_jane/share-token",
        headers={"X-Candidate-ID": "cand_eve"},
    )
    assert res_bad.status_code == 403


# ---------------------------------------------------------------------------
# 27. FORGED IDS
# ---------------------------------------------------------------------------
def test_27_forged_ids(test_client):
    headers = {"X-Candidate-ID": "cand_nonexistent"}
    res = test_client.get("/api/coach/showcase/cand_nonexistent", headers=headers)
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# 28. FORGED EVIDENCE IDS
# ---------------------------------------------------------------------------
def test_28_forged_evidence_ids(db_session, jane_career_twin, jane_evidence_vault):
    # Add a forged skill without backing vault evidence
    jane_career_twin.skills.append("Quantum Computing")
    service = CareerShowcaseService()
    showcase = service.get_candidate_showcase("cand_jane", jane_career_twin, jane_evidence_vault, db_session)

    skill_names = [s.name for s in showcase.verified_skills]
    assert "Quantum Computing" not in skill_names


# ---------------------------------------------------------------------------
# 29. STATUS TAMPERING
# ---------------------------------------------------------------------------
def test_29_status_tampering(test_client):
    headers = {"X-Candidate-ID": "cand_jane"}
    res = test_client.put(
        "/api/coach/showcase/cand_jane",
        json={"headline": "Valid Headline", "fake_status": "SUPER_ADMIN"},
        headers=headers,
    )
    assert res.status_code == 200
    assert "fake_status" not in res.json()


# ---------------------------------------------------------------------------
# 30. CLAIM SCOPE TAMPERING
# ---------------------------------------------------------------------------
def test_30_claim_scope_tampering(test_client):
    headers = {"X-Candidate-ID": "cand_jane"}
    res = test_client.put(
        "/api/coach/showcase/cand_jane",
        json={"claim_scope": "LEVEL 5 — SPECIFIC SCOPE"},
        headers=headers,
    )
    assert res.status_code == 200
    get_res = test_client.get("/api/coach/showcase/cand_jane", headers=headers)
    k8s = next(s for s in get_res.json()["skills"] if s["name"] == "Kubernetes")
    assert "LEVEL 5" not in k8s["claim_scope"]


# ---------------------------------------------------------------------------
# 31. SECRET EXPOSURE CHECKS IN PUBLIC SHOWCASE
# ---------------------------------------------------------------------------
def test_31_secret_exposure_checks_in_public_showcase(db_session):
    service = CareerShowcaseService()
    token = service.generate_share_token("cand_jane", db_session).share_token

    public_showcase = service.get_public_showcase_by_token(token, db_session)
    assert public_showcase is not None

    pub_dict = public_showcase.model_dump()
    assert "candidate_id" not in pub_dict
    assert "id" not in pub_dict
    assert "email" not in pub_dict
    assert "phone" not in pub_dict


# ---------------------------------------------------------------------------
# 32. UNSAFE FILE HANDLING
# ---------------------------------------------------------------------------
def test_32_unsafe_file_handling(test_client):
    headers = {"X-Candidate-ID": "../../../etc/passwd"}
    res = test_client.get("/api/coach/showcase/..%2F..%2F..%2Fetc%2Fpasswd", headers=headers)
    assert res.status_code in [400, 404]


# ---------------------------------------------------------------------------
# 33. API ERROR SANITIZATION
# ---------------------------------------------------------------------------
def test_33_api_error_sanitization(test_client):
    res = test_client.get("/api/coach/showcase/public/nonexistent_token")
    assert res.status_code == 404
    text = res.text.lower()
    assert "traceback" not in text
    assert "file \"" not in text
    assert "sqlite3" not in text


# ---------------------------------------------------------------------------
# 34. DATABASE INTEGRITY
# ---------------------------------------------------------------------------
def test_34_database_integrity(db_session):
    service = CareerShowcaseService()
    sc1 = service.get_or_create_showcase_record("cand_jane", db_session)
    sc2 = service.get_or_create_showcase_record("cand_jane", db_session)

    assert sc1.showcase_id == sc2.showcase_id


# ---------------------------------------------------------------------------
# 35. FRONTEND API INTEGRATION CONTRACTS
# ---------------------------------------------------------------------------
def test_35_frontend_api_integration_contracts(test_client):
    headers = {"X-Candidate-ID": "cand_jane"}
    res = test_client.get("/api/coach/showcase/cand_jane", headers=headers)
    assert res.status_code == 200
    data = res.json()

    expected_fields = [
        "showcase_id",
        "name",
        "headline",
        "visibility",
        "skills",
        "experience",
        "projects",
        "education",
        "certifications",
    ]
    for field in expected_fields:
        assert field in data, f"Missing {field} in frontend contract"


# ---------------------------------------------------------------------------
# 36. LOADING AND EMPTY STATES
# ---------------------------------------------------------------------------
def test_36_loading_and_empty_states(db_session, test_client):
    empty_twin = CareerTwin(twin_id="twin_empty", candidate_id="cand_empty", name="Empty Candidate")
    empty_vault = EvidenceVault(vault_id="v_empty", candidate_id="cand_empty")
    repo = Repository(db_session)
    repo.save_candidate_profile(
        candidate_id="cand_empty",
        name="Empty Candidate",
        email=None,
        phone=None,
        summary=None,
        profile_dict=empty_twin.model_dump()
    )
    _in_memory_twins["cand_empty"] = empty_twin
    _in_memory_vaults["cand_empty"] = empty_vault

    headers = {"X-Candidate-ID": "cand_empty"}
    res = test_client.get("/api/coach/showcase/cand_empty", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["skills"] == []
    assert data["projects"] == []
    assert data["experience"] == []


# ---------------------------------------------------------------------------
# 37. PUBLIC/PRIVATE VISIBILITY TRANSITIONS
# ---------------------------------------------------------------------------
def test_37_public_private_visibility_transitions(test_client):
    headers = {"X-Candidate-ID": "cand_jane"}

    # 1. Start PRIVATE
    res = test_client.get("/api/coach/showcase/cand_jane", headers=headers)
    assert res.json()["visibility"] == "PRIVATE"

    # 2. Generate share token -> SHAREABLE
    res_share = test_client.post("/api/coach/showcase/cand_jane/share-token", headers=headers)
    token = res_share.json()["share_token"]
    assert res_share.json()["visibility"] == "SHAREABLE"

    # 3. Public access succeeds
    res_pub = test_client.get(f"/api/coach/showcase/public/{token}")
    assert res_pub.status_code == 200

    # 4. Revoke share -> PRIVATE
    res_revoke = test_client.post("/api/coach/showcase/cand_jane/revoke-share", headers=headers)
    assert res_revoke.json()["visibility"] == "PRIVATE"

    # 5. Public access now returns 404
    res_pub_revoked = test_client.get(f"/api/coach/showcase/public/{token}")
    assert res_pub_revoked.status_code == 404


# ---------------------------------------------------------------------------
# 38. EXPORT CORRECTNESS
# ---------------------------------------------------------------------------
def test_38_export_correctness(test_client):
    headers = {"X-Candidate-ID": "cand_jane"}
    res = test_client.get("/api/coach/showcase/cand_jane/export", headers=headers)
    assert res.status_code == 200
    export_payload = res.json()
    assert export_payload["name"] == "Jane Doe"
    assert len(export_payload["skills"]) > 0
    assert "CloudSync Engine" in [p["name"] for p in export_payload["projects"]]


# ---------------------------------------------------------------------------
# 39. REGRESSION COVERAGE: EVIDENCE VAULT AUTHORITY PRESERVED
# ---------------------------------------------------------------------------
def test_39_regression_evidence_vault_authority(db_session, jane_career_twin, jane_evidence_vault):
    count_before = len(jane_evidence_vault.items)
    service = CareerShowcaseService()
    _ = service.get_candidate_showcase("cand_jane", jane_career_twin, jane_evidence_vault, db_session)

    # Showcase is read-only projection; NEVER mutates Evidence Vault items
    assert len(jane_evidence_vault.items) == count_before


# ---------------------------------------------------------------------------
# 40. COMPLETE END-TO-END SHOWCASE WORKFLOW
# ---------------------------------------------------------------------------
def test_40_complete_e2e_showcase_workflow(test_client):
    headers = {"X-Candidate-ID": "cand_jane"}

    # Step 1: Query Showcase
    r1 = test_client.get("/api/coach/showcase/cand_jane", headers=headers)
    assert r1.status_code == 200
    assert r1.json()["visibility"] == "PRIVATE"

    # Step 2: Update Headline and Bio
    r2 = test_client.put(
        "/api/coach/showcase/cand_jane",
        json={"headline": "Verified Distributed Systems Engineer", "bio": "Passionate about reliable systems."},
        headers=headers,
    )
    assert r2.status_code == 200
    assert r2.json()["headline"] == "Verified Distributed Systems Engineer"

    # Step 3: Generate Share Token
    r3 = test_client.post("/api/coach/showcase/cand_jane/share-token", headers=headers)
    assert r3.status_code == 200
    token = r3.json()["share_token"]

    # Step 4: Access via Public URL
    r4 = test_client.get(f"/api/coach/showcase/public/{token}")
    assert r4.status_code == 200
    public_data = r4.json()
    assert public_data["headline"] == "Verified Distributed Systems Engineer"
    assert "candidate_id" not in public_data

    # Step 5: Export verified showcase
    r5 = test_client.get("/api/coach/showcase/cand_jane/export", headers=headers)
    assert r5.status_code == 200
    assert r5.json()["name"] == "Jane Doe"

    # Step 6: Revoke share token
    r6 = test_client.post("/api/coach/showcase/cand_jane/revoke-share", headers=headers)
    assert r6.status_code == 200
    assert r6.json()["visibility"] == "PRIVATE"

    # Step 7: Public URL now returns 404
    r7 = test_client.get(f"/api/coach/showcase/public/{token}")
    assert r7.status_code == 404
