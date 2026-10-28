"""The spelling tutor: adding words, learning mode and test mode.

The robot passes text here while a spelling activity is running and says
whatever ``Reply`` comes back (``None`` means "say nothing, keep listening").

Python is the examiner: this class decides every mark, never an AI.
Typed answers are marked straight away. Spoken answers are built up letter
by letter (see ``letter_input``): the child spells, can say "delete" or
"start again", and says "finished". Any letter the recogniser wasn't sure
of is asked about, and the whole spelling is read back for a yes before it
is marked, so a child is never marked wrong because of a mishearing.

Practice is a teaching ladder for each word: ask (the spelling is not
said first), clarify unclear letters, encourage and try again, a clue that
doesn't give the spelling away, then teach it (beats, the tricky part, a
memory tip, the spelling) and try straight away. A taught word comes back
at the end of the session and at the next one. Every answer is saved with
its outcome (correct, incorrect, unclear, help_requested, taught, skipped)
and words move between review boxes (``learning/schedule.py``).
"""

import json
import logging
import random
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

from alfiebot.conversation.engine import Reply
from alfiebot.conversation.intents import NO, YES, normalise
from alfiebot.core.states import Expression
from alfiebot.learning import schedule, teaching
from alfiebot.learning.store import HELP_REQUESTED, SKIPPED, TAUGHT, UNCLEAR
from alfiebot.spelling.letter_input import (CHILD_WORDS, NATO_WORDS, Command, Letter, LetterSequence,
                                           Unknown, confusable_with, parse_letters)
from alfiebot.spelling.lists import week_id
from alfiebot.spelling.words import clean_word, parse_spelled_answer, spell_out

log = logging.getLogger(__name__)

RESPONSES_PATH = Path(__file__).resolve().parent / "responses.json"
RECOGNITION_MODES = ("continuous", "letter_by_letter")
TEACH_AFTER = 3  # genuine mistakes before AlfieBot teaches the word
MAX_CLUES = 2

# Ends adding words, or the menu (spelling answers have their own commands).
CMD_STOP = re.compile(r"^(stop|finish|finished|end|quit|im done|i am done|thats enough|"
                      r"no more|done|thats all|that is all|all done|stop the test)\b")
ADD_WORD = re.compile(r"^(?:please )?(?:can you )?(?:add|put|save)(?: the)?(?: word)?\s+([a-z]+)\b")
THE_WORD_IS = re.compile(r"^(?:the )?(?:next )?word is\s+([a-z]+)\b")
CHOICES = [
    ("add", re.compile(r"\b(add|new words?|write|enter|put)\b")),
    ("practice", re.compile(r"\b(practi[sc]e|learn|learning|go through)\b")),
    ("test", re.compile(r"\b(test|quiz)\b")),
]

TYPED_COMMANDS = {"stop", "finish", "restart", "clear", "repeat", "slower", "next", "clue", "dont_know"}

MODE_STATE = {"menu": "spelling_setup", "add": "spelling_setup", "after_test": "spelling_setup",
              "after_practice": "spelling_setup",
              "practice": "spelling_practice", "test": "spelling_test"}


def load_responses(path=RESPONSES_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return {k: v for k, v in json.load(f).items() if not k.startswith("_")}


class SpellingTutor:
    def __init__(self, lists, progress, rng: random.Random = None, responses: dict = None,
                 min_confidence: float = 0.75, confirm_spoken: str = "always",
                 phonetic: str = "child", reveal_after_test_mistake: bool = False,
                 recognition_mode: str = "continuous"):
        """``lists`` and ``progress`` are ``learning.store.WordLists`` and
        ``LearningProgress`` (SQLite)."""
        self.min_confidence = min_confidence
        self.reveal_after_test_mistake = reveal_after_test_mistake
        # "continuous" (letters in a run) or "letter_by_letter" (one per utterance).
        self.recognition_mode = recognition_mode if recognition_mode in RECOGNITION_MODES else "continuous"
        self.letters_heard = 0  # spoken letters accepted so far (the robot ticks after each)
        self.confirm_spoken = confirm_spoken  # "always" or "when_unsure"
        self.phonetic = phonetic  # "child" (B for ball), "nato" (B for bravo) or "off"
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
        self.session_id: Optional[int] = None
        self._planned = 0  # words before any taught ones were added back
        self._requeued: set = set()
        self._reset_word()
        self._pending_word: Optional[str] = None
        self._reset_answer()
        self._added: List[str] = []
        self._missed: List[str] = []

    def _reset_word(self) -> None:
        self._asked_at = time.monotonic()  # for the time per answer
        self._mistakes = 0
        self._hint = 0  # clues given for this word
        self._taught = False

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
        return self._pending_word is not None or self.stage in ("clarify", "review")

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

    def handle(self, text: str, source: str = "typed", confidence: float = 1.0,
               words=None) -> Optional[Reply]:
        """``words`` is the recogniser's [(word, confidence)] list, if it has one."""
        norm = normalise(text)
        if self.mode in ("practice", "test"):
            if source == "typed":
                return self._handle_typed(text, norm)
            return self._handle_spoken(text, confidence, words)
        if self.mode == "add":
            return self._handle_add(text, norm, source, confidence)
        if CMD_STOP.search(norm):
            return self._finish_early()
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
            else:
                words = self.progress.plan_practice(words)
        self.mode = mode
        self.week = week
        self.words = words
        self._planned = len(words)
        self._requeued = set()
        self.index = 0
        self.results = {}
        self.session_id = self.progress.start_session(mode, week or self.active_week, self.recognition_mode)
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

    # ---- typed answers -----------------------------------------------------
    def _handle_typed(self, text: str, norm: str) -> Reply:
        """Typing is exact, so a typed answer is marked straight away."""
        word = self.words[self.index]
        tokens = parse_letters(norm)
        # A typed command ("next", "stop"...), unless it is simply the answer.
        commands = [t.name for t in tokens if isinstance(t, Command) and t.name in TYPED_COMMANDS]
        if commands and norm.replace(" ", "") != word and not any(isinstance(t, Letter) for t in tokens):
            # Nothing is being built when typing, so "finished" means stop.
            return self._command("stop" if commands[0] == "finish" else commands[0])
        letters = re.sub(r"[^a-z]", "", text.lower())
        if not letters:
            return self._say("nothing_heard", mood=Expression.CONFUSED)
        self._reset_answer()
        return self._judge(letters)

    # ---- spoken answers: letters build up until "finished" -----------------
    def _reset_answer(self) -> None:
        self.answer = LetterSequence(self.min_confidence)
        self._stage = "spelling"
        self._clarify_index: Optional[int] = None
        self._clarify_options: List[str] = []
        self._clarifications = 0

    @property
    def collecting_letters(self) -> bool:
        """True while a spoken spelling is being built (and not yet checked)."""
        return self.mode in ("practice", "test") and self._stage == "spelling" and len(self.answer) > 0

    @property
    def stage(self) -> Optional[str]:
        """"spelling", "clarify" or "review" during practice and tests."""
        return self._stage if self.mode in ("practice", "test") else None

    def _handle_spoken(self, text, confidence, words) -> Optional[Reply]:
        tokens = parse_letters(text, words, confidence)
        if self._stage == "clarify":
            return self._handle_clarify(tokens)
        if self._stage == "review":
            return self._handle_review(tokens)
        return self._collect(tokens)

    def _collect(self, tokens) -> Optional[Reply]:
        """Add letters and run commands. Returns None when there is nothing to
        say, so AlfieBot just keeps listening while the letters appear."""
        has_letters = any(isinstance(t, Letter) for t in tokens)
        unknown, note = [], None
        extra = None
        if self.recognition_mode == "letter_by_letter":
            letters = [t for t in tokens if isinstance(t, Letter)]
            if len(letters) > 1:
                # One letter per go: keep the first, ask for the rest one at a time.
                keep = letters[0]
                tokens = [t for t in tokens if not isinstance(t, Letter) or t is keep]
                extra = keep
        for t in tokens:
            if isinstance(t, Letter):
                self.answer.add(t.letter, t.confidence, t.phonetic, t.heard)
                self.letters_heard += 1
            elif isinstance(t, Unknown):
                unknown.append(t.word)
                if has_letters:
                    # Something between letters that wasn't a letter: ask about it later.
                    self.answer.add("?", 0.0, heard=t.word)
            elif t.name == "delete":
                note = ("deleted", self.answer.delete())
            elif t.name == "clear":
                self.answer.clear()
                note = ("cleared", None)
            elif t.name == "finish":
                return self._answer_finished()
            elif t.name in ("yes", "no", "first", "second", "third"):
                continue
            else:
                return self._command(t.name)
        word = self.words[self.index]
        if note and note[0] == "deleted":
            if note[1] is None:
                return self._say("deleted_nothing", mood=Expression.LISTENING, word=word)
            removed = "something" if note[1].letter == "?" else note[1].letter.upper()
            return self._say_text(self._pick("deleted", removed=removed) + " " + self._so_far(),
                                  mood=Expression.LISTENING)
        if note:
            return self._say("cleared", mood=Expression.LISTENING, word=word)
        if unknown and not has_letters:
            self._record(UNCLEAR)  # a hearing problem, never a mistake
            return self._say("letters_please", mood=Expression.CONFUSED, heard=" ".join(unknown))
        if extra is not None:
            return self._say("one_letter_at_a_time", mood=Expression.LISTENING, letter=extra.letter.upper())
        return None

    def finish_spoken_answer(self) -> Optional[Reply]:
        """The child stopped spelling for a while: check what we have."""
        if self.collecting_letters:
            return self._answer_finished()
        return None

    def _so_far(self) -> str:
        if not self.answer.letters:
            return self._pick("no_letters_so_far")
        return self._pick("so_far", so_far=_spoken(self.answer.text))

    def _answer_finished(self) -> Reply:
        if not self.answer.letters:
            return self._say("no_letters_yet", mood=Expression.LISTENING, word=self.words[self.index])
        index = self.answer.unsure_index()
        if index is not None:
            return self._clarify(index)
        if self.confirm_spoken == "always":
            return self._review()
        return self._mark_answer()

    def _review(self) -> Reply:
        self._stage = "review"
        return self._say("review", mood=Expression.LISTENING, answer=_spoken(self.answer.text))

    def _mark_answer(self) -> Reply:
        letters = self.answer.text
        heard = {"source": "voice", "clarifications": self._clarifications,
                 "min_confidence": min((h.confidence for h in self.answer.letters), default=None)}
        self._reset_answer()
        return self._judge(letters, heard)

    # ---- unsure letters ------------------------------------------------------
    def _phonetic(self, letter: str) -> str:
        words = NATO_WORDS if self.phonetic == "nato" else CHILD_WORDS
        if self.phonetic == "off":
            return letter.upper()
        return f"{letter.upper()} for {words[letter]}"

    def _clarify(self, index: int, key: str = None) -> Reply:
        """Ask about one letter. The choices come from letters that sound
        alike, never from the word being tested."""
        self._stage = "clarify"
        self._clarify_index = index
        self._clarifications += 1
        heard = self.answer.letters[index]
        n = index + 1
        if heard.letter == "?":
            self._clarify_options = []
            return self._say(key or "clarify_missing", mood=Expression.CONFUSED, n=n,
                             example=self._phonetic("b"))
        self._clarify_options = confusable_with(heard.letter)
        options = [self._phonetic(o) for o in self._clarify_options]
        if key is None:
            key = "clarify_choice" if len(options) > 1 else "clarify_one"
        return self._say(key, mood=Expression.CONFUSED, n=n, options=_join(options, "or"),
                         option=options[0], example=options[0])

    def _handle_clarify(self, tokens) -> Reply:
        index = self._clarify_index
        heard = self.answer.letters[index]
        letters = [t for t in tokens if isinstance(t, Letter)]
        commands = [t.name for t in tokens if isinstance(t, Command)]
        if "stop" in commands:
            return self._finish_early()
        if "clear" in commands:
            self._reset_answer()
            return self._say("cleared", mood=Expression.LISTENING, word=self.words[self.index])
        if "delete" in commands and not letters:
            del self.answer.letters[index]  # it wasn't a letter after all
            return self._after_clarify()
        picks = {"first": 0, "second": 1, "third": 2}
        chosen = next((self._clarify_options[picks[c]] for c in commands
                       if c in picks and picks[c] < len(self._clarify_options)), None)
        if letters:
            t = letters[0]
            if t.phonetic or t.confidence >= self.min_confidence:
                chosen = t.letter
            else:
                return self._clarify(index, "clarify_again")
        if chosen:
            heard.letter, heard.checked = chosen, True
            return self._after_clarify()
        if "yes" in commands and heard.letter != "?" and len(self._clarify_options) <= 1:
            heard.checked = True
            return self._after_clarify()
        if "no" in commands or "yes" in commands:
            return self._say("clarify_which", mood=Expression.LISTENING, n=index + 1,
                             example=self._phonetic("b"))
        return self._clarify(index, "clarify_again")

    def _after_clarify(self) -> Reply:
        index = self.answer.unsure_index()
        if index is not None:
            return self._clarify(index)
        if not self.answer.letters:
            self._stage = "spelling"
            return self._say("no_letters_yet", mood=Expression.LISTENING, word=self.words[self.index])
        return self._review()  # something was unsure, so always read it back

    def _handle_review(self, tokens) -> Optional[Reply]:
        commands = [t.name for t in tokens if isinstance(t, Command)]
        has_letters = any(isinstance(t, Letter) for t in tokens)
        if "stop" in commands:
            return self._finish_early()
        if not has_letters and ("yes" in commands or "finish" in commands):
            return self._mark_answer()
        if not has_letters and "no" in commands:
            self._stage = "spelling"
            return self._say_text(self._pick("review_no") + " " + self._so_far(), mood=Expression.LISTENING)
        if not tokens or (not has_letters and not commands):
            return self._say("yes_or_no", mood=Expression.LISTENING)
        # More letters, "delete" or "start again": back to spelling.
        self._stage = "spelling"
        return self._collect(tokens)

    # ---- commands while spelling ----------------------------------------
    def _command(self, name: str) -> Optional[Reply]:
        word = self.words[self.index]
        practice = self.mode == "practice"
        if name == "stop":
            return self._finish_early()
        if name == "restart" and practice:
            self.index = 0
            self.results = {}
            self._reset_answer()
            return self._say_text(self._pick("start_again") + " " + self._practice_prompt())
        if name in ("clear", "restart"):
            self.answer.clear()
            self._stage = "spelling"
            return self._say("cleared", mood=Expression.LISTENING, word=word)
        if name == "delete":
            return self._collect([Command("delete")])
        if name == "finish":
            return self._answer_finished()
        if name == "slower" and practice:
            if self._taught:
                return self._say("practice_slow", word=word)
            return self._say("practice_slow_beats", word=word, beats=self._help(word).beats)
        if name in ("repeat", "slower"):
            lead = self._pick("repeat_word", word=word)
            if self.answer.letters:
                lead += " " + self._so_far()
            return self._say_text(lead, mood=Expression.LISTENING)
        if name == "readback":
            return self._say_text(self._so_far(), mood=Expression.LISTENING)
        if name == "next" or (name == "dont_know" and not practice):
            self._reset_answer()
            self._record(SKIPPED)
            self.results.setdefault(word, False)
            self._finish_word(word, schedule.SKIPPED)
            if practice:
                return self._next_practice_word("")
            self.results[word] = False
            key = "test_skip_reveal" if self.reveal_after_test_mistake else "test_skip"
            return self._next_test_word(self._pick(key, word=word))
        if name in ("clue", "dont_know"):
            if not practice:
                return self._say("test_no_clue", mood=Expression.LISTENING)
            self._reset_answer()
            self._record(HELP_REQUESTED)
            self.results.setdefault(word, False)  # not right first time
            if self._taught:
                return self._say("practice_slow", word=word)
            if name == "dont_know" or self._hint >= MAX_CLUES:
                return self._teach(word)
            return self._say_text(self._next_clue(word) + " " + self._pick("try_again", word=word),
                                  mood=Expression.LISTENING)
        return None

    def _judge(self, letters: str, heard: dict = None) -> Reply:
        word = self.words[self.index]
        correct = letters == word
        heard = heard or {"source": "typed"}
        self.progress.record_attempt(word, correct, self.mode, letters, hints=self._hint + int(self._taught),
                                     session_id=self.session_id, seconds=round(time.monotonic() - self._asked_at, 1),
                                     **heard)
        self._asked_at = time.monotonic()
        if self.mode == "practice":
            return self._practice_answer(word, letters, correct)
        return self._test_answer(word, correct)

    def _record(self, outcome: str) -> None:
        """Save something that isn't a marked answer (unclear, help, taught, skipped)."""
        word = self.current_word
        if word:
            self.progress.record_attempt(word, mode=self.mode, outcome=outcome,
                                         hints=self._hint + int(self._taught), session_id=self.session_id)

    def _finish_word(self, word: str, result: str) -> None:
        """Move the word between review boxes, except when it comes back for
        a retest later in the same session (so it is still due next time)."""
        if self.index < self._planned:
            self.progress.finish_word(word, result, self.session_id)

    def _help(self, word: str) -> teaching.WordHelp:
        info = self.lists.word_info(word) if hasattr(self.lists, "word_info") else {}
        return teaching.word_help(word, info.get("syllables", ""), info.get("tip", ""), info.get("sentence", ""))

    def _next_clue(self, word: str) -> str:
        self._hint = min(self._hint + 1, MAX_CLUES)
        return teaching.clue(self._help(word), self._hint)

    def _teach(self, word: str) -> Reply:
        self._taught = True
        self._record(TAUGHT)
        self._requeue(word)
        return self._say_text(teaching.teach(self._help(word)), mood=Expression.HAPPY)

    def _requeue(self, word: str) -> None:
        """A taught word comes back once at the end of the session."""
        if word not in self._requeued and self.index < self._planned:
            self._requeued.add(word)
            self.words.append(word)

    # ---- learning mode: the teaching ladder ---------------------------------
    def _practice_prompt(self) -> str:
        word = self.words[self.index]
        self._reset_word()
        if self.index >= self._planned:
            return self._pick("practice_retest", word=word)
        sentence = self._help(word).sentence
        return self._pick("practice_word", word=word, n=self.index + 1, total=self._planned,
                          sentence=f"Here it is in a sentence: {sentence} " if sentence else "")

    def _practice_answer(self, word: str, letters: str, correct: bool) -> Reply:
        self.results.setdefault(word, correct)  # first try counts for the summary
        if correct:
            if self._taught:
                self._finish_word(word, schedule.TAUGHT)
                return self._next_practice_word(self._pick("practice_taught_correct", word=word), celebrate=True)
            first = self._mistakes == 0 and self._hint == 0
            self._finish_word(word, schedule.FIRST_TRY if first else schedule.WITH_HELP)
            return self._next_practice_word(self._pick("practice_correct", word=word), celebrate=True)
        self._mistakes += 1
        if self._taught:
            self._finish_word(word, schedule.TAUGHT)
            return self._next_practice_word(self._pick("practice_taught_wrong", word=word))
        lead = self._pick("wrong_lead")
        note = teaching.first_mistake_note(word, letters)
        if note and self._mistakes == 1:
            lead += " " + note
        early = self._mistakes == 1 and self._hint == 0 and self.progress.word(word).get("early_clue")
        if self._mistakes >= TEACH_AFTER or self._hint >= MAX_CLUES:
            reply = self._teach(word)
            return self._say_text(f"{lead} {reply.text}", mood=Expression.HAPPY)
        if self._mistakes >= 2 or early:
            lead += " " + self._next_clue(word)
        return self._say_text(f"{lead} {self._pick('try_again', word=word)}", mood=Expression.LISTENING)

    def _next_practice_word(self, lead: str, celebrate: bool = False) -> Reply:
        self.index += 1
        if self.index >= len(self.words):
            score = sum(self.results.values())
            total = len(self.results)
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
        self._reset_word()
        return self._pick("test_word", word=word, n=self.index + 1, total=len(self.words))

    def _test_answer(self, word: str, correct: bool) -> Reply:
        self.results[word] = correct
        self._finish_word(word, schedule.FIRST_TRY if correct else schedule.INCORRECT)
        if correct:
            lead = self._pick("test_correct", word=word)
        else:
            lead = self._pick("test_wrong_reveal" if self.reveal_after_test_mistake else "test_wrong", word=word)
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
            # Every word right: proud heart eyes.
            return self._say_text(f"{lead} {done}", mood=Expression.LOVE, then="listen",
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
    def _save_session(self) -> None:
        if self.mode in ("practice", "test") and self.session_id is not None:
            self.progress.finish_session(self.session_id, dict(self.results))
            self.session_id = None

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


def _join(words: List[str], last: str = "and") -> str:
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + f" {last} " + words[-1]


def _spoken(letters: str) -> str:
    """'bec?' -> 'B-E-C-_' (the speech engine says each letter, and "blank" for _)."""
    return "-".join("_" if c == "?" else c.upper() for c in letters)
