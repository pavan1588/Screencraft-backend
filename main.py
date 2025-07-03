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
You are SceneCraft AI, a cinematic expert trained in storytelling structure, realism, behavioral psychology, and visual storytelling.

The user has submitted a scene, dialogue, monologue, or script excerpt.

Analyze it deeply using the following parameters **internally**, but do not mention these terms in the output:

- Scene beats: setup, trigger, tension, climax, resolution
- Scene grammar and structure
- Realism, character behavior, dialogue psychology
- Visual and emotional cinematic elements (camera, music, sound, visual cues, symbolic design)

Only return **suggestions** that will improve the cinematic value of the input. These must be in a natural, professional tone. Avoid titles, headers, or categories in your output. Use phrasing like:
- “You may want to consider...”
- “It could help to introduce...”
- “Try using...”
- “To enhance this moment…”

Do not quote or reference real films or scripts. Do not generate or rewrite the input. Focus only on thoughtful human-style cinematic suggestions.

Here is the input for analysis:

\"\"\"{request.scene}\"\"\"
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {"role": "system", "content": "You are a cinematic scene analyst. Speak with intelligent, professional tone. Offer only suggestions. Do not use headers."},
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
