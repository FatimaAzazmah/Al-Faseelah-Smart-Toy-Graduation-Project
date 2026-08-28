#!/usr/bin/env python3
"""
RDM6300 RFID reader module - Al-Faseelah World
Port: /dev/ttyAMA0 (GPIO 14/15)
Usage:
    from rfid_reader import RFIDReader
    reader = RFIDReader()
    tag = reader.wait_for_tag()          # blocking
    tag = reader.check_tag(timeout=0.1)  # non-blocking-ish, None if nothing
"""
import serial
import time

PORT = "/dev/ttyAMA0"
BAUD = 9600
DEBOUNCE_SECONDS = 3.0   # ignore same tag re-read within this window


def _verify_checksum(data_hex, checksum_hex):
    try:
        data_bytes = bytes.fromhex(data_hex)
        checksum = int(checksum_hex, 16)
    except ValueError:
        return False
    x = 0
    for b in data_bytes:
        x ^= b
    return x == checksum


class RFIDReader:
    def __init__(self, port=PORT, baud=BAUD):
        self.ser = serial.Serial(port, baud, timeout=0.2)
        self.ser.reset_input_buffer()
        self._last_tag = None
        self._last_time = 0.0

    def _try_read_frame(self):
        """Try to read one frame. Returns tag hex or None."""
        b = self.ser.read(1)
        if b != b"\x02":
            return None
        frame = self.ser.read(13)
        if len(frame) < 13 or frame[-1:] != b"\x03":
            self.ser.reset_input_buffer()
            return None
        payload = frame[:12].decode("ascii", errors="ignore")
        data_hex, checksum_hex = payload[:10], payload[10:12]
        if not _verify_checksum(data_hex, checksum_hex):
            return None
        tag = data_hex[2:]
        if tag == "00000000":   # defective/null tag
            return None
        # debounce
        now = time.time()
        if tag == self._last_tag and (now - self._last_time) < DEBOUNCE_SECONDS:
            return None
        self._last_tag, self._last_time = tag, now
        return tag

    def wait_for_tag(self):
        """Block until a valid tag is scanned. Returns 8-char hex ID."""
        self.ser.reset_input_buffer()
        while True:
            tag = self._try_read_frame()
            if tag:
                return tag

    def check_tag(self, timeout=0.1):
        """Check briefly for a tag. Returns tag or None."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            tag = self._try_read_frame()
            if tag:
                return tag
        return None

    def close(self):
        self.ser.close()


if __name__ == "__main__":
    # quick self-test
    r = RFIDReader()
    print("Scan a tag... (Ctrl+C to exit)")
    try:
        while True:
            print("[TAG]", r.wait_for_tag())
    except KeyboardInterrupt:
        print("\nBye!")
    finally:
        r.close()
