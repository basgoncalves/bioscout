"""bioscout.plot.compare — one comparison figure, any two things.

The figure this generalises has been rebuilt three times in three projects, and
each time the only thing that really changed was WHAT the two columns were:

    Powerlifting   columns = generic models,   rows = algorithm
    FAIS (subject) columns = task,             rows = pre- / post-fatigue
    FAIS (group)   columns = pre- / post-,     rows = task

So the columns and the rows are arguments, not code::

    import bioscout as bs

    (bs.plot.compare("results/master_results.csv")
        .where(Variable="muscle_work_total", Algo="SO")
        .compare("Condition", order=["pre-fatigue", "post-fatigue"])
        .facet("Task")
        .top(8)
        .title("total muscle work ranks")
        .save("results/group/work_ranks.png"))

Swap ``.compare("Condition")`` for ``.compare("Task")`` and the same table
answers "which muscles change between TASKS" instead. Swap it for
``.compare("Algo")`` and it answers "does the algorithm reorder the leg".
Nothing about the figure is specific to fatigue, to tasks, or to muscle work —
it ranks whatever is in the ``Channel`` column by whatever is in ``Value``.

TWO RENDERERS ON ONE SELECTION
    ``.ranks()``   ranked horizontal bars, colour anchored on the first column
    ``.curves()``  mean ± SD waveforms, one line per compared level

    Both read the same tidy table and the same ``.where/.compare/.facet``
    selection, which is the point: the pipeline from data to figure is written
    once.

READING A RANK FIGURE
    Bar colour is the item's rank in the FIRST compared column, carried into
    every column to its right. The left panel is therefore always a clean
    dark-to-pale ramp by construction, and ANY colour disorder further right is
    a re-ranking — no tracing of lines required. ▲/▼ after a label gives the
    places gained or lost, and ``style="connector"`` draws the arrows from
    Collings et al. (2025) instead (see ``bioscout.utils.collings`` for the
    fixed published layout).

    With ``normalise="reference"`` (the default) every panel in a row is scaled
    to the leader of the first column, so a panel that shrinks did less work
    and a bar may legitimately pass 100 %. ``normalise="panel"`` scales each
    panel to its own leader: that is a pure ranking with the magnitudes thrown
    away, which is sometimes what you want and is never what you want by
    accident.
"""
from __future__ import annotations

import os

from . import config as _config
from . import tidy as _tidy


# ------------------------------------------------------------ small helpers
def _ramp(n, cfg):
    """Dark-to-pale ladder of length ``n``, rank 1 darkest."""
    import matplotlib
    import numpy as np
    try:
        m = matplotlib.colormaps[cfg.cmap]
    except (AttributeError, KeyError):          # matplotlib < 3.5
        import matplotlib.cm as cm
        m = cm.get_cmap(cfg.cmap)
    a, b = cfg.cmap_range
    return [m(x) for x in np.linspace(a, b, max(int(n), 1))]


def _text_colour(rgba):
    """Black or white label, by luminance — a fixed colour is unreadable at one
    end of the ramp or the other."""
    r, g, b = rgba[0], rgba[1], rgba[2]
    return "white" if (0.299 * r + 0.587 * g + 0.114 * b) < 0.55 else "#111111"


def _connector_colours():
    """The blue/red/grey arrow palette, from ``collings`` when it imports (it
    pulls in ``bioscout.utils``, which wants scipy) and inline when it does
    not — the figure must still draw in a bare environment."""
    try:
        from ..utils import collings as C
        return C.UP_COLOUR, C.DOWN_COLOUR, C.SAME_COLOUR
    except Exception:                                          # noqa: BLE001
        return "#2166ac", "#b2182b", "0.65"


def _icon_axes(fig, gs_cell, path, cfg, label=None):
    """The row's pictogram, with its name under it. The name is kept even when
    the icon is missing — a row nobody can identify is worse than a plain one."""
    import matplotlib.pyplot as plt
    has = bool(path) and os.path.isfile(str(path))
    if not has and not label:
        return None
    ax = fig.add_subplot(gs_cell)
    if has:
        ax.imshow(plt.imread(str(path)), interpolation="antialiased")
    ax.axis("off")
    if label:
        ax.text(0.5, -0.04 if has else 0.5, str(label), transform=ax.transAxes,
                ha="center", va="top" if has else "center",
                fontsize=cfg.fs_tick, color="0.25")
    return ax


def _resolve_icon(icons, value):
    if icons is None:
        return None
    if callable(icons):
        return icons(value)
    return icons.get(value)


# ------------------------------------------------------------- the builder
class Compare:
    """A comparison figure, built up a clause at a time.

    Every method returns a NEW ``Compare`` — chains are safe to branch::

        base = bs.plot.compare(df).facet("Task").top(8)
        base.compare("Condition").save("by_fatigue.png")
        base.compare("Algo").save("by_algorithm.png")
    """

    def __init__(self, data=None, **filters):
        self._data = _tidy.read(data, **filters) if data is not None else None
        self._item = "Channel"
        self._value = _tidy.VALUE
        self._compare = None
        self._compare_order = None
        self._compare_labels = None
        self._facet = None
        self._facet_order = None
        self._facet_labels = None
        self._icons = None
        self._groups = None
        self._keep_unmapped = False
        self._agg = "mean"
        self._panels = None            # curves only; defaults to ``item``
        self._title = ""
        self._note = None
        self._xlabel = None
        self._ylabel = None
        self._count_over = None
        self._kind = "ranks"
        self._x = "Percent"            # curves only
        self._overrides = {}
        self._fig = None

    # -- plumbing ----------------------------------------------------------
    def _with(self, **kw):
        import copy
        new = copy.copy(self)
        new._fig = None
        for k, v in kw.items():
            setattr(new, "_" + k, v)
        return new

    def __repr__(self):
        n = 0 if self._data is None else len(self._data)
        return ("<bioscout.plot.Compare %s rows | compare=%r facet=%r item=%r "
                "top=%d style=%r>"
                % (n, self._compare, self._facet, self._item,
                   self._cfg().top, self._cfg().style))

    def _cfg(self):
        return _config.resolve(**self._overrides)

    # -- data --------------------------------------------------------------
    def data(self, source, **filters):
        """Replace the table."""
        return self._with(data=_tidy.read(source, **filters))

    def where(self, **filters):
        """Keep only matching rows. Scalars, lists and callables all work::

            .where(Variable="muscle_work_total", Algo="SO",
                   Side=lambda s: s == "_r")
        """
        if self._data is None:
            raise ValueError("no data — call bs.plot.compare(table) first")
        return self._with(data=_tidy.select(self._data, **filters))

    def item(self, col):
        """Which column names the things being ranked/drawn (default
        ``Channel``)."""
        return self._with(item=col)

    def value(self, col):
        """Which column holds the number (default ``Value``)."""
        return self._with(value=col)

    def group(self, mapping, keep_unmapped=False):
        """Collapse the item column into functional groups before ranking.
        ``mapping`` is ``{group: (member, ...)}`` — see
        :data:`bioscout.plot.MUSCLE_GROUPS`."""
        return self._with(groups=mapping, keep_unmapped=keep_unmapped)

    def agg(self, how):
        """How to collapse everything the figure is not splitting on —
        ``"mean"`` (default), ``"sum"``, ``"median"``, ``"max"``…"""
        return self._with(agg=how)

    # -- layout ------------------------------------------------------------
    def compare(self, col, order=None, labels=None):
        """The column that becomes the panels side by side. ``order`` fixes
        their left-to-right order (and therefore which one anchors the colour);
        ``labels`` is an optional ``{value: heading}`` rename."""
        return self._with(compare=col, compare_order=order,
                          compare_labels=labels)

    def facet(self, col, order=None, labels=None, icons=None):
        """The column that becomes the stacked rows. ``icons`` may be a
        ``{value: image path}`` map or a callable, drawn in a strip on the
        left."""
        return self._with(facet=col, facet_order=order, facet_labels=labels,
                          icons=icons if icons is not None else self._icons)

    def icons(self, mapping):
        """Row icons: ``{facet value: image path}`` or a callable."""
        return self._with(icons=mapping)

    def panels(self, col):
        """Curves only — the column that becomes the columns of panels
        (defaults to the item column, i.e. one panel per channel)."""
        return self._with(panels=col)

    # -- style -------------------------------------------------------------
    def top(self, n):
        return self.set(top=int(n))

    def style(self, name):
        """``"delta"`` (▲/▼ markers), ``"connector"`` (arrows), ``"both"``."""
        return self.set(style=name)

    def normalise(self, how):
        """``"reference"`` or ``"panel"`` — see the module docstring."""
        return self.set(normalise=how)

    def set(self, **kw):
        """Any :class:`bioscout.plot.PlotConfig` field, for this figure only::

            .set(dpi=600, cmap="viridis", panel_w_in=4.2)
        """
        _config.settings().merged(**kw)          # validate now, not at draw
        return self._with(overrides={**self._overrides, **kw})

    def title(self, text):
        return self._with(title=text)

    def note(self, text):
        """A footnote under the figure. ``None`` restores the default legend
        text, ``""`` removes it."""
        return self._with(note=text)

    def labels(self, x=None, y=None):
        return self._with(xlabel=x if x is not None else self._xlabel,
                          ylabel=y if y is not None else self._ylabel)

    def count_over(self, col="Trial"):
        """Print ``n=…`` on each panel, counting distinct values of ``col``.
        Off by default — but a panel drawn from one trial and a panel drawn
        from twelve should not look identical, so turn it on for anything
        anyone else will read."""
        return self._with(count_over=col)

    # -- renderers ---------------------------------------------------------
    def ranks(self, **kw):
        """Choose the ranked-bar renderer (and optionally set style keys)."""
        return self._with(kind="ranks").set(**kw) if kw \
            else self._with(kind="ranks")

    def curves(self, x=None, **kw):
        """Choose the mean ± SD waveform renderer. ``x`` names the column that
        holds the cycle axis (default ``Percent``); the data is expected to be
        time-normalised already — this draws what it is given."""
        c = self._with(kind="curves", x=x or self._x)
        return c.set(**kw) if kw else c

    # backwards-friendly aliases for the two things people say out loud
    add_force_curves = curves
    add_ranks = ranks

    # -- output ------------------------------------------------------------
    def draw(self, force=False):
        """Build the matplotlib Figure (cached; ``force=True`` redraws)."""
        if self._fig is not None and not force:
            return self._fig
        if self._data is None or not len(self._data):
            raise ValueError("nothing to draw — the table is empty")
        if not self._compare:
            raise ValueError("nothing to compare — call .compare('<column>')")
        df = self._data
        if self._groups:
            df = _tidy.group_channels(df, self._groups, item=self._item,
                                      value=self._value,
                                      keep_unmapped=self._keep_unmapped)
        self._fig = (_draw_ranks if self._kind == "ranks" else _draw_curves)(
            self, df)
        return self._fig

    def save(self, path, **kw):
        """Draw if needed and write the file. Makes parent folders, honours
        ``save_pdf``, returns the path written."""
        cfg = self._cfg()
        fig = self.draw()
        path = os.fspath(path)
        d = os.path.dirname(os.path.abspath(path))
        if d:
            os.makedirs(d, exist_ok=True)
        fig.savefig(path, dpi=cfg.dpi, bbox_inches="tight",
                    facecolor="none" if cfg.transparent else cfg.facecolor,
                    transparent=cfg.transparent)
        if cfg.save_pdf and not path.lower().endswith(".pdf"):
            fig.savefig(os.path.splitext(path)[0] + ".pdf", bbox_inches="tight",
                        facecolor=cfg.facecolor)
        print("-> %s" % path)
        return path

    def show(self):
        import matplotlib.pyplot as plt
        self.draw()
        plt.show()
        return self

    def close(self):
        import matplotlib.pyplot as plt
        if self._fig is not None:
            plt.close(self._fig)
            self._fig = None
        return self

    def table(self):
        """The reduced numbers the figure will draw —
        ``{row: [(column, {item: value}), ...]}``. Print this when a panel
        looks wrong; it is much faster than reading the picture."""
        df = self._data
        if self._groups:
            df = _tidy.group_channels(df, self._groups, item=self._item,
                                      value=self._value,
                                      keep_unmapped=self._keep_unmapped)
        return _tidy.cells(df, self._compare, self._item, self._value,
                           self._facet, self._agg, self._compare_order,
                           self._facet_order)

    def _repr_png_(self):
        """So the last line of a notebook cell renders the figure."""
        import io
        try:
            fig = self.draw()
        except ValueError:
            return None
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=self._cfg().dpi,
                    bbox_inches="tight", facecolor=self._cfg().facecolor)
        return buf.getvalue()


# --------------------------------------------------------------- rendering
def _grid(n_rows, n_cols, cfg, icons):
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec
    icon_w = cfg.icon_w_in if icons else 0.0
    row_h = cfg.row_pad_in + cfg.row_per_item_in * cfg.top
    w = icon_w + cfg.panel_w_in * n_cols
    h = row_h * n_rows + 1.0
    fig = plt.figure(figsize=(w, h))
    ratios = ([icon_w / cfg.panel_w_in] if icons else []) + [1.0] * n_cols
    gs = GridSpec(n_rows, n_cols + (1 if icons else 0), figure=fig,
                  width_ratios=ratios)
    return fig, gs, (1 if icons else 0)


def _draw_ranks(spec, df):
    import numpy as np
    from matplotlib.patches import ConnectionPatch

    cfg = spec._cfg()
    cells = _tidy.cells(df, spec._compare, spec._item, spec._value,
                        spec._facet, spec._agg, spec._compare_order,
                        spec._facet_order)
    if not cells:
        raise ValueError("no rows survived the selection")
    counts = (_tidy.counts(df, spec._compare, spec._facet, spec._count_over)
              if spec._count_over else {})
    rows = list(cells)
    n_cols = max(len(v) for v in cells.values())
    fig, gs, off = _grid(len(rows), n_cols, cfg, spec._icons)
    up, down, same = _connector_colours()

    for r, fv in enumerate(rows):
        columns = cells[fv]
        if spec._icons is not None:
            _icon_axes(fig, gs[r, 0], _resolve_icon(spec._icons, fv), cfg,
                       str((spec._facet_labels or {}).get(fv, fv)))
        ref = columns[0][1]
        order_ref = sorted(ref, key=ref.get, reverse=True)[:cfg.top]
        ramp = _ramp(max(len(order_ref), cfg.top), cfg)
        colour = {g: ramp[i] for i, g in enumerate(order_ref)}
        lead = ref[order_ref[0]] if order_ref else 1.0

        # One x limit for the whole row: panels drawn to different scales are
        # not a comparison, they are two figures side by side.
        xmax = 100.0
        if cfg.normalise == "reference" and lead:
            for _, vals in columns:
                xmax = max(xmax, 100.0 * max(vals.values()) / lead)

        # The x limit is decided BEFORE any bar is drawn, because whether a
        # label fits inside its bar depends on the bar's share of the AXIS, not
        # on its percentage. Deciding from the percentage puts a 70 %% label
        # inside a bar that is a third of a 0-230 axis, and it runs off the
        # left edge — which is what the first version of this did.
        xhi = max(118.0, 1.18 * xmax)
        axes, orders = [], []
        for c, (label, vals) in enumerate(columns):
            ax = fig.add_subplot(gs[r, c + off])
            axes.append(ax)
            order = sorted(vals, key=vals.get, reverse=True)[:cfg.top]
            orders.append(order)
            denom = (lead if cfg.normalise == "reference"
                     else (vals[order[0]] if order else 1.0)) or 1.0
            y = np.arange(len(order))[::-1]
            for yi, g in zip(y, order):
                pct = 100.0 * vals[g] / denom
                col = colour.get(g, cfg.missing_colour)
                ax.barh(yi, pct, color=col, height=cfg.bar_height, zorder=2)
                tag = ""
                if c and g in order_ref and cfg.style in ("delta", "both"):
                    d = order_ref.index(g) - order.index(g)
                    tag = "  %s%d" % ("▲" if d > 0 else "▼", abs(d)) if d else ""
                inside = (100.0 * pct / xhi) > cfg.label_inside_pct
                pad = 0.02 * xhi
                ax.text(pct - pad if inside else pct + pad, yi, str(g) + tag,
                        va="center", ha="right" if inside else "left",
                        fontsize=cfg.fs_label, zorder=3,
                        color=_text_colour(col) if inside else "0.15")
            ax.set_xlim(0, xhi)
            ax.set_ylim(-0.7, max(len(order), 1) - 0.3)
            ax.set_yticks([])
            ax.tick_params(labelsize=cfg.fs_tick)
            for s in ("top", "right", "left"):
                ax.spines[s].set_visible(False)
            head = (spec._compare_labels or {}).get(label, label)
            n = counts.get((fv, label))
            if r == 0:
                ax.set_title("%s%s" % (head, "" if n is None else "\n(n=%d)" % n),
                             fontsize=cfg.fs_title)
            elif n is not None:
                ax.set_title("n=%d" % n, fontsize=cfg.fs_tick, color="0.45")
            if r == len(rows) - 1:
                ax.set_xlabel(spec._xlabel or _default_xlabel(spec, cfg),
                              fontsize=cfg.fs_label)
            if c == 0 and spec._facet is not None and spec._icons is None:
                ax.set_ylabel(str((spec._facet_labels or {}).get(fv, fv)),
                              fontsize=cfg.fs_title)

        if cfg.style in ("connector", "both"):
            for c in range(len(axes) - 1):
                oA, oB = orders[c], orders[c + 1]
                x_right = axes[c].get_xlim()[1]
                for k, g in enumerate(oA):
                    kA = len(oA) - 1 - k
                    if g in oB:
                        kB = len(oB) - 1 - oB.index(g)
                        col = same if oB.index(g) == k else (
                            up if oB.index(g) < k else down)
                        ls = "-"
                    else:
                        kB, col, ls = -0.6, down, ":"
                    fig.add_artist(ConnectionPatch(
                        (x_right, kA), (0, kB), "data", "data",
                        axesA=axes[c], axesB=axes[c + 1], lw=0.9, color=col,
                        linestyle=ls, alpha=0.85, zorder=1,
                        arrowstyle="-|>", mutation_scale=8))

    _finish(fig, spec, cfg, default_note=_default_note(cfg),
            w_pad=3.0 if cfg.style in ("connector", "both") else None)
    return fig


def _default_xlabel(spec, cfg):
    if cfg.normalise == "reference":
        first = None
        try:
            first = list(spec.table().values())[0][0][0]
        except Exception:                                      # noqa: BLE001
            pass
        return "%% of the %s leader" % (first or "reference")
    return "% of the top item in this panel"


def _default_note(cfg):
    bits = ["bar colour = rank in the first column, carried right"]
    if cfg.style in ("delta", "both"):
        bits.append("▲/▼ = places gained/lost")
    if cfg.style in ("connector", "both"):
        bits.append("blue = ranked higher on the right, red = lower, "
                    "dotted = leaves the top %d" % cfg.top)
    if cfg.normalise == "reference":
        bits.append("all panels scaled to the first column's leader")
    return "      |      ".join(bits)


def _draw_curves(spec, df):
    import numpy as np

    cfg = spec._cfg()
    panel_col = spec._panels or spec._item
    x = spec._x
    for c in (x, panel_col, spec._compare):
        if c not in df.columns:
            raise KeyError("no column %r in the table; have: %s"
                           % (c, ", ".join(map(str, df.columns))))
    rows = _tidy.levels(df, spec._facet, spec._facet_order) if spec._facet \
        else [None]
    panels = _tidy.levels(df, panel_col)
    lines = _tidy.levels(df, spec._compare, spec._compare_order)

    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec
    icon_w = cfg.icon_w_in if spec._icons else 0.0
    fig = plt.figure(figsize=(icon_w + 2.4 * len(panels),
                              1.9 * len(rows) + 1.1))
    ratios = ([icon_w / 2.4] if spec._icons else []) + [1.0] * len(panels)
    gs = GridSpec(len(rows), len(panels) + (1 if spec._icons else 0),
                  figure=fig, width_ratios=ratios)
    off = 1 if spec._icons else 0
    palette = plt.rcParams["axes.prop_cycle"].by_key().get(
        "color", ["#2166ac", "#b2182b", "#1b7837", "#762a83"])
    colour = {lv: palette[i % len(palette)] for i, lv in enumerate(lines)}

    for r, fv in enumerate(rows):
        d = df[df[spec._facet] == fv] if spec._facet else df
        if spec._icons is not None:
            _icon_axes(fig, gs[r, 0], _resolve_icon(spec._icons, fv), cfg,
                       str((spec._facet_labels or {}).get(fv, fv)))
        for p, pv in enumerate(panels):
            ax = fig.add_subplot(gs[r, p + off])
            dp = d[d[panel_col] == pv]
            for lv in lines:
                dl = dp[dp[spec._compare] == lv]
                if dl.empty:
                    continue
                g = dl.groupby(x)[spec._value]
                m, s = g.mean(), g.std().fillna(0.0)
                xs = np.asarray(m.index, dtype=float)
                ax.fill_between(xs, m - s, m + s, color=colour[lv], alpha=0.18,
                                lw=0)
                ax.plot(xs, m, color=colour[lv], lw=1.6,
                        label=str((spec._compare_labels or {}).get(lv, lv)))
            ax.tick_params(labelsize=cfg.fs_tick)
            for sp in ("top", "right"):
                ax.spines[sp].set_visible(False)
            if r == 0:
                ax.set_title(str(pv), fontsize=cfg.fs_title)
            if r == len(rows) - 1:
                ax.set_xlabel(spec._xlabel or x, fontsize=cfg.fs_label)
            else:
                ax.tick_params(labelbottom=False)
            if p == 0:
                lab = spec._ylabel or ""
                if spec._facet is not None and spec._icons is None:
                    lab = "%s\n%s" % ((spec._facet_labels or {}).get(fv, fv),
                                      lab) if lab else str(fv)
                ax.set_ylabel(lab, fontsize=cfg.fs_label)

    handles, labels = [], []
    for ax in fig.axes:
        h, l = ax.get_legend_handles_labels()
        for hh, ll in zip(h, l):
            if ll not in labels:
                handles.append(hh); labels.append(ll)
    if handles:
        fig.legend(handles, labels, loc="lower center", ncol=len(labels),
                   frameon=False, fontsize=cfg.fs_legend,
                   bbox_to_anchor=(0.5, 0.022))
    # The legend and the footnote both live at the bottom, so the axes have to
    # give up enough room for BOTH or they overlap.
    _finish(fig, spec, cfg, default_note="shaded band = ±1 SD",
            bottom=0.10 if handles else None)
    return fig


def _finish(fig, spec, cfg, default_note="", w_pad=None, bottom=None):
    note = default_note if spec._note is None else spec._note
    if spec._title:
        fig.suptitle(spec._title, fontsize=cfg.fs_suptitle)
    if note:
        fig.text(0.5, 0.006, note, ha="center", va="bottom",
                 fontsize=cfg.fs_legend, color="0.38")
    top = 0.94 if spec._title else 0.985
    bottom = bottom if bottom is not None else (0.055 if note else 0.03)
    try:
        # A wider gutter when the connectors are on: they run BETWEEN the
        # panels, and a gutter tight enough to be pretty makes them unreadable.
        fig.tight_layout(rect=(0.0, bottom, 1.0, top),
                         **({"w_pad": w_pad} if w_pad else {}))
    except Exception:                                          # noqa: BLE001
        fig.subplots_adjust(top=top, bottom=bottom)


__all__ = ["Compare"]
