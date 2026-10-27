"""The brain: decides who answers what Alfie says.

    1. A running spelling activity -> the spelling tutor (Python marks every
       answer; AI never does).
    2. Anything the scripted conversation engine recognises (greetings,
       jokes, "help me with my spellings"...) -> its hand-written reply.
    3. Everything else -> the router picks an AI provider. The provider runs
       on a worker thread so the face keeps animating; the robot polls for
       the answer each frame. Its output is validated (core/actions.py)
       before it is used.
    4. If the AI is switched off, unavailable, too slow, fails or sends back
       something unusable -> the scripted fallback reply.

Safety checks on what goes in and out (privacy classification, personal
details, topics) arrive in Phase 3; until then nothing is classified as
"public", so the router never lets a child's words reach the cloud.
"""

import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import List, Optional, Union

from alfiebot.ai.connectivity import Connectivity
from alfiebot.ai.mock_provider import MockProvider
from alfiebot.ai.performance import PerformanceTracker
from alfiebot.ai.provider_base import AIProvider, AIRequest, AIResult
from alfiebot.ai.router import Router, RoutingDecision
from alfiebot.conversation.engine import ConversationEngine, Reply
from alfiebot.conversation.intents import normalise
from alfiebot.core.actions import InvalidResponse, parse_response, to_reply
from alfiebot.core.events import UserInput
from alfiebot.spelling.tutor import CHOICES, SpellingTutor

log = logging.getLogger(__name__)

# Placeholder until the personality engine (Phase 3) builds the real prompt.
SYSTEM_PROMPT = (
    "You are AlfieBot, a joyful, playful, slightly robotic companion robot for a child. "
    "Use British English. Reply in one or two short sentences, kindly, and never pretend to be human. "
    'Answer only with JSON: {"speech": "...", "expression": "happy|excited|thinking|confused|listening", '
    '"action": null}.')


@dataclass
class PendingReply:
    """An AI answer being worked on in the background."""

    future: Future
    request: AIRequest
    decision: RoutingDecision
    fallback: Reply
    deadline: float
    started: float = field(default_factory=time.monotonic)


@dataclass
class Exchange:
    """The last AI exchange, for the developer panel."""

    text: str
    decision: RoutingDecision
    results: List[AIResult] = field(default_factory=list)
    used: str = ""  # "ai", "fallback" or "pending"
    notes: List[str] = field(default_factory=list)


def create_providers(ai: dict):
    """The local and cloud providers named in the config. Only mock
    providers exist so far (Ollama arrives in Phase 3, OpenAI in Phase 4)."""
    delay = float(ai.get("mock_delay_s", 0.0))
    local = MockProvider("mock-local", "local", ai.get("local_model") or "mock-1", delay_s=delay)
    cloud = MockProvider("mock-cloud", "cloud", "mock-cloud-1", delay_s=delay)
    if ai.get("local_provider", "mock") != "mock":
        log.warning("Local AI provider %r isn't available yet; using the mock", ai.get("local_provider"))
    return local, cloud


class Brain:
    def __init__(self, config: dict, conversation: ConversationEngine, tutor: SpellingTutor,
                 local: AIProvider = None, cloud: AIProvider = None, connectivity: Connectivity = None,
                 performance: PerformanceTracker = None):
        ai = config.get("ai", {})
        self.conversation = conversation
        self.tutor = tutor
        self.ai_enabled = bool(ai.get("enabled", True))
        self.timeout_s = float(ai.get("timeout_s", 8.0))
        if local is None and cloud is None:
            local, cloud = create_providers(ai)
        self.connectivity = connectivity or Connectivity()
        self.router = Router(local, cloud, self.connectivity, ai.get("mode", "local_only"),
                             cloud_enabled=bool(ai.get("cloud_enabled", False)))
        self.performance = performance or PerformanceTracker()
        self.last: Optional[Exchange] = None
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="alfiebot-ai")
        self._pending: List[PendingReply] = []

    @property
    def local(self) -> Optional[AIProvider]:
        return self.router.local

    @property
    def cloud(self) -> Optional[AIProvider]:
        return self.router.cloud

    # ---- entry point ----------------------------------------------------------
    def handle(self, inp: UserInput) -> Union[Reply, PendingReply, None]:
        """A Reply now, a PendingReply to poll, or None (keep listening:
        letters of a spelling are building up)."""
        if self.tutor.active:
            reply = self.tutor.handle(inp.text, inp.source, inp.confidence, inp.words)
            if not self.tutor.active:
                self.conversation.reset()
            return reply
        reply = self.conversation.respond(inp.text)
        if reply.intent in ("spelling_help", "spelling_choice"):
            return self._start_spelling(inp.text, reply)
        if reply.intent != "fallback" or not self.ai_enabled:
            return reply
        return self._ask_ai(inp, reply)

    def _start_spelling(self, text: str, reply: Reply) -> Reply:
        norm = normalise(text)
        choice = reply.detail or next((c for c, p in CHOICES if p.search(norm)), None)
        if choice:
            return self.tutor.start(choice, text)
        self.tutor.start(None)  # menu; keep the conversation's wording
        reply.then = "spelling_setup"
        return reply

    # ---- AI ----------------------------------------------------------------
    def _ask_ai(self, inp: UserInput, fallback: Reply) -> Union[Reply, PendingReply]:
        decision = self.router.choose(inp.text)
        self.last = Exchange(inp.text, decision, used="pending")
        if not decision.providers:
            self.last.used = "fallback"
            return fallback
        request = AIRequest(messages=[{"role": "user", "content": inp.text}], system=SYSTEM_PROMPT,
                            timeout_s=self.timeout_s)
        if not any(p.runs_in_background for p in decision.providers):
            future: Future = Future()
            future.set_result(self._run(decision, request))
        else:
            future = self._executor.submit(self._run, decision, request)
        pending = PendingReply(future, request, decision, fallback,
                               deadline=time.monotonic() + self.timeout_s)
        reply = self.poll(pending)
        if reply is not None:
            return reply
        self._pending.append(pending)
        return pending

    def _run(self, decision: RoutingDecision, request: AIRequest) -> List[AIResult]:
        """Worker thread: try each provider in turn until one answers well."""
        results = []
        for provider in decision.providers:
            if request.cancel.is_set():
                break
            result = provider.generate(request)
            results.append(result)
            if result.ok:
                try:
                    parse_response(result.text)
                    break
                except InvalidResponse as exc:
                    result.ok, result.error = False, f"invalid output: {exc}"
            log.warning("%s failed: %s", provider.label, result.error)
        return results

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
        for result in results:
            self.performance.record(result)
        good = results[-1] if results and results[-1].ok else None
        if good is not None:
            try:
                response, notes = parse_response(good.text)
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
                return reply
        exchange.used = "fallback"
        return pending.fallback

    def close(self) -> None:
        for pending in list(self._pending):
            self.cancel(pending)
        self._executor.shutdown(wait=False, cancel_futures=True)
