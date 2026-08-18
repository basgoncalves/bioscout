"""bioscout.plot.work — muscle work, from .sto files to a tidy table.

    W_i = ∫ F_i(t) · v_i(t) dt

``F`` is whatever force the algorithm produced (static optimisation's
``*_force.sto``, CEINMS' ``MuscleForces.sto``); ``v`` is muscle–tendon
shortening velocity, the negated derivative of ``_MuscleAnalysis_Length.sto``.
That length comes from the kinematics alone, so it is IDENTICAL for every
algorithm run on the same trial — the algorithms differ only in the force,
which is exactly the comparison worth making.

FOUR PHASES, AND SAYING WHICH ONE YOU DREW
    ``total``       ∫|F·v| dt   concentric + eccentric. A muscle doing equal
                                positive and negative work scores high here.
    ``concentric``  ∫ F·v dt over v > 0 only.
    ``eccentric``   ∫ F·|v| dt over v < 0 only.
    ``net``         ∫ F·v dt    — signed; the other three are its parts.

    These rank muscles differently and the difference is not small, so the
    phase is written into the table (``Variable = "muscle_work_total"``) rather
    than left to the caller's memory. Quote a figure, quote the phase.

Nothing here needs OpenSim, scipy or a bioscout session: the .sto reader is
plain text on purpose, so this runs on a collaborator's laptop and in CI.
"""
from __future__ import annotations

import glob
import os

#: Functional groups. Individual heads are not separately interpretable and
#: eighty bars are not a ranking. Superset of the maps the FAIS and
#: Powerlifting projects grew independently; override per project with
#: ``groups=`` or ``.group({...})`` on the builder.
MUSCLE_GROUPS = {
    "Triceps surae":      ("gasmed", "gaslat", "soleus"),
    "Vasti":              ("vasmed", "vaslat", "vasint"),
    "Rectus femoris":     ("recfem",),
    "Hamstrings":         ("bflh", "bfsh", "semimem", "semiten"),
    "Gluteus maximus":    ("glmax1", "glmax2", "glmax3"),
    "Gluteus medius":     ("glmed1", "glmed2", "glmed3"),
    "Gluteus minimus":    ("glmin1", "glmin2", "glmin3"),
    "Iliopsoas":          ("iliacus", "psoas"),
    "Adductors":          ("addbrev", "addlong", "addmagDist", "addmagIsch",
                           "addmagMid", "addmagProx"),
    "Tibialis anterior":  ("tibant",),
    "Tibialis posterior": ("tibpost",),
    "Peroneals":          ("perbrev", "perlong", "pertert"),
    "TFL":                ("tfl",),
    "Sartorius":          ("sart",),
    "Gracilis":           ("grac",),
    "Piriformis":         ("piri",),
}

#: The same map with the adductor magnus compartments kept apart from the other
#: adductors and the peroneals split, as the Powerlifting manuscript draws them.
MUSCLE_GROUPS_SPLIT = dict(
    MUSCLE_GROUPS,
    Adductors=("addbrev", "addlong"),
    **{"Adductor magnus": ("addmagDist", "addmagIsch", "addmagMid",
                           "addmagProx"),
       "Peroneus longus": ("perlong",),
       "Peroneus brevis": ("perbrev",)})
MUSCLE_GROUPS_SPLIT.pop("Peroneals", None)

PHASES = ("total", "concentric", "eccentric", "net")


def _member_of(groups):
    return {m.lower(): g for g, ms in groups.items() for m in ms}


def group_of(name, groups=None):
    """Which functional group a muscle column belongs to, side suffix ignored.
    Returns ``None`` for a column no group claims (``time``, a coordinate, a
    muscle the map does not list)."""
    s = str(name)
    if s.lower() == "time":
        return None
    if s.endswith("_r") or s.endswith("_l"):
        s = s[:-2]
    return _member_of(groups or MUSCLE_GROUPS).get(s.lower())


# ------------------------------------------------------------------ reading
def read_sto(path):
    """``(column_names, ndarray)`` from an OpenSim/CEINMS .sto or .mot.

    Deliberately plain text: this must work in an environment with no OpenSim
    and no scipy. Ragged or non-numeric lines are skipped rather than raising —
    a half-written file from an interrupted run should cost you one trial, not
    the figure.
    """
    import numpy as np
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()
    end = next((i for i, x in enumerate(lines)
                if x.strip().lower() == "endheader"), None)
    if end is None:                     # headerless: first non-numeric row wins
        end = -1
    head = [c.strip() for c in lines[end + 1].replace("\r", "").split("\t")
            if c.strip()]
    rows = []
    for ln in lines[end + 2:]:
        f = [x for x in ln.replace("\r", "").split("\t") if x.strip()]
        if len(f) != len(head):
            continue
        try:
            rows.append([float(x) for x in f])
        except ValueError:
            continue
    return head, np.asarray(rows, dtype=float)


def _column(head, arr, name):
    import numpy as np
    key = next((i for i, c in enumerate(head)
                if str(c).lower() == str(name).lower()), None)
    return None if key is None else np.asarray(arr[:, key], dtype=float)


# -------------------------------------------------------------- the integral
def muscle_work(force, length, side="_r", phase="total", groups=None,
                per_muscle=False):
    """``{group: work in J}`` for one trial and one limb.

    ``force`` and ``length`` are paths to the two .sto files (or already-read
    ``(head, array)`` tuples). The force is resampled onto the length's time
    base with linear interpolation — static optimisation usually writes a
    coarser grid than the muscle analysis, and integrating on the coarser of
    the two throws away velocity detail for no reason.

    Returns ``{}`` rather than raising when either file is missing or unusable,
    so a batch over a part-solved session skips the gaps.
    """
    import numpy as np
    if phase not in PHASES:
        raise ValueError("phase must be one of %s; got %r" % (PHASES, phase))
    try:
        fh, fa = force if isinstance(force, tuple) else read_sto(force)
        lh, la = length if isinstance(length, tuple) else read_sto(length)
    except (OSError, IndexError):
        return {}
    if fa.size == 0 or la.size == 0:
        return {}
    ft, lt = fa[:, 0], la[:, 0]

    out = {}
    for i, col in enumerate(fh):
        if str(col).lower() == "time":
            continue
        if side and not str(col).endswith(side):
            continue
        key = col if per_muscle else group_of(col, groups)
        if key is None:
            continue
        L = _column(lh, la, col)
        if L is None:
            continue
        F = np.interp(lt, ft, fa[:, i])
        ok = np.isfinite(F) & np.isfinite(L) & np.isfinite(lt)
        if ok.sum() < 3:
            continue
        t, F, L = lt[ok], F[ok], L[ok]
        v = -np.gradient(L, t)                       # shortening positive
        p = F * v                                    # instantaneous power
        if phase == "total":
            p = np.abs(p)
        elif phase == "concentric":
            p = np.where(v > 0, p, 0.0)
        elif phase == "eccentric":
            p = np.where(v < 0, np.abs(p), 0.0)
        trapz = getattr(np, "trapezoid", None) or np.trapz
        out[key] = out.get(key, 0.0) + float(trapz(p, t))
    return out


# ---------------------------------------------------------------- the table
def work_table(records, phase="total", groups=None, sides=("_r",),
               per_muscle=False, quiet=True):
    """Many trials -> a tidy table (see :mod:`bioscout.plot.tidy`).

    ``records`` is any iterable of dicts. Two keys are used here — ``force``
    and ``length``, the two .sto paths — and EVERY other key is copied onto the
    rows as a column, so you label your data with whatever your study is
    actually split by::

        rows = bs.plot.work_table([
            {"Task": "run",  "Condition": "pre",  "Trial": "run_01",
             "force": ".../SO_StaticOptimization_force.sto",
             "length": ".../_MuscleAnalysis_Length.sto"},
            ...
        ])

    ``sides`` may hold ``"_r"``, ``"_l"`` or both; the limb lands in a ``Side``
    column so a figure can pool it (the default) or split on it.
    """
    import pandas as pd
    var = "muscle_work_%s" % phase
    rows = []
    for rec in records:
        rec = dict(rec)
        f, l = rec.pop("force", None), rec.pop("length", None)
        if not f or not l or not os.path.isfile(f) or not os.path.isfile(l):
            if not quiet:
                print("[skip] missing inputs for %s" % rec.get("Trial", rec))
            continue
        for side in (sides or ("_r",)):
            w = muscle_work(f, l, side=side, phase=phase, groups=groups,
                            per_muscle=per_muscle)
            if not w:
                if not quiet:
                    print("[skip] no work for %s %s"
                          % (rec.get("Trial", rec), side))
                continue
            for ch, val in w.items():
                rows.append({**rec, "Side": side, "Variable": var,
                             "Channel": ch, "Metric": "work_J", "Value": val})
    if not rows:
        return pd.DataFrame(columns=["Side", "Variable", "Channel", "Metric",
                                     "Value"])
    return pd.DataFrame(rows)


# ----------------------------------------------------- bioscout session walk
def _iterations_root(session):
    numbered = os.path.join(session, "3_iterations")
    return numbered if os.path.isdir(numbered) else session


def find_trials(session, iteration):
    p = os.path.join(_iterations_root(session), iteration)
    if not os.path.isdir(p):
        return []
    return sorted(d for d in os.listdir(p)
                  if os.path.isdir(os.path.join(p, d))
                  and not d.startswith(("_", "."))
                  and d not in ("ceinms_calibration", "static_optimisation"))


def trial_inputs(session, iteration, trial, algo="SO", ceinms_dir=None):
    """``(force_path, length_path)`` for one trial, or ``(None, None)``.

    ``algo`` is ``"SO"`` or ``"CEINMS"``. For CEINMS the newest
    ``Execution_*`` folder wins unless ``ceinms_dir`` names one — pin it when a
    figure has to be reproducible across a re-run that added executions.
    """
    d = os.path.join(_iterations_root(session), iteration, trial)
    length = os.path.join(d, "muscle_analysis", "_MuscleAnalysis_Length.sto")
    if str(algo).upper() == "SO":
        hits = glob.glob(os.path.join(d, "static_optimisation", "*force.sto"))
    else:
        pat = ceinms_dir or "Execution_*"
        hits = glob.glob(os.path.join(d, "ceinms", pat, "MuscleForces.sto"))
    hits = [h for h in hits if os.path.isfile(h)]
    force = max(hits, key=os.path.getmtime) if hits else None
    return (force, length if os.path.isfile(length) else None)


def session_records(session, iteration, algos=("SO",), trials=None,
                    label=None, **keys):
    """Trial records for :func:`work_table`, walked off a bioscout session.

    ``label`` is an optional ``callable(trial_name) -> dict`` that turns a
    trial name into the study's own keys — the task it belongs to, the
    condition, the repetition. That callable is the ONLY project-specific thing
    in this whole path, and it stays in the project::

        recs = bs.plot.session_records(
            sess, "iteration_1", algos=("SO", "CEINMS"),
            label=lambda t: {"Task": task_of(t), "Condition": cond_of(t)},
            Subject="021")
    """
    out = []
    for tr in (trials or find_trials(session, iteration)):
        for algo in algos:
            force, length = trial_inputs(session, iteration, tr, algo)
            if not force or not length:
                continue
            rec = {"Session": os.path.basename(str(session).rstrip("/\\")),
                   "Iteration": iteration, "Trial": tr,
                   "Algo": str(algo).upper(), **keys}
            if label:
                rec.update(label(tr) or {})
            out.append({**rec, "force": force, "length": length})
    return out


__all__ = ["MUSCLE_GROUPS", "MUSCLE_GROUPS_SPLIT", "PHASES", "group_of",
           "read_sto", "muscle_work", "work_table", "find_trials",
           "trial_inputs", "session_records"]
