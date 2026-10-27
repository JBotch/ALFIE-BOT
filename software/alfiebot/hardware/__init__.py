"""Hardware abstraction: the same app runs on a PC or on the Raspberry Pi."""

from alfiebot.hardware.base import Platform
from alfiebot.hardware.detect import create_platform, is_raspberry_pi

__all__ = ["Platform", "create_platform", "is_raspberry_pi"]
