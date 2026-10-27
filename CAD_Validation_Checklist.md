# AlfieBot V0.1: CAD validation checklist

> **Current status:** Stages F and H were applied to the live Fusion design
> and checked there (sections below). A full fresh run of the generator has
> not been done, so the automated-check table is still to fill in.

## What has been checked so far (outside Fusion)

| Check | Method | Result |
|---|---|---|
| Python syntax and undefined names | `py_compile`, `pyflakes` | Clean |
| Every script code path runs without Python errors | Mocked `adsk` module (stand-in objects, no geometry) | All stages, validation and the flex test ran to completion. This proves control flow only. |
| Layout maths: envelopes, A1 Mini fit, parts inside the cavity, features on flat faces, FDM walls, fastenings, electronics fit | `python offline_layout_check.py --flex` | 116/116 rules pass at the defaults and with every flex edit |

What these do **not** prove: that each Fusion API call behaves as
expected in your Fusion build, that fillets, shells and combines succeed,
that hole features drill in the right direction, or that parameter edits
recompute cleanly.

## Automated checks (run by the script)

The script writes `AlfieBot_Validation_Report.txt` next to itself and shows a
summary. Copy the results here.

| # | Check | How the script checks it | Result |
|---|---|---|---|
| 1 | Stages A–E built | Each stage runs in its own try/except. Any exception is reported | ☐ |
| 2 | All expected components exist | The 11 component names from the brief exist under `AlfieBot_V0.1` | ☐ |
| 3 | Valid solid bodies | Each component has ≥ 1 body and every body has `isSolid` | ☐ |
| 4 | Main enclosure hollow | Main_Body volume / envelope < 0.35, and the cavity centre point is outside the material | ☐ |
| 5 | Main_Body one piece | `lumps.count == 1` | ☐ |
| 6 | Overall envelope | Measured box (oriented bounding boxes along X/Y/Z) within 1 mm of the analytic 163 × 100 × 141 | ☐ |
| 7 | A1 Mini fit | Each printable component's measured box fits 180³ in some orientation | ☐ |
| 8 | No unintended intersections | `Design.analyzeInterference` across all physical components, coincident faces excluded | ☐ |
| 9 | Rear cover and bezel separate | Each is its own component with its own bodies | ☐ |
| 10 | Design rules on the live parameters | The same rules as the offline checker, using the parameter values read from Fusion | ☐ |
| 11 | Timeline health | Every timeline item reports a healthy state | ☐ |
| 12 | Parameter edits do not break the model | Flex test: `body_width` 175, `body_depth` 110, `corner_radius` 18, `speaker_diameter` 36, `face_width` 130, one at a time, then restored | ☐ |

Watch for these **WARN lines in the build log**:
- `hole feature removed no material; using extrude cut instead`: the hole
  feature went the wrong way in your build. The model is still correct
  (it falls back to a cut), but please report it so V0.2 can fix the direction.
- `Could not set colour on …`: the appearance library names differ in your
  build. The geometry is unaffected.
- `As-built joint for … failed`: the parts are still positioned correctly
  (they are modelled in place), but they are not tied together.

## Manual checks in Fusion

| # | Check | How | Result |
|---|---|---|---|
| M1 | Looks like AlfieBot | Compare with `reference/alfiebot_concept.png`: rounded white body, large black face, cyan-ringed side speakers, top button, four feet | ☐ |
| M2 | Wall thickness | Inspect > Section Analysis on YZ and XZ: 3 mm walls everywhere, including the fillets | ☐ |
| M3 | Bezel fit | Section: 0.3 mm gap all round the bezel in the face opening. Bezel front 4 mm behind the front plane | ☐ |
| M4 | Rear cover fit | Section: tabs 0.3 mm inside the body walls. Covers butt at Y = split_y | ☐ |
| M5 | Button | Section: flange 1 mm below the top wall. 0.3 mm radial gap in the hole. Cap 5 mm proud | ☐ |
| M6 | Speakers | Ring lip sits on the side face. Grille sits on the step, flush with the side face. 37 holes per grille | ☐ |
| M7 | Tray removable | Hide Rear_Cover and remove the four foot screws. The tray can slide out of the back with nothing blocking it (there is no bottom tab) | ☐ |
| M8 | Parameter edit by hand | Change `body_width` to 170 mm and `corner_radius` to 20 mm. Everything follows. Undo | ☐ |
| M9 | Rear cover separate | Suppress `Rigid Rear_Cover` and drag the cover backwards. It moves on its own | ☐ |
| M10 | Export | Save As Mesh (3MF) for Main_Body and Rear_Cover, then import into Bambu Studio and check the size and the orientation in Component_List.md | ☐ |
| M11 | Slicer check | Slice Main_Body standing on its rear rim. Check overhang warnings at the side holes and button hole | ☐ |

## Fastenings added in Fusion (25 Oct 2026)

Stage F was applied to the saved `AlfieBot_V0.1` design in Fusion through
the Fusion connector, step by step, with the same parameters and features
as the generator. Checked afterwards in Fusion:

| Check | Result |
|---|---|
| Timeline health after every step | All items healthy |
| Interference across all 12 physical components (coincident faces excluded) | None |
| Main_Body still inside its skin (oriented bounding box) | 160 × 75.6 × 130, one lump |
| Insert and clearance holes open (point containment at hole axes) | Open at all rear, bezel bracket and access positions |
| Volumes match hand calculations (button bosses, retainer plate, floor holes) | Yes |

Manual checks for the fastenings:

| # | Check | How | Result |
|---|---|---|---|
| F1 | Rear screws | Section on X = 52: counterbore, clearance hole, insert hole line up across the split | ☐ |
| F2 | Bezel clamp | Section on X = 65: bezel boss, display back and bracket front meet at Y = −38 | ☐ |
| F3 | Screwdriver access | From the rear opening, a straight 3 mm driver reaches each bezel screw | ☐ |
| F4 | Button | Section on X = 0: 3.5 mm between retainer top and the button flange for the switch | ☐ |
| F5 | Feet | Section through a foot: counterbore, floor hole and tray insert line up | ☐ |
| F6 | Test print | Print a small coupon of one boss and fit an insert before printing the full body | ☐ |

## Electronics added in Fusion (25 Oct 2026)

Stage H was applied to the saved `AlfieBot_V0.1` design in Fusion through
the Fusion connector, with the same parameters as the generator. A
checkpoint version was saved first.

Offline electronics checks (all pass): every part inside the cavity, no
part overlapping another, display corners clear of the rounded front
edges, Pi and cooler clear of the top wall and tray, USB-C plug clear of
the button retainer, cable clear of everything along its route to the floor exit,
mic 2.5 mm clear of the left speaker magnet, speakers clear of the ring
edge, switch legs inside the retainer pocket.

Checked afterwards in Fusion:

| Check | Result |
|---|---|
| Each build step (brackets, display and Pi, speakers and clamps, amp and cradle, switch, PSU and mic) | All built without errors (about 330 new timeline items) |
| Timeline health | No unhealthy items. Only the retired features (tray Pi standoffs and the old side-bracket screw cuts) are suppressed |
| Interference across all 23 components, 48 bodies (coincident faces excluded), after the power cable reroute | None |
| Bezel screw paths | Solid bracket (top) and tray upright (bottom) behind each bezel boss, with the clearance hole on the boss axis, at X = ±50 |
| Joints | As-built rigid joints from Main_Body to every new part |

Fix made during the check: in the existing design the two Front_Bezel boss
features kept their old profiles (beside the display) after the upgrade,
although their sketches moved, so the bosses hit the display. They were
suppressed and rebuilt as `Bezel insert bosses v2` and `Bezel insert holes v2`
on the same construction points. A fresh generator run builds them in the
right place directly.

Power cable reroute (25 Oct 2026, design version 6): the rear cover
opening was removed. The cable now runs over the top, through a snap clip
under the top wall, down behind the Pi, along the tray under the screwed
Cable_Clamp, and out through a tray slot and a Main_Body floor notch, then
away under the rear cover. Checked in Fusion: no interference, timeline
healthy, rear cover solid where the opening was, clip bore and opening
clear with the ring solid round them, floor notch and tray slot open,
clamp and amp insert holes and screw holes on their boss axes. The amp
was moved forward 5 mm (`amp_center_y` 7 mm) to make room for the clamp.

Manual checks for the electronics:

| # | Check | How | Result |
|---|---|---|---|
| E1 | Display | Measure the real panel edge thickness (assumed 6.6 mm) and where the Pi standoffs sit on the back | ☐ |
| E2 | Speakers | Measure the real speaker depth, rim thickness and magnet diameter (assumed 20, 2.5, Ø28) | ☐ |
| E3 | USB-C plug | Measure the plug body and cable (assumed 12 × 7 × 26 plug, Ø3.5 cable) | ☐ |
| E4 | Switch feel | Print the retainer and cap. Press the cap: a clear click, no rattle, returns fully | ☐ |
| E5 | Test fit | Fit the Pi, cooler and plug on the display before printing the body | ☐ |
| E6 | Power cable | Snap the real cable into the clip (should click in and not slide freely), and check the clamp grips it without crushing it | ☐ |

## Known unresolved issues (to report against)

1. Some electronics sizes are estimates (display edge, Pi standoff position, speaker depth, USB-C plug). See E1 to E3.
2. One MAX98357A is mono: wire the two speakers in series or add a second amp.
3. Horizontal holes in Main_Body (speakers, button) and the top display brackets need light support when printed upright.
4. Cable channels other than the power cable are not modelled.
5. The derived `rear_cover_depth = corner_radius + 2 mm` couples the rear cover depth to the corner radius.

## Failure log

| Date | Fusion version | Check | Failure / message | Fix |
|---|---|---|---|---|
| | | | | |
