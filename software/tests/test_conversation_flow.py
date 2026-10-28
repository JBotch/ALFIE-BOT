"""The robot's state machine driven by typed input, with simulated time."""

import random
import tempfile

from alfiebot.config import load_config
from alfiebot.conversation.engine import ConversationEngine
from alfiebot.core.robot import AlfieBot
from alfiebot.core.states import Expression, RobotState
from alfiebot.hardware.simulator import create_simulator_platform


def make_robot(ai=True, **timing):
    config = load_config()
    config["conversation"].update(timing)
    config["ai"]["enabled"] = ai
    config["data_dir"] = tempfile.mkdtemp(prefix="alfiebot-test-")
    config["ai"]["local_provider"] = "mock"  # never a real Ollama in tests
    robot = AlfieBot(config, create_simulator_platform(config, speech=False),
                     ConversationEngine("AlfieBot", rng=random.Random(0)))
    states = []
    robot.state_machine.add_listener(lambda old, new: states.append(new))
    return robot, states


def tick(robot, seconds, step=1 / 30):
    for _ in range(int(seconds / step)):
        robot.update(step)


def say(robot, text):
    robot.handle_text(text)


def finish_talking(robot):
    for _ in range(2000):
        if robot.state not in (RobotState.THINKING, RobotState.SPEAKING) and not robot._timers:
            return
        robot.update(1 / 30)
    raise AssertionError("robot never stopped talking")


def robot_lines(robot):
    return [e.text for e in robot.transcript.entries if e.speaker == "robot"]


def test_wake_from_sleep_greets_then_listens():
    robot, states = make_robot()
    robot.running = True  # asleep but switched on
    say(robot, "Hey AlfieBot")
    assert robot.state == RobotState.IDLE  # eyes opening first
    tick(robot, 1.0)
    assert robot.state == RobotState.SPEAKING
    assert robot.expression == Expression.EXCITED
    assert robot.talking
    assert not robot.mic_gate.mic_allowed  # can't hear itself
    finish_talking(robot)
    assert robot.state == RobotState.LISTENING
    assert states[:3] == [RobotState.IDLE, RobotState.SPEAKING, RobotState.LISTENING]
    assert "how are you today" in robot_lines(robot)[-1].lower()


def test_full_example_conversation():
    robot, states = make_robot()
    robot.start()
    say(robot, "Hey AlfieBot")
    finish_talking(robot)
    say(robot, "I'm good.")
    assert robot.state == RobotState.THINKING
    assert robot.expression == Expression.THINKING
    finish_talking(robot)
    assert "what shall we do" in robot_lines(robot)[-1].lower() or "what would you like" in robot_lines(robot)[-1].lower()
    say(robot, "How are you?")
    finish_talking(robot)
    say(robot, "What can you do?")
    finish_talking(robot)
    assert len(robot_lines(robot)) == 4
    assert robot.state == RobotState.LISTENING
    assert RobotState.THINKING in states and RobotState.SPEAKING in states


def test_wake_phrase_with_command():
    robot, _ = make_robot()
    robot.start()
    say(robot, "Hey AlfieBot, what can you do?")
    assert robot.state == RobotState.THINKING
    finish_talking(robot)
    assert "spelling" in robot_lines(robot)[-1].lower()


def test_idle_ignores_text_without_wake_phrase():
    robot, _ = make_robot()
    robot.start()
    say(robot, "How are you?")
    assert robot.state == RobotState.IDLE
    assert robot_lines(robot) == []
    assert robot.transcript.entries[-1].speaker == "system"


def test_listening_times_out_to_idle_then_sleeps():
    robot, _ = make_robot(listen_timeout=3.0, sleep_after_idle=5.0)
    robot.start()
    say(robot, "Hey AlfieBot")
    finish_talking(robot)
    assert robot.state == RobotState.LISTENING
    tick(robot, 2.0)
    assert robot.state == RobotState.LISTENING
    tick(robot, 1.5)
    assert robot.state == RobotState.IDLE
    tick(robot, 5.5)
    assert robot.state == RobotState.SLEEPING


def test_text_while_talking_is_answered_afterwards():
    robot, _ = make_robot()
    robot.start()
    say(robot, "Hey AlfieBot")
    tick(robot, 0.1)
    assert robot.state == RobotState.SPEAKING
    say(robot, "tell me a joke")
    assert robot.state == RobotState.SPEAKING  # not interrupted
    finish_talking(robot)
    assert len(robot_lines(robot)) == 2
    assert robot.conversation.last_reply.intent == "joke"


def test_fallback_shows_confused_face_while_talking():
    robot, _ = make_robot(ai=False)
    robot.start()
    say(robot, "Hey AlfieBot")
    finish_talking(robot)
    say(robot, "what is the capital of peru")
    tick(robot, 1.0)
    assert robot.state == RobotState.SPEAKING
    assert robot.expression == Expression.CONFUSED


def test_spelling_request_enters_spelling_setup():
    robot, _ = make_robot()
    robot.start()
    say(robot, "Hey AlfieBot, help me with my spellings")
    finish_talking(robot)
    assert robot.state == RobotState.SPELLING_SETUP
    assert robot.expression == Expression.LISTENING
    say(robot, "take a test")
    finish_talking(robot)
    # No spellings saved yet, so AlfieBot offers to add some.
    assert "add" in robot_lines(robot)[-1].lower()
    assert robot.state == RobotState.SPELLING_SETUP
    assert robot.tutor.active


def test_goodbye_goes_to_sleep():
    robot, _ = make_robot()
    robot.start()
    say(robot, "Hey AlfieBot")
    finish_talking(robot)
    say(robot, "goodbye")
    finish_talking(robot)
    assert robot.state == RobotState.SLEEPING
    assert robot.running


def test_hey_alfiebot_while_listening_acknowledges():
    robot, _ = make_robot()
    robot.start()
    say(robot, "Hey AlfieBot")
    finish_talking(robot)
    say(robot, "Hey AlfieBot")
    assert robot.state == RobotState.SPEAKING
    assert robot.conversation.last_reply.intent == "wake_again"


def test_button_interrupts_speech_and_listens():
    robot, _ = make_robot()
    robot.start()
    say(robot, "Hey AlfieBot")
    tick(robot, 0.2)
    assert robot.state == RobotState.SPEAKING
    robot.press_button()
    assert robot.state == RobotState.LISTENING
    assert not robot.platform.tts.speaking


def test_engine_crash_shows_error_then_recovers():
    robot, states = make_robot()
    robot.start()
    say(robot, "Hey AlfieBot")
    finish_talking(robot)

    def boom(text):
        raise RuntimeError("test")

    robot.conversation.respond = boom
    say(robot, "hello")
    assert robot.state == RobotState.ERROR
    assert robot.expression == Expression.CONFUSED
    finish_talking(robot)
    tick(robot, 2.0)
    finish_talking(robot)
    assert robot.state == RobotState.LISTENING
    assert "muddle" in robot_lines(robot)[-1]


def test_stop_while_talking():
    robot, _ = make_robot()
    robot.start()
    say(robot, "Hey AlfieBot")
    tick(robot, 0.2)
    robot.stop()
    assert robot.state == RobotState.SLEEPING
    tick(robot, 5)
    assert robot.state == RobotState.SLEEPING


def setup_words(robot, *words):
    robot.spelling_lists.add_words(robot.tutor.active_week, list(words))


def test_spelling_practice_by_conversation():
    robot, states = make_robot()
    setup_words(robot, "because", "friend")
    robot.start()
    say(robot, "Hey AlfieBot")
    finish_talking(robot)
    say(robot, "Help me with my spellings")
    finish_talking(robot)
    assert "add" in robot_lines(robot)[-1] and "test" in robot_lines(robot)[-1]
    assert robot.state == RobotState.SPELLING_SETUP
    say(robot, "practise them")
    finish_talking(robot)
    assert robot.state == RobotState.SPELLING_PRACTICE
    assert "spell because" in robot_lines(robot)[-1].lower()
    assert "B-E-C-A-U-S-E" not in robot_lines(robot)[-1]  # asked, not told
    say(robot, "because")
    tick(robot, 0.6)
    assert robot.state == RobotState.CELEBRATING
    assert robot.expression == Expression.EXCITED
    finish_talking(robot)
    assert robot.state == RobotState.SPELLING_PRACTICE
    say(robot, "stop")
    finish_talking(robot)
    assert robot.state == RobotState.LISTENING
    assert not robot.tutor.active
    say(robot, "how are you")  # back to normal chat
    finish_talking(robot)
    assert robot.conversation.last_reply.intent == "how_are_you"


def test_spelling_test_from_panel_and_progress_saved():
    robot, _ = make_robot()
    setup_words(robot, "because", "friend")
    robot.start_spelling("test")
    tick(robot, 1.5)
    finish_talking(robot)
    assert robot.state == RobotState.SPELLING_TEST
    assert robot.expression == Expression.LISTENING
    while robot.tutor.mode == "test":
        say(robot, robot.tutor.current_word)
        finish_talking(robot)
    assert robot.progress.sessions()[-1]["score"] == 2
    assert robot.state == RobotState.LISTENING


def test_add_word_without_saying_spellings():
    robot, _ = make_robot()
    robot.start()
    say(robot, "Hey AlfieBot, add the word because")
    finish_talking(robot)
    assert "B-E-C-A-U-S-E. Is that correct?" in robot_lines(robot)[-1]
    say(robot, "yes")
    finish_talking(robot)
    assert robot.spelling_lists.load(robot.tutor.active_week).words == ["because"]


def test_going_idle_ends_the_spelling_activity():
    robot, _ = make_robot(listen_timeout=2.0)
    setup_words(robot, "because")
    robot.start_spelling("practice")
    finish_talking(robot)
    tick(robot, 1.5)
    finish_talking(robot)
    assert robot.tutor.active
    tick(robot, 2.5)
    assert robot.state == RobotState.IDLE
    assert not robot.tutor.active
