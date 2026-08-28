import requests
import pygame
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import time

# Default free voices that support Arabic
FREE_VOICES = [
    {"name": "Rachel",  "id": "21m00Tcm4TlvDq8ikWAM"},
    {"name": "Domi",    "id": "AZnzlk1XvdvUeBnXmlld"},
    {"name": "Bella",   "id": "EXAVITQu4vr4xnSDxMaL"},
    {"name": "Antoni",  "id": "ErXwobaYiN019PkySvjV"},
    {"name": "Josh",    "id": "TxGEqnHWrfWFTfGW9XjX"},
    {"name": "Arnold",  "id": "VR6AewLTigWG4xSOukaG"},
    {"name": "Adam",    "id": "pNInz6obpgDQGcFmaJgB"},
]

TEST_TEXT = "مرحباً يا أصدقائي! أنا فسيلة. هيا نلعب معاً!"

pygame.mixer.init()

for voice in FREE_VOICES:
    print(f"\nTesting: {voice['name']}...")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice['id']}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": config.ELEVENLABS_API_KEY
    }
    data = {
        "text": TEST_TEXT,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.75, "similarity_boost": 0.75}
    }
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 200:
        print(f"Playing {voice['name']}... (press Ctrl+C to skip)")
        audio = io.BytesIO(response.content)
        pygame.mixer.music.load(audio)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        print(f"{voice['name']} done.")
        input("Press Enter for next voice...")
    else:
        print(f"Error {response.status_code}: {response.text[:100]}")
