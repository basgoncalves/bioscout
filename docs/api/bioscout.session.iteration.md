# `bioscout.session.iteration`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py)

Iteration — one model iteration of a recording session: the runnable unit.

``Session(path).iteration("gpk")`` returns one. It resolves the iteration's  
models from session.yaml and runs the pipeline stages over the session's  
trials: :meth:`Iteration.scale_model`, :meth:`Iteration.run`  
(exbiomec / muscle_analysis / so / mew / ceinms), EMG normalisation, CEINMS  
calibration, plots.

## Contents

- class [`Iteration`](#iteration) — One (model-iteration, recording-session) on disk — the RUNNABLE unit.
  - [`Iteration.path`](#iterationpath) — 
  - [`Iteration.results`](#iterationresults) — This iteration's results (plus the session's experimental data)::
  - [`Iteration.engine`](#iterationengine) — ``opensim`` (default) or ``pyosim``: what runs this iteration's scaling, IK, ID, MA, SO and JRA (session.yaml ``iterations.<name>.engine``).
  - [`Iteration.tag`](#iterationtag) — ``<session>/<iteration>`` -- the prefix of every log line.
  - [`Iteration.describe`](#iterationdescribe) — Print this iteration: its session.yaml keys (model files resolved, found or MISSING) and which stage outputs each trial has on disk (``trials``: restrict the table; ``[]`` leaves it out).
  - [`Iteration.stage_status`](#iterationstage_status) — ``{trial: {stage: bool}}`` -- which stage outputs exist on disk (the same check ``run()`` reports at the end, devtools.run_check).
  - [`Iteration.trial`](#iterationtrial) — Return an Analyse for one trial, with shared experimental inputs bound.
  - [`Iteration.get_trial`](#iterationget_trial) — The Analyse (trial) object for the session trial ``name`` — explicit alias for :meth:`trial`::
  - [`Iteration.plot_summary`](#iterationplot_summary) — Regenerate the per-trial summary figures for this iteration's trials from data already on disk (no re-solve):
  - [`Iteration.resolve_model_file`](#iterationresolve_model_file) — Find a configured model file. -> absolute path or None.
  - [`Iteration.trial_config`](#iterationtrial_config) — FULL config for one (trial, iteration) from session.yaml.
  - [`Iteration.model_file`](#iterationmodel_file) — The .osim a trial of this iteration loads (Analyse.model_dir).
  - [`Iteration.trials`](#iterationtrials) — 
  - [`Iteration.iterations`](#iterationiterations) — Model-iteration folders configured for this session (session.yaml).
  - [`Iteration.calibration_trials`](#iterationcalibration_trials) — CEINMS calibration trial names (session.yaml, else settings) present here.
  - [`Iteration.ingest_c3d`](#iterationingest_c3d) — Distribute loose ``*.c3d`` into per-trial ``<trial>/inputs/c3dfile.c3d`` under this iteration. ``source`` defaults to the session folder. ``trials`` (name or list) restricts distribution to those c3d (matched by file stem), so only the selected trials' folders are touched; default: every loose ``*.c3d``.
  - [`Iteration.run_emg_normalise`](#iterationrun_emg_normalise) — Session-wide EMG normalisation. The per-channel session-max (MVC-style) reference is computed across ALL of the session's trials; then each written trial's inputs/emg_filtered_normalised.mot is scaled into [0, 1]. ``write_trials`` (name or list) restricts which trials have their normalised file (re)written and their ``replace`` flag touched — the MVC reference STILL spans every trial. Default: write all.
  - [`Iteration.normalise_emg`](#iterationnormalise_emg) — 
  - [`Iteration.run_ceinms_calibration`](#iterationrun_ceinms_calibration) — Calibrate CEINMS once for THIS session, driven off the first calibration trial (dynamic, never the static trial).
  - [`Iteration.calibrate`](#iterationcalibrate) — Calibrate CEINMS for THIS session (settings names, or explicit ones).
  - [`Iteration.prepare_ceinms`](#iterationprepare_ceinms) — Session EMG normalisation, then CEINMS calibration. ``calibration_trials`` restricts which trials the calibration objective uses (e.g. walking-only when you'll execute on walking); default = settings.CEINMSSettings.
  - [`Iteration.prepare_uncalibrated_ceinms`](#iterationprepare_uncalibrated_ceinms) — Everything CEINMS execution needs EXCEPT a calibration.
  - [`Iteration.subject_name`](#iterationsubject_name) — This session's subject id — the folder above the session.
  - [`Iteration.session_name`](#iterationsession_name) — This session's id — the session folder itself.
  - [`Iteration.models_dir`](#iterationmodels_dir) — Where THIS session's personalised models are written and read: ``<project>/models/personalised/<subject>/<session>/``.
  - [`Iteration.model_output_path`](#iterationmodel_output_path) — Absolute path to WRITE a model named ``name`` to.
  - [`Iteration.link_geometry`](#iterationlink_geometry) — Link the generic model's ``Geometry/`` beside the scaled model.
  - [`Iteration.scale_model`](#iterationscale_model) — Build THIS iteration's ONE scaled model, driven by session.yaml.
  - [`Iteration.export_trials`](#iterationexport_trials) — Model-INDEPENDENT c3d export for this session's trials: ingest loose c3d -> markers/GRF/EMG into the SHARED ``experimental/<trial>/`` folder, filter EMG, then (``normalise``) run the session-wide EMG normalise. The raw inputs are shared by every iteration, so this writes ONCE regardless of which iteration anchors it — prefer :meth:`Session.export` over per-iteration ``run(export=True)``.
  - [`Iteration.run`](#iterationrun) — Run the pipeline for THIS iteration.

<a id="iteration"></a>

## class `Iteration`(IterationKeys)

```python
Iteration(session_dir, iteration)
```

| input | type | default |
|---|---|---|
| `session_dir` | – | required |
| `iteration` | – | required |

One (model-iteration, recording-session) on disk — the RUNNABLE unit.

``session_dir`` is the athlete/session folder holding ``session.yaml``  
(e.g. ``simulations/Athlete_03/25_03_31``); ``iteration`` is the model  
sub-folder (``gpk``, ``gpk_mri``, ``cateli`` ...). Trials come from  
``session.yaml`` (``type: static`` entries skipped), restricted to those  
present under this iteration.

Roles:  
  * navigation — ``.path``, ``.trials``, ``.trial(name)``  
  * analysis — ``scale_model``, session-wide EMG normalisation, CEINMS  
    calibration, ``plot_summary``, and the ``run()`` orchestrator  
    (export -> external biomechanics -> SO -> CEINMS).

Usually obtained from a :class:`Session` rather than built directly::

    s  = Session(r"...\simulations\Athlete_03\25_03_31")  
    it = s.iteration("gpk_mri")  
    it.run(trials=["Squat_BW_01", "Walking_02"],  
           do_exbiomec=True, do_so=True, do_ceinms=True, replace=True)

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L130)</sub>

<a id="iterationpath"></a>

### `Iteration.path`

```python
Iteration.path()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L244)</sub>

<a id="iterationresults"></a>

### `Iteration.results`

```python
Iteration.results() -> 'Results'
```

**returns** `'Results'`

This iteration's results (plus the session's experimental data)::

    it.results("ik", trial="Gehen_01").plot()

Same call as :attr:`bioscout.Session.results`, iteration fixed.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L248)</sub>

<a id="iterationengine"></a>

### `Iteration.engine`

```python
Iteration.engine()
```

``opensim`` (default) or ``pyosim``: what runs this iteration's scaling, IK,  
ID, MA, SO and JRA (session.yaml ``iterations.<name>.engine``).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L258)</sub>

<a id="iterationtag"></a>

### `Iteration.tag`

```python
Iteration.tag()
```

``<session>/<iteration>`` -- the prefix of every log line.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L267)</sub>

<a id="iterationdescribe"></a>

### `Iteration.describe`

```python
Iteration.describe(log=print, trials=None)
```

| input | type | default |
|---|---|---|
| `log` | – | `print` |
| `trials` | – | `None` |

Print this iteration: its session.yaml keys (model files resolved,  
found or MISSING) and which stage outputs each trial has on disk  
(``trials``: restrict the table; ``[]`` leaves it out).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L274)</sub>

<a id="iterationstage_status"></a>

### `Iteration.stage_status`

```python
Iteration.stage_status(trials=None)
```

| input | type | default |
|---|---|---|
| `trials` | – | `None` |

``{trial: {stage: bool}}`` -- which stage outputs exist on disk  
(the same check ``run()`` reports at the end, devtools.run_check).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L328)</sub>

<a id="iterationtrial"></a>

### `Iteration.trial`

```python
Iteration.trial(name, force_type='SO')
```

| input | type | default |
|---|---|---|
| `name` | – | required |
| `force_type` | – | `'SO'` |

Return an Analyse for one trial, with shared experimental inputs bound.

Raw inputs (markers/grf/emg/GRF.xml) live once in  
``<session>/experimental/<trial>/`` and are shared by every iteration.  
Setting ``experimental_dir`` makes Analyse redirect them there on every  
settings reload; derived outputs still write under this iteration's own  
trial folder.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L360)</sub>

<a id="iterationget_trial"></a>

### `Iteration.get_trial`

```python
Iteration.get_trial(name, force_type='SO')
```

| input | type | default |
|---|---|---|
| `name` | – | required |
| `force_type` | – | `'SO'` |

The Analyse (trial) object for the session trial ``name`` — explicit  
alias for :meth:`trial`::

    a = Session(session_path).iteration("gpk_mri").get_trial("Walking_02")  
    a.run_ik(); a.plot_jra_comparison()

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L424)</sub>

<a id="iterationplot_summary"></a>

### `Iteration.plot_summary`

```python
Iteration.plot_summary(trials=None, dofs=None, figures=None, **opts)
```

| input | type | default |
|---|---|---|
| `trials` | – | `None` |
| `dofs` | – | `None` |
| `figures` | – | `None` |
| `**opts` | – | – |

Regenerate the per-trial summary figures for this iteration's trials  
from data already on disk (no re-solve):

  * ``kinematics_moments.png``     — plot_kin_mom_summary (IK angles + ID moments)  
  * ``summary``                    — plot_summary (angles + SO/CEINMS muscle moments)  
  * ``jrf_so_vs_ceinms.png``       — plot_jra_comparison (joint contact forces)

Defaults come from ``settings.SummarySettings`` (dofs, analysis_leg,  
algorithms, joints, ...). ``figures`` selects which to make — any of  
``{"kin_mom", "summary", "jra"}`` (default: kin_mom + jra). ``trials``  
defaults to every trial in this iteration. Extra ``SummarySettings``  
keywords are accepted and ignored where they only apply to the  
cross-model overlay figure (that multi-model comparison is  
``summary_figures.py`` / a future session-level overlay).

    it = Session(session_path).iteration("gpk_mri")  
    it.plot_summary(trials=["Walking_03", "Squat_BW_01", "Squat_BW_02"])

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L433)</sub>

<a id="iterationresolve_model_file"></a>

### `Iteration.resolve_model_file`

```python
Iteration.resolve_model_file(mfile)
```

| input | type | default |
|---|---|---|
| `mfile` | – | required |

Find a configured model file. -> absolute path or None.

Search order (2026-08-17 — models used to HAVE to be copied into every  
iteration folder, so the same scaled model existed 3x per subject):  
  1. an absolute path, as given  
  2. relative to THIS iteration folder        (the classic location)  
  3. relative to the session folder            (explicit ../ paths)  
  4. the project models library, in order:  
     ``<project>/<mfile>`` verbatim (project-relative paths),  
     ``models/personalised/<subject>/<name>``,  
     ``models/generic/<name>`` and one level of family subfolders,  
     ``models/<name>`` (flat legacy layout, kept working)  
A session.yaml can therefore keep just the filename and store the model  
once in the project's models/ folder, shared by every session and  
iteration of that subject.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L487)</sub>

<a id="iterationtrial_config"></a>

### `Iteration.trial_config`

```python
Iteration.trial_config(name, force_type='SO')
```

| input | type | default |
|---|---|---|
| `name` | – | required |
| `force_type` | – | `'SO'` |

FULL config for one (trial, iteration) from session.yaml.

``side`` / ``time_range`` / ``trial_type`` from ``trials.<name>``;  
``body_mass`` session-wide; ``emg_map`` (resolved), CEINMS weights and  
calibration flattened as ``ceinms_*`` / ``calibration_*``; the model  
file as ``model_scaled`` (absolute path, the same name as in  
session.yaml). Which model a trial loads: :meth:`model_file`.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L560)</sub>

<a id="iterationmodel_file"></a>

### `Iteration.model_file`

```python
Iteration.model_file(force_type='SO', trial=None)
```

| input | type | default |
|---|---|---|
| `force_type` | – | `'SO'` |
| `trial` | – | `None` |

The .osim a trial of this iteration loads (Analyse.model_dir).

CEINMS: ``model_scaled`` as is. Everything else (IK, ID, MA, SO, mew,  
JRA): :attr:`model_so` -- the same geometry, max isometric force x  
``mvic_factor``; built from ``model_scaled`` here if it is missing.  
None when the iteration names no model.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L682)</sub>

<a id="iterationtrials"></a>

### `Iteration.trials`

```python
Iteration.trials()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L751)</sub>

<a id="iterationiterations"></a>

### `Iteration.iterations`

```python
Iteration.iterations()
```

Model-iteration folders configured for this session (session.yaml).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L755)</sub>

<a id="iterationcalibration_trials"></a>

### `Iteration.calibration_trials`

```python
Iteration.calibration_trials()
```

CEINMS calibration trial names (session.yaml, else settings) present here.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L789)</sub>

<a id="iterationingest_c3d"></a>

### `Iteration.ingest_c3d`

```python
Iteration.ingest_c3d(source=None, dry_run=False, trials=None)
```

| input | type | default |
|---|---|---|
| `source` | – | `None` |
| `dry_run` | – | `False` |
| `trials` | – | `None` |

Distribute loose ``*.c3d`` into per-trial ``<trial>/inputs/c3dfile.c3d``  
under this iteration. ``source`` defaults to the session folder. ``trials``  
(name or list) restricts distribution to those c3d (matched by file stem), so  
only the selected trials' folders are touched; default: every loose ``*.c3d``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L810)</sub>

<a id="iterationrun_emg_normalise"></a>

### `Iteration.run_emg_normalise`

```python
Iteration.run_emg_normalise(replace=None, write_trials=None)
```

| input | type | default |
|---|---|---|
| `replace` | – | `None` |
| `write_trials` | – | `None` |

Session-wide EMG normalisation. The per-channel session-max (MVC-style)  
reference is computed across ALL of the session's trials; then each written  
trial's inputs/emg_filtered_normalised.mot is scaled into [0, 1]. ``write_trials``  
(name or list) restricts which trials have their normalised file (re)written  
and their ``replace`` flag touched — the MVC reference STILL spans every trial.  
Default: write all.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L847)</sub>

<a id="iterationnormalise_emg"></a>

### `Iteration.normalise_emg`

```python
Iteration.normalise_emg(replace=None, write_trials=None)
```

| input | type | default |
|---|---|---|
| `replace` | – | `None` |
| `write_trials` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L1050)</sub>

<a id="iterationrun_ceinms_calibration"></a>

### `Iteration.run_ceinms_calibration`

```python
Iteration.run_ceinms_calibration(replace=None, prefer_trial=None)
```

| input | type | default |
|---|---|---|
| `replace` | – | `None` |
| `prefer_trial` | – | `None` |

Calibrate CEINMS once for THIS session, driven off the first  
calibration trial (dynamic, never the static trial).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L1053)</sub>

<a id="iterationcalibrate"></a>

### `Iteration.calibrate`

```python
Iteration.calibrate(replace=None, calibration_trials=None)
```

| input | type | default |
|---|---|---|
| `replace` | – | `None` |
| `calibration_trials` | – | `None` |

Calibrate CEINMS for THIS session (settings names, or explicit ones).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L1073)</sub>

<a id="iterationprepare_ceinms"></a>

### `Iteration.prepare_ceinms`

```python
Iteration.prepare_ceinms(replace=None, calibration_trials=None)
```

| input | type | default |
|---|---|---|
| `replace` | – | `None` |
| `calibration_trials` | – | `None` |

Session EMG normalisation, then CEINMS calibration. ``calibration_trials``  
restricts which trials the calibration objective uses (e.g. walking-only  
when you'll execute on walking); default = settings.CEINMSSettings.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L1091)</sub>

<a id="iterationprepare_uncalibrated_ceinms"></a>

### `Iteration.prepare_uncalibrated_ceinms`

```python
Iteration.prepare_uncalibrated_ceinms(replace=None, host_trial=None)
```

| input | type | default |
|---|---|---|
| `replace` | – | `None` |
| `host_trial` | – | `None` |

Everything CEINMS execution needs EXCEPT a calibration.

Calibration produces three things execution depends on: the session's  
normalised EMG, the excitation generator, and a subject XML. An  
UNCALIBRATED run still needs the first two -- excitations are what  
execution solves against, calibrated or not. The third is the  
uncalibrated subject: optimal fibre lengths, tendon slack lengths,  
pennation angles and max isometric forces exactly as the OpenSim model  
states them, nothing fitted.

This builds those three and stops. No calibration executable runs, so  
an uncalibrated arm costs execution time only.

-> the uncalibrated subject XML path, or None.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L1098)</sub>

<a id="iterationsubject_name"></a>

### `Iteration.subject_name`

```python
Iteration.subject_name()
```

This session's subject id — the folder above the session.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L1169)</sub>

<a id="iterationsession_name"></a>

### `Iteration.session_name`

```python
Iteration.session_name()
```

This session's id — the session folder itself.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L1174)</sub>

<a id="iterationmodels_dir"></a>

### `Iteration.models_dir`

```python
Iteration.models_dir(create=False)
```

| input | type | default |
|---|---|---|
| `create` | – | `False` |

Where THIS session's personalised models are written and read:  
``<project>/models/personalised/<subject>/<session>/``.

The anatomy does not change between a morning and an afternoon  
session, but the SCALED MODEL does: it is built from that session's  
static trial and its marker set, so two sessions of one subject  
produce two different ``<generic>_scaled.osim``. Sharing one  
``personalised/<subject>/`` folder between them meant the second  
session silently overwrote the first, and neither session could be  
re-analysed afterwards without rescaling.

Kept from the 2026-08-19 change: models still live in the models tree  
rather than scattered through ``3_iterations/``, which is what made  
them impossible to find. Only the subject folder gained a session  
level underneath it.

Backwards compatible on READ: if the session folder does not exist yet  
but the flat ``personalised/<subject>/`` does and holds models, that  
one is returned, so sessions scaled before this change keep working  
until they are next rescaled. ``create=True`` always makes and returns  
the session folder.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L1182)</sub>

<a id="iterationmodel_output_path"></a>

### `Iteration.model_output_path`

```python
Iteration.model_output_path(name, default_stem=None, create=True)
```

| input | type | default |
|---|---|---|
| `name` | – | required |
| `default_stem` | – | `None` |
| `create` | – | `True` |

Absolute path to WRITE a model named ``name`` to.

The mirror of :meth:`_resolve_model_file` (which finds a model to  
READ), so a model lands exactly where session.yaml says it will be  
looked for:

* absolute path            -> used as given  
* contains a separator     -> project-relative, e.g.  
  ``models/personalised/023/023_Rajagopal2015_FAI.osim``  
* bare filename            -> ``models/personalised/<subject>/``

The bare-filename case is the one that changed: it used to mean the  
iteration folder.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L1224)</sub>

<a id="iterationlink_geometry"></a>

### `Iteration.link_geometry`

```python
Iteration.link_geometry(generic_model_path, name='Geometry', dest_dir=None)
```

| input | type | default |
|---|---|---|
| `generic_model_path` | – | required |
| `name` | – | `'Geometry'` |
| `dest_dir` | – | `None` |

Link the generic model's ``Geometry/`` beside the scaled model.

A scaled .osim keeps the generic's relative mesh references  
(``r_femur.vtp`` ...), but it is written into the iteration folder,  
which has no ``Geometry/``. OpenSim's GUI then loads the model with no  
bones and no muscle paths — "Couldn't find file 'r_femur.vtp'" — and  
the model looks broken when it is fine.

A LINK, not a copy: the mesh set is tens of megabytes and identical for  
every iteration and every subject that shares the generic, so copying  
it would multiply it across the whole simulations tree. On Windows this  
is a directory JUNCTION, which needs no elevation and no developer  
mode, unlike a true symlink. Never fails the scaling — if the link  
cannot be made, it says so and moves on, because a missing mesh affects  
only what you can SEE, never what is computed.

Returns the link path, or None.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L1252)</sub>

<a id="iterationscale_model"></a>

### `Iteration.scale_model`

```python
Iteration.scale_model(
    static_trial=None,
    n_eval=None,
    mass=None,
    replace=True,
    muscle_opt=None,
    marker_placer=None,
    linear_scaling=None
)
```

| input | type | default |
|---|---|---|
| `static_trial` | – | `None` |
| `n_eval` | – | `None` |
| `mass` | – | `None` |
| `replace` | – | `True` |
| `muscle_opt` | – | `None` |
| `marker_placer` | – | `None` |
| `linear_scaling` | – | `None` |

Build THIS iteration's ONE scaled model, driven by session.yaml.

Pipeline (each keyword overrides the matching ``session.yaml`` value)::

    generic + static  --ScaleTool-->  scaled.osim  
                           (MarkerPlacer registers markers to the static  
                            pose; dimensional scaling only if linear_scaling)  
                      --Modenese2015 muscle-opt-->  scaled_opt_N<n>.osim   (= CEINMS model)  
                      -> model_scaled   (CEINMS uses it as is)  
                      --isometric force x mvic_factor-->  model_so (SO, derived)

No ``model_generic`` in the iteration means ``model_scaled`` is a given  
(MRI/TPS) model: nothing is scaled, only the SO copy is written.

  
**Parameters**

static_trial : str, optional  
    Name of the static trial whose markers drive scaling/registration.  
    Read from the SHARED ``experimental/<static_trial>/marker_experimental.trc``.  
    Defaults to session.yaml's ``static_trial:`` — NOT to a hardcoded  
    name. It used to default to ``"Static_01"``, so a session whose  
    static trial is called anything else (``static1``, the FAIS  
    convention) scaled against a trial that does not exist: "static  
    TRC not found", no model, and every downstream stage failing for  
    every trial, with the session file naming the right trial all  
    along.  
n_eval : int, optional  
    Number of Modenese2015 muscle-optimisation evaluations. Defaults to  
    this iteration's ``opt_neval`` in session.yaml (or 10). Ignored when  
    ``muscle_opt=False``.  
mass : float, optional  
    Target total body mass (kg) for ScaleTool. Defaults to session.yaml  
    ``body_mass``.  
replace : bool  
    If False and both output models already exist, skip and return the SO  
    model path. If True, rebuild.  
muscle_opt : bool, optional  
    True  -> run the (slow, minutes) Modenese2015 muscle-parameter  
             optimisation, producing ``<subject>_scaled_opt_N<n>.osim``  
             as the force model. Needed for SO/CEINMS.  
    False -> stop after the scaled model and use it directly as the  
             force model (keeps the generic's OFL/TSL — right for a  
             validated MRI/personalised model). Fast; enough for  
             external biomechanics (IK/ID/MA).  
    Defaults to this iteration's ``muscle_opt:`` in session.yaml  
    (True when absent), so "this model is not re-fit" is recorded with  
    the model rather than retyped at every call site.  
marker_placer : bool, optional  
    Override ScaleTool's MarkerPlacer stage. Default: session.yaml  
    ``marker_placer`` (else False).  
linear_scaling : bool, optional  
    Override dimensional (segment) scaling. Default: session.yaml  
    ``linear_scaling`` (else True). Set False to keep MRI segment geometry.

  
**Returns**

str or None  
    Absolute path to the SO model (``it.model_so``; ``None`` if the  
    generic/static is missing). ``model_scaled`` is written where  
    session.yaml says (relative to the iteration folder); unset, it goes  
    to ``models/personalised/<subject>/<session>/<iteration>_scaled.osim``  
    and the line to add is printed. A different ``mvic_factor`` is a  
    different iteration (session.add_iteration).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L1303)</sub>

<a id="iterationexport_trials"></a>

### `Iteration.export_trials`

```python
Iteration.export_trials(
    trials=None,
    export_src=None,
    replace=False,
    normalise=True,
    detect=True,
    log=print
)
```

| input | type | default |
|---|---|---|
| `trials` | – | `None` |
| `export_src` | – | `None` |
| `replace` | – | `False` |
| `normalise` | – | `True` |
| `detect` | – | `True` |
| `log` | – | `print` |

Model-INDEPENDENT c3d export for this session's trials: ingest loose c3d ->  
markers/GRF/EMG into the SHARED ``experimental/<trial>/`` folder, filter EMG,  
then (``normalise``) run the session-wide EMG normalise. The raw inputs are  
shared by every iteration, so this writes ONCE regardless of which iteration  
anchors it — prefer :meth:`Session.export` over per-iteration ``run(export=True)``.

``detect`` (default True) then runs movement detection over what was just  
exported, writing ``movement_detection.yaml`` and ``movement_detection.png``  
into each trial folder, beside the data they describe. It reads the markers  
and GRF the export just wrote, so this is the moment where it is cheapest —  
and it never touches ``session.yaml``: a disagreement is reported, not  
applied. Set ``detect=False`` to skip it. Returns the list of trials  
exported.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L1665)</sub>

<a id="iterationrun"></a>

### `Iteration.run`

```python
Iteration.run(
    trials=None,
    export=False,
    export_src=None,
    detect=True,
    do_scale=False,
    do_exbiomec=False,
    do_muscle_analysis=False,
    do_so=False,
    do_rra=False,
    do_forward=False,
    do_cmc=False,
    cmc_duration=None,
    do_mew=False,
    do_ceinms=False,
    do_iaa=False,
    iaa_opts=None,
    calibrate=False,
    calibration_trials=None,
    replace=False,
    mew_opts=None,
    do_contrib=None,
    contrib_groups=None,
    contrib_jobs=None,
    log=print,
    **_ignored
)
```

| input | type | default |
|---|---|---|
| `trials` | – | `None` |
| `export` | – | `False` |
| `export_src` | – | `None` |
| `detect` | – | `True` |
| `do_scale` | – | `False` |
| `do_exbiomec` | – | `False` |
| `do_muscle_analysis` | – | `False` |
| `do_so` | – | `False` |
| `do_rra` | – | `False` |
| `do_forward` | – | `False` |
| `do_cmc` | – | `False` |
| `cmc_duration` | – | `None` |
| `do_mew` | – | `False` |
| `do_ceinms` | – | `False` |
| `do_iaa` | – | `False` |
| `iaa_opts` | – | `None` |
| `calibrate` | – | `False` |
| `calibration_trials` | – | `None` |
| `replace` | – | `False` |
| `mew_opts` | – | `None` |
| `do_contrib` | – | `None` |
| `contrib_groups` | – | `None` |
| `contrib_jobs` | – | `None` |
| `log` | – | `print` |
| `**_ignored` | – | – |

Run the pipeline for THIS iteration.

Stages (each optional, run in this order):  
  do_scale    : build this iteration's scaled models first (delegates to  
                :meth:`scale_model`, reading session.yaml). Does not need  
                trials. Use when you want scale + analysis in one call.  
  export      : (re)build inputs from c3d + refresh window + filter EMG,  
                then session-wide EMG normalise, then movement detection  
                into each ``2_experimental/<trial>/`` (``detect=False``  
                skips that last part). ``export_src`` first distributes  
                loose ``*.c3d`` into each trial's inputs/.  
  do_exbiomec : external biomechanics only (IK -> ID). Muscle Analysis  
                is its own stage — see ``do_muscle_analysis``.  
  do_muscle_analysis : Muscle Analysis (muscle lengths + moment arms).  
                Required by ``do_so``; when do_so runs without it, any  
                missing MA output is filled in without overwriting.  
  do_so       : SO stage (SO -> muscle moments -> JRA), needs IK/ID/MA.  
  do_rra      : Residual Reduction Algorithm on the IK/GRF of each trial  
                -> ``<trial>/residual_reduction/`` (adjusted kinematics,  
                residuals, COM-adjusted model). Needs IK/ID (filled if  
                missing). Diagnostic only: nothing downstream uses its  
                outputs unless you point an iteration at them.  
  do_forward  : forward simulation: CMC tracking (muscle-driven) then the  
                CMC excitations replayed open-loop with ForwardTool, + JRA on  
                the CMC forces -> ``<trial>/forward_simulation/``. Uses the  
                RRA kinematics/model when residual_reduction/ exists.  
  do_mew      : mew (bioscout.simulate.mew, the Python muscle solver)  
                -> JRA, into ``<trial>/mew/``. Needs IK/ID/MA and the SO  
                force file (its residual/reserve columns balance the  
                JRA); missing prerequisites are filled, never  
                overwritten. ``mew_opts`` is passed to  
                :func:`bioscout.simulate.mew.analyse_trial` (``tier``,  
                ``smoothing``, ``filter_hz``, ``jcf``, ``plot``).  
  do_ceinms   : CEINMS calibration (once) + per-trial execution -> JRA.  
  do_iaa      : induced acceleration analysis on the SO forces (each  
                muscle's / actuator's / gravity's / velocity's share of  
                every coordinate's acceleration, the COM acceleration  
                and each foot's GRF) -> ``<trial>/induced_accelerations/``.  
                Needs SO (filled if missing). ``iaa_opts`` goes to  
                Trial.run_iaa: ``engine`` ("opensim" | "pyosim" | "both"),  
                ``constraint`` ("rolling" | "point" | "weld"),  
                ``force_threshold`` (N).  
  do_contrib  : after each trial's SO JRA, also the muscle-group  
                contributions to the JCF (run_jra_contributions ->  
                joint_contact_forces/contributions_so.*). Default: the  
                iteration's ``jra_contributions`` in session.yaml, else True.  
                ``contrib_groups`` = dict, or callable(SO force columns,  
                trial) -> dict; ``contrib_jobs`` caps the parallel JRA runs.  
                A failure here is logged and never fails the trial.

``replace`` overwrites existing outputs. ``trials`` defaults to all trials.  
``calibrate`` (default True) — when do_ceinms is on, calibrate once first;  
set ``calibrate=False`` to SKIP calibration and run only execution -> JRA  
against the existing ``ceinms_calibration/subjectCalibrated.xml``.

``ceinms: {calibrated: false}`` in session.yaml overrides both: the  
iteration executes against ``subjectUncalibrated.xml`` (built straight  
from the .osim, nothing fitted), no calibration runs whatever  
``calibrate`` says, and every execution folder is tagged ``_uncal`` so  
it cannot be mistaken for — or overwrite — a calibrated result. The same  
key on an ITERATION overrides the session-wide one, so an uncalibrated  
control can live beside the calibrated arms it is the control for.

Unknown keyword arguments are ignored (forward-compat). Returns a dict  
of trials that completed each stage.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/iteration.py#L1856)</sub>
