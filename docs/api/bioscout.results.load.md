# `bioscout.results.load`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/load.py)

Results files -> DataFrames. The one reader used by ``session.results(...)``,  
:func:`bioscout.results.load` and the CSV export.

## Contents

- [`read_parts`](#read_parts) — Read + cut every source -> (parts, index_rows, errors), in source order.
- [`load_infos`](#load_infos) — A session folder (holds session.yaml) or a project folder -> sessions.
- [`available`](#available) — iteration x trial -> number of files per variable. Reads no result file.
- [`load`](#load) — -> ResultSet when ``file`` names ONE variable, else ResultSets {variable: ResultSet}.

### `read_parts`

```python
read_parts(
    sources: Iterable[Source],
    var=None,
    window='trial',
    points=101,
    normalise=False,
    tasks=None,
    jobs=8
)
```

| input | type | default |
|---|---|---|
| `sources` | Iterable[Source] | required |
| `var` | – | `None` |
| `window` | – | `'trial'` |
| `points` | – | `101` |
| `normalise` | – | `False` |
| `tasks` | – | `None` |
| `jobs` | – | `8` |

Read + cut every source -> (parts, index_rows, errors), in source order.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/load.py#L28)</sub>

### `load_infos`

```python
load_infos(path, subject=None, session=None) -> List[SessionInfo]
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `subject` | – | `None` |
| `session` | – | `None` |

**returns** `List[SessionInfo]`

A session folder (holds session.yaml) or a project folder -> sessions.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/load.py#L57)</sub>

### `available`

```python
available(infos, iteration=None, trial=None, experimental=True) -> pd.DataFrame
```

| input | type | default |
|---|---|---|
| `infos` | – | required |
| `iteration` | – | `None` |
| `trial` | – | `None` |
| `experimental` | – | `True` |

**returns** `pd.DataFrame`

iteration x trial -> number of files per variable. Reads no result file.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/load.py#L65)</sub>

### `load`

```python
load(
    infos,
    file,
    iteration=None,
    trial=None,
    var=None,
    window='trial',
    points=101,
    normalise=None,
    tasks=None,
    experimental=True,
    jobs=8
)
```

| input | type | default |
|---|---|---|
| `infos` | – | required |
| `file` | – | required |
| `iteration` | – | `None` |
| `trial` | – | `None` |
| `var` | – | `None` |
| `window` | – | `'trial'` |
| `points` | – | `101` |
| `normalise` | – | `None` |
| `tasks` | – | `None` |
| `experimental` | – | `True` |
| `jobs` | – | `8` |

-> ResultSet when ``file`` names ONE variable, else ResultSets {variable: ResultSet}.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/load.py#L81)</sub>
