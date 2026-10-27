# AlfieBot V1 architecture proposal

*Phase 1 proposal for approval. Nothing here is built yet.* See [existing_system_audit.md](existing_system_audit.md) for what exists today and [development_plan.md](development_plan.md) for milestones.

## 1. Approach

Extend the v0.7 code in place. New packages go beside the existing ones, and existing modules are refactored rather than replaced, so Jordan's install, settings, spelling lists and the 244 tests keep working at every step.

The main change is a **Brain** between the robot's timing loop and everything that produces a reply:

```text
            microphone / typed text / button
                         │
                         ▼
 ┌────────────────── core/robot.py (existing, slimmed) ──────────────────┐
 │ state machine · timers · mic gate · TTS · face listener · hold text   │
 └───────────────┬───────────────────────────────────────▲───────────────┘
                 │ UserInput event                       │ BrainResponse
                 ▼                                       │ (speech, expression, action)
 ┌──────────────────────────── core/brain.py (new) ──────┴───────────────┐
 │ 1. safety.check_input   → privacy class, sensitive topics, refusals   │
 │ 2. learning engine      → if an activity is running (Python examiner) │
 │ 3. deterministic tools  → maths, time, commands, scripted intents     │
 │ 4. ai/router            → choose local / cloud / mock provider        │
 │ 5. personality + memory → build the prompt                            │
 │ 6. validate output      → schema, safety.check_output, action allowlist│
 └───────────────────────────────────────────────────────────────────────┘
          │                   │                       │
     learning/           ai/ providers          storage/database.py (SQLite)
```

The brain runs on a worker thread. While it works the robot stays in THINKING and the face keeps animating at 60 fps. The robot polls for the result each frame, exactly like it polls the recogniser today. If the result is late, a configurable timeout returns a scripted fallback.

## 2. Package layout

Brief names on the left, where they live on the right. Folders marked *existing* keep their current names to avoid breaking imports and Jordan's install.

```text
software/
├── config/
│   ├── alfiebot.json            existing; new sections ai, cloud, router, learning, memory, safety
│   └── personality.json         new
├── benchmarks/questions.json    new: fixed benchmark prompts
├── docs/                        audit, architecture, plan, install, Pi deployment
├── tools/benchmark_models.py    new
└── alfiebot/
    ├── main.py                  existing
    ├── core/
    │   ├── robot.py             existing; reply generation moves to brain.py
    │   ├── brain.py             new
    │   ├── conversation.py      new: wraps conversation/engine.py (scripted tier) + AI chat
    │   ├── personality.py       new: loads personality.json, builds system prompt, style checks
    │   ├── memory.py            new: short-term conversation memory
    │   ├── safety.py            new: input privacy classifier, output filter, refusals
    │   ├── actions.py           new: action allowlist and validation
    │   ├── events.py            new: UserInput, BrainResponse, Action dataclasses
    │   └── state_machine.py, states.py, transcript.py   existing
    ├── conversation/            existing regex intents + responses.json (scripted tier)
    ├── ai/                      new
    │   ├── provider_base.py     AIProvider, AIRequest, AIResult
    │   ├── mock_provider.py     scripted, deterministic, can simulate slow or failing
    │   ├── local_provider.py    Ollama HTTP API (llama.cpp server via the same adapter later)
    │   ├── cloud_provider.py    OpenAI adapter behind a generic CloudProvider
    │   ├── connectivity.py      internet check + "simulate internet failure"
    │   ├── router.py            routing rules and decisions with reasons
    │   └── performance.py       latency, tokens, errors, memory, cost → SQLite
    ├── learning/                new; replaces spelling/tutor.py, progress.py, lists.py
    │   ├── engine.py            activity manager (one activity at a time)
    │   ├── spelling.py          the examiner: sequence, attempts, outcomes
    │   ├── teaching.py          the teaching ladder (clarify → retry → clue → teach → practise)
    │   ├── adaptive.py          spaced repetition, difficulty, adaptation log
    │   ├── progress.py          SQLite repository for lists, attempts, sessions
    │   └── activities.py        activity registry (spelling now; maths later)
    ├── spelling/                existing; letter_input.py and words.py stay as the letter validator
    ├── speech/                  existing; recognition, TTS, wake word interfaces already here
    ├── face/                    existing (brief's interface/face.py, expressions.py)
    ├── hardware/                existing + actuators.py (simulated motors, sensors, battery)
    ├── storage/
    │   ├── json_store.py        existing (letter test results, small settings)
    │   ├── database.py          new: sqlite3, schema migrations, WAL mode
    │   └── models.py            new: dataclasses for rows
    └── ui/                      existing simulator + new ai_panel.py and learning_panel.py
```

`speech/letter_validation.py` from the brief is `spelling/letter_input.py`. It already does the job and is well tested, so it stays where it is.

**Config format.** The brief suggests YAML. I recommend keeping JSON: it needs no extra package (PyYAML), the existing loader and "save from the panel" code already work with it, and Jordan's settings on the PC carry over. `personality.json` is new and separate so it can be edited without touching technical settings.

## 3. Brain and response contract

Every reply, whichever component made it, becomes a validated `BrainResponse`:

```json
{"speech": "Brilliant! Let's try another!", "expression": "happy", "action": null}
```

- `speech`: 1 to 300 characters after cleaning; at most about 3 short sentences for conversation.
- `expression`: one of the face's expressions (idle, listening, thinking, happy, excited, confused, sleeping). Anything else becomes `happy`.
- `action`: `null` or one name from the allowlist in `core/actions.py` (for V1: `celebrate`, `sound:<name>`, `start_activity:spelling`, `end_conversation`, `sleep`). Parameters are checked against a schema. Unknown actions are dropped and logged. AI output can never run code, change settings, install anything, or move hardware.

The response maps onto the existing `Reply` (speech → text, expression → mood, action → then/celebrate), so the robot loop barely changes.

**Getting structured output from small models.** Ollama's `format` option accepts a JSON schema, which keeps 1B-class models on track. If parsing still fails, the brain uses the raw text as `speech` with a default expression, provided it passes the output safety check. Otherwise it uses a scripted fallback ("Ooh, my circuits got muddled. Can you say that again?").

## 4. AI providers

```python
class AIProvider(ABC):
    name: str                      # "mock", "ollama", "openai"
    kind: Literal["mock", "local", "cloud"]
    def available(self) -> bool: ...
    def unavailable_reason(self) -> str: ...
    def models(self) -> list[str]: ...
    def generate(self, request: AIRequest) -> AIResult: ...   # blocking; called on the worker thread

@dataclass
class AIResult:
    text: str; model: str; ok: bool
    latency_s: float; prompt_tokens: int; completion_tokens: int
    error: str | None; timed_out: bool; cost_estimate: float = 0.0
```

- **Mock:** canned replies keyed by task type, configurable delay and failure rate, so routing, timeouts and fallbacks are testable without any model.
- **Local (Ollama):** standard-library HTTP to `http://localhost:11434` (`/api/tags` to detect the runtime and installed models, `/api/chat` to generate, `/api/ps` for loaded size). No new Python packages. If Ollama isn't running, the panel says "Ollama not found: install from ollama.com, then `ollama pull qwen3:0.6b`" and the mock provider is used. Models are never pulled automatically; the panel shows the pull command for an adult to run. Qwen3 thinking is turned off in the request and any `<think>` text is stripped.
- **Cloud (OpenAI):** standard-library HTTPS to the OpenAI API. Key from the `OPENAI_API_KEY` environment variable only, never from config files or the repo. Configurable model, timeout (default 10 s), up to 2 retries with backoff for timeouts, 429s and 5xx errors, token usage recorded, cost estimated from configurable prices per million tokens. Other providers are added as further `CloudProvider` subclasses.

## 5. Router

`ai/router.py` returns a `RoutingDecision(target, provider, model, reasons)`. The reasons are shown in the developer panel and stored with each request.

Modes: `local_only`, `cloud_only`, `automatic` (default `local_only` until cloud is reviewed).

Rules, applied in this order (earlier rules can't be overridden by later ones):

1. **Safety first.** `safety.check_input` classifies the request. Self-harm, abuse or danger topics get a fixed, kind, scripted reply that suggests talking to a grown-up. No model is used.
2. **Privacy gate.** Requests are `public`, `personal` (names, addresses, school, phone, email, health, family details, or anything the classifier isn't sure about) or `learning_record`. Only `public` requests can ever go to the cloud. The gate also requires **all** of: `cloud.enabled`, a set API key, `cloud.child_data_review_complete` (a parent setting, false by default, with a warning that it means the provider's terms and child-data rules have been reviewed), and either an adult test session or that review flag. Until then the cloud only receives text typed in an "adult test session" in the developer panel.
3. **Deterministic tasks.** Running spelling activity → learning engine. Basic maths ("what's 7 times 8") → a small Python calculator. Time and date, commands (stop, sleep, louder) and expressions → Python. Strong scripted intent matches (greetings, jokes, name) → scripted tier.
4. **Availability.** Offline (real or simulated) → local. Local unavailable → mock or scripted fallback with an explanation in the panel.
5. **Mode.** `local_only` → local. `cloud_only` → cloud if the gate allows, else local with the reason logged.
6. **Automatic.** Simple conversation → local. Complex explanation (task classifier: "why", "how does", "explain", long questions) → cloud only if the gate allows and today's estimated spend is under `cloud.daily_budget`; otherwise local.
7. **Performance.** Rolling local latency from `performance.py` adjusts the local timeout and the "keep it short" prompt hint. **Slowness never sends anything to the cloud unless rules 2 and 5/6 already allow cloud.** If local is too slow, the fallback is a scripted reply.
8. **Failure.** Cloud error or timeout → retry within limits → local → scripted. Local error → scripted, and repeated failures mark the provider unhealthy for a cool-down period.

Thresholds (`router.local_timeout_s`, `router.slow_local_s`, `cloud.timeout_s`, `cloud.daily_budget`) live in config. Adaptive changes to provider preference are logged in the adaptations table and can be reset.

## 6. Personality

`config/personality.json` holds the traits (joyful, playful, curious, friendly, encouraging, patient, slightly robotic, occasionally funny), style rules (British English, short replies, at most one follow-up question, don't repeat the last question, admit when unsure), firm rules (never claim to be human, never encourage dependence such as "I'm your best friend, you only need me", never ask for personal details, never give medical or safety advice beyond "ask a grown-up"), a few example exchanges, and the expression list.

`core/personality.py` builds one system prompt from it for every provider, so the personality is the same on local, cloud and mock. After generation it checks the reply: trims length, removes "As an AI language model" phrasing, rejects human claims, and avoids repeating the previous follow-up question. The scripted `responses.json` replies stay as written by hand in the same voice.

## 7. Spelling: Python is the examiner, AI is the tutor

The learning engine is deterministic and fully offline. It decides every mark. The AI only rephrases encouragement or explanations, and only when the router allows it.

**Outcomes.** Every spoken answer produces one of:

| Outcome | Meaning | Effect on progress |
|---|---|---|
| `unclear` | Low confidence or unknown words | Ask about the letter ("B for ball or D for dog?"). Never counted as wrong |
| `correct` | Letters match after read-back | Counted; hints used are recorded |
| `incorrect` | Clear letters, read back and confirmed, but wrong | Counted as a mistake |
| `help_requested` | "Clue", "I don't know" | Moves up the teaching ladder; not a mistake |
| `taught` | AlfieBot taught the word | Word goes back in the queue to retest later |

**Teaching ladder** (learning mode), per word:

1. Say the word and a sentence using it. Ask the child to spell it. **The spelling is not revealed.**
2. If unclear: clarify what was heard (existing letter clarification). No attempt is used up.
3. First genuine mistake: encourage and ask again, saying which part was right ("You got the start perfectly!") without giving letters away.
4. Second mistake or "clue": a clue that doesn't give the answer, such as the number of letters, the first sound, the number of syllables, or a rhyme.
5. Third mistake or "I don't know": **teach**. Split into syllables (be-cause), say the tricky part, give a memory tip ("Big Elephants Can Always Understand Small Elephants"), spell it together letter by letter, then ask the child to try once more straight away.
6. The word is marked `taught` and comes back later in the same session and at the next session.

Syllables and memory tips come from optional fields on each word that a parent can fill in, then a simple built-in syllable splitter, then (if allowed) an AI-written tip. Any AI-written hint before step 5 is checked so it can't contain the spelling: it is rejected if it spells out three or more letters of the word in order.

**Test mode** asks each word once, uses clarification for unclear letters, gives no clues, and records results. Whether AlfieBot says the correct spelling after a wrong test answer is a setting (`learning.reveal_after_test_mistake`, default false: the word goes into the practice list instead).

**Spaced repetition.** A Leitner system with five boxes, review intervals 1, 2, 4, 7 and 14 days (configurable). Correct first time with no hints moves the word up a box. Correct with hints keeps it in the same box. Incorrect or taught moves it to box 1. Unclear never moves it. Each session mixes due words, then this week's new words, then a couple of mastered words for confidence. Words wrong in two or more sessions are flagged as "repeated difficulty" in the parent view.

**Adaptations log.** Every automatic change (box moves, difficulty changes, more clues earlier for a word, shorter sessions after several wrong answers in a row, provider preference) is written to an `adaptations` table with the reason and the old and new values. The parent view can undo one or reset all.

**Letter recognition comparison.** Two modes, chosen per session or in settings:

- *Letter-by-letter:* the recogniser grammar accepts one letter or command per utterance. AlfieBot gives a short chirp after each letter. This is slower but each letter gets its own confidence.
- *Continuous:* the current behaviour, a run of letters per utterance.

The existing letter test tool gains a mode switch and a confused-pairs test set (B/D, M/N, P/T, F/S, plus the existing C/G/T and A/H/J). Results go to SQLite and a CSV report compares accuracy, clarification rate and time per word for each mode. Tests use adult voices, synthetic TTS audio and simulated recogniser output, never recordings of a child.

**The robot screen shows only the face during spelling.** The letters overlay moves to the developer panel.

## 8. Memory

- **Conversation memory** (`core/memory.py`): the last N turns (default 10) in RAM, cleared when AlfieBot goes to sleep or after `memory.conversation_idle_minutes`. Not written to disk by default (`memory.keep_conversation_days: 0`). Before any turn goes into memory or a prompt, the safety module masks personal details it detects.
- **Learning memory** (SQLite): lists, words, attempts, sessions, review schedule, adaptations, approved preferences (for example "likes dinosaur examples", only after a parent approves it in the panel).
- Both are independent of the AI provider, so switching providers changes nothing stored.
- **Parent controls** in the panel: view progress, view the adaptations log, delete a list, reset one word, reset all learning data, clear conversation memory, and export to CSV.

### SQLite schema (first version)

```text
word_lists(id, week, title, created_at)
words(id, list_id, word, syllables, tip, difficulty)
word_progress(word_id, box, due_on, attempts, correct, incorrect, taught, last_seen)
sessions(id, activity, mode, started_at, ended_at, score, total, recognition_mode)
attempts(id, session_id, word_id, at, outcome, answer, hints_used, clarifications,
         min_confidence, recognition_mode, provider)
adaptations(id, at, kind, target, old_value, new_value, reason, reverted_at)
preferences(key, value, approved_at)
ai_requests(id, at, machine, provider, model, task, route_reasons, latency_ms,
            prompt_tokens, completion_tokens, tokens_per_s, ok, error, timed_out,
            memory_mb, cost_estimate)
schema_version(version)
```

On first run, the existing `data/spellings/*.json` and `data/progress.json` are imported. The JSON files are left in place as a backup.

## 9. Speech

The existing interfaces stay as they are (`SpeechRecognizer`, `TextToSpeech`, `WakeWordDetector`, `MicGate`). Additions in Phase 6:

- A quick "voice output on/off" (muted test mode) in the panel. `TranscriptOnlyTTS` already exists for this.
- A recognition-mode switch for letter-by-letter or continuous spelling.
- An experiment comparing Vosk (US model with letter grammar) against whisper.cpp or faster-whisper `tiny.en`/`base.en` for letters, because there is no British Vosk model. Only adopt it if it measurably helps and runs acceptably on a Pi.
- A real offline wake word (for example openWakeWord with a custom "Hey AlfieBot" model) after the brain work, behind the existing interface.
- Interruption: keep the button for barge-in. Voice barge-in needs echo cancellation and is left for later, because the mic gate is what stops AlfieBot hearing itself.

## 10. Hardware and future robotics

`hardware/actuators.py` adds interfaces for motors, wheel encoders, distance sensors, an IMU, a camera, servos and battery monitoring, each with a simulated version. The developer panel can trigger simulated sensor readings and faults.

Movement goes through a separate `MotionSafetyController` that accepts only high-level intents (`look_left`, `nod`, `turn_towards`, `stop`) with hard speed, range and time limits that the AI can't change. The conversational AI can only request allowlisted actions through `core/actions.py`. It never sets motor power, torque or positions directly. In V1 all of this is simulation only.

## 11. Simulator additions

New **AI panel** (overlay like the Voice panel):

- mode (local only, cloud only, automatic), provider and model pickers, installed-model list;
- runtime status ("Ollama running, 2 models" or why not), cloud status (key present, gate open or closed and why);
- "Simulate internet failure" and "Simulate local AI failure" switches;
- adult test session switch (the only way cloud can receive typed text before the child-data review);
- last routing decision with reasons;
- performance table per provider and model: requests, median and p90 latency, tokens per second, errors, timeouts, memory, estimated cost, and a **machine** column that says "laptop (measured)" and "Pi 5 (not yet measured)".

New **Learning panel**: due words, boxes, repeated difficulties, recent sessions with outcomes (correct, incorrect, unclear, taught), the adaptations log with undo, and reset buttons.

The main panel gains: voice output on/off, "Reset simulation data", and the spelling letters as heard (moved off the face).

## 12. Testing

New tests (all headless, synthetic data only, no network) cover: routing in every mode, local and cloud failure and timeouts, internet loss, the privacy gate (personal data never routed to cloud in any mode, including when local is slow), invalid AI JSON, unknown and unauthorised actions, the human-claim filter, conversation memory expiry, SQLite persistence across a simulated restart, JSON import, all spelling outcomes (correct, incorrect, ambiguous letters, recognition failure, help requested, repeated wrong answers, success after hints, teaching), switching provider mid-activity, the Leitner schedule, adaptation undo, and simulated hardware faults. Cloud tests use a fake HTTP server, never the real API.

## 13. Decisions for Jordan

1. **Extend in place** (new packages beside the existing ones) rather than renaming folders to match the brief exactly. *Recommended.*
2. **Keep JSON config** rather than YAML. *Recommended.*
3. **Test mode:** after a wrong answer, say the correct spelling, or don't and add the word to practice? *Recommend not revealing (configurable).*
4. **Order:** the brief puts the learning engine (Phase 5) after the AI work. Because spelling is the feature Alfie uses today and needs no AI, it could move up to straight after Phase 2. *Either works; I'd keep the brief's order unless spelling homework is urgent.*
