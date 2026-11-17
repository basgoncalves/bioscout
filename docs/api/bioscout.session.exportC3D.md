# `bioscout.session.exportC3D`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/exportC3D.py)

## Contents

- [`quiet_call`](#quiet_call) — Call ``fn`` with its stdout folded away, keeping only lines that can mean a problem (same rule as main()). For chatty helpers run once per trial -- create_grf_xml prints ~12 lines per trial. BIOSCOUT_VERBOSE=1 shows all.
- [`load_any_data_file`](#load_any_data_file) — 
- [`filter_emg`](#filter_emg) — 
- [`crop_nans`](#crop_nans) — Crop NaN values from the beginning and end of TRC/MOT/STO files.
- [`define_time_range`](#define_time_range) — 
- [`write_mot`](#write_mot) — Write analog data (samples, n_channels) to MOT in OpenSim format.
- [`rotate_data_table`](#rotate_data_table) — Rotate OpenSim::TimeSeriesTableVec3 entries using an axis and angle.
- [`export_emg`](#export_emg) — 
- [`export_markers`](#export_markers) — 
- [`export_grf`](#export_grf) — 
- [`get_time_range_from_c3d`](#get_time_range_from_c3d) — Return (start_time, end_time) in seconds from a C3D file.
- [`main`](#main) — Export C3D data to TRC / GRF.mot / EMG.mot files.
- [`export_session`](#export_session) — Export EVERY c3d of a session-centric session into per-trial folders.
- [`transform_labels`](#transform_labels) — Transforms a list of labels from a compact format to a more descriptive format. Example: 'f1x' -> 'ground_force_1_vx'
- [`grf_from_c3d`](#grf_from_c3d) — 
- [`plot_GRF`](#plot_grf) — 

### `quiet_call`

```python
quiet_call(fn, *args, **kwargs)
```

| input | type | default |
|---|---|---|
| `fn` | – | required |
| `*args` | – | – |
| `**kwargs` | – | – |

Call ``fn`` with its stdout folded away, keeping only lines that can  
mean a problem (same rule as main()). For chatty helpers run once per trial  
-- create_grf_xml prints ~12 lines per trial. BIOSCOUT_VERBOSE=1 shows all.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/exportC3D.py#L88)</sub>

### `load_any_data_file`

```python
load_any_data_file(*args, **kwargs)
```

| input | type | default |
|---|---|---|
| `*args` | – | – |
| `**kwargs` | – | – |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/exportC3D.py#L167)</sub>

### `filter_emg`

```python
filter_emg(*args, **kwargs)
```

| input | type | default |
|---|---|---|
| `*args` | – | – |
| `**kwargs` | – | – |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/exportC3D.py#L171)</sub>

### `crop_nans`

```python
crop_nans(filepath, nan_threshold=None)
```

| input | type | default |
|---|---|---|
| `filepath` | – | required |
| `nan_threshold` | – | `None` |

Crop NaN values from the beginning and end of TRC/MOT/STO files.

For TRC files, uses direct text parsing to preserve exact format.  
For other files, uses pandas DataFrames.

  
**Parameters**

filepath : str  
    Path to TRC, MOT, or STO file to crop  
nan_threshold : float, optional  
    If provided, removes rows where NaN fraction > threshold.  
    If None (default), uses 0.5 (50%) for TRC files.

  
**Returns**

dict or None  
    Dictionary with crop information or None if error/no cropping needed.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/exportC3D.py#L351)</sub>

### `define_time_range`

```python
define_time_range(trc_filepath, markers, algorithm)
```

| input | type | default |
|---|---|---|
| `trc_filepath` | – | required |
| `markers` | – | required |
| `algorithm` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/exportC3D.py#L517)</sub>

### `write_mot`

```python
write_mot(analog_df, labels, mot_file)
```

| input | type | default |
|---|---|---|
| `analog_df` | – | required |
| `labels` | – | required |
| `mot_file` | – | required |

Write analog data (samples, n_channels) to MOT in OpenSim format.

  
**inputs**

    labels: The labels for the analog channels (not including time).  
    analog_df: The DataFrame containing the analog data (must include 'time' column).  
    mot_file: Output file path.  
    

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/exportC3D.py#L539)</sub>

### `rotate_data_table`

```python
rotate_data_table(table, axis, deg)
```

| input | type | default |
|---|---|---|
| `table` | – | required |
| `axis` | – | required |
| `deg` | – | required |

Rotate OpenSim::TimeSeriesTableVec3 entries using an axis and angle.

  
**Parameters**

table: OpenSim.common.TimeSeriesTableVec3

axis: 3x1 vector

deg: angle in degrees

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/exportC3D.py#L576)</sub>

### `export_emg`

```python
export_emg(
    c3d_filepath,
    emg_strings_list=['emg'],
    reset_time=True,
    output_dir=None,
    emg_channels=None
)
```

| input | type | default |
|---|---|---|
| `c3d_filepath` | – | required |
| `emg_strings_list` | – | `['emg']` |
| `reset_time` | – | `True` |
| `output_dir` | – | `None` |
| `emg_channels` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/exportC3D.py#L646)</sub>

### `export_markers`

```python
export_markers(c3d_filepath, strings_to_remove=[], output_dir=None)
```

| input | type | default |
|---|---|---|
| `c3d_filepath` | – | required |
| `strings_to_remove` | – | `[]` |
| `output_dir` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/exportC3D.py#L794)</sub>

### `export_grf`

```python
export_grf(c3d_filepath, output_dir=None)
```

| input | type | default |
|---|---|---|
| `c3d_filepath` | – | required |
| `output_dir` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/exportC3D.py#L920)</sub>

### `get_time_range_from_c3d`

```python
get_time_range_from_c3d(c3d_filepath)
```

| input | type | default |
|---|---|---|
| `c3d_filepath` | – | required |

Return (start_time, end_time) in seconds from a C3D file.

Tries the forces/analog table first (present even when there are no markers),  
then falls back to the markers table.  Returns None if both fail.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/exportC3D.py#L1021)</sub>

### `main`

```python
main(
    c3d_filepath,
    emg_string_list=['emg'],
    create_folder=False,
    output_dir=None,
    emg_channels=None
)
```

| input | type | default |
|---|---|---|
| `c3d_filepath` | – | required |
| `emg_string_list` | – | `['emg']` |
| `create_folder` | – | `False` |
| `output_dir` | – | `None` |
| `emg_channels` | – | `None` |

Export C3D data to TRC / GRF.mot / EMG.mot files.

  
**Parameters**

output_dir : str, optional  
    Explicit destination folder (created if needed). In the session-centric  
    layout this is ``<session>/experimental/<trial>/``. If omitted, exports  
    next to the c3d — optionally in a per-trial subfolder (``create_folder``).

  
**Returns**

tuple or None  
    (start_time, end_time) in seconds read from the C3D, or None if  
    the time range could not be determined.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/exportC3D.py#L1043)</sub>

### `export_session`

```python
export_session(
    session_dir,
    emg_string_list=None,
    c3d_dirname=None,
    out_dirname=None,
    normalise=True
)
```

| input | type | default |
|---|---|---|
| `session_dir` | – | required |
| `emg_string_list` | – | `None` |
| `c3d_dirname` | – | `None` |
| `out_dirname` | – | `None` |
| `normalise` | – | `True` |

Export EVERY c3d of a session-centric session into per-trial folders.

New layout (model-INDEPENDENT data, produced ONCE and shared by all model  
iterations)::

    <session_dir>/<c3d_dirname>/<trial>.c3d          # raw input  
    <session_dir>/<out_dirname>/<trial>/             # created here  
        marker_experimental.trc  grf.mot  GRF.xml  
        emg.mot  emg_filtered.mot  emg_filtered_normalised.mot

EMG amplitude normalisation is SESSION-WIDE (per-channel max across all  
trials = MVC reference) and writes columns in canonical SORTED order  
(time, EMG01..EMGnn) so CEINMS pairs the excitation generator with each  
trial's excitations consistently. Returns the list of exported trial names.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/exportC3D.py#L1284)</sub>

### `transform_labels`

```python
transform_labels(labels)
```

| input | type | default |
|---|---|---|
| `labels` | – | required |

Transforms a list of labels from a compact format to a more descriptive format.  
Example: 'f1x' -> 'ground_force_1_vx'

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/exportC3D.py#L1403)</sub>

### `grf_from_c3d`

```python
grf_from_c3d(c3d_filepath)
```

| input | type | default |
|---|---|---|
| `c3d_filepath` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/exportC3D.py#L1438)</sub>

### `plot_GRF`

```python
plot_GRF()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/exportC3D.py#L1623)</sub>
