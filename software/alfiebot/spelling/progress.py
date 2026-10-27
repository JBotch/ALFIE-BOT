"""Spelling progress, saved locally in data/progress.json.

For every word: attempts, correct and incorrect answers, and the date and
result of each attempt. Each finished practice or test is kept as a session.
"""

import datetime as dt
from typing import Dict, List

from alfiebot.storage.json_store import JsonStore

FILE = "progress"
MAX_HISTORY = 20


def today() -> str:
    return dt.date.today().isoformat()


class ProgressTracker:
    def __init__(self, store: JsonStore):
        self.store = store
        self.data = self._load()

    def _load(self) -> dict:
        data = self.store.load(FILE) or {}
        data.setdefault("words", {})
        data.setdefault("sessions", [])
        return data

    def reload(self) -> None:
        self.data = self._load()

    def save(self) -> None:
        self.store.save(FILE, self.data)

    def word(self, word: str) -> dict:
        return self.data["words"].get(word, {"attempts": 0, "correct": 0, "incorrect": 0,
                                             "last_practised": None, "history": []})

    def record_attempt(self, word: str, correct: bool, mode: str, answer: str = "") -> None:
        entry = self.word(word)
        entry["attempts"] += 1
        entry["correct" if correct else "incorrect"] += 1
        entry["last_practised"] = today()
        entry["history"] = (entry["history"] + [
            {"date": today(), "mode": mode, "correct": correct, "answer": answer}])[-MAX_HISTORY:]
        self.data["words"][word] = entry
        self.save()

    def record_session(self, mode: str, week: str, results: Dict[str, bool]) -> None:
        self.data["sessions"].append({
            "date": today(), "mode": mode, "week": week,
            "score": sum(results.values()), "total": len(results),
            "incorrect": [w for w, ok in results.items() if not ok],
        })
        self.save()

    def needs_practice(self, word: str) -> bool:
        """Never got right, or got wrong on the latest attempt."""
        entry = self.word(word)
        if not entry["attempts"]:
            return False
        last = entry["history"][-1]["correct"] if entry["history"] else entry["correct"] > 0
        return entry["correct"] == 0 or not last

    def words_needing_practice(self, words: List[str]) -> List[str]:
        return [w for w in words if self.needs_practice(w)]

    def sessions(self) -> List[dict]:
        return list(self.data["sessions"])
