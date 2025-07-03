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

    # Enriched prompt for high-fidelity cinematic analysis
    prompt = f"""
You are SceneCraft AI — a human-like cinematic analyst working at a global film studio.

Your job is to analyze the following scene like a top development executive would — drawing from benchmarks in cinema, literature, psychology, and real-world experience.

Write a cohesive, natural, fluent response (no lists, no labels, no categories), but analyze based on the following **internally**:

- Scene flow and emotional beats
- Structural integrity (linear or nonlinear)
- Originality of writing style or narrative choices
- Genre alignment and modern audience expectations
- Behavioral realism based on real-world emotional reactions
- Scene relatability to real-life situations and global culture
- Effectiveness of subtext, pacing, rhythm, or visual language (if implied)
- Use of contemporary and timeless storytelling principles found in novels, real events, and globally acclaimed screenwriting

Also predict how this might resonate with a modern audience — what they would feel, and why.

At the end, include one final visible section titled “Suggestions” with natural, human phrasing (e.g., “You may want to…”, “It could help to…”, “Consider exploring…”). Do not reveal any structural markers or cinematic categories in the output.

Here is the scene input:

\"\"\"{request.scene}\"\"\"
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {
                "role": "system",
                "content": "You are a professional cinematic analyst. You follow all internal benchmarks for scene, realism, originality, structure, and genre, but never label or show categories. Your response must read like a natural human evaluation and end with a 'Suggestions' section only."
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

@app.get("/")
def root():
    return {"message": "SceneCraft backend is live."}
