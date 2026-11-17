# `bioscout.model.moment_arms.core`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/core.py)

Wire the solver to real OpenSim moment-arm sweeps.

This is the only module here that needs ``opensim``; everything else is pure  
file/maths so it can be tested without one. Imports are lazy and the failure is  
reported rather than raised, so an environment without OpenSim still gets the  
listing and the volume measurements.

## Contents

- class [`Target`](#target) — One adjustable (muscle, coordinate) pair and how it can be adjusted.
  - [`Target.route`](#targetroute) — 
- [`list_coordinates`](#list_coordinates) — Every coordinate name in the model — pure XML, so no OpenSim needed.
- [`expand_coordinates`](#expand_coordinates) — Parse a user coordinate string into validated names.
- [`list_targets`](#list_targets) — Muscles that genuinely span ``coordinate``, and how each can be changed.
- [`sweep_moment_arm`](#sweep_moment_arm) — Moment-arm curve (metres) for one muscle about one coordinate.
- [`apply_offset`](#apply_offset) — Grow the muscle's wrap surface(s) until its moment arm rises by ``offset_mm``.
- [`check_model`](#check_model) — Re-run the discontinuity check — inflating a wrap is exactly the edit that shoves a path through a bone, so never skip this.
- [`apply_to_muscle`](#apply_to_muscle) — Change one muscle's moment arm, choosing the route automatically.
- [`apply_batch`](#apply_batch) — Apply the same target to many muscles, accumulating into ONE model.

<a id="target"></a>

## class `Target`

One adjustable (muscle, coordinate) pair and how it can be adjusted.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/core.py#L27)</sub>

<a id="targetroute"></a>

### `Target.route`

```python
Target.route() -> str
```

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/core.py#L36)</sub>

### `list_coordinates`

```python
list_coordinates(model: str | Path) -> List[str]
```

| input | type | default |
|---|---|---|
| `model` | str \| Path | required |

**returns** `List[str]`

Every coordinate name in the model — pure XML, so no OpenSim needed.

Used to validate what the user typed before paying for a sweep: an unknown  
name previously surfaced as "no muscle has a moment arm > 1 mm", which  
points at the wrong problem entirely.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/core.py#L40)</sub>

### `expand_coordinates`

```python
expand_coordinates(text: str, model: str | Path) -> tuple
```

| input | type | default |
|---|---|---|
| `text` | str | required |
| `model` | str \| Path | required |

**returns** `tuple`

Parse a user coordinate string into validated names.

Accepts a comma- or space-separated list, and expands a side-less name to  
both sides (``hip_adduction`` -> ``hip_adduction_r``, ``hip_adduction_l``)  
since a bilateral change is the normal case for a gait/lifting study.

Returns ``(valid, unknown)``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/core.py#L58)</sub>

### `list_targets`

```python
list_targets(
    model: str | Path,
    coordinate: str,
    n: int = 12,
    min_ma_mm: float = 1.0
) -> List[Target]
```

| input | type | default |
|---|---|---|
| `model` | str \| Path | required |
| `coordinate` | str | required |
| `n` | int | `12` |
| `min_ma_mm` | float | `1.0` |

**returns** `List[Target]`

Muscles that genuinely span ``coordinate``, and how each can be changed.

``min_ma_mm`` defaults to 1 mm rather than the 0.1 mm used elsewhere: below  
that a "moment arm" is numerical residue from a muscle that does not cross  
the joint at all (gastrocnemius shows ~0.2 mm about the hip), and offering  
it as something to tune is worse than useless.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/core.py#L94)</sub>

### `sweep_moment_arm`

```python
sweep_moment_arm(
    model: str | Path,
    muscle: str,
    coordinate: str,
    n: int = 40
) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `model` | str \| Path | required |
| `muscle` | str | required |
| `coordinate` | str | required |
| `n` | int | `40` |

**returns** `np.ndarray`

Moment-arm curve (metres) for one muscle about one coordinate.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/core.py#L123)</sub>

### `apply_offset`

```python
apply_offset(
    model: str | Path,
    out_path: str | Path,
    muscle: str,
    coordinate: str,
    offset_mm: float,
    wraps: Optional[List[str]] = None,
    n: int = 40,
    tol_mm: float = 0.2,
    max_iter: int = 20
) -> dict
```

| input | type | default |
|---|---|---|
| `model` | str \| Path | required |
| `out_path` | str \| Path | required |
| `muscle` | str | required |
| `coordinate` | str | required |
| `offset_mm` | float | required |
| `wraps` | Optional[List[str]] | `None` |
| `n` | int | `40` |
| `tol_mm` | float | `0.2` |
| `max_iter` | int | `20` |

**returns** `dict`

Grow the muscle's wrap surface(s) until its moment arm rises by ``offset_mm``.

Every trial radius is written to a scratch copy and swept, so the input  
model is never touched until the search succeeds.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/core.py#L132)</sub>

### `check_model`

```python
check_model(
    model: str | Path,
    coordinates: Optional[List[str]] = None,
    n: int = 40
) -> dict
```

| input | type | default |
|---|---|---|
| `model` | str \| Path | required |
| `coordinates` | Optional[List[str]] | `None` |
| `n` | int | `40` |

**returns** `dict`

Re-run the discontinuity check — inflating a wrap is exactly the edit  
that shoves a path through a bone, so never skip this.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/core.py#L176)</sub>

### `apply_to_muscle`

```python
apply_to_muscle(
    model,
    out_path,
    muscle,
    coordinate,
    scale=None,
    offset_mm=None,
    n=25,
    tol_mm=0.2,
    max_iter=18,
    probe_n=7,
    fallback=True,
    partial=True,
    min_fraction=0.25,
    max_shift_mm=25.0
) -> dict
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `out_path` | – | required |
| `muscle` | – | required |
| `coordinate` | – | required |
| `scale` | – | `None` |
| `offset_mm` | – | `None` |
| `n` | – | `25` |
| `tol_mm` | – | `0.2` |
| `max_iter` | – | `18` |
| `probe_n` | – | `7` |
| `fallback` | – | `True` |
| `partial` | – | `True` |
| `min_fraction` | – | `0.25` |
| `max_shift_mm` | – | `25.0` |

**returns** `dict`

Change one muscle's moment arm, choosing the route automatically.

Wrap radius when the muscle has a scalable wrap (the mechanism: the surface  
stands in for muscle bulk); otherwise a rigid translation of its path points  
(weaker — it models the attachment moving, not the bulk). The route is  
always reported so a mixed batch stays interpretable.

Two behaviours keep a whole-model run from collapsing to a handful of  
changed muscles:

``fallback``  
    A wrap that runs out of room at 3x its radius is not the end of the  
    line — the remaining deficit is then chased by translating the path,  
    starting from the already-inflated model. The result records  
    ``route="wrap radius + path translation"`` so the mixed provenance  
    stays visible in the report.

``partial``  
    When even that cannot reach the target, keep the largest change that  
    *was* achievable instead of leaving the muscle untouched. A wrap  
    surface has a hard geometric ceiling, so refusing anything short of the  
    full request turns a +50% run into a +0% run for most of the model.  
    The result carries ``ok=False, applied=True, partial=True`` and the  
    achieved fraction, so a shortfall is reported rather than hidden.  
    ``min_fraction`` is the floor below which a change is too small to be  
    worth keeping.

``max_shift_mm`` caps the translation route: past ~25 mm the edit stops  
being "the attachment sits slightly differently" and becomes a different  
muscle.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/core.py#L263)</sub>

### `apply_batch`

```python
apply_batch(
    model,
    out_path,
    muscles,
    coordinate,
    scale=None,
    offset_mm=None,
    n=25,
    probe_n=7,
    partial=True,
    fallback=True,
    min_fraction=0.25,
    log=print
) -> dict
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `out_path` | – | required |
| `muscles` | – | required |
| `coordinate` | – | required |
| `scale` | – | `None` |
| `offset_mm` | – | `None` |
| `n` | – | `25` |
| `probe_n` | – | `7` |
| `partial` | – | `True` |
| `fallback` | – | `True` |
| `min_fraction` | – | `0.25` |
| `log` | – | `print` |

**returns** `dict`

Apply the same target to many muscles, accumulating into ONE model.

Each muscle is solved against the model produced so far, so the edits  
compose. A muscle that fails is reported and skipped rather than aborting  
the run — on a 100-muscle model a single awkward path should not cost you  
the other 99.

A muscle that only got *part* of the way is kept and reported as PARTIAL:  
the alternative is a run where the request quietly applies to four muscles  
out of seventy, which reads as success and is not.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/core.py#L426)</sub>
