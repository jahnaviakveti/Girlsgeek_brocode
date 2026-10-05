import httpx
import json

token = "eyJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6IjI0ZjIwMDg5MDZAZHMuc3R1ZHkuaWl0bS5hYy5pbiIsImlhdCI6MTc4NjI5MDY1NCwiaXNzIjoiaHR0cHM6Ly9haXBpcGUub3JnIiwiYXVkIjoiYWlwaXBlLWFwaSIsImV4cCI6MTc4Njg5NTQ1NH0._oaJu7KrpLF2X-kpMo1M-wmnDC_qmkQfi_YixSuIRRA"
model = "openai/gpt-4.1-mini"

# I will test the JSON formatting that AIPipe Provider requires
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
  "status": "REWRITE",
  "rewritten_text": "your strictly evidence-grounded rewrite here",
  "reason": "brief explanation"
}
"""

prompt = """
TARGET REQUIREMENT:
"TechNova Solutions is looking for a Junior Full Stack Developer Intern to join our product engineering team."

CURRENT RESUME:
"Final-year Computer Science student with hands-on experience building full stack web applications using the MERN stack."

VERIFIED EVIDENCE:
- MERN stack
- full stack web applications
- Computer Science student
"""

try:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            "https://aipipe.org/openrouter/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": AIPIPE_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.2
            }
        )
        print("STATUS:", response.status_code)
        if response.status_code == 200:
            print("RESPONSE JSON KEYS:", response.json().keys())
            content = response.json()["choices"][0]["message"]["content"]
            print("RAW CONTENT:", content)
            
            try:
                parsed = json.loads(content)
                print("PARSED KEYS:", parsed.keys())
                print("REWRITTEN:", parsed.get("rewritten_text"))
            except Exception as e:
                print("PARSE ERROR:", str(e))
        else:
            print("ERROR RESPONSE:", response.text)
except Exception as e:
    print("FATAL ERROR:", str(e))
