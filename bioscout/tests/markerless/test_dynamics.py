"""
Pin the inverse-dynamics signs and magnitudes against hand calculations.

A sign error flips a joint from extensor to flexor while leaving the magnitude
entirely plausible, so it survives any "looks about right" inspection. These
checks are the thing standing between that and a published number.

    python -m bioscout.tests.markerless.test_dynamics
"""
import math
import sys

import numpy as np

from bioscout.movement_detector.markerless.dynamics import G, inverse_dynamics
from bioscout.movement_detector.markerless.kinematics import compute_px_per_m
from bioscout.movement_detector.markerless.squat import (
    SquatConfig, build_squat_features, find_squat_reps, joint_positions_m)

from .test_squat import synth_squats

MASS = 75.0
FAILURES = []


def expect(cond, msg):
    print("  [%s] %s" % ("OK  " if cond else "FAIL", msg))
    if not cond:
        FAILURES.append(msg)


def static_pose(knee_flex_deg, n=90, facing=+1):
    """A subject frozen in one posture, repeated so derivatives are zero."""
    poses = {}
    from .test_squat import synth_squats as _s
    one = _s(n_reps=1, peak_knee=knee_flex_deg, rest_frames=0, rep_frames=2)
    # take the deepest frame and hold it
    deepest = max(one, key=lambda k: one[k]["left_hip"][1])
    lm = one[deepest]
    if facing < 0:                       # mirror about x
        lm = {k: (-v[0], v[1]) for k, v in lm.items()}
    for i in range(n):
        poses[i] = lm
    return poses


def run(poses, fps=30.0):
    F = build_squat_features(poses)
    px, _ = compute_px_per_m(poses, 1.75)
    n = F["_n"]
    pos = joint_positions_m(F, (0, n // 2, n - 1), px, F["_floor_y"])
    return inverse_dynamics(pos, MASS, fps), pos


def main():
    print("static deep squat: accelerations are zero, so this is pure statics")
    d, pos = run(static_pose(115))
    bw = MASS * G
    mid = len(d["knee_moment"]) // 2

    expect(abs(d["grf_vertical"][mid] - bw) < 0.02 * bw,
           "vertical GRF %.0f N equals body weight %.0f N when still"
           % (d["grf_vertical"][mid], bw))
    expect(abs(d["grf_horizontal"][mid]) < 0.02 * bw,
           "horizontal GRF %.1f N is ~zero when still" % d["grf_horizontal"][mid])

    km, hm, am = (d["knee_moment"][mid], d["hip_moment"][mid],
                  d["ankle_moment"][mid])
    print("     knee %+.1f Nm   hip %+.1f Nm   ankle %+.1f Nm" % (km, hm, am))
    expect(km > 0, "knee moment is EXTENSOR (positive) in a held deep squat")
    expect(hm > 0, "hip moment is EXTENSOR (positive) in a held deep squat")

    # Hand check: the external moment about the knee from half the ground
    # reaction, minus the small weight of the shank and foot below it.
    half_grf = 0.5 * bw
    arm = pos["knee"][mid, 0] - pos["ankle"][mid, 0] - 0.5 * (
        pos["toe"][mid, 0] - pos["ankle"][mid, 0])
    hand = abs(half_grf * arm)
    print("     hand-computed knee moment from GRF x moment arm: %.1f Nm" % hand)
    expect(abs(abs(km) - hand) < max(12.0, 0.30 * hand),
           "computed knee moment %.1f Nm agrees with the hand figure %.1f Nm"
           % (abs(km), hand))

    print("\ndepth scaling: deeper squat must demand a larger knee extensor moment")
    shallow = run(static_pose(55))[0]["knee_moment"][45]
    deep = run(static_pose(115))[0]["knee_moment"][45]
    print("     55 deg knee flexion -> %+.1f Nm ;  115 deg -> %+.1f Nm"
          % (shallow, deep))
    # A small FLEXOR moment when shallow is physical, not a bug: the ground
    # reaction can pass in front of the knee. What must hold is that depth
    # drives a large EXTENSOR demand.
    expect(deep > 0, "deep squat knee moment %+.1f Nm is extensor" % deep)
    expect(deep > abs(shallow) + 10.0,
           "extensor demand grows sharply with depth (%.1f vs %.1f Nm)"
           % (deep, abs(shallow)))

    print("\nmirroring the camera must not flip extensor into flexor")
    left = run(static_pose(115, facing=+1))[0]
    right = run(static_pose(115, facing=-1))[0]
    print("     facing +x: knee %+.1f Nm (facing=%+.0f)"
          % (left["knee_moment"][45], left["facing"]))
    print("     facing -x: knee %+.1f Nm (facing=%+.0f)"
          % (right["knee_moment"][45], right["facing"]))
    expect(left["knee_moment"][45] > 0 and right["knee_moment"][45] > 0,
           "knee is extensor whichever way the subject faces")
    expect(abs(left["knee_moment"][45] - right["knee_moment"][45]) < 1.0,
           "the two mirrored poses give the same magnitude")

    print("\nmoving squat: magnitudes must stay physiological")
    poses = synth_squats(n_reps=2, peak_knee=115)
    F = build_squat_features(poses)
    px, _ = compute_px_per_m(poses, 1.75)
    reps, _ = find_squat_reps(F, SquatConfig())
    dm = inverse_dynamics(joint_positions_m(F, reps[0], px, F["_floor_y"]),
                          MASS, 30.0)
    for k in ("ankle_moment", "knee_moment", "hip_moment"):
        peak = float(np.max(np.abs(dm[k]))) / MASS
        print("     %-13s peak %.2f Nm/kg" % (k, peak))
        expect(peak < 4.0, "%s peak %.2f Nm/kg is physiological (<4)" % (k, peak))
    gv = dm["grf_vertical"] / dm["body_weight_n"]
    print("     vertical GRF %.2f .. %.2f BW" % (gv.min(), gv.max()))
    expect(0.3 < gv.min() and gv.max() < 3.0,
           "GRF stays in a plausible 0.3-3 BW band")

    print("\n%s" % ("FAILED:\n  " + "\n  ".join(FAILURES)
                    if FAILURES else "ALL CHECKS PASSED"))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
