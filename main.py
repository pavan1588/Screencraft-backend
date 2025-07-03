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

Analyze the following scene without revealing structural or category headers. Your internal analysis must consider:

- Scene architecture (setup, trigger, tension, climax, resolution)
- Cinematic intelligence: grammar, pacing, structure
- Visual storytelling and editing: rhythm, emotional continuity, cutting patterns
- Genre: recognize and analyze the genre, how it aligns or deviates from expectations, and what modern global audiences expect from it
- Realism and psychology: character motivation, behavioral cues, emotional logic, using references to real events and psychological depth often found in literary fiction and biographies
- Sound design, music/BGM: only if these elements are implied or directly present in the scene
- Camera angles, movement: only if described or implied
- Lighting, tone, symbolism: only if narratively evident
- Editing style and timing: analyze pacing and transitions only if contextual clues allow
- Use intuitive reasoning influenced by directors, editors, novelists, and other cinematic minds — but without naming them

The output should:
1. Read like an intelligent human analyst speaking about the scene in natural language
2. Include an evaluation of why it works (or not) for a larger audience, especially for that genre
3. End with a section titled "Suggestions" with human-sounding recommendations, not robotic. Use phrases like “You may want to…”, “It could help to…”, “Consider exploring…”

Avoid commenting on elements like sound, lighting, or editing if the input does not indicate or imply them. Do not quote or name specific movies, filmmakers, or authors. Do not show internal logic or category names. Here is the input:

"""{request.scene}"""
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {"role": "system", "content": "You are a highly experienced, insightful cinematic analyst. You never use headers or show internal structure. You only show one visible 'Suggestions' heading at the end."},
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
