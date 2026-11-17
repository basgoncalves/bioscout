# `bioscout.simulate.mew.io_ports`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/io_ports.py)

File I/O and resampling — the only place that touches disk formats.

Prefers ``bioscout.utils.io`` when bioscout is importable (so headers, column  
handling and quirks stay identical to the rest of the pipeline), and falls back  
to a self-contained OpenSim .sto/.mot parser so the package runs standalone.

## Contents

- [`read_storage`](#read_storage) — Read an OpenSim .sto / .mot into a DataFrame with a ``time`` column.
- [`as_frame`](#as_frame) — Accept a path, a DataFrame or None and return a DataFrame or None.
- [`resample`](#resample) — Linear-interpolate every non-time column onto ``times``.
- [`common_time`](#common_time) — The ``base`` time axis, clipped to the window every frame covers.
- [`derivative`](#derivative) — Central-difference d/dt along axis 0, edge-safe.
- [`write_sto`](#write_sto) — Write an OpenSim .sto with the header CEINMS/bioscout readers expect.

### `read_storage`

```python
read_storage(path) -> pd.DataFrame
```

| input | type | default |
|---|---|---|
| `path` | – | required |

**returns** `pd.DataFrame`

Read an OpenSim .sto / .mot into a DataFrame with a ``time`` column.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/io_ports.py#L30)</sub>

### `as_frame`

```python
as_frame(obj, what='signal') -> Optional[pd.DataFrame]
```

| input | type | default |
|---|---|---|
| `obj` | – | required |
| `what` | – | `'signal'` |

**returns** `Optional[pd.DataFrame]`

Accept a path, a DataFrame or None and return a DataFrame or None.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/io_ports.py#L76)</sub>

### `resample`

```python
resample(df: pd.DataFrame, times: np.ndarray) -> pd.DataFrame
```

| input | type | default |
|---|---|---|
| `df` | pd.DataFrame | required |
| `times` | np.ndarray | required |

**returns** `pd.DataFrame`

Linear-interpolate every non-time column onto ``times``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/io_ports.py#L92)</sub>

### `common_time`

```python
common_time(
    frames: Iterable[pd.DataFrame],
    base: pd.DataFrame,
    time_range: Optional[Sequence[float]] = None
) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `frames` | Iterable[pd.DataFrame] | required |
| `base` | pd.DataFrame | required |
| `time_range` | Optional[Sequence[float]] | `None` |

**returns** `np.ndarray`

The ``base`` time axis, clipped to the window every frame covers.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/io_ports.py#L103)</sub>

### `derivative`

```python
derivative(y: np.ndarray, t: np.ndarray) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `y` | np.ndarray | required |
| `t` | np.ndarray | required |

**returns** `np.ndarray`

Central-difference d/dt along axis 0, edge-safe.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/io_ports.py#L120)</sub>

### `write_sto`

```python
write_sto(path, times, columns: List[str], data: np.ndarray, name='Data')
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `times` | – | required |
| `columns` | List[str] | required |
| `data` | np.ndarray | required |
| `name` | – | `'Data'` |

Write an OpenSim .sto with the header CEINMS/bioscout readers expect.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/io_ports.py#L132)</sub>
