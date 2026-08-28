import os
import sys
import time
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# ---------- 1. Gemini (thinking OFF for speed) ----------
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

t0 = time.time()
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="You are Faseelah, a friendly plant character for children. Greet a 6-year-old boy named Adam with two short sentences in simple Modern Standard Arabic.",
    config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0)  # no thinking = fast
    )
)
text = response.text
print(f"[Gemini] {time.time()-t0:.1f}s")
print(text)

# ---------- 2. ElevenLabs TTS (Habibah voice) ----------
ELEVEN_KEY = os.getenv("ELEVENLABS_API_KEY")
import config
VOICE_ID = config.ELEVENLABS_VOICE_AR   # Habibah (Arabic female)

t0 = time.time()
r = requests.post(
    f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
    headers={"xi-api-key": ELEVEN_KEY, "Content-Type": "application/json"},
    json={
        "text": text,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
    }
)
with open("test_reply.mp3", "wb") as f:
    f.write(r.content)
print(f"[ElevenLabs] {time.time()-t0:.1f}s")

# ---------- 3. Play it ----------
os.system("mpg123 test_reply.mp3")
