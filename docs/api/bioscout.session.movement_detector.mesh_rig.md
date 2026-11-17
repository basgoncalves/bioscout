# `bioscout.session.movement_detector.mesh_rig`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_rig.py)

mesh_rig — turn a single whole-body surface mesh into a rigged OpenSim model.

``mesh_convert`` gets a scan into STL. This module takes it the rest of the way:  
one closed human-shaped mesh in, a segmented, un-posed, joint-filled STL set  
plus a ready-to-open ``.osim`` out, with the base model's kinematics untouched.

    from bioscout.session.movement_detector import rig_mesh  
    res = rig_mesh("3DModel.obj", out_dir="subject01", name="bas",  
                   config=RigConfig(target_height=1.81))  
    print(res.model_path)        # subject01/bas.osim  
    print(res.landmarks)         # ankle/knee/hip/lumbar/neck heights, metres

Command line::

    python -m bioscout.session.movement_detector.mesh_rig scan.stl -o out --height 1.81

  
**What it does, in order**

1. **Load and weld.** Binary/ASCII STL and Wavefront OBJ. STL stores three  
   loose vertices per triangle, so vertices are welded by position — without  
   that there is no connectivity and no boundary loop to cap.  
2. **Decimate** by vertex clustering (``config.grid``). A 1 M-triangle sculpt  
   drops to a few hundred thousand in about a second; everything downstream is  
   then linear in a much smaller number.  
3. **Orient.** The mesh is rotated into the anatomical frame the model uses  
   (+x anterior, +y up, +z to the subject's right), scaled to  
   ``config.target_height`` and dropped onto y = 0. The medio-lateral axis is  
   the major horizontal principal axis of the trunk band; anterior is the  
   remaining horizontal axis, signed by where the feet point.  
4. **Landmarks.** Ankle, knee and neck are the narrowest girth of the limb  
   inside anthropometric search bands; the hip is found from the crotch — the  
   highest level at which the two legs are still separated by a gap. These  
   reproduce the values that were read off ruler renders by hand in the  
   original per-character build scripts (see ``examples`` in the tests).  
5. **Cut** into the base model's bodies, per triangle centroid.  
6. **Un-pose.** Each segment is rotated so the line between its own two joint  
   centres lands on the body's long axis, then scaled axially to the model's  
   segment length. Hip and ankle centres are *imposed* from the model rather  
   than measured — fitting splayed legs or a foot slab centroid is much less  
   reliable than trusting the skeleton.  
7. **Close.** Every plane cut leaves an open shell, which reads as a hole the  
   moment the joint flexes. Boundary loops are fanned to their centroid, and a  
   filler blob at each joint centre — carried by the *proximal* body, sized  
   from the distal segment's cut — fills the wedge that opens under flexion.  
8. **Write.** One STL per body per region, and a copy of the base ``.osim``  
   whose ``attached_geometry`` is replaced. Joints, coordinates, constraints,  
   forces and markers are copied verbatim, so existing ``.mot``/``.sto`` files  
   and IK/ID/SO setups keep working against the result.

Only numpy is required. Pillow is used, if present, to carry a textured OBJ's  
colours into per-region meshes.

  
**Caveats worth knowing before trusting a result**

* Segments are rigid, so loose clothing shows a seam at the knee and hip.  
* Arms and head ride on ``torso`` unless the base model has arm/skull bodies.  
* Masses and inertias come from the base model and are NOT rescaled to the  
  subject. The output is display geometry on someone else's dynamics: fine for  
  visualisation and IK, not validated for ID/SO without a scaling pass.

## Contents

- class [`RigConfig`](#rigconfig) — Everything tunable about a rig, with defaults that work on a standing scan.
  - [`RigConfig.resolved_grid`](#rigconfigresolved_grid) — Decimation cell, defaulting to 1/700 of the mesh height.
- class [`ModelLandmarks`](#modellandmarks) — Joint geometry read out of the base ``.osim``, in each body's own frame.
- class [`RigResult`](#rigresult) — What :func:`rig_mesh` produced.
- [`load_mesh`](#load_mesh) — Read ``.stl`` (binary or ASCII) or ``.obj`` into ``(V, F)`` numpy arrays.
- [`weld`](#weld) — Merge vertices that share a position, dropping the faces that collapse.
- [`decimate`](#decimate) — Vertex-cluster decimation: one representative vertex per ``grid`` cell.
- [`write_stl_fast`](#write_stl_fast) — Write a binary STL from numpy arrays in one buffer write.
- [`orient_mesh`](#orient_mesh) — Rotate, scale and centre a mesh into the anatomical frame.
- [`body_landmarks`](#body_landmarks) — Find the heights the cuts are made at, in metres above the floor.
- [`read_model_landmarks`](#read_model_landmarks) — Read hip / knee / ankle / MTP geometry out of a base ``.osim``.
- [`cap_open_boundaries`](#cap_open_boundaries) — Close every hole by fanning its loop to the loop's centroid.
- [`write_osim`](#write_osim) — Copy a base model, swapping each body's display geometry for our meshes.
- [`rig_mesh`](#rig_mesh) — Rig a whole-body surface mesh onto an OpenSim skeleton.

<a id="rigconfig"></a>

## class `RigConfig`

Everything tunable about a rig, with defaults that work on a standing scan.

  
**Attributes**

target_height : float  
    Finished stature in metres. A scan is rarely metric; this is what sets  
    the scale, so it is the single most important number to get right.  
grid : float  
    Vertex-clustering cell size for decimation, in *source* units. ``None``  
    or 0 disables decimation. The default is chosen relative to the mesh  
    height at run time if left at ``None``.  
facing_yaw : float or None  
    Anterior direction in degrees about the up axis, measured from +x.  
    ``None`` auto-detects, which is right for any scan whose feet point  
    forwards. Give it explicitly for a lunge or a twisted sculpt, where the  
    line between the legs no longer carries the facing.  
up : str  
    Which source axis is up: ``"y"`` (default, OpenSim and most scanners)  
    or ``"z"`` (CAD exports).  
ankle_h, knee_h, hip_h, lumbar_h, neck_h : float or None  
    Landmark heights as a *fraction of stature*. ``None`` auto-detects.  
    Override one when a garment hides the cue — baggy trousers are the  
    usual reason.  
cap_cuts : bool  
    Fan every open boundary loop to its centroid, making each piece a  
    closed solid. Leave this on for anything animated.  
joint_fillers : bool  
    Add a blob at each joint centre, on the proximal body, so the joint  
    stays covered under flexion.  
filler_scale : float  
    Filler radius as a multiple of the distal segment's own cut radius.  
smooth : int  
    Taubin smoothing passes applied after decimation. Takes scanner noise  
    off without the shrinkage a plain Laplacian causes. 0 disables.  
fit_legs : bool  
    Ignore ``target_height`` and scale the mesh so its **hip height**  
    matches the base model's instead. Use it whenever the figure's  
    proportions differ from the skeleton's — a child, a stylised character,  
    anyone long or short in the leg. Scaling by stature onto a mismatched  
    skeleton stretches the limbs to the model's segment lengths and leaves  
    a figure with a small torso on stilts. The finished height is then  
    whatever the model implies, and the OpenSim Scale Tool is the right  
    place to bring the model (and its geometry with it) back down.  
keep_bones : bool  
    Also write an x-ray model that keeps the base model's bone geometry  
    under a translucent skin. Handy for checking the fit.  
skin_colour : str  
    OpenSim ``<color>`` triple used for untextured meshes.  
opacity : float  
    Skin opacity in the main model.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_rig.py#L101)</sub>

<a id="rigconfigresolved_grid"></a>

### `RigConfig.resolved_grid`

```python
RigConfig.resolved_grid(height: float) -> float
```

| input | type | default |
|---|---|---|
| `height` | float | required |

**returns** `float`

Decimation cell, defaulting to 1/700 of the mesh height.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_rig.py#L181)</sub>

<a id="modellandmarks"></a>

## class `ModelLandmarks`

Joint geometry read out of the base ``.osim``, in each body's own frame.

All lengths are metres. ``hip`` is the right hip in the pelvis frame;  
the left is its mirror in z.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_rig.py#L189)</sub>

<a id="rigresult"></a>

## class `RigResult`

What :func:`rig_mesh` produced.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_rig.py#L212)</sub>

### `load_mesh`

```python
load_mesh(path: str | Path) -> Tuple[Array, Array]
```

| input | type | default |
|---|---|---|
| `path` | str \| Path | required |

**returns** `Tuple[Array, Array]`

Read ``.stl`` (binary or ASCII) or ``.obj`` into ``(V, F)`` numpy arrays.

``V`` is ``(n, 3)`` float64 vertices, ``F`` is ``(m, 3)`` int64 triangle  
indices. STL vertices come back unwelded — call :func:`weld` before doing  
anything that needs connectivity.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_rig.py#L268)</sub>

### `weld`

```python
weld(V: Array, F: Array, tol: float | None = None) -> Tuple[Array, Array]
```

| input | type | default |
|---|---|---|
| `V` | Array | required |
| `F` | Array | required |
| `tol` | float \| None | `None` |

**returns** `Tuple[Array, Array]`

Merge vertices that share a position, dropping the faces that collapse.

STL has no vertex sharing at all, so every mesh read from one is a pile of  
loose triangles: no edge is shared, no boundary loop can be found, and  
smoothing does nothing. ``tol`` defaults to 1e-6 of the bounding box, which  
is well below any real feature and well above float32 STL round-off.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_rig.py#L294)</sub>

### `decimate`

```python
decimate(V: Array, F: Array, grid: float) -> Tuple[Array, Array]
```

| input | type | default |
|---|---|---|
| `V` | Array | required |
| `F` | Array | required |
| `grid` | float | required |

**returns** `Tuple[Array, Array]`

Vertex-cluster decimation: one representative vertex per ``grid`` cell.

Crude next to quadric edge collapse, but it is O(n), needs no neighbour  
structure, and preserves the silhouette — which is all the downstream cuts  
and girth profiles care about. A 1 M-triangle sculpt takes about a second.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_rig.py#L312)</sub>

### `write_stl_fast`

```python
write_stl_fast(V: Array, F: Array, path: str | Path, name: str = 'bioscout') -> Path
```

| input | type | default |
|---|---|---|
| `V` | Array | required |
| `F` | Array | required |
| `path` | str \| Path | required |
| `name` | str | `'bioscout'` |

**returns** `Path`

Write a binary STL from numpy arrays in one buffer write.

Facet normals are recomputed from the winding, so a piece whose stored  
normals disagreed with its triangles comes out self-consistent.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_rig.py#L359)</sub>

### `orient_mesh`

```python
orient_mesh(V: Array, cfg: RigConfig) -> Tuple[Array, Dict[str, float]]
```

| input | type | default |
|---|---|---|
| `V` | Array | required |
| `cfg` | RigConfig | required |

**returns** `Tuple[Array, Dict[str, float]]`

Rotate, scale and centre a mesh into the anatomical frame.

Output convention matches OpenSim: **+x anterior, +y up, +z to the  
subject's right**, ground at ``y = 0``, the midsagittal plane at ``z = 0``  
and the trunk centred at ``x = 0``. Stature becomes  
``cfg.target_height``.

Returns the transformed vertices and a dict recording what was applied  
(``scale``, ``yaw_deg``, ``height_in``), which is what you check first when  
a result comes out mirrored or lying down.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_rig.py#L464)</sub>

### `body_landmarks`

```python
body_landmarks(
    V: Array,
    cfg: RigConfig,
    ml: ModelLandmarks | None = None
) -> Dict[str, float]
```

| input | type | default |
|---|---|---|
| `V` | Array | required |
| `cfg` | RigConfig | required |
| `ml` | ModelLandmarks \| None | `None` |

**returns** `Dict[str, float]`

Find the heights the cuts are made at, in metres above the floor.

Everything the caller pinned in ``cfg`` is honoured as-is (as a fraction of  
stature); the rest is measured.

``hip`` is the anchor, and the only leg landmark measured outright: it is  
the crotch — the highest level at which the two legs are still separate —  
plus 2 % of stature. A hip joint centre cannot be seen on a surface (the  
greater trochanter is buried under muscle), but the crotch is sharp,  
unambiguous, and a fixed distance below the joint across adults.

``knee`` and ``ankle`` then **split the measured hip height in the base  
model's own proportions** — femur : tibia : ankle-height. Girth minima are  
the obvious alternative and were tried first: they do not survive contact  
with real scans. Trousers, socks and a calf that tapers smoothly into the  
ankle leave a profile that falls monotonically with no interior minimum at  
all, and a search that takes the band edge anyway returns a confident  
number that is 6 cm wrong. A girth minimum is used only when there is a  
real interior one on *both* legs and it agrees with the proportional  
estimate to within 12 % of stature — that is, only when it confirms.

``lumbar`` is fixed at 0.63 stature (roughly L5-S1). ``neck`` is the  
narrowest girth above the shoulders, which is one place the girth search  
does work: the neck is a genuine waist between head and trunk.

The MTP cut is not here at all — it comes from the model's own foot  
geometry later. A scan foot is usually shorter ahead of the ankle than the  
model's, so cutting the toes at a fraction of foot length puts the joint in  
the wrong place.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_rig.py#L653)</sub>

### `read_model_landmarks`

```python
read_model_landmarks(osim: str | Path) -> ModelLandmarks
```

| input | type | default |
|---|---|---|
| `osim` | str \| Path | required |

**returns** `ModelLandmarks`

Read hip / knee / ankle / MTP geometry out of a base ``.osim``.

Falls back to :data:`GPK_LANDMARKS` for anything the file does not name in  
a way this can recognise, so an unusual model degrades to slightly-wrong  
segment lengths rather than an exception. ``ModelLandmarks.source`` records  
which happened — check it when a limb comes out the wrong length.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_rig.py#L840)</sub>

### `cap_open_boundaries`

```python
cap_open_boundaries(
    V: Array,
    F: Array,
    min_len: int = 3,
    passes: int = 4
) -> Tuple[Array, Array]
```

| input | type | default |
|---|---|---|
| `V` | Array | required |
| `F` | Array | required |
| `min_len` | int | `3` |
| `passes` | int | `4` |

**returns** `Tuple[Array, Array]`

Close every hole by fanning its loop to the loop's centroid.

A plane cut leaves an open shell. In a viewer with back-face culling that  
is not a subtle artefact — flex the knee and you are looking straight into  
the inside of the thigh. Loops shorter than ``min_len`` are skipped; the  
default of 3 caps everything, because a stray triangle costs nothing and a  
hole left in a small piece is still a hole.

Fanning is exact for a convex loop and acceptable for the mildly concave  
ones a joint cut produces. A deeply concave loop (a cut through splayed  
fingers) gets a slightly bulged cap, not a self-intersecting one.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_rig.py#L1125)</sub>

### `write_osim`

```python
write_osim(
    base: str | Path,
    out_path: str | Path,
    meshes: Dict[str, List[Path]],
    stl_rel: str,
    colour: str = '0.89 0.71 0.60',
    opacity: float = 1.0,
    keep_bones: bool = False,
    bone_dir: str = 'Geometry',
    model_name: str | None = None
) -> Path
```

| input | type | default |
|---|---|---|
| `base` | str \| Path | required |
| `out_path` | str \| Path | required |
| `meshes` | Dict[str, List[Path]] | required |
| `stl_rel` | str | required |
| `colour` | str | `'0.89 0.71 0.60'` |
| `opacity` | float | `1.0` |
| `keep_bones` | bool | `False` |
| `bone_dir` | str | `'Geometry'` |
| `model_name` | str \| None | `None` |

**returns** `Path`

Copy a base model, swapping each body's display geometry for our meshes.

Everything that is not ``<attached_geometry>`` — joints, coordinates,  
constraints, forces, markers, wrap objects — is copied verbatim, which is  
the whole point: the result drives from the same motion files and setup XML  
as the model it came from.

``keep_bones=True`` leaves the original bone meshes in place under the skin  
so you can see whether the surface actually contains the skeleton. That  
x-ray copy is the fastest check that a rig came out right.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_rig.py#L1281)</sub>

### `rig_mesh`

```python
rig_mesh(
    src: str | Path,
    base_model: str | Path | None = None,
    out_dir: str | Path = '.',
    name: str = 'subject',
    config: RigConfig | None = None
) -> RigResult
```

| input | type | default |
|---|---|---|
| `src` | str \| Path | required |
| `base_model` | str \| Path \| None | `None` |
| `out_dir` | str \| Path | `'.'` |
| `name` | str | `'subject'` |
| `config` | RigConfig \| None | `None` |

**returns** `RigResult`

Rig a whole-body surface mesh onto an OpenSim skeleton.

  
**Parameters**

src : str or Path  
    The scan or sculpt: ``.stl``, ``.obj``, or anything pyvista reads.  
    One connected human-shaped surface, standing, arms clear of the body.  
base_model : str or Path, optional  
    Skeleton to rig onto. Defaults to the highest-versioned GPK model  
    :func:`default_base_model` can find. Any ``.osim`` works; body names  
    are matched against it, so a model with ``skull`` gets a head that  
    follows the neck and one without carries the head on ``torso``.  
out_dir : str or Path  
    Written to as ``<out_dir>/<name>.osim`` plus ``<out_dir>/stl_<name>/``.  
name : str  
    Stem for the model and its STL folder.  
config : RigConfig, optional  
    See :class:`RigConfig`. The one field worth setting on every run is  
    ``target_height``.

  
**Returns**

RigResult  
    Paths written, the landmarks and joint centres that were used, and  
    timing. Print ``result.landmarks`` before believing any output — a rig  
    that came out wrong almost always has one landmark obviously off.

  
**Raises**

ValueError  
    If the landmarks come out in the wrong vertical order, which means the  
    mesh is not a standing human in the orientation the config claims.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_rig.py#L1367)</sub>
