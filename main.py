# === main.py ===
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os

app = FastAPI()

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request schema
class SceneRequest(BaseModel):
    scene: str

@app.get("/")
def read_root():
    return {"message": "SceneCraft backend is live!"}

@app.post("/analyze")
async def analyze_scene(request: SceneRequest):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing OpenRouter API key")

    scene_text = request.scene.strip()
    if len(scene_text) < 20 or scene_text.lower() in ["hi", "hello", "hey", "test"]:
        raise HTTPException(status_code=400, detail="Please enter a valid scene, script, monologue, or cinematic situation.")

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://yourapp.com",
        "X-Title": "SceneCraft",
        "Content-Type": "application/json"
    }

    system_prompt = (
        "You are a cinematic scene analyst with expertise in behavioral psychology, realism from therapy transcripts, "
        "and cinematic storytelling techniques. You must NOT generate scenes. Instead, analyze ONLY if the input is a valid scene, "
        "script, monologue, character interaction, or movie scenario.\n\n"
        "Do NOT respond to greetings or incomplete prompts. If the input is not valid scene material, return: 'Invalid input for cinematic analysis.'\n\n"
        "If valid, analyze the scene using:\n"
        "- Why the scene works / doesn’t work\n"
        "- Scene grammar (structure, setup, payoff)\n"
        "- Realism (authenticity, dialogue vs. monologue)\n"
        "- Behavioral cues (psychological depth, interaction style)\n"
        "- Strong and weak points (objectively highlighted)\n\n"
        "Avoid quoting real movies or titles. Use scene analysis logic only."
    )

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": scene_text}
        ]
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            return {"analysis": result["choices"][0]["message"]["content"]}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"OpenRouter API error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
