"""Download the offline speech model (about 40 MB, needed once).

    python tools/download_speech_model.py

It is saved in software/models/. The model is Vosk's small US English
model (Apache 2.0 licence) from https://alphacephei.com/vosk/models.
Nothing you say is ever sent anywhere: recognition runs on this computer.
"""

import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alfiebot.config import load_config  # noqa: E402
from alfiebot.speech.factory import model_path  # noqa: E402

BASE_URL = "https://alphacephei.com/vosk/models/"


def main() -> int:
    target = model_path(load_config())
    if target.is_dir():
        print(f"The speech model is already installed: {target}")
        return 0
    url = BASE_URL + target.name + ".zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url}")
    with tempfile.TemporaryDirectory(dir=target.parent) as tmp:
        zip_path = Path(tmp) / "model.zip"
        with urllib.request.urlopen(url, timeout=60) as response, open(zip_path, "wb") as out:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            while True:
                block = response.read(1 << 16)
                if not block:
                    break
                out.write(block)
                done += len(block)
                if total:
                    print(f"\r  {done * 100 // total}% of {total // 1_000_000} MB", end="", flush=True)
        print()
        with zipfile.ZipFile(zip_path) as zf:
            for member in zf.namelist():
                # Refuse anything that would land outside the temp folder.
                if member.startswith("/") or ".." in Path(member).parts:
                    raise RuntimeError(f"Unexpected path in zip: {member}")
            zf.extractall(tmp)
        extracted = Path(tmp) / target.name
        if not extracted.is_dir():
            raise RuntimeError(f"The zip didn't contain {target.name}/")
        shutil.move(str(extracted), str(target))
    print(f"Installed the speech model in {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
