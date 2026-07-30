"""Configuration objects.

This module replaces the original ``paths_setup.py``, which hard-coded
subject-specific values (mass ``89.9``, height ``1.80``, filenames like
``orientation_Katya.mrk.json``) as module-level constants and created
directories on import.

Here, all subject and path information lives in a dataclass that can be built
from:
  * a YAML file (standalone use), or
  * a BioScout ``players.json`` entry + project layout (integrated use).

Nothing is created or read at import time. Directory creation is explicit via
:meth:`PersonalisationConfig.ensure_dirs`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class SubjectInfo:
    """Person-specific anthropometry. Previously hard-coded strings."""

    id: str
    mass_kg: float
    height_m: float
    age_years: Optional[float] = None
    sex: Optional[str] = None
    dominant_leg: Optional[str] = None

    def __post_init__(self) -> None:
        if self.mass_kg <= 0:
            raise ValueError(f"mass_kg must be > 0, got {self.mass_kg}")
        if self.height_m <= 0 or self.height_m > 3:
            raise ValueError(
                f"height_m must be in metres and plausible, got {self.height_m}"
            )


@dataclass
class PersonalisationConfig:
    """All inputs/outputs for one personalisation run.

    Paths are :class:`pathlib.Path`. Relative paths are resolved against
    ``project_root`` when set.
    """

    subject: SubjectInfo

    # --- inputs -------------------------------------------------------------
    generic_model: Path            # generic .osim (e.g. GPK_generic.osim)
    scaled_model: Path             # output of the OpenSim scale step
    mri_landmarks: Path            # 3D Slicer .mrk.json with bone landmarks
    bone_marker_template: Path     # markers_and_bone_markers_in_bodies.xml
    geometry_dir: Path             # folder of generic .vtp bone meshes

    # --- outputs ------------------------------------------------------------
    output_dir: Path               # where personalised model + CSVs are written
    # If left None, the output is named "<generic_model_stem>_tps.osim"
    # (e.g. GPK_generic_modWO.osim -> GPK_generic_modWO_tps.osim). A "{model}"
    # token in an explicit name is also replaced with the generic model stem.
    personalised_model_name: Optional[str] = None

    # --- algorithm parameters (were magic numbers in notebooks) ------------
    tps_alpha: float = 0.002       # TPS regularisation
    landmark_units_to_metres: float = 1e-3   # MRI landmarks in mm -> model metres
    orient_slicer_json: bool = True          # apply Slicer orientation matrix

    # Optional: folder of per-bone MRI segmentation masks (.nii.gz). When set,
    # `tps-landmarks` can auto-generate `mri_landmarks` from it.
    segmentation_dir: Optional[Path] = None

    # Optional joint-centre wiring overrides (model-specific joint names).
    # Each maps joint_name -> [offset_frame_name, transformed_marker_name].
    # Leave as None and the preset matching the model's joint names is chosen
    # automatically (see osim_model.MODEL_PRESETS).
    joint_centres: Optional[dict] = None
    pin_joint_centres: Optional[dict] = None

    # The model whose body frames `bone_marker_template` is expressed in. When
    # set, the frames of `generic_model` are verified against it before any
    # warping, so reusing one template across generic models fails loudly
    # instead of producing a plausible-but-wrong warp. See model_compat.py.
    template_source_model: Optional[Path] = None
    check_template_frames: bool = True

    # --- context ------------------------------------------------------------
    project_root: Optional[Path] = None

    # internal: keep the raw dict so unknown keys round-trip
    _extra: dict = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------------ paths
    def _resolve(self, p: Path) -> Path:
        p = Path(p)
        if not p.is_absolute() and self.project_root is not None:
            return (self.project_root / p).resolve()
        return p.resolve()

    def __post_init__(self) -> None:
        if self.project_root is not None:
            self.project_root = Path(self.project_root).resolve()
        for attr in (
            "generic_model", "scaled_model", "mri_landmarks",
            "bone_marker_template", "geometry_dir", "output_dir",
        ):
            setattr(self, attr, self._resolve(getattr(self, attr)))
        if self.segmentation_dir is not None:
            self.segmentation_dir = self._resolve(self.segmentation_dir)
        if self.template_source_model is not None:
            self.template_source_model = self._resolve(self.template_source_model)

    @property
    def resolved_model_name(self) -> str:
        """Output file name, defaulting to ``<generic_model_stem>_tps.osim``."""
        stem = Path(self.generic_model).stem
        if not self.personalised_model_name:
            return f"{stem}_tps.osim"
        return self.personalised_model_name.replace("{model}", stem)

    @property
    def personalised_model_path(self) -> Path:
        return self.output_dir / self.resolved_model_name

    def ensure_dirs(self) -> None:
        """Create output directories. Explicit — never happens on import."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "bones").mkdir(parents=True, exist_ok=True)

    def validate_inputs(self) -> None:
        """Fail fast with a clear message if required inputs are missing.

        ``geometry_dir`` is deliberately NOT required: it is read only to warp
        bone meshes, which is optional (needs ``pyvista``) and already degrades
        to "keep the generic surfaces, log it" downstream. Requiring it here
        blocked the entire personalisation — joint centres, muscle paths,
        wraps — over cosmetic geometry.
        """
        missing = [
            str(p)
            for p in (
                self.generic_model, self.scaled_model, self.mri_landmarks,
                self.bone_marker_template,
            )
            if not Path(p).exists()
        ]
        if missing:
            raise FileNotFoundError(
                "Missing required input(s):\n  " + "\n  ".join(missing)
            )
        if not Path(self.geometry_dir).exists():
            from .logging_utils import get_logger
            get_logger(__name__).warning(
                "geometry_dir not found (%s) — bone meshes will not be warped; "
                "the model keeps the generic surfaces. Everything that affects "
                "a simulation result is still personalised.", self.geometry_dir,
            )

    # ------------------------------------------------------------ loaders
    @classmethod
    def from_yaml(cls, path: str | Path) -> "PersonalisationConfig":
        """Build from a standalone YAML file (see ``examples/config.example.yaml``)."""
        path = Path(path)
        with open(path, "r") as fh:
            raw = yaml.safe_load(fh) or {}
        raw.setdefault("project_root", str(path.parent))
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: dict) -> "PersonalisationConfig":
        raw = dict(raw)
        subj_raw = raw.pop("subject")
        subject = SubjectInfo(**subj_raw) if isinstance(subj_raw, dict) else subj_raw
        known = {
            "generic_model", "scaled_model", "mri_landmarks",
            "bone_marker_template", "geometry_dir", "output_dir",
            "personalised_model_name", "tps_alpha", "landmark_units_to_metres",
            "orient_slicer_json", "project_root",
            "joint_centres", "pin_joint_centres", "segmentation_dir",
            "template_source_model", "check_template_frames",
        }
        kwargs = {k: raw[k] for k in known if k in raw}
        extra = {k: v for k, v in raw.items() if k not in known}
        return cls(subject=subject, _extra=extra, **kwargs)

    @classmethod
    def from_bioscout(
        cls,
        player_id: str,
        project_root: str | Path,
        players_json: str | Path | None = None,
        trial: str | None = None,
        **overrides,
    ) -> "PersonalisationConfig":
        """Build a config from a BioScout project layout.

        Mirrors BioScout conventions::

            <project_root>/players.json
            <project_root>/Models/GPK_generic.osim
            <project_root>/Models/Geometry/
            <project_root>/setup_files/markers_and_bone_markers_in_bodies.xml
            <project_root>/simulations/<player_id>/mri/landmarks.mrk.json
            <project_root>/simulations/<player_id>/<trial>/scaled_model.osim

        Subject anthropometry is read from ``players.json`` instead of being
        hard-coded — the central fix versus the original pipeline.
        """
        project_root = Path(project_root).resolve()
        players_json = Path(players_json) if players_json else project_root / "players.json"
        with open(players_json, "r") as fh:
            players = json.load(fh)
        if player_id not in players:
            raise KeyError(f"player '{player_id}' not in {players_json}")
        p = players[player_id]
        subject = SubjectInfo(
            id=player_id,
            mass_kg=float(p.get("mass") or p.get("mass_kg")),
            height_m=float(p.get("height") or p.get("height_m")),
            age_years=p.get("age") or p.get("age_years"),
            sex=p.get("sex"),
            dominant_leg=p.get("dominant_leg"),
        )
        sim_dir = project_root / "simulations" / player_id
        trial_dir = sim_dir / trial if trial else sim_dir
        defaults = dict(
            subject=subject,
            project_root=project_root,
            generic_model=project_root / "Models" / "GPK_generic.osim",
            scaled_model=trial_dir / "scaled_model.osim",
            mri_landmarks=sim_dir / "mri" / "landmarks.mrk.json",
            bone_marker_template=project_root / "setup_files"
            / "markers_and_bone_markers_in_bodies.xml",
            geometry_dir=project_root / "Models" / "Geometry",
            output_dir=trial_dir / "personalised",
        )
        defaults.update(overrides)
        return cls(**defaults)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("_extra", None)
        # stringify paths for serialisation
        for k, v in d.items():
            if isinstance(v, Path):
                d[k] = str(v)
        return d
