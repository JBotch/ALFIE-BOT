"""Deterministic intent recognition: plain phrase patterns, no AI service.

Text is normalised (lower case, no punctuation, apostrophes dropped so
"I'm" becomes "im"), then checked against each intent's patterns in order.
The first match wins. Some intents only count when AlfieBot has just asked
a matching question (the ``expecting`` context).
"""

import re
from dataclasses import dataclass
from typing import Optional

WAKE_RE = re.compile(
    r"^(?:(?:hey|hi|hello|ok|okay|oi)\s+)?(?:alfie\s*bot|alfiebot|alfy\s*bot|alfie)\b\s*(.*)$")
WAKE_REQUIRES_GREETING = {"alfie"}  # bare "alfie" alone could be the child's own name


def normalise(text: str) -> str:
    text = text.lower().replace("’", "'").replace("'", "")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def split_wake_phrase(text: str):
    """Return (woke, rest) where rest is anything said after the wake phrase.

    "Hey AlfieBot, how are you?" -> (True, "how are you")
    """
    norm = normalise(text)
    m = WAKE_RE.match(norm)
    if not m:
        return False, norm
    head = norm[: m.start(1)].strip() if m.group(1) else norm
    words = head.split()
    if words and words[-1] in WAKE_REQUIRES_GREETING and len(words) == 1:
        return False, norm  # just "alfie ..." without hey/hi
    return True, m.group(1).strip()


def _any(*patterns):
    return [re.compile(p) for p in patterns]


# Ordered: earlier intents win.
GENERAL_INTENTS = [
    ("spelling_help", _any(r"\bspell(ing|ings|s)?\b", r"\bhomework\b")),
    ("goodbye", _any(r"\b(good ?bye|bye|see you|go to sleep|good ?night|night night)\b")),
    ("stop", _any(r"^(stop|cancel|never ?mind|nothing|be quiet|shush|shh+)\b")),
    ("how_are_you", _any(r"\bhow (are|r) (you|u)\b", r"\bhow( a)?re you (doing|feeling)\b",
                         r"\bhows it going\b", r"\bare you (ok|okay|alright|well)\b",
                         r"\bhow do you feel\b")),
    ("what_can_you_do", _any(r"\bwhat (can|do) you do\b", r"\bwhat are you able\b",
                             r"\bwhat can we do\b", r"\bwhat shall we do\b",
                             r"\bwhat (things|games) can\b", r"^help$", r"\bhelp me\b$")),
    ("joke", _any(r"\bjokes?\b", r"\bmake me laugh\b", r"\bsomething funny\b")),
    ("who_made_you", _any(r"\bwho (made|built|created|designed|printed) you\b")),
    ("name", _any(r"\bwhats your name\b", r"\bwhat is your name\b", r"\bwho are you\b")),
    ("age", _any(r"\bhow old are you\b", r"\bwhen were you (made|built|born)\b")),
    ("repeat", _any(r"\b(say (that|it) again|repeat( that| it)?|what did you say|pardon)\b",
                    r"^what$")),
    ("thanks", _any(r"\b(thank you|thanks|thankyou|cheers|ta)\b")),
    ("hello", _any(r"^(hello|hi|hey|hiya|good (morning|afternoon|evening))\b")),
]

NEGATIVE_FEELING = re.compile(
    r"\b(not (very )?(good|great|ok|okay|well|happy|fine|alright)|sad|bad|tired|upset|poorly|"
    r"ill|sick|rubbish|grumpy|angry|cross|worried|scared|lonely|bored|awful|terrible|"
    r"horrible|cry|crying|hurt)\b")
POSITIVE_FEELING = re.compile(
    r"\b(good|great|fine|brilliant|awesome|amazing|happy|fantastic|excellent|super|well|"
    r"ok|okay|alright|not bad|cool|wonderful|excited|lovely|grand)\b")
FEELING_LEAD = re.compile(r"^(im|i am|i feel|i m|feeling|i was|very|really|pretty|so)\b")

YES = re.compile(r"^(yes|yeah|yep|yup|sure|ok|okay|please|yes please|go on|go for it|alright|definitely)\b")
NO = re.compile(r"^(no|nope|nah|not now|no thanks|no thank you)\b")

SPELLING_CHOICES = [
    ("add", re.compile(r"\b(add|new|write|enter|put)\b")),
    ("practise", re.compile(r"\b(practi[sc]e|learn|learning|go through)\b")),
    ("test", re.compile(r"\b(test|quiz)\b")),
]


@dataclass
class IntentMatch:
    intent: str
    detail: Optional[str] = None


def match_intent(text: str, expecting: Optional[str] = None) -> IntentMatch:
    norm = normalise(text)
    if not norm:
        return IntentMatch("fallback")

    if expecting == "spelling_choice":
        for choice, pattern in SPELLING_CHOICES:
            if pattern.search(norm):
                return IntentMatch("spelling_choice", choice)
    if expecting == "joke_offer":
        if YES.search(norm):
            return IntentMatch("joke_yes")
        if NO.search(norm):
            return IntentMatch("joke_no")

    feeling = _feeling(norm, expecting == "feeling")
    if feeling:
        return IntentMatch(feeling)

    for intent, patterns in GENERAL_INTENTS:
        if any(p.search(norm) for p in patterns):
            return IntentMatch(intent)

    if expecting == "spelling_choice":
        return IntentMatch("spelling_unclear")
    return IntentMatch("fallback")


def _feeling(norm: str, expected: bool) -> Optional[str]:
    """Feelings count when AlfieBot asked, or when phrased "I'm ..."/"I feel ..."."""
    if not (expected or FEELING_LEAD.search(norm)):
        return None
    if re.search(r"\bhow are you\b", norm):
        return None
    if NEGATIVE_FEELING.search(norm) and not re.search(r"\bnot bad\b", norm):
        return "feeling_bad"
    if POSITIVE_FEELING.search(norm):
        return "feeling_good"
    return None
