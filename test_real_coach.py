import asyncio
import os
from dotenv import load_dotenv

# Load env before importing services so config picks up AIPIPE_TOKEN
load_dotenv("backend/.env")

from app.services.coach.resume.service import ResumeCoachService
from app.schemas.resume_coach import ResumeCoachRequest

async def test_coach():
    service = ResumeCoachService()
    
    req = ResumeCoachRequest(
        user_id="test_user",
        candidate_id="test_candidate",
        job_description_id="job_123",
        requirement_id="req_123",
        resume_version_id="ver_123",
        gap_type="RESUME_VISIBILITY_GAP",
        requirement_text="Demonstrated experience with modern frontend frameworks, specifically React or Vue.",
        original_resume_text="Built user interfaces using HTML and CSS.",
        verified_evidence=[
            "Used React to build the frontend of the e-commerce platform.",
            "Built user interfaces using HTML and CSS."
        ]
    )
    
    response = await service.generate_rewrite(req)
    
    print(f"STATUS: {response.status}")
    print(f"BEFORE: {req.original_resume_text}")
    print(f"AFTER:  {response.suggested_text}")
    print(f"EXPLANATION: {response.explanation}")
    
    if req.original_resume_text != response.suggested_text and response.suggested_text is not None:
        print("\nSUCCESS: BEFORE != AFTER")
    else:
        print("\nFAILED: BEFORE == AFTER or None")

if __name__ == "__main__":
    asyncio.run(test_coach())
