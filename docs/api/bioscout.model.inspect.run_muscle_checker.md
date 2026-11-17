# `bioscout.model.inspect.run_muscle_checker`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/run_muscle_checker.py)

run_muscle_checker.py  --  motion-driven muscle-path checker (matches MATLAB muscleChecker)

Inputs: an OpenSim model + one or more kinematics (.mot) files.  
Edit the CONFIG block, then run:

    python run_muscle_checker.py

  
**Outputs**

  - corrected model  <model_dir>/<model>_modWO.osim      (next to the ORIGINAL model)  
  - log              <model_dir>/<model>_modWO_log.txt    (next to the ORIGINAL model)  
  - figures          <model_dir>/validation/<model>/

## Contents

- [`main`](#main) — 

### `main`

```python
main()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/run_muscle_checker.py#L42)</sub>
