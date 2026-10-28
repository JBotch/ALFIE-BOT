"""Turning AI output into something safe to use.

An AI provider is asked for ``{"speech": ..., "expression": ..., "action": ...}``.
Nothing it returns is ever run as code or a command: ``speech`` is cleaned
and length-limited, ``expression`` must be one of the face's expressions
(an approved name from face/controller.py),
and ``action`` must be one of the few names in ``ALLOWED_ACTIONS``, each of
which maps to a fixed behaviour. Anything else is dropped and logged.
"""

import json
import logging
import re
from typing import List, Optional, Tuple

from alfiebot.conversation.engine import Reply
from alfiebot.core.events import BrainResponse
from alfiebot.core.states import Expression
from alfiebot.face.controller import ai_expression

log = logging.getLogger(__name__)

MAX_SPEECH_CHARS = 300
ALLOWED_ACTIONS = {
    "celebrate": "bounce with excitement before speaking",
    "start_spelling": "open the spelling menu",
    "end_conversation": "stop listening and go idle",
    "sleep": "go to sleep",
}
THEN_FOR_ACTION = {"end_conversation": "idle", "sleep": "sleep"}


class InvalidResponse(ValueError):
    pass


# Typographic characters some models use, as plain ones the voice and screen handle.
PLAIN = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-",
                       "\u2014": " - ", "\u2026": "...", "\u00a0": " "})
EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]")


def _clean_speech(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", " ", text, flags=re.S | re.I)
    text = EMOJI.sub("", text.translate(PLAIN))
    text = re.sub(r"\s+([!?.,])", r"\1", text)
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", " ", text)
    text = re.sub(r"[*_#`]+", "", text)  # markdown the voice would read out
    text = " ".join(text.split())
    if len(text) > MAX_SPEECH_CHARS:
        cut = text[:MAX_SPEECH_CHARS]
        end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
        text = cut[:end + 1] if end > 40 else cut.rsplit(" ", 1)[0] + "..."
    return text


def _extract_json(text: str) -> Optional[dict]:
    text = re.sub(r"<think>.*?</think>", " ", text, flags=re.S | re.I).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    if not text.startswith(("{", "[")):
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidResponse(f"broken JSON: {exc}") from None
    if not isinstance(data, dict):
        raise InvalidResponse("JSON is not an object")
    return data


def parse_response(raw) -> Tuple[BrainResponse, List[str]]:
    """Validate a provider's output (a JSON string, plain text or a dict).

    Returns the response and notes about anything that was corrected.
    Raises InvalidResponse if there is nothing usable to say.
    """
    notes: List[str] = []
    data = raw if isinstance(raw, dict) else _extract_json(str(raw))
    if data is None:
        data = {"speech": str(raw)}
        notes.append("plain text instead of JSON")
    speech = data.get("speech")
    if not isinstance(speech, str):
        raise InvalidResponse("no speech text")
    speech = _clean_speech(speech)
    if not speech:
        raise InvalidResponse("empty speech")

    expression = Expression.HAPPY
    value = data.get("expression")
    if value is not None:
        approved = ai_expression(str(value))
        if approved is None:
            notes.append(f"expression {value!r} is not allowed -> happy")
        else:
            expression = approved

    action = data.get("action")
    if isinstance(action, str):
        action = action.strip().lower() or None
        if action in ("null", "none"):
            action = None
    elif action is not None:
        notes.append(f"action {action!r} is not a name; dropped")
        action = None
    if action is not None and action not in ALLOWED_ACTIONS:
        notes.append(f"action {action!r} is not allowed; dropped")
        log.warning("Dropped unauthorised action from AI: %r", action)
        action = None
    for note in notes:
        log.info("AI output: %s", note)
    return BrainResponse(speech, expression, action), notes


def to_reply(response: BrainResponse, intent: str = "ai") -> Reply:
    """The robot's Reply for a validated response (start_spelling is handled
    by the brain, which owns the tutor)."""
    celebrate = response.action == "celebrate"
    mood = Expression.EXCITED if celebrate and response.expression == Expression.HAPPY else response.expression
    return Reply(text=response.speech, intent=intent, mood=mood,
                 then=THEN_FOR_ACTION.get(response.action, "listen"), celebrate=celebrate)
