"""
alfiebot_parameters.py - single source of truth for AlfieBot V0.1 dimensions.

This module is pure Python (no Autodesk imports) so it can be used both by
the Fusion generator script and by the offline layout checker.

All lengths are in millimetres. Fusion stores lengths internally in
centimetres; the generator converts where needed.

Coordinate system (shared by every component):
    X = robot width, left (-X) to right (+X)
    Y = robot depth, front (-Y) to rear (+Y)
    Z = robot height, bottom (Z = 0, underside of the feet) to top
"""

import math
import re

VERSION = "0.1"
ASSEMBLY_NAME = "AlfieBot_V0.1"

# Bambu Lab A1 Mini build volume (X, Y, Z) in mm.
BUILD_VOLUME_MM = (180.0, 180.0, 180.0)

# Minimum practical FDM wall for a 0.4 mm nozzle (3 perimeters).
MIN_FDM_WALL_MM = 1.2

# Speaker grille hole rings: (radius as a fraction of speaker_diameter,
# count parameter, seed direction in the grille sketch).
GRILLE_RINGS = [
    (0.14, "grille_ring1_count", "up"),
    (0.27, "grille_ring2_count", "right"),
    (0.40, "grille_ring3_count", "down"),
]

# Button accent inlay radii as fractions of button_diameter (diameters).
BUTTON_ACCENT_INNER = 0.6
BUTTON_ACCENT_OUTER = 0.8

# ---------------------------------------------------------------------------
# Parameter tables: (name, expression, unit, comment)
# unit "" means unitless.
# ---------------------------------------------------------------------------

# The eleven parameters requested in the V0.1 brief.
PRIMARY_PARAMETERS = [
    ("body_width", "160 mm", "mm", "Enclosure width along X"),
    ("body_height", "130 mm", "mm", "Enclosure height along Z (excludes feet and button)"),
    ("body_depth", "100 mm", "mm", "Enclosure depth along Y (front face to rear cover)"),
    ("wall_thickness", "3 mm", "mm", "Enclosure wall thickness"),
    ("corner_radius", "22 mm", "mm", "Outer fillet radius on all enclosure edges"),
    ("face_width", "140 mm", "mm", "Front face opening width"),
    ("face_height", "95 mm", "mm", "Front face opening height"),
    ("speaker_diameter", "42 mm", "mm", "Speaker grille diameter"),
    ("button_diameter", "22 mm", "mm", "Top button cap diameter"),
    ("foot_height", "6 mm", "mm", "Foot height; enclosure underside sits at Z = foot_height"),
    ("assembly_clearance", "0.3 mm", "mm", "Clearance between mating printed parts"),
]

# Additional independent parameters needed to fully define V0.1.
# All provisional; edit freely.
SECONDARY_PARAMETERS = [
    # Front face
    ("face_corner_radius", "14 mm", "mm", "Corner radius of the front face opening"),
    ("bezel_thickness", "3 mm", "mm", "Front bezel plate thickness (Y)"),
    ("display_width", "121 mm", "mm", "Display module outline width (placeholder, verify against real display)"),
    ("display_height", "76 mm", "mm", "Display module outline height (placeholder, verify against real display)"),
    ("display_thickness", "5 mm", "mm", "Display module thickness (placeholder)"),
    ("display_overlap", "3 mm", "mm", "Bezel overlap over each display edge"),
    ("display_window_radius", "3 mm", "mm", "Corner radius of the bezel display window"),
    # Speakers
    ("accent_ring_width", "3 mm", "mm", "Radial width of the accent ring tube"),
    ("accent_ring_lip", "1.5 mm", "mm", "Radial overhang of the accent ring lip on the side face"),
    ("accent_ring_protrusion", "1.5 mm", "mm", "How far the accent ring stands proud of the side face"),
    ("grille_step", "1 mm", "mm", "Axial thickness of the ring's inner step that seats the grille"),
    ("grille_step_width", "1.5 mm", "mm", "Radial width of the ring's inner step"),
    ("grille_hole_diameter", "2.5 mm", "mm", "Speaker grille hole diameter"),
    ("grille_ring1_count", "6", "", "Holes in grille ring 1"),
    ("grille_ring2_count", "12", "", "Holes in grille ring 2"),
    ("grille_ring3_count", "18", "", "Holes in grille ring 3"),
    # Top button
    ("button_height", "5 mm", "mm", "Button rise above the enclosure top"),
    ("button_travel", "1 mm", "mm", "Gap between button flange and the inside of the top wall"),
    ("button_flange_width", "3 mm", "mm", "Radial width of the button retaining flange"),
    ("button_flange_thickness", "1.5 mm", "mm", "Thickness of the button retaining flange"),
    ("button_top_fillet", "1 mm", "mm", "Fillet on the button cap top edge"),
    ("button_accent_depth", "1 mm", "mm", "Depth of the blue accent inlay in the button cap"),
    # Feet
    ("foot_diameter", "14 mm", "mm", "Foot diameter"),
    ("foot_fillet", "2 mm", "mm", "Fillet on the foot bottom edge"),
    ("foot_inset", "1 mm", "mm", "Gap between foot edge and the start of the enclosure fillet"),
    # Rear cover
    ("lip_depth", "6 mm", "mm", "How far the rear cover locating tabs reach into the main body"),
    ("lip_thickness", "2 mm", "mm", "Rear cover locating tab thickness"),
    ("lip_bridge_depth", "3 mm", "mm", "Length of the tab root that fuses into the rear cover wall"),
    ("rear_vent_count", "7", "", "Number of rear cover vent slots"),
    ("rear_vent_spacing", "8 mm", "mm", "Rear vent slot pitch along X"),
    ("rear_vent_width", "3 mm", "mm", "Rear vent slot width (X)"),
    ("rear_vent_length", "24 mm", "mm", "Rear vent slot length (Z)"),
    # Electronics tray
    ("tray_thickness", "2.5 mm", "mm", "Electronics tray plate thickness"),
    ("tray_rail_height", "8 mm", "mm", "Height of the tray side rails"),
    ("tray_rail_width", "2 mm", "mm", "Width of the tray side rails"),
    ("standoff_diameter", "6 mm", "mm", "Board standoff outer diameter"),
    ("standoff_hole_diameter", "2.5 mm", "mm", "Board standoff pilot hole (M2.5)"),
    ("standoff_height", "5 mm", "mm", "Board standoff height above the tray"),
    ("pi_hole_spacing_x", "58 mm", "mm", "Raspberry Pi 5 mounting hole pitch, long side"),
    ("pi_hole_spacing_y", "49 mm", "mm", "Raspberry Pi 5 mounting hole pitch, short side"),
    # Eye graphics (visual only)
    ("eye_diameter", "30 mm", "mm", "Eye graphic outer diameter (visual only)"),
    ("eye_spacing", "52 mm", "mm", "Eye graphic centre-to-centre spacing (visual only)"),
    ("eye_offset_z", "6 mm", "mm", "Eye graphic height above the face centre (visual only)"),
    ("eye_graphic_thickness", "0.2 mm", "mm", "Eye graphic thickness (visual only)"),
]

# Dependent values. Edit the expressions only if you want to change the
# design intent, not just a size.
DERIVED_PARAMETERS = [
    ("rear_cover_depth", "corner_radius + 2 mm", "mm", "Rear cover depth; must exceed corner_radius so the split is in the straight section"),
    ("split_y", "body_depth/2 - rear_cover_depth", "mm", "Y position of the main body / rear cover split plane"),
    ("module_center_y", "(corner_radius - rear_cover_depth)/2", "mm", "Y centre of the flat side/top region in front of the split"),
    ("body_center_z", "foot_height + body_height/2", "mm", "Z centre of the enclosure"),
    ("body_top_z", "foot_height + body_height", "mm", "Z of the enclosure top surface"),
    ("face_center_z", "body_center_z", "mm", "Z centre of the front face"),
    ("face_recess", "wall_thickness + 1 mm", "mm", "Depth of the bezel front surface behind the front plane"),
    ("display_front_y", "-body_depth/2 + face_recess + bezel_thickness", "mm", "Y of the display front surface"),
    ("speaker_hole_diameter", "speaker_diameter + 2*accent_ring_width", "mm", "Side wall hole for the accent ring"),
    ("foot_x", "body_width/2 - corner_radius - foot_diameter/2 - foot_inset", "mm", "Foot centre X offset"),
    ("foot_front_y", "-(body_depth/2 - corner_radius) + foot_diameter/2 + foot_inset", "mm", "Front foot centre Y"),
    ("tray_z", "foot_height + wall_thickness", "mm", "Z of the tray underside (inner floor)"),
    ("tray_width", "body_width - 2*corner_radius - 2*assembly_clearance", "mm", "Tray width (fits the flat floor)"),
    ("tray_depth", "body_depth - 2*corner_radius - 2*assembly_clearance", "mm", "Tray depth (fits the flat floor)"),
]

ALL_PARAMETERS = PRIMARY_PARAMETERS + SECONDARY_PARAMETERS + DERIVED_PARAMETERS
PARAMETER_UNITS = {p[0]: p[2] for p in ALL_PARAMETERS}

# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------

COMPONENTS = [
    "Main_Body",
    "Front_Bezel",
    "Display_Placeholder",
    "Top_Button",
    "Left_Speaker_Grille",
    "Right_Speaker_Grille",
    "Left_Accent_Ring",
    "Right_Accent_Ring",
    "Rear_Cover",
    "Electronics_Tray",
    "Feet",
]

# Optional, visual only. Never printed, excluded from physical checks.
VISUAL_COMPONENTS = ["Eye_Graphics"]

# Components that are 3D printed on the A1 Mini.
PRINTABLE_COMPONENTS = [c for c in COMPONENTS if c != "Display_Placeholder"]

# Parameter edits used by the in-Fusion flex test (and the offline checker).
FLEX_TESTS = [
    ("body_width", "175 mm"),
    ("body_depth", "110 mm"),
    ("corner_radius", "18 mm"),
    ("speaker_diameter", "38 mm"),
    ("face_width", "130 mm"),
]

# ---------------------------------------------------------------------------
# Expression evaluation (offline)
# ---------------------------------------------------------------------------

_UNIT_RE = re.compile(r"(?<![A-Za-z_0-9])(mm|deg)(?![A-Za-z_0-9])")


def evaluate(overrides=None):
    """Evaluate every parameter expression to a float (mm or unitless)."""
    overrides = overrides or {}
    values = {}
    namespace = {"__builtins__": {}, "abs": abs, "min": min, "max": max, "sqrt": math.sqrt}
    for name, expr, _unit, _comment in ALL_PARAMETERS:
        expr = overrides.get(name, expr)
        values[name] = float(eval(_UNIT_RE.sub("", expr), namespace, values))
    return values


# ---------------------------------------------------------------------------
# Enclosure geometry helpers
#
# Filleting every edge of a box with the same rolling-ball radius R gives
# exactly the Minkowski sum of a "core" box (shrunk by R) and a sphere of
# radius R. Shelling inwards by t leaves an inner surface that is the same
# core box plus a sphere of radius R - t. This makes containment checks exact.
# ---------------------------------------------------------------------------


def _core(v):
    r = v["corner_radius"]
    half = (v["body_width"] / 2 - r, v["body_depth"] / 2 - r, v["body_height"] / 2 - r)
    centre = (0.0, 0.0, v["body_center_z"])
    return half, centre


def distance_to_core(v, p):
    half, centre = _core(v)
    d = [max(abs(p[i] - centre[i]) - half[i], 0.0) for i in range(3)]
    return math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2)


def box_corners(box):
    (x0, x1), (y0, y1), (z0, z1) = box
    return [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]


def box_inside_cavity(v, box, tol=1e-6):
    """True if an axis-aligned box lies inside the enclosure's inner cavity."""
    limit = v["corner_radius"] - v["wall_thickness"] + tol
    return all(distance_to_core(v, p) <= limit for p in box_corners(box))


def cavity_margin(v, box):
    """Smallest distance (mm) between the box corners and the inner wall."""
    limit = v["corner_radius"] - v["wall_thickness"]
    return min(limit - distance_to_core(v, p) for p in box_corners(box))


# ---------------------------------------------------------------------------
# Analytic part envelopes (axis-aligned, mm) in assembly coordinates
# ---------------------------------------------------------------------------


def part_envelopes(v):
    W, D = v["body_width"], v["body_depth"]
    t, c = v["wall_thickness"], v["assembly_clearance"]
    fh, top, zc = v["foot_height"], v["body_top_z"], v["body_center_z"]
    mc, ys = v["module_center_y"], v["split_y"]
    fcz = v["face_center_z"]

    env = {}
    env["Main_Body"] = ((-W / 2, W / 2), (-D / 2, ys), (fh, top))

    bw, bh = v["face_width"] / 2 - c, v["face_height"] / 2 - c
    yb = -D / 2 + v["face_recess"]
    env["Front_Bezel"] = ((-bw, bw), (yb, yb + v["bezel_thickness"]), (fcz - bh, fcz + bh))

    dw, dh, yd = v["display_width"] / 2, v["display_height"] / 2, v["display_front_y"]
    env["Display_Placeholder"] = ((-dw, dw), (yd, yd + v["display_thickness"]), (fcz - dh, fcz + dh))

    rb = v["button_diameter"] / 2 + v["button_flange_width"]
    zb0 = top - t - v["button_travel"] - v["button_flange_thickness"]
    env["Top_Button"] = ((-rb, rb), (mc - rb, mc + rb), (zb0, top + v["button_height"]))

    rl = v["speaker_hole_diameter"] / 2 + v["accent_ring_lip"]
    rg = v["speaker_diameter"] / 2
    for side, s in (("Left", -1), ("Right", 1)):
        xg = tuple(sorted((s * (W / 2 - t + v["grille_step"]), s * W / 2)))
        env[side + "_Speaker_Grille"] = (xg, (mc - rg, mc + rg), (zc - rg, zc + rg))
    for side, s in (("Left", -1), ("Right", 1)):
        xr = tuple(sorted((s * (W / 2 - t), s * (W / 2 + v["accent_ring_protrusion"]))))
        env[side + "_Accent_Ring"] = (xr, (mc - rl, mc + rl), (zc - rl, zc + rl))

    env["Rear_Cover"] = ((-W / 2, W / 2), (ys - v["lip_depth"], D / 2), (fh, top))

    tw, td, tz = v["tray_width"] / 2, v["tray_depth"] / 2, v["tray_z"]
    th = v["tray_thickness"] + max(v["tray_rail_height"], v["standoff_height"])
    env["Electronics_Tray"] = ((-tw, tw), (-td, td), (tz, tz + th))

    fr, fx, fy = v["foot_diameter"] / 2, v["foot_x"], v["foot_front_y"]
    ry = 2 * mc - fy
    env["Feet"] = ((-fx - fr, fx + fr), (fy - fr, ry + fr), (0.0, fh))
    return env


def assembly_envelope(v):
    env = part_envelopes(v)
    return tuple(
        (min(b[i][0] for b in env.values()), max(b[i][1] for b in env.values()))
        for i in range(3)
    )


def box_size(box):
    return tuple(hi - lo for lo, hi in box)


def fits_build_volume(size):
    """Any-orientation check: sorted part dims vs sorted build volume dims."""
    return all(a <= b + 1e-9 for a, b in zip(sorted(size), sorted(BUILD_VOLUME_MM)))


# ---------------------------------------------------------------------------
# Design rule checks
# ---------------------------------------------------------------------------


def design_rule_checks(v):
    """Return a list of (status, check, detail). status is PASS / WARN / FAIL."""
    out = []

    def check(name, ok, detail, warn_only=False):
        out.append(("PASS" if ok else ("WARN" if warn_only else "FAIL"), name, detail))

    W, H, D = v["body_width"], v["body_height"], v["body_depth"]
    t, R, c = v["wall_thickness"], v["corner_radius"], v["assembly_clearance"]
    mc, ys, zc, top = v["module_center_y"], v["split_y"], v["body_center_z"], v["body_top_z"]
    flat_y = (-(D / 2 - R), D / 2 - R)  # straight section of the side/top walls in Y
    usable_y = (flat_y[0], min(flat_y[1], ys))  # straight section in front of the split

    # Enclosure
    check("Corner radius fits the body", t + 1 < R < min(W, H, D) / 2 - 1,
          "corner_radius=%.1f, needs wall_thickness+1 < R < %.1f" % (R, min(W, H, D) / 2 - 1))
    check("Rear split lies in the straight section", v["rear_cover_depth"] > R + 0.5,
          "rear_cover_depth=%.1f must exceed corner_radius=%.1f" % (v["rear_cover_depth"], R))
    check("FDM wall thickness", t >= MIN_FDM_WALL_MM, "wall_thickness=%.2f" % t)
    check("Assembly clearance in FDM range", 0.1 <= c <= 0.6,
          "assembly_clearance=%.2f (0.1-0.6 typical)" % c, warn_only=True)

    # Front face
    fw2, fh2, fcz = v["face_width"] / 2, v["face_height"] / 2, v["face_center_z"]
    check("Face opening clears the side walls", fw2 <= W / 2 - t - 2,
          "face_width/2=%.1f, limit %.1f" % (fw2, W / 2 - t - 2))
    check("Face opening clears top and bottom walls",
          fcz - fh2 >= v["foot_height"] + t + 2 and fcz + fh2 <= top - t - 2,
          "face Z %.1f..%.1f, inner walls %.1f..%.1f" % (fcz - fh2, fcz + fh2, v["foot_height"] + t, top - t))
    check("Face corner radius valid", c < v["face_corner_radius"] <= min(fw2, fh2),
          "face_corner_radius=%.1f" % v["face_corner_radius"])
    env = part_envelopes(v)
    check("Display inside the cavity", box_inside_cavity(v, env["Display_Placeholder"]),
          "margin %.2f mm" % cavity_margin(v, env["Display_Placeholder"]))
    win_w = v["display_width"] / 2 - v["display_overlap"]
    win_h = v["display_height"] / 2 - v["display_overlap"]
    check("Bezel window smaller than display", v["display_overlap"] > 0, "display_overlap=%.1f" % v["display_overlap"])
    check("Bezel border width printable",
          min(fw2 - c - win_w, fh2 - c - win_h) >= 3.0,
          "border %.1f / %.1f mm" % (fw2 - c - win_w, fh2 - c - win_h))
    ex = v["eye_spacing"] / 2 + v["eye_diameter"] / 2
    ez = abs(v["eye_offset_z"]) + v["eye_diameter"] / 2
    check("Eye graphics inside the bezel window", ex < win_w and ez < win_h,
          "eyes reach %.1f / %.1f, window half %.1f / %.1f" % (ex, ez, win_w, win_h), warn_only=True)

    # Speakers
    rl = v["speaker_hole_diameter"] / 2 + v["accent_ring_lip"]
    check("Accent ring lip on the flat side face (Y)",
          mc - rl >= usable_y[0] and mc + rl <= usable_y[1],
          "ring Y %.1f..%.1f, flat %.1f..%.1f" % (mc - rl, mc + rl, usable_y[0], usable_y[1]))
    check("Accent ring lip on the flat side face (Z)", rl <= H / 2 - R,
          "ring radius %.1f, flat half-height %.1f" % (rl, H / 2 - R))
    check("Accent ring tube wall printable", v["accent_ring_width"] - 2 * c >= MIN_FDM_WALL_MM,
          "radial wall %.2f mm" % (v["accent_ring_width"] - 2 * c))
    check("Grille step seats the grille", v["grille_step_width"] > c and v["grille_step"] < t,
          "grille_step=%.1f grille_step_width=%.1f" % (v["grille_step"], v["grille_step_width"]))
    check("Grille thickness printable", t - v["grille_step"] >= MIN_FDM_WALL_MM,
          "grille thickness %.2f" % (t - v["grille_step"]))
    sd, hd = v["speaker_diameter"], v["grille_hole_diameter"]
    outer = GRILLE_RINGS[-1][0] * sd + hd / 2
    check("Grille holes inside the grille", outer <= sd / 2 - 1.0,
          "outer hole edge %.1f, grille radius %.1f" % (outer, sd / 2))
    for frac, count_name, _ in GRILLE_RINGS:
        r = frac * sd
        web = 2 * math.pi * r / v[count_name] - hd
        check("Grille web, ring r=%.1f" % r, web >= 1.0, "web %.2f mm between holes" % web, warn_only=True)
    radii = [frac * sd for frac, _, _ in GRILLE_RINGS]
    gaps = [radii[0] - hd] + [b - a - hd for a, b in zip(radii, radii[1:])]
    check("Grille ring spacing", min(gaps) >= 1.0, "min radial web %.2f mm" % min(gaps), warn_only=True)

    # Button
    rb = v["button_diameter"] / 2 + v["button_flange_width"]
    check("Button flange under the flat top (Y)", mc - rb >= usable_y[0] and mc + rb <= usable_y[1],
          "flange Y %.1f..%.1f, flat %.1f..%.1f" % (mc - rb, mc + rb, usable_y[0], usable_y[1]))
    check("Button flange under the flat top (X)", rb <= W / 2 - R, "flange radius %.1f" % rb)
    check("Button flange clear of the top wall",
          box_inside_cavity(v, ((-rb, rb), (mc - rb, mc + rb),
                                (env["Top_Button"][2][0], top - t - v["button_travel"]))),
          "button_travel=%.1f" % v["button_travel"])

    # Feet
    fr = v["foot_diameter"] / 2
    check("Feet under the flat base (X)", v["foot_x"] + fr <= W / 2 - R + 1e-9,
          "foot outer X %.1f, flat %.1f" % (v["foot_x"] + fr, W / 2 - R))
    feet_y = env["Feet"][1]
    check("Feet under the main body only (Y)", feet_y[0] >= flat_y[0] - 1e-9 and feet_y[1] <= ys + 1e-9,
          "feet Y %.1f..%.1f, allowed %.1f..%.1f" % (feet_y[0], feet_y[1], flat_y[0], ys))
    check("Feet do not overlap", v["foot_x"] > fr, "foot_x=%.1f" % v["foot_x"])

    # Rear cover tabs
    tab_len = W / 2 - R - 2
    tz_top = top - t - c
    tabs = {
        "top": ((-tab_len, tab_len), (ys - v["lip_depth"], ys), (tz_top - v["lip_thickness"], tz_top)),
        "left": ((-(W / 2 - t - c), -(W / 2 - t - c - v["lip_thickness"])), (ys - v["lip_depth"], ys),
                 (zc - (H / 2 - R - 2), zc + (H / 2 - R - 2))),
    }
    for name, box in tabs.items():
        check("Rear cover %s tab clears the main body" % name, box_inside_cavity(v, box),
              "margin %.2f mm" % cavity_margin(v, box))
    check("Rear tabs printable", v["lip_thickness"] >= MIN_FDM_WALL_MM, "lip_thickness=%.2f" % v["lip_thickness"])
    span = (v["rear_vent_count"] - 1) * v["rear_vent_spacing"] / 2 + v["rear_vent_width"] / 2
    check("Rear vents on the flat rear face", span <= W / 2 - R - 2 and v["rear_vent_length"] / 2 <= H / 2 - R - 2,
          "vent half-span %.1f, half-length %.1f" % (span, v["rear_vent_length"] / 2))

    # Tray
    check("Electronics tray inside the cavity", box_inside_cavity(v, env["Electronics_Tray"], tol=1e-3),
          "margin %.2f mm" % cavity_margin(v, env["Electronics_Tray"]))
    check("Pi standoffs on the tray",
          v["pi_hole_spacing_x"] / 2 + v["standoff_diameter"] / 2 <= v["tray_width"] / 2 - v["tray_rail_width"]
          and v["pi_hole_spacing_y"] / 2 + v["standoff_diameter"] / 2 <= v["tray_depth"] / 2,
          "standoff field %.1f x %.1f, tray %.1f x %.1f" % (
              v["pi_hole_spacing_x"] + v["standoff_diameter"], v["pi_hole_spacing_y"] + v["standoff_diameter"],
              v["tray_width"] - 2 * v["tray_rail_width"], v["tray_depth"]))

    # Rails / side tabs / speaker rings must not collide inside the body
    side_tab_inner_x = W / 2 - t - c - v["lip_thickness"]
    check("Tray rails clear of rear cover side tabs",
          v["tray_width"] / 2 < side_tab_inner_x or env["Electronics_Tray"][2][1] < zc - (H / 2 - R - 2),
          "tray top Z %.1f, side tabs start at Z %.1f" % (env["Electronics_Tray"][2][1], zc - (H / 2 - R - 2)))

    # Printability
    for name in PRINTABLE_COMPONENTS:
        size = box_size(env[name])
        check("Fits A1 Mini: %s" % name, fits_build_volume(size),
              "%.1f x %.1f x %.1f mm" % size)
    return out
