from fastapi import FastAPI, HTTPException, Request, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
import re
import time
import json
import datetime
from starlette.responses import HTMLResponse
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

app = FastAPI()

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
LOG_FILE = "scenecraft_logs.jsonl"

def is_valid_scene(text: str) -> bool:
    greetings = ["hi", "hello", "hey", "good morning", "good evening"]
    command_words = ["generate", "write a scene", "compose a script", "create a scene"]
    text_lower = text.lower()
    if len(text.strip()) < 30 or text_lower in greetings or any(cmd in text_lower for cmd in command_words):
        return False
    has_keywords = any(word in text_lower for word in ["scene", "dialogue", "monologue", "script", "character"])
    has_format_clues = re.search(r"[A-Z]{2,}:|\(.*?\)|\bINT\.|\bEXT\.|\bCUT TO:|\bFADE IN:", text)
    return True if has_format_clues or has_keywords else False

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
async def analyze_scene(
    request: Request,
    data: SceneRequest,
    authorization: str = Header(None),
    x_user_agreement: str = Header(None)
):
    global PASSWORD_USAGE_COUNT, STORED_PASSWORD

    ip = request.client.host
    if not rate_limiter(ip):
        raise HTTPException(status_code=HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

    if not x_user_agreement or x_user_agreement.lower() != "true":
        raise HTTPException(status_code=400, detail="User agreement must be accepted before submission.")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized: Missing or invalid token")

    token = authorization.split("Bearer ")[1]
    if token != STORED_PASSWORD:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid access token")

    PASSWORD_USAGE_COUNT += 1
    if PASSWORD_USAGE_COUNT >= ROTATION_THRESHOLD:
        rotate_password()

    if not is_valid_scene(data.scene):
        return {"error": "Please enter a valid cinematic scene, script excerpt, dialogue, or monologue. Random or incomplete text is not supported."}

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing OpenRouter API key")

    # Lightweight logging
    log_entry = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "ip": ip,
        "scene_preview": data.scene.strip()[:250]
    }
    try:
        with open(LOG_FILE, "a") as log_file:
            log_file.write(json.dumps(log_entry) + "\n")
    except Exception as log_error:
        print(f"[SceneCraft] Logging failed: {log_error}")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://yourapp.com",
        "X-Title": "SceneCraft"
    }

    prompt = f"""
You are SceneCraft AI — a master-level cinematic analyst and creative mentor.
You understand every layer of the filmmaking process: writing, direction, editing, sound, psychology, realism, blocking, cinematography, and audience experience.
You do not generate content. You analyze user-submitted scenes with depth, creativity, and professionalism.

Rules:
- Detect and interpret the input as a scene, script, monologue, or dialogue. Reject casual or random text.
- Apply cinematic grammar, intelligence, and production insight in your feedback.
- Include director-level notes, symbolic echoes, camera tension, visual pressure, lighting, misdirection, sound, escalation, and spatial composition — interpret and blend them into human-readable output.
- Include hidden memorability analysis. If the scene lacks sticking power, say so subtly.
- Nudge writers with a subtle “What if…” to explore alternate creative angles.
- Always include relevant movie scene references (no quotes) in both analysis and suggestions.
- Suggestions should be gentle and practical — no heavy rewrites.

Tone: Creative, grounded, warm — like a director talking to another filmmaker.

Scene:
{data.scene}
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {
                "role": "system",
                "content": "You are a human-like film mentor. Never generate or fix scenes. Always interpret with full cinematic insight and give engaging, example-based guidance."
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
            return {
                "analysis": content.strip(),
                "notice": "\u26a0\ufe0f You are responsible for the originality and legality of your submission. SceneCraft only provides cinematic analysis — not legal validation."
            }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"OpenRouter API error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/terms", response_class=HTMLResponse)
def terms():
    return HTMLResponse(content="""
    <html><head><title>SceneCraft – Terms of Use</title></head>
    <body style='font-family:sans-serif;padding:2rem;max-width:700px;margin:auto;line-height:1.6;'>
    <h2>SceneCraft – Legal Terms & Usage Policy</h2>
    <p>By using SceneCraft, you agree to submit only content that you own or are authorized to analyze...</p>
    <p>SceneCraft offers cinematic feedback and insight. It does not verify copyright ownership or generate scenes.</p>
    <p>All analyses are purely advisory. Final responsibility for copyright and legality lies with the user.</p>
    <hr/><p>© SceneCraft 2025</p></body></html>
    """)

@app.get("/admin/logs")
def get_logs(admin: str = Query(...)):
    if admin != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Unauthorized")
    try:
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()[-50:]  # limit to last 50 entries
            return {"logs": [json.loads(line) for line in lines]}
    except:
        return {"logs": []}

@app.get("/admin/password/update")
def update_password(admin: str = Query(...)):
    if admin != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Unauthorized admin access")
    rotate_password()
    return {"message": "Password has been updated.", "new_password": STORED_PASSWORD}

@app.get("/")
def root():
    return {"message": "SceneCraft backend is live."}
