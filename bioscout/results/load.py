"""Results files -> DataFrames. The one reader used by ``session.results(...)``,
:func:`bioscout.results.load` and the CSV export."""
from __future__ import annotations

import fnmatch
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable, List, Optional

import pandas as pd

from . import kinds as _files
from .io import read_storage
from .scan import SessionInfo, Source, find_sessions, read_session, scan, split
from .windows import ID_COLS, cut

__all__ = ["read_parts", "load", "load_infos", "available"]


def _select(df: pd.DataFrame, var) -> pd.DataFrame:
    if not var:
        return df
    keep = [c for c in df.columns if c != "time"
            and any(fnmatch.fnmatchcase(c, p) for p in var)]
    return df[["time"] + keep]


def read_parts(sources: Iterable[Source], *, var=None, window="trial", points=101,
               normalise=False, tasks=None, jobs=8):
    """Read + cut every source -> (parts, index_rows, errors), in source order."""
    var, tasks = split(var), split(tasks)

    def one(src):
        try:
            df = read_storage(src.path)
        except Exception as e:                                  # noqa: BLE001
            return None, f"{src.path}: {e}"
        if df.empty:
            return None, f"{src.path}: empty"
        df = _select(df, var)
        if df.shape[1] < 2:
            return ([], []), None
        return cut(df, src.session, src.iteration, src.trial, window=window,
                   points=points, normalise=normalise, tasks=tasks), None

    parts, idx, errors = [], [], []
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
        for res, err in ex.map(one, list(sources)):
            if err:
                errors.append(err)
            else:
                parts += res[0]
                idx += res[1]
    return parts, idx, errors


def load_infos(path, subject=None, session=None) -> List[SessionInfo]:
    """A session folder (holds session.yaml) or a project folder -> sessions."""
    path = os.path.abspath(str(path))
    if os.path.isfile(os.path.join(path, "session.yaml")):
        return [read_session(path)]
    return find_sessions(path, subject, session)


def available(infos, *, iteration=None, trial=None, experimental=True) -> pd.DataFrame:
    """iteration x trial -> number of files per variable. Reads no result file."""
    rows = [dict(subject=s.session.subject, session=s.session.session,
                 iteration=s.iteration or "(experimental)", trial=s.trial,
                 variable=s.variable)
            for s in scan(infos, iteration, trial, None, experimental)]
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    idx = ["iteration", "trial"]
    if df[["subject", "session"]].drop_duplicates().shape[0] > 1:
        idx = ["subject", "session"] + idx
    return df.assign(n=1).pivot_table(index=idx, columns="variable", values="n",
                                      aggfunc="sum", fill_value=0)


def load(infos, file, *, iteration=None, trial=None, var=None, window="trial",
         points=101, normalise=None, tasks=None, experimental=True, jobs=8):
    """-> ResultSet when ``file`` names ONE variable, else ResultSets {variable: ResultSet}."""
    from .resultset import ResultSet, ResultSets
    if normalise is None:
        normalise = window != "trial"
    sources = scan(infos, iteration, trial, file, experimental)
    if not sources:
        have = sorted({s.variable for s in scan(infos, iteration, trial, None, experimental)})
        raise LookupError(f"no {file!r} files for iteration={iteration!r} trial={trial!r}. "
                          f"Found: {', '.join(have) or 'nothing'}")
    by_var = {}
    for s in sources:
        by_var.setdefault(s.variable, []).append(s)
    out = ResultSets()
    for v, srcs in by_var.items():
        parts, idx, errors = read_parts(srcs, var=var, window=window, points=points,
                                        normalise=normalise, tasks=tasks, jobs=jobs)
        for e in errors:
            print(f"  [warn] {e}")
        if not parts:
            continue
        df = pd.concat(parts, ignore_index=True)
        out[v] = ResultSet(df, variable=v, infos=infos, window=window,
                           index=pd.DataFrame(idx), errors=errors)
    if not out:
        raise LookupError(f"{file!r}: no data for var={var!r}")
    single = (isinstance(file, str) and len(out) == 1
              and next(iter(out)) == _files.canonical(file.strip()))
    return next(iter(out.values())) if single else out
