# AlfieBot existing system audit

*Phase 1 of the "AlfieBot V1: AI Brain, Hybrid Router and Adaptive Learning Engine" brief. Audited 27 October 2026.*

This audit covers the software in `software/` at v0.7 ("Bubbly Bot"), commit `f978d8c` on branch `claude/project-thread-k9lqed` (PR #1). All 244 automated tests pass on Linux with Python 3.13 and pygame 2.6. Version 0.6 has been installed and run on Jordan's Windows 11 PC. Nothing has been run on a Raspberry Pi yet.

Read this together with [architecture_proposal.md](architecture_proposal.md) (the proposed design) and [development_plan.md](development_plan.md) (milestones and checklist).

## 1. Summary

AlfieBot is already a working, well-tested offline prototype. Python with pygame runs the face, a regex conversation engine, a spelling tutor with careful spoken-letter handling, offline speech recognition (Vosk) and offline text-to-speech (Piper, with Windows and espeak fallbacks). It has no AI language model and no cloud AI. Storage is JSON files, not SQLite.

The core is in good shape to extend. The face, speech, letter parsing, hardware layer and simulator are worth keeping. Five things conflict with the new brief and need changing, with your approval:

1. **The robot screen shows spelling letters.** Since v0.5, letters appear in boxes under the eyes while the child spells (`ui/face_view.py`, `draw_letters`). The brief forbids this.
2. **Practice mode reveals the spelling before the child tries.** Each practice word starts with "Because is spelled B-E-C-A-U-S-E. Now you try!", and the first wrong answer repeats the spelling. The brief wants the child to try first, then a clue, and teaching only after that.
3. **Progress does not separate a mishearing from a mistake.** The tutor already asks about unclear letters before marking, so a mishearing is never marked wrong. But the saved progress only records right or wrong. It does not record clarifications, hints, recognition confidence or "needed teaching".
4. **No spaced repetition or adaptation.** Words are practised in list order and tests shuffle the list. Nothing schedules revision or adapts difficulty.
5. **Progress is stored as JSON**, and the brief asks for SQLite.

## 2. Language, framework and dependencies

| Item | Current |
|---|---|
| Language | Python 3 (developed on 3.13; Jordan's PC uses 3.13.17 because pygame 2.6.1 has no wheels for 3.15) |
| UI framework | pygame 2.6, drawn by hand (no widget toolkit) |
| Required packages | `pygame`, `vosk`, `sounddevice`, `piper-tts` (`requirements.txt`) |
| Optional | `edge-tts` (online voice comparison only, `requirements-cloud.txt`), `pytest` (dev) |
| Pi-only | `gpiozero` (button), system `libportaudio2`, `espeak-ng` |
| Config | `config/alfiebot.json` merged over defaults in `alfiebot/config.py` |
| Data | `data/` folder: `spellings/<ISO week>.json`, `progress.json`, `letter_tests/` |
| Tests | 244 pytest tests in `tests/`, all headless (fake recogniser, fake TTS, dummy video driver) |
| Size | about 7,000 lines of application code |

There are type hints in places but not throughout. Logging uses the standard `logging` module with plain text messages, not structured fields.

## 3. Current architecture

```text
software/
├── run_simulator.py, run_face.py   entry scripts
├── config/alfiebot.json            settings (JSON with _comment keys)
└── alfiebot/
    ├── main.py                     argument parsing; simulator or face-only app
    ├── config.py                   defaults + JSON override, save_setting
    ├── core/
    │   ├── robot.py                AlfieBot class: the "brain" and flow controller
    │   ├── state_machine.py        RobotState transitions + listeners
    │   ├── states.py               RobotState, Expression and the state->face map
    │   └── transcript.py           in-memory conversation log
    ├── conversation/
    │   ├── intents.py              regex intents, wake phrase, normalise()
    │   ├── engine.py               Reply dataclass, picks replies, follow-up context
    │   └── responses.json          editable reply text, mood and next state
    ├── spelling/
    │   ├── words.py                letter names, cleaning, spell_out
    │   ├── letter_input.py         spoken-letter parser, confusion sets, commands, grammar
    │   ├── lists.py                weekly lists (JSON per ISO week)
    │   ├── progress.py             per-word attempts and sessions (JSON)
    │   ├── tutor.py                add / practise / test activities (610 lines)
    │   └── responses.json          tutor wording
    ├── face/
    │   ├── poses.py                numeric FacePose per expression
    │   ├── engine.py               easing, blinking, eye wander, particles
    │   └── renderer.py             pygame drawing with supersampling and glow
    ├── speech/
    │   ├── base.py                 abstract SpeechRecognizer, TextToSpeech, WakeWordDetector
    │   ├── vosk_recognizer.py      Vosk + sounddevice, grammar switching, per-word confidence
    │   ├── tts.py                  SegmentedTTS, WindowsTTS, EspeakTTS, engine selection
    │   ├── piper_tts.py            Piper voices with pitch/speed via resampling
    │   ├── cloud_tts.py            edge-tts comparison voice (off by default)
    │   ├── voice_profiles.py       classic / bubbly personalities -> voice profiles
    │   ├── sounds.py               generated chirps
    │   ├── mic_gate.py             keeps the mic deaf while AlfieBot talks
    │   ├── letter_test.py          letter recognition test sessions and reports
    │   └── null.py, text.py, factory.py
    ├── hardware/
    │   ├── base.py                 Platform dataclass, InteractionButton
    │   ├── detect.py               Pi detection via /proc/device-tree/model
    │   ├── simulator.py            keyboard/mouse button
    │   └── raspberry_pi.py         gpiozero button (untested on a Pi)
    ├── storage/json_store.py       atomic JSON files inside data/
    └── ui/
        ├── simulator_app.py        window: face + developer panel + transcript + log
        ├── face_app.py             face only (what the Pi shows), demo mode
        ├── face_view.py            FaceEngine + renderer + spelling letters overlay
        ├── spelling_panel.py       Lists / Progress overlay
        ├── voice_panel.py          voice settings and "Try it"
        ├── letter_test_panel.py    letter recognition test overlay
        └── widgets.py, log_capture.py
```

### Application flow

1. `main.py` loads the config, picks the simulator or Pi platform (`hardware/detect.py`), builds the speech engines and starts either `SimulatorApp` (laptop) or `FaceApp` (Pi, full screen).
2. Each frame (60 fps) the app calls `AlfieBot.update(dt)`. This runs timers, finishes speech, counts down the listen timeout, opens or closes the microphone, polls the recogniser and polls the button. Everything runs on the main thread except audio capture and speech output, which have their own threads.
3. Input arrives as text: typed in the developer panel, or a Vosk result. `AlfieBot.handle_text` checks for the wake phrase ("Hey AlfieBot"), holds text that arrives while AlfieBot is talking, and otherwise calls `_reply_to`.
4. `_reply_to` sends the text to the spelling tutor when an activity is running, otherwise to the regex `ConversationEngine`. Both return a `Reply(text, intent, mood, then, celebrate)`.
5. The robot goes THINKING for 0.7 s (or CELEBRATING), then SPEAKING. The face listener receives the mood as an `Expression`. TTS speaks with a voice profile chosen from the reply type.
6. When speech ends, the reply's `then` picks the next state (LISTENING, a spelling state, IDLE or SLEEPING). After 60 s with no answer AlfieBot goes IDLE, then SLEEPING after 300 s.

The state machine has 10 states: SLEEPING, IDLE, LISTENING, THINKING, SPEAKING, SPELLING_SETUP, SPELLING_PRACTICE, SPELLING_TEST, CELEBRATING and ERROR. They map to 7 expressions: sleeping, idle, listening, thinking, happy, excited and confused.

## 4. Component findings

### Speech recognition

- **Engine:** Vosk with the `vosk-model-small-en-us-0.15` model (40 MB, US English, Apache 2.0), downloaded by `tools/download_speech_model.py`. The microphone is read through `sounddevice` at 16 kHz.
- **Two modes already exist.** In conversation mode recognition is free text. While a child spells, the recogniser is restricted to a letter grammar (letter names, "B for ball" words and commands), and every word keeps its own confidence score.
- **Privacy:** the mic opens only in listening states, only when a parent has set `privacy.microphone_enabled` (off by default), and never while AlfieBot speaks. `MicGate` adds a 0.6 s deaf tail after speech so AlfieBot can't hear itself. Audio is never written to disk.
- **Push-to-talk** mode exists alongside open mic.
- **Wake word:** there is no real detector. `NoWakeWordDetector` is a placeholder. "Hey AlfieBot" only works when typed, or when it is heard while the mic is already open. The physical or space-bar button wakes AlfieBot.
- **Gap: British English.** Vosk publishes no British English model; its English models are US or Indian English. British letter names ("zed", "aitch", "haitch") are handled by the letter grammar, but the acoustic model is American. This is a likely cause of the letter difficulties and needs measuring (see the letter recognition plan in the development plan).
- **Gap:** real-microphone recognition has been tested on Jordan's PC but there are no recorded accuracy figures yet.

### Text-to-speech

- **Engines:** Piper (default voice `en_GB-cori-medium`, offline), Windows System.Speech through a persistent PowerShell process, and espeak-ng on Linux and the Pi. `tts_engine: auto` picks Piper if a voice is installed, otherwise the platform voice.
- **Voice profiles:** normal, excited, teacher and sleepy (speed, volume, pauses, pitch). The "bubbly" personality maps reply roles to profiles and sometimes adds cheers. Letters are spoken one by one with pauses (`SegmentedTTS`).
- **Interruption:** pressing the button while AlfieBot talks stops speech and starts listening. Speech can't be interrupted by voice, because the mic is closed while AlfieBot talks (on purpose, to avoid hearing itself).
- **Cloud:** `cloud_tts.py` (edge-tts) is a comparison voice, off by default behind `speech.allow_cloud_voices`. It only sends AlfieBot's own words.

### Facial animation

- `face/poses.py` defines a numeric pose per expression (eye size, lid angles, pupil offset, mouth curve, colour). `face/engine.py` eases between poses and adds blinking, gaze wander, a talking mouth and particles (sleep "z"s, excitement sparkles). `face/renderer.py` draws with 2x supersampling and glow. It draws in about 7 ms per frame at 1280x720 on the cloud test machine; `display.supersample: 1` is the planned Pi fallback.
- The face is driven only by `Expression` values and a `talking` flag. It doesn't know about conversation or spelling. That is the right separation for the new brain.
- **Conflict:** `ui/face_view.py` also draws the spelling letters under the eyes. This must be removed from the robot screen. The developer panel can keep showing them.
- **Gap:** no separate "speaking" pose. SPEAKING uses the reply's mood with an animated mouth, which meets the "speaking animation" requirement. Listening and thinking already have their own poses.

### Spelling activity

- **Lists:** one JSON file per ISO week in `data/spellings/`. Words can be added by voice (with a yes/no confirmation), in the Lists overlay, or from `examples/spelling_list_example.json`.
- **Modes:** "add", "practice" (learning mode, 3 tries per word) and "test" (shuffled, one try per word, then an offer to practise missed words).
- **Spoken answers:** `letter_input.py` turns recogniser words into `Letter`, `Command` and `Unknown` tokens. It handles "B for ball" and NATO words, "double T", fillers ("capital", "letter"), and commands such as delete, start again, finished, repeat, clue, skip and "I don't know". Letters below `min_confidence` (0.75) are never guessed. AlfieBot asks "Was letter 2 B for ball, D for dog or P for pig?", using the confusion sets B/D/P, C/G/T, M/N, F/S and A/H/J. The target word is never used to correct what was heard. By default the whole answer is read back for a "yes" before it is marked. After 5 s of quiet the answer is checked.
- **Marking is deterministic** (`letters == word`). No AI is involved. That already matches "Python is the examiner".
- **Conflicts with the brief:**
  - Practice reveals the spelling up front (`practice_word`) and after every wrong answer (`practice_wrong`).
  - Test mode reveals the spelling after a wrong answer (`test_wrong`). This may be acceptable after marking, but it is worth a decision.
  - Clues are fixed: first letter and length, then half the letters, then the whole spelling. There is no syllable or memory-technique teaching, and no "practise together then retest later".
  - There is no record of hints, clarifications or recognition confidence per attempt, and no spaced repetition.
- **Strength:** the letter test tool (`speech/letter_test.py`, `tools/letter_test.py`, simulator panel) already measures per-letter accuracy, confidence, latency and confusions, and saves results to `data/letter_tests/`. It can be extended to compare letter-by-letter and continuous modes.

### Conversation and AI

- **No AI integration exists.** There is no local model, cloud model or router. Conversation is the regex `ConversationEngine` with about 20 intents (greeting, how are you, jokes, name, age, spelling help, goodbye, repeat and so on) and editable replies in `responses.json`. Anything else gets a fallback reply.
- `Reply.mood` already plays the role of the brief's `expression` tag, and `Reply.then` decides the next state. This is the natural place to attach validated AI output.
- There is short-term context only (`expecting`: one pending question). There is no conversation memory beyond the on-screen transcript.

### Hardware

- `Platform` bundles the button, recogniser, TTS, wake word and sounds. The simulator and Pi platforms share everything except the button. The Pi platform uses `gpiozero` and is **untested on a Pi**. There are no interfaces yet for motors, sensors, a camera or a battery.

### Storage and privacy

- `JsonStore` writes atomically inside `data/` and refuses paths outside it. There is a parent button to delete all local data. No audio is stored. There is no per-category deletion or review screen beyond the Lists and Progress overlays.

### Simulator and developer panel

The current panel has Start/Stop, jump-to-state buttons, expression previews, mic on/off, open or push-to-talk, a simulated button, typed or simulated-speech input with high/low confidence, spelling buttons (Lists, Add by voice, Practise, Test), Letter test, Voice settings, Allow mic (parent), Delete local data, full-screen face, transcript and debug log.

Compared with the brief, the panel is missing: voice output on/off (there is a voice panel but no quick mute), AI mode selection, model selection, simulated internet failure, AI performance statistics, and a learning progress view beyond per-word counts. "Reset simulation data" exists as "Delete local data".

## 5. Retain, refactor or replace

| Component | Decision | Reason |
|---|---|---|
| Face engine, poses, renderer | **Retain** | Works, tested, already independent of the brain |
| `face_view.draw_letters` on the robot screen | **Remove** (keep in the dev panel) | Brief forbids letters on the robot screen |
| State machine, states, expressions | **Retain**, add states if needed | Matches listening, thinking, speaking, happy, confused, sleeping |
| `core/robot.py` | **Refactor** | Keep the timing, mic and state logic. Move reply generation into a new `Brain` so the AI call runs off the frame loop |
| Regex `ConversationEngine` + `responses.json` | **Retain as the scripted tier** | Instant offline answers for greetings, jokes and commands; the fallback when no AI is available |
| `letter_input.py`, `words.py` | **Retain** and extend | Already does confidence, confusion sets, clarification and never uses the target word |
| `tutor.py` | **Refactor** into the learning engine | Keep the activity flow and spoken commands; replace the "reveal first" practice and fixed clues with the teaching sequence; return explicit outcomes |
| `progress.py`, `lists.py` (JSON) | **Replace** with SQLite, with a one-off import | Brief requires SQLite and richer records |
| `JsonStore` | **Retain** for settings-like files (letter test results, panel state) | Still useful; not for learning data |
| Speech interfaces, Vosk, Piper, Windows, espeak, MicGate, voice profiles | **Retain** | Already interchangeable behind `speech/base.py` |
| Wake word | **Add later** (Phase 6) | Placeholder today |
| `hardware/` | **Retain** and extend with an action interface | Platform split is right; add a simulated actuator and sensor layer |
| pygame simulator | **Retain** and extend with an AI panel | Works on Windows and is the planned Pi stack; PySide6 would be heavy on the Pi and a rewrite |
| `config/alfiebot.json` | **Retain JSON** (see the proposal) | Avoids a PyYAML dependency and keeps Jordan's existing settings working |
| edge-tts comparison voice | **Retain**, off by default | Sends only AlfieBot's words; must stay behind the parent switch |

## 6. Dependencies and compatibility risks

| Risk | Impact | Mitigation |
|---|---|---|
| No British English Vosk model | Letter recognition accuracy for British children | Measure with the letter test tool; compare with whisper.cpp or faster-whisper `tiny.en`/`base.en` in Phase 6; keep clarification as the safety net |
| pygame wheels lag new Python releases | Install fails on Python 3.15 (seen on Jordan's PC) | Pin Python 3.11 to 3.13 in the docs; Pi OS Bookworm ships 3.11 |
| Local LLM speed on a Pi 5 | Laptop timings won't carry over; 1B to 2B models may take several seconds per reply | Benchmark tool records machine type; keep replies short; scripted tier answers common phrases instantly; never assume Pi figures from laptop runs |
| Pi 5 RAM (8 GB vs 16 GB) | Vosk (~300 MB), Piper (~100 MB), the face and a 1B to 2B model (1 to 2.5 GB at 4-bit) fit in 8 GB | Track memory in benchmarks; one model loaded at a time |
| Small models produce invalid JSON | Broken expression tags or replies | Use Ollama's JSON schema `format` option, validate, and fall back to plain text with a default expression |
| Qwen3 "thinking" output | Slow, long hidden reasoning | Disable thinking in the request; strip any `<think>` blocks before use |
| Ollama not installed on the PC | Local AI unavailable | Detect at start-up, show why in the panel, and use the mock provider |
| Cloud child-data rules | Legal and policy exposure | Cloud off by default; a privacy gate blocks child data; adult or synthetic testing only until the provider's terms are reviewed |
| Blocking network calls in the 60 fps loop | Face freezes while AI thinks | Run providers on a worker thread; the face stays in THINKING |
| `gpiozero`, I2S amp and USB mic untested on a Pi | Unknown Pi issues | Phase 8 only; no claims until tested on hardware |
| Restructuring the package | Breaks Jordan's install and 244 tests | Add new packages beside the existing ones instead of renaming folders; keep `run_simulator.py` working |

Model notes (to re-check before any download in Phase 3): Qwen3 0.6B and 1.7B are Apache 2.0 on Ollama (`qwen3:0.6b`, `qwen3:1.7b`). Gemma 3 1B (`gemma3:1b`) is under Google's Gemma Terms of Use and Prohibited Use Policy, which allow use and redistribution with conditions but are not an open-source licence.

## 7. Repository state

- `main` holds only Jordan's uploaded CAD V0.1 files.
- PR #1 (`claude/project-thread-k9lqed`) holds software v0.1 to v0.7 and is not merged. PR #2 (`claude/project-thread-42svw3`) holds CAD v0.2/v0.3 and software v0.6.
- This Phase 1 work is on `claude/project-thread-m5dfb8`, branched from PR #1, so it shows only the new documents. Merging PR #1 first would give V1 a clean base.
