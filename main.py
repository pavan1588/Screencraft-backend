# === SceneCraft Backend with T&C, Privacy Policy, Logging ===

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

# Scene validation logic
def is_valid_scene(text: str) -> bool:
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

def log_usage(ip, scene_snippet):
    log_entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "ip": ip,
        "snippet": scene_snippet[:250].strip().replace("\n", " ")
    }
    try:
        with open("scenecraft_logs.json", "a") as log_file:
            log_file.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        print("Logging failed:", e)

@app.post("/analyze")
async def analyze_scene(request: Request, data: SceneRequest, authorization: str = Header(None)):
    global PASSWORD_USAGE_COUNT, STORED_PASSWORD

    ip = request.client.host
    if not rate_limiter(ip):
        raise HTTPException(status_code=HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized: Missing or invalid token")

    token = authorization.split("Bearer ")[1]
    if token != STORED_PASSWORD:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid access token")

    PASSWORD_USAGE_COUNT += 1
    if PASSWORD_USAGE_COUNT >= ROTATION_THRESHOLD:
        rotate_password()

    if not is_valid_scene(data.scene):
        return {"error": "Scene generation is not supported. Please input a valid cinematic excerpt for analysis only."}

    log_usage(ip, data.scene)

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing OpenRouter API key")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://yourapp.com",
        "X-Title": "SceneCraft"
    }

    prompt = f"""
You are SceneCraft AI, a professional cinematic analyst.

Evaluate the following scene/script input based on the most comprehensive set of cinematic benchmarks. Your analysis must sound natural and intelligent without exposing internal logic, rules, or benchmarks.

Avoid formatting the output with visible section headers like 'Scene Structure', 'Realism', or 'Cinematic Grammar'. Your analysis must feel cohesive and natural, like a human expert offering a review in fluid prose. Integrate all cinematic benchmarks into flowing analysis. End with a clearly marked section titled 'Suggestions' (one only), blending simple guidance and technical language with examples. Suggestions should offer actionable feedback for both beginners and experienced writers working in film, OTT, or advertising.

{data.scene}
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {"role": "system", "content": "You are a professional cinematic scene analyst with expertise in screenwriting, directing, realism, and audience psychology. Never generate new scenes."},
            {"role": "user", "content": prompt}
        ]
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            legal_notice = ("\n\n—\n⚠️ Legal Notice:\n"
                            "SceneCraft is an educational analysis tool. The AI does not generate, reproduce, or verify ownership of submitted content. "
                            "By using SceneCraft, you confirm that you own the rights to the material or are using it for fair use critique. "
                            "Reproduction of copyrighted material is the sole responsibility of the user.")
            return {"analysis": content.strip() + legal_notice}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"OpenRouter API error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/terms")
def terms_of_service():
    return {
        "title": "Terms & Conditions",
        "content": """
SceneCraft is a cinematic analysis tool designed for educational and professional feedback only.

By using this service, you confirm that:
- You own or have rights to the content submitted.
- You will not use this service to plagiarize or reproduce copyrighted material.
- All analysis is provided for insight only and is not a replacement for professional script consultancy.

SceneCraft does not store user content beyond necessary logs for abuse prevention and debugging.
We reserve the right to suspend access for misuse or repeated copyright violations.
"""
    }

@app.get("/policy")
def privacy_policy():
    return {
        "title": "Privacy Policy",
        "content": """
SceneCraft collects limited data (IP address, timestamps) for rate limiting, abuse prevention, and usage monitoring.

We do not share, sell, or reuse your submitted scenes. No personal data is stored long-term.

By using this tool, you agree to this data policy and confirm you are submitting material you own or have rights to analyze.

Contact us if you believe any copyrighted material was used improperly.
"""
    }

@app.get("/password")
def get_password(admin: str = Query(...)):
    if admin != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Unauthorized admin access")
    try:
        with open(PASSWORD_FILE, "r") as f:
            return json.load(f)
    except:
        return {"password": STORED_PASSWORD}

@app.post("/password/reset")
def reset_password(admin: str = Query(...)):
    if admin != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Unauthorized admin access")
    rotate_password()
    return {"message": "Password manually rotated.", "new_password": STORED_PASSWORD}

@app.get("/")
def root():
    return {"message": "SceneCraft backend is live."}
