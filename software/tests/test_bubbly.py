"""Bubbly Bot: personalities, pitch, sound effects, the online comparison voice
and the voice test screen."""

import tempfile
import types

import pytest

from alfiebot.config import load_config
from alfiebot.conversation.engine import Reply
from alfiebot.core.robot import AlfieBot
from alfiebot.core.states import Expression
from alfiebot.hardware.simulator import create_simulator_platform
from alfiebot.speech import piper_tts
from alfiebot.speech.cloud_tts import CloudTTS
from alfiebot.speech.null import TranscriptOnlyTTS
from alfiebot.speech.sounds import EFFECTS, RATE, SoundEffects, make_effect, personality_sounds
from alfiebot.speech.tts import EspeakTTS, _build, engine_order, wait_until_quiet
from alfiebot.speech.voice_profiles import DEFAULT_PROFILES, PERSONALITIES, get_personality

from tests.test_voice import FakeSD, FakeVoice, fake_piper


# ---- personalities and profiles -------------------------------------------
def test_bubbly_profiles_exist_and_are_selectable():
    bubbly = get_personality("bubbly")
    assert bubbly.roles["normal"] == "bubbly_conversation"
    assert bubbly.roles["teacher"] == "clear_spelling_teacher"
    for name in bubbly.roles.values():
        assert name in DEFAULT_PROFILES
    assert set(PERSONALITIES) >= {"classic", "bubbly"}
    assert get_personality("nonsense").name == "classic"


def test_bubbly_is_livelier_and_the_teacher_is_slower_and_clearer():
    chat = DEFAULT_PROFILES["bubbly_conversation"]
    teacher = DEFAULT_PROFILES["clear_spelling_teacher"]
    classic = DEFAULT_PROFILES["normal"]
    # Personality comes from pacing and expression, not only pitch.
    assert chat.rate > classic.rate and chat.expressiveness > classic.expressiveness
    assert chat.sentence_pause < classic.sentence_pause
    assert 0 < chat.pitch <= 4  # a little higher, not squeaky
    assert teacher.rate < chat.rate and teacher.letter_pause > chat.letter_pause
    assert teacher.expressiveness < chat.expressiveness  # steadier, clearer letters


def make_robot(**speech):
    config = load_config()
    config["data_dir"] = tempfile.mkdtemp(prefix="alfiebot-test-")
    config["speech"].update(speech)
    platform = create_simulator_platform(config, speech=False)
    platform.sounds = SoundEffects(player=lambda data: None)
    return AlfieBot(config, platform), platform


def run(robot, seconds=3.0):
    for _ in range(int(seconds * 30)):
        robot.update(1 / 30)


def test_bubbly_robot_uses_bubbly_profiles_and_the_spelling_teacher():
    robot, platform = make_robot(personality="bubbly")
    tts = platform.tts
    robot.start()
    robot.handle_text("Hey AlfieBot")
    run(robot)
    robot.handle_text("What's your name?")
    run(robot)
    assert tts.profiles_used[-1] == "bubbly_conversation"
    robot.spelling_lists.add_words(robot.tutor.active_week, ["cat"])
    robot.start_spelling("test")
    run(robot, 1.0)
    assert tts.profiles_used[-1] == "clear_spelling_teacher"


def test_sounds_play_for_bubbly_only():
    robot, platform = make_robot(personality="bubbly")
    robot.start()
    robot.handle_text("Hey AlfieBot")
    run(robot)
    assert platform.sounds.played[0] == "wake"
    assert "listen" in platform.sounds.played
    robot.play_sound("celebrate")
    assert platform.sounds.played[-1] == "celebrate"

    robot, platform = make_robot(personality="classic")
    robot.start()
    robot.handle_text("Hey AlfieBot")
    run(robot)
    assert platform.sounds.played == []


def test_bubbly_cheers_only_on_celebrations_and_never_repeat():
    robot, _ = make_robot(personality="bubbly")
    robot._rng.random = lambda: 0.0
    praise = Reply("You did it!", "x", Expression.EXCITED, celebrate=True)
    cheers = []
    for _ in range(10):
        text = robot._add_cheer(praise).text
        assert text.endswith(" You did it!")
        cheers.append(robot._last_cheer)
    assert all(a != b for a, b in zip(cheers, cheers[1:]))
    plain = Reply("Hello.", "hello", Expression.HAPPY)
    assert robot._add_cheer(plain).text == "Hello."
    robot.personality = "classic"
    assert robot._add_cheer(praise).text == "You did it!"


# ---- sound effects -----------------------------------------------------------
def test_effects_are_short_and_quiet():
    for name in EFFECTS:
        audio = make_effect(name, 0.5)
        seconds = len(audio) / 2 / RATE
        assert 0.03 < seconds < 1.0
        samples = memoryview(audio).cast("h")
        assert max(abs(v) for v in samples) < 32767 * 0.5


def test_effects_can_be_switched_off():
    played = []
    sounds = SoundEffects({"listen": False}, player=played.append)
    sounds.play("listen")
    sounds.play("wake")
    sounds.play("unknown")
    assert sounds.played == ["wake"] and len(played) == 1
    assert personality_sounds("bubbly", {}) and not personality_sounds("classic", {})
    assert not personality_sounds("bubbly", {"sounds": {"bubbly": False}})


# ---- pitch -------------------------------------------------------------------
@pytest.fixture
def piper(tmp_path):
    model = tmp_path / "en_GB-test-medium.onnx"
    model.write_bytes(b"")
    FakeVoice.calls.clear()
    FakeVoice.gate = None
    FakeSD.streams.clear()
    return piper_tts.PiperTTS(model, volume=80, piper_module=fake_piper, sounddevice_module=FakeSD)


def test_piper_raises_pitch_without_changing_the_timing(piper):
    flat = DEFAULT_PROFILES["normal"]
    up = DEFAULT_PROFILES["bubbly_conversation"]
    plain = piper.synthesize("Hello", flat)
    raised = piper.synthesize("Hello", up)
    factor = 2 ** (piper.pitch(up) / 12)
    # Made slower by the pitch factor, then squeezed back: higher voice, same pace.
    assert FakeVoice.calls[-1][1].length_scale == pytest.approx(factor / piper.rate(up))
    assert len(raised) == pytest.approx(len(plain) / factor, rel=0.02)


def test_pitch_setting_adds_to_the_profile_and_is_limited(piper):
    profile = DEFAULT_PROFILES["bubbly_conversation"]
    piper.pitch_offset = 1.0
    assert piper.pitch(profile) == pytest.approx(profile.pitch + 1)
    piper.pitch_offset = 20
    assert piper.pitch(profile) == 6.0


def test_resample_shortens_audio():
    raw = bytes(range(256)) * 40
    assert len(piper_tts.resample(raw, 2.0)) == pytest.approx(len(raw) / 2, abs=2)


def test_espeak_pitch_follows_semitones(tmp_path):
    tts = EspeakTTS(command="true")
    bubbly = tts.args(tts.profile("bubbly_conversation"))
    normal = tts.args(tts.profile("normal"))
    assert int(bubbly[bubbly.index("-p") + 1]) == 50 + int(6 * DEFAULT_PROFILES["bubbly_conversation"].pitch)
    assert int(normal[normal.index("-p") + 1]) == 50


# ---- the optional online voice ------------------------------------------------
class FakeCommunicate:
    calls = []

    def __init__(self, text, voice, rate, pitch, volume):
        FakeCommunicate.calls.append((text, voice, rate, pitch, volume))

    async def stream(self):
        yield {"type": "WordBoundary"}
        yield {"type": "audio", "data": b"mp3"}


class FakeChannel:
    def get_busy(self):
        return False

    def stop(self):
        pass


class FakeSound:
    played = []

    def __init__(self, file):
        FakeSound.played.append(file.read())

    def play(self):
        return FakeChannel()


fake_pygame = types.SimpleNamespace(mixer=types.SimpleNamespace(get_init=lambda: True, init=lambda: None,
                                                                Sound=FakeSound))
fake_edge = types.SimpleNamespace(Communicate=FakeCommunicate)


def test_cloud_voice_is_off_unless_a_parent_allows_it():
    assert "cloud" not in engine_order("auto")
    with pytest.raises(RuntimeError, match="allow_cloud_voices"):
        _build("cloud", {"speech": {}})


def test_cloud_voice_sends_only_what_alfiebot_says():
    FakeCommunicate.calls.clear()
    FakeSound.played.clear()
    tts = CloudTTS("en-GB-MaisieNeural", edge_module=fake_edge, pygame_module=fake_pygame)
    tts.speak("Hello! C-A-T.", "bubbly_conversation")
    wait_until_quiet(tts, 5)
    texts = [c[0] for c in FakeCommunicate.calls]
    assert texts[0] == "Hello!"
    assert len(texts) == 4  # the sentence, then each letter on its own
    text, voice, rate, pitch, volume = FakeCommunicate.calls[0]
    assert voice == "en-GB-MaisieNeural"
    assert rate.startswith("+") and pitch.startswith("+") and pitch.endswith("Hz")
    assert FakeSound.played and set(FakeSound.played) == {b"mp3"}


# ---- the voice test screen ------------------------------------------------------
class RecordingTTS(TranscriptOnlyTTS):
    def __init__(self):
        super().__init__()
        self.said = []

    def speak(self, text, profile=None):
        self.said.append((text, profile))

    def speak_letters(self, word, profile=None, repeat=1):
        self.said.append((f"letters:{word}", profile))

    @property
    def speaking(self):
        return False


def test_voice_screen_compares_classic_and_bubbly():
    pygame = pytest.importorskip("pygame")  # noqa: F841
    from alfiebot.ui.voice_panel import EXAMPLES, VoicePanel

    robot, platform = make_robot(personality="bubbly")
    platform.tts = RecordingTTS()
    panel = VoicePanel(robot, robot.config, (0, 0, 400, 400))
    assert set(EXAMPLES) == {"Greetings", "Jokes", "Spelling"}
    panel.compare = True
    panel.play_example("Hello!", "normal", "wake")
    for _ in range(100):
        panel.update(0.05)
    assert [p for _, p in platform.tts.said] == ["normal", "bubbly_conversation"]
    assert platform.sounds.played == ["wake"]  # Classic stays without sound effects

    panel.compare = False
    panel.play_with = "bubbly"
    panel.play_example("letters:friend", "teacher", None)
    for _ in range(10):
        panel.update(0.05)
    assert platform.tts.said[-1] == ("letters:friend", "clear_spelling_teacher")
