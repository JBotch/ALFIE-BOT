"""Face animation engine and expression controller (pure Python, no pygame).

Call ``update(dt)`` every frame, then hand ``frame()`` to the renderer.

Controller commands (all instant to call, never blocking):

    face.set_expression("happy")      any Expression or its name
    face.look_at("left")              left, right, up, down, up_left, up_right, centre
    face.look_around()                a few natural glances, then back
    face.blink() / face.blink(double=True)
    face.start_speaking() / face.stop_speaking()
    face.set_mouth_level(0.6)         voice loudness 0..1 while speaking (None = timed fallback)
    face.reset()                      neutral, looking ahead
"""

import math
import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from alfiebot.core.states import Expression
from alfiebot.face.poses import BEHAVIOURS, LOOK_DIRECTIONS, POSE_FIELDS, POSES, Behaviour, FacePose

BLINK_CLOSE = 0.07
BLINK_HOLD = 0.04
BLINK_OPEN = 0.11
BLINK_TIME = BLINK_CLOSE + BLINK_HOLD + BLINK_OPEN
DEFAULT_BLINK_INTERVAL = (2.5, 6.0)
MAX_GAZE = 1.0


def approach(current: float, target: float, speed: float, dt: float) -> float:
    """Frame-rate independent exponential ease towards a target."""
    return target + (current - target) * math.exp(-speed * dt)


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


@dataclass
class Particle:
    kind: str  # "zzz" (sparkle and question are kept for older callers)
    x: float  # position as a fraction of the screen
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    size: float
    spin: float = 0.0

    @property
    def alpha(self) -> float:
        """0..1, fading in quickly and out slowly."""
        age = self.max_life - self.life
        fade_in = min(1.0, age / 0.4)
        fade_out = min(1.0, self.life / (self.max_life * 0.5))
        return max(0.0, min(fade_in, fade_out))


@dataclass
class FaceFrame:
    """Everything the renderer needs for one frame."""
    pose: FacePose
    breathe: float = 1.0
    bob: float = 0.0
    particles: List[Particle] = field(default_factory=list)
    time: float = 0.0


class FaceEngine:
    def __init__(self, expression: Expression = Expression.NEUTRAL,
                 transition_speed: float = 6.0, rng: random.Random = None,
                 blink_interval: Tuple[float, float] = DEFAULT_BLINK_INTERVAL):
        self.rng = rng or random.Random()
        self.default_speed = transition_speed
        self.blink_interval = tuple(blink_interval)
        self.time_scale = 1.0  # developer panel: slow motion / fast forward
        self.expression = Expression(expression)
        self.behaviour: Behaviour = BEHAVIOURS[self.expression]
        self.target: FacePose = POSES[self.expression].copy()
        self.pose: FacePose = self.target.copy()
        self.talking = False
        self.time = 0.0
        self.particles: List[Particle] = []

        self._blink_t = None  # time into the current blink, or None
        self._next_blink = self._blink_delay()
        self._double_blink = False
        self._wander_x = 0.0
        self._wander_y = 0.0
        self._wander_target = (0.0, 0.0)
        self._next_wander = 1.0
        # look_at / look_around: queued (gaze_x, gaze_y, seconds); weight fades pupils in.
        self._looks: List[Tuple[float, float, float]] = []
        self._look_target: Optional[Tuple[float, float]] = None
        self._look_left_s = 0.0
        self._look_x = 0.0
        self._look_y = 0.0
        self._look_weight = 0.0
        self._twitch_t = None
        self._next_twitch = self.rng.uniform(3.0, 7.0)
        self._flourish: Optional[str] = None
        self._flourish_t = 0.0
        self._next_flourish = self.rng.uniform(8.0, 16.0)
        self._spawn_timer = 0.0
        self._mouth_phase = 0.0
        self._mouth_level: Optional[float] = None
        self._mouth_smooth = 0.0
        self._bounce_amp = 0.0

    # ---- controller --------------------------------------------------------
    def set_expression(self, expression) -> bool:
        expression = Expression(expression)
        if expression == self.expression:
            return False
        previous = self.expression
        self.expression = expression
        self.behaviour = BEHAVIOURS[expression]
        self.target = POSES[expression].copy()
        self._wander_target = (0.0, 0.0)
        self._next_wander = self.rng.uniform(0.6, 1.5)
        self._spawn_timer = 0.0
        self._flourish = None
        if previous == Expression.LOOKING_AROUND:
            self._looks.clear()  # its automatic glances
            self._look_target = None
        # A blink as the face changes reads as "coming alive"; waking up gets
        # a double blink once the eyes have opened.
        if previous in (Expression.SLEEPING, Expression.SLEEPY):
            self._next_blink = 0.8
            self._double_blink = True
        elif expression in (Expression.LISTENING, Expression.SURPRISED, Expression.CONFUSED,
                            Expression.CURIOUS):
            self._start_blink()
        else:
            self._next_blink = self._blink_delay()
        return True

    def look_at(self, direction, seconds: float = 2.5) -> None:
        """Look somewhere for a while. ``direction`` is a name from
        LOOK_DIRECTIONS or a (gaze_x, gaze_y) pair, each -1..1."""
        if isinstance(direction, str):
            gx, gy = LOOK_DIRECTIONS[direction.lower()]
        else:
            gx, gy = (_clamp(float(v), -MAX_GAZE, MAX_GAZE) for v in direction)
        self._looks = [(gx, gy, max(0.2, float(seconds)))]
        self._look_left_s = 0.0

    def look_around(self) -> None:
        """A few natural glances with pauses, then back to the front."""
        r = self.rng
        side = r.choice((-1, 1))
        self._looks = [(side * r.uniform(0.7, 0.9), r.uniform(-0.15, 0.1), r.uniform(0.7, 1.1)),
                       (-side * r.uniform(0.7, 0.9), r.uniform(-0.2, 0.1), r.uniform(0.8, 1.2)),
                       (r.uniform(-0.3, 0.3), r.uniform(-0.55, -0.35), r.uniform(0.5, 0.8)),
                       (0.0, 0.0, 0.4)]
        self._look_left_s = 0.0

    def blink(self, double: bool = False) -> None:
        self._start_blink()
        if double:
            self._double_blink = True

    def start_speaking(self) -> None:
        self.talking = True

    def stop_speaking(self) -> None:
        self.talking = False
        self._mouth_level = None

    def set_talking(self, talking: bool) -> None:
        self.start_speaking() if talking else self.stop_speaking()

    def set_mouth_level(self, level: Optional[float]) -> None:
        """Loudness of the voice right now, 0..1, or None if the speech engine
        can't tell (the mouth then uses a timed animation)."""
        self._mouth_level = None if level is None else _clamp(float(level), 0.0, 1.0)

    def reset(self) -> None:
        self._looks.clear()
        self._look_target = None
        self._flourish = None
        self.set_expression(Expression.NEUTRAL)

    @property
    def transition_progress(self) -> float:
        """0..1 estimate of how far the face is through its current transition."""
        worst = 0.0
        start = POSES[self.expression]
        for name in POSE_FIELDS:
            worst = max(worst, abs(getattr(self.pose, name) - getattr(start, name)))
        return max(0.0, 1.0 - worst)

    # ---- animation -----------------------------------------------------
    def update(self, dt: float) -> None:
        dt = max(0.0, min(dt, 0.1)) * self.time_scale  # survive pauses without jumping
        self.time += dt
        b = self.behaviour
        speed = b.transition_speed or self.default_speed
        for name in POSE_FIELDS:
            current = getattr(self.pose, name)
            setattr(self.pose, name, approach(current, getattr(self.target, name), speed, dt))

        self._update_blink(dt)
        self._update_wander(dt)
        self._update_looks(dt)
        self._update_twitch(dt)
        self._update_flourish(dt)
        self._update_particles(dt)
        self._bounce_amp = approach(self._bounce_amp, b.bounce, 6.0, dt)
        if self.talking:
            self._mouth_phase += dt
        level = self._speech_level() if self.talking else 0.0
        # Mouths open fast and close a little slower, like real speech.
        self._mouth_smooth = approach(self._mouth_smooth, level, 30.0 if level > self._mouth_smooth else 14.0, dt)

    def _speech_level(self) -> float:
        if self._mouth_level is not None:
            return min(1.0, self._mouth_level * 1.4)
        # Timed fallback: syllable-like bursts with small pauses between words.
        ph = self._mouth_phase
        syllables = abs(math.sin(ph * 9.0)) * (0.55 + 0.45 * math.sin(ph * 2.9))
        word_gap = 0.25 if math.sin(ph * 1.7) > 0.85 else 1.0
        return max(0.0, syllables * word_gap)

    def _blink_delay(self) -> float:
        interval = BEHAVIOURS[self.expression].blink_interval
        if interval is None:
            return float("inf")
        if interval == "default":
            interval = self.blink_interval
        return self.rng.uniform(*interval)

    def _start_blink(self) -> None:
        if self._blink_t is None:
            self._blink_t = 0.0

    def _update_blink(self, dt: float) -> None:
        if self._blink_t is not None:
            self._blink_t += dt
            if self._blink_t >= BLINK_TIME:
                self._blink_t = None
                if self._double_blink:
                    self._double_blink = False
                    self._next_blink = 0.12
                else:
                    self._next_blink = self._blink_delay()
                    # Now and then a natural double blink.
                    if self.behaviour.blink_interval and self.rng.random() < 0.15:
                        self._next_blink = 0.15
            return
        self._next_blink -= dt
        if self._next_blink <= 0:
            self._start_blink()

    def blink_amount(self) -> float:
        """1 = eyes as posed, 0 = fully shut by a blink."""
        t = self._blink_t
        if t is None:
            return 1.0
        if t < BLINK_CLOSE:
            return 1.0 - t / BLINK_CLOSE
        if t < BLINK_CLOSE + BLINK_HOLD:
            return 0.0
        return min(1.0, (t - BLINK_CLOSE - BLINK_HOLD) / BLINK_OPEN)

    def _update_wander(self, dt: float) -> None:
        wx, wy = self.behaviour.wander
        if wx or wy:
            self._next_wander -= dt
            if self._next_wander <= 0:
                lo, hi = self.behaviour.wander_interval
                self._next_wander = self.rng.uniform(lo, hi)
                if self.rng.random() < 0.35:
                    self._wander_target = (0.0, 0.0)  # glance back at you
                else:
                    self._wander_target = (self.rng.uniform(-wx, wx), self.rng.uniform(-wy, wy))
        else:
            self._wander_target = (0.0, 0.0)
        # Eyes dart quickly (saccades) rather than drifting.
        self._wander_x = approach(self._wander_x, self._wander_target[0], 14.0, dt)
        self._wander_y = approach(self._wander_y, self._wander_target[1], 14.0, dt)

    def _update_looks(self, dt: float) -> None:
        if self.behaviour.look_around and not self._looks and self._look_target is None:
            self.look_around()
            self._looks.pop()  # no pause at the front: keep looking around
            self._looks.append((0.0, 0.0, self.rng.uniform(0.6, 1.4)))
        if self._look_target is not None:
            self._look_left_s -= dt
            if self._look_left_s <= 0:
                self._look_target = None
        if self._look_target is None and self._looks:
            gx, gy, hold = self._looks.pop(0)
            self._look_target = (gx, gy)
            self._look_left_s = hold
        active = self._look_target is not None
        tx, ty = self._look_target if active else (self._look_x, self._look_y)
        self._look_x = approach(self._look_x, tx, 12.0, dt)
        self._look_y = approach(self._look_y, ty, 12.0, dt)
        self._look_weight = approach(self._look_weight, 1.0 if active else 0.0, 8.0, dt)

    def _update_twitch(self, dt: float) -> None:
        if not self.behaviour.twitch:
            self._twitch_t = None
            return
        if self._twitch_t is not None:
            self._twitch_t += dt
            if self._twitch_t > 0.9:
                self._twitch_t = None
                self._next_twitch = self.rng.uniform(5.0, 10.0)
            return
        self._next_twitch -= dt
        if self._next_twitch <= 0:
            self._twitch_t = 0.0

    def _twitch_amount(self) -> float:
        if self._twitch_t is None:
            return 0.0
        return math.sin(math.pi * self._twitch_t / 0.9)

    def _update_flourish(self, dt: float) -> None:
        """Idle only: every so often a small change of expression."""
        if not self.behaviour.flourishes or self.talking:
            self._flourish = None
            return
        if self._flourish is not None:
            self._flourish_t += dt
            if self._flourish_t > 1.6:
                self._flourish = None
                self._next_flourish = self.rng.uniform(9.0, 20.0)
            return
        self._next_flourish -= dt
        if self._next_flourish <= 0:
            self._flourish = self.rng.choice(("curious", "squint", "glance", "double_blink"))
            self._flourish_t = 0.0
            if self._flourish == "glance":
                self.look_at(self.rng.choice(("left", "right", "up_left", "up_right")), 1.2)
            elif self._flourish == "double_blink":
                self.blink(double=True)

    def _flourish_amount(self) -> float:
        return math.sin(math.pi * min(1.0, self._flourish_t / 1.6)) if self._flourish else 0.0

    def _update_particles(self, dt: float) -> None:
        for p in self.particles:
            p.life -= dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.spin += dt
        self.particles = [p for p in self.particles if p.life > 0]

        self._spawn_timer -= dt
        if self._spawn_timer > 0:
            return
        if self.behaviour.zzz and self.pose.l_open < 0.3:
            # Z, z, Z: each one a little bigger, drifting gently up and right.
            count = sum(1 for p in self.particles if p.kind == "zzz")
            self._spawn_timer = self.rng.uniform(1.2, 1.6)
            self.particles.append(Particle(
                "zzz", 0.68, 0.36, 0.03, -0.07, life=3.6, max_life=3.6,
                size=0.05 + 0.018 * (count % 3), spin=self.rng.uniform(-0.2, 0.2)))
        else:
            self._spawn_timer = 0.3

    def frame(self) -> FaceFrame:
        p = self.pose.copy()
        b = self.behaviour
        t = self.time

        blink = self.blink_amount()
        p.l_open *= blink
        p.r_open *= blink

        # Gaze: the pose, then idle glances, then any look_at / look_around.
        w = self._look_weight
        gx = p.gaze_x + self._wander_x
        gy = p.gaze_y + self._wander_y
        if b.scan:
            gx += b.scan * math.sin(t * 1.3)
            gy += 0.06 * math.sin(t * 0.8)
        p.gaze_x = _clamp(gx * (1 - w) + self._look_x * w, -MAX_GAZE, MAX_GAZE)
        p.gaze_y = _clamp(gy * (1 - w) + self._look_y * w, -MAX_GAZE, MAX_GAZE)
        # Looking somewhere on purpose shows the pupils, even on a face without them.
        if w > 0.01 and p.l_arch < 0.5 and p.l_heart < 0.5:
            p.l_pupil = max(p.l_pupil, 0.9 * w * min(1.0, p.l_open * 2))
            p.r_pupil = max(p.r_pupil, 0.9 * w * min(1.0, p.r_open * 2))

        if b.brow_wiggle:
            wiggle = math.sin(t * 2.1) * math.sin(t * 0.7)
            p.l_brow_rot += 4.0 * wiggle
            p.brow_y += 0.006 * wiggle

        f = self._flourish_amount()
        if self._flourish == "curious":
            p.r_h *= 1 + 0.08 * f
            p.l_h *= 1 - 0.05 * f
        elif self._flourish == "squint":
            p.l_open *= 1 - 0.3 * f
            p.r_open *= 1 - 0.3 * f

        twitch = self._twitch_amount()
        if twitch:
            # A sleepy flutter: lids lift a little and the face shifts.
            p.l_open += 0.18 * twitch
            p.r_open += 0.14 * twitch

        if self.talking or self._mouth_smooth > 0.01:
            level = self._mouth_smooth
            target = 0.15 + 0.75 * level if self.talking else 0.9 * level
            p.mouth_open = max(p.mouth_open * (1 - level * 0.3), target)
            p.mouth_curve = p.mouth_curve * (1 - 0.6 * level)
            p.mouth_ring *= 1 - level
            p.mouth_width = max(p.mouth_width, 0.45) * (1 + 0.1 * level)

        breathe = 1.0 + b.breathe * math.sin(t * 1.6)
        if b.glow_pulse:
            p.glow *= 1 + b.glow_pulse * math.sin(t * 2.4)
        bob = 0.0
        if self._bounce_amp > 1e-4:
            speed = b.bounce_speed or 3.0
            bob = -abs(math.sin(t * speed)) * self._bounce_amp
        return FaceFrame(pose=p, breathe=breathe, bob=bob, particles=list(self.particles), time=t)
