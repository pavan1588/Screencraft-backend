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
USAGE_LOG = "scenecraft_usage_log.json"

# Logging submitted scenes for traceability
def log_usage(ip: str, scene: str):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    entry = {"ip": ip, "timestamp": timestamp, "text_sample": scene[:200]}
    try:
        with open(USAGE_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        print("Failed to log usage:", e)

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

    PASSWORD_USAGE_COUNT += 1
    if PASSWORD_USAGE_COUNT >= ROTATION_THRESHOLD:
        rotate_password()

    if not is_valid_scene(data.scene):
        return JSONResponse(content={"error": "Scene generation is not supported. Please input a valid cinematic excerpt for analysis only."})

    log_usage(ip, data.scene)

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
You are SceneCraft AI, a professional cinematic analyst. Do not generate new content. Analyze the scene using cinematic intelligence, structure, realism, and visual language. Avoid headings. Reference known cinematic moments. Add professional director-level notes where appropriate.

Scene:
{data.scene}
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {"role": "system", "content": "You are a highly skilled film analyst. Never generate or complete scenes. Provide insight-rich evaluations with director-level analysis."},
            {"role": "user", "content": prompt}
        ]
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            if response.status_code != 200:
                return JSONResponse(status_code=500, content={"error": f"API error: {response.text}"})

            result = response.json()
            content = result["choices"][0]["message"]["content"]

            legal_notice = (
                "\n\n⚠️ Legal Disclaimer:\n"
                "This tool is intended for educational and critique purposes only. Do not submit copyrighted work without authorization. "
                "SceneCraft does not store or claim ownership. Responsibility lies with the user."
            )
            return JSONResponse(content={"analysis": content.strip() + legal_notice})

    except httpx.RequestError as e:
        return JSONResponse(status_code=500, content={"error": f"Network error: {str(e)}"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Unexpected error: {str(e)}"})

@app.get("/terms", response_class=HTMLResponse)
def terms_page():
    return """
    <html><head><title>SceneCraft Terms & Conditions</title></head><body style='font-family:sans-serif; padding:2rem;'>
    <h1>Terms & Conditions</h1>
    <p>By using SceneCraft, you agree to submit only content you own or are authorized to submit under fair use or commentary guidelines. SceneCraft does not generate content or claim ownership over submitted material.</p>
    <p>SceneCraft is for critique and educational purposes only. Misuse or infringement of copyright is the sole responsibility of the user.</p>
    <p>We reserve the right to log anonymized metadata (e.g., IP, timestamp) for moderation and improvement purposes.</p>
    <p>Do not attempt to bypass our protections or misuse the system for generative content creation.</p>
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
    return {"message": "SceneCraft backend is live."}
