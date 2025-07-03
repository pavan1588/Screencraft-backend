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
        return {"error": "Please input a valid cinematic scene, dialogue, monologue, or script excerpt."}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://yourapp.com",
        "X-Title": "SceneCraft"
    }

    prompt = f"""
You are SceneCraft AI, a studio-grade cinematic analyst trusted by global film production houses.

Perform a deep, technical analysis of the provided cinematic input using established cinematic principles. Your evaluation should include:

- Scene Architecture: structure, pacing, beats (setup, trigger, tension, climax, resolution)
- Genre Alignment: identify genre, evaluate if the scene fulfills core genre conventions, and how well it resonates with contemporary global audiences
- Cinematic Intelligence: story logic, transitions, scene grammar, dramatic arc, stakes, tension
- Realism & Psychology: character actions, behavioral credibility, emotional realism
- Visual Language (only when clearly present): camera, lighting, blocking, symbolism
- Sound/Music/Editing (only if explicitly referenced or contextually inferred)
- Cohesion and implementation feasibility at the production level
- Remove speculation; no guesses. Make evidence-based observations

Deliver a studio-level analysis in a cohesive, technically sound, and professional tone.
Do not expose internal categories or structures in the output. Write as a high-level studio analyst.

End only with a section titled: Suggestions — with clear, implementable, technically feasible improvements.
Do not quote specific filmmakers, films, or novels. Do not use assumptions about intent unless inferred directly from the text.

Here is the input:
\"\"\"{request.scene}\"\"\"
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {"role": "system", "content": "You are a precise, unbiased, studio-grade cinematic analyst. Avoid assumptions. Only show a 'Suggestions' section in the end."},
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
