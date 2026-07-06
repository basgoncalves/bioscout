"""Moment-arm and muscle-length sweeps over coordinate range of motion.

For a given coordinate, set it across its range (holding the rest of the model
at its default pose) and record each spanning muscle's moment arm and length.
Requires ``import opensim``.

Performance notes
-----------------
The expensive call is ``model.assemble`` (the constraint solver). Two things keep
this fast:
  * spanning-muscle detection poses the model once per sample and loops muscles
    inside (not once per muscle), and
  * ``assemble`` is skipped for coordinates that do not drive any constrained
    (dependent) coordinate -- detected once per coordinate. Only joints like the
    knee (patella coupler) actually need the solver.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .logutil import LOG, timed

try:
    import opensim
except Exception:  # pragma: no cover
    opensim = None


# Default coordinates worth inspecting on a lower-limb gait model.
DEFAULT_COORDINATES = [
    "hip_flexion_r", "hip_adduction_r", "hip_rotation_r",
    "knee_angle_r", "ankle_angle_r", "subtalar_angle_r",
    "hip_flexion_l", "hip_adduction_l", "hip_rotation_l",
    "knee_angle_l", "ankle_angle_l", "subtalar_angle_l",
]


@dataclass
class CoordinateSweep:
    coordinate: str
    angles_rad: np.ndarray
    angles_deg: np.ndarray
    moment_arms: dict          # muscle name -> np.ndarray (m)
    lengths: dict              # muscle name -> np.ndarray (m)
    unit: str = "rad"          # native unit of the coordinate (rad for rotational)


def _require_opensim():
    if opensim is None:
        raise ImportError(
            "The 'opensim' Python package is required to run moment_arms. "
            "Install it (conda -c opensim-org opensim) and run locally."
        )


class MomentArmModel:
    """Wraps an OpenSim model for repeated coordinate sweeps."""

    def __init__(self, osim_path: str):
        _require_opensim()
        self.path = osim_path
        self.model = opensim.Model(osim_path)
        self.state = self.model.initSystem()
        self.coord_set = self.model.getCoordinateSet()
        self.muscles = self.model.getMuscles()

        # Capture default pose so each sweep starts clean.
        self._defaults = {}
        self._dependent = []  # names of constrained (dependent) coordinates
        for i in range(self.coord_set.getSize()):
            c = self.coord_set.get(i)
            name = c.getName()
            self._defaults[name] = c.getValue(self.state)
            try:
                if c.isConstrained(self.state):
                    self._dependent.append(name)
            except Exception:
                pass
        self.has_constraints = self.model.getConstraintSet().getSize() > 0
        self._assemble_cache: dict[str, bool] = {}

    # -- pose helpers ------------------------------------------------------
    def reset_pose(self):
        for name, val in self._defaults.items():
            c = self.coord_set.get(name)
            if not c.getLocked(self.state):
                c.setValue(self.state, val, False)
        self.model.assemble(self.state)
        self.model.realizePosition(self.state)

    def _set_coord(self, coord, value, assemble: bool = True):
        coord.setValue(self.state, value, False)
        if assemble:
            self.model.assemble(self.state)
        self.model.realizePosition(self.state)

    def _assemble_needed(self, coord_name: str) -> bool:
        """Does moving this coordinate move any dependent coordinate?

        If not, we can skip the constraint solver for the whole sweep. Result is
        cached. Costs two solves to decide; saves dozens.
        """
        if not self.has_constraints or not self._dependent:
            return False
        if coord_name in self._assemble_cache:
            return self._assemble_cache[coord_name]

        coord = self.coord_set.get(coord_name)
        self.reset_pose()
        before = {d: self.coord_set.get(d).getValue(self.state) for d in self._dependent}
        lo, hi = coord.getRangeMin(), coord.getRangeMax()
        test = lo + 0.6 * (hi - lo)
        coord.setValue(self.state, test, False)
        self.model.assemble(self.state)
        moved = any(
            abs(self.coord_set.get(d).getValue(self.state) - before[d]) > 1e-6
            for d in self._dependent
        )
        self.reset_pose()
        self._assemble_cache[coord_name] = moved
        return moved

    # -- muscle selection --------------------------------------------------
    def all_muscle_names(self, muscle_filter: Optional[list] = None) -> list:
        names = []
        for i in range(self.muscles.getSize()):
            n = self.muscles.get(i).getName()
            if muscle_filter is None or any(f in n for f in muscle_filter):
                names.append(n)
        return names

    def find_spanning_muscles(
        self, coord_name: str, candidate_names: list,
        n_sample: int = 3, threshold: float = 1e-4,
    ) -> list:
        """Return muscles whose moment arm about ``coord_name`` is non-trivial.

        Poses the model once per sample and evaluates all muscles at that pose.
        """
        coord = self.coord_set.get(coord_name)
        lo, hi = coord.getRangeMin(), coord.getRangeMax()
        samples = np.linspace(lo, hi, n_sample)
        assemble = self._assemble_needed(coord_name)
        handles = {m: self.muscles.get(m) for m in candidate_names}
        ma_max = {m: 0.0 for m in candidate_names}

        self.reset_pose()
        for a in samples:
            self._set_coord(coord, a, assemble=assemble)
            for m in candidate_names:
                try:
                    v = abs(handles[m].computeMomentArm(self.state, coord))
                    if v > ma_max[m]:
                        ma_max[m] = v
                except Exception:
                    pass
        self.reset_pose()
        return [m for m in candidate_names if ma_max[m] > threshold]

    # -- the sweep ---------------------------------------------------------
    def sweep(self, coord_name: str, muscle_names: list, n: int = 80) -> CoordinateSweep:
        coord = self.coord_set.get(coord_name)
        lo, hi = coord.getRangeMin(), coord.getRangeMax()
        angles = np.linspace(lo, hi, n)
        assemble = self._assemble_needed(coord_name)

        unit = "rad"  # rotational coordinates are stored in radians
        try:
            if coord.getMotionType() == opensim.Coordinate.Translational:
                unit = "m"
        except Exception:
            pass

        moment_arms = {m: np.full(n, np.nan) for m in muscle_names}
        lengths = {m: np.full(n, np.nan) for m in muscle_names}
        handles = {m: self.muscles.get(m) for m in muscle_names}

        self.reset_pose()
        for k, a in enumerate(angles):
            self._set_coord(coord, a, assemble=assemble)
            for m in muscle_names:
                mh = handles[m]
                try:
                    moment_arms[m][k] = mh.computeMomentArm(self.state, coord)
                    lengths[m][k] = mh.getLength(self.state)
                except Exception:
                    pass
        self.reset_pose()

        angles_deg = np.degrees(angles) if unit == "rad" else angles
        return CoordinateSweep(
            coordinate=coord_name,
            angles_rad=angles,
            angles_deg=angles_deg,
            moment_arms=moment_arms,
            lengths=lengths,
            unit=unit,
        )

    # -- moment arms at the ACTUAL motion poses -----------------------------
    def moment_arm_over_motion(self, motion_df, mdof_coord, muscle_names,
                               in_degrees=True):
        """Moment arm of each muscle about ``mdof_coord`` at every frame of a
        recorded motion (as opposed to a synthetic single-DOF sweep).

        ``motion_df`` is an IK-style DataFrame with a ``time`` column plus one
        column per coordinate name (rotational coords in DEGREES when
        ``in_degrees``). The FULL pose is set each frame (every coordinate the
        model shares with the motion), so cross-DOF coupling is respected.
        Returns ``(time, {muscle: np.array})`` with moment arms in metres."""
        names = {self.coord_set.get(i).getName() for i in range(self.coord_set.getSize())}
        cols = [c for c in motion_df.columns if c != "time" and c in names]
        rot = {}
        for cname in cols:
            try:
                rot[cname] = (self.coord_set.get(cname).getMotionType()
                              == opensim.Coordinate.Rotational)
            except Exception:
                rot[cname] = True
        coord = self.coord_set.get(mdof_coord)
        handles = {m: self.muscles.get(m) for m in muscle_names}
        n = len(motion_df)
        t = np.asarray(motion_df["time"], dtype=float) if "time" in motion_df else np.arange(n)
        ma = {m: np.full(n, np.nan) for m in muscle_names}

        self.reset_pose()
        for k in range(n):
            for cname in cols:
                c = self.coord_set.get(cname)
                if c.getLocked(self.state):
                    continue
                val = float(motion_df[cname].iloc[k])
                if in_degrees and rot[cname]:
                    val = np.radians(val)
                c.setValue(self.state, val, False)
            self.model.assemble(self.state)
            self.model.realizePosition(self.state)
            for m in muscle_names:
                try:
                    ma[m][k] = handles[m].computeMomentArm(self.state, coord)
                except Exception:
                    pass
        self.reset_pose()
        return t, ma


def canonical_flip(coord):
    """Return +1.0 or -1.0 to express a model coordinate in the CANONICAL
    (literature) convention. [knee flexion-sign reconciliation]

    Only the knee differs across our models: Rajagopal/Catelli define knee
    flexion POSITIVE (range ~0..+150 deg) whereas GPK/Lernagopal -- and the
    literature database -- define knee flexion NEGATIVE (~-140..+10 deg). To
    compare any model against the same literature we flip flexion-positive knees
    so every model is shown/scored in the flexion-negative frame. Flipping the
    knee coordinate negates both the joint-angle axis and the moment-arm sign.
    Detected from the coordinate's range (no model editing required)."""
    try:
        name = coord.getName()
    except Exception:
        name = str(coord)
    if "knee_angle" in name:
        try:
            lo = np.degrees(coord.getRangeMin()); hi = np.degrees(coord.getRangeMax())
            if hi > abs(lo):          # flexion-positive model -> flip to canonical
                return -1.0
        except Exception:
            pass
    return 1.0


def compute_sweeps(
    osim_path: str,
    coordinate_names: Optional[list] = None,
    muscle_filter: Optional[list] = None,
    n: int = 80,
    auto_select: bool = True,
) -> dict:
    """Compute moment-arm/length sweeps for several coordinates.

    Returns ``{coordinate_name: CoordinateSweep}``. Coordinates that don't exist
    in the model are skipped with a warning.
    """
    with timed(f"load model {osim_path}"):
        mam = MomentArmModel(osim_path)
    if coordinate_names is None:
        coordinate_names = DEFAULT_COORDINATES
    present = {mam.coord_set.get(i).getName() for i in range(mam.coord_set.getSize())}
    candidates = mam.all_muscle_names(muscle_filter)
    LOG.info("Model has %d muscles, %d constrained coordinates%s",
             len(candidates), len(mam._dependent),
             f" ({', '.join(mam._dependent)})" if mam._dependent else "")

    results = {}
    for cname in coordinate_names:
        if cname not in present:
            LOG.warning("skip: coordinate '%s' not in model", cname)
            continue
        muscles = (
            mam.find_spanning_muscles(cname, candidates) if auto_select else candidates
        )
        if not muscles:
            LOG.warning("skip: no spanning muscles for '%s'", cname)
            continue
        need = mam._assemble_cache.get(cname, False)
        with timed(f"sweep {cname} ({len(muscles)} muscles, n={n}, "
                   f"assemble={'on' if need else 'off'})"):
            results[cname] = mam.sweep(cname, muscles, n=n)
    return results


def discontinuous_muscles(sweeps: dict, **detect_kwargs) -> set:
    """Names of muscles whose moment-arm or length curve has a discontinuity.

    Extra keyword args (e.g. ``min_jump_m``, ``k_global``) are forwarded to
    ``detect_discontinuities`` to tune sensitivity.
    """
    from .discontinuity import detect_discontinuities
    bad = set()
    for sw in sweeps.values():
        for series in (sw.lengths, sw.moment_arms):
            for mname, arr in series.items():
                if detect_discontinuities(arr, **detect_kwargs):
                    bad.add(mname)
    return bad
