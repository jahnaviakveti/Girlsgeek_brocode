import io
from fastapi.testclient import TestClient
from app.main import app
from app.schemas.api import AnalysisResponse

client = TestClient(app)

def test_api_analyze_includes_bias_audit(monkeypatch):
    """
    Verifies that the /api/analyze endpoint produces a valid JDBiasAudit structure.
    """
    # Create a dummy mock PDF file content
    dummy_pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    
    # We can test with 15 dummy files using mocked pipeline to check route serialization
    from app.schemas.api import JobSummary, JobRequirementSummary
    from app.schemas.bias import JDBiasAudit, BiasFlag, BiasCategory, BiasSeverity
    from app.schemas.explanation import CandidateExplanation
    
    fake_bias = JDBiasAudit(
        inclusivity_score=85,
        inclusivity_grade="A",
        total_flags=1,
        flags=[
            BiasFlag(
                id="flag_1",
                category=BiasCategory.GENDER_CODED,
                severity=BiasSeverity.MEDIUM,
                matched_text="rockstar",
                context_snippet="Seeking a rockstar developer",
                explanation="Superstar jargon test",
                inclusive_alternative="Skilled engineer"
            )
        ],
        summary="Test summary",
        bias_free=False
    )
    
    fake_response = AnalysisResponse(
        job=JobSummary(
            job_id="job_test",
            job_title="Test Software Engineer",
            total_requirements=1,
            required_count=1,
            preferred_count=0,
            requirements=[
                JobRequirementSummary(
                    id="req_1",
                    requirement_text="Python",
                    category="skill",
                    priority="required",
                    extracted_keywords=["Python"]
                )
            ],
            bias_audit=fake_bias
        ),
        total_resumes_received=15,
        total_candidates_processed=15,
        total_ranked=15,
        ranked_candidates=[],
        failed_candidates=[]
    )
    
    # Mock pipeline process_batch
    monkeypatch.setattr(
        "app.api.routes.analyze.ShortlistingPipeline.process_batch",
        lambda self, jd_path, resume_paths: fake_response
    )
    
    # Submit 1 JD and 15 dummy resumes
    files = [("jd_file", ("test_jd.pdf", dummy_pdf, "application/pdf"))]
    for i in range(15):
        files.append(("resume_files", (f"resume_{i}.pdf", dummy_pdf, "application/pdf")))
        
    res = client.post("/api/analyze", files=files)
    assert res.status_code == 200
    data = res.json()
    assert "job" in data
    assert "bias_audit" in data["job"]
    assert data["job"]["bias_audit"]["inclusivity_score"] == 85
    assert data["job"]["bias_audit"]["inclusivity_grade"] == "A"
    assert len(data["job"]["bias_audit"]["flags"]) == 1
    assert data["job"]["bias_audit"]["flags"][0]["matched_text"] == "rockstar"
