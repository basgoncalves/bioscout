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

    The inline backend already draws every figure made in a cell; returning a
    bare Figure as the cell's last value drew it twice. This wrapper shows
    nothing as a value and forwards everything else to the figure
    (``p.savefig(...)``, ``p.axes``); ``p.fig`` is the matplotlib Figure."""

    def __init__(self, fig):
        self.fig = fig

    def __getattr__(self, name):
        return getattr(self.fig, name)

    def _repr_html_(self):
        return ""

    def __repr__(self):
        return f"<Plot '{self.fig._suptitle.get_text() if self.fig._suptitle else ''}', {len(self.fig.axes)} axes>"


def plot_resultset(rs, var=None, *, by="iteration", mean=True, ncols=3, title=None, save=None):
    import matplotlib.pyplot as plt

    pats = split(var)
    chans = [c for c in rs.vars if not pats or any(fnmatch.fnmatchcase(c, p) for p in pats)]
    if not chans:
        raise KeyError(f"{var!r} matches none of {rs.vars}")
    if len(chans) > 24:
        print(f"[results] {len(chans)} channels - plotting the first 24 (pass var=...)")
        chans = chans[:24]
    by = split(by) or []
    n = len(chans)
    nc = min(n, ncols)
    nr = -(-n // nc)
    fig, axes = plt.subplots(nr, nc, figsize=(4.2 * nc, 3.0 * nr), squeeze=False, sharex=True)
    x = rs.x
    groups = list(rs.df.groupby(by, sort=False)) if by else [((), rs.df)]
    # averaging needs a shared x: only on time-normalised data ('pct').
    # Raw time (window='trial') -> every curve on its own time axis.
    average = mean and x == "pct"
    for ax, ch in zip(axes.flat, chans):
        for key, g in groups:
            st, lab = _style(rs, by, key)
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
                colour = st.get("color")
                for i, c in enumerate(curves):
                    line, = ax.plot(c[x].to_numpy(), c[ch].to_numpy(), lw=1.2, color=colour,
                                    label=f"{lab} (n={len(curves)})" if i == 0 else None)
                    colour = line.get_color()
        ax.set_title(ch, fontsize=10)
        ax.grid(alpha=0.3)
    for ax in list(axes.flat)[n:]:
        ax.set_visible(False)
    for ax in axes[-1]:
        ax.set_xlabel("% " + rs.window if x == "pct" else "time (s)")
    for ax in axes[:, 0]:
        ax.set_ylabel(rs.unit)
    axes.flat[0].legend(fontsize=8)
    fig.suptitle(title or rs.variable)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    if save:
        fig.savefig(save, dpi=150, bbox_inches="tight")
    return Plot(fig)
