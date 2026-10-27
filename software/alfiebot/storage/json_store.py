"""Local JSON storage. Everything stays on the device."""

import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class JsonStore:
    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)

    def path_for(self, name: str) -> Path:
        if not name.endswith(".json"):
            name += ".json"
        path = (self.base_dir / name).resolve()
        if self.base_dir.resolve() not in path.parents:
            raise ValueError(f"Refusing to use a path outside the data folder: {name}")
        return path

    def load(self, name: str, default: Any = None) -> Any:
        path = self.path_for(name)
        if not path.exists():
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            log.error("Could not read %s: %s", path, exc)
            return default

    def save(self, name: str, data: Any) -> Path:
        """Write atomically so a power cut can't leave a half-written file."""
        path = self.path_for(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise
        return path

    def list(self, subdir: str = "") -> list:
        folder = self.base_dir / subdir
        if not folder.is_dir():
            return []
        return sorted(p.stem for p in folder.glob("*.json"))

    def delete_all(self) -> None:
        """Parent control: remove every saved file."""
        if self.base_dir.exists():
            shutil.rmtree(self.base_dir)
        log.info("Deleted local data in %s", self.base_dir)
