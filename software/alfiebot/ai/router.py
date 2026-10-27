"""Chooses which AI provider answers a request, and says why.

Phase 2 rules (privacy classification and cost limits arrive in Phases 3-4):

1. Cloud is only ever a candidate when a parent has switched it on, the
   internet is up, the provider is available, and the request is either
   classified "public" or typed by an adult in an adult test session.
   Nothing classifies requests as "public" yet, so in a child's session
   the cloud is never used.
2. local_only: the local provider.
3. cloud_only: the cloud provider if rule 1 allows it, otherwise local.
4. automatic: local for everyday chat; cloud for long or "why/how/explain"
   questions if rule 1 allows it, otherwise local.
5. If the first choice fails, the other allowed provider is tried. A slow
   local reply never sends anything to the cloud unless rule 1 already
   allows it.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

from alfiebot.ai.connectivity import Connectivity
from alfiebot.ai.provider_base import AIProvider

log = logging.getLogger(__name__)

MODES = ("local_only", "cloud_only", "automatic")
MODE_LABELS = {"local_only": "Local only", "cloud_only": "Cloud only", "automatic": "Automatic"}
COMPLEX = re.compile(r"^(why|how|explain|what makes|what would happen|tell me about)\b")


@dataclass
class RoutingDecision:
    providers: List[AIProvider] = field(default_factory=list)  # first choice, then fallbacks
    reasons: List[str] = field(default_factory=list)

    @property
    def first(self) -> Optional[AIProvider]:
        return self.providers[0] if self.providers else None

    def summary(self) -> str:
        chosen = " then ".join(p.label for p in self.providers) or "no AI (scripted reply)"
        return f"{chosen}: " + "; ".join(self.reasons)


class Router:
    def __init__(self, local: Optional[AIProvider], cloud: Optional[AIProvider] = None,
                 connectivity: Connectivity = None, mode: str = "local_only",
                 cloud_enabled: bool = False):
        self.local = local
        self.cloud = cloud
        self.connectivity = connectivity or Connectivity()
        self.mode = mode if mode in MODES else "local_only"
        # Parent switch, off by default. Even when on, only public requests
        # (or an adult test session) can go to the cloud.
        self.cloud_enabled = cloud_enabled
        self.adult_test_session = False

    def cloud_blocked_reason(self, privacy: str) -> Optional[str]:
        """Why the cloud can't take this request, or None if it can."""
        if self.cloud is None:
            return "no cloud provider configured"
        if not self.cloud_enabled:
            return "cloud is switched off (parent setting)"
        if not self.connectivity.online:
            return f"internet is {self.connectivity.status}"
        if not self.cloud.available():
            return f"cloud unavailable: {self.cloud.unavailable_reason or 'unknown'}"
        if privacy != "public" and not self.adult_test_session:
            return f"privacy: a {privacy} request can't leave this device"
        return None

    def choose(self, text: str, privacy: str = "unclassified") -> RoutingDecision:
        reasons = [f"mode {self.mode}"]
        local_ok = self.local is not None and self.local.available()
        if not local_ok:
            reasons.append("local AI unavailable: "
                           + (self.local.unavailable_reason if self.local else "none configured"))
        blocked = self.cloud_blocked_reason(privacy)
        cloud_ok = blocked is None
        if blocked:
            reasons.append(f"no cloud: {blocked}")
        local = [self.local] if local_ok else []
        cloud = [self.cloud] if cloud_ok else []

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
