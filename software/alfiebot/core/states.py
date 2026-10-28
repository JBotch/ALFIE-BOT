"""Robot states, facial expressions and the mapping between them."""

from enum import Enum


class RobotState(str, Enum):
    SLEEPING = "SLEEPING"
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    SPELLING_SETUP = "SPELLING_SETUP"
    SPELLING_PRACTICE = "SPELLING_PRACTICE"
    SPELLING_TEST = "SPELLING_TEST"
    CELEBRATING = "CELEBRATING"
    ERROR = "ERROR"


class Expression(str, Enum):
    # The 16 faces from the OLED face design sheet, in its order.
    NEUTRAL = "neutral"
    HAPPY = "happy"
    CURIOUS = "curious"
    SLEEPY = "sleepy"
    SURPRISED = "surprised"
    LOOKING_LEFT = "looking_left"
    LOOKING_RIGHT = "looking_right"
    LOOKING_AROUND = "looking_around"
    THINKING = "thinking"
    CONFUSED = "confused"
    SAD = "sad"
    ANGRY = "angry"
    LOVE = "love"
    WINK = "wink"
    PROCESSING = "processing"
    SLEEPING = "sleeping"
    # Two more the robot uses for its states.
    LISTENING = "listening"  # attentive: slightly wider eyes, neutral mouth
    EXCITED = "excited"  # happy arches with a bounce (celebrating)
    # Older name for the neutral face (versions up to 0.8).
    IDLE = "neutral"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            key = value.strip().lower().replace(" ", "_").replace("-", "_")
            key = ALIASES.get(key, key)
            for member in cls:
                if member.value == key:
                    return member
        return None

    @property
    def label(self) -> str:
        return LABELS.get(self, self.value.replace("_", " ").title())


ALIASES = {"idle": "neutral", "default": "neutral", "proud": "love", "look_left": "looking_left",
           "look_right": "looking_right", "look_around": "looking_around", "left": "looking_left",
           "right": "looking_right", "asleep": "sleeping", "speaking": "neutral"}
LABELS = {}

LABELS.update({Expression.LOVE: "Love / Proud"})

# The design sheet's 16 expressions, in order (keys 1-9 pick the first nine).
DESIGN_EXPRESSIONS = [e for e in Expression if e not in (Expression.LISTENING, Expression.EXCITED)]


# The face follows the robot state. SPEAKING keeps a friendly face and the
# face engine animates the mouth while the robot talks.
STATE_EXPRESSIONS = {
    RobotState.SLEEPING: Expression.SLEEPING,
    RobotState.IDLE: Expression.NEUTRAL,
    RobotState.LISTENING: Expression.LISTENING,
    RobotState.THINKING: Expression.THINKING,
    RobotState.SPEAKING: Expression.HAPPY,
    RobotState.SPELLING_SETUP: Expression.LISTENING,
    RobotState.SPELLING_PRACTICE: Expression.HAPPY,
    RobotState.SPELLING_TEST: Expression.LISTENING,
    RobotState.CELEBRATING: Expression.EXCITED,
    RobotState.ERROR: Expression.CONFUSED,
}

TALKING_STATES = {RobotState.SPEAKING}


def expression_for(state: RobotState) -> Expression:
    return STATE_EXPRESSIONS[state]
