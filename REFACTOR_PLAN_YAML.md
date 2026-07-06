# BioScout — YAML + session-centric layout refactor

Goal: manage many subjects × sessions × **iterations** (model variants) cleanly,
with human-authored config in **YAML** and a one-command **summary across
iterations**. Do this deliberately, without breaking the working pipeline.

## 1. Core principles

1. **Raw once, derived per iteration.** Model-independent inputs (c3d, markers,
   GRF, EMG, EMG normalisation, trial window/events) are stored ONCE per session.
   Only model-dependent outputs (IK, ID, MA, SO, CEINMS, JCF) live per iteration.
   This removes the per-model duplication of raw data that caused the EMG/CEINMS
   tangles.
2. **An iteration = one model + its scale recipe + its results.** Free-form names.
3. **YAML for humans, XML only for tools.** OpenSim/CEINMS setup files stay XML
   because bioscout *generates* them; everything a person edits is YAML.
4. **Summary is iteration-agnostic.** It globs iteration folders, so adding a new
   variant needs zero code change.

## 2. Target folder layout

```
project/
  generic models/                # shared, immutable template library (referenced by `generic`)
    Catelli.../..osim  GPK/..osim  Rajagopal.osim   Geometry/
  setupFiles/                    # markersets, OpenSim setup templates
  simulations/
    Athlete_03/
      25_03_31/                                  # a SESSION
        c3dfiles/                                # RAW captures, once
          Static_01.c3d  Walking_02.c3d ...
        experimental/                            # PROCESSED, model-independent, once
          Walking_02/
            marker_experimental.trc  grf.mot  GRF.xml
            emg.mot  emg_filtered.mot  emg_filtered_normalised.mot
            trial_settings.xml                   # window / events / type
        session.yaml                             # session-wide config (see below)
        cateli/                                  # ITERATION (model-dependent only)
          model.osim  model_so.osim
          scale.stamp.yaml                       # AUTO-generated provenance (do not hand-edit)
          ceinms_calibration/
          Walking_02/                            # ik/id/ma/so/ceinms/jcf
        gpk_mri/                                 # another iteration, same experimental/ trials
        cateli_mvic3/                            # cheap variant: same generic, different recipe
      results/                                   # cross-iteration summaries for the session
```

Path roots (resolver convention):
  * `generic`       -> shared `<project>/generic models/<value>`  (NOT duplicated per session)
  * `session_model` -> session-relative `<session>/<value>`        (provided/personalised model)
  * `experimental/` and iteration outputs -> session-relative, produced by bioscout.

## 3. `session.yaml` schema

Authored source of truth. Reader/writer already implemented in
`bioscout/utils/session_yaml.py` (maps to the existing `SessionSpec`/`Model`
dataclasses — a drop-in for the old `session.xml`).

```yaml
subject: Athlete_03
session: "25_03_31"
body_mass: 89.9                 # subject-level; measured from static trial
static_trial: Static_01
markerset: setup/markers_powerlifter.xml
calibration_trials: [Walking_02, Squat_BW_01]
normalisation_trials: all       # or explicit list; "all" = every trial
emg_map:
  EMG_Channels_EMG01_vast_lat_l: [vaslat_l, vasmed_l, vasint_l]
ceinms: {alpha: 10, beta: 1, gamma: 1000}
trials:
  Walking_02: {type: walking, time_range: [0.10, 1.91]}
  Squat_BW_01: {type: squat}
iterations:                     # == model variants; UNIFORM keys across all
  cateli:
    generic: Catelli/..._PowerliftingMarkers.osim  # scale-from + muscle-opt reference
    session_model:                # empty -> produced by scaling from generic
    linear_scaling: true          # ScaleTool ModelScaler (dimensional)
    marker_placer: false          # ScaleTool MarkerPlacer (align markers to static)
    opt_neval: 10                 # Modenese muscle-opt sampling
    mvic_factor: 3.0              # isometric-force x factor at scale time
    label: "Scaled (Cateli)"
    color: green
    group: generic
  gpk_mri:
    generic: GPK/GPK_generic_modWO.osim            # muscle-opt REFERENCE template
    session_model: GPK/..._tps_Athlete_03.osim     # provided MRI/TPS (session-relative)
    linear_scaling: false         # geometry already personalised -> no dimensional scaling
    marker_placer: false
    opt_neval: 10
    mvic_factor: 3.0
    group: MRI
```

Notes:
- UNIFORM schema: every iteration has the same keys. `session_model` present ->
  geometric scaling skipped, that model is the input (muscle-opt still runs
  against `generic`, then MVIC x factor). Absent -> scale from `generic`.
- The `iterations` block IS the scale recipe — no separate `scale.yaml` to
  hand-maintain. Scaling reads it and produces `model.osim` / `model_so.osim`.
- At scale time, write a read-only `scale.stamp.yaml` into the iteration folder
  (resolved generic path, N_eval, MVIC factor, static trial, timestamp, bioscout
  version / git hash) for reproducibility.

## 4. Scaling as a per-iteration action

`scale(iteration)` reads its recipe and runs the existing three stages:
`geometric scale -> Modenese muscle-opt (opt_neval) -> isometric-force x mvic_factor`
(already implemented in `pipeline._run_scaling`), writing `model.osim` +
`scale.stamp.yaml` into the iteration folder. This is the "run the optimiser and
increase MVIC at the moment of scaling" behaviour, now driven by YAML.

## 5. Path resolver (the key adapter)

One place maps identity -> paths so nothing else hard-codes layout:

```
resolve(subject, session, iteration, trial) -> {
    raw_dir:     subjects/<S>/<Sess>/trials/<trial>/          # shared
    derived_dir: subjects/<S>/<Sess>/<iteration>/<trial>/     # per-iteration
    model:       subjects/<S>/<Sess>/<iteration>/model.osim
    calib_dir:   subjects/<S>/<Sess>/<iteration>/ceinms_calibration/
}
```

`Analyse` reads raw inputs from `raw_dir` and writes outputs to `derived_dir`
(instead of assuming everything is in one trial folder). This is the main code
change; most of the pipeline stays as-is once paths route through the resolver.

## 6. Summary across iterations

`summarise(subject, session)`:
1. glob iteration folders under the session,
2. load each iteration's SO / CEINMS / JCF for the shared trials,
3. emit comparison tables + figures (RMSE/R² vs a reference iteration, JCF
   overlays) and `metrics_long.csv` / `metrics_wide.csv`.

Adding an iteration = drop a folder + a YAML entry; the summary picks it up
automatically. This is the study's core deliverable (generic vs MRI vs measured
coordination).

## 7. Phased migration (do NOT big-bang)

- **Phase 0 (done):** `session_yaml.py` reader/writer + `session.xml` -> `.yaml`
  converter. Additive; nothing else touched.
- **Phase 1:** implement `resolve()` + teach `Analyse` to read raw from `raw_dir`,
  write to `derived_dir`. Keep the old flat layout working via a compatibility
  branch in the resolver.
- **Phase 2:** wire `Project`/`run_sessions` to build subjects from session YAML
  (`discover` sessions -> iterations) instead of `settings.py`.
- **Phase 3:** per-iteration `scale()` from the recipe + provenance stamp.
- **Phase 4:** iteration-agnostic `summarise()`.
- **Phase 5:** migrate `settings.py` project-level knobs into a top-level
  `project.yaml`; keep Python only for genuine logic, not data.
- Migrate ONE session first, prove parity against the current outputs, then roll
  out.

## 8. Open decisions

- EMG normalisation kept at **session level** (recommended) vs per-iteration.
- Whether body mass / markerset live only in `session.yaml` or also stamped per
  iteration.
- Exact `results/` figure set for the cross-iteration summary.
