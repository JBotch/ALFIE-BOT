"""AI performance statistics: latency, tokens, errors and timeouts per
provider and model, labelled with the machine that measured them.

Laptop numbers say nothing about a Raspberry Pi 5, so every record carries
the machine label and the panel shows the Pi as "not measured" until the
same benchmark has been run on one. With a database, every request is
also saved to the ``ai_requests`` table (timings and counts only, never
what was said) and the statistics survive a restart.
"""

import logging
import platform
import sqlite3
import statistics
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from alfiebot.ai.provider_base import AIResult

log = logging.getLogger(__name__)


def machine_label() -> str:
    from alfiebot.hardware.detect import is_raspberry_pi

    if is_raspberry_pi():
        return "Raspberry Pi"
    system = {"Windows": "Windows PC", "Darwin": "Mac", "Linux": "Linux PC"}.get(platform.system(),
                                                                              platform.system())
    return f"{system} ({platform.machine() or 'unknown CPU'})"


@dataclass
class Record:
    at: float
    machine: str
    provider: str
    model: str
    ok: bool
    timed_out: bool
    latency_s: float
    completion_tokens: int
    tokens_per_s: Optional[float]
    error: Optional[str]
    cost_estimate: float
    source: str = "chat"  # "chat" or "benchmark"


@dataclass
class Summary:
    provider: str
    model: str
    machine: str
    requests: int
    errors: int
    timeouts: int
    median_s: Optional[float]
    p90_s: Optional[float]
    tokens_per_s: Optional[float]
    cost: float


class PerformanceTracker:
    MAX_RECORDS = 2000

    def __init__(self, machine: str = None, db=None):
        self.machine = machine or machine_label()
        self.db = db
        self.records: List[Record] = []
        self._lock = threading.Lock()
        if db is not None:
            self._load()

    def _load(self) -> None:
        try:
            rows = self.db.query("SELECT * FROM ai_requests ORDER BY id DESC LIMIT ?", (self.MAX_RECORDS,))
        except (sqlite3.Error, OSError) as exc:
            log.error("Couldn't read AI statistics: %s", exc)
            return
        self.records = [Record(r["at"], r["machine"], r["provider"], r["model"], bool(r["ok"]),
                               bool(r["timed_out"]), r["latency_s"], r["completion_tokens"], r["tokens_per_s"],
                               r["error"], r["cost"], r["source"]) for r in reversed(rows)]

    def record(self, result: AIResult, source: str = "chat", task: str = "conversation") -> None:
        rec = Record(time.time(), self.machine, result.provider, result.model, result.ok,
                     result.timed_out, result.latency_s, result.completion_tokens,
                     result.tokens_per_s, result.error, result.cost_estimate, source)
        with self._lock:
            self.records.append(rec)
            del self.records[:-self.MAX_RECORDS]
        if self.db is not None:
            try:
                self.db.execute(
                    "INSERT INTO ai_requests (at, machine, source, provider, model, task, ok, timed_out, latency_s,"
                    " prompt_tokens, completion_tokens, tokens_per_s, memory_mb, cost, error)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (rec.at, rec.machine, source, rec.provider, rec.model, task, int(rec.ok), int(rec.timed_out),
                     rec.latency_s, result.prompt_tokens, rec.completion_tokens, rec.tokens_per_s,
                     result.memory_mb, rec.cost_estimate, (rec.error or "")[:200] or None))
            except (sqlite3.Error, OSError) as exc:
                log.error("Couldn't save AI statistics: %s", exc)

    def reset(self) -> None:
        with self._lock:
            self.records.clear()
        if self.db is not None:
            try:
                self.db.execute("DELETE FROM ai_requests")
            except (sqlite3.Error, OSError) as exc:
                log.error("Couldn't clear AI statistics: %s", exc)

    def spend_today(self) -> float:
        """Estimated cloud cost since midnight (local time)."""
        midnight = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
        with self._lock:
            return sum(r.cost_estimate for r in self.records if r.at >= midnight)

    def recent_median(self, provider: str, model: str, count: int = 5) -> Optional[float]:
        """Median time of the last few good answers from one model."""
        with self._lock:
            times = [r.latency_s for r in self.records if r.provider == provider and r.model == model and r.ok
                     and r.source == "chat"][-count:]
        return statistics.median(times) if times else None

    def summaries(self) -> List[Summary]:
        with self._lock:
            records = list(self.records)
        groups: Dict[Tuple[str, str, str], List[Record]] = {}
        for r in records:
            groups.setdefault((r.provider, r.model, r.machine), []).append(r)
        out = []
        for (provider, model, machine), rs in sorted(groups.items()):
            good = sorted(r.latency_s for r in rs if r.ok)
            speeds = [r.tokens_per_s for r in rs if r.ok and r.tokens_per_s]
            out.append(Summary(
                provider, model, machine, len(rs),
                errors=sum(1 for r in rs if not r.ok and not r.timed_out),
                timeouts=sum(1 for r in rs if r.timed_out),
                median_s=statistics.median(good) if good else None,
                p90_s=good[min(len(good) - 1, int(round(0.9 * (len(good) - 1))))] if good else None,
                tokens_per_s=statistics.mean(speeds) if speeds else None,
                cost=sum(r.cost_estimate for r in rs)))
        return out
