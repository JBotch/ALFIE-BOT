import pytest

from alfiebot.conversation.intents import match_intent, normalise, split_wake_phrase


@pytest.mark.parametrize("text, rest", [
    ("Hey AlfieBot", ""),
    ("hey alfiebot!", ""),
    ("Hey Alfie Bot, how are you?", "how are you"),
    ("Hi AlfieBot what can you do", "what can you do"),
    ("AlfieBot", ""),
    ("OK Alfiebot tell me a joke", "tell me a joke"),
    ("Hey Alfie", ""),
])
def test_wake_phrase(text, rest):
    assert split_wake_phrase(text) == (True, rest)


@pytest.mark.parametrize("text", ["Alfie", "Alfie is my name", "how are you", "hey there", "I like robots"])
def test_not_a_wake_phrase(text):
    assert split_wake_phrase(text)[0] is False


def test_normalise():
    assert normalise("I’m GOOD!!") == "im good"
    assert normalise("  What's   your name? ") == "whats your name"


@pytest.mark.parametrize("text, intent", [
    ("How are you?", "how_are_you"),
    ("how are you feeling", "how_are_you"),
    ("are you ok", "how_are_you"),
    ("What can you do?", "what_can_you_do"),
    ("Tell me a joke", "joke"),
    ("do you know any jokes", "joke"),
    ("Help me with my spellings.", "spelling_help"),
    ("can we do my spelling homework", "spelling_help"),
    ("What's your name?", "name"),
    ("who made you", "who_made_you"),
    ("how old are you", "age"),
    ("thank you", "thanks"),
    ("say that again", "repeat"),
    ("goodbye", "goodbye"),
    ("go to sleep", "goodbye"),
    ("never mind", "stop"),
    ("hello", "hello"),
    ("I'm good.", "feeling_good"),
    ("I feel great", "feeling_good"),
    ("I'm sad", "feeling_bad"),
    ("I'm not very happy", "feeling_bad"),
    ("What colour is the sky", "fallback"),
    ("banana", "fallback"),
    ("", "fallback"),
])
def test_intents(text, intent):
    assert match_intent(text).intent == intent


def test_feelings_need_context_or_i_am():
    assert match_intent("good").intent == "fallback"
    assert match_intent("good", expecting="feeling").intent == "feeling_good"
    assert match_intent("not bad", expecting="feeling").intent == "feeling_good"
    assert match_intent("not great", expecting="feeling").intent == "feeling_bad"
    assert match_intent("tired", expecting="feeling").intent == "feeling_bad"


def test_question_back_is_not_a_feeling():
    assert match_intent("how are you", expecting="feeling").intent == "how_are_you"


def test_spelling_choices_only_in_context():
    assert match_intent("practise them", expecting="spelling_choice").detail == "practise"
    assert match_intent("I want to practice", expecting="spelling_choice").detail == "practise"
    assert match_intent("take a test", expecting="spelling_choice").detail == "test"
    assert match_intent("add this week's words", expecting="spelling_choice").detail == "add"
    assert match_intent("umm", expecting="spelling_choice").intent == "spelling_unclear"
    assert match_intent("take a test").intent == "fallback"


def test_joke_offer_yes_no():
    assert match_intent("yes please", expecting="joke_offer").intent == "joke_yes"
    assert match_intent("no thanks", expecting="joke_offer").intent == "joke_no"
    assert match_intent("yes").intent == "fallback"
