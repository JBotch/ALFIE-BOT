"""Letter recognition test: how well does the recogniser hear each letter?

A grown-up (or Alfie) is shown a letter, says it, and the result is
recorded: what was heard, the confidence, how long recognition took,
whether AlfieBot would have had to ask, and the final answer after asking.
Sessions are saved to ``data/letter_tests/`` (results only, never audio)
and ``format_report`` sums them up: accuracy, the letters that get mixed
up, and differences between speakers and speaking speeds.

Used by ``tools/letter_test.py`` and the simulator's Letter test panel.
"""

import random
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List, Optional

from alfiebot.spelling.letter_input import CONFUSION_SETS, Letter, parse_letters

ALPHABET = "abcdefghijklmnopqrstuvwxyz"
LETTER_SETS = {
    "all": ALPHABET,
    "confusing": "".join(CONFUSION_SETS),
    **{"/".join(group.upper()): group for group in CONFUSION_SETS},
}
SPEEDS = ("normal", "slow", "fast")
TEST_DIR = "letter_tests"


@dataclass
class Trial:
    expected: str
    recognised: str  # first attempt: one letter, "" for nothing, or several letters
    confidence: float
    latency: float  # seconds from the start of speech to the result
    clarification_required: bool
    final: str  # after asking again (or the first attempt if no need)
    correct: bool  # final == expected
    heard: str = ""
    speaker: str = ""
    speed: str = "normal"


class LetterTestSession:
    def __init__(self, letter_set: str = "all", rounds: int = 1, speaker: str = "",
                 speed: str = "normal", min_confidence: float = 0.75, rng: random.Random = None):
        letters = LETTER_SETS.get(letter_set, letter_set)
        self.prompts = list(letters) * max(1, rounds)
        (rng or random.Random()).shuffle(self.prompts)
        self.letter_set = letter_set
        self.speaker = speaker.strip() or "unnamed"
        self.speed = speed
        self.min_confidence = min_confidence
        self.trials: List[Trial] = []
        self.index = 0
        self.clarifying = False
        self._first = None
        self.started = time.strftime("%Y-%m-%d %H:%M:%S")

    @property
    def current(self) -> Optional[str]:
        return self.prompts[self.index] if self.index < len(self.prompts) else None

    @property
    def done(self) -> bool:
        return self.current is None

    def record(self, text: str, words=None, confidence: float = 1.0, latency: float = 0.0) -> str:
        """One recognition result for the current letter.
        Returns "clarify" (ask again, as AlfieBot would), "next" or "done"."""
        letters = [t for t in parse_letters(text, words, confidence) if isinstance(t, Letter)]
        recognised = "".join(t.letter for t in letters)
        conf = min((t.confidence for t in letters), default=0.0)
        clear = len(letters) == 1 and (letters[0].phonetic or conf >= self.min_confidence)
        if not self.clarifying:
            self._first = (recognised, conf, latency, text)
            if not clear:
                self.clarifying = True
                return "clarify"
        first = self._first
        final = recognised if len(letters) == 1 else ""
        expected = self.current
        self.trials.append(Trial(expected, first[0], round(first[1], 3), round(first[2], 3),
                                 self.clarifying, final, final == expected, first[3],
                                 self.speaker, self.speed))
        self.clarifying = False
        self.index += 1
        return "done" if self.done else "next"

    def nothing_heard(self) -> str:
        """No result in time: ask again once, then count it as a miss."""
        if self.clarifying:
            self.skip()
            return "done" if self.done else "next"
        self._first = ("", 0.0, 0.0, "")
        self.clarifying = True
        return "clarify"

    def skip(self) -> None:
        """Nothing usable was heard (e.g. a timeout): counts as a miss."""
        expected = self.current
        if expected is None:
            return
        first = self._first if self.clarifying else ("", 0.0, 0.0, "")
        self.trials.append(Trial(expected, first[0], first[1], first[2], True, "", False, first[3],
                                 self.speaker, self.speed))
        self.clarifying = False
        self.index += 1

    def to_json(self) -> dict:
        return {"started": self.started, "speaker": self.speaker, "speed": self.speed,
                "letter_set": self.letter_set, "min_confidence": self.min_confidence,
                "trials": [asdict(t) for t in self.trials]}

    def save(self, store) -> str:
        """Save to data/letter_tests/ with a JsonStore. Returns the file name."""
        safe = "".join(c for c in self.speaker if c.isalnum() or c in "-_") or "unnamed"
        name = f"{TEST_DIR}/{time.strftime('%Y%m%d-%H%M%S')}-{safe}-{self.speed}.json"
        store.save(name, self.to_json())
        return name


def load_trials(store) -> List[Trial]:
    trials = []
    for name in store.list(TEST_DIR):
        data = store.load(f"{TEST_DIR}/{name}", {}) or {}
        for t in data.get("trials", []):
            try:
                trials.append(Trial(**t))
            except TypeError:
                continue
    return trials


# ---- report -----------------------------------------------------------
def _pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.0f}%" if whole else "-"


def summarise(trials: Iterable[Trial]) -> Dict:
    trials = list(trials)
    n = len(trials)
    first_right = sum(1 for t in trials if t.recognised == t.expected and not t.clarification_required)
    confusions = Counter((t.expected, t.recognised or "(nothing)") for t in trials
                         if t.recognised != t.expected)
    per_letter = defaultdict(lambda: [0, 0, 0])  # tries, right first time, right in the end
    for t in trials:
        row = per_letter[t.expected]
        row[0] += 1
        row[1] += t.recognised == t.expected and not t.clarification_required
        row[2] += t.correct
    groups = {}
    for key in ("speaker", "speed"):
        g = defaultdict(lambda: [0, 0])
        for t in trials:
            g[getattr(t, key)][0] += 1
            g[getattr(t, key)][1] += t.correct
        groups[key] = dict(g)
    sets = {}
    for group in CONFUSION_SETS:
        ts = [t for t in trials if t.expected in group]
        if ts:
            sets["/".join(group.upper())] = (len(ts), sum(t.recognised == t.expected for t in ts),
                                             sum(t.correct for t in ts))
    latencies = [t.latency for t in trials if t.latency > 0]
    return {
        "trials": n,
        "first_try_right": first_right,
        "final_right": sum(t.correct for t in trials),
        "clarified": sum(t.clarification_required for t in trials),
        "wrong_but_sure": sum(1 for t in trials if not t.clarification_required and not t.correct),
        "mean_latency": sum(latencies) / len(latencies) if latencies else 0.0,
        "mean_confidence": sum(t.confidence for t in trials) / n if n else 0.0,
        "per_letter": dict(per_letter),
        "confusions": confusions.most_common(),
        "groups": groups,
        "sets": sets,
    }


def format_report(trials: Iterable[Trial]) -> str:
    s = summarise(trials)
    n = s["trials"]
    if not n:
        return "No letter tests recorded yet."
    lines = [
        f"Letter recognition report: {n} letters",
        f"  Right first time, no need to ask:  {s['first_try_right']} ({_pct(s['first_try_right'], n)})",
        f"  AlfieBot would have asked again:   {s['clarified']} ({_pct(s['clarified'], n)})",
        f"  Right in the end (after asking):   {s['final_right']} ({_pct(s['final_right'], n)})",
        f"  Wrong but sure (the risky case):   {s['wrong_but_sure']} ({_pct(s['wrong_but_sure'], n)})",
        f"  Average confidence {s['mean_confidence']:.2f}, average recognition time "
        f"{s['mean_latency']:.2f} s",
        "",
        "Most common mix-ups (said -> heard):",
    ]
    if s["confusions"]:
        for (said, heard), count in s["confusions"][:12]:
            lines.append(f"  {said.upper()} -> {heard.upper() if heard != '(nothing)' else heard}  x{count}")
    else:
        lines.append("  none")
    if s["sets"]:
        lines += ["", "Letters that sound alike (tries, right first time, right in the end):"]
        for name, (tries, first, final) in s["sets"].items():
            lines.append(f"  {name:<7} {tries:>3} tries  {_pct(first, tries):>4} first time  "
                         f"{_pct(final, tries):>4} in the end")
    for key, title in (("speaker", "By speaker"), ("speed", "By speed")):
        if len(s["groups"][key]) > 1 or key == "speaker":
            lines += ["", f"{title} (right in the end):"]
            for name, (tries, right) in sorted(s["groups"][key].items()):
                lines.append(f"  {name:<12} {right}/{tries} ({_pct(right, tries)})")
    weak = sorted(((row[2] / row[0], letter) for letter, row in s["per_letter"].items() if row[0]))
    weak = [letter.upper() for score, letter in weak if score < 0.8]
    lines += ["", "Letters to watch (under 80% in the end): " + (", ".join(weak) if weak else "none")]
    return "\n".join(lines)
