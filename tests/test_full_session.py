# -*- coding: utf-8 -*-
# FULL SESSION TEST — the first real end-to-end session!
# Simulated RFID -> child context -> Faseelah talks from REAL content
import os, json, sys, io
sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8', errors='ignore')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
from google import genai
from google.genai import types
from prompts import build_system_prompt
from content_manager import get_child_context, get_piece_card, get_active_dynamic_zone

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# ---------- 1. Simulate RFID scan ----------
# Put a real rfid_id from your own `children` table here:
RFID = "YOUR_CHILD_RFID_TAG"
print(f"[RFID] tag scanned: {RFID}")
ctx = get_child_context(RFID)
if not ctx:
    print("Unknown tag!"); exit()

child = ctx["child"]
goal = ctx["goal"]
print(f"[DB] child: {child['name']}, age {child['age']}")
print(f"[DB] active goal: {goal['title'] if goal else 'none'}")
print(f"[DB] active board: {(get_active_dynamic_zone() or {}).get('name_ar','?')}")

# ---------- 2. Simulate placing the ELEPHANT piece ----------
card = get_piece_card("elephant", difficulty=1)
kc = card["knowledge_card"]

# ---------- 3. Build the task from the REAL card ----------
task = f"""The child just placed the ELEPHANT piece on the board. Use ONLY this knowledge card:
FACTS: {json.dumps([f['ar'] for f in kc['facts_l1'] + kc.get('facts_l2', [])], ensure_ascii=False)}
DID YOU KNOW: {json.dumps([d['ar'] for d in kc.get('did_you_know', [])], ensure_ascii=False)}
VALUES: {json.dumps([v['ar'] for v in kc.get('values', [])], ensure_ascii=False)}
PLAY IDEAS: {json.dumps([p['ar'] for p in kc.get('play_ideas', [])], ensure_ascii=False)}
Start by reacting excitedly to the elephant, share ONE fun fact, then ask ONE simple question from the play ideas."""

goal_text = goal["target_behavior"] if goal else "no specific goal"
system = build_system_prompt(
    child_name=child["name"], age=child["age"],
    task=task, parent_goal=goal_text, simplified=False)

# ---------- 4. Chat loop ----------
chat = client.chats.create(
    model="gemini-2.5-flash",
    config=types.GenerateContentConfig(
        system_instruction=system,
        thinking_config=types.ThinkingConfig(thinking_budget=0)))

print("\n=== FIRST REAL SESSION — Faseelah + real content ===")
r = chat.send_message("ابدئي الآن")
print("Faseelah:", r.text)
while True:
    msg = input(f"{child['name']}: ")
    if msg.strip().lower() == "q": break
    r = chat.send_message(msg)
    print("Faseelah:", r.text)
