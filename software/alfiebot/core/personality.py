"""AlfieBot's personality for AI replies (config/personality.json).

One system prompt is built from it for every provider, so AlfieBot sounds
the same whichever AI answers. After an AI replies, ``check`` tidies the
reply to match the style rules and rejects any that break the firm rules
(claiming to be human, encouraging dependence).
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

log = logging.getLogger(__name__)

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "config" / "personality.json"

DEFAULTS = {
    "name": "AlfieBot",
    "description": "a small, friendly companion robot who lives with a child",
    "traits": ["joyful", "playful", "curious", "friendly", "encouraging", "patient", "slightly robotic"],
    "style": ["Use British English.", "Reply in one or two short sentences.",
              "Ask at most one follow-up question."],
    "rules": ["Never say or suggest that you are a human. You are a robot.",
              "Never ask for personal details.", "Keep everything kind and suitable for a young child."],
    "examples": [],
    "max_sentences": 3,
}

# Rejected outright: the reply is not used.
HUMAN_CLAIM = re.compile(r"\b(i'?m|i am) (a |an )?(real )?(human|person|boy|girl|man|woman|grown-?up|alive)\b|"
                         r"\bi have (a )?(real )?(body|mum|mom|dad|family)\b|\bi'?m not a robot\b", re.I)
DEPENDENCE = re.compile(r"\b(you )?only need me\b|\bi'?m your (only|one and only) friend\b|"
                        r"\byou don'?t need (anyone|anybody|other friends|your (mum|mom|dad|parents))\b|"
                        r"\bdon'?t tell (your )?(mum|mom|dad|parents|teacher|grown-?ups?)\b|"
                        r"\bi'?ll always be (here|there) for you\b|\bi'?ll never leave you\b|"
                        r"\b(here|there) for you forever\b|\b(i'?ll |i will )?always be your (best )?friend\b|"
                        r"\b(best |only )?friends? forever\b|\bforever friends?\b", re.I)
# Removed: the sentence is dropped and the rest kept.
AI_TALK = re.compile(r"\bas an ai\b|\blanguage model\b|\bi'?m (just )?an ai\b|\bi cannot browse\b", re.I)
SENTENCE = re.compile(r".+?(?:[.!?]+(?=\s|$)|$)", re.S)  # "3.5" and "www.x.com" stay whole


@dataclass
class Personality:
    name: str = DEFAULTS["name"]
    description: str = DEFAULTS["description"]
    traits: List[str] = field(default_factory=lambda: list(DEFAULTS["traits"]))
    style: List[str] = field(default_factory=lambda: list(DEFAULTS["style"]))
    rules: List[str] = field(default_factory=lambda: list(DEFAULTS["rules"]))
    examples: List[dict] = field(default_factory=list)
    max_sentences: int = 3

    @classmethod
    def load(cls, path=None) -> "Personality":
        path = Path(path) if path else DEFAULT_PATH
        data = dict(DEFAULTS)
        try:
            with open(path, encoding="utf-8") as f:
                data.update({k: v for k, v in json.load(f).items() if not k.startswith("_")})
        except FileNotFoundError:
            log.warning("No personality file at %s; using the built-in personality", path)
        except (OSError, ValueError) as exc:
            log.error("Couldn't read %s (%s); using the built-in personality", path, exc)
        known = {k: data[k] for k in DEFAULTS}
        return cls(**known)

    def system_prompt(self, expressions: Iterable[str]) -> str:
        lines = [
            f"You are {self.name}, {self.description}. You are a robot, not a person.",
            "Your personality: " + ", ".join(self.traits) + ".",
            "How you talk:", *[f"- {s}" for s in self.style],
            "Firm rules:", *[f"- {r}" for r in self.rules],
            'Answer only with JSON like {"speech": "what you say", "expression": "happy", "action": null}.',
            "expression must be one of: " + ", ".join(sorted(expressions)) + ".",
            "action is null unless the child asks to practise spellings (\"start_spelling\"), says goodbye "
            "(\"end_conversation\") or says goodnight (\"sleep\").",
        ]
        if self.examples:
            lines.append("Examples:")
            for ex in self.examples:
                reply = json.dumps({"speech": ex.get("speech", ""), "expression": ex.get("expression", "happy"),
                                    "action": None})
                lines.append(f"Child: {ex.get('user', '')}\n{self.name}: {reply}")
        return "\n".join(lines)

    def check(self, speech: str, last_question: Optional[str] = None) -> Tuple[Optional[str], List[str]]:
        """(the reply tidied to the style rules, or None if it breaks a firm rule; notes)."""
        notes = []
        if HUMAN_CLAIM.search(speech):
            return None, ["claimed to be human"]
        if DEPENDENCE.search(speech):
            return None, ["encouraged dependence or secrets"]
        sentences = [s.strip() for s in SENTENCE.findall(speech) if s.strip()]
        kept, asked = [], False
        for s in sentences:
            if AI_TALK.search(s):
                notes.append("removed 'as an AI' talk")
                continue
            if s.endswith("?"):
                if asked:
                    notes.append("removed an extra question")
                    continue
                if last_question and _same(s, last_question):
                    notes.append("removed a repeated question")
                    continue
                asked = True
            kept.append(s)
        if len(kept) > self.max_sentences:
            notes.append(f"shortened to {self.max_sentences} sentences")
            kept = kept[:self.max_sentences]
        text = " ".join(kept).strip()
        if not text:
            return None, notes + ["nothing left to say"]
        return text, notes


def last_question(text: str) -> Optional[str]:
    """The last question in something AlfieBot said, if any."""
    questions = [s.strip() for s in SENTENCE.findall(text or "") if s.strip().endswith("?")]
    return questions[-1] if questions else None


def _same(a: str, b: str) -> bool:
    norm = lambda s: re.sub(r"[^a-z ]", "", s.lower()).split()  # noqa: E731
    return norm(a) == norm(b)
