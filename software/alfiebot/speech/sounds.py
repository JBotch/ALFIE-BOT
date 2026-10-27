"""Little electronic sound effects: waking up, starting to listen, celebrating.

The sounds are made by the code (soft sine-wave chirps and sparkles), so
there are no audio files to download. They are short and quiet on purpose:
a hint of "robot", not a noise. Each can be switched off in the config
(``sounds``). Played with pygame's mixer, or sounddevice if pygame has no
audio; if neither works AlfieBot just stays quiet.
"""

import logging
import math
import threading
from array import array
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

RATE = 22050
EFFECTS = ("wake", "listen", "celebrate")

# (start Hz, end Hz, seconds) notes; a note's pitch glides from start to end.
NOTES: Dict[str, List[Tuple[float, float, float]]] = {
    "wake": [(520, 780, 0.09), (780, 1170, 0.09), (1170, 1560, 0.16)],  # rising "boot up" chirp
    "listen": [(1320, 1760, 0.07)],  # one soft blip
    "celebrate": [(1047, 1047, 0.07), (1319, 1319, 0.07), (1568, 1568, 0.07), (2093, 2093, 0.22)],
}


def make_effect(name: str, volume: float = 0.5) -> bytes:
    """16-bit mono audio for one effect."""
    out = array("h")
    peak = 32767 * max(0.0, min(1.0, volume)) * 0.5
    phase = 0.0
    for start, end, seconds in NOTES[name]:
        n = int(RATE * seconds)
        for i in range(n):
            t = i / n
            freq = start + (end - start) * t
            phase += 2 * math.pi * freq / RATE
            # Quick attack, gentle fade, and a quiet octave on top for a "digital" shine.
            envelope = min(1.0, i / (0.008 * RATE)) * (1 - t) ** 1.5
            sample = math.sin(phase) + 0.25 * math.sin(2 * phase)
            out.append(int(peak * envelope * sample / 1.25))
    if name == "celebrate":
        # A short sparkle tail: fading high blips.
        for k, freq in enumerate((2637, 3136, 2794, 3520)):
            n = int(RATE * 0.05)
            for i in range(n):
                envelope = (1 - i / n) ** 2 * (0.5 - 0.1 * k)
                out.append(int(peak * envelope * math.sin(2 * math.pi * freq * i / RATE)))
    return out.tobytes()


class SoundEffects:
    """Plays an effect without waiting for it to finish."""

    def __init__(self, enabled: Dict[str, bool] = None, volume: float = 0.5, player=None):
        self.enabled = {name: True for name in EFFECTS}
        self.enabled.update(enabled or {})
        self.volume = volume
        self.played: List[str] = []
        self._player = player
        self._cache: Dict[Tuple[str, float], bytes] = {}

    def play(self, name: str) -> None:
        if name not in NOTES or not self.enabled.get(name, False):
            return
        self.played.append(name)
        key = (name, round(self.volume, 2))
        if key not in self._cache:
            self._cache[key] = make_effect(name, self.volume)
        player = self._player or self._find_player()
        if player is None:
            return
        try:
            player(self._cache[key])
        except Exception as exc:
            log.info("Couldn't play the %s sound: %s", name, exc)

    def _find_player(self):
        try:
            import pygame

            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=RATE, size=-16, channels=1)
            freq, _, channels = pygame.mixer.get_init()

            def play_pygame(data: bytes):
                if freq != RATE or channels != 1:
                    data = _convert(data, freq, channels)
                pygame.mixer.Sound(buffer=data).play()

            self._player = play_pygame
            return self._player
        except Exception as exc:
            log.debug("pygame mixer unavailable for sound effects: %s", exc)
        try:
            import sounddevice

            def play_sd(data: bytes):
                def run():
                    with sounddevice.RawOutputStream(samplerate=RATE, channels=1, dtype="int16") as stream:
                        stream.write(data)
                threading.Thread(target=run, daemon=True).start()

            self._player = play_sd
            return self._player
        except Exception as exc:
            log.info("No audio output for sound effects: %s", exc)
            self._player = lambda data: None
            return self._player


def _convert(data: bytes, freq: int, channels: int) -> bytes:
    """Resample (nearest) and duplicate channels to match the mixer."""
    src = array("h")
    src.frombytes(data)
    n = int(len(src) * freq / RATE)
    out = array("h")
    for i in range(n):
        v = src[min(len(src) - 1, int(i * RATE / freq))]
        out.extend([v] * channels)
    return out.tobytes()


class NoSounds(SoundEffects):
    def __init__(self):
        super().__init__({name: False for name in EFFECTS})


def create_sounds(config: dict) -> SoundEffects:
    cfg = config.get("sounds", {})
    return SoundEffects({name: bool(cfg.get(name, True)) for name in EFFECTS},
                        volume=float(cfg.get("volume", 0.5)))


def personality_sounds(personality: Optional[str], config: dict) -> bool:
    """Bubbly Bot uses sound effects; Classic only if the config says so."""
    cfg = config.get("sounds", {})
    if personality == "bubbly":
        return bool(cfg.get("bubbly", True))
    return bool(cfg.get("classic", False))
