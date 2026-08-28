#!/bin/bash
# Launcher for the app-connected mode: BLE server + integrated display/dialogue.
# For the full standalone AI experience run instead:
#     python3 main_ai.py --lang ar
cd "$(dirname "$0")"
source venv/bin/activate

# Stop any old ble_server instance
pkill -f ble_server.py 2>/dev/null || true
sleep 1

# Set the Bluetooth speaker volume (adjust the sink name to your device;
# list sinks with: pactl list short sinks)
pactl set-sink-volume bluez_output.BD_FE_6C_AA_9A_C1.1 60% 2>/dev/null || true

# Start the BLE server in the background
python3 ble_server.py &
BLE_PID=$!

# Start the main integrated loop
DISPLAY=:0 python3 main_integrated.py "$@"

# Cleanup
kill $BLE_PID 2>/dev/null || true
