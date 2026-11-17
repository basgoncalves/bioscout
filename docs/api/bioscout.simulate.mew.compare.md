# `bioscout.simulate.mew.compare`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/compare.py)

Compare mew output against Static Optimisation and CEINMS.

This is DESIGN.md section 10, items 3 and 4, made runnable. Tier 1 should agree  
closely with OpenSim SO -- systematic disagreement there is a geometry or  
parameter bug, not a modelling choice. Tier 2/3 should NOT agree exactly with  
SO (that would mean the EMG changed nothing), but should track CEINMS.

## Contents

- [`compare_arrays`](#compare_arrays) — Core comparison: an (nt, nm) array against a reference DataFrame.
- [`compare_files`](#compare_files) — Compare two force .sto files on a common time base.
- [`compare_forces`](#compare_forces) — Per-muscle R2, RMSE and peak error against a reference force .sto.
- [`summarise`](#summarise) — Readable digest, weighted towards the muscles that carry real force.
- [`aggregate`](#aggregate) — Robust summary of a comparison table.
- [`aggregate_line`](#aggregate_line) — 
- [`plot_comparison`](#plot_comparison) — Grid of force traces: this solve against each reference. Needs matplotlib.

### `compare_arrays`

```python
compare_arrays(
    times,
    muscles,
    new: np.ndarray,
    ref: pd.DataFrame,
    smooth_cutoff=15.0
) -> pd.DataFrame
```

| input | type | default |
|---|---|---|
| `times` | – | required |
| `muscles` | – | required |
| `new` | np.ndarray | required |
| `ref` | pd.DataFrame | required |
| `smooth_cutoff` | – | `15.0` |

**returns** `pd.DataFrame`

Core comparison: an (nt, nm) array against a reference DataFrame.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/compare.py#L36)</sub>

### `compare_files`

```python
compare_files(
    path_new,
    path_ref,
    times,
    label='reference',
    smooth_cutoff=15.0
) -> pd.DataFrame
```

| input | type | default |
|---|---|---|
| `path_new` | – | required |
| `path_ref` | – | required |
| `times` | – | required |
| `label` | – | `'reference'` |
| `smooth_cutoff` | – | `15.0` |

**returns** `pd.DataFrame`

Compare two force .sto files on a common time base.

Used to measure how far the EXISTING references (SO and CEINMS) sit from  
each other. Without that baseline, "mew disagrees with SO by X"  
is a number with nothing to compare it to.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/compare.py#L65)</sub>

### `compare_forces`

```python
compare_forces(
    result: MuscleForceResult,
    reference_path,
    label='reference',
    smooth_cutoff=15.0
) -> pd.DataFrame
```

| input | type | default |
|---|---|---|
| `result` | MuscleForceResult | required |
| `reference_path` | – | required |
| `label` | – | `'reference'` |
| `smooth_cutoff` | – | `15.0` |

**returns** `pd.DataFrame`

Per-muscle R2, RMSE and peak error against a reference force .sto.

Reports R2 twice: raw, and after low-pass filtering BOTH signals identically.

That second column is not cosmetic. OpenSim's Static Optimisation solves  
each frame independently with no temporal coupling, so its force traces  
chatter between adjacent frames; this solver carries a smoothing term  
(``SolverWeights.delta``) and does not. Raw R2 therefore charges this  
solver for SO's frame-to-frame noise. ``r2_smooth`` compares what the two  
methods actually disagree about -- the shape of the force over time --  
rather than which one is noisier.

Sorted by the reference's peak force, so the muscles that carry real load  
appear first rather than the alphabetically lucky ones.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/compare.py#L82)</sub>

### `summarise`

```python
summarise(df: pd.DataFrame, top=15) -> str
```

| input | type | default |
|---|---|---|
| `df` | pd.DataFrame | required |
| `top` | – | `15` |

**returns** `str`

Readable digest, weighted towards the muscles that carry real force.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/compare.py#L106)</sub>

### `aggregate`

```python
aggregate(df: pd.DataFrame, load_fraction=0.05, r2_floor=-1.0) -> dict
```

| input | type | default |
|---|---|---|
| `df` | pd.DataFrame | required |
| `load_fraction` | – | `0.05` |
| `r2_floor` | – | `-1.0` |

**returns** `dict`

Robust summary of a comparison table.

Two guards, both learned the hard way on FAIS 022:

* **Only muscles carrying real load count.** A muscle whose reference peak  
  is under ``load_fraction`` of the largest peak is mostly noise; including  
  it measures agreement about nothing.  
* **R2 is floored.** R2 is unbounded below, so ONE muscle whose reference  
  is nearly constant can return -10000 and swamp a weighted mean -- a  
  force-weighted R2 of -1066 on this trial came from exactly that. Floored  
  at ``r2_floor``, the aggregate says "no better than the mean" instead of  
  reporting a meaningless magnitude. The median is reported alongside  
  because it needs no floor at all.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/compare.py#L121)</sub>

### `aggregate_line`

```python
aggregate_line(df: pd.DataFrame) -> str
```

| input | type | default |
|---|---|---|
| `df` | pd.DataFrame | required |

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/compare.py#L159)</sub>

### `plot_comparison`

```python
plot_comparison(
    result: MuscleForceResult,
    references: Dict[str, str],
    out_png,
    muscles: Optional[List[str]] = None,
    n=9
) -> Optional[str]
```

| input | type | default |
|---|---|---|
| `result` | MuscleForceResult | required |
| `references` | Dict[str, str] | required |
| `out_png` | – | required |
| `muscles` | Optional[List[str]] | `None` |
| `n` | – | `9` |

**returns** `Optional[str]`

Grid of force traces: this solve against each reference. Needs matplotlib.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/compare.py#L171)</sub>
