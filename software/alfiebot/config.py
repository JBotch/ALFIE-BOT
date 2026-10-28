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
        "blink_interval": [2.5, 6.0],
        "show_mouth": True,
    },
    "conversation": {
        "listen_timeout": 60.0,
        "sleep_after_idle": 300.0,
        "thinking_time": 0.7,
        "wake_delay": 0.9,
    },
    "speech": {
        "tts_engine": "auto",
        "piper_voice": "en_GB-cori-medium",
        "voice": "",
        "rate": 0,
        "volume": 90,
        "speed": 1.0,
        "voice_profile": "auto",
        "personality": "bubbly",
        "pitch": 0.0,
        "allow_cloud_voices": False,
        "cloud_voice": "en-GB-MaisieNeural",
        "speaker_device": None,
        "recognizer": "vosk",
        "vosk_model": "models/vosk-model-small-en-us-0.15",
        "mic_mode": "open",
        "mic_device": None,
        "min_confidence": 0.75,
    },
    "spelling": {
        "confirm_spoken_answers": "always",
        "phonetic_words": "child",
        "finish_after_pause": 5.0,
    },
    "learning": {
        "review_days": [1, 2, 4, 7, 14],
        "max_session_words": 10,
        "confidence_words": 2,
        "reveal_after_test_mistake": False,
    },
    "voice_profiles": {},
    "sounds": {"bubbly": True, "classic": False, "wake": True, "listen": True, "celebrate": True,
               "volume": 0.5},
    "ai": {
        "enabled": True,
        "mode": "local_only",
        "local_provider": "ollama",
        "local_model": "qwen3:1.7b",
        "ollama_url": "http://localhost:11434",
        "timeout_s": 12.0,
        "max_tokens": 160,
        "mock_delay_s": 0.0,
    },
    "memory": {"conversation_turns": 10, "conversation_idle_minutes": 5.0},
    "cloud": {
        "enabled": False,
        "child_data_review_complete": False,
        "provider": "mock",
        "model": "gpt-4o-mini",
        "url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "timeout_s": 10.0,
        "max_retries": 2,
        "price_input_per_million": 0.15,
        "price_output_per_million": 0.60,
        "daily_budget_usd": 0.50,
    },
    "router": {"slow_local_s": 6.0, "unhealthy_after_failures": 3, "cooldown_s": 60.0},
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
    config["config_path"] = str(path)
    return config


def save_setting(config: dict, section: str, key: str, value) -> None:
    """Change one setting in memory and in the config file (keeps its comments)."""
    config.setdefault(section, {})[key] = value
    path = Path(config.get("config_path") or DEFAULT_CONFIG_PATH)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        data = {}
    data.setdefault(section, {})[key] = value
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    log.info("Saved setting %s.%s = %r", section, key, value)
