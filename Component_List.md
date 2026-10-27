# AlfieBot V0.1: component list

Every component sits under the `AlfieBot_V0.1` assembly component. **All
component origins coincide with the assembly origin**, and every occurrence
uses the identity transform, so each part is modelled in place in assembly
coordinates (X width, Y depth with the front at −Y, Z height with Z = 0 under the feet).

`Main_Body` is grounded. Every other component is attached to it with an
as-built **rigid** joint named `Rigid <component>` (`Eye_Graphics` attaches
to `Display_Placeholder`). Suppress a joint to move that part on its own.

Envelopes are the analytic values at the default parameters, from
`offline_layout_check.py`. They are not measured in Fusion. Each Fusion
run measures them again and writes the result to the validation report.

| # | Component | Bodies | Appearance | Envelope X × Y × Z (mm) | Position (assembly, mm) | Printed? |
|---|---|---|---|---|---|---|
| 1 | Main_Body | `Main_Body` | Satin white | 160.0 × 76.0 × 130.0 | X ±80, Y −50 … 26, Z 6 … 136 | Yes |
| 2 | Front_Bezel | `Front_Bezel` | Black | 139.4 × 8.0 × 94.4 | Plate Y −46 … −43, insert bosses to Y −38, centred on Z 71 | Yes |
| 3 | Display_Placeholder | `Display_Placeholder` | Glossy black | 121.0 × 5.0 × 76.0 | Y −43 … −38, centred on Z 71 | No (bought display) |
| 4 | Top_Button | `Button_Cap`, `Button_Accent` | Dark grey + cyan | 28.0 × 28.0 × 10.5 | Centred X 0, Y −1. Z 130.5 … 141 | Yes |
| 5 | Left_Speaker_Grille | `Left_Speaker_Grille` | Dark grey | 2.0 × 42.0 × 42.0 | X −80 … −78, centred Y −1, Z 71 | Yes |
| 6 | Right_Speaker_Grille | `Right_Speaker_Grille` | Dark grey | 2.0 × 42.0 × 42.0 | X 78 … 80, centred Y −1, Z 71 | Yes |
| 7 | Left_Accent_Ring | `Left_Accent_Ring` | Cyan blue | 4.5 × 51.0 × 51.0 | X −81.5 … −77, centred Y −1, Z 71 | Yes |
| 8 | Right_Accent_Ring | `Right_Accent_Ring` | Cyan blue | 4.5 × 51.0 × 51.0 | X 77 … 81.5, centred Y −1, Z 71 | Yes |
| 9 | Rear_Cover | `Rear_Cover` | Satin white | 160.0 × 30.0 × 130.0 | Y 20 … 50 (tabs reach forward to Y 20) | Yes |
| 10 | Electronics_Tray | `Electronics_Tray` | Dark grey | 115.4 × 55.4 × 10.5 | Y ±27.7, Z 9 … 19.5 (rests on the inner floor) | Yes |
| 11 | Feet | `Foot_Front_Right`, `Foot_Front_Left`, `Foot_Rear_Right`, `Foot_Rear_Left` | Dark grey | 114.0 × 52.0 × 6.0 (set of 4) | X ±50, Y −20 and 18, Z 0 … 6 | Yes (or TPU) |
| 12 | Button_Retainer | `Button_Retainer` | Dark grey | 52.0 × 12.0 × 2.5 | Centred X 0, Y −1. Z 124.5 … 127 | Yes |
| – | Eye_Graphics (optional) | `Eye_Ring_1/2`, `Eye_Highlight_1/2` | Cyan / white | 0.2 thick | On the display front, Y −43.2 … −43 | No (visual only) |

Overall assembly envelope: **163.0 × 100.0 × 141.0 mm** (the width includes
the accent ring lips; the height includes the feet and the button).

## Build volume (Bambu Lab A1 Mini, 180 × 180 × 180 mm)

The largest parts are `Main_Body` (160 × 76 × 130) and `Rear_Cover`
(160 × 30 × 130). Every printable component fits the build volume in at
least one orientation. The in-Fusion validation measures this again.

## Suggested print orientation (not yet slicer-validated)

| Component | Orientation | Supports | Notes |
|---|---|---|---|
| Main_Body | Standing on the rear rim (split face on the bed, front face up) | Light: the tops of the two Ø48 side holes and the Ø22.6 button hole | The split face is the only large flat face; the front has no flat area left after the face opening. Rim overhangs reach about 36° from vertical. Fits as 160 × 130 footprint, 76 tall. |
| Rear_Cover | Rear face on the bed, tabs pointing up | None expected | The first layers follow the start of the edge fillet, so a brim helps. |
| Front_Bezel | Front face on the bed | None | 3 mm plate with four insert bosses pointing up. |
| Top_Button | Flange down | None | Two bodies: print the accent in cyan with AMS lite, or paint it. |
| Speaker grilles | Outer face on the bed | None | Holes are vertical. |
| Accent rings | Lip face down (the outer face, X = ±81.5, on the bed) | None | Tube and step build straight up. |
| Electronics_Tray | Plate on the bed | None | Insert holes open on the underside (the bed face). Press the inserts in from below. |
| Feet | Top face on the bed (fillet up) | None | Counterbore faces up. Print in PLA/PETG or TPU; the screw holds them either way. |
| Button_Retainer | Plate on the bed | None | |

## Assembly order and fasteners

All joints are M3 screws into M3 heat-set inserts: 14 screws (4 × M3 × 16,
6 × M3 × 8, 4 × M3 × 10) and 14 inserts. The joint-by-joint table and the
assembly order are in [README.md](README.md), section 7. The accent rings
and grilles are still a press fit.
