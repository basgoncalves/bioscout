# `bioscout.model.cli`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/cli.py)

Command line for ``bioscout.model``.

python -m bioscout.model --verify                    # cwd  
python -m bioscout.model --verify models "generic models"  
python -m bioscout.model --verify --strict --json geometry.json  
bioscout --model                                     # same, via the main CLI

## Contents

- [`build_parser`](#build_parser) — 
- [`main`](#main) — 
- [`run`](#run) — Entry point used by ``bioscout --model`` with no further flags.

### `build_parser`

```python
build_parser() -> argparse.ArgumentParser
```

**returns** `argparse.ArgumentParser`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/cli.py#L34)</sub>

### `main`

```python
main(argv: Optional[Sequence[str]] = None) -> int
```

| input | type | default |
|---|---|---|
| `argv` | Optional[Sequence[str]] | `None` |

**returns** `int`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/cli.py#L65)</sub>

### `run`

```python
run(project=None) -> int
```

| input | type | default |
|---|---|---|
| `project` | – | `None` |

**returns** `int`

Entry point used by ``bioscout --model`` with no further flags.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/cli.py#L87)</sub>
