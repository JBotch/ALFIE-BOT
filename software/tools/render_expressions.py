"""Save a PNG of every expression, a contact sheet of the 16 design
expressions and a few transition frames.

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

from alfiebot.core.states import DESIGN_EXPRESSIONS, Expression  # noqa: E402
from alfiebot.face.engine import FaceEngine  # noqa: E402
from alfiebot.face.renderer import FaceRenderer  # noqa: E402


def settled(expr):
    """The engine after the transition into expr has finished, eyes open."""
    engine = FaceEngine(Expression.NEUTRAL, rng=random.Random(4))
    engine.set_expression(expr)
    for _ in range(150):  # 2.5 s at 60 fps
        engine.update(1 / 60)
    engine._blink_t = None
    return engine


def contact_sheet(renderer, expressions, cell=(480, 270), cols=4):
    cw, ch = cell
    rows = (len(expressions) + cols - 1) // cols
    sheet = pygame.Surface((cols * cw, rows * (ch + 26)))
    sheet.fill((40, 40, 50))
    font = pygame.font.Font(None, 26)
    face = pygame.Surface(cell)
    for i, expr in enumerate(expressions):
        renderer.draw(face, settled(expr).frame())
        x, y = (i % cols) * cw, (i // cols) * (ch + 26)
        sheet.blit(face, (x, y))
        sheet.blit(font.render(f"{i + 1}. {expr.label}", True, (230, 230, 230)), (x + 8, y + ch + 5))
    return sheet


def main(out_dir="expression_previews", size=(1280, 720)):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pygame.init()
    surface = pygame.Surface(size)
    renderer = FaceRenderer()
    for expr in Expression:
        renderer.draw(surface, settled(expr).frame())
        pygame.image.save(surface, str(out / f"{expr.value}.png"))
    pygame.image.save(contact_sheet(renderer, DESIGN_EXPRESSIONS), str(out / "expression_sheet.png"))
    # Transition strip: neutral -> happy, part way through the morph.
    engine = FaceEngine(Expression.NEUTRAL, rng=random.Random(4))
    engine.set_expression(Expression.HAPPY)
    for i in range(4):
        for _ in range(4):
            engine.update(1 / 60)
        renderer.draw(surface, engine.frame())
        pygame.image.save(surface, str(out / f"transition_neutral_to_happy_{i}.png"))
    print(f"Saved previews to {out.resolve()}")


if __name__ == "__main__":
    main(*sys.argv[1:2])
