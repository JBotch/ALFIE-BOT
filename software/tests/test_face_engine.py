import random

from alfiebot.core.states import Expression
from alfiebot.face.engine import FaceEngine
from alfiebot.face.poses import POSE_FIELDS, POSES


def run(engine, seconds, fps=60):
    for _ in range(int(seconds * fps)):
        engine.update(1 / fps)


def test_transition_is_gradual_not_instant():
    engine = FaceEngine(Expression.IDLE, rng=random.Random(1))
    start = POSES[Expression.IDLE].l_smile
    end = POSES[Expression.HAPPY].l_smile
    engine.set_expression(Expression.HAPPY)
    engine.update(1 / 60)
    assert start < engine.pose.l_smile < end
    values = [engine.pose.l_smile]
    for _ in range(30):
        engine.update(1 / 60)
        values.append(engine.pose.l_smile)
    assert values == sorted(values)  # moves steadily towards the target


def test_transition_settles_on_target():
    for expr in Expression:
        engine = FaceEngine(Expression.IDLE, rng=random.Random(2))
        engine.set_expression(expr)
        run(engine, 3.0)
        for name in POSE_FIELDS:
            assert abs(getattr(engine.pose, name) - getattr(POSES[expr], name)) < 0.01, (expr, name)


def test_transition_speed_independent_of_frame_rate():
    a = FaceEngine(Expression.IDLE, rng=random.Random(3))
    b = FaceEngine(Expression.IDLE, rng=random.Random(3))
    a.set_expression(Expression.EXCITED)
    b.set_expression(Expression.EXCITED)
    run(a, 0.2, fps=60)
    run(b, 0.2, fps=20)
    assert abs(a.pose.mouth_open - b.pose.mouth_open) < 0.02


def test_idle_blinks_and_reopens():
    engine = FaceEngine(Expression.IDLE, rng=random.Random(4))
    closed = False
    for _ in range(8 * 60):
        engine.update(1 / 60)
        if engine.blink_amount() == 0.0:
            closed = True
    assert closed
    run(engine, 0.3)
    engine._next_blink = 99  # make sure no new blink has started
    run(engine, 0.3)
    assert engine.blink_amount() == 1.0


def test_sleeping_never_blinks_but_moves():
    engine = FaceEngine(Expression.SLEEPING, rng=random.Random(5))
    opens = []
    for _ in range(12 * 60):
        engine.update(1 / 60)
        assert engine.blink_amount() == 1.0
        opens.append(engine.frame().pose.l_open)
    assert max(opens) > 0.05  # occasional sleepy flutter
    assert any(p.kind == "zzz" for p in engine.frame().particles)


def test_idle_looks_around():
    engine = FaceEngine(Expression.IDLE, rng=random.Random(6))
    gazes = set()
    for _ in range(10 * 60):
        engine.update(1 / 60)
        gazes.add(round(engine.frame().pose.gaze_x, 1))
    assert len(gazes) > 3


def test_excited_bounces_and_sparkles():
    engine = FaceEngine(Expression.IDLE, rng=random.Random(7))
    engine.set_expression(Expression.EXCITED)
    run(engine, 1.0)
    bobs = []
    for _ in range(60):
        engine.update(1 / 60)
        bobs.append(engine.frame().bob)
    assert min(bobs) < -0.01
    assert any(p.kind == "sparkle" for p in engine.particles)


def test_confused_shows_question_mark():
    engine = FaceEngine(Expression.IDLE, rng=random.Random(8))
    engine.set_expression(Expression.CONFUSED)
    run(engine, 0.5)
    assert any(p.kind == "question" for p in engine.particles)


def test_talking_moves_mouth():
    engine = FaceEngine(Expression.HAPPY, rng=random.Random(9))
    engine.set_talking(True)
    values = set()
    for _ in range(60):
        engine.update(1 / 60)
        values.add(round(engine.frame().pose.mouth_open, 2))
    assert len(values) > 5


def test_long_pause_does_not_jump():
    engine = FaceEngine(Expression.IDLE, rng=random.Random(10))
    engine.set_expression(Expression.HAPPY)
    engine.update(5.0)  # e.g. the window was dragged
    assert engine.pose.l_smile < POSES[Expression.HAPPY].l_smile - 0.05
