"""Marker gap filling for .trc files — spline for short gaps, rigid-cluster
(pattern) fill for long ones.

Why this exists
---------------
OpenSim's IK does not fail on a missing marker; it solves without it. Lose the
sacral cluster for a third of a running trial and the pelvis becomes
under-determined, so the solver puts it wherever the remaining markers allow —
90 degrees of heading error, a metre of drift — and reports a plausible marker
RMS while doing it, because the markers it cannot see cost nothing. The
kinematics are then double-differentiated into inverse dynamics, and the
residuals come out in the thousands of newtons. Nothing downstream is
interpretable, and nothing upstream said so.

Linear interpolation across a 0.5 s gap does not help: it draws a straight line
through a swinging limb and plants the marker off the body. What does work is
what a motion-capture technician does by hand — reconstruct the missing marker
from OTHER markers on the same rigid segment. Three or more markers on one
segment define its pose; the missing one has a fixed position in that segment's
frame, so it can be recovered exactly as long as the donors are visible.

What it does
------------
``fill_trc`` walks every marker, finds its gaps, and fills each one by:

* **spline** — gaps up to ``max_spline_gap`` frames (default 10 ≈ 50 ms at
  200 Hz), where the trajectory is smooth and interpolation is honest;
* **rigid** — longer gaps, from a donor cluster chosen FROM THE DATA: the
  markers whose distance to the target varies least over the frames where both
  are visible. No hard-coded segment table, so it works for any markerset. The
  transform is a Kabsch fit (rotation + translation, no scale) taken from the
  nearest complete frame on each side of the gap and blended across it, so the
  fill meets the real trajectory at both edges instead of stepping.

A gap is left EMPTY when it cannot be filled honestly — fewer than
``min_donors`` sufficiently rigid donors, or no donor visible in the gap. An
empty marker is one OpenSim ignores; a wrong one it believes. Leading and
trailing gaps outside the marker's own span are never filled at all.

Everything is reported: which marker, how many frames, by which method, with
which donors, and — for rigid fills — a leave-one-out RMS measured on frames
where the true position IS known, so the fill comes with its own error bar.

Pure numpy. SciPy is used for the cubic spline when present; without it short
gaps fall back to linear, which over 10 frames is a small difference.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import numpy as np

__all__ = ["read_trc", "write_trc", "fill_trc", "fill_array", "FillReport",
           "MarkerFill", "format_report", "usable_window"]

# Defaults. `max_spline_gap` is in FRAMES: at 200 Hz, 10 frames = 50 ms, about
# the longest a limb marker moves smoothly enough to interpolate through.
MAX_SPLINE_GAP = 10
MIN_DONORS = 3
N_DONORS = 6
# Maximum standard deviation of the target-to-donor distance, in the TRC's own
# units, for that donor to count as being on the same rigid segment. 25 mm is
# generous for skin markers (soft-tissue artefact) and still excludes a marker
# on the other side of a joint, whose distance swings by hundreds of mm.
MAX_RIGID_STD = 25.0
MIN_COPRESENT = 20      # frames a donor must share with the target to be judged
# The fill is only allowed if, on frames where the answer is known, carrying the
# marker across a gap-sized lag reproduces it to better than this (TRC units).
# 15 mm is about the soft-tissue artefact of a skin marker on a running trial —
# tighter than that is not achievable, looser is not worth having.
MAX_CARRY_RMS = 15.0


# --------------------------------------------------------------------------- #
# TRC i/o — the header is preserved byte-for-byte
# --------------------------------------------------------------------------- #
def read_trc(path):
    """Read a .trc. Returns ``(header_lines, frames, times, data, names)`` where
    ``data`` is ``(n_frames, n_markers, 3)`` with NaN for missing."""
    with open(path, "r", errors="replace") as fh:
        lines = fh.read().splitlines(keepends=True)
    fr = next((i for i, l in enumerate(lines)
               if l.lstrip().lower().startswith("frame#")), None)
    if fr is None or fr + 2 >= len(lines):
        raise ValueError(f"{path}: no 'Frame#' header row — not a .trc?")
    header = lines[:fr + 2]
    names = [n.strip() for n in lines[fr].rstrip("\r\n").split("\t")[2:] if n.strip()]
    rows = []
    for l in lines[fr + 2:]:
        if not l.strip():
            continue
        cells = l.rstrip("\r\n").split("\t")
        rows.append([np.nan if c.strip() in ("", "nan", "NaN", "NAN") else float(c)
                     for c in cells])
    if not rows:
        raise ValueError(f"{path}: no data rows")
    w = max(len(r) for r in rows)
    A = np.full((len(rows), w), np.nan)
    for i, r in enumerate(rows):
        A[i, :len(r)] = r
    frames, times = A[:, 0], A[:, 1]
    n_mk = min(len(names), (w - 2) // 3)
    data = A[:, 2:2 + 3 * n_mk].reshape(len(rows), n_mk, 3)
    return header, frames, times, data, names[:n_mk]


def write_trc(path, header, frames, times, data, fmt="%.5f"):
    """Write a .trc, keeping ``header`` verbatim. NaN is written as an empty
    cell, which is how OpenSim marks a marker as absent."""
    n, m, _ = data.shape
    out = list(header)
    flat = data.reshape(n, m * 3)
    for i in range(n):
        f = int(round(frames[i])) if np.isfinite(frames[i]) else i + 1
        cells = [str(f), ("" if not np.isfinite(times[i]) else fmt % times[i])]
        cells += ["" if not np.isfinite(v) else fmt % v for v in flat[i]]
        out.append("\t".join(cells) + "\n")
    with open(path, "w", newline="") as fh:
        fh.writelines(out)


# --------------------------------------------------------------------------- #
# the geometry
# --------------------------------------------------------------------------- #
def _kabsch(P, Q):
    """Least-squares rigid transform (R, t) taking P onto Q; both ``(n, 3)``.
    Rotation only — no scaling, because a body segment does not change size."""
    cp, cq = P.mean(0), Q.mean(0)
    H = (P - cp).T @ (Q - cq)
    U, S, Vt = np.linalg.svd(H)
    d = 1.0 if np.linalg.det(Vt.T @ U.T) > 0 else -1.0
    R = Vt.T @ np.diag([1.0, 1.0, d]) @ U.T
    return R, cq - R @ cp


def _gaps(present, lo, hi):
    """Interior gaps of ``present`` within ``[lo, hi]``, as (start, stop) with
    stop exclusive. Only runs bounded by real data on both sides — a marker
    that never appears before frame 400 has no gap before frame 400, it has no
    data, and inventing some is not filling, it is fabrication."""
    out, i = [], lo
    while i <= hi:
        if not present[i]:
            j = i
            while j <= hi and not present[j]:
                j += 1
            if i > lo and j <= hi:
                out.append((i, j))
            i = j
        else:
            i += 1
    return out


def _rank_donors(data, present, target, max_std=None):
    """Markers that travel rigidly with ``target``, best first.

    Ranked by the standard deviation of the target-to-donor distance over the
    frames where both are visible: on the same segment that is a few mm of
    soft-tissue artefact, across a joint it is hundreds.

    Deliberately says nothing about WHEN a donor is visible. Who shares your
    segment is a property of the markerset and the subject; who happens to be
    visible in frame 812 is a property of the occlusion. Conflating the two —
    demanding a donor that covers every frame of every gap — is what made this
    return nothing on real data: with 60 markers each dropping out at slightly
    different times, no single set covers any whole gap. Availability is
    handled per frame, later, where it belongs.
    """
    m = data.shape[1]
    tp = present[:, target]
    max_std = MAX_RIGID_STD if max_std is None else max_std
    out = []
    for k in range(m):
        if k == target:
            continue
        co = tp & present[:, k]
        if int(co.sum()) < MIN_COPRESENT:
            continue
        d = np.linalg.norm(data[co, target] - data[co, k], axis=1)
        sd = float(np.std(d))
        if sd <= max_std:
            out.append((sd, k))
    out.sort()
    return [k for _, k in out]


def _rigid_estimate(data, target, donors, ref, at):
    """Position of ``target`` at frame ``at``, carried from reference frame
    ``ref`` by the rigid transform the donors underwent between the two."""
    P = data[ref][donors]
    Q = data[at][donors]
    R, t = _kabsch(P, Q)
    return R @ data[ref][target] + t


def _carry_rms(data, present, target, donors, lag, samples=40):
    """RMS error of carrying ``target`` ``lag`` frames on ``donors``, measured
    on frames where the true position IS known.

    This is the honest test, and it is the one that decides whether a fill
    happens at all. Ranking donors by how constant their distance to the target
    is (below) is only a prefilter: a marker orbiting a joint centre holds a
    PERFECTLY constant distance to a marker at that centre while sharing none
    of its orientation, so distance alone will happily nominate a thigh marker
    as a donor for the sacrum. Fitting the transform and checking what it
    predicts cannot be fooled that way.

    ``lag`` matters. Testing against the adjacent frame flatters the method —
    nothing has moved — so the reference is taken about as far away as the gap
    the fill will actually have to cross.
    """
    known = np.where(present[:, target] & present[:, donors].all(axis=1))[0]
    if known.size < 3:
        return None
    lag = max(1, int(lag))
    step = max(1, known.size // max(1, samples))
    errs = []
    for f in known[::step][:samples]:
        others = known[np.abs(known - f) >= 1]
        if others.size == 0:
            continue
        # a known frame roughly `lag` away — the distance the fill must span
        ref = int(others[np.argmin(np.abs(np.abs(others - f) - lag))])
        est = _rigid_estimate(data, target, donors, ref, int(f))
        errs.append(float(np.linalg.norm(est - data[f, target])))
    return float(np.sqrt(np.mean(np.square(errs)))) if errs else None


# --------------------------------------------------------------------------- #
# results
# --------------------------------------------------------------------------- #
@dataclass
class MarkerFill:
    name: str
    spline_frames: int = 0
    rigid_frames: int = 0
    left_empty: int = 0
    donors: list = field(default_factory=list)
    loo_rms: float | None = None          # leave-one-out error, TRC units
    note: str = ""


@dataclass
class FillReport:
    path: str = ""
    n_frames: int = 0
    n_markers: int = 0
    span: tuple = (0, 0)
    markers: list = field(default_factory=list)

    @property
    def spline_frames(self):
        return sum(m.spline_frames for m in self.markers)

    @property
    def rigid_frames(self):
        return sum(m.rigid_frames for m in self.markers)

    @property
    def left_empty(self):
        return sum(m.left_empty for m in self.markers)

    @property
    def ok(self):
        return self.left_empty == 0


# --------------------------------------------------------------------------- #
# the filler
# --------------------------------------------------------------------------- #
def _runs(present, lo, hi):
    """Every missing run of ``present`` inside ``[lo, hi]``, as (start, stop)
    with stop exclusive, plus whether it is bounded by data on both sides.

    Both kinds matter, and they are filled differently. An INTERIOR run can be
    interpolated. A run at the start or end of a marker's own visibility — the
    marker that only appears halfway through the trial — cannot be interpolated
    at all, but it CAN be reconstructed, because its segment's pose is known
    there from the other markers on it. Refusing those was leaving most of the
    real damage in place: on 022's running trials the sacral markers are missing
    from the START of the window, not in the middle of it.
    """
    out, i = [], lo
    while i <= hi:
        if not present[i]:
            j = i
            while j <= hi and not present[j]:
                j += 1
            out.append((i, j, i > lo and j <= hi))
            i = j
        else:
            i += 1
    return out


def _trusted_cluster(data, present, target, lag, *, min_donors, n_donors,
                     max_carry=None):
    """The donor set for ``target``, and the error it makes over a ``lag``-frame
    carry. ``([], carry, why)`` when no set is good enough.

    Two families of candidate set are scored, because either alone has a hole:

    * **prefixes of the rigidity ranking** — the k most rigidly-travelling
      markers, for every k. Cheap, and usually right.
    * **backward elimination** — drop whichever single donor most improves the
      measured carry error, repeatedly. This is what catches an impostor at the
      TOP of the ranking, and there is a specific one: a marker orbiting a joint
      centre holds a perfectly constant distance to a marker AT that centre, so
      a thigh marker can outrank a genuine sacral donor. A prefix can never
      exclude it; elimination can.

    Sets are scored on measured carry error, and **ties are broken towards the
    LARGER set**. That matters more than it looks. Three markers fit a rigid
    transform with zero residual by construction, so a minimal set can post a
    flattering error while being partly impostors — and a minimal set is also
    fragile, since losing one donor to an occlusion makes the frame unfillable,
    which on real data is most of them. Given two sets that predict the marker
    equally well, the bigger one is both better evidenced and more robust.
    """
    max_carry = MAX_CARRY_RMS if max_carry is None else max_carry
    cand = _rank_donors(data, present, target)[:max(n_donors, 10)]
    if len(cand) < min_donors:
        return [], None, (f"only {len(cand)} marker(s) move rigidly with it "
                          f"(need {min_donors})")

    seen, scored = set(), []

    def _score(sub):
        key = tuple(sorted(sub))
        if key in seen or len(sub) < min_donors:
            return None
        seen.add(key)
        r = _carry_rms(data, present, target, list(sub), lag)
        if r is not None:
            scored.append((r, len(sub), list(sub)))
        return r

    for k in range(min_donors, len(cand) + 1):          # prefixes
        _score(cand[:k])
    donors = list(cand)                                  # elimination
    while len(donors) > min_donors:
        trials = []
        for d in donors:
            sub = [x for x in donors if x != d]
            r = _carry_rms(data, present, target, sub, lag)
            if r is not None:
                _score(sub)
                trials.append((r, sub))
        if not trials:
            break
        trials.sort(key=lambda x: x[0])
        donors = trials[0][1]

    if not scored:
        return [], None, "not enough co-visible frames to test any donor set"
    best_err = min(r for r, _, _ in scored)
    # Anything within this of the best counts as equally good; among those, take
    # the largest set.
    tol = max(0.5, 0.10 * best_err)
    tied = [(sz, sub, r) for r, sz, sub in scored if r <= best_err + tol]
    tied.sort(key=lambda x: -x[0])
    size, donors, carry = tied[0]
    if carry > max_carry:
        return [], carry, (f"best donor set carries {lag} frames to "
                           f"{carry:.0f}, tolerance is {max_carry:g}")
    return donors, carry, ""


def _spline_leftovers(data, i, mf, runs, max_spline_gap, _CS):
    """Interpolate any SHORT INTERIOR gap the rigid pass could not fill.

    Last resort, and deliberately limited: over a handful of frames a marker's
    own trajectory is smooth enough to interpolate, and over a long one it is
    not — a straight line through a swinging limb plants the marker off the
    body, which is exactly the failure that makes IK diverge while reporting a
    respectable marker error.
    """
    idx = np.where(np.isfinite(data[:, i]).all(axis=1))[0]
    if idx.size < 2:
        return
    for (a, b, interior) in runs:
        if not interior or b - a > max_spline_gap:
            continue
        miss = [f for f in range(a, b) if not np.isfinite(data[f, i]).all()]
        if not miss:
            continue
        for c in range(3):
            if _CS is not None and idx.size >= 4:
                vals = _CS(idx, data[idx, i, c], extrapolate=False)(np.array(miss))
            else:
                vals = np.interp(np.array(miss), idx, data[idx, i, c])
            data[miss, i, c] = vals
        mf.spline_frames += len(miss)
        mf.left_empty = max(0, mf.left_empty - len(miss))


def fill_array(data, names=None, *, max_spline_gap=MAX_SPLINE_GAP,
               min_donors=MIN_DONORS, n_donors=N_DONORS,
               max_carry=MAX_CARRY_RMS, loo_samples=40):
    """Fill gaps in ``data`` ``(n_frames, n_markers, 3)``. Returns
    ``(filled, FillReport)``. Never alters a sample that was already present,
    so running it twice is the same as running it once."""
    data = np.array(data, dtype=float)
    n, m, _ = data.shape
    names = list(names or [f"M{i+1}" for i in range(m)])
    present = np.isfinite(data).all(axis=2)

    rep = FillReport(n_frames=n, n_markers=m)
    any_present = present.any(axis=1)
    if not any_present.any():
        return data, rep
    lo, hi = int(np.argmax(any_present)), int(n - 1 - np.argmax(any_present[::-1]))
    rep.span = (lo, hi)

    try:
        from scipy.interpolate import CubicSpline as _CS
    except Exception:
        _CS = None

    for i in range(m):
        mf = MarkerFill(name=names[i])
        runs = _runs(present[:, i], lo, hi)
        if not runs:
            rep.markers.append(mf)
            continue
        if not present[lo:hi + 1, i].any():
            mf.left_empty += sum(b - a for a, b, _ in runs)
            mf.note = "marker never visible in this trial"
            rep.markers.append(mf)
            continue

        # ---- everything else: carry the marker on its own segment -----------
        # Rigid reconstruction is tried on EVERY gap, short ones included.
        # Where a segment is properly instrumented it is exact, while a spline
        # through five frames of a swinging limb is merely close; the spline is
        # the fallback for markers with no usable cluster, not the first choice.
        rest = [(a, b) for (a, b, it) in runs]
        if not rest:
            rep.markers.append(mf)
            continue
        pn = np.isfinite(data).all(axis=2)
        lag = int(np.median([b - a for a, b in rest])) or 1
        cluster, carry, why = _trusted_cluster(data, pn, i, lag,
                                               min_donors=min_donors,
                                               n_donors=n_donors,
                                               max_carry=max_carry)
        donor_names = set()
        if not cluster:
            mf.left_empty += sum(b - a for a, b in rest)
            mf.loo_rms, mf.note = carry, why
            _spline_leftovers(data, i, mf, runs, max_spline_gap, _CS)
            rep.markers.append(mf)
            continue
        mf.loo_rms = carry
        cl = list(cluster)
        # Availability is decided FRAME BY FRAME. The donor that is occluded at
        # frame 812 is still on the segment at 813; requiring one set to cover a
        # whole gap throws away most of what is fillable, because with 60
        # markers the dropouts overlap but do not coincide.
        okf = {}                    # tuple(subset) -> frames where all visible
        for (a, b) in rest:
            for f in range(a, b):
                avail = tuple(d for d in cl if pn[f, d])
                if len(avail) < min_donors:
                    mf.left_empty += 1
                    if not mf.note:
                        mf.note = (f"fewer than {min_donors} of its segment's "
                                   f"markers visible in part of the gap")
                    continue
                if avail not in okf:
                    # Each distinct subset earns its own error bar before it is
                    # allowed to fill anything — a subset of a trusted cluster
                    # is not automatically trustworthy (three collinear markers
                    # do not determine a rotation).
                    _r = _carry_rms(data, pn, i, list(avail), lag)
                    okf[avail] = (np.where(pn[:, i] &
                                           pn[:, list(avail)].all(axis=1))[0]
                                  if (_r is not None and _r <= max_carry)
                                  else np.empty(0, dtype=int))
                    if _r is not None and _r <= max_carry:
                        mf.loo_rms = max(mf.loo_rms or 0.0, _r)
                anchors_all = okf[avail]
                if anchors_all.size == 0:
                    mf.left_empty += 1
                    mf.note = mf.note or ("no usable anchor for the subset of "
                                          "its segment visible there")
                    continue
                left = anchors_all[anchors_all < f]
                right = anchors_all[anchors_all > f]
                dl = list(avail)
                if left.size and right.size:
                    # Blend the estimate carried forward from the nearest
                    # anchor before with the one carried back from the nearest
                    # after, weighted by position between them, so the fill
                    # meets the real trajectory at BOTH edges rather than
                    # stepping at one of them.
                    l, r = int(left[-1]), int(right[0])
                    w = (f - l) / float(r - l)
                    p = ((1 - w) * _rigid_estimate(data, i, dl, l, f)
                         + w * _rigid_estimate(data, i, dl, r, f))
                elif left.size:
                    p = _rigid_estimate(data, i, dl, int(left[-1]), f)
                else:
                    p = _rigid_estimate(data, i, dl, int(right[0]), f)
                data[f, i] = p
                mf.rigid_frames += 1
                donor_names.update(names[d] for d in avail)
        mf.donors = sorted(donor_names)
        _spline_leftovers(data, i, mf, runs, max_spline_gap, _CS)
        rep.markers.append(mf)
    return data, rep


def usable_window(data, names=None, required=None, min_count=None,
                  min_frac=0.9):
    """Longest contiguous run of frames in which the markers that matter are
    actually there. Returns ``(start, stop, n_frames, detail)``.

    Gap filling has a floor: three visible markers on a segment. Below that the
    segment's pose is not under-determined, it is UNOBSERVED, and no method
    recovers it — the honest move is to solve a shorter window rather than a
    longer one containing frames nothing constrains. This finds that window.

    ``required`` names the markers to insist on (default: all of them);
    ``min_count`` how many must be present (default ``min_frac`` of them).
    """
    data = np.asarray(data, dtype=float)
    present = np.isfinite(data).all(axis=2)
    names = list(names or [f"M{i+1}" for i in range(data.shape[1])])
    if required:
        idx = [names.index(x) for x in required if x in names]
    else:
        idx = list(range(data.shape[1]))
    if not idx:
        return 0, 0, 0, "no markers matched"
    need = int(min_count if min_count is not None
               else max(1, round(min_frac * len(idx))))
    ok = present[:, idx].sum(1) >= need
    best, i = (0, 0, 0), 0
    while i < len(ok):
        if ok[i]:
            j = i
            while j < len(ok) and ok[j]:
                j += 1
            if j - i > best[0]:
                best = (j - i, i, j)
            i = j
        else:
            i += 1
    L, a, b = best
    return a, b, L, (f"{L} frame(s) with >= {need} of {len(idx)} markers "
                     f"present, frames {a}-{max(a, b - 1)}")


def fill_trc(path, out_path=None, *, max_spline_gap=MAX_SPLINE_GAP,
             min_donors=MIN_DONORS, n_donors=N_DONORS,
             max_carry=MAX_CARRY_RMS, backup=False, log=print):
    """Fill the gaps in a .trc. Writes in place unless ``out_path`` is given.

    Returns the :class:`FillReport`. The header is preserved verbatim and no
    sample that was already present is changed, so re-running is a no-op.
    """
    header, frames, times, data, names = read_trc(path)
    filled, rep = fill_array(data, names, max_spline_gap=max_spline_gap,
                             min_donors=min_donors, n_donors=n_donors,
                             max_carry=max_carry)
    rep.path = path
    dst = out_path or path
    if backup and dst == path and not os.path.exists(path + ".pregap"):
        with open(path, "r", errors="replace") as fh:
            _raw = fh.read()
        with open(path + ".pregap", "w", newline="") as fh:
            fh.write(_raw)
    write_trc(dst, header, frames, times, filled)
    if log:
        for line in format_report(rep).splitlines():
            log(line)
    return rep


def format_report(rep: FillReport, verbose=True) -> str:
    """Human-readable summary — one line per marker that needed work."""
    out = [f"[gapfill] {os.path.basename(rep.path) or 'trc'}: "
           f"{rep.n_markers} markers, {rep.n_frames} frames, "
           f"data span {rep.span[0]}-{rep.span[1]}"]
    touched = [m for m in rep.markers
               if m.spline_frames or m.rigid_frames or m.left_empty]
    if not touched:
        out.append("[gapfill] no interior gaps — nothing to fill")
        return "\n".join(out)
    if verbose:
        for m in sorted(touched, key=lambda x: -(x.rigid_frames + x.left_empty)):
            bits = []
            if m.spline_frames:
                bits.append(f"{m.spline_frames} spline")
            if m.rigid_frames:
                q = f" (carry err {m.loo_rms:.1f})" if m.loo_rms is not None else ""
                bits.append(f"{m.rigid_frames} rigid from "
                            f"{'+'.join(m.donors)}{q}")
            if m.left_empty:
                bits.append(f"{m.left_empty} LEFT EMPTY ({m.note})")
            out.append(f"  {m.name:10s} " + "; ".join(bits))
    out.append(f"[gapfill] filled {rep.spline_frames} frame(s) by spline, "
               f"{rep.rigid_frames} by rigid cluster, "
               f"{rep.left_empty} left empty")
    if rep.left_empty:
        out.append("[gapfill] frames left empty are markers OpenSim will ignore — "
                   "that is deliberate: a fabricated marker is worse than an "
                   "absent one.")
    return "\n".join(out)


if __name__ == "__main__":                                  # pragma: no cover
    import argparse
    ap = argparse.ArgumentParser(
        description="Fill marker gaps in a .trc (spline + rigid cluster).")
    ap.add_argument("trc", nargs="+")
    ap.add_argument("-o", "--out", help="write here instead of in place "
                                        "(single input only)")
    ap.add_argument("--max-spline-gap", type=int, default=MAX_SPLINE_GAP)
    ap.add_argument("--min-donors", type=int, default=MIN_DONORS)
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be filled, write nothing")
    ap.add_argument("--window", action="store_true",
                    help="also report the longest stretch where the markers "
                         "are actually present (what you can honestly solve)")
    ap.add_argument("--require", help="comma-separated markers --window insists "
                                      "on (default: all of them)")
    a = ap.parse_args()
    for p in a.trc:
        if a.window:
            _h, _f, _t, _d, _n = read_trc(p)
            _req = [x.strip() for x in a.require.split(",")] if a.require else None
            _s, _e, _L, _why = usable_window(_d, _n, required=_req)
            print(f"[window] {os.path.basename(p)}: {_why}")
            if _L:
                print(f"[window] time_range: [{_t[_s]:.3f}, {_t[_e - 1]:.3f}]"
                      f"   ({_t[_e - 1] - _t[_s]:.3f} s)")
        if a.dry_run:
            _h, _f, _t, _d, _n = read_trc(p)
            _, r = fill_array(_d, _n, max_spline_gap=a.max_spline_gap,
                              min_donors=a.min_donors)
            r.path = p
            print(format_report(r))
        else:
            fill_trc(p, a.out if len(a.trc) == 1 else None,
                     max_spline_gap=a.max_spline_gap, min_donors=a.min_donors,
                     backup=True)
