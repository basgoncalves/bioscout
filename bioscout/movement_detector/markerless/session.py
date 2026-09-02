"""
session.py -- orchestration: video (or cached poses) -> reps -> angles -> forces.

This is the only module the UI talks to. It has no Kivy and no Android
imports, so the whole pipeline can be run and tested from a desktop shell.
"""
from __future__ import annotations

import json
import os

import numpy as np

from . import forces as force_mod
from . import squat as squat_mod
from .kinematics import (
    DRIVEN_COORDS, PullupConfig, build_features, compute_px_per_m, find_reps,
    reference_positions, rep_coordinates, view_quality, write_mot,
)

DEFAULT_CFG = PullupConfig(top_rise_frac=0.50, min_rep_frames=12,
                           min_elbow_flexion_deg=40, smooth_win=5)

# Each activity supplies its own feature builder, rep detector, coordinate
# mapper and export column set. Adding a movement means adding an entry here,
# not editing analyse().
ACTIVITIES = {
    "pullup": {
        "label": "a pull-up",
        "config": PullupConfig,
        "default_cfg": DEFAULT_CFG,
        "features": build_features,
        "find_reps": find_reps,
        "coords": rep_coordinates,
        "reference": reference_positions,
        "columns": DRIVEN_COORDS,
        "phase_names": ("concentric_s", "eccentric_s"),
    },
    "squat": {
        "label": "a squat",
        "config": squat_mod.SquatConfig,
        "default_cfg": squat_mod.SquatConfig(),
        "features": squat_mod.build_squat_features,
        "find_reps": squat_mod.find_squat_reps,
        "coords": squat_mod.squat_rep_coordinates,
        "reference": squat_mod.reference_positions,
        "columns": squat_mod.SQUAT_DRIVEN_COORDS,
        "phase_names": ("eccentric_s", "concentric_s"),
    },
}


class Rep:
    """One repetition: timing, joint angles, and (optionally) muscle forces.

    `top` is the movement's extremum -- the highest point of a pull-up, the
    bottom of a squat -- so the two phase durations swap meaning between
    activities. `phase_names` carries which is which.
    """

    def __init__(self, index, times, coords, fps, bounds, activity="pullup"):
        self.index = index
        self.times = times
        self.coords = coords
        self.fps = fps
        self.b0, self.top, self.b1 = bounds
        self.activity = activity
        self.forces = None
        self.target_names = []

    @property
    def concentric_s(self):
        return (self.top - self.b0) / self.fps

    @property
    def eccentric_s(self):
        return (self.b1 - self.top) / self.fps

    @property
    def duration_s(self):
        return (self.b1 - self.b0) / self.fps

    def summary(self):
        first, second = ACTIVITIES[self.activity]["phase_names"]
        out = {
            "rep": self.index,
            first: round((self.top - self.b0) / self.fps, 3),
            second: round((self.b1 - self.top) / self.fps, 3),
            "duration_s": round(self.duration_s, 3),
        }
        ty = self.coords.get("pelvis_ty")
        if ty is not None:
            out["pelvis_travel_m"] = round(float(np.max(ty) - np.min(ty)), 3)

        if self.activity == "squat":
            knee = self.coords["knee_angle_r"]
            hip = self.coords["hip_flexion_r"]
            ankle = self.coords["ankle_angle_r"]
            out.update({
                # knee_angle is SIGNED per model family, so report peak flexion
                # as a magnitude; a GPK export would otherwise summarise as -2.
                "knee_flex_max_deg": round(float(np.max(np.abs(knee))), 1),
                "hip_flex_max_deg": round(float(np.max(hip)), 1),
                "ankle_dorsi_max_deg": round(float(np.max(np.abs(ankle))), 1),
                # pelvis_ty is an ABSOLUTE height, so depth is the drop.
                "depth_below_standing_m": round(float(np.max(ty) - np.min(ty)), 3)
                if ty is not None else None,
            })
        else:
            elbow = self.coords["elbow_flex_r"]
            arm = self.coords["arm_flex_r"]
            out.update({
                "elbow_flex_min_deg": round(float(np.min(elbow)), 1),
                "elbow_flex_max_deg": round(float(np.max(elbow)), 1),
                "arm_flex_range_deg": round(float(np.max(arm) - np.min(arm)), 1),
            })
        return out


class SessionResult:
    def __init__(self, reps, fps, px_per_m, scale_detail, coverage,
                 model_name, validity, validity_reason, missing_features,
                 n_features=0, activity="pullup", zscores=None,
                 implausible_fraction=0.0, view=None, osim_model="gpk"):
        self.reps = reps
        self.fps = fps
        self.px_per_m = px_per_m
        self.scale_detail = scale_detail
        self.coverage = coverage
        self.model_name = model_name
        self.validity = validity
        self.validity_reason = validity_reason
        self.missing_features = missing_features
        self.n_features = n_features
        self.activity = activity
        #: [(coord, mean_z, max_abs_z, measured)] -- how far this activity sits
        #: from the force model's training data. The honest domain check.
        self.zscores = zscores or []
        #: Fraction of predicted forces above any physiological ceiling.
        self.implausible_fraction = implausible_fraction
        #: Camera-view diagnostics; sagittal angles need a side-on view.
        self.view = view or {}
        #: Which OpenSim model family the exported .mot is signed for.
        self.osim_model = osim_model

    def domain_report(self, limit=6):
        """The measured coordinates furthest from the training distribution."""
        measured = [z for z in self.zscores if z[3]]
        worst = sorted(measured, key=lambda z: -z[2])[:limit]
        return [{"coord": n, "mean_z": round(mz, 2), "max_z": round(xz, 2)}
                for n, mz, xz, _ in worst]

    def summary(self):
        return {
            "activity": self.activity,
            "rep_count": len(self.reps),
            "fps": round(self.fps, 2),
            "px_per_m": round(self.px_per_m, 2),
            "pose_coverage": round(self.coverage, 3),
            "force_model": self.model_name,
            "force_validity": self.validity,
            "force_validity_reason": self.validity_reason,
            "unmeasured_model_inputs": "%d of %d (filled with the model's "
                                       "training mean)"
                                       % (len(self.missing_features),
                                          self.n_features),
            "osim_model": self.osim_model,
            "camera_view": self.view,
            "implausible_force_fraction": round(self.implausible_fraction, 4),
            "furthest_inputs_from_training_data": self.domain_report(),
            "reps": [r.summary() for r in self.reps],
        }

    def write(self, out_dir):
        """Write one trial folder per rep, in the layout the desktop tools use."""
        os.makedirs(out_dir, exist_ok=True)
        columns = ACTIVITIES[self.activity]["columns"]
        cols = ["time"] + columns
        for rep in self.reps:
            tdir = os.path.join(out_dir, "trial%d" % rep.index)
            os.makedirs(tdir, exist_ok=True)
            # A column the camera cannot measure is written as 0.0 for OpenSim.
            # The force model does NOT see this zero -- it gets the training
            # mean instead, via ForceModel.build_matrix.
            rows = [[rep.times[i]] +
                    [(rep.coords[c][i] if c in rep.coords else 0.0)
                     for c in columns]
                    for i in range(len(rep.times))]
            write_mot(os.path.join(tdir, "joint_angles.mot"),
                      "joint_angles", cols, rows)
            if rep.forces is not None and rep.forces.size:
                _write_forces_csv(os.path.join(tdir, "muscle_forces.csv"),
                                  rep.times, rep.target_names, rep.forces,
                                  self.validity)
        with open(os.path.join(out_dir, "session_summary.json"), "w") as f:
            json.dump(self.summary(), f, indent=2)
        return out_dir


def _write_forces_csv(path, times, names, forces, validity):
    with open(path, "w") as f:
        f.write("# validity=%s\n" % validity)
        f.write("time," + ",".join(names) + "\n")
        for i, t in enumerate(times):
            f.write("%.6f," % t + ",".join("%.4f" % v for v in forces[i]) + "\n")


def coords_for_force_model(coords, osim_model):
    """Coordinates in RAJAGOPAL signs, whatever the export convention is.

    The surrogate was trained on Rajagopal data (its knee_angle_r training mean
    is +56.9 deg). Handing it a GPK-signed knee inverts that input and pushes it
    even further outside the training distribution than it already is, silently.
    """
    if squat_mod.KNEE_SIGN.get(osim_model, -1.0) > 0:
        return coords
    out = dict(coords)
    for k in ("knee_angle_r", "knee_angle_l"):
        if k in out:
            out[k] = -np.asarray(out[k])
    return out


def analyse(poses, fps, height_m=1.75, mass_kg=75.0, cfg=None,
            model_key="none", activity="pullup",
            segment_fractions=None, osim_model="gpk"):
    """The whole pipeline, from landmarks to a SessionResult."""
    if activity not in ACTIVITIES:
        raise ValueError("unknown activity %r; expected one of %s"
                         % (activity, ", ".join(sorted(ACTIVITIES))))
    spec = ACTIVITIES[activity]
    cfg = cfg or spec["default_cfg"]

    F = spec["features"](poses)
    px_per_m, scale_detail = compute_px_per_m(poses, height_m, segment_fractions)
    ref_a, ref_b = spec["reference"](F)
    rep_bounds, _ = spec["find_reps"](F, cfg)
    view = view_quality(poses)

    model = force_mod.load_model(model_key)
    validity, reason = model.validity_for(spec["label"])

    reps, missing, zscores = [], [], []
    implausible = 0.0
    for i, bounds in enumerate(rep_bounds, 1):
        if activity == "squat":
            times, coords = spec["coords"](F, bounds, fps, px_per_m, ref_a, ref_b,
                                           model=osim_model,
                                           ankle_valid=view["ankle_usable"])
        else:
            times, coords = spec["coords"](F, bounds, fps, px_per_m, ref_a, ref_b)
        rep = Rep(i, times, coords, fps, bounds, activity=activity)
        if validity != force_mod.Validity.UNAVAILABLE:
            model_coords = (coords_for_force_model(coords, osim_model)
                            if activity == "squat" else coords)
            rep.forces = model.predict(model_coords, len(times))
            rep.target_names = model.target_names
            missing = getattr(model, "last_missing", [])
            if hasattr(model, "input_zscores") and not zscores:
                zscores = model.input_zscores(model_coords, len(times))
            implausible = max(implausible,
                              force_mod.implausible_fraction(rep.forces))
        reps.append(rep)

    # A runtime plausibility check outranks the static label. A model can be
    # nominally "extrapolating" on its inputs and still return numbers that are
    # simply impossible; when it does, say so rather than dressing the output
    # up as an estimate.
    if implausible > 0.01 and validity in (force_mod.Validity.VALID,
                                           force_mod.Validity.EXTRAPOLATED):
        peak = max((float(np.nanmax(np.abs(r.forces))) for r in reps
                    if r.forces is not None and r.forces.size), default=0.0)
        validity = force_mod.Validity.OUT_OF_DOMAIN
        reason = (
            "%.0f%% of predicted values exceed %.0f N, peaking at %.0f N -- "
            "no human muscle reaches that. The inputs are only a few standard "
            "deviations outside the training data, but the model's targets are "
            "log-scaled, so that modest extrapolation is exponentiated into a "
            "meaningless magnitude. Rejected on output plausibility."
            % (implausible * 100, force_mod.MAX_PLAUSIBLE_FORCE_N, peak))

    return SessionResult(reps, fps, px_per_m, scale_detail, F["_coverage"],
                         model.name, validity, reason, missing,
                         n_features=len(model.feature_names),
                         activity=activity, zscores=zscores,
                         implausible_fraction=implausible,
                         view=view, osim_model=osim_model)


def analyse_video(video_path, progress=None, **kwargs):
    """Convenience wrapper that runs MediaPipe first."""
    from .pose import extract_poses
    poses, fps = extract_poses(video_path, progress=progress)
    return analyse(poses, fps, **kwargs), poses, fps
