from fastapi import FastAPI, HTTPException, Request, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
import re
import time
import json
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

app = FastAPI()

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SceneRequest(BaseModel):
    scene: str

RATE_LIMIT = {}
ROTATION_THRESHOLD = 50
PASSWORD_USAGE_COUNT = 0
STORED_PASSWORD = os.getenv("SCENECRAFT_PASSWORD", "SCENECRAFT-2024")
ADMIN_PASSWORD = os.getenv("SCENECRAFT_ADMIN_KEY", "ADMIN-ACCESS-1234")
PASSWORD_FILE = "scenecraft_password.json"

# Profanity/Slang blacklist (sample)
SLANG_BLACKLIST = [
    "chutiya", "bhosdi", "madarchod", "fuck", "shit", "bitch", "asshole",
    "mc", "bc", "gaand", "loda", "behenchod", "kutti", "nigger", "cunt"
]

def contains_profanity(text: str) -> bool:
    text_lower = text.lower()
    return any(bad_word in text_lower for bad_word in SLANG_BLACKLIST)

# Scene validation logic
def is_valid_scene(text: str) -> bool:
    if contains_profanity(text):
        return False
    greetings = ["hi", "hello", "hey", "good morning", "good evening"]
    command_words = ["generate", "write a scene", "compose a script", "create a scene"]
    text_lower = text.lower()
    if len(text.strip()) < 30 or text_lower in greetings or any(cmd in text_lower for cmd in command_words):
        return False
    has_dialogue = re.search(r"[A-Z][a-z]+\s*\(.*?\)|[A-Z]{2,}.*:|\[.*?\]", text)
    has_cinematic_cues = re.search(r"\b(INT\.|EXT\.|CUT TO:|FADE IN:)\b", text, re.IGNORECASE)
    return True if (has_dialogue or has_cinematic_cues or (len(text.split()) > 20 and any(p in text_lower for p in ["character", "scene", "dialogue", "script", "monologue", "film"]))) else False

def rate_limiter(ip, window=60, limit=10):
    now = time.time()
    RATE_LIMIT.setdefault(ip, [])
    RATE_LIMIT[ip] = [t for t in RATE_LIMIT[ip] if now - t < window]
    if len(RATE_LIMIT[ip]) >= limit:
        return False
    RATE_LIMIT[ip].append(now)
    return True

def rotate_password():
    global STORED_PASSWORD, PASSWORD_USAGE_COUNT
    new_token = f"SCENECRAFT-{int(time.time())}"
    STORED_PASSWORD = new_token
    PASSWORD_USAGE_COUNT = 0
    with open(PASSWORD_FILE, "w") as f:
        json.dump({"password": new_token}, f)
    print("Password rotated to:", new_token)

@app.post("/analyze")
async def analyze_scene(request: Request, data: SceneRequest, authorization: str = Header(None)):
    global PASSWORD_USAGE_COUNT, STORED_PASSWORD

    ip = request.client.host
    if not rate_limiter(ip):
        return {"error": "Rate limit exceeded"}

    if not authorization or not authorization.startswith("Bearer "):
        return {"error": "Unauthorized: Missing or invalid token"}

    token = authorization.split("Bearer ")[1]
    if token != STORED_PASSWORD:
        return {"error": "Forbidden: Invalid access token"}

    PASSWORD_USAGE_COUNT += 1
    if PASSWORD_USAGE_COUNT >= ROTATION_THRESHOLD:
        rotate_password()

    if not is_valid_scene(data.scene):
        return {"error": "Invalid or non-cinematic input. Do not include profanity, casual chat, or generated requests."}

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return {"error": "Missing OpenRouter API key"}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://yourapp.com",
        "X-Title": "SceneCraft"
    }

    prompt = f"""
You are SceneCraft AI, a professional cinematic analyst. Evaluate this scene for story structure, realism, directing insight, emotional beats, and visual tension. Include director-level notes, practical suggestions, and comparative references. Do not generate content. Focus on critique only.

Scene:
{data.scene}
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {"role": "system", "content": "Professional cinematic scene analyst. Never generate content. Only analyze."},
            {"role": "user", "content": prompt}
        ]
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            if "choices" not in result or not result["choices"]:
                raise ValueError("Model returned no output.")

            content = result["choices"][0]["message"]["content"]
            legal_notice = (
                "\n\n—\n⚠️ Legal Notice:\n"
                "SceneCraft is for educational cinematic critique only. You are responsible for rights to submitted content."
            )
            return {"analysis": content.strip() + legal_notice}
    except Exception as e:
        return {"error": f"Server error: {str(e)}"}

@app.get("/terms")
def get_terms():
    return {
        "terms": """
        By using SceneCraft, you agree to:
        - Submit only original or authorized material.
        - Avoid uploading copyrighted, abusive, or personal data.
        - Accept that this tool is only for cinematic critique and educational use.
        - Understand that SceneCraft is not liable for any content you submit.
        """,
        "usage_policy": """
        - Do not abuse or spam this service.
        - Do not attempt to use this tool for content generation.
        - Feedback is automatically generated based on scene inputs for educational review.
        - Repeated misuse may result in IP bans or access restrictions.
        """,
        "legal_disclaimer": """
        SceneCraft does not verify copyright ownership.
        All responsibility for submitted material lies with the user.
        This tool offers automated scene critique using AI.
        Use of SceneCraft indicates acceptance of these terms.
        """
    }

@app.get("/")
def root():
    return {"message": "SceneCraft backend is running"}
