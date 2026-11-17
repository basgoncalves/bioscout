# `bioscout.results.windows`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/windows.py)

Cut one result file into windows (stance / cycle / whole trial) and  
optionally time-normalise each to ``points`` samples.

## Contents

- class [`Window`](#window) — 
- [`windows_for`](#windows_for) — The windows of one trial. ``stance`` falls back to the cycle, and a trial without cycles in movement_detection/cycles.csv gets one '<trial>_full'.
- [`resample`](#resample) — ``df`` (with 'time') on n points from t0 to t1 -> 'pct' 0..100 + channels. Points outside the data (beyond ``tol``) are NaN, never extrapolated.
- [`cut`](#cut) — One file's DataFrame -> (parts, index_rows). Each part is one window with the ID_COLS in front, then 'pct' (normalised) or 'time', 'time_rel'.

<a id="window"></a>

## class `Window`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/windows.py#L20)</sub>

### `windows_for`

```python
windows_for(
    info: SessionInfo,
    trial: str,
    window: str,
    t_data: Tuple[float, float],
    tasks=None
) -> List[Window]
```

| input | type | default |
|---|---|---|
| `info` | SessionInfo | required |
| `trial` | str | required |
| `window` | str | required |
| `t_data` | Tuple[float, float] | required |
| `tasks` | – | `None` |

**returns** `List[Window]`

The windows of one trial. ``stance`` falls back to the cycle, and a trial  
without cycles in movement_detection/cycles.csv gets one '<trial>_full'.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/windows.py#L36)</sub>

### `resample`

```python
resample(df: pd.DataFrame, t0: float, t1: float, n: int, tol: float) -> pd.DataFrame
```

| input | type | default |
|---|---|---|
| `df` | pd.DataFrame | required |
| `t0` | float | required |
| `t1` | float | required |
| `n` | int | required |
| `tol` | float | required |

**returns** `pd.DataFrame`

``df`` (with 'time') on n points from t0 to t1 -> 'pct' 0..100 + channels.  
Points outside the data (beyond ``tol``) are NaN, never extrapolated.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/windows.py#L64)</sub>

### `cut`

```python
cut(
    df: pd.DataFrame,
    info: SessionInfo,
    iteration: str,
    trial: str,
    window='trial',
    points=101,
    normalise=True,
    tasks=None
)
```

| input | type | default |
|---|---|---|
| `df` | pd.DataFrame | required |
| `info` | SessionInfo | required |
| `iteration` | str | required |
| `trial` | str | required |
| `window` | – | `'trial'` |
| `points` | – | `101` |
| `normalise` | – | `True` |
| `tasks` | – | `None` |

One file's DataFrame -> (parts, index_rows). Each part is one window with  
the ID_COLS in front, then 'pct' (normalised) or 'time', 'time_rel'.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/windows.py#L84)</sub>
