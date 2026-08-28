# -*- coding: utf-8 -*-
"""
dialogue_manager.py - Al-Faseelah World

Voice interaction helpers used by main_ai.py:
  speak()  — ElevenLabs neural TTS (with a gTTS fallback)
  listen() — records from the USB microphone and transcribes with Whisper

Also contains the legacy zone-dialogue session loop used by
main_integrated.py before the full Gemini pipeline (main_ai.py) replaced it.
"""
import io, json, logging, random, time
from datetime import datetime, timezone
import numpy as np
import pygame, requests, scipy.signal, sounddevice as sd, whisper
from gtts import gTTS
from supabase import create_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

from config import ELEVENLABS_API_KEY, SUPABASE_URL, SUPABASE_KEY, ELEVENLABS_VOICE_AR, ELEVENLABS_VOICE_EN

ELEVENLABS_MODEL   = "eleven_turbo_v2_5"
SUPABASE_URL_CLEAN = SUPABASE_URL.replace("/rest/v1/", "")
supabase           = create_client(SUPABASE_URL_CLEAN, SUPABASE_KEY)
MIC_RATE, WHISPER_RATE = 44100, 16000

def _find_mic_device():
    try:
        devices = sd.query_devices()
        for i, d in enumerate(devices):
            name = d.get("name", "")
            if d.get("max_input_channels", 0) > 0 and "PnP" in name:
                log.info(f"[MIC] Using device {i}: {name}")
                return i
    except Exception as e:
        log.warning(f"[MIC] auto-detect failed: {e}")
    log.warning("[MIC] falling back to default input device (0)")
    return 0

MIC_DEVICE = _find_mic_device()

log.info("[Whisper] Loading model...")
WHISPER_MODEL = whisper.load_model("base")
log.info("[Whisper] Ready!")
pygame.mixer.init()

# Local fallback profiles used when no BLE/Supabase profile is available.
# Fill child_id/parent_id with real row ids from your own Supabase project.
CHILD_PROFILES = {
    "RFID_TAG_001": {"name":"Adam","name_ar":"آدم","language":"ar","age":4,"child_id":"","parent_id":""},
    "RFID_TAG_002": {"name":"Sara","name_ar":"سارة","language":"ar","age":8,"child_id":"","parent_id":""},
    "TEST":         {"name":"Test Child","name_ar":"طفل تجريبي","language":"ar","age":5,"child_id":"","parent_id":""},
}
ZONES = {"home":{"ar":"المنزل","en":"Home"},"school":{"ar":"المدرسة","en":"School"},"mosque":{"ar":"المسجد","en":"Mosque"},"dynamic":{"ar":"منطقة الحيوانات","en":"Zoo"}}
DIALOGUES = {
    "home":    {"ar":["مرحباً بك في المنزل! هل غسلت يديك اليوم؟","المنزل مكان جميل! ماذا تحب أن تفعل هنا؟","هيا نتعلم آداب البيت معاً!"],"en":["Welcome to the Home zone! Did you wash your hands today?","Home is a great place to learn daily routines!","Let us learn good habits together at home!"]},
    "school":  {"ar":["أهلاً بك في المدرسة! هل أنت مستعد للتعلم؟","المدرسة مكان رائع! ماذا تحب أن تتعلم اليوم؟","هيا نتعلم الحروف والأرقام معاً!"],"en":["Welcome to School! Are you ready to learn?","School is amazing! What would you like to learn today?","Let us count and read together!"]},
    "mosque":  {"ar":["مرحباً بك في المسجد! هيا نتعلم سورة الفاتحة.","المسجد بيت الله. هل تعرف كيف نصلي؟","بسم الله الرحمن الرحيم."],"en":["Welcome to the Mosque! Let us learn Surah Al-Fatiha.","The mosque is the house of Allah. Do you know how to pray?","In the name of Allah, the Most Gracious, the Most Merciful."]},
    "dynamic": {"ar":["مرحباً بك في حديقة الحيوانات! ماذا ترى هنا؟","انظر! هذا أسد كبير. ما صوته؟","الحيوانات جميلة! هل تحب الحيوانات؟"],"en":["Welcome to the Zoo! What animals do you see?","Look! A big lion. What sound does it make?","Animals are amazing! Do you like animals?"]},
}

def read_shared_state(key):
    try:
        with open("/tmp/alfaseelah_state.json") as f:
            return json.load(f).get(key)
    except: return None

def _play_bytes(data):
    fp = io.BytesIO(data)
    pygame.mixer.music.load(fp)
    time.sleep(0.5)
    pygame.mixer.music.play()
    deadline = time.time() + 60
    while pygame.mixer.music.get_busy() and time.time() < deadline:
        time.sleep(0.1)
    time.sleep(0.2)

def speak(text, language="ar", character=None):
    log.info(f"[TTS] Speaking ({language}): {text[:60]}...")
    if character: character.set_expression("happy"); character.start_talking()
    try:
        vid = ELEVENLABS_VOICE_AR if language == "ar" else ELEVENLABS_VOICE_EN
        r = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{vid}",
            headers={"Accept":"audio/mpeg","Content-Type":"application/json","xi-api-key":ELEVENLABS_API_KEY},
            json={"text":text,"model_id":ELEVENLABS_MODEL,"voice_settings":{"stability":0.75,"similarity_boost":0.75}},
            timeout=30)
        if r.status_code == 200: _play_bytes(r.content)
        else: raise Exception(f"HTTP {r.status_code}")
    except Exception as e:
        log.warning(f"[TTS] ElevenLabs failed ({e}), using gTTS")
        try:
            tts = gTTS(text, lang="ar" if language=="ar" else "en")
            fp = io.BytesIO(); tts.write_to_fp(fp); fp.seek(0)
            pygame.mixer.music.load(fp); time.sleep(0.5); pygame.mixer.music.play()
            deadline = time.time()+60
            while pygame.mixer.music.get_busy() and time.time()<deadline: time.sleep(0.1)
        except Exception as e2: log.error(f"[gTTS] {e2}")
    finally:
        if character: character.stop_talking()

def listen(timeout=10, language="ar", character=None):
    if character: character.set_expression("listening")
    lang_code = "ar" if language=="ar" else "en"
    log.info(f"[Whisper] Listening {timeout}s ({lang_code})...")
    try:
        audio = sd.rec(int(timeout*MIC_RATE), samplerate=MIC_RATE, channels=1, dtype="float32", device=MIC_DEVICE)
        sd.wait()
        audio = audio.flatten()
        peak = np.abs(audio).max()
        if peak > 0:
            audio = audio * min(0.9 / peak, 3.0)
        audio_16k = scipy.signal.resample(audio, int(len(audio)*WHISPER_RATE/MIC_RATE))
        result = WHISPER_MODEL.transcribe(audio_16k, language=lang_code, fp16=False, temperature=0.0, condition_on_previous_text=False)
        text = result.get("text","").strip()
        log.info(f"[Whisper] Heard: {text}" if text else "[Whisper] No speech detected")
        return text
    except Exception as e:
        log.error(f"[Whisper] {e}"); return ""

def save_session(child, zone, duration_minutes, stars):
    try:
        if not child.get("child_id") or not child.get("parent_id"):
            log.warning("[Supabase] No child_id or parent_id — skipping"); return
        lang = child.get("language","ar")
        now = datetime.now(timezone.utc)
        start = datetime.fromtimestamp(now.timestamp()-duration_minutes*60, tz=timezone.utc)
        data = {"child_id":child["child_id"],"parent_id":child["parent_id"],"start_time":start.isoformat(),"end_time":now.isoformat(),"total_minutes":duration_minutes,
            "activities":[{"id":f"act_{zone}_{int(now.timestamp())}","title":ZONES[zone][lang],"type":"dialogue","zone":zone,"duration":duration_minutes,"result":"completed","starsEarned":stars,"completedAt":now.isoformat()}],
            "zones_visited":{ZONES[zone][lang]:1},"mood":"happy","focus_level":"high","stars_earned":stars}
        result = supabase.table("sessions").insert(data).execute()
        if result.data: log.info(f"[Supabase] Session saved | id={result.data[0].get('id')}")
        else: log.error(f"[Supabase] Save failed: {result}")
    except Exception as e: log.error(f"[Supabase] {e}")

def run_zone_dialogue(child, zone, character=None):
    lang = child.get("language","ar")
    name = child["name"] if lang=="en" else child["name_ar"]
    greeting = f"Hello {name}! " if lang=="en" else f"مرحباً {name}! "
    line = random.choice(DIALOGUES.get(zone, DIALOGUES["home"])[lang])
    speak(greeting+line, lang, character)
    time.sleep(0.3)
    speak("What do you say?" if lang=="en" else "ماذا تقول؟", lang, character)
    response = listen(timeout=6, language=lang, character=character)
    if response:
        if character: character.set_expression("excited"); time.sleep(0.5)
        speak(f"Great job {name}! Well done!" if lang=="en" else f"أحسنت! شكراً {name}.", lang, character)
        return 3
    else:
        if character: character.set_expression("encouraging"); time.sleep(0.5)
        speak("That is okay! Try again next time." if lang=="en" else "لا بأس! حاول مرة أخرى.", lang, character)
        return 1

def get_current_zone():
    shared = read_shared_state("zone")
    if shared and shared.get("zone"): return shared["zone"]
    return random.choice(list(ZONES.keys()))

def get_child_from_ble(fallback_lang="ar"):
    shared = read_shared_state("child")
    if shared and shared.get("child_id"):
        return {"name":"Child","name_ar":"طفل","language":fallback_lang,"age":5,"child_id":shared["child_id"],"parent_id":shared.get("parent_id","")}
    return None

def main(character=None, child_profile=None):
    log.info("="*50)
    log.info("  Al-Faseelah World — Dialogue Manager")
    log.info("="*50)
    lang = child_profile.get("language","ar") if child_profile else "ar"
    if character: character.set_expression("happy")
    speak("Welcome to Al-Faseelah World!" if lang=="en" else "مرحباً بك في عالم الفسيلة!", lang, character)
    while True:
        try:
            if character: character.set_expression("sleeping")
            log.info("[Main] Waiting for child (RFID)...")
            time.sleep(2)
            if child_profile: child = child_profile
            else:
                child = get_child_from_ble(lang) or CHILD_PROFILES.get("TEST")
                if not child: continue
            log.info(f"[RFID] Child: {child['name']} | Lang: {child.get('language','ar')}")
            if character: character.set_expression("happy"); time.sleep(0.5)
            zone = get_current_zone()
            log.info(f"[Zone] {zone}")
            t0 = time.time()
            stars = run_zone_dialogue(child, zone, character)
            save_session(child, zone, max(1,int((time.time()-t0)/60)), stars)
            log.info("[Main] Session done. Waiting 10s...")
            if character: character.set_expression("happy")
            time.sleep(10)
        except KeyboardInterrupt:
            log.info("[Main] Stopped.")
            speak("Goodbye! See you next time!" if lang=="en" else "مع السلامة! إلى اللقاء.", lang, character)
            break
        except Exception as e:
            log.error(f"[Main] Error: {e}"); time.sleep(5)

if __name__ == "__main__":
    main()
