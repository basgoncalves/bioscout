"""Inverse kinematics: weighted least squares on marker positions, frame by frame,
like OpenSim's InverseKinematicsTool (same task set and setup files)."""
import os
import xml.etree.ElementTree as ET
import numpy as np
from scipy.optimize import least_squares
from .io import read_trc, write_mot
from .model import Model, Kinematics


def read_tasks(path):
    """IK task set -> {marker: weight}, {coordinate: (weight, value_or_None)}."""
    root = ET.parse(path).getroot()
    mk, co = {}, {}
    for t in root.iter("IKMarkerTask"):
        if (t.findtext("apply") or "true").strip() == "true":
            mk[t.get("name")] = float(t.findtext("weight") or 1)
    for t in root.iter("IKCoordinateTask"):
        if (t.findtext("apply") or "true").strip() == "true":
            vt = (t.findtext("value_type") or "default_value").strip()
            co[t.get("name")] = (float(t.findtext("weight") or 1), vt, float(t.findtext("value") or 0))
    return mk, co


def solve(model, times, markers, marker_w, coord_tasks=None, t_range=None, log=print):
    coord_tasks = coord_tasks or {}
    names = [n for n in marker_w if n in markers and n in model.markers]
    common = [n for n in model.markers if n in markers and not np.isnan(markers[n]).all()]
    # a task set written for another lab's marker names would track a handful of markers and
    # leave the rest unused: when it covers less than half of what model and .trc share, every
    # shared marker is tracked with weight 1 instead (the task-set weights only where they match)
    if len(names) < 6 or len(names) < 0.5 * len(common):
        log(f"[ik] task set names only {len(names)} of the {len(common)} markers shared by model and .trc; "
            f"tracking all {len(common)} (task-set weights where named, 1 elsewhere)")
        marker_w = {n: marker_w.get(n, 1.0) for n in common}
        names = common
    elif len(common) > len(names):   # markers the placer added from the c3d: track them too, weight 1
        extra = [n for n in common if n not in marker_w]
        log(f"[ik] also tracking {len(extra)} markers not in the task set (weight 1): {' '.join(extra[:15])}")
        marker_w = {**marker_w, **{n: 1.0 for n in extra}}
        names = names + extra
    missing = [n for n in marker_w if n not in markers or n not in model.markers]
    if len(names) < 6:
        raise ValueError(f"only {len(names)} task markers are both in the model and the .trc "
                         f"({', '.join(names) or 'none'}); check marker names / task set")
    if missing:
        log(f"[ik] {len(missing)} task markers not found, ignored: {', '.join(missing[:10])}")
    free = model.free
    lo = np.array([model.coords[n].range[0] if model.coords[n].clamped else -np.inf for n in free])
    hi = np.array([model.coords[n].range[1] if model.coords[n].clamped else np.inf for n in free])
    w = np.sqrt(np.array([marker_w[n] for n in names]))
    ct = [(n, np.sqrt(wt), val) for n, (wt, vt, val) in coord_tasks.items() if n in free]
    sel = np.ones(len(times), bool)
    if t_range is not None:
        half = 0.5 * np.median(np.diff(times))
        sel = (times >= t_range[0] - 1e-9) & (times <= t_range[1] + half)
    x = np.array([model.coords[n].default for n in free])
    x = np.clip(x, lo, hi)
    kin = Kinematics(model, names)
    nf = len(free)
    ct_i = [(free.index(n), s, val) for n, s, val in ct]
    H = 1e-6

    def resid_jac(v, obs, ok):
        V = np.vstack([v, v + H * np.eye(nf)])                 # pose + forward differences
        P = kin.markers(V)                                      # (nf+1, m, 3)
        R = ((P - obs[None]) * w[None, :, None])[:, ok].reshape(nf + 1, -1)
        if ct_i:
            C = np.array([[s * (Vb[i] - val) for i, s, val in ct_i] for Vb in V])
            R = np.hstack([R, C])
        return R[0], ((R[1:] - R[0]) / H).T

    # frames with too few task markers (subject outside the volume, start/end of a sprint
    # trial) cannot be solved: trimmed at the ends, the last pose held through gaps inside
    vis = np.array([(~np.isnan(np.array([markers[n][k] for n in names])).any(axis=1)).sum() for k in range(len(times))])
    MIN = 6
    idx = np.where(sel & (vis >= MIN))[0]
    if not len(idx):
        raise ValueError(f"no frame in the time range has {MIN} or more of the task markers")
    sel = sel & (np.arange(len(times)) >= idx[0]) & (np.arange(len(times)) <= idx[-1])
    trimmed = int(sel.sum() - len(idx))
    if idx[0] > np.where(sel | True)[0][0] or trimmed:
        log(f"[ik] solving {times[idx[0]]:.3f}-{times[idx[-1]]:.3f} s ({int(sel.sum())} frames); "
            f"{trimmed} frames inside with < {MIN} markers keep the last pose")
    out, errs, per = [], [], []
    first = True
    for k in np.where(sel)[0]:
        obs = np.array([markers[n][k] for n in names])
        ok = ~np.isnan(obs).any(axis=1)
        if ok.sum() < MIN:
            out.append(model.full_q(dict(zip(free, x)))); errs.append((np.nan, np.nan, np.nan)); per.append(np.full(len(names), np.nan))
            continue
        obs = np.nan_to_num(obs)
        cache = {}

        def fun(v):
            r, J = resid_jac(v, obs, ok); cache["J"] = J; cache["v"] = v.copy(); return r

        def jac(v):
            if "v" not in cache or not np.array_equal(cache["v"], v):
                fun(v)
            return cache["J"]

        sol = least_squares(fun, x, jac=jac, bounds=(lo, hi), method="trf", x_scale="jac",
                            xtol=1e-6, ftol=1e-6, gtol=1e-6, max_nfev=200 if first else 20)
        x = sol.x; first = False
        P = kin.markers(x[None])[0]
        d = np.linalg.norm(P - obs, axis=1)
        e = d[ok]
        errs.append((np.sqrt(np.mean(e ** 2)), e.max(), float(np.sum(e ** 2))))
        per.append(np.where(ok, d, np.nan))                  # per-marker distance (m), as _ik_marker_errors_all.sto
        out.append(model.full_q(dict(zip(free, x))))
    t = times[sel]
    return t, out, np.array(errs), names, np.array(per)


def run(model_path, trc_path, task_path, out_mot, t_range=None, log=print, markerset=None,
        errors_path=None, setup_path=None):
    model = model_path if isinstance(model_path, Model) else Model(model_path)
    if markerset:
        model.load_markerset(markerset)
        if getattr(model, "dropped_markers", None):
            d, b = model.dropped_markers
            log(f"[ik] {len(d)} marker(s) of the marker set left out, on bodies the model does not have ({', '.join(b)}): {' '.join(d)}")
        log(f"[ik] markers from {os.path.basename(markerset)} ({len(model.markers)})")
    times, markers, rate = read_trc(trc_path)
    mw, ct = read_tasks(task_path) if task_path else ({}, {})
    t, qs, errs, used, per = solve(model, times, markers, mw, ct, t_range, log)
    cols = ["time"] + model.coord_order
    # as OpenSim: degrees for rotational coordinates, but coupled (dependent) ones stay in radians
    rot = {n for n, c in model.coords.items() if not c.translational and c.coupled is None}
    data = np.array([[ti] + [np.degrees(q[n]) if n in rot else q[n] for n in model.coord_order]
                     for ti, q in zip(t, qs)])
    write_mot(out_mot, cols, data)
    if errors_path:   # as OpenSim's _ik_marker_errors.sto
        write_mot(errors_path, ["time", "total_squared_error", "marker_error_RMS", "marker_error_max"],
                  np.column_stack([t, errs[:, 2], errs[:, 0], errs[:, 1]]), name="Model Marker Errors from IK",
                  degrees=False)
        # per-marker distances (m), as bioscout's _ik_marker_errors_all.sto
        allp = os.path.join(os.path.dirname(errors_path), "ik_marker_errors_all.sto")
        write_mot(allp, ["time"] + list(used), np.column_stack([t, per]), name="Per-marker errors from IK", degrees=False)
    if setup_path:
        write_setup(setup_path, model_path, trc_path, task_path, out_mot, t if len(t) else None)
    log(f"[ik] {len(t)} frames, {len(used)} markers; RMS error mean {errs[:,0].mean()*1000:.1f} mm, "
        f"max {errs[:,1].max()*1000:.1f} mm")
    return out_mot, errs


def write_setup(path, model_path, trc_path, task_path, out_mot, t):
    """An OpenSim InverseKinematicsTool setup that reproduces this run in the desktop GUI."""
    b = lambda p: os.path.basename(p) if isinstance(p, str) else "scaled.osim"
    tr = f"{t[0]:.6f} {t[-1]:.6f}" if t is not None else ""
    with open(path, "w", newline="\n") as f:
        f.write(f"""<?xml version="1.0" encoding="UTF-8" ?>
<OpenSimDocument Version="40000">
\t<InverseKinematicsTool name="ik">
\t\t<model_file>{b(model_path)}</model_file>
\t\t<constraint_weight>Inf</constraint_weight>
\t\t<accuracy>1e-05</accuracy>
\t\t<IKTaskSet file="{b(task_path) if task_path else ''}" />
\t\t<marker_file>{b(trc_path)}</marker_file>
\t\t<coordinate_file>Unassigned</coordinate_file>
\t\t<time_range>{tr}</time_range>
\t\t<report_errors>true</report_errors>
\t\t<output_motion_file>{b(out_mot)}</output_motion_file>
\t\t<report_marker_locations>false</report_marker_locations>
\t</InverseKinematicsTool>
</OpenSimDocument>
""")
