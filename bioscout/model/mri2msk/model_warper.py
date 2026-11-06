"""Python re-implementation of the OpenSim Creator Model Warper (step 5).

Reads the ``warp_setup.xml`` written by step 4 (an OSC ``ModelWarperV3Document``)
and applies its scaling steps, in document order, to the base model:

==========================================  ====================================
OSC scaling step                            what is warped
==========================================  ====================================
ThinPlateSplineMeshesScalingStep            mesh vertices -> new .obj files
ThinPlateSplineOffsetFrameTranslation...    PhysicalOffsetFrame translations
ThinPlateSplinePathPointsScalingStep        PathPoint locations
ThinPlateSplineStationsScalingStep          Station / Marker locations
ThinPlateSplineWrapCylinderScalingStep      WrapCylinder centre, axis, radius
ManuallyScaleBodySegmentsScalingStep        OpenSim body scaling (scale factors)
==========================================  ====================================

TPS details (reverse-engineered from OSC output; matches OSC to < 0.001 mm on
the MRI2MSK example participant):

* 3-D thin-plate spline with kernel U(r) = r, landmarks multiplied by the
  source/destination prescale, fitted source -> destination.
* Affine part ``f(p) = a0 + [a1 a2 a3] p``. ``apply_affine_translation`` (default
  false) toggles a0. With ``apply_affine_rotation`` false (default) the linear
  part is replaced by ``diag(|a1|, |a2|, |a3|)`` (column norms) when
  ``apply_affine_scale`` is true (default), else by identity.
  ``apply_non_affine_warp`` (default true) toggles the radial-basis part.
* ``compensate_for_frame_changes``: a point given in frame F is moved into the
  landmarks frame L with the *original* model's default pose, warped, and
  moved back into F with the pose of the model *as warped so far*.
* Wrap cylinders: centre c -> f(c); axis z' = f(c + 1 mm * z) - f(c);
  radius' = |f(c + r x) - f(c)|; x' = that vector made orthogonal to z'.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .geometry import rotation_xyz_body, xyz_body_from_matrix
from .landmarks import read_landmarks_csv

CYL_AXIS_STEP = 1e-3  # m, OSC samples the cylinder axis 1 mm from the centre


# =========================================================================== TPS
@dataclass
class TPS:
    ctrl: np.ndarray   # (n,3) source landmarks
    W: np.ndarray      # (n,3) radial weights
    A: np.ndarray      # (4,3) affine [a0; a1; a2; a3]

    @classmethod
    def fit(cls, src, dst):
        src = np.asarray(src, float)
        dst = np.asarray(dst, float)
        n = len(src)
        K = np.linalg.norm(src[:, None] - src[None], axis=-1)
        P = np.hstack([np.ones((n, 1)), src])
        L = np.zeros((n + 4, n + 4))
        L[:n, :n] = K
        L[:n, n:] = P
        L[n:, :n] = P.T
        sol = np.linalg.solve(L, np.vstack([dst, np.zeros((4, 3))]))
        return cls(src, sol[:n], sol[n:])

    def __call__(self, p, translation=False, rotation=False, scale=True, warp=True):
        p = np.atleast_2d(np.asarray(p, float))
        lin = self.A[1:].T.copy()          # columns = coefficients of x, y, z
        if not rotation:
            lin = np.diag(np.linalg.norm(lin, axis=0)) if scale else np.eye(3)
        elif not scale:
            lin = lin / np.linalg.norm(lin, axis=0)
        out = p @ lin.T
        if translation:
            out = out + self.A[0]
        if warp:
            # chunk to bound memory on big meshes
            for i in range(0, len(p), 20000):
                q = p[i:i + 20000]
                out[i:i + 20000] += np.linalg.norm(q[:, None] - self.ctrl[None], axis=-1) @ self.W
        return out


# =========================================================================== mesh I/O
def _vtp_array(da) -> np.ndarray:
    fmt = da.get("format", "ascii")
    typ = {"Float32": "<f4", "Float64": "<f8", "Int32": "<i4", "Int64": "<i8",
           "UInt32": "<u4", "UInt64": "<u8"}[da.get("type")]
    if fmt == "ascii":
        return np.array(da.text.split(), dtype=typ)
    raise NotImplementedError("binary/appended VTP not supported yet")


def read_mesh(path) -> tuple[np.ndarray, np.ndarray]:
    """Read vertices (N,3) and triangle faces (M,3, 0-based) from .vtp/.obj/.stl."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".obj":
        V, F = [], []
        for line in path.read_text().splitlines():
            if line.startswith("v "):
                V.append(line.split()[1:4])
            elif line.startswith("f "):
                idx = [int(t.split("/")[0]) - 1 for t in line.split()[1:]]
                F += [[idx[0], idx[k], idx[k + 1]] for k in range(1, len(idx) - 1)]
        return np.array(V, float), np.array(F, np.int64).reshape(-1, 3)
    if ext == ".stl":
        from .geometry import load_stl
        V, F = load_stl(path)
        # STL stores 3 vertices per face: weld identical ones (first-occurrence order)
        uniq, first, inv = np.unique(V, axis=0, return_index=True, return_inverse=True)
        order = np.argsort(first)
        remap = np.empty(len(order), np.int64)
        remap[order] = np.arange(len(order))
        return uniq[order], remap[inv.reshape(-1)][F]
    if ext == ".vtp":
        root = ET.parse(path).getroot()
        piece = root.find(".//Piece")
        pts = _vtp_array(piece.find("Points/DataArray")).astype(float).reshape(-1, 3)
        polys = piece.find("Polys")
        conn = off = None
        for da in polys.findall("DataArray"):
            if da.get("Name") == "connectivity":
                conn = _vtp_array(da).astype(np.int64)
            elif da.get("Name") == "offsets":
                off = _vtp_array(da).astype(np.int64)
        F, start = [], 0
        for end in off:
            poly = conn[start:end]
            F += [[poly[0], poly[k], poly[k + 1]] for k in range(1, len(poly) - 1)]
            start = end
        return pts, np.array(F, np.int64).reshape(-1, 3)
    raise ValueError(f"Unsupported mesh format: {path}")


def write_obj(path, V, F) -> None:
    lines = ["# mri2msk model warper"]
    lines += [f"v {x:.9g} {y:.9g} {z:.9g}" for x, y, z in V]
    lines += [f"f {a + 1} {b + 1} {c + 1}" for a, b, c in F]
    Path(path).write_text("\n".join(lines) + "\n")


def _basename(p: str) -> str:
    return re.split(r"[\\/]", p)[-1]


# =========================================================================== setup parsing
@dataclass
class Step:
    kind: str
    name: str
    props: dict

    @property
    def enabled(self) -> bool:
        return self.props.get("enabled", "true").lower() != "false"

    def flag(self, key, default) -> bool:
        v = self.props.get(key)
        return default if v is None else v.lower() == "true"

    def targets(self, key) -> list[str]:
        return self.props.get(key, "").split()


def read_warp_setup(path) -> list[Step]:
    root = ET.parse(path).getroot()
    comps = root.find(".//components")
    steps = []
    for c in comps:
        props = {ch.tag: (ch.text or "").strip() for ch in c}
        steps.append(Step(c.tag, c.get("name", ""), props))
    return steps


# =========================================================================== warper
class ModelWarper:
    def __init__(self, model_file, setup_file, out_model_file, geometry_dir, log=print):
        import opensim as osim
        self.osim = osim
        self.log = log
        self.model_file = Path(model_file)
        self.setup_file = Path(setup_file)
        self.out_model = Path(out_model_file)
        self.geom_dir = Path(geometry_dir)
        self.geom_dir.mkdir(parents=True, exist_ok=True)
        self.base = osim.Model(str(self.model_file))
        self.base_state = self.base.initSystem()
        self.model = osim.Model(str(self.model_file))
        self.state = self.model.initSystem()
        self._tps_cache: dict = {}

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _v(vec) -> np.ndarray:
        return np.array([vec.get(0), vec.get(1), vec.get(2)], float)

    def _vec3(self, a):
        return self.osim.Vec3(float(a[0]), float(a[1]), float(a[2]))

    def _reinit(self):
        self.model.finalizeConnections()
        self.state = self.model.initSystem()

    def _transform(self, model, state, frm_from: str, frm_to: str):
        """(R, p) with x_to = R x_from + p, default pose."""
        osim = self.osim
        A = osim.Frame.safeDownCast(model.getComponent(frm_from))
        B = osim.Frame.safeDownCast(model.getComponent(frm_to))
        X = A.findTransformBetween(state, B)
        R = np.array([[X.R().get(i, j) for j in range(3)] for i in range(3)])
        return R, self._v(X.p())

    def _resolve(self, p: str) -> Path:
        """Landmark CSV path: as given, relative, or by file name next to the setup."""
        s = self.setup_file.parent
        q = Path(p)
        if q.is_file():
            return q
        base = _basename(p)
        for cand in (s / p, self.model_file.parent / p, s / "landmarks" / base, s / base):
            if cand.is_file():
                return cand
        raise FileNotFoundError(p)

    def _tps(self, step: Step) -> TPS:
        key = (step.props.get("source_landmarks_file"), step.props.get("destination_landmarks_file"),
               step.props.get("source_landmarks_prescale", "1"), step.props.get("destination_landmarks_prescale", "1"))
        if key not in self._tps_cache:
            _, s = read_landmarks_csv(self._resolve(key[0]))
            _, d = read_landmarks_csv(self._resolve(key[1]))
            self._tps_cache[key] = TPS.fit(s * float(key[2] or 1), d * float(key[3] or 1))
        return self._tps_cache[key]

    def _warp_points(self, step: Step, pts: np.ndarray, frame: str) -> np.ndarray:
        """Warp points expressed in ``frame`` according to the step's flags."""
        tps = self._tps(step)
        flags = dict(translation=step.flag("apply_affine_translation", False),
                     rotation=step.flag("apply_affine_rotation", False),
                     scale=step.flag("apply_affine_scale", True),
                     warp=step.flag("apply_non_affine_warp", True))
        L = step.props.get("landmarks_frame", "")
        if frame and L and frame != L:
            # into the landmarks frame with the unwarped pose ...
            Rb, pb = self._transform(self.base, self.base_state, frame, L)
            q = tps(pts @ Rb.T + pb, **flags)
            # ... and back with the warped-so-far pose (compensate) or the unwarped one
            if step.flag("compensate_for_frame_changes", False):
                Rb, pb = self._transform(self.model, self.state, frame, L)
            return (q - pb) @ Rb          # = R^T (q - p)
        return tps(pts, **flags)

    # ------------------------------------------------------------------ step types
    def _meshes(self, step: Step):
        osim = self.osim
        for path in step.targets("meshes"):
            mesh = osim.Mesh.safeDownCast(self.model.updComponent(path))
            src_name = mesh.get_mesh_file()
            src = self._find_mesh_file(src_name)
            V, F = read_mesh(src)
            sf = self._v(mesh.get_scale_factors())
            V = V * sf
            frame = mesh.getFrame().getAbsolutePathString()
            Vw = self._warp_points(step, V, frame)
            out = self.geom_dir / (Path(_basename(src_name)).stem + ".obj")
            write_obj(out, Vw, F)
            mesh.set_mesh_file(str(out.resolve()))
            mesh.set_scale_factors(osim.Vec3(1, 1, 1))

    def _find_mesh_file(self, name: str) -> Path:
        p = Path(name)
        if p.is_file():
            return p
        md = self.model_file.parent
        base = _basename(name)
        for cand in (md / name, md / "Geometry" / base, md / base):
            if cand.is_file():
                return cand
        hits = sorted(md.rglob(base))
        if hits:
            return hits[0]
        raise FileNotFoundError(f"Mesh file not found: {name}")

    def _offset_frames(self, step: Step):
        osim = self.osim
        comp = step.flag("compensate_for_frame_changes", False)
        for path in step.targets("offset_frames"):
            of = osim.PhysicalOffsetFrame.safeDownCast(self.model.updComponent(path))
            frame = of.getParentFrame().getAbsolutePathString()
            q = self._warp_points(step, self._v(of.get_translation())[None], frame)[0]
            of.set_translation(self._vec3(q))
            if comp:
                self._reinit()

    def _path_points(self, step: Step):
        osim = self.osim
        for path in step.targets("path_points"):
            pp = osim.PathPoint.safeDownCast(self.model.updComponent(path))
            if pp is None:
                self.log(f"  (skipped, not a PathPoint: {path})")
                continue
            frame = pp.getParentFrame().getAbsolutePathString()
            q = self._warp_points(step, self._v(pp.get_location())[None], frame)[0]
            pp.set_location(self._vec3(q))

    def _stations(self, step: Step):
        osim = self.osim
        for path in step.targets("stations"):
            st = osim.Station.safeDownCast(self.model.updComponent(path))
            frame = st.getParentFrame().getAbsolutePathString()
            q = self._warp_points(step, self._v(st.get_location())[None], frame)[0]
            st.set_location(self._vec3(q))

    def _wrap_cylinders(self, step: Step):
        osim = self.osim
        for path in step.targets("wrap_cylinders"):
            wc = osim.WrapCylinder.safeDownCast(self.model.updComponent(path))
            frame = wc.getFrame().getAbsolutePathString()
            c = self._v(wc.get_translation())
            R = rotation_xyz_body(*self._v(wc.get_xyz_body_rotation()))
            r = wc.get_radius()
            pts = np.vstack([c, c + R[:, 2] * CYL_AXIS_STEP, c + R[:, 0] * r])
            fc, fz, fx = self._warp_points(step, pts, frame)
            z = (fz - fc) / np.linalg.norm(fz - fc)
            vx = fx - fc
            radius = np.linalg.norm(vx)
            x = vx - (vx @ z) * z
            x /= np.linalg.norm(x)
            y = np.cross(z, x)
            wc.set_translation(self._vec3(fc))
            wc.set_xyz_body_rotation(self._vec3(xyz_body_from_matrix(np.column_stack([x, y, z]))))
            wc.set_radius(float(radius))

    def _manual_scale(self, step: Step):
        """OpenSim body scaling for the listed bodies (not validated against OSC)."""
        osim = self.osim
        sf = [float(x) for x in step.props.get("scale_factors", "1 1 1").split()]
        ss = osim.ScaleSet()
        for b in step.targets("bodies"):
            sc = osim.Scale()
            sc.setSegmentName(b.split("/")[-1])
            sc.setScaleFactors(self._vec3(sf))
            sc.setApply(True)
            ss.cloneAndAppend(sc)
        self.model.scale(self.state, ss, True, -1.0)
        self._reinit()

    # ------------------------------------------------------------------ run
    def run(self) -> Path:
        handlers = {
            "ThinPlateSplineMeshesScalingStep": self._meshes,
            "ThinPlateSplineOffsetFrameTranslationScalingStep": self._offset_frames,
            "ThinPlateSplinePathPointsScalingStep": self._path_points,
            "ThinPlateSplineStationsScalingStep": self._stations,
            "ThinPlateSplineWrapCylinderScalingStep": self._wrap_cylinders,
            "ManuallyScaleBodySegmentsScalingStep": self._manual_scale,
        }
        for i, step in enumerate(read_warp_setup(self.setup_file), 1):
            label = step.props.get("label") or step.name
            if not step.enabled:
                self.log(f"[warp] {i:2d} {label}: disabled")
                continue
            h = handlers.get(step.kind)
            if h is None:
                self.log(f"[warp] {i:2d} {label}: unsupported step type {step.kind} - skipped")
                continue
            h(step)
            if step.flag("compensate_for_frame_changes", False) and step.kind != \
                    "ThinPlateSplineOffsetFrameTranslationScalingStep":
                self._reinit()
            elif step.kind == "ThinPlateSplineOffsetFrameTranslationScalingStep":
                self._reinit()
            self.log(f"[warp] {i:2d} {label}: done")
        self.model.finalizeConnections()
        self.out_model.parent.mkdir(parents=True, exist_ok=True)
        self.model.printToXML(str(self.out_model))
        return self.out_model


def warp_model(model_file, setup_file, out_model_file, geometry_dir, log=print) -> Path:
    return ModelWarper(model_file, setup_file, out_model_file, geometry_dir, log).run()
