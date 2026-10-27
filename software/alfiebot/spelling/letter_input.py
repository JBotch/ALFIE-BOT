"""Spelling recognition: building an answer from letters spoken one at a
time or in short runs.

Conversation and spelling are recognised differently. While a child spells,
the recogniser is limited to ``LETTER_GRAMMAR`` (letter names, "B for ball"
words and a few commands), and every letter keeps its own confidence score.
The letters build up on screen as they are heard:

    "bee ee see"        -> B E C
    "delete"            -> B E
    "see ay"            -> B E C A
    "start again"       -> (cleared)
    "finished"          -> AlfieBot reads the letters back before marking

A letter the recogniser wasn't sure about is never guessed. AlfieBot asks
(e.g. "Was letter 2 B for ball, D for dog or P for pig?") and the child's
answer replaces it. The target word is never used to fix what was heard.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple, Union

from alfiebot.spelling.words import FILLER, LETTER_NAMES, NAME_TO_LETTER

# Letters that sound alike, so a shaky one gets a choice rather than a yes/no.
CONFUSION_SETS = ("bdp", "cgt", "mn", "fs", "ahj")

# "B for ball": child-friendly words, and the NATO alphabet for grown-ups.
CHILD_WORDS = {
    "a": "apple", "b": "ball", "c": "cat", "d": "dog", "e": "egg", "f": "fish", "g": "goat",
    "h": "hat", "i": "igloo", "j": "jam", "k": "kite", "l": "lion", "m": "monkey", "n": "nest",
    "o": "orange", "p": "pig", "q": "queen", "r": "rabbit", "s": "sun", "t": "tiger",
    "u": "umbrella", "v": "van", "w": "window", "x": "xray", "y": "yellow", "z": "zebra",
}
NATO_WORDS = {
    "a": "alpha", "b": "bravo", "c": "charlie", "d": "delta", "e": "echo", "f": "foxtrot",
    "g": "golf", "h": "hotel", "i": "india", "j": "juliet", "k": "kilo", "l": "lima", "m": "mike",
    "n": "november", "o": "oscar", "p": "papa", "q": "quebec", "r": "romeo", "s": "sierra",
    "t": "tango", "u": "uniform", "v": "victor", "w": "whiskey", "x": "xray", "y": "yankee",
    "z": "zulu",
}
PHONETIC_TO_LETTER = {word: letter for words in (CHILD_WORDS, NATO_WORDS)
                      for letter, word in words.items()}
PHONETIC_TO_LETTER.update({"alfa": "a", "juliett": "j", "whisky": "w"})

# Spoken commands while spelling, as word sequences (matched longest first).
COMMANDS = {
    "delete": ["delete", "delete that", "delete it", "delete the last letter", "delete the last one",
               "undo", "go back", "rub that out", "rub it out", "take that off",
               "take it off", "backspace", "remove that"],
    "clear": ["start again", "start over", "clear", "clear it", "clear them", "clear all",
              "rub them out", "rub it all out", "scrap that", "wipe it"],
    "finish": ["finished", "im finished", "i am finished", "done", "im done", "i am done",
               "thats it", "that is it", "check it", "check", "check my spelling", "all done"],
    "readback": ["read it back", "read them back", "what have i got", "what have i spelled",
                 "what have i spelt", "say my letters", "what did i say", "what did you hear"],
    "repeat": ["repeat", "repeat the word", "repeat it", "repeat that", "say the word again",
               "say it again", "say that again", "what was the word", "what is the word",
               "whats the word", "pardon", "again please"],
    "slower": ["slower", "slowly", "say it slowly", "more slowly"],
    "stop": ["stop", "stop the test", "stop spelling", "quit", "no more", "thats enough",
             "i want to stop", "lets stop"],
    "clue": ["clue", "hint", "help", "help me", "give me a clue", "give me a hint"],
    "next": ["next", "next word", "skip", "skip it", "pass", "move on"],
    "dont_know": ["i dont know", "dont know", "no idea", "i give up", "not sure", "im not sure"],
    "restart": ["restart", "from the beginning", "start from the beginning",
                "back to the first word", "go back to the start"],
    "yes": ["yes", "yeah", "yep", "yes please", "thats right", "that is right", "correct", "right"],
    "no": ["no", "nope", "no thanks", "wrong", "thats wrong", "not right"],
    "first": ["the first one", "first one", "the first"],
    "second": ["the second one", "second one", "the second"],
    "third": ["the third one", "third one", "the third"],
}
_PHRASES = sorted(((tuple(p.split()), name) for name, ps in COMMANDS.items() for p in ps),
                  key=lambda item: -len(item[0]))
MULTIPLY = {"double": 2, "treble": 3, "triple": 3}
PHONETIC_JOINERS = (("for",), ("as", "in"), ("like",))
# Words that sit in front of a letter without meaning anything.
SPELLING_FILLER = FILLER | {"the", "ok", "okay", "please", "so", "now", "spell"}


def letter_grammar(phonetic: str = "child") -> List[str]:
    """Words the recogniser may hear while a child spells: letter names,
    "B for ball" words (``phonetic``: "child", "nato" or "both") and commands."""
    words = {name for names in LETTER_NAMES.values() for name in names}
    words.discard("doubleu")
    words.discard("doubleyou")
    words |= set(MULTIPLY) | {"for", "as", "in", "like", "letter", "capital"}
    for phrases in COMMANDS.values():
        for phrase in phrases:
            words |= set(phrase.split())
    if phonetic in ("child", "both"):
        words |= set(CHILD_WORDS.values())
    if phonetic in ("nato", "both"):
        words |= set(NATO_WORDS.values())
    # Vosk spells these with apostrophes and a hyphen.
    words |= {"don't", "that's", "i'm", "x-ray"}
    return sorted(words)


# ---- parsing --------------------------------------------------------------
@dataclass
class Letter:
    letter: str  # "a".."z"
    confidence: float = 1.0
    phonetic: bool = False  # said with a word ("B for ball"), so it's clear
    heard: str = ""


@dataclass
class Command:
    name: str


@dataclass
class Unknown:
    word: str
    confidence: float = 0.0


Token = Union[Letter, Command, Unknown]


def _words_with_confidence(text: str, words: Optional[Sequence[Tuple[str, float]]],
                           confidence: float) -> List[Tuple[str, float]]:
    """Lower-case words with a confidence each. ``words`` are the recogniser's
    own per-word scores when it has them."""
    def tidy(word):
        word = word.lower().replace("’", "'").replace("'", "").replace("-", "")
        return re.sub(r"[^a-z]", "", word)

    if words:
        out = [(tidy(w), c) for w, c in words if w != "[unk]"]
    else:
        out = [(tidy(w), confidence) for w in re.split(r"[\s,.!?;:]+", text)]
    out = [(w, c) for w, c in out if w]
    # "double u" / "double you" is the letter W, not a doubled U.
    merged = []
    for w, c in out:
        if merged and merged[-1][0] == "double" and w in ("u", "you"):
            merged[-1] = ("w", min(c, merged[-1][1]))
        else:
            merged.append((w, c))
    return merged


def parse_letters(text: str, words: Optional[Sequence[Tuple[str, float]]] = None,
                  confidence: float = 1.0) -> List[Token]:
    """Turn what was heard into letters, commands and unknown words, in order."""
    items = _words_with_confidence(text, words, confidence)
    tokens: List[Token] = []
    i = 0
    while i < len(items):
        word, conf = items[i]
        rest = [w for w, _ in items[i:]]
        match = next(((phrase, name) for phrase, name in _PHRASES
                      if tuple(rest[:len(phrase)]) == phrase), None)
        if match:
            tokens.append(Command(match[1]))
            i += len(match[0])
            continue
        if word in MULTIPLY and i + 1 < len(items) and items[i + 1][0] in NAME_TO_LETTER:
            letter = NAME_TO_LETTER[items[i + 1][0]]
            c = min(conf, items[i + 1][1])
            tokens.extend(Letter(letter, c, heard=f"{word} {items[i + 1][0]}")
                          for _ in range(MULTIPLY[word]))
            i += 2
            continue
        if word in NAME_TO_LETTER or word in PHONETIC_TO_LETTER:
            phonetic = word not in NAME_TO_LETTER
            letter = PHONETIC_TO_LETTER[word] if phonetic else NAME_TO_LETTER[word]
            heard = word
            i += 1
            # "B for ball": the word decides, because it is much easier to hear.
            for joiner in PHONETIC_JOINERS:
                end = i + len(joiner)
                if tuple(w for w, _ in items[i:end]) == joiner and end < len(items) \
                        and items[end][0] in PHONETIC_TO_LETTER:
                    said = PHONETIC_TO_LETTER[items[end][0]]
                    heard = " ".join(w for w, _ in items[i - 1:end + 1])
                    # "D for ball" doesn't add up, so it gets checked.
                    phonetic = said == letter
                    conf = max(conf, items[end][1]) if phonetic else 0.0
                    letter = said
                    i = end + 1
                    break
            tokens.append(Letter(letter, conf, phonetic, heard))
            continue
        if word in SPELLING_FILLER or word in ("for", "as", "in", "like", "capital"):
            i += 1
            continue
        tokens.append(Unknown(word, conf))
        i += 1
    return tokens


def heard_letters(text: str, words=None, confidence: float = 1.0) -> str:
    """Just the letters in a (partial) result, e.g. for the live display."""
    return "".join(t.letter for t in parse_letters(text, words, confidence) if isinstance(t, Letter))


def confusable_with(letter: str) -> List[str]:
    """The letters that sound like ``letter`` (including itself), e.g. b -> b, d, p."""
    for group in CONFUSION_SETS:
        if letter in group:
            return list(group)
    return [letter]


# ---- the answer being built ---------------------------------------------
@dataclass
class HeardLetter:
    letter: str  # "a".."z", or "?" for something that wasn't a letter
    confidence: float = 1.0
    phonetic: bool = False
    checked: bool = False  # the child confirmed it
    heard: str = ""

    def sure(self, min_confidence: float) -> bool:
        return self.letter != "?" and (self.checked or self.phonetic or self.confidence >= min_confidence)


@dataclass
class LetterSequence:
    min_confidence: float = 0.75
    letters: List[HeardLetter] = field(default_factory=list)

    def add(self, letter: str, confidence: float = 1.0, phonetic: bool = False, heard: str = "") -> None:
        self.letters.append(HeardLetter(letter, confidence, phonetic, heard=heard))

    def delete(self) -> Optional[HeardLetter]:
        return self.letters.pop() if self.letters else None

    def clear(self) -> None:
        self.letters.clear()

    def __len__(self) -> int:
        return len(self.letters)

    @property
    def text(self) -> str:
        return "".join(h.letter for h in self.letters)

    def unsure_index(self) -> Optional[int]:
        for i, h in enumerate(self.letters):
            if not h.sure(self.min_confidence):
                return i
        return None

    def display(self) -> List[Tuple[str, bool]]:
        """[(letter as shown, sure?)] for the screen."""
        return [(h.letter.upper(), h.sure(self.min_confidence)) for h in self.letters]
