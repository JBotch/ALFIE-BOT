# AlfieBot software

Python software for AlfieBot, the 3D-printed companion robot. The same code
runs as a desktop simulator on a normal computer and, later, on the robot's
Raspberry Pi 5.

**Version 0.8: AI brain skeleton** (V1 Phase 2: the brain, a pretend AI
and the developer controls for it; a real local AI model comes in 0.9).
The V1 plan is in [docs/](docs/): the audit of the existing software, the
architecture and the development plan.

> Tested on Linux with Python 3.13 and pygame 2.6.1 (all automated tests,
> plus headless launches of both apps, and the espeak-ng voice). The speech
> recogniser was tested with stand-in recognition results only, because the
> test machine has no microphone and couldn't download the speech model.
> Version 0.4 also ran on Windows 11 with Python 3.13 and a real microphone.
> The Piper voice engine was tested with a stand-in voice only, because the
> test machine couldn't download Piper voices (version 0.6 has since run
> with the real Piper voice on Windows). The online comparison voice was
> tested with a stand-in service only. Version 0.8's AI is a pretend
> (mock) AI that runs inside the program; no real AI model or online AI
> service is used yet.
> **It has not been run on Raspberry Pi hardware yet.** The Pi-specific code
> (GPIO button) is written but untested.

## What version 0.8 adds: the AI brain skeleton

- **No more letters on the robot's face.** While Alfie spells, the robot's
  screen shows only the eyes. The letters AlfieBot heard (with a `?` after
  unsure ones) are shown in the developer panel under *Spelling homework*
  instead.
- **A brain** (`alfiebot/core/brain.py`) decides who answers. A running
  spelling activity goes to the spelling tutor, and Python marks every
  answer. Anything with a hand-written reply (greetings, jokes, "help me with
  my spellings") gets that reply. Anything else goes to an AI.
- **A pretend AI** for now. It gives a few in-character answers (try "I
  like dinosaurs" or "why is the sky blue"), so the whole path can be tried
  without installing a model. The real local model (Ollama) comes next.
- **AI answers run in the background**, so the eyes keep animating in the
  thinking face. If the AI fails, is too slow (8 s), or sends back something
  broken, AlfieBot uses its hand-written "I didn't understand" reply
  instead.
- **AI output is checked before it is used.** It must say what to speak,
  which face to make, and at most one action from a short allowed list
  (celebrate, open the spelling menu, stop listening, go to sleep).
  Anything else is dropped and logged. AI can never run commands, change
  settings or move hardware.
- **AI brain panel** (button at the top of the developer panel): AI on/off,
  mode (local only, cloud only, automatic), model, the parent cloud switch
  and an adult test session, switches to simulate the internet going down
  or the AI failing, the last routing decision and why, and performance
  statistics labelled with the machine that measured them.
- **Cloud is off by default**, and even when a parent switches it on, a
  child's words are never sent to it until privacy checks exist (Phase 4).
  Only an adult test session can use it. The cloud is also pretend for now:
  nothing leaves the computer.
- **Speaker: on/off** at the top of the panel mutes AlfieBot (replies still
  appear in the transcript and the mouth still moves).
- **Reset all data** (was *Delete local data*) also clears the transcript
  and AI statistics.
- New settings section `ai` in `config/alfiebot.json`.

## What version 0.7 added: Bubbly Bot

- **A new voice personality, Bubbly Bot**: a cheerful, friendly cartoon
  robot. Choose **Classic** (the v0.6 voice) or **Bubbly Bot** in the Voice
  panel to compare them; the choice is saved. Bubbly Bot is the default.
- **The personality isn't just pitch.** Bubbly Bot speaks a little faster,
  with shorter gaps between sentences and more variation in rhythm (Piper's
  expressiveness), a gentle pitch lift (+2.5 semitones: brighter, not
  squeaky), sometimes starts celebrations with "Woohoo!", "Yay!" or
  "Beep boop, yes!", and plays little sound effects.
- **Bubbly Bot's profiles**, chosen automatically: **Bubbly Conversation**
  (chatting), **Bubbly Excited** (celebrations), **Clear Spelling Teacher**
  (spelling: noticeably slower than chatting, steadier, with long gaps
  between letters, which are always said one at a time) and **Bubbly
  Sleepy**. All are tunable in `voice_profiles` in `config/alfiebot.json`.
- **Speed, pitch and volume** settings in the Voice panel (and `speed`,
  `pitch`, `volume` in `speech`). Pitch is in semitones, added to the
  profile's own pitch. It works with Piper (the voice is made slightly
  slower, then played back faster, so it's higher but not sped up),
  espeak-ng, and Windows voices that support it.
- **Sound effects**: a rising "boot up" chirp when AlfieBot wakes, a soft
  blip when it starts listening, and a sparkly arpeggio when celebrating.
  They're made by the code (no sound files), short and quiet. On for Bubbly
  Bot, off for Classic; switch them in the Voice panel or in `sounds`.
- **Voice test screen**: Voice panel, **Try it** tab. Example greetings,
  jokes and spelling (a new word, letters spelled out, "B for ball, D for
  dog or P for pig?", praise, goodnight), played with Classic, Bubbly Bot,
  the online voice, or **Compare both** (Classic then Bubbly Bot).
- **Optional online voice, for comparison only.** Off unless a parent turns
  on **Parent: online voice comparison** in the Voice panel. It uses
  Microsoft's free neural voices through `edge-tts`
  (`pip install -r requirements-cloud.txt`); the default is
  `en-GB-MaisieNeural`, a young British girl's voice. Only the words
  AlfieBot says are sent, never anything Alfie says or any microphone
  audio. It's only used in **Try it**: AlfieBot itself always speaks
  offline. It needs the internet and the free service could change or stop.

**Which voice model?** Piper has no British child's voice, so Bubbly Bot is
built on `en_GB-cori-medium` (bright, clear, friendly, and already
installed), with the livelier pacing, expressiveness and gentle pitch lift
on top. It runs well on the Raspberry Pi 5. Worth comparing in the Voice
panel: `en_GB-jenny_dioco-medium` (warm southern English) and
`en_GB-southern_english_female-low` (lighter, lower quality). Download them
with `python tools/download_voice.py <name>`. The online Maisie voice shows
what a genuinely young voice sounds like next to them.

New settings: `speech.personality` (`bubbly` or `classic`), `speech.pitch`,
`speech.allow_cloud_voices`, `speech.cloud_voice`, and a `sounds` section.

## What version 0.6 added: a better voice

- **Piper voices** (offline, natural-sounding, British English) are now
  the preferred voice. `pip install -r requirements.txt` installs Piper, and
  `python tools/download_voice.py` downloads the default voice,
  `en_GB-cori-medium` (about 60 MB). `--list` shows other British voices
  (Alan, Jenny, Alba, a northern English male voice...). If Piper or the
  voice is missing, AlfieBot uses the Windows voice (or espeak-ng on the Pi)
  as before and says why in the panel. Adding another engine later means
  writing one class; the conversation and tutor code don't change.
- **Four voice profiles**, chosen automatically for each reply:
  **normal** (friendly), **excited** (celebrations: a bit quicker),
  **teacher** (spelling: slower, longer gaps between letters) and **sleepy**
  (going to sleep: slow and quiet). The offline voices can't really sound
  happy or sleepy, so a profile changes only what they can honestly change:
  speed, volume, pauses between sentences, words and letters, pitch (espeak-ng
  only) and, for Piper, a little more or less variation in rhythm. The
  feeling comes from AlfieBot's wording. Tune them in `voice_profiles` in
  `config/alfiebot.json`.
- **Letters are always said one at a time**, never run together into a
  word, with the profile's gap between them. `tts.speak_letters("because",
  profile, repeat)` does this directly; spelled words in AlfieBot's replies
  ("B-E-C-A-U-S-E") are spoken the same way.
- **Voice panel** (button **Voice** next to Microphone): the engine and
  voice in use, a list of voices on this computer (Piper, Windows or
  espeak-ng) to switch between, the voice profile (Auto or one fixed),
  speaking speed, and **Test voice** / **Test letters** buttons.
- `python tools/check_speech.py --no-mic --profiles` plays all four profiles.

New settings in `speech`: `tts_engine` (`auto` = Piper first),
`piper_voice`, `speed` (1.0 normal), `voice_profile` (`auto` or a name),
`speaker_device`.

## What version 0.5 added: spelling recognition

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
   python tools\download_voice.py
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
   .\.venv\Scripts\python.exe tools\download_voice.py
   .\.venv\Scripts\python.exe run_simulator.py
   ```

   You can copy the `models` folder from `software_old` instead of
   downloading the speech model and voice again. The download steps say so
   if they are already there.

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
python tools/download_voice.py
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
| Panel | Voice | Choose the voice, voice profile and speed; test them |
| Panel | As: typing/speech, Conf: high/low | Send simulated speech as typing (marked at once) or as speech (letters build up), sure or unsure |
| Panel | AI brain | AI mode, model, cloud switch, simulated failures, routing and performance |
| Panel | Speaker: on/off | Mute AlfieBot's voice; replies still show in the transcript |
| Panel | Reset all data | Click twice to delete the `data/` folder (spelling lists and progress) and clear the transcript and AI statistics |
| Face-only mode | 1-7, 0, D, Space, Esc | Expressions, follow state, demo cycle, button, quit |

## What to test in version 0.8

1. Start the simulator, wake AlfieBot and type "I like dinosaurs". The face
   should think, then answer with a pretend-AI reply. "Tell me a joke"
   should still get a hand-written joke.
2. Click **AI brain**. The last request shows which AI answered and why.
   Set **Think time** to 2 s and type something new: the eyes keep moving
   in the thinking face while you wait.
3. Set **Local AI** to **Too slow**: after 8 s AlfieBot gives its
   "didn't understand" reply instead of hanging. Try **Error** and **Bad
   output** too, then set it back to **Working**.
4. Set **Mode** to **Cloud only**. With the cloud off, the route says so
   and the local AI answers. Turn the cloud **On (parent)**: it still isn't
   used for normal input. Turn on **Adult test session**: now the pretend
   cloud answers. Set **Internet** to **Offline**: the local AI takes over.
5. Start a spelling **Test** and spell some letters by voice (or with
   **As: speech**). The robot's face shows no letters; the panel does.
6. Click **Speaker: off** and talk to AlfieBot: no sound, but the replies
   appear in the transcript.

## What to test in version 0.7

1. `python tools/check_speech.py --no-mic --profiles`: you should hear the
   Classic profiles, then the four Bubbly Bot profiles, then "because"
   spelled with the Classic teacher and the Clear Spelling Teacher.
2. In the simulator click **Voice**, then **Try it**. Click **Compare
   both**, then each example. Does Bubbly Bot sound cheerful, clear and a
   little younger, without being squeaky? Try **Letters: friend**: the
   letters should be slow and clear.
3. On **Settings**, try Pitch +/-, Speed and Volume, and the sound effect
   buttons. If Bubbly Bot sounds too high, take the pitch down a step or two.
4. Talk to AlfieBot as Bubbly Bot: a chirp when it wakes, a blip when it
   listens, sparkles and sometimes "Woohoo!" when celebrating. Do a spelling
   practice: words and letters should use the Clear Spelling Teacher.
5. Switch to **Classic**: it should sound and behave exactly as v0.6.
6. Optional: `pip install -r requirements-cloud.txt`, turn on **Parent:
   online voice comparison**, and play examples with **Online voice**.
7. Try other Piper voices with Bubbly Bot (see "Which voice model?").

## What to test in version 0.6

1. Run `python tools/download_voice.py`, then
   `python tools/check_speech.py --no-mic --profiles`. You should hear the
   Piper voice ("Speech output: Piper"), then the four profiles and
   "because" spelled letter by letter, twice.
2. In the simulator click **Voice**. Check it says "Speaking with: Piper".
   Try **Test voice** and **Test letters** with each profile and speed.
   Switch to a Windows voice and back.
3. Do a practice and a test by voice: AlfieBot should use the teacher
   voice for words and letters, the excited voice for "Brilliant!", and the
   sleepy voice when you say goodbye.
4. To try other British voices: `python tools/download_voice.py --list`,
   then for example `python tools/download_voice.py en_GB-alan-medium`.

## What to test in version 0.5

1. Simulator: click **Allow mic**, then **Test** (or **Practise**). Spell the
   word letter by letter. Watch the letters appear in the developer panel
   (since 0.8 they are no longer shown under the eyes).
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
  tools/download_voice.py  downloads a Piper voice (British English)
  requirements-cloud.txt   optional: online comparison voice (edge-tts)
  tests/                   automated tests (pytest)
  alfiebot/
    main.py                entry point and command-line options
    config.py              loads config/alfiebot.json over built-in defaults
    core/                  robot, brain (who answers), actions (checks AI output),
                           events, state machine, states -> expressions, transcript
    face/                  poses (numbers per expression), engine (animation), renderer (pygame)
    speech/                base.py (interfaces), tts.py (engine choice and fallback,
                           Windows voice, espeak-ng), piper_tts.py (Piper voices),
                           voice_profiles.py (profiles; Classic and Bubbly Bot personalities),
                           sounds.py (wake, listen, celebrate effects),
                           cloud_tts.py (optional online comparison voice),
                           vosk_recognizer.py (offline mic), text.py (letters for speech),
                           mic_gate.py keeps the mic deaf while AlfieBot talks,
                           letter_test.py (letter recognition test and report)
    conversation/          intents.py (phrase matching), responses.json (what AlfieBot says), engine.py
    ai/                    provider_base.py (provider interface), mock_provider.py (pretend AI),
                           router.py (which provider answers, and why), connectivity.py,
                           performance.py (latency, tokens, errors per provider and machine)
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

- Everything runs offline. There is no internet chatbot. The AI in
  version 0.8 is a pretend AI inside the program; the cloud AI switch is
  off by default, and even when it's on, a child's words are never sent
  (only an adult test session can use it).
- The microphone is off until a parent allows it (**Allow mic**, saved as
  `privacy.microphone_enabled`), it only opens while AlfieBot is listening,
  and its status is always shown in the panel.
- Audio is processed in memory and never saved; there is no code that
  records it. Speech recognition and AlfieBot's voice (Piper, Windows or
  espeak-ng) run on the computer, not online. The only downloads are the
  speech model and voices, once, when you run the download tools.
- The transcript is kept in memory only. Spelling lists and progress are
  saved as JSON in `data/` on this computer only, and **Reset all data**
  removes them.
