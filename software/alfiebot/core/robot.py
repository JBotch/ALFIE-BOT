"""The robot's brain, shared by the simulator and the Pi.

Conversation flow (Stage 2):

    SLEEPING/IDLE --"Hey AlfieBot" or button--> (eyes open) SPEAKING greeting
    SPEAKING --finished--> LISTENING --text--> THINKING --> SPEAKING --> LISTENING
    LISTENING --no answer for listen_timeout--> IDLE --sleep_after_idle--> SLEEPING

Spelling (Stage 3): "help me with my spellings" (or the panel) hands the
conversation to the spelling tutor until the activity ends. A correct answer
gets a short CELEBRATING bounce before AlfieBot speaks.

Text that arrives while AlfieBot is thinking or talking is held and handled
as soon as it is listening again.

AI (V1 Phase 2): replies come from the brain (core/brain.py). Most are
ready at once; an AI answer is worked out on a background thread while
AlfieBot stays THINKING, and the robot polls for it each frame.

Microphone (Stage 4): only open while AlfieBot is listening (or, in
push_to_talk mode, while the button is held), never while it is thinking,
talking or celebrating, and only if a parent has allowed it in the config.
The mic gate also keeps it shut for a moment after speech ends, so AlfieBot
can't hear its own voice.
"""

import logging
import random
from typing import Callable, List, Optional, Tuple

from alfiebot.conversation.engine import ConversationEngine, Reply
from alfiebot.conversation.intents import split_wake_phrase
from alfiebot.core.brain import Brain, PendingReply
from alfiebot.core.events import UserInput
from alfiebot.core.state_machine import StateMachine
from alfiebot.core.states import TALKING_STATES, Expression, RobotState, expression_for
from alfiebot.core.transcript import Transcript
from alfiebot.hardware.base import Platform
from alfiebot.speech.mic_gate import MicGate
from alfiebot.spelling.lists import SpellingLists
from alfiebot.spelling.progress import ProgressTracker
from alfiebot.spelling.tutor import SpellingTutor
from alfiebot.spelling.letter_input import heard_letters, letter_grammar
from alfiebot.speech.base import TextToSpeech
from alfiebot.speech.null import TranscriptOnlyTTS
from alfiebot.speech.sounds import personality_sounds
from alfiebot.speech.voice_profiles import get_personality, profile_for_reply
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
    def __init__(self, config: dict, platform: Platform, conversation: ConversationEngine = None,
                 brain: Brain = None):
        self.config = config
        self.platform = platform
        self.name = config["robot"]["name"]
        timing = config["conversation"]
        self.listen_timeout = float(timing["listen_timeout"])
        self.sleep_after_idle = float(timing["sleep_after_idle"])
        self.thinking_time = float(timing["thinking_time"])
        self.wake_delay = float(timing["wake_delay"])
        speech = config.get("speech", {})
        self.mic_mode = speech.get("mic_mode", "open")
        # "auto" picks a voice profile for each reply; or a fixed profile name.
        self.voice_profile = speech.get("voice_profile", "auto") or "auto"
        # Classic or Bubbly Bot: which profiles "auto" uses, cheers, sound effects.
        self.personality = speech.get("personality", "classic") or "classic"
        self.last_profile = "normal"
        self._rng = random.Random()
        self._last_cheer = ""
        # The panel's microphone switch; it only works if a parent allowed the mic.
        self.mic_switch = True

        self.state_machine = StateMachine(RobotState.SLEEPING)
        self.conversation = conversation or ConversationEngine(self.name)
        self.transcript = Transcript()
        self.mic_gate = MicGate()
        self.store = JsonStore(config["data_dir"])
        self.spelling_lists = SpellingLists(self.store)
        self.progress = ProgressTracker(self.store)
        spelling = config.get("spelling", {})
        self.tutor = SpellingTutor(self.spelling_lists, self.progress,
                                   min_confidence=speech.get("min_confidence", 0.75),
                                   confirm_spoken=spelling.get("confirm_spoken_answers", "always"),
                                   phonetic=spelling.get("phonetic_words", "child"))
        self.brain = brain or Brain(config, self.conversation, self.tutor)
        self._pending: Optional[PendingReply] = None
        # Developer panel: voice output off shows replies in the transcript only.
        self.voice_output = True
        self._silent_tts = TranscriptOnlyTTS()
        self.letter_grammar = letter_grammar(spelling.get("phonetic_words", "child"))
        self.finish_after_pause = float(spelling.get("finish_after_pause", 5.0))
        self._letters_quiet = 0.0  # seconds since the last spoken letter
        # The letter test tool borrows the microphone; the robot leaves it alone then.
        self.external_mic = False
        self.last_heard: Optional[Tuple[str, float]] = None  # for the developer panel
        self.running = False
        # Developer override: show an expression regardless of state.
        self.expression_override = None
        self.listen_time_left = 0.0
        self._speaking_mood = Expression.HAPPY
        self._current_reply: Optional[Reply] = None
        self._held_text: Optional[tuple] = None
        self._timers: List[Tuple[float, Callable[[], None]]] = []
        self._face_listeners = []
        # Validated face commands (look, blink...) for the face view to apply.
        self.face_commands: List = []
        self.state_machine.add_listener(self._on_state_change)

    @property
    def tts(self) -> TextToSpeech:
        return self.platform.tts if self.voice_output else self._silent_tts

    def set_voice_output(self, on: bool) -> None:
        if on != self.voice_output:
            self.tts.stop()
            self.voice_output = on
            log.info("Voice output %s", "on" if on else "off (transcript only)")

    def _cancel_pending(self) -> None:
        self.brain.cancel(self._pending)
        self._pending = None

    def close(self) -> None:
        self._cancel_pending()
        self.brain.close()

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

    @property
    def sound_effects_on(self) -> bool:
        return personality_sounds(self.personality, self.config)

    def play_sound(self, name: str) -> None:
        if self.sound_effects_on:
            self.platform.sounds.play(name)

    def _on_state_change(self, old: RobotState, new: RobotState) -> None:
        self.mic_gate.set_speaking(new in TALKING_STATES)
        if new == RobotState.CELEBRATING:
            self.play_sound("celebrate")
        elif new in LISTENING_STATES and old not in LISTENING_STATES and self.running:
            self.play_sound("listen")
        if new in LISTENING_STATES:
            self.listen_time_left = self.listen_timeout
        if new in ASLEEP_STATES:
            self._cancel_pending()
            self.conversation.reset()
            self.tutor.stop()
        self._notify_face()

    def set_state(self, state: RobotState) -> None:
        """Developer panel: jump straight to a state."""
        self.expression_override = None
        self._timers.clear()
        self._current_reply = None
        self._cancel_pending()
        if self.state == RobotState.SPEAKING:
            self.tts.stop()
        if not self.state_machine.set_state(state):
            self._notify_face()

    def face_command(self, kind: str, value=None, seconds: float = 2.5) -> bool:
        """Ask the face to look somewhere, blink, etc. (see face/controller.py).
        Returns False, and does nothing, if the command isn't allowed."""
        from alfiebot.face.controller import face_command

        try:
            self.face_commands.append(face_command(kind, value, seconds))
        except (ValueError, TypeError) as exc:
            log.warning("Face command refused: %s", exc)
            return False
        del self.face_commands[:-20]
        return True

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
    def handle_text(self, text: str, source: str = "typed", confidence: float = 1.0,
                    words=None) -> None:
        """Text from the keyboard (simulated speech) or a recogniser.

        ``confidence`` (0..1) and ``words`` ([(word, confidence)]) come from
        the recogniser; the spelling tutor asks about letters it wasn't sure of.
        """
        text = text.strip()
        if not text:
            return
        if not self.running:
            log.warning("Ignored %r: %s is stopped. Press Start first.", text, self.name)
            return
        if self.state in BUSY_STATES or self._timers or self._pending:
            # Answer it once AlfieBot has finished talking.
            self._held_text = (text, source, confidence, words)
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
            self._think_then_reply(rest if woke else text, source, confidence,
                                   None if woke else words)

    def press_button(self) -> None:
        """The robot's button: wake up, skip the current speech, or keep listening."""
        if not self.running:
            self.start()
        if self.state in ASLEEP_STATES:
            self._wake("", by_button=True)
        elif self.state == RobotState.SPEAKING:
            log.info("Button: stop talking and listen")
            self.tts.stop()
            self._finish_speaking(force_listen=True)
        elif self.state in LISTENING_STATES:
            self.listen_time_left = self.listen_timeout

    # ---- conversation flow ----------------------------------------------
    def start_spelling(self, mode: Optional[str]) -> None:
        """Developer panel: start "add", "practice", "test" or (None) the menu."""
        if not self.running:
            self.start()
        if self.state in BUSY_STATES:
            self.tts.stop()
        self._timers.clear()
        self._current_reply = None
        self._cancel_pending()
        reply = self.tutor.start(mode)
        if self.state == RobotState.SLEEPING:
            self.state_machine.set_state(RobotState.IDLE)
            self._after(self.wake_delay, lambda: self._say(reply))
        else:
            self._say(reply)

    def _wake(self, rest: str, by_button: bool = False, source: str = "typed",
              confidence: float = 1.0) -> None:
        log.info("Wake %s", "button pressed" if by_button else "phrase heard (typed)")
        self.play_sound("wake")

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

    def _think_then_reply(self, text: str, source: str = "typed", confidence: float = 1.0,
                          words=None) -> None:
        try:
            reply = self.brain.handle(UserInput(text, source, confidence, words))
        except Exception:
            log.exception("Failed to answer %r", text)
            self._error()
            return
        if isinstance(reply, PendingReply):
            # The AI is working on it in the background; update() collects it.
            self._pending = reply
            self.state_machine.set_state(RobotState.THINKING)
            return
        if reply is None:
            # Letters of a spelling: they build up in the tutor; keep listening.
            self._letters_quiet = 0.0
            self.listen_time_left = self.listen_timeout
            return
        self._reply(reply)

    def _reply(self, reply: Reply) -> None:
        self.state_machine.set_state(RobotState.THINKING)
        if reply.celebrate:
            def celebrate():
                self.state_machine.set_state(RobotState.CELEBRATING)
                self._after(CELEBRATE_SECONDS, lambda: self._say(reply))
            self._after(self.thinking_time * 0.5, celebrate)
        else:
            self._after(self.thinking_time, lambda: self._say(reply))

    def _collect_ai_reply(self) -> None:
        reply = self.brain.poll(self._pending)
        if reply is None:
            return
        self._pending = None
        # Think for at least thinking_time, however fast the answer came.
        wait = max(0.0, self.thinking_time - self.state_machine.time_in_state)
        if reply.celebrate:
            self._after(wait * 0.5, lambda: self._reply(reply))
        else:
            self._after(wait, lambda: self._say(reply))

    def _say(self, reply: Reply) -> None:
        reply = self._add_cheer(reply)
        self._current_reply = reply
        self._speaking_mood = reply.mood
        self.transcript.add("robot", reply.text)
        self.state_machine.set_state(RobotState.SPEAKING)
        self._notify_face()  # mood may differ even if already SPEAKING
        self.last_profile = self.profile_for(reply)
        self.tts.speak(reply.text, self.last_profile)

    def profile_for(self, reply: Reply) -> str:
        """The voice profile for a reply: fixed in the panel, or chosen by the
        personality from the kind of reply (normal, excited, teacher, sleepy)."""
        if self.voice_profile != "auto":
            return self.voice_profile
        role = profile_for_reply(reply, self.tutor.mode)
        return get_personality(self.personality).roles.get(role, role)

    def _add_cheer(self, reply: Reply) -> Reply:
        """Bubbly Bot sometimes starts a celebration with "Woohoo!" or "Yay!"."""
        cheers = [c for c in get_personality(self.personality).cheers if c != self._last_cheer]
        if (self.voice_profile == "auto" and cheers and reply.celebrate
                and profile_for_reply(reply, self.tutor.mode) == "excited" and self._rng.random() < 0.6):
            self._last_cheer = self._rng.choice(cheers)
            return Reply(f"{self._last_cheer} {reply.text}", reply.intent, reply.mood, reply.then,
                         reply.detail, reply.celebrate)
        return reply

    def _finish_speaking(self, force_listen: bool = False) -> None:
        reply = self._current_reply
        self._current_reply = None
        then = "listen" if force_listen or reply is None else reply.then
        self.state_machine.set_state(NEXT_STATE.get(then, RobotState.LISTENING))
        if self._held_text and self.state in LISTENING_STATES:
            held, self._held_text = self._held_text, None
            self.handle_text(*held)

    def _error(self) -> None:
        self._timers.clear()
        self.state_machine.set_state(RobotState.ERROR)
        reply = self.conversation.error_reply()
        self._after(1.5, lambda: self._say(reply))

    def _after(self, seconds: float, action: Callable[[], None]) -> None:
        self._timers.append((seconds, action))

    # ---- microphone --------------------------------------------------------
    @property
    def mic_allowed_by_parent(self) -> bool:
        return bool(self.config["privacy"]["microphone_enabled"])

    @property
    def mic_should_be_open(self) -> bool:
        rec = self.platform.recognizer
        if not (self.running and self.mic_switch and self.mic_allowed_by_parent and rec.available):
            return False
        if self.state not in LISTENING_STATES or self._timers or not self.mic_gate.mic_allowed:
            return False
        if self.mic_mode == "push_to_talk":
            return self.platform.button.is_pressed
        return True

    @property
    def recognition_mode(self) -> str:
        """"letters" while a spelling is being spoken, otherwise "conversation"."""
        return "letters" if self.tutor.stage is not None else "conversation"

    def spelling_letters(self):
        """For the developer panel (never the robot's face) while a child spells:
        ([(letter, sure)], letters still being heard)."""
        if self.tutor.stage is None:
            return [], ""
        rec = self.platform.recognizer
        partial = getattr(rec, "partial", "") if rec.listening and not self.external_mic else ""
        return self.tutor.answer.display(), heard_letters(partial).upper() if partial else ""

    def _update_microphone(self) -> None:
        if self.external_mic:
            return
        rec = self.platform.recognizer
        want = self.mic_should_be_open
        if want:
            rec.set_grammar(self.letter_grammar if self.recognition_mode == "letters" else None)
            if not rec.listening:
                rec.start_listening()
        elif rec.listening:
            # A push-to-talk release keeps what was said; anything else drops it.
            released = self.mic_mode == "push_to_talk" and self.state in LISTENING_STATES
            rec.stop_listening(finalise=released)
        if getattr(rec, "partial", "") and self.state in LISTENING_STATES:
            # Don't time out (or check the spelling) while the child is still talking.
            self.listen_time_left = max(self.listen_time_left, 3.0)
            self._letters_quiet = 0.0
        result = rec.poll()
        if result is not None:
            self.last_heard = (result.text, result.confidence)
            self.handle_text(result.text, "voice", result.confidence, result.words)
            if rec.listening and not self.mic_should_be_open:
                rec.stop_listening()  # AlfieBot is about to think and reply

    def _check_spelling_pause(self, dt: float) -> None:
        """A quiet spell after some letters: read them back, as if "finished"."""
        if not (self.tutor.collecting_letters and self.state in LISTENING_STATES
                and not self._timers and self.finish_after_pause > 0):
            self._letters_quiet = 0.0
            return
        self._letters_quiet += dt
        if self._letters_quiet >= self.finish_after_pause:
            self._letters_quiet = 0.0
            reply = self.tutor.finish_spoken_answer()
            if reply:
                self._reply(reply)

    # ---- per-frame -------------------------------------------------------
    def update(self, dt: float) -> None:
        self.state_machine.update(dt)
        self.mic_gate.update(dt)
        self.tts.update(dt)
        if self._pending is not None:
            self._collect_ai_reply()

        if self._timers:
            due, waiting = [], []
            for left, action in self._timers:
                left -= dt
                (due if left <= 0 else waiting).append((left, action))
            self._timers = waiting
            for _, action in due:
                action()

        state = self.state
        if state == RobotState.SPEAKING and self._current_reply and self.tts.speaking:
            # Safety net in case a speech engine never reports that it finished.
            limit = 8.0 + 0.15 * len(self._current_reply.text)
            if self.state_machine.time_in_state > limit:
                log.warning("Speech didn't finish after %.0f s; stopping it", limit)
                self.tts.stop()
        if state == RobotState.SPEAKING and not self.tts.speaking and self._current_reply:
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

        self._update_microphone()
        self._check_spelling_pause(dt)

        button = self.platform.button
        if button.poll_pressed():
            log.info("Button pressed")
            self.press_button()
        if button.poll_released():
            log.debug("Button released")
