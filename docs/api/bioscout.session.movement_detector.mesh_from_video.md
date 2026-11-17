# `bioscout.session.movement_detector.mesh_from_video`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_from_video.py)

mesh_from_video — a closed body mesh from a fixed-camera turntable video.

The capture is the cheapest one there is: put a phone on a tripod, have the  
subject stand on the spot and turn through a full circle, stopping briefly at a  
few known angles. This module turns that clip into one watertight STL, which  
:mod:`bioscout.session.movement_detector.mesh_rig` then rigs onto an OpenSim skeleton::

    from bioscout.session.movement_detector import carve_from_video, rig_mesh  
    res = carve_from_video("turn.mp4", "subject01/body.stl",  
                           config=CarveConfig(target_height=1.81))  
    rig_mesh(res.mesh_path, out_dir="subject01", name="bas")

Command line::

    python -m bioscout.session.movement_detector.mesh_from_video turn.mp4 \  
        --views front=0,q1@45=1.6,right=3.1,q3@135=4.7 --height 1.81 -o body.stl

  
**Choosing views**

Azimuths 180 apart are **geometrically redundant**: under orthographic  
projection the silhouette at 0 and at 180 pin the body between the same pair of  
planes, so front/right/back/left is only *two* distinct constraints and carves a  
limb 27% too fat. Spread the views over a **half** turn instead — 0/45/90/135  
costs the same four stops and cuts that to 5%. Eight stops over 180 reach 1.3%.  
See :func:`hull_bias`. (Views past 180 still earn their keep for robustness,  
since ``tolerance`` votes over all of them, but they add no new geometry.)

  
**Method**

**Shape from silhouette** (the visual hull). Each view's silhouette back-projects  
to a cone containing the subject; the intersection of the cones over a full turn  
is a closed solid that bounds the true body. Concretely:

1. **Grab** the frames the caller named, each with the azimuth the subject was  
   facing at that moment (:class:`ViewSpec`).  
2. **Segment** the person in each frame. MediaPipe is the default, but note it  
   reorganised at 1.0: ``mp.solutions.selfie_segmentation`` (weights bundled in  
   the wheel) was removed, and the replacement Tasks API needs a ``.tflite``  
   fetched from Google. So the backend is pluggable — ``"background"`` needs no  
   model at all, only a frame of the empty scene, and ``mask_dir`` accepts masks  
   from any other tool. The mask is then cleaned: threshold, largest connected  
   component, hole fill.  
3. **Register** the views to each other. The camera never moves and the subject  
   turns on the spot, so one scale (metres per pixel, from ``target_height``),  
   one ground row and one rotation-axis column serve every view.  
4. **Carve** a voxel grid: a voxel survives if it projects inside the silhouette  
   in every view (``tolerance`` allows a few disagreements, which rescues a run  
   where one mask clipped a hand).  
5. **Surface** the result. A Euclidean distance transform turns the binary  
   occupancy into a signed field, and naive surface nets extracts its zero level  
   as a closed, manifold, quad-derived triangle mesh — smoother than a blocky  
   voxel boundary and, unlike marching cubes, small enough to carry here rather  
   than take on scikit-image as a dependency.  
6. **Smooth and write** with ``mesh_rig``'s Taubin pass and fast STL writer, so  
   the output is byte-identical in style to the rest of the mesh pipeline.

  
**What this cannot do**

A visual hull is an *upper bound* on the body. Anything the silhouette never  
reveals stays filled in:

* **Concavities never show.** The small of the back, the gap under the chin and  
  the dish of the stomach come out flatter than life. This is inherent to the  
  method, not a tuning problem.  
* **Arms against the torso weld to it.** The subject must hold the arms clearly  
  away from the body — an A-pose — or the hull bridges the gap and the rig's  
  crotch/limb landmarks land on a solid slab.  
* **Loose clothing is measured, not the body.** Anthropometry from the result is  
  of the clothed subject. Fitted clothing, and no skirts.  
* **The turn must be on the spot.** Translating across the floor breaks the  
  single-axis assumption and smears the carve; so does turning the head or  
  shifting the arms between views.

For segment volumes and inertial parameters the hull is nonetheless a reasonable  
instrument — it is what photogrammetric anthropometry has always used — but the  
numbers should be treated as an estimate and sanity-checked against a table.

## Contents

- class [`ViewSpec`](#viewspec) — One frame of the turn, and the azimuth the subject was at.
- class [`CarveConfig`](#carveconfig) — Tunables for the carve. Defaults suit a phone clip of a standing adult.
- class [`CarveResult`](#carveresult) — What a carve produced, and enough numbers to judge whether to trust it.
  - [`CarveResult.summary`](#carveresultsummary) — One-line sanity check.
- [`hull_bias`](#hull_bias) — Systematic volume overestimate of a hull carved from these azimuths.
- [`parse_views`](#parse_views) — Parse a CLI view string into :class:`ViewSpec` objects.
- [`read_view_frames`](#read_view_frames) — Grab one RGB frame per view from ``video``.
- [`make_segmenter`](#make_segmenter) — Build the segmentation backend named by ``cfg.backend``.
- [`silhouette`](#silhouette) — Boolean person mask for one RGB frame.
- [`silhouettes_from_video`](#silhouettes_from_video) — Silhouette mask per view, opening the backend once for the whole set.
- [`register_views`](#register_views) — Recover ``(axis_col, ground_row, m_per_px)`` from the silhouettes.
- [`carve_visual_hull`](#carve_visual_hull) — Intersect the silhouette cones into a voxel occupancy grid.
- [`regularise_occupancy`](#regularise_occupancy) — Remove diagonal-only contacts, so the isosurface comes out manifold.
- [`surface_nets`](#surface_nets) — Extract the ``level`` isosurface of a scalar field as a closed mesh.
- [`is_watertight`](#is_watertight) — True when every edge is shared by exactly two triangles.
- [`carve_from_video`](#carve_from_video) — Fixed-camera turntable video in, one closed STL out.

<a id="viewspec"></a>

## class `ViewSpec`

One frame of the turn, and the azimuth the subject was at.

Give exactly one of ``time_s`` or ``frame``. ``angle_deg`` follows  
:data:`STANDARD_VIEWS`: 0 facing the camera, increasing as the subject turns  
to their own left.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_from_video.py#L154)</sub>

<a id="carveconfig"></a>

## class `CarveConfig`

Tunables for the carve. Defaults suit a phone clip of a standing adult.

  
**Attributes**

target_height : float  
    Subject's stature in metres. This is the only metric input — it sets the  
    scale of everything downstream, so measure it rather than guess.  
voxels : int  
    Grid resolution along the *height* axis. 192 gives roughly a centimetre  
    voxel on an adult and carves in a few seconds; 320 is visibly finer and  
    about five times the work. Memory grows as the cube.  
tolerance : int  
    Number of views a voxel is allowed to fall outside and still survive.  
    0 is the strict visual hull. 1 rescues a run where a single mask clipped  
    a hand, at the cost of a slightly fatter body.  
mask_threshold : float  
    Confidence above which MediaPipe's soft mask counts as person.  
erode, dilate : int  
    Pixels of morphological erosion / dilation applied to each mask. Erode  
    trims the halo a soft segmenter leaves around the body; dilate is the  
    escape hatch if the carve comes out too thin.  
smooth : int  
    Taubin smoothing passes on the finished mesh. Takes the voxel stair-step  
    off without shrinking the volume the way a plain Laplacian would.  
keep_largest : bool  
    Discard everything but the largest connected blob, which removes the  
    floating specks a stray mask pixel leaves behind.  
regularise : bool  
    Weld diagonal-only voxel contacts before surfacing, so the mesh comes  
    out manifold. See :func:`regularise_occupancy`. Leave it on — a single  
    non-manifold edge is enough to break ``mesh_rig``.  
close_iters : int  
    Binary-closing passes on the voxel volume, to bridge pinholes before  
    surfacing. Keep small; this also fills genuine detail.  
margin : float  
    Fraction of the subject's width added around the grid, so the body never  
    touches the boundary (which would leave an open mesh).  
backend : str  
    Which segmenter to use: ``"auto"`` (MediaPipe, falling back to  
    background subtraction if a ``background`` is set and the model cannot  
    be reached), ``"mediapipe-legacy"``, ``"mediapipe-tasks"`` or  
    ``"background"``.  
model_path : str or Path, optional  
    ``.tflite`` for the Tasks backend, when it cannot be downloaded. Also  
    read from ``$BIOSCOUT_SEGMENTER_MODEL``.  
background : str, Path or ndarray, optional  
    Empty-scene reference for the background backend: an image path, an RGB  
    array, or ``"#0"`` / seconds to take a frame from the clip itself.  
bg_threshold : int  
    Per-channel intensity difference, 0-255, above which a pixel differs  
    from the background. Raise it if shadows are being carved.  
mask_dir : str or Path, optional  
    Skip segmentation entirely and read ``<mask_dir>/<view name>.png``.  
    The way to use a better mask from any other tool.  
axis_col, ground_row, m_per_px : float or None  
    Registration overrides, in pixels. ``None`` auto-detects from the  
    silhouettes, which is right whenever the subject turns on the spot.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_from_video.py#L174)</sub>

<a id="carveresult"></a>

## class `CarveResult`

What a carve produced, and enough numbers to judge whether to trust it.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_from_video.py#L260)</sub>

<a id="carveresultsummary"></a>

### `CarveResult.summary`

```python
CarveResult.summary() -> str
```

**returns** `str`

One-line sanity check.

A standing adult lands near 60-100 L. The quoted bias is what  
:func:`hull_bias` predicts for this view set — the hull is an upper  
bound, so the true body is smaller than the number printed.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_from_video.py#L276)</sub>

### `hull_bias`

```python
hull_bias(angles_deg: Sequence[float]) -> float
```

| input | type | default |
|---|---|---|
| `angles_deg` | Sequence[float] | required |

**returns** `float`

Systematic volume overestimate of a hull carved from these azimuths.

A silhouette constrains the body to a slab, and azimuths 180 apart give the  
*same* slab, so ``n`` distinct slab orientations carve a circular  
cross-section into a circumscribed regular ``2n``-gon rather than the circle:

.. math:: \text{bias} = \frac{2n \tan(\pi / 2n)}{\pi}

which is 1.27 for 2 slabs, 1.055 for 4, 1.013 for 8 and 1.006 for 12. So  
four views (front/right/back/left) overestimate a limb's volume by about 5%,  
eight views by 1.3%, and past a dozen the discretisation error dominates and  
more views stop paying. Body cross-sections are not circles, so treat this  
as the scale of the effect rather than a correction factor to divide out.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_from_video.py#L128)</sub>

### `parse_views`

```python
parse_views(spec: str) -> List[ViewSpec]
```

| input | type | default |
|---|---|---|
| `spec` | str | required |

**returns** `List[ViewSpec]`

Parse a CLI view string into :class:`ViewSpec` objects.

Format is comma-separated ``name=time`` or ``name@angle=time`` entries, where  
``time`` is seconds into the clip, or ``#123`` for a frame index::

    "front=0,right=3.1,back=6.4,left=9.2"  
    "front@0=0.5,q1@45=1.8,side@90=3.0"  
    "front=#12,right=#96"

A bare ``name`` must be one of :data:`STANDARD_VIEWS`; use ``name@angle`` for  
anything else.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_from_video.py#L298)</sub>

### `read_view_frames`

```python
read_view_frames(video: str | Path, views: Sequence[ViewSpec]) -> List[Array]
```

| input | type | default |
|---|---|---|
| `video` | str \| Path | required |
| `views` | Sequence[ViewSpec] | required |

**returns** `List[Array]`

Grab one RGB frame per view from ``video``.

Frames are read in ascending order so the capture is walked once forwards,  
which matters for the long GOPs phone footage uses.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_from_video.py#L356)</sub>

### `make_segmenter`

```python
make_segmenter(cfg: CarveConfig, video: str | Path | None = None)
```

| input | type | default |
|---|---|---|
| `cfg` | CarveConfig | required |
| `video` | str \| Path \| None | `None` |

Build the segmentation backend named by ``cfg.backend``.

``"auto"`` prefers MediaPipe and falls back to background subtraction when a  
background was supplied, so a config that names one always gets a working  
run even on a machine where the model cannot be fetched.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_from_video.py#L594)</sub>

### `silhouette`

```python
silhouette(frame: Array, cfg: CarveConfig | None = None, _segmenter=None) -> Array
```

| input | type | default |
|---|---|---|
| `frame` | Array | required |
| `cfg` | CarveConfig \| None | `None` |
| `_segmenter` | – | `None` |

**returns** `Array`

Boolean person mask for one RGB frame.

Pass ``_segmenter`` (from :func:`make_segmenter`) to reuse one backend across  
frames; constructing it costs far more than running it.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_from_video.py#L637)</sub>

### `silhouettes_from_video`

```python
silhouettes_from_video(
    video: str | Path,
    views: Sequence[ViewSpec],
    cfg: CarveConfig | None = None
) -> List[Array]
```

| input | type | default |
|---|---|---|
| `video` | str \| Path | required |
| `views` | Sequence[ViewSpec] | required |
| `cfg` | CarveConfig \| None | `None` |

**returns** `List[Array]`

Silhouette mask per view, opening the backend once for the whole set.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_from_video.py#L653)</sub>

### `register_views`

```python
register_views(masks: Sequence[Array], cfg: CarveConfig) -> Tuple[float, float, float]
```

| input | type | default |
|---|---|---|
| `masks` | Sequence[Array] | required |
| `cfg` | CarveConfig | required |

**returns** `Tuple[float, float, float]`

Recover ``(axis_col, ground_row, m_per_px)`` from the silhouettes.

The camera is fixed and the subject turns on the spot, so one registration  
serves every view. The ground row is the lowest foot pixel seen in any view  
and the head row the highest, which together with ``target_height`` give the  
scale. The rotation axis is the mean of the per-view bounding-box centres:  
a subject standing slightly off-axis swings left and right about the true  
axis through the turn, and over a roughly symmetric set of views that  
averages out.

Any of the three may be pinned in the config, which is what to do when the  
subject's arms are out far enough to bias the bounding boxes.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_from_video.py#L708)</sub>

### `carve_visual_hull`

```python
carve_visual_hull(
    masks: Sequence[Array],
    angles_deg: Sequence[float],
    cfg: CarveConfig
) -> Tuple[Array, Array, Array]
```

| input | type | default |
|---|---|---|
| `masks` | Sequence[Array] | required |
| `angles_deg` | Sequence[float] | required |
| `cfg` | CarveConfig | required |

**returns** `Tuple[Array, Array, Array]`

Intersect the silhouette cones into a voxel occupancy grid.

Returns ``(occupancy, origin, spacing)`` with the grid in metres, y up, the  
feet on ``y = 0``, +x to the camera's right at the front view and +z toward  
the camera.

Projection is orthographic. For a subject a few metres from a phone camera  
the perspective across their own depth is a couple of percent, well under  
the error the segmentation already contributes, and orthographic needs no  
calibration at all — which is the difference between a module that runs on  
any clip and one that needs a checkerboard.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_from_video.py#L747)</sub>

### `regularise_occupancy`

```python
regularise_occupancy(occ: Array, max_passes: int = 8) -> Tuple[Array, int]
```

| input | type | default |
|---|---|---|
| `occ` | Array | required |
| `max_passes` | int | `8` |

**returns** `Tuple[Array, int]`

Remove diagonal-only contacts, so the isosurface comes out manifold.

Surface nets places exactly one vertex per cell, which cannot represent two  
surface sheets passing through the same cell. That happens wherever the  
occupancy touches itself only across a diagonal — a 2x2 checkerboard in some  
axis-aligned plane. The result is an edge shared by four triangles instead of  
two: the mesh is no longer manifold, and ``mesh_rig``'s boundary walk and  
every downstream mesh tool treat it as broken.

Rather than repair the triangles afterwards, fix the cause: fill one voxel of  
each checkerboard, which welds the diagonal contact into a face contact.  
Filling can create new checkerboards a cell over, so it iterates to a fixed  
point. The change is a handful of voxels on a body-sized grid — far below the  
carve's own discretisation error.

Returns the corrected grid and how many voxels were added.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_from_video.py#L845)</sub>

### `surface_nets`

```python
surface_nets(
    field: Array,
    spacing: Array,
    origin: Array,
    level: float = 0.0
) -> Tuple[Array, Array]
```

| input | type | default |
|---|---|---|
| `field` | Array | required |
| `spacing` | Array | required |
| `origin` | Array | required |
| `level` | float | `0.0` |

**returns** `Tuple[Array, Array]`

Extract the ``level`` isosurface of a scalar field as a closed mesh.

Naive surface nets: one vertex per cell that straddles the level, placed at  
the mean of that cell's edge crossings, and one quad per straddling grid  
edge joining the four cells around it. The result is manifold and closed  
provided the field is above ``level`` on the whole boundary — which is why  
the carve pads its grid.

Chosen over marching cubes because it is a fifth of the code, has no  
256-case table to get subtly wrong, and produces far fewer, better-shaped  
triangles; the cost is slightly softer sharp edges, which a body scan does  
not have anyway.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_from_video.py#L904)</sub>

### `is_watertight`

```python
is_watertight(faces: Array) -> bool
```

| input | type | default |
|---|---|---|
| `faces` | Array | required |

**returns** `bool`

True when every edge is shared by exactly two triangles.

Worth checking on every carve rather than trusting the pipeline: ``mesh_rig``  
walks boundary loops to cap its cuts, and a mesh with a hole sends that walk  
somewhere meaningless instead of failing loudly.

This tests *topology*, so it needs shared vertex indices. Faces read back  
from an STL never have them — the format stores three loose vertices per  
triangle — so a mesh loaded from disk must go through  
:func:`~bioscout.session.movement_detector.mesh_rig.weld` first, exactly as  
``rig_mesh`` does. Called on unwelded faces this always returns False.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_from_video.py#L1006)</sub>

### `carve_from_video`

```python
carve_from_video(
    video: str | Path,
    out_path: str | Path,
    views: Sequence[ViewSpec] | str,
    config: CarveConfig | None = None
) -> CarveResult
```

| input | type | default |
|---|---|---|
| `video` | str \| Path | required |
| `out_path` | str \| Path | required |
| `views` | Sequence[ViewSpec] \| str | required |
| `config` | CarveConfig \| None | `None` |

**returns** `CarveResult`

Fixed-camera turntable video in, one closed STL out.

  
**Parameters**

video : str or Path  
    The clip. Fixed camera, subject turning on the spot in an A-pose.  
out_path : str or Path  
    Destination ``.stl``.  
views : sequence of ViewSpec, or str  
    Which frames to use and what azimuth each is. A string is passed to  
    :func:`parse_views`. Spread them over a *half* turn, not a full one —  
    0/45/90/135 is the practical minimum, and 8 stops over 180 is  
    noticeably rounder. See :func:`hull_bias` for why front/back is a  
    wasted pair.  
config : CarveConfig, optional  
    See :class:`CarveConfig`. ``target_height`` is the field to set.

  
**Returns**

CarveResult  
    Print ``result.summary()`` before trusting the mesh — a standing adult  
    should come out near 60-100 litres, and a wildly different volume means  
    the registration or the view angles are wrong.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_from_video.py#L1043)</sub>
