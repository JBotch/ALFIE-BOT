"""Questions Python answers exactly, without any AI: simple maths, the time
and the date. Small AI models get sums wrong; these never do.

``answer(text)`` returns a ToolAnswer, or None if the text isn't one of
these questions. Numbers can be digits or words ("seven times eight").
"""

import datetime as dt
import re
from dataclasses import dataclass
from typing import Callable, Optional

from alfiebot.core.states import Expression

UNITS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
         "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
WORD_VALUES = {w: i for i, w in enumerate(UNITS)}
WORD_VALUES.update({w: i * 10 for i, w in enumerate(TENS) if w})
WORD_VALUES.update({"a hundred": 100, "one hundred": 100, "a thousand": 1000, "one thousand": 1000})
NUMBER = (r"(\d+(?:\.\d+)?|(?:" + "|".join(sorted(WORD_VALUES, key=len, reverse=True)) +
          r")(?:[ -](?:one|two|three|four|five|six|seven|eight|nine))?)")
OPERATORS = {
    "+": ("plus", lambda a, b: a + b), "plus": ("plus", lambda a, b: a + b), "add": ("add", lambda a, b: a + b),
    "and": ("and", lambda a, b: a + b),
    "-": ("minus", lambda a, b: a - b), "minus": ("minus", lambda a, b: a - b),
    "take away": ("take away", lambda a, b: a - b), "takeaway": ("take away", lambda a, b: a - b),
    "x": ("times", lambda a, b: a * b), "*": ("times", lambda a, b: a * b), "×": ("times", lambda a, b: a * b),
    "times": ("times", lambda a, b: a * b), "multiplied by": ("times", lambda a, b: a * b),
    "/": ("divided by", None), "÷": ("divided by", None), "divided by": ("divided by", None),
    "over": ("divided by", None),
}
OP = "|".join(re.escape(o) for o in sorted(OPERATORS, key=len, reverse=True))
SUM = re.compile(rf"^(?:what(?:'s| is)|how much is|how many is|can you (?:do|work out)|work out|calculate)?\s*"
                 rf"{NUMBER}\s*({OP})\s*{NUMBER}\s*(?:equals?|is)?\s*\??$")
TIME = re.compile(r"\b(what(?:'s| is) the time|what time is it|tell me the time)\b")
DATE = re.compile(r"\b(what(?:'s| is) the date|what(?:'s| is) today'?s date|what date is it|"
                  r"what day is it( today)?|what(?:'s| is) today)\b")
LIMIT = 1_000_000


@dataclass
class ToolAnswer:
    text: str
    tool: str
    mood: Expression = Expression.HAPPY


def answer(text: str, now: Callable[[], dt.datetime] = dt.datetime.now) -> Optional[ToolAnswer]:
    lowered = " ".join(text.lower().replace("?", " ?").split()).replace(" ?", "?")
    lowered = re.sub(r"^(hey |hi )?(alfie ?bot,? )?(please )?", "", lowered).rstrip("!. ")
    if TIME.search(lowered):
        t = now()
        return ToolAnswer(f"Beep boop, my clock says it's {_time_words(t)}.", "time")
    if DATE.search(lowered):
        d = now()
        return ToolAnswer(f"Today is {d:%A} the {_ordinal(d.day)} of {d:%B}.", "date")
    m = SUM.match(lowered)
    if m:
        return _sum(m.group(1), m.group(2), m.group(3))
    return None


def _number(word: str) -> Optional[float]:
    word = word.strip()
    if re.fullmatch(r"\d+(\.\d+)?", word):
        return float(word)
    parts = re.split(r"[ -]", word)
    if " ".join(parts) in WORD_VALUES:
        return float(WORD_VALUES[" ".join(parts)])
    if len(parts) == 2 and parts[0] in WORD_VALUES and parts[1] in WORD_VALUES:
        return float(WORD_VALUES[parts[0]] + WORD_VALUES[parts[1]])
    return None


def _sum(left: str, op: str, right: str) -> Optional[ToolAnswer]:
    a, b = _number(left), _number(right)
    if a is None or b is None or abs(a) > LIMIT or abs(b) > LIMIT:
        return None
    name, fn = OPERATORS[op]
    question = f"{_fmt(a)} {name} {_fmt(b)}"
    if name == "divided by":
        if b == 0:
            return ToolAnswer("Ooh, dividing by zero is a puzzle even robots can't solve!", "maths", Expression.CONFUSED)
        if a == int(a) and b == int(b) and a % b:
            q, r = divmod(int(a), int(b))
            return ToolAnswer(f"{question} is {q} remainder {r}. Beep boop!", "maths")
        result = a / b
    else:
        result = fn(a, b)
    return ToolAnswer(f"{question} is {_fmt(result)}! Beep boop, maths is fun.", "maths")


def _fmt(value: float) -> str:
    if value < 0:
        return "minus " + _fmt(-value)
    if value == int(value):
        return f"{int(value):,}".replace(",", " ") if abs(value) >= 10000 else str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _time_words(t: dt.datetime) -> str:
    hour = t.hour % 12 or 12
    part = "in the morning" if t.hour < 12 else ("in the afternoon" if t.hour < 18 else "in the evening")
    if t.minute == 0:
        return f"{hour} o'clock {part}"
    return f"{hour}:{t.minute:02d} {part}"
