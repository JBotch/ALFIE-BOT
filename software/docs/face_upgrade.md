# OLED face upgrade (v0.9): summary of changes

From the brief "AlfieBot V1: OLED Face Design & Animation Upgrade" and its reference image. Built on v0.8; nothing that worked before was removed.

## What changed

| Area | Files | Change |
|---|---|---|
| Expressions | `core/states.py` | 16 design expressions (`DESIGN_EXPRESSIONS`) plus Listening and Excited. Friendly aliases (`proud`, `idle`, `left`...) map to them. |
| Poses | `face/poses.py` | Rewritten. Each expression is a set of numbers (eye size, openness, lid cut and slant, arch, heart, pupil, rotation, eyebrows, mouth width/curve/open/round/wave/ring, glow) plus a `Behaviour` (blink timing, glances, bounce, pulse, ZZZ...). |
| Animation | `face/engine.py` | Rewritten. Exponential easing between poses with a configurable speed, random blinks within `face.blink_interval` (sometimes double), eyes that move together, `look_at`, `look_around`, idle flourishes, ZZZ particles, a mouth that follows the voice level or a timed pattern and settles back smoothly, `time_scale` for slow motion. |
| Drawing | `face/renderer.py` | Rewritten. Each eye is one 72-point outline morphed between a rounded square, an arch and a pixel heart; lids, pupils, eyebrows, a one-piece mouth outline, processing dots and Z particles. Supersampled for smooth edges with a blurred glow. Resolution independent: the face scales to any screen. |
| Controller | `face/controller.py` (new), `core/robot.py`, `core/actions.py` | The only things other code or an AI may ask the face to do. Approved expressions for AI replies (not Angry, Sleeping, Sleepy or Processing), and commands `look`, `look_around`, `blink`, `double_blink`, `talk_test`, each validated, with times clamped to 0.3-6 s. `robot.face_command()` queues them; the face view applies them on the next frame, so nothing waits on the face. |
| Talking mouth | `speech/base.py`, `speech/piper_tts.py`, `ui/face_view.py` | Speech engines can report a loudness level. Piper does, from the audio it plays; others report none and the mouth uses the timed animation. |
| Developer panel | `ui/face_test_panel.py` (new), `ui/simulator_app.py` | **Face test...** opens a panel under the robot screen: all expressions, blink, double blink, look left/right/up/down/around, mouth test, speed x0.25-x2, reset to neutral, demo of all 16. Preview keys are now 1-9. |
| Face-only app | `ui/face_app.py` | Keys 1-9; `--demo` and D cycle all 16 design expressions. |
| Settings | `config.py`, `config/alfiebot.json` | `face.blink_interval`: seconds between blinks, default `[2.5, 6.0]`. |
| Tools | `tools/render_expressions.py` | Also saves `expression_sheet.png` with all 16. |
| Tests | `tests/test_face_engine.py`, `tests/test_renderer.py`, `tests/test_face_controller.py` (new), `tests/test_states.py` | See below. |

## What the AI brain may ask for

| Situation | Expression |
|---|---|
| Listening | Listening (attentive, wider eyes) |
| Processing / waiting for the AI | Thinking |
| Speaking | The reply's mood, with the mouth moving |
| Success, praise | Happy, Excited, or Love / Proud |
| Asking a question | Curious |
| Uncertainty | Confused |
| Idle | Neutral |
| Sleep | Sleeping, with ZZZ (set by the robot's state, not by the AI) |

An AI reply asking for anything else (including Angry) gets Happy, and the substitution is logged in the AI panel.

## Tests

All 16 expressions render at three screen sizes; every morph keeps the shapes valid; eyes and pupils stay inside the face; blink intervals stay within the configured limits; looks and glances move both eyes and return to the front; the mouth moves while talking and settles back smoothly afterwards; unknown expressions and commands are refused; the AI can't ask for Angry or Sleeping; the face test panel's buttons and demo work; spelling still works with the panel open and the robot's face never shows spelling letters; both apps launch headless. 353 tests pass on Linux with Python 3.13 and pygame 2.6.1.

## Performance

On the Linux test machine one face frame takes about 14 ms at 1280x720 and 7 ms at 800x480 (3 ms with `"supersample": 1`). **Not measured on a Raspberry Pi yet.** If the Pi is slow, lower `display.supersample` to 1 or `display.glow` to 0 in `config/alfiebot.json`.
