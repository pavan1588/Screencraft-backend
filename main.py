from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
import re
import nltk
from textstat import flesch_reading_ease

nltk.download("punkt")

app = FastAPI()

# CORS settings
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
    banned_keywords = [
        "give", "provide", "generate", "write", "create", "compose",
        "produce", "draft", "develop", "construct", "build", "make up", "invent"
    ]
    text_lower = text.lower()
    if len(text.strip()) < 30:
        return False
    if text_lower.strip() in greetings:
        return False
    if any(word in text_lower for word in banned_keywords):
        return False
    return True

def analyze_scene_readability(text: str) -> str:
    score = flesch_reading_ease(text)
    if score < 40:
        return "The scene uses complex language that may reduce accessibility."
    elif score < 70:
        return "The language strikes a balance between sophistication and readability."
    else:
        return "The language is highly accessible, aiding flow and comprehension."

@app.post("/analyze")
async def analyze_scene(request: SceneRequest):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing OpenRouter API key")

    if not is_valid_scene(request.scene):
        return {
            "error": "Please input a valid cinematic scene, dialogue, monologue, or script excerpt for analysis. Scene generation is not supported."
        }

    readability = analyze_scene_readability(request.scene)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://yourapp.com",
        "X-Title": "SceneCraft"
    }

    prompt = f"""
You are SceneCraft AI, a professional cinematic analyst. Do not generate or invent new scenes. Your job is only to analyze the submitted input.

Use the following principles internally, but do not name them in the output:
- Scene structure and emotional beats (setup, trigger, tension, climax, resolution)
- Genre conventions and how they influence audience reaction
- Cinematic grammar, editing patterns, and narrative flow
- Realism, behavior psychology, and audience believability
- Visual storytelling and sound (only if described or implied)
- Literary scene-building inspired by novels and real-world narratives

End with a section titled "Suggestions". Do not expose internal logic or cinematic terminology.

Here is the scene:
\"\"\"{request.scene}\"\"\"

Language Note: {readability}
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a professional cinematic analyst. Do not generate or imagine scenes. "
                    "Evaluate only what's written. Use cinematic intelligence and realism benchmarks, "
                    "but do not display those terms. End with humanlike suggestions only."
                )
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
            return {"analysis": result["choices"][0]["message"]["content"]}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"OpenRouter API error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def root():
    return {"message": "SceneCraft backend is live!"}
