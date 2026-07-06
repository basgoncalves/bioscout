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
import shutil
import time

from .session_yaml import read_session


def _rm_empty_inputs(trial_path):
    """Remove an empty ``inputs/`` folder left in an iteration trial dir (raw
    inputs live in shared experimental/ now, so it should never hold anything)."""
    p = os.path.join(trial_path, "inputs")
    try:
        if os.path.isdir(p) and not os.listdir(p):
            os.rmdir(p)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# path resolver
# ---------------------------------------------------------------------------
# Which experimental subfolder the runners read raw inputs from. Normally
# "experimental"; a downsample run points this at e.g. "experimental_ds10".
_EXP_SUBDIR = "experimental"

def experimental_dir(session_dir, trial):
    return os.path.join(session_dir, _EXP_SUBDIR, trial)

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


def full_time_range(exp_dir):
    """Return ``[t0, t_last]`` — the FULL trial window from its time column.
    Used to override any stale (e.g. ghost-run) window persisted in
    trial_settings.xml when running full length."""
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
                return [float(tv[0]), float(tv[-1])]
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# downsample experimental inputs (quick-look speedup)
# ---------------------------------------------------------------------------
def _decimate_storage(src, dst, factor):
    """Decimate an OpenSim .mot/.sto: keep header, every ``factor``-th data row,
    update nRows. Time column is a data column so it is preserved intact."""
    with open(src, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    # find endheader
    hi = next((i for i, l in enumerate(lines) if l.strip().lower() == "endheader"), None)
    if hi is None:
        shutil.copyfile(src, dst); return
    header = lines[:hi + 1]
    col_line = lines[hi + 1]
    data = lines[hi + 2:]
    data = [l for l in data if l.strip() != ""]
    kept = data[::factor]
    # update nRows in header if present
    for i, l in enumerate(header):
        if l.lower().strip().startswith("nrows"):
            header[i] = f"nRows={len(kept)}\n"
    with open(dst, "w", encoding="utf-8") as f:
        f.writelines(header); f.write(col_line); f.writelines(kept)


def _decimate_trc(src, dst, factor):
    """Decimate a .trc marker file: keep every ``factor``-th frame, renumber
    Frame#, keep the real Time values, update NumFrames / DataRate headers."""
    with open(src, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    if len(lines) < 6:
        shutil.copyfile(src, dst); return
    l0, l1, l2 = lines[0], lines[1], lines[2]          # PathFileType / hdr names / hdr values
    col1, col2 = lines[3], lines[4]                    # Frame# Time markers / X Y Z sub-cols
    # data starts at line 5 (some files have a blank line 5) — collect non-empty rows
    body = [l for l in lines[5:] if l.strip() != ""]
    kept = body[::factor]
    # renumber Frame# (col 0), keep Time (col 1) and marker columns
    out = []
    for n, row in enumerate(kept, start=1):
        parts = row.rstrip("\n").split("\t")
        if parts:
            parts[0] = str(n)
        out.append("\t".join(parts) + "\n")
    # update header value row: DataRate CameraRate NumFrames NumMarkers Units OrigDataRate ...
    hv = l2.rstrip("\n").split("\t")
    try:
        for idx in (0, 1):                              # DataRate, CameraRate -> /factor
            hv[idx] = f"{float(hv[idx]) / factor:g}"
        hv[2] = str(len(out))                           # NumFrames
    except Exception:
        pass
    l2 = "\t".join(hv) + "\n"
    with open(dst, "w", encoding="utf-8") as f:
        f.writelines([l0, l1, l2, col1, col2, "\n"]); f.writelines(out)


def downsample_experimental(session_path, factor=10, trials=None):
    """Write decimated copies of the model-independent inputs into
    ``<session>/experimental_ds{factor}/<trial>/`` (every ``factor``-th sample,
    real time column kept). Returns the subdir name to feed run_session(exp_subdir=..).
    Non-tabular files (GRF.xml, analog.csv) are copied; GRF.xml's datafile is
    repointed at the decimated grf.mot."""
    import re, glob
    session_path = os.path.abspath(session_path)
    src_root = os.path.join(session_path, "experimental")
    sub = f"experimental_ds{factor}"
    dst_root = os.path.join(session_path, sub)
    tlist = trials or [d for d in os.listdir(src_root)
                       if os.path.isdir(os.path.join(src_root, d))]
    for tn in tlist:
        sdir = os.path.join(src_root, tn); ddir = os.path.join(dst_root, tn)
        if not os.path.isdir(sdir):
            continue
        os.makedirs(ddir, exist_ok=True)
        for fn in os.listdir(sdir):
            sp, dp = os.path.join(sdir, fn), os.path.join(ddir, fn)
            low = fn.lower()
            if low.endswith((".mot", ".sto")):
                _decimate_storage(sp, dp, factor)
            elif low.endswith(".trc"):
                _decimate_trc(sp, dp, factor)
            elif low == "grf.xml":
                txt = open(sp, "r", encoding="utf-8", errors="replace").read()
                txt = re.sub(r"(<datafile>).*?(</datafile>)",
                             lambda m: m.group(1) + os.path.join(ddir, "grf.mot") + m.group(2),
                             txt, flags=re.I | re.S)
                open(dp, "w", encoding="utf-8").write(txt)
            elif os.path.isfile(sp):
                shutil.copyfile(sp, dp)
        print(f"  [downsample x{factor}] {tn} -> {sub}/{tn}", flush=True)
    return sub


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
        print(f"\n[{spec_model.name}/{tn}] starting SO pipeline (IK ID MA SO moments JRA) ...", flush=True)
        try:
            t = Analyse(dd)
            t.subject = "Athlete"; t.session = os.path.basename(session_dir)
            t.side = (spec.trials.get(tn) or {}).get("side", "r")   # per-trial leg for JCF/plots
            t.update_model(so_model)                  # SO uses the strength model
            # Durable hooks: raw inputs from shared experimental/<trial>/ and the
            # shared setup templates dir; re-applied on every load_settings.
            t.experimental_dir = experimental_dir(session_dir, tn)
            t._session_setup_dir = setup_dir
            t._apply_inputs_layout()                  # apply now (before first run step)
            # SIMULATION window (inputs stay full length):
            #   frames -> first N samples (ghost); yaml time_range -> use it;
            #   else -> FULL trial length. Persist start/end so load_settings
            #   inside run_* uses THIS window (not a stale persisted one).
            _exp = experimental_dir(session_dir, tn)
            tr = (spec.trials.get(tn) or {}).get("time_range")
            if frames:
                tr = first_frames_range(_exp, frames) or tr
            elif not tr:
                tr = full_time_range(_exp)
            if tr:
                t.time_range = list(tr)
                t.update_trial_attribute("start_time", f"{float(tr[0]):.4f}")
                t.update_trial_attribute("end_time", f"{float(tr[1]):.4f}")
            t.update_trial_attribute("replace", replace)
            os.chdir(t.path)   # ensure cwd = trial dir (skipped steps don't chdir)
            _tag = f"{spec_model.name}/{tn}"
            # normal bioscout logging (default [trial] prefix; no custom tag).
            # Each stage prints its own wall-clock duration + a per-trial total.
            _t0 = time.perf_counter(); _s = _t0
            def _lap(msg):
                nonlocal _s
                dt = time.perf_counter() - _s; _s = time.perf_counter()
                print(f"  [ok] {_tag} {msg} ({dt:.1f}s)", flush=True)
            t.run_ik(replace=replace);   _lap("IK done")
            t.run_id(replace=replace);   _lap("ID done")
            t.run_ma(replace=replace);   _lap("MA done")
            t.run_so(replace=replace);   _lap("SO done")
            t.calculate_muscle_moments(forces_type="so"); _lap("muscle moments done")
            t.run_jra(replace=replace);  _lap("JRA done")
            _rm_empty_inputs(t.path)
            done.append(tn)
            print(f"  [SO ok] {_tag} — trial total {time.perf_counter() - _t0:.1f}s", flush=True)
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
        t.side = (spec.trials.get(tn) or {}).get("side", "r")   # per-trial leg for JCF/plots
        t.update_model(ceinms_model)
        t.experimental_dir = experimental_dir(session_dir, tn)
        t._session_setup_dir = setup_dir
        t._apply_inputs_layout()
        t.update_trial_attribute("replace", replace)
        # CEINMS window: frames -> first N (ghost); yaml -> use it; else FULL.
        _exp = experimental_dir(session_dir, tn)
        _yr = (spec.trials.get(tn) or {}).get("time_range")
        _tr = (first_frames_range(_exp, frames) if frames
               else (_yr if _yr else full_time_range(_exp)))
        if _tr:
            t.time_range = list(_tr)
            t.update_trial_attribute("start_time", f"{float(_tr[0]):.4f}")
            t.update_trial_attribute("end_time", f"{float(_tr[1]):.4f}")
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
            _c0 = time.perf_counter()
            host.run_ceinms_calibration()
            print(f"  [ok] {it} CEINMS calibration done (trials={calib}) ({time.perf_counter() - _c0:.1f}s)", flush=True)
        else:
            print(f"  [skip] {it} CEINMS calibration already done (replace=False)", flush=True)
        # ---- per-trial execution: only when replace, or not yet done ----
        for tn in here:
            exe_done = _glob.glob(os.path.join(derived_trial_dir(session_dir, it, tn),
                                               "ceinms", "Execution_*", "MuscleForces.sto"))
            if exe_done and not replace:
                print(f"  [CEINMS-exe {it}/{tn}] already done -> skip", flush=True)
                continue
            print(f"\n[{it}/{tn}] starting CEINMS (execution + moments + JRA) ...", flush=True)
            try:
                t = _mk(tn)
                # normal bioscout logging (default [trial] prefix; no custom tag)
                _e0 = time.perf_counter(); _es = _e0
                def _elap(msg):
                    nonlocal _es
                    dt = time.perf_counter() - _es; _es = time.perf_counter()
                    print(f"  [ok] {it}/{tn} {msg} ({dt:.1f}s)", flush=True)
                t.run_ceinms_exe();                          _elap("CEINMS execution done")
                t.calculate_muscle_moments(forces_type="ceinms"); _elap("CEINMS muscle moments done")
                t.run_jra_ceinms(replace=replace);           _elap("CEINMS JRA done")
                _rm_empty_inputs(t.path)
                print(f"  [ok] {it}/{tn} CEINMS trial total {time.perf_counter() - _e0:.1f}s", flush=True)
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
                smoke=False, exp_subdir=None):
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
    global _EXP_SUBDIR
    _cwd0 = os.getcwd()                       # restored in finally (run_* chdir into trials)
    _exp0 = _EXP_SUBDIR
    if exp_subdir:
        _EXP_SUBDIR = exp_subdir              # read raw inputs from e.g. experimental_ds10/
        print(f"[bioscout] reading experimental inputs from '{exp_subdir}/'")
    session_path = os.path.abspath(session_path)
    project = bioscout.Project(project_dir)
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
            # Pipeline plan: show EVERY stage, marked RUN or SKIP, so a re-run makes
            # explicit which steps are part of the pipeline but not executed this pass.
            _R = lambda f: ("RUN " if f else "SKIP")
            print(f"  [plan {m.name}] export C3D              : SKIP (session step; run exportC3D.export_session separately)")
            print(f"  [plan {m.name}] EMG normalisation       : SKIP (session step; done during export)")
            print(f"  [plan {m.name}] model scaling           : {_R(do_scale)}")
            print(f"  [plan {m.name}] IK ID MA SO moments JRA  : {_R(do_so)}")
            print(f"  [plan {m.name}] CEINMS calibrate+execute : {_R(do_ceinms)}")
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
        _EXP_SUBDIR = _exp0             # restore experimental subdir
        try:
            os.chdir(_cwd0)              # restore cwd (run_* chdir into trial folders)
        except Exception:
            pass
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
    session_path = os.path.abspath(session_path)     # resolve before any chdir
    project_dir = os.path.abspath(project_dir)
    project = bioscout.Project(project_dir)
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
        _side = (spec.trials.get(tn) or {}).get("side", "r")   # per-trial leg
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
                cols = (BS.JRA_COLUMNS(m.label or m.name, _side)
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
