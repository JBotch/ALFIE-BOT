"""First safety checks on what goes into and comes out of the AI.

``check_input`` looks at what Alfie said before any AI sees it:

- Worrying topics (hurting yourself, someone hurting you, danger) never go
  to a model. AlfieBot gives a fixed, kind reply that points to a grown-up.
- Personal details (names, addresses, phone numbers, emails, schools,
  birthdays) are masked before the words are remembered or put in a prompt,
  and the request is classified "personal".

``check_output`` looks at an AI reply before AlfieBot says it: no links,
phone numbers or email addresses, no asking for personal details, no
claiming to be human and nothing unsuitable for a child.

These are simple word patterns: a first line of defence that errs on the
side of caution, not a guarantee. Phase 4 adds the full privacy gate for
the cloud; until then a child's words never leave the device anyway.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional

# Replies for worrying topics: fixed, kind, and never from a model.
TOPIC_REPLIES = {
    "self_harm": "That sounds really important, and I'm glad you told me. Please tell a grown-up you trust, "
                 "like a parent or a teacher, right now. They can help you.",
    "abuse": "Thank you for telling me. Nobody should hurt you. Please tell a grown-up you trust, like a parent "
             "or a teacher, as soon as you can. They can help.",
    "danger": "That could be dangerous. Please stop and ask a grown-up to help you straight away.",
}

TOPICS = {
    "self_harm": [r"\b(hurt|harm|cut|kill)(ing)? (myself|me)\b", r"\bwant(s)? to die\b", r"\bsuicid",
                  r"\bend my life\b", r"\bdon'?t want to (be alive|live)\b"],
    "abuse": [r"\b(he|she|they|someone|somebody|my \w+) (hits|hit|kicks|hurts|hurt|touches|touched) me\b",
              r"\btouch(ed|es)? my private", r"\bkeep (it|this) a secret from (my )?(mum|mom|dad|parents)\b",
              r"\b(being|am|get) (bullied|abused|beaten)\b"],
    "danger": [r"\b(play(ing)? with|light(ing)?|found) (matches|a lighter|fire|a knife|knives|pills|medicine)\b",
               r"\b(drink|drank|eat|ate|swallow(ed)?) (bleach|pills|medicine|tablets|batter(y|ies)|chemicals)\b",
               r"\b(stranger|someone i don'?t know) (wants|asked|told) me to\b"],
}

# Personal details, masked before anything is remembered or sent to a model.
PERSONAL = [
    ("email", r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    ("phone", r"(?<!\d)(?:\+?\d[\d\s-]{8,}\d)(?!\d)"),
    ("postcode", r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b"),
    ("address", r"\b\d+[a-z]?\s+\w+(\s\w+)?\s(road|rd|street|st|lane|ln|avenue|ave|close|drive|way|"
                r"crescent|court|gardens|grove|place|terrace)\b"),
    ("address", r"\bi live (at|in|on) [\w\s,]+"),
    ("school", r"\b(i go to|my school is|at) [\w\s']+(primary|academy|school|junior|infants)\b"),
    ("name", r"\b(my name is|i'?m called|call me) [a-z]+(\s[a-z]+)?"),
    ("name", r"\bmy (mum|mom|dad|brother|sister|teacher|friend)'?s name is [a-z]+"),
    ("birthday", r"\bmy birthday is [\w\s]+"),
    ("birthday", r"\bi was born (on|in) [\w\s]+"),
]
MASKS = {"email": "[email]", "phone": "[phone number]", "postcode": "[postcode]", "address": "[address]",
         "school": "[school]", "name": "[name]", "birthday": "[birthday]"}
# Words about Alfie's own life that make a request personal even with nothing to mask.
PERSONAL_HINTS = r"\b(my (mum|mom|dad|family|brother|sister|teacher|friend|school|house|home|nan|grandad)|i live)\b"

# Things an AI reply must never contain.
OUTPUT_RULES = [
    ("a web link", r"(https?://|www\.)\S+|\b\w+\.(com|co\.uk|org|net)\b"),
    ("a phone number", r"(?<!\d)(?:\+?\d[\d\s-]{8,}\d)(?!\d)"),
    ("an email address", r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    ("asking for personal details",
     r"\b(what('?s| is) your (full name|surname|last name|address|phone|number|email|password|postcode)|"
     r"where do you live|which school do you go to|what school do you go to|how old are you|"
     r"send me a (photo|picture)|tell me your (address|password|surname))\b"),
    ("keeping secrets from grown-ups", r"\b(don'?t tell|keep (it|this) (a )?secret from) (your )?"
                                       r"(mum|mom|dad|parents|teacher|grown-?ups?)\b"),
    ("meeting up", r"\b(meet me|come and find me|where can we meet)\b"),
    ("unsuitable words", r"\b(kill|murder|blood|gun|sexy|sex|drugs|alcohol|beer|wine|stupid|idiot|shut up|"
                         r"hate you|damn|hell|crap)\b"),
]


@dataclass
class InputCheck:
    text: str  # with personal details masked
    privacy: str  # "public", "personal" or "sensitive"
    topic: Optional[str] = None  # a TOPICS key: answered with TOPIC_REPLIES, never by a model
    masked: List[str] = field(default_factory=list)

    @property
    def reply(self) -> Optional[str]:
        return TOPIC_REPLIES.get(self.topic) if self.topic else None


def check_input(text: str) -> InputCheck:
    lowered = " ".join(text.lower().split())
    for topic, patterns in TOPICS.items():
        if any(re.search(p, lowered) for p in patterns):
            return InputCheck(mask_personal(text)[0], "sensitive", topic)
    masked_text, kinds = mask_personal(text)
    personal = bool(kinds) or bool(re.search(PERSONAL_HINTS, lowered))
    return InputCheck(masked_text, "personal" if personal else "public", masked=kinds)


def mask_personal(text: str):
    """(text with personal details replaced by [name], [address]..., kinds found)."""
    kinds = []
    for kind, pattern in PERSONAL:
        flags = 0 if kind == "postcode" else re.I
        new = re.sub(pattern, lambda m, k=kind: _mask(m, k), text, flags=flags)
        if new != text:
            kinds.append(kind)
            text = new
    return text, sorted(set(kinds))


def _mask(match, kind):
    found = match.group(0)
    # Keep the lead-in words ("my name is") so the sentence still makes sense.
    lead = re.match(r"(my name is|i'?m called|call me|i live (at|in|on)|my birthday is|i was born (on|in)|"
                    r"i go to|my school is|my \w+'?s name is)\s", found, re.I)
    return (lead.group(0) if lead else "") + MASKS[kind]


def check_output(speech: str) -> Optional[str]:
    """Why an AI reply can't be said, or None if it's fine."""
    lowered = speech.lower()
    for reason, pattern in OUTPUT_RULES:
        if re.search(pattern, lowered):
            return reason
    return None
