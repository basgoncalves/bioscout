# Changelog

All notable changes to BioScout are documented here.

> **Versioning.** 2.0.0 is a **normal release** — `pip install bioscout` picks
> it up, no `--pre`. It is still beta software, and says so through the
> `Development Status :: 4 - Beta` classifier rather than through a `bN` version
> suffix: a PEP 440 pre-release is hidden from the PyPI landing page and skipped
> by pip's resolver, which was hiding the 2.x line rather than qualifying it.
> The `2.0.0bN` betas stay in the release history. Breaking changes are still
> possible in 2.x while the session/iteration API settles; they get a minor bump
> and a note here.

## 2.0.0c1 — 2026-08-17 (unreleased, branch `implementations-c1`)

Post-2.0.0 work driven by the Powerlifting and FAIS studies — see
`docs/IMPLEMENTATIONS.md` for the full field-tested bug list and roadmap.

### Added
- **GUI: per-machine settings + Settings tab.** `gui/gui_settings.py` →
  `~/.bioscout/gui_settings.json` (UI scale, theme, window memory, last-used
  folders, C3D-export form state). Deliberately NOT ConfigManager, which
  writes back into the installed package. The split: data settings →
  `session.yaml`, machine settings → `gui_settings.json`. UI scale applies
  widget+window scaling before construction; plain-Tk widgets take
  `font_size()` at build and follow on reload ("Apply cleanly" button).
- **GUI: sidebar sections.** Record / Data curation / Simulations / Results /
  Project, replacing the flat 11-button list and its hand-numbered grid rows.
- **GUI: merged EMG tab** (`gui/widgets/emg_tab.py`) — Filtering
  (EMGProcessingTab, `show_mvc=False`) + Analysis (frequency/synergies) behind
  one nav entry, left sub-tab rail, children built lazily.
- **C3D Export: post-export step.** Two persisted checkboxes: update
  `session.yaml` (scaffold if missing, `SessionForm` surgical `emg_filter:`
  write, backup first) and run movement detection (`classify_session`,
  corrects trial types with backup). Session root resolved from the
  destination; anywhere unrecognised skips with a message rather than
  scaffolding in a random folder.
- **C3D Export: EMG scaling on export** (uniform or per-muscle; "From Max
  EMG" fills 1/peak; blank/zero/junk factor → 1.0, never wiping a channel),
  Max-EMG table with per-trial peak-% columns in a both-ways-scrollable
  monospace view, and folder/marker/channel/filter persistence.
- **Model Scaling: models-folder layout.** `scaling_defaults` resolves the
  generic against `models/generic/` (legacy `generic models/` still works),
  the markerset against `models/utils/`, and defaults the scaled output to
  `models/personalised/<subject>/<generic>_scaled.osim` — one scaled model
  per subject instead of a copy per session.

- **`bioscout.plot` — generic comparison figures** (`docs/PLOTTING.md`). The
  ranked muscle-work figure existed in three project-local copies that differed
  only in what the columns were, so the columns and rows became arguments:

  ```python
  (bs.plot("results/master_results.csv")
     .where(Variable="muscle_work_total", Algo="SO")
     .compare("Condition", order=["pre-fatigue", "post-fatigue"])
     .facet("Task", icons=TASK_ICONS).group(bs.plot.MUSCLE_GROUPS)
     .top(8).save("results/group/work_ranks.png"))
  ```

  Three layers, each usable alone: `plot.work` (.sto -> joules, four work
  phases, `work_table()`), `plot.tidy` (the long-table contract every figure
  reads), `plot.compare` (the `Compare` builder, ranked bars or mean±SD
  curves). Bar colour is anchored on the first compared column and carried
  right, so colour disorder IS a re-ranking; `normalise="reference"` keeps the
  magnitudes, `normalise="panel"` throws them away. **No project settings file
  is involved** — the house style lives in `bioscout/plot/config.py` and a
  notebook overrides it with `bs.plot.configure(...)` / `bs.plot.using(...)`
  / `.set(...)`. numpy + pandas + matplotlib only: no OpenSim, no scipy.
  `bioscout/tests/test_plot.py`, 21 tests, including the work integral pinned
  against cases with exact answers.
- **`dir(bioscout)` now lists the public API.** The lazy `__getattr__` that
  keeps `import bioscout` light also hid every name from `dir()`, so notebook
  tab-completion on `bs.` offered nothing but `test` and `__version__`. A
  `__dir__` advertises `__all__` explicitly; `bioscout.plot` and
  `bioscout.pipeline` are both reachable as lazy submodule attributes.
- **Shared model library.** `so_model` / `ceinms_model` resolve: absolute
  path -> iteration folder -> session folder -> `<project>/models/`. One
  scaled model per subject serves every session/iteration; a per-iteration
  copy still wins when present. A model that resolves nowhere now WARNS
  instead of silently leaving the trial without a model.
- `BIOSCOUT_LOG_DIR` env var: one folder for every log of a project;
  `BIOSCOUT_LOG=0` disables bioscout's own file logging when a parent
  process already tees all output (one run = one log file).

- **`bioscout -test`** (also `--test`/`--tests`) runs the packaged suite and
  exits with unittest's status — handled before the heavy imports, so it
  starts instantly and still reports in a half-built environment.
- **Scaling ignored `session.yaml`'s `static_trial:`** — `scale_model`
  defaulted to a hardcoded `"Static_01"`, so a session whose static trial is
  named anything else (`static1`, the FAIS convention) scaled against a trial
  that does not exist: "static TRC not found", no model written, and every
  IK/ID/MA/SO/CEINMS stage failing for every trial — with the session file
  naming the right trial all along. The session now owns the name.
- **c3d export failed for any trial never analysed before.** `export_c3d`
  writes into the shared `2_experimental/<trial>/`, but the loop then
  `chdir`-ed into the ITERATION's trial folder, which does not exist yet for
  a fresh trial — `WinError 2`, reported as `[export ERROR]` for every such
  trial. The bare folder is created first (no stage scaffolding).
- **`bioscout run` discovers trials from session.yaml** when nothing names
  them (no `--trial`, empty `BatchSettings.trial_list`) — static and
  normalisation-only trials excluded. Before, the run printed `trials=[]`
  and every stage loop silently did nothing, which read as a clean run.
- **Per-stage flags on `bioscout run`** — `--scale`, `--exbiomec`, `--so`,
  `--ceinms` (legacy forms `--do-*`). No stage flag = the full pipeline (SO +
  CEINMS, unchanged); ANY stage flag = only the named stages. This is what
  replaces the `DO_SO`/`DO_CEINMS` block in a project settings.py: run
  selection is stated at the call site each time, never persisted in a file.
  `--scale` closes the last gap that forced people out of the CLI —
  `bioscout run <subj> --session <s> --export --scale --exbiomec` is now the
  whole chain for a session that has never been analysed (`run_subject`
  gained the matching `do_scale=` parameter, run after export and before the
  solve stages). The run summary line reports every stage's count, not just
  SO and CEINMS.
- **`project.yaml` replaces the copied per-project `settings.py`**
  (IMPLEMENTATIONS §2.9 steps 1+2). `utils/project_config.py` applies the
  nearest `project.yaml` on top of whatever settings resolved, so every
  consumer of `utils.settings` sees session.yaml → project.yaml →
  settings.py (legacy) → bioscout defaults; `bioscout project init` extracts
  a project's settings.py into `project.yaml` (data-only lab facts that
  differ from bioscout's defaults — run selection and paths are never
  persisted). After a review run the settings.py can be deleted; a legacy
  settings.py keeps working with a one-line deprecation note.

### Changed
- **All run logs land in `<project>/logs/`** as uniform
  `bioscout_<date>_<time>.txt` — `Session.open`/`Iteration.open` no longer
  scatter per-session `logs/` folders; the heading inside the file names the
  run.

### Fixed
- **C3D Export wrote raw EMG under a filtered name.** `emg_filtered.mot` was a
  byte-for-byte COPY of `emg.mot`; the Low/High/Notch fields only drove the
  preview. Now filtered for real (same envelope maths as the preview; NaNs
  zeroed, never dropped — dropping desynchronised the time column). Also
  `trial_settings.xml` pointed at `emg_filtered_normalised.mot`, which nothing
  ever wrote — now `emg_filtered.mot`.
- **Launch time.** A silent `pip install` at import (network, before the
  window painted), scipy+matplotlib imported at startup by the C3D Export
  module, and mediapipe/cv2/matplotlib pulled in eagerly by Recording / Video
  Analysis / Training Tracking. All deferred to first use.
- **Notebook output vanished after `bs.Project()`.** `start_logging` teed onto
  `sys.__stdout__` — the kernel process's terminal, not the cell. It now tees
  onto the CURRENT stdout, unfiltered in notebooks (`bioscout/tests/
  test_logging.py` pins both failure modes).
- **Terminal twin of the same bug**: a plain
  `python -c "...; print('run ok:', ...)"` never showed its final print — the
  LOG_TYPE="minimal" whitelist ate it. The filter now applies ONLY when
  bioscout's own CLI owns the console (`__main__` sets
  `BIOSCOUT_LOG_FILTER=1`); library use — notebooks, scripts, `python -c` —
  passes everything through raw.
- **`Iteration.run(skip_done=...)` was a dead parameter** — accepted,
  documented, never read (skipping is a per-stage mtime decision, and each
  gate already logs its reason). Removed; passing it now prints a note
  instead of silently doing nothing.
- **"No model found" warning listed the same candidate twice** (`so_model`
  consulted under both its own key and the requested key), and the trial then
  ran with whatever stale `model_dir` sat in its `trial_settings.xml` — often
  a legacy `../../models/<subject>/<session>/scaled.osim` path, so the
  eventual "Model file not found" error named a ghost. Deduped, the warning
  now names the personalised/generic search roots, and the UNRESOLVED
  configured model is passed through so downstream errors point at the model
  the session actually asked for.
- **UI scaling stability**: scaling applied before geometry restore, geometry
  saved through `_reverse_geometry_scaling` (a 120 % window grew ~20 % per
  launch), Start-maximised takes precedence over the remembered geometry.
- **GUI Python console forgot its variables** — every line ran in a fresh
  scope; one persistent namespace now, with `_` bound like the real REPL.
- **C3D Export Browse opened in unrelated folders** — no `initialdir`, no
  `set_project_dir`, registered with empty args. All three fixed.
- **EMG-only normalisation trials no longer scaffold empty stage folders**
  (`external_biomechanics/`, `ceinms/`, ...) in every iteration —
  normalisation-only trials skip the scaffolding and constructor leftovers
  are pruned.

## [2.0.0] — 2026-08-11

First normal (non-pre-release) 2.x. Code-identical to `2.0.0b20` — only the
version string and the packaging metadata changed.

### Changed — beta is declared by classifier, not by the version string

`2.0.0bN` is a PEP 440 pre-release, which meant PyPI kept the 2.x line off the
project's landing page (it showed 1.1.0) and pip skipped it unless you passed
`--pre`. That hid the release rather than qualifying it. 2.0.0 is a normal
release; the beta status is now stated by `Development Status :: 4 - Beta`,
which shows in the PyPI sidebar and does not affect resolution.

**Anyone still on 1.x will now get 2.x from a plain `pip install bioscout`.**
2.x requires Python 3.9–3.11 and OpenSim — `python_requires` is `>=3.9`, so a
3.8 install fails at resolution instead of at import.

Also added the Python 3.9/3.10/3.11, Science/Research and Medical Science Apps.
classifiers, which were missing entirely.

## [2.0.0b20] — 2026-08-11

### Changed — the ghost test fixture is built on the ITERATIVE layout, by bioscout's own tools

`bioscout/tests/_results/simulations/` was still the old shape: trials directly
under the session, no iteration level, no `session.yaml`. It is now

    KneeGhost/ghost_session/
        session.yaml
        1_c3dfiles/  2_experimental/  logs/
        3_iterations/ghost/
            knee.osim  ExtFlex_01/  ExtFlex_02/  ceinms_calibration/

built by `build_ghost_session()` through `scaffold_session_yaml` and the
`session_layout` resolvers rather than by joining folder names. That makes this
the only coverage that session CREATION produces a session `Session.open` will
accept, and a layout change can no longer pass here while breaking real
projects. `ceinms_calibration/` moved INSIDE the iteration: the calibrated
subject belongs to one model variant, not to the session.

### Added — `TestGhostSessionLayout`, which does not skip

Four checks — numbered layout, the iteration under `3_iterations/`, the
`session.yaml` round-trip, and `Session.open` finding the iteration — with no
OpenSim required, running first in the suite. Every other knee test self-skips
without OpenSim, which is exactly why the layout assertions must not sit behind
that skip.

### Fixed — the fixture wipe failed silently and the next run built on top of it

`shutil.rmtree(SIM_ROOT, ignore_errors=True)` is the obvious call and the wrong
one: files copied from a read-only source carry the read-only bit, and on
Windows the unlink then fails. With errors ignored nothing was reported, so a
new-layout session was being written over the old flat-layout one — a fixture
half old, half new, and passing. `_wipe()` clears the bit, retries, and asserts
the path is gone.

### Changed — the bundled `settings.py` template caught up with the project

`muscle_opt_skip_coords` and `muscle_opt_ma_tol` (the Modenese grid is
`N**nDOF`; two unlocked secondary DOFs were 34 of a 39-minute run), and an
explicit `dof_set` literal with `knee_adduction` dropped per t23 — derived from
`dof_list` it changed silently whenever `dof_list` did. Project run state
(`ITERATIONS`, `TRIALS`, the `DO_*` switches) deliberately not ported.

### Added — `docs/SESSION_LAYOUT.md`

The layout, the resolver table, how to create a session end to end, which
`settings.py` is which, and how the fixture proves it.

### Changed — README restructured

The README opened with a "Session-centric YAML layout (2.x)" block and then
described a *different*, older layout under "Project layout" further down — two
trees, neither matching what bioscout writes today. Both are gone, replaced by
one **Project structure** section that documents the numbered layout
(`1_c3dfiles/`, `2_experimental/`, `3_iterations/<iteration>/`), explains why the
three levels are separate, states the `session.yaml`-outranks-`settings.py` rule,
and carries the `session_layout` resolver table with the warning not to cache a
resolver in a module constant.

The hero is now a **Why BioScout** introduction — the comparison-of-model-variants
problem the session/iteration split exists to solve — rather than a folder tree.

Also merged the two near-identically named `settings.py` sections ("Configuring a
project" and "Running a project") into one.

### Removed — repository cleanup

`documentation/` (122 tracked `.md` files from the GUI era —
`ALL_FIXES_SUMMARY_MAY_20_2026.md`, `APP_FIXES_FINAL.md`,
`BATCH_EXPORT_FIX_v2.md` and so on) archived to `_to_delete/`. Nothing
referenced it: not `MANIFEST.in`, not `setup.py`, not the README. It is all in
git history if it is ever wanted.

`guide/` folded into `docs/` — `git_commands.md` → `GIT_COMMANDS.md`,
`steps_to_upload_to_pip.md` → `RELEASING_TO_PIP.md`, `bops_issues.md` →
`BOPS_ISSUES.md`. `docs/` is now the one documentation folder.

The one-off CEINMS packaging script (`finish_ceinms_pkg.py`) and the `ceinms/`
manifest folder it wrote were archived too.

### Removed — backup-file litter

The 17 `*.pre_*` / `*.bak_*` files and the stale gitignored root `settings.py`
moved to `_to_delete/cleanup_2026-08-11/`. One of them,
`bioscout/utils/session.py.bak_ceinmsprep`, was actually TRACKED — `.gitignore`
never applied to it because it was already in the index.

## [2.0.0b19] — 2026-08-11

### Fixed — the Muscle Analysis stage logged one trial out of eight, and never a path

An 8-trial MA stage wrote a single progress line (`[MA] Squat_35kg_01 -
running`) and then nothing, while all eight trials ran to completion on disk.
Two causes:

- `settings.LOG_TYPE = "minimal"` is a WHITELIST and `_KEEP_MINIMAL` never
  matched `[MA]` / `[MA ok]` / the indented `inputs -` line. The first line
  survived only because `_Tee` keeps an indented line whose predecessor was
  kept, and it followed the stage banner; the next unindented OpenSim print
  broke that chain. `[SO]`, `[IK]`, `[ID]`, `[JRA]` and `[exbiomec]` were in
  the same position.
- `Analyse.run_ma` logged its success with `terminal=False`, so the line
  naming the output folder reached `log.txt` only, never the run log —
  `run_so` had already been fixed this way, `run_ma` had not.

Now: those tags are whitelisted (`_QUIET_DROP` still drops the `... ok]`
completions in `quiet`), `run_ma` logs its absolute output dir with
`terminal=True`, and the session line is `[MA ok] <trial> -> <dir>`.

Regression test: `tests/MAcost/t2_ma_log.py` in the Powerlifting project —
pushes the stage's exact line sequence through the real `_Tee` at all three
verbosities, no OpenSim needed.

## [2.0.0b17] — 2026-08-10

### Fixed — CEINMS JRA wrote a confidently wrong contact force when SO was absent

`run_jra_ceinms` calls `add_so_columns_to_ceinms_results` first, which appends
the SO force file's residual, reserve and GRF columns to the CEINMS forces so
the JointReaction has the full actuator set. When the SO force file is missing
that helper logged an error and returned — and the JRA ran anyway, on a forces
file with muscles only.

The result is not merely inaccurate. Without the residuals the JointReaction
cannot balance the dynamics, so it reports the imbalance instead of the contact
force: ~100x too large, **and no longer a function of the muscle forces at
all**. Every arm of a comparison therefore gets the SAME wrong number, in a
file that looks entirely ordinary. t25's variance smoke run produced hip
32.36 BW and knee 32.23 BW byte-identical across four arms whose muscle forces
differed by three orders of magnitude; t14's 353 BW hip was the same failure.

It now refuses: no JRA is run, any earlier output is removed (a stale file is
worse than a missing one, because everything downstream reads it happily), and
the error names the file to copy. `Analyse.jra_allow_unbalanced = True` opts
back in. `add_so_columns_to_ceinms_results` returns True/False instead of None.


### Fixed — an UNCALIBRATED arm could not build its own excitation generator

`save_pretty_xml` opened the file without creating its parent directory. For a
calibrated iteration that never mattered: `run_ceinms_calibration` makes
`ceinms_calibration/` before anything writes into it. An UNCALIBRATED
iteration skips calibration entirely and goes straight to
`create_excitation_generator`, so on a fresh arm the folder did not exist and
the write died with `FileNotFoundError`.

It failed loudly in the log and silently everywhere else: bioscout catches
CEINMS errors and logs them, so `Iteration.run` returned normally and the
caller reported **"ok 0.5 min"** for an arm that produced nothing at all. Every
uncalibrated arm on a session that had not already calibrated hit this — which
is every session where the uncalibrated model is used as the control it exists
to be. `save_pretty_xml` now creates the parent directory; every XML writer in
the package goes through it.


### Added — `calibrated:` is an ITERATION key too, not only a session one

b15 put `calibrated: false` in the session-wide `ceinms:` block, which makes an
uncalibrated arm a whole separate session — the same drift `emg_map` and
`calibration:` were moved into the file to end. It is now also an iteration
key, so the control lives beside the arms it is the control for:

```yaml
ceinms: {alpha: 1, beta: 1, gamma: 30}
iterations:
  cateli__b0.75-1.25: {calibration: b0.75-1.25}
  cateli__uncalibrated: {calibrated: false}    # the control, same session
```

The session-wide flag still sets the default for every iteration; the
iteration overrides it, either way round. Everything else b15 built is
unchanged — no calibration runs for that iteration whatever `calibrate=` says,
and its output still lands in `Execution_uncal_*`.

An uncalibrated iteration no longer has to name a `calibration:` config. With
several configs defined, an iteration naming none normally refuses to load —
correctly, because a silently-defaulted bound is invisible in the output. But
an iteration that calibrates NOTHING has no bound to choose, and forcing a
selector into it would put a value in the file that is never read. `load_session_yaml`
skips those, `trial_config` omits `calibration_params` for them, and a
CALIBRATED iteration still has to choose. New: `iteration_is_calibrated`.

Covered by `bioscout/tests/test_uncalibrated_per_iteration.py` (14).

### Fixed — `trial_config` crashed on the list form of `iterations:`

`read_session_yaml` has always accepted `iterations` as a LIST of blocks each
carrying a `name`. `Iteration.trial_config` read it with a raw
`.get(self.iteration)`, so on a list-form session it raised
`AttributeError: 'list' object has no attribute 'get'` before resolving any
model file. It goes through `_iteration_blocks` now, like every other reader.

## [2.0.0b16] — 2026-08-10

### Added — the `calibration:` block now carries the OPTIMISER, not just the bounds

`calibration:` has held the six parameter bounds since b14. It now also holds
how the calibration *searches*:

```yaml
calibration:
  lr0.020__r01: {learningRate: 0.02,  optimalFiberLength: "0.5 3"}
  lr0.005__r01: {learningRate: 0.005, optimalFiberLength: "0.5 3"}
iterations:
  cateli__lr0.005__r01: {calibration: lr0.005__r01}
```

Accepted, in either spelling: `learningRate`/`learning_rate`,
`maxIterations`/`max_iterations`, `patience`/`early_stopping_patience`,
`minImprovement`/`early_stopping_min_improvement`,
`numberOfSynergies`/`num_synergies`, plus `learningRateDecay`+`minLearningRate`
(emitted only when asked for — the reference cfg ships that block commented
out, so this build's support for it is unproven).

Precedence is unchanged and partial: the iteration beats `settings.py` beats
the built-in default, and a config naming only `learningRate` leaves every
other optimiser setting alone.

### Why

`learning_rate` was a `settings.py` global, so comparing 0.02 with 0.005 meant
monkeypatching `sys.modules["settings"].CEINMSSettings` between
`Session.open()` and `run()` — a mutation that left **no trace in the session
it produced**. The only record of which arm ran under which rate was the
sweeping script's memory of what it had just set. That is precisely the defect
`calibration:` was introduced to end for the bounds.

### Fixed — an optimiser key could become a bound, silently

Before this, an unrecognised key in `calibration:` was passed through to
`parametersToCalibrate`. `{learningRate: 0.005}` therefore emitted
`<parameter name="learningRate">0.005</parameter>`: CEINMS ignored it, the
learning rate stayed at 0.02, and nothing anywhere said so. Optimiser keys are
now filtered out of `calibration_param_ranges` by name and routed to
`<optimiser>`; a genuine typo still falls through to the bounds and still
raises the load-time warning, so a mistake stays visible instead of vanishing.

### API

`bioscout.utils.ceinms.configs.calibration_optimiser_settings(params, override)`
and `is_optimiser_key(key)`; `bioscout.utils.session.CALIBRATION_OPTIMISER_NAMES`.
`_OPTIMISER_ALIASES` in `configs.py` and `CALIBRATION_OPTIMISER_NAMES` in
`session.py` are the two halves of one list — keep them in step, exactly as
`_PARAM_ALIASES`/`CALIBRATION_PARAM_NAMES` already have to be.

Tests: `bioscout/tests/test_calibration_optimiser.py`.
Consumer: `tests/GPKv3/t25_calibration_variance` (Powerlifting) — the
calibration-variance and learning-rate test this was written for.

## [2.0.0b15] — 2026-08-10

### Added — execute CEINMS against the UNCALIBRATED subject model

CEINMS execution has only ever been driven by `subjectCalibrated.xml`. There
was no way to ask for the other one — `subjectUncalibrated.xml`, the subject
XML `create_ceinms_model()` writes straight from the .osim, carrying OpenSim's
own optimal fibre lengths, tendon slack lengths, pennation angles and max
isometric forces with nothing fitted to the subject.

That file is the control a calibrated result has to beat. Without it,
"calibration changed the forces" has no baseline: every arm of every test so
far has been one calibration compared with another calibration.

```yaml
ceinms:
  gamma: 30
  calibrated: false          # execute against subjectUncalibrated.xml
```

Declared in session.yaml, like `emg_map` and `calibration`, so the session that
produced a result RECORDS which subject model made it. What it does:

- `Iteration.run(do_ceinms=True)` runs **no calibration at all** for that
  iteration, whatever `calibrate=` says — calibrating and then executing
  against the uncalibrated subject would burn ten minutes on a file nothing
  reads, in a run that looks calibrated in every log.
- `Session.prepare_uncalibrated_ceinms()` builds the three things execution
  still needs — normalised EMG, the excitation generator, and the uncalibrated
  subject XML — and stops. An uncalibrated arm therefore costs execution time
  only.
- Execution output goes to `Execution_uncal_a1_b1_g30`. A calibrated and an
  uncalibrated solve of the same trial at the same weights would otherwise
  write to the same folder and one would silently overwrite the other. The tag
  still matches the `Execution_*` glob `ceinms.modes` finds solves by.
- `run_ceinms_exe_single` rebuilds the cached cfg + setup when the setup on
  disk names a **different** subject file, so a trial solved once as calibrated
  cannot keep solving calibrated after the iteration switched.

New on `Analyse`: `ceinms_is_calibrated`, `ceinms_execution_subject`,
`ceinms_exe_tag`, `ceinms_exe_out_rel()`. The last one replaces two
independent format strings that built the execution folder name — write it
one way, read it the other, and a solve lands where nothing looks for it.
New in `session`: `yaml_bool`, because a quoted `"false"` is a string and
`bool("false")` is True.

Nothing changes for a session that does not mention the flag: no key reaches
the trial config and the folder names are unchanged.
Covered by `bioscout/tests/test_uncalibrated_execution.py` (31).

## [2.0.0b14] — 2026-08-10

### Added — several NAMED `calibration` configs, picked per iteration

Same shape as the named `emg_map`s below, for CEINMS's calibration parameter
bounds. They were one global value in `settings.py`, so a bound sweep meant one
copied session per bound plus a runtime monkeypatch of
`sys.modules["settings"].CEINMSSettings` between `Session.open()` and `run()` —
a mutation with no record in the session it produced.

```yaml
calibration:
  wide:  {optimalFiberLength: "0.5 3",        tendonSlackLength: "0.5 3"}
  tight: {optimal_fiber_length: [0.75, 1.25], tendon_slack_length: "0.75 1.25"}
default_calibration: wide
iterations:
  cateli__tight: {generic: Catelli.osim, calibration: tight, ...}
```

One flat block or several named ones, told apart by value type; ambiguity
refuses to load; the resolved bounds reach `Analyse` as `calibration_params`
and `create_calibrationCfg` applies them over `settings.py`. The override is
PARTIAL — a config naming one bound leaves the rest alone.

Because both features now share `_is_named` and `_select_name`, the two cannot
drift into behaving differently. New helpers: `calibration_configs`,
`resolve_calibration`, `calibration_name_for`, `is_named_calibration`;
`SessionSpec.calibrations` / `default_calibration`, `Model.calibration`.
Covered by `bioscout/tests/test_calibration_configs.py`.

### Fixed — four of six calibration ranges in `settings.py` were unreachable

`create_calibrationCfg` read `optimalFiberLength`, `tendonSlackLength`,
`shapefactor` and `strengthCoefficient`; every project `settings.py` declares
`optimal_fiber_length`, `tendon_slack_length`, `shape_factor` and
`strength_coefficient`. The `getattr` always missed and the hard-coded literal
was used, so **editing those four in `settings.py` did nothing, silently** —
only `c1` and `c2` were ever live. No number was wrong, because the literals
happened to equal the declared values, which is exactly why it went unnoticed.
Both spellings are now accepted and canonicalised, in `settings.py` and in the
new `calibration:` block alike.

## [2.0.0b13] — 2026-08-10

### Added — several NAMED `emg_map`s in one session, picked per iteration

How EMG channels are grouped onto model muscles is a modelling choice, but it
was the one modelling choice that could not live in an iteration. Testing three
electrode groupings of the same recording meant three whole COPIED sessions
(`arms/A_narrow`, `arms/B_triceps`, `arms/C_wide`), each with the same subject,
the same trials, the same windows and the same experimental inputs, differing
in one dict. Three places to fix a time range, three chances to fix two of them.

`emg_map` may now hold named sub-maps, with each iteration naming the one it
runs with:

```yaml
emg_map:
  narrow:  {EMG_Channels_EMG09_gast_med_l: [gasmed_l, gaslat_l]}
  triceps: {EMG_Channels_EMG09_gast_med_l: [gasmed_l, gaslat_l, soleus_l]}
default_emg_map: narrow        # optional: what a silent iteration gets
iterations:
  cateli_narrow:  {generic: Catelli.osim, emg_map: narrow}
  cateli_triceps: {generic: Catelli.osim, emg_map: triceps}
```

Nothing existing changes. The two forms are told apart by VALUE TYPE — a
channel maps to a list of muscles, a named map to a mapping of channels — so
every flat `emg_map` on disk parses exactly as before, and a flat file still
writes back out flat. Resolution runs in `Iteration.trial_config`, so by the
time `Analyse` sees `self.emg_map` it is one flat map, and everything
downstream (`emg_channel_map`, the excitation generator, CEINMS calibration)
is untouched. The iteration's resolved name also lands on the trial as
`emg_map_name`.

Ambiguity is an ERROR, not a default. With more than one map and no way to
choose — no iteration selector, no `default_emg_map`, no map called `default` —
`load_session_yaml` refuses the file. So does a selector naming a map that
does not exist, a selector on a flat `emg_map`, an inline channel map inside an
iteration, a block mixing named maps with bare channels, and two names
differing only by case. All of them fail at load, because the alternative is a
run that finishes normally hours later having used the wrong electrode set,
with nothing in the output to say so.

New public helpers in `bioscout.utils.session`: `emg_maps`, `resolve_emg_map`,
`emg_map_name_for`, `is_named_emg_map`. `SessionSpec` gains
`emg_muscle_mappings` / `default_emg_map` / `emg_map_for(model)` and `Model`
gains `emg_map`; `SessionSpec.emg_muscle_mapping` still holds the session
default, so existing readers are unaffected. `session.xml` carries the
per-model selector but cannot hold the maps themselves — writing a multi-map
session to XML now warns instead of quietly keeping one. Adding an iteration
from the GUI pins a map when the session has several and no default, so the
new block cannot make the file unloadable. Covered by
`bioscout/tests/test_emg_maps.py`.

### Fixed — two consumers never honoured `session.yaml`'s `emg_map` at all

`plot_summary`'s EMG-vs-activation panel read `settings.EMG_muscle_mapping`,
which no `settings.py` has ever defined — not the project's, not the bundled
template. The panel raised on every call and the exception was swallowed
upstream, so the row simply drew nothing and had done since it was written. It
now calls `analysis.emg_channel_map()` like the rest of the pipeline. Getting
past that first line exposed two more: the RMSE/R² box scored against
`emg_col`, a leaked loop variable — undefined for any DOF with no mapped
channel (`pelvis_tilt`, `lumbar_extension`), and otherwise whichever channel
the loop happened to end on. It now scores against the mean of every mapped
channel, and skips muscles the activation file does not contain.

`summary.py` read only `settings.BatchSettings.emg_muscle_mapping`, so a
per-session (let alone per-iteration) map never reached the trial summaries. It
now walks up to the trial's own `session.yaml` and resolves the map for the
iteration the trial sits in, falling back to `settings.py` when there is none.
The walk skips the `3_iterations/` wrapper level, without which every trial on
the numbered layout would infer no iteration and silently take the default map.

## [2.0.0b11] — 2026-08-10

### Fixed — the wheel could not be published at all (284 MB vs PyPI's 100 MB)

`ceinms.py` ships `torch_cpu.zip` (76 MB) and extracts `torch_cpu.dll`
(252 MB) from it on first run. But `package_data` listed `*.dll`, which swept up
the EXTRACTED dll from whichever machine built the wheel, while `*.zip` was in
neither `package_data` nor `MANIFEST.in` — so the wheel carried the huge file
the zip existed to avoid AND omitted the zip, leaving the extraction with no
input. Both wrong, and they cancelled into "cannot release".

`MANIFEST.in` now includes `*.zip` and excludes `torch_cpu.dll`; `setup.py`
gains `exclude_package_data`, because a package_data glob cannot say "every dll
except this one". Measured: **87.3 MB**, 12.7 MB inside the limit, zip present
and dll absent.

### Fixed — adding an iteration corrupted session.yaml

Duplicating an iteration copied the source block PLUS the following line, so
`+ Add iteration` on `cateli` also wrote a second `lernagopal:` key.
`load_session_yaml` rejects duplicate keys, so the next `Session.open` raised
and every run of that session failed. For a block mapping YAML's `end_mark`
sits at the start of the NEXT key — the parser only knows the block ended once
it sees a shallower token. Entry bounds are found by indentation now.
`delete_entry` had the same bug and was worse: it deleted the following
iteration's key line, merging its settings into the wrong entry.

### Fixed — the GRF window's lines never moved on matplotlib >= 3.10

`axvspan` returns a `Rectangle` there and a `Polygon` before it;
`Rectangle.set_xy` takes a corner, so a polygon path raised — and the redraw is
defensive, so it was swallowed: the numbers moved and the plot did not.

### Added — sliders for the trial window, and a dependency error worth reading

Start/end sliders under the GRF plot drag their dashed line and the shaded band
live, cannot cross, and sit beside an "Update session.yaml" button. Separately,
a missing dependency now names the package AND the command that installs it
(`bioscout --env-create`, or `uv pip install -r "<path>"` — quoted, because
git-bash eats backslashes in a bare Windows path) instead of a bare
ModuleNotFoundError.

### Changed — bundled settings.py template refreshed from the study project

### Changed — one `validation/` folder per iteration, one rule for its name

Every report *about* a model now goes to `<model_dir>/validation/<model_stem>/`
instead of a `muscle_inspect_<stem>/` folder sitting directly in the iteration
folder. An iteration folder is models plus `validation/`, and everything written
about a given model sits together under that model's name:

    cateli/
        scaled.osim
        scaled_opt_N10.osim                 <- CEINMS model
        scaled_opt_N10_mvicx3.00.osim       <- SO model
        scale_factors.xml
        validation/
            scaled_opt_N10/
            scaled_opt_N10_mvicx3.00/
                moment_arm_change/

The point is not tidiness. The folder name was computed independently in five
places — `muscle_inspect.run_moment_arm_inspection`, `.run_muscle_checker`,
`.__main__`, `tps_personalise.bioscout_adapter` (which only *reported* the path,
so it could disagree with the tool that wrote it) and
`change_moment_arms.inspection` (`moment_arm_change_<stem>/`). All five now call
`muscle_inspect.paths.validation_dir(model, kind=..., out=...)`. `--out` still
wins wherever it was accepted.

`paths.is_report_dir()` replaces the three ad-hoc `"muscle_inspect" not in str(p)`
string tests in `change_moment_arms.cli`, so a model picker cannot offer a figure
folder as a model. It also matches the legacy names, so old sessions stay safe.

**Not migrated.** Nothing reads these folders, so there is no fallback and no
auto-move: old `muscle_inspect_*/` folders keep sitting where they are until you
move or delete them, and the next run writes to the new place. Note that reports
generated before a model was rebuilt describe a model that no longer exists —
worth checking the dates before trusting one.

### Added

* `bioscout/tests/test_validation_paths.py` (13 tests, pure stdlib, wired into
  `tests.suite()`) — pins the layout, the `kind=` sub-folder, `--out` precedence,
  and that an iteration's SO and CEINMS models cannot collide.

## [2.0.0b10] — 2026-08-07

### Added — Trial Analysis rebuilt around a stage's real inputs

The stage x iteration grid of file counts is gone. A count of files in a folder
says a stage produced *something*, not whether it produced the right thing, and
it cost the whole left panel. That panel now answers the question you actually
have when one trial looks wrong:

* **Inputs** — the selected stage's inputs resolved to real paths, editable,
  each marked present or missing (the model path is read from the iteration's
  `session.yaml` block, so it follows `so_model` / `ceinms_model`). Run warns
  which file is absent instead of letting OpenSim fail two minutes later.
* **GRF window** — plots the trial's vertical ground reaction per plate; drag
  across it to set the time window. The window currently in the fields is drawn
  as dashed lines, so the plot and the numbers cannot disagree.
* Stages are chosen one at a time rather than as checkboxes.
* **Iterations can be added and removed from the GUI** (`+` / `-` beside the
  Iteration menu). Adding one used to mean hand-editing session.yaml, which is
  why every session had the same six. Removing deletes the folder only when it
  is empty — a folder with results in it is never deleted by a config edit.

### Added — EMG Processing (was EMG Normalization)

The tab owns the whole chain now, each step independently switchable:
band-pass -> notch -> rectify -> envelope low-pass -> amplitude normalise, with
a frequency-spectrum view for arguing about cut-offs. Normalisation stays
SESSION-level on purpose: an MVC computed from one trial is not an MVC. One
trial list picks what the reference spans, another picks what is drawn.

Input and output are names inside each trial folder rather than absolute paths,
because the tab runs over many trials at once; the output follows the input as
`<stem>_processed<ext>` until edited by hand, so the raw recording is never
overwritten. `write_table()` dispatches on the OUTPUT extension — asking for
`.csv` used to produce a file with an OpenSim .sto header inside it.

### Changed

* Sidebar order: C3D Export now precedes Trial Analysis.
* Results viewer: adding a series ticks ONE channel (the first non-time column)
  instead of all of them. A 126-channel static-optimisation file opened as a
  126-subplot figure ~1300x8600 px, which reads as a hang. Grid mode caps at 64
  subplots and says so; a new "Single plot (overlay channels)" toggle draws them
  all on one axes. "All" now skips time columns.

### Changed — the bundled settings.py template caught up with the study project

`bioscout/settings.py` was ~112 lines behind the powerlifting project's copy:
it was missing the CONTROL PANEL restructure (`CAPTURES` / `CAPTURE` and the
module-level `RUN_*` / `DO_*` / `TPS_*` / `PRUNE_*` flags) and both runner
functions, and still had that block buried inside `if __name__ == "__main__"`.
Ported across; the two are now in sync (verified by AST diff — no top-level
name and no class attribute differs).

Two adaptations were required, and both matter:

* `matplotlib.use("Agg")` moved out of module scope into the `__main__` runner.
  The template is exec'd while bioscout imports, so setting Agg there would
  have killed the GUI's TkAgg canvases.
* The `bioscout.utils.analysis` imports are guarded with stub fallbacks. The
  template is loaded DURING bioscout's own import, so a bare import is
  circular; a real project's copy takes the real imports.

The schema `__version__` stays `2.0.0b1` — the shape did not change, it caught
up — so projects pinned to it still validate.

## [2.0.0b9] — 2026-08-06

### Added — File Editor tab: edit session.yaml / OpenSim XML / JSON in the GUI

Changing a trial's `time_range`, an `ExternalForce` body or a CEINMS weight
meant leaving BioScout for a text editor, where a bad indent or a stringified
number surfaces three pipeline stages later as an unrelated OpenSim error.

* **New** `bioscout/utils/file_edit.py` — a headless, format-agnostic document
  model (`load_document` → tree of `Node`, form of `Field`). Handles YAML, XML
  (incl. `.osim`) and JSON behind one API. Atomic saves, `.bak` kept.
* **New** `bioscout/gui/widgets/file_editor.py` — `FileEditorTab` (sidebar) and
  the reusable `FileEditorFrame` / `open_file_editor_window()`, so any tab can
  offer "edit this file" without duplicating the editor. Structure tree,
  typed form (switches for booleans, dropdowns for keys that behave like
  enumerations), raw-text view with a syntax check, and a **Changes** view
  showing the diff a save would produce plus semantic checks (`time_range`
  ordering, `side` values, `static_trial` present in `trials:`, model files
  actually on disk).
* Files with no structured editor, and anything over 3 MB, fall back to
  plain-text editing rather than freezing on a 10k-row tree.

### Fixed — saving a trial from Trial Analysis deleted every comment in session.yaml

`_save_trial_settings` did `yaml.safe_dump` of the WHOLE file. That rewrote
session.yaml from the parsed object on every save, which:

* deleted all comments — including the block recording that **Walking_02 must
  not be re-enabled** and why, the only place that decision was written down;
* reordered keys, expanded every one-line `{type: ..., side: ...}` trial into
  four lines, and rewrote `0.00` as `0.0`.

YAML is no longer re-dumped anywhere. `file_edit` composes the document to get
the exact character span of every scalar and patches only the spans that
changed, so an edit to one trial is a one-line diff and everything else stays
byte-identical. Verified against the real `Athlete_03/25_03_31/session.yaml`:
loading and browsing every node changes nothing, and editing one trial touches
two lines out of 153.

Trial Analysis also gained an **Edit whole file…** button for the keys that
panel does not model (`iterations`, `emg_map`, `ceinms`).

### Note

No new dependency: the comment-preserving writer is built on PyYAML's composer,
which is already required.

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
