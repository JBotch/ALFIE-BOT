"""The letter recognition test tool and its report."""

import random

from alfiebot.speech.letter_test import LETTER_SETS, LetterTestSession, format_report, load_trials, summarise
from alfiebot.storage.json_store import JsonStore

NAMES = {"b": "bee", "d": "dee", "p": "pee", "m": "em", "n": "en"}


def test_all_26_letters_and_the_confusing_sets():
    assert len(LETTER_SETS["all"]) == 26
    for name in ("B/D/P", "C/G/T", "M/N", "F/S", "A/H/J"):
        assert name in LETTER_SETS
    session = LetterTestSession("all", rounds=2, rng=random.Random(1))
    assert sorted(session.prompts) == sorted(LETTER_SETS["all"] * 2)


def test_clear_result_moves_on_and_records_everything():
    session = LetterTestSession("B/D/P", speaker="Alfie", speed="slow", rng=random.Random(2))
    letter = session.current
    assert session.record(NAMES[letter], [(NAMES[letter], 0.92)], latency=0.6) == "next"
    t = session.trials[0]
    assert (t.expected, t.recognised, t.final, t.correct) == (letter, letter, letter, True)
    assert t.confidence == 0.92 and t.latency == 0.6 and not t.clarification_required
    assert (t.speaker, t.speed) == ("Alfie", "slow")


def test_unsure_result_asks_again_and_keeps_the_first_guess():
    session = LetterTestSession("M/N", rng=random.Random(3))
    letter = session.current
    other = "m" if letter == "n" else "n"
    assert session.record(NAMES[other], [(NAMES[other], 0.3)]) == "clarify"
    session.record(NAMES[letter], [(NAMES[letter], 0.9)])
    t = session.trials[0]
    assert t.clarification_required and t.recognised == other and t.final == letter and t.correct


def test_nothing_heard_twice_is_a_miss():
    session = LetterTestSession("M/N", rng=random.Random(3))
    assert session.nothing_heard() == "clarify"
    session.nothing_heard()
    assert session.trials[0].final == "" and not session.trials[0].correct


def test_report_shows_mix_ups_speakers_and_speeds(tmp_path):
    store = JsonStore(tmp_path)
    for speaker, speed, wrong in (("Alfie", "normal", True), ("Dad", "slow", False)):
        session = LetterTestSession("B/D/P", speaker=speaker, speed=speed, rng=random.Random(4))
        while not session.done:
            said = session.current
            heard = ("d" if said == "b" else said) if wrong else said
            session.record(NAMES[heard], [(NAMES[heard], 0.95)], latency=0.5)
        session.save(store)
    trials = load_trials(store)
    assert len(trials) == 6
    summary = summarise(trials)
    assert summary["confusions"][0] == (("b", "d"), 1)
    assert summary["wrong_but_sure"] == 1
    report = format_report(trials)
    assert "B -> D" in report and "Alfie" in report and "Dad" in report and "slow" in report
    assert format_report([]) == "No letter tests recorded yet."
