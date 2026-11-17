# `bioscout.simulate.mrs.cli`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mrs/cli.py)

bioscout.simulate.mrs.cli -- `bioscout simulate mrs check` and `bioscout simulate mrs run <trial>`.

## Contents

- [`config_for_trial`](#config_for_trial) — Build an MRSConfig from a BioScout trial folder.
- [`main`](#main) — 

### `config_for_trial`

```python
config_for_trial(
    trial_dir: str,
    dofs: Optional[Sequence[str]] = None,
    muscles: Optional[Sequence[str]] = None,
    time: Optional[Sequence[float]] = None,
    out_dir: Optional[str] = None,
    model: Optional[str] = None,
    ik: Optional[str] = None,
    id_file: Optional[str] = None,
    **kw
) -> MRSConfig
```

| input | type | default |
|---|---|---|
| `trial_dir` | str | required |
| `dofs` | Optional[Sequence[str]] | `None` |
| `muscles` | Optional[Sequence[str]] | `None` |
| `time` | Optional[Sequence[float]] | `None` |
| `out_dir` | Optional[str] | `None` |
| `model` | Optional[str] | `None` |
| `ik` | Optional[str] | `None` |
| `id_file` | Optional[str] | `None` |
| `**kw` | – | – |

**returns** `MRSConfig`

Build an MRSConfig from a BioScout trial folder.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mrs/cli.py#L66)</sub>

### `main`

```python
main(argv: Optional[Sequence[str]] = None) -> int
```

| input | type | default |
|---|---|---|
| `argv` | Optional[Sequence[str]] | `None` |

**returns** `int`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mrs/cli.py#L100)</sub>
