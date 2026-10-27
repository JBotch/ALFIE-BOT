"""The AI brain panel, in the simulator (developer only, never on the robot).

Mode and model, the parent cloud switch and adult test session, switches
that simulate an internet or AI failure, the last routing decision with its
reasons, and performance statistics per provider, model and machine.
"""

import logging

import pygame

from alfiebot.ai.mock_provider import FAILURES
from alfiebot.ai.router import MODE_LABELS, MODES
from alfiebot.config import save_setting
from alfiebot.core.brain import LOCAL_PROVIDERS
from alfiebot.ui import widgets as w

log = logging.getLogger(__name__)

FAILURE_LABELS = {"ok": "Working", "error": "Error", "slow": "Too slow", "timeout": "Timeout",
                  "invalid": "Bad output"}
DELAYS = (0.0, 0.5, 2.0)


class AIPanel:
    def __init__(self, robot, config, rect):
        self.robot = robot
        self.config = config
        self.rect = pygame.Rect(rect)
        self.open = False
        self._hits = []

    @property
    def brain(self):
        return self.robot.brain

    @property
    def router(self):
        return self.robot.brain.router

    def toggle(self):
        self.open = not self.open

    # ---- actions -------------------------------------------------------------
    def _set_enabled(self, on):
        self.brain.ai_enabled = on
        save_setting(self.config, "ai", "enabled", on)

    def _set_mode(self, mode):
        self.router.mode = mode
        save_setting(self.config, "ai", "mode", mode)

    def _set_provider(self, name):
        if self.brain.use_local_provider(name):
            save_setting(self.config, "ai", "local_provider", name)

    def _set_model(self, model):
        local = self.brain.local
        local.model = model
        if hasattr(local, "warm_up"):  # Ollama: save it and load it now
            save_setting(self.config, "ai", "local_model", model)
            if local.available():
                local.warm_up()

    def _set_cloud(self, on):
        self.router.cloud_enabled = on
        save_setting(self.config, "ai", "cloud_enabled", on)
        log.info("Parent setting: cloud AI %s", "on" if on else "off")

    def _set_adult(self, on):
        self.router.adult_test_session = on
        log.info("Adult test session %s", "on: typed text may go to the cloud" if on else "off")

    def _set_offline(self, on):
        self.brain.connectivity.simulate_offline = on
        log.info("Simulated internet: %s", self.brain.connectivity.status)

    def _set_failure(self, provider, failure):
        provider.failure = failure
        log.info("Simulated %s: %s", provider.name, FAILURE_LABELS[failure])

    def _set_delay(self, seconds):
        for provider in (self.brain.local, self.brain.cloud):
            if provider is not None and hasattr(provider, "delay_s"):
                provider.delay_s = seconds

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
    def _button(self, s, rect, label, action, mouse, selected=False, size=15, enabled=True):
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

    def _choices(self, s, x, y, options, current, action, mouse, width=None, enabled=True):
        """A row of buttons, one selected. options: [(value, label)]."""
        for value, label in options:
            bw = width or w.font(15).size(label)[0] + 20
            self._button(s, (x, y, bw, 24), label, (lambda v=value: action(v)), mouse,
                         value == current, enabled=enabled)
            x += bw + 5
        return x

    def draw(self, s, mouse, dt):
        if not self.open:
            return
        self._hits = []
        r = self.rect
        pygame.draw.rect(s, w.PANEL, r, border_radius=10)
        pygame.draw.rect(s, w.ACCENT, r, 1, border_radius=10)
        x, right, y = r.x + 16, r.right - 16, r.y + 14
        brain, router = self.brain, self.router
        w.draw_text(s, "AI brain", (x, y), w.TEXT, 26)
        self._button(s, (right - 80, y - 2, 80, 28), "Close", self.toggle, mouse, size=16)
        y += 34
        y = _para(s, "Hand-written replies answer first. Anything else goes to the AI chosen below. "
                     "Spelling is always marked by Python, never by AI.", x, y, w.TEXT_DIM, 15, right - x) + 12

        label_w = 118
        w.draw_text(s, "AI replies", (x, y + 4), w.ACCENT, 18)
        self._choices(s, x + label_w, y, [(True, "On"), (False, "Off (scripted only)")], brain.ai_enabled,
                      self._set_enabled, mouse)
        y += 30
        w.draw_text(s, "Mode", (x, y + 4), w.ACCENT, 18)
        self._choices(s, x + label_w, y, [(m, MODE_LABELS[m]) for m in MODES], router.mode, self._set_mode,
                      mouse, width=110)
        y += 30
        local = brain.local
        w.draw_text(s, "Local AI", (x, y + 4), w.ACCENT, 18)
        names = [(n, label) for n, label in LOCAL_PROVIDERS.items() if n in brain.local_providers]
        nx = self._choices(s, x + label_w, y, names, brain.local_provider_name, self._set_provider, mouse,
                           width=100)
        if local.simulated:
            note, colour = "Pretend AI: canned answers, for testing.", w.TEXT_DIM
        elif local.available():
            note, colour = f"Ollama {getattr(local, 'version', '')} running on this computer.", w.GOOD
        else:
            note, colour = local.unavailable_reason + " Until then the pretend AI answers.", w.WARN
        _para(s, note, nx + 6, y + 1, colour, 14, right - nx - 6)
        y += 30
        w.draw_text(s, "Model", (x, y + 4), w.TEXT, 16)
        self._choices(s, x + label_w, y, [(m, m) for m in local.models()[:6]], local.model, self._set_model,
                      mouse)
        y += 30
        w.draw_text(s, "Cloud AI", (x, y + 4), w.ACCENT, 18)
        nx = self._choices(s, x + label_w, y, [(False, "Off"), (True, "On (parent)")], router.cloud_enabled,
                           self._set_cloud, mouse)
        self._button(s, (nx + 10, y, 170, 24), f"Adult test session: {'on' if router.adult_test_session else 'off'}",
                     lambda: self._set_adult(not router.adult_test_session), mouse, router.adult_test_session)
        y += 28
        cloud_note = ("Pretend cloud only; nothing leaves this computer. " if brain.cloud and brain.cloud.simulated
                      else "")
        cloud_note += ("A child's words never go to the cloud until privacy checks exist; only an adult "
                       "test session can use it.")
        y = _para(s, cloud_note, x + label_w, y, w.TEXT_DIM, 14, right - x - label_w) + 12

        w.draw_text(s, "Simulate problems", (x, y), w.ACCENT, 19)
        y += 24
        w.draw_text(s, "Internet", (x, y + 4), w.TEXT, 16)
        self._choices(s, x + label_w, y, [(False, "Online"), (True, "Offline")],
                      brain.connectivity.simulate_offline, self._set_offline, mouse)
        y += 28
        for name, provider in (("Local AI", brain.local), ("Cloud AI", brain.cloud)):
            if provider is None or not hasattr(provider, "failure"):
                continue
            w.draw_text(s, name, (x, y + 4), w.TEXT, 16)
            self._choices(s, x + label_w, y, [(f, FAILURE_LABELS[f]) for f in FAILURES], provider.failure,
                          (lambda f, p=provider: self._set_failure(p, f)), mouse, width=92)
            y += 28
        w.draw_text(s, "Think time", (x, y + 4), w.TEXT, 16)
        delay = getattr(brain.local, "delay_s", 0.0)
        nx = self._choices(s, x + label_w, y, [(d, f"{d:g} s") for d in DELAYS], delay, self._set_delay, mouse,
                           width=60)
        w.draw_text(s, f"Gives up after {brain.timeout_s:g} s and uses a hand-written reply.", (nx + 6, y + 5),
                    w.TEXT_DIM, 14)
        y += 36

        y = self._draw_last(s, x, right, y)
        self._draw_stats(s, mouse, x, right, y)

    def _draw_last(self, s, x, right, y):
        w.draw_text(s, "Last AI request", (x, y), w.ACCENT, 19)
        y += 24
        last = self.brain.last
        if last is None:
            w.draw_text(s, "None yet. Type something AlfieBot has no hand-written reply for, "
                           "e.g. \"I like dinosaurs\".", (x, y), w.TEXT_DIM, 15, max_width=right - x)
            return y + 40
        used = {"ai": ("Used the AI reply", w.GOOD), "fallback": ("Used a hand-written reply", w.WARN),
                "pending": ("Waiting for the AI...", w.TEXT),
                "safety": ("Fixed safety reply (no AI)", w.WARN)}[last.used]
        w.draw_text(s, f"\"{last.text}\"  ", (x, y), w.TEXT, 16, max_width=right - x - 200)
        img = w.font(16).render(used[0], True, used[1])
        s.blit(img, (right - img.get_width(), y))
        y += 20
        privacy = f"Privacy: {last.privacy}" + (f" (masked: {', '.join(last.masked)})" if last.masked else "")
        y = _para(s, f"{privacy}.  Route: " + last.decision.summary(), x, y, w.TEXT_DIM, 14, right - x) + 2
        for res in last.results:
            status = "ok" if res.ok else ("timed out" if res.timed_out else f"failed: {res.error}")
            speed = f", {res.tokens_per_s:.0f} tok/s" if res.tokens_per_s else ""
            w.draw_text(s, f"{res.provider} ({res.model}): {status}, {res.latency_s:.2f} s, "
                           f"{res.completion_tokens} tokens{speed}", (x, y), w.TEXT_DIM, 14, max_width=right - x)
            y += 17
        if last.notes:
            y = _para(s, "Fixed in output: " + "; ".join(last.notes), x, y, w.WARN, 14, right - x) + 2
        return y + 10

    def _draw_stats(self, s, mouse, x, right, y):
        w.draw_text(s, "Performance", (x, y), w.ACCENT, 19)
        self._button(s, (right - 100, y - 2, 100, 22), "Reset stats", self.brain.performance.reset, mouse, size=14)
        y += 24
        cols = [("Provider / model", 0), ("Machine", 190), ("Asked", 360), ("Errors", 410), ("Slow", 465),
                ("Median", 510), ("90%", 575), ("Tok/s", 630), ("Cost", 690)]
        for label, cx in cols:
            w.draw_text(s, label, (x + cx, y), w.TEXT_DIM, 14)
        y += 18
        summaries = self.brain.performance.summaries()
        for sm in summaries[:5]:
            values = [f"{sm.provider} ({sm.model})", sm.machine, str(sm.requests), str(sm.errors),
                      str(sm.timeouts), _secs(sm.median_s), _secs(sm.p90_s),
                      f"{sm.tokens_per_s:.0f}" if sm.tokens_per_s else "-", f"${sm.cost:.3f}"]
            for (label, cx), value in zip(cols, values):
                w.draw_text(s, value, (x + cx, y), w.TEXT, 14, max_width=165 if cx < 360 else 60)
            y += 17
        if not summaries:
            w.draw_text(s, "No AI requests yet.", (x, y), w.TEXT, 14)
            y += 17
        _para(s, "Raspberry Pi 5: not measured yet. Times on this computer don't predict the Pi; "
                 "they'll be measured on the real Pi.", x, y + 2, w.WARN, 14, right - x)


def _para(s, text, x, y, colour, size, width) -> int:
    """Wrapped text; returns the y below it."""
    for line in w.wrap_text(text, width, size):
        w.draw_text(s, line, (x, y), colour, size)
        y += size - 1
    return y


def _secs(value):
    return f"{value:.2f} s" if value is not None else "-"
