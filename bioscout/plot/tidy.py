"""bioscout.plot.tidy — the one table shape every bioscout figure understands.

WHY A TABLE AND NOT A FOLDER WALK
    Three projects have now grown their own version of the same figure
    (``FAIS/code/figure_muscle_work.py``, ``FAIS/code/results.py``,
    ``Powerlifting/results.py``) and each one re-walked ``simulations/`` in its
    own way. The drawing was never the hard part; agreeing on where the numbers
    come from was. So the plotting layer here reads exactly one thing — a LONG
    ("tidy") table, one row per number — and knows nothing about disks,
    sessions or file layouts.

    That is what makes it generic. A bioscout project builds the table with
    :func:`bioscout.plot.work_table`; a project with data from anywhere else
    builds the same columns however it likes, and every figure works unchanged.

THE SHAPE
    One row per number. One column, ``Value``, holds it. Everything else is a
    KEY that describes that number:

        Value     the number                                       (required)
        Channel   what is being ranked / plotted — a muscle group  (usual item)
        Task      running, cutting, squat …
        Condition pre-fatigue / post-fatigue, control/patient, …
        Subject Session Iteration Trial Side Algo Model Variable Metric

    None of the key columns are required and none are special-cased: you tell a
    figure which column to compare across and which to facet by, and any column
    present can play either role. ``Variable``/``Metric`` are the convention for
    "which quantity is this" (``work`` / ``work_J``) so several quantities can
    share one table — that is how the FAIS and Powerlifting master tables are
    already built, and both drop straight in.

TIME SERIES LIVE HERE TOO
    Add an ``x`` column (``Percent``, ``Time``, whatever you name it) and each
    row becomes one sample of a curve rather than one summary number. The same
    selection machinery then feeds the curve renderer. No second schema.
"""
from __future__ import annotations

import os

#: Conventional column order. Purely cosmetic — nothing requires these to exist,
#: and extra columns are always kept.
KEYS = ("Subject", "Session", "Iteration", "Trial", "Task", "Condition",
        "Fatigue", "Group", "Side", "Algo", "Model", "Variable", "Channel",
        "Metric")
VALUE = "Value"


def _pd():
    import pandas as pd
    return pd


# ---------------------------------------------------------------- loading
def read(source, **filters):
    """Anything you might have -> a tidy DataFrame.

    Accepts a DataFrame (returned as-is), a path to a ``.csv`` / ``.csv.gz``,
    a list of row-dicts, or a nested dict (see :func:`from_mapping`).
    ``**filters`` are applied through :func:`select` on the way out, so
    ``read(master, Variable="work", Algo="SO")`` is the whole preamble of every
    figure in one line.
    """
    pd = _pd()
    if source is None:
        raise ValueError("no data given")
    if isinstance(source, pd.DataFrame):
        df = source
    elif isinstance(source, (str, os.PathLike)):
        p = os.fspath(source)
        if not os.path.isfile(p):
            raise FileNotFoundError(p)
        df = pd.read_csv(p)
    elif isinstance(source, dict):
        df = from_mapping(source)
    elif isinstance(source, (list, tuple)):
        df = pd.DataFrame(list(source))
    else:
        raise TypeError("cannot read a tidy table from %r" % type(source).__name__)
    if VALUE not in df.columns:
        raise KeyError(
            "tidy table needs a %r column; got %s"
            % (VALUE, ", ".join(map(str, df.columns))))
    return select(df, **filters) if filters else df


def from_mapping(data, levels=None, item="Channel", value=VALUE):
    """A nested dict -> a tidy table, for when the numbers are already in hand.

    Depth decides the columns, so all three of these work::

        {"Vasti": 12.0, "Hamstrings": 9.1}                     -> Channel, Value
        {"pre": {...}, "post": {...}}                -> Condition, Channel, Value
        {"run": {"pre": {...}, "post": {...}}} -> Task, Condition, Channel, Value

    ``levels`` names the outer levels explicitly (outermost first) when the
    defaults — ``("Task", "Condition")`` — are not what they are.
    """
    pd = _pd()

    def depth(d):
        return 1 + depth(next(iter(d.values()))) if isinstance(d, dict) and d \
            and isinstance(next(iter(d.values())), dict) else 1

    n_outer = depth(data) - 1
    if levels is None:
        levels = ("Task", "Condition")[-n_outer:] if n_outer else ()
    levels = list(levels)
    if len(levels) != n_outer:
        raise ValueError("mapping is %d level(s) deep above the items; got %d "
                         "level name(s) %r" % (n_outer, len(levels), levels))

    rows = []

    def walk(d, keys):
        if len(keys) == n_outer:
            for k, v in d.items():
                rows.append({**dict(zip(levels, keys)), item: k, value: float(v)})
            return
        for k, v in d.items():
            walk(v, keys + [k])

    walk(data, [])
    return pd.DataFrame(rows)


# -------------------------------------------------------------- selecting
def select(df, **filters):
    """Filter rows. Each value may be a scalar, a list/tuple/set of allowed
    values, or a callable predicate::

        select(df, Variable="work", Algo=["SO", "CEINMS"],
               Side=lambda s: str(s).endswith("_r"))

    An unknown column raises rather than being ignored: a filter that silently
    does nothing is a figure that quietly plots the wrong rows.
    """
    for col, want in filters.items():
        if want is None:
            continue
        if col not in df.columns:
            raise KeyError("no column %r in the table; have: %s"
                           % (col, ", ".join(map(str, df.columns))))
        if callable(want):
            df = df[[bool(want(v)) for v in df[col]]]
        elif isinstance(want, (list, tuple, set, frozenset)):
            df = df[df[col].isin(list(want))]
        else:
            df = df[df[col] == want]
    return df


def levels(df, col, order=None):
    """The distinct values of ``col``, in ``order`` if given (unknown names in
    ``order`` are dropped, values missing from it are appended in the order
    they appear — so a partial order is a nudge, not a filter)."""
    seen = list(dict.fromkeys(df[col].tolist()))
    if not order:
        return seen
    head = [v for v in order if v in seen]
    return head + [v for v in seen if v not in head]


def cells(df, compare, item="Channel", value=VALUE, facet=None,
          agg="mean", compare_order=None, facet_order=None):
    """The table, reduced to what a comparison figure actually draws.

    -> ``{facet_value: [(compare_label, {item: number}), ...]}``, columns in
    ``compare_order``, rows in ``facet_order``. With no ``facet``, the single
    key is ``None``.

    ``agg`` collapses everything the figure is NOT splitting on (trials, sides,
    repetitions, subjects) — ``"mean"`` by default, because the question a rank
    figure asks is about the condition, not about one trial. Pass ``"sum"`` for
    quantities that add across limbs, or any name pandas' ``groupby`` accepts.
    """
    for c in (compare, item, value) + ((facet,) if facet else ()):
        if c not in df.columns:
            raise KeyError("no column %r in the table; have: %s"
                           % (c, ", ".join(map(str, df.columns))))
    df = df.dropna(subset=[value])
    out = {}
    for fv in (levels(df, facet, facet_order) if facet else [None]):
        d = df[df[facet] == fv] if facet else df
        cols = []
        for cv in levels(d, compare, compare_order):
            sub = d[d[compare] == cv]
            g = getattr(sub.groupby(item)[value], agg)()
            vals = {k: float(v) for k, v in g.items()
                    if v == v and abs(float(v)) > 0}
            if vals:
                cols.append((str(cv), vals))
        if cols:
            out[fv] = cols
    return out


def counts(df, compare, facet=None, over="Trial"):
    """``{(facet, compare): n}`` — how many distinct ``over`` values back each
    panel. Figures print this as ``n=…``; a panel drawn from one trial and a
    panel drawn from twelve should not look identical."""
    if over not in df.columns:
        return {}
    out = {}
    for fv in ([None] if not facet else levels(df, facet)):
        d = df[df[facet] == fv] if facet else df
        for cv in levels(d, compare):
            out[(fv, str(cv))] = int(d[d[compare] == cv][over].nunique())
    return out


def group_channels(df, mapping, item="Channel", value=VALUE, agg="sum",
                   keep_unmapped=False, strip_side=True):
    """Collapse individual muscles into functional groups.

    Ranking raw muscle names lets a three-compartment gluteus maximus be beaten
    by an intact peroneus longus purely because its force was split three ways
    — an artefact of the model's discretisation, not a statement about the leg.
    ``mapping`` is ``{group: (member, ...)}``; unmapped channels are dropped
    unless ``keep_unmapped``.
    """
    member_of = {m.lower(): g for g, ms in mapping.items() for m in ms}
    df = df.copy()

    def to_group(c):
        s = str(c)
        if strip_side and (s.endswith("_r") or s.endswith("_l")):
            s = s[:-2]
        return member_of.get(s.lower(), s if keep_unmapped else None)

    df[item] = [to_group(c) for c in df[item]]
    df = df[df[item].notna()]
    keys = [c for c in df.columns if c != value]
    return df.groupby(keys, as_index=False, dropna=False)[value].agg(agg)


__all__ = ["KEYS", "VALUE", "read", "from_mapping", "select", "levels",
           "cells", "counts", "group_channels"]
