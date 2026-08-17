"""Fibre operating point on the Hill force-length-velocity surface.

Generic, project-agnostic drawing code. Callers hand over already-reduced
traces; nothing in here knows about sessions, tasks or models.

    from bioscout.muscle_inspect.fl_fv_surface import plot_fl_fv_surface

    panels = [dict(title="Squat 35kg", series=[
        dict(name="cateli", ls="-",  marker="o",
             data={"Vasti": dict(l=..., v=..., fn=..., wpos=.., wneg=..)}),
        dict(name="gpk",    ls="--", marker="X", data={...}),
    ])]
    plot_fl_fv_surface(panels, groups, colors, "out.png")

WHAT THE SURFACE IS
    f(l~, v~) = f_L(l~) . f_V(v~) at full activation, Thelen (2003) defaults --
    the MODEL's capacity, not any one subject's. Height = the fraction of peak
    isometric force a fibre can make at that normalised length and velocity.
    Negative v~ is SHORTENING (OpenSim convention) and is plotted to the LEFT.

WHAT A TRACE IS
    One muscle group over one movement cycle, force-weighted across its heads.
    The marker sits at that group's instant of PEAK force.
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
from matplotlib.colors import to_rgb
from mpl_toolkits.mplot3d.art3d import Line3DCollection

# the plotted domain
LLIM = (0.4, 1.7)
VLIM = (-1.0, 1.0)
ZMAX = 1.45          # just above F_ecc_max
ZPAD = 0.012         # lift markers off the sheet
VMAX_LOPT_PER_S = 10.0   # v_max for the rigid-tendon velocity estimate


# =============================================================================
# the Hill surface
# =============================================================================

def hill_value(L, V, kshape=0.45, af=0.25, flen=1.4):
    """f_L(l~) . f_V(v~) at full activation -- Thelen 2003 defaults."""
    L, V = np.asarray(L, float), np.asarray(V, float)
    fL = np.exp(-((L - 1.0) ** 2) / kshape)
    vm = 1.0
    fV = np.where(
        V <= 0,
        (vm + V) / np.maximum(vm - V / af, 1e-9),                       # conc
        (vm * (flen - 1.0) + (flen + flen / af) * V)
        / np.maximum(vm * (flen - 1.0) + (1.0 + 1.0 / af) * V, 1e-9))   # ecc
    return np.clip(fL * fV, 0, flen)


def hill_surface(nl=161, nv=161):
    """(l, v, L, V, S) -- the multiplier on a (l~, v~) grid."""
    l = np.linspace(*LLIM, nl)
    v = np.linspace(*VLIM, nv)
    L, V = np.meshgrid(l, v)
    return l, v, L, V, hill_value(L, V)


def mask_out_of_domain(L, V, where=""):
    """NaN out samples off the plotted sheet -- a 3D axes does NOT clip."""
    L, V = np.asarray(L, float).copy(), np.asarray(V, float).copy()
    bad = ~((LLIM[0] <= L) & (L <= LLIM[1]) & (VLIM[0] <= V) & (V <= VLIM[1]))
    if bad.all():
        print(f"[skip] {where}: entirely outside the surface")
    elif bad.any():
        print(f"[trim] {where}: {bad.sum()}/{bad.size} samples off-surface")
    L[bad] = np.nan
    V[bad] = np.nan
    return L, V


# =============================================================================
# muscle parameters + the rigid-tendon fibre estimate
# =============================================================================

def osim_muscle_params(model_path):
    """{muscle: dict(f0, lopt, lts, pennation)} out of an .osim."""
    out = {}
    if not model_path or not os.path.isfile(model_path):
        return out
    keys = dict(f0="max_isometric_force", lopt="optimal_fiber_length",
                lts="tendon_slack_length",
                pennation="pennation_angle_at_optimal")
    for el in ET.parse(model_path).getroot().iter():
        if not el.get("name") or el.find(keys["lopt"]) is None:
            continue
        d = {}
        for k, tag in keys.items():
            n = el.find(tag)
            try:
                d[k] = float(n.text)
            except (AttributeError, TypeError, ValueError):
                d[k] = np.nan
        out[el.get("name")] = d
    return out


def rigid_tendon_states(t, lmt, par, vmax=VMAX_LOPT_PER_S):
    """(l~, v~) from muscle-tendon length under a RIGID tendon assumption.

    l_fibre = (l_MT - l_TS) / cos(pennation);  l~ = l_fibre / l_opt
    v~      = d(l~)/dt / vmax          (vmax in optimal fibre lengths per second)

    Needed wherever OpenSim's MuscleAnalysis fibre output is degenerate (a
    constant fibre length means it never solved fibre equilibrium, and its
    velocity column is then the derivative of a flat line).
    """
    lopt, lts = par.get("lopt", np.nan), par.get("lts", 0.0)
    pen = par.get("pennation", 0.0) or 0.0
    if not np.isfinite(lopt) or lopt <= 0:
        return None, None
    ln = (np.asarray(lmt, float) - (lts or 0.0)) / max(np.cos(pen), 1e-6) / lopt
    return ln, np.gradient(ln, np.asarray(t, float)) / vmax


# =============================================================================
# reduction helpers
# =============================================================================

def force_weights(F):
    """(weights, total force) for the heads of one group, per sample.

    Public so a caller can average a FURTHER per-head signal -- activation, say
    -- with exactly the weights the fibre state was averaged with.
    """
    F = np.vstack(F)
    tot = np.nansum(F, axis=0)
    w = np.where(tot > 0, 1.0, 0.0) * F / np.where(tot > 0, tot, 1.0)
    return w + np.where(tot > 0, 0.0, 1.0 / F.shape[0]), tot   # else a plain mean


def weighted_group_trace(F, L, V, F0):
    """Force-weighted (l~, v~) of one group + its normalised force.

    F/L/V are (n_heads, n_samples); F0 the summed peak isometric force.
    """
    w, tot = force_weights(F)
    fn = tot / F0 if F0 and F0 > 0 else tot * np.nan
    return (np.nansum(w * np.vstack(L), axis=0),
            np.nansum(w * np.vstack(V), axis=0), fn)


def finish_trace(l, v, fn, wpos=np.nan, wneg=np.nan, where="", act=None,
                 **extra):
    """Mask, find the peak-force instant, and package one trace.

    Anything passed as **extra rides along on the trace -- e.g. `peak_bw=` for
    a second force scale the numbers block can rank and print.
    """
    l, v = mask_out_of_domain(l, v, where)
    if not np.isfinite(l).any():
        return None
    ok = np.isfinite(fn * l)
    ipk = int(np.nanargmax(np.where(np.isfinite(l), fn, np.nan))) if ok.any() else 0
    act = None if act is None else np.asarray(act, float)
    return dict(l=l, v=v, fn=fn, wpos=wpos, wneg=wneg, act=act,
                # activation AT the instant of peak force -- the height the
                # fibre actually reached is act * f(l~, v~), not f(l~, v~)
                act_pk=(float(act[ipk]) if act is not None
                        and np.isfinite(act[ipk]) else np.nan),
                # TOTAL work done, positive + negative as magnitudes -- not the
                # net, which cancels an eccentric-concentric cycle to ~nothing
                work_abs=abs(wpos) + abs(wneg),
                lmin=float(np.nanmin(l)), lmax=float(np.nanmax(l)),
                vmin=float(np.nanmin(v)), vmax=float(np.nanmax(v)),
                peak=float(np.nanmax(fn)) if np.isfinite(fn).any() else np.nan,
                ipk=ipk, **extra)


# =============================================================================
# drawing
# =============================================================================

DEFAULT_COLUMNS = (
    dict(key="work_abs", head="Wtot (J)", fmt=".0f", cw=4),
    dict(key="peak",     head="F/F0",    fmt=".2f", cw=4),
    dict(key="range:l",  head="l~ rng", fmt=".1f", cw=6),
    dict(key="range:v",  head="v~ rng", fmt=".1f", cw=7),
    dict(key="act_pk",   head="a@Fpk",  fmt=".2f", cw=4),
)
RULE = "\u2502"          # the vertical rule between columns

# when colour codes the SERIES (model), the group has to be coded by stroke
GROUP_LS = ["-", "--", ":", "-.", (0, (3, 1, 1, 1)), (0, (5, 1)), (0, (1, 1))]
GROUP_MK = ["o", "X", "s", "^", "D", "P", "v"]


ACT_LW = (0.8, 5.5)      # stroke width at a = 0 and a = 1
ACT_FADE = 0.80          # how far an unactivated segment washes out to white


def _dash_mask(n, ls, on=5, off=4):
    """Which of `n` path segments to draw, so a THICK ribbon reads as dashed.

    A per-segment collection cannot hold a dash pattern -- matplotlib would
    restart it inside every one-sample segment and the result looks solid. The
    gaps are cut out of the segment list instead.
    """
    if ls in ("-", "solid", None):
        return np.ones(n, bool)
    k = np.arange(n) % (on + off)
    return k < on


def _activation_underlay(ax, x, y, z, base, a, zorder=5.5, ls="-"):
    """Redraw the path as a per-segment ribbon whose weight IS the activation.

    The sheet is capacity at a = 1, so a path drawn on it says where the fibre
    COULD make force, never how much of that it took up. Thickness and darkness
    carry `a` along the whole cycle: fat and saturated where the muscle is
    driven hard, thin and washed out where it is coasting.

    Drawn as an UNDERLAY, with the identity line (its colour, its dash pattern)
    still on top -- a per-segment collection cannot hold a dash pattern, and in
    the by-model figure the dashes are what name the muscle.
    """
    if a is None:
        return
    p = np.column_stack([np.asarray(x, float), np.asarray(y, float),
                         np.asarray(z, float)])
    a = np.asarray(a, float)
    segs, lws, cols = [], [], []
    rgb = np.asarray(to_rgb(base), float)
    keep = _dash_mask(len(p) - 1, ls)
    for i in range(len(p) - 1):
        if not keep[i]:
            continue
        am = np.nanmean(a[i:i + 2])
        if not np.isfinite(p[i]).all() or not np.isfinite(p[i + 1]).all() \
                or not np.isfinite(am):
            continue
        am = float(np.clip(am, 0.0, 1.0))
        segs.append([p[i], p[i + 1]])
        lws.append(ACT_LW[0] + (ACT_LW[1] - ACT_LW[0]) * am)
        # blend toward white rather than using alpha: transparency wrecks
        # matplotlib's 3D depth sorting
        cols.append(tuple(rgb + (1.0 - rgb) * ACT_FADE * (1.0 - am)))
    if not segs:
        return
    lc = Line3DCollection(segs, linewidths=lws, colors=cols,
                          capstyle="round", zorder=zorder)
    lc.set_sort_zpos(None)
    ax.add_collection3d(lc)


def _activation_scale(fig, rect, n=9):
    """A key for the activation encoding: stroke weight AND shade against a.

    A plain colourbar cannot say this -- the ramp runs in TWO channels at once,
    and the hue is the model's, not the scale's. So the key is a stack of real
    strokes in neutral grey, drawn with the same lw/blend the paths use.
    """
    ax = fig.add_axes(rect, zorder=6)
    rgb = np.zeros(3)                      # neutral: the models supply the hue
    for a in np.linspace(0, 1, n):
        ax.plot([0.06, 0.94], [a, a],
                lw=ACT_LW[0] + (ACT_LW[1] - ACT_LW[0]) * a,
                color=tuple(rgb + (1.0 - rgb) * ACT_FADE * (1.0 - a)),
                solid_capstyle="round")
    ax.set_xlim(0, 1); ax.set_ylim(-0.06, 1.06)
    ax.set_xticks([])
    ax.yaxis.tick_right(); ax.yaxis.set_label_position("right")
    ax.set_yticks([0, 0.5, 1.0])
    ax.tick_params(labelsize=7, length=2, pad=1)
    ax.set_ylabel("activation  a", fontsize=8, labelpad=2)
    for sp in ("top", "bottom", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["right"].set_color("0.7")
    return ax


def _style(panel, groups, colors, color_by, s, g, style_by=None):
    """(colour, linestyle, marker) for one series x group cell.

    color_by  which dimension carries COLOUR -- "group" (the muscle) or
              "series" (the model, in the manuscript palette).
    style_by  which carries the STROKE. Defaults to the other one, but they can
              be the SAME: with one muscle a figure, colour is the model and the
              stroke is the model's algorithm, and the group codes nothing.
    """
    style_by = style_by or ("group" if color_by == "series" else "series")
    i = groups.index(g) if g in groups else 0
    col = s.get("color", "0.3") if color_by == "series" else colors[g]
    if style_by == "group":
        return col, GROUP_LS[i % len(GROUP_LS)], GROUP_MK[i % len(GROUP_MK)]
    return col, s.get("ls", "-"), s.get("marker", "o")


def _trim0(x, fmt):
    """0.72 -> '.7', -0.31 -> '-.3' at fmt='.1f'."""
    t = format(x, fmt)
    return t.replace("-0.", "-.").replace("0.", ".", 1) if t.startswith(
        ("0.", "-0.")) else t


def _value(d, spec):
    """The scalar a column compares across series (a range compares its SPAN)."""
    if not d:
        return np.nan
    key = spec["key"]
    if key.startswith("range:"):
        a, b = d.get(key[6:] + "min"), d.get(key[6:] + "max")
        return (b - a) if a is not None and b is not None else np.nan
    x = d.get(key)
    return x if x is not None else np.nan


def _spread_pct(vals):
    """Peak-to-peak disagreement across the series, as % of the mean."""
    vs = [float(x) for x in vals if x is not None and np.isfinite(x)]
    if len(vs) < 2:
        return 0.0
    m = abs(np.mean(vs))
    return 100.0 * (max(vs) - min(vs)) / m if m > 1e-9 else 0.0


def _cell(d, spec):
    """One series' value for one column. `range:x` prints xmin/xmax."""
    key, fmt = spec["key"], spec.get("fmt", ".2f")
    if not d:
        return "-"
    if key.startswith("range:"):
        a, b = d.get(key[6:] + "min"), d.get(key[6:] + "max")
        if a is None or b is None or not np.isfinite(a) or not np.isfinite(b):
            return "-"
        # drop the leading zero (".7/1.3", "-.2/-.1") -- four columns of
        # model>model>model only fit across a panel without it
        return f"{_trim0(a, fmt)}/{_trim0(b, fmt)}"
    x = d.get(key) if d else None
    return format(x, fmt) if x is not None and np.isfinite(x) else "-"


def _draw_rows(ax, rows, three_d, fontsize, ncha):
    """Paint [(colour, [(char offset, text, bold)])] as a monospace table."""
    txt = ax.text2D if three_d else ax.text
    pos = ax.get_position()
    fw_in, fh_in = ax.figure.get_size_inches()
    h_pt = max(pos.height * fh_in, 0.1) * 72
    w_pt = max(pos.width * fw_in, 0.1) * 72
    # AUTO-FIT: `fontsize` is a cap; shrink until the widest row fits the axes
    fs = min(fontsize, 0.98 * w_pt / (ncha * 0.602))
    dx, dy = fs * 0.602 / w_pt, (fs + 1.8) / h_pt
    y0 = 1.0 + dy * (len(rows) + 0.3) if three_d else 0.995
    for i, (col, segs) in enumerate(rows):
        for x0, t, bold in segs:
            txt(0.005 + x0 * dx, y0 - dy * i, t, transform=ax.transAxes,
                color=col, fontsize=fs, family="DejaVu Sans Mono",
                fontweight="bold" if bold else "normal",
                va="top", ha="left", zorder=10)


def _sub_table(ax, panel, groups, three_d, columns, fontsize, flag_pct):
    """One row per MODEL, every metric split into SO / EMG sub-columns.

    Series carry `row_key` (the model), `sub` (the algorithm) and `color`. Each
    row holds one muscle group -- the figures that use this are one muscle per
    row -- so a cell is a single number per sub-column, not a chain.

    Two markers, two questions:
      *  on the metric heading -- the MODELS disagree by > flag_pct %
      #  after a row's pair    -- SO and EMG disagree for THAT model
    """
    ser = [s for s in panel["series"] if s.get("data")]
    if not ser:
        return
    subs, ents, tint = [], [], {}
    for s in ser:
        if s.get("sub") not in subs:
            subs.append(s.get("sub"))
        k = s.get("row_key") or s.get("name")
        if k not in ents:
            ents.append(k); tint[k] = s.get("color", "0.25")

    def trace(e, sub):
        for s in ser:
            if (s.get("row_key") or s.get("name")) == e and s.get("sub") == sub:
                d = s["data"] or {}
                return next((d[g] for g in groups if g in d), None)
        return None

    ns = len(subs)
    wid, heads = [], []
    for c in columns:
        # models disagree on this metric, under EITHER algorithm?
        star = flag_pct and any(
            _spread_pct([_value(trace(e, sub), c) for e in ents]) > flag_pct
            for sub in subs)
        heads.append(c["head"] + ("*" if star else ""))
        wid.append(max(len(heads[-1]), ns * c["cw"] + ns - 1 + 1))

    def segments(lab, cells, bold):
        segs, pos = [], 0
        t = f"{lab:<15.15s}"
        segs.append((pos, t, False)); pos += len(t)
        for cell, w in zip(cells, wid):
            segs.append((pos, " " + RULE + " ", False)); pos += 3
            t = f"{cell:>{w}s}"
            segs.append((pos, t, bold)); pos += len(t)
        return segs

    rows = [("0.45", segments("", heads, False)),
            ("0.45", segments("", [" ".join(f"{str(x):>{c['cw']}s}"
                                            for x in subs)
                                   for c in columns], False))]
    for e in ents:
        cells = []
        for c in columns:
            ds = [trace(e, sub) for sub in subs]
            hash_ = (flag_pct and
                     _spread_pct([_value(d, c) for d in ds]) > flag_pct)
            cells.append(" ".join(f"{_cell(d, c):>{c['cw']}s}" for d in ds)
                         + ("#" if hash_ else ""))
        rows.append((tint[e], segments(e, cells, False)))
    ncha = max(max(x0 + len(t) for x0, t, _ in segs) for _, segs in rows)
    _draw_rows(ax, rows, three_d, fontsize, ncha)


def _numbers_block(ax, panel, groups, colors, three_d=True,
                   columns=DEFAULT_COLUMNS, rank_by=None, fontsize=8.0,
                   color_by="group", flag_pct=10.0, rows_are="group"):
    """A small monospace table above the panel.

    rows_are "group"   one row per muscle, each cell chaining the series
                       (model1>model2>model3). A cell whose series disagree by
                       more than `flag_pct` % of their mean is `*` and BOLD.
    rows_are "series"  one row per series, in that series' own colour, each
                       cell chaining the groups. With a single muscle on the
                       figure that is one plain number per column, so the
                       disagreement marker moves onto the column HEADING.

    `fontsize` is a CAP: the table auto-shrinks to fit the axes, so adding a
    column can never silently spill it across the neighbouring panel.
    """
    MONO_ADV = 0.602        # DejaVu Sans Mono advance width, in em
    ser = panel["series"]

    if rows_are == "series" and any(s.get("sub") for s in ser):
        return _sub_table(ax, panel, groups, three_d, columns, fontsize,
                          flag_pct)
    if rows_are == "series":
        ents = [s for s in ser if s.get("data")]
        chain = [g for g in groups
                 if any((s["data"] or {}).get(g) for s in ser)]
        label = lambda e: str(e.get("short") or e["name"])          # noqa: E731
        tint = lambda e: (e.get("color", "0.25")                    # noqa: E731
                          if color_by == "series" else "0.25")
        cell = lambda e, c: (e["data"] or {}).get(c)                # noqa: E731
        chain_names = [str(c)[:10] for c in chain]
    else:
        ents = [g for g in groups
                if any((s["data"] or {}).get(g) for s in ser)]
        chain = ser
        label = lambda e: str(e)                                    # noqa: E731
        tint = lambda e: (colors[e] if color_by == "group" else "0.25")  # noqa: E731
        cell = lambda e, c: (c["data"] or {}).get(e)                # noqa: E731
        chain_names = [str(c.get("short") or c["name"])[:6] for c in chain]
    if not ents or not chain:
        return

    if rank_by:
        def rank(e):
            vs = [cell(e, c) for c in chain]
            vs = [d.get(rank_by, np.nan) for d in vs if d]
            vs = [x for x in vs if x is not None and np.isfinite(x)]
            return -max(vs) if vs else np.inf     # metric-less rows go last
        ents = sorted(ents, key=rank)

    # rows_are "series": the disagreement is BETWEEN rows, so it belongs on the
    # heading -- one row is one model and has nothing to disagree with itself
    head_flag = [False] * len(columns)
    if rows_are == "series" and flag_pct:
        columns = list(columns)
        for j, c in enumerate(columns):
            sp = _spread_pct([_value(cell(e, ch), c)
                              for e in ents for ch in chain])
            head_flag[j] = sp > flag_pct
            if head_flag[j]:
                columns[j] = dict(c, head=c["head"] +
                                  ("**" if sp > 2.5 * flag_pct else "*"))

    n = len(chain)
    wid = [max(len(c["head"]), n * c["cw"] + n - 1 + 2) for c in columns]

    def segments(lab, cells, flags):
        """[(char offset, text, bold)] -- one artist per cell, since matplotlib
        cannot bold PART of a text. Bold and regular DejaVu Sans Mono share an
        advance width, so the columns stay aligned either way.

        Values and headings are both RIGHT-aligned in their field, so the
        numbers line up under their own heading and can be compared down the
        column. Vertical rules only -- horizontal ones just add ink.
        """
        segs, pos = [], 0
        t = f"{lab:<15.15s}"
        segs.append((pos, t, False)); pos += len(t)
        for c, w, fl in zip(cells, wid, flags):
            segs.append((pos, " " + RULE + " ", False)); pos += 3
            t = f"{c:>{w}s}"
            segs.append((pos, t, fl)); pos += len(t)
        return segs

    rows = []
    for e in ents:
        cells, flags = [], []
        for c in columns:
            ds = [cell(e, ch) for ch in chain]
            txt = ">".join(_cell(d, c) for d in ds)
            sp = (_spread_pct([_value(d, c) for d in ds])
                  if flag_pct and rows_are != "series" else 0.0)
            cells.append(txt + ("**" if sp > 2.5 * flag_pct else
                                "*" if sp > flag_pct else ""))
            flags.append(sp > flag_pct)          # starred cells are bold too
        rows.append((tint(e), segments(label(e), cells, flags)))
    rows.insert(0, ("0.45", segments("", [c["head"] for c in columns],
                                     head_flag)))
    if n > 1:
        rows.insert(0, ("0.45", [(0, "cells: " + ">".join(chain_names), False)]))

    ncha = max(max(x0 + len(t) for x0, t, _ in segs) for _, segs in rows)
    _draw_rows(ax, rows, three_d, fontsize, ncha)


def _panel(ax, grid, panel, groups, colors, elev, azim, first,
           color_by="group", style_by=None):
    l, v, L, V, S = grid
    ax.view_init(elev=elev, azim=azim)
    ax.set_box_aspect((1.0, 1.0, 0.62), zoom=1.22)
    # ORTHOGRAPHIC, not the matplotlib default perspective: under perspective
    # the vertical rails converge on screen and read as tilted, and two bars at
    # different depths get different apparent slopes.
    ax.set_proj_type("ortho")
    # honour explicit zorder: the default camera puts the operating points just
    # over the crest, so true depth sorting would hide nearly all of them.
    ax.computed_zorder = False

    ax.plot_surface(V, L, S, rstride=8, cstride=8, color="0.88",
                    edgecolor="0.45", linewidth=0.3, shade=False,
                    antialiased=True, zorder=1)
    ax.contour(V, L, S, levels=np.linspace(0.2, 1.4, 7), zdir="z", offset=0.0,
               colors="0.72", linewidths=0.5, zorder=0)
    # Reference slices ON the sheet: the isometric ridge (v~ = 0, i.e. the
    # force-length curve) and the optimum-length slice (l~ = 1, the
    # force-velocity curve). They only survive because computed_zorder is off --
    # under depth sorting a line lying on a surface is sorted per-quad and comes
    # out as disconnected fragments. Drawn UNDER the muscle paths (zorder 6).
    ax.plot(np.zeros_like(l), l, hill_value(l, np.zeros_like(l)) + ZPAD,
            color="#C0392B", ls="--", lw=1.4, zorder=5)        # isometric f-L
    ax.plot(v, np.ones_like(v), hill_value(np.ones_like(v), v) + ZPAD,
            color="#2E5FA3", ls="--", lw=1.4, zorder=5)        # f-V at l~ = 1

    for s in panel["series"]:
        for g in groups:
            d = (s["data"] or {}).get(g)
            if d is None:
                continue
            col, ls, mk = _style(panel, groups, colors, color_by, s, g,
                                 style_by)
            zz = hill_value(d["l"], d["v"]) + ZPAD
            _activation_underlay(ax, d["v"], d["l"], zz, col, d.get("act"),
                                 ls=ls)
            ax.plot(d["v"], d["l"], zz, ls=ls, color=col,
                    lw=1.0, alpha=0.95, zorder=6)
            i = d["ipk"]
            if np.isfinite(d["l"][i]) and np.isfinite(d["v"][i]):
                ax.scatter([d["v"][i]], [d["l"][i]], [zz[i]], marker=mk, s=55,
                           color=col, edgecolors="w", linewidths=1.0,
                           depthshade=False, zorder=7)

    # Range rails on the box edges. They follow the COLOUR dimension: one rail
    # per muscle when colour is the muscle, one per series when colour is the
    # model -- a neutral rail next to coloured paths says nothing.
    if color_by == "series":
        rails = [(s.get("color", "0.45"), s.get("ls", "-"),
                  [d for g in groups if (d := (s["data"] or {}).get(g))])
                 for s in panel["series"]]
    else:
        rails = [(colors[g], "-", [d for s in panel["series"]
                                   if (d := (s["data"] or {}).get(g))])
                 for g in groups]
    for i, (rc, rls, ds) in enumerate(rails):
        if not ds:
            continue
        # the rail carries activation too: mean a over the cycle sets its
        # weight, so a bar for a muscle that is barely driven stays hairline
        am = [np.nanmean(d["act"]) for d in ds if d.get("act") is not None]
        am = float(np.nanmean(am)) if am else np.nan
        # a NaN here used to become a NaN linewidth, and the whole rail
        # disappeared without a word -- that is how cateli's bar went missing
        am = float(np.clip(am, 0, 1)) if np.isfinite(am) else 1.0
        o = 0.035 * (i + 1)
        zs = [hill_value(d["l"], d["v"]) for d in ds]
        rail = dict(color=rc, lw=1.0 + 3.6 * am, ls=rls, zorder=8, alpha=0.95,
                    solid_capstyle="butt", dash_capstyle="butt")
        # l~ and v~ rails lie on the FLOOR along the edge each axis is drawn on
        ax.plot([VLIM[0] + o] * 2,
                [np.nanmin([np.nanmin(d["l"]) for d in ds]),
                 np.nanmax([np.nanmax(d["l"]) for d in ds])], [0, 0], **rail)
        ax.plot([np.nanmin([np.nanmin(d["v"]) for d in ds]),
                 np.nanmax([np.nanmax(d["v"]) for d in ds])],
                [LLIM[0] + o * 0.5] * 2, [0, 0], **rail)
        # the FORCE rail stands in the v~ = -1 wall -- the vertical/lateral
        # plane the z axis itself is drawn on. Stacking the muscles along l~
        # keeps every bar in that one plane; offsetting them along v~ instead
        # fanned them out in depth, which is what made them read as tilted.
        # a hair INSIDE the wall: exactly on v~ = -1 the bar z-fights with the
        # axis pane and disappears behind it
        ax.plot([VLIM[0] + 0.03] * 2, [LLIM[1] - 1.7 * o] * 2,
                [np.nanmin([np.nanmin(z) for z in zs]),
                 np.nanmax([np.nanmax(z) for z in zs])], **rail)

    ax.set_xlim(*VLIM); ax.set_ylim(*LLIM); ax.set_zlim(0.0, ZMAX)
    ax.set_xlabel("v~   <- shortening   lengthening ->", fontsize=8, labelpad=-1)
    ax.set_ylabel("l~  normalised fibre length", fontsize=8, labelpad=-1)
    ax.tick_params(labelsize=7, pad=0.5)
    ax.set_xticks([-1, -0.5, 0, 0.5, 1])
    ax.set_yticks([0.5, 0.8, 1.1, 1.4, 1.7])
    ax.set_zticks([0, 0.5, 1.0, 1.4])
    if first:
        ax.set_zlabel("force multiplier  f(l~, v~)", fontsize=8, labelpad=-4)
    else:
        ax.set_zticklabels([])          # a second zlabel lands in the neighbour
    for pane in (ax.xaxis, ax.yaxis, ax.zaxis):
        pane.pane.set_facecolor("white")
        pane.pane.set_edgecolor("0.85")
        pane._axinfo["grid"].update(color="0.90", linewidth=0.5)


KNOWN_COLUMNS = {
    "work_abs": "total muscle-tendon work per cycle, |positive| + |negative|",
    "peak": "peak force over peak isometric force",
    "peak_bw": "peak muscle-group force in bodyweights",
    "range:l": "min/max normalised fibre length over the cycle",
    "range:v": "min/max normalised fibre velocity over the cycle",
    "act_pk": "activation at the instant of peak force",
}


def _columns_note(columns, rank_by):
    """The one-line caption explaining the numbers table's columns."""
    txt = ";  ".join(f"{c['head']} = {KNOWN_COLUMNS.get(c['key'], c['head'])}"
                     for c in columns)
    hit = next((c for c in columns if c["key"] == rank_by), None)
    return txt + (f"    (rows ranked by {hit['head']})" if hit else "")


def _flag_note(flag_pct):
    """The caption line explaining the asterisks."""
    if not flag_pct:
        return ""
    return (f"* on a heading = the MODELS disagree by more than {flag_pct:g} % "
            f"of their mean;   # after a pair = SO and EMG disagree by more "
            f"than {flag_pct:g} % for that model"
            "   (peak-to-peak; a range column is compared on its width)")


ROW_LABEL_FS = 10        # the row caption under a badge


def _wrap_label(text, width=11):
    """Split a row caption on spaces so it fits the gutter beside the badge."""
    if not text:
        return []
    out, cur = [], ""
    for word in str(text).split():
        if cur and len(cur) + 1 + len(word) > width:
            out.append(cur); cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        out.append(cur)
    return out


def _as_image(x):
    """A path or an already-loaded array -> an array, or None."""
    if x is None:
        return None
    if isinstance(x, str):
        return plt.imread(x) if os.path.isfile(x) else None
    return np.asarray(x)



# per-row geometry, in inches
AXES_IN = 2.95      # the 3D axes itself
TITLE_IN = 58 / 72  # the panel title's pad, above the numbers block
FOOT_IN = 2.60      # legend + caption under the last row


def _table_gap(columns, n_chain, n_rows, panel_width, cap):
    """Inches to leave above a row of axes for its title and numbers table.

    A fixed gap was fine for one table shape and clipped the moment the table
    grew a row (six model x algorithm lines instead of five muscles). The same
    two formulas `_numbers_block` uses are run here, on an estimate of the axes
    width, so the layout reserves what the table will actually take.
    """
    ncha = 15 + sum(3 + max(len(c["head"]),
                            n_chain * c["cw"] + n_chain - 1 + 2)
                    for c in columns)
    fs = min(cap, 0.98 * (panel_width * 0.93 * 72) / (ncha * 0.602))
    return TITLE_IN + (n_rows + 2.5) * (fs + 1.8) / 72


def plot_fl_fv_surface(rows, groups, colors, out_path, title="",
                       footnote="", elev=26.0, azim=-122.0,
                       dpi=200, panel_width=4.9,
                       icon_for_panel=None, icon_h_in=0.62, header_icon=None,
                       task_icon_scale=1.5, annot_for_panel=None,
                       columns=DEFAULT_COLUMNS, rank_by=None,
                       color_by="group", flag_pct=10.0,
                       rows_are="group", style_by=None, legend_handles=None,
                       table_fontsize=8.0,
                       act_scale=True, save_pdf=False):
    """Draw a grid of 3D panels -- one ROW per algorithm, one COLUMN per task.

    rows            [dict(panels=[...], corner_icon=path|array)]. A bare list of
                    panels (no `panels` key) is taken as a single row, so the
                    one-row call still works unchanged.
    panels          [dict(title, series=[dict(name, ls, marker, data={group: trace})])]
    groups          ordered group names; colors {group: colour}
    title           figure heading, drawn top-left beside `header_icon` (or
                    centred if there is no icon); "" draws none
    header_icon     one pictogram (path or array) for the figure's top-left --
                    the muscle badge when a figure is one muscle group
    icon_for_panel  f(panel title) -> a pictogram path or array, above the TOP
                    row's panels only -- the columns are the same task throughout
    corner_icon     per row: the badge at the left of that row
    label           per row: the caption printed under that row's badge
    style_by        which dimension carries the STROKE; defaults to whichever
                    `color_by` does not use, but may be the same as `color_by`
    color_by        "group" -> colour is the muscle and stroke is the series;
                    "series" -> colour is the series (each needs a `color`) and
                    stroke is the muscle
    columns         [dict(key, head, fmt, cw)] for the numbers table
    rank_by         trace key to sort the numbers block by, largest first
    flag_pct        mark a cell `*` and bold it when the series disagree by
                    more than this % of their mean, `**` past 2.5x it; 0 off
    rows_are        "group" -> a table row is a muscle; "series" -> a table row
                    is a model, in its own colour (use with one muscle a figure)
    legend_handles  replace the auto identity block of the legend (use when one
                    series is a model x algorithm pair and the two read apart)
    act_scale       draw the activation key at the right of the panels
    """
    if rows and "panels" not in rows[0]:
        rows = [dict(panels=rows)]
    for r in rows:
        r["panels"] = [p for p in r["panels"]
                       if any(s.get("data") for s in p["series"])]
    rows = [r for r in rows if r["panels"]]
    if not rows:
        print("[skip] nothing to draw")
        return None

    nrow = len(rows)
    ncol = max(len(r["panels"]) for r in rows)
    head_im = _as_image(header_icon)
    task_h = icon_h_in * task_icon_scale if icon_for_panel else 0.0
    if annot_for_panel:
        # the callout blocks live in the same strip as the pictogram: measure
        # them, or the top ones run off the page and the bottom ones land on
        # the panel title
        ext = 0.0
        for p in rows[0]["panels"]:
            for an in annot_for_panel(p["title"]) or []:
                fs = an.get("fontsize", 6.5)
                ext = max(ext, abs(an["dy"]) + 0.10,
                          abs(an["dy"] - len(an["lines"]) * (fs + 1.6) / 72)
                          + 0.10)
        task_h = max(task_h, 2 * ext)
    head_h = max(1.15 * icon_h_in if head_im is not None else 0.0,
                 0.48 if title else icon_h_in * 0.4)
    n_chain = max(len(r["panels"][0]["series"]) for r in rows) \
        if rows_are == "series" else len(groups)
    n_tab = (max(len(r["panels"][0]["series"]) for r in rows)
             if rows_are == "series" else len(groups))
    gap_in = _table_gap(columns, n_chain, n_tab, panel_width, table_fontsize)
    fh = head_h + task_h + nrow * (AXES_IN + gap_in) + FOOT_IN
    grid = hill_surface()
    fig = plt.figure(figsize=(panel_width * ncol, fh))

    axs = [[] for _ in rows]
    for r, row in enumerate(rows):
        for c, p in enumerate(row["panels"]):
            ax = fig.add_subplot(nrow, ncol, r * ncol + c + 1, projection="3d")
            axs[r].append(ax)
            _panel(ax, grid, p, groups, colors, elev, azim, c == 0,
                   color_by=color_by, style_by=style_by)
            # the columns are the same task in every row: name them once
            ax.set_title(p["title"] if r == 0 else "", fontsize=11, pad=58)

    fw, _ = fig.get_size_inches()
    # the heading: badge hard against the top-left corner, name beside it
    x = 0.004
    if head_im is not None:
        h = icon_h_in
        w = h * (head_im.shape[1] / head_im.shape[0])
        a = fig.add_axes([x, 1 - (0.06 + h) / fh, w / fw, h / fh], zorder=6)
        a.imshow(head_im, interpolation="antialiased"); a.axis("off")
        x += w / fw + 0.005
    if title and head_im is not None:
        fig.text(x, 1 - (0.06 + icon_h_in / 2) / fh, title, fontsize=14,
                 ha="left", va="center")
    elif title:
        fig.suptitle(title, fontsize=13, y=1 - 0.22 / fh)

    series0 = rows[0]["panels"][0]["series"]
    if legend_handles is not None:
        key = list(legend_handles)
    elif color_by == "series":                 # colour = model, stroke = muscle
        key = [mlines.Line2D([], [], color=s.get("color", "0.3"), marker="o",
                             ls="none", ms=8, label=s["name"]) for s in series0]
        key += [mlines.Line2D([], [], color="0.3",
                              ls=GROUP_LS[i % len(GROUP_LS)],
                              marker=GROUP_MK[i % len(GROUP_MK)], lw=1.5, ms=7,
                              label=f"{g} (marker = peak force)")
                for i, g in enumerate(groups)]
    else:                                    # colour = muscle, stroke = model
        key = [mlines.Line2D([], [], color=colors[g], marker="o", ls="none",
                             ms=8, label=g) for g in groups]
        key += [mlines.Line2D([], [], color="0.3", ls=s.get("ls", "-"),
                              marker=s.get("marker", "o"), lw=1.5, ms=7,
                              label=f"{s['name']} (marker = peak force)")
                for s in series0]
    key += [mlines.Line2D([], [], color="0.3", lw=2.6,
                          label="axis rail = range covered over the cycle"),
            mlines.Line2D([], [], color="0.78", lw=ACT_LW[0] + 0.4,
                          label="thin + pale = low activation"),
            mlines.Line2D([], [], color="0.15", lw=ACT_LW[1],
                          label="thick + dark = high activation (a)"),
            mlines.Line2D([], [], color="#C0392B", ls="--", lw=1.3,
                          label="on-surface guide: isometric (v~ = 0)"),
            mlines.Line2D([], [], color="#2E5FA3", ls="--", lw=1.3,
                          label="on-surface guide: optimum length (l~ = 1)")]
    fig.legend(handles=key, loc="lower center", ncol=min(len(key), 5),
               frameon=False, fontsize=9, bbox_to_anchor=(0.5, 1.58 / fh))
    fig.text(0.5, 1.16 / fh,
             ((footnote + "\n") if footnote else "") +
             "surface height = Hill force multiplier at full activation\n"
             "(Thelen 2003 defaults -- the MODEL's capacity, not this subject's)\n"
             "each path is one muscle group over the whole cycle, averaged over "
             "the repetitions\npaths lie ON the sheet and are drawn over it, so "
             "a path beyond the crest still shows\n"
             f"{_columns_note(columns, rank_by)}"
             + (("\n" + _flag_note(flag_pct)) if flag_pct else ""),
             ha="center", va="top", fontsize=8.5, color="0.35", linespacing=1.4)

    # GAP_IN of title pad + numbers block sits above EVERY row, hence hspace.
    # The row badges need a gutter, or they land on the z-axis label.
    # Measure the badges AND their captions: a fixed gutter clipped the wide
    # ones onto the y-axis label. The caption wraps on spaces, so the gutter is
    # sized by the longest WORD, not the longest name.
    lab_lines = [_wrap_label(r.get("label")) for r in rows]
    bw = [icon_h_in * (im.shape[1] / im.shape[0])
          for im in (_as_image(r.get("corner_icon")) for r in rows)
          if im is not None]
    bw += [max(len(t) for t in ls) * ROW_LABEL_FS * 0.58 / 72
           for ls in lab_lines if ls]
    left = ((0.03 + max(bw) + 0.16) / fw) if bw else 0.015
    right = 1 - (0.95 if act_scale else 0.06) / fw
    fig.subplots_adjust(left=left, right=right, wspace=0.02,
                        bottom=FOOT_IN / fh, hspace=gap_in / AXES_IN,
                        top=1 - (head_h + task_h + gap_in) / fh)
    for r, row in enumerate(rows):       # after adjust: pitch needs the height
        for c, p in enumerate(row["panels"]):
            _numbers_block(axs[r][c], p, groups, colors, columns=columns,
                           rank_by=rank_by, color_by=color_by,
                           flag_pct=flag_pct, rows_are=rows_are,
                           fontsize=table_fontsize)

    for r, row in enumerate(rows):       # row badge + caption, left of the row
        im = _as_image(row.get("corner_icon"))
        lines = lab_lines[r]
        if im is None and not lines:
            continue
        b = axs[r][0].get_position()
        cy = 0.5 * (b.y0 + b.y1)
        cx = 0.03 / fw + 0.5 * (left - 0.03 / fw)      # centre of the gutter
        top = cy + (icon_h_in / fh) / 2
        if im is not None:
            w = icon_h_in * (im.shape[1] / im.shape[0])
            a = fig.add_axes([cx - (w / fw) / 2, cy - (icon_h_in / fh) / 2,
                              w / fw, icon_h_in / fh], zorder=6)
            a.imshow(im, interpolation="antialiased"); a.axis("off")
            top = cy - (icon_h_in / fh) / 2 - 0.02 / fh
        else:
            top = cy + len(lines) * (ROW_LABEL_FS + 2) / 2 / 72 / fh
        for k, t in enumerate(lines):    # the name, under its pictogram
            fig.text(cx, top - k * (ROW_LABEL_FS + 2) / 72 / fh, t,
                     fontsize=ROW_LABEL_FS, ha="center", va="top", zorder=6)

    if act_scale:                        # activation key, right of the panels
        b0, b1 = axs[-1][-1].get_position(), axs[0][-1].get_position()
        h = min(0.42 * (b1.y1 - b0.y0), 1.6 / fh)
        _activation_scale(fig, [right + 0.10 / fw,
                                0.5 * (b0.y0 + b1.y1) - h / 2, 0.13 / fw, h])

    if (icon_for_panel or annot_for_panel) and task_h:   # top strip per column
        for c, p in enumerate(rows[0]["panels"]):
            b = axs[0][c].get_position()
            cx, cy = 0.5 * (b.x0 + b.x1), 1 - (head_h + task_h / 2) / fh
            im = _as_image(icon_for_panel(p["title"])) if icon_for_panel else None
            if im is not None:
                w = task_h * (im.shape[1] / im.shape[0])
                a = fig.add_axes([cx - (w / fw) / 2, cy - (task_h / 2) / fh,
                                  w / fw, task_h / fh], zorder=6)
                a.imshow(im, interpolation="antialiased"); a.axis("off")
            for an in (annot_for_panel(p["title"]) if annot_for_panel else []):
                # one text artist per LINE: the lines are different colours
                # (one per model) and a single artist cannot hold two
                fs = an.get("fontsize", 6.5)
                for k, (t, col) in enumerate(an["lines"]):
                    fig.text(cx + an["dx"] / fw,
                             cy + (an["dy"] - k * (fs + 1.6) / 72) / fh, t,
                             color=col, fontsize=fs, ha=an.get("ha", "center"),
                             va=an.get("va", "top"), zorder=6,
                             family="DejaVu Sans Mono")

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    fig.savefig(out_path, dpi=dpi, facecolor="white")
    if save_pdf:
        fig.savefig(out_path[:-4] + ".pdf", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"-> {out_path}")
    return out_path
