# `bioscout.session.stage`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/stage.py)

Put the captures a session needs into ``1_c3dfiles/``.

    from bioscout.session import stage  
    stage.stage_c3d(session_dir)                     # report, copy nothing  
    stage.stage_c3d(session_dir, apply=True)

    bioscout session stage PATH --apply

bioscout resolves a capture from ``<session>/1_c3dfiles/<trial>.c3d`` and  
NOWHERE else: ``c3d_source:`` in session.yaml is the pointer for this copy,  
not a read path, so a session that was never staged solves nothing and says  
so. ``session ingest`` files a folder of loose captures into a session;  
this is the other direction -- session.yaml already names the trials, and  
these are the files it names, wherever they sit under ``c3d_source``.

What is needed is more than the trials being solved: the STATIC trial (there  
is no .trc to scale from without it), the CEINMS calibration trials, and every  
EMG-normalisation capture -- the session-wide MVC maximum spans all of them,  
so leaving one out changes every excitation in the session.

Hard links, not copies, where the filesystem allows: same disk, instant, and  
the capture is never edited in place.

## Contents

- [`source_index`](#source_index) — ``{trial name: path}`` for every .c3d under ``source``. A name already taken by a shallower file is suffixed ``_NU`` (the convention for the same capture re-exported into a "not used" folder), so the deeper copy is still reachable instead of silently shadowed.
- [`needed_trials`](#needed_trials) — Every trial a session must have staged: the scope, the static trial, the calibration trials and every EMG-normalisation capture.
- [`stage_c3d`](#stage_c3d) — Link/copy the captures this session names into ``1_c3dfiles/``.

### `source_index`

```python
source_index(source, skip_dirs=SKIP_DIRS)
```

| input | type | default |
|---|---|---|
| `source` | – | required |
| `skip_dirs` | – | `SKIP_DIRS` |

``{trial name: path}`` for every .c3d under ``source``. A name already  
taken by a shallower file is suffixed ``_NU`` (the convention for the same  
capture re-exported into a "not used" folder), so the deeper copy is still  
reachable instead of silently shadowed.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/stage.py#L37)</sub>

### `needed_trials`

```python
needed_trials(cfg, trials=None)
```

| input | type | default |
|---|---|---|
| `cfg` | – | required |
| `trials` | – | `None` |

Every trial a session must have staged: the scope, the static trial,  
the calibration trials and every EMG-normalisation capture.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/stage.py#L58)</sub>

### `stage_c3d`

```python
stage_c3d(session_dir, trials=None, source=None, apply=False, log=print)
```

| input | type | default |
|---|---|---|
| `session_dir` | – | required |
| `trials` | – | `None` |
| `source` | – | `None` |
| `apply` | – | `False` |
| `log` | – | `print` |

Link/copy the captures this session names into ``1_c3dfiles/``.

``source`` defaults to session.yaml's ``c3d_source`` (relative to the  
session folder). Returns ``{"staged", "present", "missing"}``; a trial with  
no capture anywhere under the source is named rather than skipped quietly,  
and a missing STATIC trial raises -- nothing in the session can be scaled  
without it.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/stage.py#L72)</sub>
