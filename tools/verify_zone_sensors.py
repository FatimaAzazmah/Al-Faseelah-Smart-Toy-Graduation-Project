#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# verify_zone_sensors.py — list a zone's pieces/pins from the database, flag pin
# conflicts, then watch the sensors live and print which piece each touch maps to.
import os
from dotenv import load_dotenv
from supabase import create_client
from gpiozero import Button
import signal

load_dotenv()
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

ZONE_KEY = "home"

r = sb.table("pieces").select("*, zones!inner(key)").eq("zones.key", ZONE_KEY).execute()
pieces = r.data

print(f"=== Zone: {ZONE_KEY} — {len(pieces)} registered pieces ===")
pin_to_name = {}
seen_pins = {}
for p in pieces:
    pin = p.get("sensor_pin")
    label = f"{p['key']} ({p['name_ar']})"
    print(f"  {label}  ->  sensor_pin: {pin}")
    if pin is not None:
        if pin in seen_pins:
            print(f"    ⚠️ Conflict! GPIO{pin} is also registered for {seen_pins[pin]}")
        seen_pins[pin] = label
        pin_to_name[pin] = label

active = {}
def on_trigger(pin):
    name = pin_to_name.get(pin, "⚠️ pin not registered in the database for this zone")
    print(f"\n[TRIGGER] GPIO{pin}  ->  {name}")

for pin in pin_to_name.keys():
    try:
        b = Button(pin, pull_up=True, bounce_time=0.05)
        b.when_pressed = (lambda p=pin: on_trigger(p))
        active[pin] = b
    except Exception as e:
        print(f"⚠️ GPIO{pin} failed: {e}")

print(f"\nReady — watching {len(active)} pins. Touch each sensor in the {ZONE_KEY} zone with the magnet.")
print("Ctrl+C to exit.\n")
signal.pause()
