import io
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import get_db, SessionLocal
from app.db.repository import Repository

client = TestClient(app)

def create_simple_pdf_bytes(text: str) -> bytes:
    """Helper to generate minimal valid PDF bytes with PyMuPDF."""
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes

def test_resume_upload_error_handling_non_pdf():
    """Regression test: Non-PDF files must return 400 with explicit error message."""
    resp = client.post(
        "/api/coach/resume",
        files={"resume_file": ("resume.txt", b"plain text resume content", "text/plain")}
    )
    assert resp.status_code == 400
    data = resp.json()
    assert "detail" in data
    assert "Only PDF files are supported" in data["detail"]

def test_resume_upload_error_handling_empty_pdf():
    """Regression test: Empty 0-byte PDF must return 400 with explicit error message."""
    resp = client.post(
        "/api/coach/resume",
        files={"resume_file": ("empty_resume.pdf", b"", "application/pdf")}
    )
    assert resp.status_code == 400
    data = resp.json()
    assert "detail" in data
    assert "Uploaded PDF is empty (0 bytes)" in data["detail"]

def test_resume_upload_error_handling_corrupted_pdf():
    """Regression test: Corrupted PDF bytes must return 400 with parsing error message rather than hanging."""
    corrupted_bytes = b"%PDF-1.4\ncorrupted content that cannot be parsed as a real PDF\n%%EOF"
    resp = client.post(
        "/api/coach/resume",
        files={"resume_file": ("corrupted.pdf", corrupted_bytes, "application/pdf")}
    )
    assert resp.status_code == 400
    data = resp.json()
    assert "detail" in data
    assert "Document parsing error" in data["detail"]

def test_resume_upload_error_does_not_modify_vault_or_twins():
    """Regression test: Failed uploads do not inject invalid records into Evidence Vault or DB."""
    from app.db.models import CandidateProfileRecord, EvidenceRecord
    db = SessionLocal()
    try:
        initial_cand_count = db.query(CandidateProfileRecord).count()
        initial_ev_count = db.query(EvidenceRecord).count()

        # Attempt corrupted upload
        resp = client.post(
            "/api/coach/resume",
            files={"resume_file": ("bad.pdf", b"corrupted garbage", "application/pdf")}
        )
        assert resp.status_code == 400

        # Verify candidate and evidence counts did not change
        assert db.query(CandidateProfileRecord).count() == initial_cand_count
        assert db.query(EvidenceRecord).count() == initial_ev_count
    finally:
        db.close()

def test_resume_upload_success_returns_twin_and_vault():
    """Regression test: Valid PDF returns 200, career twin, and evidence vault cleanly."""
    valid_text = """
    Jane Developer
    Email: jane.dev@example.com
    Phone: (555) 234-5678
    
    SKILLS
    Python, TypeScript, React, Docker, SQL
    
    EXPERIENCE
    Full Stack Engineer at Tech Innovators (Jan 2021 - Present)
    - Built responsive web dashboards using React and TypeScript.
    - Designed Python microservices with Docker deployment.
    """
    pdf_bytes = create_simple_pdf_bytes(valid_text)
    resp = client.post(
        "/api/coach/resume",
        files={"resume_file": ("Jane_Developer_Resume.pdf", pdf_bytes, "application/pdf")}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "candidate_id" in data
    assert "career_twin" in data
    assert "evidence_vault" in data
    assert data["career_twin"]["name"] == "Jane Developer"
    assert data["evidence_vault"]["total_items"] > 0
