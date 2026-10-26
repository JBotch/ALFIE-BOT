# AlfieBot software

Python software for AlfieBot, the 3D-printed companion robot. The same code
runs as a desktop simulator on a normal computer and, later, on the robot's
Raspberry Pi 5.

**Version 0.2, Stage 2 of 5: typed conversation and state transitions.**

> Tested on Linux with Python 3.13 and pygame 2.6.1 (121 automated tests,
> plus headless launches of both apps). Stage 1 also ran on Windows 11 with
> Python 3.13. **It has not been run on Raspberry Pi hardware yet.** The
> Pi-specific code (GPIO button) is written but untested.

## What Stage 2 adds

- Typed conversation. Type in the panel (or click a quick phrase) as if you
  were speaking. AlfieBot only listens after **"Hey AlfieBot"** or the robot
  button (Space). "Hey AlfieBot, tell me a joke" works in one go.
- The full flow: wake (eyes open, greeting) -> LISTENING -> THINKING ->
  SPEAKING -> LISTENING. After 1 minute with no answer AlfieBot goes back to
  IDLE, and after 5 minutes idle it falls asleep. Text typed while it's
  talking is answered straight after.
- Deterministic intents: how are you, what can you do, jokes, name, who made
  you, age, thanks, hello, goodbye (goes to sleep), never mind, say that
  again, "I'm good" / "I'm sad" (offers a joke and suggests telling a
  grown-up), and "help me with my spellings" (asks add / practise / test;
  the tutor itself arrives in Stage 3). Anything else gets a clear "I don't
  know how to do that yet" with a confused face.
- Several replies per intent, never the same one twice in a row. They're in
  `alfiebot/conversation/responses.json`, so you can edit what AlfieBot says.
- The face follows the conversation: excited greeting, thinking pause,
  happy or confused while talking (with a moving mouth), attentive while
  listening.
- The robot button wakes AlfieBot, cuts it off mid-sentence to listen, or
  keeps it listening longer.
- There's no voice yet (Stage 4). AlfieBot's lines appear in the transcript
  and it "talks" for as long as the sentence would take to say.

## What Stage 1 does

- A simulator window with AlfieBot's face in a 16:9 viewport framed like the
  robot's 5-inch screen, and a developer panel beside it.
- An animated face engine with all seven expressions: sleeping, idle,
  listening, thinking, happy, excited and confused. The face glides between
  them, blinks, looks around, bounces when excited, shows "z"s when asleep
  and a "?" when confused, and moves its mouth while "speaking".
- The robot state machine (SLEEPING, IDLE, LISTENING, THINKING, SPEAKING,
  SPELLING_SETUP, SPELLING_PRACTICE, SPELLING_TEST, CELEBRATING, ERROR).
  Changing state changes the face.
- A face-only mode that runs full screen, for the robot's own display.
- The developer panel skeleton: start/stop, current state and expression,
  state and expression buttons, typed "speech" box, microphone status,
  push-to-talk button, transcript, debug log, spelling area (Stage 3) and a
  parent area with **Delete local data**.

Not built yet, on purpose: spelling tutor (Stage 3), speech output and microphone (Stage 4), wake word and Pi hardware
(Stage 5). The microphone status says "Off" and the wake word says "not
configured" because none exists yet. Nothing pretends otherwise.

## Run it on Windows

1. Install Python 3.12 or 3.13 from <https://www.python.org/downloads/>.
   Tick **Add python.exe to PATH** in the installer.
2. Download the project (the `software` folder), open **Command Prompt** in
   that folder and run:

   ```bat
   py -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   python run_simulator.py
   ```

3. For just the face: `python run_face.py` (windowed) or
   `python run_face.py --fullscreen --demo` (full screen, cycling expressions).

If you used the new **Python install manager** from python.org, it installs
the newest Python (3.15 or later), which pygame doesn't support yet. Run
`py install 3.13` and create the venv with `py -3.13 -m venv .venv`.

To run the tests: `pip install -r requirements-dev.txt` then `python -m pytest`.

If `pip install pygame` fails on a brand-new Python version, install
Python 3.12 instead (pygame wheels lag new Python releases), or try
`pip install pygame-ce`, a compatible fork.

## Run it on Raspberry Pi OS

For Raspberry Pi OS Bookworm (64-bit, desktop). Open a terminal **on the
Pi's desktop** (not over SSH, because the window needs the screen):

```bash
sudo apt update
sudo apt install -y git python3-venv
git clone https://github.com/JBotch/ALFIE-BOT.git
cd ALFIE-BOT/software
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m alfiebot
```

On a Pi, `python -m alfiebot` detects the Pi and opens the **face only, full
screen** (press Esc to quit). Other options:

```bash
python run_simulator.py                 # the full simulator with the panel
python run_face.py --windowed --demo    # face in a window, cycling expressions
python -m pytest                        # tests (after pip install -r requirements-dev.txt)
```

If pip can't install pygame on the Pi, use the system package instead:
`sudo apt install python3-pygame`, then create the venv with
`python3 -m venv --system-site-packages .venv`.

The Pi Touch Display 2 starts in portrait. Set it to landscape in
**Screen Configuration** first. If the face runs slowly on the Pi, set
`"supersample": 1` in `config/alfiebot.json` (smoother edges cost about
3x more drawing time).

## Controls

| Where | Control | Does |
|---|---|---|
| Panel | Start / Stop | Wake the robot (IDLE) / put it to sleep. Typed input is ignored while stopped |
| Panel | Set state | Any of the ten states; the face follows |
| Panel or keys 1-7 | Preview expression | Show one expression; 0 or "Follow state" goes back to the state's face |
| Panel or Space | Robot button | Wakes AlfieBot, interrupts it to listen, or keeps it listening. Real push-to-talk arrives in Stage 4 |
| Panel, T or Enter | Simulated speech | Type what you would say, or click a quick phrase |
| Panel or F11 | Face full screen | Face only; F11 or Esc returns |
| Panel | Delete local data | Click twice to delete the `data/` folder |
| Face-only mode | 1-7, 0, D, Space, Esc | Expressions, follow state, demo cycle, button, quit |

## What to test before Stage 3

1. Press Start, then type "Hey AlfieBot". The eyes open, AlfieBot greets you
   (excited face, moving mouth), then listens. The state line counts down.
2. Have the example chat: "I'm good", "How are you?", "What can you do?".
   Replies should vary when you repeat things.
3. Try jokes, "say that again", "I'm sad", "help me with my spellings", and
   something it doesn't know (it should look confused and say what it can do).
4. Type "How are you?" while it's IDLE: it should ignore you and remind you
   to say "Hey AlfieBot" first.
5. Wait 1 minute while it's listening (back to idle), and say "goodbye" (asleep).
6. Press Space while it's talking: it stops and listens.
7. Read through `responses.json` and change anything that doesn't sound like
   AlfieBot to you and Alfie.

## Stage 1 checks

1. The simulator opens and the face starts asleep, with slow breathing, "z"s
   floating up and an occasional sleepy flutter.
2. **Start** wakes AlfieBot: the eyes open smoothly with a double blink.
3. Each expression (keys 1 to 7) looks right to you and Alfie, and changes
   smoothly, with no jumps or flicker.
4. Idle blinks every few seconds and glances around.
5. Every state button gives the expected face (for example SPEAKING = happy
   with a moving mouth, ERROR = confused, CELEBRATING = excited).
6. **F11** shows the face full screen and Esc returns to the panel.
7. `python run_face.py --fullscreen --demo` on the Pi's 5-inch display: the
   face fills the screen in landscape and the animation is smooth. Note the
   fps shown in the simulator panel if it isn't.
8. `python -m pytest` passes on your computer.

Please tell us anything about the face design (eye size, colour, mouth,
speed of blinks) before Stage 2, since it's easy to tune now.

## Project layout

```
software/
  run_simulator.py         simulator with the developer panel
  run_face.py              face only (for the robot's screen)
  config/alfiebot.json     settings, including the parent/privacy section
  examples/                example weekly spelling list
  tools/render_expressions.py   saves a PNG of every expression
  tests/                   automated tests (pytest)
  alfiebot/
    main.py                entry point and command-line options
    config.py              loads config/alfiebot.json over built-in defaults
    core/                  robot, state machine, states -> expressions, transcript
    face/                  poses (numbers per expression), engine (animation), renderer (pygame)
    speech/                recogniser, text-to-speech and wake-word interfaces;
                           mic_gate.py keeps the mic deaf while AlfieBot talks
    conversation/          intents.py (phrase matching), responses.json (what AlfieBot says), engine.py
    spelling/              Stage 3: lists, learning mode, test mode, progress
    hardware/              simulator vs Raspberry Pi (button), auto-detected
    storage/               local JSON files (atomic writes, delete all)
    ui/                    simulator window, widgets and face-only app
```

The core (`core/`, `face/engine.py`, `speech/`, `storage/`) doesn't import
pygame, so it can be tested on its own and reused unchanged on the Pi.
Swapping in a real speech or wake-word engine later means writing one class
that implements the interface in `speech/base.py`.

## Privacy

- Everything runs offline. There is no internet chatbot.
- The microphone is off by default (`privacy.microphone_enabled` in the
  config) and its status is always shown in the panel.
- Audio is never saved (`privacy.keep_audio_recordings` is false).
- The transcript is kept in memory only. Spelling data (from Stage 3) is
  saved as JSON in `data/`, which **Delete local data** removes.
