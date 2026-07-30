"""Derive bone landmarks directly from MRI segmentation masks.

This automates the previously-manual 3D-Slicer step: instead of hand-placing
every fiducial, we read per-bone segmentation masks (one ``.nii.gz`` per bone,
e.g. TotalSegmentator output), turn each into a surface point cloud, and compute
landmarks with geometric rules (sphere fit for joint centres, extremal points
along anatomical axes for prominences).

Output is a Slicer-compatible ``.mrk.json`` so the landmarks can be loaded,
visually checked and nudged in 3D Slicer before feeding the TPS pipeline
(``mri_landmarks`` input) — the human stays in the loop.

Coordinate convention
---------------------
NIfTI affines are RAS+ (``+x`` right, ``+y`` anterior, ``+z`` superior). We
compute landmarks in that world frame, then write the ``.mrk.json`` in Slicer's
LPS convention with a per-point ``diag(-1,-1,1)`` orientation, so that
``orientation @ position`` recovers the RAS world coordinate — matching the
files the existing pipeline already consumes.

Heavy deps (``nibabel``/``SimpleITK`` + ``scikit-image``) are imported lazily so
importing this module never requires them; only :func:`mask_surface` does.

NOTE: the anatomical rules assume a roughly anatomically-aligned supine scan
(scan axes ≈ RAS). They are a first pass and should be verified in Slicer on
first use for a new dataset/scanner.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, Optional, Sequence

import numpy as np

from .logging_utils import get_logger

logger = get_logger(__name__)

Array = np.ndarray

# Default TotalSegmentator-style mask file names per anatomical bone/side.
# Override via `mask_names` if your segmenter names them differently.
DEFAULT_MASK_NAMES: Dict[str, str] = {
    "hip_r": "hip_right.nii.gz",
    "hip_l": "hip_left.nii.gz",
    "sacrum": "sacrum.nii.gz",
    "femur_r": "femur_right.nii.gz",
    "femur_l": "femur_left.nii.gz",
    "tibia_r": "tibia_right.nii.gz",
    "tibia_l": "tibia_left.nii.gz",
    "fibula_r": "fibula_right.nii.gz",
    "fibula_l": "fibula_left.nii.gz",
    "patella_r": "patella_right.nii.gz",
    "patella_l": "patella_left.nii.gz",
}


# --------------------------------------------------------------------- I/O
def mask_surface(path: str | Path, level: float = 0.5) -> Array:
    """Return an (N,3) RAS world-coordinate point cloud of a mask's surface.

    Uses marching cubes on the binary mask, then maps voxel vertices through the
    NIfTI affine to world (RAS mm). Requires ``nibabel`` and ``scikit-image``.
    """
    import nibabel as nib
    from skimage.measure import marching_cubes

    img = nib.load(str(path))
    vol = np.asarray(img.dataobj)
    mask = (vol > 0).astype(np.float32)
    if mask.max() == 0:
        raise ValueError(f"mask is empty: {path}")
    verts, *_ = marching_cubes(mask, level=level)
    # voxel (i,j,k) -> world (x,y,z) via affine
    affine = img.affine
    homog = np.c_[verts, np.ones(len(verts))]
    world = (affine @ homog.T).T[:, :3]
    return world


# ------------------------------------------------------------- geometry
def fit_sphere(points: Array) -> tuple[Array, float]:
    """Algebraic least-squares sphere fit. Returns (center_xyz, radius)."""
    p = np.asarray(points, float)
    A = np.c_[2 * p, np.ones(len(p))]
    b = (p ** 2).sum(axis=1)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    center = sol[:3]
    radius = float(np.sqrt(sol[3] + center @ center))
    return center, radius


def _extreme(points: Array, direction: Sequence[float], frac: float = 0.0) -> Array:
    """Point (or mean of the top ``frac`` fraction) most along ``direction``."""
    d = np.asarray(direction, float)
    proj = points @ d
    if frac <= 0:
        return points[int(np.argmax(proj))]
    k = max(1, int(len(points) * frac))
    idx = np.argsort(proj)[-k:]
    return points[idx].mean(axis=0)


def _region(points: Array, direction: Sequence[float], frac: float) -> Array:
    """Sub-cloud: the ``frac`` fraction of points furthest along ``direction``.

    At least 4 points are always returned, whatever ``frac`` asks for — the
    callers fit a sphere or a plane to this sub-cloud and fewer than 4 points
    is under-determined. On a real mask (thousands of vertices) the floor never
    binds; on a toy cloud it can return everything, which is the intended
    degenerate behaviour rather than a filter that failed.
    """
    d = np.asarray(direction, float)
    proj = points @ d
    k = max(4, int(len(points) * frac))
    return points[np.argsort(proj)[-k:]]


# RAS unit directions (+x right, +y anterior, +z superior)
SUP = (0, 0, 1); INF = (0, 0, -1)
ANT = (0, 1, 0); POST = (0, -1, 0)
RIGHT = (1, 0, 0); LEFT = (-1, 0, 0)


# --------------------------------------------------- per-bone landmark rules
# Each rule: name -> function(surfaces: dict[str,Array], side: str) -> xyz
# `surfaces` holds the RAS point clouds keyed by bone key (hip_r, femur_r, ...).
def _lat(side):  # lateral direction for a side
    return RIGHT if side == "r" else LEFT


def _med(side):
    return LEFT if side == "r" else RIGHT


def _pelvis_rules(side: str) -> Dict[str, Callable]:
    hip = f"hip_{side}"
    return {
        f"ASIS_{side}": lambda s: _extreme(s[hip], ANT, 0.01),
        f"PSIS_{side}": lambda s: _extreme(s[hip], POST, 0.01),
        f"ilium_{side}": lambda s: _extreme(s[hip], SUP, 0.02),
    }


def _pelvis_midline_rules() -> Dict[str, Callable]:
    # pubic symphysis points from the union of both hip halves, most inferior-medial
    def _pub_super(s):
        pts = np.vstack([s["hip_r"], s["hip_l"]])
        infer = _region(pts, INF, 0.15)          # lower pelvis
        return _extreme(infer, ANT, 0.02)         # anterior of that = pubis
    return {"pub_super_c": _pub_super}


def _femur_rules(side: str) -> Dict[str, Callable]:
    fem = f"femur_{side}"
    def _head(s):
        prox = _region(s[fem], SUP, 0.20)         # proximal fifth = head+neck
        c, _ = fit_sphere(prox)
        return c
    return {
        f"femur_{side}_center": _head,
        f"knee_{side}_med": lambda s: _extreme(_region(s[fem], INF, 0.20), _med(side), 0.01),
        f"knee_{side}_lat": lambda s: _extreme(_region(s[fem], INF, 0.20), _lat(side), 0.01),
    }


def _tibia_rules(side: str) -> Dict[str, Callable]:
    tib = f"tibia_{side}"
    def _knee_center(s):
        plateau = _region(s[tib], SUP, 0.10)
        return plateau.mean(axis=0)
    return {
        f"knee_{side}_center": _knee_center,
        f"tibia_{side}_center": lambda s: _region(s[tib], SUP, 0.10).mean(axis=0),
        f"tibia_{side}_med": lambda s: _extreme(_region(s[tib], SUP, 0.15), _med(side), 0.01),
        f"tibia_{side}_lat": lambda s: _extreme(_region(s[tib], SUP, 0.15), _lat(side), 0.01),
        f"tibia_{side}_med_malleol_tip": lambda s: _extreme(_region(s[tib], INF, 0.10), _med(side), 0.01),
    }


def _fibula_rules(side: str) -> Dict[str, Callable]:
    fib = f"fibula_{side}"
    return {
        f"fibula_{side}_lat_malleol_tip": lambda s: _extreme(_region(s[fib], INF, 0.10), _lat(side), 0.01),
    }


def _patella_rules(side: str) -> Dict[str, Callable]:
    pat = f"patella_{side}"
    return {
        f"patella_{side}": lambda s: s[pat].mean(axis=0),
        f"patella_lat_{side}": lambda s: _extreme(s[pat], _lat(side), 0.01),
        f"patella_med_{side}": lambda s: _extreme(s[pat], _med(side), 0.01),
        f"patella_sup_{side}": lambda s: _extreme(s[pat], SUP, 0.02),
    }


def _all_rules() -> Dict[str, tuple[list[str], Callable]]:
    """Return {landmark_name: (required_mask_keys, fn)} for every side/bone."""
    rules: Dict[str, tuple[list[str], Callable]] = {}
    for side in ("r", "l"):
        for name, fn in _pelvis_rules(side).items():
            rules[name] = ([f"hip_{side}"], fn)
        for name, fn in _femur_rules(side).items():
            rules[name] = ([f"femur_{side}"], fn)
        for name, fn in _tibia_rules(side).items():
            rules[name] = ([f"tibia_{side}"], fn)
        for name, fn in _fibula_rules(side).items():
            rules[name] = ([f"fibula_{side}"], fn)
        for name, fn in _patella_rules(side).items():
            rules[name] = ([f"patella_{side}"], fn)
    for name, fn in _pelvis_midline_rules().items():
        rules[name] = (["hip_r", "hip_l"], fn)
    return rules


# ------------------------------------------------------------- orchestrator
def extract_landmarks(
    segmentation_dir: str | Path,
    mask_names: Optional[Dict[str, str]] = None,
) -> Dict[str, Array]:
    """Compute all derivable bone landmarks (RAS mm) from segmentation masks.

    Masks that are absent are skipped with a warning (their landmarks are simply
    not produced), so a partial mask set yields a partial landmark set.
    """
    seg_dir = Path(segmentation_dir)
    mask_names = {**DEFAULT_MASK_NAMES, **(mask_names or {})}

    # load only the masks that exist
    surfaces: Dict[str, Array] = {}
    for key, fname in mask_names.items():
        p = seg_dir / fname
        if not p.exists():
            continue
        try:
            surfaces[key] = mask_surface(p)
        except Exception as exc:  # pragma: no cover - depends on data
            logger.warning("could not load mask %s: %s", p, exc)

    if not surfaces:
        raise FileNotFoundError(
            f"No segmentation masks found in {seg_dir}. Expected files like "
            f"{sorted(mask_names.values())[:3]} ..."
        )
    logger.info("loaded %d masks: %s", len(surfaces), ", ".join(sorted(surfaces)))

    landmarks: Dict[str, Array] = {}
    missing_masks: set[str] = set()
    for name, (need, fn) in _all_rules().items():
        if all(k in surfaces for k in need):
            try:
                landmarks[name] = np.asarray(fn(surfaces), float)
            except Exception as exc:  # pragma: no cover
                logger.warning("landmark '%s' failed: %s", name, exc)
        else:
            missing_masks.update(k for k in need if k not in surfaces)

    logger.info("extracted %d landmarks", len(landmarks))
    if missing_masks:
        logger.warning(
            "masks not found for: %s — landmarks on those bones were skipped and "
            "must be placed manually in Slicer.", ", ".join(sorted(missing_masks)),
        )
    return landmarks


# ------------------------------------------------------------- writer
def write_mrk_json(
    landmarks: Dict[str, Array],
    out_path: str | Path,
    coordinate_system: str = "LPS",
) -> Path:
    """Write landmarks (RAS mm) to a Slicer ``.mrk.json`` fiducial file.

    Stored in LPS with a per-point ``diag(-1,-1,1)`` orientation so that
    ``orientation @ position`` recovers the RAS coordinate the TPS loader uses.
    """
    out_path = Path(out_path)
    ras_to_lps = np.diag([-1.0, -1.0, 1.0])
    control_points = []
    for i, (name, ras) in enumerate(landmarks.items(), start=1):
        lps = ras_to_lps @ np.asarray(ras, float)
        control_points.append({
            "id": str(i),
            "label": name,
            "description": "auto-extracted from MRI segmentation",
            "position": [float(v) for v in lps],
            "orientation": [-1.0, 0.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 1.0],
            "selected": True,
            "locked": False,
            "visibility": True,
            "positionStatus": "defined",
        })
    doc = {
        "@schema": "https://raw.githubusercontent.com/slicer/slicer/master/Modules/Loadable/Markups/Resources/Schema/markups-schema-v1.0.3.json#",
        "markups": [{
            "type": "Fiducial",
            "coordinateSystem": coordinate_system,
            "coordinateUnits": "mm",
            "controlPoints": control_points,
        }],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as fh:
        json.dump(doc, fh, indent=2)
    logger.info("wrote %d landmarks to %s", len(landmarks), out_path)
    return out_path


def extract_and_write(
    segmentation_dir: str | Path,
    out_path: str | Path,
    mask_names: Optional[Dict[str, str]] = None,
) -> Path:
    """Convenience: extract landmarks from masks and write the ``.mrk.json``."""
    lms = extract_landmarks(segmentation_dir, mask_names=mask_names)
    return write_mrk_json(lms, out_path)
