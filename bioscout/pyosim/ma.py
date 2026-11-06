"""Muscle analysis in pure Python, in OpenSim's MuscleAnalysis file layout:
_MuscleAnalysis_Length.sto, _FiberLength.sto, _NormalizedFiberLength.sto,
_TendonLength.sto, _MomentArm_<coord>.sto and, when muscle forces are given
(static optimisation), _Moment_<coord>.sto = moment arm x force per muscle.
Paths and moment arms come from muscles.Paths (checked against OpenSim's
MuscleAnalysis: lengths ~0.5 mm, moment arms ~1 mm median)."""
import os
import numpy as np
from .model import Model
from .muscles import Paths
from .io import read_sto, write_mot
from . import id as idtool

LEG = ("hip_flexion", "hip_adduction", "hip_rotation", "knee_angle", "knee_adduction", "ankle_angle", "subtalar_angle")


def run(model_path, coords_mot, out_dir, forces_sto=None, t_range=None, cutoff=6.0, coords=None, log=print, prefix=""):
    model = model_path if isinstance(model_path, Model) else Model(model_path)
    paths = Paths(model, model.path)
    t, Q = idtool.read_coords(model, coords_mot)
    if t_range:
        m = (t >= t_range[0] - 1e-9) & (t <= t_range[1] + 1e-9); t, Q = t[m], Q[m]
    Q = idtool._lowpass(Q, t, cutoff)
    coords = coords or [c for c in model.coord_order if any(c.startswith(b) for b in LEG) and not model.coords[c].locked]
    L, R = paths.moment_arms(Q, coords)
    mus = paths.mus; names = [m["name"] for m in mus]
    lopt = np.array([m["lopt"] for m in mus]); lts = np.array([m["lts"] for m in mus]); h = lopt * np.sin(np.array([m["alpha"] for m in mus]))
    lm = np.sqrt(np.maximum(L - lts, 1e-4) ** 2 + h ** 2)
    os.makedirs(out_dir, exist_ok=True)
    W = lambda tag, data: write_mot(os.path.join(out_dir, f"{prefix}_MuscleAnalysis_{tag}.sto"), ["time"] + names,
                                    np.column_stack([t, data]), name=f"MuscleAnalysis {tag}", degrees=False)
    W("Length", L); W("FiberLength", lm); W("NormalizedFiberLength", lm / lopt); W("TendonLength", np.broadcast_to(lts, L.shape))
    for k, c in enumerate(coords):
        W(f"MomentArm_{c}", R[:, k])
    F = None
    if forces_sto and os.path.isfile(forces_sto):
        fc, fd, _ = read_sto(forces_sto); tf = fd[:, fc.index("time")]
        F = np.stack([np.interp(t, tf, fd[:, fc.index(n)]) if n in fc else np.zeros(len(t)) for n in names], 1)
        for k, c in enumerate(coords):
            W(f"Moment_{c}", R[:, k] * F)
    log(f"[ma] {len(t)} frames, {len(names)} muscles, moment arms about {len(coords)} coordinates"
        + (", muscle moments from the static-optimisation forces" if F is not None else ""))
    return t, names, L, R, coords
