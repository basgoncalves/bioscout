# `bioscout.plot.jcf_coverage`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_coverage.py)

Where the joint contact forces of one trial land on the bones.

``bioscout plot jcf_coverage TRIAL`` draws ONE sagittal scene of the loaded limb,  
posed at the instant of peak hip force, with each joint's contact force painted  
onto the surface that receives it:

* hip -- the MRI femoral head AND the acetabulum (from the segmentations), so  
  this doubles as the acetabular-coverage figure with load on it;  
* tibiofemoral, patellofemoral and ankle -- the model's own bone meshes.

A surface point is coloured by the PEAK force that passed through it during the  
trial: for every frame, the contact patch is the cone of half-angle  
``spread/2`` around the force direction at the joint centre, and each point  
keeps the largest magnitude it ever saw. One figure per force source (SO, and  
CEINMS when that trial has it), written into the trial's  
``joint_contact_forces/`` folder.

Everything about the trial is discovered from its path: the JRA ``.sto`` files,  
the IK ``.mot``, the iteration's model, ``body_mass`` from ``session.yaml`` and  
``mri_root`` from ``project.yaml`` (default: the ucloud MRI segmentation tree).

Frames: the MRI meshes are put into the model's pelvis frame from the pelvic  
landmarks at ``<project>/mri/<subject>/landmarks.csv`` (ASIS_R, ASIS_L,  
PUBIC_SYMPHYSIS). Without that file the meshes are drawn as-is and the figure  
says so -- the heat SHAPE is still right, its place on the head is not.

## Contents

- [`discover`](#discover) — Everything needed for the figure, from ``simulations/<S>/<sess>/3_iterations/<it>/<trial>``.
- [`jcf_coverage_figure`](#jcf_coverage_figure) — One figure for the whole trial: the posed limb and the GRF of both feet on top, then one row per joint x one column per gait event, each cell the contact surface seen from above. Only the analysed leg's joints are drawn (``sides``); the strip keeps both limbs so the pose reads as a stride.
- [`main`](#main) — 

### `discover`

```python
discover(trial, model=None, mass=None, mri_root=None, side=None) -> dict
```

| input | type | default |
|---|---|---|
| `trial` | – | required |
| `model` | – | `None` |
| `mass` | – | `None` |
| `mri_root` | – | `None` |
| `side` | – | `None` |

**returns** `dict`

Everything needed for the figure, from ``simulations/<S>/<sess>/3_iterations/<it>/<trial>``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_coverage.py#L379)</sub>

### `jcf_coverage_figure`

```python
jcf_coverage_figure(
    info: dict,
    label: str,
    out=None,
    spread_deg=25.0,
    patch_mm=16.0,
    window_ms=30.0,
    n_poses=6,
    events=None,
    sides=None,
    strip_sides=('r', 'l'),
    plane: str = 'sagittal',
    add_polygon: bool = False,
    polygon_top: int = 6
) -> dict
```

| input | type | default |
|---|---|---|
| `info` | dict | required |
| `label` | str | required |
| `out` | – | `None` |
| `spread_deg` | – | `25.0` |
| `patch_mm` | – | `16.0` |
| `window_ms` | – | `30.0` |
| `n_poses` | – | `6` |
| `events` | – | `None` |
| `sides` | – | `None` |
| `strip_sides` | – | `('r', 'l')` |
| `plane` | str | `'sagittal'` |
| `add_polygon` | bool | `False` |
| `polygon_top` | int | `6` |

**returns** `dict`

One figure for the whole trial: the posed limb and the GRF of both feet  
on top, then one row per joint x one column per gait event, each cell the  
contact surface seen from above. Only the analysed leg's joints are drawn  
(``sides``); the strip keeps both limbs so the pose reads as a stride.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_coverage.py#L1016)</sub>

### `main`

```python
main(argv=None) -> int
```

| input | type | default |
|---|---|---|
| `argv` | – | `None` |

**returns** `int`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_coverage.py#L1713)</sub>
