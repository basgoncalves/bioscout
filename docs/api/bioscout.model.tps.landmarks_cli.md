# `bioscout.model.tps.landmarks_cli`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/landmarks_cli.py)

``tps-landmarks`` — derive bone landmarks from MRI segmentation masks.

Writes a Slicer-compatible ``.mrk.json`` you can review/adjust in 3D Slicer,  
then pass to ``tps-personalise`` as ``mri_landmarks``.

  
**Examples**

    tps-landmarks --seg-dir mri/segmentation --out mri/results/auto_landmarks.mrk.json  
    tps-landmarks --config config.yaml         # uses segmentation_dir/mri_landmarks

## Contents

- [`build_parser`](#build_parser) — 
- [`main`](#main) — 

### `build_parser`

```python
build_parser() -> argparse.ArgumentParser
```

**returns** `argparse.ArgumentParser`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/landmarks_cli.py#L22)</sub>

### `main`

```python
main(argv: list[str] | None = None) -> int
```

| input | type | default |
|---|---|---|
| `argv` | list[str] \| None | `None` |

**returns** `int`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/landmarks_cli.py#L36)</sub>
