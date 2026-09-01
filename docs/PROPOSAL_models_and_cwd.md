# Proposal — a models layout that works for any project, and a CWD that stays put

Draft 2026-08-24. Three linked changes, each independently shippable.

---

## 1. Where personalised models live

### The rule

> A personalised model is identified by **(subject, generic)**.
> Session, iteration and trial are *not* part of its identity.

`models/personalised/<subject>/` (2026-08-19) got half of this: it dropped
session, which was right. It kept a **flat folder with fixed filenames**, which
assumes one model per subject — true for FAIS today, false for Powerlifting,
and false for FAIS the moment two sessions want different models.

Powerlifting has six models for one subject because six *generics* are scaled to
him. Six files all named `scaled.osim` cannot share a flat folder.

### The layout

```
models/
  generic/                              # the unscaled published models
    Catelli-V4.0_PowerliftingMarkers.osim
    GPK_v3.osim
  personalised/
    <subject>/
      <generic-stem>/                   # ONE folder per (subject, generic)
        scaled.osim                     # always this name
        scaled_opt_N10.osim             # muscle_opt products, optional
        scaled_opt_N10_mvicx3.00.osim
        scale_factors.xml  scale_setup.xml
        validation/                     # muscle_inspect reports for THIS model
```

Worked examples:

```
models/personalised/Athlete_03/GPK_v3/scaled.osim
models/personalised/Athlete_03/Catelli-V4.0_PowerliftingMarkers/scaled.osim
models/personalised/Athlete_03/GPK_v3_tps_Athlete_03/scaled.osim    # the MRI arm
models/personalised/022/Rajagopal2015_FAI/scaled.osim               # FAIS, one folder
```

### Where do models a TEST built live?

Not in `models/`. `models/generic/` means **published, citable, frozen** — a
model a reader could go and download. A model a test just built is a
*candidate*, and the two must not share a namespace.

```
tests/<campaign>/_models/          # the test builds here. Nothing resolves it.
    GPK_v4_generic.osim
    provenance.yaml                # generated: base, recipe, ops, date, gate
models/generic/                    # published only. Promotion is deliberate.
```

**Why not a `models/generic/_candidate/` staging folder:** it puts the
candidate one `ls` away from the published set and one typo away from being
resolved. The GPKv4 campaign is the worked example — its generic was copied
into `generic models/GPK/` to make the pipeline see it, sat beside `GPK_v3`
for a day, and was disqualified the same morning by t03c. The campaign's own
SUMMARY had predicted exactly that: *"a provisional test model sitting beside
the production ones is how the wrong .osim ends up in a manuscript."*

**Two rules that follow.**

1. **Solving a candidate does not require promoting it.** The reason GPKv4 got
   copied was that `settings.py` only resolves models under the project roots.
   Give a campaign its own session instead —
   `tests/<campaign>/_session/` with its own `session.yaml` pointing at
   `tests/<campaign>/_models/` — so a test never adds an iteration to the
   production session. (The 2026-08-24 `--skip` incident is the other half of
   this: a test-shaped command re-solved two production iterations.)

2. **Promotion is an explicit command with a gate, not a `cp`.**
   **BUILT 2026-08-24** — `model_edit promote` (backup `cli.py.bak_promote`).

   ```bash
   python -m bioscout.model_edit promote tests/GPKv4/_models/GPK_v4_generic.osim \
          --as GPK_v4 --gate tests/GPKv4/SUMMARY.md
   ```

   It refuses unless the campaign summary contains a literal `PROMOTE: PASS`
   line, copies into `models/generic/`, and writes a provenance sidecar: source
   path, sha256, size, date, the gate file, the evidence line, and the
   candidate's own build record if `_models/provenance.yaml` exists.
   `--overwrite` keeps the previous version as `.superseded_<date>.osim`;
   `--force` needs `--reason`, which is recorded.

   **The gate is a literal marker, never inferred from prose.** A campaign
   summary argues with itself — it holds the failed arms and the reasons a
   thing was nearly built. Reading intent out of that is precisely how a
   disqualified model gets promoted. Verified against the real case: pointed at
   `tests/GPKv4/SUMMARY.md`, it refuses. `models/generic/`
   then answers "where did this .osim come from" for every file in it — which
   `GPK_v2` / `GPK_v2c` / `GPK_v3` / `GPK_v4` currently do not.

### Why a folder per generic, not `<Generic>_scaled*.osim` flat

A flat folder was the obvious first answer and it does not scale:

- **Count.** Flat, a subject accumulates `n_generics x n_variants` files —
  Powerlifting is already 6 x 3 = 18, and every `mvicx` factor or `opt_N`
  setting adds another. Foldered, it is `n_generics` folders (6) with 3-5 files
  each. **The folder count grows with generics only; it never grows with
  sessions, trials, or variants.**
- **Derived artefacts have a home.** `scale_factors.xml`, the muscle_opt log,
  the `validation/` reports and the future `.pre_reserves.osim` all belong to
  one model. Flat, they collide or need the prefix repeated on every one.
- **Deleting one model is `rm -r` on one folder**, not a glob that might catch
  a neighbour with a similar prefix.
- **Filenames stay stable**, so `ceinms_model: scaled_opt_N10.osim` in
  session.yaml keeps working unchanged — only the folder it resolves against
  moves. This is what makes the migration cheap.

### What changes in code

| where | change |
|---|---|
| `utils/session.py` `Session.models_dir()` | takes `generic` → returns `<project>/models/personalised/<subject>/<generic-stem>/` |
| `utils/analysis.py` ~2015 | drop the `os.listdir` + filename-glob resolver; resolve `(subject, generic)` then join the requested filename |
| `utils/analysis.py` `_update_model` ~1717 | **delete the hard-coded subject dispatch** (`if self.subject == 'Athlete_03': update_model('scaled_12_05_2026.osim')`). This is the source of the `Scaled model not found: ..\..\models\Athlete_03\25_03_31\scaled_12_05_2026.osim` spam — a filename nothing has written in months |
| `utils/model_scaler.py` | write into the new folder |
| legacy fallback | keep reading `3_iterations/<iter>/` and `models/<subject>/<session>/` for one release, log once when hit |

### Migration (Powerlifting, reversible)

Copy — never move — then flip the resolver, then verify the six iterations
still find their models, then retire the originals to `_to_delete/`.
`session.yaml` needs no edit: the filenames it names do not change.

---

## 2. `muscle_opt` becomes opt-in and silent by default

`tests/ModeneseN` found the Modenese optimisation is **not better than plain
scaling** for the quantities this project reports, and it costs **26 h** on GPK.
It should not be on a default path.

- `BatchSettings.muscle_opt = False` by default.
- `--muscle-opt` / `muscle_opt: true` per iteration to switch it on.
- When off: no `scaled_opt_N10*` files, no log, no warning. Silence, not a skip
  message on every trial.
- When on: products land beside `scaled.osim` in the same (subject, generic)
  folder, so they are obviously derived from it.
- `ceinms_model:`/`so_model:` naming a `scaled_opt_*` file while `muscle_opt`
  is off must **fail at load**, not silently fall back — that is how a result
  gets attributed to the wrong model.

---

## 3. Make the working directory stop moving

### The bug

`utils/analysis.py` has ~20 `os.chdir(self.path)` calls that never restore.
One of them carries the comment `# reset cwd (Analyse() chdir's into trial
folders)` — the workaround is already in the codebase, admitting the problem.

Consequences seen in this project:

- `ikTool.setResultsDir('./')` meant *the process CWD*, so OpenSim wrote
  `_ik_marker_errors.sto` into the repo root, overwritten by every trial.
  (Fixed 2026-08-24 in `openSim.py`; backup `openSim.py.bak_resultsdir`.)
- `calculate_mean_marker_error` reads the hard-coded relative
  `'.\\_ik_marker_errors.sto'` — so it reports whichever trial ran last.
- Any exception between a `chdir` and the next one leaves the process in a
  random directory for the rest of the run.

### The fix

**a. One context manager, always restoring.**

```python
from contextlib import contextmanager

@contextmanager
def in_dir(path):
    """chdir that always comes back, exception or not."""
    prev = os.getcwd()
    os.chdir(path)
    try:
        yield path
    finally:
        os.chdir(prev)
```

Replace every bare `os.chdir(self.path)` with `with in_dir(self.path):`.
Mechanical, ~20 sites, one file.

**b. Never hand a relative path to an OpenSim tool.** `setResultsDir`,
`setOutputMotionFileName`, `set_model_file` and the setup XMLs all resolve
against CWD. Absolutise at the boundary.

**c. A test that fails if CWD moves.**

```python
def test_cwd_is_restored(...):
    before = os.getcwd()
    run_one_trial_stage(...)
    assert os.getcwd() == before
```

**d. Longer term:** stop chdir-ing at all. Every consumer takes an explicit
directory. The chdir exists so relative filenames in old setup XMLs resolve;
absolutising those removes the need.

---

## Order to ship

1. **(3)** the CWD fix — smallest, unblocks trusting any path.
2. **(2)** muscle_opt default off — one flag, saves 26 h a rebuild.
3. **(1)** the models layout — needs the migration and a README rewrite.
