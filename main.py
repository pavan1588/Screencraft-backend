from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
import re

app = FastAPI()

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Scene input model
class SceneRequest(BaseModel):
    scene: str

# Scene validation logic
def is_valid_scene(text: str) -> bool:
    greetings = ["hi", "hello", "hey", "good morning", "good evening"]
    command_words = ["generate", "write a scene", "compose a script", "create a scene"]
    text_lower = text.lower()

    if len(text.strip()) < 30:
        return False
    if text_lower.strip() in greetings:
        return False
    if any(cmd in text_lower for cmd in command_words):
        return False

    has_dialogue = re.search(r"[A-Z][a-z]+\s*\(.*?\)|[A-Z]{2,}.*:|\[.*?\]", text)
    has_cinematic_cues = re.search(r"\b(INT\.|EXT\.|CUT TO:|FADE IN:)\b", text, re.IGNORECASE)
    if has_dialogue or has_cinematic_cues:
        return True

    return True if len(text.split()) > 20 and any(p in text_lower for p in ["character", "scene", "dialogue", "script", "monologue", "film"]) else False

@app.post("/analyze")
async def analyze_scene(request: SceneRequest):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing OpenRouter API key")

    if not is_valid_scene(request.scene):
        return {"error": "Please input a valid cinematic scene, dialogue, monologue, or script excerpt. Scene generation is not supported."}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://yourapp.com",
        "X-Title": "SceneCraft"
    }

    prompt = f"""
You are SceneCraft AI, a professional cinematic analyst.

Evaluate the following scene/script input based on the most comprehensive set of cinematic benchmarks. Your analysis must sound natural and intelligent without exposing internal logic, rules, or benchmarks.

Use the following benchmarks internally to guide your critique:

- Scene structure and emotional beats: setup, trigger, tension, conflict, climax, resolution
- Cinematic grammar and pacing: coherence, continuity, spatial logic, transitions, cinematic rhythm
- Genre effectiveness: whether the scene delivers the emotional and structural expectations of its genre, how it adapts to modern audience tastes
- Audience reaction prediction: how different types of audiences (festivals, mainstream, OTT, global cinema lovers) may react to this scene based on past works and current trends
- Realism and character psychology: is behavior authentic, emotionally truthful, rooted in believable motivation or therapy-style realism
- Use of visuals and emotion: visual cues, camera, lighting, spatial emotion, editing tempo — but only if implied or described
- Sound, tone, music: analyze sound design and BGM only if hinted or described by the writer, no assumptions
- Editing: visual tempo, spatial cohesion, rhythm, cutting pattern, style (linear/nonlinear)
- Tone and symbolism: layered meaning, metaphorical devices, emotional undertones
- Voice and originality: does the writing show a unique voice or perspective? Draw influence from great writers, directors, editors, and novelists (no names)
- Scene-building from literary and real-event influences: does the scene show influence of novelistic detail, experiential realism, or real-life structure
- Structure resonance: how this scene fits in a larger story arc and what it tells us about world-building
- Call out when the scene lacks cinematic depth, believability, or execution detail. Do not flatter. Do not generate scenes.

Additional storytelling principles to apply:
- Chekhov’s Gun
- Setup and Payoff
- The Iceberg Theory (Hemingway)
- Show, Don’t Tell
- Dramatic Irony
- Save the Cat
- Circular Storytelling
- The MacGuffin
- Symmetry & Asymmetry in Character Arcs
- The Button Line

Additional cinematic/directing principles to apply:
- Visual Grammar
- Symbolic Echoes
- The Rule of Three (visual/comic pacing)
- Camera Framing & Composition
- Blocking & Physical Distance
- Lighting for Emotional Tone
- Escalation (Scene Tension Curve)
- Cognitive Misdirection (via editing)
- Shot-Reverse-Shot for Conflict/Subtext
- Sound Design as Narrative Tool

Output should:
- Be cohesive, evaluative, and technically sharp
- Help writers and studios understand scene potential and weaknesses
- End with a clearly marked section titled "Suggestions" that contains constructive improvement ideas in plain natural language

Here is the scene for review:

{request.scene}
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {
                "role": "system",
                "content": "You are a professional cinematic scene analyst with expertise in realism, audience psychology, literary storytelling, and film production. Never generate new scenes. Provide deep analysis and only show one 'Suggestions' section at the end."
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
            content = result["choices"][0]["message"]["content"]

            if "generate" in content.lower():
                return {"error": "Scene generation is not supported."}
            return {"analysis": content.strip()}

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"OpenRouter API error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def root():
    return {"message": "SceneCraft backend is live."}
