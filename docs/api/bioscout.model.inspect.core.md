# `bioscout.model.inspect.core`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/core.py)

muscle_inspect.core -- compatibility aggregator.

The muscle-length/strength side of this package (ported from the standalone  
MuscleLengthsChecker) imports its shared helpers from ``muscle_inspect.core``.  
bioscout keeps those helpers split across small modules  
(``geometry``/``discontinuity``/``logutil``); this module simply re-exports them  
under the ``core`` name so the ported files (``strength``,  
``muscle_length_validation``) work unchanged, and adds the one helper bioscout  
did not already have: :func:`load_function_matrix`.

## Contents

- [`load_function_matrix`](#load_function_matrix) — Parse the muscle-centric ``muscle_functions.csv`` incidence matrix.

### `load_function_matrix`

```python
load_function_matrix(path)
```

| input | type | default |
|---|---|---|
| `path` | – | required |

Parse the muscle-centric ``muscle_functions.csv`` incidence matrix.

Columns: model_muscle, literature_muscle, then one JOINT ACTION per column (0/1).  
Returns ``(lit_map, action_map)``:  
  lit_map    : {literature_muscle: [model_muscle, ...]}  (aggregation for moment-arm/fibre validation)  
  action_map : {joint_action:      [model_muscle, ...]}  (agonist groups for strength validation)  
Model muscle names are WITHOUT side. Returns ({}, {}) if the file is absent or  
is not a matrix (first column != 'model_muscle').

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/core.py#L35)</sub>
