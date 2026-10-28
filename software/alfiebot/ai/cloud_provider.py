"""A cloud AI (OpenAI's Chat Completions API), off unless a parent turns it on.

Standard-library HTTPS only. The API key is read from an environment
variable (``OPENAI_API_KEY`` by default) when a request is made; it is
never read from or written to a settings file, logged or shown.

This provider never decides *whether* something may go to the cloud: the
router's privacy gate does that before it is ever called. It handles
timeouts, a few retries with backoff for timeouts, rate limits and server
errors, token usage and an estimated cost from configurable prices.
"""

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import List, Optional

from alfiebot.ai.provider_base import AIProvider, AIRequest, AIResult, timed

log = logging.getLogger(__name__)

DEFAULT_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
RETRY_CODES = {408, 409, 429, 500, 502, 503, 504}


class OpenAIProvider(AIProvider):
    name = "openai"
    kind = "cloud"

    def __init__(self, model: str = DEFAULT_MODEL, url: str = DEFAULT_URL, key_env: str = "OPENAI_API_KEY",
                 timeout_s: float = 10.0, max_retries: int = 2, price_in: float = 0.15, price_out: float = 0.60,
                 backoff_s: float = 0.5):
        super().__init__(model)
        self.url = url.rstrip("/")
        self.key_env = key_env
        self.timeout_s = timeout_s
        self.max_retries = max(0, int(max_retries))
        self.price_in = price_in  # per million prompt tokens
        self.price_out = price_out  # per million completion tokens
        self.backoff_s = backoff_s

    def _key(self) -> str:
        return os.environ.get(self.key_env, "").strip()

    @property
    def has_key(self) -> bool:
        return bool(self._key())

    def available(self) -> bool:
        return self.has_key

    @property
    def unavailable_reason(self) -> str:
        return "" if self.has_key else f"no API key (set the {self.key_env} environment variable)"

    def models(self) -> List[str]:
        return [self.model]

    def cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return (prompt_tokens * self.price_in + completion_tokens * self.price_out) / 1e6

    def generate(self, request: AIRequest) -> AIResult:
        return timed(self, request, lambda: self._generate(request))

    def _body(self, request: AIRequest) -> dict:
        messages = ([{"role": "system", "content": request.system}] if request.system else []) + request.messages
        body = {"model": self.model, "messages": messages, "max_completion_tokens": request.max_tokens}
        if request.json_schema:
            schema = dict(request.json_schema, additionalProperties=False)
            body["response_format"] = {"type": "json_schema",
                                       "json_schema": {"name": "alfiebot_reply", "strict": True, "schema": schema}}
        return body

    def _generate(self, request: AIRequest) -> AIResult:
        key = self._key()
        if not key:
            return AIResult("", self.name, self.model, ok=False, error=self.unavailable_reason)
        data = json.dumps(self._body(request)).encode("utf-8")
        timeout = min(self.timeout_s, request.timeout_s)
        start = time.monotonic()
        error, timed_out = "", False
        for attempt in range(self.max_retries + 1):
            if request.cancel.is_set():
                return self._fail("cancelled", start, timed_out=True)
            req = urllib.request.Request(f"{self.url}/chat/completions", data=data, headers={
                "Content-Type": "application/json", "Authorization": f"Bearer {key}"})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    reply = json.loads(response.read())
                return self._result(reply, start)
            except urllib.error.HTTPError as exc:
                error, timed_out = f"HTTP {exc.code}: {_error_text(exc)}", exc.code == 408
                if exc.code not in RETRY_CODES:
                    break
            except (OSError, ValueError) as exc:
                timed_out = "timed out" in str(exc).lower()
                error = "timed out" if timed_out else f"{type(exc).__name__}: {exc}"
            if attempt < self.max_retries:
                delay = self.backoff_s * (2 ** attempt)
                log.info("Cloud AI %s; retrying in %.1f s", error, delay)
                if request.cancel.wait(delay):
                    return self._fail("cancelled", start, timed_out=True)
        return self._fail(error, start, timed_out)

    def _result(self, reply: dict, start: float) -> AIResult:
        usage = reply.get("usage") or {}
        prompt, completion = int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))
        try:
            message = reply["choices"][0]["message"]
        except (KeyError, IndexError, TypeError):
            return self._fail("unexpected reply from the cloud", start)
        text = message.get("content") or ""
        result = AIResult(text, self.name, reply.get("model", self.model), latency_s=time.monotonic() - start,
                          prompt_tokens=prompt, completion_tokens=completion,
                          cost_estimate=self.cost(prompt, completion))
        if message.get("refusal") or not text.strip():
            result.ok, result.error = False, "the cloud AI refused" if message.get("refusal") else "empty reply"
        return result

    def _fail(self, error: str, start: float, timed_out: bool = False) -> AIResult:
        return AIResult("", self.name, self.model, ok=False, error=error, timed_out=timed_out,
                        latency_s=time.monotonic() - start)


def _error_text(exc: urllib.error.HTTPError) -> str:
    try:
        return json.loads(exc.read().decode("utf-8", "replace"))["error"]["message"][:200]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return str(exc.reason)
