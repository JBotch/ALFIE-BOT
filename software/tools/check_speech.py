"""Check speech output and the microphone without opening the simulator.

    python tools/check_speech.py          speak a sentence, list microphones,
                                          then listen for 5 seconds
    python tools/check_speech.py --no-mic  speech output only
    python tools/check_speech.py --no-mic --profiles   hear the four voice profiles

It never saves any audio.
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alfiebot.config import load_config  # noqa: E402
from alfiebot.speech.factory import create_recognizer, create_tts  # noqa: E402
from alfiebot.speech.tts import wait_until_quiet  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-mic", action="store_true")
    parser.add_argument("--profiles", action="store_true", help="also try the four voice profiles")
    parser.add_argument("--seconds", type=float, default=5.0)
    args = parser.parse_args()
    config = load_config()

    tts = create_tts(config)
    print(f"Speech output: {tts.name}" + (f" ({tts.voice_name})" if tts.voice_name else ""))
    if tts.fallback_reason:
        print(f"  Not used: {tts.fallback_reason}")
    tts.speak("Hello! I'm AlfieBot. Because is spelled B-E-C-A-U-S-E.")
    time.sleep(0.5)
    wait_until_quiet(tts)
    print("  If you heard that, speech output works.")
    if args.profiles:
        for profile, line in (("normal", "This is my normal voice."),
                              ("excited", "This is my excited voice. Brilliant spelling!"),
                              ("teacher", "This is my teacher voice. Spell because."),
                              ("sleepy", "This is my sleepy voice. Night night.")):
            print(f"  Profile: {profile}")
            tts.speak(line, profile)
            time.sleep(0.3)
            wait_until_quiet(tts)
        print("  Letters, teacher profile, twice:")
        tts.speak_letters("because", "teacher", repeat=2)
        time.sleep(0.3)
        wait_until_quiet(tts)
    if hasattr(tts, "close"):
        tts.close()

    if args.no_mic:
        return 0
    try:
        import sounddevice
        print("Microphones:")
        for i, dev in enumerate(sounddevice.query_devices()):
            if dev["max_input_channels"] > 0:
                print(f"  {i}: {dev['name']}")
    except Exception as exc:
        print(f"Can't list microphones: {exc}")
    rec = create_recognizer(config)
    for _ in range(100):
        if rec.available or "Loading" not in rec.unavailable_reason:
            break
        time.sleep(0.1)
    if not rec.available:
        print(f"Speech recognition: {rec.unavailable_reason}")
        return 1
    print(f"Listening for {args.seconds:.0f} seconds. Say something like 'how are you'...")
    rec.start_listening()
    end = time.monotonic() + args.seconds
    loudest = 0.0
    while time.monotonic() < end:
        loudest = max(loudest, getattr(rec, "level", 0.0))
        result = rec.poll()
        if result:
            print(f"  Heard: {result.text!r} (confidence {result.confidence:.2f})")
        time.sleep(0.05)
    rec.stop_listening(finalise=True)
    time.sleep(1.0)
    result = rec.poll()
    while result:
        print(f"  Heard: {result.text!r} (confidence {result.confidence:.2f})")
        result = rec.poll()
    print(f"  Loudest sound level: {loudest:.2f} (0 means the microphone heard nothing)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
