"""Hardware interfaces shared by the simulator and the Pi."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from alfiebot.speech.base import SpeechRecognizer, TextToSpeech, WakeWordDetector
from alfiebot.speech.null import NoSpeechRecognizer, NoWakeWordDetector, TranscriptOnlyTTS


class InteractionButton(ABC):
    """The momentary button on top of the robot (push-to-talk / wake)."""

    @property
    @abstractmethod
    def is_pressed(self) -> bool: ...

    def poll_pressed(self) -> bool:
        """True once for each new press."""
        return False

    def poll_released(self) -> bool:
        """True once for each release."""
        return False

    def close(self) -> None:
        pass


@dataclass
class Platform:
    name: str
    button: InteractionButton
    fullscreen_face: bool
    recognizer: SpeechRecognizer = field(default_factory=NoSpeechRecognizer)
    tts: TextToSpeech = field(default_factory=TranscriptOnlyTTS)
    wake_word: WakeWordDetector = field(default_factory=NoWakeWordDetector)

    def close(self) -> None:
        self.button.close()
