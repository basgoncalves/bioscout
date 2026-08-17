"""Build the fibre force-length-velocity figure from a session.

`fl_fv_surface` draws; this module collects. Give it a `FlFvSpec` -- which
tasks, which muscle groups, which models, which pictograms -- and a source that
knows where a project keeps its files, and it produces the figure.

    from bioscout.muscle_inspect.fl_fv_report import FlFvSpec, build_fl_fv

    spec = FlFvSpec(
        session_dir="/data/Athlete_03/25_03_31",
        tasks={"Walking": ["Walking_03", "Walking_05"],
               "Squat":   ["Squat_01", "Squat_02"]},
        groups={"Vasti": ["vasint_r", "vaslat_r", "vasmed_r"],
                "Triceps Surae": ["soleus_r", "gaslat_r", "gasmed_r"]},
        models=["cateli", "gpk"],
        model_colors={"cateli": "green", "gpk": "firebrick"},
        task_icons={"Walking": "icons/walking.png"},
        group_icons={"Vasti": "icons/vasti.png"})
    build_fl_fv(spec, out_dir="figures")

NOTHING here is specific to one study: the tasks, their pictograms, the muscle
groups and their pictograms, the models and their colours all come out of the
spec. A project that needs different tasks or different muscles changes the
spec, not this file.

WHERE THE NUMBERS COME FROM
    `FlFvSource` is the seam. The default `BioscoutSource` reads a standard
    bioscout session (`3_iterations/<model>/<trial>/...`). A project whose
    layout or conventions differ subclasses it and overrides the handful of
    hooks it needs -- which is also where project POLICY belongs (which .osim a
    given algorithm ran on, how a joint's reaction columns are named, what to
    do when the fibre output is degenerate). Keeping that out here means no
    release of bioscout inherits one dataset's quirks.
"""
from __future__ import annotations

import glob
import os
import pickle
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import matplotlib.lines as mlines

from .fl_fv_surface import (osim_muscle_params, rigid_tendon_states,
                            weighted_group_trace, force_weights, finish_trace,
                            plot_fl_fv_surface)

NCYC = 101                     # samples per movement cycle
_trapz = getattr(np, "trapezoid", None) or np.trapz   # numpy renamed it in 2.0

# colour is the MODEL; the algorithm is the stroke and the peak-force marker
ALGO_LS = {"SO": "-", "CEINMS": (0, (5, 2))}
ALGO_MK = {"SO": "o", "CEINMS": "X"}
ALGO_TAG = {"SO": "SO", "CEINMS": "EMG"}
ALGO_NAME = {"SO": "static optimisation", "CEINMS": "EMG-informed"}
TAB10 = ["#1F77B4", "#D62728", "#2CA02C", "#9467BD", "#E67E22",
         "#17BECF", "#8C564B", "#7F7F7F"]

# the numbers table above each panel
COLUMNS = (dict(key="work_abs", head="Wtot (J)", fmt=".0f", cw=4),
           dict(key="peak_bw", head="F (BW)", fmt=".2f", cw=4),
           dict(key="range:l", head="l~ range", fmt=".1f", cw=7),
           dict(key="range:v", head="v~ range", fmt=".1f", cw=8),
           dict(key="act_pk", head="a@Fpk", fmt=".2f", cw=4))

# where each joint's contact-force callout sits around the task pictogram
JOINT_POS = {"hip": dict(dx=-0.50, dy=0.60, ha="right", va="top"),
             "knee": dict(dx=0.50, dy=0.14, ha="left", va="top"),
             "ankle": dict(dx=-0.50, dy=-0.16, ha="right", va="top")}


# =============================================================================
# what to draw
# =============================================================================

@dataclass
class FlFvSpec:
    """Everything study-specific, in one place."""
    session_dir: str
    tasks: Dict[str, List[str]]                  # label -> its repetition trials
    groups: Dict[str, List[str]]                 # muscle group -> muscle names
    models: List[str]
    algorithms: Sequence[str] = ("SO", "CEINMS")
    side: str = "R"
    subject: str = ""
    model_colors: Dict[str, str] = field(default_factory=dict)
    model_labels: Dict[str, str] = field(default_factory=dict)
    group_colors: Dict[str, str] = field(default_factory=dict)
    task_icons: Dict[str, str] = field(default_factory=dict)
    group_icons: Dict[str, str] = field(default_factory=dict)
    joints: Sequence[str] = ("hip", "knee", "ankle")
    method_note: Dict[str, str] = field(default_factory=dict)  # algo -> caption
    dpi: int = 200
    save_pdf: bool = False

    def colour_of(self, model):
        return self.model_colors.get(model) or TAB10[
            self.models.index(model) % len(TAB10)]

    def label_of(self, model):
        return self.model_labels.get(model, model)

    def group_colour(self, group):
        gs = list(self.groups)
        return self.group_colors.get(group) or TAB10[gs.index(group) % len(TAB10)]

    def colors(self):
        return {g: self.group_colour(g) for g in self.groups}


# =============================================================================
# where the numbers live
# =============================================================================

class FlFvSource:
    """The seam between the figure and a project's folder layout.

    Every method may return None; a missing file drops that series quietly
    rather than failing the whole figure.
    """

    def force(self, model, trial, algo):        raise NotImplementedError
    def activation(self, model, trial, algo):   return None
    def mt_length(self, model, trial):          return None
    def fibre_states(self, model, trial, algo): return None   # (l~ file, v~ file)
    def model_file(self, model, algo):          return None   # the .osim
    def jra(self, model, trial, algo):          return None
    def bodyweight_N(self, model):              return 1.0
    def time_range(self, trial):                return None
    def sides(self, trial):                     return ["r", "l"]

    def jra_columns(self, model, joint, side):
        """The three force columns of one joint reaction, project convention."""
        s = "l" if str(side).lower().startswith("l") else "r"
        stem = {"hip": f"hip_{s}_on_femur_{s}_in_femur_{s}",
                "ankle": f"ankle_{s}_on_talus_{s}_in_talus_{s}",
                "knee": f"walker_knee_{s}_on_tibia_{s}_in_tibia_{s}"}
        return [f"{stem[joint]}_f{a}" for a in "xyz"] if joint in stem else None


class BioscoutSource(FlFvSource):
    """A standard bioscout session: `3_iterations/<model>/<trial>/...`."""

    def __init__(self, session_dir, spec=None):
        self.dir = session_dir
        self.spec = spec

    # -- layout ------------------------------------------------------------
    def root(self):
        p = os.path.join(self.dir, "3_iterations")
        return p if os.path.isdir(p) else self.dir

    def trial_dir(self, model, trial):
        return os.path.join(self.root(), model, trial)

    def _exec_dir(self, model, trial):
        base = os.path.join(self.trial_dir(model, trial), "ceinms")
        hits = sorted(glob.glob(os.path.join(base, "Execution_a*_b*_g*"))) \
            or sorted(glob.glob(os.path.join(base, "Execution*")))
        return hits[-1] if hits else None

    # -- files -------------------------------------------------------------
    def force(self, model, trial, algo):
        if str(algo).upper() == "SO":
            return _first(os.path.join(self.trial_dir(model, trial),
                                       "static_optimisation",
                                       "SO_StaticOptimization_force.sto"))
        d = self._exec_dir(model, trial)
        return _first(os.path.join(d, "MuscleForces.sto")) if d else None

    def activation(self, model, trial, algo):
        if str(algo).upper() == "SO":
            return _first(os.path.join(self.trial_dir(model, trial),
                                       "static_optimisation",
                                       "SO_StaticOptimization_activation.sto"))
        d = self._exec_dir(model, trial)
        return _first(os.path.join(d, "Activations.sto")) if d else None

    def mt_length(self, model, trial):
        return _first(os.path.join(self.trial_dir(model, trial),
                                   "muscle_analysis",
                                   "_MuscleAnalysis_Length.sto"))

    def fibre_states(self, model, trial, algo):
        """CEINMS solves its own fibre dynamics; SO has none of its own."""
        if str(algo).upper() == "SO":
            return None
        d = self._exec_dir(model, trial)
        if not d:
            return None
        l = _first(os.path.join(d, "NormFibreLengths.sto"))
        v = _first(os.path.join(d, "NormFibreVelocities.sto"))
        return (l, v) if l and v else None

    def model_file(self, model, algo):
        hits = sorted(glob.glob(os.path.join(self.root(), model, "scaled*.osim")))
        return hits[0] if hits else None

    def jra(self, model, trial, algo):
        fn = f"Analyse_JRA_ReactionLoads_{str(algo).upper()}.sto"
        d = self.trial_dir(model, trial)
        return _first(os.path.join(d, "joint_contact_forces", fn),
                      os.path.join(d, "static_optimisation", fn),
                      os.path.join(d, "ceinms", fn))

    def bodyweight_N(self, model):
        import xml.etree.ElementTree as ET
        f = self.model_file(model, "SO")
        if not f or not os.path.isfile(f):
            return 1.0
        try:
            root = ET.parse(f).getroot()
            m = sum(float(b.find("mass").text) for b in root.iter("Body")
                    if b.find("mass") is not None)
            return m * 9.81 if m > 0 else 1.0
        except Exception:
            return 1.0


def _first(*cands):
    return next((c for c in cands if c and os.path.isfile(c)), None)


# =============================================================================
# collection
# =============================================================================

def _load(path, _cache={}):
    """Read an .sto into {column: array}. Cached per path."""
    if not path:
        return None
    if path in _cache:
        return _cache[path]
    out = None
    try:
        with open(path, "r", errors="ignore") as fh:
            lines = fh.read().splitlines()
        i = next(k for k, l in enumerate(lines)
                 if l.strip().lower() == "endheader")
        head = lines[i + 1].split()
        rows = [[float(x) for x in l.split()] for l in lines[i + 2:] if l.strip()]
        a = np.asarray(rows, float)
        out = {h: a[:, k] for k, h in enumerate(head)} if a.size else None
    except Exception as exc:
        print(f"[warn] unreadable {os.path.basename(str(path))}: {exc}")
    _cache[path] = out
    return out


def _col(df, name):
    if df is None:
        return None
    lut = {str(k).strip().lower(): k for k in df}
    return lut.get(str(name).strip().lower())


def _series(df, name, tt):
    c = _col(df, name)
    if c is None:
        return None
    t = df[_col(df, "time")]
    return np.interp(tt, t, np.asarray(df[c], float))


def trial_traces(spec, src, model, trial, algo, bw, par):
    """{group: raw arrays} for one trial, over NCYC samples of the cycle."""
    fdf = _load(src.force(model, trial, algo))
    mdf = _load(src.mt_length(model, trial))
    adf = _load(src.activation(model, trial, algo))
    if fdf is None:
        return {}
    fib = src.fibre_states(model, trial, algo)
    ldf, vdf = (_load(fib[0]), _load(fib[1])) if fib else (None, None)
    if ldf is None and mdf is None:
        return {}

    w = src.time_range(trial)
    if w:
        t0, t1 = float(w[0]), float(w[1])
    else:
        base = [d for d in (fdf, mdf, ldf, vdf) if d is not None]
        t0 = max(float(np.nanmin(d[_col(d, "time")])) for d in base)
        t1 = min(float(np.nanmax(d[_col(d, "time")])) for d in base)
    if not (t1 > t0):
        return {}
    tt = np.linspace(t0, t1, NCYC)

    out = {}
    for g, muscles in spec.groups.items():
        F, L, V, A, F0, W = [], [], [], [], 0.0, [0.0, 0.0]
        for m in muscles:
            f = _series(fdf, m, tt)
            if f is None or not np.isfinite(f).any():
                continue
            lmt = _series(mdf, m, tt) if mdf is not None else None
            if ldf is not None:
                ln, vn = _series(ldf, m, tt), _series(vdf, m, tt)
            elif lmt is not None:
                # no solved fibre state: fall back to a RIGID-TENDON estimate
                ln, vn = rigid_tendon_states(tt, lmt, par.get(m, {}))
            else:
                ln = vn = None
            if ln is None or vn is None:
                continue
            F.append(f); L.append(ln); V.append(vn)
            a = _series(adf, m, tt) if adf is not None else None
            A.append(a if a is not None else np.full_like(f, np.nan))
            F0 += float(par.get(m, {}).get("f0", np.nan) or np.nan)
            if lmt is not None:                      # muscle-tendon work
                p = f * -np.gradient(lmt, tt)        # shortening positive
                W[0] += float(_trapz(np.clip(p, 0, None), tt))
                W[1] += float(_trapz(np.clip(p, None, 0), tt))
        if F:
            l, v, fn = weighted_group_trace(F, L, V, F0)
            wt, _ = force_weights(F)       # same weights for the activation
            out[g] = dict(l=l, v=v, fn=fn, fbw=fn * F0 / bw,
                          act=np.nansum(wt * np.vstack(A), axis=0),
                          wpos=W[0], wneg=W[1])
    return out


def task_traces(spec, src, model, trials, algo, where=""):
    """{group: trace} averaged over the repetitions of one task, one limb."""
    par = osim_muscle_params(src.model_file(model, algo))
    bw = src.bodyweight_N(model) or 1.0
    side = spec.side.lower()
    acc = {}
    for tr in trials:
        if side not in [s.lower() for s in src.sides(tr)]:
            continue
        for g, d in trial_traces(spec, src, model, tr, algo, bw, par).items():
            acc.setdefault(g, []).append(d)
    out = {}
    for g, ds in acc.items():
        fbw = np.nanmean(np.vstack([d["fbw"] for d in ds]), axis=0)
        t = finish_trace(np.nanmean(np.vstack([d["l"] for d in ds]), axis=0),
                         np.nanmean(np.vstack([d["v"] for d in ds]), axis=0),
                         np.nanmean(np.vstack([d["fn"] for d in ds]), axis=0),
                         float(np.nanmean([d["wpos"] for d in ds])),
                         float(np.nanmean([d["wneg"] for d in ds])),
                         where=f"{where} {g}",
                         act=np.nanmean(np.vstack([d["act"] for d in ds]), axis=0),
                         peak_bw=(float(np.nanmax(fbw))
                                  if np.isfinite(fbw).any() else np.nan))
        if t:
            out[g] = t
    return out


def joint_range_bw(spec, src, model, trials, algo, joint):
    """(min, max) |R| of one joint contact force over the task, in BW."""
    vals = []
    for tr in trials:
        df = _load(src.jra(model, tr, algo))
        names = src.jra_columns(model, joint, spec.side)
        cols = [_col(df, c) for c in (names or [])] if df is not None else []
        if not names or not all(cols):
            continue
        t = df[_col(df, "time")]
        r = np.linalg.norm(np.vstack([df[c] for c in cols]), axis=0)
        w = src.time_range(tr)
        m = ((t >= w[0]) & (t <= w[1])) if w else np.ones_like(t, bool)
        if m.sum() < 2:
            m = np.ones_like(t, bool)
        vals.append(r[m] / (src.bodyweight_N(model) or 1.0))
    if not vals:
        return None
    return (float(np.nanmin([np.nanmin(v) for v in vals])),
            float(np.nanmax([np.nanmax(v) for v in vals])))


def collect(spec, src, cache_path=None, refresh=False, verbose=True):
    """{(task, model, algo): {group: trace}}, {(task, model, algo, joint): (lo, hi)}.

    Reading the .sto files dominates the runtime; drawing is seconds. The cache
    is INCREMENTAL and saved after every task, so an interrupted run leaves
    progress behind and the next one picks up where it stopped.
    """
    algos = [a.upper() for a in spec.algorithms]
    key = (spec.subject, spec.session_dir, tuple(spec.models), tuple(algos),
           spec.side, tuple(sorted(spec.groups)))
    data, jcf = {}, {}
    if cache_path and not refresh and os.path.isfile(cache_path):
        try:
            with open(cache_path, "rb") as fh:
                got = pickle.load(fh)
            if got.get("key") == key:
                data, jcf = got["data"], got["jcf"]
        except Exception as exc:
            print(f"[warn] unreadable cache: {exc}")

    def save():
        if not cache_path:
            return
        try:
            os.makedirs(os.path.dirname(os.path.abspath(cache_path)) or ".",
                        exist_ok=True)
            with open(cache_path, "wb") as fh:
                pickle.dump(dict(key=key, data=data, jcf=jcf), fh)
        except Exception as exc:
            print(f"[warn] could not write cache: {exc}")

    todo = [(lab, trs) for lab, trs in spec.tasks.items()
            if any((lab, m, a) not in data for m in spec.models for a in algos)]
    if verbose:
        print(f"[fl-fv] have {len(data)}/"
              f"{len(spec.tasks) * len(spec.models) * len(algos)}"
              f", collecting {len(todo)} task(s)")
    for label, trials in todo:
        for m in spec.models:
            for algo in algos:
                if (label, m, algo) in data:
                    continue
                data[(label, m, algo)] = task_traces(
                    spec, src, m, trials, algo, f"{algo} {label} {m}")
                for j in spec.joints:
                    jcf[(label, m, algo, j)] = joint_range_bw(
                        spec, src, m, trials, algo, j)
        save()
        if verbose:
            print(f"[fl-fv] {label} done")
    if todo:
        save()
    return data, jcf


# =============================================================================
# assembly
# =============================================================================

def _panels(spec, data, groups):
    """One panel per task. A series is a model x algorithm pair, in a FIXED
    order (model, then the algorithms as given) so the table reads the same way
    in every panel of every figure."""
    algos = [a.upper() for a in spec.algorithms]
    out = []
    for label in spec.tasks:
        series = []
        for m in spec.models:
            for algo in algos:
                trs = data.get((label, m, algo), {})
                series.append(dict(
                    name=f"{spec.label_of(m)} -- {ALGO_TAG.get(algo, algo)}",
                    short=f"{m[:9]} {ALGO_TAG.get(algo, algo)}",
                    row_key=m[:12], sub=ALGO_TAG.get(algo, algo),
                    color=spec.colour_of(m), ls=ALGO_LS.get(algo, "-"),
                    marker=ALGO_MK.get(algo, "o"),
                    data={g: t for g, t in trs.items() if g in groups}))
        out.append(dict(title=label, series=series))
    return out


def _legend(spec):
    """Model (colour) and algorithm (stroke) said separately -- one entry per
    model x algorithm would print each colour twice."""
    key = [mlines.Line2D([], [], color=spec.colour_of(m), marker="o", ls="none",
                         ms=8, label=spec.label_of(m)) for m in spec.models]
    for a in [a.upper() for a in spec.algorithms]:
        key.append(mlines.Line2D(
            [], [], color="0.3", ls=ALGO_LS.get(a, "-"),
            marker=ALGO_MK.get(a, "o"), lw=1.5, ms=7,
            label=f"{ALGO_NAME.get(a, a)} ({ALGO_TAG.get(a, a)}), "
                  "marker = peak force"))
    return key


def _annotator(spec, jcf):
    algos = [a.upper() for a in spec.algorithms]
    tags = " | ".join(ALGO_TAG.get(a, a) for a in algos)

    def annot(task):
        out = []
        for j in spec.joints:
            if j not in JOINT_POS:
                continue
            lines = [(f"{j.capitalize()} (BW)  {tags}", "0.35")]
            for m in spec.models:
                cells = []
                for a in algos:
                    r = jcf.get((task, m, a, j))
                    cells.append(f"{r[0]:.1f}-{r[1]:.1f}" if r else "  -")
                lines.append((f"{m[:9]:<9s} " + " | ".join(cells),
                              spec.colour_of(m)))
            out.append(dict(lines=lines, **JOINT_POS[j]))
        return out
    return annot


def _note(spec):
    algos = [a.upper() for a in spec.algorithms]
    bits = [f"{ALGO_TAG.get(a, a)}: {spec.method_note[a]}"
            for a in algos if a in spec.method_note]
    head = f"{spec.subject}, {spec.side} limb" if spec.subject else \
        f"{spec.side} limb"
    tail = ("beside each task pictogram: joint contact force min-max in BW, "
            "per model, " + " | ".join(ALGO_TAG.get(a, a) for a in algos))
    return " -- ".join([head] + ([";  ".join(bits)] if bits else [])) \
        + ";  " + tail


def build_fl_fv(spec, src=None, out_dir=".", split="muscle", groups=None,
                cache_path=None, refresh=False, elev=26.0, azim=-122.0,
                prefix="fig_fl_fv_surface", **kw):
    """Collect and draw. Returns the paths written.

    split "muscle"  one figure per muscle group, its pictogram and name in the
                    top-left corner
    split "all"     every group on one figure, a ROW per group with its
                    pictogram and name in the left gutter
    """
    src = src or BioscoutSource(spec.session_dir, spec)
    cache_path = cache_path or os.path.join(out_dir, ".fl_fv_traces.pkl")
    data, jcf = collect(spec, src, cache_path, refresh)

    groups = [g for g in (groups or spec.groups) if g in spec.groups]
    common = dict(colors=spec.colors(), footnote=_note(spec),
                  color_by="series", style_by="series", rows_are="series",
                  legend_handles=_legend(spec), columns=COLUMNS, rank_by=None,
                  icon_for_panel=lambda t: spec.task_icons.get(t),
                  annot_for_panel=_annotator(spec, jcf), task_icon_scale=1.6,
                  elev=elev, azim=azim, dpi=spec.dpi, save_pdf=spec.save_pdf)
    common.update(kw)

    out = []
    if split == "muscle":
        for g in groups:
            slug = g.lower().replace(" ", "_")
            out.append(plot_fl_fv_surface(
                [dict(panels=_panels(spec, data, [g]))], [g],
                out_path=os.path.join(out_dir, f"{prefix}_{slug}.png"),
                title=g, header_icon=spec.group_icons.get(g), **common))
    else:
        rows = [dict(panels=_panels(spec, data, [g]),
                     corner_icon=spec.group_icons.get(g), label=g)
                for g in groups]
        out.append(plot_fl_fv_surface(
            rows, groups, out_path=os.path.join(out_dir, f"{prefix}.png"),
            **common))
    return [p for p in out if p]
