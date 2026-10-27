"""Offline speech recognition with Vosk and the sounddevice microphone library.

Privacy: audio is only captured while the microphone is open (the robot
opens it while listening and closes it while AlfieBot talks), it is
processed in memory, and it is never written to disk.

The model is downloaded once with ``python tools/download_speech_model.py``.
"""

import json
import logging
import queue
import threading
from pathlib import Path
from typing import List, Optional

from alfiebot.speech.base import RecognitionResult, SpeechRecognizer

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000
BLOCK_SECONDS = 0.1
# Results that are just noise.
IGNORED = {"", "huh", "the", "a", "[unk]"}


class VoskRecognizer(SpeechRecognizer):
    name = "Vosk"

    def __init__(self, model_path, device=None, vosk_module=None, sounddevice_module=None):
        self.model_path = Path(model_path)
        self.device = device
        self._vosk = vosk_module
        self._sd = sounddevice_module
        self._model = None
        self._reason = "Loading speech model..."
        self._stream = None
        self._audio: "queue.Queue[Optional[bytes]]" = queue.Queue()
        self._results: "queue.Queue[RecognitionResult]" = queue.Queue()
        self._grammar: Optional[List[str]] = None
        self._new_grammar = False
        self._finalise = threading.Event()
        self._lock = threading.Lock()
        self.partial = ""
        self.level = 0.0  # 0..1 microphone loudness, for the panel's meter
        self._listening = False
        threading.Thread(target=self._load, daemon=True).start()

    # ---- setup -----------------------------------------------------------
    def _load(self) -> None:
        try:
            if self._vosk is None:
                import vosk

                vosk.SetLogLevel(-1)
                self._vosk = vosk
            if self._sd is None:
                import sounddevice

                self._sd = sounddevice
            if not self.model_path.is_dir():
                self._reason = ("No speech model. Run: python tools/download_speech_model.py")
                log.warning("Speech model not found at %s", self.model_path)
                return
            self._model = self._vosk.Model(str(self.model_path))
            self._reason = ""
            log.info("Speech model loaded from %s", self.model_path.name)
            threading.Thread(target=self._work, daemon=True).start()
        except Exception as exc:  # missing package, PortAudio, bad model...
            self._reason = f"Microphone unavailable: {exc}"
            log.warning("Speech recognition unavailable: %s", exc)

    @property
    def available(self) -> bool:
        return self._model is not None

    @property
    def unavailable_reason(self) -> str:
        return self._reason

    @property
    def listening(self) -> bool:
        return self._listening

    def set_grammar(self, phrases: Optional[List[str]]) -> None:
        """Limit recognition to these words (e.g. letter names), or None for anything."""
        if phrases != self._grammar:
            self._grammar = phrases
            self._new_grammar = True

    # ---- microphone ------------------------------------------------------
    def _callback(self, data, frames, time_info, status) -> None:
        chunk = bytes(data)
        # Loudness for the meter (16-bit samples).
        samples = memoryview(chunk).cast("h")
        if len(samples):
            peak = max(abs(min(samples)), abs(max(samples)))
            self.level = min(1.0, peak / 20000)
        self._audio.put(chunk)

    def start_listening(self) -> None:
        if not self.available or self._listening:
            return
        with self._lock:
            self._stream = self._sd.RawInputStream(
                samplerate=SAMPLE_RATE, blocksize=int(SAMPLE_RATE * BLOCK_SECONDS),
                dtype="int16", channels=1, device=self.device, callback=self._callback)
            self._stream.start()
            self._listening = True
        log.debug("Microphone open")

    def stop_listening(self, finalise: bool = False) -> None:
        """Close the microphone. finalise=True turns what was heard into a result
        (push-to-talk release); otherwise the half-heard audio is thrown away."""
        if not self._listening:
            return
        with self._lock:
            self._listening = False
            stream, self._stream = self._stream, None
        if stream is not None:
            stream.stop()
            stream.close()
        self.level = 0.0
        if finalise:
            self._finalise.set()
        self._audio.put(None)  # marks the end of this listening session
        log.debug("Microphone closed")

    def poll(self) -> Optional[RecognitionResult]:
        try:
            return self._results.get_nowait()
        except queue.Empty:
            return None

    # ---- recognition thread ----------------------------------------------
    def _make_recognizer(self):
        if self._grammar:
            rec = self._vosk.KaldiRecognizer(self._model, SAMPLE_RATE,
                                             json.dumps(self._grammar + ["[unk]"]))
        else:
            rec = self._vosk.KaldiRecognizer(self._model, SAMPLE_RATE)
        rec.SetWords(True)
        return rec

    def _work(self) -> None:
        rec = self._make_recognizer()
        while True:
            chunk = self._audio.get()
            if self._new_grammar:
                self._new_grammar = False
                rec = self._make_recognizer()
            if chunk is None:
                if self._finalise.is_set():
                    self._finalise.clear()
                    self._emit(rec.FinalResult())
                rec = self._make_recognizer()  # forget anything half-heard
                self.partial = ""
                continue
            try:
                if rec.AcceptWaveform(chunk):
                    self._emit(rec.Result())
                    self.partial = ""
                else:
                    self.partial = json.loads(rec.PartialResult()).get("partial", "")
            except Exception:
                log.exception("Speech recognition error")
                rec = self._make_recognizer()

    def _emit(self, raw: str) -> None:
        result = parse_result(raw)
        if result is not None:
            log.info("Heard %r (confidence %.2f)", result.text, result.confidence)
            self._results.put(result)


def parse_result(raw: str) -> Optional[RecognitionResult]:
    """Vosk JSON -> RecognitionResult, or None for silence and noise."""
    data = json.loads(raw)
    text = " ".join(w for w in data.get("text", "").split() if w != "[unk]")
    if text.lower() in IGNORED:
        return None
    words = [(w.get("word", ""), float(w.get("conf", 1.0))) for w in data.get("result") or []
             if w.get("word") not in (None, "[unk]")]
    confidences = [c for _, c in words]
    confidence = sum(confidences) / len(confidences) if confidences else 1.0
    return RecognitionResult(text=text, confidence=confidence, source="voice", words=words)
