"""The learning engine: Python is the examiner, AI is (later) the tutor.

- ``store.py``: spelling lists, progress, sessions, attempts and the
  adaptations log in SQLite; parent review, undo, reset and CSV export;
  the one-off copy of the old JSON files.
- ``schedule.py``: the five-box spaced-repetition schedule.
- ``teaching.py``: clues that don't give the spelling away, and the
  teaching step (beats, tricky part, memory tip, spelling it together).

The spoken-letter checks and the activity itself are in
``spelling/tutor.py`` and ``spelling/letter_input.py``.
"""
