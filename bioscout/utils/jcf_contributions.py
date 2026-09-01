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
    The check is written to `closure.txt` -- if it is not ~0 the decomposition
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
    try:
        from .openSim import _quiet_model
        m = _quiet_model(model_path)
    except Exception:
        import opensim as osim
        m = osim.Model(model_path)
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
def _jra_task(args):
    """One JointReaction run in its own process (and its own working dir, so
    parallel runs never share a setup/forces/log file). Module-level so it
    pickles for ProcessPoolExecutor on Windows (spawn)."""
    (tag, keep, model_path, ik_file, grf_xml, forces_file, out_dir,
     setup_template, keep_sto, muscles) = args
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
    from bioscout.utils import openSim as _os
    if _os is None:                       # circular-import fallback
        from bioscout import utils as _u
        _os = _u.get_openSim()
    cwd = _o.getcwd()
    try:
        _o.chdir(wdir)
        _os.run_jra(osim_modelPath=model_path, ik_output=ik_file, grf_xml=grf_xml,
                    setup_xml=setup_xml, actuators=None,
                    muscle_force_path=tmp_forces, saveFileName=sto)
    finally:
        _o.chdir(cwd)
    _, d = read_sto(sto)
    if not keep_sto:
        _o.remove(sto)
    _sh.rmtree(wdir, ignore_errors=True)
    return tag, d


def decompose(model_path, ik_file, grf_xml, forces_file, out_dir, jra_columns,
              groups=None, per_muscle=False, keep_sto=False, replace=False,
              setup_template=None, log=print, n_jobs=None):
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
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "contributions.csv")
    if os.path.exists(csv_path) and not replace:
        log(f"[contrib] SKIPPED — {csv_path} already exists "
            f"(pass --replace / replace=True to redo it)")
        return pd.read_csv(csv_path)

    header, forces = read_sto(forces_file)
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
        from bioscout.utils import openSim as _os
        _os.run_jra(osim_modelPath=model_path, ik_output=ik_file, grf_xml=grf_xml,
                    setup_xml=setup_xml, actuators=None,
                    muscle_force_path=tmp_forces, saveFileName=sto)
        _, d = read_sto(sto)
        if not keep_sto:
            os.remove(sto)
        return d

    joints = {j: c for j, c in jra_columns.items()}
    if n_jobs is None:
        n_jobs = max(1, min((os.cpu_count() or 2) - 1,
                            int(os.environ.get("BIOSCOUT_JCF_JOBS", "8"))))
    log(f"[contrib] {len(gmap)} groups + baseline + total = {len(gmap)+2} JRA runs"
        f"  (n_jobs={n_jobs})")

    results = {}
    if n_jobs > 1:
        # Every run is independent (superposition), so fan them ALL out at once.
        # Each worker gets its own working dir -- the shared-file hazard that
        # forbade two decompositions on one trial does not apply here.
        from concurrent.futures import ProcessPoolExecutor, as_completed
        tasks = [("baseline", set()), ("total", set(muscles))] + \
                [(_slug(n), set(m)) for n, m in gmap.items()]
        args = [(t, k, model_path, ik_file, grf_xml, forces_file, out_dir,
                 setup_template, keep_sto, muscles) for t, k in tasks]
        with ProcessPoolExecutor(max_workers=n_jobs) as ex:
            futs = {ex.submit(_jra_task, a): a[0] for a in args}
            done = 0
            for fu in as_completed(futs):
                tag, d = fu.result()
                results[tag] = d
                done += 1
                log(f"[contrib] {done}/{len(tasks)} {tag}")
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
    open(os.path.join(out_dir, "closure.txt"), "w").write(txt + "\n")
    log("[contrib] " + txt.replace("\n", "\n[contrib] "))
    for p in (tmp_forces,):
        if os.path.exists(p):
            os.remove(p)
    return df


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
