"""Letter recognition test: shows letters, you say them, it reports how
well they were recognised.

    python tools/letter_test.py --speaker Alfie              all 26 letters
    python tools/letter_test.py --speaker Mum --set confusing --speed slow
    python tools/letter_test.py --set B/D/P --rounds 3
    python tools/letter_test.py --report                     sum up every saved test
    python tools/letter_test.py --typed                      no microphone: type what was "heard"

Sets: all, confusing, B/D/P, C/G/T, M/N, F/S, A/H/J.
Results (not audio) are saved in data/letter_tests/. Audio is never saved.
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alfiebot.config import load_config  # noqa: E402
from alfiebot.spelling.letter_input import CHILD_WORDS, letter_grammar  # noqa: E402
from alfiebot.speech.factory import create_recognizer  # noqa: E402
from alfiebot.speech.letter_test import (LETTER_SETS, SPEEDS, LetterTestSession,  # noqa: E402
                                         format_report, load_trials)
from alfiebot.storage.json_store import JsonStore  # noqa: E402

TIMEOUT = 8.0


def listen(rec):
    """Wait for one result. Returns (text, words, confidence, latency) or None."""
    end = time.monotonic() + TIMEOUT
    speech_start = None
    while time.monotonic() < end:
        if speech_start is None and (getattr(rec, "partial", "") or getattr(rec, "level", 0) > 0.08):
            speech_start = time.monotonic()
        result = rec.poll()
        if result:
            latency = time.monotonic() - (speech_start or time.monotonic())
            return result.text, result.words, result.confidence, latency
        time.sleep(0.02)
    return None


def typed():
    text = input("  Heard (type it): ")
    return text, None, 1.0, 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--speaker", default="", help="who is speaking, e.g. Alfie")
    parser.add_argument("--speed", default="normal", choices=SPEEDS)
    parser.add_argument("--set", default="all", choices=sorted(LETTER_SETS))
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--report", action="store_true", help="sum up all saved tests and stop")
    parser.add_argument("--typed", action="store_true", help="type instead of using the microphone")
    args = parser.parse_args()
    config = load_config()
    store = JsonStore(config["data_dir"])

    if args.report:
        print(format_report(load_trials(store)))
        return 0

    rec = None
    if not args.typed:
        rec = create_recognizer(config)
        for _ in range(150):
            if rec.available or "Loading" not in rec.unavailable_reason:
                break
            time.sleep(0.1)
        if not rec.available:
            print(f"Speech recognition isn't available: {rec.unavailable_reason}")
            print("Try --typed to try the tool without a microphone.")
            return 1
        rec.set_grammar(letter_grammar(config.get("spelling", {}).get("phonetic_words", "child")))
        rec.start_listening()

    session = LetterTestSession(args.set, args.rounds, args.speaker, args.speed,
                                config["speech"].get("min_confidence", 0.75))
    print(f"Letter test: {len(session.prompts)} letters, speaker {session.speaker}, speed {args.speed}.")
    print("Say each letter when it appears. Press Ctrl+C to stop early (results so far are kept).\n")
    try:
        while not session.done:
            letter = session.current
            print(f"[{session.index + 1}/{len(session.prompts)}]   Say:  {letter.upper()}"
                  + ("   (again, e.g. \"" + letter.upper() + " for " + CHILD_WORDS[letter] + "\")"
                     if session.clarifying else ""))
            heard = typed() if rec is None else listen(rec)
            if heard is None:
                print("  (nothing heard)")
                session.nothing_heard()
                continue
            text, words, conf, latency = heard
            outcome = session.record(text, words, conf, latency)
            scores = ", ".join(f"{w} {c:.2f}" for w, c in (words or [])) or f"{conf:.2f}"
            print(f"  heard {text!r} ({scores}, {latency:.2f} s)")
            if outcome == "clarify":
                print("  Not sure. AlfieBot would ask again.")
            elif session.trials:
                t = session.trials[-1]
                print("  right" if t.correct else f"  wrong: got {t.final.upper() or 'nothing'}")
    except KeyboardInterrupt:
        print("\nStopped early.")
    finally:
        if rec is not None:
            rec.stop_listening()

    if session.trials:
        name = session.save(store)
        print(f"\nSaved results to data/{name}\n")
        print(format_report(session.trials))
    return 0


if __name__ == "__main__":
    sys.exit(main())
