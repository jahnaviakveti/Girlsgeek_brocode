import pytest
from app.schemas.domain import (
    JDRequirement,
    JobDescription,
    ResumeDocument,
    CandidateScore,
    CandidateRanking,
    RequirementMatch,
    Evidence,
    RequirementCategory,
    RequirementPriority,
    MatchVerdict
)

def test_requirement_priority_and_category():
    # Test default values
    req_default = JDRequirement(
        id="req-1",
        requirement_text="Must know Python"
    )
    assert req_default.category == RequirementCategory.SKILL
    assert req_default.priority == RequirementPriority.REQUIRED
    assert req_default.is_required is True

    # Test explicit non-default values
    req_pref = JDRequirement(
        id="req-2",
        requirement_text="Experience with Docker is a plus",
        category=RequirementCategory.EXPERIENCE,
        priority=RequirementPriority.PREFERRED
    )
    assert req_pref.category == RequirementCategory.EXPERIENCE
    assert req_pref.priority == RequirementPriority.PREFERRED
    assert req_pref.is_required is False

def test_requirement_match_verdict_enum():
    match = RequirementMatch(
        candidate_id="cand-1",
        requirement_id="req-1"
    )
    # Verify default status is MISSING
    assert match.verdict == MatchVerdict.MISSING

    # Verify transition to PARTIAL and MATCHED
    match.verdict = MatchVerdict.PARTIAL
    assert match.verdict == MatchVerdict.PARTIAL
    assert match.verdict.value == "partial"

    match.verdict = MatchVerdict.MATCHED
    assert match.verdict == MatchVerdict.MATCHED
    assert match.verdict.value == "matched"

def test_evidence_provenance_fields():
    # Test basic evidence with optional fields omitted
    ev_basic = Evidence(
        source_text="Built microservices in Python",
        source_section="Experience",
        confidence_score=0.92
    )
    assert ev_basic.page_number is None
    assert ev_basic.evidence_type is None

    # Test evidence with full provenance metadata
    ev_full = Evidence(
        source_text="Lead developer on React frontend",
        source_section="Projects",
        confidence_score=0.88,
        page_number=1,
        evidence_type="direct_quote"
    )
    assert ev_full.page_number == 1
    assert ev_full.evidence_type == "direct_quote"
    assert ev_full.source_section == "Projects"

def test_mutable_default_isolation():
    # Verify JobDescription requirements isolation
    jd1 = JobDescription(jd_id="jd-1", raw_text="text 1")
    jd2 = JobDescription(jd_id="jd-2", raw_text="text 2")

    req = JDRequirement(id="r-1", requirement_text="Git")
    jd1.requirements.append(req)

    assert len(jd1.requirements) == 1
    assert len(jd2.requirements) == 0

    # Verify JDRequirement extracted_keywords isolation
    req1 = JDRequirement(id="r-1", requirement_text="Python")
    req2 = JDRequirement(id="r-2", requirement_text="Java")

    req1.extracted_keywords.append("python3")

    assert "python3" in req1.extracted_keywords
    assert len(req2.extracted_keywords) == 0

    # Verify CandidateRanking list isolation
    score = CandidateScore(candidate_id="c-1", overall_score=80.0)
    rank1 = CandidateRanking(rank=1, candidate_id="c-1", score=score)
    rank2 = CandidateRanking(rank=2, candidate_id="c-2", score=score)

    rank1.matched_skills.append("FastAPI")
    rank1.missing_skills.append("Kubernetes")

    assert len(rank1.matched_skills) == 1
    assert len(rank2.matched_skills) == 0
    assert len(rank1.missing_skills) == 1
    assert len(rank2.missing_skills) == 0

    # Verify ResumeDocument sections dict isolation
    res1 = ResumeDocument(candidate_id="c-1", raw_text="raw 1")
    res2 = ResumeDocument(candidate_id="c-2", raw_text="raw 2")

    res1.sections["skills"] = "Python, SQL"

    assert "skills" in res1.sections
    assert len(res2.sections) == 0
