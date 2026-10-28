"""The brain, AI providers, router and output validation (mock AI only)."""

import json
import random
import tempfile
import time

import pytest

from alfiebot.ai.connectivity import Connectivity
from alfiebot.ai.mock_provider import MockProvider
from alfiebot.ai.performance import PerformanceTracker
from alfiebot.ai.provider_base import AIRequest
from alfiebot.ai.router import Router
from alfiebot.config import load_config
from alfiebot.conversation.engine import ConversationEngine
from alfiebot.core.actions import InvalidResponse, parse_response, to_reply
from alfiebot.core.brain import Brain, PendingReply
from alfiebot.core.events import UserInput
from alfiebot.core.robot import AlfieBot
from alfiebot.core.states import Expression, RobotState
from alfiebot.hardware.simulator import create_simulator_platform
from alfiebot.spelling.lists import SpellingLists, week_id
from alfiebot.spelling.progress import ProgressTracker
from alfiebot.spelling.tutor import SpellingTutor
from alfiebot.storage.json_store import JsonStore

UNKNOWN = "what is the capital of peru"


def make_brain(mode="local_only", cloud_enabled=False, timeout=8.0):
    config = load_config()
    config["ai"].update(mode=mode, timeout_s=timeout)
    config["cloud"]["enabled"] = cloud_enabled
    store = JsonStore(tempfile.mkdtemp(prefix="alfiebot-test-"))
    tutor = SpellingTutor(SpellingLists(store), ProgressTracker(store), rng=random.Random(0))
    local = MockProvider("mock-local", "local", rng=random.Random(0))
    cloud = MockProvider("mock-cloud", "cloud", "mock-cloud-1", rng=random.Random(0))
    brain = Brain(config, ConversationEngine("AlfieBot", rng=random.Random(0)), tutor, local, cloud)
    return brain


def wait_for(brain, pending, seconds=5.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        reply = brain.poll(pending)
        if reply is not None:
            return reply
        time.sleep(0.01)
    raise AssertionError("no reply")


# ---- output validation ---------------------------------------------------------
def test_valid_json_response():
    response, notes = parse_response('{"speech": "Brilliant! Let\'s try another!", '
                                     '"expression": "happy", "action": null}')
    assert response.speech == "Brilliant! Let's try another!"
    assert response.expression == Expression.HAPPY
    assert response.action is None
    assert notes == []


def test_unknown_expression_becomes_happy():
    response, notes = parse_response({"speech": "Hi!", "expression": "dancing", "action": None})
    assert response.expression == Expression.HAPPY
    assert notes


@pytest.mark.parametrize("action", ["rm -rf /", "set_motor_power", "install_package", "move_forward"])
def test_unauthorised_actions_are_dropped(action):
    response, notes = parse_response({"speech": "OK!", "expression": "happy", "action": action})
    assert response.action is None
    assert any("not allowed" in n for n in notes)


def test_non_string_action_is_dropped():
    response, _ = parse_response({"speech": "OK!", "action": {"motor": 100}})
    assert response.action is None


def test_allowed_action_maps_to_fixed_behaviour():
    response, _ = parse_response({"speech": "Woohoo!", "expression": "happy", "action": "celebrate"})
    reply = to_reply(response)
    assert reply.celebrate and reply.mood == Expression.EXCITED
    response, _ = parse_response({"speech": "Night night!", "expression": "sleeping", "action": "sleep"})
    assert to_reply(response).then == "sleep"


@pytest.mark.parametrize("raw", ['{"speech": , "expression"', '{"expression": "happy"}',
                                 '{"speech": "   "}', '[1, 2]'])
def test_invalid_output_is_rejected(raw):
    with pytest.raises(InvalidResponse):
        parse_response(raw)


def test_plain_text_and_thinking_are_cleaned():
    response, notes = parse_response("<think>hmm let me think</think>**Hello** there!")
    assert response.speech == "Hello there!"
    assert "plain text instead of JSON" in notes


def test_long_speech_is_trimmed():
    response, _ = parse_response({"speech": "This is a sentence. " * 40})
    assert len(response.speech) <= 300
    assert response.speech.endswith(".")


# ---- router ------------------------------------------------------------------------
def make_router(**kwargs):
    return Router(MockProvider("mock-local", "local"), MockProvider("mock-cloud", "cloud"), Connectivity(),
                  **kwargs)


def names(decision):
    return [p.name for p in decision.providers]


def test_local_only_never_uses_cloud():
    router = make_router(mode="local_only", cloud_enabled=True)
    router.adult_test_session = True
    assert names(router.choose("why is the sky blue")) == ["mock-local"]


def test_cloud_is_off_by_default():
    router = make_router(mode="cloud_only")
    decision = router.choose("hello")
    assert names(decision) == ["mock-local"]
    assert any("switched off" in r for r in decision.reasons)


def test_child_words_never_reach_cloud_even_when_enabled():
    for mode in ("cloud_only", "automatic"):
        router = make_router(mode=mode, cloud_enabled=True)
        assert "mock-cloud" not in names(router.choose("why is the sky blue"))
        assert "mock-cloud" not in names(router.choose("my name is Sam and I live at 4 Oak Road",
                                                       privacy="personal"))


def test_adult_test_session_can_use_cloud():
    router = make_router(mode="cloud_only", cloud_enabled=True)
    router.adult_test_session = True
    assert names(router.choose("hello", "public")) == ["mock-cloud", "mock-local"]


def test_personal_data_blocked_even_in_adult_session_without_override():
    router = make_router(mode="cloud_only", cloud_enabled=True)
    assert router.cloud_blocked_reason("personal") is not None


def test_automatic_routes_complex_questions_to_cloud_only_when_allowed():
    router = make_router(mode="automatic", cloud_enabled=True)
    router.adult_test_session = True
    assert names(router.choose("why do cats purr", "public")) == ["mock-cloud", "mock-local"]
    assert names(router.choose("I like cats", "public")) == ["mock-local", "mock-cloud"]


def test_internet_failure_keeps_local():
    router = make_router(mode="cloud_only", cloud_enabled=True)
    router.adult_test_session = True
    router.connectivity.simulate_offline = True
    decision = router.choose("hello", "public")
    assert names(decision) == ["mock-local"]
    assert any("offline" in r for r in decision.reasons)


# ---- brain -------------------------------------------------------------------------
def test_scripted_intents_stay_scripted():
    brain = make_brain()
    reply = brain.handle(UserInput("tell me a joke"))
    assert reply.intent == "joke"
    assert brain.local.calls == 0


def test_unknown_text_goes_to_local_ai():
    brain = make_brain()
    reply = brain.handle(UserInput(UNKNOWN))
    assert reply.intent == "ai:mock-local"
    assert brain.last.used == "ai"
    assert brain.performance.summaries()[0].requests == 1


def test_ai_disabled_uses_scripted_fallback():
    brain = make_brain()
    brain.ai_enabled = False
    assert brain.handle(UserInput(UNKNOWN)).intent == "fallback"


@pytest.mark.parametrize("failure", ["error", "invalid"])
def test_local_failure_falls_back_to_scripted(failure):
    brain = make_brain()
    brain.local.failure = failure
    result = brain.handle(UserInput(UNKNOWN))
    reply = wait_for(brain, result) if isinstance(result, PendingReply) else result
    assert reply.intent == "fallback"
    assert brain.last.used == "fallback"
    assert brain.performance.summaries()[0].errors == 1


def test_provider_timeout_is_recorded():
    brain = make_brain()
    brain.local.failure = "timeout"
    pending = brain.handle(UserInput(UNKNOWN))
    assert isinstance(pending, PendingReply)
    assert wait_for(brain, pending).intent == "fallback"
    assert brain.performance.summaries()[0].timeouts == 1


def test_slow_ai_gives_up_after_timeout():
    brain = make_brain(timeout=0.2)
    brain.local.failure = "slow"
    pending = brain.handle(UserInput(UNKNOWN))
    assert isinstance(pending, PendingReply)
    start = time.monotonic()
    reply = wait_for(brain, pending)
    assert time.monotonic() - start < 2.0
    assert reply.intent == "fallback"
    assert pending.request.cancel.is_set()  # the provider is told to stop
    assert brain.performance.summaries()[0].timeouts == 1
    brain.close()


def test_slow_local_never_goes_to_cloud_without_permission():
    brain = make_brain(mode="automatic", timeout=0.2)
    brain.local.failure = "slow"
    wait_for(brain, brain.handle(UserInput(UNKNOWN)))
    assert brain.cloud.calls == 0
    brain.close()


def test_cloud_failure_falls_back_to_local():
    brain = make_brain(mode="cloud_only", cloud_enabled=True)
    brain.router.adult_test_session = True
    brain.cloud.failure = "error"
    result = brain.handle(UserInput(UNKNOWN))
    reply = wait_for(brain, result) if isinstance(result, PendingReply) else result
    assert reply.intent == "ai:mock-local"
    assert [r.provider for r in brain.last.results] == ["mock-cloud", "mock-local"]


def test_background_reply_arrives():
    brain = make_brain()
    brain.local.delay_s = 0.05
    pending = brain.handle(UserInput(UNKNOWN))
    assert isinstance(pending, PendingReply)
    assert wait_for(brain, pending).intent == "ai:mock-local"


def test_say_that_again_repeats_ai_reply():
    brain = make_brain()
    first = brain.handle(UserInput(UNKNOWN))
    again = brain.handle(UserInput("say that again"))
    assert again.text == first.text


def test_spelling_marked_by_python_whatever_the_ai_does():
    brain = make_brain()
    brain.tutor.lists.add_words(week_id(), ["cat"])
    brain.handle(UserInput("help me with my spellings test"))
    assert brain.tutor.mode == "test"
    brain.local.failure = "error"  # switching providers mid-activity changes nothing
    brain.router.mode = "automatic"
    brain.handle(UserInput("cat"))
    assert brain.tutor.progress.word("cat")["correct"] == 1
    assert brain.local.calls == 0


def test_mock_provider_output_is_valid_json():
    provider = MockProvider(rng=random.Random(1))
    for text in ("why is grass green", "I like dinosaurs", "blah"):
        result = provider.generate(AIRequest([{"role": "user", "content": text}]))
        data = json.loads(result.text)
        assert set(data) == {"speech", "expression", "action"}
        parse_response(result.text)


def test_performance_summary_labels_machine():
    tracker = PerformanceTracker(machine="Test laptop")
    provider = MockProvider()
    tracker.record(provider.generate(AIRequest([{"role": "user", "content": "hi"}])))
    summary = tracker.summaries()[0]
    assert summary.machine == "Test laptop"
    assert summary.requests == 1 and summary.errors == 0
    tracker.reset()
    assert tracker.summaries() == []


# ---- robot integration ---------------------------------------------------------------
def make_robot():
    config = load_config()
    config["data_dir"] = tempfile.mkdtemp(prefix="alfiebot-test-")
    config["ai"]["local_provider"] = "mock"  # never a real Ollama in tests
    robot = AlfieBot(config, create_simulator_platform(config, speech=False),
                     ConversationEngine("AlfieBot", rng=random.Random(0)))
    robot.start()
    robot.handle_text("Hey AlfieBot")
    run_until(robot, lambda: robot.state == RobotState.LISTENING)
    return robot


def run_until(robot, done, seconds=10.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        robot.update(1 / 30)
        if done():
            return
        time.sleep(0.001)
    raise AssertionError(f"timed out in state {robot.state}")


def test_robot_thinks_while_ai_works_then_speaks():
    robot = make_robot()
    robot.brain.local.delay_s = 0.1
    robot.handle_text(UNKNOWN)
    assert robot.state == RobotState.THINKING
    robot.handle_text("hello?")  # held until AlfieBot has answered
    run_until(robot, lambda: robot.state == RobotState.SPEAKING)
    assert robot.transcript.entries[-1].speaker == "robot"
    run_until(robot, lambda: robot.state == RobotState.SPEAKING
              and len([e for e in robot.transcript.entries if e.speaker == "user"]) == 3)
    robot.close()


def test_robot_falls_back_when_ai_hangs():
    robot = make_robot()
    robot.brain.timeout_s = 0.2
    robot.brain.local.failure = "slow"
    robot.handle_text(UNKNOWN)
    run_until(robot, lambda: robot.state == RobotState.SPEAKING)
    assert robot.expression == Expression.CONFUSED  # the scripted "didn't understand" reply
    robot.close()


def test_stopping_cancels_ai_request():
    robot = make_robot()
    robot.brain.local.failure = "slow"
    robot.handle_text(UNKNOWN)
    pending = robot._pending
    robot.stop()
    assert robot._pending is None and pending.request.cancel.is_set()
    robot.close()


def test_voice_output_off_still_talks_on_screen():
    robot = make_robot()
    robot.set_voice_output(False)
    robot.handle_text("tell me a joke")
    run_until(robot, lambda: robot.state == RobotState.SPEAKING)
    assert robot.tts is robot._silent_tts
    assert robot._silent_tts.spoken
    run_until(robot, lambda: robot.state == RobotState.LISTENING)


def test_robot_face_never_shows_spelling_letters():
    import pygame

    from alfiebot.ui.face_view import FaceView

    pygame.init()
    robot = make_robot()
    robot.spelling_lists.add_words(week_id(), ["cat"])
    robot.start_spelling("test")
    run_until(robot, lambda: robot.state == RobotState.SPELLING_TEST)
    view = FaceView(robot, robot.config)
    blank = pygame.Surface((320, 180))
    view.draw(blank)
    robot.handle_text("see ay", "voice", 0.95, [("see", 0.95), ("ay", 0.95)])
    assert robot.spelling_letters()[0]  # the developer panel can see them...
    shown = pygame.Surface((320, 180))
    view.draw(shown)
    # ...but the face drawing is identical with or without letters spelled.
    assert pygame.image.tostring(blank, "RGB") == pygame.image.tostring(shown, "RGB")
    assert not hasattr(view, "draw_letters")
