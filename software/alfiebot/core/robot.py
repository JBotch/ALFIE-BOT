"""The robot's brain, shared by the simulator and the Pi.

Conversation flow (Stage 2):

    SLEEPING/IDLE --"Hey AlfieBot" or button--> (eyes open) SPEAKING greeting
    SPEAKING --finished--> LISTENING --text--> THINKING --> SPEAKING --> LISTENING
    LISTENING --no answer for listen_timeout--> IDLE --sleep_after_idle--> SLEEPING

Text that arrives while AlfieBot is thinking or talking is held and handled
as soon as it is listening again. The microphone gate is closed whenever
AlfieBot talks, so it can't answer its own voice.
"""

import logging
from typing import Callable, List, Optional, Tuple

from alfiebot.conversation.engine import ConversationEngine, Reply
from alfiebot.conversation.intents import split_wake_phrase
from alfiebot.core.state_machine import StateMachine
from alfiebot.core.states import TALKING_STATES, Expression, RobotState, expression_for
from alfiebot.core.transcript import Transcript
from alfiebot.hardware.base import Platform
from alfiebot.speech.mic_gate import MicGate

log = logging.getLogger(__name__)

LISTENING_STATES = {RobotState.LISTENING, RobotState.SPELLING_SETUP}
ASLEEP_STATES = {RobotState.SLEEPING, RobotState.IDLE}
BUSY_STATES = {RobotState.THINKING, RobotState.SPEAKING}
NEXT_STATE = {
    "listen": RobotState.LISTENING,
    "spelling_setup": RobotState.SPELLING_SETUP,
    "idle": RobotState.IDLE,
    "sleep": RobotState.SLEEPING,
}


class AlfieBot:
    def __init__(self, config: dict, platform: Platform, conversation: ConversationEngine = None):
        self.config = config
        self.platform = platform
        self.name = config["robot"]["name"]
        timing = config["conversation"]
        self.listen_timeout = float(timing["listen_timeout"])
        self.sleep_after_idle = float(timing["sleep_after_idle"])
        self.thinking_time = float(timing["thinking_time"])
        self.wake_delay = float(timing["wake_delay"])

        self.state_machine = StateMachine(RobotState.SLEEPING)
        self.conversation = conversation or ConversationEngine(self.name)
        self.transcript = Transcript()
        self.mic_gate = MicGate()
        self.running = False
        # Developer override: show an expression regardless of state.
        self.expression_override = None
        self.listen_time_left = 0.0
        self._speaking_mood = Expression.HAPPY
        self._current_reply: Optional[Reply] = None
        self._held_text: Optional[Tuple[str, str]] = None
        self._timers: List[Tuple[float, Callable[[], None]]] = []
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
        if self.expression_override:
            return self.expression_override
        if self.state == RobotState.SPEAKING:
            return self._speaking_mood
        return expression_for(self.state)

    @property
    def talking(self) -> bool:
        return self.state in TALKING_STATES

    def _notify_face(self) -> None:
        for listener in self._face_listeners:
            listener(self.expression, self.talking)

    def _on_state_change(self, old: RobotState, new: RobotState) -> None:
        self.mic_gate.set_speaking(new in TALKING_STATES)
        if new in LISTENING_STATES:
            self.listen_time_left = self.listen_timeout
        if new in ASLEEP_STATES:
            self.conversation.reset()
        self._notify_face()

    def set_state(self, state: RobotState) -> None:
        """Developer panel: jump straight to a state."""
        self.expression_override = None
        self._timers.clear()
        self._current_reply = None
        if self.state == RobotState.SPEAKING:
            self.platform.tts.stop()
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
        self._held_text = None
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
        if self.state in BUSY_STATES or self._timers:
            # Answer it once AlfieBot has finished talking.
            self._held_text = (text, source)
            log.info("Holding %r until %s has finished talking", text, self.name)
            return
        self.transcript.add("user", text, source)
        woke, rest = split_wake_phrase(text)

        if self.state in ASLEEP_STATES:
            if not woke:
                log.info("Not listening: say \"Hey %s\" or press the button first", self.name)
                self.transcript.add("system", f"{self.name} is not listening. "
                                    f"Start with \"Hey {self.name}\" or press the button.")
                return
            self._wake(rest)
        elif woke and not rest:
            self._say(self.conversation.acknowledge("wake_again"))
        else:
            self._think_then_reply(rest if woke else text)

    def press_button(self) -> None:
        """The robot's button: wake up, skip the current speech, or keep listening."""
        if not self.running:
            self.start()
        if self.state in ASLEEP_STATES:
            self._wake("", by_button=True)
        elif self.state == RobotState.SPEAKING:
            log.info("Button: stop talking and listen")
            self.platform.tts.stop()
            self._finish_speaking(force_listen=True)
        elif self.state in LISTENING_STATES:
            self.listen_time_left = self.listen_timeout

    # ---- conversation flow ----------------------------------------------
    def _wake(self, rest: str, by_button: bool = False) -> None:
        log.info("Wake %s", "button pressed" if by_button else "phrase heard (typed)")

        def respond():
            if rest:
                self._think_then_reply(rest)
            elif by_button:
                self._say(self.conversation.acknowledge("button"))
            else:
                self._say(self.conversation.greet())

        if self.state == RobotState.SLEEPING:
            # Let the eyes open (and blink) before saying anything.
            self.state_machine.set_state(RobotState.IDLE)
            self._after(self.wake_delay, respond)
        else:
            respond()

    def _think_then_reply(self, text: str) -> None:
        self.state_machine.set_state(RobotState.THINKING)
        try:
            reply = self.conversation.respond(text)
        except Exception:
            log.exception("Conversation engine failed on %r", text)
            self._error()
            return
        self._after(self.thinking_time, lambda: self._say(reply))

    def _say(self, reply: Reply) -> None:
        self._current_reply = reply
        self._speaking_mood = reply.mood
        self.transcript.add("robot", reply.text)
        self.state_machine.set_state(RobotState.SPEAKING)
        self._notify_face()  # mood may differ even if already SPEAKING
        self.platform.tts.speak(reply.text)

    def _finish_speaking(self, force_listen: bool = False) -> None:
        reply = self._current_reply
        self._current_reply = None
        then = "listen" if force_listen or reply is None else reply.then
        self.state_machine.set_state(NEXT_STATE.get(then, RobotState.LISTENING))
        if self._held_text and self.state in LISTENING_STATES:
            text, source = self._held_text
            self._held_text = None
            self.handle_text(text, source)

    def _error(self) -> None:
        self._timers.clear()
        self.state_machine.set_state(RobotState.ERROR)
        reply = self.conversation.error_reply()
        self._after(1.5, lambda: self._say(reply))

    def _after(self, seconds: float, action: Callable[[], None]) -> None:
        self._timers.append((seconds, action))

    # ---- per-frame -------------------------------------------------------
    def update(self, dt: float) -> None:
        self.state_machine.update(dt)
        self.mic_gate.update(dt)
        self.platform.tts.update(dt)

        if self._timers:
            due, waiting = [], []
            for left, action in self._timers:
                left -= dt
                (due if left <= 0 else waiting).append((left, action))
            self._timers = waiting
            for _, action in due:
                action()

        state = self.state
        if state == RobotState.SPEAKING and not self.platform.tts.speaking and self._current_reply:
            self._finish_speaking()
        elif state in LISTENING_STATES:
            self.listen_time_left -= dt
            if self.listen_time_left <= 0:
                log.info("No answer for %.0f s; back to idle", self.listen_timeout)
                self.state_machine.set_state(RobotState.IDLE)
        elif (state == RobotState.IDLE and self.running and not self._timers
              and self.state_machine.time_in_state >= self.sleep_after_idle):
            log.info("Idle for %.0f s; going to sleep", self.sleep_after_idle)
            self.state_machine.set_state(RobotState.SLEEPING)

        button = self.platform.button
        if button.poll_pressed():
            log.info("Button pressed")
            self.press_button()
        if button.poll_released():
            log.debug("Button released")
