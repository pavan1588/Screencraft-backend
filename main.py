from fastapi import FastAPI, HTTPException, Request, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
import httpx
import os
import re
import time
import json
from starlette.status import HTTP_429_TOO_MANY_REQUESTS
from datetime import datetime

app = FastAPI()

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Models ---
class SceneRequest(BaseModel):
    scene: str

# --- Globals ---
RATE_LIMIT = {}
ROTATION_THRESHOLD = 50
PASSWORD_USAGE_COUNT = 0
PASSWORD_FILE = "scenecraft_password.json"
LOG_FILE = "submission_log.json"

# --- Env Vars ---
STORED_PASSWORD = os.getenv("SCENECRAFT_PASSWORD", "SCENECRAFT-2024")
ADMIN_PASSWORD = os.getenv("SCENECRAFT_ADMIN_KEY", "ADMIN-ACCESS-1234")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")

# --- Scene Validator ---
def is_valid_scene(text: str) -> bool:
    text_lower = text.lower()
    if len(text.strip()) < 30:
        return False

    greetings = ["hi", "hello", "hey"]
    commands = ["generate", "create", "write a scene"]
    profanity = ["fuck", "shit", "bitch", "asshole", "dumbass", "bastard"]

    if any(greet in text_lower for greet in greetings):
        return False
    if any(bad in text_lower for bad in profanity):
        return False
    if any(cmd in text_lower for cmd in commands):
        return False

    has_dialogue = re.search(r"[A-Z]{2,}.*:|[A-Z][a-z]+ \(.*\)", text)
    has_cues = re.search(r"\b(INT\.|EXT\.|FADE IN:|CUT TO:)\b", text, re.IGNORECASE)

    return bool(has_dialogue or has_cues or "dialogue" in text_lower or "scene" in text_lower)

# --- Rate Limiter ---
def rate_limiter(ip, window=60, limit=10):
    now = time.time()
    RATE_LIMIT.setdefault(ip, [])
    RATE_LIMIT[ip] = [t for t in RATE_LIMIT[ip] if now - t < window]
    if len(RATE_LIMIT[ip]) >= limit:
        return False
    RATE_LIMIT[ip].append(now)
    return True

# --- Password Rotation ---
def rotate_password():
    global STORED_PASSWORD, PASSWORD_USAGE_COUNT
    new_pass = f"SCENECRAFT-{int(time.time())}"
    STORED_PASSWORD = new_pass
    PASSWORD_USAGE_COUNT = 0
    with open(PASSWORD_FILE, "w") as f:
        json.dump({"password": new_pass}, f)

# --- Log Submission ---
def log_submission(ip, scene):
    log = {
        "ip": ip,
        "timestamp": datetime.utcnow().isoformat(),
        "scene_snippet": scene[:200]
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(log) + "\n")

# --- Analyze Endpoint ---
@app.post("/analyze")
async def analyze_scene(request: Request, data: SceneRequest, authorization: str = Header(None)):
    global PASSWORD_USAGE_COUNT

    ip = request.client.host

    if not rate_limiter(ip):
        return JSONResponse(status_code=HTTP_429_TOO_MANY_REQUESTS, content={"error": "Rate limit exceeded."})

    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"error": "Missing or invalid token."})

    token = authorization.split("Bearer ")[1]
    if token != STORED_PASSWORD:
        return JSONResponse(status_code=403, content={"error": "Invalid access token."})

    if not is_valid_scene(data.scene):
        return {"error": "Scene generation is not supported. Please input a valid cinematic excerpt for analysis only."}

    PASSWORD_USAGE_COUNT += 1
    if PASSWORD_USAGE_COUNT >= ROTATION_THRESHOLD:
        rotate_password()

    log_submission(ip, data.scene)

    if not OPENROUTER_KEY:
        return JSONResponse(status_code=500, content={"error": "Missing OpenRouter API key."})

    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://scenecraft.app",
        "X-Title": "SceneCraft"
    }

    prompt = f"""
You are SceneCraft AI, a professional cinematic analyst.

Evaluate this scene using advanced cinematic storytelling principles (Chekhov’s Gun, Show Don't Tell, Visual Grammar, Sound Design, etc.) and filmmaking judgment (like a director, editor, or script doctor). Avoid naming any principles directly. Your review should include intuitive scene feedback, realism checks, performance impact, visual pressure, and audience reaction.

Conclude with a clearly labeled "Suggestions" section.

Scene:
{data.scene}
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {"role": "system", "content": "You are a top-level film critic and scene analyst."},
            {"role": "user", "content": prompt}
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)

            if response.status_code != 200:
                return JSONResponse(status_code=response.status_code, content={"error": f"OpenRouter error: {response.text}"})

            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

            if not content:
                return JSONResponse(status_code=502, content={"error": "Empty analysis response from model."})

            return {"analysis": content.strip()}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Server error: {str(e)}"})

# --- T&C Page ---
@app.get("/terms", response_class=HTMLResponse)
async def terms():
    return """
    <html>
    <head><title>Terms & Conditions | SceneCraft</title></head>
    <body style="font-family:sans-serif;padding:2rem;line-height:1.6">
      <h1>Terms & Conditions</h1>
      <p>SceneCraft is an educational and analytical tool. All input must be original or submitted under fair use for critique. Users are solely responsible for the content they submit. No copyrighted content is stored or redistributed by SceneCraft.</p>
      <h2>Usage Policy</h2>
      <ul>
        <li>No offensive, abusive, or explicit content is allowed.</li>
        <li>Submissions are logged with timestamp and IP for abuse tracking.</li>
        <li>Analysis provided is opinionated and non-authoritative.</li>
        <li>SceneCraft is not responsible for any third-party copyright violations.</li>
      </ul>
      <h2>Copyright Notice</h2>
      <p>By using this service, you confirm that you have the rights to submit the material or are using it under fair-use for critique. SceneCraft does not generate or store scenes, nor claim ownership of user submissions.</p>
    </body>
    </html>
    """

# --- Admin Token Check ---
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
    return {"message": "Password manually rotated", "new_password": STORED_PASSWORD}

# --- Root ---
@app.get("/")
def root():
    return {"message": "SceneCraft backend is live."}
