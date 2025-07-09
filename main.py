from fastapi import FastAPI, HTTPException, Request, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
import httpx
import os
import re
import time
import json
from datetime import datetime
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

app = FastAPI()

# CORS
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
LOG_FILE = "scene_log.jsonl"

# --- Scene validation ---
def is_valid_scene(text: str) -> bool:
    greetings = ["hi", "hello", "hey", "good morning", "good evening"]
    command_words = ["generate", "write a scene", "compose a script", "create a scene"]
    text_lower = text.lower()
    if len(text.strip()) < 30 or text_lower in greetings or any(cmd in text_lower for cmd in command_words):
        return False
    has_dialogue = re.search(r"[A-Z][a-z]+\s*\(.*?\)|[A-Z]{2,}.*:|\[.*?\]", text)
    has_cinematic_cues = re.search(r"\b(INT\.|EXT\.|CUT TO:|FADE IN:)\b", text, re.IGNORECASE)
    return True if (has_dialogue or has_cinematic_cues or (len(text.split()) > 20 and any(p in text_lower for p in ["character", "scene", "dialogue", "script", "monologue", "film"]))) else False

# --- Profanity blocklist (basic) ---
PROFANITY_LIST = ["fuck", "shit", "bitch", "asshole", "chod", "gandu", "loda", "randi", "madarchod", "bhenchod", "mc", "bc"]

def contains_profanity(text: str) -> bool:
    text_lower = text.lower()
    return any(bad in text_lower for bad in PROFANITY_LIST)

# --- Rate Limiting ---
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

# --- Scene Logging ---
def log_scene(ip, scene_text):
    with open(LOG_FILE, "a", encoding="utf-8") as logf:
        logf.write(json.dumps({
            "timestamp": datetime.utcnow().isoformat(),
            "ip": ip,
            "text": scene_text[:300] + ("..." if len(scene_text) > 300 else "")
        }) + "\n")

# --- Analyze Route ---
@app.post("/analyze")
async def analyze_scene(request: Request, data: SceneRequest, authorization: str = Header(None)):
    global PASSWORD_USAGE_COUNT, STORED_PASSWORD

    ip = request.client.host
    if not rate_limiter(ip):
        return JSONResponse(status_code=HTTP_429_TOO_MANY_REQUESTS, content={"error": "Rate limit exceeded"})

    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"error": "Unauthorized: Missing or invalid token"})

    token = authorization.split("Bearer ")[1]
    if token != STORED_PASSWORD:
        return JSONResponse(status_code=403, content={"error": "Forbidden: Invalid access token"})

    PASSWORD_USAGE_COUNT += 1
    if PASSWORD_USAGE_COUNT >= ROTATION_THRESHOLD:
        rotate_password()

    if contains_profanity(data.scene):
        return JSONResponse(status_code=400, content={"error": "Profanity or abusive language detected. Please revise your input."})

    if not is_valid_scene(data.scene):
        return JSONResponse(status_code=400, content={"error": "Scene generation is not supported. Please input a valid cinematic excerpt for analysis only."})

    log_scene(ip, data.scene)

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return JSONResponse(status_code=500, content={"error": "Missing OpenRouter API key"})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://yourapp.com",
        "X-Title": "SceneCraft"
    }

    prompt = f"""
You are SceneCraft AI, a professional cinematic analyst. Evaluate the scene/script excerpt below using professional human tone.

Avoid listing benchmark names. Integrate the following principles fluidly into your output:
- Emotional realism
- Scene structure and tension
- Character psychology and motivations
- Genre tone and audience effect
- Directorial grammar and visual pressure
- Examples from global cinema scenes
- Conclude with clear “Suggestions” section only

Scene:
{data.scene}
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {"role": "system", "content": "You are a cinematic story analyst. Do not generate. Provide human-grade scene critique using director-level insight."},
            {"role": "user", "content": prompt}
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)

            try:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                return {"analysis": content.strip()}
            except Exception:
                return JSONResponse(status_code=500, content={"error": "OpenRouter returned invalid response."})

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Unexpected backend error: {str(e)}"})

# --- Admin Password Routes ---
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

# --- Legal / Terms Page ---
@app.get("/terms", response_class=HTMLResponse)
def get_terms():
    html = """
    <html>
    <head><title>SceneCraft Terms & Usage</title></head>
    <body style='font-family:sans-serif;max-width:800px;margin:auto;padding:2rem;line-height:1.6'>
      <h1>Terms & Conditions</h1>
      <p>By using SceneCraft, you agree to the following:</p>
      <ul>
        <li>You are submitting content for critique only.</li>
        <li>You retain full responsibility for any uploaded material.</li>
        <li>SceneCraft does not store or reuse your scene data beyond trace logs.</li>
        <li>We do not verify originality of your content. Copyright remains your responsibility.</li>
        <li>No scene generation, copying, or AI writing is allowed or supported.</li>
      </ul>
      <h2>Legal Disclaimer</h2>
      <p>This tool is for educational and analysis purposes only. It does not replace professional consultation. All feedback is subjective, and SceneCraft is not liable for any professional or commercial outcomes based on this critique.</p>
      <p>Use of this tool constitutes acceptance of these terms.</p>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.get("/")
def root():
    return {"message": "SceneCraft backend is live."}
