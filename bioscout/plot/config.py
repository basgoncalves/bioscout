"""bioscout.plot.config — figure settings that live IN bioscout, not in a project.

The rule this module exists to enforce: **a project should not need its own
copy of anything to draw a figure.** Every knob has a defensible default here,
and a notebook overrides the ones it cares about at run time::

    import bioscout as bs
    bs.plot.configure(dpi=300, top=8, style="delta")

    with bs.plot.using(dpi=600, save_pdf=True):     # temporary, for one export
        fig.save("results/figure_3.png")

Nothing reads a project ``settings.py``. If a project *wants* to pin its own
look it does so by calling ``configure()`` once at the top of its script or
notebook — which is the same mechanism, written down in the project rather than
copied into it.

Precedence, lowest to highest:

1. the defaults in :class:`PlotConfig` below
2. whatever ``configure()`` has been given in this process
3. keyword arguments passed to the individual plotting call

so any single figure can always break the house style without changing it.
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass, fields, replace


@dataclass
class PlotConfig:
    """Every knob the plotting layer has. All optional, all overridable."""

    # --- what gets drawn ---------------------------------------------------
    top: int = 8
    """How many items (muscle groups, channels…) a ranked panel shows."""

    style: str = "delta"
    """``"delta"``    — ▲/▼ places gained/lost written after each bar label.
       ``"connector"`` — Collings-style arrows joining the columns
                        (``bioscout.utils.collings.rank_shift_axes``).
       ``"both"``     — arrows and markers."""

    normalise: str = "reference"
    """``"reference"`` — every panel in a row is scaled to the leader of the
                        FIRST column, so a shrinking panel reads as "did less
                        work" and a bar may legitimately pass 100 %.
       ``"panel"``     — each panel scaled to its own leader: pure ranking, the
                        magnitudes are discarded (this is Collings' original)."""

    cmap: str = "YlGnBu"
    cmap_range: tuple = (0.85, 0.25)
    """Dark-to-pale ramp ends. Rank 1 takes ``cmap_range[0]``."""

    missing_colour: str = "0.78"
    """An item absent from the reference column has no rank to inherit, so it
    is drawn neutral rather than being given a colour it never earned."""

    # --- geometry ----------------------------------------------------------
    panel_w_in: float = 3.4
    """Width of ONE comparison panel, in inches. Figure width scales with the
    number of columns."""

    row_pad_in: float = 0.9
    row_per_item_in: float = 0.36
    """Row height = ``row_pad_in + row_per_item_in * top``. Fixed inches, not a
    fraction: a fraction tuned at top=12 leaves half the canvas empty at top=5."""

    bar_height: float = 0.72
    icon_w_in: float = 0.85
    """Width of the per-row facet icon strip. 0 turns icons off entirely."""

    # --- text --------------------------------------------------------------
    fs_label: float = 9.0
    fs_tick: float = 8.0
    fs_title: float = 11.0
    fs_suptitle: float = 13.0
    fs_legend: float = 9.0
    label_inside_pct: float = 55.0
    """A bar at least this wide (% of panel) carries its label inside it."""

    # --- output ------------------------------------------------------------
    dpi: int = 200
    facecolor: str = "white"
    save_pdf: bool = False
    """Write a sibling .pdf next to every .png. Journals ask; screens do not."""

    transparent: bool = False

    def merged(self, **kw):
        """A copy with ``kw`` applied. Unknown keys raise — a silently ignored
        ``dpi=600`` is a figure that went to a journal at 200 dpi."""
        known = {f.name for f in fields(self)}
        bad = [k for k in kw if k not in known]
        if bad:
            raise TypeError(
                "unknown plot setting(s) %s — known: %s"
                % (", ".join(sorted(bad)), ", ".join(sorted(known))))
        return replace(self, **{k: v for k, v in kw.items() if v is not None})


#: The process-wide settings. Read through :func:`settings`, never bound at
#: import time by callers — ``configure()`` replaces this object.
_ACTIVE = PlotConfig()


def settings() -> PlotConfig:
    """The settings in force right now."""
    return _ACTIVE


def configure(**kw) -> PlotConfig:
    """Change the house style for the rest of this process. Returns the new
    config so a notebook cell shows what it did."""
    global _ACTIVE
    _ACTIVE = _ACTIVE.merged(**kw)
    return _ACTIVE


def reset() -> PlotConfig:
    """Back to the bioscout defaults."""
    global _ACTIVE
    _ACTIVE = PlotConfig()
    return _ACTIVE


@contextlib.contextmanager
def using(**kw):
    """Temporary settings::

        with bs.plot.using(dpi=600, save_pdf=True):
            ...
    """
    global _ACTIVE
    old = _ACTIVE
    try:
        _ACTIVE = _ACTIVE.merged(**kw)
        yield _ACTIVE
    finally:
        _ACTIVE = old


def resolve(**kw) -> PlotConfig:
    """The active settings with per-call overrides applied. ``None`` values are
    dropped, so a plotting function can forward every one of its keyword
    arguments without having to know which were actually given."""
    return _ACTIVE.merged(**kw)


__all__ = ["PlotConfig", "settings", "configure", "reset", "using", "resolve"]
