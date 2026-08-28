#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from gpiozero import Button
import signal

CANDIDATE_PINS = range(2, 28)
active = {}

def on_trigger(pin):
    print(f"GPIO{pin} -> Detected")

for pin in CANDIDATE_PINS:
    try:
        b = Button(pin, pull_up=True, bounce_time=0.05)
        b.when_pressed = (lambda p=pin: on_trigger(p))
        active[pin] = b
    except Exception:
        pass

print(f"Watching {len(active)} pins. Ctrl+C to stop.")
signal.pause()
