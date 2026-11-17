# `bioscout.model.inspect.model_ma_check`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/model_ma_check.py)

Moment-arm discontinuity check straight from a MODEL and a motion.

Unlike ``moment_arm_motion`` (which QCs already-solved MuscleAnalysis ``.sto``  
files), this drives the ``.osim`` through the trial's joint angles with OpenSim  
and computes the moment arms itself — so a model can be checked BEFORE any  
pipeline stage is run, e.g. right after scaling or after a wrap edit.

The figure is one fig06-style column: one row per muscle group about its  
primary coordinate (hip -> knee -> ankle), moment arms in cm over the task  
cycle, every member muscle drawn, discontinuities marked with an X. Pass  
``dofs=[...]`` instead to inspect coordinates directly — each row then shows  
every muscle spanning that DOF.

    from bioscout.model.inspect.model_ma_check import check_ma_discontinuities  
    check_ma_discontinuities("scaled.osim", "joint_angles.mot")

    python -m bioscout.model.inspect.model_ma_check scaled.osim joint_angles.mot  
    python -m bioscout.model.inspect.model_ma_check scaled.osim ik.mot         --dofs hip_flexion_r knee_angle_r --out qc/

Found the 2026-08 defect this was written for: linearly scaled pelvis wrap  
cylinders make psoas/iliacus flicker 24-31 mm twice per walking cycle.

## Contents

- [`check_ma_discontinuities`](#check_ma_discontinuities) — One-column fig06-style discontinuity check of ``model`` over ``motion``.
- [`main`](#main) — 

### `check_ma_discontinuities`

```python
check_ma_discontinuities(
    model,
    motion,
    out_dir=None,
    side='_r',
    groups=None,
    dofs=None,
    min_jump_mm=1.0,
    step_mm=2.0,
    min_ma_mm=5.0,
    stride=1,
    title=None
)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `motion` | – | required |
| `out_dir` | – | `None` |
| `side` | – | `'_r'` |
| `groups` | – | `None` |
| `dofs` | – | `None` |
| `min_jump_mm` | – | `1.0` |
| `step_mm` | – | `2.0` |
| `min_ma_mm` | – | `5.0` |
| `stride` | – | `1` |
| `title` | – | `None` |

One-column fig06-style discontinuity check of ``model`` over ``motion``.

  
**Parameters**

model : str            ``.osim`` file.  
motion : str           IK ``joint_angles.mot`` (degrees).  
out_dir : str          where the png + csv go (default: next to the model).  
side : str             ``"_r"`` or ``"_l"``, appended to stems.  
groups : list          ``(label, [muscle stems], dof stem)`` rows  
                       (default: the fig06 muscle groups).  
dofs : list[str]       inspect these coordinates instead of groups — each  
                       row shows every muscle spanning the DOF  
                       (peak |MA| >= ``min_ma_mm``).  
min_jump_mm : float    ``detect_discontinuities`` sensitivity.  
step_mm : float        also flag any frame-to-frame change above this.  
stride : int           evaluate every Nth frame (speed).

Returns ``{"figure": png, "table": csv, "flagged": DataFrame}``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/model_ma_check.py#L91)</sub>

### `main`

```python
main(argv=None)
```

| input | type | default |
|---|---|---|
| `argv` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/model_ma_check.py#L212)</sub>
