"""
BioScout — Shot Analysis (prototype)
====================================

From a basketball video: count shot attempts, segment each shot, extract
per-shot kinematics on a smooth 0-100% axis, support assisted made/missed
tagging, and (low-fidelity) predict muscle forces from the kinematics with a
kinematics-only surrogate model.

Pipeline
--------
    video ──pose──▶ landmarks{frame:{name:(x,y)}}
          ──detect_shots──▶ [Shot(start,release,end), ...]
          ──shot_kinematics──▶ joint angles, time-normalised 0-100%
          ──plot/CSV──▶ figures + shots.csv (mark 'made' column)
          ──predict_muscle_forces──▶ per-shot muscle-force curves

Pose
----
2-D pose comes from BioScout's MediaPipe tracker (``record.video``), which runs
on the user's machine. Pass ``poses=`` (a precomputed {frame:{name:(x,y)}} dict
or a JSON path produced by the GUI) to skip detection — this also makes the rest
of the pipeline testable without MediaPipe.

CLI (wired in __main__.py):
    python -m bioscout --shots "video.mp4"
    python -m bioscout --shots "video.mp4" --shooting-hand right
    python -m bioscout --shots "video.mp4" --poses poses.json   # skip MediaPipe

NOTE on muscle forces: predicting muscle forces from joint angles ALONE is
inherently low fidelity (forces scale with subject strength/size, which angles
don't encode; cross-subject R^2 is poor). Treat the force output as indicative
shape, not calibrated magnitude.
"""

import os
import io
import json
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# MediaPipe-pose landmark names we rely on.
LMS = ["nose", "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
       "left_wrist", "right_wrist", "left_hip", "right_hip",
       "left_knee", "right_knee", "left_ankle", "right_ankle"]

# Joint angles extracted per frame (2-D, image plane). Each = (a, vertex, b).
ANGLE_DEFS = {
    "elbow_flex":   ("shoulder", "elbow", "wrist"),     # 180=straight
    "shoulder_elev": ("hip", "shoulder", "elbow"),      # arm raise vs trunk
    "hip_flex":     ("shoulder", "hip", "knee"),        # trunk-thigh
    "knee_flex":    ("hip", "knee", "ankle"),           # 180=straight
}


@dataclass
class Shot:
    index: int
    start_frame: int
    release_frame: int
    end_frame: int
    fps: float
    made: Optional[bool] = None
    score_frame: Optional[int] = None        # frame the ball reached the rim
    path: list = field(default_factory=list)  # ball (x,y) trajectory near the rim
    hoop_box: Optional[tuple] = None          # (cx, cy, w, h) rim used to score
    release_angle: Optional[float] = None     # launch angle at release (deg, from horizontal)

    @property
    def t_release(self) -> float:
        return self.release_frame / self.fps if self.fps else 0.0

    def __repr__(self):
        m = {True: "made", False: "miss", None: "?"}[self.made]
        return (f"Shot#{self.index} frames {self.start_frame}-{self.end_frame} "
                f"(release {self.release_frame}, t={self.t_release:.1f}s, {m})")


# ---------------------------------------------------------------------------
# Ball detection (HSV) — used to confirm the true release frame
# ---------------------------------------------------------------------------
_BALL_HSV = (np.array([5, 120, 80]), np.array([25, 255, 255]),       # orange
             np.array([170, 120, 80]), np.array([180, 255, 255]))    # hue wrap


def _detect_balls(frame, min_area=60, max_area=50000, min_circ=0.55):
    """Return [(x, y, r), ...] candidate round orange blobs in a BGR frame."""
    import cv2
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lo1, hi1, lo2, hi2 = _BALL_HSV
    mask = cv2.inRange(hsv, lo1, hi1) | cv2.inRange(hsv, lo2, hi2)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)
    cs, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in cs:
        a = cv2.contourArea(c)
        if a < min_area or a > max_area:
            continue
        p = cv2.arcLength(c, True)
        if p == 0 or (4 * np.pi * a) / (p * p) < min_circ:
            continue
        (x, y), r = cv2.minEnclosingCircle(c)
        out.append((float(x), float(y), float(r)))
    return out


# ---------------------------------------------------------------------------
# Hoop-based shot/score detection (after Shah, "AI Basketball Shot Detection
# Tracker", github.com/avishah3/AI-Basketball-Shot-Detection-Tracker).
# A ball + hoop are detected each frame; an ATTEMPT is registered when the ball
# goes from an "up" region (above the rim) to a "down" region (below it); a MAKE
# is scored by fitting the ball's path and checking it crosses within the rim.
# ---------------------------------------------------------------------------
def detect_ball_hoop_yolo(video_path, model_path, conf=0.3, every=1):
    """Per-frame best ball & hoop boxes via a YOLO (ultralytics) model trained
    on 'Basketball' + 'Basketball Hoop'. Returns (ball, hoop, fps) where each is
    {frame: (cx, cy, w, h)}. Requires `pip install ultralytics` + a model."""
    import cv2
    from ultralytics import YOLO
    model = YOLO(model_path)
    names = {int(k): str(v).lower() for k, v in model.names.items()}
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    ball, hoop = {}, {}
    fi = 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        if fi % every == 0:
            res = model(fr, verbose=False)[0]
            bb = bh = None
            for b in res.boxes:
                cls = names.get(int(b.cls), "")
                c = float(b.conf)
                if c < conf:
                    continue
                x1, y1, x2, y2 = b.xyxy[0].tolist()
                box = ((x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1, c)
                if "ball" in cls and (bb is None or c > bb[4]):
                    bb = box
                elif ("hoop" in cls or "rim" in cls or "basket" in cls) and (bh is None or c > bh[4]):
                    bh = box
            if bb:
                ball[fi] = bb[:4]
            if bh:
                hoop[fi] = bh[:4]
        fi += 1
    cap.release()
    return ball, hoop, fps


def _score_make(hist, hoop):
    """True if the ball path crosses the rim height within the rim width."""
    cx, cy, w, h = hoop
    rim_y = cy - 0.5 * h
    pts = [(x, y) for (_, x, y) in hist]
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        if (y0 < rim_y <= y1) or (y1 < rim_y <= y0):
            px = x0 + (rim_y - y0) / (y1 - y0) * (x1 - x0) if y1 != y0 else 0.5 * (x0 + x1)
            return (cx - 0.5 * w) < px < (cx + 0.5 * w)
    return False


def detect_shots_via_hoop(ball: dict, hoop: dict, fps: float,
                          follow_through_s: float = 0.4) -> List[Shot]:
    """avishah3 up/down/through-rim logic. ``ball``/``hoop`` = {frame:(cx,cy,w,h)}.
    Returns Shots with ``made`` set (True/False) per the trajectory through the rim.
    The release frame is estimated as the ball's apex just before the rim pass.
    """
    if not ball or not hoop:
        return []
    H = np.median(np.array(list(hoop.values()), float), axis=0)
    cx, cy, w, h = H                                  # static rim estimate
    frames = sorted(ball)
    up = False
    up_f = -1
    hist = []
    shots: List[Shot] = []
    ft = max(1, int(round(fps * follow_through_s)))
    n = 0
    for f in frames:
        x, y = ball[f][0], ball[f][1]
        hist.append((f, x, y)); hist = hist[-40:]
        in_up = (cx - 4 * w < x < cx + 4 * w) and (cy - 2 * h < y < cy - 0.5 * h)
        in_down = y > cy + 0.5 * h
        if not up and in_up:
            up = True; up_f = f
        elif up and in_down:
            made = _score_make(hist, (cx, cy, w, h))
            # release ~ apex of the arc (highest ball) between the shooter and rim
            seg = [(ff, yy) for (ff, xx, yy) in hist if up_f - int(fps) <= ff <= f]
            rel = min(seg, key=lambda t: t[1])[0] if seg else up_f
            n += 1
            shots.append(Shot(index=n, start_frame=int(max(frames[0], rel - int(fps))),
                              release_frame=int(rel), end_frame=int(min(frames[-1], f + ft)),
                              fps=fps, made=bool(made), score_frame=int(f),
                              path=[(xx, yy) for (_, xx, yy) in hist],
                              hoop_box=(float(cx), float(cy), float(w), float(h))))
            up = False
    return shots


def _hsv_ball_track(balls_all: dict, hoop) -> dict:
    """Rough single-ball track from HSV candidates by nearest-neighbour linking
    (re-seeds to the highest blob on a big jump). Returns {frame:(cx,cy,w,h)}.
    Far less reliable than a YOLO ball detector — use --yolo-model when possible.
    """
    track, prev = {}, None
    for f in sorted(balls_all):
        cands = balls_all[f]
        if not cands:
            prev = None
            continue
        if prev is None:
            c = min(cands, key=lambda b: b[1])              # highest blob (in flight)
        else:
            c = min(cands, key=lambda b: (b[0] - prev[0]) ** 2 + (b[1] - prev[1]) ** 2)
            if ((c[0] - prev[0]) ** 2 + (c[1] - prev[1]) ** 2) ** 0.5 > 300:
                c = min(cands, key=lambda b: b[1])
        track[f] = (c[0], c[1], c[2], c[2] * 2)
        prev = c
    return track


def _hand_ball(balls, lm, side):
    """Pick the ball candidate held overhead by the shooter: nearest the
    shooting wrist, within ~2.5x torso, and above the shoulders. Else None."""
    if not balls or lm is None:
        return None
    wr = lm.get(f"{side}_wrist") or lm.get(f"{'left' if side == 'right' else 'right'}_wrist")
    sh = lm.get(f"{side}_shoulder") or lm.get(f"{'left' if side == 'right' else 'right'}_shoulder")
    hip = lm.get(f"{side}_hip")
    if wr is None or sh is None:
        return None
    scale = abs(hip[1] - sh[1]) if hip else abs(wr[1] - sh[1])
    scale = scale or 50.0
    best, bestd = None, 1e9
    for (x, y, r) in balls:
        if y > sh[1]:                       # must be at/above the shoulders
            continue
        d = ((x - wr[0]) ** 2 + (y - wr[1]) ** 2) ** 0.5
        if d < bestd and d < 2.5 * scale:   # near the shooting hand
            bestd, best = d, (x, y, r)
    return best


# ---------------------------------------------------------------------------
# Pose
# ---------------------------------------------------------------------------
def extract_poses(video_path: str, every: int = 1, vis_thresh: float = 0.0,
                  roi_zoom: bool = True, shooting_hand: str = "right",
                  detect_ball: bool = True) -> Tuple[Dict[int, dict], dict, float]:
    """Run BioScout's MediaPipe pose landmarker on a video. Returns (poses, fps).

    poses = {frame_idx: {landmark_name: (x_px, y_px)}}. Uses MovementTracker's
    ``_pose_landmarker`` (Tasks API, num_poses=1). Landmarks are kept in
    full-frame pixel coords. ``roi_zoom`` re-detects on a crop around the last
    detection to better catch a small/distant player (common in game footage).
    """
    import cv2  # noqa
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        import mediapipe as mp
        from record.video import MovementTracker, _LANDMARK_NAMES  # noqa
    except Exception as e:
        raise RuntimeError(
            "Pose extraction needs BioScout's MediaPipe tracker (record.video) "
            f"and mediapipe installed: {e}")

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    tracker = MovementTracker()                      # creates _pose_landmarker
    landmarker = tracker._pose_landmarker

    def _detect(img_bgr, off=(0, 0)):
        h, w = img_bgr.shape[:2]
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB,
                          data=cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
        res = landmarker.detect(mp_img)
        if not res.pose_landmarks:
            return None
        person = res.pose_landmarks[0]
        return {name: (lm.x * w + off[0], lm.y * h + off[1])
                for name, lm in zip(_LANDMARK_NAMES, person)
                if (getattr(lm, "visibility", None) or 0.0) >= vis_thresh}

    side = "right" if shooting_hand.startswith("r") else "left"
    poses: Dict[int, dict] = {}
    balls: Dict[int, tuple] = {}     # {frame: (x, y, r)} ball held overhead at the hand
    last_box = None      # (x1, y1, x2, y2) of last detection, full-frame
    fi = 0
    H = W = None
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if H is None:
            H, W = frame.shape[:2]
        if fi % every == 0:
            lm = _detect(frame)
            # Retry on a zoomed ROI around the last detection if nothing / few points
            if roi_zoom and last_box is not None and (not lm or len(lm) < 8):
                x1, y1, x2, y2 = last_box
                pad_w = (x2 - x1) * 0.6 + 20
                pad_h = (y2 - y1) * 0.6 + 20
                cx1 = max(0, int(x1 - pad_w)); cy1 = max(0, int(y1 - pad_h))
                cx2 = min(W, int(x2 + pad_w)); cy2 = min(H, int(y2 + pad_h))
                crop = frame[cy1:cy2, cx1:cx2]
                if crop.size:
                    lm2 = _detect(crop, off=(cx1, cy1))
                    if lm2 and (not lm or len(lm2) > len(lm)):
                        lm = lm2
            if lm:
                poses[fi] = {k: tuple(v) for k, v in lm.items()}
                xs = [x for x, y in lm.values()]; ys = [y for x, y in lm.values()]
                last_box = (min(xs), min(ys), max(xs), max(ys))
                if detect_ball:
                    cand = _detect_balls(frame)
                    if cand:
                        balls[fi] = cand          # ALL ball candidates this frame
        fi += 1
    cap.release()
    return poses, balls, fps


def load_poses_json(path: str) -> Dict[int, dict]:
    with open(path) as f:
        raw = json.load(f)
    return {int(k): {name: tuple(v) for name, v in lms.items()} for k, lms in raw.items()}


def _series(poses: Dict[int, dict], name: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (frames, x, y) arrays for one landmark (NaN where missing)."""
    fr = np.array(sorted(poses.keys()))
    x = np.full(len(fr), np.nan)
    y = np.full(len(fr), np.nan)
    for i, f in enumerate(fr):
        p = poses[f].get(name)
        if p is not None:
            x[i], y[i] = p[0], p[1]
    return fr, x, y


def _interp_nan(a: np.ndarray) -> np.ndarray:
    a = a.copy()
    m = np.isnan(a)
    if m.all():
        return a
    a[m] = np.interp(np.flatnonzero(m), np.flatnonzero(~m), a[~m])
    return a


# ---------------------------------------------------------------------------
# Shot detection
# ---------------------------------------------------------------------------
def detect_shots(poses: Dict[int, dict], fps: float,
                 shooting_hand: str = "right",
                 min_gap_s: float = 1.0,
                 follow_through_s: float = 0.4,
                 balls: Optional[dict] = None,
                 hoop_side: str = "auto") -> List[Shot]:
    """Detect shot attempts by BALL FLIGHT.

    A release = a ball at the shooter's hand (near the raised wrist, above the
    shoulders, above the head) that, in the next 1-3 frames, travels clearly
    UPWARD and toward the hoop. This rejects gathers/dribbles/pump-fakes (the
    ball doesn't fly to the basket) and the static scoreboard/rack balls.

    ``balls`` = {frame: [(x, y, r), ...]} all candidates per frame.
    ``hoop_side`` 'right' | 'left' | 'auto' (inferred from the ball flight).
    Pose-only ("wrist above head") is the fallback when no ball is available.
    A hard refractory of >=1 s (or ``min_gap_s`` if larger) is enforced.
    """
    fr = np.array(sorted(poses))
    if len(fr) == 0:
        return []
    side = "right" if shooting_hand.startswith("r") else "left"

    def S(name):
        x = np.full(len(fr), np.nan); y = np.full(len(fr), np.nan)
        for i, f in enumerate(fr):
            p = poses[f].get(name)
            if p is not None:
                x[i], y[i] = p[0], p[1]
        return _interp_nan(x), _interp_nan(y)

    nx, ny = S("nose")
    lwx, lwy = S("left_wrist"); rwx, rwy = S("right_wrist")
    shx, shy = S(f"{side}_shoulder"); hpx, hpy = S(f"{side}_hip")
    if np.isnan(ny).all():
        return []
    scale = np.nanmedian(np.abs(hpy - shy))
    if not np.isfinite(scale) or scale <= 0:
        scale = 100.0

    # higher wrist per frame (smaller image-y) = the shooting hand at the set
    use_left = lwy < rwy
    hx = np.where(use_left, lwx, rwx); hy = np.where(use_left, lwy, rwy)
    wrist_top = np.minimum(lwy, rwy)
    raise_sig = ny - wrist_top
    k = max(1, int(round(fps * 0.2)))
    if k > 1:
        raise_sig = np.convolve(raise_sig, np.ones(k) / k, mode="same")

    min_gap = max(1, int(round(fps * max(min_gap_s, 1.0))))
    ft = max(1, int(round(fps * follow_through_s)))
    up_thr = 0.30 * scale       # ball must rise this much after release
    dx_thr = 0.20 * scale       # ...and move this much horizontally to the hoop

    def cand(i):
        return balls.get(int(fr[i]), []) if balls else []

    def hand_ball(i):
        best, bd = None, 2.5 * scale
        for (x, y, r) in cand(i):
            if y > shy[i]:                      # must be above the shoulders
                continue
            d = ((x - hx[i]) ** 2 + (y - hy[i]) ** 2) ** 0.5
            if d < bd:
                bd, best = d, (x, y, r)
        return best

    # ---- Candidate releases: hand-ball above head + subsequent flight ----
    cands = []   # (i, hbx, hby, [dir votes])
    if balls:
        for i in range(len(fr)):
            hb = hand_ball(i)
            if hb is None or hb[1] >= ny[i]:    # ball must be above the head
                continue
            hbx, hby = hb[0], hb[1]
            dirs = []
            for g in (i + 1, i + 2, i + 3):
                if g >= len(fr):
                    break
                for (x, y, r) in cand(g):
                    if y <= hby - up_thr and abs(x - hbx) >= dx_thr:
                        dirs.append(1 if x > hbx else -1)
            if dirs:
                cands.append((i, hbx, hby, dirs))

    releases, ball_h = [], {}
    if cands:
        votes = [d for _, _, _, ds in cands for d in ds]
        hd = (1 if hoop_side == "right" else -1 if hoop_side == "left"
              else (1 if sum(votes) >= 0 else -1))
        for (i, hbx, hby, ds) in cands:
            if any(d == hd for d in ds):
                releases.append(i); ball_h[i] = hby
    else:
        # pose-only fallback: shooting wrist clearly above the head
        above = wrist_top < (ny - 0.05 * scale)
        for i in range(1, len(raise_sig) - 1):
            if above[i] and raise_sig[i] >= raise_sig[i - 1] and raise_sig[i] >= raise_sig[i + 1]:
                releases.append(i)

    # ---- Refractory: >= min_gap, keep the stronger (higher ball / bigger raise)
    def _strength(j):
        return -ball_h[j] if j in ball_h else raise_sig[j]

    releases = sorted(set(int(i) for i in releases))
    merged = []
    for i in releases:
        if merged and (i - merged[-1]) < min_gap:
            if _strength(i) > _strength(merged[-1]):
                merged[-1] = i
        else:
            merged.append(i)

    max_load = int(round(fps * 1.2))
    shots: List[Shot] = []
    for n, pi in enumerate(merged, 1):
        lo = max(0, pi - max_load)
        s = pi
        while s > lo and raise_sig[s - 1] <= raise_sig[s]:
            s -= 1
        s = max(lo, s - min_gap // 2)
        e = min(len(fr) - 1, pi + ft)
        shots.append(Shot(index=n, start_frame=int(fr[s]), release_frame=int(fr[pi]),
                          end_frame=int(fr[e]), fps=fps))
    return shots


# ---------------------------------------------------------------------------
# Kinematics
# ---------------------------------------------------------------------------
def _angle(a, v, b) -> float:
    """Angle at vertex v formed by a-v-b, in degrees (0-180)."""
    va = np.array(a) - np.array(v)
    vb = np.array(b) - np.array(v)
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return np.nan
    c = np.clip(np.dot(va, vb) / (na * nb), -1, 1)
    return float(np.degrees(np.arccos(c)))


def _frame_angles(lm: dict, side: str) -> Dict[str, float]:
    def P(joint):
        return lm.get(f"{side}_{joint}") if joint != "nose" else lm.get("nose")
    out = {}
    for ang, (a, v, b) in ANGLE_DEFS.items():
        pa, pv, pb = P(a), P(v), P(b)
        out[ang] = _angle(pa, pv, pb) if (pa and pv and pb) else np.nan
    return out


def _smooth_resample(y: np.ndarray, n: int, smooth_frac: float = 0.12) -> np.ndarray:
    """Interpolate few raw samples to n points and Gaussian-smooth (no scipy)."""
    y = _interp_nan(np.asarray(y, float))
    if not np.isfinite(y).any():
        return np.full(n, np.nan)
    xs = np.linspace(0, 100, len(y))
    xo = np.linspace(0, 100, n)
    yi = np.interp(xo, xs, y)
    win = max(3, int(n * smooth_frac) | 1)            # odd window
    t = np.linspace(-2.5, 2.5, win)
    ker = np.exp(-0.5 * t * t); ker /= ker.sum()
    pad = win // 2
    yp = np.pad(yi, (pad, pad), mode="edge")
    return np.convolve(yp, ker, mode="valid")[:n]


def shot_kinematics(poses: Dict[int, dict], shot: Shot,
                    side: str = "right", n: int = 1000,
                    smooth_frac: float = 0.12) -> Dict[str, np.ndarray]:
    """Per-shot joint angles, time-normalised + smoothed to n points (0-100%)."""
    frames = [f for f in sorted(poses) if shot.start_frame <= f <= shot.end_frame]
    if len(frames) < 3:
        return {}
    raw = {a: [] for a in ANGLE_DEFS}
    for f in frames:
        fa = _frame_angles(poses[f], side)
        for a in ANGLE_DEFS:
            raw[a].append(fa[a])
    out = {"pct": np.linspace(0, 100, n)}
    for a in ANGLE_DEFS:
        out[a] = _smooth_resample(np.array(raw[a], float), n, smooth_frac)
    return out


# ---------------------------------------------------------------------------
# Muscle forces (kinematics-only surrogate)
# ---------------------------------------------------------------------------
def load_force_model(path: str) -> dict:
    with open(path, "rb") as f:
        return pickle.load(f)


def _relu(x):
    return np.maximum(0, x)


def _predict_forces(model: dict, X: np.ndarray) -> np.ndarray:
    Xs = (X - model["xm"]) / model["xs"]
    a1 = _relu(Xs @ model["W1"] + model["b1"])
    Yz = a1 @ model["W2"] + model["b2"]
    return np.clip(np.expm1(Yz * model["ys"] + model["ym"]), 0, None)


def kinematics_to_model_features(kin: Dict[str, np.ndarray], model: dict,
                                 side: str = "right") -> np.ndarray:
    """Map the 2-D shot angles onto the model's OpenSim feature columns.

    Only the sagittal angles we can see from video are filled; everything else
    is left at the training-set mean (model['xm']). This is a coarse mapping —
    image-plane angles are not OpenSim joint coordinates — hence low fidelity.
    """
    feat = list(model["feat"])
    n = len(kin["pct"])
    X = np.tile(np.asarray(model["xm"], float), (n, 1))   # start at training mean
    s = "r" if side.startswith("r") else "l"
    # video angle -> OpenSim coordinate (degrees, rough sign conventions)
    knee = kin.get("knee_flex")
    hip = kin.get("hip_flex")
    elb = kin.get("elbow_flex")
    sh = kin.get("shoulder_elev")
    mapping = {
        f"knee_angle_{s}":  (knee, lambda v: -(180.0 - v)),   # flexion negative in model
        f"hip_flexion_{s}": (hip,  lambda v: (180.0 - v)),    # more trunk-thigh closing = flexion
        f"elbow_flex_{s}":  (elb,  lambda v: (180.0 - v)),
        f"arm_flex_{s}":    (sh,   lambda v: v),
    }
    for col, (series, fn) in mapping.items():
        if col in feat and series is not None and np.isfinite(series).any():
            X[:, feat.index(col)] = fn(_interp_nan(series))
    # Clamp to the model's training range to curb wild extrapolation on
    # out-of-distribution inputs (image-plane angles are not OpenSim coords).
    xm, xs = np.asarray(model["xm"], float), np.asarray(model["xs"], float)
    X = np.clip(X, xm - 3 * xs, xm + 3 * xs)
    return X


def predict_muscle_forces(kin: Dict[str, np.ndarray], model: dict,
                          side: str = "right", smooth_frac: float = 0.06) -> Dict[str, np.ndarray]:
    X = kinematics_to_model_features(kin, model, side=side)
    Y = _predict_forces(model, X)                 # (n, 80)
    n = len(kin["pct"])
    out = {"pct": kin["pct"]}
    for j, name in enumerate(model["targ"]):
        out[name] = _smooth_resample(Y[:, j], n, smooth_frac)   # tidy MLP jitter
    return out


# ---------------------------------------------------------------------------
# Plots & tagging
# ---------------------------------------------------------------------------
def plot_kinematics(shots_kin: List[Dict[str, np.ndarray]], shots: List[Shot],
                    out_path: str):
    angles = list(ANGLE_DEFS)
    fig, ax = plt.subplots(1, len(angles), figsize=(4 * len(angles), 3.4), squeeze=False)
    cmap = matplotlib.colormaps["tab10"]
    for j, ang in enumerate(angles):
        a = ax[0, j]
        for k, (kin, sh) in enumerate(zip(shots_kin, shots)):
            if ang in kin:
                lbl = f"#{sh.index} {'miss' if sh.made is False else ('made' if sh.made else '?')}"
                ls = "--" if sh.made is False else "-"
                a.plot(kin["pct"], kin[ang], color=cmap(k % 10), ls=ls, label=lbl)
        a.set_title(ang); a.set_xlabel("% shot")
        if j == 0:
            a.set_ylabel("angle (deg)")
        a.legend(fontsize=6)
    fig.suptitle("Per-shot kinematics (0-100%)", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def plot_muscle_forces(shots_forces: List[Dict[str, np.ndarray]], shots: List[Shot],
                       out_path: str, muscles: Optional[List[str]] = None):
    if not shots_forces:
        return
    if muscles is None:
        muscles = ["vaslat_r", "recfem_r", "gasmed_r", "soleus_r",
                   "glmax2_r", "bflh_r"]
    muscles = [m for m in muscles if m in shots_forces[0]]
    fig, ax = plt.subplots(1, len(muscles), figsize=(3.2 * len(muscles), 3.2), squeeze=False)
    cmap = matplotlib.colormaps["tab10"]
    for j, m in enumerate(muscles):
        a = ax[0, j]
        for k, (ff, sh) in enumerate(zip(shots_forces, shots)):
            a.plot(ff["pct"], ff[m], color=cmap(k % 10),
                   ls="--" if sh.made is False else "-", label=f"#{sh.index}")
        a.set_title(m); a.set_xlabel("% shot")
        if j == 0:
            a.set_ylabel("force (N)")
        a.legend(fontsize=6)
    fig.suptitle("Per-shot muscle forces (kinematics-only surrogate — low fidelity)", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def write_shots_csv(shots: List[Shot], path: str):
    """One row per attempt; 'made' left blank for assisted tagging (1/0)."""
    import csv
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["shot", "start_frame", "release_frame", "end_frame",
                    "t_release_s", "release_angle_deg", "made"])
        for s in shots:
            w.writerow([s.index, s.start_frame, s.release_frame, s.end_frame,
                        f"{s.t_release:.2f}",
                        "" if s.release_angle is None else f"{s.release_angle:.1f}",
                        "" if s.made is None else (1 if s.made else 0)])


def load_tags(shots: List[Shot], path: str) -> List[Shot]:
    """Read a filled shots.csv ('made' = 1/0) back onto the shots."""
    import csv
    if not os.path.exists(path):
        return shots
    tags = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            v = (row.get("made") or "").strip()
            if v != "":
                tags[int(row["shot"])] = v in ("1", "true", "True", "made", "y", "yes")
    for s in shots:
        if s.index in tags:
            s.made = tags[s.index]
    return shots


def save_release_thumbnails(video_path: str, shots: List[Shot], out_dir: str):
    """Save the release frame of each shot to help manual made/missed tagging."""
    import cv2
    os.makedirs(out_dir, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    want = {s.release_frame: s.index for s in shots}
    fi = 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        if fi in want:
            cv2.imwrite(os.path.join(out_dir, f"shot_{want[fi]:02d}_release.png"), fr)
        fi += 1
    cap.release()


def _predict_cross(path, rim_y):
    """x where the ball path crosses rim_y (linear interp on the straddling pair)."""
    for (x0, y0), (x1, y1) in zip(path, path[1:]):
        if (y0 < rim_y <= y1) or (y1 < rim_y <= y0):
            return x0 + (rim_y - y0) / (y1 - y0) * (x1 - x0) if y1 != y0 else 0.5 * (x0 + x1)
    return None


def save_score_frames(video_path: str, shots: List[Shot], out_dir: str):
    """For each hoop-scored shot, draw the rim, the ball path and the predicted
    rim crossing on the frame the ball reached the hoop, label IN/OUT, and save."""
    import cv2
    scored = [s for s in shots if s.score_frame is not None and s.hoop_box]
    if not scored:
        return
    os.makedirs(out_dir, exist_ok=True)
    want = {int(s.score_frame): s for s in scored}
    cap = cv2.VideoCapture(video_path)
    fi = 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        if fi in want:
            s = want[fi]
            img = fr.copy()
            cx, cy, w, h = (int(round(v)) for v in s.hoop_box)
            made = bool(s.made)
            col = (0, 200, 0) if made else (0, 0, 255)       # BGR: green / red
            rim_y = int(round(cy - 0.5 * h))
            cv2.rectangle(img, (cx - w // 2, cy - h // 2), (cx + w // 2, cy + h // 2),
                          (0, 165, 255), 2)
            cv2.line(img, (cx - w // 2, rim_y), (cx + w // 2, rim_y), (0, 165, 255), 2)
            pts = [(int(round(x)), int(round(y))) for (x, y) in s.path]
            for a, b in zip(pts, pts[1:]):
                cv2.line(img, a, b, col, 2)
            for p in pts:
                cv2.circle(img, p, 3, col, -1)
            px = _predict_cross(s.path, rim_y)
            if px is not None:
                cv2.circle(img, (int(round(px)), rim_y), 7, col, 2)
            label = "IN" if made else "OUT"
            cv2.putText(img, f"Shot {s.index}: {label}", (30, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.3, col, 3, cv2.LINE_AA)
            cv2.imwrite(os.path.join(out_dir, f"shot_{s.index:02d}_{label}.png"), img)
        fi += 1
    cap.release()


# Skeleton edges (subset of MediaPipe pose connections we use).
_SKELETON = [("nose", "left_shoulder"), ("nose", "right_shoulder"),
             ("left_shoulder", "right_shoulder"),
             ("left_shoulder", "left_elbow"), ("left_elbow", "left_wrist"),
             ("right_shoulder", "right_elbow"), ("right_elbow", "right_wrist"),
             ("left_shoulder", "left_hip"), ("right_shoulder", "right_hip"),
             ("left_hip", "right_hip"),
             ("left_hip", "left_knee"), ("left_knee", "left_ankle"),
             ("right_hip", "right_knee"), ("right_knee", "right_ankle")]


def release_angle_from_poses(poses, rel_frame, side):
    """Launch angle (deg from horizontal) from the shooting wrist's motion
    across the release frame. Positive = upward."""
    import math
    def wrist(f):
        return poses.get(f, {}).get(f"{side}_wrist")
    before = after = None
    for d in range(1, 6):
        if before is None and wrist(rel_frame - d):
            before = rel_frame - d
        if after is None and wrist(rel_frame + d):
            after = rel_frame + d
    a = wrist(before) if before is not None else wrist(rel_frame)
    b = wrist(after) if after is not None else wrist(rel_frame)
    if not a or not b or (a[0] == b[0] and a[1] == b[1]):
        return None
    return math.degrees(math.atan2(-(b[1] - a[1]), (b[0] - a[0])))   # y grows down


def _draw_pose_panel(img, lm, side, release_angle=None):
    """Draw the stick figure, per-joint angles, and the release-angle arrow."""
    import cv2, math

    def P(name):
        v = lm.get(name)
        return (int(round(v[0])), int(round(v[1]))) if v else None

    for a, b in _SKELETON:
        pa, pb = P(a), P(b)
        if pa and pb:
            cv2.line(img, pa, pb, (0, 255, 255), 2, cv2.LINE_AA)
    for name in LMS:
        p = P(name)
        if p:
            cv2.circle(img, p, 4, (0, 180, 255), -1)
    fa = _frame_angles(lm, side)
    for ang, jn in (("elbow_flex", "elbow"), ("shoulder_elev", "shoulder"),
                    ("hip_flex", "hip"), ("knee_flex", "knee")):
        p = P(f"{side}_{jn}")
        if p and np.isfinite(fa.get(ang, np.nan)):
            cv2.putText(img, f"{fa[ang]:.0f}", (p[0] + 6, p[1] - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
    wr = P(f"{side}_wrist")
    if wr and release_angle is not None:
        rad = math.radians(release_angle)
        tip = (int(wr[0] + 90 * math.cos(rad)), int(wr[1] - 90 * math.sin(rad)))
        cv2.arrowedLine(img, wr, tip, (0, 255, 0), 3, tipLength=0.3)
        cv2.putText(img, f"release {release_angle:.0f} deg", (wr[0] - 30, wr[1] - 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
    return img


def _draw_score_panel(img, s):
    """Draw rim + ball path + predicted crossing + IN/OUT onto a frame copy."""
    import cv2
    if not s.hoop_box:
        return img
    cx, cy, w, h = (int(round(v)) for v in s.hoop_box)
    made = bool(s.made)
    col = (0, 200, 0) if made else (0, 0, 255)
    rim_y = int(round(cy - 0.5 * h))
    cv2.rectangle(img, (cx - w // 2, cy - h // 2), (cx + w // 2, cy + h // 2), (0, 165, 255), 2)
    cv2.line(img, (cx - w // 2, rim_y), (cx + w // 2, rim_y), (0, 165, 255), 2)
    pts = [(int(round(x)), int(round(y))) for (x, y) in s.path]
    for a, b in zip(pts, pts[1:]):
        cv2.line(img, a, b, col, 2)
    for p in pts:
        cv2.circle(img, p, 3, col, -1)
    px = _predict_cross(s.path, rim_y)
    if px is not None:
        cv2.circle(img, (int(round(px)), rim_y), 7, col, 2)
    cv2.putText(img, f"Shot {s.index}: {'IN' if made else 'OUT'}", (30, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, col, 3, cv2.LINE_AA)
    return img


def save_shot_summary_frames(video_path, shots, poses, out_dir, side="right"):
    """Per shot, a side-by-side card: release (stick figure + joint angles +
    release angle)  |  shot path (rim + trajectory + IN/OUT). -> shot_NN_card.png"""
    import cv2
    os.makedirs(out_dir, exist_ok=True)
    need = set()
    for s in shots:
        need.add(int(s.release_frame))
        if s.score_frame is not None:
            need.add(int(s.score_frame))
    cap = cv2.VideoCapture(video_path)
    cache, fi = {}, 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        if fi in need:
            cache[fi] = fr
        fi += 1
    cap.release()

    for s in shots:
        rel = int(s.release_frame)
        if rel not in cache:
            continue
        left = cache[rel].copy()
        lm = poses.get(rel) or (poses.get(min(poses, key=lambda f: abs(f - rel))) if poses else None)
        ra = s.release_angle if s.release_angle is not None else release_angle_from_poses(poses, rel, side)
        if lm:
            _draw_pose_panel(left, lm, side, ra)
        cv2.putText(left, f"Shot {s.index} release (t={s.t_release:.2f}s)", (20, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
        if s.score_frame is not None and int(s.score_frame) in cache and s.hoop_box:
            right = _draw_score_panel(cache[int(s.score_frame)].copy(), s)
        else:
            right = np.zeros_like(left)
            cv2.putText(right, "no shot path", (40, right.shape[0] // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (150, 150, 150), 2, cv2.LINE_AA)
        H = min(left.shape[0], right.shape[0])

        def _rs(im):
            sc = H / im.shape[0]
            return cv2.resize(im, (int(im.shape[1] * sc), H))
        combo = np.hstack([_rs(left), _rs(right)])
        cv2.imwrite(os.path.join(out_dir, f"shot_{s.index:02d}_card.png"), combo)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def analyze_video(video_path: str, out_dir: Optional[str] = None,
                  shooting_hand: str = "right", poses=None,
                  model_path: Optional[str] = None, fps: Optional[float] = None,
                  min_gap_s: float = 1.0, n_points: int = 1000,
                  smooth_frac: float = 0.12, hoop_side: str = "auto",
                  yolo_model: Optional[str] = None,
                  hoop: Optional[tuple] = None) -> dict:
    """Full prototype pipeline. Returns a dict summary; writes figures + CSV.

    fps: override the video frame rate (e.g. footage exported at 5 fps). When
    None it is read from the file. Detection/segmentation timing uses it.
    """
    try:
        from utils.logger import logger
    except Exception:
        import logging
        logger = logging.getLogger("bioscout.shots")
        logging.basicConfig(level=logging.INFO)

    out_dir = out_dir or os.path.join(os.path.dirname(os.path.abspath(video_path)),
                                      Path(video_path).stem + "_shots")
    os.makedirs(out_dir, exist_ok=True)
    side = "right" if shooting_hand.startswith("r") else "left"

    def _file_fps():
        import cv2
        return cv2.VideoCapture(video_path).get(cv2.CAP_PROP_FPS) or 30.0

    # 1. poses (+ ball held overhead at the hand)
    balls: dict = {}
    if poses is None:
        poses, balls, detected_fps = extract_poses(video_path, shooting_hand=shooting_hand)
    elif isinstance(poses, str):
        sib = os.path.join(os.path.dirname(poses), "balls.json")
        poses = load_poses_json(poses)
        if os.path.exists(sib):
            with open(sib) as f:
                balls = {int(k): [tuple(b) for b in v] for k, v in json.load(f).items()}
        detected_fps = _file_fps()
    else:
        detected_fps = _file_fps()
    if fps is None:
        fps = detected_fps
    elif abs(fps - detected_fps) > 0.5:
        logger.info(f"Using fps override {fps:.2f} (file reports {detected_fps:.2f})")
    logger.info(f"Poses: {len(poses)} frames @ {fps:.2f} fps  |  ball-at-hand: {len(balls)} frames")

    # Cache poses + ball so detection can be re-tuned WITHOUT re-running MediaPipe
    # (re-run with --poses <poses.json>; balls.json is picked up automatically).
    try:
        with open(os.path.join(out_dir, "poses.json"), "w") as f:
            json.dump({str(k): {n: list(v) for n, v in lm.items()}
                       for k, lm in poses.items()}, f)
        with open(os.path.join(out_dir, "balls.json"), "w") as f:
            json.dump({str(k): [list(b) for b in v] for k, v in balls.items()}, f)
    except Exception as e:
        logger.info(f"(poses/balls cache not saved: {e})")

    # 2. shots — prefer the hoop-based method (avishah3) when a hoop is available
    #    (YOLO ball+hoop, or HSV ball + a manually supplied --hoop box); otherwise
    #    fall back to the pose+ball-flight method.
    method = "flight"
    if yolo_model and os.path.exists(yolo_model):
        try:
            btr, htr, dfps = detect_ball_hoop_yolo(video_path, yolo_model)
            if fps is None or abs(fps - dfps) < 0.01:
                fps = fps or dfps
            shots = detect_shots_via_hoop(btr, htr, fps)
            method = f"hoop/YOLO ({len(btr)} ball, {len(htr)} hoop frames)"
        except Exception as e:
            logger.error(f"YOLO hoop detection failed ({e}); using flight method")
            shots = detect_shots(poses, fps, shooting_hand=shooting_hand,
                                 min_gap_s=min_gap_s, balls=balls, hoop_side=hoop_side)
    elif hoop is not None:
        # HSV best-ball-per-frame (nearest to the rolling track) + manual hoop box
        btr = _hsv_ball_track(balls, hoop)
        shots = detect_shots_via_hoop(btr, {f: tuple(hoop) for f in btr}, fps)
        method = f"hoop/HSV+manual ({len(btr)} ball frames)"
    else:
        shots = detect_shots(poses, fps, shooting_hand=shooting_hand,
                             min_gap_s=min_gap_s, balls=balls, hoop_side=hoop_side)
    logger.info(f"Shot detection method: {method}")
    logger.info(f"Detected {len(shots)} shot attempt(s)")
    for s in shots:
        logger.info(f"  {s}")

    # Release (launch) angle from the shooting wrist's motion at release
    for s in shots:
        s.release_angle = release_angle_from_poses(poses, int(s.release_frame), side)

    # Assisted tagging: preserve any existing 'made' tags, always (re)write the
    # CSV for the current shots, and always (re)save the release thumbnails.
    csv_path = os.path.join(out_dir, "shots.csv")
    shots = load_tags(shots, csv_path)        # no-op if file missing
    write_shots_csv(shots, csv_path)
    rf_dir = os.path.join(out_dir, "release_frames")
    try:
        save_release_thumbnails(video_path, shots, rf_dir)
        # hoop method also annotates the rim-pass frame with the path + IN/OUT
        save_score_frames(video_path, shots, rf_dir)
        # combined card: release (stick figure + joint/release angles) | shot path
        save_shot_summary_frames(video_path, shots, poses, rf_dir, side=side)
    except Exception as e:
        logger.info(f"(annotated frames skipped: {e})")

    # 3. kinematics
    kins = [shot_kinematics(poses, s, side=side, n=n_points, smooth_frac=smooth_frac)
            for s in shots]
    kins_ok = [(k, s) for k, s in zip(kins, shots) if k]
    if kins_ok:
        plot_kinematics([k for k, _ in kins_ok], [s for _, s in kins_ok],
                        os.path.join(out_dir, "kinematics.png"))

    # 4. muscle forces (optional, low fidelity)
    forces = []
    if model_path and os.path.exists(model_path) and kins_ok:
        model = load_force_model(model_path)
        forces = [predict_muscle_forces(k, model, side=side) for k, _ in kins_ok]
        plot_muscle_forces(forces, [s for _, s in kins_ok],
                           os.path.join(out_dir, "muscle_forces.png"))

    made = sum(1 for s in shots if s.made is True)
    missed = sum(1 for s in shots if s.made is False)
    logger.info(f"Output -> {out_dir}  (attempts={len(shots)}, made={made}, missed={missed}, "
                f"untagged={len(shots) - made - missed})")
    return {"out_dir": out_dir, "fps": fps, "shots": shots,
            "kinematics": kins, "forces": forces,
            "made": made, "missed": missed, "attempts": len(shots)}
