"""Local SQLite database (data/alfiebot.db), with numbered migrations.

Version 1 holds AI request statistics: timings, token counts, errors and
which machine measured them, never what was said. Version 2 adds learning
records: spelling lists, progress per word, sessions, attempts and the
adaptations log. Version 3 adds the time per answer and the letter
recognition comparison results (from synthetic voices, never a child). Each version is a migration, so an existing database is
upgraded in place rather than replaced.

A connection is opened per operation: calls come from the AI worker
thread and the UI thread, and the database is small.
"""

import logging
import sqlite3
import threading
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Iterable, Iterator, List, Sequence

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
    # 2: learning records (spelling lists, progress, sessions, attempts, adaptations).
    ("""CREATE TABLE word_lists (
            week TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL)""",
     """CREATE TABLE words (
            id INTEGER PRIMARY KEY,
            week TEXT NOT NULL REFERENCES word_lists(week) ON DELETE CASCADE,
            word TEXT NOT NULL,
            position INTEGER NOT NULL,
            syllables TEXT NOT NULL DEFAULT '',
            tip TEXT NOT NULL DEFAULT '',
            sentence TEXT NOT NULL DEFAULT '',
            UNIQUE (week, word))""",
     """CREATE TABLE word_progress (
            word TEXT PRIMARY KEY,
            box INTEGER NOT NULL DEFAULT 1,
            due_on TEXT,
            attempts INTEGER NOT NULL DEFAULT 0,
            correct INTEGER NOT NULL DEFAULT 0,
            incorrect INTEGER NOT NULL DEFAULT 0,
            unclear INTEGER NOT NULL DEFAULT 0,
            hints INTEGER NOT NULL DEFAULT 0,
            taught INTEGER NOT NULL DEFAULT 0,
            difficult_sessions INTEGER NOT NULL DEFAULT 0,
            early_clue INTEGER NOT NULL DEFAULT 0,
            last_seen TEXT)""",
     """CREATE TABLE sessions (
            id INTEGER PRIMARY KEY,
            activity TEXT NOT NULL,
            week TEXT NOT NULL DEFAULT '',
            started_at REAL NOT NULL,
            ended_at REAL,
            score INTEGER NOT NULL DEFAULT 0,
            total INTEGER NOT NULL DEFAULT 0,
            to_practise TEXT NOT NULL DEFAULT '',
            recognition_mode TEXT NOT NULL DEFAULT 'continuous')""",
     """CREATE TABLE attempts (
            id INTEGER PRIMARY KEY,
            session_id INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
            word TEXT NOT NULL,
            at REAL NOT NULL,
            mode TEXT NOT NULL,
            outcome TEXT NOT NULL,
            answer TEXT NOT NULL DEFAULT '',
            hints_used INTEGER NOT NULL DEFAULT 0,
            clarifications INTEGER NOT NULL DEFAULT 0,
            min_confidence REAL,
            source TEXT NOT NULL DEFAULT 'typed')""",
     "CREATE INDEX attempts_word ON attempts (word, at)",
     """CREATE TABLE adaptations (
            id INTEGER PRIMARY KEY,
            at REAL NOT NULL,
            kind TEXT NOT NULL,
            target TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            reason TEXT NOT NULL,
            reverted_at REAL)""",
     """CREATE TABLE preferences (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            approved_at REAL)""",
     """CREATE TABLE meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL)"""),
    # 3: time per answer, and the letter recognition comparison (synthetic voices only).
    ("ALTER TABLE attempts ADD COLUMN seconds REAL",
     """CREATE TABLE letter_trials (
            id INTEGER PRIMARY KEY,
            run TEXT NOT NULL,
            at REAL NOT NULL,
            machine TEXT NOT NULL,
            recogniser TEXT NOT NULL,
            mode TEXT NOT NULL,
            voice TEXT NOT NULL,
            speed REAL NOT NULL,
            noise REAL NOT NULL,
            expected TEXT NOT NULL,
            heard TEXT NOT NULL,
            min_confidence REAL,
            would_ask INTEGER NOT NULL,
            correct INTEGER NOT NULL,
            audio_s REAL NOT NULL,
            process_s REAL NOT NULL)"""),
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
        conn.execute("PRAGMA foreign_keys = ON")
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

    def execute(self, sql: str, params: Iterable = ()) -> int:
        """Run one statement; returns the new row's id for an INSERT."""
        self._ensure()
        with self._lock, closing(self._connect()) as conn, conn:
            return conn.execute(sql, tuple(params)).lastrowid

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Several statements that succeed or fail together."""
        self._ensure()
        with self._lock, closing(self._connect()) as conn, conn:
            yield conn

    def query(self, sql: str, params: Iterable = ()) -> List[sqlite3.Row]:
        self._ensure()
        with self._lock, closing(self._connect()) as conn:
            return conn.execute(sql, tuple(params)).fetchall()
