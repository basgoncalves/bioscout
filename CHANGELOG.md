# Changelog

All notable changes to BioScout are documented here.

## [2.0.0b6] — 2026-07-31

### Fixed — `bioscout.utils.openSim` was None outside the CLI

`openSim.py` does a bare `import utils` (the legacy top-level copy of the
package), so the deferred `from . import openSim` at the bottom of
`utils/__init__.py` hits a circular import, is swallowed by `except Exception`,
and leaves `openSim = None`. Every caller doing
`from bioscout.utils import openSim as _os` then got None, and the first use
failed with `'NoneType' object has no attribute 'scale_model'` — naming neither
the module nor the cause. `bioscout/__main__.py` has carried a hand-rolled
workaround for this, which is why `bioscout --...` could scale a model and
`python settings.py` could not.

* **New** `bioscout.utils.get_openSim()` — resolves the module late (by which
  point the cycle is gone), falls back to an already-loaded copy under another
  name, and raises the ORIGINAL exception rather than handing back None.
* Rewired the four call sites: `pipeline.py`, `exportC3D.py`, and both in
  `session.py` (`Iteration.scale_model` and `Iteration.run`).

## [2.0.0b5] — 2026-07-31

### Fixed — every scaled model before this release was generic geometry

`openSim.scale_model()` built its `osim.ScaleTool()` from scratch and called
`ModelScaler.setApply(True)` **without ever populating a MeasurementSet**.
OpenSim accepts an empty one in silence: with nothing to measure, every body
keeps a scale factor of exactly 1.0 and the only thing `setSubjectMass()`
changes is the total mass. The output was still written to `scaled.osim`, the
logs said nothing, and IK, ID, MA, SO, CEINMS and JRA all ran on the generic
skeleton. Segment lengths, mass distribution, moment arms, joint moments and
contact forces from any earlier run are affected and must be recomputed.

* **New** `bioscout.utils.scale_measurements`:
  * `augment_static_trc()` — writes the joint centres a camera cannot see into
    a scaling-only copy of the static TRC: hips by the Harrington (2007) pelvis
    regression, knees and ankles as epicondyle/malleoli midpoints. This is what
    makes the `*WK` markers in `markers_powerlifter.xml` usable — they sit on
    body origins, so they are the joint centres in *every* model, which keeps
    the femur and tibia factors independent of which generic is being scaled.
  * `build_measurement_set()` — emits a Measurement only for marker pairs that
    exist in BOTH the model marker set and the TRC, and only for bodies the
    model actually has (Catelli has arms; GPK and Lernagopal have knee
    sub-bodies). Everything dropped is printed, not skipped quietly.
  * `verify_scaled()` — compares the result against its generic and says
    plainly when no body changed size.
  * `mass_from_static_grf()` — body mass from the static trial's vertical GRF.
  * `set_total_mass()` — mass and inertia only, geometry untouched.
* `scale_model()` now attaches that MeasurementSet, checks it actually landed
  on the tool, verifies the output, and writes the applied factors to
  `scale_factors.xml` in the iteration folder instead of a temp dir.
* **MRI/TPS models were never given the subject's mass.** With
  `linear_scaling: false` the model was copied through untouched, so it kept
  the generic's 75.34 kg while every result was normalised by the real body
  mass. Mass and inertia are now rescaled on their own.
* `Iteration.scale_model()` prefers the mass measured by the force plates over
  `session.yaml`'s typed-in `body_mass` (Athlete_03: 91.01 measured vs 89.9
  typed). Opt out with `body_mass_from_grf: false`.
* Joint centres are stripped from the marker set before marker registration —
  they are regression estimates and must not pull real markers around in IK.

## [2.0.0b1 - 2.0.0b4] — 2026-07-31

Beta series while the GUI restructure settles. The last digit moves on each
commit; this collapses to 2.0.1 when it merges to main.

### Added

* `bioscout.utils.motion_detect` — finds a trial's movement window from the
  barbell markers, falling back to pelvis markers, then vertical GRF, then the
  full capture. The 5%-of-bar-travel rule was **fitted to the hand-set windows
  already in Athlete_06's session.yaml**: it reproduces all five squats with
  end errors under 20 ms and starts 0.06-0.33 s early (the generous direction).
  Reproducing the existing convention was the acceptance test — detecting a
  *different* one and applying it to half a session would be worse than not
  detecting at all.
* `bioscout.utils.emg_analysis` — EMG power spectra with mains/artefact flags,
  and muscle synergies by NMF with the VAF-vs-count curve.
* GUI: **Trial Analysis** tab (per-trial stage status across every iteration,
  editable session.yaml block with a Detect button, per-trial re-run) and
  **EMG Analysis** tab (frequency + synergies, with channel selection).

### Changed

* GUI navigation follows the pipeline: Recording -> Video -> Trial Analysis ->
  C3D Export -> EMG Normalization -> EMG Analysis -> Model Scaling -> CEINMS
  Calibration -> Results. Session Analysis, Batch, Logs and the duplicate C3D
  Export tab are gone; the C3D preview panel is hidden.
* Results tab: Source -> Group -> File cascade instead of one ~200-entry list,
  plus a filter bar (Butterworth zero-lag / moving average / Savitzky-Golay)
  that applies at draw time and can save the filtered signals to CSV with the
  parameters recorded in the file.

### Fixed

* Results tab listed the layout's own folders (`1_c3dfiles`, `3_iterations`,
  `logs`) as trials, and a hard-coded `grid_rowconfigure(6, weight=1)` put the
  stretchy row on the "File" label.
* Trial stage detection keyed on guessed filenames, so Inverse Kinematics read
  as never-run on trials that had run it — IK writes `joint_angles.mot`.
  Detection now keys on the trial subfolder.
* EMG tab crashed on redraw: the matplotlib canvas was assigned to
  `self._canvas`, which `CTkFrame` already uses for its own drawing surface.
* Sidebar had gaps because `grid_rowconfigure(10, weight=1)` had become a nav
  button as tabs were added.

## [2.0.1] — 2026-07-30

Two new subpackages land in this release, plus the version scheme is repaired.

Numbering note: the tracked history runs 1.2.9 -> 2.0.0, so this continues from
2.0.0. The 2.4.x/2.5.x numbers that appeared in the working tree were never
committed and are not part of this series.

### Added

* `bioscout.tps_personalise` — TPS/MRI personalisation of a generic model,
  `bioscout --tps` for the guided version, with a v3/v4 `.osim` schema
  normaliser (`osim_format`) and a `model_compat` check that refuses to warp a
  model the bundled bone-landmark template was not authored for.
* `bioscout.change_moment_arms` — adjust a muscle's moment arm by wrap radius
  or path translation, `bioscout --change-moment-arms` for the guided version.
  A whole-model run now falls back from wrap to translation, keeps partial
  results with the achieved fraction reported, and ends with
  `inspection.inspect_change`: a before/after overlay per muscle, a summary
  CSV, and the standard `muscle_inspect` pass.
* `bioscout.utils.session_layout` — resolvers for the numbered session layout
  (`1_c3dfiles` / `2_experimental` / `3_iterations`), old flat layout still
  read.
* `Session.prune_legacy_inputs()` — drop the pre-YAML per-iteration `inputs/`
  copies, guarded so it can never delete the last copy.

### Fixed

* **The test suite was untracked.** `.gitignore` had a bare `tests/`, which
  matches at any depth, so all 8 files under `bioscout/tests/` were ignored and
  had never been committed. Anchored to `/tests/`.
* **Wheel installs shipped no TPS template.** `package_data` did not list
  `bioscout.tps_personalise`, so `data/markers_and_bone_markers_in_bodies.xml`
  was absent from the wheel (MANIFEST.in only governs the sdist). The
  `package_data` dict also had duplicate keys, where Python silently keeps the
  last — de-duplicated.
* **The settings version meant two different things.** A project `settings.py`
  was mirroring the *package* version while `check_settings_version` compares
  it against the *schema* version in the bundled template, so the two disagreed
  on every release. The schema version is now its own series (2.1.0) and the
  docstring says so.
* `_region` in `landmarks_from_mri` documents its "at least 4 points" floor;
  the test that asserted against a 4-point cloud — exactly the floor, where
  nothing can be selected — was rewritten to use a cloud the floor does not
  bind on.

### Changed

* The bundled `settings.py` template's runner now matches what a real project
  needs: `RUN_*` mode switches with a banner and a non-zero exit when they are
  all off, `DO_EXPORT`/`DO_MA` stages, the TPS block, the prune block, and the
  guards that turn a silent wrong-session run into an error.

## [2.4.2] — 2026-07-30

### Fixed — the solver assumed which way the parameter moves the moment arm

`solve_scalar_for_target` derived its search direction from the **sign of the
target**: a positive target grew the parameter, a negative one shrank it. That
is wrong whenever the moment arm itself is negative. About `hip_adduction`,
abductors (gluteus medius/minimus, TFL, gemelli, obturators, iliacus) have
negative moment arms, so scaling them up gives a negative target — and the
search shrank the wrap radius, which makes such a muscle's moment arm *less*
negative, i.e. straight away from the target. Every one of them ran to the 3x
limit and reported "the request is larger than this wrap can deliver".

The direction is now **measured**: one probe step, and the bracket then moves
whichever way actually approaches the target. Verified across all four
sign/route combinations plus a reversed-response case — every one converges to
x1.50 in 7-16 iterations where the negative-moment-arm cases previously all
failed.

Impact: a whole-model run adjusted only 4 of 80 scalable wraps and moved zero
path points. Any model produced by 2.4.0-2.4.1 is mostly unchanged from its
input and should be regenerated.

### Fixed — the ALL path never wrote the sibling model

Sibling syncing (keeping an iteration's SO and CEINMS models geometrically
identical) existed only on the single-muscle path. A whole-model run therefore
produced one model and silently left the paired one untouched. The ALL path now
offers it too, copying both the changed wrap radii and the moved path points.

## [2.4.1] — 2026-07-30

### Added — `--change-moment-arms` takes several coordinates at once

The prompt accepted one coordinate, so `hip_adduction_r,hip_adduction_l` was
read as a single (nonexistent) name and surfaced as "no muscle has a moment arm
> 1 mm" — pointing at the wrong problem. It now takes a comma- or
space-separated list, and a side-less name expands to both legs
(`hip_adduction` -> `hip_adduction_r`, `hip_adduction_l`), since bilateral is
the normal case.

`list_coordinates()` reads the coordinate names straight from the XML, so an
unknown name is caught **before** any sweep and answered with the coordinates
that do exist rather than an empty result.

Each coordinate is swept and batched in turn, accumulating into one model. When
a muscle spans more than one of the chosen coordinates the tool says so up
front and explains the consequence: it is solved once per coordinate against
the model built so far, so the last coordinate's target is the one that ends up
satisfied. Left/right sets are disjoint, so the usual bilateral run is unaffected.

## [2.4.0] — 2026-07-30

### Added — whole-model moment-arm scaling, and a working route for wrap-less muscles

`--change-moment-arms` now offers **ALL** as well as a single muscle, and
`apply_batch()` applies a target to every muscle spanning a coordinate,
accumulating the edits into one model. A muscle that fails is reported and
skipped rather than aborting the run.

**This needed the path-translation route to actually solve.** Only 58 of the 101
muscles in the GPK model have a scalable wrap; the other 43 include gluteus
medius, gluteus minimus and TFL — the primary hip abductors. A whole-model
change by wrap radius alone would have silently missed them.
`_best_translation_direction()` probes one small displacement per body axis with
a deliberately coarse sweep (ranking directions only), then the chosen direction
is solved at full resolution. The route used is always reported so a mixed batch
stays interpretable.

### Added — scale targets, not just offsets (`solve_scalar_for_target`)

For a whole-model change a fixed +mm offset is wrong: moment arms are signed, so
+5 mm grows the adductors and *shrinks* the abductors. A scale factor preserves
sign and grows every magnitude, which is what more muscle bulk does. Verified
against an analytic stub: x1.15 gives |MA| x1.150 for a positive-moment-arm
muscle and x1.148 for a negative one, where a signed +5 mm offset takes an
abductor from 44.0 to 39.0 mm. The ALL branch defaults to scale and explains why.

The solver also refuses rather than guessing: an unresponsive muscle fails to
bracket, and a near-zero baseline moment arm is rejected outright because a
scale factor on ~0 is meaningless.

## [2.3.1] — 2026-07-29

### Changed — `--change-moment-arms` reaches the models a session actually runs

The model picker listed only `generic models/`. Tuning is normally done on the
subject-scaled model an iteration runs (`3_iterations/<it>/scaled*.osim`), not
on the generic, so those are now discovered too.

### Added — sibling models are kept in step

An iteration runs a CEINMS model and an SO model. If only one gets the wrap
change the two force estimates are no longer comparable — which is exactly the
comparison these studies are built on. After a successful solve the tool now
lists the other `.osim` files in the same folder and offers to write the same
radii to them, with matching suffixes
(`scaled_opt_N10_mvicx3.00_ma.osim` / `scaled_opt_N10_ma.osim`).

## [2.3.0] — 2026-07-29

### Added — `bioscout.change_moment_arms`

Adjust a muscle's moment arm on a model, with the amount derived from measured
muscle volume rather than a guessed factor. Built for the powerlifting question
"larger muscle volume gives larger moment arms".

```
bioscout --change-moment-arms          # guided, same style as --tps
python -m bioscout.change_moment_arms
```

**Wrap radius is the primary mechanism, not path translation.** In OpenSim the
wrap surface *is* the geometric stand-in for muscle bulk: the path is held off
the bone by the cylinder, so its radius sets how far the line of action sits
from the joint axis. Growing it is the mechanism being modelled rather than a
proxy for it, the curve keeps its shape because the path still wraps, and the
change in where the path engages the surface moves the peak along the
coordinate on its own — so a left/right shift falls out instead of being
imposed. (An explicit left/right shift is available via
`paths.rotate_path_points`, but note it has no justification from muscle
volume: bulk changes the height of the curve, not where its peak sits.)

Muscles with no wrap on their path (glute medius/minimus in the GPK model) fall
back to `paths.translate_path_points`, which models the attachment moving — a
weaker claim, and the tool says which route it used.

Layout keeps OpenSim behind one seam, so all but one module is testable without
it: `wraps` (read/edit radii, pure XML), `paths` (translate/rotate points, pure
XML), `volumes` (NIfTI mask → radius factor), `solve` (bracket + bisect over a
caller-supplied measure callable), `core` (the OpenSim sweeps), `cli`.

Volume route: `V = pi r^2 L` with length fixed by the TPS bone geometry gives
`r_new/r_old = sqrt(V_subject/V_reference)`. This is a first-order geometric
argument, **not** an established scaling law — `volumes.py` says so, and it
needs stating as an assumption in any methods section.

The solver optimises the **mean** offset across the sweep, not the value at one
pose, because a single-pose match can be hit by a radius that distorts the rest
of the range. It refuses rather than guesses: an unreachable request, an
unresponsive wrap, or a non-finite moment arm all return `ok=False` with a
reason and the closest attempt, instead of silently writing a model that missed.

`list_targets()` uses a 1 mm floor rather than the 0.1 mm used by
`muscle_inspect.find_spanning_muscles`, so muscles that do not cross the joint
are not offered as adjustable — gastrocnemius shows ~0.2 mm of numerical
residue about the hip.

Every run re-checks for discontinuities afterwards, since inflating a wrap is
exactly the edit that pushes a path through a bone, and warns that the
force-length operating point moved with the moment arm.

### Fixed — `[ma]` output would have been dropped by `LOG_TYPE = "minimal"`

Pre-emptively whitelisted in `_KEEP_MINIMAL`, the same trap that silenced
`[prune]` in 2.0.4 and `[tps]` in 2.1.0.

## [2.2.0] — 2026-07-29

### Added — TPS personalisation inspects the model it just produced

A warp moves every muscle path point and every wrap-surface translation, so it
is precisely the operation that can introduce a discontinuous moment arm in a
model whose paths were clean beforehand. Checking is now part of producing the
model rather than a separate chore that has to be remembered.

`personalise_iteration(..., inspect=True)` (the default) runs the moment-arm
sweep on the warped model, writing the before/after plots and the literature
comparison to `muscle_inspect_<model>/`, plus a wrap-corrected
`<model>_modWO.osim` beside it. That corrected file is an **extra** to compare
against: the personalised model is left exactly as the warp produced it, and
`session.yaml` keeps pointing at it. Switching is a deliberate edit.

Also exposed as `bioscout --tps` ("inspect the model afterwards? [yes]") and as
`TPS_INSPECT` in the project's `settings.py`. Turn it off for a quick rebuild —
the sweep costs a few minutes per model.

New `bioscout_adapter.inspect_model()` wraps the sweep, and
`PersonalisationResult.inspection` carries the outcome
(`{ok, model, corrected, figures, reason}`).

**A failed inspection never invalidates a good warp.** Missing `opensim`, a bad
argument, or a `SystemExit` from the sweep are caught and reported; the model
stays written and the message names the command to run the check by hand. The
working directory is restored either way, since the sweep resolves relative
paths against it.

## [2.1.1] — 2026-07-29

### Fixed — stray `models/<something>/` folders created from positional path slicing

`Analyse` derived a trial's subject and session by slicing fixed positions off
the trial path (`parts[-3]`, `parts[-2]`, `[-3:-1]`). A trial sits at
`<subject>/<session>/<iteration>/<trial>`, so those positions actually yielded
`<session>/<iteration>` — wrong even in the flat layout, where it silently
created an empty `models/<session>/<iteration>/`. With the numbered layout the
trial sits one level deeper and it became `models/3_iterations/<iteration>/`.

New `analysis.subject_session_for_trial()` walks the structure instead,
stepping over the `3_iterations/` level when present, and is used by all four
affected call sites:

- the `models/<subject>/<session>` creation in `Analyse.__init__` (which also
  now only creates that folder when the project actually uses that convention —
  i.e. `models/<subject>/` already exists — so session-centric projects get
  nothing created at all);
- `self.subject` / `self.session`, which were being set to the session and
  iteration names respectively;
- the available-`.osim` lookup in the model fallback, which was listing a
  directory that could never exist;
- `Subject.trial()`'s `t.session`, which was being set to the iteration name.

`[-2]` (the iteration folder, used to pick knee-joint column naming) is
genuinely correct in both layouts and is unchanged.

## [2.1.0] — 2026-07-29

### Added — `bioscout --tps`, interactive TPS personalisation

A guided prompt rather than a config file, because this is a once-per-subject
operation whose inputs are exactly the things nobody remembers the spelling of:

```
bioscout --tps                 # from the project root
bioscout --tps <project path>
```

It discovers the sessions, the iterations and any `mri/**/*.mrk.json`, offers
each as a numbered menu with a default, prints a summary, and writes nothing
until that summary is confirmed. Enter accepts every default, so the common
case is all-Enter. Only the *generic* iterations are offered as the model to
warp — a `*_mri` iteration names the file this step produces, it is not an
input to it.

### Fixed — `[tps]` output dropped by `LOG_TYPE = "minimal"`

Same trap as `[prune]` in 2.0.4: `_KEEP_MINIMAL` is a whitelist, so the
completion summary ("done — N bodies warped", "wrote <model>") was discarded
from both console and log, and a successful run looked like it had done
nothing. Now whitelisted.

## [2.0.6] — 2026-07-29

### Fixed — `personalise_iteration()` could never find an iteration

`bioscout_adapter._iteration_spec()` read `spec.iterations`, which
`SessionSpec` does not have — its iterations are a `models` **list** of `Model`
objects (`get_model()` / `model_names()`). Every call failed with
`KeyError: "iteration '<name>' not in session.yaml (have: none)"`, so the
BioScout entry point to the TPS personalisation had never worked. It now uses
`spec.get_model()` and falls back to the session's raw YAML.

`_resolve_generic()` had the same problem, using a `session.project_dir` that
does not exist; it now goes through `Iteration._resolve_model_file()` (which
searches every base bioscout uses) with `resolve_generic()` as a fallback.

### Changed — `geometry_dir` is no longer a required input

`validate_inputs()` refused to run when the generic model's `Geometry/` folder
was absent, even though bone-mesh warping is optional (it needs `pyvista`) and
already degrades to "keep the generic surfaces, log it". A missing
`geometry_dir` now warns; joint centres, muscle paths and wraps — everything
that affects a simulation result — are still personalised.

## [2.0.5] — 2026-07-29

### Fixed — Lerner-knee joint centre written into the wrong frame

`MODEL_PRESETS["lerner_knee"]` (added in 2.0.1) mapped the knee centre onto
`Lerner_knee_r/femoral_cond_r_offset` and `fem_pat_r/femoral_cond_r_offset`.
Those offsets are expressed in the **femoral condyle body's own frame** and are
legitimately `(0, 0, 0)`; the femur->condyle placement lives in the
`femur_weld_r` joint, whose `femur_r_offset` is in the femur frame (generic:
`0, -0.404, 0`).

Writing the femur-frame landmark `knee_r_center_in_femur_r` (~0.40 m distal of
the hip) into a condyle-frame offset displaced the knee, patella and entire
shank by ~40 cm. The mapping now targets `femur_weld_r/l`, and
`Lerner_knee_*`/`fem_pat_*` are deliberately left generic — the template has no
landmark expressed in condyle-local coordinates, so personalising them
correctly is not currently possible.

The upstream config carried this mapping as a commented-out block labelled
"Uncomment + verify"; it was enabled in 2.0.1 without that verification.
Affects Lerner-knee models only (GPK, Lernagopal); walker-knee models
(Rajagopal2015, Catelli) were always correct, since their `femur_r_offset`
genuinely is in the femur frame.

**Any Lerner-knee model personalised with 2.0.1-2.0.4 must be regenerated.**

### Fixed — written models lost their XML declaration and all comments

`write_personalised_model()` used a plain `ET.parse()`/`tree.write()` round
trip, which drops the `<?xml ...?>` declaration and **every** `<!--...-->`
property description OpenSim ships in its models — 5,665 of them in the Catelli
model, halving the file size. Comments are cosmetic but they are what makes an
`.osim` readable, and the missing declaration is a real interoperability risk.
The parser now keeps comments (`TreeBuilder(insert_comments=True)`) and the
writer emits the declaration.

Only visible when `opensim` is absent: with it installed, the validation step
re-serialises the model through the OpenSim API and produced a correct file
regardless.

### Fixed — WeldJoint ignored by the joint-centre writer

`write_personalised_model()` walked only `CustomJoint` and `PinJoint`, so a
mapping naming a `WeldJoint` (such as `femur_weld_r`) could never be applied and
was reported as "not found in this model". `detect_joint_centre_preset()` was
likewise blind to weld joints. Both now include them.

## [2.0.4] — 2026-07-29

### Fixed — maintenance-command output swallowed by `LOG_TYPE = "minimal"`

`utils/shared._KEEP_MINIMAL` is a whitelist: in `minimal`/`quiet` mode any line
it does not match is dropped from **both** the console and the log file.
`[prune]` and `[reset]` were not on it, so `Session.prune_legacy_inputs()` and
`Session.reset()` produced no visible output whatsoever — the command looked
like it had silently failed, when it had run correctly and simply had nowhere
to report to. `[prune]`, `[reset]` and `[settings]` are now whitelisted.

These are commands the user invokes deliberately and whose entire point is the
report, so they must never be filtered as chatter.

## [2.0.3] — 2026-07-29

### Added — `Session.prune_legacy_inputs()`

Removes the pre-YAML `<iteration>/<trial>/inputs/` folders, where every model
kept its own copy of the raw c3d/markers/GRF/EMG. Those are exported once into
the shared experimental folder now and nothing reads the per-model copies, but
nothing deleted them either — a single session was carrying 153 MB of them.

`_rm_empty_inputs()` was supposed to cover this and was **never called from
anywhere**; it also only handled *empty* folders, so every non-empty one
survived. It is now superseded.

This is the inverse of `reset()`, which *keeps* `inputs/` and deletes derived
output. Safety: a trial's `inputs/` is only removed when the shared export for
that trial exists and holds the marker TRC, so the last copy can never be
deleted; failures are reported and skipped. Defaults to `dry_run=True`, and
`archive_dir=` moves folders aside instead of deleting — worth using, since a
legacy `inputs/` file may be an *earlier* export rather than a byte-identical
duplicate.

### Fixed — two paths still assuming the flat layout

Both silently returned nothing after a session was migrated to the numbered
layout, rather than failing:

- `Session.summarise()` filtered iterations by `<session>/<name>`, so on a
  migrated session every iteration looked absent and the cross-model figures
  came out empty.
- `Session.reset()` scoped its trial walk to `<session>/<iteration>`, so it
  found no trials to reset and reported success having done nothing.

Both now resolve through `session_layout.iteration_path()`.

## [2.0.2] — 2026-07-29

### Added — numbered session layout (`utils/session_layout.py`)

A session's folders are now ordered by pipeline stage::

    <session>/1_c3dfiles/            raw captures
              2_experimental/        model-independent exports, written once
              3_iterations/<name>/   one model variant per folder
              logs/  results/ ...

**Both layouts are supported.** Every path resolver prefers whatever already
exists on disk and only *writes* the numbered names, so existing sessions,
other projects and collaborators' copies keep working untouched. A
half-migrated session (some folders renamed, some not) resolves correctly too.
`experimental_dir`, `c3d_path`, `iteration_dir`, `derived_trial_dir`,
`Session.iterations`, `Iteration.path`, `Model.c3d_dir`,
`pipeline._c3d_for_trial` and `exportC3D.export_session` all route through it —
join those folder names by hand and the two layouts drift apart.

`export_session`'s `c3d_dirname` / `out_dirname` now default to `None` (resolve
from the session) instead of the hard-coded `"c3dfiles"` / `"experimental"`. An
explicit value still wins, which is how a downsample run redirects output.

### Added — session.yaml is parsed strictly (`load_session_yaml`)

Two silent corruptions are now errors:

- **Duplicate keys.** PyYAML keeps the *last* value for a repeated key, so two
  `gpk:` blocks collapsed into one and the first block's generic model, colour
  and CEINMS settings vanished with no warning. The error names the key and the
  line.
- **Iteration names differing only by case or whitespace.** `GPK` and `gpk` are
  distinct in YAML but the same folder on Windows, so they overwrote each
  other's results.

Both `session_spec_from_yaml` and `Iteration._read_yaml` route through it.

## [2.0.1] — 2026-07-29

### Added — `bioscout.tps_personalise`

Thin-plate-spline personalisation of OpenSim models from segmented MRI bone
geometry is now part of bioscout (ported from the standalone `tps-personalise`
package, itself a refactor of Ekaterina Stansfield's notebook pipeline). Per
bone, a TPS is fitted from the generic model's bone landmarks onto the
subject's MRI landmarks and applied to muscle paths, markers, wrap surfaces,
joint centres and bone meshes.

- `personalise_iteration(session_dir, iteration, mri_landmarks=...)` reads
  `session.yaml`, resolves that iteration's generic model and writes
  `<generic stem>_tps_<subject>.osim` beside it.
- CLI: `python -m bioscout.tps_personalise --config config.yaml`, plus the
  `tps-personalise` / `tps-landmarks` console scripts.
- The bone-landmark template ships with the package
  (`tps_personalise/data/markers_and_bone_markers_in_bodies.xml`).

### Added — OpenSim 3.x model support (`tps_personalise/osim_format.py`)

Markers, path points, joint centres and bone meshes are now read and written on
both the 3.x and 4.x schemas. `Rajagopal2015.osim` as distributed is a Version
30000 document; previously it parsed as an empty model (0 path points, 0
markers) with no error raised.

### Added — bone-frame compatibility checking (`tps_personalise/model_compat.py`)

A bone-landmark template stores landmarks *in a model's body frames*, so
reusing one across generic models is only valid when those frames coincide.
`compare_bone_frames()` verifies this by checking both models attach the same
bone meshes to the same bodies, unscaled and untransformed, and the check runs
before any warping — an incompatible template does not error downstream, it
silently yields a wrong model. GPK, Catelli, Lernagopal and Rajagopal2015 all
verify as compatible, so one template covers all four.

### Added — joint-centre presets

`MODEL_PRESETS` + `detect_joint_centre_preset()` select the joint wiring from a
model's own joint names (`walker_knee` for Rajagopal/Catelli, `lerner_knee` for
GPK/Lernagopal). Previously the walker-knee map was the hard default, so
Lerner-knee models kept their generic knee centres and only logged a warning.

### Fixed

- `Iteration.run()`'s `do_muscle_analysis` parameter was spelled
  `do_muscle_analsysis`. Since unknown kwargs fall into `**_ignored`, callers
  passing the correct spelling were silently dropped and the flag never took
  effect. The correct spelling is now the parameter name and the old one is
  accepted as an alias.

### Changed

- No third-party TPS dependency: `_tps_backend.py` implements the spline in
  numpy and is used automatically when `thin-plate-spline` is absent. The
  external package is still preferred when installed.
- `PathWrap` → muscle links are resolved for any muscle class, not just
  `Millard2012EquilibriumMuscle`; Thelen-based models previously lost every
  wrap/muscle association.
- `MovingPathPoint`s are explicitly skipped when warping (their location is a
  function of a coordinate, so warping the constant would corrupt the model).

### Tests

`bioscout/tests/tps_personalise/` — 40 passing, covering both schemas, the TPS
backend (exact landmark interpolation, affine reproduction) and the frame
checks. One pre-existing failure in `test_landmarks_from_mri` was inherited
from the standalone package and is unrelated to the personalisation path.

## [1.2.0] — 2026-06-14

Big release: a full **energetics** path, a **`--summary`** reporting module, an
EMG time‑base fix, and a first **basketball shot‑analysis** prototype
(computer‑vision → kinematics → muscle forces).

### Added — OpenSim energetics
- `utils.openSim.run_energetics`: attaches an **Umberger (2010)** metabolic‑energy
  probe set to the scaled model and runs a `ProbeReporter`
  (`energetics_ProbeReporter_probes.sto`).
- `Analyse.run_energetics` wrapper and an `enable_energetics` switch wired into
  batch mode (`bioscout/__main__.py`).
- Batch mode now **fails fast with a clear message** when OpenSim is not
  importable, instead of erroring on every step.

### Added — `python -m bioscout --summary`
- New `utils/summary.py`: per‑trial **and** overall (grouped by movement type)
  kinematics / kinetics / muscle summaries.
- One **column per joint** with left + right overlaid (left = red, right = blue).
- Rows: joint **angle** (with per‑joint, per‑side **marker‑error** box), **EMG**,
  joint **moment** vs summed muscle moment, **moment arms**, **muscle forces**,
  **activations** (EMG shaded behind), **energetics** — empty panels where data
  is absent. Per‑muscle rows show **agonist (+MA) / antagonist (−MA)** means.
- EMG uses `emg_filtered_normalised.mot` (falls back to filtered, then raw).
- CLI: optional settings path (`--summary "<proj>/settings.py"`), `-s` (player),
  `-t` (single trial), `-overall`. New `SummarySettings` class in `settings.py`.

### Fixed — EMG processing
- `Analyse.run_emg_filter` now derives the EMG **sampling rate from the data's own
  time column** (true analog rate) instead of a fixed setting, and no longer
  overwrites a valid time vector — fixes degenerate (all‑zero) timestamps that
  flattened the EMG in the summary.

### Added — Basketball shot analysis (prototype) — `python -m bioscout --shots VIDEO`
- 2‑D pose via BioScout's MediaPipe tracker; per‑shot segmentation.
- Three detection paths: pose **ball‑flight**, and an **avishah3‑style hoop**
  method (ball + hoop → up/down/through‑rim **attempt + make** scoring) with a
  **YOLO** (`--yolo-model`) detector or an HSV + manual `--hoop CX,CY,W,H` fallback.
  (after Shah, *AI Basketball Shot Detection Tracker*.)
- Per‑shot **kinematics on a smooth 0–100 %** axis (1000 pts, configurable).
- **Kinematics‑only muscle‑force surrogate** (`models/kinematics_only_model.pkl`,
  numpy MLP) — *low fidelity, see limitations.*
- **Assisted made/missed tagging** (`shots.csv`), release thumbnails, annotated
  **score frames** (rim + predicted path + IN/OUT), and a combined per‑shot
  **card**: release (stick figure + joint angles + **release angle**) | shot path.
- `--fps`, `--min-gap`, `--n-points`, `--hoop-side`, `--shooting-hand` CLI flags.

![Shot analysis card](bioscout/utils/shot_analysis_card.png)

*Per‑shot card: stick figure + joint/release angles on the left, ball path and
IN/OUT on the right (stick figure shown is a placeholder; a real run uses MediaPipe).*

### Known limitations / still missing
- **Shot detection needs ~30–60 fps.** At 5 fps the ball crosses the rim in ~1
  frame, so the hoop method misses rim passes; use a high‑fps clip.
- **Ball identification needs YOLO.** HSV alone can't isolate the game ball from
  the ball rack / court logos; a trained ball+hoop model is required for robust,
  fully‑automatic detection.
- **Muscle forces from video are low fidelity.** A kinematics‑only model can't
  recover absolute force (cross‑subject R² is poor — force scales with subject
  strength/size). Needs richer inputs (moments/EMG) or per‑athlete calibration.
- **2‑D joint angles** are image‑plane only — valid when the shooter is roughly
  side‑on to the camera; wide/distant broadcast footage degrades pose badly.
- **Energetics probe API** not validated across all OpenSim versions; **CEINMS**
  depends on external executables being installed.
- Hoop is static/manual or per‑frame YOLO; no automatic rim auto‑detection yet.

## [1.1.x] — earlier
- PyPI packaging, image URL fixes, batch pipeline, GUI, OpenSim C3D→CEINMS pipeline.
