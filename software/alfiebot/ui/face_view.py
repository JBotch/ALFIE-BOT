"""Connects the robot to the face engine and renderer."""

from alfiebot.core.robot import AlfieBot
from alfiebot.core.states import Expression
from alfiebot.face.engine import FaceEngine
from alfiebot.face.renderer import FaceRenderer


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
        robot.add_face_listener(self._on_face_change)

    def _on_face_change(self, expression: Expression, talking: bool) -> None:
        self.engine.set_expression(expression)
        self.engine.set_talking(talking)

    def update(self, dt: float) -> None:
        self.engine.update(dt)

    def draw(self, surface, rect=None) -> None:
        # Only the face: spelling letters are never shown on the robot screen
        # (they appear in the developer panel instead).
        self.renderer.draw(surface, self.engine.frame(), rect)
