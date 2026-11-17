# `bioscout.model.tps.landmarks_from_mri`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/landmarks_from_mri.py)

Derive bone landmarks directly from MRI segmentation masks.

This automates the previously-manual 3D-Slicer step: instead of hand-placing  
every fiducial, we read per-bone segmentation masks (one ``.nii.gz`` per bone,  
e.g. TotalSegmentator output), turn each into a surface point cloud, and compute  
landmarks with geometric rules (sphere fit for joint centres, extremal points  
along anatomical axes for prominences).

Output is a Slicer-compatible ``.mrk.json`` so the landmarks can be loaded,  
visually checked and nudged in 3D Slicer before feeding the TPS pipeline  
(``mri_landmarks`` input) — the human stays in the loop.

  
**Coordinate convention**

NIfTI affines are RAS+ (``+x`` right, ``+y`` anterior, ``+z`` superior). We  
compute landmarks in that world frame, then write the ``.mrk.json`` in Slicer's  
LPS convention with a per-point ``diag(-1,-1,1)`` orientation, so that  
``orientation @ position`` recovers the RAS world coordinate — matching the  
files the existing pipeline already consumes.

Heavy deps (``nibabel``/``SimpleITK`` + ``scikit-image``) are imported lazily so  
importing this module never requires them; only :func:`mask_surface` does.

NOTE: the anatomical rules assume a roughly anatomically-aligned supine scan  
(scan axes ≈ RAS). They are a first pass and should be verified in Slicer on  
first use for a new dataset/scanner.

## Contents

- [`mask_surface`](#mask_surface) — Return an (N,3) RAS world-coordinate point cloud of a mask's surface.
- [`fit_sphere`](#fit_sphere) — Algebraic least-squares sphere fit. Returns (center_xyz, radius).
- [`extract_landmarks`](#extract_landmarks) — Compute all derivable bone landmarks (RAS mm) from segmentation masks.
- [`write_mrk_json`](#write_mrk_json) — Write landmarks (RAS mm) to a Slicer ``.mrk.json`` fiducial file.
- [`extract_and_write`](#extract_and_write) — Convenience: extract landmarks from masks and write the ``.mrk.json``.

### `mask_surface`

```python
mask_surface(path: str | Path, level: float = 0.5) -> Array
```

| input | type | default |
|---|---|---|
| `path` | str \| Path | required |
| `level` | float | `0.5` |

**returns** `Array`

Return an (N,3) RAS world-coordinate point cloud of a mask's surface.

Uses marching cubes on the binary mask, then maps voxel vertices through the  
NIfTI affine to world (RAS mm). Requires ``nibabel`` and ``scikit-image``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/landmarks_from_mri.py#L60)</sub>

### `fit_sphere`

```python
fit_sphere(points: Array) -> tuple[Array, float]
```

| input | type | default |
|---|---|---|
| `points` | Array | required |

**returns** `tuple[Array, float]`

Algebraic least-squares sphere fit. Returns (center_xyz, radius).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/landmarks_from_mri.py#L83)</sub>

### `extract_landmarks`

```python
extract_landmarks(
    segmentation_dir: str | Path,
    mask_names: Optional[Dict[str, str]] = None
) -> Dict[str, Array]
```

| input | type | default |
|---|---|---|
| `segmentation_dir` | str \| Path | required |
| `mask_names` | Optional[Dict[str, str]] | `None` |

**returns** `Dict[str, Array]`

Compute all derivable bone landmarks (RAS mm) from segmentation masks.

Masks that are absent are skipped with a warning (their landmarks are simply  
not produced), so a partial mask set yields a partial landmark set.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/landmarks_from_mri.py#L219)</sub>

### `write_mrk_json`

```python
write_mrk_json(
    landmarks: Dict[str, Array],
    out_path: str | Path,
    coordinate_system: str = 'LPS'
) -> Path
```

| input | type | default |
|---|---|---|
| `landmarks` | Dict[str, Array] | required |
| `out_path` | str \| Path | required |
| `coordinate_system` | str | `'LPS'` |

**returns** `Path`

Write landmarks (RAS mm) to a Slicer ``.mrk.json`` fiducial file.

Stored in LPS with a per-point ``diag(-1,-1,1)`` orientation so that  
``orientation @ position`` recovers the RAS coordinate the TPS loader uses.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/landmarks_from_mri.py#L270)</sub>

### `extract_and_write`

```python
extract_and_write(
    segmentation_dir: str | Path,
    out_path: str | Path,
    mask_names: Optional[Dict[str, str]] = None
) -> Path
```

| input | type | default |
|---|---|---|
| `segmentation_dir` | str \| Path | required |
| `out_path` | str \| Path | required |
| `mask_names` | Optional[Dict[str, str]] | `None` |

**returns** `Path`

Convenience: extract landmarks from masks and write the ``.mrk.json``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/landmarks_from_mri.py#L312)</sub>
