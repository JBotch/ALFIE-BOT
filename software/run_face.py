"""Run just the face: `python run_face.py` (add --fullscreen on the robot)."""
import sys

from alfiebot.main import main

sys.exit(main(["--face-only"] + sys.argv[1:]))
