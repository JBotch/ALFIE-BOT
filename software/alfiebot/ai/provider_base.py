"""The interface every AI provider implements, so providers can be swapped
without touching the rest of AlfieBot."""

import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# The structured reply every provider is asked for (see core/actions.py).
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "speech": {"type": "string"},
        "expression": {"type": "string"},
        "action": {"type": ["string", "null"]},
    },
    "required": ["speech", "expression", "action"],
}


@dataclass
class AIRequest:
    messages: List[Dict[str, str]]  # [{"role": "user" | "assistant", "content": ...}]
    system: str = ""
    task: str = "conversation"
    max_tokens: int = 120
    timeout_s: float = 8.0
    json_schema: Optional[dict] = field(default_factory=lambda: dict(RESPONSE_SCHEMA))
    # Set when the brain gives up on the request, so a provider can stop early.
    cancel: threading.Event = field(default_factory=threading.Event)


@dataclass
class AIResult:
    text: str
    provider: str
    model: str
    ok: bool = True
    error: Optional[str] = None
    timed_out: bool = False
    latency_s: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_estimate: float = 0.0
    memory_mb: Optional[float] = None

    @property
    def tokens_per_s(self) -> Optional[float]:
        if self.completion_tokens and self.latency_s >= 0.05:  # too quick to measure otherwise
            return self.completion_tokens / self.latency_s
        return None


class AIProvider(ABC):
    """``kind`` is "local" or "cloud": the router treats them differently.
    ``simulated`` providers never contact anything outside the program."""

    name = "base"
    kind = "local"
    simulated = False

    def __init__(self, model: str = ""):
        self.model = model

    def available(self) -> bool:
        return True

    @property
    def unavailable_reason(self) -> str:
        return ""

    def models(self) -> List[str]:
        return [self.model] if self.model else []

    @property
    def runs_in_background(self) -> bool:
        """True if generate() may take a while, so the brain runs it on a
        worker thread and the face keeps animating."""
        return True

    @abstractmethod
    def generate(self, request: AIRequest) -> AIResult:
        """Blocking call. Must not raise: errors come back as ok=False."""

    @property
    def label(self) -> str:
        return f"{self.name} ({self.model})" if self.model else self.name


def timed(provider: AIProvider, request: AIRequest, call) -> AIResult:
    """Run ``call()`` -> AIResult, filling in latency and catching errors."""
    start = time.monotonic()
    try:
        result = call()
    except Exception as exc:  # a provider bug must never crash the robot
        result = AIResult("", provider.name, provider.model, ok=False, error=f"{type(exc).__name__}: {exc}")
    if not result.latency_s:
        result.latency_s = time.monotonic() - start
    return result
