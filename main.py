from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
import re

app = FastAPI()

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Input model
class SceneRequest(BaseModel):
    scene: str

# Improved scene validator
def is_valid_scene(text: str) -> bool:
    text = text.strip()
    if len(text) < 20:
        return False

    text_lower = text.lower()
    if text_lower in ["hi", "hello", "hey", "good morning", "good evening"]:
        return False

    if any(cmd in text_lower for cmd in ["generate", "write", "compose", "create"]):
        return False

    has_script_format = bool(re.search(r"^[A-Z]{2,}(?:\s*\(.*?\))?$", text, re.MULTILINE))
    has_direction = bool(re.search(r"\b(INT\.|EXT\.|FADE TO|CUT TO|DISSOLVE TO)\b", text, re.IGNORECASE))

    return has_script_format or has_direction or len(text.split()) > 20

# Main analysis endpoint
@app.post("/analyze")
async def analyze_scene(request: SceneRequest):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing OpenRouter API key")

    if not is_valid_scene(request.scene):
        return {
            "error": "Please input a valid cinematic scene, dialogue, monologue, or script excerpt. Scene generation is not supported."
        }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://yourapp.com",
        "X-Title": "SceneCraft"
    }

    # Analysis prompt using benchmarks (unchanged)
    prompt = f"""
You are SceneCraft AI, a professional cinematic analyst.

Evaluate the following scene/script input based on cinematic benchmarks. Your analysis must sound natural and intelligent without revealing internal terms or logic.

Internally apply:
- Scene structure and emotional beats (setup, trigger, tension, conflict, climax, resolution)
- Cinematic grammar and pacing
- Genre conventions and audience resonance
- Character psychology and realism
- Visual/sound/editing tone (only if implied)
- Storytelling techniques: Chekhov’s Gun, Save the Cat, Iceberg Theory, etc.
- Cinematic direction: shot-reverse-shot, cognitive editing, lighting tone
- Voice and originality inspired by great filmmakers and novelists
- Literary realism or experiential cues from real-life events
- Call out lack of cinematic depth if applicable

Output must be human, unbiased, detailed, and end with one clearly marked section: "Suggestions".

Scene:
\"\"\"{request.scene}\"\"\"
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {
                "role": "system",
                "content": "You are a highly experienced cinematic analyst. Do not quote scripts, do not generate new scenes. Always end with a natural 'Suggestions' section."
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

            if "generate" in content.lower():
                return {"error": "Scene generation is not supported."}

            return {"analysis": content.strip()}

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"OpenRouter API error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def root():
    return {"message": "SceneCraft backend is live!"}
