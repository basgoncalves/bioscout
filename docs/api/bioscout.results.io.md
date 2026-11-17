# `bioscout.results.io`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/io.py)

Read an OpenSim / CEINMS storage file.

## Contents

- [`read_storage`](#read_storage) — OpenSim .sto/.mot (or CEINMS .sto) -> DataFrame with a ``time`` column, numeric, sorted, one row per time.

### `read_storage`

```python
read_storage(path: str) -> pd.DataFrame
```

| input | type | default |
|---|---|---|
| `path` | str | required |

**returns** `pd.DataFrame`

OpenSim .sto/.mot (or CEINMS .sto) -> DataFrame with a ``time`` column,  
numeric, sorted, one row per time.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/io.py#L9)</sub>
