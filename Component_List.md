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
| 2 | Front_Bezel | `Front_Bezel` | Black | 139.4 × 12.6 × 109.4 | Plate Y −46 … −40, insert bosses to Y −33.4, centred on Z 71 | Yes |
| 3 | Display_Placeholder | `Display_Placeholder`, `Display_Pi_Standoff_1…4` | Glossy black | 143.4 × 16.0 × 91.5 | Panel Y −40 … −33.4, standoffs to Y −24, centred on Z 71 | No (Touch Display 2, 5 inch) |
| 4 | Top_Button | `Button_Cap`, `Button_Accent` | Dark grey + cyan | 28.0 × 28.0 × 10.0 | Centred X 0, Y −1. Z 131 … 141 | Yes (the button cap) |
| 5 | Left_Speaker_Grille | `Left_Speaker_Grille` | Dark grey | 2.0 × 38.0 × 38.0 | X −80 … −78, centred Y −1, Z 71 | Yes |
| 6 | Right_Speaker_Grille | `Right_Speaker_Grille` | Dark grey | 2.0 × 38.0 × 38.0 | X 78 … 80, centred Y −1, Z 71 | Yes |
| 7 | Left_Accent_Ring | `Left_Accent_Ring` | Cyan blue | 4.5 × 47.0 × 47.0 | X −81.5 … −77, centred Y −1, Z 71 | Yes |
| 8 | Right_Accent_Ring | `Right_Accent_Ring` | Cyan blue | 4.5 × 47.0 × 47.0 | X 77 … 81.5, centred Y −1, Z 71 | Yes |
| 9 | Rear_Cover | `Rear_Cover` | Satin white | 160.0 × 30.0 × 130.0 | Y 20 … 50 (tabs reach forward to Y 20). No cable passes through it | Yes |
| 10 | Electronics_Tray | `Electronics_Tray` | Dark grey | 115.4 × 61.1 × 20.3 | Plate Y ±27.7, Z 9 … 19.5; bezel uprights reach Y −33.4, Z 29.3 | Yes |
| 11 | Feet | `Foot_Front_Right`, `Foot_Front_Left`, `Foot_Rear_Right`, `Foot_Rear_Left` | Dark grey | 114.0 × 52.0 × 6.0 (set of 4) | X ±50, Y −20 and 18, Z 0 … 6 | Yes (or TPU) |
| 12 | Button_Retainer | `Button_Retainer` | Dark grey | 52.0 × 17.0 × 2.5 | Centred X 0, Y −1. Z 123.5 … 126 | Yes |
| 13 | Raspberry_Pi_5 | `Pi_Board`, ports, `Pi_GPIO_Header`, `Active_Cooler` | Green / metal | 87.0 × 17.6 × 57.0 | On the display back: board Y −24 … −22.4, X −44.5 … 42.5, Z 43 … 100 (USB-C edge up) | No (bought) |
| 14 | USB_Microphone | `USB_Microphone` | Black | 10.0 × 7.0 × 18.0 | In the lower USB port nearest the floor, X −54.5 … −44.5 | No (bought) |
| 15 | PSU_Plug | `PSU_USB_C_Plug`, `PSU_Cable` | White | 12.0 × 89.3 × 131.8 | Plug Z 100 … 126 at X 31.3. Cable over the top (Z 130), down at Y 11, along the tray, out through the floor at Y 23 and away under the body | No (official 27 W PSU) |
| 16 | Left_Speaker | `Left_Speaker` | Black | 20.0 × 40.0 × 40.0 | X −77 … −57, centred Y −1, Z 71 | No (40 mm 3 W) |
| 17 | Right_Speaker | `Right_Speaker` | Black | 20.0 × 40.0 × 40.0 | X 57 … 77, centred Y −1, Z 71 | No (40 mm 3 W) |
| 18 | Left_Speaker_Clamp | `Left_Speaker_Clamp` | Dark grey | 7.5 × 48.0 × 72.0 | X −74.5 … −67, centred Y −1, Z 71 | Yes |
| 19 | Right_Speaker_Clamp | `Right_Speaker_Clamp` | Dark grey | 7.5 × 48.0 × 72.0 | X 67 … 74.5, centred Y −1, Z 71 | Yes |
| 20 | I2S_Amplifier | `Amp_Board`, `Amp_Header`, `Amp_Terminal_Block` | Blue / black | 19.4 × 17.8 × 10.1 | In the tray cradle, centred X 0, Y 12, board top Z 16.1 | No (Adafruit MAX98357A) |
| 21 | Amp_Clamp | `Amp_Clamp_Left`, `Amp_Clamp_Right` | Dark grey | 44.0 × 10.0 × 3.0 (pair) | X ±(7.7 … 22), Y 7 … 17, Z 16.1 … 19.1 | Yes |
| 22 | Tactile_Switch | `Switch_Body`, `Switch_Plunger`, `Switch_Leg_1…4` | Metal / black | 13.3 × 12.0 × 9.5 | In the retainer pocket, base Z 125, plunger top Z 131 | No (12 mm, 6 mm tall) |
| 23 | Cable_Clamp | `Cable_Clamp` | Dark grey | 16.0 × 6.0 × 3.0 | On the tray over the power cable, X 23.3 … 39.3, Y 14 … 20, Z 15 … 18 | Yes |
| – | Eye_Graphics (optional) | `Eye_Ring_1/2`, `Eye_Highlight_1/2` | Cyan / white | 0.2 thick | On the display front, Y −40.2 … −40 | No (visual only) |

Overall assembly envelope: **163.0 × 100.0 × 141.0 mm** (the width includes
the accent ring lips; the height includes the feet and the button).

## Build volume (Bambu Lab A1 Mini, 180 × 180 × 180 mm)

The largest parts are `Main_Body` (160 × 76 × 130) and `Rear_Cover`
(160 × 30 × 130). Every printable component fits the build volume in at
least one orientation. The in-Fusion validation measures this again.

## Suggested print orientation (not yet slicer-validated)

| Component | Orientation | Supports | Notes |
|---|---|---|---|
| Main_Body | Standing on the rear rim (split face on the bed, front face up) | Light: the tops of the two Ø44 side holes, the Ø22.6 button hole, the two top display brackets (45° gussets help) and the speaker clamp bosses | The split face is the only large flat face; the front has no flat area left after the face opening. Rim overhangs reach about 36° from vertical. Fits as 160 × 130 footprint, 76 tall. |
| Rear_Cover | Rear face on the bed, tabs pointing up | None expected | The first layers follow the start of the edge fillet, so a brim helps. |
| Front_Bezel | Front face on the bed | None | 3 mm plate with four insert bosses pointing up. |
| Top_Button | Flange down | None | Two bodies: print the accent in cyan with AMS lite, or paint it. |
| Speaker grilles | Outer face on the bed | None | Holes are vertical. |
| Accent rings | Lip face down (the outer face, X = ±81.5, on the bed) | None | Tube and step build straight up. |
| Electronics_Tray | Plate on the bed | None | Insert holes open on the underside (the bed face). Press the inserts in from below. |
| Feet | Top face on the bed (fillet up) | None | Counterbore faces up. Print in PLA/PETG or TPU; the screw holds them either way. |
| Button_Retainer | Plate on the bed, switch pocket up | None | The 12 mm switch sits in the 1 mm pocket with its legs through the four holes. |
| Speaker clamps | Plate on the bed, collar up | None | |
| Amp_Clamp | Flat on the bed | None | Two small tabs. |
| Cable_Clamp | Flat on the bed | None | A small bar with two screw holes. |

## Assembly order and fasteners

All printed joints are M3 screws into M3 heat-set inserts: 22 screws
(4 × M3 × 16, 14 × M3 × 8, 4 × M3 × 10) and 22 inserts. The Pi 5 screws
onto the display standoffs with the 4 × M2.5 screws supplied with the
display. The joint-by-joint table and the assembly order are in
[README.md](README.md), section 7. The speaker clamps now hold the accent
rings and grilles in place from inside.
