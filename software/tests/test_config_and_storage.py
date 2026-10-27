import json

import pytest

from alfiebot.config import DEFAULTS, deep_merge, load_config
from alfiebot.speech.mic_gate import MicGate
from alfiebot.storage.json_store import JsonStore


def test_default_config_file_loads():
    config = load_config()
    assert config["display"]["width"] == 1280
    assert config["privacy"]["microphone_enabled"] is False
    assert config["privacy"]["keep_audio_recordings"] is False


def test_missing_config_uses_defaults(tmp_path):
    config = load_config(tmp_path / "nope.json")
    assert config["face"] == DEFAULTS["face"]


def test_bad_json_uses_defaults(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{ not json")
    assert load_config(path)["display"]["fps"] == DEFAULTS["display"]["fps"]


def test_override_merges_deeply(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"display": {"fps": 30}, "data_dir": str(tmp_path / "d")}))
    config = load_config(path)
    assert config["display"]["fps"] == 30
    assert config["display"]["width"] == 1280
    assert config["data_dir"] == str(tmp_path / "d")


def test_deep_merge_does_not_modify_inputs():
    base = {"a": {"b": 1}}
    deep_merge(base, {"a": {"b": 2}})
    assert base == {"a": {"b": 1}}


def test_store_round_trip_and_list(tmp_path):
    store = JsonStore(tmp_path / "data")
    assert store.load("missing", {"x": 1}) == {"x": 1}
    store.save("spellings/2026-W44", {"words": ["because"]})
    assert store.load("spellings/2026-W44") == {"words": ["because"]}
    assert store.list("spellings") == ["2026-W44"]
    assert not list((tmp_path / "data" / "spellings").glob(".tmp-*"))


def test_store_refuses_paths_outside_data_folder(tmp_path):
    store = JsonStore(tmp_path / "data")
    with pytest.raises(ValueError):
        store.save("../escape", {})


def test_store_delete_all(tmp_path):
    store = JsonStore(tmp_path / "data")
    store.save("progress", {"a": 1})
    store.delete_all()
    assert not (tmp_path / "data").exists()
    assert store.load("progress") is None


def test_example_spelling_list_is_valid():
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "examples" / "spelling_list_example.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["words"] and all(w.isalpha() for w in data["words"])


def test_mic_gate_tail():
    gate = MicGate(tail_seconds=0.5)
    gate.set_speaking(True)
    assert not gate.mic_allowed
    gate.set_speaking(False)
    gate.update(0.3)
    assert not gate.mic_allowed
    gate.update(0.3)
    assert gate.mic_allowed
