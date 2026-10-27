"""Keeps the microphone deaf while AlfieBot is talking.

Speakers and microphone sit a few centimetres apart in the robot, so the
recogniser must ignore audio while speech is playing and for a short tail
afterwards (room echo). The app asks ``mic_allowed`` before passing audio on.
"""


class MicGate:
    def __init__(self, tail_seconds: float = 0.6):
        self.tail_seconds = tail_seconds
        self._speaking = False
        self._tail_left = 0.0

    def set_speaking(self, speaking: bool) -> None:
        if self._speaking and not speaking:
            self._tail_left = self.tail_seconds
        self._speaking = speaking

    def update(self, dt: float) -> None:
        if not self._speaking and self._tail_left > 0:
            self._tail_left = max(0.0, self._tail_left - dt)

    @property
    def mic_allowed(self) -> bool:
        return not self._speaking and self._tail_left <= 0
