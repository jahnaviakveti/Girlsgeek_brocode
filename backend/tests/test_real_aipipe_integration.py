import os
import pytest
from app.services.coach.resume.service import ResumeCoachService
from app.schemas.resume_coach import ResumeCoachRequest, ResumeCoachStatus
from app.services.coach.llm.aipipe_provider import AIPipeLLMProvider
from dotenv import load_dotenv
from tests.test_phase4_resume_coach import alex_profile, alex_twin_and_vault

load_dotenv(".env")

def test_real_aipipe_coach(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    
    # Verify we have the token
    token = os.environ.get("AIPIPE_TOKEN")
    model = os.environ.get("AIPIPE_MODEL")
    assert token is not None, "Missing token"
    
    # Init the real provider
    real_llm = AIPipeLLMProvider(api_token=token, model=model)
    service = ResumeCoachService(llm_provider=real_llm)
    
    original_text = "Built Flask backend microservices."
    
    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_backend",
        requirement_text="Backend engineer with robust API development experience.",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=[it.evidence_id for it in vault.items if "flask" in it.source_text.lower()],
        existing_evidence_snippets=[original_text],
        current_resume_text=original_text
    )
    
    print("\n[TEST] Making real AI Pipe request...")
    resp = service.generate_rewrite(req, twin, vault)
    
    print("\n--- RESULTS ---")
    print(f"STATUS: {resp.status}")
    print(f"BEFORE: {original_text}")
    print(f"RAW RESP TEXT: {resp.suggested_text}")
    print(f"REASON: {resp.explanation}")
    
    # The requirement is BEFORE != AFTER
    assert resp.suggested_text is not None, "Rewrite was None (NO_SAFE_REWRITE / identical)"
    assert resp.suggested_text != original_text, "Rewrite was identical to original!"
