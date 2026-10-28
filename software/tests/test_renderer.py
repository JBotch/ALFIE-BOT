import random
import time

import pygame
import pytest

from alfiebot.core.states import DESIGN_EXPRESSIONS, Expression
from alfiebot.face.engine import FaceEngine
from alfiebot.face.poses import POSE_FIELDS, POSES, FacePose
from alfiebot.face.renderer import POINTS, FaceRenderer, _arch_unit, _heart_unit, rounded_rect


@pytest.fixture(scope="module", autouse=True)
def pygame_init():
    pygame.init()
    yield
    pygame.quit()


def bright_pixels(surface):
    small = pygame.transform.scale(surface, (160, 90))
    count = 0
    for x in range(160):
        for y in range(90):
            r, g, b, *_ = small.get_at((x, y))
            if b > 120 and g > 80:
                count += 1
    return count


def settled(expr, seconds=2.5):
    engine = FaceEngine(Expression.NEUTRAL, rng=random.Random(1))
    engine.set_expression(expr)
    for _ in range(int(seconds * 60)):
        engine.update(1 / 60)
    engine._blink_t = None
    return engine


def render(expr, size=(1280, 720), renderer=None):
    surface = pygame.Surface(size)
    (renderer or FaceRenderer()).draw(surface, settled(expr).frame())
    return surface


@pytest.mark.parametrize("expr", list(Expression))
@pytest.mark.parametrize("size", [(1280, 720), (800, 480), (480, 320)])
def test_every_expression_draws_cyan_features(expr, size):
    assert bright_pixels(render(expr, size)) > 8


def test_all_shapes_have_the_same_number_of_points():
    """That's what lets an eye morph from a square into an arch or a heart."""
    assert len(rounded_rect(10, 8, 2)) == POINTS
    assert len(_arch_unit()) == POINTS
    assert len(_heart_unit()) == POINTS


def test_expressions_look_different():
    neutral = bright_pixels(render(Expression.NEUTRAL))
    assert bright_pixels(render(Expression.HAPPY)) < neutral * 0.8  # arches, not blocks
    assert bright_pixels(render(Expression.SLEEPY)) < neutral * 0.4  # thin bars
    assert bright_pixels(render(Expression.PROCESSING)) < neutral * 0.3  # dots


def test_sleeping_is_darker_than_awake():
    assert bright_pixels(render(Expression.SLEEPING)) < bright_pixels(render(Expression.NEUTRAL)) / 3


def test_eyes_stay_inside_the_face_whatever_the_gaze():
    renderer = FaceRenderer(supersample=1)
    for expr in DESIGN_EXPRESSIONS + [Expression.LISTENING, Expression.EXCITED]:
        for gaze in ((-1, -1), (1, 1), (-1, 1), (1, -1)):
            engine = settled(expr, 1.5)
            frame = engine.frame()
            frame.pose.gaze_x, frame.pose.gaze_y = gaze
            surface = pygame.Surface((800, 480))
            rect = pygame.Rect(0, 0, 800, 480)
            renderer.draw(surface, frame, rect)
            for box in renderer.last_eye_boxes:
                assert rect.contains(box), (expr, gaze, box)


def test_pupils_stay_inside_the_eye():
    renderer = FaceRenderer(supersample=1)
    unit = 480
    for gx in (-1, 1):
        for gy in (-1, 1):
            pose = POSES[Expression.CURIOUS].copy()
            pose.gaze_x, pose.gaze_y = gx, gy
            e = {k: getattr(pose, "l_" + k) for k in ("w", "h", "open", "round", "lid", "slope", "arch",
                                                       "heart", "pupil", "rot", "dy", "brow_rot")}
            pts, w, h_full, h = renderer.eye_outline(unit, -1, e)
            pr = unit * 0.06
            margin = 0.08 * min(w, h)
            px = gx * (w / 2 - pr - margin)
            py = gy * (h / 2 - pr - margin)
            assert abs(px) + pr < w / 2 and abs(py) + pr < h / 2


def test_half_way_morphs_draw():
    """Any blend of two poses must draw (that's what the screen shows mid-transition)."""
    renderer = FaceRenderer(supersample=1)
    surface = pygame.Surface((480, 270))
    rng = random.Random(3)
    exprs = list(Expression)
    for _ in range(40):
        a, b = POSES[rng.choice(exprs)], POSES[rng.choice(exprs)]
        t = rng.random()
        mid = FacePose(**{n: getattr(a, n) + (getattr(b, n) - getattr(a, n)) * t for n in POSE_FIELDS})
        engine = FaceEngine(Expression.NEUTRAL)
        frame = engine.frame()
        frame.pose = mid
        renderer.draw(surface, frame)


def test_draws_into_a_sub_rectangle_only():
    engine = FaceEngine(Expression.NEUTRAL)
    surface = pygame.Surface((400, 300))
    surface.fill((255, 0, 0))
    FaceRenderer().draw(surface, engine.frame(), pygame.Rect(50, 50, 160, 90))
    assert surface.get_at((10, 10))[:3] == (255, 0, 0)
    assert surface.get_at((300, 250))[:3] == (255, 0, 0)


def test_drawing_is_quick_enough_for_smooth_animation():
    """A rough check on this computer only; the Pi needs its own test."""
    renderer = FaceRenderer(supersample=2)
    surface = pygame.Surface((1280, 720))
    engine = settled(Expression.THINKING)
    start = time.perf_counter()
    for _ in range(30):
        engine.update(1 / 60)
        renderer.draw(surface, engine.frame())
    per_frame = (time.perf_counter() - start) / 30
    assert per_frame < 1 / 15
