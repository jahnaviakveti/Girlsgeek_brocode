import pytest
import sys
from pathlib import Path

# Ensure backend is on sys.path
backend_path = Path(__file__).resolve().parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.services.document_parser import parse_document
from app.services.resume_analyzer import analyze_resume
from app.schemas.candidate import CandidateProfile

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "test_fixtures"

def test_root_level_resume_analysis_smoke():
    pdf_path = FIXTURES_DIR / "resume_standard_sample.pdf"
    doc = parse_document(pdf_path)
    profile = analyze_resume(doc)

    assert isinstance(profile, CandidateProfile)
    assert profile.name == "Jane Doe"
    assert profile.email == "jane.doe@example.com"
    assert len(profile.skills) > 0
    assert len(profile.experience) > 0
    assert len(profile.education) > 0
    assert len(profile.certifications) > 0
    assert len(profile.projects) > 0
    assert len(profile.evidence) > 0
