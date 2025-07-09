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
LOG_FILE = "scene_logs.json"

# Slang + profanity check
profanity_keywords = ["fuck", "shit", "bastard", "madarchod", "bhenchod", "suar", "kutte", "cunt", "asshole", "gandu"]
def contains_profanity(text: str) -> bool:
    return any(bad in text.lower() for bad in profanity_keywords)

# Logging for traceability
def log_request(ip: str, scene: str):
    log_entry = {
        "ip": ip,
        "timestamp": datetime.utcnow().isoformat(),
        "length": len(scene),
        "preview": scene[:120].strip().replace("\n", " ") + "..."
    }
    with open(LOG_FILE, "a") as log_file:
        log_file.write(json.dumps(log_entry) + "\n")

# Scene validation logic
def is_valid_scene(text: str) -> bool:
    greetings = ["hi", "hello", "hey", "good morning", "good evening"]
    command_words = ["generate", "write a scene", "compose a script", "create a scene"]
    text_lower = text.lower()
    if len(text.strip()) < 30 or text_lower in greetings or any(cmd in text_lower for cmd in command_words):
        return False
    if contains_profanity(text_lower):
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
        return JSONResponse(status_code=HTTP_429_TOO_MANY_REQUESTS, content={"error": "Rate limit exceeded"})

    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"error": "Unauthorized: Missing or invalid token"})

    token = authorization.split("Bearer ")[1]
    if token != STORED_PASSWORD:
        return JSONResponse(status_code=403, content={"error": "Forbidden: Invalid access token"})

    if not is_valid_scene(data.scene):
        return JSONResponse(status_code=400, content={"error": "Invalid input. Profanity, casual input, or scene generation is not allowed."})

    log_request(ip, data.scene)

    PASSWORD_USAGE_COUNT += 1
    if PASSWORD_USAGE_COUNT >= ROTATION_THRESHOLD:
        rotate_password()

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
You are SceneCraft AI, a professional cinematic analyst.

Evaluate the following scene using all cinematic and storytelling benchmarks, including advanced behavioral, psychological, genre, realism, director-level, and visual pressure factors. Do not generate content.

Scene:
{data.scene}
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a professional cinematic analyst. Do not generate or complete scenes. "
                    "Deliver natural, grounded, human-sounding feedback across cinematic structure, scene grammar, psychology, realism, directing, editing, and storytelling. "
                    "End with a clearly marked section titled 'Suggestions'. Include director-level notes. Always include visual pressure analysis if cues exist."
                )
            },
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
            content = result["choices"][0]["message"]["content"]
            legal_notice = (
                "\n\n⚠️ Legal Disclaimer:\n"
                "This analysis is for educational and critical commentary only. SceneCraft does not generate or recreate original works. "
                "By using SceneCraft, you confirm you hold necessary rights to submit material or are submitting for legal fair use critique. "
                "You are solely responsible for submitted content."
            )
            return {"analysis": content.strip() + legal_notice}
    except httpx.HTTPStatusError as e:
        return JSONResponse(status_code=500, content={"error": f"OpenRouter API error: {e.response.text}"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Internal error: {str(e)}"})

@app.get("/terms", response_class=HTMLResponse)
def terms():
    return """
    <html><body>
    <h1>Terms & Conditions</h1>
    <p>By using SceneCraft, you agree to only submit content you have the right to analyze or use for critique under fair use.</p>
    <p>SceneCraft is intended strictly for educational and analytical purposes. Misuse may result in termination of access.</p>
    <p>No data is shared with third parties. All analyses are stored only for internal logging and improvement.</p>
    <p>Do not upload copyrighted, sensitive, or private material you do not have rights to analyze.</p>
    </body></html>
    """

@app.get("/policy", response_class=HTMLResponse)
def policy():
    return """
    <html><body>
    <h1>Usage Policy</h1>
    <p>SceneCraft is a scene analysis tool designed for screenwriters, filmmakers, students, and critics.</p>
    <p>All output is educational, interpretative, and may reflect subjective cinematic principles.</p>
    <p>No scene generation or creation is permitted. Offensive, harmful, or illegal submissions are strictly prohibited.</p>
    <p>Your IP and timestamp may be logged for safety, performance, and abuse prevention.</p>
    </body></html>
    """

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
    return {"message": "SceneCraft backend is live and healthy."}
