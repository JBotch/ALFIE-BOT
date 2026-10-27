"""Conversation transcript kept in memory only (never written to disk)."""

import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class TranscriptEntry:
    speaker: str  # "user", "robot" or "system"
    text: str
    source: str = ""  # e.g. "typed", "voice"
    timestamp: float = field(default_factory=time.time)


class Transcript:
    def __init__(self, max_entries: int = 200):
        self.entries = deque(maxlen=max_entries)
        self.version = 0  # bumped on every change so views know to redraw

    def add(self, speaker: str, text: str, source: str = "") -> TranscriptEntry:
        entry = TranscriptEntry(speaker, text, source)
        self.entries.append(entry)
        self.version += 1
        return entry

    def clear(self) -> None:
        self.entries.clear()
        self.version += 1
