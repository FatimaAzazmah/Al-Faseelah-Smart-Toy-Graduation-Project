import requests
import pygame
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

print("Testing ElevenLabs...")

try:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}"
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": config.ELEVENLABS_API_KEY
    }
    
    data = {
        "text": "Hello Obay! How are you? I am Alfaseelah World. lets go to the zoo...",
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.75,
            "similarity_boost": 0.75
        }
    }
    
    print("Audio generated OK...")
    response = requests.post(url, json=data, headers=headers)
    
    if response.status_code == 200:
        print("Playing Audio...")
        
        pygame.mixer.init()
        audio = io.BytesIO(response.content)
        pygame.mixer.music.load(audio)
        pygame.mixer.music.play()
        
        print("Audio finished...")
        
        import time
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
            
        print("Audio finished too!")
        
    else:
        print(f"Error: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"Exceppption: {e}")
