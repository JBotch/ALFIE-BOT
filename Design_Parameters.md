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
| `face_height` | `110 mm` | 110 | mm | Front face opening height (tall enough for bezel screws above and below the display) |
| `speaker_diameter` | `38 mm` | 38 | mm | Speaker grille diameter (the 40 mm speaker rim seats on the accent ring behind it) |
| `button_diameter` | `22 mm` | 22 | mm | Top button cap diameter |
| `foot_height` | `6 mm` | 6 | mm | Foot height; enclosure underside sits at Z = foot_height |
| `assembly_clearance` | `0.3 mm` | 0.3 | mm | Clearance between mating printed parts |

## 2. Secondary parameters (independent, added to define V0.1 fully)

| Parameter | Expression | Value | Unit | Purpose |
|---|---|---|---|---|
| `face_corner_radius` | `14 mm` | 14 | mm | Corner radius of the front face opening |
| `bezel_thickness` | `6 mm` | 6 | mm | Front bezel plate thickness (Y); sets the display back far enough to clear the rounded front corners |
| `display_width` | `143.4 mm` | 143.4 | mm | Raspberry Pi Touch Display 2 (5 inch) outline, long side, mounted landscape (published 143.4 mm) |
| `display_height` | `91.46 mm` | 91.46 | mm | Touch Display 2 (5 inch) outline, short side (published 91.46 mm) |
| `display_thickness` | `6.6 mm` | 6.6 | mm | Touch Display 2 panel thickness at the edges, where the brackets clamp it (6.6 mm listed; measure) |
| `display_window_width` | `111 mm` | 111 | mm | Bezel window width (active area 110.4 mm, viewing area 111.5 mm) |
| `display_window_height` | `62.6 mm` | 62.6 | mm | Bezel window height (active area 62.1 mm, viewing area 63 mm) |
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
| `button_travel` | `0.5 mm` | 0.5 | mm | Gap between button flange and the inside of the top wall (free play above the switch) |
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
| `standoff_diameter` | `6 mm` | 6 | mm | Board standoff outer diameter (no longer used: the Pi mounts on the display) |
| `standoff_hole_diameter` | `2.5 mm` | 2.5 | mm | Board standoff pilot hole (M2.5, no longer used) |
| `standoff_height` | `5 mm` | 5 | mm | Height of the tray insert bosses above the tray |
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
| `bezel_screw_x` | `50 mm` | 50 | mm | Bezel screw X offset (screws sit above and below the display) |
| `bezel_bracket_thickness` | `4 mm` | 4 | mm | Main_Body bezel bracket thickness (Y) |
| `bezel_bracket_width` | `12 mm` | 12 | mm | Main_Body bezel bracket width (Z) |
| `bezel_bracket_overlap` | `4 mm` | 4 | mm | How far the bezel brackets reach over the display back edge |
| `button_switch_size` | `12 mm` | 12 | mm | Tactile switch body, square (12 x 12 mm, 6 mm tall switch) |
| `button_switch_total_height` | `6 mm` | 6 | mm | Tactile switch height from its base to the top of the plunger |
| `button_switch_pocket_depth` | `1 mm` | 1 | mm | Depth of the switch locating pocket in the retainer |
| `button_switch_leg_pitch_x` | `12.5 mm` | 12.5 | mm | Tactile switch leg pitch across the leg pairs |
| `button_switch_leg_pitch_y` | `5 mm` | 5 | mm | Tactile switch leg pitch within a pair |
| `button_switch_leg_hole` | `1.4 mm` | 1.4 | mm | Retainer hole for each switch leg |
| `button_screw_offset` | `6 mm` | 6 | mm | Gap from the button flange edge to the retainer screw centre |
| `button_retainer_thickness` | `2.5 mm` | 2.5 | mm | Button retainer plate thickness |
| `foot_counterbore_depth` | `3.5 mm` | 3.5 | mm | Screw head counterbore depth in each foot |

## 3. Derived parameters (expressions of other parameters)

Change these only to change the design intent. Normally you edit the
independent parameters above and these follow.

| Parameter | Expression | Value | Unit | Purpose |
|---|---|---|---|---|
| `rear_cover_depth` | `corner_radius + 2 mm` | 24 | mm | Rear cover depth; must exceed corner_radius so the split is in the straight section |
| `split_y` | `body_depth/2 - rear_cover_depth` | 26 | mm | Y position of the main body / rear cover split plane |
| `module_center_y` | `(corner_radius - rear_cover_depth)/2` | -1 | mm | Y centre of the flat side/top region in front of the split |
| `body_center_z` | `foot_height + body_height/2` | 71 | mm | Z centre of the enclosure |
| `body_top_z` | `foot_height + body_height` | 136 | mm | Z of the enclosure top surface |
| `face_center_z` | `body_center_z` | 71 | mm | Z centre of the front face |
| `face_recess` | `wall_thickness + 1 mm` | 4 | mm | Depth of the bezel front surface behind the front plane |
| `display_front_y` | `-body_depth/2 + face_recess + bezel_thickness` | -40 | mm | Y of the display front surface |
| `speaker_hole_diameter` | `speaker_diameter + 2*accent_ring_width` | 44 | mm | Side wall hole for the accent ring |
| `foot_x` | `body_width/2 - corner_radius - foot_diameter/2 - foot_inset` | 50 | mm | Foot centre X offset |
| `foot_front_y` | `-(body_depth/2 - corner_radius) + foot_diameter/2 + foot_inset` | -20 | mm | Front foot centre Y |
| `tray_z` | `foot_height + wall_thickness` | 9 | mm | Z of the tray underside (inner floor) |
| `tray_width` | `body_width - 2*corner_radius - 2*assembly_clearance` | 115.4 | mm | Tray width (fits the flat floor) |
| `tray_depth` | `body_depth - 2*corner_radius - 2*assembly_clearance` | 55.4 | mm | Tray depth (fits the flat floor) |
| `foot_rear_y` | `2*module_center_y - foot_front_y` | 18 | mm | Rear foot centre Y (mirror of the front feet) |
| `rear_screw_x` | `body_width/2 - corner_radius - rear_screw_inset` | 52 | mm | Rear cover screw X offset |
| `rear_screw_dz` | `body_height/2 - corner_radius - rear_screw_inset` | 37 | mm | Rear cover screw Z offset from the body centre |
| `bezel_screw_dz` | `display_height/2 + insert_boss_diameter/2 + 0.6 mm` | 50.33 | mm | Bezel screw Z offset above and below the face centre (just clear of the display) |
| `display_back_y` | `display_front_y + display_thickness` | -33.4 | mm | Y of the display panel back, where the brackets clamp it |
| `button_switch_height` | `button_switch_total_height - button_switch_pocket_depth` | 5 | mm | Switch height above the retainer top face |
| `button_screw_x` | `button_diameter/2 + button_flange_width + button_screw_offset` | 20 | mm | Button retainer screw X offset |
| `button_retainer_z` | `body_top_z - wall_thickness - button_travel - button_flange_thickness - button_switch_height` | 126 | mm | Z of the button retainer top face |

## 4. Electronics parameters (Stage H)

Sizes of the bought parts, the clamps and cradle that hold them, and the
PSU cable route and its retention.
Values marked "measure" or "assumed" had no published drawing; check
them against the real parts when they arrive and edit the parameter.

| Parameter | Expression | Value | Unit | Purpose |
|---|---|---|---|---|
| `display_total_depth` | `16 mm` | 16 | mm | Display depth including the Pi standoffs on its back (published 16 mm) |
| `display_standoff_diameter` | `5 mm` | 5 | mm | Display Pi standoff diameter (mock-up) |
| `pi_holes_center_x` | `10 mm` | 10 | mm | X of the Pi hole pattern centre on the display back (assumed; puts the board centred) |
| `pi_board_length` | `85 mm` | 85 | mm | Raspberry Pi 5 board length |
| `pi_board_width` | `56 mm` | 56 | mm | Raspberry Pi 5 board width |
| `pi_board_thickness` | `1.6 mm` | 1.6 | mm | Raspberry Pi 5 board thickness |
| `pi_hole_inset` | `3.5 mm` | 3.5 | mm | Raspberry Pi 5 mounting hole inset from the board edges |
| `cooler_length` | `63.5 mm` | 63.5 | mm | Active Cooler footprint along the board |
| `cooler_width` | `42.5 mm` | 42.5 | mm | Active Cooler footprint across the board |
| `cooler_height` | `13.7 mm` | 13.7 | mm | Active Cooler height above the board |
| `usbc_plug_width` | `12 mm` | 12 | mm | PSU USB-C plug overmould width (measure) |
| `usbc_plug_thickness` | `7 mm` | 7 | mm | PSU USB-C plug overmould thickness (measure) |
| `usbc_plug_length` | `26 mm` | 26 | mm | PSU USB-C plug length out from the board edge, strain relief included (measure) |
| `psu_cable_diameter` | `3.5 mm` | 3.5 | mm | PSU cable diameter |
| `mic_length` | `10 mm` | 10 | mm | Mini USB microphone length standing out of the USB port (22 mm overall) |
| `mic_width` | `18 mm` | 18 | mm | Mini USB microphone width |
| `mic_thickness` | `7 mm` | 7 | mm | Mini USB microphone thickness |
| `speaker_outer_diameter` | `40 mm` | 40 | mm | Speaker frame diameter |
| `speaker_depth` | `20 mm` | 20 | mm | Speaker depth, rim to magnet back (measure) |
| `speaker_rim_thickness` | `2.5 mm` | 2.5 | mm | Speaker front rim thickness (measure) |
| `speaker_magnet_diameter` | `28 mm` | 28 | mm | Speaker magnet diameter (measure) |
| `speaker_boss_length` | `7 mm` | 7 | mm | Speaker clamp insert boss length from the inner side wall |
| `speaker_clamp_dz` | `30 mm` | 30 | mm | Speaker clamp screw Z offset above and below the speaker axis |
| `speaker_clamp_thickness` | `3 mm` | 3 | mm | Speaker clamp plate thickness |
| `speaker_clamp_width` | `12 mm` | 12 | mm | Speaker clamp arm width |
| `amp_board_width` | `19.4 mm` | 19.4 | mm | Amplifier board size along X (19.4 x 17.8 mm published) |
| `amp_board_depth` | `17.8 mm` | 17.8 | mm | Amplifier board size along Y |
| `amp_board_thickness` | `1.6 mm` | 1.6 | mm | Amplifier board thickness |
| `amp_center_y` | `12 mm` | 12 | mm | Amplifier centre Y on the tray |
| `amp_ledge_height` | `3 mm` | 3 | mm | Height of the cradle ledges under the amplifier (clears solder joints) |
| `amp_ledge_width` | `1.5 mm` | 1.5 | mm | Width of the cradle ledges under the amplifier side edges |
| `amp_cradle_wall` | `1.6 mm` | 1.6 | mm | Amplifier cradle wall thickness |
| `amp_screw_x` | `16 mm` | 16 | mm | Amplifier clamp screw X offset |
| `amp_clamp_overlap` | `2 mm` | 2 | mm | How far each clamp tab presses on the amplifier board edge |
| `amp_clamp_thickness` | `3 mm` | 3 | mm | Amplifier clamp tab thickness |
| `amp_part_height` | `8.5 mm` | 8.5 | mm | Height of the amplifier header pins and terminal block above the board |
| `psu_route_y` | `11 mm` | 11 | mm | Y of the PSU cable's vertical run behind the Pi |
| `psu_exit_y` | `23 mm` | 23 | mm | Y where the PSU cable drops through the tray and the floor |
| `cable_bend_radius` | `3 mm` | 3 | mm | PSU cable bend radius at each corner of the route |
| `cable_slot_width` | `4.2 mm` | 4.2 | mm | Tray and floor slot the PSU cable slides into from the rear |
| `cable_clip_y` | `0 mm` | 0 | mm | Y centre of the snap clip under the top wall |
| `cable_clip_length` | `6 mm` | 6 | mm | Snap clip length along the cable |
| `cable_clip_wall` | `1.6 mm` | 1.6 | mm | Snap clip ring wall thickness |
| `cable_clip_opening` | `2.8 mm` | 2.8 | mm | Snap clip opening (narrower than the cable so it snaps in) |
| `cable_clamp_y` | `17 mm` | 17 | mm | Y centre of the cable clamp on the tray |
| `cable_clamp_length` | `16 mm` | 16 | mm | Cable clamp bar length across the cable (X) |
| `cable_clamp_width` | `6 mm` | 6 | mm | Cable clamp bar width along the cable (Y) |
| `cable_clamp_thickness` | `3 mm` | 3 | mm | Cable clamp bar thickness |
| `cable_clamp_screw_dx` | `5.5 mm` | 5.5 | mm | Cable clamp screw X offset either side of the cable |
| `cable_clamp_crush` | `0.3 mm` | 0.3 | mm | Gap under the clamp bar at its bosses; tightening the screws squeezes the cable this much |

Derived:

| Parameter | Expression | Value | Unit | Purpose |
|---|---|---|---|---|
| `pi_pcb_y` | `display_front_y + display_total_depth` | -24 | mm | Y of the Pi 5 board underside |
| `pi_center_x` | `pi_holes_center_x - (pi_board_length/2 - pi_hole_inset - pi_hole_spacing_x/2)` | 0 | mm | Pi 5 board centre X |
| `pi_top_z` | `face_center_z + pi_board_width/2` | 99 | mm | Z of the Pi 5 top edge (the USB-C edge) |
| `usbc_x` | `pi_center_x + pi_board_length/2 - 11.2 mm` | 31.3 | mm | X of the Pi 5 USB-C port |
| `speaker_front_x` | `body_width/2 - wall_thickness` | 77 | mm | X of the speaker rim front (seated on the accent ring) |
| `speaker_boss_x` | `speaker_front_x - speaker_boss_length` | 70 | mm | X of the speaker clamp boss ends |
| `amp_top_z` | `tray_z + tray_thickness + amp_ledge_height + amp_board_thickness` | 16.1 | mm | Z of the amplifier board top |
| `psu_plug_y` | `pi_pcb_y + pi_board_thickness + 1.6 mm` | -20.8 | mm | Y of the USB-C plug centre |
| `psu_plug_top_z` | `pi_top_z + 1 mm + usbc_plug_length` | 126 | mm | Z of the USB-C plug top, where the cable leaves it |
| `psu_route_top_z` | `psu_plug_top_z + 4 mm` | 130 | mm | Z of the PSU cable's top run |
| `psu_run_z` | `tray_z + tray_thickness + psu_cable_diameter/2` | 13.25 | mm | Z of the PSU cable axis where it lies on the tray |
| `psu_under_z` | `psu_cable_diameter/2 + 0.2 mm` | 1.95 | mm | Z of the PSU cable axis under the body (between the feet) |
| `cable_clamp_z` | `psu_run_z + psu_cable_diameter/2` | 15 | mm | Z of the cable clamp bar underside (on the cable) |

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
- `speaker_diameter` → `36 mm`
- `face_width` → `130 mm`

With the electronics added, all five pass the offline rules (116 checks
each). The bezel screws now sit above and below the display, so a narrower
face no longer clashes with them. Whether the Fusion timeline recomputes
cleanly with them still needs to be confirmed in Fusion.

## Constraints between parameters

- `rear_cover_depth` > `corner_radius`: the split plane must sit in the straight part of the walls.
- `face_width/2` ≤ `body_width/2 − wall_thickness − 2 mm`: the face opening must not cut the side walls.
- `speaker_hole_diameter/2 + accent_ring_lip` must fit the flat side area: Y from `−(body_depth/2 − corner_radius)` to `split_y`, Z within `±(body_height/2 − corner_radius)`.
- `button_diameter/2 + button_flange_width` must fit under the flat top.
- Fastenings: rear counterbores must stay on the flat rear face, bezel bosses must fit between the display's top and bottom edges and the bezel edge, and the bezel side shelves must stay clear of the speaker holes. `offline_layout_check.py` checks all of these.
- Electronics: every mock-up must sit inside the cavity, the display corners must clear the rounded front edges (this is what sets `bezel_thickness`), the microphone must clear the left speaker magnet, the PSU plug and lead must clear the button retainer and the top wall, and the PSU cable must stay in front of the rear cover tabs, leave through the Main_Body floor (not the rear cover), fit under the body between the feet, and keep its clamp on the straight run along the tray.
- `accent_ring_width − 2·assembly_clearance`, `lip_thickness`, `wall_thickness − grille_step` and `wall_thickness` must each be ≥ 1.2 mm (three 0.4 mm perimeters).
