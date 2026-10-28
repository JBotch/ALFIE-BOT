"""Spaced repetition: a five-box Leitner system, simple enough to explain.

Every word sits in a box from 1 to 5. A word in box 1 comes back the next
day; box 5 waits 14 days (the gaps are a setting). After each word in a
practice or test:

- right first time with no help: up one box;
- right after a clue or another try: stays in its box;
- taught, wrong in a test, or skipped: back to box 1;
- unclear (AlfieBot couldn't hear the letters): never moves.

A word that ends two different sessions wrong or taught is a "repeated
difficulty": AlfieBot offers its first clue sooner, and the parent view
shows it.
"""

import datetime as dt
from typing import Sequence

INTERVALS = (1, 2, 4, 7, 14)
BOXES = len(INTERVALS)
MASTERED_BOX = 4

# How a word went in one session.
FIRST_TRY = "first_try"
WITH_HELP = "with_help"
TAUGHT = "taught"
INCORRECT = "incorrect"
SKIPPED = "skipped"
RESULTS = (FIRST_TRY, WITH_HELP, TAUGHT, INCORRECT, SKIPPED)
DIFFICULT = (TAUGHT, INCORRECT, SKIPPED)

REASONS = {
    FIRST_TRY: "right first time with no help",
    WITH_HELP: "right after help or another try",
    TAUGHT: "AlfieBot taught it",
    INCORRECT: "wrong in a test",
    SKIPPED: "skipped",
}


def next_box(box: int, result: str) -> int:
    if result == FIRST_TRY:
        return min(box + 1, BOXES)
    if result == WITH_HELP:
        return box
    return 1


def due_date(box: int, today: dt.date, intervals: Sequence[int] = INTERVALS) -> dt.date:
    box = max(1, min(box, len(intervals)))
    return today + dt.timedelta(days=int(intervals[box - 1]))
