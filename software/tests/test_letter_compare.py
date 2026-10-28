"""The spelling-aloud comparison and the voice measurement tool, with a
pretend voice and recogniser (no audio, no models)."""

import json
import sys
import types

from alfiebot.speech import letter_compare as lc
from alfiebot.speech.base import RecognitionResult
from alfiebot.spelling.words import LETTER_NAMES
from alfiebot.storage.database import Database


def synth(text):
    return text.encode("ascii") + b"|"


def recogniser(confuse_in_a_run=False, low=()):
    """Hears what was said. In a run, it mixes up B and D (sure of it, the
    risky case); letters in ``low`` come back unsure."""
    def recognise(audio, grammar):
        said = [p for p in audio.replace(b"\x00", b"").decode("ascii").split("|") if p]
        if not said:
            return None
        run = len(said) > 1
        words = []
        for s in said:
            if confuse_in_a_run and run and s == "b":
                s = "d"
            name = LETTER_NAMES[s][0] if len(s) == 1 else s
            words += [(w, 0.4 if s in low else 0.95) for w in name.split()]
        return RecognitionResult(" ".join(w for w, _ in words), 0.9, "voice", words)
    return recognise


def test_one_letter_at_a_time_vs_a_run():
    trials = lc.compare(synth, recogniser(confuse_in_a_run=True), [], words=["bed", "man"])
    s = lc.summarise(trials)
    assert s["letter_by_letter"]["first_time"] == 2
    assert s["continuous"]["first_time"] == 1 and s["continuous"]["wrong_but_sure"] == 1
    assert s["continuous"]["pairs"]["B/D"] == (2, 1)
    report = lc.format_report(trials)
    assert "Letters in a run" in report and "| continuous |" in report and "BED | DED" in report


def test_unsure_letters_count_as_asking_not_wrong():
    trials = lc.compare(synth, recogniser(low=("m",)), [], words=["man"], modes=["letter_by_letter"])
    t = trials[0]
    assert t.correct and t.would_ask and t.min_confidence == 0.4


def test_nothing_heard_is_a_question_mark():
    trials = lc.compare(synth, lambda audio, grammar: None, [], words=["pat"])
    assert trials[0].heard == "???" and trials[0].would_ask
    assert trials[1].heard == "" and trials[1].would_ask


def test_wake_word_check_counts_false_wakes():
    def always_wake(audio, grammar):
        return RecognitionResult("hey alfie bot", 0.9, "voice", [("hey", 0.9), ("alfie", 0.9), ("bot", 0.9)])
    result = lc.check_wake(synth, always_wake, [], None)
    assert result["wake_heard"] == result["wake_said"] and result["false_wakes"] == result["other_said"]


def test_results_are_saved_without_audio(tmp_path):
    db = Database(tmp_path)
    lc.save(db, lc.compare(synth, recogniser(), [], words=["fish"]), "run1", "test", "fake")
    rows = db.query("SELECT * FROM letter_trials")
    assert len(rows) == 2 and {r["mode"] for r in rows} == set(lc.MODES)
    assert "audio" not in {r[0] for r in db.query("SELECT name FROM pragma_table_info('letter_trials')")}


def test_noise_is_repeatable():
    import random

    audio = lc.silence(0.1)
    assert lc.add_noise(audio, 0.01, random.Random(1)) == lc.add_noise(audio, 0.01, random.Random(1))
    assert lc.add_noise(audio, 0.0, random.Random(1)) == audio


def test_measure_tool_runs_with_the_fake_backend(tmp_path):
    from tools import measure_voice

    assert measure_voice.main(["--fake", "--no-db", "--out", str(tmp_path)]) == 0
    report = next(tmp_path.glob("voice_*.md")).read_text(encoding="utf-8-sig")
    assert "One letter at a time" in report and "Wake word" in report
    assert next(tmp_path.glob("voice_*.csv")).exists()


def test_vosk_adapter_joins_results(monkeypatch):
    class Kaldi:
        def __init__(self, model, rate, grammar=None):
            self.grammar = json.loads(grammar) if grammar else None
            self.n = 0

        def SetWords(self, on):
            pass

        def AcceptWaveform(self, chunk):
            self.n += 1
            return self.n == 2  # one result part-way through

        def Result(self):
            return json.dumps({"text": "bee", "result": [{"word": "bee", "conf": 0.9}]})

        def FinalResult(self):
            return json.dumps({"text": "dee", "result": [{"word": "dee", "conf": 0.5}]})

    fake = types.SimpleNamespace(SetLogLevel=lambda n: None, Model=lambda path: object(), KaldiRecognizer=Kaldi)
    monkeypatch.setitem(sys.modules, "vosk", fake)
    from tools import measure_voice

    recognise = measure_voice.vosk_recogniser("model")
    result = recognise(lc.silence(1.0), ["bee", "dee"])
    assert result.text == "bee dee" and result.words == [("bee", 0.9), ("dee", 0.5)]
    assert abs(result.confidence - 0.7) < 1e-9
