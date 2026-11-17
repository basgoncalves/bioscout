# `bioscout.model.muscle_optimize`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/muscle_optimize.py)

The Modenese (2015) muscle-parameter optimiser.

Its own cluster: given a reference model and a target (scaled) model, it  
rescales optimal fibre length / tendon slack length so the target reproduces  
the reference's normalised operating range.

Split out of the old ``bioscout/utils/openSim.py`` (docs/RESTRUCTURE_PLAN.md,  
stage 6) -- the code is unchanged, only its address.

## Contents

- [`mean_squared_error`](#mean_squared_error) — Local RMSE/MSE helper (avoids sklearn version differences over the removed `squared=` kwarg). Returns RMSE when squared=False.
- [`muscle_optimimizer_Modenese2015`](#muscle_optimimizer_modenese2015) — Optimize muscle parameters in an OpenSim model using the Modenese 2015 method.
- [`optimMuscleParams`](#optimmuscleparams) — 
- [`plot_optimization_results`](#plot_optimization_results) — 
- [`optimize_moment_arms`](#optimize_moment_arms) — Optimize muscle parameters in the target model to match the moment arms of the reference model.

### `mean_squared_error`

```python
mean_squared_error(y_true, y_pred, squared=True)
```

| input | type | default |
|---|---|---|
| `y_true` | – | required |
| `y_pred` | – | required |
| `squared` | – | `True` |

Local RMSE/MSE helper (avoids sklearn version differences over the  
removed `squared=` kwarg). Returns RMSE when squared=False.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/muscle_optimize.py#L31)</sub>

### `muscle_optimimizer_Modenese2015`

```python
muscle_optimimizer_Modenese2015(
    osim_model_path=None,
    save_path=None,
    ref_model_path=None,
    N_eval=10,
    log_folder=None
)
```

| input | type | default |
|---|---|---|
| `osim_model_path` | – | `None` |
| `save_path` | – | `None` |
| `ref_model_path` | – | `None` |
| `N_eval` | – | `10` |
| `log_folder` | – | `None` |

Optimize muscle parameters in an OpenSim model using the Modenese 2015 method.

  
**Args**

    osim_model_path (str): Path to the TARGET (e.g. scaled) .osim model whose  
        muscle optimal-fiber-length / tendon-slack-length will be optimised.  
    save_path (str, optional): Where to write the optimised model. Defaults to  
        '<target>_opt_N<N_eval>.osim'.  
    ref_model_path (str, optional): Reference (template/generic) model whose  
        muscle operating range is preserved. Defaults to the target model.  
    N_eval (int): Sampling points per spanned coordinate (default 10 -> _N10).  
    log_folder (str, optional): Folder for the per-muscle optimisation log.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/muscle_optimize.py#L37)</sub>

### `optimMuscleParams`

```python
optimMuscleParams(osimModel_ref_filepath, osimModel_targ_filepath, N_eval, log_folder)
```

| input | type | default |
|---|---|---|
| `osimModel_ref_filepath` | – | required |
| `osimModel_targ_filepath` | – | required |
| `N_eval` | – | required |
| `log_folder` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/muscle_optimize.py#L113)</sub>

### `plot_optimization_results`

```python
plot_optimization_results(intial_model_path, optimised_model_path)
```

| input | type | default |
|---|---|---|
| `intial_model_path` | – | required |
| `optimised_model_path` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/muscle_optimize.py#L366)</sub>

### `optimize_moment_arms`

```python
optimize_moment_arms(ref_model_path=None, target_model_path=None)
```

| input | type | default |
|---|---|---|
| `ref_model_path` | – | `None` |
| `target_model_path` | – | `None` |

Optimize muscle parameters in the target model to match the moment arms of the reference model.

NOT FINNISED!!!

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/muscle_optimize.py#L468)</sub>
