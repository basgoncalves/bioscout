# `bioscout.model.measure`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py)

Measurements from bone meshes (STL) — model-independent building blocks.

Everything here takes plain meshes / arrays and returns numbers, so it can be  
used on raw MRI segmentations or on the meshes behind an ``.osim`` model.  
:class:`bioscout.model.geometry.Measure` wraps these per model.

  
**Acetabular coverage**

1. Fit a sphere to the femoral head (least squares, iterative outlier trim).  
2. Sample directions on the head sphere and decide which are covered. A  
   direction counts as covered when the acetabulum is within ``threshold_mm``  
   of the head surface there (default 2.5 mm), by one of two methods:  
   ``nearest`` (default) measures the distance to the nearest acetabulum  
   vertex -- fast; ``rays`` casts a ray from the head centre and takes the hit  
   distance -- exact, but slow, because trimesh casts rays in pure python  
   unless embree is installed. ``min_f``/``max_f`` (rays only) give the hit  
   window directly instead of deriving it from ``threshold_mm``.  
3. Report covered area on the head sphere (mm^2) and % of the full sphere.  
   With a pelvic frame (landmarks: ASIS_R, ASIS_L, PUBIC_SYMPHYSIS) also:  
   % of the superior hemisphere, anterior/superior/posterior sectors, and  
   lateral/anterior centre-edge angles (LCEA/ACEA).

  
**Torsional geometry (from an ``.osim`` model)**

Neck-shaft angle, femoral anteversion and tibial torsion of the model that is  
actually simulated. Joint centres and the medio-lateral axes come from the  
model's own joint frames (expressed in the femur/tibia body frames); the  
femoral neck axis comes from the femur mesh the model draws, by finding the  
smallest neck cross-section (the isthmus). Any of these can be replaced with  
digitised landmarks. Angles in degrees, distances in mm; positive anteversion  
= neck anterior to the posterior condylar axis, positive tibial torsion =  
external.

CLI::

    bioscout model measure coverage FOLDER [--method nearest|rays] [--threshold MM]  
        [--side r l] [--landmarks CSV] [-o CSV]  
        [--plots DIR | --no-plots]   (per-hip 3D figure + summary dot plot)  
    bioscout model measure coverage --acetabulum A.stl --femoral-head F.stl --side l  
    bioscout model measure jcf-coverage FOLDER --model m.osim --jra jra.sto --ik ik.mot  
        --side r --mass 80        (peak contact force heat map on the head)

    bioscout model measure markups FOLDER_OR_FILES [-o CSV] [--json]  
        (neck-shaft angle + anteversion straight from the MRI landmarks)

    bioscout model measure torsion MODEL.osim [--side r l] [--landmarks CSV]  
        [--json] [-o CSV] [--json-out FILE | --no-json-file]  
        (also writes <model>_torsion_angles.json next to each model)

File loading comes from :mod:`bioscout.model.io`. Heavy deps (numpy, trimesh, scipy) are imported inside functions, so importing  
this module is cheap.

## Contents

- [`fit_sphere`](#fit_sphere) — Algebraic least-squares sphere. Returns ``(centre, radius, rms)``.
- [`fit_head_sphere`](#fit_head_sphere) — Femoral head sphere from a head mesh (or a whole femur + seed points).
- [`pelvic_frame`](#pelvic_frame) — Anterior pelvic plane. Returns ``(origin, R)``; rows of R are anterior (x), superior (y), right (z) in image coordinates.
- [`fibonacci_directions`](#fibonacci_directions) — ~Uniform unit vectors on the sphere.
- [`covered_directions`](#covered_directions) — Bool per direction: is the head sphere covered by ``mesh`` there?
- [`centre_edge_angle`](#centre_edge_angle) — Angle (deg) from superior toward local unit vector ``toward`` at which coverage ends. Negative if the superior direction is itself uncovered.
- [`acetabular_coverage`](#acetabular_coverage) — Coverage of the femoral head by the acetabulum.
- [`neck_shaft_angle`](#neck_shaft_angle) — Femoral neck-shaft angle (deg): neck axis vs shaft axis.
- [`shaft_axis_from_mesh`](#shaft_axis_from_mesh) — Anatomical shaft axis (unit, pointing distally) from the diaphysis.
- [`femoral_anteversion`](#femoral_anteversion) — Femoral anteversion / torsion (deg), positive = anteverted.
- [`tibial_torsion`](#tibial_torsion) — Tibial torsion (deg), positive = external (lateral malleolus posterior).
- [`neck_axis_from_mesh`](#neck_axis_from_mesh) — Femoral neck axis by the minimal cross-section (isthmus) of a femur mesh.
- [`read_slicer_markups`](#read_slicer_markups) — A ``.mrk.json`` fiducial list -> ``{label: xyz}`` (as stored, LPS mm).
- [`markup_femoral_geometry`](#markup_femoral_geometry) — Neck-shaft angle and anteversion from MRI landmarks.
- [`joint_rotation_axis`](#joint_rotation_axis) — The joint's main rotation axis, expressed in body ``other``.
- [`joint_table`](#joint_table) — ``[{"joint", "parent", "child"}]`` -- joints with their two base bodies.
- [`resolve_mesh_path`](#resolve_mesh_path) — ``(Path | None, tier)`` for one ``mesh_file`` value.
- [`body_mesh`](#body_mesh) — Every mesh attached to ``body_name``, merged, in that body's frame (m).
- [`femoral_geometry`](#femoral_geometry) — Neck-shaft angle and anteversion for one femur of an ``.osim`` model.
- [`tibial_geometry`](#tibial_geometry) — Tibial torsion for one leg of an ``.osim`` model.
- [`model_torsion`](#model_torsion) — Neck-shaft angle, anteversion and tibial torsion for one leg.
- [`plot_hip_coverage`](#plot_hip_coverage) — Two 3D views of one hip: acetabulum + head sphere coloured by coverage.
- [`plot_coverage_summary`](#plot_coverage_summary) — Dot plot: coverage % per subject, right vs left.
- [`mri_to_pelvis_rotation`](#mri_to_pelvis_rotation) — Rotation from MRI/scanner coordinates to the model's PELVIS frame.
- [`hip_force_in_pelvis`](#hip_force_in_pelvis) — Hip contact force ON the acetabulum IN the pelvis frame.
- [`jcf_coverage`](#jcf_coverage) — Peak contact force per region of the femoral head, over a task.
- [`plot_jcf_coverage`](#plot_jcf_coverage) — Head sphere heat-mapped by peak contact force, with the covered rim.
- [`find_hip_meshes`](#find_hip_meshes) — Locate acetabulum / femoral head meshes for one side in a Meshlab folder.
- [`Acetabular_Coverage`](#acetabular_coverage) — Backwards-compatible wrapper: returns % coverage of the head sphere.
- [`main`](#main) — 

### `fit_sphere`

```python
fit_sphere(points)
```

| input | type | default |
|---|---|---|
| `points` | – | required |

Algebraic least-squares sphere. Returns ``(centre, radius, rms)``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L86)</sub>

### `fit_head_sphere`

```python
fit_head_sphere(vertices, seed_points=None, n_iter=5, keep_tol=0.08)
```

| input | type | default |
|---|---|---|
| `vertices` | – | required |
| `seed_points` | – | `None` |
| `n_iter` | – | `5` |
| `keep_tol` | – | `0.08` |

Femoral head sphere from a head mesh (or a whole femur + seed points).

``seed_points``: vertices known to lie on the head (e.g. the femur vertices  
nearest the acetabulum). Needed when ``vertices`` is a whole femur.  
Each iteration keeps vertices within ``keep_tol*r`` of the current sphere.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L98)</sub>

### `pelvic_frame`

```python
pelvic_frame(asis_r, asis_l, pubic_symphysis)
```

| input | type | default |
|---|---|---|
| `asis_r` | – | required |
| `asis_l` | – | required |
| `pubic_symphysis` | – | required |

Anterior pelvic plane. Returns ``(origin, R)``; rows of R are  
anterior (x), superior (y), right (z) in image coordinates.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L117)</sub>

### `fibonacci_directions`

```python
fibonacci_directions(n)
```

| input | type | default |
|---|---|---|
| `n` | – | required |

~Uniform unit vectors on the sphere.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L129)</sub>

### `covered_directions`

```python
covered_directions(
    mesh,
    centre,
    directions,
    radius,
    method='nearest',
    threshold_mm=5.0,
    min_f=None,
    max_f=None
)
```

| input | type | default |
|---|---|---|
| `mesh` | – | required |
| `centre` | – | required |
| `directions` | – | required |
| `radius` | – | required |
| `method` | – | `'nearest'` |
| `threshold_mm` | – | `5.0` |
| `min_f` | – | `None` |
| `max_f` | – | `None` |

Bool per direction: is the head sphere covered by ``mesh`` there?

method="nearest" (default, fast): the point on the head sphere is within  
    ``threshold_mm`` of the acetabulum surface.  
method="rays" (exact, slow without embree): a ray from ``centre`` hits the  
    mesh between ``min_f*r`` and ``max_f*r`` -- by default the window  
    implied by ``threshold_mm`` (``r ± threshold_mm``).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L138)</sub>

### `centre_edge_angle`

```python
centre_edge_angle(mesh, centre, radius, R, toward, step=0.5, **kw)
```

| input | type | default |
|---|---|---|
| `mesh` | – | required |
| `centre` | – | required |
| `radius` | – | required |
| `R` | – | required |
| `toward` | – | required |
| `step` | – | `0.5` |
| `**kw` | – | – |

Angle (deg) from superior toward local unit vector ``toward`` at which  
coverage ends. Negative if the superior direction is itself uncovered.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L173)</sub>

### `acetabular_coverage`

```python
acetabular_coverage(
    acetabulum,
    femoral_head,
    side: str = 'r',
    landmarks: Optional[dict] = None,
    whole_femur: bool = False,
    crop_factor: Optional[float] = None,
    n_dirs: int = 20000,
    method: str = 'nearest',
    threshold_mm: float = 5.0,
    min_f: Optional[float] = None,
    max_f: Optional[float] = None,
    return_details: bool = False
) -> dict
```

| input | type | default |
|---|---|---|
| `acetabulum` | – | required |
| `femoral_head` | – | required |
| `side` | str | `'r'` |
| `landmarks` | Optional[dict] | `None` |
| `whole_femur` | bool | `False` |
| `crop_factor` | Optional[float] | `None` |
| `n_dirs` | int | `20000` |
| `method` | str | `'nearest'` |
| `threshold_mm` | float | `5.0` |
| `min_f` | Optional[float] | `None` |
| `max_f` | Optional[float] | `None` |
| `return_details` | bool | `False` |

**returns** `dict`

Coverage of the femoral head by the acetabulum.

acetabulum, femoral_head: path or ``trimesh.Trimesh`` (same coordinates).  
whole_femur: femoral_head is a full femur -> head seeded from the vertices  
    nearest the acetabulum.  
crop_factor: crop the acetabulum mesh to ``crop_factor*r`` around the head  
    (use ~1.5 when passing a whole pelvis).  
landmarks: {"ASIS_R","ASIS_L","PUBIC_SYMPHYSIS"} -> adds frame-based metrics.  
method: "nearest" (fast, default) or "rays" (exact, slow).  
threshold_mm: how close the acetabulum must be to the head surface to count  
    as covered (mm). The head-acetabulum gap (cartilage + segmentation) is  
    typically 3.5-5 mm, so a threshold under ~4 mm finds nothing; the  
    reported ``gap_min_mm`` says what it is for this hip.  
min_f, max_f: rays only -- give the hit window directly, as multiples of r,  
    instead of deriving it from threshold_mm.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L201)</sub>

### `neck_shaft_angle`

```python
neck_shaft_angle(head_centre, neck_centre, knee_centre, shaft_axis=None) -> float
```

| input | type | default |
|---|---|---|
| `head_centre` | – | required |
| `neck_centre` | – | required |
| `knee_centre` | – | required |
| `shaft_axis` | – | `None` |

**returns** `float`

Femoral neck-shaft angle (deg): neck axis vs shaft axis.

``neck_centre`` is the centre of the narrowest neck cross-section, so the  
neck axis is ``neck_centre`` -> ``head_centre``. The shaft axis is  
``shaft_axis`` when given (the anatomical axis of the diaphysis, from  
:func:`shaft_axis_from_mesh` -- it is oriented distally here), otherwise the  
line from the neck centre to ``knee_centre``. Prefer the fitted axis: the  
line through the neck centre swings by degrees with the few millimetres of  
uncertainty in where the isthmus sits.  
Typical adult value ~125 deg; < 120 is coxa vara, > 135 coxa valga. Points  
may be in any consistent frame.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L317)</sub>

### `shaft_axis_from_mesh`

```python
shaft_axis_from_mesh(mesh, proximal, distal, span=(0.3, 0.7))
```

| input | type | default |
|---|---|---|
| `mesh` | – | required |
| `proximal` | – | required |
| `distal` | – | required |
| `span` | – | `(0.3, 0.7)` |

Anatomical shaft axis (unit, pointing distally) from the diaphysis.

Takes the mesh vertices whose position along ``proximal`` -> ``distal``  
falls inside ``span`` (fractions of that length, the straight middle of the  
diaphysis: away from the trochanters and the condyles) and returns the first  
principal axis of that cloud.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L343)</sub>

### `femoral_anteversion`

```python
femoral_anteversion(
    head_centre,
    neck_centre,
    knee_centre,
    condylar_axis,
    side: str = 'r'
) -> float
```

| input | type | default |
|---|---|---|
| `head_centre` | – | required |
| `neck_centre` | – | required |
| `knee_centre` | – | required |
| `condylar_axis` | – | required |
| `side` | str | `'r'` |

**returns** `float`

Femoral anteversion / torsion (deg), positive = anteverted.

Angle in the transverse plane (perpendicular to the shaft axis) between the  
neck axis (``neck_centre`` -> ``head_centre``) and the medial direction of  
the posterior condylar axis. ``condylar_axis``: the femoral medio-lateral  
axis at the knee -- its sign does not matter, it is oriented with  
:func:`_lateral`, which assumes an OpenSim-style frame (+z to the subject's  
right, +y proximal, +x anterior).  
Typical adult value ~10-20 deg; a negative value is retroversion.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L377)</sub>

### `tibial_torsion`

```python
tibial_torsion(knee_centre, ankle_centre, knee_axis, ankle_axis, side: str = 'r') -> float
```

| input | type | default |
|---|---|---|
| `knee_centre` | – | required |
| `ankle_centre` | – | required |
| `knee_axis` | – | required |
| `ankle_axis` | – | required |
| `side` | str | `'r'` |

**returns** `float`

Tibial torsion (deg), positive = external (lateral malleolus posterior).

Angle about the tibial long axis between the proximal medio-lateral axis  
(``knee_axis``, e.g. the tibial plateau / knee flexion axis) and the distal  
one (``ankle_axis``, e.g. the transmalleolar or talocrural axis). Axis signs  
do not matter -- both are oriented laterally with :func:`_lateral`, which  
assumes an OpenSim-style frame (+z to the subject's right).  
Typical adult value ~20-35 deg external.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L400)</sub>

### `neck_axis_from_mesh`

```python
neck_axis_from_mesh(
    mesh,
    head_centre,
    shaft_axis,
    head_radius,
    n_dirs: int = 600,
    t_steps: int = 9,
    t_range=(1.1, 2.6),
    refine: int = 2
)
```

| input | type | default |
|---|---|---|
| `mesh` | – | required |
| `head_centre` | – | required |
| `shaft_axis` | – | required |
| `head_radius` | – | required |
| `n_dirs` | int | `600` |
| `t_steps` | int | `9` |
| `t_range` | – | `(1.1, 2.6)` |
| `refine` | int | `2` |

Femoral neck axis by the minimal cross-section (isthmus) of a femur mesh.

Scans candidate axes through the head centre that make 15-85 deg with the  
proximal shaft direction, and along each one the planes between  
``t_range`` x head radius from the centre; the plane with the smallest neck  
cross-section defines the axis and the neck centre. Planes are kept clear of  
the head itself (``t_range`` starts past the head surface), because a cap cut  
off the head is smaller than any neck section and would win every time.

mesh: ``trimesh.Trimesh`` of the (proximal) femur, same units/frame as  
    ``head_centre``; shaft_axis: proximal -> distal; head_radius: from  
    :func:`fit_head_sphere`.  
Returns ``(neck_centre, neck_axis, area)`` -- ``neck_axis`` points from the  
neck towards the head, ``area`` is the isthmus area in the mesh's units^2.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L465)</sub>

### `read_slicer_markups`

```python
read_slicer_markups(path) -> dict
```

| input | type | default |
|---|---|---|
| `path` | – | required |

**returns** `dict`

A ``.mrk.json`` fiducial list -> ``{label: xyz}`` (as stored, LPS mm).

Every control point of every markup in the file is returned, so a file with  
the points split across lists still loads.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L543)</sub>

### `markup_femoral_geometry`

```python
markup_femoral_geometry(markups, side: str = 'r') -> dict
```

| input | type | default |
|---|---|---|
| `markups` | – | required |
| `side` | str | `'r'` |

**returns** `dict`

Neck-shaft angle and anteversion from MRI landmarks.

markups: a ``.mrk.json`` path or a ``{label: xyz}`` dict, in Slicer's LPS  
millimetres, carrying :data:`MARKUP_LABELS`:

====  =========================================================  
HJC   femoral head centre (the hip joint centre)  
GT    greater trochanter -- the lateral end of the neck axis  
PS    proximal shaft point  
LC    lateral femoral condyle  
MC    medial femoral condyle  
DS    distal shaft point  
====  =========================================================

The neck axis is ``GT`` -> ``HJC``, the shaft axis ``PS`` -> ``DS`` and the  
condylar axis ``MC`` -> ``LC``; anteversion is measured in the plane  
perpendicular to the shaft, positive anterior. This reproduces the angles  
the Slicer measurement script writes for these files.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L562)</sub>

### `joint_rotation_axis`

```python
joint_rotation_axis(state, joint, other, pattern=('angle', 'flex'))
```

| input | type | default |
|---|---|---|
| `state` | – | required |
| `joint` | – | required |
| `other` | – | required |
| `pattern` | – | `('angle', 'flex')` |

The joint's main rotation axis, expressed in body ``other``.

For a ``CustomJoint`` this is the rotation ``TransformAxis`` driven by a  
coordinate (preferring one named like a flexion angle) -- NOT the joint  
frame's z. The two differ: a gait2392-style knee rotates about the frame's  
z, while Rajagopal's ``walker_knee`` rotates about its x, so reading z as  
the medio-lateral axis silently turns anteversion into a number ~90 deg  
off. Falls back to the frame's z for joints with no spatial transform  
(a ``PinJoint``, where z IS the axis by definition).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L671)</sub>

### `joint_table`

```python
joint_table(model) -> list
```

| input | type | default |
|---|---|---|
| `model` | – | required |

**returns** `list`

``[{"joint", "parent", "child"}]`` -- joints with their two base bodies.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L703)</sub>

### `resolve_mesh_path`

```python
resolve_mesh_path(raw: str, model_path=None, search: Optional[Sequence] = None)
```

| input | type | default |
|---|---|---|
| `raw` | str | required |
| `model_path` | – | `None` |
| `search` | Optional[Sequence] | `None` |

``(Path | None, tier)`` for one ``mesh_file`` value.

A folder passed in ``search`` wins over every resolver tier: bioscout's  
resolver tries its own bundled Geometry first, so without this a model  
whose bones live elsewhere in the project silently resolves to the generic  
bone. Every caller that reads or rewrites a model's meshes goes through  
here, so measuring and deforming can never pick different files.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L781)</sub>

### `body_mesh`

```python
body_mesh(
    model,
    body_name: str,
    model_path=None,
    state=None,
    tiers: Sequence[str] = MEASURE_TIERS,
    info: Optional[dict] = None,
    search: Optional[Sequence] = None
)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `body_name` | str | required |
| `model_path` | – | `None` |
| `state` | – | `None` |
| `tiers` | Sequence[str] | `MEASURE_TIERS` |
| `info` | Optional[dict] | `None` |
| `search` | Optional[Sequence] | `None` |

Every mesh attached to ``body_name``, merged, in that body's frame (m).

Mesh files are located with :mod:`bioscout.model.geometry`'s resolver, then  
scaled by the model's ``scale_factors`` and moved by the attachment frame's  
offset, so the vertices line up with joint centres from the same model.  
Returns ``None`` when the body has no mesh from an accepted tier.

tiers: which resolver tiers count as "this model's own geometry".  
    The default leaves out ``bundled`` -- a mesh found only in bioscout's  
    generic Geometry folder is not this model's bone, and measuring it  
    quietly gives every model the same shape (see ``MEASURE_TIERS``).  
info: filled in with ``{"files": [...], "tiers": [...], "rejected": [...]}``  
    so a caller can report which mesh the numbers came from.  
search: extra geometry folders to look in (the ``search`` tier), for models  
    whose bones live somewhere else in the project.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L815)</sub>

### `femoral_geometry`

```python
femoral_geometry(
    model,
    side: str = 'r',
    mesh=None,
    model_path=None,
    landmarks: Optional[dict] = None,
    state=None,
    tiers: Sequence[str] = MEASURE_TIERS,
    search: Optional[Sequence] = None,
    **neck_kw
) -> dict
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `side` | str | `'r'` |
| `mesh` | – | `None` |
| `model_path` | – | `None` |
| `landmarks` | Optional[dict] | `None` |
| `state` | – | `None` |
| `tiers` | Sequence[str] | `MEASURE_TIERS` |
| `search` | Optional[Sequence] | `None` |
| `**neck_kw` | – | – |

**returns** `dict`

Neck-shaft angle and anteversion for one femur of an ``.osim`` model.

The hip and knee joint centres come from the model's own joint frames  
(expressed in the femur body frame), the medio-lateral axis from the knee  
joint frame on the femur, and the neck axis from the femur mesh  
(:func:`neck_axis_from_mesh`) -- so the numbers describe the model that is  
actually simulated, scaling and personalisation included.

model: path to an ``.osim`` or a live ``opensim.Model``.  
mesh: femur mesh to use instead of the model's own geometry (femur frame).  
landmarks: optional overrides in the femur frame (metres), any of  
    ``HEAD_CENTRE``, ``NECK_CENTRE``, ``KNEE_CENTRE``, ``CONDYLE_MED``,  
    ``CONDYLE_LAT`` (the two condyles replace the knee-frame axis).  
Extra kwargs go to :func:`neck_axis_from_mesh`.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L885)</sub>

### `tibial_geometry`

```python
tibial_geometry(
    model,
    side: str = 'r',
    landmarks: Optional[dict] = None,
    model_path=None,
    state=None
) -> dict
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `side` | str | `'r'` |
| `landmarks` | Optional[dict] | `None` |
| `model_path` | – | `None` |
| `state` | – | `None` |

**returns** `dict`

Tibial torsion for one leg of an ``.osim`` model.

Proximal axis: the knee joint frame on the tibia; distal axis: the ankle  
joint frame on the tibia (the talocrural axis, the model's stand-in for the  
transmalleolar axis). Both expressed in the tibia body frame.

landmarks: optional overrides in the tibia frame (metres):  
    ``KNEE_CENTRE``, ``ANKLE_CENTRE``, ``MALLEOLUS_MED``, ``MALLEOLUS_LAT``  
    (the two malleoli replace the ankle-frame axis), ``PLATEAU_MED``,  
    ``PLATEAU_LAT`` (replace the knee-frame axis).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L980)</sub>

### `model_torsion`

```python
model_torsion(
    model,
    side: str = 'r',
    mesh=None,
    landmarks: Optional[dict] = None,
    model_path=None,
    state=None,
    tiers: Sequence[str] = MEASURE_TIERS,
    search: Optional[Sequence] = None,
    **neck_kw
) -> dict
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `side` | str | `'r'` |
| `mesh` | – | `None` |
| `landmarks` | Optional[dict] | `None` |
| `model_path` | – | `None` |
| `state` | – | `None` |
| `tiers` | Sequence[str] | `MEASURE_TIERS` |
| `search` | Optional[Sequence] | `None` |
| `**neck_kw` | – | – |

**returns** `dict`

Neck-shaft angle, anteversion and tibial torsion for one leg.

``landmarks`` is passed to both halves; keys that do not apply are ignored.  
Returns one flat dict (an ``error``/``warning`` key is set rather than  
raised when only one half fails).

The model is loaded once here and the same model and state go to both  
halves. Pass the ``opensim.Model`` itself (plus ``model_path`` for the mesh  
lookup, and ``state``) to measure both sides off a single load.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L1019)</sub>

### `plot_hip_coverage`

```python
plot_hip_coverage(res: dict, path, title: str = '') -> Path
```

| input | type | default |
|---|---|---|
| `res` | dict | required |
| `path` | – | required |
| `title` | str | `''` |

**returns** `Path`

Two 3D views of one hip: acetabulum + head sphere coloured by coverage.

``res`` must come from ``acetabular_coverage(..., return_details=True)``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L1057)</sub>

### `plot_coverage_summary`

```python
plot_coverage_summary(rows, path) -> Optional[Path]
```

| input | type | default |
|---|---|---|
| `rows` | – | required |
| `path` | – | required |

**returns** `Optional[Path]`

Dot plot: coverage % per subject, right vs left.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L1102)</sub>

### `mri_to_pelvis_rotation`

```python
mri_to_pelvis_rotation(landmarks) -> 'object'
```

| input | type | default |
|---|---|---|
| `landmarks` | – | required |

**returns** `'object'`

Rotation from MRI/scanner coordinates to the model's PELVIS frame.

OpenSim pelvis frames (Rajagopal, GPK, Catelli) use the ISB convention:  
x anterior, y superior, z right — which is exactly the anterior pelvic  
plane frame :func:`pelvic_frame` builds from ASIS_R, ASIS_L and  
PUBIC_SYMPHYSIS picked on the MRI. So the landmarks ARE the registration:  
no ICP, and no need to read the model's geometry (whose ``.vtp`` files are  
often compressed, and whose pelvis mesh may be far too coarse to register  
against anyway).

Returns R with rows [anterior, superior, right] in MRI coordinates, so  
``R @ v_mri`` is in the pelvis frame and ``R.T @ v_pelvis`` back in MRI.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L1145)</sub>

### `hip_force_in_pelvis`

```python
hip_force_in_pelvis(osim, jra, ik, joint=None, side='r', geometry=None)
```

| input | type | default |
|---|---|---|
| `osim` | – | required |
| `jra` | – | required |
| `ik` | – | required |
| `joint` | – | `None` |
| `side` | – | `'r'` |
| `geometry` | – | `None` |

Hip contact force ON the acetabulum IN the pelvis frame.

Returns ``(F (3, N), joint_name)`` in newtons, reusing the conversion in  
:mod:`bioscout.plot.jcf_direction` (Newton's third law + the hip joint's  
own rotation), so this matches the ``bioscout plot jcf`` figures.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L1169)</sub>

### `jcf_coverage`

```python
jcf_coverage(
    acetabulum,
    femoral_head,
    osim,
    jra,
    ik,
    side='r',
    geometry=None,
    bodyweight=None,
    threshold_mm=5.0,
    method='nearest',
    n_dirs=20000,
    spread_deg=20.0,
    landmarks=None,
    rotation=None,
    frames=None
) -> dict
```

| input | type | default |
|---|---|---|
| `acetabulum` | – | required |
| `femoral_head` | – | required |
| `osim` | – | required |
| `jra` | – | required |
| `ik` | – | required |
| `side` | – | `'r'` |
| `geometry` | – | `None` |
| `bodyweight` | – | `None` |
| `threshold_mm` | – | `5.0` |
| `method` | – | `'nearest'` |
| `n_dirs` | – | `20000` |
| `spread_deg` | – | `20.0` |
| `landmarks` | – | `None` |
| `rotation` | – | `None` |
| `frames` | – | `None` |

**returns** `dict`

Peak contact force per region of the femoral head, over a task.

Geometry from the MRI meshes, load from an OpenSim JointReaction run:  
each time frame's force direction (pelvis frame) is mapped onto the head  
sphere and every surface direction within ``spread_deg/2`` of it takes that  
frame's magnitude. The map is therefore the PEAK force that passed through  
each region during the task (N, or body weights with ``bodyweight``).

Adds the load-side metrics coverage alone cannot give:  
Alignment: MRI meshes are put into the pelvis frame from the pelvic  
landmarks (see :func:`mri_to_pelvis_rotation`); pass ``rotation`` to supply  
one, or neither when the model is MRI-personalised in the same frame.

  peak_force_covered      was the peak load on covered acetabulum?  
  load_bearing_coverage_pct   % of frames whose force points at covered surface  
  rim_margin_deg_min      smallest angle from the load direction to the  
                          nearest UNCOVERED direction (small = edge loading)  
  rim_margin_deg_at_peak  the same at the instant of peak force

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L1200)</sub>

### `plot_jcf_coverage`

```python
plot_jcf_coverage(res: dict, path, title: str = '') -> Path
```

| input | type | default |
|---|---|---|
| `res` | dict | required |
| `path` | – | required |
| `title` | str | `''` |

**returns** `Path`

Head sphere heat-mapped by peak contact force, with the covered rim.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L1296)</sub>

### `find_hip_meshes`

```python
find_hip_meshes(folder, side: str) -> dict
```

| input | type | default |
|---|---|---|
| `folder` | – | required |
| `side` | str | required |

**returns** `dict`

Locate acetabulum / femoral head meshes for one side in a Meshlab folder.

Preference: cropped ``acetabulum_{s}.stl`` + ``femoral_head_{s}.stl``;  
fallback: ``Segmentation*_{s}_pelvis|acetabulum.stl`` +  
``Segmentation*_{s}_femur.stl`` (whole bones, cropped/seeded automatically).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L1354)</sub>

### `Acetabular_Coverage`

```python
Acetabular_Coverage(stl_acetabulum, stl_femoral_head, **kw)
```

| input | type | default |
|---|---|---|
| `stl_acetabulum` | – | required |
| `stl_femoral_head` | – | required |
| `**kw` | – | – |

Backwards-compatible wrapper: returns % coverage of the head sphere.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L1384)</sub>

### `main`

```python
main(argv: Optional[Sequence[str]] = None) -> int
```

| input | type | default |
|---|---|---|
| `argv` | Optional[Sequence[str]] | `None` |

**returns** `int`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/measure.py#L1698)</sub>
