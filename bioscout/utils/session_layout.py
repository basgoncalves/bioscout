"""Session-centric layout runner (new YAML layout).

Drives a session from its ``session.yaml`` over the SHARED ``experimental/``
inputs and per-ITERATION output folders::

    <session>/c3dfiles/<trial>.c3d                 # raw captures
    <session>/experimental/<trial>/...             # processed inputs, model-independent, ONCE
    <session>/<iteration>/model.osim               # this iteration's scaled model (CEINMS/base)
    <session>/<iteration>/model_so.osim            # + isometric x factor (SO)
    <session>/<iteration>/<trial>/...              # IK/ID/MA/SO/CEINMS/JCF (model-dependent)
    <session>/<iteration>/ceinms_calibration/      # model-specific

The trick that avoids rewriting ``Analyse``: an Analyse resolves every path as
``os.path.join(self.path, <relative>)``. If we set its RAW-input attributes to
ABSOLUTE paths under ``experimental/<trial>/``, they resolve there, while every
DERIVED output stays under the iteration's trial folder (``self.path``). So one
Analyse per (iteration, trial) reads shared raw inputs and writes model-specific
results — no duplication.
"""
from __future__ import annotations

import os

from .session_yaml import read_session

# ---------------------------------------------------------------------------
# path resolver
# ---------------------------------------------------------------------------
def experimental_dir(session_dir, trial):
    return os.path.join(session_dir, "experimental", trial)

def c3d_path(session_dir, trial):
    return os.path.join(session_dir, "c3dfiles", f"{trial}.c3d")

def iteration_dir(session_dir, iteration):
    return os.path.join(session_dir, iteration)

def derived_trial_dir(session_dir, iteration, trial):
    return os.path.join(session_dir, iteration, trial)

# RAW input attribute -> filename in experimental/<trial>/. These are the
# model-INDEPENDENT files; everything else an Analyse writes is derived output.
_RAW_ATTR_FILES = {
    "markers": "marker_experimental.trc",
    "grf_mot": "grf.mot",
    "setup_grf": "GRF.xml",
    "emg": "emg.mot",
    "analog": "analog.csv",
    "emg_filtered": "emg_filtered.mot",
    "emg_filtered_normalised": "emg_filtered_normalised.mot",
    "ceinms_excitations": "emg_filtered_normalised.mot",
}

def bind_experimental(trial_obj, exp_dir):
    """Point an Analyse's raw-input attributes at ``exp_dir`` (absolute), so it
    reads shared experimental inputs but writes derived outputs under its own
    folder. Only sets attributes the object already has."""
    for attr, fname in _RAW_ATTR_FILES.items():
        if hasattr(trial_obj, attr):
            setattr(trial_obj, attr, os.path.join(exp_dir, fname))
    return trial_obj


def resolve_generic(name, project_dir, models_dir=None):
    """Resolve a `generic` value against the shared library, then models/, then root."""
    if not name:
        return None
    if os.path.isabs(name) and os.path.exists(name):
        return name
    bases = [os.path.join(project_dir, "generic models"),
             os.path.join(project_dir, "generic_models")]
    if models_dir:
        bases.append(str(models_dir))
    bases.append(project_dir)
    for b in bases:
        cand = os.path.join(b, name)
        if os.path.exists(cand):
            return cand
    return os.path.join(project_dir, "generic models", name)  # best guess


def resolve_session_model(name, session_dir, project_dir):
    """Resolve a `session_model` value (session-relative first, then generic lib)."""
    if not name:
        return None
    if os.path.isabs(name) and os.path.exists(name):
        return name
    for b in (session_dir, os.path.join(project_dir, "generic models"), project_dir):
        cand = os.path.join(b, name)
        if os.path.exists(cand):
            return cand
    return os.path.join(session_dir, name)


def first_frames_range(exp_dir, frames):
    """Return ``[t0, t_{frames-1}]`` from a trial's time column (grf/marker/emg)
    for a quick GHOST run over just the first ``frames`` samples."""
    import pandas as _pd
    from bioscout import utils as _u
    for fn in ("grf.mot", "marker_experimental.trc", "emg_filtered_normalised.mot"):
        fp = os.path.join(exp_dir, fn)
        if not os.path.exists(fp):
            continue
        try:
            df = _u.load_any_data_file(fp)
            tcol = next((c for c in df.columns if c.lower() == "time"), None)
            if tcol is None:
                continue
            tv = _pd.to_numeric(df[tcol], errors="coerce").dropna().to_numpy()
            if len(tv) >= 2:
                k = max(1, min(int(frames), len(tv)) - 1)
                return [float(tv[0]), float(tv[k])]
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# scaling: build one iteration's model.osim / model_so.osim from its recipe
# ---------------------------------------------------------------------------
def scale_iteration(spec_model, session_dir, project_dir, utils, static_trc,
                    markerset=None, replace=True):
    """Produce ``<iteration>/model.osim`` (+ ``model_so.osim``) from a Model recipe.

    Honours: session_model (skip geometric scale), linear_scaling / marker_placer,
    opt_neval (Modenese muscle-opt vs `generic`), mvic_factor (isometric x factor).
    Returns (model_ceinms_path, model_so_path)."""
    import shutil
    _os = utils.openSim
    it_dir = iteration_dir(session_dir, spec_model.name)
    os.makedirs(it_dir, exist_ok=True)

    generic = resolve_generic(spec_model.generic_model, project_dir, getattr(utils, "MODELS_DIR", None))
    provided = resolve_session_model(spec_model.session_model, session_dir, project_dir)

    n_eval = int(spec_model.opt_neval or 10)
    factor = float(spec_model.mvic_factor or 1.0)
    # Output model filenames: use the iteration's authored ceinms_model / so_model
    # (descriptive scaling-output names), else sensible defaults.
    ceinms_name = spec_model.model_ceinms or f"scaled_opt_N{n_eval}.osim"
    so_name = spec_model.model or f"scaled_opt_N{n_eval}_mvicx{factor:.2f}.osim"
    base = os.path.join(it_dir, ceinms_name)          # CEINMS/base model
    so = os.path.join(it_dir, so_name)                # SO (strength-increased) model
    if os.path.exists(base) and os.path.exists(so) and not replace:
        print(f"  [scale skip] {spec_model.name}: models exist ({ceinms_name}, {so_name})")
        return base, so

    # 1) model that muscle-opt starts from
    scaled = os.path.join(it_dir, "scaled.osim")
    linear = bool(spec_model.linear_scaling)
    placer = bool(spec_model.marker_placer)
    scale_input = provided or generic
    if provided:
        linear = False                                # provided model: never dimensionally scale
        print(f"  [scale] {spec_model.name}: provided/session model (no geometric scaling)")
    _os.scale_model(scale_input, static_trc, scaled, scale_setup_output_dir=it_dir,
                    marker_set_file=markerset, linear_scaling=linear, marker_placer=placer)

    # 2) muscle-opt (Modenese) against the generic reference -> base (CEINMS) model
    _os.muscle_optimimizer_Modenese2015(scaled, save_path=base,
                                        ref_model_path=generic, N_eval=n_eval)

    # 3) isometric-force x factor -> SO model
    if factor and factor != 1.0:
        _os.increase_isometric_force(base, muscleList="all", factor=factor)
        produced = base.replace(".osim", f"_increased_{factor:.2f}.osim")
        if os.path.exists(produced):
            shutil.copyfile(produced, so)
    else:
        shutil.copyfile(base, so)
    print(f"  [scale OK] {spec_model.name} -> model.osim (+ model_so.osim)")
    return base, so


# ---------------------------------------------------------------------------
# run one iteration over all trials (SO stage), reading shared experimental/
# ---------------------------------------------------------------------------
def run_iteration_so(project, spec, spec_model, session_dir, trials, replace=True, frames=None):
    """IK -> ID -> MA -> SO -> muscle moments -> JRA for one iteration, per trial.
    Reads raw from experimental/<trial>/, writes derived into <iteration>/<trial>/."""
    utils = project.utils
    Trial = getattr(project, "subject", None)  # placeholder; use Analyse directly
    from bioscout.utils.analysis import _trial_class
    Analyse = _trial_class()

    so_name = spec_model.model or "scaled_opt_N10_mvicx3.00.osim"   # SO uses the strength model
    so_model = os.path.join(iteration_dir(session_dir, spec_model.name), so_name)
    _bs = getattr(project.settings, "BatchSettings", None)
    setup_dir = str(getattr(_bs, "setup_files_folder", None)
                    or os.path.join(str(project.dir), "setupFiles"))
    # static trial is for scaling only — never run the analysis pipeline on it
    _static = spec.static_trial
    trials = [t for t in trials if t != _static
              and (spec.trials.get(t) or {}).get("type") != "static"]
    done = []
    for tn in trials:
        dd = derived_trial_dir(session_dir, spec_model.name, tn)
        os.makedirs(dd, exist_ok=True)
        try:
            t = Analyse(dd)
            t.subject = "Athlete"; t.session = os.path.basename(session_dir)
            t.update_model(so_model)                  # SO uses the strength model
            # Durable hooks: raw inputs from shared experimental/<trial>/ and the
            # shared setup templates dir; re-applied on every load_settings.
            t.experimental_dir = experimental_dir(session_dir, tn)
            t._session_setup_dir = setup_dir
            t._apply_inputs_layout()                  # apply now (before first run step)
            # time window for the SIMULATION (inputs stay full length). GHOST run:
            # cap to the first `frames` samples; else use the session spec window.
            tr = (spec.trials.get(tn) or {}).get("time_range")
            if frames:
                tr = first_frames_range(experimental_dir(session_dir, tn), frames) or tr
            if tr:
                t.time_range = tr
                t.update_trial_attribute("time_range", tr)
            t.update_trial_attribute("replace", replace)
            os.chdir(t.path)   # ensure cwd = trial dir (skipped steps don't chdir)
            _tag = f"{spec_model.name}/{tn}"
            t.run_ik(replace=replace);   print(f"  [{_tag}] IK done", flush=True)
            t.run_id(replace=replace);   print(f"  [{_tag}] ID done", flush=True)
            t.run_ma(replace=replace);   print(f"  [{_tag}] MA done", flush=True)
            t.run_so(replace=replace);   print(f"  [{_tag}] SO done", flush=True)
            t.calculate_muscle_moments(forces_type="so")
            t.run_jra(replace=replace);  print(f"  [{_tag}] JRA done", flush=True)
            done.append(tn)
            print(f"  [SO ok] {_tag}", flush=True)
        except Exception as e:
            print(f"  [SO ERROR] {spec_model.name}/{tn}: {e}")
    return done


# ---------------------------------------------------------------------------
# import already-scaled models from the OLD models/<subject>/<session>/ layout
# ---------------------------------------------------------------------------
def import_models(session_path, models_dir, mapping, replace=True):
    """Copy existing scaled models into the new iteration folders so scaling can
    be skipped (``run_session(do_scale=False)``).

    ``mapping`` = ``{iteration_name: old_subject_folder}``, e.g.
    ``{"cateli": "Athlete_03_Cateli", ...}``. For each, picks the ``*_opt_*``
    model as the base (CEINMS) model and the ``*mvic*`` / ``*increased*`` model
    as the SO model (falls back to the base if there is only one), and writes
    them as ``<session>/<iteration>/model.osim`` and ``model_so.osim``.
    """
    import glob, shutil
    from .session_yaml import read_session
    try:
        spec = read_session(session_path)
    except Exception:
        spec = None
    sess_name = os.path.basename(os.path.abspath(session_path))
    for it, old in mapping.items():
        src_dir = os.path.join(str(models_dir), old, sess_name)
        osims = sorted(glob.glob(os.path.join(src_dir, "*.osim")))
        if not osims:
            print(f"[import] {it}: no .osim in {src_dir}"); continue
        # source models: strength (mvic/increased) and base (the *_opt_* without those)
        src_so = next((f for f in osims if ("mvic" in os.path.basename(f).lower()
                                            or "increased" in os.path.basename(f).lower())), None)
        src_base = next((f for f in osims if "opt" in os.path.basename(f).lower()
                         and "mvic" not in os.path.basename(f).lower()
                         and "increased" not in os.path.basename(f).lower()), None)
        if src_base is None:
            src_base = next((f for f in osims if f != src_so), osims[0])
        if src_so is None:
            src_so = src_base
        # TARGET filenames from the yaml (ceinms_model / so_model); fall back to source names
        m = spec.get_model(it) if spec else None
        ceinms_name = (m.model_ceinms if m and m.model_ceinms else os.path.basename(src_base))
        so_name = (m.model if m and m.model else os.path.basename(src_so))
        it_dir = iteration_dir(session_path, it)
        os.makedirs(it_dir, exist_ok=True)
        dst_base = os.path.join(it_dir, ceinms_name)
        dst_so = os.path.join(it_dir, so_name)
        if (os.path.exists(dst_base) and os.path.exists(dst_so)) and not replace:
            print(f"[import] {it}: models already present, skip"); continue
        shutil.copyfile(src_base, dst_base); shutil.copyfile(src_so, dst_so)
        print(f"[import] {it}: {os.path.basename(src_base)} -> {ceinms_name} | "
              f"{os.path.basename(src_so)} -> {so_name}")


# ---------------------------------------------------------------------------
# CEINMS for one iteration over all trials (new layout)
# ---------------------------------------------------------------------------
def run_iteration_ceinms(project, spec, spec_model, session_dir, trials, replace=True, frames=None):
    """CEINMS calibration + per-trial execution for one iteration.

    Calibration is model-specific -> <iteration>/ceinms_calibration/. Uses
    spec.calibration_trials (bridged into settings so the calibration collector
    picks them up), the base (ceinms) model, and reads shared EMG from
    experimental/. Pre-builds each calibration trial's inputData (experimental-
    bound) so calibration collects them without needing per-sibling binding.
    """
    from bioscout.utils.analysis import _trial_class
    Analyse = _trial_class()
    utils = project.utils
    it = spec_model.name
    ceinms_model = os.path.join(iteration_dir(session_dir, it),
                                spec_model.model_ceinms or "scaled_opt_N10.osim")

    # static trial is for scaling only — exclude from CEINMS
    _static = spec.static_trial
    here = [t for t in trials if t != _static
            and (spec.trials.get(t) or {}).get("type") != "static"]
    calib = [t for t in (spec.calibration_trials or []) if t in here] or here
    _bs = getattr(project.settings, "BatchSettings", None)
    setup_dir = str(getattr(_bs, "setup_files_folder", None)
                    or os.path.join(str(project.dir), "setupFiles"))

    def _mk(tn):
        t = Analyse(derived_trial_dir(session_dir, it, tn))
        t.subject = "Athlete"; t.session = os.path.basename(session_dir)
        t.update_model(ceinms_model)
        t.experimental_dir = experimental_dir(session_dir, tn)
        t._session_setup_dir = setup_dir
        t._apply_inputs_layout()
        t.update_trial_attribute("replace", replace)
        if frames:   # GHOST run: cap CEINMS window (inputs stay full length)
            _tr = first_frames_range(experimental_dir(session_dir, tn), frames)
            if _tr:
                t.time_range = _tr
                t.update_trial_attribute("time_range", _tr)
        os.chdir(t.path)   # ensure cwd = trial dir for setup/output writes
        return t

    # bridge session calibration trials into settings for the collector
    cs = getattr(getattr(utils, "settings", None), "CEINMSSettings", None)
    old = getattr(cs, "calibration_trial_names", None) if cs is not None else None
    try:
        if cs is not None:
            cs.calibration_trial_names = list(calib)
        import glob as _glob
        calibrated = os.path.join(iteration_dir(session_dir, it),
                                  "ceinms_calibration", "subjectCalibrated.xml")
        # ---- calibration: only when replace, or not yet done ----
        if replace or not os.path.exists(calibrated):
            # Pre-build inputData for the NON-driver calibration trials (bound to
            # experimental/); the driver (calib[0]) builds its own inside
            # run_ceinms_calibration, so skip it here to avoid a double build.
            for tn in calib[1:]:
                try:
                    _mk(tn).create_ceinms_input_data()
                    print(f"  [{it}/{tn}] CEINMS input data built", flush=True)
                except Exception as e:
                    print(f"  [{it}/{tn}] CEINMS input build ERROR: {e}", flush=True)
            host = _mk(calib[0])
            host.run_ceinms_calibration()
            print(f"  [{it}] CEINMS calibrated (trials={calib})", flush=True)
        else:
            print(f"  [{it}] CEINMS calibration already done -> skip (replace=False)", flush=True)
        # ---- per-trial execution: only when replace, or not yet done ----
        for tn in here:
            exe_done = _glob.glob(os.path.join(derived_trial_dir(session_dir, it, tn),
                                               "ceinms", "Execution_*", "MuscleForces.sto"))
            if exe_done and not replace:
                print(f"  [CEINMS-exe {it}/{tn}] already done -> skip", flush=True)
                continue
            try:
                t = _mk(tn)
                t._log_tag = f"CEINMS-exe {os.path.basename(session_dir)}"  # distinct tag
                t.run_ceinms_exe()
                t.calculate_muscle_moments(forces_type="ceinms")
                t.run_jra_ceinms(replace=replace)
                print(f"  [CEINMS-exe {it}/{tn}] exe + JRA done", flush=True)
            except Exception as e:
                print(f"  [CEINMS-exe {it}/{tn}] ERROR: {e}", flush=True)
    finally:
        if cs is not None:
            cs.calibration_trial_names = old


# ---------------------------------------------------------------------------
# top-level driver
# ---------------------------------------------------------------------------
def run_session(project_dir=".", session_path=None, iterations=None, trials=None,
                do_scale=True, do_so=True, do_ceinms=False, replace=True, frames=None,
                smoke=False):
    """Run the new session-centric layout from ``session.yaml``.

    ``session_path`` is the session folder (contains session.yaml, c3dfiles/,
    experimental/). ``iterations``/``trials`` optionally restrict the run.
    Assumes ``experimental/`` is already populated (run
    ``exportC3D.export_session(session_path)`` first).

    ``smoke=True`` = fast "do the functions run?" pass: no-ops every figure and
    the validation sweep so only the solve code paths run. Combine with a small
    ``frames`` (auto 5 if unset) and ``do_ceinms=False`` for a <2 min sweep.
    """
    import bioscout
    project = bioscout.Project(project_dir)
    session_path = os.path.abspath(session_path)
    spec = read_session(session_path)
    proj_dir = str(project.dir)

    # smoke: disable all plotting + validation (the slow, output-only steps)
    _restore = {}
    if smoke:
        if frames is None:
            frames = 5
        from bioscout.utils.analysis import _trial_class
        _A = _trial_class()
        _noop = lambda self, *a, **k: None
        _skip = [n for n in dir(_A)
                 if n.startswith("plot") or n.startswith("validate")
                 or n in ("run_validation", "compare_marker_locations",
                          "plot_kin_mom_summary", "plot_id", "plot_residuals")]
        for n in _skip:
            try:
                if callable(getattr(_A, n)):
                    _restore[n] = getattr(_A, n)
                    setattr(_A, n, _noop)
            except Exception:
                pass
        print(f"[smoke] no-op'd {len(_restore)} plot/validation methods; frames={frames}")

    markerset = getattr(getattr(project.settings, "BatchSettings", None), "markerset", None)
    static = spec.static_trial or "Static_01"
    static_trc = os.path.join(experimental_dir(session_path, static), "marker_experimental.trc")

    models = [m for m in spec.models if (iterations is None or m.name in set(iterations))]
    run_trials = trials or [t for t in spec.trials] or None

    results = {}
    try:
        for m in models:
            print(f"\n=== iteration {m.name} ({m.label or ''}) ===")
            if do_scale:
                try:
                    scale_iteration(m, session_path, proj_dir, project.utils, static_trc,
                                    markerset=markerset, replace=replace)
                except Exception as e:
                    print(f"  [scale ERROR] {m.name}: {e}")
            if do_so:
                results[m.name] = run_iteration_so(project, spec, m, session_path,
                                                   run_trials or list(spec.trials),
                                                   replace=replace, frames=frames)
            if do_ceinms:
                run_iteration_ceinms(project, spec, m, session_path,
                                     run_trials or list(spec.trials),
                                     replace=replace, frames=frames)
    finally:
        if _restore:                     # restore patched methods after smoke run
            from bioscout.utils.analysis import _trial_class
            _A = _trial_class()
            for n, f in _restore.items():
                setattr(_A, n, f)
    return results


def summarise_session(project_dir=".", session_path=None, iterations=None, trials=None,
                      forces=("SO", "CEINMS"), joints=("hip", "knee", "ankle"), npts=101):
    """Cross-model comparison figures: overlay each iteration's joint contact
    force (|resultant|, time-normalised) per trial and joint, one line per model.
    Reads <iteration>/<trial>/joint_contact_forces/Analyse_JRA_ReactionLoads_<SO|CEINMS>.sto
    and writes results/<session>/comparison/<trial>_<force>_JCF.png."""
    import bioscout
    import numpy as np
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    project = bioscout.Project(project_dir)
    session_path = os.path.abspath(session_path)
    spec = read_session(session_path)
    BS = getattr(project.settings, "BatchSettings", None)
    _u = project.utils
    outdir = os.path.join(str(project.dir), "results", os.path.basename(session_path), "comparison")
    os.makedirs(outdir, exist_ok=True)

    models = [m for m in spec.models if (iterations is None or m.name in set(iterations))]
    static = spec.static_trial
    run_trials = [t for t in (trials or list(spec.trials))
                  if t != static and (spec.trials.get(t) or {}).get("type") != "static"]

    def _resultant(df, cols):
        C = [c for c in cols if c in df.columns]
        if len(C) < 3:
            return None
        v = np.sqrt(sum(pd.to_numeric(df[c], errors="coerce").to_numpy(float) ** 2 for c in C))
        x = np.linspace(0, 1, len(v))
        return np.interp(np.linspace(0, 1, npts), x, v)

    made = []
    for tn in run_trials:
        for ft in forces:
            fname = f"Analyse_JRA_ReactionLoads_{ft}.sto"
            fig, axes = plt.subplots(1, len(joints), figsize=(5 * len(joints), 4), squeeze=False)
            any_data = False
            for m in models:
                fp = os.path.join(session_path, m.name, tn, "joint_contact_forces", fname)
                if not os.path.exists(fp):
                    continue
                try:
                    df = _u.load_any_data_file(fp)
                except Exception:
                    continue
                cols = (BS.JRA_COLUMNS(m.label or m.name)
                        if BS and hasattr(BS, "JRA_COLUMNS") else {})
                for ji, j in enumerate(joints):
                    r = _resultant(df, cols.get(j, [])) if cols else None
                    if r is None:
                        continue
                    axes[0][ji].plot(np.linspace(0, 100, npts), r, lw=2,
                                     color=(m.color or None), label=m.label or m.name)
                    axes[0][ji].set_title(f"{j} JCF ({ft})")
                    axes[0][ji].set_xlabel("% trial"); axes[0][ji].set_ylabel("Force (N)")
                    any_data = True
            if any_data:
                axes[0][0].legend(fontsize=8)
                fig.suptitle(f"{tn} — joint contact force across models ({ft})")
                fig.tight_layout()
                out = os.path.join(outdir, f"{tn}_{ft}_JCF.png")
                fig.savefig(out, dpi=150); made.append(out)
            plt.close(fig)
    print(f"[summarise] wrote {len(made)} comparison figure(s) -> {outdir}")
    return made


__all__ = ["run_session", "run_iteration_so", "run_iteration_ceinms", "summarise_session",
           "scale_iteration", "import_models",
           "bind_experimental", "experimental_dir", "iteration_dir",
           "derived_trial_dir", "c3d_path", "resolve_generic", "resolve_session_model"]
