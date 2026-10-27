"""The robot's brain, shared by the simulator and the Pi.

Conversation flow (Stage 2):

    SLEEPING/IDLE --"Hey AlfieBot" or button--> (eyes open) SPEAKING greeting
    SPEAKING --finished--> LISTENING --text--> THINKING --> SPEAKING --> LISTENING
    LISTENING --no answer for listen_timeout--> IDLE --sleep_after_idle--> SLEEPING

Spelling (Stage 3): "help me with my spellings" (or the panel) hands the
conversation to the spelling tutor until the activity ends. A correct answer
gets a short CELEBRATING bounce before AlfieBot speaks.

Text that arrives while AlfieBot is thinking or talking is held and handled
as soon as it is listening again. The microphone gate is closed whenever
AlfieBot talks, so it can't answer its own voice.
"""

import logging
from typing import Callable, List, Optional, Tuple

from alfiebot.conversation.engine import ConversationEngine, Reply
from alfiebot.conversation.intents import normalise, split_wake_phrase
from alfiebot.core.state_machine import StateMachine
from alfiebot.core.states import TALKING_STATES, Expression, RobotState, expression_for
from alfiebot.core.transcript import Transcript
from alfiebot.hardware.base import Platform
from alfiebot.speech.mic_gate import MicGate
from alfiebot.spelling.lists import SpellingLists
from alfiebot.spelling.progress import ProgressTracker
from alfiebot.spelling.tutor import CHOICES, SpellingTutor
from alfiebot.storage.json_store import JsonStore

log = logging.getLogger(__name__)

LISTENING_STATES = {RobotState.LISTENING, RobotState.SPELLING_SETUP,
                    RobotState.SPELLING_PRACTICE, RobotState.SPELLING_TEST}
ASLEEP_STATES = {RobotState.SLEEPING, RobotState.IDLE}
BUSY_STATES = {RobotState.THINKING, RobotState.SPEAKING, RobotState.CELEBRATING, RobotState.ERROR}
CELEBRATE_SECONDS = 1.3
NEXT_STATE = {
    "listen": RobotState.LISTENING,
    "spelling_setup": RobotState.SPELLING_SETUP,
    "spelling_practice": RobotState.SPELLING_PRACTICE,
    "spelling_test": RobotState.SPELLING_TEST,
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
        self.store = JsonStore(config["data_dir"])
        self.spelling_lists = SpellingLists(self.store)
        self.progress = ProgressTracker(self.store)
        self.tutor = SpellingTutor(self.spelling_lists, self.progress)
        self.running = False
        # Developer override: show an expression regardless of state.
        self.expression_override = None
        self.listen_time_left = 0.0
        self._speaking_mood = Expression.HAPPY
        self._current_reply: Optional[Reply] = None
        self._held_text: Optional[Tuple[str, str, float]] = None
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
            self.tutor.stop()
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
    def handle_text(self, text: str, source: str = "typed", confidence: float = 1.0) -> None:
        """Text from the keyboard (simulated speech) or a recogniser.

        ``confidence`` (0..1) comes from the recogniser; the spelling tutor
        double-checks answers it wasn't sure about.
        """
        text = text.strip()
        if not text:
            return
        if not self.running:
            log.warning("Ignored %r: %s is stopped. Press Start first.", text, self.name)
            return
        if self.state in BUSY_STATES or self._timers:
            # Answer it once AlfieBot has finished talking.
            self._held_text = (text, source, confidence)
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
            self._wake(rest, source=source, confidence=confidence)
        elif woke and not rest:
            self._say(self.conversation.acknowledge("wake_again"))
        else:
            self._think_then_reply(rest if woke else text, source, confidence)

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
    def start_spelling(self, mode: Optional[str]) -> None:
        """Developer panel: start "add", "practice", "test" or (None) the menu."""
        if not self.running:
            self.start()
        if self.state in BUSY_STATES:
            self.platform.tts.stop()
        self._timers.clear()
        self._current_reply = None
        reply = self.tutor.start(mode)
        if self.state == RobotState.SLEEPING:
            self.state_machine.set_state(RobotState.IDLE)
            self._after(self.wake_delay, lambda: self._say(reply))
        else:
            self._say(reply)

    def _wake(self, rest: str, by_button: bool = False, source: str = "typed",
              confidence: float = 1.0) -> None:
        log.info("Wake %s", "button pressed" if by_button else "phrase heard (typed)")

        def respond():
            if rest:
                self._think_then_reply(rest, source, confidence)
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

    def _think_then_reply(self, text: str, source: str = "typed", confidence: float = 1.0) -> None:
        self.state_machine.set_state(RobotState.THINKING)
        try:
            reply = self._reply_to(text, source, confidence)
        except Exception:
            log.exception("Failed to answer %r", text)
            self._error()
            return
        if reply.celebrate:
            def celebrate():
                self.state_machine.set_state(RobotState.CELEBRATING)
                self._after(CELEBRATE_SECONDS, lambda: self._say(reply))
            self._after(self.thinking_time * 0.5, celebrate)
        else:
            self._after(self.thinking_time, lambda: self._say(reply))

    def _reply_to(self, text: str, source: str, confidence: float) -> Reply:
        if self.tutor.active:
            reply = self.tutor.handle(text, source, confidence)
            if not self.tutor.active:
                self.conversation.reset()
            return reply
        reply = self.conversation.respond(text)
        if reply.intent in ("spelling_help", "spelling_choice"):
            norm = normalise(text)
            choice = reply.detail or next((c for c, p in CHOICES if p.search(norm)), None)
            if choice:
                return self.tutor.start(choice, text)
            self.tutor.start(None)  # menu; keep the conversation's wording
            reply.then = "spelling_setup"
        return reply

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
            text, source, confidence = self._held_text
            self._held_text = None
            self.handle_text(text, source, confidence)

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
