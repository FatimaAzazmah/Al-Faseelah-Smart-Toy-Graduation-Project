import pyaudio
import json
import numpy as np
from scipy import signal
from vosk import Model, KaldiRecognizer

MIC_RATE  = 44100
VOSK_RATE = 16000
CHUNK     = 8192

# Download the Arabic model from https://alphacephei.com/vosk/models
# and unzip it next to the repo (folder: vosk-model-ar-mgb2-0.4).
model = Model("vosk-model-ar-mgb2-0.4")
rec   = KaldiRecognizer(model, VOSK_RATE)

p = pyaudio.PyAudio()
stream = p.open(
    format=pyaudio.paInt16,
    channels=1,
    rate=MIC_RATE,
    input=True,
    input_device_index=0,
    frames_per_buffer=CHUNK,
)
stream.start_stream()
print("Listening... (Ctrl+C to stop)")

def resample(data):
    audio = np.frombuffer(data, dtype=np.int16)
    resampled = signal.resample_poly(audio, VOSK_RATE, MIC_RATE)
    return resampled.astype(np.int16).tobytes()

counter = 0
try:
    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        resampled = resample(data)
        counter += 1
        if rec.AcceptWaveform(resampled):
            result = json.loads(rec.Result())
            text = result.get("text", "").strip()
            print(f"\n[RESULT] '{text}'")
        else:
            partial = json.loads(rec.PartialResult())
            p_text = partial.get("partial", "").strip()
            if p_text:
                print(f"[PARTIAL] '{p_text}'", end="\r")
            elif counter % 10 == 0:
                print(f"[listening... {counter}]", end="\r")
except KeyboardInterrupt:
    print("\nStopped.")

stream.stop_stream()
stream.close()
p.terminate()
