import os
import json
import httpx
from typing import Any, Dict, Optional, Type, TypeVar
from pydantic import BaseModel

from .provider import LLMProvider

T = TypeVar("T", bound=BaseModel)

AIPIPE_SYSTEM_PROMPT = """You are Vettora's evidence-locked resume editor.

Your job is to improve the wording of an existing resume statement so that it is clearer, stronger, more concise, professional, and better aligned with the supplied target job requirement.

You are NOT allowed to invent facts.

You may only use facts explicitly present in the supplied Evidence Vault evidence.

Never invent or infer:
- technologies
- programming languages
- frameworks
- tools
- metrics
- percentages
- achievements
- responsibilities
- leadership
- seniority
- employers
- dates
- duration
- users
- scale
- business impact
- production experience
- deployment experience
- architecture ownership
- certifications
- degrees
- project scope

You MUST produce a meaningful editorial rewrite when a safe improvement is possible.

Do NOT return the original text unchanged.

Improve the wording through one or more of:
- stronger action verbs
- clearer sentence structure
- concise professional phrasing
- better ordering of verified facts
- stronger visibility of verified job-relevant keywords
- better alignment with the target requirement
- removal of unnecessary filler

Preserve the factual meaning of the original statement.

If the evidence does not support a safe meaningful improvement, return NO_SAFE_REWRITE.

Never compensate for missing experience by inventing it.

You must return ONLY structured JSON in exactly this format:
{
  "status": "REWRITE" | "NO_SAFE_REWRITE",
  "rewritten_text": "your strictly evidence-grounded rewrite here, or empty if NO_SAFE_REWRITE",
  "reason": "brief explanation"
}
"""

class AIPipeLLMProvider(LLMProvider):
    def __init__(self, api_token: Optional[str] = None, model: str = "openai/gpt-4.1-nano"):
        self.api_token = api_token or os.environ.get("AIPIPE_TOKEN")
        self.model = model or os.environ.get("AIPIPE_MODEL", "openai/gpt-4.1-nano")

    def generate_resume_rewrite(self, context: Dict[str, Any]) -> str:
        if not self.api_token:
            return "Error: AIPIPE_TOKEN is missing. Please configure the AI Pipe provider."

        gap_type = context.get("gap_type")
        if gap_type == "EXPERIENCE_GAP":
            return "NO_SAFE_REWRITE"

        prompt = (
            f"TARGET REQUIREMENT:\n{context.get('requirement_text', 'N/A')}\n\n"
            f"TARGET ROLE:\n{context.get('target_role', 'N/A')}\n\n"
            f"CURRENT RESUME:\n{context.get('current_resume_text', 'N/A')}\n\n"
            f"VERIFIED EVIDENCE:\n{chr(10).join(context.get('existing_evidence_snippets', []))}\n"
        )

        import logging
        logger = logging.getLogger("aipipe_diagnostic")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            ch = logging.StreamHandler()
            logger.addHandler(ch)
            
        try:
            with httpx.Client(timeout=15.0) as client:
                logger.info(f"Provider: AIPipeLLMProvider | Model: {self.model} | URL: https://aipipe.org/openrouter/v1/chat/completions")
                response = client.post(
                    "https://aipipe.org/openrouter/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": AIPIPE_SYSTEM_PROMPT},
                            {"role": "user", "content": prompt}
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.2
                    }
                )
                logger.info(f"HTTP Status: {response.status_code}")
                response.raise_for_status()
                data = response.json()
                logger.info(f"Response JSON keys: {list(data.keys())}")
                content = data["choices"][0]["message"]["content"]
                logger.info(f"Parsed content length: {len(content)}")
                logger.info(f"RAW CONTENT: {content}")
                
                try:
                    parsed = json.loads(content)
                    rewritten = parsed.get("rewritten_text", "NO_SAFE_REWRITE")
                    logger.info(f"Parsed rewrite length: {len(rewritten) if isinstance(rewritten, str) else 0}")
                    if parsed.get("status") == "NO_SAFE_REWRITE":
                        return "NO_SAFE_REWRITE"
                    return rewritten
                except json.JSONDecodeError:
                    return "Error: Malformed JSON from AI Pipe"
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return "Error: API authentication failure (401)"
            if e.response.status_code == 429:
                return "Error: API rate-limit failure (429)"
            return f"Error: Provider API error ({e.response.status_code})"
        except httpx.TimeoutException:
            return "Error: Provider timeout"
        except Exception as e:
            return f"Error: {str(e)}"

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        pass

    def generate_structured(self, prompt: str, schema: Type[T], system_prompt: Optional[str] = None, **kwargs) -> T:
        pass
