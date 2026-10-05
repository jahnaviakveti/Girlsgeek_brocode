import os

tests_to_append = """

def test_identical_before_after_is_rejected(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    mock_llm = MockLLMProvider(mode="safe_rewrite")
    # Override mock to return exact original
    original_text = "Built Flask backend microservices for automated payment processing."
    mock_llm.set_custom_response(original_text)
    
    service = ResumeCoachService(llm_provider=mock_llm)
    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_api",
        requirement_text="Flask backend development",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=[it.evidence_id for it in vault.items if "flask" in it.source_text.lower()],
        existing_evidence_snippets=[original_text],
        current_resume_text=original_text
    )
    resp = service.generate_rewrite(req, twin, vault)
    assert resp.status == ResumeCoachStatus.NO_SAFE_REWRITE
    assert resp.suggested_text is None
    assert "identical or negligibly different" in resp.explanation

def test_whitespace_case_only_change_is_rejected(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    mock_llm = MockLLMProvider(mode="safe_rewrite")
    original_text = "Built Flask backend microservices for automated payment processing."
    mock_llm.set_custom_response("  built flask BACKEND microservices for automated payment processing.   ")
    
    service = ResumeCoachService(llm_provider=mock_llm)
    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_api",
        requirement_text="Flask backend development",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=[it.evidence_id for it in vault.items if "flask" in it.source_text.lower()],
        existing_evidence_snippets=[original_text],
        current_resume_text=original_text
    )
    resp = service.generate_rewrite(req, twin, vault)
    assert resp.status == ResumeCoachStatus.NO_SAFE_REWRITE
    assert resp.suggested_text is None

def test_genuinely_improved_evidence_grounded_rewrite_accepted(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    mock_llm = MockLLMProvider(mode="safe_rewrite")
    original_text = "Built Flask backend microservices."
    improved_text = "Engineered robust Flask backend microservices to accelerate automated payment processing."
    mock_llm.set_custom_response(improved_text)
    
    service = ResumeCoachService(llm_provider=mock_llm)
    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_api",
        requirement_text="Flask backend development",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=[it.evidence_id for it in vault.items if "flask" in it.source_text.lower()],
        existing_evidence_snippets=[original_text],
        current_resume_text=original_text
    )
    resp = service.generate_rewrite(req, twin, vault)
    assert resp.status == ResumeCoachStatus.ACCEPTED
    assert resp.suggested_text == improved_text

def test_improved_wording_with_unsupported_claim_rejected(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    mock_llm = MockLLMProvider(mode="safe_rewrite")
    original_text = "Built Flask backend microservices."
    improved_text = "Engineered robust Flask backend microservices to accelerate automated payment processing, leading a team of 10 developers."
    mock_llm.set_custom_response(improved_text)
    
    service = ResumeCoachService(llm_provider=mock_llm)
    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_api",
        requirement_text="Flask backend development",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=[it.evidence_id for it in vault.items if "flask" in it.source_text.lower()],
        existing_evidence_snippets=[original_text],
        current_resume_text=original_text
    )
    resp = service.generate_rewrite(req, twin, vault)
    assert resp.status == ResumeCoachStatus.REJECTED
    assert len(resp.unsupported_claims) > 0

def test_jd_keyword_visibility_improvement_using_verified_evidence_accepted(alex_twin_and_vault):
    twin, vault = alex_twin_and_vault
    mock_llm = MockLLMProvider(mode="safe_rewrite")
    original_text = "Built backend microservices for automated payment processing."
    # We know from alex_profile that the evidence explicitly says "Flask" and "Python"
    improved_text = "Built Python and Flask backend microservices for automated payment processing."
    mock_llm.set_custom_response(improved_text)
    
    service = ResumeCoachService(llm_provider=mock_llm)
    req = ResumeCoachRequest(
        candidate_id=twin.candidate_id,
        requirement_id="req_api",
        requirement_text="Python Flask backend development",
        gap_type="RESUME_VISIBILITY_GAP",
        evidence_ids=[it.evidence_id for it in vault.items if "flask" in it.source_text.lower()],
        existing_evidence_snippets=[original_text],
        current_resume_text=original_text
    )
    resp = service.generate_rewrite(req, twin, vault)
    assert resp.status == ResumeCoachStatus.ACCEPTED
"""

with open("backend/tests/test_improve_resume.py", "a") as f:
    f.write(tests_to_append)
