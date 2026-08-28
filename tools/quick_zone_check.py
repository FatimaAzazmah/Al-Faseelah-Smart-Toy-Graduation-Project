#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# quick_zone_check.py — check and name sensors without the database (print only)
from gpiozero import Button
import signal

# Watch every free GPIO (BCM numbering)
CANDIDATE_PINS = list(range(2, 28))
results = {}
active = {}

def on_trigger(pin):
    if pin in results:
        return  # already recorded, ignore repeated presses
    print(f"\n[TRIGGER] GPIO{pin} fired ✅")
    name = input("Piece name? (or Enter to skip): ").strip()
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

print(f"Ready — watching {len(active)} pins. Touch each sensor in the zone with the magnet, one at a time.")
print("When done, press Ctrl+C to see the summary.\n")

try:
    signal.pause()
except KeyboardInterrupt:
    print("\n\n=== Zone summary ===")
    if results:
        for pin, name in sorted(results.items()):
            print(f"  GPIO{pin:>2}  ->  {name}")
    else:
        print("  No sensors recorded.")
    print(f"\nTotal: {len(results)} working sensors out of {len(active)} watched.")
