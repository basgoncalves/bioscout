# `bioscout.model.inspect`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/__init__.py)

muscle_inspect

A small, headless Python toolkit (ported from the MATLAB MuscleLengthsChecker  
pipeline) to check an OpenSim model's muscle geometry and properties against the  
literature, mirroring how the joint-contact-force overlay validates JRA results:

  1. detect muscle path points that sit *inside* wrap cylinders and project them  
     back out -- the geometry error that produces non-physiological / discontinuous  
     moment arms in scaled or warped OpenSim models,  
  2. sweep each joint coordinate over its range of motion and plot moment arms and  
     muscle lengths *before vs after* the correction, so the fix can be inspected  
     visually,  
  3. validate the model's MOMENT ARMS and MUSCLE ARCHITECTURE (fascicle length /  
     pennation) against digitized literature bands  (``muscle_length_validation``), and  
  4. validate joint STRENGTH -- isometric and isokinetic peak moments -- against  
     literature MVC bands  (``strength``).

Requires the official OpenSim Python package (`import opensim`) at run time.  
The pure-math helpers in `geometry` and `discontinuity` do not need OpenSim and  
are unit-testable on their own.

## Available as `bioscout.model.inspect.<name>`

- [`bioscout.model.inspect.euler_xyz_to_rotation_matrix`](bioscout.model.inspect.geometry.md#euler_xyz_to_rotation_matrix) — from `bioscout.model.inspect.geometry`
- [`bioscout.model.inspect.project_point_outside_cylinder`](bioscout.model.inspect.geometry.md#project_point_outside_cylinder) — from `bioscout.model.inspect.geometry`
- [`bioscout.model.inspect.radial_distance`](bioscout.model.inspect.geometry.md#radial_distance) — from `bioscout.model.inspect.geometry`
- [`bioscout.model.inspect.detect_discontinuities`](bioscout.model.inspect.discontinuity.md#detect_discontinuities) — from `bioscout.model.inspect.discontinuity`
- [`bioscout.model.inspect.mad`](bioscout.model.inspect.discontinuity.md#mad) — from `bioscout.model.inspect.discontinuity`
- [`bioscout.model.inspect.load_function_matrix`](bioscout.model.inspect.core.md#load_function_matrix) — from `bioscout.model.inspect.core`
- [`bioscout.model.inspect.LITERATURE_MOMENT_ARMS_CSV`](bioscout.model.inspect.paths.md#literature_moment_arms_csv) — from `bioscout.model.inspect.paths`
- [`bioscout.model.inspect.LITERATURE_CURVES_CSV`](bioscout.model.inspect.paths.md#literature_curves_csv) — from `bioscout.model.inspect.paths`
- [`bioscout.model.inspect.LITERATURE_MANIFEST_JSON`](bioscout.model.inspect.paths.md#literature_manifest_json) — from `bioscout.model.inspect.paths`
- [`bioscout.model.inspect.resolve_literature_csv`](bioscout.model.inspect.paths.md#resolve_literature_csv) — from `bioscout.model.inspect.paths`
- [`bioscout.model.inspect.literature_jcf`](bioscout.model.inspect.md#literature_jcf) — from `bioscout.model.inspect`
- [`bioscout.model.inspect.moment_arm_motion`](bioscout.model.inspect.md#moment_arm_motion) — from `bioscout.model.inspect`
- [`bioscout.model.inspect.inspect_moment_arms_over_motion`](bioscout.model.inspect.moment_arm_motion.md#inspect_moment_arms_over_motion) — from `bioscout.model.inspect.moment_arm_motion`
- [`bioscout.model.inspect.model_ma_check`](bioscout.model.inspect.md#model_ma_check) — from `bioscout.model.inspect`
- [`bioscout.model.inspect.check_ma_discontinuities`](bioscout.model.inspect.model_ma_check.md#check_ma_discontinuities) — from `bioscout.model.inspect.model_ma_check`
