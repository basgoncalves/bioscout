"""Cut one result file into windows (stance / cycle / whole trial) and
optionally time-normalise each to ``points`` samples."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from .scan import SessionInfo, matches

__all__ = ["ID_COLS", "WINDOWS", "Window", "windows_for", "resample", "cut"]

ID_COLS = ["subject", "session", "iteration", "trial", "task", "cycle", "side"]
WINDOWS = ("trial", "cycle", "stance")


@dataclass
class Window:
    cycle: str
    side: str
    task: str
    t0: float
    t1: float


def _num(x) -> Optional[float]:
    try:
        x = float(x)
        return None if np.isnan(x) else x
    except (TypeError, ValueError):
        return None


def windows_for(info: SessionInfo, trial: str, window: str,
                t_data: Tuple[float, float], tasks=None) -> List[Window]:
    """The windows of one trial. ``stance`` falls back to the cycle, and a trial
    without cycles in movement_detection/cycles.csv gets one '<trial>_full'."""
    if window not in WINDOWS:
        raise ValueError(f"window={window!r}: use one of {WINDOWS}")
    task = info.tasks.get(trial, "")
    rows = info.cycles.get(trial, [])
    wins: List[Window] = []
    if window != "trial":
        for r in rows:
            t = str(r.get("task") or task)
            if tasks and not matches(t, tasks):
                continue
            a, b = (_num(r.get("stance_start")), _num(r.get("stance_end"))) \
                if window == "stance" else (None, None)
            if a is None or b is None:
                a, b = _num(r.get("t_start")), _num(r.get("t_end"))
            if a is None or b is None or b <= a:
                continue
            wins.append(Window(str(r.get("cycle")), str(r.get("side") or ""), t, a, b))
    if not wins and window == "trial" or (not wins and not rows):
        if tasks and not matches(task, tasks):
            return []
        wins.append(Window(f"{trial}_full", "", task, t_data[0], t_data[1]))
    return wins


def resample(df: pd.DataFrame, t0: float, t1: float, n: int, tol: float) -> pd.DataFrame:
    """``df`` (with 'time') on n points from t0 to t1 -> 'pct' 0..100 + channels.
    Points outside the data (beyond ``tol``) are NaN, never extrapolated."""
    t = df["time"].to_numpy(float)
    grid = np.linspace(t0, t1, n)
    vals = df.drop(columns="time").to_numpy(float)
    out = np.full((n, vals.shape[1]), np.nan)
    ok = (grid >= t[0] - tol) & (grid <= t[-1] + tol)
    if ok.any():
        g = np.clip(grid[ok], t[0], t[-1])
        for j in range(vals.shape[1]):
            col = vals[:, j]
            fin = np.isfinite(col)
            if fin.sum() >= 2:
                out[ok, j] = np.interp(g, t[fin], col[fin])
    res = pd.DataFrame(out, columns=df.columns.drop("time"))
    res.insert(0, "pct", np.linspace(0, 100, n).round(3))
    return res


def cut(df: pd.DataFrame, info: SessionInfo, iteration: str, trial: str, *,
        window="trial", points=101, normalise=True, tasks=None):
    """One file's DataFrame -> (parts, index_rows). Each part is one window with
    the ID_COLS in front, then 'pct' (normalised) or 'time', 'time_rel'."""
    t = df["time"].to_numpy(float)
    dt = float(np.median(np.diff(t))) if len(t) > 1 else 0.0
    parts, idx = [], []
    for w in windows_for(info, trial, window, (t[0], t[-1]), tasks):
        if w.t1 < t[0] - dt or w.t0 > t[-1] + dt:
            continue                       # this file does not cover the window
        if normalise:
            part = resample(df, w.t0, w.t1, points, tol=1.5 * dt)
        else:
            part = df[(df["time"] >= w.t0 - 1e-9) & (df["time"] <= w.t1 + 1e-9)].copy()
            part.insert(1, "time_rel", part["time"] - w.t0)
        ids = [info.subject, info.session, iteration, trial, w.task, w.cycle, w.side]
        for k, v in reversed(list(zip(ID_COLS, ids))):
            part.insert(0, k, v)
        parts.append(part)
        idx.append(dict(zip(ID_COLS, ids), t_start=w.t0, t_end=w.t1,
                        covered_from=t[0], covered_to=t[-1], body_mass=info.body_mass))
    return parts, idx
