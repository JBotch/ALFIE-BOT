"""Spelling homework manager: weekly lists and progress.

Shown over the left half of the simulator. Typed words are checked
before saving: they appear as chips, a click on one moves it back into the
box to fix it, and only "Save" writes them to the list.
"""

import json
import logging
import time
from pathlib import Path

import pygame

from alfiebot.spelling.lists import week_id, week_label
from alfiebot.spelling.words import parse_word_list
from alfiebot.ui import widgets as w

log = logging.getLogger(__name__)

EXAMPLE_LIST = Path(__file__).resolve().parents[2] / "examples" / "spelling_list_example.json"
GOOD_CHIP = (36, 92, 70)
BAD_CHIP = (110, 45, 45)
WORD_CHIP = (48, 62, 84)


class SpellingPanel:
    def __init__(self, robot, rect):
        self.robot = robot
        self.rect = pygame.Rect(rect)
        self.open = False
        self.tab = "lists"
        self.staged = []  # words typed but not saved yet
        self.rejected = []
        self.message = ""
        self._delete_armed_until = 0.0
        self._hits = []  # (rect, action) rebuilt every frame
        self.input = w.TextInput((self.rect.x + 16, 0, self.rect.width - 32 - 96, 32), self._check,
                                 "Type words: because, friend, people ...")

    # ---- helpers ---------------------------------------------------------
    @property
    def tutor(self):
        return self.robot.tutor

    @property
    def lists(self):
        return self.robot.spelling_lists

    def toggle(self, tab=None):
        if tab and (not self.open or self.tab != tab):
            self.open, self.tab = True, tab
        else:
            self.open = not self.open
        if self.open:
            self.robot.progress.reload()

    def _weeks(self):
        weeks = set(self.lists.weeks()) | {week_id(), self.tutor.active_week}
        return sorted(weeks)

    def _shift_week(self, step):
        weeks = self._weeks()
        i = weeks.index(self.tutor.active_week) + step
        if 0 <= i < len(weeks):
            self.tutor.active_week = weeks[i]
            self.message = ""

    def _check(self, text):
        good, bad = parse_word_list(text)
        current = self.lists.load(self.tutor.active_week).words
        for word in good:
            if word not in self.staged and word not in current:
                self.staged.append(word)
        self.rejected = bad
        skipped = [g for g in good if g in current]
        parts = []
        if self.staged:
            parts.append("Check the green words, click one to fix it, then Save.")
        if bad:
            parts.append("Letters only, so these were left out: " + ", ".join(bad) + ".")
        if skipped:
            parts.append("Already on the list: " + ", ".join(skipped) + ".")
        self.message = " ".join(parts)

    def _fix(self, word):
        self.staged.remove(word)
        self.input.text = (self.input.text + " " + word).strip()
        self.input.focused = True
        pygame.key.start_text_input()

    def _save(self):
        added = self.lists.add_words(self.tutor.active_week, self.staged)
        self.message = f"Saved {len(added)} word{'s' if len(added) != 1 else ''} to {self.tutor.active_week}."
        self.staged = []
        self.rejected = []

    def _remove(self, word):
        self.lists.remove_word(self.tutor.active_week, word)
        self.input.text = (self.input.text + " " + word).strip()
        self.message = f"Removed {word}. Fix it in the box and press Enter to add it back."

    def _load_example(self):
        try:
            data = json.loads(EXAMPLE_LIST.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            self.message = f"Couldn't read the example list: {exc}"
            return
        added = self.lists.add_words(self.tutor.active_week, data.get("words", []))
        self.message = f"Added {len(added)} example words to {self.tutor.active_week}."

    def _delete_list(self):
        now = time.monotonic()
        if now > self._delete_armed_until:
            self._delete_armed_until = now + 4.0
            self.message = "Click Delete list again to confirm."
            return
        self._delete_armed_until = 0.0
        self.lists.delete(self.tutor.active_week)
        self.message = f"Deleted the list for {self.tutor.active_week}."

    # ---- events ----------------------------------------------------------
    def handle(self, event) -> bool:
        if not self.open:
            return False
        if self.tab == "lists" and self.input.handle(event):
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, action in self._hits:
                if rect.collidepoint(event.pos):
                    action()
                    return True
            return self.rect.collidepoint(event.pos)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.open = False
            return True
        return False

    # ---- drawing ---------------------------------------------------------
    def _button(self, s, rect, label, action, mouse, selected=False, colour=None, size=16):
        rect = pygame.Rect(rect)
        if colour is None:
            colour = w.WIDGET_ACTIVE if selected else (w.WIDGET_HOVER if rect.collidepoint(mouse) else w.WIDGET)
        pygame.draw.rect(s, colour, rect, border_radius=6)
        img = w.font(size).render(label, True, w.TEXT)
        s.blit(img, img.get_rect(center=rect.center))
        self._hits.append((rect, action))
        return rect

    def _chips(self, s, words, x, y, right, colour, action, mouse, suffix=""):
        """Lay words out as clickable chips, wrapping lines. Returns the next y."""
        if not words:
            return y
        cx = x
        for word in words:
            label = word + suffix
            width = w.font(17).size(label)[0] + 18
            if cx + width > right:
                cx = x
                y += 32
            rect = pygame.Rect(cx, y, width, 26)
            hover = rect.collidepoint(mouse)
            self._button(s, rect, label, (lambda wd=word: action(wd)), mouse,
                         colour=tuple(min(255, c + 20) for c in colour) if hover else colour, size=17)
            cx += width + 6
        return y + 34

    def draw(self, s, mouse, dt):
        if not self.open:
            return
        self._hits = []
        r = self.rect
        pygame.draw.rect(s, w.PANEL, r, border_radius=10)
        pygame.draw.rect(s, w.ACCENT, r, 1, border_radius=10)
        x, right = r.x + 16, r.right - 16
        w.draw_text(s, "Spelling homework", (x, r.y + 14), w.TEXT, 26)
        self._button(s, (right - 80, r.y + 12, 80, 28), "Close", self.toggle, mouse)
        self._button(s, (x + 230, r.y + 12, 80, 28), "Lists", lambda: setattr(self, "tab", "lists"),
                     mouse, selected=self.tab == "lists")
        self._button(s, (x + 316, r.y + 12, 90, 28), "Progress",
                     lambda: (setattr(self, "tab", "progress"), self.robot.progress.reload()),
                     mouse, selected=self.tab == "progress")
        if self.tab == "lists":
            self._draw_lists(s, mouse, dt, x, right, r.y + 54)
        else:
            self._draw_progress(s, x, right, r.y + 54)

    def _draw_lists(self, s, mouse, dt, x, right, y):
        week = self.tutor.active_week
        this_week = " (this week)" if week == week_id() else ""
        self._button(s, (x, y, 32, 28), "<", lambda: self._shift_week(-1), mouse)
        w.draw_text(s, f"{week}: {week_label(week)}{this_week}", (x + 42, y + 5), w.TEXT, 20)
        self._button(s, (right - 32, y, 32, 28), ">", lambda: self._shift_week(1), mouse)
        y += 36
        w.draw_text(s, "AlfieBot uses the week shown here for practice and tests.",
                    (x, y), w.TEXT_DIM, 16)
        y += 26

        words = self.lists.load(week).words
        w.draw_text(s, f"Saved words ({len(words)})", (x, y), w.ACCENT, 19)
        y += 26
        if self.tutor.hide_words:
            w.draw_text(s, "Hidden while the spelling test is running.", (x, y), w.TEXT_DIM, 18)
            y += 34
        elif words:
            w.draw_text(s, "Click a word to remove it (it goes back in the box to fix).",
                        (x, y), w.TEXT_DIM, 15)
            y = self._chips(s, words, x, y + 20, right, WORD_CHIP, self._remove, mouse, "  x")
        else:
            w.draw_text(s, "No words yet. Type some below, or add them by voice.", (x, y), w.TEXT_DIM, 18)
            y += 30

        y += 6
        w.draw_text(s, "Add words", (x, y), w.ACCENT, 19)
        y += 26
        self.input.rect.topleft = (x, y)
        self.input.rect.width = right - x - 96
        self.input.draw(s, dt)
        self._button(s, (right - 88, y, 88, 32), "Check", self.input.submit, mouse)
        y += 42
        if self.staged:
            y = self._chips(s, self.staged, x, y, right, GOOD_CHIP, self._fix, mouse)
            self._button(s, (x, y, 150, 28), f"Save {len(self.staged)} word{'s' if len(self.staged) != 1 else ''}",
                         self._save, mouse, colour=(30, 120, 80))
            self._button(s, (x + 158, y, 90, 28), "Clear",
                         lambda: (self.staged.clear(), setattr(self, "message", "")), mouse)
            y += 36
        if self.rejected:
            y = self._chips(s, self.rejected, x, y, right, BAD_CHIP, lambda _: None, mouse)
        if self.message:
            for line in w.wrap_text(self.message, right - x, 17):
                w.draw_text(s, line, (x, y), w.WARN if "left out" in self.message else w.TEXT_DIM, 17)
                y += 20

        bottom = self.rect.bottom - 44
        if not words:
            self._button(s, (x, bottom, 170, 28), "Load example list", self._load_example, mouse)
        armed = time.monotonic() < self._delete_armed_until
        if words:
            self._button(s, (right - 190, bottom, 190, 28),
                         "Click again to confirm" if armed else "Delete this list",
                         self._delete_list, mouse, colour=(120, 50, 50) if armed else None)

    def _draw_progress(self, s, x, right, y):
        progress = self.robot.progress
        words = self.lists.load(self.tutor.active_week).words
        others = sorted(set(progress.data["words"]) - set(words))
        rows = words + others
        w.draw_text(s, f"Words for {self.tutor.active_week}" + (" and earlier" if others else ""),
                    (x, y), w.ACCENT, 19)
        y += 28
        cols = [x, x + 200, x + 290, x + 380, x + 470, x + 610]
        for cx, head in zip(cols, ("Word", "Tries", "Right", "Wrong", "Last practised", "")):
            w.draw_text(s, head, (cx, y), w.TEXT_DIM, 17)
        y += 22
        hidden = self.tutor.hide_words
        max_rows = 11
        if not rows:
            w.draw_text(s, "Nothing practised yet.", (x, y), w.TEXT_DIM, 18)
            y += 24
        for i, word in enumerate(rows[:max_rows]):
            e = progress.word(word)
            needs = progress.needs_practice(word)
            colour = w.WARN if needs else w.TEXT
            label = f"word {i + 1}" if hidden and word in words else word
            values = (label, e["attempts"], e["correct"], e["incorrect"], e["last_practised"] or "-",
                      "practise again" if needs else "")
            for cx, v in zip(cols, values):
                w.draw_text(s, str(v), (cx, y), colour, 18)
            y += 22
        if len(rows) > max_rows:
            w.draw_text(s, f"... and {len(rows) - max_rows} more", (x, y), w.TEXT_DIM, 16)
            y += 22
        y += 12
        w.draw_text(s, "Recent sessions", (x, y), w.ACCENT, 19)
        y += 26
        sessions = progress.sessions()[-6:][::-1]
        if not sessions:
            w.draw_text(s, "No practice or tests finished yet.", (x, y), w.TEXT_DIM, 18)
        for sess in sessions:
            missed = ", ".join(sess.get("incorrect", [])) or "none"
            if hidden:
                missed = "(hidden during test)"
            text = (f"{sess['date']}  {sess['mode']:<8}  {sess['score']}/{sess['total']}   "
                    f"to practise: {missed}")
            w.draw_text(s, text, (x, y), w.TEXT, 17, max_width=right - x)
            y += 22
