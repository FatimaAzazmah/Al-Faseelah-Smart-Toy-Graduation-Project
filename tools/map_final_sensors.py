#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# map_final_sensors.py — verify and store sensor pins immediately, zone by zone
import os
from dotenv import load_dotenv
from supabase import create_client
from gpiozero import Button
import signal, sys

load_dotenv()
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

ZONE_KEY = "school"   # change per zone: home / mosque / school / zoo / careers

def get_zone_pieces(zone_key):
    r = sb.table("pieces").select("*, zones!inner(key)") \
        .eq("zones.key", zone_key).execute()
    return r.data

pieces = get_zone_pieces(ZONE_KEY)
if not pieces:
    print(f"No pieces registered for zone '{ZONE_KEY}' — check the key.")
    sys.exit(1)

print(f"=== Zone: {ZONE_KEY} — {len(pieces)} expected pieces ===")
for p in pieces:
    status = f"pin={p.get('sensor_pin')}" if p.get('sensor_pin') is not None else "no pin yet"
    print(f"  - {p['key']} ({p.get('name_ar','')}) [{status}]")

# Watch every candidate GPIO (BCM numbering) — any free pin on the board
CANDIDATE_PINS = list(range(2, 28))
active = {}

def on_trigger(pin):
    print(f"\n[TRIGGER] GPIO{pin} pressed.")
    print("Which piece from the list above? Type its key (or 's' to skip):")
    key = input("> ").strip()
    if key.lower() == 's':
        return
    match = next((p for p in pieces if p['key'] == key), None)
    if not match:
        print("Not in this zone's list — check the key.")
        return
    sb.table("pieces").update({"sensor_pin": pin}).eq("id", match["id"]).execute()
    print(f"✅ Stored immediately: {key} -> GPIO{pin}")

for pin in CANDIDATE_PINS:
    try:
        b = Button(pin, pull_up=True, bounce_time=0.05)
        b.when_pressed = (lambda p=pin: on_trigger(p))
        active[pin] = b
    except Exception:
        pass  # pin in use elsewhere or faulty, skip it

print(f"\nReady. Touch each sensor in the {ZONE_KEY} zone with the magnet, one at a time.")
print("Press Ctrl+C when this zone is done.\n")
signal.pause()
