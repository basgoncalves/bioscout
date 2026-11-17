# `bioscout.model.inspect.run_moment_arm_inspection`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/run_moment_arm_inspection.py)

Adjust the moment arms of an OpenSim model, plot before/after, and validate vs literature.

EDIT THE `CONFIG` BLOCK BELOW, then run:

    python run_moment_arm_inspection.py

Outputs (all under <model_dir>/validation/<model>/):  
  - corrected model  <model_dir>/<model>_modWO.osim   (next to the ORIGINAL model)  
  - momentarm_<coord>.png / length_<coord>.png  before vs after grids  
        (literature bands overlaid on hip-flexion moment-arm panels where available)  
  - validation_moment_arms.png + validation_rmse.csv   full literature comparison

Coordinate-SWEEP (motion-free) tool. For motion-driven checking against a .mot,  
use run_muscle_checker.py.

## Contents

- [`main`](#main) — 

### `main`

```python
main(argv=None)
```

| input | type | default |
|---|---|---|
| `argv` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/run_moment_arm_inspection.py#L85)</sub>
