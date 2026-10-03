import pytest
import numpy as np
from app.services.keyword_matcher import KeywordMatcher
from app.services.semantic_matcher import LocalSentenceTransformerEmbeddingModel, SemanticMatcher
from app.services.hybrid_evaluator import (
    RequirementEvaluator,
    ScoringEngine,
    RankingService,
    WEIGHT_PRIORITY_REQUIRED,
    WEIGHT_PRIORITY_PREFERRED
)
from app.schemas.candidate import (
    CandidateProfile,
    CandidateSkill,
    CandidateExperience,
    CandidateEducation,
    CandidateCertification
)
from app.schemas.domain import (
    JobDescription,
    JDRequirement,
    RequirementCategory,
    RequirementPriority,
    MatchVerdict,
    Evidence
)

@pytest.fixture(scope="module")
def embedding_model():
    return LocalSentenceTransformerEmbeddingModel("all-MiniLM-L6-v2")

@pytest.fixture(scope="module")
def keyword_matcher():
    return KeywordMatcher()

@pytest.fixture(scope="module")
def semantic_matcher(embedding_model):
    return SemanticMatcher(embedding_model)

@pytest.fixture(scope="module")
def requirement_evaluator(keyword_matcher, semantic_matcher):
    return RequirementEvaluator(keyword_matcher, semantic_matcher)

@pytest.fixture(scope="module")
def scoring_engine(requirement_evaluator):
    return ScoringEngine(requirement_evaluator)

@pytest.fixture(scope="module")
def ranking_service(scoring_engine):
    return RankingService(scoring_engine)

# TEST 1 — Exact lexical + semantic match
def test_1_exact_lexical_and_semantic_match(requirement_evaluator):
    req = JDRequirement(
        id="req_py",
        requirement_text="Python",
        category=RequirementCategory.SKILL,
        extracted_keywords=["Python"]
    )
    profile = CandidateProfile(
        candidate_id="c1",
        skill_details=[CandidateSkill(name="Python", raw_name="Python")]
    )
    res = requirement_evaluator.evaluate_requirement(req, profile)
    assert res.hybrid_score > 0.90
    assert res.verdict == MatchVerdict.MATCHED
    assert res.strongest_lexical is not None
    assert res.strongest_lexical.match_type == "EXACT"

# TEST 2 — Semantic-only conceptual match (permitted for conceptual/domain requirements)
def test_2_semantic_only_conceptual_match(requirement_evaluator):
    req = JDRequirement(
        id="req_orch",
        requirement_text="container orchestration",
        category=RequirementCategory.SKILL,
        extracted_keywords=["container orchestration"]
    )
    profile = CandidateProfile(
        candidate_id="c1",
        skill_details=[CandidateSkill(name="Kubernetes", raw_name="Kubernetes")]
    )
    res = requirement_evaluator.evaluate_requirement(req, profile)
    assert res.strongest_lexical is None
    assert res.strongest_semantic is not None
    assert res.hybrid_score > 0.30
    assert res.verdict in [MatchVerdict.PARTIAL, MatchVerdict.MATCHED]

# TEST 3 — Semantic-only concrete skill protection
def test_3_semantic_only_concrete_skill_protection(requirement_evaluator):
    req = JDRequirement(
        id="req_py",
        requirement_text="Python programming",
        category=RequirementCategory.SKILL,
        extracted_keywords=["Python"]
    )
    profile = CandidateProfile(
        candidate_id="c1",
        experience=[CandidateExperience(description="data analysis and statistical modeling")]
    )
    res = requirement_evaluator.evaluate_requirement(req, profile)
    # Topical similarity alone must NOT award positive credit for unmentioned Python
    assert res.strongest_lexical is None
    assert res.hybrid_score == 0.0
    assert res.verdict == MatchVerdict.MISSING

# TEST 4 — Semantic-only certification protection
def test_4_semantic_only_certification_protection(requirement_evaluator):
    req = JDRequirement(
        id="req_cert",
        requirement_text="AWS Certified Solutions Architect",
        category=RequirementCategory.CERTIFICATION,
        extracted_keywords=["AWS Certified Solutions Architect"]
    )
    profile = CandidateProfile(
        candidate_id="c1",
        experience=[CandidateExperience(description="cloud computing experience on enterprise systems")]
    )
    res = requirement_evaluator.evaluate_requirement(req, profile)
    # Semantic proximity to cloud experience must NOT substitute for an actual certification
    assert res.hybrid_score == 0.0
    assert res.verdict == MatchVerdict.MISSING

# TEST 5 — Semantic-only degree protection
def test_5_semantic_only_degree_protection(requirement_evaluator):
    req = JDRequirement(
        id="req_deg",
        requirement_text="Bachelor's degree in Computer Science",
        category=RequirementCategory.EDUCATION,
        extracted_keywords=["Computer Science"]
    )
    profile = CandidateProfile(
        candidate_id="c1",
        education=[CandidateEducation(degree="Bachelor of Arts", field_of_study="History")]
    )
    res = requirement_evaluator.evaluate_requirement(req, profile)
    # Semantic proximity of degree prose must NOT satisfy Computer Science degree requirement
    assert res.hybrid_score == 0.0
    assert res.verdict == MatchVerdict.MISSING

# TEST 6 — Aspirational semantic protection
def test_6_aspirational_semantic_protection(requirement_evaluator):
    req = JDRequirement(
        id="req_py_exp",
        requirement_text="Python programming experience",
        category=RequirementCategory.EXPERIENCE,
        extracted_keywords=["Python"]
    )
    profile = CandidateProfile(
        candidate_id="c1",
        experience=[CandidateExperience(description="Interested in learning Python in my next role")]
    )
    res = requirement_evaluator.evaluate_requirement(req, profile)
    assert res.hybrid_score == 0.0
    assert res.verdict == MatchVerdict.MISSING
    assert res.is_aspirational_or_negated is True

# TEST 7 — Negative semantic protection
def test_7_negative_semantic_protection(requirement_evaluator):
    req = JDRequirement(
        id="req_py",
        requirement_text="Python",
        category=RequirementCategory.SKILL,
        extracted_keywords=["Python"]
    )
    profile = CandidateProfile(
        candidate_id="c1",
        experience=[CandidateExperience(description="Currently developing in Java, no experience with Python")]
    )
    res = requirement_evaluator.evaluate_requirement(req, profile)
    assert res.hybrid_score == 0.0
    assert res.verdict == MatchVerdict.MISSING
    assert res.is_aspirational_or_negated is True

# TEST 8 — Aspirational evidence does not distort valid skill evidence
def test_8_aspirational_does_not_distort_valid_skill(requirement_evaluator):
    req = JDRequirement(
        id="req_py",
        requirement_text="Python",
        category=RequirementCategory.SKILL,
        extracted_keywords=["Python"]
    )
    profile = CandidateProfile(
        candidate_id="c1",
        skill_details=[CandidateSkill(name="Python", raw_name="Python")],
        summary="Experienced engineer. Interested in learning Python 3.12 async features."
    )
    res = requirement_evaluator.evaluate_requirement(req, profile)
    # The valid Python skill must be evaluated and awarded, not overridden by the aspirational note
    assert res.hybrid_score >= 0.70
    assert res.verdict == MatchVerdict.MATCHED
    assert res.strongest_lexical is not None
    assert res.strongest_lexical.evidence_text == "Python"

# TEST 9 — Total tenure != technology-specific tenure
def test_9_total_tenure_vs_domain_specific_tenure(requirement_evaluator):
    req = JDRequirement(
        id="req_py_3yr",
        requirement_text="3+ years of Python experience",
        category=RequirementCategory.EXPERIENCE,
        experience_domain="Python",
        min_years=3.0,
        extracted_keywords=["Python"]
    )
    # Candidate with 5 years (60 months) total employment as a Java developer,
    # with Python listed only in skills (no Python-specific employment history)
    profile_unverified = CandidateProfile(
        candidate_id="cand_java_5yr",
        skill_details=[CandidateSkill(name="Python", raw_name="Python")],
        experience=[CandidateExperience(
            role="Java Backend Engineer",
            description="Built microservices using Java and Spring Boot",
            duration_months=60.0,
            technologies=["Java", "Spring Boot"]
        )]
    )
    res = requirement_evaluator.evaluate_requirement(req, profile_unverified)
    # Total 5 years tenure must NOT be credited as 3+ years of Python!
    assert res.candidate_years is None
    assert res.experience_satisfied is False
    assert res.verdict == MatchVerdict.PARTIAL
    assert res.hybrid_score <= 0.60

# TEST 10 — Insufficient technology-specific years
def test_10_insufficient_technology_specific_years(requirement_evaluator):
    req = JDRequirement(
        id="req_py_3yr",
        requirement_text="3+ years of Python experience",
        category=RequirementCategory.EXPERIENCE,
        experience_domain="Python",
        min_years=3.0,
        extracted_keywords=["Python"]
    )
    # Candidate with 2 years (24 months) verified Python experience
    profile_partial = CandidateProfile(
        candidate_id="cand_py_2yr",
        experience=[CandidateExperience(
            role="Junior Python Developer",
            description="Developed backend APIs in Python and Django",
            duration_months=24.0,
            technologies=["Python", "Django"]
        )]
    )
    res = requirement_evaluator.evaluate_requirement(req, profile_partial)
    assert res.candidate_years == 2.0
    assert res.experience_satisfied is False
    assert res.verdict == MatchVerdict.PARTIAL
    # Score is prorated by 2/3 ratio
    assert res.hybrid_score < 0.70

# TEST 11 — Sufficient technology-specific years
def test_11_sufficient_technology_specific_years(requirement_evaluator):
    req = JDRequirement(
        id="req_py_3yr",
        requirement_text="3+ years of Python experience",
        category=RequirementCategory.EXPERIENCE,
        experience_domain="Python",
        min_years=3.0,
        extracted_keywords=["Python"]
    )
    # Candidate with 4 years (48 months) verified Python experience
    profile_full = CandidateProfile(
        candidate_id="cand_py_4yr",
        experience=[CandidateExperience(
            role="Senior Python Engineer",
            description="Lead Python engineer developing scalable backend systems",
            duration_months=48.0,
            technologies=["Python"]
        )]
    )
    res = requirement_evaluator.evaluate_requirement(req, profile_full)
    assert res.candidate_years == 4.0
    assert res.experience_satisfied is True
    assert res.verdict == MatchVerdict.MATCHED
    assert res.hybrid_score >= 0.70

# TEST 12 — Keyword stuffing protection
def test_12_keyword_stuffing_protection(requirement_evaluator):
    req = JDRequirement(
        id="req_py",
        requirement_text="Production Python backend engineering",
        category=RequirementCategory.EXPERIENCE,
        extracted_keywords=["Python"]
    )
    cand_stuffed = CandidateProfile(
        candidate_id="cand_stuffed",
        skill_details=[
            CandidateSkill(name="Python", raw_name="Python"),
            CandidateSkill(name="Python", raw_name="Python"),
            CandidateSkill(name="Python", raw_name="Python")
        ]
    )
    cand_rich = CandidateProfile(
        candidate_id="cand_rich",
        experience=[CandidateExperience(
            role="Senior Backend Engineer",
            description="Built production backend microservices using Python and FastAPI with high throughput."
        )]
    )
    res_stuffed = requirement_evaluator.evaluate_requirement(req, cand_stuffed)
    res_rich = requirement_evaluator.evaluate_requirement(req, cand_rich)
    assert res_rich.hybrid_score >= res_stuffed.hybrid_score

# TEST 13 — Required vs preferred prioritization
def test_13_required_vs_preferred_ranking(scoring_engine, ranking_service):
    jd = JobDescription(
        jd_id="jd_tech",
        raw_text="Job Description",
        requirements=[
            JDRequirement(id="r1", requirement_text="Python", category=RequirementCategory.SKILL, priority=RequirementPriority.REQUIRED, extracted_keywords=["Python"]),
            JDRequirement(id="r2", requirement_text="SQL", category=RequirementCategory.SKILL, priority=RequirementPriority.REQUIRED, extracted_keywords=["SQL"]),
            JDRequirement(id="r3", requirement_text="Docker", category=RequirementCategory.SKILL, priority=RequirementPriority.PREFERRED, extracted_keywords=["Docker"])
        ]
    )
    # Candidate A: satisfies both REQUIRED (Python, SQL), misses PREFERRED (Docker)
    cand_a = CandidateProfile(
        candidate_id="cand_a",
        skill_details=[CandidateSkill(name="Python", raw_name="Python"), CandidateSkill(name="SQL", raw_name="SQL")]
    )
    # Candidate B: satisfies PREFERRED (Docker) + 1 REQUIRED (Python), misses 1 REQUIRED (SQL)
    cand_b = CandidateProfile(
        candidate_id="cand_b",
        skill_details=[CandidateSkill(name="Python", raw_name="Python"), CandidateSkill(name="Docker", raw_name="Docker")]
    )
    ranks = ranking_service.rank_candidates(jd, [cand_b, cand_a])
    # Candidate A must rank 1st because required requirements have 3x weight
    assert ranks[0].candidate_id == "cand_a"
    assert ranks[1].candidate_id == "cand_b"
    assert ranks[0].score.overall_score > ranks[1].score.overall_score
    # Candidate B is NOT discarded, receives valid score and rank
    assert ranks[1].score.overall_score > 0.0

# TEST 14 — Score traceability
def test_14_score_traceability(scoring_engine):
    jd = JobDescription(
        jd_id="jd_trace",
        raw_text="Job Description",
        requirements=[
            JDRequirement(id="r1", requirement_text="Python", priority=RequirementPriority.REQUIRED, extracted_keywords=["Python"]),
            JDRequirement(id="r2", requirement_text="Docker", priority=RequirementPriority.PREFERRED, extracted_keywords=["Docker"])
        ]
    )
    profile = CandidateProfile(
        candidate_id="c_trace",
        skill_details=[CandidateSkill(name="Python", raw_name="Python")]
    )
    score, breakdown, evals, _, _ = scoring_engine.score_candidate(jd, profile)

    # Reconstruct score mathematically from formula:
    # (w_req * s_req + w_pref * s_pref) / (w_req + w_pref) * 100
    w_req = WEIGHT_PRIORITY_REQUIRED
    w_pref = WEIGHT_PRIORITY_PREFERRED
    s_req = evals[0].hybrid_score
    s_pref = evals[1].hybrid_score

    expected_score = ((w_req * s_req + w_pref * s_pref) / (w_req + w_pref)) * 100.0
    assert np.isclose(score.overall_score, round(expected_score, 2))
    assert np.isclose(breakdown.overall_score, round(expected_score, 2))
    assert breakdown.total_requirements == 2

# TEST 15 — Score bounds and empty candidate
def test_15_score_bounds_and_empty_candidate(scoring_engine):
    jd = JobDescription(
        jd_id="jd_bounds",
        raw_text="Test JD",
        requirements=[
            JDRequirement(id="r1", requirement_text="Python", priority=RequirementPriority.REQUIRED, extracted_keywords=["Python"]),
            JDRequirement(id="r2", requirement_text="Go", priority=RequirementPriority.PREFERRED, extracted_keywords=["Go"])
        ]
    )
    cand_empty = CandidateProfile(candidate_id="c_empty")
    cand_full = CandidateProfile(candidate_id="c_full", skill_details=[
        CandidateSkill(name="Python", raw_name="Python"),
        CandidateSkill(name="Go", raw_name="Go")
    ])

    score_empty, _, _, _, _ = scoring_engine.score_candidate(jd, cand_empty)
    score_full, _, _, _, _ = scoring_engine.score_candidate(jd, cand_full)

    assert 0.0 <= score_empty.overall_score <= 100.0
    assert 0.0 <= score_full.overall_score <= 100.0
    assert score_empty.overall_score == 0.0
    assert score_full.overall_score >= 85.0

# TEST 16 — Deterministic ranking and tie handling
def test_16_deterministic_ranking_and_tie_handling(ranking_service):
    jd = JobDescription(
        jd_id="jd_det",
        raw_text="Fullstack Developer",
        requirements=[
            JDRequirement(id="r1", requirement_text="Python", priority=RequirementPriority.REQUIRED, extracted_keywords=["Python"]),
            JDRequirement(id="r2", requirement_text="React", priority=RequirementPriority.REQUIRED, extracted_keywords=["React"]),
        ]
    )
    cand_alpha = CandidateProfile(candidate_id="cand_alpha", skill_details=[CandidateSkill(name="Python", raw_name="Python")])
    cand_beta = CandidateProfile(candidate_id="cand_beta", skill_details=[CandidateSkill(name="Python", raw_name="Python")])

    run_1 = ranking_service.rank_candidates(jd, [cand_beta, cand_alpha])
    run_2 = ranking_service.rank_candidates(jd, [cand_alpha, cand_beta])

    assert run_1[0].candidate_id == "cand_alpha"
    assert run_1[1].candidate_id == "cand_beta"
    assert run_2[0].candidate_id == "cand_alpha"
    assert run_2[1].candidate_id == "cand_beta"
    assert run_1[0].score.overall_score == run_2[0].score.overall_score
