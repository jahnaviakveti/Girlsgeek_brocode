import pytest
from pathlib import Path
from app.services.document_parser import DocumentParser, parse_document, normalize_text, SectionDetector
from app.core.exceptions import (
    DocumentNotFoundError,
    InvalidPDFError,
    EmptyPDFError,
    CorruptPDFError,
    NoTextExtractedError,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "test_fixtures"

def test_1_basic_extraction():
    pdf_path = FIXTURES_DIR / "basic_single_page.pdf"
    doc = parse_document(pdf_path)

    assert doc.filename == "basic_single_page.pdf"
    assert doc.page_count == 1
    assert "Engineering Document" in doc.raw_text
    assert "Engineering Document" in doc.normalized_text
    assert len(doc.pages) == 1
    assert len(doc.pages[0].blocks) > 0

    # Verify block bounding box coordinates exist
    first_block = doc.pages[0].blocks[0]
    assert first_block.bbox is not None
    assert len(first_block.bbox) == 4
    assert first_block.page_number == 1

def test_2_page_preservation():
    pdf_path = FIXTURES_DIR / "multipage_document.pdf"
    doc = parse_document(pdf_path)

    assert doc.page_count == 3
    assert len(doc.pages) == 3
    for idx, page in enumerate(doc.pages, start=1):
        assert page.page_number == idx
        assert f"Page {idx}" in page.raw_text
        assert f"Page {idx}" in page.normalized_text

def test_3_raw_normalized_separation():
    pdf_path = FIXTURES_DIR / "unusual_whitespace.pdf"
    doc = parse_document(pdf_path)

    # Raw text preserves irregular tabs/multiple spaces
    assert "\t" in doc.raw_text or "   " in doc.raw_text

    # Normalized text has cleaned tabs and excessive spaces
    assert "\t" not in doc.normalized_text
    assert "    " not in doc.normalized_text
    assert doc.raw_text != doc.normalized_text

    # Both representations remain available and non-empty
    assert len(doc.raw_text) > 0
    assert len(doc.normalized_text) > 0

def test_4_whitespace_normalization():
    pdf_path = FIXTURES_DIR / "unusual_whitespace.pdf"
    doc = parse_document(pdf_path)

    # De-hyphenation test: 'hyphen-\nnation' -> 'hyphenation'
    assert "hyphenation" in doc.normalized_text
    assert "hyphen-\nnation" not in doc.normalized_text

    # Excessive blank lines collapsed: no triple newlines
    assert "\n\n\n" not in doc.normalized_text

    # Core content remains intact
    assert "Final paragraph after excess blank lines." in doc.normalized_text

def test_5_section_detection():
    pdf_path = FIXTURES_DIR / "sections_document.pdf"
    doc = parse_document(pdf_path)

    # Standard sections are recognized and mapped to canonical names
    assert "skills" in doc.sections
    assert "experience" in doc.sections
    assert "education" in doc.sections
    assert "projects" in doc.sections

    # Section texts contain their respective content
    assert "Python, JavaScript, SQL, Docker" in doc.sections["skills"]
    assert "Software Engineering Intern" in doc.sections["experience"]
    assert "Computer Science" in doc.sections["education"]
    assert "distributed event queue" in doc.sections["projects"]

    # Verify detected_sections list with provenance
    assert len(doc.detected_sections) >= 4
    skills_sec = next(s for s in doc.detected_sections if s.canonical_name == "skills")
    assert skills_sec.title == "TECHNICAL SKILLS"
    assert skills_sec.start_page == 1

def test_6_heading_normalization():
    # Verify variations map to the same canonical section name
    variations = [
        ("TECHNICAL SKILLS", "skills"),
        ("Technical Skills", "skills"),
        ("technical skills", "skills"),
        ("1. Work Experience:", "experience"),
        ("• Professional Experience", "experience"),
        ("ACADEMIC BACKGROUND", "education"),
        ("Key Projects:", "projects"),
    ]
    for raw, expected in variations:
        assert SectionDetector.normalize_heading(raw) == expected

def test_7_missing_and_unusual_sections():
    # Test document with NO section headings (pure prose)
    doc_no_sec = parse_document(FIXTURES_DIR / "no_sections_document.pdf")
    assert doc_no_sec.sections == {}
    assert len(doc_no_sec.detected_sections) == 0
    assert "This is an essay with no headings." in doc_no_sec.normalized_text

    # Test document with unusual headings (non-standard)
    doc_unusual = parse_document(FIXTURES_DIR / "unusual_headings_document.pdf")
    # Heading normalizer generates clean snake_case identifiers without crashing
    assert "toolbox" in doc_unusual.sections or len(doc_unusual.detected_sections) > 0
    assert "where_i_studied" in doc_unusual.sections or len(doc_unusual.detected_sections) > 0

def test_8_invalid_and_corrupt_pdf():
    # Corrupt PDF structure
    with pytest.raises(CorruptPDFError):
        parse_document(FIXTURES_DIR / "corrupt_damaged.pdf")

    # Empty 0-byte file
    with pytest.raises(EmptyPDFError):
        parse_document(FIXTURES_DIR / "zero_byte_empty.pdf")

    # PDF with pages but no extractable text
    with pytest.raises(NoTextExtractedError):
        parse_document(FIXTURES_DIR / "empty_pages_no_text.pdf")

    # Non-PDF invalid file
    dummy_text_file = FIXTURES_DIR / "not_a_pdf.txt"
    dummy_text_file.write_text("Just plain text, not a PDF.")
    try:
        with pytest.raises(InvalidPDFError):
            parse_document(dummy_text_file)
    finally:
        if dummy_text_file.exists():
            dummy_text_file.unlink()

def test_9_missing_file():
    with pytest.raises(DocumentNotFoundError):
        parse_document(FIXTURES_DIR / "non_existent_file.pdf")

def test_10_multipage_provenance():
    pdf_path = FIXTURES_DIR / "multipage_document.pdf"
    doc = parse_document(pdf_path)

    # Page 1 provenance
    page_1 = doc.pages[0]
    assert page_1.page_number == 1
    assert "Content for Page 1" in page_1.raw_text
    assert "Content for Page 2" not in page_1.raw_text

    # Page 2 provenance
    page_2 = doc.pages[1]
    assert page_2.page_number == 2
    assert "Content for Page 2" in page_2.raw_text
    assert "Content for Page 1" not in page_2.raw_text

    # Page 3 provenance
    page_3 = doc.pages[2]
    assert page_3.page_number == 3
    assert "Content for Page 3" in page_3.raw_text

    # Verify block provenance links to page number
    for block in page_2.blocks:
        assert block.page_number == 2

def test_11_two_column_layout():
    pdf_path = FIXTURES_DIR / "two_column_layout.pdf"
    doc = parse_document(pdf_path)

    assert doc.page_count == 1
    blocks = doc.pages[0].blocks
    assert len(blocks) >= 2

    # Left column block: x0 ~ 50
    left_block = next((b for b in blocks if "Column 1" in b.text), None)
    assert left_block is not None
    assert left_block.bbox[0] < 200

    # Right column block: x0 ~ 320
    right_block = next((b for b in blocks if "Column 2" in b.text), None)
    assert right_block is not None
    assert right_block.bbox[0] > 250
