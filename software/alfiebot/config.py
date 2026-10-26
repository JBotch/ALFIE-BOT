"""Configuration: built-in defaults, overridden by config/alfiebot.json."""

import copy
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

SOFTWARE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = SOFTWARE_ROOT / "config" / "alfiebot.json"

DEFAULTS = {
    "robot": {"name": "AlfieBot", "wake_phrase": "hey alfiebot"},
    "platform": "auto",
    "display": {
        "width": 1280,
        "height": 720,
        "fullscreen_on_pi": True,
        "fps": 60,
        "supersample": 2,
        "glow": 1.0,
        "hide_mouse_in_fullscreen": True,
    },
    "simulator": {"window_width": 1280, "window_height": 720},
    "face": {
        "start_expression": "sleeping",
        "transition_speed": 6.0,
        "show_mouth": True,
    },
    "conversation": {
        "listen_timeout": 60.0,
        "sleep_after_idle": 300.0,
        "thinking_time": 0.7,
        "wake_delay": 0.9,
    },
    "hardware": {"button_gpio_pin": 17},
    "privacy": {"microphone_enabled": False, "keep_audio_recordings": False},
    "data_dir": "data",
}


def deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path=None) -> dict:
    path = Path(path) if path else DEFAULT_CONFIG_PATH
    config = copy.deepcopy(DEFAULTS)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                user = json.load(f)
            user = {k: v for k, v in user.items() if not k.startswith("_")}
            config = deep_merge(config, user)
        except (OSError, json.JSONDecodeError) as exc:
            log.error("Could not read config %s (%s); using defaults", path, exc)
    else:
        log.warning("Config %s not found; using defaults", path)
    data_dir = Path(config["data_dir"])
    if not data_dir.is_absolute():
        data_dir = SOFTWARE_ROOT / data_dir
    config["data_dir"] = str(data_dir)
    return config
