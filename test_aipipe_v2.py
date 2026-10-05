import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv(".env")
token = os.environ.get("AIPIPE_TOKEN")
model = os.environ.get("AIPIPE_MODEL", "openai/gpt-4.1-nano")

if not token:
    print("Token not found in .env")
    exit(1)

prompt = """
Respond with structured JSON.
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
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"}
            }
        )
        
        print(f"Model Name: {model}")
        print(f"HTTP Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response Keys: {list(data.keys())}")
            
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            print(f"Content Length: {len(content)}")
            
            if len(content) == 0:
                print("Error: Content is empty!")
            else:
                print("Content is non-empty!")
        else:
            print("Error response text:", response.text)
except Exception as e:
    print(f"Error: {e}")
