# `bioscout.model.mri2msk.staple.algorithms`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/algorithms.py)

STAPLE joint coordinate systems used by MRI2MSK step 1.

Ported from STAPLE (Modenese & Renault 2021, CC BY-NC 4.0) / GIBOC-core:

* ``staple_pelvis``  -> JCS.ground_pelvis   (STAPLE_pelvis.m + pelvis_guess_CS.m)  
* ``kai2014_tibia``  -> JCS.knee_<side>      (Kai2014_tibia.m)  
* ``giboc_femur``    -> JCS.hip_<side>       (GIBOC_femur.m, 'ellipsoids')

All return ``(origin (3,), V (3,3))`` in the mesh units (mm), V columns = X, Y, Z.

## Contents

- [`side_sign`](#side_sign) — 
- [`pelvis_guess_cs`](#pelvis_guess_cs) — 
- [`cs_pelvis_isb`](#cs_pelvis_isb) — 
- [`staple_pelvis`](#staple_pelvis) — Returns (origin, V, landmarks) for JCS.ground_pelvis.
- [`tibia_guess_cs`](#tibia_guess_cs) — 
- [`tibia_identify_lateral_direction`](#tibia_identify_lateral_direction) — 
- [`kai2014_tibia`](#kai2014_tibia) — Returns (origin, V) of JCS.knee_<side>.
- [`femur_guess_cs`](#femur_guess_cs) — 
- [`giboc_fit_sphere_fem_head`](#giboc_fit_sphere_fem_head) — 
- [`giboc_isolate_epiphysis`](#giboc_isolate_epiphysis) — 
- [`pc_region_growing`](#pc_region_growing) — 
- [`giboc_femur_process_epiphysis`](#giboc_femur_process_epiphysis) — 
- [`get_condyle_most_prox_point`](#get_condyle_most_prox_point) — 
- [`pts_on_condyles_femur`](#pts_on_condyles_femur) — 
- [`giboc_femur_artic_surf_full`](#giboc_femur_artic_surf_full) — GIBOC_femur_ArticSurf with art_surface='full_condyles'. Returns (med, lat) Tri.
- [`giboc_femur`](#giboc_femur) — GIBOC_femur(..., 'ellipsoids'). Returns (origin, V) of JCS.hip_<side>.

### `side_sign`

```python
side_sign(side: str) -> int
```

| input | type | default |
|---|---|---|
| `side` | str | required |

**returns** `int`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/algorithms.py#L27)</sub>

### `pelvis_guess_cs`

```python
pelvis_guess_cs(pelvis: Tri)
```

| input | type | default |
|---|---|---|
| `pelvis` | Tri | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/algorithms.py#L32)</sub>

### `cs_pelvis_isb`

```python
cs_pelvis_isb(RASIS, LASIS, RPSIS, LPSIS)
```

| input | type | default |
|---|---|---|
| `RASIS` | – | required |
| `LASIS` | – | required |
| `RPSIS` | – | required |
| `LPSIS` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/algorithms.py#L73)</sub>

### `staple_pelvis`

```python
staple_pelvis(pelvis: Tri, side='r')
```

| input | type | default |
|---|---|---|
| `pelvis` | Tri | required |
| `side` | – | `'r'` |

Returns (origin, V, landmarks) for JCS.ground_pelvis.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/algorithms.py#L81)</sub>

### `tibia_guess_cs`

```python
tibia_guess_cs(tibia: Tri)
```

| input | type | default |
|---|---|---|
| `tibia` | Tri | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/algorithms.py#L110)</sub>

### `tibia_identify_lateral_direction`

```python
tibia_identify_lateral_direction(dist_tib: Tri, Z0)
```

| input | type | default |
|---|---|---|
| `dist_tib` | Tri | required |
| `Z0` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/algorithms.py#L128)</sub>

### `kai2014_tibia`

```python
kai2014_tibia(tibia: Tri, side='r', slice_thickness=1.0)
```

| input | type | default |
|---|---|---|
| `tibia` | Tri | required |
| `side` | – | `'r'` |
| `slice_thickness` | – | `1.0` |

Returns (origin, V) of JCS.knee_<side>.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/algorithms.py#L146)</sub>

### `femur_guess_cs`

```python
femur_guess_cs(femur: Tri)
```

| input | type | default |
|---|---|---|
| `femur` | Tri | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/algorithms.py#L181)</sub>

### `giboc_fit_sphere_fem_head`

```python
giboc_fit_sphere_fem_head(prox: Tri, cs: dict, cm: float)
```

| input | type | default |
|---|---|---|
| `prox` | Tri | required |
| `cs` | dict | required |
| `cm` | float | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/algorithms.py#L204)</sub>

### `giboc_isolate_epiphysis`

```python
giboc_isolate_epiphysis(tri: Tri, Z0, which='distal')
```

| input | type | default |
|---|---|---|
| `tri` | Tri | required |
| `Z0` | – | required |
| `which` | – | `'distal'` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/algorithms.py#L237)</sub>

### `pc_region_growing`

```python
pc_region_growing(pts, seed, r)
```

| input | type | default |
|---|---|---|
| `pts` | – | required |
| `seed` | – | required |
| `r` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/algorithms.py#L245)</sub>

### `giboc_femur_process_epiphysis`

```python
giboc_femur_process_epiphysis(epi: Tri, cs, V_all, edge_thr=0.5, dev_thr=0.75)
```

| input | type | default |
|---|---|---|
| `epi` | Tri | required |
| `cs` | – | required |
| `V_all` | – | required |
| `edge_thr` | – | `0.5` |
| `dev_thr` | – | `0.75` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/algorithms.py#L260)</sub>

### `get_condyle_most_prox_point`

```python
get_condyle_most_prox_point(epi: Tri, cs, trace, U)
```

| input | type | default |
|---|---|---|
| `epi` | Tri | required |
| `cs` | – | required |
| `trace` | – | required |
| `U` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/algorithms.py#L291)</sub>

### `pts_on_condyles_femur`

```python
pts_on_condyles_femur(P0, Pepi, cut_angle, inset, dilat)
```

| input | type | default |
|---|---|---|
| `P0` | – | required |
| `Pepi` | – | required |
| `cut_angle` | – | required |
| `inset` | – | required |
| `dilat` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/algorithms.py#L302)</sub>

### `giboc_femur_artic_surf_full`

```python
giboc_femur_artic_surf_full(epi: Tri, cs, cm)
```

| input | type | default |
|---|---|---|
| `epi` | Tri | required |
| `cs` | – | required |
| `cm` | – | required |

GIBOC_femur_ArticSurf with art_surface='full_condyles'. Returns (med, lat) Tri.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/algorithms.py#L328)</sub>

### `giboc_femur`

```python
giboc_femur(femur: Tri, side='r')
```

| input | type | default |
|---|---|---|
| `femur` | Tri | required |
| `side` | – | `'r'` |

GIBOC_femur(..., 'ellipsoids'). Returns (origin, V) of JCS.hip_<side>.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/algorithms.py#L364)</sub>
