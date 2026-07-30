"""High-level personalisation orchestrator.

This replaces the notebook-driven workflow (notebooks ``2.0`` -> ``4``). The
nine-notebook, run-cells-in-order process becomes a single callable object with
clear, individually-testable stages and structured logging.

The orchestration is deliberately split into small methods so a host
application (BioScout GUI/CLI) can run, monitor, or override any stage.

Stages
------
1. ``load_inputs``      — parse OSIM markers, MRI landmarks, muscles, wraps.
2. ``match_landmarks``  — match MRI<->OSIM bone markers, group by body.
3. ``fit_transforms``   — per body, fit a :class:`OneBodyTPS`.
4. ``apply_transforms`` — warp muscle paths / skin / wraps / surfaces.
5. ``write_outputs``    — CSVs + transformed surfaces (+ model update hook).

Heavy steps that require ``opensim``/``pyvista`` degrade gracefully: if those
libraries are absent the geometry is still computed and written as CSV, and the
final ``.osim`` write is reported as skipped.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

import pandas as pd

from .config import PersonalisationConfig
from .landmarks import (
    load_mri_landmarks, load_osim_bone_markers, match_by_name, split_by_body,
)
from .logging_utils import get_logger
from .osim_model import OsimModelXML
from .recording import GeometryWriter
from .tps import OneBodyTPS

logger = get_logger(__name__)


@dataclass
class PersonalisationResult:
    transforms: Dict[str, OneBodyTPS] = field(default_factory=dict)
    matched_markers: list = field(default_factory=list)
    unmatched_mri: list = field(default_factory=list)
    unmatched_osim: list = field(default_factory=list)
    written_files: list = field(default_factory=list)
    model_written: bool = False
    #: Populated by personalise_iteration() when it runs the moment-arm sweep:
    #: {"ok", "model", "corrected", "figures", "reason"}. None = not attempted.
    inspection: dict | None = None


class Personaliser:
    """Run the TPS personalisation described by a :class:`PersonalisationConfig`."""

    def __init__(self, config: PersonalisationConfig):
        self.cfg = config
        self.result = PersonalisationResult()
        # populated by load_inputs()
        self.osim_bone: pd.DataFrame | None = None
        self.mri_bone: pd.DataFrame | None = None
        self.muscles: pd.DataFrame | None = None
        # transformed geometry accumulated in apply_and_write(), keyed by name
        self._marker_points: dict = {}
        self._muscle_points: dict = {}
        self._wrap_points: dict = {}
        self._mesh_files: dict = {}

    # ------------------------------------------------------------------ run
    def run(self) -> PersonalisationResult:
        logger.info("Personalising subject '%s'", self.cfg.subject.id)
        self.cfg.validate_inputs()
        self.cfg.ensure_dirs()
        self.check_model_frames()
        self.load_inputs()
        self.match_landmarks()
        self.fit_transforms()
        self.apply_and_write()
        logger.info(
            "Done: %d body transforms, %d files written, model_written=%s",
            len(self.result.transforms),
            len(self.result.written_files),
            self.result.model_written,
        )
        return self.result

    # --------------------------------------------------------------- stages
    def check_model_frames(self) -> None:
        """Verify the bone-landmark template is valid for this generic model.

        No-op unless ``template_source_model`` is configured. Skipping this and
        warping with a template built in another model's frames does not raise
        anywhere downstream — it just yields a wrong model — so the check runs
        before any expensive work.
        """
        if not self.cfg.template_source_model:
            return
        from .model_compat import assert_template_compatible

        assert_template_compatible(
            self.cfg.template_source_model,
            self.cfg.generic_model,
            strict=self.cfg.check_template_frames,
        )

    def load_inputs(self) -> None:
        logger.info("Loading inputs")
        self.osim_bone = load_osim_bone_markers(self.cfg.bone_marker_template)
        self.mri_bone = load_mri_landmarks(
            self.cfg.mri_landmarks, apply_orientation=self.cfg.orient_slicer_json
        )
        # scale MRI landmarks into model units if needed
        if self.cfg.landmark_units_to_metres != 1.0:
            self.mri_bone[["r", "a", "s"]] *= self.cfg.landmark_units_to_metres
        self.muscles = OsimModelXML(self.cfg.scaled_model).muscle_path_points()

    def match_landmarks(self) -> None:
        matched, only_mri, only_osim = match_by_name(self.osim_bone, self.mri_bone)
        self.result.matched_markers = matched
        self.result.unmatched_mri = only_mri
        self.result.unmatched_osim = only_osim
        if only_mri:
            logger.warning("MRI landmarks not in OSIM template: %s", only_mri)
        if not matched:
            raise ValueError(
                "No MRI landmarks matched the OSIM bone-marker template; "
                "check marker naming."
            )
        logger.info("%d landmarks matched across bodies", len(matched))

    def fit_transforms(self) -> None:
        osim_by_body = split_by_body(self.osim_bone, self.result.matched_markers)
        mri_by_body = {
            b: self.mri_bone.loc[[n for n in df.index if n in self.mri_bone.index]]
            for b, df in osim_by_body.items()
        }
        for body, osim_df in osim_by_body.items():
            mri_df = mri_by_body[body]
            common = [n for n in osim_df.index if n in mri_df.index]
            if len(common) < 4:
                logger.warning("Body '%s': only %d landmarks, skipping", body, len(common))
                continue
            tps = OneBodyTPS(body, alpha=self.cfg.tps_alpha)
            tps.fit(osim_df.loc[common], mri_df.loc[common, ["r", "a", "s"]])
            self.result.transforms[body] = tps
            logger.info("Body '%s': TPS fitted on %d landmarks", body, len(common))

    def apply_and_write(self) -> None:
        """Warp every geometry set and rotate it into each body's child frame.

        Two steps per body, matching the original notebook exactly:
          1. apply the body's TPS (result is in the MRI/fit frame), then
          2. rotate into the OpenSim body-local (child) frame via ``axes.py``.

        Step 2 was missing in the first refactor, which left all geometry in
        the global MRI frame — the cause of the scattered/exploded model.
        Patella bodies are rotated with their femur's axes, so femurs are
        processed first.
        """
        from .axes import PelvisAxes, FemurAxes, TibiaAxes

        osim_all_by_body = split_by_body(self.osim_bone)
        # scaled-model skin/experimental markers, grouped by body
        try:
            skin_by_body = split_by_body(load_osim_bone_markers(self.cfg.scaled_model))
        except Exception as exc:  # pragma: no cover
            logger.warning("Could not read scaled-model markers: %s", exc)
            skin_by_body = {}
        # wrap-cylinder translations, grouped by body
        try:
            wrap_df = OsimModelXML(self.cfg.scaled_model).wrap_surfaces()
        except Exception as exc:  # pragma: no cover
            logger.warning("Could not read wrap surfaces: %s", exc)
            wrap_df = None

        femur_axes: dict = {}  # side ('r'/'l') -> FemurAxes, reused by patella
        # femurs/tibia/pelvis before patella
        bodies = sorted(self.result.transforms,
                        key=lambda b: (b.startswith("patella"), b))
        for body in bodies:
            tps = self.result.transforms[body]
            osim_body = osim_all_by_body.get(body)
            if osim_body is None or not len(osim_body):
                continue
            names = list(osim_body.index)
            t_bone = tps.transform_points(osim_body)          # MRI frame

            # --- build the child-frame rotation for this body ---
            side = body[-1]
            if body == "pelvis":
                ax = PelvisAxes(t_bone, names)
                rot = ax.apply_to_non_bone
                bone_child = ax.bone_transformed
            elif body.startswith("femur"):
                ax = FemurAxes(t_bone, names)
                femur_axes[side] = ax
                rot = ax.apply_to_non_bone
                bone_child = ax.bone_transformed
            elif body.startswith("tibia"):
                ax = TibiaAxes(t_bone, names)
                rot = ax.apply_to_non_bone
                bone_child = ax.bone_transformed
            elif body.startswith("patella"):
                ax = femur_axes.get(side)
                if ax is None:
                    logger.warning("patella '%s': femur_%s axes unavailable; skipping",
                                   body, side)
                    continue
                mus = self._body_muscles(body)
                bone_child, mus_child = ax.transform_patella(
                    t_bone, names,
                    tps.transform_points(mus[["r", "a", "s"]]) if mus is not None else None,
                )
                rot = ax.apply_patella_non_bone
                self._record_body(body, names, bone_child, mus, mus_child, rot,
                                  skin_by_body, wrap_df, tps, patella=True)
                continue
            else:
                logger.warning("body '%s' has no axis definition; skipping rotation", body)
                continue

            mus = self._body_muscles(body)
            mus_child = rot(tps.transform_points(mus[["r", "a", "s"]])) if mus is not None else None
            self._record_body(body, names, bone_child, mus, mus_child, rot,
                              skin_by_body, wrap_df, tps, patella=False)

        self.result.model_written = self._write_model()

    # ------------------------------------------------------------- helpers
    def _body_muscles(self, body: str):
        if self.muscles is None:
            return None
        mus = self.muscles[self.muscles["body"] == body]
        return mus if len(mus) else None

    def _record_body(self, body, names, bone_child, mus, mus_child, rot,
                     skin_by_body, wrap_df, tps, patella) -> None:
        """Write CSVs and accumulate child-frame geometry for the assembler."""
        import numpy as np
        writer = GeometryWriter(body, self.cfg.output_dir / "bones", to_metres=1.0)

        # bone markers
        f = writer.write_bone_markers(bone_child, names)
        if f:
            self.result.written_files.append(f)
        for n, p in zip(names, bone_child):
            self._marker_points[n] = p

        # muscle path points
        if mus is not None and mus_child is not None:
            f = writer.write_muscle_paths(mus_child, list(mus["label"]))
            if f:
                self.result.written_files.append(f)
            for n, p in zip(mus["label"], mus_child):
                self._muscle_points[n] = p

        # skin / experimental markers (from the scaled model itself)
        skin = skin_by_body.get(body)
        if skin is not None and len(skin):
            skin_child = rot(tps.transform_points(skin))
            f = writer.write_skin_markers(skin_child, list(skin.index))
            if f:
                self.result.written_files.append(f)
            for n, p in zip(skin.index, skin_child):
                self._marker_points.setdefault(n, p)

        # wrap-cylinder translations
        if wrap_df is not None and not wrap_df.empty:
            sub = wrap_df[wrap_df["body"] == body]
            if len(sub):
                pts = np.array([np.asarray(t, float) for t in sub["translation"]])
                wrap_child = rot(tps.transform_points(pts))
                f = writer.write_wrap_translations(wrap_child, list(sub.index))
                if f:
                    self.result.written_files.append(f)
                for n, p in zip(sub.index, wrap_child):
                    self._wrap_points[n] = p

        # bone meshes (pyvista; optional)
        self._apply_body_meshes(body, tps, rot)

    def _apply_body_meshes(self, body, tps, rot) -> None:
        from .osim_model import body_meshes
        try:
            import pyvista as pv
        except Exception:
            return  # logged once elsewhere; keep quiet per body
        bones_dir = self.cfg.output_dir / "bones"
        bones_dir.mkdir(parents=True, exist_ok=True)
        for b, mesh_name, mesh_file in body_meshes(self.cfg.scaled_model):
            if b != body or not mesh_file:
                continue
            src = self.cfg.geometry_dir / Path(mesh_file).name
            if not src.exists():
                logger.warning("mesh source not found for '%s': %s", mesh_name, src)
                continue
            try:
                surf = pv.read(str(src))
                warped_pts = rot(tps.transform_surface(surf).points)  # -> child frame
                out_name = f"{Path(mesh_file).stem}.stl"
                pv.PolyData(warped_pts, surf.faces).save(str(bones_dir / out_name))
                self._mesh_files[mesh_name] = f"bones/{out_name}"
                self.result.written_files.append(bones_dir / out_name)
            except Exception as exc:  # pragma: no cover
                logger.warning("mesh '%s' transform failed: %s", mesh_name, exc)

    def _write_model(self) -> bool:
        from .osim_model import write_personalised_model, joint_centre_maps

        custom, pin = self.cfg.joint_centres, self.cfg.pin_joint_centres
        if custom is None or pin is None:
            auto_custom, auto_pin = joint_centre_maps(self.cfg.scaled_model)
            custom = custom or auto_custom
            pin = pin or auto_pin

        out = self.cfg.personalised_model_path
        counts = write_personalised_model(
            scaled_model=self.cfg.scaled_model,
            markers=self._marker_points,
            muscles=self._muscle_points,
            out_path=out,
            model_name=self.cfg.resolved_model_name.replace(".osim", ""),
            custom_joint_centres=custom,
            pin_joint_centres=pin,
            wraps=self._wrap_points,
            mesh_files=self._mesh_files,
        )
        self.result.written_files.append(out)
        logger.info(
            "Personalised model assembled: %d muscle points, %d markers, "
            "%d joint centres, %d wraps, %d meshes updated",
            counts["muscle_points"], counts["markers"], counts["joint_centres"],
            counts["wraps"], counts["meshes"],
        )
        return True
