"""Model scaling with bioscout.pyosim, for iterations with ``engine: pyosim``.

Same inputs and outputs as :func:`bioscout.model.scale.osim_scale.scale_model`, and
the same preparation, done here as plain XML/text without OpenSim (2026-11-03: a
pyosim iteration never touches OpenSim):

  * trailing NUL padding stripped from the generic (some warping tools add it);
  * markers in BatchSettings.markers_to_skip and markers on ground dropped from a
    scale-ready copy of the generic and of the marker-set file;
  * joint centres (Harrington hips, knee/ankle midpoints) added to a scaling-only
    copy of the static TRC;
  * a ScaleTool setup written: the iteration's ``scale_tool`` template with the marker
    aliases applied (every marker it names must be in the static TRC), or a
    MeasurementSet from ``measurement_spec`` (pairs in both the model marker set and
    the TRC, bodies the model has);

then pyosim measures, scales (bodies, markers, muscle lengths) and registers the
markers on the static pose, leaving the derived joint-centre markers out of that
registration, as the OpenSim route does. The setup is a normal ScaleTool file, so the
OpenSim GUI can open it, but nothing here runs OpenSim.
"""
import os
import re
import shutil
import xml.etree.ElementTree as ET

from bioscout.model.scale import measurements as _sm
from bioscout.model.scale.measurements import JC_MARKERS


def _strip_trailing_nulls(path):
    raw = open(path, "rb").read()
    end = raw.rfind(b"</OpenSimDocument>")
    if end != -1 and raw[end + len(b"</OpenSimDocument>"):].strip(b"\r\n\t \x00"):
        return path
    if end != -1 and b"\x00" in raw[end:]:
        shutil.copyfile(path, path + ".nulbak")
        with open(path, "wb") as f:
            f.write(raw[:end + len(b"</OpenSimDocument>")] + b"\n")
        print(f"[scale] stripped trailing NUL padding from {os.path.basename(path)} (backup .nulbak)")
    return path


def _skip_names():
    try:
        from bioscout.utils import settings as _st
        return {str(s).upper() for s in getattr(getattr(_st, "BatchSettings", None), "markers_to_skip", []) or []}
    except Exception:                                    # noqa: BLE001
        return set()


def _on_ground(mk):
    pf = (mk.findtext("socket_parent_frame") or mk.findtext("body") or "").strip().lower()
    return pf.endswith("ground")


def _scaleready_model(generic, skip, tmp):
    tree = ET.parse(generic)
    ms = tree.getroot().find("./Model/MarkerSet/objects")
    drop = [mk for mk in (ms if ms is not None else []) if mk.get("name", "").upper() in skip or _on_ground(mk)]
    if not drop:
        return generic
    for mk in drop:
        ms.remove(mk)
    out = os.path.join(tmp, os.path.splitext(os.path.basename(generic))[0] + "_scaleready.osim")
    tree.write(out, encoding="UTF-8", xml_declaration=True)
    print(f"[scale] dropped unplaceable markers from model: {[m.get('name') for m in drop]}")
    return out


def _sanitize_markerset(src, skip, tmp):
    txt = open(src, errors="replace").read()
    removed = []

    def _filt(m):
        name, body = m.group(1), m.group(2)
        pf = re.search(r"<socket_parent_frame>([^<]+)", body)
        if name.upper() in skip or (pf.group(1) if pf else "").strip().lower().endswith("ground"):
            removed.append(name)
            return ""
        return m.group(0)
    new = re.sub(r'<Marker name="([^"]+)">(.*?)</Marker>\s*', _filt, txt, flags=re.S)
    if not removed:
        return src
    out = os.path.join(tmp, os.path.splitext(os.path.basename(src))[0] + "_scaleready.xml")
    open(out, "w").write(new)
    print(f"[scale] dropped unplaceable markers from marker set: {removed} -> {os.path.basename(out)}")
    return out


def _model_names(model_path, markerset):
    root = ET.parse(model_path).getroot()
    bodies = {b.get("name") for b in root.iterfind("./Model/BodySet/objects/Body")}
    if markerset and os.path.isfile(markerset):          # GenericModelMaker replaces the model's markers
        markers = _sm.markerset_file_names(markerset) or set()
    else:
        markers = {m.get("name") for m in root.iterfind("./Model/MarkerSet/objects/Marker")}
    return markers, bodies


def _measurement_xml(name, pairs, bodies):
    m = ET.Element("Measurement", name=name)
    ET.SubElement(m, "apply").text = "true"
    ps = ET.SubElement(ET.SubElement(m, "MarkerPairSet"), "objects")
    for a, b in pairs:
        ET.SubElement(ET.SubElement(ps, "MarkerPair"), "markers").text = f" {a} {b}"
    bs = ET.SubElement(ET.SubElement(m, "BodyScaleSet"), "objects")
    for body, axes in sorted(bodies.items()):
        ET.SubElement(ET.SubElement(bs, "BodyScale", name=body), "axes").text = " " + " ".join(axes.upper())
    return m


def _write_setup(path, generic, markerset, trc, scaled, outdir, mass, t_range, scale_tool, spec, aliases):
    _, have_trc, _, _ = _sm.read_trc(trc)
    have_trc = set(have_trc)
    if scale_tool:
        tree = ET.parse(scale_tool)
        root = tree.getroot()
        tool = root.find("ScaleTool")
        ms = tool.find("ModelScaler")
        al, missing, n = dict(aliases or {}), [], 0
        for meas in ms.iter("Measurement"):
            n += 1
            for mp in meas.iter("MarkerPair"):
                e = mp.find("markers")
                names = [al.get(x, x) for x in (e.text or "").split()]
                e.text = " " + " ".join(names)
                missing += [f"{meas.get('name')}:{x}" for x in names if x not in have_trc]
        if n == 0:
            raise RuntimeError(f"scale_tool {scale_tool} has an EMPTY MeasurementSet")
        if missing:
            raise RuntimeError(f"scale_tool {scale_tool}: markers not in the static TRC {trc}: {', '.join(missing)}")
        print(f"[scale] ScaleTool template {os.path.basename(str(scale_tool))}: {n} measurements")
    else:
        root = ET.Element("OpenSimDocument", Version="40600")
        tool = ET.SubElement(root, "ScaleTool", name="ModelScaling")
        ET.SubElement(tool, "GenericModelMaker")
        ms = ET.SubElement(tool, "ModelScaler")
        ET.SubElement(ms, "scaling_order").text = " measurements"
        mset = ET.SubElement(ET.SubElement(ms, "MeasurementSet"), "objects")
        have_model, have_bodies = _model_names(generic, markerset)
        report, skipped = [], []
        for name, pairs, bodies in _sm.resolve_spec(spec or _sm.DEFAULT_SPEC, aliases):
            ok_p = [(a, b) for a, b in pairs if {a, b} <= have_model and {a, b} <= have_trc]
            ok_b = {b: ax for b, ax in bodies.items() if b in have_bodies}
            if not ok_p or not ok_b:
                skipped.append(name)
                continue
            mset.append(_measurement_xml(name, ok_p, ok_b))
            report.append(f"{name}: {'+'.join(a + '-' + b for a, b in ok_p)}")
        print(f"[scale] MeasurementSet: {len(report)} measurements" + (f" (SKIPPED {', '.join(skipped)})" if skipped else ""))
        if not report:
            raise RuntimeError("empty MeasurementSet with linear_scaling=True")
        tree = ET.ElementTree(root)

    def put(parent, tag, text):
        e = parent.find(tag)
        if e is None:
            e = ET.SubElement(parent, tag)
        e.text = text
    put(tool, "mass", f"{mass:g}" if mass else (tool.findtext("mass") or "-1"))
    put(tool, "path_to_subject", "")
    gmm = tool.find("GenericModelMaker")
    put(gmm, "model_file", generic)
    put(gmm, "marker_set_file", markerset or "Unassigned")
    put(ms, "apply", "true")
    put(ms, "marker_file", trc)
    put(ms, "time_range", f" {t_range[0]!r} {t_range[1]!r}")
    put(ms, "output_model_file", scaled)
    put(ms, "output_scale_file", os.path.join(outdir, "scale_factors_pyosim.xml"))
    mp = tool.find("MarkerPlacer")
    if mp is None:
        mp = ET.SubElement(tool, "MarkerPlacer")
    put(mp, "apply", "false")                # markers are registered by pyosim's own placer pass
    tree.write(path, encoding="UTF-8", xml_declaration=True)
    print(f"[scale] ScaleTool setup written (pyosim, not run by OpenSim): {path}")
    return path


def scale_model(generic_opensim_model_path, static_trc_path, scaled_model_path, scale_setup_output_dir=None,
                mass=None, marker_set_file=None, linear_scaling=True, marker_placer=False,
                marker_aliases=None, measurement_spec=None, scale_tool=None, time_range=None, **_ignored):
    from bioscout.pyosim import scale as _ps
    from bioscout.pyosim.io import read_trc
    log = lambda m: print(m, flush=True)
    outdir = scale_setup_output_dir or os.path.dirname(scaled_model_path) or "."
    os.makedirs(outdir, exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(scaled_model_path)), exist_ok=True)
    generic = _strip_trailing_nulls(os.path.abspath(generic_opensim_model_path))
    scaled = os.path.abspath(scaled_model_path)

    if not linear_scaling and not marker_placer:          # geometry untouched, subject mass only
        _ps.run(generic, static_trc_path, scaled, mass=mass, placer=False, out_dir=outdir, log=log)
        print(f"[scale] (pyosim) linear_scaling=False, marker_placer=False -> geometry unchanged, mass set: {scaled}")
        return None

    tmp = os.path.join(outdir, "_temp_scaling")
    os.makedirs(tmp, exist_ok=True)
    skip = _skip_names()
    generic_s = _scaleready_model(generic, skip, tmp)
    markerset = os.path.abspath(marker_set_file) if marker_set_file and os.path.exists(marker_set_file) else None
    if markerset:
        markerset = _sanitize_markerset(markerset, skip, tmp)
    trc = os.path.abspath(static_trc_path)
    if linear_scaling:
        try:
            trc = _sm.augment_static_trc(static_trc_path,
                                         os.path.join(tmp, os.path.basename(static_trc_path).replace(".trc", "_jc.trc")),
                                         aliases=marker_aliases)
        except Exception as e:                            # noqa: BLE001
            print(f"[scale] [WARNING] could not add joint centres to the static TRC: {e}")
    t = read_trc(trc)[0]
    t_range = tuple(time_range) if time_range else (float(t[0]), float(t[-1]))

    setup = None
    if linear_scaling:
        setup = _write_setup(os.path.join(outdir, "scale_setup.xml"), generic_s, markerset, trc, scaled, outdir,
                             mass, t_range, scale_tool, measurement_spec, marker_aliases)
    print(f"[scale] (pyosim) generic {os.path.basename(generic_s)}, static {os.path.basename(trc)}")
    _ps.run(generic_s, trc, scaled, setup_path=setup, mass=mass, markerset=markerset,
            aliases=marker_aliases, t_range=t_range, placer=bool(marker_placer), placer_exclude=JC_MARKERS,
            out_dir=outdir, log=log)
    sf = os.path.splitext(scaled)[0] + "_scale_factors.xml"
    if os.path.isfile(sf):                                 # beside the OpenSim route's scale_factors.xml
        os.replace(sf, os.path.join(outdir, "scale_factors_pyosim.xml"))
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"[scale] (pyosim) scaled model -> {scaled}")
    return None


def increase_isometric_force(osim_modelPath, muscleList="all", factor=1.0):
    """max_isometric_force x factor -> <model>_increased_<f>.osim, as osim_ops' version, in plain XML."""
    from bioscout.pyosim.muscles import MUSCLE_TAGS
    tree = ET.parse(osim_modelPath)
    objs = tree.getroot().find("./Model/ForceSet/objects")
    n = 0
    for e in (objs if objs is not None else []):
        if e.tag in MUSCLE_TAGS and (muscleList == "all" or e.get("name") in muscleList):
            f = e.find("max_isometric_force")
            if f is not None:
                f.text = repr(float(f.text) * factor)
                n += 1
    out = osim_modelPath.replace(".osim", f"_increased_{factor:.2f}.osim")
    tree.write(out, encoding="UTF-8", xml_declaration=True)
    print(f"[scale] increased isometric force x{factor:.2f} on {n} muscles -> {os.path.basename(out)}")
