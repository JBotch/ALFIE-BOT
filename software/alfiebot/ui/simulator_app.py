"""Desktop simulator: the face in a 5-inch style viewport plus a developer
control panel. F11 shows the face alone, full screen."""

import logging
import time

import pygame

from alfiebot import __version__
from alfiebot.config import save_setting
from alfiebot.core.robot import AlfieBot
from alfiebot.core.states import Expression, RobotState
from alfiebot.ui import widgets as w
from alfiebot.ui.ai_panel import AIPanel
from alfiebot.ui.face_view import FaceView
from alfiebot.ui.letter_test_panel import LetterTestPanel
from alfiebot.ui.voice_panel import VoicePanel
from alfiebot.ui.log_capture import MemoryLogHandler
from alfiebot.ui.spelling_panel import SpellingPanel

log = logging.getLogger(__name__)

EXPRESSION_KEYS = {pygame.K_1 + i: e for i, e in enumerate(Expression)}
STATE_LABELS = {
    RobotState.SLEEPING: "SLEEPING", RobotState.IDLE: "IDLE",
    RobotState.LISTENING: "LISTENING", RobotState.THINKING: "THINKING",
    RobotState.SPEAKING: "SPEAKING", RobotState.SPELLING_SETUP: "SPELL SETUP",
    RobotState.SPELLING_PRACTICE: "PRACTICE", RobotState.SPELLING_TEST: "SPELL TEST",
    RobotState.CELEBRATING: "CELEBRATE", RobotState.ERROR: "ERROR",
}
QUICK_PHRASES = ("Hey AlfieBot", "I'm good", "How are you?", "Tell me a joke")


class SimulatorApp:
    def __init__(self, robot: AlfieBot, config: dict, log_handler: MemoryLogHandler):
        self.robot = robot
        self.config = config
        self.log_handler = log_handler
        sim = config["simulator"]
        self.window_size = (sim["window_width"], sim["window_height"])
        self.fps = config["display"]["fps"]
        self.store = robot.store
        self.face_fullscreen = False
        # Simulated speech: sent as typing (marked straight away) or as speech
        # (letters build up, like the microphone), with high or low confidence.
        self.sim_as_speech = False
        self.sim_low_confidence = False
        self._delete_armed_until = 0.0
        self._fps_shown = 0.0
        self.screen = None
        self.face = None
        self._build_layout()

    # ---- layout ----------------------------------------------------------
    def _build_layout(self):
        W, H = self.window_size
        self.bezel = pygame.Rect(12, 12, 800, 464)
        self.face_rect = self.bezel.inflate(-32, -32)
        half = (self.bezel.width - 8) // 2
        log_top = self.bezel.bottom + 12
        self.transcript_view = w.LogView((12, log_top, half, H - log_top - 12), "Conversation transcript")
        self.debug_view = w.LogView((20 + half, log_top, half, H - log_top - 12), "Debug log", size=15)

        x0 = self.bezel.right + 12
        pw = W - x0 - 12
        self.panel = pygame.Rect(x0, 12, pw, H - 24)
        px = x0 + 12
        inner = pw - 24
        self.px, self.inner = px, inner
        self.buttons = []

        def add(*args, **kwargs):
            b = w.Button(*args, **kwargs)
            self.buttons.append(b)
            return b

        y = 50
        self.start_btn = add((px, y, 96, 30), "Start", self.robot.start)
        self.stop_btn = add((px + 104, y, 96, 30), "Stop", self.robot.stop)
        self.y_status = y + 38

        # States, two rows of five.
        y = 140
        self.state_buttons = {}
        bw = (inner - 4 * 6) // 5
        for i, state in enumerate(RobotState):
            r, c = divmod(i, 5)
            self.state_buttons[state] = add(
                (px + c * (bw + 6), y + r * 32, bw, 27), STATE_LABELS[state],
                (lambda s=state: self.robot.set_state(s)), size=15)

        # Expression previews.
        y = 232
        self.expr_buttons = {}
        bw = (inner - 3 * 6) // 4
        for i, expr in enumerate(Expression):
            r, c = divmod(i, 4)
            self.expr_buttons[expr] = add(
                (px + c * (bw + 6), y + r * 32, bw, 27), f"{i + 1} {expr.value.title()}",
                (lambda e=expr: self.robot.show_expression(e)), size=16)
        self.follow_btn = add((px + 3 * (bw + 6), y + 32, bw, 27), "0 Follow state",
                              lambda: self.robot.show_expression(None), size=16)

        # Microphone and button.
        y = 300
        self.y_mic = y
        add((px + inner - 110, y - 3, 110, 22), "Voice", self._toggle_voice, size=15)
        self.mic_btn = add((px, y + 24, 130, 28), "Mic: on", self._toggle_mic, size=16)
        self.mode_btn = add((px + 136, y + 24, 140, 28), "Mode: open", self._toggle_mic_mode, size=16)
        self.ptt_btn = add((px + 282, y + 24, inner - 282, 28), "Button (Space)",
                           on_press=self._button_down, on_release=self._button_up, size=16)

        # Simulated speech.
        y = 412
        self.y_input = y
        self.text_input = w.TextInput((px, y + 22, inner - 82, 32), self._submit_text,
                                      "Type what you'd say, then Enter")
        self.as_btn = add((px + inner - 236, y - 3, 120, 22), "As: typing",
                          lambda: setattr(self, "sim_as_speech", not self.sim_as_speech), size=15)
        self.conf_btn = add((px + inner - 110, y - 3, 110, 22), "Conf: high",
                            lambda: setattr(self, "sim_low_confidence", not self.sim_low_confidence),
                            size=15)
        add((px + inner - 74, y + 22, 74, 32), "Send", self.text_input.submit)
        bw = (inner - 3 * 6) // 4
        for i, phrase in enumerate(QUICK_PHRASES):
            add((px + i * (bw + 6), y + 62, bw, 26), phrase,
                (lambda p=phrase: self._submit_text(p)), size=15)

        # Spelling homework.
        y = 508
        self.y_spelling = y
        bw = (inner - 3 * 6) // 4
        for i, (label, action) in enumerate((
                ("Lists", self._toggle_lists),
                ("Add by voice", lambda: self.robot.start_spelling("add")),
                ("Practise", lambda: self.robot.start_spelling("practice")),
                ("Test", lambda: self.robot.start_spelling("test")))):
            add((px + i * (bw + 6), y + 48, bw, 27), label, action, size=16)
        self.spelling = SpellingPanel(self.robot, (12, 12, self.bezel.width, H - 24))
        self.letter_test = LetterTestPanel(self.robot, (12, 12, self.bezel.width, H - 24))
        self.voice = VoicePanel(self.robot, self.config, (12, 12, self.bezel.width, H - 24))
        self.ai = AIPanel(self.robot, self.config, (12, 12, self.bezel.width, H - 24))
        self.ai_btn = add((px + 170, 18, 84, 24), "AI brain", self._toggle_ai, size=15)
        self.speaker_btn = add((px + 260, 18, 96, 24), "Speaker: on",
                               lambda: self.robot.set_voice_output(not self.robot.voice_output), size=15)
        add((px + inner - 110, y - 3, 110, 22), "Letter test", self._toggle_letter_test, size=15)

        # Parent area.
        y = 594
        self.y_parent = y
        bw = (inner - 12) // 3
        self.allow_mic_btn = add((px, y + 46, bw, 28), "Allow mic: no", self._toggle_allow_mic, size=16)
        self.delete_btn = add((px + bw + 6, y + 46, bw, 28), "Reset all data", self._delete_data, size=16)
        add((px + 2 * (bw + 6), y + 46, bw, 28), "Full-screen face",
            self._toggle_face_fullscreen, size=16)

    # ---- actions ---------------------------------------------------------
    def _submit_text(self, text):
        if not self.sim_as_speech:
            self.robot.handle_text(text, "typed")
            return
        confidence = 0.5 if self.sim_low_confidence else 0.95
        words = [(word, confidence) for word in text.lower().split()]
        self.robot.handle_text(text, "simulated", confidence, words)

    def _close_overlays(self):
        self.spelling.open = self.voice.open = self.ai.open = False
        if self.letter_test.open:
            self.letter_test.toggle()

    def _toggle_ai(self):
        was_open = self.ai.open
        self._close_overlays()
        self.ai.open = not was_open

    def _toggle_letter_test(self):
        self.spelling.open = self.voice.open = self.ai.open = False
        self.letter_test.toggle()

    def _toggle_lists(self):
        self.voice.open = self.ai.open = False
        if self.letter_test.open:
            self.letter_test.toggle()
        self.spelling.toggle("lists")

    def _toggle_voice(self):
        self.spelling.open = self.ai.open = False
        if self.letter_test.open:
            self.letter_test.toggle()
        self.voice.toggle()

    def _toggle_mic(self):
        rec = self.robot.platform.recognizer
        if not self.robot.mic_allowed_by_parent:
            log.warning("The microphone isn't allowed. A parent can click 'Allow mic' below.")
            return
        if not rec.available:
            log.warning("Microphone unavailable: %s", rec.unavailable_reason)
            return
        self.robot.mic_switch = not self.robot.mic_switch

    def _toggle_mic_mode(self):
        self.robot.mic_mode = "push_to_talk" if self.robot.mic_mode == "open" else "open"
        save_setting(self.config, "speech", "mic_mode", self.robot.mic_mode)

    def _toggle_allow_mic(self):
        allowed = not self.robot.mic_allowed_by_parent
        save_setting(self.config, "privacy", "microphone_enabled", allowed)
        log.info("Parent setting: microphone %s", "allowed" if allowed else "not allowed")

    def _button_down(self):
        self.robot.platform.button.press()

    def _button_up(self):
        self.robot.platform.button.release()

    def _delete_data(self):
        now = time.monotonic()
        if now > self._delete_armed_until:
            self._delete_armed_until = now + 4.0
            log.warning("Click 'Reset all data' again within 4 s to delete %s and reset the simulation",
                        self.store.base_dir)
            return
        self._delete_armed_until = 0.0
        robot = self.robot
        self.store.delete_all()
        robot.tutor.stop()
        robot.progress.reload()
        robot.transcript.clear()
        robot.conversation.reset()
        robot.brain.performance.reset()
        robot.brain.last = None
        log.info("Simulation reset: spelling lists, progress, transcript and AI statistics cleared")

    def _toggle_face_fullscreen(self):
        self.face_fullscreen = not self.face_fullscreen
        if self.face_fullscreen:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode(self.window_size)
        log.info("Face full screen %s", "on (F11 or Esc to return)" if self.face_fullscreen else "off")

    # ---- main loop -------------------------------------------------------
    def run(self, max_frames: int = None) -> int:
        pygame.display.set_caption(f"AlfieBot simulator v{__version__}")
        self.screen = pygame.display.set_mode(self.window_size)
        pygame.key.stop_text_input()
        self.face = FaceView(self.robot, self.config)
        log.info("Simulator ready. Press Start (or the Space bar) to wake %s.", self.robot.name)
        clock = pygame.time.Clock()
        frames = 0
        running = True
        while running:
            dt = clock.tick(self.fps) / 1000.0
            if dt > 0:
                self._fps_shown += (1.0 / dt - self._fps_shown) * 0.05
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                else:
                    self._handle(event)
            self.robot.update(dt)
            self.letter_test.update(dt)
            self.voice.update(dt)
            self.face.update(dt)
            if self.face_fullscreen:
                self.face.draw(self.screen)
            else:
                self._draw(dt)
            pygame.display.flip()
            frames += 1
            if max_frames and frames >= max_frames:
                break
        return 0

    def _handle(self, event):
        if self.face_fullscreen:
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_F11):
                self._toggle_face_fullscreen()
            elif event.type == pygame.KEYDOWN and event.key in EXPRESSION_KEYS:
                self.robot.show_expression(EXPRESSION_KEYS[event.key])
            return
        if self.text_input.handle(event):
            self.spelling.input.focused = False
            return
        if self.letter_test.handle(event) or self.voice.handle(event) or self.ai.handle(event):
            return
        if self.spelling.handle(event):
            if self.spelling.input.focused and self.text_input.focused:
                self.text_input.focused = False
            return
        for view in (self.transcript_view, self.debug_view):
            if view.handle(event):
                return
        for b in self.buttons:
            if b.handle(event):
                return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F11:
                self._toggle_face_fullscreen()
            elif event.key in EXPRESSION_KEYS:
                self.robot.show_expression(EXPRESSION_KEYS[event.key])
            elif event.key == pygame.K_0:
                self.robot.show_expression(None)
            elif event.key == pygame.K_SPACE:
                self._button_down()
            elif event.key in (pygame.K_RETURN, pygame.K_t):
                self.text_input.focused = True
                pygame.key.start_text_input()
        elif event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
            self._button_up()

    # ---- drawing ---------------------------------------------------------
    def _draw(self, dt):
        s = self.screen
        s.fill(w.BG)
        mouse = pygame.mouse.get_pos()

        # Robot bezel around the 5-inch screen.
        pygame.draw.rect(s, (232, 234, 238), self.bezel, border_radius=26)
        pygame.draw.rect(s, (12, 14, 18), self.bezel.inflate(-14, -14), border_radius=20)
        self.face.draw(s, self.face_rect)

        self._draw_transcript()
        self._draw_debug()
        self._draw_panel(mouse, dt)
        self.spelling.draw(s, mouse, dt)
        self.letter_test.draw(s, mouse, dt)
        self.voice.draw(s, mouse, dt)
        self.ai.draw(s, mouse, dt)

    def _draw_transcript(self):
        colours = {"user": w.TEXT, "robot": w.ACCENT, "system": w.TEXT_DIM}
        names = {"user": "You", "robot": self.robot.name, "system": "Note"}
        lines = [(colours[e.speaker], f"{names[e.speaker]}: {e.text}")
                 for e in self.robot.transcript.entries]
        if not lines:
            lines = [(w.TEXT_DIM, "Nothing said yet. Typed and spoken lines appear here. "
                                  "The transcript is kept in memory only.")]
        self.transcript_view.draw(self.screen, lines)

    def _draw_debug(self):
        colour = {logging.DEBUG: w.TEXT_DIM, logging.INFO: w.TEXT,
                  logging.WARNING: w.WARN, logging.ERROR: w.BAD, logging.CRITICAL: w.BAD}
        lines = [(colour.get(level, w.TEXT), text) for level, text in self.log_handler.records]
        self.debug_view.draw(self.screen, lines)

    def _section(self, y, title):
        w.draw_text(self.screen, title, (self.px, y), w.ACCENT, 19)

    def _mic_status(self):
        robot = self.robot
        rec = robot.platform.recognizer
        if rec.listening:
            return w.BAD, "ON - listening"
        if not robot.mic_allowed_by_parent:
            return w.TEXT_DIM, "Off (not allowed by parent)"
        if not rec.available:
            return w.TEXT_DIM, "Off: " + (rec.unavailable_reason or "unavailable")
        if not robot.mic_switch:
            return w.TEXT_DIM, "Off (switched off)"
        if robot.talking or not robot.mic_gate.mic_allowed:
            return w.WARN, "Muted while AlfieBot talks"
        if robot.mic_mode == "push_to_talk":
            return w.TEXT_DIM, "Off. Hold the button to talk"
        return w.TEXT_DIM, "Off. Opens when AlfieBot listens"

    def _draw_panel(self, mouse, dt):
        s = self.screen
        robot = self.robot
        pygame.draw.rect(s, w.PANEL, self.panel, border_radius=8)
        px, inner = self.px, self.inner
        w.draw_text(s, "Developer panel", (px, 20), w.TEXT, 24)
        w.draw_text(s, f"{self._fps_shown:4.0f} fps", (self.panel.right - 70, 24), w.TEXT_DIM, 16)

        # Run status.
        running = robot.running
        colour = w.GOOD if running else w.TEXT_DIM
        self.start_btn.enabled = not running
        self.stop_btn.enabled = running
        pygame.draw.circle(s, colour, (px + 222, 65), 7)
        w.draw_text(s, "Running" if running else "Stopped (asleep)", (px + 236, 57), colour, 19)
        state_text = f"State: {robot.state.value}"
        if robot.state.value in ("LISTENING", "SPELLING_SETUP"):
            state_text += f" ({max(0, robot.listen_time_left):.0f}s)"
        w.draw_text(s, state_text, (px, self.y_status), w.TEXT, 20)
        face_text = robot.expression.value
        if robot.expression_override:
            face_text += " (preview)"
        if robot.talking:
            face_text += ", talking"
        face_img = w.font(20).render(f"Face: {face_text}", True, w.TEXT)
        s.blit(face_img, (self.panel.right - 12 - face_img.get_width(), self.y_status))
        w.draw_text(s, "Set state (drives the face)", (px, 120), w.ACCENT, 18)
        for state, b in self.state_buttons.items():
            b.selected = state == robot.state
        w.draw_text(s, "Preview expression (keys 1-7)", (px, 212), w.ACCENT, 18)
        for expr, b in self.expr_buttons.items():
            b.selected = robot.expression_override == expr
        self.follow_btn.selected = robot.expression_override is None

        # Microphone status: always visible so it's clear when it's listening.
        self._section(self.y_mic, "Microphone")
        dot, text = self._mic_status()
        pygame.draw.circle(s, dot, (px + 112, self.y_mic + 9), 7)
        w.draw_text(s, text, (px + 126, self.y_mic + 1), w.TEXT, 18, max_width=inner - 126)
        rec = robot.platform.recognizer
        self.mic_btn.label = "Mic: on" if robot.mic_switch else "Mic: off"
        self.mic_btn.enabled = robot.mic_allowed_by_parent and rec.available
        self.mode_btn.label = "Mode: open" if robot.mic_mode == "open" else "Mode: hold button"
        self.ptt_btn.selected = robot.platform.button.is_pressed
        # Level meter and what the recogniser is hearing right now.
        bar = pygame.Rect(px, self.y_mic + 60, 90, 10)
        pygame.draw.rect(s, w.WIDGET, bar, border_radius=4)
        level = getattr(rec, "level", 0.0) if rec.listening else 0.0
        if level > 0.01:
            fill = bar.copy()
            fill.width = max(4, int(bar.width * level))
            pygame.draw.rect(s, w.GOOD if level < 0.8 else w.WARN, fill, border_radius=4)
        partial = getattr(rec, "partial", "") if rec.listening else ""
        if partial:
            heard = f"Hearing: {partial}"
        elif robot.last_heard:
            heard = f"Heard: \"{robot.last_heard[0]}\" (confidence {robot.last_heard[1]:.2f})"
        else:
            heard = f"Voice: {robot.platform.tts.name}" + ("" if robot.voice_output else " (speaker off)")
        w.draw_text(s, heard, (px + 100, self.y_mic + 57), w.TEXT_DIM, 16, max_width=inner - 100)
        ww = robot.platform.wake_word
        mode = ("letters A-Z + spelling commands" if robot.recognition_mode == "letters"
                else "conversation")
        w.draw_text(s, f"Listening for: {mode}.  Wake word: "
                    + ("on" if ww.configured else "not yet (Stage 5)"),
                    (px, self.y_mic + 78), w.TEXT_DIM, 15, max_width=inner)

        self._section(self.y_input, "Simulated speech")
        self.as_btn.label = "As: speech" if self.sim_as_speech else "As: typing"
        self.as_btn.selected = self.sim_as_speech
        self.conf_btn.label = "Conf: low" if self.sim_low_confidence else "Conf: high"
        self.conf_btn.selected = self.sim_low_confidence
        self.conf_btn.enabled = self.sim_as_speech
        self.text_input.draw(s, dt)

        self._section(self.y_spelling, "Spelling homework")
        tutor = robot.tutor
        letters, hearing = robot.spelling_letters()
        if tutor.stage:
            shown = " ".join(l if ok else l + "?" for l, ok in letters) + (f" [{hearing}]" if hearing else "")
            stage = {"spelling": "Letters", "clarify": "Checking", "review": "Read back"}[tutor.stage]
            status = f"{tutor.status()}. {stage}: {shown or '-'}"
        elif tutor.active:
            status = tutor.status()
        else:
            count = len(robot.spelling_lists.load(tutor.active_week).words)
            status = f"List {tutor.active_week}: {count} word{'s' if count != 1 else ''}"
        w.draw_text(s, status, (px, self.y_spelling + 24), w.TEXT_DIM, 16, max_width=inner)

        self._section(self.y_parent, "Parent settings")
        w.draw_text(s, "Audio is never recorded or saved. Speech is recognised on this computer.",
                    (px, self.y_parent + 24), w.TEXT_DIM, 16, max_width=inner)
        self.allow_mic_btn.label = "Allow mic: yes" if robot.mic_allowed_by_parent else "Allow mic: no"
        self.allow_mic_btn.selected = robot.mic_allowed_by_parent
        armed = time.monotonic() < self._delete_armed_until
        self.delete_btn.label = "Click again to confirm" if armed else "Reset all data"
        self.ai_btn.selected = self.ai.open
        self.speaker_btn.label = "Speaker: on" if robot.voice_output else "Speaker: off"
        self.speaker_btn.selected = not robot.voice_output

        for b in self.buttons:
            b.draw(s, mouse)
        w.draw_text(s, "Space = robot button   T or Enter = type   1-7 faces   F11 full-screen face",
                    (px, self.panel.bottom - 22), w.TEXT_DIM, 15, max_width=inner)

