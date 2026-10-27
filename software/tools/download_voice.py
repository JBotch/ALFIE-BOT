"""Download a Piper voice for AlfieBot (about 60 MB each, needed once).

    python tools/download_voice.py                    the voice in the config (en_GB-cori-medium)
    python tools/download_voice.py en_GB-alan-medium  another voice
    python tools/download_voice.py --list             British English voices to try

Voices are saved in software/models/piper/. They come from the Piper
project's voice collection on Hugging Face (each voice has its own licence;
see the MODEL_CARD link printed after download). Speech is made on this
computer; nothing AlfieBot says is sent anywhere.

Then pick the voice in the simulator's Voice panel, or set
"piper_voice" in config/alfiebot.json.
"""

import argparse
import re
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alfiebot.config import load_config  # noqa: E402
from alfiebot.speech.piper_tts import DEFAULT_VOICE, voice_dir  # noqa: E402

BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
BRITISH_VOICES = {
    "en_GB-cori-medium": "female, clear and friendly (the default)",
    "en_GB-cori-high": "female, the same voice in higher quality (bigger and slower, best on Windows)",
    "en_GB-jenny_dioco-medium": "female, southern English",
    "en_GB-alba-medium": "female, Scottish",
    "en_GB-alan-medium": "male",
    "en_GB-northern_english_male-medium": "male, northern English",
    "en_GB-southern_english_female-low": "female, small and fast (lower quality)",
}
NAME = re.compile(r"^(?P<lang>[a-z]{2})_(?P<region>[A-Z]{2})-(?P<voice>[a-z0-9_]+)-(?P<quality>x_low|low|medium|high)$")


def download(url: str, target: Path) -> None:
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False, suffix=".part") as out:
        tmp = Path(out.name)
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                total = int(response.headers.get("Content-Length") or 0)
                done = 0
                while True:
                    block = response.read(1 << 16)
                    if not block:
                        break
                    out.write(block)
                    done += len(block)
                    if total > 1_000_000:
                        print(f"\r  {done * 100 // total}% of {total // 1_000_000} MB", end="", flush=True)
        except BaseException:
            out.close()
            tmp.unlink(missing_ok=True)
            raise
    if total > 1_000_000:
        print()
    tmp.replace(target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("voice", nargs="?", help="voice name, e.g. en_GB-alan-medium")
    parser.add_argument("--list", action="store_true", help="show British English voices")
    args = parser.parse_args()
    if args.list:
        for name, about in BRITISH_VOICES.items():
            print(f"  {name:<38} {about}")
        print("More voices: https://rhasspy.github.io/piper-samples/")
        return 0

    config = load_config()
    name = args.voice or config["speech"].get("piper_voice") or DEFAULT_VOICE
    m = NAME.match(name)
    if not m:
        print(f"{name!r} doesn't look like a Piper voice name (e.g. en_GB-cori-medium).")
        return 1
    folder = voice_dir(config)
    folder.mkdir(parents=True, exist_ok=True)
    model = folder / f"{name}.onnx"
    url = f"{BASE_URL}/{m['lang']}/{m['lang']}_{m['region']}/{m['voice']}/{m['quality']}/{name}"
    for suffix in (".onnx.json", ".onnx"):
        target = folder / f"{name}{suffix}"
        if target.exists():
            print(f"Already downloaded: {target.name}")
            continue
        print(f"Downloading {url}{suffix}")
        try:
            download(url + suffix + "?download=true", target)
        except Exception as exc:
            print(f"Download failed: {exc}")
            return 1
    print(f"Installed the Piper voice {name} in {folder}")
    print(f"Voice details and licence: {url.rsplit('/', 1)[0]}/MODEL_CARD")
    if name != config["speech"].get("piper_voice"):
        print(f'To use it, choose it in the simulator\'s Voice panel or set "piper_voice": "{name}" '
              "in config/alfiebot.json.")
    return 0 if model.exists() else 1


if __name__ == "__main__":
    sys.exit(main())
