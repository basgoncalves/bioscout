"""Literature joint-contact-force / muscle-force curves for validation overlays.

Reads the tidy long-form ``literature/literature_curves.csv`` (digitized from
Bergmann 2001, Giarmatzis 2015, Hoang, Pandy 2021) and exposes helpers to:

  * pull a study's mean / band (lower-upper) waveform for a given variable,
    entity (joint or muscle group) and condition, and
  * overlay those bands onto an existing matplotlib axis -- e.g. the pipeline's
    joint-contact-force figure -- by mapping % gait cycle onto the plotted
    time window.

All y-values are returned in **multiples of body weight (xBW)** so they line up
with a model joint-reaction resultant normalized to body weight. Sources stored
in ``%BW`` are divided by 100; ``normalized`` muscle forces are left as-is.

CSV columns: source, variable, entity, condition, series, x, y, x_unit, y_unit
  variable : "hip_contact_force" | "muscle_force"
  entity   : "hip" | muscle group (GAS, GMAX, GMED, HAMS, IP, RF, SOL, VAS)
  series   : "mean" | "lower" | "upper" | "curve" | "peak"
  x        : % gait cycle (0-100)
"""
from __future__ import annotations

import os
from collections import defaultdict

import numpy as np

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None

from .paths import LITERATURE_CURVES_CSV
from .logutil import LOG

# joint entity -> the contact-force variable name used in the CSV.
ENTITY_VARIABLE = {
    "hip": "hip_contact_force",
    "knee": "knee_contact_force",          # total (auto-overlaid on the knee panel)
    "knee_medial": "knee_contact_force",   # compartment bands (standalone use)
    "knee_lateral": "knee_contact_force",
    "ankle": "ankle_contact_force",
}

# study curves that describe walking (vs running speeds), used as the default
# overlay set when a study is not named explicitly.
WALKING_CONDITIONS = {
    "Bergmann2001": ["walk_4kmh"],
    "Hoang": ["assisted_minmoment"],
    "Giarmatzis2015": ["6kmh"],          # slowest available (~walking)
    "Pandy2021": ["FC1"],
    "Richards2018": ["walk_normal"],     # medial-KOA measured knee contact force
}

STUDY_COLORS = {
    "Bergmann2001": "#8c564b",
    "Giarmatzis2015": "#9467bd",
    "Hoang": "#e377c2",
    "Pandy2021": "#7f7f7f",
    "Richards2018": "#8c564b",
}

# Sources whose contact-force curve covers the STANCE phase only: their 0-100%
# spans heel-strike -> ipsilateral toe-off, NOT the full stride. These are mapped
# onto the stance sub-window (when one is supplied) instead of the whole gait
# cycle, so the curve is not stretched across swing.
STANCE_ONLY = {"Hoang"}


def variable_for_entity(entity):
    """CSV ``variable`` name for a joint entity (default ``<entity>_contact_force``)."""
    return ENTITY_VARIABLE.get(entity, f"{entity}_contact_force")


def _to_xbw(y, y_unit):
    """Normalize a y series to multiples of body weight (xBW)."""
    y = np.asarray(y, float)
    if y_unit == "%BW":
        return y / 100.0
    return y  # "xBW" and "normalized" left unchanged


def load_curves(csv_path=None):
    """Load the literature curves CSV into a DataFrame (xBW-normalized ``y_xbw``)."""
    if pd is None:
        raise ImportError("pandas is required to load literature curves.")
    path = csv_path or LITERATURE_CURVES_CSV
    if not os.path.isfile(path):
        LOG.warning("literature curves not found: %s", path)
        return pd.DataFrame()
    df = pd.read_csv(path)
    # vectorised xBW normalisation: %BW -> /100; xBW / normalized left as-is.
    y = pd.to_numeric(df["y"], errors="coerce").to_numpy(dtype=float)
    factor = np.where(df["y_unit"].to_numpy() == "%BW", 1.0 / 100.0, 1.0)
    df["y_xbw"] = y * factor
    return df


def available(df=None):
    """Summarize what is in the CSV: {variable: {entity: {source: [conditions]}}}."""
    df = load_curves() if df is None else df
    out = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
    for _, r in df.iterrows():
        out[r["variable"]][r["entity"]][r["source"]].add(r["condition"])
    return {v: {e: {s: sorted(c) for s, c in se.items()}
                for e, se in ev.items()} for v, ev in out.items()}


def get_series(df, variable, entity, source=None, condition=None):
    """Return {(source, condition): {series_name: (x, y_xbw)}} matching the filters."""
    sel = df[(df["variable"] == variable) & (df["entity"] == entity)]
    if source is not None:
        sel = sel[sel["source"] == source]
    if condition is not None:
        sel = sel[sel["condition"] == condition]
    out = {}
    for (src, cond), g in sel.groupby(["source", "condition"]):
        series = {}
        for sname, gg in g.groupby("series"):
            gg = gg.sort_values("x")
            series[sname] = (gg["x"].to_numpy(), gg["y_xbw"].to_numpy())
        out[(src, cond)] = series
    return out


def _walking_defaults(df, variable, entity):
    """Pick (source, condition) pairs that correspond to walking for this entity."""
    pairs = []
    present = df[(df["variable"] == variable) & (df["entity"] == entity)]
    for src, conds in WALKING_CONDITIONS.items():
        for cond in conds:
            if not present[(present["source"] == src)
                           & (present["condition"] == cond)].empty:
                pairs.append((src, cond))
    return pairs


def overlay_joint_contact_force(ax, entity="hip", df=None, sources=None,
                                condition=None, gait_window=None, stance_window=None,
                                bands=True, label_prefix="", central=True,
                                band_alpha=0.15, line_alpha=0.60, line_width=1.8):
    """Overlay literature contact-force bands on an existing axis.

    Parameters
    ----------
    ax : matplotlib axis whose x-axis is TIME (seconds) over one motion cycle.
    entity : joint entity to overlay (default "hip").
    df : pre-loaded DataFrame (loaded from bundle if None).
    sources : list of study names to include; None -> the walking defaults.
    condition : force a specific condition; None -> per-source walking default.
    gait_window : (t0, t1) time window that maps to 0-100 % gait cycle;
        None -> the axis' current x-limits.
    bands : draw lower-upper (or mean +/- ) shaded band when available.
    central : draw the central (mean/curve) line. Set False to show only the
        shaded band (cleaner overlay). Sources with no band fall back to a
        faint central line so they are not lost.
    band_alpha : transparency of the shaded band.

    Returns the list of study labels drawn (for legend handling upstream).
    """
    df = load_curves() if df is None else df
    if df.empty:
        return []
    if gait_window is None:
        gait_window = ax.get_xlim()
    t0, t1 = gait_window

    def _mapper(src):
        """x-mapping for this source: stance-only sources map 0-100 % onto the
        stance sub-window (if given), everyone else onto the full gait cycle."""
        w0, w1 = (stance_window if (stance_window and src in STANCE_ONLY)
                  else (t0, t1))
        return lambda pct: w0 + (np.asarray(pct, float) / 100.0) * (w1 - w0)

    variable = variable_for_entity(entity)
    if sources is None and condition is None:
        pairs = _walking_defaults(df, variable, entity)
    else:
        got = get_series(df, variable, entity,
                         source=None, condition=condition)
        pairs = [k for k in got
                 if (sources is None or k[0] in sources)]

    drawn = []
    for (src, cond) in pairs:
        series = get_series(df, variable, entity,
                            source=src, condition=cond).get((src, cond), {})
        color = STUDY_COLORS.get(src, "#888888")
        stance = src in STANCE_ONLY and stance_window is not None
        suffix = " [stance]" if stance else ""
        label = f"{label_prefix}{src} ({cond}){suffix}"
        _map_x = _mapper(src)
        central_data = series.get("mean") or series.get("curve") or series.get("peak")
        has_band = bands and "lower" in series and "upper" in series
        # central line (only when requested)
        if central and central_data is not None:
            x, y = central_data
            ax.plot(_map_x(x), y, color=color, lw=1.6, ls="-",
                    label=label, zorder=1)
            drawn.append(label)
        # shaded band from lower/upper when present; carries the legend label
        # when the central line is suppressed.
        if has_band:
            xl, yl = series["lower"]
            xu, yu = series["upper"]
            xs = np.linspace(0, 100, 101)
            yl_i = np.interp(xs, xl, yl)
            yu_i = np.interp(xs, xu, yu)
            band_label = None if (central and central_data is not None) else label
            ax.fill_between(_map_x(xs), yl_i, yu_i, color=color, alpha=band_alpha,
                            zorder=0, label=band_label)
            if band_label:
                drawn.append(band_label)
        elif not central and central_data is not None:
            # no variance band in the dataset -> show the mean as a dashed
            # reference line (thicker, lightly transparent so it stays readable).
            x, y = central_data
            ax.plot(_map_x(x), y, color=color, lw=line_width, ls="--",
                    alpha=line_alpha, label=label, zorder=1)
            drawn.append(label)
    return drawn


def plot_jcf_validation(out_path, entity="hip", model=None, df=None,
                        sources=None, condition=None, title=None):
    """Standalone literature joint-contact-force reference figure.

    Independent of the pipeline: plots the literature bands (xBW vs % gait cycle)
    for ``entity`` and, if given, overlays a model resultant.

    Parameters
    ----------
    out_path : where to save the PNG.
    model : optional ``(x_pct, y_xbw)`` model curve already expressed in
        % gait cycle and multiples of body weight.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = load_curves() if df is None else df
    variable = variable_for_entity(entity)
    fig, ax = plt.subplots(figsize=(8, 5))
    # plot literature on a native 0-100 % gait-cycle axis
    ax.set_xlim(0, 100)
    if sources is None and condition is None:
        pairs = _walking_defaults(df, variable, entity)
    else:
        pairs = [k for k in get_series(df, variable, entity,
                                       condition=condition)
                 if (sources is None or k[0] in sources)]
    for (src, cond) in pairs:
        series = get_series(df, variable, entity,
                            source=src, condition=cond).get((src, cond), {})
        color = STUDY_COLORS.get(src, "#888888")
        central = series.get("mean") or series.get("curve") or series.get("peak")
        if central is not None:
            x, y = central
            ax.plot(x, y, color=color, lw=1.8, label=f"{src} ({cond})")
        if "lower" in series and "upper" in series:
            xs = np.linspace(0, 100, 101)
            yl = np.interp(xs, *series["lower"])
            yu = np.interp(xs, *series["upper"])
            ax.fill_between(xs, yl, yu, color=color, alpha=0.15)

    if model is not None:
        mx, my = model
        ax.plot(mx, my, "k--", lw=2.2, label="model")

    ax.set_xlabel("% gait cycle")
    ax.set_ylabel(f"{entity} contact force (xBW)")
    ax.set_title(title or f"Literature {entity} contact force vs model")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    return out_path
