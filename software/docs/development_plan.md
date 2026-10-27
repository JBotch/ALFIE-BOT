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

## Phase 3: Local AI brain (v0.10)

- [ ] `config/personality.json`, `core/personality.py`, `core/memory.py`, `core/safety.py` (first version)
- [ ] `ai/local_provider.py` for Ollama: detection, model list, chat with JSON schema output, thinking off, timeouts
- [ ] Re-check model licences and sizes, then (with Jordan's go-ahead) pull `qwen3:0.6b`, `qwen3:1.7b`, `gemma3:1b` on the PC
- [ ] `ai/performance.py` + SQLite `ai_requests` table, `storage/database.py` with migrations
- [ ] `tools/benchmark_models.py` with `benchmarks/questions.json` (greetings, simple chat, explanations, tricky "are you human?" and personal-data prompts), CSV and SQLite output, machine label
- [ ] Performance view in the AI panel, with Pi 5 shown as "not measured"
- [ ] Tests: personality checks, memory expiry, provider unavailable, malformed model output (using the mock and a fake Ollama server)
- **Demo:** a typed conversation with a local model on the laptop; benchmark report comparing the three models on laptop hardware.

## Phase 4: Hybrid router (v0.11)

- [ ] `ai/connectivity.py`, `ai/router.py` with the rule order in the proposal
- [ ] Privacy gate, parent settings `cloud.enabled` and `cloud.child_data_review_complete` (both off), adult test session switch
- [ ] `ai/cloud_provider.py` (OpenAI) with environment-variable key, timeouts, limited retries, usage and cost estimates, daily budget
- [ ] Deterministic tools: maths calculator, time and date
- [ ] Tests with a fake cloud server: every routing table row in the brief, cloud failure → local, internet loss, slow local never goes to cloud without permission, personal data never goes to cloud in any mode
- **Demo:** switch modes in the panel and watch decisions and reasons; pull the (simulated) internet and keep chatting locally.

The real OpenAI API is only called by an adult with their own key, with synthetic prompts, and only after Jordan agrees.

## Phase 5: Learning engine (v0.12)

- [ ] SQLite learning schema; one-off import of `data/spellings/*.json` and `data/progress.json` (JSON kept as backup)
- [ ] `learning/spelling.py` examiner with explicit outcomes (correct, incorrect, unclear, help requested, taught), reusing `spelling/letter_input.py`
- [ ] `learning/teaching.py` ladder: ask, clarify, retry, clue, teach (syllables, tricky part, memory tip, spell together), retest later
- [ ] Practice no longer reveals the spelling before the child tries
- [ ] `learning/adaptive.py`: Leitner schedule, repeated-difficulty flags, adaptations log with undo
- [ ] Optional AI tutor phrasing for encouragement and tips, with the "no spelling leak" check; works fully without AI
- [ ] Learning panel; parent review, delete, reset and CSV export
- [ ] Tests: every testing bullet in brief section 11, including restart persistence and switching provider mid-activity
- **Demo:** a voice-only spelling session where AlfieBot clarifies an unclear letter, gives a clue, teaches a word, and the next day's session brings the tricky words back.

## Phase 6: Voice integration (v0.13)

- [ ] Letter-by-letter vs continuous recognition modes; extend the letter test tool to compare them on B/D, M/N, P/T, F/S
- [ ] Measure on Jordan's PC with adult voices and synthetic Piper audio; report accuracy, clarification rate and time per word
- [ ] Try whisper.cpp or faster-whisper for letters if Vosk accuracy is poor (no British Vosk model exists); adopt only if it helps
- [ ] Offline wake word ("Hey AlfieBot") behind the existing interface
- [ ] Speech and expression timing, spoken AI replies through the voice profiles
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
