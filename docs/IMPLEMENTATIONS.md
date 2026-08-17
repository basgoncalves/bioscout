# IMPLEMENTATIONS.md — what bioscout needs to serve researchers beyond us

Written 2026-08-17, after running bioscout as the engine of two real studies —
the **Powerlifting** model-personalisation project (6 models × 2 athletes,
SO vs CEINMS) and the **FAIS machine-learning** project (29 subjects, a
pre/sprints/post fatigue protocol). Everything here was learned the hard way in
those projects; the point of this file is that the next lab should not have to.

Status tags: **[fixed]** shipped, **[patched-in-project]** works but lives in
project code and belongs in bioscout, **[open]** not addressed anywhere.

---

## 1. Bugs found in the field

### Correctness

- **[fixed 2026-08-12] "Uncalibrated" CEINMS execution was never wired.**
  `ceinms.calibrated=false` set a flag, built the subject, skipped
  calibration — and no writer ever read the flag: the setup always named
  `subjectCalibrated.xml`. Every "uncalibrated" result before the fix was
  silently calibrated. *Lesson: a switch is not implemented until an output
  differs when it is flipped — needs a regression test per config flag.*
- **[fixed b17] JRA without the SO forces file.** A raw CEINMS
  `MuscleForces.sto` carries no residuals/reserves; JRA then produces contact
  forces ~100× too large that are ALSO identical across arms. bioscout now
  refuses instead of producing plausible-looking garbage. *Pattern to
  generalise: every stage should declare its input contract and refuse, not
  degrade.*
- **[fixed 2026-08-05] `utils.ceinms` is `None` unless a `Project` was built
  first** — every script that imported the module directly failed in a way
  that looked like a model problem. Import-order side effects must go.
- **[fixed b20] `shutil.rmtree(ignore_errors=True)` on session rebuild** let a
  new-layout session be built ON TOP of an old one — mixed layouts, silent.
- **[fixed b19] `LOG_TYPE="minimal"` was a whitelist** that swallowed the
  `[MA]`/`[MA ok]`/`[SO ok]` progress lines entirely; one line survived only by
  an indentation accident.

### Silent-failure traps (the worst kind)

- **[open] EMG channel mapping is not validated.** The c3ds in FAIS export
  every electrode TWICE — a bare `Voltage_N` and a tagged `Voltage_N-VM`
  (the conditioned signal). The generated `emg_map` keyed the bare names, and
  bioscout normalised, calibrated and executed CEINMS on the wrong columns
  without a single warning. Needed: at export time, compare `emg_map` keys
  against the analog labels; warn on bare/tagged duplicates; fail when a
  mapped key does not exist. (Project-side fix: `FAIS code/fix_emg_maps.py`.)
- **[open] Missing stage outputs do not fail the run.** A run can end
  `[settings] done` with export having failed on every trial (seen 2026-08-17:
  the whole pipeline "succeeded" without `opensim` importable — the export
  errors scrolled past and later stages just found nothing to do). Needed: a
  per-trial, per-stage ok/MISS verification as part of the run, non-zero exit
  when a requested stage produced nothing. (Project-side fix:
  `simulate.py verify()`.)
- **[open] Generated session.yaml can contain duplicate mapping keys**
  (`Voltage_1:` twice) — YAML silently keeps the last one. The writer should
  refuse to emit a duplicate key.
- **[open] TRC export silently skips trials** it cannot process; the run
  summary does not name them.
- **[open] The mtime gate** ("output newer than input → skip") surprises
  users after any file copy/restore; there is no `--why-skipped` explanation.
- **[open] Windows MAX_PATH.** Session trees + CEINMS execution folder names
  exceed 260 chars at ~220-char project roots; failures appear as "file not
  found" deep inside OpenSim. Needs an up-front path-length check.

### Operational

- **[fixed 2.0.1] Logs scattered per session folder.** `Session.open` logged
  into `<session>/logs`, one folder per subject × state. Now: everything into
  `<project>/logs/bioscout_<date>_<time>.txt`, `BIOSCOUT_LOG_DIR` override.
- **[patched-in-project] The session name is a constant.** FAIS needed three
  sessions per subject (`pre`/`sprints`/`post`); the only way in was a
  `BIOSCOUT_SESSION` env var monkey-patched into the project's `settings.py`
  and `bioscout_setup.py`. Sessions must be a first-class argument.
- **[open] git operations over network mounts** leave `index.lock`; document
  or detect.

---

## 2. Implementations needed for general use

Ordered by what would most change adoption, not by effort.

### 2.1 A real entry point: `bioscout <verb>` instead of a copied settings.py

Today every project starts by copying and mutating a 1500-line `settings.py`
whose module-level constants ARE the configuration, then runs
`python settings.py`. That couples every project to bioscout internals (two
projects now carry three diverged copies each). Replace with:

    bioscout run   --project . --subjects 022 --sessions pre post --trials ...
    bioscout status --project .        # the per-stage ok/MISS coverage table
    bioscout plot  ...

driven by a declarative `bioscout.yaml` at the project root (paths, stages
on/off, CEINMS config, muscle groups, JRA columns). `settings.py` survives only
as an optional hook for code-level overrides. The FAIS `simulate.py`
(stage → preflight → solve → verify → results) is the shape the built-in
runner should have.

### 2.2 Preflight as a first-class stage

Fail in seconds, not hours in. Before solving: every scoped trial has a c3d;
`so_model`/`ceinms_model` resolve; `time_range` present (warn: whole capture);
calibration trials inside the scope; `BatchSettings` attributes complete; EMG
map keys exist in the analog labels; path lengths under the OS limit;
`import opensim` works. All of this exists today as project-side scripts —
it belongs in the library, run automatically by `bioscout run`.

### 2.3 Sessions, states and calibrations as a data model

The FAIS lesson: **one CEINMS calibration per experimental state** (a
calibration built pre-fatigue applied post-fatigue assumes away the effect
being measured). bioscout already has named emg_maps (b13) and named
calibration configs (b14); what is missing is the level above — a subject
with N sessions, each owning its calibration, MVIC set and trial scope, and
tooling to split/scaffold them (`split_sessions.py` generalised). Same need
appears in the Powerlifting project as iterations × calibration arms.

### 2.4 A results layer

Both projects independently rebuilt the same thing on top of raw `.sto`s:
a long-format master table (`Subject Session Trial Task Side Algo Variable
Channel Metric Value`), a time-normalised curves table, incremental
per-(subject, session, variable) updates, and a figure registry that redraws
everything from the tables in seconds. Ship it: `bioscout results update` /
`bioscout results plot`, with the per-trial figures bioscout already draws
registered in the same catalogue. (Prior art in-repo: `bioscout/figures.py`;
FAIS `code/results.py`.) Two hard-won details to keep: read ID-like columns
back as **strings** (subject "021" must not become 21), and replace rows per
(subject, session, variable) so partial rescans never delete sibling data.

### 2.5 Provenance and refusal to mix stale results

A results file should carry: bioscout version, model file hash, session.yaml
hash, calibration id, timestamp. `results update` should refuse (or loudly
flag) outputs whose inputs changed since they were solved — the
"master table quietly mixing a re-run session with a stale one" class of error
has reached a manuscript draft once already.

### 2.6 Validation as a standard QC gate

`muscle_inspect` (moment arms / fibre lengths / strength vs literature bands,
wrap-surface QC, JCF vs literature) is the most transferable thing in the
package and currently the least discoverable. Make `bioscout validate
--model X.osim` a documented, single-command step, with the literature CSVs
versioned and citable, and wire it into the runner as an optional pre-solve
gate. Add the sanity screens learned in the field: JRA peak |force| screening
(single-frame blow-ups — 335 BW hips — should be flagged at solve time, not
found in a group figure), residual/reserve saturation reports.

### 2.7 Portability and packaging

- OpenSim's Python bindings are conda-only and version-fragile — document ONE
  blessed environment per bioscout release (env.yaml in the repo), and make
  every non-solving feature (results, figures, validation on exported data)
  importable WITHOUT opensim installed (lazy imports; mostly true today,
  enforce with a CI job that imports the package in a bare env).
- Kill the `.bat` writers or pair each with a `.sh`; no `shell=True`.
- Path handling through `pathlib` with a MAX_PATH check on Windows.
- CEINMS binaries: pin the version, check the executable at preflight, and
  record its version in provenance.

### 2.8 Engineering hygiene

- **Tests in CI.** The repo's tests run against local sessions on one
  machine. A tiny synthetic session (the "ghost" fixture generalised, few KB)
  should run export→IK→ID→SO on every commit; CEINMS mocked.
- **One source of truth for layout.** The `session_layout` resolvers exist —
  finish migrating every path join to them; the split/legacy-layout confusion
  in FAIS (ik.mot at trial root vs `external_biomechanics/`) is what happens
  when two layouts coexist unnamed. Detect legacy layouts and say so.
- **Structured run report.** End every run with the trial × stage ok/MISS
  table and write it as `run_report.json` next to the log — machine-readable
  status is what makes 29-subject batches auditable.
- **Docs.** A quickstart that goes c3d → JCF figure on a public sample
  dataset in under 30 minutes; the FAIS/Powerlifting projects as case
  studies; every silent-failure trap above documented until it is fixed.

---

## 3. Suggested order of work

1. Preflight + run verification + non-zero exit (2.2, part of 2.8) — kills the
   whole silent-failure class, small effort.
2. EMG map validation at export (§1) — one afternoon, prevents wrong-column
   CEINMS results forever.
3. `bioscout run` + `bioscout.yaml` + first-class `--session` (2.1, 2.3).
4. Results layer + provenance (2.4, 2.5).
5. Validation gate, packaging, CI, docs (2.6–2.8).
