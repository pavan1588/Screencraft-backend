from fastapi import FastAPI, HTTPException, Request, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.responses import HTMLResponse
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
    rewrite_requests = [
        "rewrite this",
        "can you rewrite",
        "write a better version",
        "fix this scene",
        "make this better",
        "reword this",
        "polish this scene",
        "improve this dialogue",
        "generate a version",
        "regenerate",
        "compose a new scene"
    ]
    text_lower = text.lower()

    # Block obvious generation/rewrite prompts
    if any(req in text_lower for req in rewrite_requests):
        return False

    if len(text.strip()) < 30 or text_lower in greetings:
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
        return {"error": "❌ SceneCraft only analyzes valid cinematic scenes, dialogues, or monologues. It cannot accept generation or rewrite requests."}

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing OpenRouter API key")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://screencraft.app",
        "X-Title": "SceneCraft"
    }

    prompt = f"""
You are SceneCraft AI — a creative mentor and expert cinematic analyst.

You must:
- Understand what makes a scene work (structure, realism, subtext, tone, symbolism, emotion, blocking, direction, cinematic grammar)
- Never generate, rewrite, or complete scenes
- Do NOT paraphrase, reword or invent new lines or versions
- Always evaluate with subtle, helpful suggestions — never rewrite
- Include references only for analysis (e.g., scenes like the diner in *Heat*)
- Blend classic and modern cinema insight
- Include visual tension, emotional beats, genre awareness, memorability and story rhythm
- End with Suggestions and Exploration Angle
Scene:
{data.scene}
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {
                "role": "system",
                "content": "You are SceneCraft AI — a creative analyst. Never generate, rewrite, or compose content. Offer cinematic feedback only."
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
                "notice": "⚠️ This is a creative analysis only. You are responsible for the content and its originality."
            }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"OpenRouter API error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/terms", response_class=HTMLResponse)
def terms():
    html = """
    <!DOCTYPE html>
    <html>
      <head><title>SceneCraft – Terms of Use</title></head>
      <body style='font-family: sans-serif; padding: 2rem; max-width: 700px; margin: auto; line-height: 1.6;'>
        <h2>SceneCraft – Legal Terms & Usage Policy</h2>
        <h3>User Agreement</h3>
        <p>By using SceneCraft, you agree to submit only content that you own or are authorized to analyze. This platform is for creative cinematic analysis only.</p>

        <h3>Disclaimer</h3>
        <p>SceneCraft is not a generator. It analyzes your scene using principles of filmmaking and storytelling. You remain responsible for submitted content.</p>

        <h3>Usage Policy</h3>
        <ul>
          <li>Submit scenes, monologues, dialogues, or excerpts — not random text or rewrite prompts.</li>
          <li>Do not submit third-party copyrighted material.</li>
          <li>All analysis is creative and not legal validation.</li>
        </ul>

        <h3>Copyright Responsibility</h3>
        <p>You are fully responsible for the originality and rights of the content you submit. SceneCraft does not store or certify authorship.</p>

        <h3>About SceneCraft</h3>
        <p>SceneCraft is a cinematic assistant. It brings together story grammar, realism, editing cues, and audience insight to help writers and creators improve their scenes creatively.</p>

        <p style=\"margin-top: 2rem;\"><em>Created for filmmakers, storytellers, and writers who want sharper scenes, not shortcuts.</em></p>
        <hr />
        <p>© SceneCraft 2025. All rights reserved.</p>
      </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.get("/")
def root():
    return {"message": "SceneCraft backend is live."}
