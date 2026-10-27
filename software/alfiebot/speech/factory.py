"""Builds the speech engines named in the config."""

import logging
from pathlib import Path

from alfiebot.config import SOFTWARE_ROOT
from alfiebot.speech.base import SpeechRecognizer
from alfiebot.speech.null import NoSpeechRecognizer
from alfiebot.speech.tts import create_tts

log = logging.getLogger(__name__)

__all__ = ["create_recognizer", "create_tts"]


def model_path(config: dict) -> Path:
    path = Path(config["speech"]["vosk_model"])
    return path if path.is_absolute() else SOFTWARE_ROOT / path


def create_recognizer(config: dict) -> SpeechRecognizer:
    speech = config["speech"]
    if speech.get("recognizer", "vosk") != "vosk":
        return NoSpeechRecognizer()
    from alfiebot.speech.vosk_recognizer import VoskRecognizer

    device = speech.get("mic_device")
    return VoskRecognizer(model_path(config), device=device if device not in ("", None) else None)
