"""Raspberry Pi 5 hardware.

NOT YET TESTED ON A RASPBERRY PI. Stage 5 wires up and tests the GPIO
button, I2S amplifier and USB microphone. Until then this module only
tries to open the button with gpiozero and falls back to the simulated
button (space bar / touch) if that fails.
"""

import logging

from alfiebot.hardware.base import InteractionButton, Platform
from alfiebot.hardware.simulator import SimulatedButton

log = logging.getLogger(__name__)


class GpioButton(InteractionButton):
    def __init__(self, pin: int):
        from gpiozero import Button  # imported lazily: only exists on the Pi

        self._button = Button(pin, pull_up=True, bounce_time=0.05)
        self._press_events = 0
        self._release_events = 0
        self._button.when_pressed = self._on_press
        self._button.when_released = self._on_release

    def _on_press(self):
        self._press_events += 1

    def _on_release(self):
        self._release_events += 1

    @property
    def is_pressed(self) -> bool:
        return self._button.is_pressed

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

    def close(self) -> None:
        self._button.close()


def create_pi_platform(config) -> Platform:
    pin = config["hardware"]["button_gpio_pin"]
    try:
        button = GpioButton(pin)
        log.info("Interaction button on GPIO%d", pin)
    except Exception as exc:  # gpiozero missing, no permission, pin busy...
        log.warning("GPIO button unavailable (%s); using space bar instead", exc)
        button = SimulatedButton()
    return Platform(name="raspberry_pi", button=button,
                    fullscreen_face=config["display"]["fullscreen_on_pi"])
