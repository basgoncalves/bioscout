# `bioscout.simulate.mrs.config`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mrs/config.py)

bioscout.simulate.mrs.config -- the Misc struct for the KU Leuven Muscle Redundancy  
Solver, built in Python and handed to MATLAB as JSON.

One dataclass, one JSON file. Every field maps 1:1 onto a `Misc.<Field>` of  
`solveMuscleRedundancy`, so the MATLAB README is the reference for all of them.  
Fields left as None are simply not written -- MRS then applies its own default.

## Contents

- class [`MRSConfig`](#mrsconfig) — Everything one `solveMuscleRedundancy` call needs.
  - [`MRSConfig.calibrating`](#mrsconfigcalibrating) — True when any muscle parameter is being estimated.
  - [`MRSConfig.misc`](#mrsconfigmisc) — The MATLAB `Misc` struct as a plain dict (None fields dropped).
  - [`MRSConfig.to_json`](#mrsconfigto_json) — Write the config MATLAB reads. Returns the path.
  - [`MRSConfig.as_dict`](#mrsconfigas_dict) — 

<a id="mrsconfig"></a>

## class `MRSConfig`

Everything one `solveMuscleRedundancy` call needs.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mrs/config.py#L60)</sub>

<a id="mrsconfigcalibrating"></a>

### `MRSConfig.calibrating`

```python
MRSConfig.calibrating() -> bool
```

**returns** `bool`

True when any muscle parameter is being estimated.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mrs/config.py#L124)</sub>

<a id="mrsconfigmisc"></a>

### `MRSConfig.misc`

```python
MRSConfig.misc() -> dict
```

**returns** `dict`

The MATLAB `Misc` struct as a plain dict (None fields dropped).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mrs/config.py#L130)</sub>

<a id="mrsconfigto_json"></a>

### `MRSConfig.to_json`

```python
MRSConfig.to_json(path: str) -> str
```

| input | type | default |
|---|---|---|
| `path` | str | required |

**returns** `str`

Write the config MATLAB reads. Returns the path.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mrs/config.py#L140)</sub>

<a id="mrsconfigas_dict"></a>

### `MRSConfig.as_dict`

```python
MRSConfig.as_dict() -> dict
```

**returns** `dict`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mrs/config.py#L157)</sub>
