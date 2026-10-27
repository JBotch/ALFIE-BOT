import tempfile

from alfiebot.config import load_config
from alfiebot.core.robot import AlfieBot
from alfiebot.core.states import Expression, RobotState
from alfiebot.hardware.simulator import create_simulator_platform


def make_robot():
    config = load_config()
    config["data_dir"] = tempfile.mkdtemp(prefix="alfiebot-test-")
    robot = AlfieBot(config, create_simulator_platform(config, speech=False))
    faces = []
    robot.add_face_listener(lambda expr, talking: faces.append((expr, talking)))
    return robot, faces


def test_starts_asleep_and_wakes_on_start():
    robot, faces = make_robot()
    assert robot.state == RobotState.SLEEPING
    assert faces[-1] == (Expression.SLEEPING, False)
    robot.start()
    assert robot.running and robot.state == RobotState.IDLE
    assert faces[-1] == (Expression.IDLE, False)
    robot.stop()
    assert robot.state == RobotState.SLEEPING


def test_state_drives_face_and_talking():
    robot, faces = make_robot()
    robot.start()
    robot.set_state(RobotState.SPEAKING)
    assert faces[-1] == (Expression.HAPPY, True)
    robot.set_state(RobotState.CELEBRATING)
    assert faces[-1] == (Expression.EXCITED, False)
    robot.set_state(RobotState.ERROR)
    assert faces[-1] == (Expression.CONFUSED, False)


def test_expression_preview_and_follow_state():
    robot, faces = make_robot()
    robot.start()
    robot.show_expression(Expression.THINKING)
    assert faces[-1][0] == Expression.THINKING
    robot.show_expression(None)
    assert faces[-1][0] == Expression.IDLE
    robot.show_expression(Expression.HAPPY)
    robot.set_state(RobotState.LISTENING)  # a state change ends the preview
    assert faces[-1][0] == Expression.LISTENING


def test_typed_text_ignored_while_stopped():
    robot, _ = make_robot()
    robot.handle_text("Hey AlfieBot")
    assert len(robot.transcript.entries) == 0
    robot.start()
    robot.handle_text("Hey AlfieBot")
    assert robot.transcript.entries[0].speaker == "user"
    assert robot.transcript.entries[0].text == "Hey AlfieBot"


def test_microphone_gated_while_speaking():
    robot, _ = make_robot()
    robot.start()
    assert robot.mic_gate.mic_allowed
    robot.set_state(RobotState.SPEAKING)
    assert not robot.mic_gate.mic_allowed
    robot.set_state(RobotState.IDLE)
    assert not robot.mic_gate.mic_allowed  # echo tail
    robot.update(1.0)
    assert robot.mic_gate.mic_allowed


def test_button_press_wakes_robot():
    robot, _ = make_robot()
    robot.platform.button.press()
    robot.update(0.016)
    assert robot.running
    assert robot.state == RobotState.SPEAKING  # "Yes? I'm listening!"


def test_no_fake_wake_word_or_microphone():
    robot, _ = make_robot()
    assert not robot.platform.wake_word.configured
    assert not robot.platform.recognizer.available
