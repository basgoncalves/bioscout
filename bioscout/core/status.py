"""What is on disk, per session -- the read-only page you check a run against.

    from bioscout.core import status
    status.table(project_dir)                     # DataFrame, one row per session
    status.table(project_dir, verbose=True)       # + one row per trial x stage

    bioscout project status [PATH] [--subjects 009,010] [--sessions pre,post]

Runs nothing and writes nothing. Every column is a file test:

    mass      session.yaml body_mass            windowed  trials with a time_range
    trials    trials to solve                   jc_trc    static trial has joint centres
    emg_only  captures with no markers          model     the iteration's scaled model
    staged    trials with a c3d in 1_c3dfiles/   solved    trials with a JRA on disk
    exported  trials with 2_experimental/<trial>/

`solved` is the joint reaction after static optimisation
(``joint_contact_forces/output_so.sto``) -- the contact
force a project reports -- not merely "SO wrote something".

The roster comes from ``project.yaml``'s ``project:`` section when it has one
(``subjects:``, ``skip_subjects:``, ``session_states:``); otherwise from the
folders under ``simulations/``.
"""
from __future__ import annotations

import glob
import os
from pathlib import Path

__all__ = ["subjects", "sessions_for", "STAGE_OUTPUTS", "trial_stages", "table"]

#: What each stage leaves behind, relative to ``3_iterations/<iteration>/<trial>/``.
STAGE_OUTPUTS = [
    ("IK",     "external_biomechanics/joint_angles.mot"),
    ("ID",     "external_biomechanics/inverse_dynamics.sto"),
    ("MA",     "muscle_analysis/_MuscleAnalysis_Length.sto"),
    ("SO",     "static_optimisation/*StaticOptimization_force.sto"),   # + legacy SO_ prefix
    ("CEINMS", "ceinms/Execution_a*/MuscleForces.sto"),
    ("mew",    "mew/MuscleForces.sto"),
    ("JRA",    "joint_contact_forces/output_so.sto"),
]

NON_SUBJECT_DIRS = {"_to_delete", "_rmtest", "backups", "_export"}


def _facts(project_dir):
    try:
        from bioscout.project_config import project_facts
        return project_facts(project_dir) or {}
    except Exception:                                          # noqa: BLE001
        return {}


def _yaml(path):
    import yaml
    try:
        return yaml.safe_load(Path(path).read_text(encoding="utf-8", errors="ignore")) or {}
    except (OSError, ValueError):
        return {}


def subjects(project_dir, only=None):
    """Subject folders under ``simulations/``, honouring project.yaml's
    ``subjects:`` / ``skip_subjects:``."""
    f = _facts(project_dir)
    skip = {str(s) for s in (f.get("skip_subjects") or [])}
    root = Path(project_dir) / "simulations"
    have = sorted(p.name for p in root.iterdir()
                  if p.is_dir() and p.name not in NON_SUBJECT_DIRS
                  and not p.name.startswith("_")) if root.is_dir() else []
    want = only if only else f.get("subjects")
    if want and str(want).lower() != "all":
        if isinstance(want, str):
            want = want.replace(",", " ").split()
        keep = {f"{int(s):03d}" if str(s).strip().isdigit() else str(s) for s in want}
        have = [s for s in have if s in keep]
    return [s for s in have if s not in skip]


def sessions_for(project_dir, subject, only=None):
    """Session folders that carry a session.yaml, in ``session_states`` order."""
    d = Path(project_dir) / "simulations" / str(subject)
    if not d.is_dir():
        return []
    have = [p.name for p in d.iterdir() if p.is_dir() and (p / "session.yaml").is_file()]
    states = list(_facts(project_dir).get("session_states") or [])
    order = {n: i for i, n in enumerate(states)}
    have = sorted(have, key=lambda n: (order.get(n, len(order)), n))
    if only and str(only).lower() != "all":
        if isinstance(only, str):
            only = only.replace(",", " ").split()
        low = {str(o).lower() for o in only}
        have = [h for h in have if h.lower() in low]
    return have


def trial_stages(session_dir, trial, iteration):
    """``{stage: bool}`` -- which stage outputs exist for one trial."""
    base = Path(session_dir) / "3_iterations" / iteration / trial
    out = {}
    for name, rel in STAGE_OUTPUTS:
        pat = str(base / rel)
        hits = glob.glob(pat) if "*" in pat else [pat]
        out[name] = any(os.path.isfile(h) and os.path.getsize(h) > 0 for h in hits)
    return out


_MARKERS_CACHE = {}


def has_markers(c3d):
    """True when a capture carries marker trajectories, from the 512-byte c3d
    header (POINT count) -- no ezc3d needed. None when unreadable.

    THIS is the rule that decides what can be solved: a capture with no markers
    cannot go through IK/ID, so it is used only to set the session's EMG
    maximum. On a strength session that is every MVIC, and no name pattern
    catches them reliably.
    """
    import struct
    c3d = str(c3d)
    try:
        key = (c3d, os.path.getsize(c3d))
    except OSError:
        return None
    if key in _MARKERS_CACHE:
        return _MARKERS_CACHE[key]
    val = None
    try:
        with open(c3d, "rb") as fh:
            h = fh.read(12)
        if len(h) >= 12 and h[1] == 0x50:
            val = struct.unpack("<4H", h[2:10])[0] > 0
    except OSError:
        val = None
    _MARKERS_CACHE[key] = val
    return val


def _analysis_trials(cfg, session_dir=None):
    """(trials that can be solved, the marker-less EMG-only captures).

    Excluded: the static trial, calibration-rig captures, and every capture
    with no marker data -- read from the staged c3d where there is one, and
    from session.yaml's flags where there is not."""
    static = cfg.get("static_trial")
    skip_types = {"static", "calibration", "mvic"}
    tcfg = cfg.get("trials") or {}
    emg_only = set(cfg.get("normalisation_trials") or [])
    emg_only |= {t for t, m in tcfg.items()
                 if isinstance(m, dict) and m.get("emg_only")}
    for t, m in tcfg.items():
        mk = has_markers(Path(session_dir) / "1_c3dfiles" / f"{t}.c3d") if session_dir else None
        if mk is False:
            emg_only.add(t)
        elif mk is True:
            emg_only.discard(t)
        elif mk is None and isinstance(m, dict) and m.get("emg_normalisation") \
                and str(m.get("type", "")).lower() in ("generic", "mvic", ""):
            emg_only.add(t)
    return [t for t, m in tcfg.items()
            if t != static and str((m or {}).get("type", "")).lower() not in skip_types
            and t not in emg_only], emg_only


def table(project_dir=".", subjects_=None, sessions=None, iteration=None,
          verbose=False, log=print):
    """One row per session (plus one per trial when ``verbose``). Returns a
    pandas DataFrame, or a list of dicts when pandas is not installed."""
    project_dir = Path(project_dir)
    facts = _facts(project_dir)
    iteration = iteration or facts.get("default_iteration") or "gpk"
    rows, trows = [], []
    for sub in subjects(project_dir, subjects_):
        sess = sessions_for(project_dir, sub, sessions)
        if not sess:
            rows.append(dict(session=f"{sub}/-", note="no session.yaml"))
            continue
        for s in sess:
            sdir = project_dir / "simulations" / sub / s
            cfg = _yaml(sdir / "session.yaml")
            tcfg = cfg.get("trials") or {}
            an, emg_only = _analysis_trials(cfg, sdir)
            static = cfg.get("static_trial") or "static1"
            itcfg = (cfg.get("iterations") or {}).get(iteration) or {}
            model = itcfg.get("model_scaled") or itcfg.get("so_model")
            mpath = (Path(os.path.normpath(sdir / "3_iterations" / iteration / model))
                     if model else None)
            rows.append(dict(
                session=f"{sub}/{s}", mass=cfg.get("body_mass"), trials=len(an),
                emg_only=len(emg_only),
                staged=sum((sdir / "1_c3dfiles" / f"{t}.c3d").is_file() for t in an),
                exported=sum((sdir / "2_experimental" / t).is_dir() for t in an),
                windowed=sum(bool((tcfg.get(t) or {}).get("time_range")) for t in an),
                jc_trc=(sdir / "2_experimental" / static /
                        "marker_experimental_jc.trc").is_file(),
                model=bool(mpath and mpath.is_file()),
                solved=sum(trial_stages(sdir, t, iteration)["JRA"] for t in an),
                note="" if iteration in (cfg.get("iterations") or {})
                     else f"no iteration {iteration!r}"))
            if verbose:
                for t in an:
                    trows.append(dict(session=f"{sub}/{s}", trial=t,
                                      type=(tcfg.get(t) or {}).get("type"),
                                      window=(tcfg.get(t) or {}).get("time_range"),
                                      **trial_stages(sdir, t, iteration)))
    if log:
        n = sum(r.get("trials") or 0 for r in rows)
        done = sum(r.get("solved") or 0 for r in rows)
        log(f"[status] {project_dir}  iteration {iteration}: {len(rows)} session(s), "
            f"{n} solvable trial(s), {done} with a JRA")
    try:
        import pandas as pd
        df = pd.DataFrame(rows).set_index("session") if rows else pd.DataFrame()
        if verbose:
            return df, (pd.DataFrame(trows).set_index(["session", "trial"])
                        if trows else pd.DataFrame())
        return df
    except ImportError:
        return (rows, trows) if verbose else rows
