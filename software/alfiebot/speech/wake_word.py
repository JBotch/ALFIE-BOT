"""An offline "Hey AlfieBot" wake word using the speech model AlfieBot
already has (Vosk), so nothing new is downloaded.

While AlfieBot is asleep or idle, and only if a parent has switched the wake
word on (``privacy.wake_word_enabled``, off by default) and allowed the
microphone, the robot opens the microphone with a tiny grammar: the wake
phrases and "[unk]" for everything else. Audio is processed in memory and
never saved. Anything that isn't the wake phrase, said clearly enough, is
dropped without being shown or kept anywhere.
"""

import logging
from typing import List

from alfiebot.conversation.intents import split_wake_phrase
from alfiebot.speech.base import RecognitionResult, SpeechRecognizer, WakeWordDetector

log = logging.getLogger(__name__)

# Said as two words. If a speech model doesn't know "alfie", the wake word
# simply never fires; tools/measure_voice.py checks this with a synthetic voice.
WAKE_PHRASES = ["hey alfie bot", "hi alfie bot", "hello alfie bot", "okay alfie bot", "alfie bot",
                "hey alfie", "hi alfie"]


class GrammarWakeWord(WakeWordDetector):
    name = "offline speech model"

    def __init__(self, recognizer: SpeechRecognizer, enabled: bool = False, min_confidence: float = 0.7):
        self.recognizer = recognizer
        self.enabled = enabled
        self.min_confidence = min_confidence
        self._detected = False
        self.heard = 0  # wake phrases accepted
        self.rejected = 0  # things heard while asleep that weren't a clear wake phrase

    @property
    def configured(self) -> bool:
        return self.enabled and self.recognizer.available

    @property
    def status(self) -> str:
        if not self.enabled:
            return "off (parent setting)"
        if not self.recognizer.available:
            return f"needs the microphone: {self.recognizer.unavailable_reason or 'unavailable'}"
        return "on, offline"

    @property
    def grammar(self) -> List[str]:
        return list(WAKE_PHRASES)

    def check(self, result: RecognitionResult) -> bool:
        """True if ``result`` is a clear "Hey AlfieBot"."""
        woke, _ = split_wake_phrase(result.text)
        confidences = [c for w, c in result.words if w in ("alfie", "bot", "alfiebot")] or [result.confidence]
        if woke and min(confidences) >= self.min_confidence:
            self.heard += 1
            self._detected = True
            log.info("Wake word heard (confidence %.2f)", min(confidences))
            return True
        self.rejected += 1
        log.debug("Heard something while asleep that wasn't the wake word; ignored")
        return False

    def poll(self) -> bool:
        detected, self._detected = self._detected, False
        return detected
