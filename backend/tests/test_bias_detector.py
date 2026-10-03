import pytest
from app.schemas.bias import BiasCategory, BiasSeverity, JDBiasAudit
from app.schemas.domain import JobDescription, JDRequirement, RequirementCategory, RequirementPriority
from app.services.jd_analyzer.bias_detector import JDBiasDetector

def test_inclusive_clean_jd_audit():
    detector = JDBiasDetector()
    jd = JobDescription(
        jd_id="jd_inclusive_001",
        title="Junior Software Engineer",
        raw_text="We are seeking a collaborative Junior Software Engineer. Requirements include proficiency with Python, React, and REST APIs. B.S. in Computer Science or equivalent practical project experience.",
        requirements=[
            JDRequirement(id="r1", requirement_text="Proficiency in Python and React", category=RequirementCategory.SKILL, priority=RequirementPriority.REQUIRED),
            JDRequirement(id="r2", requirement_text="Degree in CS or equivalent practical experience", category=RequirementCategory.EDUCATION, priority=RequirementPriority.REQUIRED),
        ]
    )

    audit = detector.audit_jd(jd)
    assert isinstance(audit, JDBiasAudit)
    assert audit.inclusivity_score >= 95
    assert audit.inclusivity_grade == "A+"
    assert audit.bias_free is True
    assert len(audit.flags) == 0

def test_detects_gender_and_aggressive_phrasing():
    detector = JDBiasDetector()
    raw = "We are seeking a 10x rockstar ninja developer who is aggressive and ready to dominate the market in a work hard play hard environment."
    jd = JobDescription(
        jd_id="jd_aggressive_001",
        title="Full Stack Ninja",
        raw_text=raw,
        requirements=[]
    )

    audit = detector.audit_jd(jd)
    assert audit.inclusivity_score < 70
    assert audit.bias_free is False
    categories = [f.category for f in audit.flags]
    assert BiasCategory.GENDER_CODED in categories

    matched_texts = [f.matched_text.lower() for f in audit.flags]
    assert any("rockstar" in m or "ninja" in m for m in matched_texts)
    assert any("work hard" in m for m in matched_texts)
    assert any("dominate" in m or "aggressive" in m for m in matched_texts)

def test_detects_pedigree_and_degree_gatekeeping():
    detector = JDBiasDetector()
    raw = "Only candidates from Tier 1 colleges or Ivy League universities should apply. Strictly B.Tech graduates only; no bootcamps."
    jd = JobDescription(
        jd_id="jd_pedigree_001",
        title="Backend Engineer",
        raw_text=raw,
        requirements=[]
    )

    audit = detector.audit_jd(jd)
    assert audit.inclusivity_score < 75
    categories = [f.category for f in audit.flags]
    assert BiasCategory.PEDIGREE_DEGREE in categories

    matched_texts = [f.matched_text.lower() for f in audit.flags]
    assert any("tier 1" in m or "ivy" in m for m in matched_texts)

def test_detects_unrealistic_experience_for_internship():
    detector = JDBiasDetector()
    jd = JobDescription(
        jd_id="jd_intern_001",
        title="Junior Full Stack Developer Intern",
        raw_text="Seeking an intern for summer. Must have 5+ years experience in enterprise distributed architectures.",
        requirements=[
            JDRequirement(
                id="r1",
                requirement_text="Must have 5+ years experience with enterprise software architectures",
                category=RequirementCategory.EXPERIENCE,
                priority=RequirementPriority.REQUIRED,
                min_years=5.0
            )
        ]
    )

    audit = detector.audit_jd(jd)
    categories = [f.category for f in audit.flags]
    assert BiasCategory.UNREALISTIC_EXPERIENCE in categories
    exp_flag = next(f for f in audit.flags if f.category == BiasCategory.UNREALISTIC_EXPERIENCE)
    assert exp_flag.severity == BiasSeverity.HIGH
    assert "internship" in exp_flag.explanation.lower() or "intern" in exp_flag.explanation.lower()

def test_detects_age_and_ableist_coding():
    detector = JDBiasDetector()
    raw = "Looking for digital natives with young and energetic personalities. Must lift 50 lbs and be native English speaker only."
    jd = JobDescription(
        jd_id="jd_age_ableist_001",
        title="Software Intern",
        raw_text=raw,
        requirements=[]
    )

    audit = detector.audit_jd(jd)
    categories = set(f.category for f in audit.flags)
    assert BiasCategory.AGE_GENERATIONAL in categories
    assert BiasCategory.ABLEIST_PHYSICAL in categories
