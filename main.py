from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
import re

app = FastAPI()

# CORS Middleware
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
You are SceneCraft AI, a studio-grade cinematic analyst trusted by global film production houses.

Perform a deeply technical and human-grade analysis of the cinematic input based on:

- Scene structure and beats
- Genre and modern audience resonance
- Realism, psychology, behavior
- Camera, sound, tone, editing, visual storytelling — only if clearly suggested
- Novelist and real-world storytelling influences (no names or quotations)

Do not use capitalized section headers, bullet points, numbered lists, or outline formatting. Never label categories. Do not define techniques. Do not explain what you're doing.

Write a flowing, human, paragraph-based analysis that feels like a professional's take. At the end, include a short section titled "Suggestions" — without calling attention to the cinematic categories behind them. These should be implementable ideas phrased in natural language.

Here is the input:
"""{request.scene}"""
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {
                "role": "system",
                "content": "You are a precise, studio-grade cinematic analyst. You never expose internal logic or headings. You avoid capitalized titles, outlines, or list formats. Only show a human-sounding analysis followed by a short section labeled 'Suggestions'."
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
        raise HTTPException(status_code=e.response.status_code, detail=f"OpenRouter API error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def root():
    return {"message"
