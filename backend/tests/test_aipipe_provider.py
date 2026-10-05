import pytest
import httpx
from unittest.mock import patch, MagicMock
from app.services.coach.llm.aipipe_provider import AIPipeLLMProvider

def test_missing_api_key():
    provider = AIPipeLLMProvider(api_token="")
    res = provider.generate_resume_rewrite({})
    assert "Error: AIPIPE_TOKEN is missing" in res

def test_experience_gap_short_circuit():
    provider = AIPipeLLMProvider(api_token="fake")
    res = provider.generate_resume_rewrite({"gap_type": "EXPERIENCE_GAP"})
    assert res == "NO_SAFE_REWRITE"

@patch("httpx.Client.post")
def test_successful_aipipe_rewrite_and_json_parsing(mock_post):
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {
        "choices": [{
            "message": {
                "content": '{"status": "REWRITE", "rewritten_text": "Successfully improved the backend.", "reason": "Better wording"}'
            }
        }]
    }
    mock_post.return_value = mock_resp
    
    provider = AIPipeLLMProvider(api_token="fake")
    res = provider.generate_resume_rewrite({"requirement_text": "Backend", "current_resume_text": "backend"})
    assert res == "Successfully improved the backend."

@patch("httpx.Client.post")
def test_no_safe_rewrite_json(mock_post):
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {
        "choices": [{
            "message": {
                "content": '{"status": "NO_SAFE_REWRITE", "rewritten_text": "", "reason": "Cannot improve"}'
            }
        }]
    }
    mock_post.return_value = mock_resp
    
    provider = AIPipeLLMProvider(api_token="fake")
    res = provider.generate_resume_rewrite({"requirement_text": "Backend", "current_resume_text": "backend"})
    assert res == "NO_SAFE_REWRITE"

@patch("httpx.Client.post")
def test_malformed_json_response(mock_post):
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {
        "choices": [{
            "message": {
                "content": 'Not a JSON object'
            }
        }]
    }
    mock_post.return_value = mock_resp
    
    provider = AIPipeLLMProvider(api_token="fake")
    res = provider.generate_resume_rewrite({"requirement_text": "Backend", "current_resume_text": "backend"})
    assert "Error: Malformed JSON" in res

@patch("httpx.Client.post")
def test_api_timeout(mock_post):
    mock_post.side_effect = httpx.TimeoutException("Timeout")
    
    provider = AIPipeLLMProvider(api_token="fake")
    res = provider.generate_resume_rewrite({"requirement_text": "Backend", "current_resume_text": "backend"})
    assert "Error: Provider timeout" in res

@patch("httpx.Client.post")
def test_api_auth_failure(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_post.side_effect = httpx.HTTPStatusError("401", request=MagicMock(), response=mock_resp)
    
    provider = AIPipeLLMProvider(api_token="fake")
    res = provider.generate_resume_rewrite({"requirement_text": "Backend", "current_resume_text": "backend"})
    assert "Error: API authentication failure (401)" in res

@patch("httpx.Client.post")
def test_api_rate_limit_failure(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_post.side_effect = httpx.HTTPStatusError("429", request=MagicMock(), response=mock_resp)
    
    provider = AIPipeLLMProvider(api_token="fake")
    res = provider.generate_resume_rewrite({"requirement_text": "Backend", "current_resume_text": "backend"})
    assert "Error: API rate-limit failure (429)" in res
