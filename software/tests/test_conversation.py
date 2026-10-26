import random

from alfiebot.conversation.engine import ConversationEngine, load_responses
from alfiebot.core.states import Expression


def engine(seed=1):
    return ConversationEngine("AlfieBot", rng=random.Random(seed))


def test_brief_example_replies_are_available():
    r = load_responses()
    assert "Hey! How are you today?" in r["wake"]["replies"]
    assert "That's brilliant! What shall we do today?" in r["feeling_good"]["replies"]
    assert "I'm feeling fantastic! My circuits are ready for an adventure!" in r["how_are_you"]["replies"]
    assert "I can chat, tell jokes and help you practise your spellings!" in r["what_can_you_do"]["replies"]
    assert ("Of course! Would you like to add this week's spellings, practise them or take a test?"
            in r["spelling_help"]["replies"])


def test_every_intent_has_several_replies():
    r = load_responses()
    single_ok = {"nothing_to_repeat", "error", "repeat", "joke_yes"}
    for intent, spec in r.items():
        if intent in single_ok:
            continue
        assert len(spec["replies"]) >= 2, intent
        Expression(spec["mood"])


def test_example_conversation():
    e = engine()
    greet = e.greet()
    assert "how are you today" in greet.text.lower()
    assert e.expecting == "feeling"
    good = e.respond("I'm good.")
    assert good.intent == "feeling_good" and good.mood == Expression.HAPPY
    assert e.respond("How are you?").intent == "how_are_you"
    can = e.respond("What can you do?")
    assert "joke" in can.text.lower() and "spelling" in can.text.lower()


def test_replies_vary_and_never_repeat_back_to_back():
    e = engine(3)
    texts = [e.respond("tell me a joke").text for _ in range(20)]
    assert len(set(texts)) > 3
    assert all(a != b for a, b in zip(texts, texts[1:]))


def test_fallback_is_clear_and_confused():
    reply = engine().respond("fly me to the moon")
    assert reply.intent == "fallback"
    assert reply.mood == Expression.CONFUSED
    assert "joke" in reply.text.lower() or "spelling" in reply.text.lower()


def test_spelling_help_flow():
    e = engine()
    r = e.respond("Help me with my spellings")
    assert r.then == "spelling_setup"
    assert e.expecting == "spelling_choice"
    r = e.respond("practise them")
    assert r.intent == "spelling_choice" and r.detail == "practise"
    assert "next update" in r.text  # honest: the tutor arrives in Stage 3


def test_feeling_bad_offers_joke():
    e = engine()
    e.greet()
    r = e.respond("I'm sad")
    assert r.intent == "feeling_bad"
    assert "grown-up" in r.text or "joke" in r.text
    assert e.respond("yes").intent == "joke_yes"


def test_repeat_says_the_last_thing_again():
    e = engine()
    assert e.respond("say that again").intent == "nothing_to_repeat"
    first = e.respond("what can you do")
    again = e.respond("say that again")
    assert again.text == first.text


def test_goodbye_goes_to_sleep_and_stop_goes_idle():
    e = engine()
    assert e.respond("bye").then == "sleep"
    assert e.respond("never mind").then == "idle"


def test_name_placeholder_filled():
    assert "AlfieBot" in engine().respond("what's your name").text
