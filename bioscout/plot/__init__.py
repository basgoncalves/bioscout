"""bioscout.plot — project-independent comparison figures.

    import bioscout as bs

    fig = (bs.plot(df)                       # or bs.plot.compare(df)
             .where(Variable="muscle_work_total", Algo="SO")
             .compare("Condition", order=["pre-fatigue", "post-fatigue"])
             .facet("Task", icons=TASK_ICONS)
             .group(bs.plot.MUSCLE_GROUPS)
             .top(8)
             .title("total muscle work ranks")
             .save("results/group/work_ranks.png"))

Three layers, each usable on its own:

``bioscout.plot.work``     .sto files  -> muscle work numbers  (:func:`work_table`)
``bioscout.plot.tidy``     numbers     -> one long table       (:func:`read`)
``bioscout.plot.compare``  table       -> a figure             (:class:`Compare`)

The middle layer is the contract. A bioscout session goes through all three; a
project whose numbers came from anywhere else builds the table itself and uses
the last one. Nothing in here reads a project ``settings.py`` — the house style
lives in :mod:`bioscout.plot.config` and a notebook overrides it at run time
with :func:`configure`.

Quick tour, no data required::

    bs.plot.demo().show()
"""
from __future__ import annotations

import sys as _sys
import types as _types

from .compare import Compare
from .config import PlotConfig, configure, reset, resolve, settings, using
from .tidy import (KEYS, VALUE, cells, counts, from_mapping, group_channels,
                   levels, read, select)
from .work import (MUSCLE_GROUPS, MUSCLE_GROUPS_SPLIT, PHASES, find_trials,
                   group_of, muscle_work, read_sto, session_records,
                   trial_inputs, work_table)

__all__ = [
    # build a figure
    "compare", "Compare", "work_ranks", "curves", "demo",
    # settings (these live in bioscout, not in your project)
    "configure", "settings", "reset", "using", "resolve", "PlotConfig",
    # the tidy table
    "read", "select", "from_mapping", "group_channels", "levels", "cells",
    "counts", "KEYS", "VALUE",
    # numbers out of .sto files
    "work_table", "muscle_work", "session_records", "trial_inputs",
    "find_trials", "read_sto", "group_of", "MUSCLE_GROUPS",
    "MUSCLE_GROUPS_SPLIT", "PHASES",
]


def compare(data=None, **filters):
    """Start a comparison figure from a tidy table (DataFrame, CSV path,
    list of dicts or nested dict). Extra keywords filter rows immediately::

        bs.plot.compare("results/master_results.csv", Variable="work")
    """
    return Compare(data, **filters)


def work_ranks(source, compare_by="Condition", facet_by="Task", where=None,
               group=MUSCLE_GROUPS, title=None, save=None, icons=None,
               order=None, facet_order=None, **style):
    """The ranked muscle-work figure, in one call.

    ``source`` is a tidy table — usually one built by :func:`work_table`. This
    is a thin convenience over the builder; reach for the builder the moment
    you want anything it does not expose::

        bs.plot.work_ranks(rows, compare_by="Condition", facet_by="Task",
                           where={"Algo": "SO"}, top=8,
                           save="results/group/work_ranks.png")
    """
    c = Compare(source)
    if where:
        c = c.where(**where)
    c = (c.compare(compare_by, order=order)
          .facet(facet_by, order=facet_order, icons=icons) if facet_by
         else c.compare(compare_by, order=order))
    if group:
        c = c.group(group)
    c = c.title(title if title is not None
                else "muscle work ranks — colour = rank in %s" % compare_by)
    if style:
        c = c.set(**style)
    if save:
        c.save(save)
    return c


def curves(source, compare_by, facet_by=None, x="Percent", **kw):
    """Mean ± SD waveforms, same selection grammar as :func:`work_ranks`."""
    c = Compare(source).compare(compare_by).curves(x=x)
    if facet_by:
        c = c.facet(facet_by)
    return c.set(**kw) if kw else c


def demo(seed=0):
    """A synthetic table wired into a finished figure — for checking the
    install, and for seeing the layout before you have your own numbers."""
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(seed)
    base = {"Vasti": 100, "Triceps surae": 84, "Gluteus maximus": 66,
            "Hamstrings": 58, "Rectus femoris": 44, "Adductors": 33,
            "Iliopsoas": 21, "Gluteus medius": 14}
    rows = []
    for task, shift in (("run", 1.0), ("cut", 1.15), ("squat", 0.8)):
        for cond, drift in (("pre", 1.0), ("post", 0.88)):
            for trial in range(4):
                for ch, v in base.items():
                    rows.append({"Task": task, "Condition": cond,
                                 "Trial": "%s_%s_%02d" % (task, cond, trial),
                                 "Channel": ch, "Variable": "muscle_work_total",
                                 "Value": v * shift * drift
                                 * float(rng.normal(1.0, 0.12))})
    return (Compare(pd.DataFrame(rows))
            .compare("Condition", order=["pre", "post"])
            .facet("Task")
            .top(8)
            .title("bioscout.plot demo — synthetic data"))


# `bs.plot(df)` as well as `bs.plot.compare(df)`: a module cannot define
# __call__ on itself, but it can be given a subclass of ModuleType that does.
# Worth the trick — the short form is what people actually type in a notebook.
class _PlotModule(_types.ModuleType):
    def __call__(self, data=None, **filters):
        return compare(data, **filters)

    def __dir__(self):
        # __all__ plus the three submodules, so `bs.plot.<TAB>` in a notebook
        # offers the API and not the module's import machinery.
        return sorted(set(__all__) | {"tidy", "work", "config", "Compare"})


_sys.modules[__name__].__class__ = _PlotModule
