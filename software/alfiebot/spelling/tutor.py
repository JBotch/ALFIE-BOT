"""The spelling tutor: adding words, learning mode and test mode.

The robot passes text here while a spelling activity is running and says
whatever ``Reply`` comes back. The tutor never judges an answer it isn't
sure it heard: unclear spoken answers are read back for a yes/no first.
"""

import json
import logging
import random
import re
from pathlib import Path
from typing import Dict, List, Optional

from alfiebot.conversation.engine import Reply
from alfiebot.conversation.intents import NO, YES, normalise
from alfiebot.core.states import Expression
from alfiebot.spelling.lists import SpellingLists, week_id
from alfiebot.spelling.progress import ProgressTracker
from alfiebot.spelling.words import clean_word, parse_spelled_answer, spell_out

log = logging.getLogger(__name__)

RESPONSES_PATH = Path(__file__).resolve().parent / "responses.json"
PRACTICE_TRIES = 3  # wrong answers before moving on in learning mode

CMD_STOP = re.compile(r"^(stop|finish|finished|end|quit|im done|i am done|thats enough|"
                      r"no more|done|thats all|that is all|all done|stop the test)\b")
CMD_REPEAT = re.compile(r"\b(repeat|say (that|it) again|again|pardon|what did you say|what was the word)\b")
CMD_SLOWER = re.compile(r"\b(slower|slowly|slow)\b")
CMD_NEXT = re.compile(r"^(next|next word|skip|skip it|pass|move on)\b")
CMD_CLUE = re.compile(r"\b(clue|hint|help me|help)\b")
CMD_START_AGAIN = re.compile(r"\b(start again|start over|from the (start|beginning)|restart)\b")
CMD_DONT_KNOW = re.compile(r"\b(i dont know|dont know|no idea|not sure|i give up)\b")
ADD_WORD = re.compile(r"^(?:please )?(?:can you )?(?:add|put|save)(?: the)?(?: word)?\s+([a-z]+)\b")
THE_WORD_IS = re.compile(r"^(?:the )?(?:next )?word is\s+([a-z]+)\b")
CHOICES = [
    ("add", re.compile(r"\b(add|new words?|write|enter|put)\b")),
    ("practice", re.compile(r"\b(practi[sc]e|learn|learning|go through)\b")),
    ("test", re.compile(r"\b(test|quiz)\b")),
]

MODE_STATE = {"menu": "spelling_setup", "add": "spelling_setup", "after_test": "spelling_setup",
              "after_practice": "spelling_setup",
              "practice": "spelling_practice", "test": "spelling_test"}


def load_responses(path=RESPONSES_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return {k: v for k, v in json.load(f).items() if not k.startswith("_")}


class SpellingTutor:
    def __init__(self, lists: SpellingLists, progress: ProgressTracker,
                 rng: random.Random = None, responses: dict = None,
                 min_confidence: float = 0.75):
        self.min_confidence = min_confidence
        self.lists = lists
        self.progress = progress
        self.rng = rng or random.Random()
        self.responses = responses or load_responses()
        self.active_week = week_id()
        self.mode: Optional[str] = None
        self.last_reply: Optional[Reply] = None
        self._last_choice: Dict[str, str] = {}
        self._reset_activity()

    def _reset_activity(self) -> None:
        self.words: List[str] = []
        self.week: Optional[str] = None
        self.index = 0
        self.results: Dict[str, bool] = {}
        self._tries = 0
        self._clue = 0
        self._pending_word: Optional[str] = None
        self._pending_answer: Optional[str] = None
        self._added: List[str] = []
        self._missed: List[str] = []

    # ---- status for the panel -------------------------------------------
    @property
    def active(self) -> bool:
        return self.mode is not None

    @property
    def hide_words(self) -> bool:
        """True during a test, so the panel doesn't show the answers."""
        return self.mode == "test"

    @property
    def awaiting_yes_no(self) -> bool:
        return self._pending_answer is not None or self._pending_word is not None

    @property
    def current_word(self) -> Optional[str]:
        if self.mode in ("practice", "test") and self.index < len(self.words):
            return self.words[self.index]
        return None

    def status(self) -> str:
        if self.mode == "practice":
            return f"Practising word {self.index + 1} of {len(self.words)}"
        if self.mode == "test":
            return f"Test: word {self.index + 1} of {len(self.words)}, {sum(self.results.values())} right so far"
        if self.mode == "add":
            return f"Adding words to {self.active_week}"
        if self.mode in ("menu", "after_test", "after_practice"):
            return "Choosing: add, practise or test"
        return "Not running"

    # ---- entry points ---------------------------------------------------
    def start(self, choice: Optional[str], text: str = "") -> Reply:
        """Begin an activity: "add", "practice"/"practise", "test", or None for the menu."""
        choice = {"practise": "practice"}.get(choice, choice)
        self._reset_activity()
        if choice == "add":
            self.mode = "add"
            word = self._word_in(normalise(text))
            if word:
                return self._confirm_add(word)
            return self._say("add_intro")
        if choice in ("practice", "test"):
            return self._start_words(choice)
        self.mode = "menu"
        return self._say("menu_question")

    def stop(self) -> None:
        """End quietly (AlfieBot stopped listening). Saved progress is kept."""
        if self.mode:
            log.info("Spelling %s ended", self.mode)
        self.mode = None
        self._reset_activity()

    def handle(self, text: str, source: str = "typed", confidence: float = 1.0) -> Reply:
        norm = normalise(text)
        if self.mode in ("practice", "test") and self._pending_answer is not None:
            return self._handle_confirm_answer(norm)
        if self.mode == "add":
            return self._handle_add(text, norm, source, confidence)
        if CMD_STOP.search(norm):
            return self._finish_early()
        if self.mode == "practice":
            return self._handle_practice(text, norm, source, confidence)
        if self.mode == "test":
            return self._handle_test(text, norm, source, confidence)
        if self.mode == "after_test":
            return self._handle_after_test(norm)
        if self.mode == "after_practice":
            return self._handle_after_practice(norm)
        return self._handle_menu(norm, text)

    # ---- menu -----------------------------------------------------------
    def _handle_menu(self, norm: str, text: str) -> Reply:
        for choice, pattern in CHOICES:
            if pattern.search(norm):
                return self.start(choice, text)
        return self._say("menu_unclear")

    def _start_words(self, mode: str, words: List[str] = None) -> Reply:
        week = self.lists.best_week(self.active_week)
        if words is None:
            if week is None:
                self.mode = "menu"
                return self._say("no_words")
            words = list(self.lists.load(week).words)
            if mode == "test":
                self.rng.shuffle(words)
        self.mode = mode
        self.week = week
        self.words = words
        self.index = 0
        self.results = {}
        intro = self._pick(f"{mode}_intro", total=len(words))
        if mode == "practice":
            return self._say_text(intro + " " + self._practice_prompt(), mood=Expression.HAPPY)
        return self._say_text(intro + " " + self._test_prompt(), mood=Expression.EXCITED)

    def _finish_early(self) -> Reply:
        if self.mode == "test" and self.index > 0:
            reply = self._say("test_stopped", then="listen", score=sum(self.results.values()),
                              n=len(self.results))
        else:
            reply = self._say("stop", then="listen")
        self._save_session()
        self.stop()
        return reply

    # ---- adding words ----------------------------------------------------
    def _word_in(self, norm: str) -> Optional[str]:
        for pattern in (ADD_WORD, THE_WORD_IS):
            m = pattern.match(norm)
            if m:
                return clean_word(m.group(1))
        return None

    def _handle_add(self, text, norm, source, confidence) -> Reply:
        if self._pending_word is not None:
            if YES.search(norm):
                word = self._pending_word
                self._pending_word = None
                added = self.lists.add_words(self.active_week, [word])
                if added:
                    self._added.append(word)
                    return self._say("add_saved", word=word)
                return self._say("add_already", word=word)
            if NO.search(norm):
                self._pending_word = None
                return self._say("add_retry")
            # Neither yes nor no: treat it as a corrected word or spelling.
            self._pending_word = None

        if CMD_STOP.search(norm):
            count = len(self.lists.load(self.active_week).words)
            self.mode = "menu"
            key = "add_done" if self._added else "add_done_empty"
            return self._say(key, count=count)

        word = self._word_in(norm)
        if word is None:
            tokens = norm.split()
            if len(tokens) == 1:
                word = clean_word(tokens[0])
            elif tokens and (all(len(t) == 1 for t in tokens) or source != "typed"):
                answer = parse_spelled_answer(text, source, confidence)
                word = clean_word(answer.letters) if answer.letters else None
        if word is None:
            return self._say("add_unclear")
        return self._confirm_add(word)

    def _confirm_add(self, word: str) -> Reply:
        self._pending_word = word
        return self._say("add_confirm", word=word, mood=Expression.LISTENING)

    # ---- answers ---------------------------------------------------------
    def _read_answer(self, text, source, confidence):
        answer = parse_spelled_answer(text, source, confidence, self.min_confidence)
        if not answer.letters:
            return None, self._say("nothing_heard", mood=Expression.CONFUSED)
        if not answer.confident:
            # Never mark wrong because the recogniser was unsure: check first.
            self._pending_answer = answer.letters
            return None, self._say("confirm_heard", letters=spell_out(answer.letters),
                                   mood=Expression.LISTENING)
        return answer.letters, None

    def _handle_confirm_answer(self, norm: str) -> Reply:
        if YES.search(norm):
            letters = self._pending_answer
            self._pending_answer = None
            return self._judge(letters)
        if NO.search(norm):
            self._pending_answer = None
            return self._say("heard_retry", mood=Expression.LISTENING)
        return self._say("yes_or_no", mood=Expression.LISTENING)

    def _judge(self, letters: str) -> Reply:
        if self.mode == "practice":
            return self._practice_answer(letters)
        return self._test_answer(letters)

    # ---- learning mode ----------------------------------------------------
    def _practice_prompt(self) -> str:
        word = self.words[self.index]
        self._tries = 0
        self._clue = 0
        return self._pick("practice_word", word=word, n=self.index + 1, total=len(self.words))

    def _handle_practice(self, text, norm, source, confidence) -> Reply:
        word = self.words[self.index]
        if CMD_START_AGAIN.search(norm):
            self.index = 0
            self.results = {}
            return self._say_text(self._pick("start_again") + " " + self._practice_prompt())
        if CMD_SLOWER.search(norm):
            return self._say("practice_slow", word=word)
        if CMD_REPEAT.search(norm):
            return self._repeat()
        if CMD_NEXT.search(norm):
            self.results.setdefault(word, False)
            return self._next_practice_word("")
        if CMD_CLUE.search(norm) or CMD_DONT_KNOW.search(norm):
            self._clue = min(self._clue + 1, 3)
            pattern = "-".join(c.upper() if i < max(1, len(word) // 2) else "_"
                               for i, c in enumerate(word))
            return self._say(f"clue_{self._clue}", word=word, first=word[0].upper(),
                             length=len(word), pattern=pattern)
        letters, reply = self._read_answer(text, source, confidence)
        if reply:
            return reply
        return self._practice_answer(letters)

    def _practice_answer(self, letters: str) -> Reply:
        word = self.words[self.index]
        correct = letters == word
        self._tries += 1
        self.progress.record_attempt(word, correct, "practice", letters)
        self.results.setdefault(word, correct)  # first try counts for the summary
        if correct:
            praise = self._pick("practice_correct", word=word)
            return self._next_practice_word(praise, celebrate=True)
        if self._tries >= PRACTICE_TRIES:
            return self._next_practice_word(self._pick("practice_give_up", word=word))
        return self._say("practice_wrong", word=word, answer=spell_out(letters))

    def _next_practice_word(self, lead: str, celebrate: bool = False) -> Reply:
        self.index += 1
        if self.index >= len(self.words):
            score = sum(self.results.values())
            total = len(self.words)
            self._save_session()
            self.mode = "after_practice"
            done = self._pick("practice_done", total=total, score=score)
            return self._say_text(f"{lead} {done}".strip(), mood=Expression.EXCITED,
                                  celebrate=celebrate or score == total)
        return self._say_text(f"{lead} {self._practice_prompt()}".strip(),
                              mood=Expression.EXCITED if celebrate else Expression.HAPPY,
                              celebrate=celebrate)

    # ---- test mode --------------------------------------------------------
    def _test_prompt(self) -> str:
        word = self.words[self.index]
        return self._pick("test_word", word=word, n=self.index + 1, total=len(self.words))

    def _handle_test(self, text, norm, source, confidence) -> Reply:
        word = self.words[self.index]
        if CMD_REPEAT.search(norm) or CMD_SLOWER.search(norm):
            return self._say("test_repeat_word", word=word, mood=Expression.LISTENING)
        if CMD_NEXT.search(norm) or CMD_DONT_KNOW.search(norm):
            self.progress.record_attempt(word, False, "test", "")
            self.results[word] = False
            lead = self._pick("test_skip", word=word)
            return self._next_test_word(lead)
        letters, reply = self._read_answer(text, source, confidence)
        if reply:
            return reply
        return self._test_answer(letters)

    def _test_answer(self, letters: str) -> Reply:
        word = self.words[self.index]
        correct = letters == word
        self.progress.record_attempt(word, correct, "test", letters)
        self.results[word] = correct
        lead = self._pick("test_correct" if correct else "test_wrong", word=word)
        return self._next_test_word(lead, correct)

    def _next_test_word(self, lead: str, correct: bool = False) -> Reply:
        self.index += 1
        if self.index < len(self.words):
            return self._say_text(f"{lead} {self._test_prompt()}",
                                  mood=Expression.HAPPY if correct else Expression.LISTENING)
        score = sum(self.results.values())
        total = len(self.words)
        self._missed = [w for w in self.words if not self.results.get(w)]
        self._save_session()
        if not self._missed:
            done = self._pick("test_done_all", total=total)
            self.stop()
            return self._say_text(f"{lead} {done}", mood=Expression.EXCITED, then="listen",
                                  celebrate=True)
        self.mode = "after_test"
        one = len(self._missed) == 1
        done = self._pick("test_done_some", score=score, total=total, missed=_join(self._missed),
                          them="it" if one else "them", ones="one" if one else "ones",
                          were="was" if one else "were")
        return self._say_text(f"{lead} {done}", mood=Expression.HAPPY,
                              celebrate=score * 2 >= total)

    def _handle_after_test(self, norm: str) -> Reply:
        if YES.search(norm) or CHOICES[1][1].search(norm):
            return self._start_words("practice", list(self._missed))
        if NO.search(norm):
            reply = self._say("no_thanks", then="listen")
            self.stop()
            return reply
        return self._handle_menu(norm, norm)

    def _handle_after_practice(self, norm: str) -> Reply:
        if YES.search(norm) or CHOICES[2][1].search(norm):
            return self._start_words("test")
        if NO.search(norm):
            reply = self._say("no_thanks", then="listen")
            self.stop()
            return reply
        return self._handle_menu(norm, norm)

    # ---- shared -------------------------------------------------------------
    def _repeat(self) -> Reply:
        if self.last_reply is None:
            return self._say("menu_question")
        r = self.last_reply
        return Reply(r.text, "spelling_repeat", r.mood, r.then)

    def _save_session(self) -> None:
        if self.mode in ("practice", "test") and self.results:
            self.progress.record_session(self.mode, self.week or self.active_week, dict(self.results))

    def _pick(self, key: str, **values) -> str:
        options = self.responses[key]
        if len(options) > 1:
            last = self._last_choice.get(key)
            options = [o for o in options if o != last] or options
        text = self.rng.choice(options)
        self._last_choice[key] = text
        word = values.get("word", "")
        values.setdefault("Word", word[:1].upper() + word[1:])
        if word:
            values.setdefault("letters", spell_out(word))
            values.setdefault("slow_letters", spell_out(word, slow=True))
        return text.format(**values)

    def _say(self, key: str, mood: Expression = Expression.HAPPY, then: str = None, **values) -> Reply:
        return self._say_text(self._pick(key, **values), mood=mood, then=then)

    def _say_text(self, text: str, mood: Expression = Expression.HAPPY, then: str = None,
                  celebrate: bool = False) -> Reply:
        if then is None:
            then = MODE_STATE.get(self.mode, "listen")
        reply = Reply(text=text, intent=f"spelling_{self.mode or 'done'}", mood=mood,
                      then=then, celebrate=celebrate)
        self.last_reply = reply
        return reply


def _join(words: List[str]) -> str:
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + " and " + words[-1]
