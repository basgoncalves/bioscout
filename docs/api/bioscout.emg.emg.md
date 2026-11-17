# `bioscout.emg.emg`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/emg.py)

bioscout.emg.emg — unified EMG processing surface.

Combines the EMG helpers that were split between ``utils/__init__.py`` and  
``utils/emg_normalise.py``:

* DataFrame-level routines (``filter_emg``, ``load_sto``, ``write_sto_file``,  
  ``time_normalise_df``, ``plot_emg_results``, ``emg_amplitude_normalise``) are  
  imported from :mod:`bioscout.emg.normalise` (their implementation home).  
* File/path-level and session-level routines (``filter_emg_file``,  
  ``amplitude_normalise_emg``, ``emg_processing_file``,  
  ``normalise_emg_across_session``) live here.

``filter_emg`` is the DataFrame filter and the canonical name; ``filter_emg_df``  
is an alias of it (and fixes a previously-undefined reference in  
``emg_processing_file``). ``filter_emg_file`` is the file-path wrapper.

## Contents

- [`filter_emg_file`](#filter_emg_file) — Apply bandpass filter, rectify, and lowpass filter to EMG signals in a .sto file.
- [`amplitude_normalise_emg`](#amplitude_normalise_emg) — Normalise EMG envelope amplitudes across trials to the maximum value found in the normalisation trials, then save new files and plots.
- [`emg_processing_file`](#emg_processing_file) — 
- [`normalise_emg_across_session`](#normalise_emg_across_session) — Session-level EMG amplitude normalisation. Finds max per channel across all trials, divides each trial's emg_filtered.mot by that max -> emg_filtered_normalised.mot. Updates trial.ceinms_excitations on each Analyse instance.

### `filter_emg_file`

```python
filter_emg_file(
    emg_path=None,
    highcut_bp=95,
    lowcut_bp=20,
    order_bp=4,
    lowcut_lp=6,
    order_lp=4
)
```

| input | type | default |
|---|---|---|
| `emg_path` | – | `None` |
| `highcut_bp` | – | `95` |
| `lowcut_bp` | – | `20` |
| `order_bp` | – | `4` |
| `lowcut_lp` | – | `6` |
| `order_lp` | – | `4` |

Apply bandpass filter, rectify, and lowpass filter to EMG signals in a .sto file.

  
**Inputs**

    - emg_path: The path to the .sto file containing EMG signals.  
    - highcut_bp: High cutoff frequency for the bandpass filter.  
    - lowcut_bp: Low cutoff frequency for the bandpass filter.  
    - order_bp: Order of the bandpass filter.  
    - lowcut_lp: Low cutoff frequency for the lowpass filter.  
    - order_lp: Order of the lowpass filter.

  
**Returns**

    - data: A DataFrame containing the original and processed EMG signals.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/emg.py#L35)</sub>

### `amplitude_normalise_emg`

```python
amplitude_normalise_emg(
    main_dir=None,
    trials_to_normalise=None,
    normalisation_trials=None,
    emg_filename='emg.mot'
)
```

| input | type | default |
|---|---|---|
| `main_dir` | – | `None` |
| `trials_to_normalise` | – | `None` |
| `normalisation_trials` | – | `None` |
| `emg_filename` | – | `'emg.mot'` |

Normalise EMG envelope amplitudes across trials to the maximum value found  
in the normalisation trials, then save new files and plots.

  
**Args**

    main_dir: Root directory containing per-trial subdirectories.  
    trials_to_normalise: List of trial folder names to normalise. Defaults to all subdirs.  
    normalisation_trials: List of trial folder names used to find the max EMG. Defaults to trials_to_normalise.  
    emg_filename: Name of the EMG file inside each trial folder (must contain _envelope columns).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/emg.py#L126)</sub>

### `emg_processing_file`

```python
emg_processing_file(
    filepath=None,
    highcut_bp=95,
    lowcut_bp=20,
    order_bp=4,
    lowcut_lp=6,
    order_lp=4,
    emg_prefix='EMG_Channels_EMG'
)
```

| input | type | default |
|---|---|---|
| `filepath` | – | `None` |
| `highcut_bp` | – | `95` |
| `lowcut_bp` | – | `20` |
| `order_bp` | – | `4` |
| `lowcut_lp` | – | `6` |
| `order_lp` | – | `4` |
| `emg_prefix` | – | `'EMG_Channels_EMG'` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/emg.py#L192)</sub>

### `normalise_emg_across_session`

```python
normalise_emg_across_session(trial_objects)
```

| input | type | default |
|---|---|---|
| `trial_objects` | – | required |

Session-level EMG amplitude normalisation.  
Finds max per channel across all trials, divides each trial's  
emg_filtered.mot by that max -> emg_filtered_normalised.mot.  
Updates trial.ceinms_excitations on each Analyse instance.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/emg.py#L205)</sub>
