"""Turns what AlfieBot writes in the transcript into what a voice should say.

``plan_speech`` splits a reply into sentences, spelled letters and pauses,
so every engine says letters one at a time (never run together into a
word) with the gaps the voice profile asks for.
"""

import re
from dataclasses import dataclass
from typing import List, Union

SPELLED = re.compile(r"\b[A-Z_](?:-[A-Z_])+\b")
SLOW_LETTER = re.compile(r"\b([A-Z])\.\.\.")
SLOW_SPELLED = re.compile(r"\b[A-Z_]\.\.\.(?:\s+[A-Z_]\.\.\.)*")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
# Letters a speech engine might read as a word instead of a letter name.
LETTER_SOUNDS = {"A": "ay", "_": "blank"}


def _letters(match: re.Match) -> str:
    return ", ".join(LETTER_SOUNDS.get(c, c) for c in match.group(0).split("-"))


def letter_sound(letter: str) -> str:
    """What to send to a voice so it says the letter's name: 'b' -> 'B', 'a' -> 'ay'."""
    letter = letter.upper()
    return LETTER_SOUNDS.get(letter, letter)


def for_speech(text: str) -> str:
    """'Because. B-E-C-A-U-S-E.' -> 'Because. B, E, C, ay, U, S, E.'

    Spelled words are read letter by letter with a pause between letters,
    the slow "B... E..." form keeps its long pauses, and "AlfieBot" is said
    as two words.
    """
    text = SPELLED.sub(_letters, text)
    text = SLOW_LETTER.sub(lambda m: LETTER_SOUNDS.get(m.group(1), m.group(1)) + "...", text)
    text = re.sub(r"Alfie ?Bot", "Alfie Bot", text, flags=re.I)
    return " ".join(text.split())


@dataclass
class Say:
    text: str


@dataclass
class SayLetter:
    letter: str  # "B", or "_" for a blank


@dataclass
class Pause:
    seconds: float


Segment = Union[Say, SayLetter, Pause]


def letter_segments(letters: str, profile, slow: bool = False, repeat: int = 1) -> List[Segment]:
    """Each letter on its own, with the profile's gap after it."""
    gap = profile.letter_pause * (1.6 if slow else 1.0)
    out: List[Segment] = []
    for r in range(max(1, repeat)):
        if r:
            out.append(Pause(profile.sentence_pause + gap))
        for letter in letters:
            out += [SayLetter(letter.upper()), Pause(gap)]
    return out


def _sentences(text: str, profile) -> List[Segment]:
    out: List[Segment] = []
    for sentence in SENTENCE_END.split(text):
        sentence = sentence.strip()
        if not sentence or not re.search(r"[A-Za-z0-9]", sentence):
            continue
        if profile.word_pause > 0:
            for word in sentence.split():
                out += [Say(word), Pause(profile.word_pause)]
        else:
            out.append(Say(sentence))
        if sentence[-1] in ".!?":
            out.append(Pause(profile.sentence_pause))
    return out


def plan_speech(text: str, profile) -> List[Segment]:
    """'Because is spelled B-E-C-A-U-S-E. Your turn!' ->
    [Say('Because is spelled'), SayLetter('B'), Pause, ..., Say('Your turn!'), Pause]"""
    text = re.sub(r"Alfie ?Bot", "Alfie Bot", text, flags=re.I)
    text = " ".join(text.split())
    out: List[Segment] = []
    pos = 0
    pattern = re.compile(f"{SPELLED.pattern}|{SLOW_SPELLED.pattern}")
    for m in pattern.finditer(text):
        out += _sentences(text[pos:m.start()], profile)
        found = m.group(0)
        slow = "..." in found
        letters = re.findall(r"[A-Z_]", found)
        out += letter_segments("".join(letters), profile, slow)
        pos = m.end()
    out += _sentences(text[pos:], profile)
    # Collapse pauses that ended up next to each other (keep the longest).
    merged: List[Segment] = []
    for seg in out:
        if isinstance(seg, Pause) and merged and isinstance(merged[-1], Pause):
            merged[-1] = Pause(max(merged[-1].seconds, seg.seconds))
        else:
            merged.append(seg)
    while merged and isinstance(merged[-1], Pause):
        merged.pop()
    return merged
