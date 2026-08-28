# -*- coding: utf-8 -*-
"""
config.py - Al-Faseelah World

Central configuration. All secrets are read from the .env file (see
.env.example) — never hardcode API keys in this file.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ===== API keys (from .env) =====
GEMINI_API_KEY       = os.getenv("GEMINI_API_KEY", "")
ELEVENLABS_API_KEY   = os.getenv("ELEVENLABS_API_KEY", "")

# ===== Supabase (from .env) =====
SUPABASE_URL         = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY         = os.getenv("SUPABASE_KEY", "")
# The BLE server needs write access to the sessions table; it falls back
# to SUPABASE_KEY when no separate service key is provided.
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", SUPABASE_KEY)

# ===== ElevenLabs voice IDs =====
ELEVENLABS_VOICE_ID        = "EXAVITQu4vr4xnSDxMaL"  # Bella (default test voice)
ELEVENLABS_VOICE_AR_FEMALE = "w4LX7bK479eHGM1k15Em"  # Habibah
ELEVENLABS_VOICE_AR_MALE   = "xvhpbk8otnNHtT3fjCpr"  # Omar
ELEVENLABS_VOICE_EN_FEMALE = "ocZQ262SsZb9RIxcQBOj"  # Lulu Lolipop
ELEVENLABS_VOICE_EN_MALE   = "raMcNf2S8wCmuaBcyI6E"  # Tyler Kurk

# Default voices used by the dialogue manager
ELEVENLABS_VOICE_AR = ELEVENLABS_VOICE_AR_FEMALE
ELEVENLABS_VOICE_EN = ELEVENLABS_VOICE_EN_FEMALE
