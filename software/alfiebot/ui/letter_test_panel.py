"""Letter recognition test, inside the simulator.

Shows a letter, listens for it with the spelling grammar, and records what
was heard (see ``alfiebot.speech.letter_test``). While a test runs the robot
leaves the microphone alone. Without a microphone, type what was "heard"
to try the tool out.
"""

import logging
import time

import pygame

from alfiebot.spelling.letter_input import CHILD_WORDS
from alfiebot.speech.letter_test import (LETTER_SETS, SPEEDS, LetterTestSession, format_report,
                                         load_trials)
from alfiebot.ui import widgets as w

log = logging.getLogger(__name__)

SET_ORDER = ("all", "confusing", "pairs", "B/D/P", "C/G/T", "M/N", "F/S", "A/H/J", "O/R")
TIMEOUT = 8.0


class LetterTestPanel:
    def __init__(self, robot, rect):
        self.robot = robot
        self.rect = pygame.Rect(rect)
        self.open = False
        self.letter_set = "all"
        self.speed = "normal"
        self.session = None
        self.report = ""
        self.message = ""
        self.last = ""
        self._hits = []
        self._waited = 0.0
        self._speech_start = None
        self.speaker = w.TextInput((0, 0, 200, 30), lambda _: None, "Speaker, e.g. Alfie")
        self.typed = w.TextInput((0, 0, 300, 30), self._typed, "No mic? Type what was heard, Enter")

    # ---- microphone ----------------------------------------------------------
    @property
    def rec(self):
        return self.robot.platform.recognizer

    @property
    def using_mic(self) -> bool:
        return self.robot.mic_allowed_by_parent and self.rec.available

    def toggle(self):
        self.open = not self.open
        if not self.open:
            self.stop()

    def start(self):
        self.session = LetterTestSession(self.letter_set, 1, self.speaker.text, self.speed,
                                         self.robot.tutor.min_confidence)
        self.report = ""
        self.last = ""
        self._waited = 0.0
        self._speech_start = None
        if self.using_mic:
            self.robot.external_mic = True
            if self.rec.listening:
                self.rec.stop_listening()
            self.rec.set_grammar(self.robot.letter_grammar)
            self.rec.start_listening()
            self.message = "Say each letter as it appears."
        elif not self.robot.mic_allowed_by_parent:
            self.message = "The mic isn't allowed (Parent settings), so type what was heard."
        else:
            self.message = f"No microphone ({self.rec.unavailable_reason}). Type what was heard."
        log.info("Letter test started: %d letters", len(self.session.prompts))

    def stop(self):
        if self.robot.external_mic:
            self.rec.stop_listening()
            self.robot.external_mic = False
        if self.session and self.session.trials:
            name = self.session.save(self.robot.store)
            self.report = format_report(self.session.trials)
            self.message = f"Saved to data/{name}"
            log.info("Letter test saved to %s", name)
        self.session = None

    def _record(self, text, words, confidence, latency):
        outcome = self.session.record(text, words, confidence, latency)
        scores = ", ".join(f"{word} {c:.2f}" for word, c in words) if words else f"{confidence:.2f}"
        self.last = f"Heard \"{text}\" ({scores}, {latency:.2f} s)"
        if outcome == "clarify":
            self.last += ": not sure, say it again"
        elif self.session.trials[-1].correct:
            self.last += ": right"
        else:
            self.last += f": wrong ({self.session.trials[-1].final.upper() or 'nothing'})"
        self._waited = 0.0
        self._speech_start = None
        if outcome == "done":
            self.stop()

    def _typed(self, text):
        if self.session and not self.session.done:
            self._record(text, None, 1.0, 0.0)

    def update(self, dt):
        if not (self.session and self.robot.external_mic):
            return
        rec = self.rec
        if self._speech_start is None and (getattr(rec, "partial", "") or getattr(rec, "level", 0) > 0.08):
            self._speech_start = time.monotonic()
        result = rec.poll()
        if result:
            latency = time.monotonic() - (self._speech_start or time.monotonic())
            self._record(result.text, result.words, result.confidence, latency)
            return
        self._waited += dt
        if self._waited > TIMEOUT:
            self._waited = 0.0
            self.last = "Nothing heard"
            if self.session.nothing_heard() == "done":
                self.stop()

    # ---- events ----------------------------------------------------------------
    def handle(self, event) -> bool:
        if not self.open:
            return False
        if self.speaker.handle(event) or self.typed.handle(event):
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, action in self._hits:
                if rect.collidepoint(event.pos):
                    action()
                    return True
            return self.rect.collidepoint(event.pos)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.toggle()
            return True
        return False

    # ---- drawing ---------------------------------------------------------------
    def _button(self, s, rect, label, action, mouse, selected=False, size=16):
        rect = pygame.Rect(rect)
        colour = w.WIDGET_ACTIVE if selected else (w.WIDGET_HOVER if rect.collidepoint(mouse) else w.WIDGET)
        pygame.draw.rect(s, colour, rect, border_radius=6)
        img = w.font(size).render(label, True, w.TEXT)
        s.blit(img, img.get_rect(center=rect.center))
        self._hits.append((rect, action))

    def draw(self, s, mouse, dt):
        if not self.open:
            return
        self._hits = []
        r = self.rect
        pygame.draw.rect(s, w.PANEL, r, border_radius=10)
        pygame.draw.rect(s, w.ACCENT, r, 1, border_radius=10)
        x, right, y = r.x + 16, r.right - 16, r.y + 14
        w.draw_text(s, "Letter recognition test", (x, y), w.TEXT, 26)
        self._button(s, (right - 80, y - 2, 80, 28), "Close", self.toggle, mouse)
        y += 40
        running = self.session is not None
        if not running:
            w.draw_text(s, "Speaker", (x, y + 7), w.TEXT_DIM, 17)
            self.speaker.rect = pygame.Rect(x + 70, y, 180, 30)
            self.speaker.draw(s, dt)
            for i, speed in enumerate(SPEEDS):
                self._button(s, (x + 270 + i * 82, y + 1, 76, 28), speed.title(),
                             lambda sp=speed: setattr(self, "speed", sp), mouse, self.speed == speed)
            y += 40
            bx = x
            for name in SET_ORDER:
                label = name if "/" in name else name.title()
                width = w.font(16).size(label)[0] + 20
                self._button(s, (bx, y, width, 28), label,
                             lambda n=name: setattr(self, "letter_set", n), mouse, self.letter_set == name)
                bx += width + 6
            y += 38
            count = len(LETTER_SETS[self.letter_set])
            self._button(s, (x, y, 200, 32), f"Start ({count} letters)", self.start, mouse, size=18)
            self._button(s, (x + 210, y, 210, 32), "Report of all tests",
                         lambda: setattr(self, "report", format_report(load_trials(self.robot.store))),
                         mouse, size=18)
            y += 44
            if self.message:
                w.draw_text(s, self.message, (x, y), w.TEXT_DIM, 17, max_width=right - x)
                y += 24
            for line in (self.report or "Say each letter that appears. Results are saved in "
                         "data/letter_tests (never audio). Try the mix-up sets (B/D/P...) "
                         "with different speakers and speeds.").split("\n"):
                for part in w.wrap_text(line, right - x, 17):
                    if y > r.bottom - 24:
                        break
                    w.draw_text(s, part, (x, y), w.TEXT, 17)
                    y += 19
            return

        session = self.session
        letter = session.current or ""
        w.draw_text(s, f"Letter {session.index + 1} of {len(session.prompts)}   "
                       f"speaker {session.speaker}, {session.speed}", (x, y), w.TEXT_DIM, 18)
        y += 26
        big = w.font(150).render(letter.upper(), True, w.WARN if session.clarifying else w.ACCENT)
        s.blit(big, big.get_rect(midtop=(r.centerx, y)))
        y += 120
        hint = (f"Not sure, say it again (like \"{letter.upper()} for {CHILD_WORDS.get(letter, '')}\")"
                if session.clarifying else "Say this letter")
        img = w.font(22).render(hint, True, w.TEXT)
        s.blit(img, img.get_rect(midtop=(r.centerx, y)))
        y += 34
        rec = self.rec
        partial = getattr(rec, "partial", "") if rec.listening else ""
        w.draw_text(s, f"Hearing: {partial}" if partial else (self.last or self.message),
                    (x, y), w.TEXT_DIM, 18, max_width=right - x)
        y += 30
        if not self.robot.external_mic:
            self.typed.rect = pygame.Rect(x, y, right - x, 30)
            self.typed.draw(s, dt)
            y += 40
        right_first = sum(t.correct for t in session.trials)
        w.draw_text(s, f"So far: {right_first}/{len(session.trials)} right", (x, y), w.TEXT, 18)
        y += 26
        recent = [f"{t.expected.upper()}->{(t.final or '-').upper()}{'?' if t.clarification_required else ''}"
                  for t in session.trials[-14:]]
        w.draw_text(s, "  ".join(recent), (x, y), w.TEXT_DIM, 17, max_width=right - x)
        self._button(s, (x, r.bottom - 44, 200, 30), "Stop and show report", self.stop, mouse)
