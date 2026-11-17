# `bioscout.simulate.gapfill`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/gapfill.py)

Marker gap filling for .trc files — spline for short gaps, rigid-cluster  
(pattern) fill for long ones.

  
**Why this exists**

OpenSim's IK does not fail on a missing marker; it solves without it. Lose the  
sacral cluster for a third of a running trial and the pelvis becomes  
under-determined, so the solver puts it wherever the remaining markers allow —  
90 degrees of heading error, a metre of drift — and reports a plausible marker  
RMS while doing it, because the markers it cannot see cost nothing. The  
kinematics are then double-differentiated into inverse dynamics, and the  
residuals come out in the thousands of newtons. Nothing downstream is  
interpretable, and nothing upstream said so.

Linear interpolation across a 0.5 s gap does not help: it draws a straight line  
through a swinging limb and plants the marker off the body. What does work is  
what a motion-capture technician does by hand — reconstruct the missing marker  
from OTHER markers on the same rigid segment. Three or more markers on one  
segment define its pose; the missing one has a fixed position in that segment's  
frame, so it can be recovered exactly as long as the donors are visible.

  
**What it does**

``fill_trc`` walks every marker, finds its gaps, and fills each one by:

* **spline** — gaps up to ``max_spline_gap`` frames (default 10 ≈ 50 ms at  
  200 Hz), where the trajectory is smooth and interpolation is honest;  
* **rigid** — longer gaps, from a donor cluster chosen FROM THE DATA: the  
  markers whose distance to the target varies least over the frames where both  
  are visible. No hard-coded segment table, so it works for any markerset. The  
  transform is a Kabsch fit (rotation + translation, no scale) taken from the  
  nearest complete frame on each side of the gap and blended across it, so the  
  fill meets the real trajectory at both edges instead of stepping.

A gap is left EMPTY when it cannot be filled honestly — fewer than  
``min_donors`` sufficiently rigid donors, or no donor visible in the gap. An  
empty marker is one OpenSim ignores; a wrong one it believes. Leading and  
trailing gaps outside the marker's own span are never filled at all.

Everything is reported: which marker, how many frames, by which method, with  
which donors, and — for rigid fills — a leave-one-out RMS measured on frames  
where the true position IS known, so the fill comes with its own error bar.

Pure numpy. SciPy is used for the cubic spline when present; without it short  
gaps fall back to linear, which over 10 frames is a small difference.

## Contents

- class [`MarkerFill`](#markerfill) — 
- class [`FillReport`](#fillreport) — 
  - [`FillReport.spline_frames`](#fillreportspline_frames) — 
  - [`FillReport.rigid_frames`](#fillreportrigid_frames) — 
  - [`FillReport.left_empty`](#fillreportleft_empty) — 
  - [`FillReport.ok`](#fillreportok) — 
- [`read_trc`](#read_trc) — Read a .trc. Returns ``(header_lines, frames, times, data, names)`` where ``data`` is ``(n_frames, n_markers, 3)`` with NaN for missing.
- [`write_trc`](#write_trc) — Write a .trc, keeping ``header`` verbatim. NaN is written as an empty cell, which is how OpenSim marks a marker as absent.
- [`fill_array`](#fill_array) — Fill gaps in ``data`` ``(n_frames, n_markers, 3)``. Returns ``(filled, FillReport)``. Never alters a sample that was already present, so running it twice is the same as running it once.
- [`usable_window`](#usable_window) — Longest contiguous run of frames in which the markers that matter are actually there. Returns ``(start, stop, n_frames, detail)``.
- [`fill_trc`](#fill_trc) — Fill the gaps in a .trc. Writes in place unless ``out_path`` is given.
- [`format_report`](#format_report) — Human-readable summary. Compact by default: one line of totals, one line naming the LABELLED markers that stayed empty (with frame counts), and unlabelled ``*NN`` trajectories folded into a single count -- a line per marker per trial is what made the log unreadable. ``verbose`` gives the old per-marker listing.

<a id="markerfill"></a>

## class `MarkerFill`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/gapfill.py#L235)</sub>

<a id="fillreport"></a>

## class `FillReport`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/gapfill.py#L246)</sub>

<a id="fillreportspline_frames"></a>

### `FillReport.spline_frames`

```python
FillReport.spline_frames()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/gapfill.py#L254)</sub>

<a id="fillreportrigid_frames"></a>

### `FillReport.rigid_frames`

```python
FillReport.rigid_frames()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/gapfill.py#L258)</sub>

<a id="fillreportleft_empty"></a>

### `FillReport.left_empty`

```python
FillReport.left_empty()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/gapfill.py#L262)</sub>

<a id="fillreportok"></a>

### `FillReport.ok`

```python
FillReport.ok()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/gapfill.py#L266)</sub>

### `read_trc`

```python
read_trc(path)
```

| input | type | default |
|---|---|---|
| `path` | – | required |

Read a .trc. Returns ``(header_lines, frames, times, data, names)`` where  
``data`` is ``(n_frames, n_markers, 3)`` with NaN for missing.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/gapfill.py#L78)</sub>

### `write_trc`

```python
write_trc(path, header, frames, times, data, fmt='%.5f')
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `header` | – | required |
| `frames` | – | required |
| `times` | – | required |
| `data` | – | required |
| `fmt` | – | `'%.5f'` |

Write a .trc, keeping ``header`` verbatim. NaN is written as an empty  
cell, which is how OpenSim marks a marker as absent.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/gapfill.py#L108)</sub>

### `fill_array`

```python
fill_array(
    data,
    names=None,
    max_spline_gap=MAX_SPLINE_GAP,
    min_donors=MIN_DONORS,
    n_donors=N_DONORS,
    max_carry=MAX_CARRY_RMS,
    loo_samples=40
)
```

| input | type | default |
|---|---|---|
| `data` | – | required |
| `names` | – | `None` |
| `max_spline_gap` | – | `MAX_SPLINE_GAP` |
| `min_donors` | – | `MIN_DONORS` |
| `n_donors` | – | `N_DONORS` |
| `max_carry` | – | `MAX_CARRY_RMS` |
| `loo_samples` | – | `40` |

Fill gaps in ``data`` ``(n_frames, n_markers, 3)``. Returns  
``(filled, FillReport)``. Never alters a sample that was already present,  
so running it twice is the same as running it once.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/gapfill.py#L399)</sub>

### `usable_window`

```python
usable_window(data, names=None, required=None, min_count=None, min_frac=0.9)
```

| input | type | default |
|---|---|---|
| `data` | – | required |
| `names` | – | `None` |
| `required` | – | `None` |
| `min_count` | – | `None` |
| `min_frac` | – | `0.9` |

Longest contiguous run of frames in which the markers that matter are  
actually there. Returns ``(start, stop, n_frames, detail)``.

Gap filling has a floor: three visible markers on a segment. Below that the  
segment's pose is not under-determined, it is UNOBSERVED, and no method  
recovers it — the honest move is to solve a shorter window rather than a  
longer one containing frames nothing constrains. This finds that window.

``required`` names the markers to insist on (default: all of them);  
``min_count`` how many must be present (default ``min_frac`` of them).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/gapfill.py#L516)</sub>

### `fill_trc`

```python
fill_trc(
    path,
    out_path=None,
    max_spline_gap=MAX_SPLINE_GAP,
    min_donors=MIN_DONORS,
    n_donors=N_DONORS,
    max_carry=MAX_CARRY_RMS,
    backup=False,
    log=print
)
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `out_path` | – | `None` |
| `max_spline_gap` | – | `MAX_SPLINE_GAP` |
| `min_donors` | – | `MIN_DONORS` |
| `n_donors` | – | `N_DONORS` |
| `max_carry` | – | `MAX_CARRY_RMS` |
| `backup` | – | `False` |
| `log` | – | `print` |

Fill the gaps in a .trc. Writes in place unless ``out_path`` is given.

Returns the :class:`FillReport`. The header is preserved verbatim and no  
sample that was already present is changed, so re-running is a no-op.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/gapfill.py#L557)</sub>

### `format_report`

```python
format_report(rep: FillReport, verbose=False) -> str
```

| input | type | default |
|---|---|---|
| `rep` | FillReport | required |
| `verbose` | – | `False` |

**returns** `str`

Human-readable summary. Compact by default: one line of totals, one  
line naming the LABELLED markers that stayed empty (with frame counts),  
and unlabelled ``*NN`` trajectories folded into a single count -- a line  
per marker per trial is what made the log unreadable. ``verbose`` gives  
the old per-marker listing.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/gapfill.py#L583)</sub>
