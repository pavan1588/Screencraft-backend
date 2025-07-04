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

# Scene input model
class SceneRequest(BaseModel):
    scene: str

# Scene validation logic
def is_valid_scene(text: str) -> bool:
    greetings = ["hi", "hello", "hey", "good morning", "good evening"]
    command_words = ["generate", "write a scene", "compose a script", "create a scene"]
    text_lower = text.lower()

    if len(text.strip()) < 30:
        return False
    if text_lower.strip() in greetings:
        return False
    if any(cmd in text_lower for cmd in command_words):
        return False

    # Check if input resembles a scene or script with characters/dialogue/cinematic elements
    has_dialogue = re.search(r"[A-Z][a-z]+\s*\(.*?\)|[A-Z]{2,}.*:|\[.*?\]", text)
    has_cinematic_cues = re.search(r"\b(INT\.|EXT\.|CUT TO:|FADE IN:)\b", text, re.IGNORECASE)
    if has_dialogue or has_cinematic_cues:
        return True

    # Allow naturalistic prose-style movie scenes or descriptions
    return True if len(text.split()) > 20 and any(p in text_lower for p in ["character", "scene", "dialogue", "script", "monologue", "film"]) else False

@app.post("/analyze")
async def analyze_scene(request: SceneRequest):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing OpenRouter API key")

    if not is_valid_scene(request.scene):
        return {"error": "Please input a valid cinematic scene, dialogue, monologue, or script excerpt. Scene generation is not supported."}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://yourapp.com",
        "X-Title": "SceneCraft"
    }

    prompt = f"""
You are SceneCraft AI, a professional cinematic analyst.

Analyze the following scene using studio-grade cinematic evaluation. Avoid using any visible structural or category headers. Internally benchmark against:

- Scene structure and emotional beats
- Genre conventions and audience trends
- Character psychology and dramatic credibility
- Visual, tonal, and sound elements (only if described or implied)
- Influence of literary scene-building and real-world narratives
- Nonlinear storytelling and modern realism
- Why the scene resonates (or not) with a larger audience, within its genre

The output should:
1. Read like a technically sound, creative studio-grade analysis
2. Provide critical insight and validation
3. Conclude with a section titled \"Suggestions\" offering actionable improvements (without sounding robotic)

Never generate new scenes. Do not name categories. Never quote or mention real films or authors.

Scene:
{request.scene}
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {
                "role": "system",
                "content": "You are a professional cinematic scene analyst trained in studio-grade screenwriting benchmarks and audience psychology. Your response must sound natural, detailed, and constructive. Never generate or suggest scenes. Only return insightful analysis ending with 'Suggestions'."
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
    return {"message": "SceneCraft backend is live."}
