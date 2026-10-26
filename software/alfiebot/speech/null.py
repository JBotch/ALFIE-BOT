"""Placeholder speech engines used until real ones are configured."""

import logging

from alfiebot.speech.base import SpeechRecognizer, TextToSpeech, WakeWordDetector

log = logging.getLogger(__name__)


class NoSpeechRecognizer(SpeechRecognizer):
    name = "none"

    def __init__(self, reason: str = "No speech recogniser configured (arrives in Stage 4)"):
        self._reason = reason

    @property
    def available(self) -> bool:
        return False

    @property
    def unavailable_reason(self) -> str:
        return self._reason

    def start_listening(self) -> None:
        log.warning("Microphone requested, but %s", self._reason[0].lower() + self._reason[1:])


class TranscriptOnlyTTS(TextToSpeech):
    """Shows what AlfieBot would say instead of speaking it."""

    name = "transcript only"

    def __init__(self):
        self.spoken = []

    def speak(self, text: str) -> None:
        self.spoken.append(text)
        log.info("(speech output disabled) AlfieBot would say: %s", text)


class NoWakeWordDetector(WakeWordDetector):
    name = "none"

    @property
    def configured(self) -> bool:
        return False

    @property
    def status(self) -> str:
        return "No wake-word engine configured. Type \"Hey AlfieBot\" instead."
