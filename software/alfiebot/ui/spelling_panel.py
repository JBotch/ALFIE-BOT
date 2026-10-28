"""Spelling homework manager: weekly lists, progress and the learning log.

Shown over the left half of the simulator. Typed words are checked
before saving: they appear as chips, a click on one moves it back into the
box to fix it, and only "Save" writes them to the list.

Progress shows each word's review box, next review, right / wrong / help /
unclear counts and repeated difficulties, with a reset per word. Changes
shows every automatic adaptation with its reason and an Undo, plus CSV
export and "Reset all learning". Words are hidden while a test runs.
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
        self._armed = None  # (action name, until) for two-click parent controls
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
        added = self.lists.add_words(self.tutor.active_week, data.get("words", []), data.get("extras") or {})
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

    def _confirm(self, name: str, prompt: str) -> bool:
        """Parent controls that delete things take two clicks."""
        now = time.monotonic()
        if self._armed and self._armed[0] == name and now < self._armed[1]:
            self._armed = None
            return True
        self._armed = (name, now + 4.0)
        self.message = prompt
        return False

    def _armed_for(self, name: str) -> bool:
        return bool(self._armed and self._armed[0] == name and time.monotonic() < self._armed[1])

    def _reset_word(self, word):
        if self._confirm(f"reset:{word}", f"Click Reset again to forget the progress for {word}."):
            self.robot.progress.reset_word(word)
            self.message = f"Progress for {word} reset."

    def _reset_all(self):
        if self._confirm("reset_all", "Click again to delete all spelling progress (the lists are kept)."):
            self.tutor.stop()
            self.robot.progress.reset_all()
            self.message = "All spelling progress deleted. The lists are kept."

    def _undo(self, adaptation_id):
        ok = self.robot.progress.undo(adaptation_id)
        self.message = "Change undone." if ok else "That change was already undone."

    def _export(self):
        try:
            path = self.robot.progress.export_csv(Path(self.robot.store.base_dir) / "exports")
            self.message = f"Saved {path}"
        except OSError as exc:
            self.message = f"Couldn't export: {exc}"

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
                     lambda: (setattr(self, "tab", "progress"), setattr(self, "message", "")),
                     mouse, selected=self.tab == "progress")
        self._button(s, (x + 412, r.y + 12, 90, 28), "Changes",
                     lambda: (setattr(self, "tab", "changes"), setattr(self, "message", "")),
                     mouse, selected=self.tab == "changes")
        if self.tab == "lists":
            self._draw_lists(s, mouse, dt, x, right, r.y + 54)
        elif self.tab == "progress":
            self._draw_progress(s, mouse, x, right, r.y + 54)
        else:
            self._draw_changes(s, mouse, x, right, r.y + 54)

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

    def _draw_progress(self, s, mouse, x, right, y):
        progress = self.robot.progress
        words = self.lists.load(self.tutor.active_week).words
        others = [wd for wd in progress.known_words() if wd not in words]
        rows = words + others
        w.draw_text(s, f"Words for {self.tutor.active_week}" + (" and earlier" if others else ""),
                    (x, y), w.ACCENT, 19)
        w.draw_text(s, "Box 1 comes back tomorrow, box 5 in 14 days.", (x + 330, y + 3), w.TEXT_DIM, 15)
        y += 28
        cols = [x, x + 150, x + 200, x + 310, x + 365, x + 420, x + 475, x + 540]
        for cx, head in zip(cols, ("Word", "Box", "Next review", "Right", "Wrong", "Help", "Unclear", "")):
            w.draw_text(s, head, (cx, y), w.TEXT_DIM, 16)
        y += 22
        hidden = self.tutor.hide_words
        max_rows = 10
        if not rows:
            w.draw_text(s, "Nothing practised yet.", (x, y), w.TEXT_DIM, 18)
            y += 24
        today = progress.today().isoformat()
        for i, word in enumerate(rows[:max_rows]):
            e = progress.word(word)
            tricky = e["difficult_sessions"] >= 2
            due = e["seen"] and (e["due_on"] or "") <= today
            colour = w.WARN if tricky or (due and e["box"] <= 1) else w.TEXT
            label = f"word {i + 1}" if hidden and word in words else word
            note = "tricky" if tricky else ("due" if due else "")
            values = (label, e["box"] if e["seen"] else "-", e["due_on"] if e["seen"] else "new",
                      e["correct"], e["incorrect"], e["hints"] + e["taught"], e["unclear"], note)
            for cx, v in zip(cols, values):
                w.draw_text(s, str(v), (cx, y), colour, 17)
            if e["seen"] and not hidden:
                armed = self._armed_for(f"reset:{word}")
                self._button(s, (right - 70, y - 2, 70, 20), "Sure?" if armed else "Reset",
                             lambda wd=word: self._reset_word(wd), mouse,
                             colour=(120, 50, 50) if armed else None, size=14)
            y += 22
        if len(rows) > max_rows:
            w.draw_text(s, f"... and {len(rows) - max_rows} more", (x, y), w.TEXT_DIM, 16)
            y += 22
        y += 10
        w.draw_text(s, "Recent sessions", (x, y), w.ACCENT, 19)
        y += 26
        sessions = progress.sessions(5)[::-1]
        if not sessions:
            w.draw_text(s, "No practice or tests finished yet.", (x, y), w.TEXT_DIM, 18)
        for sess in sessions:
            missed = ", ".join(sess.get("incorrect", [])) or "none"
            if hidden:
                missed = "(hidden during test)"
            counts = sess.get("outcomes", {})
            extra = ", ".join(f"{n} {k.replace('_', ' ')}" for k, n in sorted(counts.items())
                              if k in ("taught", "unclear", "help_requested", "skipped"))
            text = (f"{sess['date']}  {sess['mode']:<8}  {sess['score']}/{sess['total']}   to practise: {missed}"
                    + (f"   ({extra})" if extra else ""))
            w.draw_text(s, text, (x, y), w.TEXT, 16, max_width=right - x)
            y += 22
        if self.message:
            w.draw_text(s, self.message, (x, self.rect.bottom - 34), w.TEXT_DIM, 16, max_width=right - x)

    def _draw_changes(self, s, mouse, x, right, y):
        progress = self.robot.progress
        w.draw_text(s, "What AlfieBot changed by itself, and why", (x, y), w.ACCENT, 19)
        y += 26
        w.draw_text(s, "Review boxes and earlier clues. Undo puts the old value back.", (x, y), w.TEXT_DIM, 15)
        y += 24
        hidden = self.tutor.hide_words
        changes = progress.adaptations(12)
        if not changes:
            w.draw_text(s, "No changes yet.", (x, y), w.TEXT_DIM, 18)
            y += 24
        for a in changes:
            target = "a word (hidden during test)" if hidden else a["target"]
            text = f"{a['when']}  {target}: {a['reason']}"
            colour = w.TEXT_DIM if a["reverted_at"] else w.TEXT
            w.draw_text(s, text + ("  (undone)" if a["reverted_at"] else ""), (x, y), colour, 15,
                        max_width=right - x - 80)
            if not a["reverted_at"] and not hidden:
                self._button(s, (right - 70, y - 2, 70, 20), "Undo", lambda i=a["id"]: self._undo(i), mouse, size=14)
            y += 22
        bottom = self.rect.bottom - 44
        self._button(s, (x, bottom, 150, 28), "Export CSV", self._export, mouse)
        armed = self._armed_for("reset_all")
        self._button(s, (right - 220, bottom, 220, 28), "Click again to confirm" if armed else "Reset all learning",
                     self._reset_all, mouse, colour=(120, 50, 50) if armed else None)
        if self.message:
            w.draw_text(s, self.message, (x, bottom - 26), w.TEXT_DIM, 16, max_width=right - x)
