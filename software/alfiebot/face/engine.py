"""Face animation engine (pure Python, no pygame).

Call ``update(dt)`` every frame, then hand ``frame()`` to the renderer.
"""

import math
import random
from dataclasses import dataclass, field
from typing import List

from alfiebot.core.states import Expression
from alfiebot.face.poses import BEHAVIOURS, POSE_FIELDS, POSES, Behaviour, FacePose

BLINK_CLOSE = 0.07
BLINK_HOLD = 0.04
BLINK_OPEN = 0.11
BLINK_TIME = BLINK_CLOSE + BLINK_HOLD + BLINK_OPEN


def approach(current: float, target: float, speed: float, dt: float) -> float:
    """Frame-rate independent exponential ease towards a target."""
    return target + (current - target) * math.exp(-speed * dt)


@dataclass
class Particle:
    kind: str  # "sparkle", "zzz" or "question"
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
        fade_in = min(1.0, age / 0.25)
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
    def __init__(self, expression: Expression = Expression.IDLE,
                 transition_speed: float = 6.0, rng: random.Random = None):
        self.rng = rng or random.Random()
        self.default_speed = transition_speed
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
        self._twitch_t = None
        self._next_twitch = self.rng.uniform(3.0, 7.0)
        self._spawn_timer = 0.0
        self._mouth_phase = 0.0
        self._bounce_amp = 0.0

    # ---- control -------------------------------------------------------
    def set_expression(self, expression: Expression) -> bool:
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
        # A blink as the face changes reads as "coming alive"; waking up gets
        # a double blink once the eyes have opened.
        if previous == Expression.SLEEPING:
            self._next_blink = 0.7
            self._double_blink = True
        elif expression in (Expression.LISTENING, Expression.EXCITED, Expression.CONFUSED):
            self._start_blink()
        else:
            self._next_blink = self._blink_delay()
        return True

    def set_talking(self, talking: bool) -> None:
        self.talking = talking

    def blink(self) -> None:
        self._start_blink()

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
        dt = max(0.0, min(dt, 0.1))  # survive pauses without jumping
        self.time += dt
        b = self.behaviour
        speed = b.transition_speed or self.default_speed
        for name in POSE_FIELDS:
            current = getattr(self.pose, name)
            setattr(self.pose, name, approach(current, getattr(self.target, name), speed, dt))

        self._update_blink(dt)
        self._update_wander(dt)
        self._update_twitch(dt)
        self._update_particles(dt)
        self._bounce_amp = approach(self._bounce_amp, b.bounce, 6.0, dt)
        if self.talking:
            self._mouth_phase += dt

    def _blink_delay(self) -> float:
        interval = BEHAVIOURS[self.expression].blink_interval
        if interval is None:
            return float("inf")
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
                if self.rng.random() < 0.3:
                    self._wander_target = (0.0, 0.0)  # glance back at you
                else:
                    self._wander_target = (self.rng.uniform(-wx, wx),
                                           self.rng.uniform(-wy, wy))
        else:
            self._wander_target = (0.0, 0.0)
        # Eyes dart quickly (saccades) rather than drifting.
        self._wander_x = approach(self._wander_x, self._wander_target[0], 14.0, dt)
        self._wander_y = approach(self._wander_y, self._wander_target[1], 14.0, dt)

    def _update_twitch(self, dt: float) -> None:
        if not self.behaviour.twitch:
            self._twitch_t = None
            return
        if self._twitch_t is not None:
            self._twitch_t += dt
            if self._twitch_t > 0.9:
                self._twitch_t = None
                self._next_twitch = self.rng.uniform(4.0, 9.0)
            return
        self._next_twitch -= dt
        if self._next_twitch <= 0:
            self._twitch_t = 0.0

    def _twitch_amount(self) -> float:
        if self._twitch_t is None:
            return 0.0
        return math.sin(math.pi * self._twitch_t / 0.9)

    def _update_particles(self, dt: float) -> None:
        for p in self.particles:
            p.life -= dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.spin += dt
        self.particles = [p for p in self.particles if p.life > 0]

        b = self.behaviour
        self._spawn_timer -= dt
        if self._spawn_timer > 0:
            return
        rng = self.rng
        if b.sparkles:
            self._spawn_timer = rng.uniform(0.05, 0.14)
            side = rng.choice((-1, 1))
            self.particles.append(Particle(
                "sparkle", 0.5 + side * rng.uniform(0.05, 0.42), rng.uniform(0.08, 0.75),
                rng.uniform(-0.03, 0.03), rng.uniform(-0.12, -0.04),
                life=0.9, max_life=0.9, size=rng.uniform(0.018, 0.04)))
        elif b.zzz:
            self._spawn_timer = rng.uniform(1.4, 2.0)
            self.particles.append(Particle(
                "zzz", 0.74, 0.32, 0.025, -0.05, life=3.2, max_life=3.2,
                size=rng.uniform(0.09, 0.12)))
        elif b.question:
            if not any(p.kind == "question" for p in self.particles):
                self.particles.append(Particle(
                    "question", 0.79, 0.16, 0.0, 0.0, life=3.0, max_life=3.0,
                    size=0.12))
            self._spawn_timer = 0.5
        else:
            self._spawn_timer = 0.2

    def frame(self) -> FaceFrame:
        p = self.pose.copy()
        b = self.behaviour
        t = self.time

        blink = self.blink_amount()
        p.l_open *= blink
        p.r_open *= blink

        p.gaze_x += self._wander_x
        p.gaze_y += self._wander_y
        if b.scan:
            p.gaze_x += b.scan * math.sin(t * 1.1) - b.scan * 0.3
            p.gaze_y += 0.08 * math.sin(t * 0.7)

        twitch = self._twitch_amount()
        if twitch:
            # A sleepy flutter: lids lift a little and the head shifts.
            p.l_open += 0.12 * twitch
            p.r_open += 0.09 * twitch
            p.tilt += 0.15 * twitch

        if self.talking:
            ph = self._mouth_phase
            chatter = abs(math.sin(ph * 11.0)) * (0.6 + 0.4 * math.sin(ph * 3.7))
            p.mouth_open = max(p.mouth_open, 0.15 + 0.55 * chatter)

        breathe = 1.0 + b.breathe * math.sin(t * 1.6)
        bob = 0.0
        if self._bounce_amp > 1e-4:
            speed = b.bounce_speed or 3.0
            bob = -abs(math.sin(t * speed)) * self._bounce_amp
        return FaceFrame(pose=p, breathe=breathe, bob=bob,
                         particles=list(self.particles), time=t)
