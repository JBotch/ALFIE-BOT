"""Speech interfaces: recognition, text-to-speech and wake-word detection.

Each is an abstract interface so an offline engine (for example Vosk,
Piper or openWakeWord) can be plugged in later without touching the rest
of the app. Stage 1 ships only the "not configured" implementations, which
say honestly that no real engine is present.
"""
