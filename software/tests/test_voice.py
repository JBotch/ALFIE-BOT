"""Voice engine upgrade: speech planning, profiles, speak_letters, Piper and fallbacks."""

import sys
import tempfile
import threading
import types

import pytest

from alfiebot.config import load_config
from alfiebot.conversation.engine import Reply
from alfiebot.core.robot import AlfieBot
from alfiebot.core.states import Expression
from alfiebot.hardware.simulator import create_simulator_platform
from alfiebot.speech import tts as tts_module
from alfiebot.speech.null import TranscriptOnlyTTS
from alfiebot.speech.piper_tts import PiperTTS, _trim
from alfiebot.speech.text import Pause, Say, SayLetter, plan_speech
from alfiebot.speech.tts import create_tts, engine_order, wait_until_quiet
from alfiebot.speech.voice_profiles import DEFAULT_PROFILES, load_profiles, profile_for_reply

NORMAL = DEFAULT_PROFILES["normal"]
TEACHER = DEFAULT_PROFILES["teacher"]


# ---- planning what to say ---------------------------------------------------
def test_spelled_words_become_separate_letters_with_pauses():
    plan = plan_speech("Because is spelled B-E-C. Your turn!", TEACHER)
    assert plan[0] == Say("Because is spelled")
    assert [s.letter for s in plan if isinstance(s, SayLetter)] == ["B", "E", "C"]
    assert plan[2] == Pause(TEACHER.letter_pause)
    assert plan[-1] == Say("Your turn!")
    assert not isinstance(plan[-1], Pause)


def test_slow_letters_get_longer_gaps():
    plan = plan_speech("Okay. B... A... T...", NORMAL)
    gaps = [s.seconds for s in plan if isinstance(s, Pause)]
    assert [s.letter for s in plan if isinstance(s, SayLetter)] == ["B", "A", "T"]
    assert max(gaps) > NORMAL.letter_pause


def test_blanks_in_clues():
    plan = plan_speech("It goes B-E-_-_.", NORMAL)
    assert [s.letter for s in plan if isinstance(s, SayLetter)] == ["B", "E", "_", "_"]


def test_sentences_get_the_profile_pause_and_word_pauses_are_optional():
    plan = plan_speech("Hello there. How are you?", NORMAL)
    assert plan == [Say("Hello there."), Pause(NORMAL.sentence_pause), Say("How are you?")]
    slow = load_profiles({"voice_profiles": {"normal": {"word_pause": 0.2}}})["normal"]
    plan = plan_speech("Spell cat.", slow)
    assert plan[:3] == [Say("Spell"), Pause(0.2), Say("cat.")]


# ---- profiles --------------------------------------------------------------------
def test_four_profiles_and_config_overrides():
    assert set(DEFAULT_PROFILES) == {"normal", "excited", "teacher", "sleepy"}
    assert DEFAULT_PROFILES["teacher"].rate < 1 < DEFAULT_PROFILES["excited"].rate
    assert DEFAULT_PROFILES["sleepy"].volume < 1
    profiles = load_profiles({"voice_profiles": {"teacher": {"letter_pause": 0.9, "bogus": 1},
                                                 "_comment": "x"}})
    assert profiles["teacher"].letter_pause == 0.9 and profiles["teacher"].rate == TEACHER.rate


def test_profile_chosen_for_each_reply():
    assert profile_for_reply(Reply("Hi!", "hello", Expression.HAPPY)) == "normal"
    assert profile_for_reply(Reply("Yay!", "x", Expression.EXCITED, celebrate=True)) == "excited"
    assert profile_for_reply(Reply("Night night", "goodbye", Expression.HAPPY, then="sleep")) == "sleepy"
    assert profile_for_reply(Reply("Spell cat.", "spelling_test", Expression.LISTENING), "test") == "teacher"
    # Praise that goes on to spell the next word keeps the clear teacher voice.
    praise = Reply("Brilliant! Word 2 is dog. It's spelled D-O-G.", "spelling_practice",
                   Expression.EXCITED, celebrate=True)
    assert profile_for_reply(praise, "practice") == "teacher"


def make_robot(**speech):
    config = load_config()
    config["data_dir"] = tempfile.mkdtemp(prefix="alfiebot-test-")
    config["speech"].update(speech)
    platform = create_simulator_platform(config, speech=False)
    return AlfieBot(config, platform), platform.tts


def run(robot, seconds=3.0):
    for _ in range(int(seconds * 30)):
        robot.update(1 / 30)


def test_robot_switches_profiles():
    robot, tts = make_robot()
    robot.start()
    robot.handle_text("Hey AlfieBot")
    run(robot)
    robot.handle_text("What's your name?")
    run(robot)
    assert tts.profiles_used[-1] == "normal"
    robot.spelling_lists.add_words(robot.tutor.active_week, ["cat"])
    robot.start_spelling("test")
    run(robot, 1.0)
    assert tts.profiles_used[-1] == "teacher"
    robot.voice_profile = "sleepy"  # the panel can fix one profile
    robot.handle_text("repeat")
    run(robot, 20.0)
    assert tts.profiles_used[-1] == "sleepy"


def test_slower_profiles_take_longer():
    text = "Brilliant! You spelled because. B-E-C-A-U-S-E."
    excited = TranscriptOnlyTTS.estimate_seconds(text, DEFAULT_PROFILES["excited"])
    sleepy = TranscriptOnlyTTS.estimate_seconds(text, DEFAULT_PROFILES["sleepy"])
    assert sleepy > excited * 1.3


def test_default_speak_letters_spells_never_says_the_word():
    tts = TranscriptOnlyTTS()
    tts.speak_letters("because", repeat=2)
    assert tts.spoken[-1] == "B-E-C-A-U-S-E B-E-C-A-U-S-E"


# ---- engine choice and fallback ----------------------------------------------
def test_engine_order_prefers_piper():
    assert engine_order("auto")[0] == "piper"
    assert engine_order("espeak") == ["espeak"]


def test_missing_piper_voice_falls_back(monkeypatch, tmp_path):
    monkeypatch.setattr(tts_module.shutil, "which", lambda name: None)  # no espeak / PowerShell
    tts = create_tts({"speech": {"tts_engine": "auto", "piper_voice": str(tmp_path / "nope.onnx")}})
    assert isinstance(tts, TranscriptOnlyTTS)
    assert "piper" in tts.fallback_reason and "download_voice" in tts.fallback_reason


def test_unavailable_engine_named_in_config_falls_back_to_transcript(monkeypatch):
    monkeypatch.setattr(tts_module.shutil, "which", lambda name: None)
    tts = create_tts({"speech": {"tts_engine": "espeak"}})
    assert isinstance(tts, TranscriptOnlyTTS) and "espeak" in tts.fallback_reason


# ---- Piper with stand-in piper and sounddevice modules -------------------------
class FakeStream:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.data = bytearray()
        self.state = "new"
        FakeSD.streams.append(self)

    def start(self):
        self.state = "started"

    def write(self, data):
        self.data += data

    def stop(self):
        self.state = "stopped"

    def abort(self):
        self.state = "aborted"

    def close(self):
        pass


class FakeSD:
    streams = []
    RawOutputStream = FakeStream


class FakeVoice:
    calls = []
    gate = None

    def __init__(self):
        self.config = types.SimpleNamespace(sample_rate=1000)

    def synthesize(self, text, syn_config=None):
        FakeVoice.calls.append((text, syn_config))
        if FakeVoice.gate is not None:
            FakeVoice.gate.wait(2)
        # 0.1 s of "sound" per character, quiet edges for letters.
        loud = (b"\x00\x10" * 100) * len(text)
        yield types.SimpleNamespace(audio_int16_bytes=b"\x00\x00" * 50 + loud + b"\x00\x00" * 50)


class FakeConfig:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


fake_piper = types.SimpleNamespace(PiperVoice=types.SimpleNamespace(load=lambda path: FakeVoice()),
                                   SynthesisConfig=FakeConfig)


@pytest.fixture
def piper(tmp_path):
    model = tmp_path / "en_GB-test-medium.onnx"
    model.write_bytes(b"")
    FakeVoice.calls.clear()
    FakeVoice.gate = None
    FakeSD.streams.clear()
    return PiperTTS(model, volume=80, piper_module=fake_piper, sounddevice_module=FakeSD)


def test_piper_speaks_sentences_and_separate_letters(piper):
    piper.speak("Spell cat. C-A-T.", "teacher")
    wait_until_quiet(piper, 5)
    texts = [text for text, _ in FakeVoice.calls]
    assert texts == ["Spell cat.", "C", "ay", "T"]  # each letter made on its own
    syn = FakeVoice.calls[0][1]
    assert syn.length_scale == pytest.approx(1 / TEACHER.rate)  # slower
    assert syn.volume == pytest.approx(0.8)
    stream = FakeSD.streams[-1]
    assert stream.kwargs["samplerate"] == 1000 and stream.state == "stopped"
    # The letter gaps are real silence in the audio.
    assert stream.data.count(b"\x00\x00" * int(1000 * TEACHER.letter_pause)) >= 2


def test_piper_letters_are_cached_and_trimmed(piper):
    piper.speak_letters("tt")
    wait_until_quiet(piper, 5)
    assert [text for text, _ in FakeVoice.calls] == ["T"]
    raw = b"\x00\x00" * 1000 + b"\x00\x10" * 10 + b"\x00\x00" * 1000
    assert len(_trim(raw)) < len(raw)


def test_piper_profiles_change_speed_and_expressiveness(piper):
    piper.speak("Hooray!", "excited")
    wait_until_quiet(piper, 5)
    piper.speak("Night night.", "sleepy")
    wait_until_quiet(piper, 5)
    excited, sleepy = FakeVoice.calls[0][1], FakeVoice.calls[1][1]
    assert excited.length_scale < sleepy.length_scale
    assert excited.noise_scale > sleepy.noise_scale
    assert excited.volume > sleepy.volume
    piper.speed = 1.2
    piper.speak("Faster.", "normal")
    wait_until_quiet(piper, 5)
    assert FakeVoice.calls[-1][1].length_scale == pytest.approx(1 / 1.2)


def test_piper_can_be_stopped(piper):
    FakeVoice.gate = threading.Event()
    piper.speak("One. Two. Three. Four.")
    assert piper.speaking
    piper.stop()
    FakeVoice.gate.set()
    wait_until_quiet(piper, 3)
    assert not piper.speaking
    assert len(FakeVoice.calls) <= 2


def test_piper_not_installed_is_reported(tmp_path, monkeypatch):
    model = tmp_path / "v.onnx"
    model.write_bytes(b"")
    monkeypatch.setitem(sys.modules, "piper", None)  # import piper -> ImportError
    with pytest.raises(RuntimeError, match="pip install piper-tts"):
        PiperTTS(model, sounddevice_module=FakeSD)
