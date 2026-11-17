# `bioscout.model.mri2msk.landmarks`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/landmarks.py)

Automatic landmark generation for the OpenSim Creator Mesh Warper.

Idea: after step 1 the participant bone is already in the OpenSim frame and  
scaled to the base bone, so both meshes almost overlap. We

1. pick ``n`` well-spread landmarks on the base mesh (farthest-point sampling),  
2. register base -> participant with Coherent Point Drift (affine, then  
   non-rigid; Myronenko & Song 2010),  
3. push the base landmarks through that deformation and snap them onto the  
   participant surface,  
4. write ``base_<bone>.csv`` / ``participant_<bone>.csv`` in the Mesh Warper  
   format (``name,x,y,z``).

Pure numpy/scipy, no extra dependency.

## Contents

- class [`Registration`](#registration) — Base -> participant mapping in normalised coordinates.
- [`read_landmarks_csv`](#read_landmarks_csv) — 
- [`write_landmarks_csv`](#write_landmarks_csv) — 
- [`mesh_points`](#mesh_points) — Area-uniform random surface samples (deterministic seed).
- [`farthest_point_sampling`](#farthest_point_sampling) — ``n`` well-spread points; starts at the point farthest from the centroid.
- [`cpd_affine`](#cpd_affine) — Affine CPD. Returns (B (3,3), t (3,)) so that Y -> Y @ B.T + t.
- [`cpd_deformable`](#cpd_deformable) — Non-rigid CPD (motion coherence). Returns (W (M,3), beta) with T(Y) = Y + G(Y,Y) W, G = exp(-|yi-yj|^2 / (2 beta^2)).
- [`register`](#register) — CPD registration of the base surface onto the participant surface.
- [`snap_to_surface`](#snap_to_surface) — Closest point on the mesh (dense surface sampling + vertices).
- [`auto_landmarks`](#auto_landmarks) — Return (names, base_pts, participant_pts) for one bone.
- [`auto_landmarks_for_participant`](#auto_landmarks_for_participant) — Generate and write CSVs for every bone in ``info`` (from ``pipeline.prepare_mesh_warper_files``). ``counts`` maps bone -> n landmarks.

<a id="registration"></a>

## class `Registration`

Base -> participant mapping in normalised coordinates.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/landmarks.py#L134)</sub>

### `read_landmarks_csv`

```python
read_landmarks_csv(path) -> tuple[list[str], np.ndarray]
```

| input | type | default |
|---|---|---|
| `path` | – | required |

**returns** `tuple[list[str], np.ndarray]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/landmarks.py#L28)</sub>

### `write_landmarks_csv`

```python
write_landmarks_csv(path, names, pts) -> None
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `names` | – | required |
| `pts` | – | required |

**returns** `None`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/landmarks.py#L38)</sub>

### `mesh_points`

```python
mesh_points(vertices, faces, n, seed=0)
```

| input | type | default |
|---|---|---|
| `vertices` | – | required |
| `faces` | – | required |
| `n` | – | required |
| `seed` | – | `0` |

Area-uniform random surface samples (deterministic seed).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/landmarks.py#L44)</sub>

### `farthest_point_sampling`

```python
farthest_point_sampling(pts, n)
```

| input | type | default |
|---|---|---|
| `pts` | – | required |
| `n` | – | required |

``n`` well-spread points; starts at the point farthest from the centroid.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/landmarks.py#L55)</sub>

### `cpd_affine`

```python
cpd_affine(X, Y, w=0.1, iters=60, tol=1e-06)
```

| input | type | default |
|---|---|---|
| `X` | – | required |
| `Y` | – | required |
| `w` | – | `0.1` |
| `iters` | – | `60` |
| `tol` | – | `1e-06` |

Affine CPD. Returns (B (3,3), t (3,)) so that Y -> Y @ B.T + t.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/landmarks.py#L86)</sub>

### `cpd_deformable`

```python
cpd_deformable(X, Y, beta=2.0, lam=2.0, w=0.1, iters=80, tol=1e-06)
```

| input | type | default |
|---|---|---|
| `X` | – | required |
| `Y` | – | required |
| `beta` | – | `2.0` |
| `lam` | – | `2.0` |
| `w` | – | `0.1` |
| `iters` | – | `80` |
| `tol` | – | `1e-06` |

Non-rigid CPD (motion coherence). Returns (W (M,3), beta) with  
T(Y) = Y + G(Y,Y) W, G = exp(-|yi-yj|^2 / (2 beta^2)).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/landmarks.py#L109)</sub>

### `register`

```python
register(base_v, base_f, part_v, part_f, n_points=1500, beta=3.0, lam=3.0, seed=0)
```

| input | type | default |
|---|---|---|
| `base_v` | – | required |
| `base_f` | – | required |
| `part_v` | – | required |
| `part_f` | – | required |
| `n_points` | – | `1500` |
| `beta` | – | `3.0` |
| `lam` | – | `3.0` |
| `seed` | – | `0` |

CPD registration of the base surface onto the participant surface.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/landmarks.py#L152)</sub>

### `snap_to_surface`

```python
snap_to_surface(pts, vertices, faces, n_dense=60000, seed=2)
```

| input | type | default |
|---|---|---|
| `pts` | – | required |
| `vertices` | – | required |
| `faces` | – | required |
| `n_dense` | – | `60000` |
| `seed` | – | `2` |

Closest point on the mesh (dense surface sampling + vertices).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/landmarks.py#L166)</sub>

### `auto_landmarks`

```python
auto_landmarks(
    base_stl,
    participant_stl,
    n_landmarks=25,
    base_landmarks=None,
    n_points=1500
)
```

| input | type | default |
|---|---|---|
| `base_stl` | – | required |
| `participant_stl` | – | required |
| `n_landmarks` | – | `25` |
| `base_landmarks` | – | `None` |
| `n_points` | – | `1500` |

Return (names, base_pts, participant_pts) for one bone.

``base_landmarks``: optional (names, pts) to reuse instead of sampling.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/landmarks.py#L173)</sub>

### `auto_landmarks_for_participant`

```python
auto_landmarks_for_participant(info: dict, counts: dict[str, int], log=print) -> None
```

| input | type | default |
|---|---|---|
| `info` | dict | required |
| `counts` | dict[str, int] | required |
| `log` | – | `print` |

**returns** `None`

Generate and write CSVs for every bone in ``info`` (from  
``pipeline.prepare_mesh_warper_files``). ``counts`` maps bone -> n landmarks.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/landmarks.py#L191)</sub>
