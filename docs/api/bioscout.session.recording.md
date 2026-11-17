# `bioscout.session.recording`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/recording.py)

Session — one recording session folder (the one holding session.yaml).

``bs.Session(path)`` opens it (logging + project bootstrap), lists and creates  
its model iterations (:meth:`Session.iteration`, :meth:`Session.add_iteration`),  
and runs/exports/summarises/resets across them. Project-wide operations (every  
session of every subject) live on :class:`bioscout.Project`.

## Contents

- class [`Session`](#session) — A recording session (e.g. ``25_03_31``) — the setup object that unifies one session's config (``session.yaml``) and its model iterations. Iterations are the runnable units::
  - [`Session.describe`](#sessiondescribe) — Print what this session declares and what it has on disk: the session-wide keys, the trials by type and role, then every iteration (:meth:`Iteration.describe`: its models found or MISSING, marker set, scaling recipe, CEINMS, and which stage outputs each trial has). ``trials=False`` leaves out the per-trial stage tables.
  - [`Session.iterations`](#sessioniterations) — Model-iteration folders present on disk (the ground truth), unioned with any ``session.yaml`` ``iterations`` keys — excluding shared dirs (``experimental``, ``logs``) and dotfiles. ``session.yaml`` need not list every iteration; the folders do.
  - [`Session.iteration`](#sessioniteration) — Return the runnable :class:`Iteration` for model ``name``.
  - [`Session.add_iteration`](#sessionadd_iteration) — Declare a new model iteration in session.yaml, copied from an existing one.
  - [`Session.migrate`](#sessionmigrate) — Rewrite session.yaml to the current schema. Returns the new text.
  - [`Session.run`](#sessionrun) — Run several iterations with the same stage flags. ``iterations`` defaults to every iteration present on disk. ``do_scale`` builds each iteration's scaled models first (delegates to :meth:`Iteration.scale_model`, reading ``session.yaml``); the remaining keyword args forward verbatim to :meth:`Iteration.run` (``trials``, ``do_exbiomec``, ``do_so``, ``do_ceinms``, ``replace`` ...)::
  - [`Session.export`](#sessionexport) — Session-level c3d export, done ONCE. The raw markers/GRF/EMG are model- INDEPENDENT and shared by every iteration (they live in ``experimental/<trial>/``), so exporting per-iteration just repeats identical work. This ingests loose c3d -> markers/GRF/EMG -> filters EMG -> runs the session-wide EMG normalise -> classifies each trial (``detect``, writing ``movement_detection.yaml`` and ``.png`` into the trial folder), once. Prefer this over per-iteration ``run(export=True)``::
  - [`Session.scale_model`](#sessionscale_model) — Convenience: scale EVERY iteration's model (scaling only, no analysis). The real implementation lives on :meth:`Iteration.scale_model`; this just loops it over ``iterations`` (default: all). For scale + analysis in one call, prefer ``run(do_scale=True, ...)``.
  - [`Session.events`](#sessionevents) — Gait events of one trial as a DataFrame (name, event, n, side, time, source, on_plate, at_record_edge)::
  - [`Session.results`](#sessionresults) — This session's results -- call it to load, nothing is read before::
  - [`Session.summarise`](#sessionsummarise) — Cross-model comparison figures for this session: overlay EVERY model iteration (cateli/gpk/gpk_mri/...) on the same axes, one figure per trial TYPE, written FLAT into ``out_dir`` (default ``<project>/results/<subject>/ <session>``). Reuses each iteration's on-disk kinematics / ID moments / JRA (no re-solve). Colours/labels come from ``session.yaml`` iterations; SO = solid, CEINMS = dashed.
  - [`Session.reset`](#sessionreset) — Strip THIS session's trial folders back to inputs-only.
- [`find_session_dir`](#find_session_dir) — Locate the athlete/session folder holding session.yaml for ``session`` (layout: ``simulations/<athlete>/<session>/session.yaml``).

<a id="session"></a>

## class `Session`(SessionKeys)

```python
Session(path, project_dir=None, verbose=False, bootstrap=True)
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `project_dir` | – | `None` |
| `verbose` | – | `False` |
| `bootstrap` | – | `True` |

A recording session (e.g. ``25_03_31``) — the setup object that unifies  
one session's config (``session.yaml``) and its model iterations. Iterations  
are the runnable units::

    s  = Session(r"...\simulations\Athlete_03\25_03_31")  
    s.iterations                     # ['cateli', 'gpk', 'gpk_mri', ...]  
    it = s.iteration("gpk_mri")      # -> Iteration (runnable)  
    it.run(trials=["Walking_02"], do_so=True)  
    it.scale_model(muscle_opt=False)  
    it.plot_summary(trials=["Walking_02"])

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/recording.py#L104)</sub>

<a id="sessiondescribe"></a>

### `Session.describe`

```python
Session.describe(log=print, trials=True)
```

| input | type | default |
|---|---|---|
| `log` | – | `print` |
| `trials` | – | `True` |

Print what this session declares and what it has on disk: the  
session-wide keys, the trials by type and role, then every iteration  
(:meth:`Iteration.describe`: its models found or MISSING, marker set,  
scaling recipe, CEINMS, and which stage outputs each trial has).  
``trials=False`` leaves out the per-trial stage tables.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/recording.py#L169)</sub>

<a id="sessioniterations"></a>

### `Session.iterations`

```python
Session.iterations()
```

Model-iteration folders present on disk (the ground truth), unioned  
with any ``session.yaml`` ``iterations`` keys — excluding shared dirs  
(``experimental``, ``logs``) and dotfiles. ``session.yaml`` need not list  
every iteration; the folders do.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/recording.py#L214)</sub>

<a id="sessioniteration"></a>

### `Session.iteration`

```python
Session.iteration(name)
```

| input | type | default |
|---|---|---|
| `name` | – | required |

Return the runnable :class:`Iteration` for model ``name``.

An iteration DECLARED in session.yaml but not yet on disk is created  
here. Declaring it was previously not enough — the folder only appeared  
as a side effect of some earlier step, so adding a model to session.yaml  
and calling ``s.iteration(name)`` raised FileNotFoundError and listed  
the very name you had just declared as "available". A name that is not  
declared still raises, so a typo is still an error.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/recording.py#L254)</sub>

<a id="sessionadd_iteration"></a>

### `Session.add_iteration`

```python
Session.add_iteration(name, copy_from=None, **overrides)
```

| input | type | default |
|---|---|---|
| `name` | – | required |
| `copy_from` | – | `None` |
| `**overrides` | – | – |

Declare a new model iteration in session.yaml, copied from an existing one.

``copy_from=None`` starts an empty block instead: ``model_scaled`` set  
to ``models/personalised/<subject>/<session>/<name>_scaled.osim`` and  
``label`` to ``name``; give ``model_generic=`` (and ``markerset=``) as  
overrides or fill them in the file before scaling.

    it = session.add_iteration("gpk_mri", copy_from="gpk",  
                               model_generic="../../../../../generic models/GPK_v4/GPK_v4_016_mri.osim",  
                               label="Scaled (GPK, MRI)")

The ``copy_from`` block (generic model, scaling flags, emg_map, colour...)  
is copied under ``name`` and ``overrides`` are applied on top. Only the  
configuration is copied -- no models, no results; run the steps you  
want (``it.scale_model()``, ``it.run(...)``) on the new iteration.

Two things are changed unless you override them, because a straight  
copy would be wrong: a ``model_scaled`` file name containing  
``copy_from`` (``gpk_scaled.osim``) is renamed (``gpk_mri_scaled.osim``)  
so scaling the copy cannot overwrite the original's model, and  
``label`` becomes ``name`` so the two do not share a legend entry.  
Paths stay valid as they are: they are relative to the iteration  
folder, and the new one sits beside the old one.

The block is inserted after ``copy_from``'s; the rest of session.yaml,  
comments included, is left as it was. The file is only written if it  
re-reads to exactly the intended configuration. Returns the new  
:class:`Iteration` (its folder is created).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/recording.py#L278)</sub>

<a id="sessionmigrate"></a>

### `Session.migrate`

```python
Session.migrate(dry_run=False, backup=True)
```

| input | type | default |
|---|---|---|
| `dry_run` | – | `False` |
| `backup` | – | `True` |

Rewrite session.yaml to the current schema. Returns the new text.

* ``project_dir:`` added (relative to the session folder) if missing  
* every iteration block rewritten with the current keys:  
  ``model_generic`` / ``model_scaled`` (the old so_model/ceinms_model  
  collapse into one) / ``markerset``, each written RELATIVE TO THE  
  ITERATION FOLDER -- found the old way (search) and written as the  
  path it actually is  
* a session-level ``markerset`` moved into the iterations

Only the iteration blocks are re-serialised (their inline comments go);  
the rest of the file, comments and line endings included, stays.  
``dry_run=True`` prints the diff and writes nothing; ``backup`` keeps  
``session.yaml.bak``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/recording.py#L401)</sub>

<a id="sessionrun"></a>

### `Session.run`

```python
Session.run(iterations=None, do_scale=False, **kw)
```

| input | type | default |
|---|---|---|
| `iterations` | – | `None` |
| `do_scale` | – | `False` |
| `**kw` | – | – |

Run several iterations with the same stage flags. ``iterations``  
defaults to every iteration present on disk. ``do_scale`` builds each  
iteration's scaled models first (delegates to :meth:`Iteration.scale_model`,  
reading ``session.yaml``); the remaining keyword args forward verbatim to  
:meth:`Iteration.run` (``trials``, ``do_exbiomec``, ``do_so``, ``do_ceinms``,  
``replace`` ...)::

    Session(path).run(iterations=["gpk", "gpk_mri"], do_so=True)  
    Session(path).run(do_scale=True, do_so=True)   # scale + analyse

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/recording.py#L488)</sub>

<a id="sessionexport"></a>

### `Session.export`

```python
Session.export(trials=None, export_src=None, replace=False, normalise=True, detect=True)
```

| input | type | default |
|---|---|---|
| `trials` | – | `None` |
| `export_src` | – | `None` |
| `replace` | – | `False` |
| `normalise` | – | `True` |
| `detect` | – | `True` |

Session-level c3d export, done ONCE. The raw markers/GRF/EMG are model-  
INDEPENDENT and shared by every iteration (they live in ``experimental/<trial>/``),  
so exporting per-iteration just repeats identical work. This ingests loose c3d  
-> markers/GRF/EMG -> filters EMG -> runs the session-wide EMG normalise ->  
classifies each trial (``detect``, writing ``movement_detection.yaml`` and  
``.png`` into the trial folder), once.  
Prefer this over per-iteration ``run(export=True)``::

    s = Session(path)  
    s.export(trials=["Deadlift_35kg_01", "Deadlift_35kg_02"], export_src="c3dfiles")  
    for name in ("cateli", "gpk"):  
        s.iteration(name).run(trials=[...], do_ceinms=True, calibrate=False)

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/recording.py#L504)</sub>

<a id="sessionscale_model"></a>

### `Session.scale_model`

```python
Session.scale_model(iterations=None, **kw)
```

| input | type | default |
|---|---|---|
| `iterations` | – | `None` |
| `**kw` | – | – |

Convenience: scale EVERY iteration's model (scaling only, no analysis).  
The real implementation lives on :meth:`Iteration.scale_model`; this just  
loops it over ``iterations`` (default: all). For scale + analysis in one  
call, prefer ``run(do_scale=True, ...)``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/recording.py#L556)</sub>

<a id="sessionevents"></a>

### `Session.events`

```python
Session.events(trial)
```

| input | type | default |
|---|---|---|
| `trial` | – | required |

Gait events of one trial as a DataFrame (name, event, n, side, time,  
source, on_plate, at_record_edge)::

    sess.events("Walking_01")  
    sess.events("Walking_01").set_index("name").time["foot_contact_1_r"]

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/recording.py#L566)</sub>

<a id="sessionresults"></a>

### `Session.results`

```python
Session.results() -> 'Results'
```

**returns** `'Results'`

This session's results -- call it to load, nothing is read before::

    sess.results()                                        # what exists  
    sess.results("so_forces", trial="Gehen_01", iteration="gpkv4", var="*_r")  
    sess.results(["ik", "id"], trial="Gehen*", window="cycle").mean().plot()

See :mod:`bioscout.results`.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/recording.py#L580)</sub>

<a id="sessionsummarise"></a>

### `Session.summarise`

```python
Session.summarise(
    trials=None,
    iterations=None,
    out_dir=None,
    figures=('kinematics', 'moments', 'jcf'),
    leg='r'
)
```

| input | type | default |
|---|---|---|
| `trials` | – | `None` |
| `iterations` | – | `None` |
| `out_dir` | – | `None` |
| `figures` | – | `('kinematics', 'moments', 'jcf')` |
| `leg` | – | `'r'` |

Cross-model comparison figures for this session: overlay EVERY model  
iteration (cateli/gpk/gpk_mri/...) on the same axes, one figure per trial  
TYPE, written FLAT into ``out_dir`` (default ``<project>/results/<subject>/  
<session>``). Reuses each iteration's on-disk kinematics / ID moments /  
JRA (no re-solve). Colours/labels come from ``session.yaml`` iterations;  
SO = solid, CEINMS = dashed.

    Session(path).summarise()

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/recording.py#L591)</sub>

<a id="sessionreset"></a>

### `Session.reset`

```python
Session.reset(
    trials=None,
    iterations=None,
    backup=True,
    dry_run=False,
    trial_keep=None,
    raw_inputs=False,
    verbose=True
)
```

| input | type | default |
|---|---|---|
| `trials` | – | `None` |
| `iterations` | – | `None` |
| `backup` | – | `True` |
| `dry_run` | – | `False` |
| `trial_keep` | – | `None` |
| `raw_inputs` | – | `False` |
| `verbose` | – | `True` |

Strip THIS session's trial folders back to inputs-only.

Walks each model-iteration folder (``<session>/<iteration>/<trial>/``) and,  
as a fallback, any flat trial folders directly under the session; each trial  
is reduced to ``trial_keep`` (``inputs/`` + ``trial_settings.xml`` by default)  
and every generated output — IK/ID/MA/SO/JRA results, ``setup_*.xml``,  
``MuscleAnalysis/``, ``Execution*/``, plots, filtered EMG ... — is deleted.  
Shared session dirs (``experimental/``, ``logs/``) are never touched.

With ``backup`` (default) the whole session folder is first copied to a  
timestamped sibling ``<session>_backup_<YYYYmmdd_HHMMSS>``. Use ``dry_run=True``  
to PREVIEW without deleting (recommended first). ``raw_inputs=True`` also prunes  
each ``inputs/`` down to just the raw c3d. ``trials`` / ``iterations`` (name or  
list) scope the reset. Returns ``{"timestamp","backup","trials_reset","removed"}``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/recording.py#L1028)</sub>

### `find_session_dir`

```python
find_session_dir(session, project_dir=None, subject=None)
```

| input | type | default |
|---|---|---|
| `session` | – | required |
| `project_dir` | – | `None` |
| `subject` | – | `None` |

Locate the athlete/session folder holding session.yaml for ``session``  
(layout: ``simulations/<athlete>/<session>/session.yaml``).

``subject`` scopes the search to one participant, and you almost always want  
it: a session NAME like "pre" is not unique — every participant in the study  
has one. Without a subject this used to glob ``*/pre/session.yaml`` and  
return ``sorted(hits)[0]``, i.e. the lowest participant id that happens to  
have a folder by that name. Asking for subject 022's "pre" therefore solved  
009's data, under 022's name, silently. An ambiguous name with no subject is  
now an error rather than a coin toss.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/recording.py#L1128)</sub>
