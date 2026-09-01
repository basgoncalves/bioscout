# Moment-arm discontinuity check from a model (`mi_check`)

Checks a `.osim` model for moment-arm discontinuities over a trial's measured
kinematics — the wrap-surface flicker that linear scaling can create (found
2026-08 in the Powerlifting study: psoas/iliacus stepping 24–31 mm twice per
walking cycle in every linearly scaled model).

Unlike `moment_arm_motion` (which QCs already-solved MuscleAnalysis `.sto`
files), this computes the moment arms straight from the model with OpenSim, so
it runs BEFORE any pipeline stage — right after scaling, a TPS warp, or a wrap
edit.

## Use

```bash
# one fig06-style column: 7 muscle-group rows, X marks every discontinuity
python -m bioscout.muscle_inspect.model_ma_check scaled.osim \
    path/to/external_biomechanics/joint_angles.mot

# specific coordinates instead of the muscle groups; every spanning muscle drawn
python -m bioscout.muscle_inspect.model_ma_check scaled.osim joint_angles.mot \
    --dofs hip_flexion_r knee_angle_r --out qc/ --stride 2

# left side, custom thresholds
python -m bioscout.muscle_inspect.model_ma_check scaled.osim joint_angles.mot \
    --side _l --min-jump-mm 1.0 --step-mm 2.0
```

```python
from bioscout.muscle_inspect import check_ma_discontinuities
r = check_ma_discontinuities("scaled.osim", "joint_angles.mot")
r["flagged"]     # DataFrame: muscle, coordinate, max_step_mm, n_jumps
r["figure"]      # <model>_ma_discontinuity_check.png
r["table"]       # <model>_ma_discontinuity_check.csv (every muscle, not just flagged)
```

Also in the figures registry: `python -m bioscout.figures mi_check`.

## What it flags

A muscle-DOF pair is flagged when EITHER detector fires:

1. `detect_discontinuities` — the MAD-based jump detector shared with the
   other inspections (`--min-jump-mm`, default 1.0);
2. any frame-to-frame change above `--step-mm` (default 2.0 mm) — kept because
   a clean two-frame square jump (the psoas wrap flicker) can slip past a
   MAD threshold that two large jumps have inflated.

The CLI exits 1 if anything is flagged, so it can gate a pipeline.

## Figure

One column in the style of the Powerlifting fig06: rows are Gluteus maximus,
Iliopsoas, Gluteus med+min, Rectus femoris, Hamstrings, Vasti, Triceps surae,
each about its primary coordinate, arms in cm, knee/ankle sign-flipped into
the literature's frame, x = task cycle %. Flagged muscles are drawn thick,
labelled, with an X at each jump. With `--dofs`, rows are the requested
coordinates and every muscle whose peak |MA| ≥ 5 mm about that DOF is drawn.

## Notes

- `--stride N` evaluates every Nth frame for speed on long lift trials; the
  walking flicker persists over many frames, so stride 2–3 is safe there, but
  use stride 1 for a final gate.
- Needs `import opensim` at call time (msk311); the module imports without it.
- Validated against the 2026-08 defect: flags iliacus_r (31 mm, 2 jumps),
  psoas_r (25 mm) and a real 2.4 mm vaslat step on the broken GPK scaled
  model; only the vaslat step remains on the brim-radius-fixed model.
