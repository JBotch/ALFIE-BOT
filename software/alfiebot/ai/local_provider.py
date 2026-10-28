"""A local AI model through Ollama (https://ollama.com), on this computer.

Talks to Ollama's HTTP API on localhost with the standard library only:
``/api/tags`` to see whether Ollama is running and which models are
installed, ``/api/chat`` to generate (streamed, so a cancelled request
stops early), ``/api/ps`` for how much memory the model uses.

Nothing leaves the computer. Models are never downloaded by AlfieBot: if a
model is missing the panel shows the ``ollama pull`` command for an adult to
run. Checking Ollama happens on a background thread so the face never
waits for it.
"""

import json
import logging
import re
import threading
import time
import urllib.error
import urllib.request
from typing import Dict, List, Optional

from alfiebot.ai.provider_base import AIProvider, AIRequest, AIResult, timed

log = logging.getLogger(__name__)

DEFAULT_URL = "http://localhost:11434"
RECOMMENDED_MODELS = ("qwen3:0.6b", "gemma3:1b", "qwen3:1.7b")
CHECK_EVERY_S = 10.0
THINK = re.compile(r"<think>.*?(</think>|$)", re.S | re.I)


class OllamaProvider(AIProvider):
    name = "ollama"
    kind = "local"

    def __init__(self, model: str = "qwen3:0.6b", url: str = DEFAULT_URL, temperature: float = 0.7,
                 keep_alive: str = "10m"):
        super().__init__(model)
        self.url = url.rstrip("/")
        self.temperature = temperature
        self.keep_alive = keep_alive
        self.running: Optional[bool] = None  # None until the first check
        self.version = ""
        self.installed: List[str] = []
        self.loaded_mb: Dict[str, float] = {}
        self.last_error = ""
        self._checked_at = 0.0
        self._lock = threading.Lock()
        self._checking = False
        self._warmed = set()
        self._no_think = set()  # models that refused the "think" option

    # ---- status ------------------------------------------------------------
    def refresh(self, wait: bool = False) -> None:
        """Check Ollama in the background (or now, with wait=True)."""
        with self._lock:
            if self._checking:
                start = False
            else:
                self._checking = start = True
        if not start:
            return
        if wait:
            self._check()
        else:
            threading.Thread(target=self._check, name="alfiebot-ollama-check", daemon=True).start()

    def _check(self) -> None:
        try:
            version = self._get("/api/version", 2.0).get("version", "")
            tags = self._get("/api/tags", 3.0)
            installed = sorted(m.get("name", "") for m in tags.get("models", []))
            try:
                ps = self._get("/api/ps", 2.0)
                loaded = {m.get("name", ""): m.get("size", 0) / 1e6 for m in ps.get("models", [])}
            except (OSError, ValueError):
                loaded = {}
            self.version, self.installed, self.loaded_mb = version, installed, loaded
            self.running, self.last_error = True, ""
        except (OSError, ValueError) as exc:
            if self.running is not False:
                log.info("Ollama not found at %s (%s)", self.url, exc)
            self.running, self.installed, self.last_error = False, [], str(exc)
        finally:
            self._checked_at = time.monotonic()
            with self._lock:
                self._checking = False
        if self.running and self.has_model(self.model):
            self.warm_up()

    def _maybe_refresh(self) -> None:
        if time.monotonic() - self._checked_at > CHECK_EVERY_S:
            self.refresh()

    def has_model(self, model: str) -> bool:
        names = set(self.installed)
        return model in names or f"{model}:latest" in names

    def available(self) -> bool:
        self._maybe_refresh()
        return bool(self.running) and self.has_model(self.model)

    @property
    def unavailable_reason(self) -> str:
        if self.running is None:
            return "checking for Ollama..."
        if not self.running:
            return f"Ollama isn't running. Install it from ollama.com, then run: ollama pull {self.model}"
        if not self.has_model(self.model):
            return f"model {self.model} isn't installed. Run: ollama pull {self.model}"
        return ""

    def models(self) -> List[str]:
        self._maybe_refresh()
        return list(self.installed) or [self.model]

    def warm_up(self) -> None:
        """Load the model in the background so the first answer isn't slow."""
        model = self.model
        if model in self._warmed:
            return
        self._warmed.add(model)

        def load():
            try:
                self._post("/api/generate", {"model": model, "keep_alive": self.keep_alive}, 120.0).read()
                log.info("Ollama model %s loaded", model)
            except (OSError, ValueError) as exc:
                log.info("Couldn't preload %s: %s", model, exc)
                self._warmed.discard(model)

        threading.Thread(target=load, name="alfiebot-ollama-warm", daemon=True).start()

    # ---- generating ------------------------------------------------------------
    def generate(self, request: AIRequest) -> AIResult:
        return timed(self, request, lambda: self._generate(request))

    def _generate(self, request: AIRequest) -> AIResult:
        model = self.model
        messages = ([{"role": "system", "content": request.system}] if request.system else []) + request.messages
        body = {"model": model, "messages": messages, "stream": True, "keep_alive": self.keep_alive,
                "options": {"temperature": self.temperature, "num_predict": request.max_tokens}}
        if request.json_schema:
            body["format"] = request.json_schema
        if model not in self._no_think:
            body["think"] = False  # Qwen3 would otherwise reason at length before answering
        start = time.monotonic()
        try:
            response = self._post("/api/chat", body, request.timeout_s)
        except urllib.error.HTTPError as exc:
            detail = _error_text(exc)
            if exc.code == 400 and "think" in detail.lower() and "think" in body:
                self._no_think.add(model)
                return self._generate(request)
            return self._fail(f"HTTP {exc.code}: {detail}", start)
        except (OSError, ValueError) as exc:
            self.running = None if self.running else self.running
            timed_out = "timed out" in str(exc).lower()
            return self._fail(f"{type(exc).__name__}: {exc}", start, timed_out)
        parts, final = [], {}
        try:
            with response:
                for line in response:
                    if request.cancel.is_set():
                        return self._fail("cancelled", start, timed_out=True)
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    if chunk.get("error"):
                        return self._fail(str(chunk["error"]), start)
                    parts.append(chunk.get("message", {}).get("content", ""))
                    if chunk.get("done"):
                        final = chunk
                        break
        except (OSError, ValueError) as exc:
            timed_out = "timed out" in str(exc).lower()
            return self._fail(f"{type(exc).__name__}: {exc}", start, timed_out)
        text = THINK.sub(" ", "".join(parts)).strip()
        result = AIResult(text, self.name, model, latency_s=time.monotonic() - start,
                          prompt_tokens=int(final.get("prompt_eval_count", 0)),
                          completion_tokens=int(final.get("eval_count", 0)),
                          memory_mb=self.loaded_mb.get(model))
        if not text:
            result.ok, result.error = False, "empty reply"
        return result

    def _fail(self, error: str, start: float, timed_out: bool = False) -> AIResult:
        return AIResult("", self.name, self.model, ok=False, error=error, timed_out=timed_out,
                        latency_s=time.monotonic() - start)

    # ---- HTTP --------------------------------------------------------------------
    def _get(self, path: str, timeout: float) -> dict:
        with urllib.request.urlopen(self.url + path, timeout=timeout) as response:
            return json.loads(response.read() or b"{}")

    def _post(self, path: str, body: dict, timeout: float):
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(self.url + path, data=data, headers={"Content-Type": "application/json"})
        return urllib.request.urlopen(req, timeout=timeout)


def _error_text(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8", "replace")
        return json.loads(body).get("error", body)
    except (OSError, ValueError, AttributeError):
        return str(exc.reason)
