import random

import pytest

from tests.learning_helpers import make_tutor

from alfiebot.core.states import Expression
from alfiebot.spelling.tutor import SpellingTutor
from alfiebot.storage.json_store import JsonStore

WEEK = "2026-W44"


@pytest.fixture
def tutor(tmp_path):
    t = make_tutor(tmp_path, random.Random(3))
    t.active_week = WEEK
    return t


def with_words(tutor, *words):
    tutor.lists.add_words(WEEK, list(words))
    return tutor


def test_add_word_by_voice_with_confirmation(tutor):
    r = tutor.start("add", "Add the word because")
    assert r.text == "Because. B-E-C-A-U-S-E. Is that correct?"
    assert tutor.lists.load(WEEK).words == []  # not saved until confirmed
    r = tutor.handle("Yes")
    assert "added because" in r.text or "because is saved" in r.text.lower() or "Because is on" in r.text
    assert tutor.lists.load(WEEK).words == ["because"]


def test_correcting_a_misheard_word(tutor):
    tutor.start("add")
    assert "FREIND" in tutor.handle("add the word freind").text.replace("-", "")
    r = tutor.handle("no")
    assert "letter" in r.text
    r = tutor.handle("eff are eye ee en dee", "voice")
    assert "F-R-I-E-N-D" in r.text
    tutor.handle("yes")
    assert tutor.lists.load(WEEK).words == ["friend"]


def test_add_then_finish_offers_practice(tutor):
    tutor.start("add")
    tutor.handle("people")
    tutor.handle("yes")
    r = tutor.handle("finished")
    assert "1 words" in r.text or "has 1" in r.text or "got 1" in r.text
    assert tutor.mode == "menu" and r.then == "spelling_setup"
    assert tutor.handle("practise").then == "spelling_practice"


def test_no_words_yet(tutor):
    r = tutor.start("test")
    assert "add" in r.text.lower()
    assert tutor.mode == "menu"


def test_learning_mode_steps(tutor):
    with_words(tutor, "because", "friend")
    r = tutor.start("practice")
    # Ask first: the word is said, but its spelling isn't.
    assert "because" in r.text and "B-E-C-A-U-S-E" not in r.text and "spell because" in r.text.lower()
    assert r.then == "spelling_practice"
    assert "be... cause" in tutor.handle("spell it slower").text  # beats, not letters
    assert tutor.handle("repeat that").text == tutor.last_reply.text
    clue = tutor.handle("give me a clue").text
    assert "7 letters" in clue and "be... cause" in clue and "B-E" not in clue
    bigger = tutor.handle("another clue").text
    assert "starts with B" in bigger and "ends with E" in bigger and "B-E-C" not in bigger
    wrong = tutor.handle("b e c o s")
    # Two clues already: the next mistake teaches the word.
    assert "B-E-C-A-U-S-E" in wrong.text and "Elephants" in wrong.text and wrong.then == "spelling_practice"
    right = tutor.handle("because")
    assert right.celebrate and right.mood == Expression.EXCITED
    assert "friend" in right.text  # moves on by itself
    assert tutor.current_word == "friend"


def test_first_mistake_encourages_without_the_spelling(tutor):
    with_words(tutor, "because")
    tutor.start("practice")
    r = tutor.handle("becos")
    assert "start right" in r.text and "B-E-C" not in r.text
    r = tutor.handle("becos")
    assert "7 letters" in r.text and "B-E-C" not in r.text  # second mistake: a clue
    assert tutor.current_word == "because"


def test_i_dont_know_teaches_straight_away(tutor):
    with_words(tutor, "friend", "people")
    tutor.start("practice")
    r = tutor.handle("I don't know")
    assert "F-R-I-E-N-D" in r.text and "Now you try" in r.text
    assert tutor.current_word == "friend"
    assert tutor.handle("friend").celebrate
    # Taught words come back at the end of the session to try again.
    assert tutor.current_word == "people"
    r = tutor.handle("people")
    assert tutor.current_word == "friend" and "again" in r.text
    assert "F-R-I-E-N-D" not in r.text
    r = tutor.handle("friend")
    assert tutor.mode == "after_practice"
    assert tutor.progress.sessions()[-1]["incorrect"] == ["friend"]  # taught, so not right first time
    assert tutor.progress.word("friend")["box"] == 1  # taught: due again tomorrow
    assert tutor.progress.word("friend")["taught"] == 1


def test_learning_next_and_start_again(tutor):
    with_words(tutor, "because", "friend", "people")
    tutor.start("practice")
    tutor.handle("next word")
    assert tutor.current_word == "friend"
    r = tutor.handle("restart")
    assert tutor.current_word == "because" and "first word" in r.text


def test_learning_teaches_after_three_tries_then_moves_on(tutor):
    with_words(tutor, "because", "friend")
    tutor.start("practice")
    replies = [tutor.handle("bekos").text for _ in range(3)]
    assert all("B-E-C" not in r for r in replies[:2])  # no spelling before the teaching step
    assert "B-E-C-A-U-S-E" in replies[2]  # third mistake: taught
    assert tutor.current_word == "because"  # try once more straight away
    r = tutor.handle("bekos")
    assert tutor.current_word == "friend"
    assert "tricky" in r.text.lower() or "soon" in r.text.lower()
    assert tutor.progress.needs_practice("because")
    assert tutor.words[-1] == "because"  # comes back later in the session


def test_test_mode_hides_spelling_and_scores(tutor):
    with_words(tutor, "because", "friend", "people")
    r = tutor.start("test")
    assert tutor.hide_words
    first = tutor.current_word
    assert first in r.text and "-".join(first.upper()) not in r.text  # word said, not spelled
    tutor.handle(first)  # right
    second = tutor.current_word
    r = tutor.handle("wrong")
    assert "-".join(second.upper()) not in r.text  # the spelling isn't given away in a test
    assert second in r.text and "practise" in r.text
    third = tutor.current_word
    r = tutor.handle(third)
    assert "2 out of 3" in r.text
    assert second in r.text  # suggests what to practise again
    assert tutor.mode == "after_test"
    sessions = tutor.progress.sessions()
    assert sessions[-1]["score"] == 2 and sessions[-1]["incorrect"] == [second]
    # Practise the missed word straight away.
    r = tutor.handle("yes please")
    assert tutor.mode == "practice" and tutor.words == [second]


def test_all_correct_test_celebrates_and_finishes(tutor):
    with_words(tutor, "because", "friend")
    tutor.start("test")
    tutor.handle(tutor.current_word)
    r = tutor.handle(tutor.current_word)
    assert r.celebrate and "2" in r.text
    assert not tutor.active and r.then == "listen"


def test_spoken_answer_is_read_back_before_marking(tutor):
    with_words(tutor, "because")
    tutor.start("test")
    assert tutor.handle("bee ee see ay you ess ee", "voice", confidence=0.95) is None
    r = tutor.handle("finished", "voice")
    assert "B-E-C-A-U-S-E" in r.text and "right" in r.text or "meant" in r.text
    assert tutor.progress.word("because")["attempts"] == 0  # nothing marked yet
    r = tutor.handle("no", "voice")
    assert tutor.progress.word("because")["attempts"] == 0
    assert tutor.current_word == "because"  # same word, fix it
    tutor.handle("finished", "voice")
    tutor.handle("yes", "voice")
    assert tutor.progress.word("because")["correct"] == 1


def test_whole_word_spoken_asks_for_letters(tutor):
    with_words(tutor, "because", "friend")
    tutor.start("practice")
    r = tutor.handle("because", "voice")
    assert "letter" in r.text.lower()
    assert tutor.progress.word("because")["attempts"] == 0


def test_test_repeat_word_and_skip(tutor):
    with_words(tutor, "because", "friend")
    tutor.start("test")
    word = tutor.current_word
    assert word in tutor.handle("say it again").text
    r = tutor.handle("I don't know")
    assert "-".join(word.upper()) not in r.text and "later" in r.text
    entry = tutor.progress.word(word)
    assert entry["incorrect"] == 0 and entry["box"] == 1  # skipped, not a mistake; practised again soon


def test_stop_part_way(tutor):
    with_words(tutor, "because", "friend")
    tutor.start("test")
    tutor.handle(tutor.current_word)
    r = tutor.handle("stop")
    assert "1 out of 1" in r.text
    assert not tutor.active and r.then == "listen"


def test_practice_done_offers_test(tutor):
    with_words(tutor, "because")
    tutor.start("practice")
    r = tutor.handle("because")
    assert "test" in r.text
    assert tutor.handle("yes").then == "spelling_test"


def test_replies_vary(tutor):
    with_words(tutor, *"because friend people could would should beautiful".split())
    tutor.start("test")
    texts = set()
    while tutor.mode == "test":
        texts.add(tutor.handle(tutor.current_word).text.split(" Word")[0])
    assert len(texts) > 2
