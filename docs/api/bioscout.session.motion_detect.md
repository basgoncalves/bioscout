# `bioscout.session.motion_detect`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/motion_detect.py)

Find the time range of the actual movement in a capture.

A 15-second capture of a deadlift contains a walk-up, a setup, the lift, and a  
re-rack. Everything downstream — IK, ID, SO, CEINMS — crops to  
``session.yaml``'s ``time_range``, so a trial with no range is analysed across  
the whole recording, walk-up included.

**How the window is defined.** The barbell markers (``BL``/``BR``) give the  
cleanest signal for a barbell lift, so the reference is bar height and the rule  
is: *the movement is the span where the bar has left its resting height by more  
than 5% of its total travel in this trial.*

That rule was not chosen for elegance — it was fitted to the windows already in  
Athlete_06's ``session.yaml``, which were set by hand:

    trial            hand-set            detected       error (start / end)  
    Squat_70_01      2.615 - 5.755      2.57 - 5.75     0.045 / 0.005  
    Squat_75_01      3.180 - 6.715      3.07 - 6.70     0.110 / 0.015  
    Squat_80_01      2.170 - 5.725      2.06 - 5.71     0.110 / 0.015  
    Squat_85_01      2.555 - 6.335      2.50 - 6.32     0.055 / 0.015  
    Squat_90_01      3.105 - 6.855      2.90 - 6.85     0.205 / 0.005

Ends agree to within 15 ms; starts land 0.05-0.2 s early, i.e. slightly  
generous, which is the safe direction to err. Detecting a *different*  
convention from the one the existing trials use would be worse than not  
detecting at all, so reproducing it was the acceptance test.

**Direction is inferred, not assumed.** A squat starts at the top and the bar  
goes down; a deadlift starts on the floor and the bar goes up. Rather than  
trusting the trial's ``type`` (which is free text and often absent), the  
resting height is compared against the middle of the range: if the bar rests  
near the top it is a lowering movement, near the bottom a lifting one.

**Fallbacks, in order.** Bar markers -> pelvis/sacrum markers -> vertical GRF  
-> the full capture. The last one is not a failure mode to hide: returning the  
whole recording is exactly what an absent ``time_range`` already means, so the  
worst case changes nothing and is reported as ``method="full"``.

## Contents

- class [`TimeRange`](#timerange) — A detected window, and enough provenance to argue about it later.
  - [`TimeRange.duration`](#timerangeduration) — 
  - [`TimeRange.detected`](#timerangedetected) — False when this is the whole capture, i.e. nothing was found.
  - [`TimeRange.as_list`](#timerangeas_list) — ``[start, end]`` rounded to milliseconds, for session.yaml.
- [`read_trc`](#read_trc) — Read a .trc into ``(time, {marker: (n, 3) array})``.
- [`detect_time_range`](#detect_time_range) — Detect the movement window for one exported trial folder.
- [`detect_session`](#detect_session) — Detect (and optionally write) ``time_range`` for a session's trials.

<a id="timerange"></a>

## class `TimeRange`

A detected window, and enough provenance to argue about it later.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/motion_detect.py#L70)</sub>

<a id="timerangeduration"></a>

### `TimeRange.duration`

```python
TimeRange.duration() -> float
```

**returns** `float`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/motion_detect.py#L81)</sub>

<a id="timerangedetected"></a>

### `TimeRange.detected`

```python
TimeRange.detected() -> bool
```

**returns** `bool`

False when this is the whole capture, i.e. nothing was found.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/motion_detect.py#L85)</sub>

<a id="timerangeas_list"></a>

### `TimeRange.as_list`

```python
TimeRange.as_list() -> List[float]
```

**returns** `List[float]`

``[start, end]`` rounded to milliseconds, for session.yaml.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/motion_detect.py#L89)</sub>

### `read_trc`

```python
read_trc(path) -> Tuple[np.ndarray, Dict[str, np.ndarray]]
```

| input | type | default |
|---|---|---|
| `path` | – | required |

**returns** `Tuple[np.ndarray, Dict[str, np.ndarray]]`

Read a .trc into ``(time, {marker: (n, 3) array})``.

Tolerant of the blank columns OpenSim writes between marker triplets and of  
gaps written as empty fields, which become NaN rather than raising.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/motion_detect.py#L95)</sub>

### `detect_time_range`

```python
detect_time_range(
    trial_dir,
    threshold: float = DEFAULT_THRESHOLD,
    min_duration: float = MIN_DURATION
) -> TimeRange
```

| input | type | default |
|---|---|---|
| `trial_dir` | – | required |
| `threshold` | float | `DEFAULT_THRESHOLD` |
| `min_duration` | float | `MIN_DURATION` |

**returns** `TimeRange`

Detect the movement window for one exported trial folder.

``trial_dir`` is the shared export (``2_experimental/<trial>/``), which is  
where the markers and GRF live. Never raises: an undetectable trial returns  
the full capture with ``method="full"``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/motion_detect.py#L175)</sub>

### `detect_session`

```python
detect_session(
    session_dir,
    only_missing: bool = True,
    apply: bool = False,
    threshold: float = DEFAULT_THRESHOLD,
    log=print
) -> dict
```

| input | type | default |
|---|---|---|
| `session_dir` | – | required |
| `only_missing` | bool | `True` |
| `apply` | bool | `False` |
| `threshold` | float | `DEFAULT_THRESHOLD` |
| `log` | – | `print` |

**returns** `dict`

Detect (and optionally write) ``time_range`` for a session's trials.

``only_missing=True`` leaves existing ranges alone — hand-set windows are  
the reference this detector was fitted against, so overwriting them by  
default would destroy the thing that makes it checkable.

``apply=False`` reports and writes nothing. Run it once to read the table,  
then again with ``apply=True``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/motion_detect.py#L254)</sub>
