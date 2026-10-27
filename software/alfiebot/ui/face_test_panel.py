"""Face test panel, in the simulator (developer only, never on the robot).

Sits under the robot screen so the face stays visible while testing: a
button for every expression, blinking, looking around, the talking mouth,
animation speed, reset to neutral and an automatic demo of transitions.
Everything goes through the same calls the rest of AlfieBot uses
(show_expression and the validated face commands).
"""

import logging

import pygame

from alfiebot.core.states import DESIGN_EXPRESSIONS, Expression
from alfiebot.ui import widgets as w

log = logging.getLogger(__name__)

PANEL_EXPRESSIONS = list(DESIGN_EXPRESSIONS) + [Expression.LISTENING, Expression.EXCITED]
SPEEDS = (0.25, 0.5, 1.0, 2.0)
DEMO_SECONDS = 2.5
LOOKS = (("Look left", "left"), ("Look right", "right"), ("Look up", "up"), ("Look down", "down"))


class FaceTestPanel:
    def __init__(self, robot, rect):
        self.robot = robot
        self.rect = pygame.Rect(rect)
        self.open = False
        self.face = None  # the simulator's FaceView, set once the window exists
        self.demo = False
        self._demo_t = 0.0
        self._demo_index = -1
        self._hits = []

    def toggle(self):
        self.open = not self.open
        if not self.open:
            self._stop_demo()

    # ---- actions -------------------------------------------------------------
    @property
    def speed(self) -> float:
        return self.face.engine.time_scale if self.face else 1.0

    def _set_speed(self, speed):
        if self.face:
            self.face.engine.time_scale = speed
            log.info("Face animation speed x%g", speed)

    def _show(self, expression):
        self._stop_demo()
        self.robot.show_expression(expression)

    def _toggle_talk(self):
        on = not (self.face and self.face.test_talking)
        self.robot.face_command("talk_test", on)

    def _reset(self):
        self._stop_demo()
        self.robot.face_command("talk_test", False)
        if self.face:
            self.face.engine.time_scale = 1.0
            self.face.engine.reset()
        self.robot.show_expression(Expression.NEUTRAL)

    def _toggle_demo(self):
        if self.demo:
            self._stop_demo()
            return
        self.demo = True
        self._demo_index = -1
        self._demo_t = DEMO_SECONDS
        log.info("Face demo: cycling all %d expressions", len(DESIGN_EXPRESSIONS))

    def _stop_demo(self):
        if self.demo:
            self.demo = False
            log.info("Face demo stopped")

    def update(self, dt):
        if not self.demo:
            return
        self._demo_t += dt * self.speed
        if self._demo_t >= DEMO_SECONDS:
            self._demo_t = 0.0
            self._demo_index = (self._demo_index + 1) % len(DESIGN_EXPRESSIONS)
            self.robot.show_expression(DESIGN_EXPRESSIONS[self._demo_index])

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
    def _button(self, s, rect, label, action, mouse, selected=False, size=15):
        rect = pygame.Rect(rect)
        colour = w.WIDGET_ACTIVE if selected else (w.WIDGET_HOVER if rect.collidepoint(mouse) else w.WIDGET)
        pygame.draw.rect(s, colour, rect, border_radius=6)
        if selected:
            pygame.draw.rect(s, w.ACCENT, rect, 1, border_radius=6)
        img = w.font(size).render(label, True, w.TEXT)
        s.blit(img, img.get_rect(center=rect.center))
        self._hits.append((rect, action))
        return rect.right

    def draw(self, s, mouse, dt):
        if not self.open:
            return
        self._hits = []
        r = self.rect
        pygame.draw.rect(s, w.PANEL, r, border_radius=10)
        pygame.draw.rect(s, w.ACCENT, r, 1, border_radius=10)
        x, right, y = r.x + 14, r.right - 14, r.y + 10
        w.draw_text(s, "Face test", (x, y), w.TEXT, 22)
        w.draw_text(s, "Developer only. The robot screen shows just the face.", (x + 104, y + 5), w.TEXT_DIM, 15)
        self._button(s, (right - 70, y - 2, 70, 24), "Close", self.toggle, mouse)
        y += 30

        # One button per expression, six to a row.
        cols = 6
        bw = (right - x - (cols - 1) * 5) // cols
        current = self.robot.expression_override
        for i, expr in enumerate(PANEL_EXPRESSIONS):
            row, col = divmod(i, cols)
            label = expr.label + ("" if expr in DESIGN_EXPRESSIONS else " *")
            self._button(s, (x + col * (bw + 5), y + row * 28, bw, 24), label,
                         (lambda e=expr: self._show(e)), mouse, current == expr)
        y += 3 * 28 + 6

        bx = x
        bx = self._button(s, (bx, y, 64, 24), "Blink", lambda: self.robot.face_command("blink"), mouse) + 5
        bx = self._button(s, (bx, y, 104, 24), "Double blink",
                          lambda: self.robot.face_command("double_blink"), mouse) + 12
        for label, direction in LOOKS:
            bx = self._button(s, (bx, y, 86, 24), label,
                              (lambda d=direction: self.robot.face_command("look", d)), mouse) + 5
        self._button(s, (bx, y, 104, 24), "Look around", lambda: self.robot.face_command("look_around"), mouse)
        y += 30

        talking = bool(self.face and self.face.test_talking)
        bx = self._button(s, (x, y, 124, 24), f"Mouth test: {'on' if talking else 'off'}", self._toggle_talk,
                          mouse, talking) + 12
        w.draw_text(s, "Speed", (bx, y + 4), w.TEXT_DIM, 15)
        bx += 46
        for speed in SPEEDS:
            bx = self._button(s, (bx, y, 50, 24), f"x{speed:g}", (lambda v=speed: self._set_speed(v)), mouse,
                              abs(self.speed - speed) < 1e-6) + 4
        bx += 8
        bx = self._button(s, (bx, y, 128, 24), "Reset to neutral", self._reset, mouse) + 5
        self._button(s, (bx, y, right - bx, 24), f"Demo all 16: {'on' if self.demo else 'off'}",
                     self._toggle_demo, mouse, self.demo)
        y += 30

        if self.demo:
            note = (f"Demo: {DESIGN_EXPRESSIONS[max(self._demo_index, 0)].label} "
                    f"({max(self._demo_index, 0) + 1} of {len(DESIGN_EXPRESSIONS)})")
        else:
            note = "* = extra expressions the robot uses (listening, excited). Esc closes."
        w.draw_text(s, note, (x, y), w.TEXT_DIM, 15, max_width=right - x)
