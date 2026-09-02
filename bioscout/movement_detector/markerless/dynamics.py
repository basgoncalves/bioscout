"""
dynamics.py -- sagittal inverse dynamics for a bodyweight squat.

Joint moments computed from kinematics and body mass alone, no force plate.
The chain is standard Newton-Euler, bottom-up from the foot:

    ground reaction  ->  ankle  ->  knee  ->  hip

What makes this defensible without a force plate is that the ground reaction is
not guessed: for a body in contact with the ground, Newton's second law applied
to the WHOLE body gives  GRF = m * (a_com + g)  exactly. The whole-body centre
of mass is a mass-weighted sum of segment centres, all of which the camera
measures. So the resultant force is derived, not assumed.

What IS assumed, and where the error lives:
  * The centre of pressure sits under the midfoot. Without a plate its true
    path is unknown; this mostly affects the ankle moment and propagates
    upward, though the knee and hip are dominated by the much larger
    thigh/trunk terms.
  * Left and right are symmetric, so each leg takes half the ground reaction.
    A single camera cannot see asymmetry, and a squat with a visible lean will
    violate this.
  * Everything is planar. Out-of-plane motion is invisible and unmodelled.

Segment inertial parameters follow Winter, "Biomechanics and Motor Control of
Human Movement" (4th ed.), Table 4.1.
"""
from __future__ import annotations

import numpy as np

G = 9.80665

#: Winter Table 4.1. mass = fraction of body mass; com = fraction of segment
#: length from the PROXIMAL joint; rg = radius of gyration about the segment
#: COM, as a fraction of segment length.
SEGMENTS = {
    "foot":  {"mass": 0.0145, "com": 0.50,  "rg": 0.475},
    "shank": {"mass": 0.0465, "com": 0.433, "rg": 0.302},
    "thigh": {"mass": 0.1000, "com": 0.433, "rg": 0.323},
    # Head + arms + trunk, treated as one rigid segment from hip to shoulder.
    "hat":   {"mass": 0.6780, "com": 0.626, "rg": 0.496},
}


def _smooth(x, win):
    """Moving average that preserves the ends, applied before differentiating.

    Double differentiation amplifies pose jitter enormously -- an untreated
    0.5 px wobble at 50 fps becomes hundreds of m/s^2 -- so this is not
    cosmetic.
    """
    x = np.asarray(x, float)
    if win < 3 or len(x) < win:
        return x
    if win % 2 == 0:
        win += 1
    pad = win // 2
    padded = np.concatenate([np.full(pad, x[0]), x, np.full(pad, x[-1])])
    return np.convolve(padded, np.ones(win) / win, mode="valid")


def _deriv(x, dt):
    """Central difference, one-sided at the ends."""
    x = np.asarray(x, float)
    d = np.empty_like(x)
    if len(x) < 2:
        return np.zeros_like(x)
    d[1:-1] = (x[2:] - x[:-2]) / (2 * dt)
    d[0] = (x[1] - x[0]) / dt
    d[-1] = (x[-1] - x[-2]) / dt
    return d


class Segment:
    """One rigid body: endpoints in metres, world frame, y up."""

    def __init__(self, name, prox, dist, mass_kg, dt, smooth_win):
        p = SEGMENTS[name]
        self.name = name
        self.mass = p["mass"] * mass_kg
        self.prox = prox          # (n, 2)
        self.dist = dist
        length = np.median(np.hypot(*(prox - dist).T))
        self.length = float(length)
        self.inertia = self.mass * (p["rg"] * self.length) ** 2

        # centre of mass, then its acceleration
        self.com = prox + p["com"] * (dist - prox)
        cx = _smooth(self.com[:, 0], smooth_win)
        cy = _smooth(self.com[:, 1], smooth_win)
        self.acc = np.column_stack([_deriv(_deriv(cx, dt), dt),
                                    _deriv(_deriv(cy, dt), dt)])

        # segment angle (from +x, CCW positive) and its second derivative
        d = dist - prox
        ang = np.unwrap(np.arctan2(d[:, 1], d[:, 0]))
        ang = _smooth(ang, smooth_win)
        self.alpha = _deriv(_deriv(ang, dt), dt)


def _cross_z(r, f):
    """z component of r x f for planar vectors."""
    return r[:, 0] * f[:, 1] - r[:, 1] * f[:, 0]


def inverse_dynamics(coords_m, mass_kg, fps, smooth_win=9, bar_mass_kg=0.0):
    """Joint moments for one rep.

    coords_m: dict of (n, 2) arrays in METRES, world frame, y up, with keys
        ankle, knee, hip, shoulder, toe.
    Returns {ankle_moment, knee_moment, hip_moment, grf_vertical, grf_horizontal,
             com_y} -- moments in N*m per leg, extension POSITIVE; forces in N
             for both legs together.
    """
    dt = 1.0 / fps
    ankle = np.asarray(coords_m["ankle"], float)
    knee = np.asarray(coords_m["knee"], float)
    hip = np.asarray(coords_m["hip"], float)
    shoulder = np.asarray(coords_m["shoulder"], float)
    toe = np.asarray(coords_m["toe"], float)
    n = len(ankle)

    total_mass = mass_kg + bar_mass_kg
    segs = {
        "foot": Segment("foot", ankle, toe, mass_kg, dt, smooth_win),
        "shank": Segment("shank", knee, ankle, mass_kg, dt, smooth_win),
        "thigh": Segment("thigh", hip, knee, mass_kg, dt, smooth_win),
        "hat": Segment("hat", hip, shoulder, mass_kg, dt, smooth_win),
    }
    # Two legs: the leg segments each exist twice.
    seg_mass = {"foot": 2, "shank": 2, "thigh": 2, "hat": 1}

    # Whole-body COM, and the ground reaction that its acceleration implies.
    m_tot = sum(segs[k].mass * seg_mass[k] for k in segs)
    com = sum(segs[k].com * segs[k].mass * seg_mass[k] for k in segs) / m_tot
    com_x = _smooth(com[:, 0], smooth_win)
    com_y = _smooth(com[:, 1], smooth_win)
    com_acc = np.column_stack([_deriv(_deriv(com_x, dt), dt),
                               _deriv(_deriv(com_y, dt), dt)])
    if bar_mass_kg:
        # A bar on the shoulders rides with the trunk's distal end.
        bx = _smooth(shoulder[:, 0], smooth_win)
        by = _smooth(shoulder[:, 1], smooth_win)
        bar_acc = np.column_stack([_deriv(_deriv(bx, dt), dt),
                                   _deriv(_deriv(by, dt), dt)])
        com_acc = (m_tot * com_acc + bar_mass_kg * bar_acc) / total_mass

    grf = np.column_stack([total_mass * com_acc[:, 0],
                           total_mass * (com_acc[:, 1] + G)])

    # Centre of pressure: assumed under the midfoot. See the module docstring.
    cop = ankle + 0.5 * (toe - ankle)
    cop[:, 1] = np.minimum(ankle[:, 1], toe[:, 1])

    half = 0.5

    # Newton-Euler, bottom-up. F_x is the force ON the distal segment FROM the
    # next one up; M_x likewise. Each moment balance is taken about that
    # segment's own centre of mass, and the reaction onto the next segment is
    # the negation of both.
    #
    #   sum F = m a           sum M_about_com = I alpha
    #
    # Getting these signs right matters more than it looks: an error flips a
    # joint from extensor to flexor while leaving the magnitude plausible, so
    # it survives a "does the number look about right" check. test_dynamics.py
    # pins them against a hand-computed static pose instead.

    # --- foot: ground reaction in, ankle reaction out ----------------------
    f = segs["foot"]
    W_f = np.column_stack([np.zeros(n), np.full(n, f.mass * G)])
    F_ankle = f.mass * f.acc - half * grf + W_f
    M_ankle = (f.inertia * f.alpha
               - _cross_z(cop - f.com, half * grf)
               - _cross_z(ankle - f.com, F_ankle))

    # --- shank -------------------------------------------------------------
    s_ = segs["shank"]
    W_s = np.column_stack([np.zeros(n), np.full(n, s_.mass * G)])
    F_knee = s_.mass * s_.acc + F_ankle + W_s
    M_knee = (s_.inertia * s_.alpha
              + M_ankle
              + _cross_z(ankle - s_.com, F_ankle)
              - _cross_z(knee - s_.com, F_knee))

    # --- thigh -------------------------------------------------------------
    t = segs["thigh"]
    W_t = np.column_stack([np.zeros(n), np.full(n, t.mass * G)])
    F_hip = t.mass * t.acc + F_knee + W_t
    M_hip = (t.inertia * t.alpha
             + M_knee
             + _cross_z(knee - t.com, F_knee)
             - _cross_z(hip - t.com, F_hip))

    # Which way is the subject facing? Toes point forward, so the sign of
    # (toe_x - ankle_x) gives it. Mirroring the camera or turning around must
    # not flip an extensor moment into a flexor one.
    facing = np.sign(np.median(toe[:, 0] - ankle[:, 0])) or 1.0

    # Report EXTENSION as positive at every joint. The raw values are CCW
    # z-moments, so the anatomical sense depends on which segment each moment
    # acts upon: M_knee acts on the SHANK, whose extension rotates it opposite
    # to the thigh about the same axis, so the knee takes the opposite sign to
    # the hip and ankle. This is a declared convention, not a derived one --
    # test_dynamics.py pins it against a hand-computed static pose.
    #
    # Note a genuine physical result that looks like a bug: in a SHALLOW squat
    # the ground reaction can pass in front of the knee, giving a small FLEXOR
    # moment, which grows into a large extensor moment as depth increases. A
    # sign change with depth is expected here.
    return {
        "ankle_moment": -facing * M_ankle,
        "knee_moment": +facing * M_knee,
        "hip_moment": -facing * M_hip,
        "facing": float(facing),
        "grf_vertical": grf[:, 1],
        "grf_horizontal": grf[:, 0],
        "com_y": com_y,
        "body_weight_n": total_mass * G,
    }
