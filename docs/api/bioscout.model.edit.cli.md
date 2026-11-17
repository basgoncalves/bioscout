# `bioscout.model.edit.cli`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/cli.py)

Command line for model_edit — guided when you have no arguments, flat when you do.

    bioscout --model-edit                    # guided, from the current project  
    python -m bioscout.model.edit list  
    python -m bioscout.model.edit list --long  
    python -m bioscout.model.edit show mvic  
    python -m bioscout.model.edit info    --model X.osim  
    python -m bioscout.model.edit apply   mvic --model X.osim --factor 3.0  
    python -m bioscout.model.edit recipe  build_gpk.yaml --root . --dry-run

Both front ends are built from the registry, so an op added in ``ops/`` shows up  
in ``list``, gets ``--flags`` in ``apply``, gets prompts in the guided mode, and  
is accepted in a recipe, with no change here.

## Contents

- [`run`](#run) — The guided prompt — `bioscout --model-edit`.
- [`build_parser`](#build_parser) — 
- [`main`](#main) — 

### `run`

```python
run(project_path: Optional[str] = None) -> int
```

| input | type | default |
|---|---|---|
| `project_path` | Optional[str] | `None` |

**returns** `int`

The guided prompt — `bioscout --model-edit`.

Same shape as the TPS and moment-arm prompts: discovered defaults in  
brackets, Enter accepts, a summary, and nothing written before you confirm.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/cli.py#L204)</sub>

### `build_parser`

```python
build_parser() -> argparse.ArgumentParser
```

**returns** `argparse.ArgumentParser`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/cli.py#L295)</sub>

### `main`

```python
main(argv: Optional[List[str]] = None) -> int
```

| input | type | default |
|---|---|---|
| `argv` | Optional[List[str]] | `None` |

**returns** `int`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/cli.py#L468)</sub>
