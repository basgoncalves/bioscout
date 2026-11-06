"""OpenSim-API helpers (port of the torsion-correction helpers in MRI2MSK.m).

Requires the ``opensim`` Python bindings (4.4+ recommended, e.g.
``conda install -c opensim-org opensim``).
"""
from __future__ import annotations

import numpy as np
import opensim as osim

from .geometry import apply_transform, calc_angle_2d, rotation_xyz_body, xyz_body_from_matrix


# --------------------------------------------------------------------------- conversions
def vec3_to_np(v) -> np.ndarray:
    return np.array([v.get(0), v.get(1), v.get(2)], dtype=float)


def np_to_vec3(a) -> "osim.Vec3":
    a = np.asarray(a, float).reshape(3)
    return osim.Vec3(float(a[0]), float(a[1]), float(a[2]))


# --------------------------------------------------------------------------- lookups
def get_offset_frame(joint, frame_name: str):
    """Return the joint's PhysicalOffsetFrame called ``frame_name``."""
    for i in range(2):
        f = joint.get_frames(i)
        if f.getName() == frame_name:
            return f
    raise KeyError(f"Frame not found: {frame_name}")


def iter_meshes(body):
    """Yield every Mesh attached directly to ``body``."""
    prop = body.getPropertyByName("attached_geometry")
    for j in range(prop.size()):
        mesh = osim.Mesh.safeDownCast(prop.getValueAsObject(j))
        if mesh is not None:
            yield mesh


def _abs(f) -> str:
    """Absolute path: OpenSim resolves relative mesh paths from the model's folder, not the cwd."""
    from pathlib import Path
    return str(Path(f).resolve())


def set_body_mesh_file(model, body_name: str, geom_filter: str, mesh_file: str) -> None:
    body = model.getBodySet().get(body_name)
    for mesh in iter_meshes(body):
        if geom_filter in mesh.get_mesh_file():
            mesh.set_mesh_file(_abs(mesh_file))


def set_condyle_mesh_file(model, side: str, mesh_file: str) -> None:
    body = model.getBodySet().get(f"femoral_cond_{side}")
    frame = osim.PhysicalOffsetFrame.safeDownCast(body.getComponent(f"femoral_cond_{side}_geom_frame_1"))
    mesh = osim.Mesh.safeDownCast(frame.getComponent(f"femoral_cond_{side}_geom_1"))
    mesh.set_mesh_file(_abs(mesh_file))


def set_tibial_plateau_mesh_file(model, side: str, mesh_file: str) -> None:
    body = model.getBodySet().get(f"tibial_plat_{side}")
    frame = osim.PhysicalOffsetFrame.safeDownCast(body.getComponent(f"tibial_plat_{side}_geom_frame_1"))
    mesh = osim.Mesh.safeDownCast(frame.getComponent(f"tibial_plat_{side}_geom_1"))
    mesh.set_mesh_file(_abs(mesh_file))


# --------------------------------------------------------------------------- transforms
def transform_markers(model, frame_name, R, pivot, restore_translation) -> None:
    ms = model.getMarkerSet()
    for i in range(ms.getSize()):
        marker = ms.get(i)
        if marker.getParentFrame().getName() == frame_name:
            v = vec3_to_np(marker.get_location())
            marker.set_location(np_to_vec3(apply_transform(v, R, pivot, restore_translation)))


def transform_path_points(model, state, frame_name, R, pivot, restore_translation) -> None:
    """Rotate fixed PathPoints of all muscles attached to ``frame_name``.

    Points that don't down-cast to PathPoint (e.g. MovingPathPoint) are skipped,
    as in the MATLAB version.
    """
    muscles = model.getMuscles()
    for m in range(muscles.getSize()):
        pps = muscles.get(m).getGeometryPath().getPathPointSet()
        for p in range(pps.getSize()):
            point = pps.get(p)
            if point.getParentFrame().getName() != frame_name:
                continue
            pp = osim.PathPoint.safeDownCast(point)
            if pp is None:
                continue
            v = vec3_to_np(pp.getLocation(state))
            pp.setLocation(np_to_vec3(apply_transform(v, R, pivot, restore_translation)))


def transform_wrap_objects(body, R, pivot) -> None:
    ws = body.getWrapObjectSet()
    for i in range(ws.getSize()):
        wo = ws.get(i)
        p = vec3_to_np(wo.get_translation())
        wo.set_translation(np_to_vec3(apply_transform(p, R, pivot, True)))
        rx, ry, rz = vec3_to_np(wo.get_xyz_body_rotation())
        R_new = R @ rotation_xyz_body(rx, ry, rz)
        wo.set_xyz_body_rotation(np_to_vec3(xyz_body_from_matrix(R_new)))


def fix_femoral_condyles(model, side: str, R, femur_translation) -> np.ndarray:
    """Re-locate femur weld + medial/lateral condyle frames after femur rotation.

    Returns the new femur weld location (used as pivot for the condyle mesh).
    """
    joint = osim.WeldJoint.safeDownCast(model.getJointSet().get(f"femur_weld_{side}"))
    of = get_offset_frame(joint, f"femur_{side}_offset")
    weld = vec3_to_np(of.get_translation()) - np.asarray(femur_translation).reshape(3)
    of.set_translation(np_to_vec3(weld))

    # medial condyle
    joint = osim.CustomJoint.safeDownCast(model.getJointSet().get(f"med_cond_joint_{side}"))
    of = get_offset_frame(joint, f"sagittal_articulation_frame_{side}_offset")
    new = R @ (vec3_to_np(of.get_translation()) - weld) + weld
    of.set_translation(np_to_vec3(new))
    joint = osim.WeldJoint.safeDownCast(model.getJointSet().get(f"med_cond_weld_{side}"))
    get_offset_frame(joint, f"med_cond_{side}_offset").set_translation(np_to_vec3(-new))

    # lateral condyle
    joint = osim.CustomJoint.safeDownCast(model.getJointSet().get(f"lat_cond_joint_{side}"))
    of = get_offset_frame(joint, f"sagittal_articulation_frame_{side}_offset")
    new = R @ (vec3_to_np(of.get_translation()) - weld) + weld
    of.set_translation(np_to_vec3(new))
    constraint = osim.WeldConstraint.safeDownCast(
        model.getConstraintSet().get(f"Lat_Cond_{side}_Constraint"))
    of = osim.PhysicalOffsetFrame.safeDownCast(constraint.getComponent(f"lat_cond_{side}_offset"))
    of.set_translation(np_to_vec3(-new))
    return weld


# --------------------------------------------------------------------------- measurements
def get_model_angles_and_offsets(model, state, side: str, knee_axis_ref):
    """Condylar, tibial-plateau and tibial-torsion angles (deg) in the transverse plane.

    Returns ``(angles, translations)`` dicts:
    ``angles = {'cond', 'tibialPlat', 'torsion'}``, ``translations = {'femur', 'tibia'}``.
    """
    side = side.lower()
    SIDE = side.upper()
    model.realizePosition(state)

    joint = osim.CustomJoint.safeDownCast(model.getJointSet().get(f"hip_{side}"))
    t_femur = vec3_to_np(get_offset_frame(joint, f"femur_{side}_offset").get_translation())
    joint = osim.WeldJoint.safeDownCast(model.getJointSet().get(f"tibial_plat_weld_{side}"))
    t_tibia = vec3_to_np(get_offset_frame(joint, f"tibia_{side}_offset").get_translation())

    bs = model.getBodySet()
    med = vec3_to_np(bs.get(f"med_cond_{side}").getPositionInGround(state))
    lat = vec3_to_np(bs.get(f"lat_cond_{side}").getPositionInGround(state))

    ms = model.getMarkerSet()
    loc = lambda name: vec3_to_np(ms.get(name).getLocationInGround(state))  # noqa: E731
    knee_lat, knee_med = loc(f"{SIDE}_TIB_PLAT"), loc(f"{SIDE}_TIB_PLAT_MED")
    ankle_lat, ankle_med = loc(f"{SIDE}_ANKLE_AXIS"), loc(f"{SIDE}_ANKLE_AXIS_MED")

    xz = [0, 2]
    cond = (med - lat)[xz]
    tib = (knee_med - knee_lat)[xz]
    ankle = (ankle_med - ankle_lat)[xz]
    angles = {
        "cond": calc_angle_2d(cond, knee_axis_ref),
        "tibialPlat": calc_angle_2d(tib, knee_axis_ref),
        "torsion": calc_angle_2d(tib, ankle),
    }
    return angles, {"femur": t_femur, "tibia": t_tibia}


def wrap_coordinate_functions_with_scale(joint, scale: float, axes=(3, 4, 5)) -> None:
    """Wrap the translational TransformAxis functions of a CustomJoint in a
    MultiplierFunction(scale) - used to scale patellofemoral / Lerner knee splines.

    OpenSim takes ownership of the functions passed to setFunction(); the Python
    proxies must give up ownership (``thisown = False``) or Python frees them a
    second time (segfault).
    """
    st = joint.upd_SpatialTransform()
    for idx in axes:
        axis = st.updTransformAxis(idx)
        inner = axis.getFunction().clone()
        mult = osim.MultiplierFunction()
        mult.setScale(scale)
        inner.thisown = False
        mult.setFunction(inner)
        mult.thisown = False
        axis.setFunction(mult)
