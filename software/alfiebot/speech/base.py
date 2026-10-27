"""Abstract speech interfaces."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class RecognitionResult:
    text: str
    confidence: float = 1.0  # 0..1; typed input is always 1.0
    source: str = "voice"


class SpeechRecognizer(ABC):
    """Turns microphone audio into text. Audio is never stored by default."""

    name = "base"

    @property
    @abstractmethod
    def available(self) -> bool:
        """True if a working recogniser and microphone are configured."""

    @property
    def unavailable_reason(self) -> str:
        return ""

    @property
    def listening(self) -> bool:
        return False

    def start_listening(self) -> None:
        """Open the microphone and start recognising."""

    def stop_listening(self, finalise: bool = False) -> None:
        """Close the microphone. finalise=True turns what was heard so far
        into a result (push-to-talk release)."""

    def set_grammar(self, phrases) -> None:
        """Optionally limit recognition to these words; None allows anything."""

    def poll(self) -> Optional[RecognitionResult]:
        """Return a finished result if one is ready, else None."""
        return None


class TextToSpeech(ABC):
    name = "base"

    @abstractmethod
    def speak(self, text: str) -> None:
        """Start speaking. Must not block the animation loop."""

    @property
    def speaking(self) -> bool:
        return False

    def stop(self) -> None:
        pass

    def update(self, dt: float) -> None:
        """Called every frame (lets simple engines track timing)."""


class WakeWordDetector(ABC):
    """Listens for "Hey AlfieBot". Replace with a real offline engine later."""

    name = "base"

    @property
    @abstractmethod
    def configured(self) -> bool:
        """True only if a real detector is running."""

    @property
    def status(self) -> str:
        return ""

    def poll(self) -> bool:
        """Return True once per detected wake word."""
        return False
