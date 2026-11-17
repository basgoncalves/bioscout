# `bioscout.model.tps.cli`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/cli.py)

Command-line entry point.

Replaces the "run nine notebooks in order" workflow with a single command::

    tps-personalise --config config.yaml  
    tps-personalise --bioscout PROJECT_ROOT --player 012 --trial HAB1

Exits non-zero with a clear message on missing inputs (fail-fast), matching  
BioScout conventions.

## Contents

- [`build_parser`](#build_parser) — 
- [`main`](#main) — 

### `build_parser`

```python
build_parser() -> argparse.ArgumentParser
```

**returns** `argparse.ArgumentParser`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/cli.py#L24)</sub>

### `main`

```python
main(argv: list[str] | None = None) -> int
```

| input | type | default |
|---|---|---|
| `argv` | list[str] \| None | `None` |

**returns** `int`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/cli.py#L41)</sub>
