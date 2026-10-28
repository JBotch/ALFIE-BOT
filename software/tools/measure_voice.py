"""Measure spelling aloud and the wake word on this computer, with
synthetic voices only.

    python tools/measure_voice.py                      # every installed Piper voice, speeds 0.85 / 1.0 / 1.2
    python tools/measure_voice.py --noise 0 0.02       # also with a little background hiss
    python tools/measure_voice.py --fake               # no Vosk or Piper needed: tries the tool itself

Piper (the voices in models/piper) says letters and short phrases, and the
Vosk speech model hears them, exactly as AlfieBot would: once one letter at
a time, and once as a run of letters. The words are made of letters that
sound alike (B/D, M/N, P/T, F/S). It also says "Hey AlfieBot" and some
other sentences to check the wake word.

Saves a Markdown report and a CSV in benchmarks/results/, and the results
(not the audio) in data/alfiebot.db. Audio is made in memory and never
saved. Nothing is downloaded: install the speech model and a voice first
(tools/download_speech_model.py, tools/download_voice.py).
"""

import argparse
import csv
import datetime as dt
import json
import re
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alfiebot.ai.performance import machine_label  # noqa: E402
from alfiebot.config import load_config  # noqa: E402
from alfiebot.speech import letter_compare as lc  # noqa: E402
from alfiebot.speech.base import RecognitionResult  # noqa: E402
from alfiebot.speech.factory import model_path  # noqa: E402
from alfiebot.speech.vosk_recognizer import parse_result  # noqa: E402
from alfiebot.speech.wake_word import WAKE_PHRASES  # noqa: E402
from alfiebot.spelling.letter_input import letter_grammar  # noqa: E402
from alfiebot.storage.database import Database  # noqa: E402


def vosk_recogniser(path: Path):
    import vosk

    vosk.SetLogLevel(-1)
    model = vosk.Model(str(path))

    def recognise(audio: bytes, grammar):
        rec = (vosk.KaldiRecognizer(model, lc.RATE, json.dumps(list(grammar) + ["[unk]"])) if grammar
               else vosk.KaldiRecognizer(model, lc.RATE))
        rec.SetWords(True)
        parts = []
        step = int(lc.RATE * 0.1) * 2
        for i in range(0, len(audio), step):
            if rec.AcceptWaveform(audio[i:i + step]):
                parts.append(parse_result(rec.Result()))
        parts.append(parse_result(rec.FinalResult()))
        parts = [p for p in parts if p is not None]
        if not parts:
            return None
        words = [w for p in parts for w in p.words]
        confidence = sum(c for _, c in words) / len(words) if words else parts[0].confidence
        return RecognitionResult(" ".join(p.text for p in parts), confidence, "voice", words)

    return recognise


def piper_synth(model_file: Path, speed: float):
    """Returns synth(text) -> 16 kHz audio. Letters are said by name, the
    same way AlfieBot says them."""
    from alfiebot.speech.piper_tts import PiperTTS, resample
    from alfiebot.speech.voice_profiles import DEFAULT_PROFILES

    # Nothing is played: a stand-in for the sound card.
    tts = PiperTTS(model_file, speed=speed, sounddevice_module=types.SimpleNamespace())
    profile = DEFAULT_PROFILES["normal"]
    cache = {}

    def synth(text: str) -> bytes:
        if text not in cache:
            audio = tts.letter_audio(text, profile) if len(text) == 1 else tts.synthesize(text, profile)
            cache[text] = resample(audio, tts.sample_rate / lc.RATE)
        return cache[text]

    return synth


def fake_backend():
    """A pretend voice and recogniser: letters come back as their names."""
    from alfiebot.spelling.words import LETTER_NAMES

    def synth(text: str) -> bytes:
        return text.encode("ascii") + b"|"

    def recognise(audio: bytes, grammar):
        said = [p for p in audio.replace(b"\x00", b"").decode("ascii").split("|") if p]
        if not said:
            return None
        words = [LETTER_NAMES[s][0] if len(s) == 1 else s for s in said]
        text = " ".join(words)
        return RecognitionResult(text, 0.9, "voice", [(w, 0.9) for w in text.split()])

    return synth, recognise


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--voices", nargs="*", help="Piper voice names (default: every installed voice)")
    p.add_argument("--speeds", nargs="+", type=float, default=[0.85, 1.0, 1.2])
    p.add_argument("--noise", nargs="+", type=float, default=[0.0])
    p.add_argument("--fake", action="store_true", help="pretend voice and recogniser, to try the tool")
    p.add_argument("--out", default=str(ROOT / "benchmarks" / "results"))
    p.add_argument("--no-db", action="store_true")
    args = p.parse_args(argv)

    config = load_config()
    machine = machine_label()
    grammar = letter_grammar(config["spelling"].get("phonetic_words", "child"))
    trials, wake = [], {"wake_said": 0, "wake_heard": 0, "other_said": 0, "false_wakes": 0}
    if args.fake:
        recogniser_name = "fake"
        backends = [("fake", 1.0, *fake_backend())]
    else:
        from alfiebot.speech.piper_tts import installed_voices, voice_dir

        path = model_path(config)
        if not path.is_dir():
            print(f"No speech model at {path}. Run: python tools/download_speech_model.py")
            return 1
        voices = args.voices or installed_voices(config)
        if not voices:
            print("No Piper voices installed. Run: python tools/download_voice.py")
            return 1
        recogniser_name = f"Vosk {path.name}"
        print(f"Loading {recogniser_name}...")
        recognise = vosk_recogniser(path)
        backends = [(v, s, piper_synth(voice_dir(config) / f"{v}.onnx", s), recognise)
                    for v in voices for s in args.speeds]

    for voice, speed, synth, recognise in backends:
        for noise in args.noise:
            print(f"{voice} x{speed:g}, noise {noise:g}...")
            trials += lc.compare(synth, recognise, grammar, voice=voice, speed=speed, noise=noise,
                                 min_confidence=config["speech"].get("min_confidence", 0.75))
        result = lc.check_wake(synth, recognise, WAKE_PHRASES, None)
        for k, v in result.items():
            wake[k] += v

    stem = f"voice_{dt.datetime.now():%Y%m%d-%H%M}_{re.sub(r'[^A-Za-z0-9]+', '-', machine).strip('-')}"
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report = lc.format_report(trials, wake, f"{machine}, {recogniser_name}")
    (out / f"{stem}.md").write_text(report, encoding="utf-8-sig")
    with open(out / f"{stem}.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(lc.as_rows(trials[:1])[0]) if trials else ["mode"])
        writer.writeheader()
        writer.writerows(lc.as_rows(trials))
    if not args.no_db:
        lc.save(Database(config["data_dir"]), trials, stem, machine, recogniser_name)
    print()
    print(report)
    print(f"Saved {out / (stem + '.md')} and .csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
