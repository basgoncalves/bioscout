"""bioscout.results — load, analyse, plot and export simulation results.

From a session, iteration or project (all the same call)::

    sess = PROJECT.session("K2L", "11_03_24")
    sess.results()                                       # what is on disk (no file read)
    sess.results.files                                   # every file kind, its aliases and unit

    f = sess.results("so_forces", trial="Gehen_01", iteration="gpkv4", var=["vasmed_r", "soleus_r"])
    f.df                                                 # time | vasmed_r | soleus_r (+ ID columns)
    f.plot()

    f = sess.results("so_forces", trial="Gehen*", var="*_r", window="cycle")   # many at once
    f.mean("iteration").plot()
    f.to_bw().peak()

    r = sess.results(["ik", "id", "jcf_so"], trial="Gehen_01")                 # several files
    r["joint_angles"].plot(var="*_r")

Without bioscout objects::

    from bioscout import results
    results.load(r"C:/.../simulations/K2L/11_03_24", "ik")     # a session folder
    results.load(r"C:/.../ExampleData", "ik", subject="K2L")   # or a project

Layers (each extensible on its own):

    kinds      file kind registry       -> register_file(...)
    scan       which sessions/files exist
    windows    trial / cycle / stance cutting + time normalisation
    load       read + cut -> ResultSet
    resultset  ResultSet + actions      -> @action
    export     CSVs for Excel/JASP/R    (``bioscout project results``)
"""
from __future__ import annotations

import os

import pandas as pd

from . import actions as _actions          # noqa: F401  (registers built-in actions)
from .export import export_results
from .kinds import FILES, describe, register_file
from .io import read_storage
from .load import available, load_infos
from .load import load as _load
from .resultset import ACTIONS, ResultSet, ResultSets, action
from .scan import find_sessions, read_session
from .windows import ID_COLS

__all__ = ["load", "Results", "ResultSet", "ResultSets", "action", "ACTIONS",
           "register_file", "FILES", "files", "read_storage", "export_results",
           "find_sessions", "ID_COLS"]


def files():
    """The file kinds as a table: name, aliases, unit, description."""
    return describe()


def load(path, file=None, *, subject=None, session=None, **kw):
    """``path`` = a session folder (holds session.yaml) or a project folder.
    ``file=None`` -> availability table; otherwise see :meth:`Results.__call__`."""
    return Results(lambda: load_infos(path, subject, session))(file, **kw)


class Results:
    """``session.results`` / ``iteration.results`` / ``project.results``.

    Call it to load; nothing is read until you do. Fixed filters (the
    iteration of an Iteration, the subject/session of a Session) are applied
    on every call."""

    def __init__(self, infos, **fixed):
        self._infos = infos                  # callable -> [SessionInfo], re-read every call
        self._fixed = fixed

    def __call__(self, file=None, *, trial=None, iteration=None, var=None,
                 window="trial", points=101, normalise=None, tasks=None,
                 experimental=True, jobs=8, subject=None, session=None
                 ) -> "ResultSet | ResultSets | pd.DataFrame":
        """Load one or more result files.

        file        name, alias, group or glob - 'so_forces', 'ik', 'jcf_so',
                    'moment_arms', 'joint_*' - or a list. None: what exists.
        trial       name / list / glob ('Gehen*'); None = all
        iteration   name / list / glob; None = all
        var         channels in the file, names or globs ('vasmed_r', '*_r')
        window      'trial' (whole file, raw time - default), 'cycle' or 'stance'
                    (from movement_detection/cycles.csv, time-normalised to `points`)
        normalise   force on/off (default: on for cycle/stance, off for trial)
        tasks       cycles.csv task filter, e.g. 'walking'
        subject, session   narrow a project-wide call (names / globs)

        Returns a ResultSet when ``file`` is one variable ('so_forces'), else
        ResultSets {variable: ResultSet} (a list, a group like 'moment_arms', a glob).
        """
        iteration = self._fixed.get("iteration", iteration)
        infos = self._infos()
        if subject or session:
            from .scan import matches, split
            infos = [i for i in infos if matches(i.subject, split(subject))
                     and matches(i.session, split(session))]
        if file is None:
            return available(infos, iteration=iteration, trial=trial,
                             experimental=experimental)
        return _load(infos, file, iteration=iteration, trial=trial, var=var,
                     window=window, points=points, normalise=normalise, tasks=tasks,
                     experimental=experimental, jobs=jobs)

    def plot_iaa(self, trial=None, iteration=None, *, side="r", engine="opensim", group=True,
                 top=8, bw=None, window="trial", title=None, save=None, **kw):
        """The IAA summary, 3 x 3, contributions stacked (positive up, negative down;
        black = sum, dashed = measured):

          row 1  centre-of-mass acceleration  X, Y, Z            (IAA)
          row 2  ground reaction force under the ``side`` foot  X, Y, Z   (IAA)
          row 3  sagittal hip / knee / ankle moments on ``side``: each muscle's SO
                 force x moment arm (muscle_moments_so), dashed = inverse dynamics

        ``engine`` "opensim" | "pyosim"; ``bw`` body weight in N (GRF in BW, moments in
        N*m/kg); ``group`` muscles into groups (False: individual muscles)."""
        from .plotting import _stack_grid, _stack_frame, _xlabel
        from bioscout.simulate import iaa_files as _iaf
        load = lambda f, **k: self(f, trial=trial, iteration=iteration, window=window, **k, **kw)

        def panel(f, title, measured=None, k=None, unit=None):
            try:
                rs = load(f)
            except LookupError as e:
                print(f"[results] {f}: {str(e).splitlines()[0]}")
                return None
            fr = _stack_frame(rs, None, group)
            if measured is not None:
                fr = fr.drop(columns=[c for c in ("total", "measured") if c in fr])
                fr["total"] = fr.sum(1)
                try:
                    m = _stack_frame(measured[0], [measured[1]], False)[measured[1]]
                    fr["measured"] = m.reindex(fr.index, method="nearest")
                except Exception:                                    # noqa: BLE001
                    pass
            kk, uu = _iaf._unit(f.split("/", 1)[-1])
            return dict(title=title, frame=fr, k=k if k is not None else kk,
                        unit=unit or uu, xlabel=_xlabel(rs))

        e = f"iaa_{engine}"
        panels = [panel(f"{e}/center_of_mass_{a}", f"COM {a}") for a in "XYZ"]
        gk, gu = (1.0 / bw, "BW") if bw else (1.0, "N")
        panels += [panel(f"{e}/grf_calcn_{side}_{a}", f"GRF {side.upper()} {a}", k=gk, unit=gu) for a in "XYZ"]
        try:
            idrs = load("joint_moments")
        except LookupError:
            idrs = None
        mk, mu = (9.81 / bw, "N·m/kg") if bw else (1.0, "N·m")
        for j, lab in (("hip_flexion", "hip flexion"), ("knee_angle", "knee flexion"), ("ankle_angle", "ankle dorsiflexion")):
            c = f"{j}_{side}"
            panels.append(panel(f"muscle_moments_so/{c}", f"{lab} {side.upper()} moment",
                                measured=(idrs, f"{c}_moment") if idrs is not None else (None, None),
                                k=mk, unit=mu))
        return _stack_grid(panels, ncols=3, top=top, save=save,
                           row_labels=["COM acceleration", "GRF", "joint moments"],
                           title=title or f"Contributions ({engine} IAA; moments: SO force x moment arm), {side.upper()} side")

    @property
    def files(self):
        return describe()

    def available(self, **kw):
        return self(None, **kw)

    def __repr__(self):
        infos = self._infos()
        ses = ", ".join(f"{i.subject}/{i.session}" for i in infos[:5])
        it = f" iteration={self._fixed['iteration']}" if "iteration" in self._fixed else ""
        return (f"<results {ses}{' ...' if len(infos) > 5 else ''}{it}> - call it: "
                f".results('so_forces', trial=..., iteration=..., var=...); "
                f".results() lists what exists; .results.files lists file kinds")


def for_session(session_dir, **fixed) -> Results:
    return Results(lambda: [read_session(session_dir)], **fixed)


def for_project(project_dir, **fixed) -> Results:
    return Results(lambda: find_sessions(project_dir, fixed.get("subject"),
                                         fixed.get("session")), **fixed)
