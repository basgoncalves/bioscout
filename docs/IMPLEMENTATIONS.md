# IMPLEMENTATIONS.md — what bioscout needs to serve researchers beyond us

Written 2026-08-17, after running bioscout as the engine of two real studies —
the **Powerlifting** model-personalisation project (6 models × 2 athletes,
SO vs CEINMS) and the **FAIS machine-learning** project (29 subjects, a
pre/sprints/post fatigue protocol). Everything here was learned the hard way in
those projects; the point of this file is that the next lab should not have to.

Status tags: **[fixed]** shipped, **[patched-in-project]** works but lives in
project code and belongs in bioscout, **[open]** not addressed anywhere.

§1–2 are about getting a *trial* through the pipeline. §3 is the other axis —
building, organising and trusting the `.osim` files themselves — added after the
FAIS MRI-personalisation work, which is currently four hand-run scripts with no
bioscout verb behind them.

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
- **[fixed 2026-08-17] A model that has been moved loads with NO BONES, in
  silence.** OpenSim resolves `<geometry_file>` (v3) / `<mesh_file>` (v4)
  relative to the folder holding the `.osim`. Move a model, or move the
  geometry out from under it — which is what any tidy-up of `models/` does, and
  what writing a personalised model into a new subfolder does — and it opens
  with muscles and markers and no skeleton, with no error and no log line.
  Handling only one of the two tag names breaks the other schema family just as
  quietly. Now checked by `bioscout.model` (see 3.2): `bioscout
  --model`, and a warn-level check on every `Analyse.load_model`. Two
  variants of the same silence are checked with it — a mesh found only by
  ignoring filename case (works on Windows, fails on Linux) and one found only
  by absolute path (points somewhere else on any other machine). *Lesson: the
  tier that resolved a path is the finding, not whether it resolved.*

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

### 2.9 Retiring `settings.py` — the design that replaces it

*(2026-08-19, after the FAIS models/ reorg made most of settings.py
redundant in practice. This section is the concrete design behind §2.1's
one-paragraph sketch; §2.1's verbs are the interface, this is the data model
under them.)*

**Diagnosis first.** The reason a copied `settings.py` keeps hurting is not
that it is long — it is that one file conflates FIVE kinds of thing that have
different owners, different lifetimes and different change rates, and only by
separating them does the "functions repeated per project drift into version
skew" problem actually disappear:

| what settings.py holds today | what it really is | where it belongs |
|---|---|---|
| `Subject`, `Inputs`, `build_model_config`, the runner functions | **library code** | bioscout, versioned ONCE, upgraded by `pip install -U`. Copying code into projects is the entire drift problem — the Powerlifting copy is 112 lines ahead of the template while both claim schema `2.0.0b1`, and `check_settings_version` cannot see it because you cannot diff the *shape* of arbitrary code |
| marker conventions, EMG rig channel names, plate mapping, filter defaults | **lab facts** (true for every session this lab records) | a small declarative `project.yaml` at the project root — data, not code |
| trials, time windows, body mass, models, emg_map, calibrations | **session facts** | `session.yaml` — already done; the models/markerset/emg_filter moves of 2026-08-18/19 completed it |
| `SUBJECTS = ["021"]`, `TRIALS = [...]`, `DO_SO`, `--replace` | **run selection** (true for one afternoon) | the CALL SITE — CLI flags, the notebook control panel, the GUI. Never persisted: a selection written into a settings file is why "run the pipeline" silently re-ran one subject from March |
| `MODELS_DIR`, `SIMULATIONS_DIR`, ... | **paths** | convention. The folder layout (`models/{generic,personalised,utils}`, `simulations/<subject>/<session>`, `results/`) IS the configuration; only a deviation needs stating |

**The replacement: `project.yaml`.** Everything a project legitimately needs
to declare fits in ~20 data-only lines:

```yaml
# project.yaml — lab facts and deviations from convention. No code.
schema: 1
name: FAIS
lab:
  markerset: models/utils/markers_FAIS.xml     # session.yaml may override
  trc_axes: yzx
  emg_label_pattern: "Voltage"
  emg_filter: {bandpass_low: 10, bandpass_high: 500, notch: 50}
defaults:
  iteration: rajagopal_fai
  algorithms: [SO, CEINMS]
# paths: only if the convention is broken, e.g.
# paths: {simulations: simulations_test}
```

Being data buys what code can never have: the schema can be validated on
load, diffed between projects, and MIGRATED explicitly (`bioscout project
migrate` rewrites schema 1 → 2 with a backup, the same way session.yaml
edits go through span patches). "Template drift" stops being silent because
there is no template to copy — `bioscout project init` *generates* the file,
and an old file is upgraded, not diverged from.

**Discovery instead of declaration.** The batch runner stops reading
`SUBJECTS`/`SESSIONS` from anywhere. It enumerates
`simulations/*/*/session.yaml` — the sessions that exist ARE the cohort —
and the CLI narrows: `bioscout run --subjects 021 022 --sessions pre post`.
`Project()` already auto-populates subjects this way when settings.py
declares none; make that the only path.

**The escape hatch, fenced.** Some logic is genuinely project-specific and
genuinely code — FAIS's "trial `RunL*` means post-fatigue", the task-split
labeller. That goes in an OPTIONAL `project_hooks.py` with a documented
3-function interface (`label_trial(name) -> dict`, `classify_overrides`,
`on_export_done`), imported if present. One small file with a stable
interface is auditable; a 999-line file where config and code interleave is
not. Everything else that today reaches into settings
(`figure_jcf_polar.py`'s `import settings as CFG`, movement_detector's
settings-above-the-session lookup, `emg_filter`'s BatchSettings tier) reads
`project.yaml` through one accessor: `bioscout.project_config(path)` — one
loader, one cache, one schema check.

**Migration, non-breaking, in four steps:**

1. `Project()` prefers `project.yaml`, falls back to `settings.py` with a
   one-line deprecation note. Nothing breaks on day one.
2. `bioscout project init` writes a `project.yaml` FROM an existing
   settings.py (the lab facts are mechanically extractable — BatchSettings
   attributes map 1:1), so migrating a project is one command plus a diff
   review.
3. Consumers move to `project_config()`: the figure scripts, the movement
   detector, the emg_filter precedence tier (which becomes
   session.yaml → project.yaml → bioscout defaults — same three tiers,
   with data replacing code in the middle).
4. Delete the bundled 999-line template from the package; `init_project`
   scaffolds `project.yaml` + folder layout instead. `settings.py` in old
   projects keeps working through step 1's fallback until the projects
   migrate themselves.

**Answering the design question directly:** no, per-project `settings.py`
is not a good organisation, and the failure mode is exactly the one
observed — code copied per project ages independently, and the version
check that should catch it cannot, because code has no diffable schema. The
rule that fixes it for good: **code lives in the package, facts live in
data files (project.yaml for the lab, session.yaml for the session),
choices live at the call site.** Any future feature that wants a new
setting must first answer which of the five kinds it is — and if the answer
is "code", it goes in bioscout, not in the project.

---

## 3. The model side: personalisation, model trees, model verification

§2 is about getting a *trial* through the pipeline. This section is about the
other axis, which FAIS exercised hard in August 2026 and which bioscout barely
covers: producing, organising and trusting the `.osim` files themselves. Four
scripts now live in `FAIS_machine_learning/{code,mri}/` and are run by hand:

    python code/reorganise_models.py --apply | --verify
    python mri/create_mri_model.py --subject 021 --side both --method all --yes
    python mri/verify_morph.py <source.osim> <morphed.osim>
    python mri/muscle_inspect.py --subject 021

None of the four had an equivalent verb in bioscout, and all four are generic.
The `--verify` half of the first one now does: see 3.2.

### 3.1 Model personalisation back-ends beyond TPS

`bioscout/tps_personalise/` already does the hard parts of model rewriting:
v3/v4 schema normalisation (`osim_format.py`), a comment-preserving parser
(`osim_model.py:_commented_parser`), frame-compatibility refusal
(`model_compat.assert_template_compatible`), mesh warping
(`pipeline._apply_body_meshes`), MRI landmark extraction from NIfTI
segmentations (`landmarks_from_mri.py`), Handsfield force scaling
(`scaling.py`) — and exactly **one** morph, `tps.OneBodyTPS`.

FAIS `mri/create_mri_model.py` (1500 lines) adds three more back-ends and,
critically, re-implements `OsimModel` from scratch to do it — a parallel copy of
machinery bioscout already ships. Port the back-ends, not the copy:

| back-end | what it changes | why it matters |
|---|---|---|
| `TorsionMorph` | AVA + NSA by regional rigid rotation about the shaft axis, smooth blend zone, distal femur exactly invariant | the Torsion Tool concept (Veerkamp 2021) in pure Python, no MATLAB, no OpenSim import. Changes only the two angles you measured |
| `TibialTorsionMorph` | tibial torsion | same, distally |
| `RigidPassthrough` | nothing | produces the M0 baseline arm through the *identical* code path, so an arm comparison is not confounded by the writer |
| `TPSMorph` | landmark-driven TPS | already in bioscout — but see 3.4: FAIS measured it failing |

`bioscout/tps_personalise/` should be renamed to something honest
(`personalise/`) with the morph selected by `--method`, since "TPS" is now one
option out of four and the least trustworthy of them.

Two design details worth keeping verbatim. First, the morph applies the
*difference* between the subject's angles and the **generic model's own**
angles, and the generic baseline is an input, not a constant — a wrong baseline
biases every subject the same way and is indistinguishable from a real group
effect. bioscout should measure the baseline from the template's bone geometry
rather than prompt for a literature value. Second, `morph_markers = false` by
default: if the skin markers do not move, IK is driven by identical data in
every arm, so any difference downstream comes from bone geometry alone.

### 3.2 `bioscout --model` — geometry resolution **[verifier fixed 2026-08-17]**, layout still open

**Shipped:** `bioscout/model/` — pure stdlib, no OpenSim, no numpy.

    bioscout --model                     # the project's model folders
    bioscout --model "generic models" --strict
    python -m bioscout.model --verify --json geometry.json
    from bioscout.model import verify_model, verify_tree, format_text

Every `<geometry_file>` and `<mesh_file>` in the document — including the ground
and contact meshes v4 puts *outside* the body set — is resolved from that
model's own folder outward, and the report names the **tier** that hit:
`local` (portable, the only pass), `parent`, `bundled`, `search`, `absolute`,
`case`, `empty` (zero-byte mesh), `missing`. Non-local tiers warn; `--strict`
fails on them. Non-zero exit, so it gates a script or a CI job. It is also
wired as a warn-level check into `Analyse.load_model`, and — like `--env` — is
dispatched *before* `__main__.py` imports the scientific stack, so the question
"can my models still find their bones?" can be asked on a machine where
bioscout cannot otherwise start. 30 unit tests on synthetic v3 and v4 fixtures,
in `bioscout/tests/test_model.py`.

What it found on first contact, in trees believed to be fine:

| tree | finding |
|---|---|
| FAIS `models/` | 3 BROKEN. All three Catelli models reference `l_pat.vtp`; the file is `l_patella.vtp` — they have been opening with no left patella. The v3 one also wants `{l,r}_pelvis_Rajagopal.vtp` and `sacrum_Rajagopal.vtp`, which exist nowhere: no pelvis either. |
| FAIS `models/` | 56 NOT PORTABLE. 79 of 81 refs carry the `Raja\` prefix a rewrite gave them; `metacarpal3_rvs.vtp` and `middle_medial_rvs.vtp` were left bare and resolve **only because bioscout is installed and ships the same mesh**. Uninstall bioscout, or open the model in the OpenSim GUI, and two hand bones vanish. |
| FAIS `models/personalised/` | clean — the torsion-morphed models resolve locally. |
| Powerlifting `generic models/` | live models clean; 8 broken copies under `to_delete/` (GPK and Lernagopal, missing both tibiae). |

*Still open:* the reorganiser. FAIS `code/reorganise_models.py` moves generic
templates into
`generic models/<family>/{*.osim, Geometry/}`, rewrites every geometry path by
**text substitution on the tag lines only** (so the 54 production models stay
byte-identical apart from those lines), backs up everything it touches, updates
the `generic:` key in 54 `session.yaml` files, and then re-verifies.

bioscout today has: a layout created once by `run_init_mode`
(`__main__.py:1315`), `MODELS_DIR` in `settings.py`, and a `models/<subject>/
<session>/` convention in `utils/analysis.py`. It has no registry, no
reorganiser, and no verifier — and `pipeline.py:584` already papers over the
mess by falling back through `Models/`, `generic models/` and the project root.
Also note: bioscout resolves a relative sub-path against those roots but does
**not** search subfolders, so any nested layout needs the prefix written into
`session.yaml` — which is why the FAIS script has to edit 54 files.

Still wanted, on top of the shipped `--verify`:

    bioscout --model --reorganise [--apply]
    bioscout --model --list      # generic / scaled / personalised, per subject

and `--verify` should be called by preflight (2.2) once preflight exists — the
per-model warning in `Analyse.load_model` is the interim, and it deliberately
only warns, because a missing mesh does not make a solve wrong. What it breaks
is every visual check a human would use to notice that something else is.

### 3.3 `bioscout model-diff` — verify every edit, not just morphs

`mri/verify_morph.py` is 180 lines and checks: element count and tag sequence
unchanged, XML comments still present, the region that must not move has
displacement **exactly** 0.0, the region that should move did move and by a
plausible amount (0.1–60 mm), child joint frames bit-identical, geometry still
resolves from the *new* folder, and bodies outside the target untouched. Exit
code gates a script.

That is not a morph-specific test — it is the post-condition contract for
**every one of the 15 `model_edit` ops**, none of which has one today
(`model_edit` ships `info`, `check_paths`, `diff`, `compare` as *inspection*
verbs; nothing asserts an invariant and fails). Generalise it to
`bioscout model-diff A.osim B.osim --expect-unchanged <bodies|frames>` and have
`model_edit apply` run the relevant subset automatically, refusing to write
otherwise. Same principle as the b17 JRA fix: refuse rather than degrade.

### 3.4 Plausibility gates and provenance on written models

The TPS arm for subject 009 displaced muscle attachments by **1.3 metres** —
because only 2 of 6 control points carried information and they were nearly
collinear along the shaft, so the biharmonic kernel extrapolated the
trochanteric attachments into nonsense. `create_mri_model.py` caught it, printed
the numbers, and **refused to write the model** without `--force`. A silently
written broken model that reaches CEINMS is far worse than a build that stops.
bioscout's TPS path has `model_compat` frame checks but no displacement gate:
add one, plus the degenerate-control-point detection (rank / collinearity of the
landmark set) that explains *why* a warp is under-determined.

Every written model should carry the provenance JSON and re-runnable recipe
`create_mri_model.py` already emits (`--config <recipe>.json` rebuilds it) —
this is 2.5 applied to models, and it is what makes a comparison ladder
auditable months later.

### 3.5 Cohort-level measurement QC, and a two-model muscle-geometry diff

Two smaller pieces, both of which found real errors in the data:

- **`--report-only`**: recompute AVA/NSA for every fiducial file in the cohort
  and print a table with flags. It found subject 010 at 62.3°/41.1° — not
  physiological, and disagreeing with two spreadsheets — and subject 015
  missing three landmarks entirely. The angle convention was validated by
  reproducing 10/10 recorded values to 0.1°. This belongs next to
  `bioscout validate` (2.6) as a cohort input-QC table, with the derived value
  treated as the source of truth over any spreadsheet.
- **`mri/muscle_inspect.py`**: per-muscle *diff* between two models — max
  attachment displacement, and moment arm r(q) = −dL/dq swept through each hip
  DOF for both models, ranked by change, CSV + two figures. It runs with **no
  OpenSim installed**, and it flags muscles whose real path is wrap-dominated
  because their absolute values are then approximate.
  bioscout's `muscle_inspect` is single-model-vs-literature and
  `MomentArmModel._require_opensim()`s; `muscle_inspect compare` compares
  *settings*, not models; `--compare-models` (`utils/model_report.py`) compares
  segment dimensions, masses and mesh scale, not muscle geometry. So this is a
  genuine gap: add a `--baseline <model>` diff mode, and keep the OpenSim-free
  straight-line path model as the fast pre-check it is (documented as a ranking
  tool, never as publishable moment arms).

  *Housekeeping:* the project file is named `muscle_inspect.py` and sits on
  `sys.path` next to its importer, so it shadows `bioscout.muscle_inspect`.
  Rename it on the way in.

### 3.6 Where this lands for the user

Terminal, mirroring the four commands above:

    bioscout --model [--strict]            # DONE
    bioscout --model --reorganise --apply
    bioscout personalise --subject 021 --side both --method torsion|tps|rigid|all
    bioscout personalise --report-only
    bioscout model-diff <a.osim> <b.osim>
    bioscout validate --model <x.osim>          # 2.6, existing muscle_inspect

GUI: the existing **Model Scaling** tab is the natural host for `--model`
(it is where a model is produced) and for a Personalise panel —
subject, side, method checkboxes, generic-baseline fields, a dry-run that shows
the displacement report and the plausibility verdict before writing. The
**File Editor** tab already edits the XML; **Results** already plots multi-model
comparisons via `figures.py` `m_model_effects*` and `mi_*`, so once an arm is a
registered model rather than an ad-hoc file, the plots are free.

---

## 4. Suggested order of work

1. Preflight + run verification + non-zero exit (2.2, part of 2.8) — kills the
   whole silent-failure class, small effort.
2. EMG map validation at export (§1) — one afternoon, prevents wrong-column
   CEINMS results forever.
3. ~~Geometry resolution check + `--model` (3.2)~~ — **done
   2026-08-17.** Found 3 broken and 56 non-portable models on the first run.
4. `bioscout run` + `project.yaml` + first-class `--session` (2.1, 2.3, 2.9 —
   2.9 is the data model; FAIS is the pilot: its settings.py is already
   functionally redundant after the session.yaml/models moves).
5. Results layer + provenance (2.4, 2.5).
6. `model-diff` invariants wired into `model_edit apply` (3.3), then the torsion
   back-end and plausibility gate (3.1, 3.4).
7. Validation gate incl. cohort measurement QC, packaging, CI, docs (2.6–2.8,
   3.5).
