"""Read-only checks. None of these write a model.

They are ops rather than a separate API so that a recipe can end with one — a
build that does not verify itself is a build you have to remember to verify.
"""
from __future__ import annotations

from pathlib import Path

from ..introspect import summary as _xml_summary
from ..spec import OpResult, Param, op

__all__ = []


@op("info",
    verb="inspect",
    summary="Model inventory: coordinates, muscles, bodies, markers, wraps",
    needs_opensim=False,
    writes_model=False,
    params=[])
def info(model, out, **_):
    d = _xml_summary(model)
    return OpResult(True, "info", str(model), None, data=d,
                    messages=[f"[model-edit] {d['name']}: {d['coordinates']} coordinates, "
                              f"{d['muscles']} muscles, {d['bodies']} bodies, "
                              f"{d['markers']} markers, {d['wraps']} wraps "
                              f"({d['wraps_scalable']} scalable)"])


@op("check_paths",
    verb="inspect",
    summary="Sweep moment arms and flag discontinuous muscle paths",
    delegates_to="bioscout.change_moment_arms.core.check_model",
    writes_model=False,
    notes=("Run this after ANY wrap edit. Inflating a wrap is the change most "
           "likely to shove a muscle path through a bone, and a discontinuous "
           "moment arm produces a plausible-looking force that is wrong."),
    params=[
        Param("coordinates", "list[str]", default=None, choices_from="coordinates",
              help="Coordinates to sweep (default: all that muscles span)"),
        Param("n", "int", default=40,
              help="Sample points per coordinate sweep"),
    ])
def check_paths(model, out, *, coordinates=None, n=40, **_):
    from bioscout.change_moment_arms.core import check_model

    d = check_model(str(model), coordinates=list(coordinates) if coordinates else None,
                    n=int(n))
    bad = d.get("discontinuous", [])
    return OpResult(
        True, "check_paths", str(model), None, data=d,
        messages=[f"[model-edit] swept {len(d.get('coordinates', []))} coordinate(s); "
                  + (f"DISCONTINUOUS: {', '.join(bad)}" if bad
                     else "no discontinuous muscle paths")])


@op("compare",
    verb="inspect",
    summary="Compare models by mass, segment length, size and mesh scale",
    delegates_to="bioscout.utils.model_report.compare_models",
    needs_opensim=False,
    writes_model=False,
    notes=("Pure XML, so it runs anywhere. This is the report that makes an "
           "unscaled 'scaled' model visible: identical segment lengths and a "
           "mesh scale of 1.0 against the generic."),
    params=[
        Param("against", "list[str]", required=True,
              help="Other .osim files to compare with (the generic, and the "
                   "other iterations)"),
        Param("out_file", "path", default=None,
              help="Write the tables to this .xlsx/.csv"),
        Param("figures", "str", default=None,
              help="Directory for comparison figures"),
    ])
def compare(model, out, *, against, out_file=None, figures=None, **_):
    from bioscout.utils.model_report import compare_models

    models = [str(model)] + [str(a) for a in against]
    rep = compare_models(models, out=str(out_file) if out_file else None,
                         figures=figures, verbose=False)
    keys = sorted(k for k in rep) if isinstance(rep, dict) else []
    return OpResult(True, "compare", str(model), None,
                    data={"tables": keys, "models": models},
                    messages=[f"[model-edit] compared {len(models)} models; "
                              f"tables: {', '.join(keys) or 'none'}"])


@op("diff",
    verb="inspect",
    summary="What changed between two models: wraps, path points, muscle forces",
    needs_opensim=False,
    writes_model=False,
    notes=("Compares as FLOATS. A naive text diff of two OpenSim models shows "
           "dozens of 'differences' that are float-repr noise "
           "(0.006758400000000002 vs 0.0067584000000000021) from a "
           "re-serialisation that changed nothing."),
    params=[
        Param("against", "path", required=True,
              help="The other model"),
        Param("tol", "float", default=1e-12,
              help="Absolute tolerance below which two numbers are the same"),
    ])
def diff(model, out, *, against, tol=1e-12, **_):
    import xml.etree.ElementTree as ET

    from ..introspect import iter_real

    def read(p):
        root = ET.parse(str(p)).getroot()
        rad, pts, mif = {}, [], {}
        for el in iter_real(root):
            tag = getattr(el, "tag", "")
            if isinstance(tag, str) and tag.startswith("Wrap") and el.get("name"):
                r = el.find("radius")
                if r is not None and r.text:
                    rad[el.get("name")] = [float(x) for x in r.text.split()]
        for el in iter_real(root, "PathPoint"):
            loc = el.find("location")
            if loc is not None and loc.text:
                pts.append((el.get("name") or "", [float(x) for x in loc.text.split()]))
        for parent in iter_real(root):
            n = parent.get("name") if hasattr(parent, "get") else None
            e = parent.find("max_isometric_force") if hasattr(parent, "find") else None
            if n and e is not None and e.text and e.text.strip():
                mif[n] = float(e.text)
        return rad, pts, mif

    r0, p0, f0 = read(model)
    r1, p1, f1 = read(against)
    tol = float(tol)

    wrap_diff = {k: {"a": r0[k], "b": r1[k],
                     "ratio": (r1[k][0] / r0[k][0]) if r0.get(k) and r0[k][0] else None}
                 for k in sorted(set(r0) & set(r1))
                 if any(abs(a - b) > tol for a, b in zip(r0[k], r1[k]))}
    pt_diff = 0
    if len(p0) == len(p1):
        pt_diff = sum(1 for (_, a), (_, b) in zip(p0, p1)
                      if any(abs(x - y) > tol for x, y in zip(a, b)))
    force_ratio = sorted({round(f1[k] / f0[k], 9) for k in set(f0) & set(f1) if f0[k]})

    msgs = [f"[model-edit] wraps differing: {len(wrap_diff)} of {len(set(r0) & set(r1))}",
            f"[model-edit] path points differing: {pt_diff} of {min(len(p0), len(p1))}"
            + ("" if len(p0) == len(p1) else f"  (COUNT DIFFERS: {len(p0)} vs {len(p1)})")]
    if len(force_ratio) == 1:
        msgs.append(f"[model-edit] max isometric force: uniform x{force_ratio[0]:g} "
                    f"across all {len(set(f0) & set(f1))} muscles")
    elif force_ratio:
        msgs.append(f"[model-edit] max isometric force: {len(force_ratio)} distinct "
                    f"ratios, {min(force_ratio):g}..{max(force_ratio):g}")
    for k, v in list(wrap_diff.items())[:20]:
        msgs.append(f"[model-edit]   {k:24s} {v['a'][0]:.5f} -> {v['b'][0]:.5f}"
                    + (f"  x{v['ratio']:.4f}" if v["ratio"] else ""))

    identical = not wrap_diff and pt_diff == 0 and force_ratio in ([], [1.0])
    if identical:
        msgs.append("[model-edit] the two models are numerically IDENTICAL "
                    "(any text difference is float-repr noise)")
    return OpResult(True, "diff", str(model), None,
                    data={"wraps": wrap_diff, "path_points_differing": pt_diff,
                          "force_ratios": force_ratio, "identical": identical,
                          "against": str(against)},
                    messages=msgs)


@op("inspect_change",
    verb="inspect",
    summary="Before/after moment-arm sweep with figures and a CSV",
    delegates_to="bioscout.change_moment_arms.inspection.inspect_change",
    writes_model=False,
    params=[
        Param("against", "path", required=True,
              help="The BEFORE model (this model is the after)"),
        Param("coordinates", "list[str]", required=True, choices_from="coordinates",
              help="Coordinates to sweep"),
        Param("n", "int", default=40, help="Sample points per sweep"),
        Param("full", "bool", default=True,
              help="Also run the muscle_inspect discontinuity pass"),
    ])
def inspect_change(model, out, *, against, coordinates, n=40, full=True, **_):
    from bioscout.change_moment_arms.inspection import inspect_change as _ic

    d = _ic(str(against), str(model), list(coordinates), n=int(n), full=bool(full),
            plots=True, log=lambda m: None)
    return OpResult(bool(d.get("ok")), "inspect_change", str(model), None, data=d,
                    reason=d.get("reason", ""),
                    messages=[f"[model-edit] figures: {len(d.get('figures') or [])}, "
                              f"csv: {d.get('csv') or 'none'}, "
                              f"discontinuous: {', '.join(d.get('discontinuous') or []) or 'none'}"])
