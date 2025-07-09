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

Evaluate the following scene or script excerpt using the most advanced cinematic and storytelling benchmarks. Do not generate content. Avoid listing or naming cinematic principles directly. Instead, base your insights and suggestions implicitly on these principles and explain through intuitive language and examples.

🔍 Include behavioral triggers and motivations behind character actions.
🎬 Provide director-level production insights (e.g., timing, blocking, visual rhythm, tonal modulation).
🔴 Mention visual pressure or frame-based tension when appropriate (e.g., "This moment holds visual pressure similar to the final hallway in *Birdman*").

In your analysis, draw from timeless cinematic storytelling patterns. When appropriate:
- Identify objects, lines, or moments that may need clearer connection or payoff later in the scene (e.g., a lighter introduced early but unused).
- Point out if something important is shown too directly instead of being revealed through behavior or tension.
- Suggest where leaving emotional meaning beneath the surface may improve the scene’s depth.
- Call out missed chances for tension where the audience knows more than the character.
- Highlight beats that could emotionally turn a character's arc full circle.
- Mention if character action contradicts their earlier behavior in a distracting way.
- Comment when a final line or image could leave a sharper echo, or if symmetry is lacking between beginning and end.
- Recommend strengthening cause-effect between setup and resolution.
- Gently point out where exposition might be replaced with action, subtext, or silence.
- If the story hinges on a goal, object, or pursuit, check if it drives the characters meaningfully.

Your analysis must reference relevant film moments (e.g., "This echoes the restaurant conversation in *The Irishman*") when they enhance clarity. Use these only to support insight—not for name-dropping.

Your output should include:
- A grounded and creative cinematic evaluation that touches on realism, structure, pacing, tone, and emotional authenticity.
- When offering feedback, include subtle rewrite hints using examples, not rules. (e.g., "You might hold back this reveal to build tension, like the motel sequence in *No Country for Old Men*.")
- End with a clearly labeled section called **Suggestions**, written naturally—not as bullet points, but in helpful, intuitive language.

Never include headings like “Scene Grammar” or internal categories. Never generate or complete any scenes.

Scene:
{data.scene}
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {
                "role": "system",
                "content": "You are a highly skilled film analyst. Never generate or complete scenes. Avoid stating benchmark names. Provide insight-rich evaluations and constructive feedback with relevant movie scene references."
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
                "notice": "⚠️ Note: You are responsible for the originality and legality of the submitted content. SceneCraft is for cinematic analysis only. No scene generation, reproduction, or copyright infringement is allowed."
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
    html_content = """
    <html>
      <head><title>SceneCraft Terms & Conditions</title></head>
      <body style="font-family: sans-serif; padding: 2rem;">
        <h2>SceneCraft – Terms & Conditions</h2>
        <p><strong>By using SceneCraft, you agree to the following:</strong></p>
        <ul>
          <li>You are submitting original content you own or have permission to use.</li>
          <li>SceneCraft provides only cinematic analysis—not content generation or legal validation.</li>
          <li>You are fully responsible for your submitted content.</li>
          <li>Usage is tracked for security and misuse prevention.</li>
        </ul>
        <p>Any misuse of SceneCraft for plagiarism, content scraping, or copyright violation may result in access revocation.</p>
        <hr>
        <p><em>All rights reserved © SceneCraft 2025</em></p>
      </body>
    </html>
    """
    return HTMLResponse(content=html_content)
