"""Face only: what runs full screen on the robot's 5-inch display.

Keys: 1-7 expressions, 0 follow the robot state, D demo cycle,
Space or a tap = the robot's button, F11 full screen, Esc quit.
"""

import logging

import pygame

from alfiebot.core.robot import AlfieBot
from alfiebot.core.states import Expression
from alfiebot.ui.face_view import FaceView

log = logging.getLogger(__name__)

EXPRESSION_KEYS = {pygame.K_1 + i: e for i, e in enumerate(Expression)}
DEMO_SECONDS = 4.0


class FaceApp:
    def __init__(self, robot: AlfieBot, config: dict, fullscreen: bool, demo: bool = False):
        self.robot = robot
        self.config = config
        self.fullscreen = fullscreen
        self.demo = demo
        self._demo_t = 0.0
        self._demo_index = 0
        display = config["display"]
        self.window_size = (display["width"], display["height"])
        self.fps = display["fps"]
        self.screen = None
        self.face = None

    def _set_mode(self):
        if self.fullscreen:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            pygame.mouse.set_visible(not self.config["display"]["hide_mouse_in_fullscreen"])
        else:
            self.screen = pygame.display.set_mode(self.window_size)
            pygame.mouse.set_visible(True)

    def run(self, max_frames: int = None) -> int:
        pygame.display.set_caption(f"{self.robot.name} face")
        self._set_mode()
        self.face = FaceView(self.robot, self.config)
        if self.demo:
            self.robot.start()
            self.robot.show_expression(list(Expression)[0])
        clock = pygame.time.Clock()
        frames = 0
        running = True
        while running:
            dt = clock.tick(self.fps) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    running = self._key(event)
                elif event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
                    self._button(False)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self._button(True)
                elif event.type == pygame.MOUSEBUTTONUP:
                    self._button(False)
            if self.demo:
                self._demo_t += dt
                if self._demo_t >= DEMO_SECONDS:
                    self._demo_t = 0.0
                    self._demo_index = (self._demo_index + 1) % len(Expression)
                    self.robot.show_expression(list(Expression)[self._demo_index])
            self.robot.update(dt)
            self.face.update(dt)
            self.face.draw(self.screen)
            pygame.display.flip()
            frames += 1
            if max_frames and frames >= max_frames:
                break
        return 0

    def _button(self, down: bool):
        button = self.robot.platform.button
        if hasattr(button, "press"):
            button.press() if down else button.release()

    def _key(self, event) -> bool:
        if event.key == pygame.K_ESCAPE:
            return False
        if event.key == pygame.K_F11:
            self.fullscreen = not self.fullscreen
            self._set_mode()
        elif event.key in EXPRESSION_KEYS:
            self.demo = False
            self.robot.show_expression(EXPRESSION_KEYS[event.key])
        elif event.key == pygame.K_0:
            self.demo = False
            self.robot.show_expression(None)
        elif event.key == pygame.K_d:
            self.demo = not self.demo
            self._demo_t = DEMO_SECONDS
            log.info("Demo cycle %s", "on" if self.demo else "off")
        elif event.key == pygame.K_SPACE:
            self._button(True)
        return True
