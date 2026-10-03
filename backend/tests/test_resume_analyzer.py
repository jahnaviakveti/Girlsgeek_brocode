import pytest
from pathlib import Path
from app.services.document_parser import parse_document
from app.services.resume_analyzer import (
    ResumeAnalyzer,
    analyze_resume,
    ResumeSectionExtractor,
    SkillExtractor,
    ExperienceExtractor,
    EducationExtractor,
    CertificationExtractor,
    ProjectExtractor,
    parse_date_range,
)
from app.schemas.candidate import CandidateProfile, CandidateSkill
from app.schemas.domain import Evidence

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "test_fixtures"

@pytest.fixture
def standard_resume_doc():
    return parse_document(FIXTURES_DIR / "resume_standard_sample.pdf")

@pytest.fixture
def messy_resume_doc():
    return parse_document(FIXTURES_DIR / "resume_messy_sample.pdf")

@pytest.fixture
def two_column_resume_doc():
    return parse_document(FIXTURES_DIR / "resume_two_column_sample.pdf")

def test_1_basic_resume_extraction(standard_resume_doc):
    """Verify analyze_resume extracts candidate name, email, phone, and core profile."""
    profile = analyze_resume(standard_resume_doc, candidate_id="cand_jane_001")
    assert profile.candidate_id == "cand_jane_001"
    assert profile.name == "Jane Doe"
    assert profile.email == "jane.doe@example.com"
    assert profile.phone == "(555) 123-4567"
    assert profile.summary is not None
    assert "distributed systems" in profile.summary.lower()

def test_2_section_detection_and_mapping(standard_resume_doc):
    """Verify standard sections are mapped accurately."""
    profile = analyze_resume(standard_resume_doc)
    expected_sections = {"skills", "experience", "education", "certifications", "projects", "summary"}
    assert expected_sections.issubset(set(profile.sections.keys()))

def test_3_skills_extraction(standard_resume_doc):
    """Verify technical skills are extracted with canonical names and categories."""
    profile = analyze_resume(standard_resume_doc)
    extracted_names = {s.name for s in profile.skill_details}
    assert "Python" in extracted_names
    assert "React" in extracted_names
    assert "PostgreSQL" in extracted_names
    assert "Docker" in extracted_names

    # Check category
    python_skill = next(s for s in profile.skill_details if s.name == "Python")
    assert python_skill.category == "technology"
    assert python_skill.evidence is not None
    assert python_skill.evidence.source_section in ["Skills", "skills", "General Body"]

def test_4_technologies_list_aggregation(standard_resume_doc):
    """Verify aggregated technologies list contains unique items from skills, experience, and projects."""
    profile = analyze_resume(standard_resume_doc)
    assert isinstance(profile.technologies, list)
    # Check deduplication
    assert len(profile.technologies) == len(set(profile.technologies))
    assert "Python" in profile.technologies
    assert "FastAPI" in profile.technologies  # from experience
    assert "Redis" in profile.technologies    # from project

def test_5_alias_and_technology_normalization(messy_resume_doc):
    """Verify aliases like NodeJS -> Node.js and Postgres -> PostgreSQL normalize correctly."""
    profile = analyze_resume(messy_resume_doc)
    assert "Node.js" in profile.skills
    assert "NodeJS" not in profile.skills
    assert "PostgreSQL" in profile.skills
    assert "Postgres" not in profile.skills

def test_6_experience_extraction(standard_resume_doc):
    """Verify job entries extract role, company, responsibilities, and technologies."""
    profile = analyze_resume(standard_resume_doc)
    assert len(profile.experience) == 2

    # Senior role
    sr_exp = profile.experience[0]
    assert "Senior Software Engineer" in sr_exp.role
    assert "TechCorp" in sr_exp.company
    assert "FastAPI" in sr_exp.technologies
    assert "Docker" in sr_exp.technologies

    # Junior/mid role
    se_exp = profile.experience[1]
    assert "Software Engineer" in se_exp.role
    assert "DevWorks" in se_exp.company
    assert "React" in se_exp.technologies
    assert "PostgreSQL" in se_exp.technologies

def test_7_date_normalization():
    """Verify start and end dates normalize to consistent format."""
    s_d, e_d, is_cur, dur = parse_date_range("Jan 2023 - Present")
    assert s_d == "Jan 2023"
    assert e_d == "Present"
    assert is_cur is True

    s_d2, e_d2, is_cur2, dur2 = parse_date_range("Jun 2020 - Dec 2022")
    assert s_d2 == "Jun 2020"
    assert e_d2 == "Dec 2022"
    assert is_cur2 is False

    s_d3, e_d3, is_cur3, dur3 = parse_date_range("2022 - 2024")
    assert s_d3 == "2022"
    assert e_d3 == "2024"

def test_8_present_current_role_handling(standard_resume_doc):
    """Verify is_current=True and end_date='Present' for current position."""
    profile = analyze_resume(standard_resume_doc)
    curr_job = next(e for e in profile.experience if "Senior Software Engineer" in (e.role or ""))
    assert curr_job.is_current is True
    assert curr_job.end_date == "Present"

def test_9_duration_calculation(standard_resume_doc):
    """Verify duration in months is computed for experience entries."""
    profile = analyze_resume(standard_resume_doc)
    past_job = next(e for e in profile.experience if "DevWorks" in (e.company or ""))
    # Jun 2020 to Dec 2022 = 2 years 6 months = 30 months
    assert past_job.duration_months == 30.0

def test_10_education_extraction(standard_resume_doc):
    """Verify degree, major, institution, dates, and GPA are extracted."""
    profile = analyze_resume(standard_resume_doc)
    assert len(profile.education) >= 1
    edu = profile.education[0]
    assert "Bachelor of Science" in edu.degree
    assert edu.field_of_study == "Computer Science"
    assert "Tech University" in edu.institution
    assert edu.grade_or_gpa == "3.8/4.0"

def test_11_certifications_extraction(standard_resume_doc):
    """Verify certification name, issuer, and issue date are extracted."""
    profile = analyze_resume(standard_resume_doc)
    assert len(profile.certifications) >= 1
    cert = profile.certifications[0]
    assert "AWS Certified Solutions Architect" in cert.name
    assert "Amazon Web Services (AWS)" in cert.issuer
    assert cert.date == "Mar 2022"

def test_12_projects_extraction(standard_resume_doc):
    """Verify project title, description, and technologies are extracted."""
    profile = analyze_resume(standard_resume_doc)
    assert len(profile.projects) >= 1
    proj = profile.projects[0]
    assert "CloudSync Engine" in proj.name
    assert "Python" in proj.technologies
    assert "Redis" in proj.technologies

def test_13_provenance_and_evidence(standard_resume_doc):
    """Verify all entities have valid Evidence objects with page and section provenance."""
    profile = analyze_resume(standard_resume_doc)
    assert len(profile.evidence) > 0
    for ev in profile.evidence:
        assert isinstance(ev, Evidence)
        assert ev.source_text
        assert ev.source_section
        assert ev.page_number >= 1
        assert 0.0 <= ev.confidence_score <= 1.0

def test_14_unfamiliar_technical_terms_preservation(messy_resume_doc):
    """Verify unfamiliar terms (e.g. CustomDSL) in skills section are preserved as other_skill."""
    profile = analyze_resume(messy_resume_doc)
    assert "CustomDSL" in profile.skills
    unfam_skill = next((s for s in profile.skill_details if s.name == "CustomDSL"), None)
    assert unfam_skill is not None
    assert unfam_skill.category == "other_skill"

def test_15_messy_and_non_standard_headings(messy_resume_doc):
    """Verify messy headings (Skills & Technologies, Employment History, etc.) map to canonical sections."""
    profile = analyze_resume(messy_resume_doc)
    assert "skills" in profile.sections
    assert "experience" in profile.sections
    assert "education" in profile.sections
    assert "projects" in profile.sections
    assert "certifications" in profile.sections

def test_16_two_column_resume_layout(two_column_resume_doc):
    """Verify two-column layout preserves text across columns without losing sections or content."""
    profile = analyze_resume(two_column_resume_doc)
    assert profile.name == "Samantha Reed"
    assert profile.email == "samantha.reed@domain.com"
    assert "skills" in profile.sections
    assert "experience" in profile.sections
    assert "Python" in profile.skills
    assert "Java" in profile.skills
    assert len(profile.experience) >= 1
    assert "Global Logistics" in profile.experience[0].company

def test_17_false_positive_protection_aspirational(messy_resume_doc):
    """Verify aspirational phrases ('Interested in learning Rust') do not credit Rust as an active skill."""
    profile = analyze_resume(messy_resume_doc)
    skills_lower = [s.lower() for s in profile.skills]
    assert "rust" not in skills_lower
    assert "webassembly" not in skills_lower

def test_18_analyzer_determinism(standard_resume_doc):
    """Verify analyze_resume is deterministic and idempotent across repeated runs."""
    res1 = analyze_resume(standard_resume_doc, candidate_id="test_cand")
    res2 = analyze_resume(standard_resume_doc, candidate_id="test_cand")

    assert res1.name == res2.name
    assert res1.email == res2.email
    assert res1.skills == res2.skills
    assert res1.technologies == res2.technologies
    assert len(res1.experience) == len(res2.experience)
    for i in range(len(res1.experience)):
        assert res1.experience[i].role == res2.experience[i].role
        assert res1.experience[i].company == res2.experience[i].company
        assert res1.experience[i].start_date == res2.experience[i].start_date
        assert res1.experience[i].end_date == res2.experience[i].end_date
    assert len(res1.education) == len(res2.education)
    assert len(res1.certifications) == len(res2.certifications)
    assert len(res1.projects) == len(res2.projects)

def test_19_prose_resume_without_sections():
    """Verify analyzer safely handles documents without structural sections."""
    doc = parse_document(FIXTURES_DIR / "no_sections_document.pdf")
    profile = analyze_resume(doc)
    assert profile.candidate_id is not None
    assert isinstance(profile.skills, list)
    assert isinstance(profile.experience, list)
    assert isinstance(profile.education, list)

