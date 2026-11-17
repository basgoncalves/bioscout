# `bioscout.simulate.mew`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/__init__.py)

mew (muscle extrapolation web) -- a Python-native, always-answers muscle force estimator.

CEINMS's hybrid EMG-informed solve, rebuilt in numpy/scipy, with a tier ladder  
so it returns forces from as little as height + mass + a model + kinematics, and  
gets better as GRF, EMG and subject calibration are added.

    from bioscout.simulate.mew import Mew  
    ma = Mew(model="Rajagopal2015.osim", height=1.81, mass=78,  
             kinematics="joint_angles.mot")  
    res = ma.run()  
    print(res.summary())          # tier, confidence, moment residual  
    res.write_sto("ceinms/Optimised/MuscleForces.sto")

See DESIGN.md for the architecture, the tier ladder and the bioscout  
integration plan.

Import discipline: this module and everything it imports at module level depend  
on numpy/scipy only. OpenSim, torch and bioscout are optional and confined to  
``geometry``, ``ml`` and ``bioscout_adapter``.

## Available as `bioscout.simulate.mew.<name>`

- [`bioscout.simulate.mew.Tier`](bioscout.simulate.mew.types.md#tier) — from `bioscout.simulate.mew.types`
- [`bioscout.simulate.mew.SubjectSpec`](bioscout.simulate.mew.types.md#subjectspec) — from `bioscout.simulate.mew.types`
- [`bioscout.simulate.mew.TrialInputs`](bioscout.simulate.mew.types.md#trialinputs) — from `bioscout.simulate.mew.types`
- [`bioscout.simulate.mew.MuscleForceResult`](bioscout.simulate.mew.types.md#muscleforceresult) — from `bioscout.simulate.mew.types`
- [`bioscout.simulate.mew.Provenance`](bioscout.simulate.mew.types.md#provenance) — from `bioscout.simulate.mew.types`
- [`bioscout.simulate.mew.MuscleParameters`](bioscout.simulate.mew.mtu.md#muscleparameters) — from `bioscout.simulate.mew.mtu`
- [`bioscout.simulate.mew.scale_parameters`](bioscout.simulate.mew.mtu.md#scale_parameters) — from `bioscout.simulate.mew.mtu`
- [`bioscout.simulate.mew.build_mtu`](bioscout.simulate.mew.mtu.md#build_mtu) — from `bioscout.simulate.mew.mtu`
- [`bioscout.simulate.mew.SolverWeights`](bioscout.simulate.mew.solver.md#solverweights) — from `bioscout.simulate.mew.solver`
- [`bioscout.simulate.mew.MODE_PRESETS`](bioscout.simulate.mew.solver.md#mode_presets) — from `bioscout.simulate.mew.solver`
- [`bioscout.simulate.mew.solve_trial`](bioscout.simulate.mew.solver.md#solve_trial) — from `bioscout.simulate.mew.solver`
- [`bioscout.simulate.mew.Mew`](bioscout.simulate.mew.analyser.md#mew) — from `bioscout.simulate.mew.analyser`
- [`bioscout.simulate.mew.analyse_trial`](bioscout.simulate.mew.pipeline.md#analyse_trial) — from `bioscout.simulate.mew.pipeline`
- [`bioscout.simulate.mew.read_storage`](bioscout.simulate.mew.io_ports.md#read_storage) — from `bioscout.simulate.mew.io_ports`
- [`bioscout.simulate.mew.write_sto`](bioscout.simulate.mew.io_ports.md#write_sto) — from `bioscout.simulate.mew.io_ports`
- [`bioscout.simulate.mew.contact_force_magnitude`](bioscout.simulate.mew.jcf.md#contact_force_magnitude) — from `bioscout.simulate.mew.jcf`
