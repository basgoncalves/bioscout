"""
bioscout.utils.emg — unified EMG processing surface.

Combines the EMG helpers that were split between ``utils/__init__.py`` and
``utils/emg_normalise.py``:

* DataFrame-level routines (``filter_emg``, ``load_sto``, ``write_sto_file``,
  ``time_normalise_df``, ``plot_emg_results``, ``emg_amplitude_normalise``) are
  imported from :mod:`bioscout.utils.emg_normalise` (their implementation home).
* File/path-level and session-level routines (``filter_emg_file``,
  ``amplitude_normalise_emg``, ``emg_processing_file``,
  ``normalise_emg_across_session``) live here.

``filter_emg`` is the DataFrame filter and the canonical name; ``filter_emg_df``
is an alias of it (and fixes a previously-undefined reference in
``emg_processing_file``). ``filter_emg_file`` is the file-path wrapper.
"""
import os

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import scipy.signal

from bioscout import utils as _u
from .emg_normalise import (
    filter_emg, load_sto, write_sto_header, write_sto_file,
    time_normalise_df, mmfn, plot_emg_results, emg_amplitude_normalise,
)

# canonical DataFrame filter alias (also repairs emg_processing_file's call)
filter_emg_df = filter_emg


def filter_emg_file(emg_path=None, highcut_bp=95, lowcut_bp=20, order_bp=4, lowcut_lp=6, order_lp=4):
    """
    Apply bandpass filter, rectify, and lowpass filter to EMG signals in a .sto file.

    Inputs:
        - emg_path: The path to the .sto file containing EMG signals.
        - highcut_bp: High cutoff frequency for the bandpass filter.
        - lowcut_bp: Low cutoff frequency for the bandpass filter.
        - order_bp: Order of the bandpass filter.
        - lowcut_lp: Low cutoff frequency for the lowpass filter.
        - order_lp: Order of the lowpass filter.

    Returns:
        - data: A DataFrame containing the original and processed EMG signals.
    """
    if emg_path is None:
        emg_path = input("Please provide the path to the .sto file containing EMG signals: ")

    data = _u.load_any_data_file(emg_path)

    # Calculate sampling frequency from the time column (default 1000 Hz).
    sampling_freq = 1000.0
    if 'time' in data.columns and len(data['time']) > 1:
        try:
            dt = float(data['time'].iloc[1]) - float(data['time'].iloc[0])
            if dt > 0:
                sampling_freq = 1.0 / dt
        except Exception:
            sampling_freq = 1000.0
        if not (100 <= sampling_freq <= 10000):
            print(f"Warning: unusual EMG sampling freq ({sampling_freq:.1f} Hz) — defaulting to 1000 Hz")
            sampling_freq = 1000.0
    print(f"EMG Sampling Frequency: {sampling_freq:.1f} Hz")

    emg_cols = [col for col in data.columns if col.startswith('emg')]

    # --- 1. Bandpass Filter ---
    nyquist = 0.5 * sampling_freq
    low = lowcut_bp / nyquist
    high = highcut_bp / nyquist

    if low >= high:
        print("Warning: Bandpass filter low cutoff is greater than or equal to high cutoff after normalization.")
        print("Adjusting cutoff frequencies or sampling frequency may be necessary.")
    elif low >= 1.0 or high >= 1.0:
        print("Warning: Bandpass filter cutoff frequency is at or above Nyquist frequency.")
        print("This might lead to unexpected filter behavior. Check sampling frequency and cutoff values.")

    b, a = scipy.signal.butter(order_bp, [low, high], btype='band')

    print(f"\nApplying bandpass filter ({lowcut_bp}-{highcut_bp} Hz, Order {order_bp})...")
    for col in emg_cols:
        filtered_col_name = f"{col}_bandpass"
        data[filtered_col_name] = scipy.signal.filtfilt(b, a, data[col].values)
    print("Bandpass filtering complete.")

    # --- 2. Rectify ---
    print("\nRectifying bandpass-filtered signals...")
    bandpass_emg_cols = [col for col in data.columns if col.endswith('_bandpass')]
    for col in bandpass_emg_cols:
        rectified_col_name = col.replace('_bandpass', '_rectified')
        data[rectified_col_name] = np.abs(data[col].values)
    print("Rectification complete.")

    # --- 3. Lowpass Filter (Envelope) ---
    nyquist = 0.5 * sampling_freq
    low_lp = lowcut_lp / nyquist

    if low_lp >= 1.0:
        print("Warning: Lowpass filter cutoff frequency is at or above Nyquist frequency.")
        print("This might lead to unexpected filter behavior. Check sampling frequency and cutoff values.")

    b_lp, a_lp = scipy.signal.butter(order_lp, low_lp, btype='low')

    print(f"\nApplying lowpass filter ({lowcut_lp} Hz, Order {order_lp}) for envelope detection...")
    rectified_emg_cols = [col for col in data.columns if col.endswith('_rectified')]
    for col in rectified_emg_cols:
        envelope_col_name = col.replace('_rectified', '_envelope')
        data[envelope_col_name] = scipy.signal.filtfilt(b_lp, a_lp, data[col].values)
    print("Lowpass filtering complete.")

    print("\nFiltered data processing complete.")

    # save new file 
    ext = os.path.splitext(emg_path)[1]
    new_emg_path = emg_path.replace(ext, f"_filtered{ext}")
    write_sto_file(data, new_emg_path)
    print(f"Filtered EMG data saved to: {new_emg_path}")

    return data

def amplitude_normalise_emg(main_dir=None, trials_to_normalise=None, normalisation_trials=None, emg_filename="emg.mot"):
    '''
    Normalise EMG envelope amplitudes across trials to the maximum value found
    in the normalisation trials, then save new files and plots.

    Args:
        main_dir: Root directory containing per-trial subdirectories.
        trials_to_normalise: List of trial folder names to normalise. Defaults to all subdirs.
        normalisation_trials: List of trial folder names used to find the max EMG. Defaults to trials_to_normalise.
        emg_filename: Name of the EMG file inside each trial folder (must contain _envelope columns).
    '''

    if main_dir is None:
        main_dir = input("Please provide the path to the main directory containing trial subdirectories: ").strip('"')

    if trials_to_normalise is None:
        trials_to_normalise = os.listdir(main_dir)
        trials_to_normalise = [trial for trial in trials_to_normalise if os.path.isdir(os.path.join(main_dir, trial))]
    
    if normalisation_trials is None:
        normalisation_trials = trials_to_normalise
        

    # load normalisation trial data
    max_emg = {}
    envelope_columns = []
    for trial in normalisation_trials:
        emg_path = f'{main_dir}/{trial}/{emg_filename}'
        emg_data = load_sto(emg_path)
        envelope_columns = [col for col in emg_data.columns if col.endswith('_envelope')]
        if not max_emg:
            for col in envelope_columns:
                max_emg[col] = 0
        for col in envelope_columns:
            max_emg[col] = max(max_emg[col], emg_data[col].max())

    # normalise each trial to max and save new file
    for trial in trials_to_normalise:
        emg_path = f'{main_dir}/{trial}/{emg_filename}'
        emg_data = load_sto(emg_path)

        for col in envelope_columns:
            emg_data[col] = emg_data[col] / max_emg[col]

        new_filepath = emg_path.replace('.mot', '_normalised_amplitude.mot')
        write_sto_file(emg_data, new_filepath)
        print(f'Saved normalised amplitude data to {new_filepath}')

        n_cols = 4
        n_rows = int(np.ceil(len(envelope_columns) / n_cols))
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 3 * n_rows), sharex=True)
        axes = axes.flatten() if n_rows > 1 else [axes]
        for i, col in enumerate(envelope_columns):
            ax = axes[i]
            ax.plot(emg_data['time'], emg_data[col], label=col)
            ax.set_title(f"{trial} - {col}", fontsize=10)
            ax.set_xlabel('Time (s)')
            ax.set_ylabel('Normalised Amplitude')

        plt.tight_layout()
        mmfn(fig, n_rows, n_cols)

        save_path = f'{main_dir}/{trial}/emg_normalised_amplitude_plot.png'
        plt.savefig(save_path)
        print(f'Saved normalised amplitude plot to {save_path}')

def emg_processing_file(filepath=None, highcut_bp=95, lowcut_bp=20, order_bp=4, lowcut_lp=6, order_lp=4, emg_prefix='EMG_Channels_EMG'):
    if filepath is None:
        filepath = input("Please provide the path to the EMG file to be processed: ").strip('"')
    
    # save processed file
    df = _u.load_any_data_file(filepath)
    filtered_df = filter_emg_df(df, highcut_bp, lowcut_bp, order_bp, lowcut_lp, order_lp)

    
    processed_filepath = filepath.replace('.mot', '_processed.mot')
    write_sto_file(filtered_df, processed_filepath)
    print(f'Saved processed EMG data to {processed_filepath}')

def normalise_emg_across_session(trial_objects):
    """
    Session-level EMG amplitude normalisation.
    Finds max per channel across all trials, divides each trial's
    emg_filtered.mot by that max -> emg_filtered_normalised.mot.
    Updates trial.ceinms_excitations on each Analyse instance.
    """
    trial_dfs = {}
    for trial in trial_objects:
        filt_path = os.path.join(trial.path, os.path.dirname(getattr(trial, 'emg', '')) or "", 'emg_filtered.mot')
        if os.path.exists(filt_path):
            try:
                trial_dfs[trial] = _u.load_any_data_file(filt_path)
            except Exception as e:
                _u.print_to_log(f"[Warning] Could not load {filt_path}: {e}")

    if not trial_dfs:
        _u.print_to_log("[Warning] No filtered EMG files found — skipping session normalisation")
        return

    first_df = next(iter(trial_dfs.values()))
    emg_cols = [c for c in first_df.columns if c.lower() != 'time']

    # Session-wide max per channel
    session_max = {}
    for col in emg_cols:
        vals = []
        for df in trial_dfs.values():
            if col in df.columns:
                vals.extend(pd.to_numeric(df[col], errors='coerce').dropna().values)
        session_max[col] = float(np.max(vals)) if vals else 1.0

    _u.print_to_log(f"Session EMG max: { {k: round(v,4) for k,v in session_max.items()} }")

    for trial, df in trial_dfs.items():
        _norm_rel = getattr(trial, 'emg_filtered_normalised', 'emg_filtered_normalised.mot')
        out_path = os.path.join(trial.path, _norm_rel)
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        norm = df.copy()
        for col in emg_cols:
            if col in norm.columns:
                mx = session_max.get(col, 1.0)
                if mx <= 0:
                    mx = 1.0  # zero channel — keep as-is, avoid 0/0 → NaN
                norm[col] = (pd.to_numeric(norm[col], errors='coerce') / mx).clip(0.0, 1.0)
        # Canonical column order: 'time' first, then EMG channels SORTED by name
        # (EMG01..EMG16). CEINMS pairs the excitation generator's inputSignals to
        # the excitations-file columns POSITIONALLY, so EVERY trial's .mot must
        # share one order (and match the generator), else CEINMS execution aborts:
        # "Muscle names are different between excitation generator and input file".
        _tcol = [c for c in norm.columns if c.lower() == 'time']
        _emg = sorted([c for c in norm.columns if c.lower() != 'time'])
        norm = norm[_tcol + _emg]
        write_sto_file(norm, out_path)
        trial.update_trial_attribute('ceinms_excitations', _norm_rel)
        _u.print_to_log(f"[Success] EMG normalised -> {out_path}", trial=trial.trial)


__all__ = [
    "filter_emg", "filter_emg_df", "filter_emg_file",
    "load_sto", "write_sto_header", "write_sto_file",
    "time_normalise_df", "mmfn", "plot_emg_results", "emg_amplitude_normalise",
    "amplitude_normalise_emg", "emg_processing_file", "normalise_emg_across_session",
]
