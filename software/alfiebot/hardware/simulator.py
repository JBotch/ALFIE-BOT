"""Simulated hardware: the button is the space bar or a panel button."""

from alfiebot.hardware.base import InteractionButton, Platform


class SimulatedButton(InteractionButton):
    def __init__(self):
        self._pressed = False
        self._press_events = 0
        self._release_events = 0

    @property
    def is_pressed(self) -> bool:
        return self._pressed

    def press(self) -> None:
        if not self._pressed:
            self._pressed = True
            self._press_events += 1

    def release(self) -> None:
        if self._pressed:
            self._pressed = False
            self._release_events += 1

    def poll_pressed(self) -> bool:
        if self._press_events:
            self._press_events -= 1
            return True
        return False

    def poll_released(self) -> bool:
        if self._release_events:
            self._release_events -= 1
            return True
        return False


def create_simulator_platform(config, speech: bool = True) -> Platform:
    platform = Platform(name="simulator", button=SimulatedButton(), fullscreen_face=False)
    if speech:
        from alfiebot.speech.factory import create_recognizer, create_tts

        from alfiebot.speech.sounds import create_sounds

        platform.tts = create_tts(config)
        platform.recognizer = create_recognizer(config)
        platform.sounds = create_sounds(config)
    return platform
