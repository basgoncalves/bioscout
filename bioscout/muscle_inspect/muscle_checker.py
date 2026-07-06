"""Motion-driven muscle-path checker -- Python port of the MATLAB `muscleChecker`.

Inputs: an OpenSim model (.osim) and one or more kinematics files (.mot).
Mirrors the MATLAB pipeline `checkAndFixMusclePaths` / `calcMuscleLengthsForMotion`:

  Phase 1  static same-body geometry check  (project points out of cylinders)
  Phase 1b temp model with the Phase-1 fixes
  Phase 2  compute muscle LENGTHS across the motion frames, detect discontinuities
  Phase 3  cross-body projection (worst penetration over motion frames)  ->
           radius reduction (binary search over the full motion)  ->  motion rejection
  Phase 4  summary
  outer    iteration loop; writes <model>_modWO.osim and <model>_modWO_log.txt

Defaults, thresholds and behaviour match the MATLAB version. Requires `opensim`.
"""
from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .logutil import LOG, timed
from .geometry import euler_xyz_to_rotation_matrix, project_point_outside_cylinder
from .discontinuity import detect_discontinuities
from .wrap_fixer import (
    PointProjection, find_wrap_object,
    check_points_inside_cylinders, apply_projections,
)

try:
    import opensim
except Exception:  # pragma: no cover
    opensim = None


# --- MATLAB defaults --------------------------------------------------------
DEFAULT_COORDINATES = [
    "hip_flexion_l", "hip_rotation_l", "hip_adduction_l",
    "hip_flexion_r", "hip_rotation_r", "hip_adduction_r",
    "knee_angle_l", "knee_angle_r", "ankle_angle_l", "ankle_angle_r",
    "subtalar_angle_l", "subtalar_angle_r",
]
DEFAULT_MUSCLE_FILTER = [
    "addbrev", "addlong", "addmagD", "addmagI", "addmagM", "addmagP",
    "bfsh", "gaslat", "gasmed", "glmax1", "glmax2", "glmax3",
    "grac", "iliacus", "psoas", "recfem", "semimem", "semiten",
    "vasint", "vaslat", "vasmed",
]

# thresholds (match MATLAB)
NEIGHBORHOOD = 10          # frames around each discontinuity to scan (Phase 3)
XB_MARGIN_BASE = 0.002     # cross-body margin base (m)
XB_MARGIN_FRAC = 0.5       # + fraction of worst penetration
MAX_DISPLACEMENT_MM = 5.0
MIN_RADIUS_FLOOR = 0.005
MAX_RADIUS_REDUCTION = 0.010
RADIUS_TOL = 0.0005
RADIUS_MAX_ITER = 10


def _require_opensim():
    if opensim is None:
        raise ImportError("muscle_checker requires the 'opensim' Python package.")


# ---------------------------------------------------------------------------
# .mot reading
# ---------------------------------------------------------------------------
def read_mot(path: str):
    """Return (time, {column: array}, in_degrees, column_names)."""
    lines = open(path).read().splitlines()
    hi = next(i for i, l in enumerate(lines) if l.strip().lower() == "endheader")
    header = lines[:hi]
    in_degrees = any("indegrees" in l.lower() and "yes" in l.lower() for l in header)
    cols = lines[hi + 1].split()
    rows = [ln.split() for ln in lines[hi + 2:] if ln.strip()]
    data = np.array([[float(x) for x in r] for r in rows], float)
    d = {cols[j]: data[:, j] for j in range(len(cols))}
    return data[:, 0], d, in_degrees, cols


def _butter_lowpass(sig, fs, fc):
    from scipy.signal import butter, filtfilt
    nyq = 0.5 * fs
    if fc <= 0 or fc >= nyq:
        return sig
    b, a = butter(4, fc / nyq)
    return filtfilt(b, a, sig)


# ---------------------------------------------------------------------------
# Motion model: pose the model along a .mot, evaluate muscle lengths
# ---------------------------------------------------------------------------
class MotionModel:
    def __init__(self, model_path: str, mot_path: str,
                 coordinate_names: Optional[list] = None, filter_freq: float = 0.0):
        _require_opensim()
        self.model = opensim.Model(model_path)
        self.state = self.model.initSystem()
        self.coord_set = self.model.getCoordinateSet()
        self.muscles = self.model.getMuscles()

        self.time, mot, self.in_degrees, _ = read_mot(mot_path)
        present = {self.coord_set.get(i).getName() for i in range(self.coord_set.getSize())}
        wanted = coordinate_names if coordinate_names else list(present)

        # drive every coord that is in the mot AND the model AND not dependent/locked;
        # coordinate_names (if given) restricts which are actively set.
        self.drive = []
        self._is_rot = {}
        for name in mot:
            if name == "time" or name not in present:
                continue
            c = self.coord_set.get(name)
            try:
                if c.isConstrained(self.state):
                    continue
            except Exception:
                pass
            if coordinate_names and name not in wanted:
                # still drive pelvis/lumbar/etc. so the pose is physical, but the
                # MATLAB "coordinateNames" set is always included; keep all present.
                pass
            self.drive.append(name)
            try:
                self._is_rot[name] = (c.getMotionType() != opensim.Coordinate.Translational)
            except Exception:
                self._is_rot[name] = True

        # optional low-pass filter of the driven columns
        self.data = {}
        fs = 1.0 / np.median(np.diff(self.time)) if len(self.time) > 1 else 0.0
        for name in self.drive:
            col = mot[name].astype(float)
            if filter_freq and filter_freq > 0 and fs > 0:
                try:
                    col = _butter_lowpass(col, fs, filter_freq)
                except Exception:
                    pass
            self.data[name] = col

    @property
    def n_frames(self):
        return len(self.time)

    def pose(self, frame: int):
        for name in self.drive:
            c = self.coord_set.get(name)
            if c.getLocked(self.state):
                continue
            val = self.data[name][frame]
            if self.in_degrees and self._is_rot.get(name, True):
                val = np.deg2rad(val)
            c.setValue(self.state, float(val), False)
        self.model.assemble(self.state)
        self.model.realizePosition(self.state)

    def lengths(self, muscle_names: list, frames=None) -> np.ndarray:
        frames = range(self.n_frames) if frames is None else frames
        frames = list(frames)
        handles = [self.muscles.get(m) for m in muscle_names]
        out = np.full((len(frames), len(muscle_names)), np.nan)
        for k, fi in enumerate(frames):
            self.pose(fi)
            for j, h in enumerate(handles):
                try:
                    out[k, j] = h.getLength(self.state)
                except Exception:
                    pass
        return out


# ---------------------------------------------------------------------------
# muscle-name helpers (side-aware, MATLAB parity)
# ---------------------------------------------------------------------------
def get_muscle_subset(model, muscle_filter) -> list:
    names = []
    ms = model.getMuscles()
    for i in range(ms.getSize()):
        n = ms.get(i).getName()
        if any(f in n for f in muscle_filter):
            names.append(n)
    return names


def derive_side(motion_path: str) -> str:
    for part in re.split(r"[\\/]", motion_path):
        m = re.search(r"_([LR])\d*$", os.path.splitext(part)[0])
        if m:
            return "_l" if m.group(1).upper() == "L" else "_r"
    return ""


def filter_by_side(names: list, side: str) -> list:
    if not side:
        return names
    opp = "_r" if side == "_l" else "_l"
    return [n for n in names if not n.endswith(opp)]


# ---------------------------------------------------------------------------
# Phase 3: cross-body projection over motion frames
# ---------------------------------------------------------------------------
def _vec3(v):
    return np.array([v.get(0), v.get(1), v.get(2)], float)


def _cross_body_combos(model, muscle_names):
    combos = []
    ms = model.getMuscles()
    for mname in muscle_names:
        gp = ms.get(mname).getGeometryPath()
        ws, ps = gp.getWrapSet(), gp.getPathPointSet()
        for w in range(ws.getSize()):
            won = ws.get(w).getWrapObjectName()
            wo, wbody = find_wrap_object(model, won)
            if wo is None:
                continue
            cyl = opensim.WrapCylinder.safeDownCast(wo)
            if cyl is None:
                continue
            rxyz = cyl.get_xyz_body_rotation()
            info = dict(muscle=mname, wrap=won, wbody_name=wbody.getName(), wframe=wbody,
                        radius=cyl.get_radius(), length=cyl.get_length(),
                        R=euler_xyz_to_rotation_matrix(rxyz.get(0), rxyz.get(1), rxyz.get(2)),
                        t=_vec3(cyl.get_translation()))
            for p in range(ps.getSize()):
                app = ps.get(p)
                if app.getBody().getName() == info["wbody_name"]:
                    continue
                pp = opensim.PathPoint.safeDownCast(app)
                if pp is None:
                    continue
                c = dict(info, pp=pp, ppname=pp.getName(), ppframe=app.getBody(),
                         worst=0.0, worst_frame=-1)
                combos.append(c)
    return combos


def propose_cross_body(mm, combos, scan_frames, verbose=True):
    """Scan the given motion frames, track worst penetration, propose projections."""
    for fi in scan_frames:
        mm.pose(fi)
        for c in combos:
            try:
                ptw = c["ppframe"].findStationLocationInAnotherFrame(
                    mm.state, c["pp"].get_location(), c["wframe"])
            except Exception:
                continue
            p = np.array([ptw.get(0), ptw.get(1), ptw.get(2)])
            pc = c["R"].T @ (p - c["t"])
            if abs(pc[2]) > c["length"] / 2:
                continue
            pen = c["radius"] - float(np.hypot(pc[0], pc[1]))
            if pen > c["worst"]:
                c["worst"], c["worst_frame"] = pen, fi

    best = {}
    for c in combos:
        if c["worst"] <= 0 or c["worst_frame"] < 0:
            continue
        mm.pose(c["worst_frame"])
        loc = c["pp"].get_location()
        ptw = _vec3(c["ppframe"].findStationLocationInAnotherFrame(mm.state, loc, c["wframe"]))
        margin = XB_MARGIN_BASE + XB_MARGIN_FRAC * c["worst"]
        _, pt_new, _, r_point = project_point_outside_cylinder(ptw, c["R"], c["t"], c["radius"], margin)
        new_pp = _vec3(c["wframe"].findStationLocationInAnotherFrame(
            mm.state, opensim.Vec3(*pt_new), c["ppframe"]))
        orig = _vec3(loc)
        disp = float(np.linalg.norm(new_pp - orig) * 1000)
        if disp >= MAX_DISPLACEMENT_MM:
            continue
        proj = PointProjection(
            muscle_name=c["muscle"], path_point_name=c["ppname"], wrap_object_name=c["wrap"],
            body_name=c["ppframe"].getName(), original_location=tuple(orig),
            projected_location=tuple(new_pp), displacement_mm=disp, radial_distance=r_point,
            cylinder_radius=c["radius"], penetration_mm=c["worst"] * 1000,
            method=f"cross-body (worst {c['worst']*1000:.2f} mm at frame {c['worst_frame']})")
        if c["muscle"] not in best or disp < best[c["muscle"]].displacement_mm:
            best[c["muscle"]] = proj
            if verbose:
                LOG.info("  cross-body: %s.%s -> %.2f mm (pen %.2f mm)",
                         c["muscle"], c["ppname"], disp, c["worst"] * 1000)
    return list(best.values())


# ---------------------------------------------------------------------------
# Phase 3 priority 2: radius reduction over the full motion
# ---------------------------------------------------------------------------
def estimate_min_radius(model_path, mot_path, muscle, wrap_name, r0,
                        coordinate_names, filter_freq, dk, verbose=True):
    lo = max(MIN_RADIUS_FLOOR, r0 - MAX_RADIUS_REDUCTION)
    hi = r0
    best = None
    for _ in range(RADIUS_MAX_ITER):
        mid = 0.5 * (lo + hi)
        fd, tmpf = tempfile.mkstemp(suffix=".osim")
        os.close(fd)
        try:
            m = opensim.Model(model_path)
            m.initSystem()
            wo, _ = find_wrap_object(m, wrap_name)
            opensim.WrapCylinder.safeDownCast(wo).set_radius(mid)
            m.finalizeConnections()
            m.printToXML(tmpf)
            mm = MotionModel(tmpf, mot_path, coordinate_names, filter_freq)
            L = mm.lengths([muscle])[:, 0]
            disc = bool(detect_discontinuities(L, **dk))
            del mm
        finally:
            try:
                os.remove(tmpf)
            except OSError:
                pass
        if disc:
            hi = mid
        else:
            best = mid
            lo = mid
        if hi - lo < RADIUS_TOL:
            break
    return max(MIN_RADIUS_FLOOR, best) if best is not None else r0


def apply_radius_reductions(model, reductions, verbose=True):
    n = 0
    for r in reductions:
        wo, _ = find_wrap_object(model, r["wrap"])
        wc = opensim.WrapCylinder.safeDownCast(wo) if wo is not None else None
        if wc is not None:
            wc.set_radius(r["new_radius"])
            n += 1
    return n


# ---------------------------------------------------------------------------
# corrections container
# ---------------------------------------------------------------------------
@dataclass
class Corrections:
    point_projections: list = field(default_factory=list)
    radius_reductions: list = field(default_factory=list)
    rejected_motions: list = field(default_factory=list)
    summary: str = ""


def apply_corrections(model_path, output_path, corr: Corrections, verbose=True):
    _require_opensim()
    model = opensim.Model(model_path)
    model.initSystem()
    apply_projections(model, corr.point_projections, verbose=verbose)
    apply_radius_reductions(model, corr.radius_reductions, verbose=verbose)
    model.finalizeConnections()
    model.printToXML(output_path)


# ---------------------------------------------------------------------------
# calc_muscle_lengths_for_motion  (Phases 1-4)
# ---------------------------------------------------------------------------
def calc_muscle_lengths_for_motion(model_path, motion_files, coordinate_names=None,
                                   muscle_filter=None, filter_freq=0.0, dk=None,
                                   verbose=True):
    _require_opensim()
    coordinate_names = coordinate_names or DEFAULT_COORDINATES
    muscle_filter = muscle_filter or DEFAULT_MUSCLE_FILTER
    dk = dk or {}

    model = opensim.Model(model_path)
    model.initSystem()
    muscle_names = get_muscle_subset(model, muscle_filter)
    corr = Corrections()

    # -- Phase 1: static same-body --
    state = model.initSystem()
    LOG.info("PHASE 1  static geometry check (%d muscles)", len(muscle_names))
    static = check_points_inside_cylinders(model, state, muscle_names,
                                           max_penetration_mm=5.0, verbose=verbose)
    corr.point_projections = [p for p in static if not p.method.startswith("skipped")]

    # -- Phase 1b: temp model with the static fixes --
    if corr.point_projections:
        fd, temp_model = tempfile.mkstemp(suffix=".osim")
        os.close(fd)
        apply_corrections(model_path, temp_model, Corrections(point_projections=corr.point_projections),
                          verbose=False)
        model_for_analysis = temp_model
    else:
        temp_model = None
        model_for_analysis = model_path

    # -- Phase 2: lengths over motion, detect discontinuities --
    all_disc = []  # (motion_idx, frame, muscle)
    length_data = []  # per motion: (time, muscle_names_side, N x M)
    for mi, mot in enumerate(motion_files):
        side = derive_side(mot)
        names_side = filter_by_side(muscle_names, side)
        LOG.info("PHASE 2  motion %d/%d: %s (%d muscles)", mi + 1, len(motion_files),
                 os.path.basename(mot), len(names_side))
        mm = MotionModel(model_for_analysis, mot, coordinate_names, filter_freq)
        with timed(f"muscle lengths ({mm.n_frames} frames)"):
            L = mm.lengths(names_side)
        length_data.append((mm.time, names_side, L))
        for j, mname in enumerate(names_side):
            for f in detect_discontinuities(L[:, j], **dk):
                all_disc.append((mi, f, mname))
        del mm
    if verbose:
        LOG.info("PHASE 2  %d discontinuities found", len(all_disc))

    # -- Phase 3: cross-body projection, then radius reduction, then rejection --
    if all_disc:
        affected = sorted({d[2] for d in all_disc})
        model2 = opensim.Model(model_for_analysis)
        model2.initSystem()
        combos = _cross_body_combos(model2, affected)
        del model2

        # scan frames = union of +/-neighborhood around each discontinuity, per motion
        frames_by_motion = {}
        for (mi, f, _m) in all_disc:
            s = frames_by_motion.setdefault(mi, set())
            s.update(range(max(0, f - NEIGHBORHOOD), f + NEIGHBORHOOD + 1))

        projections = []
        if combos:
            for mi, frames in frames_by_motion.items():
                mm = MotionModel(model_for_analysis, motion_files[mi], coordinate_names, filter_freq)
                frames = sorted(fr for fr in frames if 0 <= fr < mm.n_frames)
                LOG.info("PHASE 3  cross-body scan: motion %d, %d frames, %d combos",
                         mi + 1, len(frames), len(combos))
                projections += propose_cross_body(mm, combos, frames, verbose=verbose)
                del mm

        fixed = {p.muscle_name for p in projections}
        corr.point_projections += projections

        # radius reduction for muscles still unresolved
        for mname in affected:
            if mname in fixed:
                continue
            mot_idxs = sorted({d[0] for d in all_disc if d[2] == mname})
            mpath = motion_files[mot_idxs[0]]
            mtmp = opensim.Model(model_for_analysis)
            mtmp.initSystem()
            wnames = []
            gp = mtmp.getMuscles().get(mname).getGeometryPath()
            ws = gp.getWrapSet()
            for w in range(ws.getSize()):
                won = ws.get(w).getWrapObjectName()
                wo, _ = find_wrap_object(mtmp, won)
                if wo is not None and opensim.WrapCylinder.safeDownCast(wo) is not None:
                    wnames.append(won)
            del mtmp
            done = False
            for won in wnames:
                probe = opensim.Model(model_for_analysis)
                probe.initSystem()
                wo, _ = find_wrap_object(probe, won)
                r0 = opensim.WrapCylinder.safeDownCast(wo).get_radius()
                del probe
                with timed(f"radius search {mname}/{won}"):
                    rmin = estimate_min_radius(model_for_analysis, mpath, mname, won, r0,
                                               coordinate_names, filter_freq, dk, verbose)
                if rmin < r0:
                    corr.radius_reductions.append(dict(muscle=mname, wrap=won,
                                                       old_radius=r0, new_radius=rmin,
                                                       reduction_mm=(r0 - rmin) * 1000))
                    LOG.info("  radius: %s/%s %.4f -> %.4f m", mname, won, r0, rmin)
                    done = True
                    break
            if not done:
                for mo in mot_idxs:
                    if motion_files[mo] not in corr.rejected_motions:
                        corr.rejected_motions.append(motion_files[mo])
                LOG.info("  reject: %s could not be resolved", mname)

    if temp_model:
        try:
            os.remove(temp_model)
        except OSError:
            pass

    corr.summary = (f"{len(corr.point_projections)} projections, "
                    f"{len(corr.radius_reductions)} radius reductions, "
                    f"{len(corr.rejected_motions)} motions flagged for rejection")
    LOG.info("PHASE 4  %s", corr.summary)
    return corr, length_data


# ---------------------------------------------------------------------------
# outer iteration loop
# ---------------------------------------------------------------------------
def check_and_fix_muscle_paths(model_file, motion_files, coordinate_names=None,
                               muscle_filter=None, filter_freq=0.0, max_iterations=3,
                               min_jump_mm=1.0, out_dir=None, verbose=True):
    """Returns (success, corrected_model_path, log_path)."""
    _require_opensim()
    if isinstance(motion_files, str):
        motion_files = [motion_files]
    dk = dict(min_jump_m=min_jump_mm / 1000.0)
    model_dir = out_dir or os.path.dirname(model_file)
    os.makedirs(model_dir, exist_ok=True)
    name = os.path.splitext(os.path.basename(model_file))[0]
    corrected = os.path.join(model_dir, f"{name}_modWO.osim")
    log_path = os.path.join(model_dir, f"{name}_modWO_log.txt")

    def log(msg):
        with open(log_path, "a") as f:
            f.write(msg + "\n")

    open(log_path, "w").close()
    log("Muscle Path Correction Log")
    log("==========================")
    log(f"Original model: {model_file}")
    log(f"Motions analyzed: {len(motion_files)}")
    for i, m in enumerate(motion_files):
        log(f"  [{i}] {m}")

    success = False
    current = model_file
    total = 0
    for it in range(1, max_iterations + 1):
        LOG.info("#" * 64)
        LOG.info("ITERATION %d/%d  model: %s", it, max_iterations, os.path.basename(current))
        LOG.info("#" * 64)
        log(f"\n=== ITERATION {it}/{max_iterations} ===\nInput model: {current}")

        corr, _ = calc_muscle_lengths_for_motion(
            current, motion_files, coordinate_names, muscle_filter, filter_freq, dk, verbose)
        n_proj = len(corr.point_projections)
        n_rad = len(corr.radius_reductions)
        total_corr = n_proj + n_rad
        log(f"Findings: {n_proj} projections, {n_rad} radius reductions, "
            f"{len(corr.rejected_motions)} rejections")

        if total_corr == 0:
            for rm in corr.rejected_motions:
                log(f"  REJECT: {rm}")
            log("No corrections needed." if total == 0
                else f"SUCCESS after {it} iteration(s), {total} total corrections.")
            success = True
            break

        LOG.info("Applying %d corrections (%d proj, %d radius)", total_corr, n_proj, n_rad)
        apply_corrections(current, corrected, corr, verbose=verbose)
        log(f"Applied {total_corr} corrections -> {corrected}")
        total += total_corr
        current = corrected

        n_phase1 = sum(1 for p in corr.point_projections if "geometry check" in p.method)
        if total_corr - n_phase1 == 0:
            log("All corrections verified by Phase 2. Done.")
            success = True
            break
        LOG.info("Re-checking: %d Phase 3 corrections need verification", total_corr - n_phase1)

    if not success:
        log(f"WARNING: max iterations ({max_iterations}) reached, {total} corrections applied.")
    if os.path.isfile(corrected):
        log(f"Final model: {corrected}")
    LOG.info("Corrected model: %s", corrected if os.path.isfile(corrected) else "(none)")
    LOG.info("Log: %s", log_path)
    return success, (corrected if os.path.isfile(corrected) else model_file), log_path


# ---------------------------------------------------------------------------
# convenience: compute lengths + plot before/after waveforms
# ---------------------------------------------------------------------------
def compute_lengths(model_path, mot_path, coordinate_names=None,
                    muscle_filter=None, filter_freq=0.0):
    """(time, muscle_names, N x M lengths) for the filtered muscles over the motion."""
    _require_opensim()
    muscle_filter = muscle_filter or DEFAULT_MUSCLE_FILTER
    mm = MotionModel(model_path, mot_path, coordinate_names, filter_freq)
    names = filter_by_side(get_muscle_subset(mm.model, muscle_filter), derive_side(mot_path))
    L = mm.lengths(names)
    return mm.time, names, L


def plot_length_waveforms(time, names, before_L, after_L, outdir, tag, dk=None):
    import math
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    dk = dk or {}
    os.makedirs(outdir, exist_ok=True)
    n = len(names)
    cols = int(math.ceil(math.sqrt(n)))
    rows = int(math.ceil(n / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(3.2 * cols, 2.4 * rows), squeeze=False)
    for i, m in enumerate(names):
        ax = axes[i // cols][i % cols]
        if before_L is not None:
            yb = before_L[:, i] * 1000.0
            ax.plot(time, yb, color="#bbbbbb", lw=1.4, label="before")
            for j in detect_discontinuities(before_L[:, i], **dk):
                ax.plot(time[j], yb[j], "o", mfc="none", mec="#d62728", ms=8)
        if after_L is not None:
            ya = after_L[:, i] * 1000.0
            ax.plot(time, ya, color="#1f77b4", lw=1.5, linestyle="--", dashes=(5, 3), label="after")
            for j in detect_discontinuities(after_L[:, i], **dk):
                ax.plot(time[j], ya[j], "rx", ms=7)
        ax.set_title(m, fontsize=8)
        ax.tick_params(labelsize=7)
        ax.grid(True, alpha=0.25)
    for i in range(n, rows * cols):
        axes[i // cols][i % cols].axis("off")
    h, l = axes[0][0].get_legend_handles_labels()
    if h:
        fig.legend(h, l, loc="upper right", fontsize=9)
    fig.suptitle(f"Muscle length vs time -- {tag}  (grey=before, blue dashed=after, red=discontinuity)",
                 fontsize=11)
    fig.supxlabel("time (s)")
    fig.supylabel("Muscle length (mm)")
    fig.tight_layout(rect=[0.01, 0.01, 1, 0.97])
    path = os.path.join(outdir, f"length_{tag}.png")
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path
