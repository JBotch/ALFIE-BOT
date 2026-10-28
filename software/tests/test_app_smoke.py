"""Launch the real apps headless for a few frames."""

from alfiebot.main import main


def test_simulator_launches():
    assert main(["--simulator", "--platform", "simulator", "--frames", "20"]) == 0


def test_face_only_demo_launches():
    assert main(["--face-only", "--windowed", "--demo", "--platform", "simulator", "--frames", "20"]) == 0


def test_letter_test_panel_and_spoken_letters_draw():
    import tempfile

    import pygame

    from alfiebot.config import load_config
    from alfiebot.core.robot import AlfieBot
    from alfiebot.hardware.simulator import create_simulator_platform
    from alfiebot.ui.log_capture import MemoryLogHandler
    from alfiebot.ui import widgets
    from alfiebot.ui.simulator_app import SimulatorApp

    pygame.init()
    widgets._fonts.clear()  # fonts cached by the earlier launch died with pygame.quit()
    config = load_config()
    config["data_dir"] = tempfile.mkdtemp(prefix="alfiebot-test-")
    config["config_path"] = config["data_dir"] + "/alfiebot.json"  # don't change the real settings
    robot = AlfieBot(config, create_simulator_platform(config, speech=False))
    app = SimulatorApp(robot, config, MemoryLogHandler())
    robot.spelling_lists.add_words(robot.tutor.active_week, ["cat"])
    robot.start_spelling("test")
    robot.tutor.handle("see ay", "voice", words=[("see", 0.9), ("ay", 0.3)])
    assert robot.spelling_letters()[0] == [("C", True), ("A", False)]
    app.run(max_frames=3)
    app._toggle_letter_test()
    app.letter_test.start()  # no microphone: typed mode
    assert not robot.external_mic
    app.letter_test._typed("bee")
    app.run(max_frames=3)
    app.letter_test.stop()
    assert "Letter recognition report" in app.letter_test.report
    app._toggle_voice()
    app.voice._set_profile("teacher")
    app.run(max_frames=3)
    assert robot.voice_profile == "teacher"
    app.voice._set_personality("bubbly")
    app.voice.tab = "try"
    app.voice.play_example("Hello!", "normal", "wake")
    app.run(max_frames=3)
    assert robot.personality == "bubbly" and robot.voice_profile == "auto"
    pygame.quit()


def test_learning_tabs_draw_and_parent_controls_work():
    import tempfile

    import pygame

    from alfiebot.config import load_config
    from alfiebot.core.robot import AlfieBot
    from alfiebot.hardware.simulator import create_simulator_platform
    from alfiebot.ui import widgets
    from alfiebot.ui.log_capture import MemoryLogHandler
    from alfiebot.ui.simulator_app import SimulatorApp

    pygame.init()
    widgets._fonts.clear()
    config = load_config()
    config["data_dir"] = tempfile.mkdtemp(prefix="alfiebot-test-")
    config["config_path"] = config["data_dir"] + "/alfiebot.json"
    robot = AlfieBot(config, create_simulator_platform(config, speech=False))
    app = SimulatorApp(robot, config, MemoryLogHandler())
    robot.spelling_lists.add_words(robot.tutor.active_week, ["cat", "dog"])
    robot.start_spelling("test")
    robot.tutor.handle(robot.tutor.current_word)
    for tab in ("progress", "changes"):
        app.spelling.toggle(tab)
        app.run(max_frames=2)  # draws with the test running: words hidden
    robot.tutor.stop()
    panel = app.spelling
    change = robot.progress.adaptations()[0]
    panel._undo(change["id"])
    assert robot.progress.adaptations()[0]["reverted_at"]
    panel._export()
    assert panel.message.startswith("Saved") and panel.message.endswith(".csv")
    panel._reset_all()
    assert robot.progress.known_words()  # first click only arms it
    panel._reset_all()
    assert robot.progress.known_words() == [] and robot.spelling_lists.load(robot.tutor.active_week).words
    app.run(max_frames=2)
    pygame.quit()
