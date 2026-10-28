"""Phase 4: the privacy gate, routing in every mode, the cloud provider
(against a stand-in server, never the real API), failures, budget and the
Python tools. Synthetic text only."""

import datetime as dt
import logging
import random
import tempfile
import threading
import time

import pytest

from alfiebot.ai.cloud_provider import OpenAIProvider
from alfiebot.ai.mock_provider import MockProvider
from alfiebot.ai.performance import PerformanceTracker
from alfiebot.ai.provider_base import AIRequest, AIResult
from alfiebot.ai.router import Router
from alfiebot.config import load_config
from alfiebot.conversation.engine import ConversationEngine
from alfiebot.core.brain import Brain, PendingReply
from alfiebot.core.events import UserInput
from alfiebot.core.tools import answer
from alfiebot.spelling.tutor import SpellingTutor
from alfiebot.storage.json_store import JsonStore
from tests.learning_helpers import make_tutor
from tests.fake_openai import FakeOpenAI

KEY = "sk-test-not-a-real-key-123"
PUBLIC = "why is the sky blue"


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", KEY)


def openai(fake, **kw):
    kw.setdefault("backoff_s", 0.01)
    return OpenAIProvider("gpt-test-mini", fake.url, **kw)


def router(mode="automatic", enabled=True, review=True, adult=False, cloud=None, local=None, **kw):
    r = Router(local or MockProvider("mock-local", "local", rng=random.Random(0)),
               cloud or MockProvider("mock-cloud", "cloud", "mock-cloud-1", rng=random.Random(0)),
               mode=mode, cloud_enabled=enabled, review_complete=review, **kw)
    r.adult_test_session = adult
    return r


def make_brain(local, cloud, mode="automatic", enabled=True, review=True, timeout=3.0):
    config = load_config()
    config["ai"].update(mode=mode, timeout_s=timeout)
    config["cloud"].update(enabled=enabled, child_data_review_complete=review)
    tutor = make_tutor(rng=random.Random(0))
    return Brain(config, ConversationEngine("AlfieBot", rng=random.Random(0)), tutor, local, cloud,
                 performance=PerformanceTracker("Test PC"))


def ask(brain, text, source="typed", seconds=5.0):
    reply = brain.handle(UserInput(text, source))
    end = time.monotonic() + seconds
    while isinstance(reply, PendingReply):
        assert time.monotonic() < end, "no reply"
        time.sleep(0.01)
        reply = brain.poll(reply) or reply
    return reply


# ---- the privacy gate ------------------------------------------------------------------
GATE = [
    # enabled, review, adult, source, privacy, allowed
    (False, True, True, "typed", "public", False),       # parent switch off: never
    (True, False, False, "voice", "public", False),      # review not done: a child's words stay here
    (True, False, False, "typed", "public", False),
    (True, False, True, "typed", "public", True),        # adult test session, typed: allowed
    (True, False, True, "typed", "personal", False),     # personal: never, even for an adult
    (True, False, True, "voice", "public", False),       # adult session never covers speech
    (True, True, False, "voice", "public", True),        # review done + general question
    (True, True, False, "voice", "personal", False),     # personal: never
    (True, True, False, "typed", "unclassified", False),
    (True, True, True, "typed", "sensitive", False),     # sensitive: never, even for an adult
]


@pytest.mark.parametrize("enabled,review,adult,source,privacy,allowed", GATE)
def test_privacy_gate(enabled, review, adult, source, privacy, allowed):
    r = router(enabled=enabled, review=review, adult=adult)
    assert (r.cloud_blocked_reason(privacy, source) is None) == allowed


@pytest.mark.parametrize("mode", ["local_only", "cloud_only", "automatic"])
@pytest.mark.parametrize("privacy", ["personal", "sensitive", "unclassified"])
@pytest.mark.parametrize("adult,source", [(False, "voice"), (True, "typed")])
def test_personal_data_never_goes_to_the_cloud_in_any_mode(mode, privacy, adult, source):
    r = router(mode=mode, adult=adult)
    decision = r.choose("why do I have freckles on my nose and arms and legs", privacy, source)
    assert not decision.uses_cloud


def test_internet_loss_keeps_everything_local():
    r = router(mode="cloud_only")
    r.connectivity.simulate_offline = True
    decision = r.choose(PUBLIC, "public", "voice")
    assert [p.kind for p in decision.providers] == ["local"]
    assert any("internet is offline" in reason for reason in decision.reasons)


def test_no_api_key_keeps_the_cloud_out(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    r = router(mode="cloud_only", cloud=OpenAIProvider())
    decision = r.choose(PUBLIC, "public", "voice")
    assert not decision.uses_cloud
    assert any("OPENAI_API_KEY" in reason for reason in decision.reasons)


@pytest.mark.parametrize("mode,text,kinds", [
    ("local_only", PUBLIC, ["local"]),
    ("cloud_only", "hello there", ["cloud", "local"]),
    ("automatic", "I like trains", ["local", "cloud"]),          # everyday chat: local first
    ("automatic", PUBLIC, ["cloud", "local"]),                   # complex question: cloud first
    ("automatic", "explain how rainbows are made", ["cloud", "local"]),
])
def test_modes_when_the_gate_is_open(mode, text, kinds):
    decision = router(mode=mode).choose(text, "public", "voice")
    assert [p.kind for p in decision.providers] == kinds


def test_daily_budget_stops_the_cloud():
    r = router(mode="cloud_only", daily_budget=0.10, spend_today=lambda: 0.11)
    decision = r.choose(PUBLIC, "public", "voice")
    assert not decision.uses_cloud and any("budget" in reason for reason in decision.reasons)


def test_repeated_failures_rest_a_provider_then_it_comes_back():
    now = [0.0]
    fallback = MockProvider("mock-local", "local", "mock-1")
    local = MockProvider("ollama", "local", "qwen")
    r = router(mode="local_only", local=local, local_fallback=fallback, unhealthy_after=3, cooldown_s=60,
               clock=lambda: now[0])
    for _ in range(3):
        r.report(local, False)
    decision = r.choose("hello", "public")
    assert decision.providers == [fallback] and any("resting" in reason for reason in decision.reasons)
    now[0] += 61
    assert r.choose("hello", "public").providers == [local]


def test_success_resets_the_failure_count():
    r = router()
    for ok in (False, False, True, False, False):
        r.report(r.cloud, ok)
    assert not r.resting(r.cloud)


# ---- the brain with the router -----------------------------------------------------------
def test_cloud_failure_falls_back_to_local(key):
    with FakeOpenAI() as fake:
        fake.statuses = [500, 500, 500]
        brain = make_brain(MockProvider("mock-local", "local", rng=random.Random(0)), openai(fake))
        reply = ask(brain, PUBLIC, "voice")
        assert reply.intent == "ai:mock-local"
        assert [r.provider for r in brain.last.results] == ["openai", "mock-local"]
        assert len(fake.requests) == 3  # first try + 2 retries


def test_a_childs_personal_words_never_reach_the_cloud_even_when_local_fails(key):
    with FakeOpenAI() as fake:
        local = MockProvider("mock-local", "local", rng=random.Random(0))
        local.failure = "error"
        brain = make_brain(local, openai(fake), mode="cloud_only")
        reply = ask(brain, "my friend Sam and I built a den", "voice")
        assert reply.intent == "fallback" and fake.requests == []


def test_slow_local_never_sends_to_the_cloud_without_permission(key):
    with FakeOpenAI() as fake:
        local = MockProvider("mock-local", "local", rng=random.Random(0))
        local.failure = "slow"
        brain = make_brain(local, openai(fake), mode="automatic", review=False, timeout=0.5)
        reply = ask(brain, PUBLIC, "voice")
        assert reply.intent == "fallback" and fake.requests == []


def test_slow_local_answers_ask_for_shorter_replies():
    local = MockProvider("mock-local", "local", rng=random.Random(0))
    brain = make_brain(local, None, mode="local_only")
    for _ in range(5):
        brain.performance.record(AIResult("{}", "mock-local", "mock-1", latency_s=9.0))
    ask(brain, "I like trains")
    assert any("short answer" in reason for reason in brain.last.decision.reasons)


def test_adult_test_session_uses_the_cloud_for_typed_text_only(key):
    with FakeOpenAI() as fake:
        brain = make_brain(MockProvider("mock-local", "local", rng=random.Random(0)), openai(fake),
                           mode="cloud_only", review=False)
        brain.router.adult_test_session = True
        assert ask(brain, PUBLIC, "typed").intent == "ai:openai"
        assert ask(brain, PUBLIC, "voice").intent == "ai:mock-local"
        assert len(fake.requests) == 1


def test_cloud_cost_counts_towards_the_budget(key):
    with FakeOpenAI() as fake:
        cloud = openai(fake, price_in=1.0, price_out=10.0)
        brain = make_brain(MockProvider("mock-local", "local", rng=random.Random(0)), cloud, mode="cloud_only")
        brain.router.daily_budget = 0.003
        ask(brain, PUBLIC, "voice")
        assert brain.performance.spend_today() == pytest.approx(0.002)  # 1000 * 1/1e6 + 100 * 10/1e6
        ask(brain, PUBLIC, "voice")
        ask(brain, PUBLIC, "voice")
        assert len(fake.requests) == 2  # the third request found the budget spent


# ---- the cloud provider ------------------------------------------------------------------
def test_openai_request_shape_and_usage(key):
    with FakeOpenAI() as fake:
        result = openai(fake).generate(AIRequest([{"role": "user", "content": "hi"}], system="Be AlfieBot",
                                                 max_tokens=90))
        assert result.ok and '"speech"' in result.text
        assert (result.prompt_tokens, result.completion_tokens) == (1000, 100)
        assert result.cost_estimate == pytest.approx((1000 * 0.15 + 100 * 0.60) / 1e6)
        headers, body = fake.requests[-1]
        assert headers["Authorization"] == f"Bearer {KEY}"
        assert body["messages"][0] == {"role": "system", "content": "Be AlfieBot"}
        assert body["max_completion_tokens"] == 90
        fmt = body["response_format"]["json_schema"]
        assert fmt["strict"] is True and fmt["schema"]["additionalProperties"] is False


def test_openai_retries_rate_limits_then_succeeds(key):
    with FakeOpenAI() as fake:
        fake.statuses = [429, 503]
        result = openai(fake).generate(AIRequest([{"role": "user", "content": "hi"}]))
        assert result.ok and len(fake.requests) == 3


def test_openai_does_not_retry_a_bad_request(key):
    with FakeOpenAI() as fake:
        fake.statuses = [400]
        result = openai(fake).generate(AIRequest([{"role": "user", "content": "hi"}]))
        assert not result.ok and "HTTP 400" in result.error and len(fake.requests) == 1


def test_openai_timeout(key):
    with FakeOpenAI() as fake:
        fake.delay_s = 1.0
        result = openai(fake, timeout_s=0.2, max_retries=0).generate(AIRequest([{"role": "user", "content": "hi"}]))
        assert not result.ok and result.timed_out


def test_openai_refusal_is_a_failure(key):
    with FakeOpenAI() as fake:
        fake.refuse = True
        result = openai(fake).generate(AIRequest([{"role": "user", "content": "hi"}]))
        assert not result.ok and "refused" in result.error


def test_openai_cancel_stops_retrying(key):
    with FakeOpenAI() as fake:
        fake.statuses = [500] * 5
        request = AIRequest([{"role": "user", "content": "hi"}])
        threading.Timer(0.05, request.cancel.set).start()
        result = openai(fake, backoff_s=1.0, max_retries=4).generate(request)
        assert not result.ok and len(fake.requests) < 5


def test_api_key_is_never_logged_or_saved(key, caplog, tmp_path):
    from alfiebot.config import save_setting

    caplog.set_level(logging.DEBUG)
    with FakeOpenAI() as fake:
        fake.statuses = [401]
        openai(fake).generate(AIRequest([{"role": "user", "content": "hi"}]))
    config = load_config()
    config["config_path"] = str(tmp_path / "alfiebot.json")
    save_setting(config, "cloud", "enabled", True)
    assert KEY not in caplog.text
    assert KEY not in (tmp_path / "alfiebot.json").read_text(encoding="utf-8")


def test_cloud_is_off_and_review_not_done_by_default():
    config = load_config()
    assert config["cloud"]["enabled"] is False and config["cloud"]["child_data_review_complete"] is False
    assert config["cloud"]["provider"] == "mock" and "api_key" not in config["cloud"]


# ---- Python tools ---------------------------------------------------------------------------
NOW = lambda: dt.datetime(2026, 10, 28, 15, 0)  # noqa: E731


@pytest.mark.parametrize("text,expected", [
    ("What's 7 times 8?", "7 times 8 is 56!"),
    ("what is seven times eight", "7 times 8 is 56!"),
    ("twenty-one plus four", "21 plus 4 is 25!"),
    ("10 divided by 3", "10 divided by 3 is 3 remainder 1."),
    ("what is 5 minus 9", "5 minus 9 is minus 4!"),
    ("what time is it", "it's 3 o'clock in the afternoon."),
    ("What day is it today?", "Today is Wednesday the 28th of October."),
])
def test_tools(text, expected):
    assert expected in answer(text, NOW).text


@pytest.mark.parametrize("text", ["what is a volcano", "I have 2 cats", "seven dwarves", "what is up"])
def test_not_tools(text):
    assert answer(text, NOW) is None


def test_dividing_by_zero_is_answered_kindly():
    assert "robots can't solve" in answer("9 divided by 0", NOW).text


def test_maths_never_reaches_an_ai():
    local = MockProvider("mock-local", "local", rng=random.Random(0))
    brain = make_brain(local, None, mode="local_only")
    reply = ask(brain, "what is 6 times 7")
    assert reply.text.startswith("6 times 7 is 42") and reply.intent == "tool:maths" and local.calls == 0
