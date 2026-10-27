"""The robot opening and closing the microphone, with a fake recogniser."""

import tempfile

from alfiebot.config import load_config
from alfiebot.core.robot import AlfieBot
from alfiebot.core.states import RobotState
from alfiebot.hardware.simulator import create_simulator_platform
from alfiebot.speech.base import RecognitionResult, SpeechRecognizer
from alfiebot.spelling.letter_input import letter_grammar


class FakeRecognizer(SpeechRecognizer):
    def __init__(self):
        self._listening = False
        self.queue = []
        self.grammar = None
        self.finalised = 0
        self.opened = 0

    @property
    def available(self):
        return True

    @property
    def listening(self):
        return self._listening

    def start_listening(self):
        self._listening = True
        self.opened += 1

    def stop_listening(self, finalise=False):
        self._listening = False
        self.finalised += finalise

    def set_grammar(self, phrases):
        self.grammar = phrases

    def poll(self):
        return self.queue.pop(0) if self.queue else None

    def hear(self, text, confidence=0.95, words=None):
        self.queue.append(RecognitionResult(text, confidence, "voice", words or []))


def make_robot(allowed=True, mode="open"):
    config = load_config()
    config["data_dir"] = tempfile.mkdtemp(prefix="alfiebot-test-")
    config["privacy"]["microphone_enabled"] = allowed
    config["speech"]["mic_mode"] = mode
    platform = create_simulator_platform(config, speech=False)
    platform.recognizer = FakeRecognizer()
    robot = AlfieBot(config, platform)
    return robot, platform.recognizer


def tick(robot, seconds, step=1 / 30):
    for _ in range(int(seconds / step)):
        robot.update(step)


def until_listening(robot, limit=20.0):
    t = 0.0
    while t < limit:
        robot.update(1 / 30)
        t += 1 / 30
        if robot.state in (RobotState.LISTENING, RobotState.SPELLING_SETUP,
                           RobotState.SPELLING_PRACTICE, RobotState.SPELLING_TEST) \
                and not robot._timers and robot.mic_gate.mic_allowed:
            robot.update(1 / 30)
            return
    raise AssertionError(f"never listened (state {robot.state})")


def robot_lines(robot):
    return [e.text for e in robot.transcript.entries if e.speaker == "robot"]


def test_mic_stays_closed_unless_a_parent_allows_it():
    robot, mic = make_robot(allowed=False)
    robot.start()
    robot.handle_text("Hey AlfieBot")
    until_listening(robot)
    assert not mic.listening and mic.opened == 0


def test_mic_closed_while_idle_and_while_talking():
    robot, mic = make_robot()
    robot.start()
    tick(robot, 1.0)
    assert not mic.listening  # idle: no wake-word engine yet, so no listening
    robot.handle_text("Hey AlfieBot")
    tick(robot, 0.2)
    assert robot.state == RobotState.SPEAKING
    assert not mic.listening  # never hears its own voice
    until_listening(robot)
    assert mic.listening


def test_voice_reply_flow():
    robot, mic = make_robot()
    robot.start()
    robot.handle_text("Hey AlfieBot")
    until_listening(robot)
    mic.hear("how are you")
    robot.update(1 / 30)
    assert robot.state == RobotState.THINKING
    assert not mic.listening
    assert robot.transcript.entries[-1].source == "voice"
    until_listening(robot)
    assert "circuits" in robot_lines(robot)[-1] or "systems" in robot_lines(robot)[-1] \
        or "batteries" in robot_lines(robot)[-1] or "working" in robot_lines(robot)[-1]


def test_switch_off_in_panel_closes_mic():
    robot, mic = make_robot()
    robot.start()
    robot.handle_text("Hey AlfieBot")
    until_listening(robot)
    robot.mic_switch = False
    robot.update(1 / 30)
    assert not mic.listening


def test_push_to_talk_only_while_button_held():
    robot, mic = make_robot(mode="push_to_talk")
    robot.start()
    robot.handle_text("Hey AlfieBot")
    until_listening(robot)
    assert not mic.listening
    robot.platform.button.press()
    robot.update(1 / 30)
    assert mic.listening
    robot.platform.button.release()
    robot.update(1 / 30)
    assert not mic.listening and mic.finalised == 1


def test_spelling_answers_use_the_letter_grammar_and_unsure_answers_are_checked():
    robot, mic = make_robot()
    robot.spelling_lists.add_words(robot.tutor.active_week, ["because"])
    robot.start_spelling("test")
    until_listening(robot)
    assert mic.grammar == letter_grammar("child")
    assert robot.recognition_mode == "letters"
    said = len(robot_lines(robot))
    # One unsure letter: "bee ee see ay you ESS? ee".
    words = [(w, 0.95) for w in "bee ee see ay you".split()] + [("ess", 0.4), ("ee", 0.95)]
    mic.hear("bee ee see ay you ess ee", words=words)
    robot.update(1 / 30)
    assert robot.state == RobotState.SPELLING_TEST and mic.listening  # silent, still listening
    assert len(robot_lines(robot)) == said
    letters, _ = robot.spelling_letters()
    assert "".join(l for l, _ in letters) == "BECAUSE" and letters[5] == ("S", False)
    mic.hear("finished")
    robot.update(1 / 30)
    until_listening(robot)
    assert "letter 6" in robot_lines(robot)[-1] and "S for sun" in robot_lines(robot)[-1]
    assert robot.progress.word("because")["attempts"] == 0
    mic.hear("s for sun")
    robot.update(1 / 30)
    until_listening(robot)
    assert "B-E-C-A-U-S-E" in robot_lines(robot)[-1]  # read back before marking
    mic.hear("yes")
    robot.update(1 / 30)
    until_listening(robot)
    assert robot.progress.word("because")["correct"] == 1


def test_pause_after_letters_reads_them_back():
    robot, mic = make_robot()
    robot.spelling_lists.add_words(robot.tutor.active_week, ["cat"])
    robot.start_spelling("practice")
    until_listening(robot)
    mic.hear("see ay tee")
    robot.update(1 / 30)
    said = len(robot_lines(robot))
    tick(robot, robot.finish_after_pause - 0.5)
    assert len(robot_lines(robot)) == said
    tick(robot, 1.5)
    assert "C-A-T" in robot_lines(robot)[-1]
    assert robot.progress.word("cat")["attempts"] == 0
