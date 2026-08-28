#!/usr/bin/env python3
"""UART loopback test: jumper wire between Pin 8 (GPIO14 TX) and Pin 10 (GPIO15 RX)."""
import serial

PORT = "/dev/ttyAMA0"   # GPIO 14/15 on Pi 5
ser = serial.Serial(PORT, 9600, timeout=2)
ser.reset_input_buffer()

msg = b"FASEELAH_TEST_123"
ser.write(msg)
received = ser.read(len(msg))
ser.close()

if received == msg:
    print(f"[OK] GPIO 15 is ALIVE! ({PORT}) Received:", received.decode())
else:
    print(f"[FAIL] on {PORT} | Sent:", msg, "| Received:", received)
