"""Words and letters: cleaning words, spelling them out, and reading a
child's spelled answer (typed, or spoken letter by letter)."""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

MAX_WORD_LENGTH = 30

# Spoken names for each letter, as a speech recogniser might write them.
LETTER_NAMES = {
    "a": ["a", "ay", "eh"],
    "b": ["b", "bee", "be"],
    "c": ["c", "see", "sea", "cee"],
    "d": ["d", "dee"],
    "e": ["e", "ee"],
    "f": ["f", "ef", "eff"],
    "g": ["g", "gee", "jee"],
    "h": ["h", "aitch", "haitch", "ach"],
    "i": ["i", "eye"],
    "j": ["j", "jay"],
    "k": ["k", "kay"],
    "l": ["l", "el", "ell"],
    "m": ["m", "em"],
    "n": ["n", "en"],
    "o": ["o", "oh"],
    "p": ["p", "pee"],
    "q": ["q", "queue", "cue"],
    "r": ["r", "ar", "are"],
    "s": ["s", "es", "ess"],
    "t": ["t", "tee", "tea"],
    "u": ["u", "you", "yu"],
    "v": ["v", "vee"],
    "w": ["w", "doubleyou", "doubleu"],
    "x": ["x", "ex"],
    "y": ["y", "why", "wy"],
    "z": ["z", "zed", "zee"],
}
NAME_TO_LETTER = {name: letter for letter, names in LETTER_NAMES.items() for name in names}
FILLER = {"capital", "big", "small", "little", "letter", "then", "and", "um", "umm", "er", "erm",
          "its", "it", "is", "spelled", "spelt"}


def clean_word(text: str) -> Optional[str]:
    """Lower-case a single word; None if it isn't a plain word of letters."""
    word = text.strip().lower().replace("’", "'")
    word = word.strip(".,!?;:\"'()")
    if not word or len(word) > MAX_WORD_LENGTH or not re.fullmatch(r"[a-z]+", word):
        return None
    return word


def parse_word_list(text: str) -> Tuple[List[str], List[str]]:
    """Split typed text into words. Returns (good words, rejected pieces).

    Commas, new lines and spaces all separate words. Duplicates are dropped.
    """
    good, bad = [], []
    for piece in re.split(r"[,\n;\t ]+", text):
        if not piece.strip():
            continue
        word = clean_word(piece)
        if word is None:
            bad.append(piece.strip())
        elif word not in good:
            good.append(word)
    return good, bad


def spell_out(word: str, slow: bool = False) -> str:
    """'because' -> 'B-E-C-A-U-S-E' (or 'B... E... C...' when slow)."""
    letters = [c.upper() for c in word]
    return "... ".join(letters) + "..." if slow else "-".join(letters)


@dataclass
class SpelledAnswer:
    letters: str  # e.g. "because"; empty if nothing usable was heard
    confident: bool  # False = ask the child to confirm before marking it


def parse_spelled_answer(text: str, source: str = "typed", confidence: float = 1.0,
                         min_confidence: float = 0.75) -> SpelledAnswer:
    """Read a spelling attempt.

    Typed answers are taken as they are: "because", "b e c a u s e" and
    "B-E-C-A-U-S-E" all give "because".

    Spoken answers must be letter names ("bee ee see ay you ess ee",
    "double s" for "ss"). If anything is unclear, or the recogniser wasn't
    sure, the answer comes back with confident=False so AlfieBot asks
    "is that right?" instead of marking it wrong.
    """
    lowered = text.lower().replace("’", "'")
    if source == "typed":
        letters = re.sub(r"[^a-z]", "", lowered)
        return SpelledAnswer(letters, bool(letters))

    tokens = re.findall(r"[a-z]+", lowered.replace("double u", "doubleu").replace("double you", "doubleyou"))
    letters = []
    unclear = False
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("double", "treble", "triple") and i + 1 < len(tokens) and tokens[i + 1] in NAME_TO_LETTER:
            letters.append(NAME_TO_LETTER[tokens[i + 1]] * (2 if tok == "double" else 3))
            i += 2
            continue
        if tok in NAME_TO_LETTER:
            letters.append(NAME_TO_LETTER[tok])
        elif tok in FILLER:
            pass
        else:
            # A whole word, or something the recogniser misheard.
            unclear = True
            letters.append(tok)
        i += 1
    joined = "".join(letters)
    confident = bool(joined) and not unclear and confidence >= min_confidence
    return SpelledAnswer(joined, confident)

