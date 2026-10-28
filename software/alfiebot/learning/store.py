"""Learning records in SQLite (data/alfiebot.db): spelling lists, progress
per word, sessions, attempts and the adaptations log.

``WordLists`` and ``LearningProgress`` keep the method names of the old
JSON classes (``spelling/lists.py`` and ``spelling/progress.py``), so the
tutor and panels work with either. On first start the JSON files are
copied in once by ``import_json`` and left in place as a backup.

Nothing here depends on an AI provider, so switching AI never touches
progress.
"""

import csv
import datetime as dt
import json
import logging
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

from alfiebot.learning import schedule
from alfiebot.learning.schedule import DIFFICULT, FIRST_TRY, INTERVALS, MASTERED_BOX
from alfiebot.spelling.lists import SpellingList
from alfiebot.spelling.words import clean_word
from alfiebot.storage.database import Database

log = logging.getLogger(__name__)

# Attempt outcomes. Only correct and incorrect count as marked attempts.
CORRECT = "correct"
INCORRECT = "incorrect"
UNCLEAR = "unclear"
HELP_REQUESTED = "help_requested"
TAUGHT = "taught"
SKIPPED = "skipped"
OUTCOMES = (CORRECT, INCORRECT, UNCLEAR, HELP_REQUESTED, TAUGHT, SKIPPED)


class WordLists:
    """Weekly spelling lists. Same methods as ``spelling.lists.SpellingLists``."""

    def __init__(self, db: Database):
        self.db = db

    def weeks(self) -> List[str]:
        return [r["week"] for r in self.db.query("SELECT week FROM word_lists ORDER BY week")]

    def load(self, week: str) -> SpellingList:
        title = self.db.query("SELECT title FROM word_lists WHERE week = ?", (week,))
        rows = self.db.query("SELECT word FROM words WHERE week = ? ORDER BY position", (week,))
        return SpellingList(week, [r["word"] for r in rows], title[0]["title"] if title else "")

    def save(self, spelling_list: SpellingList) -> None:
        with self.db.transaction() as conn:
            self._ensure_week(conn, spelling_list.week, spelling_list.title)
            conn.execute("UPDATE word_lists SET title = ? WHERE week = ?", (spelling_list.title, spelling_list.week))
            keep = [w for w in spelling_list.words]
            conn.execute(f"DELETE FROM words WHERE week = ? AND word NOT IN ({','.join('?' * len(keep))})",
                         (spelling_list.week, *keep))
            for i, word in enumerate(keep):
                conn.execute("INSERT INTO words (week, word, position) VALUES (?, ?, ?) "
                             "ON CONFLICT (week, word) DO UPDATE SET position = excluded.position",
                             (spelling_list.week, word, i))
        log.info("Saved %d spellings for %s", len(spelling_list.words), spelling_list.week)

    @staticmethod
    def _ensure_week(conn, week: str, title: str = "") -> None:
        conn.execute("INSERT OR IGNORE INTO word_lists (week, title, created_at) VALUES (?, ?, ?)",
                     (week, title, time.time()))

    def add_words(self, week: str, words: List[str], extras: Dict[str, dict] = None) -> List[str]:
        """Add words to a week's list; returns the ones that were new.
        ``extras`` can give a word its own syllables, tip and sentence."""
        added = []
        with self.db.transaction() as conn:
            self._ensure_week(conn, week)
            existing = {r[0] for r in conn.execute("SELECT word FROM words WHERE week = ?", (week,))}
            position = len(existing)
            for raw in words:
                word = clean_word(str(raw))
                if not word or word in existing:
                    continue
                info = (extras or {}).get(word, {})
                conn.execute("INSERT INTO words (week, word, position, syllables, tip, sentence) "
                             "VALUES (?, ?, ?, ?, ?, ?)",
                             (week, word, position, info.get("syllables", ""), info.get("tip", ""),
                              info.get("sentence", "")))
                existing.add(word)
                added.append(word)
                position += 1
        if added:
            log.info("Added %d spellings to %s", len(added), week)
        return added

    def remove_word(self, week: str, word: str) -> None:
        self.db.execute("DELETE FROM words WHERE week = ? AND word = ?", (week, word))

    def delete(self, week: str) -> None:
        """Parent control: delete a week's list. Progress for its words is kept."""
        self.db.execute("DELETE FROM word_lists WHERE week = ?", (week,))
        log.info("Deleted spelling list %s", week)

    def best_week(self, preferred: str) -> Optional[str]:
        """The preferred week if it has words, otherwise the newest list with words."""
        rows = self.db.query("SELECT DISTINCT week FROM words ORDER BY week DESC")
        weeks = [r["week"] for r in rows]
        if preferred in weeks:
            return preferred
        return weeks[0] if weeks else None

    def word_info(self, word: str) -> dict:
        """A word's syllables, tip and sentence, from its newest list."""
        rows = self.db.query("SELECT syllables, tip, sentence FROM words WHERE word = ? "
                             "ORDER BY week DESC LIMIT 1", (word,))
        return dict(rows[0]) if rows else {"syllables": "", "tip": "", "sentence": ""}


class LearningProgress:
    """Progress, sessions, the review schedule and the adaptations log.
    Same reading methods as ``spelling.progress.ProgressTracker``."""

    def __init__(self, db: Database, intervals: Sequence[int] = INTERVALS, max_session_words: int = 10,
                 confidence_words: int = 2, today: Callable[[], dt.date] = dt.date.today,
                 clock: Callable[[], float] = time.time):
        self.db = db
        self.intervals = tuple(intervals) if len(intervals) == schedule.BOXES else INTERVALS
        self.max_session_words = max(1, int(max_session_words))
        self.confidence_words = max(0, int(confidence_words))
        self.today = today
        self.clock = clock

    def reload(self) -> None:
        """Nothing is cached; kept so callers of the JSON tracker still work."""

    # ---- sessions -------------------------------------------------------------
    def start_session(self, activity: str, week: str = "", recognition_mode: str = "continuous") -> int:
        return self.db.execute("INSERT INTO sessions (activity, week, started_at, recognition_mode) "
                               "VALUES (?, ?, ?, ?)", (activity, week or "", self.clock(), recognition_mode))

    def finish_session(self, session_id: int, results: Dict[str, bool]) -> None:
        missed = [w for w, ok in results.items() if not ok]
        self.db.execute("UPDATE sessions SET ended_at = ?, score = ?, total = ?, to_practise = ? WHERE id = ?",
                        (self.clock(), sum(results.values()), len(results), json.dumps(missed), session_id))

    def record_session(self, mode: str, week: str, results: Dict[str, bool]) -> None:
        self.finish_session(self.start_session(mode, week), results)

    def sessions(self, limit: int = None) -> List[dict]:
        sql = "SELECT * FROM sessions WHERE ended_at IS NOT NULL ORDER BY started_at DESC, id DESC"
        rows = self.db.query(sql + (f" LIMIT {int(limit)}" if limit else ""))
        out = []
        for r in reversed(rows):
            counts = {row["outcome"]: row["n"] for row in self.db.query(
                "SELECT outcome, COUNT(*) AS n FROM attempts WHERE session_id = ? GROUP BY outcome", (r["id"],))}
            out.append({"id": r["id"], "date": _date(r["started_at"]), "mode": r["activity"], "week": r["week"],
                        "score": r["score"], "total": r["total"],
                        "incorrect": json.loads(r["to_practise"] or "[]"), "outcomes": counts})
        return out

    # ---- attempts -------------------------------------------------------------
    def record_attempt(self, word: str, correct: bool = None, mode: str = "practice", answer: str = "",
                       outcome: str = None, hints: int = 0, clarifications: int = 0,
                       min_confidence: float = None, source: str = "typed", session_id: int = None,
                       seconds: float = None) -> None:
        outcome = outcome or (CORRECT if correct else INCORRECT)
        if outcome not in OUTCOMES:
            raise ValueError(f"unknown outcome {outcome}")
        marked = outcome in (CORRECT, INCORRECT)
        with self.db.transaction() as conn:
            conn.execute("INSERT INTO attempts (session_id, word, at, mode, outcome, answer, hints_used, "
                         "clarifications, min_confidence, source, seconds) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (session_id, word, self.clock(), mode, outcome, answer if marked else "", hints,
                          clarifications, min_confidence, source, seconds))
            self._ensure_word(conn, word)
            conn.execute(
                "UPDATE word_progress SET attempts = attempts + ?, correct = correct + ?, "
                "incorrect = incorrect + ?, unclear = unclear + ?, hints = hints + ?, taught = taught + ?, "
                "last_seen = ? WHERE word = ?",
                (int(marked), int(outcome == CORRECT), int(outcome == INCORRECT),
                 int(outcome == UNCLEAR or clarifications > 0), int(outcome == HELP_REQUESTED),
                 int(outcome == TAUGHT), self.today().isoformat(), word))

    def _ensure_word(self, conn, word: str) -> None:
        conn.execute("INSERT OR IGNORE INTO word_progress (word, box, due_on) VALUES (?, 1, ?)",
                     (word, self.today().isoformat()))

    def finish_word(self, word: str, result: str, session_id: int = None) -> int:
        """Move the word between boxes after a practice or test. Returns its box."""
        if result not in schedule.RESULTS:
            raise ValueError(f"unknown result {result}")
        today = self.today()
        with self.db.transaction() as conn:
            self._ensure_word(conn, word)
            row = conn.execute("SELECT box, due_on, difficult_sessions, early_clue FROM word_progress "
                               "WHERE word = ?", (word,)).fetchone()
            box = schedule.next_box(row["box"], result)
            due = schedule.due_date(box, today, self.intervals).isoformat()
            conn.execute("UPDATE word_progress SET box = ?, due_on = ?, last_seen = ? WHERE word = ?",
                         (box, due, today.isoformat(), word))
            if box != row["box"]:
                self._adapt(conn, "box", word, {"box": row["box"], "due_on": row["due_on"]},
                            {"box": box, "due_on": due},
                            f"{schedule.REASONS[result]}: box {row['box']} to {box}, next review {due}")
            if result in DIFFICULT:
                difficult = row["difficult_sessions"] + 1
                conn.execute("UPDATE word_progress SET difficult_sessions = ? WHERE word = ?", (difficult, word))
                if difficult == 2 and not row["early_clue"]:
                    conn.execute("UPDATE word_progress SET early_clue = 1 WHERE word = ?", (word,))
                    self._adapt(conn, "early_clue", word, 0, 1,
                                "tricky in two sessions, so AlfieBot offers a clue after the first mistake")
        return box

    def _adapt(self, conn, kind: str, target: str, old, new, reason: str) -> None:
        conn.execute("INSERT INTO adaptations (at, kind, target, old_value, new_value, reason) "
                     "VALUES (?, ?, ?, ?, ?, ?)", (self.clock(), kind, target, json.dumps(old), json.dumps(new), reason))
        log.info("Adaptation (%s) for a word: %s", kind, reason)

    # ---- reading ------------------------------------------------------------------
    def word(self, word: str) -> dict:
        rows = self.db.query("SELECT * FROM word_progress WHERE word = ?", (word,))
        if not rows:
            return {"word": word, "box": 1, "due_on": None, "attempts": 0, "correct": 0, "incorrect": 0,
                    "unclear": 0, "hints": 0, "taught": 0, "difficult_sessions": 0, "early_clue": 0,
                    "last_practised": None, "seen": False}
        entry = dict(rows[0])
        entry["last_practised"] = entry["last_seen"]
        entry["seen"] = True
        return entry

    def known_words(self) -> List[str]:
        return [r["word"] for r in self.db.query("SELECT word FROM word_progress ORDER BY word")]

    def repeated_difficulty(self, word: str) -> bool:
        return self.word(word)["difficult_sessions"] >= 2

    def is_due(self, word: str) -> bool:
        entry = self.word(word)
        return entry["seen"] and (entry["due_on"] or "") <= self.today().isoformat()

    def needs_practice(self, word: str) -> bool:
        """Seen before and still in box 1, or due for review."""
        entry = self.word(word)
        return entry["attempts"] > 0 and (entry["box"] <= 1 or self.is_due(word))

    def words_needing_practice(self, words: List[str]) -> List[str]:
        return [w for w in words if self.needs_practice(w)]

    def plan_practice(self, week_words: List[str]) -> List[str]:
        """Words due for review (lowest box first, from any week), then this
        week's new words, then this week's other words, then a couple of
        mastered words for confidence; at most ``max_session_words``."""
        today = self.today().isoformat()
        rows = {r["word"]: r for r in self.db.query("SELECT word, box, due_on FROM word_progress")}
        due = sorted((w for w, r in rows.items() if (r["due_on"] or "") <= today and r["box"] < MASTERED_BOX
                      and (w in week_words or self._attempted(w))),
                     key=lambda w: (rows[w]["box"], rows[w]["due_on"] or "", w))
        new = [w for w in week_words if w not in rows]
        other = [w for w in week_words if w in rows and w not in due and rows[w]["box"] < MASTERED_BOX]
        mastered = [w for w in week_words if w in rows and rows[w]["box"] >= MASTERED_BOX and w not in due]
        if len(mastered) < self.confidence_words:
            mastered += sorted((w for w, r in rows.items() if r["box"] >= MASTERED_BOX and w not in mastered
                                and (r["due_on"] or "") <= today), key=lambda w: rows[w]["due_on"] or "")
        plan: List[str] = []
        for w in due + new + other:
            if w not in plan:
                plan.append(w)
        plan = plan[:self.max_session_words]
        for w in mastered[:self.confidence_words]:
            if w not in plan and (len(plan) < self.max_session_words or not plan):
                plan.append(w)
        return plan or list(week_words[:self.max_session_words])

    def _attempted(self, word: str) -> bool:
        return self.word(word)["attempts"] > 0

    # ---- adaptations and parent controls ----------------------------------------
    def adaptations(self, limit: int = 30) -> List[dict]:
        rows = self.db.query("SELECT * FROM adaptations ORDER BY at DESC, id DESC LIMIT ?", (limit,))
        return [dict(r, when=_date(r["at"])) for r in rows]

    def undo(self, adaptation_id: int) -> bool:
        """Parent control: put back the value from before an adaptation."""
        with self.db.transaction() as conn:
            row = conn.execute("SELECT * FROM adaptations WHERE id = ?", (adaptation_id,)).fetchone()
            if row is None or row["reverted_at"] is not None:
                return False
            old = json.loads(row["old_value"])
            if row["kind"] == "box":
                conn.execute("UPDATE word_progress SET box = ?, due_on = ? WHERE word = ?",
                             (old["box"], old["due_on"], row["target"]))
            elif row["kind"] == "early_clue":
                conn.execute("UPDATE word_progress SET early_clue = ? WHERE word = ?", (old, row["target"]))
            else:
                return False
            conn.execute("UPDATE adaptations SET reverted_at = ? WHERE id = ?", (self.clock(), adaptation_id))
        log.info("Parent undid adaptation %d (%s)", adaptation_id, row["kind"])
        return True

    def reset_word(self, word: str) -> None:
        """Parent control: forget one word's progress (its attempts too)."""
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM word_progress WHERE word = ?", (word,))
            conn.execute("DELETE FROM attempts WHERE word = ?", (word,))
            conn.execute("DELETE FROM adaptations WHERE target = ?", (word,))
        log.info("Parent reset the progress for one word")

    def reset_all(self) -> None:
        """Parent control: delete all learning progress. Lists are kept."""
        with self.db.transaction() as conn:
            for table in ("attempts", "sessions", "word_progress", "adaptations"):
                conn.execute(f"DELETE FROM {table}")
        log.info("Parent reset all learning progress (spelling lists kept)")

    def export_csv(self, folder) -> Path:
        """Parent control: write every word's progress and every attempt to CSV."""
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"learning_{dt.datetime.now():%Y%m%d-%H%M%S}.csv"
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            out = csv.writer(f)
            out.writerow(["record", "word", "date", "mode", "outcome", "answer", "hints", "clarifications",
                          "lowest_confidence", "box", "next_review", "right", "wrong", "unclear", "taught",
                          "tricky_sessions", "seconds", "spelling_mode"])
            for r in self.db.query("SELECT * FROM word_progress ORDER BY word"):
                out.writerow(["word", r["word"], r["last_seen"], "", "", "", r["hints"], "", "", r["box"],
                              r["due_on"], r["correct"], r["incorrect"], r["unclear"], r["taught"],
                              r["difficult_sessions"], "", ""])
            for r in self.db.query("SELECT a.*, s.recognition_mode FROM attempts a LEFT JOIN sessions s "
                                   "ON s.id = a.session_id ORDER BY a.at, a.id"):
                out.writerow(["attempt", r["word"], _date(r["at"], True), r["mode"], r["outcome"], r["answer"],
                              r["hints_used"], r["clarifications"],
                              "" if r["min_confidence"] is None else f"{r['min_confidence']:.2f}"]
                             + [""] * 7 + ["" if r["seconds"] is None else f"{r['seconds']:.1f}",
                                           r["recognition_mode"] or ""])
        log.info("Exported learning records to %s", path)
        return path


def _date(at: float, with_time: bool = False) -> str:
    when = dt.datetime.fromtimestamp(at)
    return f"{when:%Y-%m-%d %H:%M}" if with_time else when.date().isoformat()


def import_json(store, lists: WordLists, progress: LearningProgress) -> Optional[dict]:
    """Copy the JSON spelling lists and progress in, once. The JSON files
    stay where they are as a backup. Returns what was copied, or None if
    this already happened."""
    db = lists.db
    if db.query("SELECT value FROM meta WHERE key = 'json_import'"):
        return None
    counts = {"lists": 0, "words": 0, "progress": 0, "sessions": 0}
    for week in store.list("spellings"):
        data = store.load(f"spellings/{week}") or {}
        spelling_list = SpellingList.from_json(data, week)
        if spelling_list.words:
            with db.transaction() as conn:
                WordLists._ensure_week(conn, spelling_list.week, spelling_list.title)
            counts["words"] += len(lists.add_words(spelling_list.week, spelling_list.words,
                                                   data.get("extras") or {}))
            counts["lists"] += 1
    old = store.load("progress") or {}
    today = progress.today().isoformat()
    with db.transaction() as conn:
        for word, entry in (old.get("words") or {}).items():
            word = clean_word(word)
            if not word:
                continue
            history = entry.get("history") or []
            last_ok = history[-1].get("correct") if history else entry.get("correct", 0) > 0
            box = 2 if entry.get("correct", 0) and last_ok else 1
            conn.execute("INSERT OR REPLACE INTO word_progress (word, box, due_on, attempts, correct, incorrect, "
                         "last_seen) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (word, box, today, int(entry.get("attempts", 0)), int(entry.get("correct", 0)),
                          int(entry.get("incorrect", 0)), entry.get("last_practised")))
            for h in history:
                conn.execute("INSERT INTO attempts (word, at, mode, outcome, answer) VALUES (?, ?, ?, ?, ?)",
                             (word, _timestamp(h.get("date")), h.get("mode", "practice"),
                              CORRECT if h.get("correct") else INCORRECT, h.get("answer", "")))
            counts["progress"] += 1
        for s in old.get("sessions") or []:
            at = _timestamp(s.get("date"))
            conn.execute("INSERT INTO sessions (activity, week, started_at, ended_at, score, total, to_practise) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (s.get("mode", "practice"), s.get("week", ""), at, at, int(s.get("score", 0)),
                          int(s.get("total", 0)), json.dumps(s.get("incorrect", []))))
            counts["sessions"] += 1
        conn.execute("INSERT INTO meta (key, value) VALUES ('json_import', ?)",
                     (json.dumps(dict(counts, at=time.time())),))
    if any(counts.values()):
        log.info("Copied spelling records from JSON into the database (JSON kept as a backup): %s", counts)
    return counts


def _timestamp(day: Optional[str]) -> float:
    try:
        return dt.datetime.fromisoformat(day).timestamp() if day else time.time()
    except ValueError:
        return time.time()
