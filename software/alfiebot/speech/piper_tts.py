"""Piper: natural-sounding offline neural voices (the preferred engine).

Install once:   pip install piper-tts
Get a voice:    python tools/download_voice.py            (British English, ~60 MB)

Voices live in ``models/piper/<name>.onnx`` with a ``<name>.onnx.json``
next to them; ``speech.piper_voice`` picks one. Audio is made in memory and
played through the default speaker (or ``speech.speaker_device``); nothing
is saved. Runs on Windows and on the Raspberry Pi 5.

Speed, volume and the pauses come from the voice profile. Piper can't
change pitch or act out feelings; the profile's "expressiveness" only
gives a little more or less variation in rhythm and tone.
"""

import logging
from pathlib import Path
from typing import Dict, List

from alfiebot.config import SOFTWARE_ROOT
from alfiebot.speech.text import letter_sound
from alfiebot.speech.tts import SegmentedTTS

log = logging.getLogger(__name__)

VOICE_DIR = "models/piper"
DEFAULT_VOICE = "en_GB-cori-medium"
# Piper's own defaults; a profile's expressiveness scales them.
NOISE_SCALE = 0.667
NOISE_W = 0.8
BLOCK_SECONDS = 0.05


def voice_dir(config: dict = None) -> Path:
    return SOFTWARE_ROOT / VOICE_DIR


def piper_model_path(config: dict) -> Path:
    name = (config.get("speech", {}).get("piper_voice") or DEFAULT_VOICE).strip()
    path = Path(name)
    if not path.suffix:
        path = voice_dir(config) / f"{name}.onnx"
    elif not path.is_absolute():
        path = SOFTWARE_ROOT / path
    return path


def installed_voices(config: dict = None) -> List[str]:
    folder = voice_dir(config)
    if not folder.is_dir():
        return []
    return sorted(p.stem for p in folder.glob("*.onnx") if Path(str(p) + ".json").exists())


class PiperTTS(SegmentedTTS):
    name = "Piper"

    def __init__(self, model_path, volume: int = 90, profiles=None, speed: float = 1.0,
                 device=None, piper_module=None, sounddevice_module=None):
        super().__init__(profiles, speed)
        model_path = Path(model_path)
        if not model_path.exists():
            raise RuntimeError(f"no Piper voice {model_path.name}. Run: python tools/download_voice.py")
        try:
            piper = piper_module or __import__("piper")
            sd = sounddevice_module or __import__("sounddevice")
        except ImportError as exc:
            raise RuntimeError(f"Piper isn't installed ({exc}). Run: pip install piper-tts") from exc
        self._piper = piper
        self._sd = sd
        self.voice = piper.PiperVoice.load(str(model_path))
        self.voice_name = model_path.stem
        self.sample_rate = int(self.voice.config.sample_rate)
        self.volume = max(0, min(100, volume))
        self.device = device if device not in ("", None) else None
        self._letters: Dict[tuple, bytes] = {}
        self._stream = None
        log.info("Piper voice loaded: %s", self.voice_name)

    # ---- making audio ------------------------------------------------------
    def synthesize(self, text: str, profile) -> bytes:
        """16-bit mono audio for ``text`` at the profile's speed, pitch and volume.

        Pitch: the speech is made slower by the pitch factor, then played
        back that much faster (resampled). The timing ends up as asked and the
        voice is higher, without the "fast-forward" effect of speeding up."""
        factor = 2 ** (self.pitch(profile) / 12)
        length = factor / self.rate(profile)
        audio = self._synthesize(text, profile, length)
        return audio if abs(factor - 1) < 1e-3 else resample(audio, factor)

    def _synthesize(self, text: str, profile, length: float) -> bytes:
        noise = NOISE_SCALE * profile.expressiveness
        noise_w = NOISE_W * profile.expressiveness
        volume = self.volume / 100 * profile.volume
        config_cls = getattr(self._piper, "SynthesisConfig", None)
        if config_cls is not None:  # piper-tts 1.3 and later
            syn = config_cls(length_scale=length, noise_scale=noise, noise_w_scale=noise_w,
                             volume=volume)
            return b"".join(chunk.audio_int16_bytes for chunk in self.voice.synthesize(text, syn_config=syn))
        # piper-tts 1.2
        raw = b"".join(self.voice.synthesize_stream_raw(text, length_scale=length, noise_scale=noise,
                                                         noise_w=noise_w, sentence_silence=0.0))
        return _scale(raw, volume)

    def silence(self, seconds: float) -> bytes:
        return b"\x00\x00" * int(self.sample_rate * max(0.0, seconds))

    # ---- playing it --------------------------------------------------------
    def _begin(self, profile) -> None:
        self._stream = self._sd.RawOutputStream(samplerate=self.sample_rate, channels=1, dtype="int16",
                                                device=self.device)
        self._stream.start()

    def _end(self, cancel) -> None:
        stream, self._stream = self._stream, None
        if stream is None:
            return
        if cancel.is_set():
            stream.abort()
        else:
            stream.stop()  # lets the last bit play out
        stream.close()

    def _write(self, data: bytes, cancel) -> None:
        step = int(self.sample_rate * BLOCK_SECONDS) * 2
        for i in range(0, len(data), step):
            if cancel.is_set() or self._stream is None:
                return
            self._stream.write(data[i:i + step])

    def _say(self, text, profile, cancel) -> None:
        self._write(self.synthesize(text, profile), cancel)

    def _say_letter(self, letter, profile, cancel) -> None:
        key = (letter, self.rate(profile), self.pitch(profile), self.volume, profile.volume,
               profile.expressiveness)
        if key not in self._letters:
            self._letters[key] = _trim(self.synthesize(letter_sound(letter), profile))
        self._write(self._letters[key], cancel)

    def _pause(self, seconds, cancel) -> None:
        self._write(self.silence(seconds), cancel)

    def available_voices(self) -> List[str]:
        return installed_voices()


def resample(raw: bytes, factor: float) -> bytes:
    """Squeeze 16-bit audio to 1/factor of its length (raises the pitch by factor)."""
    try:
        import numpy as np
    except ImportError:
        return raw
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    if len(samples) < 2:
        return raw
    count = max(1, int(len(samples) / factor))
    positions = np.linspace(0, len(samples) - 1, count)
    return np.interp(positions, np.arange(len(samples)), samples).astype(np.int16).tobytes()


def _scale(raw: bytes, volume: float) -> bytes:
    if abs(volume - 1.0) < 1e-3:
        return raw
    from array import array

    samples = array("h")
    samples.frombytes(raw)
    for i, v in enumerate(samples):
        samples[i] = max(-32768, min(32767, int(v * volume)))
    return samples.tobytes()


def _trim(raw: bytes, threshold: int = 300) -> bytes:
    """Cut the silence Piper leaves around a single letter, so the profile's
    letter pause is the gap you actually hear."""
    from array import array

    samples = array("h")
    samples.frombytes(raw)
    loud = [i for i, v in enumerate(samples) if abs(v) > threshold]
    if not loud:
        return raw
    start, end = max(0, loud[0] - 200), min(len(samples), loud[-1] + 400)
    return samples[start:end].tobytes()
