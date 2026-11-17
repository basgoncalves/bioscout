# `bioscout.simulate.mrs.runner`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mrs/runner.py)

bioscout.simulate.mrs.runner -- call MATLAB, run the solver, export the results.

BioScout owns the inputs and the outputs; MATLAB only runs the KU Leuven code.  
The whole exchange is two files: mrs_config.json in, MRS_Results.mat out.

## Contents

- [`find_matlab`](#find_matlab) — Absolute path to the MATLAB executable, or None.
- [`find_mrs_dir`](#find_mrs_dir) — The MuscleRedundancySolver checkout, or None.
- [`check`](#check) — What is installed. Printed by `bioscout simulate mrs check`.
- [`run`](#run) — Write the config, run MATLAB, export .sto files. Returns {key: path}.

### `find_matlab`

```python
find_matlab(exe: Optional[str] = None) -> Optional[str]
```

| input | type | default |
|---|---|---|
| `exe` | Optional[str] | `None` |

**returns** `Optional[str]`

Absolute path to the MATLAB executable, or None.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mrs/runner.py#L20)</sub>

### `find_mrs_dir`

```python
find_mrs_dir(path: Optional[str] = None) -> Optional[str]
```

| input | type | default |
|---|---|---|
| `path` | Optional[str] | `None` |

**returns** `Optional[str]`

The MuscleRedundancySolver checkout, or None.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mrs/runner.py#L39)</sub>

### `check`

```python
check(
    matlab_exe: Optional[str] = None,
    mrs_dir: Optional[str] = None
) -> Dict[str, Optional[str]]
```

| input | type | default |
|---|---|---|
| `matlab_exe` | Optional[str] | `None` |
| `mrs_dir` | Optional[str] | `None` |

**returns** `Dict[str, Optional[str]]`

What is installed. Printed by `bioscout simulate mrs check`.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mrs/runner.py#L47)</sub>

### `run`

```python
run(cfg: MRSConfig, replace: bool = True, verbose: bool = True) -> Dict[str, str]
```

| input | type | default |
|---|---|---|
| `cfg` | MRSConfig | required |
| `replace` | bool | `True` |
| `verbose` | bool | `True` |

**returns** `Dict[str, str]`

Write the config, run MATLAB, export .sto files. Returns {key: path}.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mrs/runner.py#L54)</sub>
