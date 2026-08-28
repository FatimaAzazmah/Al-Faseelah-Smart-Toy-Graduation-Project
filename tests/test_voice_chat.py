# -*- coding: utf-8 -*-
# Full voice loop test: Mic -> Whisper -> Gemini -> ElevenLabs -> Speaker
import os, sys, time, subprocess
import warnings
warnings.filterwarnings('ignore')
from dotenv import load_dotenv
from google import genai
from google.genai import types
import whisper
import requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from prompts import build_system_prompt, build_activity_task

load_dotenv()

# ---- Load Whisper once (takes ~10s on Pi) ----
print("Loading Whisper model...")
stt = whisper.load_model("base")
print("Whisper ready!")

# ---- Gemini chat setup ----
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
task = build_activity_task(
    activity_text="ما هو لون الشمس؟",
    expected_answers="أصفر، ذهبي",
    ai_hint="انظر إلى السماء في النهار",
)
system = build_system_prompt("آدم", 6, task, parent_goal="saying thank you", simplified=False)
chat = client.chats.create(
    model="gemini-2.5-flash",
    config=types.GenerateContentConfig(
        system_instruction=system,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    ),
)

# ---- ElevenLabs speak ----
def speak(text):
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{os.getenv('HABIBAH_VOICE_ID')}",
        headers={"xi-api-key": os.getenv("ELEVENLABS_API_KEY"), "Content-Type": "application/json"},
        json={"text": text, "model_id": "eleven_turbo_v2_5",
              "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}},
    )
    if r.status_code == 200:
        with open("reply.mp3", "wb") as f: f.write(r.content)
        subprocess.run(["mpg123", "-q", "reply.mp3"])
    else:
        print("TTS ERROR:", r.text[:200])

# ---- Record from mic (5 seconds) ----
def record(seconds=6):
    print("\n" + "="*30 + "\n🎤🎤🎤  GO! SPEAK NOW!  🎤🎤🎤\n" + "="*30)
    subprocess.run(["arecord", "-d", str(seconds), "-f", "S16_LE", "-r", "16000",
                    "-c", "1", "child.wav"], stderr=subprocess.DEVNULL)
    print("Processing...")

# ---- The loop ----
print("\n=== Faseelah Voice Test — Ctrl+C to stop ===")
r = chat.send_message("ابدئي النشاط الآن")
print("Faseelah:", r.text)
speak(r.text)

while True:
    input("\nPress ENTER, wait for GO, then speak...")
    record(5)
    t0 = time.time()
    result = stt.transcribe("child.wav", language="ar")
    child_text = result["text"].strip()
    print(f"[Whisper {time.time()-t0:.1f}s] Child said: {child_text}")
    if not child_text:
        print("(empty — try again, speak louder)")
        continue
    t0 = time.time()
    r = chat.send_message(child_text)
    print(f"[Gemini {time.time()-t0:.1f}s] Faseelah: {r.text}")
    speak(r.text)
