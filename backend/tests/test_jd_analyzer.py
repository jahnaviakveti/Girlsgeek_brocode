import pytest
from pathlib import Path
from app.services.document_parser import parse_document
from app.services.jd_analyzer import (
    analyze_jd,
    determine_category,
    determine_priority,
    extract_experience_details,
    is_negated,
    decompose_requirement,
)
from app.schemas.domain import RequirementCategory, RequirementPriority

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "test_fixtures"

def test_1_required_skill():
    doc = parse_document(FIXTURES_DIR / "jd_standard_sample.pdf")
    jd = analyze_jd(doc)

    # Check for presence of required skill
    python_req = next((r for r in jd.requirements if "Python" in r.extracted_keywords), None)
    assert python_req is not None
    assert python_req.category == RequirementCategory.SKILL
    assert python_req.priority == RequirementPriority.REQUIRED
    assert python_req.is_required is True

def test_2_preferred_skill():
    doc = parse_document(FIXTURES_DIR / "jd_standard_sample.pdf")
    jd = analyze_jd(doc)

    # Check for preferred skill (e.g. GraphQL is desirable)
    graphql_req = next((r for r in jd.requirements if "GraphQL" in r.extracted_keywords), None)
    assert graphql_req is not None
    assert graphql_req.category == RequirementCategory.SKILL
    assert graphql_req.priority == RequirementPriority.PREFERRED
    assert graphql_req.is_required is False

def test_3_technology_list_granularity():
    doc = parse_document(FIXTURES_DIR / "jd_standard_sample.pdf")
    jd = analyze_jd(doc)

    # 'Hands-on experience with Python, Django, PostgreSQL and Docker'
    # Should be decomposed into atomic requirements
    tech_keywords = [kw for r in jd.requirements for kw in r.extracted_keywords]
    assert "Python" in tech_keywords
    assert "Django" in tech_keywords
    assert "PostgreSQL" in tech_keywords
    assert "Docker" in tech_keywords

def test_4_experience_requirement():
    doc = parse_document(FIXTURES_DIR / "jd_standard_sample.pdf")
    jd = analyze_jd(doc)

    exp_req = next((r for r in jd.requirements if r.category == RequirementCategory.EXPERIENCE), None)
    assert exp_req is not None
    assert exp_req.min_years == 2.0
    assert exp_req.priority == RequirementPriority.REQUIRED
    assert "backend" in (exp_req.experience_domain or "").lower()

def test_5_education_requirement():
    doc = parse_document(FIXTURES_DIR / "jd_standard_sample.pdf")
    jd = analyze_jd(doc)

    edu_req = next((r for r in jd.requirements if r.category == RequirementCategory.EDUCATION), None)
    assert edu_req is not None
    assert edu_req.priority == RequirementPriority.REQUIRED
    assert "Bachelor" in edu_req.requirement_text or "bachelor" in edu_req.requirement_text.lower()

def test_6_certification_requirement():
    doc = parse_document(FIXTURES_DIR / "jd_standard_sample.pdf")
    jd = analyze_jd(doc)

    cert_req = next((r for r in jd.requirements if r.category == RequirementCategory.CERTIFICATION), None)
    assert cert_req is not None
    assert "AWS Certified" in cert_req.requirement_text or "certification" in cert_req.requirement_text.lower()
    assert cert_req.priority == RequirementPriority.PREFERRED

def test_7_contextual_conceptual_requirement_preservation():
    # 'Demonstrated experience designing scalable distributed systems'
    # Should remain a conceptual requirement rather than being split
    doc = parse_document(FIXTURES_DIR / "jd_standard_sample.pdf")
    jd = analyze_jd(doc)

    concept_req = next((r for r in jd.requirements if "scalable distributed systems" in r.requirement_text.lower()), None)
    assert concept_req is not None
    assert "designing" in concept_req.requirement_text.lower()

def test_8_required_vs_preferred_wording():
    # Explicit linguistic markers
    p1, neg1, _ = determine_priority("Must have 3 years of React experience")
    assert p1 == RequirementPriority.REQUIRED
    assert neg1 is False

    p2, neg2, _ = determine_priority("Docker experience is a bonus")
    assert p2 == RequirementPriority.PREFERRED
    assert neg2 is False

def test_9_negation_handling():
    # 'Java experience is not required' must NOT become REQUIRED
    text = "Java experience is not required."
    assert is_negated(text) is True

    priority, neg, _ = determine_priority(text)
    assert neg is True
    assert priority != RequirementPriority.REQUIRED

    reqs = decompose_requirement(text, text, page_number=1, source_section="Preferred")
    for r in reqs:
        assert r.is_negated is True
        assert r.is_required is False

def test_10_and_relationship():
    text = "Proficiency in Python and Django is required."
    reqs = decompose_requirement(text, text, page_number=1)
    # Joint skills preserved with AND logic
    assert any(r.logical_operator == "AND" for r in reqs)

def test_11_or_alternative_relationship():
    # 'Experience with React or Angular for frontend development.'
    # Must NOT become two separate independent requirements!
    doc = parse_document(FIXTURES_DIR / "jd_standard_sample.pdf")
    jd = analyze_jd(doc)

    alt_req = next((r for r in jd.requirements if (r.is_alternative or r.logical_operator == "OR") and "React" in r.extracted_keywords), None)
    assert alt_req is not None
    assert "React" in alt_req.extracted_keywords
    assert "Angular" in alt_req.extracted_keywords
    assert alt_req.logical_operator == "OR"
    assert "React" in alt_req.alternatives and "Angular" in alt_req.alternatives

def test_12_ambiguous_soft_wording():
    # 'Familiarity with GraphQL'
    p, neg, conf = determine_priority("Familiarity with GraphQL")
    assert p == RequirementPriority.PREFERRED
    assert conf < 1.0

def test_13_requirements_inside_paragraphs():
    # Tests extraction from prose text without bullet points
    doc = parse_document(FIXTURES_DIR / "jd_paragraph_sample.pdf")
    jd = analyze_jd(doc)

    assert len(jd.requirements) >= 3
    # Check Python and FastAPI extracted from paragraph
    all_kws = [kw for r in jd.requirements for kw in r.extracted_keywords]
    assert "Python" in all_kws
    assert "FastAPI" in all_kws

    # Check experience extracted from paragraph
    exp_req = next((r for r in jd.requirements if r.category == RequirementCategory.EXPERIENCE), None)
    assert exp_req is not None
    assert exp_req.min_years == 3.0

    # Check negation in paragraph: 'Prior C++ knowledge is not required'
    cpp_req = next((r for r in jd.requirements if "C++" in r.extracted_keywords or "c++" in r.requirement_text.lower()), None)
    if cpp_req:
        assert cpp_req.is_negated is True
        assert cpp_req.is_required is False

def test_14_multipage_section_provenance():
    # Verifies requirement provenance across multiple pages
    doc = parse_document(FIXTURES_DIR / "jd_multipage_sample.pdf")
    jd = analyze_jd(doc)

    p1_reqs = [r for r in jd.requirements if r.page_number == 1]
    p2_reqs = [r for r in jd.requirements if r.page_number == 2]

    assert len(p1_reqs) > 0
    assert len(p2_reqs) > 0

    # Linux experience on page 1
    linux_req = next(r for r in p1_reqs if "Linux" in r.extracted_keywords or "linux" in r.requirement_text.lower())
    assert linux_req.page_number == 1

    # Kubernetes / Terraform on page 2
    p2_kws = [kw for r in p2_reqs for kw in r.extracted_keywords]
    assert "Kubernetes" in p2_kws or "Terraform" in p2_kws

def test_15_false_positive_protection():
    # 'Working with a collaborative engineering team' and 'Competitive compensation'
    # Must NOT become requirements
    doc = parse_document(FIXTURES_DIR / "jd_standard_sample.pdf")
    jd = analyze_jd(doc)

    req_texts = [r.requirement_text.lower() for r in jd.requirements]
    assert not any("collaborative" in t for t in req_texts)
    assert not any("compensation" in t for t in req_texts)
    assert not any("health benefits" in t for t in req_texts)

def test_16_determinism():
    doc = parse_document(FIXTURES_DIR / "jd_standard_sample.pdf")
    jd1 = analyze_jd(doc)
    jd2 = analyze_jd(doc)

    assert len(jd1.requirements) == len(jd2.requirements)
    for r1, r2 in zip(jd1.requirements, jd2.requirements):
        assert r1.requirement_text == r2.requirement_text
        assert r1.category == r2.category
        assert r1.priority == r2.priority
        assert r1.extracted_keywords == r2.extracted_keywords
        assert r1.is_alternative == r2.is_alternative
        assert r1.logical_operator == r2.logical_operator

def test_17_taxonomy_extensibility_preserves_unknown_terms():
    # Verify that an unfamiliar or proprietary technical term (e.g. AcmeFlow)
    # is NOT discarded merely because it is absent from the taxonomy.
    from app.services.jd_analyzer.taxonomy import CANONICAL_TECHNOLOGIES
    assert "acmeflow" not in CANONICAL_TECHNOLOGIES

    text = "Experience with AcmeFlow platform"
    reqs = decompose_requirement(text, source_text=text, page_number=1, source_section="Technical Skills")

    assert len(reqs) == 1
    req = reqs[0]
    assert req.requirement_text == "Experience with AcmeFlow platform"
    assert "AcmeFlow" in req.extracted_keywords
    # The category may be OTHER or SKILL if it cannot be classified as a standard taxonomy item
    assert req.category in (RequirementCategory.OTHER, RequirementCategory.SKILL)
    assert req.source_text == "Experience with AcmeFlow platform"

def test_18_confidence_semantics_distinction():
    # Verify that extraction_confidence specifically represents the JD analyzer's
    # confidence in extracting/interpreting the requirement, NOT candidate match confidence.
    from app.schemas.domain import JDRequirement, RequirementMatch

    # 1. Direct extraction_confidence initialization
    req1 = JDRequirement(
        id="r-conf-1",
        requirement_text="Familiarity with GraphQL",
        extraction_confidence=0.80
    )
    assert req1.extraction_confidence == 0.80
    # Backward compatibility alias
    assert req1.confidence == 0.80

    # 2. Backwards compatible 'confidence' kwarg mapping
    req2 = JDRequirement(
        id="r-conf-2",
        requirement_text="Must know Python",
        confidence=0.95
    )
    assert req2.extraction_confidence == 0.95
    assert req2.confidence == 0.95

    # 3. Explicit separation from candidate match score/confidence
    # Candidate match scores belong to RequirementMatch, not JDRequirement
    match = RequirementMatch(
        candidate_id="cand-123",
        requirement_id=req1.id,
        keyword_match_score=0.90,
        semantic_match_score=0.85
    )
    # JD extraction confidence (0.80) != Candidate match scores (0.90 / 0.85)
    assert req1.extraction_confidence != match.keyword_match_score
    assert req1.extraction_confidence != match.semantic_match_score
