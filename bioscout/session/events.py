"""Gait/task events from editable definitions, not from code.

Which instants a figure shows (hip drive, impact peak, bottom of a squat ...)
is a METHODS decision, so it lives in data: ``bioscout/session/events.yaml``
ships the defaults per task, ``project.yaml`` overrides them for a project
under ``events:`` and ``session.yaml`` for one session. The keys and their
meaning are documented at the top of ``events.yaml``.

The task, its cycle and its phases come from the movement detector
(``2_experimental/<trial>/movement_detection.yaml``); the signals from the
trial's IK ``.mot`` and ``grf.mot``. Nothing here re-detects foot contacts.

    >>> defs = load_definitions(project_dir, session_dir)
    >>> ev = resolve_events(defs["running"], "r", phases, signals)
    >>> [(e.name, e.time, e.letter) for e in ev]

``bioscout session events TRIAL`` prints what a trial resolves to.
"""
from __future__ import annotations

import copy
import math
import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

#: [events] warnings already printed (each is printed once per process)
_EVENT_WARNED: set = set()

__all__ = ["Event", "load_definitions", "resolve_events", "trial_signals",
           "trial_phases", "events_for_trial", "DEFAULT_FILE"]

DEFAULT_FILE = Path(__file__).with_name("events.yaml")
FUNCTIONS = ("max", "min", "first_local_max", "last_local_max", "start", "end")


@dataclass
class Event:
    name: str                 # "hip drive"
    time: float
    letter: str = ""
    label: str = ""
    phase: str = ""
    landmark: str = ""        # tibia | calcn
    value: float | None = None
    unit: str = ""
    note: str = ""            # e.g. "19,373 deg/s²"
    spec: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# definitions: shipped defaults <- project.yaml <- session.yaml
# --------------------------------------------------------------------------- #
def _yaml(path):
    try:
        import yaml
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except Exception:                                   # noqa: BLE001
        return {}


def _merge(base: dict, over: dict) -> dict:
    """Task -> event -> keys. An event set to null is removed; a key given
    replaces that key only, so an override can change just the window."""
    out = copy.deepcopy(base)
    for task, events in (over or {}).items():
        if events is None:
            out.pop(task, None)
            continue
        dst = out.setdefault(task, {})
        for name, spec in (events or {}).items():
            if spec is None:
                dst.pop(name, None)
            elif isinstance(spec, dict):
                dst.setdefault(name, {}).update(spec)
    return out


def load_definitions(project_dir=None, session_dir=None, defaults=None) -> dict:
    """{task: {event name: spec}} after the three tiers are merged."""
    defs = _yaml(defaults or DEFAULT_FILE)
    for d in (project_dir, session_dir):
        if not d:
            continue
        for fname in ("project.yaml", "session.yaml"):
            p = Path(d) / fname
            if p.is_file():
                defs = _merge(defs, (_yaml(p) or {}).get("events") or {})
    return defs


def definitions_for(defs: dict, task: str) -> dict:
    """The task's events, with the aliases the detector uses; ``_default``
    when nothing matches."""
    t = (task or "").lower()
    for key in (t, t.replace("-", "_"), t.replace("_", " ")):
        if key in defs:
            return defs[key]
    if "squat" in t and "single" in t and "single_leg_squat" in defs:
        return defs["single_leg_squat"]
    if "squat" in t and "squat" in defs:
        return defs["squat"]
    if t in ("run", "sprint", "jog") and "running" in defs:
        return defs["running"]
    if "cut" in t and "cut" in defs:
        return defs["cut"]
    return defs.get("_default", {})


# --------------------------------------------------------------------------- #
# signals and phases of one trial
# --------------------------------------------------------------------------- #
def trial_signals(ik_names, ik_data, degrees, grf=None) -> dict:
    """name -> (t, values). IK columns in DEGREES (pelvis translations in m);
    ``grf_vertical_{l,r}`` and ``grf_anterior_{l,r}`` in N when GRF is given
    as ``(t, {side: vy}, {side: vx})`` (what ``jcf_coverage.grf_for`` returns)."""
    sig = {}
    t = ik_data[:, 0]
    for i, nm in enumerate(ik_names[1:], start=1):
        v = ik_data[:, i].astype(float)
        if not degrees and nm not in ("pelvis_tx", "pelvis_ty", "pelvis_tz"):
            v = np.degrees(v)
        sig[nm] = (t, v)
    # knee_angle is flexion-positive in Rajagopal and flexion-NEGATIVE in
    # GPK/Lerner: ``knee_flexion_{side}`` is always flexion-positive (the
    # larger excursion from zero is flexion; hyperextension is a few degrees)
    for sd in ("l", "r"):
        k = f"knee_angle_{sd}"
        if k in sig:
            t_, v_ = sig[k]
            sig[f"knee_flexion_{sd}"] = (t_, v_ if np.nanmax(v_) >= -np.nanmin(v_) else -v_)
    if grf:
        tg, vys = grf[0], grf[1]
        for sd, vy in vys.items():
            sig[f"grf_vertical_{sd}"] = (tg, np.asarray(vy, float))
        if len(grf) > 2 and grf[2]:
            for sd, vx in grf[2].items():
                sig[f"grf_anterior_{sd}"] = (tg, np.asarray(vx, float))
    return sig


def trial_phases(det: dict, side: str, t0: float, t1: float) -> tuple:
    """(task, {phase: (start, end)}) from a movement_detection.yaml dict,
    for the analysed leg, restricted to [t0, t1]: the cycle's ``stance``
    gives swing/stance; a squat's ``tasks[].phases`` give descent/hold/
    concentric. ``cycle`` is always the window itself."""
    task, phases = "", {}
    best = None
    for c in (det.get("cycles") or []):
        tr = c.get("time_range") or []
        if len(tr) != 2 or (c.get("side") or "")[:1].lower() != side[:1]:
            continue
        ov = min(t1, float(tr[1])) - max(t0, float(tr[0]))
        if ov > 0 and (best is None or ov > best[0]):
            best = (ov, c)
    if best:
        c = best[1]
        task = c.get("task") or det.get("type") or ""
        st = c.get("stance") or []
        c0, c1 = (float(x) for x in c["time_range"])
        if len(st) == 2:
            s0, s1 = float(st[0]), float(st[1])
            phases["swing"] = (c0, s0)
            phases["stance"] = (s0, s1)
            if s1 < c1:
                phases["late swing"] = (s1, c1)
    else:
        best = None
        for tk in (det.get("tasks") or []):
            tr = tk.get("time_range") or []
            if len(tr) != 2 or not tk.get("phases"):
                continue
            if tk.get("side") and (tk["side"] or "")[:1].lower() != side[:1]:
                continue
            ov = min(t1, float(tr[1])) - max(t0, float(tr[0]))
            if ov > 0 and (best is None or ov > best[0]):
                best = (ov, tk)
        if best:
            tk = best[1]
            task = tk.get("task") or det.get("type") or ""
            for ph in tk.get("phases") or []:
                tr = ph.get("time_range") or []
                if len(tr) == 2:
                    phases[str(ph.get("phase"))] = (float(tr[0]), float(tr[1]))
        else:
            task = det.get("type") or ""
    # every phase is clipped to what is simulated; an empty one is dropped
    out = {}
    for k, (a, b) in phases.items():
        a, b = max(a, t0), min(b, t1)
        if b > a:
            out[k] = (a, b)
    # ``cycle`` is the detected cycle / task window, clipped to the data
    if best:
        tr = best[1].get("time_range") or [t0, t1]
        c0, c1 = max(float(tr[0]), t0), min(float(tr[1]), t1)
        out["cycle"] = (c0, c1) if c1 > c0 else (t0, t1)
    else:
        out["cycle"] = (t0, t1)
    return task, out


# --------------------------------------------------------------------------- #
# the resolver
# --------------------------------------------------------------------------- #
def _prepare(t, v, derivative, smooth_ms):
    v = np.asarray(v, float)
    if smooth_ms and len(v) > 3:
        dt = float(np.median(np.diff(t))) or 1e-3
        w = max(3, int(round(smooth_ms / 1000.0 / dt))) | 1
        if w < len(v):
            v = np.convolve(v, np.ones(w) / w, mode="same")
    for _ in range(int(derivative or 0)):
        v = np.gradient(v, t)
    return v


def _local_maxima(v):
    i = np.arange(1, len(v) - 1)
    return i[(v[i] > v[i - 1]) & (v[i] >= v[i + 1])]


def _unit(signal, derivative):
    base = "m" if signal.startswith("pelvis_t") else ("N" if signal.startswith("grf") else "deg")
    return base + ("", "/s", "/s²")[min(int(derivative or 0), 2)]


def resolve_events(defs: dict, side: str, phases: dict, signals: dict,
                   strict=False) -> list:
    """Every event in ``defs`` that the data supports, sorted by time.
    Missing signal/phase: skipped when ``optional``, else raises in strict
    mode and is skipped (with a stderr note) otherwise."""
    out = []
    for name, spec in (defs or {}).items():
        try:
            e = _resolve_one(name, spec, side, phases, signals)
        except (KeyError, ValueError) as exc:
            if spec.get("optional"):
                continue
            if strict:
                raise ValueError(f"{name}: {exc}") from None
            import sys
            _msg = f"  [events] {name}: {exc}"
            if _msg not in _EVENT_WARNED:       # once per process (2026-10-19)
                _EVENT_WARNED.add(_msg)
                print(_msg, file=sys.stderr)
            continue
        if e is not None:
            out.append(e)
    out.sort(key=lambda e: e.time)
    return out


def _resolve_one(name, spec, side, phases, signals):
    sig_name = str(spec.get("signal", "")).replace("{side}", side[:1])
    phase = str(spec.get("phase", "cycle"))
    if phase not in phases:
        raise KeyError(f"phase '{phase}' is not in the simulated window")
    if sig_name not in signals:
        raise KeyError(f"signal '{sig_name}' is not available")
    fn = str(spec.get("function", "max"))
    if fn not in FUNCTIONS:
        raise ValueError(f"function '{fn}' is not one of {FUNCTIONS}")
    a, b = phases[phase]
    w = spec.get("window") or [0.0, 1.0]
    a, b = a + float(w[0]) * (b - a), phases[phase][0] + float(w[1]) * (phases[phase][1] - phases[phase][0])
    deriv, smooth = int(spec.get("derivative", 0) or 0), float(spec.get("smooth_ms", 0) or 0)
    landmark = spec.get("landmark") or ("tibia" if "swing" in phase else "calcn")
    common = dict(letter=str(spec.get("letter", "")), label=str(spec.get("label", name)),
                  phase=phase, landmark=landmark, spec=dict(spec))

    if fn in ("start", "end"):
        return Event(name, float(a if fn == "start" else b), **common)

    t, v = signals[sig_name]
    v = _prepare(t, v, deriv, smooth)
    # the derivative's edge samples are one-sided: keep clear of them
    pad = 0
    if deriv or smooth:
        dt = float(np.median(np.diff(t))) or 1e-3
        pad = max(1, int(round(max(smooth / 1000.0, 0.0) / dt)))
    m = (t >= a) & (t <= b)
    idx = np.where(m)[0]
    if pad and len(idx) > 3 * pad:
        idx = idx[(idx >= pad) & (idx < len(t) - pad)]
    if len(idx) < 3:
        raise ValueError(f"fewer than 3 samples of {sig_name} in {phase} {list(w)}")
    seg = v[idx]
    if fn == "max":
        k = idx[int(np.nanargmax(seg))]
    elif fn == "min":
        k = idx[int(np.nanargmin(seg))]
    else:
        lm = _local_maxima(seg)
        # a local maximum that is the PHASE's global one is not an "impact"
        # peak, it is the main peak the window was meant to set apart from
        pa, pb = phases[phase]
        pm = np.where((t >= pa) & (t <= pb))[0]
        k_phase = pm[int(np.nanargmax(v[pm]))] if len(pm) else -1
        lm = [i for i in lm if idx[i] != k_phase]
        if not len(lm):
            raise ValueError(f"no local maximum of {sig_name} in {phase} {list(w)} "
                             "apart from the window's own peak")
        k = idx[int(lm[0] if fn == "first_local_max" else lm[-1])]
    val = float(v[k])
    unit = _unit(sig_name, deriv)
    note = f"{val:,.0f} {unit}" if unit.endswith("/s²") else ""
    return Event(name, float(t[k]), value=val, unit=unit, note=note, **common)


# --------------------------------------------------------------------------- #
# convenience: everything for a trial folder
# --------------------------------------------------------------------------- #
def events_for_trial(trial, side=None, t0=None, t1=None, strict=False):
    """(task, phases, [Event]) for ``.../3_iterations/<it>/<trial>`` or
    ``.../2_experimental/<trial>``. Uses jcf_coverage's discovery so the
    same IK/GRF files feed both the figure and this listing."""
    from bioscout.plot.jcf_coverage import grf_for, read_sto, measured_side
    trial = Path(trial).resolve()
    if trial.parent.name == "2_experimental":
        # any iteration of it will do for the IK; the first that has one
        its = sorted((trial.parents[1] / "3_iterations").glob(f"*/{trial.name}"))
        if not its:
            raise FileNotFoundError(f"no simulated iteration of {trial.name}")
        trial = its[0]
    ik = trial / "external_biomechanics" / "joint_angles.mot"
    if not ik.is_file():
        cand = sorted((trial / "external_biomechanics").glob("*.mot"))
        if not cand:
            raise FileNotFoundError(f"no IK .mot in {trial / 'external_biomechanics'}")
        ik = cand[0]
    info = {"trial": trial, "subject": trial.parents[3].name, "ik": ik}
    side = side or measured_side(info) or "r"
    ik_names, ik_data = read_sto(str(ik))
    with open(ik) as fh:
        degrees = "indegrees=yes" in fh.read(2000).replace(" ", "").lower()
    grf = grf_for(info)
    det = _yaml(trial.parents[2] / "2_experimental" / trial.name / "movement_detection.yaml")
    a = float(ik_data[0, 0]) if t0 is None else t0
    b = float(ik_data[-1, 0]) if t1 is None else t1
    task, phases = trial_phases(det, side, a, b)
    session_dir = trial.parents[2]
    defs = load_definitions(session_dir.parent.parent.parent, session_dir)
    ev = resolve_events(definitions_for(defs, task), side, phases,
                        trial_signals(ik_names, ik_data, degrees, grf), strict)
    return task, phases, ev


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="bioscout session events",
                                 description="which instants a trial's figures will show")
    ap.add_argument("trial", help=".../3_iterations/<it>/<trial> or .../2_experimental/<trial>")
    ap.add_argument("--side", choices=["r", "l"])
    ap.add_argument("--strict", action="store_true", help="fail on an event the data cannot give")
    ns = ap.parse_args(argv)
    task, phases, ev = events_for_trial(ns.trial, ns.side, strict=ns.strict)
    print(f"task: {task or '?'}")
    for k, (a, b) in phases.items():
        print(f"  {k:12} {a:7.3f} - {b:7.3f} s")
    print("events:")
    for e in ev:
        extra = f"  = {e.value:,.1f} {e.unit}" if e.value is not None else ""
        print(f"  {e.letter:1} {e.time:7.3f} s  {e.name:18} {e.label}{extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
