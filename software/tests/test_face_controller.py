"""The face controller: approved expressions and validated face commands,
applied by the face view without blocking the robot."""

import tempfile
import time

import pygame
import pytest

from alfiebot.config import load_config
from alfiebot.core.actions import parse_response
from alfiebot.core.robot import AlfieBot
from alfiebot.core.states import DESIGN_EXPRESSIONS, Expression, RobotState
from alfiebot.face.controller import AI_EXPRESSIONS, MAX_SECONDS, MIN_SECONDS, ai_expression, face_command
from alfiebot.hardware.simulator import create_simulator_platform
from alfiebot.ui import widgets
from alfiebot.ui.face_test_panel import DEMO_SECONDS, PANEL_EXPRESSIONS, FaceTestPanel
from alfiebot.ui.face_view import FaceView


def make_robot():
    config = load_config()
    config["data_dir"] = tempfile.mkdtemp(prefix="alfiebot-test-")
    config["config_path"] = config["data_dir"] + "/alfiebot.json"
    return AlfieBot(config, create_simulator_platform(config, speech=False))


@pytest.mark.parametrize("name", ["angry", "sleeping", "sleepy", "processing", "dancing", "", "Happy()"])
def test_ai_cannot_ask_for_unapproved_expressions(name):
    assert ai_expression(name) is None


def test_ai_expressions_and_aliases():
    assert ai_expression("happy") == Expression.HAPPY
    assert ai_expression("proud") == Expression.LOVE
    assert ai_expression("looking_around") == Expression.LOOKING_AROUND
    assert Expression.ANGRY not in AI_EXPRESSIONS


def test_ai_reply_asking_for_angry_gets_happy():
    response, notes = parse_response({"speech": "Grr!", "expression": "angry", "action": None})
    assert response.expression == Expression.HAPPY
    assert notes


def test_face_commands_are_validated_and_clamped():
    assert face_command("look", "LEFT").value == "left"
    assert face_command("look", "up", seconds=100).seconds == MAX_SECONDS
    assert face_command("blink", "ignored", seconds=0).seconds == MIN_SECONDS
    assert face_command("talk_test", 1).value is True
    for kind, value in (("draw", None), ("look", "behind"), ("look", "import os")):
        with pytest.raises(ValueError):
            face_command(kind, value)


def test_robot_refuses_bad_commands_and_keeps_the_queue_short():
    robot = make_robot()
    assert not robot.face_command("explode")
    assert not robot.face_command("look", "sideways")
    assert robot.face_commands == []
    for _ in range(50):
        assert robot.face_command("blink")
    assert len(robot.face_commands) <= 20


def test_face_view_applies_commands_on_the_next_frame():
    pygame.init()
    robot = make_robot()
    view = FaceView(robot, robot.config)
    robot.face_command("look", "left", seconds=2)
    robot.face_command("talk_test", True)
    view.update(1 / 30)
    assert robot.face_commands == []
    assert view.test_talking and view.engine.talking
    for _ in range(30):
        view.update(1 / 30)
    assert view.engine.frame().pose.gaze_x < -0.3
    robot.face_command("talk_test", False)
    view.update(1 / 30)
    assert not view.engine.talking


def test_face_commands_do_not_change_the_robot_state():
    robot = make_robot()
    robot.start()
    state = robot.state
    robot.face_command("look_around")
    robot.face_command("double_blink")
    robot.update(0.1)
    assert robot.state == state


def test_panel_has_every_design_expression_and_buttons_show_them():
    pygame.init()
    widgets._fonts.clear()  # fonts cached by an earlier app launch died with pygame.quit()
    robot = make_robot()
    panel = FaceTestPanel(robot, (0, 0, 800, 220))
    panel.face = FaceView(robot, robot.config)
    assert all(e in PANEL_EXPRESSIONS for e in DESIGN_EXPRESSIONS) and len(DESIGN_EXPRESSIONS) == 16
    panel.toggle()
    surface = pygame.Surface((800, 220))
    panel.draw(surface, (0, 0), 0)
    # Click the "Wink" button.
    rect = next(r for r, action in panel._hits
                if getattr(action, "__defaults__", None) == (Expression.WINK,))
    assert panel.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center))
    assert robot.expression == Expression.WINK


def test_panel_demo_cycles_all_sixteen_and_reset_returns_to_neutral():
    pygame.init()
    robot = make_robot()
    panel = FaceTestPanel(robot, (0, 0, 800, 220))
    panel.face = FaceView(robot, robot.config)
    panel._toggle_demo()
    seen = []
    for _ in range(16):
        panel.update(DEMO_SECONDS)
        seen.append(robot.expression)
    assert seen == list(DESIGN_EXPRESSIONS)
    panel._set_speed(2.0)
    assert panel.face.engine.time_scale == 2.0
    panel._reset()
    assert not panel.demo
    assert panel.face.engine.time_scale == 1.0
    assert robot.expression == Expression.NEUTRAL


def test_spelling_still_works_with_the_face_test_open():
    pygame.init()
    robot = make_robot()
    panel = FaceTestPanel(robot, (0, 0, 800, 220))
    panel.face = FaceView(robot, robot.config)
    panel.toggle()
    panel._toggle_demo()
    robot.spelling_lists.add_words(robot.tutor.active_week, ["cat"])
    robot.start_spelling("test")
    end = time.monotonic() + 10  # speech timing is in real time
    while robot.state != RobotState.SPELLING_TEST and time.monotonic() < end:
        robot.update(1 / 30)
        panel.update(1 / 30)
        panel.face.update(1 / 30)
        time.sleep(0.001)
    assert robot.state == RobotState.SPELLING_TEST
    robot.tutor.handle("see ay tee", "voice", words=[("see", 0.95), ("ay", 0.95), ("tee", 0.95)])
    assert [letter for letter, _ in robot.spelling_letters()[0]] == ["C", "A", "T"]
