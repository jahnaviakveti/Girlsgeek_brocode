import pytest
import sys
from pathlib import Path

# Ensure backend is on sys.path
backend_path = Path(__file__).resolve().parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.services.document_parser import parse_document
from app.core.exceptions import DocumentNotFoundError

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "test_fixtures"

def test_root_level_parsing_smoke():
    pdf_path = FIXTURES_DIR / "basic_single_page.pdf"
    doc = parse_document(pdf_path)
    assert doc.filename == "basic_single_page.pdf"
    assert doc.page_count == 1
    assert "Engineering Document" in doc.raw_text
