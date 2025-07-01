from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openai
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

openai.api_key = os.getenv("OPENAI_API_KEY")

# ✅ Define request body schema
class SceneRequest(BaseModel):
    scene_text: str

@app.get("/")
def root():
    return {"message": "SceneCraft API is running"}

@app.get("/ping")
def ping():
    return {"status": "ok"}

@app.post("/analyze")
async def analyze_scene(scene: SceneRequest):
    try:
        if not scene.scene_text:
            return {"error": "No scene text provided."}

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "user",
                    "content": f"Analyze this movie scene:\n{scene.scene_text}"
                }
            ]
        )

        return {"analysis": response.choices[0].message.content}

    except openai.error.AuthenticationError:
        return {"error": "Invalid or missing OpenAI API key."}
    except Exception as e:
        return {"error": str(e)}
