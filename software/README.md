# AlfieBot software

Python software for AlfieBot, the 3D-printed companion robot. The same code
runs as a desktop simulator on a normal computer and, later, on the robot's
Raspberry Pi 5.

**Version 0.5: spelling recognition upgrade** (Stage 4 of 5, plus the
first half of the speech recognition and voice upgrade).

> Tested on Linux with Python 3.13 and pygame 2.6.1 (all automated tests,
> plus headless launches of both apps, and the espeak-ng voice). The speech
> recogniser was tested with stand-in recognition results only, because the
> test machine has no microphone and couldn't download the speech model.
> Version 0.4 also ran on Windows 11 with Python 3.13 and a real microphone.
> **It has not been run on Raspberry Pi hardware yet.** The Pi-specific code
> (GPIO button) is written but untested.

## What version 0.5 adds: spelling recognition

Conversation and spelling are now recognised differently. While Alfie
spells a word in practice or a test:

- **Letters appear under AlfieBot's eyes as they are heard**, one box per
  letter: blue = heard clearly, amber = AlfieBot will check it, grey = still
  being heard. The same letters show in the panel.
- Letters can be said **one at a time or in short runs** ("bee ee see",
  pause, "ay you ess ee"). "Double s" works. AlfieBot stays quiet while the
  letters build up.
- **Spoken commands while spelling:** "delete" (rub out the last letter),
  "start again" (clear them all), "repeat" (say the word again; the letters
  are kept), "finished" (check it), "what have I got" (read them back),
  "stop". In practice there are also "clue", "slower", "skip" and
  "restart" (back to the first word).
- **Unsure letters are asked about, never guessed.** Each letter has its own
  confidence score from the recogniser. If one is low, AlfieBot asks about
  that letter, offering the letters that sound alike: "Was letter 2 B for
  ball, D for dog or P for pig?" Alfie can answer "D", "D for dog", "dog" or
  "the second one". Anything that wasn't a letter shows as "?" and gets
  asked about too.
- **Read back before marking.** After "finished" (or 5 seconds of quiet),
  AlfieBot reads the letters back ("You spelled B-E-C-A-U-S-E. Is that
  right?") and only marks it after a yes. After a no, Alfie can say
  "delete", "start again" or more letters.
- **AlfieBot never uses the target word to fix what it heard**, so a
  mishearing can't turn a wrong spelling into a right one, and an unsure
  letter can't turn a right spelling into a wrong one.
- **Typing still works** as before and is marked straight away.
- **Letter recognition test** (panel button **Letter test**, or
  `python tools/letter_test.py`): shows letters one at a time, records what
  was heard, the confidence, the recognition time, whether AlfieBot would
  have asked, and the final answer. It saves results (never audio) in
  `data/letter_tests/` and reports accuracy, the most common mix-ups, the
  letters that sound alike (B/D/P, C/G/T, M/N, F/S, A/H/J), and results by
  speaker and speed.
- Panel: "Listening for: letters" or "conversation", the last thing heard
  with its confidence, and the letters so far. **Simulated speech** has
  **As: speech** (typed text behaves like the microphone, so letters build
  up) and **Conf: low** (pretend the recogniser was unsure).

Settings in `config/alfiebot.json`, section `spelling`:
`confirm_spoken_answers` (`always`, or `when_unsure` to skip the read-back
when every letter was clear), `phonetic_words` (`child` = "B for ball",
`nato` = "B for bravo", `off`) and `finish_after_pause` (seconds; 0 = wait
for "finished").

**What we found about the recogniser (Vosk):** it supports a restricted
word list (used: letter names, "B for ball" words and the commands) and a
confidence score per word (used). It can also give alternative guesses
(`SetMaxAlternatives`), but then it only scores whole sentences, not single
letters, so per-letter scores were the better choice. With a restricted word
list the recogniser sometimes picks a wrong letter with high confidence.
That's why AlfieBot reads every spoken spelling back before marking it by
default, and why the letter test reports "wrong but sure" separately.

## What Stage 4 adds

- **AlfieBot speaks.** On Windows it uses the built-in Windows voices; on
  the Pi it uses espeak-ng. Both are offline. Spelled words are read letter
  by letter with pauses ("B, E, C, ay, U, S, E"). The mouth moves for as long
  as the voice is actually talking, and the robot button cuts it off.
  Choose a voice, speed and volume in `config/alfiebot.json` (`speech`).
- **AlfieBot listens.** Offline speech recognition with Vosk. Nothing is
  recorded or saved and nothing goes over the internet. The speech model
  (about 40 MB) is downloaded once with `python tools/download_speech_model.py`.
- **The microphone only opens while AlfieBot is listening**, never while
  it's idle, thinking or talking, and stays shut for a moment after it
  stops talking, so it can't answer its own voice. Wake it with "Hey
  AlfieBot" typed or the button (a real wake word is Stage 5).
- Two microphone modes: **open** (listens whenever AlfieBot is listening)
  or **hold button** (push-to-talk: only while Space / the robot button is
  held). Switch with the **Mode** button.
- **Clear microphone status** in the panel: a red dot and "ON - listening"
  when the mic is open, "Muted while AlfieBot talks", or why it's off, plus a
  sound level meter and the words being heard.
- **Parent switch:** the mic is off until a parent clicks **Allow mic** in
  Parent settings (saved in the config). **Mic: on/off** switches it off
  for a while without changing the parent setting.
- **Spelling by voice:** while waiting for a spelling answer, the
  recogniser only listens for letter names and tutor commands, which makes
  letters much easier to recognise (improved in version 0.5, above).
- `python tools/check_speech.py` tests the voice and microphone on their
  own (says a sentence, lists microphones, listens for 5 seconds).

The speech model is US English. If it struggles with your accents, a larger
model can be set in `speech.vosk_model`.

## What Stage 3 adds

- **Weekly spelling lists**, saved in `data/spellings/<week>.json` (for
  example `2026-W44.json`). Click **Lists** in the panel to see a week's
  words, flick between weeks with `<` `>`, and type new words (commas or
  spaces between them). Typed words are shown first as green chips to check;
  click one to fix it, then **Save**. Anything that isn't plain letters is
  left out and shown in red. Click a saved word to remove or correct it.
  **Load example list** adds the 10 example words.
- **Adding words by voice** (typed for now): "Add the word because" ->
  "Because. B-E-C-A-U-S-E. Is that correct?" -> "yes" saves it, "no" asks
  you to spell it letter by letter. Say "finished" when done.
- **Learning mode** ("practise"): for each word AlfieBot says it, spells it
  letter by letter and asks you to try. You can say *repeat that*, *spell it
  slower*, *give me a clue* (up to three clues), *next word*, *start again*
  or *stop*. A right answer gets a celebration and moves on; a wrong one gets
  encouragement and another go (after three tries it moves on and marks the
  word for more practice).
- **Test mode**: the words in a random order, said but not spelled (the
  Lists window hides them during a test). Type the answer, or letters like
  "b e c a u s e". Each answer gets supportive feedback with the right
  spelling, then the next word. At the end: your score, which words to
  practise again, and an offer to practise them straight away. *Say it again*
  repeats the word; *I don't know* or *skip* moves on.
- **Spoken answers are double-checked.** Letter names ("bee ee see ...",
  "double s") are understood. If the recogniser was unsure, or it heard a
  whole word instead of letters, AlfieBot asks "I heard B-E-C-A-U-S-E. Is
  that what you meant?" before marking it, so a mishearing is never marked
  wrong. (This is ready for Stage 4's microphone and tested with simulated
  voice input.)
- **Progress** in `data/progress.json`: attempts, right and wrong answers,
  date of practice and each answer for every word, plus each finished
  practice or test. The **Progress** tab shows it, with "practise again" on
  words that were never right or were wrong last time.
- The panel's **Add by voice**, **Practise** and **Test** buttons start each
  activity directly. Everything AlfieBot says in the tutor is in
  `alfiebot/spelling/responses.json`.

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
  grown-up), and "help me with my spellings" (asks add / practise / test).
  Anything else gets a clear "I don't
  know how to do that yet" with a confused face.
- Several replies per intent, never the same one twice in a row. They're in
  `alfiebot/conversation/responses.json`, so you can edit what AlfieBot says.
- The face follows the conversation: excited greeting, thinking pause,
  happy or confused while talking (with a moving mouth), attentive while
  listening.
- The robot button wakes AlfieBot, cuts it off mid-sentence to listen, or
  keeps it listening longer.
- AlfieBot's lines appear in the transcript (and, from Stage 4, are spoken).

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

Not built yet, on purpose: speech output and microphone (Stage 4), wake word and Pi hardware
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
   python tools\download_speech_model.py
   python run_simulator.py
   ```

3. For just the face: `python run_face.py` (windowed) or
   `python run_face.py --fullscreen --demo` (full screen, cycling expressions).

If you used the new **Python install manager** from python.org, it installs
the newest Python (3.15 or later), which pygame doesn't support yet. Run
`py install 3.13` and create the venv with `py -V:3.13 -m venv .venv`.

To run the tests: `pip install -r requirements-dev.txt` then `python -m pytest`.

If `pip install pygame` fails on a brand-new Python version, install
Python 3.12 instead (pygame wheels lag new Python releases), or try
`pip install pygame-ce`, a compatible fork.

### Updating to a new version on Windows

Each version comes as a zip (for example `AlfieBot_software_v0.3.zip`).
Your spelling lists and progress are in the `data` folder, so keep it.

1. Close the simulator.
2. In File Explorer, go to `C:\Users\<you>\AlfieBot`. Rename the `software`
   folder to `software_old` (a backup).
3. Unzip the new zip into `C:\Users\<you>\AlfieBot`, so you get a fresh
   `software` folder next to `software_old`.
4. Copy the `data` folder (if there is one) from `software_old` into the new
   `software` folder.
5. Open PowerShell and run:

   ```powershell
   cd $HOME\AlfieBot\software
   py -V:3.13 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
   .\.venv\Scripts\python.exe -m pytest -q
   .\.venv\Scripts\python.exe tools\download_speech_model.py
   .\.venv\Scripts\python.exe run_simulator.py
   ```

   You can copy the `models` folder from `software_old` instead of
   downloading the speech model again. The download step says so if the
   model is already there.

   The test line should end with "passed" and no failures. Once the new
   version works, you can delete `software_old`.

To just run it again later:

```powershell
cd $HOME\AlfieBot\software
.\.venv\Scripts\python.exe run_simulator.py
```

## Run it on Raspberry Pi OS

For Raspberry Pi OS Bookworm (64-bit, desktop). Open a terminal **on the
Pi's desktop** (not over SSH, because the window needs the screen):

```bash
sudo apt update
sudo apt install -y git python3-venv espeak-ng libportaudio2
git clone https://github.com/JBotch/ALFIE-BOT.git
cd ALFIE-BOT/software
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python tools/download_speech_model.py
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
| Panel or Space | Robot button | Wakes AlfieBot, interrupts it to listen, or keeps it listening. In "hold button" mode, hold it while you talk |
| Panel | Mic: on/off, Mode | Switch the microphone off for now; open mic or hold-to-talk |
| Panel | Allow mic | Parent setting: the microphone can't open until this says yes |
| Panel, T or Enter | Simulated speech | Type what you would say, or click a quick phrase |
| Panel or F11 | Face full screen | Face only; F11 or Esc returns |
| Panel | Lists / Add by voice / Practise / Test | Spelling lists and progress window, or start an activity |
| Panel | Letter test | Letter recognition test and report |
| Panel | As: typing/speech, Conf: high/low | Send simulated speech as typing (marked at once) or as speech (letters build up), sure or unsure |
| Panel | Delete local data | Click twice to delete the `data/` folder (spelling lists and progress) |
| Face-only mode | 1-7, 0, D, Space, Esc | Expressions, follow state, demo cycle, button, quit |

## What to test in version 0.5

1. Simulator: click **Allow mic**, then **Test** (or **Practise**). Spell the
   word letter by letter. Watch the letters appear under the eyes.
2. Say a wrong letter, then "delete". Say "start again". Say "repeat".
3. Say "finished". AlfieBot should read your letters back and only mark the
   word after you say yes.
4. Mumble one letter, or say B and D carelessly. AlfieBot should ask about
   that letter ("B for ball, D for dog or P for pig?").
5. Say "no" at the read-back and fix the spelling.
6. Type an answer instead: it should be marked straight away.
7. Click **Letter test**, type a speaker name, pick **All**, then **Start**.
   Say each letter. Repeat with **Confusing** and **Slow**/**Fast**, and with
   Alfie as the speaker. **Report of all tests** sums them all up
   (or run `python tools/letter_test.py --report`).
8. No microphone? Set **As: speech** under Simulated speech and type letters
   like "bee ee see", "delete", "finished". **Conf: low** makes AlfieBot
   unsure so you can see the questions.

## Stage 4 checks

1. Run `python tools/check_speech.py`. You should hear AlfieBot speak, see
   your microphone listed, and see what you say written out.
2. In the simulator, click **Allow mic**. The status should say the mic
   opens when AlfieBot listens.
3. Type "Hey AlfieBot". AlfieBot speaks the greeting (status "Muted while
   AlfieBot talks"), then the red dot comes on. Say "I'm good", "How are
   you?", "Tell me a joke". Watch the level meter and "Hearing:" line.
4. Check AlfieBot never answers its own voice, even with the speakers loud.
5. Practise and test spellings by voice (see the version 0.5 checks above).
6. Switch **Mode** to "hold button" and talk while holding Space.
7. Press Space while AlfieBot is talking: it should stop mid-word.
8. Try a different voice: on Windows set `"voice": "Hazel"` (or another
   installed voice) in `config/alfiebot.json`.

## Stage 3 checks

1. Open **Lists**, click **Load example list** (or type your own week's
   words), check them and save. Close the window.
2. Wake AlfieBot and say "help me with my spellings", then "practise".
   Try a right answer, a wrong one, *give me a clue*, *spell it slower*,
   *repeat that*, *next word* and *start again*.
3. Click **Test** and do a whole test with a few mistakes. Check the score,
   the practise-again suggestion, and that **Lists** hides the words during
   the test.
4. Open **Progress** and check the attempts, dates and sessions look right.
5. Add a word by voice: "add the word because", then "no", then spell it.
6. **Delete local data** (click twice) should clear lists and progress.
7. Read `spelling/responses.json` with Alfie and change anything that
   doesn't sound right.

## Stage 2 checks

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
  tools/check_speech.py    tests the voice and microphone on their own
  tools/letter_test.py     letter recognition test and report
  tests/                   automated tests (pytest)
  alfiebot/
    main.py                entry point and command-line options
    config.py              loads config/alfiebot.json over built-in defaults
    core/                  robot, state machine, states -> expressions, transcript
    face/                  poses (numbers per expression), engine (animation), renderer (pygame)
    speech/                base.py (interfaces), tts.py (Windows voice, espeak-ng),
                           vosk_recognizer.py (offline mic), text.py (letters for speech),
                           mic_gate.py keeps the mic deaf while AlfieBot talks,
                           letter_test.py (letter recognition test and report)
    conversation/          intents.py (phrase matching), responses.json (what AlfieBot says), engine.py
    spelling/              words.py (letters, spoken letter names), letter_input.py (spoken
                           spelling: letters, commands, unsure letters), lists.py (weekly lists),
                           progress.py, tutor.py (add / learn / test), responses.json
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
- The microphone is off until a parent allows it (**Allow mic**, saved as
  `privacy.microphone_enabled`), it only opens while AlfieBot is listening,
  and its status is always shown in the panel.
- Audio is processed in memory and never saved; there is no code that
  records it. Speech recognition runs on the computer, not online.
- The transcript is kept in memory only. Spelling lists and progress are
  saved as JSON in `data/` on this computer only, and **Delete local data**
  removes them.
