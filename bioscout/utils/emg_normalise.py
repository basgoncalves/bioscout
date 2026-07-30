import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt
import math

# Handle both package and standalone imports
try:
    from . import openSim
except (ImportError, ValueError):
    try:
        import openSim
    except ImportError:
        import sys
        from pathlib import Path
        parent_dir = str(Path(__file__).parent)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        import openSim


'''
This module contains functions for normalising EMG data, including filtering, rectification, lowpass filtering (envelope detection), and time normalisation. It also includes functions for loading and writing .sto files, as well as plotting EMG results.
'''
CANONICAL_EMG_PREFIX = 'EMG_Channels_EMG'


def emg_prefix_for(columns):
    """Prefix to hand ``filter_emg`` for these column names.

    Returns ``CANONICAL_EMG_PREFIX`` when the file uses the Vicon
    'EMG Channels.EMG01_...' naming, else '' (= every non-time column is an EMG
    channel). Different capture sessions label the same signals differently
    ('Voltage.EMG1_vast_lat_l' -> 'Voltage_EMG1_vast_lat_l' after export), so
    the prefix must be detected, never assumed.
    """
    cols = [] if columns is None else [str(c) for c in columns]
    return CANONICAL_EMG_PREFIX if any(
        c.startswith(CANONICAL_EMG_PREFIX) for c in cols) else ''


def emg_channel_columns(columns):
    """The raw EMG channel columns among ``columns`` (no time, no derived)."""
    pre = emg_prefix_for(columns)
    cols = [] if columns is None else [str(c) for c in columns]
    return [c for c in cols
            if c.startswith(pre) and c.lower() != 'time'
            and not c.endswith(('_rectified', '_bandpass', '_envelope'))]


def filter_emg(data, highcut_bp=95, lowcut_bp=20, order_bp=4, lowcut_lp=6, order_lp=4, emg_prefix='EMG_Channels_EMG', sampling_freq=None):
    """
    Apply bandpass filter, rectify, and lowpass filter to EMG signals.

    Parameters:
    - data: DataFrame containing EMG signals.
    - highcut_bp: High cutoff frequency for the bandpass filter.
    - lowcut_bp: Low cutoff frequency for the bandpass filter.
    - order_bp: Order of the bandpass filter.
    - lowcut_lp: Low cutoff frequency for the lowpass filter.
    - order_lp: Order of the lowpass filter.
    """
    # Calculate sampling frequency
    if sampling_freq is None:
        time_diffs = data['time'].diff().dropna()
        if not time_diffs.empty:
            mean_dt = time_diffs.mean()
            if mean_dt > 0:
                sampling_freq = 1 / mean_dt
            else:
                sampling_freq = 1000
                print(f"Warning: invalid time step ({mean_dt:.6g}) — defaulting to {sampling_freq} Hz")
            if not (100 <= sampling_freq <= 10000):
                print(f"Warning: unusual sampling freq ({sampling_freq:.1f} Hz) — clamping to 1000 Hz")
                sampling_freq = 1000
        else:
            sampling_freq = 1000
    print(f"EMG Sampling Frequency: {sampling_freq:.1f} Hz")

    # List of EMG signal columns (excluding 'time' and any previously rectified/filtered columns)
    emg_cols = [col for col in data.columns
                if col.startswith(emg_prefix)
                and col.lower() != 'time'
                and not col.endswith(('_rectified', '_bandpass', '_envelope'))]

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

    b, a = butter(order_bp, [low, high], btype='band')

    print(f"\nApplying bandpass filter ({lowcut_bp}-{highcut_bp} Hz, Order {order_bp})...")
    for col in emg_cols:
        filtered_col_name = f"{col}_bandpass"
        data[filtered_col_name] = filtfilt(b, a, data[col].values)
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

    b_lp, a_lp = butter(order_lp, low_lp, btype='low')

    print(f"\nApplying lowpass filter ({lowcut_lp} Hz, Order {order_lp}) for envelope detection...")
    rectified_emg_cols = [col for col in data.columns if col.endswith('_rectified')]
    for col in rectified_emg_cols:
        envelope_col_name = col.replace('_rectified', '_envelope')
        data[envelope_col_name] = filtfilt(b_lp, a_lp, data[col].values)
    print("Lowpass filtering complete.")

    print("\nFiltered data processing complete.")
    return data

def load_sto(path=None, output=0):
    """
    Load a .sto file into a pandas DataFrame.

    Args:
        path (str): The path to the .sto file. If None, prompts for input.
        output (int): If 1, prints the columns of the DataFrame.

    Returns:
        pd.DataFrame: The loaded data from the .sto file.
    """

    if not path:
        print("Path not found!")
        return


    # find line with 'endheader' to skip the header
    try:
        with open(path, 'r') as file:
            for i, line in enumerate(file):
                if 'endheader' in line or i > 100:  # Limit to first 100 lines to avoid long files
                        break
    except:
        print(f"Error: Could not read the file at {path}. Please check the path and try again.")
        return None

    # read the file into a pandas DataFrame, skipping the header
    try:
        columns = []
        offset = -3
        while 'time' not in columns:
            try:
                data = pd.read_csv(path, sep= r'\s+', header=i+offset)
                columns = data.columns
                offset += 1
                if offset > 100:
                    print(f"Error: Could not find 'time' column in the file {path}. Please check the file format.")
                    return None
            except pd.errors.ParserError:
                offset += 1

    except Exception as e:
        print(f"Error: Could not read the file at {path}. Please check the file format and try again.")
        print(f"Details: {e}")
        return None

    if output == 1: print(data.columns)

    return data

def write_sto_header(writer, dataFrame):
    """
    Writes the header for a .sto file.

    Args:
        writer (TextIOWrapper): The file writer object.
        dataFrame (pd.DataFrame): The DataFrame containing the data.
    """
    writer.write(f"{os.path.basename(writer.name)}\n")
    writer.write("version=1\n")
    writer.write(f"nRows={dataFrame.shape[0]}\n")
    writer.write(f"nColumns={dataFrame.shape[1]}\n")
    writer.write("in_degrees=yes\n")
    writer.write("endheader\n")

def write_sto_file(dataFrame, file_path):
    """
    Writes a pandas DataFrame to a .sto file with a specified header.

    Args:
        dataFrame (pd.DataFrame): The DataFrame to write.
        file_path (str): The path where the .sto file will be saved.
        header (list): A list of strings representing the header lines to write.
    """
    if not os.path.exists(os.path.dirname(file_path)):
        os.makedirs(os.path.dirname(file_path))
        print(f"Created directory: {os.path.dirname(file_path)}")

    # make time lowercase
    if 'Time' in dataFrame.columns:
        dataFrame = dataFrame.rename(columns={"Time": "time"})


    with open(file_path, 'w', newline='') as f:
        # Write the header lines
        write_sto_header(f, dataFrame)

        # bring time column to front
        dataFrame = dataFrame[['time'] + [col for col in dataFrame.columns if col != 'time']]

        # Write the data without extra line spaces
        dataFrame.to_csv(f, sep='\t', index=False, float_format='%.6f')

def plot_emg_results(emg_data):
    time_col = emg_data.columns[0]
    signal_cols = emg_data.columns[1:]

    num_signals = len(signal_cols)
    # Determine a suitable grid size for subplots
    # Aim for a roughly square layout
    ncols = int(math.ceil(math.sqrt(num_signals)))
    nrows = int(math.ceil(num_signals / ncols))

    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(5 * ncols, 3 * nrows), sharex=True)
    title = "EMG Signals"
    fig.suptitle(title, fontsize=16)

    # Flatten axes array for easy iteration if it's 2D
    if nrows > 1 and ncols > 1:
        axes = axes.flatten()
    elif nrows == 1 and ncols > 1:
        pass # axes is already 1D
    else:
        axes = [axes] # Make it iterable for a single plot

    for i, col in enumerate(signal_cols):
        ax = axes[i]
        ax.plot(emg_data[time_col], emg_data[col], label=col)
        ax.set_title(col, fontsize=10)
        ax.set_ylabel("Amplitude")
        ax.grid(True)
        # Hide x-axis labels for all but the bottom row plots
        if i < (nrows - 1) * ncols:
            ax.tick_params(labelbottom=False)

    # Set common x-label for the bottom row plots
    for j in range(ncols):
        if (nrows - 1) * ncols + j < num_signals:
            axes[(nrows - 1) * ncols + j].set_xlabel(time_col)

    # Hide any unused subplots
    for i in range(num_signals, len(axes)):
        fig.delaxes(axes[i])

    plt.tight_layout(rect=[0, 0.03, 1, 0.95]) # Adjust layout to prevent suptitle overlap
    plt.show()

def time_normalise_df(df, fs=''):

    if not type(df) == pd.core.frame.DataFrame:
        raise Exception('Input must be a pandas DataFrame')

    if not fs:
        try:
            # mean sampling frequency over the time column
            fs = 1/((df['time'].iloc[-1]-df['time'].iloc[0])/(len(df)-1))
        except  KeyError as e:
            raise Exception('Input DataFrame must contain a column named "time"')

    normalised_df = pd.DataFrame(columns=df.columns)
    try:
        for column in df.columns:
            normalised_df[column] = np.zeros(101)

            currentData = df[column]
            currentData = currentData[~np.isnan(currentData)]

            if currentData.empty:
                currentData = np.zeros(len(df))

            # time trial length of trial (start at 0) and normalised time vector (0-100%)
            timeTrial = df['time']- df['time'].iloc[0]
            if len(timeTrial) > len(currentData):
                timeTrial = np.arange(1/fs, len(currentData)/fs, 1/fs)

            Tnorm = np.arange(0, timeTrial.iloc[-1], timeTrial.iloc[-1]/101)

            if len(Tnorm) == 102:
                Tnorm = Tnorm[:-1]

            if len(timeTrial) != len(currentData):
                breakpoint()

            normalised_df[column] = np.interp(Tnorm, timeTrial, currentData)
            normalised_df['time'] = Tnorm
    except Exception as e:
        print(f"Error during time normalisation: {e}")
        breakpoint()
    return normalised_df

def mmfn(fig: plt.Figure, n_rows: int, n_cols: int):
    '''make my figure nice

    - remove x-tick labels from all but last row
    - remove title from all but first row

    '''
    axes = fig.get_axes()
    if len(axes) != n_rows * n_cols:
        raise ValueError(f'Number of axes ({len(axes)}) does not match n_rows * n_cols ({n_rows * n_cols})')
    
    for idx, ax in enumerate(axes):
        row = idx // n_cols
        col = idx % n_cols
        
        # Remove x-tick labels from all but last row
        if row < n_rows - 1:
            ax.set_xticklabels([])
            ax.set_xlabel('')

        # Remove title from all but first row
        if row > 0:
            ax.set_title('')
    
    plt.tight_layout()
    return fig

def emg_amplitude_normalise(main_dir, trials_to_normalise, normalisation_trials, emg_filename = "emg.mot"):

    # load normalisation trial data
    normalisation_data = []
    max_emg = {}
    for trial in normalisation_trials:
        emg_path = f'{main_dir}/{trial}/{emg_filename}'
        emg_data = load_sto(emg_path)        
        envelope_columns = [col for col in emg_data.columns if col.endswith('_envelope')]
        # if max_emg empty add the columns from emg_data as keys
        if not max_emg:
            for col in envelope_columns:
                max_emg[col] = 0
        
        for col in envelope_columns:
            max_emg[col] = max(max_emg[col], emg_data[col].max())

    # normalise each tiral to max and save new .mot file
    for trial in trials_to_normalise:
        emg_path = f'{main_dir}/{trial}/{emg_filename}'
        emg_data = load_sto(emg_path)

        for col in envelope_columns:
            max_emg_col = max_emg[col]
            emg_data[col] = emg_data[col] / max_emg_col
        
        new_filepath = emg_path.replace('.mot', '_normalised_amplitude.mot')
        write_sto_file(emg_data, new_filepath)
        print(f'Saved normalised amplitude data to {new_filepath}')

        # plot the normalised data
        n_cols = 4
        n_rows = int(np.ceil(len(envelope_columns) / n_cols))   
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 3 * n_rows), sharex=True)
        axes = axes.flatten() if n_rows > 1 else [axes] # Ensure axes is always a list for iteration
        for i, col in enumerate(envelope_columns):
            ax = axes[i]
            ax.plot(emg_data['time'], emg_data[col], label=col)
            ax.set_title(col)
            ax.set_xlabel('Time (s)')
            ax.set_ylabel('Normalised Amplitude')
        

        plt.tight_layout()
        mmfn(fig, n_rows, n_cols)

        # add title to all subplots
        for ax in axes:
            ax.set_title(f"{trial} - {col}", fontsize=10)

        save_path = f'{main_dir}/{trial}/emg_normalised_amplitude_plot.png'
        plt.savefig(save_path)
        print(f'Saved normalised amplitude plot to {save_path}')


if __name__ == "__main__":
    
    # main directory containing the c3d files and where the normalised .mot files will be saved
    main_dir = r"C:\Users\Basilio\Downloads\Kicking_data-20260417T091537Z-3-001\Kicking_data\Pilot_EMG"
    emg_list = os.listdir(main_dir)
    emg_list = [file.replace('.c3d', '') for file in emg_list if file.endswith('.c3d')]

    normalisation_trials = emg_list

    skip_export = True

    bandpass = [20, 95]
    lowpass = 4
    prefix_EMG = 'EMG_Channels'

    for trial in emg_list:

        if skip_export:
            continue

        c3d_path = os.path.join(main_dir, f"{trial}.c3d")
        openSim.export_c3d(c3d_path, create_folder=True, emg_string_list=[prefix_EMG])

        emg_path = os.path.join(main_dir, trial, "emg.mot")
        try:
            filtred_emg  = filter_emg(load_sto(emg_path))
            write_sto_file(filtred_emg, emg_path.replace(".mot", "_filtered.mot"))
        except Exception as e:
            print(f"Error processing EMG file {emg_path}: {e}")

        try:
            time_norm_emg = time_normalise_df(load_sto(emg_path.replace(".mot", "_filtered.mot")))
            write_sto_file(time_norm_emg, emg_path.replace(".mot", "_filtered_time_normalised.mot"))
        except Exception as e:
            print(f"Error time normalising EMG file {emg_path}: {e}")

    
    emg_amplitude_normalise(main_dir, emg_list, normalisation_trials, emg_filename="emg_filtered_time_normalised.mot")
