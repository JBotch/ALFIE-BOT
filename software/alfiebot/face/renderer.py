"""Draws the OLED-style face with pygame.

Every size is a fraction of the target rectangle, so the same face fits
the simulator viewport and any screen resolution. Each eye is one polygon
with a fixed number of points: a rounded square, an arch and a heart are
all described with the same number of points, so blending the numbers
morphs one shape smoothly into another. Features are drawn at
``supersample`` times their size and scaled down for smooth edges, and a
blurred copy is added underneath for the soft cyan glow. No images, no
GPU effects.
"""

import math
from functools import lru_cache
from typing import List, Tuple

import pygame

from alfiebot.face.engine import FaceFrame

BACKGROUND = (3, 6, 12)
EYE = (110, 225, 255)
POINTS = 72  # points per eye outline (the same for every shape, so they morph)
Point = Tuple[float, float]

# Pixel heart (the "love" eyes), 9 x 8 cells, # = lit.
HEART = (
    ".##...##.",
    "####.####",
    "#########",
    "#########",
    ".#######.",
    "..#####..",
    "...###...",
    "....#....",
)


def _lerp_colour(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


# ---- shapes: closed outlines, clockwise from the top centre --------------------
def _resample(points: List[Point], n: int) -> List[Point]:
    """n points evenly spaced along a closed outline, starting at its first point."""
    segs = []
    total = 0.0
    for i, a in enumerate(points):
        b = points[(i + 1) % len(points)]
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        segs.append((a, b, d))
        total += d
    out = []
    step = total / n
    target, acc = 0.0, 0.0
    for a, b, d in segs:
        while target <= acc + d and len(out) < n:
            t = 0.0 if d == 0 else (target - acc) / d
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            target += step
        acc += d
    while len(out) < n:
        out.append(points[0])
    return out


def rounded_rect(w: float, h: float, r: float, n: int = POINTS) -> List[Point]:
    r = max(0.0, min(r, w / 2, h / 2))
    x0, y0 = w / 2 - r, h / 2 - r
    pts = [(0.0, -h / 2)]
    corners = ((x0, -y0, -90), (x0, y0, 0), (-x0, y0, 90), (-x0, -y0, 180))
    for cx, cy, start in corners:
        for k in range(9):
            a = math.radians(start + 90 * k / 8)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return _resample(pts, n)


@lru_cache(maxsize=1)
def _arch_unit() -> Tuple[Point, ...]:
    """A happy-eye arch (a thick upside-down U) in a 1 x 1 box."""
    rx, ry, cy, t = 0.5, 0.78, 0.28, 0.2
    rxi, ryi = rx - t, ry - t * 1.15
    pts = []
    for k in range(17):  # outer: top -> right end
        a = math.radians(-90 + 90 * k / 16)
        pts.append((rx * math.cos(a), cy + ry * math.sin(a)))
    for k in range(33):  # inner: right end -> over the top -> left end
        a = math.radians(0 - 180 * k / 32)
        pts.append((rxi * math.cos(a), cy + ryi * math.sin(a)))
    for k in range(17):  # outer: left end -> top
        a = math.radians(180 + 90 * k / 16)
        pts.append((rx * math.cos(a), cy + ry * math.sin(a)))
    top = cy - ry
    pts = [(x, y - top - 0.5) for x, y in pts[:-1]]  # top edge at -0.5
    return tuple(_resample(pts, POINTS))


@lru_cache(maxsize=1)
def _heart_unit() -> Tuple[Point, ...]:
    """The pixel heart's outline in a 1 x (8/9) box, starting at the top notch."""
    cells = {(x, y) for y, row in enumerate(HEART) for x, ch in enumerate(row) if ch == "#"}
    edges = {}
    for x, y in cells:
        for a, b, nb in (((x, y), (x + 1, y), (x, y - 1)), ((x + 1, y), (x + 1, y + 1), (x + 1, y)),
                         ((x + 1, y + 1), (x, y + 1), (x, y + 1)), ((x, y + 1), (x, y), (x - 1, y))):
            if nb not in cells:
                edges[a] = b
    cols, rows = len(HEART[0]), len(HEART)
    centre = cols / 2
    start = min((v for v in edges if v[1] > 0 and v[1] < 3), key=lambda v: (abs(v[0] - centre), v[1]))
    loop = [start]
    v = edges[start]
    while v != start:
        loop.append(v)
        v = edges[v]
    scale = 1.0 / cols
    pts = [((x - centre) * scale, (y - rows / 2) * scale) for x, y in loop]
    return tuple(_resample(pts, POINTS))


def _scaled(unit, w, h) -> List[Point]:
    return [(x * w, y * h) for x, y in unit]


def _rotate(points, degrees: float):
    if abs(degrees) < 0.01:
        return points
    a = math.radians(degrees)
    c, s = math.cos(a), math.sin(a)
    return [(x * c - y * s, x * s + y * c) for x, y in points]


class FaceRenderer:
    def __init__(self, supersample: int = 2, glow: float = 1.0, show_mouth: bool = True):
        self.ss = max(1, int(supersample))
        self.glow_strength = glow
        self.show_mouth = show_mouth
        self._glow = 1.0
        self.last_eye_boxes: List[pygame.Rect] = []  # for tests: where the eyes were drawn

    # ---- whole face ------------------------------------------------------
    def draw(self, target: pygame.Surface, frame: FaceFrame, rect: pygame.Rect = None) -> None:
        rect = pygame.Rect(rect) if rect else target.get_rect()
        W, H = rect.size
        target.fill(BACKGROUND, rect)
        self.last_eye_boxes = []
        if W < 20 or H < 20:
            return
        p = frame.pose
        # "unit" keeps proportions sensible on screens that aren't 16:9.
        unit = min(H, W * 9 / 16)
        self._glow = _clamp(p.glow * self.glow_strength, 0.0, 2.0)
        ox, oy = rect.topleft
        lift = (p.y_offset + frame.bob) * H
        cx = ox + W / 2
        eye_cy = oy + H * 0.42 + lift
        shift_x = p.gaze_x * unit * 0.035
        shift_y = p.gaze_y * unit * 0.025

        clip = target.get_clip()
        target.set_clip(rect)
        for side, pre in ((-1, "l_"), (1, "r_")):
            e = {k: getattr(p, pre + k) for k in ("w", "h", "open", "round", "lid", "slope", "arch", "heart",
                                                    "pupil", "rot", "dy", "brow_rot")}
            ex = cx + side * unit * 0.31 + shift_x
            ey = eye_cy + e["dy"] * H + shift_y
            self._eye(target, unit, side, e, p, frame, (ex, ey))
            if p.brow > 0.01:
                self._brow(target, unit, side, e, p, (ex, ey), frame.breathe)
        if self.show_mouth:
            mx = cx + shift_x * 0.6
            my = oy + H * 0.42 + unit * 0.28 + lift + shift_y * 0.4
            self._mouth(target, unit, p, (mx, my))
        for particle in frame.particles:
            self._particle(target, particle, rect, unit)
        target.set_clip(clip)

    def _blit_glowing(self, target, surf, centre):
        """Blit a feature with a soft cyan halo (blur by shrinking and
        re-enlarging, then add it to the screen). Working per feature keeps
        the cost low enough for the Pi."""
        x, y = round(centre[0]), round(centre[1])
        if self._glow > 0.02:
            w, h = surf.get_size()
            k = 8
            pad = 3
            sw, sh = max(1, w // k), max(1, h // k)
            small = pygame.Surface((sw + 2 * pad, sh + 2 * pad), pygame.SRCALPHA)
            small.blit(pygame.transform.smoothscale(surf, (sw, sh)), (pad, pad))
            if hasattr(small, "premul_alpha"):
                small = small.premul_alpha()  # transparent pixels add nothing
            level = int(_clamp(150 * self._glow, 0, 255))
            small.fill((level, level, level, 255), special_flags=pygame.BLEND_RGBA_MULT)
            big = pygame.transform.smoothscale(small, (w + 2 * pad * k, h + 2 * pad * k))
            target.blit(big, big.get_rect(center=(x, y)), special_flags=pygame.BLEND_RGB_ADD)
        target.blit(surf, surf.get_rect(center=(x, y)))

    def _canvas(self, w, h):
        ss = self.ss
        surf = pygame.Surface((max(4, int(w * ss)), max(4, int(h * ss))), pygame.SRCALPHA)
        return surf, ss

    def _finish(self, surf, alpha: float = 1.0):
        if alpha < 0.999:
            surf.fill((255, 255, 255, int(255 * _clamp(alpha, 0, 1))), special_flags=pygame.BLEND_RGBA_MULT)
        if self.ss > 1:
            w, h = surf.get_size()
            surf = pygame.transform.smoothscale(surf, (max(1, w // self.ss), max(1, h // self.ss)))
        return surf

    # ---- eye -------------------------------------------------------------
    def eye_outline(self, unit, side, e, breathe=1.0) -> Tuple[List[Point], float, float, float]:
        """The eye polygon around (0, 0), plus its width, full height and current height."""
        w = unit * 0.40 * e["w"] * breathe
        h_full = unit * 0.30 * e["h"] * breathe
        bar = unit * 0.06
        h = bar + (h_full - bar) * _clamp(e["open"], 0.0, 1.3)
        arch = _clamp(e["arch"], 0, 1)
        heart = _clamp(e["heart"], 0, 1 - arch)
        rect_w = 1 - arch - heart
        r = _clamp(e["round"], 0, 0.5) * min(w, h)
        shapes = [(rect_w, rounded_rect(w, h, r))]
        if arch > 0.001:
            shapes.append((arch, _scaled(_arch_unit(), w, h * 0.9)))
        if heart > 0.001:
            hw = w * 0.92
            shapes.append((heart, _scaled(_heart_unit(), hw, hw * (h / h_full))))
        pts = [(sum(wt * s[i][0] for wt, s in shapes), sum(wt * s[i][1] for wt, s in shapes))
               for i in range(POINTS)]
        lid = _clamp(e["lid"], 0, 0.9)
        if lid > 0.001:
            # Cut the top along a slanted line (inner corner = towards the nose).
            top = -h / 2
            out = []
            for x, y in pts:
                s = -side * x / w  # +0.5 at the inner corner, -0.5 at the outer
                line = top + h * lid * (1 + e["slope"] * 1.6 * s)
                out.append((x, max(y, line)))
            pts = out
        return _rotate(pts, e["rot"]), w, h_full, h

    def _eye(self, target, unit, side, e, p, frame, centre):
        pts, w, h_full, h = self.eye_outline(unit, side, e, frame.breathe)
        dots = _clamp(p.dots, 0, 1)
        size = max(w, h_full) * 1.5
        if dots < 0.999:
            surf, ss = self._canvas(size, size)
            c = size / 2
            pygame.draw.polygon(surf, EYE, [((x + c) * ss, (y + c) * ss) for x, y in pts])
            # Pupil: a dark hole that moves with the gaze and stays inside the eye.
            shape = 1 - _clamp(e["arch"] + e["heart"], 0, 1)
            pr = unit * 0.06 * _clamp(e["pupil"], 0, 1.2) * shape
            pr = min(pr, h * 0.36)
            if pr > unit * 0.004 and h > unit * 0.1:
                margin = 0.08 * min(w, h)
                px = _clamp(p.gaze_x, -1, 1) * max(0.0, w / 2 - pr - margin)
                py = _clamp(p.gaze_y, -1, 1) * max(0.0, h / 2 - pr - margin)
                (px, py), = _rotate([(px, py)], e["rot"])
                pygame.draw.circle(surf, (0, 0, 0, 0), ((px + c) * ss, (py + c) * ss), pr * ss)
            self._blit_glowing(target, self._finish(surf, 1 - dots), centre)
            self.last_eye_boxes.append(pygame.Rect(0, 0, w, h).move(centre[0] - w / 2, centre[1] - h / 2))
        if dots > 0.001:
            self._dots(target, unit, side, dots, frame.time, centre)

    def _dots(self, target, unit, side, amount, t, centre):
        """Processing: three square dots per eye, lighting up in turn."""
        d = unit * 0.07
        gap = unit * 0.045
        width = 3 * d + 2 * gap
        surf, ss = self._canvas(width, d)
        for i in range(3):
            k = i if side < 0 else i + 3  # the wave runs across both eyes
            lit = 0.35 + 0.65 * max(0.0, math.sin(2 * math.pi * (t * 0.9 - k / 6)))
            colour = (*EYE, int(255 * _clamp(lit, 0, 1)))
            r = pygame.Rect(int(i * (d + gap) * ss), 0, int(d * ss), int(d * ss))
            pygame.draw.rect(surf, colour, r, border_radius=int(d * ss * 0.18))
        self._blit_glowing(target, self._finish(surf, amount), centre)

    def _brow(self, target, unit, side, e, p, centre, breathe):
        w = unit * 0.40 * e["w"] * breathe * 0.78
        thick = unit * 0.045
        h_full = unit * 0.30 * e["h"] * breathe
        bx = centre[0] - side * unit * 0.01
        by = centre[1] - h_full / 2 - unit * (0.075 + p.brow_y)
        angle = e["brow_rot"] if side < 0 else -e["brow_rot"]  # + = inner end lower
        pts = _rotate(rounded_rect(w, thick, thick / 2, 32), angle)
        size = w * 1.2
        surf, ss = self._canvas(size, size)
        c = size / 2
        pygame.draw.polygon(surf, EYE, [((x + c) * ss, (y + c) * ss) for x, y in pts])
        self._blit_glowing(target, self._finish(surf, p.brow), (bx, by))

    # ---- mouth -----------------------------------------------------------
    def mouth_outline(self, unit, p) -> List[Point]:
        """One closed outline that can be a smile, a frown, a flat line, a
        wavy line, a D-shaped open smile or a circle."""
        mw = unit * 0.2 * max(0.15, p.mouth_width)
        half = mw / 2
        depth = unit * 0.05
        thick = unit * 0.03
        open_depth = unit * 0.09 * _clamp(p.mouth_open, 0, 1.2)
        rnd = _clamp(p.mouth_round, 0, 1)
        wave = _clamp(p.mouth_wave, 0, 1)
        curve = _clamp(p.mouth_curve, -1.2, 1.2)
        n = 28
        upper, lower = [], []
        for i in range(n + 1):
            u = -1 + 2 * i / n
            bend = 1 - u * u
            ell = math.sqrt(max(0.0, bend))
            centre = curve * depth * (bend - 0.5) + wave * depth * 0.5 * math.sin(u * math.pi)
            x = u * half
            top = centre - thick / 2
            bottom = centre + thick / 2 + open_depth * ell  # open: a half-disc below the line
            # Round: blend towards a circle of the mouth's width.
            upper.append((x, top + (-half * ell - top) * rnd))
            lower.append((x, bottom + (half * ell - bottom) * rnd))
        return upper + lower[::-1]

    def _mouth(self, target, unit, p, centre):
        pts = self.mouth_outline(unit, p)
        xs = [x for x, _ in pts]
        ys = [y for _, y in pts]
        thick = unit * 0.03
        w = max(xs) - min(xs) + thick * 2
        h = max(ys) - min(ys) + thick * 2
        size = max(w, h) + thick * 2
        surf, ss = self._canvas(size, size)
        c = size / 2
        mid_y = (max(ys) + min(ys)) / 2
        poly = [((x + c) * ss, (y - mid_y + c) * ss) for x, y in pts]
        pygame.draw.polygon(surf, EYE, poly)
        if p.mouth_round < 0.5:  # rounded ends on a line-like mouth
            n = len(pts) // 2
            for a, b in ((poly[0], poly[-1]), (poly[n - 1], poly[n])):
                pygame.draw.circle(surf, EYE, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2),
                                   max(1.0, abs(b[1] - a[1]) / 2))
        ring = _clamp(p.mouth_ring, 0, 1)
        if ring > 0.01:
            rx = max(0.0, (max(xs) - min(xs)) / 2 - thick) * ring
            ry = max(0.0, (max(ys) - min(ys)) / 2 - thick) * ring
            if rx > 0.5 and ry > 0.5:
                hole = pygame.Rect(0, 0, 2 * rx * ss, 2 * ry * ss)
                hole.center = (c * ss, c * ss)
                pygame.draw.ellipse(surf, (0, 0, 0, 0), hole)
        self._blit_glowing(target, self._finish(surf), (centre[0], centre[1] + mid_y))

    # ---- particles -------------------------------------------------------
    def _particle(self, target, p, rect, unit):
        a = _clamp(p.alpha, 0, 1)
        if a <= 0.01 or p.kind != "zzz":
            return
        x, y = rect.x + p.x * rect.width, rect.y + p.y * rect.height
        s = p.size * unit * (1.0 + 0.5 * (1 - p.life / p.max_life))
        t = max(1.5, s * 0.2)
        # A geometric "Z": top bar, diagonal, bottom bar.
        h = s / 2
        bars = [[(-h, -h), (h, -h), (h, -h + t), (-h, -h + t)],
                [(-h, h - t), (h, h - t), (h, h), (-h, h)],
                [(h - t * 1.3, -h + t), (h, -h + t), (-h + t * 1.3, h - t), (-h, h - t)]]
        size = s * 1.6
        surf, ss = self._canvas(size, size)
        c = size / 2
        for bar in bars:
            pts = _rotate(bar, p.spin * 8)
            pygame.draw.polygon(surf, EYE, [((px + c) * ss, (py + c) * ss) for px, py in pts])
        self._blit_glowing(target, self._finish(surf, a * 0.9), (x, y))
