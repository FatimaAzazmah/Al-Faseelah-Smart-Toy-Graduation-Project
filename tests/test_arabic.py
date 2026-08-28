import requests
import pygame
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import time

pygame.mixer.init()

# Test with different models
TESTS = [
    {"voice": "Bella",  "id": "EXAVITQu4vr4xnSDxMaL", "model": "eleven_turbo_v2_5"},
    {"voice": "Antoni", "id": "ErXwobaYiN019PkySvjV", "model": "eleven_turbo_v2_5"},
    {"voice": "Adam",   "id": "pNInz6obpgDQGcFmaJgB", "model": "eleven_turbo_v2_5"},
]

TEXT = "Hello Ayham! Welcome to Al-Faseelah World. Let us learn and play together!"

for t in TESTS:
    print(f"\nTesting: {t['voice']} with {t['model']}...")
    response = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{t['id']}",
        headers={
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": config.ELEVENLABS_API_KEY
        },
        json={
            "text": TEXT,
            "model_id": t["model"],
            "voice_settings": {"stability": 0.75, "similarity_boost": 0.75}
        }
    )
    if response.status_code == 200:
        print("Playing...")
        pygame.mixer.music.load(io.BytesIO(response.content))
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        input("Enter for next...")
    else:
        print(f"Error: {response.status_code}")
