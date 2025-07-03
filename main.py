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

# Basic validation
def is_valid_scene(text: str) -> bool:
    greetings = ["hi", "hello", "hey", "good morning", "good evening"]
    if len(text.strip()) < 30:
        return False
    if text.lower().strip() in greetings:
        return False
    return True

# Main endpoint
@app.post("/analyze")
async def analyze_scene(request: SceneRequest):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing OpenRouter API key")

    if not is_valid_scene(request.scene):
        return {
            "error": "Please input a valid cinematic scene, dialogue, monologue, or script excerpt."
        }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://yourapp.com",
        "X-Title": "SceneCraft"
    }

    # Prompt to instruct AI for natural, benchmark-driven analysis (no labels shown)
    prompt = f"""
You are SceneCraft AI, a professional cinematic analyst trained to evaluate scenes as per studio-grade, globally recognized filmmaking and screenwriting practices.

Evaluate the scene naturally — relying on your understanding of:

- Scene progression and emotional beats
- Genre conventions and modern audience preferences
- Character psychology, realism, and dramatic effectiveness
- How well visuals, sound, tone, or editing are implied
- Real-event storytelling and literary scene-writing influences

Do not show or label any categories or techniques. Just write a cohesive, intelligent human-like critique that feels natural and film-professional.

Only at the end, add a clearly marked “Suggestions” section using natural, conversational phrasing like “You may want to...”, “It could help to...”, etc.

Here is the input scene:

\"\"\"{request.scene}\"\"\"
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {
                "role": "system",
                "content": "You are a studio-grade cinematic analyst. You analyze scenes using internal benchmarks but never mention them. Do not show section titles or category names, except for one final 'Suggestions' section written naturally."
            },
            {
                "role": "user",
                "content": prompt
            }
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
            return {
                "analysis": result["choices"][0]["message"]["content"]
            }
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"OpenRouter API error: {e.response.text}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Health check
@app.get("/")
def root():
    return {"message": "SceneCraft backend is live."}
