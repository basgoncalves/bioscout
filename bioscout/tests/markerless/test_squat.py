"""
Squat pipeline check on synthetic kinematics.

No squat video exists yet, so this builds a stick figure that performs a known
number of squats to a known depth, runs it through the pipeline, and asserts
the detector finds them and recovers the joint angles it was given. It also
prints how far each model input sits from the gait training distribution, which
is the number that decides whether the force prediction means anything.

    python -m bioscout.tests.markerless.test_squat
"""
import math
import sys

import numpy as np

from bioscout.movement_detector.markerless.forces import (
    Validity, load_model, summarise)
from bioscout.movement_detector.markerless.session import analyse

FPS = 30.0
N_REPS = 3
PEAK_KNEE = 115.0     # deg of knee flexion at the bottom
PX_PER_M = 200.0
HEIGHT_M = 1.75

FAILURES = []


def expect(cond, msg):
    print("  [%s] %s" % ("OK  " if cond else "FAIL", msg))
    if not cond:
        FAILURES.append(msg)


def synth_squats(n_reps=N_REPS, peak_knee=PEAK_KNEE, rest_frames=20,
                 rep_frames=60):
    """A sagittal stick figure squatting, in pixel coordinates.

    Segment lengths follow Winter fractions of a 1.75 m stature so the
    pipeline's own px->m scaling has something consistent to find.
    """
    thigh = 0.245 * HEIGHT_M * PX_PER_M
    shank = 0.246 * HEIGHT_M * PX_PER_M
    trunk = 0.288 * HEIGHT_M * PX_PER_M
    upper_arm = 0.186 * HEIGHT_M * PX_PER_M
    forearm = 0.146 * HEIGHT_M * PX_PER_M
    foot = 0.152 * HEIGHT_M * PX_PER_M

    poses = {}
    frame = 0
    ankle = (300.0, 800.0)   # fixed on the floor

    def emit(knee_flex):
        # Shank rotates forward by a fraction of knee flexion (dorsiflexion),
        # thigh takes the remainder. Trunk leans to keep it balanced-ish.
        dorsi = math.radians(0.30 * knee_flex)
        knee = (ankle[0] + shank * math.sin(dorsi),
                ankle[1] - shank * math.cos(dorsi))
        thigh_from_vert = math.radians(knee_flex) - dorsi
        hip = (knee[0] - thigh * math.sin(thigh_from_vert),
               knee[1] - thigh * math.cos(thigh_from_vert))
        lean = math.radians(0.45 * knee_flex)
        shoulder = (hip[0] + trunk * math.sin(lean),
                    hip[1] - trunk * math.cos(lean))
        elbow = (shoulder[0] - upper_arm * 0.3, shoulder[1] + upper_arm * 0.95)
        wrist = (elbow[0] - forearm * 0.2, elbow[1] + forearm * 0.97)
        toe = (ankle[0] + foot, ankle[1] + 2.0)
        heel = (ankle[0] - foot * 0.25, ankle[1] + 2.0)
        lm = {}
        for side in ("left", "right"):
            lm["%s_shoulder" % side] = shoulder
            lm["%s_hip" % side] = hip
            lm["%s_knee" % side] = knee
            lm["%s_ankle" % side] = ankle
            lm["%s_elbow" % side] = elbow
            lm["%s_wrist" % side] = wrist
            lm["%s_foot_index" % side] = toe
            lm["%s_heel" % side] = heel
        lm["nose"] = (shoulder[0] + 8, shoulder[1] - 30)
        return lm

    for _ in range(rest_frames):
        poses[frame] = emit(2.0); frame += 1
    for _ in range(n_reps):
        for i in range(rep_frames):
            phase = (1 - math.cos(2 * math.pi * i / rep_frames)) / 2.0
            poses[frame] = emit(2.0 + (peak_knee - 2.0) * phase)
            frame += 1
        for _ in range(rest_frames):
            poses[frame] = emit(2.0); frame += 1
    return poses


def main():
    poses = synth_squats()
    print("synthetic input: %d frames, %d squats to %.0f deg knee flexion\n"
          % (len(poses), N_REPS, PEAK_KNEE))

    print("squat detection")
    res = analyse(poses, FPS, height_m=HEIGHT_M, mass_kg=75.0,
                  activity="squat", model_key="kinematics_only")
    expect(len(res.reps) == N_REPS,
           "found %d reps (expected %d)" % (len(res.reps), N_REPS))

    if res.reps:
        s = res.reps[0].summary()
        expect(abs(s["knee_flex_max_deg"] - PEAK_KNEE) < 5.0,
               "peak knee flexion %.1f deg (expected ~%.0f)"
               % (s["knee_flex_max_deg"], PEAK_KNEE))
        expect(s["hip_flex_max_deg"] > 60.0,
               "peak hip flexion %.1f deg (a real squat, not a knee bend)"
               % s["hip_flex_max_deg"])
        expect(s["ankle_dorsi_max_deg"] > 10.0,
               "peak ankle dorsiflexion %.1f deg" % s["ankle_dorsi_max_deg"])
        expect(s["depth_below_standing_m"] > 0.20,
               "hips dropped %.2f m below standing" % s["depth_below_standing_m"])
        expect(s["eccentric_s"] > 0 and s["concentric_s"] > 0,
               "phases: down %.2f s, up %.2f s"
               % (s["eccentric_s"], s["concentric_s"]))

    print("\nthe pull-up detector must NOT fire on squats")
    res_pu = analyse(poses, FPS, height_m=HEIGHT_M, activity="pullup",
                     model_key="kinematics_only")
    expect(len(res_pu.reps) == 0,
           "pull-up detector found %d reps in squat footage (expected 0)"
           % len(res_pu.reps))

    print("\nforce model domain")
    expect(res.validity == Validity.OUT_OF_DOMAIN,
           "squat rejected on output plausibility: '%s'" % res.validity)
    print("     " + res.validity_reason)
    expect(res_pu.validity == Validity.OUT_OF_DOMAIN,
           "validity for a pull-up is '%s'" % res_pu.validity)
    expect(analyse(poses, FPS, height_m=HEIGHT_M,
                   activity="squat").validity == Validity.UNAVAILABLE,
           "the DEFAULT model is 'none', so no force numbers ship by accident")

    print("\n  how far each MEASURED input sits from the gait training data")
    print("  %-20s %8s %8s" % ("coord", "mean z", "max |z|"))
    for row in res.domain_report(limit=12):
        flag = "  <-- extrapolating" if row["max_z"] > 3.0 else ""
        print("  %-20s %8.2f %8.2f%s"
              % (row["coord"], row["mean_z"], row["max_z"], flag))
    worst = max((r["max_z"] for r in res.domain_report(limit=99)), default=0.0)
    expect(worst < 4.0,
           "worst measured input is %.1f sigma from training data" % worst)

    if res.reps and res.reps[0].forces is not None:
        f = res.reps[0].forces
        print("\n  predicted force range: %.0f .. %.0f N" % (f.min(), f.max()))
        print("  top muscles by peak force:")
        for name, peak in summarise(f, res.reps[0].target_names, top_n=6):
            print("    %-14s %8.0f N" % (name, peak))
        expect(res.implausible_fraction > 0.01,
               "%.0f%% of values exceed the physiological ceiling, so the "
               "runtime guard fires as intended"
               % (res.implausible_fraction * 100))

    print("\n%s" % ("FAILED:\n  " + "\n  ".join(FAILURES)
                    if FAILURES else "ALL CHECKS PASSED"))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
