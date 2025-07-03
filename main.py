from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
import re

app = FastAPI()

# CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Input structure
class SceneRequest(BaseModel):
    scene: str

# Basic input check
def is_valid_scene(text: str) -> bool:
    greetings = ["hi", "hello", "hey", "good morning", "good evening"]
    if len(text.strip()) < 30:
        return False
    if text.lower().strip() in greetings:
        return False
    return True

# Main route
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

    prompt = f"""
You are SceneCraft AI — a professional cinematic analyst working for a global production studio.

Analyze the input scene holistically. Internally consider:
- Scene progression and emotional beats
- Genre conventions and expectations from today’s global audiences
- Character realism, emotional depth, and behavioral credibility
- Audience relatability based on modern and timeless social contexts
- The psychological realism of responses and interactions
- Implied visual elements (camera, lighting, tone, editing) if present
- Influences from real-life events and literary scene-building techniques
- Structural originality (e.g. nonlinear storytelling, jump cuts, visual grammar)

Do not label or display categories or technical terms. Write like a seasoned human reader/analyst from a studio’s development team — insightful, fluent, unbiased.

Predict what modern viewers might feel while watching this scene and why it would or wouldn’t resonate.

End with one visible section titled “Suggestions” with clear, helpful, human-style creative advice. Use phrases like “You may want to…”, “It could help to…”, “Consider exploring…”

Here is the scene to analyze:

\"\"\"{request.scene}\"\"\"
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an experienced studio-grade cinematic analyst. "
                    "You analyze film scenes and scripts with internal understanding of emotional beats, genre, realism, originality, visual implication, and writing influence. "
                    "Never mention any category or technical term explicitly. "
                    "The output must feel like a natural human analysis ending in a 'Suggestions' section."
                )
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
