# `bioscout.model.mri2msk.staple.fitting`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/fitting.py)

Fitting routines from GIBOC-core/SubFunctions/FittingFun (+ LSGE lsplane).

## Contents

- [`sphere_fit`](#sphere_fit) — Algebraic sphere fit (sphereFit.m). Returns centre (3,), radius, error dist.
- [`ellipsoid_fit`](#ellipsoid_fit) — Unconstrained ellipsoid fit (ellipsoid_fit.m, equals='').
- [`fit_ellipse`](#fit_ellipse) — Least-squares ellipse fit (fit_ellipse.m by O. Gal). Returns a dict.
- [`lsplane`](#lsplane) — Least-squares plane: (centroid (3,), unit normal (3,)).
- [`fit_csa`](#fit_csa) — fitCSA.m: locate diaphysis/epiphysis transition from cross-section areas.

### `sphere_fit`

```python
sphere_fit(X)
```

| input | type | default |
|---|---|---|
| `X` | – | required |

Algebraic sphere fit (sphereFit.m). Returns centre (3,), radius, error dist.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/fitting.py#L10)</sub>

### `ellipsoid_fit`

```python
ellipsoid_fit(X)
```

| input | type | default |
|---|---|---|
| `X` | – | required |

Unconstrained ellipsoid fit (ellipsoid_fit.m, equals='').

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/fitting.py#L29)</sub>

### `fit_ellipse`

```python
fit_ellipse(x, y)
```

| input | type | default |
|---|---|---|
| `x` | – | required |
| `y` | – | required |

Least-squares ellipse fit (fit_ellipse.m by O. Gal). Returns a dict.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/fitting.py#L52)</sub>

### `lsplane`

```python
lsplane(X)
```

| input | type | default |
|---|---|---|
| `X` | – | required |

Least-squares plane: (centroid (3,), unit normal (3,)).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/fitting.py#L88)</sub>

### `fit_csa`

```python
fit_csa(Z, Area)
```

| input | type | default |
|---|---|---|
| `Z` | – | required |
| `Area` | – | required |

fitCSA.m: locate diaphysis/epiphysis transition from cross-section areas.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/fitting.py#L103)</sub>
