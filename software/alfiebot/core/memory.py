"""Short-term conversation memory, so an AI reply can follow on from the
last few things said.

Kept in RAM only and never written to disk. It holds the last few turns,
forgets everything when AlfieBot goes to sleep or after a quiet spell, and
only ever stores text whose personal details have already been masked
(core/safety.py).
"""

import time
from dataclasses import dataclass
from typing import Callable, Dict, List


@dataclass
class Turn:
    role: str  # "user" or "assistant"
    text: str
    at: float


class ConversationMemory:
    def __init__(self, max_turns: int = 10, idle_minutes: float = 5.0, clock: Callable[[], float] = None):
        self.max_turns = max(0, int(max_turns))
        self.idle_s = float(idle_minutes) * 60.0
        self.clock = clock or time.monotonic
        self.turns: List[Turn] = []

    def add(self, role: str, text: str) -> None:
        if not self.max_turns or not text:
            return
        self.expire()
        self.turns.append(Turn(role, text, self.clock()))
        del self.turns[:-self.max_turns]

    def expire(self) -> None:
        """Forget everything after a quiet spell."""
        if self.turns and self.clock() - self.turns[-1].at > self.idle_s:
            self.turns.clear()

    def clear(self) -> None:
        self.turns.clear()

    def messages(self) -> List[Dict[str, str]]:
        self.expire()
        return [{"role": t.role, "content": t.text} for t in self.turns]

    def __len__(self) -> int:
        return len(self.turns)
