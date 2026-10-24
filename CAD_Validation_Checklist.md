# AlfieBot V0.1: CAD validation checklist

> **Current status: NOT EXECUTED IN FUSION.** The generator was written in
> an environment without Autodesk Fusion. Nothing below has been confirmed
> against real Fusion geometry yet. Fill in the "Result" columns after the
> first run.

## What has been checked so far (outside Fusion)

| Check | Method | Result |
|---|---|---|
| Python syntax and undefined names | `py_compile`, `pyflakes` | Clean |
| Every script code path runs without Python errors | Mocked `adsk` module (stand-in objects, no geometry) | All stages, validation and the flex test ran to completion. This proves control flow only. |
| Layout maths: envelopes, A1 Mini fit, parts inside the cavity, features on flat faces, FDM walls | `python offline_layout_check.py --flex` | 44/44 rules pass at the defaults and for each of the 5 flex-test edits |

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
| 12 | Parameter edits do not break the model | Flex test: `body_width` 175, `body_depth` 110, `corner_radius` 18, `speaker_diameter` 38, `face_width` 130, one at a time, then restored | ☐ |

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
| M7 | Tray removable | Hide Rear_Cover. The tray can slide out of the back with nothing blocking it (there is no bottom tab) | ☐ |
| M8 | Parameter edit by hand | Change `body_width` to 170 mm and `corner_radius` to 20 mm. Everything follows. Undo | ☐ |
| M9 | Rear cover separate | Suppress `Rigid Rear_Cover` and drag the cover backwards. It moves on its own | ☐ |
| M10 | Export | Save As Mesh (3MF) for Main_Body and Rear_Cover, then import into Bambu Studio and check the size and the orientation in Component_List.md | ☐ |
| M11 | Slicer check | Slice Main_Body standing on its rear rim. Check overhang warnings at the side holes and button hole | ☐ |

## Known unresolved issues (to report against)

1. Retention is not modelled (screws, inserts, snaps) for the bezel, display, rings, grilles, button and rear cover.
2. The display dimensions are placeholders.
3. A Raspberry Pi 5 board (85 × 56) does not fit flat on the 55.4 mm deep tray. Mounting is to be decided in Prototype 2.
4. Horizontal holes in Main_Body (speakers, button) need support or a teardrop shape when printed upright.
5. Speaker drivers, button switch, microphone, cable channels and screen mount are not modelled.
6. The derived `rear_cover_depth = corner_radius + 2 mm` couples the rear cover depth to the corner radius.

## Failure log

| Date | Fusion version | Check | Failure / message | Fix |
|---|---|---|---|---|
| | | | | |
