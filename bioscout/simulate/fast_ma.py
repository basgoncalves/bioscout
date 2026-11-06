"""Fast muscle analysis: MTU length + moment arms only, by finite differences.

OpenSim's MuscleAnalysis computes every moment arm with a separate
MomentArmSolver call (muscles x coordinates x frames) plus fibre outputs and
moments we never use. Here, per frame: pose the model once (IK, 6 Hz low-pass
like the AnalyzeTool), read all lengths, then for each coordinate perturb it
+/-h (constraints enforced, so couplers move with it) and take
r = -dL/dq for ALL muscles at once.

Writes _MuscleAnalysis_Length.sto and _MuscleAnalysis_MomentArm_<coord>.sto
(same names/columns as OpenSim) to --out.

  python fast_ma.py MODEL.osim IK.mot --out DIR [--coords hip_flexion_r ...]
  python fast_ma.py --compare REF_DIR NEW_DIR
"""
import argparse, os, sys, time
import numpy as np

LEG = ["hip_flexion", "hip_adduction", "hip_rotation", "knee_angle",
       "knee_adduction", "ankle_angle", "subtalar_angle"]


def write_sto(path, t, names, data, name):
    with open(path, "w") as f:
        f.write(f"{name}\nversion=1\nnRows={len(t)}\nnColumns={len(names)+1}\n"
                "inDegrees=no\nendheader\n")
        f.write("time\t" + "\t".join(names) + "\n")
        for i in range(len(t)):
            f.write(f"{t[i]:.8f}\t" + "\t".join(f"{v:.8f}" for v in data[i]) + "\n")


def run(model_path, ik_path, out, coords=None, h=1e-4, lowpass=6.0, min_wraps=2):
    import opensim as osim
    t0 = time.time()
    model = osim.Model(model_path)
    s = model.initSystem()
    cs = model.getCoordinateSet()
    names = [cs.get(i).getName() for i in range(cs.getSize())]
    if not coords:
        coords = [n for b in LEG for n in (b + "_r", b + "_l") if n in names]
    musc = model.getMuscles()
    mnames = [musc.get(i).getName() for i in range(musc.getSize())]
    mus = [musc.get(i) for i in range(musc.getSize())]

    sto = osim.Storage(ik_path)
    if lowpass:
        sto.pad(sto.getSize() // 2)
        sto.lowpassIIR(lowpass)
    if sto.isInDegrees():
        model.getSimbodyEngine().convertDegreesToRadians(sto)
    _cl = sto.getColumnLabels()
    labels = [_cl.get(i) for i in range(1, _cl.getSize())]
    tv = osim.ArrayDouble(); sto.getTimeColumn(tv)
    T = np.array([tv.get(i) for i in range(tv.getSize())])
    # keep the original (unpadded) span
    ik = osim.Storage(ik_path)
    keep = (T >= ik.getFirstTime() - 1e-9) & (T <= ik.getLastTime() + 1e-9)
    # row by row: getDataColumn() can return a column shorter than the time
    # column after pad() (seen on an 817-frame sit-down trial: 1225 vs 1633)
    Q = np.full((len(T), len(labels)), np.nan)
    for i in range(sto.getSize()):
        v = sto.getStateVector(i).getData()
        n = min(v.getSize(), len(labels))
        Q[i, :n] = [v.get(k) for k in range(n)]
    T, Q = T[keep], Q[keep]

    cidx = {lab: names.index(lab) for lab in labels if lab in names}
    L = np.zeros((len(T), len(mus)))
    R = {c: np.zeros((len(T), len(mus))) for c in coords}

    # coordinate couplers: set dependent = f(independents) directly instead of
    # model.assemble() (an iterative solve per call -- that was the slow part)
    couplers = []
    csets = model.getConstraintSet()
    for k in range(csets.getSize()):
        cc = osim.CoordinateCouplerConstraint.safeDownCast(csets.get(k))
        if cc is None or not cc.get_isEnforced():
            continue
        ind = cc.getIndependentCoordinateNames()
        couplers.append((cs.get(cc.getDependentCoordinateName()),
                         [cs.get(ind.get(j)) for j in range(ind.getSize())],
                         cc.getFunction()))
    locked = {n for n in names if cs.get(n).getLocked(s)}

    def apply_couplers():
        for dep, ind, fn in couplers:
            v = osim.Vector(len(ind), 0.0)
            for j, c in enumerate(ind):
                v.set(j, c.getValue(s))
            dep.setValue(s, fn.calcValue(v), False)

    def lengths():
        apply_couplers()
        model.realizePosition(s)
        return np.array([m.getLength(s) for m in mus])

    # Muscles wrapping over 2+ objects (gastrocs: shank + condyle cylinders):
    # OpenSim's wrap result depends on the order/previous path, so a +/-h length
    # difference is not their moment arm. Use OpenSim's own solver for those.
    exact = [k for k, m in enumerate(mus)
             if m.getGeometryPath().getWrapSet().getSize() >= min_wraps]
    print(f"[fast MA] OpenSim solver for {len(exact)} multi-wrap muscles: "
          + ", ".join(mnames[k] for k in exact))

    setters = [(cs.get(lab), labels.index(lab)) for lab in cidx if lab not in locked]
    free = [c for c in coords if c not in locked]

    for i in range(len(T)):
        for co, j in setters:
            co.setValue(s, Q[i, j], False)
        L[i] = lengths()
        for c in free:
            co = cs.get(c)
            q0 = co.getValue(s)
            co.setValue(s, q0 + h, False); lp = lengths()
            co.setValue(s, q0 - h, False); lm = lengths()
            co.setValue(s, q0, False)
            R[c][i] = -(lp - lm) / (2 * h)
        if exact:
            apply_couplers(); model.realizePosition(s)
            for c in free:
                co = cs.get(c)
                for k in exact:
                    if abs(R[c][i, k]) > 1e-6:
                        R[c][i, k] = mus[k].getGeometryPath().computeMomentArm(s, co)

    os.makedirs(out, exist_ok=True)
    write_sto(os.path.join(out, "_MuscleAnalysis_Length.sto"), T, mnames, L, "Length")
    for c in coords:
        write_sto(os.path.join(out, f"_MuscleAnalysis_MomentArm_{c}.sto"), T, mnames, R[c],
                  f"MomentArm_{c}")
    print(f"[fast MA] {len(T)} frames, {len(mus)} muscles, {len(coords)} coords: "
          f"{time.time()-t0:.1f} s -> {out}")


def read_sto(p):
    import pandas as pd
    with open(p) as f:
        n = next(i for i, l in enumerate(f) if l.strip() == "endheader")
    return pd.read_csv(p, sep="\t", skiprows=n + 1)


def compare(ref, new):
    import numpy as np
    worst = []
    for fn in sorted(os.listdir(new)):
        if not fn.endswith(".sto") or not os.path.exists(os.path.join(ref, fn)):
            continue
        a, b = read_sto(os.path.join(ref, fn)), read_sto(os.path.join(new, fn))
        cols = [c for c in b.columns if c != "time" and c in a.columns]
        bi = np.column_stack([np.interp(a["time"], b["time"], b[c]) for c in cols])
        d = np.abs(a[cols].to_numpy() - bi)
        scale = np.maximum(np.abs(a[cols].to_numpy()).max(0), 1e-3)
        k = int(np.argmax(d.max(0)))
        worst.append((d.max(), fn, cols[k], d.max(0)[k] / scale[k]))
        print(f"{fn:48s} max|diff| {d.max()*1000:7.3f} mm  (worst {cols[k]}, "
              f"{100*d.max(0)[k]/scale[k]:.2f} % of its peak)")
    print("-> OK" if worst and max(w[0] for w in worst) < 2e-3 else "-> check the worst ones")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("model", nargs="?"); ap.add_argument("ik", nargs="?")
    ap.add_argument("--out"); ap.add_argument("--coords", nargs="*")
    ap.add_argument("--min-wraps", type=int, default=2,
                    help="muscles with >= this many wrap objects use OpenSim's solver (99 = none)")
    ap.add_argument("--compare", nargs=2, metavar=("REF", "NEW"))
    a = ap.parse_args()
    if a.compare:
        compare(*a.compare)
    else:
        run(a.model, a.ik, a.out, a.coords, min_wraps=a.min_wraps)
