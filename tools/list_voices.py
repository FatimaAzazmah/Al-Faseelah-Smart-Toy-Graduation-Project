import requests
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

response = requests.get(
    'https://api.elevenlabs.io/v1/voices',
    headers={'xi-api-key': config.ELEVENLABS_API_KEY}
)
voices = response.json().get('voices', [])
for v in voices:
    print(f"Name: {v['name']} | ID: {v['voice_id']} | Labels: {v.get('labels', {})}")
