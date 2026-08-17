"""bioscout.figures - one catalogue for every plot in this project.

Every figure that lives in the powerlifting scripts (``results.py``,
``calibration_figures.py``, ``manuscript.py``) and in bioscout itself
(``utils.ceinms.plot``, ``muscle_inspect``) is registered here ONCE, with the
inputs it needs. Nothing is re-implemented: this module only knows how to find
the builder, ask for its inputs and call it.

Two ways to use it
------------------
standalone::

    python -m bioscout.figures                # menu, prompts for what it needs
    python -m bioscout.figures --list
    python -m bioscout.figures p04 p07jcf     # run these, prompt for inputs

inside bioscout / a notebook::

    from bioscout import figures
    figures.catalog()                          # -> list of Figure
    figures.run("p04")                         # prompts for the missing inputs
    figures.run("p04", trial="Squat_BW_01")    # nothing to prompt for
    figures.menu()                             # the interactive menu

Anything you do not pass to ``run()`` is asked for with ``input()``; anything
you do pass is used as-is, so the same registry works scripted and by hand.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import os
import sys
from dataclasses import dataclass, field
from typing import Callable, List, Optional

_MISSING = object()


# =============================================================================
# 1. prompting
# =============================================================================

def _interactive() -> bool:
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except Exception:
        return False


def ask(prompt, default=None, kind="text", choices=None):
    """Ask for one value. Returns `default` when there is no terminal."""
    if choices:
        choices = list(choices)
        if not _interactive():
            return default if default is not None else choices[0]
        print(f"\n{prompt}")
        for i, c in enumerate(choices, 1):
            print(f"  {i:>3}. {c}")
        d = choices.index(default) + 1 if default in choices else 1
        raw = input(f"  pick 1-{len(choices)} [{d}]: ").strip()
        try:
            return choices[int(raw) - 1] if raw else choices[d - 1]
        except (ValueError, IndexError):
            return raw or choices[d - 1]

    if not _interactive():
        if default is None and kind != "opt":
            raise RuntimeError(f"no terminal to ask for {prompt!r} - pass it as an argument")
        return default

    tag = f" [{default}]" if default not in (None, "") else ""
    raw = input(f"  {prompt}{tag}: ").strip()
    if not raw:
        return default
    if kind == "int":
        return int(raw)
    if kind == "float":
        return float(raw)
    if kind == "bool":
        return raw.lower() in ("y", "yes", "1", "true", "t")
    if kind == "list":
        return raw.split()
    if kind == "path":
        return os.path.expanduser(raw.strip('"').strip("'"))
    return raw


@dataclass
class P:
    """One input a figure needs."""
    name: str
    prompt: str
    default: object = None
    kind: str = "text"                       # text|path|int|float|bool|list|opt
    choices: Optional[Callable] = None       # callable(state) -> list

    def resolve(self, state):
        ch = self.choices(state) if self.choices else None
        return ask(self.prompt, self.default, self.kind, ch)


@dataclass
class Figure:
    key: str
    group: str
    title: str
    fn: Callable
    params: List[P] = field(default_factory=list)
    ctx: bool = False                        # fn(ctx, **params) instead of fn(**params)


FIGURES: dict = {}


def _reg(key, group, title, fn, params=(), ctx=False):
    FIGURES[key] = Figure(key, group, title, fn, list(params), ctx)
    return FIGURES[key]


def catalog(group=None):
    return [f for f in FIGURES.values() if group in (None, f.group)]


def groups():
    out = []
    for f in FIGURES.values():
        if f.group not in out:
            out.append(f.group)
    return out


# =============================================================================
# 2. finding the powerlifting project + its scripts
# =============================================================================

_PROJECT = None
_MODS = {}

_PROJECT_GUESSES = (
    os.environ.get("POWERLIFTING_DIR", ""),
    os.environ.get("BIOSCOUT_PROJECT_DIR", ""),
    os.path.expanduser("~/ucloud/Powerlifiting"),
    r"C:\Users\Basilio\ucloud\Powerlifiting",
    os.getcwd(),
)


def project_dir(path=None):
    """Folder holding results.py / manuscript.py / calibration_figures.py."""
    global _PROJECT
    if path:
        _PROJECT = os.path.abspath(os.path.expanduser(path))
    if _PROJECT is None:
        for cand in _PROJECT_GUESSES:
            if cand and os.path.isfile(os.path.join(cand, "results.py")):
                _PROJECT = os.path.abspath(cand)
                break
    if _PROJECT is None:
        _PROJECT = ask("path to the powerlifting project (has results.py)", kind="path")
    if not os.path.isfile(os.path.join(_PROJECT, "results.py")):
        raise SystemExit(f"no results.py in {_PROJECT} - set POWERLIFTING_DIR")
    return _PROJECT


def _script(name):
    """Import <project>/<name>.py by path, once."""
    if name in _MODS:
        return _MODS[name]
    proj = project_dir()
    if proj not in sys.path:
        sys.path.insert(0, proj)
    spec = importlib.util.spec_from_file_location(name, os.path.join(proj, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, mod)
    spec.loader.exec_module(mod)
    _MODS[name] = mod
    return mod


def R():
    return _script("results")


# =============================================================================
# 3. the session context (built once, reused by every project figure)
# =============================================================================

class Ctx:
    """sess / S / L / trials / tasks for one session - what results.run() builds."""

    def __init__(self, session=None, subject=None, models=None):
        from collections import defaultdict
        r = R()
        r.apply_house_style()
        self.R = r
        self.sess = r.Session(r.find_session_yaml(session, subject))
        if models:
            self.sess.models = [m for m in self.sess.models if m in models]
        if not self.sess.models:
            raise SystemExit("no model iterations on disk for this session")
        r.sort_models(self.sess)
        r.resolve_model_colors(self.sess)
        r.set_output_dir(self.sess)
        self.S = r.Series(self.sess)
        self.L = r.Legs(self.sess, self.S)
        self.trials = self.sess.available_trials()
        tt = defaultdict(list)
        for t in self.trials:
            tt[self.sess.trial_type(t)].append(t)
        self.types_to_reps = dict(tt)
        self.tasks = [(lab, [t for t in reps if t in self.trials])
                      for lab, reps in self.sess.task_groups()]
        self.tasks = [(lab, reps) for lab, reps in self.tasks if reps]
        print(f"[figures] {self.sess.subject} / {self.sess.name} - "
              f"{len(self.sess.models)} model(s), {len(self.trials)} trial(s)")


_CTX = None


def session_ctx(session=None, subject=None, models=None, reuse=True):
    global _CTX
    if reuse and _CTX is not None and session is None and subject is None:
        return _CTX
    if session is None and subject is None and _interactive():
        subject = ask("subject (blank = any)", "", kind="opt") or None
        session = ask("session (blank = newest)", "", kind="opt") or None
    _CTX = Ctx(session, subject, models)
    return _CTX


def _trials(state):
    return state["ctx"].trials


def _ttypes(state):
    return list(state["ctx"].types_to_reps)


def _tasklabels(state):
    return [lab for lab, _ in state["ctx"].tasks]


# =============================================================================
# 4. master tables (cross-session CSVs written by `results.py --master`)
# =============================================================================

_MASTER = None


def master(reload=False):
    """{'curves','discrete','effects'} read from <project>/results/master_*.csv."""
    global _MASTER
    if _MASTER is not None and not reload:
        return _MASTER
    import pandas as pd
    root = os.path.join(project_dir(), "results")
    out = {}
    for name in ("curves", "discrete", "effects"):
        df = None
        for cand in (f"master_{name}.csv.gz", f"master_{name}.csv"):
            fp = os.path.join(root, cand)
            if os.path.isfile(fp):
                df = pd.read_csv(fp)
                print(f"  <- results/{cand} ({len(df):,} rows)")
                break
        if df is None:
            print(f"  [warn] results/master_{name}.csv missing "
                  f"- run: python results.py --master")
            df = pd.DataFrame()
        out[name] = df
    _MASTER = out
    return out


def _master_out():
    r = R()
    r.apply_house_style()
    r.set_output_dir_path(r.MASTER_FIG_DIR)


# =============================================================================
# 5. THE CATALOGUE
# =============================================================================

TRIAL = P("trial", "trial", None, choices=_trials)
TTYPE = P("ttype", "trial type", None, choices=_ttypes)

# ---- 5a. per-session report figures (results.py) ---------------------------
_reg("p01", "session", "marker tracking errors",
     lambda c: c.R.fig_01_marker_errors(c.sess, c.S, c.trials), ctx=True)
_reg("p02", "session", "kinematics + joint moments (one trial)",
     lambda c, trial: c.R.fig_02_kin_mom(c.sess, c.S, trial), [TRIAL], ctx=True)
_reg("p03", "session", "moment arms (one trial)",
     lambda c, trial: c.R.fig_02b_moment_arms(c.sess, c.S, trial), [TRIAL], ctx=True)
_reg("p04", "session", "muscle dynamics: force / activation / length (one trial)",
     lambda c, trial: c.R.fig_04_muscle_dynamics(c.sess, c.S, trial), [TRIAL], ctx=True)
_reg("p05", "session", "session summary (all trial types)",
     lambda c: c.R.fig_05_summary(c.sess, c.S, c.types_to_reps), ctx=True)
_reg("p06", "session", "calibration compare (CEINMS subject files)",
     lambda c: c.R.fig_06_calibration_compare(c.sess), ctx=True)
_reg("p08", "session", "muscle moments vs ID (one trial)",
     lambda c, trial: c.R.fig_08_muscle_moments(c.sess, c.S, trial), [TRIAL], ctx=True)
_reg("p09", "session", "calibration fit",
     lambda c, trial: c.R.fig_09_calibration(c.sess, trial or None),
     [P("trial", "trial (blank = default)", "", kind="opt")], ctx=True)

_reg("p07kin", "session", "trial-type average: kinematics + moments",
     lambda c, ttype: c.R.fig_07_avg_kin_mom(c.sess, c.S, ttype, c.types_to_reps[ttype]),
     [TTYPE], ctx=True)
_reg("p07ma", "session", "trial-type average: moment arms",
     lambda c, ttype: c.R.fig_07_avg_moment_arms(c.sess, c.S, ttype, c.types_to_reps[ttype]),
     [TTYPE], ctx=True)
_reg("p07dyn", "session", "trial-type average: muscle dynamics",
     lambda c, ttype: c.R.fig_07_avg_muscle_dyn(c.sess, c.S, ttype, c.types_to_reps[ttype]),
     [TTYPE], ctx=True)
_reg("p07jrf", "session", "trial-type average: joint reaction forces",
     lambda c, ttype: c.R.fig_07_avg_jrf(c.sess, c.S, ttype, c.types_to_reps[ttype]),
     [TTYPE], ctx=True)

# ---- 5b. session / task summary panels -------------------------------------
_reg("s_session", "summary", "session summary panels (all tasks)",
     lambda c: c.R.build_session_figures(c.sess, c.L, c.tasks), ctx=True)
_reg("s_tasks", "summary", "task summary figure",
     lambda c: c.R.build_tasks_figure(c.sess, c.L, c.tasks), ctx=True)
_reg("s_kin", "summary", "kinematics summary figure",
     lambda c: c.R.build_kinematics_figure(c.sess, c.L, c.tasks), ctx=True)
_reg("s_jcf_angle", "summary", "JCF compass (force vs joint angle, bone silhouette)",
     lambda c: c.R.build_jcf_angle_figure(c.sess, c.L, c.tasks), ctx=True)
_reg("s_moments", "summary", "muscle-moment figures (per DOF)",
     lambda c: c.R.build_muscle_moment_figures(c.sess, c.L, c.tasks), ctx=True)
_reg("s_poster", "summary", "poster",
     lambda c, task, rerender: c.R.build_poster(c.sess, c.L, c.tasks,
                                                task=task or None, rerender=rerender),
     [P("task", "task (blank = all)", "", kind="opt"),
      P("rerender", "force re-render? y/N", False, kind="bool")], ctx=True)
_reg("s_all", "summary", "EVERYTHING for this session (results.py run)",
     lambda c, groups: c.R.run(session=c.sess.name, subject=c.sess.subject,
                               groups=groups or None),
     [P("groups", "groups, space separated (blank = default)", "", kind="list")], ctx=True)

# ---- 5c. calibration (calibration_figures.py) ------------------------------


def _cal(session, subject, trial, side, only, report):
    argv = ["--trial", trial, "--side", side, "--only", only, "--report", report]
    if session:
        argv += ["--session", session]
    if subject:
        argv += ["--subject", subject]
    return _script("calibration_figures").main(argv)


_reg("cal", "calibration", "CEINMS calibration fit + MTU parameters", _cal,
     [P("session", "session (blank = newest)", "", kind="opt"),
      P("subject", "subject (blank = any)", "", kind="opt"),
      P("trial", "trial for the moment-capacity panel", "Squat_BW_01"),
      P("side", "side", "both", choices=lambda s: ["both", "r", "l"]),
      P("only", "which panels", "both", choices=lambda s: ["both", "fit", "params"]),
      P("report", "iteration to report", "best", choices=lambda s: ["best", "last"])])

# ---- 5d. cross-session (master) figures ------------------------------------
METRIC = P("metric", "metric", "peak_JCF_BW")


def _m(fn_name, key):
    """Wrap a master figure that takes one of the master dataframes."""
    def call(**kw):
        _master_out()
        return getattr(R(), fn_name)(master()[key], **kw)
    return call


_reg("m_all", "master", "redraw EVERY master figure from the CSVs on disk",
     lambda: R().rebuild_master_figures())
_reg("m_rescan", "master", "re-scan every session, rewrite master tables + figures",
     lambda subject, session: R().run_master(subject=subject or None,
                                             session=session or None),
     [P("subject", "subject (blank = all)", "", kind="opt"),
      P("session", "session (blank = all)", "", kind="opt")])

_reg("m_heatmap", "master", "effect heatmap", _m("fig_master_effect_heatmap", "effects"),
     [METRIC])
_reg("m_dumbbell", "master", "effect dumbbell (per lift)",
     _m("fig_master_effect_dumbbell", "effects"),
     [METRIC, P("lift", "lift (blank = all)", None, kind="opt")])
_reg("m_effects", "master", "effects combined (one subject, all tasks)",
     _m("fig_master_effects_combined", "effects"),
     [METRIC, P("subject", "subject (blank = pooled)", None, kind="opt")])
_reg("m_peak_jcf", "master", "peak JCF by model",
     _m("fig_master_peak_jcf", "discrete"),
     [P("metric", "metric", "peak"), P("variable", "variable", "jcf")])
_reg("m_factors", "master", "factor effects (geometry / coordination)",
     _m("fig_master_factor_effects", "discrete"),
     [P("variable", "variable", "jcf"), P("metric", "metric", "peak")])
_reg("m_ranking", "master", "muscle ranking",
     _m("fig_master_muscle_ranking", "discrete"),
     [P("lift", "lift (blank = all)", None, kind="opt"),
      P("top", "how many muscles", 10, kind="int"),
      P("metric", "metric", "peak_pct_MIF")])
_reg("m_work", "master", "muscle work ranks",
     _m("fig_muscle_work_ranks", "discrete"),
     [P("phase", "phase", "conc", choices=lambda s: ["conc", "ecc"]),
      P("subject", "subject (blank = pooled)", None, kind="opt"),
      P("task", "task (blank = all)", None, kind="opt")])
_reg("m_rank_shift", "master", "rank shift between models",
     _m("fig_master_rank_shift", "discrete"),
     [P("subject", "subject (blank = pooled)", None, kind="opt"),
      P("top", "how many muscles", 14, kind="int")])
_reg("m_model_effects", "master", "model effects (moment tracking error)",
     _m("fig_master_model_effects", "discrete"),
     [P("metric", "metric", "vs_ID_RMSE_pct"),
      P("subject", "subject (blank = pooled)", None, kind="opt")])
_reg("m_model_effects_jcf", "master", "model effects (JCF)",
     _m("fig_master_model_effects_jcf", "discrete"),
     [P("metric", "metric", "mean"),
      P("subject", "subject (blank = pooled)", None, kind="opt")])
_reg("m_model_effects_work", "master", "model effects (muscle work)",
     _m("fig_master_model_effects_work", "discrete"),
     [P("phase", "phase", "conc", choices=lambda s: ["conc", "ecc"]),
      P("subject", "subject (blank = pooled)", None, kind="opt")])
_reg("m_errors", "master", "error by model",
     _m("fig_master_error_by_model", "discrete"),
     [P("family", "family", "moment", choices=lambda s: ["moment", "marker"])])
_reg("m_ms_errors", "master", "manuscript error figure",
     _m("fig_manuscript_errors", "discrete"))
_reg("m_curves", "master", "curve overlay (all models)",
     _m("fig_master_curve_overlay", "curves"),
     [P("variable", "variable", "jcf")])
_reg("m_curve_diff", "master", "curve difference SO vs CEINMS",
     _m("fig_master_curve_diff", "curves"),
     [P("variable", "variable", "jcf"),
      P("a_from", "from algorithm", "SO"), P("a_to", "to algorithm", "CEINMS")])
_reg("m_kin_overlay", "master", "kinematics overlay",
     _m("fig_master_kinematics_overlay", "curves"))
_reg("m_force_curves", "master", "muscle force curves",
     _m("fig_master_muscle_force_curves", "curves"),
     [P("subject", "subject (blank = pooled)", None, kind="opt"),
      P("variable", "variable", "force")])

# ---- 5e. manuscript figures (manuscript.py) --------------------------------


def _MS():
    return _script("manuscript")


_reg("ms_setup", "manuscript", "fig01 model setup (tasks + design)",
     lambda session, show: _MS().make_setup_figure(session=session or None, show=show),
     [P("session", "session (blank = newest)", "", kind="opt"),
      P("show", "show on screen? y/N", False, kind="bool")])
_reg("ms_metrics", "manuscript", "fig05 metric summary",
     lambda facet: _MS().make_metric_summary(facet=facet),
     [P("facet", "facet", "joint")])
_reg("ms_metrics_task", "manuscript", "metric summary by task",
     lambda: _MS().make_metric_summary_by_task())
_reg("ms_forces", "manuscript", "fig07 muscle force summary",
     lambda: _MS().make_muscle_force_summary())
_reg("ms_task_panel", "manuscript", "task panel",
     lambda task, show: _MS().make_task_panel(task, show=show),
     [P("task", "task"), P("show", "show on screen? y/N", False, kind="bool")])
_reg("ms_overview", "manuscript", "model overview table/figure",
     lambda session: _MS().model_overview(session=session or None),
     [P("session", "session (blank = newest)", "", kind="opt")])
_reg("ms_plot_metric", "manuscript", "quick bar/box of any metric CSV column",
     lambda metric, kind: _MS().plot_metric(metric=metric, kind=kind),
     [P("metric", "metric", "peak_JCF_BW"),
      P("kind", "kind", "bar", choices=lambda s: ["bar", "box", "strip"])])
_reg("ms_plot_curve", "manuscript", "quick curve from the curves CSV",
     lambda variable, channel, task, algo: _MS().plot_curve(
         variable=variable, channel=channel, task=task or None, algo=algo),
     [P("variable", "variable", "jcf"), P("channel", "channel", "knee"),
      P("task", "task (blank = all)", "", kind="opt"), P("algo", "algorithm", "SO")])

# ---- 5f. bioscout: CEINMS plots --------------------------------------------
_CEINMS = [
    ("c_loop", "CEINMS calibration loop results", "plot_loop_results",
     P("CSVresultsPath", "calibration results CSV", None, kind="path")),
    ("c_params", "CEINMS model parameters", "plot_ceinms_model_parameters",
     P("ceinmsModelPath", "CEINMS subject .xml", None, kind="path")),
    ("c_moments", "CEINMS moment tracking", "plot_moments_calibration_results",
     P("momentResultsCSV", "moment results CSV", None, kind="path")),
    ("c_calres", "CEINMS calibration results (from setup xml)", "plot_ceinms_calibration_results",
     P("setupXML_path", "calibration setup .xml", None, kind="path")),
    ("c_opt", "CEINMS optimisation results", "plot_optimisation_results",
     P("optimisationOutputDir", "optimisation output dir", None, kind="path")),
    ("c_forces", "CEINMS muscle forces", "plot_ceinms_muscle_forces",
     P("ceinmsForcesFile", "CEINMS forces .sto", None, kind="path")),
]
for _k, _t, _fn, _p in _CEINMS:
    def _mk(fn=_fn):
        def call(**kw):
            from bioscout.utils.ceinms import plot as CP
            return getattr(CP, fn)(**kw)
        return call
    _reg(_k, "ceinms", _t, _mk(), [_p])

_reg("c_compare", "ceinms", "CEINMS model parameters: uncalibrated vs calibrated",
     lambda uncalibratedModelPath, calibratedModelPath: _mod("bioscout.utils.ceinms.plot").plot_compare_ceinms_models(
         uncalibratedModelPath, calibratedModelPath),
     [P("uncalibratedModelPath", "uncalibrated subject .xml", None, kind="path"),
      P("calibratedModelPath", "calibrated subject .xml", None, kind="path")])
_reg("c_emg", "ceinms", "experimental EMG vs CEINMS excitations",
     lambda emgFile: _mod("bioscout.utils.ceinms.plot").plot_experimental_vs_ceinms(emgFile),
     [P("emgFile", "EMG .sto/.mot", None, kind="path")])

# ---- 5g. bioscout: muscle_inspect ------------------------------------------
MODEL = P("model", "OpenSim .osim model", None, kind="path")
OUT = P("out_dir", "output folder", "muscle_inspect_out", kind="path")
SIDE = P("side", "side", "_r", choices=lambda s: ["_r", "_l"])


def _mod(path):
    """Import a bioscout submodule by dotted path."""
    return importlib.import_module(path)


def _lit(name=None):
    from bioscout.muscle_inspect.paths import LITERATURE_MOMENT_ARMS_CSV
    d = os.path.dirname(LITERATURE_MOMENT_ARMS_CSV)
    return LITERATURE_MOMENT_ARMS_CSV if name is None else os.path.join(d, name)


def _mi_all(model, out_dir, side, n):
    from bioscout.muscle_inspect import muscle_length_validation as V, strength as S
    from bioscout.muscle_inspect.paths import validation_dir
    out = validation_dir(model, out=out_dir or None,
                         base=os.path.splitext(os.path.basename(model))[0])
    os.makedirs(out, exist_ok=True)
    lit, scsv, grp = _lit(), _lit("literature_strength.csv"), _lit("muscle_functions.csv")
    V.run_validation(model, lit, out, side=side, n=n)
    V.run_fibre_validation(model, lit, out, side=side, n=max(30, n // 2))
    S.run_strength(model, scsv, grp, out, side=side, n=40)
    S.run_isokinetic(model, scsv, grp, scsv, out, side=side)
    print(f"[figures] full model validation -> {out}")
    return out


_reg("mi_all", "model", "FULL model validation: moment arms + fibre + strength", _mi_all,
     [MODEL, P("out_dir", "output folder (blank = next to the model)", "", kind="opt"),
      SIDE, P("n", "samples per coordinate", 60, kind="int")])
_reg("mi_ma", "model", "moment arms vs literature",
     lambda model, out_dir, side, n: _mod("bioscout.muscle_inspect.validation").run_validation(model, _lit(), out_dir, side=side, n=n),
     [MODEL, OUT, SIDE, P("n", "samples per coordinate", 60, kind="int")])
_reg("mi_fibre", "model", "fascicle length + pennation vs literature",
     lambda model, out_dir, side, n: _mod("bioscout.muscle_inspect.muscle_length_validation").run_fibre_validation(model, _lit(), out_dir, side=side, n=n),
     [MODEL, OUT, SIDE, P("n", "samples per coordinate", 40, kind="int")])
_reg("mi_strength", "model", "isometric joint strength vs literature MVC",
     lambda model, out_dir, side, n: _mod("bioscout.muscle_inspect.strength").run_strength(model, _lit("literature_strength.csv"),
                    _lit("muscle_functions.csv"), out_dir, side=side, n=n),
     [MODEL, OUT, SIDE, P("n", "samples per coordinate", 40, kind="int")])
_reg("mi_isok", "model", "isokinetic joint strength vs literature",
     lambda model, out_dir, side: _mod("bioscout.muscle_inspect.strength").run_isokinetic(model, _lit("literature_strength.csv"),
                      _lit("muscle_functions.csv"),
                      _lit("literature_strength.csv"), out_dir, side=side),
     [MODEL, OUT, SIDE])
_reg("mi_motion", "model", "moment arm vs joint angle over a trial (wrap QC)",
     lambda ma, ik, out_dir, side, min_ma_mm, min_jump_mm: _mod("bioscout.muscle_inspect.moment_arm_motion").inspect_moment_arms_over_motion(ma, ik, out_dir=out_dir or None, side=side,
                                       min_ma_mm=min_ma_mm, min_jump_mm=min_jump_mm),
     [P("ma", "muscle_analysis/ folder", None, kind="path"),
      P("ik", "IK joint_angles.mot", None, kind="path"),
      P("out_dir", "output folder (blank = next to --ma)", "", kind="opt"),
      SIDE, P("min_ma_mm", "min peak |MA| (mm)", 3.0, kind="float"),
      P("min_jump_mm", "discontinuity sensitivity (mm)", 1.0, kind="float")])
_reg("mi_jcf_lit", "model", "JCF vs literature bands",
     lambda out_path, entity: _mod("bioscout.muscle_inspect.literature_jcf").plot_jcf_validation(out_path, entity=entity),
     [P("out_path", "output .png", "jcf_validation.png", kind="path"),
      P("entity", "joint", "knee", choices=lambda s: ["hip", "knee", "ankle"])])


# =============================================================================
# 6. running
# =============================================================================

def run(key, **kw):
    """Run one figure. Missing inputs are prompted for."""
    if key not in FIGURES:
        raise SystemExit(f"unknown figure {key!r} - try figures.list_figures()")
    f = FIGURES[key]
    state = {}
    if f.ctx:
        state["ctx"] = session_ctx(kw.pop("session", None), kw.pop("subject", None),
                                   kw.pop("models", None))
    print(f"\n=== {f.key}: {f.title}")
    vals = {}
    for p in f.params:
        v = kw.get(p.name, _MISSING)
        vals[p.name] = p.resolve(state) if v is _MISSING else v
    out = f.fn(state["ctx"], **vals) if f.ctx else f.fn(**vals)
    print(f"    done -> {out}")
    return out


def run_many(keys, **kw):
    made = {}
    for k in keys:
        try:
            made[k] = run(k, **kw)
        except Exception as exc:
            print(f"    [FAILED] {k}: {type(exc).__name__}: {exc}")
    return made


def list_figures(group=None):
    for g in ([group] if group else groups()):
        print(f"\n{g}:")
        for f in catalog(g):
            needs = ", ".join(p.name for p in f.params) or "-"
            print(f"  {f.key:<16} {f.title:<58} ({needs})")


def menu():
    """Interactive picker: numbers, keys, a group name, or 'all'."""
    figs = list(FIGURES.values())
    if not _interactive():
        print("no terminal - listing instead of prompting")
        list_figures()
        return {}
    print("\n" + "=" * 78)
    print("bioscout figures")
    print("=" * 78)
    n = 0
    last = None
    for f in figs:
        if f.group != last:
            print(f"\n-- {f.group} --")
            last = f.group
        n += 1
        print(f"  {n:>3}. {f.key:<16} {f.title}")
    print(f"\n  groups: {', '.join(groups())}")
    raw = input("\npick numbers/keys/group (space separated, 'all', blank = quit): ").strip()
    if not raw:
        return {}
    keys = []
    for tok in raw.split():
        if tok == "all":
            keys = [f.key for f in figs]
            break
        if tok in groups():
            keys += [f.key for f in catalog(tok)]
        elif tok in FIGURES:
            keys.append(tok)
        elif tok.isdigit() and 1 <= int(tok) <= len(figs):
            keys.append(figs[int(tok) - 1].key)
        else:
            print(f"  [skip] {tok!r} is not a figure")
    return run_many(keys)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m bioscout.figures",
                                 description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("keys", nargs="*", help="figure keys or group names (blank = menu)")
    ap.add_argument("--list", action="store_true", help="list every figure and exit")
    ap.add_argument("--project", help="powerlifting project folder (has results.py)")
    ap.add_argument("--session")
    ap.add_argument("--subject")
    a = ap.parse_args(argv)

    if a.project:
        project_dir(a.project)
    if a.list:
        list_figures()
        return
    kw = {k: v for k, v in (("session", a.session), ("subject", a.subject)) if v}
    if not a.keys:
        return menu()
    keys = []
    for tok in a.keys:
        keys += [f.key for f in catalog(tok)] if tok in groups() else [tok]
    return run_many(keys, **kw)


if __name__ == "__main__":
    main()
