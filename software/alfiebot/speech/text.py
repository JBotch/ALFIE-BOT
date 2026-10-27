"""Turns what AlfieBot writes in the transcript into what a voice should say."""

import re

SPELLED = re.compile(r"\b[A-Z_](?:-[A-Z_])+\b")
SLOW_LETTER = re.compile(r"\b([A-Z])\.\.\.")
# Letters a speech engine might read as a word instead of a letter name.
LETTER_SOUNDS = {"A": "ay", "_": "blank"}


def _letters(match: re.Match) -> str:
    return ", ".join(LETTER_SOUNDS.get(c, c) for c in match.group(0).split("-"))


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
