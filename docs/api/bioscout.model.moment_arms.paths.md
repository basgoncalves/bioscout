# `bioscout.model.moment_arms.paths`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/paths.py)

Translate a muscle's path points — the fallback for muscles without a wrap.

Glute medius and minimus in the GPK model have no wrap surface on their paths,  
so there is no radius to grow; the only way to move their line of action is to  
move the attachment points themselves. This is a weaker model of "the muscle got  
bigger" than growing a wrap — it moves the attachment rather than the bulk — so  
prefer ``wraps.py`` wherever a wrap exists, and say which route was used when  
reporting the result.

Pure ``xml.etree``; also shifts along the coordinate axis by rotating points  
about a joint axis, which is the mechanically correct way to move a moment-arm  
curve left/right in ``q``.

## Contents

- [`read_path_points`](#read_path_points) — ``[(point name, body, xyz)]`` for one muscle's fixed path points.
- [`translate_path_points`](#translate_path_points) — Rigidly translate a muscle's path points by ``offset_m`` (metres).
- [`rotate_path_points`](#rotate_path_points) — Rotate path points about a joint axis — shifts the curve along ``q``.

### `read_path_points`

```python
read_path_points(model: str | Path, muscle: str) -> List[Tuple[str, str, np.ndarray]]
```

| input | type | default |
|---|---|---|
| `model` | str \| Path | required |
| `muscle` | str | required |

**returns** `List[Tuple[str, str, np.ndarray]]`

``[(point name, body, xyz)]`` for one muscle's fixed path points.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/paths.py#L52)</sub>

### `translate_path_points`

```python
translate_path_points(
    model: str | Path,
    out_path: str | Path,
    muscle: str,
    offset_m: Sequence[float],
    bodies: Optional[Iterable[str]] = None
) -> Dict[str, tuple]
```

| input | type | default |
|---|---|---|
| `model` | str \| Path | required |
| `out_path` | str \| Path | required |
| `muscle` | str | required |
| `offset_m` | Sequence[float] | required |
| `bodies` | Optional[Iterable[str]] | `None` |

**returns** `Dict[str, tuple]`

Rigidly translate a muscle's path points by ``offset_m`` (metres).

Restrict to ``bodies`` to move only, say, the pelvic attachments.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/paths.py#L88)</sub>

### `rotate_path_points`

```python
rotate_path_points(
    model: str | Path,
    out_path: str | Path,
    muscle: str,
    angle_deg: float,
    axis: str = 'x',
    centre_m: Sequence[float] = (0.0, 0.0, 0.0),
    bodies: Optional[Iterable[str]] = None
) -> Dict[str, tuple]
```

| input | type | default |
|---|---|---|
| `model` | str \| Path | required |
| `out_path` | str \| Path | required |
| `muscle` | str | required |
| `angle_deg` | float | required |
| `axis` | str | `'x'` |
| `centre_m` | Sequence[float] | `(0.0, 0.0, 0.0)` |
| `bodies` | Optional[Iterable[str]] | `None` |

**returns** `Dict[str, tuple]`

Rotate path points about a joint axis — shifts the curve along ``q``.

A moment-arm curve moves left/right in the coordinate when the attachment  
rotates about that coordinate's axis, so this is the correct edit for a  
left/right shift. Note it has no justification from muscle volume: bulk  
changes the height of the curve, not where along the range its peak sits.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/paths.py#L101)</sub>
