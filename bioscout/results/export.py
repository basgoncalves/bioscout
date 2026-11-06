"""Every time-varying result of a project -> analysis-ready CSVs.

``bioscout project results <PROJECT>`` (or :func:`export_results`) writes::

    <project>/results/README.txt
                     index.csv                              one row per exported cycle
                     joint_angles/knee_angle_r.csv          ONE file per channel holding
                     moment_arms/knee_angle_r/bflh_r.csv    every subject/session/iteration/trial/cycle

Each file: one row per curve -- ``subject, session, iteration, trial, task,
cycle, side, max, min, mean, pct_000 ... pct_100`` (or long format with
``normalise=False``). Nothing under ``simulations/`` is modified.
"""
from __future__ import annotations

import datetime as _dt
import os
import re
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from . import kinds as _files
from .load import read_parts
from .scan import Source, find_sessions, scan, split
from .windows import ID_COLS

__all__ = ["export_results", "list_variables", "add_arguments", "run"]


def list_variables(sources) -> pd.DataFrame:
    rows: Dict[str, dict] = {}
    for s in sources:
        r = rows.setdefault(s.variable, {"files": 0, "iterations": set()})
        r["files"] += 1
        r["iterations"].add(s.iteration or "(experimental)")
    return pd.DataFrame([{"variable": k, "files": v["files"], "iterations": len(v["iterations"])}
                         for k, v in sorted(rows.items())])


def _safe(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]+', "_", name).strip() or "unnamed"


def _write(df, path, sep, decimal, fmt):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False, sep=sep, decimal=decimal, float_format=fmt,
              encoding="utf-8-sig" if sep == ";" else "utf-8")


def _channel_tables(parts, normalise, points):
    """parts -> {channel: DataFrame} in the export's row layout."""
    pct_cols = [f"pct_{i:03d}" for i in range(points)]
    per: Dict[str, List[Tuple[tuple, np.ndarray]]] = {}
    for part in parts:
        ids = tuple(part[c].iloc[0] for c in ID_COLS)
        for ch in part.columns:
            if ch in ID_COLS or ch in ("pct", "time", "time_rel"):
                continue
            per.setdefault(ch, []).append(
                (ids, part[ch].to_numpy(float) if normalise
                 else part[["time", "time_rel", ch]].to_numpy(float)))
    for ch, rows in per.items():
        idf = pd.DataFrame([r[0] for r in rows], columns=ID_COLS)
        if normalise:
            arr = np.vstack([r[1] for r in rows])
            with np.errstate(all="ignore"):
                st = pd.DataFrame({"max": np.nanmax(arr, 1), "min": np.nanmin(arr, 1),
                                   "mean": np.nanmean(arr, 1)})
            df = pd.concat([idf, st, pd.DataFrame(arr, columns=pct_cols)], axis=1)
        else:
            blocks = []
            for ids, a in rows:
                b = pd.DataFrame(a, columns=["time", "time_rel", "value"])
                for c, v in zip(ID_COLS, ids):
                    b[c] = v
                blocks.append(b)
            df = pd.concat(blocks, ignore_index=True)[ID_COLS + ["time", "time_rel", "value"]]
        if df.drop(columns=ID_COLS).isna().all().all():
            continue
        yield ch, df.sort_values(ID_COLS, kind="stable")


def export_results(project: str, out_dir: Optional[str] = None, *,
                   subjects=None, sessions=None, iterations=None, trials=None,
                   variables=None, tasks=None, window: str = "stance",
                   points: int = 101, normalise: bool = True,
                   experimental: bool = True, sep: str = ",", decimal: str = ".",
                   float_format: str = "%.6g", jobs: int = 8,
                   list_only: bool = False, verbose: bool = True) -> str:
    """One CSV per channel holding every subject, session, iteration, trial and
    cycle (see the module docstring). ``variables`` takes the same names as
    ``session.results`` (aliases, groups, globs). ``sep=';', decimal=','`` for
    German-locale Excel."""
    project = os.path.abspath(project)
    if verbose:
        print(f"[results] scanning {project}")
    infos = find_sessions(project, subjects, sessions)
    sources = scan(infos, iterations, trials, variables, experimental, verbose)
    table = list_variables(sources)
    if list_only or table.empty:
        print(table.to_string(index=False) if not table.empty else "no result files found")
        return ""
    if out_dir is None:
        base = project if os.path.isdir(os.path.join(project, "simulations")) \
            else os.path.dirname(project)
        out_dir = os.path.join(base, "results")
    os.makedirs(out_dir, exist_ok=True)
    if verbose:
        print(f"[results] {len(sources)} files, {len(table)} variable groups -> {out_dir}")

    by_var: Dict[str, List[Source]] = {}
    for s in sources:
        by_var.setdefault(s.variable, []).append(s)
    index_rows, written, errors = [], [], []
    for k, var in enumerate(sorted(by_var), 1):
        parts, idx, errs = read_parts(by_var[var], window=window, points=points,
                                      normalise=normalise, tasks=tasks, jobs=jobs)
        index_rows += idx
        errors += errs
        vdir = os.path.join(out_dir, *(_safe(p) for p in var.split("/")))
        n = 0
        for ch, df in _channel_tables(parts, normalise, points):
            p = os.path.join(vdir, _safe(ch) + ".csv")
            _write(df, p, sep, decimal, float_format)
            written.append((os.path.relpath(p, out_dir), len(df)))
            n += 1
        if verbose:
            print(f"  [{k}/{len(by_var)}] {var}: {len(by_var[var])} files -> {n} channel CSVs")

    if index_rows:
        idx = pd.DataFrame(index_rows).drop_duplicates(ID_COLS).sort_values(ID_COLS, kind="stable")
        _write(idx, os.path.join(out_dir, "index.csv"), sep, decimal, float_format)
    _readme(out_dir, project, written, window, points, normalise, sep, decimal)
    if errors:
        with open(os.path.join(out_dir, "errors.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(errors))
        print(f"[results] {len(errors)} files could not be read -> errors.txt")
    print(f"[results] done: {len(written)} CSVs in {out_dir}")
    return out_dir


def _readme(out_dir, project, written, window, points, normalise, sep, decimal):
    groups: Dict[str, int] = {}
    for rel, _ in written:
        g = os.path.dirname(rel).replace("\\", "/")
        groups[g] = groups.get(g, 0) + 1
    L = [f"bioscout results - {_dt.datetime.now():%Y-%m-%d %H:%M}",
         f"source: {project}", "",
         "One CSV per variable: <group>/<channel>.csv, e.g. joint_moments/knee_angle_r_moment.csv.",
         "Each file holds ALL subjects, sessions, iterations, trials and cycles.",
         ("One row per curve: " + ", ".join(ID_COLS) + ", max, min, mean, "
          f"pct_000..pct_{points - 1:03d} ({window} window, time-normalised)."
          if normalise else
          "Long format: " + ", ".join(ID_COLS) + ", time (s), time_rel (s from window start), value."),
         "  iteration is empty for model-independent data (EMG, GRF, measured JCF).",
         "  cycle/side come from movement_detection/cycles.csv; '<trial>_full' = no cycles.",
         "index.csv: every cycle exported with its window (s) and body mass (kg).",
         f"separator '{sep}', decimal '{decimal}', missing values empty.", "",
         "pandas:",
         "  df  = pd.read_csv('joint_moments/knee_angle_r_moment.csv')",
         "  pct = [c for c in df if c.startswith('pct_')]",
         "  df[df.trial.str.startswith('Gehen')].groupby(['iteration'])[pct].mean().T.plot()",
         "", "Groups (number of channel files):"]
    for g, n in sorted(groups.items()):
        k = _files.kind_of(g) or _files.kind_of(g + "/x")
        L.append(f"  {g + '/':<45} {n:>4}  {k.description if k else ''}")
    with open(os.path.join(out_dir, "README.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


# ------------------------------------------------------------------- CLI --- #
def add_arguments(p):
    p.add_argument("path", nargs="?", default=".", metavar="PROJECT_PATH",
                   help="project folder (holds simulations/) or the simulations folder")
    p.add_argument("-o", "--out", metavar="DIR", help="default: <project>/results")
    p.add_argument("--subjects", metavar="IDS", help="comma-separated, wildcards ok")
    p.add_argument("--sessions", metavar="NAMES")
    p.add_argument("--iterations", metavar="NAMES", help="e.g. 'gpkv4,gpkv4_pct*'")
    p.add_argument("--trials", metavar="NAMES", help="e.g. 'Gehen_*'")
    p.add_argument("--variables", metavar="NAMES",
                   help="e.g. 'emg,joint_*,so_forces,moment_arms' (see --list)")
    p.add_argument("--tasks", metavar="NAMES", help="cycles.csv task, e.g. 'walking'")
    p.add_argument("--window", choices=("stance", "cycle", "trial"), default="stance")
    p.add_argument("--points", type=int, default=101)
    p.add_argument("--no-normalise", action="store_true",
                   help="long files with original samples (time, time_rel, value)")
    p.add_argument("--no-experimental", action="store_true", help="skip EMG/GRF/in-vivo JCF")
    p.add_argument("--excel-de", action="store_true",
                   help="';' separator and ',' decimal for German-locale Excel")
    p.add_argument("--jobs", type=int, default=8, help="parallel file readers")
    p.add_argument("--list", action="store_true", help="only list the variables found")
    return p


def run(ns) -> int:
    export_results(
        ns.path, ns.out, subjects=ns.subjects, sessions=ns.sessions,
        iterations=ns.iterations, trials=ns.trials, variables=ns.variables,
        tasks=ns.tasks, window=ns.window, points=ns.points,
        normalise=not ns.no_normalise, experimental=not ns.no_experimental,
        sep=";" if ns.excel_de else ",", decimal="," if ns.excel_de else ".",
        jobs=ns.jobs, list_only=ns.list)
    return 0


if __name__ == "__main__":
    import argparse
    import sys
    sys.exit(run(add_arguments(argparse.ArgumentParser(
        prog="python -m bioscout.results.export")).parse_args()))
