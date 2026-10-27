"""Connects the robot to the face engine and renderer.

The robot says which expression to show and whether it is talking; it can
also queue validated face commands (look, blink...) which are applied here
on the next frame. While AlfieBot talks, the mouth follows the loudness of
the voice if the speech engine reports it, otherwise a timed animation.
"""

from alfiebot.core.robot import AlfieBot
from alfiebot.core.states import Expression
from alfiebot.face.engine import DEFAULT_BLINK_INTERVAL, FaceEngine
from alfiebot.face.renderer import FaceRenderer


class FaceView:
    def __init__(self, robot: AlfieBot, config: dict):
        self.robot = robot
        face_cfg = config["face"]
        display = config["display"]
        start = Expression(face_cfg.get("start_expression", "sleeping"))
        blink = face_cfg.get("blink_interval") or DEFAULT_BLINK_INTERVAL
        self.engine = FaceEngine(start, transition_speed=face_cfg["transition_speed"],
                                 blink_interval=(float(blink[0]), float(blink[1])))
        self.renderer = FaceRenderer(supersample=display["supersample"],
                                     glow=display["glow"],
                                     show_mouth=face_cfg["show_mouth"])
        self._robot_talking = False
        self.test_talking = False  # developer panel: move the mouth without speech
        robot.add_face_listener(self._on_face_change)

    def _on_face_change(self, expression: Expression, talking: bool) -> None:
        self.engine.set_expression(expression)
        self._robot_talking = talking

    def update(self, dt: float) -> None:
        engine = self.engine
        commands, self.robot.face_commands[:] = list(self.robot.face_commands), []
        for cmd in commands:
            if cmd.kind == "look":
                engine.look_at(cmd.value, cmd.seconds)
            elif cmd.kind == "look_around":
                engine.look_around()
            elif cmd.kind in ("blink", "double_blink"):
                engine.blink(double=cmd.kind == "double_blink")
            elif cmd.kind == "talk_test":
                self.test_talking = cmd.value
        talking = self._robot_talking or self.test_talking
        if talking != engine.talking:
            engine.set_talking(talking)
        if self._robot_talking:
            engine.set_mouth_level(self.robot.tts.level)
        else:
            engine.set_mouth_level(None)
        engine.update(dt)

    def draw(self, surface, rect=None) -> None:
        # Only the face: spelling letters are never shown on the robot screen
        # (they appear in the developer panel instead).
        self.renderer.draw(surface, self.engine.frame(), rect)
