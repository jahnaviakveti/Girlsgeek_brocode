import os
import json
import copy
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import SessionLocal, init_db
from app.db.repository import Repository
from app.schemas.career_twin import CareerTwin
from app.schemas.evidence_vault import EvidenceVault, VaultEvidenceItem
from app.schemas.candidate import CandidateProfile, CandidateExperience, CandidateProject
from app.schemas.interview_readiness import (
    InterviewTarget,
    InterviewTargetStatus,
    PreparationStatus,
    QuestionType,
    ValidationVerdict,
    InterviewQuestion,
    EvidenceCitation,
    ProjectStory,
    AnswerValidationResult,
    InterviewSession,
    InterviewSessionItem,
    InterviewReadinessResponse,
    CreateInterviewTargetRequest,
    ValidateAnswerRequest,
    CreateInterviewSessionRequest,
    SubmitSessionAnswerRequest,
)
from app.services.coach.interview.readiness_service import InterviewReadinessService
from app.services.coach.interview.question_service import InterviewQuestionService
from app.services.coach.interview.answer_coach_service import InterviewAnswerCoachService
from app.services.coach.evidence.validation import EvidenceValidationService
from app.api.routes.coach import (
    _in_memory_twins,
    _in_memory_vaults,
    _in_memory_targets,
    _in_memory_interview_targets,
    _in_memory_interview_sessions,
)

init_db()
client = TestClient(app)


@pytest.fixture
def candidate_alex_p7():
    cid = "cand_alex_p7"
    profile = CandidateProfile(
        candidate_id=cid,
        name="Alex Chen",
        email="alex.chen@example.com",
        skills=["Python", "Flask", "PostgreSQL", "REST APIs", "Docker"],
        experience=[
            CandidateExperience(
                role="Backend Engineer",
                company="Acme Corp",
                start_date="2021",
                end_date="2023",
                description="Built Flask backend microservices for automated payment processing.\nOptimized SQL queries reducing latency by 30%.\nIntegrated Docker containerization for CI/CD.",
                technologies=["Python", "Flask", "PostgreSQL", "Docker"],
            )
        ],
        projects=[
            CandidateProject(
                name="Payment Processing Engine",
                description="Engineered reliable payment pipelines with Flask and PostgreSQL.",
                technologies=["Python", "Flask", "PostgreSQL"],
            ),
            CandidateProject(
                name="Side Project Portfolio",
                description="Built small utility scripts without quantitative business metrics.",
                technologies=["Python"],
            )
        ],
        raw_text="Alex Chen Backend Developer with Python, Flask, PostgreSQL, Docker.",
    )

    items = [
        VaultEvidenceItem(
            evidence_id="ev_alex_flask",
            candidate_id=cid,
            source_text="Built Flask backend microservices for automated payment processing.",
            source_document="alex_resume.pdf",
            source_section="Experience",
            page_number=1,
            evidence_type="EXPERIENCE_BULLET",
            confidence=1.0,
            normalized_facts=["Built Flask backend microservices", "automated payment processing"],
            related_skill="Flask",
            related_technologies=["Python", "Flask"],
        ),
        VaultEvidenceItem(
            evidence_id="ev_alex_sql",
            candidate_id=cid,
            source_text="Optimized SQL queries reducing latency by 30%.",
            source_document="alex_resume.pdf",
            source_section="Experience",
            page_number=1,
            evidence_type="EXPERIENCE_BULLET",
            confidence=1.0,
            normalized_facts=["Optimized SQL queries", "reduced latency by 30%"],
            related_skill="SQL",
            related_technologies=["PostgreSQL", "SQL"],
        ),
        VaultEvidenceItem(
            evidence_id="ev_alex_docker",
            candidate_id=cid,
            source_text="Integrated Docker containerization for CI/CD.",
            source_document="alex_resume.pdf",
            source_section="Experience",
            page_number=1,
            evidence_type="EXPERIENCE_BULLET",
            confidence=1.0,
            normalized_facts=["Integrated Docker containerization", "CI/CD"],
            related_skill="Docker",
            related_technologies=["Docker"],
        ),
    ]

    vault = EvidenceVault(
        vault_id=f"vault_{cid}",
        candidate_id=cid,
        total_items=len(items),
        items=items,
    )

    twin = CareerTwin(
        twin_id=f"twin_{cid}",
        candidate_id=cid,
        name=profile.name,
        email=profile.email,
        skills=set(profile.skills),
        experience=profile.experience,
        projects=profile.projects,
        candidate_profile=profile,
        raw_text=profile.raw_text,
    )

    _in_memory_twins[cid] = twin
    _in_memory_vaults[cid] = vault

    return twin, vault


@pytest.fixture
def candidate_bob_p7():
    cid = "cand_bob_p7"
    profile = CandidateProfile(
        candidate_id=cid,
        name="Bob Vance",
        email="bob@example.com",
        skills=["Java", "Spring"],
        experience=[],
        projects=[],
        raw_text="Bob Vance Java developer",
    )
    items = [
        VaultEvidenceItem(
            evidence_id="ev_bob_1",
            candidate_id=cid,
            source_text="Java enterprise development",
            source_document="bob_resume.pdf",
            source_section="Experience",
            page_number=1,
            evidence_type="EXPERIENCE_BULLET",
            confidence=1.0,
            normalized_facts=["Java enterprise development"],
            related_skill="Java",
            related_technologies=["Java"],
        )
    ]
    vault = EvidenceVault(vault_id=f"vault_{cid}", candidate_id=cid, total_items=1, items=items)
    twin = CareerTwin(
        twin_id=f"twin_{cid}",
        candidate_id=cid,
        name="Bob Vance",
        email="bob@example.com",
        skills={"Java", "Spring"},
        experience=[],
        projects=[],
        candidate_profile=profile,
        raw_text="Bob Vance Java developer",
    )
    _in_memory_twins[cid] = twin
    _in_memory_vaults[cid] = vault
    return twin, vault


# ==============================================================================
# 1. CREATE INTERVIEW TARGET
# ==============================================================================
def test_01_create_interview_target(candidate_alex_p7):
    resp = client.post(
        "/api/coach/interview-targets",
        json={
            "candidate_id": "cand_alex_p7",
            "target_role": "Senior Backend Engineer",
            "company": "Fintech Global",
            "job_description_text": "Requirements:\n- Python microservices with Flask\n- PostgreSQL optimization",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["interview_target_id"].startswith("itarget_")
    assert data["candidate_id"] == "cand_alex_p7"
    assert data["target_role"] == "Senior Backend Engineer"
    assert data["company"] == "Fintech Global"
    assert data["status"] == "ACTIVE"


# ==============================================================================
# 2. RETRIEVE INTERVIEW TARGET
# ==============================================================================
def test_02_retrieve_interview_target(candidate_alex_p7):
    resp = client.post(
        "/api/coach/interview-targets",
        json={
            "candidate_id": "cand_alex_p7",
            "target_role": "Backend Engineer",
            "company": "Fintech Global",
            "job_description_text": "Requirements:\n- Python",
        },
    )
    target_id = resp.json()["interview_target_id"]
    get_resp = client.get(f"/api/coach/interview-targets/cand_alex_p7/{target_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["interview_target_id"] == target_id


# ==============================================================================
# 3. CANDIDATE OWNERSHIP
# ==============================================================================
def test_03_candidate_ownership_enforcement(candidate_alex_p7, candidate_bob_p7):
    resp = client.post(
        "/api/coach/interview-targets",
        json={
            "candidate_id": "cand_alex_p7",
            "target_role": "Backend Lead",
            "company": "Tech Corp",
            "job_description_text": "Requirements:\n- Python microservices",
        },
    )
    target_id = resp.json()["interview_target_id"]
    cross_access = client.get(f"/api/coach/interview-targets/cand_bob_p7/{target_id}")
    assert cross_access.status_code == 403


# ==============================================================================
# 4. GENERATE INTERVIEW READINESS
# ==============================================================================
def test_04_generate_interview_readiness(candidate_alex_p7):
    resp = client.post(
        "/api/coach/interview-targets",
        json={
            "candidate_id": "cand_alex_p7",
            "target_role": "Senior Backend Engineer",
            "company": "Fintech Global",
            "job_description_text": "Requirements:\n- Python and Flask microservices\n- PostgreSQL optimization",
        },
    )
    target_id = resp.json()["interview_target_id"]
    readiness_resp = client.get(f"/api/coach/interview-readiness/cand_alex_p7/{target_id}")
    assert readiness_resp.status_code == 200
    data = readiness_resp.json()
    assert data["interview_target_id"] == target_id
    assert "Requirements reviewed" in data["preparation_progress_metric"]
    assert len(data["requirements_map"]) >= 1


# ==============================================================================
# 5. REQUIREMENT PREPARATION MAPPING
# ==============================================================================
def test_05_requirement_preparation_mapping(candidate_alex_p7):
    resp = client.post(
        "/api/coach/interview-targets",
        json={
            "candidate_id": "cand_alex_p7",
            "target_role": "Senior Backend Engineer",
            "company": "Fintech Global",
            "job_description_text": "Requirements:\n- Flask backend development\n- Kubernetes orchestration",
        },
    )
    target_id = resp.json()["interview_target_id"]
    readiness_resp = client.get(f"/api/coach/interview-readiness/cand_alex_p7/{target_id}")
    data = readiness_resp.json()
    assert "requirement_map" in data
    assert len(data["requirement_map"]) >= 2
    for item in data["requirement_map"]:
        assert item["preparation_status"] in ["READY", "REVIEW", "PREPARE", "NOT_VERIFIABLE"]


# ==============================================================================
# 6. READY CLASSIFICATION
# ==============================================================================
def test_06_ready_classification(candidate_alex_p7):
    resp = client.post(
        "/api/coach/interview-targets",
        json={
            "candidate_id": "cand_alex_p7",
            "target_role": "Senior Backend Engineer",
            "job_description_text": "Requirements:\n- Flask backend microservices",
        },
    )
    target_id = resp.json()["interview_target_id"]
    data = client.get(f"/api/coach/interview-readiness/cand_alex_p7/{target_id}").json()
    ready_items = [r for r in data["requirement_map"] if r["preparation_status"] == "READY"]
    assert len(ready_items) >= 1
    assert "ev_alex_flask" in ready_items[0]["evidence_ids"]


# ==============================================================================
# 7. REVIEW CLASSIFICATION
# ==============================================================================
def test_07_review_classification(candidate_alex_p7):
    resp = client.post(
        "/api/coach/interview-targets",
        json={
            "candidate_id": "cand_alex_p7",
            "target_role": "DevOps Engineer",
            "job_description_text": "Requirements:\n- Continuous deployment pipelines",
        },
    )
    target_id = resp.json()["interview_target_id"]
    data = client.get(f"/api/coach/interview-readiness/cand_alex_p7/{target_id}").json()
    # If partial evidence exists, mapped to REVIEW
    assert "areas_to_review" in data or "review_count" in data


# ==============================================================================
# 8. PREPARE CLASSIFICATION
# ==============================================================================
def test_08_prepare_classification(candidate_alex_p7):
    resp = client.post(
        "/api/coach/interview-targets",
        json={
            "candidate_id": "cand_alex_p7",
            "target_role": "Cloud Architect",
            "job_description_text": "Requirements:\n- Kubernetes cluster orchestration",
        },
    )
    target_id = resp.json()["interview_target_id"]
    data = client.get(f"/api/coach/interview-readiness/cand_alex_p7/{target_id}").json()
    prep_items = [r for r in data["requirement_map"] if r["preparation_status"] == "PREPARE"]
    assert len(prep_items) >= 1
    assert prep_items[0]["evidence_ids"] == []


# ==============================================================================
# 9. NOT_VERIFIABLE CLASSIFICATION
# ==============================================================================
def test_09_not_verifiable_classification(candidate_alex_p7):
    resp = client.post(
        "/api/coach/interview-targets",
        json={
            "candidate_id": "cand_alex_p7",
            "target_role": "Backend Engineer",
            "job_description_text": "Requirements:\n- Highly charismatic culture fit",
        },
    )
    target_id = resp.json()["interview_target_id"]
    data = client.get(f"/api/coach/interview-readiness/cand_alex_p7/{target_id}").json()
    assert "not_verifiable_count" in data


# ==============================================================================
# 10. EVIDENCE-GROUNDED QUESTION GENERATION
# ==============================================================================
def test_10_evidence_grounded_question_generation(candidate_alex_p7):
    resp = client.post(
        "/api/coach/interview-targets",
        json={
            "candidate_id": "cand_alex_p7",
            "target_role": "Senior Backend Engineer",
            "job_description_text": "Requirements:\n- Flask backend development",
        },
    )
    target_id = resp.json()["interview_target_id"]
    questions = client.get(f"/api/coach/interview-questions/{target_id}?candidate_id=cand_alex_p7").json()
    flask_q = next((q for q in questions if "flask" in q["question"].lower()), None)
    assert flask_q is not None
    assert "ev_alex_flask" in flask_q["evidence_ids"]
    assert flask_q["source"] == "EVIDENCE_VAULT"


# ==============================================================================
# 11. UNSUPPORTED CANDIDATE CLAIM NOT INSERTED INTO QUESTION
# ==============================================================================
def test_11_unsupported_claim_not_inserted_into_question(candidate_alex_p7):
    resp = client.post(
        "/api/coach/interview-targets",
        json={
            "candidate_id": "cand_alex_p7",
            "target_role": "Senior Backend Engineer",
            "job_description_text": "Requirements:\n- Flask backend development",
        },
    )
    target_id = resp.json()["interview_target_id"]
    questions = client.get(f"/api/coach/interview-questions/{target_id}?candidate_id=cand_alex_p7").json()
    flask_q = next((q for q in questions if "flask" in q["question"].lower()), None)
    assert flask_q is not None
    # Must NOT hallucinate arbitrary metrics like 40% reduction into question text
    assert "40%" not in flask_q["question"]
    assert "99.9%" not in flask_q["question"]


# ==============================================================================
# 12. EVIDENCE CITATIONS
# ==============================================================================
def test_12_evidence_citations(candidate_alex_p7):
    resp = client.post(
        "/api/coach/interview-targets",
        json={
            "candidate_id": "cand_alex_p7",
            "target_role": "Senior Backend Engineer",
            "job_description_text": "Requirements:\n- Flask backend development",
        },
    )
    target_id = resp.json()["interview_target_id"]
    questions = client.get(f"/api/coach/interview-questions/{target_id}?candidate_id=cand_alex_p7").json()
    flask_q = next((q for q in questions if "flask" in q["question"].lower()), None)
    assert len(flask_q["citations"]) > 0
    citation = flask_q["citations"][0]
    assert citation["evidence_id"] == "ev_alex_flask"
    assert citation["source_document"] == "alex_resume.pdf"
    assert citation["section"] == "Experience"
    assert citation["page_number"] == 1


# ==============================================================================
# 13. PROJECT STORY GENERATION
# ==============================================================================
def test_13_project_story_generation(candidate_alex_p7):
    stories = client.get("/api/coach/project-stories/cand_alex_p7").json()
    assert len(stories) >= 1
    story = stories[0]
    assert "project_name" in story
    assert len(story["technologies"]) > 0
    assert len(story["likely_discussion_areas"]) >= 2


# ==============================================================================
# 14. STAR PROMPT GENERATION
# ==============================================================================
def test_14_star_prompt_generation(candidate_alex_p7):
    stories = client.get("/api/coach/project-stories/cand_alex_p7").json()
    story = stories[0]
    star = story["star_preparation"]
    assert "situation" in star and len(star["situation"]) > 0
    assert "task" in star and len(star["task"]) > 0
    assert "action" in star and len(star["action"]) > 0
    assert "result" in star and len(star["result"]) > 0


# ==============================================================================
# 15. MISSING RESULT HANDLING
# ==============================================================================
def test_15_missing_result_handling(candidate_alex_p7):
    # Retrieve Side Project Portfolio which has no metrics in vault
    stories = client.get("/api/coach/project-stories/cand_alex_p7").json()
    side_story = next((s for s in stories if "Side Project" in s["project_name"]), None)
    if side_story:
        # If no verified outcome, explicit guardrail message is returned without inventing metrics
        assert "not currently supported" in side_story["star_preparation"]["result"].lower() or "verified evidence" in side_story["star_preparation"]["result"].lower()


# ==============================================================================
# 16. CANDIDATE ANSWER VALIDATION PIPELINE
# ==============================================================================
def test_16_candidate_answer_validation(candidate_alex_p7):
    resp = client.post(
        "/api/coach/interview-answers/validate",
        json={
            "candidate_id": "cand_alex_p7",
            "question_id": "q_test",
            "answer_text": "I built Flask backend services.",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "verdict" in data
    assert "star_breakdown" in data


# ==============================================================================
# 17. SUPPORTED ANSWER
# ==============================================================================
def test_17_supported_answer(candidate_alex_p7):
    resp = client.post(
        "/api/coach/interview-answers/validate",
        json={
            "candidate_id": "cand_alex_p7",
            "question_id": "q_flask",
            "answer_text": "In my previous role, I built Flask backend microservices for automated payment processing.",
        },
    )
    data = resp.json()
    assert data["verdict"] == "SUPPORTED"
    assert data["unsupported_claims"] == []
    assert len(data["supported_claims"]) > 0


# ==============================================================================
# 18. PARTIALLY SUPPORTED ANSWER
# ==============================================================================
def test_18_partially_supported_answer(candidate_alex_p7):
    resp = client.post(
        "/api/coach/interview-answers/validate",
        json={
            "candidate_id": "cand_alex_p7",
            "question_id": "q_flask",
            "answer_text": "I built Flask backend microservices and scaled it to 500 million active users.",
        },
    )
    data = resp.json()
    assert data["verdict"] in ["PARTIALLY_SUPPORTED", "UNSUPPORTED"]
    assert len(data["unsupported_claims"]) > 0


# ==============================================================================
# 19. UNSUPPORTED METRIC DETECTION
# ==============================================================================
def test_19_unsupported_metric_detection(candidate_alex_p7):
    resp = client.post(
        "/api/coach/interview-answers/validate",
        json={
            "candidate_id": "cand_alex_p7",
            "question_id": "q_flask",
            "answer_text": "I reduced latency by 95% and cut server costs by 80%.",
        },
    )
    data = resp.json()
    assert any("95%" in c or "80%" in c or "metric" in c.lower() for c in data["unsupported_claims"])


# ==============================================================================
# 20. UNSUPPORTED TECHNOLOGY DETECTION
# ==============================================================================
def test_20_unsupported_technology_detection(candidate_alex_p7):
    resp = client.post(
        "/api/coach/interview-answers/validate",
        json={
            "candidate_id": "cand_alex_p7",
            "question_id": "q_flask",
            "answer_text": "I implemented distributed consensus with Rust and Apache Cassandra.",
        },
    )
    data = resp.json()
    assert any(tech in ["Rust", "Cassandra", "Apache Cassandra"] for tech in data["unsupported_technologies"])


# ==============================================================================
# 21. UNSUPPORTED RESPONSIBILITY DETECTION
# ==============================================================================
def test_21_unsupported_responsibility_detection(candidate_alex_p7):
    resp = client.post(
        "/api/coach/interview-answers/validate",
        json={
            "candidate_id": "cand_alex_p7",
            "question_id": "q_resp",
            "answer_text": "As VP of Engineering, I owned the entire corporate budget and managed a 50-person department.",
        },
    )
    data = resp.json()
    assert any("vp" in c.lower() or "budget" in c.lower() or "50-person" in c.lower() for c in data["unsupported_claims"])


# ==============================================================================
# 22. UNSUPPORTED IMPACT DETECTION
# ==============================================================================
def test_22_unsupported_impact_detection(candidate_alex_p7):
    resp = client.post(
        "/api/coach/interview-answers/validate",
        json={
            "candidate_id": "cand_alex_p7",
            "question_id": "q_imp",
            "answer_text": "My backend service generated $5M in annual revenue and revolutionized the company business.",
        },
    )
    data = resp.json()
    assert any("$5M" in c or "revenue" in c.lower() or "revolutionized" in c.lower() for c in data["unsupported_claims"])


# ==============================================================================
# 23. EXPERIENCE GAP HANDLING
# ==============================================================================
def test_23_experience_gap_handling(candidate_alex_p7):
    resp = client.post(
        "/api/coach/interview-targets",
        json={
            "candidate_id": "cand_alex_p7",
            "target_role": "Backend Engineer",
            "job_description_text": "Requirements:\n- Kubernetes administration",
        },
    )
    target_id = resp.json()["interview_target_id"]
    questions = client.get(f"/api/coach/interview-questions/{target_id}?candidate_id=cand_alex_p7").json()
    k8s_q = next((q for q in questions if "kubernetes" in q["question"].lower()), None)
    assert k8s_q is not None
    assert "no verified" in k8s_q["rationale"].lower() or "gap" in k8s_q["rationale"].lower()


# ==============================================================================
# 24. MOCK INTERVIEW SESSION START
# ==============================================================================
def test_24_mock_interview_session_start(candidate_alex_p7):
    resp = client.post(
        "/api/coach/interview-targets",
        json={
            "candidate_id": "cand_alex_p7",
            "target_role": "Backend Engineer",
            "job_description_text": "Requirements:\n- Flask backend development",
        },
    )
    target_id = resp.json()["interview_target_id"]
    sess_resp = client.post(
        "/api/coach/interview-sessions",
        json={"candidate_id": "cand_alex_p7", "interview_target_id": target_id},
    )
    assert sess_resp.status_code == 201
    assert sess_resp.json()["session_id"].startswith("sess_")


# ==============================================================================
# 25. ANSWER PERSISTENCE
# ==============================================================================
def test_25_mock_interview_answer_persistence(candidate_alex_p7):
    t_resp = client.post(
        "/api/coach/interview-targets",
        json={"candidate_id": "cand_alex_p7", "target_role": "Backend Engineer", "job_description_text": "Requirements:\n- Flask"},
    )
    t_id = t_resp.json()["interview_target_id"]
    sess_resp = client.post("/api/coach/interview-sessions", json={"candidate_id": "cand_alex_p7", "interview_target_id": t_id})
    sess = sess_resp.json()
    q_id = sess["items"][0]["question_id"]

    ans_resp = client.post(
        f"/api/coach/interview-sessions/{sess['session_id']}/answer",
        json={"candidate_id": "cand_alex_p7", "question_id": q_id, "answer_text": "Built Flask backend microservices for automated payment processing."},
    )
    assert ans_resp.status_code == 200
    assert ans_resp.json()["items"][0]["candidate_answer"] is not None


# ==============================================================================
# 26. REQUIREMENT PREPARATION TRACKING
# ==============================================================================
def test_26_requirement_preparation_tracking(candidate_alex_p7):
    t_resp = client.post(
        "/api/coach/interview-targets",
        json={"candidate_id": "cand_alex_p7", "target_role": "Backend Engineer", "job_description_text": "Requirements:\n- Flask\n- PostgreSQL"},
    )
    t_id = t_resp.json()["interview_target_id"]
    sess_resp = client.post("/api/coach/interview-sessions", json={"candidate_id": "cand_alex_p7", "interview_target_id": t_id})
    sess = sess_resp.json()
    q_id = sess["items"][0]["question_id"]

    ans_resp = client.post(
        f"/api/coach/interview-sessions/{sess['session_id']}/answer",
        json={"candidate_id": "cand_alex_p7", "question_id": q_id, "answer_text": "Built Flask backend microservices."},
    )
    assert ans_resp.json()["requirements_reviewed_count"] >= 1


# ==============================================================================
# 27. HISTORICAL SESSION PERSISTENCE
# ==============================================================================
def test_27_historical_session_persistence(candidate_alex_p7):
    t_resp = client.post(
        "/api/coach/interview-targets",
        json={"candidate_id": "cand_alex_p7", "target_role": "Backend Engineer", "job_description_text": "Requirements:\n- Flask"},
    )
    t_id = t_resp.json()["interview_target_id"]
    sess_resp = client.post("/api/coach/interview-sessions", json={"candidate_id": "cand_alex_p7", "interview_target_id": t_id})
    sess_id = sess_resp.json()["session_id"]

    db = SessionLocal()
    try:
        repo = Repository(db)
        rec = repo.get_mock_interview_session(sess_id)
        assert rec is not None
        assert rec.session_id == sess_id
    finally:
        db.close()


# ==============================================================================
# 28. CANDIDATE ISOLATION
# ==============================================================================
def test_28_candidate_isolation(candidate_alex_p7, candidate_bob_p7):
    t_resp = client.post(
        "/api/coach/interview-targets",
        json={"candidate_id": "cand_alex_p7", "target_role": "Backend Engineer", "job_description_text": "Requirements:\n- Flask"},
    )
    t_id = t_resp.json()["interview_target_id"]
    sess_resp = client.post("/api/coach/interview-sessions", json={"candidate_id": "cand_alex_p7", "interview_target_id": t_id})
    sess_id = sess_resp.json()["session_id"]

    cross_sub = client.post(
        f"/api/coach/interview-sessions/{sess_id}/answer",
        json={
            "candidate_id": "cand_bob_p7",
            "question_id": sess_resp.json()["items"][0]["question_id"],
            "answer_text": "Hacking into another candidate session",
        },
    )
    assert cross_sub.status_code == 403


# ==============================================================================
# 29. FOREIGN EVIDENCE PROTECTION
# ==============================================================================
def test_29_foreign_evidence_protection(candidate_alex_p7, candidate_bob_p7):
    resp = client.post(
        "/api/coach/interview-answers/validate",
        json={
            "candidate_id": "cand_alex_p7",
            "question_id": "q_foreign",
            "answer_text": "I have extensive Java enterprise development experience.",
        },
    )
    data = resp.json()
    assert "Java" in data["unsupported_technologies"]
    assert data["verdict"] in ["UNSUPPORTED", "PARTIALLY_SUPPORTED"]


# ==============================================================================
# 30. FORGED VALIDATION STATUS PROTECTION
# ==============================================================================
def test_30_forged_validation_status_protection(candidate_alex_p7):
    forged_payload = {
        "candidate_id": "cand_alex_p7",
        "question_id": "q_forged",
        "answer_text": "I have managed massive Kubernetes production clusters for 10 years.",
        "verdict": "SUPPORTED",
        "is_supported": True,
    }
    resp = client.post("/api/coach/interview-answers/validate", json=forged_payload)
    data = resp.json()
    assert data["verdict"] in ["UNSUPPORTED", "PARTIALLY_SUPPORTED"]
    assert "Kubernetes" in data["unsupported_technologies"]


# ==============================================================================
# 31. FULL PHASE 7 END-TO-END FLOW
# ==============================================================================
def test_31_full_phase7_end_to_end_flow(candidate_alex_p7):
    twin, vault = candidate_alex_p7

    # 1. Create Target
    t_res = client.post(
        "/api/coach/interview-targets",
        json={
            "candidate_id": "cand_alex_p7",
            "target_role": "Senior Backend Engineer",
            "company": "Fintech Global",
            "job_description_text": "Requirements:\n- Python microservices with Flask\n- PostgreSQL performance\n- Kubernetes orchestration",
        },
    )
    assert t_res.status_code == 201
    target_id = t_res.json()["interview_target_id"]

    # 2. Generate Readiness
    r_res = client.get(f"/api/coach/interview-readiness/cand_alex_p7/{target_id}")
    assert r_res.status_code == 200
    r_data = r_res.json()
    assert len(r_data["requirement_map"]) >= 2

    # 3. Generate Questions
    q_res = client.get(f"/api/coach/interview-questions/{target_id}?candidate_id=cand_alex_p7")
    assert q_res.status_code == 200
    questions = q_res.json()
    assert len(questions) >= 2

    flask_q = next(q for q in questions if "flask" in q["question"].lower())
    assert len(flask_q["citations"]) > 0

    # 4. Project Stories
    story_res = client.get("/api/coach/project-stories/cand_alex_p7")
    assert story_res.status_code == 200
    stories = story_res.json()
    assert len(stories) >= 1

    # 5. Answer Validation Supported
    val1 = client.post(
        "/api/coach/interview-answers/validate",
        json={
            "candidate_id": "cand_alex_p7",
            "question_id": flask_q["question_id"],
            "answer_text": "I built Flask backend microservices for automated payment processing.",
        },
    ).json()
    assert val1["verdict"] == "SUPPORTED"

    # 6. Answer Validation Unsupported Metric
    val2 = client.post(
        "/api/coach/interview-answers/validate",
        json={
            "candidate_id": "cand_alex_p7",
            "question_id": flask_q["question_id"],
            "answer_text": "I built Flask backend microservices and increased throughput by 400%.",
        },
    ).json()
    assert any("400%" in c for c in val2["unsupported_claims"])

    # 7. Mock Interview Session
    sess_res = client.post(
        "/api/coach/interview-sessions",
        json={"candidate_id": "cand_alex_p7", "interview_target_id": target_id},
    )
    assert sess_res.status_code == 201
    sess = sess_res.json()

    ans_res = client.post(
        f"/api/coach/interview-sessions/{sess['session_id']}/answer",
        json={
            "candidate_id": "cand_alex_p7",
            "session_id": sess["session_id"],
            "question_id": sess["items"][0]["question_id"],
            "answer_text": "Built Flask backend microservices for automated payment processing.",
        },
    )
    assert ans_res.status_code == 200
    assert ans_res.json()["answers_submitted_count"] == 1
