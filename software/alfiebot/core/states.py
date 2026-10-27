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
    SLEEPING = "sleeping"
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    HAPPY = "happy"
    EXCITED = "excited"
    CONFUSED = "confused"


# The face follows the robot state. SPEAKING keeps a friendly face and the
# face engine animates the mouth while the robot talks.
STATE_EXPRESSIONS = {
    RobotState.SLEEPING: Expression.SLEEPING,
    RobotState.IDLE: Expression.IDLE,
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
