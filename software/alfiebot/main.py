"""Entry point.

    python -m alfiebot                 simulator (on a PC) or face (on the Pi)
    python -m alfiebot --face-only     face only, windowed on a PC
    python -m alfiebot --face-only --fullscreen --demo
"""

import argparse
import logging
import os
import sys

from alfiebot import __version__
from alfiebot.config import load_config
from alfiebot.core.robot import AlfieBot
from alfiebot.hardware import create_platform
from alfiebot.ui.log_capture import MemoryLogHandler


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="alfiebot", description="AlfieBot companion robot")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--simulator", action="store_true", help="desktop simulator with control panel")
    mode.add_argument("--face-only", action="store_true", help="just the face (what the robot shows)")
    screen = p.add_mutually_exclusive_group()
    screen.add_argument("--fullscreen", action="store_true", help="face full screen")
    screen.add_argument("--windowed", action="store_true", help="face in a window")
    p.add_argument("--demo", action="store_true", help="cycle through all expressions")
    p.add_argument("--platform", choices=["auto", "simulator", "raspberry_pi"])
    p.add_argument("--config", help="path to a config JSON file")
    p.add_argument("--log-level", default="INFO")
    p.add_argument("--frames", type=int, help=argparse.SUPPRESS)  # for automated tests
    p.add_argument("--version", action="version", version=f"AlfieBot {__version__}")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    handler = MemoryLogHandler()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger().addHandler(handler)
    log = logging.getLogger("alfiebot")

    config = load_config(args.config)
    platform = create_platform(config, args.platform)
    log.info("AlfieBot %s on %s platform", __version__, platform.name)

    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    import pygame

    pygame.init()
    robot = AlfieBot(config, platform)
    try:
        face_only = args.face_only or (platform.name == "raspberry_pi" and not args.simulator)
        if face_only:
            from alfiebot.ui.face_app import FaceApp

            fullscreen = args.fullscreen or (platform.fullscreen_face and not args.windowed)
            return FaceApp(robot, config, fullscreen=fullscreen, demo=args.demo).run(args.frames)
        from alfiebot.ui.simulator_app import SimulatorApp

        return SimulatorApp(robot, config, handler).run(args.frames)
    finally:
        robot.close()
        platform.close()
        pygame.quit()


if __name__ == "__main__":
    sys.exit(main())
