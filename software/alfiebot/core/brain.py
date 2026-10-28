"""The brain: decides who answers what Alfie says.

    1. A running spelling activity -> the spelling tutor (Python marks every
       answer; AI never does).
    2. Anything the scripted conversation engine recognises (greetings,
       jokes, "help me with my spellings"...) -> its hand-written reply.
    2. Worrying and guarded topics (core/safety.py) -> a fixed, kind reply
       (pointing to a grown-up where it matters). No model sees them.
    3. Simple maths, the time and the date (core/tools.py) -> Python's exact
       answer.
    4. Anything the scripted conversation engine recognises (greetings,
       jokes, "help me with my spellings"...) -> its hand-written reply.
    5. Everything else -> the router picks an AI provider. The provider runs
       on a worker thread so the face keeps animating; the robot polls for
       the answer each frame. The prompt is built from the personality
       (core/personality.py) and the last few turns (core/memory.py), with
       personal details masked. The output is validated (core/actions.py),
       checked against the personality's rules and the output safety rules
       before it is used.
    6. If the AI is switched off, unavailable, too slow, fails or sends back
       something unusable -> the scripted fallback reply.

Requests are classified (public, personal, sensitive) and the router's
privacy gate (ai/router.py) decides whether the cloud may see them. By
default it may not: the cloud is off and the child-data review isn't done.
"""

import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from typing import List, Optional, Tuple, Union

from alfiebot.ai.cloud_provider import DEFAULT_MODEL as DEFAULT_CLOUD_MODEL, OpenAIProvider
from alfiebot.ai.connectivity import Connectivity
from alfiebot.ai.local_provider import DEFAULT_URL, OllamaProvider
from alfiebot.ai.mock_provider import MockProvider
from alfiebot.ai.performance import PerformanceTracker
from alfiebot.ai.provider_base import AIProvider, AIRequest, AIResult
from alfiebot.ai.router import Router, RoutingDecision
from alfiebot.conversation.engine import ConversationEngine, Reply
from alfiebot.conversation.intents import normalise
from alfiebot.core.actions import InvalidResponse, parse_response, to_reply
from alfiebot.core.events import BrainResponse, UserInput
from alfiebot.core.memory import ConversationMemory
from alfiebot.core.personality import Personality, last_question
from alfiebot.core.safety import check_input, check_output
from alfiebot.core.states import Expression
from alfiebot.core.tools import answer as tool_answer
from alfiebot.face.controller import AI_EXPRESSIONS
from alfiebot.spelling.tutor import CHOICES, SpellingTutor

log = logging.getLogger(__name__)

LOCAL_PROVIDERS = {"mock": "Pretend AI", "ollama": "Ollama"}
CLOUD_PROVIDERS = {"mock": "Pretend cloud", "openai": "OpenAI"}
SHORT_HINT = "\nThe local AI is running slowly: keep your answer to one short sentence."
DEFAULT_OLLAMA_MODEL = "qwen3:1.7b"


@dataclass
class PendingReply:
    """An AI answer being worked on in the background."""

    future: Future
    request: AIRequest
    decision: RoutingDecision
    fallback: Reply
    deadline: float
    started: float = field(default_factory=time.monotonic)
    last_question: Optional[str] = None


@dataclass
class Exchange:
    """The last AI exchange, for the developer panel."""

    text: str
    decision: RoutingDecision
    results: List[AIResult] = field(default_factory=list)
    used: str = ""  # "ai", "fallback", "safety" or "pending"
    notes: List[str] = field(default_factory=list)
    privacy: str = ""
    masked: List[str] = field(default_factory=list)


def create_providers(ai: dict, cloud_cfg: dict = None):
    """(local providers by name, cloud providers by name)."""
    cloud_cfg = cloud_cfg or {}
    delay = float(ai.get("mock_delay_s", 0.0))
    mock = MockProvider("mock-local", "local", "mock-1", delay_s=delay)
    model = ai.get("local_model") or DEFAULT_OLLAMA_MODEL
    if model.startswith("mock"):
        mock.model, model = model, DEFAULT_OLLAMA_MODEL
    ollama = OllamaProvider(model, ai.get("ollama_url") or DEFAULT_URL)
    pretend_cloud = MockProvider("mock-cloud", "cloud", "mock-cloud-1", delay_s=delay)
    openai = OpenAIProvider(cloud_cfg.get("model") or DEFAULT_CLOUD_MODEL,
                            cloud_cfg.get("url") or "https://api.openai.com/v1",
                            key_env=cloud_cfg.get("api_key_env") or "OPENAI_API_KEY",
                            timeout_s=float(cloud_cfg.get("timeout_s", 10.0)),
                            max_retries=int(cloud_cfg.get("max_retries", 2)),
                            price_in=float(cloud_cfg.get("price_input_per_million", 0.15)),
                            price_out=float(cloud_cfg.get("price_output_per_million", 0.60)))
    return {"mock": mock, "ollama": ollama}, {"mock": pretend_cloud, "openai": openai}


def check_reply(personality: Personality, text: str, asked: Optional[str] = None) -> Tuple[BrainResponse, List[str]]:
    """The validated, personality-checked reply in an AI's output, or
    InvalidResponse saying why it can't be used."""
    response, notes = parse_response(text)
    problem = check_output(response.speech)
    if problem:
        raise InvalidResponse(f"unsafe reply ({problem})")
    speech, more = personality.check(response.speech, asked)
    notes += more
    if speech is None:
        raise InvalidResponse("; ".join(more))
    problem = check_output(speech)
    if problem:
        raise InvalidResponse(f"unsafe reply ({problem})")
    return replace(response, speech=speech), notes


class Brain:
    def __init__(self, config: dict, conversation: ConversationEngine, tutor: SpellingTutor,
                 local: AIProvider = None, cloud: AIProvider = None, connectivity: Connectivity = None,
                 performance: PerformanceTracker = None, personality: Personality = None, db=None):
        ai = config.get("ai", {})
        cloud_cfg = config.get("cloud", {})
        router_cfg = config.get("router", {})
        self.conversation = conversation
        self.tutor = tutor
        self.ai_enabled = bool(ai.get("enabled", True))
        self.timeout_s = float(ai.get("timeout_s", 8.0))
        self.max_tokens = int(ai.get("max_tokens", 160))
        self.slow_local_s = float(router_cfg.get("slow_local_s", 6.0))
        self.local_providers, self.cloud_providers = {}, {}
        if local is None and cloud is None:
            self.local_providers, self.cloud_providers = create_providers(ai, cloud_cfg)
            name = ai.get("local_provider", "mock")
            local = self.local_providers.get(name) or self.local_providers["mock"]
            cloud = self.cloud_providers.get(cloud_cfg.get("provider", "mock")) or self.cloud_providers["mock"]
        self.performance = performance or PerformanceTracker(db=db)
        self.connectivity = connectivity or Connectivity()
        self.router = Router(local, cloud, self.connectivity, ai.get("mode", "local_only"),
                             cloud_enabled=bool(cloud_cfg.get("enabled", ai.get("cloud_enabled", False))),
                             local_fallback=self.local_providers.get("mock"),
                             review_complete=bool(cloud_cfg.get("child_data_review_complete", False)),
                             daily_budget=float(cloud_cfg.get("daily_budget_usd", 0.50)),
                             spend_today=self.performance.spend_today,
                             unhealthy_after=int(router_cfg.get("unhealthy_after_failures", 3)),
                             cooldown_s=float(router_cfg.get("cooldown_s", 60.0)))
        if isinstance(local, OllamaProvider):
            local.refresh()
        self.personality = personality or Personality.load(ai.get("personality_file") or None)
        self.system_prompt = self.personality.system_prompt(e.value for e in AI_EXPRESSIONS)
        memory = config.get("memory", {})
        self.memory = ConversationMemory(memory.get("conversation_turns", 10),
                                         memory.get("conversation_idle_minutes", 5.0))
        self.last: Optional[Exchange] = None
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="alfiebot-ai")
        self._pending: List[PendingReply] = []

    @property
    def local(self) -> Optional[AIProvider]:
        return self.router.local

    @property
    def cloud(self) -> Optional[AIProvider]:
        return self.router.cloud

    @property
    def local_provider_name(self) -> str:
        return next((n for n, p in self.local_providers.items() if p is self.local), self.local.name)

    def use_local_provider(self, name: str) -> bool:
        """Developer panel: switch between the pretend AI and Ollama."""
        provider = self.local_providers.get(name)
        if provider is None:
            return False
        self.router.local = provider
        if isinstance(provider, OllamaProvider):
            provider.refresh()
        log.info("Local AI: %s", provider.label)
        return True

    @property
    def cloud_provider_name(self) -> str:
        return next((n for n, p in self.cloud_providers.items() if p is self.cloud), getattr(self.cloud, "name", ""))

    def use_cloud_provider(self, name: str) -> bool:
        """Developer panel: switch between the pretend cloud and OpenAI."""
        provider = self.cloud_providers.get(name)
        if provider is None:
            return False
        self.router.cloud = provider
        log.info("Cloud AI: %s", provider.label)
        return True

    # ---- entry point ----------------------------------------------------------
    def handle(self, inp: UserInput) -> Union[Reply, PendingReply, None]:
        """A Reply now, a PendingReply to poll, or None (keep listening:
        letters of a spelling are building up)."""
        if self.tutor.active:
            reply = self.tutor.handle(inp.text, inp.source, inp.confidence, inp.words)
            if not self.tutor.active:
                self.conversation.reset()
            return reply
        check = check_input(inp.text)
        if check.topic:
            log.info("Safety: %s topic; using the fixed reply", check.topic)
            self.last = Exchange(check.text, RoutingDecision([], [f"safety: {check.topic} topic, no AI"]),
                                 used="safety", privacy=check.privacy, masked=check.masked)
            mood = Expression.SAD if check.privacy == "sensitive" else Expression.HAPPY
            return Reply(check.reply, f"safety:{check.topic}", mood)
        tool = tool_answer(inp.text)
        if tool is not None:
            log.info("Answered by Python (%s)", tool.tool)
            self._remember(check.text, tool.text)
            return Reply(tool.text, f"tool:{tool.tool}", tool.mood)
        reply = self.conversation.respond(inp.text)
        if reply.intent in ("spelling_help", "spelling_choice"):
            return self._start_spelling(inp.text, reply)
        if reply.intent != "fallback" or not self.ai_enabled:
            self._remember(check.text, reply.text)
            return reply
        return self._ask_ai(inp, reply, check)

    def _remember(self, user_text: str, reply_text: str) -> None:
        self.memory.add("user", user_text)
        self.memory.add("assistant", reply_text)

    def _start_spelling(self, text: str, reply: Reply) -> Reply:
        norm = normalise(text)
        choice = reply.detail or next((c for c, p in CHOICES if p.search(norm)), None)
        if choice:
            return self.tutor.start(choice, text)
        self.tutor.start(None)  # menu; keep the conversation's wording
        reply.then = "spelling_setup"
        return reply

    # ---- AI ----------------------------------------------------------------
    def _ask_ai(self, inp: UserInput, fallback: Reply, check) -> Union[Reply, PendingReply]:
        decision = self.router.choose(check.text, privacy=check.privacy, source=inp.source)
        self.last = Exchange(check.text, decision, used="pending", privacy=check.privacy, masked=check.masked)
        history = self.memory.messages()
        previous = next((m["content"] for m in reversed(history) if m["role"] == "assistant"), None)
        self.memory.add("user", check.text)
        if not decision.providers:
            self.last.used = "fallback"
            self.memory.add("assistant", fallback.text)
            return fallback
        system = self.system_prompt
        first = decision.first
        if first.kind == "local" and (self.performance.recent_median(first.name, first.model) or 0) > self.slow_local_s:
            system += SHORT_HINT  # a slow local AI never moves the request to the cloud
            decision.reasons.append(f"local AI slow (over {self.slow_local_s:g} s): asking for a short answer")
        request = AIRequest(messages=history + [{"role": "user", "content": check.text}],
                            system=system, timeout_s=self.timeout_s, max_tokens=self.max_tokens)
        asked = last_question(previous)
        if not any(p.runs_in_background for p in decision.providers):
            future: Future = Future()
            future.set_result(self._run(decision, request, asked))
        else:
            future = self._executor.submit(self._run, decision, request, asked)
        pending = PendingReply(future, request, decision, fallback,
                               deadline=time.monotonic() + self.timeout_s, last_question=asked)
        reply = self.poll(pending)
        if reply is not None:
            return reply
        self._pending.append(pending)
        return pending

    def _run(self, decision: RoutingDecision, request: AIRequest, asked: Optional[str] = None) -> List[AIResult]:
        """Worker thread: try each provider in turn until one answers well."""
        results = []
        for provider in decision.providers:
            if request.cancel.is_set():
                break
            result = provider.generate(request)
            results.append(result)
            if result.ok:
                try:
                    self.usable(result.text, asked)
                    break
                except InvalidResponse as exc:
                    result.ok, result.error = False, f"invalid output: {exc}"
            log.warning("%s failed: %s", provider.label, result.error)
        return results

    def usable(self, text: str, asked: Optional[str] = None) -> Tuple[BrainResponse, List[str]]:
        return check_reply(self.personality, text, asked)

    def poll(self, pending: PendingReply) -> Optional[Reply]:
        """The reply once it's ready (or the fallback if it took too long)."""
        if pending.future.done():
            self._forget(pending)
            return self._finish(pending, pending.future.result())
        if time.monotonic() >= pending.deadline:
            pending.request.cancel.set()
            self._forget(pending)
            first = pending.decision.first
            result = AIResult("", first.name, first.model, ok=False, timed_out=True,
                              error=f"no answer within {self.timeout_s:g} s",
                              latency_s=time.monotonic() - pending.started)
            log.warning("%s took too long; using a scripted reply", first.label)
            return self._finish(pending, [result])
        return None

    def cancel(self, pending: Optional[PendingReply]) -> None:
        if pending is not None:
            pending.request.cancel.set()
            self._forget(pending)

    def _forget(self, pending: PendingReply) -> None:
        if pending in self._pending:
            self._pending.remove(pending)

    def _finish(self, pending: PendingReply, results: List[AIResult]) -> Reply:
        exchange = self.last if self.last and self.last.decision is pending.decision else \
            Exchange("", pending.decision)
        exchange.results = results
        for provider, result in zip(pending.decision.providers, results):
            self.router.report(provider, result.ok)
        for result in results:
            self.performance.record(result)
        good = results[-1] if results and results[-1].ok else None
        if good is not None:
            try:
                response, notes = self.usable(good.text, pending.last_question)
            except InvalidResponse as exc:  # checked on the worker, but be safe
                notes, response = [str(exc)], None
            exchange.notes = notes
            if response is not None:
                exchange.used = "ai"
                reply = to_reply(response, intent=f"ai:{good.provider}")
                if response.action == "start_spelling":
                    menu = self.tutor.start(None)
                    reply.text = f"{reply.text} {menu.text}"
                    reply.then = menu.then
                self.conversation.last_reply = reply  # so "say that again" repeats it
                self.memory.add("assistant", response.speech)
                return reply
        exchange.used = "fallback"
        self.memory.add("assistant", pending.fallback.text)
        return pending.fallback

    def close(self) -> None:
        for pending in list(self._pending):
            self.cancel(pending)
        self._executor.shutdown(wait=False, cancel_futures=True)
