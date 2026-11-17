# `bioscout.simulate.mrs`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mrs/__init__.py)

bioscout.simulate.mrs -- the KU Leuven Muscle Redundancy Solver, driven from BioScout.

    from bioscout.simulate.mrs import MRSConfig, run  
    cfg = MRSConfig(model_path=..., ik_files=[...], id_files=[...],  
                    time=[0.5, 1.8], dof_names=["hip_flexion_r", "knee_angle_r"],  
                    out_path=".../mrs")  
    run(cfg)

BioScout writes mrs_config.json, MATLAB runs solveMuscleRedundancy through  
run_mrs.m, and the resulting MRS_Results.mat is exported to OpenSim .sto files.  
The toolbox itself is NOT vendored: clone it and point BIOSCOUT_MRS_DIR at it.

## Available as `bioscout.simulate.mrs.<name>`

- [`bioscout.simulate.mrs.MRSConfig`](bioscout.simulate.mrs.config.md#mrsconfig) — from `bioscout.simulate.mrs.config`
- [`bioscout.simulate.mrs.run`](bioscout.simulate.mrs.runner.md#run) — from `bioscout.simulate.mrs.runner`
- [`bioscout.simulate.mrs.check`](bioscout.simulate.mrs.runner.md#check) — from `bioscout.simulate.mrs.runner`
- [`bioscout.simulate.mrs.find_matlab`](bioscout.simulate.mrs.runner.md#find_matlab) — from `bioscout.simulate.mrs.runner`
- [`bioscout.simulate.mrs.find_mrs_dir`](bioscout.simulate.mrs.runner.md#find_mrs_dir) — from `bioscout.simulate.mrs.runner`
- [`bioscout.simulate.mrs.DRIVER`](bioscout.simulate.mrs.runner.md#driver) — from `bioscout.simulate.mrs.runner`
- [`bioscout.simulate.mrs.export`](bioscout.simulate.mrs.io.md#export) — from `bioscout.simulate.mrs.io`
- [`bioscout.simulate.mrs.write_sto`](bioscout.simulate.mrs.io.md#write_sto) — from `bioscout.simulate.mrs.io`
