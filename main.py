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
You are SceneCraft AI — a highly trained cinematic story analyst.

Write a technically sound, unbiased, professional-grade analysis of the input scene or script excerpt.

Follow this internal evaluation logic — but do NOT display any structural terms or analysis labels:

- Scene progression and emotional beats
- Genre conventions and modern global audience resonance
- Depth of character motivation, psychological realism, and dramatic effectiveness
- Authenticity of dialogue and conflict grounded in real emotional cues
- Whether visuals, tone, sound, or editing are implied effectively (only if hinted)
- Influences of real-world storytelling or literary scene construction
- Structural or stylistic choices (e.g., nonlinear, visual storytelling, experimental pacing)

Output a natural, human-like response. If the scene lacks depth or dramatic weight, respectfully highlight it. Avoid flattery. Help the writer improve.

End with a single section titled “Suggestions” that offers actionable insights, phrased in a natural, empowering way (e.g., “You may want to…”, “It could help to…”, “Consider exploring…”).

Here is the scene:

\"\"\"{request.scene}\"\"\"
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a senior story analyst at a global film studio. "
                    "Your feedback is insightful, constructive, and creative. "
                    "You evaluate each scene with technical rigor and cinematic intelligence, "
                    "and offer empowering, unbiased suggestions in a human voice. "
                    "You NEVER show category names — only a final section called 'Suggestions'."
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

@app.get("/")
def root():
    return {"message": "SceneCraft backend is live."}
