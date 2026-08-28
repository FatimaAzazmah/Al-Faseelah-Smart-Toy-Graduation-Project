# -*- coding: utf-8 -*-
# PIN MAPPER — touch a sensor with a magnet, name it, save the map!
import time, json
from gpiozero import Button

# All usable pins (BCM) — excluding RFID UART (14,15) and EEPROM (0,1)
CANDIDATE_PINS = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13,
                  16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27]

print("Setting up pins...")
sensors = {}
for pin in CANDIDATE_PINS:
    try:
        # reed switch to GND, internal pull-up
        sensors[pin] = Button(pin, pull_up=True, bounce_time=0.1)
    except Exception as e:
        print(f"  (skip GPIO {pin}: {e})")

print(f"Watching {len(sensors)} pins.")
print("=" * 50)
print("TOUCH a sensor with the magnet now!")
print("(Ctrl+C when finished — map auto-saves)")
print("=" * 50)

pin_map = {}
try:
    # load previous progress if exists
    try:
        pin_map = json.load(open("pin_map.json"))
        print(f"Loaded {len(pin_map)} already-mapped pins:", pin_map)
    except FileNotFoundError:
        pass

    already_active = {p for p, s in sensors.items() if s.is_pressed}
    if already_active:
        print(f"Note: pins already active at start (magnet resting?): {sorted(already_active)}")

    last_state = {p: s.is_pressed for p, s in sensors.items()}
    while True:
        for pin, s in sensors.items():
            now = s.is_pressed
            if now and not last_state[pin]:
                print(f"\n🧲 MAGNET DETECTED on GPIO {pin}!")
                if str(pin) in pin_map:
                    print(f"   (already named: {pin_map[str(pin)]} — type new name to overwrite, or Enter to keep)")
                name = input(f"   What piece is this? > ").strip()
                if name:
                    pin_map[str(pin)] = name
                    json.dump(pin_map, open("pin_map.json", "w"),
                              ensure_ascii=False, indent=2)
                    print(f"   ✅ saved: GPIO {pin} = {name}   (total: {len(pin_map)})")
            last_state[pin] = now
        time.sleep(0.05)
except KeyboardInterrupt:
    print("\n" + "=" * 50)
    print("FINAL MAP:")
    for pin, name in sorted(pin_map.items(), key=lambda x: int(x[0])):
        print(f"  GPIO {pin:>2} = {name}")
    print(f"\nSaved to pin_map.json ({len(pin_map)} pieces)")
    print("\n-- SQL (physical wiring -> database): --")
    for pin, name in sorted(pin_map.items(), key=lambda x: int(x[0])):
        print(f"UPDATE pieces SET sensor_pin = {pin} WHERE key = '{name}';")
