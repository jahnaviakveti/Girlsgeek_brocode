import pytest
import numpy as np
from app.services.keyword_matcher import KeywordMatcher
from app.services.semantic_matcher import LocalSentenceTransformerEmbeddingModel, SemanticMatcher
from app.services.hybrid_evaluator import (
    RequirementEvaluator,
    ScoringEngine,
    RankingService
)
from app.services.explanation_engine import (
    ExplanationEngine,
    EvidenceSelector,
    ExplanationTemplates
)
from app.schemas.explanation import EvidenceReference
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

@pytest.fixture(scope="module")
def explanation_engine():
    return ExplanationEngine()

@pytest.fixture(scope="module")
def standard_jd():
    return JobDescription(
        jd_id="jd_explain_test",
        raw_text="Fullstack Engineer JD",
        requirements=[
            JDRequirement(
                id="r1_py",
                requirement_text="Python programming experience",
                category=RequirementCategory.EXPERIENCE,
                priority=RequirementPriority.REQUIRED,
                extracted_keywords=["Python"]
            ),
            JDRequirement(
                id="r2_sql",
                requirement_text="SQL relational database experience",
                category=RequirementCategory.SKILL,
                priority=RequirementPriority.REQUIRED,
                extracted_keywords=["SQL"]
            ),
            JDRequirement(
                id="r3_docker",
                requirement_text="Docker containerization",
                category=RequirementCategory.SKILL,
                priority=RequirementPriority.PREFERRED,
                extracted_keywords=["Docker"]
            )
        ]
    )

# 1. Top-1 candidate explanation
def test_1_top_1_candidate_explanation(ranking_service, explanation_engine, standard_jd):
    cand1 = CandidateProfile(
        candidate_id="cand_1",
        name="Alex Smith",
        skill_details=[
            CandidateSkill(name="Python", raw_name="Python"),
            CandidateSkill(name="SQL", raw_name="SQL"),
            CandidateSkill(name="Docker", raw_name="Docker")
        ]
    )
    cand2 = CandidateProfile(
        candidate_id="cand_2",
        name="Bob Jones",
        skill_details=[CandidateSkill(name="Python", raw_name="Python")]
    )
    ranked = ranking_service.rank_candidates(standard_jd, [cand2, cand1])
    assert ranked[0].candidate_id == "cand_1"
    
    exp = explanation_engine.explain_candidate(ranked[0], standard_jd)
    assert exp.rank == 1
    assert exp.is_top_3 is True
    assert "Ranked #1" in exp.why_ranked_here
    assert len(exp.matched_requirements) >= 2
    assert len(exp.missing_required_requirements) == 0

# 2. Top-2 candidate explanation
def test_2_top_2_candidate_explanation(ranking_service, explanation_engine, standard_jd):
    cand1 = CandidateProfile(candidate_id="c1", skill_details=[CandidateSkill(name="Python", raw_name="Python"), CandidateSkill(name="SQL", raw_name="SQL"), CandidateSkill(name="Docker", raw_name="Docker")])
    cand2 = CandidateProfile(candidate_id="c2", skill_details=[CandidateSkill(name="Python", raw_name="Python"), CandidateSkill(name="SQL", raw_name="SQL")])
    cand3 = CandidateProfile(candidate_id="c3", skill_details=[CandidateSkill(name="Python", raw_name="Python")])
    
    ranked = ranking_service.rank_candidates(standard_jd, [cand3, cand1, cand2])
    assert ranked[1].candidate_id == "c2"
    
    exp = explanation_engine.explain_candidate(ranked[1], standard_jd)
    assert exp.rank == 2
    assert exp.is_top_3 is True
    assert "Ranked #2" in exp.why_ranked_here

# 3. Top-3 candidate explanation
def test_3_top_3_candidate_explanation(ranking_service, explanation_engine, standard_jd):
    cand1 = CandidateProfile(candidate_id="c1", skill_details=[CandidateSkill(name="Python", raw_name="Python"), CandidateSkill(name="SQL", raw_name="SQL"), CandidateSkill(name="Docker", raw_name="Docker")])
    cand2 = CandidateProfile(candidate_id="c2", skill_details=[CandidateSkill(name="Python", raw_name="Python"), CandidateSkill(name="SQL", raw_name="SQL")])
    cand3 = CandidateProfile(candidate_id="c3", skill_details=[CandidateSkill(name="Python", raw_name="Python")])
    
    ranked = ranking_service.rank_candidates(standard_jd, [cand1, cand2, cand3])
    exp = explanation_engine.explain_candidate(ranked[2], standard_jd)
    assert exp.rank == 3
    assert exp.is_top_3 is True
    assert "Ranked #3" in exp.why_ranked_here
    assert len(exp.missing_required_requirements) >= 1

# 4. Why-ranked-here explanation content
def test_4_why_ranked_here_explanation(ranking_service, explanation_engine, standard_jd):
    cand = CandidateProfile(candidate_id="c_top", skill_details=[CandidateSkill(name="Python", raw_name="Python"), CandidateSkill(name="SQL", raw_name="SQL")])
    ranked = ranking_service.rank_candidates(standard_jd, [cand])
    exp = explanation_engine.explain_candidate(ranked[0], standard_jd)
    assert "Ranked #1" in exp.why_ranked_here
    assert f"{ranked[0].score.overall_score:.1f}/100" in exp.why_ranked_here

# 5. Matched required requirement explanation
def test_5_matched_required_requirement(scoring_engine, explanation_engine, standard_jd):
    cand = CandidateProfile(candidate_id="c1", skill_details=[CandidateSkill(name="Python", raw_name="Python")])
    _, _, evals, _, _ = scoring_engine.score_candidate(standard_jd, cand)
    py_eval = next(e for e in evals if "Python" in e.requirement_text)
    
    refs = EvidenceSelector.select_requirement_evidence(py_eval)
    text = ExplanationTemplates.explain_requirement(py_eval, refs)
    assert "Matched" in text
    assert "Python" in text

# 6. Partial requirement explanation
def test_6_partial_requirement(requirement_evaluator, explanation_engine):
    req = JDRequirement(
        id="r_exp",
        requirement_text="3+ years of Python experience",
        category=RequirementCategory.EXPERIENCE,
        experience_domain="Python",
        min_years=3.0,
        extracted_keywords=["Python"]
    )
    cand = CandidateProfile(
        candidate_id="c_partial",
        experience=[CandidateExperience(
            role="Python Developer",
            description="Built web applications with Python",
            duration_months=24.0,
            technologies=["Python"]
        )]
    )
    eval_res = requirement_evaluator.evaluate_requirement(req, cand)
    assert eval_res.verdict == MatchVerdict.PARTIAL
    
    refs = EvidenceSelector.select_requirement_evidence(eval_res)
    text = ExplanationTemplates.explain_requirement(eval_res, refs)
    assert "Partial match" in text
    assert "2.0 verified years" in text
    assert "3.0+ years" in text

# 7. Missing required requirement explanation
def test_7_missing_required_requirement(requirement_evaluator, explanation_engine):
    req = JDRequirement(
        id="r_missing",
        requirement_text="Rust programming experience",
        category=RequirementCategory.SKILL,
        priority=RequirementPriority.REQUIRED,
        extracted_keywords=["Rust"]
    )
    cand = CandidateProfile(candidate_id="c1", skill_details=[CandidateSkill(name="Python", raw_name="Python")])
    eval_res = requirement_evaluator.evaluate_requirement(req, cand)
    assert eval_res.verdict == MatchVerdict.MISSING
    
    refs = EvidenceSelector.select_requirement_evidence(eval_res)
    text = ExplanationTemplates.explain_requirement(eval_res, refs)
    assert "Missing" in text
    assert "Supporting evidence was not found" in text

# 8. Missing preferred requirement explanation
def test_8_missing_preferred_requirement(scoring_engine, explanation_engine, standard_jd):
    cand = CandidateProfile(candidate_id="c1", skill_details=[CandidateSkill(name="Python", raw_name="Python")])
    score, breakdown, evals, matched, missing = scoring_engine.score_candidate(standard_jd, cand)
    from app.schemas.scoring import CandidateRankingResult
    ranking_res = CandidateRankingResult(
        rank=1,
        candidate_id="c1",
        score=score,
        score_breakdown=breakdown,
        matched_skills=matched,
        missing_skills=missing,
        evaluations=evals
    )
    exp = explanation_engine.explain_candidate(ranking_res, standard_jd)
    # Missing preferred requirement should be Docker
    missing_pref_ids = [r.requirement_id for r in exp.missing_preferred_requirements]
    assert "r3_docker" in missing_pref_ids

# 9. Supporting evidence included
def test_9_supporting_evidence_included(scoring_engine, explanation_engine, standard_jd):
    cand = CandidateProfile(
        candidate_id="c1",
        skill_details=[CandidateSkill(name="Python", raw_name="Python")]
    )
    score, breakdown, evals, matched, missing = scoring_engine.score_candidate(standard_jd, cand)
    from app.schemas.scoring import CandidateRankingResult
    ranking_res = CandidateRankingResult(
        rank=1,
        candidate_id="c1",
        score=score,
        score_breakdown=breakdown,
        matched_skills=matched,
        missing_skills=missing,
        evaluations=evals
    )
    exp = explanation_engine.explain_candidate(ranking_res, standard_jd)
    matched_py = next(r for r in exp.matched_requirements if "Python" in r.requirement_text)
    assert len(matched_py.supporting_evidence) >= 1
    assert "Python" in matched_py.supporting_evidence[0].evidence_text

# 10. Page provenance preserved
def test_10_page_provenance_preserved(requirement_evaluator, explanation_engine):
    ev = Evidence(source_text="Python 3.10 developer", source_section="Skills", confidence_score=1.0, page_number=2, evidence_type="skill")
    cand = CandidateProfile(
        candidate_id="c1",
        skill_details=[CandidateSkill(name="Python", raw_name="Python", evidence=ev)]
    )
    req = JDRequirement(id="r1", requirement_text="Python", category=RequirementCategory.SKILL, extracted_keywords=["Python"])
    eval_res = requirement_evaluator.evaluate_requirement(req, cand)
    refs = EvidenceSelector.select_requirement_evidence(eval_res)
    assert len(refs) >= 1
    assert refs[0].page_number == 2

# 11. Section provenance preserved
def test_11_section_provenance_preserved(requirement_evaluator, explanation_engine):
    ev = Evidence(source_text="Managed PostgreSQL clusters", source_section="Experience", confidence_score=0.9, page_number=3, evidence_type="experience")
    cand = CandidateProfile(
        candidate_id="c1",
        experience=[CandidateExperience(description="Managed PostgreSQL clusters", evidence=ev)]
    )
    req = JDRequirement(id="r1", requirement_text="PostgreSQL", category=RequirementCategory.SKILL, extracted_keywords=["PostgreSQL"])
    eval_res = requirement_evaluator.evaluate_requirement(req, cand)
    refs = EvidenceSelector.select_requirement_evidence(eval_res)
    assert len(refs) >= 1
    assert refs[0].source_section == "Experience"

# 12. Evidence type preserved as recruiter-friendly label
def test_12_evidence_type_preserved(requirement_evaluator, explanation_engine):
    ev = Evidence(source_text="Python", source_section="Skills", confidence_score=1.0, page_number=1, evidence_type="skill")
    cand = CandidateProfile(
        candidate_id="c1",
        skill_details=[CandidateSkill(name="Python", raw_name="Python", evidence=ev)]
    )
    req = JDRequirement(id="r1", requirement_text="Python", category=RequirementCategory.SKILL, extracted_keywords=["Python"])
    eval_res = requirement_evaluator.evaluate_requirement(req, cand)
    refs = EvidenceSelector.select_requirement_evidence(eval_res)
    assert refs[0].evidence_type == "Technical Skill"

# 13. No claim without evidence
def test_13_no_claim_without_evidence(requirement_evaluator, explanation_engine):
    req = JDRequirement(
        id="r_aws",
        requirement_text="AWS cloud architecture",
        category=RequirementCategory.SKILL,
        extracted_keywords=["AWS"]
    )
    cand = CandidateProfile(candidate_id="c_none", skill_details=[CandidateSkill(name="Photoshop", raw_name="Photoshop")])
    eval_res = requirement_evaluator.evaluate_requirement(req, cand)
    refs = EvidenceSelector.select_requirement_evidence(eval_res)
    text = ExplanationTemplates.explain_requirement(eval_res, refs)
    # The system must not claim candidate has AWS
    assert "Matched" not in text
    assert "Supporting evidence was not found" in text
    assert len(refs) == 0

# 14. No fabricated evidence ID
def test_14_no_fabricated_evidence_id(requirement_evaluator):
    cand = CandidateProfile(candidate_id="c1", skill_details=[CandidateSkill(name="Python", raw_name="Python")])
    req = JDRequirement(id="r1", requirement_text="Python", category=RequirementCategory.SKILL, extracted_keywords=["Python"])
    eval_res = requirement_evaluator.evaluate_requirement(req, cand)
    refs = EvidenceSelector.select_requirement_evidence(eval_res)
    # Verify EvidenceReference does not contain a fabricated ID field
    assert not hasattr(refs[0], "evidence_id") or getattr(refs[0], "evidence_id", None) is None

# 15. Aspirational evidence does not become a positive explanation
def test_15_aspirational_evidence_does_not_become_positive_explanation(requirement_evaluator):
    req = JDRequirement(
        id="r1",
        requirement_text="Python programming experience",
        category=RequirementCategory.EXPERIENCE,
        extracted_keywords=["Python"]
    )
    cand = CandidateProfile(
        candidate_id="c_asp",
        experience=[CandidateExperience(description="Interested in learning Python in the future")]
    )
    eval_res = requirement_evaluator.evaluate_requirement(req, cand)
    refs = EvidenceSelector.select_requirement_evidence(eval_res)
    text = ExplanationTemplates.explain_requirement(eval_res, refs)
    assert "Missing" in text
    assert "future aspiration" in text
    assert "Matched" not in text

# 16. Negative evidence is handled correctly in explanation
def test_16_negative_evidence_handled_correctly(requirement_evaluator):
    req = JDRequirement(
        id="r1",
        requirement_text="Python",
        category=RequirementCategory.SKILL,
        extracted_keywords=["Python"]
    )
    cand = CandidateProfile(
        candidate_id="c_neg",
        experience=[CandidateExperience(description="Java developer with no experience with Python")]
    )
    eval_res = requirement_evaluator.evaluate_requirement(req, cand)
    refs = EvidenceSelector.select_requirement_evidence(eval_res)
    text = ExplanationTemplates.explain_requirement(eval_res, refs)
    assert "Missing" in text
    assert "explicitly states a lack of experience" in text

# 17. Insufficient experience is explained as partial/uncertain
def test_17_insufficient_experience_explained_as_partial(requirement_evaluator):
    req = JDRequirement(
        id="r1",
        requirement_text="5+ years of Python experience",
        category=RequirementCategory.EXPERIENCE,
        experience_domain="Python",
        min_years=5.0,
        extracted_keywords=["Python"]
    )
    cand = CandidateProfile(
        candidate_id="c_2yr",
        experience=[CandidateExperience(role="Python Dev", description="Python backend", duration_months=24.0, technologies=["Python"])]
    )
    eval_res = requirement_evaluator.evaluate_requirement(req, cand)
    refs = EvidenceSelector.select_requirement_evidence(eval_res)
    text = ExplanationTemplates.explain_requirement(eval_res, refs)
    assert "Partial match" in text
    assert "below the required 5.0+ years" in text

# 18. Verified experience is explained correctly
def test_18_verified_experience_explained_correctly(requirement_evaluator):
    req = JDRequirement(
        id="r1",
        requirement_text="3+ years of Python experience",
        category=RequirementCategory.EXPERIENCE,
        experience_domain="Python",
        min_years=3.0,
        extracted_keywords=["Python"]
    )
    cand = CandidateProfile(
        candidate_id="c_4yr",
        experience=[CandidateExperience(role="Python Engineer", description="Python services", duration_months=48.0, technologies=["Python"])]
    )
    eval_res = requirement_evaluator.evaluate_requirement(req, cand)
    refs = EvidenceSelector.select_requirement_evidence(eval_res)
    text = ExplanationTemplates.explain_requirement(eval_res, refs)
    assert "Matched" in text
    assert "meeting the 3.0+ years requirement" in text

# 19. Concrete skill cannot be claimed from semantic-only similarity
def test_19_concrete_skill_cannot_be_claimed_from_semantic_similarity(requirement_evaluator):
    req = JDRequirement(
        id="r1",
        requirement_text="Python programming",
        category=RequirementCategory.SKILL,
        extracted_keywords=["Python"]
    )
    cand = CandidateProfile(
        candidate_id="c_data",
        experience=[CandidateExperience(description="data analysis and statistical modeling")]
    )
    eval_res = requirement_evaluator.evaluate_requirement(req, cand)
    refs = EvidenceSelector.select_requirement_evidence(eval_res)
    text = ExplanationTemplates.explain_requirement(eval_res, refs)
    assert "Missing" in text
    assert "Supporting evidence was not found" in text

# 20. Certification cannot be claimed from semantic-only similarity
def test_20_certification_cannot_be_claimed_from_semantic_similarity(requirement_evaluator):
    req = JDRequirement(
        id="r1",
        requirement_text="AWS Certified Solutions Architect",
        category=RequirementCategory.CERTIFICATION,
        extracted_keywords=["AWS Certified Solutions Architect"]
    )
    cand = CandidateProfile(
        candidate_id="c_cloud",
        experience=[CandidateExperience(description="cloud computing on virtual servers")]
    )
    eval_res = requirement_evaluator.evaluate_requirement(req, cand)
    refs = EvidenceSelector.select_requirement_evidence(eval_res)
    text = ExplanationTemplates.explain_requirement(eval_res, refs)
    assert "Missing" in text
    assert "Required certification" in text

# 21. Education cannot be claimed from semantic-only similarity
def test_21_education_cannot_be_claimed_from_semantic_similarity(requirement_evaluator):
    req = JDRequirement(
        id="r1",
        requirement_text="Bachelor's degree in Computer Science",
        category=RequirementCategory.EDUCATION,
        extracted_keywords=["Computer Science"]
    )
    cand = CandidateProfile(
        candidate_id="c_arts",
        education=[CandidateEducation(degree="Bachelor of Arts", field_of_study="English")]
    )
    eval_res = requirement_evaluator.evaluate_requirement(req, cand)
    refs = EvidenceSelector.select_requirement_evidence(eval_res)
    text = ExplanationTemplates.explain_requirement(eval_res, refs)
    assert "Missing" in text
    assert "Educational qualification" in text

# 22. Deterministic repeated explanation
def test_22_deterministic_repeated_explanation(ranking_service, explanation_engine, standard_jd):
    cand = CandidateProfile(candidate_id="c_det", skill_details=[CandidateSkill(name="Python", raw_name="Python"), CandidateSkill(name="SQL", raw_name="SQL")])
    ranked = ranking_service.rank_candidates(standard_jd, [cand])
    
    exp1 = explanation_engine.explain_candidate(ranked[0], standard_jd)
    exp2 = explanation_engine.explain_candidate(ranked[0], standard_jd)
    
    assert exp1.why_ranked_here == exp2.why_ranked_here
    assert exp1.summary == exp2.summary
    assert exp1.strengths == exp2.strengths
    assert len(exp1.matched_requirements) == len(exp2.matched_requirements)
    for r1, r2 in zip(exp1.matched_requirements, exp2.matched_requirements):
        assert r1.explanation == r2.explanation
        assert r1.contribution_to_score == r2.contribution_to_score

# 23. Lower-ranked candidate explanation structure
def test_23_lower_ranked_candidate_explanation(ranking_service, explanation_engine, standard_jd):
    c1 = CandidateProfile(candidate_id="c1", skill_details=[CandidateSkill(name="Python", raw_name="Python"), CandidateSkill(name="SQL", raw_name="SQL"), CandidateSkill(name="Docker", raw_name="Docker")])
    c2 = CandidateProfile(candidate_id="c2", skill_details=[CandidateSkill(name="Python", raw_name="Python"), CandidateSkill(name="SQL", raw_name="SQL")])
    c3 = CandidateProfile(candidate_id="c3", skill_details=[CandidateSkill(name="Python", raw_name="Python")])
    c4 = CandidateProfile(candidate_id="c4")  # Misses all
    
    ranked = ranking_service.rank_candidates(standard_jd, [c1, c2, c3, c4])
    exp_c4 = explanation_engine.explain_candidate(ranked[3], standard_jd)
    
    assert exp_c4.rank == 4
    assert exp_c4.is_top_3 is False
    assert "Ranked #4" in exp_c4.why_ranked_here
    assert len(exp_c4.missing_required_requirements) >= 2

# 24. Empty candidate explanation
def test_24_empty_candidate_explanation(ranking_service, explanation_engine, standard_jd):
    cand_empty = CandidateProfile(candidate_id="c_empty")
    ranked = ranking_service.rank_candidates(standard_jd, [cand_empty])
    exp = explanation_engine.explain_candidate(ranked[0], standard_jd)
    
    assert exp.overall_score == 0.0
    assert len(exp.matched_requirements) == 0
    assert len(exp.all_evidence) == 0

# 25. Evidence deduplication
def test_25_evidence_deduplication():
    refs = [
        EvidenceReference(evidence_text="Built microservices using Python", evidence_type="Work Experience", page_number=2),
        EvidenceReference(evidence_text="Built microservices using Python", evidence_type="Work Experience", page_number=2),
        EvidenceReference(evidence_text="Docker deployment", evidence_type="Project", page_number=3)
    ]
    deduped = EvidenceSelector.deduplicate_evidence(refs)
    assert len(deduped) == 2
    assert deduped[0].evidence_text == "Built microservices using Python"
    assert deduped[1].evidence_text == "Docker deployment"
