#!/usr/bin/env python3
"""
Al-Faseelah World — Main Integrated
=====================================
Wires character_display.py and dialogue_manager.py together.

Run:
    cd ~/alfaseelah
    source venv/bin/activate
    python3 main_integrated.py

Accepts a child profile as arguments:
    python3 main_integrated.py --lang ar       # Arabic
    python3 main_integrated.py --lang en       # English
    python3 main_integrated.py --lang ar --name Sara
"""

import threading
import time
import argparse
import logging

from character_display import CharacterDisplay

# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Import dialogue_manager — fall back to demo mode if missing
# ─────────────────────────────────────────────────────────────
try:
    import dialogue_manager
    HAS_DIALOGUE = True
    log.info("[OK] dialogue_manager loaded")
except ImportError:
    HAS_DIALOGUE = False
    log.warning("[WARN] dialogue_manager not found — running demo mode")


# ─────────────────────────────────────────────────────────────
# Helper: map a dialogue state to a character expression
# ─────────────────────────────────────────────────────────────

def state_to_expression(state: str) -> str:
    """
    Convert a dialogue_manager state name into a character_display expression.

    Adjust this dictionary to match the actual FSM states in dialogue_manager.
    """
    mapping = {
        # greeting states
        "GREETING":      "happy",
        "IDLE":          "neutral",
        "SLEEPING":      "sleeping",

        # interaction states
        "TALKING":       "neutral",       # character speaks → start_talking runs separately
        "LISTENING":     "listening",
        "WAITING":       "listening",

        # feedback states
        "CORRECT":       "excited",
        "WRONG":         "surprised",
        "ENCOURAGING":   "encouraging",
        "HINT":          "encouraging",
        "SAD":           "sad",

        # end of session
        "SESSION_END":   "happy",
        "GOODBYE":       "happy",
    }
    return mapping.get(state.upper(), "neutral")


# ─────────────────────────────────────────────────────────────
# Demo mode (used when dialogue_manager is not available)
# ─────────────────────────────────────────────────────────────

def demo_ai_loop(character: CharacterDisplay):
    """
    A simple simulation of the dialogue flow — replaced by the real
    DialogueManager when it is available.
    """
    time.sleep(1.5)
    log.info("[DEMO] Starting demo sequence")

    steps = [
        ("happy",        2.0,  False,  "GREETING"),
        ("neutral",      3.0,  True,   "TALKING — saying hello"),
        ("listening",    2.5,  False,  "LISTENING for child"),
        ("excited",      1.5,  False,  "CORRECT answer!"),
        ("encouraging",  2.0,  True,   "ENCOURAGING"),
        ("surprised",    1.5,  False,  "WRONG answer"),
        ("sad",          1.5,  False,  "SAD"),
        ("happy",        2.5,  True,   "SESSION END"),
        ("sleeping",     4.0,  False,  "IDLE / SLEEP"),
        ("neutral",      2.0,  False,  "WAKING UP"),
    ]

    for expr, duration, talking, label in steps:
        log.info(f"[DEMO] State: {label}")
        character.set_expression(expr)
        if talking:
            character.start_talking()
            time.sleep(duration)
            character.stop_talking()
        else:
            time.sleep(duration)

    log.info("[DEMO] Demo complete. Press ESC to exit.")


# ─────────────────────────────────────────────────────────────
# Real dialogue loop (used when dialogue_manager is available)
# ─────────────────────────────────────────────────────────────

def real_ai_loop(character: CharacterDisplay, child_profile: dict):
    time.sleep(1.0)
    try:
        import dialogue_manager
        log.info(f"[AI] Starting dialogue for: {child_profile.get('name', 'child')}")
        dialogue_manager.main(character=character, child_profile=child_profile)
    except Exception as e:
        log.error(f"[AI] Error: {e}")
        demo_ai_loop(character)


def main():
    parser = argparse.ArgumentParser(description="Al-Faseelah World")
    parser.add_argument("--lang",    default="ar",   help="ar or en")
    parser.add_argument("--name", default=None, help="Child name")
    parser.add_argument("--age",     default=5,      type=int, help="Child age")
    parser.add_argument("--profile", default="child_001", help="Profile ID in Supabase")
    args = parser.parse_args()

    child_profile = {
        "name":       args.name if args.name else ("Child" if args.lang == "en" else "صديقي"),
        "age":        args.age,
        "language":   args.lang,
        "name_ar":    args.name if args.name else "صديقي",
        "profile_id": args.profile,
    }

    log.info(f"[MAIN] Starting Al-Faseelah World")
    log.info(f"[MAIN] Child: {child_profile['name']} | Age: {child_profile['age']} | Lang: {child_profile['language']}")

    # ── Initialize the character display ────────────────────
    character = CharacterDisplay()

    # ── Pick the AI loop ────────────────────────────────────
    if HAS_DIALOGUE:
        target = real_ai_loop
        log.info("[MAIN] Using real DialogueManager")
    else:
        target = demo_ai_loop
        log.info("[MAIN] Using demo mode")

    # ── Run the AI in a background thread ───────────────────
    ai_thread = threading.Thread(
        target=target,
        args=(character, child_profile) if HAS_DIALOGUE else (character,),
        daemon=True
    )
    ai_thread.start()

    # ── Pygame must run on the main thread ──────────────────
    character.run()

    log.info("[MAIN] Goodbye!")


if __name__ == "__main__":
    main()
