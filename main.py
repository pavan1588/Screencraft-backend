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

Analyze the scene below as a deeply thoughtful and human-like expert in cinematic storytelling. Internally apply:

- Scene architecture (setup, trigger, tension, climax, resolution)
- Cinematic intelligence: structure, pacing, scene rhythm
- Realism and psychology: evaluate character behavior, motivations, and emotions like a novelist drawing from real-world stories and human behavior
- Visual storytelling (camera movement, angles, lighting, symbolism) — only if inferred or directly described
- Editing, sound design, music/BGM — only when cues are present or strongly implied in the text
- Consider storytelling techniques found in historical fiction, biographies, and literary novels — apply their influence naturally
- Evaluate genre and audience alignment: what makes it compelling or disconnected from contemporary global audiences

Output:
- Write in a natural, human, intelligent voice without showing analysis structure
- Explain why the scene may or may not work and why it resonates (or doesn’t)
- Only display one titled section at the end: Suggestions
- Do not name or quote specific works or authors
- Do not comment on sound/music/lighting/etc. unless contextually relevant

Here is the scene:
"""{request.scene}"""
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {"role": "system", "content": "You are a highly experienced, insightful cinematic analyst. You write like a thoughtful human. Never show internal analysis structure. Only end with a 'Suggestions' section."},
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
