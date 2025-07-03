from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
import re

app = FastAPI()

# Allow frontend access
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

def is_valid_scene(text: str) -> bool:
    """Reject greetings, short text, and clearly invalid inputs"""
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
        return {"error": "Please input a valid cinematic scene, dialogue, monologue, or script for analysis."}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://yourapp.com",  # Optional, update if required
        "X-Title": "SceneCraft",
        "Content-Type": "application/json"
    }

    # NEW PROMPT (reference-free, grounded in screencraft)
    prompt = (
        "You are SceneCraft AI, a cinematic analyst with deep knowledge of screenwriting, behavioral psychology, "
        "and storytelling structure. Analyze the following input strictly from a cinematic perspective.\n\n"
        "Avoid references to real films or scenes. Do not quote or suggest rewrites. Focus on:\n"
        "- Scene grammar, structure, pacing, and tone\n"
        "- Realism of character behavior and dialogue\n"
        "- Use of psychological authenticity, conflict, and narrative dynamics\n"
        "- Strengths and weaknesses of cinematic choices based on screenwriting principles\n\n"
        "Identify whether it appears to be a scene, monologue, dialogue, or full script and analyze accordingly.\n\n"
        f"Input:\n{request.scene}"
    )

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {"role": "system", "content": "You are a professional cinematic scene analyst. You do not quote or reference any specific films."},
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
