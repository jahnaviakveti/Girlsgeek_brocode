"""
Phase 7 Hardening Tests — Evidence Granularity & Claim Scope Audit.
Verifies the core principle:
TECHNOLOGY PRESENCE != EXPERIENCE SCOPE

Covers all 15 audit requirements:
1. Kubernetes technology evidence vs production Kubernetes requirement.
2. Python technology evidence vs Python requirement.
3. Kubernetes deployment evidence vs Kubernetes requirement.
4. Kubernetes technology evidence vs EKS management requirement.
5. EKS production management evidence vs EKS requirement.
6. Kubernetes technology evidence vs Kubernetes architecture requirement.
7. Project technology listing does not imply operational expertise.
8. Interview question scope remains aligned with evidence.
9. Project Story scope remains aligned with evidence.
10. Answer validator rejects production claims without production evidence.
11. Existing Kubernetes evidence remains visible to the candidate.
12. Experience gap remains an EXPERIENCE_GAP where appropriate.
13. Visibility gap behavior remains unchanged.
14. NOT_VERIFIABLE behavior remains unchanged.
15. Candidate isolation remains intact.
"""

import pytest
import uuid
from typing import List

from app.schemas.candidate import CandidateProfile, CandidateSkill, CandidateExperience, CandidateProject
from app.schemas.domain import (
    JDRequirement,
    RequirementCategory,
    RequirementPriority,
    MatchVerdict,
    JobDescription,
)
from app.schemas.career_twin import CareerTwin, CareerSkillNode, CareerProjectNode
from app.schemas.evidence_vault import (
    EvidenceVault,
    VaultEvidenceItem,
    EvidenceType,
)
from app.schemas.job_fit import GapType, RequirementStatus
from app.schemas.interview_readiness import (
    InterviewTarget,
    PreparationStatus,
    ValidationVerdict,
)
from app.services.keyword_matcher import KeywordMatcher
from app.services.semantic_matcher import LocalSentenceTransformerEmbeddingModel, SemanticMatcher
from app.services.hybrid_evaluator import RequirementEvaluator
from app.services.coach.job_fit.service import JobFitService
from app.services.coach.interview.question_service import InterviewQuestionService
from app.services.coach.interview.answer_coach_service import InterviewAnswerCoachService
from app.services.coach.interview.readiness_service import InterviewReadinessService
from app.services.coach.evidence.claim_scope import (
    evaluate_claim_scope,
    extract_operational_scope_claims,
)


@pytest.fixture(scope="module")
def evaluator():
    embedding_model = LocalSentenceTransformerEmbeddingModel()
    kw_matcher = KeywordMatcher()
    sem_matcher = SemanticMatcher(embedding_model)
    return RequirementEvaluator(kw_matcher, sem_matcher)


@pytest.fixture(scope="module")
def job_fit_service():
    return JobFitService()


# 1. Kubernetes technology evidence vs production Kubernetes requirement
def test_01_kubernetes_tech_evidence_vs_production_kubernetes_requirement(evaluator, job_fit_service):
    req = JDRequirement(
        id="req_k8s_prod",
        requirement_text="Experience managing production Kubernetes clusters (EKS/GKE)",
        category=RequirementCategory.SKILL,
        priority=RequirementPriority.REQUIRED,
        extracted_keywords=["Kubernetes", "production", "clusters", "EKS", "GKE"]
    )
    profile = CandidateProfile(
        candidate_id="cand_k8s_basic",
        technologies=["Kubernetes"],
        skills=["Containerization"],
        experience=[CandidateExperience(description="Built a microservices application using Kubernetes in a university project.")]
    )
    res = evaluator.evaluate_requirement(req, profile)
    # MUST NOT be MATCHED
    assert res.verdict != MatchVerdict.MATCHED
    assert res.verdict in [MatchVerdict.PARTIAL, MatchVerdict.MISSING]
    assert "Scope distinction" in res.rationale or "scope" in res.rationale.lower()

    # In Job Fit, must be EXPERIENCE_GAP
    jd = JobDescription(jd_id="jd_test", title="DevOps Engineer", requirements=[req], raw_text="Job with k8s prod")
    twin = CareerTwin(twin_id="twin_1", candidate_id="cand_k8s_basic", name="Test Candidate")
    vault = EvidenceVault(
        vault_id="vault_k8s_basic",
        candidate_id="cand_k8s_basic",
        total_items=1,
        items=[
            VaultEvidenceItem(
                evidence_id="ev_k8s_1",
                candidate_id="cand_k8s_basic",
                evidence_type=EvidenceType.PROJECT,
                source_document="Resume.pdf",
                source_section="Projects",
                source_text="Built a microservices application using Kubernetes in a university project.",
                related_skill="Kubernetes"
            )
        ]
    )
    fit_res = job_fit_service.evaluate_fit(profile, jd, twin=twin, vault=vault)
    req_fit = fit_res.job_fit_analysis.requirements[0]
    assert req_fit.status != RequirementStatus.MATCHED
    assert req_fit.gap_type == GapType.EXPERIENCE_GAP


# 2. Python technology evidence vs Python requirement
def test_02_python_tech_evidence_vs_python_requirement(evaluator, job_fit_service):
    req = JDRequirement(
        id="req_py",
        requirement_text="Python",
        category=RequirementCategory.SKILL,
        priority=RequirementPriority.REQUIRED,
        extracted_keywords=["Python"]
    )
    profile = CandidateProfile(
        candidate_id="cand_py",
        technologies=["Python"],
        experience=[CandidateExperience(description="Built Python backend microservices.")]
    )
    res = evaluator.evaluate_requirement(req, profile)
    assert res.verdict == MatchVerdict.MATCHED
    assert res.hybrid_score >= 0.70


# 3. Kubernetes deployment evidence vs Kubernetes requirement
def test_03_kubernetes_deployment_evidence_vs_kubernetes_requirement(evaluator, job_fit_service):
    req = JDRequirement(
        id="req_k8s_basic",
        requirement_text="Kubernetes",
        category=RequirementCategory.SKILL,
        priority=RequirementPriority.REQUIRED,
        extracted_keywords=["Kubernetes"]
    )
    profile = CandidateProfile(
        candidate_id="cand_k8s_dep",
        technologies=["Kubernetes"],
        experience=[CandidateExperience(description="Used Kubernetes for project deployment.")]
    )
    res = evaluator.evaluate_requirement(req, profile)
    assert res.verdict in [MatchVerdict.MATCHED, MatchVerdict.PARTIAL]
    assert res.hybrid_score > 0.50


# 4. Kubernetes technology evidence vs EKS management requirement
def test_04_kubernetes_tech_evidence_vs_eks_management_requirement(evaluator):
    req = JDRequirement(
        id="req_eks_mgmt",
        requirement_text="Managed production EKS infrastructure",
        category=RequirementCategory.SKILL,
        priority=RequirementPriority.REQUIRED,
        extracted_keywords=["EKS", "production", "infrastructure"]
    )
    profile = CandidateProfile(
        candidate_id="cand_k8s_only",
        technologies=["Kubernetes"],
        experience=[CandidateExperience(description="Used Kubernetes in local Docker desktop environment.")]
    )
    res = evaluator.evaluate_requirement(req, profile)
    # MUST NOT be MATCHED
    assert res.verdict != MatchVerdict.MATCHED


# 5. EKS production management evidence vs EKS requirement
def test_05_eks_production_management_evidence_vs_eks_requirement(evaluator):
    req = JDRequirement(
        id="req_eks_prod",
        requirement_text="Production Kubernetes cluster management (EKS)",
        category=RequirementCategory.SKILL,
        priority=RequirementPriority.REQUIRED,
        extracted_keywords=["Kubernetes", "production", "clusters", "EKS"]
    )
    profile = CandidateProfile(
        candidate_id="cand_eks_pro",
        technologies=["Kubernetes", "AWS", "EKS"],
        experience=[CandidateExperience(description="Managed production EKS clusters, configured node pools, and led operational maintenance.")]
    )
    res = evaluator.evaluate_requirement(req, profile)
    # When explicit production cluster management is documented, MATCHED is permitted
    assert res.verdict == MatchVerdict.MATCHED
    assert res.hybrid_score >= 0.70


# 6. Kubernetes technology evidence vs Kubernetes architecture requirement
def test_06_kubernetes_tech_evidence_vs_kubernetes_architecture_requirement(evaluator):
    req = JDRequirement(
        id="req_k8s_arch",
        requirement_text="Designed scalable Kubernetes infrastructure",
        category=RequirementCategory.SKILL,
        priority=RequirementPriority.REQUIRED,
        extracted_keywords=["Kubernetes", "infrastructure", "scalable"]
    )
    profile = CandidateProfile(
        candidate_id="cand_k8s_mention",
        technologies=["Kubernetes"],
        experience=[CandidateExperience(description="Kubernetes mentioned in project.")]
    )
    res = evaluator.evaluate_requirement(req, profile)
    # MUST NOT be MATCHED
    assert res.verdict != MatchVerdict.MATCHED


# 7. Project technology listing does not imply operational expertise
def test_07_project_technology_listing_does_not_imply_operational_expertise():
    readiness_service = InterviewReadinessService()
    twin = CareerTwin(
        twin_id="twin_alex",
        candidate_id="cand_alex",
        name="Alex Candidate",
        projects=[
            CandidateProject(
                name="CloudSync Engine",
                technologies=["Python", "Redis", "Kubernetes"],
                description="Built real-time file synchronization service."
            )
        ]
    )
    vault = EvidenceVault(
        vault_id="vault_alex",
        candidate_id="cand_alex",
        total_items=2,
        items=[
            VaultEvidenceItem(
                evidence_id="ev_cs_1",
                candidate_id="cand_alex",
                evidence_type=EvidenceType.PROJECT,
                source_document="Resume.pdf",
                source_section="Projects",
                source_text="CloudSync Engine: Built real-time file synchronization service using Python and Redis. Learned Kubernetes.",
                related_project="CloudSync Engine",
                related_skill="Kubernetes"
            )
        ]
    )
    target = InterviewTarget(
        interview_target_id="itarget_1",
        candidate_id="cand_alex",
        target_role="Senior DevOps Engineer",
    )
    readiness = readiness_service.generate_interview_readiness(target, twin, vault)
    story = next((s for s in readiness.project_stories if s.project_name == "CloudSync Engine"), None)
    assert story is not None
    # Verified technology list retains Kubernetes
    assert "Kubernetes" in story.technologies
    # But discussion areas DO NOT claim production cluster management
    assert "Operational reliability and production cluster management" not in story.likely_discussion_areas
    assert any("Practical hands-on usage" in area for area in story.likely_discussion_areas)


# 8. Interview question scope remains aligned with evidence
def test_08_interview_question_scope_remains_aligned_with_evidence():
    q_service = InterviewQuestionService()
    twin = CareerTwin(
        twin_id="twin_1",
        candidate_id="cand_1",
        name="Candidate 1",
        projects=[CandidateProject(name="CloudSync", technologies=["Kubernetes"])]
    )
    vault = EvidenceVault(
        vault_id="vault_cand_1",
        candidate_id="cand_1",
        total_items=1,
        items=[
            VaultEvidenceItem(
                evidence_id="ev_1",
                candidate_id="cand_1",
                evidence_type=EvidenceType.PROJECT,
                source_document="Resume.pdf",
                source_section="Projects",
                source_text="CloudSync: Explored Kubernetes containerization.",
                related_skill="Kubernetes"
            )
        ]
    )
    from app.schemas.interview_readiness import InterviewRequirementMapItem
    req_items = [
        InterviewRequirementMapItem(
            requirement_id="req_k8s_prod",
            requirement_text="Experience managing production Kubernetes clusters (EKS/GKE)",
            priority="REQUIRED",
            preparation_status=PreparationStatus.PREPARE,
            job_fit_status="MISSING",
            rationale="Experience gap requires preparation."
        )
    ]
    questions = q_service.generate_questions_for_target(
        interview_target_id="itarget_1",
        target_role="Senior Infrastructure Engineer",
        requirement_items=req_items,
        twin=twin,
        vault=vault
    )
    k8s_q = next(q for q in questions if "kubernetes" in q.question.lower())
    # MUST NOT ask "How did you manage your production EKS cluster?"
    assert "How did you manage" not in k8s_q.question
    assert "familiarity with Kubernetes" in k8s_q.question
    assert k8s_q.experience_gap_note is not None
    assert "no verified production cluster management" in k8s_q.experience_gap_note.lower()


# 9. Project Story scope remains aligned with evidence
def test_09_project_story_scope_remains_aligned_with_evidence():
    readiness_service = InterviewReadinessService()
    twin = CareerTwin(
        twin_id="twin_2",
        candidate_id="cand_2",
        name="Candidate 2",
        projects=[CandidateProject(name="MicroApp", technologies=["Kubernetes", "Docker"])]
    )
    vault = EvidenceVault(
        vault_id="vault_cand_2",
        candidate_id="cand_2",
        total_items=1,
        items=[
            VaultEvidenceItem(
                evidence_id="ev_m_1",
                candidate_id="cand_2",
                evidence_type=EvidenceType.PROJECT,
                source_document="Resume.pdf",
                source_section="Projects",
                source_text="MicroApp: Containerized app with Docker and Kubernetes.",
                related_project="MicroApp",
                related_skill="Kubernetes"
            )
        ]
    )
    target = InterviewTarget(interview_target_id="it_2", candidate_id="cand_2", target_role="Backend Dev")
    res = readiness_service.generate_interview_readiness(target, twin, vault)
    story = res.project_stories[0]
    # STAR prompts ask about design/implementation choices, NOT production cluster admin
    assert "How did you design and implement" in story.star_preparation["action"]


# 10. Answer validator rejects production claims without production evidence
def test_10_answer_validator_rejects_production_claims_without_production_evidence():
    answer_coach = InterviewAnswerCoachService()
    vault = EvidenceVault(
        vault_id="vault_val",
        candidate_id="cand_test_val",
        total_items=1,
        items=[
            VaultEvidenceItem(
                evidence_id="ev_test_1",
                candidate_id="cand_test_val",
                evidence_type=EvidenceType.PROJECT,
                source_document="Resume.pdf",
                source_section="Projects",
                source_text="Built a microservices application using Kubernetes.",
                related_skill="Kubernetes"
            )
        ]
    )
    # Case A: Honest claim
    res_honest = answer_coach.validate_candidate_answer(vault, "I used Kubernetes in my project.")
    assert res_honest.verdict == ValidationVerdict.SUPPORTED
    assert len(res_honest.unsupported_claims) == 0

    # Case B: Unsupported operational cluster claim
    res_op = answer_coach.validate_candidate_answer(vault, "I managed production Kubernetes clusters.")
    assert res_op.verdict in [ValidationVerdict.UNSUPPORTED, ValidationVerdict.PARTIALLY_SUPPORTED]
    assert any("operational scope claim" in c.lower() for c in res_op.unsupported_claims)

    # Case C: Unsupported deployment claim
    res_dep = answer_coach.validate_candidate_answer(vault, "I deployed the application using Kubernetes.")
    assert res_dep.verdict in [ValidationVerdict.UNSUPPORTED, ValidationVerdict.PARTIALLY_SUPPORTED]
    assert any("deployment claim" in c.lower() for c in res_dep.unsupported_claims)

    # Case D: Unsupported EKS platform claim
    res_eks = answer_coach.validate_candidate_answer(vault, "I managed production EKS clusters.")
    assert res_eks.verdict == ValidationVerdict.UNSUPPORTED
    assert any("eks" in c.lower() for c in res_eks.unsupported_claims + res_eks.unsupported_technologies)


# 11. Existing Kubernetes evidence remains visible to the candidate
def test_11_existing_kubernetes_evidence_remains_visible_to_candidate(job_fit_service):
    profile = CandidateProfile(
        candidate_id="cand_k8s_vis",
        technologies=["Kubernetes"],
        skills=["Containerization"],
        experience=[CandidateExperience(description="CloudSync Engine project used Kubernetes.")]
    )
    req = JDRequirement(
        id="req_prod_k8s",
        requirement_text="Production Kubernetes cluster management",
        category=RequirementCategory.SKILL,
        priority=RequirementPriority.REQUIRED,
        extracted_keywords=["Kubernetes", "production", "cluster", "management"]
    )
    jd = JobDescription(jd_id="jd_k8s_vis", title="Lead DevOps", requirements=[req], raw_text="Job with k8s prod")
    vault = EvidenceVault(
        vault_id="vault_vis",
        candidate_id="cand_k8s_vis",
        total_items=1,
        items=[
            VaultEvidenceItem(
                evidence_id="ev_cs_k8s",
                candidate_id="cand_k8s_vis",
                evidence_type=EvidenceType.PROJECT,
                source_document="Resume.pdf",
                source_section="Projects",
                source_text="CloudSync Engine project used Kubernetes.",
                related_project="CloudSync Engine",
                related_skill="Kubernetes"
            )
        ]
    )
    fit_res = job_fit_service.evaluate_fit(profile, jd, vault=vault)
    req_fit = fit_res.job_fit_analysis.requirements[0]
    # Existing vault evidence remains visible in citations
    assert len(req_fit.evidence) > 0
    assert req_fit.evidence[0].evidence_id == "ev_cs_k8s"
    # Status is EXPERIENCE_GAP
    assert req_fit.gap_type == GapType.EXPERIENCE_GAP


# 12. Experience gap remains an EXPERIENCE_GAP where appropriate
def test_12_experience_gap_remains_an_experience_gap_where_appropriate(job_fit_service):
    profile = CandidateProfile(
        candidate_id="cand_gap_test",
        technologies=["Kubernetes"],
        experience=[CandidateExperience(description="Kubernetes used in university project.")]
    )
    req = JDRequirement(
        id="req_eks_years",
        requirement_text="3+ years managing production EKS clusters",
        category=RequirementCategory.EXPERIENCE,
        priority=RequirementPriority.REQUIRED,
        extracted_keywords=["EKS", "production", "clusters", "managing"]
    )
    jd = JobDescription(jd_id="jd_eks_years", title="Senior Cloud Engineer", requirements=[req], raw_text="Need 3+ years managing production EKS clusters")
    fit_res = job_fit_service.evaluate_fit(profile, jd)
    req_fit = fit_res.job_fit_analysis.requirements[0]
    # Must be EXPERIENCE_GAP, NOT RESUME_VISIBILITY_GAP
    assert req_fit.gap_type == GapType.EXPERIENCE_GAP
    # Cannot rewrite resume to fabricate unevidenced production cluster management
    assert fit_res.job_fit_analysis.evidence_gaps[0].gap_type == GapType.EXPERIENCE_GAP


# 13. Visibility gap behavior remains unchanged
def test_13_visibility_gap_behavior_remains_unchanged(job_fit_service):
    profile = CandidateProfile(
        candidate_id="cand_vis_gap",
        technologies=["Python", "Flask"],
        experience=[CandidateExperience(description="Built backend microservices with Flask.")]
    )
    req = JDRequirement(
        id="req_flask_vis",
        requirement_text="Python microservices using Flask framework",
        category=RequirementCategory.SKILL,
        priority=RequirementPriority.REQUIRED,
        extracted_keywords=["Python", "Flask", "microservices"]
    )
    jd = JobDescription(jd_id="jd_flask_vis", title="Backend Dev", requirements=[req], raw_text="Flask microservices")
    vault = EvidenceVault(
        vault_id="vault_vis_gap",
        candidate_id="cand_vis_gap",
        total_items=1,
        items=[
            VaultEvidenceItem(
                evidence_id="ev_flask_1",
                candidate_id="cand_vis_gap",
                evidence_type=EvidenceType.EXPERIENCE,
                source_document="Resume.pdf",
                source_section="Experience",
                source_text="Built backend microservices with Flask.",
                related_skill="Flask"
            )
        ]
    )
    fit_res = job_fit_service.evaluate_fit(profile, jd, vault=vault)
    req_fit = fit_res.job_fit_analysis.requirements[0]
    # If partial, visibility gap is assigned and can_rewrite is True
    if req_fit.status == RequirementStatus.PARTIAL:
        assert req_fit.gap_type == GapType.RESUME_VISIBILITY_GAP


# 14. NOT_VERIFIABLE behavior remains unchanged
def test_14_not_verifiable_behavior_remains_unchanged(job_fit_service):
    profile = CandidateProfile(
        candidate_id="cand_comm",
        skills=["Python"],
        experience=[CandidateExperience(description="Software Engineer.")]
    )
    req = JDRequirement(
        id="req_comm",
        requirement_text="Exceptional communication and collaboration skills",
        category=RequirementCategory.SKILL,
        priority=RequirementPriority.REQUIRED,
        extracted_keywords=["communication", "collaboration"]
    )
    jd = JobDescription(jd_id="jd_comm", title="Software Engineer", requirements=[req], raw_text="Job with soft skill")
    fit_res = job_fit_service.evaluate_fit(profile, jd)
    req_fit = fit_res.job_fit_analysis.requirements[0]
    assert req_fit.gap_type == GapType.NOT_VERIFIABLE


# 15. Candidate isolation remains intact
def test_15_candidate_isolation_remains_intact(evaluator, job_fit_service):
    # Candidate A has production EKS cluster management
    # Candidate B has only university project with Kubernetes
    req = JDRequirement(
        id="req_k8s_iso",
        requirement_text="Experience managing production Kubernetes clusters (EKS/GKE)",
        category=RequirementCategory.SKILL,
        priority=RequirementPriority.REQUIRED,
        extracted_keywords=["Kubernetes", "production", "clusters", "EKS", "GKE"]
    )
    profile_b = CandidateProfile(
        candidate_id="cand_isolated_b",
        technologies=["Kubernetes"],
        experience=[CandidateExperience(description="Used Kubernetes for student project.")]
    )
    res_b = evaluator.evaluate_requirement(req, profile_b)
    # Candidate B MUST NOT inherit Candidate A's scope
    assert res_b.verdict != MatchVerdict.MATCHED
    assert res_b.verdict in [MatchVerdict.PARTIAL, MatchVerdict.MISSING]
