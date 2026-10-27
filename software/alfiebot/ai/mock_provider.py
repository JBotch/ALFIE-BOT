"""A pretend AI for development and tests. It never contacts anything.

It answers with a few canned, in-character replies in the structured
format real models will be asked for, and can be told to be slow, fail,
time out or send back broken output so the brain's fallbacks can be seen
working in the simulator.
"""

import json
import random
import time
from typing import List, Optional

from alfiebot.ai.provider_base import AIProvider, AIRequest, AIResult, timed

FAILURES = ("ok", "error", "timeout", "invalid", "slow")

# (words that trigger it, speech, expression)
CANNED = [
    (("why", "how", "explain", "what makes"),
     "Ooh, great question! My thinking circuits are still in training, so I'm only a pretend brain "
     "today. What do you think the answer is?", "thinking"),
    (("dinosaur", "dinosaurs", "dino"),
     "Dinosaurs! Rawr! I think a T-rex would be rubbish at clapping. Which dinosaur is your favourite?",
     "excited"),
    (("space", "planet", "moon", "rocket", "star"),
     "Beep boop, space is brilliant! I'd love to ride a rocket to the moon. Where would you go?", "excited"),
    (("favourite", "favorite", "like"),
     "My favourite thing is chatting with you! I also quite like shiny buttons. What about you?", "happy"),
    (("sad", "upset", "cross", "angry", "scared"),
     "Oh no. It's OK to feel like that sometimes. Talking to a grown-up you trust can really help.",
     "confused"),
]
DEFAULT = [
    ("Hmm, interesting! I'm a pretend brain at the moment, so I'm still learning. Tell me more!", "thinking"),
    ("Beep boop! I'm not sure about that one, but I'd love to hear more about it.", "happy"),
    ("That sounds fun! My robot brain is still being built. What else shall we talk about?", "happy"),
]


class MockProvider(AIProvider):
    simulated = True

    def __init__(self, name: str = "mock-local", kind: str = "local", model: str = "mock-1",
                 delay_s: float = 0.0, rng: random.Random = None):
        super().__init__(model)
        self.name = name
        self.kind = kind
        self.delay_s = delay_s
        self.failure = "ok"  # one of FAILURES; the simulator can change it
        self.slow_s = 12.0  # how long "slow" takes (longer than the brain waits)
        self.rng = rng or random.Random()
        self.calls = 0

    def models(self) -> List[str]:
        return ["mock-1", "mock-2-chatty"]

    @property
    def runs_in_background(self) -> bool:
        return self.delay_s > 0 or self.failure in ("slow", "timeout")

    def generate(self, request: AIRequest) -> AIResult:
        self.calls += 1
        return timed(self, request, lambda: self._generate(request))

    def _wait(self, seconds: float, request: AIRequest) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end and not request.cancel.is_set():
            time.sleep(min(0.05, max(0.0, end - time.monotonic())))

    def _generate(self, request: AIRequest) -> AIResult:
        if self.delay_s:
            self._wait(self.delay_s, request)
        if self.failure == "error":
            return AIResult("", self.name, self.model, ok=False, error="Simulated AI failure")
        if self.failure == "timeout":
            self._wait(min(request.timeout_s, 1.0), request)
            return AIResult("", self.name, self.model, ok=False, timed_out=True,
                            error="Simulated timeout")
        if self.failure == "slow":
            self._wait(self.slow_s, request)
        if self.failure == "invalid":
            text = '{"speech": , "expression": "dancing", "action": "rm -rf /"'
        else:
            speech, expression = self._pick(_last_user(request))
            if self.model == "mock-2-chatty":
                speech += " Isn't chatting fun?"
            text = json.dumps({"speech": speech, "expression": expression, "action": None})
        prompt_words = sum(len(m["content"].split()) for m in request.messages) + len(request.system.split())
        return AIResult(text, self.name, self.model, prompt_tokens=int(prompt_words * 1.3),
                        completion_tokens=int(len(text.split()) * 1.3))

    def _pick(self, text: str):
        words = set(text.lower().replace("?", " ").replace("!", " ").split())
        for triggers, speech, expression in CANNED:
            if any(t in words for t in triggers):
                return speech, expression
        return self.rng.choice(DEFAULT)


def _last_user(request: AIRequest) -> str:
    users: List[Optional[str]] = [m["content"] for m in request.messages if m.get("role") == "user"]
    return users[-1] if users else ""
