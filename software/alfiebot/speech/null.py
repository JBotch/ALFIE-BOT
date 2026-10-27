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

    It still "talks" for as long as the sentence would take to say (at the
    voice profile's pace), so the mouth animation and state changes behave
    as they will with real speech.
    """

    name = "transcript only"
    SECONDS_PER_CHARACTER = 0.055  # roughly 150 words a minute
    SECONDS_PER_LETTER = 0.35
    MIN_SECONDS = 0.8

    def __init__(self, profiles=None):
        from alfiebot.speech.voice_profiles import DEFAULT_PROFILES

        self.profiles = dict(profiles or DEFAULT_PROFILES)
        self.speed = 1.0
        self.spoken = []
        self.profiles_used = []
        self._remaining = 0.0

    @classmethod
    def estimate_seconds(cls, text: str, profile=None) -> float:
        if profile is None:
            return max(cls.MIN_SECONDS, len(text) * cls.SECONDS_PER_CHARACTER)
        from alfiebot.speech.text import Pause, Say, plan_speech

        total = 0.0
        for seg in plan_speech(text, profile):
            if isinstance(seg, Pause):
                total += seg.seconds
            elif isinstance(seg, Say):
                total += len(seg.text) * cls.SECONDS_PER_CHARACTER / profile.rate
            else:
                total += cls.SECONDS_PER_LETTER / profile.rate
        return max(cls.MIN_SECONDS, total)

    def speak(self, text: str, profile=None) -> None:
        p = self.profiles.get(profile or "normal") or self.profiles["normal"]
        self.spoken.append(text)
        self.profiles_used.append(p.name)
        self._remaining = self.estimate_seconds(text, p) / max(0.3, self.speed)
        log.debug("(no speech output) AlfieBot says (%s): %s", p.name, text)

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
