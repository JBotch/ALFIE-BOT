"""The robot's brain, shared by the simulator and the Pi.

Stage 1 handles start/stop, the state machine, the transcript and the
button. Stage 2 plugs the conversation engine into ``handle_text``.
"""

import logging

from alfiebot.core.state_machine import StateMachine
from alfiebot.core.states import TALKING_STATES, Expression, RobotState, expression_for
from alfiebot.core.transcript import Transcript
from alfiebot.hardware.base import Platform
from alfiebot.speech.mic_gate import MicGate

log = logging.getLogger(__name__)


class AlfieBot:
    def __init__(self, config: dict, platform: Platform):
        self.config = config
        self.platform = platform
        self.name = config["robot"]["name"]
        self.state_machine = StateMachine(RobotState.SLEEPING)
        self.transcript = Transcript()
        self.mic_gate = MicGate()
        self.running = False
        # Developer override: show an expression regardless of state.
        self.expression_override = None
        self._face_listeners = []
        self.state_machine.add_listener(self._on_state_change)

    # ---- face hookup -----------------------------------------------------
    def add_face_listener(self, listener) -> None:
        """listener(expression, talking) is called whenever the face should change."""
        self._face_listeners.append(listener)
        listener(self.expression, self.talking)

    @property
    def state(self) -> RobotState:
        return self.state_machine.state

    @property
    def expression(self) -> Expression:
        return self.expression_override or expression_for(self.state)

    @property
    def talking(self) -> bool:
        return self.state in TALKING_STATES

    def _notify_face(self) -> None:
        for listener in self._face_listeners:
            listener(self.expression, self.talking)

    def _on_state_change(self, old: RobotState, new: RobotState) -> None:
        self.mic_gate.set_speaking(new in TALKING_STATES)
        self._notify_face()

    def set_state(self, state: RobotState) -> None:
        self.expression_override = None
        if not self.state_machine.set_state(state):
            self._notify_face()

    def show_expression(self, expression) -> None:
        """Developer panel: preview an expression without changing state."""
        self.expression_override = Expression(expression) if expression else None
        if self.expression_override:
            log.info("Expression preview: %s", self.expression.value)
        else:
            log.info("Expression preview off; face follows state %s", self.state.value)
        self._notify_face()

    # ---- lifecycle -------------------------------------------------------
    def start(self) -> None:
        if self.running:
            return
        self.running = True
        log.info("%s started", self.name)
        self.set_state(RobotState.IDLE)

    def stop(self) -> None:
        if not self.running:
            return
        self.running = False
        log.info("%s stopped", self.name)
        self.set_state(RobotState.SLEEPING)

    # ---- input -----------------------------------------------------------
    def handle_text(self, text: str, source: str = "typed") -> None:
        """Text from the keyboard (simulated speech) or a recogniser."""
        text = text.strip()
        if not text:
            return
        if not self.running:
            log.warning("Ignored %r: %s is stopped. Press Start first.", text, self.name)
            return
        self.transcript.add("user", text, source)
        # Stage 2 replaces this with the conversation engine.
        self.transcript.add("system", "Conversation engine arrives in Stage 2.")
        log.info("Received %s input: %r (no conversation engine yet)", source, text)

    def update(self, dt: float) -> None:
        self.state_machine.update(dt)
        self.mic_gate.update(dt)
        button = self.platform.button
        if button.poll_pressed():
            log.info("Button pressed (push-to-talk arrives in Stage 4)")
            if not self.running:
                self.start()
        if button.poll_released():
            log.debug("Button released")
