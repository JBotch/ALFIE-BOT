"""Compare the two ways of spelling aloud, using synthetic voices only.

- **letter_by_letter**: each letter is its own utterance (a short pause,
  one letter, a pause), so each letter gets its own recognition result.
- **continuous**: the whole word's letters in one run, with a short gap
  between letters, recognised as one utterance.

Test words are made of letters that sound alike (B/D, M/N, P/T, F/S). For
each word and mode the report gives: right first time, how often AlfieBot
would have had to ask about a letter, wrong-but-sure answers (the risky
case), letter accuracy per pair, and the time per word (audio plus
recognition). It also checks the offline wake word with the same voices.

The audio comes from Piper voices on this computer (``synth``), and the
recogniser is passed in (``recognise``), so the tests here use fakes and
``tools/measure_voice.py`` uses the real Vosk model. No recordings of a
child are ever used or saved; only the results are kept.
"""

import random
import statistics
import time
from array import array
from dataclasses import asdict, dataclass
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from alfiebot.speech.base import RecognitionResult
from alfiebot.spelling.letter_input import Letter, parse_letters

RATE = 16000
MODES = ("letter_by_letter", "continuous")
PAIRS = ("bd", "mn", "pt", "fs")
TEST_WORDS = ["bed", "dab", "bid", "bud", "man", "nan", "mint", "name", "pat", "tap", "pet", "top",
              "fish", "self", "safe", "fast"]
WAKE_SENTENCES = ["hey alfie bot", "hi alfie bot"]
NOT_WAKE_SENTENCES = ["have a lovely day", "what is for tea", "hey everybody", "turn it off please",
                      "half a bottle"]

Synth = Callable[[str], bytes]  # text or a letter -> 16-bit mono audio at 16 kHz
Recognise = Callable[[bytes, Optional[List[str]]], Optional[RecognitionResult]]


@dataclass
class Trial:
    mode: str
    voice: str
    speed: float
    noise: float
    expected: str
    heard: str
    min_confidence: Optional[float]
    would_ask: bool
    correct: bool
    audio_s: float
    process_s: float


def silence(seconds: float) -> bytes:
    return b"\x00\x00" * int(RATE * seconds)


def add_noise(audio: bytes, level: float, rng: random.Random) -> bytes:
    """Mix in steady hiss (``level`` 0..1 of full scale), like a quiet room."""
    if level <= 0:
        return audio
    samples = array("h")
    samples.frombytes(audio)
    amp = 32767 * level
    for i, v in enumerate(samples):
        samples[i] = max(-32768, min(32767, int(v + rng.uniform(-amp, amp))))
    return samples.tobytes()


def seconds_of(audio: bytes) -> float:
    return len(audio) / 2 / RATE


def _letters(result: Optional[RecognitionResult]) -> List[Letter]:
    if result is None:
        return []
    return [t for t in parse_letters(result.text, result.words, result.confidence) if isinstance(t, Letter)]


def spell(word: str, mode: str, synth: Synth, recognise: Recognise, grammar: List[str],
          min_confidence: float = 0.75, gap_s: float = 0.45, noise: float = 0.0,
          rng: random.Random = None, voice: str = "", speed: float = 1.0) -> Trial:
    rng = rng or random.Random(0)
    heard, confidences, sure = "", [], True
    audio_s = process_s = 0.0
    if mode == "letter_by_letter":
        for letter in word:
            audio = add_noise(silence(0.3) + synth(letter) + silence(0.5), noise, rng)
            start = time.perf_counter()
            letters = _letters(recognise(audio, grammar))
            process_s += time.perf_counter() - start
            audio_s += seconds_of(audio)
            if len(letters) != 1:
                sure = False  # nothing or more than one: AlfieBot would ask
            if letters:
                heard += letters[0].letter
                confidences.append(letters[0].confidence)
                sure = sure and (letters[0].phonetic or letters[0].confidence >= min_confidence)
            else:
                heard += "?"
    else:
        parts = [silence(0.3)]
        for letter in word:
            parts += [synth(letter), silence(gap_s)]
        audio = add_noise(b"".join(parts) + silence(0.3), noise, rng)
        start = time.perf_counter()
        letters = _letters(recognise(audio, grammar))
        process_s = time.perf_counter() - start
        audio_s = seconds_of(audio)
        heard = "".join(t.letter for t in letters)
        confidences = [t.confidence for t in letters]
        sure = len(letters) == len(word) and all(t.phonetic or t.confidence >= min_confidence for t in letters)
    return Trial(mode, voice, speed, noise, word, heard, round(min(confidences), 3) if confidences else None,
                 not sure, heard == word, round(audio_s, 2), round(process_s, 3))


def compare(synth: Synth, recognise: Recognise, grammar: List[str], words: Sequence[str] = TEST_WORDS,
            modes: Sequence[str] = MODES, voice: str = "", speed: float = 1.0, noise: float = 0.0,
            min_confidence: float = 0.75, seed: int = 0) -> List[Trial]:
    rng = random.Random(seed)
    return [spell(word, mode, synth, recognise, grammar, min_confidence, noise=noise, rng=rng,
                  voice=voice, speed=speed)
            for mode in modes for word in words]


def check_wake(synth: Synth, recognise: Recognise, grammar: List[str], detector) -> Dict[str, int]:
    """How often the wake word fires for "Hey AlfieBot" and for other speech."""
    from alfiebot.speech.wake_word import GrammarWakeWord

    if detector is None:
        detector = GrammarWakeWord(type("Rec", (), {"available": True})(), enabled=True)
    out = {"wake_said": 0, "wake_heard": 0, "other_said": 0, "false_wakes": 0}
    for sentence in WAKE_SENTENCES:
        result = recognise(silence(0.3) + synth(sentence) + silence(0.5), grammar)
        out["wake_said"] += 1
        out["wake_heard"] += bool(result and detector.check(result))
    for sentence in NOT_WAKE_SENTENCES:
        result = recognise(silence(0.3) + synth(sentence) + silence(0.5), grammar)
        out["other_said"] += 1
        out["false_wakes"] += bool(result and detector.check(result))
    return out


# ---- report ---------------------------------------------------------------------
def _pct(part: float, whole: float) -> str:
    return f"{100 * part / whole:.0f}%" if whole else "-"


def summarise(trials: Iterable[Trial]) -> Dict[str, dict]:
    by_mode: Dict[str, dict] = {}
    for mode in MODES:
        ts = [t for t in trials if t.mode == mode]
        if not ts:
            continue
        letters = sum(len(t.expected) for t in ts)
        letters_right = sum(sum(a == b for a, b in zip(t.expected, t.heard)) for t in ts)
        pairs = {}
        for pair in PAIRS:
            said = [(a, b) for t in ts for a, b in zip(t.expected, t.heard.ljust(len(t.expected), "?"))
                    if a in pair]
            if said:
                pairs["/".join(pair.upper())] = (len(said), sum(a == b for a, b in said))
        by_mode[mode] = {
            "words": len(ts),
            "first_time": sum(t.correct and not t.would_ask for t in ts),
            "would_ask": sum(t.would_ask for t in ts),
            "wrong_but_sure": sum(not t.correct and not t.would_ask for t in ts),
            "letters": letters,
            "letters_right": letters_right,
            "seconds_per_word": statistics.mean(t.audio_s + t.process_s for t in ts),
            "pairs": pairs,
        }
    return by_mode


def format_report(trials: List[Trial], wake: Dict[str, int] = None, title: str = "") -> str:
    s = summarise(trials)
    lines = [f"# Spelling aloud: one letter at a time vs letters in a run{(': ' + title) if title else ''}", "",
             "Synthetic voices only (no recordings of a child). Words use letters that sound alike.", "",
             "| | One letter at a time | Letters in a run |", "|---|---|---|"]

    def row(label, fn):
        cells = [fn(s[m]) if m in s else "-" for m in MODES]
        lines.append(f"| {label} | {cells[0]} | {cells[1]} |")

    row("Words", lambda m: str(m["words"]))
    row("Right first time, no need to ask", lambda m: f"{m['first_time']} ({_pct(m['first_time'], m['words'])})")
    row("AlfieBot would ask about a letter", lambda m: f"{m['would_ask']} ({_pct(m['would_ask'], m['words'])})")
    row("Wrong but sure (the risky case)",
        lambda m: f"{m['wrong_but_sure']} ({_pct(m['wrong_but_sure'], m['words'])})")
    row("Letters heard right", lambda m: f"{m['letters_right']}/{m['letters']} ({_pct(m['letters_right'], m['letters'])})")
    row("Time per word (audio + recognition)", lambda m: f"{m['seconds_per_word']:.1f} s")
    for pair in ("/".join(p.upper()) for p in PAIRS):
        row(f"{pair} letters right", lambda m, p=pair: (f"{m['pairs'][p][1]}/{m['pairs'][p][0]}"
                                                        if p in m["pairs"] else "-"))
    if wake:
        lines += ["", "## Wake word", "",
                  f"- \"Hey AlfieBot\" heard {wake['wake_heard']} of {wake['wake_said']} times.",
                  f"- Woke by mistake {wake['false_wakes']} of {wake['other_said']} other sentences."]
    mistakes = [t for t in trials if not t.correct][:20]
    if mistakes:
        lines += ["", "## Words heard wrong", "", "| Mode | Voice | Said | Heard | Would ask |", "|---|---|---|---|---|"]
        lines += [f"| {t.mode} | {t.voice} x{t.speed:g} | {t.expected.upper()} | {t.heard.upper() or '(nothing)'} | "
                  f"{'yes' if t.would_ask else 'no'} |" for t in mistakes]
    return "\n".join(lines) + "\n"


def save(db, trials: List[Trial], run: str, machine: str, recogniser: str) -> None:
    with db.transaction() as conn:
        for t in trials:
            conn.execute("INSERT INTO letter_trials (run, at, machine, recogniser, mode, voice, speed, noise, "
                         "expected, heard, min_confidence, would_ask, correct, audio_s, process_s) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (run, time.time(), machine, recogniser, t.mode, t.voice, t.speed, t.noise, t.expected,
                          t.heard, t.min_confidence, int(t.would_ask), int(t.correct), t.audio_s, t.process_s))


def as_rows(trials: List[Trial]) -> List[dict]:
    return [asdict(t) for t in trials]
