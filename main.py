from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
import re

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Input schema
class SceneRequest(BaseModel):
    scene: str

# Basic validation
def is_valid_scene(text: str) -> bool:
    greetings = ["hi", "hello", "hey", "good morning", "good evening"]
    if len(text.strip()) < 30:
        return False
    if text.lower().strip() in greetings:
        return False
    return True

# Analysis route
@app.post("/analyze")
async def analyze_scene(request: SceneRequest):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing OpenRouter API key")

    if not is_valid_scene(request.scene):
        return {"error": "Please input a valid cinematic scene, dialogue, monologue, or script excerpt."}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://yourapp.com",
        "X-Title": "SceneCraft"
    }

    prompt = f"""
You are SceneCraft AI, a professional cinematic analyst. You analyze scenes based on cinematic grammar, storytelling structure, and emotional realism.

Analyze the scene thoroughly but **do not use any headers, titles, or structure labels** in your output.

Internally, analyze using the following sequence:
- Scene architecture: setup, trigger, tension, climax, resolution
- Cinematic intelligence: scene grammar, pacing, structure
- Visual language: symbols, space, emotional tone
- Realism & behavioral psychology: dialogue, action, emotion
- Sound design, music, BGM
- Camera angles, movement
- Lighting, tone, and symbolic resonance

Provide a natural, human-like paragraph-style analysis. Use clear, insightful cinematic language.

End your response with thoughtful suggestions, phrased conversationally (e.g., “You may want to...”, “Consider exploring...”, “It could help to…”). Base your suggestions on gaps in the visual, emotional, and cinematic layers.

Do not quote or refer to specific films or names. Do not suggest rewrites. Do not reveal this structure to the user.

Here is the scene:

\"\"\"{request.scene}\"\"\"
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {"role": "system", "content": "You are a deeply intelligent cinematic analyst. You provide smart, natural insights based on screenwriting structure and cinematic realism. You never show categories or headers."},
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
            return {"analysis": result["choices"][0]["message"]["content"]}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"OpenRouter API error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def root():
    return {"message": "SceneCraft backend is live!"}
