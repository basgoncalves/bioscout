# `bioscout.session.windows`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/windows.py)

Per-trial ``time_range`` and ``side`` in session.yaml, from the exported data.

    from bioscout.session import windows as W

    W.set_time_ranges(session_dir)                      # report, write nothing  
    W.set_time_ranges(session_dir, apply=True)          # write the windows  
    W.set_sides(session_dir, apply=True)                # which leg is loaded  
    W.set_trial_keys(yaml_path, {"RunA1": {"side": "r"}})

    bioscout session windows PATH --apply  
    bioscout session sides   PATH --apply

WHY A WINDOW AT ALL. Without ``time_range`` IK is solved over the WHOLE  
capture, of which the participant is in the volume for a second or two; the  
solve then fails on the frames nothing observed and the session produces  
nothing. ``bioscout.session.motion_detect`` finds the window from the movement  
itself (bar or pelvis height, GRF as a fallback), which is what a lift or a  
squat needs. This module is the other preference: for a trial that STRIKES A  
PLATE -- running, cutting, a landing -- the window that matters is the stance  
phase, so the loaded run on the plates is taken first and the movement  
detector is the fallback. Pick with ``source=``.

Every window is then CLIPPED to the span the markers actually support (the  
same test the IK preflight applies) and floored at zero: a window the markers  
do not cover is the failure above, whatever produced it.

THE WRITE IS A TEXT EDIT. ``set_trial_keys`` patches the lines under each  
trial and leaves the rest of session.yaml -- comments, key order, line endings  
-- exactly as it was, and only writes when the edited text re-reads as the  
configuration intended. Re-dumping the file through yaml.safe_dump loses the  
comment block that explains the study, and has silently corrupted a  
hand-written session.yaml before (a block-list ``time_range`` whose key was  
removed and whose ``- 0.03`` items were left behind).

## Contents

- [`set_trial_keys`](#set_trial_keys) — Set ``key: value`` under named trials, editing the TEXT.
- [`grf_window`](#grf_window) — (t0, t1) of the longest run in which ANY plate carries more than ``threshold`` newtons -- the stance phase for a trial that strikes one.
- [`marker_span`](#marker_span) — (t0, t1) of the longest run of frames carrying at least ``min_frac`` of the markers -- the span IK can fit a pose to.
- [`trial_window`](#trial_window) — (window, how) for one exported trial folder, or (None, why).
- [`set_time_ranges`](#set_time_ranges) — Give each exported trial a ``time_range``. Existing windows are kept unless ``force``; nothing is written unless ``apply``. Returns ``{trial: {"window", "source", "note"}}``.
- [`detect_side`](#detect_side) — ('l'|'r'|'both'|None, why) -- which foot is loaded in this trial.
- [`set_sides`](#set_sides) — Write each trial's loaded leg as ``side:`` in session.yaml. Existing values are kept unless ``force``; nothing is written unless ``apply``.

### `set_trial_keys`

```python
set_trial_keys(yaml_path, updates, dry_run=False, log=print)
```

| input | type | default |
|---|---|---|
| `yaml_path` | – | required |
| `updates` | – | required |
| `dry_run` | – | `False` |
| `log` | – | `print` |

Set ``key: value`` under named trials, editing the TEXT.

``updates`` is ``{trial: {key: value}}``; a value of None removes the key.  
Handles both block-style trials (``  RunA1:`` + indented keys) and flow  
style (``  RunA1: {type: running}``), and replaces a block-list value  
(``time_range:`` followed by ``- a`` / ``- b``) whole. Returns the trials  
that were not found. Nothing is written unless the result re-reads as  
exactly the intended configuration.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/windows.py#L72)</sub>

### `grf_window`

```python
grf_window(mot, threshold=DEFAULT_GRF_THRESHOLD, min_duration=DEFAULT_MIN_DURATION)
```

| input | type | default |
|---|---|---|
| `mot` | – | required |
| `threshold` | – | `DEFAULT_GRF_THRESHOLD` |
| `min_duration` | – | `DEFAULT_MIN_DURATION` |

(t0, t1) of the longest run in which ANY plate carries more than  
``threshold`` newtons -- the stance phase for a trial that strikes one.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/windows.py#L197)</sub>

### `marker_span`

```python
marker_span(trc, min_frac=0.9)
```

| input | type | default |
|---|---|---|
| `trc` | – | required |
| `min_frac` | – | `0.9` |

(t0, t1) of the longest run of frames carrying at least ``min_frac`` of  
the markers -- the span IK can fit a pose to.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/windows.py#L215)</sub>

### `trial_window`

```python
trial_window(
    trial_export_dir,
    source='grf',
    pad=DEFAULT_PAD,
    threshold=DEFAULT_GRF_THRESHOLD,
    min_duration=DEFAULT_MIN_DURATION,
    classifier_row=None
)
```

| input | type | default |
|---|---|---|
| `trial_export_dir` | – | required |
| `source` | – | `'grf'` |
| `pad` | – | `DEFAULT_PAD` |
| `threshold` | – | `DEFAULT_GRF_THRESHOLD` |
| `min_duration` | – | `DEFAULT_MIN_DURATION` |
| `classifier_row` | – | `None` |

(window, how) for one exported trial folder, or (None, why).

``source="grf"``   plates first, movement detector second (running, cuts)  
``source="motion"`` movement detector first, plates second (lifts, squats)

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/windows.py#L278)</sub>

### `set_time_ranges`

```python
set_time_ranges(
    session_dir,
    trials=None,
    source='grf',
    pad=DEFAULT_PAD,
    threshold=DEFAULT_GRF_THRESHOLD,
    min_duration=DEFAULT_MIN_DURATION,
    force=False,
    apply=False,
    skip_types=('static',),
    log=print
)
```

| input | type | default |
|---|---|---|
| `session_dir` | – | required |
| `trials` | – | `None` |
| `source` | – | `'grf'` |
| `pad` | – | `DEFAULT_PAD` |
| `threshold` | – | `DEFAULT_GRF_THRESHOLD` |
| `min_duration` | – | `DEFAULT_MIN_DURATION` |
| `force` | – | `False` |
| `apply` | – | `False` |
| `skip_types` | – | `('static',)` |
| `log` | – | `print` |

Give each exported trial a ``time_range``. Existing windows are kept  
unless ``force``; nothing is written unless ``apply``. Returns  
``{trial: {"window", "source", "note"}}``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/windows.py#L318)</sub>

### `detect_side`

```python
detect_side(trial_export_dir, body_mass=None, window=None)
```

| input | type | default |
|---|---|---|
| `trial_export_dir` | – | required |
| `body_mass` | – | `None` |
| `window` | – | `None` |

('l'|'r'|'both'|None, why) -- which foot is loaded in this trial.

``window`` (the trial's ``time_range``) restricts the search to the frames  
that are actually solved. Without it a running capture that also catches  
the NEXT footfall on another plate reads as "both".

Read from the plate-to-foot assignment bioscout worked out at export time  
(GRF.xml, CoP against the foot markers), cross-checked against which plates  
actually carry load: a plate mapped to a foot but never loaded does not  
count. The threshold is 10 % of body weight, floored at 50 N.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/windows.py#L383)</sub>

### `set_sides`

```python
set_sides(session_dir, trials=None, force=False, apply=False, log=print)
```

| input | type | default |
|---|---|---|
| `session_dir` | – | required |
| `trials` | – | `None` |
| `force` | – | `False` |
| `apply` | – | `False` |
| `log` | – | `print` |

Write each trial's loaded leg as ``side:`` in session.yaml. Existing  
values are kept unless ``force``; nothing is written unless ``apply``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/windows.py#L426)</sub>
