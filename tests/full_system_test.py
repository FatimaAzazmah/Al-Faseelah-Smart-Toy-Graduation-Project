#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv
from supabase import create_client
from gpiozero import Button
import signal

load_dotenv()
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

r = sb.table("pieces").select("*, zones!inner(key)").execute()
pieces = r.data

pin_to_names = {}
for p in pieces:
    pin = p.get("sensor_pin")
    if pin is None:
        continue
    label = f"{p['key']} ({p['name_en']}) - {p['zones']['key']}"
    pin_to_names.setdefault(pin, []).append(label)

print(f"=== Loaded {len(pin_to_names)} pins from database ===")
for pin, names in sorted(pin_to_names.items()):
    print(f"  GPIO{pin}  ->  {' | '.join(names)}")

active = {}
def on_trigger(pin):
    names = pin_to_names.get(pin, ["WARNING: not registered in database"])
    print(f"\n[TRIGGER] GPIO{pin}  ->  {' | '.join(names)}")

for pin in pin_to_names.keys():
    try:
        b = Button(pin, pull_up=True, bounce_time=0.05)
        b.when_pressed = (lambda p=pin: on_trigger(p))
        active[pin] = b
    except Exception as e:
        print(f"WARNING: GPIO{pin} failed to init: {e}")

print(f"\nReady - watching {len(active)} pins across all zones.")
print("Place a magnet on any sensor anywhere on the board.")
print("Ctrl+C to stop.\n")
signal.pause()
