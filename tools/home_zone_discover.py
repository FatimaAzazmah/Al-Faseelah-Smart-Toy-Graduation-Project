#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Discovers the real GPIO pin of each sensor, without relying on the old
# numbers stored in the database.
from gpiozero import Button
import signal

CANDIDATE_PINS = [p for p in range(2, 28)]  # all actually-usable GPIOs (2-27)
results = {}
active = {}

def on_trigger(pin):
    if pin in results:
        return
    print(f"\n[TRIGGER] GPIO{pin} fired")
    name = input("Piece name? (kitchen/bed/bathroom/desk/play_area or Enter to skip): ").strip()
    if name:
        results[pin] = name
        print(f"  -> recorded: GPIO{pin} = {name}")

for pin in CANDIDATE_PINS:
    try:
        b = Button(pin, pull_up=True, bounce_time=0.05)
        b.when_pressed = (lambda p=pin: on_trigger(p))
        active[pin] = b
    except Exception:
        pass

print(f"Ready — watching {len(active)} pins (2-27, the valid range on the Pi 5).")
print("Touch each sensor in the Home zone with the magnet, one at a time.")
print("Press Ctrl+C when done to see the summary.\n")

try:
    signal.pause()
except KeyboardInterrupt:
    print("\n\n=== Home zone summary (real discovered pins) ===")
    for pin, name in sorted(results.items()):
        print(f"  GPIO{pin}  ->  {name}")
    print(f"\nTotal: {len(results)} working sensors.")
