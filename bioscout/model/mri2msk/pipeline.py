"""MRI2MSK warping pipeline - Python port of the executeStepXX functions in MRI2MSK.m.

Steps (numbering follows the README / GUI):

    step1_rescale_and_align        executeStep01
    step2_align_skin               executeStep02
    step2b_add_skin_to_base_model  executeStep02b
    (3: user creates landmarks in OpenSim Creator Mesh Warper)
    step4_create_warp_setup        executeStep03
    (5: user warps the model in OpenSim Creator Model Warper)
    step6_replace_skin             executeStep04b
    step7a_correct_torsion         executeStep05
    step7b_correct_mass_centers    executeStep06
    step8_mechanical_knee_axis     executeStep07

The GUI and the post-scaling steps (IK, muscle path check, muscle optimiser) are
not ported yet.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

from . import geometry as geo

BONES_LEG = ("tibia", "femur")
SIDES = ("l", "r")
TIBIA_Y_SHIFT = 0.04  # tibia Y shift applied after rescaling (as in MATLAB)
PREALIGN_JSON = "preAligningToOpenSim.json"
PREALIGN_MAT = "preAligningToOpenSim.mat"


# =========================================================================== config
@dataclass
class Config:
    participant_folder: Path
    base_model_file: Path
    base_folder: Path | None = None  # folder with base STLs; defaults to model folder
    participant_name: str | None = None
    warp_template: Path | None = None  # chosen automatically if None
    include_skin: bool | None = None   # None = auto (skin/ folder with STLs present)

    def __post_init__(self):
        self.participant_folder = Path(self.participant_folder)
        self.base_model_file = Path(self.base_model_file)
        self.base_folder = Path(self.base_folder) if self.base_folder else self.base_model_file.parent
        self.participant_name = self.participant_name or self.participant_folder.name

    # convenience paths
    @property
    def stl_dir(self) -> Path:
        return self.participant_folder / "stls"

    @property
    def skin_dir(self) -> Path:
        return self.stl_dir / "skin"

    @property
    def landmark_dir(self) -> Path:
        return self.participant_folder / "landmarks"

    @property
    def warped_dir(self) -> Path:
        return self.participant_folder / "warpedModel"

    @property
    def has_skin(self) -> bool:
        if self.include_skin is not None:
            return bool(self.include_skin)
        return self.skin_dir.is_dir() and any(self.skin_dir.glob("*.stl"))


# =========================================================================== pre-alignment store
@dataclass
class BoneAlignment:
    origin_translation: np.ndarray  # (3,) mm, participant CS
    rotation_matrix: np.ndarray     # (3,3) columns = anatomical axes
    resize_factor: float = 1.0      # participant [mm] -> base model size

    def to_dict(self):
        return {"originTranslation": self.origin_translation.tolist(),
                "rotationMatrix": self.rotation_matrix.tolist(),
                "resizeFactor": self.resize_factor}

    @classmethod
    def from_dict(cls, d):
        return cls(np.asarray(d["originTranslation"], float).reshape(3),
                   np.asarray(d["rotationMatrix"], float).reshape(3, 3),
                   float(d["resizeFactor"]))


def save_prealignment(stl_dir: Path, pre: dict[str, BoneAlignment]) -> Path:
    path = Path(stl_dir) / PREALIGN_JSON
    path.write_text(json.dumps({k: v.to_dict() for k, v in pre.items()}, indent=2))
    return path


def load_prealignment(stl_dir: Path) -> dict[str, BoneAlignment]:
    """Load the JSON written by step 1, or fall back to the MATLAB .mat file.

    Keys are canonical: 'pelvis', 'femur_l', 'femur_r', 'tibia_l', 'tibia_r'.
    """
    stl_dir = Path(stl_dir)
    js = stl_dir / PREALIGN_JSON
    if js.is_file():
        return {k: BoneAlignment.from_dict(v) for k, v in json.loads(js.read_text()).items()}
    mat = stl_dir / PREALIGN_MAT
    if mat.is_file():
        return _load_prealignment_mat(mat)
    raise FileNotFoundError(f"No {PREALIGN_JSON} or {PREALIGN_MAT} in {stl_dir} - run step 1 first.")


def _load_prealignment_mat(path: Path) -> dict[str, BoneAlignment]:
    from scipy.io import loadmat
    raw = loadmat(str(path), squeeze_me=True, struct_as_record=False)["preAligning"]
    out: dict[str, BoneAlignment] = {}
    for fname in raw._fieldnames:
        s = getattr(raw, fname)
        if not hasattr(s, "rotationMatrix"):
            continue  # e.g. mechanicalKneeAxis_l scalars
        key = _canonical_bone_key(fname)
        out[key] = BoneAlignment(np.asarray(s.originTranslation, float).reshape(3),
                                 np.asarray(s.rotationMatrix, float),
                                 float(s.resizeFactor))
    return out


def _canonical_bone_key(name: str) -> str:
    n = name.lower()
    if "pelvis" in n:
        return "pelvis"
    for bone in ("femur", "tibia"):
        for side in SIDES:
            if f"{bone}_{side}" in n or f"{side}_{bone}" in n:
                return f"{bone}_{side}"
    raise ValueError(f"Cannot map '{name}' to a bone")


def scale_factor_to_participant(al: BoneAlignment) -> float:
    """Factor from base-model size back to participant [m] (MATLAB 1/(resize*1000))."""
    return 1.0 / (al.resize_factor * 1000.0)


# =========================================================================== file finding
def _iglob(folder: Path, pattern: str):
    """Case-insensitive glob (MATLAB dir() on Windows is case-insensitive)."""
    import fnmatch
    return sorted(p for p in Path(folder).iterdir() if fnmatch.fnmatch(p.name.lower(), pattern.lower()))


def _find_one(folder: Path, patterns, exclude="_resizedToOpenSim", what="file") -> Path | None:
    """First pattern that matches exactly one non-excluded STL wins."""
    for pat in patterns:
        hits = [p for p in _iglob(folder, pat) if not exclude or exclude not in p.name]
        if len(hits) > 1:
            raise RuntimeError(f"Too many {what} files for pattern {pat}: {[h.name for h in hits]}")
        if hits:
            return hits[0]
    return None


# =========================================================================== joint coordinate systems
JCSFunc = Callable[[Path, str, str], tuple[np.ndarray, np.ndarray]]
"""Signature: (stl_path, bone, side) -> (origin (3,) mm, R (3,3)).

``bone`` is 'pelvis', 'femur' or 'tibia'. R columns are the X, Y, Z axes in
OpenSim convention (X anterior, Y up, Z right). Must match MATLAB STAPLE:
  * pelvis -> JCS.pelvis.ground_pelvis      (STAPLE_pelvis)
  * femur  -> JCS.femur_<side>.hip_<side>   (GIBOC_femur 'ellipsoids')
  * tibia  -> JCS.tibia_<side>.knee_<side>  (Kai2014_tibia)
"""


def jcs_staple(stl_path: Path, bone: str, side: str):
    """Default JCS routine: the Python port of STAPLE in ``mri2msk.staple``."""
    from .staple import giboc_femur, kai2014_tibia, load_tri, staple_pelvis
    tri = load_tri(stl_path)
    if bone == "pelvis":
        origin, V, _ = staple_pelvis(tri, side)
        return origin, V
    if bone == "femur":
        # MATLAB falls back to Kai2014_femur if GIBOC fails - not ported yet.
        return giboc_femur(tri, side)
    if bone == "tibia":
        return kai2014_tibia(tri, side)
    raise ValueError(bone)


# =========================================================================== STEP 1
def step1_rescale_and_align(cfg: Config, jcs_func: JCSFunc = jcs_staple) -> dict[str, BoneAlignment]:
    """Align each participant bone to the OpenSim CS and rescale it to the base bone size.

    Writes ``*_resizedToOpenSim_inOpenSimCS.stl`` next to each input STL and
    ``stls/preAligningToOpenSim.json``.
    """
    pre: dict[str, BoneAlignment] = {}

    jobs = [(b, s) for b in BONES_LEG for s in SIDES] + [("pelvis", None)]
    for bone, side in jobs:
        key = bone if side is None else f"{bone}_{side}"
        if side is None:
            p_file = _find_one(cfg.stl_dir, ["*pelvis*.stl"], what="pelvis")
            b_file = _find_one(cfg.base_folder, ["*pelvis*.stl"], exclude=None, what="base pelvis")
        else:
            p_file = _find_one(cfg.stl_dir, [f"*{bone}_{side}*.stl", f"*{side}_{bone}*.stl"], what=key)
            b_file = _find_one(cfg.base_folder, [f"*{side}_{bone}*.stl"], exclude=None, what=f"base {key}")
        if p_file is None or b_file is None:
            raise FileNotFoundError(f"Missing participant or base STL for {key}")

        base_v, _ = geo.load_stl(b_file)
        opensim_size = geo.max_extent(base_v)

        v, f = geo.load_stl(p_file)
        origin, R = jcs_func(p_file, bone, side or "l")
        origin = np.asarray(origin, float).reshape(3)
        R = np.asarray(R, float).reshape(3, 3)

        v_cs = (v - origin) @ R
        resize = opensim_size / geo.max_extent_subsampled(v_cs)
        v_cs = v_cs * resize
        if bone == "tibia":
            v_cs[:, 1] -= TIBIA_Y_SHIFT

        geo.save_stl(p_file.with_name(p_file.stem + "_resizedToOpenSim_inOpenSimCS.stl"), v_cs, f)
        pre[key] = BoneAlignment(origin, R, resize)
        print(f"[step1] {key}: resize factor {resize:.6g}")

    save_prealignment(cfg.stl_dir, pre)
    return pre


# =========================================================================== STEP 2
def step2_align_skin(cfg: Config, n_vertices: int = 10000) -> None:
    """Transform skin STLs with the bone alignments; write unscaled and base-scaled copies."""
    pre = load_prealignment(cfg.stl_dir)

    def _process(src: Path, al: BoneAlignment, out_stem: str, y_shift: float = 0.0):
        v, f = geo.load_stl(src)
        v = (v - al.origin_translation) @ al.rotation_matrix / 1000.0
        v[:, 1] -= y_shift
        dv, df = geo.downsample_mesh(v, f, n_vertices)
        geo.save_stl(cfg.skin_dir / f"{out_stem}.stl", dv, df)
        v2 = v * (al.resize_factor * 1000.0)
        dv2, df2 = geo.downsample_mesh(v2, f, n_vertices)
        geo.save_stl(cfg.skin_dir / f"{out_stem}_scaledToBaseModel.stl", dv2, df2)

    for bone, skin in (("femur", "thigh"), ("tibia", "shank")):
        for side in SIDES:
            side_long = "left" if side == "l" else "right"
            files = sorted(cfg.skin_dir.glob(f"*{side_long}_{skin}*.stl"))
            for i, src in enumerate(files, start=1):
                _process(src, pre[f"{bone}_{side}"], f"skin_{skin}_{side}_{i}",
                         TIBIA_Y_SHIFT if skin == "shank" else 0.0)

    # NB: MATLAB loops over all pelvis skin files but always reads the first one;
    # here only the first raw pelvis skin is used, explicitly.
    pelvis_files = sorted(p for p in cfg.skin_dir.glob("*pelvis*.stl") if not p.name.startswith("skin_"))
    if pelvis_files:
        _process(pelvis_files[0], pre["pelvis"], "skin_pelvis")


def step2b_add_skin_to_base_model(cfg: Config) -> Path:
    """Attach the base-scaled skin meshes to the base model for visual reference."""
    import opensim as osim

    out_dir = cfg.participant_folder / "BaseModelWithSkin"
    geom_dir = out_dir / f"WarpedGeometry_{cfg.participant_name}"
    geom_dir.mkdir(parents=True, exist_ok=True)

    model = osim.Model(str(cfg.base_model_file))
    model.initSystem()
    bodies = model.getBodySet()

    def _attach(body_name: str, pattern: str):
        if not bodies.contains(body_name):
            return
        body = bodies.get(body_name)
        for src in sorted(cfg.skin_dir.glob(pattern)):
            dst = geom_dir / src.name
            shutil.copy2(src, dst)
            mesh = osim.Mesh(str(dst))
            mesh.set_scale_factors(osim.Vec3(1, 1, 1))
            mesh.setColor(osim.Vec3(0.6, 0.6, 0.6))
            mesh.setOpacity(0.5)
            body.attachGeometry(mesh)

    for part, bone in (("thigh", "femur"), ("shank", "tibia")):
        for side in SIDES:
            _attach(f"{bone}_{side}", f"skin_{part}_{side}*_scaledToBaseModel.stl")
    _attach("pelvis", "skin_pelvis*_scaledToBaseModel.stl")

    out = out_dir / f"{cfg.participant_name}_unscaled_withSkin.osim"
    model.printToXML(str(out))
    src_geom = cfg.base_model_file.parent / "Geometry"
    if src_geom.is_dir():
        shutil.copytree(src_geom, out_dir / "Geometry", dirs_exist_ok=True)
    return out


# =========================================================================== STEP 3 helper (Mesh Warper)
LANDMARK_BONES = ("pelvis", "femur_l", "femur_r", "tibia_l", "tibia_r")


def prepare_mesh_warper_files(cfg: Config) -> dict[str, dict]:
    """Copy base + participant meshes for each bone into ``landmarks/meshes``.

    Returns per bone: source (base STL), destination (participant STL in
    OpenSim CS) and the landmark CSV paths the user should export to.
    """
    out_dir = cfg.landmark_dir / "meshes"
    out_dir.mkdir(parents=True, exist_ok=True)
    info = {}
    for key in LANDMARK_BONES:
        if key == "pelvis":
            base = _find_one(cfg.base_folder, ["*pelvis*.stl"], exclude=None, what="base pelvis")
            part = _find_one(cfg.stl_dir, ["*pelvis*_resizedToOpenSim_inOpenSimCS.stl"], exclude=None)
        else:
            bone, side = key.split("_")
            base = _find_one(cfg.base_folder, [f"*{side}_{bone}*.stl"], exclude=None, what=f"base {key}")
            part = _find_one(cfg.stl_dir, [f"*{bone}_{side}*_resizedToOpenSim_inOpenSimCS.stl",
                                           f"*{side}_{bone}*_resizedToOpenSim_inOpenSimCS.stl"], exclude=None)
        if base is None or part is None:
            raise FileNotFoundError(f"Mesh missing for {key} - run step 1 first.")
        src, dst = out_dir / f"base_{key}.stl", out_dir / f"participant_{key}.stl"
        shutil.copy2(base, src)
        shutil.copy2(part, dst)
        info[key] = dict(source=src, destination=dst,
                         base_csv=cfg.landmark_dir / f"base_{key}.csv",
                         participant_csv=cfg.landmark_dir / f"participant_{key}.csv")
    return info


# =========================================================================== STEP 4 (warp setup)
def resolve_warp_template(cfg: Config) -> Path:
    """Pick the warp setup template (no skin / skin / sparse skin with *_2.stl files)."""
    if cfg.warp_template:
        return Path(cfg.warp_template)
    base = cfg.base_model_file.parent
    stem = "Base_LernagopalLaiUhlrich_warping_setup_template"
    if not cfg.has_skin:
        return base / f"{stem}.xml"
    multiple = any(any(cfg.skin_dir.glob(f"*{part}_{side}_2*.stl"))
                   for part in ("shank", "thigh") for side in SIDES)
    sparse = base / f"{stem}_withSparseSkin.xml"
    return sparse if multiple and sparse.is_file() else base / f"{stem}_withSkin.xml"


def _find_participant_lm(files, bone: str, side_tag: str) -> str:
    for f in files:
        n = f.name
        if "base" not in n and bone in n and side_tag in n:
            return str(f)
    return ""


def step4_create_warp_setup(cfg: Config, template: Path | None = None) -> Path:
    """Fill the OpenSim Creator warp template with scale factors, landmark paths and markers."""
    import opensim as osim

    template = Path(template) if template else resolve_warp_template(cfg)
    pre = load_prealignment(cfg.stl_dir)
    text = template.read_text()

    all_lm = sorted(cfg.landmark_dir.glob("*.csv"))
    base_lm = [f for f in all_lm if "base" in f.name]

    for f in base_lm:
        n = f.name.lower()
        targets = []
        if "pelvis" in n:
            targets.append(("pelvis", "", "PELVIS"))
        for bone in ("femur", "tibia"):
            for side in SIDES:
                if bone in n and f"_{side}" in n:
                    targets.append((f"{bone}_{side}", f"_{side}", f"{bone.upper()}_{side.upper()}"))
        for key, side_tag, tag in targets:
            bone = key.split("_")[0]
            sf = scale_factor_to_participant(pre[key])
            text = text.replace(f"SCALEFACTOR_{tag}_LANDMARKS", repr(sf))
            text = text.replace(f"PARTICIPANT_{tag}_LANDMARKS", _find_participant_lm(all_lm, bone, side_tag))
            text = text.replace(f"BASE_{tag}_LANDMARKS", str(f))

    model = osim.Model(str(cfg.base_model_file))
    model.initSystem()
    ms = model.getMarkerSet()
    for seg in ("pelvis", "femur_l", "femur_r", "tibia_r", "tibia_l"):
        names = [ms.get(i).getName() for i in range(ms.getSize())
                 if ms.get(i).getParentFrame().getName() == seg]
        text = text.replace(f"MARKERS_{seg.upper()}", "".join(f" /markerset/{n}" for n in names))

    out = cfg.participant_folder / "warp_setup.xml"
    out.write_text(text)
    (cfg.warped_dir / "warpedGeometry").mkdir(parents=True, exist_ok=True)
    return out


# =========================================================================== STEP 5 (warp model)
def warp_source_model(cfg: Config) -> Path:
    """Model to warp: skin model from step 2 (marker-adjusted version preferred), else base."""
    d = cfg.participant_folder / "BaseModelWithSkin"
    if cfg.has_skin and d.is_dir():
        for pat in (f"{cfg.participant_name}_unscaled_withSkin_markersAdjusted.osim",
                    f"{cfg.participant_name}_unscaled_withSkin.osim", "*_markersAdjusted.osim", "*.osim"):
            hits = sorted(d.glob(pat))
            if hits:
                return hits[-1]
    return cfg.base_model_file


def step5_warp_model(cfg: Config, model_file: Path | None = None) -> Path:
    """Apply warp_setup.xml to the model (Python Model Warper, replaces OSC step).

    Writes warpedModel/warpedModel.osim and warpedModel/warpedGeometry/*.obj.
    """
    from .model_warper import warp_model
    setup = cfg.participant_folder / "warp_setup.xml"
    if not setup.is_file():
        raise FileNotFoundError("warp_setup.xml not found - run step 4 first.")
    model_file = Path(model_file) if model_file else warp_source_model(cfg)
    print(f"[step5] warping {model_file.name}")
    return warp_model(model_file, setup, cfg.warped_dir / "warpedModel.osim", cfg.warped_dir / "warpedGeometry")


# =========================================================================== STEP 6 (replace skin)
def step6_replace_skin(cfg: Config, suffix: str = "_scaledToBaseModel") -> Path:
    """Point skin meshes of the warped model to the participant-scale skin STLs."""
    import opensim as osim
    from .osim_utils import iter_meshes

    model_file = cfg.warped_dir / "warpedModel.osim"
    model = osim.Model(str(model_file))
    bodies = model.getBodySet()
    for i in range(bodies.getSize()):
        for mesh in iter_meshes(bodies.get(i)):
            old = mesh.get_mesh_file()
            if suffix in old:
                stem = Path(old).stem.replace(suffix, "")
                mesh.set_mesh_file(str((cfg.skin_dir / f"{stem}.stl").resolve()))
    model.finalizeConnections()
    out = model_file.with_name("warpedModel_skinUpd.osim")
    model.printToXML(str(out))
    return out


# =========================================================================== STEP 7a (torsion)
def step7a_correct_torsion(cfg: Config) -> Path:
    """Undo the femoral/tibial torsion introduced by warping (relative to the base model)."""
    import opensim as osim
    from . import osim_utils as ou

    warped_file = cfg.warped_dir / "warpedModel.osim"
    skin_upd = warped_file.with_name("warpedModel_skinUpd.osim")
    if skin_upd.is_file():
        warped_file = skin_upd
    out = warped_file.with_name(warped_file.stem + "_torsionCorrected.osim")
    geom = warped_file.parent / "warpedGeometry"

    base = osim.Model(str(cfg.base_model_file))
    base_state = base.initSystem()
    model = osim.Model(str(warped_file))
    state = model.initSystem()
    zero = np.zeros(3)

    def _rot_obj(name: str, R, pivot, restore):
        src = geom / name
        dst = src.with_name(src.stem + "_rotated.obj")
        geo.rotate_obj_file(src, dst, R, pivot, restore)
        return dst

    for side in SIDES:
        knee_ref = [0, 1] if side == "l" else [0, -1]
        base_ang, _ = ou.get_model_angles_and_offsets(base, base_state, side, knee_ref)
        ang, trans = ou.get_model_angles_and_offsets(model, state, side, knee_ref)

        # ---- femur
        R_f = geo.rotation_y(-np.radians(ang["cond"] - base_ang["cond"]))
        ou.transform_path_points(model, state, f"femur_{side}", R_f, trans["femur"], False)
        ou.transform_wrap_objects(model.getBodySet().get(f"femur_{side}"), R_f, zero)
        ou.transform_markers(model, f"femur_{side}", R_f, trans["femur"], False)
        ou.set_body_mesh_file(model, f"femur_{side}", "femur",
                              str(_rot_obj(f"femur_{side}.obj", R_f, trans["femur"], False)))

        weld = ou.fix_femoral_condyles(model, side, R_f, trans["femur"])
        ou.set_condyle_mesh_file(model, side, str(_rot_obj(f"fem_cond_{side}.obj", R_f, weld, True)))

        # zero hip offset
        hip = osim.CustomJoint.safeDownCast(model.getJointSet().get(f"hip_{side}"))
        ou.get_offset_frame(hip, f"femur_{side}_offset").set_translation(osim.Vec3(0, 0, 0))

        # ---- tibia
        R_t = geo.rotation_y(-np.radians(ang["tibialPlat"] - base_ang["tibialPlat"]))
        torsion_corr = np.radians(ang["torsion"] - base_ang["torsion"])

        ou.transform_path_points(model, state, f"tibia_{side}", R_t, zero, False)
        ou.transform_wrap_objects(model.getBodySet().get(f"tibia_{side}"), R_t, zero)
        ou.transform_markers(model, f"tibia_{side}", R_t, zero, False)
        ou.set_body_mesh_file(model, f"tibia_{side}", "tibia",
                              str(_rot_obj(f"{side}_tibia.obj", R_t, zero, False)))
        ou.set_body_mesh_file(model, f"tibia_{side}", "fibula",
                              str(_rot_obj(f"{side}_fibula.obj", R_t, zero, False)))
        ou.set_tibial_plateau_mesh_file(model, side,
                                        str(_rot_obj(f"tib_plat_{side}_cut.obj", R_t, zero, False)))

        # knee offset: base X, warped Y, zero Z
        jn, fn = f"tibial_plat_weld_{side}", f"tibia_{side}_offset"
        of = ou.get_offset_frame(osim.WeldJoint.safeDownCast(model.getJointSet().get(jn)), fn)
        old = ou.vec3_to_np(of.get_translation())
        base_t = ou.vec3_to_np(ou.get_offset_frame(
            osim.WeldJoint.safeDownCast(base.getJointSet().get(jn)), fn).get_translation())
        of.set_translation(osim.Vec3(base_t[0], old[1], 0.0))

        # ankle torsion
        ankle = osim.PinJoint.safeDownCast(model.getJointSet().get(f"ankle_{side}"))
        of = ou.get_offset_frame(ankle, f"talus_{side}_offset")
        rot = ou.vec3_to_np(of.get_orientation())
        of.set_orientation(osim.Vec3(rot[0], rot[1] + torsion_corr, rot[2]))

        print(f"[step7a] {side}: femur corr {base_ang['cond'] - ang['cond']:.2f} deg, "
              f"tibia corr {base_ang['tibialPlat'] - ang['tibialPlat']:.2f} deg, "
              f"ankle torsion corr {np.degrees(torsion_corr):.2f} deg")

    model.printToXML(str(out))
    return out


# =========================================================================== STEP 7b (mass centres)
_MC_MARKERS = {"Pelvis": "pelvis", "Femur_L": "femur_l", "Femur_R": "femur_r",
               "Tibia_L": "tibia_l", "Tibia_R": "tibia_r"}


def step7b_correct_mass_centers(cfg: Config) -> Path:
    """Set body COMs from warped *MassCenter* markers and scale knee/patella splines."""
    import opensim as osim
    from . import osim_utils as ou

    candidates = sorted(cfg.warped_dir.glob("*_torsionCorrected.osim"))
    if not candidates:
        raise FileNotFoundError("Torsion-corrected model not found.")
    model_file = candidates[-1]
    pre = load_prealignment(cfg.stl_dir)

    model = osim.Model(str(model_file))
    ms = model.getMarkerSet()
    pelvis_mc = None
    for i in range(ms.getSize()):
        name = ms.get(i).getName()
        if "MassCenter" not in name:
            continue
        mc = ms.get(i).get_location()
        for tag, body in _MC_MARKERS.items():
            if tag in name:
                model.getBodySet().get(body).set_mass_center(mc)
                if body == "pelvis":
                    pelvis_mc = mc
                break

    if pelvis_mc is not None:
        fs = model.getForceSet()
        for i in range(fs.getSize()):
            if fs.get(i).getName() in ("FX", "FY", "FZ"):
                osim.PointActuator.safeDownCast(fs.get(i)).set_point(pelvis_mc)

    for side in ("r", "l"):
        sf = scale_factor_to_participant(pre[f"femur_{side}"])
        for jn in (f"fem_pat_{side}", f"Lerner_knee_{side}"):
            ou.wrap_coordinate_functions_with_scale(
                osim.CustomJoint.safeDownCast(model.getJointSet().get(jn)), sf)

    model.finalizeConnections()
    out = model_file.with_name(model_file.stem + "_massCentersCorrected.osim")
    model.printToXML(str(out))
    return out


# =========================================================================== STEP 8 (MKA)
def compute_mechanical_knee_axis(pre: dict[str, BoneAlignment]) -> dict[str, float]:
    """Frontal-plane femur-tibia angle (deg) per side from the step-1 frames."""
    out = {}
    for side in SIDES:
        R_rel = pre[f"femur_{side}"].rotation_matrix.T @ pre[f"tibia_{side}"].rotation_matrix
        out[side] = float(np.degrees(np.arcsin(np.clip(R_rel[2, 1], -1, 1))))
    return out


def mka_label(side: str, angle: float) -> str:
    if side == "l":
        return "Abduction" if angle >= 0 else "Adduction"
    return "Adduction" if angle >= 0 else "Abduction"


def participant_bone_meshes(cfg: Config, n_faces: int = 4000) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Participant bone STLs (MRI frame, mm) decimated for plotting."""
    meshes = {}
    for key in ("pelvis", "femur_l", "femur_r", "tibia_l", "tibia_r"):
        if key == "pelvis":
            f = _find_one(cfg.stl_dir, ["*pelvis*.stl"])
        else:
            b, s = key.split("_")
            f = _find_one(cfg.stl_dir, [f"*{b}_{s}*.stl", f"*{s}_{b}*.stl"])
        if f is None:
            continue
        v, fc = geo.load_stl(f)
        try:
            v, fc = geo.downsample_mesh(v, fc, n_faces // 2)
        except Exception:  # noqa: BLE001  (fast-simplification missing: subsample faces)
            fc = fc[:: max(1, len(fc) // n_faces)]
        meshes[key] = (v, fc)
    return meshes


def plot_mka(pre: dict[str, BoneAlignment], mka: dict[str, float], axis_len: float = 50.0,
             bones: dict | None = None):
    """3-D debug plot of pelvis/femur/tibia frames (replaces the MATLAB uifigure).

    ``bones``: optional {name: (vertices, faces)} in the same (MRI, mm) frame,
    drawn as translucent surfaces under the coordinate systems.
    """
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    fig = plt.figure(figsize=(10, 7.5))
    ax = fig.add_subplot(projection="3d")
    colors = ("r", "g", "b")
    pts = []

    if bones:
        for name, (v, f) in bones.items():
            col = (0.80, 0.78, 0.70) if name.startswith(("femur", "pelvis")) else (0.72, 0.76, 0.82)
            pc = Poly3DCollection(v[f], facecolor=col, edgecolor="none", alpha=0.4)
            ax.add_collection3d(pc)
            pts.append(v)

    def _frame(O, R, label):
        for i in range(3):
            ax.quiver(*O, *(axis_len * R[:, i]), color=colors[i], linewidth=2)
        ax.text(*O, f"  {label}", fontweight="bold")
        pts.append(np.atleast_2d(O))

    _frame(pre["pelvis"].origin_translation, pre["pelvis"].rotation_matrix, "Pelvis")
    for side in SIDES:
        f, t = pre[f"femur_{side}"], pre[f"tibia_{side}"]
        neg_len = abs(np.dot(t.origin_translation - f.origin_translation, f.rotation_matrix[:, 1]))
        neg_col = (0.55, 0, 0) if side == "l" else (0, 0.35, 0)
        for name, seg in (("femur", f), ("tibia", t)):
            _frame(seg.origin_translation, seg.rotation_matrix, f"{name}_{side}")
            ax.quiver(*seg.origin_translation, *(-neg_len * seg.rotation_matrix[:, 1]),
                      color=neg_col, linewidth=3, arrow_length_ratio=0.04)
            pts.append(np.atleast_2d(seg.origin_translation - neg_len * seg.rotation_matrix[:, 1]))
        mid = (f.origin_translation + t.origin_translation) / 2
        ax.text(*mid, f"{side.upper()}: {mka_label(side, mka[side])} {abs(mka[side]):.2f} deg",
                fontweight="bold", backgroundcolor="w")
    # equal axis ranges so angles are not distorted
    P = np.vstack(pts)
    c, h = (P.max(0) + P.min(0)) / 2, (P.max(0) - P.min(0)).max() / 2 * 1.05
    ax.set_xlim(c[0] - h, c[0] + h); ax.set_ylim(c[1] - h, c[1] + h); ax.set_zlim(c[2] - h, c[2] + h)
    ax.set_box_aspect((1, 1, 1))
    ax.set_xlabel("X [mm]"); ax.set_ylabel("Y [mm]"); ax.set_zlabel("Z [mm]")
    ax.set_title("Pelvis, Femur and Tibia Coordinate Systems")
    return fig


def step8_mechanical_knee_axis(cfg: Config, confirm: bool | Callable[[dict], bool] = True,
                               show_plot: bool = True) -> Path | None:
    """Apply half the MKA angle to the femoral-condyle and tibial-plateau weld frames.

    ``confirm``: True = apply without asking, False = only report, or a callable
    receiving ``{'l': deg, 'r': deg}`` (model correction values) returning bool.
    """
    import opensim as osim

    candidates = sorted(cfg.warped_dir.glob("*_massCentersCorrected.osim"))
    if not candidates:
        raise FileNotFoundError("Mass-centers-corrected model not found.")
    model_file = candidates[-1]

    pre = load_prealignment(cfg.stl_dir)
    mka = compute_mechanical_knee_axis(pre)
    correction = {s: -a for s, a in mka.items()}  # model correction = inverted measurement
    for s in SIDES:
        print(f"[step8] {s.upper()}: {abs(mka[s]):.2f} deg ({mka_label(s, mka[s])})")

    if show_plot:
        import matplotlib.pyplot as plt
        plot_mka(pre, mka, bones=participant_bone_meshes(cfg))
        plt.show()

    ok = confirm(correction) if callable(confirm) else bool(confirm)
    if not ok:
        print(f"[step8] not applied. Suggested values: left = {correction['l']:.4g} deg; "
              f"right = {correction['r']:.4g} deg")
        return None

    model = osim.Model(str(model_file))
    model.initSystem()
    for side in SIDES:
        half = np.radians(correction[side] / 2)
        for jn, fn in ((f"femur_weld_{side}", f"femoral_cond_{side}_offset"),
                       (f"tibial_plat_weld_{side}", f"tibia_{side}_offset")):
            joint = model.getJointSet().get(jn)
            for j in range(2):
                frame = joint.get_frames(j)
                if frame.getName() == fn:
                    frame.set_orientation(osim.Vec3(half, 0, 0))

    model.finalizeConnections()
    out = model_file.with_name(model_file.stem + "_MKA.osim")
    model.printToXML(str(out))
    return out


# =========================================================================== status
def detect_completed_steps(cfg: Config) -> dict[str, bool]:
    """Rough equivalent of the GUI's detectCompletedSteps()."""
    w = cfg.warped_dir
    return {
        "step1": (cfg.stl_dir / PREALIGN_JSON).is_file() or (cfg.stl_dir / PREALIGN_MAT).is_file(),
        "step2": any(cfg.skin_dir.glob("*_scaledToBaseModel.stl")) if cfg.skin_dir.is_dir() else False,
        "step3_landmarks": len(list(cfg.landmark_dir.glob("*.csv"))) >= 10 if cfg.landmark_dir.is_dir() else False,
        "step4": (cfg.participant_folder / "warp_setup.xml").is_file(),
        "step5_warped": (w / "warpedModel.osim").is_file(),
        "step6": (w / "warpedModel_skinUpd.osim").is_file(),
        "step7a": any(w.glob("*_torsionCorrected.osim")) if w.is_dir() else False,
        "step7b": any(w.glob("*_massCentersCorrected.osim")) if w.is_dir() else False,
        "step8": any(w.glob("*_MKA.osim")) if w.is_dir() else False,
    }
