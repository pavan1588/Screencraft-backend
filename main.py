from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import openai
import os

app = FastAPI()

# ✅ CORS Middleware to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Load OpenAI API Key from environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.get("/")
def root():
    return {"message": "SceneCraft API is running"}

# ✅ Keepalive route for testing
@app.get("/ping")
def ping():
    return {"status": "ok"}

# ✅ Main analysis route with full error handling
@app.post("/analyze")
async def analyze_scene(request: Request):
    try:
        body = await request.json()
        scene_text = body.get("scene_text", "")

        if not scene_text:
            return {"error": "No scene text provided."}

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # You can switch to gpt-4 if you have access
            messages=[
                {
                    "role": "user",
                    "content": f"Analyze this movie scene for narrative beats, tone, emotion and cinematic structure:\n{scene_text}"
                }
            ]
        )

        return {"analysis": response.choices[0].message.content}

    except openai.error.AuthenticationError:
        return {"error": "Invalid or missing OpenAI API key."}
    except Exception as e:
        return {"error": str(e)}

