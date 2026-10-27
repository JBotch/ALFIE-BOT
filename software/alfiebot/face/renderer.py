"""Draws the face with pygame.

Every size is a fraction of the target rectangle, so the same face fits
the simulator viewport and the Pi's 1280x720 screen. Eyes are drawn at
``supersample`` times their size and scaled down for smooth edges, and a
blurred copy is added underneath for the cyan glow.
"""

import math

import pygame

from alfiebot.face.engine import FaceFrame

BACKGROUND = (5, 9, 16)
RIM = (150, 238, 255)
IRIS_OUTER = (45, 175, 245)
IRIS_INNER = (20, 105, 210)
PUPIL = (6, 16, 38)
PUPIL_RING = (14, 52, 110)
HIGHLIGHT = (255, 255, 255)
LINE = (120, 228, 255)
MOUTH_INSIDE = (10, 40, 75)


def _lerp_colour(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


class FaceRenderer:
    def __init__(self, supersample: int = 2, glow: float = 1.0, show_mouth: bool = True):
        self.ss = max(1, int(supersample))
        self.glow_strength = glow
        self.show_mouth = show_mouth
        self._fonts = {}

    def _font(self, size: int) -> pygame.font.Font:
        size = max(8, int(size))
        if size not in self._fonts:
            self._fonts[size] = pygame.font.Font(None, size)
        return self._fonts[size]

    # ---- whole face ------------------------------------------------------
    def draw(self, target: pygame.Surface, frame: FaceFrame, rect: pygame.Rect = None) -> None:
        rect = pygame.Rect(rect) if rect else target.get_rect()
        W, H = rect.size
        target.fill(BACKGROUND, rect)
        if W < 20 or H < 20:
            return
        p = frame.pose
        # "unit" keeps proportions sensible on screens that aren't 16:9.
        unit = min(H, W * 9 / 16)
        self._glow = _clamp(p.glow * self.glow_strength, 0.0, 2.0)
        ox, oy = rect.topleft

        cx = W / 2
        cy = H * 0.44 + (p.y_offset + frame.bob) * H
        sep = unit * 0.53
        eye_h = unit * 0.5
        eye_w = eye_h * 0.8
        shift_x = p.gaze_x * unit * 0.05
        shift_y = p.gaze_y * unit * 0.03
        tilt_dy = p.tilt * unit * 0.04

        clip = target.get_clip()
        target.set_clip(rect)
        for side, open_, lid, smile, scale in (
            (-1, p.l_open, p.l_lid, p.l_smile, p.l_scale),
            (1, p.r_open, p.r_lid, p.r_smile, p.r_scale),
        ):
            w = eye_w * scale
            h = eye_h * scale * frame.breathe
            eye = self._eye(w, h, side, open_, lid, smile, p.pupil, p.gaze_x, p.gaze_y)
            ex = ox + cx + side * sep / 2 + shift_x
            ey = oy + cy + shift_y + side * tilt_dy
            self._blit_glowing(target, eye, (ex, ey))

        if self.show_mouth:
            mouth = self._mouth(unit, p.mouth_curve, p.mouth_width, p.mouth_open)
            mx = ox + cx + shift_x * 0.6 + p.tilt * unit * 0.015
            my = oy + H * 0.83 + (p.y_offset + frame.bob) * H + shift_y * 0.5
            self._blit_glowing(target, mouth, (mx, my))

        for particle in frame.particles:
            self._particle(target, particle, rect, unit, frame.time)
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
            level = int(_clamp(200 * self._glow, 0, 255))
            small.fill((level, level, level, 255), special_flags=pygame.BLEND_RGBA_MULT)
            big = pygame.transform.smoothscale(small, (w + 2 * pad * k, h + 2 * pad * k))
            target.blit(big, big.get_rect(center=(x, y)), special_flags=pygame.BLEND_RGB_ADD)
        target.blit(surf, surf.get_rect(center=(x, y)))

    # ---- eye -------------------------------------------------------------
    def _eye(self, w, h, side, openness, lid, smile, pupil, gaze_x, gaze_y):
        ss = self.ss
        W2 = max(4, int(w * ss))
        H2 = max(4, int(h * ss))
        s = pygame.Surface((W2, H2), pygame.SRCALPHA)
        full = pygame.Rect(0, 0, W2, H2)

        pygame.draw.ellipse(s, RIM, full)
        # Iris: rings from bright edge to deeper blue, nudged toward the gaze.
        rim = 0.075
        steps = 7
        gx = _clamp(gaze_x, -1.2, 1.2)
        gy = _clamp(gaze_y, -1.2, 1.2)
        for i in range(steps):
            t = i / (steps - 1)
            inset = rim + t * 0.16
            r = full.inflate(-W2 * inset * 2, -H2 * inset * 2)
            r.move_ip(gx * W2 * 0.06 * t, gy * H2 * 0.05 * t)
            pygame.draw.ellipse(s, _lerp_colour(IRIS_OUTER, IRIS_INNER, t), r)

        # Pupil follows the gaze furthest.
        pw = W2 * 0.56 * pupil
        ph = H2 * 0.58 * pupil
        pcx = W2 / 2 + gx * W2 * 0.15
        pcy = H2 / 2 + gy * H2 * 0.13
        ring = pygame.Rect(0, 0, pw * 1.12, ph * 1.12)
        ring.center = (pcx, pcy)
        pygame.draw.ellipse(s, PUPIL_RING, ring)
        prect = pygame.Rect(0, 0, pw, ph)
        prect.center = (pcx, pcy)
        pygame.draw.ellipse(s, PUPIL, prect)

        # Highlights stay put in the eye (they are reflections), mirrored per eye.
        hx = -side * 0.0
        big = W2 * 0.13
        pygame.draw.ellipse(s, HIGHLIGHT, pygame.Rect(
            pcx - pw * 0.30 - big + hx, pcy - ph * 0.30 - big * 1.1, big * 2, big * 2.2))
        small = W2 * 0.05
        pygame.draw.circle(s, HIGHLIGHT, (pcx + pw * 0.22, pcy + ph * 0.25), small)

        # Mask: the eye ellipse minus eyelids. Applying it with BLEND_RGBA_MIN
        # clears everything outside the visible part of the eye.
        mask = pygame.Surface((W2, H2), pygame.SRCALPHA)
        pygame.draw.ellipse(mask, (255, 255, 255, 255), full)
        clear = (0, 0, 0, 0)

        openness = _clamp(openness, 0.0, 1.2)
        # Fully closed still leaves the bottom 10% of the ellipse: a sleepy curve.
        lid_y = (1.0 - min(openness, 1.0)) * H2 * 0.9
        slope = lid * H2 * 0.3
        inner_y = lid_y + slope
        outer_y = lid_y - slope
        pad = W2
        if side < 0:  # left eye on screen: inner corner is on its right
            left_y, right_y = outer_y, inner_y
        else:
            left_y, right_y = inner_y, outer_y
        # The lid edge bows upwards a little so a half-open eye keeps a
        # rounded top; the bow fades out as the eye closes.
        bow = H2 * 0.12 * min(openness, 1.0)
        if max(left_y, right_y) + bow > 0:
            edge = []
            n = 16
            for i in range(n + 1):
                u = i / n
                y = left_y + (right_y - left_y) * u - bow * (1 - (2 * u - 1) ** 2)
                edge.append((u * W2, y))
            pygame.draw.polygon(mask, clear, [(-pad, -pad), (W2 + pad, -pad),
                                              (W2 + pad, right_y)] + edge[::-1]
                                + [(-pad, left_y)])

        smile = _clamp(smile, 0.0, 1.0)
        if smile > 0.01:
            ew, eh = W2 * 1.6, H2 * 1.15
            centre_y = H2 * (0.5 + 1.25 - 0.85 * smile)
            pygame.draw.ellipse(mask, clear, pygame.Rect(
                W2 / 2 - ew / 2, centre_y - eh / 2, ew, eh))

        s.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        if ss > 1:
            s = pygame.transform.smoothscale(s, (max(1, W2 // ss), max(1, H2 // ss)))
        return s

    # ---- mouth -----------------------------------------------------------
    def _mouth(self, unit, curve, width, open_):
        ss = self.ss
        mw = unit * 0.13 * max(0.2, width)
        depth = unit * 0.045
        thick = max(2, unit * 0.016)
        open_depth = unit * 0.11 * _clamp(open_, 0, 1)
        pad = thick * 2
        W2 = int((mw + pad * 2) * ss)
        H2 = int((depth * 2 + open_depth + pad * 2) * ss)
        s = pygame.Surface((W2, H2), pygame.SRCALPHA)
        base_y = (pad + depth) * ss
        n = 24
        upper, lower = [], []
        for i in range(n + 1):
            u = -1 + 2 * i / n
            x = (pad + mw / 2 + u * mw / 2) * ss
            bend = 1 - u * u
            y = base_y + curve * depth * bend * ss
            upper.append((x, y))
            lower.append((x, y + open_depth * (bend ** 0.7) * ss))
        t = int(thick * ss)
        if open_depth * ss > t * 0.6:
            shape = upper + lower[::-1]
            pygame.draw.polygon(s, MOUTH_INSIDE, shape)
            pygame.draw.lines(s, LINE, False, lower, t)
        pygame.draw.lines(s, LINE, False, upper, t)
        for end in (upper[0], upper[-1], lower[len(lower) // 2]):
            if end is lower[len(lower) // 2] and open_depth * ss <= t * 0.6:
                continue
            pygame.draw.circle(s, LINE, end, t / 2)
        if ss > 1:
            s = pygame.transform.smoothscale(s, (max(1, W2 // ss), max(1, H2 // ss)))
        return s

    # ---- particles -------------------------------------------------------
    def _particle(self, target, p, rect, unit, time):
        a = _clamp(p.alpha, 0, 1)
        if a <= 0.01:
            return
        x, y = rect.x + p.x * rect.width, rect.y + p.y * rect.height
        if p.kind == "sparkle":
            r = p.size * unit * (0.6 + 0.4 * a)
            ang = p.spin * 3
            pts = []
            for k in range(8):
                rad = r if k % 2 == 0 else r * 0.28
                th = ang + k * math.pi / 4
                pts.append((x + rad * math.cos(th), y + rad * math.sin(th)))
            colour = _lerp_colour(BACKGROUND, (200, 245, 255), a)
            pygame.draw.polygon(target, colour, pts)
        elif p.kind in ("zzz", "question"):
            text = "z" if p.kind == "zzz" else "?"
            size = p.size * unit * (1.0 + 0.4 * (1 - p.life / p.max_life))
            if p.kind == "question":
                y += math.sin(time * 2.2) * unit * 0.01
            surf = self._font(size).render(text, True, _lerp_colour(BACKGROUND, LINE, a))
            target.blit(surf, surf.get_rect(center=(x, y)))
