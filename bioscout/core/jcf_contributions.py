"""Muscle contributions to the joint contact force (JCF), by force superposition.

WHY IT WORKS
    At fixed kinematics the JointReaction analysis is LINEAR in the applied
    actuator forces, so the contact force of a joint decomposes EXACTLY:

        JCF_total(t) = JCF_base(t) + sum_g [ JCF_g(t) - JCF_base(t) ]

    JCF_base   = the analysis with every MUSCLE force zeroed, i.e. what gravity,
                 segment inertia, the GRF, the residuals and the reserves alone
                 push through the joint.
    JCF_g      = the analysis with ONLY muscle group g switched on.

    Cost: one JRA run per group + a baseline + a total (the total is re-run
    rather than read off disk so the closure check compares like with like).
    The check is written to the .sto header (closure=...) -- if it is not ~0 the decomposition
    is not trustworthy, so read it before quoting anything.

WHAT IS REPORTED  (per joint, per source, per frame)
    fx, fy, fz    the contribution VECTOR in the JRA frame (additive by
                  construction)
    along_total   its projection on the unit vector of the total JCF -- the
                  scalar contribution to the RESULTANT. Magnitudes are not
                  additive; this projection is, and it sums to |JCF_total|.

TRAPS
    * The residual / reserve / GRF columns stay in EVERY run. Strip them and the
      analysis cannot balance, the force blows up ~100x and stops depending on
      the muscle forces at all (see docs/JCF_CONTRIBUTIONS.md).
    * Always go through ``openSim.run_jra`` -- never hand-roll an AnalyzeTool.
"""
from __future__ import annotations

import os
import re
import shutil

import numpy as np
import pandas as pd


# ----------------------------------------------------------------- .sto io --

def _jra_engine():
    """OpenSim's run_jra, or pyosim's for iterations with ``engine: pyosim``. Read from
    the environment (set by Analyse.run_jra_contributions) so worker processes see it."""
    import os as _env_os
    if _env_os.environ.get("BIOSCOUT_JRA_ENGINE", "opensim").lower() == "pyosim":
        from bioscout.simulate import pyosim_backend as _m
    else:
        from bioscout.simulate import opensim as _m
    return _m

def read_sto(path):
    """(header lines, DataFrame). The header is kept verbatim so a rewritten
    forces file stays byte-compatible with what OpenSim already accepted."""
    header = []
    with open(path) as f:
        for line in f:
            header.append(line.rstrip("\n"))
            if line.strip().lower() == "endheader":
                break
        df = pd.read_csv(f, sep=r"\s+")
    return header, df


def write_sto(path, header, df):
    out = []
    for h in header:
        low = h.lower().replace(" ", "")
        if low.startswith("nrows"):
            h = f"nRows={df.shape[0]}"
        elif low.startswith("ncolumns"):
            h = f"nColumns={df.shape[1]}"
        out.append(h)
    with open(path, "w", newline="") as f:
        f.write("\n".join(out) + "\n")
        df.to_csv(f, sep="\t", index=False, float_format="%.8f")


# ------------------------------------------------------------- muscle sets --
def model_muscles(model_path):
    """Muscle names in the .osim (the ONLY columns that may be zeroed)."""
    if os.environ.get("BIOSCOUT_JRA_ENGINE", "opensim").lower() == "pyosim":
        from bioscout.pyosim.muscles import muscle_names       # a pyosim iteration never loads OpenSim
        return muscle_names(model_path)
    from bioscout.model.opensim_base import _quiet_model
    m = _quiet_model(model_path)
    ms = m.getMuscles()
    return [ms.get(i).getName() for i in range(ms.getSize())]


# settings.BatchSettings.MUSCLE_GROUPS covers the big movers only; these name
# the rest, so nothing important (psoas, tibialis posterior, the peroneals)
# disappears into one anonymous lump. Stems are matched with the _r/_l suffix.
EXTRA_GROUPS = {
    "Iliopsoas":          ["psoas", "iliacus"],
    "Adductors (l/b/gr)": ["addbrev", "addlong", "grac"],
    "Deep hip rotators":  ["piri", "obt_internus", "obt_externus", "quad_fem", "gem"],
    "Sartorius + TFL":    ["sart", "tfl"],
    "Tibialis posterior": ["tibpost"],
    "Tibialis anterior":  ["tibant"],
    "Peroneals":          ["perbrev", "perlong", "pertert"],
    "Toe flexors/ext":    ["fdl", "fhl", "edl", "ehl"],
}


def _expand_extras(cols):
    out = {}
    for name, stems in EXTRA_GROUPS.items():
        for side in ("r", "l"):
            members = [f"{st}_{side}" for st in stems if f"{st}_{side}" in cols]
            if members:
                out[f"{side.upper()} {name}"] = members
    return out


def build_groups(muscle_cols, groups=None, per_muscle=False):
    """name -> [columns]. settings.BatchSettings.MUSCLE_GROUPS, then EXTRA_GROUPS
    for what it does not cover, then one source per leftover muscle -- so every
    muscle is named and the decomposition closes."""
    cols = list(muscle_cols)
    if per_muscle:
        return {m: [m] for m in cols}
    if groups is None:
        try:
            from bioscout import utils as _u
            groups = getattr(_u.settings.BatchSettings, "MUSCLE_GROUPS", {}) or {}
        except Exception:
            groups = {}
    out, used = {}, set()
    for name, members in groups.items():
        present = [m for m in members if m in cols]
        if present:
            out[name] = present
            used.update(present)
    rest = [m for m in cols if m not in used]
    for name, members in _expand_extras(rest).items():
        out[name] = members
        used.update(members)
    for m in cols:                       # never lump the remainder: name it
        if m not in used:
            out[m] = [m]
    return out


_trapz = getattr(np, "trapezoid", None) or np.trapz


def _slug(name):
    return re.sub(r"[^A-Za-z0-9]+", "_", str(name)).strip("_")[:40]


# --------------------------------------------------------------- the core ---
def _so_force_set(forces_file, out_dir):
    """[actuators_so.xml] the trial's SO ran with, or None (2026-10-12).

    The reserves and residuals are NOT in the model; SO and the trial's own JRA
    load them from this force-set file. Without it every column of the forces
    file that is not a model muscle (the *_reserve, FX..MZ) is silently ignored,
    so the decomposition misses them and its total falls short of output_so.sto.
    """
    for d in (os.path.dirname(os.path.abspath(forces_file)),
              os.path.join(os.path.abspath(out_dir), "..", "..", "static_optimisation")):
        f = os.path.normpath(os.path.join(d, "actuators_so.xml"))
        if os.path.exists(f):
            return [f]
    return None


def _jra_task(args):
    """One JointReaction run in its own process (and its own working dir, so
    parallel runs never share a setup/forces/log file). Module-level so it
    pickles for ProcessPoolExecutor on Windows (spawn)."""
    (tag, keep, model_path, ik_file, grf_xml, forces_file, out_dir,
     setup_template, keep_sto, muscles, force_set) = args
    import os as _o, shutil as _sh
    header, forces = read_sto(forces_file)
    wdir = _o.path.join(out_dir, "_par", tag)
    _o.makedirs(wdir, exist_ok=True)
    tmp_forces = _o.path.join(wdir, "forces.sto")
    setup_xml = _o.path.join(wdir, "setup_JRA_contrib.xml")
    sto = _o.path.join(out_dir, f"JRA_{tag}.sto")
    f = forces.copy()
    f[[m for m in muscles if m not in keep]] = 0.0
    write_sto(tmp_forces, header, f)
    if setup_template and _o.path.exists(setup_template):
        _sh.copyfile(setup_template, setup_xml)
    _os = _jra_engine()
    if _os is None:                       # circular-import fallback
        from bioscout import utils as _u
        _os = _u.get_openSim()
    cwd = _o.getcwd()
    try:
        _o.chdir(wdir)
        _os.run_jra(osim_modelPath=model_path, ik_output=ik_file, grf_xml=grf_xml,
                    setup_xml=setup_xml, actuators=force_set,
                    muscle_force_path=tmp_forces, saveFileName=sto)
    finally:
        _o.chdir(cwd)
    try:
        _, d = read_sto(sto)
    except Exception as e:                # keep the run folder: its .log says why
        raise RuntimeError(f"JRA '{tag}' produced no data ({e}); see {wdir}") from None
    if not keep_sto:
        _o.remove(sto)
    _sh.rmtree(wdir, ignore_errors=True)
    return tag, d


def decompose(model_path, ik_file, grf_xml, forces_file, out_dir, jra_columns,
              groups=None, per_muscle=False, keep_sto=False, replace=False,
              setup_template=None, log=print, n_jobs=None, force_set="auto"):
    """Run the superposition and write `contributions.csv` + `closure.txt`.

    jra_columns: {"hip": [fx, fy, fz], "knee": [...], "ankle": [...]}
                 (settings.BatchSettings.JRA_COLUMNS(model, side))
    Returns the long DataFrame: time, joint, source, fx, fy, fz, along_total,
    total_mag.
    """
    # Callers pass paths relative to their own cwd (analysis.py chdirs into the
    # trial folder); the parallel workers run elsewhere, so pin everything down.
    model_path, ik_file, grf_xml, forces_file, out_dir = (
        os.path.abspath(x) for x in (model_path, ik_file, grf_xml, forces_file, out_dir))
    if setup_template:
        setup_template = os.path.abspath(setup_template)
    # Every JointReaction below reads a copy of this template. A missing one
    # used to be skipped in silence, and OpenSim then failed on each of the
    # 50+ runs with "Cannot open file ... setup_JRA_contrib.xml" -- naming the
    # copy, not the template that was never found.
    if not setup_template or not os.path.exists(setup_template):
        raise FileNotFoundError(
            f"JRA setup template not found: {setup_template} (the trial's "
            f"setup_dir has no setup_JRA.xml)")
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "contributions.csv")
    if os.path.exists(csv_path) and not replace:
        log(f"[contrib] SKIPPED — {csv_path} already exists "
            f"(pass --replace / replace=True to redo it)")
        return pd.read_csv(csv_path)

    import time as _time
    for _try in range(10):                 # a just-written file on a synced folder
        try:                               # can read empty for a moment
            header, forces = read_sto(forces_file)
            if len(forces.columns):
                break
        except Exception:
            if _try == 9:
                raise
        _time.sleep(1.0)
    muscles = [m for m in model_muscles(model_path) if m in forces.columns]
    if not muscles:
        raise ValueError(f"no model muscle columns in {forces_file}")
    gmap = build_groups(muscles, groups, per_muscle)
    setup_xml = os.path.join(out_dir, "setup_JRA_contrib.xml")
    # PID-tagged: two decompositions running on the same trial would otherwise
    # overwrite each other's forces file and silently produce garbage that still
    # looks like a result (only closure.txt catches it).
    tmp_forces = os.path.join(out_dir, f"_forces_{os.getpid()}.sto")

    def _jra(tag, keep):
        """JointReaction with only `keep` muscles active; everything that is not
        a muscle (residuals, reserves, GRF, torque actuators) is left alone."""
        sto = os.path.join(out_dir, f"JRA_{tag}.sto")
        f = forces.copy()
        off = [m for m in muscles if m not in keep]
        f[off] = 0.0
        write_sto(tmp_forces, header, f)
        if setup_template and os.path.exists(setup_template):
            shutil.copyfile(setup_template, setup_xml)
        _os = _jra_engine()
        _os.run_jra(osim_modelPath=model_path, ik_output=ik_file, grf_xml=grf_xml,
                    setup_xml=setup_xml, actuators=_fs,
                    muscle_force_path=tmp_forces, saveFileName=sto)
        _, d = read_sto(sto)
        if not keep_sto:
            os.remove(sto)
        return d

    # force_set: "auto" = the trial's SO actuators_so.xml (reserves/residuals as
    # actuators); None = no extra force set, as the CEINMS JRA itself runs
    # (2026-10-21) -- the decomposition must mirror the JRA it decomposes.
    _fs = _so_force_set(forces_file, out_dir) if force_set == "auto" else force_set
    # Workers read a private copy of the forces (2026-10-21): the original may
    # have JUST been rewritten (CEINMS: add_so_columns_to_ceinms_results), and on
    # a synced folder (ucloud/OneDrive) parallel readers then saw it empty --
    # "No columns to parse from file" with an empty work folder.
    forces_file = os.path.join(out_dir, "_forces_src.sto")
    write_sto(forces_file, header, forces)
    joints = {j: c for j, c in jra_columns.items()}
    if n_jobs is None:
        n_jobs = max(1, min((os.cpu_count() or 2) - 1,
                            int(os.environ.get("BIOSCOUT_JCF_JOBS", "8"))))
    _eng = _jra_engine()
    one_pass = hasattr(_eng, "run_jra_subsets")          # pyosim: every muscle set from one pass
    if one_pass:
        log(f"[contrib] {len(gmap)} groups + baseline + total = {len(gmap)+2} muscle sets, "
            f"one pyosim pass (the loads are linear in the muscle forces)")
    else:
        log(f"[contrib] {len(gmap)} groups + baseline + total = {len(gmap)+2} JRA runs"
            f"  (n_jobs={n_jobs})")

    results = {}
    if one_pass:
        sets = {"baseline": set(), "total": set(muscles)}
        sets.update({_slug(n): set(m) for n, m in gmap.items()})
        results = _eng.run_jra_subsets(model_path, ik_file, grf_xml, forces_file, sets)
        base, total = results["baseline"], results["total"]
    elif n_jobs > 1:
        # Every run is independent (superposition), so fan them ALL out at once.
        # Each worker gets its own working dir -- the shared-file hazard that
        # forbade two decompositions on one trial does not apply here.
        from concurrent.futures import ProcessPoolExecutor, as_completed
        tasks = [("baseline", set()), ("total", set(muscles))] + \
                [(_slug(n), set(m)) for n, m in gmap.items()]
        args = [(t, k, model_path, ik_file, grf_xml, forces_file, out_dir,
                 setup_template, keep_sto, muscles, _fs) for t, k in tasks]
        with ProcessPoolExecutor(max_workers=n_jobs) as ex:
            futs = {ex.submit(_jra_task, a): a[0] for a in args}
            done = 0
            for fu in as_completed(futs):
                tag, d = fu.result()
                results[tag] = d
                done += 1
                # progress every ~25 %, not one line per group/muscle
                _step = max(1, len(tasks) // 4)
                if done % _step == 0 or done == len(tasks):
                    log(f"[contrib] {done}/{len(tasks)} JRA runs done")
        base, total = results["baseline"], results["total"]
    else:
        base = _jra("baseline", set())
        total = _jra("total", set(muscles))
    missing = {j: [c for c in cc if c not in total.columns] for j, cc in joints.items()}
    joints = {j: cc for j, cc in joints.items() if not missing[j]}
    for j, m in missing.items():
        if m:
            log(f"[contrib] skipping {j}: columns not in the JRA output ({m[0]} ...)")

    time = total["time"].to_numpy()
    V = {j: np.column_stack([total[c].to_numpy() for c in cc]) for j, cc in joints.items()}
    B = {j: np.column_stack([base[c].to_numpy() for c in cc]) for j, cc in joints.items()}
    mag = {j: np.linalg.norm(V[j], axis=1) for j in joints}
    unit = {j: V[j] / np.where(mag[j] > 1e-9, mag[j], 1.0)[:, None] for j in joints}

    rows, closure = [], {j: B[j].copy() for j in joints}

    def _add(source, vec):
        for j in joints:
            v = vec[j]
            rows.append(pd.DataFrame(dict(
                time=time, joint=j, source=source,
                fx=v[:, 0], fy=v[:, 1], fz=v[:, 2],
                along_total=(v * unit[j]).sum(1), total_mag=mag[j])))

    _add("Non-muscle (gravity+GRF+residuals)", B)
    for name, members in gmap.items():
        d = results.get(_slug(name)) if results else None
        if d is None:
            d = _jra(_slug(name), set(members))
        c = {j: np.column_stack([d[x].to_numpy() for x in cc]) - B[j]
             for j, cc in joints.items()}
        for j in joints:
            closure[j] += c[j]
        _add(name, c)

    df = pd.concat(rows, ignore_index=True)
    df.to_csv(csv_path, index=False, float_format="%.6f")

    lines = ["source vector sum vs the total JRA (should be ~0)"]
    for j in joints:
        e = np.abs(closure[j] - V[j]).max()
        lines.append(f"{j:6s} max |sum - total| = {e:10.3f} N   "
                     f"({100*e/max(mag[j].max(), 1e-9):.4f} % of peak |JCF|)")
    txt = "\n".join(lines)
    df.attrs["closure"] = lines[1:]
    log("[contrib] " + txt.replace("\n", "\n[contrib] "))
    for p in (tmp_forces,):
        if os.path.exists(p):
            os.remove(p)
    return df


RESERVE_SOURCE = "Reserve actuators"
NONMUSCLE_SOURCE = "Non-muscle (gravity+GRF+residuals)"


def split_reserves(model_path, ik_file, grf_xml, forces_file, out_dir, jra_columns,
                   setup_template=None, replace=False, log=print,
                   reserve_pattern=r"_reserve$"):
    """Split the reserves out of the non-muscle baseline of an existing
    `contributions.csv` (2026-10-12).

    decompose() leaves every non-muscle column in every run, so its baseline row
    is gravity + GRF + residuals + RESERVES. One more JointReaction with the
    muscles AND the reserve columns zeroed gives B0, then
        Reserve actuators = B - B0          Non-muscle = B0
    The sum over sources is unchanged, so the closure stays exact. Residuals
    (FX..MZ) and GRF stay in -- zeroing those unbalances the analysis.

    jra_columns: {"hip_l": [fx, fy, fz], ...} as passed to decompose().
    Idempotent: skipped when the csv already has a reserve row (unless replace).
    """
    model_path, ik_file, grf_xml, forces_file, out_dir = (
        os.path.abspath(x) for x in (model_path, ik_file, grf_xml, forces_file, out_dir))
    csv_path = os.path.join(out_dir, "contributions.csv")
    if not os.path.exists(csv_path):
        log(f"[contrib] reserve split: no {csv_path}")
        return None
    df = pd.read_csv(csv_path)
    closure = df.attrs.get("closure")
    if RESERVE_SOURCE in set(df.source) and not replace:
        log("[contrib] reserve split: already done")
        return df
    header, forces = read_sto(forces_file)
    reserves = [c for c in forces.columns if re.search(reserve_pattern, c)]
    if not reserves:
        log("[contrib] reserve split: no reserve columns in the forces file")
        return df
    if not _so_force_set(forces_file, out_dir):
        log("[contrib] reserve split: no actuators_so.xml next to the forces -- the "
            "reserves are not in the model, so JRA would ignore them; skipped")
        return df
    muscles = [m for m in model_muscles(model_path) if m in forces.columns]
    wdir = os.path.join(out_dir, "_par", "no_reserve")
    os.makedirs(wdir, exist_ok=True)
    tmp = os.path.join(wdir, "forces.sto")
    setup_xml = os.path.join(wdir, "setup_JRA_contrib.xml")
    sto = os.path.join(wdir, "JRA_no_reserve.sto")
    f = forces.copy()
    f[muscles + reserves] = 0.0
    write_sto(tmp, header, f)
    if setup_template and os.path.exists(setup_template):
        shutil.copyfile(os.path.abspath(setup_template), setup_xml)
    _os = _jra_engine()
    cwd = os.getcwd()
    try:
        os.chdir(wdir)
        _os.run_jra(osim_modelPath=model_path, ik_output=ik_file, grf_xml=grf_xml,
                    setup_xml=setup_xml, actuators=_so_force_set(forces_file, out_dir),
                    muscle_force_path=tmp, saveFileName=sto)
    finally:
        os.chdir(cwd)
    _, d0 = read_sto(sto)
    shutil.rmtree(wdir, ignore_errors=True)

    t0 = d0["time"].to_numpy()
    base_rows = df.source.isin([NONMUSCLE_SOURCE, RESERVE_SOURCE])   # a re-split folds back first
    rows, done = [], set()
    for j, g in df.groupby("joint", sort=False):
        cc = jra_columns.get(j)
        if not cc or not all(c in d0.columns for c in cc):
            log(f"[contrib] reserve split: {j} not in the JRA output -- left as is")
            continue
        b = g[g.source.isin([NONMUSCLE_SOURCE, RESERVE_SOURCE])].groupby("time")[["fx", "fy", "fz"]].sum()
        tt = b.index.to_numpy()
        tot = g.groupby("time").total_mag.first().loc[tt].to_numpy()
        u = g.groupby("time")[["fx", "fy", "fz"]].sum().loc[tt].to_numpy()   # = total JCF vector
        u = u / np.where(tot > 1e-9, tot, 1.0)[:, None]
        b0 = np.column_stack([np.interp(tt, t0, d0[c].to_numpy()) for c in cc])
        for src, v in ((NONMUSCLE_SOURCE, b0), (RESERVE_SOURCE, b.to_numpy() - b0)):
            rows.append(pd.DataFrame(dict(time=tt, joint=j, source=src,
                                          fx=v[:, 0], fy=v[:, 1], fz=v[:, 2],
                                          along_total=(v * u).sum(1), total_mag=tot)))
        done.add(j)
    out = pd.concat([df[~(base_rows & df.joint.isin(done))]] + rows, ignore_index=True)
    out.to_csv(csv_path, index=False, float_format="%.6f")
    out.attrs["closure"] = closure
    r = out[out.source == RESERVE_SOURCE]
    log("[contrib] reserve split, peak |reserve along JCF| (N): " +
        ", ".join(f"{j} {r[r.joint == j].along_total.abs().max():.0f}" for j in sorted(done)))
    return out


# --------------------------------------------------------------- reporting --
def summarise(df, body_weight=None):
    """One row per joint x source: the contribution at the frame of PEAK total
    JCF, its own peak, and its impulse. In BW when body_weight (N) is given."""
    s = 1.0 / body_weight if body_weight else 1.0
    out = []
    for j, d in df.groupby("joint"):
        t_peak = d.loc[d.total_mag.idxmax(), "time"]
        for src, g in d.groupby("source"):
            g = g.sort_values("time")
            at = float(g.loc[(g.time - t_peak).abs().idxmin(), "along_total"])
            out.append(dict(joint=j, source=src, unit=("BW" if body_weight else "N"),
                            at_peak=at * s,
                            peak=float(g.along_total.max()) * s,
                            impulse=float(_trapz(g.along_total, g.time)) * s,
                            pct_of_peak=100 * at / max(g.total_mag.max(), 1e-9)))
    return pd.DataFrame(out).sort_values(["joint", "at_peak"], ascending=[True, False])


def load_measured_jcf(path, side="r"):
    """In-vivo JCF from an instrumented implant (OrthoLoad) as
    {"<joint>_<side>": (time, |F| in N)} -- ready to hand to
    ``plot_contribution_curves(measured=...)``.

    Uses the ``<joint>_measured_f`` magnitude column written by
    orthoload_to_bioscout, else builds the magnitude from
    ``<joint>_measured_f{x,y,z}``. The instrumented side is NOT in the file --
    pass it (OrthoLoad trial ids carry it: `h9l_...` = left)."""
    _, d = read_sto(path)
    t = d["time"].to_numpy(float)
    out = {}
    for j in sorted({c.split("_measured")[0] for c in d.columns if "_measured_f" in c}):
        if f"{j}_measured_f" in d.columns:
            v = d[f"{j}_measured_f"].to_numpy(float)
        else:
            cc = [f"{j}_measured_f{a}" for a in "xyz"]
            if not all(c in d.columns for c in cc):
                continue
            v = np.linalg.norm(d[cc].to_numpy(float), axis=1)
        out[f"{j}_{side}"] = (t, v)
    return out


BASELINE = "Non-muscle (gravity+GRF+residuals)"

# Line weights: the contact forces are the subject of the figure, the per-source
# contributions are the supporting detail.
_LW_JCF = 2.4
_LW_SOURCE = 1.2

# Canonical source order -> a FIXED colour, so a muscle keeps the same colour in
# every panel, every figure and every trial, and left/right share it. Order
# follows MUSCLE_GROUPS then EXTRA_GROUPS; adding a name at the END is safe,
# inserting one in the middle recolours everything after it.
_CANON = [
    "Gluteus maximus", "Gluteus medius", "Gluteus minimus", "Adductor Magnus",
    "Biceps Femoris", "Semimembranosus", "Semitendinosus", "Rectus Femoris",
    "Vasti", "Triceps Surae", "Iliopsoas", "Adductors (l/b/gr)",
    "Deep hip rotators", "Sartorius + TFL", "Tibialis posterior",
    "Tibialis anterior", "Peroneals", "Toe flexors/ext",
]


def _palette():
    """Saturated colours FIRST — thin lines need them. tab20's strong half (its
    grey dropped, that is reserved for the pooled "other"), then tab20b, then
    tab20's pale half only once those run out."""
    import matplotlib.pyplot as plt
    strong = [c for i, c in enumerate(plt.cm.tab20.colors) if i % 2 == 0 and i != 14]
    pale = [c for i, c in enumerate(plt.cm.tab20.colors) if i % 2 == 1 and i != 15]
    return strong + list(plt.cm.tab20b.colors) + pale


def source_color(name):
    """Stable colour for one contribution source. Side-independent ("R Vasti"
    and "L Vasti" match), fixed across figures, grey for the pooled remainder
    and dark grey for the non-muscle baseline."""
    import zlib
    s = str(name)
    base = re.sub(r"^[RL]\s+", "", s)
    if s == BASELINE or base.startswith("Non-muscle"):
        return "#3d3d3d"
    if base.lower() == "other":
        return "#b3b3b3"
    pal = _palette()
    i = _CANON.index(base) if base in _CANON else \
        len(_CANON) + zlib.crc32(base.encode()) % (len(pal) - len(_CANON))
    return pal[i % len(pal)]


def _grid(joints, ncols=3):
    """Lay joints out as JOINT rows x SIDE columns when they are keyed
    "<joint>_<side>"; otherwise a plain `ncols`-wide wrapped grid.
    Returns (grid, column titles or None)."""
    ORDER = ["hip", "knee", "ankle"]
    SIDES = [("r", "right"), ("l", "left")]
    sided = {j: (j.rsplit("_", 1)[0], j.rsplit("_", 1)[1]) for j in joints
             if "_" in j and j.rsplit("_", 1)[1] in ("r", "l")}
    if joints and len(sided) == len(joints):
        rows = [j for j in ORDER if any(b == j for b, _ in sided.values())]
        rows += sorted({b for b, _ in sided.values()} - set(rows))
        cols = [sd for sd, _ in SIDES if any(x == sd for _, x in sided.values())]
        grid = [[next((j for j, (b, x) in sided.items() if b == r and x == c), None)
                 for c in cols] for r in rows]
        return grid, [dict(SIDES)[c] for c in cols]
    nc = min(ncols, max(len(joints), 1))
    grid = [joints[i:i + nc] for i in range(0, len(joints), nc)] or [[None]]
    grid[-1] += [None] * (nc - len(grid[-1]))
    return grid, None


def _panel_name(j, col_title):
    return f"{col_title} {j.rsplit('_', 1)[0]}" if col_title else j


def plot_contributions(df, save=None, body_weight=None, title=None, top=12, ncols=3):
    """Per joint, each source's contribution at the frame of peak JCF.
    Joint rows x side columns when the joints are keyed "<joint>_<side>"."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    s = summarise(df, body_weight)
    unit = "BW" if body_weight else "N"
    peak = df.groupby("joint").total_mag.max() / (body_weight or 1.0)
    grid, col_titles = _grid(list(dict.fromkeys(s.joint)), ncols)
    nr, nc = len(grid), len(grid[0])
    fig, axes = plt.subplots(nr, nc, figsize=(5.4 * nc, 0.30 * top * nr + 1.4),
                             squeeze=False)
    for r, row in enumerate(grid):
        for c, j in enumerate(row):
            ax = axes[r][c]
            if j is None:
                ax.set_axis_off()
                continue
            d = s[s.joint == j].head(top).iloc[::-1]
            # same colour per muscle as the curve figure; a NEGATIVE (unloading)
            # contribution keeps its colour but is hatched, so the sign is not
            # carried by colour alone
            bars = ax.barh(d.source, d.at_peak,
                           color=[source_color(x) for x in d.source])
            for b, v in zip(bars, d.at_peak):
                if v < 0:
                    b.set_hatch("///")
                    b.set_edgecolor("white")
            ax.set_title(f"{_panel_name(j, col_titles and col_titles[c])}"
                         f"   peak |JCF| = {peak[j]:.2f} {unit}", fontsize=10)
            ax.axvline(0, color="k", lw=.8)
            ax.tick_params(labelsize=8)
            if r == nr - 1:
                ax.set_xlabel(f"contribution at peak JCF [{unit}]", fontsize=8)
    fig.suptitle(title or "Muscle contributions to joint contact force")
    fig.tight_layout()
    if save:
        fig.savefig(save, dpi=150)
        plt.close(fig)
    return fig


def plot_contribution_curves(df, save=None, body_weight=None, title=None, top=6,
                             ncols=3, stacked=False, xnorm=False, measured=None):
    """Each source's contribution to the total JCF OVER TIME, one panel per
    joint (joint rows x side columns).

    Curves are `along_total` — the projection on the total-JCF direction — so
    they add up to the black |JCF| line at every instant. `top` sources per
    panel are named (ranked by peak contribution); the rest are pooled into a
    thin grey "other" line so the panel still sums to the total.
    stacked=True draws them as a filled stack instead of lines (negative
    contributions then sit below zero and the stack top no longer meets the
    total line — read the lines when that matters).
    xnorm=True puts the x axis in % of the trial instead of seconds.
    measured: {joint_key: (time, |F| in N)} -- e.g. an instrumented implant's
    in-vivo JCF from :func:`load_measured_jcf` -- drawn as a dashed reference.
    It is a MEASUREMENT of the same joint, not one of the sources, so it is
    deliberately NOT part of the sum."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    sc = 1.0 / body_weight if body_weight else 1.0
    unit = "BW" if body_weight else "N"
    grid, col_titles = _grid(list(dict.fromkeys(df.joint)), ncols)
    nr, nc = len(grid), len(grid[0])
    fig, axes = plt.subplots(nr, nc, figsize=(6.0 * nc, 3.2 * nr), squeeze=False,
                             sharex=True)
    for r, row in enumerate(grid):
        for c, j in enumerate(row):
            ax = axes[r][c]
            if j is None:
                ax.set_axis_off()
                continue
            d = df[df.joint == j]
            w = d.pivot_table(index="time", columns="source", values="along_total")
            tot = d.groupby("time").total_mag.first().reindex(w.index) * sc
            w = w * sc
            rank = w.abs().max().sort_values(ascending=False)
            named = list(rank.index[:top])
            other = [x for x in w.columns if x not in named]
            x = np.linspace(0, 100, len(w)) if xnorm else w.index.to_numpy()
            colors = [source_color(n) for n in named]
            if stacked:
                ax.stackplot(x, *[w[n].to_numpy() for n in named],
                             labels=named, colors=colors, alpha=.85)
                if other:
                    ax.plot(x, w[other].sum(1), color=source_color("other"),
                            lw=_LW_SOURCE, label="other")
            else:
                for n, col in zip(named, colors):
                    ax.plot(x, w[n].to_numpy(), lw=_LW_SOURCE, color=col, label=n)
                if other:
                    ax.plot(x, w[other].sum(1), color=source_color("other"),
                            lw=_LW_SOURCE, label="other")
            # the JCF traces sit ON TOP and are the heavy lines: the sources are
            # the detail, the contact force is the thing being explained
            ax.plot(x, tot.to_numpy(), color="k", lw=_LW_JCF, zorder=5,
                    label="|JCF| total")
            mv = None
            mref = (measured or {}).get(j)
            if mref is not None:
                mt, mv = np.asarray(mref[0], float), np.asarray(mref[1], float) * sc
                ax.plot(np.linspace(0, 100, len(mt)) if xnorm else mt, mv,
                        color="#7030a0", lw=_LW_JCF, ls="--", zorder=5,
                        label="measured (in vivo)")
            ax.axhline(0, color="k", lw=.6)
            ax.set_title(_panel_name(j, col_titles and col_titles[c]), fontsize=10)
            ax.set_ylabel(f"contribution [{unit}]", fontsize=8)
            ax.tick_params(labelsize=8)
            # headroom so the legend never sits on top of the curves
            _lo = float(min(w.min().min(), 0.0)); _hi = float(max(tot.max(), w.max().max()))
            if mv is not None and len(mv):
                _lo = min(_lo, float(np.nanmin(mv))); _hi = max(_hi, float(np.nanmax(mv)))
            ax.set_ylim(_lo - 0.05 * (_hi - _lo), _hi + 0.42 * (_hi - _lo))
            ax.legend(fontsize=6, ncol=2, loc="upper left", framealpha=.85)
            if r == nr - 1:
                ax.set_xlabel("% of trial" if xnorm else "time [s]", fontsize=8)
    fig.suptitle(title or "Muscle contributions to joint contact force over time")
    fig.tight_layout()
    if save:
        fig.savefig(save, dpi=150)
        plt.close(fig)
    return fig


# ------------------------------------------------ contributions_<t>.sto io --
# One wide OpenSim storage per trial instead of a folder (2026-10-12):
#   time | <joint>/<src>/fx|fy|fz|along ... | <joint>/total_mag
# <src> is the source name with spaces -> "_"; the exact names, the body
# weight and the closure check live in the header.
def write_contributions_sto(df, path, body_weight=None, closure=None):
    names = list(dict.fromkeys(df.source))
    key = {n: re.sub(r"\s+", "_", str(n)) for n in names}
    # build all columns, then ONE concat (a join/insert per column fragmented the
    # frame and flooded the log with PerformanceWarnings, 2026-10-16)
    parts = []
    for (j, n), g in df.groupby(["joint", "source"], sort=False):
        g = g.sort_values("time").set_index("time")
        parts.append(pd.DataFrame({f"{j}/{key[n]}/{c}": g[c if c != "along" else "along_total"]
                                   for c in ("fx", "fy", "fz", "along")}))
    for j, g in df.groupby("joint", sort=False):
        parts.append(g.drop_duplicates("time").set_index("time").total_mag
                     .rename(f"{j}/total_mag").to_frame())
    wide = pd.concat(parts, axis=1).sort_index()
    wide.index.name = "time"
    wide = wide.reset_index()
    header = [os.path.basename(path), "version=1", f"nRows={wide.shape[0]}",
              f"nColumns={wide.shape[1]}", "inDegrees=no", "units=N",
              f"body_weight_N={body_weight if body_weight else ''}"]
    header += [f"source={key[n]}={n}" for n in names]
    header += [f"closure={l}" for l in (closure or [])]
    header.append("endheader")
    with open(path, "w", newline="") as f:
        f.write("\n".join(header) + "\n")
        wide.to_csv(f, sep="\t", index=False, float_format="%.6f")
    return path


def read_contributions(path):
    """contributions_<t>.sto -> (long DataFrame as decompose() returns, body
    weight in N or None). Also accepts a legacy contributions.csv."""
    if str(path).lower().endswith(".csv"):
        return pd.read_csv(path), None
    header, wide = read_sto(path)
    names, bw = {}, None
    for h in header:
        if h.startswith("source="):
            k, n = h[len("source="):].split("=", 1)
            names[k] = n
        elif h.startswith("body_weight_N="):
            v = h.split("=", 1)[1].strip()
            bw = float(v) if v else None
    t = wide["time"].to_numpy()
    rows = []
    cols = [c for c in wide.columns if c.count("/") == 2]
    for (j, k) in dict.fromkeys(tuple(c.split("/")[:2]) for c in cols):
        rows.append(pd.DataFrame(dict(
            time=t, joint=j, source=names.get(k, k.replace("_", " ")),
            fx=wide[f"{j}/{k}/fx"], fy=wide[f"{j}/{k}/fy"], fz=wide[f"{j}/{k}/fz"],
            along_total=wide[f"{j}/{k}/along"], total_mag=wide[f"{j}/total_mag"])))
    return pd.concat(rows, ignore_index=True), bw


# ------------------------------------------------- stacked |JCF| figure --
# After Fig. 5 of doi:10.1038/s41598-022-13386-9 and actuators_so/plot.py
# fig9_jcf_stack: who carries the contact force, stacked to |JCF|.
STACK_GROUPS = {   # paper group -> group-name stems (side prefix stripped, lower case)
    "Adductors": ["hip adductors", "adductors (l/b/gr)", "adductor magnus"],
    "Gluteus maximus": ["glut max", "gluteus maximus"],
    "Gluteus med+min": ["hip abductors", "gluteus medius", "gluteus minimus"],
    "Hamstrings": ["hamstrings", "biceps femoris", "semimembranosus", "semitendinosus"],
    "Iliopsoas": ["hip flexors", "iliopsoas"],
    "Rectus femoris": ["rectus femoris"],
    "Triceps surae": ["gastrocnemius", "soleus", "triceps surae"],
    "Vasti": ["vasti"],
}
# per_muscle=True runs name single muscles -> match by muscle-name prefix
STACK_MUSCLE_PREFIX = {
    "Adductors": ["addbrev", "addlong", "addmag"], "Gluteus maximus": ["glmax"],
    "Gluteus med+min": ["glmed", "glmin"],
    "Hamstrings": ["bflh", "bfsh", "semimem", "semiten"], "Iliopsoas": ["iliacus", "psoas"],
    "Rectus femoris": ["recfem"], "Triceps surae": ["soleus", "gaslat", "gasmed"],
    "Vasti": ["vasint", "vaslat", "vasmed"],
}
STACK_ORDER = ["Intersegmental"] + list(STACK_GROUPS) + ["Other muscles", "Other leg (lumped)",
                                                         "Reserve actuators"]


def stack_group(source):
    """Contribution source -> one of STACK_ORDER."""
    s = str(source)
    if s == BASELINE or s.startswith("Non-muscle"):
        return "Intersegmental"
    if s == RESERVE_SOURCE:
        return "Reserve actuators"
    base = re.sub(r"^[RL]\s+", "", s).strip().lower()
    if base == "other leg":
        return "Other leg (lumped)"
    for g, stems in STACK_GROUPS.items():
        if base in stems:
            return g
    for g, pre in STACK_MUSCLE_PREFIX.items():
        if any(base.startswith(p) for p in pre):
            return g
    return "Other muscles"


def _stack_colors():
    """Fixed, qualitative colours (Okabe-Ito based, colour-blind safe) -- one
    clearly different hue per group; same dict as actuators_so/plot.py."""
    return dict({"Intersegmental": "#b8a27a", "Adductors": "#2bb5c0", "Gluteus maximus": "#a266b1",
             "Gluteus med+min": "#5d8cb3", "Hamstrings": "#6b2f73", "Iliopsoas": "#dd7036",
             "Rectus femoris": "#2f6b43", "Triceps surae": "#a41e23", "Vasti": "#6cc070",
             "Other muscles": "0.8", "Reserve actuators": "0.35", "Other leg (lumped)": "#c9d6c3"})


def plot_contribution_stack(df, save=None, body_weight=None, title=None, n_points=101,
                            measured=None):
    """Stacked contributions to |JCF| for ONE trial: rows = hip / knee / ankle,
    columns = left | right (left on the left); x = % trial, y = BW (N without body_weight).
    Uses the along-|JCF| projection, which is additive, so the stack tops out
    at |JCF| (black line); parts pulling against the resultant go below 0.
    ``measured`` = {"<joint>_<side>": (time, |F| N)} (load_measured_jcf): the in-vivo
    JCF, drawn red dashed on its panel over the same time window (2026-10-15)."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    s = 1.0 / body_weight if body_weight else 1.0
    unit = "BW" if body_weight else "N"
    d = df.assign(group=df.source.map(stack_group))
    t0, t1 = float(d.time.min()), float(d.time.max())
    xg = np.linspace(0, 100, n_points)

    def _interp(t, v):
        x = 100 * (np.asarray(t, float) - t0) / max(t1 - t0, 1e-12)
        return np.interp(xg, x, np.asarray(v, float))

    grid, col_titles = _grid(sorted(d.joint.unique()))
    # joint rows x side columns, LEFT side in the left column (2026-10-16)
    if col_titles:
        _ix = sorted(range(len(col_titles)), key=lambda i: col_titles[i] != "left")
        grid = [[r[i] for i in _ix] for r in grid]
        col_titles = [col_titles[i] for i in _ix]
    rows = grid
    joint_names = [next((j for j in r if j), "").rsplit("_", 1)[0] for r in grid] \
        if col_titles else [None] * len(rows)
    col = _stack_colors()
    hatch = {"Reserve actuators": "///"}
    nr, nc = len(rows), len(rows[0]) if rows else 1
    fig, ax = plt.subplots(nr, nc, figsize=(4.6 * nc, 2.2 * nr + 1.6), squeeze=False,
                           sharex=True, sharey="row")
    used = set()
    for r, row in enumerate(rows):
        for c, j in enumerate(row):
            a = ax[r][c]
            if j is None:
                a.set_visible(False)
                continue
            g = d[d.joint == j]
            per = g.groupby(["group", "time"]).along_total.sum()
            pos = np.zeros_like(xg)
            neg = np.zeros_like(xg)
            for grp in STACK_ORDER:
                if grp not in per.index.get_level_values(0):
                    continue
                y = per.loc[grp]
                v = _interp(y.index, y.values) * s
                if not np.any(np.abs(v) > 0):
                    continue
                used.add(grp)
                p, n = np.clip(v, 0, None), np.clip(v, None, 0)
                kw = dict(color=col[grp], lw=0, hatch=hatch.get(grp),
                          edgecolor="white" if grp in hatch else None)
                a.fill_between(xg, pos, pos + p, **kw)
                a.fill_between(xg, neg, neg + n, **kw)
                pos, neg = pos + p, neg + n
            tot = g.drop_duplicates("time").sort_values("time")
            a.plot(xg, _interp(tot.time, tot.total_mag) * s, color="k", lw=1.1)
            if measured and j in measured:
                mt, mv = (np.asarray(x, float) for x in measured[j])
                tg = t0 + xg / 100.0 * (t1 - t0)
                ok = (tg >= mt.min()) & (tg <= mt.max())
                if ok.any():
                    a.plot(xg[ok], np.interp(tg[ok], mt, mv) * s, color="#d62728",
                           lw=1.6, ls="--", zorder=20)
                    used.add("__invivo__")
            a.axhline(0, color="0.4", lw=0.5)
            a.spines[["top", "right"]].set_visible(False)
            a.set_xlim(0, 100)
            a.tick_params(labelsize=7)
            if r == 0 and col_titles:
                a.set_title(col_titles[c], fontweight="bold", fontsize=11)
            if c == 0:
                jn = joint_names[r] if col_titles else j
                a.set_ylabel(f"{jn} ({unit})", fontsize=9, fontweight="bold")
            elif not col_titles:
                a.set_title(j, fontsize=9)
            if r == nr - 1:
                a.set_xlabel("% trial")
    if title:
        fig.suptitle(title, fontweight="bold")
    order = [grp for grp in STACK_ORDER if grp in used]
    h = [Patch(facecolor=col[grp], hatch=hatch.get(grp),
               edgecolor="white" if grp in hatch else col[grp], label=grp) for grp in order]
    h.append(Line2D([], [], color="k", lw=1.1, label="|JCF|"))
    if "__invivo__" in used:
        h.append(Line2D([], [], color="#d62728", lw=1.6, ls="--", label="in vivo |JCF|"))
    # legend never wider than the figure (2026-10-15): columns from the figure
    # width (~1.9 in each), title wrapped to the same width
    import textwrap as _tw
    _fw = fig.get_size_inches()[0]
    _nc = max(2, min(len(h), int(_fw // 1.9)))
    _nrow = -(-len(h) // _nc)
    _ttl = "\n".join(_tw.wrap("contribution = projection on the total JCF (sums to |JCF|); "
                              "below 0 = pulls against it", width=int(_fw * 11)))
    fig.legend(handles=h, loc="lower center", ncol=_nc, frameon=False, fontsize=8,
               title_fontsize=8, title=_ttl)
    fig.tight_layout(rect=(0, (0.45 + 0.22 * _nrow + 0.15 * _ttl.count(chr(10))) / fig.get_size_inches()[1], 1, 0.97))
    if save:
        fig.savefig(save, dpi=170)
        plt.close(fig)
    return fig


def _measured_for(sto):
    """In-vivo JCF for a contributions_<t>.sto in the bioscout layout
    <session>/3_iterations/<it>/<trial>/joint_contact_forces/: reads
    <session>/2_experimental/<trial>/invivo_jcf.mot, side = session.yaml
    measured_side. None when there is no implant data."""
    try:
        jcf = os.path.dirname(os.path.abspath(sto))
        trial = os.path.basename(os.path.dirname(jcf))
        ses = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(jcf))))
        f = os.path.join(ses, "2_experimental", trial, "invivo_jcf.mot")
        if not os.path.exists(f):
            return None
        side = "r"
        y = os.path.join(ses, "session.yaml")
        if os.path.exists(y):
            import yaml
            with open(y, encoding="utf-8") as fh:
                c = yaml.safe_load(fh) or {}
            side = str(c.get("measured_side") or c.get("implanted_side") or "r").lower()[:1]
        return load_measured_jcf(f, side=side)
    except Exception:                                    # noqa: BLE001
        return None


def plot_contribution_stacks(root, body_weight=None, replace=True, log=print):
    """Draw plot_contribution_stack for every contributions_<t>.sto under `root`
    (one .sto, a trial folder or a whole session); each figure is saved as the
    .sto's stem + .png next to it. Returns the list of figures written."""
    root = os.path.abspath(root)
    pat = re.compile(r"^contributions_\w+\.sto$", re.I)
    if os.path.isfile(root):
        hits = [root]
    else:
        hits = []
        for dp, dn, fn in os.walk(root):
            dn[:] = [x for x in dn if not x.startswith(("_", "."))]
            hits += [os.path.join(dp, f) for f in fn if pat.match(f)]
    done = []
    for sto in sorted(hits):
        out = os.path.splitext(sto)[0] + ".png"
        if os.path.exists(out) and not replace:
            continue
        try:
            df, bw = read_contributions(sto)
            parts = os.path.normpath(sto).split(os.sep)
            trial = parts[-3] if len(parts) >= 3 else ""
            kind = os.path.splitext(parts[-1])[0].replace("contributions_", "").upper()
            plot_contribution_stack(df, save=out, body_weight=body_weight or bw,
                                    title=f"{trial} - {kind} contributions to the joint contact force",
                                    measured=_measured_for(sto))
            done.append(out)
            log(f"[stack] {out}")
        except Exception as e:
            log(f"[stack] FAILED {sto}: {e}")
    if not done:
        log(f"[stack] nothing drawn under {root}")
    return done


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Stacked |JCF| contribution figure per trial")
    ap.add_argument("root", help="contributions_<t>.sto, a trial folder or a session folder")
    ap.add_argument("--bw", type=float, default=None, help="body weight in N (default: from the .sto header)")
    a = ap.parse_args()
    import matplotlib
    matplotlib.use("Agg")
    plot_contribution_stacks(a.root, body_weight=a.bw)
