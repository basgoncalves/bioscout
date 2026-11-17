# `bioscout.simulate.ceinms`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/__init__.py)

bioscout.simulate.ceinms — the CEINMS toolbox: Python helpers AND the binaries.

    from bioscout.simulate import ceinms  
    ceinms.create_ceinms_cfg(...)          # configs.py  
    ceinms.executable(...)                 # commands.py  
    ceinms.ExecutionMode(trial).run(fn)    # modes.py  
    ceinms.plot_ceinms_muscle_forces(...)  # plot.py

WHY THIS IS A PACKAGE NOW  
    It used to be a 331 MB directory of .exe/.dll files with a single  
    `__init__.py` whose only job was to work around a name collision: a  
    *package* shadows a same-named *module*, so `import ceinms` reached the  
    binaries and missed the helpers in the sibling `utils/ceinms.py`. That shim  
    loaded the .py by file path inside `try/except Exception` and fell back to  
    "binary package only" on any failure — so a missing OpenSim DLL silently  
    removed every helper instead of raising.

    There is now one `ceinms`, and it is this package. The helpers are real  
    submodules; the binaries live under `bin/`. Nothing is loaded by file path  
    and nothing is swallowed.

LAYOUT  
    shared.py    header, the live `settings` proxy, small shared helpers  
    configs.py   every CEINMS XML builder (model, generator, cfgs, setups)  
    commands.py  running the executables (terminal, calibrate, execute, loop,  
                 optimise)  
    modes.py     execution MODES — how many solves, and what the result IS  
                 (single / bounds / full_loop / lcurve / optimise)  
    plot.py      figures from CEINMS output  
    bin/         CEINMS.exe, CEINMSoptimise.exe, ceinms-nn-calibrate.exe, DLLs

    `modes.py` deliberately imports only the standard library. Mode SELECTION  
    must not depend on OpenSim importing: if it did, a missing DLL would turn a  
    three-arm `bounds` run into a one-arm run with no error — a config option  
    silently ignored, which is worse than one that fails.

        from bioscout.simulate.ceinms.modes import ExecutionMode   # no OpenSim

## Available as `bioscout.simulate.ceinms.<name>`

- [`bioscout.simulate.ceinms.ExecutionMode`](bioscout.simulate.ceinms.modes.md#executionmode) — from `bioscout.simulate.ceinms.modes`
- [`bioscout.simulate.ceinms.ModeError`](bioscout.simulate.ceinms.modes.md#modeerror) — from `bioscout.simulate.ceinms.modes`
- [`bioscout.simulate.ceinms.EXECUTION_MODES`](bioscout.simulate.ceinms.modes.md#modes) — from `bioscout.simulate.ceinms.modes`
- [`bioscout.simulate.ceinms.aggregate_band`](bioscout.simulate.ceinms.modes.md#aggregate_band) — from `bioscout.simulate.ceinms.modes`
- [`bioscout.simulate.ceinms.lcurve_knee`](bioscout.simulate.ceinms.modes.md#lcurve_knee) — from `bioscout.simulate.ceinms.modes`
- [`bioscout.simulate.ceinms.resolve_mode`](bioscout.simulate.ceinms.modes.md#resolve) — from `bioscout.simulate.ceinms.modes`
- [`bioscout.simulate.ceinms.upWorkingDirectory`](bioscout.simulate.ceinms.shared.md#upworkingdirectory) — from `bioscout.simulate.ceinms.shared`
- [`bioscout.simulate.ceinms.check_input_times`](bioscout.simulate.ceinms.shared.md#check_input_times) — from `bioscout.simulate.ceinms.shared`
- [`bioscout.simulate.ceinms.abg_base_name`](bioscout.simulate.ceinms.shared.md#abg_base_name) — from `bioscout.simulate.ceinms.shared`
- [`bioscout.simulate.ceinms.abg_from_name`](bioscout.simulate.ceinms.shared.md#abg_from_name) — from `bioscout.simulate.ceinms.shared`
- [`bioscout.simulate.ceinms.create_ceinms_model`](bioscout.simulate.ceinms.configs.md#create_ceinms_model) — from `bioscout.simulate.ceinms.configs`
- [`bioscout.simulate.ceinms.create_excitation_generator`](bioscout.simulate.ceinms.configs.md#create_excitation_generator) — from `bioscout.simulate.ceinms.configs`
- [`bioscout.simulate.ceinms.is_optimiser_key`](bioscout.simulate.ceinms.configs.md#is_optimiser_key) — from `bioscout.simulate.ceinms.configs`
- [`bioscout.simulate.ceinms.calibration_optimiser_settings`](bioscout.simulate.ceinms.configs.md#calibration_optimiser_settings) — from `bioscout.simulate.ceinms.configs`
- [`bioscout.simulate.ceinms.calibration_param_ranges`](bioscout.simulate.ceinms.configs.md#calibration_param_ranges) — from `bioscout.simulate.ceinms.configs`
- [`bioscout.simulate.ceinms.create_calibrationCfg`](bioscout.simulate.ceinms.configs.md#create_calibrationcfg) — from `bioscout.simulate.ceinms.configs`
- [`bioscout.simulate.ceinms.create_calibrationSetupXML`](bioscout.simulate.ceinms.configs.md#create_calibrationsetupxml) — from `bioscout.simulate.ceinms.configs`
- [`bioscout.simulate.ceinms.create_input_data`](bioscout.simulate.ceinms.configs.md#create_input_data) — from `bioscout.simulate.ceinms.configs`
- [`bioscout.simulate.ceinms.create_ceinms_cfg`](bioscout.simulate.ceinms.configs.md#create_ceinms_cfg) — from `bioscout.simulate.ceinms.configs`
- [`bioscout.simulate.ceinms.replace_ceinms_cfg_parameter`](bioscout.simulate.ceinms.configs.md#replace_ceinms_cfg_parameter) — from `bioscout.simulate.ceinms.configs`
- [`bioscout.simulate.ceinms.create_optimise_setupFiles`](bioscout.simulate.ceinms.configs.md#create_optimise_setupfiles) — from `bioscout.simulate.ceinms.configs`
- [`bioscout.simulate.ceinms.ceinms_terminal`](bioscout.simulate.ceinms.commands.md#ceinms_terminal) — from `bioscout.simulate.ceinms.commands`
- [`bioscout.simulate.ceinms.calibrate`](bioscout.simulate.ceinms.commands.md#calibrate) — from `bioscout.simulate.ceinms.commands`
- [`bioscout.simulate.ceinms.calibrate_synergy_compare`](bioscout.simulate.ceinms.commands.md#calibrate_synergy_compare) — from `bioscout.simulate.ceinms.commands`
- [`bioscout.simulate.ceinms.executable`](bioscout.simulate.ceinms.commands.md#executable) — from `bioscout.simulate.ceinms.commands`
- [`bioscout.simulate.ceinms.executable_loop`](bioscout.simulate.ceinms.commands.md#executable_loop) — from `bioscout.simulate.ceinms.commands`
- [`bioscout.simulate.ceinms.executable_loop_summarise_results`](bioscout.simulate.ceinms.commands.md#executable_loop_summarise_results) — from `bioscout.simulate.ceinms.commands`
- [`bioscout.simulate.ceinms.optimise`](bioscout.simulate.ceinms.commands.md#optimise) — from `bioscout.simulate.ceinms.commands`
- [`bioscout.simulate.ceinms.plot_loop_results`](bioscout.simulate.ceinms.plot.md#plot_loop_results) — from `bioscout.simulate.ceinms.plot`
- [`bioscout.simulate.ceinms.plot_ceinms_model_parameters`](bioscout.simulate.ceinms.plot.md#plot_ceinms_model_parameters) — from `bioscout.simulate.ceinms.plot`
- [`bioscout.simulate.ceinms.plot_compare_ceinms_models`](bioscout.simulate.ceinms.plot.md#plot_compare_ceinms_models) — from `bioscout.simulate.ceinms.plot`
- [`bioscout.simulate.ceinms.plot_moments_calibration_results`](bioscout.simulate.ceinms.plot.md#plot_moments_calibration_results) — from `bioscout.simulate.ceinms.plot`
- [`bioscout.simulate.ceinms.plot_ceinms_calibration_results`](bioscout.simulate.ceinms.plot.md#plot_ceinms_calibration_results) — from `bioscout.simulate.ceinms.plot`
- [`bioscout.simulate.ceinms.plot_optimisation_results`](bioscout.simulate.ceinms.plot.md#plot_optimisation_results) — from `bioscout.simulate.ceinms.plot`
- [`bioscout.simulate.ceinms.plot_experimental_vs_ceinms`](bioscout.simulate.ceinms.plot.md#plot_experimental_vs_ceinms) — from `bioscout.simulate.ceinms.plot`
- [`bioscout.simulate.ceinms.plot_ceinms_muscle_forces`](bioscout.simulate.ceinms.plot.md#plot_ceinms_muscle_forces) — from `bioscout.simulate.ceinms.plot`
- [`bioscout.simulate.ceinms.plot_calibration_parameters`](bioscout.simulate.ceinms.plot.md#plot_calibration_parameters) — from `bioscout.simulate.ceinms.plot`
- [`bioscout.simulate.ceinms.plot_ceinms_summary`](bioscout.simulate.ceinms.plot.md#plot_ceinms_summary) — from `bioscout.simulate.ceinms.plot`
- [`bioscout.simulate.ceinms.shared`](bioscout.simulate.ceinms.md#shared) — from `bioscout.simulate.ceinms`
- [`bioscout.simulate.ceinms.commands`](bioscout.simulate.ceinms.md#commands) — from `bioscout.simulate.ceinms`
- [`bioscout.simulate.ceinms.plot`](bioscout.simulate.ceinms.md#plot) — from `bioscout.simulate.ceinms`
- [`bioscout.simulate.ceinms.modes`](bioscout.simulate.ceinms.md#modes) — from `bioscout.simulate.ceinms`
- [`bioscout.simulate.ceinms.configs`](bioscout.simulate.ceinms.md#configs) — from `bioscout.simulate.ceinms`
