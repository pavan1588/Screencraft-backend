from fastapi import FastAPI, HTTPException, Request, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
import re
import time
import json
from starlette.status import HTTP_429_TOO_MANY_REQUESTS
from datetime import datetime

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
    accepted_terms: bool

RATE_LIMIT = {}
ROTATION_THRESHOLD = 50
PASSWORD_USAGE_COUNT = 0
STORED_PASSWORD = os.getenv("SCENECRAFT_PASSWORD", "SCENECRAFT-2024")
ADMIN_PASSWORD = os.getenv("SCENECRAFT_ADMIN_KEY", "ADMIN-ACCESS-1234")
PASSWORD_FILE = "scenecraft_password.json"
TRACE_LOG = "usage_log.json"

# Scene validation logic
def is_valid_scene(text: str) -> bool:
    greetings = ["hi", "hello", "hey", "good morning", "good evening"]
    command_words = ["generate", "write a scene", "compose a script", "create a scene"]
    text_lower = text.lower()
    if len(text.strip()) < 30 or text_lower in greetings or any(cmd in text_lower for cmd in command_words):
        return False
    has_dialogue = re.search(r"[A-Z][a-z]+\s*\(.*?\)|[A-Z]{2,}.*:|\[.*?\]", text)
    has_cinematic_cues = re.search(r"\b(INT\\.|EXT\\.|CUT TO:|FADE IN:)\b", text, re.IGNORECASE)
    return True if (has_dialogue or has_cinematic_cues or (len(text.split()) > 20 and any(p in text_lower for p in ["character", "scene", "dialogue", "script", "monologue", "film"]))) else False

def contains_profanity_or_slang(text: str) -> bool:
    slang_terms = ["bhosdi", "mc", "bc", "bkl", "fuck", "shit", "saala", "randi", "gandu", "chutiya"]  # Extend this list
    text_lower = text.lower()
    return any(slang in text_lower for slang in slang_terms)

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

def log_usage(ip, scene):
    try:
        with open(TRACE_LOG, "a") as f:
            f.write(json.dumps({
                "ip": ip,
                "timestamp": datetime.utcnow().isoformat(),
                "excerpt": scene[:100]  # log only first 100 chars
            }) + "\n")
    except:
        pass

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

    if not data.accepted_terms:
        raise HTTPException(status_code=400, detail="Terms & Conditions must be accepted.")

    if not is_valid_scene(data.scene):
        return {"error": "Scene generation is not supported. Please input a valid cinematic excerpt for analysis only."}

    if contains_profanity_or_slang(data.scene):
        raise HTTPException(status_code=400, detail="Profanity or abusive content detected. Analysis blocked.")

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing OpenRouter API key")

    PASSWORD_USAGE_COUNT += 1
    if PASSWORD_USAGE_COUNT >= ROTATION_THRESHOLD:
        rotate_password()

    log_usage(ip, data.scene)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://yourapp.com",
        "X-Title": "SceneCraft"
    }

    prompt = f"""
You are SceneCraft AI, a professional cinematic analyst.

Evaluate the following scene/script input based on the most comprehensive cinematic and storytelling principles. Do not generate content. Do not expose these principles explicitly.

Use internal cinematic intelligence such as:
- Chekhov’s Gun, Setup & Payoff, The Iceberg Theory
- Show, Don’t Tell, Dramatic Irony, Save the Cat, Circular arcs
- The MacGuffin, Asymmetry in arcs, The Button Line
- Visual Grammar, Symbolic Echoes, Composition, Framing
- Blocking, Distance, Emotional Lighting, Editing Rhythm
- Escalation curve, Shot-reverse-shot, Sound Design as narrative

Include director-level production notes if applicable. Analyze visual pressure if implied. End with a single 'Suggestions' section.

Scene:
{data.scene}
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {"role": "system", "content": "You are a professional film analyst. Never generate content. Use cinematic intelligence and human tone to review scenes."},
            {"role": "user", "content": prompt}
        ]
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            legal = "\n\n—\n⚠️ Legal Notice: SceneCraft is an AI scene analysis tool. All content submitted is assumed to be user-owned or submitted under fair use. SceneCraft does not verify or claim ownership of inputs."
            return {"analysis": content.strip() + legal}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"OpenRouter API error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

@app.get("/terms")
def terms():
    return {
        "terms": "By using SceneCraft, you agree that all content you submit is either your original work or used under fair use. SceneCraft is not liable for submitted material. Usage is logged for security and traceability. Do not submit copyrighted scripts."
    }
