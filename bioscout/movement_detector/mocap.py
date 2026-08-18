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
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np


MOCAP_TASK_LABELS = (
    "emg_only",
    "static",
    "single_leg_stance",
    "squat_jump",
    "deadlift",
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
    # Rigid-cluster marker sets carry no ASIS at all — a powerlifting set
    # cannot, because a loaded bar and a belt sit where those markers would go.
    # A sacral cluster is a fine stand-in here: every rule downstream uses the
    # pelvis for RELATIVE vertical excursion and horizontal travel, never for
    # an absolute anatomical height, so a constant offset changes nothing.
    ("SACROL", "SACR2", "SACR3"),
    ("SACR2", "SACR3"),
    ("SACROL",),
    ("BELTOL", "BELT2", "BELT3"),
)


@dataclass
class MocapConfig:
    """Thresholds for :func:`classify_trial`, all in SI units.

    Defaults were set against FAIS running / squat / single-leg-squat / jump
    captures (200 Hz, 59 markers, 4 force plates) and are deliberately loose —
    the classifier is meant to catch gross mislabelling, not to adjudicate
    borderline technique.
    """
    # --- laboratory conventions -------------------------------------------
    # These are PROJECT facts, not algorithm parameters, and every one of them
    # was previously hard-coded here: Y meant vertical, the pelvis meant
    # LASI/RASI, and a foot marker was anything whose name contained "HEE" or
    # "TOE". That works until a project uses a different convention — a
    # powerlifting markerset has no ASIS marker at all, because a loaded bar
    # and a belt occupy that space — and then the detector silently returns
    # nothing rather than saying what it could not find. A project states these
    # once in its settings and passes them in; see MocapConfig.from_settings.
    vertical_axis: str = "Y"
    ap_axis: str = "X"                # anterior-posterior
    lateral_axis: str = "Z"           # mediolateral
    #: Markers averaged to give the pelvis centre. None = try _PELVIS_SETS.
    pelvis_markers: Optional[Sequence[str]] = None
    #: Markers averaged to give each foot. None = match on name fragments.
    left_foot_markers: Optional[Sequence[str]] = None
    right_foot_markers: Optional[Sequence[str]] = None
    #: Markers on the barbell, averaged to give the bar centre. A project with
    #: no bar leaves this None and every bar rule switches itself off.
    bar_markers: Optional[Sequence[str]] = None
    # A bar that never moves is not being lifted — on a bodyweight squat the
    # markers sit on a bar left in the rack and their vertical range is 0 mm.
    # Below this the bar is ignored rather than reported as a 0 cm lift.
    bar_min_travel_m: float = 0.10
    # Where the bar starts within its own vertical range separates the two
    # barbell lifts, and separates them cleanly: on this session a deadlift
    # starts at 0% of that range (the bar is on the floor and the lifter comes
    # down to it) and a back squat at 88% (the bar starts on the lifter and
    # goes down with them). Below this fraction the lift is a deadlift.
    deadlift_start_frac: float = 0.33
    # How far back before the bar leaves the floor to look for the descent the
    # lifter made to reach it. Longer than a squat descent because a deadlift
    # setup includes walking in, gripping and bracing.
    deadlift_setup_max_s: float = 5.0
    # How much of the lockout belongs to the lift. The pull is the movement;
    # standing holding the bar afterwards is not, and on these captures the
    # lockout runs 2.3 s, which would put two thirds of the "deadlift" into a
    # phase where nothing moves. Reported window = start of the pull to this
    # far into the lockout, whichever comes first.
    deadlift_lockout_s: float = 0.5

    # --- force plate ---
    # A plate counts as loaded above this fraction of body weight. 0.10 BW is
    # well clear of baseline drift and crosstalk while still catching the light
    # contact at the start of a squat descent.
    load_bw: float = 0.10
    # Once a contact is CONFIRMED above ``load_bw``, its start and end are
    # walked outward to this much lower fraction of BW. Detection needs a
    # threshold high enough to ignore crosstalk and baseline drift; the
    # reported WINDOW needs one low enough to include the loading ramp. On
    # FAIS RunA2 the first contact goes 36 N -> 768 N inside one 10 ms frame,
    # so a 0.10 BW (61 N) edge cuts the whole foot-strike frame off the front
    # of the task and the shaded band visibly starts after the force rise.
    contact_edge_bw: float = 0.01
    # Total vertical GRF below this fraction of BW = airborne.
    flight_bw: float = 0.10
    # A flight phase must last at least this long to be real. Measured on both
    # projects, with the marker corroboration in place:
    #     walking artefact   0.06 s   (Walking_02, a 1.36 m/s walk)
    #     slowest real run   0.11 s   (FAIS Run_baselineA1, 5.8 m/s)
    #     squat jump         0.39 s
    # 0.08 sits in the 2x gap between the first two. At the old 0.05 the walk
    # cleared the bar and was reported as running.
    min_flight_s: float = 0.08
    # How long either side of a zero-force interval to look for real load
    # before believing it was flight rather than the participant simply
    # standing off the plates. Half a second covers a running stride's contact.
    flight_context_s: float = 0.60

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

    # A cut does not begin when the cutting foot lands. It begins when the
    # CONTRALATERAL foot leaves the ground: the flight between the two is when
    # the body commits to the turn, and starting the window at touchdown opens
    # the task mid-manoeuvre. The window then closes at the cutting foot's own
    # foot off, so it spans contra foot off -> ipsi foot off.
    cut_from_contra_off: bool = True
    # How far back to look for that contralateral foot off. Beyond this the
    # previous step is a separate stride, not the lead-in to this plant.
    cut_lead_max_s: float = 0.50

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

    def axes(self) -> Tuple[int, int, int]:
        """(vertical, anterior-posterior, lateral) column indices into a TRC."""
        _AX = {"X": 0, "Y": 1, "Z": 2}
        return (_AX.get(str(self.vertical_axis).upper(), 1),
                _AX.get(str(self.ap_axis).upper(), 0),
                _AX.get(str(self.lateral_axis).upper(), 2))

    def horizontal(self) -> List[int]:
        """The two non-vertical column indices, anterior-posterior first."""
        _iv, _ia, _il = self.axes()
        return [_ia, _il]

    @classmethod
    def from_settings(cls, settings=None, **overrides) -> "MocapConfig":
        """Build a config from a project's settings object.

        Reads the names a bioscout project already declares — ``markerset``,
        ``right_foot_markers``, ``trc_vertical_axis`` and friends — so the lab
        convention is stated once, in the project, instead of being re-guessed
        from marker names inside the detector. Anything absent keeps its
        default, so passing a partial settings object is fine and passing none
        gives exactly the old behaviour.

            from bioscout.movement_detector import MocapConfig
            cfg = MocapConfig.from_settings(settings.BatchSettings)
        """
        _MAP = {
            "vertical_axis": ("trc_vertical_axis", "vertical_axis"),
            "ap_axis": ("trc_ap_axis", "ap_axis"),
            "lateral_axis": ("trc_lateral_axis", "lateral_axis"),
            "pelvis_markers": ("pelvis_markers",),
            "left_foot_markers": ("left_foot_markers",),
            "right_foot_markers": ("right_foot_markers",),
            "bar_markers": ("bar_markers", "barbell_markers"),
        }
        kw = {}
        if settings is not None:
            _get = (settings.get if isinstance(settings, dict)
                    else lambda k, d=None: getattr(settings, k, d))
            for field_name, aliases in _MAP.items():
                for alias in aliases:
                    val = _get(alias, None)
                    if val:
                        kw[field_name] = val
                        break
        kw.update(overrides)
        return cls(**kw)

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
    # A trial may START with the participant already down in the squat — on
    # these captures SJ1 opens 31 cm, SJ_post3 16 cm and SJ_post4 16 cm below
    # where they finish. Taking the head of the trial as "standing" then makes
    # depth ~0 for the whole squat and the trial reads as static. If the
    # settled height AFTER landing exceeds the opening height by this much,
    # the trial started low and the post-landing stance is the reference.
    started_low_m: float = 0.06

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
        if not line.strip():
            continue
        # SPLIT ON TABS AND KEEP THE EMPTY CELLS. A .trc marks an occluded
        # marker with three empty fields, and `line.split()` — splitting on
        # whitespace — deletes them, so every marker AFTER the gap shifts three
        # columns left and is read as a different marker. On a trial where most
        # markers have gaps that is most frames, and nothing downstream can tell:
        # the pelvis quietly becomes whichever marker slid into its columns, the
        # speed comes out at 0.45 m/s for a 5.8 m/s sprint, and the trial is
        # classified "static". The row is a fixed-width record; treat it as one.
        tok = line.rstrip("\r\n").split("\t") if "\t" in line else line.split()
        if len(tok) < 3:
            continue
        vals = []
        for x in tok:
            x = x.strip()
            if x in ("", "nan", "NaN", "NAN"):
                vals.append(np.nan)
            else:
                try:
                    vals.append(float(x))
                except ValueError:
                    vals.append(np.nan)
        rows.append(vals)
    if not rows:
        return np.array([]), {}, rate

    width = max(len(r) for r in rows)
    arr = np.full((len(rows), width), np.nan)
    for i, r in enumerate(rows):
        arr[i, :len(r)] = r
    # Drop frames with no marker at all — the blank padding an export leaves
    # when the capture is longer than the tracked segment. Keeping them does
    # not add information, it just stretches every duration and rate estimate
    # over time in which nothing was measured.
    if arr.shape[1] > 2:
        _any = np.isfinite(arr[:, 2:]).any(axis=1)
        if _any.any() and not _any.all():
            _lo = int(np.argmax(_any))
            _hi = int(len(_any) - np.argmax(_any[::-1]))
            arr = arr[_lo:_hi]

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

def _pelvis_centre(markers: Dict[str, np.ndarray],
                   cfg: Optional["MocapConfig"] = None) -> Optional[np.ndarray]:
    """Mean of whichever pelvis marker set is present, or None.

    A marker can be listed in the TRC header and still be entirely occluded, so
    "the column exists" is not "the column has data". Averaging an all-NaN
    stack warns and yields NaN; require at least one finite sample per set
    instead, and fall through to the next convention when there is none.
    """
    _sets = _PELVIS_SETS
    if cfg is not None and cfg.pelvis_markers:
        # The project said which markers these are; do not guess.
        _sets = (tuple(cfg.pelvis_markers),) + _PELVIS_SETS
    for names in _sets:
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


def _both_feet_lifted(markers: Dict[str, np.ndarray], t: np.ndarray,
                      cfg: "MocapConfig") -> Optional[np.ndarray]:
    """Boolean series: BOTH feet clear of their own floor level.

    The marker second opinion on flight. Force plates cannot tell "airborne"
    from "standing next to the plate", and on a walking trial the difference
    is the whole classification: Walking_02 reads 0.58 s of zero force as the
    participant walks off the plates, which promoted a 1.36 m/s walk to a run.
    The feet are unambiguous — over that same interval they are both off the
    ground for 0.05 s, which is nobody's flight phase.
    """
    if not markers or t is None or not np.size(t):
        return None
    both = None
    for key in ("L", "R"):
        h = _foot_height(markers, key, cfg)
        if h is None or not np.isfinite(h).any():
            return None
        floor = float(np.nanpercentile(h[np.isfinite(h)], 5))
        lift = np.nan_to_num(h - floor) > cfg.foot_lift_m
        both = lift if both is None else (both & lift)
    return both


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
            pel = _pelvis_centre(markers, cfg)
            if pel is not None:
                _iv = cfg.axes()[0]
                horiz = pel[:, cfg.horizontal()]
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
                vert = pel[:, _iv]
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
            # Zero force is only flight if the FEET agree they are off the
            # ground. See _both_feet_lifted.
            # markers/time only exist when this trial HAS a TRC — an
            # EMG-only capture has neither, and reaching for them here is
            # what turned 41 emg_only trials into UnboundLocalError.
            _mk_ = locals().get("markers") or {}
            _tm_ = locals().get("time")
            _bl = _both_feet_lifted(_mk_, _tm_, cfg) if _mk_ is not None else None
            if _bl is not None and _tm_ is not None and np.size(_tm_):
                _blg = np.interp(gt, _tm_, _bl.astype(float)) > 0.5
                air = air & _blg
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
    # Turn angle for a cut, in degrees (0 = carried straight on). Kept as a
    # field rather than left inside ``reason`` so the figure, the CSV and the
    # YAML can all state it without parsing prose back out of a sentence.
    angle_deg: Optional[float] = None
    # Which way a cut turned. Kept separate from ``side`` because they are
    # different facts and were being conflated: a cut to the RIGHT can be
    # planted off either leg, and reporting the turn direction in ``side``
    # made a right turn off a left plant read as a right-leg task.
    direction: Optional[str] = None
    # Jump height in metres, by two independent routes: ``jump_height_m`` from
    # the markers (peak pelvis minus pelvis at take-off) and
    # ``jump_height_grf_m`` from the net vertical impulse. They estimate the
    # same quantity from different instruments, so a disagreement between them
    # is a signal about the trial, not noise to be averaged away.
    jump_height_m: Optional[float] = None
    jump_height_grf_m: Optional[float] = None
    flight_time_s: Optional[float] = None
    # Bar path, present only on barbell lifts. See :func:`bar_metrics`.
    bar_rom_m: Optional[float] = None
    bar_ap_drift_m: Optional[float] = None
    bar_path_deviation_m: Optional[float] = None
    bar_peak_velocity_ms: Optional[float] = None
    bar_mean_concentric_velocity_ms: Optional[float] = None

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


def _foot_markers(markers: Dict[str, np.ndarray], side: str,
                  cfg: Optional["MocapConfig"] = None) -> List[str]:
    """Names of one foot's markers — from the project if it said, else by name.

    ``side`` is "L" or "R". The name-fragment fallback covers the conventional
    sets; a project with its own naming states the list in its settings.
    """
    if cfg is not None:
        _named = (cfg.left_foot_markers if side.upper().startswith("L")
                  else cfg.right_foot_markers)
        if _named:
            _hit = [m for m in _named if m in markers]
            if _hit:
                return _hit
    return [m for m in markers
            if m.upper().startswith(side.upper())
            and any(k in m.upper()
                    for k in ("HEE", "MT1", "MT2", "MT5", "TOE",
                              "FMH", "SMH", "VMH"))]


def _foot_height(markers: Dict[str, np.ndarray], side: str,
                 cfg: Optional["MocapConfig"] = None):
    """Mean vertical position of one foot's markers, or None."""
    names = _foot_markers(markers, side, cfg)
    if not names:
        return None
    _iv = (cfg or MocapConfig()).axes()[0]
    stack = np.stack([markers[n][:, _iv] for n in names], axis=0)
    if not np.isfinite(stack).any():
        return None                       # every foot marker occluded
    out = np.full(stack.shape[1], np.nan)
    ok = np.isfinite(stack).any(axis=0)
    if ok.any():
        with np.errstate(invalid="ignore"):
            out[ok] = np.nanmean(stack, axis=0)[ok]
    return out


def _smooth_runs(labels: List[str], t: np.ndarray, min_s: float,
                 min_by_label: Optional[Dict[str, float]] = None) -> List[str]:
    """Absorb runs shorter than ``min_s`` into whichever neighbour is longer.

    ``min_by_label`` overrides the minimum for particular labels. Flight needs
    one: every squat jump in this session is airborne for 0.40-0.46 s, which
    straddles ``min_task_s`` (0.40), so the same movement had its jump kept on
    some trials and absorbed into the neighbouring stance on others. A flight
    phase is short by nature and is governed by ``min_flight_s`` instead.
    """
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
            _lim = (min_by_label or {}).get(lab, min_s)
            if float(t[b] - t[a]) >= _lim or len(runs) == 1:
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




def _grow_mask(v: np.ndarray, mask: np.ndarray, thr_edge: float) -> np.ndarray:
    """Extend every True run in ``mask`` out while ``v`` stays above ``thr_edge``.

    Two thresholds, two jobs. The high one decides WHETHER a contact happened
    — it has to clear crosstalk from the neighbouring plate and baseline
    drift. The low one decides WHEN it started and ended — it only has to
    clear the noise floor. Using the high threshold for both is what made the
    task shading start after the force curve had already left the floor.
    """
    out = np.zeros(len(mask), dtype=bool)
    n = len(mask)
    i = 0
    while i < n:
        if not mask[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and mask[j + 1]:
            j += 1
        a, b = i, j
        while a > 0 and np.isfinite(v[a - 1]) and v[a - 1] > thr_edge:
            a -= 1
        while b < n - 1 and np.isfinite(v[b + 1]) and v[b + 1] > thr_edge:
            b += 1
        out[a:b + 1] = True
        i = j + 1
    return out


def _gait_event_times(exp_dir: str, contacts: Optional[List[dict]] = None,
                      cfg: Optional["MocapConfig"] = None
                      ) -> List[Tuple[str, str, float]]:
    """Foot strikes and foot offs per leg — plates first, then markers.

    Returns ``[(side, "strike"|"off", time), ...]`` sorted by time. A plate
    contact is ground truth where it exists, so its ``t_on``/``t_off`` are
    taken first; a marker-derived event within half a stride of one is dropped
    as the same event seen twice. The marker events are what fill in the
    strides the plates never saw, which on a straight run is most of them.
    """
    cfg = cfg or MocapConfig()
    out: List[Tuple[str, str, float]] = []
    for c in (contacts or []):
        sd = c.get("side") or ""
        if sd in ("l", "r"):
            out.append((sd, "strike", float(c["t_on"])))
            out.append((sd, "off", float(c["t_off"])))
    tol = max(cfg.min_stride_s * 0.5, 0.05)
    try:
        mev = foot_events_from_markers(exp_dir, cfg) or {}
    except Exception:
        mev = {}
    _t0 = _t1 = None
    _edge = 0.03
    try:
        _tt_all, _, _ = read_trc(os.path.join(exp_dir, "marker_experimental.trc"))
        if _tt_all.size > 1:
            _t0, _t1 = float(_tt_all[0]), float(_tt_all[-1])
    except Exception:
        pass
    for sd, ev in mev.items():
        for kind, key in (("strike", "contact"), ("off", "off")):
            for tt in ev.get(key, []):
                # An "event" on the first or last frame is the trial window
                # opening or closing, not the foot doing anything.
                if _t0 is not None and (float(tt) - _t0 < _edge
                                        or _t1 - float(tt) < _edge):
                    continue
                if not any(s == sd and k == kind and abs(t0 - float(tt)) < tol
                           for s, k, t0 in out):
                    out.append((sd, kind, float(tt)))

    # One leg cannot strike twice inside half a stride. Two plates sometimes
    # both claim the same footfall (RunA2: plate 1 and plate 2 are both called
    # left, 20 ms apart, with a 2.4 cm CoP margin on the second), which would
    # otherwise draw two lines for one event. Collapse each cluster to its
    # outer edge: the earliest strike, the latest off — the widest window the
    # data supports, which is the same principle as growing the contact.
    out.sort(key=lambda e: e[2])
    merged: List[Tuple[str, str, float]] = []
    for sd, kind, tt in out:
        prev = next((i for i in range(len(merged) - 1, -1, -1)
                     if merged[i][0] == sd and merged[i][1] == kind
                     and abs(merged[i][2] - tt) < tol), None)
        if prev is None:
            merged.append((sd, kind, tt))
        elif kind == "off":
            merged[prev] = (sd, kind, max(merged[prev][2], tt))
    merged.sort(key=lambda e: e[2])
    return merged


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
        h = _foot_height(markers, key, cfg)
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

    _iv, _ia, _il = cfg.axes()
    feet = {}
    for side, key in (("l", "L"), ("r", "R")):
        names = _foot_markers(markers, key, cfg)
        if names:
            feet[side] = np.nanmean(np.stack([markers[n] for n in names], axis=0), axis=0)
    if not feet:
        return []

    total = np.nansum(np.stack([v for c, v in gcols.items()
                                if c.endswith("_vy")], axis=0), axis=0) \
        if any(c.endswith("_vy") for c in gcols) else np.zeros(gt.size)
    thr = (cfg.load_bw * float(body_mass) * cfg.gravity) if body_mass \
        else cfg.load_bw * float(np.nanmax(total) or 1.0)
    thr_edge = (cfg.contact_edge_bw * float(body_mass) * cfg.gravity) if body_mass \
        else cfg.contact_edge_bw * float(np.nanmax(total) or 1.0)

    out = []
    plates = sorted({c.rsplit("_", 1)[0] for c in gcols if c.endswith("_vy")})
    for pre in plates:
        vy = gcols.get(pre + "_vy")
        if vy is None or not np.isfinite(vy).any() or float(np.nanmax(vy)) < thr:
            continue
        # Confirm with the high threshold, then grow the window out to the
        # loading ramp with the low one.
        on = _grow_mask(vy, vy > thr, thr_edge)
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
            # CoP columns are named px/py/pz in the OpenSim frame; pick the
            # two that are horizontal under this project's convention.
            _pn = {0: "_px", 1: "_py", 2: "_pz"}
            px, pz = gcols.get(pre + _pn[_ia]), gcols.get(pre + _pn[_il])
            side, margin = "", float("nan")
            if px is not None and pz is not None and np.isfinite(px[k]) and np.isfinite(pz[k]):
                cop = np.array([px[k], pz[k]])
                j = int(np.argmin(np.abs(t - gt[k])))
                d = {}
                for sd, arr in feet.items():
                    if j < len(arr) and np.isfinite(arr[j][_ia]) \
                            and np.isfinite(arr[j][_il]):
                        d[sd] = float(np.linalg.norm(
                            np.array([arr[j][_ia], arr[j][_il]]) - cop))
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


def _quiet_body_weight(gt: np.ndarray, total: np.ndarray, nominal: float,
                       exclude: Optional[Tuple[float, float]] = None,
                       win: float = 0.4) -> float:
    """Body weight as the PLATES measure it, from the quietest standing window.

    The impulse route integrates ``F - BW``, so a constant error in BW is
    multiplied by the length of the integration window. It matters: on these
    captures the plates read 607-618 N at quiet stance while the session's
    entered mass says 601 N, and that 2.6% gap doubled the computed jump
    height when integrated over a two-second task. Every force-plate jump
    protocol measures body weight from the trial itself for this reason.

    ``exclude`` brackets the movement, so the search cannot settle on the
    bottom of the squat — which is genuinely low-variance but is not standing.
    Returns ``nominal`` unchanged when no usable window exists.
    """
    if gt is None or total is None or not np.size(gt) or not nominal:
        return nominal
    dt = float(np.median(np.diff(gt))) if np.size(gt) > 1 else 0.0
    w = max(3, int(win / dt)) if dt > 0 else 3
    if len(total) < w + 1:
        return nominal
    v = np.nan_to_num(np.asarray(total, dtype=float))
    keep = np.ones(len(v), bool)
    if exclude:
        keep &= ~((gt >= exclude[0] - 0.1) & (gt <= exclude[1] + 0.6))
    c1 = np.cumsum(np.insert(v, 0, 0.0))
    c2 = np.cumsum(np.insert(v * v, 0, 0.0))
    ck = np.cumsum(np.insert(keep.astype(int), 0, 0))
    mean = (c1[w:] - c1[:-w]) / w
    var = (c2[w:] - c2[:-w]) / w - mean ** 2
    good = ((ck[w:] - ck[:-w]) == w) & (np.abs(mean - nominal) < 0.30 * nominal)
    if not good.any():                     # movement fills the trial
        good = np.abs(mean - nominal) < 0.30 * nominal
    if not good.any():
        return nominal
    return float(mean[int(np.flatnonzero(good)[np.argmin(var[good])])])


def jump_height(t: np.ndarray, vert: np.ndarray,
                t_takeoff: float, t_land: float,
                gt: Optional[np.ndarray] = None,
                total: Optional[np.ndarray] = None,
                body_mass: Optional[float] = None,
                t_start: Optional[float] = None,
                cfg: Optional["MocapConfig"] = None) -> Dict[str, float]:
    """Jump height by three independent routes, all in metres.

    * **impulse** — the net vertical impulse from ``t_start`` (where the body
      is at rest, i.e. the start of the task) to take-off gives the take-off
      velocity; height is then ``v**2 / 2g``. This is the reference method,
      and the only one that uses the force plates.
    * **flight**  — ``g * t_flight**2 / 8`` from the airborne duration alone.
      Needs no mass and no marker, so it survives trials where either is bad,
      but it assumes take-off and landing heights are equal — which they are
      not if the participant lands in a deeper crouch than they left.
    * **marker**  — peak pelvis height minus pelvis height at take-off. This
      is the same quantity the impulse route estimates, measured directly.

    Three routes rather than one because they fail differently: a mis-entered
    body mass moves the impulse estimate and leaves the other two untouched,
    an occluded pelvis moves the marker estimate alone. Agreement between them
    is the check that any of them is trustworthy.
    """
    cfg = cfg or MocapConfig()
    g = cfg.gravity
    out = {"impulse_m": float("nan"), "flight_m": float("nan"),
           "marker_m": float("nan"), "takeoff_velocity_ms": float("nan"),
           "body_weight_n": float("nan"),
           "flight_time_s": float(max(0.0, float(t_land) - float(t_takeoff)))}

    tf = out["flight_time_s"]
    if tf > 0:
        out["flight_m"] = g * tf * tf / 8.0

    if t is not None and np.size(t) and vert is not None and np.size(vert):
        sel = (t >= t_takeoff) & (t <= t_land)
        if sel.any():
            j = int(np.argmin(np.abs(t - t_takeoff)))
            y0 = float(vert[j]) if j < len(vert) else float("nan")
            pk = float(np.nanmax(vert[sel]))
            if np.isfinite(y0) and np.isfinite(pk):
                out["marker_m"] = max(0.0, pk - y0)

    if (gt is not None and total is not None and body_mass
            and t_start is not None):
        # Weight as the plates read it, not as the session file states it.
        bw = _quiet_body_weight(gt, total, float(body_mass) * g,
                                exclude=(float(t_start), float(t_land)))
        out["body_weight_n"] = bw
        sel = (gt >= float(t_start)) & (gt <= float(t_takeoff))
        if int(sel.sum()) >= 3:
            m = bw / g
            f = np.nan_to_num(total[sel]) - bw
            x = gt[sel]
            # trapezoid by hand: np.trapz/np.trapezoid changed name across the
            # numpy 2 boundary and this has to run on both.
            v = float(np.sum((f[:-1] + f[1:]) * 0.5 * np.diff(x)) / m)
            out["takeoff_velocity_ms"] = v
            if v > 0:
                out["impulse_m"] = v * v / (2.0 * g)
    return out


def bar_centre(markers: Dict[str, np.ndarray],
               cfg: Optional["MocapConfig"] = None) -> Optional[np.ndarray]:
    """Mean of the barbell markers, or None when the project has no bar."""
    cfg = cfg or MocapConfig()
    if not cfg.bar_markers:
        return None
    names = [m for m in cfg.bar_markers if m in markers]
    if not names:
        return None
    stack = np.stack([markers[n] for n in names], axis=0)
    if not np.isfinite(stack).any():
        return None
    out = np.full(stack.shape[1:], np.nan)
    ok = np.isfinite(stack).any(axis=0)
    with np.errstate(invalid="ignore"):
        out[ok] = np.nanmean(stack, axis=0)[ok]
    return out


def bar_metrics(t: np.ndarray, bar: np.ndarray,
                t_start: float, t_end: float,
                concentric: Optional[Tuple[float, float]] = None,
                cfg: Optional["MocapConfig"] = None) -> Dict[str, float]:
    """Bar path measures over one lift, in SI units.

    * ``rom_m``            vertical travel of the bar
    * ``start_frac``       where the bar began within its own vertical range;
      the number that separates a deadlift (0) from a squat (1)
    * ``ap_drift_m``       total fore-aft excursion — how far the bar wandered
      away from the vertical, which is the usual coaching read on bar path
    * ``path_deviation_m`` largest fore-aft departure from the bar's position
      at the start of the concentric, i.e. the bow in the pull
    * ``peak_velocity_ms`` fastest upward bar velocity
    * ``mean_concentric_velocity_ms`` mean upward velocity over the concentric,
      the quantity velocity-based training is prescribed against
    """
    cfg = cfg or MocapConfig()
    iv, ia, il = cfg.axes()
    out = {k: float("nan") for k in
           ("rom_m", "start_frac", "ap_drift_m", "path_deviation_m",
            "peak_velocity_ms", "mean_concentric_velocity_ms")}
    if t is None or bar is None or not np.size(t):
        return out
    sel = (t >= t_start) & (t <= t_end)
    if sel.sum() < 3:
        return out
    y, x = bar[sel, iv], bar[sel, ia]
    ts = t[sel]
    if not np.isfinite(y).any():
        return out
    lo, hi = float(np.nanmin(y)), float(np.nanmax(y))
    out["rom_m"] = hi - lo
    _f = np.flatnonzero(np.isfinite(y))
    if _f.size and hi > lo:
        out["start_frac"] = (float(y[_f[0]]) - lo) / (hi - lo)
    if np.isfinite(x).any():
        out["ap_drift_m"] = float(np.nanmax(x) - np.nanmin(x))

    # Interpolate across dropouts and smooth before differentiating. A raw
    # frame-to-frame gradient on 200 Hz marker data turns one jittery frame
    # into an 8.9 m/s "peak bar velocity", which is not a bar.
    _ok = np.flatnonzero(np.isfinite(y))
    if _ok.size < 3:
        return out
    _yi = np.interp(np.arange(len(y)), _ok, y[_ok])
    _fs = 1.0 / max(float(np.median(np.diff(ts))), 1e-6)
    _w = max(3, int(0.05 * _fs))
    _yi = np.convolve(_yi, np.ones(_w) / _w, mode="same")
    dt = np.gradient(ts)
    vel = np.nan_to_num(np.gradient(_yi) / np.where(dt == 0, np.nan, dt))
    # the moving average smears the ends; ignore them
    vel[:_w] = 0.0
    vel[-_w:] = 0.0
    if vel.size:
        out["peak_velocity_ms"] = float(np.nanmax(vel))
    if concentric:
        cs = (ts >= concentric[0]) & (ts <= concentric[1])
        if cs.sum() >= 2:
            out["mean_concentric_velocity_ms"] = float(np.nanmean(vel[cs]))
            xc = x[cs]
            if np.isfinite(xc).any():
                _fc = np.flatnonzero(np.isfinite(xc))
                out["path_deviation_m"] = float(
                    np.nanmax(np.abs(xc - xc[_fc[0]])))
    return out


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
        # The phase NAME states the convention the cycle was cut with, so a
        # reader never has to go and look up cfg.stride_from to know what the
        # window means.
        _pname = ("foot_off_to_foot_off" if cfg.stride_from == "foot_off"
                  else "foot_contact_to_foot_contact")
        marks = offs if cfg.stride_from == "foot_off" else contacts
        for k in range(len(marks) - 1):
            x0, x1 = a + marks[k], a + marks[k + 1]
            phases.append(TaskSegment(
                task="stride", phase=_pname, side=side,
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
    _numbered(phases)
    return phases


def _numbered(phases: List[TaskSegment]) -> List[TaskSegment]:
    """Suffix a phase name with its ordinal when the same name repeats.

    One ``foot_off_to_foot_off`` per leg stays unsuffixed; two become
    ``_1`` and ``_2``, so a reader can tell which cycle a row refers to
    without counting rows.
    """
    _count: Dict[Tuple[str, str], int] = {}
    for p in phases:
        _count[(p.phase, p.side)] = _count.get((p.phase, p.side), 0) + 1
    _seen: Dict[Tuple[str, str], int] = {}
    for p in phases:
        _key = (p.phase, p.side)
        if _count[_key] > 1:
            _seen[_key] = _seen.get(_key, 0) + 1
            p.index = _seen[_key]
            p.phase = f"{p.phase}_{_seen[_key]}"
    return phases


def _merge_bar_lifts(out: List[TaskSegment], t: np.ndarray, bar: np.ndarray,
                     cfg: "MocapConfig") -> List[TaskSegment]:
    """Rebuild deadlifts around the BAR instead of around the pelvis.

    The pelvis cannot bound a deadlift. On Deadlift_35kg_01 the lifter spends
    3.2 s descending to a bar that is still on the floor, pulls for 0.8 s,
    stands at lockout for 2 s, lowers for 1.5 s and then stands up again — and
    a pelvis-driven segmenter sees that as two separate descent-and-rise
    blocks, reports both as squats, and puts the boundary in the middle of the
    lockout. Every part of the movement that makes it a deadlift is in the bar.

    A lift is one contiguous interval with the bar off the floor. It is split
    into

        setup       the lifter descending to a bar that has not moved
        concentric  the pull, bar rising
        lockout     bar held at the top
        lowering    bar returning to the floor

    Segments wholly inside the lift are replaced by it. A barbell squat is
    untouched: the bar never returns to the floor, so there is no floor
    interval to key on and the function declines to act.
    """
    if bar is None or not len(out) or t.size < 5:
        return out
    iv, ia, _il = cfg.axes()
    y = bar[:, iv]
    if not np.isfinite(y).any():
        return out
    floor = float(np.nanpercentile(y[np.isfinite(y)], 5))
    rom = float(np.nanmax(y) - floor)
    if rom < cfg.bar_min_travel_m:
        return out
    # A barbell SQUAT also has the bar low at the bottom of the rep, so "the
    # bar went down" is not enough to call this a floor lift. The bar has to
    # START on the floor: in a deadlift it begins at the bottom of its own
    # travel and the lifter comes down to it, in a squat it begins at the top,
    # already on the lifter. Measured here: deadlift 0%, back squat 88%.
    _f0 = np.flatnonzero(np.isfinite(y))
    _start_frac = (float(y[_f0[0]]) - floor) / rom if _f0.size and rom > 0 else 1.0
    if _start_frac > cfg.deadlift_start_frac:
        return out
    off = np.nan_to_num(y - floor) > max(0.03, 0.15 * rom)
    if off.mean() < 0.02:
        return out

    lifts = []
    i = 0
    while i < len(off):
        if not off[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(off) and off[j + 1]:
            j += 1
        if float(t[j] - t[i]) >= cfg.min_task_s:
            lifts.append((i, j))
        i = j + 1
    if not lifts:
        return out

    keep = [g for g in out]
    for i0, i1 in lifts:
        t_up, t_down = float(t[i0]), float(t[i1])
        # The lift starts where the lifter started going down to the bar: the
        # earliest task already found that runs into the pull.
        _pre = [g for g in out if g.task in ("squat", "deadlift", "single_leg_squat")
                and g.t_start < t_up and g.t_end > t_up - cfg.deadlift_setup_max_s]
        t0 = min([g.t_start for g in _pre], default=t_up)
        seg = y[i0:i1 + 1]
        k_top = i0 + int(np.nanargmax(seg))
        top = float(np.nanmax(seg))
        band = top - max(0.02, 0.08 * rom)
        h0 = i0 + int(np.flatnonzero(np.nan_to_num(seg) >= band)[0])
        h1 = i0 + int(np.flatnonzero(np.nan_to_num(seg) >= band)[-1])

        def _ph(name, x0, x1):
            if x1 > x0 and float(t[x1] - t[x0]) > 0.05:
                return [TaskSegment(task="deadlift", phase=name, index=1,
                                    t_start=round(float(t[x0]), 3),
                                    t_end=round(float(t[x1]), 3), confidence=0.7,
                                    reason=f"bar {y[x0]:.2f} -> {y[x1]:.2f} m")]
            return []

        # The reported task is the PULL, not the whole time the bar is off the
        # floor. Setup and lowering are removed from the timeline (they are
        # part of the lift and must not come back as separate "squats") but
        # they are not the movement being analysed.
        h_end = h0
        while h_end + 1 <= h1 and float(t[h_end + 1] - t[h0]) <= cfg.deadlift_lockout_s:
            h_end += 1
        t_task0, t_task1 = float(t[i0]), float(t[h_end])

        phases = []
        phases += _ph("concentric", i0, h0)
        phases += _ph("lockout", h0, h_end)

        # ROM is measured from the FLOOR, not from where the bar crossed the
        # off-the-floor threshold: the lift is floor-to-lockout, and starting
        # 15% of the way up under-reports it by 7 cm. The reported task window
        # is unaffected — this only widens what the metrics are computed over.
        _i_floor = i0
        while _i_floor > 0 and np.nan_to_num(y[_i_floor - 1] - floor) > 0.01:
            _i_floor -= 1
            if float(t[i0] - t[_i_floor]) > 1.0:
                break
        _bm = bar_metrics(t, bar, float(t[_i_floor]), t_task1,
                          concentric=(float(t[i0]), float(t[h0])), cfg=cfg)
        keep = [g for g in keep
                if g.t_end <= t0 + 1e-9 or g.t_start >= t_down - 1e-9]
        keep.append(TaskSegment(
            task="deadlift", t_start=round(t_task0, 3), t_end=round(t_task1, 3),
            confidence=0.85, phases=phases,
            reason=(f"pull from the floor, {float(t[h0] - t[i0]):.2f}s "
                    f"concentric, lifted {_bm['rom_m']*100:.0f} cm"
                    + (f", mean concentric bar velocity "
                       f"{_bm['mean_concentric_velocity_ms']:.2f} m/s"
                       if np.isfinite(_bm["mean_concentric_velocity_ms"]) else "")),
            bar_rom_m=round(_bm["rom_m"], 3),
            bar_ap_drift_m=(round(_bm["ap_drift_m"], 3)
                            if np.isfinite(_bm["ap_drift_m"]) else None),
            bar_path_deviation_m=(round(_bm["path_deviation_m"], 3)
                                  if np.isfinite(_bm["path_deviation_m"]) else None),
            bar_peak_velocity_ms=(round(_bm["peak_velocity_ms"], 3)
                                  if np.isfinite(_bm["peak_velocity_ms"]) else None),
            bar_mean_concentric_velocity_ms=(
                round(_bm["mean_concentric_velocity_ms"], 3)
                if np.isfinite(_bm["mean_concentric_velocity_ms"]) else None)))
    keep.sort(key=lambda g: g.t_start)
    return keep


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
    pel = _pelvis_centre(markers, cfg) if markers else None
    if pel is None or t.size < 5:
        return []
    _iv, _ia, _il = cfg.axes()
    # The bar, if this project has one. Computed once: every lift in the trial
    # is measured against the same series.
    _bar = bar_centre(markers, cfg)
    if _bar is not None:
        _by = _bar[:, _iv]
        if not np.isfinite(_by).any() or \
                float(np.nanmax(_by) - np.nanmin(_by)) < cfg.bar_min_travel_m:
            # Markers on a bar that never moved — a bodyweight squat with the
            # bar left in the rack. Reporting a 0 cm lift would be worse than
            # reporting no bar at all.
            _bar = None

    # pelvis: depth below the standing reference, and horizontal speed
    vert = pel[:, _iv]
    if not np.isfinite(vert).any():
        return []                         # pelvis never seen — nothing to segment
    head = vert[:max(3, len(vert) // 20)]
    tail = vert[-max(3, len(vert) // 10):]
    # The first 5% can be entirely occluded; fall back to the whole trial.
    _base_head = float(np.nanmedian(head)) if np.isfinite(head).any() \
        else float(np.nanmedian(vert[np.isfinite(vert)]))
    # Standing is the HIGHER of the opening and the settled tail. A trial that
    # starts with the participant already in the hold (see started_low_m) has
    # no standing frames at its head at all, and referencing depth to the squat
    # makes the squat invisible. A trial that ends low is unaffected: the head
    # is then the higher of the two and this reduces to the old behaviour.
    _base_tail = float(np.nanmedian(tail)) if np.isfinite(tail).any() else _base_head
    base = max(_base_head, _base_tail)
    _started_low = bool(_base_tail - _base_head > cfg.started_low_m)
    depth = base - vert
    horiz = pel[:, cfg.horizontal()]
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
        h = _foot_height(markers, side, cfg)
        if h is None:
            lifted[side] = np.zeros(len(t), bool)
            continue
        floor = float(np.nanpercentile(h[np.isfinite(h)], 5)) if np.isfinite(h).any() else 0.0
        lifted[side] = np.nan_to_num(h - floor) > cfg.foot_lift_m

    # airborne, only when the plate mapping covers both feet
    air = np.zeros(len(t), bool)
    _gt_all = _total_all = None
    gm = os.path.join(exp_dir, "grf.mot")
    if os.path.exists(gm):
        gt, gcols = read_grf(gm)
        vy = [v for c, v in gcols.items() if c.endswith("_vy")]
        if gt.size and vy:
            total = np.nansum(np.stack(vy, axis=0), axis=0)
            _bw = (float(body_mass) * cfg.gravity) if body_mass else 0.0
            # The guard used to be "GRF.xml maps both feet", but that mapping
            # is produced at export time and is wrong often enough that it was
            # switching flight detection off on trials that have perfectly good
            # force. What actually matters is whether the plates carry the
            # BODY: if the summed vertical force reaches roughly body weight
            # somewhere, an interval near zero really is flight.
            _seen = (not _bw) or float(np.nanmax(total)) >= 0.8 * _bw
            if _seen:
                _gt_all, _total_all = gt, total
                thr = (cfg.flight_bw * _bw) if _bw \
                    else cfg.flight_bw * float(np.nanmax(total) or 1.0)
                _low = np.asarray(total) < thr
                # Zero force is only FLIGHT if the body took off from the
                # plates and landed back on them. Without that check, the long
                # stretches where a runner is simply not over any plate — the
                # approach and the run-out on every straight run here — read as
                # one enormous airborne phase and the trial classifies as a
                # jump. Require real load within flight_context_s either side.
                _ld = np.asarray(total) >= 0.5 * (_bw or float(np.nanmax(total) or 1.0))
                _dt = float(np.median(np.diff(gt))) if gt.size > 1 else 0.0
                _pad = max(1, int(cfg.flight_context_s / _dt)) if _dt > 0 else 1
                _i = 0
                while _i < len(_low):
                    if not _low[_i]:
                        _i += 1
                        continue
                    _j = _i
                    while _j + 1 < len(_low) and _low[_j + 1]:
                        _j += 1
                    _before = _ld[max(0, _i - _pad):_i].any()
                    _after = _ld[_j + 1:_j + 1 + _pad].any()
                    if not (_before and _after):
                        _low[_i:_j + 1] = False
                    _i = _j + 1
                air = np.interp(t, gt, _low.astype(float)) > 0.5
                # And the feet have to agree. Without this a participant
                # walking off the plates reads as a flight phase.
                _bl = _both_feet_lifted(markers, t, cfg)
                if _bl is not None:
                    air = air & _bl

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
        elif air[i]:
            # Force-derived flight. Kept apart from the marker-derived case
            # below only until smoothing, because the two deserve different
            # minimum durations: zero force between two loaded instants is
            # flight however brief, while "both feet above their own floor"
            # is true for half of a fast run-through and needs the full
            # min_task_s before it may become a task.
            labels.append("flight")
        elif both_lifted:
            labels.append("jump")
        elif one_lifted:
            labels.append("single_leg_squat" if depth[i] >= cfg.squat_drop_m
                          else "single_leg_stance")
        else:
            labels.append("squat" if depth[i] >= cfg.squat_drop_m else "static")

    labels = _smooth_runs(labels, t, cfg.min_task_s,
                          {"flight": cfg.min_flight_s})
    labels = ["jump" if _l == "flight" else _l for _l in labels]

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
            # A squat and a deadlift look the same from the pelvis alone —
            # both are a descent, a bottom and a rise — so the pelvis cannot
            # tell them apart and this used to report every deadlift as a
            # squat. The bar can: in a squat it starts ON the lifter, at the
            # top of its own travel; in a deadlift it starts on the floor, at
            # the bottom, and the lifter comes down to it.
            if _bar is not None:
                _con = [_p for _p in phases if _p.phase == "concentric"]
                _bm = bar_metrics(t, _bar, float(t[a]), float(t[b]),
                                  concentric=((_con[0].t_start, _con[0].t_end)
                                              if _con else None), cfg=cfg)
                if np.isfinite(_bm["start_frac"]) \
                        and _bm["start_frac"] <= cfg.deadlift_start_frac:
                    lab = "deadlift"
                    why = (f"bar starts at {_bm['start_frac']:.0%} of its own "
                           f"travel (on the floor), lifted "
                           f"{_bm['rom_m']*100:.0f} cm")
                else:
                    why += (f"; bar starts at {_bm['start_frac']:.0%} of its "
                            f"travel, {_bm['rom_m']*100:.0f} cm of bar travel")
                if np.isfinite(_bm["mean_concentric_velocity_ms"]):
                    why += (f", mean concentric bar velocity "
                            f"{_bm['mean_concentric_velocity_ms']:.2f} m/s")
                _barvals = _bm
                for _p in phases:
                    _p.task = lab
            else:
                _barvals = None
        elif lab == "static":
            why = "both feet down, no descent"
        elif lab == "jump":
            why = "both feet off the ground"
            # A jump that never got merged into a squat still has a height —
            # the impulse route needs a resting start it does not have here,
            # so only the two that do not are reported.
            _jh0 = jump_height(t, vert, float(t[a]), float(t[b]), cfg=cfg)
            if np.isfinite(_jh0["marker_m"]):
                why += (f", rose {_jh0['marker_m']*100:.0f} cm "
                        f"in {_jh0['flight_time_s']:.2f}s of flight")
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
                    _t0 = float(_c["t_on"])
                    if _last and _turning:
                        _lab = "cut"
                        # The LEG that planted. The turn direction travels in
                        # its own field.
                        _sd = _foot
                        # Open the window at the contralateral foot off. Both
                        # sources are used: the plate sees that foot only if it
                        # happened to land ON a plate, and on most cuts here it
                        # did not, so the marker events are what actually close
                        # the gap.
                        _contra = {"l": "r", "r": "l"}.get(_c["side"], "")
                        _offs = [float(o) for o in
                                 (_marker_events or {}).get(_contra, {}).get("off", [])]
                        _offs += [float(x["t_off"]) for x in _cs
                                  if x.get("side") == _contra]
                        _prev = [o for o in _offs
                                 if o <= _c["t_on"] + 1e-9
                                 and (_c["t_on"] - o) <= cfg.cut_lead_max_s]
                        if cfg.cut_from_contra_off and _prev:
                            _t0 = max(_prev)
                        _dir = cut_dir
                        _why = (f"{_foot or '?'}-foot plant, {cut_angle:.0f}\u00b0 "
                                f"to the {cut_dir}, peak {_c['peak_n']:.0f} N"
                                + (f"; from {_contra.upper()} foot off "
                                   f"({_c['t_on'] - _t0:.2f} s of flight)"
                                   if _t0 < _c["t_on"] else
                                   "; no contralateral foot off found, "
                                   "window starts at touchdown"))
                    else:
                        _lab = "running" if v >= cfg.walk_run_speed else "walking"
                        _dir = None
                        _why = (f"{_foot or '?'}-foot contact at {v:.2f} m/s, "
                                f"peak {_c['peak_n']:.0f} N"
                                + ("" if _last else " (approach step)"))
                        _sd = _foot
                    # Only phases belonging to THIS leg. A left-foot task
                    # was carrying the right leg's stride as well, which made a
                    # task labelled "left" report two phases, one of them the
                    # other leg's.
                    _t1 = float(_c["t_off"])

                    def _best_stride(_side, _lo, _hi):
                        """The one cycle of ``_side`` that this contact is in.

                        Ranked by overlap DURATION, not by touching: the stride
                        that merely abuts the contact at a boundary is the
                        NEXT cycle, and picking it labelled a task with a
                        window that started after the task had ended.
                        """
                        _cands = []
                        for _p in phases:
                            if _p.side != _side or not _p.phase.startswith(
                                    ("foot_off_to_foot_off",
                                     "foot_contact_to_foot_contact")):
                                continue
                            _ov = min(_p.t_end, _hi) - max(_p.t_start, _lo)
                            if _ov > 0.02:
                                _cands.append((_ov, _p))
                        return max(_cands, key=lambda x: x[0])[1] if _cands else None
                    # Exactly ONE phase per task, and the task window IS
                    # that phase. A running step is its stride: the plate only
                    # sees the fraction of the cycle that passed over it, so
                    # shading the contact window drew a band that disagreed
                    # with the phase directly above it. A cut keeps its own
                    # window — contralateral foot off to ipsilateral foot off,
                    # which is not a stride — and reports the measured contact.
                    _st = _best_stride(_foot, _t0, _t1) if _lab != "cut" else None
                    if _st is not None:
                        _t0, _t1 = float(_st.t_start), float(_st.t_end)
                        _ph = [TaskSegment(
                            task=_lab, phase=_st.phase.split("_1")[0].split("_2")[0],
                            side=_foot, index=1,
                            t_start=_st.t_start, t_end=_st.t_end, confidence=0.6,
                            reason=_st.reason)]
                    else:
                        # Nothing but the plate saw this step. Say exactly
                        # that, rather than implying a gait cycle was measured.
                        _ph = [TaskSegment(
                            task=_lab, phase="ground_contact", side=_foot,
                            index=1, t_start=round(float(_c["t_on"]), 3),
                            t_end=round(float(_c["t_off"]), 3), confidence=0.6,
                            reason=(f"{_foot or '?'} foot on {_c['plate']}, "
                                    f"peak {_c['peak_n']:.0f} N; no complete "
                                    f"{cfg.stride_from}-to-{cfg.stride_from} "
                                    f"cycle for this leg in the capture"))]
                    out.append(TaskSegment(
                        task=_lab, side=_sd, t_start=round(_t0, 3),
                        t_end=round(_t1, 3), confidence=0.75,
                        reason=_why, phases=_ph, direction=_dir,
                        angle_deg=(round(float(cut_angle), 1)
                                   if _lab == "cut" else None)))
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
        _bj = (jump_height(t, vert, float(t[a]), float(t[b]), cfg=cfg)
               if lab == "jump" else None)
        _bv = locals().get("_barvals") if lab in ("squat", "deadlift") else None

        def _bnum(key):
            _v = (_bv or {}).get(key)
            return round(float(_v), 3) if _v is not None and np.isfinite(_v) else None

        out.append(TaskSegment(task=lab, side=side,
                               bar_rom_m=_bnum("rom_m"),
                               bar_ap_drift_m=_bnum("ap_drift_m"),
                               bar_path_deviation_m=_bnum("path_deviation_m"),
                               bar_peak_velocity_ms=_bnum("peak_velocity_ms"),
                               bar_mean_concentric_velocity_ms=_bnum(
                                   "mean_concentric_velocity_ms"),
                               t_start=round(float(t[a]), 3),
                               t_end=round(float(t[b]), 3),
                               confidence=0.7, reason=why, phases=phases,
                               jump_height_m=(round(_bj["marker_m"], 3)
                                              if _bj and np.isfinite(_bj["marker_m"])
                                              else None),
                               flight_time_s=(round(_bj["flight_time_s"], 3)
                                              if _bj else None)))
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
            # Integrate from the bottom of the squat, where the body is
            # genuinely at rest, rather than from the top of the descent. Same
            # physics, quarter the window, so plate drift has a quarter of the
            # time to accumulate into a spurious take-off velocity.
            _con = [_p for _p in _ph if _p.phase == "concentric"]
            _rest = _con[0].t_start if _con else _g.t_start
            _jh = jump_height(t, vert, _nx.t_start, _nx.t_end,
                              gt=_gt_all, total=_total_all,
                              body_mass=body_mass, t_start=_rest, cfg=cfg)
            _hm = _jh["marker_m"] if np.isfinite(_jh["marker_m"]) else None
            _hg = _jh["impulse_m"] if np.isfinite(_jh["impulse_m"]) else None
            _hbits = []
            if _hg is not None:
                _hbits.append(f"{_hg*100:.0f} cm by impulse")
            if _hm is not None:
                _hbits.append(f"{_hm*100:.0f} cm by marker")
            if np.isfinite(_jh["flight_m"]):
                _hbits.append(f"{_jh['flight_m']*100:.0f} cm by flight time")
            _merged.append(TaskSegment(
                task="squat_jump", side=_g.side, t_start=_g.t_start,
                t_end=_nx.t_end, confidence=0.85,
                reason=(f"{_g.reason.split(',')[-1].strip()} then "
                        f"{_nx.duration:.2f}s of flight"
                        + ("; jump height " + ", ".join(_hbits) if _hbits else "")),
                phases=_ph,
                jump_height_m=(round(_hm, 3) if _hm is not None else None),
                jump_height_grf_m=(round(_hg, 3) if _hg is not None else None),
                flight_time_s=round(_jh["flight_time_s"], 3)))
            _k += 2
            continue
        _merged.append(_g)
        _k += 1
    out = _merged

    # Widening a step to its stride can reorder the list: a left stride that
    # opened before the right contact now starts earlier than the task emitted
    # before it. The overlap pass below walks neighbours, so it has to see the
    # list in time order.
    out.sort(key=lambda g: (g.t_start, g.t_end))

    if _bar is not None:
        out = _merge_bar_lifts(out, t, _bar, cfg)

    _GROWN = {"squat", "single_leg_squat", "squat_jump", "deadlift"}
    for k in range(1, len(out)):
        prev, cur = out[k - 1], out[k]
        if cur.t_start >= prev.t_end:
            continue
        # Two travelling tasks are two strides of OPPOSITE legs, and
        # consecutive strides overlap — that is what walking and running are.
        # Trimming them apart shortened every step to the part no other step
        # touched, which is exactly the disagreement between the task band and
        # the stride phase above it.
        _TRAVEL = {"running", "walking", "cut"}
        if cur.task in _TRAVEL and prev.task in _TRAVEL:
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
            thr_edge = (cfg.contact_edge_bw * float(body_mass) * cfg.gravity) \
                if body_mass else cfg.contact_edge_bw * float(np.nanmax(total) or 1.0)
            out["grf"] = _span(_grow_mask(total, total > thr, thr_edge), gt)

    # --- markers ---
    trc = os.path.join(exp_dir, "marker_experimental.trc")
    if os.path.exists(trc):
        try:
            t, markers, _ = read_trc(trc)
        except Exception:
            t, markers = np.array([]), {}
        pel = _pelvis_centre(markers, cfg) if markers else None
        if pel is not None and t.size > 2:
            horiz = pel[:, cfg.horizontal()]
            dt = np.diff(t); dt[dt <= 0] = np.nan
            spd = np.concatenate([[0.0],
                                  np.linalg.norm(np.diff(horiz, axis=0), axis=1) / dt])
            spd = np.nan_to_num(spd)
            moving = spd > cfg.static_speed
            if moving.any():
                out["markers"] = _span(moving, t)
            else:
                vert = pel[:, cfg.axes()[0]]
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
        rank = {"cut": 7, "squat_jump": 6, "single_leg_squat": 5,
                "deadlift": 5, "jump": 4,
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
# Left is red, right is green, everywhere the figure names a leg — force
# curve, gait event line, footfall marker. One mapping so the colour means the
# same thing in every panel and can be changed in one place.
FOOT_COLOURS = {"l": "#D32F2F", "r": "#2E7D32"}


TASK_COLOURS = {
    "static": "#B0BEC5", "single_leg_stance": "#90CAF9",
    "squat": "#66BB6A", "single_leg_squat": "#26A69A",
    "deadlift": "#8D6E63",
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
    # Three orthogonal views stacked in the right column. A sub-gridspec
    # keeps them independent of the four uneven rows on the left.
    gsr = gs[:, 1].subgridspec(3, 1, hspace=.42)
    axt = fig.add_subplot(gsr[0])            # sagittal   X-Y
    axn = fig.add_subplot(gsr[1])            # frontal    Z-Y
    axv = fig.add_subplot(gsr[2])            # transverse X-Z (top view)

    # --- vertical GRF ---
    gm = os.path.join(exp_dir, "grf.mot")
    _cf: List[dict] = []

    def _seg_foot(g):
        """The leg a task segment belongs to, from the ground contact inside it.

        NOT ``g.side``: on a cut that field carries the DIRECTION of the turn
        ("cut right" = turned right), which is a different thing from the leg
        that planted — and colouring by it would paint a right-turn cut off a
        left-foot plant green. The contact is unambiguous, so use it, and only
        fall back to ``g.side`` for the tasks where it does name a leg.
        """
        # ``side`` is authoritative now that it names the LEG on every task
        # including cuts (the turn direction moved to ``direction``). It has to
        # win: once a step is widened to its whole stride the window covers the
        # other leg's contact too, and inferring the leg from contact overlap
        # then gives up and paints both strides of a run the same colour.
        if g.side in ("left", "right"):
            return g.side[0]
        # Otherwise fall back to overlap DURATION, not "do they touch": a
        # neighbouring contact that ends exactly on t_start is not in the
        # window. Whichever leg is under it at least twice as long owns it.
        ov: Dict[str, float] = {}
        for c in _cf:
            s = c.get("side")
            if s not in ("l", "r"):
                continue
            d = min(c["t_off"], g.t_end) - max(c["t_on"], g.t_start)
            if d > 0:
                ov[s] = ov.get(s, 0.0) + d
        if ov:
            best = max(ov, key=ov.get)
            other = max([v for k, v in ov.items() if k != best] or [0.0])
            if ov[best] >= 2 * other:
                return best
            return None
        return None

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
                axf.plot(gt, v, lw=1.8 if sd else 1.0,
                         ls="--" if sd else ":", alpha=.95 if sd else .35,
                         color=FOOT_COLOURS.get(sd) if sd else "grey",
                         label=f"{c}{tag}")
            total = np.nansum(np.stack(list(vy.values()), axis=0), axis=0)
            # Thin and dotted so it never competes with the plate traces, and
            # recoloured leg-by-leg across each task: during a running contact
            # the total IS that leg's load, and one black line loses whose.
            axf.plot(gt, total, lw=0.9, ls=":", color="0.35", alpha=.85,
                     label="total")
            for _g in segs:
                _sf = _seg_foot(_g)
                if not _sf:
                    continue
                _m = (gt >= _g.t_start) & (gt <= _g.t_end)
                if _m.any():
                    axf.plot(gt[_m], total[_m], lw=1.1, ls=":", zorder=4,
                             color=FOOT_COLOURS[_sf], alpha=.95)
            if body_mass:
                bw = float(body_mass) * cfg.gravity
                axf.axhline(bw, ls="--", c="grey", lw=.8)
                axf.text(gt[0], bw, " 1 BW", fontsize=7, va="bottom", color="grey")
    axf.set_ylabel("vertical GRF (N)")

    # --- detected gait events ----------------------------------------------
    # Thin dashed = foot strike, thin dotted = foot off, coloured by leg.
    # Drawn for the travelling tasks only: on a squat the "events" are the
    # participant shifting weight and the lines are noise on the figure.
    _events: List[Tuple[str, str, float]] = (
        _gait_event_times(exp_dir, _cf, cfg)
        if any(g.task in ("running", "walking", "cut") for g in segs) else [])
    _seen_lbl = set()
    for _sd, _kind, _tt in _events:
        _lbl = f"{_sd.upper()} foot {_kind}"
        axf.axvline(_tt, color=FOOT_COLOURS.get(_sd, "grey"),
                    ls="--" if _kind == "strike" else ":", lw=0.9, alpha=.85,
                    zorder=1, label=None if _lbl in _seen_lbl else _lbl)
        _seen_lbl.add(_lbl)
    axf.legend(fontsize=6.5, ncol=3, loc="upper center", framealpha=.9, borderpad=.3)

    # --- pelvis height ---
    trc = os.path.join(exp_dir, "marker_experimental.trc")
    _pt = _py = None
    if os.path.exists(trc):
        try:
            t, mk, _ = read_trc(trc)
            pel = _pelvis_centre(mk, cfg)
            if pel is not None:
                _ivp = cfg.axes()[0]
                axp.plot(t, pel[:, _ivp], lw=1.2, color="tab:blue")
                _pt, _py = t, pel[:, _ivp]
        except Exception:
            pass

    # --- jump height on the pelvis trace ------------------------------------
    # Drawn where the rise actually happens: a dotted line at the take-off
    # height and a measured arrow up to the apex, so the number on the ribbon
    # can be checked against the trace rather than taken on trust.
    if _pt is not None:
        for g in segs:
            if getattr(g, "jump_height_m", None) is None:
                continue
            _fl = [p for p in g.phases if p.phase == "air_time"] or None
            _t0 = _fl[0].t_start if _fl else g.t_start
            _t1 = _fl[0].t_end if _fl else g.t_end
            _sel = (_pt >= _t0) & (_pt <= _t1)
            if not _sel.any():
                continue
            _y0 = float(_py[int(np.argmin(np.abs(_pt - _t0)))])
            _sy = _py[_sel]
            if not np.isfinite(_y0) or not np.isfinite(_sy).any():
                continue
            _pk = float(np.nanmax(_sy))
            _xpk = float(_pt[_sel][int(np.nanargmax(_sy))])
            axp.hlines(_y0, _t0, _t1, color="#5D4037", ls=":", lw=.9, zorder=5)
            axp.annotate("", xy=(_xpk, _pk), xytext=(_xpk, _y0), zorder=6,
                         arrowprops=dict(arrowstyle="<->", color="#5D4037", lw=1.0))
            axp.text(_xpk, (_y0 + _pk) / 2, f"  {(_pk - _y0)*100:.0f} cm",
                     fontsize=7, color="#5D4037", va="center", ha="left", zorder=6)
    # --- the bar, when the project has one ----------------------------------
    _barp = None
    if os.path.exists(trc):
        try:
            _tb, _mkb, _ = read_trc(trc)
            _barp = bar_centre(_mkb, cfg)
            if _barp is not None:
                _ivb = cfg.axes()[0]
                _byb = _barp[:, _ivb]
                if np.isfinite(_byb).any() and float(
                        np.nanmax(_byb) - np.nanmin(_byb)) >= cfg.bar_min_travel_m:
                    axp.plot(_tb, _byb, lw=1.6, color="#F9A825", label="bar")
                    axp.legend(fontsize=7, loc="upper right", framealpha=.9)
                else:
                    _barp = None
        except Exception:
            _barp = None
    axp.set_ylabel("height (m)" if _barp is not None else "pelvis height (m)")
    axp.set_xlabel("time (s)")
    # Only the bottom time axis carries tick labels — sharex repeats them on
    # every panel otherwise, which reads as three different axes.
    for _ax in (axr, axq, axf):
        plt.setp(_ax.get_xticklabels(), visible=False)

    # --- phase ribbon -------------------------------------------------------
    # The sub-phases are the point of a squat jump — descent / hold /
    # concentric / air_time — and a single task block hides them.
    PHASE_COLOURS = {"descent": "#81C784", "hold": "#FFD54F",
                     "setup": "#BCAAA4", "lockout": "#FFCC80",
                     "lowering": "#9575CD",
                     "concentric": "#4DB6AC", "air_time": "#FF8A65",
                     "landing": "#BA68C8", "swing": "#B0BEC5",
                     "ground_contact": "#9FA8DA",
                     "foot_off_to_foot_off": "#80CBC4",
                     "foot_contact_to_foot_contact": "#A5D6A7"}

    def _phase_colour(name):
        """Colour by phase family, so numbered repeats match their siblings."""
        if name in PHASE_COLOURS:
            return PHASE_COLOURS[name]
        for _k, _v in PHASE_COLOURS.items():
            if name.startswith(_k):
                return _v
        return "#CFD8DC"
    _any_phase = False
    for g in segs:
        for ph in g.phases:
            _any_phase = True
            _c = _phase_colour(ph.phase)
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
        if getattr(g, "direction", None):
            _name += f" \u2192 {g.direction}"
        _hbits = []
        if getattr(g, "jump_height_grf_m", None) is not None:
            _hbits.append(f"{g.jump_height_grf_m*100:.0f} GRF")
        if getattr(g, "jump_height_m", None) is not None:
            _hbits.append(f"{g.jump_height_m*100:.0f} mkr")
        _extra = ("h " + " / ".join(_hbits) + " cm") if _hbits else ""
        if getattr(g, "bar_rom_m", None) is not None:
            _bb = [f"bar {g.bar_rom_m*100:.0f} cm"]
            if getattr(g, "bar_mean_concentric_velocity_ms", None) is not None:
                _bb.append(f"MCV {g.bar_mean_concentric_velocity_ms:.2f} m/s")
            if getattr(g, "bar_path_deviation_m", None) is not None:
                _bb.append(f"drift {g.bar_path_deviation_m*100:.0f} cm")
            _extra = (_extra + "\n" if _extra else "") + ", ".join(_bb)
        # "cut right" says which way; "cut right 26\u00b0" says how sharp, which
        # is the number that separates a sidestep from a gentle swerve.
        if getattr(g, "angle_deg", None) is not None:
            _name += f" {g.angle_deg:.0f}\u00b0"
        span = g.t_end - g.t_start
        if span > 0.8:
            axr.text((g.t_start + g.t_end) / 2, 0.5,
                     f"{_name}\n{g.duration:.2f}s"
                     + (f"\n{_extra}" if _extra else ""),
                     ha="center", va="center", fontsize=7.5)
        else:
            axr.annotate(f"{_name} {g.duration:.2f}s"
                         + (f"  {_extra}" if _extra else ""),
                         xy=((g.t_start + g.t_end) / 2, 1.0), xytext=(0, 6),
                         textcoords="offset points", ha="center", va="bottom",
                         fontsize=6.5, rotation=30)
    axr.set_ylim(0, 1); axr.set_yticks([])
    axr.set_ylabel("tasks", fontsize=8, rotation=0, ha="right", va="center")
    for sp in ("top", "right", "left"):
        axr.spines[sp].set_visible(False)
    for ax in (axf, axp):
        for g in segs:
            # Leg colour where the task has one; the task ribbon above still
            # carries the task colour, so nothing is lost by using this band
            # to answer "whose leg is this?" instead.
            _sf = _seg_foot(g)
            ax.axvspan(g.t_start, g.t_end, lw=0,
                       color=FOOT_COLOURS[_sf] if _sf
                       else TASK_COLOURS.get(g.task, "#ECEFF1"),
                       alpha=.16 if _sf else .22)
            ax.axvline(g.t_start, color="k", lw=.5, alpha=.35)
        ax.grid(alpha=.25)

    # --- marker trajectories: three orthogonal views ------------------------
    # Every marker as a hairline path with a dot at the LAST frame, so the
    # trial reads as a movement rather than as three time series. The pelvis is
    # drawn thick because it is what the task rules are computed from.
    try:
        if os.path.exists(trc):
            t2, mk2, _ = read_trc(trc)
            pel2 = _pelvis_centre(mk2, cfg)

            # Which horizontal axis the participant actually travelled along.
            # The lab frame is not the same in every capture: on this session
            # the runway runs along Z, so drawing X-Y and calling it "sagittal"
            # shows a 2 m box while the 5 m of running hides in the panel
            # labelled frontal. Pick the axis with the larger net pelvis
            # displacement and label the panels with the axis actually used.
            _ivv, _ip, _il = cfg.axes()
            if pel2 is not None:
                _h = pel2[:, [_ip, _il]]
                _f = np.isfinite(_h).all(axis=1)
                if _f.sum() > 2:
                    _d = np.abs(_h[_f][-1] - _h[_f][0])
                    if _d[1] > _d[0] + 0.20:      # clearly along Z, not a tie
                        _ip, _il = 2, 0
            _NM = {0: "X", 1: "Y", 2: "Z"}
            _VERT = _NM[_ivv]
            _PROG = f"progression {_NM[_ip]} (m)"
            _LAT = f"mediolateral {_NM[_il]} (m)"

            def _cloud(ax, ia, ib):
                """Hairline path per marker + a dot on the final frame."""
                for _nm, _arr in mk2.items():
                    if _arr.shape[0] < 2:
                        continue
                    _u, _v = _arr[:, ia], _arr[:, ib]
                    if not (np.isfinite(_u).any() and np.isfinite(_v).any()):
                        continue
                    ax.plot(_u, _v, lw=0.35, alpha=.55, color="#78909C",
                            solid_capstyle="round")
                    _fi = np.flatnonzero(np.isfinite(_u) & np.isfinite(_v))
                    if _fi.size:
                        ax.plot(_u[_fi[-1]], _v[_fi[-1]], "o", ms=4.5,
                                color="#37474F", zorder=3)
                if pel2 is not None:
                    _u, _v = pel2[:, ia], pel2[:, ib]
                    ax.plot(_u, _v, lw=2.6, color="tab:blue", alpha=.95,
                            label="pelvis", zorder=4)
                    _fi = np.flatnonzero(np.isfinite(_u) & np.isfinite(_v))
                    if _fi.size:
                        ax.plot(_u[_fi[-1]], _v[_fi[-1]], "o", ms=8,
                                color="tab:blue", zorder=5)
                ax.set_aspect("equal", adjustable="box")
                ax.grid(alpha=.25)
                ax.legend(fontsize=7, loc="upper right")

            # Foot centres, used to place the gait events in space.
            _feet_xy = {}
            for _s, _k in (("l", "L"), ("r", "R")):
                _nmz = _foot_markers(mk2, _k, cfg)
                if _nmz:
                    _feet_xy[_s] = np.nanmean(
                        np.stack([mk2[n] for n in _nmz], axis=0), axis=0)

            def _event_frame(sd, tt):
                _arr = _feet_xy.get(sd)
                if _arr is None or not t2.size:
                    return None
                _j = int(np.argmin(np.abs(t2 - tt)))
                if _j >= len(_arr) or not np.isfinite(_arr[_j]).all():
                    return None
                return _arr[_j]

            # --- sagittal: progression against vertical ---------------------
            _cloud(axt, _ip, _ivv)
            axt.set_xlabel(_PROG)
            axt.set_ylabel(f"vertical {_VERT} (m)")
            axt.set_title("markers — sagittal (%s-%s)\ndots = final frame"
                          % (_NM[_ip], _VERT), fontsize=9, pad=6)
            # The same gait events as the GRF panel, placed at the PROGRESSION
            # coordinate the foot was at. A time line has no meaning on a
            # spatial plot; the footfall LOCATION does, and it lines the events
            # up against the trajectory they belong to.
            for _sd, _kind, _tt in _events:
                _p = _event_frame(_sd, _tt)
                if _p is None:
                    continue
                axt.axvline(float(_p[_ip]), lw=0.8, alpha=.8, zorder=1,
                            color=FOOT_COLOURS.get(_sd, "grey"),
                            ls="--" if _kind == "strike" else ":")

            # The bar path, in the plane a coach reads it in. Drawn on the
            # sagittal panel rather than in a panel of its own because the
            # question is always where the bar went RELATIVE to the lifter.
            _barp2 = bar_centre(mk2, cfg)
            if _barp2 is not None:
                _bu, _bv2 = _barp2[:, _ip], _barp2[:, _ivv]
                if np.isfinite(_bv2).any() and float(
                        np.nanmax(_bv2) - np.nanmin(_bv2)) >= cfg.bar_min_travel_m:
                    axt.plot(_bu, _bv2, lw=2.4, color="#F9A825", alpha=.95,
                             label="bar", zorder=6)
                    _fb = np.flatnonzero(np.isfinite(_bu) & np.isfinite(_bv2))
                    if _fb.size:
                        axt.plot(_bu[_fb[0]], _bv2[_fb[0]], "s", ms=6,
                                 color="#F9A825", mec="k", mew=.4, zorder=7)
                        axt.plot(_bu[_fb[-1]], _bv2[_fb[-1]], "o", ms=8,
                                 color="#F9A825", mec="k", mew=.4, zorder=7)
                    axt.legend(fontsize=7, loc="upper right")

            # --- frontal: mediolateral against vertical ---------------------
            _cloud(axn, _il, _ivv)
            axn.set_xlabel(_LAT)
            axn.set_ylabel(f"vertical {_VERT} (m)")
            axn.set_title("markers — frontal (%s-%s)" % (_NM[_il], _VERT),
                          fontsize=9, pad=6)

            # --- transverse: the top view -----------------------------------
            # The plane a cut actually happens in. Sagittal and frontal both
            # project the turn away; from above it IS the shape of the path.
            _cloud(axv, _ip, _il)
            axv.set_xlabel(_PROG)
            axv.set_ylabel(_LAT)
            axv.set_title("markers — transverse (%s-%s, top view)\nX = foot strike"
                          % (_NM[_ip], _NM[_il]), fontsize=9, pad=6)
            for _sd, _kind, _tt in _events:
                if _kind != "strike":
                    continue
                _p = _event_frame(_sd, _tt)
                if _p is None:
                    continue
                axv.plot(float(_p[_ip]), float(_p[_il]), marker="X", ms=7,
                         color=FOOT_COLOURS.get(_sd, "grey"),
                         mec="k", mew=.4, zorder=6)
    except Exception as _e:
        for _ax in (axt, axn, axv):
            _ax.text(.5, .5, f"trajectories unavailable\n{type(_e).__name__}",
                     ha="center", va="center", fontsize=8, transform=_ax.transAxes)

    fig.suptitle(f"{trial} — {len(segs)} task(s) detected", fontsize=11)
    os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
    fig.savefig(out_png, dpi=150)
    plt.close(fig)
    return out_png
