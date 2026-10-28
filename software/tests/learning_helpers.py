"""A spelling tutor backed by a throwaway SQLite learning store."""

import datetime as dt
import random
import tempfile

from alfiebot.learning.store import LearningProgress, WordLists
from alfiebot.spelling.tutor import SpellingTutor
from alfiebot.storage.database import Database


class Clock:
    """A date you can move forward, for the review schedule."""

    def __init__(self, day=dt.date(2026, 10, 26)):
        self.day = day

    def __call__(self):
        return self.day

    def advance(self, days):
        self.day += dt.timedelta(days=days)


def make_store(data_dir=None, today=None, **kw):
    db = Database(data_dir or tempfile.mkdtemp(prefix="alfiebot-test-"))
    return WordLists(db), LearningProgress(db, today=today or dt.date.today, **kw)


def make_tutor(data_dir=None, rng=None, today=None, **kwargs):
    lists, progress = make_store(data_dir, today)
    return SpellingTutor(lists, progress, rng or random.Random(0), **kwargs)
