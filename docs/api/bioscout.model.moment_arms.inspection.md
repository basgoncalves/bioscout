# `bioscout.model.moment_arms.inspection`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/inspection.py)

Check a moment-arm edit the moment it is made.

Growing a wrap surface or shifting a path point is exactly the operation that  
puts a muscle path through a bone, so verification is part of producing the  
model rather than a separate chore you might remember to do. This runs at the  
end of every ``bioscout --change-moment-arms`` run and produces three things:

1. **A before/after overlay** per coordinate — the original curve and the  
   modified one on the same axes, per muscle, with the achieved change in the  
   subplot title. This is the plot the whole exercise is *about*: it shows  
   whether the curve moved as a shape-preserving shift or got bent out of  
   recognition.  
2. **A CSV** of baseline vs modified mean and peak moment arm, so the change  
   can go into a manuscript table without re-deriving it by eye.  
3. **The standard ``muscle_inspect`` pass** on the modified model, which sweeps  
   every default coordinate (not just the edited one — an edit about hip  
   adduction also moves the same muscle's hip flexion moment arm), flags  
   discontinuities, and writes the wrap-corrected ``*_modWO.osim`` alongside.

Only step 3 needs the rest of bioscout; steps 1-2 need opensim and matplotlib.  
Every step degrades to a reported ``reason`` rather than an exception, because  
a failed check must not invalidate a good model.

## Contents

- [`compare_sweeps`](#compare_sweeps) — Sweep both models and pair the curves up per coordinate and muscle.
- [`plot_comparison`](#plot_comparison) — One figure per coordinate: baseline vs modified, per changed muscle.
- [`write_summary_csv`](#write_summary_csv) — Baseline vs modified mean and peak per muscle — a table you can cite.
- [`inspect_change`](#inspect_change) — Verify and document a moment-arm edit. Never raises.

### `compare_sweeps`

```python
compare_sweeps(
    before_model,
    after_model,
    coordinates,
    muscles: Optional[List[str]] = None,
    n: int = 40
) -> Dict
```

| input | type | default |
|---|---|---|
| `before_model` | – | required |
| `after_model` | – | required |
| `coordinates` | – | required |
| `muscles` | Optional[List[str]] | `None` |
| `n` | int | `40` |

**returns** `Dict`

Sweep both models and pair the curves up per coordinate and muscle.

Returns ``{coordinate: {"deg": array, "muscles": {name: (before, after)}}}``  
with moment arms in **mm**. Only muscles present in both sweeps appear; a  
muscle that stopped spanning the coordinate after the edit is a red flag  
and is listed separately by :func:`inspect_change`.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/inspection.py#L40)</sub>

### `plot_comparison`

```python
plot_comparison(comparison, out_dir, title_prefix='') -> List[str]
```

| input | type | default |
|---|---|---|
| `comparison` | – | required |
| `out_dir` | – | required |
| `title_prefix` | – | `''` |

**returns** `List[str]`

One figure per coordinate: baseline vs modified, per changed muscle.

Grey is the model you started from, colour is the model you just wrote, so  
a glance answers the question that matters — did the curve translate, or  
did it change shape?

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/inspection.py#L84)</sub>

### `write_summary_csv`

```python
write_summary_csv(comparison, path) -> str
```

| input | type | default |
|---|---|---|
| `comparison` | – | required |
| `path` | – | required |

**returns** `str`

Baseline vs modified mean and peak per muscle — a table you can cite.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/inspection.py#L135)</sub>

### `inspect_change`

```python
inspect_change(
    before_model,
    after_model,
    coordinates,
    n: int = 40,
    full: bool = True,
    plots: bool = True,
    log=print
) -> dict
```

| input | type | default |
|---|---|---|
| `before_model` | – | required |
| `after_model` | – | required |
| `coordinates` | – | required |
| `n` | int | `40` |
| `full` | bool | `True` |
| `plots` | bool | `True` |
| `log` | – | `print` |

**returns** `dict`

Verify and document a moment-arm edit. Never raises.

``full`` also runs the standard ``muscle_inspect`` pass on the modified  
model. That is the slower half (it sweeps every default coordinate, not  
just the ones edited) and the more thorough one: an edit made about hip  
adduction also moves that muscle's hip flexion and knee moment arms, and  
those are where an unnoticed discontinuity would sit.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/inspection.py#L160)</sub>
