import json
import os
import stat
import sys
import time
import types

import pytest

from alfiebot.speech.base import RecognitionResult
from alfiebot.speech.mic_gate import MicGate  # noqa: F401  (imported for completeness)
from alfiebot.speech.null import TranscriptOnlyTTS
from alfiebot.speech.text import for_speech
from alfiebot.speech import tts as tts_module
from alfiebot.speech.tts import EspeakTTS, WindowsTTS, create_tts, wait_until_quiet
from alfiebot.speech.vosk_recognizer import VoskRecognizer, parse_result

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="uses a shell script as a fake engine")


def test_for_speech_spells_letters_with_pauses():
    assert for_speech("Because. B-E-C-A-U-S-E. Is that correct?") == \
        "Because. B, E, C, ay, U, S, E. Is that correct?"
    assert for_speech("It goes B-E-C-_-_.") == "It goes B, E, C, blank, blank."
    assert for_speech("Hi, I'm AlfieBot!") == "Hi, I'm Alfie Bot!"
    assert for_speech("Okay. B... A... T...") == "Okay. B... ay... T..."


def fake_engine(tmp_path, body):
    path = tmp_path / "engine.sh"
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


@posix_only
def test_espeak_runs_in_background_says_letters_separately_and_can_be_stopped(tmp_path):
    out = tmp_path / "said.txt"
    cmd = fake_engine(tmp_path, f'cat >> "{out}"\necho "|$*" >> "{out}"\nsleep 0.05\n')
    tts = EspeakTTS(command=cmd)
    tts.speak("Because. B-E-C.", profile="teacher")
    assert tts.speaking  # returns at once; doesn't block the animation
    wait_until_quiet(tts, 10)
    assert not tts.speaking
    calls = out.read_text().strip().split("\n")
    said = [c.split("|")[0] for c in calls]
    assert said == ["Because.", "B", "E", "C"]  # one letter per call, never "bec"
    assert all("-s 140" in c for c in calls)  # teacher: slower (160 words a minute x 0.88)
    tts.speak("A long sentence. And another one. And more.")
    tts.stop()
    assert not tts.speaking


@posix_only
def test_espeak_profiles_change_pitch_and_volume(tmp_path):
    tts = EspeakTTS(command=fake_engine(tmp_path, "cat > /dev/null\n"))
    excited, sleepy = tts.args(tts.profile("excited")), tts.args(tts.profile("sleepy"))
    assert int(excited[excited.index("-p") + 1]) > int(sleepy[sleepy.index("-p") + 1])
    assert int(excited[excited.index("-a") + 1]) > int(sleepy[sleepy.index("-a") + 1])


@posix_only
def test_windows_voice_protocol(tmp_path):
    # Stands in for PowerShell: READY first, then DONE after each line.
    log_file = tmp_path / "lines.txt"
    cmd = fake_engine(tmp_path, 'echo "READY Test Voice"\nwhile read line; do echo "$line" >> '
                      f'"{log_file}"; '
                      'if [ "$line" = "#VOICES" ]; then echo "VOICE Microsoft Hazel Desktop"; fi; '
                      'sleep 0.05; echo DONE; done\n')
    tts = WindowsTTS(command=cmd, voice="Hazel'; rm -rf /")
    assert "$want = 'Hazel rm -rf '" in tts.script  # quotes stripped: stays a plain name
    tts.speak("Hello there")
    assert tts.speaking
    wait_until_quiet(tts, 5)
    assert not tts.speaking
    assert tts.voice_name == "Test Voice"
    tts.speak("Spell it. C-A-T.", profile="sleepy")
    wait_until_quiet(tts, 5)
    lines = log_file.read_text().split("\n")
    assert lines[:1] == ["Hello there"]
    assert "#RATE -2" in lines and "#VOLUME 63" in lines  # sleepy: slower and quieter
    assert lines[-5:-1] == ["Spell it.", "C", "ay", "T"]
    tts.speak("Interrupt me. Please do.")
    tts.stop()
    assert not tts.speaking
    tts.speak("Back again")  # restarts the engine after a stop
    wait_until_quiet(tts, 5)
    assert not tts.speaking
    assert tts.available_voices() == ["Microsoft Hazel Desktop"]
    tts.close()


def test_create_tts_falls_back_to_transcript(monkeypatch):
    assert isinstance(create_tts({"speech": {"tts_engine": "none"}}), TranscriptOnlyTTS)
    monkeypatch.setattr(tts_module.shutil, "which", lambda name: None)
    assert isinstance(create_tts({"speech": {"tts_engine": "espeak"}}), TranscriptOnlyTTS)
    assert isinstance(create_tts({"speech": {"tts_engine": "windows"}}), TranscriptOnlyTTS)


def test_transcript_tts_still_takes_time():
    tts = TranscriptOnlyTTS()
    tts.speak("Hello there, how are you?")
    assert tts.speaking
    tts.update(5.0)
    assert not tts.speaking


def test_parse_vosk_result():
    raw = json.dumps({"text": "how are you", "result": [
        {"word": "how", "conf": 1.0}, {"word": "are", "conf": 0.8}, {"word": "you", "conf": 0.6}]})
    result = parse_result(raw)
    assert result.text == "how are you" and abs(result.confidence - 0.8) < 1e-9
    assert parse_result(json.dumps({"text": ""})) is None
    assert parse_result(json.dumps({"text": "[unk]"})) is None
    assert parse_result(json.dumps({"text": "the"})) is None


# ---- Vosk recogniser with fake vosk and sounddevice modules --------------

class FakeKaldi:
    def __init__(self, model, rate, grammar=None):
        self.grammar = json.loads(grammar) if grammar else None
        self.heard = []
        FakeVosk.recognizers.append(self)

    def SetWords(self, on):
        pass

    def AcceptWaveform(self, chunk):
        if chunk == b"\x00\x00" * 4:  # silence = end of an utterance
            return bool(self.heard)
        self.heard.append(chunk.decode("latin-1").strip("\x00"))
        return False

    def _json(self):
        text = " ".join(self.heard)
        self.heard = []
        return json.dumps({"text": text, "result": [{"word": w, "conf": 0.9} for w in text.split()]})

    def Result(self):
        return self._json()

    def FinalResult(self):
        return self._json()

    def PartialResult(self):
        return json.dumps({"partial": " ".join(self.heard)})


class FakeVosk:
    recognizers = []
    Model = staticmethod(lambda path: object())
    KaldiRecognizer = FakeKaldi


class FakeStream:
    def __init__(self, callback, **kwargs):
        self.callback = callback
        self.kwargs = kwargs
        self.started = self.closed = False
        FakeSoundDevice.streams.append(self)

    def start(self):
        self.started = True

    def stop(self):
        pass

    def close(self):
        self.closed = True


class FakeSoundDevice:
    streams = []
    RawInputStream = FakeStream


def word(text):
    data = text.encode("latin-1")
    return data + b"\x00" * (len(data) % 2)


def wait_for(fn, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = fn()
        if value:
            return value
        time.sleep(0.01)
    return None


@pytest.fixture
def recogniser(tmp_path):
    FakeVosk.recognizers.clear()
    FakeSoundDevice.streams.clear()
    rec = VoskRecognizer(tmp_path, vosk_module=FakeVosk, sounddevice_module=FakeSoundDevice)
    assert wait_for(lambda: rec.available)
    return rec


def test_missing_model_is_reported(tmp_path):
    rec = VoskRecognizer(tmp_path / "nope", vosk_module=FakeVosk, sounddevice_module=FakeSoundDevice)
    assert wait_for(lambda: "download_speech_model" in rec.unavailable_reason)
    assert not rec.available


def test_listening_opens_and_closes_the_microphone(recogniser):
    assert not recogniser.listening
    recogniser.start_listening()
    stream = FakeSoundDevice.streams[-1]
    assert recogniser.listening and stream.started
    assert stream.kwargs["samplerate"] == 16000
    recogniser.stop_listening()
    assert not recogniser.listening and stream.closed


def test_speech_becomes_a_result(recogniser):
    recogniser.start_listening()
    cb = FakeSoundDevice.streams[-1].callback
    cb(word("how"), 0, None, None)
    cb(word("are you"), 0, None, None)
    assert wait_for(lambda: recogniser.partial)
    cb(b"\x00\x00" * 4, 0, None, None)
    result = wait_for(recogniser.poll)
    assert isinstance(result, RecognitionResult)
    assert result.text == "how are you" and result.source == "voice"
    assert recogniser.level >= 0


def test_push_to_talk_release_keeps_what_was_said(recogniser):
    recogniser.start_listening()
    FakeSoundDevice.streams[-1].callback(word("bee"), 0, None, None)
    recogniser.stop_listening(finalise=True)
    result = wait_for(recogniser.poll)
    assert result.text == "bee"


def test_stopping_without_finalise_drops_half_heard_audio(recogniser):
    recogniser.start_listening()
    FakeSoundDevice.streams[-1].callback(word("half"), 0, None, None)
    recogniser.stop_listening()
    time.sleep(0.2)
    assert recogniser.poll() is None


def test_grammar_is_passed_to_vosk(recogniser):
    recogniser.set_grammar(["bee", "see"])
    recogniser.start_listening()
    FakeSoundDevice.streams[-1].callback(word("bee"), 0, None, None)
    assert wait_for(lambda: FakeVosk.recognizers and FakeVosk.recognizers[-1].grammar == ["bee", "see", "[unk]"])


def test_unusable_vosk_module_is_reported(tmp_path):
    broken = types.SimpleNamespace(Model=lambda path: (_ for _ in ()).throw(OSError("bad model")))
    rec = VoskRecognizer(tmp_path, vosk_module=broken, sounddevice_module=FakeSoundDevice)
    assert wait_for(lambda: "bad model" in rec.unavailable_reason)


def test_no_audio_files_are_written(recogniser, tmp_path):
    before = set(os.listdir(tmp_path))
    recogniser.start_listening()
    FakeSoundDevice.streams[-1].callback(word("hello"), 0, None, None)
    recogniser.stop_listening(finalise=True)
    wait_for(recogniser.poll)
    assert set(os.listdir(tmp_path)) == before
