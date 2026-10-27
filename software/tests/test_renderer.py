import random

import pygame
import pytest

from alfiebot.core.states import Expression
from alfiebot.face.engine import FaceEngine
from alfiebot.face.renderer import FaceRenderer


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


def render(expr, size=(1280, 720)):
    engine = FaceEngine(Expression.IDLE, rng=random.Random(1))
    engine.set_expression(expr)
    for _ in range(120):
        engine.update(1 / 60)
    engine._blink_t = None
    surface = pygame.Surface(size)
    FaceRenderer().draw(surface, engine.frame())
    return surface


@pytest.mark.parametrize("expr", list(Expression))
@pytest.mark.parametrize("size", [(1280, 720), (768, 432), (800, 480)])
def test_every_expression_draws_cyan_eyes(expr, size):
    assert bright_pixels(render(expr, size)) > 20


def test_sleeping_is_darker_than_awake():
    assert bright_pixels(render(Expression.SLEEPING)) < bright_pixels(render(Expression.IDLE)) / 3


def test_draws_into_a_sub_rectangle_only():
    engine = FaceEngine(Expression.IDLE)
    surface = pygame.Surface((400, 300))
    surface.fill((255, 0, 0))
    FaceRenderer().draw(surface, engine.frame(), pygame.Rect(50, 50, 160, 90))
    assert surface.get_at((10, 10))[:3] == (255, 0, 0)
    assert surface.get_at((300, 250))[:3] == (255, 0, 0)
