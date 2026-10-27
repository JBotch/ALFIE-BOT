"""Weekly spelling lists, saved as JSON in data/spellings/<week>.json."""

import datetime as dt
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from alfiebot.spelling.words import clean_word
from alfiebot.storage.json_store import JsonStore

log = logging.getLogger(__name__)

FOLDER = "spellings"


def week_id(day: dt.date = None) -> str:
    """ISO week, e.g. '2026-W44'."""
    year, week, _ = (day or dt.date.today()).isocalendar()
    return f"{year}-W{week:02d}"


def week_label(week: str) -> str:
    """'2026-W44' -> 'week beginning 26 Oct 2026'."""
    try:
        monday = dt.datetime.strptime(week + "-1", "%G-W%V-%u").date()
    except ValueError:
        return week
    return f"week beginning {monday.day} {monday.strftime('%b %Y')}"


@dataclass
class SpellingList:
    week: str
    words: List[str] = field(default_factory=list)
    title: str = ""

    def to_json(self) -> dict:
        return {"week": self.week, "title": self.title, "words": self.words}

    @classmethod
    def from_json(cls, data: dict, week: str = "") -> "SpellingList":
        words = []
        for w in data.get("words", []):
            w = clean_word(str(w))
            if w and w not in words:
                words.append(w)
        return cls(week=data.get("week") or week, words=words, title=data.get("title", ""))


class SpellingLists:
    def __init__(self, store: JsonStore):
        self.store = store

    def weeks(self) -> List[str]:
        return self.store.list(FOLDER)

    def load(self, week: str) -> SpellingList:
        data = self.store.load(f"{FOLDER}/{week}")
        return SpellingList.from_json(data, week) if data else SpellingList(week)

    def save(self, spelling_list: SpellingList) -> None:
        self.store.save(f"{FOLDER}/{spelling_list.week}", spelling_list.to_json())
        log.info("Saved %d spellings for %s", len(spelling_list.words), spelling_list.week)

    def add_words(self, week: str, words: List[str]) -> List[str]:
        """Add words to a week's list; returns the ones that were new."""
        spelling_list = self.load(week)
        added = []
        for w in words:
            w = clean_word(w)
            if w and w not in spelling_list.words:
                spelling_list.words.append(w)
                added.append(w)
        if added:
            self.save(spelling_list)
        return added

    def remove_word(self, week: str, word: str) -> None:
        spelling_list = self.load(week)
        if word in spelling_list.words:
            spelling_list.words.remove(word)
            self.save(spelling_list)

    def delete(self, week: str) -> None:
        path = self.store.path_for(f"{FOLDER}/{week}")
        if path.exists():
            path.unlink()
            log.info("Deleted spelling list %s", week)

    def best_week(self, preferred: str) -> Optional[str]:
        """The preferred week if it has words, otherwise the newest list with words."""
        if self.load(preferred).words:
            return preferred
        for week in reversed(self.weeks()):
            if self.load(week).words:
                return week
        return None
