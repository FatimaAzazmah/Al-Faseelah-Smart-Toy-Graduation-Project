#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main_ai.py - Al-Faseelah World (Live Demo / Committee Version)
==================================================================

This version adds, on top of the working live pipeline:
  * A warm ONBOARDING opening: Faseelah wakes up, gives a warm salaam,
    greets the child by name, asks how they are / how their day was, has
    a short natural back-and-forth, then cheerfully invites them to play.
    The child leads: grabbing a piece early or going quiet ends the
    check-in gracefully.
  * SESSION TRACKING + PARENT REPORT: every piece the child engages with
    is recorded (with the zone and a star), along with total time. When
    the session ends (ESC / Ctrl+C / display closed) a full session row
    is written to Supabase `sessions`, which the Pearant parent app reads
    as the child's activity report.

AUDIO/THREADING NOTE (unchanged): CharacterDisplay uses Pygame, whose
event loop MUST run on the main thread and run continuously. All
AI/session logic runs in a background thread (session_loop);
character.run() drives rendering on the main thread. Recording shells out
to `arecord` (its own OS process) to avoid the cross-thread PortAudio hang.

Flow:
  1. Boot: Faseelah is asleep, screen idle.
  2. Background thread blocks on the real RFID reader waiting for a tag.
  3. Tag recognized -> load child + active goal + saved content from
     Supabase -> warm onboarding (greet, check in, invite to play).
  4. Watch the reed-switch sensors. On each piece placement, pick up the
     piece's knowledge card and start a Gemini-powered conversation,
     spoken aloud with ElevenLabs. Each engaged piece is tracked.
  5. On stop (ESC / Ctrl+C), save the full session report for the parent.

Run:
    cd ~/alfaseelah
    source venv/bin/activate
    python3 main_ai.py --lang ar
    python3 main_ai.py --lang en
"""
import os
import json
import time
import argparse
import logging
import threading
from datetime import datetime, timezone

from dotenv import load_dotenv
from google import genai
from google.genai import types

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

load_dotenv()

from rfid_reader import RFIDReader
from sensor_controller import SensorController
from content_manager import (
    get_child_context, get_piece_card, get_active_dynamic_zone,
    save_session_full, save_child_content, upsert_session,
)
from behavior_engine import (
    resolve_goal, behavior_system_addition, detect_success, increment_goal,
)
from prompts import build_system_prompt
import dialogue_manager as legacy   # reuse speak()/listen() audio helpers

try:
    from character_display import CharacterDisplay
    HAS_CHARACTER = True
except ImportError:
    HAS_CHARACTER = False
    log.warning("[MAIN] character_display not available - running headless")

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Listening windows (seconds). Faseelah picks how long to wait based on
# what kind of reply she just invited: a quick yes/no needs little time, a
# recitation ("read Surah Al-Fatiha", "count to ten") needs much more.
LISTEN_SHORT  = 3   # quick yes/no / one word
LISTEN_NORMAL = 4   # ordinary short reply (default)
LISTEN_LONG   = 10  # recitation / long answer (surah, counting, a story)
LISTEN_SECONDS = LISTEN_NORMAL   # backward-compatible default

# Words that, if they appear in Faseelah's own last line, signal she asked
# the child for a LONGER answer (recite / read / repeat after me / count).
_LONG_CUES = (
    # Arabic
    "اقرأ", "اقرئي", "اقرا", "سمّع", "سمعني", "سمعيني", "ردد", "رددي",
    "احفظ", "احفظي", "سورة", "الفاتحة", "آية", "دعاء", "عُدّ", "عد ",
    "احكيلي", "احكي لي", "خبرني", "خبريني", "قصة", "بالتفصيل",
    # English
    "recite", "read ", "repeat after", "count to", "count ",
    "tell me about", "say the", "surah", "the whole", "story",
)
# Words that signal a very SHORT answer (yes/no, pick one).
_SHORT_CUES = (
    "نعم أم لا", "صح أم", "هل ", "أليس", "موافق",
    "yes or no", "do you", "did you", "is it", "right?",
)


def choose_listen_seconds(last_line: str) -> int:
    """Pick a listening window from Faseelah's own last spoken line."""
    if not last_line:
        return LISTEN_NORMAL
    low = last_line.lower()
    for c in _LONG_CUES:
        if c.lower() in low:
            return LISTEN_LONG
    for c in _SHORT_CUES:
        if c.lower() in low:
            return LISTEN_SHORT
    return LISTEN_NORMAL
# How many consecutive silent turns before Faseelah stops asking and
# goes back to waiting for a new piece.
MAX_SILENT_TURNS = 2
# How many check-in exchanges during the opening onboarding chat before
# Faseelah invites the child to start playing.
ONBOARDING_TURNS = 2
# ALSA card number for the USB PnP microphone (see `arecord -l`).
ARECORD_CARD = 0


def _find_arecord_card():
    """Return the ALSA card number whose name contains 'PnP'."""
    import subprocess
    import re
    try:
        out = subprocess.run(
            ["arecord", "-l"], capture_output=True, text=True, timeout=5
        ).stdout
    except Exception as e:
        log.warning(f"[MIC] arecord -l failed: {e}")
        return 0
    for line in out.splitlines():
        m = re.match(r"card (\d+):.*", line)
        if m and "PnP" in line:
            card = int(m.group(1))
            log.info(f"[MIC] arecord will use card {card}: {line.strip()}")
            return card
    log.warning("[MIC] no PnP capture card found, falling back to card 0")
    return 0


ARECORD_CARD = _find_arecord_card()


# ─────────────────────────────────────────────────────────
# Audio recording (arecord in its own process — see module docstring)
# ─────────────────────────────────────────────────────────
def listen_via_dedicated_thread(timeout=10, language="ar", character=None):
    """Records with `arecord` (a plain ALSA command-line tool) instead of
    sounddevice/PortAudio, which was intermittently hanging when called
    from a background thread while Pygame's event loop ran on the main
    thread. `arecord` runs as its own OS process, immune to that."""
    import subprocess
    import wave
    import numpy as np
    import scipy.signal

    if character:
        character.set_expression("listening")
    lang_code = "ar" if language == "ar" else "en"
    log.info(f"[Whisper] Listening {timeout}s ({lang_code})...")

    wav_path = "/tmp/faseelah_input.wav"
    cmd = [
        "arecord",
        "-D", f"plughw:{ARECORD_CARD},0",
        "-f", "S16_LE",
        "-r", str(legacy.MIC_RATE),
        "-c", "1",
        "-d", str(timeout),
        wav_path,
    ]
    try:
        proc = subprocess.run(
            cmd,
            timeout=timeout + 5,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            log.error(f"[AUDIO] arecord failed (rc={proc.returncode}): {proc.stderr.strip()}")
            log.error(f"[AUDIO] command was: {' '.join(cmd)}")
            return ""
    except subprocess.TimeoutExpired:
        log.error("[AUDIO] arecord timed out")
        return ""
    except FileNotFoundError:
        log.error("[AUDIO] arecord not found - install alsa-utils")
        return ""

    if not os.path.exists(wav_path):
        log.error(f"[AUDIO] arecord produced no file at {wav_path}")
        return ""

    try:
        with wave.open(wav_path, "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            rate = wf.getframerate()
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    except Exception as e:
        log.error(f"[AUDIO] could not read wav: {e}")
        return ""

    if audio.size == 0:
        log.info("[Whisper] No speech detected (empty recording)")
        return ""

    peak = np.abs(audio).max()
    if peak > 0:
        audio = audio * min(0.9 / peak, 3.0)
    audio_16k = scipy.signal.resample(audio, int(len(audio) * legacy.WHISPER_RATE / rate))

    try:
        result = legacy.WHISPER_MODEL.transcribe(
            audio_16k, language=lang_code, fp16=False,
            temperature=0.0,
            condition_on_previous_text=False,
            compression_ratio_threshold=2.0,
            no_speech_threshold=0.6,
        )
        text = result.get("text", "").strip()
        words = text.split()
        if len(words) > 4 and len(set(words)) <= 2:
            log.warning("[Whisper] Repetition detected - discarding")
            return ""
        log.info(f"[Whisper] Heard: {text}" if text else "[Whisper] No speech detected")
        return text
    except Exception as e:
        log.error(f"[Whisper] {e}")
        return ""


# ─────────────────────────────────────────────────────────
# Gemini helper with retry on transient server errors
# ─────────────────────────────────────────────────────────

def ask_gemini(chat, message, retries=3):
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            return chat.send_message(message)
        except Exception as e:
            last_err = e
            log.warning(f"[GEMINI] attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                time.sleep(1.5 * attempt)
    log.error(f"[GEMINI] all retries failed: {last_err}")
    return None


# ─────────────────────────────────────────────────────────
# Step 1: wait for RFID login (real tag, once per session)
# ─────────────────────────────────────────────────────────

def wait_for_child_login(reader: RFIDReader):
    log.info("[LOGIN] Waiting for RFID tag...")
    tag = reader.wait_for_tag()
    log.info(f"[LOGIN] Tag scanned: {tag}")

    ctx = get_child_context(tag)
    if ctx:
        child = ctx["child"]
        log.info(f"[LOGIN] Child found: {child['name']} (age {child['age']})")
        return ctx

    log.warning(f"[LOGIN] Tag {tag} not registered - using guest profile")
    return {
        "child": {"name": "صديقي", "age": 5, "id": None, "parent_id": None},
        "preferences": None,
        "goal": None,
        "achieved": [],
        "saved_content_ids": [],
    }


# ─────────────────────────────────────────────────────────
# Step 2: onboarding — a natural, warm opening check-in
#
# Faseelah wakes, gives a warm salaam, greets the child by name, asks how
# they are and how their day was, has a short back-and-forth, and only
# then cheerfully invites them to start playing. The child leads: if they
# grab a piece early or go quiet, the check-in ends gracefully.
# ─────────────────────────────────────────────────────────

def _piece_waiting(sensors):
    """True if the child has already placed a piece (let play take over)."""
    return sensors is not None and not sensors.events.empty()


def run_onboarding(chat, child: dict, lang: str, character=None, sensors=None):
    name = child.get("name", "")
    interests = child.get("interests")
    notes = child.get("parent_notes")

    # Faseelah wakes up and greets warmly, by name, with a salaam.
    if character:
        character.set_expression("happy")

    extra = ""
    if interests:
        extra += f" The child's interests: {interests}."
    if notes:
        extra += f" (Private note from the parent, do not read it aloud: {notes})"

    greet_task = (
        f"This is the very first moment of the session. You just woke up and "
        f"recognized your dear friend {name}. Greet them with a warm salaam "
        f"(say 'السلام عليكم' if Arabic), tell them how happy you are to see "
        f"them, and gently ask how they are and how their day was.{extra} "
        f"Warm, friendly, and SHORT — one reply, ask only one thing."
    )
    r = ask_gemini(chat, greet_task)
    if r is None:
        last_line = (f"السلام عليكم يا {name}! اشتقتلك، كيف حالك اليوم؟" if lang == "ar"
                    else f"Peace be upon you, {name}! I missed you. How are you today?")
        legacy.speak(last_line, lang, character)
    else:
        last_line = r.text
        legacy.speak(r.text, lang, character)

    # Short check-in: react to the child's answers, keep it light.
    for turn in range(ONBOARDING_TURNS):
        if _piece_waiting(sensors):
            log.info("[ONBOARD] child placed a piece early - starting play")
            return
        secs = choose_listen_seconds(last_line)
        reply = listen_via_dedicated_thread(
            timeout=secs, language=lang, character=character
        )
        if not reply:
            log.info("[ONBOARD] child quiet - moving on to play")
            break
        if character:
            character.set_expression("happy")
        if turn == ONBOARDING_TURNS - 1:
            steer = ("\n\n(The child said the above. Reply warmly to it, then "
                     "gently start moving toward playing.)")
            r = ask_gemini(chat, reply + steer)
        else:
            r = ask_gemini(chat, reply)
        if r:
            last_line = r.text
            legacy.speak(r.text, lang, character)

    # Warm invitation to begin playing.
    if _piece_waiting(sensors):
        return
    if character:
        character.set_expression("excited")
    invite_task = (
        "Now cheerfully invite the child to start playing together — something "
        "like 'yalla, let's play, my friend!' — and ask them to place a piece "
        "on the board. Keep it short and joyful."
    )
    r = ask_gemini(chat, invite_task)
    if r is None:
        fallback = ("يلا نلعب مع بعض يا صديقي! حط قطعة عالطاولة." if lang == "ar"
                    else "Yalla, let's play together! Place a piece on the board.")
        legacy.speak(fallback, lang, character)
    else:
        legacy.speak(r.text, lang, character)
    if character:
        character.set_expression("neutral")


# ─────────────────────────────────────────────────────────
# Step 3: react to a sensor touch (piece placed on the board)
#
# Returns True if the child engaged with this piece (Faseelah spoke about
# it), so the caller can record it in the session report.
# ─────────────────────────────────────────────────────────

def handle_piece_touch(chat, piece: dict, lang: str, character=None,
                       sensors=None, saved_ids=None, child_id=None,
                       behavior_res=None, goal=None, said_facts=None):
    key = piece.get("key")
    log.info(f"[TOUCH] {key}")

    card = get_piece_card(key, difficulty=1, prefer_ids=saved_ids)
    if not card:
        log.warning(f"[TOUCH] No content card found for '{key}'")
        return False

    # If the parent had saved this exact card as a favorite, note it.
    if saved_ids and card.get("id") in saved_ids:
        log.info(f"[TOUCH] playing parent-saved favorite (id={card.get('id')})")

    kc = card["knowledge_card"]
    lang_key = "ar" if lang == "ar" else "en"

    # Use ALL fact layers + did-you-know, not just l1/l2, so there is far
    # more material and Faseelah does not fall back on the same few facts.
    facts = [f[lang_key] for f in (
        kc.get("facts_l1", []) + kc.get("facts_l2", []) + kc.get("facts_l3", [])
    ) if lang_key in f]
    fun = [d[lang_key] for d in kc.get("did_you_know", []) if lang_key in d]
    values = [v[lang_key] for v in kc.get("values", []) if lang_key in v]
    play_ideas = [p[lang_key] for p in kc.get("play_ideas", []) if lang_key in p]
    open_qs = [q[lang_key] for q in kc.get("open_questions", []) if lang_key in q]

    # Which facts about THIS piece has Faseelah already used this session?
    # said_facts maps piece_key -> set of fact strings already spoken.
    if said_facts is None:
        said_facts = {}
    already = said_facts.setdefault(key, set())
    fresh_facts = [f for f in facts if f not in already]
    fresh_fun = [f for f in fun if f not in already]
    # If everything has been said, allow reuse but tell Gemini to rephrase.
    pool_facts = fresh_facts or facts
    pool_fun = fresh_fun or fun
    repeat_warning = ""
    if not fresh_facts and not fresh_fun:
        repeat_warning = ("\nNOTE: The child has heard all these facts before. "
                          "Do NOT repeat them as-is; instead ask a playful "
                          "question or suggest a game about this piece.")

    task = f"""The child just placed the '{key}' piece on the board. Use ONLY this knowledge card:
NEW FACTS (prefer these, pick ONE you have not said): {json.dumps(pool_facts, ensure_ascii=False)}
DID YOU KNOW: {json.dumps(pool_fun, ensure_ascii=False)}
VALUES: {json.dumps(values, ensure_ascii=False)}
PLAY IDEAS: {json.dumps(play_ideas, ensure_ascii=False)}
OPEN QUESTIONS: {json.dumps(open_qs, ensure_ascii=False)}
React warmly to this piece, share ONE fact the child has NOT heard yet, then ask ONE simple question.{repeat_warning}"""

    # Mark a couple of items as "said" so next time we move on to others.
    for f in pool_facts[:1]:
        already.add(f)
    for f in pool_fun[:1]:
        already.add(f)

    if character:
        character.set_expression("excited")

    r = ask_gemini(chat, task)
    if r is None:
        fallback = "هذه القطعة رائعة! لكن دعني أفكر لحظة." if lang == "ar" else "This piece is great! Let me think for a moment."
        legacy.speak(fallback, lang, character)
        return False
    last_line = r.text
    legacy.speak(r.text, lang, character)

    # This card was actively played; auto-save it to the child's content
    # so it appears among their pieces in the app (best-effort).
    if child_id and card.get("id"):
        save_child_content(child_id, card["id"])

    # ── Keep the conversation going around this piece ──────────
    # Faseelah keeps chatting about this piece until the child goes quiet
    # a couple of times in a row, OR until they move on to a new piece.
    silent_turns = 0
    while silent_turns < MAX_SILENT_TURNS:
        if sensors is not None and not sensors.events.empty():
            log.info("[CONV] new piece detected - ending this conversation")
            return True

        if character:
            character.set_expression("listening")
        secs = choose_listen_seconds(last_line)
        response = listen_via_dedicated_thread(timeout=secs, language=lang, character=character)

        if not response:
            silent_turns += 1
            log.info(f"[CONV] no speech ({silent_turns}/{MAX_SILENT_TURNS})")
            if silent_turns >= MAX_SILENT_TURNS:
                if character:
                    character.set_expression("neutral")
                log.info("[CONV] child is quiet - waiting for a new piece")
                return True
            continue

        silent_turns = 0
        if character:
            character.set_expression("happy")

        # ── Behavior tracking: did the child show the target behavior? ──
        # Best-effort, non-blocking; never breaks the conversation on error.
        if behavior_res and goal and not goal.get("is_completed"):
            try:
                if detect_success(behavior_res, response):
                    prog = increment_goal(goal)
                    if prog:
                        log.info(f"[BEHAVIOR] progress -> {prog['current']}/{prog['target']} "
                                 f"completed={prog['completed']}")
                        if prog["just_completed"]:
                            if character:
                                character.set_expression("excited")
                            celebrate = (
                                f"The child has just fully completed their good-behavior "
                                f"goal! Celebrate proudly and warmly in ONE short sentence, "
                                f"tell them how proud you are and that their family will be "
                                f"so happy."
                            )
                            rc = ask_gemini(chat, celebrate)
                            if rc:
                                legacy.speak(rc.text, lang, character)
            except Exception as e:
                log.error(f"[BEHAVIOR] tracking error (ignored): {e}")

        r2 = ask_gemini(chat, response)
        if r2 is None:
            return True
        last_line = r2.text
        legacy.speak(r2.text, lang, character)

    return True


# ─────────────────────────────────────────────────────────
# Parent report: write the finished session to Supabase.
# ─────────────────────────────────────────────────────────

def _persist_session(child, session_start, pieces_played, active_zone_name,
                     session_id=None):
    """Create-or-update the session report the parent app will read.

    Called incrementally after EVERY piece (not only at exit), because the
    finally-block in a daemon thread is not guaranteed to run when the
    program is killed. Passing session_id back in updates the same row.

    Returns the session id (new or existing), or the passed-in id on failure.
    Best-effort: never raises.
    """
    try:
        child_id = child.get("id")
        parent_id = child.get("parent_id")
        if not child_id or not parent_id:
            log.warning("[REPORT] guest/unknown child - no session saved")
            return session_id

        now = datetime.now(timezone.utc)
        total_minutes = max(1, int((now.timestamp() - session_start) / 60))
        stars = len(pieces_played)  # one star per piece engaged with

        activities = []
        zones_visited = {}
        for p in pieces_played:
            zone_name = p.get("zone") or active_zone_name or "منطقة اللعب"
            activities.append({
                "id": f"act_{p['key']}_{int(now.timestamp())}",
                "title": p.get("name") or p["key"],
                "type": "dialogue",
                "zone": zone_name,
                "key": p["key"],
                "result": "completed",
                "starsEarned": 1,
                "completedAt": now.isoformat(),
            })
            zones_visited[zone_name] = zones_visited.get(zone_name, 0) + 1

        start_iso = datetime.fromtimestamp(session_start, tz=timezone.utc).isoformat()
        new_id = upsert_session(
            session_id=session_id,
            child_id=child_id,
            parent_id=parent_id,
            start_time=start_iso,
            end_time=now.isoformat(),
            total_minutes=total_minutes,
            activities=activities,
            zones_visited=zones_visited,
            stars_earned=stars,
            mood="happy",
            focus_level="high",
        )
        log.info(f"[REPORT] session persisted | {len(pieces_played)} piece(s), "
                 f"{total_minutes} min, {stars} star(s)")
        return new_id or session_id
    except Exception as e:
        log.error(f"[REPORT] failed to save session: {e}")
        return session_id


# ─────────────────────────────────────────────────────────
# Background thread: all session/AI/hardware logic lives here.
# The main thread is reserved for Pygame's character.run().
# ─────────────────────────────────────────────────────────

def session_loop(lang: str, character):
    reader = RFIDReader()
    sensors = SensorController()
    sensors.start()

    # Session tracking state for the parent report.
    session_start = time.time()
    pieces_played = []      # list of {key, name, zone}
    session_id = None       # Supabase row id, set on first save
    child = {"id": None, "parent_id": None}
    active_zone_name = None
    said_facts = {}         # piece_key -> set of facts already spoken (anti-repeat)

    try:
        ctx = wait_for_child_login(reader)
        child = ctx["child"]
        goal = ctx.get("goal")
        saved_ids = ctx.get("saved_content_ids") or []
        active_zone = get_active_dynamic_zone()
        active_zone_name = (active_zone or {}).get("name_ar")
        log.info(f"[SESSION] active dynamic board: {active_zone_name or '?'}")
        log.info(f"[SESSION] parent-saved favorites: {len(saved_ids)} item(s)")

        # Fresh start time now that the child is actually logged in.
        session_start = time.time()

        # Resolve the behavior goal to its catalog entry + story, and get
        # the private coaching strategy to weave into the system prompt.
        behavior_res = resolve_goal(goal) if goal else None
        if behavior_res:
            log.info(f"[BEHAVIOR] goal resolved -> {behavior_res['catalog_key']} "
                     f"| story={behavior_res['story_key']} "
                     f"| progress={goal.get('current_count')}/{goal.get('target_count')}")
        else:
            log.info("[BEHAVIOR] no behavior goal resolved for this child")

        goal_text = goal["target_behavior"] if goal else "no specific goal"
        system_prompt = build_system_prompt(
            child_name=child["name"],
            age=child["age"],
            task="Wait for the session to begin.",
            parent_goal=goal_text,
            simplified=False,
            language=lang,
        )

        # Inject the hidden behavior-coaching strategy (soft nudging, never
        # lecturing). Empty string if there is no active behavior goal.
        system_prompt += behavior_system_addition(behavior_res, lang)

        # Language override: the base prompt is Arabic-first, so make the
        # target language explicit.
        if lang == "en":
            system_prompt += (
                "\n\nCRITICAL LANGUAGE RULE: You MUST reply ONLY in English. "
                "Never use Arabic words or Arabic script. "
                "The child's name may be Arabic - keep it as-is, but write "
                "everything else in English."
            )
        else:
            system_prompt += (
                "\n\nCRITICAL LANGUAGE RULE: You MUST reply ONLY in Arabic."
            )

        chat = client.chats.create(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )

        # Warm opening: greet, check in, then invite to play.
        run_onboarding(chat, child, lang, character, sensors)

        log.info("[MAIN] Watching sensors for touches...")
        while True:
            touch = sensors.wait_for_touch(timeout=0.5)
            if touch:
                engaged = handle_piece_touch(
                    chat, touch, lang, character,
                    sensors=sensors, saved_ids=saved_ids,
                    child_id=child.get("id"),
                    behavior_res=behavior_res, goal=goal,
                    said_facts=said_facts,
                )
                if engaged:
                    pieces_played.append({
                        "key": touch.get("key"),
                        "name": touch.get("name_ar") if lang == "ar" else touch.get("name_en"),
                        "zone": active_zone_name,
                    })
                    # Persist after EVERY piece so the parent report is safe
                    # even if the program is killed before a clean exit.
                    session_id = _persist_session(
                        child, session_start, pieces_played,
                        active_zone_name, session_id=session_id,
                    )
    except Exception as e:
        log.error(f"[SESSION] fatal error: {e}", exc_info=True)
    finally:
        # Final save on clean exit (updates the same row if it exists).
        _persist_session(child, session_start, pieces_played,
                         active_zone_name, session_id=session_id)
        sensors.close()
        reader.close()


# ─────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Al-Faseelah World - Live AI")
    parser.add_argument("--lang", default="ar", choices=["ar", "en"], help="ar or en")
    args = parser.parse_args()
    lang = args.lang

    log.info("=" * 60)
    log.info(f"  Al-Faseelah World - Live Demo (lang={lang})")
    log.info("=" * 60)

    character = None
    if HAS_CHARACTER:
        character = CharacterDisplay()
        character.set_expression("sleeping")

        session_thread = threading.Thread(
            target=session_loop, args=(lang, character), daemon=True
        )
        session_thread.start()

        # Pygame's event loop MUST run on the main thread.
        character.run()
        log.info("[MAIN] Display closed. Goodbye!")
    else:
        # Headless fallback: no display available, just run the session
        # loop directly on the main thread.
        try:
            session_loop(lang, None)
        except KeyboardInterrupt:
            log.info("[MAIN] Stopped by user.")


if __name__ == "__main__":
    main()
