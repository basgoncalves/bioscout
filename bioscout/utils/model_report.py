"""Compare the DIMENSIONS and SEGMENT MASSES of several ``.osim`` models.

Why this module exists
----------------------
Two people scaling the same subject with the same generic model can produce
models that differ by tens of millimetres per segment and tens of percent per
segment mass, and nothing in the resulting ``.osim`` says so. Before comparing
kinematics, moments or joint contact forces ACROSS scaling methods, you need to
know how far apart the models themselves are — otherwise a "method effect" is
really a scaling artefact.

It reads the XML directly (``xml.etree`` only, via
:mod:`bioscout.tps_personalise.osim_format` for the 3.x/4.x differences), so it
needs **no OpenSim install** and never modifies the models.

What "dimension" means here
---------------------------
For every joint, the norm of its PARENT-frame offset translation: the distance
from the parent body's origin to the joint centre, expressed in the parent
frame. On a serial chain that is the parent segment's length — ``femur_r ->
walker_knee_r`` IS the femur length. This is the quantity ScaleTool's scale
factors actually act on, so it is what differs between scaling methods.

Usage
-----
    from bioscout.utils.model_report import compare_models
    rep = compare_models(r"C:\\path\\to\\models_folder")      # every *.osim in it
    print(rep["segment_mass"])

    # explicit list + labels, and write the tables out
    compare_models({"Addbio": "Addbio_Scaled_Model.osim",
                    "Feri":   "Feri_Scaled_Model.osim"},
                   out="model_comparison.xlsx",
                   setups={"Feri": "Feri_Scaled_Setup.xml"})

Or from the command line::

    python -m bioscout.utils.model_report <folder-or-models...> -o report.xlsx
"""
from __future__ import annotations

import glob
import math
import os
import re
import xml.etree.ElementTree as ET
from typing import Dict, Iterable, Mapping, Optional, Sequence, Union

__all__ = ["read_model_geometry", "read_scale_setup", "compare_models",
           "segment_dimensions", "dimension_sources", "make_figures"]


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def _nums(text: Optional[str], n: int, default: float = 0.0) -> list:
    if not text:
        return [default] * n
    try:
        vals = [float(x) for x in text.replace(",", " ").split()]
    except ValueError:
        return [default] * n
    return (vals + [default] * n)[:n]


def _norm(v: Sequence[float]) -> float:
    return math.sqrt(sum(float(x) * float(x) for x in v))


def _strip_socket(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    return text.strip().split("/")[-1] or None


def _model_root(path):
    root = ET.parse(str(path)).getroot()
    model = root.find("Model")
    return root, (model if model is not None else root)


def _is_v3(root: ET.Element) -> bool:
    try:
        return int(root.get("Version") or 0) < 40000
    except ValueError:
        return False


# --------------------------------------------------------------------------- #
# reading one model
# --------------------------------------------------------------------------- #
_BBOX_CACHE: Dict[str, Optional[list]] = {}


def _vtp_bbox(path) -> Optional[list]:
    """Bounding box of a VTK PolyData mesh as ``[x0,x1,y0,y1,z0,z1]``.

    The Arnold/Rajagopal-lineage ``.vtp`` files ship their Points as ASCII
    Float32, so plain ``xml.etree`` is enough — no VTK, no OpenSim.
    """
    key = os.path.abspath(str(path))
    if key in _BBOX_CACHE:
        return _BBOX_CACHE[key]
    box = None
    try:
        root = ET.parse(key).getroot()
        for piece in root.iter("Piece"):
            pts = piece.find("Points")
            if pts is None:
                continue
            da = pts.find("DataArray")
            if da is None or (da.get("format") or "ascii").lower() != "ascii":
                break                       # binary/appended payload: not parsed
            v = [float(x) for x in (da.text or "").split()]
            if len(v) < 3:
                break
            xs, ys, zs = v[0::3], v[1::3], v[2::3]
            box = [min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)]
            break
    except Exception:
        box = None
    _BBOX_CACHE[key] = box
    return box


def _geometry_dirs(model_path, extra=None) -> list:
    """Where to look for the generic meshes a model references.

    Order: an explicit path, a ``Geometry/`` folder beside or one level above the
    model, then the copy bundled with bioscout. Mesh files are NOT stored with a
    scaled model — only their filenames are — so the generic geometry has to be
    found for any size measurement to be possible.
    """
    out = []
    if extra:
        out += [str(extra)] if isinstance(extra, (str, os.PathLike)) else [str(e) for e in extra]
    here = os.path.dirname(os.path.abspath(str(model_path)))
    out += [os.path.join(here, "Geometry"), here,
            os.path.join(os.path.dirname(here), "Geometry")]
    try:                                    # the bundled generic geometry
        import bioscout
        out.append(os.path.join(os.path.dirname(os.path.abspath(bioscout.__file__)),
                                "models", "Geometry"))
    except Exception:
        # standalone copy with no bioscout installed: walk up looking for a
        # checkout, so a sibling clone still works
        probe = os.path.dirname(os.path.abspath(__file__))
        for _ in range(4):
            out.append(os.path.join(probe, "bioscout", "models", "Geometry"))
            out.append(os.path.join(probe, "models", "Geometry"))
            nxt = os.path.dirname(probe)
            if nxt == probe:
                break
            probe = nxt
    return [d for d in out if os.path.isdir(d)]


def segment_sizes(geom: Mapping, geometry=None) -> Dict[str, float]:
    """Each body's bounding-box extent per axis, from its SCALED bone meshes.

    ``{"torso_depth": .., "torso_height": .., "torso_width": ..}`` in metres, for
    EVERY body — including the terminal ones (patella, toes, hand) that parent no
    joint and therefore have no joint-to-joint length.

    The box is the union of the body's meshes, each generic mesh's own bounding
    box multiplied by that mesh's ``scale_factors``. Meshes in these models are
    attached to the body at identity (``socket_frame`` = ``..``), so the union is
    already in the body frame.

    Axis names follow the OpenSim body-frame convention — x anterior, y superior,
    z lateral — so depth/height/width are anteroposterior/superoinferior/
    mediolateral. A body whose meshes cannot be found is omitted rather than
    reported as zero.
    """
    dirs = _geometry_dirs(geom["path"], geometry)
    out: Dict[str, float] = {}
    for body, info in geom["bodies"].items():
        lo = [None, None, None]
        hi = [None, None, None]
        for mesh_file, scale in info.get("meshes") or []:
            path = next((os.path.join(d, mesh_file) for d in dirs
                         if os.path.isfile(os.path.join(d, mesh_file))), None)
            if path is None:
                continue
            box = _vtp_bbox(path)
            if not box:
                continue
            sf = scale or [1.0, 1.0, 1.0]
            for a in range(3):
                p0, p1 = sorted((box[2 * a] * sf[a], box[2 * a + 1] * sf[a]))
                lo[a] = p0 if lo[a] is None else min(lo[a], p0)
                hi[a] = p1 if hi[a] is None else max(hi[a], p1)
        if any(v is None for v in lo):
            continue
        for a, name in enumerate(("depth", "height", "width")):
            out[f"{body}_{name}"] = hi[a] - lo[a]
    return out


def _body_y_extent(geom: Mapping, body: str, geometry=None):
    """(y_min, y_max) of a body's scaled meshes in its own frame, or (None, None)."""
    dirs = _geometry_dirs(geom["path"], geometry)
    lo = hi = None
    for mesh_file, sf in (geom["bodies"].get(body, {}).get("meshes") or []):
        path = next((os.path.join(d, mesh_file) for d in dirs
                     if os.path.isfile(os.path.join(d, mesh_file))), None)
        if path is None:
            continue
        box = _vtp_bbox(path)
        if not box:
            continue
        a, b = sorted((box[2] * sf[1], box[3] * sf[1]))
        lo = a if lo is None else min(lo, a)
        hi = b if hi is None else max(hi, b)
    return lo, hi


def model_height(geom: Mapping, geometry=None, side: str = "r") -> Dict[str, float]:
    """Standing-height ESTIMATE, as the sum of the vertical chain sole -> vertex.

    Why an estimate and not the real thing: a true ground-frame height needs the
    full kinematic chain evaluated in the default pose, and the walker knee's
    translations are ``MultiplierFunction``/``PolynomialFunction`` splines coupled
    to ``knee_angle`` — reimplementing those outside OpenSim is exactly the kind
    of assumption that ships wrong numbers. Instead this sums each segment's
    VERTICAL offset along its own frame, which is the standard anthropometric
    approximation for a neutral standing pose and is exact arithmetic on values
    read straight from the file.

    Terms (all in metres):
      ``sole_to_calcn``   sole of the foot mesh below the calcaneus origin
      ``calcn_to_ankle``  |talus y offset| — ankle centre above the calcaneus
      ``ankle_to_knee``   |tibia y offset|
      ``knee_to_hip``     |femur y offset|
      ``hip_to_lumbar``   |back y − hip y|, BOTH in the pelvis frame (measuring
                          from the pelvis origin instead under-counts by the hip
                          offset, ~60 mm)
      ``lumbar_to_vertex`` top of the torso meshes above the torso origin — the
                          torso carries the skull, so this reaches the vertex
      ``total``           their sum
    """
    s = "l" if str(side).lower().startswith("l") else "r"
    pj = _parent_joints(geom)
    by = {j["joint"]: (j.get("parent_trans") or [0.0, 0.0, 0.0])
          for js in pj.values() for j in js}
    out: Dict[str, float] = {}

    lo, _ = _body_y_extent(geom, f"calcn_{s}", geometry)
    if lo is not None:
        out["sole_to_calcn"] = abs(min(lo, 0.0))
    if f"subtalar_{s}" in by:
        out["calcn_to_ankle"] = abs(by[f"subtalar_{s}"][1])
    if f"ankle_{s}" in by:
        out["ankle_to_knee"] = abs(by[f"ankle_{s}"][1])
    knee = f"walker_knee_{s}" if f"walker_knee_{s}" in by else f"knee_{s}"
    if knee in by:
        out["knee_to_hip"] = abs(by[knee][1])
    if "back" in by and f"hip_{s}" in by:
        out["hip_to_lumbar"] = abs(by["back"][1] - by[f"hip_{s}"][1])
    _, hi = _body_y_extent(geom, "torso", geometry)
    if hi is not None:
        out["lumbar_to_vertex"] = hi
    # Only total up a COMPLETE chain. Two terms need the generic meshes, and
    # without them the sum was still being reported as a stature estimate — a
    # plausible-looking ~0.9 m instead of ~1.6 m. Partial terms are still
    # returned; the total simply is not invented.
    required = ("sole_to_calcn", "calcn_to_ankle", "ankle_to_knee",
                "knee_to_hip", "hip_to_lumbar", "lumbar_to_vertex")
    missing = [k for k in required if k not in out]
    if out and not missing:
        out["total"] = sum(out[k] for k in required)
    elif out:
        out["_missing"] = missing
    return out


def bilateral_widths(geom: Mapping) -> Dict[str, float]:
    """Widths that come from PAIRED child joints rather than from bone meshes.

    ``pelvis`` parents hip_r and hip_l, so their mediolateral separation IS the
    inter-hip width; ``torso`` parents acromial_r/l, giving biacromial breadth.
    These are the numbers a scaling method actually places, and they do not
    include the skin/skull that a mesh bounding box picks up.
    """
    out = {}
    for body, joints in _parent_joints(geom).items():
        pairs = {}
        for j in joints:
            name = j["joint"]
            if name.endswith("_r") or name.endswith("_l"):
                pairs.setdefault(name[:-2], {})[name[-1]] = j.get("parent_trans") or [0, 0, 0]
        for stem, sides in pairs.items():
            if {"r", "l"} <= set(sides):
                out[f"{body}_{stem}_width"] = abs(sides["r"][2] - sides["l"][2])
    return out


def read_model_geometry(path) -> dict:
    """Bodies (mass / COM / inertia / mesh scale) and joints (offsets) of one model.

    Returns ``{"path", "version", "name", "bodies", "joints"}``. Works on
    OpenSim 3.x and 4.x; ``opensim`` is NOT imported.
    """
    root, model = _model_root(path)
    v3 = _is_v3(root)

    bodies: Dict[str, dict] = {}
    body_els = model.findall(".//BodySet/objects/Body") or model.findall(".//BodySet/objects/body")
    for b in body_els:
        name = b.get("name")
        scale = None
        meshes = []
        # v4: Mesh/{mesh_file,scale_factors} ; v3: DisplayGeometry/{geometry_file,..}
        for mesh in list(b.iter("Mesh")) + list(b.iter("DisplayGeometry")):
            txt = mesh.findtext("scale_factors")
            sf = _nums(txt, 3, 1.0) if txt else [1.0, 1.0, 1.0]
            if scale is None and txt:
                scale = sf                      # first mesh's factors, for reporting
            mf = mesh.findtext("mesh_file") or mesh.findtext("geometry_file")
            if mf:
                meshes.append((mf.strip(), sf))
        bodies[name] = {
            "mass": float(b.findtext("mass") or "nan"),
            "mass_center": _nums(b.findtext("mass_center"), 3),
            # inertia: v4 single <inertia> of 6; v3 separate inertia_xx ...
            "inertia": (_nums(b.findtext("inertia"), 6) if b.findtext("inertia") else
                        [float(b.findtext(f"inertia_{k}") or "nan")
                         for k in ("xx", "yy", "zz", "xy", "xz", "yz")]),
            "mesh_scale": scale,
            "meshes": meshes,
        }

    joints = []
    for j in model.findall(".//JointSet/objects/*"):
        entry = {"joint": j.get("name"), "type": j.tag}
        if v3:
            # 3.x: the joint element itself carries parent body + location_in_parent
            entry["parent_body"] = _strip_socket(j.findtext("parent_body"))
            entry["child_body"] = None          # 3.x: the owning <body> is the child
            entry["parent_trans"] = _nums(j.findtext("location_in_parent"), 3)
            entry["child_trans"] = _nums(j.findtext("location"), 3)
        else:
            frames = {f.get("name"): f for f in j.iter("PhysicalOffsetFrame")}
            for key, tag in (("socket_parent_frame", "parent"), ("socket_child_frame", "child")):
                ref = _strip_socket(j.findtext(key))
                fr = frames.get(ref)
                entry[f"{tag}_body"] = _strip_socket(fr.findtext("socket_parent")) if fr is not None else ref
                entry[f"{tag}_trans"] = _nums(fr.findtext("translation"), 3) if fr is not None else [0.0] * 3
        joints.append(entry)

    return {"path": str(path), "version": root.get("Version"),
            "name": model.get("name"), "bodies": bodies, "joints": joints}


def read_scale_setup(path) -> dict:
    """The intent behind a ScaleTool setup: subject mass/height, whether mass
    distribution was preserved, the scaling order, and any MANUAL ScaleSet
    override. A manual override in ``scaling_order`` is the usual reason two
    setups that look alike produce different segment lengths."""
    root = ET.parse(str(path)).getroot()
    st = root.find(".//ScaleTool")
    ms = root.find(".//ModelScaler")
    mp = root.find(".//MarkerPlacer")

    def _txt(el, tag):
        return (el.findtext(tag) or "").strip() if el is not None else ""

    manual = {sc.findtext("segment").strip(): _nums(sc.findtext("scales"), 3, 1.0)
              for sc in root.findall(".//ScaleSet/objects/Scale")
              if sc.findtext("segment")}
    measurements = {}
    for m in root.findall(".//MeasurementSet/objects/Measurement"):
        measurements[m.get("name")] = {
            "apply": _txt(m, "apply").lower() == "true",
            "marker_pairs": [(p.findtext("markers") or "").split()
                             for p in m.findall(".//MarkerPair")],
            "bodies": [(_txt(b, "body"), _txt(b, "axes"))
                       for b in m.findall(".//BodyScale")],
        }
    return {
        "path": str(path),
        "subject_mass": _txt(st, "mass"), "subject_height": _txt(st, "height"),
        "subject_age": _txt(st, "age"),
        "model_scaler_apply": _txt(ms, "apply"),
        "preserve_mass_distribution": _txt(ms, "preserve_mass_distribution"),
        "scaling_order": _txt(ms, "scaling_order"),
        "marker_placer_apply": _txt(mp, "apply"),
        "manual_scales": manual,
        "measurements": measurements,
    }


# --------------------------------------------------------------------------- #
# comparing several
# --------------------------------------------------------------------------- #
def _parent_joints(geom: Mapping) -> Dict[str, list]:
    """``{parent body: [joint entries]}``, skipping ground."""
    out: Dict[str, list] = {}
    for j in geom["joints"]:
        parent = j.get("parent_body")
        if not parent or parent == "ground":
            continue
        out.setdefault(parent, []).append(j)
    return out


def dimension_sources(geom: Mapping) -> Dict[str, dict]:
    """Which joint each body's dimension is measured to.

    A body can parent several joints — ``pelvis`` parents hip_r, hip_l and back;
    ``femur_r`` parents walker_knee_r and patellofemoral_r; ``torso`` parents
    acromial_r and acromial_l. The one with the LONGEST offset is the segment's
    long axis, so that is what gets reported as ``<body>_x/y/z/length``; the
    others are recorded here rather than silently dropped.
    """
    out = {}
    for body, joints in _parent_joints(geom).items():
        ranked = sorted(joints,
                        key=lambda j: _norm(j.get("parent_trans") or [0, 0, 0]),
                        reverse=True)
        out[body] = {"joint": ranked[0]["joint"],
                     "also_parents": [j["joint"] for j in ranked[1:]]}
    return out


def segment_dimensions(geom: Mapping, per_axis: bool = True) -> Dict[str, float]:
    """Each body's offset to its distal joint, named for the SEGMENT it describes.

    ``{"femur_r_x": .., "femur_r_y": .., "femur_r_z": .., "femur_r_length": ..}``
    in metres, in the model's own body order. Components are SIGNED and expressed
    in the parent body's frame (a femur's y is negative — it points distally), so
    a sign difference between two models is a real difference, not a formatting
    artefact. ``_length`` is the vector norm: the number you would quote as
    "femur length", and what the TPS validation invariants check.

    ``per_axis=False`` returns only the ``_length`` entries.
    """
    out: Dict[str, float] = {}
    src = dimension_sources(geom)
    by_name = {j["joint"]: j for j in geom["joints"]}
    for body in geom["bodies"]:              # model body order, not joint order
        if body not in src:
            continue                         # a terminal body parents nothing
        t = by_name[src[body]["joint"]].get("parent_trans") or [0.0, 0.0, 0.0]
        if per_axis:
            for axis, v in zip("xyz", t):
                out[f"{body}_{axis}"] = float(v)
        out[f"{body}_length"] = _norm(t)
    return out


def _resolve(models) -> Dict[str, str]:
    """Folder | list of paths | {label: path}  ->  {label: path}."""
    if isinstance(models, Mapping):
        return {str(k): str(v) for k, v in models.items()}
    if isinstance(models, (str, os.PathLike)):
        p = str(models)
        if os.path.isdir(p):
            hits = sorted(glob.glob(os.path.join(p, "*.osim")))
            if not hits:
                raise FileNotFoundError(f"no .osim files in {p!r}")
        else:
            hits = [p]
    else:
        hits = [str(x) for x in models]
    labels, out = [], {}
    for h in hits:
        lab = os.path.splitext(os.path.basename(h))[0]
        for suffix in ("_Scaled_Model", "_scaled_model", "_scaled", "_Model"):
            if lab.endswith(suffix):
                lab = lab[: -len(suffix)]
                break
        while lab in out:                     # keep labels unique
            lab += "_2"
        labels.append(lab); out[lab] = h
    return out


def _spread(df, cols):
    """max-min and % of the mean ACROSS ``cols`` only — never across columns we
    appended ourselves (doing that silently produced 30,000 % 'spreads')."""
    import pandas as pd            # local: keeps `import bioscout` light
    sub = df[cols]
    rng = sub.max(axis=1) - sub.min(axis=1)
    mean = sub.mean(axis=1).abs()
    pct = (100.0 * rng / mean).where(mean > 1e-12)
    return rng, pct


def compare_models(models, out: Optional[str] = None,
                   setups: Optional[Mapping[str, str]] = None,
                   figures: Union[bool, str, None] = None,
                   geometry=None, verbose: bool = True) -> dict:
    """Tabulate dimensions and segment masses across models.

    Parameters
    ----------
    models : folder, list of ``.osim`` paths, or ``{label: path}``
        A folder compares every ``.osim`` inside it. Labels are derived from the
        filename (``Feri_Scaled_Model.osim`` -> ``Feri``) unless you pass a dict.
    out : str, optional
        Write the tables to ``.xlsx`` (one sheet each) or ``.csv`` (one file per
        table, suffixed).
    geometry : path or list of paths, optional
        Where to find the generic ``.vtp``/``.stl`` meshes the models reference.
        Searched before ``Geometry/`` beside the models and the copy bundled with
        bioscout. Without them the mesh-derived sizes are unavailable (the joint
        and mass tables are not affected).
    figures : bool or str, optional
        ``True`` renders the figures beside ``out`` (or into the models' folder);
        pass a path to choose the output folder. Four figures: segment
        dimensions, segment mass + mass distribution, a mesh-scale heatmap and
        left-right asymmetry, as .png and .pdf.
    setups : ``{label: ScaleTool setup .xml}``, optional
        Adds a table of scaling INTENT — preserve_mass_distribution, scaling
        order, manual overrides — which is usually what explains the differences.

    Returns
    -------
    dict of DataFrames: ``totals``, ``segment_mass``, ``segment_mass_fraction``,
    ``segment_dimension``, ``mesh_scale``, ``asymmetry``, and ``scale_setup``.
    """
    import pandas as pd

    paths = _resolve(models)
    geoms = {lab: read_model_geometry(p) for lab, p in paths.items()}
    cols = list(geoms)
    rep: Dict[str, "pd.DataFrame"] = {}

    # ---- totals ----------------------------------------------------------
    totals = {}
    for lab, g in geoms.items():
        masses = [b["mass"] for b in g["bodies"].values()]
        dims = segment_dimensions(g)
        totals[lab] = {
            # rounded: summing 22 float masses lands on 67.00000000000003, and an
            # exact comparison of those sums then reports two "different" totals
            "total_mass_kg": round(sum(masses), 4),
            "n_bodies": len(g["bodies"]),
            "n_joints": len(g["joints"]),
            "osim_version": g["version"],
            "model_name": g["name"],
            "mesh_scaling": _mesh_style(g),
            "file": os.path.basename(g["path"]),
        }
    rep["totals"] = pd.DataFrame(totals)

    # ---- segment mass, and mass as a FRACTION of the total ---------------
    # The fraction matters: two models can share a total mass and still
    # distribute it very differently (preserve_mass_distribution vs an
    # optimiser that re-estimates inertial parameters).
    mass = pd.DataFrame({lab: {b: v["mass"] for b, v in g["bodies"].items()}
                         for lab, g in geoms.items()})
    mass = mass.reindex(list(geoms[cols[0]]["bodies"]))
    frac = mass / mass.sum(axis=0) * 100.0
    for df, key in ((mass, "segment_mass"), (frac, "segment_mass_fraction")):
        d = df.copy()
        rng, pct = _spread(d, cols)
        d["range"] = rng
        d["range_pct_of_mean"] = pct
        rep[key] = d

    # ---- segment dimensions ---------------------------------------------
    dims = pd.DataFrame({lab: segment_dimensions(g) for lab, g in geoms.items()})
    dims = dims.reindex(list(segment_dimensions(geoms[cols[0]])))
    d = dims.copy()
    rng, pct = _spread(d, cols)
    d["range_mm"] = rng * 1000.0
    d["range_pct_of_mean"] = pct
    rep["segment_dimension"] = d

    # which joint each body's dimension was measured to, and what else it parents
    srcs = {lab: dimension_sources(g) for lab, g in geoms.items()}
    ref = srcs[cols[0]]
    src_rows = {}
    for body, info in ref.items():
        row = {"measured_to": info["joint"],
               "body_also_parents": ", ".join(info["also_parents"]) or "-"}
        differing = [c for c in cols
                     if srcs[c].get(body, {}).get("joint") != info["joint"]]
        if differing:
            # the long axis resolving to a DIFFERENT joint in another model means
            # that row is not comparing like with like — say so rather than hide it
            row["WARNING"] = ("longest offset is a different joint in: "
                              + ", ".join(f"{c} -> {srcs[c][body]['joint']}"
                                          for c in differing))
        src_rows[body] = row
    for body, info in geoms[cols[0]]["bodies"].items():
        src_rows.setdefault(body, {"measured_to": "-", "body_also_parents": "-"})
        src_rows[body]["meshes"] = ", ".join(m for m, _ in info.get("meshes") or []) or "-"
    rep["dimension_source"] = pd.DataFrame(src_rows).T

    # ---- segment size from the SCALED bone meshes -------------------------
    # Covers every body, including the terminal ones (patella, toes, hand) that
    # parent no joint and so have no joint-to-joint length at all.
    sizes = pd.DataFrame({lab: segment_sizes(g, geometry) for lab, g in geoms.items()})
    if not sizes.empty:
        sizes = sizes.reindex([f"{b}_{k}" for b in geoms[cols[0]]["bodies"]
                               for k in ("depth", "height", "width")]).dropna(how="all")
        sz = sizes.copy()
        rng, pct = _spread(sz, cols)
        sz["range_mm"] = rng * 1000.0
        sz["range_pct_of_mean"] = pct
        rep["segment_size"] = sz
    else:
        print("[model_report] no generic meshes found, so segment_size and the "
              "stature estimate are unavailable.\n"
              "               The scaled .osim store only mesh FILENAMES, so the "
              "generic geometry has to be reachable. Either:\n"
              "                 - copy the model family's Geometry/ folder in "
              "beside the models (bioscout ships one at "
              "bioscout/models/Geometry), or\n"
              "                 - pass --geometry <that folder> / "
              "geometry='<that folder>'.")

    # ---- standing-height estimate ----------------------------------------
    hb, heights = {}, {}
    for lab, g in geoms.items():
        col, gaps = {}, set()
        for sd in ("r", "l"):
            for k, v in model_height(g, geometry, side=sd).items():
                if k == "_missing":
                    gaps.update(v); continue
                col[f"{k} ({sd})"] = v
        if gaps:
            print(f"[model_report] {lab}: no stature estimate — the vertical chain "
                  f"is missing {', '.join(sorted(gaps))} (the mesh-based terms need "
                  f"the generic geometry).")
        if col:
            r_t, l_t = col.get("total (r)"), col.get("total (l)")
            both = [v for v in (r_t, l_t) if v is not None]
            if both:
                col["STATURE ESTIMATE (mean of sides)"] = sum(both) / len(both)
                heights[lab] = col["STATURE ESTIMATE (mean of sides)"]
        hb[lab] = col
    hbd = pd.DataFrame(hb)
    if not hbd.empty:
        h2 = hbd.copy()
        rng, pct = _spread(h2, cols)
        h2["range_mm"] = rng * 1000.0
        h2["range_pct_of_mean"] = pct
        rep["height_breakdown"] = h2
    if heights:
        rep["totals"] = pd.concat([
            rep["totals"],
            pd.DataFrame({lab: {"stature_estimate_m": round(v, 4),
                                "BMI_at_this_mass": round(
                                    float(totals[lab]["total_mass_kg"]) / v ** 2, 1)}
                          for lab, v in heights.items()})])

    # ---- widths from PAIRED child joints ---------------------------------
    bw = pd.DataFrame({lab: bilateral_widths(g) for lab, g in geoms.items()})
    if not bw.empty:
        b2 = bw.copy()
        rng, pct = _spread(b2, cols)
        b2["range_mm"] = rng * 1000.0
        b2["range_pct_of_mean"] = pct
        rep["bilateral_width"] = b2

    # ---- mesh scale factors ---------------------------------------------
    rows = {}
    for lab, g in geoms.items():
        for b, v in g["bodies"].items():
            s = v["mesh_scale"]
            rows.setdefault(b, {})[lab] = ("  ".join(f"{x:.4f}" for x in s)
                                           if s else "")
    rep["mesh_scale"] = pd.DataFrame(rows).T.reindex(list(geoms[cols[0]]["bodies"]))

    # ---- left/right asymmetry WITHIN each model --------------------------
    # A model whose left and right femur differ was scaled per side; one whose
    # sides match was scaled symmetrically. Worth knowing before averaging legs.
    asym = {}
    for lab, g in geoms.items():
        dd = segment_dimensions(g); mm = {b: v["mass"] for b, v in g["bodies"].items()}
        col = {}
        # dimension keys are "<body>_r_<x|y|z>" / "<body>_r_length" since the rows
        # are named by segment, so match the SIDE token, not a trailing "_r".
        #
        # Compare MAGNITUDES, |r| - |l|, not the signed values. Left and right
        # body frames are MIRRORED about the mediolateral axis, so a perfectly
        # symmetric model has z_l = -z_r and a signed r - l reports 2*z as an
        # "asymmetry". Checked on Addbio, which is symmetric by construction:
        # signed r - l gives -17.5 mm on humerus_z, 47.6 mm on ulna_z and
        # 24.9 mm on radius_z, while |r| - |l| is 0.000 on every component.
        _side = re.compile(r"^(.*)_r(_[xyz]|_length)$")
        for key in dd:
            m = _side.match(key)
            if not m:
                continue
            lkey = f"{m.group(1)}_l{m.group(2)}"
            if lkey in dd:
                col[f"dim {m.group(1)}_r/l{m.group(2)} (mm)"] = (
                    abs(dd[key]) - abs(dd[lkey])) * 1000.0
        for b in mm:
            if b.endswith("_r") and b[:-2] + "_l" in mm:
                col[f"mass {b[:-2]}_r/l (kg)"] = mm[b] - mm[b[:-2] + "_l"]
                # masses are scalars — no mirroring, so a signed difference is right
        asym[lab] = col
    rep["asymmetry"] = pd.DataFrame(asym)

    # ---- scaling intent --------------------------------------------------
    if setups:
        srows = {}
        for lab, sp in setups.items():
            s = read_scale_setup(sp)
            srows[lab] = {
                "subject_mass": s["subject_mass"],
                "subject_height": s["subject_height"],
                "preserve_mass_distribution": s["preserve_mass_distribution"],
                "scaling_order": s["scaling_order"],
                "model_scaler_apply": s["model_scaler_apply"],
                "marker_placer_apply": s["marker_placer_apply"],
                "n_measurements": len(s["measurements"]),
                "n_measurements_applied": sum(m["apply"] for m in s["measurements"].values()),
                "n_manual_scale_overrides": len(s["manual_scales"]),
                "manual_scaled_segments": ", ".join(sorted(s["manual_scales"])) or "-",
                "file": os.path.basename(s["path"]),
            }
        rep["scale_setup"] = pd.DataFrame(srows)

    if verbose:
        _print(rep, cols)
    if out:
        _write(rep, out)
        if verbose:
            print(f"[model_report] wrote {out}")
    if figures:
        fig_dir = figures if isinstance(figures, str) else (
            os.path.dirname(os.path.abspath(out)) if out
            else os.path.dirname(os.path.abspath(next(iter(paths.values())))))
        prefix = (os.path.splitext(os.path.basename(out))[0] if out
                  else "model_comparison")
        rep["_figures"] = make_figures(rep, fig_dir, prefix=prefix, verbose=verbose)
    return rep


def _mesh_style(geom) -> str:
    """"isotropic" if every body's mesh scale is uniform across x/y/z."""
    seen = []
    for v in geom["bodies"].values():
        s = v["mesh_scale"]
        if s:
            seen.append(max(s) - min(s) < 1e-9)
    if not seen:
        return "no mesh scale factors"
    return "isotropic" if all(seen) else "per-axis (anisotropic)"


def _print(rep, cols):
    fmt = lambda x: f"{x:10.4f}" if isinstance(x, float) else str(x)
    for key in ("totals", "scale_setup", "height_breakdown", "segment_mass",
                "segment_mass_fraction", "segment_dimension", "segment_size",
                "bilateral_width", "dimension_source", "mesh_scale", "asymmetry"):
        if key not in rep or rep[key].empty:
            continue
        print()
        print(f"=== {key} " + "=" * max(0, 60 - len(key)))
        print(rep[key].to_string(float_format=fmt))


def _write(rep, out: str):
    import pandas as pd
    if str(out).lower().endswith((".xlsx", ".xlsm")):
        with pd.ExcelWriter(out) as xl:
            for k, df in rep.items():
                if hasattr(df, "empty") and not df.empty:
                    df.to_excel(xl, sheet_name=k[:31])
    else:
        stem, ext = os.path.splitext(out)
        ext = ext or ".csv"
        for k, df in rep.items():
            if hasattr(df, "empty") and not df.empty:
                df.to_csv(f"{stem}_{k}{ext}")



# --------------------------------------------------------------------------- #
# figures
# --------------------------------------------------------------------------- #
# Palette: the first three slots of the validated categorical theme. Three is the
# all-pairs cap, and three models is what this typically compares.
#   node scripts/validate_palette.js "#2a78d6,#eb6834,#1baf7a" --mode light \
#        --surface "#fcfcfb" --pairs all      ->  ALL CHECKS PASS
#   worst all-pairs CVD dE 9.2 (deutan), normal-vision 24.0. The aqua slot is
#   2.74:1 on the light surface, so the contrast WARN's relief applies: every
#   figure carries a legend plus visible labels, and the .xlsx is the table view.
SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300",
          "#4a3aa7", "#e34948")
SURFACE  = "#fcfcfb"
INK      = "#0b0b0b"
INK_2    = "#52514e"
MUTED    = "#898781"
GRID     = "#e1e0d9"
BASELINE = "#c3c2b7"
DIVERGE  = ("#2a78d6", "#f0efec", "#e34948")   # cool | neutral gray | warm

_ROW_H   = 0.34      # inches per category row
_SLOT    = 0.62      # share of a row the bar group may use — the rest is air
_GAPFRAC = 0.16      # surface gap between adjacent bars, as a share of one bar


def _style(ax, xlabel=None, xgrid=True, zeroline=False):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(BASELINE)
        ax.spines[side].set_linewidth(1.0)
    if zeroline:
        ax.spines["left"].set_visible(False)
        ax.axvline(0, color=BASELINE, linewidth=1.0, zorder=2)
    ax.tick_params(colors=MUTED, labelsize=8, length=0)
    for lbl in list(ax.get_xticklabels()) + list(ax.get_yticklabels()):
        lbl.set_color(INK_2)
    if xgrid:
        ax.grid(axis="x", color=GRID, linewidth=1.0, linestyle="-")   # hairline, solid
        ax.set_axisbelow(True)
    if xlabel:
        ax.set_xlabel(xlabel, color=INK_2, fontsize=9)


def _barh_group(ax, d, cols, ylabels=True):
    """Grouped horizontal bars. Series order runs TOP-to-bottom so it matches the
    legend, marks are thin, and white does the separating — never a stroke."""
    import numpy as np
    y = np.arange(len(d))
    n = len(cols)
    h = _SLOT / n * (1 - _GAPFRAC)
    for i, c in enumerate(cols):
        off = ((n - 1) / 2 - i) * (_SLOT / n)          # slot 1 on top
        ax.barh(y + off, d[c].values, height=h, color=SERIES[i], label=str(c),
                zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels(d.index if ylabels else [""] * len(d), fontsize=8)
    ax.set_ylim(-0.6, len(d) - 0.4)
    ax.invert_yaxis()          # largest spread at the top


def _label_extremes(ax, d, cols, unit, n_label=3):
    """Direct labels are sparing on purpose — only the widest-spread rows, and
    never the same value twice."""
    rng = (d[cols].max(axis=1) - d[cols].min(axis=1))
    xmax = float(d[cols].values.max())
    seen, done = set(), 0
    for name in rng.sort_values(ascending=False).index:
        if done >= n_label:
            break
        key = round(float(rng[name]), 3)
        if key in seen or key == 0:
            continue
        seen.add(key)
        row = list(d.index).index(name)
        ax.text(float(d.loc[name, cols].max()) + xmax * 0.02, row,
                f"\u0394{rng[name]:.3g}{unit}", va="center", ha="left",
                fontsize=7.5, color=INK_2, zorder=4)
        done += 1
    ax.set_xlim(0, xmax * 1.18)


def _deviation(d, cols):
    """Each model's signed % departure from the mean ACROSS models — the panel
    that makes small segments legible and shows WHICH WAY each one differs."""
    mean = d[cols].mean(axis=1)
    return (d[cols].sub(mean, axis=0)).div(mean, axis=0) * 100.0


def _titles(fig, title, subtitle=None, footnote=None):
    """Place the title block a FIXED distance from the top edge.

    Offsets must be in inches: these figures range from ~4 to ~10 inches tall, and
    one figure-fraction offset cannot serve both (0.04 of 4 in is 0.17 in, of
    10 in is 0.4 in) — which is how the subtitle ended up on top of the title.
    """
    H = fig.get_figheight()
    fig.text(0.005, 1 - 0.26 / H, title, fontsize=12.5, color=INK,
             va="top", ha="left")
    if subtitle:
        fig.text(0.005, 1 - 0.52 / H, subtitle, fontsize=8.5, color=INK_2,
                 va="top", ha="left")
    if footnote:
        fig.text(0.005, 0.13 / H, footnote, fontsize=7.5, color=MUTED,
                 style="italic", va="bottom", ha="left")
    return 1 - 0.80 / H          # the top of the plot area


def _legend_above(fig, ax, cols, extra=None):
    """A legend is always present for >= 2 series, and it sits ABOVE the plot —
    never floating over the marks."""
    h, l = ax.get_legend_handles_labels()
    # top-RIGHT: the title and subtitle own the top-left, so a legend there
    # would sit on top of them.
    leg = fig.legend(h[:len(cols)], l[:len(cols)], loc="upper right",
                     bbox_to_anchor=(0.997, 1.002), frameon=False, fontsize=9,
                     ncol=len(cols), handlelength=1.0, handleheight=1.0,
                     columnspacing=1.6, borderaxespad=0.2)
    for t in leg.get_texts():
        t.set_color(INK_2)
    return leg


def _two_panel(rep, key, cols, scale, unit, title, subtitle, xlabel, note=None):
    """Absolute values | signed % deviation from the cross-model mean."""
    import matplotlib.pyplot as plt
    d = rep[key][cols] * scale
    d = d.loc[(d.max(axis=1) - d.min(axis=1)).sort_values(ascending=False).index]
    dev = _deviation(d, cols)

    fig, axes = plt.subplots(1, 2, figsize=(11.6, _ROW_H * len(d) + 2.35),
                             facecolor=SURFACE,
                             gridspec_kw={"width_ratios": [1.35, 1.0], "wspace": 0.06})
    _barh_group(axes[0], d, cols)
    _label_extremes(axes[0], d, cols, unit)
    _style(axes[0], xlabel=xlabel)

    _barh_group(axes[1], dev, cols, ylabels=False)
    # guard the all-identical case: two models that share a mass distribution
    # make every deviation exactly 0, and set_xlim(0, 0) is singular
    lim = float(dev.abs().values.max()) * 1.12 or 1.0
    axes[1].set_xlim(-lim, lim)
    _style(axes[1], xlabel="departure from the mean of the three models (%)",
           zeroline=True)

    top = _titles(fig, title, subtitle, footnote=note)
    _legend_above(fig, axes[0], cols)
    H = fig.get_figheight()
    fig.subplots_adjust(left=0.155, right=0.995, top=top,
                        bottom=(0.70 if note else 0.48) / H)
    return fig


def _split_dims(rep):
    """(length rows, per-axis rows) of the segment_dimension table."""
    idx = list(rep["segment_dimension"].index)
    return ([i for i in idx if i.endswith("_length")],
            [i for i in idx if not i.endswith("_length")])


def _fig_dimensions(rep, cols):
    """Segment LENGTH per body — one row each, so the whole skeleton fits."""
    import pandas as pd
    lengths, _ = _split_dims(rep)
    sub = {k: v for k, v in rep.items() if not hasattr(v, "loc")}
    d = rep["segment_dimension"].loc[lengths].copy()
    d.index = [i[: -len("_length")] for i in lengths]
    note = None
    # whole-model height on the same axis as the segments it is made of
    if "height_breakdown" in rep:
        row = "STATURE ESTIMATE (mean of sides)"
        if row in rep["height_breakdown"].index:
            h = rep["height_breakdown"].loc[[row]].copy()
            h.index = ["WHOLE MODEL (stature est.)"]
            d = pd.concat([h.reindex(columns=d.columns), d])
            note = ("stature estimate = the vertical chain sole \u2192 vertex summed in "
                    "the neutral pose (see the height_breakdown sheet); it is an "
                    "approximation, not a measured height")
    sub["segment_dimension"] = d
    sub["totals"] = rep["totals"]
    return _two_panel(
        sub, "segment_dimension", cols, 1000.0, " mm",
        "Segment length, and whole-model height",
        "per body: |offset from its origin to its distal joint centre|, the distance "
        "each scale factor acts on. Top row: the whole standing chain.",
        "length (mm)", note=note)


def _fig_dimension_axes(rep, cols, n_bodies=8):
    """The x/y/z breakdown, for the bodies whose LENGTH disagrees most.

    All 16 bodies x 4 rows is 64 rows — unreadable in one figure — and the axis
    detail only matters where the models actually differ. Which bodies were shown
    is stated on the figure, so nothing is silently truncated.
    """
    import numpy as np
    import matplotlib.pyplot as plt
    d_all = rep["segment_dimension"]
    lengths, axes_rows = _split_dims(rep)
    rank = (d_all.loc[lengths, cols].max(axis=1)
            - d_all.loc[lengths, cols].min(axis=1)).sort_values(ascending=False)
    bodies = [i[: -len("_length")] for i in rank.index[:n_bodies]]
    keep = [f"{b}_{a}" for b in bodies for a in "xyz" if f"{b}_{a}" in axes_rows]
    if not keep:
        return None
    d = d_all.loc[keep, cols] * 1000.0

    fig, ax = plt.subplots(figsize=(9.4, _ROW_H * len(d) + 2.7), facecolor=SURFACE)
    _barh_group(ax, d, cols)
    lim = float(np.abs(d.values).max()) * 1.12 or 1.0
    ax.set_xlim(-lim, lim)
    _style(ax, xlabel="offset component in the parent body's frame (mm)",
           zeroline=True)
    # a hairline between bodies, so the x/y/z triplets read as groups
    for i in range(3, len(d), 3):
        ax.axhline(i - 0.5, color=GRID, linewidth=1.0, zorder=1)
    top = _titles(fig, "Segment dimensions by axis",
                  "signed components of the same offsets; negative simply means "
                  "the joint sits below/behind the body origin",
                  footnote=(f"the {len(bodies)} bodies whose length disagrees most, "
                            f"worst first: {', '.join(bodies)}"))
    _legend_above(fig, ax, cols)
    H = fig.get_figheight()
    fig.subplots_adjust(left=0.20, right=0.99, top=top, bottom=0.85 / H)
    return fig


def _fig_sizes(rep, cols):
    """Bounding-box depth / height / width for EVERY body, one panel per axis.

    Three panels of 22 rows beat one panel of 66: the bodies stay on a single
    shared y-axis and the axes are directly comparable side by side.
    """
    import numpy as np
    import matplotlib.pyplot as plt
    if "segment_size" not in rep:
        return None
    d_all = rep["segment_size"]
    bodies, seen = [], set()
    for i in d_all.index:
        b = i.rsplit("_", 1)[0]
        if b not in seen:
            seen.add(b); bodies.append(b)
    axes_names = ("depth", "height", "width")
    # NOT sharey: with a shared y-axis the later panels' blank tick labels win and
    # every body name disappears. Each panel keeps its own axis; only the first
    # draws the names, the others just hide their labels.
    fig, axs = plt.subplots(1, 3, figsize=(13.2, _ROW_H * len(bodies) + 2.6),
                            facecolor=SURFACE, gridspec_kw={"wspace": 0.04})
    xmax = float(np.nanmax(d_all[cols].values)) * 1000.0 * 1.08
    labels = {"depth": "depth \u2014 x, anteroposterior (mm)",
              "height": "height \u2014 y, superoinferior (mm)",
              "width": "width \u2014 z, mediolateral (mm)"}
    for k, (ax, aname) in enumerate(zip(axs, axes_names)):
        rows = [f"{b}_{aname}" for b in bodies]
        d = d_all.reindex(rows)[cols] * 1000.0
        d.index = bodies
        _barh_group(ax, d, cols)
        ax.set_xlim(0, xmax)
        # the axis label carries the anatomical meaning, so no per-panel title is
        # needed — one less thing to collide with the subtitle
        _style(ax, xlabel=labels[aname])
        if k:
            ax.tick_params(labelleft=False)
    top = _titles(
        fig, "Segment size",
        "bounding box of each body's SCALED bone meshes, in the body frame — the "
        "only size measure that also covers patella, toes and hand, which parent "
        "no joint",
        footnote="torso includes the skull and jaw meshes, so its height is "
                 "head-to-lumbar, not thorax alone (see the dimension_source "
                 "sheet for each body's meshes)")
    _legend_above(fig, axs[0], cols)
    H = fig.get_figheight()
    fig.subplots_adjust(left=0.105, right=0.995, top=top, bottom=0.80 / H)
    return fig


def _fig_mass(rep, cols):
    note = None
    try:
        tot = [float(v) for v in rep["totals"].loc["total_mass_kg"]]
        # tolerance, not equality: summing 22 floats gives 67.00000000000003 vs
        # 66.99999999999999, which an exact test calls "different"
        if max(tot) - min(tot) < 0.05:
            note = (f"total body mass is the same in every model "
                    f"({sum(tot) / len(tot):.1f} kg) \u2014 what differs is the "
                    f"DISTRIBUTION of that mass, not how heavy the subject is")
    except Exception:
        pass
    return _two_panel(
        rep, "segment_mass", cols, 1.0, " kg",
        "Segment mass",
        "per-body mass, and how far each model sits from the three-model mean",
        "segment mass (kg)", note=note)


def _fig_mesh_scale(rep, cols):
    """Diverging heatmap centred on 1.0.

    Scale factors have a true neutral (1.0 = geometry untouched), so this is
    polarity: two opposite hues with a NEUTRAL GRAY midpoint, never a rainbow.
    Per-axis sub-columns expose anisotropic scaling that a mean would hide.
    """
    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

    ms = rep["mesh_scale"]
    bodies = list(ms.index)
    vals, xlab = [], []
    for c in cols:
        for k, axis_name in enumerate("xyz"):
            col = []
            for b in bodies:
                txt = str(ms.loc[b, c]).split()
                col.append(float(txt[k]) if len(txt) == 3 else np.nan)
            vals.append(col); xlab.append(axis_name)
    M = np.array(vals).T
    if not np.isfinite(M).any():
        return None

    cmap = LinearSegmentedColormap.from_list("diverge_1", list(DIVERGE))
    lim = float(np.nanmax(np.abs(M - 1.0))) or 0.1
    norm = TwoSlopeNorm(vmin=1 - lim, vcenter=1.0, vmax=1 + lim)

    fig, ax = plt.subplots(figsize=(0.78 * M.shape[1] + 3.9, _ROW_H * len(bodies) + 2.0),
                           facecolor=SURFACE)
    ax.imshow(M, cmap=cmap, norm=norm, aspect="auto")
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]
            if not np.isfinite(v):
                continue
            r, g, b, _ = cmap(norm(v))
            lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
            # a label inside a coloured fill picks white or ink by luminance
            ax.text(j, i, f"{v:.3f}", ha="center", va="center", fontsize=6.8,
                    color=("#ffffff" if lum < 0.55 else INK))
    ax.set_xticks(range(M.shape[1])); ax.set_xticklabels(xlab, fontsize=8)
    ax.set_yticks(range(len(bodies))); ax.set_yticklabels(bodies, fontsize=8)
    ax.tick_params(colors=MUTED, length=0, labelsize=8)
    for lbl in list(ax.get_xticklabels()) + list(ax.get_yticklabels()):
        lbl.set_color(INK_2)
    for sp in ax.spines.values():
        sp.set_visible(False)
    for i, c in enumerate(cols):
        # y = 1.0 in axes fraction is the TOP of the grid (imshow origin is
        # upper); y = 0 put the model names on top of the last row's cells.
        ax.annotate(str(c), xy=(i * 3 + 1, 1.0), xycoords=("data", "axes fraction"),
                    xytext=(0, 7), textcoords="offset points",
                    ha="center", va="bottom", fontsize=9.5, color=INK)
        if i:
            ax.axvline(i * 3 - 0.5, color=SURFACE, linewidth=3)   # surface gap
    top = _titles(fig, "Mesh scale factors",
                  "per axis; 1.000 = geometry unchanged from the generic model. "
                  "Equal x/y/z = isotropic scaling.")
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    cb = fig.colorbar(sm, ax=ax, fraction=0.045, pad=0.03)
    cb.set_label("scale factor (1.0 = unchanged)", color=INK_2, fontsize=8.5)
    cb.ax.tick_params(colors=MUTED, labelsize=7.5)
    cb.outline.set_visible(False)
    # leave room on the right for the colorbar's tick labels, and at the top for
    # the model-name band above the grid
    # leave room on the right for the colorbar's tick labels, and a band above
    # the grid for the model names
    fig.subplots_adjust(left=0.135, right=0.86, top=top - 0.22 / fig.get_figheight(),
                        bottom=0.32 / fig.get_figheight())
    return fig


def _fig_asymmetry(rep, cols):
    """Right-minus-left WITHIN each model. Rows that are zero everywhere are
    dropped; a model that is zero in every remaining row is named in the note,
    because an all-zero series draws no mark and would otherwise look missing."""
    import matplotlib.pyplot as plt
    a = rep["asymmetry"]
    keep = a.index[(a[cols].abs() > 1e-9).any(axis=1)]
    if len(keep) == 0:
        return None
    d = a.loc[keep, cols]
    d = d.loc[d.abs().max(axis=1).sort_values(ascending=False).index]
    flat = [c for c in cols if float(d[c].abs().max()) <= 1e-9]

    fig, ax = plt.subplots(figsize=(9.0, _ROW_H * len(d) + 2.5), facecolor=SURFACE)
    _barh_group(ax, d, cols)
    lim = float(d.abs().values.max()) * 1.15 or 1.0
    ax.set_xlim(-lim, lim)
    _style(ax, xlabel="|right| \u2212 |left|   (mm for dimensions, kg for masses)",
           zeroline=True)
    note = None
    if flat:
        note = (f"{', '.join(flat)}: symmetric in every row shown "
                f"(exactly zero, so no bar is drawn)")
    top = _titles(fig, "Left\u2013right asymmetry within each model",
                  "|right| \u2212 |left| per component \u2014 magnitudes, because the two "
                  "sides' frames are mirrored. Rows zero in every model are omitted.",
                  footnote=note)
    _legend_above(fig, ax, cols)
    H = fig.get_figheight()
    fig.subplots_adjust(left=0.30, right=0.985, top=top,
                        bottom=(0.85 if note else 0.62) / H)
    return fig


def make_figures(rep, out_dir=".", prefix="model_comparison", dpi=200,
                 formats=("png",), verbose=True):
    """Render the comparison figures. Returns the list of files written."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    matplotlib.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans"],
        "figure.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.unicode_minus": False, "svg.fonttype": "none",
    })
    cols = list(rep["totals"].columns)
    if len(cols) > len(SERIES):
        print(f"[model_report] {len(cols)} models exceeds the {len(SERIES)}-slot "
              f"palette; figures show the first {len(SERIES)}.")
        cols = cols[:len(SERIES)]
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for name, fn in (("segment_length", _fig_dimensions),
                     ("segment_dimension_axes", _fig_dimension_axes),
                     ("segment_size", _fig_sizes),
                     ("segment_mass", _fig_mass),
                     ("mesh_scale", _fig_mesh_scale),
                     ("asymmetry", _fig_asymmetry)):
        try:
            fig = fn(rep, cols)
        except Exception as exc:          # one bad figure must not lose the rest
            print(f"[model_report] figure {name!r} skipped: {type(exc).__name__}: {exc}")
            continue
        if fig is None:
            continue
        for ext in formats:
            path = os.path.join(out_dir, f"{prefix}_{name}.{ext}")
            fig.savefig(path, dpi=dpi)
            written.append(path)
        plt.close(fig)
    if verbose and written:
        print(f"[model_report] {len(written)} figure file(s) -> {out_dir}")
    return written

def main(argv=None):
    """CLI. With NO arguments this compares every ``.osim`` beside the script and
    writes the workbook and figures there — so dropping this file into a folder of
    models and running ``python model_report.py`` is enough."""
    import argparse
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        prog="python model_report.py",
        description="Compare segment masses, dimensions and height across .osim "
                    "models. With no arguments: every .osim in this script's own "
                    "folder, tables + figures written beside them.")
    ap.add_argument("models", nargs="*", default=None,
                    help="a folder of .osim files, or the .osim paths themselves "
                         "(default: the folder this script is in)")
    ap.add_argument("-o", "--out", default=None,
                    help="write tables to .xlsx (one sheet each) or .csv")
    ap.add_argument("--geometry", default=None, metavar="DIR",
                    help="folder holding the generic .vtp meshes (defaults to "
                         "Geometry/ beside the models, then bioscout's own copy)")
    ap.add_argument("-f", "--figures", nargs="?", const=True, default=None,
                    metavar="DIR",
                    help="render the figures (.png + .pdf); optionally into DIR")
    ap.add_argument("--setups", nargs="*", default=None, metavar="LABEL=SETUP.xml",
                    help="ScaleTool setup XMLs, e.g. Feri=Feri_Scaled_Setup.xml")
    a = ap.parse_args(argv)
    bare = not a.models
    models = here if bare else (a.models[0] if len(a.models) == 1 else a.models)

    setups = a.setups
    if setups is None and bare:
        # pair each *_Setup.xml with the model whose name it shares
        setups = {}
        for f in sorted(os.listdir(here)):
            if f.lower().endswith(".xml") and "setup" in f.lower():
                setups[f.split("_")[0]] = os.path.join(here, f)
        setups = setups or None
    elif setups:
        setups = {}
        for item in a.setups:
            lab, _, pth = item.partition("=")
            setups[lab if pth else os.path.basename(lab).split("_")[0]] = pth or lab

    out = a.out
    figures = a.figures
    if bare:                       # "just run it" -> do everything, here
        out = out or os.path.join(here, "model_comparison.xlsx")
        figures = True if figures is None else figures
        print(f"[model_report] no arguments — comparing the .osim files in {here}")

    compare_models(models, out=out, setups=setups, figures=figures,
                   geometry=a.geometry)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
