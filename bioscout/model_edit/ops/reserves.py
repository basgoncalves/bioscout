"""Reserve and residual actuators -- the force set static optimisation needs."""
from __future__ import annotations

import os
from pathlib import Path

from ..spec import OpResult, Param, op

__all__ = []

#: Names treated as residual (pelvis) actuators rather than joint reserves.
RESIDUALS = ("FX", "FY", "FZ", "MX", "MY", "MZ")


def _default_actuator_file():
    """settings' setup folder, if this machine has a project settings.py bound."""
    try:
        import settings as _s
        d = getattr(_s.BatchSettings, "setup_files_folder", None)
        if d:
            p = os.path.join(str(d), "actuators_so.xml")
            if os.path.exists(p):
                return p
    except Exception:                                        # noqa: BLE001
        pass
    return None


def _load_force_set(path):
    """Load a force-set XML THROUGH OpenSim so its document version is upgraded.

    This is the whole reason this op exists as code rather than as an XML edit.
    A typical actuators_so.xml is OpenSimDocument Version 40000 while a current
    model is 40600, and OpenSim rewrites the older schema -- a
    CoordinateActuator's ``<coordinate>`` becomes a socket, a PointActuator's
    ``<body>`` becomes ``<socket_frame>`` -- only when it LOADS the document.
    Copying the XML blocks into a 40600 model as text skips that: the
    properties are unrecognised, the actuators never connect, and the model
    then loads WITHOUT them and without an error. The symptom is silent and
    downstream: static optimisation with no reserves drives the muscles to
    whatever balances the inverse-dynamics moments, which has produced a
    walking hip contact force of 26 BW against a true 5.4.
    """
    import opensim as osim
    for ctor in (lambda: osim.ForceSet(path),
                 lambda: osim.ForceSet(path, True)):
        try:
            fs = ctor()
            if fs.getSize():
                return fs
        except Exception:                                    # noqa: BLE001
            continue
    return None


@op("reserves",
    verb="actuators",
    summary="Add the SO reserve and pelvis residual actuators to the model",
    delegates_to="opensim.ForceSet + Model.updForceSet().cloneAndAppend",
    suffix="_reserves",
    notes=("Static optimisation runs with useModelForceSet(True) and ALSO "
           "appends whatever force-set files it is given, so these actuators "
           "must exist in exactly one place. In both, each one is created "
           "twice -- two independent actuators on the same coordinate, halving "
           "the effective cost of a reserve. In neither, SO has nothing to "
           "absorb the muscle-moment vs ID-moment difference and silently "
           "inflates the muscle forces. bioscout.utils.openSim."
           "reserve_actuator_plan() enforces that at run time; this op is how "
           "you put them in the model. "
           "Note that published gait models do not ship reserves: Catelli's 17 "
           "and Hagen's 13 CoordinateActuators are all on lumbar and arm DOFs "
           "that carry no muscles, which is model rather than analysis. Adding "
           "them here is a deliberate pipeline choice, so apply it to every "
           "model a study compares, and release the pre-edit file."),
    params=[
        Param("actuators", "path", default=None,
              help="Force-set XML to take the actuators from "
                   "(default: <setup folder>/actuators_so.xml)"),
        Param("optimal_force", "float", default=None, unit="N.m",
              help="Override optimal_force on the joint reserves only; the "
                   "pelvis residuals keep theirs. Must match whatever the SO "
                   "setup used to append, or the cost of a reserve changes."),
        Param("allow_partial", "bool", default=False,
              help="Proceed when the model already has SOME of them. Off by "
                   "default: a partial set is how duplicates get created."),
    ])
def reserves(model, out, *, actuators=None, optimal_force=None,
             allow_partial=False, **_):
    import opensim as osim

    src = str(actuators) if actuators else _default_actuator_file()
    if not src or not os.path.exists(src):
        return OpResult(False, "reserves", str(model),
                        reason=("no actuator force-set XML: pass actuators=<path>. "
                                "The pelvis residuals are PointActuators with a "
                                "body, point and direction, so they cannot be "
                                "invented -- they have to come from a file."))
    fs = _load_force_set(src)
    if fs is None:
        return OpResult(False, "reserves", str(model),
                        reason=f"{os.path.basename(src)} loaded as an empty or "
                               f"unreadable ForceSet")

    m = osim.Model(str(model))
    have = {m.getForceSet().get(i).getName()
            for i in range(m.getForceSet().getSize())}
    want = [fs.get(i).getName() for i in range(fs.getSize())]
    already = [n for n in want if n in have]
    if already and not allow_partial:
        if len(already) == len(want):
            return OpResult(True, "reserves", str(model), str(model),
                            changed={},
                            messages=[f"[model-edit] all {len(want)} actuator(s) "
                                      f"already present; model unchanged"])
        return OpResult(False, "reserves", str(model),
                        reason=(f"{len(already)} of {len(want)} already in the "
                                f"model ({already[:4]}). A partial set is how "
                                f"duplicates happen -- pass allow_partial=True "
                                f"only if you know the rest are genuinely absent."))

    added, kinds = [], {}
    for i in range(fs.getSize()):
        f = fs.get(i)
        if f.getName() in have:
            continue
        if optimal_force is not None and f.getConcreteClassName() == "CoordinateActuator":
            try:
                osim.CoordinateActuator.safeDownCast(f).setOptimalForce(float(optimal_force))
            except Exception:                                # noqa: BLE001
                pass
        m.updForceSet().cloneAndAppend(f)
        added.append(f.getName())
        k = f.getConcreteClassName()
        kinds[k] = kinds.get(k, 0) + 1
    if not added:
        return OpResult(False, "reserves", str(model),
                        reason="nothing to add")
    m.finalizeConnections()
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    m.printToXML(str(out))

    # Verify the WRITTEN file, not the object in memory. A model that parses is
    # not a model whose actuators exist -- initSystem() is what proves the
    # sockets resolved.
    chk = osim.Model(str(out))
    kept = {chk.getForceSet().get(i).getName()
            for i in range(chk.getForceSet().getSize())}
    missing = [n for n in added if n not in kept]
    if missing:
        return OpResult(False, "reserves", str(model), str(out),
                        reason=f"{len(missing)} actuator(s) did not survive the "
                               f"write: {missing[:4]}")
    try:
        chk.initSystem()
    except Exception as e:                                   # noqa: BLE001
        return OpResult(False, "reserves", str(model), str(out),
                        reason=f"model does not initialise -- an actuator socket "
                               f"is unconnected: {type(e).__name__}: {e}")

    n_res = sum(1 for n in added if n.endswith("_reserve"))
    n_pel = sum(1 for n in added if n in RESIDUALS)
    return OpResult(
        True, "reserves", str(model), str(out),
        changed={"added": len(added), "joint_reserves": n_res,
                 "pelvis_residuals": n_pel, "source": os.path.basename(src),
                 "optimal_force": optimal_force if optimal_force is not None else "as in file"},
        messages=[f"[model-edit] +{len(added)} actuator(s) "
                  f"({', '.join(f'{v} {k}' for k, v in sorted(kinds.items()))}); "
                  f"{chk.getForceSet().getSize()} force(s) total, initSystem() ok"])
