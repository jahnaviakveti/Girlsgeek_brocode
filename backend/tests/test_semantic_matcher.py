import pytest
import numpy as np
from app.services.semantic_matcher import LocalSentenceTransformerEmbeddingModel, SemanticMatcher, cosine_similarity
from app.schemas.candidate import CandidateProfile, CandidateSkill, CandidateExperience
from app.schemas.domain import JDRequirement, Evidence, RequirementCategory
import uuid

@pytest.fixture(scope="module")
def embedding_model():
    # Use a real model for realistic semantic similarity tests
    return LocalSentenceTransformerEmbeddingModel("all-MiniLM-L6-v2")

@pytest.fixture(scope="module")
def matcher(embedding_model):
    return SemanticMatcher(embedding_model)

def test_cosine_similarity():
    vec_a = np.array([1.0, 0.0, 0.0])
    vec_b = np.array([1.0, 0.0, 0.0])
    assert np.isclose(cosine_similarity(vec_a, vec_b), 1.0)
    
    vec_c = np.array([0.0, 1.0, 0.0])
    assert np.isclose(cosine_similarity(vec_a, vec_c), 0.0)
    
    vec_d = np.array([-1.0, 0.0, 0.0])
    assert np.isclose(cosine_similarity(vec_a, vec_d), -1.0)
    
    # Zero vectors
    assert cosine_similarity(np.array([0.0, 0.0]), np.array([1.0, 1.0])) == 0.0

def test_batch_cosine_similarity():
    vec = np.array([1.0, 0.0, 0.0])
    matrix = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [-1.0, 0.0, 0.0],
        [0.0, 0.0, 0.0]
    ])
    from app.services.semantic_matcher import batch_cosine_similarity
    sims = batch_cosine_similarity(vec, matrix)
    assert len(sims) == 4
    assert np.isclose(sims[0], 1.0)
    assert np.isclose(sims[1], 0.0)
    assert np.isclose(sims[2], -1.0)
    assert np.isclose(sims[3], 0.0)

def test_exact_semantic_relationship(matcher):
    req = JDRequirement(
        id=str(uuid.uuid4()),
        requirement_text="Python",
        category=RequirementCategory.SKILL,
        is_required=True
    )
    profile = CandidateProfile(
        candidate_id="c1",
        skill_details=[CandidateSkill(name="Python", raw_name="Python")]
    )
    results = matcher.evaluate_requirement(req, profile)
    assert len(results) == 1
    assert results[0].similarity_score > 0.95

def test_close_conceptual_relationship_relative_ordering(matcher):
    """
    Validates relative semantic ordering (NOT a fixed production threshold).
    Related evidence ('Kubernetes') must score substantially higher than
    unrelated evidence ('graphic design and Adobe Photoshop') for 'container orchestration'.
    """
    req = JDRequirement(
        id=str(uuid.uuid4()),
        requirement_text="container orchestration",
        category=RequirementCategory.SKILL,
        is_required=True
    )
    profile = CandidateProfile(
        candidate_id="c1",
        skill_details=[
            CandidateSkill(name="Kubernetes", raw_name="Kubernetes"),
            CandidateSkill(name="graphic design and Adobe Photoshop", raw_name="graphic design and Adobe Photoshop")
        ]
    )
    results = matcher.evaluate_requirement(req, profile)
    assert len(results) == 2
    # Strongest evidence must be the conceptually related one
    assert results[0].evidence_text == "Kubernetes"
    assert results[1].evidence_text == "graphic design and Adobe Photoshop"
    # Relative assertion: related concept must have higher similarity than unrelated
    assert results[0].similarity_score > results[1].similarity_score
    # Documented relative gap: related is significantly greater than unrelated
    assert (results[0].similarity_score - results[1].similarity_score) > 0.2

def test_related_wording_relative_ordering(matcher):
    """
    Validates relative semantic ordering (NOT a fixed production threshold).
    'PostgreSQL database development' must score higher than unrelated 'graphic design'
    against 'relational database experience'.
    """
    req = JDRequirement(
        id=str(uuid.uuid4()),
        requirement_text="relational database experience",
        category=RequirementCategory.EXPERIENCE,
        is_required=True
    )
    profile = CandidateProfile(
        candidate_id="c1",
        experience=[
            CandidateExperience(description="PostgreSQL database development"),
            CandidateExperience(description="graphic design and Adobe Photoshop")
        ]
    )
    results = matcher.evaluate_requirement(req, profile)
    assert len(results) == 2
    rel_res = next(r for r in results if "PostgreSQL" in r.evidence_text)
    unrel_res = next(r for r in results if "graphic design" in r.evidence_text)
    # Relative assertion
    assert rel_res.similarity_score > unrel_res.similarity_score

def test_multiple_evidence_items(matcher):
    req = JDRequirement(
        id=str(uuid.uuid4()),
        requirement_text="experience with container orchestration",
        category=RequirementCategory.SKILL,
        is_required=True
    )
    profile = CandidateProfile(
        candidate_id="c1",
        experience=[
            CandidateExperience(description="Built Docker images for local dev"),
            CandidateExperience(description="Managed AWS infrastructure"),
            CandidateExperience(description="Deployed Kubernetes workloads to production cluster")
        ]
    )
    results = matcher.evaluate_requirement(req, profile)
    assert len(results) == 3
    # The Kubernetes one should be highest
    assert "Kubernetes" in results[0].evidence_text

def test_provenance_preservation(matcher):
    req = JDRequirement(
        id="r1",
        requirement_text="Java",
        category=RequirementCategory.SKILL,
        is_required=True
    )
    evidence = Evidence(
        page_number=2,
        source_section="Skills",
        source_text="Core Java", confidence_score=1.0
    )
    profile = CandidateProfile(
        candidate_id="c1",
        skill_details=[CandidateSkill(name="Java", raw_name="Java", evidence=evidence)]
    )
    results = matcher.evaluate_requirement(req, profile)
    assert len(results) == 1
    res = results[0]
    assert res.page_number == 2
    assert res.source_section == "Skills"
    assert res.source_text == "Core Java"

def test_empty_evidence(matcher):
    req = JDRequirement(
        id="r1",
        requirement_text="Java",
        category=RequirementCategory.SKILL,
        is_required=True
    )
    profile = CandidateProfile(candidate_id="c1")
    results = matcher.evaluate_requirement(req, profile)
    assert len(results) == 0

def test_empty_requirement(matcher):
    req = JDRequirement(
        id="r1",
        requirement_text="",
        category=RequirementCategory.SKILL,
        is_required=True
    )
    profile = CandidateProfile(
        candidate_id="c1",
        skill_details=[CandidateSkill(name="Java", raw_name="Java")]
    )
    results = matcher.evaluate_requirement(req, profile)
    assert len(results) == 0

def test_determinism(matcher):
    req = JDRequirement(
        id="r1",
        requirement_text="Machine Learning",
        category=RequirementCategory.SKILL,
        is_required=True
    )
    profile = CandidateProfile(
        candidate_id="c1",
        experience=[CandidateExperience(description="Trained deep neural networks in PyTorch")]
    )
    res1 = matcher.evaluate_requirement(req, profile)[0]
    res2 = matcher.evaluate_requirement(req, profile)[0]
    assert np.isclose(res1.similarity_score, res2.similarity_score)

def test_adversarial_semantic_vs_context(matcher):
    # This demonstrates that semantic matching is NOT the final verdict
    req = JDRequirement(
        id="r1",
        requirement_text="Expert Python developer",
        category=RequirementCategory.EXPERIENCE,
        is_required=True
    )
    profile = CandidateProfile(
        candidate_id="c1",
        experience=[CandidateExperience(description="Interested in learning Python")]
    )
    results = matcher.evaluate_requirement(req, profile)
    assert len(results) == 1
    # They both share "Python", so similarity will be somewhat high, 
    # but the meaning is opposite (expert vs learning).
    # The matcher should just report the similarity.
    assert results[0].similarity_score > 0.4
    
