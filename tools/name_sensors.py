#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Interactive sensor naming: touch each sensor with the magnet and type its name.
from gpiozero import Button
import signal

CANDIDATE_PINS = range(2, 28)
results = {}
active = {}

def on_trigger(pin):
    if pin in results:
        return
    print(f"\n[TRIGGER] GPIO{pin} fired")
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

print(f"Ready — watching {len(active)} pins.")
print("Touch each sensor with the magnet one at a time and type its name.")
print("Press Ctrl+C when done to see the summary.\n")

try:
    signal.pause()
except KeyboardInterrupt:
    print("\n\n=== Summary ===")
    for pin, name in sorted(results.items()):
        print(f"  GPIO{pin}  ->  {name}")
    print(f"\nTotal: {len(results)} sensors.")
