import datetime as dt

import pytest

from alfiebot.spelling.lists import SpellingList, SpellingLists, week_id, week_label
from alfiebot.spelling.progress import ProgressTracker
from alfiebot.spelling.words import clean_word, parse_spelled_answer, parse_word_list, spell_out
from alfiebot.storage.json_store import JsonStore


def test_parse_word_list_splits_cleans_and_rejects():
    good, bad = parse_word_list("Because, friend\npeople people  4ever be-cause")
    assert good == ["because", "friend", "people"]
    assert bad == ["4ever", "be-cause"]


def test_clean_word():
    assert clean_word("  Because. ") == "because"
    assert clean_word("two words") is None
    assert clean_word("") is None


def test_spell_out():
    assert spell_out("because") == "B-E-C-A-U-S-E"
    assert spell_out("cat", slow=True) == "C... A... T..."


@pytest.mark.parametrize("text", ["because", "b e c a u s e", "B-E-C-A-U-S-E", "B, E, C, A, U, S, E"])
def test_typed_answers(text):
    answer = parse_spelled_answer(text, "typed")
    assert answer.letters == "because" and answer.confident


def test_spoken_letter_names():
    answer = parse_spelled_answer("bee ee see ay you ess ee", "voice", 0.95)
    assert answer.letters == "because" and answer.confident


def test_spoken_double_letters():
    assert parse_spelled_answer("are ee ay double el why", "voice").letters == "really"


def test_unsure_recogniser_is_not_confident():
    answer = parse_spelled_answer("f r i e n d", "voice", confidence=0.4)
    assert answer.letters == "friend" and not answer.confident


def test_spoken_whole_word_needs_confirming():
    # Saying "because" isn't spelling it, so AlfieBot must check.
    assert not parse_spelled_answer("because", "voice").confident


def test_week_id_and_label():
    assert week_id(dt.date(2026, 10, 27)) == "2026-W44"
    assert week_label("2026-W44") == "week beginning 26 Oct 2026"
    assert week_label("nonsense") == "nonsense"


def test_lists_saved_by_week(tmp_path):
    lists = SpellingLists(JsonStore(tmp_path))
    assert lists.add_words("2026-W44", ["because", "Friend", "because", "4ever"]) == ["because", "friend"]
    lists.add_words("2026-W45", ["people"])
    assert lists.weeks() == ["2026-W44", "2026-W45"]
    assert lists.load("2026-W44").words == ["because", "friend"]
    lists.remove_word("2026-W44", "because")
    assert lists.load("2026-W44").words == ["friend"]
    lists.delete("2026-W45")
    assert lists.weeks() == ["2026-W44"]


def test_best_week_falls_back_to_newest_list(tmp_path):
    lists = SpellingLists(JsonStore(tmp_path))
    assert lists.best_week("2026-W46") is None
    lists.add_words("2026-W43", ["could"])
    lists.add_words("2026-W44", ["would"])
    assert lists.best_week("2026-W46") == "2026-W44"
    assert lists.best_week("2026-W43") == "2026-W43"


def test_bad_words_in_file_are_ignored():
    sl = SpellingList.from_json({"words": ["Because", "12", "because", "friend"]}, "2026-W44")
    assert sl.words == ["because", "friend"] and sl.week == "2026-W44"


def test_progress_tracks_attempts_and_practice_needed(tmp_path):
    store = JsonStore(tmp_path)
    p = ProgressTracker(store)
    p.record_attempt("because", False, "test", "becos")
    p.record_attempt("because", True, "practice", "because")
    p.record_attempt("friend", False, "test", "frend")
    p.record_attempt("people", True, "test", "people")
    p.record_session("test", "2026-W44", {"friend": False, "people": True})
    again = ProgressTracker(store)  # read back from disk
    e = again.word("because")
    assert (e["attempts"], e["correct"], e["incorrect"]) == (2, 1, 1)
    assert e["last_practised"] == dt.date.today().isoformat()
    assert e["history"][0]["answer"] == "becos"
    assert again.words_needing_practice(["because", "friend", "people", "new"]) == ["friend"]
    assert again.sessions()[0]["incorrect"] == ["friend"]
    assert again.sessions()[0]["score"] == 1
