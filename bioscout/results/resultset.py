"""ResultSet: one result variable across any number of sessions, iterations,
trials and cycles -- a DataFrame with a few helpers, extensible with actions.

    rs = sess.results("so_forces", trial="Gehen*", var="*_r")
    rs.df                         # the data: ID columns + x ('time' or 'pct') + one column per channel
    rs["vasmed_r"]                # x  x  curves  (one column per iteration/trial/cycle)
    rs.where(iteration="gpkv4")   # filter (names, lists or globs on any ID column)
    rs.to_bw().plot()             # actions chain

Add an action (in bioscout, a project, or a notebook)::

    from bioscout.results import action

    @action
    def co_contraction(rs, a="vasmed_r", b="bflh_r"):
        ...
    rs.co_contraction()
"""
from __future__ import annotations

import fnmatch
import functools
from typing import Callable, Dict, List, Optional

import pandas as pd

from . import kinds as _files
from .scan import matches, split
from .windows import ID_COLS

__all__ = ["ResultSet", "ResultSets", "action", "ACTIONS"]

X_COLS = ("pct", "time", "time_rel")

#: name -> function(ResultSet, *args, **kw)
ACTIONS: Dict[str, Callable] = {}


def action(fn=None, *, name=None):
    """Register ``fn(rs, ...)`` as ``ResultSet.<name>(...)`` (and on ResultSets,
    where it runs on every member)."""
    def deco(f):
        ACTIONS[name or f.__name__] = f
        return f
    return deco(fn) if fn is not None else deco


class ResultSet:
    def __init__(self, df: pd.DataFrame, *, variable: str, infos=(), window="trial",
                 index: Optional[pd.DataFrame] = None, errors=(), unit=None):
        self.df = df
        self.variable = variable
        self.infos = list(infos)
        self.window = window
        self.index = index if index is not None else pd.DataFrame()
        self.errors = list(errors)
        kind = _files.kind_of(variable)
        self.unit = unit if unit is not None else (kind.unit if kind else "")

    # -- shape -------------------------------------------------------------
    @property
    def x(self) -> str:
        """'pct' for time-normalised data, else 'time'."""
        return "pct" if "pct" in self.df else "time"

    @property
    def vars(self) -> List[str]:
        return [c for c in self.df.columns if c not in ID_COLS and c not in X_COLS]

    @property
    def ids(self) -> pd.DataFrame:
        """One row per curve."""
        return self.df[ID_COLS].drop_duplicates().reset_index(drop=True)

    @property
    def varying(self) -> List[str]:
        """ID columns that differ between curves (what a legend needs)."""
        ids = self.ids
        return [c for c in ID_COLS if ids[c].nunique() > 1]

    def __len__(self):
        return len(self.ids)

    def info(self, subject, session):
        return next((i for i in self.infos if i.subject == subject and i.session == session), None)

    def _new(self, df, **kw) -> "ResultSet":
        d = dict(variable=self.variable, infos=self.infos, window=self.window,
                 index=self.index, errors=self.errors, unit=self.unit)
        d.update(kw)
        return ResultSet(df, **d)

    # -- selection ---------------------------------------------------------
    def where(self, **ids) -> "ResultSet":
        """Keep curves whose ID columns match (a name, list or glob each)."""
        m = pd.Series(True, index=self.df.index)
        for k, v in ids.items():
            if k not in ID_COLS:
                raise KeyError(f"{k!r} is not one of {ID_COLS}")
            pats = split(v)
            if pats:
                m &= self.df[k].astype(str).map(lambda s: matches(s, pats))
        return self._new(self.df[m].reset_index(drop=True))

    def select(self, var) -> "ResultSet":
        """Keep channels (names or globs)."""
        pats = split(var)
        keep = [c for c in self.vars if any(fnmatch.fnmatchcase(c, p) for p in pats)]
        if not keep:
            raise KeyError(f"{var!r} matches none of {self.vars}")
        return self._new(self.df[[c for c in self.df if c not in self.vars] + keep])

    def __getitem__(self, var):
        """``rs['vasmed_r']`` -> curves table; ``rs[['a', 'b*']]`` -> ResultSet."""
        if isinstance(var, str) and var in self.vars:
            return self.curves(var)
        return self.select(var)

    # -- reshaping ---------------------------------------------------------
    def curves(self, var: str) -> pd.DataFrame:
        """x as index, one column per curve (labelled by the ID columns that vary)."""
        cols = self.varying or ["trial"]
        return self.df.pivot_table(index=self.x, columns=cols, values=var, sort=False)

    def long(self) -> pd.DataFrame:
        """One value per row (ID columns, x, channel, value) -- bioscout.plot.tidy shape."""
        x = [c for c in X_COLS if c in self.df]
        return self.df.melt(id_vars=ID_COLS + x, value_vars=self.vars,
                            var_name="channel", value_name="value")

    # -- display -----------------------------------------------------------
    def _summary(self) -> str:
        ids = self.ids
        parts = [f"{c}: {', '.join(map(str, ids[c].unique()[:6]))}"
                 + (" ..." if ids[c].nunique() > 6 else "")
                 for c in ("iteration", "trial", "cycle") if ids[c].nunique()]
        return (f"ResultSet '{self.variable}' [{self.unit or '-'}] - {len(self)} curves, "
                f"{len(self.vars)} channels, x={self.x}, window={self.window}\n  "
                + "\n  ".join(parts) + f"\n  channels: {', '.join(self.vars[:12])}"
                + (" ..." if len(self.vars) > 12 else ""))

    def __repr__(self):
        return self._summary()

    def _repr_html_(self):
        return f"<pre>{self._summary()}</pre>" + self.df.head().to_html()

    # -- built-in actions (typed so editors autocomplete them; the code lives
    #    in actions.py and can be replaced through the ACTIONS registry) ----
    def plot(self, var=None, *, by="iteration", mean=True, ncols=3, title=None,
             save=None, **where):
        """One subplot per channel, one line per ``by`` group (mean +- SD on
        normalised data). Returns a Plot (``.savefig``, ``.axes``, ``.fig``)."""
        return ACTIONS["plot"](self, var, by=by, mean=mean, ncols=ncols, title=title,
                               save=save, **where)

    def mean(self, by="iteration", sd=False) -> "ResultSet":
        """Mean (or SD) curve per ``by`` group."""
        return ACTIONS["mean"](self, by=by, sd=sd)

    def to_bw(self) -> "ResultSet":
        """Every channel divided by its session's body weight."""
        return ACTIONS["to_bw"](self)

    def peak(self, how="max") -> pd.DataFrame:
        """One row per curve: 'max', 'min' or 'abs' peak of every channel."""
        return ACTIONS["peak"](self, how=how)

    def at(self, x: float) -> pd.DataFrame:
        """Every channel at x (percent or seconds), one row per curve."""
        return ACTIONS["at"](self, x)

    def stats(self) -> pd.DataFrame:
        """max / min / mean of every curve and channel."""
        return ACTIONS["stats"](self)

    # -- actions -----------------------------------------------------------
    def __getattr__(self, name):
        if name.startswith("_") or name not in ACTIONS:
            raise AttributeError(f"ResultSet has no {name!r}. Actions: {sorted(ACTIONS)}")
        return functools.wraps(ACTIONS[name])(functools.partial(ACTIONS[name], self))

    def __dir__(self):
        return sorted(set(super().__dir__()) | set(ACTIONS))

    @property
    def actions(self):
        """Every action and its first docstring line."""
        return {k: (f.__doc__ or "").strip().split("\n")[0] for k, f in sorted(ACTIONS.items())}


class ResultSets(dict):
    """{variable: ResultSet}. Actions run on every member::

        r = sess.results(["ik", "id"], trial="Gehen_01")
        r["joint_angles"].plot()
        r.to_bw()                   # -> ResultSets
    """
    def __getattr__(self, name):
        if name.startswith("_") or name not in ACTIONS:
            raise AttributeError(name)
        return lambda *a, **k: _collect({v: ACTIONS[name](rs, *a, **k) for v, rs in self.items()})

    def __dir__(self):
        return sorted(set(super().__dir__()) | set(ACTIONS))

    def __repr__(self):
        return "\n".join(rs._summary() for rs in self.values()) or "ResultSets {}"

    def _repr_html_(self):
        return "".join(f"<pre>{rs._summary()}</pre>" for rs in self.values())


def _collect(d):
    return ResultSets(d) if all(isinstance(v, ResultSet) for v in d.values()) else d
