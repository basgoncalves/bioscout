"""Check whether a bone-landmark template can be reused across generic models.

The bone landmarks (``ASIS_r``, ``femur_r_center``, ``knee_r_med`` …) are stored
as marker locations **expressed in a model's body frames**. That template is
therefore only valid for another generic model if the two models put their
pelvis/femur/tibia/patella frames in the same place.

For the Arnold-lineage models used in this project (GPK, Catelli, Lernagopal and
Rajagopal2015) that happens to be true: each attaches the *same* bone meshes
(``r_femur.vtp``, ``l_pelvis.vtp`` …) to the corresponding body at identity
transform with scale ``1 1 1``, which pins the body frame to the mesh frame. So
one template covers all four — but that is a property to *verify per model*, not
to assume, which is what this module is for.

    >>> from bioscout.tps_personalise.model_compat import compare_bone_frames
    >>> rep = compare_bone_frames(gpk, rajagopal)
    >>> rep.compatible, rep.summary()

The check is conservative: anything it cannot prove identical is reported as a
mismatch, and the caller decides whether to proceed.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

from .logging_utils import get_logger
from .osim_format import is_v3, mesh_elements

logger = get_logger(__name__)

#: Bodies whose frames the TPS actually depends on.
DEFAULT_BODIES = (
    "pelvis", "femur_r", "femur_l", "tibia_r", "tibia_l", "patella_r", "patella_l",
)

_ZERO = np.zeros(6)


def _numbers(text: Optional[str], n: int, default: float = 0.0) -> np.ndarray:
    if not text:
        return np.full(n, default)
    vals = [float(v) for v in text.split()]
    if len(vals) < n:
        vals += [default] * (n - len(vals))
    return np.asarray(vals[:n], dtype=float)


@dataclass
class BodyGeometry:
    """What a model attaches to one body, in that body's own frame."""

    meshes: Dict[str, np.ndarray] = field(default_factory=dict)   # file -> scale
    transforms: Dict[str, np.ndarray] = field(default_factory=dict)  # file -> 6-vec


def read_bone_geometry(model: str | Path,
                       bodies: Sequence[str] = DEFAULT_BODIES) -> Dict[str, BodyGeometry]:
    """Map ``body -> BodyGeometry`` for the bodies that matter to the TPS."""
    root = ET.parse(Path(model)).getroot()
    v3 = is_v3(root)
    out: Dict[str, BodyGeometry] = {}
    for body_name, _mesh_name, el, file_tag in mesh_elements(root):
        if body_name not in bodies:
            continue
        mf = el.find(file_tag)
        if mf is None or not mf.text:
            continue
        fname = Path(mf.text.strip().replace("\\", "/")).name
        bg = out.setdefault(body_name, BodyGeometry())
        bg.meshes[fname] = _numbers(
            el.findtext("scale_factors"), 3, 1.0
        )
        # v3 stores rotation+translation together in <transform> (6 numbers);
        # v4 splits them across the owning frame, which for a direct body
        # attachment is the identity.
        bg.transforms[fname] = (
            _numbers(el.findtext("transform"), 6) if v3 else _ZERO.copy()
        )
    return out


@dataclass
class CompatibilityReport:
    reference: str
    target: str
    matched_bodies: List[str] = field(default_factory=list)
    missing_bodies: List[str] = field(default_factory=list)
    mesh_mismatch: Dict[str, str] = field(default_factory=dict)
    transform_mismatch: Dict[str, str] = field(default_factory=dict)
    scale_mismatch: Dict[str, str] = field(default_factory=dict)

    @property
    def compatible(self) -> bool:
        return (
            bool(self.matched_bodies)
            and not self.mesh_mismatch
            and not self.transform_mismatch
            and not self.scale_mismatch
        )

    def summary(self) -> str:
        lines = [
            f"bone-frame compatibility: {Path(self.target).name} "
            f"vs {Path(self.reference).name}",
            f"  bodies verified identical : {', '.join(self.matched_bodies) or '(none)'}",
        ]
        if self.missing_bodies:
            lines.append(
                f"  bodies absent from one model: {', '.join(self.missing_bodies)}"
            )
        for label, d in (
            ("mesh set differs", self.mesh_mismatch),
            ("mesh transform differs", self.transform_mismatch),
            ("mesh scale differs", self.scale_mismatch),
        ):
            for body, detail in d.items():
                lines.append(f"  [{label}] {body}: {detail}")
        lines.append(f"  -> {'COMPATIBLE' if self.compatible else 'NOT COMPATIBLE'}")
        return "\n".join(lines)


def compare_bone_frames(
    reference_model: str | Path,
    target_model: str | Path,
    bodies: Sequence[str] = DEFAULT_BODIES,
    atol: float = 1e-9,
) -> CompatibilityReport:
    """Verify that ``target_model`` shares ``reference_model``'s bone frames.

    Two bodies are treated as sharing a frame when both models attach the same
    bone mesh file(s) to that body with the same scale factors and the same
    (identity, in practice) local transform. That is a sufficient condition:
    the mesh vertices are in a fixed anatomical frame, so pinning the same mesh
    unscaled and untranslated pins the same body frame.
    """
    ref = read_bone_geometry(reference_model, bodies)
    tgt = read_bone_geometry(target_model, bodies)
    rep = CompatibilityReport(str(reference_model), str(target_model))

    for body in bodies:
        rg, tg = ref.get(body), tgt.get(body)
        if rg is None or tg is None:
            if rg is not None or tg is not None:
                rep.missing_bodies.append(body)
            continue
        shared = set(rg.meshes) & set(tg.meshes)
        if not shared:
            rep.mesh_mismatch[body] = (
                f"no common mesh ({sorted(rg.meshes)} vs {sorted(tg.meshes)})"
            )
            continue
        only = (set(rg.meshes) ^ set(tg.meshes))
        bad = False
        for f in sorted(shared):
            if not np.allclose(rg.meshes[f], tg.meshes[f], atol=atol):
                rep.scale_mismatch[body] = (
                    f"{f}: {rg.meshes[f].tolist()} vs {tg.meshes[f].tolist()}"
                )
                bad = True
            if not np.allclose(rg.transforms[f], tg.transforms[f], atol=1e-6):
                rep.transform_mismatch[body] = (
                    f"{f}: {rg.transforms[f].tolist()} vs {tg.transforms[f].tolist()}"
                )
                bad = True
        if not bad:
            rep.matched_bodies.append(body)
            if only:
                logger.debug("body '%s': meshes only in one model: %s", body, sorted(only))
    return rep


def assert_template_compatible(
    reference_model: str | Path,
    target_model: str | Path,
    bodies: Sequence[str] = DEFAULT_BODIES,
    strict: bool = True,
) -> CompatibilityReport:
    """Log the compatibility report; raise on failure when ``strict``.

    Call this before reusing a bone-landmark template built on
    ``reference_model`` to personalise ``target_model``. Running the TPS with an
    incompatible template does not error — it silently produces a warp fitted
    between mismatched frames, i.e. a plausible-looking but wrong model. Failing
    loudly here is the whole point.
    """
    rep = compare_bone_frames(reference_model, target_model, bodies)
    (logger.info if rep.compatible else logger.error)("%s", rep.summary())
    if strict and not rep.compatible:
        raise ValueError(
            "Bone-landmark template is not valid for this model.\n"
            + rep.summary()
            + "\n  Fix: build a template in this model's own body frames, or set "
              "check_template_frames: false in the config if you have verified "
              "the frames another way."
        )
    return rep
