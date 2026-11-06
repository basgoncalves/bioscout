"""Built-in ResultSet actions. Each is a plain function ``f(rs, ...)``
registered with :func:`bioscout.results.action` -- copy one to write your own."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .resultset import ResultSet, action
from .scan import split
from .windows import ID_COLS


def _by(by):
    by = split(by) or []
    bad = [b for b in by if b not in ID_COLS]
    if bad:
        raise KeyError(f"by={bad}: use ID columns {ID_COLS}")
    return by


@action
def to_bw(rs: ResultSet) -> ResultSet:
    """Divide every channel by body weight (session.yaml body_mass * 9.81) of
    each curve's own session."""
    df = rs.df.copy()
    bw = df.apply(lambda r: getattr(rs.info(r["subject"], r["session"]), "body_weight", None),
                  axis=1).astype(float)
    if bw.isna().any():
        missing = df.loc[bw.isna(), ["subject", "session"]].drop_duplicates().values.tolist()
        raise ValueError(f"no body_mass in session.yaml for {missing}")
    df[rs.vars] = df[rs.vars].div(bw, axis=0)
    return rs._new(df, unit=f"{rs.unit}/BW" if rs.unit else "BW")


@action
def mean(rs: ResultSet, by="iteration", sd=False) -> ResultSet:
    """Mean curve per group (``by`` = ID column(s)); the other ID columns become
    'mean' (or 'sd' with ``sd=True``). Needs a shared x: use a normalised
    window (window='cycle'/'stance', or normalise=True)."""
    by = _by(by)
    if rs.x != "pct":
        print("[results] mean over raw time: curves only line up if sampled identically "
              "-- use window='cycle' or normalise=True")
    g = rs.df.groupby(by + [rs.x], sort=False)[rs.vars]
    out = (g.std() if sd else g.mean()).reset_index()
    for c in ID_COLS:
        if c not in out:
            out[c] = "sd" if sd else "mean"
    return rs._new(out[ID_COLS + [rs.x] + rs.vars])


def _per_curve(rs, fn):
    rows = []
    for ids, g in rs.df.groupby(ID_COLS, sort=False):
        r = dict(zip(ID_COLS, ids))
        r.update({v: fn(g, v) for v in rs.vars})
        rows.append(r)
    out = pd.DataFrame(rows)
    keep = [c for c in ID_COLS if out[c].nunique() > 1] or ["trial"]
    return out[keep + rs.vars].set_index(keep)


@action
def peak(rs: ResultSet, how="max") -> pd.DataFrame:
    """One row per curve, one column per channel: 'max', 'min' or 'abs' peak."""
    f = {"max": np.nanmax, "min": np.nanmin,
         "abs": lambda a: a[np.nanargmax(np.abs(a))] if np.isfinite(a).any() else np.nan}[how]
    return _per_curve(rs, lambda g, v: f(g[v].to_numpy(float)))


@action
def at(rs: ResultSet, x: float) -> pd.DataFrame:
    """Value of every channel at x (percent or seconds), one row per curve."""
    def f(g, v):
        xs, ys = g[rs.x].to_numpy(float), g[v].to_numpy(float)
        ok = np.isfinite(ys)
        return float(np.interp(x, xs[ok], ys[ok])) if ok.sum() > 1 else np.nan
    return _per_curve(rs, f)


@action
def stats(rs: ResultSet) -> pd.DataFrame:
    """max / min / mean of every curve and channel, long format."""
    d = rs.df.groupby(ID_COLS, sort=False)[rs.vars].agg(["max", "min", "mean"])
    d.columns.names = ["channel", "stat"]
    return d


@action
def plot(rs: ResultSet, var=None, *, by="iteration", mean=True, ncols=3,
         title=None, save=None, **where):
    """One subplot per channel; one line (mean +- SD when several curves) per
    ``by`` group (mean +- SD only on time-normalised data). Shown inline in a
    notebook, once; written only when ``save=`` is given. Returns a Plot:
    ``p.savefig(...)``, ``p.axes``, ``p.fig`` (the matplotlib Figure)."""
    from .plotting import plot_resultset
    return plot_resultset(rs.where(**where) if where else rs, var, by=by, mean=mean,
                          ncols=ncols, title=title, save=save)
