# `bioscout.results.scan`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/scan.py)

Find sessions and their result files. Reads folder names and session.yaml /  
cycles.csv only -- never a result file.

## Contents

- class [`SessionInfo`](#sessioninfo) — 
  - [`SessionInfo.body_weight`](#sessioninfobody_weight) — 
- class [`Source`](#source) — 
- [`split`](#split) — None | 'a,b' | ['a', 'b'] -> list or None.
- [`find_sessions`](#find_sessions) — Every ``simulations/<subject>/<session>`` that looks like a session.
- [`scan`](#scan) — Every result file of ``infos`` whose variable is wanted.

<a id="sessioninfo"></a>

## class `SessionInfo`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/scan.py#L27)</sub>

<a id="sessioninfobody_weight"></a>

### `SessionInfo.body_weight`

```python
SessionInfo.body_weight() -> Optional[float]
```

**returns** `Optional[float]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/scan.py#L37)</sub>

<a id="source"></a>

## class `Source`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/scan.py#L42)</sub>

### `split`

```python
split(arg) -> Optional[List[str]]
```

| input | type | default |
|---|---|---|
| `arg` | – | required |

**returns** `Optional[List[str]]`

None | 'a,b' | ['a', 'b'] -> list or None.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/scan.py#L51)</sub>

### `find_sessions`

```python
find_sessions(project: str, subjects=None, sessions=None) -> List[SessionInfo]
```

| input | type | default |
|---|---|---|
| `project` | str | required |
| `subjects` | – | `None` |
| `sessions` | – | `None` |

**returns** `List[SessionInfo]`

Every ``simulations/<subject>/<session>`` that looks like a session.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/scan.py#L118)</sub>

### `scan`

```python
scan(
    infos: Iterable[SessionInfo],
    iterations=None,
    trials=None,
    variables=None,
    experimental=True,
    verbose=False
) -> List[Source]
```

| input | type | default |
|---|---|---|
| `infos` | Iterable[SessionInfo] | required |
| `iterations` | – | `None` |
| `trials` | – | `None` |
| `variables` | – | `None` |
| `experimental` | – | `True` |
| `verbose` | – | `False` |

**returns** `List[Source]`

Every result file of ``infos`` whose variable is wanted.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/scan.py#L170)</sub>
