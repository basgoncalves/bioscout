# `bioscout.lab.load_tracking.sample_data`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/sample_data.py)

Synthetic sample-data generator for the load-tracking module.

Generates a few weeks of realistic-looking TCX workout files (HR trace, GPS-free  
is fine for load) plus a strength-session manifest CSV — useful for trying the  
module without a real Zepp/Amazfit export.

    python -m bioscout.lab.load_tracking.sample_data  out_dir/

## Contents

- [`generate`](#generate) — 

### `generate`

```python
generate(out_dir: str, weeks: int = 4, seed: int = 7) -> str
```

| input | type | default |
|---|---|---|
| `out_dir` | str | required |
| `weeks` | int | `4` |
| `seed` | int | `7` |

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/sample_data.py#L51)</sub>
