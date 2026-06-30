# from logging import root
from glob import glob
import math
import os
import shutil
import subprocess
import time
import sys
import re
from pathlib import Path

import webbrowser

# GUI toolkits are optional: importing utils for analysis/headless use must not
# require (or stall on) a display. The GUI widgets import these themselves.
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog
except Exception:
    tk = None
    filedialog = messagebox = simpledialog = None
try:
    import customtkinter as ctk
except Exception:
    ctk = None

import numpy as np
import pandas as pd

# Handle matplotlib import with graceful fallback for circular import issues
try:
    import matplotlib
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.offsetbox import AnchoredText
    HAS_MATPLOTLIB = True
except ImportError as e:
    # If matplotlib fails to import (circular import or missing), provide fallback
    HAS_MATPLOTLIB = False
    class FakeMatplotlib:
        pyplot = None
        backends = None
        offsetbox = None
    matplotlib = FakeMatplotlib()
    plt = None
    PdfPages = None
    AnchoredText = None

# scipy
try:
    import scipy
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

import xml.etree.ElementTree as ET
import xml.dom.minidom

try:
    # opensim/__init__.py prints a "Found simbody-visualizer, setting
    # SIMBODY_HOME ..." banner via a plain Python print() on first import.
    # Capture stdout during the import to silence it (the env var it sets still
    # gets set). Set BIOSCOUT_VERBOSE_OPENSIM=1 to see the banner.
    if os.environ.get("BIOSCOUT_VERBOSE_OPENSIM"):
        import opensim as osim
    else:
        import io as _io
        import contextlib as _contextlib
        with _contextlib.redirect_stdout(_io.StringIO()):
            import opensim as osim
    HAS_OPENSIM = True
except ImportError:
    HAS_OPENSIM = False
    osim = None

# c3d
try:
    import c3d
    HAS_C3D = True
except ImportError:
    HAS_C3D = False
    c3d = None

# Ensure utils dir and app dir are on sys.path for standalone execution.

_utils_dir = str(Path(__file__).parent)
_app_dir = str(Path(__file__).parent.parent)
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)
if _utils_dir in sys.path:
    sys.path.remove(_utils_dir)
sys.path.insert(0, _utils_dir)

# ceinms and openSim are imported at BOTTOM of this file to break circular imports
# (ceinms.py and openSim.py both import utils, so importing them here causes deadlock)
openSim = None
ceinms = None
HAS_CEINMS = False

# settings
try:
    import settings
except Exception as e:
    print(f"Error importing settings module: {e}")
    settings = None

# emg_normalise imported at BOTTOM to break circular import chain
# (emg_normalise -> openSim -> exportC3D -> utils)
emg_normalise = None
HAS_EMG_NORMALISE = False


# utils doesn't carry its own version — it reflects the package (single source).
from bioscout import __version__  # noqa: E402,F401

# Project directories
UTILS_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(UTILS_DIR)


def _resolve_project_dir():
    """Locate the project root (the folder holding models/ simulations/ results/).

    Priority:
      1. BIOSCOUT_PROJECT_DIR environment variable
      2. current working directory, if it looks like a project
         (has settings.py or a models/ or simulations/ folder)
      3. PROJECT_ROOT from an imported project settings.py (if it exists on disk)
      4. the folder containing the bioscout package (legacy default)
    """
    env = os.environ.get('BIOSCOUT_PROJECT_DIR')
    if env and os.path.isdir(env):
        return os.path.abspath(env)
    cwd = os.getcwd()
    if (os.path.exists(os.path.join(cwd, 'settings.py')) or
            any(os.path.isdir(os.path.join(cwd, d))
                for d in ('simulations', 'Simulations', 'models', 'Models'))):
        return cwd
    try:
        _pr = getattr(getattr(settings, 'BatchSettings', None), 'PROJECT_ROOT', None)
        if _pr and os.path.isdir(str(_pr)):
            return os.path.abspath(str(_pr))
    except Exception:
        pass
    return os.path.dirname(APP_DIR)


PROJECT_DIR = _resolve_project_dir()

CODE_DIR = UTILS_DIR   # where this package physically lives (e.g. for log.txt)

# Project data directories. The SOURCE OF TRUTH is the project's settings.py;
# these just mirror it so the package can read utils.MODELS_DIR /
# utils.SIMULATIONS_DIR / utils.RESULTS_DIR. They are None until a project's
# settings define them, and bioscout.Project() (re)points them via _point_dirs().
def _dir_from_settings(name):
    val = getattr(getattr(settings, "BatchSettings", None), name, None)
    return str(val) if val is not None else None

MODELS_DIR       = _dir_from_settings('MODELS_DIR')
SIMULATIONS_DIR  = _dir_from_settings('SIMULATIONS_DIR')
RESULTS_DIR      = _dir_from_settings('RESULTS_DIR')
TASK_FIGURES_DIR = os.path.join(RESULTS_DIR, 'task_figures') if RESULTS_DIR else None

CEINMS_DIR = os.path.join(UTILS_DIR, 'ceinms')
CEINMS_EXE = os.path.join(CEINMS_DIR, 'CEINMS.exe')
CEINMS_OPTIMISE_EXE = os.path.join(CEINMS_DIR, 'CEINMSoptimise.exe')
CEINMS_CALIBRATION_EXE = os.path.join(CEINMS_DIR, 'ceinms-nn-calibrate.exe')

PRINT_TERMINAL = False







def _update():
    '''
    update the version of the present .utils package in the simulations directory with the current version of the .utils package in the code directory.

    1. Ask the user what version they want to update to 
    2. Changes the version number in the present .utils package 
    3. Commites the changes to git with a message indicating the update

    '''
    os.chdir(CODE_DIR)
    
    current_version = __version__
    print(f'Current version: {current_version}')

    new_version = input(f'Enter the new version number to update to (current: {current_version}): ')
    if new_version == current_version:
        print('New version is the same as current version. No update needed.')
        return
    
    # update version in __init__.py
    current_file = os.path.abspath(__file__)
    with open(current_file, 'r') as file:
        lines = file.readlines()
    with open(current_file, 'w') as file:
        for line in lines:
            if line.startswith('__version__'):
                file.write(f"__version__ = '{new_version}'\n")
            else:
                file.write(line)
    
    print(f'Updated version to {new_version} in {current_file}')

    # commit changes to git
    try:
        subprocess.run(['git', 'add', current_file], check=True, cwd=os.getcwd())
        commit_message = f"Update .utils version to {new_version}"
        subprocess.run(['git', 'commit', '-m', commit_message], check=True, cwd=os.getcwd())
        print(f'[Success] Updated .utils version to {new_version} and pushed to git.')
    except subprocess.CalledProcessError as e:
        print(f'[Error] Failed to commit version update to git: {e}')

def create_session(subject, session):

    subject_path = os.path.join(SIMULATIONS_DIR, subject)
    session_path = os.path.join(SIMULATIONS_DIR, subject, session)
    
    model_path = os.path.join(MODELS_DIR, subject, session)

    if not os.path.exists(session_path):
        try:
            os.makedirs(session_path, exist_ok=True)
            self._log(f'[Success] Created session directory: {session_path}', terminal=True)
        except Exception as e:
            self._log(f'[Error] Failed to create session directory: {e}', terminal=True)

    if not os.path.exists(model_path):
        try:
            os.makedirs(model_path, exist_ok=True)
            self._log(f'[Success] Created model directory: {model_path}', terminal=True)
        except Exception as e:
            self._log(f'[Error] Failed to create model directory: {e}', terminal=True)


    return session_path

## Utility functions — moved to utils/shared.py and re-exported so that
## utils.updir / utils.print_to_log / utils.time_normalise_df and every bare-name
## internal reference keep working unchanged.
from .shared import updir, print_to_log, time_normalise_df, start_logging, trial_type


def summarize_results(settings_path=None):
    """Build the results summary (figures + JASP CSV) for a project.

    Uses the folder of ``settings_path`` if given, else the current working
    directory — which must contain a ``settings.py`` and a ``summarize_results.py``.

        import bioscout
        bioscout.summarize_results()                       # cwd project
        bioscout.summarize_results(r"C:/proj/settings.py")  # explicit
    """
    import os as _os
    import runpy as _runpy
    proj = _os.path.dirname(_os.path.abspath(settings_path)) if settings_path else _os.getcwd()
    if not _os.path.exists(_os.path.join(proj, "settings.py")):
        raise FileNotFoundError(f"no settings.py in {proj} — pass settings_path=...")
    script = _os.path.join(proj, "summarize_results.py")
    if not _os.path.exists(script):
        raise FileNotFoundError(f"no summarize_results.py in {proj}")
    return _runpy.run_path(script, run_name="__main__")

# File I/O (loaders/writers/XML) moved to utils/io.py — re-exported so
# utils.load_any_data_file / utils.check_path / utils.save_pretty_xml etc. and
# every internal reference keep working unchanged.
from .io import (
    check_path, load_c3d, load_trc, load_sto, load_grf_mot,
    load_data_file, load_any_data_file, load_any_data_file_time_normalized,
    save_data_file, load_sto_header, write_trc, write_mot,
    write_sto_header, write_sto_file, read_xml, dict_to_xml,
    save_pretty_xml, edit_xml_tag_value,
)
# plotting
# Figure/axis helpers moved to utils/plotting.py (re-exported so existing
# `utils.save_fig`, `utils.mmfn`, `utils.figure_suplots_grid`, … and every
# internal reference keep working unchanged).
from .plotting import (
    save_fig, get_screen_size, calculate_nRows_nCols, figure_suplots_grid,
    mmfn, plot_mean_error_shade, add_picture_to_ax, convert_to_interactive_fig,
)

# EMG processing



# data manipulation
def time_normalise_file(filepath=None, fs=None):
    
    if filepath is None:
        filepath = input("Please provide the path to the file to be time-normalised: ").strip('"')
    
    df = load_any_data_file(filepath)
    if fs is None:
        fs = 1/(df['time'][1]-df['time'][0])
    normalised_df = time_normalise_df(df, fs)
    # save normalised file
    normalised_filepath = filepath.replace('.sto', '_timeNormalised.sto')
    write_sto_file(normalised_df, normalised_filepath)

def get_mean_across_trial_dfs(df_list, mode = 'mean') -> pd.DataFrame:
    """
    Groups a list of DataFrames by their row position and returns the mean.
    
    Args:
        df_list (list): List of DataFrames (one per trial)
        mode (str): 'mean' to calculate mean, 'median' to calculate median, 'stdev' for standard deviation.
        
    Returns:
        pd.DataFrame: A single DataFrame of 101 rows (mean of all trials)
    """
    processed_dfs = []
    
    for i, df in enumerate(df_list):
        temp_df = df.copy()
        
        # 1. Add a trial ID for tracking
        temp_df['trial_id'] = i
        
        # 2. Create a 'sample_index' (0, 1, 2...) to align trials
        # This ensures row 1 of Trial A matches row 1 of Trial B
        temp_df['sample_index'] = range(len(temp_df))
        
        processed_dfs.append(temp_df)
    
    # Combine all trials into one large DataFrame
    combined_df = pd.concat(processed_dfs, axis=0)
    
    # Group by the sample_index and calculate mean
    # We drop 'trial_id' because averaging IDs isn't useful
    if mode == 'mean':
        result_df = combined_df.groupby('sample_index').mean().drop(columns=['trial_id'], errors='ignore')
    elif mode == 'median':
        result_df = combined_df.groupby('sample_index').median().drop(columns=['trial_id'], errors='ignore')
    elif mode == 'stdev':
        result_df = combined_df.groupby('sample_index').std().drop(columns=['trial_id'], errors='ignore')
    else:
        raise ValueError("Invalid mode. Choose from 'mean', 'median', or 'stdev'.")
    
    # Reset index to make sample_index a regular column
    result_df = result_df.reset_index(drop=True)
    
    return result_df

def get_unique_names(paths):
    # Split each path into parts
    split_paths = [p.split(os.sep) for p in paths]

    # Transpose to compare columns
    columns = list(zip(*split_paths))

    # Find the indices where not all elements are the same
    diff_indices = [i for i, col in enumerate(columns) if len(set(col)) > 1]

    # Create unique names using the differing parts
    unique_names = []
    for parts in split_paths:
        unique = "_".join([parts[i] for i in diff_indices])
        unique_names.append(unique)
    return unique_names

def create_color_and_style_dict(labels):
    """Creates a color and style dictionary based on unique labels.
    Args:
        labels (list): List of unique labels.
        Returns:
        tuple: Two dictionaries, one for colors and one for styles.
            
    Example:
        labels = ['Athlete_03_sq_70', 'Athlete_03_sq_75', 'Athlete_03_sq_80']
        color_dict, style_dict = create_color_and_style_dict(labels)
        
    """
    
    
    color_dict = {}
    style_dict = {}
    # Extract the number (e.g., 70, 75, 80, 85, 90) from each label for color assignment
    # Assume the number is always at the end after an underscore
    numbers = [label.split('_')[-1] for label in labels]
    unique_numbers = sorted(set(numbers), key=lambda x: int(x))
    color_map = matplotlib.colormaps['tab10']
    number_to_color = {num: color_map.colors[i % 10] for i, num in enumerate(unique_numbers)}
    for label, num in zip(labels, numbers):
        color_dict[label] = number_to_color[num]
        if 'mri' in label.lower():
            style_dict[label] = '--'
        else:
            style_dict[label] = '-'
    return color_dict, style_dict

# Curve-agreement metrics moved to utils/stats.py (re-exported here so existing
# `utils.rmse` / `utils.rsquared` / `utils.compare_curves` / `utils.sum3d` and
# every internal reference keep working unchanged).
from .stats import rsquared, rmse, compare_curves, sum3d

# dir manipulation
def rename_all_files_in_dir(dir_path, old_str, new_str):
    """
    Renames all files in the specified directory by replacing old_str with new_str in their names.
    
    Args:
        dir_path (str): The path to the directory containing the files.
        old_str (str): The substring to be replaced in the file names.
        new_str (str): The substring to replace old_str with.
    """
    if not os.path.isdir(dir_path):
        raise ValueError(f"The provided path '{dir_path}' is not a valid directory.")
    
    for filename in os.listdir(dir_path):
        if old_str in filename:
            new_filename = filename.replace(old_str, new_str)
            try:
                os.rename(os.path.join(dir_path, filename), os.path.join(dir_path, new_filename))
                print(f"Renamed '{filename}' to '{new_filename}'")
            except Exception as e:
                print(f"Error renaming '{filename}': {e}")


class gitTools():
    def __init__(self, local_repo_path):
        self.local_repo_path = local_repo_path
        try:
            self.repo = Repo(local_repo_path)
        except Exception as e:
            print(f"Error initializing git repository at {local_repo_path}: {e}")
            self.repo = None

# ------------------------------------------------

# Katya funtions TPS
class osimTools():
    """A collection of utility functions for OpenSim and data processing.
    
    functions with '_' the object to be created first because they refer to self
    Example:
        tools = osimTools()
        tools._printHello()
        
        osimTools.calculate_emg_linear_envelope(x)
        # katya
        # Utility functions.
        #
        # author: Dimitar Stanev <jimstanev@gmail.com>
        ##
    
    """
    
    def __init__(self, filepath=None):
        self.filepath = filepath

    def _printHello(self):
        print("Hello from osimTools!")

    def calculate_emg_linear_envelope(x, f_sampling=1000, f_band_low=30,
                                    f_band_high=300, f_env=6, to_normalize=True,
                                    plot=False):
        """Calculates the EMG linear envelope by applying the following
        transformations to the raw signal:

        1) Remove mean
        2) Band-pass 4th order Butterworth filter to remove low and high frequencies
        3) Full rectification (use of abs)
        4) Normalization based on max value (if to_normalize=True)
        5) Low-pass filter to calculate the envelope
        6) (optional) plot the raw and envelop signals (if plot=True); does not show plot just in the background

        """
        f_nyq = f_sampling / 2
        # 1) remove mean
        y = x - x.mean()
        # 2) band-pass
        b, a = signal.butter(4, [f_band_low / f_nyq, f_band_high / f_nyq], 'band')
        y = signal.filtfilt(b, a, y)
        # 3) rectify
        y = np.abs(y)
        # 4) normalize
        if to_normalize:
            y = y / y.max()

        # 5) low-pass
        b, a = signal.butter(2, f_env / f_nyq, 'low')
        env = signal.filtfilt(b, a, y)
        if plot:
            plt.figure()
            plt.plot(y, label='raw')
            plt.plot(env, label='envelop')
            plt.legend()
            
        return env

    def normalize_interpolate_dataframe(df, interp_column='time', method='linear'):
        """Normalizes time between [0, 1] and then re-samples data frame at
        constant interval.

        """
        # normalize between 0, 1
        time_old = df.time.to_numpy()
        time_new = (time_old - time_old[0]) / (time_old[-1] - time_old[0])
        df.loc[:, 'time'] = time_new
        # re-sample time with specific interval
        df = df.set_index(interp_column)
        at = np.arange(0, 1.01, 0.01)
        df = df.reindex(df.index | at)
        df = df.interpolate(method=method).loc[at]
        df = df.reset_index()
        df = df.rename(columns={'index': interp_column})
        return df

    def osim_vector_to_list(array):
        """Convert SimTK::Vector to Python list.
        """
        temp = []
        for i in range(array.size()):
            temp.append(array[i])

        return temp

    def vector_vec3_to_nparray(vector):
        temp = []
        for i in range(vector.size()):
            temp.append([vector[i][0], vector[i][1], vector[i][2]])

        return np.array(temp)


    def osim_array_to_list(array):
        """Convert OpenSim::Array<T> to Python list.
        """
        temp = []
        for i in range(array.getSize()):
            temp.append(array.get(i))

        return temp


    def list_to_osim_array_str(self, list_str):
        """Convert Python list of strings to OpenSim::Array<string>."""
        arr = osim.ArrayStr()
        for element in list_str:
            arr.append(element)

        return arr


    def np_array_to_simtk_matrix(array):
        """Convert numpy array to SimTK::Matrix"""
        n, m = array.shape
        M = osim.Matrix(n, m)
        for i in range(n):
            for j in range(m):
                M.set(i, j, array[i, j])

        return M


    def rotate_data_table(table, axis, deg):
        """Rotate OpenSim::TimeSeriesTableVec3 entries using an axis and angle.

        Parameters
        ----------
        table: OpenSim.common.TimeSeriesTableVec3

        axis: 3x1 vector

        deg: angle in degrees

        """
        R = osim.Rotation(np.deg2rad(deg),
                          osim.Vec3(axis[0], axis[1], axis[2]))
        for i in range(table.getNumRows()):
            vec = table.getRowAtIndex(i)
            vec_rotated = R.multiply(vec)
            table.setRowAtIndex(i, vec_rotated)


    def mm_to_m(table, label):
        """Scale from units in mm for units in m.

        Parameters
        ----------
        label: string containing the name of the column you want to convert

        """
        c = table.updDependentColumn(label)
        for i in range(c.size()):
            c[i] = osim.Vec3(c[i][0] * 0.001, c[i][1] * 0.001, c[i][2] * 0.001)


    def mirror_z(table, label):
        """Mirror the z-component of the vector.

        Parameters
        ----------
        label: string containing the name of the column you want to convert

        """
        c = table.updDependentColumn(label)
        for i in range(c.size()):
            c[i] = osim.Vec3(c[i][0], c[i][1], -c[i][2])


    def lowess_bell_shape_kern(x, y, tau=0.0005):
        """lowess_bell_shape_kern(x, y, tau = .005) -> y_est Locally weighted
        regression: fits a nonparametric regression curve to a scatterplot. The
        arrays x and y contain an equal number of elements; each pair (x[i], y[i])
        defines a data point in the scatterplot. The function returns the estimated
        (smooth) values of y.  The kernel function is the bell shaped function with
        parameter tau. Larger tau will result in a smoother curve.

        """
        n = len(x)
        y_est = np.zeros(n)

        # initializing all weights from the bell shape kernel function
        w = np.array([np.exp(- (x - x[i]) ** 2 / (2 * tau)) for i in range(n)])

        # looping through all x-points
        for i in range(n):
            weights = w[:, i]
            b = np.array([np.sum(weights * y), np.sum(weights * y * x)])
            A = np.array([[np.sum(weights), np.sum(weights * x)],
                        [np.sum(weights * x), np.sum(weights * x * x)]])
            theta = np.linalg.solve(A, b)
            y_est[i] = theta[0] + theta[1] * x[i]

        return y_est

    def _storage_to_dataframe(self, sto):
        print('Converting OpenSim Storage to pandas DataFrame')
        
        # for i in range(sto.getSize()):print(sto.getStateVector(i).getTime())
        for i in range(sto.getSize()):print(sto.getData(i))
        sto.printToFile()
        
        
    def _create_opensim_storage(self, time, data, column_names):
        """Creates a OpenSim::Storage.

        Parameters
        ----------
        time: SimTK::Vector

        data: SimTK::Matrix

        column_names: list of strings

        Returns
        -------
        sto: OpenSim::Storage

        """
        sto = osim.Storage()
        sto.setColumnLabels(osimTools().list_to_osim_array_str(['time'] + column_names))
        for i in range(data.nrow()):
            row = osim.ArrayDouble()
            for j in range(data.ncol()):
                value = data.getElt(i, j)
                if np.isnan(value):
                    value = 0
                row.append(value)
            sto.append(time[i], row)
        
        # self._storage_to_dataframe(sto)
        return sto


    def annotate_plot(ax, text):
        """Annotate a figure by adding a text.
        """
        at = AnchoredText(text, frameon=True, loc='upper left')
        at.patch.set_boxstyle('round, pad=0, rounding_size=0.2')
        ax.add_artist(at)


    def rmse_metric(s1, s2):
        """Root mean squared error between two time series.

        """
        # Signals are sampled with the same sampling frequency. Here time
        # series are first aligned.
        # if s1.index[0] < 0:
        #     s1.index = s1.index - s1.index[0]

        # if s2.index[0] < 0:
        #     s2.index = s2.index - s2.index[0]

        t1_0 = s1.index[0]
        t1_f = s1.index[-1]
        t2_0 = s2.index[0]
        t2_f = s2.index[-1]
        t_0 = np.round(np.max([t1_0, t2_0]), 3)
        t_f = np.round(np.min([t1_f, t2_f]), 3)
        x = s1[(s1.index >= t_0) & (s1.index <= t_f)].to_numpy()
        y = s2[(s2.index >= t_0) & (s2.index <= t_f)].to_numpy()
        return np.round(np.sqrt(np.mean((x - y) ** 2)), 3)


    def refine_ground_reaction_wrench(self,data_table, label_triplet, stance_threshold,
                                    tau, debug=True):
        """Clean and filter raw ground reaction forces at a single leg as specified by
        label triplet. This algorithm checks when the foot is in touch with the
        ground (stance phase). When the foot is not in touch then the original data
        contain noise with very small SNR. Therefore, the data is either set to zero
        or to nan. Then, the data is interpolated in case of nan. Finally, the
        signals are low pass filtered using lowess_bell_shape_kern.

        Parameters
        ----------

        data_table: OpenSim::DataTable<Vec3> containing [force, point, moment] for
        each leg

        label_triplet: column identifiers for the wrench triplet (e.g., ['f1', 'p1', 'm1'])

        stance_threshold: values to consider the foot in touch with the ground

        tau: kernel standard divination (filtering)

        debug: Boolean to visualize filtering result

        Returns
        -------

        This function mutates the original data_table

        """
        # get data of single leg
        t = np.array(data_table.getIndependentColumn())
        f = data_table.updDependentColumn(label_triplet[0])
        p = data_table.updDependentColumn(label_triplet[1])
        m = data_table.updDependentColumn(label_triplet[2])
        f_l = self.vector_vec3_to_nparray(f)
        p_l = self.vector_vec3_to_nparray(p)
        m_l = self.vector_vec3_to_nparray(m)

        # debugging
        if debug:
            plt.figure()
            f1 = plt.gca()
            f1.plot(t, f_l)
            plt.figure()
            f2 = plt.gca()
            f2.plot(t, p_l)
            plt.figure()
            f3 = plt.gca()
            f3.plot(t, m_l)

        # remove information when the foot is not touching the ground
        t0 = None
        tf = None
        for i in range(len(f_l)):
            # remove noise
            if f_l[i, 1] < stance_threshold:
                for j in range(3):
                    f_l[i, j] = 0
                    p_l[i, j] = np.nan
                    m_l[i, j] = 0

            # detect heel strike
            if t0 is None and f_l[i, 1] >= stance_threshold:
                t0 = t[i]

            # detect toe off
            if tf is None and t0 is not None and f_l[i, 1] <= stance_threshold:
                tf = t[i]

        # interpolate nan values for points and moments
        f_l = pd.DataFrame(f_l).interpolate(limit_direction="both", kind="cubic").to_numpy()
        p_l = pd.DataFrame(p_l).interpolate(limit_direction="both", kind="cubic").to_numpy()
        m_l = pd.DataFrame(m_l).interpolate(limit_direction="both", kind="cubic").to_numpy()

        # filter data
        for j in range(3):
            # f_l[:, j] = signal.medfilt(f_l[:, j], median)
            f_l[:, j] = self.lowess_bell_shape_kern(t, f_l[:, j], tau)
            p_l[:, j] = self.lowess_bell_shape_kern(t, p_l[:, j], tau)
            m_l[:, j] = self.lowess_bell_shape_kern(t, m_l[:, j], tau)

        # debugging
        if debug:
            f1.plot(t, f_l)
            f2.plot(t, p_l)
            f3.plot(t, m_l)

        # update columns in the original data
        for i in range(f_l.shape[0]):
            f[i] = osim.Vec3(f_l[i, 0], f_l[i, 1], f_l[i, 2])
            p[i] = osim.Vec3(p_l[i, 0], p_l[i, 1], p_l[i, 2])
            m[i] = osim.Vec3(m_l[i, 0], m_l[i, 1], m_l[i, 2])

        return t0, tf, p_l.mean(axis=0)

    def read_from_storage(self, file_name, sampling_interval=0.01,
                        to_filter=False):
        """Read OpenSim.Storage files.

        Parameters
        ----------
        file_name: (string) path to file

        sampling_interval: resample the data with a given interval (0.01)

        to_filter: use low pass 4th order FIR filter with 6Hz cut off
        frequency

        Returns
        ------- 
        df: pandas data frame

        """
        sto = osim.Storage(file_name)
        sto.resampleLinear(sampling_interval)
        if to_filter:
            sto.lowpassFIR(4, 6)

        labels = self.osim_array_to_list(sto.getColumnLabels())
        time = osim.ArrayDouble()
        sto.getTimeColumn(time)
        time = self.osim_array_to_list(time)
        data = []
        for i in range(sto.getSize()):
            temp = self.osim_array_to_list(sto.getStateVector(i).getData())
            temp.insert(0, time[i])
            data.append(temp)

        df = pd.DataFrame(data, columns=labels)
        df.index = df.time
        return df


    def index_containing_substring(list_str, pattern):
        """For a given list of strings finds the index of the element that
        contains the substring.

        Parameters
        ----------
        list_str: list of str

        pattern: str
            pattern


        Returns
        -------
        indices: list of int
            the indices where the pattern matches

        """
        return [i for i, item in enumerate(list_str)
                if re.search(pattern, item)]


    def _plot_sto_file(self, file_name, plot_file, plots_per_row=4, pattern=None,
                    title_function=lambda x: x):
        """Plots the .sto file (OpenSim) by constructing a grid of subplots.

        Parameters
        ----------
        sto_file: str
            path to file
        plot_file: str
            path to store result
        plots_per_row: int
            subplot columns
        pattern: str, optional, default=None
            plot based on pattern (e.g. only pelvis coordinates)
        title_function: lambda
            callable function f(str) -> str
        """
        df = osimTools().read_from_storage(file_name)
        labels = df.columns.to_list()
        data = df.to_numpy()

        if pattern is not None:
            indices = self.index_containing_substring(labels, pattern)
        else:
            indices = range(1, len(labels))

        n = len(indices)
        ncols = int(plots_per_row)
        nrows = int(np.ceil(float(n) / plots_per_row))
        pages = int(np.ceil(float(nrows) / ncols))
        if ncols > n:
            ncols = n

        with PdfPages(plot_file) as pdf:
            for page in range(0, pages):
                fig, ax = plt.subplots(nrows=ncols, ncols=ncols,
                                    figsize=(8, 8))
                ax = ax.flatten()
                for pl, col in enumerate(indices[page * ncols ** 2:page *
                                                ncols ** 2 + ncols ** 2]):
                    ax[pl].plot(data[:, 0], data[:, col])
                    ax[pl].set_title(title_function(labels[col]))

                fig.tight_layout()
                pdf.savefig(fig)
                plt.close()


    def adjust_model_mass(model_file, mass_change):
        """Given a required mass change adjust all body masses accordingly.

        """
        rra_model = osim.Model(model_file)
        rra_model.setName('model_adjusted')
        state = rra_model.initSystem()
        current_mass = rra_model.getTotalMass(state)
        new_mass = current_mass + mass_change
        mass_scale_factor = new_mass / current_mass
        for body in rra_model.updBodySet():
            body.setMass(mass_scale_factor * body.getMass())

        # save model with adjusted body masses
        rra_model.printToXML(model_file)


    def replace_thelen_muscles_with_millard(model_file, target_folder):
        """Replaces Thelen muscles with Millard muscles so that we can disable
        tendon compliance and perform MuscleAnalysis to compute normalized
        fiber length/velocity without spikes.

        """
        model = osim.Model(model_file)
        new_force_set = osim.ForceSet()
        force_set = model.getForceSet()
        for i in range(force_set.getSize()):
            force = force_set.get(i)
            muscle = osim.Muscle.safeDownCast(force)
            millard_muscle = osim.Millard2012EquilibriumMuscle.safeDownCast(
                force)
            thelen_muscle = osim.Thelen2003Muscle.safeDownCast(force)
            if muscle is None:
                new_force_set.adoptAndAppend(force.clone())
            elif millard_muscle is not None:
                millard_muscle = millard_muscle.clone()
                millard_muscle.set_ignore_tendon_compliance(True)
                new_force_set.adoptAndAppend(millard_muscle)
            elif thelen_muscle is not None:
                millard_muscle = osim.Millard2012EquilibriumMuscle()
                # properties
                millard_muscle.set_default_activation(
                    thelen_muscle.getDefaultActivation())
                millard_muscle.set_activation_time_constant(
                    thelen_muscle.get_activation_time_constant())
                millard_muscle.set_deactivation_time_constant(
                    thelen_muscle.get_deactivation_time_constant())
                # millard_muscle.set_fiber_damping(0)
                # millard_muscle.set_tendon_strain_at_one_norm_force(
                #     thelen_muscle.get_FmaxTendonStrain())
                millard_muscle.setName(thelen_muscle.getName())
                millard_muscle.set_appliesForce(thelen_muscle.get_appliesForce())
                millard_muscle.setMinControl(thelen_muscle.getMinControl())
                millard_muscle.setMaxControl(thelen_muscle.getMaxControl())
                millard_muscle.setMaxIsometricForce(
                    thelen_muscle.getMaxIsometricForce())
                millard_muscle.setOptimalFiberLength(
                    thelen_muscle.getOptimalFiberLength())
                millard_muscle.setTendonSlackLength(
                    thelen_muscle.getTendonSlackLength())
                millard_muscle.setPennationAngleAtOptimalFiberLength(
                    thelen_muscle.getPennationAngleAtOptimalFiberLength())
                millard_muscle.setMaxContractionVelocity(
                    thelen_muscle.getMaxContractionVelocity())
                # millard_muscle.set_ignore_tendon_compliance(
                #     thelen_muscle.get_ignore_tendon_compliance())
                millard_muscle.set_ignore_tendon_compliance(True)
                millard_muscle.set_ignore_activation_dynamics(
                    thelen_muscle.get_ignore_activation_dynamics())
                # muscle path
                pathPointSet = thelen_muscle.getGeometryPath().getPathPointSet()
                geomPath = millard_muscle.updGeometryPath()
                for j in range(pathPointSet.getSize()):
                    pathPoint = pathPointSet.get(j).clone()
                    geomPath.updPathPointSet().adoptAndAppend(pathPoint)

                # append
                new_force_set.adoptAndAppend(millard_muscle)
            else:
                raise RuntimeError(
                    'cannot handle the type of muscle: ' + force.getName())

        new_force_set.printToXML(os.path.join(target_folder, 'muscle_set.xml'))


    def subject_specific_isometric_force(generic_model_file, subject_model_file,
                                        height_generic, height_subject):
        """Adjust the max isometric force of the subject-specific model based on results
        from Handsfield et al. 2014 [1] (equation from Fig. 5A). Function adapted
        from Rajagopal et al. 2015 [2].

        Given the height and mass of the generic and subject models, we can
        calculate the total muscle volume [1]:

        V_total = 47.05 * mass * height + 1289.6

        Since we can calculate the muscle volume and the optimal fiber length of the
        generic and subject model, respectively, we can calculate the force scale
        factor to scale the maximum isometric force of each muscle:

        scale_factor = (V_total_subject / V_total_generic) / (l0_subject / l0_generic)

        F_max_i = scale_factor * F_max_i

        [1] http://dx.doi.org/10.1016/j.jbiomech.2013.12.002
        [2] http://dx.doi.org/10.1109/TBME.2016.2586891

        """
        model_generic = osim.Model(generic_model_file)
        state_generic = model_generic.initSystem()
        mass_generic = model_generic.getTotalMass(state_generic)

        model_subject = osim.Model(subject_model_file)
        state_subject = model_subject.initSystem()
        mass_subject = model_subject.getTotalMass(state_subject)

        # formula for total muscle volume
        V_total_generic = 47.05 * mass_generic * height_generic + 1289.6
        V_total_subject = 47.05 * mass_subject * height_subject + 1289.6

        for i in range(0, model_subject.getMuscles().getSize()):
            muscle_generic = model_generic.updMuscles().get(i)
            muscle_subject = model_subject.updMuscles().get(i)

            l0_generic = muscle_generic.getOptimalFiberLength()
            l0_subject = muscle_subject.getOptimalFiberLength()

            force_scale_factor = (V_total_subject / V_total_generic) / (l0_subject /
                                                                        l0_generic)
            muscle_subject.setMaxIsometricForce(force_scale_factor *
                                                muscle_subject.getMaxIsometricForce())

        model_subject.printToXML(subject_model_file)

    def hide_muscles(self, model_file_path, hide = True):
        
        """Hide or show all muscles in the OpenSim model file.

        Parameters
        ----------
        model_file_path: str
            path to the OpenSim model file (.osim)
        hide: bool
            True to hide muscles, False to show muscles

        """
        model = osim.Model(model_file_path)
        for i in range(model.getMuscles().getSize()):
            muscle = model.updMuscles().get(i)

        model.printToXML(model_file_path)    
    ####


# Project specific command line interface
class Organise():
    def __init__(self):
        pass

    def open_dir_in_explorer(self):
        'Open the models and simulations directory in file explorer in the same window'

        try:
            # Open the first directory
            os.startfile(PROJECT_DIR)
            time.sleep(0.5)  # Small delay to ensure first window opens

        except Exception as e:
            print(f"Error opening directories: {e}")


    def rename_files_in_dir(self):
        dir_path = input("Enter directory path: ").strip('"')
        old_str = input("Enter string to be replaced: ")
        new_str = input("Enter new string: ")
        rename_all_files_in_dir(dir_path, old_str, new_str)

# Deferred imports to break circular dependency
# (these modules import utils, so they must load AFTER utils is fully defined)
try:
    from . import openSim as _openSim_mod
    openSim = _openSim_mod
except (ImportError, ValueError):
    try:
        import importlib.util as _ilu
        _op_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'openSim.py')
        _op_spec = _ilu.spec_from_file_location('openSim', _op_path)
        _op_mod = _ilu.module_from_spec(_op_spec)
        sys.modules['openSim'] = _op_mod
        _op_spec.loader.exec_module(_op_mod)
        openSim = _op_mod
    except Exception:
        openSim = None

# CEINMS helpers are bound at the BOTTOM of this file (after analysis/emg/plot
# are loaded). Loading them here, mid-init, hit an import cycle (ceinms.py ->
# import utils/settings -> back into this module before it is complete) and
# silently failed, leaving utils.ceinms = None. Placeholder until then:
ceinms = None
HAS_CEINMS = False

try:
    import emg_normalise as _emg_mod
    emg_normalise = _emg_mod
    HAS_EMG_NORMALISE = True
except ImportError:
    HAS_EMG_NORMALISE = False
    emg_normalise = None

# Analysis object model (Project -> Subject -> Session -> Trial). Loaded here,
# after Analyse is defined, because Trial subclasses Analyse. These are the
# typed entry points re-exported by the top-level `bioscout` package.
try:
    from .analysis import (
        Subject, Session, Project,
        build_model_config, discover_subjects, init_project,
        check_settings_version, migrate_settings, ensure_editor_paths,
        select_subjects, subjects_in_simulations, resolve_subject_selection,
        sessions_from_subjects, subjects_from_subjects,
    )
    from . import analysis
except Exception as _e:
    print(f"[bioscout.utils] analysis model not loaded: {_e}")


# EMG processing consolidated into utils/emg.py — re-exported here so
# utils.filter_emg / utils.normalise_emg_across_session etc. keep working.
from .emg import (
    filter_emg, filter_emg_df, filter_emg_file, amplitude_normalise_emg,
    emg_processing_file, normalise_emg_across_session, plot_emg_results,
    emg_amplitude_normalise,
)

# Plot class moved to utils/plot.py (re-exported so utils.Plot keeps working).
from .plot import Plot

# Analyse now lives in utils/analysis.py (with Project/Subject/Session).
from .analysis import Analyse

# ---------------------------------------------------------------------------
# CEINMS helpers — bound LAST, on purpose.
#
# utils/ceinms.py holds the Python helpers (create_input_data, create_ceinms_cfg,
# create_ceinms_model, calibrate, …); the sibling binary package utils/ceinms/
# shadows it on import. The package __init__ re-exports the .py helpers, so the
# package object carries both helpers and the .exe paths. Import