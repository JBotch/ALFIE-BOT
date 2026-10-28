"""The learning engine: SQLite records, the review schedule, adaptations,
teaching, and the spelling outcomes from the brief (all with made-up words,
never a child's data)."""

import csv
import datetime as dt
import json
import random

import pytest

from tests.learning_helpers import Clock, make_store, make_tutor

from alfiebot.ai.mock_provider import MockProvider
from alfiebot.config import load_config
from alfiebot.conversation.engine import ConversationEngine
from alfiebot.core.brain import Brain, UserInput
from alfiebot.learning import schedule
from alfiebot.learning.store import LearningProgress, WordLists, import_json
from alfiebot.learning.teaching import clue, leaks_spelling, split_syllables, teach, word_help
from alfiebot.spelling.lists import week_id
from alfiebot.storage.database import Database
from alfiebot.storage.json_store import JsonStore

WEEK = "2026-W44"
WORDS = ["because", "friend", "people", "could", "beautiful", "different", "favourite", "minute"]


def tutor_with(tmp_path, *words, clock=None, **kwargs):
    t = make_tutor(tmp_path, random.Random(1), today=clock, **kwargs)
    t.active_week = WEEK
    t.lists.add_words(WEEK, list(words))
    return t


def voice(tutor, letters, confidence=0.95):
    """Spell a word aloud, say finished, then yes at the read-back."""
    names = {"a": "ay", "b": "bee", "c": "see", "d": "dee", "e": "ee", "f": "eff", "g": "gee", "h": "aitch",
             "i": "eye", "l": "el", "m": "em", "n": "en", "o": "oh", "p": "pee", "r": "are", "s": "ess",
             "t": "tee", "u": "you", "w": "double you", "y": "why"}
    spoken = " ".join(names[c] for c in letters)
    tutor.handle(spoken, "voice", words=[(w, confidence) for w in spoken.split()])
    tutor.handle("finished", "voice")
    return tutor.handle("yes", "voice")


def outcomes(tutor, word):
    return [r["outcome"] for r in tutor.progress.db.query(
        "SELECT outcome FROM attempts WHERE word = ? ORDER BY id", (word,))]


# ---- the review schedule -------------------------------------------------------------
@pytest.mark.parametrize("box,result,expected", [
    (1, schedule.FIRST_TRY, 2), (5, schedule.FIRST_TRY, 5), (3, schedule.WITH_HELP, 3),
    (4, schedule.TAUGHT, 1), (4, schedule.INCORRECT, 1), (2, schedule.SKIPPED, 1),
])
def test_leitner_boxes(box, result, expected):
    assert schedule.next_box(box, result) == expected


def test_review_gaps():
    today = dt.date(2026, 10, 26)
    assert [(schedule.due_date(b, today) - today).days for b in range(1, 6)] == [1, 2, 4, 7, 14]


# ---- lists and progress in SQLite --------------------------------------------------
def test_lists_in_the_database(tmp_path):
    lists, _ = make_store(tmp_path)
    assert lists.add_words(WEEK, ["because", "Friend", "because", "no way"]) == ["because", "friend"]
    assert lists.load(WEEK).words == ["because", "friend"]
    lists.remove_word(WEEK, "because")
    assert lists.load(WEEK).words == ["friend"]
    assert lists.best_week("2026-W45") == WEEK
    lists.delete(WEEK)
    assert lists.weeks() == [] and lists.best_week(WEEK) is None


def test_parent_syllables_and_tip_are_used(tmp_path):
    lists, _ = make_store(tmp_path)
    lists.add_words(WEEK, ["island"], {"island": {"syllables": "is-land", "tip": "An island is land."}})
    info = lists.word_info("island")
    h = word_help("island", **info)
    assert h.syllables == ["is", "land"] and "is land" in teach(h)


def test_progress_survives_a_restart(tmp_path):
    clock = Clock()
    tutor = tutor_with(tmp_path, "because", "friend", clock=clock)
    tutor.start("test")
    first = tutor.current_word
    tutor.handle(first)
    tutor.handle("wrong")
    # A new start: new database connection, store and tutor.
    again = tutor_with(tmp_path, clock=clock)
    assert again.progress.word(first)["box"] == 2 and again.progress.word(first)["correct"] == 1
    assert again.progress.sessions()[-1]["score"] == 1
    assert again.lists.load(WEEK).words == ["because", "friend"]


def test_practice_plan_puts_due_words_first(tmp_path):
    clock = Clock()
    lists, progress = make_store(tmp_path, clock, max_session_words=4, confidence_words=1)
    lists.add_words("2026-W43", ["could", "would"])
    lists.add_words(WEEK, ["because", "friend", "people"])
    progress.record_attempt("could", True)
    progress.finish_word("could", schedule.TAUGHT)  # box 1, due tomorrow
    progress.record_attempt("people", True)
    for _ in range(3):
        progress.finish_word("people", schedule.FIRST_TRY)  # box 4: mastered
    clock.advance(1)
    plan = progress.plan_practice(lists.load(WEEK).words)
    assert plan[0] == "could"  # due from last week
    assert plan[1:3] == ["because", "friend"]  # this week's new words
    assert "people" not in plan[:3] and len(plan) <= 4


def test_repeated_difficulty_gives_an_earlier_clue_and_can_be_undone(tmp_path):
    clock = Clock()
    for _ in range(2):
        tutor = tutor_with(tmp_path, "because", clock=clock)
        tutor.start("test")
        tutor.handle("bekos")
        clock.advance(1)
    progress = tutor.progress
    assert progress.repeated_difficulty("because") and progress.word("because")["early_clue"]
    log = progress.adaptations()
    early = next(a for a in log if a["kind"] == "early_clue")
    assert "two sessions" in early["reason"]
    # Practice now offers the first clue after one mistake.
    tutor = tutor_with(tmp_path, clock=clock)
    tutor.start("practice")
    assert "7 letters" in tutor.handle("bekos").text
    # The parent undoes it: back to encouragement only.
    assert progress.undo(early["id"]) and not progress.word("because")["early_clue"]
    assert not progress.undo(early["id"])  # only once
    tutor.stop()
    tutor.start("practice")
    assert "7 letters" not in tutor.handle("bekos").text


def test_box_moves_are_logged_with_a_reason_and_undo(tmp_path):
    lists, progress = make_store(tmp_path, Clock())
    progress.finish_word("friend", schedule.FIRST_TRY)
    move = progress.adaptations()[0]
    assert move["kind"] == "box" and "box 1 to 2" in move["reason"] and "right first time" in move["reason"]
    assert progress.word("friend")["box"] == 2
    progress.undo(move["id"])
    assert progress.word("friend")["box"] == 1


def test_reset_one_word_and_reset_all_keep_the_lists(tmp_path):
    tutor = tutor_with(tmp_path, "because", "friend")
    tutor.start("test")
    tutor.handle(tutor.current_word)
    tutor.handle(tutor.current_word)
    tutor.progress.reset_word("because")
    assert not tutor.progress.word("because")["seen"] and tutor.progress.word("friend")["seen"]
    tutor.progress.reset_all()
    assert tutor.progress.known_words() == [] and tutor.progress.sessions() == []
    assert tutor.lists.load(WEEK).words == ["because", "friend"]


def test_csv_export(tmp_path):
    tutor = tutor_with(tmp_path, "because")
    tutor.start("test")
    tutor.handle("becos")
    path = tutor.progress.export_csv(tmp_path / "exports")
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    assert {r["record"] for r in rows} == {"word", "attempt"}
    attempt = next(r for r in rows if r["record"] == "attempt")
    assert attempt["word"] == "because" and attempt["outcome"] == "incorrect" and attempt["answer"] == "becos"


def test_json_records_are_copied_once_and_kept(tmp_path):
    store = JsonStore(tmp_path)
    store.save(f"spellings/{WEEK}", {"week": WEEK, "title": "Year 3", "words": ["because", "friend"]})
    store.save("progress", {"words": {
        "because": {"attempts": 2, "correct": 1, "incorrect": 1, "last_practised": "2026-10-20",
                    "history": [{"date": "2026-10-19", "mode": "test", "correct": False, "answer": "becos"},
                                {"date": "2026-10-20", "mode": "practice", "correct": True, "answer": "because"}]},
        "friend": {"attempts": 1, "correct": 0, "incorrect": 1, "last_practised": "2026-10-20",
                   "history": [{"date": "2026-10-20", "mode": "test", "correct": False, "answer": "frend"}]}},
        "sessions": [{"date": "2026-10-20", "mode": "test", "week": WEEK, "score": 0, "total": 1,
                      "incorrect": ["friend"]}]})
    lists, progress = make_store(tmp_path)
    counts = import_json(store, lists, progress)
    assert counts == {"lists": 1, "words": 2, "progress": 2, "sessions": 1}
    assert lists.load(WEEK).words == ["because", "friend"] and lists.load(WEEK).title == "Year 3"
    assert progress.word("because")["box"] == 2 and progress.word("friend")["box"] == 1
    assert progress.word("because")["correct"] == 1
    assert progress.sessions()[0]["incorrect"] == ["friend"]
    assert import_json(store, lists, progress) is None  # only once
    assert (tmp_path / "progress.json").exists() and (tmp_path / "spellings" / f"{WEEK}.json").exists()


def test_learning_tables_never_need_an_ai(tmp_path):
    db = Database(tmp_path)
    db.migrate()
    tables = {r["name"] for r in db.query("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"word_lists", "words", "word_progress", "sessions", "attempts", "adaptations", "preferences"} <= tables
    columns = {r["name"] for r in db.query("PRAGMA table_info(attempts)")}
    assert "provider" not in columns  # the AI provider is never part of a mark


# ---- teaching ---------------------------------------------------------------------
def test_syllables():
    assert split_syllables("because") == ["be", "cause"]
    assert split_syllables("people") == ["peo", "ple"]
    assert split_syllables("minute") == ["mi", "nute"]
    assert split_syllables("friend") == ["friend"]


@pytest.mark.parametrize("word", WORDS)
def test_clues_never_spell_the_word(word):
    h = word_help(word)
    for level in (1, 2):
        text = clue(h, level)
        assert not leaks_spelling(text, word)
        assert "-".join(word.upper()) not in text
    assert "-".join(word.upper()) in teach(h)  # only the teaching step does


def test_leak_check():
    assert leaks_spelling("It starts B-E-C", "because")
    assert leaks_spelling("try b, e, c, a", "because")
    assert leaks_spelling("say B E C", "because")
    assert not leaks_spelling("Because has 7 letters", "because")
    assert not leaks_spelling("starts with B and ends with E", "because")


# ---- the spelling outcomes the brief asks for ----------------------------------------
def test_correct_spoken_spelling(tmp_path):
    tutor = tutor_with(tmp_path, "cat")
    tutor.start("test")
    reply = voice(tutor, "cat")
    assert reply.celebrate
    assert outcomes(tutor, "cat") == ["correct"]
    assert tutor.progress.word("cat")["box"] == 2


def test_incorrect_spelling(tmp_path):
    tutor = tutor_with(tmp_path, "cat")
    tutor.start("test")
    reply = voice(tutor, "cot")
    assert "C-A-T" not in reply.text
    assert outcomes(tutor, "cat") == ["incorrect"]
    assert tutor.progress.word("cat")["box"] == 1


def test_ambiguous_letter_is_clarified_not_marked_wrong(tmp_path):
    tutor = tutor_with(tmp_path, "bed")
    tutor.start("test")
    tutor.handle("bee ee dee finished", "voice", words=[("bee", 0.95), ("ee", 0.95), ("dee", 0.4), ("finished", 0.9)])
    assert tutor.stage == "clarify"
    assert tutor.progress.word("bed")["attempts"] == 0  # nothing marked
    tutor.handle("D for dog", "voice", words=[("dee", 0.9), ("for", 0.9), ("dog", 0.9)])
    reply = tutor.handle("yes", "voice")
    assert reply.celebrate
    entry = tutor.progress.word("bed")
    assert entry["correct"] == 1 and entry["incorrect"] == 0 and entry["unclear"] == 1


def test_recognition_failure_is_not_a_mistake(tmp_path):
    tutor = tutor_with(tmp_path, "cat")
    tutor.start("test")
    reply = tutor.handle("banana", "voice", words=[("banana", 0.3)])
    assert "letter" in reply.text.lower()
    assert outcomes(tutor, "cat") == ["unclear"]
    entry = tutor.progress.word("cat")
    assert entry["incorrect"] == 0 and entry["attempts"] == 0 and tutor.current_word == "cat"


def test_child_asks_for_help(tmp_path):
    tutor = tutor_with(tmp_path, "because")
    tutor.start("practice")
    assert "7 letters" in tutor.handle("clue", "voice").text
    assert outcomes(tutor, "because") == ["help_requested"]
    assert tutor.progress.word("because")["hints"] == 1


def test_repeated_wrong_answers_lead_to_teaching_not_the_same_question(tmp_path):
    tutor = tutor_with(tmp_path, "because")
    tutor.start("practice")
    texts = [tutor.handle("bekos").text for _ in range(3)]
    assert len(set(texts)) == 3  # each reply adds something new
    assert "B-E-C-A-U-S-E" in texts[-1]
    assert outcomes(tutor, "because") == ["incorrect", "incorrect", "incorrect", "taught"]


def test_success_after_hints_keeps_the_box(tmp_path):
    clock = Clock()
    tutor = tutor_with(tmp_path, "because", clock=clock)
    tutor.start("practice")
    tutor.handle("because")  # first try: box 2
    clock.advance(2)
    tutor.handle("no")  # say no to a test
    tutor.start("practice")
    tutor.handle("clue")
    reply = tutor.handle("because")
    assert reply.celebrate
    assert tutor.progress.word("because")["box"] == 2  # right with a clue: stays put


def test_test_mode_can_reveal_when_a_parent_chooses(tmp_path):
    tutor = tutor_with(tmp_path, "cat", reveal_after_test_mistake=True)
    tutor.start("test")
    assert "C-A-T" in tutor.handle("cot").text


def test_switching_ai_provider_during_an_activity_keeps_progress(tmp_path):
    config = load_config()
    config["cloud"]["enabled"] = False
    tutor = make_tutor(tmp_path, random.Random(0))
    tutor.lists.add_words(week_id(), ["cat", "dog"])
    local = MockProvider("mock-local", "local", rng=random.Random(0))
    brain = Brain(config, ConversationEngine("AlfieBot", rng=random.Random(0)), tutor, local, None)
    brain.handle(UserInput("help me practise my spellings"))
    assert tutor.mode == "practice"
    first = tutor.current_word
    brain.handle(UserInput(first))
    brain.router.local = MockProvider("other", "local", rng=random.Random(1))  # switch mid-activity
    brain.router.mode = "automatic"
    second = tutor.current_word
    brain.handle(UserInput(second))
    assert tutor.progress.word(first)["correct"] == 1 and tutor.progress.word(second)["correct"] == 1
    assert local.calls == 0 and brain.router.local.calls == 0  # no AI marked anything
    again = make_tutor(tmp_path)  # and after a restart
    assert again.progress.word(second)["box"] == 2
