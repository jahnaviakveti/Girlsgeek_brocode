import pytest
from pathlib import Path
from app.services.document_parser import parse_document
from app.services.resume_analyzer import analyze_resume

# Find the resume. The user's downloaded CV is the likely candidate.
# Let's search common paths.
POSSIBLE_PATHS = [
    Path("/Users/jahnaviakveti/Downloads/Jonath_Jimmi_CVv2.pdf"),
    Path(__file__).parent.parent.parent / "Jonath_Jimmi_CVv2.pdf",
]

def get_resume_doc():
    for p in POSSIBLE_PATHS:
        if p.exists():
            return parse_document(p)
    # If not found, skip tests or fail
    pytest.skip("Could not find the attached resume for regression testing.")

@pytest.fixture(scope="module")
def resume_profile():
    doc = get_resume_doc()
    return analyze_resume(doc)

def test_1_education_not_split(resume_profile):
    """Test 1: The education section produces exactly ONE education record"""
    assert len(resume_profile.education) == 1
    edu = resume_profile.education[0]
    assert "Manipal Institute of Technology" in edu.institution
    assert "B.Tech" in edu.degree
    assert "Information Technology" in edu.field_of_study
    assert edu.start_date is not None
    assert edu.end_date is not None

def test_2_quibc_project(resume_profile):
    """Test 2: QUIBC produces exactly ONE project record."""
    quibc_projects = [p for p in resume_profile.projects if "QUIBC" in p.name]
    assert len(quibc_projects) == 1

def test_3_project_repo_link_not_standalone(resume_profile):
    """Test 3: 'Project Repo Link' does NOT produce a separate project/evidence record."""
    repo_link_projects = [p for p in resume_profile.projects if "Project Repo Link" in p.name or "Repo Link" in p.name]
    assert len(repo_link_projects) == 0

def test_4_supplychainiq_project(resume_profile):
    """Test 4: SupplyChainIQ produces exactly ONE project record."""
    supply_projects = [p for p in resume_profile.projects if "SupplyChainIQ" in p.name]
    assert len(supply_projects) == 1

def test_5_supplychainiq_repo_link(resume_profile):
    """Test 5: Its 'Project Repo Link' does NOT produce another project."""
    # Verified by test 3

def test_6_robust_har_project(resume_profile):
    """Test 6: Robust HAR via Federated Learning & Differential Privacy produces exactly ONE project record."""
    har_projects = [p for p in resume_profile.projects if "Robust HAR" in p.name]
    assert len(har_projects) == 1

def test_7_har_repo_link(resume_profile):
    """Test 7: Its 'Project Repo Link' does NOT produce another project."""
    # Verified by test 3

def test_8_video_demo_link(resume_profile):
    """Test 8: 'Video Demo Link' under a technical activity does not become a separate activity (project)."""
    video_links = [p for p in resume_profile.projects if "Video Demo Link" in p.name]
    assert len(video_links) == 0

def test_9_doi(resume_profile):
    """Test 9: 'DOI' associated with a paper presentation does not become a separate activity (project)."""
    dois = [p for p in resume_profile.projects if "DOI" == p.name.strip() or "DOI:" in p.name]
    assert len(dois) == 0
