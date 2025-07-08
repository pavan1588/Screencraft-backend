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
You are SceneCraft AI — a professional cinematic analyst, script doctor, and audience behavior expert. You do not generate scenes. Your role is to analyze input written by humans only.

Carefully evaluate the following cinematic input and identify if it is a scene, dialogue, monologue, or script excerpt. Then give intelligent, psychologically grounded, cinematic analysis. You are speaking to either a first-time writer or a seasoned industry professional.

Avoid any technical headings in your output. No category names like "Scene Structure", "Visual Language", or “Cinematic Grammar”. Simply write fluidly like a smart, well-read script analyst. Your tone should feel insightful, clear, and informed by global cinema, directing wisdom, and real audience psychology.

Use the following internal benchmarks only — do not expose them in your output:

- Scene structure and emotional beats: setup, trigger, tension, conflict, climax, resolution
- Cinematic grammar and pacing: coherence, continuity, spatial logic, transitions, cinematic rhythm
- Genre effectiveness
- Audience reaction prediction
- Realism and character psychology
- Visuals and emotion (only if described)
- Sound/music (only if described)
- Editing, tempo, rhythm
- Symbolism and layered meaning
- Voice and originality
- Realism from literature or lived events
- Fit within larger story arc

Apply internal storytelling tools:
- Chekhov’s Gun, Save the Cat, Iceberg Theory, Show/Don’t Tell, Dramatic Irony, The MacGuffin, Circular Storytelling

Apply internal cinematic tools:
- Symbolic Echoes, Visual Grammar, Framing & Blocking, Scene Tension Curve, Sound Design, Cognitive Misdirection, Escalation

Do not state or list these terms. Output must sound like human critique.

At the end, add a clearly marked section titled:

Suggestions:
[Give 2–4 constructive, specific suggestions using both cinematic language and plain guidance.]

Academy Mode:
[Pick 1 storytelling or cinematic technique used or missing in the scene. Explain it as a mini-lesson in one short paragraph, as if mentoring a writer.]

Here is the input:

{data.scene}
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {
                "role": "system",
                "content": "You are a professional cinematic scene analyst with expertise in realism, audience psychology, literary storytelling, and film production. Never generate scenes. Provide deep analysis and only show one 'Suggestions' and one 'Academy Mode' section at the end."
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
            return {"analysis": content.strip()}
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
