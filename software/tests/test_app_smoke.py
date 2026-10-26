"""Launch the real apps headless for a few frames."""

from alfiebot.main import main


def test_simulator_launches():
    assert main(["--simulator", "--platform", "simulator", "--frames", "20"]) == 0


def test_face_only_demo_launches():
    assert main(["--face-only", "--windowed", "--demo", "--platform", "simulator", "--frames", "20"]) == 0
