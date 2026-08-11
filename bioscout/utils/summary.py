"""
BioScout — Summary module
==========================

Kinematics / kinetics / muscle summaries for processed trials.

Columns = joint DOFs (left + right share a column; left = red, right = blue).
Rows (configurable via ``settings.SummarySettings.rows``):

    1. Joint angle    (IK; per-joint per-side mean marker error box)
    2. EMG            (filtered-normalised; channels mapped to the joint muscles)
    3. Joint moment   (ID) + summed muscle moment (SO / CEINMS)
    4. Moment arms    (mean of +MA and -MA muscles acting on the coordinate)
    5. Muscle forces  (mean of the same +MA / -MA muscle groups)
    6. Activations    (mean of the same groups; EMG envelope shaded behind)
    7. Energetics     (mean metabolic rate of the same groups, if available)

Every panel carries a small legend; missing data leaves a "no data" panel.

CLI (wired in __main__.py):
    python -m bioscout --summary                       # ./settings.py if present
    python -m bioscout --summary "<proj>/settings.py"  # that project's settings
    python -m bioscout --summary "<...>/SomeTrial"      # ONE trial only (fast)
    python -m bioscout --summary -t "<...>/SomeTrial"   # ONE trial only (explicit)
    python -m bioscout --summary -overall               # overall only
    python -m bioscout --summary -s 012                 # one subject
"""

import os
import re
import sys
import glob
import traceback
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

import settings as _pkg_settings
import utils

try:
    from utils import openSim as _openSim
except Exception:
    _openSim = getattr(utils, "openSim", None)


_ACTIVE = _pkg_settings

ROW_LABELS = {
    "angle": "Angle (deg)",
    "emg": "EMG",
    "moment": "Moment (Nm)",
    "moment_arms": "Moment arm (m)",
    "muscle_forces": "Muscle force (N)",
    "activations": "Activation",
    "energetics": "Metab. rate (W)",
}
DEFAULT_ROWS = ["angle", "emg", "moment", "moment_arms",
                "muscle_forces", "activations", "energetics"]
DEFAULT_JOINT_MARKERS = {
    "hip":   ["ASI", "PSI", "SACR", "THI"],
    "knee":  ["THI", "FC", "TIB", "KNE"],
    "ankle": ["TIB", "MAL", "ANK", "HEE", "MT"],
    "subtalar": ["MAL", "ANK", "HEE", "MT"],
    "mtp":   ["MT", "TOE"],
}
EMG_FILE_FALLBACKS = ["emg_filtered_normalised.mot", "emg_filtered.mot", "emg.mot"]

ENERGETICS_FILE = "energetics_ProbeReporter_probes.sto"
SO_FORCES_FILE = "SO_StaticOptimization_force.sto"
SO_ACT_FILE = "SO_StaticOptimization_activation.sto"
MARKER_ERR_ALL = "_ik_marker_errors_all.sto"


# ----------------------------------------------------------------------------
# Active settings
# ----------------------------------------------------------------------------
def _S():
    return _ACTIVE or _pkg_settings


def _summary_cfg():
    return getattr(_S(), "SummarySettings", _DefaultSummary)


class _DefaultSummary:
    combine_legs = True
    left_color = "tab:red"
    right_color = "tab:blue"
    rows = DEFAULT_ROWS
    joint_marker_patterns = DEFAULT_JOINT_MARKERS
    joint_muscles = {}
    emg_file = "emg_filtered_normalised.mot"


def _rows():
    r = list(getattr(_summary_cfg(), "rows", DEFAULT_ROWS) or DEFAULT_ROWS)
    return [k for k in r if k in ROW_LABELS]


def _side_color(side):
    c = _summary_cfg()
    if side == "l":
        return getattr(c, "left_color", "tab:red")
    if side == "r":
        return getattr(c, "right_color", "tab:blue")
    return "black"


def _dofs():
    return list(getattr(_S().BatchSettings, "dof_list", []) or [])


_SESSION_EMG_CACHE = {}


def _session_emg_mapping(td):
    """This trial's channel -> muscles from its own session.yaml, or None.

    Walks up from the trial folder to the session.yaml, then resolves the map
    for the ITERATION the trial sits in — a session may define several named
    maps (``emg_map: {narrow: {...}, wide: {...}}``) with each iteration naming
    one, and a summary drawn with a sibling iteration's electrode grouping is
    wrong in a way nothing in the figure would show.
    """
    if not td:
        return None
    key = os.path.abspath(td)
    if key in _SESSION_EMG_CACHE:
        return _SESSION_EMG_CACHE[key]

    def _yaml_in(d):
        for fn in ("session.yaml", "session.yml"):
            p = os.path.join(d, fn)
            if os.path.isfile(p):
                return p
        return None

    # Folder names between the session and the iteration, in either layout:
    #   <session>/<iteration>/<trial>                 (flat)
    #   <session>/3_iterations/<iteration>/<trial>    (numbered)
    # Miss this and every trial on the numbered layout infers no iteration and
    # silently falls back to the session default map.
    WRAPPERS = {"3_iterations", "iterations", "models"}
    result, seen, cur = None, [], key
    for _ in range(7):
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        seen.append(os.path.basename(cur))
        sy = _yaml_in(parent)
        if sy:
            try:
                from bioscout.utils import session as _sess
                cfg = _sess.load_session_yaml(sy)
                names = set(cfg.get("iterations") or cfg.get("models") or {})
                # `seen` is trial-first; the iteration is the deepest folder
                # under the session that is not a wrapper level.
                it = next((n for n in reversed(seen) if n not in WRAPPERS), None)
                result = _sess.resolve_emg_map(
                    cfg, it if it in names else None, strict=False) or None
            except Exception as exc:                       # noqa: BLE001
                # load_session_yaml raises on a malformed emg_map ON PURPOSE.
                # Swallowing it silently here would draw the figure with some
                # other session's channel names and say nothing.
                print(f"[summary] could not read {sy} ({exc}); "
                      "falling back to settings.py's emg_muscle_mapping")
                result = None
            break
        cur = parent
    _SESSION_EMG_CACHE[key] = result
    return result


def _emg_mapping(td=None):
    """Channel -> muscles: this trial's session.yaml first, settings.py after."""
    own = _session_emg_mapping(td)
    if own:
        return own
    return getattr(_S().BatchSettings, "emg_muscle_mapping", {}) or {}


def _emg_file_order():
    f = getattr(_summary_cfg(), "emg_file", None)
    order = list(EMG_FILE_FALLBACKS)
    if f:
        order = [f] + [x for x in order if x != f]
    return order


def _project_root(project_root=None):
    if project_root:
        return Path(project_root)
    p = getattr(_S(), "PROJECT_ROOT", None)
    if p:
        return Path(p)
    sims = getattr(_S(), "SIMULATIONS_DIR", None)
    return Path(sims).parent if sims else Path.cwd()


def _sims_dir(project_root):
    for cand in ("Simulations", "simulations"):
        d = project_root / cand
        if d.exists():
            return d
    return project_root / "Simulations"


def _summary_dir(project_root, sub=None):
    d = project_root / "summary"
    if sub:
        d = d / sub
    d.mkdir(parents=True, exist_ok=True)
    return d


def _find_settings_upwards(start):
    p = Path(start).resolve()
    for anc in [p, *p.parents]:
        cand = anc / "settings.py"
        if cand.is_file():
            return str(cand)
    return None


def _resolve_settings(settings_path):
    global _ACTIVE
    candidate = None
    if settings_path:
        p = Path(settings_path)
        candidate = (p / "settings.py") if p.is_dir() else p
    else:
        cw = Path.cwd() / "settings.py"
        if cw.is_file():
            candidate = cw
    if candidate and candidate.is_file():
        try:
            spec = importlib.util.spec_from_file_location("_summary_settings", str(candidate))
            mod = importlib.util.module_from_spec(spec)
            sys.modules["_summary_settings"] = mod
            spec.loader.exec_module(mod)
            _ACTIVE = mod
            return mod, str(candidate)
        except Exception as e:
            print(f"[summary] could not load settings from {candidate}: {e}; using package settings")
    _ACTIVE = _pkg_settings
    return _pkg_settings, getattr(_pkg_settings, "__file__", "package settings.py")


# ----------------------------------------------------------------------------
# Loading helpers
# ----------------------------------------------------------------------------
def _load(path):
    try:
        if not path or not os.path.exists(path):
            return None
        return utils.load_any_data_file(path)
    except Exception:
        return None


def _norm_pct(df):
    if df is None or "time" not in df.columns:
        return None
    df = df.copy()
    # Guard against a degenerate time column (e.g. all zeros / non-monotonic),
    # which would otherwise collapse every signal to a flat line. Replace it with
    # a uniform ramp; time-normalisation only cares about sample order anyway.
    t = pd.to_numeric(df["time"], errors="coerce").values.astype(float)
    if len(t) < 2 or not np.all(np.diff(t) > 0):
        df["time"] = np.linspace(0.0, 1.0, len(df))
    try:
        out = utils.time_normalise_df(df)
    except Exception:
        return None
    out = out.copy()
    out["pct"] = np.linspace(0, 100, len(out))
    return out


def _load_emg(td):
    for fn in _emg_file_order():
        df = _load(os.path.join(td, fn))
        if df is not None:
            return _norm_pct(df)
    return None


def _ik_col(ik, dof):
    if ik is None:
        return None
    if f"{dof}_angle" in ik.columns:
        return f"{dof}_angle"
    if dof in ik.columns:
        return dof
    return None


def _muscle_cols(df):
    return [c for c in df.columns if c not in ("time", "pct")] if df is not None else []


def _nonzero_muscles(ma):
    if ma is None:
        return []
    muscles = _muscle_cols(ma)
    if _openSim is not None and hasattr(_openSim, "find_non_zero_mom_arm_muscles"):
        try:
            return _openSim.find_non_zero_mom_arm_muscles(ma, muscles)
        except Exception:
            pass
    return [m for m in muscles if ma[m].abs().sum() > 0]


def _split_pos_neg(ma, muscles):
    """Split acting muscles into +MA (agonist) and -MA (antagonist) by mean sign."""
    pos, neg = [], []
    for m in muscles:
        if ma is not None and m in ma.columns:
            (pos if ma[m].mean() >= 0 else neg).append(m)
    return pos, neg


def _series_mean(df, muscles):
    if df is None:
        return None
    cols = [m for m in muscles if m in df.columns]
    return df[cols].mean(axis=1).values if cols else None


def _split_side(dof):
    m = re.search(r"_(l|r)$", dof)
    return (dof[:-2], m.group(1)) if m else (dof, None)


def _joint_key(base):
    return base.split("_")[0]


def _columns(dofs):
    combine = getattr(_summary_cfg(), "combine_legs", True)
    if not combine:
        return [(d, [(d, _split_side(d)[1])]) for d in dofs]
    order, groups = [], {}
    for d in dofs:
        base, side = _split_side(d)
        if base not in groups:
            groups[base] = []
            order.append(base)
        groups[base].append((d, side))
    return [(b, groups[b]) for b in order]


def _per_joint_marker_error(all_err, base):
    if all_err is None:
        return {}
    patterns = getattr(_summary_cfg(), "joint_marker_patterns",
                       DEFAULT_JOINT_MARKERS).get(_joint_key(base))
    cols = [c for c in all_err.columns if c.lower() != "time"]
    if not patterns:
        try:
            return {"all": float(all_err[cols].mean().mean()) * 1000.0}
        except Exception:
            return {}
    out = {}
    for side, letter in (("l", "L"), ("r", "R")):
        sel = [c for c in cols
               if any(p.upper() in c.upper() for p in patterns)
               and (c.upper().startswith(letter) or not c.upper().startswith(("L", "R")))]
        if sel:
            try:
                out[side] = float(all_err[sel].mean().mean()) * 1000.0
            except Exception:
                pass
    return out


def _find_ceinms_forces(td):
    for attr in ("ceinms_muscle_forces", "jra_forces_ceinms"):
        try:
            rel = getattr(_S().Inputs(), attr, None)
        except Exception:
            rel = None
        if rel and os.path.exists(os.path.join(td, rel)):
            return os.path.join(td, rel)
    hits = glob.glob(os.path.join(td, "**", "MuscleForces.sto"), recursive=True)
    return hits[0] if hits else None


def _emg_channels_for(emg, muscles, td=None):
    if emg is None or not muscles:
        return []
    mapping = _emg_mapping(td)
    return [ch for ch, muscs in mapping.items()
            if ch in emg.columns and any(m in muscles for m in muscs)]


def _emg_envelope(emg, muscles, normalise=True, td=None):
    chans = _emg_channels_for(emg, muscles, td)
    if not chans:
        return None
    env = emg[chans].mean(axis=1).values.astype(float)
    if normalise:
        rng = np.nanmax(env) - np.nanmin(env)
        env = (env - np.nanmin(env)) / rng if rng > 0 else env * 0.0
    return env


def _energetics_cols(en, muscles):
    if en is None or not muscles:
        return []
    out = []
    for c in _muscle_cols(en):
        cl = c.lower()
        if any(m.lower() in cl for m in muscles):
            out.append(c)
    return out


def _energetics_total_col(en):
    if en is None:
        return None
    for c in _muscle_cols(en):
        if "total" in c.lower():
            return c
    return None


def _moment_arms(td, dof):
    return _norm_pct(_load(os.path.join(
        td, "muscleAnalysis", f"_MuscleAnalysis_MomentArm_{dof}.sto")))


def _sum_muscle_moment(forces, ma, muscles):
    if forces is None or ma is None or not muscles:
        return None
    cols = [m for m in muscles if m in forces.columns and m in ma.columns]
    if not cols:
        return None
    total = np.zeros(len(forces))
    for m in cols:
        total = total + forces[m].values * ma[m].values
    return pd.DataFrame({"pct": forces["pct"].values, "moment": total})


def _load_trial(td):
    ce = _find_ceinms_forces(td)
    return {
        "ik": _norm_pct(_load(os.path.join(td, "joint_angles.mot"))),
        "id": _norm_pct(_load(os.path.join(td, "inverse_dynamics.sto"))),
        "so_forces": _norm_pct(_load(os.path.join(td, SO_FORCES_FILE))),
        "so_act": _norm_pct(_load(os.path.join(td, SO_ACT_FILE))),
        "emg": _load_emg(td),
        "energetics": _norm_pct(_load(os.path.join(td, ENERGETICS_FILE))),
        "all_err": _load(os.path.join(td, MARKER_ERR_ALL)),
        "ce_forces": _norm_pct(_load(ce)) if ce else None,
    }


# ----------------------------------------------------------------------------
# Discovery
# ----------------------------------------------------------------------------
def _is_processed(td):
    return os.path.exists(os.path.join(td, "joint_angles.mot"))


def discover(project_root, subject=None):
    sims = _sims_dir(project_root)
    out = []
    if not sims.exists():
        return out
    subjects = [subject] if subject else sorted(
        d.name for d in sims.iterdir() if d.is_dir())
    for pid in subjects:
        pdir = sims / pid
        if not pdir.is_dir():
            continue
        for sdir in sorted(p for p in pdir.iterdir() if p.is_dir()):
            for tdir in sorted(p for p in sdir.iterdir() if p.is_dir()):
                if _is_processed(str(tdir)):
                    out.append({"subject": pid, "session": sdir.name,
                                "trial": tdir.name, "path": str(tdir)})
    return out


def _info_from_path(trial_path):
    p = Path(trial_path).resolve()
    return {"subject": p.parent.parent.name, "session": p.parent.name,
            "trial": p.name, "path": str(p)}


def _trial_type(name):
    return re.sub(r"\d+$", "", name) or name


def _empty(ax):
    ax.text(0.5, 0.5, "no data", transform=ax.transAxes, ha="center",
            va="center", fontsize=8, color="0.6", style="italic")


def _legend(ax):
    h, l = ax.get_legend_handles_labels()
    if h:
        ax.legend(fontsize=5, loc="best", framealpha=0.5, handlelength=1.4)


# ----------------------------------------------------------------------------
# Per-trial figure
# ----------------------------------------------------------------------------
def plot_trial(info, save_dir=None):
    td = info["path"]
    dofs = _dofs()
    if not dofs:
        return [], None
    rows_keys = _rows()
    cols_def = _columns(dofs)
    combine = getattr(_summary_cfg(), "combine_legs", True)

    D = _load_trial(td)
    ik, idm = D["ik"], D["id"]
    so_f, so_a, emg, ener = D["so_forces"], D["so_act"], D["emg"], D["energetics"]
    ce_f, all_err = D["ce_forces"], D["all_err"]

    ncols, nrows = len(cols_def), len(rows_keys)
    fig, ax = plt.subplots(nrows, ncols, figsize=(max(3.4 * ncols, 6), 2.3 * nrows),
                           squeeze=False)
    metric_rows = []
    SLAB = {"l": "L", "r": "R", None: ""}

    for jc, (title, members) in enumerate(cols_def):
        base = title if combine else _split_side(title)[0]
        side_data = []
        for dof, side in members:
            ma = _moment_arms(td, dof)
            nz = _nonzero_muscles(ma)
            pos, neg = _split_pos_neg(ma, nz)
            side_data.append({"dof": dof, "side": side, "sc": _side_color(side),
                              "ma": ma, "nz": nz, "pos": pos, "neg": neg})
        joint_muscles = sorted(set().union(*[set(d["nz"]) for d in side_data])
                               if side_data else set())
        cfg_jm = getattr(_summary_cfg(), "joint_muscles", {}) or {}
        if cfg_jm.get(_joint_key(base)):
            joint_muscles = sorted(set(joint_muscles) | set(cfg_jm[_joint_key(base)]))

        for ri, key in enumerate(rows_keys):
            a = ax[ri, jc]
            drew = False

            if key == "angle":
                for sd in side_data:
                    col = _ik_col(ik, sd["dof"])
                    if col is not None:
                        a.plot(ik["pct"], ik[col], color=sd["sc"],
                               label={"l": "Left", "r": "Right"}.get(sd["side"], "—"))
                        drew = True
                a.set_title(title, fontsize=9)
                jerr = _per_joint_marker_error(all_err, base)
                if jerr:
                    txt = " / ".join(f"{k.upper()}:{v:.0f}" for k, v in jerr.items())
                    a.text(0.03, 0.97, f"mkr err (mm)\n{txt}", transform=a.transAxes,
                           fontsize=6.5, va="top",
                           bbox=dict(boxstyle="round", fc="wheat", alpha=0.6))

            elif key == "emg":
                chans = _emg_channels_for(emg, joint_muscles, td)
                for i, ch in enumerate(chans):
                    a.plot(emg["pct"], emg[ch], lw=1,
                           color=matplotlib.colormaps["tab10"](i % 10), label=ch)
                drew = bool(chans)

            elif key == "moment":
                for sd in side_data:
                    idcol = f"{sd['dof']}_moment"
                    sc, S = sd["sc"], SLAB.get(sd["side"], "")
                    if idm is not None and idcol in idm.columns:
                        a.plot(idm["pct"], idm[idcol], color=sc, lw=2, label=f"ID {S}".strip())
                        drew = True
                    mm = _sum_muscle_moment(so_f, sd["ma"], sd["nz"])
                    if mm is not None:
                        a.plot(mm["pct"], mm["moment"], "--", color=sc, lw=1.4,
                               label=f"Sum musc {S}".strip())
                        drew = True
                        if idm is not None and idcol in idm.columns:
                            try:
                                r2 = utils.rsquared(idm[idcol].values, mm["moment"].values)
                                rng = float(idm[idcol].max() - idm[idcol].min())
                                rmsep = (utils.rmse(idm[idcol].values, mm["moment"].values)
                                         / rng * 100) if rng else np.nan
                                metric_rows.append({
                                    "subject": info["subject"], "session": info["session"],
                                    "trial": info["trial"], "trial_type": _trial_type(info["trial"]),
                                    "dof": sd["dof"], "moment_R2": r2, "moment_RMSE_pct": rmsep})
                            except Exception:
                                pass
                    ce = _sum_muscle_moment(ce_f, sd["ma"], sd["nz"])
                    if ce is not None:
                        a.plot(ce["pct"], ce["moment"], ":", color=sc, lw=1.4,
                               label=f"CEINMS {S}".strip())

            elif key in ("moment_arms", "muscle_forces", "activations", "energetics"):
                src = {"moment_arms": None, "muscle_forces": so_f,
                       "activations": so_a, "energetics": ener}[key]
                for sd in side_data:
                    sc, S = sd["sc"], SLAB.get(sd["side"], "")
                    if key == "moment_arms":
                        df, pct = sd["ma"], (sd["ma"]["pct"].values if sd["ma"] is not None else None)
                        pv = _series_mean(df, sd["pos"])
                        nv = _series_mean(df, sd["neg"])
                    elif key == "energetics":
                        pct = ener["pct"].values if ener is not None else None
                        pcols = _energetics_cols(ener, sd["pos"])
                        ncols_ = _energetics_cols(ener, sd["neg"])
                        pv = ener[pcols].mean(axis=1).values if pcols else None
                        nv = ener[ncols_].mean(axis=1).values if ncols_ else None
                    else:
                        pct = src["pct"].values if src is not None else None
                        pv = _series_mean(src, sd["pos"])
                        nv = _series_mean(src, sd["neg"])
                    if pct is not None and pv is not None:
                        a.plot(pct, pv, color=sc, ls="-", lw=1.5, label=f"{S} (+MA)".strip())
                        drew = True
                    if pct is not None and nv is not None:
                        a.plot(pct, nv, color=sc, ls="--", lw=1.5, label=f"{S} (-MA)".strip())
                        drew = True
                if key == "activations":
                    env = _emg_envelope(emg, joint_muscles, normalise=True, td=td)
                    if env is not None:
                        a.fill_between(emg["pct"], 0, env, color="gray", alpha=0.2, label="EMG")
                        drew = True

            if ri == 0 and key != "angle":
                a.set_title(title, fontsize=9)
            if not drew:
                _empty(a)
            else:
                _legend(a)
            if jc == 0:
                a.set_ylabel(ROW_LABELS[key])
            if ri == nrows - 1:
                a.set_xlabel("% trial")

    fig.suptitle(f"{info['subject']} / {info['session']} / {info['trial']}", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    # Saved in the trial folder -> simply "summary.png". When routed elsewhere
    # (e.g. the overall-only temp dir) keep the trial name to avoid collisions.
    in_trial_folder = save_dir is None
    save_dir = save_dir or td
    os.makedirs(save_dir, exist_ok=True)
    png = os.path.join(save_dir, "summary.png" if in_trial_folder
                       else f"summary_{info['trial']}.png")
    try:
        fig.savefig(png, dpi=130)
    finally:
        plt.close(fig)

    if all_err is not None:
        for mr in metric_rows:
            je = _per_joint_marker_error(all_err, _split_side(mr["dof"])[0])
            mr["marker_err_mm"] = je.get(_split_side(mr["dof"])[1], je.get("all"))
    return metric_rows, png


# ----------------------------------------------------------------------------
# Overall figure (mean +/- SD per side)
# ----------------------------------------------------------------------------
def _trial_series(td, dof):
    out = {}
    ik = _norm_pct(_load(os.path.join(td, "joint_angles.mot")))
    idm = _norm_pct(_load(os.path.join(td, "inverse_dynamics.sto")))
    so_f = _norm_pct(_load(os.path.join(td, SO_FORCES_FILE)))
    so_a = _norm_pct(_load(os.path.join(td, SO_ACT_FILE)))
    emg = _load_emg(td)
    ener = _norm_pct(_load(os.path.join(td, ENERGETICS_FILE)))
    ma = _moment_arms(td, dof)
    nz = _nonzero_muscles(ma)
    pct = np.linspace(0, 100, 101)

    def mk(v):
        return pd.DataFrame({"pct": pct, "val": np.asarray(v, float)[:101]})

    col = _ik_col(ik, dof)
    if col is not None:
        out["angle"] = mk(ik[col].values)
    env = _emg_envelope(emg, set(nz), normalise=True, td=td)
    if env is not None:
        out["emg"] = mk(env)
    if idm is not None and f"{dof}_moment" in idm.columns:
        out["moment"] = mk(idm[f"{dof}_moment"].values)
    if ma is not None and nz:
        out["moment_arms"] = mk(ma[nz].abs().mean(axis=1).values)
    fc = [m for m in nz if so_f is not None and m in so_f.columns]
    if fc:
        out["muscle_forces"] = mk(so_f[fc].mean(axis=1).values)
    ac = [m for m in nz if so_a is not None and m in so_a.columns]
    if ac:
        out["activations"] = mk(so_a[ac].mean(axis=1).values)
    ec = _energetics_cols(ener, set(nz))
    if ec:
        out["energetics"] = mk(ener[ec].mean(axis=1).values)
    elif ener is not None and _energetics_total_col(ener):
        out["energetics"] = mk(ener[_energetics_total_col(ener)].values)
    return out


def plot_overall(targets, project_root, out_dir=None):
    out_dir = out_dir or _summary_dir(project_root)
    dofs = _dofs()
    if not dofs or not targets:
        return []
    rows_keys = _rows()
    cols_def = _columns(dofs)

    groups = {}
    for t in targets:
        groups.setdefault(_trial_type(t["trial"]), []).append(t)

    saved = []
    for gtype, items in sorted(groups.items()):
        data = {}
        for t in items:
            for _, members in cols_def:
                for dof, side in members:
                    s = _trial_series(t["path"], dof)
                    for k, df in s.items():
                        data.setdefault((k, dof), []).append(df)

        ncols, nrows = len(cols_def), len(rows_keys)
        fig, ax = plt.subplots(nrows, ncols, figsize=(max(3.4 * ncols, 6), 2.3 * nrows),
                               squeeze=False)
        for jc, (title, members) in enumerate(cols_def):
            for ri, key in enumerate(rows_keys):
                a = ax[ri, jc]
                any_drew = False
                for dof, side in members:
                    dfl = data.get((key, dof), [])
                    if dfl:
                        try:
                            utils.plot_mean_error_shade(
                                a, dfl, "pct", "val", color=_side_color(side),
                                label={"l": "Left", "r": "Right"}.get(side, "—"))
                            any_drew = True
                        except Exception:
                            pass
                if not any_drew:
                    _empty(a)
                else:
                    _legend(a)
                if ri == 0:
                    a.set_title(title, fontsize=9)
                if ri == nrows - 1:
                    a.set_xlabel("% trial")
                if jc == 0:
                    a.set_ylabel(ROW_LABELS[key])
        fig.suptitle(f"Overall: {gtype}  (n={len(items)} trials)", fontsize=12)
        fig.tight_layout(rect=(0, 0, 1, 0.98))
        png = os.path.join(out_dir, f"overall_{gtype}.png")
        try:
            fig.savefig(png, dpi=130)
        finally:
            plt.close(fig)
        saved.append(png)
    return saved


# ----------------------------------------------------------------------------
# Report writers
# ----------------------------------------------------------------------------
def _write_csv(rows, out_dir):
    if not rows:
        return None
    path = os.path.join(out_dir, "summary_metrics.csv")
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _write_report(rows, overall_pngs, out_dir, project_root, subject=None):
    df = pd.DataFrame(rows) if rows else pd.DataFrame()
    md = os.path.join(out_dir, "summary_report.md")
    scope = f"subject {subject}" if subject else "all subjects"
    lines = ["# BioScout Summary Report", "",
             f"Scope: **{scope}**  |  Project: `{project_root}`", "",
             "Columns = joints (left red, right blue). Rows: "
             + ", ".join(_rows()) + ".", ""]
    if not df.empty:
        n_tr = df[["subject", "session", "trial"]].drop_duplicates().shape[0]
        lines += [f"- Trials summarised: **{n_tr}**",
                  f"- Subjects: {', '.join(sorted(df['subject'].unique()))}",
                  f"- Trial types: {', '.join(sorted(df['trial_type'].unique()))}", "",
                  "## Mean metrics by trial type & DOF", "",
                  "| Trial type | DOF | Marker err (mm) | Moment R2 | Moment RMSE% |",
                  "|---|---|---|---|---|"]
        agg = {}
        if "marker_err_mm" in df.columns:
            agg["marker_err_mm"] = ("marker_err_mm", "mean")
        agg["moment_R2"] = ("moment_R2", "mean")
        agg["moment_RMSE_pct"] = ("moment_RMSE_pct", "mean")
        g = df.groupby(["trial_type", "dof"]).agg(**agg).reset_index()

        def _f(x):
            return "-" if pd.isna(x) else f"{x:.2f}"
        for _, r in g.iterrows():
            lines.append(f"| {r['trial_type']} | {r['dof']} | {_f(r.get('marker_err_mm'))} "
                         f"| {_f(r['moment_R2'])} | {_f(r['moment_RMSE_pct'])} |")
        lines.append("")
    lines += ["## Overall plots", ""]
    for p in overall_pngs:
        rel = os.path.relpath(p, out_dir)
        lines += [f"### {Path(p).stem}", f"![{Path(p).stem}]({rel})", ""]
    with open(md, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    pdf_path = os.path.join(out_dir, "summary_report.pdf")
    try:
        with PdfPages(pdf_path) as pdf:
            fig = plt.figure(figsize=(11, 8.5))
            fig.text(0.5, 0.95, "BioScout Summary Report", ha="center", fontsize=18)
            fig.text(0.5, 0.91, f"Scope: {scope}", ha="center", fontsize=11)
            pdf.savefig(fig)
            plt.close(fig)
            for p in overall_pngs:
                if not os.path.exists(p):
                    continue
                img = plt.imread(p)
                fig = plt.figure(figsize=(11, 8.5))
                axi = fig.add_axes([0, 0, 1, 1])
                axi.imshow(img)
                axi.axis("off")
                pdf.savefig(fig)
                plt.close(fig)
    except Exception as e:
        print(f"[summary] PDF generation skipped: {e}")
        pdf_path = None
    return md, pdf_path


# ----------------------------------------------------------------------------
# Public entry point
# ----------------------------------------------------------------------------
def run_summary(settings_path=None, subject=None, overall_only=False,
                project_root=None, trial_path=None):
    """Build summaries. ``trial_path`` (or a trial directory passed as
    ``settings_path``) restricts to a single trial for fast iteration."""
    try:
        from utils.logger import logger
    except Exception:
        import logging
        logger = logging.getLogger("bioscout.summary")
        logging.basicConfig(level=logging.INFO)

    # If --summary was given a trial directory, treat it as single-trial mode.
    if trial_path is None and settings_path:
        p = Path(settings_path)
        if p.is_dir() and (p / "joint_angles.mot").exists():
            trial_path = str(p)
            settings_path = None

    if trial_path:
        sp = settings_path or _find_settings_upwards(trial_path)
        _, used = _resolve_settings(sp)
    else:
        _, used = _resolve_settings(settings_path)
    root = _project_root(project_root)

    logger.info("=" * 70)
    logger.info("BioScout — Summary")
    logger.info(f"Settings       : {used}")
    logger.info(f"Rows           : {', '.join(_rows())}")
    logger.info(f"EMG source     : {_emg_file_order()[0]} (fallbacks: "
                f"{', '.join(_emg_file_order()[1:])})")

    # --- single-trial mode ---
    if trial_path:
        if not _is_processed(trial_path):
            logger.error(f"Not a processed trial (no joint_angles.mot): {trial_path}")
            return False
        info = _info_from_path(trial_path)
        logger.info(f"Single trial   : {info['subject']}/{info['session']}/{info['trial']}")
        logger.info("=" * 70)
        try:
            _, png = plot_trial(info)
            logger.info(f"[OK] {png}")
            logger.info("=" * 70)
            return True
        except Exception as e:
            logger.error(f"[ERROR] {info['trial']}: {e}")
            logger.error(traceback.format_exc())
            return False

    targets = discover(root, subject=subject)
    logger.info(f"Project        : {root}")
    logger.info(f"Scope          : {'subject ' + subject if subject else 'all subjects'}")
    logger.info(f"Mode           : {'overall only' if overall_only else 'per-trial + overall'}")
    logger.info(f"Processed trials found : {len(targets)}")
    logger.info("=" * 70)
    if not targets:
        logger.error("No processed trials found under "
                     f"{_sims_dir(root)}. Check the settings path / project root.")
        return False

    all_rows = []
    if not overall_only:
        for t in targets:
            try:
                rows, png = plot_trial(t)
                all_rows.extend(rows)
                logger.info(f"  [OK] {t['subject']}/{t['session']}/{t['trial']} -> {png}")
            except Exception as e:
                logger.error(f"  [ERROR] {t['subject']}/{t['session']}/{t['trial']}: {e}")
                logger.debug(traceback.format_exc())
    else:
        tmp = _summary_dir(root, "_per_trial_tmp")
        for t in targets:
            try:
                rows, _ = plot_trial(t, save_dir=tmp)
                all_rows.extend(rows)
            except Exception as e:
                logger.debug(f"metrics gather failed for {t['trial']}: {e}")

    out_dir = _summary_dir(root)
    overall_pngs = plot_overall(targets, root, out_dir=out_dir)
    csv_path = _write_csv(all_rows, out_dir)
    md_path, pdf_path = _write_report(all_rows, overall_pngs, out_dir, root, subject=subject)
    if subject:
        _write_csv([r for r in all_rows if r["subject"] == subject],
                   _summary_dir(root, subject))

    logger.info("-" * 70)
    logger.info(f"Overall figures : {len(overall_pngs)} -> {out_dir}")
    if csv_path:
        logger.info(f"Metrics CSV     : {csv_path}")
    if md_path:
        logger.info(f"Report          : {md_path}")
    logger.info("[OK] Summary complete.")
    logger.info("=" * 70)
    return True
