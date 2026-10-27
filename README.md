# AlfieBot V0.1: Autodesk Fusion generator

AlfieBot is a small desktop companion robot, designed to be printed on a
Bambu Lab A1 Mini. This folder holds a Fusion Python script that builds the
V0.1 external design as an editable, parametric Fusion assembly. It uses
native components, sketches and timeline features, with no meshes and no
OpenSCAD.

> **Status: applied to the live Fusion design, not yet run fresh.** The
> fastenings (Stage F) and the electronics mock-ups (Stage H) were added to
> the existing `AlfieBot_V0.1` design in Fusion through the Fusion connector,
> and checked there (see [CAD_Validation_Checklist.md](CAD_Validation_Checklist.md)).
> The full generator passes Python static checks and `offline_layout_check.py
> --flex`, but has not been run from scratch in Fusion.

Visual reference: [`alfiebot_concept.png`](alfiebot_concept.png)

## Files

| File | Purpose |
|---|---|
| `AlfieBot_Fusion_Generator.py` | Main Fusion script (entry point `run(context)`) |
| `AlfieBot_Fusion_Generator.manifest` | Script manifest, so Fusion lists the script |
| `alfiebot_parameters.py` | The parameter table, component list and analytic design rules. It is pure Python and shared by both scripts |
| `offline_layout_check.py` | Checks the layout maths with plain Python, without Fusion |
| `Design_Parameters.md` | Every user parameter, what it drives, and how to edit it |
| `Component_List.md` | Components, origins, envelopes, appearances and print orientation |
| `CAD_Validation_Checklist.md` | Automated and manual checks to run in Fusion |

The folder name has to match the script name (`AlfieBot_Fusion_Generator`),
because that is how Fusion finds the entry point. Fusion ignores the docs in here.

---

## 1. Install the script in Fusion

1. Copy the whole `AlfieBot_Fusion_Generator` folder somewhere permanent, for
   example `Documents/Fusion Scripts/AlfieBot_Fusion_Generator`. Keep all
   files together, because the script imports `alfiebot_parameters.py` from the same folder.
2. In Fusion, open **Utilities > Add-Ins > Scripts and Add-Ins** (or press
   **Shift+S**).
3. On the **Scripts** tab, click the **+** (or the green plus icon next to
   *My Scripts*) and choose the `AlfieBot_Fusion_Generator` folder.
4. **AlfieBot_Fusion_Generator** now appears in the list.

If Fusion doesn't list it, change `"autodeskProduct": "Fusion"` to
`"Fusion360"` in the `.manifest` file (older builds use that value) and add the folder again.

Optional: set Fusion to Z-up (**Preferences > General > Design > Default
modeling orientation: Z up**) so the ViewCube matches the robot's axes. The
script also sets a Z-up camera after building, but the ViewCube labels
follow the preference.

## 2. Generate the assembly

1. Select the script and click **Run**.
2. The script creates a **new design document**, so your open documents
   are left alone. It then:
   - adds all user parameters,
   - builds Stages A to E (body, front, speakers, button and feet, rear cover and tray),
   - builds Stage F, the fastenings: M3 screw bosses, heat-set insert holes and the button retainer (see section 7),
   - applies appearances, grounds `Main_Body` and ties the other parts to it with as-built rigid joints,
   - runs validation and a parameter flex test,
   - writes `AlfieBot_Validation_Report.txt` next to the script (or in your home folder if that isn't writable).
3. A message box shows PASS/WARN/FAIL counts and lists any failures.

Expect it to take somewhere between tens of seconds and a few minutes. The
flex test recomputes the timeline five times. To skip it, set
`RUN_PARAMETER_FLEX_TEST = False` at the top of the script.

Each stage runs in its own error handler. If one stage fails, the report
says which one and why, and the remaining stages still run. Full tracebacks
go to the report and to **Text Commands** (**View > Show Text Commands**).

Options at the top of the script:

| Option | Default | Effect |
|---|---|---|
| `CREATE_NEW_DOCUMENT` | `True` | `False` builds into the active design |
| `CREATE_EYE_GRAPHICS` | `True` | Visual-only eye discs (`Eye_Graphics` component) |
| `APPLY_APPEARANCES` | `True` | Satin white, black, grey and cyan appearances |
| `CREATE_JOINTS` | `True` | Grounds `Main_Body`; as-built rigid joints for the rest |
| `RUN_VALIDATION` | `True` | In-Fusion checks |
| `RUN_PARAMETER_FLEX_TEST` | `True` | Edits five parameters one at a time, checks the timeline, then restores them |
| `ADD_FASTENINGS_TO_ACTIVE_DESIGN` | `False` | `True` adds only Stage F to an AlfieBot design that is already open (one generated before the fastenings existed). Keeps your parameter values and adds the missing ones. Refuses to run twice |

## 3. Edit dimensions

All geometry is driven by **user parameters**.

1. Open **Modify > Change Parameters**.
2. Expand **User Parameters** and edit an expression, for example set `body_width` to `170 mm`.
3. Fusion recomputes the timeline. Every component follows, because every
   sketch dimension, plane offset, extrude distance, fillet radius, shell
   thickness and pattern count refers to a parameter.

Some parameters are derived from others (for example `split_y` and
`speaker_hole_diameter`). Change the primary values. Edit a derived
expression only when you mean to change the design intent. The full list
is in [Design_Parameters.md](Design_Parameters.md).

Before a big change, try it offline first:

```bash
python offline_layout_check.py --set body_width="170 mm" --set corner_radius="20 mm"
```

To change the defaults that every new build starts from, edit
`alfiebot_parameters.py` and run the script again.

## 4. Inspect individual components

- The **Browser** shows `AlfieBot_V0.1` with one occurrence per component
  (Main_Body, Front_Bezel, and so on, plus `Eye_Graphics`).
- Click the eye icon to hide components. For example, hide `Main_Body` and
  `Rear_Cover` to see the tray, display and button flange.
- Right-click a component and choose **Activate Component** to see only its
  sketches and features in the timeline.
- **Inspect > Section Analysis** on the YZ plane shows the wall thickness, how
  the bezel and display stack, the button flange, and the rear cover tabs.
- **Inspect > Interference** confirms that no parts overlap. The script
  runs the same check automatically.
- To move the rear cover or another part away from the body, suppress or
  delete its `Rigid <name>` joint in the Browser's **Joints** folder.

## 5. Save the native Fusion design

**File > Save** (Ctrl/Cmd+S), choose a project, and name the document
`AlfieBot_V0.1`. That gives you a native, cloud-stored `.f3d` design with the
full timeline. To keep a local copy, use **File > Export > Fusion Archive (.f3d)**.

## 6. Export STEP and STL/3MF

**STEP (whole assembly or one part):**
**File > Export**, Type **STEP Files (*.stp, *.step)**. Alternatively,
right-click a component in the Browser and choose **Save As STEP**. Use
STEP for CAD exchange and for the record.

**STL or 3MF for printing (one file per printable component):**
1. In the Browser, right-click a component (for example `Rear_Cover`) and
   choose **Save As Mesh**. You can also use **Utilities > Make > 3D Print**
   and turn off "Send to 3D print utility".
2. Format **3MF** (recommended, as Bambu Studio keeps units and colours) or
   **STL (Binary)**. Units **mm**. Refinement **High**.
3. Repeat for each printable component listed in
   [Component_List.md](Component_List.md). Don't export
   `Display_Placeholder` (a bought display) or `Eye_Graphics` (visual only).
4. In Bambu Studio, set the orientation given in the component list.

`Top_Button` contains two bodies, the dark grey cap and the cyan accent
inlay. Export them together as one 3MF to print in two colours with an AMS
lite, or print the cap on its own.

---

## 7. Fastenings and assembly

Everything except the speaker rings and grilles is held with **M3 socket
head screws into brass M3 heat-set inserts** (M3 × 5.7 mm long × 4.6 mm OD,
CNC Kitchen or Ruthex style, in a 4.0 mm hole). Every joint can be undone.

| Joint | Screws | Inserts go in | Screw goes in from |
|---|---|---|---|
| Rear_Cover → Main_Body | 4 × M3 × 16 | Main_Body corner bosses, just in front of the split | The rear face, through counterbored bosses in the cover |
| Front_Bezel → Main_Body and tray | 4 × M3 × 8 | Bosses on the back of the bezel, above and below the display | Inside: the top two through brackets hanging from the top wall, the bottom two through uprights at the front of the tray |
| Button_Retainer → Main_Body | 2 × M3 × 8 | Bosses under the top wall | Below, through the retainer plate |
| Feet + Electronics_Tray → Main_Body | 4 × M3 × 10 | Bosses on the tray, above each foot | Underneath, through each foot and the floor |
| Speaker clamps → Main_Body | 4 × M3 × 8 | Bosses on the side walls, above and below each speaker | Inside, through each clamp plate |
| Amp_Clamp → Electronics_Tray | 2 × M3 × 8 | Bosses on the tray beside the amplifier cradle | Above, through the clamp tabs |
| Cable_Clamp → Electronics_Tray | 2 × M3 × 8 | Bosses on the tray either side of the power cable | Above, through the clamp bar |
| Raspberry Pi 5 → display | 4 × M2.5 (supplied with the display) | Standoffs on the display back | Through the Pi mounting holes |
| **Total (M3)** | **22 screws, 22 inserts** | | |

How each joint works:
- **Rear cover.** Each corner boss in Main_Body is braced to the corner by
  a 45° web. The matching bosses in the cover run from the rear wall to the
  split and have a 6.2 mm counterbore 13 mm deep, so the screw heads sit
  below the rear face. The locating tabs still align the cover.
- **Bezel and display.** The display goes in from the front, then the
  bezel. The display's edges rest against shelves on the side walls, and
  the four bezel screws sit above and below the display (X = ±50). The top
  two go through brackets hanging from the top wall (45° gussets, so no
  support), and the bottom two through uprights at the front of the tray.
  The screws pull the bezel back so the display is clamped. Reach the
  screws from the back with the rear cover off.
- **Raspberry Pi 5.** The Pi screws onto the four standoffs on the back of
  the Touch Display 2 (58 × 49 pattern), with the Active Cooler fitted and
  the USB-C power edge at the top. The ribbon goes straight across to the
  display connector.
- **Power.** The 27 W USB-C plug points up into the Pi. The cable loops
  back over the top, snaps into a clip under the top wall, runs down behind
  the Pi, lies along the tray under a screwed clamp bar, and drops through
  a slot in the tray and a notch in the Main_Body floor. It leaves under
  the body (the feet give 6 mm of room) and comes out at the back below the
  rear cover. Nothing passes through the rear cover, so the cover comes off
  with the cable still plugged in, and the clamp takes any pull on the
  cable before it reaches the Pi.
- **Microphone.** The USB microphone sits in the lower USB-A port and
  sticks out towards the left side wall, clear of the speaker magnet.
- **Speakers.** Each 40 mm speaker's rim seats on the step inside the
  accent ring. A printed clamp (plate and collar) screws to two side-wall
  bosses and holds the speaker, the ring and the grille in one go, so the
  rings and grilles are no longer just a press fit.
- **Amplifier.** The MAX98357A board sits in a cradle on the tray (ledges
  and walls) and a printed clamp with two screws holds it down.
- **Button.** A 12 × 12 × 6 mm tactile switch sits in a 1 mm pocket in the
  Button_Retainer, with its four legs through holes in the plate. The
  printed Top_Button cap rests on the switch plunger, 0.5 mm of travel
  under the flange, and the retainer stops the cap falling in.
- **Feet and tray.** One screw per foot goes up through the foot's
  counterbore and the floor into an insert in the tray. It holds the foot
  and the tray together. To take the tray out, remove the four foot screws.

Assembly order:
1. Press the heat-set inserts into Main_Body (10), Front_Bezel (4) and
   Electronics_Tray (8) with a soldering iron and insert tip.
2. Fit the accent rings and grilles from outside, then each speaker and
   its clamp from inside.
3. Put the Top_Button in from inside, solder or plug the switch, seat it in
   the Button_Retainer pocket, and screw the retainer up into the top bosses.
4. Screw the Pi 5 (with the Active Cooler) onto the display standoffs and
   connect the ribbon. Fit the display, then the bezel, from the front.
   Screw the top two bezel screws in from inside.
5. Clamp the amplifier on the tray. Slide the Electronics_Tray in from the
   rear, screw the bottom two bezel screws, then fit the feet and screw
   them up into the tray.
6. Plug in the microphone and the USB-C power. Snap the cable into the
   clip under the top wall, lay it down behind the Pi and along the tray,
   and slide it into the tray slot and floor notch from the rear so it
   hangs out under the body. Screw the cable clamp bar down over it, then
   fit the Rear_Cover and screw it on.

Print notes: inserts go in from the open face of each boss, so every insert
hole faces up or sideways in the suggested print orientations
(see [Component_List.md](Component_List.md)).

## How the generator is built

### Coordinate system and origins
- X = width (left −X, right +X), Y = depth (front −Y, rear +Y), Z = height.
- Z = 0 is the underside of the feet. The enclosure runs from
  Z = `foot_height` to Z = `body_top_z`.
- The front face points to −Y. The rear cover is at +Y, behind the split
  plane Y = `split_y`.
- **Every component's origin coincides with the assembly origin**, and every
  occurrence uses the identity transform. Each part is modelled in place in
  assembly coordinates, so all components share the same axes and you
  never need transform maths to read a dimension.
- "Left" means −X: the viewer's left when facing the robot's front.

### Component structure
```
(root document)
└── AlfieBot_V0.1                 assembly component
    ├── Main_Body                 grounded
    ├── Front_Bezel               as-built rigid joint → Main_Body
    ├── Display_Placeholder       "
    ├── Top_Button                "  (bodies: Button_Cap, Button_Accent)
    ├── Left_Speaker_Grille       "
    ├── Right_Speaker_Grille      "
    ├── Left_Accent_Ring          "
    ├── Right_Accent_Ring         "
    ├── Rear_Cover                "
    ├── Electronics_Tray          "
    ├── Feet                      "  (4 bodies)
    ├── Button_Retainer           "  (plate under the button, carries the switch)
    ├── Left/Right_Speaker_Clamp  "  (printed)
    ├── Amp_Clamp                 "  (printed)
    ├── Raspberry_Pi_5            "  (mock-up, with Active Cooler)
    ├── Left/Right_Speaker        "  (mock-up)
    ├── I2S_Amplifier             "  (mock-up)
    ├── Tactile_Switch            "  (mock-up)
    ├── Cable_Clamp               "  (printed, holds the power cable on the tray)
    ├── PSU_Plug                  "  (mock-up, with cable)
    ├── USB_Microphone            "  (mock-up)
    └── Eye_Graphics              joint → Display_Placeholder (visual only)
```
The Fusion root component always takes the document's name, so the named
`AlfieBot_V0.1` assembly is a component directly under the root.

### Modelling approach
- **Parametric anchors.** Each component gets construction planes offset
  from its own origin planes by parameter expressions. Construction points
  are made from three such planes, projected into sketches, and sketch
  rectangles and circles are dimensioned from them with expressions. No
  sketch geometry relies on hard-coded coordinates.
- **Units.** Feature sizes are passed as expression strings
  (`"body_width/2 + 10 mm"`), so Fusion converts mm to its internal cm.
  Numeric values (from `unitsManager.evaluateExpression`) are only used to
  place starting sketch geometry before the driven dimensions lock it.
- **Extrude direction.** Worked out from the sketch normal and the wanted
  model direction, not from assumptions about how Fusion orients each
  sketch plane.
- **No fixed timeline indices.** Features are found through the objects
  the API returns and through body names.
- **Fragile operations avoided.** Rounded rectangles are rectangular
  prisms with edge fillets, not sketch fillets. Openings are cut with
  combine tool bodies. Hole features fall back to an extrude cut, with a
  log entry, if a Fusion build behaves differently.

| Stage | Operations |
|---|---|
| A: Main body | Footprint sketch → extrude → fillet all 12 edges (`corner_radius`) → shell inward (`wall_thickness`) → cut everything behind `split_y` |
| B: Front | Rounded prism tool → combine cut for the face opening. Bezel = rounded plate minus a rounded window. Display block. Eye rings and highlights |
| C: Speakers | One symmetric cut through both side walls. Ring = tube + inner step + outer lip (3 joins). Grille disc + hole feature + 3 **circular patterns** about an axis from the grille's cylindrical face |
| D: Button and feet | Button hole cut. Button flange + stem/cap join + top fillet + accent groove cut + accent inlay body. Foot extrude + fillet + **mirror** on X, then on Y = `module_center_y` |
| E: Rear cover and tray | The same rounded shell, keeping only what is behind `split_y`. Tab roots fused into the wall + 3 locating tabs. Vent slot + **rectangular pattern**. Tray plate + rails + standoff + 2×2 **rectangular pattern** |
| F: Fastenings | Rear insert bosses with 45° corner webs, bezel brackets with 45° undersides, button insert bosses: joined to Main_Body, then everything outside the enclosure skin is cut away. Insert holes, clearance holes, counterbores. Bezel and tray insert bosses. Button_Retainer plate |
| H: Electronics | Top display brackets and tray uprights. Mock-ups of the Touch Display 2, the Pi 5 with the Active Cooler, the speakers, the amplifier, the switch, the USB-C plug (pipe cable) and the microphone. Speaker clamps and side bosses, the amp cradle and clamp, the switch pocket and leg holes. The power cable route with its snap clip under the top wall, the screwed cable clamp and bosses on the tray, and the tray slot and floor notch where it leaves |
| G: Finish | Appearances, grounding and joints, camera, validation, flex test, report |

### Design decisions you should know about
- **Overall height** is `foot_height + body_height + button_height` = 141 mm,
  and the overall width including the accent rings is 163 mm. `body_*` sets the
  enclosure itself, as the brief describes.
- **The rear cover** is the back 24 mm of the same rounded shell, so the
  split lies in the straight part of the walls. Three tabs (top, left
  and right) locate it inside the body with `assembly_clearance`. There is
  no bottom tab, so the electronics tray can slide out of the back.
- **The front face opening** (140 × 95) is larger than the flat front area
  (116 × 86), as in the concept image. The opening cuts into the edge
  fillets, which gives the white rim its rounded look.
- **The speaker rings** sit in the side-wall holes. An outer lip stops a
  ring from going in too far, and an inner step stops the grille.
  Everything is centred in the flat side area in front of the split.

## Known limitations
- **Electronics sizes come from published drawings, with some guesses.**
  The Touch Display 2 outline (143.4 × 91.46), active area and standoff
  pattern are published; the 6.6 mm panel edge thickness and the standoff
  position on the back (assumed centred under the board) are not, and
  should be measured. The 40 mm speaker has no drawing: depth 20, rim
  2.5 mm and magnet Ø28 are estimates. The USB-C plug and mic sizes are
  typical values. All are in `ELECTRONICS_PARAMETERS`, so measure and edit.
- **One MAX98357A is mono.** Two speakers on one amp need wiring in series
  (2 × 4 Ω = 8 Ω, a little quieter) or a second amp for stereo.
- **The electronics were added to the existing Fusion design** (25 Oct
  2026) with `context_for_electronics_upgrade()`, the same steps as Stage
  H. A full fresh run of this generator has not been done yet. In the
  upgraded design the bezel bosses had to be rebuilt by hand (the old
  extrudes kept their old profiles), so if you run the upgrade on another
  copy, check the bezel bosses sit at X = ±50 above and below the display.
- **Circle-based bosses and holes do not follow parameter edits in Fusion.**
  Found on 25 Oct 2026: after a parameter moved them, the sketch circles
  moved but the extrudes kept their old profiles (bezel bosses, amp and
  cable clamp bosses, insert and screw holes). Features drawn with
  rectangles follow correctly. Until `PartBuilder.circles()` is fixed,
  regenerate (or rebuild those features) after moving a boss or hole.
- **Cable channels** are not modelled, apart from the power cable route. Leave
  slack for the speaker, switch and ribbon wires.
- **Main_Body print orientation.** Printed standing on its rear rim, the
  front rim overhangs reach about 36° from vertical, which is fine. The
  44 mm side holes, the 22.6 mm button hole, the top display brackets and
  the speaker bosses then need a little support.
- Eye graphics are extrusions 0.2 mm thick and are for looks only.
