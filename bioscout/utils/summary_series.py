"""
summary_series.py — generic, OpenSim-free helpers for turning already-computed
OpenSim result files (.sto/.mot, loaded via ``io.load_any_data_file``) into the
aggregated series used by summary/figure code.

These live in bioscout (not in a project script) so the aggregation logic is
shared: time-normalisation, mean±SD banding across reps, and the time-aligned
muscle-moment decomposition (force × moment-arm) that several figures need.
Depends only on numpy/pandas (+ bioscout.utils.stats); no OpenSim import.
"""
import numpy as np
import pandas as pd


def col(df, name):
    """Case-insensitive column lookup; None if the column (or df) is absent."""
    return None if df is None else {c.lower(): c for c in df.columns}.get(str(name).lower())


def rmse(a, b):
    """NaN-safe RMSE over the overlapping finite samples of a and b."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    m = ~(np.isnan(a) | np.isnan(b))
    return float(np.sqrt(np.mean((a[m] - b[m]) ** 2))) if m.any() else np.nan


def rsquared(a, b):
    """NaN-safe R^2 over the overlapping finite samples of a and b."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    m = ~(np.isnan(a) | np.isnan(b))
    if m.sum() < 2:
        return np.nan
    return float(np.corrcoef(a[m], b[m])[0, 1] ** 2)


def time_normalize(y, npts=101):
    """Resample a 1-D series onto ``npts`` points over 0-100 % of its own length."""
    y = pd.to_numeric(pd.Series(y), errors="coerce").to_numpy(float)
    y = y[~np.isnan(y)]
    if y.size < 2:
        return np.full(npts, np.nan)
    return np.interp(np.linspace(0, 100, npts), np.linspace(0, 100, y.size), y)


def norm_window(t, y, window=None, npts=101):
    """Time-normalise y(t) onto ``npts`` points over ``window`` = (t0, t1),
    or the full available span when ``window`` is None. Clips the window to the
    data's own time range."""
    t = np.asarray(t, float); y = np.asarray(y, float)
    g = ~(np.isnan(t) | np.isnan(y)); t, y = t[g], y[g]
    if t.size < 2:
        return np.full(npts, np.nan)
    t0, t1 = window if window else (t.min(), t.max())
    t0 = max(t0, t.min()); t1 = min(t1, t.max())
    if not (t1 > t0):
        return np.full(npts, np.nan)
    return np.interp(np.linspace(t0, t1, npts), t, y)


def band(getter, items, npts=101):
    """Stack ``getter(item)`` -> 1-D array across ``items`` -> (mean, sd).
    Skips items returning None/non-1-D/all-NaN; returns (None, None) if empty."""
    arrs = []
    for it in items:
        try:
            v = getter(it)
        except Exception:
            v = None
        if v is not None and np.ndim(v) == 1 and np.isfinite(v).any():
            arrs.append(np.asarray(v, float))
    if not arrs:
        return None, None
    M = np.vstack(arrs)
    return np.nanmean(M, 0), np.nanstd(M, 0)


def avg_items(getter, items):
    """Mean across items of ``getter(item)`` (1-D array or scalar); None if empty."""
    vals = []
    for it in items:
        try:
            v = getter(it)
        except Exception:
            v = None
        if v is not None and np.isfinite(np.asarray(v, float)).any():
            vals.append(np.asarray(v, float))
    if not vals:
        return None
    return np.nanmean(np.vstack(vals), 0) if np.ndim(vals[0]) == 1 else float(np.nanmean(vals))


def muscle_moment_pack(force_df, ma_df, id_df, dof, npts=101, sign=1.0, thresh=1e-4, window=None):
    """Time-aligned muscle-moment decomposition for one DOF.

    ``force_df`` = muscle forces (SO/CEINMS .sto), ``ma_df`` = MuscleAnalysis
    moment arms (.sto), ``id_df`` = inverse_dynamics (.sto). Each source is
    interpolated by its OWN time column onto a common grid over the overlapping
    window before multiplying force × moment-arm (their sampling can differ).
    ``sign`` flips the convention (e.g. -1 for a flipped knee).

    Returns ``(total_muscle_moment, id_moment, {muscle: series})`` each of length
    ``npts``, or ``(None, None, {})`` if inputs/columns/muscles are missing.
    """
    if force_df is None or ma_df is None or id_df is None:
        return None, None, {}
    idc = col(id_df, dof + "_moment")
    tcF, tcMA, tcID = col(force_df, "time"), col(ma_df, "time"), col(id_df, "time")
    if not (idc and tcF and tcMA and tcID):
        return None, None, {}
    muscles = [c for c in ma_df.columns if c.lower() != "time" and col(force_df, c)
               and np.nanmax(np.abs(pd.to_numeric(ma_df[c], errors="coerce"))) > thresh]
    if not muscles:
        return None, None, {}
    tF = pd.to_numeric(force_df[tcF], errors="coerce").to_numpy()
    tMA = pd.to_numeric(ma_df[tcMA], errors="coerce").to_numpy()
    tID = pd.to_numeric(id_df[tcID], errors="coerce").to_numpy()
    t0 = max(np.nanmin(tF), np.nanmin(tMA), np.nanmin(tID))
    t1 = min(np.nanmax(tF), np.nanmax(tMA), np.nanmax(tID))
    if window:                                   # crop to an analysis window (t0, t1)
        t0 = max(t0, window[0]); t1 = min(t1, window[1])
    if not (t1 > t0):
        return None, None, {}
    grid = np.linspace(t0, t1, npts)

    def ip(t, y):
        y = pd.to_numeric(pd.Series(y), errors="coerce").to_numpy()
        gm = ~(np.isnan(t) | np.isnan(y))
        return np.interp(grid, t[gm], y[gm]) if gm.sum() > 1 else np.full(npts, np.nan)

    mm = {mu: sign * ip(tF, force_df[col(force_df, mu)].values) * ip(tMA, ma_df[mu].values)
          for mu in muscles}
    total = np.nansum(np.vstack([mm[mu] for mu in muscles]), axis=0)
    idv = sign * ip(tID, id_df[idc].values)
    return total, idv, mm


def flex_ext_peaks(muscle_series):
    """From a (muscles × N) moment matrix (or iterable of 1-D series) return the
    peak of the summed positive (flexor) and summed negative (extensor) moment."""
    M = np.vstack([np.asarray(s, float) for s in muscle_series]) if len(muscle_series) else np.empty((0, 0))
    if M.size == 0:
        return np.nan, np.nan
    flex = np.nansum(np.where(M > 0, M, 0.0), axis=0)
    ext = np.nansum(np.where(M < 0, M, 0.0), axis=0)
    return float(np.nanmax(flex)), float(np.nanmin(ext))
