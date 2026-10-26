"""Double-click or run `python run_simulator.py` to open the simulator."""
import sys

from alfiebot.main import main

sys.exit(main(["--simulator"] + sys.argv[1:]))
