# TPS Personalised Musculoskeletal Model — Review & Migration into BioScout

**Source reviewed:** `C:\Git\powerlifing_model_clean\models\tps` (local copy of
[katya-stanzy/thin-plate-spline_personalised_muscoloskeletal_model](https://github.com/katya-stanzy/thin-plate-spline_personalised_muscoloskeletal_model))
**Target:** `C:\Git\bioscout`
**Date:** 2026-06-23

---

## 1. What the TPS pipeline actually does

It builds a *subject-specific* OpenSim model by warping a generic model onto an
individual's MRI bone geometry using a **Thin-Plate-Spline (TPS)** transform.
The flow is a chain of 9 Jupyter notebooks plus ~4,700 lines of supporting
Python in `model_update/`:

1. `0_create_template` — build marker/bone-marker template from the generic model.
2. `1_extract_static_C3D` — export markers / GRF / EMG from a static C3D trial.
3. `2.0` / `2.1_use_mri_data` — load segmented MRI bone landmarks, match to OpenSim bone markers, run **per-bone TPS** (pelvis, femur L/R, patella L/R, tibia L/R).
4. `3_scale_generic_model` — standard OpenSim scaling to external markers + Handsfield muscle-volume force scaling.
5. `4_update_generic_model_with_mri_data` — apply the TPS transform to muscle path points, wrapping surfaces, joint centres, and skin markers; write the personalised `.osim`.
6. `5_optimize_muscles` — moment-arm-based muscle path optimisation.

The science is sound and the per-bone TPS classes (`OneBodyTPS`,
`GetPelvisAxes`/`GetFemurAxes`/`GetTibiaAxes`, `ScaleAndRecordData` in
`tps_scripts.py`) are the genuinely valuable, reusable core.

---

## 2. Biggest flaws

### Architecture & reproducibility
- **No package structure.** Flat `model_update/` folder of scripts + notebooks. No `__init__.py`, no installable package, no entry point. Importing the TPS logic elsewhere means copying files.
- **No version control in the working copy** and **no README / docs** — there is no narrative of how to run it end-to-end; the only "documentation" is notebook section headers.
- **Notebook-driven, not function-driven.** The actual orchestration lives in notebook cells (e.g. `2.0_use_mri_data.ipynb` runs the TPS body-by-body inline). This is not callable, not testable, and not batchable. `0.1_orientation_with_tps.ipynb` alone has 150 cells.
- **No tests at all.** A geometric transform pipeline with zero regression tests — a silent change in axis convention can corrupt every output undetected.

### Configuration & portability
- **Hard-coded, person-specific values in source.** `paths_setup.py` hard-codes `mass_text='89.9'`, `height_text='1.80'`, `age_text='33'`, plus subject filenames (`orientation_Katya.mrk.json`, `athlete_03.nrrd`, `2025-10-07-Scene.mrml`). Running a second subject means editing source.
- **Paths assume a fixed working directory** (`os.path.abspath('../')`). The notebooks only work if launched from `model_update/`.
- **Mixed unit conventions** left as commented-out code (`a[0]#*1000`) — a recurring mm/m ambiguity that is a classic source of silent error.

### Code quality
- **Side effects on import.** `paths_setup.py` creates directories and `OsimMusclePathsAndWrapping.__init__` runs parsing — importing the module does real work.
- **God-classes and copy-paste geometry.** `GetPelvisAxes`/`GetFemurAxes`/`GetTibiaAxes` repeat near-identical axis-construction logic; `optimization_grid.py` is a single 1,459-line file.
- **`runProgram` uses `shell`/subprocess with blocking stdout reads** and prints rather than logging — no structured error handling for OpenSim CLI calls.
- **Duplicated code across locations** (`tps_scripts.py` exists in both `model_update/` and `mri/results/`), so it is unclear which is canonical.
- **Typos in public names** (`muslce_paths_df`, `partcipant`) that would propagate into any API.

### Usability
- A new user must: install a heavy conda env (`environment.yml`, 163 lines, OpenSim + pyvista + tps + stan), manually segment MRI in 3D Slicer, hand-edit `paths_setup.py`, then run 9 notebooks **in order**, knowing which cells to skip. There is no CLI, no GUI, no single command, and no validation of inputs.

---

## 3. What BioScout already gives you (and why migration is the right move)

BioScout is a packaged, pip-installable app (`pip install -e .`, `python -m bioscout`)
with exactly the scaffolding the TPS project lacks:

- **A step-based pipeline runner** — `core/analysis_runner.py` with an `AnalysisStep` enum and `AnalysisRunner.run_step()` dispatch (already covers scaling → IK → ID → SO → muscle analysis → CEINMS → energetics).
- **Config & subject management** — `config/config_manager.py`, `settings.py`, `players.json` registry (`--add_player`), and per-player overrides. This directly solves the hard-coded-subject problem.
- **A project scaffold** — `--init` creates `simulations/<player>/`, `Models/`, `setup_files/`, `logs/`.
- **A GUI** — `gui/widgets/model_scaling.py` already exists; a TPS step would sit naturally beside it.
- **OpenSim helpers** — `utils.openSim`, batch mode, energetics, summary reporting.

The TPS personalisation is essentially **one new pipeline step that runs between
scaling and IK**: take the scaled `.osim` + the subject's segmented MRI landmarks,
produce a personalised `.osim`.

---

## 4. Migration steps

### Phase 0 — Salvage the core (do this first)
1. Extract only the reusable, side-effect-free logic from `tps_scripts.py`, `rotation_utils.py`, `wrap_scripts.py`, `simFunctions.py` (`scaleOptimalForceSubjectSpecific`, mass helpers — note BioScout may already have equivalents).
2. Strip every hard-coded path/subject value; convert module-level constants into function arguments.

### Phase 1 — Create a `bioscout.personalisation` (TPS) module
3. Add `bioscout/personalisation/__init__.py`, `tps.py` (the `OneBodyTPS` + per-bone axis classes, de-duplicated), `landmarks.py` (MRI `.mrk.json` / `.nrrd` import, currently `MRIBoneMarkers`), and `apply_transform.py` (warp muscle paths, wrap surfaces, joint centres, skin markers — currently notebook 4).
4. Reuse `tps` (PyPI) and `pyvista`; add them to `requirements.txt` and the `--install` dependency table.
5. Give each class a single clear responsibility and add type hints; fix the typo'd names.

### Phase 2 — Wire into the pipeline
6. Add `PERSONALISE_TPS = "personalise_tps"` to the `AnalysisStep` enum in `core/analysis_runner.py`, ordered **after scaling, before IK**.
7. Implement `_run_personalise_tps(self, config)` delegating to `Analyse.run_personalisation()`, mirroring the existing `_run_*` methods. Input: scaled model + `simulations/<player>/mri/`. Output: `personalised_model.osim` in the trial folder.
8. Make it **opt-in** via an `enable_personalisation` switch in `settings.py` + batch mode (same pattern as `enable_energetics`), since not every subject will have MRI.

### Phase 3 — Config, data layout & inputs
9. Store subject MRI/landmark paths in `players.json` (e.g. `mri_landmarks`, `mri_volume`), **not** in source — this is the key fix vs. the original.
10. Define a project sub-layout: `simulations/<player>/mri/{landmarks.mrk.json, segmentation.nrrd}` and document it in the README project-structure section.
11. Pull `mass`/`height`/`age` from the player registry (already collected by `--add_player`) instead of `paths_setup.py` literals.

### Phase 4 — GUI & CLI
12. Add a "Personalise (MRI/TPS)" panel to `gui/widgets/model_scaling.py` (or a sibling widget): pick landmarks file, run, preview the warped bones (pyvista/plotly).
13. Optionally expose `--personalise <player>` in `__main__.py` for headless runs.

### Phase 5 — Validation (critical — the original has none)
14. Add regression tests under `bioscout/tests/`: a tiny fixture model + known landmarks, assert TPS output marker positions within tolerance. This locks down the axis/unit conventions that are currently implicit.
15. Add an input-validation pass (units, landmark count/order, NaNs) that fails fast with a clear message — matching BioScout's "fail fast when OpenSim missing" philosophy.
16. Sanity-check: scaled-only vs personalised model should give plausibly close IK marker errors; flag large divergences.

### Suggested effort / sequencing
Phase 0–1 (salvage + module) is the bulk of the work and unblocks everything.
Phases 2–3 are small given BioScout's existing runner/config. Phase 5 should be
written **alongside** Phase 1, not deferred.

---

## 5. One-line summary

The TPS science is good but trapped in un-versioned, hard-coded, notebook-only code
with no tests; BioScout already provides the package, config, pipeline-runner, and
GUI it lacks — so port the per-bone TPS core into a new opt-in `personalise_tps`
step between scaling and IK, drive subject data from `players.json`, and add the
regression tests the original never had.
