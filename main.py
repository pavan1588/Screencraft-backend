from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
import re

app = FastAPI()

# Enable CORS for all origins (adjust if needed for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SceneRequest(BaseModel):
    scene: str

def is_valid_scene(text: str) -> bool:
    greetings = ["hi", "hello", "hey", "good morning", "good evening"]
    if len(text.strip()) < 30:
        return False
    if text.lower().strip() in greetings:
        return False
    return True

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
You are SceneCraft AI, a professional cinematic analyst.

Analyze the scene below as a deeply thoughtful and human-like expert in cinematic storytelling. Internally apply:

- Scene architecture (setup, trigger, tension, climax, resolution)
- Cinematic intelligence: structure, pacing, scene rhythm
- Realism and psychology: character behavior, motivations, and emotional logic — like a novelist or memoirist drawing from real-world insight
- Visual storytelling (camera, lighting, symbolism) — only if explicitly present or implied
- Editing, sound/music — only if directly suggested by the scene
- Literary depth: apply insights from biographical and literary storytelling
- Genre analysis: assess genre conventions and audience expectations globally

Output:
- Sound like a human film analyst, not a tool
- Explain why it resonates or not
- Do not reveal structural logic
- End with a section titled: Suggestions
- Do not name or quote real films, books, or creators

Here is the scene:
\"\"\"{request.scene}\"\"\"
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {"role": "system", "content": "You are a thoughtful, intelligent film analyst. You write like a human. Never show categories. End with only a 'Suggestions' section."},
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
