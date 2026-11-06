"""Scale tool: measurement-based segment scaling + marker placement, like OpenSim's
ScaleTool (ModelScaler + MarkerPlacer), reading the same setup_scale.xml.

The scaled model is written as an .osim by editing the generic model's XML, so
everything the tool does not touch stays exactly as it was.
"""
import os
import xml.etree.ElementTree as ET
import numpy as np
from .io import read_trc
from .model import Model, _path_name, _vec
from . import ik as _ik
from .io import write_mot as _wm

AX = {"X": 0, "Y": 1, "Z": 2}


def read_setup(path):
    """-> dict(measurements=[(name, [(m1, m2)], [(body, [axes])])], mass, time_range,
    preserve_mass, placer=bool, manual={body: [sx, sy, sz]}, order=[...])."""
    r = ET.parse(path).getroot()
    out = {"measurements": [], "manual": {}, "mass": None, "time_range": None,
           "preserve_mass": False, "placer": True, "order": ["measurements"]}
    m = r.find(".//mass")
    if m is not None and (m.text or "").strip():
        out["mass"] = float(m.text)
    ms = r.find(".//ModelScaler")
    if ms is not None:
        tr = ms.findtext("time_range")
        if tr and len(tr.split()) == 2:
            out["time_range"] = tuple(float(x) for x in tr.split())
        out["preserve_mass"] = (ms.findtext("preserve_mass_distribution") or "").strip() == "true"
        order = (ms.findtext("scaling_order") or "measurements").split()
        out["order"] = order
        for meas in ms.iter("Measurement"):
            if (meas.findtext("apply") or "true").strip() == "false":
                continue
            pairs = [tuple((mp.findtext("markers") or "").split()[:2]) for mp in meas.iter("MarkerPair")]
            bodies = [(b.get("name"), (b.findtext("axes") or "X Y Z").split()) for b in meas.iter("BodyScale")]
            out["measurements"].append((meas.get("name"), [p for p in pairs if len(p) == 2], bodies))
        for sc in ms.iter("Scale"):
            if (sc.findtext("apply") or "true").strip() == "false":
                continue
            out["manual"][(sc.findtext("segment") or "").strip()] = [float(x) for x in (sc.findtext("scales") or "1 1 1").split()]
    mp = r.find(".//MarkerPlacer")
    if mp is not None:
        out["placer"] = (mp.findtext("apply") or "true").strip() != "false"
    return out


def _mean_markers(trc_path, t_range):
    t, mk, _ = read_trc(trc_path)
    sel = np.ones(len(t), bool)
    if t_range:
        sel = (t >= t_range[0] - 1e-9) & (t <= t_range[1] + 1e-9)
        if not sel.any():
            sel[np.argmin(abs(t - t_range[0]))] = True
    return {n: v[sel] for n, v in mk.items()}, t[sel]


def scale_factors(model, exp, measurements, aliases=None, log=print):
    """Per-body [sx, sy, sz] from measured / model marker distances (default pose)."""
    aliases = aliases or {}
    alias = lambda n: aliases.get(n, n)
    P = model.marker_positions({})
    factors, used = {}, 0
    for name, pairs, bodies in measurements:
        ratios = []
        for a, b in pairs:
            ea, eb = exp.get(alias(a)), exp.get(alias(b))
            if a in P and b in P and ea is not None and eb is not None:
                dm = np.linalg.norm(P[a] - P[b])
                de = np.linalg.norm(np.atleast_2d(ea) - np.atleast_2d(eb), axis=1)   # per frame, as OpenSim
                if dm > 1e-9 and np.isfinite(de).any():
                    ratios.append(np.nanmean(de) / dm)
        if not ratios:
            log(f"[scale]   SKIPPED {name} (markers {','.join(sorted({x for p in pairs for x in p}))})")
            continue
        s = float(np.mean(ratios)); used += 1
        log(f"[scale]   {name}: {s:.4f}")
        for body, axes in bodies:
            f = factors.setdefault(body, [None, None, None])
            for a in axes:
                f[AX[a.upper()]] = s
    if not used:
        raise ValueError("no measurement could be made: the measurement set's markers are not in both "
                         "the model and the static .trc (check names, or give marker aliases)")
    return {b: [1.0 if v is None else v for v in f] for b, f in factors.items()}


def _scale_vec_text(el, s):
    v = _vec(el.text) * np.asarray(s)
    el.text = " ".join(f"{x:.10g}" for x in v)


def write_scaled(generic_path, out_path, factors, mass=None, preserve_mass=False,
                 markers=None, defaults=None, name=None):
    """Apply per-body scale factors to the .osim XML and write it."""
    tree = ET.parse(generic_path)
    m = tree.getroot().find("Model")
    if name:
        m.set("name", name)
    S = lambda body: np.asarray(factors.get(body, [1.0, 1.0, 1.0]))
    bodies = {b.get("name"): b for b in m.find("BodySet/objects")}
    # masses: OpenSim scales by volume unless the distribution is preserved, then fits the total
    old = {n: float(b.findtext("mass") or 0) for n, b in bodies.items()}
    new = {n: (old[n] if preserve_mass else old[n] * float(np.prod(S(n)))) for n in bodies}
    if mass:
        k = mass / max(sum(new.values()), 1e-12)
        new = {n: v * k for n, v in new.items()}
    for n, b in bodies.items():
        s = S(n)
        if b.find("mass") is not None:
            b.find("mass").text = f"{new[n]:.10g}"
        if b.find("mass_center") is not None:
            _scale_vec_text(b.find("mass_center"), s)
        I = b.find("inertia")
        if I is not None and old[n] > 0:
            v = _vec(I.text, 6); r = new[n] / old[n]
            d = [(s[1] ** 2 + s[2] ** 2) / 2, (s[0] ** 2 + s[2] ** 2) / 2, (s[0] ** 2 + s[1] ** 2) / 2]
            prod = [s[0] * s[1], s[0] * s[2], s[1] * s[2]]
            v = np.r_[v[:3] * r * np.array(d), v[3:] * r * np.array(prod)]
            I.text = " ".join(f"{x:.10g}" for x in v)
        for wrap in b.iter():
            if wrap.tag.startswith("Wrap") and wrap.tag != "WrapObjectSet" and wrap.find("translation") is not None:
                _scale_vec_text(wrap.find("translation"), s)
                for tag in ("radius", "inner_radius", "outer_radius"):
                    e = wrap.find(tag)
                    if e is not None:
                        e.text = f"{float(e.text) * float(np.mean(s)):.10g}"
                for tag in ("dimensions",):
                    e = wrap.find(tag)
                    if e is not None:
                        _scale_vec_text(e, s)
                e = wrap.find("length")
                if e is not None:
                    e.text = f"{float(e.text) * float(np.mean(s)):.10g}"
        for g in b.iter("scale_factors"):
            _scale_vec_text(g, s)
    # frames fixed to a body (joint offset frames) and every point on a body
    _up = {c: p for p in m.iter() for c in p}                    # child -> parent element

    def _owner_body(el):                                         # the <Body> a component sits in
        e = _up.get(el)
        while e is not None and e.tag != "Body":
            e = _up.get(e)
        return e.get("name") if e is not None else None

    for el in m.iter():
        parent = None
        if el.tag == "PhysicalOffsetFrame":
            sp = (el.findtext("socket_parent") or "").strip()
            # ".." = the body this frame is declared in (e.g. a body's geometry frame): scaled with it, as OpenSim does
            parent = _owner_body(el) if sp in ("..", "../") else _path_name(sp)
            tr = el.find("translation")
        elif el.tag in ("PathPoint", "ConditionalPathPoint", "Marker"):
            parent = _path_name(el.findtext("socket_parent_frame"))
            tr = el.find("location")
        else:
            continue
        if parent in bodies and tr is not None:
            _scale_vec_text(tr, S(parent))
    # translational transform axes follow the parent body's scale along their axis
    for j in m.find("JointSet/objects"):
        if j.tag != "CustomJoint":
            continue
        frames = {f.get("name"): _path_name(f.findtext("socket_parent")) for f in (j.find("frames") or [])}
        pf = _path_name(j.findtext("socket_parent_frame"))
        pbody = frames.get(pf, pf)
        if pbody not in bodies:
            continue
        for ta in j.iter("TransformAxis"):
            if not ta.get("name", "").startswith("translation"):
                continue
            ax = _vec(ta.findtext("axis")); ax = ax / (np.linalg.norm(ax) or 1)
            k = float(np.linalg.norm(S(pbody) * ax))
            for f in ta:
                if f.tag == "LinearFunction":
                    c = _vec(f.findtext("coefficients"), 2) * k
                    f.find("coefficients").text = " ".join(f"{x:.10g}" for x in c)
                elif f.tag == "Constant":
                    f.find("value").text = f"{float(f.findtext('value')) * k:.10g}"
                elif f.tag in ("SimmSpline", "NaturalCubicSpline", "GCVSpline", "PiecewiseLinearFunction"):
                    f.find("y").text = " ".join(f"{x:.10g}" for x in _vec(f.findtext("y")) * k)
                elif f.tag == "MultiplierFunction":
                    e = f.find("scale"); e.text = f"{float(e.text or 1) * k:.10g}"
    if markers:              # marker placer result: {name: (body, location)}
        ms = m.find("MarkerSet/objects")
        for mk in ms:
            if mk.get("name") in markers:
                body, loc = markers[mk.get("name")]
                mk.find("location").text = " ".join(f"{x:.10g}" for x in loc)
        have = {mk.get("name") for mk in ms}
        for n, (body, loc) in markers.items():   # extra c3d markers attached by the placer
            if n in have:
                continue
            e = ET.SubElement(ms, "Marker", name=n)
            ET.SubElement(e, "socket_parent_frame").text = f"/bodyset/{body}"
            ET.SubElement(e, "location").text = " ".join(f"{x:.10g}" for x in loc)
            ET.SubElement(e, "fixed").text = "false"
    if defaults:             # static pose becomes the model's default pose
        for c in m.iter("Coordinate"):
            if c.get("name") in defaults and c.find("default_value") is not None:
                c.find("default_value").text = f"{defaults[c.get('name')]:.10g}"
    tree.write(out_path, encoding="UTF-8", xml_declaration=True)
    return out_path


def _attach_extra(model, T, exp, max_d=0.2):
    """Every static-trial marker the model lacks -> {name: (nearest body, local location)}.
    A body is the segment from its origin to each child's origin (or to its centre of mass
    for an end body); the marker goes on the body whose segment is closest, if within max_d."""
    segs = []
    kids = {}
    for j in model.joints:
        kids.setdefault(model._body_of(j.parent), []).append(model._body_of(j.child))
    for b in model.bodies:
        if b not in T:
            continue
        R, p = T[b]
        ends = [T[c][1] for c in kids.get(b, []) if c in T]
        if not ends:
            ends = [p + R @ (2 * np.asarray(model.bodies[b].get("com", np.zeros(3))))]
        segs += [(b, p, e) for e in ends]
    out = {}
    for n, x in exp.items():
        if n in model.markers or not np.isfinite(x).all():
            continue
        best = None
        for b, a, e in segs:
            d = e - a; L = float(d @ d)
            u = 0.0 if L < 1e-12 else min(1.0, max(0.0, float((x - a) @ d) / L))
            dist = float(np.linalg.norm(x - (a + u * d)))
            if best is None or dist < best[0]:
                best = (dist, b)
        if best and best[0] <= max_d:
            R, p = T[best[1]]
            out[n] = (best[1], R.T @ (x - p))
    return out


def _scale_muscle_lengths(generic_path, scaled_path, log=print):
    """As OpenSim's Muscle::postScale: optimal fibre length and tendon slack length scale with
    the musculotendon length change in the default pose (generic -> scaled)."""
    from .muscles import Paths
    def lengths(path):
        m = Model(path)
        q = m.full_q({})
        P = Paths(m, path)
        return dict(zip(P.names, P.lengths(np.array([[q[n] for n in m.coord_order]]))[0]))
    lg, ls = lengths(generic_path), lengths(scaled_path)
    tree = ET.parse(scaled_path)
    n = 0
    for el in tree.getroot().iter():
        name = el.get("name")
        if name in lg and name in ls and lg[name] > 0 and el.find("optimal_fiber_length") is not None:
            r = ls[name] / lg[name]
            for tag in ("optimal_fiber_length", "tendon_slack_length"):
                t = el.find(tag)
                if t is not None and (t.text or "").strip():
                    t.text = f" {float(t.text) * r:.12g}"
            n += 1
    tree.write(scaled_path, encoding="UTF-8", xml_declaration=True)
    log(f"[scale] optimal fibre + tendon slack lengths of {n} muscles scaled with their path length")


def run(generic_path, static_trc, out_osim, setup_path=None, mass=None, markerset=None,
        aliases=None, t_range=None, placer=None, log=print, out_dir=None, all_markers=True,
        placer_exclude=None):
    """placer_exclude: marker names left out of the marker-placement IK (e.g. joint centres
    estimated by regression, which should drive scaling but not the static pose)."""
    cfg = read_setup(setup_path) if setup_path else {"measurements": [], "manual": {}, "mass": None,
                                                     "time_range": None, "preserve_mass": False, "placer": True}
    mass = mass or cfg["mass"]
    t_range = t_range or cfg["time_range"]
    placer = cfg["placer"] if placer is None else placer
    model = Model(generic_path)
    if markerset:
        model.load_markerset(markerset)
        if getattr(model, "dropped_markers", None):
            d, b = model.dropped_markers
            log(f"[scale] {len(d)} marker(s) of the marker set left out, on bodies the model does not have ({', '.join(b)}): {' '.join(d)}")
    frames, ts = _mean_markers(static_trc, t_range)
    exp = {n: np.nanmean(v, axis=0) for n, v in frames.items()}
    log(f"[scale] static trial: {len(ts)} frames averaged ({ts[0]:.3f}-{ts[-1]:.3f} s), {len(exp)} markers")
    factors = scale_factors(model, frames, cfg["measurements"], aliases, log)
    for b, s in cfg["manual"].items():
        factors.setdefault(b, s)
    work = out_osim + ".tmp.osim"
    # put the (possibly new) marker set into the model before scaling so markers scale with bodies
    tmp_generic = generic_path
    if markerset:
        tree = ET.parse(generic_path); mm = tree.getroot().find("Model")
        new = ET.parse(markerset).getroot().find(".//MarkerSet")
        old = mm.find("MarkerSet")
        if old is not None:
            mm.insert(list(mm).index(old), new); mm.remove(old)
        else:
            mm.append(new)
        tmp_generic = out_osim + ".markers.osim"
        tree.write(tmp_generic, encoding="UTF-8", xml_declaration=True)
    write_scaled(tmp_generic, work, factors, mass, cfg["preserve_mass"])
    log(f"[scale] scaled {len(factors)} bodies" + (f", mass {mass:g} kg" if mass else ""))
    _scale_muscle_lengths(tmp_generic, work, log)
    placed, defaults = None, None
    if placer:
        sm = Model(work)
        skip = {str(n).upper() for n in (placer_exclude or ())}
        names = [n for n in sm.markers if n in exp and np.isfinite(exp[n]).all() and n.upper() not in skip]
        if skip:
            log(f"[scale] marker placer: {len([n for n in sm.markers if n.upper() in skip])} marker(s) left out of the static-pose IK")
        # IK on every static frame, then the mean pose (bioscout's marker registration does the same;
        # one IK on the averaged markers lands ~0.2-0.5 mm away from it)
        mk = {n: frames[n] for n in names}
        _, qs, errs, used, _per = _ik.solve(sm, np.asarray(ts, float), mk, {n: 1.0 for n in names}, log=lambda *a: None)
        q = {k: float(np.mean([qq[k] for qq in qs])) for k in qs[0]}
        T = sm.body_transforms(q)
        placed = {}
        for n in used:
            b, _loc = sm.markers[n]
            R, p = T[b]
            placed[n] = (b, R.T @ (exp[n] - p))
        if all_markers:
            extra = _attach_extra(sm, T, exp)
            if extra:
                placed.update(extra)
                log(f"[scale] {len(extra)} static-trial markers not in the marker set attached to the nearest body: "
                    + " ".join(f"{n}({b})" for n, (b, _) in sorted(extra.items())))
        defaults = {n: v for n, v in q.items()}
        _wm(os.path.join(os.path.dirname(os.path.abspath(out_osim)), "static_pose.mot"),
                      ["time"] + sm.coord_order,
                      np.array([[0.0] + [q[n] if sm.coords[n].translational else np.degrees(q[n]) for n in sm.coord_order]]))
        log(f"[scale] marker placer: {len(placed)} markers moved onto the static trial "
            f"(RMS before {errs[0, 0] * 1000:.1f} mm)")
    write_scaled(work, out_osim, {}, None, True, placed, None)   # OpenSim keeps the default pose
    with open(os.path.splitext(out_osim)[0] + "_scale_factors.xml", "w", newline="\n") as f:
        f.write('<?xml version="1.0" encoding="UTF-8" ?>\n<OpenSimDocument Version="40000">\n\t<ScaleSet name="scale_factors">\n\t\t<objects>\n')
        for b, v in sorted(factors.items()):
            f.write(f"\t\t\t<Scale>\n\t\t\t\t<scales> {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}</scales>\n\t\t\t\t<segment>{b}</segment>\n\t\t\t\t<apply>true</apply>\n\t\t\t</Scale>\n")
        f.write("\t\t</objects>\n\t</ScaleSet>\n</OpenSimDocument>\n")
    for f in (work, out_osim + ".markers.osim"):
        if os.path.exists(f):
            os.remove(f)
    return out_osim, factors
