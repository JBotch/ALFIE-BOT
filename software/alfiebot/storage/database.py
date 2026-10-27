"""Local SQLite database (data/alfiebot.db), with numbered migrations.

Version 1 holds AI request statistics only: timings, token counts, errors
and which machine measured them. It never stores what was said. Later
phases add tables (learning records) as new migrations, so an existing
database is upgraded in place rather than replaced.

A connection is opened per operation: calls come from the AI worker
thread and the UI thread, and the database is small.
"""

import logging
import sqlite3
import threading
from contextlib import closing
from pathlib import Path
from typing import Iterable, List, Sequence

log = logging.getLogger(__name__)

MIGRATIONS: List[Sequence[str]] = [
    # 1: AI request statistics.
    ("""CREATE TABLE ai_requests (
            id INTEGER PRIMARY KEY,
            at REAL NOT NULL,
            machine TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'chat',
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            task TEXT NOT NULL DEFAULT 'conversation',
            ok INTEGER NOT NULL,
            timed_out INTEGER NOT NULL DEFAULT 0,
            latency_s REAL NOT NULL,
            prompt_tokens INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            tokens_per_s REAL,
            memory_mb REAL,
            cost REAL NOT NULL DEFAULT 0,
            error TEXT)""",
     "CREATE INDEX ai_requests_model ON ai_requests (provider, model, machine)"),
]


class Database:
    FILENAME = "alfiebot.db"

    def __init__(self, data_dir):
        self.path = Path(data_dir) / self.FILENAME
        self._lock = threading.Lock()
        self._ready = False

    @property
    def version(self) -> int:
        with closing(self._connect()) as conn:
            return conn.execute("PRAGMA user_version").fetchone()[0]

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    def migrate(self) -> None:
        """Bring the database up to date (safe to call every start)."""
        with self._lock, closing(self._connect()) as conn:
            current = conn.execute("PRAGMA user_version").fetchone()[0]
            for number, statements in enumerate(MIGRATIONS[current:], start=current + 1):
                with conn:  # one transaction per migration
                    for sql in statements:
                        conn.execute(sql)
                    conn.execute(f"PRAGMA user_version = {number}")
                log.info("Database %s upgraded to version %d", self.path.name, number)
            self._ready = True

    def _ensure(self) -> None:
        if not self._ready or not self.path.exists():
            self._ready = False
            self.migrate()

    def execute(self, sql: str, params: Iterable = ()) -> None:
        self._ensure()
        with self._lock, closing(self._connect()) as conn, conn:
            conn.execute(sql, tuple(params))

    def query(self, sql: str, params: Iterable = ()) -> List[sqlite3.Row]:
        self._ensure()
        with self._lock, closing(self._connect()) as conn:
            return conn.execute(sql, tuple(params)).fetchall()
