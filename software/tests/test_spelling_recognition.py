"""Spelling recognition: letters spoken one at a time, commands, unsure
letters and reading back before marking."""

import json
import random

import pytest

from tests.learning_helpers import make_tutor as new_tutor

from alfiebot.spelling.letter_input import (Command, Letter, LetterSequence, Unknown, confusable_with,
                                           heard_letters, letter_grammar, parse_letters)
from alfiebot.spelling.tutor import SpellingTutor
from alfiebot.speech.vosk_recognizer import parse_result
from alfiebot.storage.json_store import JsonStore

WEEK = "2026-W44"


def make_tutor(tmp_path, *words, **kwargs):
    t = new_tutor(tmp_path, random.Random(5), **kwargs)
    t.active_week = WEEK
    t.lists.add_words(WEEK, list(words))
    return t


def sure(text):
    """Words all heard with high confidence, as Vosk would report them."""
    return [(w, 0.95) for w in text.split()]


def shown(tutor):
    return "".join(letter for letter, _ in tutor.answer.display())


# ---- parsing ------------------------------------------------------------
def test_letter_names_commands_and_unknown_words():
    tokens = parse_letters("bee ee see delete see double ess finished")
    assert [t.letter for t in tokens if isinstance(t, Letter)] == list("beccss")
    assert [t.name for t in tokens if isinstance(t, Command)] == ["delete", "finish"]
    assert parse_letters("because") == [Unknown("because", 1.0)]
    assert heard_letters("are ee ay double el why") == "really"
    assert heard_letters("double you") == "w"


def test_each_letter_keeps_its_own_confidence():
    tokens = parse_letters("bee dee", words=[("bee", 0.9), ("dee", 0.3)])
    assert [(t.letter, t.confidence) for t in tokens] == [("b", 0.9), ("d", 0.3)]


def test_phonetic_words():
    b, = parse_letters("b for ball")
    assert b.letter == "b" and b.phonetic
    assert heard_letters("delta oscar golf") == "dog"
    # The word and the letter disagree: it gets asked about, not guessed.
    odd, = parse_letters("dee for ball")
    assert odd.letter == "b" and not odd.phonetic and odd.confidence == 0.0


def test_confusion_sets():
    assert confusable_with("d") == ["b", "d", "p"]
    assert confusable_with("n") == ["m", "n"]
    assert confusable_with("j") == ["a", "h", "j"]
    assert confusable_with("o") == ["o", "r"]  # British R ("ah") is heard as "oh"
    assert confusable_with("w") == ["w"]


def test_british_r_and_words_vosk_does_not_know():
    assert parse_letters("ah", [("ah", 0.9)], 0.9)[0].letter == "r"
    grammar = letter_grammar("child")
    assert "ah" in grammar
    for word in ("aitch", "haitch", "backspace", "x-ray", "xray"):
        assert word not in grammar


def test_grammar_has_letters_commands_and_phonetic_words():
    grammar = letter_grammar("child")
    for word in ("bee", "zed", "delete", "finished", "start", "again", "yes", "ball", "for"):
        assert word in grammar
    assert "bravo" not in grammar
    assert "bravo" in letter_grammar("nato")


def test_sequence_display_marks_unsure_letters():
    seq = LetterSequence(0.75)
    seq.add("b", 0.9)
    seq.add("d", 0.4)
    seq.add("?", 0.0)
    assert seq.display() == [("B", True), ("D", False), ("?", False)]
    assert seq.unsure_index() == 1
    seq.delete()
    assert seq.text == "bd"


def test_vosk_result_keeps_per_word_confidence():
    raw = json.dumps({"text": "bee dee", "result": [{"word": "bee", "conf": 0.91},
                                                    {"word": "dee", "conf": 0.42}]})
    result = parse_result(raw)
    assert result.words == [("bee", 0.91), ("dee", 0.42)]


# ---- building an answer ------------------------------------------------
def test_letters_build_up_silently_across_several_results(tmp_path):
    tutor = make_tutor(tmp_path, "because")
    tutor.start("test")
    assert tutor.handle("bee ee", "voice", words=sure("bee ee")) is None
    assert tutor.handle("see", "voice", words=sure("see")) is None
    assert tutor.handle("ay you ess ee", "voice", words=sure("ay you ess ee")) is None
    assert shown(tutor) == "BECAUSE"
    assert tutor.collecting_letters


def test_delete_removes_the_last_letter(tmp_path):
    tutor = make_tutor(tmp_path, "because")
    tutor.start("test")
    tutor.handle("bee ee see dee", "voice", words=sure("bee ee see dee"))
    r = tutor.handle("delete", "voice")
    assert "D" in r.text and "B-E-C" in r.text
    assert shown(tutor) == "BEC"
    # Delete in the middle of a run of letters.
    tutor.handle("ay you delete you", "voice", words=sure("ay you delete you"))
    assert shown(tutor) == "BECAU"


def test_start_again_clears_the_letters_but_keeps_the_word(tmp_path):
    tutor = make_tutor(tmp_path, "because", "friend")
    tutor.start("practice")
    tutor.handle("bee ee", "voice", words=sure("bee ee"))
    r = tutor.handle("start again", "voice")
    assert shown(tutor) == "" and "because" in r.text
    assert tutor.current_word == "because"


def test_repeat_says_the_word_and_keeps_the_letters(tmp_path):
    tutor = make_tutor(tmp_path, "because")
    tutor.start("test")
    tutor.handle("bee ee", "voice", words=sure("bee ee"))
    r = tutor.handle("repeat", "voice")
    assert "because" in r.text and "B-E" in r.text
    assert shown(tutor) == "BE"


def test_finished_with_no_letters(tmp_path):
    tutor = make_tutor(tmp_path, "because")
    tutor.start("test")
    r = tutor.handle("finished", "voice")
    assert "letters" in r.text and tutor.active
    assert tutor.progress.word("because")["attempts"] == 0


# ---- marking ------------------------------------------------------------
def test_correct_spelling_is_marked_after_the_child_agrees(tmp_path):
    tutor = make_tutor(tmp_path, "cat", "dog")
    tutor.start("practice")
    tutor.handle("see ay tee finished", "voice", words=sure("see ay tee finished"))
    assert tutor.stage == "review"
    r = tutor.handle("yes", "voice")
    assert r.celebrate
    assert tutor.progress.word("cat")["correct"] == 1
    assert tutor.current_word == "dog" and shown(tutor) == ""


def test_wrong_spelling_is_marked_wrong_only_when_heard_clearly(tmp_path):
    tutor = make_tutor(tmp_path, "cat", "dog")
    tutor.start("test")
    first = tutor.current_word
    wrong = "kay ay tee" if first == "cat" else "dee oh jay"
    tutor.handle(wrong + " finished", "voice", words=sure(wrong + " finished"))
    tutor.handle("yes", "voice")
    assert tutor.progress.word(first)["incorrect"] == 1


def test_unsure_letter_is_asked_about_never_marked_wrong(tmp_path):
    tutor = make_tutor(tmp_path, "dog")
    tutor.start("test")
    tutor.handle("bee oh gee", "voice", words=[("bee", 0.4), ("oh", 0.95), ("gee", 0.95)])
    r = tutor.handle("finished", "voice")
    assert tutor.stage == "clarify"
    assert "letter 1" in r.text and "B for ball" in r.text and "D for dog" in r.text and "P for pig" in r.text
    assert tutor.progress.word("dog")["attempts"] == 0
    r = tutor.handle("dee for dog", "voice", words=sure("dee for dog"))
    assert tutor.stage == "review" and "D-O-G" in r.text
    tutor.handle("yes", "voice")
    assert tutor.progress.word("dog")["correct"] == 1


def test_target_word_is_never_used_to_fix_what_was_heard(tmp_path):
    # The child really said B: AlfieBot asks, and if the child says B it is
    # marked as B, even though the word is "dog".
    tutor = make_tutor(tmp_path, "dog")
    tutor.start("test")
    tutor.handle("bee oh gee finished", "voice",
                 words=[("bee", 0.4), ("oh", 0.95), ("gee", 0.95), ("finished", 0.9)])
    assert tutor.answer.text == "bog"  # still what was heard
    tutor.handle("the first one", "voice")
    tutor.handle("yes", "voice")
    assert tutor.progress.word("dog")["incorrect"] == 1
    last = tutor.progress.db.query("SELECT answer, clarifications, min_confidence FROM attempts "
                                   "WHERE word = 'dog' ORDER BY id DESC LIMIT 1")[0]
    assert last["answer"] == "bog" and last["clarifications"] == 1 and last["min_confidence"] == 0.4


def test_clarify_answer_that_is_still_unsure_asks_again(tmp_path):
    tutor = make_tutor(tmp_path, "man")
    tutor.start("test")
    tutor.handle("em ay en finished", "voice",
                 words=[("em", 0.3), ("ay", 0.95), ("en", 0.95), ("finished", 0.9)])
    r = tutor.handle("en", "voice", words=[("en", 0.3)])
    assert tutor.stage == "clarify" and "letter 1" in r.text
    tutor.handle("monkey", "voice", words=[("monkey", 0.5)])  # "M for monkey" is clear
    assert tutor.stage == "review" and tutor.answer.text == "man"


def test_something_that_was_not_a_letter_is_asked_about(tmp_path):
    tutor = make_tutor(tmp_path, "cat")
    tutor.start("test")
    tutor.handle("see um banana tee", "voice", words=sure("see banana tee"))
    assert shown(tutor) == "C?T"
    r = tutor.handle("finished", "voice")
    assert "letter 2" in r.text
    tutor.handle("ay", "voice", words=sure("ay"))
    assert tutor.answer.text == "cat"


def test_saying_no_at_the_read_back_lets_the_child_fix_it(tmp_path):
    tutor = make_tutor(tmp_path, "cat")
    tutor.start("test")
    tutor.handle("see ay dee finished", "voice", words=sure("see ay dee finished"))
    r = tutor.handle("no", "voice")
    assert tutor.stage == "spelling" and "delete" in r.text
    tutor.handle("delete", "voice")
    tutor.handle("tee finished", "voice", words=sure("tee finished"))
    tutor.handle("yes", "voice")
    assert tutor.progress.word("cat")["correct"] == 1


def test_when_unsure_setting_marks_clear_answers_straight_away(tmp_path):
    tutor = make_tutor(tmp_path, "cat", "dog", confirm_spoken="when_unsure")
    tutor.start("practice")
    r = tutor.handle("see ay tee finished", "voice", words=sure("see ay tee finished"))
    assert r.celebrate and tutor.progress.word("cat")["correct"] == 1


def test_nato_words_in_questions(tmp_path):
    tutor = make_tutor(tmp_path, "dog", phonetic="nato")
    tutor.start("test")
    r = tutor.handle("dee oh gee finished", "voice",
                     words=[("dee", 0.2), ("oh", 0.9), ("gee", 0.9), ("finished", 0.9)])
    assert "D for delta" in r.text


def test_typed_answers_are_still_marked_straight_away(tmp_path):
    tutor = make_tutor(tmp_path, "cat", "dog")
    tutor.start("practice")
    r = tutor.handle("cat")
    assert r.celebrate and tutor.progress.word("cat")["correct"] == 1


def test_typed_answer_that_looks_like_a_command(tmp_path):
    tutor = make_tutor(tmp_path, "next", "pass")
    tutor.start("practice")
    r = tutor.handle("next")  # the word itself, not "skip"
    assert r.celebrate


def test_stop_during_a_spoken_answer(tmp_path):
    tutor = make_tutor(tmp_path, "cat")
    tutor.start("test")
    tutor.handle("see ay", "voice", words=sure("see ay"))
    r = tutor.handle("stop", "voice")
    assert not tutor.active and r.then == "listen"


@pytest.mark.parametrize("spoken,letters", [
    ("bee ee see ay you ess ee", "because"),
    ("eff are eye ee en dee", "friend"),
    ("pee ee oh pee el ee", "people"),
    ("double you ay ess", "was"),
    ("ess ay eye dee", "said"),
])
def test_common_words(spoken, letters):
    assert heard_letters(spoken) == letters
