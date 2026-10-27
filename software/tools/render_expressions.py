"""Save a PNG of every expression (and a few transition frames).

    python tools/render_expressions.py [output_dir]

Runs without a window, so it also works over SSH on the Pi.
"""

import os
import random
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame  # noqa: E402

from alfiebot.core.states import Expression  # noqa: E402
from alfiebot.face.engine import FaceEngine  # noqa: E402
from alfiebot.face.renderer import FaceRenderer  # noqa: E402


def main(out_dir="expression_previews", size=(1280, 720)):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pygame.init()
    surface = pygame.Surface(size)
    renderer = FaceRenderer()
    for expr in Expression:
        engine = FaceEngine(Expression.IDLE, rng=random.Random(4))
        engine.set_expression(expr)
        for _ in range(90):  # 1.5 s at 60 fps: transition finished
            engine.update(1 / 60)
        engine._blink_t = None  # show eyes open
        renderer.draw(surface, engine.frame())
        pygame.image.save(surface, str(out / f"{expr.value}.png"))
    # Transition strip: idle -> happy
    engine = FaceEngine(Expression.IDLE, rng=random.Random(4))
    engine.set_expression(Expression.HAPPY)
    for i in range(4):
        for _ in range(4):
            engine.update(1 / 60)
        renderer.draw(surface, engine.frame())
        pygame.image.save(surface, str(out / f"transition_idle_to_happy_{i}.png"))
    print(f"Saved previews to {out.resolve()}")


if __name__ == "__main__":
    main(*sys.argv[1:2])
