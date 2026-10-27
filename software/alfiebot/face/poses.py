"""What each expression looks like.

A ``FacePose`` is a set of numbers. The engine glides every number from
the current pose to the target pose, which is what makes transitions
smooth instead of swapping images. ``Behaviour`` holds the per-expression
motion (blinking, looking around, bouncing) that is layered on top.
"""

from dataclasses import dataclass, fields, replace
from typing import Optional, Tuple

from alfiebot.core.states import Expression


@dataclass
class FacePose:
    # Eyelids: 1 = fully open, 0 = closed (a thin curved line remains).
    l_open: float = 1.0
    r_open: float = 1.0
    # Top lid slope: + lowers the inner corner (focused), - raises it (curious).
    l_lid: float = 0.0
    r_lid: float = 0.0
    # Lower lid rising into a crescent: 0 = none, 1 = full smiling eye.
    l_smile: float = 0.0
    r_smile: float = 0.0
    l_scale: float = 1.0
    r_scale: float = 1.0
    pupil: float = 1.0
    # Gaze direction, -1..1 (right / down positive).
    gaze_x: float = 0.0
    gaze_y: float = 0.0
    # Head tilt, shown by raising one eye and lowering the other.
    tilt: float = 0.0
    # Mouth: curve -1 (frown) .. 1 (big smile); width multiplier; 0..1 open.
    mouth_curve: float = 0.5
    mouth_width: float = 1.0
    mouth_open: float = 0.0
    glow: float = 0.8
    # Whole-face vertical offset as a fraction of the screen height.
    y_offset: float = 0.0

    def copy(self) -> "FacePose":
        return replace(self)


POSE_FIELDS = [f.name for f in fields(FacePose)]


@dataclass(frozen=True)
class Behaviour:
    blink_interval: Optional[Tuple[float, float]] = (2.5, 6.0)
    wander: Tuple[float, float] = (0.0, 0.0)  # random look-around range x, y
    wander_interval: Tuple[float, float] = (1.2, 3.5)
    bounce: float = 0.0  # vertical bounce amplitude (fraction of height)
    bounce_speed: float = 0.0
    breathe: float = 0.0  # slow eye-size pulse
    scan: float = 0.0  # slow side-to-side gaze sweep (thinking)
    sparkles: bool = False
    zzz: bool = False
    question: bool = False
    twitch: bool = False  # occasional small movements while asleep
    transition_speed: Optional[float] = None  # None = use config default


POSES = {
    Expression.SLEEPING: FacePose(
        l_open=0.0, r_open=0.0, pupil=0.9, gaze_y=0.25,
        mouth_curve=0.2, mouth_width=0.6, glow=0.45, y_offset=0.02),
    Expression.IDLE: FacePose(
        l_open=0.97, r_open=0.97, mouth_curve=0.55, glow=0.8),
    Expression.LISTENING: FacePose(
        l_scale=1.08, r_scale=1.08, l_lid=-0.08, r_lid=-0.08, pupil=1.12,
        gaze_y=-0.08, mouth_curve=0.35, mouth_width=0.75, mouth_open=0.12,
        glow=1.0, y_offset=-0.012),
    Expression.THINKING: FacePose(
        l_open=0.55, r_open=0.7, l_lid=0.06, r_lid=-0.04, pupil=0.9,
        gaze_x=0.4, gaze_y=-0.6, tilt=0.25, mouth_curve=-0.05,
        mouth_width=0.6, glow=0.75),
    Expression.HAPPY: FacePose(
        l_smile=0.72, r_smile=0.72, l_scale=1.03, r_scale=1.03, pupil=1.05,
        mouth_curve=1.0, mouth_width=1.2, mouth_open=0.15, glow=1.0),
    Expression.EXCITED: FacePose(
        l_smile=0.42, r_smile=0.42, l_scale=1.12, r_scale=1.12, pupil=1.18,
        l_lid=-0.1, r_lid=-0.1, mouth_curve=1.0, mouth_width=1.35,
        mouth_open=0.65, glow=1.25, y_offset=-0.015),
    Expression.CONFUSED: FacePose(
        l_open=0.6, l_lid=0.28, r_open=1.0, r_scale=1.1, r_lid=-0.22,
        gaze_x=-0.35, gaze_y=-0.25, tilt=-0.6, mouth_curve=-0.3,
        mouth_width=0.6, glow=0.8),
}

BEHAVIOURS = {
    Expression.SLEEPING: Behaviour(blink_interval=None, breathe=0.025,
                                   zzz=True, twitch=True, transition_speed=2.2),
    Expression.IDLE: Behaviour(wander=(0.6, 0.35)),
    Expression.LISTENING: Behaviour(blink_interval=(3.5, 7.0), wander=(0.08, 0.05),
                                    breathe=0.012, transition_speed=9.0),
    Expression.THINKING: Behaviour(blink_interval=(3.0, 6.0), scan=0.45),
    Expression.HAPPY: Behaviour(blink_interval=(3.0, 6.0), wander=(0.15, 0.08),
                                bounce=0.008, bounce_speed=3.0),
    Expression.EXCITED: Behaviour(blink_interval=(2.0, 4.0), bounce=0.03,
                                  bounce_speed=9.0, sparkles=True,
                                  transition_speed=10.0),
    Expression.CONFUSED: Behaviour(blink_interval=(1.8, 4.0), wander=(0.15, 0.1),
                                   question=True),
}
