"""Voice settings in the simulator: engine and voice, voice profile, speed,
and buttons to hear them. Choices are saved in config/alfiebot.json."""

import logging
import sys
import threading

import pygame

from alfiebot.config import save_setting
from alfiebot.speech.piper_tts import installed_voices
from alfiebot.speech.tts import create_tts
from alfiebot.speech.voice_profiles import PROFILE_NAMES
from alfiebot.ui import widgets as w

log = logging.getLogger(__name__)

TEST_SENTENCE = "Hello! I'm AlfieBot. Shall we practise your spellings? Because is spelled B-E-C-A-U-S-E."
TEST_WORD = "because"
SPEEDS = (0.6, 1.6)


class VoicePanel:
    def __init__(self, robot, config, rect):
        self.robot = robot
        self.config = config
        self.rect = pygame.Rect(rect)
        self.open = False
        self.choices = []  # (label, engine, voice)
        self.message = ""
        self._hits = []
        self._loading = False

    @property
    def tts(self):
        return self.robot.platform.tts

    def toggle(self):
        self.open = not self.open
        if self.open and not self._loading:
            self._loading = True
            threading.Thread(target=self._find_voices, daemon=True).start()

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

                native = [v for v in EspeakTTS().available_voices() if v.startswith("en")][:8]
        except Exception as exc:
            log.info("Couldn't list the computer's voices: %s", exc)
        engine = "windows" if sys.platform == "win32" else "espeak"
        label = "Windows" if engine == "windows" else "espeak"
        choices += [(f"{label}: {v}", engine, v) for v in native]
        self.choices = choices
        self._loading = False

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
        new.speed = old.speed if hasattr(old, "speed") else 1.0
        self.robot.platform.tts = new
        save_setting(self.config, "speech", "tts_engine", engine)
        save_setting(self.config, "speech", "piper_voice" if engine == "piper" else "voice", voice)
        self.message = f"Now using {new.name}" + (f" ({new.voice_name})" if new.voice_name else "")
        if new.fallback_reason:
            self.message += f". {new.fallback_reason}"
        log.info(self.message)

    def _set_profile(self, name):
        self.robot.voice_profile = name
        save_setting(self.config, "speech", "voice_profile", name)

    def _change_speed(self, step):
        speed = round(min(SPEEDS[1], max(SPEEDS[0], getattr(self.tts, "speed", 1.0) + step)), 2)
        self.tts.speed = speed
        save_setting(self.config, "speech", "speed", speed)

    def _test_profile(self):
        return "normal" if self.robot.voice_profile == "auto" else self.robot.voice_profile

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
            self.open = False
            return True
        return False

    # ---- drawing -------------------------------------------------------------
    def _button(self, s, rect, label, action, mouse, selected=False, size=16):
        rect = pygame.Rect(rect)
        colour = w.WIDGET_ACTIVE if selected else (w.WIDGET_HOVER if rect.collidepoint(mouse) else w.WIDGET)
        pygame.draw.rect(s, colour, rect, border_radius=6)
        img = w.font(size).render(label, True, w.TEXT)
        s.blit(img, img.get_rect(center=rect.center))
        self._hits.append((rect, action))

    def draw(self, s, mouse, dt):
        if not self.open:
            return
        self._hits = []
        r = self.rect
        pygame.draw.rect(s, w.PANEL, r, border_radius=10)
        pygame.draw.rect(s, w.ACCENT, r, 1, border_radius=10)
        x, right, y = r.x + 16, r.right - 16, r.y + 14
        w.draw_text(s, "Voice", (x, y), w.TEXT, 26)
        self._button(s, (right - 80, y - 2, 80, 28), "Close", self.toggle, mouse)
        y += 38
        tts = self.tts
        now = f"Speaking with: {tts.name}" + (f" ({tts.voice_name})" if tts.voice_name else "")
        w.draw_text(s, now, (x, y), w.TEXT, 19, max_width=right - x)
        y += 24
        if tts.fallback_reason:
            for line in w.wrap_text("Not used: " + tts.fallback_reason, right - x, 16)[:2]:
                w.draw_text(s, line, (x, y), w.WARN, 16)
                y += 19
        y += 6

        w.draw_text(s, "Voices on this computer", (x, y), w.ACCENT, 19)
        y += 26
        if self._loading:
            w.draw_text(s, "Looking for voices...", (x, y), w.TEXT_DIM, 17)
            y += 30
        elif not self.choices:
            w.draw_text(s, "None found.", (x, y), w.TEXT_DIM, 17)
            y += 30
        else:
            col_w = (right - x - 8) // 2
            current = (tts.name, tts.voice_name)
            for i, (label, engine, voice) in enumerate(self.choices[:12]):
                cx = x + (i % 2) * (col_w + 8)
                cy = y + (i // 2) * 32
                selected = current[1] == voice and (engine == "piper") == (current[0] == "Piper")
                self._button(s, (cx, cy, col_w, 28), label, (lambda e=engine, v=voice: self._choose(e, v)),
                             mouse, selected, size=15)
            y += ((min(len(self.choices), 12) + 1) // 2) * 32 + 4
        if not any(engine == "piper" for _, engine, _ in self.choices) and not self._loading:
            w.draw_text(s, "For a natural British voice: pip install piper-tts, then "
                           "python tools/download_voice.py", (x, y), w.TEXT_DIM, 16, max_width=right - x)
            y += 24

        y += 4
        w.draw_text(s, "Voice profile", (x, y), w.ACCENT, 19)
        y += 26
        names = ("auto",) + PROFILE_NAMES
        bw = (right - x - 6 * (len(names) - 1)) // len(names)
        for i, name in enumerate(names):
            self._button(s, (x + i * (bw + 6), y, bw, 28), name.title(),
                         (lambda n=name: self._set_profile(n)), mouse, self.robot.voice_profile == name)
        y += 36
        profiles = getattr(tts, "profiles", {})
        auto = self.robot.voice_profile == "auto"
        shown = PROFILE_NAMES if auto else (self.robot.voice_profile,)
        for name in shown:
            p = profiles.get(name)
            if p is None:
                continue
            last = " (last used)" if auto and name == self.robot.last_profile else ""
            w.draw_text(s, f"{name.title()}{last}: speed {p.rate:g}, volume {p.volume:g}, "
                           f"gaps {p.sentence_pause:g}s / letters {p.letter_pause:g}s. {p.style}",
                        (x, y), w.TEXT_DIM, 15, max_width=right - x)
            y += 19
        w.draw_text(s, "Profiles change speed, volume and pauses (pitch too with espeak). "
                       "They don't add real emotion.", (x, y + 2), w.TEXT_DIM, 15, max_width=right - x)
        y += 30

        w.draw_text(s, "Speed", (x, y + 5), w.ACCENT, 19)
        speed = getattr(tts, "speed", 1.0)
        self._button(s, (x + 70, y, 36, 28), "-", lambda: self._change_speed(-0.1), mouse, size=20)
        w.draw_text(s, f"{speed:.1f}x", (x + 116, y + 5), w.TEXT, 19)
        self._button(s, (x + 166, y, 36, 28), "+", lambda: self._change_speed(0.1), mouse, size=20)
        y += 40
        profile = self._test_profile()
        self._button(s, (x, y, 190, 32), "Test voice",
                     lambda: tts.speak(TEST_SENTENCE, profile), mouse, size=18)
        self._button(s, (x + 198, y, 220, 32), f"Test letters: {TEST_WORD}",
                     lambda: tts.speak_letters(TEST_WORD, profile if profile != "normal" else "teacher"),
                     mouse, size=18)
        self._button(s, (x + 426, y, 90, 32), "Stop", tts.stop, mouse, size=18)
        y += 42
        if self.message:
            for line in w.wrap_text(self.message, right - x, 16)[:3]:
                w.draw_text(s, line, (x, y), w.TEXT_DIM, 16)
                y += 19
