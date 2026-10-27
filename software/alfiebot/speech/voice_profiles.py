"""Voice profiles and personalities: how AlfieBot says things.

A **profile** sets speed, loudness, pitch, the pauses between sentences,
words and letters, and (Piper only) how much the rhythm and tone vary.
A **personality** is a set of four profiles, one for each kind of reply
(normal, excited, teacher, sleepy), plus a few cheerful words it may add
to celebrations. There are two personalities to compare:

- **Classic**: the v0.6 voice.
- **Bubbly Bot**: a cheerful, friendly cartoon-robot voice. It is a little
  higher, livelier and more varied ("Bubbly Conversation"), with a slower,
  very clear "Clear Spelling Teacher" for words and letters.

Pitch is lifted only a little: the bubbly feel comes mostly from the pace,
the variation in tone, short gaps, sound effects and wording. No offline
voice can truly act happy, so the profiles don't pretend to.

Profiles can be tuned in ``config/alfiebot.json`` under ``voice_profiles``.
"""

from dataclasses import dataclass, fields, replace
from typing import Dict, Optional, Tuple

from alfiebot.core.states import Expression
from alfiebot.speech.text import SPELLED


@dataclass(frozen=True)
class VoiceProfile:
    name: str
    rate: float = 1.0  # speed: 1 = normal, 0.8 = slower, 1.2 = faster
    volume: float = 1.0  # 0..1, on top of speech.volume
    pitch: float = 0.0  # semitones: +2 = a little higher (Piper, espeak-ng; Windows if the voice allows)
    sentence_pause: float = 0.3  # seconds of quiet after each sentence
    word_pause: float = 0.0  # seconds between words (0 = natural speech)
    letter_pause: float = 0.45  # seconds between spelled letters
    expressiveness: float = 1.0  # Piper only: variation in rhythm and tone
    style: str = ""  # a note for people; not used by the engines
    label: str = ""  # name shown in the panel


DEFAULT_PROFILES = {
    # Classic (v0.6)
    "normal": VoiceProfile("normal", style="friendly and conversational", label="Normal"),
    "excited": VoiceProfile("excited", rate=1.1, volume=1.0, pitch=1.5, sentence_pause=0.2,
                            letter_pause=0.35, expressiveness=1.25,
                            style="celebrations: a bit quicker and brighter", label="Excited"),
    "teacher": VoiceProfile("teacher", rate=0.88, sentence_pause=0.5, letter_pause=0.7,
                            expressiveness=0.85, style="spelling: clear, slightly slower, longer gaps",
                            label="Teacher"),
    "sleepy": VoiceProfile("sleepy", rate=0.78, volume=0.7, pitch=-1.5, sentence_pause=0.7,
                           letter_pause=0.8, expressiveness=0.7,
                           style="going to sleep: slow, quiet and gentle", label="Sleepy"),
    # Bubbly Bot
    "bubbly_conversation": VoiceProfile(
        "bubbly_conversation", rate=1.06, pitch=2.5, sentence_pause=0.22, letter_pause=0.45,
        expressiveness=1.4, label="Bubbly Conversation",
        style="cheerful and playful: a little higher, lively pace, lots of variation"),
    "bubbly_excited": VoiceProfile(
        "bubbly_excited", rate=1.12, pitch=3.5, sentence_pause=0.18, letter_pause=0.4,
        expressiveness=1.55, label="Bubbly Excited", style="celebrations: bouncy and bright"),
    "clear_spelling_teacher": VoiceProfile(
        "clear_spelling_teacher", rate=0.84, pitch=1.5, sentence_pause=0.55, letter_pause=0.85,
        expressiveness=0.75, label="Clear Spelling Teacher",
        style="spelling: friendly but slower and very clear, long gaps between letters"),
    "bubbly_sleepy": VoiceProfile(
        "bubbly_sleepy", rate=0.82, volume=0.75, pitch=1.0, sentence_pause=0.6, letter_pause=0.8,
        expressiveness=0.9, label="Bubbly Sleepy", style="going to sleep: soft and slow"),
}
ROLES = ("normal", "excited", "teacher", "sleepy")


@dataclass(frozen=True)
class Personality:
    name: str
    label: str
    roles: Dict[str, str]  # role -> profile name
    cheers: Tuple[str, ...] = ()  # sometimes said before a celebration
    about: str = ""


PERSONALITIES = {
    "classic": Personality("classic", "Classic",
                           {"normal": "normal", "excited": "excited", "teacher": "teacher",
                            "sleepy": "sleepy"},
                           about="The v0.6 voice."),
    "bubbly": Personality("bubbly", "Bubbly Bot",
                          {"normal": "bubbly_conversation", "excited": "bubbly_excited",
                           "teacher": "clear_spelling_teacher", "sleepy": "bubbly_sleepy"},
                          cheers=("Woohoo!", "Yay!", "Ooh!", "Beep boop, yes!", "Hooray!"),
                          about="Cheerful cartoon robot: livelier, a little higher, sound effects."),
}
PROFILE_NAMES = tuple(DEFAULT_PROFILES)


def get_personality(name: Optional[str]) -> Personality:
    return PERSONALITIES.get(name or "classic", PERSONALITIES["classic"])


def load_profiles(config: dict) -> Dict[str, VoiceProfile]:
    """The built-in profiles with any changes from the config's voice_profiles."""
    profiles = dict(DEFAULT_PROFILES)
    allowed = {f.name for f in fields(VoiceProfile)} - {"name"}
    for name, values in (config.get("voice_profiles") or {}).items():
        if name.startswith("_") or not isinstance(values, dict):
            continue
        base = profiles.get(name, VoiceProfile(name))
        changes = {k: v for k, v in values.items() if k in allowed}
        profiles[name] = replace(base, **changes)
    return profiles


def profile_for_reply(reply, tutor_mode: Optional[str] = None) -> str:
    """Pick the kind of voice (a role: normal, excited, teacher or sleepy) for
    something AlfieBot is about to say. The personality turns it into a profile."""
    if reply.then == "sleep" or reply.intent in ("goodbye",):
        return "sleepy"
    if tutor_mode in ("practice", "test") or reply.intent.startswith(("spelling_practice", "spelling_test")):
        # Clear and steady for words and letters; excited only for pure praise.
        return "excited" if reply.celebrate and not SPELLED.search(reply.text) else "teacher"
    if reply.celebrate or reply.mood == Expression.EXCITED:
        return "excited"
    return "normal"
