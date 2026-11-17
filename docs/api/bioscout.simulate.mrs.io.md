# `bioscout.simulate.mrs.io`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mrs/io.py)

bioscout.simulate.mrs.io -- MRS_Results.mat -> OpenSim .sto + a parameter JSON.

MRS returns one struct per sub-problem (`genericMRS`, `MTE`, `validationMRS`,  
...). Every one of them is exported, so the file name tells you which solve it  
came from: MRS_<problem>_activation.sto, MRS_<problem>_force.sto.

## Contents

- [`write_sto`](#write_sto) — data: (nRows, nCols) aligned with `labels`.
- [`export`](#export) — Export every solved problem in MRS_Results.mat. Returns {key: file}.

### `write_sto`

```python
write_sto(
    path: str,
    time: np.ndarray,
    data: np.ndarray,
    labels: List[str],
    name: str = 'MRS'
) -> str
```

| input | type | default |
|---|---|---|
| `path` | str | required |
| `time` | np.ndarray | required |
| `data` | np.ndarray | required |
| `labels` | List[str] | required |
| `name` | str | `'MRS'` |

**returns** `str`

data: (nRows, nCols) aligned with `labels`.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mrs/io.py#L35)</sub>

### `export`

```python
export(mat_path: str, out_dir: str | None = None) -> Dict[str, str]
```

| input | type | default |
|---|---|---|
| `mat_path` | str | required |
| `out_dir` | str \| None | `None` |

**returns** `Dict[str, str]`

Export every solved problem in MRS_Results.mat. Returns {key: file}.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mrs/io.py#L53)</sub>
