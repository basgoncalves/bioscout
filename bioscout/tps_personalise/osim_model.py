"""Parse an OpenSim ``.osim`` file into tidy DataFrames.

Consolidates the parsing logic that the original spread across
``OsimMusclePathsAndWrapping`` (in ``tps_scripts.py``) and ``FixWraps`` (in
``wrap_scripts.py``). Pure XML parsing — no ``opensim`` import needed, so this is
fast and unit-testable against a small fixture model.

Returned frames
---------------
``muscle_path_points`` : label, muscle, body, r, a, s
``wrap_surfaces``       : name(index), body, muscle, rotation, translation,
                          radius, length, range
``joints``              : name, body, translation, rotation
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Mapping, Sequence

import numpy as np
import pandas as pd

from .landmarks import _strip_socket
from .logging_utils import get_logger

logger = get_logger(__name__)


# --- joint-centre wiring (ported verbatim from notebook 4) -------------------
# Maps each joint -> (offset-frame name, transformed-marker name whose location
# becomes that frame's translation). Kept as data so a differently-named model
# can override it without touching code.
CUSTOM_JOINT_CENTRES: Dict[str, tuple[str, str]] = {
    "back":             ("pelvis_offset",  "torso_origin_in_pelvis"),
    "hip_r":            ("pelvis_offset",  "femur_r_center_in_pelvis"),
    "hip_l":            ("pelvis_offset",  "femur_l_center_in_pelvis"),
    "walker_knee_r":    ("femur_r_offset", "knee_r_center_in_femur_r"),
    "walker_knee_l":    ("femur_l_offset", "knee_l_center_in_femur_l"),
    "patellofemoral_r": ("femur_r_offset", "knee_r_center_in_femur_r"),
    "patellofemoral_l": ("femur_l_offset", "knee_l_center_in_femur_l"),
}
PIN_JOINT_CENTRES: Dict[str, tuple[str, str]] = {
    # NB: original notebook had a copy-paste bug using talus_r for ankle_l;
    # corrected here to talus_l.
    "ankle_r": ("tibia_r_offset", "talus_r_center_in_tibia"),
    "ankle_l": ("tibia_l_offset", "talus_l_center_in_tibia"),
}


#: Joint-centre wiring per model family, selected automatically by
#: :func:`detect_joint_centre_preset` from the joint names present in the model.
#: The maps were previously implicit — the defaults only fitted walker-knee
#: models, so Lerner-knee models (GPK, Lernagopal) silently kept their generic
#: knee centres and only warned.
MODEL_PRESETS: Dict[str, Dict[str, Dict[str, tuple]]] = {
    # Rajagopal2015, Catelli V4 — standard OpenSim walker knee + patellofemoral.
    "walker_knee": {
        "custom": {
            "back":             ("pelvis_offset",  "torso_origin_in_pelvis"),
            "hip_r":            ("pelvis_offset",  "femur_r_center_in_pelvis"),
            "hip_l":            ("pelvis_offset",  "femur_l_center_in_pelvis"),
            "walker_knee_r":    ("femur_r_offset", "knee_r_center_in_femur_r"),
            "walker_knee_l":    ("femur_l_offset", "knee_l_center_in_femur_l"),
            "patellofemoral_r": ("femur_r_offset", "knee_r_center_in_femur_r"),
            "patellofemoral_l": ("femur_l_offset", "knee_l_center_in_femur_l"),
        },
        "pin": {
            "ankle_r": ("tibia_r_offset", "talus_r_center_in_tibia"),
            "ankle_l": ("tibia_l_offset", "talus_l_center_in_tibia"),
        },
    },
    # GPK, Lernagopal — Lerner sagittal-articulation knee.
    #
    # The knee's position along the femur is NOT held by `Lerner_knee_r`: that
    # joint's `femoral_cond_r_offset` is expressed in the *femoral condyle*
    # body's own frame and is legitimately (0, 0, 0). The femur->condyle
    # placement lives in the `femur_weld_r` joint, whose `femur_r_offset` IS in
    # the femur frame (generic: 0, -0.404, 0) — that is where a femur-frame
    # knee centre belongs. Writing `knee_r_center_in_femur_r` into the
    # condyle-frame offset instead displaces knee, patella and shank by ~40 cm.
    "lerner_knee": {
        "custom": {
            "back":          ("pelvis_offset",  "torso_origin_in_pelvis"),
            "hip_r":         ("pelvis_offset",  "femur_r_center_in_pelvis"),
            "hip_l":         ("pelvis_offset",  "femur_l_center_in_pelvis"),
            "femur_weld_r":  ("femur_r_offset", "knee_r_center_in_femur_r"),
            "femur_weld_l":  ("femur_l_offset", "knee_l_center_in_femur_l"),
            # Lerner_knee_*/fem_pat_* deliberately absent: their offsets are in
            # condyle-local frames and the template has no landmark expressed
            # in those frames. Left generic rather than personalised wrongly.
        },
        "pin": {
            "ankle_r": ("tibia_r_offset", "talus_r_center_in_tibia"),
            "ankle_l": ("tibia_l_offset", "talus_l_center_in_tibia"),
        },
    },
}


def detect_joint_centre_preset(model: str | Path) -> str:
    """Pick the joint-centre preset that matches a model's joint names.

    Returns a key of :data:`MODEL_PRESETS`. Raises when no preset fits, which is
    the honest outcome — guessing would leave joint centres un-personalised
    while the run still reports success.
    """
    root = ET.parse(Path(model)).getroot()
    names = {j.get("name") for j in root.iter("CustomJoint")}
    names |= {j.get("name") for j in root.iter("PinJoint")}
    names |= {j.get("name") for j in root.iter("WeldJoint")}
    best, score = None, 0
    for key, preset in MODEL_PRESETS.items():
        hits = len(names & set(preset["custom"])) + len(names & set(preset["pin"]))
        if hits > score:
            best, score = key, hits
    if best is None:
        raise ValueError(
            f"No joint-centre preset matches {Path(model).name} "
            f"(joints: {sorted(n for n in names if n)}). Set joint_centres / "
            "pin_joint_centres explicitly in the config."
        )
    logger.info("joint-centre preset '%s' matched %d joints in %s",
                best, score, Path(model).name)
    return best


def joint_centre_maps(model: str | Path):
    """``(custom_joint_centres, pin_joint_centres)`` for a model."""
    preset = MODEL_PRESETS[detect_joint_centre_preset(model)]
    return preset["custom"], preset["pin"]


def _commented_parser() -> ET.XMLParser:
    """An XMLParser that keeps comments in the tree (they are dropped by default)."""
    return ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))


def _fmt_point(p) -> str:
    """Format a 3-vector as the space-separated text OpenSim expects."""
    return " ".join(repr(float(v)) for v in np.asarray(p, float).ravel()[:3])


def body_meshes(scaled_model: str | Path):
    """Yield ``(body, mesh_name, mesh_file)`` for every ``Mesh`` under a Body.

    Used to transform and repoint bone geometry per body. Generic — no
    hard-coded mesh-name map (unlike the original notebook).
    """
    from .osim_format import mesh_elements

    root = ET.parse(Path(scaled_model)).getroot()
    for body_name, mesh_name, el, file_tag in mesh_elements(root):
        mf = el.find(file_tag)
        yield body_name, mesh_name, (mf.text.strip() if mf is not None and mf.text else None)


def write_personalised_model(
    scaled_model: str | Path,
    markers: Mapping[str, Sequence[float]],
    muscles: Mapping[str, Sequence[float]],
    out_path: str | Path,
    model_name: str = "tps_transformed",
    custom_joint_centres: Mapping[str, tuple[str, str]] = CUSTOM_JOINT_CENTRES,
    pin_joint_centres: Mapping[str, tuple[str, str]] = PIN_JOINT_CENTRES,
    wraps: Mapping[str, Sequence[float]] | None = None,
    mesh_files: Mapping[str, str] | None = None,
    validate: bool = True,
) -> Dict[str, int]:
    """Assemble a personalised ``.osim`` from transformed geometry.

    Port of notebook 4: parse the scaled model XML and, by name-match, overwrite
    (a) muscle ``PathPoint`` locations, (b) ``Marker`` locations (bone, joint and
    skin markers), (c) joint offset-frame translations (joint centres),
    (d) ``WrapCylinder`` translations, and (e) ``Mesh`` files (repoint to the
    transformed bone surfaces, scale reset to ``1 1 1``). Pure ``xml.etree`` — no
    opensim needed to write; if ``validate`` and opensim is importable the result
    is loaded back to catch structural errors.

    Parameters
    ----------
    markers, muscles, wraps : mapping of name -> (x, y, z) in model metres.
    mesh_files : mapping of ``Mesh`` name -> new ``mesh_file`` path (relative to
        the model), e.g. ``{"pelvis_geom_1": "bones/pelvis.stl"}``.

    Returns counts: ``{"muscle_points", "markers", "joint_centres", "wraps",
    "meshes"}``.
    """
    wraps = wraps or {}
    mesh_files = mesh_files or {}
    out_path = Path(out_path)
    # Preserve the <!--...--> property documentation OpenSim ships in its models:
    # a plain ET.parse() silently drops every comment (5,000+ in a full-body
    # model), so a round-trip strips the file of everything that explains it.
    tree = ET.parse(Path(scaled_model), parser=_commented_parser())
    root = tree.getroot()
    counts = {"muscle_points": 0, "markers": 0, "joint_centres": 0,
              "wraps": 0, "meshes": 0}

    # (a) muscle path points
    from .osim_format import mesh_elements, path_point_elements, set_joint_centre

    for pp in path_point_elements(root):
        name = pp.attrib.get("name")
        if name in muscles:
            loc = pp.find("location")
            if loc is not None:
                loc.text = _fmt_point(muscles[name])
                counts["muscle_points"] += 1

    # (b) markers (bone markers, joint-in-parent markers, skin markers)
    for mk in root.iter("Marker"):
        name = mk.attrib.get("name")
        if name in markers:
            loc = mk.find("location")
            if loc is not None:
                loc.text = _fmt_point(markers[name])
                counts["markers"] += 1

    # (c) joint centres via offset-frame translations
    def _set_joint(joint_iter, mapping):
        for joint in joint_iter:
            jname = joint.attrib.get("name")
            if jname not in mapping:
                continue
            offset_name, marker_name = mapping[jname]
            if marker_name not in markers:
                logger.warning(
                    "joint '%s': marker '%s' not transformed; centre left unchanged",
                    jname, marker_name,
                )
                continue
            if set_joint_centre(joint, offset_name, _fmt_point(markers[marker_name])):
                counts["joint_centres"] += 1

    # WeldJoint included: the Lerner-knee models hold the femur->condyle
    # placement in `femur_weld_r/l`, so a custom map naming it must be applied.
    model_custom = {j.attrib.get("name") for j in root.iter("CustomJoint")}
    model_custom |= {j.attrib.get("name") for j in root.iter("WeldJoint")}
    model_pin = {j.attrib.get("name") for j in root.iter("PinJoint")}
    _set_joint(root.iter("CustomJoint"), custom_joint_centres)
    _set_joint(root.iter("WeldJoint"), custom_joint_centres)
    _set_joint(root.iter("PinJoint"), pin_joint_centres)
    # warn about mapped joints that don't exist in this model (name mismatch),
    # e.g. a Lerner-knee model has no 'walker_knee_r'/'patellofemoral_r'.
    unmapped = [j for j in custom_joint_centres if j not in model_custom]
    unmapped += [j for j in pin_joint_centres if j not in model_pin]
    if unmapped:
        logger.warning(
            "joint-centre map names not found in this model (centres NOT "
            "personalised): %s — override joint_centres/pin_joint_centres in the "
            "config to match this model's joint names.",
            ", ".join(unmapped),
        )

    # (d) wrapping-surface translations
    for wrap in root.iter("WrapCylinder"):
        name = wrap.attrib.get("name")
        if name in wraps:
            tr = wrap.find("translation")
            if tr is not None:
                tr.text = _fmt_point(wraps[name])
                counts["wraps"] += 1

    # (e) mesh files -> transformed bone surfaces (scale reset to identity)
    for _body, name, el, file_tag in mesh_elements(root):
        if name in mesh_files:
            mf = el.find(file_tag)
            if mf is not None:
                mf.text = str(mesh_files[name])
                sf = el.find("scale_factors")
                if sf is not None:
                    sf.text = "1 1 1"
                counts["meshes"] += 1

    # rename and write
    for model in root.iter("Model"):
        model.set("name", model_name)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # xml_declaration is required: ElementTree omits it by default and OpenSim's
    # own serialiser always writes one.
    tree.write(out_path, encoding="utf-8", xml_declaration=True)
    logger.info(
        "Wrote personalised model %s (%d muscle points, %d markers, %d joint "
        "centres, %d wraps, %d meshes)",
        out_path, counts["muscle_points"], counts["markers"],
        counts["joint_centres"], counts["wraps"], counts["meshes"],
    )

    if validate:
        try:
            import opensim  # noqa
            # Round-trip through the OpenSim API so the file is written with
            # OpenSim's canonical serialiser (correct <?xml?> header, element
            # ordering and formatting) rather than raw ElementTree output.
            model = opensim.Model(str(out_path))
            model.initSystem()
            model.printToXML(str(out_path))
            logger.info("Validated and re-saved via OpenSim: %s", out_path)
        except ImportError:
            logger.info("opensim not installed; wrote raw XML (not re-serialised)")
        except Exception as exc:  # pragma: no cover - depends on model content
            logger.warning("Model written but OpenSim validation failed: %s", exc)

    return counts


class OsimModelXML:
    """Lightweight, parse-once view of an OpenSim model XML."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._root = ET.parse(self.path).getroot()

    # ------------------------------------------------------------- muscles
    def muscle_path_points(self) -> pd.DataFrame:
        from .osim_format import frame_of, path_point_elements

        rows = []
        for el in path_point_elements(self._root):
            label = el.attrib.get("name")
            loc_el = el.find("location")
            if label is None or loc_el is None or not loc_el.text:
                continue
            loc = [float(v) for v in loc_el.text.split()]
            rows.append({
                "label": label,
                "muscle": label[:-3],          # strip trailing -P1/-P2...
                "body": frame_of(el),
                "r": loc[0], "a": loc[1], "s": loc[2],
            })
        return pd.DataFrame(rows)

    # ------------------------------------------------------------- wraps
    def wrap_surfaces(self) -> pd.DataFrame:
        rows = []
        for body in self._root.iter("Body"):
            body_name = body.get("name")
            for obj in body.iter("WrapCylinder"):
                def _vec(tag, default="0 0 0"):
                    el = obj.find(tag)
                    txt = el.text if el is not None and el.text else default
                    return np.array([float(x) for x in txt.split()])

                def _num(tag, default=0.0):
                    el = obj.find(tag)
                    return float(el.text) if el is not None and el.text else default

                transl_el = obj.find("translation")
                if transl_el is None or not transl_el.text:
                    continue  # a wrap with no translation can't be personalised
                rows.append({
                    "name": obj.get("name"),
                    "body": body_name,
                    "rotation": _vec("xyz_body_rotation"),   # radians
                    "translation": _vec("translation"),
                    "radius": _num("radius"),
                    "length": _num("length"),
                })
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        df = df.set_index("name")
        # link each wrap to the muscle that references it + its range
        # Any muscle class may own a PathWrap (Millard2012, Thelen2003,
        # DeGrooteFregly2016 ...). Walk the ForceSet generically rather than
        # hard-coding one class, or Thelen-based models (e.g. Rajagopal2015 as
        # distributed) silently lose every wrap<->muscle link.
        for mscl in self._root.iter():
            gp = mscl.find("GeometryPath")
            if gp is None or mscl.get("name") is None:
                continue          # only a force/muscle owns a GeometryPath
            # PathWrapSet sits inside GeometryPath in OpenSim's own files, but
            # search the whole force so hand-edited models that hoist it out
            # still link correctly.
            for pw in mscl.iter("PathWrap"):
                obj_el = pw.find("wrap_object")
                if obj_el is None or not obj_el.text:
                    continue
                obj_name = obj_el.text.strip()
                if obj_name in df.index:
                    df.loc[obj_name, "muscle"] = mscl.get("name")
                    rng = pw.find("range")
                    df.loc[obj_name, "range"] = rng.text if rng is not None else None
        return df

    # ------------------------------------------------------------- joints
    def joints(self) -> pd.DataFrame:
        rows = []
        for joint in self._root.iter("CustomJoint"):
            info = {"name": joint.attrib.get("name")}
            spf = joint.find("socket_parent_frame")
            spf_text = spf.text if spf is not None else None
            for frame in joint.iter("PhysicalOffsetFrame"):
                if frame.attrib.get("name") == spf_text:
                    info["body"] = _strip_socket(frame.find("socket_parent").text)
                    info["translation"] = frame.find("translation").text
                    info["rotation"] = frame.find("orientation").text
            rows.append(info)
        return pd.DataFrame(rows)


def wraps_to_points(wrap_df: pd.DataFrame) -> pd.DataFrame:
    """Add ``radius_point`` and ``axis_point`` columns for TPS transformation.

    Mirrors the original ``OsimWrapsByBodies.wraps_to_points_by_bodies`` point
    construction (radius point in -X, axis point along +Z), but returns a single
    frame rather than a dict-by-body (grouping is the caller's choice).
    """
    from .geometry import rotation_matrix

    df = wrap_df.copy()
    axes = np.eye(3)
    radius_pts, axis_pts = [], []
    for _, row in df.iterrows():
        ang = np.asarray(row["rotation"], float)
        center = np.asarray(row["translation"], float)
        R = np.matmul(
            rotation_matrix(axes[2], ang[2]),
            rotation_matrix(axes[0], ang[0]),
        )  # z * x  (then y applied below as in original np.matmul(z,x,y) semantics)
        R = np.matmul(R, rotation_matrix(axes[1], ang[1]))
        radius_pts.append(np.matmul(R, axes[0] * -1) * row["radius"] + center)
        half_len = row.get("length", 0.0) * 0.5
        axis_pts.append(np.matmul(R, axes[2]) * half_len * 0.5 + center)
    df["radius_point"] = radius_pts
    df["axis_point"] = axis_pts
    return df
