"""Dimensional scaling and mass — the two halves of "make it this subject".

They are separate ops because they come apart in practice. An MRI/TPS model has
personalised geometry, so ``linear_scaling`` is off and ScaleTool's ModelScaler
never runs -- which also means nothing ever applies the subject's mass and the
model quietly keeps the generic's 75.34 kg while every joint contact force is
normalised by the real body mass. ``set_mass`` is the op that fixes that without
touching a single segment length.
"""
from __future__ import annotations

import os
from pathlib import Path

from ..spec import OpResult, Param, op

__all__ = []


@op("scale",
    verb="scale",
    summary="Linear-scale a generic model onto a static trial (ScaleTool)",
    delegates_to="bioscout.utils.openSim.scale_model",
    suffix="_scaled",
    notes=("Verifies afterwards that the femur and shank lengths actually "
           "CHANGED. OpenSim's ModelScaler cannot compute a measurement whose "
           "markers are missing and falls back to a scale factor of 1.0 "
           "silently, so a 'scaled' model can be generic geometry carrying only "
           "the subject's mass and nothing in the log says so."),
    params=[
        Param("static_trc", "path", required=True,
              help="Static trial marker file (marker_experimental.trc)"),
        Param("mass", "float", default=None, unit="kg",
              help="Subject mass. Measure it from the static GRF where you can."),
        Param("marker_set", "path", default=None,
              help="Marker set XML (setupFiles/markers_powerlifter.xml)"),
        Param("linear_scaling", "bool", default=True,
              help="Scale segment dimensions. OFF for MRI/TPS models."),
        Param("marker_placer", "bool", default=True,
              help="Register markers to the static pose by standalone IK"),
        Param("time_range", "list[float]", default=None, unit="s",
              help="Window of the static trial to average, as two numbers"),
        Param("setup_dir", "path", default=None,
              help="Where scale_setup.xml / scale_factors.xml go (default: beside out)"),
    ])
def scale(model, out, *, static_trc, mass=None, marker_set=None,
          linear_scaling=True, marker_placer=True, time_range=None,
          setup_dir=None, **_):
    from bioscout.utils import get_openSim
    _os = get_openSim()

    if not os.path.exists(static_trc):
        return OpResult(False, "scale", str(model),
                        reason=f"static trial not found: {static_trc}")
    setup_dir = str(setup_dir or Path(out).parent)

    _os.scale_model(str(model), str(static_trc), str(out),
                    scale_setup_output_dir=setup_dir,
                    mass=mass,
                    time_range=list(time_range) if time_range else None,
                    marker_set_file=str(marker_set) if marker_set else None,
                    linear_scaling=bool(linear_scaling),
                    marker_placer=bool(marker_placer))

    if not os.path.exists(out):
        return OpResult(False, "scale", str(model),
                        reason="ScaleTool produced no model")

    # The check that would have caught the 2026-07 silent-failure: a scaled
    # model whose segment lengths equal the generic's has not been scaled.
    messages, changed = [], {}
    try:
        from bioscout.utils.scale_measurements import verify_scaled
        did_change, lines = verify_scaled(str(model), str(out), verbose=False)
        messages.extend(f"[model-edit] {ln}" for ln in lines)
        changed["geometry_changed"] = bool(did_change)
        if linear_scaling and not did_change:
            return OpResult(
                False, "scale", str(model), str(out), changed=changed,
                messages=messages,
                reason=("linear_scaling was requested but NO body changed size — "
                        "the model is generic geometry with the subject's mass. "
                        "The MeasurementSet almost certainly names markers that "
                        "do not exist in the marker set or the TRC."))
    except Exception as e:                                   # noqa: BLE001
        messages.append(f"[model-edit] could not verify scaling: {e}")

    changed["mass_kg"] = mass
    return OpResult(True, "scale", str(model), str(out),
                    changed=changed, messages=messages)


@op("set_mass",
    verb="mass",
    summary="Rescale every body's mass and inertia to a total, geometry untouched",
    delegates_to="bioscout.utils.scale_measurements.set_total_mass",
    suffix="_m{mass:.1f}kg",
    notes=("The op for MRI/TPS models, which carry the generic's mass because "
           "linear_scaling is off. Segment lengths, markers and muscle paths are "
           "untouched — one uniform factor on mass and inertia."),
    params=[
        Param("mass", "float", required=True, unit="kg",
              help="Target total model mass"),
    ])
def set_mass(model, out, *, mass, **_):
    import shutil

    from bioscout.utils.scale_measurements import set_total_mass

    # set_total_mass defaults to writing in place; copy first so the source
    # survives and the facade's out-path contract holds.
    shutil.copy2(str(model), str(out))
    written = set_total_mass(str(out), float(mass), out_path=str(out), verbose=False)
    if not written or not os.path.exists(out):
        return OpResult(False, "set_mass", str(model),
                        reason="no model written (target mass 0, or model has no mass)")
    return OpResult(True, "set_mass", str(model), str(out),
                    changed={"total_mass_kg": float(mass)},
                    messages=[f"[model-edit] total mass set to {float(mass):.2f} kg "
                              f"(geometry untouched)"])


@op("mass_from_static_grf",
    verb="mass",
    summary="Read the subject's mass off the static trial's ground reaction force",
    delegates_to="bioscout.utils.scale_measurements.mass_from_static_grf",
    needs_opensim=False,
    writes_model=False,
    params=[
        Param("grf_mot", "path", required=True,
              help="Static trial GRF file (grf.mot)"),
    ])
def mass_from_static_grf(model, out, *, grf_mot, **_):
    from bioscout.utils.scale_measurements import mass_from_static_grf as _m

    kg = _m(str(grf_mot), verbose=False)
    if not kg:
        return OpResult(False, "mass_from_static_grf", str(model),
                        reason=f"no usable vertical force in {grf_mot}")
    return OpResult(True, "mass_from_static_grf", str(model), None,
                    data={"mass_kg": float(kg)},
                    messages=[f"[model-edit] measured body mass {kg:.2f} kg "
                              f"from the static plates"])
