"""Optional online voice, for comparison only: Microsoft's neural voices
through the free ``edge-tts`` package (pip install edge-tts).

It is off unless a parent sets ``speech.allow_cloud_voices`` to true. Even
then AlfieBot only uses it when chosen in the Voice panel: the normal voice
stays offline. Only the words AlfieBot says are sent to Microsoft to be
turned into audio; nothing Alfie says, and no audio from the microphone,
is ever sent. It needs the internet, and the service may change or stop at
any time, so AlfieBot must never depend on it.

en-GB-MaisieNeural is a young British girl's voice, useful to hear what a
genuinely youthful voice sounds like next to Bubbly Bot.
"""

import asyncio
import io
import logging
from typing import Dict, List

from alfiebot.speech.text import letter_sound
from alfiebot.speech.tts import SegmentedTTS

log = logging.getLogger(__name__)

BRITISH_CLOUD_VOICES = ("en-GB-MaisieNeural", "en-GB-SoniaNeural", "en-GB-LibbyNeural",
                        "en-GB-RyanNeural")
BASE_PITCH_HZ = 220  # rough speaking pitch, to turn semitones into the Hz edge-tts wants


class CloudTTS(SegmentedTTS):
    name = "Cloud voice (online)"

    def __init__(self, voice: str = "en-GB-MaisieNeural", volume: int = 90, profiles=None,
                 speed: float = 1.0, edge_module=None, pygame_module=None):
        super().__init__(profiles, speed)
        try:
            self._edge = edge_module or __import__("edge_tts")
            self._pg = pygame_module or __import__("pygame")
        except ImportError as exc:
            raise RuntimeError(f"edge-tts isn't installed ({exc}). Run: pip install edge-tts") from exc
        if not self._pg.mixer.get_init():
            self._pg.mixer.init()
        self.voice_name = voice
        self.volume = volume
        self._letters: Dict[tuple, bytes] = {}
        self._channel = None

    def fetch(self, text: str, profile) -> bytes:
        """MP3 audio for ``text`` from the online service."""
        rate = f"{round((self.rate(profile) - 1) * 100):+d}%"
        pitch = f"{round(BASE_PITCH_HZ * (2 ** (self.pitch(profile) / 12) - 1)):+d}Hz"
        volume = f"{round(self.volume * profile.volume - 100):+d}%"

        async def run():
            audio = b""
            communicate = self._edge.Communicate(text, self.voice_name, rate=rate, pitch=pitch, volume=volume)
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio":
                    audio += chunk["data"]
            return audio

        return asyncio.run(run())

    def _play_mp3(self, mp3: bytes, cancel) -> None:
        if not mp3:
            return
        sound = self._pg.mixer.Sound(file=io.BytesIO(mp3))
        self._channel = channel = sound.play()
        while channel is not None and channel.get_busy():
            if cancel.wait(0.02):
                channel.stop()
                return

    def _say(self, text, profile, cancel) -> None:
        self._play_mp3(self.fetch(text, profile), cancel)

    def _say_letter(self, letter, profile, cancel) -> None:
        key = (letter, self.rate(profile), self.pitch(profile))
        if key not in self._letters:
            self._letters[key] = self.fetch(letter_sound(letter), profile)
        self._play_mp3(self._letters[key], cancel)

    def _interrupt(self) -> None:
        if self._channel is not None:
            self._channel.stop()

    def available_voices(self) -> List[str]:
        return list(BRITISH_CLOUD_VOICES)

