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

Visual reference: [`../reference/alfiebot_concept.png`](../reference/alfiebot_concept.png)

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
| F: Finish | Appearances, grounding and joints, camera, validation, flex test, report |

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
- **Retention isn't modelled yet.** The bezel, display, rings, grilles and
  rear cover locate correctly, but nothing holds them in place yet: no
  screw bosses, snaps or heat-set inserts. That is planned for V0.2. The
  concept shows M3 screws and inserts.
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
