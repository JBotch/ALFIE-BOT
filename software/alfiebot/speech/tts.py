"""Offline text-to-speech engines.

- Piper (preferred): natural neural voices, including British English ones.
  ``pip install piper-tts`` and ``python tools/download_voice.py``. See piper_tts.py.
- Windows: the built-in Windows voices (System.Speech via PowerShell).
- Raspberry Pi / Linux: espeak-ng (``sudo apt install espeak-ng``).
- Nothing works: transcript only (the words appear on screen).

Every engine speaks on a background thread, one segment at a time (see
``text.plan_speech``): sentences, single letters and pauses. So speaking
never freezes the animation, letters are always said separately, and the
robot button can cut AlfieBot off mid-sentence.

``create_tts`` tries the engines in order and falls back to the next one,
saying why in the debug log and in ``fallback_reason``.
"""

import base64
from xml.sax.saxutils import escape
import logging
import math
import re
import shutil
import subprocess
import sys
import threading
import time
from typing import Dict, List, Optional

from alfiebot.speech.base import TextToSpeech
from alfiebot.speech.null import TranscriptOnlyTTS
from alfiebot.speech.text import Pause, Say, SayLetter, for_speech, letter_segments, letter_sound, plan_speech
from alfiebot.speech.voice_profiles import DEFAULT_PROFILES, VoiceProfile, load_profiles

log = logging.getLogger(__name__)

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
ENGINES = ("piper", "windows", "espeak")


class SegmentedTTS(TextToSpeech):
    """Shared by the real engines: plays a list of segments on a thread.

    Subclasses implement ``_say`` and ``_say_letter`` (blocking, but they
    must return soon after ``cancel`` is set) and may override ``_pause``,
    ``_begin``, ``_end`` and ``_interrupt``.
    """

    def __init__(self, profiles: Dict[str, VoiceProfile] = None, speed: float = 1.0):
        self.profiles = dict(profiles or DEFAULT_PROFILES)
        self.speed = speed  # overall speed, on top of each profile's rate
        self.pitch_offset = 0.0  # semitones, on top of each profile's pitch
        self.volume = 90  # 0..100, on top of each profile's volume
        self.spoken: List[str] = []
        self.profiles_used: List[str] = []
        self._thread: Optional[threading.Thread] = None
        self._cancel = threading.Event()

    def profile(self, name: Optional[str]) -> VoiceProfile:
        return self.profiles.get(name or "normal") or self.profiles.get("normal") or DEFAULT_PROFILES["normal"]

    def rate(self, profile: VoiceProfile) -> float:
        return max(0.3, min(3.0, profile.rate * self.speed))

    def pitch(self, profile: VoiceProfile) -> float:
        """Semitones up (or down) for this profile, kept within a sensible range."""
        return max(-6.0, min(6.0, profile.pitch + self.pitch_offset))

    def speak(self, text: str, profile: Optional[str] = None) -> None:
        p = self.profile(profile)
        self._start(plan_speech(text, p), p, text)

    def speak_letters(self, word: str, profile: Optional[str] = None, repeat: int = 1) -> None:
        p = self.profile(profile or "teacher")
        letters = re.sub(r"[^A-Za-z_]", "", word)
        self._start(letter_segments(letters, p, repeat=repeat)[:-1], p, "-".join(letters.upper()))

    def _start(self, segments, profile: VoiceProfile, text: str) -> None:
        self.stop()
        self.spoken.append(text)
        self.profiles_used.append(profile.name)
        cancel = threading.Event()
        self._cancel = cancel
        self._thread = threading.Thread(target=self._play, args=(segments, profile, cancel), daemon=True)
        self._thread.start()

    def _play(self, segments, profile, cancel) -> None:
        try:
            self._begin(profile)
            for seg in segments:
                if cancel.is_set():
                    break
                if isinstance(seg, Pause):
                    self._pause(seg.seconds, cancel)
                elif isinstance(seg, SayLetter):
                    self._say_letter(seg.letter, profile, cancel)
                elif isinstance(seg, Say):
                    self._say(seg.text, profile, cancel)
        except Exception:
            log.exception("%s failed while speaking", self.name)
        finally:
            try:
                self._end(cancel)
            except Exception:
                log.exception("%s failed to finish", self.name)

    @property
    def speaking(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def stop(self) -> None:
        if not self.speaking:
            return
        self._cancel.set()
        self._interrupt()
        self._thread.join(timeout=1.0)

    # ---- hooks -------------------------------------------------------------
    def _begin(self, profile) -> None:
        pass

    def _end(self, cancel) -> None:
        pass

    def _pause(self, seconds: float, cancel) -> None:
        cancel.wait(seconds)

    def _interrupt(self) -> None:
        pass

    def _say(self, text: str, profile, cancel) -> None:
        raise NotImplementedError

    def _say_letter(self, letter: str, profile, cancel) -> None:
        self._say(letter_sound(letter), profile, cancel)

    def available_voices(self) -> List[str]:
        return []


def _run_until_done(proc, cancel) -> None:
    while proc.poll() is None:
        if cancel.wait(0.02):
            proc.terminate()
            return


class EspeakTTS(SegmentedTTS):
    """espeak-ng, one short process per sentence or letter; text goes in on stdin."""

    name = "espeak-ng"

    def __init__(self, voice: str = "en-gb", rate: int = 0, volume: int = 90, command: str = None,
                 profiles=None, speed: float = 1.0):
        super().__init__(profiles, speed)
        self.command = command or shutil.which("espeak-ng") or shutil.which("espeak")
        if not self.command:
            raise RuntimeError("espeak-ng is not installed (sudo apt install espeak-ng)")
        self.voice = self.voice_name = voice or "en-gb"
        self.words_per_minute = int(160 + 8 * rate)  # rate -10..10 like the Windows voices
        self.volume = max(0, min(100, volume))
        self._proc = None

    def args(self, profile: VoiceProfile = None):
        profile = profile or self.profile("normal")
        wpm = int(self.words_per_minute * self.rate(profile))
        amplitude = int(self.volume * profile.volume * 1.5)  # espeak's 0..200 scale
        pitch = int(max(0, min(99, 50 + 6 * self.pitch(profile))))  # espeak: about 6 per semitone
        return [self.command, "-v", self.voice, "-s", str(wpm), "-a", str(amplitude),
                "-p", str(pitch), "--stdin"]

    def _say(self, text, profile, cancel) -> None:
        try:
            self._proc = proc = subprocess.Popen(self.args(profile), stdin=subprocess.PIPE,
                                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            proc.stdin.write(for_speech(text).encode("utf-8"))
            proc.stdin.close()
        except OSError as exc:
            log.error("espeak-ng failed: %s", exc)
            return
        _run_until_done(proc, cancel)

    def _interrupt(self) -> None:
        proc = self._proc
        if proc is not None and proc.poll() is None:
            proc.terminate()

    def available_voices(self) -> List[str]:
        try:
            out = subprocess.run([self.command, "--voices=en"], capture_output=True, text=True,
                                 timeout=5).stdout
        except (OSError, subprocess.SubprocessError):
            return [self.voice]
        voices = []  # language codes, which is what -v wants: en-gb, en-gb-scotland...
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) > 1 and parts[1] not in voices:
                voices.append(parts[1])
        return voices or [self.voice]


SAPI_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.Rate = __RATE__
$s.Volume = __VOLUME__
$want = '__VOICE__'
if ($want) {
  foreach ($v in $s.GetInstalledVoices()) {
    if ($v.VoiceInfo.Name -like "*$want*") { $s.SelectVoice($v.VoiceInfo.Name); break }
  }
}
[Console]::Out.WriteLine('READY ' + $s.Voice.Name)
[Console]::Out.Flush()
while ($null -ne ($line = [Console]::In.ReadLine())) {
  if ($line.StartsWith('#RATE ')) { $s.Rate = [int]$line.Substring(6) }
  elseif ($line.StartsWith('#VOLUME ')) { $s.Volume = [int]$line.Substring(8) }
  elseif ($line.StartsWith('#SSML ')) { $s.SpeakSsml($line.Substring(6)) }
  elseif ($line -eq '#VOICES') {
    foreach ($v in $s.GetInstalledVoices()) { [Console]::Out.WriteLine('VOICE ' + $v.VoiceInfo.Name) }
  }
  elseif ($line.Length -gt 0) { $s.Speak($line) }
  [Console]::Out.WriteLine('DONE')
  [Console]::Out.Flush()
}
"""
# Windows voice speed steps: each step of Rate is about 11% faster or slower.
SAPI_STEP = 1.11


class WindowsTTS(SegmentedTTS):
    """Windows voices through one long-running PowerShell process.

    Each sentence or letter is one line on stdin; PowerShell answers DONE
    when it has finished saying it. Lines starting with # are settings
    (#RATE, #VOLUME, #VOICES). Stopping kills the process; the next
    sentence starts a fresh one.
    """

    name = "Windows voice"

    def __init__(self, voice: str = "", rate: int = 0, volume: int = 90, command: str = None,
                 profiles=None, speed: float = 1.0):
        super().__init__(profiles, speed)
        self.command = command or shutil.which("powershell") or shutil.which("pwsh")
        if not self.command:
            raise RuntimeError("PowerShell not found")
        safe_voice = "".join(c for c in (voice or "") if c.isalnum() or c in " -_")
        self.base_rate = int(max(-10, min(10, rate)))
        self.volume = int(max(0, min(100, volume)))
        self.script = (SAPI_SCRIPT.replace("__RATE__", str(self.base_rate))
                       .replace("__VOLUME__", str(self.volume))
                       .replace("__VOICE__", safe_voice))
        self._proc = None
        self._done = threading.Event()
        self._lock = threading.Lock()
        self._settings = None  # (rate, volume) the process is using
        self._voices: List[str] = []
        self.voice_name = ""
        self._start_process()

    def _start_process(self) -> None:
        # The script goes on the command line, so stdin is free for sentences.
        encoded = base64.b64encode(self.script.encode("utf-16-le")).decode("ascii")
        self._proc = subprocess.Popen(
            [self.command, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-EncodedCommand", encoded],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            creationflags=NO_WINDOW)
        self._settings = (self.base_rate, self.volume)
        proc = self._proc
        threading.Thread(target=self._read, args=(proc,), daemon=True).start()

    def _read(self, proc) -> None:
        for raw in proc.stdout:
            line = raw.decode("utf-8", "replace").strip()
            if line.startswith("READY"):
                self.voice_name = line[6:]
                log.info("Windows voice ready: %s", self.voice_name or "default")
            elif line.startswith("VOICE "):
                self._voices.append(line[6:])
            elif line == "DONE" and proc is self._proc:
                self._done.set()
        if proc is self._proc:
            self._done.set()

    def _send(self, line: str, cancel=None) -> None:
        """Send one line and wait for DONE (or until cancelled)."""
        with self._lock:
            if self._proc is None or self._proc.poll() is not None:
                self._start_process()
            proc = self._proc
            self._done.clear()
            try:
                proc.stdin.write(line.encode("utf-8") + b"\n")
                proc.stdin.flush()
            except OSError as exc:
                log.error("Windows voice failed: %s", exc)
                return
        while not self._done.wait(0.02):
            if cancel is not None and cancel.is_set():
                return

    def _begin(self, profile) -> None:
        steps = round(math.log(self.rate(profile)) / math.log(SAPI_STEP))
        wanted = (int(max(-10, min(10, self.base_rate + steps))),
                  int(round(max(0, min(100, self.volume * profile.volume)))))
        if self._proc is None or self._proc.poll() is not None:
            self._start_process()
        if wanted != self._settings:
            self._send(f"#RATE {wanted[0]}")
            self._send(f"#VOLUME {wanted[1]}")
            self._settings = wanted

    def _say(self, text, profile, cancel) -> None:
        line = for_speech(text).replace("\r", " ").replace("\n", " ").lstrip("#")
        semitones = self.pitch(profile)
        if abs(semitones) >= 0.25:
            # Pitch needs SSML; voices that can't change pitch just ignore it.
            percent = round((2 ** (semitones / 12) - 1) * 100)
            line = ("#SSML <speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' "
                    f"xml:lang='en-GB'><prosody pitch='{percent:+d}%'>{escape(line)}</prosody></speak>")
        self._send(line, cancel)

    def _interrupt(self) -> None:
        with self._lock:
            proc, self._proc = self._proc, None
            self._done.set()
            if proc and proc.poll() is None:
                proc.kill()

    def available_voices(self) -> List[str]:
        self._voices = []
        self._send("#VOICES")
        return list(self._voices)

    def close(self) -> None:
        self.stop()
        proc, self._proc = self._proc, None
        if proc and proc.poll() is None:
            try:
                proc.stdin.close()
                proc.wait(timeout=2)
            except Exception:
                proc.kill()


# ---- choosing an engine ---------------------------------------------------
def engine_order(choice: str) -> List[str]:
    """Which engines to try, best first."""
    native = "windows" if sys.platform == "win32" else "espeak"
    if choice in ("auto", "", None):
        return ["piper", native]
    if choice == "piper":
        return ["piper", native]
    if choice == "cloud":
        return ["cloud", "piper", native]  # online voices are never relied on
    if choice in ENGINES:
        return [choice]
    log.warning("Unknown tts_engine %r; using auto", choice)
    return ["piper", native]


def _build(engine: str, config: dict) -> TextToSpeech:
    speech = config.get("speech", {})
    profiles = load_profiles(config)
    speed = float(speech.get("speed", 1.0) or 1.0)
    common = {"rate": speech.get("rate", 0), "volume": speech.get("volume", 90),
              "profiles": profiles, "speed": speed}
    if engine == "piper":
        from alfiebot.speech.piper_tts import PiperTTS, piper_model_path

        return PiperTTS(piper_model_path(config), volume=speech.get("volume", 90),
                        profiles=profiles, speed=speed, device=speech.get("speaker_device"))
    if engine == "cloud":
        if not speech.get("allow_cloud_voices"):
            raise RuntimeError("cloud voices are off (parent setting speech.allow_cloud_voices)")
        from alfiebot.speech.cloud_tts import CloudTTS

        return CloudTTS(speech.get("cloud_voice") or "en-GB-MaisieNeural", volume=speech.get("volume", 90),
                        profiles=profiles, speed=speed)
    if engine == "windows":
        return WindowsTTS(voice=speech.get("voice", ""), **common)
    if engine == "espeak":
        return EspeakTTS(voice=speech.get("voice") or "en-gb", **common)
    raise RuntimeError(f"unknown engine {engine}")


def create_tts(config: dict) -> TextToSpeech:
    speech = config.get("speech", {})
    choice = speech.get("tts_engine", "auto")
    if choice == "none":
        return TranscriptOnlyTTS(load_profiles(config))
    reasons = []
    for engine in engine_order(choice):
        try:
            tts = _build(engine, config)
        except Exception as exc:
            reasons.append(f"{engine}: {exc}")
            log.info("Speech engine %s not used: %s", engine, exc)
            continue
        tts.fallback_reason = "; ".join(reasons)
        tts.pitch_offset = float(speech.get("pitch", 0.0) or 0.0)
        if reasons:
            log.warning("Using %s for speech (%s)", tts.name, tts.fallback_reason)
        return tts
    log.warning("No speech output (%s). AlfieBot's words will only appear in the transcript.",
                "; ".join(reasons))
    tts = TranscriptOnlyTTS(load_profiles(config))
    tts.fallback_reason = "; ".join(reasons)
    return tts


def wait_until_quiet(tts: TextToSpeech, timeout: float = 30.0) -> None:
    """Block until speech finishes (for tools and tests only)."""
    end = time.monotonic() + timeout
    while tts.speaking and time.monotonic() < end:
        time.sleep(0.05)
