"""Connects the robot to the face engine and renderer."""

import pygame

from alfiebot.core.robot import AlfieBot
from alfiebot.core.states import Expression
from alfiebot.face.engine import FaceEngine
from alfiebot.face.renderer import FaceRenderer

LETTER_SURE = (90, 215, 255)
LETTER_UNSURE = (240, 180, 60)
LETTER_HEARING = (110, 120, 135)


class FaceView:
    def __init__(self, robot: AlfieBot, config: dict):
        self.robot = robot
        face_cfg = config["face"]
        display = config["display"]
        start = Expression(face_cfg.get("start_expression", "sleeping"))
        self.engine = FaceEngine(start, transition_speed=face_cfg["transition_speed"])
        self.renderer = FaceRenderer(supersample=display["supersample"],
                                     glow=display["glow"],
                                     show_mouth=face_cfg["show_mouth"])
        self._fonts = {}
        robot.add_face_listener(self._on_face_change)

    def _on_face_change(self, expression: Expression, talking: bool) -> None:
        self.engine.set_expression(expression)
        self.engine.set_talking(talking)

    def update(self, dt: float) -> None:
        self.engine.update(dt)

    def draw(self, surface, rect=None) -> None:
        self.renderer.draw(surface, self.engine.frame(), rect)
        self.draw_letters(surface, rect)

    def _font(self, size):
        if size not in self._fonts:
            self._fonts[size] = pygame.font.Font(None, size)
        return self._fonts[size]

    def draw_letters(self, surface, rect=None) -> None:
        """While Alfie spells out loud, show each letter under the eyes as it
        is heard: blue = heard clearly, amber = AlfieBot will ask about it,
        grey = still being heard."""
        letters, hearing = self.robot.spelling_letters()
        cells = letters + [(c, None) for c in hearing]
        if not cells:
            return
        rect = pygame.Rect(rect) if rect else surface.get_rect()
        box = min(rect.height * 0.16, (rect.width * 0.92) / len(cells) - 6)
        box = max(12, int(box))
        gap = max(3, box // 8)
        total = len(cells) * box + (len(cells) - 1) * gap
        x = rect.centerx - total // 2
        y = rect.bottom - box - int(rect.height * 0.05)
        font = self._font(int(box * 0.95))
        for letter, sure in cells:
            colour = LETTER_HEARING if sure is None else (LETTER_SURE if sure else LETTER_UNSURE)
            cell = pygame.Rect(x, y, box, box)
            pygame.draw.rect(surface, (14, 22, 30), cell, border_radius=box // 5)
            pygame.draw.rect(surface, colour, cell, max(1, box // 18), border_radius=box // 5)
            img = font.render(letter, True, colour)
            surface.blit(img, img.get_rect(center=(cell.centerx, cell.centery + box // 16)))
            x += box + gap
