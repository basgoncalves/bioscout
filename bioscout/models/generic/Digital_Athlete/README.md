# Digital Athlete model

`Digital_Athlete.osim` = personalised lower limb + pelvis from `GPK_v4_016.osim`
grafted onto the full upper body / spine / ball from `Full_Body_with_ball.osim`,
with the complete muscle set from both.

## Why this merge works

Both source models share the exact same body and joint names/architecture for
the entire lower limb (the "Lerner knee" template: `pelvis`, `femur_r/l`,
`femoral_cond_r/l`, `tibia_r/l`, `patella_r/l`, `talus_r/l`, `calcn_r/l`,
`toes_r/l`, and joints `ground_pelvis`, `hip_r/l`, `Lerner_knee_r/l`,
`ankle_r/l`, `subtalar_r/l`, `mtp_r/l`, etc.). All 101 muscles in
`GPK_v4_016.osim` also exist under identical names in `Full_Body_with_ball.osim`.

So the build script (`build_digital_athlete.py`) starts from
`Full_Body_with_ball.osim` (it already has the full muscle set: 575 muscles,
spine, shoulder girdle, arms, ball) and replaces, by name, every lower-limb
`Body`, `Joint`, and `Muscle` block with GPK_v4_016's personalised version.
Everything above the pelvis (sacrum, lumbar1-5, torso, Abdomen, shoulder
girdle, arms, hand, ball, and the ~474 non-leg muscles) is kept untouched.

Before writing the script we confirmed (by diffing the two source files):
- no *kept* (non-leg) muscle references a wrap object that lives on a body
  being swapped
- the only kept joint touching the swap boundary is `sacrumjnt`
  (pelvis -> sacrum)

## Known limitation — check this in the GUI

`sacrumjnt` keeps `Full_Body_with_ball`'s original `pelvis_sacrum_offset`
frame (translation relative to the pelvis). That offset was tuned for the
generic Full_Body pelvis, **not** rescaled to GPK_v4_016's personalised
(scan-derived) pelvis geometry. The model will load and run fine (all
references resolve), but the spine's attachment point on the pelvis may sit
slightly off the personalised bone surface. Open the model in the OpenSim
GUI and visually check the sacrum/L5-S1 attachment against the pelvis; if it
looks off, adjust `pelvis_sacrum_offset`'s translation in `sacrumjnt`
(search for `sacrumjnt` in the .osim XML) to match the personalised pelvis.

## Rebuilding

```
cd "bioscout/models/Digital Athlete"
python3 build_digital_athlete.py
```

Reads `../GPK_v4_016.osim` and `../Full_Body_with_ball.osim`, writes
`Digital_Athlete.osim` in this folder. Re-run any time either source model
changes (e.g. a new GPK version) — edit the two `_PATH` constants at the top
of the script if you want to point at a different GPK version.

## Verified on build

- 53 bodies, 53 joints, 575 muscles — same counts/names as `Full_Body_with_ball.osim`
- all 23 swapped bodies/joints and 101 swapped muscles come from `GPK_v4_016.osim`
- output XML parses cleanly (`xml.etree.ElementTree`)
