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
    """Reject greetings, single words, and non-cinematic content"""
    greetings = ["hi", "hello", "hey", "good morning", "good evening"]
    if len(text.strip()) < 30:
        return False
    if text.lower().strip() in greetings:
        return False
    if len(re.findall(r'[A-Z]{2,}.*:', text)) >= 1 or re.search(r'\b(INT\.|EXT\.)\b', text):
        return True
    return True  # Allow full script or descriptive scenes

@app.post("/analyze")
async def analyze_scene(request: SceneRequest):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing OpenRouter API key")

    if not is_valid_scene(request.scene):
        return {"error": "Please input a valid scene, dialogue, monologue, or script for analysis."}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://yourapp.com",
        "X-Title": "SceneCraft",
        "Content-Type": "application/json"
    }

    prompt = (
        "As a cinematic analyst with deep understanding of global cinema, analyze the following input. "
        "Do not quote original scripts or suggest scene rewrites. Instead, focus on:\n\n"
        "- Why the scene/script works or doesn't work\n"
        "- Scene grammar and structure\n"
        "- Realism based on therapy transcripts, behavioral psychology, natural dialogue\n"
        "- Strong and weak points of storytelling\n\n"
        "Mention references to similar cinematic moments from global cinema as examples "
        "(without quoting their exact script). Also cite filmmaking literature or screenwriting principles where applicable. "
        "Distinguish between scene, monologue, dialogue, and full script based on input structure.\n\n"
        f"Analyze this:\n{request.scene}"
    )

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {"role": "system", "content": "You are a professional cinematic scene analyst."},
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
