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
You are SceneCraft AI, a cinematic intelligence analyst. The user has submitted a scene or script excerpt.

Break down the analysis into the following categories in a natural, intelligent, human voice. Do not quote any known films or scenes.

---
1. **Scene Architecture**:
   - Setup
   - Trigger
   - Rising Tension
   - Climax
   - Resolution
   (If beats are missing, suggest how they might be added naturally.)

2. **Cinematic Intelligence**:
   - Scene Grammar (structure, rhythm, progression)
   - Realism & Psychological Authenticity
   - Dialogue/Subtext
   - Character Motivations & Emotional Arcs

3. **Visual & Emotional Language**:
   - Visual Cues (setting, symbols, body language)
   - Sound Design / Music / BGM
   - Camera Movement / Angles
   - Lighting, Tone, Symbolism

4. **Suggestions**:
   Offer recommendations in a kind, human tone. 
   Use phrases like “You may want to...” or “Consider adding…” to improve weak or missing aspects. 
   Be constructive, not robotic.

---
Analyze this input accordingly:

\"\"\"{request.scene}\"\"\"
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {"role": "system", "content": "You are a cinematic scene analyst. You speak in an insightful, human tone. You do not reference real movies."},
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
