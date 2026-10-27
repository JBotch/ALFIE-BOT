"""Speech interfaces: recognition, text-to-speech and wake-word detection.

Each is an abstract interface (``base.py``) so engines can be swapped
without touching the rest of the app. Built in: Windows voices and
espeak-ng for speech output (``tts.py``), Vosk for offline recognition
(``vosk_recognizer.py``). The wake word (Stage 5) is still a "not
configured" placeholder that says so honestly.
"""
