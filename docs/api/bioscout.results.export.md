# `bioscout.results.export`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/export.py)

Every time-varying result of a project -> analysis-ready CSVs.

``bioscout project results <PROJECT>`` (or :func:`export_results`) writes::

    <project>/results/README.txt  
                     index.csv                              one row per exported cycle  
                     joint_angles/knee_angle_r.csv          ONE file per channel holding  
                     moment_arms/knee_angle_r/bflh_r.csv    every subject/session/iteration/trial/cycle

Each file: one row per curve -- ``subject, session, iteration, trial, task,  
cycle, side, max, min, mean, pct_000 ... pct_100`` (or long format with  
``normalise=False``). Nothing under ``simulations/`` is modified.

## Contents

- [`list_variables`](#list_variables) — 
- [`export_results`](#export_results) — One CSV per channel holding every subject, session, iteration, trial and cycle (see the module docstring). ``variables`` takes the same names as ``session.results`` (aliases, groups, globs). ``sep=';', decimal=','`` for German-locale Excel.
- [`add_arguments`](#add_arguments) — 
- [`run`](#run) — 

### `list_variables`

```python
list_variables(sources) -> pd.DataFrame
```

| input | type | default |
|---|---|---|
| `sources` | – | required |

**returns** `pd.DataFrame`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/export.py#L32)</sub>

### `export_results`

```python
export_results(
    project: str,
    out_dir: Optional[str] = None,
    subjects=None,
    sessions=None,
    iterations=None,
    trials=None,
    variables=None,
    tasks=None,
    window: str = 'stance',
    points: int = 101,
    normalise: bool = True,
    experimental: bool = True,
    sep: str = ',',
    decimal: str = '.',
    float_format: str = '%.6g',
    jobs: int = 8,
    list_only: bool = False,
    verbose: bool = True
) -> str
```

| input | type | default |
|---|---|---|
| `project` | str | required |
| `out_dir` | Optional[str] | `None` |
| `subjects` | – | `None` |
| `sessions` | – | `None` |
| `iterations` | – | `None` |
| `trials` | – | `None` |
| `variables` | – | `None` |
| `tasks` | – | `None` |
| `window` | str | `'stance'` |
| `points` | int | `101` |
| `normalise` | bool | `True` |
| `experimental` | bool | `True` |
| `sep` | str | `','` |
| `decimal` | str | `'.'` |
| `float_format` | str | `'%.6g'` |
| `jobs` | int | `8` |
| `list_only` | bool | `False` |
| `verbose` | bool | `True` |

**returns** `str`

One CSV per channel holding every subject, session, iteration, trial and  
cycle (see the module docstring). ``variables`` takes the same names as  
``session.results`` (aliases, groups, globs). ``sep=';', decimal=','`` for  
German-locale Excel.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/export.py#L85)</sub>

### `add_arguments`

```python
add_arguments(p)
```

| input | type | default |
|---|---|---|
| `p` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/export.py#L174)</sub>

### `run`

```python
run(ns) -> int
```

| input | type | default |
|---|---|---|
| `ns` | – | required |

**returns** `int`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/export.py#L197)</sub>
