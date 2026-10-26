"""Conversation engine: text in, reply out.

It picks the intent, chooses one of several replies and says what the robot
should do next. It doesn't know about timing, speech or the face; the robot
(``core/robot.py``) handles those.
"""

import json
import logging
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from alfiebot.conversation.intents import match_intent
from alfiebot.core.states import Expression

log = logging.getLogger(__name__)

RESPONSES_PATH = Path(__file__).resolve().parent / "responses.json"

# Questions AlfieBot asks, so the next answer is understood in context.
EXPECTS = {
    "wake": "feeling",
    "feeling_bad": "joke_offer",
    "spelling_help": "spelling_choice",
    "spelling_unclear": "spelling_choice",
}


@dataclass
class Reply:
    text: str
    intent: str
    mood: Expression = Expression.HAPPY
    # What happens after speaking: "listen", "idle", "sleep" or "spelling_setup".
    then: str = "listen"
    detail: Optional[str] = None


def load_responses(path=RESPONSES_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


class ConversationEngine:
    def __init__(self, robot_name: str = "AlfieBot", responses: dict = None,
                 rng: random.Random = None):
        self.robot_name = robot_name
        self.responses = responses or load_responses()
        self.rng = rng or random.Random()
        self.expecting: Optional[str] = None
        self.last_reply: Optional[Reply] = None
        self._last_choice = {}

    def reset(self) -> None:
        """Forget the conversation context (e.g. after going back to idle)."""
        self.expecting = None

    def greet(self) -> Reply:
        return self._reply("wake")

    def acknowledge(self, intent: str = "wake_again") -> Reply:
        """Short reply when woken while already listening, or by the button."""
        reply = self._reply(intent)
        return reply

    def respond(self, text: str) -> Reply:
        match = match_intent(text, self.expecting)
        log.info("Intent: %s%s (expecting %s)", match.intent,
                 f" [{match.detail}]" if match.detail else "", self.expecting or "nothing")
        if match.intent == "repeat":
            if self.last_reply is None:
                return self._reply("nothing_to_repeat")
            again = self.last_reply
            # Keep the same follow-up context as the original question.
            self.expecting = EXPECTS.get(again.intent)
            return Reply(again.text, "repeat", again.mood, again.then)
        return self._reply(match.intent, match.detail)

    def error_reply(self) -> Reply:
        self.expecting = None
        return self._reply("error")

    def _reply(self, intent: str, detail: Optional[str] = None) -> Reply:
        spec = self.responses.get(intent) or self.responses["fallback"]
        pool_intent = spec.get("use", intent)
        replies = self.responses[pool_intent]["replies"] if "use" in spec else spec["replies"]
        text = self._choose(pool_intent, replies).replace("{name}", self.robot_name)
        reply = Reply(text=text, intent=intent, mood=Expression(spec.get("mood", "happy")),
                      then=spec.get("then", "listen"), detail=detail)
        self.expecting = EXPECTS.get(intent)
        self.last_reply = reply
        return reply

    def _choose(self, key: str, options: list) -> str:
        """Random choice that never repeats the previous pick for this intent."""
        if len(options) == 1:
            return options[0]
        last = self._last_choice.get(key)
        choices = [o for o in options if o != last]
        pick = self.rng.choice(choices)
        self._last_choice[key] = pick
        return pick
