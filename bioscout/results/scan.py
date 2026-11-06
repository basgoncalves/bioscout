"""Find sessions and their result files. Reads folder names and session.yaml /
cycles.csv only -- never a result file."""
from __future__ import annotations

import fnmatch
import glob
import os
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence

import pandas as pd

from . import kinds as _files

__all__ = ["SessionInfo", "Source", "find_sessions", "scan", "split"]

EXPERIMENTAL_DIRS = ("2_experimental", "experimental")
ITERATIONS_DIRS = ("3_iterations",)
NON_ITERATION = {"1_c3dfiles", "c3dfiles", "2_experimental", "experimental",
                 "3_iterations", "4_outputs", "logs", "results",
                 "movement_detection", "models", "setupFiles", "setup_files",
                 "manuscript", "recordings", "ceinms_calibration"}


@dataclass
class SessionInfo:
    subject: str
    session: str
    path: str
    body_mass: Optional[float] = None
    tasks: Dict[str, str] = field(default_factory=dict)        # trial -> type
    cycles: Dict[str, List[dict]] = field(default_factory=dict)  # trial -> cycles.csv rows
    iterations: Dict[str, dict] = field(default_factory=dict)  # session.yaml iterations: (color, label)

    @property
    def body_weight(self) -> Optional[float]:
        return float(self.body_mass) * 9.81 if self.body_mass else None


@dataclass
class Source:
    variable: str
    path: str
    session: SessionInfo
    iteration: str          # "" for experimental
    trial: str


# ----------------------------------------------------------------- helpers --- #
def split(arg) -> Optional[List[str]]:
    """None | 'a,b' | ['a', 'b'] -> list or None."""
    if arg is None:
        return None
    if isinstance(arg, str):
        arg = arg.split(",")
    out = [str(a).strip() for a in arg if a is not None and str(a).strip()]
    return out or None


def matches(name: str, patterns: Optional[Sequence[str]]) -> bool:
    return not patterns or any(fnmatch.fnmatch(name, p) for p in patterns)


def _first_dir(base: str, names: Sequence[str]) -> Optional[str]:
    for n in names:
        p = os.path.join(base, n)
        if os.path.isdir(p):
            return p
    return None


def _subdirs(p: str) -> List[str]:
    try:
        return sorted(d for d in os.listdir(p) if os.path.isdir(os.path.join(p, d)))
    except OSError:
        return []


def read_session(path: str, subject: str = None, session: str = None) -> SessionInfo:
    path = os.path.abspath(path)
    info = SessionInfo(subject or os.path.basename(os.path.dirname(path)),
                       session or os.path.basename(path), path)
    y = os.path.join(path, "session.yaml")
    if os.path.isfile(y):
        try:
            import yaml
            with open(y, "r", encoding="utf-8") as f:
                d = yaml.safe_load(f) or {}
            info.body_mass = d.get("body_mass")
            for t, td in (d.get("trials") or {}).items():
                if isinstance(td, dict):
                    info.tasks[str(t)] = str(td.get("type") or "")
            info.iterations = {str(k): (v or {}) for k, v in (d.get("iterations") or {}).items()
                               if isinstance(v, (dict, type(None)))}
        except Exception as e:                                  # noqa: BLE001
            print(f"  [warn] {y}: {e}")
    cyc = os.path.join(path, "movement_detection", "cycles.csv")
    if os.path.isfile(cyc):
        try:
            c = pd.read_csv(cyc)
            for t, g in c.groupby("trial"):
                info.cycles[str(t)] = g.to_dict("records")
        except Exception as e:                                  # noqa: BLE001
            print(f"  [warn] {cyc}: {e}")
    return info


def simulations_dir(project: str) -> str:
    sim = os.path.join(project, "simulations")
    if os.path.isdir(sim):
        return sim
    if os.path.basename(os.path.normpath(project)) == "simulations":
        return project
    raise FileNotFoundError(f"no simulations/ folder in {project}")


def find_sessions(project: str, subjects=None, sessions=None) -> List[SessionInfo]:
    """Every ``simulations/<subject>/<session>`` that looks like a session."""
    sim = simulations_dir(project)
    subjects, sessions = split(subjects), split(sessions)
    out = []
    for subj in _subdirs(sim):
        if subj.startswith((".", "_")) or not matches(subj, subjects):
            continue
        for ses in _subdirs(os.path.join(sim, subj)):
            p = os.path.join(sim, subj, ses)
            if not matches(ses, sessions):
                continue
            if os.path.isfile(os.path.join(p, "session.yaml")) or \
                    _first_dir(p, ITERATIONS_DIRS + EXPERIMENTAL_DIRS):
                out.append(read_session(p, subj, ses))
    return out


def _newest_execution(rels: List[str]) -> List[str]:
    """Keep only the newest ceinms/*Execution* folder's files."""
    execs = sorted({m.group(0) for f in rels
                    for m in [re.search(r"ceinms/[^/]*Execution[^/]*", f)] if m})
    if len(execs) <= 1:
        return rels
    return [f for f in rels if "Execution" not in f or execs[-1] in f]


def _trial_files(trial_dir: str) -> List[str]:
    rels = []
    for root, dirs, fns in os.walk(trial_dir):
        dirs[:] = [d for d in dirs if d != "ceinms_calibration"]
        rels += [os.path.relpath(os.path.join(root, fn), trial_dir).replace(os.sep, "/")
                 for fn in fns if fn.lower().endswith((".sto", ".mot"))]
    return _newest_execution(rels)


def _trial_dirs(info: SessionInfo, iterations, trials, experimental):
    """(iteration, trial, folder) for every trial folder of one session."""
    exp = _first_dir(info.path, EXPERIMENTAL_DIRS)
    if experimental and exp:
        for tr in _subdirs(exp):
            if matches(tr, trials):
                yield "", tr, os.path.join(exp, tr)
    root = _first_dir(info.path, ITERATIONS_DIRS) or info.path
    for it in _subdirs(root):
        if it in NON_ITERATION or it.startswith((".", "_")) or not matches(it, iterations):
            continue
        for tr in _subdirs(os.path.join(root, it)):
            if matches(tr, trials):
                yield it, tr, os.path.join(root, it, tr)


def scan(infos: Iterable[SessionInfo], iterations=None, trials=None, variables=None,
         experimental=True, verbose=False) -> List[Source]:
    """Every result file of ``infos`` whose variable is wanted."""
    iterations, trials = split(iterations), split(trials)
    pats = _files.resolve(variables)
    out: List[Source] = []
    for info in infos:
        n0 = len(out)
        for it, tr, td in _trial_dirs(info, iterations, trials, experimental):
            for rel in _trial_files(td):
                v = _files.variable_for(rel)
                if v and _files.wanted(v, pats):
                    out.append(Source(v, os.path.join(td, rel), info, it, tr))
        if verbose:
            print(f"  {info.subject}/{info.session}: {len(out) - n0} files")
    return out
