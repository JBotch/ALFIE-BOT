"""Chooses which AI provider answers a request, and says why.

By the time a request gets here, the brain has already handled safety
topics, the spelling tutor, hand-written replies and Python answers (maths,
time, date). The router then applies, in order:

1. Privacy gate. The cloud is only a candidate when ALL of these hold:
   a parent has switched the cloud on, the internet is up, an API key is
   set, the cloud isn't resting after repeated failures, today's estimated
   spend is under the daily budget, and either
   - an adult typed it in an adult test session (never spoken words, which
     could be a child's), or
   - a parent has marked the child-data review as complete,
   AND the request is classified "public" (no personal details, nothing
   about the child). Personal and sensitive requests never go to the cloud
   in any mode, even in an adult test session.
2. Availability. If the local AI isn't available (Ollama not running,
   model not installed, or resting after repeated failures), the pretend AI
   takes its place and the reasons say why.
3. Mode. local_only: local. cloud_only: cloud if the gate allows, otherwise
   local. automatic: local for everyday chat; cloud first for long or
   "why / how / explain" questions if the gate allows, otherwise local.
4. Failure. If the first choice fails, the other allowed provider is tried,
   then the brain's hand-written reply. A slow local AI never sends anything
   to the cloud unless rule 1 already allows it.
"""

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from alfiebot.ai.connectivity import Connectivity
from alfiebot.ai.provider_base import AIProvider

log = logging.getLogger(__name__)

MODES = ("local_only", "cloud_only", "automatic")
MODE_LABELS = {"local_only": "Local only", "cloud_only": "Cloud only", "automatic": "Automatic"}
COMPLEX = re.compile(r"^(why|how|explain|what makes|what would happen|tell me about|what is the difference)\b")


@dataclass
class RoutingDecision:
    providers: List[AIProvider] = field(default_factory=list)  # first choice, then fallbacks
    reasons: List[str] = field(default_factory=list)

    @property
    def first(self) -> Optional[AIProvider]:
        return self.providers[0] if self.providers else None

    @property
    def uses_cloud(self) -> bool:
        return any(p.kind == "cloud" for p in self.providers)

    def summary(self) -> str:
        chosen = " then ".join(p.label for p in self.providers) or "no AI (scripted reply)"
        return f"{chosen}: " + "; ".join(self.reasons)


class Router:
    def __init__(self, local: Optional[AIProvider], cloud: Optional[AIProvider] = None,
                 connectivity: Connectivity = None, mode: str = "local_only",
                 cloud_enabled: bool = False, local_fallback: Optional[AIProvider] = None,
                 review_complete: bool = False, daily_budget: float = 0.50,
                 spend_today: Callable[[], float] = None, unhealthy_after: int = 3, cooldown_s: float = 60.0,
                 clock: Callable[[], float] = None):
        self.local = local
        self.local_fallback = local_fallback
        self.cloud = cloud
        self.connectivity = connectivity or Connectivity()
        self.mode = mode if mode in MODES else "local_only"
        # Parent settings, both off by default.
        self.cloud_enabled = cloud_enabled
        self.review_complete = review_complete
        # Developer panel: an adult typing test questions.
        self.adult_test_session = False
        self.daily_budget = daily_budget
        self.spend_today = spend_today or (lambda: 0.0)
        self.unhealthy_after = max(1, int(unhealthy_after))
        self.cooldown_s = cooldown_s
        self.clock = clock or time.monotonic
        self._failures: Dict[int, int] = {}
        self._resting_until: Dict[int, float] = {}

    # ---- health ----------------------------------------------------------------
    def report(self, provider: AIProvider, ok: bool) -> None:
        """After each answer: repeated failures rest a provider for a while."""
        key = id(provider)
        if ok:
            self._failures[key] = 0
            return
        self._failures[key] = self._failures.get(key, 0) + 1
        if self._failures[key] >= self.unhealthy_after:
            self._failures[key] = 0
            self._resting_until[key] = self.clock() + self.cooldown_s
            log.warning("%s failed %d times in a row; resting it for %.0f s", provider.label,
                        self.unhealthy_after, self.cooldown_s)

    def resting(self, provider: Optional[AIProvider]) -> bool:
        return provider is not None and self.clock() < self._resting_until.get(id(provider), 0.0)

    def reset_health(self) -> None:
        self._failures.clear()
        self._resting_until.clear()

    # ---- privacy gate ------------------------------------------------------------
    def cloud_blocked_reason(self, privacy: str, source: str = "typed") -> Optional[str]:
        """Why the cloud can't take this request, or None if it can."""
        if self.cloud is None:
            return "no cloud provider configured"
        if not self.cloud_enabled:
            return "cloud is switched off (parent setting)"
        if privacy != "public":
            return f"privacy: a {privacy} request never leaves this device"
        if not self.connectivity.online:
            return f"internet is {self.connectivity.status}"
        if not self.cloud.available():
            return f"cloud unavailable: {self.cloud.unavailable_reason or 'unknown'}"
        if self.resting(self.cloud):
            return "cloud is resting after repeated failures"
        adult = self.adult_test_session and source == "typed"
        if not adult:
            if self.adult_test_session:
                return "adult test session only covers typed text, not speech"
            if not self.review_complete:
                return "child-data review not marked complete (parent setting)"
        spent = self.spend_today()
        if spent >= self.daily_budget:
            return f"daily cloud budget reached (${spent:.2f} of ${self.daily_budget:.2f})"
        return None

    # ---- choosing ------------------------------------------------------------------
    def choose(self, text: str, privacy: str = "unclassified", source: str = "typed") -> RoutingDecision:
        reasons = [f"mode {self.mode}", f"privacy {privacy}"]
        local_provider = self.local
        local_ok = local_provider is not None and local_provider.available() and not self.resting(local_provider)
        if not local_ok:
            why = ("resting after repeated failures" if self.resting(local_provider) else
                   (local_provider.unavailable_reason if local_provider else "none configured"))
            reasons.append(f"local AI unavailable: {why}")
            backup = self.local_fallback
            if backup is not None and backup is not local_provider and backup.available():
                local_provider, local_ok = backup, True
                reasons.append(f"using {backup.label} instead")
        blocked = self.cloud_blocked_reason(privacy, source)
        if blocked:
            reasons.append(f"no cloud: {blocked}")
        local = [local_provider] if local_ok else []
        cloud = [] if blocked else [self.cloud]

        if self.mode == "local_only":
            order = local
        elif self.mode == "cloud_only":
            order = cloud + local
            if cloud:
                reasons.append("cloud chosen (cloud only mode); local as fallback")
            elif local:
                reasons.append("falling back to local")
        else:
            complex_question = bool(COMPLEX.search(text.lower())) or len(text.split()) > 14
            if complex_question and cloud:
                order = cloud + local
                reasons.append("complex question: cloud first, local as fallback")
            else:
                order = local + cloud
                reasons.append("complex question, but cloud not allowed" if complex_question
                               else "everyday chat: local first")
        decision = RoutingDecision(order, reasons)
        log.info("Route: %s", decision.summary())
        return decision
