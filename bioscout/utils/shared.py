"""
bioscout.utils.shared — small, dependency-light helpers needed across several
utils modules (analyse, analysis, emg, plotting, …).

Keeping them here (rather than in ``utils/__init__``) avoids import-order and
circular-import headaches: every module can do ``from bioscout.utils import
shared`` (or rely on the re-exports from ``utils/__init__``) without pulling in
the whole package.

Functions that depend on project-level globals (CODE_DIR, PRINT_TERMINAL, …)
read them lazily from ``bioscout.utils`` at call time, so they stay correct
after ``bioscout.Project`` re-points those globals at the active project.
"""
import os
import re
import sys
import time
import datetime

import numpy as np
import pandas as pd

# Trials are named "<type>_<number>" (e.g. Squat_35kg_01); this strips the
# trailing number so repetitions of the same task can be grouped/averaged.
DEFAULT_TRIAL_TYPE_PATTERN = r"(.+?)_(\d+)$"


def updir(path, levels=1):
    """Move up a directory path by a specified number of levels."""
    for _ in range(levels):
        path = os.path.dirname(path)
    return path


def print_to_log(message, terminal=None, trial=None):
    """Print a message to the console and append it to the package log file.

    Args:
        message (str): The message to print and log.
        terminal (bool|None): Force console echo; ``None`` falls back to
            ``utils.PRINT_TERMINAL``.
        trial (str): Optional trial name shown before the message.
    """
    from bioscout import utils as _u  # lazy: globals are re-pointed at runtime
    if terminal is None:
        terminal = getattr(_u, 'PRINT_TERMINAL', False)
    code_dir = getattr(_u, 'CODE_DIR', os.path.dirname(os.path.abspath(__file__)))

    timestamp = time.strftime('%d.%m.%Y_%H:%M:%S', time.localtime()) + f":{int((time.time() % 1) * 1000):03d}"
    prefix = f'[{trial}] ' if trial else ''

    with open(os.path.join(code_dir, 'log.txt'), 'a', encoding='utf-8') as log_file:
        log_file.write(f'{timestamp}: {prefix}{message}\n')

    if terminal:
        print(f'{prefix}{message}')


class _Tee:
    """Write to several streams at once (e.g. the console AND a log file)."""
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            try:
                s.write(data)
                s.flush()
            except Exception:
                pass

    def flush(self):
        for s in self.streams:
            try:
                s.flush()
            except Exception:
                pass


def start_logging(name="run", log_dir=None):
    """Tee stdout+stderr to ``<log_dir>/<name>_<timestamp>.log`` and the console.

    ``log_dir`` defaults to ``<project>/logs`` (``utils.PROJECT_DIR``), so any
    script can save a run log to the project's logs folder with one call::

        from bioscout import utils
        utils.start_logging("downsample")

    Captures Python-level output. OpenSim's C++ ``[info]`` lines are written at
    the file-descriptor level; to capture those too, also pipe the process:
    ``python ... 2>&1 | tee logs/run.log``. Returns the open log file handle.
    """
    if log_dir is None:
        from bioscout import utils as _u
        log_dir = os.path.join(getattr(_u, "PROJECT_DIR", os.getcwd()), "logs")
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, f"{name}_{datetime.datetime.now():%Y%m%d_%H%M%S}.log")
    f = open(path, "w", encoding="utf-8")
    sys.stdout = _Tee(sys.__stdout__, f)
    sys.stderr = _Tee(sys.__stderr__, f)
    print(f"[bioscout] logging this run to {path}")
    return f


def trial_type(trial_name, pattern=DEFAULT_TRIAL_TYPE_PATTERN):
    """Strip a trailing ``_<number>`` so reps of a task share a type.

    ``'Squat_35kg_02' -> 'Squat_35kg'``; names without a trailing number are
    returned unchanged.
    """
    m = re.match(pattern, str(trial_name))
    return m.group(1) if m else str(trial_name)


def time_normalise_df(df, fs=''):
    """Resample every column of ``df`` to 101 points over its time range."""
    if not type(df) == pd.core.frame.DataFrame:
        raise Exception('Input must be a pandas DataFrame')

    if 'time' not in df.columns:
        raise Exception('Input DataFrame must contain a column named "time"')

    normalised_df = pd.DataFrame(columns=df.columns)
    timeTrial = df['time'].values
    Tnorm = np.linspace(timeTrial[0], timeTrial[-1], 101)

    for column in df.columns:
        normalised_df[column] = np.zeros(101)
        currentData = df[column].values.astype(float)

        # replace NaNs with interpolated values where possible, else 0
        nan_mask = np.isnan(currentData)
        if nan_mask.all():
            currentData = np.zeros(len(timeTrial))
        elif nan_mask.any():
            currentData[nan_mask] = np.interp(
                timeTrial[nan_mask], timeTrial[~nan_mask], currentData[~nan_mask]
            )

        normalised_df[column] = np.interp(Tnorm, timeTrial, currentData)

    return normalised_df
