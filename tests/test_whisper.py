import numpy as np, whisper, tempfile, soundfile as sf, os, time
import sounddevice as sd
import scipy.signal

MIC, MIC_RATE, WHISPER_RATE, SECS = 1, 44100, 16000, 6
MODEL = "base"          # try "small" later for accuracy comparison

print(f"Loading Whisper {MODEL}...")
t_load = time.time()
model = whisper.load_model(MODEL)
print(f"Model loaded in {time.time()-t_load:.1f}s")

print("Speak Arabic NOW — mouth ~15cm from mic!")
audio = sd.rec(int(SECS * MIC_RATE), samplerate=MIC_RATE,
               channels=1, dtype="float32", device=MIC)
sd.wait()
audio = audio.flatten()

peak = np.abs(audio).max()
print(f"PEAK = {peak:.4f}")

t_res = time.time()
audio_16k = scipy.signal.resample(audio, int(len(audio) * WHISPER_RATE / MIC_RATE))
print(f"Resample took {time.time()-t_res:.1f}s")

sf.write("/tmp/check16k.wav", audio_16k, WHISPER_RATE)

tmp = tempfile.mktemp(suffix=".wav")
sf.write(tmp, audio_16k, WHISPER_RATE)

t0 = time.time()
r = model.transcribe(tmp, language="ar", task="transcribe", fp16=False,
                     temperature=0.0, condition_on_previous_text=False)
print(f"[Whisper {time.time()-t0:.1f}s] Heard: {r['text']!r}")
os.unlink(tmp)
