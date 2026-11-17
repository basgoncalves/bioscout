# `bioscout.model.inspect.moment_arm_motion`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/moment_arm_motion.py)

Moment-arm QC over the ACTUAL TRIAL MOTION (not a ROM sweep).

Reads the OpenSim MuscleAnalysis moment-arm ``.sto`` files (already produced by the  
muscle-analysis stage — no OpenSim call, no literature) plus the trial's IK joint  
angles, and for every DOF plots each spanning muscle's moment arm against the JOINT  
ANGLE the motion actually visited, flagging discontinuities (wrap-point glitches)  
that occurred DURING the movement.

This is the motion-driven counterpart to the ``validate``/``inspect`` model checks:  
those sweep each coordinate over its full range to compare against literature; this  
one only asks "are the moment arms that drove ID/SO/CEINMS smooth over THIS task?".  
Fast, per-trial, standalone.

    from bioscout.model.inspect.moment_arm_motion import inspect_moment_arms_over_motion  
    inspect_moment_arms_over_motion("…/muscle_analysis",  
                                    "…/external_biomechanics/joint_angles.mot")

## Contents

- [`inspect_moment_arms_over_motion`](#inspect_moment_arms_over_motion) — QC the model's moment arms over the trial motion.

### `inspect_moment_arms_over_motion`

```python
inspect_moment_arms_over_motion(
    ma_dir,
    ik_mot,
    out_dir=None,
    dofs=None,
    side='_r',
    min_ma_mm=3.0,
    min_jump_mm=1.0,
    max_muscles=14,
    title=None
)
```

| input | type | default |
|---|---|---|
| `ma_dir` | – | required |
| `ik_mot` | – | required |
| `out_dir` | – | `None` |
| `dofs` | – | `None` |
| `side` | – | `'_r'` |
| `min_ma_mm` | – | `3.0` |
| `min_jump_mm` | – | `1.0` |
| `max_muscles` | – | `14` |
| `title` | – | `None` |

QC the model's moment arms over the trial motion.

  
**Parameters**

ma_dir : str  
    Folder holding ``_MuscleAnalysis_MomentArm_<dof>.sto`` (the trial's  
    ``muscle_analysis/``).  
ik_mot : str  
    The trial's IK ``joint_angles.mot`` — supplies the joint-angle x-axis.  
out_dir : str, optional  
    Where to write ``moment_arm_motion_check.png`` (default: ``ma_dir``).  
dofs : list[str], optional  
    DOF stems (no side) to inspect, e.g. ``["hip_flexion", "knee_angle"]``.  
    Default: the standard lower-limb set present on disk.  
side : str  
    ``"_r"`` or ``"_l"``.  
min_ma_mm : float  
    Only inspect muscles whose peak |moment arm| exceeds this (mm) for a DOF —  
    i.e. the muscles that actually span it.  
min_jump_mm : float  
    Discontinuity sensitivity (mm). Lower = more sensitive.  
max_muscles : int  
    Cap on curves drawn per panel (largest |MA| first); all spanning muscles are  
    still checked for discontinuities.

  
**Returns**

dict  
    ``{"figure": <png path or None>, "flagged": [(dof, muscle, n_jumps), ...],  
       "dofs": [<dof>, ...]}``.

  
**Notes**

A near-static DOF (small angle range) shows its curves as a near-vertical smear —  
expected, not a defect: the joint simply didn't move much over this window.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/moment_arm_motion.py#L53)</sub>
