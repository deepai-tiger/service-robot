import sounddevice as sd
import soundfile as sf

# Parameters
duration = 5  # seconds
samplerate = 44100
channels = 1
device = 2  # <-- Your USB mic device index (from earlier)

print("🎙️ Recording for 5 seconds...")

# Record audio
recording = sd.rec(int(duration * samplerate), samplerate=samplerate,
                   channels=channels, dtype='int16', device=device)
sd.wait()  # Wait until recording is finished

# Save as WAV file
sf.write("test_recording.wav", recording, samplerate)

print("✅ Saved as 'test_recording.wav'")
