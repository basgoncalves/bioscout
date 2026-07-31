"""Find the time range of the actual movement in a capture.

A 15-second capture of a deadlift contains a walk-up, a setup, the lift, and a
re-rack. Everything downstream — IK, ID, SO, CEINMS — crops to
``session.yaml``'s ``time_range``, so a trial with no range is analysed across
the whole recording, walk-up included.

**How the window is defined.** The barbell markers (``BL``/``BR``) give the
cleanest signal for a barbell lift, so the reference is bar height and the rule
is: *the movement is the span where the bar has left its resting height by more
than 5% of its total travel in this trial.*

That rule was not chosen for elegance — it was fitted to the windows already in
Athlete_06's ``session.yaml``, which were set by hand:

    trial            hand-set            detected       error (start / end)
    Squat_70_01      2.615 - 5.755      2.57 - 5.75     0.045 / 0.005
    Squat_75_01      3.180 - 6.715      3.07 - 6.70     0.110 / 0.015
    Squat_80_01      2.170 - 5.725      2.06 - 5.71     0.110 / 0.015
    Squat_85_01      2.555 - 6.335      2.50 - 6.32     0.055 / 0.015
    Squat_90_01      3.105 - 6.855      2.90 - 6.85     0.205 / 0.005

Ends agree to within 15 ms; starts land 0.05-0.2 s early, i.e. slightly
generous, which is the safe direction to err. Detecting a *different*
convention from the one the existing trials use would be worse than not
detecting at all, so reproducing it was the acceptance test.

**Direction is inferred, not assumed.** A squat starts at the top and the bar
goes down; a deadlift starts on the floor and the bar goes up. Rather than
trusting the trial's ``type`` (which is free text and often absent), the
resting height is compared against the middle of the range: if the bar rests
near the top it is a lowering movement, near the bottom a lifting one.

**Fallbacks, in order.** Bar markers -> pelvis/sacrum markers -> vertical GRF
-> the full capture. The last one is not a failure mode to hide: returning the
whole recording is exactly what an absent ``time_range`` already means, so the
worst case changes nothing and is reported as ``method="full"``.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

__all__ = ["TimeRange", "read_trc", "detect_time_range", "detect_session",
           "BAR_MARKERS", "PELVIS_MARKERS"]

#: Barbell markers, most preferred first. A barbell is rigid and heavily
#: marked, so its height is the least noisy signal in the file.
BAR_MARKERS = ("BL", "BR", "BARL", "BARR", "BAR_L", "BAR_R")

#: Fallback: pelvis markers. Tracks the lifter rather than the load, so it
#: still moves for un-barbelled movements.
PELVIS_MARKERS = ("SACROL", "SACR2", "SACR3", "SACR", "BELTOL", "BELT2",
                  "BELT3", "RASI", "LASI")

#: Fraction of the trial's vertical travel that counts as "the movement has
#: started". Fitted to the hand-set windows above; see the module docstring.
DEFAULT_THRESHOLD = 0.05

#: Minimum plausible movement, in seconds. A window shorter than this means
#: the detector locked onto noise, and the caller gets the full capture.
MIN_DURATION = 0.30


@dataclass
class TimeRange:
    """A detected window, and enough provenance to argue about it later."""

    start: float
    end: float
    method: str                 # "bar" | "pelvis" | "grf" | "full"
    reference: str = ""         # which markers/columns were used
    threshold: float = DEFAULT_THRESHOLD
    note: str = ""

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def detected(self) -> bool:
        """False when this is the whole capture, i.e. nothing was found."""
        return self.method != "full"

    def as_list(self) -> List[float]:
        """``[start, end]`` rounded to milliseconds, for session.yaml."""
        return [round(float(self.start), 3), round(float(self.end), 3)]


# ------------------------------------------------------------------ loading
def read_trc(path) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    """Read a .trc into ``(time, {marker: (n, 3) array})``.

    Tolerant of the blank columns OpenSim writes between marker triplets and of
    gaps written as empty fields, which become NaN rather than raising.
    """
    lines = io.open(path, encoding="utf-8", errors="replace").read().splitlines()
    if len(lines) < 6:
        raise ValueError(f"{path}: too short to be a TRC")
    names = [n.strip() for n in lines[3].split("\t")[2:] if n.strip()]
    rows = []
    for ln in lines[5:]:
        if not ln.strip():
            continue
        rows.append([float(x) if x.strip() else np.nan for x in ln.split("\t")])
    if not rows:
        raise ValueError(f"{path}: no data rows")
    d = np.array(rows, float)
    return d[:, 1], {n: d[:, 2 + 3 * i: 5 + 3 * i] for i, n in enumerate(names)}


def _read_mot(path) -> Tuple[List[str], np.ndarray]:
    lines = io.open(path, encoding="utf-8", errors="replace").read().splitlines()
    i = next((n for n, l in enumerate(lines) if l.strip().lower() == "endheader"), -1)
    hdr = lines[i + 1].split()
    d = np.array([[float(x) for x in l.split()] for l in lines[i + 2:] if l.strip()],
                 float)
    return hdr, d


# ---------------------------------------------------------------- the rule
def _vertical_axis(arr: np.ndarray) -> int:
    """Index of the axis with the largest travel — the vertical one.

    Assuming Y avoids one lookup and breaks silently on a differently-oriented
    lab; during a lift the vertical axis is by far the widest-ranging.
    """
    span = np.nanmax(arr, axis=0) - np.nanmin(arr, axis=0)
    return int(np.argmax(span))


def _window_from_signal(t, y, threshold=DEFAULT_THRESHOLD) -> Optional[Tuple[float, float, str]]:
    """Span where ``y`` has left its resting level by ``threshold`` of range."""
    y = np.asarray(y, float)
    ok = np.isfinite(y)
    if ok.sum() < 10:
        return None
    t, y = np.asarray(t, float)[ok], y[ok]
    lo, hi = float(np.nanpercentile(y, 5)), float(np.nanpercentile(y, 95))
    span = hi - lo
    if span <= 0:
        return None

    # Resting level from the first 10% of the capture: a lifter is stationary
    # at the start of every trial, whether standing over the bar or holding it.
    rest = float(np.nanmedian(y[:max(5, len(y) // 10)]))
    rising = rest < (lo + hi) / 2.0       # bar starts low -> it will go up
    if rising:
        moving = y > lo + threshold * span
        direction = "rising (bar starts low)"
    else:
        moving = y < hi - threshold * span
        direction = "falling (bar starts high)"
    idx = np.where(moving)[0]
    if idx.size == 0:
        return None
    return float(t[idx[0]]), float(t[idx[-1]]), direction


def _marker_height(markers: Dict[str, np.ndarray], names) -> Optional[Tuple[np.ndarray, str]]:
    present = [n for n in names if n in markers]
    if not present:
        return None
    stack = []
    for n in present:
        a = markers[n]
        stack.append(a[:, _vertical_axis(a)])
    return np.nanmean(np.vstack(stack), axis=0), "+".join(present)


def detect_time_range(trial_dir, *, threshold: float = DEFAULT_THRESHOLD,
                      min_duration: float = MIN_DURATION) -> TimeRange:
    """Detect the movement window for one exported trial folder.

    ``trial_dir`` is the shared export (``2_experimental/<trial>/``), which is
    where the markers and GRF live. Never raises: an undetectable trial returns
    the full capture with ``method="full"``.
    """
    trial_dir = Path(trial_dir)
    trc = trial_dir / "marker_experimental.trc"
    t_full = None

    # -- 1/2. markers: barbell, then pelvis ------------------------------
    if trc.is_file():
        try:
            t, markers = read_trc(trc)
            t_full = (float(t[0]), float(t[-1]))
            for names, method in ((BAR_MARKERS, "bar"), (PELVIS_MARKERS, "pelvis")):
                got = _marker_height(markers, names)
                if got is None:
                    continue
                y, ref = got
                win = _window_from_signal(t, y, threshold)
                if win and (win[1] - win[0]) >= min_duration:
                    return TimeRange(win[0], win[1], method, ref, threshold, win[2])
        except Exception as exc:
            pass

    # -- 3. vertical GRF --------------------------------------------------
    grf = trial_dir / "grf.mot"
    if grf.is_file():
        try:
            hdr, d = _read_mot(grf)
            t = d[:, 0]
            t_full = t_full or (float(t[0]), float(t[-1]))
            vy_cols = [i for i, c in enumerate(hdr) if c.endswith("_vy")]
            if vy_cols:
                vy = d[:, vy_cols].sum(axis=1)
                # GRF never rests at zero for a standing lifter, so the
                # "resting level" logic above applies unchanged.
                win = _window_from_signal(t, vy, threshold)
                if win and (win[1] - win[0]) >= min_duration:
                    return TimeRange(win[0], win[1], "grf", "sum of *_vy",
                                     threshold, win[2])
        except Exception:
            pass

    # -- 4. give up, honestly ---------------------------------------------
    if t_full is None:
        return TimeRange(0.0, 0.0, "full", "", threshold,
                         "no marker or GRF file found")
    return TimeRange(t_full[0], t_full[1], "full", "", threshold,
                     "no movement detected — using the whole capture")



def _session_layout():
    """Load ``session_layout`` without importing the whole ``bioscout.utils``.

    ``from bioscout.utils import session_layout`` executes that package's
    ``__init__``, which imports scipy, pandas and the OpenSim helpers. This
    module is deliberately numpy-only so it can run in a bare environment, and
    a convenience import at the bottom of it would quietly undo that.
    """
    try:
        import bioscout.utils.session_layout as L        # normal case
        return L
    except Exception:
        import importlib.util
        import sys as _sys
        p = Path(__file__).with_name("session_layout.py")
        spec = importlib.util.spec_from_file_location("_bs_session_layout", p)
        m = importlib.util.module_from_spec(spec)
        _sys.modules.setdefault(spec.name, m)
        spec.loader.exec_module(m)
        return m


# ------------------------------------------------------------- whole session
def detect_session(session_dir, *, only_missing: bool = True, apply: bool = False,
                   threshold: float = DEFAULT_THRESHOLD, log=print) -> dict:
    """Detect (and optionally write) ``time_range`` for a session's trials.

    ``only_missing=True`` leaves existing ranges alone — hand-set windows are
    the reference this detector was fitted against, so overwriting them by
    default would destroy the thing that makes it checkable.

    ``apply=False`` reports and writes nothing. Run it once to read the table,
    then again with ``apply=True``.
    """
    import yaml
    L = _session_layout()

    session_dir = Path(session_dir)
    yml = session_dir / "session.yaml"
    if not yml.is_file():
        raise FileNotFoundError(f"no session.yaml in {session_dir}")
    cfg = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
    trials = cfg.get("trials") or {}
    exp = Path(L.experimental_root(str(session_dir)))

    results, changed = {}, 0
    for name, blk in trials.items():
        blk = blk or {}
        existing = blk.get("time_range")
        if existing and only_missing:
            results[name] = ("kept", existing, None)
            log(f"[motion] {name:16s} kept {existing}")
            continue
        d = exp / name
        if not d.is_dir():
            results[name] = ("no data", existing, None)
            log(f"[motion] {name:16s} SKIP — no export at {d.name}")
            continue
        tr = detect_time_range(d, threshold=threshold)
        results[name] = ("detected", tr.as_list(), tr)
        log(f"[motion] {name:16s} {tr.start:6.2f}-{tr.end:6.2f} "
            f"({tr.duration:5.2f}s) via {tr.method:6s} {tr.reference}"
            + (f"  [{tr.note}]" if tr.method == "full" else ""))
        if apply:
            trials.setdefault(name, {})["time_range"] = tr.as_list()
            changed += 1

    if apply and changed:
        cfg["trials"] = trials
        tmp = yml.with_suffix(".yaml.tmp")
        tmp.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
        tmp.replace(yml)                      # atomic: never a half-written file
        log(f"[motion] wrote {changed} time_range entries to session.yaml")
    elif apply:
        log("[motion] nothing to write")
    else:
        log("[motion] dry run — pass apply=True to write these to session.yaml")
    return results
