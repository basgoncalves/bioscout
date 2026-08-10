"""
mocap.py — trial-level movement classification from MOCAP data.

The rest of this package classifies FRAMES of 2-D pose landmarks from video
(``detector.detect_segments``). This module answers a different question, for
marker-based laboratory capture: **what task is this whole trial?** — from the
exported ``marker_experimental.trc`` and ``grf.mot`` that BioScout already
writes into ``<session>/2_experimental/<trial>/``.

Why it exists
-------------
Projects type their trials from the FILE NAME (``RunG3`` -> running,
``SquatNorm1`` -> squat). That is a naming convention, not a measurement: it
cannot catch a mislabelled capture, a trial where the participant did something
else, or a squat where one foot missed the plate. This module derives the task
from the signals so the two can be compared.

Tasks
-----
emg_only            no 3-D point data at all (MVIC / strength captures)
static              stationary, both feet loaded, no vertical excursion
squat               bilateral, vertical pelvis cycling, no travel
single_leg_squat    as squat but only ONE foot loaded
jump                flight phase with low travel speed + high landing impulse
running             high travel speed WITH a flight phase
walking             moderate travel speed, no flight phase
cut                 fast travel with a large lateral component
unknown             nothing matched with enough confidence

The thresholds live in :class:`MocapConfig` and are expressed in SI units
(m, s, body weights) so they transfer between labs, unlike the pixel/frame
thresholds the video path uses.
"""

from __future__ import annotations

import os
import math
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

import numpy as np


MOCAP_TASK_LABELS = (
    "emg_only",
    "static",
    "single_leg_stance",
    "squat_jump",
    "squat",
    "single_leg_squat",
    "jump",
    "running",
    "walking",
    "cut",
    "unknown",
)

# Marker names that identify the pelvis, per lab convention. The first set that
# is present wins, so a session labelled with either convention works.
_PELVIS_SETS = (
    ("LASI", "RASI", "LPSI", "RPSI"),
    ("LASI", "RASI", "USACR", "LSACR"),
    ("LASI", "RASI", "SACR"),
    ("LASI", "RASI"),
)


@dataclass
class MocapConfig:
    """Thresholds for :func:`classify_trial`, all in SI units.

    Defaults were set against FAIS running / squat / single-leg-squat / jump
    captures (200 Hz, 59 markers, 4 force plates) and are deliberately loose —
    the classifier is meant to catch gross mislabelling, not to adjudicate
    borderline technique.
    """
    # --- force plate ---
    # A plate counts as loaded above this fraction of body weight. 0.10 BW is
    # well clear of baseline drift and crosstalk while still catching the light
    # contact at the start of a squat descent.
    load_bw: float = 0.10
    # Total vertical GRF below this fraction of BW = airborne.
    flight_bw: float = 0.10
    # A flight phase must last at least this long to be real (not a dropout).
    min_flight_s: float = 0.05

    # --- travel ---
    # Median horizontal pelvis speed separating a stationary task from gait.
    static_speed: float = 0.20        # m/s
    walk_run_speed: float = 2.20      # m/s, above this it is running not walking
    # Lateral travel as a fraction of total travel, above which a fast trial is
    # a change-of-direction (cut) rather than straight-line running.
    # Measured on FAIS 021 (approach speeds 3.8-5.8 m/s):
    #     cut     RunA2 0.316, RunA3 0.209, RunG3 0.158
    #     running RunB1 0.017, Run_baselineA1 0.030
    # A clean 5x gap, so 0.10 sits between the populations rather than on the
    # edge of either. Physically: more than a tenth of the travel is sideways.
    cut_lateral_ratio: float = 0.10

    # Fraction of the TRAVELLED DISTANCE used to estimate the heading before
    # and after a turn. 0.30 leaves a 40% middle band for the turn itself.
    cut_heading_frac: float = 0.30
    # Below this turn angle the trial carried straight on. 20 deg matches the
    # tolerance a straight run shows from stride-to-stride drift.
    straight_angle_deg: float = 20.0
    # Trajectories shorter than this are too short for a meaningful heading.
    min_travel_for_angle: float = 1.0     # m

    # --- vertical excursion ---
    # Peak-to-peak vertical pelvis movement that marks a squat/jump cycle.
    squat_drop_m: float = 0.12
    static_drop_m: float = 0.05

    # Fraction of the trial on ONE foot above which a squat is single-leg.
    # 0.50 sits well clear of both observed cases (86% for a single-leg squat,
    # 0% for a bilateral one).
    single_support_frac: float = 0.50

    # --- segmentation ---
    # A foot is OFF the ground once its markers rise this far above their own
    # floor level. Measured on FAIS SLSback_post1: the lifted foot sits 18-34 cm
    # up, the stance foot within 0.4 cm of its floor — no ambiguity at 5 cm.
    foot_lift_m: float = 0.05
    # Shortest task worth reporting. Anything briefer is absorbed into its
    # neighbours as a transition rather than becoming its own row.
    min_task_s: float = 0.40

    # --- squat phases ---
    # A squat STARTS when the descent starts, not when it passes squat_drop_m.
    # The segment is grown out from the depth peak until the pelvis is back
    # within this band of standing height, so the eccentric phase is captured
    # from its first millimetre rather than from the threshold crossing.
    squat_onset_band_m: float = 0.02
    # |vertical velocity| below this counts as the bottom hold.
    hold_vel_ms: float = 0.05
    # Hold only applies in the deepest part of the descent.
    hold_depth_frac: float = 0.80

    # A trial that never goes anywhere cannot contain running or walking. A
    # squat jump translates the pelvis ~0.3 m while a run covers 5 m, but the
    # jump's push-off and landing briefly exceed static_speed and were being
    # labelled "walking" mid-squat (SJ2 came back a walk outright, SJ3 grew a
    # walk inside its concentric phase). Measured on 021: stationary tasks
    # 0.22-0.34 m, locomotion 4.9-5.5 m — 1.5 m sits in the gap.
    min_trial_travel_m: float = 1.5

    # --- squat jump ---
    # A squat followed by flight is a squat JUMP, not a squat: the descent is
    # the countermovement, the ascent is propulsion, and the task ends with a
    # landing. Merge the two when the gap between them is under this.
    squat_jump_gap_s: float = 0.40

    # --- travelling-task window ---
    # A running/cut capture starts recording before the participant reaches the
    # plates and keeps going after they leave, so the raw block spans the whole
    # trial. Trim it to the plant: from the start of the SECOND-TO-LAST ground
    # contact (which gives the contralateral swing leading into the cut) to the
    # end of the LAST contact. Set False to keep the full travelling block.
    trim_travel_to_grf: bool = True
    # How many contacts to include, counting back from the last.
    travel_contacts: int = 2
    # Emit ONE TASK PER CONTACT instead of a single block spanning them. A
    # sidestep capture is an approach step on one foot then the cut on the
    # other; they are different tasks on different legs and merging them hides
    # which leg did what.
    split_travel_by_contact: bool = True

    # --- running strides ---
    # What bounds a stride: "foot_off" (toe-off to the same foot's next
    # toe-off) or "foot_contact" (contact to contact). This project uses
    # foot_off, so a stride starts as the foot leaves the ground.
    stride_from: str = "foot_off"
    # Shortest credible stride/step; anything faster is marker noise.
    min_stride_s: float = 0.25

    # --- analysis window ---
    # Pelvis height deviation marking the start of a stationary task (squat).
    window_vert_band: float = 0.02        # m
    # Normalised EMG above this fraction of a channel's own range = active.
    emg_active: float = 0.15

    # --- impulse ---
    # Peak total vertical GRF above this = jump landing.
    jump_peak_bw: float = 2.00

    gravity: float = 9.80665


@dataclass
class TrialFeatures:
    """Everything :func:`classify_trial` measured. Reported alongside the label
    so a disagreement can be read rather than guessed at."""
    n_frames: int = 0
    duration_s: float = 0.0
    has_markers: bool = False
    has_grf: bool = False
    median_speed: float = float("nan")      # m/s, horizontal pelvis
    peak_speed: float = float("nan")
    travel_m: float = float("nan")
    lateral_ratio: float = float("nan")
    vertical_rom_m: float = float("nan")    # peak-to-peak pelvis height
    flight_fraction: float = float("nan")
    longest_flight_s: float = float("nan")
    peak_vgrf_bw: float = float("nan")
    left_loaded: bool = False
    right_loaded: bool = False
    sides_loaded: int = 0
    double_support_frac: float = float("nan")
    single_support_frac: float = float("nan")
    single_support_side: str = ""
    # change-of-direction geometry (populated for travelling trials)
    cut_angle_deg: float = float("nan")     # 0 = straight on, 180 = full reversal
    cut_direction: str = ""                 # "left" | "right" | "straight"
    heading_in_deg: float = float("nan")
    heading_out_deg: float = float("nan")
    # analysis window suggested per modality (seconds, absolute trial time)
    window_grf: tuple = ()
    window_markers: tuple = ()
    window_emg: tuple = ()
    window_consensus: tuple = ()

    def as_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Readers — deliberately dependency-free (no pandas): these files are read once
# per trial and a project may classify a few thousand of them.
# ---------------------------------------------------------------------------

def read_trc(path: str) -> Tuple[np.ndarray, Dict[str, np.ndarray], float]:
    """(time, {marker: (n,3) array in METRES}, rate) from an OpenSim .trc."""
    with open(path, "r", errors="ignore") as fh:
        lines = fh.read().split("\n")
    if len(lines) < 6:
        raise ValueError(f"{path}: too short to be a TRC")

    meta = lines[2].split()
    rate = float(meta[0]) if meta else float("nan")
    units = meta[4].lower() if len(meta) > 4 else "mm"
    scale = 0.001 if units.startswith("mm") else 1.0

    names = [n for n in lines[3].split("\t")[2:] if n.strip()]
    rows = []
    for line in lines[5:]:
        tok = line.split()
        if len(tok) < 3:
            continue
        try:
            rows.append([float(x) for x in tok])
        except ValueError:
            continue          # occlusion rows with empty fields
    if not rows:
        return np.array([]), {}, rate

    width = max(len(r) for r in rows)
    arr = np.full((len(rows), width), np.nan)
    for i, r in enumerate(rows):
        arr[i, :len(r)] = r

    time = arr[:, 1]
    data: Dict[str, np.ndarray] = {}
    for i, nm in enumerate(names):
        c = 2 + 3 * i
        if c + 2 < arr.shape[1]:
            data[nm] = arr[:, c:c + 3] * scale
    return time, data, rate


def read_grf(path: str) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    """(time, {column: values}) from an OpenSim .mot."""
    cols, rows = None, []
    with open(path, "r", errors="ignore") as fh:
        for line in fh:
            tok = line.split()
            if cols is None:
                if tok and tok[0] == "time":
                    cols = tok
                continue
            if len(tok) != len(cols):
                continue
            try:
                rows.append([float(x) for x in tok])
            except ValueError:
                continue
    if not cols or not rows:
        return np.array([]), {}
    arr = np.asarray(rows, float)
    return arr[:, 0], {c: arr[:, i] for i, c in enumerate(cols)}


def _plate_sides(grf_xml: str) -> Dict[str, str]:
    """{force_identifier: 'l'|'r'} from a GRF.xml, or {} when unavailable."""
    from xml.etree import ElementTree as ET
    out: Dict[str, str] = {}
    try:
        root = ET.parse(grf_xml).getroot()
    except Exception:
        return out
    for ef in root.iter("ExternalForce"):
        body = (ef.findtext("applied_to_body") or "").strip().lower()
        fid = (ef.findtext("force_identifier") or "").strip()
        if fid and body.startswith("calcn_"):
            out[fid] = "l" if body.endswith("_l") else "r"
    return out



def _cut_geometry(horiz: np.ndarray, time: np.ndarray,
                  cfg: "MocapConfig") -> Tuple[float, str, float, float]:
    """(angle_deg, direction, heading_in_deg, heading_out_deg) for a trajectory.

    ``horiz`` is (n, 2) pelvis position in the horizontal plane, metres.

    The heading BEFORE and AFTER the turn is taken from the first and last
    ``cfg.cut_heading_frac`` of the *travelled distance* — not of the frame
    count. Using distance keeps the estimate stable when the participant
    decelerates into the cut and spends many frames covering little ground,
    which is exactly where a frame-based split would put both windows on the
    same side of the turn.

    Angle is the turn magnitude: 0 deg = carried straight on, 90 deg = square
    cut, 180 deg = full reversal. Direction is the sign of the 2-D cross
    product of the two headings, so it is independent of which way the runway
    points in lab coordinates.
    """
    good = np.isfinite(horiz).all(axis=1)
    P = horiz[good]
    if len(P) < 8:
        return float("nan"), "", float("nan"), float("nan")

    step = np.linalg.norm(np.diff(P, axis=0), axis=1)
    dist = np.concatenate([[0.0], np.cumsum(step)])
    total = dist[-1]
    if total < cfg.min_travel_for_angle:
        return float("nan"), "", float("nan"), float("nan")

    f = cfg.cut_heading_frac
    i_in = int(np.searchsorted(dist, total * f))
    i_out = int(np.searchsorted(dist, total * (1.0 - f)))
    i_in = max(i_in, 1)
    i_out = min(max(i_out, i_in + 1), len(P) - 1)

    v_in = P[i_in] - P[0]
    v_out = P[-1] - P[i_out]
    n_in, n_out = np.linalg.norm(v_in), np.linalg.norm(v_out)
    if n_in < 1e-6 or n_out < 1e-6:
        return float("nan"), "", float("nan"), float("nan")
    v_in, v_out = v_in / n_in, v_out / n_out

    dot = float(np.clip(np.dot(v_in, v_out), -1.0, 1.0))
    angle = round(float(np.degrees(np.arccos(dot))), 1)
    cross = float(v_in[0] * v_out[1] - v_in[1] * v_out[0])

    if angle < cfg.straight_angle_deg:
        direction = "straight"
    else:
        direction = "left" if cross > 0 else "right"
    h_in = round(float(np.degrees(np.arctan2(v_in[1], v_in[0]))), 1)
    h_out = round(float(np.degrees(np.arctan2(v_out[1], v_out[0]))), 1)
    return angle, direction, h_in, h_out


# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------

def _pelvis_centre(markers: Dict[str, np.ndarray]) -> Optional[np.ndarray]:
    """Mean of whichever pelvis marker set is present, or None.

    A marker can be listed in the TRC header and still be entirely occluded, so
    "the column exists" is not "the column has data". Averaging an all-NaN
    stack warns and yields NaN; require at least one finite sample per set
    instead, and fall through to the next convention when there is none.
    """
    for names in _PELVIS_SETS:
        if not all(n in markers for n in names):
            continue
        stack = np.stack([markers[n] for n in names], axis=0)
        if not np.isfinite(stack).any():
            continue
        with np.errstate(invalid="ignore"):
            out = np.full(stack.shape[1:], np.nan)
            ok = np.isfinite(stack).any(axis=0)
            if ok.any():
                out[ok] = np.nanmean(stack, axis=0)[ok]
        return out
    return None


def extract_trial_features(exp_dir: str, body_mass: Optional[float] = None,
                           cfg: Optional[MocapConfig] = None) -> TrialFeatures:
    """Measure one trial's ``2_experimental/<trial>/`` folder."""
    cfg = cfg or MocapConfig()
    f = TrialFeatures()

    trc = os.path.join(exp_dir, "marker_experimental.trc")
    grf = os.path.join(exp_dir, "grf.mot")
    gxml = os.path.join(exp_dir, "GRF.xml")

    # --- markers ---
    if os.path.exists(trc):
        try:
            time, markers, _rate = read_trc(trc)
        except Exception:
            time, markers = np.array([]), {}
        if len(time) > 1 and markers:
            f.has_markers = True
            f.n_frames = len(time)
            f.duration_s = float(time[-1] - time[0])
            pel = _pelvis_centre(markers)
            if pel is not None:
                # OpenSim frame after exportC3D: Y is vertical, X/Z horizontal.
                horiz = pel[:, [0, 2]]
                dt = np.diff(time)
                dt[dt <= 0] = np.nan
                step = np.linalg.norm(np.diff(horiz, axis=0), axis=1)
                spd = step / dt
                spd = spd[np.isfinite(spd)]
                if spd.size:
                    f.median_speed = float(np.median(spd))
                    f.peak_speed = float(np.percentile(spd, 95))
                finite = horiz[np.isfinite(horiz).all(axis=1)]
                if len(finite) > 1:
                    dx = float(np.nanmax(finite[:, 0]) - np.nanmin(finite[:, 0]))
                    dz = float(np.nanmax(finite[:, 1]) - np.nanmin(finite[:, 1]))
                    f.travel_m = math.hypot(dx, dz)
                    # Travel is predominantly along ONE lab axis; the smaller of
                    # the two spans is the lateral component whichever way the
                    # runway is oriented.
                    f.lateral_ratio = (min(dx, dz) / max(dx, dz)
                                       if max(dx, dz) > 1e-6 else float("nan"))
                # Heading is only meaningful when the participant travelled.
                # A jump in place wanders the pelvis over a metre or so and
                # would otherwise report a large spurious "turn".
                if (np.isfinite(f.median_speed)
                        and f.median_speed >= cfg.static_speed):
                    (f.cut_angle_deg, f.cut_direction,
                     f.heading_in_deg, f.heading_out_deg) = _cut_geometry(
                        horiz, time, cfg)
                vert = pel[:, 1]
                vert = vert[np.isfinite(vert)]
                if vert.size:  # noqa: SIM102 - explicit: all-NaN pelvis is valid input
                    f.vertical_rom_m = float(np.nanmax(vert) - np.nanmin(vert))

    # --- ground reaction forces ---
    if os.path.exists(grf):
        gt, gcols = read_grf(grf)
        vy = {c: v for c, v in gcols.items() if c.endswith("_vy")}
        if gt.size and vy:
            f.has_grf = True
            total = np.nansum(np.stack(list(vy.values()), axis=0), axis=0)
            bw = (float(body_mass) * cfg.gravity) if body_mass else None
            if bw and bw > 0:
                f.peak_vgrf_bw = float(np.nanmax(total) / bw)
                thr_flight = cfg.flight_bw * bw
                thr_load = cfg.load_bw * bw
            else:                       # no mass: fall back to a fraction of peak
                pk = float(np.nanmax(total)) or 1.0
                thr_flight = 0.10 * pk
                thr_load = 0.10 * pk
            air = total < thr_flight
            f.flight_fraction = float(np.mean(air))
            # longest CONTIGUOUS airborne block, in seconds
            dt = float(np.median(np.diff(gt))) if gt.size > 1 else 0.0
            best = run = 0
            for a in air:
                run = run + 1 if a else 0
                best = max(best, run)
            f.longest_flight_s = best * dt

            # Per-side load as a TIME SERIES, not a whole-trial maximum. A
            # single-leg squat begins with the participant standing on both
            # feet, so "did this side ever exceed threshold" answers yes for
            # both legs and calls the trial bilateral. Measured on FAIS
            # SLSfront1: both feet loaded for 14% of the trial (the set-up),
            # right foot ALONE for 86% (the actual task).
            sides = _plate_sides(gxml)
            per = {"l": np.zeros(gt.size), "r": np.zeros(gt.size)}
            for fid, side in sides.items():
                v = gcols.get(fid + "y")        # ground_force_1_v -> ..._vy
                if v is None or v.size != gt.size:
                    continue
                per[side] = np.maximum(per[side], np.nan_to_num(v))
            L, R = per["l"] >= thr_load, per["r"] >= thr_load
            if gt.size:
                f.double_support_frac = float(np.mean(L & R))
                only_l, only_r = float(np.mean(L & ~R)), float(np.mean(~L & R))
                f.single_support_frac = only_l + only_r
                if f.single_support_frac > 0:
                    f.single_support_side = "l" if only_l >= only_r else "r"
            f.left_loaded = bool(L.any())
            f.right_loaded = bool(R.any())
            f.sides_loaded = int(f.left_loaded) + int(f.right_loaded)
    return f




# ---------------------------------------------------------------------------
# Segmentation — several tasks within one capture
# ---------------------------------------------------------------------------

@dataclass
class TaskSegment:
    """One contiguous block of a trial holding a single task.

    ``phase`` names a sub-division of the parent task — "eccentric" / "hold" /
    "concentric" for a squat, "stride" / "stance" / "swing" for gait. Top-level
    task rows carry an empty ``phase``; their sub-phases are listed in
    ``phases``.
    """
    task: str
    t_start: float
    t_end: float
    confidence: float = 0.0
    reason: str = ""
    phase: str = ""
    side: str = ""
    index: int = 0
    phases: list = field(default_factory=list)

    @property
    def duration(self) -> float:
        return round(self.t_end - self.t_start, 3)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["duration"] = self.duration
        d["phases"] = [p.as_dict() for p in self.phases]
        return d

    def __repr__(self) -> str:
        tag = f":{self.phase}" if self.phase else ""
        sd = f" {self.side}" if self.side else ""
        return (f"TaskSegment({self.task}{tag}{sd}, "
                f"{self.t_start:.2f}-{self.t_end:.2f}s, {self.duration:.2f}s)")


def _foot_height(markers: Dict[str, np.ndarray], side: str):
    """Mean vertical position of one foot's markers, or None."""
    names = [m for m in markers
             if m.upper().startswith(side.upper())
             and any(k in m.upper() for k in ("HEE", "MT1", "MT2", "MT5", "TOE"))]
    if not names:
        return None
    stack = np.stack([markers[n][:, 1] for n in names], axis=0)
    if not np.isfinite(stack).any():
        return None                       # every foot marker occluded
    out = np.full(stack.shape[1], np.nan)
    ok = np.isfinite(stack).any(axis=0)
    if ok.any():
        with np.errstate(invalid="ignore"):
            out[ok] = np.nanmean(stack, axis=0)[ok]
    return out


def _smooth_runs(labels: List[str], t: np.ndarray, min_s: float) -> List[str]:
    """Absorb runs shorter than ``min_s`` into whichever neighbour is longer."""
    if not len(labels):
        return labels
    out = list(labels)
    changed = True
    while changed:
        changed = False
        runs, start = [], 0
        for i in range(1, len(out) + 1):
            if i == len(out) or out[i] != out[start]:
                runs.append((start, i - 1, out[start]))
                start = i
        for k, (a, b, lab) in enumerate(runs):
            if float(t[b] - t[a]) >= min_s or len(runs) == 1:
                continue
            prev_len = (t[runs[k - 1][1]] - t[runs[k - 1][0]]) if k else -1
            next_len = (t[runs[k + 1][1]] - t[runs[k + 1][0]]) if k + 1 < len(runs) else -1
            take = runs[k - 1][2] if prev_len >= next_len and k else (
                runs[k + 1][2] if k + 1 < len(runs) else lab)
            for i in range(a, b + 1):
                out[i] = take
            changed = True
            break
    return out




def _grf_contact_feet(exp_dir: str, body_mass, cfg) -> List[dict]:
    """Contacts with their foot — thin wrapper so segment_trial and the public
    :func:`contact_feet` cannot drift apart."""
    return contact_feet(exp_dir, body_mass, cfg)


def _grf_contacts_unused(exp_dir: str, body_mass, cfg) -> List[Tuple[float, float]]:
    """[(t_on, t_off)] for every ground contact, from the TOTAL vertical GRF.

    Total rather than per-plate: the plate->foot mapping is often partial (see
    segment_trial), but the sum is right regardless of which plate is mapped.
    """
    gm = os.path.join(exp_dir, "grf.mot")
    if not os.path.exists(gm):
        return []
    gt, gcols = read_grf(gm)
    vy = [v for c, v in gcols.items() if c.endswith("_vy")]
    if not gt.size or not vy:
        return []
    total = np.nansum(np.stack(vy, axis=0), axis=0)
    thr = (cfg.load_bw * float(body_mass) * cfg.gravity) if body_mass \
        else cfg.load_bw * float(np.nanmax(total) or 1.0)
    on = total > thr
    out, start = [], None
    for i, v in enumerate(on):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((float(gt[start]), float(gt[i - 1])))
            start = None
    if start is not None:
        out.append((float(gt[start]), float(gt[-1])))
    # drop blips too short to be a real footfall
    return [(a, b) for a, b in out if (b - a) >= 0.02]




def foot_events_from_markers(exp_dir: str, cfg: Optional["MocapConfig"] = None
                             ) -> Dict[str, Dict[str, List[float]]]:
    """Foot contacts and toe-offs per leg, from MARKER kinematics alone.

    ``{"l": {"contact": [t...], "off": [t...]}, "r": {...}}``.

    Force plates only see a foot while it is ON a plate, so a stride that
    starts on a plate and ends off it cannot be closed from GRF. Marker
    kinematics see the foot throughout: a contact is a minimum of foot height
    where vertical velocity crosses from negative to ~zero, and a toe-off is
    where it starts rising again. That lets the contralateral stride be
    completed while the other leg is the one being measured.

    Detection is deliberately kinematic-only so it works for the many trials
    here whose GRF.xml maps one plate or none.
    """
    cfg = cfg or MocapConfig()
    trc = os.path.join(exp_dir, "marker_experimental.trc")
    if not os.path.exists(trc):
        return {}
    try:
        t, markers, _ = read_trc(trc)
    except Exception:
        return {}
    if t.size < 5 or not markers:
        return {}

    fs = 1.0 / max(float(np.median(np.diff(t))), 1e-6)
    out: Dict[str, Dict[str, List[float]]] = {}
    for side, key in (("l", "L"), ("r", "R")):
        h = _foot_height(markers, key)
        if h is None:
            continue
        good = np.isfinite(h)
        if good.sum() < 5:
            continue
        hh = np.interp(np.arange(len(h)), np.flatnonzero(good), h[good])
        w = max(3, int(0.03 * fs))
        hh = np.convolve(hh, np.ones(w) / w, mode="same")
        floor = float(np.nanpercentile(hh, 5))
        lift = hh - floor
        vel = np.gradient(hh) * fs

        near = lift < cfg.foot_lift_m
        contacts, offs = [], []
        for i in range(1, len(near)):
            if near[i] and not near[i - 1] and vel[i] <= 0:
                contacts.append(float(t[i]))          # coming down onto the floor
            elif near[i - 1] and not near[i] and vel[i] >= 0:
                offs.append(float(t[i]))              # leaving it
        def _thin(xs):
            keep = []
            for x in xs:
                if not keep or (x - keep[-1]) >= cfg.min_stride_s:
                    keep.append(round(x, 3))
            return keep
        out[side] = {"contact": _thin(contacts), "off": _thin(offs)}
    return out


def contact_feet(exp_dir: str, body_mass=None,
                 cfg: Optional["MocapConfig"] = None) -> List[dict]:
    """Ground contacts with the foot that made each one, from the DATA.

    Returns ``[{"t_on", "t_off", "side", "peak_n", "plate", "margin_m"}]``.

    The foot is decided by comparing the plate's centre of pressure against
    each foot's markers at the instant of peak force — NOT by reading
    GRF.XML. That mapping is produced once at export time and is wrong often
    enough to matter: on Run_baselineB2 it labels both plates "right", while
    the CoP sits 2.5 cm from the LEFT foot and 73 cm from the right on the
    first contact. ``margin_m`` is the difference between the two distances,
    so a marginal assignment is visible rather than silent.
    """
    cfg = cfg or MocapConfig()
    gm = os.path.join(exp_dir, "grf.mot")
    trc = os.path.join(exp_dir, "marker_experimental.trc")
    if not (os.path.exists(gm) and os.path.exists(trc)):
        return []
    gt, gcols = read_grf(gm)
    try:
        t, markers, _ = read_trc(trc)
    except Exception:
        return []
    if not gt.size or not markers:
        return []

    feet = {}
    for side, key in (("l", "L"), ("r", "R")):
        names = [m for m in markers
                 if m.upper().startswith(key)
                 and any(k in m.upper() for k in ("HEE", "MT1", "MT2", "MT5", "TOE"))]
        if names:
            feet[side] = np.nanmean(np.stack([markers[n] for n in names], axis=0), axis=0)
    if not feet:
        return []

    total = np.nansum(np.stack([v for c, v in gcols.items()
                                if c.endswith("_vy")], axis=0), axis=0) \
        if any(c.endswith("_vy") for c in gcols) else np.zeros(gt.size)
    thr = (cfg.load_bw * float(body_mass) * cfg.gravity) if body_mass \
        else cfg.load_bw * float(np.nanmax(total) or 1.0)

    out = []
    plates = sorted({c.rsplit("_", 1)[0] for c in gcols if c.endswith("_vy")})
    for pre in plates:
        vy = gcols.get(pre + "_vy")
        if vy is None or not np.isfinite(vy).any() or float(np.nanmax(vy)) < thr:
            continue
        on = vy > thr
        start = None
        for i in range(len(on) + 1):
            if i < len(on) and on[i]:
                if start is None:
                    start = i
                continue
            if start is None:
                continue
            a, b = start, i - 1
            start = None
            if float(gt[b] - gt[a]) < 0.02:
                continue
            k = a + int(np.nanargmax(vy[a:b + 1]))
            px, pz = gcols.get(pre + "_px"), gcols.get(pre + "_pz")
            side, margin = "", float("nan")
            if px is not None and pz is not None and np.isfinite(px[k]) and np.isfinite(pz[k]):
                cop = np.array([px[k], pz[k]])
                j = int(np.argmin(np.abs(t - gt[k])))
                d = {}
                for sd, arr in feet.items():
                    if j < len(arr) and np.isfinite(arr[j][0]) and np.isfinite(arr[j][2]):
                        d[sd] = float(np.linalg.norm(np.array([arr[j][0], arr[j][2]]) - cop))
                if d:
                    side = min(d, key=d.get)
                    margin = round(abs(d.get("l", np.nan) - d.get("r", np.nan)), 3) \
                        if len(d) == 2 else float("nan")
            out.append({"t_on": round(float(gt[a]), 3), "t_off": round(float(gt[b]), 3),
                        "side": side, "peak_n": round(float(np.nanmax(vy[a:b + 1])), 1),
                        "plate": pre, "margin_m": margin})
    out.sort(key=lambda c: c["t_on"])
    return out


def _squat_phases(t, depth, a, b, cfg) -> Tuple[int, int, List[TaskSegment]]:
    """Grow a squat out to its true start/end and split it into phases.

    ``a``/``b`` bracket the frames that exceeded ``squat_drop_m``. The real
    task starts earlier: the descent begins the moment the pelvis leaves
    standing height. Walk outward from the depth peak until the pelvis is back
    within ``squat_onset_band_m`` of standing, then divide into

        eccentric   descending
        hold        at the bottom, |vertical velocity| < hold_vel_ms
        concentric  rising

    Returns (start_idx, end_idx, phases).
    """
    n = len(t)
    peak = int(a + np.nanargmax(depth[a:b + 1])) if b >= a else a
    band = cfg.squat_onset_band_m
    i0 = peak
    while i0 > 0 and depth[i0] > band:
        i0 -= 1
    i1 = peak
    while i1 < n - 1 and depth[i1] > band:
        i1 += 1

    # vertical velocity of the pelvis (negative = descending)
    dt = np.gradient(t)
    vel = -np.gradient(depth) / np.where(dt == 0, np.nan, dt)   # +ve = rising
    vel = np.nan_to_num(vel)

    dmax = float(np.nanmax(depth[i0:i1 + 1])) if i1 > i0 else 0.0
    deep = depth >= cfg.hold_depth_frac * dmax
    still = np.abs(vel) < cfg.hold_vel_ms

    hold_idx = [i for i in range(i0, i1 + 1) if deep[i] and still[i]]
    phases: List[TaskSegment] = []

    def _add(name, x0, x1):
        if x1 > x0 and (t[x1] - t[x0]) > 0.05:
            phases.append(TaskSegment(task="squat", phase=name,
                                      t_start=round(float(t[x0]), 3),
                                      t_end=round(float(t[x1]), 3),
                                      confidence=0.7,
                                      reason=f"{(depth[x1]-depth[x0])*100:+.0f} cm"))

    if hold_idx:
        h0, h1 = hold_idx[0], hold_idx[-1]
        _add("descent", i0, h0)
        _add("hold", h0, h1)
        _add("concentric", h1, i1)
    else:
        _add("descent", i0, peak)
        _add("concentric", peak, i1)
    return i0, i1, phases


def _gait_events(t, lifted_side, cfg) -> Tuple[List[int], List[int]]:
    """(foot_off_indices, foot_contact_indices) for one foot.

    ``lifted_side`` is the boolean "this foot is off the ground" series, so a
    foot-off is a rising edge and a contact is a falling edge.
    """
    d = np.diff(lifted_side.astype(int))
    offs = list(np.flatnonzero(d == 1) + 1)
    contacts = list(np.flatnonzero(d == -1) + 1)

    def _thin(idx):
        out = []
        for i in idx:
            if not out or (t[i] - t[out[-1]]) >= cfg.min_stride_s:
                out.append(i)
        return out
    return _thin(offs), _thin(contacts)


def _gait_phases(t, lifted, a, b, cfg, marker_events=None) -> List[TaskSegment]:
    """Split a travelling block into strides, per leg.

    A stride is bounded by consecutive events of the SAME foot. Which event
    depends on ``cfg.stride_from``: "foot_off" (this project) starts the stride
    as the foot leaves the ground, "foot_contact" starts it at touch-down. Both
    conventions describe the same cycle, they just cut it at a different point,
    so the choice matters when comparing to literature.
    """
    phases: List[TaskSegment] = []
    for side, key in (("left", "L"), ("right", "R")):
        seg = lifted[key][a:b + 1]
        if seg.size < 3:
            continue
        offs, contacts = _gait_events(t[a:b + 1], seg, cfg)
        # Prefer events estimated from marker kinematics across the WHOLE
        # trial: they close a stride that leaves the plates, which the
        # plate-bounded events cannot. Fall back to the in-block detection.
        _me = (marker_events or {}).get(key.lower()) or {}
        if _me.get("off") and _me.get("contact"):
            offs = [int(np.argmin(np.abs(t - x))) - a for x in _me["off"]]
            contacts = [int(np.argmin(np.abs(t - x))) - a for x in _me["contact"]]
            offs = [i for i in offs if 0 <= i < len(seg)]
            contacts = [i for i in contacts if 0 <= i < len(seg)]
        marks = offs if cfg.stride_from == "foot_off" else contacts
        for k in range(len(marks) - 1):
            x0, x1 = a + marks[k], a + marks[k + 1]
            phases.append(TaskSegment(
                task="stride", phase=f"stride_{cfg.stride_from}", side=side,
                index=k + 1,
                t_start=round(float(t[x0]), 3), t_end=round(float(t[x1]), 3),
                confidence=0.6,
                reason=f"{side} stride {k+1}, {float(t[x1]-t[x0]):.2f}s "
                       f"({cfg.stride_from} to {cfg.stride_from})"))
        # stance / swing within the block, useful when only one event is seen
        for k in range(min(len(offs), len(contacts))):
            o, c = offs[k], contacts[k]
            if c > o:
                phases.append(TaskSegment(
                    task="swing", phase="swing", side=side, index=k + 1,
                    t_start=round(float(t[a + o]), 3),
                    t_end=round(float(t[a + c]), 3), confidence=0.6,
                    reason=f"{side} foot off the ground"))
    phases.sort(key=lambda p: p.t_start)
    return phases


def segment_trial(exp_dir: str, body_mass: Optional[float] = None,
                  cfg: Optional[MocapConfig] = None) -> List[TaskSegment]:
    """Split one trial into the tasks it actually contains.

    A capture is rarely one task. A single-leg squat trial is typically
    *stand -> lift a foot -> squat -> rise -> put the foot down*, and collapsing
    that to one label both loses the timing and can pick the wrong winner: the
    standing portions make the whole trial look bilateral.

    Support state comes from the FOOT MARKERS, not the force plates. Plate
    mapping is per-trial and frequently partial — SLSback_post1's GRF.xml
    registers a single plate, so the stance foot spends the trial on an
    unmapped one and force alone reports "airborne" for 68% of a standing
    trial. Marker height needs no plate mapping at all. GRF is still used for
    flight detection when the mapping covers both feet.

    Returns a list of :class:`TaskSegment` ordered in time; an empty list when
    there are no markers to work from.
    """
    cfg = cfg or MocapConfig()
    trc = os.path.join(exp_dir, "marker_experimental.trc")
    if not os.path.exists(trc):
        return []
    try:
        t, markers, _rate = read_trc(trc)
    except Exception:
        return []
    pel = _pelvis_centre(markers) if markers else None
    if pel is None or t.size < 5:
        return []

    # pelvis: depth below the standing reference, and horizontal speed
    vert = pel[:, 1]
    if not np.isfinite(vert).any():
        return []                         # pelvis never seen — nothing to segment
    head = vert[:max(3, len(vert) // 20)]
    # The first 5% can be entirely occluded; fall back to the whole trial.
    base = float(np.nanmedian(head)) if np.isfinite(head).any() \
        else float(np.nanmedian(vert[np.isfinite(vert)]))
    depth = base - vert
    horiz = pel[:, [0, 2]]
    dt = np.diff(t); dt[dt <= 0] = np.nan
    spd = np.concatenate([[0.0],
                          np.linalg.norm(np.diff(horiz, axis=0), axis=1) / dt])
    spd = np.nan_to_num(spd)
    # a short moving-average keeps single-frame dropouts from splitting a task
    fs = 1.0 / max(float(np.median(np.diff(t))), 1e-6)
    w = max(3, int(0.10 * fs))
    ker = np.ones(w) / w
    depth = np.convolve(np.nan_to_num(depth), ker, mode="same")

    # Travel is NET DISPLACEMENT over a window, not instantaneous speed.
    # Squatting sways the pelvis past 0.2 m/s repeatedly while going nowhere;
    # scoring that as "walking" chopped a single-leg squat into 0.3 s fragments,
    # each under min_task_s, and smoothing then absorbed the whole task. Net
    # displacement over +/-0.5 s is ~0 for sway and unchanged for real travel.
    half = max(1, int(0.5 * fs))
    a = np.clip(np.arange(len(t)) - half, 0, len(t) - 1)
    b = np.clip(np.arange(len(t)) + half, 0, len(t) - 1)
    span = np.maximum(t[b] - t[a], 1e-6)
    spd = np.linalg.norm(horiz[b] - horiz[a], axis=1) / span
    spd = np.nan_to_num(spd)

    # feet: lifted relative to each foot's OWN floor level
    lifted = {}
    for side in ("L", "R"):
        h = _foot_height(markers, side)
        if h is None:
            lifted[side] = np.zeros(len(t), bool)
            continue
        floor = float(np.nanpercentile(h[np.isfinite(h)], 5)) if np.isfinite(h).any() else 0.0
        lifted[side] = np.nan_to_num(h - floor) > cfg.foot_lift_m

    # airborne, only when the plate mapping covers both feet
    air = np.zeros(len(t), bool)
    gm = os.path.join(exp_dir, "grf.mot")
    gx = os.path.join(exp_dir, "GRF.xml")
    sides = set(_plate_sides(gx).values())
    if os.path.exists(gm) and sides == {"l", "r"}:
        gt, gcols = read_grf(gm)
        vy = [v for c, v in gcols.items() if c.endswith("_vy")]
        if gt.size and vy:
            total = np.nansum(np.stack(vy, axis=0), axis=0)
            thr = (cfg.flight_bw * float(body_mass) * cfg.gravity) if body_mass \
                else cfg.flight_bw * float(np.nanmax(total) or 1.0)
            air = np.interp(t, gt, (total < thr).astype(float)) > 0.5

    # Did the participant actually go anywhere? See min_trial_travel_m.
    _fin = horiz[np.isfinite(horiz).all(axis=1)]
    _travel = float(np.hypot(np.ptp(_fin[:, 0]), np.ptp(_fin[:, 1]))) \
        if len(_fin) > 1 else 0.0
    _travels = _travel >= cfg.min_trial_travel_m

    # --- frame-level task -------------------------------------------------
    labels: List[str] = []
    for i in range(len(t)):
        both_lifted = lifted["L"][i] and lifted["R"][i]
        one_lifted = lifted["L"][i] ^ lifted["R"][i]
        # Travel is tested FIRST. Running has a flight phase by definition —
        # both feet leave the ground every stride — so checking "both feet off"
        # before travel labelled the flight phases of a run as jumps and split
        # the run into fragments. A jump is airborne WITHOUT travel.
        if spd[i] >= cfg.static_speed and _travels:
            labels.append("running" if spd[i] >= cfg.walk_run_speed else "walking")
        elif air[i] or both_lifted:
            labels.append("jump")
        elif one_lifted:
            labels.append("single_leg_squat" if depth[i] >= cfg.squat_drop_m
                          else "single_leg_stance")
        else:
            labels.append("squat" if depth[i] >= cfg.squat_drop_m else "static")

    labels = _smooth_runs(labels, t, cfg.min_task_s)

    # Whether the trial as a whole was a change of direction — decided from the
    # travel geometry, which is a property of the WHOLE path and cannot be read
    # off any single frame. Applied to the travelling blocks below so a cut is
    # reported as a cut rather than as running.
    # Marker-derived gait events, computed once for the whole trial.
    try:
        _marker_events = foot_events_from_markers(exp_dir, cfg)
    except Exception:
        _marker_events = {}

    cut_angle, cut_dir = float("nan"), ""
    if float(np.nanmax(spd)) >= cfg.walk_run_speed:
        cut_angle, cut_dir, _hi, _ho = _cut_geometry(horiz, t, cfg)

    # --- runs -> segments -------------------------------------------------
    out: List[TaskSegment] = []
    start = 0
    for i in range(1, len(labels) + 1):
        if i < len(labels) and labels[i] == labels[start]:
            continue
        a, b = start, i - 1
        lab = labels[a]
        d = float(np.nanmax(depth[a:b + 1])) if b >= a else 0.0
        v = float(np.nanmax(spd[a:b + 1])) if b >= a else 0.0
        side = ""
        phases: List[TaskSegment] = []
        if lab.startswith("single_leg"):
            side = "right" if lifted["L"][a:b + 1].mean() > 0.5 else "left"
            why = f"standing on the {side} leg, {d*100:.0f} cm of descent"
            if lab == "single_leg_squat":
                a, b, phases = _squat_phases(t, depth, a, b, cfg)
                for ph in phases:
                    ph.task, ph.side = lab, side
        elif lab == "squat":
            # Grow the block back to the start of the DESCENT and split it into
            # eccentric / hold / concentric.
            a, b, phases = _squat_phases(t, depth, a, b, cfg)
            d = float(np.nanmax(depth[a:b + 1]))
            why = f"both feet down, {d*100:.0f} cm of descent"
        elif lab == "static":
            why = "both feet down, no descent"
        elif lab == "jump":
            why = "both feet off the ground"
        else:
            _turning = bool(np.isfinite(cut_angle) and cut_dir
                            and cut_dir != "straight")
            if _turning:
                lab = "cut"
                why = (f"{v:.2f} m/s, change of direction "
                       f"{cut_angle:.0f}\u00b0 to the {cut_dir}")
                side = cut_dir
            else:
                why = f"travelling at up to {v:.2f} m/s"
            phases = _gait_phases(t, lifted, a, b, cfg,
                                  marker_events=_marker_events)

            # One task PER GROUND CONTACT. A sidestep capture is an approach
            # step on one leg and then the cut on the other; they are different
            # tasks performed by different legs, and reporting one block over
            # both loses which leg did what. The LAST contact is the cut (when
            # the path turns); the ones before it are approach steps.
            _cs = _grf_contact_feet(exp_dir, body_mass, cfg) \
                if (cfg.trim_travel_to_grf or cfg.split_travel_by_contact) else []
            if _cs and cfg.split_travel_by_contact:
                _take = _cs[-max(1, cfg.travel_contacts):]
                for _k, _c in enumerate(_take):
                    _last = (_k == len(_take) - 1)
                    _ia = int(np.argmin(np.abs(t - _c["t_on"])))
                    _ib = int(np.argmin(np.abs(t - _c["t_off"])))
                    if _ib <= _ia:
                        continue
                    _foot = {"l": "left", "r": "right"}.get(_c["side"], _c["side"])
                    if _last and _turning:
                        _lab = "cut"
                        _why = (f"{_foot or '?'}-foot plant, {cut_angle:.0f}\u00b0 "
                                f"to the {cut_dir}, peak {_c['peak_n']:.0f} N")
                        _sd = cut_dir
                    else:
                        _lab = "running" if v >= cfg.walk_run_speed else "walking"
                        _why = (f"{_foot or '?'}-foot contact at {v:.2f} m/s, "
                                f"peak {_c['peak_n']:.0f} N"
                                + ("" if _last else " (approach step)"))
                        _sd = _foot
                    # Strides are NOT clipped to the plant window. A stride is
                    # a full gait cycle, not a subdivision of the contact: the
                    # foot leaves the plate mid-cycle and its next contact is
                    # estimated from marker kinematics, so the cycle legitimately
                    # extends past the force the plate could see. Keep any stride
                    # that overlaps this contact, whole.
                    _ph = [_p for _p in phases
                           if not (_p.t_end < _c["t_on"] or _p.t_start > _c["t_off"])]
                    out.append(TaskSegment(
                        task=_lab, side=_sd, t_start=round(float(_c["t_on"]), 3),
                        t_end=round(float(_c["t_off"]), 3), confidence=0.75,
                        reason=_why, phases=_ph))
                start = i
                continue
            # Not splitting: keep one block, trimmed to the plant.
            if cfg.trim_travel_to_grf and _cs:
                if True:
                    _take = _cs[-max(1, cfg.travel_contacts):]
                    _t0, _t1 = _take[0]["t_on"], _take[-1]["t_off"]
                    _ia = int(np.argmin(np.abs(t - _t0)))
                    _ib = int(np.argmin(np.abs(t - _t1)))
                    if _ib > _ia:
                        a, b = _ia, _ib
                        why += (f"; window trimmed to the last {len(_take)} "
                                f"ground contact(s)")
                        # Clip the strides to the trimmed window too — a phase
                        # that runs past its parent task reads as a data error.
                        _w0, _w1 = float(t[a]), float(t[b])
                        _kept = []
                        for ph in phases:
                            if ph.t_end < _w0 or ph.t_start > _w1:
                                continue
                            ph.t_start = round(max(ph.t_start, _w0), 3)
                            ph.t_end = round(min(ph.t_end, _w1), 3)
                            if ph.duration > 0.02:
                                _kept.append(ph)
                        phases = _kept
        out.append(TaskSegment(task=lab, side=side,
                               t_start=round(float(t[a]), 3),
                               t_end=round(float(t[b]), 3),
                               confidence=0.7, reason=why, phases=phases))
        start = i

    # A squat is grown OUTWARD from its depth peak, so it can overlap the
    # standing blocks on either side. The squat wins those frames — it was
    # extended deliberately, to capture the descent from its first millimetre —
    # so the neighbour is trimmed, never the squat. Trimming the squat instead
    # cut the concentric phase off at the old threshold crossing.
    # A squat that ends in flight is a squat JUMP. Merge the pair before the
    # overlap pass so the merged task, not its halves, owns the frames.
    _merged, _k = [], 0
    while _k < len(out):
        _g = out[_k]
        _nx = out[_k + 1] if _k + 1 < len(out) else None
        if (_g.task in ("squat", "single_leg_squat") and _nx is not None
                and _nx.task == "jump"
                and (_nx.t_start - _g.t_end) <= cfg.squat_jump_gap_s):
            _ph = list(_g.phases)
            _ph.append(TaskSegment(task="squat_jump", phase="air_time",
                                   t_start=_nx.t_start, t_end=_nx.t_end,
                                   confidence=0.8, reason="both feet off the ground"))
            _after = out[_k + 2] if _k + 2 < len(out) else None
            if _after is not None and _after.task in ("static", "single_leg_stance"):
                _ph.append(TaskSegment(
                    task="squat_jump", phase="landing",
                    t_start=_after.t_start,
                    t_end=round(min(_after.t_end, _after.t_start + 0.5), 3),
                    confidence=0.7, reason="ground contact after flight"))
            for _p in _ph:
                _p.task = "squat_jump"
            _merged.append(TaskSegment(
                task="squat_jump", side=_g.side, t_start=_g.t_start,
                t_end=_nx.t_end, confidence=0.85,
                reason=(f"{_g.reason.split(',')[-1].strip()} then "
                        f"{_nx.duration:.2f}s of flight"),
                phases=_ph))
            _k += 2
            continue
        _merged.append(_g)
        _k += 1
    out = _merged

    _GROWN = {"squat", "single_leg_squat", "squat_jump"}
    for k in range(1, len(out)):
        prev, cur = out[k - 1], out[k]
        if cur.t_start >= prev.t_end:
            continue
        if cur.task in _GROWN and prev.task not in _GROWN:
            prev.t_end = cur.t_start
        elif prev.task in _GROWN and cur.task not in _GROWN:
            cur.t_start = prev.t_end
        else:
            prev.t_end = cur.t_start
    out = [g for g in out if g.duration > 0.02]
    return out


# ---------------------------------------------------------------------------
# Analysis window
# ---------------------------------------------------------------------------

def _span(mask: np.ndarray, t: np.ndarray, pad: float = 0.0) -> tuple:
    """(first, last) time where ``mask`` is True, padded and clipped."""
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return ()
    t0, t1 = float(t[idx[0]]), float(t[idx[-1]])
    if pad:
        t0, t1 = max(float(t[0]), t0 - pad), min(float(t[-1]), t1 + pad)
    return (round(t0, 4), round(t1, 4))


def detect_window(exp_dir: str, body_mass: Optional[float] = None,
                  cfg: Optional[MocapConfig] = None) -> Dict[str, tuple]:
    """Suggest the analysis window from each modality independently.

    Returns ``{"grf": (t0,t1), "markers": (...), "emg": (...),
    "consensus": (...)}`` — an empty tuple where that modality had nothing to
    say. Three independent opinions are reported rather than one number so a
    disagreement is visible: if GRF and markers bracket different intervals,
    the plate assignment or the marker export is suspect.

    * **grf**     — total vertical force above ``load_bw`` body weights.
    * **markers** — pelvis speed above ``static_speed``, OR (for a stationary
      task, where that never fires) pelvis height outside a 2 cm band around
      its own start, which is what a squat descent looks like.
    * **emg**     — any normalised channel above ``emg_active`` of its own
      range. Uses ``emg_filtered_normalised.mot`` when present, else
      ``emg_filtered.mot``.
    * **consensus** — the MEDIAN start and median end of whichever modalities
      spoke. The median ignores one dissenting modality without needing it to
      be identified in advance.
    """
    cfg = cfg or MocapConfig()
    out: Dict[str, tuple] = {"grf": (), "markers": (), "emg": (), "consensus": ()}

    # --- ground reaction force ---
    gm = os.path.join(exp_dir, "grf.mot")
    if os.path.exists(gm):
        gt, gcols = read_grf(gm)
        vy = [v for c, v in gcols.items() if c.endswith("_vy")]
        if gt.size and vy:
            total = np.nansum(np.stack(vy, axis=0), axis=0)
            thr = (cfg.load_bw * float(body_mass) * cfg.gravity) if body_mass \
                else cfg.load_bw * float(np.nanmax(total) or 1.0)
            out["grf"] = _span(total > thr, gt)

    # --- markers ---
    trc = os.path.join(exp_dir, "marker_experimental.trc")
    if os.path.exists(trc):
        try:
            t, markers, _ = read_trc(trc)
        except Exception:
            t, markers = np.array([]), {}
        pel = _pelvis_centre(markers) if markers else None
        if pel is not None and t.size > 2:
            horiz = pel[:, [0, 2]]
            dt = np.diff(t); dt[dt <= 0] = np.nan
            spd = np.concatenate([[0.0],
                                  np.linalg.norm(np.diff(horiz, axis=0), axis=1) / dt])
            spd = np.nan_to_num(spd)
            moving = spd > cfg.static_speed
            if moving.any():
                out["markers"] = _span(moving, t)
            else:
                vert = pel[:, 1]
                base = np.nanmedian(vert[:max(3, len(vert) // 20)])
                out["markers"] = _span(np.abs(vert - base) > cfg.window_vert_band, t)

    # --- EMG ---
    for name in ("emg_filtered_normalised.mot", "emg_filtered.mot", "emg.mot"):
        ep = os.path.join(exp_dir, name)
        if not os.path.exists(ep):
            continue
        et, ecols = read_grf(ep)          # same .mot reader
        chans = [v for c, v in ecols.items() if c.lower() != "time"]
        if not et.size or not chans:
            continue
        A = np.abs(np.stack(chans, axis=0))
        rng = np.nanmax(A, axis=1, keepdims=True)
        rng[rng <= 0] = 1.0
        active = (A / rng).max(axis=0) > cfg.emg_active
        out["emg"] = _span(active, et)
        break

    spoke = [v for k, v in out.items() if k != "consensus" and v]
    if spoke:
        out["consensus"] = (round(float(np.median([v[0] for v in spoke])), 4),
                            round(float(np.median([v[1] for v in spoke])), 4))
    return out


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify_features(f: TrialFeatures,
                      cfg: Optional[MocapConfig] = None) -> Tuple[str, float, str]:
    """(label, confidence 0-1, one-line reason) from measured features.

    Ordered most-specific first. Confidence is a blunt indicator of how far the
    deciding feature sat from its threshold, not a probability.
    """
    cfg = cfg or MocapConfig()

    if not f.has_markers:
        return "emg_only", 1.0, "no 3-D point data in the capture"

    spd = f.median_speed
    rom = f.vertical_rom_m
    flight = f.longest_flight_s

    if not np.isfinite(spd):
        return "unknown", 0.0, "pelvis markers missing — no speed available"

    travelling = spd >= cfg.static_speed
    airborne = np.isfinite(flight) and flight >= cfg.min_flight_s

    # --- travelling tasks -------------------------------------------------
    if travelling:
        if (np.isfinite(f.lateral_ratio)
                and f.lateral_ratio >= cfg.cut_lateral_ratio
                and spd >= cfg.walk_run_speed):
            ang = (f"{f.cut_angle_deg:.0f}\u00b0 to the {f.cut_direction}"
                   if np.isfinite(f.cut_angle_deg) and f.cut_direction
                   else f"{f.lateral_ratio:.0%} of travel lateral")
            return "cut", 0.8, f"{spd:.2f} m/s, change of direction {ang}"
        if spd >= cfg.walk_run_speed or airborne:
            why = (f"speed {spd:.2f} m/s"
                   + (f" with {flight:.2f}s flight" if airborne else ", no flight"))
            return "running", 0.9 if airborne else 0.6, why
        return "walking", 0.7, f"speed {spd:.2f} m/s, no flight phase"

    # --- stationary tasks -------------------------------------------------
    if airborne and np.isfinite(f.peak_vgrf_bw) and f.peak_vgrf_bw >= cfg.jump_peak_bw:
        return "jump", 0.9, (f"{flight:.2f}s flight, peak "
                             f"{f.peak_vgrf_bw:.1f} BW, no travel")
    if airborne:
        return "jump", 0.6, f"{flight:.2f}s flight with no travel"

    if np.isfinite(rom) and rom >= cfg.squat_drop_m:
        if f.has_grf and np.isfinite(f.single_support_frac) \
                and f.single_support_frac >= cfg.single_support_frac:
            side = "left" if f.single_support_side == "l" else "right"
            return "single_leg_squat", 0.8, (
                f"{rom*100:.0f} cm vertical, {side} foot alone for "
                f"{f.single_support_frac:.0%} of the trial")
        return "squat", 0.8, (f"{rom*100:.0f} cm vertical, both feet loaded "
                              f"{f.double_support_frac:.0%} of the trial")

    if np.isfinite(rom) and rom <= cfg.static_drop_m:
        return "static", 0.9, f"stationary, {rom*100:.0f} cm vertical"

    return "unknown", 0.2, (f"speed {spd:.2f} m/s, {rom*100:.0f} cm vertical — "
                            f"no rule matched")


def classify_trial(exp_dir: str, body_mass: Optional[float] = None,
                   cfg: Optional[MocapConfig] = None):
    """Classify one exported trial folder.

    Returns ``(label, confidence, reason, TrialFeatures)``.

        from bioscout.movement_detector import classify_trial
        label, conf, why, feats = classify_trial(
            "simulations/021/session1/2_experimental/RunG3", body_mass=61.3)
    """
    cfg = cfg or MocapConfig()
    feats = extract_trial_features(exp_dir, body_mass, cfg)
    try:
        segs = segment_trial(exp_dir, body_mass, cfg)
    except Exception:
        segs = []
    try:
        w = detect_window(exp_dir, body_mass, cfg)
        feats.window_grf = w["grf"]
        feats.window_markers = w["markers"]
        feats.window_emg = w["emg"]
        feats.window_consensus = w["consensus"]
    except Exception:
        pass                              # window is advisory, never fatal
    label, conf, why = classify_features(feats, cfg)

    # The whole-trial label should name what the trial was FOR, not whatever
    # filled the most seconds. SLSback_post1 is 7.5 s of which 1.8 s is the
    # single-leg squat and the rest is standing either side of it; scoring by
    # duration called the trial a squat. Prefer the most specific task present,
    # breaking ties by duration.
    if segs:
        rank = {"cut": 7, "squat_jump": 6, "single_leg_squat": 5, "jump": 4,
                "squat": 3, "running": 2, "walking": 2,
                "single_leg_stance": 1, "static": 0}
        best = max(segs, key=lambda g: (rank.get(g.task, 0), g.duration))
        if rank.get(best.task, 0) > rank.get(label, 0):
            label = best.task
            why = f"{best.reason} ({best.duration:.2f}s of {len(segs)} tasks)"
    return label, conf, why, feats

# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

#: One colour per task, stable across every figure bioscout draws.
TASK_COLOURS = {
    "static": "#B0BEC5", "single_leg_stance": "#90CAF9",
    "squat": "#66BB6A", "single_leg_squat": "#26A69A",
    "jump": "#FFA726", "squat_jump": "#FB8C00", "running": "#EF5350",
    "walking": "#AB47BC", "cut": "#EC407A",
    "emg_only": "#CFD8DC", "unknown": "#ECEFF1",
}


def plot_trial_tasks(exp_dir: str, out_png: str, body_mass: Optional[float] = None,
                     cfg: Optional[MocapConfig] = None, segments=None) -> Optional[str]:
    """Vertical GRF + pelvis height for one trial, with the tasks shaded.

    Lives here rather than in a project's test folder so the CLI
    (``bioscout --classifier``) and any project test draw the SAME figure — a
    QC plot that differs between the tool and the test is worse than none.

    Returns the path written, or None when the trial has nothing to draw.
    """
    cfg = cfg or MocapConfig()
    segs = segments if segments is not None else segment_trial(exp_dir, body_mass, cfg)
    if not segs:
        return None
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    trial = os.path.basename(os.path.normpath(exp_dir))
    fig = plt.figure(figsize=(16, 9))
    gs = fig.add_gridspec(4, 2, height_ratios=[0.42, 0.42, 2, 1.2],
                          width_ratios=[3, 1.5], hspace=.55, wspace=.22)
    axr = fig.add_subplot(gs[0, 0])          # task ribbon
    axq = fig.add_subplot(gs[1, 0], sharex=axr)   # phase ribbon
    axf = fig.add_subplot(gs[2, 0], sharex=axr)
    axp = fig.add_subplot(gs[3, 0], sharex=axr)
    axt = fig.add_subplot(gs[:2, 1])         # sagittal
    axn = fig.add_subplot(gs[2:, 1])         # frontal

    # --- vertical GRF ---
    gm = os.path.join(exp_dir, "grf.mot")
    if os.path.exists(gm):
        gt, gcols = read_grf(gm)
        # Foot per plate from the CoP, NOT from GRF.xml — that mapping is wrong
        # often enough to matter (Run_baselineB2 calls both plates "right"
        # while the first contact's CoP is 2.5 cm from the LEFT foot).
        _cf = contact_feet(exp_dir, body_mass, cfg)
        detected = {}
        for _c in _cf:
            detected.setdefault(_c["plate"], _c["side"])
        xml_sides = _plate_sides(os.path.join(exp_dir, "GRF.xml"))
        foot_colour = {"l": "tab:orange", "r": "tab:green"}
        vy = {c: v for c, v in gcols.items() if c.endswith("_vy")}
        if gt.size and vy:
            for c, v in sorted(vy.items()):
                pre = c[:-3]
                sd = detected.get(pre)
                was = xml_sides.get(pre[:-0] + "_v") or xml_sides.get(pre + "_v")
                if sd:
                    tag = f"  ({sd.upper()} foot"
                    tag += ", GRF.xml said %s)" % was.upper() if was and was != sd else ")"
                else:
                    tag = "  (no contact)"
                axf.plot(gt, v, lw=1.2 if sd else 1,
                         ls="-" if sd else ":", alpha=.95 if sd else .35,
                         color=foot_colour.get(sd) if sd else "grey",
                         label=f"{c}{tag}")
            total = np.nansum(np.stack(list(vy.values()), axis=0), axis=0)
            axf.plot(gt, total, lw=1.6, color="k", alpha=.7, label="total")
            if body_mass:
                bw = float(body_mass) * cfg.gravity
                axf.axhline(bw, ls="--", c="grey", lw=.8)
                axf.text(gt[0], bw, " 1 BW", fontsize=7, va="bottom", color="grey")
    axf.set_ylabel("vertical GRF (N)")
    axf.legend(fontsize=6.5, ncol=3, loc="upper center", framealpha=.9, borderpad=.3)

    # --- pelvis height ---
    trc = os.path.join(exp_dir, "marker_experimental.trc")
    if os.path.exists(trc):
        try:
            t, mk, _ = read_trc(trc)
            pel = _pelvis_centre(mk)
            if pel is not None:
                axp.plot(t, pel[:, 1], lw=1.2, color="tab:blue")
        except Exception:
            pass
    axp.set_ylabel("pelvis height (m)")
    axp.set_xlabel("time (s)")
    # Only the bottom time axis carries tick labels — sharex repeats them on
    # every panel otherwise, which reads as three different axes.
    for _ax in (axr, axq, axf):
        plt.setp(_ax.get_xticklabels(), visible=False)

    # --- phase ribbon -------------------------------------------------------
    # The sub-phases are the point of a squat jump — descent / hold /
    # concentric / air_time — and a single task block hides them.
    PHASE_COLOURS = {"descent": "#81C784", "hold": "#FFD54F",
                     "concentric": "#4DB6AC", "air_time": "#FF8A65",
                     "landing": "#BA68C8", "swing": "#B0BEC5"}
    _any_phase = False
    for g in segs:
        for ph in g.phases:
            _any_phase = True
            _c = PHASE_COLOURS.get(ph.phase, "#CFD8DC")
            _y0 = 0.55 if ph.side == "left" else (0.05 if ph.side == "right" else 0.30)
            _h = 0.40 if ph.side else 0.90
            _yy = _y0 if ph.side else 0.05
            axq.add_patch(plt.Rectangle((ph.t_start, _yy), ph.duration, _h,
                                        color=_c, alpha=.85, lw=0))
            if ph.duration > 0.25:
                axq.text(ph.t_start + ph.duration / 2, _yy + _h / 2,
                         f"{ph.phase}{(' ' + ph.side[0].upper()) if ph.side else ''}",
                         ha="center", va="center", fontsize=6.5)
    axq.set_ylim(0, 1); axq.set_yticks([])
    axq.set_ylabel("phases", fontsize=8, rotation=0, ha="right", va="center")
    for sp in ("top", "right", "left"):
        axq.spines[sp].set_visible(False)
    if not _any_phase:
        axq.text(.5, .5, "no sub-phases", ha="center", va="center",
                 fontsize=7, color="grey", transform=axq.transAxes)

    # --- task ribbon + shading ---
    for g in segs:
        axr.axvspan(g.t_start, g.t_end, color=TASK_COLOURS.get(g.task, "#ECEFF1"),
                    alpha=.85, lw=0)
        axr.axvline(g.t_start, color="w", lw=1)
        # Name the leg / direction on the ribbon: "cut right" is the finding,
        # "cut" alone makes you open the CSV to learn which way.
        _name = g.task + (f" {g.side}" if g.side else "")
        span = g.t_end - g.t_start
        if span > 0.8:
            axr.text((g.t_start + g.t_end) / 2, 0.5,
                     f"{_name}\n{g.duration:.2f}s", ha="center", va="center",
                     fontsize=7.5)
        else:
            axr.annotate(f"{_name} {g.duration:.2f}s",
                         xy=((g.t_start + g.t_end) / 2, 1.0), xytext=(0, 6),
                         textcoords="offset points", ha="center", va="bottom",
                         fontsize=6.5, rotation=30)
    axr.set_ylim(0, 1); axr.set_yticks([])
    axr.set_ylabel("tasks", fontsize=8, rotation=0, ha="right", va="center")
    for sp in ("top", "right", "left"):
        axr.spines[sp].set_visible(False)
    for ax in (axf, axp):
        for g in segs:
            ax.axvspan(g.t_start, g.t_end, color=TASK_COLOURS.get(g.task, "#ECEFF1"),
                       alpha=.22, lw=0)
            ax.axvline(g.t_start, color="k", lw=.5, alpha=.35)
        ax.grid(alpha=.25)

    # --- marker trajectories, sagittal plane -------------------------------
    # Every marker as a hairline path with a dot at the LAST frame, so the
    # trial reads as a movement rather than as three time series. The pelvis is
    # drawn thick because it is what the task rules are computed from.
    try:
        if os.path.exists(trc):
            t2, mk2, _ = read_trc(trc)
            for nm, arr in mk2.items():
                if arr.shape[0] < 2:
                    continue
                x, y = arr[:, 0], arr[:, 1]      # X = progression, Y = vertical
                if not (np.isfinite(x).any() and np.isfinite(y).any()):
                    continue
                axt.plot(x, y, lw=0.35, alpha=.55, color="#78909C",
                         solid_capstyle="round")
                fin = np.flatnonzero(np.isfinite(x) & np.isfinite(y))
                if fin.size:
                    axt.plot(x[fin[-1]], y[fin[-1]], "o", ms=4.5,
                             color="#37474F", zorder=3)
            pel2 = _pelvis_centre(mk2)
            if pel2 is not None:
                px_, py_ = pel2[:, 0], pel2[:, 1]
                axt.plot(px_, py_, lw=2.6, color="tab:blue", alpha=.95,
                         label="pelvis", zorder=4)
                fin = np.flatnonzero(np.isfinite(px_) & np.isfinite(py_))
                if fin.size:
                    axt.plot(px_[fin[-1]], py_[fin[-1]], "o", ms=8,
                             color="tab:blue", zorder=5)
            axt.set_aspect("equal", adjustable="box")
            axt.set_xlabel("progression X (m)")
            axt.set_ylabel("vertical Y (m)")
            axt.set_title("markers — sagittal (X-Y)\ndots = final frame",
                          fontsize=9, pad=6)
            axt.grid(alpha=.25)
            axt.legend(fontsize=7, loc="upper right")

            # --- frontal plane: mediolateral Z against vertical Y ----------
            for nm, arr in mk2.items():
                if arr.shape[0] < 2:
                    continue
                z, y = arr[:, 2], arr[:, 1]
                if not (np.isfinite(z).any() and np.isfinite(y).any()):
                    continue
                axn.plot(z, y, lw=0.35, alpha=.55, color="#78909C",
                         solid_capstyle="round")
                fin = np.flatnonzero(np.isfinite(z) & np.isfinite(y))
                if fin.size:
                    axn.plot(z[fin[-1]], y[fin[-1]], "o", ms=4.5,
                             color="#37474F", zorder=3)
            if pel2 is not None:
                pz_, py2_ = pel2[:, 2], pel2[:, 1]
                axn.plot(pz_, py2_, lw=2.6, color="tab:blue", alpha=.95,
                         label="pelvis", zorder=4)
                fin = np.flatnonzero(np.isfinite(pz_) & np.isfinite(py2_))
                if fin.size:
                    axn.plot(pz_[fin[-1]], py2_[fin[-1]], "o", ms=8,
                             color="tab:blue", zorder=5)
            axn.set_aspect("equal", adjustable="box")
            axn.set_xlabel("mediolateral Z (m)")
            axn.set_ylabel("vertical Y (m)")
            axn.set_title("markers — frontal (Z-Y)", fontsize=9, pad=6)
            axn.grid(alpha=.25)
            axn.legend(fontsize=7, loc="upper right")
    except Exception as _e:
        for _ax in (axt, axn):
            _ax.text(.5, .5, f"trajectories unavailable\n{type(_e).__name__}",
                     ha="center", va="center", fontsize=8, transform=_ax.transAxes)

    fig.suptitle(f"{trial} — {len(segs)} task(s) detected", fontsize=11)
    os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
    fig.savefig(out_png, dpi=150)
    plt.close(fig)
    return out_png
