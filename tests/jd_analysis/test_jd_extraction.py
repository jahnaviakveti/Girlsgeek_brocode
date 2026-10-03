import pytest
import sys
from pathlib import Path

# Ensure backend is on sys.path
backend_path = Path(__file__).resolve().parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.services.document_parser import parse_document
from app.services.jd_analyzer import analyze_jd
from app.schemas.domain import RequirementCategory, RequirementPriority

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "test_fixtures"

def test_root_level_jd_analysis_smoke():
    pdf_path = FIXTURES_DIR / "jd_standard_sample.pdf"
    doc = parse_document(pdf_path)
    jd = analyze_jd(doc)

    assert len(jd.requirements) > 0
    categories = {r.category for r in jd.requirements}
    assert RequirementCategory.SKILL in categories
    assert RequirementCategory.EXPERIENCE in categories
    assert RequirementCategory.EDUCATION in categories
