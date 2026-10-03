import pytest
import io
import fitz
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def create_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    b = doc.tobytes()
    doc.close()
    return b

def test_controlled_six_candidate_fixture():
    # 1. Job Description with required and preferred criteria
    jd_text = """
    Job Title: Lead Backend Engineer
    
    Required Qualifications:
    - 4+ years of professional experience in Python development
    - Deep knowledge of SQL databases and PostgreSQL
    
    Preferred Qualifications:
    - Experience with Docker containerization
    - Cloud experience with AWS architecture
    """
    jd_bytes = create_pdf(jd_text)

    # Candidate 1: Strong candidate (has all required + all preferred)
    c1_text = """
    Alice Walker
    Email: alice@example.com
    
    TECHNICAL SKILLS
    Python, PostgreSQL, Docker, AWS, Linux
    
    WORK EXPERIENCE
    Lead Software Engineer - Enterprise Cloud (2019 - Present)
    Designed and scaled high-throughput Python microservices backed by PostgreSQL.
    Containerized all applications using Docker and deployed onto AWS ECS.
    """
    c1_bytes = create_pdf(c1_text)

    # Candidate 2: Strong candidate missing one preferred (AWS)
    c2_text = """
    Brian Miller
    Email: brian@example.com
    
    TECHNICAL SKILLS
    Python, PostgreSQL, Docker, Git
    
    WORK EXPERIENCE
    Senior Software Engineer - FinTech Labs (2019 - Present)
    Implemented Python microservices with PostgreSQL databases.
    Maintained Docker compose staging environments locally.
    """
    c2_bytes = create_pdf(c2_text)

    # Candidate 3: Partial experience (Python + SQL, but short tenure / partial duration)
    c3_text = """
    Chloe Davis
    Email: chloe@example.com
    
    TECHNICAL SKILLS
    Python, PostgreSQL
    
    WORK EXPERIENCE
    Junior Developer - Startup Studio (2023 - 2024)
    Contributed Python scripts and wrote SQL queries against PostgreSQL.
    """
    c3_bytes = create_pdf(c3_text)

    # Candidate 4: Missing required (has Python, but completely missing SQL/PostgreSQL)
    c4_text = """
    David Evans
    Email: david@example.com
    
    TECHNICAL SKILLS
    Python, NumPy, Pandas, Data Analysis
    
    WORK EXPERIENCE
    Data Analyst - Analytics Corp (2020 - Present)
    Wrote Python data cleaning scripts for spreadsheet data.
    """
    c4_bytes = create_pdf(c4_text)

    # Candidate 5: Unrelated candidate (Frontend/Design only)
    c5_text = """
    Elena Rostova
    Email: elena@example.com
    
    SKILLS
    Figma, Adobe Photoshop, UI/UX Design, CSS
    
    EXPERIENCE
    Visual Designer - Creative Agency (2021 - Present)
    Crafted wireframes and UI mockups in Figma and Adobe Suite.
    """
    c5_bytes = create_pdf(c5_text)

    # Candidate 6: Aspirational / negated candidate
    c6_text = """
    Frank Wright
    Email: frank@example.com
    
    TECHNICAL SKILLS
    JavaScript, HTML
    
    EXPERIENCE
    Frontend Developer - Web Co (2021 - Present)
    Built frontend interfaces. Interested in learning Python in the future.
    Did not use PostgreSQL due to company preference for MongoDB.
    """
    c6_bytes = create_pdf(c6_text)

    import tempfile
    from pathlib import Path
    from app.services.pipeline import ShortlistingPipeline

    with tempfile.TemporaryDirectory(prefix="ctrl_fixture_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        jd_path = tmp_path / "lead_engineer_jd.pdf"
        jd_path.write_bytes(jd_bytes)

        resumes = [
            ("c1_alice.pdf", tmp_path / "c1_alice.pdf"),
            ("c2_brian.pdf", tmp_path / "c2_brian.pdf"),
            ("c3_chloe.pdf", tmp_path / "c3_chloe.pdf"),
            ("c4_david.pdf", tmp_path / "c4_david.pdf"),
            ("c5_elena.pdf", tmp_path / "c5_elena.pdf"),
            ("c6_frank.pdf", tmp_path / "c6_frank.pdf"),
        ]
        (tmp_path / "c1_alice.pdf").write_bytes(c1_bytes)
        (tmp_path / "c2_brian.pdf").write_bytes(c2_bytes)
        (tmp_path / "c3_chloe.pdf").write_bytes(c3_bytes)
        (tmp_path / "c4_david.pdf").write_bytes(c4_bytes)
        (tmp_path / "c5_elena.pdf").write_bytes(c5_bytes)
        (tmp_path / "c6_frank.pdf").write_bytes(c6_bytes)

        pipeline = ShortlistingPipeline.get_instance()
        response = pipeline.process_batch(jd_path, resumes)
        data = response.model_dump()

    # Structural Verifications
    assert data["total_resumes_received"] == 6
    assert data["total_candidates_processed"] == 6
    assert data["total_ranked"] == 6
    assert len(data["failed_candidates"]) == 0

    ranked = data["ranked_candidates"]
    scores = [c["overall_score"] for c in ranked]

    # Verification: Monotonically non-increasing ranking order
    for i in range(len(scores) - 1):
        assert scores[i] >= scores[i + 1]

    # Verification: Top 3 contains strong candidates
    top_3_names = [c["candidate_name"] for c in ranked[:3]]
    assert "Alice Walker" in top_3_names
    assert "Brian Miller" in top_3_names

    # Candidate 1 (Alice) must have highest score
    assert ranked[0]["candidate_name"] == "Alice Walker"
    assert ranked[0]["is_top_3"] is True
    assert ranked[0]["rank"] == 1
    assert "Ranked #1" in ranked[0]["why_ranked_here"]

    # Candidate 2 (Brian) ranks below Alice because missing AWS preferred
    assert ranked[1]["candidate_name"] == "Brian Miller"
    assert ranked[1]["overall_score"] < ranked[0]["overall_score"]

    # Candidate 5 (Elena) and Candidate 6 (Frank) should be lowest ranked
    bottom_names = [c["candidate_name"] for c in ranked[4:]]
    assert "Elena Rostova" in bottom_names or "Frank Wright" in bottom_names

    # Verification: Aspirational/negated phrases in Frank's CV did not award points for Python/PostgreSQL
    frank = next(c for c in ranked if c["candidate_name"] == "Frank Wright")
    assert frank["overall_score"] < 30.0

    # Verification: Provenance on top candidate
    alice = ranked[0]
    for req in alice["matched_requirements"]:
        assert len(req["supporting_evidence"]) > 0
        for ev in req["supporting_evidence"]:
            assert ev["evidence_text"]
            assert ev["evidence_type"]
