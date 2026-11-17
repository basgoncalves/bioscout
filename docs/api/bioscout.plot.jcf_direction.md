# `bioscout.plot.jcf_direction`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py)

Polar plot of joint contact force DIRECTION and magnitude, on the model's bones.

One polar panel per joint. The BEARING is the direction of the contact force in  
one anatomical plane of the receiving bone's reference frame (SUP up, ANT right  
on the sagittal view); the RADIUS is the magnitude of the resultant, in body  
weights when a body weight is given. A loop is therefore the contact-force  
vector itself, traced over the trial. The grey silhouette behind each panel is  
that bone, read out of the .osim itself (mesh file, scale factors, offset  
frames) — its angles are exact, its radial size is arbitrary. With ``--ik`` the  
neighbouring segment is also drawn dotted at the two extremes of its motion,  
with a range-of-motion arc at the rim.

Works from any OpenSim JointReaction output — the analysis must have been run  
with the reaction applied to the CHILD body and expressed in the CHILD frame  
(OpenSim's default), giving columns like ``hip_r_on_femur_r_in_femur_r_fx``.

From a script::

    from bioscout.plot.jcf_direction import plot_jcf_direction  
    plot_jcf_direction("model.osim",  
                       {"SO": "jra_so.sto", "CEINMS": "jra_ceinms.sto"},  
                       mass=95, ik="joint_angles.mot", out="jcf_direction.png")

From the terminal::

    bioscout plot jcf --model model.osim --jra jra_so.sto jra_ceinms.sto         --labels SO CEINMS --mass 95 --ik joint_angles.mot -o jcf_direction.png

The hip is special: OpenSim writes the hip reaction ON the femur IN the femur  
frame. With ``--ik`` (the IK .mot of the same trial) the force is converted,  
exactly, to the femoral head ON the acetabulum in the PELVIS frame — Newton's  
third law for the sign and the hip joint's own SpatialTransform rotation for  
the frame. Without ``--ik`` the hip is plotted as written (femur frame) and the  
panel title says so.

## Contents

- class [`OsimModel`](#osimmodel) — Meshes, offset frames and joint transforms of an .osim — hand-rolled XML so the plot needs no OpenSim install.
  - [`OsimModel.joint_transform`](#osimmodeljoint_transform) — (R, t) child body -> parent body at coordinates `q` (missing = 0).
  - [`OsimModel.joint_neutral`](#osimmodeljoint_neutral) — 
  - [`OsimModel.joint_rotation`](#osimmodeljoint_rotation) — (N, 3, 3) rotation, child-frame vectors -> parent frame, at the coordinate arrays `q` (name -> radians). Axes and order are the joint's own SpatialTransform, not assumed.
  - [`OsimModel.chain_pose`](#osimmodelchain_pose) — (R, t) body `frm` -> body `to` at the pose `q`, walking the joints.
  - [`OsimModel.find_mesh`](#osimmodelfind_mesh) — 
  - [`OsimModel.mesh_faces`](#osimmodelmesh_faces) — Faces of `body`'s display meshes, body coordinates, scaled. `only` filters by filename substring (a tuple = any of them); if it filters everything away the filter is dropped (mesh names vary across model families).
- class [`Style`](#style) — 
- [`read_sto`](#read_sto) — OpenSim storage file -> (names list, (N, C) array).
- [`force_triplets`](#force_triplets) — {joint: (body, frame, [ix, iy, iz])} for every *_on_*_in_*_f{x,y,z}.
- [`euler_xyz`](#euler_xyz) — 
- [`axis_rotation`](#axis_rotation) — 
- [`transform_function`](#transform_function) — A <TransformAxis> function as a plain callable f(q) -> float. Splines are linearly interpolated between their knots — good enough for a background drawing, not for driving a simulation.
- [`read_vtp`](#read_vtp) — Faces of an ASCII vtkPolyData .vtp as a list of (n, 3) arrays.
- [`keep_end`](#keep_end) — Keep the `frac` of a mesh nearest one end of its long axis — the joint end is the part the contact force acts on, so it is the part drawn.
- [`silhouette_outline`](#silhouette_outline) — Outer boundary of 2-D faces as polylines (rasterise, contour at 0.5).
- [`panel_spec`](#panel_spec) — Bones behind each joint kind + the segment that MOVES with the task.
- [`joint_kind`](#joint_kind) — 
- [`joint_side`](#joint_side) — 
- [`panel_bones`](#panel_bones) — Grey silhouette faces for one panel, projected, origin at the joint.
- [`panel_moving`](#panel_moving) — The bone that MOVES within the panel, posed at `q`, projected.
- [`segment_bearing`](#segment_bearing) — Which way the moving segment points at pose `q`, as a bearing (rad).
- [`pose_extremes`](#pose_extremes) — [(coords_dict, angle_deg), ...] at the drive's min, max and start.
- [`hip_to_pelvis`](#hip_to_pelvis) — Reaction ON the femur IN the femur frame -> force ON the acetabulum IN the pelvis frame: Newton's third law + the hip's own rotation matrix.
- [`nice_ceiling`](#nice_ceiling) — 
- [`bone_scale`](#bone_scale) — ONE radial scale shared by every bone in a panel, sized so the widest spans `frac` of the rim — the loop should sit INSIDE the joint.
- [`to_polar`](#to_polar) — 
- [`draw_bone`](#draw_bone) — 
- [`draw_pose`](#draw_pose) — 
- [`draw_rom_arc`](#draw_rom_arc) — (bearing_min, bearing_max, deg_min, deg_max, bearing_at_start).
- [`draw_panel`](#draw_panel) — 
- [`plot_jcf_direction`](#plot_jcf_direction) — Draw the figure. Returns the output path.
- [`main`](#main) — 

<a id="osimmodel"></a>

## class `OsimModel`

```python
OsimModel(path, geometry=None)
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `geometry` | – | `None` |

Meshes, offset frames and joint transforms of an .osim — hand-rolled XML  
so the plot needs no OpenSim install.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L155)</sub>

<a id="osimmodeljoint_transform"></a>

### `OsimModel.joint_transform`

```python
OsimModel.joint_transform(name, q=None)
```

| input | type | default |
|---|---|---|
| `name` | – | required |
| `q` | – | `None` |

(R, t) child body -> parent body at coordinates `q` (missing = 0).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L202)</sub>

<a id="osimmodeljoint_neutral"></a>

### `OsimModel.joint_neutral`

```python
OsimModel.joint_neutral(name)
```

| input | type | default |
|---|---|---|
| `name` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L219)</sub>

<a id="osimmodeljoint_rotation"></a>

### `OsimModel.joint_rotation`

```python
OsimModel.joint_rotation(name, q)
```

| input | type | default |
|---|---|---|
| `name` | – | required |
| `q` | – | required |

(N, 3, 3) rotation, child-frame vectors -> parent frame, at the  
coordinate arrays `q` (name -> radians). Axes and order are the  
joint's own SpatialTransform, not assumed.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L222)</sub>

<a id="osimmodelchain_pose"></a>

### `OsimModel.chain_pose`

```python
OsimModel.chain_pose(frm, to, q=None)
```

| input | type | default |
|---|---|---|
| `frm` | – | required |
| `to` | – | required |
| `q` | – | `None` |

(R, t) body `frm` -> body `to` at the pose `q`, walking the joints.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L236)</sub>

<a id="osimmodelfind_mesh"></a>

### `OsimModel.find_mesh`

```python
OsimModel.find_mesh(name)
```

| input | type | default |
|---|---|---|
| `name` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L258)</sub>

<a id="osimmodelmesh_faces"></a>

### `OsimModel.mesh_faces`

```python
OsimModel.mesh_faces(body, only=None)
```

| input | type | default |
|---|---|---|
| `body` | – | required |
| `only` | – | `None` |

Faces of `body`'s display meshes, body coordinates, scaled.  
`only` filters by filename substring (a tuple = any of them); if it  
filters everything away the filter is dropped (mesh names vary across  
model families).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L266)</sub>

<a id="style"></a>

## class `Style`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L519)</sub>

### `read_sto`

```python
read_sto(path)
```

| input | type | default |
|---|---|---|
| `path` | – | required |

OpenSim storage file -> (names list, (N, C) array).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L55)</sub>

### `force_triplets`

```python
force_triplets(names)
```

| input | type | default |
|---|---|---|
| `names` | – | required |

{joint: (body, frame, [ix, iy, iz])} for every *_on_*_in_*_f{x,y,z}.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L75)</sub>

### `euler_xyz`

```python
euler_xyz(a, b, c)
```

| input | type | default |
|---|---|---|
| `a` | – | required |
| `b` | – | required |
| `c` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L94)</sub>

### `axis_rotation`

```python
axis_rotation(axis, q)
```

| input | type | default |
|---|---|---|
| `axis` | – | required |
| `q` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L102)</sub>

### `transform_function`

```python
transform_function(axis_node)
```

| input | type | default |
|---|---|---|
| `axis_node` | – | required |

A <TransformAxis> function as a plain callable f(q) -> float. Splines  
are linearly interpolated between their knots — good enough for a  
background drawing, not for driving a simulation.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L120)</sub>

### `read_vtp`

```python
read_vtp(path, cache)
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `cache` | – | required |

Faces of an ASCII vtkPolyData .vtp as a list of (n, 3) arrays.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L286)</sub>

### `keep_end`

```python
keep_end(faces, frac, end='proximal', axis=1)
```

| input | type | default |
|---|---|---|
| `faces` | – | required |
| `frac` | – | required |
| `end` | – | `'proximal'` |
| `axis` | – | `1` |

Keep the `frac` of a mesh nearest one end of its long axis — the joint  
end is the part the contact force acts on, so it is the part drawn.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L309)</sub>

### `silhouette_outline`

```python
silhouette_outline(faces, n=160)
```

| input | type | default |
|---|---|---|
| `faces` | – | required |
| `n` | – | `160` |

Outer boundary of 2-D faces as polylines (rasterise, contour at 0.5).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L340)</sub>

### `panel_spec`

```python
panel_spec(kind, side)
```

| input | type | default |
|---|---|---|
| `kind` | – | required |
| `side` | – | required |

Bones behind each joint kind + the segment that MOVES with the task.

`at` says where a bone sits: a joint name moves the panel origin to that  
joint's centre; "chain" brings the body in through the model's own joint  
transforms. `moving` is the neighbouring segment, drawn dotted at the two  
extremes of `drive` when an IK file is given; `axis_sign` points its long  
axis away from the joint.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L380)</sub>

### `joint_kind`

```python
joint_kind(name)
```

| input | type | default |
|---|---|---|
| `name` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L418)</sub>

### `joint_side`

```python
joint_side(name)
```

| input | type | default |
|---|---|---|
| `name` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L426)</sub>

### `panel_bones`

```python
panel_bones(model, joint, frame_body, cols)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `joint` | – | required |
| `frame_body` | – | required |
| `cols` | – | required |

Grey silhouette faces for one panel, projected, origin at the joint.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L430)</sub>

### `panel_moving`

```python
panel_moving(model, joint, frame_body, q, cols)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `joint` | – | required |
| `frame_body` | – | required |
| `q` | – | required |
| `cols` | – | required |

The bone that MOVES within the panel, posed at `q`, projected.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L455)</sub>

### `segment_bearing`

```python
segment_bearing(model, joint, frame_body, q, cols)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `joint` | – | required |
| `frame_body` | – | required |
| `q` | – | required |
| `cols` | – | required |

Which way the moving segment points at pose `q`, as a bearing (rad).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L473)</sub>

### `pose_extremes`

```python
pose_extremes(ik_names, ik_data, degrees, spec)
```

| input | type | default |
|---|---|---|
| `ik_names` | – | required |
| `ik_data` | – | required |
| `degrees` | – | required |
| `spec` | – | required |

[(coords_dict, angle_deg), ...] at the drive's min, max and start.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L483)</sub>

### `hip_to_pelvis`

```python
hip_to_pelvis(model, joint, F, ik_names, ik_data, degrees)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `joint` | – | required |
| `F` | – | required |
| `ik_names` | – | required |
| `ik_data` | – | required |
| `degrees` | – | required |

Reaction ON the femur IN the femur frame -> force ON the acetabulum IN  
the pelvis frame: Newton's third law + the hip's own rotation matrix.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L498)</sub>

### `nice_ceiling`

```python
nice_ceiling(v, steps=(0.25, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 10.0))
```

| input | type | default |
|---|---|---|
| `v` | – | required |
| `steps` | – | `(0.25, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 10.0)` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L526)</sub>

### `bone_scale`

```python
bone_scale(groups, rmax, frac=None)
```

| input | type | default |
|---|---|---|
| `groups` | – | required |
| `rmax` | – | required |
| `frac` | – | `None` |

ONE radial scale shared by every bone in a panel, sized so the widest  
spans `frac` of the rim — the loop should sit INSIDE the joint.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L536)</sub>

### `to_polar`

```python
to_polar(xy, k)
```

| input | type | default |
|---|---|---|
| `xy` | – | required |
| `k` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L548)</sub>

### `draw_bone`

```python
draw_bone(ax, faces, k, color='0.92')
```

| input | type | default |
|---|---|---|
| `ax` | – | required |
| `faces` | – | required |
| `k` | – | required |
| `color` | – | `'0.92'` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L552)</sub>

### `draw_pose`

```python
draw_pose(ax, segs, k, color='0.55')
```

| input | type | default |
|---|---|---|
| `ax` | – | required |
| `segs` | – | required |
| `k` | – | required |
| `color` | – | `'0.55'` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L559)</sub>

### `draw_rom_arc`

```python
draw_rom_arc(ax, rom, rmax, color='0.45', lw=4.0, fs=8)
```

| input | type | default |
|---|---|---|
| `ax` | – | required |
| `rom` | – | required |
| `rmax` | – | required |
| `color` | – | `'0.45'` |
| `lw` | – | `4.0` |
| `fs` | – | `8` |

(bearing_min, bearing_max, deg_min, deg_max, bearing_at_start).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L567)</sub>

### `draw_panel`

```python
draw_panel(
    ax,
    faces,
    ghosts,
    rom,
    curves,
    rmax,
    unit,
    title,
    rlabel,
    rings,
    dirs,
    dir_names
)
```

| input | type | default |
|---|---|---|
| `ax` | – | required |
| `faces` | – | required |
| `ghosts` | – | required |
| `rom` | – | required |
| `curves` | – | required |
| `rmax` | – | required |
| `unit` | – | required |
| `title` | – | required |
| `rlabel` | – | required |
| `rings` | – | required |
| `dirs` | – | required |
| `dir_names` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L590)</sub>

### `plot_jcf_direction`

```python
plot_jcf_direction(
    model,
    jra,
    out='jcf_direction.png',
    joints=None,
    bodyweight=None,
    mass=None,
    plane='sagittal',
    ik=None,
    geometry=None,
    title=None,
    dpi=None
)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `jra` | – | required |
| `out` | – | `'jcf_direction.png'` |
| `joints` | – | `None` |
| `bodyweight` | – | `None` |
| `mass` | – | `None` |
| `plane` | – | `'sagittal'` |
| `ik` | – | `None` |
| `geometry` | – | `None` |
| `title` | – | `None` |
| `dpi` | – | `None` |

Draw the figure. Returns the output path.

model       .osim path (bones + hip frame conversion)  
jra         one .sto path, a list of paths, or {label: path}  
joints      joint names as in the JRA columns (default: hip/knee/ankle  
            joints found in the first file, right side preferred)  
bodyweight  N — radius in body weights; `mass` (kg) is the alternative;  
            neither -> radius in kN  
plane       "sagittal" (SUP/ANT) or "frontal" (SUP/LAT)  
ik          IK .mot of the same trial -> hip re-expressed in the pelvis  
            frame, plus the dotted extreme poses and the ROM arc  
geometry    extra folder(s) to search for .vtp meshes

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L634)</sub>

### `main`

```python
main(argv=None)
```

| input | type | default |
|---|---|---|
| `argv` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/jcf_direction.py#L757)</sub>
