"""Placeholder speech engines used until real ones are configured."""

import logging

from alfiebot.speech.base import SpeechRecognizer, TextToSpeech, WakeWordDetector

log = logging.getLogger(__name__)


class NoSpeechRecognizer(SpeechRecognizer):
    name = "none"

    def __init__(self, reason: str = "Speech recognition is switched off in the config"):
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
    """Shows what AlfieBot would say instead of speaking it.

    It still "talks" for as long as the sentence would take to say, so the
    mouth animation and state changes behave as they will with real speech.
    """

    name = "transcript only"
    SECONDS_PER_CHARACTER = 0.055  # roughly 150 words a minute
    MIN_SECONDS = 0.8

    def __init__(self):
        self.spoken = []
        self._remaining = 0.0

    @classmethod
    def estimate_seconds(cls, text: str) -> float:
        return max(cls.MIN_SECONDS, len(text) * cls.SECONDS_PER_CHARACTER)

    def speak(self, text: str) -> None:
        self.spoken.append(text)
        self._remaining = self.estimate_seconds(text)
        log.debug("(no speech output yet) AlfieBot says: %s", text)

    @property
    def speaking(self) -> bool:
        return self._remaining > 0

    def stop(self) -> None:
        self._remaining = 0.0

    def update(self, dt: float) -> None:
        self._remaining = max(0.0, self._remaining - dt)


class NoWakeWordDetector(WakeWordDetector):
    name = "none"

    @property
    def configured(self) -> bool:
        return False

    @property
    def status(self) -> str:
        return "No wake-word engine configured. Type \"Hey AlfieBot\" instead."
