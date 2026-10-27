"""Offline text-to-speech engines.

- Windows: the built-in Windows voices (System.Speech via PowerShell).
- Raspberry Pi / Linux: espeak-ng (``sudo apt install espeak-ng``).

Both run in a separate process, so speaking never freezes the animation and
the robot button can cut AlfieBot off mid-sentence. If no engine works,
AlfieBot falls back to transcript-only speech and says so in the debug log.
"""

import base64
import logging
import shutil
import subprocess
import sys
import threading
import time

from alfiebot.speech.base import TextToSpeech
from alfiebot.speech.null import TranscriptOnlyTTS
from alfiebot.speech.text import for_speech

log = logging.getLogger(__name__)

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class EspeakTTS(TextToSpeech):
    """One espeak-ng process per sentence; text goes in on stdin."""

    name = "espeak-ng"

    def __init__(self, voice: str = "en-gb", rate: int = 0, volume: int = 90, command: str = None):
        self.command = command or shutil.which("espeak-ng") or shutil.which("espeak")
        if not self.command:
            raise RuntimeError("espeak-ng is not installed (sudo apt install espeak-ng)")
        self.voice = voice or "en-gb"
        self.words_per_minute = int(160 + 8 * rate)  # rate -10..10 like the Windows voices
        self.amplitude = int(max(0, min(100, volume)) * 1.5)  # espeak's 0..200 scale
        self._proc = None
        self.spoken = []

    def args(self):
        return [self.command, "-v", self.voice, "-s", str(self.words_per_minute),
                "-a", str(self.amplitude), "--stdin"]

    def speak(self, text: str) -> None:
        self.stop()
        self.spoken.append(text)
        try:
            self._proc = subprocess.Popen(self.args(), stdin=subprocess.PIPE,
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._proc.stdin.write(for_speech(text).encode("utf-8"))
            self._proc.stdin.close()
        except OSError as exc:
            log.error("espeak-ng failed: %s", exc)
            self._proc = None

    @property
    def speaking(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def stop(self) -> None:
        if self.speaking:
            self._proc.terminate()
        self._proc = None


SAPI_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
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
  if ($line.Length -gt 0) { $s.Speak($line) }
  [Console]::Out.WriteLine('DONE')
  [Console]::Out.Flush()
}
"""


class WindowsTTS(TextToSpeech):
    """Windows voices through one long-running PowerShell process.

    Each sentence is one line on stdin; PowerShell answers DONE when it has
    finished saying it. Stopping kills the process; the next sentence starts
    a fresh one.
    """

    name = "Windows voice"

    def __init__(self, voice: str = "", rate: int = 0, volume: int = 90, command: str = None):
        self.command = command or shutil.which("powershell") or shutil.which("pwsh")
        if not self.command:
            raise RuntimeError("PowerShell not found")
        safe_voice = "".join(c for c in (voice or "") if c.isalnum() or c in " -_")
        self.script = (SAPI_SCRIPT.replace("__RATE__", str(int(max(-10, min(10, rate)))))
                       .replace("__VOLUME__", str(int(max(0, min(100, volume)))))
                       .replace("__VOICE__", safe_voice))
        self._proc = None
        self._busy = threading.Event()
        self._lock = threading.Lock()
        self.voice_name = ""
        self.spoken = []
        self._start()

    def _start(self) -> None:
        # The script goes on the command line, so stdin is free for sentences.
        encoded = base64.b64encode(self.script.encode("utf-16-le")).decode("ascii")
        self._proc = subprocess.Popen(
            [self.command, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-EncodedCommand", encoded],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            creationflags=NO_WINDOW)
        proc = self._proc
        threading.Thread(target=self._read, args=(proc,), daemon=True).start()

    def _read(self, proc) -> None:
        for raw in proc.stdout:
            line = raw.decode("utf-8", "replace").strip()
            if line.startswith("READY"):
                self.voice_name = line[6:]
                log.info("Windows voice ready: %s", self.voice_name or "default")
            elif line == "DONE" and proc is self._proc:
                self._busy.clear()
        if proc is self._proc:
            self._busy.clear()

    def speak(self, text: str) -> None:
        self.stop()
        self.spoken.append(text)
        line = for_speech(text).replace("\r", " ").replace("\n", " ")
        with self._lock:
            try:
                if self._proc is None or self._proc.poll() is not None:
                    self._start()
                self._busy.set()
                self._proc.stdin.write(line.encode("utf-8") + b"\n")
                self._proc.stdin.flush()
            except OSError as exc:
                log.error("Windows voice failed: %s", exc)
                self._busy.clear()

    @property
    def speaking(self) -> bool:
        return self._busy.is_set()

    def stop(self) -> None:
        if not self._busy.is_set():
            return
        with self._lock:
            proc, self._proc = self._proc, None
            self._busy.clear()
            if proc and proc.poll() is None:
                proc.kill()

    def close(self) -> None:
        proc, self._proc = self._proc, None
        if proc and proc.poll() is None:
            try:
                proc.stdin.close()
                proc.wait(timeout=2)
            except Exception:
                proc.kill()


def create_tts(config: dict) -> TextToSpeech:
    speech = config.get("speech", {})
    engine = speech.get("tts_engine", "auto")
    kwargs = {"voice": speech.get("voice", ""), "rate": speech.get("rate", 0),
              "volume": speech.get("volume", 90)}
    if engine == "none":
        return TranscriptOnlyTTS()
    if engine == "auto":
        engine = "windows" if sys.platform == "win32" else "espeak"
    try:
        if engine == "windows":
            return WindowsTTS(**kwargs)
        if engine == "espeak":
            if not kwargs["voice"]:
                kwargs["voice"] = "en-gb"
            return EspeakTTS(**kwargs)
        log.warning("Unknown tts_engine %r", engine)
    except Exception as exc:
        log.warning("No speech output (%s). AlfieBot's words will only appear in the transcript.", exc)
    return TranscriptOnlyTTS()


def wait_until_quiet(tts: TextToSpeech, timeout: float = 30.0) -> None:
    """Block until speech finishes (for tools and tests only)."""
    end = time.monotonic() + timeout
    while tts.speaking and time.monotonic() < end:
        time.sleep(0.05)

