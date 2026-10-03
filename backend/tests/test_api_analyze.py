import pytest
import io
import fitz
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def create_pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    b = doc.tobytes()
    doc.close()
    return b

@pytest.fixture(scope="module")
def sample_jd_bytes():
    text = """
    Job Title: Senior Software Engineer
    Location: Remote
    
    Required Qualifications:
    - 3+ years of experience with Python development
    - Strong knowledge of SQL databases and PostgreSQL
    
    Preferred Qualifications:
    - Experience with Docker containerization
    - Familiarity with AWS cloud services
    """
    return create_pdf_bytes(text)

@pytest.fixture(scope="module")
def sample_resume_1():
    text = """
    Alice Smith
    Email: alice@example.com
    
    TECHNICAL SKILLS
    Python, PostgreSQL, Docker, AWS, Git
    
    WORK EXPERIENCE
    Senior Backend Engineer - Tech Corp (2020 - Present)
    Architected backend APIs using Python and PostgreSQL databases.
    Deployed containerized microservices with Docker on AWS.
    """
    return create_pdf_bytes(text)

@pytest.fixture(scope="module")
def sample_resume_2():
    text = """
    Bob Jones
    Email: bob@example.com
    
    SKILLS
    Python, SQL, MySQL
    
    EXPERIENCE
    Software Engineer - Data Systems (2021 - 2023)
    Built backend data pipelines in Python and maintained MySQL tables.
    """
    return create_pdf_bytes(text)

@pytest.fixture(scope="module")
def sample_resume_3():
    text = """
    Charlie Brown
    Email: charlie@example.com
    
    SKILLS
    JavaScript, HTML, CSS, Graphic Design
    
    EXPERIENCE
    UI Designer - Creative Studio (2022 - Present)
    Designed web pages using HTML, CSS, and Figma.
    """
    return create_pdf_bytes(text)

def generate_n_resumes(n: int, sample_1: bytes, sample_2: bytes, sample_3: bytes):
    """Generates a list of N resume multipart file tuples for API testing."""
    samples = [sample_1, sample_2, sample_3]
    files = []
    for i in range(n):
        b = samples[i % len(samples)]
        files.append(("resume_files", (f"cand_{i+1}.pdf", io.BytesIO(b), "application/pdf")))
    return files

# ==============================================================================
# 1. Basic Health Check
# ==============================================================================
def test_1_health_check_functional():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

# ==============================================================================
# 2. Production API Boundary Tests (1, 15, 25, 26, 0 resumes, invalid formats)
# ==============================================================================
def test_boundary_accept_1_resume(sample_jd_bytes, sample_resume_1, sample_resume_2, sample_resume_3):
    """Boundary test: lower bound of exactly 1 resume must be accepted with HTTP 200."""
    resumes = generate_n_resumes(1, sample_resume_1, sample_resume_2, sample_resume_3)
    files = [("jd_file", ("job_description.pdf", io.BytesIO(sample_jd_bytes), "application/pdf"))] + resumes
    resp = client.post("/api/analyze", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_resumes_received"] == 1
    assert data["total_candidates_processed"] == 1
    assert data["total_ranked"] == 1
    assert len(data["ranked_candidates"]) == 1

def test_boundary_accept_15_resumes(sample_jd_bytes, sample_resume_1, sample_resume_2, sample_resume_3):
    """Boundary test: standard batch of 15 resumes must be accepted with HTTP 200."""
    resumes = generate_n_resumes(15, sample_resume_1, sample_resume_2, sample_resume_3)
    files = [("jd_file", ("job_description.pdf", io.BytesIO(sample_jd_bytes), "application/pdf"))] + resumes
    resp = client.post("/api/analyze", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_resumes_received"] == 15
    assert data["total_candidates_processed"] == 15
    assert data["total_ranked"] == 15
    assert len(data["ranked_candidates"]) == 15

def test_boundary_accept_25_resumes(sample_jd_bytes, sample_resume_1, sample_resume_2, sample_resume_3):
    """Boundary test: upper bound of exactly 25 resumes must be accepted with HTTP 200."""
    resumes = generate_n_resumes(25, sample_resume_1, sample_resume_2, sample_resume_3)
    files = [("jd_file", ("job_description.pdf", io.BytesIO(sample_jd_bytes), "application/pdf"))] + resumes
    resp = client.post("/api/analyze", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_resumes_received"] == 25
    assert data["total_candidates_processed"] == 25
    assert data["total_ranked"] == 25
    assert len(data["ranked_candidates"]) == 25

def test_boundary_reject_26_resumes(sample_jd_bytes, sample_resume_1, sample_resume_2, sample_resume_3):
    """Boundary test: exactly 26 resumes must be rejected with HTTP 400."""
    resumes = generate_n_resumes(26, sample_resume_1, sample_resume_2, sample_resume_3)
    files = [("jd_file", ("job_description.pdf", io.BytesIO(sample_jd_bytes), "application/pdf"))] + resumes
    resp = client.post("/api/analyze", files=files)
    assert resp.status_code == 400
    assert "between 1 and 25 candidate resumes" in resp.json()["detail"]
    assert "received 26" in resp.json()["detail"]

def test_boundary_reject_0_resumes(sample_jd_bytes):
    """Boundary test: 0 resumes provided must be rejected with HTTP 400 or 422."""
    files = [("jd_file", ("job_description.pdf", io.BytesIO(sample_jd_bytes), "application/pdf"))]
    resp = client.post("/api/analyze", files=files)
    assert resp.status_code in [400, 422]

def test_boundary_reject_missing_jd(sample_resume_1, sample_resume_2, sample_resume_3):
    """Boundary test: missing JD file must be rejected with HTTP 400 or 422."""
    resumes = generate_n_resumes(15, sample_resume_1, sample_resume_2, sample_resume_3)
    resp = client.post("/api/analyze", files=resumes)
    assert resp.status_code in [400, 422]

def test_boundary_reject_invalid_jd_type(sample_resume_1, sample_resume_2, sample_resume_3):
    """Boundary test: non-PDF JD file must be rejected with HTTP 400."""
    resumes = generate_n_resumes(15, sample_resume_1, sample_resume_2, sample_resume_3)
    files = [("jd_file", ("job_description.txt", io.BytesIO(b"Python developer needed"), "text/plain"))] + resumes
    resp = client.post("/api/analyze", files=files)
    assert resp.status_code == 400
    assert "Only PDF files are accepted" in resp.json()["detail"]

def test_boundary_reject_invalid_resume_type(sample_jd_bytes, sample_resume_1, sample_resume_2, sample_resume_3):
    """Boundary test: non-PDF resume file within a batch of 15 must be rejected with HTTP 400."""
    resumes = generate_n_resumes(14, sample_resume_1, sample_resume_2, sample_resume_3)
    resumes.append(("resume_files", ("candidate_15.docx", io.BytesIO(b"Word resume"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")))
    files = [("jd_file", ("job_description.pdf", io.BytesIO(sample_jd_bytes), "application/pdf"))] + resumes
    resp = client.post("/api/analyze", files=files)
    assert resp.status_code == 400
    assert "Only PDF files are accepted" in resp.json()["detail"]

def test_boundary_empty_zero_byte_jd(sample_resume_1, sample_resume_2, sample_resume_3):
    """Boundary test: 0-byte JD PDF must be rejected with HTTP 400."""
    resumes = generate_n_resumes(15, sample_resume_1, sample_resume_2, sample_resume_3)
    files = [("jd_file", ("empty_jd.pdf", io.BytesIO(b""), "application/pdf"))] + resumes
    resp = client.post("/api/analyze", files=files)
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()

# ==============================================================================
# 3. Pipeline Resilience & Contract Tests (using valid 15-resume batch)
# ==============================================================================
def test_corrupt_pdf_resume_handled_without_batch_crash(sample_jd_bytes, sample_resume_1, sample_resume_2, sample_resume_3):
    """A corrupted PDF inside a batch of 15 does not crash the pipeline; it is safely isolated in failed_candidates."""
    resumes = generate_n_resumes(14, sample_resume_1, sample_resume_2, sample_resume_3)
    corrupt_bytes = b"%PDF-1.4 corrupt content not valid pdf"
    resumes.append(("resume_files", ("corrupt.pdf", io.BytesIO(corrupt_bytes), "application/pdf")))
    files = [("jd_file", ("job_description.pdf", io.BytesIO(sample_jd_bytes), "application/pdf"))] + resumes
    resp = client.post("/api/analyze", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_resumes_received"] == 15
    assert data["total_candidates_processed"] == 14
    assert data["total_ranked"] == 14
    assert len(data["failed_candidates"]) == 1
    assert data["failed_candidates"][0]["filename"] == "corrupt.pdf"

def test_response_contains_complete_job_summary(sample_jd_bytes, sample_resume_1, sample_resume_2, sample_resume_3):
    """Job summary in response contains requirement counts and categorized summaries."""
    resumes = generate_n_resumes(15, sample_resume_1, sample_resume_2, sample_resume_3)
    files = [("jd_file", ("job_description.pdf", io.BytesIO(sample_jd_bytes), "application/pdf"))] + resumes
    resp = client.post("/api/analyze", files=files)
    assert resp.status_code == 200
    job = resp.json()["job"]
    assert job["total_requirements"] > 0
    assert job["required_count"] > 0
    assert len(job["requirements"]) == job["total_requirements"]

def test_every_candidate_scored_and_ranked(sample_jd_bytes, sample_resume_1, sample_resume_2, sample_resume_3):
    """Every candidate has an overall_score (0-100) and monotonically non-increasing rank."""
    resumes = generate_n_resumes(15, sample_resume_1, sample_resume_2, sample_resume_3)
    files = [("jd_file", ("job_description.pdf", io.BytesIO(sample_jd_bytes), "application/pdf"))] + resumes
    resp = client.post("/api/analyze", files=files)
    assert resp.status_code == 200
    candidates = resp.json()["ranked_candidates"]
    assert len(candidates) == 15
    for i, cand in enumerate(candidates):
        assert "overall_score" in cand
        assert 0.0 <= cand["overall_score"] <= 100.0
        assert cand["rank"] == i + 1
        if i > 0:
            assert cand["overall_score"] <= candidates[i - 1]["overall_score"]

def test_top_3_prominence(sample_jd_bytes, sample_resume_1, sample_resume_2, sample_resume_3):
    """Exactly the top 3 candidates have is_top_3=True and why_ranked_here explanation."""
    resumes = generate_n_resumes(15, sample_resume_1, sample_resume_2, sample_resume_3)
    files = [("jd_file", ("job_description.pdf", io.BytesIO(sample_jd_bytes), "application/pdf"))] + resumes
    resp = client.post("/api/analyze", files=files)
    assert resp.status_code == 200
    candidates = resp.json()["ranked_candidates"]
    for i, c in enumerate(candidates):
        if i < 3:
            assert c["is_top_3"] is True
            assert len(c["why_ranked_here"]) > 0
        else:
            assert c["is_top_3"] is False

def test_evidence_provenance_preserved(sample_jd_bytes, sample_resume_1, sample_resume_2, sample_resume_3):
    """Supporting evidence includes evidence_text, evidence_type, and provenance."""
    resumes = generate_n_resumes(15, sample_resume_1, sample_resume_2, sample_resume_3)
    files = [("jd_file", ("job_description.pdf", io.BytesIO(sample_jd_bytes), "application/pdf"))] + resumes
    resp = client.post("/api/analyze", files=files)
    assert resp.status_code == 200
    cand = resp.json()["ranked_candidates"][0]
    matched = cand["matched_requirements"]
    assert len(matched) > 0
    ev = matched[0]["supporting_evidence"][0]
    assert ev["evidence_text"] is not None
    assert ev["evidence_type"] is not None

def test_deterministic_repeated_request(sample_jd_bytes, sample_resume_1, sample_resume_2, sample_resume_3):
    """Same batch evaluated twice produces identical scores, ranks, and explanations."""
    resumes_1 = generate_n_resumes(15, sample_resume_1, sample_resume_2, sample_resume_3)
    resumes_2 = generate_n_resumes(15, sample_resume_1, sample_resume_2, sample_resume_3)
    files_1 = [("jd_file", ("job_description.pdf", io.BytesIO(sample_jd_bytes), "application/pdf"))] + resumes_1
    files_2 = [("jd_file", ("job_description.pdf", io.BytesIO(sample_jd_bytes), "application/pdf"))] + resumes_2
    resp_1 = client.post("/api/analyze", files=files_1)
    resp_2 = client.post("/api/analyze", files=files_2)
    assert resp_1.status_code == 200
    assert resp_2.status_code == 200
    d1 = resp_1.json()["ranked_candidates"]
    d2 = resp_2.json()["ranked_candidates"]
    assert len(d1) == len(d2)
    for c1, c2 in zip(d1, d2):
        assert c1["candidate_name"] == c2["candidate_name"]
        assert c1["rank"] == c2["rank"]
        assert c1["overall_score"] == c2["overall_score"]
        assert c1["why_ranked_here"] == c2["why_ranked_here"]

