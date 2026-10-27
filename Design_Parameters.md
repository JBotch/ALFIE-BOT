# AlfieBot V0.1: design parameters

All values are **provisional**. The parameters are created as Fusion
**user parameters** (Modify > Change Parameters) and drive every sketch
dimension, construction plane offset and feature in the model. The source
of truth is `alfiebot_parameters.py`: edit it to change the defaults for
new builds, or edit the parameters in Fusion to change an existing design.

Units: lengths are in mm. Counts are unitless. Fusion stores lengths in cm
internally, and the script passes every size to Fusion as an expression string, so Fusion handles the conversion.

## Coordinate system

| Axis | Meaning | Reference |
|---|---|---|
| X | Width, left (−X) to right (+X) | Body centred on X = 0 |
| Y | Depth, front (−Y) to rear (+Y) | Body centred on Y = 0. Front face at Y = −body_depth/2 |
| Z | Height, bottom to top | Z = 0 is the underside of the feet. The enclosure starts at Z = foot_height |

All component origins coincide with the assembly origin (identity transforms).

## 1. Primary parameters (from the V0.1 brief)

| Parameter | Expression | Value | Unit | Purpose |
|---|---|---|---|---|
| `body_width` | `160 mm` | 160 | mm | Enclosure width along X |
| `body_height` | `130 mm` | 130 | mm | Enclosure height along Z (excludes feet and button) |
| `body_depth` | `100 mm` | 100 | mm | Enclosure depth along Y (front face to rear cover) |
| `wall_thickness` | `3 mm` | 3 | mm | Enclosure wall thickness |
| `corner_radius` | `22 mm` | 22 | mm | Outer fillet radius on all enclosure edges |
| `face_width` | `140 mm` | 140 | mm | Front face opening width |
| `face_height` | `95 mm` | 95 | mm | Front face opening height |
| `speaker_diameter` | `42 mm` | 42 | mm | Speaker grille diameter |
| `button_diameter` | `22 mm` | 22 | mm | Top button cap diameter |
| `foot_height` | `6 mm` | 6 | mm | Foot height; enclosure underside sits at Z = foot_height |
| `assembly_clearance` | `0.3 mm` | 0.3 | mm | Clearance between mating printed parts |

## 2. Secondary parameters (independent, added to define V0.1 fully)

| Parameter | Expression | Value | Unit | Purpose |
|---|---|---|---|---|
| `face_corner_radius` | `14 mm` | 14 | mm | Corner radius of the front face opening |
| `bezel_thickness` | `3 mm` | 3 | mm | Front bezel plate thickness (Y) |
| `display_width` | `121 mm` | 121 | mm | Display module outline width (placeholder, verify against real display) |
| `display_height` | `76 mm` | 76 | mm | Display module outline height (placeholder, verify against real display) |
| `display_thickness` | `5 mm` | 5 | mm | Display module thickness (placeholder) |
| `display_overlap` | `3 mm` | 3 | mm | Bezel overlap over each display edge |
| `display_window_radius` | `3 mm` | 3 | mm | Corner radius of the bezel display window |
| `accent_ring_width` | `3 mm` | 3 | mm | Radial width of the accent ring tube |
| `accent_ring_lip` | `1.5 mm` | 1.5 | mm | Radial overhang of the accent ring lip on the side face |
| `accent_ring_protrusion` | `1.5 mm` | 1.5 | mm | How far the accent ring stands proud of the side face |
| `grille_step` | `1 mm` | 1 | mm | Axial thickness of the ring's inner step that seats the grille |
| `grille_step_width` | `1.5 mm` | 1.5 | mm | Radial width of the ring's inner step |
| `grille_hole_diameter` | `2.5 mm` | 2.5 | mm | Speaker grille hole diameter |
| `grille_ring1_count` | `6` | 6 | – | Holes in grille ring 1 |
| `grille_ring2_count` | `12` | 12 | – | Holes in grille ring 2 |
| `grille_ring3_count` | `18` | 18 | – | Holes in grille ring 3 |
| `button_height` | `5 mm` | 5 | mm | Button rise above the enclosure top |
| `button_travel` | `1 mm` | 1 | mm | Gap between button flange and the inside of the top wall |
| `button_flange_width` | `3 mm` | 3 | mm | Radial width of the button retaining flange |
| `button_flange_thickness` | `1.5 mm` | 1.5 | mm | Thickness of the button retaining flange |
| `button_top_fillet` | `1 mm` | 1 | mm | Fillet on the button cap top edge |
| `button_accent_depth` | `1 mm` | 1 | mm | Depth of the blue accent inlay in the button cap |
| `foot_diameter` | `14 mm` | 14 | mm | Foot diameter |
| `foot_fillet` | `2 mm` | 2 | mm | Fillet on the foot bottom edge |
| `foot_inset` | `1 mm` | 1 | mm | Gap between foot edge and the start of the enclosure fillet |
| `lip_depth` | `6 mm` | 6 | mm | How far the rear cover locating tabs reach into the main body |
| `lip_thickness` | `2 mm` | 2 | mm | Rear cover locating tab thickness |
| `lip_bridge_depth` | `3 mm` | 3 | mm | Length of the tab root that fuses into the rear cover wall |
| `rear_vent_count` | `7` | 7 | – | Number of rear cover vent slots |
| `rear_vent_spacing` | `8 mm` | 8 | mm | Rear vent slot pitch along X |
| `rear_vent_width` | `3 mm` | 3 | mm | Rear vent slot width (X) |
| `rear_vent_length` | `24 mm` | 24 | mm | Rear vent slot length (Z) |
| `tray_thickness` | `2.5 mm` | 2.5 | mm | Electronics tray plate thickness |
| `tray_rail_height` | `8 mm` | 8 | mm | Height of the tray side rails |
| `tray_rail_width` | `2 mm` | 2 | mm | Width of the tray side rails |
| `standoff_diameter` | `6 mm` | 6 | mm | Board standoff outer diameter |
| `standoff_hole_diameter` | `2.5 mm` | 2.5 | mm | Board standoff pilot hole (M2.5) |
| `standoff_height` | `5 mm` | 5 | mm | Board standoff height above the tray |
| `pi_hole_spacing_x` | `58 mm` | 58 | mm | Raspberry Pi 5 mounting hole pitch, long side |
| `pi_hole_spacing_y` | `49 mm` | 49 | mm | Raspberry Pi 5 mounting hole pitch, short side |
| `eye_diameter` | `30 mm` | 30 | mm | Eye graphic outer diameter (visual only) |
| `eye_spacing` | `52 mm` | 52 | mm | Eye graphic centre-to-centre spacing (visual only) |
| `eye_offset_z` | `6 mm` | 6 | mm | Eye graphic height above the face centre (visual only) |
| `eye_graphic_thickness` | `0.2 mm` | 0.2 | mm | Eye graphic thickness (visual only) |

## 2b. Fastening parameters (M3 screws and heat-set inserts)

| Parameter | Expression | Value | Unit | Purpose |
|---|---|---|---|---|
| `insert_hole_diameter` | `4 mm` | 4 | mm | Hole for an M3 heat-set insert (M3 x 5.7 x 4.6 type; check the insert datasheet) |
| `insert_depth` | `6 mm` | 6 | mm | Depth of every heat-set insert hole |
| `insert_boss_diameter` | `8 mm` | 8 | mm | Outer diameter of insert bosses |
| `screw_clearance_diameter` | `3.4 mm` | 3.4 | mm | M3 screw clearance hole |
| `screw_head_clearance_diameter` | `6.2 mm` | 6.2 | mm | Counterbore and driver access for an M3 socket head (5.5 mm) |
| `rear_screw_inset` | `6 mm` | 6 | mm | Rear screw inset from where the rear edge fillets start |
| `rear_boss_diameter` | `9 mm` | 9 | mm | Rear cover screw boss diameter (holds the counterbore) |
| `rear_boss_length` | `14 mm` | 14 | mm | Main_Body rear insert boss length in front of the split plane |
| `rear_counterbore_depth` | `13 mm` | 13 | mm | Screw head counterbore depth from the rear face |
| `bezel_screw_edge` | `5 mm` | 5 | mm | Bezel screw centre inset from the bezel side edge |
| `bezel_screw_dz` | `32 mm` | 32 | mm | Bezel screw Z offset above and below the face centre |
| `bezel_bracket_thickness` | `4 mm` | 4 | mm | Main_Body bezel bracket thickness (Y) |
| `bezel_bracket_width` | `12 mm` | 12 | mm | Main_Body bezel bracket width (Z) |
| `bezel_bracket_overlap` | `4 mm` | 4 | mm | How far the bezel brackets reach over the display back edge |
| `button_switch_height` | `3.5 mm` | 3.5 | mm | Tactile switch height between the retainer and the button flange (6 x 6 mm switch) |
| `button_screw_offset` | `6 mm` | 6 | mm | Gap from the button flange edge to the retainer screw centre |
| `button_retainer_thickness` | `2.5 mm` | 2.5 | mm | Button retainer plate thickness |
| `foot_counterbore_depth` | `3.5 mm` | 3.5 | mm | Screw head counterbore depth in each foot |

## 3. Derived parameters (expressions of other parameters)

Change these only to change the design intent. Normally you edit the
primary or secondary values and these follow.

| Parameter | Expression | Value | Unit | Purpose |
|---|---|---|---|---|
| `rear_cover_depth` | `corner_radius + 2 mm` | 24 | mm | Rear cover depth; must exceed corner_radius so the split is in the straight section |
| `split_y` | `body_depth/2 - rear_cover_depth` | 26 | mm | Y position of the main body / rear cover split plane |
| `module_center_y` | `(corner_radius - rear_cover_depth)/2` | -1 | mm | Y centre of the flat side/top region in front of the split |
| `body_center_z` | `foot_height + body_height/2` | 71 | mm | Z centre of the enclosure |
| `body_top_z` | `foot_height + body_height` | 136 | mm | Z of the enclosure top surface |
| `face_center_z` | `body_center_z` | 71 | mm | Z centre of the front face |
| `face_recess` | `wall_thickness + 1 mm` | 4 | mm | Depth of the bezel front surface behind the front plane |
| `display_front_y` | `-body_depth/2 + face_recess + bezel_thickness` | -43 | mm | Y of the display front surface |
| `speaker_hole_diameter` | `speaker_diameter + 2*accent_ring_width` | 48 | mm | Side wall hole for the accent ring |
| `foot_x` | `body_width/2 - corner_radius - foot_diameter/2 - foot_inset` | 50 | mm | Foot centre X offset |
| `foot_front_y` | `-(body_depth/2 - corner_radius) + foot_diameter/2 + foot_inset` | -20 | mm | Front foot centre Y |
| `tray_z` | `foot_height + wall_thickness` | 9 | mm | Z of the tray underside (inner floor) |
| `tray_width` | `body_width - 2*corner_radius - 2*assembly_clearance` | 115.4 | mm | Tray width (fits the flat floor) |
| `tray_depth` | `body_depth - 2*corner_radius - 2*assembly_clearance` | 55.4 | mm | Tray depth (fits the flat floor) |
| `foot_rear_y` | `2*module_center_y - foot_front_y` | 18 | mm | Rear foot centre Y (mirror of the front feet) |
| `rear_screw_x` | `body_width/2 - corner_radius - rear_screw_inset` | 52 | mm | Rear cover screw X offset |
| `rear_screw_dz` | `body_height/2 - corner_radius - rear_screw_inset` | 37 | mm | Rear cover screw Z offset from the body centre |
| `bezel_screw_x` | `face_width/2 - bezel_screw_edge` | 65 | mm | Bezel screw X offset |
| `button_screw_x` | `button_diameter/2 + button_flange_width + button_screw_offset` | 20 | mm | Button retainer screw X offset |
| `button_retainer_z` | `body_top_z - wall_thickness - button_travel - button_flange_thickness - button_switch_height` | 127 | mm | Z of the button retainer top face |

## Fixed ratios in the script

These are written into the feature expressions as multiples of a parameter, so they still scale with it:

| Feature | Expression |
|---|---|
| Grille hole ring radii | `speaker_diameter*0.14`, `*0.27`, `*0.40` |
| Button accent inlay | inner `button_diameter*0.6`, outer `button_diameter*0.8` |
| Eye graphic pupil / highlight | `eye_diameter*0.55`, highlight `eye_diameter*0.17` offset by `eye_diameter*0.1` |
| Rear cover tab length | `body_width/2 - corner_radius - 2 mm` (X), `body_height/2 - corner_radius - 2 mm` (Z) |

## Editing safely

Some combinations don't fit. For example, a large `corner_radius` shrinks
the flat side area that the speaker ring needs. Check a change before
making it in Fusion:

```bash
python offline_layout_check.py --set corner_radius="26 mm"
```

The checker evaluates the same expressions and reports which rule breaks.
The rules include ring-on-flat-face, parts inside the cavity, FDM wall
thickness and A1 Mini fit. The Fusion script runs the same rules against
the live parameter values when it validates.

Edits the in-Fusion flex test makes (one at a time, then restored):
- `body_width` → `175 mm`
- `body_depth` → `110 mm`
- `corner_radius` → `18 mm`
- `speaker_diameter` → `38 mm`
- `face_width` → `130 mm`

With the fastenings added, `face_width = 130 mm` fails one offline rule:
the bezel border beside the 121 mm display becomes too narrow for the 8 mm
bezel insert bosses. A narrower face needs a smaller display or smaller
bosses. `body_width = 175 mm` gives a WARN: the bezel screw path passes
close to the rear corner web. The rest pass. Whether the Fusion timeline
recomputes cleanly with them still needs to be confirmed by running the script.

## Constraints between parameters

- `rear_cover_depth` > `corner_radius`: the split plane must sit in the straight part of the walls.
- `face_width/2` ≤ `body_width/2 − wall_thickness − 2 mm`: the face opening must not cut the side walls.
- `speaker_hole_diameter/2 + accent_ring_lip` must fit the flat side area: Y from `−(body_depth/2 − corner_radius)` to `split_y`, Z within `±(body_height/2 − corner_radius)`.
- `button_diameter/2 + button_flange_width` must fit under the flat top.
- Fastenings: rear counterbores must stay on the flat rear face, bezel bosses must fit between the display edge and the bezel edge, and the bezel brackets must stay clear of the speaker holes. `offline_layout_check.py` checks all of these.
- `accent_ring_width − 2·assembly_clearance`, `lip_thickness`, `wall_thickness − grille_step` and `wall_thickness` must each be ≥ 1.2 mm (three 0.4 mm perimeters).
