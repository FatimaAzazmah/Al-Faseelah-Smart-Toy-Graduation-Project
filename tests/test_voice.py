import requests
import pygame
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# Test Arabic voices
VOICE_ID = "w4LX7bK479eHGM1k15Em"  # Habibah

url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"

headers = {
    "Accept": "audio/mpeg",
    "Content-Type": "application/json",
    "xi-api-key": config.ELEVENLABS_API_KEY
}

data = {
    "text": "مرحباً يا أصدقائي! أنا فسيلة. هيا نلعب ونتعلم معاً في عالم الفسيلة!",
    "model_id": "eleven_multilingual_v2",
    "voice_settings": {
        "stability": 0.75,
        "similarity_boost": 0.75
    }
}

print("Generating audio...")
response = requests.post(url, json=data, headers=headers)

if response.status_code == 200:
    print("Playing...")
    pygame.mixer.init()
    audio = io.BytesIO(response.content)
    pygame.mixer.music.load(audio)
    pygame.mixer.music.play()
    import time
    while pygame.mixer.music.get_busy():
        time.sleep(0.1)
    print("Done!")
else:
    print(f"Error: {response.status_code} - {response.text}")
