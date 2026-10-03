import pytest
import uuid
from app.services.keyword_matcher import (
    KeywordMatcher,
    normalize_text,
    clean_token,
    get_canonical_name,
    is_alias_match,
)
from app.schemas.candidate import (
    CandidateProfile,
    CandidateSkill,
    CandidateExperience,
    CandidateProject,
    CandidateEducation,
    CandidateCertification,
)
from app.schemas.domain import JDRequirement, Evidence, RequirementCategory, RequirementPriority

@pytest.fixture
def matcher():
    return KeywordMatcher()

# 1. Exact skill match
def test_1_exact_skill_match(matcher):
    req = JDRequirement(
        id=str(uuid.uuid4()),
        requirement_text="Python",
        category=RequirementCategory.SKILL,
        extracted_keywords=["Python"]
    )
    profile = CandidateProfile(
        candidate_id="c1",
        skill_details=[CandidateSkill(name="Python", raw_name="Python")]
    )
    results = matcher.evaluate_requirement(req, profile)
    assert len(results) == 1
    assert results[0].match_type == "EXACT"
    assert results[0].lexical_score == 1.0
    assert results[0].evidence_text == "Python"
    assert results[0].evidence_type == "skill"

# 2. Case normalization
def test_2_case_normalization(matcher):
    req = JDRequirement(
        id=str(uuid.uuid4()),
        requirement_text="PYTHON",
        category=RequirementCategory.SKILL,
        extracted_keywords=["PYTHON"]
    )
    profile = CandidateProfile(
        candidate_id="c1",
        skill_details=[CandidateSkill(name="python", raw_name="python")]
    )
    results = matcher.evaluate_requirement(req, profile)
    assert len(results) == 1
    assert results[0].match_type == "EXACT"
    assert results[0].lexical_score == 1.0

# 3. Whitespace and punctuation normalization
def test_3_whitespace_punctuation_normalization(matcher):
    req = JDRequirement(
        id=str(uuid.uuid4()),
        requirement_text="   React.js   ",
        category=RequirementCategory.SKILL,
        extracted_keywords=["React.js"]
    )
    profile = CandidateProfile(
        candidate_id="c1",
        skill_details=[CandidateSkill(name="React.js", raw_name="React.js")]
    )
    results = matcher.evaluate_requirement(req, profile)
    assert len(results) >= 1
    assert results[0].match_type in ["EXACT", "ALIAS"]
    assert results[0].lexical_score == 1.0

# 4. Known alias match: NodeJS -> Node.js
def test_4_known_alias_nodejs(matcher):
    req = JDRequirement(
        id=str(uuid.uuid4()),
        requirement_text="NodeJS",
        category=RequirementCategory.SKILL,
        extracted_keywords=["NodeJS"]
    )
    profile = CandidateProfile(
        candidate_id="c1",
        skill_details=[CandidateSkill(name="Node.js", raw_name="Node.js")]
    )
    results = matcher.evaluate_requirement(req, profile)
    assert len(results) == 1
    assert results[0].match_type == "ALIAS"
    assert results[0].lexical_score == 1.0
    assert results[0].evidence_text == "Node.js"

# 5. Known alias match: Postgres -> PostgreSQL
def test_5_known_alias_postgres(matcher):
    req = JDRequirement(
        id=str(uuid.uuid4()),
        requirement_text="PostgreSQL",
        category=RequirementCategory.SKILL,
        extracted_keywords=["PostgreSQL"]
    )
    profile = CandidateProfile(
        candidate_id="c1",
        skill_details=[CandidateSkill(name="Postgres", raw_name="Postgres")]
    )
    results = matcher.evaluate_requirement(req, profile)
    assert len(results) == 1
    assert results[0].match_type == "ALIAS"
    assert results[0].lexical_score == 1.0
    assert results[0].evidence_text == "Postgres"

# 6. Multi-word skill matching
def test_6_multi_word_skill_matching(matcher):
    req = JDRequirement(
        id=str(uuid.uuid4()),
        requirement_text="Spring Boot",
        category=RequirementCategory.SKILL,
        extracted_keywords=["Spring Boot"]
    )
    profile = CandidateProfile(
        candidate_id="c1",
        experience=[CandidateExperience(description="Developed enterprise services using Spring Boot framework.")]
    )
    results = matcher.evaluate_requirement(req, profile)
    assert len(results) == 1
    assert results[0].match_type == "EXACT"
    assert results[0].matched_keyword == "Spring Boot"
    assert results[0].evidence_type == "experience"

# 7. Substring false-positive protection: Java vs JavaScript
def test_7_substring_false_positive_java_vs_javascript(matcher):
    req = JDRequirement(
        id=str(uuid.uuid4()),
        requirement_text="Java",
        category=RequirementCategory.SKILL,
        extracted_keywords=["Java"]
    )
    profile = CandidateProfile(
        candidate_id="c1",
        skill_details=[CandidateSkill(name="JavaScript", raw_name="JavaScript")]
    )
    results = matcher.evaluate_requirement(req, profile)
    # Must NOT match Java against JavaScript
    assert len(results) == 0

# 8. Short-token false-positive protection: R vs Raspberry Pi, C vs C++
def test_8_short_token_false_positive_r_and_c(matcher):
    # R should not match Raspberry Pi
    req_r = JDRequirement(
        id="req_r",
        requirement_text="R",
        category=RequirementCategory.SKILL,
        extracted_keywords=["R"]
    )
    profile_r = CandidateProfile(
        candidate_id="c1",
        experience=[CandidateExperience(description="Built embedded projects on Raspberry Pi")]
    )
    results_r = matcher.evaluate_requirement(req_r, profile_r)
    assert len(results_r) == 0

    # C should not match C++
    req_c = JDRequirement(
        id="req_c",
        requirement_text="C",
        category=RequirementCategory.SKILL,
        extracted_keywords=["C"]
    )
    profile_c = CandidateProfile(
        candidate_id="c2",
        skill_details=[CandidateSkill(name="C++", raw_name="C++")]
    )
    results_c = matcher.evaluate_requirement(req_c, profile_c)
    assert len(results_c) == 0

# 9. Fuzzy typo/format variation
def test_9_fuzzy_typo_matching(matcher):
    req = JDRequirement(
        id=str(uuid.uuid4()),
        requirement_text="TypeScript",
        category=RequirementCategory.SKILL,
        extracted_keywords=["TypeScript"]
    )
    profile = CandidateProfile(
        candidate_id="c1",
        skill_details=[CandidateSkill(name="typescrpt", raw_name="typescrpt")]
    )
    results = matcher.evaluate_requirement(req, profile)
    assert len(results) == 1
    assert results[0].match_type == "FUZZY"
    assert results[0].lexical_score >= 0.85

# 10. Unrelated term does not match
def test_10_unrelated_term_does_not_match(matcher):
    req = JDRequirement(
        id=str(uuid.uuid4()),
        requirement_text="Kubernetes",
        category=RequirementCategory.SKILL,
        extracted_keywords=["Kubernetes"]
    )
    profile = CandidateProfile(
        candidate_id="c1",
        skill_details=[CandidateSkill(name="Graphic Design", raw_name="Graphic Design")]
    )
    results = matcher.evaluate_requirement(req, profile)
    assert len(results) == 0

# 11. Multiple candidate evidence items
def test_11_multiple_candidate_evidence_items(matcher):
    req = JDRequirement(
        id=str(uuid.uuid4()),
        requirement_text="Docker",
        category=RequirementCategory.SKILL,
        extracted_keywords=["Docker"]
    )
    profile = CandidateProfile(
        candidate_id="c1",
        skill_details=[CandidateSkill(name="Docker", raw_name="Docker")],
        experience=[CandidateExperience(description="Built Docker containers for microservices")],
        projects=[CandidateProject(name="Docker Deployment", description="Orchestrated Docker cluster")]
    )
    results = matcher.evaluate_requirement(req, profile)
    assert len(results) == 3
    # First should be the explicit skill evidence due to priority sorting
    assert results[0].evidence_type == "skill"
    assert results[0].match_type == "EXACT"

# 12. Provenance preservation
def test_12_provenance_preservation(matcher):
    req = JDRequirement(
        id="req_prov",
        requirement_text="Python",
        category=RequirementCategory.SKILL,
        extracted_keywords=["Python"]
    )
    ev = Evidence(
        source_text="Python programming",
        source_section="Technical Skills",
        confidence_score=1.0,
        page_number=2,
        evidence_type="skill"
    )
    profile = CandidateProfile(
        candidate_id="c1",
        skill_details=[CandidateSkill(name="Python", raw_name="Python", evidence=ev)]
    )
    results = matcher.evaluate_requirement(req, profile)
    assert len(results) == 1
    res = results[0]
    assert res.page_number == 2
    assert res.source_section == "Technical Skills"
    assert res.source_text == "Python programming"
    assert res.evidence_id is None  # No fabricated ID
    assert res.evidence == ev

# 13. Explicit skill evidence
def test_13_explicit_skill_evidence(matcher):
    req = JDRequirement(
        id="req_skill",
        requirement_text="Go",
        category=RequirementCategory.SKILL,
        extracted_keywords=["Go"]
    )
    profile = CandidateProfile(
        candidate_id="c1",
        skill_details=[CandidateSkill(name="Go", raw_name="Go")]
    )
    results = matcher.evaluate_requirement(req, profile)
    assert len(results) == 1
    assert results[0].evidence_type == "skill"
    assert results[0].matched_keyword == "Go"

# 14. Experience and project evidence
def test_14_experience_project_evidence(matcher):
    req = JDRequirement(
        id="req_exp",
        requirement_text="AWS",
        category=RequirementCategory.SKILL,
        extracted_keywords=["AWS"]
    )
    profile = CandidateProfile(
        candidate_id="c1",
        experience=[CandidateExperience(role="Cloud Engineer", description="Deployed workloads on AWS cloud infrastructure")],
        projects=[CandidateProject(name="AWS Migration", description="Migrated legacy database to AWS")]
    )
    results = matcher.evaluate_requirement(req, profile)
    assert len(results) == 2
    types = {r.evidence_type for r in results}
    assert "experience" in types
    assert "project" in types

# 15. Aspirational phrase protection: "Interested in learning Rust"
def test_15_aspirational_phrase_protection(matcher):
    req = JDRequirement(
        id="req_rust",
        requirement_text="Rust",
        category=RequirementCategory.SKILL,
        extracted_keywords=["Rust"]
    )
    profile = CandidateProfile(
        candidate_id="c1",
        experience=[CandidateExperience(description="Interested in learning Rust in the future")]
    )
    results = matcher.evaluate_requirement(req, profile)
    # Must NOT be treated as a positive active match
    assert len(results) == 0

# 16. Negative phrase protection: "No experience with Python"
def test_16_negative_phrase_protection(matcher):
    req = JDRequirement(
        id="req_py",
        requirement_text="Python",
        category=RequirementCategory.SKILL,
        extracted_keywords=["Python"]
    )
    profile = CandidateProfile(
        candidate_id="c1",
        experience=[CandidateExperience(description="Currently working in Java, no experience with Python")]
    )
    results = matcher.evaluate_requirement(req, profile)
    # Must NOT be treated as a positive match
    assert len(results) == 0

# 17. Unknown / proprietary technical term preservation
def test_17_unknown_proprietary_term_preservation(matcher):
    req = JDRequirement(
        id="req_custom",
        requirement_text="Experience with KubeVortex",
        category=RequirementCategory.SKILL,
        extracted_keywords=["KubeVortex"]
    )
    profile = CandidateProfile(
        candidate_id="c1",
        skill_details=[CandidateSkill(name="KubeVortex", raw_name="KubeVortex")]
    )
    results = matcher.evaluate_requirement(req, profile)
    assert len(results) == 1
    assert results[0].match_type == "EXACT"
    assert results[0].matched_keyword == "KubeVortex"

# 18. Deterministic repeated execution
def test_18_deterministic_repeated_execution(matcher):
    req = JDRequirement(
        id="req_det",
        requirement_text="FastAPI",
        category=RequirementCategory.SKILL,
        extracted_keywords=["FastAPI"]
    )
    profile = CandidateProfile(
        candidate_id="c1",
        skill_details=[CandidateSkill(name="FastAPI", raw_name="FastAPI")],
        experience=[CandidateExperience(description="Built async APIs using FastAPI")]
    )
    res_run1 = matcher.evaluate_requirement(req, profile)
    res_run2 = matcher.evaluate_requirement(req, profile)
    assert len(res_run1) == len(res_run2)
    for r1, r2 in zip(res_run1, res_run2):
        assert r1.matched_keyword == r2.matched_keyword
        assert r1.match_type == r2.match_type
        assert r1.lexical_score == r2.lexical_score
        assert r1.evidence_text == r2.evidence_text
        assert r1.evidence_type == r2.evidence_type

# 19. Empty requirement handling
def test_19_empty_requirement(matcher):
    req = JDRequirement(
        id="req_empty",
        requirement_text="",
        category=RequirementCategory.SKILL,
        extracted_keywords=[]
    )
    profile = CandidateProfile(
        candidate_id="c1",
        skill_details=[CandidateSkill(name="Python", raw_name="Python")]
    )
    results = matcher.evaluate_requirement(req, profile)
    assert results == []

# 20. Empty candidate evidence handling
def test_20_empty_candidate_evidence(matcher):
    req = JDRequirement(
        id="req_valid",
        requirement_text="Python",
        category=RequirementCategory.SKILL,
        extracted_keywords=["Python"]
    )
    profile = CandidateProfile(candidate_id="c_empty")
    results = matcher.evaluate_requirement(req, profile)
    assert results == []
