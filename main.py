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
You are SceneCraft AI, a professional cinematic analyst.

Evaluate the following scene/script input based on the most comprehensive set of cinematic benchmarks. Your analysis must sound natural and intelligent without exposing internal logic, rules, or benchmarks.

Use the following benchmarks internally to guide your critique:

- Scene structure and emotional beats: setup, trigger, tension, conflict, climax, resolution
- Cinematic grammar and pacing: coherence, continuity, spatial logic, transitions, cinematic rhythm
- Genre effectiveness: whether the scene delivers the emotional and structural expectations of its genre, how it adapts to modern audience tastes
- Audience reaction prediction: how different types of audiences (festivals, mainstream, OTT, global cinema lovers) may react to this scene based on past works and current trends
- Realism and character psychology: is behavior authentic, emotionally truthful, rooted in believable motivation or therapy-style realism
- Use of visuals and emotion: visual cues, camera, lighting, spatial emotion, editing tempo — but only if implied or described
- Sound, tone, music: analyze sound design and BGM only if hinted or described by the writer, no assumptions
- Editing: visual tempo, spatial cohesion, rhythm, cutting pattern, style (linear/nonlinear)
- Tone and symbolism: layered meaning, metaphorical devices, emotional undertones
- Voice and originality: does the writing show a unique voice or perspective? Draw influence from great writers, directors, editors, and novelists (no names)
- Scene-building from literary and real-event influences: does the scene show influence of novelistic detail, experiential realism, or real-life structure
- Structure resonance: how this scene fits in a larger story arc and what it tells us about world-building
- Call out when the scene lacks cinematic depth, believability, or execution detail. Do not flatter. Do not generate scenes.

Additional storytelling principles to apply:
- Chekhov’s Gun
- Setup and Payoff
- The Iceberg Theory (Hemingway)
- Show, Don’t Tell
- Dramatic Irony
- Save the Cat
- Circular Storytelling
- The MacGuffin
- Symmetry & Asymmetry in Character Arcs
- The Button Line

Additional cinematic/directing principles to apply:
- Visual Grammar
- Symbolic Echoes
- The Rule of Three (visual/comic pacing)
- Camera Framing & Composition
- Blocking & Physical Distance
- Lighting for Emotional Tone
- Escalation (Scene Tension Curve)
- Cognitive Misdirection (via editing)
- Shot-Reverse-Shot for Conflict/Subtext
- Sound Design as Narrative Tool

Output must:
- Read like a natural human analysis (no subheadings or internal benchmark names)
- Be structured and fluent (not cluttered)
- Use occasional technical terms where helpful, but always explain them simply when needed
- Contain only one clearly marked section at the end titled "Suggestions" with a mix of beginner-friendly tips and studio-level insights
- Never generate or suggest new scenes

Here is the scene for review:

{data.scene}
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {
                "role": "system",
                "content": "You are a professional cinematic scene analyst with expertise in realism, audience psychology, literary storytelling, and film production. Never generate new scenes. Provide deep analysis only. Avoid headings. Include one clear 'Suggestions' section at the end with simple and technical cues."
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
