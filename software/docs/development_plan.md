# AlfieBot V1 development plan

*Phase 1 plan for approval.* Builds on [existing_system_audit.md](existing_system_audit.md) and [architecture_proposal.md](architecture_proposal.md).

Each phase ends with: all tests passing, a version number (V1 work continues the software numbering as v0.8, v0.9 and so on, reaching v1.0 at the end of Phase 7), a zip in the project files, and PowerShell install and run steps for Jordan's PC. Nothing that works today is removed without a named reason in this plan.

## Phase 1: Audit and architecture (this delivery)

- [x] Audit the v0.7 code (`existing_system_audit.md`)
- [x] Architecture proposal (`architecture_proposal.md`)
- [x] Development plan and checklist (this file)
- [x] **Jordan approved** on 27 October 2026 with the recommended choices: extend in place, keep JSON config, don't reveal the spelling after a wrong test answer, keep the brief's phase order

## Phase 2: Desktop simulator and brain skeleton (v0.8, done)

Goal: the new brain runs inside the existing simulator with the mock AI. The child-facing screen follows the brief.

- [x] Remove the spelling letters from the robot face; show them in the developer panel instead
- [x] `core/events.py`, `core/brain.py` on a worker thread; `robot.py` hands text to the brain and polls for the `BrainResponse`
- [x] `ai/provider_base.py`, `ai/mock_provider.py` (configurable delay and failures)
- [x] `core/actions.py` allowlist and `BrainResponse` validation
- [x] Developer panel: voice output on/off, reset simulation data, AI panel (mode, provider, model, simulate internet failure, simulate AI failure, last routing reasons)
- [x] Tests: brain threading, timeout fallback, invalid responses, unauthorised actions, face never shows letters
- [x] Also done early: a first router (`ai/router.py`) with the three modes, the parent cloud switch, an adult test session, simulated internet failure and cloud-to-local fallback, and in-memory performance statistics (`ai/performance.py`). Phase 4 completes the router; Phase 3 stores statistics in SQLite
- **Demo:** chat with the mock AI in the simulator; the face goes thinking, then speaking; turning on "simulate AI failure" gives a friendly scripted reply.

## OLED face upgrade (v0.9, done)

Added at Jordan's request before the next AI phase, from the "OLED Face Design & Animation Upgrade" brief and its reference image. Later phases move up one version number; Phase 7 is still v1.0.

- [x] New face design: near-black background, cyan rounded-square eyes with a soft glow, a small mouth; drawn from numbers and morphed, no image files
- [x] 16 expressions from the brief (plus listening and excited, which the robot's states already used)
- [x] Natural blinking (random, configurable range, sometimes double), eyes that move together, idle glances, smooth transitions, sleeping with floating ZZZ
- [x] Talking mouth follows the voice's loudness (Piper) or a timed animation (other voices), and settles back smoothly
- [x] `face/controller.py`: the only things the AI or other code may ask the face to do (approved expressions, look, look around, blink, talk test), validated and queued so nothing blocks speech, listening or spelling
- [x] Developer **Face test** panel in the simulator (every expression, blink, look, mouth test, speed, reset, demo); keys 1-9 and a demo cycle in face-only mode
- [x] Tests: all expressions render at three sizes, morphs keep shapes valid, eyes stay inside the face, blinking within limits, mouth during and after speech, AI cannot request angry/sleeping, spelling still works with the panel open
- **Demo:** `python run_face.py --windowed --demo`, or **Face test** then **Demo all 16** in the simulator.
- Not done: Raspberry Pi frame rate. On the Linux test machine one face frame takes about 14 ms at 1280x720 and 7 ms at 800x480 (3 ms with `"supersample": 1`); the Pi must be measured on the real hardware.

## Phase 3: Local AI brain (v0.10, done; v0.10.1 fixes from the first benchmark)

- [x] `config/personality.json`, `core/personality.py`, `core/memory.py`, `core/safety.py` (first version)
- [x] `ai/local_provider.py` for Ollama: detection, model list, chat with JSON schema output, thinking off, timeouts, streaming so a cancelled request stops early, warm-up; the pretend AI stands in when Ollama or the model is missing
- [x] Re-checked sizes on ollama.com (qwen3:0.6b 523 MB, gemma3:1b 806 MB, qwen3:1.7b 1.4 GB); Jordan approved installing Ollama and all three
- [x] Ollama 0.40.11 and the three models installed on the laptop (Jordan installed Ollama; the first install was missing its engine and had to be redone)
- [x] SQLite `ai_requests` table via `storage/database.py` with migrations; `ai/performance.py` saves to it
- [x] `tools/benchmark_models.py` with `benchmarks/questions.json`, Markdown and CSV report, SQLite, machine label
- [x] Benchmark run on the laptop: see `docs/benchmark_2026-10-27_laptop.md`. Its findings led to v0.10.1 (guarded topics, stricter output rules, default model qwen3:1.7b)
- [x] AI panel: Pretend AI / Ollama, model choice, Ollama status, privacy class of the last request; Pi 5 shown as "not measured"
- [x] Tests: personality checks, memory expiry, safety patterns, provider unavailable, missing model, malformed output, cancelled request, benchmark (all against a stand-in Ollama server)
- Not done yet: the brief's adaptive learning (Phase 5). The full privacy gate for the cloud came in Phase 4.
- **Demo:** a typed conversation with a local model on the laptop; benchmark report comparing the three models on laptop hardware.

## Phase 4: Hybrid router (v0.11, done)

- [x] `ai/connectivity.py`, `ai/router.py` with the rule order in the proposal; provider health (3 failures in a row rest a provider for 60 s; the pretend AI stands in for a resting local AI)
- [x] Privacy gate, parent settings `cloud.enabled` and `cloud.child_data_review_complete` (both off), adult test session switch (typed text only); requests about the child (first person or numbers) are "personal" and never go to the cloud
- [x] `ai/cloud_provider.py` (OpenAI Chat Completions, strict JSON schema) with environment-variable key, timeouts, limited retries with backoff, usage and cost estimates, daily budget from the statistics database
- [x] Deterministic tools: maths calculator (digits or words, remainders), time and date (`core/tools.py`)
- [x] A slow local AI asks for shorter answers; it never sends to the cloud without permission
- [x] AI panel: cloud on/off, provider, adult test session, child-data review (two clicks), key found or missing, spend today, gate reason
- [x] Tests with a fake cloud server: every routing table row in the brief, cloud failure → local, internet loss, slow local never goes to cloud without permission, personal data never goes to cloud in any mode, key never logged, budget, retries, refusal, cancel
- Not done: a call to the real OpenAI API. That needs Jordan's agreement, an adult's own key and made-up prompts.
- **Demo:** switch modes in the panel and watch decisions and reasons; pull the (simulated) internet and keep chatting locally.

The real OpenAI API is only called by an adult with their own key, with synthetic prompts, and only after Jordan agrees.

## Phase 5: Learning engine (v0.12, done)

- [x] SQLite learning schema (migration 2: `word_lists`, `words`, `word_progress`, `sessions`, `attempts`, `adaptations`, `preferences`); one-off import of `data/spellings/*.json` and `data/progress.json` (JSON kept as backup)
- [x] Examiner with explicit outcomes (correct, incorrect, unclear, help_requested, taught, skipped), reusing `spelling/letter_input.py`; each attempt saves clues used, clarifications and the lowest recogniser confidence. The examiner stays in `spelling/tutor.py`; the records are in `learning/store.py`
- [x] `learning/teaching.py` ladder: ask, clarify, retry with encouragement, clue (letters and beats, then first and last letter), teach (beats, tricky part, memory tip, spelling), try straight away, retest at the end of the session and the next day
- [x] Practice no longer reveals the spelling before the child tries; tests don't reveal it after a mistake (`learning.reveal_after_test_mistake`, default false)
- [x] `learning/schedule.py`: 5-box Leitner schedule (1, 2, 4, 7, 14 days); practice order due → new → this week → 2 learned words; repeated-difficulty flag gives an earlier clue; adaptations log with reasons and undo
- [x] Learning view as two new tabs in the Spelling homework panel (Progress, Changes): boxes, next review, counts, tricky words, sessions with outcomes, undo, reset one word, reset all learning, CSV export; words hidden during a test
- [x] Tests: correct, incorrect, ambiguous letters, recognition failure, help requested, repeated wrong answers, success after hints, teaching, restart persistence, JSON import, switching AI provider mid-activity, the schedule, adaptation undo, clue leak check
- Not done: optional AI phrasing for encouragement and tips. `teaching.leaks_spelling` (the "no spelling leak" check) is ready for it; everything works without AI. Approved learning preferences have a table but no panel yet.

## Phase 6: Voice integration (v0.13, built; laptop measurements to do)

- [x] Letter-by-letter vs continuous spelling (`spelling.recognition_mode`, panel button): one letter per utterance with a tick after each, or a run of letters; the session records which mode was used and each attempt its time
- [x] `speech/letter_compare.py` + `tools/measure_voice.py`: Piper voices (three speeds, optional hiss) say words built from B/D, M/N, P/T, F/S; Vosk hears them both ways; report of right first time, clarification rate, wrong-but-sure, per-pair accuracy and time per word, saved to `benchmarks/results/` and the `letter_trials` table. "Pairs" set added to the Letter test for adult voices
- [ ] Run `tools/measure_voice.py` and the Letter test on Jordan's laptop and record the results
- [ ] whisper.cpp or faster-whisper for letters: only if the Vosk results are poor, and only after Jordan agrees to the download
- [x] Offline wake word ("Hey AlfieBot") behind the `WakeWordDetector` interface, using the existing Vosk model with a wake grammar (`speech/wake_word.py`); parent setting `privacy.wake_word_enabled`, off by default; anything else heard while asleep is dropped unseen
- [x] Spoken AI replies through the voice profiles with the AI's expression; the eyes look around while a slow AI answer is on its way
- **Demo:** "Hey AlfieBot", a spoken chat with the local model, and a spoken spelling test, all with the mic and speakers on the laptop.

## Phase 7: Full system testing (v1.0)

- [ ] End-to-end scripted runs (simulated speech) for the acceptance criteria in brief section 19
- [ ] Long-run stability test (for example 2 hours of mock conversation), memory growth, database size
- [ ] Failure drills: kill Ollama, drop internet, corrupt the database, hardware faults in simulation
- [ ] Installation and operating guide (`docs/install_and_operate.md`)

## Phase 8: Raspberry Pi deployment preparation

- [ ] `docs/raspberry_pi_deployment.md`: Pi OS Bookworm 64-bit, Python 3.11 venv, apt packages, Ollama or llama.cpp on ARM, Piper and Vosk ARM wheels, audio (MAX98357A I2S, USB mic), display rotation, autostart service
- [ ] `tools/install_pi.sh` and a systemd unit
- [ ] Pi config profile (supersample 1, smaller model, longer local timeout)
- [ ] Pi benchmark run of the same question set once the Pi arrives
- Nothing will be described as Pi-compatible until it has been run on the physical Pi.

## How each release is delivered

1. Code on the branch and a pull request; tests pass in the cloud.
2. Zip and screenshots in the project files folder.
3. PowerShell steps for Jordan's PC (keep the existing `data` folder):

```powershell
cd $HOME\AlfieBot
Rename-Item software software_old
Expand-Archive "$HOME\Desktop\Alfie Bot\AlfieBot_software_vX.zip" -DestinationPath .
Copy-Item software_old\data software\data -Recurse
Copy-Item software_old\models software\models -Recurse
cd software
py -V:3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe run_simulator.py
```

## Acceptance criteria tracking

| Brief section 19 criterion | Phase |
|---|---|
| Conversation using local AI | 3 |
| Consistent personality | 3 (checked again in 7) |
| Eyes respond to conversation states | 2 (exists today) |
| Voice-only spelling test | 5 and 6 |
| Remembers progress after restart | 5 |
| Adapts future spelling activities | 5 |
| Router switches between simulated providers | 4 |
| Internet failure doesn't stop local functions | 4 |
| Child-data protections can't be bypassed by routing | 4 |
| Can later be configured for the Pi | 8 |

## New dependencies

None are required for Phases 2 to 5: `sqlite3`, `urllib`, `json` and `threading` are in the Python standard library. Ollama is a separate program an adult installs. Phase 6 may add a wake word package and, if the experiment justifies it, a Whisper-based recogniser. Each will be named and justified before it is added.
