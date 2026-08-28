#!/usr/bin/env python3
"""
RDM6300 RFID Reader Test - Al-Faseelah World
Port: /dev/ttyAMA0 (GPIO 14/15) - NOT serial0!
Frame: 0x02 | 10 hex chars (data) | 2 hex chars (checksum) | 0x03
Exit with Ctrl+C only!
"""
import serial
import time
import sys

PORT = "/dev/ttyAMA0"
BAUD = 9600

def verify_checksum(data_hex, checksum_hex):
    try:
        data_bytes = bytes.fromhex(data_hex)
        checksum = int(checksum_hex, 16)
    except ValueError:
        return False
    x = 0
    for b in data_bytes:
        x ^= b
    return x == checksum

def main():
    try:
        ser = serial.Serial(PORT, BAUD, timeout=1)
    except serial.SerialException as e:
        print(f"[ERROR] Could not open {PORT}: {e}")
        sys.exit(1)

    ser.reset_input_buffer()
    print("=" * 50)
    print(f"  RFID TEST on {PORT}")
    print("  Bring a tag near the coil... (Ctrl+C to exit)")
    print("=" * 50)

    last_tag = None
    last_time = 0

    try:
        while True:
            b = ser.read(1)
            if b != b"\x02":
                continue

            frame = ser.read(13)  # 10 data + 2 checksum + 1 end
            if len(frame) < 13 or frame[-1:] != b"\x03":
                print("[WARN] Incomplete frame, skipping...")
                ser.reset_input_buffer()
                continue

            payload = frame[:12].decode("ascii", errors="ignore")
            data_hex = payload[:10]
            checksum_hex = payload[10:12]

            if not verify_checksum(data_hex, checksum_hex):
                print(f"[WARN] Bad checksum for {data_hex}, ignoring")
                continue

            tag_id = data_hex[2:]          # last 8 hex = card ID
            tag_decimal = int(tag_id, 16)

            now = time.time()
            if tag_id == last_tag and (now - last_time) < 2.0:
                continue
            last_tag, last_time = tag_id, now

            print(f"\n[TAG] hex: {tag_id}   decimal: {tag_decimal}")
            print(f"      full frame data: {data_hex}")

    except KeyboardInterrupt:
        print("\n[EXIT] Bye!")
    finally:
        ser.close()

if __name__ == "__main__":
    main()
