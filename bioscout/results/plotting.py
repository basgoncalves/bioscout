"""Matplotlib for ResultSet.plot -- imported only when a plot is asked for."""
from __future__ import annotations

import fnmatch

from .scan import split
from .windows import ID_COLS


def _style(rs, by, key):
    """Colour/label from session.yaml when grouping by iteration."""
    if by != ["iteration"]:
        return {}, " / ".join(map(str, key if isinstance(key, tuple) else (key,)))
    it = key[0] if isinstance(key, tuple) else key
    cfg = next((i.iterations.get(it) for i in rs.infos if it in i.iterations), None) or {}
    st = {"color": cfg["color"]} if cfg.get("color") else {}
    return st, cfg.get("label") or it or "experimental"


class Plot:
    """What ``ResultSet.plot`` returns: the figure, without a second copy in Jupyter.

    plot() already displayed the figure; returning a bare Figure as the cell's
    last value would draw it again. This wrapper shows nothing as a value and
    forwards everything else to the figure (``p.savefig(...)``, ``p.axes``);
    ``p.fig`` is the matplotlib Figure (``display(p.fig)`` shows it again)."""

    def __init__(self, fig):
        self.fig = fig

    def __getattr__(self, name):
        return getattr(self.fig, name)

    def _repr_html_(self):
        return ""

    def __repr__(self):
        return f"<Plot '{self.fig._suptitle.get_text() if self.fig._suptitle else ''}', {len(self.fig.axes)} axes>"


def _channels(rs, var, limit=24):
    pats = split(var)
    chans = [c for c in rs.vars if not pats or any(fnmatch.fnmatchcase(c, p) for p in pats)]
    if len(chans) > limit:
        print(f"[results] {rs.variable}: {len(chans)} channels - plotting the first {limit} (pass var=...)")
        chans = chans[:limit]
    return chans


_STYLES = ("-", "--", ":", "-.")


def _draw(ax, rs, ch, by, mean, colour=None, prefix="", style_by_group=False):
    """One channel of one ResultSet on ``ax``: a line (mean +- SD on normalised
    data) per ``by`` group. ``colour`` fixes the colour (overlay of files), and
    then the groups differ by line style instead."""
    x = rs.x
    groups = list(rs.df.groupby(by, sort=False)) if by else [((), rs.df)]
    average = mean and x == "pct"
    for gi, (key, g) in enumerate(groups):
        st, lab = _style(rs, by, key)
        if colour is not None:
            st = {"color": colour}
        if style_by_group:
            st["ls"] = _STYLES[gi % len(_STYLES)]
        lab = f"{prefix}{lab}" if prefix else lab
        curves = [c.dropna(subset=[ch]) for _, c in g.groupby(ID_COLS, sort=False)]
        curves = [c for c in curves if len(c)]
        if not curves:
            continue
        if average and len(curves) > 1:
            cur = g.pivot_table(index=x, columns=ID_COLS, values=ch, sort=True)
            m, s = cur.mean(axis=1), cur.std(axis=1)
            line, = ax.plot(m.index, m.values, label=f"{lab} (mean ± SD, n={len(curves)})", **st)
            ax.fill_between(m.index, m - s, m + s, alpha=0.2, color=line.get_color())
        else:
            c0 = st.pop("color", None)
            for i, c in enumerate(curves):
                line, = ax.plot(c[x].to_numpy(), c[ch].to_numpy(), lw=1.2, color=c0,
                                label=f"{lab} (n={len(curves)})" if i == 0 else None, **st)
                c0 = line.get_color()


def _finish(fig, axes, xlabel, title, save):
    for ax in axes[-1]:
        if ax.get_visible():
            ax.set_xlabel(xlabel)
    fig.suptitle(title)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    if save:
        fig.savefig(save, dpi=150, bbox_inches="tight")
    _show(fig)
    return Plot(fig)


def _xlabel(rs):
    return "% " + rs.window if rs.x == "pct" else "time (s)"


def plot_resultset(rs, var=None, *, by="iteration", mean=True, ncols=3, title=None, save=None):
    import matplotlib.pyplot as plt

    chans = _channels(rs, var)
    if not chans:
        raise KeyError(f"{var!r} matches none of {rs.vars}")
    by = split(by) or []
    n = len(chans)
    nc = min(n, ncols)
    nr = -(-n // nc)
    fig, axes = plt.subplots(nr, nc, figsize=(4.2 * nc, 3.0 * nr), squeeze=False, sharex=True)
    for ax, ch in zip(axes.flat, chans):
        _draw(ax, rs, ch, by, mean)
        ax.set_title(ch, fontsize=10)
        ax.grid(alpha=0.3)
    for ax in list(axes.flat)[n:]:
        ax.set_visible(False)
    for ax in axes[:, 0]:
        ax.set_ylabel(rs.unit)
    axes.flat[0].legend(fontsize=8)
    return _finish(fig, axes, _xlabel(rs), title or rs.variable, save)


LAYOUTS = ("figures", "rows", "overlay", "stack")


def plot_resultsets(rss, var=None, *, layout="figures", by="iteration", mean=True,
                    ncols=3, title=None, save=None, **stack_kw):
    """Several result files (``session.results([...])``) in one go.

    layout  "figures"  one figure per file (each like ResultSet.plot)
            "rows"     one figure, a row per file, a column per channel
            "overlay"  one axes per channel, a colour per file; a second file
                       with another unit (N vs activation) gets its own y axis
            "stack"    one axes per file, its channels stacked (IAA contributions;
                       ``group``, ``top``, ``bw`` -- see plot_stack)
    """
    import matplotlib.pyplot as plt

    if layout not in LAYOUTS:
        raise ValueError(f"layout={layout!r}: use one of {LAYOUTS}")
    if layout == "stack":
        return plot_stack(rss, var, ncols=ncols, title=title, save=save, **stack_kw)
    items = list(rss.items())
    if layout == "figures":
        figs = [plot_resultset(rs, var, by=by, mean=mean, ncols=ncols, title=title,
                               save=(save.replace(".", f"_{v.replace('/', '_')}.", 1)
                                     if save and len(items) > 1 else save))
                for v, rs in items]
        return figs[0] if len(figs) == 1 else figs
    by = split(by) or []
    per = {v: _channels(rs, var) for v, rs in items}
    chans = list(dict.fromkeys(c for cs in per.values() for c in cs))   # union, file order
    if not chans:
        raise KeyError(f"{var!r} matches no channel in {list(rss)}")

    if layout == "rows":
        nr, nc = len(items), len(chans)
        fig, axes = plt.subplots(nr, nc, figsize=(3.6 * nc, 2.8 * nr), squeeze=False, sharex=True)
        for r, (v, rs) in enumerate(items):
            for c, ch in enumerate(chans):
                ax = axes[r, c]
                if ch in rs.vars:
                    _draw(ax, rs, ch, by, mean)
                else:
                    ax.text(0.5, 0.5, "no data", ha="center", va="center",
                            transform=ax.transAxes, color="0.5")
                if r == 0:
                    ax.set_title(ch, fontsize=10)
                ax.grid(alpha=0.3)
            axes[r, 0].set_ylabel(f"{v}\n[{rs.unit or '-'}]", fontsize=9)
        axes[0, 0].legend(fontsize=7)
        return _finish(fig, axes, _xlabel(items[0][1]), title or " | ".join(rss), save)

    # overlay
    n = len(chans)
    nc = min(n, ncols)
    nr = -(-n // nc)
    fig, axes = plt.subplots(nr, nc, figsize=(4.4 * nc, 3.0 * nr), squeeze=False, sharex=True)
    colours = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    units = list(dict.fromkeys(rs.unit or "-" for _, rs in items))
    for ax, ch in zip(axes.flat, chans):
        twin = None
        for i, (v, rs) in enumerate(items):
            if ch not in rs.vars:
                continue
            tgt = ax
            if (rs.unit or "-") != units[0]:
                twin = twin or ax.twinx()
                tgt = twin
                twin.set_ylabel(rs.unit or "-", color=colours[i % len(colours)], fontsize=8)
            _draw(tgt, rs, ch, by, mean, colour=colours[i % len(colours)],
                  prefix=f"{v}: ", style_by_group=True)
        ax.set_title(ch, fontsize=10)
        ax.grid(alpha=0.3)
    for ax in list(axes.flat)[n:]:
        ax.set_visible(False)
    for ax in axes[:, 0]:
        ax.set_ylabel(units[0])
    handles, labels = [], []
    for a in fig.axes:                                  # legend from the axes and twins
        h, l = a.get_legend_handles_labels()
        for hh, ll in zip(h, l):
            if ll not in labels:
                handles.append(hh); labels.append(ll)
    axes.flat[0].legend(handles, labels, fontsize=7)
    return _finish(fig, axes, _xlabel(items[0][1]), title or " + ".join(rss), save)


def _show(fig):
    """Show the figure once, whatever the backend. bioscout's own stages switch
    matplotlib to Agg to write their PNGs, after which a notebook stops showing
    new figures by itself; so in IPython the figure is displayed explicitly and
    then closed (closing stops the inline backend drawing it a second time).
    Outside IPython the figure is left open for plt.show()."""
    try:
        from IPython import get_ipython
        if get_ipython() is None:
            return
        from IPython.display import display
    except Exception:
        return
    import matplotlib.pyplot as plt
    display(fig)
    plt.close(fig)


# ------------------------------------------------------------------ stacked (IAA)
_NOT_STACKED = ("total", "measured")


def _stack_group(ch):
    """A channel -> its stack group: muscle group + side, gravity, velocity, reserves."""
    from bioscout.simulate.iaa_files import GROUPS
    if ch in ("gravity", "velocity"):
        return ch
    import re
    m = re.match(r"(.*)_([rl])$", ch)
    if not m or "reserve" in ch:
        return "Reserves/residuals"
    stem, sd = m.group(1), m.group(2).upper()
    for g, pre in GROUPS:
        if any(stem.startswith(p) for p in pre):
            return f"{g} {sd}"
    return f"Other muscles {sd}"


def _stack_frame(rs, var, group):
    """One curve (the mean when there are several on a normalised x) -> DataFrame
    x | contributors... | total | measured."""
    import pandas as pd
    df = rs.df
    keys = [c for c in ID_COLS if c in df and df[c].nunique() > 1]
    if keys and rs.x != "pct":
        first = df[keys].drop_duplicates().iloc[0]
        print(f"[results] {rs.variable}: {len(df[keys].drop_duplicates())} curves on a time axis - "
              f"stacking the first ({', '.join(f'{k}={first[k]}' for k in keys)}); "
              "use window='cycle' to stack their mean")
        df = df[(df[keys] == first).all(1)]
    num = [c for c in rs.vars]
    g = df.groupby(rs.x, sort=True)[num].mean()
    pats = split(var)
    chans = [c for c in num if c not in _NOT_STACKED
             and (not pats or any(fnmatch.fnmatchcase(c, p) for p in pats))]
    out = {}
    for c in chans:
        k = _stack_group(c) if group else c
        out[k] = out.get(k, 0) + g[c]
    out = pd.DataFrame(out, index=g.index)
    if "total" in g and not pats:
        out["total"] = g["total"]
    elif chans:
        out["total"] = g[chans].sum(1)
    if "measured" in g:
        out["measured"] = g["measured"]
    return out


def _stack_grid(panels, *, ncols=3, top=8, title=None, save=None, row_labels=None):
    """panels: [dict(title, frame (x index; contributors, total, measured), k, unit, xlabel) | None]."""
    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    from bioscout.simulate import iaa_files as _iaf

    allc = []
    for p in panels:
        if p is not None:
            allc += [c for c in p["frame"].columns if c not in allc and c not in _NOT_STACKED]
    _iaf._colour_groups(allc)
    n = len(panels); nc = min(n, ncols); nr = -(-n // nc)
    fig, axes = plt.subplots(nr, nc, figsize=(4.8 * nc, 3.2 * nr), squeeze=False, sharex=True)
    shown, xl = [], "time (s)"
    for ax, p in zip(axes.flat, panels):
        if p is None:
            ax.text(0.5, 0.5, "not available", ha="center", va="center", transform=ax.transAxes, color="0.5")
            ax.set_xticks([]); ax.set_yticks([])
            continue
        d = p["frame"].reset_index()
        d = d.rename(columns={d.columns[0]: "time"})
        if "measured" not in d:
            d["measured"] = np.nan
        if "total" not in d:
            d["total"] = d[[c for c in d.columns if c not in ("time", "measured")]].sum(1)
        for c in _iaf._stack_one(ax, d, p.get("k", 1.0), top):
            if c not in shown:
                shown.append(c)
        ax.set_title(p["title"], fontsize=10); ax.set_ylabel(p["unit"]); ax.grid(alpha=0.3)
        xl = p.get("xlabel", xl)
    for ax in list(axes.flat)[n:]:
        ax.set_visible(False)
    if row_labels:
        for r, lab in enumerate(row_labels[:nr]):
            axes[r, 0].annotate(lab, xy=(0, 0.5), xycoords="axes fraction", xytext=(-62, 0),
                                textcoords="offset points", rotation=90, ha="center", va="center",
                                fontsize=11, fontweight="bold")
    h = [Patch(color="0.75" if c == "others" else _iaf._COLORS.get(c, "C0"), label=c) for c in shown]
    h += [Line2D([], [], color="k", lw=1.6, label="total"), Line2D([], [], color="k", ls="--", label="measured")]
    nleg = -(-len(h) // 6)
    fig.legend(handles=h, loc="lower center", ncol=min(6, len(h)), fontsize=8, frameon=False)
    for ax in axes[-1]:
        if ax.get_visible():
            ax.set_xlabel(xl)
    fig.suptitle(title or "Contributions, stacked")
    fig.tight_layout(rect=(0.03 if row_labels else 0, 0.035 * nleg + 0.02, 1, 0.97))
    if save:
        fig.savefig(save, dpi=150, bbox_inches="tight")
    _show(fig)
    return Plot(fig)


def plot_stack(rss, var=None, *, group=True, top=8, ncols=3, title=None, save=None, bw=None):
    """Stacked contributions, one axes per result file (an IAA target: a coordinate,
    center_of_mass_X/Y/Z, grf_<foot>_X/Y/Z). Positive parts stack above zero, negative
    below; black = their sum, dashed = measured.

    var    channels to stack (glob; muscles, 'gravity', ...); default all
    group  True: sum muscles into groups per side (+ gravity, velocity, reserves)
    top    the largest ``top`` contributors per axes; the rest is one grey 'others'
    bw     body weight (N): GRF axes in BW
    """
    from bioscout.simulate import iaa_files as _iaf
    panels = []
    for v, rs in rss.items():
        tg = v.split("/", 1)[-1]
        k, unit = _iaf._unit(tg)
        if bw and tg.startswith("grf_"):
            k, unit = 1.0 / bw, "BW"
        panels.append(dict(title=tg, frame=_stack_frame(rs, var, group), k=k, unit=unit, xlabel=_xlabel(rs)))
    return _stack_grid(panels, ncols=ncols, top=top, title=title or "Induced accelerations: contributions, stacked",
                       save=save)
