# `bioscout.simulate`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/__init__.py)

Everything ``bioscout simulate`` backs: run a simulation on an existing model.

    opensim.py   the pipeline stages -- IK -> ID -> MA -> SO -> JRA (plus CMC,  
                 RRA, IAA, energetics, body kinematics) -- and the trc/mot/grf/  
                 xml input prep that feeds them  
    ceinms/      CEINMS calibration and execution (binaries under bin/)  
    mrs/         the KU Leuven Muscle Redundancy Solver (`simulate mrs`)  
    gapfill.py   marker gap filling, run before IK needs complete markers  
    mew/         muscle extrapolation web -- Python CEINMS/SO: muscle forces  
                 from a model + kinematics, raised by ID/EMG/calibration  
                 (`it.run(do_mew=True)`, `bioscout simulate mew`,  
                 `python -m bioscout.simulate.mew`)

Model creation and editing live in ``bioscout.model``, not here: that package  
holds ``opensim_base`` (load_model and the OpenSim logger plumbing, which this  
package imports), ``scale/`` (ScaleTool), ``edit/`` (.osim edits) and  
``muscle_optimize`` (Modenese-2015).

Nothing is imported eagerly so ``import bioscout.simulate`` stays light.
