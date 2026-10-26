"""Desktop simulator: the face in a 5-inch style viewport plus a developer
control panel. F11 shows the face alone, full screen."""

import logging
import time
from pathlib import Path

import pygame

from alfiebot import __version__
from alfiebot.core.robot import AlfieBot
from alfiebot.core.states import Expression, RobotState
from alfiebot.storage.json_store import JsonStore
from alfiebot.ui import widgets as w
from alfiebot.ui.face_view import FaceView
from alfiebot.ui.log_capture import MemoryLogHandler

log = logging.getLogger(__name__)

EXPRESSION_KEYS = {pygame.K_1 + i: e for i, e in enumerate(Expression)}
STATE_LABELS = {
    RobotState.SLEEPING: "SLEEPING", RobotState.IDLE: "IDLE",
    RobotState.LISTENING: "LISTENING", RobotState.THINKING: "THINKING",
    RobotState.SPEAKING: "SPEAKING", RobotState.SPELLING_SETUP: "SPELL SETUP",
    RobotState.SPELLING_PRACTICE: "PRACTICE", RobotState.SPELLING_TEST: "SPELL TEST",
    RobotState.CELEBRATING: "CELEBRATE", RobotState.ERROR: "ERROR",
}
EXAMPLE_LIST = Path(__file__).resolve().parents[2] / "examples" / "spelling_list_example.json"


class SimulatorApp:
    def __init__(self, robot: AlfieBot, config: dict, log_handler: MemoryLogHandler):
        self.robot = robot
        self.config = config
        self.log_handler = log_handler
        sim = config["simulator"]
        self.window_size = (sim["window_width"], sim["window_height"])
        self.fps = config["display"]["fps"]
        self.store = JsonStore(config["data_dir"])
        self.face_fullscreen = False
        self.mic_requested = False
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
        y = 330
        self.y_mic = y
        self.mic_btn = add((px, y + 24, 150, 28), "Microphone: off", self._toggle_mic, size=16)
        self.ptt_btn = add((px + 158, y + 24, 170, 28), "Hold to talk (Space)",
                           on_press=self._button_down, on_release=self._button_up, size=16)

        # Simulated speech.
        y = 412
        self.y_input = y
        self.text_input = w.TextInput((px, y + 22, inner - 82, 32), self._submit_text,
                                      "Type what you'd say, then Enter")
        add((px + inner - 74, y + 22, 74, 32), "Send", self.text_input.submit)

        # Spelling homework (Stage 3).
        y = 478
        self.y_spelling = y
        for i, label in enumerate(("Add words", "Practise", "Test")):
            add((px + i * 104, y + 48, 96, 27), label, enabled=False, size=16)

        # Parent area.
        y = 570
        self.y_parent = y
        self.delete_btn = add((px, y + 46, 170, 28), "Delete local data", self._delete_data, size=16)
        add((px + 178, y + 46, inner - 178, 28), "Face full screen (F11)",
            self._toggle_face_fullscreen, size=16)

    # ---- actions ---------------------------------------------------------
    def _submit_text(self, text):
        self.robot.handle_text(text, "typed")

    def _toggle_mic(self):
        rec = self.robot.platform.recognizer
        if not self.config["privacy"]["microphone_enabled"]:
            log.warning("Microphone is turned off in parent settings (privacy.microphone_enabled)")
            return
        if not rec.available:
            log.warning("Microphone unavailable: %s", rec.unavailable_reason)
            return
        self.mic_requested = not self.mic_requested

    def _button_down(self):
        self.robot.platform.button.press()

    def _button_up(self):
        self.robot.platform.button.release()

    def _delete_data(self):
        now = time.monotonic()
        if now > self._delete_armed_until:
            self._delete_armed_until = now + 4.0
            log.warning("Click 'Delete local data' again within 4 s to delete %s", self.store.base_dir)
            return
        self._delete_armed_until = 0.0
        self.store.delete_all()
        self.robot.transcript.clear()

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
        w.draw_text(s, f"State: {robot.state.value}", (px, self.y_status), w.TEXT, 20)
        face_text = robot.expression.value
        if robot.expression_override:
            face_text += " (preview)"
        if robot.talking:
            face_text += ", talking"
        w.draw_text(s, f"Face: {face_text}", (px + 200, self.y_status), w.TEXT, 20)
        w.draw_text(s, "Set state (drives the face)", (px, 120), w.ACCENT, 18)
        for state, b in self.state_buttons.items():
            b.selected = state == robot.state
        w.draw_text(s, "Preview expression (keys 1-7)", (px, 212), w.ACCENT, 18)
        for expr, b in self.expr_buttons.items():
            b.selected = robot.expression_override == expr
        self.follow_btn.selected = robot.expression_override is None

        # Microphone status: always visible so it's clear when it's listening.
        self._section(self.y_mic, "Microphone")
        rec = robot.platform.recognizer
        mic_on = self.mic_requested and rec.available and robot.mic_gate.mic_allowed
        if mic_on:
            dot, text = w.BAD, "LISTENING"
        elif not self.config["privacy"]["microphone_enabled"]:
            dot, text = w.TEXT_DIM, "Off (parent setting)"
        elif not rec.available:
            dot, text = w.TEXT_DIM, "Off (no recogniser yet)"
        else:
            dot, text = w.TEXT_DIM, "Off"
        pygame.draw.circle(s, dot, (px + 112, self.y_mic + 9), 7)
        w.draw_text(s, text, (px + 126, self.y_mic + 1), w.TEXT, 18)
        self.mic_btn.label = "Microphone: on" if self.mic_requested else "Microphone: off"
        self.ptt_btn.selected = robot.platform.button.is_pressed
        ww = robot.platform.wake_word
        w.draw_text(s, "Wake word: " + ("on" if ww.configured else "not configured (type \"Hey AlfieBot\")"),
                    (px + 0, self.y_mic + 58), w.TEXT_DIM, 15, max_width=inner)

        self._section(self.y_input, "Simulated speech")
        self.text_input.draw(s, dt)

        self._section(self.y_spelling, "Spelling homework")
        saved = self.store.list("spellings")
        example = self._example_summary()
        w.draw_text(s, f"Saved lists: {len(saved) if saved else 'none yet'}.  {example}",
                    (px, self.y_spelling + 24), w.TEXT_DIM, 16, max_width=inner)
        w.draw_text(s, "Stage 3", (px + 320, self.y_spelling + 54), w.TEXT_DIM, 16)

        self._section(self.y_parent, "Parent settings")
        privacy = self.config["privacy"]
        w.draw_text(s, "Mic allowed: {}   Audio kept: {}".format(
            "yes" if privacy["microphone_enabled"] else "no",
            "yes" if privacy["keep_audio_recordings"] else "never"),
            (px, self.y_parent + 24), w.TEXT_DIM, 16, max_width=inner)
        armed = time.monotonic() < self._delete_armed_until
        self.delete_btn.label = "Click again to confirm" if armed else "Delete local data"

        for b in self.buttons:
            b.draw(s, mouse)
        w.draw_text(s, "Space = robot button   T = type   1-7 faces   F11 full-screen face",
                    (px, self.panel.bottom - 22), w.TEXT_DIM, 15, max_width=inner)

    _example_cache = None

    def _example_summary(self):
        if self._example_cache is None:
            data = JsonStore(EXAMPLE_LIST.parent).load(EXAMPLE_LIST.stem, {})
            words = data.get("words", [])
            self._example_cache = f"Example list: {len(words)} words." if words else ""
        return self._example_cache
