"""A small observable state machine.

Stage 1 allows any transition so the developer panel can show every state.
Stage 2 adds the conversation engine, which decides when to change state.
"""

import logging
from typing import Callable, List

from alfiebot.core.states import RobotState

log = logging.getLogger(__name__)

Listener = Callable[[RobotState, RobotState], None]


class StateMachine:
    def __init__(self, initial: RobotState = RobotState.SLEEPING):
        self._state = initial
        self._listeners: List[Listener] = []
        self.time_in_state = 0.0

    @property
    def state(self) -> RobotState:
        return self._state

    def add_listener(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def set_state(self, new_state: RobotState) -> bool:
        """Change state. Returns False if already in that state."""
        new_state = RobotState(new_state)
        if new_state == self._state:
            return False
        old = self._state
        self._state = new_state
        self.time_in_state = 0.0
        log.info("State %s -> %s", old.value, new_state.value)
        for listener in list(self._listeners):
            listener(old, new_state)
        return True

    def update(self, dt: float) -> None:
        self.time_in_state += dt
