from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os

app = FastAPI()

# CORS setup
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

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://yourapp.com",
        "X-Title": "SceneCraft",
        "Content-Type": "application/json"
    }

    prompt = (
        "As a cinematic analyst with deep understanding of cinematic intelligence and benchmarks, "
        "assess the following scene. Focus strictly on analysis without quoting actual movie scripts or generating new scenes.\n"
        "Your output must include:\n"
        "- Why the scene works or doesn’t work\n"
        "- Scene grammar (structure, pacing, flow)\n"
        "- Realism based on therapy transcripts, natural dialogue, and behavioral psychology\n"
        "- Strong and weak points\n"
        "Use comparative cinematic examples without quoting original material."
    )

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": request.scene}
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
