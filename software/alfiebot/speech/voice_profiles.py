"""Voice profiles: how AlfieBot says things, not what it says.

None of the offline voices can really act happy or sleepy, so a profile
only changes what every engine can honestly change: speed, loudness and
the pauses between sentences, words and letters. Pitch is used where the
engine supports it (espeak-ng), and Piper voices get a little more or less
variation in rhythm ("expressiveness"). The excited and sleepy feeling
comes mostly from the wording AlfieBot already uses.

Profiles can be tuned in ``config/alfiebot.json`` under ``voice_profiles``.
"""

from dataclasses import dataclass, fields, replace
from typing import Dict, Optional

from alfiebot.core.states import Expression
from alfiebot.speech.text import SPELLED


@dataclass(frozen=True)
class VoiceProfile:
    name: str
    rate: float = 1.0  # speed: 1 = normal, 0.8 = slower, 1.2 = faster
    volume: float = 1.0  # 0..1, on top of speech.volume
    pitch: int = 0  # -50..50; only espeak-ng can change pitch
    sentence_pause: float = 0.3  # seconds of quiet after each sentence
    word_pause: float = 0.0  # seconds between words (0 = natural speech)
    letter_pause: float = 0.45  # seconds between spelled letters
    expressiveness: float = 1.0  # Piper only: variation in rhythm and tone
    style: str = ""  # a note for people; not used by the engines


DEFAULT_PROFILES = {
    "normal": VoiceProfile("normal", style="friendly and conversational"),
    "excited": VoiceProfile("excited", rate=1.1, volume=1.0, pitch=12, sentence_pause=0.2,
                            letter_pause=0.35, expressiveness=1.25,
                            style="celebrations: a bit quicker and brighter"),
    "teacher": VoiceProfile("teacher", rate=0.88, pitch=0, sentence_pause=0.5, letter_pause=0.7,
                            expressiveness=0.85, style="spelling: clear, slightly slower, longer gaps"),
    "sleepy": VoiceProfile("sleepy", rate=0.78, volume=0.7, pitch=-10, sentence_pause=0.7,
                           letter_pause=0.8, expressiveness=0.7,
                           style="going to sleep: slow, quiet and gentle"),
}
PROFILE_NAMES = tuple(DEFAULT_PROFILES)


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
    """Pick a profile for something AlfieBot is about to say."""
    if reply.then == "sleep" or reply.intent in ("goodbye",):
        return "sleepy"
    if tutor_mode in ("practice", "test") or reply.intent.startswith(("spelling_practice", "spelling_test")):
        # Clear and steady for words and letters; excited only for pure praise.
        return "excited" if reply.celebrate and not SPELLED.search(reply.text) else "teacher"
    if reply.celebrate or reply.mood == Expression.EXCITED:
        return "excited"
    return "normal"
