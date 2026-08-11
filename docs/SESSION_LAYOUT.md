# Session layout, settings.py and the test fixture

Written 2026-08-11, bioscout 2.0.0b19.

Three things this file covers: the folder layout a session must have, how to
create one, and how the test fixture now proves both.

---

## 1. The iterative layout

```
simulations/<Subject>/<Session>/
    session.yaml            <- source of truth (see §3)
    1_c3dfiles/             <- raw captures, flat <Trial>.c3d
    2_experimental/         <- model-independent exports, written ONCE
    3_iterations/
        <iteration>/        <- one model variant
            <model>.osim
            <Trial>/            joint_angles.mot, emg.mot,
            <Trial>/            MuscleAnalysis/, inverse_dynamics.sto
            ceinms_calibration/ subject XMLs, excitation generator,
                                calibration cfg/setup, calibrationOutput/
    logs/
```

Two rules that are easy to get wrong:

**`ceinms_calibration/` is per-ITERATION, not per-session.** The calibrated
subject is a property of one model variant — `cateli`, `gpk` and `lernagopal`
each have their own. A session-level folder claims one calibration covers all
of them, which is false.

**Never join these names by hand.** Call the resolvers in
`bioscout.utils.session_layout`:

| call | gives |
|---|---|
| `c3d_root(session, create=False)` | `1_c3dfiles/` |
| `experimental_root(session, create=False)` | `2_experimental/` |
| `iterations_root(session, create=False)` | `3_iterations/` |
| `iteration_path(session, name)` | `3_iterations/<name>/` |
| `is_numbered_layout(session)` | True once the session is numbered |

They answer from **what is on disk**, so the older flat layout
(`c3dfiles/`, `experimental/`, iterations at the session root) still resolves.
Only new output takes the numbered names. That is why `iteration_path` must be
called *after* the folders exist, not at import time — anything caching it in a
module constant will get the wrong answer on a half-migrated session.

---

## 2. Creating a session

```bash
conda activate msk311

# 1. drop the captures in place
#    simulations/<Subject>/<Session>/1_c3dfiles/*.c3d

# 2. scaffold session.yaml from those filenames
bioscout --new-session "simulations/<Subject>/<Session>" --body-mass 82.5

# 3. export the model-independent data into 2_experimental/
bioscout --c3d-export "simulations/<Subject>/<Session>"

# 4. classify each trial from its markers + GRF, then write the types in
bioscout --classifier "simulations/<Subject>/<Session>" --write-session-yaml
```

What `--new-session` does, and what it deliberately does not:

* trial names come from the **c3d filenames** — the trial list is never guessed;
* `static_trial` is the trial starting with `static`, or pass `--static-trial`;
* lab constants (markerset, setup folder, EMG map) are read from the nearest
  `settings.py` above the session — they are properties of the laboratory, not
  of the participant;
* `body_mass` is **not** inherited from any template. Set it. Anything
  normalised to body weight is wrong until you do;
* trial `type` is left unset on purpose. Guessing it from the filename puts a
  guess where the pipeline expects a fact — step 4 gets it from the data;
* it refuses to overwrite an existing `session.yaml`, except a zero-byte one
  (a crash leftover, which would otherwise strand the folder forever).

It does **not** create the empty folder skeleton — step 1 is manual.

---

## 3. session.yaml is the source of truth

It defines iterations, labels, colours, groups, trial windows, EMG map, body
mass and the CEINMS α/β/γ, and it **outranks `settings.py`** at run time. When
the two disagree, `settings.py` is the one silently doing nothing.

Parsed strictly since 2.0.2: duplicate keys and case-only-different iteration
names are errors, not last-wins. `Session.open` requires exactly `session.yaml`
(not `.yml`), and `Session.iterations` only sees an iteration whose folder
exists on disk.

---

## 4. settings.py — which copy is which

| file | role |
|---|---|
| `bioscout/bioscout/settings.py` | the **bundled template**. `init_project()` copies it; `Project()` falls back to it. |
| `<project>/settings.py` | the project's own copy — config above `if __name__ == "__main__"`, the runner below. |

The template is exec'd by bioscout *during its own import*, so its
`bioscout.utils.*` imports sit behind a `try/except` with stubs — a bare import
there is circular. A project copy is loaded after bioscout is ready and takes
the real imports. Do not "fix" the guard.

`__version__` in settings.py is the **schema** version — an independent series
from the bioscout package version. Bump it only when the *shape* of settings.py
changes.

Caught up from the powerlifting project on 2026-08-11:

* `muscle_opt_skip_coords = ["knee_adduction", "subtalar_angle"]` — the Modenese
  optimiser's grid is `N**nDOF`, so every unlocked secondary DOF multiplies the
  cost by N. On Athlete_06 these two accounted for 34 of the run's 39 minutes.
* `muscle_opt_ma_tol = 0.001` — a coordinate counts as spanned only above a 1 mm
  moment arm. The old 0.1 mm default let noise add a grid axis.
* `dof_set` — now an explicit literal with `knee_adduction` dropped (t23), not
  derived from `dof_list`. A derived list changes silently when `dof_list` does.

Project **run state** is deliberately not in the template: the template keeps
`ITERATIONS`/`TRIALS` reading from `CAPTURE`, and the `DO_*` switches at their
full-rebuild defaults.

---

## 5. The test fixture

`bioscout/tests/test_knee_pipeline.py` builds one ghost session under
`bioscout/tests/_results/simulations/` (gitignored), now in the iterative
layout:

```
KneeGhost/ghost_session/
    session.yaml
    1_c3dfiles/            ExtFlex_01.c3d  ExtFlex_02.c3d  Static_01.c3d
    2_experimental/
    3_iterations/ghost/    knee.osim  ExtFlex_01/  ExtFlex_02/
                           ceinms_calibration/
    logs/
```

`build_ghost_session()` builds it **through bioscout's own tools** —
`scaffold_session_yaml` plus the `session_layout` resolvers — rather than
joining names by hand. That makes this the only coverage that session
*creation* produces a session the rest of the pipeline can *open*, and it means
a layout change cannot pass here while breaking real projects.

Two things it has to correct after scaffolding:

* the **EMG map**. The scaffold walks up for the nearest `settings.py`, and from
  inside the installed package that finds bioscout's own bundled template — a
  real powerlifting map naming muscles this 4-muscle knee does not have.
* the **markerset / setup_folder** absolute paths that came in with it. They are
  right for the machine that ran the scaffold and wrong for every other one.

`Static_01.c3d` is a placeholder: a real session always has one and the scaffold
warns when it is missing. The ghost pipeline never scales, so it is never opened.
The `.c3d` files are all empty — the scaffold reads filenames, not bytes.

### `_wipe()` — why not `rmtree(ignore_errors=True)`

Found on 2026-08-11: the old `shutil.rmtree(SIM_ROOT, ignore_errors=True)` was
**silently failing**, and the new-layout session was being built on top of the
old flat-layout one. Files copied from a read-only source carry the read-only
bit, and on Windows that makes the unlink fail. With errors ignored, nothing is
reported and the fixture ends up half old layout, half new — and passing.

`_wipe()` clears the read-only bit, retries, then **asserts the path is gone**.

### Running

```bash
python -m bioscout.tests
# or
python -c "import bioscout; bioscout.test()"
```

Log lands in `bioscout/tests/_results/test_run.log`; OpenSim's C++ messages go
to `_results/opensim_tests.log` separately (they bypass Python stdout).

`TestGhostSessionLayout` runs **first and is never skipped** — it needs no
OpenSim, and it checks the numbered layout, the iteration sitting under
`3_iterations/`, the session.yaml round-trip and that `Session.open` finds the
iteration. Everything after it self-skips without OpenSim (and, for calibration,
without the CEINMS binary), which is exactly why the layout checks must not be
behind that skip.
