from fastapi import FastAPI, Request, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import os, time, re, httpx, json
from datetime import datetime
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

class SceneRequest(BaseModel):
    scene: str

RATE_LIMIT = {}
STORED_PASSWORD = os.getenv("SCENECRAFT_PASSWORD", "SCENECRAFT-2024")
ADMIN_PASSWORD = os.getenv("SCENECRAFT_ADMIN_KEY", "ADMIN-ACCESS-1234")
PASSWORD_FILE = "scenecraft_password.json"
LOG_FILE = "scene_logs.json"
ROTATION_THRESHOLD = 50
PASSWORD_USAGE_COUNT = 0

PROFANITY = set(["fuck", "shit", "bastard", "chutiya", "gaand", "madarchod", "bhenchod", "bloody", "cunt", "randi", "lund", "suar", "gandu", "pimp", "sali", "mc", "bc"])
SLANG_HINTS = re.compile(r"\b(?:yaar|bro|dude|lit|dope|omg|bhai|abe|chod|jhand|bevda|patakha|item|tatti|lodu|jhakaas|senti|firangi|loot|tashan|swag|kaminey)\b", re.IGNORECASE)

def rate_limiter(ip, window=60, limit=10):
    now = time.time()
    RATE_LIMIT.setdefault(ip, [])
    RATE_LIMIT[ip] = [t for t in RATE_LIMIT[ip] if now - t < window]
    if len(RATE_LIMIT[ip]) >= limit:
        return False
    RATE_LIMIT[ip].append(now)
    return True

def is_valid_scene(text: str) -> bool:
    if any(word in text.lower() for word in PROFANITY):
        return False
    if len(text.strip()) < 30 or "generate" in text.lower():
        return False
    has_dialogue = re.search(r"[A-Z][a-z]+\s*\(.*?\)|[A-Z]{2,}.*:|\[.*?\]", text)
    has_cinematic_cues = re.search(r"\b(INT\.|EXT\.|CUT TO:|FADE IN:)\b", text, re.IGNORECASE)
    return bool(has_dialogue or has_cinematic_cues or len(text.split()) > 20)

def rotate_password():
    global STORED_PASSWORD, PASSWORD_USAGE_COUNT
    new_token = f"SCENECRAFT-{int(time.time())}"
    STORED_PASSWORD = new_token
    PASSWORD_USAGE_COUNT = 0
    with open(PASSWORD_FILE, "w") as f:
        json.dump({"password": new_token}, f)

def log_scene(ip: str, scene: str):
    log = {"ip": ip, "timestamp": str(datetime.now()), "scene": scene[:500]}
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(log) + "\n")

@app.post("/analyze")
async def analyze_scene(request: Request, data: SceneRequest, authorization: str = Header(None)):
    global PASSWORD_USAGE_COUNT, STORED_PASSWORD

    ip = request.client.host
    if not rate_limiter(ip):
        raise HTTPException(status_code=HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded.")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized: Missing token.")
    if authorization.split("Bearer ")[1] != STORED_PASSWORD:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid token.")

    if not is_valid_scene(data.scene):
        raise HTTPException(status_code=400, detail="Invalid input. Profanity or non-cinematic content detected.")

    PASSWORD_USAGE_COUNT += 1
    if PASSWORD_USAGE_COUNT >= ROTATION_THRESHOLD:
        rotate_password()

    log_scene(ip, data.scene)

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing OpenRouter API key")

    prompt = f"""
You are SceneCraft AI, a human-like cinematic scene analyst.

Evaluate this script based on:
- Director-level insight
- Scene structure (setup to resolution)
- Emotional realism
- Visual pressure (camera space, blocking, angles)
- Cinematic pacing, sound/mood only if implied
- Cultural and audience resonance
- Slang and urban/rural dialogue realism

Also apply:
- Show, Don’t Tell • Save the Cat • MacGuffin • Dramatic Irony • Iceberg Theory
- Visual Grammar • Symbolic Echoes • Cognitive Misdirection • Shot Composition
- No scene generation • End with one 'Suggestions' section

Scene:
{data.scene}
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {"role": "system", "content": "Act as a sharp, intelligent film analyst. Never generate scenes. Return only thoughtful critique."},
            {"role": "user", "content": prompt}
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=40) as client:
            response = await client.post("https://openrouter.ai/api/v1/chat/completions", headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://scenecraft.ai",
                "X-Title": "SceneCraft"
            }, json=payload)
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            content += (
                "\n\n⚠️ Legal Notice: SceneCraft is for educational review. You confirm rights to submitted content. "
                "SceneCraft does not store, generate, or claim ownership. Use respectfully."
            )
            return {"analysis": content.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unexpected server error: " + str(e))

@app.get("/terms", response_class=HTMLResponse)
def terms_page():
    return """
    <html><head><title>Terms & Conditions</title></head>
    <body style="font-family:sans-serif;padding:2rem;max-width:800px;margin:auto;color:#222;">
    <h2>SceneCraft Terms & Conditions</h2>
    <p><strong>1. Educational Use:</strong> SceneCraft is for script analysis and creative learning only.</p>
    <p><strong>2. Input Ownership:</strong> You must own or have permission to analyze the script text you submit.</p>
    <p><strong>3. No Generation:</strong> This service does not create or generate any original material.</p>
    <p><strong>4. Responsibility:</strong> Users are fully responsible for content they submit.</p>
    <p><strong>5. No Commercial Claims:</strong> Results must not be marketed as professional studio analysis.</p>
    <p><strong>6. Abuse/Slurs:</strong> Any abuse, hate, or offensive content will be blocked.</p>
    <p>© 2025 SceneCraft. All rights reserved.</p>
    </body></html>
    """

@app.get("/")
def root():
    return {"message": "SceneCraft backend is live."}
