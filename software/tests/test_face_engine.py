import random

import pytest

from alfiebot.core.states import DESIGN_EXPRESSIONS, Expression
from alfiebot.face.engine import BLINK_TIME, FaceEngine
from alfiebot.face.poses import BEHAVIOURS, POSE_FIELDS, POSES


def run(engine, seconds, fps=60):
    for _ in range(int(seconds * fps)):
        engine.update(1 / fps)


def test_sixteen_design_expressions():
    assert len(DESIGN_EXPRESSIONS) == 16
    assert DESIGN_EXPRESSIONS[0] == Expression.NEUTRAL
    assert DESIGN_EXPRESSIONS[-1] == Expression.SLEEPING


def test_old_names_still_work():
    assert Expression("idle") is Expression.NEUTRAL
    assert Expression.IDLE is Expression.NEUTRAL
    assert Expression("proud") is Expression.LOVE
    with pytest.raises(ValueError):
        Expression("dancing")


def test_transition_is_gradual_not_instant():
    engine = FaceEngine(Expression.NEUTRAL, rng=random.Random(1))
    engine.set_expression(Expression.HAPPY)
    engine.update(1 / 60)
    assert 0 < engine.pose.l_arch < 1
    values = [engine.pose.l_arch]
    for _ in range(30):
        engine.update(1 / 60)
        values.append(engine.pose.l_arch)
    assert values == sorted(values)  # moves steadily towards the target


def test_no_jumps_between_frames():
    """Every pair of expressions morphs without any number leaping in one frame."""
    for a in DESIGN_EXPRESSIONS:
        for b in (Expression.HAPPY, Expression.LOVE, Expression.PROCESSING, Expression.SAD):
            engine = FaceEngine(a, rng=random.Random(2))
            engine.set_expression(b)
            before = engine.pose.copy()
            engine.update(1 / 60)
            for name in POSE_FIELDS:
                span = abs(getattr(POSES[a], name) - getattr(POSES[b], name))
                step = abs(getattr(engine.pose, name) - getattr(before, name))
                assert step <= span * 0.2 + 1e-9, (a, b, name)


def test_transition_settles_on_target():
    for expr in Expression:
        engine = FaceEngine(Expression.NEUTRAL, rng=random.Random(2))
        engine.set_expression(expr)
        run(engine, 4.0)
        for name in POSE_FIELDS:
            assert abs(getattr(engine.pose, name) - getattr(POSES[expr], name)) < 0.01, (expr, name)


def test_transition_speed_independent_of_frame_rate():
    a = FaceEngine(Expression.NEUTRAL, rng=random.Random(3))
    b = FaceEngine(Expression.NEUTRAL, rng=random.Random(3))
    a.set_expression(Expression.EXCITED)
    b.set_expression(Expression.EXCITED)
    run(a, 0.2, fps=60)
    run(b, 0.2, fps=20)
    assert abs(a.pose.mouth_open - b.pose.mouth_open) < 0.02


def test_time_scale_slows_animation():
    fast = FaceEngine(Expression.NEUTRAL, rng=random.Random(3))
    slow = FaceEngine(Expression.NEUTRAL, rng=random.Random(3))
    slow.time_scale = 0.25
    for e in (fast, slow):
        e.set_expression(Expression.HAPPY)
    run(fast, 0.2)
    run(slow, 0.2)
    assert slow.pose.l_arch < fast.pose.l_arch


def test_blinks_close_and_reopen():
    engine = FaceEngine(Expression.NEUTRAL, rng=random.Random(4))
    closed = False
    for _ in range(8 * 60):
        engine.update(1 / 60)
        if engine.blink_amount() == 0.0:
            closed = True
    assert closed
    engine._next_blink = 99  # make sure no new blink starts
    run(engine, 0.5)
    assert engine.blink_amount() == 1.0


def blink_starts(engine, seconds, fps=120):
    starts, was = [], False
    for i in range(int(seconds * fps)):
        engine.update(1 / fps)
        now = engine._blink_t is not None
        if now and not was:
            starts.append(i / fps)
        was = now
    return starts


def test_blink_gaps_are_random_within_configured_limits_with_some_double_blinks():
    engine = FaceEngine(Expression.NEUTRAL, rng=random.Random(5), blink_interval=(1.0, 2.0))
    engine.behaviour = BEHAVIOURS[Expression.NEUTRAL]
    starts = blink_starts(engine, 120)
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    singles = [g for g in gaps if g > 0.5]
    doubles = [g for g in gaps if g <= 0.5]
    assert all(1.0 <= g <= 2.0 + BLINK_TIME + 0.02 for g in singles)
    assert len({round(g, 1) for g in singles}) > 5  # not mechanical
    assert doubles  # occasional double blinks


def test_sleeping_never_blinks_and_zzz_float_up():
    engine = FaceEngine(Expression.SLEEPING, rng=random.Random(5))
    for _ in range(8 * 60):
        engine.update(1 / 60)
        assert engine.blink_amount() == 1.0
    zs = [p for p in engine.frame().particles if p.kind == "zzz"]
    assert zs
    y = zs[0].y
    run(engine, 0.5)
    assert zs[0].y < y


def test_wake_up_from_sleep_opens_and_double_blinks():
    engine = FaceEngine(Expression.SLEEPING, rng=random.Random(6))
    engine.set_expression(Expression.NEUTRAL)
    starts = blink_starts(engine, 2.0)
    assert len(starts) >= 2 and starts[1] - starts[0] < 0.5
    assert engine.pose.l_open > 0.9


def test_idle_glances_around():
    engine = FaceEngine(Expression.NEUTRAL, rng=random.Random(6))
    gazes = set()
    for _ in range(12 * 60):
        engine.update(1 / 60)
        gazes.add(round(engine.frame().pose.gaze_x, 1))
    assert len(gazes) > 3


def test_look_at_moves_both_pupils_then_returns():
    engine = FaceEngine(Expression.NEUTRAL, rng=random.Random(7))
    engine.behaviour = BEHAVIOURS[Expression.HAPPY]  # no idle glances, for a clean check
    engine.look_at("left", seconds=1.0)
    run(engine, 0.6)
    f = engine.frame().pose
    assert f.gaze_x < -0.6
    assert f.l_pupil > 0.5 and f.r_pupil > 0.5  # pupils appear to show where he looks
    run(engine, 1.5)
    f = engine.frame().pose
    assert abs(f.gaze_x) < 0.15 and f.l_pupil < 0.2


def test_look_around_goes_both_ways():
    engine = FaceEngine(Expression.NEUTRAL, rng=random.Random(8))
    engine.look_around()
    xs = []
    for _ in range(4 * 60):
        engine.update(1 / 60)
        xs.append(engine.frame().pose.gaze_x)
    assert min(xs) < -0.5 and max(xs) > 0.5


def test_looking_around_expression_keeps_glancing():
    engine = FaceEngine(Expression.LOOKING_AROUND, rng=random.Random(9))
    xs = []
    for _ in range(8 * 60):
        engine.update(1 / 60)
        xs.append(engine.frame().pose.gaze_x)
    assert min(xs) < -0.5 and max(xs) > 0.5


def test_gaze_stays_in_range():
    engine = FaceEngine(Expression.CURIOUS, rng=random.Random(10))
    engine.look_at((5, -5))
    for _ in range(5 * 60):
        engine.update(1 / 60)
        f = engine.frame().pose
        assert -1 <= f.gaze_x <= 1 and -1 <= f.gaze_y <= 1


def test_timed_mouth_animation_without_audio_level():
    engine = FaceEngine(Expression.HAPPY, rng=random.Random(9))
    engine.start_speaking()
    values = set()
    for _ in range(90):
        engine.update(1 / 60)
        values.add(round(engine.frame().pose.mouth_open, 2))
    assert len(values) > 5


def test_mouth_follows_audio_level():
    engine = FaceEngine(Expression.NEUTRAL, rng=random.Random(9))
    engine.start_speaking()
    engine.set_mouth_level(0.0)
    run(engine, 0.3)
    quiet = engine.frame().pose.mouth_open
    engine.set_mouth_level(1.0)
    run(engine, 0.3)
    loud = engine.frame().pose.mouth_open
    assert loud > quiet + 0.4


def test_mouth_returns_smoothly_after_speaking():
    engine = FaceEngine(Expression.NEUTRAL, rng=random.Random(9))
    engine.start_speaking()
    engine.set_mouth_level(1.0)
    run(engine, 0.3)
    engine.stop_speaking()
    engine.update(1 / 60)
    assert engine.frame().pose.mouth_open > 0.1  # not snapped shut
    run(engine, 1.0)
    assert engine.frame().pose.mouth_open < 0.02


def test_eyes_stay_expressive_while_speaking():
    engine = FaceEngine(Expression.HAPPY, rng=random.Random(9))
    run(engine, 1.0)
    engine.start_speaking()
    run(engine, 0.5)
    assert engine.frame().pose.l_arch > 0.95


def test_excited_bounces():
    engine = FaceEngine(Expression.NEUTRAL, rng=random.Random(7))
    engine.set_expression(Expression.EXCITED)
    run(engine, 1.0)
    bobs = []
    for _ in range(60):
        engine.update(1 / 60)
        bobs.append(engine.frame().bob)
    assert min(bobs) < -0.01


def test_reset_goes_back_to_neutral():
    engine = FaceEngine(Expression.ANGRY, rng=random.Random(1))
    engine.look_at("up")
    engine.reset()
    assert engine.expression == Expression.NEUTRAL
    assert engine._look_target is None and not engine._looks


def test_set_expression_by_name():
    engine = FaceEngine(Expression.NEUTRAL)
    assert engine.set_expression("curious")
    assert engine.expression == Expression.CURIOUS
    with pytest.raises(ValueError):
        engine.set_expression("melt")


def test_long_pause_does_not_jump():
    engine = FaceEngine(Expression.NEUTRAL, rng=random.Random(10))
    engine.set_expression(Expression.HAPPY)
    engine.update(5.0)  # e.g. the window was dragged
    assert engine.pose.l_arch < 0.95
