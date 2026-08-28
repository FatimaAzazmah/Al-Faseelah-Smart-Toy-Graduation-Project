from gpiozero import Button
import time

FORBIDDEN_PINS = {0, 1, 14, 15}  # EEPROM + UART (RFID) - skip these

# All usable BCM GPIO pins on Raspberry Pi 40-pin header
ALL_PINS = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27]

buttons = {}
for pin in ALL_PINS:
    if pin in FORBIDDEN_PINS:
        continue
    try:
        btn = Button(pin, pull_up=True, bounce_time=0.15)
        buttons[pin] = btn
    except Exception as e:
        print(f"[SKIP] GPIO {pin}: {e}")

print(f"Watching {len(buttons)} GPIO pins.")
print("Bring the magnet close to any sensor...\n")

def make_pressed(pin):
    def handler():
        print(f">>> GPIO {pin}")
    return handler

for pin, btn in buttons.items():
    btn.when_pressed = make_pressed(pin)

try:
    while True:
        time.sleep(0.5)
except KeyboardInterrupt:
    print("\nBye!")
