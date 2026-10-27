"""What goes into the brain and what comes out."""

from dataclasses import dataclass
from typing import List, Optional, Tuple

from alfiebot.core.states import Expression


@dataclass(frozen=True)
class UserInput:
    text: str
    source: str = "typed"  # "typed", "simulated" or "voice"
    confidence: float = 1.0
    words: Optional[List[Tuple[str, float]]] = None


@dataclass
class BrainResponse:
    """A validated reply: what to say, which face to make, and at most one
    allowlisted action (see core/actions.py)."""

    speech: str
    expression: Expression = Expression.HAPPY
    action: Optional[str] = None
