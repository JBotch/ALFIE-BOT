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
    ("face_height", "110 mm", "mm", "Front face opening height (tall enough for bezel screws above and below the display)"),
    ("speaker_diameter", "38 mm", "mm", "Speaker grille diameter (the 40 mm speaker rim seats on the accent ring behind it)"),
    ("button_diameter", "22 mm", "mm", "Top button cap diameter"),
    ("foot_height", "6 mm", "mm", "Foot height; enclosure underside sits at Z = foot_height"),
    ("assembly_clearance", "0.3 mm", "mm", "Clearance between mating printed parts"),
]

# Additional independent parameters needed to fully define V0.1.
# All provisional; edit freely.
SECONDARY_PARAMETERS = [
    # Front face
    ("face_corner_radius", "14 mm", "mm", "Corner radius of the front face opening"),
    ("bezel_thickness", "6 mm", "mm", "Front bezel plate thickness (Y); sets the display back far enough to clear the rounded front corners"),
    ("display_width", "143.4 mm", "mm", "Raspberry Pi Touch Display 2 (5 inch) outline, long side, mounted landscape (published 143.4 mm)"),
    ("display_height", "91.46 mm", "mm", "Touch Display 2 (5 inch) outline, short side (published 91.46 mm)"),
    ("display_thickness", "6.6 mm", "mm", "Touch Display 2 panel thickness at the edges, where the brackets clamp it (6.6 mm listed; measure)"),
    ("display_window_width", "111 mm", "mm", "Bezel window width (active area 110.4 mm, viewing area 111.5 mm)"),
    ("display_window_height", "62.6 mm", "mm", "Bezel window height (active area 62.1 mm, viewing area 63 mm)"),
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
    ("button_travel", "0.5 mm", "mm", "Gap between button flange and the inside of the top wall (free play above the switch)"),
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
    ("standoff_diameter", "6 mm", "mm", "Board standoff outer diameter (no longer used: the Pi mounts on the display)"),
    ("standoff_hole_diameter", "2.5 mm", "mm", "Board standoff pilot hole (M2.5, no longer used)"),
    ("standoff_height", "5 mm", "mm", "Height of the tray insert bosses above the tray"),
    ("pi_hole_spacing_x", "58 mm", "mm", "Raspberry Pi 5 mounting hole pitch, long side"),
    ("pi_hole_spacing_y", "49 mm", "mm", "Raspberry Pi 5 mounting hole pitch, short side"),
    # Eye graphics (visual only)
    ("eye_diameter", "30 mm", "mm", "Eye graphic outer diameter (visual only)"),
    ("eye_spacing", "52 mm", "mm", "Eye graphic centre-to-centre spacing (visual only)"),
    ("eye_offset_z", "6 mm", "mm", "Eye graphic height above the face centre (visual only)"),
    ("eye_graphic_thickness", "0.2 mm", "mm", "Eye graphic thickness (visual only)"),
]

# Fastenings: M3 screws into M3 heat-set inserts (see FASTENERS below).
FASTENER_PARAMETERS = [
    ("insert_hole_diameter", "4 mm", "mm", "Hole for an M3 heat-set insert (M3 x 5.7 x 4.6 type; check the insert datasheet)"),
    ("insert_depth", "6 mm", "mm", "Depth of every heat-set insert hole"),
    ("insert_boss_diameter", "8 mm", "mm", "Outer diameter of insert bosses"),
    ("screw_clearance_diameter", "3.4 mm", "mm", "M3 screw clearance hole"),
    ("screw_head_clearance_diameter", "6.2 mm", "mm", "Counterbore and driver access for an M3 socket head (5.5 mm)"),
    # Rear cover to main body: 4 x M3 x 16
    ("rear_screw_inset", "6 mm", "mm", "Rear screw inset from where the rear edge fillets start"),
    ("rear_boss_diameter", "9 mm", "mm", "Rear cover screw boss diameter (holds the counterbore)"),
    ("rear_boss_length", "14 mm", "mm", "Main_Body rear insert boss length in front of the split plane"),
    ("rear_counterbore_depth", "13 mm", "mm", "Screw head counterbore depth from the rear face"),
    # Front bezel to main body: 4 x M3 x 8, above and below the display
    ("bezel_screw_x", "50 mm", "mm", "Bezel screw X offset (screws sit above and below the display)"),
    ("bezel_bracket_thickness", "4 mm", "mm", "Main_Body bezel bracket thickness (Y)"),
    ("bezel_bracket_width", "12 mm", "mm", "Main_Body bezel bracket width (Z)"),
    ("bezel_bracket_overlap", "4 mm", "mm", "How far the bezel brackets reach over the display back edge"),
    # Top button retainer: 2 x M3 x 8
    ("button_switch_size", "12 mm", "mm", "Tactile switch body, square (12 x 12 mm, 6 mm tall switch)"),
    ("button_switch_total_height", "6 mm", "mm", "Tactile switch height from its base to the top of the plunger"),
    ("button_switch_pocket_depth", "1 mm", "mm", "Depth of the switch locating pocket in the retainer"),
    ("button_switch_leg_pitch_x", "12.5 mm", "mm", "Tactile switch leg pitch across the leg pairs"),
    ("button_switch_leg_pitch_y", "5 mm", "mm", "Tactile switch leg pitch within a pair"),
    ("button_switch_leg_hole", "1.4 mm", "mm", "Retainer hole for each switch leg"),
    ("button_screw_offset", "6 mm", "mm", "Gap from the button flange edge to the retainer screw centre"),
    ("button_retainer_thickness", "2.5 mm", "mm", "Button retainer plate thickness"),
    # Feet and tray: 4 x M3 x 10 through each foot and the floor into the tray
    ("foot_counterbore_depth", "3.5 mm", "mm", "Screw head counterbore depth in each foot"),
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
    ("foot_rear_y", "2*module_center_y - foot_front_y", "mm", "Rear foot centre Y (mirror of the front feet)"),
    ("rear_screw_x", "body_width/2 - corner_radius - rear_screw_inset", "mm", "Rear cover screw X offset"),
    ("rear_screw_dz", "body_height/2 - corner_radius - rear_screw_inset", "mm", "Rear cover screw Z offset from the body centre"),
    ("bezel_screw_dz", "display_height/2 + insert_boss_diameter/2 + 0.6 mm", "mm", "Bezel screw Z offset above and below the face centre (just clear of the display)"),
    ("display_back_y", "display_front_y + display_thickness", "mm", "Y of the display panel back, where the brackets clamp it"),
    ("button_switch_height", "button_switch_total_height - button_switch_pocket_depth", "mm", "Switch height above the retainer top face"),
    ("button_screw_x", "button_diameter/2 + button_flange_width + button_screw_offset", "mm", "Button retainer screw X offset"),
    ("button_retainer_z", "body_top_z - wall_thickness - button_travel - button_flange_thickness - button_switch_height",
     "mm", "Z of the button retainer top face"),
]

# Bought electronics (Stage H). Sizes come from the published product data;
# the ones marked "assumed" or "measure" had no published drawing.
ELECTRONICS_PARAMETERS = [
    # Raspberry Pi Touch Display 2 (5 inch) carries the Pi 5 on its back
    ("display_total_depth", "16 mm", "mm", "Display depth including the Pi standoffs on its back (published 16 mm)"),
    ("display_standoff_diameter", "5 mm", "mm", "Display Pi standoff diameter (mock-up)"),
    ("pi_holes_center_x", "10 mm", "mm", "X of the Pi hole pattern centre on the display back (assumed; puts the board centred)"),
    # Raspberry Pi 5 + Active Cooler
    ("pi_board_length", "85 mm", "mm", "Raspberry Pi 5 board length"),
    ("pi_board_width", "56 mm", "mm", "Raspberry Pi 5 board width"),
    ("pi_board_thickness", "1.6 mm", "mm", "Raspberry Pi 5 board thickness"),
    ("pi_hole_inset", "3.5 mm", "mm", "Raspberry Pi 5 mounting hole inset from the board edges"),
    ("cooler_length", "63.5 mm", "mm", "Active Cooler footprint along the board"),
    ("cooler_width", "42.5 mm", "mm", "Active Cooler footprint across the board"),
    ("cooler_height", "13.7 mm", "mm", "Active Cooler height above the board"),
    # Official 27 W USB-C power supply and the mini USB microphone
    ("usbc_plug_width", "12 mm", "mm", "PSU USB-C plug overmould width (measure)"),
    ("usbc_plug_thickness", "7 mm", "mm", "PSU USB-C plug overmould thickness (measure)"),
    ("usbc_plug_length", "26 mm", "mm", "PSU USB-C plug length out from the board edge, strain relief included (measure)"),
    ("psu_cable_diameter", "3.5 mm", "mm", "PSU cable diameter"),
    ("mic_length", "10 mm", "mm", "Mini USB microphone length standing out of the USB port (22 mm overall)"),
    ("mic_width", "18 mm", "mm", "Mini USB microphone width"),
    ("mic_thickness", "7 mm", "mm", "Mini USB microphone thickness"),
    # 40 mm 3 W speakers and their clamps
    ("speaker_outer_diameter", "40 mm", "mm", "Speaker frame diameter"),
    ("speaker_depth", "20 mm", "mm", "Speaker depth, rim to magnet back (measure)"),
    ("speaker_rim_thickness", "2.5 mm", "mm", "Speaker front rim thickness (measure)"),
    ("speaker_magnet_diameter", "28 mm", "mm", "Speaker magnet diameter (measure)"),
    ("speaker_boss_length", "7 mm", "mm", "Speaker clamp insert boss length from the inner side wall"),
    ("speaker_clamp_dz", "30 mm", "mm", "Speaker clamp screw Z offset above and below the speaker axis"),
    ("speaker_clamp_thickness", "3 mm", "mm", "Speaker clamp plate thickness"),
    ("speaker_clamp_width", "12 mm", "mm", "Speaker clamp arm width"),
    # Adafruit MAX98357A I2S amplifier
    ("amp_board_width", "19.4 mm", "mm", "Amplifier board size along X (19.4 x 17.8 mm published)"),
    ("amp_board_depth", "17.8 mm", "mm", "Amplifier board size along Y"),
    ("amp_board_thickness", "1.6 mm", "mm", "Amplifier board thickness"),
    ("amp_center_y", "7 mm", "mm", "Amplifier centre Y on the tray"),
    ("amp_ledge_height", "3 mm", "mm", "Height of the cradle ledges under the amplifier (clears solder joints)"),
    ("amp_ledge_width", "1.5 mm", "mm", "Width of the cradle ledges under the amplifier side edges"),
    ("amp_cradle_wall", "1.6 mm", "mm", "Amplifier cradle wall thickness"),
    ("amp_screw_x", "16 mm", "mm", "Amplifier clamp screw X offset"),
    ("amp_clamp_overlap", "2 mm", "mm", "How far each clamp tab presses on the amplifier board edge"),
    ("amp_clamp_thickness", "3 mm", "mm", "Amplifier clamp tab thickness"),
    ("amp_part_height", "8.5 mm", "mm", "Height of the amplifier header pins and terminal block above the board"),
    # PSU cable route: over the top, down behind the Pi, along the tray, out
    # through a slot in the tray and the Main_Body floor and away under the
    # rear cover, so the cover comes off with the cable still plugged in.
    ("psu_route_y", "11 mm", "mm", "Y of the PSU cable's vertical run behind the Pi"),
    ("psu_exit_y", "23 mm", "mm", "Y where the PSU cable drops through the tray and the floor"),
    ("cable_bend_radius", "3 mm", "mm", "PSU cable bend radius at each corner of the route"),
    ("cable_slot_width", "4.2 mm", "mm", "Tray and floor slot the PSU cable slides into from the rear"),
    ("cable_clip_y", "0 mm", "mm", "Y centre of the snap clip under the top wall"),
    ("cable_clip_length", "6 mm", "mm", "Snap clip length along the cable"),
    ("cable_clip_wall", "1.6 mm", "mm", "Snap clip ring wall thickness"),
    ("cable_clip_opening", "2.8 mm", "mm", "Snap clip opening (narrower than the cable so it snaps in)"),
    ("cable_clamp_y", "17 mm", "mm", "Y centre of the cable clamp on the tray"),
    ("cable_clamp_length", "20 mm", "mm", "Cable clamp bar length across the cable (X)"),
    ("cable_clamp_width", "6 mm", "mm", "Cable clamp bar width along the cable (Y)"),
    ("cable_clamp_thickness", "3 mm", "mm", "Cable clamp bar thickness"),
    ("cable_clamp_screw_dx", "6.5 mm", "mm", "Cable clamp screw X offset either side of the cable"),
    ("cable_clamp_crush", "0.3 mm", "mm", "Gap under the clamp bar at its bosses; tightening the screws squeezes the cable this much"),
]

ELECTRONICS_DERIVED = [
    ("pi_pcb_y", "display_front_y + display_total_depth", "mm", "Y of the Pi 5 board underside"),
    ("pi_center_x", "pi_holes_center_x - (pi_board_length/2 - pi_hole_inset - pi_hole_spacing_x/2)", "mm", "Pi 5 board centre X"),
    ("pi_top_z", "face_center_z + pi_board_width/2", "mm", "Z of the Pi 5 top edge (the USB-C edge)"),
    ("usbc_x", "pi_center_x + pi_board_length/2 - 11.2 mm", "mm", "X of the Pi 5 USB-C port"),
    ("speaker_front_x", "body_width/2 - wall_thickness", "mm", "X of the speaker rim front (seated on the accent ring)"),
    ("speaker_boss_x", "speaker_front_x - speaker_boss_length", "mm", "X of the speaker clamp boss ends"),
    ("amp_top_z", "tray_z + tray_thickness + amp_ledge_height + amp_board_thickness", "mm", "Z of the amplifier board top"),
    ("psu_plug_y", "pi_pcb_y + pi_board_thickness + 1.6 mm", "mm", "Y of the USB-C plug centre"),
    ("psu_plug_top_z", "pi_top_z + 1 mm + usbc_plug_length", "mm", "Z of the USB-C plug top, where the cable leaves it"),
    ("psu_route_top_z", "psu_plug_top_z + 4 mm", "mm", "Z of the PSU cable's top run"),
    ("psu_run_z", "tray_z + tray_thickness + psu_cable_diameter/2", "mm", "Z of the PSU cable axis where it lies on the tray"),
    ("psu_under_z", "psu_cable_diameter/2 + 0.2 mm", "mm", "Z of the PSU cable axis under the body (between the feet)"),
    ("cable_clamp_z", "psu_run_z + psu_cable_diameter/2", "mm", "Z of the cable clamp bar underside (on the cable)"),
]

ALL_PARAMETERS = (PRIMARY_PARAMETERS + SECONDARY_PARAMETERS + FASTENER_PARAMETERS + DERIVED_PARAMETERS
                  + ELECTRONICS_PARAMETERS + ELECTRONICS_DERIVED)
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
    "Button_Retainer",
    # Stage H: electronics mock-ups and the printed parts that hold them
    "Raspberry_Pi_5",
    "USB_Microphone",
    "PSU_Plug",
    "Left_Speaker",
    "Right_Speaker",
    "Left_Speaker_Clamp",
    "Right_Speaker_Clamp",
    "I2S_Amplifier",
    "Amp_Clamp",
    "Tactile_Switch",
    "Cable_Clamp",
]

# Components added by Stage H (created when upgrading an existing design).
ELECTRONICS_COMPONENTS = COMPONENTS[COMPONENTS.index("Raspberry_Pi_5"):]

# Optional, visual only. Never printed, excluded from physical checks.
VISUAL_COMPONENTS = ["Eye_Graphics"]

# Bought parts, modelled as mock-ups (never printed).
PURCHASED_COMPONENTS = [
    "Display_Placeholder", "Raspberry_Pi_5", "USB_Microphone", "PSU_Plug",
    "Left_Speaker", "Right_Speaker", "I2S_Amplifier", "Tactile_Switch",
]

# Components that are 3D printed on the A1 Mini.
PRINTABLE_COMPONENTS = [c for c in COMPONENTS if c not in PURCHASED_COMPONENTS]

# Raspberry Pi 5 mock-up features in board coordinates (mm): u runs along the
# board from the end opposite the USB/Ethernet ports, v runs across the board
# from the USB-C edge. (name, u0, u1, v0, v1, height above the board top)
PI5_FEATURES = [
    ("Pi_USB_C", 6.7, 15.7, -1.0, 6.5, 3.2),
    ("Pi_Micro_HDMI_0", 22.05, 29.55, -1.0, 6.5, 3.5),
    ("Pi_Micro_HDMI_1", 35.45, 42.95, -1.0, 6.5, 3.5),
    ("Pi_Ethernet", 66.0, 87.0, 2.2, 18.2, 13.5),
    ("Pi_USB_Lower", 69.5, 87.0, 22.55, 35.65, 16.0),
    ("Pi_USB_Upper", 69.5, 87.0, 40.45, 53.55, 16.0),
    ("Pi_GPIO_Header", 7.1, 57.9, 50.4, 55.5, 8.5),
]
PI5_COOLER = (1.0, 7.5)       # Active Cooler footprint start (u, v); size from cooler_length/width
PI5_MIC_PORT_V = 47.0         # USB port (v centre) that takes the microphone
PI5_MIC_PORT_LIFT = 4.5       # Lower USB-A port centre above the board top

# Bought fasteners. Inserts are M3 x 5.7 mm long x 4.6 mm OD brass heat-set
# inserts (CNC Kitchen / Ruthex style). Screws are ISO 4762 socket heads.
# (joint, quantity, screw, inserts, where the inserts go)
FASTENERS = [
    ("Rear_Cover to Main_Body", 4, "M3 x 16", 4, "Main_Body rear corner bosses"),
    ("Front_Bezel to Main_Body (top) and Electronics_Tray (bottom)", 4, "M3 x 8", 4, "Front_Bezel back bosses"),
    ("Button_Retainer to Main_Body", 2, "M3 x 8", 2, "Main_Body bosses under the top wall"),
    ("Feet + Electronics_Tray to Main_Body", 4, "M3 x 10", 4, "Electronics_Tray bosses above each foot"),
    ("Speaker clamps to Main_Body", 4, "M3 x 8", 4, "Main_Body side-wall bosses"),
    ("Amp_Clamp to Electronics_Tray", 2, "M3 x 8", 2, "Electronics_Tray amplifier bosses"),
    ("Cable_Clamp to Electronics_Tray", 2, "M3 x 8", 2, "Electronics_Tray cable clamp bosses"),
    ("Raspberry Pi 5 to display", 4, "M2.5 (supplied with the display)", 0, "Display standoffs"),
]

# Parameter edits used by the in-Fusion flex test (and the offline checker).
FLEX_TESTS = [
    ("body_width", "175 mm"),
    ("body_depth", "110 mm"),
    ("corner_radius", "18 mm"),
    ("speaker_diameter", "36 mm"),
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
    # Plate plus the insert bosses on its back, which reach the display back.
    env["Front_Bezel"] = ((-bw, bw), (yb, v["display_front_y"] + v["display_thickness"]), (fcz - bh, fcz + bh))

    dw, dh, yd = v["display_width"] / 2, v["display_height"] / 2, v["display_front_y"]
    # Panel plus the Pi standoffs on its back.
    env["Display_Placeholder"] = ((-dw, dw), (yd, v["pi_pcb_y"]), (fcz - dh, fcz + dh))

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
    # Plate and rails, plus the bezel uprights reaching forward to the display.
    upright_top = fcz - v["display_height"] / 2 + v["bezel_bracket_overlap"]
    env["Electronics_Tray"] = ((-tw, tw), (v["display_back_y"], td), (tz, max(tz + th, upright_top)))

    fr, fx, fy = v["foot_diameter"] / 2, v["foot_x"], v["foot_front_y"]
    ry = 2 * mc - fy
    env["Feet"] = ((-fx - fr, fx + fr), (fy - fr, ry + fr), (0.0, fh))

    rx = v["button_screw_x"] + v["insert_boss_diameter"] / 2 + 2
    ry2 = v["button_switch_size"] / 2 + 2.5
    rz = v["button_retainer_z"]
    env["Button_Retainer"] = ((-rx, rx), (mc - ry2, mc + ry2), (rz - v["button_retainer_thickness"], rz))

    env.update(electronics_envelopes(v))
    return env


def electronics_envelopes(v):
    """Stage H parts (mm, assembly coordinates)."""
    mc, zc = v["module_center_y"], v["body_center_z"]
    env = {}
    L, Wb, tb = v["pi_board_length"], v["pi_board_width"], v["pi_board_thickness"]
    px, py, pz = v["pi_center_x"], v["pi_pcb_y"], v["pi_top_z"]
    port_end = px - L / 2 - 2.0
    env["Raspberry_Pi_5"] = ((port_end, px + L / 2), (py, py + tb + 16.0), (pz - Wb, pz + 1.0))
    my = py + tb + PI5_MIC_PORT_LIFT
    mz = pz - PI5_MIC_PORT_V
    env["USB_Microphone"] = ((port_end - v["mic_length"], port_end), (my - v["mic_thickness"] / 2, my + v["mic_thickness"] / 2),
                             (mz - v["mic_width"] / 2, mz + v["mic_width"] / 2))
    ux, uy = v["usbc_x"], v["psu_plug_y"]
    env["PSU_Plug"] = ((ux - v["usbc_plug_width"] / 2, ux + v["usbc_plug_width"] / 2),
                       (uy - v["usbc_plug_thickness"] / 2, uy + v["usbc_plug_thickness"] / 2),
                       (pz + 1.0, v["psu_plug_top_z"]))
    cx, cl, cw = v["usbc_x"], v["cable_clamp_length"] / 2, v["cable_clamp_width"] / 2
    env["Cable_Clamp"] = ((cx - cl, cx + cl), (v["cable_clamp_y"] - cw, v["cable_clamp_y"] + cw),
                          (v["cable_clamp_z"], v["cable_clamp_z"] + v["cable_clamp_thickness"]))
    sx, rs = v["speaker_front_x"], v["speaker_outer_diameter"] / 2
    rc = v["speaker_outer_diameter"] / 2 + 4.0
    zc_half = max(rc, v["speaker_clamp_dz"] + v["speaker_clamp_width"] / 2)
    xc0 = v["speaker_boss_x"] - v["speaker_clamp_thickness"]
    xc1 = sx - v["speaker_rim_thickness"]
    for side, s in (("Left", -1), ("Right", 1)):
        env[side + "_Speaker"] = (tuple(sorted((s * (sx - v["speaker_depth"]), s * sx))), (mc - rs, mc + rs), (zc - rs, zc + rs))
        env[side + "_Speaker_Clamp"] = (tuple(sorted((s * xc0, s * xc1))), (mc - rc, mc + rc), (zc - zc_half, zc + zc_half))
    aw, ad, at, ay = v["amp_board_width"] / 2, v["amp_board_depth"] / 2, v["amp_top_z"], v["amp_center_y"]
    env["I2S_Amplifier"] = ((-aw, aw), (ay - ad, ay + ad), (at - v["amp_board_thickness"], at + v["amp_part_height"]))
    cx = v["amp_screw_x"] + v["insert_boss_diameter"] / 2 + 2
    env["Amp_Clamp"] = ((-cx, cx), (ay - 5.0, ay + 5.0), (at, at + v["amp_clamp_thickness"]))
    sw, rz = v["button_switch_size"] / 2, v["button_retainer_z"]
    leg = v["button_switch_leg_pitch_x"] / 2 + 0.4
    base = rz - v["button_switch_pocket_depth"]
    env["Tactile_Switch"] = ((-leg, leg), (mc - sw, mc + sw), (base - 3.5, base + v["button_switch_total_height"]))
    return env


def psu_cable_runs(v):
    """Straight runs of the PSU cable as boxes (mm), keyed by name.

    The route lies in the plane X = usbc_x: up out of the plug, back along
    the top, down behind the Pi, along the tray under the clamp, down through
    the tray and floor slot, and back out under the rear cover.
    """
    x, r = v["usbc_x"], v["psu_cable_diameter"] / 2
    xs = (x - r, x + r)
    y0, y1, y2 = v["psu_plug_y"], v["psu_route_y"], v["psu_exit_y"]
    z_top, z_run, z_under = v["psu_route_top_z"], v["psu_run_z"], v["psu_under_z"]
    return {
        "top run": (xs, (y0 - r, y1 + r), (z_top - r, z_top + r)),
        "drop behind the Pi": (xs, (y1 - r, y1 + r), (z_run - r, z_top + r)),
        "tray run": (xs, (y1 - r, y2 + r), (z_run - r, z_run + r)),
        "floor exit": (xs, (y2 - r, y2 + r), (z_under - r, z_run + r)),
        "under the body": (xs, (y2 - r, v["body_depth"] / 2 + 15.0), (z_under - r, z_under + r)),
    }


def boxes_overlap(a, b, gap=0.0):
    """True if two axis-aligned boxes overlap (or come closer than `gap`)."""
    return all(a[i][0] < b[i][1] + gap and b[i][0] < a[i][1] + gap for i in range(3))


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
    win_w = v["display_window_width"] / 2
    win_h = v["display_window_height"] / 2
    check("Bezel window inside the display outline",
          win_w < v["display_width"] / 2 and win_h < v["display_height"] / 2,
          "window %.1f x %.1f, display %.1f x %.1f" % (2 * win_w, 2 * win_h, v["display_width"], v["display_height"]))
    check("Bezel window shows the whole active area (110.4 x 62.1)", 2 * win_w >= 110.4 and 2 * win_h >= 62.1,
          "window %.1f x %.1f" % (2 * win_w, 2 * win_h))
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
    tray_plate = ((-v["tray_width"] / 2, v["tray_width"] / 2), (-v["tray_depth"] / 2, v["tray_depth"] / 2),
                  (v["tray_z"], v["tray_z"] + v["tray_thickness"] + max(v["tray_rail_height"], v["standoff_height"])))
    check("Electronics tray inside the cavity", box_inside_cavity(v, tray_plate, tol=1e-3),
          "margin %.2f mm" % cavity_margin(v, tray_plate))

    # Rails / side tabs / speaker rings must not collide inside the body
    side_tab_inner_x = W / 2 - t - c - v["lip_thickness"]
    check("Tray rails clear of rear cover side tabs",
          v["tray_width"] / 2 < side_tab_inner_x or tray_plate[2][1] < zc - (H / 2 - R - 2),
          "tray top Z %.1f, side tabs start at Z %.1f" % (tray_plate[2][1], zc - (H / 2 - R - 2)))

    out.extend(fastener_checks(v, env, check_fn=check))
    out.extend(electronics_checks(v, env, check_fn=check))

    # Printability
    for name in PRINTABLE_COMPONENTS:
        size = box_size(env[name])
        check("Fits A1 Mini: %s" % name, fits_build_volume(size),
              "%.1f x %.1f x %.1f mm" % size)
    return out


def _distance_to_diagonal(px, pz, cx, cz):
    """Distance from (px, pz) to the 45 degree line through (cx, cz) heading outwards (+X, +Z)."""
    return abs((px - cx) - (pz - cz)) / math.sqrt(2)


def fastener_checks(v, env, check_fn):
    """Design rules for the screw bosses, inserts and retainers.

    `check_fn(name, ok, detail, warn_only=False)` records each result; this
    returns an empty list so it can be used with list.extend().
    """
    check = check_fn
    W, H = v["body_width"], v["body_height"]
    t, R, c = v["wall_thickness"], v["corner_radius"], v["assembly_clearance"]
    zc, top = v["body_center_z"], v["body_top_z"]
    hole, depth, boss = v["insert_hole_diameter"], v["insert_depth"], v["insert_boss_diameter"]
    head, clear = v["screw_head_clearance_diameter"], v["screw_clearance_diameter"]

    check("Insert boss wall", (boss - hole) / 2 >= 1.5, "%.2f mm around the insert" % ((boss - hole) / 2))
    check("Screw clearance smaller than insert hole", clear < hole, "clearance %.1f, insert hole %.1f" % (clear, hole))

    # Rear cover screws
    rx, rdz, rb = v["rear_screw_x"], v["rear_screw_dz"], v["rear_boss_diameter"]
    check("Rear counterbores on the flat rear face",
          rx + head / 2 <= W / 2 - R and rdz + head / 2 <= H / 2 - R,
          "counterbore reaches X %.1f Z +/-%.1f, flat face X %.1f Z +/-%.1f" % (rx + head / 2, rdz + head / 2, W / 2 - R, H / 2 - R))
    check("Rear boss wall around the counterbore", (rb - head) / 2 >= 1.2, "%.2f mm" % ((rb - head) / 2), warn_only=True)
    check("Rear main body boss holds the insert", v["rear_boss_length"] >= depth + 1,
          "boss %.1f mm, insert hole %.1f mm" % (v["rear_boss_length"], depth))
    tab_len_x, tab_len_z = W / 2 - R - 2, H / 2 - R - 2
    top_tab_bottom = H / 2 - t - c - v["lip_thickness"]
    side_tab_inner = W / 2 - t - c - v["lip_thickness"]
    check("Rear bosses clear of the top tab", rx - rb / 2 > tab_len_x or rdz + rb / 2 < top_tab_bottom,
          "boss top Z +%.1f, tab underside Z +%.1f" % (rdz + rb / 2, top_tab_bottom))
    check("Rear bosses clear of the side tabs", rdz - rb / 2 > tab_len_z or rx + rb / 2 < side_tab_inner,
          "boss outer X %.1f, tab inner X %.1f" % (rx + rb / 2, side_tab_inner))
    screw_len = v["rear_cover_depth"] - v["rear_counterbore_depth"] + depth - 1
    check("Rear screw length", 12 <= screw_len <= 20, "M3 x %.0f needed (rear cover %.1f, counterbore %.1f)" % (
        screw_len, v["rear_cover_depth"], v["rear_counterbore_depth"]), warn_only=True)

    # Bezel screws
    bx, bdz = v["bezel_screw_x"], v["bezel_screw_dz"]
    check("Bezel bosses clear of the display (above and below it)", bdz - boss / 2 >= v["display_height"] / 2 + c,
          "boss inner Z +%.2f, display edge +%.2f" % (bdz - boss / 2, v["display_height"] / 2))
    check("Bezel bosses inside the bezel outline (X)", bx + boss / 2 <= v["face_width"] / 2 - v["face_corner_radius"]
          or math.hypot(bx + boss / 2 - (v["face_width"] / 2 - v["face_corner_radius"]),
                        bdz + boss / 2 - (v["face_height"] / 2 - v["face_corner_radius"])) <= v["face_corner_radius"] - c,
          "boss outer X %.1f, straight bezel edge to %.1f" % (bx + boss / 2, v["face_width"] / 2 - v["face_corner_radius"]))
    check("Bezel bosses inside the bezel outline (Z)", bdz + boss / 2 <= v["face_height"] / 2 - c,
          "boss top Z +%.2f, bezel edge +%.2f" % (bdz + boss / 2, v["face_height"] / 2 - c))
    yb = v["display_front_y"]
    ybk = yb + v["display_thickness"]
    boss_box = ((bx - boss / 2, bx + boss / 2), (yb, ybk), (zc + bdz - boss / 2, zc + bdz + boss / 2))
    check("Bezel bosses inside the cavity", box_inside_cavity(v, boss_box), "margin %.2f mm" % cavity_margin(v, boss_box))
    check("Bezel insert leaves a front skin", v["bezel_thickness"] + v["display_thickness"] - depth >= 1.5,
          "%.1f mm" % (v["bezel_thickness"] + v["display_thickness"] - depth))
    check("Bezel side shelves clear of the speaker holes",
          bdz - v["bezel_bracket_width"] / 2 >= v["speaker_hole_diameter"] / 2 + 1,
          "shelf from Z +%.1f, speaker hole to +%.1f" % (bdz - v["bezel_bracket_width"] / 2, v["speaker_hole_diameter"] / 2))
    check("Bezel brackets overlap the display edge", v["bezel_bracket_overlap"] >= 2 and
          bdz - head / 2 > v["display_height"] / 2 - v["bezel_bracket_overlap"],
          "overlap %.1f mm, screw head from Z +%.1f" % (v["bezel_bracket_overlap"], bdz - head / 2))
    yA = -v["tray_depth"] / 2 + 1.0
    check("Tray bezel uprights clear of the tray bosses",
          yA <= v["foot_front_y"] - boss / 2 - 1 or abs(bx - v["foot_x"]) >= boss + 12,
          "upright back Y %.1f, front boss from Y %.1f" % (yA, v["foot_front_y"] - boss / 2))
    upright_bottom = v["tray_z"] + (yA - v["display_back_y"])
    check("Tray bezel uprights reach the lower screw",
          upright_bottom + head / 2 <= zc - bdz <= zc - v["display_height"] / 2 + v["bezel_bracket_overlap"] - clear / 2,
          "upright Z %.1f..%.1f, screw Z %.1f" % (upright_bottom, zc - v["display_height"] / 2 + v["bezel_bracket_overlap"], zc - bdz))
    access = min(_distance_to_diagonal(bx, bdz, rx, rdz), math.hypot(bx - rx, bdz - rdz))
    check("Bezel screw access clear of the rear bosses", access >= rb / 2 + head / 2 + 0.5,
          "%.1f mm from the rear boss web" % access, warn_only=True)

    # Button retainer
    rbtn = v["button_diameter"] / 2 + v["button_flange_width"]
    bsx = v["button_screw_x"]
    check("Button bosses clear of the flange", bsx - boss / 2 >= rbtn + 1, "gap %.1f mm" % (bsx - boss / 2 - rbtn))
    check("Button bosses under the flat top", bsx + boss / 2 + 2 <= W / 2 - R, "retainer reaches X %.1f" % (bsx + boss / 2 + 2))
    check("Button boss holds the insert", top - t - v["button_retainer_z"] >= depth - 0.01,
          "boss %.1f mm" % (top - t - v["button_retainer_z"]))
    ret_front = v["module_center_y"] - v["button_switch_size"] / 2 - 2.5
    check("Button retainer behind the display brackets", ret_front > v["display_back_y"] + v["bezel_bracket_thickness"],
          "retainer front Y %.1f, bracket back Y %.1f" % (ret_front, v["display_back_y"] + v["bezel_bracket_thickness"]))

    # Feet and tray
    fx = v["foot_x"]
    check("Tray bosses inside the rails", fx + boss / 2 <= v["tray_width"] / 2 - v["tray_rail_width"],
          "boss outer X %.1f, rail inner X %.1f" % (fx + boss / 2, v["tray_width"] / 2 - v["tray_rail_width"]))
    edge = max(abs(v["foot_front_y"]), abs(v["foot_rear_y"])) + boss / 2
    check("Tray bosses on the tray", edge <= v["tray_depth"] / 2, "boss Y %.1f, tray half depth %.1f" % (edge, v["tray_depth"] / 2))
    check("Tray insert leaves a top skin", v["tray_thickness"] + v["standoff_height"] - depth >= 1.0,
          "%.1f mm" % (v["tray_thickness"] + v["standoff_height"] - depth))
    check("Foot counterbore leaves a foot", v["foot_height"] - v["foot_counterbore_depth"] >= 2.0,
          "%.1f mm under the head" % (v["foot_height"] - v["foot_counterbore_depth"]))
    return []


def electronics_checks(v, env, check_fn):
    """Design rules for the Stage H electronics and their mounts."""
    check = check_fn
    t, R = v["wall_thickness"], v["corner_radius"]
    H = v["body_height"]
    top, mc = v["body_top_z"], v["module_center_y"]
    boss, depth = v["insert_boss_diameter"], v["insert_depth"]

    for name in ("Display_Placeholder", "Raspberry_Pi_5", "USB_Microphone", "PSU_Plug", "Left_Speaker", "Right_Speaker",
                 "Left_Speaker_Clamp", "Right_Speaker_Clamp", "I2S_Amplifier", "Amp_Clamp", "Tactile_Switch", "Cable_Clamp"):
        check("%s inside the cavity" % name, box_inside_cavity(v, env[name]), "margin %.2f mm" % cavity_margin(v, env[name]))
    plug = env["PSU_Plug"]

    pairs = [
        ("Raspberry_Pi_5", "Left_Speaker"), ("Raspberry_Pi_5", "Right_Speaker"),
        ("USB_Microphone", "Left_Speaker"), ("USB_Microphone", "Left_Speaker_Clamp"),
        ("Raspberry_Pi_5", "Electronics_Tray"), ("PSU_Plug", "Button_Retainer"), ("PSU_Plug", "Tactile_Switch"),
        ("I2S_Amplifier", "Raspberry_Pi_5"), ("Left_Speaker_Clamp", "Raspberry_Pi_5"),
    ]
    boxes = env
    for a, b in pairs:
        hit = boxes_overlap(boxes[a], boxes[b])
        check("%s clear of %s" % (a, b), not hit, "envelopes overlap" if hit else "clear")
    gap = v["usbc_x"] - v["psu_cable_diameter"] / 2 - env["Button_Retainer"][0][1]
    check("PSU cable clear of the button retainer", gap >= 1.0, "%.1f mm" % gap)
    gap = (v["speaker_front_x"] - v["speaker_depth"]) - abs(env["USB_Microphone"][0][0])
    check("Microphone clear of the speaker magnet", gap >= 1.0, "%.1f mm" % gap)

    # Display brackets (top in Main_Body, bottom on the tray) against the Pi and plug
    z_tip_top = v["face_center_z"] + v["display_height"] / 2 - v["bezel_bracket_overlap"]
    bx, bw = v["bezel_screw_x"], v["bezel_bracket_width"] / 2
    check("Top bezel brackets clear of the PSU plug", bx - bw > plug[0][1] + 1 or z_tip_top > plug[2][1],
          "bracket from X %.1f, plug to X %.1f" % (bx - bw, plug[0][1]))
    check("Top bezel brackets above the Pi", z_tip_top > env["Raspberry_Pi_5"][2][1],
          "bracket tip Z %.1f, Pi top Z %.1f" % (z_tip_top, env["Raspberry_Pi_5"][2][1]))

    # Speaker clamps
    dz, rh = v["speaker_clamp_dz"], v["speaker_hole_diameter"] / 2
    check("Speaker clamp bosses on the flat side wall", dz + boss / 2 <= H / 2 - R and abs(mc) + boss / 2 <= v["body_depth"] / 2 - R,
          "boss reaches Z +/-%.1f, flat +/-%.1f" % (dz + boss / 2, H / 2 - R))
    check("Speaker clamp bosses clear of the speaker hole", dz - boss / 2 >= rh + 1, "boss from %.1f, hole radius %.1f" % (dz - boss / 2, rh))
    check("Speaker clamp boss holds the insert", v["speaker_boss_length"] + t - depth >= 1.0,
          "%.1f mm of wall behind the insert" % (v["speaker_boss_length"] + t - depth))
    collar_id = v["speaker_outer_diameter"] - 3.0
    check("Speaker clamp presses the speaker rim", collar_id < v["speaker_outer_diameter"] - 2 and collar_id > v["speaker_magnet_diameter"] + 2,
          "collar bore %.1f, speaker %.1f, magnet %.1f" % (collar_id, v["speaker_outer_diameter"], v["speaker_magnet_diameter"]))
    seat = v["speaker_diameter"] / 2 - v["grille_step_width"]
    check("Speaker rim seats on the accent ring", v["speaker_outer_diameter"] / 2 - seat >= 1.5,
          "%.1f mm of rim on the ring step" % (v["speaker_outer_diameter"] / 2 - seat))
    check("Speaker clear of the side-wall hole edge", v["speaker_outer_diameter"] / 2 <= v["speaker_hole_diameter"] / 2 - v["assembly_clearance"],
          "speaker radius %.1f, ring tube outer %.1f" % (v["speaker_outer_diameter"] / 2, v["speaker_hole_diameter"] / 2))

    # Amplifier cradle and clamp
    ledge_top = v["tray_thickness"] + v["amp_ledge_height"] + v["amp_board_thickness"]
    check("Amplifier clamp boss holds the insert", ledge_top - depth >= 1.0, "%.1f mm under the insert" % (ledge_top - depth))
    cradle_x = v["amp_board_width"] / 2 + v["assembly_clearance"] + v["amp_cradle_wall"]
    check("Amplifier clamp bosses clear of the cradle", v["amp_screw_x"] - boss / 2 >= cradle_x, "boss from X %.1f, cradle to %.1f" % (
        v["amp_screw_x"] - boss / 2, cradle_x))
    check("Amplifier clamp on the tray, clear of the tray bosses",
          v["amp_screw_x"] + boss / 2 + 2 < v["foot_x"] - boss / 2 and env["Amp_Clamp"][1][1] < v["tray_depth"] / 2,
          "clamp to X %.1f, tray boss from X %.1f" % (v["amp_screw_x"] + boss / 2 + 2, v["foot_x"] - boss / 2))

    # PSU cable route, floor exit and retention
    cr, bend = v["psu_cable_diameter"] / 2, v["cable_bend_radius"]
    runs = psu_cable_runs(v)
    for name in ("top run", "drop behind the Pi", "tray run"):
        check("PSU cable %s inside the cavity" % name, box_inside_cavity(v, runs[name]),
              "margin %.2f mm" % cavity_margin(v, runs[name]))
        for part in ("Raspberry_Pi_5", "Button_Retainer", "Tactile_Switch", "I2S_Amplifier", "Amp_Clamp",
                     "Left_Speaker_Clamp", "Right_Speaker_Clamp", "USB_Microphone"):
            hit = boxes_overlap(runs[name], env[part])
            check("PSU cable %s clear of %s" % (name, part), not hit, "envelopes overlap" if hit else "clear")
    check("PSU cable under the top wall", v["psu_route_top_z"] + cr <= top - t - 0.5,
          "cable top Z %.1f, inner top %.1f" % (v["psu_route_top_z"] + cr, top - t))
    tabs_from = v["split_y"] - 6.0
    check("PSU cable in front of the rear cover tabs", v["psu_route_y"] + cr <= tabs_from - 1.0,
          "cable to Y %.1f, tabs from Y %.1f" % (v["psu_route_y"] + cr, tabs_from))
    check("PSU cable leaves through the Main_Body floor, not the rear cover",
          v["psu_exit_y"] + cr <= v["split_y"] - 1.0 and v["psu_exit_y"] < v["tray_depth"] / 2,
          "cable Y to %.1f, split Y %.1f (the slot runs out to the split edge)" % (v["psu_exit_y"] + cr, v["split_y"]))
    check("Cable slot passes the cable", v["cable_slot_width"] >= v["psu_cable_diameter"] + 0.5,
          "slot %.1f, cable %.1f" % (v["cable_slot_width"], v["psu_cable_diameter"]))
    check("PSU cable fits under the body between the feet", v["psu_under_z"] + cr <= v["foot_height"] - 1.0,
          "cable top Z %.1f, floor underside Z %.1f" % (v["psu_under_z"] + cr, v["foot_height"]))
    gap = abs(v["foot_x"] - abs(v["usbc_x"])) - boss / 2 - v["cable_slot_width"] / 2
    check("Cable slot clear of the foot bosses", gap >= 1.0, "%.1f mm" % gap)
    straight = (v["psu_route_y"] + bend, v["psu_exit_y"] - bend)
    cw = v["cable_clamp_width"] / 2
    check("Cable clamp on the straight tray run", straight[0] <= v["cable_clamp_y"] - cw and v["cable_clamp_y"] + cw <= straight[1],
          "clamp Y %.1f..%.1f, straight Y %.1f..%.1f" % (v["cable_clamp_y"] - cw, v["cable_clamp_y"] + cw, straight[0], straight[1]))
    boss_h = v["tray_thickness"] + v["cable_clamp_z"] - v["cable_clamp_crush"] - (v["tray_z"] + v["tray_thickness"])
    check("Cable clamp boss holds the insert", boss_h >= 5.7 - 1e-6, "%.1f mm of tray and boss for a 5.7 mm insert" % boss_h)
    gap = v["cable_clamp_screw_dx"] - boss / 2 - cr
    check("Cable clamp bosses clear of the cable", gap >= 0.5, "%.1f mm" % gap)
    hole_edge = v["cable_clamp_screw_dx"] + v["screw_clearance_diameter"] / 2 + 1.2
    check("Cable clamp bar holds its screws", v["cable_clamp_length"] / 2 >= hole_edge,
          "bar half length %.1f, screw hole edge + 1.2 mm %.1f" % (v["cable_clamp_length"] / 2, hole_edge))
    hit = boxes_overlap(env["Cable_Clamp"], env["Amp_Clamp"])
    check("Cable clamp clear of the amplifier clamp", not hit, "envelopes overlap" if hit else "clear")
    gap = math.hypot(v["usbc_x"] - v["cable_clamp_screw_dx"] - v["amp_screw_x"], v["cable_clamp_y"] - v["amp_center_y"]) - boss
    check("Cable clamp bosses clear of the amplifier bosses", gap >= 0.5, "%.1f mm" % gap)
    gap = v["usbc_x"] - cr - v["cable_clip_wall"] - env["Button_Retainer"][0][1]
    check("Cable clip clear of the button retainer", gap >= 1.0, "%.1f mm" % gap)
    cl = v["cable_clip_length"] / 2
    check("Cable clip on the straight top run", v["psu_plug_y"] + bend <= v["cable_clip_y"] - cl and v["cable_clip_y"] + cl <= v["psu_route_y"] - bend,
          "clip Y %.1f..%.1f" % (v["cable_clip_y"] - cl, v["cable_clip_y"] + cl))
    check("Cable clip snaps over the cable", v["cable_clip_opening"] < v["psu_cable_diameter"] - 0.4,
          "opening %.1f, cable %.1f" % (v["cable_clip_opening"], v["psu_cable_diameter"]))

    # Top button switch
    wall = v["button_switch_size"] / 2 + 2.5 - (v["button_switch_size"] / 2 + 1.0)
    check("Switch pocket leaves a retainer wall", wall >= 1.2, "%.1f mm" % wall)
    check("Switch legs land in the pocket", v["button_switch_leg_pitch_x"] / 2 + v["button_switch_leg_hole"] / 2 <= v["button_switch_size"] / 2 + 1.0,
          "legs at +/-%.2f" % (v["button_switch_leg_pitch_x"] / 2))
    check("Switch pocket leaves a retainer floor", v["button_retainer_thickness"] - v["button_switch_pocket_depth"] >= 1.2,
          "%.1f mm" % (v["button_retainer_thickness"] - v["button_switch_pocket_depth"]))
    check("Switch plunger meets the button flange", abs(v["button_retainer_z"] + v["button_switch_height"]
                                                        - (top - t - v["button_travel"] - v["button_flange_thickness"])) < 1e-6,
          "plunger top Z %.2f" % (v["button_retainer_z"] + v["button_switch_height"]))
    return []
