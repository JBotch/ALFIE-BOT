"""AI performance statistics: latency, tokens, errors and timeouts per
provider and model, labelled with the machine that measured them.

Laptop numbers say nothing about a Raspberry Pi 5, so every record carries
the machine label and the panel shows the Pi as "not measured" until the
same benchmark has been run on one. Kept in memory for now; Phase 3 stores
it in SQLite.
"""

import platform
import statistics
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from alfiebot.ai.provider_base import AIResult


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

    def __init__(self, machine: str = None):
        self.machine = machine or machine_label()
        self.records: List[Record] = []
        self._lock = threading.Lock()

    def record(self, result: AIResult) -> None:
        rec = Record(time.time(), self.machine, result.provider, result.model, result.ok,
                     result.timed_out, result.latency_s, result.completion_tokens,
                     result.tokens_per_s, result.error, result.cost_estimate)
        with self._lock:
            self.records.append(rec)
            del self.records[:-self.MAX_RECORDS]

    def reset(self) -> None:
        with self._lock:
            self.records.clear()

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
