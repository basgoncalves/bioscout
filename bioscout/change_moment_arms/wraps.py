"""Read and edit wrap-surface radii — pure ``xml.etree``, no OpenSim needed.

In OpenSim a wrap surface is the geometric stand-in for muscle bulk: the path
is held off the bone by the cylinder, so the cylinder's radius sets how far the
line of action sits from the joint axis. Growing it is therefore the *mechanism*
by which a larger muscle produces a larger moment arm, not a proxy for it — which
is why this, rather than translating attachment points, is the primary edit here.

Kept free of ``opensim`` so the file surgery can be unit-tested and so a model
can be inspected on a machine without an OpenSim install.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

__all__ = ["WrapInfo", "read_wraps", "muscle_wraps", "scale_wrap_radii",
           "set_wrap_radii", "set_wrap_quadrant", "QUADRANTS"]

#: The values OpenSim accepts for a wrap object's ``quadrant``. "all" lets the
#: path wrap either side of the surface, which is the default and the usual
#: cause of a moment arm that flips sign mid-sweep.
QUADRANTS = ("all", "+x", "-x", "+y", "-y", "+z", "-z")


@dataclass
class WrapInfo:
    """One wrap surface and where it lives."""

    name: str
    body: str
    kind: str                  # WrapCylinder / WrapEllipsoid / WrapSphere ...
    radius: Optional[float]    # None for surfaces without a single radius
    muscles: List[str]

    @property
    def scalable(self) -> bool:
        """True when this surface has a single radius we can grow."""
        return self.radius is not None


def _parser() -> ET.XMLParser:
    """Keep OpenSim's property comments through a round trip."""
    return ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))


def _muscle_elements(root: ET.Element):
    """Yield every element that owns a GeometryPath (i.e. every muscle/force)."""
    for el in root.iter():
        if el.get("name") and el.find("GeometryPath") is not None:
            yield el


def muscle_wraps(root: ET.Element) -> Dict[str, List[str]]:
    """``{muscle: [wrap object names]}`` for every muscle that wraps."""
    out: Dict[str, List[str]] = {}
    for m in _muscle_elements(root):
        gp = m.find("GeometryPath")
        names = [w.findtext("wrap_object", "").strip()
                 for w in gp.iter("PathWrap")]
        names = [n for n in names if n]
        if names:
            out[m.get("name")] = names
    return out


def read_wraps(model: str | Path) -> Dict[str, WrapInfo]:
    """Every wrap surface in the model, keyed by name."""
    root = ET.parse(Path(model), parser=_parser()).getroot()
    by_muscle = muscle_wraps(root)
    users: Dict[str, List[str]] = {}
    for muscle, wnames in by_muscle.items():
        for w in wnames:
            users.setdefault(w, []).append(muscle)

    out: Dict[str, WrapInfo] = {}
    for body in root.iter("Body"):
        bname = body.get("name")
        for wo in body.iter():
            kind = wo.tag
            # comment nodes survive the round trip (see _parser) and carry a
            # callable tag, not a string — skip them before any tag matching
            if not isinstance(kind, str):
                continue
            if not kind.startswith("Wrap") or kind == "WrapObjectSet":
                continue
            name = wo.get("name")
            if not name:
                continue
            rtxt = wo.findtext("radius")
            radius = None
            if rtxt:
                try:                       # a sphere/cylinder has one radius;
                    radius = float(rtxt)   # an ellipsoid has three -> skip
                except ValueError:
                    radius = None
            out[name] = WrapInfo(name=name, body=bname, kind=kind,
                                 radius=radius, muscles=sorted(users.get(name, [])))
    return out


def set_wrap_radii(model: str | Path, out_path: str | Path,
                   radii: Dict[str, float]) -> Dict[str, tuple]:
    """Write absolute radii. Returns ``{wrap: (old, new)}`` for those changed."""
    tree = ET.parse(Path(model), parser=_parser())
    root = tree.getroot()
    changed: Dict[str, tuple] = {}
    for wo in root.iter():
        name = wo.get("name") if hasattr(wo, "get") else None
        if not name or name not in radii:
            continue
        el = wo.find("radius")
        if el is None or not el.text:
            continue
        old = float(el.text)
        new = float(radii[name])
        if new <= 0:
            raise ValueError(f"{name}: radius must be > 0, got {new}")
        el.text = repr(new)
        changed[name] = (old, new)
    missing = set(radii) - set(changed)
    if missing:
        raise KeyError(f"wrap surface(s) not found or without a radius: "
                       f"{', '.join(sorted(missing))}")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(out_path, encoding="utf-8", xml_declaration=True)
    return changed


def scale_wrap_radii(model: str | Path, out_path: str | Path,
                     factors: Dict[str, float]) -> Dict[str, tuple]:
    """Multiply radii by per-wrap factors. Returns ``{wrap: (old, new)}``."""
    current = read_wraps(model)
    radii = {}
    for name, f in factors.items():
        info = current.get(name)
        if info is None:
            raise KeyError(f"wrap surface '{name}' not in {model}")
        if not info.scalable:
            raise ValueError(f"wrap surface '{name}' ({info.kind}) has no single "
                             "radius to scale")
        radii[name] = info.radius * float(f)
    return set_wrap_radii(model, out_path, radii)


def set_wrap_quadrant(model: str | Path, out_path: str | Path,
                      quadrants: Dict[str, str]) -> Dict[str, tuple]:
    """Restrict which side of a wrap surface the path may run on.

    ``{wrap name: quadrant}`` -> ``{wrap: (old, new)}`` for those changed.

    This is a CONTINUITY edit, not a magnitude one, and it is the only op here
    that is. Every other edit in this module changes how far the path sits from
    the joint axis; this one changes *which side of the surface it is allowed
    to sit on*, and leaves the geometry untouched.

    Why that matters: a path with no via point between its origin and insertion
    can wrap either way round a surface whose ``quadrant`` is ``all``. As the
    joint moves, the shortest-path solution jumps from one side to the other and
    the moment arm steps discontinuously from +r to -r. GPK's
    ``obt_internus1_r`` does exactly this -- a two-point path over a 27.7 mm
    sphere centred on the hip joint centre, stepping -27.2 -> +27.2 mm at
    -17 deg hip adduction. Growing or shrinking the sphere cannot help; the
    step is a degeneracy in which side is chosen, not in how big the surface is.

    Note the quadrant belongs to the WRAP OBJECT, not to one muscle's PathWrap,
    so restricting it constrains every muscle that wraps on that surface. Check
    ``read_wraps(model)[name].muscles`` before using it -- a surface with one
    user is a per-muscle fix, a shared one is not.
    """
    bad = {k: v for k, v in quadrants.items() if str(v).lower() not in QUADRANTS}
    if bad:
        raise ValueError(f"quadrant must be one of {', '.join(QUADRANTS)}; "
                         f"got {bad}")
    tree = ET.parse(Path(model), parser=_parser())
    root = tree.getroot()
    changed: Dict[str, tuple] = {}
    seen: set = set()
    for wo in root.iter():
        kind = wo.tag
        if not isinstance(kind, str) or not kind.startswith("Wrap"):
            continue
        name = wo.get("name")
        if not name or name not in quadrants or name in seen:
            continue
        want = str(quadrants[name]).lower()
        el = wo.find("quadrant")
        if el is None:
            # OpenSim omits the property when it has never been set; the
            # default is "all". Add it rather than failing -- an absent
            # quadrant is precisely the case this op exists to fix.
            el = ET.SubElement(wo, "quadrant")
            old = "all"
        else:
            old = (el.text or "all").strip()
        el.text = want
        if old != want:
            changed[name] = (old, want)
        seen.add(name)
    missing = set(quadrants) - seen
    if missing:
        raise KeyError(f"wrap surface(s) not found: {', '.join(sorted(missing))}")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(out_path, encoding="utf-8", xml_declaration=True)
    return changed


def repoint_path_wrap(model: str | Path, out_path: str | Path,
                      moves: Dict[str, Dict[str, str]]) -> Dict[str, tuple]:
    """Point a muscle's PathWrap at a DIFFERENT wrap surface already in the model.

    ``{muscle: {old wrap name: new wrap name}}`` ->
    ``{f"{muscle}:{old}": (old, new)}`` for those changed.

    Neither a magnitude edit nor a quadrant one. It changes **which surface a
    muscle wraps on**, and it invents no geometry: the target must already be
    defined in the model, so the result is reproducible from published parts
    rather than tuned.

    Why it exists: GPK_v3 defines 32 wrap surfaces that no muscle uses, against
    two in each of the published models it is compared with, and 14 of those
    orphans are surfaces Catelli DOES wire up. The clearest case is
    ``BF140_at_gastroc_r`` -- Catelli's wrap built for 140 deg of knee flexion,
    present in GPK and connected to nothing, while ``bfsh_r`` runs on
    ``BF_at_gastroc_r``, which sits 19 mm further posterior and lets the path
    leave the surface as the knee closes. The deep-flexion hamstring moment arm
    reverses sign as a result. The repair is not a new radius or a moved via
    point; it is a wire that was never connected.

    Unlike ``set_wrap_quadrant`` this is PER MUSCLE: the PathWrap belongs to the
    muscle, so re-pointing one muscle leaves every other user of either surface
    untouched. That is what makes it safe on a shared surface.

    Raises if a muscle, its PathWrap, or the target surface is missing -- a
    silent no-op here would look like a repair that did nothing.
    """
    tree = ET.parse(Path(model), parser=_parser())
    root = tree.getroot()
    have = {n for n in (
        wo.get("name") for wo in root.iter()
        if isinstance(wo.tag, str) and wo.tag.startswith("Wrap")
        and wo.tag != "WrapObjectSet") if n}

    unknown = sorted({new for mv in moves.values() for new in mv.values()
                      if new not in have})
    if unknown:
        raise ValueError(f"target wrap surface(s) not defined in the model: "
                         f"{', '.join(unknown)}. This op only connects "
                         f"geometry that already exists.")

    by_name = {m.get("name"): m for m in _muscle_elements(root)}
    missing = sorted(set(moves) - set(by_name))
    if missing:
        raise ValueError(f"muscle(s) not in the model: {', '.join(missing)}")

    changed: Dict[str, tuple] = {}
    for muscle, mapping in moves.items():
        gp = by_name[muscle].find("GeometryPath")
        found = {w.findtext("wrap_object", "").strip()
                 for w in gp.iter("PathWrap")} if gp is not None else set()
        absent = sorted(set(mapping) - found)
        if absent:
            raise ValueError(f"{muscle} has no PathWrap on {', '.join(absent)}"
                             f" (it wraps on: {', '.join(sorted(found)) or 'nothing'})")
        for w in gp.iter("PathWrap"):
            el = w.find("wrap_object")
            if el is None:
                continue
            old = (el.text or "").strip()
            if old in mapping and mapping[old] != old:
                el.text = mapping[old]
                changed[f"{muscle}:{old}"] = (old, mapping[old])

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    tree.write(Path(out_path), encoding="UTF-8", xml_declaration=True)
    return changed


#: The WrapObject properties OpenSim writes, in the order it writes them. A
#: property emitted out of order still loads, but the file stops diffing cleanly
#: against its siblings, which is how a hand-made surface announces itself.
_WRAP_KINDS = {
    "cylinder": ("WrapCylinder", ("radius", "length")),
    "sphere":   ("WrapSphere",   ("radius",)),
    "ellipsoid": ("WrapEllipsoid", ("dimensions",)),
}


def add_wrap_object(model: str | Path, out_path: str | Path, *, body: str,
                    name: str, kind: str = "cylinder",
                    translation=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0),
                    quadrant: str = "all", visible: bool = True,
                    **dims) -> Dict[str, dict]:
    """Create a wrap surface on a body. Returns ``{name: {...}}``.

    The op that was missing. `ma_scale_wraps` resizes a surface, `wrap_quadrant`
    picks a side, `repoint_path_wrap` moves a muscle between surfaces -- all of
    them presuppose the surface exists. When the geometry a model needs is not
    in it at all, and no published sibling has it either, the honest move is to
    ADD one and score it as an invention.

    It does NOT connect anything: a surface with no PathWrap changes no moment
    arm. Follow with :func:`attach_path_wrap`, or the model gains an orphan --
    and GPK_v3 already carries 32 of those.

    Raises if the body is missing or the name is taken; a duplicate wrap name is
    accepted by OpenSim and then silently shadows, which is unfixable later
    because neither surface can be addressed unambiguously.
    """
    if kind not in _WRAP_KINDS:
        raise ValueError(f"kind must be one of {', '.join(_WRAP_KINDS)}")
    tag, needed = _WRAP_KINDS[kind]
    missing = [d for d in needed if d not in dims]
    if missing:
        raise ValueError(f"{tag} needs {', '.join(missing)}")

    tree = ET.parse(Path(model), parser=_parser())
    root = tree.getroot()
    if name in {w.get("name") for w in root.iter()
                if isinstance(w.tag, str) and w.tag.startswith("Wrap")}:
        raise ValueError(f"a wrap object called {name!r} already exists")

    target = next((b for b in root.iter("Body") if b.get("name") == body), None)
    if target is None:
        raise ValueError(f"no body called {body!r} in the model")

    wos = target.find("WrapObjectSet")
    if wos is None:
        wos = ET.SubElement(target, "WrapObjectSet")
        wos.set("name", "wrapobjectset")
    objs = wos.find("objects")
    if objs is None:
        objs = ET.SubElement(wos, "objects")
        ET.SubElement(wos, "groups")

    w = ET.SubElement(objs, tag)
    w.set("name", name)
    ET.SubElement(w, "active").text = "true"
    ET.SubElement(w, "xyz_body_rotation").text = " ".join(f"{v:g}" for v in rotation)
    ET.SubElement(w, "translation").text = " ".join(f"{v:g}" for v in translation)
    ET.SubElement(w, "quadrant").text = str(quadrant)
    ap = ET.SubElement(w, "Appearance")
    ET.SubElement(ap, "visible").text = "true" if visible else "false"
    ET.SubElement(ap, "opacity").text = "0.5"
    ET.SubElement(ap, "color").text = "1 0.8 0"
    for d in needed:
        v = dims[d]
        ET.SubElement(w, d).text = (" ".join(f"{x:g}" for x in v)
                                    if isinstance(v, (list, tuple)) else f"{v:g}")

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    tree.write(Path(out_path), encoding="UTF-8", xml_declaration=True)
    return {name: dict(body=body, kind=tag, translation=list(translation),
                       rotation=list(rotation), quadrant=quadrant, **dims)}


def attach_path_wrap(model: str | Path, out_path: str | Path,
                     moves: Dict[str, List[str]], method: str = "hybrid",
                     ) -> Dict[str, str]:
    """Give a muscle a PathWrap on an existing surface. ``{muscle: [wraps]}``.

    Each PathWrap is named ``pathwrap_<surface>``, not ``pathwrap``. OpenSim's
    own files name every one of them ``pathwrap``, and a second one on the same
    muscle makes the GUI warn *"subcomponents with duplicate name 'pathwrap',
    the duplicate is being renamed to 'pathwrap_0'"* -- at which point which
    wrap is which depends on file order. Naming them for their surface removes
    that whole class of ambiguity.

    ORDER MATTERS: OpenSim applies PathWraps in the order they appear, so a
    muscle wrapping two surfaces can give a different path depending on which
    is listed first. New wraps are appended, so an existing one keeps priority.
    """
    tree = ET.parse(Path(model), parser=_parser())
    root = tree.getroot()
    have = {w.get("name") for w in root.iter()
            if isinstance(w.tag, str) and w.tag.startswith("Wrap")
            and w.tag != "WrapObjectSet"}
    unknown = sorted({w for ws in moves.values() for w in ws} - have)
    if unknown:
        raise ValueError(f"wrap surface(s) not in the model: {', '.join(unknown)}. "
                         f"Create them first with add_wrap_object.")

    by_name = {m.get("name"): m for m in _muscle_elements(root)}
    missing = sorted(set(moves) - set(by_name))
    if missing:
        raise ValueError(f"muscle(s) not in the model: {', '.join(missing)}")

    added: Dict[str, str] = {}
    for muscle, wraps in moves.items():
        gp = by_name[muscle].find("GeometryPath")
        pws = gp.find("PathWrapSet")
        if pws is None:
            pws = ET.SubElement(gp, "PathWrapSet")
            pws.set("name", "pathwrapset")
        objs = pws.find("objects")
        if objs is None:
            objs = ET.SubElement(pws, "objects")
            ET.SubElement(pws, "groups")
        already = {p.findtext("wrap_object", "").strip() for p in objs.iter("PathWrap")}
        for w in wraps:
            if w in already:
                continue
            pw = ET.SubElement(objs, "PathWrap")
            pw.set("name", f"pathwrap_{w}")
            ET.SubElement(pw, "wrap_object").text = w
            ET.SubElement(pw, "method").text = method
            ET.SubElement(pw, "range").text = "-1 -1"
            added[f"{muscle}:{w}"] = w

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    tree.write(Path(out_path), encoding="UTF-8", xml_declaration=True)
    return added


def detach_path_wrap(model: str | Path, out_path: str | Path,
                     moves: Dict[str, List[str]]) -> Dict[str, str]:
    """Remove a muscle's PathWrap on a surface. The surface itself stays.

    The counterpart to :func:`attach_path_wrap`, and the honest way to ask
    "what is this wrap doing?" -- detach it, sweep, and read the difference.
    Deleting the wrap OBJECT instead would answer the question for every muscle
    on it at once.
    """
    tree = ET.parse(Path(model), parser=_parser())
    root = tree.getroot()
    by_name = {m.get("name"): m for m in _muscle_elements(root)}
    missing = sorted(set(moves) - set(by_name))
    if missing:
        raise ValueError(f"muscle(s) not in the model: {', '.join(missing)}")

    removed: Dict[str, str] = {}
    for muscle, wraps in moves.items():
        gp = by_name[muscle].find("GeometryPath")
        pws = gp.find("PathWrapSet") if gp is not None else None
        objs = pws.find("objects") if pws is not None else None
        if objs is None:
            continue
        for pw in list(objs.findall("PathWrap")):
            w = (pw.findtext("wrap_object", "") or "").strip()
            if w in wraps:
                objs.remove(pw)
                removed[f"{muscle}:{w}"] = w
    if not removed:
        raise ValueError("no matching PathWrap found — nothing was removed")

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    tree.write(Path(out_path), encoding="UTF-8", xml_declaration=True)
    return removed
