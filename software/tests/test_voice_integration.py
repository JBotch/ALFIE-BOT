"""Phase 6: the offline wake word, one-letter-at-a-time spelling, and the
time per answer (fake recogniser; no audio)."""

import random

from tests.learning_helpers import make_tutor
from tests.test_microphone_flow import make_robot, robot_lines, tick, until_listening

from alfiebot.core.states import RobotState
from alfiebot.speech.base import RecognitionResult
from alfiebot.speech.sounds import SoundEffects
from alfiebot.speech.wake_word import WAKE_PHRASES, GrammarWakeWord

WEEK = "2026-W44"
ASLEEP = (RobotState.SLEEPING, RobotState.IDLE)


def wake_robot(wake=True, allowed=True, mode="open"):
    robot, rec = make_robot(allowed, mode)
    robot.set_wake_word(wake)
    robot.start()
    tick(robot, 0.2)
    return robot, rec


def test_wake_word_is_off_by_default():
    robot, rec = make_robot()
    robot.start()
    tick(robot, 0.2)
    assert robot.state in ASLEEP
    assert not robot.config["privacy"]["wake_word_enabled"]
    assert not rec.listening and not robot.wake_word.configured


def test_asleep_with_the_wake_word_on_listens_only_for_hey_alfiebot():
    robot, rec = wake_robot()
    assert rec.listening and rec.grammar == WAKE_PHRASES
    assert robot.recognition_mode == "wake"
    rec.hear("the cat sat on the mat")
    tick(robot, 0.2)
    assert robot.state in ASLEEP
    assert list(robot.transcript.entries) == []  # never shown or kept
    rec.hear("hey alfie bot", words=[("hey", 0.9), ("alfie", 0.92), ("bot", 0.95)])
    tick(robot, 0.2)
    assert robot.state not in ASLEEP
    until_listening(robot)
    assert rec.grammar is None  # ordinary conversation again
    assert robot_lines(robot)  # said hello


def test_unclear_wake_phrase_is_ignored():
    robot, rec = wake_robot()
    rec.hear("hey alfie bot", 0.5, words=[("hey", 0.9), ("alfie", 0.4), ("bot", 0.6)])
    tick(robot, 0.2)
    assert robot.state in ASLEEP
    assert robot.wake_word.rejected == 1


def test_wake_word_needs_the_microphone_allowed_and_open_mode():
    robot, rec = wake_robot(allowed=False)
    assert not rec.listening
    robot, rec = wake_robot(mode="push_to_talk")
    assert not rec.listening  # the button wakes AlfieBot instead


def test_parent_can_switch_the_wake_word_off():
    robot, rec = wake_robot()
    assert rec.listening
    robot.set_wake_word(False)
    tick(robot, 0.1)
    assert not rec.listening


def test_wake_word_check():
    class Rec:
        available = True

    ww = GrammarWakeWord(Rec(), enabled=True, min_confidence=0.7)
    assert ww.check(RecognitionResult("hey alfie bot", 0.9, "voice", [("alfie", 0.9), ("bot", 0.9)]))
    assert ww.poll() and not ww.poll()
    assert not ww.check(RecognitionResult("alfie", 0.99, "voice", [("alfie", 0.99)]))  # a name alone
    assert not ww.check(RecognitionResult("hello", 0.99, "voice", [("hello", 0.99)]))


# ---- one letter at a time -------------------------------------------------------
def test_one_letter_at_a_time_keeps_the_first_and_asks_for_the_next(tmp_path):
    tutor = make_tutor(tmp_path, random.Random(0), recognition_mode="letter_by_letter")
    tutor.active_week = WEEK
    tutor.lists.add_words(WEEK, ["bed"])
    tutor.start("test")
    reply = tutor.handle("bee ee", "voice", words=[("bee", 0.9), ("ee", 0.9)])
    assert "One letter at a time" in reply.text or "one letter each time" in reply.text.lower()
    assert tutor.answer.text == "b"
    assert tutor.handle("ee", "voice", words=[("ee", 0.9)]) is None
    assert tutor.handle("dee", "voice", words=[("dee", 0.9)]) is None
    assert tutor.answer.text == "bed" and tutor.letters_heard == 3
    tutor.handle("finished", "voice")
    assert tutor.handle("yes", "voice").celebrate
    session = tutor.progress.db.query("SELECT recognition_mode FROM sessions")[0]
    assert session["recognition_mode"] == "letter_by_letter"


def test_continuous_mode_takes_a_run_of_letters(tmp_path):
    tutor = make_tutor(tmp_path, random.Random(0))
    tutor.active_week = WEEK
    tutor.lists.add_words(WEEK, ["bed"])
    tutor.start("test")
    assert tutor.handle("bee ee dee", "voice", words=[("bee", 0.9), ("ee", 0.9), ("dee", 0.9)]) is None
    assert tutor.answer.text == "bed"


def test_robot_ticks_after_each_letter_in_one_at_a_time_mode():
    robot, rec = make_robot()
    robot.platform.sounds = SoundEffects(player=lambda data: None)
    robot.tutor.recognition_mode = "letter_by_letter"
    robot.spelling_lists.add_words(robot.tutor.active_week, ["cat"])
    robot.start_spelling("test")
    until_listening(robot)
    played = robot.platform.sounds.played
    before = played.count("letter")
    rec.hear("see", words=[("see", 0.95)])
    tick(robot, 0.1)
    assert played.count("letter") == before + 1


def test_time_per_answer_is_saved(tmp_path):
    tutor = make_tutor(tmp_path, random.Random(0))
    tutor.active_week = WEEK
    tutor.lists.add_words(WEEK, ["cat"])
    tutor.start("test")
    tutor.handle("cat")
    row = tutor.progress.db.query("SELECT seconds FROM attempts")[0]
    assert row["seconds"] is not None and row["seconds"] >= 0


# ---- AI replies, voice and face timing ------------------------------------------
def test_slow_ai_answer_makes_the_eyes_look_around_then_speaks_with_a_profile():
    from tests.test_brain import UNKNOWN, make_robot as ai_robot, run_until

    robot = ai_robot()
    robot.brain.local.delay_s = 2.0
    robot.handle_text(UNKNOWN)
    assert robot.state == RobotState.THINKING
    run_until(robot, lambda: any(c.kind == "look_around" for c in robot.face_commands), seconds=4)
    run_until(robot, lambda: robot.state == RobotState.SPEAKING, seconds=6)
    assert robot.last_profile  # the AI's words go through the personality's voice profiles
    assert robot.expression == robot._speaking_mood  # the AI's chosen expression while it talks
    robot.close()
