# `bioscout.model.inspect.geometry`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/geometry.py)

Pure-numpy cylinder geometry (no OpenSim dependency).

Ported from the MATLAB helpers `eulerXYZToRotationMatrix` and  
`projectPointOutsideCylinder`. The cylinder axis is the local Z axis, matching  
OpenSim's WrapCylinder convention.

## Contents

- [`euler_xyz_to_rotation_matrix`](#euler_xyz_to_rotation_matrix) — XYZ body-fixed Euler angles (radians) -> 3x3 rotation matrix.
- [`radial_distance`](#radial_distance) — Radial distance of a point (in the wrap body's frame) from the cylinder axis.
- [`project_point_outside_cylinder`](#project_point_outside_cylinder) — Project a point (in the wrap body's frame) radially outside a cylinder.

### `euler_xyz_to_rotation_matrix`

```python
euler_xyz_to_rotation_matrix(rx: float, ry: float, rz: float) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `rx` | float | required |
| `ry` | float | required |
| `rz` | float | required |

**returns** `np.ndarray`

XYZ body-fixed Euler angles (radians) -> 3x3 rotation matrix.

Matches OpenSim's ``xyz_body_rotation`` convention for wrap objects:  
R = Rx @ Ry @ Rz.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/geometry.py#L12)</sub>

### `radial_distance`

```python
radial_distance(pt_body: np.ndarray, R_cyl: np.ndarray, t_cyl: np.ndarray) -> float
```

| input | type | default |
|---|---|---|
| `pt_body` | np.ndarray | required |
| `R_cyl` | np.ndarray | required |
| `t_cyl` | np.ndarray | required |

**returns** `float`

Radial distance of a point (in the wrap body's frame) from the cylinder axis.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/geometry.py#L28)</sub>

### `project_point_outside_cylinder`

```python
project_point_outside_cylinder(
    pt_body: np.ndarray,
    R_cyl: np.ndarray,
    t_cyl: np.ndarray,
    radius: float,
    margin: float
)
```

| input | type | default |
|---|---|---|
| `pt_body` | np.ndarray | required |
| `R_cyl` | np.ndarray | required |
| `t_cyl` | np.ndarray | required |
| `radius` | float | required |
| `margin` | float | required |

Project a point (in the wrap body's frame) radially outside a cylinder.

Returns ``(is_inside, pt_body_new, displacement_mm, r_point)``.  
If the point is already outside ``radius + margin`` it is returned unchanged.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/geometry.py#L34)</sub>
