"""Anatomical axis construction and rigid alignment of each body to OpenSim.

Refactor of the original ``TransformBodyToOsim`` / ``GetPelvisAxes`` /
``GetFemurAxes`` / ``GetTibiaAxes`` classes. The anatomical-axis *definitions*
(which landmarks build each axis, and the left/right handedness handling) are
preserved exactly; the shared rigid-alignment maths is delegated to
:func:`tps_personalise.geometry.kabsch` instead of being copy-pasted three
times, and ``print`` calls are replaced with logging.

Convention (unchanged from original): OpenSim body axes are taken as
``[[0,0,1],[1,0,0],[0,1,0]] * 50`` and each body's MRI anatomical axes are
rigidly rotated onto them.
"""
from __future__ import annotations

from typing import Optional, Sequence

import numpy as np

from .geometry import kabsch, plane_normal
from .logging_utils import get_logger

logger = get_logger(__name__)

Array = np.ndarray
# OpenSim reference axes (Slicer<->OpenSim axis swap), scaled by 50 as in original.
_OSIM_AXES = np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]], dtype=float) * 50


def _rotation_onto_osim(mri_axes: Array) -> Array:
    """Rigid rotation mapping MRI anatomical axes onto the OpenSim reference."""
    R, _ = kabsch(mri_axes, _OSIM_AXES)
    return R


def _index_of(markers: Sequence[str], name: str) -> int:
    return list(markers).index(name)


class PelvisAxes:
    """Pelvis anatomical frame from ASIS_r/ASIS_l/pub_super_c."""

    def __init__(self, bone_numpy: Array, bone_markers: Sequence[str]):
        self.bone_markers = list(bone_markers)
        self.bone_numpy = np.asarray(bone_numpy, dtype=float)
        self.mri_axes = self._define_mri_axes()
        self.R = _rotation_onto_osim(self.mri_axes)
        self._apply_to_bone()

    def _define_mri_axes(self) -> Array:
        m = {n: self.bone_numpy[i] for i, n in enumerate(self.bone_markers)}
        asis_r, asis_l, pub = m["ASIS_r"], m["ASIS_l"], m["pub_super_c"]
        origin = np.mean([asis_r, asis_l], axis=0)
        lr = (asis_r - asis_l) / np.linalg.norm(asis_r - asis_l)   # left->right
        pa = plane_normal(asis_l, pub, asis_r)                     # post->ant
        is_ = np.cross(lr, pa)                                     # inf->sup
        return np.array((lr, pa, is_)) * 50 + origin

    def _apply_to_bone(self) -> None:
        rotated = np.matmul(self.R, (self.bone_numpy - self.bone_numpy.mean(0)).T).T
        asis_r = rotated[_index_of(self.bone_markers, "ASIS_r")]
        asis_l = rotated[_index_of(self.bone_markers, "ASIS_l")]
        self.origin = np.mean([asis_r, asis_l], axis=0)
        self.bone_transformed = rotated - self.origin

    def apply_to_non_bone(self, data: Array) -> Array:
        rotated = np.matmul(self.R, (np.asarray(data, float) - self.bone_numpy.mean(0)).T).T
        return rotated - self.origin


class FemurAxes:
    """Femur anatomical frame; handles right/left automatically."""

    def __init__(self, bone_numpy: Array, bone_markers: Sequence[str]):
        self.bone_markers = list(bone_markers)
        self.bone_numpy = np.asarray(bone_numpy, dtype=float)
        self.side = self._define_side()
        self.is_axis = None
        self.mri_axes = self._define_mri_axes()
        self.R = _rotation_onto_osim(self.mri_axes)
        self._apply_to_bone()

    def _define_side(self) -> str:
        if "femur_r_center" in self.bone_markers:
            return "r"
        if "femur_l_center" in self.bone_markers:
            return "l"
        raise ValueError("femur side could not be determined from marker names")

    def _define_mri_axes(self) -> Array:
        s = self.side
        m = {n: self.bone_numpy[i] for i, n in enumerate(self.bone_markers)}
        head = m[f"femur_{s}_center"]
        med, lat = m[f"knee_{s}_med"], m[f"knee_{s}_lat"]
        knee_center = np.mean([med, lat], axis=0)
        # handedness preserved exactly from the original
        pa = plane_normal(head, med, lat) if s == "r" else plane_normal(head, lat, med)
        is_ = (head - knee_center) / np.linalg.norm(head - knee_center)
        lr = np.cross(pa, is_) / np.linalg.norm(np.cross(pa, is_))
        self.is_axis = is_
        return np.array((lr, pa, is_)) * 50

    def _apply_to_bone(self) -> None:
        self.bone_center = self.bone_numpy.mean(0)
        rotated = np.matmul(self.R, (self.bone_numpy - self.bone_center).T).T
        head = rotated[_index_of(self.bone_markers, f"femur_{self.side}_center")]
        self.bone_transformed = rotated - head
        self.non_bone_translation = head

    def apply_to_non_bone(self, data: Array) -> Array:
        rotated = np.matmul(self.R, (np.asarray(data, float) - self.bone_center).T).T
        return rotated - self.non_bone_translation

    def transform_patella(
        self,
        patella_bone: Array,
        patella_markers: Sequence[str],
        patella_muscles: Optional[Array] = None,
    ):
        """Rotate a patella into its child frame using this femur's IS axis.

        Port of the original ``GetFemurAxes.transform_patella``: builds the
        patella mediolateral axis from ``patella_lat_*``/``patella_med_*``, the
        PA axis from the femur IS axis, then recentres on the ``patella_*``
        marker. Returns ``(bone_in_child, muscles_in_child_or_None)``.
        """
        s = self.side
        idx = {n: i for i, n in enumerate(patella_markers)}
        loc = idx[f"patella_{s}"]
        lat = patella_bone[idx[f"patella_lat_{s}"]]
        med = patella_bone[idx[f"patella_med_{s}"]]
        patella_lr = (lat - med) if s == "r" else (med - lat)
        patella_lr = patella_lr / np.linalg.norm(patella_lr)
        patella_pa = np.cross(self.is_axis, patella_lr)
        patella_pa = patella_pa / np.linalg.norm(patella_pa)
        mri_axes = np.array((patella_lr, patella_pa, self.is_axis)) * 50
        R = _rotation_onto_osim(mri_axes)

        def _apply(data):
            data = np.asarray(data, float)
            return np.matmul(R, (data - self.bone_center).T).T - self.non_bone_translation

        bone_t = _apply(patella_bone)
        origin = bone_t[loc]
        # stash so other patella geometry (meshes) can reuse this frame
        self._patella_apply = _apply
        self._patella_origin = origin
        bone_child = bone_t - origin
        muscles_child = None
        if patella_muscles is not None and len(patella_muscles):
            muscles_child = _apply(patella_muscles) - origin
        return bone_child, muscles_child

    def apply_patella_non_bone(self, data: Array) -> Array:
        """Rotate arbitrary patella points into the frame set by the last
        :meth:`transform_patella` call (used for patella meshes)."""
        return self._patella_apply(data) - self._patella_origin


class TibiaAxes:
    """Tibia anatomical frame; handles right/left automatically."""

    def __init__(self, bone_numpy: Array, bone_markers: Sequence[str]):
        self.bone_markers = list(bone_markers)
        self.bone_numpy = np.asarray(bone_numpy, dtype=float)
        self.side = self._define_side()
        self.bone_center = self.bone_numpy.mean(0)
        self.mri_axes = self._define_mri_axes()
        self.R = _rotation_onto_osim(self.mri_axes)
        self._apply_to_bone()

    def _define_side(self) -> str:
        if "knee_r_center" in self.bone_markers:
            return "r"
        if "knee_l_center" in self.bone_markers:
            return "l"
        raise ValueError("tibia side could not be determined from marker names")

    def _define_mri_axes(self) -> Array:
        s = self.side
        m = {n: self.bone_numpy[i] for i, n in enumerate(self.bone_markers)}
        center = m[f"tibia_{s}_center"]
        med, lat = m[f"tibia_{s}_med"], m[f"tibia_{s}_lat"]
        talus = m[f"talus_{s}_center_in_tibia"]
        pa = plane_normal(med, talus, lat) if s == "r" else plane_normal(lat, talus, med)
        is_ = (center - talus) / np.linalg.norm(center - talus)
        lr = np.cross(pa, is_) / np.linalg.norm(np.cross(pa, is_))
        return np.array((lr, pa, is_)) * 50 + center

    def _apply_to_bone(self) -> None:
        rotated = np.matmul(self.R, (self.bone_numpy - self.bone_center).T).T
        tibia_idx = _index_of(self.bone_markers, f"tibia_{self.side}_center")
        knee_idx = _index_of(self.bone_markers, f"knee_{self.side}_center")
        to_tibia = rotated - rotated[tibia_idx]
        to_tibia[knee_idx] = to_tibia[knee_idx] * np.array([0, 1, 0])
        self.bone_transformed = to_tibia - to_tibia[knee_idx]
        self.non_bone_translation = rotated[tibia_idx] + to_tibia[knee_idx]

    def apply_to_non_bone(self, data: Array) -> Array:
        rotated = np.matmul(self.R, (np.asarray(data, float) - self.bone_center).T).T
        return rotated - self.non_bone_translation
