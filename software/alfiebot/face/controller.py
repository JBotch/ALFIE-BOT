"""What the rest of AlfieBot (and the AI brain) may ask the face to do.

The face only ever receives names from fixed lists and numbers clamped to
safe ranges; nothing here can run code or draw arbitrary graphics. The
robot queues these commands and the face view applies them on its next
frame, so asking never blocks speech, listening or a spelling activity.
"""

from dataclasses import dataclass
from typing import Optional

from alfiebot.core.states import Expression
from alfiebot.face.poses import LOOK_DIRECTIONS

# Expressions an AI reply may ask for. Not angry (never at a child), and not
# sleeping, sleepy or processing: those belong to the robot's own states.
AI_EXPRESSIONS = frozenset({
    Expression.NEUTRAL, Expression.HAPPY, Expression.EXCITED, Expression.CURIOUS, Expression.SURPRISED,
    Expression.THINKING, Expression.CONFUSED, Expression.SAD, Expression.LOVE, Expression.WINK,
    Expression.LOOKING_LEFT, Expression.LOOKING_RIGHT, Expression.LOOKING_AROUND, Expression.LISTENING,
})
COMMANDS = ("look", "look_around", "blink", "double_blink", "talk_test")
MIN_SECONDS, MAX_SECONDS = 0.3, 6.0


@dataclass(frozen=True)
class FaceCommand:
    kind: str
    value: Optional[object] = None
    seconds: float = 2.5


def ai_expression(name) -> Optional[Expression]:
    """The Expression an AI asked for, or None if it isn't an approved name."""
    try:
        expression = Expression(name)
    except ValueError:
        return None
    return expression if expression in AI_EXPRESSIONS else None


def face_command(kind: str, value=None, seconds: float = 2.5) -> FaceCommand:
    """A validated command; raises ValueError for anything not on the lists."""
    if kind not in COMMANDS:
        raise ValueError(f"unknown face command {kind!r}")
    if kind == "look":
        value = str(value).lower()
        if value not in LOOK_DIRECTIONS:
            raise ValueError(f"unknown look direction {value!r}")
    elif kind == "talk_test":
        value = bool(value)
    else:
        value = None
    seconds = min(MAX_SECONDS, max(MIN_SECONDS, float(seconds)))
    return FaceCommand(kind, value, seconds)
