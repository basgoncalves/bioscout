"""bioscout.model.osim_model -- edit an .osim like an object (plain XML, no OpenSim).

    import bioscout as bs

    m = bs.model("gpkv4_scaled.osim")    # the only entry point

    # markers (the MODEL's virtual markers, in their parent frame, metres)
    rasis = m.marker("RASIS")
    rasis.location                         # array([x, y, z])
    rasis.location = rasis.location + [0, -0.02, 0]
    rasis.move([0, -20, 0], unit="mm")     # same thing
    m.move_markers(["LASIS", "RASIS"], [0, -20, 0], unit="mm")

    # any property of any named component
    ps = m.muscle("psoas_r")
    ps.max_isometric_force                 # 1234.5   (child tags read as attributes)
    ps.max_isometric_force *= 0.8
    ps.set("optimal_fiber_length", 0.11)
    ps.path_points[1].move([5, 0, 0], unit="mm")
    m.wrap("IL_at_brim_r").radius = 0.03
    m.get("hip_flexion_r").range           # coordinates, joints, bodies, ... by name

    # every bioscout.model.edit operation (wrap_add, wrap_detach, mvic, ma_target, ...)
    m.apply("wrap_add", body="pelvis", wrap_name="new_cyl_r", kind="cylinder",
            radius=0.03, length=0.1, muscles=["psoas_r"])

    m.changes                              # what was edited, in order
    m.save("gpkv4_scaled_edited.osim")     # never over the input unless overwrite=True

Locations are in the component's PARENT frame (``m.marker("RASIS").parent_frame``),
which is what the .osim stores; ``move`` adds the offset in that same frame.
Elements under ``<defaults>`` (templates) are never returned.
"""
from __future__ import annotations

import copy
import difflib
import fnmatch
import os
import shutil
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Union

import numpy as np

_UNITS = {"m": 1.0, "cm": 0.01, "mm": 0.001}
_MUSCLE_TAGS = ("Muscle",)                       # *Muscle tags: Millard2012..., Thelen2003..., DeGroote...
_WRAP_TAGS = ("WrapCylinder", "WrapSphere", "WrapEllipsoid", "WrapTorus", "WrapCylinderObst")
_POINT_TAGS = ("PathPoint", "ConditionalPathPoint", "MovingPathPoint")


# ------------------------------------------------------------------ values
def _parse(text: Optional[str]):
    """'1 2 3' -> array, '0.5' -> float, 'true' -> True, else the string."""
    if text is None:
        return None
    s = text.strip()
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    parts = s.split()
    try:
        vals = [float(p) for p in parts]
    except ValueError:
        return s
    if len(vals) == 1:
        return vals[0]
    return np.array(vals)


def _fmt(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, np.floating, np.integer)):
        return repr(float(value))                      # shortest exact round-trip
    if isinstance(value, (list, tuple, np.ndarray)):
        return " ".join(repr(float(v)) for v in np.ravel(value))
    return str(value)


def _vec(offset, unit) -> np.ndarray:
    if unit not in _UNITS:
        raise ValueError(f"unit must be one of {list(_UNITS)}, not {unit!r}")
    v = np.asarray(offset, float).reshape(-1)
    if v.size != 3:
        raise ValueError(f"offset needs 3 values (x, y, z), got {v.size}")
    return v * _UNITS[unit]


# --------------------------------------------------------------- components
class Component:
    """One named element of the model. Child tags read/write as attributes:
    ``c.max_isometric_force``, ``c.max_isometric_force = 900``; or use
    ``get(prop)`` / ``set(prop, value)``. Values are float, numpy array, bool or str."""

    def __init__(self, model: "Model", el: ET.Element):
        object.__setattr__(self, "_model", model)
        object.__setattr__(self, "_el", el)

    # identity
    @property
    def name(self) -> str:
        return self._el.get("name", "")

    @property
    def kind(self) -> str:
        """The OpenSim class (XML tag), e.g. 'Marker', 'Millard2012EquilibriumMuscle'."""
        return self._el.tag

    @property
    def element(self) -> ET.Element:
        return self._el

    def __repr__(self):
        return f"<{self.kind} {self.name!r}>"

    # properties
    def props(self) -> dict:
        """Every simple (leaf) child property and its value."""
        return {c.tag: _parse(c.text) for c in self._el if len(c) == 0}

    def _child(self, prop: str) -> ET.Element:
        c = self._el.find(prop)
        if c is None:
            near = difflib.get_close_matches(prop, [x.tag for x in self._el], n=3)
            raise AttributeError(f"{self!r} has no property {prop!r}"
                                 + (f" (did you mean {', '.join(near)}?)" if near else ""))
        return c

    def get(self, prop: str):
        return _parse(self._child(prop).text)

    def set(self, prop: str, value) -> "Component":
        c = self._child(prop)
        old = c.text
        c.text = _fmt(value)
        self._model._log(self, prop, old, c.text)
        return self

    def __getattr__(self, prop):
        if prop.startswith("_"):
            raise AttributeError(prop)
        return self.get(prop)

    def __setattr__(self, prop, value):
        cls_attr = getattr(type(self), prop, None)
        if isinstance(cls_attr, property):
            if cls_attr.fset is None:
                raise AttributeError(f"{prop} is read-only")
            cls_attr.fset(self, value)
        else:
            self.set(prop, value)


class Point(Component):
    """Anything with a <location> in a parent frame: markers, path points."""

    @property
    def location(self) -> np.ndarray:
        return np.asarray(self.get("location"), float)

    @location.setter
    def location(self, xyz):
        self.set("location", np.asarray(xyz, float).reshape(3))

    @property
    def parent_frame(self) -> str:
        for tag in ("socket_parent_frame", "parent_frame", "body"):   # 4.x, 4.0 path points, 3.x
            c = self._el.find(tag)
            if c is not None and c.text:
                return c.text.strip()
        return ""

    def move(self, offset: Sequence[float], unit: str = "m") -> "Point":
        """Add ``offset`` (x, y, z) in the parent frame."""
        self.location = self.location + _vec(offset, unit)
        return self


class Marker(Point):
    pass


class Wrap(Component):
    @property
    def translation(self) -> np.ndarray:
        return np.asarray(self.get("translation"), float)

    @translation.setter
    def translation(self, xyz):
        self.set("translation", np.asarray(xyz, float).reshape(3))

    def move(self, offset: Sequence[float], unit: str = "m") -> "Wrap":
        self.translation = self.translation + _vec(offset, unit)
        return self


class Muscle(Component):
    @property
    def path_points(self) -> List[Point]:
        gp = self._el.find("GeometryPath")
        if gp is None:
            return []
        return [Point(self._model, e) for e in gp.iter() if e.tag in _POINT_TAGS]

    @property
    def wraps(self) -> List[str]:
        """Names of the wrap objects this muscle's path uses."""
        out = []
        for pw in self._el.iter("PathWrap"):
            c = pw.find("wrap_object")
            if c is not None and c.text:
                out.append(c.text.strip())
        return out


def _wrap_class(el: ET.Element):
    t = el.tag
    if t == "Marker":
        return Marker
    if t.endswith("Muscle"):
        return Muscle
    if t in _WRAP_TAGS:
        return Wrap
    if t in _POINT_TAGS:
        return Point
    return Component


# --------------------------------------------------------------------- model
class Model:
    """An .osim held in memory as XML. See the module docstring for examples."""

    def __init__(self, path: Union[str, os.PathLike]):
        self.path = Path(path)
        self._tree = ET.parse(self.path)
        self.changes: list = []

    # ---------- lookup
    @property
    def root(self) -> ET.Element:
        return self._tree.getroot()

    def _elements(self):
        defaults = {id(e) for d in self.root.iter("defaults") for e in d.iter()}
        for e in self.root.iter():
            if e.get("name") is not None and id(e) not in defaults and e.tag != "Model":
                yield e

    @staticmethod
    def _is(e: ET.Element, kind: Optional[str]) -> bool:
        """``kind`` is a tag or tag substring; containers (``*Set``) only match by full tag."""
        if kind is None:
            return True
        if kind == e.tag:
            return True
        if kind == "Wrap":                              # wrap SURFACES, not a muscle's PathWrap
            return e.tag in _WRAP_TAGS
        return kind in e.tag and not e.tag.endswith("Set")

    def names(self, kind: Optional[str] = None) -> List[str]:
        """Names of every component (``kind``: tag or tag substring, e.g. 'Marker', 'Muscle', 'Wrap')."""
        return [e.get("name") for e in self._elements() if self._is(e, kind)]

    def find(self, pattern: str = "*", kind: Optional[str] = None) -> List[Component]:
        """Components whose name matches a glob, e.g. ``find('*ASIS')``, ``find('psoas*', 'Muscle')``."""
        return [_wrap_class(e)(self, e) for e in self._elements()
                if fnmatch.fnmatchcase(e.get("name"), pattern) and self._is(e, kind)]

    def get(self, name: str, kind: Optional[str] = None) -> Component:
        hits = [e for e in self._elements() if e.get("name") == name and self._is(e, kind)]
        if not hits:
            near = difflib.get_close_matches(name, self.names(kind), n=5)
            raise KeyError(f"no {kind or 'component'} {name!r} in {self.path.name}"
                           + (f" (did you mean {', '.join(near)}?)" if near else ""))
        if len(hits) > 1:
            kinds = sorted({e.tag for e in hits})
            raise KeyError(f"{name!r} is ambiguous ({', '.join(kinds)}); pass kind=")
        return _wrap_class(hits[0])(self, hits[0])

    __getitem__ = get

    def marker(self, name) -> Marker:
        return self.get(name, "Marker")

    def muscle(self, name) -> Muscle:
        return self.get(name, "Muscle")

    def wrap(self, name) -> Wrap:
        return self.get(name, "Wrap")

    def coordinate(self, name) -> Component:
        return self.get(name, "Coordinate")

    def body(self, name) -> Component:
        return self.get(name, "Body")

    @property
    def markers(self) -> List[Marker]:
        return self.find("*", "Marker")

    @property
    def muscles(self) -> List[Muscle]:
        return [c for c in self.find("*") if isinstance(c, Muscle)]

    # ---------- bulk edits
    def move_markers(self, names: Union[str, Iterable[str]], offset, unit: str = "m") -> List[Marker]:
        """Move several markers (names or one glob) by the same offset in their parent frames."""
        mks = self.find(names, "Marker") if isinstance(names, str) else [self.marker(n) for n in names]
        if not mks:
            raise KeyError(f"no marker matches {names!r}")
        for mk in mks:
            mk.move(offset, unit)
        return mks

    def scale(self, prop: str, factor: float, names="*", kind: Optional[str] = "Muscle") -> int:
        """Multiply ``prop`` by ``factor`` on every matching component, e.g.
        ``m.scale('max_isometric_force', 0.8, 'psoas*')``. Returns how many changed."""
        n = 0
        for c in self.find(names, kind):
            if c.element.find(prop) is not None:
                c.set(prop, c.get(prop) * factor)
                n += 1
        return n

    # ---------- the existing bioscout.model.edit operations
    def apply(self, op: str, **params):
        """Run a bioscout.model.edit operation (``bioscout model-edit list``) on the
        current in-memory state; the result is loaded back into this object.
        Returns the op's OpResult (``.ok``, ``.changed``, ``.messages``)."""
        from bioscout.model.edit import apply as _apply
        tmp = Path(tempfile.mkdtemp(prefix="bs_model_"))
        try:
            src, out = tmp / self.path.name, tmp / ("out_" + self.path.name)
            self._write(src)
            g = self.path.parent / "Geometry"                    # ops that need meshes find them
            try:                                                # (best effort: links may be unreadable,
                if g.is_dir():                                  #  and symlinks need rights on Windows)
                    os.symlink(g, tmp / "Geometry", target_is_directory=True)
            except OSError:
                pass
            res = _apply(op, src, out, overwrite=True, **params)
            if res.ok and res.model and Path(res.model).exists():
                self._tree = ET.parse(res.model)
            self.changes.append(dict(component=f"apply:{op}", prop=str(params),
                                     old=None, new="ok" if res.ok else f"FAILED: {res.reason}"))
            return res
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ---------- output
    def _log(self, comp, prop, old, new):
        self.changes.append(dict(component=f"{comp.kind}:{comp.name}", prop=prop, old=old, new=new))

    def _write(self, path: Path):
        tree = copy.deepcopy(self._tree)
        ET.indent(tree, space="\t")
        tree.write(path, encoding="UTF-8", xml_declaration=True)

    def save(self, path: Union[str, os.PathLike, None] = None, overwrite: bool = False) -> Path:
        """Write the model. Without ``path``: ``<stem>_edited.osim`` next to the input.
        Refuses to write over the input (or an existing file) unless ``overwrite=True``."""
        out = Path(path) if path else self.path.with_name(self.path.stem + "_edited.osim")
        if out.exists() and not overwrite:
            raise FileExistsError(f"{out} exists -- pass overwrite=True")
        out.parent.mkdir(parents=True, exist_ok=True)
        self._write(out)
        return out

    def summary(self) -> str:
        lines = [f"{self.path.name}: {len(self.changes)} change(s)"]
        for c in self.changes:
            lines.append(f"  {c['component']}.{c['prop']}: {c['old']} -> {c['new']}")
        return "\n".join(lines)

    def __repr__(self):
        return f"<Model {self.path.name}: {len(self.markers)} markers, {len(self.muscles)} muscles>"

