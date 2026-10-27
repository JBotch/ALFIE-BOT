"""Voice settings and the voice test screen, in the simulator.

Settings tab: engine and voice, personality (Classic or Bubbly Bot),
voice profile, speed, pitch, volume, sound effects, and the parent switch
for comparing with an online voice. Choices are saved in config/alfiebot.json.

Try it tab: example greetings, jokes and spelling, played with Classic,
Bubbly Bot or (if allowed) the online voice, one after the other to compare.
"""

import logging
import sys
import threading

import pygame

from alfiebot.config import save_setting
from alfiebot.speech.piper_tts import installed_voices
from alfiebot.speech.tts import _build, create_tts
from alfiebot.speech.voice_profiles import PERSONALITIES, get_personality
from alfiebot.ui import widgets as w

log = logging.getLogger(__name__)

SPEEDS = (0.6, 1.6)
PITCHES = (-4.0, 4.0)
# (button label, what AlfieBot says, role, sound effect first). "letters:word" spells it out.
EXAMPLES = {
    "Greetings": [
        ("Hello!", "Hello! I'm AlfieBot. It's so nice to see you!", "normal", "wake"),
        ("Good morning", "Good morning, superstar! Ready for a brilliant day?", "normal", "wake"),
        ("All charged up", "Hey there! Beep boop, I'm all charged up and ready to play!", "excited", "wake"),
    ],
    "Jokes": [
        ("Robot holiday", "Why did the robot go on holiday? Because it needed to recharge its batteries!",
         "normal", None),
        ("Dino-snore", "What do you call a sleeping dinosaur? A dino-snore!", "normal", None),
        ("Maths book", "Why was the maths book sad? Because it had too many problems!", "normal", None),
    ],
    "Spelling": [
        ("New word", "Word one is because. Because is spelled B-E-C-A-U-S-E. Now you try! Spell because.",
         "teacher", "listen"),
        ("Letters: friend", "letters:friend", "teacher", None),
        ("Which letter?", "Just checking letter 2. Was it B for ball, D for dog or P for pig?", "teacher", None),
        ("Well done!", "Brilliant! You spelled friend perfectly!", "excited", "celebrate"),
        ("Goodnight", "That was fun! Time for a little robot nap. Night night!", "sleepy", None),
    ],
}


class VoicePanel:
    def __init__(self, robot, config, rect):
        self.robot = robot
        self.config = config
        self.rect = pygame.Rect(rect)
        self.open = False
        self.tab = "settings"
        self.choices = []  # (label, engine, voice)
        self.message = ""
        self.play_with = robot.personality
        self.compare = False
        self.queue = []  # things to play in turn: ("say"/"sound"/"wait", ...)
        self._wait = 0.0
        self._busy_tts = None
        self._cloud = None
        self._hits = []
        self._loading = False

    @property
    def tts(self):
        return self.robot.platform.tts

    @property
    def cloud_allowed(self) -> bool:
        return bool(self.config["speech"].get("allow_cloud_voices"))

    def toggle(self):
        self.open = not self.open
        if self.open and not self._loading:
            self._loading = True
            threading.Thread(target=self._find_voices, daemon=True).start()
        if not self.open:
            self.stop()

    def _find_voices(self):
        """List Piper voices and the computer's own voices (in the background:
        asking Windows for its voices takes a second)."""
        choices = [(f"Piper: {v}", "piper", v) for v in installed_voices(self.config)]
        native = []
        try:
            if self.tts.name in ("Windows voice", "espeak-ng"):
                native = self.tts.available_voices()
            elif sys.platform == "win32":
                from alfiebot.speech.tts import WindowsTTS

                probe = WindowsTTS()
                native = probe.available_voices()
                probe.close()
            else:
                from alfiebot.speech.tts import EspeakTTS

                native = [v for v in EspeakTTS().available_voices() if v.startswith("en")][:6]
        except Exception as exc:
            log.info("Couldn't list the computer's voices: %s", exc)
        engine = "windows" if sys.platform == "win32" else "espeak"
        label = "Windows" if engine == "windows" else "espeak"
        choices += [(f"{label}: {v}", engine, v) for v in native]
        self.choices = choices
        self._loading = False

    # ---- settings ----------------------------------------------------------
    def _choose(self, engine, voice):
        speech = self.config["speech"]
        speech["tts_engine"] = engine
        if engine == "piper":
            speech["piper_voice"] = voice
        else:
            speech["voice"] = voice
        old = self.tts
        old.stop()
        if hasattr(old, "close"):
            old.close()
        new = create_tts(self.config)
        for attr in ("speed", "pitch_offset", "volume"):
            if hasattr(old, attr):
                setattr(new, attr, getattr(old, attr))
        self.robot.platform.tts = new
        save_setting(self.config, "speech", "tts_engine", engine)
        save_setting(self.config, "speech", "piper_voice" if engine == "piper" else "voice", voice)
        self.message = f"Now using {new.name}" + (f" ({new.voice_name})" if new.voice_name else "")
        if new.fallback_reason:
            self.message += f". {new.fallback_reason}"
        log.info(self.message)

    def _set_personality(self, name):
        self.robot.personality = name
        self.robot.voice_profile = "auto"
        self.play_with = name
        save_setting(self.config, "speech", "personality", name)
        save_setting(self.config, "speech", "voice_profile", "auto")

    def _set_profile(self, name):
        self.robot.voice_profile = name
        save_setting(self.config, "speech", "voice_profile", name)

    def _adjust(self, attr, setting, step, low, high, digits=2):
        value = round(min(high, max(low, getattr(self.tts, attr, 0) + step)), digits)
        setattr(self.tts, attr, value)
        if self._cloud is not None:
            setattr(self._cloud, attr, value)
        save_setting(self.config, "speech", setting, value)

    def _toggle_sounds(self):
        key = "bubbly" if self.robot.personality == "bubbly" else "classic"
        on = not self.robot.sound_effects_on
        save_setting(self.config, "sounds", key, on)

    def _toggle_cloud(self):
        allowed = not self.cloud_allowed
        save_setting(self.config, "speech", "allow_cloud_voices", allowed)
        if not allowed:
            self._cloud = None
            if self.play_with == "cloud":
                self.play_with = self.robot.personality
        log.info("Parent setting: online voice comparison %s", "allowed" if allowed else "off")

    # ---- playing examples ----------------------------------------------------
    def _engine_for(self, who):
        if who != "cloud":
            return self.tts
        if self._cloud is None:
            try:
                self._cloud = _build("cloud", self.config)
                self._cloud.speed = getattr(self.tts, "speed", 1.0)
                self._cloud.pitch_offset = getattr(self.tts, "pitch_offset", 0.0)
            except Exception as exc:
                self.message = f"Online voice unavailable: {exc}"
                log.warning(self.message)
                return None
        return self._cloud

    def play_example(self, text, role, sound):
        self.stop()
        who_list = ["classic", "bubbly"] if self.compare else [self.play_with]
        for i, who in enumerate(who_list):
            if i:
                self.queue.append(("wait", 0.8))
            # The online voice gets Bubbly Bot's pacing, so the comparison is about the voice itself.
            personality = get_personality("bubbly" if who == "cloud" else who)
            if sound and (who != "classic" or self.robot.config["sounds"].get("classic")):
                self.queue += [("sound", sound), ("wait", 0.45)]
            self.queue.append(("say", who, text, personality.roles.get(role, role)))

    def play_sound(self, name):
        self.robot.platform.sounds.play(name)

    def stop(self):
        self.queue.clear()
        self._wait = 0.0
        for engine in (self.tts, self._cloud):
            if engine is not None:
                engine.stop()

    def update(self, dt):
        if self._wait > 0:
            self._wait -= dt
            return
        if self._busy_tts is not None and self._busy_tts.speaking:
            return
        self._busy_tts = None
        if not self.queue:
            return
        item = self.queue.pop(0)
        if item[0] == "wait":
            self._wait = item[1]
        elif item[0] == "sound":
            self.play_sound(item[1])
        else:
            _, who, text, profile = item
            engine = self._engine_for(who)
            if engine is None:
                return
            if text.startswith("letters:"):
                engine.speak_letters(text[8:], profile)
            else:
                engine.speak(text, profile)
            self._busy_tts = engine
            label = "Online voice" if who == "cloud" else get_personality(who).label
            self.message = f"Playing: {label}, profile {profile}"

    # ---- events --------------------------------------------------------------
    def handle(self, event) -> bool:
        if not self.open:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, action in self._hits:
                if rect.collidepoint(event.pos):
                    action()
                    return True
            return self.rect.collidepoint(event.pos)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.toggle()
            return True
        return False

    # ---- drawing -------------------------------------------------------------
    def _button(self, s, rect, label, action, mouse, selected=False, size=16, enabled=True):
        rect = pygame.Rect(rect)
        if not enabled:
            colour = w.WIDGET_DISABLED
        else:
            colour = w.WIDGET_ACTIVE if selected else (w.WIDGET_HOVER if rect.collidepoint(mouse) else w.WIDGET)
        pygame.draw.rect(s, colour, rect, border_radius=6)
        img = w.font(size).render(label, True, w.TEXT if enabled else w.TEXT_DIM)
        s.blit(img, img.get_rect(center=rect.center))
        if enabled:
            self._hits.append((rect, action))

    def _stepper(self, s, x, y, title, value, minus, plus, mouse):
        w.draw_text(s, title, (x, y + 5), w.ACCENT, 18)
        self._button(s, (x + 62, y, 30, 26), "-", minus, mouse, size=20)
        w.draw_text(s, value, (x + 98, y + 5), w.TEXT, 18)
        self._button(s, (x + 158, y, 30, 26), "+", plus, mouse, size=20)

    def draw(self, s, mouse, dt):
        if not self.open:
            return
        self._hits = []
        r = self.rect
        pygame.draw.rect(s, w.PANEL, r, border_radius=10)
        pygame.draw.rect(s, w.ACCENT, r, 1, border_radius=10)
        x, right, y = r.x + 16, r.right - 16, r.y + 14
        w.draw_text(s, "Voice", (x, y), w.TEXT, 26)
        self._button(s, (x + 100, y - 2, 100, 28), "Settings", lambda: setattr(self, "tab", "settings"),
                     mouse, self.tab == "settings")
        self._button(s, (x + 206, y - 2, 100, 28), "Try it", lambda: setattr(self, "tab", "try"),
                     mouse, self.tab == "try")
        self._button(s, (right - 80, y - 2, 80, 28), "Close", self.toggle, mouse)
        y += 38
        tts = self.tts
        now = f"Speaking with: {tts.name}" + (f" ({tts.voice_name})" if tts.voice_name else "")
        now += f".  Personality: {get_personality(self.robot.personality).label}"
        w.draw_text(s, now, (x, y), w.TEXT, 18, max_width=right - x)
        y += 22
        if tts.fallback_reason:
            w.draw_text(s, "Not used: " + tts.fallback_reason, (x, y), w.WARN, 15, max_width=right - x)
            y += 19
        y += 4
        if self.tab == "settings":
            self._draw_settings(s, mouse, x, right, y)
        else:
            self._draw_try(s, mouse, x, right, y)
        if self.message:
            w.draw_text(s, self.message, (x, r.bottom - 26), w.TEXT_DIM, 16, max_width=right - x)

    def _draw_settings(self, s, mouse, x, right, y):
        tts = self.tts
        w.draw_text(s, "Personality", (x, y), w.ACCENT, 19)
        for i, p in enumerate(PERSONALITIES.values()):
            self._button(s, (x + 120 + i * 136, y - 3, 130, 26), p.label,
                         (lambda n=p.name: self._set_personality(n)), mouse, self.robot.personality == p.name)
        y += 28
        personality = get_personality(self.robot.personality)
        w.draw_text(s, personality.about, (x, y), w.TEXT_DIM, 15, max_width=right - x)
        y += 22

        w.draw_text(s, "Profile", (x, y + 4), w.ACCENT, 19)
        options = [("auto", "Auto")] + [(name, tts.profiles[name].label or name)
                                        for name in personality.roles.values() if name in tts.profiles]
        bx = x + 80
        for name, label in options:
            width = w.font(15).size(label)[0] + 18
            self._button(s, (bx, y, width, 26), label, (lambda n=name: self._set_profile(n)), mouse,
                         self.robot.voice_profile == name, size=15)
            bx += width + 5
        y += 30
        shown = personality.roles.values() if self.robot.voice_profile == "auto" else (self.robot.voice_profile,)
        for name in shown:
            p = tts.profiles.get(name)
            if p is None:
                continue
            last = " (last used)" if name == self.robot.last_profile else ""
            w.draw_text(s, f"{p.label or name}{last}: speed {p.rate:g}, pitch {p.pitch:+g}, volume {p.volume:g}, "
                           f"letter gaps {p.letter_pause:g}s. {p.style}", (x, y), w.TEXT_DIM, 14,
                        max_width=right - x)
            y += 17
        y += 8

        self._stepper(s, x, y, "Speed", f"{getattr(tts, 'speed', 1.0):.1f}x",
                      lambda: self._adjust("speed", "speed", -0.1, *SPEEDS),
                      lambda: self._adjust("speed", "speed", 0.1, *SPEEDS), mouse)
        self._stepper(s, x + 210, y, "Pitch", f"{getattr(tts, 'pitch_offset', 0.0):+.1f}",
                      lambda: self._adjust("pitch_offset", "pitch", -0.5, *PITCHES, digits=1),
                      lambda: self._adjust("pitch_offset", "pitch", 0.5, *PITCHES, digits=1), mouse)
        self._stepper(s, x + 420, y, "Volume", f"{int(getattr(tts, 'volume', 90))}",
                      lambda: self._adjust("volume", "volume", -10, 10, 100, 0),
                      lambda: self._adjust("volume", "volume", 10, 10, 100, 0), mouse)
        y += 32
        w.draw_text(s, "Pitch is in semitones on top of the profile (Piper and espeak; Windows voices "
                       "only if they support it).", (x, y), w.TEXT_DIM, 14, max_width=right - x)
        y += 22
        on = self.robot.sound_effects_on
        self._button(s, (x, y, 230, 26), f"Sound effects: {'on' if on else 'off'}", self._toggle_sounds,
                     mouse, on, size=15)
        for i, name in enumerate(("wake", "listen", "celebrate")):
            self._button(s, (x + 240 + i * 92, y, 86, 26), name.title(), (lambda n=name: self.play_sound(n)),
                         mouse, size=15)
        y += 34

        w.draw_text(s, "Voices on this computer", (x, y), w.ACCENT, 19)
        y += 24
        if self._loading:
            w.draw_text(s, "Looking for voices...", (x, y), w.TEXT_DIM, 16)
            y += 26
        else:
            col_w = (right - x - 8) // 2
            current = (tts.name, tts.voice_name)
            for i, (label, engine, voice) in enumerate(self.choices[:8]):
                cx = x + (i % 2) * (col_w + 8)
                cy = y + (i // 2) * 30
                selected = current[1] == voice and (engine == "piper") == (current[0] == "Piper")
                self._button(s, (cx, cy, col_w, 26), label, (lambda e=engine, v=voice: self._choose(e, v)),
                             mouse, selected, size=15)
            y += ((min(len(self.choices), 8) + 1) // 2) * 30 + 2
        w.draw_text(s, "More British voices: python tools/download_voice.py --list", (x, y), w.TEXT_DIM, 14)
        y += 24

        allowed = self.cloud_allowed
        self._button(s, (x, y, 300, 26), f"Parent: online voice comparison {'on' if allowed else 'off'}",
                     self._toggle_cloud, mouse, allowed, size=15)
        y += 30
        w.draw_text(s, "Online voices send AlfieBot's words (never Alfie's) to Microsoft. Only used in "
                       "Try it. Needs: pip install edge-tts", (x, y), w.TEXT_DIM, 14, max_width=right - x)

    def _draw_try(self, s, mouse, x, right, y):
        w.draw_text(s, "Play with", (x, y + 4), w.ACCENT, 19)
        options = [("classic", "Classic"), ("bubbly", "Bubbly Bot"), ("cloud", "Online voice")]
        for i, (name, label) in enumerate(options):
            enabled = name != "cloud" or self.cloud_allowed
            self._button(s, (x + 100 + i * 126, y, 120, 26), label,
                         (lambda n=name: setattr(self, "play_with", n)), mouse,
                         self.play_with == name and not self.compare, size=15, enabled=enabled)
        self._button(s, (x + 480, y, 150, 26), "Compare both", lambda: setattr(self, "compare", not self.compare),
                     mouse, self.compare, size=15)
        y += 32
        hint = ("Each example plays as Classic, then Bubbly Bot." if self.compare
                else "Click an example to hear it.")
        if not self.cloud_allowed:
            hint += " The online voice needs the parent switch in Settings."
        w.draw_text(s, hint, (x, y), w.TEXT_DIM, 15, max_width=right - x)
        y += 26
        for group, examples in EXAMPLES.items():
            w.draw_text(s, group, (x, y), w.ACCENT, 19)
            y += 24
            bx, by = x, y
            for label, text, role, sound in examples:
                width = w.font(16).size(label)[0] + 26
                if bx + width > right:
                    bx, by = x, by + 32
                self._button(s, (bx, by, width, 28), label,
                             (lambda t=text, r=role, so=sound: self.play_example(t, r, so)), mouse)
                bx += width + 6
            y = by + 34
        y += 4
        self._button(s, (x, y, 100, 30), "Stop", self.stop, mouse, size=17)
        w.draw_text(s, "Examples: greetings use the normal voice, spelling the teacher voice, praise the "
                       "excited voice.", (x + 110, y + 8), w.TEXT_DIM, 14, max_width=right - x - 110)
