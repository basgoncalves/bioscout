"""pyosim back end for bioscout's per-trial steps.

An iteration with ``engine: pyosim`` in session.yaml gets this module from
``Analyse._get_openSim()`` instead of ``bioscout.simulate.opensim``. It offers the
same functions with the same arguments, runs them with ``bioscout.pyosim`` (pure
numpy/scipy, no OpenSim) and writes the same files where the OpenSim versions
write them, so everything downstream (plots, residual checks, JCF contributions,
the comparison tables) reads them unchanged:

    run_ik   -> <setup output_motion_file>, _ik_marker_errors.sto
    run_id   -> <setup dir>/inverse_dynamics.sto
    run_ma   -> <results_dir>/_MuscleAnalysis_*.sto
    run_so   -> <resultsDir>/StaticOptimization_force.sto / _activation.sto
    run_jra  -> <saveFileName> (OpenSim's JointReaction column layout)

It never uses OpenSim (2026-11-03): no `import opensim`, no OpenSim module, no OpenSim
output. A step pyosim does not implement (RRA, CMC/forward simulation, energetics, ...)
raises NotImplementedError before writing anything -- it does not fall back to OpenSim.
"""
import os
import xml.etree.ElementTree as ET

from bioscout.pyosim import ik as _ik, id as _id, ma as _ma, so as _so, jra as _jra
from bioscout.pyosim.model import Model

ENGINE = "pyosim"


def _log(msg):
    if "frame " not in msg:          # pyosim's per-frame progress is noise in a batch log
        print(msg, flush=True)


def _resolve(path, base):
    if not path:
        return path
    path = path.strip()
    return path if os.path.isabs(path) else os.path.normpath(os.path.join(base, path))


def _setup_fields(setup_xml, *tags):
    root = ET.parse(setup_xml).getroot()
    return [(root.findtext(".//" + t) or "").strip() for t in tags]


def _time_range(txt):
    try:
        a, b = (float(x) for x in txt.split()[:2])
        return (a, b)
    except Exception:                                   # noqa: BLE001
        return None


# --------------------------------------------------------------------------- IK
def run_ik(osim_modelPath=None, setup_xml=None, resultsDir=None):
    """Inverse kinematics from an OpenSim IK setup (marker file, time range, task set)."""
    base = os.path.dirname(os.path.abspath(setup_xml))
    resultsDir = os.path.abspath(resultsDir or base)
    mfile, out, tr, model_file = _setup_fields(setup_xml, "marker_file", "output_motion_file", "time_range", "model_file")
    model = osim_modelPath or _resolve(model_file, base)
    trc = _resolve(mfile, base)
    if not os.path.isfile(trc):                              # bioscout writes paths relative to the trial folder
        trc = _resolve(mfile, resultsDir)
    out = _resolve(out or "joint_angles.mot", base)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    # marker report beside the joint angles, where bioscout's OpenSim IK leaves it
    rep = os.path.dirname(out)
    _ik.run(model, trc, setup_xml, out, _time_range(tr), log=_log,
            errors_path=os.path.join(rep, "_ik_marker_errors.sto"))
    try:
        _model_marker_locations(model, out, trc, os.path.join(rep, "_ik_model_marker_locations.sto"))
    except Exception as e:                                  # noqa: BLE001 -- a report, never fatal
        print(f"[IK] (pyosim) model marker locations not written: {e}", flush=True)
    print(f"[IK] (pyosim) done -> {out}", flush=True)
    return out


def _model_marker_locations(model_path, ik_mot, trc, dst):
    """_ik_model_marker_locations.sto as OpenSim writes it: every model marker that is also
    in the .trc, in ground, metres, one row per IK frame."""
    import numpy as np
    from bioscout.pyosim.io import read_trc
    m = Model(model_path)
    t, Q = _id.read_coords(m, ik_mot)
    names = [n for n in m.markers if n in read_trc(trc)[1]]
    rows = []
    for i in range(len(t)):
        P = m.marker_positions(dict(zip(m.coord_order, Q[i])), names)
        rows.append([t[i]] + [v for n in names for v in P[n]])
    cols = ["time"] + [f"{n}_{a}" for n in names for a in ("tx", "ty", "tz")]
    with open(dst, "w") as f:
        f.write(f"Model Marker Locations from IK\nversion=1\nnRows={len(rows)}\nnColumns={len(cols)}\ninDegrees=no\nendheader\n")
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join(f"{x:16.8f}" for x in r) + "\n")


# --------------------------------------------------------------------------- ID
def run_id(osimModelPath=None, ikOutputPath=None, grfXmlPath=None, setupXmlPath=None):
    """Inverse dynamics over the whole IK file, coordinates low-passed at 6 Hz (as bioscout's OpenSim ID)."""
    results = os.path.dirname(os.path.abspath(setupXmlPath))
    os.makedirs(results, exist_ok=True)
    out = os.path.join(results, "inverse_dynamics.sto")
    _id.run(Model(osimModelPath), ikOutputPath, grfXmlPath, out, cutoff=6.0, log=_log, setup_path=setupXmlPath)
    print(f"[ID] (pyosim) done -> {out}", flush=True)
    return out


# --------------------------------------------------------------------------- MA
def run_ma(osim_modelPath=None, ik_output=None, grf_xml=None, results_dir=None, coordinates=None,
           solve_equilibrium=False, actuators=None, method=None):
    """Muscle-tendon lengths, fibre lengths (rigid tendon) and moment arms."""
    results_dir = os.path.abspath(results_dir or os.path.join(os.path.dirname(os.path.abspath(ik_output)), "MuscleAnalysis"))
    os.makedirs(results_dir, exist_ok=True)
    _ma.run(Model(osim_modelPath), ik_output, results_dir, coords=coordinates, log=_log)
    print(f"[MA] (pyosim) done -> {results_dir}", flush=True)
    return results_dir


# --------------------------------------------------------------------------- SO
def run_so(osim_modelPath=None, ik_output=None, grf_xml=None, setup_xml=None, actuators=None, resultsDir=None):
    """Static optimisation as OpenSim's (active fibre force only, Millard curves, sum a^2).
    Needs the trial's inverse dynamics: the inverse_dynamics.sto beside the IK file, or
    one computed here from the IK and the GRF."""
    resultsDir = os.path.abspath(resultsDir or os.path.dirname(os.path.abspath(ik_output)))
    os.makedirs(resultsDir, exist_ok=True)
    id_sto = os.path.join(os.path.dirname(os.path.abspath(ik_output)), "inverse_dynamics.sto")
    if not os.path.isfile(id_sto):
        id_sto = os.path.join(resultsDir, "_so_inverse_dynamics.sto")
        _id.run(Model(osim_modelPath), ik_output, grf_xml, id_sto, cutoff=6.0, log=_log)
    acts = actuators[0] if isinstance(actuators, (list, tuple)) else actuators
    _so.run(Model(osim_modelPath), ik_output, id_sto, resultsDir, actuators=acts, log=_log, prefix="SO")
    from bioscout.simulate.so_files import migrate_dir, FORCE
    migrate_dir(resultsDir)                                   # SO_StaticOptimization_* -> StaticOptimization_*
    print(f"[SO] (pyosim) done -> {os.path.basename(resultsDir)}/{FORCE}", flush=True)
    return resultsDir


# --------------------------------------------------------------------------- JRA
def run_jra(osim_modelPath=None, ik_output=None, grf_xml=None, setup_xml=None, actuators=None,
            muscle_force_path=None, saveFileName=None):
    """Joint reaction loads on each child body, expressed in the child, from the muscle forces."""
    out = os.path.abspath(saveFileName or os.path.join(os.path.dirname(os.path.abspath(setup_xml or ik_output)),
                                                       "Analyse_JRA_ReactionLoads.sto"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    _jra.run(osim_modelPath, ik_output, muscle_force_path, grf_xml, out, log=_log)
    return out


def run_jra_subsets(osim_modelPath, ik_output, grf_xml, muscle_force_path, subsets):
    """{tag: set of muscles} -> {tag: DataFrame} of the joint reaction loads with only those
    muscles pulling (the others' forces zero), all from one pass: the loads are linear in the
    muscle forces. Used by the JCF contribution analysis instead of one JRA run per group."""
    import pandas as pd
    out = _jra.run_subsets(osim_modelPath, ik_output, muscle_force_path, grf_xml, subsets, log=_log)
    return {tag: pd.DataFrame(data, columns=cols) for tag, (cols, data) in out.items()}


# --------------------------------------------------------------------------- setups (plain XML)
from bioscout.simulate.grf_setup import create_grf_xml          # noqa: E402,F401  (no OpenSim)


def create_setup_IK(osim_modelPath=None, marker_trc=None, ik_output=None, taskSetPath=None,
                    time_range=None, saveXMLPath=None, ik_weights=None):
    """InverseKinematicsTool setup as bioscout's OpenSim create_setup_IK writes it (one
    IKMarkerTask per model marker; weight from session.yaml ik_weights / BatchSettings
    marker_weights by marker or parent body; markers not in the TRC or in markers_to_skip
    not applied), written as XML without OpenSim."""
    from bioscout.pyosim.io import read_trc
    if not osim_modelPath or not marker_trc:
        raise ValueError("create_setup_IK: osim_modelPath and marker_trc are required")
    if not os.path.exists(osim_modelPath):
        raise FileNotFoundError(f"model not found: {osim_modelPath}")
    try:
        from bioscout import settings as _st
        bs = getattr(_st, "BatchSettings", None)
        body_w = dict(getattr(bs, "marker_weights", {}) or {})
        skip = {str(x).upper() for x in (getattr(bs, "markers_to_skip", []) or [])}
    except Exception:                                        # noqa: BLE001
        body_w, skip = {}, set()
    over = {str(k): float(v) for k, v in (ik_weights or {}).items()}
    tmpl = {}
    if taskSetPath and os.path.isfile(taskSetPath):
        for t in ET.parse(taskSetPath).getroot().iter("IKMarkerTask"):
            tmpl[t.get("name")] = float(t.findtext("weight") or 1)
    model = Model(osim_modelPath)
    t, mk, _ = read_trc(marker_trc)
    in_trc = set(mk)
    tasks, tally = [], {"tracked": 0, "disabled": [], "skipped": []}
    for name, (body, _loc) in model.markers.items():
        w = over.get(name, over.get(body, tmpl.get(name, float(body_w.get(body, 1.0)))))
        skipped = name.upper() in skip or w <= 0
        apply = name in in_trc and not skipped
        tasks.append((name, apply, w))
        if skipped:
            tally["skipped"].append(name)
        elif not apply:
            tally["disabled"].append(name)
        else:
            tally["tracked"] += 1
    print(f"    markers: {tally['tracked']} tracked"
          + (f", {len(tally['disabled'])} disabled (not in TRC)" if tally["disabled"] else "")
          + (f", {len(tally['skipped'])} skipped" if tally["skipped"] else ""))
    t0, t1 = float(t[0]), float(t[-1])
    tr = None
    if time_range is not None:
        try:
            if isinstance(time_range, str):
                time_range = time_range.strip("[]").replace("np.float64(", "").replace(")", "").split(",")
            tr = [float(x) for x in time_range][:2]
            if len(tr) < 2:
                tr = None
            elif tr[0] < t0 or tr[1] > t1:
                print(f"[WARNING] time range {tr} is outside the marker data [{t0}, {t1}] -- using the full range")
                tr = None
        except (TypeError, ValueError):
            tr = None
    tr = tr or [t0, t1]
    print(f"    time range: [{tr[0]}, {tr[1]}]")
    if saveXMLPath is None:
        saveXMLPath = ik_output.replace(".mot", "_ik_setup.xml")
    res = os.path.dirname(os.path.abspath(ik_output))
    os.makedirs(res, exist_ok=True)
    model_file = os.path.relpath(osim_modelPath, os.path.dirname(os.path.abspath(saveXMLPath)))
    rows = "".join(f'\t\t\t\t<IKMarkerTask name="{n}">\n\t\t\t\t\t<apply>{"true" if a else "false"}</apply>\n'
                   f'\t\t\t\t\t<weight>{w:g}</weight>\n\t\t\t\t</IKMarkerTask>\n' for n, a, w in tasks)
    xml = ('<?xml version="1.0" encoding="UTF-8" ?>\n<OpenSimDocument Version="40600">\n\t<InverseKinematicsTool>\n'
           f'\t\t<results_directory>{res}</results_directory>\n\t\t<model_file>{model_file}</model_file>\n'
           f'\t\t<time_range>{tr[0]!r} {tr[1]!r}</time_range>\n'
           f'\t\t<output_motion_file>{os.path.relpath(os.path.abspath(ik_output), res)}</output_motion_file>\n'
           '\t\t<report_errors>true</report_errors>\n\t\t<IKTaskSet>\n\t\t\t<objects>\n' + rows +
           '\t\t\t</objects>\n\t\t\t<groups />\n\t\t</IKTaskSet>\n'
           f'\t\t<marker_file>{os.path.abspath(marker_trc)}</marker_file>\n'
           '\t\t<report_marker_locations>true</report_marker_locations>\n\t</InverseKinematicsTool>\n</OpenSimDocument>\n')
    os.makedirs(os.path.dirname(os.path.abspath(saveXMLPath)), exist_ok=True)
    with open(saveXMLPath, "w") as f:
        f.write(xml)
    print(f"[SETUP] {os.path.abspath(saveXMLPath)}  (pyosim)")


# --------------------------------------------------------------------------- CMC
def run_forward(osim_modelPath=None, kinematics=None, grf_xml=None, actuators=None, tasks=None,
                results_dir=None, time_range=None, lowpass_cutoff=6.0, cmc_time_window=0.01,
                replay=False, **_):
    """Computed muscle control (bioscout.pyosim.cmc) -> <results_dir>/cmc/, OpenSim's CMC
    file names. The open-loop ForwardTool replay is OpenSim-only: replay=True refuses."""
    if replay:
        not_implemented("open-loop forward replay (simulate forward)")
    from bioscout.pyosim import cmc as _cmc
    out = os.path.join(results_dir, "cmc")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "pyosim.log"), "w", encoding="utf-8") as fh:   # out.log = bioscout step log
        def log(m):
            fh.write(str(m) + "\n"); fh.flush(); _log(m)
        res = _cmc.run(osim_modelPath, kinematics, grf_xml, out, actuators=actuators, tasks=tasks,
                       t_range=time_range, cutoff=lowpass_cutoff or 6.0,
                       window=cmc_time_window or 0.01, log=log)
    return res


# --------------------------------------------------------------------------- not implemented
def not_implemented(step):
    raise NotImplementedError(
        f"{step} is not implemented in the pyosim engine, and a pyosim iteration never falls "
        f"back to OpenSim. Nothing was run or written. Use an iteration with engine: opensim.")


def __getattr__(name):                     # run_rra, run_energetics, ...: no fallback
    if name.startswith("__"):
        raise AttributeError(name)
    not_implemented(name)
