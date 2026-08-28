#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# verify_sensors.py — touch sensors and print the piece name straight from the database
import os
from dotenv import load_dotenv
from supabase import create_client
from gpiozero import Button
import signal

load_dotenv()
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# The pieces to verify
KEYS_TO_CHECK = ["globe", "tech_lab", "library"]

r = sb.table("pieces").select("key,name_ar,sensor_pin").in_("key", KEYS_TO_CHECK).execute()
pin_to_name = {}
for p in r.data:
    if p.get("sensor_pin") is not None:
        pin_to_name[p["sensor_pin"]] = f"{p['key']} ({p['name_ar']})"

print("=== Expected pieces and their pins registered in the database ===")
for pin, name in sorted(pin_to_name.items()):
    print(f"  GPIO{pin}  ->  {name}")

if not pin_to_name:
    print("None of these pieces has a sensor_pin registered.")
    exit()

active = {}

def on_trigger(pin):
    name = pin_to_name.get(pin, "⚠️ not registered in the database for these pieces")
    print(f"\n[TRIGGER] GPIO{pin}  ->  {name}")

for pin in pin_to_name.keys():
    try:
        b = Button(pin, pull_up=True, bounce_time=0.05)
        b.when_pressed = (lambda p=pin: on_trigger(p))
        active[pin] = b
    except Exception as e:
        print(f"⚠️ GPIO{pin} failed to init: {e}")

print(f"\nReady — watching {len(active)} pins. Touch each sensor with the magnet and check the name.")
print("Ctrl+C to exit.\n")
signal.pause()
