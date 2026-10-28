"""What AlfieBot says to help with a word: clues that don't give the
spelling away, and the teaching step that does.

Everything here is plain Python and works without any AI. A parent can
give a word its own syllables ("be-cause") and memory tip in the spelling
list; otherwise the built-in splitter and tips below are used.
"""

import re
from dataclasses import dataclass
from typing import List, Optional

from alfiebot.spelling.words import spell_out

VOWELS = set("aeiouy")
DIGRAPHS = ("ch", "sh", "th", "ph", "wh", "ck", "ng", "gh", "qu")

# Well-known memory tips for common primary school words.
TIPS = {
    "because": "Big Elephants Can Always Understand Small Elephants.",
    "said": "Sally Ann Is Dancing.",
    "friend": "A friend stays with you to the end, and friend ends with E-N-D.",
    "people": "People Eat Orange Peel, Licking Endlessly.",
    "could": "O U Lucky Duck.",
    "would": "O U Lucky Duck.",
    "should": "O U Lucky Duck.",
    "necessary": "One collar and two sleeves: one C and two S's.",
    "rhythm": "Rhythm Helps Your Two Hips Move.",
    "beautiful": "Big Elephants Are Ugly, but they're beautiful to me!",
    "island": "An island is land surrounded by water.",
    "separate": "There's a rat in separate.",
    "believe": "Never believe a lie.",
    "piece": "A piece of pie.",
    "favourite": "You are my favourite, and favourite has O-U, just like you.",
    "minute": "Wait a minute, I'm just a minute bit late.",
    "different": "Different has two Fs, because they're different from each other.",
}

# Patterns that usually make a word tricky, checked in this order.
TRICKY = [
    (r"(ough|augh|igh)", "the {part} that doesn't sound like it looks"),
    (r"ould", "the silent L in {part}"),
    (r"(.)\1", "the double {single}"),
    (r"(eau|ai|au|ie|ei|ea|our|ou)", "the {part}"),
    (r"(ph|wh|kn|wr|mb|gn)", "the {part}, which sounds different to how it looks"),
    (r"(tion|sion|ture|ful)$", "the ending, {part}"),
    (r"le$", "the ending, {part}"),
    (r"e$", "the silent E at the end"),
]


@dataclass
class WordHelp:
    word: str
    syllables: List[str]
    tip: str = ""
    sentence: str = ""

    @property
    def beats(self) -> str:
        """'be... cause' for speech."""
        return "... ".join(self.syllables)

    def tricky(self) -> str:
        """A sentence about the tricky part, with its letters spelled out."""
        for pattern, template in TRICKY:
            m = re.search(pattern, self.word)
            if m:
                part = m.group(0)
                if template.startswith("the double"):
                    return "Watch out for " + template.format(single=part[0].upper()) + "."
                if part == "e" and template.startswith("the silent E"):
                    return "Don't forget " + template + "."
                return "Watch out for " + template.format(part=spell_out(part)) + "."
        return ""


def word_help(word: str, syllables: str = "", tip: str = "", sentence: str = "") -> WordHelp:
    parts = [p for p in re.split(r"[-\s.]+", syllables.lower()) if p] if syllables else []
    if "".join(parts) != word:
        parts = split_syllables(word)
    return WordHelp(word, parts, tip.strip() or TIPS.get(word, ""), sentence.strip())


def split_syllables(word: str) -> List[str]:
    """A simple splitter for speech ("because" -> be, cause). It is only
    used to say the word in beats, so it doesn't need to be perfect."""
    word = word.lower()
    tail = ""
    m = re.search(r"[^aeiouy]le$", word)
    if m and len(word) > 4:
        word, tail = word[:m.start()], word[m.start():]  # peo + ple
    # A Y at the start is a consonant (yel-low).
    groups = [(g.start(), g.end()) for g in re.finditer(r"[aeiouy]+", "j" + word[1:] if word[0] == "y" else word)]
    if len(groups) > 1 and not tail and word.endswith("e") and groups[-1][0] == len(word) - 1:
        groups = groups[:-1]  # silent E: mi-nute
    cuts = []
    for (_, end), (start, _) in zip(groups, groups[1:]):
        between = word[end:start]
        if len(between) <= 1 or between in DIGRAPHS:
            cuts.append(end)  # be-cause, fa-ther
        else:
            cuts.append(end + 1)  # dif-fer
    parts, last = [], 0
    for cut in cuts:
        parts.append(word[last:cut])
        last = cut
    parts.append(word[last:])
    if tail:
        parts.append(tail)
    return [p for p in parts if p] or [word + tail]


def clue(help_: WordHelp, level: int) -> str:
    """Clue 1 and 2 never say more than the first and last letters."""
    word = help_.word
    if level <= 1:
        beats = len(help_.syllables)
        if beats > 1:
            return (f"Here's a clue. {word.capitalize()} has {len(word)} letters, and {beats} beats: "
                    f"{help_.beats}. Spell it one beat at a time.")
        return f"Here's a clue. {word.capitalize()} has {len(word)} letters."
    return (f"Here's a bigger clue. {word.capitalize()} starts with {word[0].upper()} "
            f"and ends with {word[-1].upper()}.")


def teach(help_: WordHelp) -> str:
    """The teaching step: beats, the tricky part, a memory tip, then the
    whole spelling, and an invitation to try straight away."""
    word = help_.word
    parts = [f"Let's learn {word} together."]
    if len(help_.syllables) > 1:
        parts.append(f"It has {len(help_.syllables)} beats: {help_.beats}.")
    tricky = help_.tricky()
    if tricky:
        parts.append(tricky)
    if help_.tip:
        parts.append(f"Here's a trick to remember it: {help_.tip}")
    parts.append(f"{word.capitalize()} is spelled {spell_out(word)}.")
    parts.append(f"Now you try. Spell {word}!")
    return " ".join(parts)


LETTER_RUN = re.compile(r"\b[a-z](?:(?:\s*[-,.]\s*|\s+)[a-z]\b)+", re.I)


def leaks_spelling(text: str, word: str, run: int = 3) -> bool:
    """True if ``text`` spells out ``run`` or more letters of ``word`` in a
    row (B-E-C, "b, e, c", "B E C"). Used to check any hint that isn't the
    teaching step itself, including one an AI might write."""
    word = word.lower()
    for m in LETTER_RUN.finditer(text):
        letters = re.sub(r"[^a-z]", "", m.group(0).lower())
        for i in range(len(letters) - run + 1):
            if letters[i:i + run] in word:
                return True
    return False


def first_mistake_note(word: str, answer: str) -> Optional[str]:
    """Something true and kind to say about a wrong answer, without letters."""
    prefix = 0
    for a, b in zip(word, answer):
        if a != b:
            break
        prefix += 1
    if prefix >= 2:
        return "You got the start right!"
    if len(answer) == len(word):
        return "You've got the right number of letters!"
    return None
