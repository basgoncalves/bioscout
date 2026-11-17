# `bioscout.simulate.ceinms.configs`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/configs.py)

bioscout.simulate.ceinms.configs — Builders for every CEINMS XML: the subject model, the excitation  
generator, calibration cfg/setup, input data, and the execution and  
optimise configurations.

Split out of the former flat `utils/ceinms.py`; see the package  
__init__ for why. The shared header (imports, the live `settings`  
proxy) comes from `.shared`.

## Contents

- [`create_ceinms_model`](#create_ceinms_model) — Create a CEINMS subject XML file with muscle parameters extracted from the OpenSim model.
- [`create_excitation_generator`](#create_excitation_generator) — Create an excitation mapping from OpenSim model muscles to EMG data.
- [`is_optimiser_key`](#is_optimiser_key) — True when `key` configures the SEARCH rather than a parameter's bounds.
- [`calibration_optimiser_settings`](#calibration_optimiser_settings) — -> ``{element: value}`` for calibrationCfg.xml's ``<optimiser>`` block.
- [`calibration_param_ranges`](#calibration_param_ranges) — -> {parameter: "min max"} for calibrationCfg.xml.
- [`create_calibrationCfg`](#create_calibrationcfg) — Create a CEINMS calibration XML configuration from input parameters.
- [`create_calibrationSetupXML`](#create_calibrationsetupxml) — 
- [`create_input_data`](#create_input_data) — 
- [`create_ceinms_cfg`](#create_ceinms_cfg) — 
- [`replace_ceinms_cfg_parameter`](#replace_ceinms_cfg_parameter) — 
- [`create_optimise_setupFiles`](#create_optimise_setupfiles) — create CEINMS setup and configuration XML files for optimisation

### `create_ceinms_model`

```python
create_ceinms_model(osimModelPath=None, outputCEINMSModelPath=None, DOFs: list = None)
```

| input | type | default |
|---|---|---|
| `osimModelPath` | – | `None` |
| `outputCEINMSModelPath` | – | `None` |
| `DOFs` | list | `None` |

Create a CEINMS subject XML file with muscle parameters extracted from the OpenSim model.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/configs.py#L12)</sub>

### `create_excitation_generator`

```python
create_excitation_generator(
    osim_model_path=None,
    emg_path=None,
    save_path=None,
    mapping=None
)
```

| input | type | default |
|---|---|---|
| `osim_model_path` | – | `None` |
| `emg_path` | – | `None` |
| `save_path` | – | `None` |
| `mapping` | – | `None` |

Create an excitation mapping from OpenSim model muscles to EMG data.

  
**Args**

    osim_model (osim.Model): The OpenSim model.  
    emg_path (str): Path to the EMG data file.  
    

**Returns**

    dict: A dictionary mapping muscle names to EMG labels.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/configs.py#L156)</sub>

### `is_optimiser_key`

```python
is_optimiser_key(key) -> bool
```

| input | type | default |
|---|---|---|
| `key` | – | required |

**returns** `bool`

True when `key` configures the SEARCH rather than a parameter's bounds.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/configs.py#L316)</sub>

### `calibration_optimiser_settings`

```python
calibration_optimiser_settings(params=None, params_override=None)
```

| input | type | default |
|---|---|---|
| `params` | – | `None` |
| `params_override` | – | `None` |

-> ``{element: value}`` for calibrationCfg.xml's ``<optimiser>`` block.

Precedence is :func:`calibration_param_ranges`'s exactly: `params_override`  
(this ITERATION's `calibration:` block in session.yaml) beats settings.py,  
which beats the built-in default. A partial override changes only what it  
names, so ``{"learningRate": 0.005}`` leaves maxIterations and the early  
stopping rule as settings.py has them.

`decay` / `minLearningRate` are absent from the result unless something  
asked for them, so the emitted XML keeps its shipped shape by default.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/configs.py#L321)</sub>

### `calibration_param_ranges`

```python
calibration_param_ranges(params=None, params_override=None)
```

| input | type | default |
|---|---|---|
| `params` | – | `None` |
| `params_override` | – | `None` |

-> {parameter: "min max"} for calibrationCfg.xml.

Precedence: `params_override` (this ITERATION's `calibration:` block in  
session.yaml) beats settings.py, which beats the built-in default. A  
partial override changes only the bounds it names.

Optimiser keys (`learningRate`, `maxIterations`, the early-stopping pair)  
may share the override dict with the bounds — they are dropped here and  
picked up by :func:`calibration_optimiser_settings` instead, so they never  
turn into a `<parameter name="learningRate">` nobody reads.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/configs.py#L349)</sub>

### `create_calibrationCfg`

```python
create_calibrationCfg(
    osimModelPath=None,
    inputPaths: list = [],
    outputPath: str = None,
    params_override: dict = None
)
```

| input | type | default |
|---|---|---|
| `osimModelPath` | – | `None` |
| `inputPaths` | list | `[]` |
| `outputPath` | str | `None` |
| `params_override` | dict | `None` |

Create a CEINMS calibration XML configuration from input parameters.

  
**Args**

- osimModelPath (str): Path to the OpenSim model (.osim). Multiple trials allowed, path must be either full or relative to the calibrationCfgPath.  
- inputPaths (list): List of trial paths for "inputData.xml".  
- outputPath (str): Path to save the generated calibration configuration XML file.  
- params_override (dict): parameter ranges for THIS iteration, from  
  session.yaml's `calibration:` block. Overrides settings.py per parameter.

  
**Returns**

- outputPath (str): The path to the saved calibration configuration XML file.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/configs.py#L383)</sub>

### `create_calibrationSetupXML`

```python
create_calibrationSetupXML(
    uncalibratedCEINMSModelPath=None,
    excitationGeneratorFile=None,
    calibrationCfgPath=None,
    outputSubjectFile=None,
    outputDirectory=None,
    setupXMLPath=None
)
```

| input | type | default |
|---|---|---|
| `uncalibratedCEINMSModelPath` | – | `None` |
| `excitationGeneratorFile` | – | `None` |
| `calibrationCfgPath` | – | `None` |
| `outputSubjectFile` | – | `None` |
| `outputDirectory` | – | `None` |
| `setupXMLPath` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/configs.py#L529)</sub>

### `create_input_data`

```python
create_input_data(
    MAFolder=None,
    excitationsFile=None,
    motionFile=None,
    externalTorquesFile=None,
    externalLoadsFile=None,
    startStopTime=None,
    output_path=None
)
```

| input | type | default |
|---|---|---|
| `MAFolder` | – | `None` |
| `excitationsFile` | – | `None` |
| `motionFile` | – | `None` |
| `externalTorquesFile` | – | `None` |
| `externalLoadsFile` | – | `None` |
| `startStopTime` | – | `None` |
| `output_path` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/configs.py#L574)</sub>

### `create_ceinms_cfg`

```python
create_ceinms_cfg(
    ceinmsModelPath=None,
    alpha=1,
    beta=100,
    gamma=1000,
    dofSet=None,
    excitationGeneratorFilePath=None,
    outputPath=None
)
```

| input | type | default |
|---|---|---|
| `ceinmsModelPath` | – | `None` |
| `alpha` | – | `1` |
| `beta` | – | `100` |
| `gamma` | – | `1000` |
| `dofSet` | – | `None` |
| `excitationGeneratorFilePath` | – | `None` |
| `outputPath` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/configs.py#L646)</sub>

### `replace_ceinms_cfg_parameter`

```python
replace_ceinms_cfg_parameter(cfgXML_path=None, parameter_name=None, new_value=None)
```

| input | type | default |
|---|---|---|
| `cfgXML_path` | – | `None` |
| `parameter_name` | – | `None` |
| `new_value` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/configs.py#L708)</sub>

### `create_optimise_setupFiles`

```python
create_optimise_setupFiles(
    ceinmsModelPath=None,
    inputDataFile=None,
    calibrationCfgPath=None,
    excitationGeneratorFilePath=None,
    outputDirectory=None,
    setupXMLPath=None,
    templateCfgXMLPath=None
)
```

| input | type | default |
|---|---|---|
| `ceinmsModelPath` | – | `None` |
| `inputDataFile` | – | `None` |
| `calibrationCfgPath` | – | `None` |
| `excitationGeneratorFilePath` | – | `None` |
| `outputDirectory` | – | `None` |
| `setupXMLPath` | – | `None` |
| `templateCfgXMLPath` | – | `None` |

create CEINMS setup and configuration XML files for optimisation

use settings.CEINMSParameters() for parameter ranges

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/configs.py#L730)</sub>
