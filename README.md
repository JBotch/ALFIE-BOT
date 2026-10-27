# AlfieBot V0.1: Autodesk Fusion generator

AlfieBot is a small desktop companion robot, designed to be printed on a
Bambu Lab A1 Mini. This folder holds a Fusion Python script that builds the
V0.1 external design as an editable, parametric Fusion assembly. It uses
native components, sketches and timeline features, with no meshes and no
OpenSCAD.

> **Status: not yet run in Fusion.** The script was written without access
> to Fusion. It passes Python static checks and a mocked run that walks every
> code path, and the layout maths passes `offline_layout_check.py`. None of
> that proves the Fusion geometry builds. Run it once, then read
> `AlfieBot_Validation_Report.txt` (see [CAD_Validation_Checklist.md](CAD_Validation_Checklist.md)).

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
| Front_Bezel → Main_Body | 4 × M3 × 8 | Bosses on the back of the bezel, beside the display | Inside, through brackets on the Main_Body side walls |
| Button_Retainer → Main_Body | 2 × M3 × 8 | Bosses under the top wall | Below, through the retainer plate |
| Feet + Electronics_Tray → Main_Body | 4 × M3 × 10 | Bosses on the tray, above each foot | Underneath, through each foot and the floor |
| **Total** | **14 screws, 14 inserts** | | |

How each joint works:
- **Rear cover.** Each corner boss in Main_Body is braced to the corner by
  a 45° web. The matching bosses in the cover run from the rear wall to the
  split and have a 6.2 mm counterbore 13 mm deep, so the screw heads sit
  below the rear face. The locating tabs still align the cover.
- **Bezel and display.** The display goes in from the front, then the
  bezel. The bezel bosses press the display back against four brackets on
  the side walls, and the screws pull the bezel back against the brackets,
  so the display is clamped between them. The brackets have 45° undersides
  so they print without support, and a 6.2 mm tunnel for the screwdriver.
  Reach the screws from the back with the rear cover off.
- **Button.** The retainer plate sits 3.5 mm under the button flange, room
  for a 6 × 6 mm tactile switch on the plate. It stops the button falling
  in and the switch pushes the button up.
- **Feet and tray.** One screw per foot goes up through the foot's
  counterbore and the floor into an insert in the tray. It holds the foot
  and the tray together. To take the tray out, remove the four foot screws.

Assembly order:
1. Press the heat-set inserts into Main_Body (6), Front_Bezel (4) and
   Electronics_Tray (4) with a soldering iron and insert tip.
2. Fit the accent rings and grilles from outside.
3. Put the Top_Button in from inside, place the switch on the
   Button_Retainer, and screw the retainer up into the top bosses.
4. Fit the display, then the bezel, from the front. Screw the bezel in from
   inside.
5. Slide the Electronics_Tray in from the rear. Fit the feet and screw them
   up into the tray.
6. Fit the Rear_Cover and screw it on from the back.

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

## Known limitations (V0.1)
- **Accent rings and speaker grilles are still a press fit.** Everything
  else is screwed (section 7). The rings and grilles have no screws or
  snaps yet; a drop of CA glue holds them, or the speaker mount can clamp
  them when it is designed.
- **The fastenings were added to the existing Fusion design** (25 Oct 2026)
  with the same steps as Stage F, and that design has no interference and
  a healthy timeline. A full fresh run of this generator with Stage F has
  not been done yet.
- **Display size is a placeholder** (121 × 76 × 5 mm). Check it against
  the actual 5" DSI display before you print the bezel.
- **The Raspberry Pi 5 does not fit flat on the tray** (85 × 56 board on a
  55.4 mm deep tray). The tray is a placeholder. Prototype 2 should decide
  how the Pi is mounted. The concept shows it upright, behind the display.
- **Speaker drivers, the button switch, the microphone, cable channels and
  the screen mount** are not modelled.
- **Main_Body print orientation.** Printed standing on its rear rim, the
  front rim overhangs reach about 36° from vertical, which is fine. The
  48 mm side holes and the 22.6 mm button hole are then horizontal holes and
  need a little support, or a teardrop shape in V0.2.
- Eye graphics are extrusions 0.2 mm thick and are for looks only.
