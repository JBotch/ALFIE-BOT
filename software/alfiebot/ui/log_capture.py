"""Logging handler that keeps recent messages for the debug panel."""

import logging
from collections import deque


class MemoryLogHandler(logging.Handler):
    def __init__(self, max_records: int = 300):
        super().__init__(level=logging.DEBUG)
        self.records = deque(maxlen=max_records)
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.records.append((record.levelno, self.format(record)))
        except Exception:  # never let logging crash the UI
            self.handleError(record)
