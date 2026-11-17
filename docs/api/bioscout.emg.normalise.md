# `bioscout.emg.normalise`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/normalise.py)

## Contents

- [`emg_prefix_for`](#emg_prefix_for) — Prefix to hand ``filter_emg`` for these column names.
- [`emg_channel_columns`](#emg_channel_columns) — The raw EMG channel columns among ``columns`` (no time, no derived).
- [`filter_emg`](#filter_emg) — Apply bandpass filter, rectify, and lowpass filter to EMG signals.
- [`load_sto`](#load_sto) — Load a .sto file into a pandas DataFrame.
- [`write_sto_header`](#write_sto_header) — Writes the header for a .sto file.
- [`write_sto_file`](#write_sto_file) — Writes a pandas DataFrame to a .sto file with a specified header.
- [`plot_emg_results`](#plot_emg_results) — 
- [`time_normalise_df`](#time_normalise_df) — 
- [`mmfn`](#mmfn) — make my figure nice
- [`emg_amplitude_normalise`](#emg_amplitude_normalise) — 

### `emg_prefix_for`

```python
emg_prefix_for(columns)
```

| input | type | default |
|---|---|---|
| `columns` | – | required |

Prefix to hand ``filter_emg`` for these column names.

Returns ``CANONICAL_EMG_PREFIX`` when the file uses the Vicon  
'EMG Channels.EMG01_...' naming, else '' (= every non-time column is an EMG  
channel). Different capture sessions label the same signals differently  
('Voltage.EMG1_vast_lat_l' -> 'Voltage_EMG1_vast_lat_l' after export), so  
the prefix must be detected, never assumed.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/normalise.py#L34)</sub>

### `emg_channel_columns`

```python
emg_channel_columns(columns)
```

| input | type | default |
|---|---|---|
| `columns` | – | required |

The raw EMG channel columns among ``columns`` (no time, no derived).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/normalise.py#L48)</sub>

### `filter_emg`

```python
filter_emg(
    data,
    highcut_bp=95,
    lowcut_bp=20,
    order_bp=4,
    lowcut_lp=6,
    order_lp=4,
    emg_prefix='EMG_Channels_EMG',
    sampling_freq=None,
    pre_enveloped=False
)
```

| input | type | default |
|---|---|---|
| `data` | – | required |
| `highcut_bp` | – | `95` |
| `lowcut_bp` | – | `20` |
| `order_bp` | – | `4` |
| `lowcut_lp` | – | `6` |
| `order_lp` | – | `4` |
| `emg_prefix` | – | `'EMG_Channels_EMG'` |
| `sampling_freq` | – | `None` |
| `pre_enveloped` | – | `False` |

Apply bandpass filter, rectify, and lowpass filter to EMG signals.

  
**Parameters**

- data: DataFrame containing EMG signals.  
- highcut_bp: High cutoff frequency for the bandpass filter.  
- lowcut_bp: Low cutoff frequency for the bandpass filter.  
- order_bp: Order of the bandpass filter.  
- lowcut_lp: Low cutoff frequency for the lowpass filter.  
- order_lp: Order of the lowpass filter.  
- pre_enveloped: the input is ALREADY a rectified, low-pass-filtered  
  envelope, so band-passing and rectifying it would destroy it. The two  
  stages are skipped and the signal is passed through to the `_envelope`  
  columns unchanged. Rectification would be a no-op on it anyway (an  
  envelope is non-negative); the band-pass is the destructive step, since  
  an envelope carries no energy in the 20 Hz+ band it keeps.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/normalise.py#L57)</sub>

### `load_sto`

```python
load_sto(path=None, output=0)
```

| input | type | default |
|---|---|---|
| `path` | – | `None` |
| `output` | – | `0` |

Load a .sto file into a pandas DataFrame.

  
**Args**

    path (str): The path to the .sto file. If None, prompts for input.  
    output (int): If 1, prints the columns of the DataFrame.

  
**Returns**

    pd.DataFrame: The loaded data from the .sto file.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/normalise.py#L160)</sub>

### `write_sto_header`

```python
write_sto_header(writer, dataFrame)
```

| input | type | default |
|---|---|---|
| `writer` | – | required |
| `dataFrame` | – | required |

Writes the header for a .sto file.

  
**Args**

    writer (TextIOWrapper): The file writer object.  
    dataFrame (pd.DataFrame): The DataFrame containing the data.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/normalise.py#L211)</sub>

### `write_sto_file`

```python
write_sto_file(dataFrame, file_path)
```

| input | type | default |
|---|---|---|
| `dataFrame` | – | required |
| `file_path` | – | required |

Writes a pandas DataFrame to a .sto file with a specified header.

  
**Args**

    dataFrame (pd.DataFrame): The DataFrame to write.  
    file_path (str): The path where the .sto file will be saved.  
    header (list): A list of strings representing the header lines to write.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/normalise.py#L249)</sub>

### `plot_emg_results`

```python
plot_emg_results(emg_data)
```

| input | type | default |
|---|---|---|
| `emg_data` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/normalise.py#L278)</sub>

### `time_normalise_df`

```python
time_normalise_df(df, fs='')
```

| input | type | default |
|---|---|---|
| `df` | – | required |
| `fs` | – | `''` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/normalise.py#L322)</sub>

### `mmfn`

```python
mmfn(fig: plt.Figure, n_rows: int, n_cols: int)
```

| input | type | default |
|---|---|---|
| `fig` | plt.Figure | required |
| `n_rows` | int | required |
| `n_cols` | int | required |

make my figure nice

- remove x-tick labels from all but last row  
- remove title from all but first row

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/normalise.py#L365)</sub>

### `emg_amplitude_normalise`

```python
emg_amplitude_normalise(
    main_dir,
    trials_to_normalise,
    normalisation_trials,
    emg_filename='emg.mot'
)
```

| input | type | default |
|---|---|---|
| `main_dir` | – | required |
| `trials_to_normalise` | – | required |
| `normalisation_trials` | – | required |
| `emg_filename` | – | `'emg.mot'` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/normalise.py#L392)</sub>
