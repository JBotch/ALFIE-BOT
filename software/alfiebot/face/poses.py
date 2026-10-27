"""What each expression looks like (the OLED face design sheet).

A ``FacePose`` is a set of numbers. The engine glides every number from
the current pose to the target pose, and the renderer turns the numbers
into shapes, so every change of expression is a smooth morph rather than a
swap of pictures. ``Behaviour`` holds the motion layered on top (blinking,
glances, bouncing, ZZZ).

Eyes are rounded squares that can morph into arches (happy), hearts
(love), thin bars (sleepy, closed) or a row of dots (processing). An eye's
top edge can be cut at a slant (sad, angry, thinking), and a dark pupil
can appear inside it. Per-eye values start with ``l_`` (the eye on the
left of the screen) or ``r_``.
"""

from dataclasses import dataclass, fields, replace
from typing import Optional, Tuple

from alfiebot.core.states import Expression


@dataclass
class FacePose:
    # Eye size multipliers (1 = the standard rounded square).
    l_w: float = 1.0
    r_w: float = 1.0
    l_h: float = 1.0
    r_h: float = 1.0
    # 1 = open, 0 = closed (a thin bar remains).
    l_open: float = 1.0
    r_open: float = 1.0
    # Corner rounding, 0 (square) .. 0.5 (pill).
    l_round: float = 0.28
    r_round: float = 0.28
    # Top edge cut: how far down (0..1 of the eye) and its slant
    # (+ inner corner lower = cross, - inner corner higher = sad).
    l_lid: float = 0.0
    r_lid: float = 0.0
    l_slope: float = 0.0
    r_slope: float = 0.0
    # Shape morphs, 0..1: arch (happy) and heart (love).
    l_arch: float = 0.0
    r_arch: float = 0.0
    l_heart: float = 0.0
    r_heart: float = 0.0
    # Dark pupil size, 0 (none) .. 1.
    l_pupil: float = 0.0
    r_pupil: float = 0.0
    # Rotation in degrees (+ = clockwise) and vertical offset (fraction of the face).
    l_rot: float = 0.0
    r_rot: float = 0.0
    l_dy: float = 0.0
    r_dy: float = 0.0
    # Gaze, -1..1 (right / down positive): moves pupils, and the eyes a little.
    gaze_x: float = 0.0
    gaze_y: float = 0.0
    # Processing: eyes become a row of dots, 0..1.
    dots: float = 0.0
    # Eyebrows: visibility 0..1, angle in degrees (+ = inner end lower), height.
    brow: float = 0.0
    l_brow_rot: float = 0.0
    r_brow_rot: float = 0.0
    brow_y: float = 0.0
    # Mouth: width multiplier, curve -1 (frown) .. 1 (smile), open 0..1
    # (a D-shaped open smile), round 0..1 (a circle), wave 0..1 (wobbly),
    # ring 0..1 (hollow circle, for a sleeping "o").
    mouth_width: float = 0.8
    mouth_curve: float = 0.7
    mouth_open: float = 0.0
    mouth_round: float = 0.0
    mouth_wave: float = 0.0
    mouth_ring: float = 0.0
    glow: float = 0.85
    # Whole-face vertical offset as a fraction of the screen height.
    y_offset: float = 0.0

    def copy(self) -> "FacePose":
        return replace(self)


POSE_FIELDS = [f.name for f in fields(FacePose)]


def _both(**values) -> dict:
    """{"pupil": 1} -> {"l_pupil": 1, "r_pupil": 1}."""
    out = {}
    for key, value in values.items():
        out[f"l_{key}"] = value
        out[f"r_{key}"] = value
    return out


def pose(both: dict = None, **values) -> FacePose:
    return FacePose(**{**_both(**(both or {})), **values})


@dataclass(frozen=True)
class Behaviour:
    # Seconds between blinks; "default" uses the configured range.
    blink_interval: object = "default"
    wander: Tuple[float, float] = (0.0, 0.0)  # random glance range x, y
    wander_interval: Tuple[float, float] = (1.2, 3.5)
    look_around: bool = False  # glance left, pause, right, pause...
    bounce: float = 0.0  # vertical bounce amplitude (fraction of height)
    bounce_speed: float = 0.0
    breathe: float = 0.0  # slow eye-size pulse
    glow_pulse: float = 0.0  # slow glow pulse (listening)
    scan: float = 0.0  # small side-to-side gaze movement (thinking)
    brow_wiggle: float = 0.0  # small eyebrow movement (thinking)
    zzz: bool = False
    twitch: bool = False  # occasional small movements while asleep
    flourishes: bool = False  # now and then a curious glance or squint (idle)
    transition_speed: Optional[float] = None  # None = use the configured speed


SMILE = dict(mouth_width=0.8, mouth_curve=0.7)
OPEN_SMILE = dict(mouth_width=0.85, mouth_curve=0.0, mouth_open=1.0)
FLAT = dict(mouth_width=0.55, mouth_curve=0.0)

POSES = {
    Expression.NEUTRAL: pose(**SMILE),
    Expression.HAPPY: pose(dict(arch=1.0, h=1.05), glow=1.0, **OPEN_SMILE),
    Expression.CURIOUS: pose(dict(pupil=1.0, h=1.08, w=1.02), gaze_x=0.55, gaze_y=-0.45,
                             mouth_width=0.7, mouth_curve=0.7),
    Expression.SLEEPY: pose(dict(open=0.0, w=1.05, round=0.5), glow=0.7, y_offset=0.01,
                            mouth_width=0.7, mouth_curve=0.6),
    Expression.SURPRISED: pose(dict(pupil=1.0, h=1.15, w=0.98), glow=1.0, mouth_width=0.55,
                               mouth_curve=0.0, mouth_round=1.0),
    Expression.LOOKING_LEFT: pose(dict(pupil=1.0, h=0.92), gaze_x=-0.85, **SMILE),
    Expression.LOOKING_RIGHT: pose(dict(pupil=1.0, h=0.92), gaze_x=0.85, **SMILE),
    Expression.LOOKING_AROUND: pose(dict(pupil=1.0, h=0.92), **SMILE),
    Expression.THINKING: pose(dict(pupil=1.0, lid=0.16), gaze_x=0.45, gaze_y=-0.5, brow=1.0,
                              l_brow_rot=-12.0, r_brow_rot=15.0, brow_y=0.0, **FLAT),
    Expression.CONFUSED: pose(dict(pupil=1.0), l_rot=-9.0, l_dy=0.025, l_w=0.95, r_h=0.95, r_dy=-0.01,
                              gaze_x=0.25, gaze_y=0.15, mouth_width=0.75, mouth_curve=0.0, mouth_wave=1.0),
    Expression.SAD: pose(dict(lid=0.3, slope=-1.0, h=0.95), glow=0.7, y_offset=0.01,
                         mouth_width=0.55, mouth_curve=-0.85),
    Expression.ANGRY: pose(dict(pupil=1.0, lid=0.25, slope=1.0), gaze_y=0.25, brow=1.0,
                           l_brow_rot=24.0, r_brow_rot=24.0, brow_y=0.02, mouth_width=0.5, mouth_curve=0.0),
    Expression.LOVE: pose(dict(heart=1.0, w=1.0, h=1.15, round=0.2), glow=1.15, **OPEN_SMILE),
    Expression.WINK: pose(dict(pupil=1.0), l_open=0.0, l_pupil=0.0, l_round=0.5, **SMILE),
    Expression.PROCESSING: pose(dots=1.0, mouth_width=0.45, mouth_curve=0.0),
    Expression.SLEEPING: pose(dict(open=0.0, round=0.5), glow=0.55, y_offset=0.02, mouth_width=0.5,
                              mouth_curve=0.0, mouth_round=1.0, mouth_ring=1.0),
    Expression.LISTENING: pose(dict(w=1.05, h=1.12), glow=1.0, y_offset=-0.01, mouth_width=0.5,
                               mouth_curve=0.25),
    Expression.EXCITED: pose(dict(arch=1.0, h=1.1, w=1.05), glow=1.2, y_offset=-0.01, mouth_width=1.0,
                             mouth_curve=0.0, mouth_open=1.0),
}

BEHAVIOURS = {
    Expression.NEUTRAL: Behaviour(wander=(0.35, 0.25), wander_interval=(2.0, 5.0), flourishes=True),
    Expression.HAPPY: Behaviour(blink_interval=(3.0, 6.0), bounce=0.006, bounce_speed=3.0),
    Expression.CURIOUS: Behaviour(wander=(0.2, 0.15), wander_interval=(1.0, 2.5), breathe=0.01),
    Expression.SLEEPY: Behaviour(blink_interval=None, breathe=0.02, transition_speed=3.0),
    Expression.SURPRISED: Behaviour(blink_interval=(4.0, 8.0), transition_speed=12.0),
    Expression.LOOKING_LEFT: Behaviour(wander=(0.05, 0.12), wander_interval=(1.5, 3.0)),
    Expression.LOOKING_RIGHT: Behaviour(wander=(0.05, 0.12), wander_interval=(1.5, 3.0)),
    Expression.LOOKING_AROUND: Behaviour(look_around=True),
    Expression.THINKING: Behaviour(blink_interval=(3.0, 6.0), scan=0.18, brow_wiggle=1.0),
    Expression.CONFUSED: Behaviour(blink_interval=(1.8, 4.0), wander=(0.1, 0.08)),
    Expression.SAD: Behaviour(blink_interval=(3.5, 7.0), breathe=0.008, transition_speed=4.0),
    Expression.ANGRY: Behaviour(blink_interval=(3.0, 6.0)),
    Expression.LOVE: Behaviour(blink_interval=None, breathe=0.04, bounce=0.006, bounce_speed=2.5),
    Expression.WINK: Behaviour(blink_interval=None, wander=(0.05, 0.05)),
    Expression.PROCESSING: Behaviour(blink_interval=None),
    Expression.SLEEPING: Behaviour(blink_interval=None, breathe=0.02, zzz=True, twitch=True,
                                   transition_speed=2.0),
    Expression.LISTENING: Behaviour(blink_interval=(3.5, 7.0), wander=(0.06, 0.04), glow_pulse=0.12,
                                    transition_speed=9.0),
    Expression.EXCITED: Behaviour(blink_interval=(2.5, 5.0), bounce=0.025, bounce_speed=8.0,
                                  transition_speed=10.0),
}

# What the developer panel's look buttons and look_at() mean, as (gaze_x, gaze_y).
LOOK_DIRECTIONS = {
    "left": (-0.85, 0.0), "right": (0.85, 0.0), "up": (0.0, -0.75), "down": (0.0, 0.7),
    "up_left": (-0.7, -0.6), "up_right": (0.7, -0.6), "centre": (0.0, 0.0), "center": (0.0, 0.0),
}
