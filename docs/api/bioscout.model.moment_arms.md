# `bioscout.model.moment_arms`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/__init__.py)

bioscout.model.moment_arms  
===========================

Adjust a muscle's moment arm on an OpenSim model, and derive the amount from  
measured muscle volume rather than a guessed factor.

Why wrap radii rather than moving attachment points: in OpenSim the wrap  
surface *is* the geometric stand-in for muscle bulk — the path is held off the  
bone by the cylinder, so its radius sets how far the line of action sits from  
the joint axis. Growing it is the mechanism by which a bigger muscle produces a  
bigger moment arm, it preserves the curve's shape because the path still wraps,  
and the change in where the path engages the surface moves the peak along the  
coordinate on its own. Translating path points (``paths``) models a different  
anatomical change — the attachment moving — and is the fallback for muscles  
with no wrap on their path.

    bioscout --change-moment-arms          # guided  
    python -m bioscout.model.moment_arms

    from bioscout.model.moment_arms import apply_offset, measure_volumes  
    apply_offset(model, out, "glmax1_r", "hip_adduction_r", offset_mm=5)

Layout — only ``core`` needs OpenSim, so everything else is testable without it:

    wraps.py    read/edit wrap radii            (pure XML)  
    paths.py    translate/rotate path points    (pure XML)  
    volumes.py  MRI mask -> radius factor       (needs nibabel)  
    solve.py    bracket + bisect on a callable  (pure numpy)  
    core.py     the OpenSim sweeps              (needs opensim)  
    inspection.py  before/after check of an edit (needs opensim)  
    cli.py      the guided prompt

## Available as `bioscout.model.moment_arms.<name>`

- [`bioscout.model.moment_arms.read_path_points`](bioscout.model.moment_arms.paths.md#read_path_points) — from `bioscout.model.moment_arms.paths`
- [`bioscout.model.moment_arms.rotate_path_points`](bioscout.model.moment_arms.paths.md#rotate_path_points) — from `bioscout.model.moment_arms.paths`
- [`bioscout.model.moment_arms.translate_path_points`](bioscout.model.moment_arms.paths.md#translate_path_points) — from `bioscout.model.moment_arms.paths`
- [`bioscout.model.moment_arms.solve_radius_for_offset`](bioscout.model.moment_arms.solve.md#solve_radius_for_offset) — from `bioscout.model.moment_arms.solve`
- [`bioscout.model.moment_arms.DEFAULT_MASK_MAP`](bioscout.model.moment_arms.volumes.md#default_mask_map) — from `bioscout.model.moment_arms.volumes`
- [`bioscout.model.moment_arms.measure_volume`](bioscout.model.moment_arms.volumes.md#measure_volume) — from `bioscout.model.moment_arms.volumes`
- [`bioscout.model.moment_arms.measure_volumes`](bioscout.model.moment_arms.volumes.md#measure_volumes) — from `bioscout.model.moment_arms.volumes`
- [`bioscout.model.moment_arms.radius_factor_from_volumes`](bioscout.model.moment_arms.volumes.md#radius_factor_from_volumes) — from `bioscout.model.moment_arms.volumes`
- [`bioscout.model.moment_arms.read_wraps`](bioscout.model.moment_arms.wraps.md#read_wraps) — from `bioscout.model.moment_arms.wraps`
- [`bioscout.model.moment_arms.scale_wrap_radii`](bioscout.model.moment_arms.wraps.md#scale_wrap_radii) — from `bioscout.model.moment_arms.wraps`
- [`bioscout.model.moment_arms.set_wrap_radii`](bioscout.model.moment_arms.wraps.md#set_wrap_radii) — from `bioscout.model.moment_arms.wraps`
