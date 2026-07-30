"""Turn segmented muscle volumes into a wrap-radius factor.

The point of this module is to replace a hand-picked "scale the moment arm by
1.3" with a number measured from the subject's own MRI.

Reasoning, first order: a wrap surface stands in for muscle bulk, and for a
muscle of roughly constant length ``V = pi * r^2 * L``. With ``L`` already
personalised by the TPS bone geometry, the radius that represents a measured
volume ``V_subject`` against a reference ``V_ref`` is::

    r_new / r_old = sqrt(V_subject / V_ref)

This is a geometric argument, **not** an established scaling law — state it as
an assumption in the methods. It also assumes the mask is the whole muscle
belly and that the generic model's wrap radius corresponds to ``V_ref``.

``nibabel`` is imported lazily so the rest of the package works without it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional

__all__ = ["MuscleVolume", "measure_volume", "measure_volumes",
           "radius_factor_from_volumes", "DEFAULT_MASK_MAP"]

#: Segmentation mask stem -> the model wrap surfaces that represent that muscle.
#: TotalSegmentator names on the left; GPK/Rajagopal-family wraps on the right.
#: Only muscles whose path actually wraps can be driven this way — glute med/min
#: have no wrap in the GPK model and need the path-translation route instead.
DEFAULT_MASK_MAP: Dict[str, Dict[str, list]] = {
    "gluteus_maximus": {"r": ["Gmax1_at_pelvis_r", "Gmax2_at_pelvis_r",
                              "Gmax3_at_pelvis_r"],
                        "l": ["Gmax1_at_pelvis_l", "Gmax2_at_pelvis_l",
                              "Gmax3_at_pelvis_l"]},
    "gluteus_medius": {"r": ["Gmed_at_pelvis_r"], "l": ["Gmed_at_pelvis_l"]},
    "iliopsoas":      {"r": ["PS_at_brim_r", "IL_at_brim_r"],
                       "l": ["PS_at_brim_l", "IL_at_brim_l"]},
}


@dataclass
class MuscleVolume:
    name: str
    side: str
    volume_cm3: float
    voxels: int
    voxel_cm3: float
    path: str


def measure_volume(mask_path: str | Path, name: str = "", side: str = "") -> MuscleVolume:
    """Volume of a binary NIfTI mask, in cm^3.

    Uses the affine's voxel dimensions, so it is correct for anisotropic scans.
    """
    try:
        import nibabel as nib
    except Exception as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "measuring muscle volumes needs nibabel — pip install nibabel"
        ) from exc
    import numpy as np

    mask_path = Path(mask_path)
    img = nib.load(str(mask_path))
    data = np.asanyarray(img.dataobj)
    voxels = int((data > 0).sum())
    zooms = img.header.get_zooms()[:3]          # mm per voxel
    voxel_cm3 = float(zooms[0] * zooms[1] * zooms[2]) / 1000.0
    return MuscleVolume(name=name or mask_path.name.split(".")[0], side=side,
                        volume_cm3=voxels * voxel_cm3, voxels=voxels,
                        voxel_cm3=voxel_cm3, path=str(mask_path))


def measure_volumes(seg_dir: str | Path,
                    muscles: Optional[Iterable[str]] = None,
                    sides: Iterable[str] = ("r", "l")) -> Dict[str, MuscleVolume]:
    """Measure every ``<muscle>_<left|right>.nii.gz`` under ``seg_dir``.

    Returns ``{"<muscle>_<side>": MuscleVolume}``; masks that are absent are
    skipped rather than raising, so a partial segmentation still yields what it
    can.
    """
    seg_dir = Path(seg_dir)
    muscles = list(muscles or DEFAULT_MASK_MAP)
    long = {"r": "right", "l": "left"}
    out: Dict[str, MuscleVolume] = {}
    for m in muscles:
        for s in sides:
            for cand in (seg_dir / f"{m}_{long[s]}.nii.gz",
                         seg_dir / f"{m}_{s}.nii.gz",
                         seg_dir / f"{m}.nii.gz"):
                if cand.is_file():
                    out[f"{m}_{s}"] = measure_volume(cand, name=m, side=s)
                    break
    return out


def radius_factor_from_volumes(subject_cm3: float, reference_cm3: float) -> float:
    """``sqrt(V_subject / V_reference)`` — the wrap-radius factor.

    Raises on non-positive inputs: a zero volume means the mask was empty or
    misnamed, and silently returning 1.0 would hide that.
    """
    if subject_cm3 <= 0 or reference_cm3 <= 0:
        raise ValueError(
            f"volumes must be > 0 (subject={subject_cm3}, reference={reference_cm3}) "
            "— an empty mask usually means the wrong file or a failed segmentation"
        )
    return math.sqrt(subject_cm3 / reference_cm3)
