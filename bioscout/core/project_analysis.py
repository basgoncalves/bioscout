"""
project_analysis.py — project-level analysis across players and sessions.

Sits above the session/trial level:

    Project
    ├── Player (P03, P05, …)        ← group membership, demographics
    │   ├── Session (P03/)          ← one calibration / model
    │   │   ├── Trial (sq_bw_01/)
    │   │   └── Trial (sq_nw_01/)
    │   └── Session (P03_follow_up/)
    └── Player (P08, …)

Key entry points
----------------
load_player_results(player_id, result_type)
    → {trial_path: DataFrame}  for all sessions of that player

load_group_results(group, result_type)
    → {player_id: {trial_path: DataFrame}}

compute_mean_curve(results)
    → (mean, sd) as DataFrames/arrays, time-normalised to 0–100 %

compare_groups(groups, result_type, dof)
    → {group: {"mean": arr, "sd": arr, "n": int}}
"""

from __future__ import annotations

import sys
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# Allow import when running from inside msk_modelling_python/
_HERE = Path(__file__).parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

try:
    import numpy as np
    import pandas as pd
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

from settings import PLAYERS, SIMULATIONS_DIR, PlayerConfig


# ---------------------------------------------------------------------------
# Result file name map — extend as new pipeline outputs are added
# ---------------------------------------------------------------------------
RESULT_FILES: Dict[str, str] = {
    'ik':            'joint_angles.mot',
    'id':            'inverse_dynamics.sto',
    'so_forces':     'SO_StaticOptimization_force.sto',
    'so_activations':'SO_StaticOptimization_activation.sto',
    'ceinms_forces': None,   # located via glob (see _find_ceinms_forces)
    'grf':           'grf.mot',
    'emg':           'emg_filtered_normalised.mot',
}


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _read_mot_sto(path: Path) -> Optional["pd.DataFrame"]:
    """Read an OpenSim .mot / .sto file into a DataFrame."""
    if not _HAS_NUMPY:
        raise ImportError("numpy and pandas are required for project_analysis")
    if not path.exists():
        return None
    # Skip header lines until we hit the row containing 'time'
    with open(path, 'r', errors='replace') as fh:
        lines = fh.readlines()
    header_end = 0
    for i, line in enumerate(lines):
        if line.strip().lower().startswith('time'):
            header_end = i
            break
    try:
        df = pd.read_csv(path, sep=r'\s+', skiprows=header_end, engine='python')
        df.columns = [c.strip() for c in df.columns]
        return df
    except Exception:
        return None


def _find_ceinms_forces(trial_dir: Path) -> Optional[Path]:
    """Locate the CEINMS MuscleForces.sto inside any Execution_* sub-folder."""
    for p in sorted(trial_dir.glob('Execution_*/MuscleForces.sto')):
        return p
    return None


def _get_trial_dirs(session_dir: Path, trials_to_skip: List[str] = None) -> List[Path]:
    """Return sub-folders that look like trials (have a .mot / .sto / .c3d inside)."""
    trials_to_skip = trials_to_skip or []
    out = []
    for d in sorted(session_dir.iterdir()):
        if not d.is_dir():
            continue
        if d.name in trials_to_skip or d.name.startswith('static'):
            continue
        # Needs at least one data file to count as a trial
        has_data = any(d.glob('*.mot')) or any(d.glob('*.sto')) or any(d.glob('*.c3d'))
        if has_data:
            out.append(d)
    return out


def _sessions_for_player(player_id: str) -> List[str]:
    """Return session folder names for a player (from PLAYERS registry)."""
    cfg: PlayerConfig = PLAYERS.get(player_id)
    if cfg is None:
        return [player_id]
    return cfg.sessions if cfg.sessions else [player_id]


# ---------------------------------------------------------------------------
# Public API — loading results
# ---------------------------------------------------------------------------

def load_trial_result(
    trial_dir: Union[str, Path],
    result_type: str,
) -> Optional["pd.DataFrame"]:
    """Load a single result file from a trial directory.

    Args:
        trial_dir: absolute path to the trial folder.
        result_type: key from RESULT_FILES (e.g. 'ik', 'id', 'so_forces').

    Returns:
        DataFrame or None if the file is missing.
    """
    trial_dir = Path(trial_dir)
    if result_type == 'ceinms_forces':
        path = _find_ceinms_forces(trial_dir)
        if path is None:
            return None
    else:
        filename = RESULT_FILES.get(result_type)
        if filename is None:
            raise ValueError(f"Unknown result_type '{result_type}'. "
                             f"Valid keys: {list(RESULT_FILES)}")
        path = trial_dir / filename
    return _read_mot_sto(path)


def load_player_results(
    player_id: str,
    result_type: str,
    trials_to_skip: List[str] = None,
    simulations_dir: Path = None,
) -> Dict[str, "pd.DataFrame"]:
    """Load result files for *all sessions and trials* of one player.

    Returns:
        {str(trial_dir): DataFrame}  — keyed by the absolute trial path string.
    """
    simulations_dir = simulations_dir or SIMULATIONS_DIR
    sessions = _sessions_for_player(player_id)
    out: Dict[str, "pd.DataFrame"] = {}
    for sess in sessions:
        session_dir = Path(simulations_dir) / sess
        if not session_dir.exists():
            continue
        for trial_dir in _get_trial_dirs(session_dir, trials_to_skip):
            df = load_trial_result(trial_dir, result_type)
            if df is not None:
                out[str(trial_dir)] = df
    return out


def load_group_results(
    group: str,
    result_type: str,
    trials_to_skip: List[str] = None,
    simulations_dir: Path = None,
) -> Dict[str, Dict[str, "pd.DataFrame"]]:
    """Load results for all players belonging to *group*.

    Returns:
        {player_id: {trial_path: DataFrame}}
    """
    group_players = [pid for pid, cfg in PLAYERS.items() if cfg.group == group]
    return {
        pid: load_player_results(pid, result_type, trials_to_skip, simulations_dir)
        for pid in group_players
    }


# ---------------------------------------------------------------------------
# Public API — aggregation and statistics
# ---------------------------------------------------------------------------

def time_normalise(df: "pd.DataFrame", n_points: int = 101) -> "np.ndarray":
    """Interpolate a DataFrame to *n_points* equally spaced in 0–100 %.

    Assumes the first column (or a column named 'time') is the time axis.
    Returns a (n_points × n_cols) array, with the time column dropped.
    """
    if not _HAS_NUMPY:
        raise ImportError("numpy is required for time_normalise")
    time_col = 'time' if 'time' in df.columns else df.columns[0]
    t = df[time_col].values.astype(float)
    data = df.drop(columns=[time_col]).values.astype(float)
    t_norm = np.linspace(t[0], t[-1], n_points)
    from numpy import interp
    out = np.column_stack([interp(t_norm, t, data[:, i]) for i in range(data.shape[1])])
    return out


def compute_mean_curve(
    results: Dict[str, "pd.DataFrame"],
    n_points: int = 101,
) -> Tuple["np.ndarray", "np.ndarray", List[str]]:
    """Compute mean ± SD across a set of trials (time-normalised).

    Args:
        results: {any_key: DataFrame} — e.g. output of load_player_results.
        n_points: number of time-normalised points (default 101 = 0–100 %).

    Returns:
        (mean, sd, column_names)  each array is (n_points × n_dof).
    """
    if not _HAS_NUMPY:
        raise ImportError("numpy is required for compute_mean_curve")
    arrays = [time_normalise(df, n_points) for df in results.values() if df is not None]
    if not arrays:
        raise ValueError("No valid results to aggregate")
    # Use column names from the first DataFrame (minus time)
    first_df = next(iter(results.values()))
    time_col = 'time' if 'time' in first_df.columns else first_df.columns[0]
    col_names = [c for c in first_df.columns if c != time_col]

    stack = np.stack(arrays, axis=0)   # (n_trials, n_points, n_dof)
    return stack.mean(axis=0), stack.std(axis=0), col_names


def compare_groups(
    groups: List[str],
    result_type: str,
    dof: str,
    n_points: int = 101,
    trials_to_skip: List[str] = None,
    simulations_dir: Path = None,
) -> Dict[str, Dict]:
    """Compare group mean ± SD for a single DOF / variable.

    Args:
        groups: list of group labels (must match PlayerConfig.group).
        result_type: e.g. 'ik', 'so_forces'.
        dof: column name in the result file (e.g. 'hip_flexion_r').
        n_points: time-normalisation points.

    Returns:
        {group_label: {"mean": array(n_points,), "sd": array(n_points,), "n": int}}
    """
    if not _HAS_NUMPY:
        raise ImportError("numpy is required for compare_groups")
    out = {}
    for group in groups:
        group_data = load_group_results(group, result_type, trials_to_skip, simulations_dir)
        # Collect all trials across all players in this group
        all_curves = []
        for pid, player_results in group_data.items():
            for trial_path, df in player_results.items():
                if dof not in df.columns:
                    continue
                time_col = 'time' if 'time' in df.columns else df.columns[0]
                sub = df[[time_col, dof]].copy()
                curve = time_normalise(sub, n_points)[:, 0]
                all_curves.append(curve)
        if not all_curves:
            out[group] = {"mean": None, "sd": None, "n": 0}
        else:
            arr = np.stack(all_curves, axis=0)
            out[group] = {
                "mean": arr.mean(axis=0),
                "sd":   arr.std(axis=0),
                "n":    len(all_curves),
            }
    return out


def compare_players(
    player_ids: List[str],
    result_type: str,
    dof: str,
    n_points: int = 101,
    trials_to_skip: List[str] = None,
    simulations_dir: Path = None,
) -> Dict[str, Dict]:
    """Mean ± SD per-player for a single variable (for individual comparisons).

    Returns:
        {player_id: {"mean": array, "sd": array, "n": int, "group": str}}
    """
    if not _HAS_NUMPY:
        raise ImportError("numpy is required for compare_players")
    out = {}
    for pid in player_ids:
        player_results = load_player_results(pid, result_type, trials_to_skip, simulations_dir)
        curves = []
        for df in player_results.values():
            if dof not in df.columns:
                continue
            time_col = 'time' if 'time' in df.columns else df.columns[0]
            sub = df[[time_col, dof]].copy()
            curve = time_normalise(sub, n_points)[:, 0]
            curves.append(curve)
        group = PLAYERS.get(pid, PlayerConfig()).group
        if not curves:
            out[pid] = {"mean": None, "sd": None, "n": 0, "group": group}
        else:
            arr = np.stack(curves, axis=0)
            out[pid] = {
                "mean":  arr.mean(axis=0),
                "sd":    arr.std(axis=0),
                "n":     len(curves),
                "group": group,
            }
    return out


def list_all_players() -> Dict[str, str]:
    """Return {player_id: group} for all registered players."""
    return {pid: cfg.group for pid, cfg in PLAYERS.items()}


def list_groups() -> List[str]:
    """Return unique group labels across all registered players."""
    return sorted(set(cfg.group for cfg in PLAYERS.values() if cfg.group))
