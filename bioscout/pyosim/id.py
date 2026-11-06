"""Inverse dynamics in pure Python: the generalized forces that, with the
measured joint angles and the external loads, produce the measured motion --
what OpenSim's InverseDynamicsTool writes to inverse_dynamics.sto.

    Q_k = sum_bodies  J_v,k . (m a_c - m g - F_ext)  +  J_w,k . (I alpha + w x I w - M_ext)

with J the body Jacobians (finite differences of the model's forward
kinematics, so coordinate couplers are honoured), a_c / alpha the COM and
angular accelerations from the low-pass-filtered coordinates, and the
external loads read from an OpenSim ExternalLoads .xml + its .mot.
"""
import os
import re
import xml.etree.ElementTree as ET
import numpy as np
from scipy.signal import butter, filtfilt
from .model import Model, _vec, Kinematics
from .io import read_sto, write_mot

DQ = 1e-6


# ------------------------------------------------------------------ inputs
def read_coords(model, mot_path):
    """ik.mot -> times, (n, ncoord) array in rad/m, in model.coord_order."""
    cols, data, deg = read_sto(mot_path)
    t = data[:, cols.index("time")]
    Q = np.zeros((len(t), len(model.coord_order)))
    for k, n in enumerate(model.coord_order):
        c = model.coords[n]
        if n in cols:
            v = data[:, cols.index(n)]
            if deg and not c.translational and c.coupled is None:
                v = np.radians(v)
            Q[:, k] = v
        else:
            Q[:, k] = c.default
    # couplers and locks, as the model has them
    for i in range(len(t)):
        q = model.full_q(dict(zip(model.coord_order, Q[i])))
        Q[i] = [q[n] for n in model.coord_order]
    return t, Q


def read_external_loads(xml_path, mot_path=None):
    """ExternalLoads .xml -> (datafile, [force dicts]). The datafile in the xml
    is used unless mot_path is given."""
    root = ET.parse(xml_path).getroot()
    el = root.find("ExternalLoads")
    if el is None:
        raise ValueError("no <ExternalLoads> in " + os.path.basename(xml_path))
    forces = []
    for ef in el.iter("ExternalForce"):
        g = lambda k, d="": (ef.findtext(k) or d).strip()
        forces.append(dict(name=ef.get("name"), body=g("applied_to_body"),
                           force_in=g("force_expressed_in_body", "ground"), point_in=g("point_expressed_in_body", "ground"),
                           fid=g("force_identifier"), pid=g("point_identifier"), tid=g("torque_identifier")))
    datafile = mot_path or (el.findtext("datafile") or "").strip()
    return datafile, forces


def _xyz(cols, data, ident, t_src, t_dst):
    if not ident:
        return np.zeros((len(t_dst), 3))
    out = np.zeros((len(t_dst), 3))
    for a, ax in enumerate("xyz"):
        name = ident + ax
        if name not in cols:
            raise ValueError(f"column {name} not in the loads file")
        out[:, a] = np.interp(t_dst, t_src, data[:, cols.index(name)])
    return out


def _lowpass(X, t, cutoff):
    """As OpenSim's tools filter coordinates (Storage::pad(n/2) + lowpassIIR): pad each end with
    half the signal, reflected about the end point, then a 3rd-order Butterworth forward and back."""
    if not cutoff or cutoff <= 0 or len(t) < 12:
        return X
    fs = 1.0 / np.median(np.diff(t))
    b, a = butter(3, min(cutoff / (fs / 2), 0.99))
    X = np.asarray(X, float); n = len(X); p = n // 2
    pre = 2 * X[0] - X[p:0:-1]
    post = 2 * X[-1] - X[-2:-p - 2:-1]
    Y = filtfilt(b, a, np.concatenate([pre, X, post]), axis=0, padlen=0)
    return Y[p:p + n]


# ------------------------------------------------------------------ kinematics
def _transforms(model, qfull):
    """body_transforms without full_q, so every coordinate can be perturbed."""
    T = {"ground": (np.eye(3), np.zeros(3))}
    for j in model.joints:
        Rb, pb = T[model._body_of(j.parent)]
        Rf, pf = Rb @ j.parent.R, pb + Rb @ j.parent.p
        Rj, pj = j.local(qfull)
        Rm, pm = Rf @ Rj, pf + Rf @ pj
        Rc, pc = j.child.R, j.child.p
        Rbody = Rm @ Rc.T
        T[model._body_of(j.child)] = (Rbody, pm - Rbody @ pc)
    return T


def _skew_vec(S):
    return np.array([S[2, 1] - S[1, 2], S[0, 2] - S[2, 0], S[1, 0] - S[0, 1]]) / 2


def _body_state(model, Q, t, kin=None):
    """COM positions (n, nb, 3), rotations (n, nb, 3, 3) for all bodies, all frames at once."""
    kin = kin or Kinematics(model, [])
    names = list(model.bodies)
    T = kin.bodies(Q)
    R = np.stack([np.broadcast_to(T[b][0], (len(Q), 3, 3)) for b in names], axis=1)
    C = np.stack([T[b][1] + T[b][0] @ model.bodies[b]["com"] for b in names], axis=1)
    return names, C, R


def _jacobians_all(model, Q, names, kin):
    """Body COM / angular Jacobians for every frame: (n, nc, nb, 3) each, by forward
    differences in batches -- a perturbed independent coordinate drags its couplers along."""
    n, nc = Q.shape
    com = np.array([model.bodies[b]["com"] for b in names])
    Jv = np.zeros((n, nc, len(names), 3)); Jw = np.zeros((n, nc, len(names), 3))
    step = max(1, 4000 // (nc + 1))
    for a in range(0, n, step):
        Qs = Q[a:a + step]; m = len(Qs)
        P = np.repeat(Qs[:, None, :], nc + 1, axis=1)               # (m, nc+1, nc)
        P[:, 1:, :] += DQ * np.eye(nc)[None]
        P = kin.couple(P.reshape(-1, nc))
        T = kin.bodies(P)
        Rb = np.stack([np.broadcast_to(T[b][0], (len(P), 3, 3)) for b in names], 1).reshape(m, nc + 1, len(names), 3, 3)
        Cb = np.stack([T[b][1] + T[b][0] @ com[k] for k, b in enumerate(names)], 1).reshape(m, nc + 1, len(names), 3)
        Jv[a:a + m] = (Cb[:, 1:] - Cb[:, :1]) / DQ
        dR = np.einsum("mqbij,mbkj->mqbik", Rb[:, 1:], Rb[:, 0])    # R1 R0^T
        Jw[a:a + m] = np.stack([dR[..., 2, 1] - dR[..., 1, 2], dR[..., 0, 2] - dR[..., 2, 0], dR[..., 1, 0] - dR[..., 0, 1]], -1) / (2 * DQ)
    return Jv, Jw


# ------------------------------------------------------------------ the tool
def run(model_path, coords_mot, loads_xml, out_sto, loads_mot=None, t_range=None, cutoff=6.0, log=print,
        setup_path=None):
    model = model_path if isinstance(model_path, Model) else Model(model_path)
    t, Q = read_coords(model, coords_mot)
    if t_range:
        m = (t >= t_range[0] - 1e-9) & (t <= t_range[1] + 1e-9)
        t, Q = t[m], Q[m]
    if len(t) < 5:
        raise ValueError("too few frames for inverse dynamics")
    Q = _lowpass(Q, t, cutoff)
    log(f"[id] {len(t)} frames, {len(model.coord_order)} coordinates, {len(model.bodies)} bodies, low-pass {cutoff} Hz")

    # external loads, resampled to the coordinate times
    loads = []
    if loads_xml:
        datafile, forces = read_external_loads(loads_xml, loads_mot)
        if not os.path.isabs(datafile) and not os.path.isfile(datafile):
            datafile = os.path.join(os.path.dirname(loads_xml), datafile)
        cols, data, _ = read_sto(datafile)
        ts = data[:, cols.index("time")]
        for f in forces:
            if f["body"] not in model.bodies:
                raise ValueError(f"external force {f['name']} is applied to {f['body']}, not a body of the model")
            loads.append((f, _xyz(cols, data, f["fid"], ts, t), _xyz(cols, data, f["pid"], ts, t), _xyz(cols, data, f["tid"], ts, t)))
        log(f"[id] {len(loads)} external force(s) from {os.path.basename(datafile)}: " + ", ".join(f['name'] + '->' + f['body'] for f, *_ in loads))

    kin = Kinematics(model, [])
    names, C, R = _body_state(model, Q, t, kin)
    mass = np.array([model.bodies[b]["mass"] for b in names])
    Iloc = []
    for b in names:
        xx, yy, zz, xy, xz, yz = model.bodies[b]["inertia"]
        Iloc.append(np.array([[xx, xy, xz], [xy, yy, yz], [xz, yz, zz]]))
    g = np.asarray(model.gravity)

    # body kinematics by central differences
    V = np.gradient(C, t, axis=0); A = np.gradient(V, t, axis=0)
    Rd = np.gradient(R, t, axis=0)
    S = np.einsum("nbij,nbkj->nbik", Rd, R)                       # dR/dt R^T
    W = np.stack([S[..., 2, 1] - S[..., 1, 2], S[..., 0, 2] - S[..., 2, 0], S[..., 1, 0] - S[..., 0, 1]], -1) / 2
    AL = np.gradient(W, t, axis=0)

    bidx = {b: k for k, b in enumerate(names)}
    JV, JW = _jacobians_all(model, Q, names, kin)
    out = np.zeros((len(t), len(model.coord_order)))
    for i in range(len(t)):
        Fs = mass[:, None] * (A[i] - g[None, :])                       # m(a - g)
        Ms = np.zeros((len(names), 3))
        for b in range(len(names)):
            Ig = R[i, b] @ Iloc[b] @ R[i, b].T
            Ms[b] = Ig @ AL[i, b] + np.cross(W[i, b], Ig @ W[i, b])
        for f, F, P, Tq in loads:
            b = bidx[f["body"]]
            Fg = F[i] if f["force_in"] == "ground" else R[i, bidx[f["force_in"]]] @ F[i]
            Tg = Tq[i] if f["force_in"] == "ground" else R[i, bidx[f["force_in"]]] @ Tq[i]
            if f["point_in"] == "ground":
                Pg = P[i]
            else:
                Rb, pb = R[i, bidx[f["point_in"]]], C[i, bidx[f["point_in"]]] - R[i, bidx[f["point_in"]]] @ model.bodies[f["point_in"]]["com"]
                Pg = pb + Rb @ P[i]
            Fs[b] -= Fg
            Ms[b] -= np.cross(Pg - C[i, b], Fg) + Tg
        Jv, Jw = JV[i], JW[i]
        out[i] = np.einsum("kbj,bj->k", Jv, Fs) + np.einsum("kbj,bj->k", Jw, Ms)
        if i % 50 == 0:
            log(f"[id] frame {i + 1}/{len(t)}")

    # body origins in ground (for the skeleton drawn over the figures)
    try:
        TB = kin.bodies(Q); bcols, bdata = ["time"], [t]
        for b in model.bodies:
            o = np.broadcast_to(TB[b][1], (len(t), 3))
            for a, ax in enumerate("xyz"):
                bcols.append(f"{b}_{ax}"); bdata.append(o[:, a])
        write_mot(os.path.join(os.path.dirname(out_sto) or ".", "body_positions.sto"), bcols, np.column_stack(bdata), name="Body origins in ground (m)", degrees=False)
    except Exception as e:                                  # the figure is optional
        log(f"[id] body positions not written: {e}")
    cols = ["time"] + [n + ("_force" if model.coords[n].translational else "_moment") for n in model.coord_order]
    write_mot(out_sto, cols, np.column_stack([t, out]), name="Inverse Dynamics Generalized Forces", degrees=False)
    log(f"[id] wrote {os.path.basename(out_sto)}")
    if setup_path:
        write_setup(setup_path, model_path, coords_mot, loads_xml, out_sto, (t[0], t[-1]), cutoff)
    return t, cols, out


def write_body_positions(model_path, coords_mot, out_path, cutoff=6.0):
    """body_positions.sto (body origins in ground) from the joint angles alone -- the skeleton row of the figures."""
    model = model_path if isinstance(model_path, Model) else Model(model_path)
    t, Q = read_coords(model, coords_mot)
    Q = _lowpass(Q, t, cutoff)
    TB = Kinematics(model, []).bodies(Q); cols, data = ["time"], [t]
    for b in model.bodies:
        o = np.broadcast_to(TB[b][1], (len(t), 3))
        for a, ax in enumerate("xyz"):
            cols.append(f"{b}_{ax}"); data.append(o[:, a])
    write_mot(out_path, cols, np.column_stack(data), name="Body origins in ground (m)", degrees=False)
    return out_path


def write_setup(path, model_path, coords_mot, loads_xml, out_sto, tr, cutoff):
    b = lambda p: os.path.basename(p) if isinstance(p, str) else "scaled.osim"
    with open(path, "w", newline="\n") as f:
        f.write(f"""<?xml version="1.0" encoding="UTF-8" ?>
<OpenSimDocument Version="40000">
\t<InverseDynamicsTool name="id">
\t\t<results_directory>.</results_directory>
\t\t<model_file>{b(model_path)}</model_file>
\t\t<time_range>{tr[0]:.6f} {tr[1]:.6f}</time_range>
\t\t<forces_to_exclude> Muscles</forces_to_exclude>
\t\t<external_loads_file>{b(loads_xml) if loads_xml else ''}</external_loads_file>
\t\t<coordinates_file>{b(coords_mot)}</coordinates_file>
\t\t<lowpass_cutoff_frequency_for_coordinates>{cutoff}</lowpass_cutoff_frequency_for_coordinates>
\t\t<output_gen_force_file>{b(out_sto)}</output_gen_force_file>
\t</InverseDynamicsTool>
</OpenSimDocument>
""")


# ------------------------------------------------------------------ a default GRF.xml
def make_grf_xml(model, grf_mot, coords_mot, out_xml, right="calcn_r", left="calcn_l", threshold=10.0, log=print):
    """ExternalLoads .xml from a force-plate .mot: each plate goes to the foot
    whose body is nearest its centre of pressure while the plate is loaded."""
    cols, data, _ = read_sto(grf_mot)
    plates = {}
    for c in cols:
        lc = c.lower()
        m = re.search(r"\d+", c)
        key = m.group(0) if m else "1"
        if "force" in lc and lc.endswith("vx"):
            plates.setdefault(key, {})["fid"] = c[:-1]
        elif "force" in lc and lc.endswith("px"):
            plates.setdefault(key, {})["pid"] = c[:-1]
        elif "torque" in lc and lc.endswith("x"):
            plates.setdefault(key, {})["tid"] = c[:-1]
    plates = {k: v for k, v in plates.items() if "fid" in v and "pid" in v}
    if not plates:
        raise ValueError("no force-plate columns (…force…vx / …force…px) in " + os.path.basename(grf_mot))
    ts = data[:, cols.index("time")]
    t, Q = read_coords(model, coords_mot)
    names, C, R = _body_state(model, Q, t)
    feet = {s: names.index(b) for s, b in (("r", right), ("l", left)) if b in names}
    objs = []
    for key, ids in sorted(plates.items(), key=lambda kv: int(kv[0])):
        F = _xyz(cols, data, ids["fid"], ts, t); P = _xyz(cols, data, ids["pid"], ts, t)
        on = F[:, 1] > threshold
        if not on.any() or not feet:
            log(f"[id] plate {key}: never loaded in this window, skipped"); continue
        d = {s: np.nanmean(np.linalg.norm(P[on] - C[on, b], axis=1)) for s, b in feet.items()}
        side = min(d, key=d.get)
        body = right if side == "r" else left
        log(f"[id] plate {key} -> {body} (COP to foot {d[side] * 100:.0f} cm)")
        objs.append(f"""\t\t\t<ExternalForce name="grf_{side}_{key}">
\t\t\t\t<applied_to_body>{body}</applied_to_body>
\t\t\t\t<force_expressed_in_body>ground</force_expressed_in_body>
\t\t\t\t<point_expressed_in_body>ground</point_expressed_in_body>
\t\t\t\t<force_identifier>{ids['fid']}</force_identifier>
\t\t\t\t<point_identifier>{ids['pid']}</point_identifier>
\t\t\t\t<torque_identifier>{ids.get('tid', '')}</torque_identifier>
\t\t\t\t<data_source_name>Unassigned</data_source_name>
\t\t\t</ExternalForce>""")
    with open(out_xml, "w", newline="\n") as f:
        f.write('<?xml version="1.0" encoding="UTF-8" ?>\n<OpenSimDocument Version="40000">\n\t<ExternalLoads name="externalloads">\n\t\t<objects>\n'
                + "\n".join(objs) + f"\n\t\t</objects>\n\t\t<groups />\n\t\t<datafile>{os.path.basename(grf_mot)}</datafile>\n"
                "\t\t<external_loads_model_kinematics_file></external_loads_model_kinematics_file>\n"
                "\t\t<lowpass_cutoff_frequency_for_load_kinematics>6</lowpass_cutoff_frequency_for_load_kinematics>\n\t</ExternalLoads>\n</OpenSimDocument>\n")
    return out_xml
