"""Choose the simulator or Raspberry Pi platform."""

import logging
from pathlib import Path

from alfiebot.hardware.base import Platform

log = logging.getLogger(__name__)


def is_raspberry_pi() -> bool:
    try:
        model = Path("/proc/device-tree/model").read_text(errors="ignore")
    except OSError:
        return False
    return "Raspberry Pi" in model


def create_platform(config, override: str = None) -> Platform:
    choice = override or config.get("platform", "auto")
    if choice == "auto":
        choice = "raspberry_pi" if is_raspberry_pi() else "simulator"
    if choice == "raspberry_pi":
        from alfiebot.hardware.raspberry_pi import create_pi_platform

        return create_pi_platform(config)
    if choice != "simulator":
        log.warning("Unknown platform %r, using the simulator", choice)
    from alfiebot.hardware.simulator import create_simulator_platform

    return create_simulator_platform(config)
