from fastapi import FastAPI, HTTPException, Request, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
import re
import time
import json
from starlette.responses import HTMLResponse
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
        return {"error": "Enter a valid scene or script excerpt for analysis. Scene generation is not supported."}

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
You are SceneCraft AI — a wise, creative, and cinematic mentor trained in every aspect of storytelling, screenwriting, direction, editing, and visual storytelling across eras and cultures.

Your job is to analyze scenes as if you're mentoring a writer or filmmaker. Never generate content. Focus only on what the user gave you.

Here’s how you should respond:
- Make your feedback inspiring, practical, and human.
- Avoid academic terms. Use movie examples or intuitive phrases instead of naming concepts like 'Chekhov’s Gun'.
- Be honest, but never discouraging. Speak with the voice of an experienced screen doctor or story consultant.
- Help the user find clarity, rhythm, emotional connection, tension, character drive, and cinematic strength in the scene.
- Do not reference cinematic 'rules' or internal benchmarks. Use creative analogies, examples, and friendly advice.
- Highlight strengths and areas for improvement naturally.

When needed, compare moments in the user’s scene to great scenes from world cinema — subtly, without quoting lines.

🎬 Suggestions section must include helpful, fun rewrite ideas that stir the writer’s imagination. (e.g., “You might let the tension build longer, like that quiet kitchen moment in *A Separation*.”)

🎯 Your tone: human, grounded, warm, film-literate — like a screenwriter’s best creative partner.

Scene:
{data.scene}
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {
                "role": "system",
                "content": "You are a skilled cinematic mentor. You never generate scenes. You analyze real cinematic material with creative, example-rich, and human feedback."
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
                "notice": "⚠️ You are responsible for the legality and originality of your submission. SceneCraft provides cinematic analysis only — not legal validation or copyright protection."
            }
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

@app.get("/terms", response_class=HTMLResponse)
def terms():
    html = """
    <html>
      <head><title>SceneCraft – Terms & Conditions</title></head>
      <body style="font-family: sans-serif; padding: 2rem; max-width: 700px; margin: auto; line-height: 1.6;">
        <h2>SceneCraft – Legal Notice & Terms of Use</h2>

        <h3>Legal Disclaimer</h3>
        <p>SceneCraft is an AI-powered cinematic analysis tool. It does not generate, reproduce, or store any copyrighted scenes. It only analyzes user-submitted content in real-time using benchmarked cinematic knowledge.</p>

        <h3>User Agreement</h3>
        <p>By using SceneCraft, you confirm that you are submitting original content that you own or are authorized to analyze. You agree not to submit copyrighted material you do not have rights to.</p>

        <h3>Usage Policy</h3>
        <ul>
          <li>SceneCraft is strictly for cinematic analysis only.</li>
          <li>SceneCraft does not generate or edit scripts, nor does it produce original content.</li>
          <li>Abuse of this tool may result in blocked access.</li>
        </ul>

        <h3>Copyright Warning</h3>
        <p>You are solely responsible for the legality of the material you submit. Submitting copyrighted material you do not own may violate local and international copyright laws.</p>

        <h3>Content Logging</h3>
        <p>All usage is tracked anonymously for rate limiting and content responsibility.</p>

        <p style="margin-top: 2rem;"><em>SceneCraft is a creative companion, not a publishing platform. Use it wisely.</em></p>
        <hr />
        <p>© SceneCraft 2025. All rights reserved.</p>
      </body>
    </html>
    """
    return HTMLResponse(content=html)
