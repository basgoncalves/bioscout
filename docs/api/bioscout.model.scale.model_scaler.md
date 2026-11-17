# `bioscout.model.scale.model_scaler`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/model_scaler.py)

OpenSim Model Scaling Tool integration.

Handles model scaling using OpenSim's Scale Tool with customizable marker weights.

## Contents

- class [`ModelScaler`](#modelscaler) — Interface to OpenSim's Scale Tool for model scaling.
  - [`ModelScaler.parse_trc_markers`](#modelscalerparse_trc_markers) — Parse TRC file and extract marker positions.
  - [`ModelScaler.calculate_scale_factors`](#modelscalercalculate_scale_factors) — Calculate scale factors based on marker positions and weights.
  - [`ModelScaler.create_scale_setup_xml`](#modelscalercreate_scale_setup_xml) — Create OpenSim Scale Tool setup XML file.
  - [`ModelScaler.run_scale`](#modelscalerrun_scale) — Run the complete scaling process.

<a id="modelscaler"></a>

## class `ModelScaler`

```python
ModelScaler(
    template_model_path: str,
    trc_file: str,
    destination_dir: str,
    output_model_dir: Optional[str] = None
)
```

| input | type | default |
|---|---|---|
| `template_model_path` | str | required |
| `trc_file` | str | required |
| `destination_dir` | str | required |
| `output_model_dir` | Optional[str] | `None` |

Interface to OpenSim's Scale Tool for model scaling.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/model_scaler.py#L15)</sub>

<a id="modelscalerparse_trc_markers"></a>

### `ModelScaler.parse_trc_markers`

```python
ModelScaler.parse_trc_markers() -> Dict[str, np.ndarray]
```

**returns** `Dict[str, np.ndarray]`

Parse TRC file and extract marker positions.

  
**Returns**

    Dictionary of marker_name -> (num_frames, 3) array of XYZ positions

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/model_scaler.py#L60)</sub>

<a id="modelscalercalculate_scale_factors"></a>

### `ModelScaler.calculate_scale_factors`

```python
ModelScaler.calculate_scale_factors(
    marker_weights: Optional[Dict[str, float]],
    markerset_path: Optional[str] = None
) -> Dict[str, float]
```

| input | type | default |
|---|---|---|
| `marker_weights` | Optional[Dict[str, float]] | required |
| `markerset_path` | Optional[str] | `None` |

**returns** `Dict[str, float]`

Calculate scale factors based on marker positions and weights.

This is a simplified implementation. For production use, integrate with  
OpenSim's Scale Tool which uses more sophisticated algorithms.

  
**Args**

    marker_weights: Dictionary of marker_name -> weight  
    markerset_path: Optional path to markerset XML file

  
**Returns**

    Dictionary of segment_name -> scale_factor

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/model_scaler.py#L180)</sub>

<a id="modelscalercreate_scale_setup_xml"></a>

### `ModelScaler.create_scale_setup_xml`

```python
ModelScaler.create_scale_setup_xml(
    marker_weights: Dict[str, float],
    scale_factors: Dict[str, float],
    markerset_path: Optional[str] = None,
    output_filename: Optional[str] = None
) -> str
```

| input | type | default |
|---|---|---|
| `marker_weights` | Dict[str, float] | required |
| `scale_factors` | Dict[str, float] | required |
| `markerset_path` | Optional[str] | `None` |
| `output_filename` | Optional[str] | `None` |

**returns** `str`

Create OpenSim Scale Tool setup XML file.

  
**Args**

    marker_weights: Dictionary of marker weights  
    scale_factors: Dictionary of segment scale factors  
    markerset_path: Optional custom markerset file  
    output_filename: Optional custom output filename (defaults to scaled_<template_name>.osim)

  
**Returns**

    Path to created setup XML file

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/model_scaler.py#L253)</sub>

<a id="modelscalerrun_scale"></a>

### `ModelScaler.run_scale`

```python
ModelScaler.run_scale(
    marker_weights: Dict[str, float],
    markerset_path: Optional[str] = None
) -> Tuple[str, Dict[str, float]]
```

| input | type | default |
|---|---|---|
| `marker_weights` | Dict[str, float] | required |
| `markerset_path` | Optional[str] | `None` |

**returns** `Tuple[str, Dict[str, float]]`

Run the complete scaling process.

  
**Args**

    marker_weights: Dictionary of marker weights  
    markerset_path: Optional custom markerset

  
**Returns**

    Tuple of (scaled_model_path, scale_factors_dict)

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/model_scaler.py#L356)</sub>
