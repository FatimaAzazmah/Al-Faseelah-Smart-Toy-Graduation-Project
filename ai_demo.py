#!/usr/bin/env python3
"""
Al-Faseelah World — AI Integration Example
===========================================
An example showing how the AI controls the character display.
Run this file instead of character_display.py to see how it works with AI.

Structure:
  - Main thread  →  runs the display (required by Pygame)
  - AI thread    →  runs logic and sends commands to display
"""

import threading
import time
from character_display import CharacterDisplay


# ═══════════════════════════════════════════════════════════
#  SIMULATED AI LOGIC  (replace this with your real AI later)
# ═══════════════════════════════════════════════════════════

def ai_logic(character: CharacterDisplay):
    """
    This function simulates how the AI will control the character.
    In your real project, this is where:
      - RFID reader sends zone/object events
      - Dialogue manager (FSM) decides what to say
      - Audio plays
      - Character expression changes to match the dialogue
    """
    time.sleep(1.5)   # wait for display to initialize

    print("\n[AI] Starting demo sequence...\n")

    # ── Greeting ────────────────────────────────────────────
    print("[AI] State: GREETING")
    character.set_expression("happy")
    time.sleep(2)

    # ── Talking (while audio plays) ──────────────────────────
    print("[AI] State: TALKING — playing audio...")
    character.start_talking()
    time.sleep(3)     # <- in real code: wait for audio to finish
    character.stop_talking()
    time.sleep(0.5)

    # ── Listening for child response ─────────────────────────
    print("[AI] State: LISTENING")
    character.set_expression("listening")
    time.sleep(2.5)

    # ── Child did something exciting ─────────────────────────
    print("[AI] State: EXCITED FEEDBACK")
    character.set_expression("excited")
    time.sleep(1.5)

    # ── Encouraging child ────────────────────────────────────
    print("[AI] State: ENCOURAGING")
    character.set_expression("encouraging")
    character.start_talking()
    time.sleep(2)
    character.stop_talking()
    time.sleep(0.5)

    # ── Child placed wrong object — gentle correction ─────────
    print("[AI] State: SURPRISED / CORRECTION")
    character.set_expression("surprised")
    time.sleep(1.5)

    # ── Try again → sad if needed ─────────────────────────────
    print("[AI] State: SAD")
    character.set_expression("sad")
    time.sleep(1.5)

    # ── Session complete ─────────────────────────────────────
    print("[AI] State: HAPPY — session complete")
    character.set_expression("happy")
    character.start_talking()
    time.sleep(2.5)
    character.stop_talking()
    time.sleep(1)

    # ── Sleep mode ───────────────────────────────────────────
    print("[AI] State: IDLE / SLEEPING")
    character.set_expression("sleeping")
    time.sleep(4)

    # ── Wake up for next session ─────────────────────────────
    print("[AI] State: WAKING — neutral")
    character.set_expression("neutral")
    time.sleep(2)

    print("\n[AI] Demo complete. Press ESC to exit.\n")


# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Create character display
    character = CharacterDisplay()

    # Run AI in a background thread
    ai_thread = threading.Thread(
        target=ai_logic,
        args=(character,),
        daemon=True
    )
    ai_thread.start()

    # Run display in main thread (required by Pygame)
    character.run()
