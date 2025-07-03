from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request model
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

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://yourapp.com",  # Replace with your app domain
        "X-Title": "SceneCraft",
        "Content-Type": "application/json"
    }

    prompt = (
        "As a cinematic analyst, assess this scene strictly without quoting actual movie titles.\n"
        "Focus on:\n"
        "- Why the scene works / doesn’t work\n"
        "- Scene grammar\n"
        "- Realism (based on therapy transcripts, behavioral psychology, and natural dialogue)\n"
        "- Strong and weak points\n"
        f"\nScene:\n{request.scene}"
    )

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {"role": "system", "content": "You are a professional film scene analyst."},
            {"role": "user", "content": prompt}
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
