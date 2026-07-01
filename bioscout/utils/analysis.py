"""
bioscout.utils.analysis — the analysis object model.

This module lives next to :class:`bioscout.utils.Analyse` and gathers the
typed objects that wrap it:

    Project ─▶ Subject ─▶ Session ─▶ Trial   (a Trial *is* an Analyse)

It used to live in two top-level modules (``bioscout/subject.py`` and
``bioscout/project.py``); they are now thin shims that re-export from here so
all the analysis-side code sits together under ``utils``.

Quick start::

    import bioscout
    proj = bioscout.Project()                  # cwd is the project root
    proj.utils, proj.settings, proj.dir

    s = proj.subject("Athlete_03_Cateli")
    trial = s.sessions[0].trials[0]            # a Trial == an Analyse
    trial.run_ik(replace=True)

    from bioscout import build_model_config
    model_config = build_model_config(proj.subjects)

Paths resolve against ``bioscout.utils`` (MODELS_DIR / SIMULATIONS_DIR /
SETUP_DIR), which ``bioscout.Project`` / ``init_project()`` point at the
project folder.
"""
import os
import sys
import json
import shutil
import importlib
import importlib.util
import traceback
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# --- imports for the Analyse class (moved from utils/analyse.py) ---
import os
import math
import sys
import re
import shutil
import subprocess
import time
import webbrowser
from glob import glob
from pathlib import Path
import xml.etree.ElementTree as ET
import xml.dom.minidom

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
try:
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.offsetbox import AnchoredText
except Exception:
    PdfPages = AnchoredText = None
try:
    import scipy
except Exception:
    scipy = None
try:
    import opensim as osim   # used by Model-building helpers throughout this module
except Exception:
    osim = None

from bioscout import utils as _u


# ===========================================================================
# Subject
# ===========================================================================

def _is_ceinms(force_type) -> bool:
    return str(force_type).upper().startswith("CEIN")


@dataclass
class Subject:
    """A subject / model variant and all parameters needed to analyse + plot it."""
    name: str                                  # folder under simulations/<name>/ and models/<name>/
    label: Optional[str] = None                # display name on plots (defaults to name)
    session: Optional[str] = None              # default session, e.g. "25_03_31"
    static_trial: Optional[str] = None         # static/MVC trial folder for this session (batch path)
    model_so: Optional[str] = None             # .osim used for static optimisation
    model_ceinms: Optional[str] = None         # .osim used for CEINMS (defaults to model_so)
    setup_folder: Optional[str] = None         # subfolder of setupFiles/ with the OpenSim setup XMLs
    color: str = "black"                       # plot colour
    line_style_so: str = "-"                   # plot line style for SO curves
    line_style_ceinms: str = "--"              # plot line style for CEINMS curves
    group: Optional[str] = None                # optional grouping tag (e.g. "generic" / "MRI")
    body_mass: Optional[float] = None          # optional, kg
    meta: dict = field(default_factory=dict)   # free-form extras

    def __post_init__(self):
        if self.label is None:
            self.label = self.name
        if self.model_ceinms is None:
            self.model_ceinms = self.model_so

    # ---- models -----------------------------------------------------------
    def model_for(self, force_type="SO") -> Optional[str]:
        """Model filename for a solver ('SO' or 'CEINMS')."""
        return self.model_ceinms if _is_ceinms(force_type) else self.model_so

    def model_path(self, force_type="SO", session=None) -> str:
        """Absolute path to the .osim for a solver."""
        from bioscout import utils
        sess = session or self.session or ""
        return os.path.join(str(utils.MODELS_DIR), self.name, sess, self.model_for(force_type) or "")

    # ---- trials -----------------------------------------------------------
    def trial_path(self, trial, session=None) -> str:
        """Absolute path to simulations/<name>/<session>/<trial>."""
        from bioscout import utils
        sess = session or self.session or ""
        return os.path.join(str(utils.SIMULATIONS_DIR), self.name, sess, trial)

    def setup_dir(self) -> str:
        """Absolute path to this subject's OpenSim setup-file folder."""
        from bioscout import utils
        base = getattr(getattr(utils, "settings", None), "SETUP_DIR", None) \
            or os.path.join(str(utils.PROJECT_DIR), "setupFiles")
        return os.path.join(str(base), self.setup_folder) if self.setup_folder else str(base)

    def analyse(self, trial, force_type="SO", session=None, configure=True):
        """Return an ``Analyse`` object for a trial, with the right model +
        setup folder wired in for the chosen solver."""
        from bioscout import utils
        a = utils.Analyse(self.trial_path(trial, session))
        if configure:
            a.subject = self.name
            a.session = session or self.session or getattr(a, "session", None)
            model = self.model_for(force_type)
            if model:
                try:
                    a.update_model(model)
                except Exception as e:
                    print(f"[Subject] {self.name}: could not set model {model}: {e}")
            sd = self.setup_dir()
            if os.path.isdir(sd):
                a.update_trial_attribute("setup_dir", sd)
        return a

    # ---- plotting helpers -------------------------------------------------
    def line_style(self, force_type="SO") -> str:
        return self.line_style_ceinms if _is_ceinms(force_type) else self.line_style_so

    def curve_label(self, force_type="SO") -> str:
        return f"{self.label} - CEINMS" if _is_ceinms(force_type) else self.label

    def to_config(self, force_types=("SO",)) -> dict:
        """Return model_config-style entries for the given solver(s)."""
        cfg = {}
        for ft in force_types:
            cfg[self.curve_label(ft)] = {
                "subject": self.name,
                "color": self.color,
                "force_type": "CEINMS" if _is_ceinms(ft) else "SO",
                "line_style": self.line_style(ft),
            }
        return cfg

    # ---- hierarchy navigation (Subject -> Session -> Trial) ---------------
    @property
    def sessions(self):
        """List of Session objects for this subject (folders under
        simulations/<name>/). If a default session is set, just that one."""
        base = os.path.join(_sim_dir(), self.name)
        if self.session:
            names = [self.session]
        elif os.path.isdir(base):
            names = sorted(d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d)))
        else:
            names = []
        return [Session(self, n) for n in names]

    def get_session(self, name):
        """Session by name."""
        return Session(self, name)

    def trials(self, session=None, force_type="SO"):
        """List of Trial objects for one session (default: self.session)."""
        return Session(self, session or self.session).trials

    def make_trial(self, trial_path, force_type="SO", configure=True):
        """Return a Trial (an Analyse) for an absolute trial path, with this
        subject's model + setup folder wired in for the chosen solver."""
        Trial = _trial_class()
        t = Trial(trial_path)
        if configure:
            try:
                _parts = os.path.normpath(trial_path).split(os.sep)
                t.subject = self.name
                t.session = _parts[-2] if len(_parts) >= 2 else self.session
                model = self.model_for(force_type)
                if model:
                    t.update_model(model)
                sd = self.setup_dir()
                if os.path.isdir(sd):
                    t.update_trial_attribute("setup_dir", sd)
            except Exception as e:
                print(f"[Subject] {self.name}: configure trial failed: {e}")
        return t

    @classmethod
    def from_model_folder(cls, name, folder, session=None, **overrides):
        """Build a Subject by inspecting the .osim files in a model folder.

        Picks ``model_so`` = a strength-increased model (filename contains
        'increased' / '3.00' / 'x3'); ``model_ceinms`` = the matching base model.
        Any keyword in ``overrides`` (color, label, setup_folder, …) wins.
        """
        try:
            files = [f for f in os.listdir(folder) if f.lower().endswith(".osim")]
        except Exception:
            files = []
        model_so, model_ceinms = _pick_models(files)
        kw = dict(name=name, session=session, model_so=model_so, model_ceinms=model_ceinms)
        kw.update(overrides)
        return cls(**kw)

    def __repr__(self):
        return f"<Subject {self.label!r} ({self.name}) SO={self.model_so} CEINMS={self.model_ceinms}>"


def build_model_config(subjects, force_types=("SO", "CEINMS")) -> dict:
    """Build a Plot-compatible ``model_config`` dict from a list of Subjects.

    Result: ``{curve_label: {subject, color, force_type, line_style}}`` — exactly
    what ``bioscout.utils.Plot`` reads from ``settings.model_config``.
    """
    cfg = {}
    for s in subjects:
        cfg.update(s.to_config(force_types))
    return cfg


# ---------------------------------------------------------------------------
# Single source of truth: derive the legacy batch structures from SUBJECTS so
# there is ONE subject/session model (these Subjects), not two. Project
# settings can do:  SUBJECTS  = subjects_from_subjects(SUBJECTS)
#                   SESSIONS = sessions_from_subjects(SUBJECTS, SIMULATIONS_DIR)
# instead of maintaining a separate SUBJECTS list + build_sessions().
# ---------------------------------------------------------------------------

def sessions_from_subjects(subjects, simulations_dir=None, default_static="static1") -> dict:
    """Legacy batch ``SESSIONS`` dict ({abs_session_path: static_trial}) derived
    from Subjects — what ``BatchSettings.sessions`` consumes."""
    if simulations_dir is None:
        from bioscout import utils
        simulations_dir = getattr(utils, "SIMULATIONS_DIR", "")
    out = {}
    for s in subjects:
        sess = getattr(s, "session", None)
        path = (os.path.join(str(simulations_dir), s.name, sess) if sess
                else os.path.join(str(simulations_dir), s.name))
        out[str(path)] = getattr(s, "static_trial", None) or default_static
    return out


def subjects_from_subjects(subjects) -> dict:
    """Legacy ``SUBJECTS`` dict ({name: {session, static_trial, group}}) derived
    from Subjects — for code/GUI paths that still read SUBJECTS."""
    out = {}
    for s in subjects:
        rec = {}
        for key in ("session", "static_trial", "group"):
            val = getattr(s, key, None)
            if val is not None:
                rec[key] = val
        out[s.name] = rec
    return out


def resolve_subject_selection(selection, all_subjects) -> set:
    """Turn a mixed list of subject NAMES (str) and/or INDICES (int, into
    ``all_subjects``) into a set of subject names. ``None``/empty -> empty set."""
    names = []
    for x in (selection or []):
        if isinstance(x, bool):
            continue
        if isinstance(x, int):
            if 0 <= x < len(all_subjects):
                names.append(all_subjects[x].name)
        else:
            names.append(str(x))
    return set(names)


def select_subjects(all_subjects, run=None, skip=None):
    """Filter Subjects by run/skip selections (each a list of names or indices).

    ``run`` None/empty keeps all; ``skip`` removes; skip wins over run. This is
    the project-level "which subjects to process" logic — kept here (next to the
    Subject model) rather than in a project's settings.py.
    """
    keep = resolve_subject_selection(run, all_subjects)
    drop = resolve_subject_selection(skip, all_subjects)
    out = list(all_subjects)
    if keep:
        out = [s for s in out if s.name in keep]
    if drop:
        out = [s for s in out if s.name not in drop]
    return out


def subjects_in_simulations(simulations_dir=None):
    """Names of every subject folder present under the simulations directory."""
    if simulations_dir is None:
        from bioscout import utils
        simulations_dir = getattr(utils, "SIMULATIONS_DIR", "")
    try:
        return sorted(d for d in os.listdir(str(simulations_dir))
                      if os.path.isdir(os.path.join(str(simulations_dir), d)))
    except Exception:
        return []


# ===========================================================================
# Hierarchy: Subject -> Session -> Trial (a Trial IS an Analyse)
# ===========================================================================

def _sim_dir():
    from bioscout import utils
    return str(getattr(utils, "SIMULATIONS_DIR", ""))


_TRIAL_CLS = None


def _trial_class():
    """Return (and cache) the Trial class: Analyse + run_*(replace=...)."""
    global _TRIAL_CLS
    if _TRIAL_CLS is not None:
        return _TRIAL_CLS
    from bioscout import utils

    class Trial(utils.Analyse):
        """A trial = an Analyse, plus run_*(replace=...) convenience.

        Inherits every pipeline method of Analyse (run_ik, run_id, run_ma,
        run_so, run_jra, CEINMS, plotting, …). The thin overrides below let you
        pass replace= directly, e.g. trial.run_ik(replace=True).
        """
        def _set_replace(self, replace):
            if replace is not None:
                self.update_trial_attribute("replace", replace)

        def run_ik(self, replace=None):          self._set_replace(replace); return super().run_ik()
        def run_id(self, replace=None):          self._set_replace(replace); return super().run_id()
        def run_ma(self, replace=None):          self._set_replace(replace); return super().run_ma()
        def run_so(self, replace=None):          self._set_replace(replace); return super().run_so()
        def run_jra(self, replace=None):         self._set_replace(replace); return super().run_jra()
        def run_jra_ceinms(self, replace=None):  self._set_replace(replace); return super().run_jra_ceinms()

    _TRIAL_CLS = Trial
    return Trial


class Session:
    """One recording session of a Subject.

    Two roles:

    * **Navigation** — ``.trials``, ``.trial(name)``, ``.path``.
    * **Session-level analysis** — operations that span the whole session
      rather than a single trial. EMG normalisation builds one session-wide
      envelope and applies it to every trial; CEINMS calibration produces one
      calibrated model per subject/session from the calibration trials. Both
      are already session-scoped inside ``Analyse``; this class drives them at
      the right granularity. Add future session-scoped steps here (e.g. MVC
      processing, per-session quality checks).

    Example::

        sess = proj.subject("Athlete_03_GPK").get_session("25_03_31")
        sess.run_emg_normalise(replace=True)     # all trials, one envelope
        sess.run_ceinms_calibration(replace=True)  # one calibrated model
        # or both in order:
        sess.prepare_ceinms(replace=True)
    """

    def __init__(self, subject, name):
        self.subject = subject     # Subject
        self.name = name           # session folder name, e.g. "25_03_31"

    # -- navigation ---------------------------------------------------------
    @property
    def path(self):
        return os.path.join(_sim_dir(), self.subject.name, self.name or "")

    def _trial_names(self):
        p = self.path
        if not os.path.isdir(p):
            return []
        # Exclude CEINMS output folders ("calibrationOutput", timestamped
        # "calibrationOutput_run_*") — they live in the session dir but are not
        # trials, so they must never be EMG-normalised / calibrated / iterated.
        return [d for d in sorted(os.listdir(p))
                if os.path.isdir(os.path.join(p, d))
                and not d.startswith("calibrationOutput")]

    @property
    def trials(self):
        """List of Trial objects (one per trial folder in this session)."""
        return [self.subject.make_trial(os.path.join(self.path, d))
                for d in self._trial_names()]

    def trial(self, name, force_type="SO"):
        """Trial by name (e.g. 'Squat_BW_01')."""
        return self.subject.make_trial(os.path.join(self.path, name), force_type=force_type)

    # -- session-level analysis --------------------------------------------
    @property
    def calibration_trials(self):
        """CEINMS calibration trial names (from
        ``settings.CEINMSSettings.calibration_trial_names``) that actually
        exist in this session."""
        from bioscout import utils
        cs = getattr(getattr(utils, "settings", None), "CEINMSSettings", None)
        names = getattr(cs, "calibration_trial_names", None) or []
        here = set(self._trial_names())
        return [n for n in names if n in here]

    def _ref_trial(self, force_type="CEINMS", prefer=None):
        """A single Trial used to drive a session-level op. Prefers ``prefer``,
        then a configured calibration trial present in the session, else the
        first trial."""
        names = self._trial_names()
        if not names:
            return None
        if prefer and prefer in names:
            pick = prefer
        else:
            calib = self.calibration_trials
            pick = calib[0] if calib else names[0]
        return self.trial(pick, force_type=force_type)

    def run_emg_normalise(self, replace=None):
        """Build CEINMS excitations for the whole session.

        For each trial, compute the rectified low-pass EMG envelope from the RAW
        emg.mot, take the per-channel max ACROSS the session (MVC-style), then
        write each trial's ``emg_ceinms.mot`` = envelope / session-max clipped to
        [0, 1] — exactly the excitation range CEINMS expects. This replaces the
        old per-trial divide-by-own-max on the raw bipolar signal (which left
        excitations negative / >1 and cascaded ``*_normalised_normalised`` files).
        Returns the list of trials that produced valid excitations.
        """
        envelopes = {}
        for t in self.trials:
            if replace is not None:
                t.update_trial_attribute("replace", replace)
            try:
                env = t._emg_envelope()
            except Exception as e:
                print(f"[Session] {self.subject.name}/{self.name}: EMG envelope "
                      f"failed for {os.path.basename(t.path)}: {e}")
                env = None
            if env is not None:
                envelopes[t] = env

        if not envelopes:
            print(f"[Session] {self.subject.name}/{self.name}: no EMG to normalise.")
            return []

        # per-channel session max envelope (MVC reference)
        chans = set()
        for env in envelopes.values():
            chans |= {c for c in env.columns if c != 'time'}
        session_max = {}
        for c in chans:
            m = max((float(env[c].max()) for env in envelopes.values() if c in env),
                    default=0.0)
            session_max[c] = m if m > 1e-9 else 1.0

        done = []
        for t, env in envelopes.items():
            out = env[['time']].copy()
            for c in chans:
                if c in env:
                    out[c] = (env[c] / session_max[c]).clip(0.0, 1.0)
            try:
                _u.emg_normalise.write_sto_file(out, os.path.join(t.path, 'emg_ceinms.mot'))
                t.update_trial_attribute('ceinms_excitations', 'emg_ceinms.mot')
                done.append(t)
            except Exception as e:
                print(f"[Session] {self.subject.name}/{self.name}: EMG normalise "
                      f"failed for {os.path.basename(t.path)}: {e}")
        print(f"[Session] {self.subject.name}/{self.name}: wrote emg_ceinms.mot "
              f"for {len(done)} trials (session-max normalised, [0,1]).")
        return done

    def run_ceinms_calibration(self, replace=None, prefer_trial=None):
        """Calibrate CEINMS once for this subject/session.

        ``Analyse.run_ceinms_calibration`` is itself session-scoped (it collects
        the calibration trials under the session folder), so it is driven here
        from a single CEINMS-configured reference trial. Produces the calibrated
        model that every trial's CEINMS execution then uses.
        """
        t = self._ref_trial(force_type="CEINMS", prefer=prefer_trial)
        if t is None:
            print(f"[Session] {self.subject.name}/{self.name}: no trials to calibrate.")
            return None
        if replace is not None:
            t.update_trial_attribute("replace", replace)
        return t.run_ceinms_calibration()

    def prepare_ceinms(self, replace=None):
        """Convenience: session-level EMG normalisation, then CEINMS
        calibration (the two steps a session needs before per-trial CEINMS
        execution)."""
        self.normalise_emg(replace=replace)
        return self.calibrate(replace=replace)

    # ---- clean public verbs ----------------------------------------------
    def normalise_emg(self, replace=None):
        """Session-wide EMG normalisation (alias of run_emg_normalise)."""
        return self.run_emg_normalise(replace=replace)

    def _resolve_calibration_trials(self):
        """Which trial folders to calibrate on for THIS session.

        Reads ``settings.CEINMSSettings.calibration_trial_names`` and matches
        them to this session's actual trial folders (case-insensitive). If none
        match (e.g. a stale or mistyped name in settings), falls back to the
        session's squat trials, then to all trials, so calibration still runs.
        """
        here = self._trial_names()
        lower = {t.lower(): t for t in here}
        from bioscout import utils
        cs = getattr(getattr(utils, "settings", None), "CEINMSSettings", None)
        wanted = list(getattr(cs, "calibration_trial_names", None) or [])
        matched = [lower[w.lower()] for w in wanted if w.lower() in lower]
        if matched:
            return matched
        if wanted:
            print(f"[Session] {self.subject.name}/{self.name}: calibration trials "
                  f"{wanted} not found in this session; falling back.")
        squats = [t for t in here if "squat" in t.lower()]
        return squats or here

    def calibrate(self, replace=None, calibration_trials=None):
        """Calibrate CEINMS for THIS session.

        Uses the calibration trials named in ``settings.CEINMSSettings``
        (matched to this session's folders via :meth:`_resolve_calibration_trials`),
        or the explicit ``calibration_trials`` you pass. The resolved names are
        fed to the underlying session-scoped calibration so it collects the
        right input trials even if the settings value is stale.

        Example::

            proj.subjects[0].sessions[0].calibrate(replace=True)
        """
        names = list(calibration_trials) if calibration_trials else self._resolve_calibration_trials()
        if not names:
            print(f"[Session] {self.subject.name}/{self.name}: no calibration trials found.")
            return None
        from bioscout import utils
        cs = getattr(getattr(utils, "settings", None), "CEINMSSettings", None)
        old = getattr(cs, "calibration_trial_names", None) if cs is not None else None
        try:
            if cs is not None:
                cs.calibration_trial_names = names   # point calibration at real folders
            print(f"[Session] {self.subject.name}/{self.name}: calibrating CEINMS on {names}")
            return self.run_ceinms_calibration(replace=replace, prefer_trial=names[0])
        finally:
            if cs is not None:
                cs.calibration_trial_names = old

    def __repr__(self):
        n = len(self._trial_names())
        return f"<Session {self.subject.name}/{self.name} — {n} trials>"


_DEFAULT_PALETTE = ["green", "blue", "red", "purple", "orange",
                    "brown", "teal", "magenta", "olive", "cyan"]

# substrings that mark a strength-increased model
_INCREASED_TOKENS = ("increased", "3.00", "_x3", "x3_")


def _pick_models(osim_files):
    """From .osim filenames pick (model_so, model_ceinms).

    SO  = a strength-increased model (name contains an _INCREASED_TOKENS marker).
    CEINMS = the base model that the increased one derives from (its name minus
             the marker), else the shortest plain model.
    """
    osims = [f for f in osim_files if f.lower().endswith(".osim")]
    if not osims:
        return None, None
    increased = [f for f in osims if any(t in f.lower() for t in _INCREASED_TOKENS)]
    base = [f for f in osims if f not in increased]
    model_so = increased[0] if increased else (sorted(base, key=len)[0] if base else None)

    model_ceinms = None
    if model_so and increased:
        stem = model_so.lower()
        for t in _INCREASED_TOKENS:
            stem = stem.split(t)[0]
        stem = stem.rstrip("_").rstrip(".")
        for b in sorted(base, key=len):
            if b.lower().startswith(stem):
                model_ceinms = b
                break
    if model_ceinms is None:
        model_ceinms = sorted(base, key=len)[0] if base else model_so
    return model_so, model_ceinms


def discover_subjects(models_dir=None, session=None, names=None,
                      palette=None, **common):
    """Auto-build a list of :class:`Subject` from the project's models folder.

    Scans ``models_dir`` (defaults to ``bioscout.utils.MODELS_DIR``); each
    sub-folder becomes a Subject, with SO/CEINMS models guessed from its .osim
    files (see :meth:`Subject.from_model_folder`). Looks inside
    ``models/<name>/<session>/`` when ``session`` is given and present.

    ``names`` restricts to specific subjects; ``palette`` overrides colours;
    extra keywords (e.g. ``setup_folder=...``) are applied to every Subject.
    """
    from bioscout import utils
    models_dir = str(models_dir or getattr(utils, "MODELS_DIR", ""))
    palette = palette or _DEFAULT_PALETTE
    out = []
    if not os.path.isdir(models_dir):
        print(f"[bioscout] discover_subjects: models dir not found: {models_dir}")
        return out
    folders = names or sorted(d for d in os.listdir(models_dir)
                              if os.path.isdir(os.path.join(models_dir, d)))
    for i, nm in enumerate(folders):
        base = os.path.join(models_dir, nm)
        folder = os.path.join(base, session) if session and os.path.isdir(os.path.join(base, session)) else base
        kw = dict(session=session, color=palette[i % len(palette)])
        kw.update(common)
        out.append(Subject.from_model_folder(nm, folder, **kw))
    return out


# ===========================================================================
# Project bootstrap
# ===========================================================================

def _force_load_helper(utils, name):
    """Load a lazily-imported helper (openSim/ceinms) onto ``utils``."""
    if getattr(utils, name, None) is not None:
        return
    mod = None
    try:                                   # bare import (utils/ dir is on sys.path)
        mod = importlib.import_module(name)
    except Exception:
        try:                               # package-qualified fallback
            mod = importlib.import_module(f"bioscout.utils.{name}")
        except Exception:
            if name == "openSim":
                print(f"[bioscout] could not load '{name}' — traceback:")
                traceback.print_exc()
            return
    setattr(utils, name, mod)
    sys.modules.setdefault(name, mod)


def check_settings_version(settings, project_dir=None, verbose=True):
    """Compare a project's ``settings.__version__`` to the package schema version.

    Returns True if they match (or can't be compared), False on mismatch.
    Does NOT modify anything — migrating a heavily-customised project
    ``settings.py`` can drop custom fields, so updating is left to an explicit,
    backed-up call (``bioscout.utils.settings_updater.write_updated_settings``)
    or the GUI's "Update Settings" button.
    """
    try:
        import bioscout.settings as _pkg_settings
        pkg_ver = getattr(_pkg_settings, "__version__", None)
    except Exception:
        pkg_ver = None
    proj_ver = getattr(settings, "__version__", None)

    if pkg_ver is None or proj_ver is None:
        if verbose and proj_ver is None:
            print(f"[bioscout] project settings.py has no __version__ — "
                  f"add  __version__ = \"{pkg_ver or '1.2'}\"  to track the schema.")
        return True

    def _mm(v):  # compare MAJOR.MINOR only — patch may differ per component/branch
        p = str(v).split(".")
        return ".".join(p[:2]) if len(p) >= 2 else str(v)

    if _mm(proj_ver) != _mm(pkg_ver):
        if verbose:
            loc = f" ({project_dir})" if project_dir else ""
            print(f"[bioscout] settings schema mismatch{loc}: project __version__={proj_ver} "
                  f"!= package={pkg_ver}.")
            print("           To migrate (backs up settings.py first):")
            print("             from bioscout.utils.settings_updater import write_updated_settings")
            print("             write_updated_settings(r'<project>/settings.py')")
            print("           NOTE: the migrator only preserves standard fields; back up custom "
                  "config (model_config, MODELS, …) first.")
        return False
    if verbose:
        print(f"[bioscout] settings schema v{proj_ver} OK")
    return True


def _find_project_root(start=None):
    """Locate the project root, robust to the cwd having been changed into a
    trial folder by Analyse(). Priority:
      1. explicit `start`
      2. BIOSCOUT_PROJECT_DIR env var
      3. walk up from cwd to the first folder with settings.py, or with both
         models/ and simulations/
      4. cwd
    """
    if start:
        return Path(start).resolve()
    env = os.environ.get("BIOSCOUT_PROJECT_DIR")
    if env and os.path.isdir(env):
        return Path(env).resolve()
    p = Path(os.getcwd()).resolve()
    for cand in [p, *p.parents]:
        if (cand / "settings.py").exists():
            return cand
        if (cand / "models").is_dir() and (cand / "simulations").is_dir():
            return cand
    return p


def migrate_settings(project, write=False, verbose=True):
    """Update a project's settings.py to the current schema, keeping its values.

    Same engine as the GUI's "Update Settings" button
    (``bioscout.utils.settings_updater``): regenerates the file from the latest
    package template and re-injects the project's own values.

    ``write=False`` (default) returns ``(new_text, preserved_lines)`` for preview.
    ``write=True`` writes settings.py in place (backing up the original first)
    and returns the list of preserved-value descriptions.
    """
    sp = Path(project)
    if sp.is_dir():
        sp = sp / "settings.py"
    try:
        from bioscout.utils import settings_updater as su
    except Exception:
        su = importlib.import_module("utils.settings_updater")
    if write:
        preserved = su.write_updated_settings(sp)
        if verbose:
            print(f"[bioscout] settings.py migrated to current schema (backup created): {sp}")
            for line in preserved:
                print(line)
        return preserved
    return su.build_updated_settings(sp)


def ensure_editor_paths(project_dir, verbose=True):
    """Make Pylance/Pyright resolve the project's own modules (e.g. `import
    settings`) by adding "." to python.analysis.extraPaths in the project's
    .vscode/settings.json.

    Relative ("."), so it is portable across machines. Idempotent and
    non-destructive: creates the file if missing, otherwise only adds the keys
    that aren't already there. Never raises (editor convenience only).

    Takes effect when the project folder is opened as a VS Code workspace
    folder (File ▸ Add Folder to Workspace…).
    """
    try:
        vs = Path(project_dir) / ".vscode"
        f = vs / "settings.json"
        data = {}
        if f.exists():
            try:
                data = json.loads(f.read_text(encoding="utf-8")) or {}
            except Exception:
                return  # unparseable / commented JSONC — leave the user's file alone
        paths = data.get("python.analysis.extraPaths", [])
        changed = False
        # Add both "." (portable, works when this folder is the workspace root)
        # and the absolute path (works regardless of the workspace root, e.g.
        # multi-root or a parent folder opened) so Pylance resolves `import
        # settings` / the project's own modules in either case.
        for entry in (".", str(Path(project_dir).resolve())):
            if entry not in paths:
                paths.append(entry)
                changed = True
        if changed:
            data["python.analysis.extraPaths"] = paths
        sev = data.setdefault("python.analysis.diagnosticSeverityOverrides", {})
        for k in ("reportMissingImports", "reportMissingModuleSource"):
            if k not in sev:
                sev[k] = "none"
                changed = True
        if changed:
            vs.mkdir(exist_ok=True)
            f.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            if verbose:
                print(f"[bioscout] editor paths configured: {f}")
    except Exception:
        pass  # never break init_project over editor config


class Project:
    """A BioScout project bound to a folder.

    The folder is expected to hold ``models/``, ``simulations/``, ``results/``
    and a project ``settings.py``. Construction wires the package to it.

    Attributes
    ----------
    dir : Path        the project root
    utils : module    bioscout.utils, with OpenSim/CEINMS loaded and dirs set
    settings : module the project's settings.py
    """

    def __init__(self, project_dir=None, verbose=True, setup_editor=True):
        self.dir = _find_project_root(project_dir)
        sys.path.insert(0, str(self.dir))
        os.chdir(self.dir)   # reset cwd (Analyse() chdir's into trial folders)

        from bioscout import utils
        self.utils = utils
        _force_load_helper(utils, "openSim")
        _force_load_helper(utils, "ceinms")

        self.settings = self._load_settings(verbose)
        self._point_dirs()
        check_settings_version(self.settings, self.dir, verbose=verbose)

        # If the settings (e.g. a freshly scaffolded template) declares no
        # subjects, populate them by scanning models/ so the project is usable.
        try:
            _bs = getattr(self.settings, "BatchSettings", None)
            if _bs is not None and not getattr(_bs, "SUBJECTS", None):
                subs = self.discover_subjects()
                if subs:
                    _bs.SUBJECTS = subs
                    if not getattr(_bs, "model_config", None):
                        _bs.model_config = build_model_config(subs)
                    if verbose:
                        print(f"[bioscout] discovered {len(subs)} subject(s) from models/")
        except Exception:
            pass

        if setup_editor:
            ensure_editor_paths(self.dir, verbose=verbose)

        if verbose:
            import bioscout
            print(f"BioScout {getattr(bioscout, '__version__', '?')}  |  project: {self.dir.name}")
            print(f"openSim ready: {utils.openSim is not None}   "
                  f"ceinms ready: {getattr(utils, 'ceinms', None) is not None}   "
                  f"settings.SESSION: {getattr(getattr(self.settings, 'BatchSettings', None), 'SESSION', None)}")

    # -- setup steps ---------------------------------------------------------
    def _load_settings(self, verbose=True, scaffold=True):
        sp = self.dir / "settings.py"
        if not sp.exists() and scaffold:
            # Create a starter settings.py from the package template so the
            # project has one to edit (mirrors `python -m bioscout --init`).
            try:
                import bioscout.settings as _pkg
                shutil.copy2(Path(_pkg.__file__), sp)
                if verbose:
                    print(f"[bioscout] created settings.py from template -> {sp}")
                    print("           edit PROJECT_ROOT and your project config, then re-run.")
            except Exception as e:
                if verbose:
                    print(f"[bioscout] could not scaffold settings.py: {e}")
        if sp.exists():
            spec = importlib.util.spec_from_file_location("settings", str(sp))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            sys.modules["settings"] = mod
            self.utils.settings = mod
            return mod
        if verbose:
            print(f"[bioscout] no settings.py in {self.dir} — using package defaults")
        return getattr(self.utils, "settings", None)

    def _point_dirs(self):
        u, d = self.utils, self.dir
        u.PROJECT_DIR     = str(d)
        u.MODELS_DIR      = str(d / "models")
        u.SIMULATIONS_DIR = str(d / "simulations")
        u.RESULTS_DIR     = str(d / "results")

    # -- convenience ---------------------------------------------------------
    def trial_path(self, subject, session, trial):
        """Absolute path to simulations/<subject>/<session>/<trial>."""
        return os.path.join(self.utils.SIMULATIONS_DIR, subject, session, trial)

    def analyse(self, subject, session, trial):
        """Return an ``Analyse`` object for one trial folder."""
        return self.utils.Analyse(self.trial_path(subject, session, trial))

    def results_dir(self, *parts):
        """Make and return results/<*parts>."""
        d = os.path.join(self.utils.RESULTS_DIR, *parts)
        os.makedirs(d, exist_ok=True)
        return d

    def discover_subjects(self, session=None, **kw):
        """Auto-build Subjects from this project's models/ folder (see
        bioscout.discover_subjects)."""
        return discover_subjects(self.utils.MODELS_DIR,
                                 session=session or getattr(self.settings, "SESSION", None), **kw)

    def migrate_settings(self, write=False, verbose=True):
        """Update this project's settings.py to the current schema, keeping
        its values (see bioscout.migrate_settings)."""
        return migrate_settings(self.dir, write=write, verbose=verbose)

    # ---- hierarchy: Project -> Subject -> Session -> Trial ----------------
    @property
    def subjects(self) -> "list[Subject]":
        """The project's Subject objects (from settings.BatchSettings.SUBJECTS)."""
        return list(getattr(getattr(self.settings, "BatchSettings", None), "SUBJECTS", []) or [])

    def subject(self, name) -> "Subject":
        """Subject by folder name or label."""
        for s in self.subjects:
            if getattr(s, "name", None) == name or getattr(s, "label", None) == name:
                return s
        return None

    def trial(self, subject, trial, session=None, force_type="SO"):
        """Configured Trial for a subject (name or Subject) / session / trial."""
        s = self.subject(subject) if isinstance(subject, str) else subject
        if s is None:
            return None
        sess = session or getattr(s, "session", None)
        return s.make_trial(s.trial_path(trial, sess), force_type=force_type)

    def __repr__(self):
        ok = "ok" if getattr(self.utils, "openSim", None) is not None else "None"
        return f"<bioscout.Project {self.dir.name!r} openSim={ok}>"


def init_project(project_dir=None, verbose=True, setup_editor=True):
    """Bootstrap BioScout for a project folder. Returns ``(utils, settings)``.

    Thin wrapper around :class:`Project` for the common "just give me utils and
    settings" case. ``setup_editor`` (default True) drops a relative
    ``.vscode/settings.json`` so Pylance resolves the project's own modules.
    """
    p = Project(project_dir, verbose=verbose, setup_editor=setup_editor)
    return p.utils, p.settings


# Plot still lives in utils/plot.py and is re-exported here lazily; Analyse is
# defined at the bottom of THIS module (moved from utils/analyse.py).
_REEXPORT = {"Plot"}


def __getattr__(name):
    if name in _REEXPORT:
        from bioscout import utils
        return getattr(utils, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Subject", "Session", "Project",
    "Analyse", "Plot",
    "build_model_config", "discover_subjects", "init_project",
    "sessions_from_subjects", "subjects_from_subjects",
    "check_settings_version", "migrate_settings", "ensure_editor_paths",
]

# ===========================================================================
# Analyse - per-trial OpenSim/CEINMS pipeline (moved here from utils/analyse.py).
# ===========================================================================
class Analyse(_u.settings.Inputs):
    '''
    Contains paths from the user settings and functions to implement in the OpenSim/Ceinms analysis
    
    subject_name: Name of the subject (or the trial path if session_name and trial_name are None)

    Usage:
        - Create an instance of the Analyse class with the trial path:


    '''
    def __init__(self, trialPath=None):

        if trialPath is None:
            trialPath = input("Enter the path to the trial directory: ").strip('"')  # Remove quotes if the path is copied with them
        
        self.replace = getattr(_u.settings.BatchSettings, 'replace_existing', False)
        self.path = os.path.abspath(trialPath)
        self.trial = os.path.basename(self.path)  # set early so _log works before settings load
        self.settingsXML = 'trial_settings.xml'

        if not os.path.exists(trialPath):
            self._log(f"Trial path not found: {trialPath}")
            os.makedirs(trialPath)
            self._reset_settings_xml()
            model_dir = os.path.join(_u.MODELS_DIR, *os.path.normpath(self.path).split(os.sep)[-3:-1])
            if not os.path.exists(model_dir):
                os.makedirs(model_dir)
                self._log(f"Created model directory: {model_dir}")
            return
        
        else:
            os.chdir(self.path)
            
            try:
                # Check file size of settings XML to ensure it's not empty or corrupted
                if os.path.exists(self.settingsXML) and os.path.getsize(self.settingsXML) > 0 and os.path.getsize(self.settingsXML) < 1 * 1024 * 1024:  # limit 1 MB
                    self.load_settings(self.settingsXML)
                    self.replace = getattr(_u.settings.BatchSettings, 'replace_existing', False)
                else:
                    self._log("Settings XML is missing, empty, or too large. Creating new settings XML.")
                    self._reset_settings_xml()
            except:
                self._log("Settings XML not found or could not be loaded. Creating new settings XML.")
                self._reset_settings_xml()
        
        # time.sleep(1)
                  
    def _reset_settings_xml(self):
        '''Create a settings xml for the trial at the specified path'''
        os.chdir(self.path)
        # delete existing settings xml if it exists
        if os.path.exists(self.settingsXML):
            os.remove(self.settingsXML)
            self._log(f"Existing settings XML deleted: {self.settingsXML}")
        
        path_parts = os.path.normpath(self.path).split(os.sep)
        self.subject = path_parts[-3]
        self.session = path_parts[-2]
        self.trial = path_parts[-1]

        self.parentdir = os.path.dirname(self.path)

        self._update_model()
        
        self.body_mass = None # Placeholder, will be updated from the model if possible
        self.time_range = 'None' # Placeholder, will be updated from data if possible
        
        # add each Input to the trial settings
        inputs = _u.settings.Inputs(parentdir=self.path)
        for varInput in inputs.__dict__.items():
            filepath = os.path.join(self.path, varInput[1])
            if varInput[0] in ['model_dir', 'model_name']:
                continue
            if os.path.exists(filepath):
                setattr(self, varInput[0], os.path.relpath(filepath, self.path))
            else:
                setattr(self, varInput[0], varInput[1])

        # Create any subfolders referenced by the input paths (e.g. inputs/,
        # external_biomechanics/, muscle_analysis/, static_optimisation/, ceinms/).
        # No-op for the flat layout (paths without a directory part); enables the
        # subfoldered layout automatically once Inputs uses subfolder-prefixed paths.
        for _k, _v in inputs.__dict__.items():
            if _k.startswith("_") or not isinstance(_v, str):
                continue
            _d = os.path.dirname(_v)
            if _d and not _d.startswith(".."):
                try:
                    os.makedirs(os.path.join(self.path, _d), exist_ok=True)
                except Exception:
                    pass

        # Update body mass and time range from data available (.trc, .c3d, events.csv)
        try:
            self.body_mass = self.get_body_mass()  
            self.time_range = self.get_time_range()
        except Exception as e:
            self._log(f"Error updating from data: {e}", terminal=True)
        
        self._update_emg_tag() 
        self._update_input_files()
        self._to_xml()

    def _to_xml(self):
        '''Print all settings for the trial to an xml in trial.path'''
        os.chdir(self.path)
        root = _u.ET.Element("TrialSettings")
        for attr, value in self.__dict__.items():

            # Skip pandas DataFrames and Series - they have __dict__ but shouldn't be serialized
            if isinstance(value, (pd.DataFrame, pd.Series)):
                continue
            
            if isinstance(value, (str, int, float, bool, list, dict)):
                child = _u.ET.SubElement(root, attr)
                if os.path.exists(str(value)):
                    child.text = os.path.relpath(str(value), self.path)
                else:
                    child.text = str(value)
            else:
                if not hasattr(value, '__dict__'):
                    continue

                for sub_attr, sub_value in value.__dict__.items():
                    child = _u.ET.SubElement(root, f"{sub_attr}")
                    if os.path.exists(str(sub_value)):
                        child.text = os.path.relpath(str(sub_value), self.path)
                    else:
                        child.text = str(sub_value)
                
        tree = _u.ET.ElementTree(root)
        _u.save_pretty_xml(tree, self.settingsXML)
        print(f"Trial settings saved to: {os.path.abspath(self.settingsXML)}")
    
    def _update_input_files(self):
        '''Update input file paths in the trial settings to match the expected names and save to XML'''

        # change .mot file to match the self.grf_mot
        if os.path.exists(os.path.join(self.path, self.trial + '.mot')):
            os.rename(os.path.join(self.path, self.trial + '.mot'), os.path.join(self.path, self.grf_mot))
            print(f"Renamed {self.trial + '.mot'} to {self.grf_mot}")

        # change .trc file to match the self.markers
        if os.path.exists(os.path.join(self.path, self.trial + '.trc')):
            os.rename(os.path.join(self.path, self.trial + '.trc'), os.path.join(self.path, self.markers))
            print(f"Renamed {self.trial + '.trc'} to {self.markers}")

        # change .c3d file to match the self.c3d
        if os.path.exists(os.path.join(self.path, self.trial + '.c3d')):
            os.rename(os.path.join(self.path, self.trial + '.c3d'), os.path.join(self.path, self.c3d))
            print(f"Renamed {self.trial + '.c3d'} to {self.c3d}")

    def _update_model(self):
        '''
        update the model path in the xml settings based on the name of the subject, and save to XML. Models should be located in MODELS_DIR/subject/session/
        '''
        if self.subject == 'Athlete_03':
            self.update_model('scaled_12_05_2026.osim')

        elif self.subject == 'Athlete_03_Lernagopal':
            self.update_model('scaled_89_opt_N10.osim')

        elif self.subject == 'Athlete_03_Lernagopal_optimised':
            self.update_model('lernagopal_with_wrapings_scaled_opt_N10_increased_3.00.osim')

        elif self.subject == 'Athlete_03_MRI_Katya':
            self.update_model('scaled_opt_N10_increased_3.00.osim')

        elif self.subject == 'Athlete_03_GPK':
            self.update_model('GPK_scaled.osim')
        
        elif self.subject == 'Athlete_03_GPK_MRI':
            self.update_model('GPK_MRI_scaled.osim')

        elif self.subject == '022':
            self.update_model('022_Rajagopal2015_FAI_originalMass_opt_N10_hans.osim')
        
        elif self.subject in ['HC835B']:
            self.update_model('GPK_generic_Lukas_scaled.osim')
            
        else:
            self.update_model('scaled.osim')

    def _update_emg_tag(self):
        '''Update settingd XML with specific EMG types for a trial if needed'''
        if os.path.exists(os.path.join(self.path, 'EMG_filtered_normalised_scaled_0.70.sto')):
            emg_name = 'EMG_filtered_normalised_scaled_0.70.sto'
        elif os.path.exists(os.path.join(self.path, 'EMG_filtered_normalised.sto')):
            emg_name = 'EMG_filtered_normalised.sto'
        else:
            emg_name = _u.settings.Inputs().emg

        self.update_trial_attribute('emg', emg_name)
        self.update_trial_attribute('ceinms_excitations', emg_name)

    def _remove_outputs(self):
        '''Remove existing output files from the trial directory to ensure a clean slate for the analysis'''
        input_files = [self.emg, self.c3d, self.grf_mot, self.markers, self.events]
        # walk through the trial directory and delete any files that are not in the input_files list
        for root, dirs, files in os.walk(self.path):
            for file in files:
                if file not in input_files:
                    file_path = os.path.join(root, file)
                    try:
                        os.remove(file_path)
                        print(f"Deleted existing output file: {file_path}")
                    except Exception as e:
                        print(f"Failed to delete file {file_path}: {e}")

    def _trial_type(self):

        if self.trial.lower().__contains__('squat'):
            return 'squatting'

    def convert_to_dict(self, attr_name):
        '''Convert a specific attribute of the trial to a dictionary'''
        attr_value = getattr(self, attr_name, None)
        if attr_value is None:
            print(f"Attribute {attr_name} not found.")
            return None
        
        if isinstance(attr_value, dict):
            return attr_value
        elif isinstance(attr_value, str):
            try:
                # Attempt to evaluate the string as a dictionary
                attr_dict = eval(attr_value)
                if isinstance(attr_dict, dict):
                    return attr_dict
                else:
                    print(f"Attribute {attr_name} is not a dictionary.")
                    return None
            except:
                print(f"Failed to convert attribute {attr_name} to dictionary.")
                return None
        else:
            print(f"Attribute {attr_name} is not a string or dictionary.")
            return None
    
    def load_settings(self, settingsXML):
        '''Load all settings for the trial from an xml in trial.path'''
        tree = _u.ET.parse(settingsXML)
        root = tree.getroot()
        
        self.settingsXML = settingsXML
        
        for variable in root:
            var_name = variable.tag
            var_value = variable.text
            
            # Check if the attribute already exists
            if hasattr(self, var_name):
                current_attr = getattr(self, var_name)
            else:
                current_attr = None
                
            if var_name == 'time_range':
                try:
                    converted_value = [float(t) for t in var_value.strip('[]').split(', ')]
                except (ValueError, AttributeError, TypeError):
                    converted_value = None
            elif var_value.startswith('[') and var_value.endswith(']'):
                converted_value = var_value.strip('[]').split(', ')
            elif isinstance(current_attr, bool):
                converted_value = var_value.lower() == 'true'
            elif isinstance(current_attr, int):
                converted_value = int(var_value)
            elif isinstance(current_attr, float):
                converted_value = float(var_value)
            elif isinstance(current_attr, list):
                # Assuming list of strings separated by commas
                converted_value = var_value.strip('[]').split(', ')
            else:
                converted_value = var_value
            
            setattr(self, var_name, converted_value)
            
            # update self.path if path variable
            if var_name == "path":
                parent_dir = os.path.dirname(self.settingsXML)
                self.path = os.path.abspath(os.path.join(parent_dir, converted_value))
                

        print(f"Settings loaded from: {os.path.abspath(self.settingsXML)}")
    
    def load_results(self, tag, time_normalise=False):
        '''Load results from a specific output file in the trial directory based on the tag
        
        Options available same as settings.Inputs output file names (e.g 'ik', 'id', 'so_forces', 'ceinms_forces', etc.)

        '''

        # check if tag is valid (i.e present in the settings XML as an attribute)
        if not hasattr(self, tag):
            print(f"Tag '{tag}' not found in trial settings.")
            return None

        try:
            results = _u.load_any_data_file(os.path.join(self.path, getattr(self, tag)))
        except Exception as e:
            print(f"Error loading results for tag '{tag}'")
            return None
        
        if time_normalise and 'time' in results.columns:
            try:
                results = _u.time_normalise_df(results)
            except Exception as e:
                print(f"Error time normalising results for tag '{tag}': {e}")

        return results

    def get(self, attr_name):
        
        self = self.load_settings(self.settingsXML)
        
        return getattr(self, attr_name, None)
    
    def get_time_range_from_eventDetector(self):
        '''Get time range from event detector'''

        os.chdir(self.path)
        try:
            detector = _u.EventDetector()
            events = detector.analyze_task(trc_file=self.markers, grf_file=self.grf_mot, kinematics_file=self.ik, task=self._trial_type())
            return events
        
        except Exception as e:
            print(f"Error determining time range from events: {e}")
            return False

    def get_time_range(self):
        os.chdir(self.path)

        try:
            event_data = pd.read_csv(self.events, index_col=None, header=None)
            self.time_range = [event_data.iloc[:, 1].min(), event_data.iloc[:, 1].max()]
            return self.time_range
        except:
            pass

        try:
            if os.path.exists(self.markers):
                marker_data = _u.load_any_data_file(self.markers)
                # load_trc returns a MultiIndex DataFrame; df['time'] gives a sub-DataFrame
                # whose .min() would be a Series. Flatten to get scalar floats.
                time_col = marker_data['time']
                time_vals = time_col.values.flatten().astype(float)
                self.time_range = [float(time_vals.min()), float(time_vals.max())]
                return self.time_range
        except:
            pass

        try:
            if os.path.exists(self.c3d):
                c3d_data = _u.load_any_data_file(self.c3d)
                time_col = c3d_data['time']
                time_vals = time_col.values.flatten().astype(float)
                self.time_range = [float(time_vals.min()), float(time_vals.max())]
                return self.time_range
        except:
            pass
    
    def get_markers(self):
        '''
        return a dataFrame with the name of each marker in the model and it's parent body
        '''

        os.chdir(self.path)
        try:
            model = osim.Model(self.model_dir)
            state = model.initSystem()
            markers = model.getMarkerSet()
            marker_data = []
            for i in range(markers.getSize()):
                marker = markers.get(i)
                marker_data.append({'Marker': marker.getName(), 'Parent Body': marker.getBodyName()})
            return pd.DataFrame(marker_data)
        except Exception as e:
            print(f"Error loading model or markers: {e}")
            return None

    def update_trial_attribute(self, attr_name, new_value):      
        '''Update a specific attribute of the trial and save to XML'''
        setattr(self, attr_name, new_value)
        self._log(f'Updated {attr_name} to {new_value} for trial at {self.path}')
        self._to_xml()
    
    def delete_trial_attribute(self, attr_name):
        '''Delete a specific attribute of the trial and save to XML'''
        if hasattr(self, attr_name):
            delattr(self, attr_name)
            self._log(f'Deleted attribute {attr_name} for trial at {self.path}')
            self._to_xml()
        else:
            self._log(f'Attribute {attr_name} not found in trial at {self.path}')

    def copy_input_files(self, src_subject, replace=False):
        """
        Copy input files from a template subject to the trial directory if they don't already exist or if replace is True.

        src_subject: name of the subject to copy input files from (should be located in SIMULATIONS_DIR/subject/session/)
        replace: whether to replace existing files in the trial directory (default is False)

        """
        input_files = [
            'trial_settings.xml','EMG_filtered_normalised.sto','EMG_filtered_normalised_scaled_0.70.sto','marker_experimental.trc','events.csv','c3dfile.c3d','GRF.xml', 'grf.mot'
        ]
        
        trial = self.trial
        src_trial_path = os.path.join(_u.SIMULATIONS_DIR, src_subject, self.session, trial)
        dest_trial_path = self.path
        
        os.makedirs(dest_trial_path, exist_ok=True)
        
        for file_name in input_files:
            src_file = os.path.join(src_trial_path, file_name)
            dest_file = os.path.join(dest_trial_path, file_name)
            if os.path.exists(src_file) or replace:
                shutil.copy2(src_file, dest_file)
                print(f"Copied {src_file} to {dest_file}")
            else:
                print(f"Warning: {src_file} does not exist and was not copied.")

    # Model manipulation functions
    def update_model(self, new_model_name):
        '''Update the model path for the trial and save to XML
        
        new_model_name: str with just the name of the new model file (should be located in MODELS_DIR/subject/session/)

        Example usage:
            analysis = utils.Analyse(trialPath='main_dir/Subject/Session/trial')
            analysis.update_model('scaled_opt_N10_muscles_copied.osim')

        Output:
            Updated model path to main_dir/models/Subject/Session/scaled_opt_N10_muscles_copied.osim for trial at main_dir/Subject/Session/trial
        
        '''
        
        model_path = os.path.join(_u.MODELS_DIR, self.subject, self.session, new_model_name)
        rel_model_path = os.path.relpath(model_path, self.path)

        self.model_name = new_model_name
        self.model_dir = rel_model_path
        self._log(f'Updated model path to {model_path} for trial at {self.path}')
        self._to_xml()

        return self.model_dir

    def increase_muscle_force(self, factor: float = 1.0, muscle_list: list = ['all']):
        """Increase muscle force in the scaled model by a given factor.
        
        Args:
            factor (float): Factor to increase muscle force by. Default is 1.5.
            replace (bool): Whether to replace existing modified model. Default is False.
        """
        os.chdir(self.path)
        self.load_settings(self.settingsXML)
        
        model_path = os.path.join(self.path, self.model_dir)
        new_model_path = model_path.replace('.osim', f'_increased_{factor:.2f}.osim')


        if not os.path.exists(model_path):
            print(f"Scaled model not found: {self.model_dir}")
            return

        if os.path.exists(new_model_path) and not self.replace:
            print(f"Increased model already used: {self.model_dir}")
            return

        if muscle_list != ['all']:
            new_model_path = new_model_path.replace('.osim', f'_selected_muscles.osim')
        
        if os.path.exists(new_model_path) or not self.replace:
            print(f"Modified model already exists: {new_model_path}")
            self.model_dir = new_model_path
            return
        
        # Load the model
        model = osim.Model(self.model_dir)
        state = model.initSystem()
        
        # Increase max isometric force for each muscle
        for i in range(model.getMuscles().getSize()):
            muscle = model.getMuscles().get(i)
            if muscle_list == ['all'] or muscle.getName() in muscle_list:
                original_force = muscle.getMaxIsometricForce()
                new_force = original_force * factor
                muscle.setMaxIsometricForce(new_force)
                print(f"Muscle: {muscle.getName()}, Original Force: {original_force:.2f}, New Force: {new_force:.2f}")
        
        # Save the modified model
        model.printToXML(new_model_path)
        print(f"Modified model saved to: {os.path.abspath(new_model_path)}")
        
        # Update the used model path
        self.model_dir = new_model_path
        self._to_xml()

    def get_body_mass(self):
        """Retrieve body mass from the scaled model using OpenSim API funtion getTotalMass, and update the trial settings if it differs from the current body mass.
        
        Returns:
            float: Body mass in kg.
        """
        os.chdir(self.path)
        self.load_settings(self.settingsXML)
        
        if not os.path.exists(self.model_dir):
            print(f"Scaled model not found: {self.model_dir}")
            return 'Unknown'

        # Load the model
        model = osim.Model(self.model_dir)
        state = model.initSystem()
        
        body_mass = model.getTotalMass(state)
        print(f"Body mass from model: {body_mass:.2f} kg")

        if body_mass != self.body_mass:
            self.body_mass = body_mass
            self._to_xml()

        return body_mass

    def get_body_mass_from_grf(self, update=False):
        '''Calculate body mass from GRF data if available.'''
        os.chdir(self.path)

        try:
            grf_data = _u.load_any_data_file(self.grf_mot)
            vz_columns = [col for col in grf_data.columns if 'ground_force_' in col and col.endswith('_vy')]
            if 'time' in grf_data.columns and vz_columns:

                mean_1000ms = grf_data[vz_columns].iloc[:1000]
                body_mass = mean_1000ms.sum(axis=1).mean() / 9.81  
                print(f"Estimated body mass from GRF: {body_mass:.2f} kg")
                if update:
                    self.body_mass = body_mass
                    self._to_xml()
                return body_mass
        except Exception as e:
            print(f"Error calculating body mass from GRF: {e}")
            return None

    def get_muscle_list(self):
        """Retrieve list of muscles from the model_dir.
        
        Returns:
            list: List of muscle names.
        """
        os.chdir(self.path)
        
        if not os.path.exists(self.model_dir):
            print(f"Model not found: {self.model_dir}")
            return None

        # Load the model
        osim.Logger.setLevelString("error")
        model = osim.Model(self.model_dir)
        state = model.initSystem()
        
        muscle_list = [model.getMuscles().get(i).getName() for i in range(model.getMuscles().getSize())]
        # print(f"Muscles in model: {muscle_list}")
        return muscle_list

    def edit_model_range_coordinates(self, coordinate_name, new_range: list):
        """Change the range of motion for a specific degree of freedom in the model.
        
        Args:
            coordinate_name (str): Name of the coordinate to modify. 
            new_range (list): New range of motion as [min, max] in radians.
        """
        os.chdir(self.path)
        
        if not os.path.exists(self.model_dir):
            print(f"Model not found: {self.model_dir}")
            return
        
        _u.openSim.edit_model_range_coordinates(osim_modelPath=self.model_dir, coordinate_name=coordinate_name, new_range=new_range, save_path=self.model_dir)

    # analyses to run
    def scale_emg(self, scale_factor=1.0):
        """Scale EMG data by a given factor and save to a new file.
        
        Args:
            scale_factor (float): Factor to scale EMG data by. Default is 1.0.
        """
        os.chdir(self.path)
        if not os.path.exists(os.path.abspath(self.emg_normalised)):
            print(f"EMG normalised file not found: {self.emg_normalised}")
            return
        
        emg_data = _u.load_any_data_file(self.emg_normalised)
        
        # Scale all columns except 'time'
        for col in emg_data.columns:
            if col != 'time':
                emg_data[col] *= scale_factor
        
        scaled_emg_path = self.emg_normalised.replace('.sto', f'_scaled_{scale_factor:.2f}.sto')
        _u.write_sto_file(emg_data, os.path.abspath(scaled_emg_path))
        print(f"Scaled EMG data saved to: {os.path.abspath(scaled_emg_path)}")

        # Update the EMG normalised path
        self.update_trial_attribute('emg_normalised', scaled_emg_path)
        self.update_trial_attribute('emg_plot', scaled_emg_path)
        self.update_trial_attribute('ceinms_excitations', scaled_emg_path)
        
    def _log(self, message, terminal=False):
        """Log with trial name prefix."""
        _u.print_to_log(message, trial=self.trial, terminal=terminal)

    def export_c3d(self, create_folder=None, emg_string_list=_u.settings.BatchSettings.emg_string_list):
        '''
        Export C3D file using the exportC3D script, which extracts EMG data and saves it in a format compatible with CEINMS.

            create_folder: True/False to force subfolder creation; None (default) = auto-detect:
                           uses create_folder=True when the C3D is outside self.path so that
                           outputs land in the trial subdir regardless of where the C3D lives.

            emg_string_list: list of strings to identify EMG channels in the C3D file.
        '''
        import exportC3D

        print("Exporting C3D file...")

        os.chdir(self.path)
        c3d_abs = os.path.abspath(self.c3d)
        if not os.path.exists(c3d_abs):
            print(f"C3D file not found: {c3d_abs}")
            return

        if create_folder is None:
            # Auto: if the C3D is in a different directory than self.path,
            # tell exportC3D to create a subfolder (named after the C3D stem)
            # so all outputs land inside self.path.
            create_folder = (
                os.path.normcase(os.path.dirname(c3d_abs)) !=
                os.path.normcase(os.path.abspath(self.path))
            )

        time_range = exportC3D.main(c3d_filepath=c3d_abs, emg_string_list=emg_string_list, create_folder=create_folder)

        # Update start_time / end_time in trial_settings.xml from actual C3D data
        if time_range is not None:
            self.start_time = f"{time_range[0]:.4f}"
            self.end_time   = f"{time_range[1]:.4f}"
            self.time_range = list(time_range)
            self._to_xml()
            print(f"[{self.trial}] Time range updated: {self.start_time} – {self.end_time} s")

    @staticmethod
    def _get_openSim():
        """Return the openSim module, attempting a late import if it is still None."""
        if _u.openSim is not None:
            return _u.openSim
        try:
            from . import openSim as _os_mod
            _u.openSim = _os_mod
            return _u.openSim
        except Exception:
            pass
        try:
            import importlib.util as _ilu, os as _os_m
            _p = _os_m.path.join(_os_m.path.dirname(_os_m.path.abspath(_u.__file__)), 'openSim.py')
            _spec = _ilu.spec_from_file_location('utils.openSim', _p)
            _mod = _ilu.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            _u.openSim = _mod
            return _u.openSim
        except Exception as _e:
            raise RuntimeError(f"openSim module unavailable: {_e}") from _e

    def run_ik(self):
        os.chdir(os.path.abspath(self.path))
        self.load_settings(self.settingsXML)

        # Guard: IK requires a TRC file. If marker export failed (e.g. C3D has no 3D point data),
        # skip IK rather than hanging on an input() prompt or crashing inside osim.Storage().
        if not os.path.exists(self.markers):
            self._log(f'[SKIP] IK skipped — marker TRC not found: {self.markers}')
            return

        # Refresh time_range from data — TRC may not have existed when settings XML was first written.
        # Also catches the 'None' string produced when the XML was saved before export.
        _tr = getattr(self, 'time_range', None)
        if _tr is None or str(_tr).strip() in ('None', '[]', ''):
            self.time_range = self.get_time_range()

        # Create IK setup file if it doesn't exist or if replace is True
        _os = self._get_openSim()
        if not os.path.exists(self.setup_ik) or self.replace:
            _os.create_setup_IK(osim_modelPath=self.model_dir,
                                marker_trc=self.markers,
                                ik_output=self.ik,
                                taskSetPath=None,
                                time_range=self.time_range,
                                saveXMLPath=self.setup_ik)
        else:
            self._log(f'Inverse Kinematics output already exists: {self.ik}')
            return

        if os.path.exists(self.ik) and not self.replace:
            print(f'Inverse Kinematics output already exists: {self.ik}')
            return

        # Run IK using OpenSim API
        try:
            _os.run_ik(osim_modelPath=self.model_dir,
                    setup_xml=self.setup_ik,
                    resultsDir=self.path)
            self._log(f'[Success] Inverse Kinematics completed. Results are saved in {self.path}')
        except Exception as e:
            self._log(f'[Error] during Inverse Kinematics: {e}')
            raise  # propagate so _run_step logs it to the batch logger
        
        # Plot IK results and marker errors
        try:
            self.plot_ik()
            self.compare_marker_locations()
            self._log(f'[Success] IK results plotted and saved in {self.path}')
        except Exception as e:
            self._log(f'[Error] during IK plotting: {e}')

    def run_id(self):
        os.chdir(self.path)
        _os = self._get_openSim()
        if not os.path.exists(self.setup_grf) or self.replace:
            try:
                _os.create_grf_xml(grf_mot_path=self.grf_mot, 
                        output_xml_path=self.setup_grf,
                        marker_trc_path=self.markers,
                        right_foot_markers=getattr(_u.settings.BatchSettings, 'right_foot_markers', None),
                        left_foot_markers=getattr(_u.settings.BatchSettings, 'left_foot_markers', None),
                        right_foot_body='calcn_r', left_foot_body='calcn_l',
                        vert_force_threshold=10.0, filter_cutoff=6, datafile=None)
            except Exception as e:
                template_grf_path = os.path.join(self.setup_dir, self.setup_grf)
                if os.path.abspath(template_grf_path) != os.path.abspath(self.setup_grf):
                    shutil.copyfile(template_grf_path, self.setup_grf)

        if os.path.exists(self.id) and not self.replace:
            self._log(f'Inverse Dynamics output already exists: {self.id}')
            return
        
        # Run ID using OpenSim API
        try:
            _os.run_id(osimModelPath=self.model_dir,
                    ikOutputPath=self.ik,
                    grfXmlPath=self.setup_grf,
                    setupXmlPath=self.setup_id)
            
            self._log(f'[Success] Inverse Dynamics completed. Results are saved in {self.id}')
        except Exception as e:
            self._log(f'[Error] during Inverse Dynamics: {e}')
            raise

        # Plot ID results
        try:
            self.plot_id()
            self._log(f'[Success] ID results plotted and saved in {self.path}')
        except Exception as e:
            self._log(f'[Error] during ID plotting: {e}')

    def run_ma(self):
        
        os.chdir(self.path)
        if os.path.exists(self.ma) and not self.replace:
            self._log(f'Muscle Analysis output already exists: {self.ma}')
            return

        _os = self._get_openSim()
        try:
            _os.run_ma(osim_modelPath=self.model_dir,
                        ik_output=os.path.join(self.path, self.ik),
                        grf_xml=os.path.join(self.path, self.setup_grf))
            self._log(f'[Success] Muscle Analysis completed. Results are saved in {self.ma}')
        except Exception as e:
            self._log(f'[Error] during Muscle Analysis: {e}')
            raise
    
    def run_so(self):
        os.chdir(self.path)
        _os = self._get_openSim()

        # Resolve all paths to absolute so openSim.run_so never hits a
        # relative-path issue regardless of working directory changes.
        actuators_abs  = os.path.join(self.path, self.actuators_so)
        ik_abs         = os.path.join(self.path, self.ik)
        grf_abs        = os.path.join(self.path, self.setup_grf)
        setup_so_abs   = os.path.join(self.path, self.setup_so)

        if not os.path.exists(actuators_abs):
            # Copy template from the global setup folder
            template_dir = getattr(_u.settings.BatchSettings, 'setup_files_folder',
                                   os.path.join(_u.APP_DIR, 'config'))
            template_actuators_path = os.path.join(template_dir, self.actuators_so)
            if os.path.exists(template_actuators_path):
                shutil.copyfile(template_actuators_path, actuators_abs)
            else:
                raise FileNotFoundError(
                    f"Actuators template not found: {template_actuators_path}")

        if os.path.exists(os.path.join(self.path, self.so_forces)) and not self.replace:
            self._log(f'Static Optimization output already exists: {self.so_forces}')
            return

        try:
            _os.run_so(osim_modelPath=self.model_dir,
                    ik_output=ik_abs,
                    grf_xml=grf_abs,
                    setup_xml=setup_so_abs,
                    actuators=actuators_abs,
                    resultsDir=self.path)
            
            self._log(f'[Success] Static Optimization completed. Results are saved in:')
            self._log(f' - Forces: {os.path.abspath(self.so_forces)}')
            self._log(f' - Activations: {os.path.abspath(self.so_activations)}')
        except Exception as e:
            self._log(f'[Error] during Static Optimization: {e}')
            raise
        
        # Plot SO results
        try:
            self.plot_so()
            self._log(f'[Success] SO results plotted and saved in {self.path}')
        except Exception as e:
            self._log(f'[Error] during SO plotting: {e}')

    def run_energetics(self):
        """Run Metabolic Cost (Energetics) analysis for this trial.

        Wraps utils.openSim.run_energetics, which attaches an Umberger (2010)
        metabolic-energy probe set to the scaled model and runs a ProbeReporter.
        Needs the IK coordinates (kinematics) and, ideally, the Static
        Optimization activations (SO_StaticOptimization_activation.sto) so the
        probe evaluates real per-frame muscle activations.

        Output: energetics_ProbeReporter_probes.sto in the trial folder.
        """
        os.chdir(self.path)
        _os = self._get_openSim()

        ik_abs     = os.path.join(self.path, self.ik)
        so_act_abs = os.path.join(self.path, self.so_activations)
        out_abs    = os.path.join(self.path, 'energetics_ProbeReporter_probes.sto')

        if os.path.exists(out_abs) and not self.replace:
            self._log(f'Energetics output already exists: {out_abs}')
            return

        if not os.path.exists(ik_abs):
            raise FileNotFoundError(
                f'IK output required for energetics not found: {ik_abs}')

        if not os.path.exists(so_act_abs):
            self._log(f'[Warning] SO activation file not found ({so_act_abs}); '
                      f'energetics will use default activation.')
            so_act_abs = None

        try:
            _os.run_energetics(osim_modelPath=self.model_dir,
                               ik_output=ik_abs,
                               muscle_activations=so_act_abs,
                               setup_xml=None,
                               results_dir=self.path)
            self._log(f'[Success] Energetics completed. Results saved in {self.path}')
        except Exception as e:
            self._log(f'[Error] during Energetics: {e}')
            raise

    def run_jra(self):
        os.chdir(self.path)
        self.load_settings(self.settingsXML)
        _os = self._get_openSim()

        if not os.path.exists(self.setup_jra):
            template_jra_path = os.path.join(self.setup_dir, self.setup_jra)
            shutil.copyfile(template_jra_path, self.setup_jra)
             
        if os.path.exists(self.jra) and not self.replace:
            return
        try:
            _os.run_jra(osim_modelPath=self.model_dir,
                     ik_output=self.ik,
                     grf_xml=self.setup_grf,
                     setup_xml=self.setup_jra,
                     actuators=None,
                     muscle_force_path=self.jra_forces,
                     saveFileName=self.jra)
        
            self._log(f"JRA analysis complete. Results saved {os.path.abspath(self.jra)}")
        except Exception as e:
            self._log(f'[Error] during Joint Reaction Analysis: {e}')
            
    def run_jra_ceinms(self):
        os.chdir(self.path)
        self.load_settings(self.settingsXML)

        if not os.path.exists(self.setup_jra):
            template_jra_path = os.path.join(self.setup_dir, self.setup_jra)
            shutil.copyfile(template_jra_path, self.setup_jra)

        if os.path.exists(self.jra_ceinms) and not self.replace:
            self._log(f'JRA CEINMS output already exists: {self.jra_ceinms} and replace is set to False.')
            return
        
        try:
            _u.openSim.run_jra(osim_modelPath=self.model_dir,
                     ik_output=self.ik,
                     grf_xml=self.setup_grf,
                     setup_xml=self.setup_jra,
                     actuators=None,
                     muscle_force_path=self.jra_forces_ceinms,
                     saveFileName=self.jra_ceinms)
            
            self._log(f"JRA CEINMS analysis complete. Results saved {os.path.abspath(self.jra_ceinms)}")
        except Exception as e:
            self._log(f'[Error] during Joint Reaction Analysis CEINMS: {e}')
        

    def run_emg_filter(self):
        """Per-trial: filter raw EMG -> emg_filtered.mot."""
        os.chdir(self.path)
        emg_path = os.path.join(self.path, self.emg)
        if not os.path.exists(emg_path):
            self._log(f"[Warning] EMG file not found: {emg_path}")
            return
        out_path = os.path.join(self.path, 'emg_filtered.mot')
        if os.path.exists(out_path) and not self.replace:
            self._log(f"EMG filtered file already exists: {out_path}")
            return
        try:
            data = _u.load_any_data_file(emg_path)
            emg_cols = [c for c in data.columns if c.lower() != 'time']
            if not emg_cols:
                self._log("[Warning] No EMG columns found in emg.mot")
                return

            # --- Reliable EMG time vector + sampling frequency ---
            # Derive the sampling frequency from the EMG file's OWN time column
            # (the true analog rate) rather than a fixed setting, which is often
            # wrong (e.g. configured 1000 Hz while the data is 200 Hz). Only when
            # that time column is invalid (non-monotonic / all-zeros) do we rebuild
            # it, aligning to the trial's kinematic window so it matches IK/ID/GRF.
            data = data.copy()
            fs_setting = getattr(_u.settings.BatchSettings, 'emg_sampling_freq', None)
            n = len(data)
            t = (pd.to_numeric(data['time'], errors='coerce').values.astype(float)
                 if 'time' in data.columns else np.array([]))
            time_ok = n >= 2 and np.all(np.isfinite(t)) and np.all(np.diff(t) > 0)
            if time_ok:
                fs = 1.0 / ((t[-1] - t[0]) / (n - 1))
            else:
                fs = fs_setting or 1000.0
                try:
                    start_t = float(self.time_range[0])
                    end_t = float(self.time_range[1])
                    if not (end_t > start_t):
                        raise ValueError
                    data['time'] = np.linspace(start_t, end_t, n)
                except Exception:
                    data['time'] = np.arange(n) / fs
                self._log(f'[Info] EMG time column invalid — rebuilt '
                          f'({n} samples @ ~{fs:.0f} Hz, '
                          f'{data["time"].iloc[0]:.4f}..{data["time"].iloc[-1]:.4f}s)',
                          terminal=True)

            # Auto-detect prefix — use the longest common prefix of EMG columns,
            # falling back to empty string (filters all non-time columns)
            prefix = 'EMG_Channels_EMG'
            if not any(c.startswith(prefix) for c in emg_cols):
                prefix = ''   # let filter_emg handle whatever names are present

            filtered = _u.emg_normalise.filter_emg(data, emg_prefix=prefix, sampling_freq=fs)
            env_cols = [c for c in filtered.columns if c.endswith('_envelope')]
            if not env_cols:
                self._log("[Warning] filter_emg produced no envelope columns — check EMG prefix")
                return
            result = filtered[['time']].copy()
            for col in env_cols:
                base = col.replace('_bandpass_rectified_envelope', '').replace('_envelope', '')
                result[base] = filtered[col].values
            _u.emg_normalise.write_sto_file(result, out_path)
            # Report which channels have zero signal (electrode not connected?)
            zero_chs = [c for c in result.columns if c != 'time'
                        and pd.to_numeric(result[c], errors='coerce').abs().max() < 1e-9]
            if zero_chs:
                self._log(f"[Info] {len(zero_chs)} channel(s) have zero signal "
                          f"(electrode not connected?): {', '.join(zero_chs)}", terminal=True)
            self._log(f"[Success] EMG filtered ({len(env_cols)} channels, "
                      f"{len(env_cols) - len(zero_chs)} non-zero) -> {out_path}")
        except Exception as e:
            self._log(f"[Error] EMG filter failed: {e}")

    def _emg_envelope(self):
        """Rectified linear envelope of this trial's RAW EMG channels.

        Bandpass -> full-wave rectify -> low-pass (via emg_normalise.filter_emg),
        returning a DataFrame with ``time`` + one non-negative envelope column per
        ``EMG_Channels_EMG*`` channel (base-named, e.g. ``EMG_Channels_EMG09_gast_med_l``).
        Always reads the RAW emg.mot so it never compounds a previously
        normalised/filtered file. Returns ``None`` if no EMG is available.
        """
        raw = os.path.join(self.path, 'emg.mot')
        if not os.path.exists(raw):
            raw = os.path.join(self.path, self.emg)
        data = _u.load_any_data_file(raw)
        if data is None or 'time' not in data.columns:
            return None
        emg_cols = [c for c in data.columns if c.startswith('EMG_Channels_EMG')]
        if not emg_cols:
            return None
        data = data.copy()
        # Sampling frequency: prefer the file's own time vector, else settings.
        n = len(data)
        t = pd.to_numeric(data['time'], errors='coerce').values.astype(float)
        if n >= 2 and np.all(np.isfinite(t)) and np.all(np.diff(t) > 0):
            fs = 1.0 / ((t[-1] - t[0]) / (n - 1))
        else:
            fs = getattr(_u.settings.BatchSettings, 'emg_sampling_freq', None) or 1000.0
        filtered = _u.emg_normalise.filter_emg(data, emg_prefix='EMG_Channels_EMG',
                                               sampling_freq=fs)
        out = filtered[['time']].copy()
        for col in [c for c in filtered.columns if c.endswith('_envelope')]:
            base = col[:-len('_envelope')]
            # non-negative envelope (low-pass of a rectified signal can dip
            # slightly negative at the edges)
            out[base] = np.clip(filtered[col].values, 0.0, None)
        return out

    def run_emg_normalise(self):

        os.chdir(self.path)
        emg_normalise_list = []
        
        for trialName in os.listdir(self.parentdir):
            emgPath = os.path.join(self.parentdir, trialName, self.emg)
            if os.path.exists(emgPath):
                emg_normalise_list.append(emgPath)
                
        if not emg_normalise_list:
            self._log(f'[Error] No EMG files found to normalise in {self.parentdir}')
            return
        
        _u.openSim.run_emg_normalise(target_emg_path= str(self.emg),
                                normalise_emg_list=emg_normalise_list)
        
        self._log(f'[Success] EMG normalisation completed. Normalised EMG saved to {self.emg}')

        new_emg_name = os.path.basename(self.emg).replace('.mot', '_normalised.mot')

        self.update_trial_attribute('emg', new_emg_name)
        self.update_trial_attribute('ceinms_excitations', new_emg_name)
    
    def convert_mot_to_sto(self, attr=None):

        os.chdir(self.path)
        if attr:
            mot_file = getattr(self, attr)
        
        sto_file_path = mot_file.replace('.mot', '.sto')
        if os.path.exists(sto_file_path) and not self.replace:
            self._log(f'STO file already exists: {sto_file_path}')
            return
        
        sto_file_path = _u.openSim.convert_mot_to_sto(mot_file_path=os.path.abspath(mot_file))

        self.update_trial_attribute(attr, os.path.relpath(sto_file_path, self.path))

    def muscles_per_coordinate(self, osimModel=None, coord_name=None):

        if osimModel is None:
            osimModel = osim.Model(self.model_dir)

        muscles = []
        indexes = []
        coord = osimModel.getCoordinateSet().get(coord_name)
        state = osimModel.initSystem()
        osimModel.realizePosition(state)

        for i in range(osimModel.getMuscles().getSize()):
            muscle = osimModel.getMuscles().get(i)
            if abs(muscle.computeMomentArm(state, coord)) > 1e-4:
                muscles.append(muscle.getName())
                indexes.append(i)

        return muscles, indexes
    
    def calculate_muscle_moments(self, forces_type = 'so'):
        '''Calculate muscle moments by multiplying muscle forces by their moment arms for each coordinate.
        
        forces_type: 'so' for static optimization forces, 'ceinms' for CEINMS muscle forces (default is 'so')
        '''

        if forces_type == 'so':
            muscle_forces = _u.load_any_data_file(self.so_forces)
        elif forces_type == 'ceinms':
            muscle_forces = _u.load_any_data_file(self.jra_forces_ceinms)

        dofNames = _u.settings.BatchSettings.dof_list
        
        for dof_name in dofNames:
            moment_arms = _u.load_any_data_file(os.path.join(self.path,self.ma, f"_MuscleAnalysis_MomentArm_{dof_name}.sto"))

            # Multiply force x moment arm for the REAL muscles only — i.e. force
            # columns that also exist in the moment-arm file. Reserve actuators,
            # GRF residuals (FX..MZ), contact loads and other non-muscle columns
            # have no moment arm and are skipped silently. Build the frame in one
            # shot to avoid pandas fragmentation warnings.
            n = min(len(muscle_forces), len(moment_arms))
            cols = [m for m in muscle_forces.columns
                    if m.lower() != 'time' and m in moment_arms.columns]
            data = {m: muscle_forces[m].values[:n] * moment_arms[m].values[:n] for m in cols}
            muscle_moments = pd.DataFrame(data)
            if 'time' in muscle_forces.columns:
                muscle_moments.insert(0, 'time', muscle_forces['time'].values[:n])

            # save muscle moments to a new file
            moments_file_path = os.path.join(self.path, self.ma, f"_MuscleMoments_{dof_name}_{forces_type}.sto")
            _u.write_sto_file(muscle_moments, moments_file_path)
            print(f"Muscle moments saved to: {os.path.abspath(moments_file_path)}")

        return muscle_moments

    #--- Valid
    def compare_marker_locations(self):
        os.chdir(self.path)
        try:
            _u.openSim.compare_marker_locations(marker_experimental_path=os.path.abspath(self.markers),marker_virtual_path=os.path.abspath('.\\_ik_model_marker_locations.sto'))
        
            self._log(f'[Success] Marker location comparison completed: {self.model_markers} vs {self.markers}')
        except Exception as e:
            self._log(f'[Error] during marker location comparison: {e}')

    def check_moment_arms(self):
        ''' Using the openSim.py function checkMomentArms to plot moment arms for each coordinate and muscle, and compare to expected patterns based on muscle geometry.'''

        os.chdir(self.path)

        results = {}
        for leg in ['l', 'r']:
            try:
                wrong, disc, action, frames = _u.openSim.checkMuscleMomentArms(
                    model_file_path=self.model_dir,
                    ik_file_path=self.ik,
                    leg=leg,
                    threshold=0.005)
                results[leg] = {'wrong': bool(wrong), 'muscle_action': action, 'frames': frames}
            except Exception as e:
                self._log(f'[Error] during moment arm check for {leg} leg: {e}')
                results[leg] = {'wrong': False, 'muscle_action': [], 'frames': []}

        return results

    def adjust_moment_arms(self, radius_step: float = 0.002, max_iter: int = 20, skip_frames: int = 2):
        """
        Iteratively increases wrapping-surface radii for muscles that have moment-arm
        discontinuities beyond the first `skip_frames` frames, then re-runs the moment-arm
        check.  Stops when no qualifying discontinuities remain or `max_iter` is reached.
        The modified model is saved in place; a .bak copy is created on the first iteration.
        """
        import shutil
        import opensim as osim

        os.chdir(self.path)

        # Make a one-time backup of the original model
        backup_path = self.model_dir.replace('.osim', '_original_backup.osim')
        if not os.path.exists(backup_path):
                shutil.copy2(self.model_dir, backup_path)
                print(f'Backup saved: {backup_path}')

        for iteration in range(max_iter):
                print(f'\n--- Moment arm check: iteration {iteration + 1}/{max_iter} ---')
                results = self.check_moment_arms()

                # Collect muscles whose discontinuities occur after the skip window
                problem_muscles: set = set()
                for leg in ['l', 'r']:
                        leg_data = results.get(leg, {})
                        for action_str, frames in zip(leg_data.get('muscle_action', []),
                                                      leg_data.get('frames', [])):
                                real_frames = [int(f) for f in frames if int(f) >= skip_frames]
                                if real_frames:
                                        muscle_name = action_str.split(' ')[0]
                                        problem_muscles.add(muscle_name)

                if not problem_muscles:
                        print(f'No significant discontinuities after {iteration} iteration(s). Done.')
                        return

                print(f'  Muscles with discontinuities: {sorted(problem_muscles)}')
                print(f'  Increasing wrap-object radii by {radius_step} m ...')

                model = osim.Model(self.model_dir)
                model.initSystem()

                adjusted_wraps: set = set()
                for muscle_name in problem_muscles:
                        try:
                                muscle = model.getMuscles().get(muscle_name)
                        except Exception:
                                print(f'  [warn] muscle "{muscle_name}" not found in model – skipped')
                                continue

                        wrap_set = muscle.getGeometryPath().getWrapSet()
                        for w in range(wrap_set.getSize()):
                                wrap_name = wrap_set.get(w).getWrapObjectName()
                                if wrap_name in adjusted_wraps:
                                        continue  # already increased this iteration

                                # Search every body for the named wrap object
                                body_set = model.getBodySet()
                                for b in range(body_set.getSize()):
                                        body = model.updBodySet().get(b)
                                        wo_set = body.updWrapObjectSet()
                                        for k in range(wo_set.getSize()):
                                                wo = wo_set.get(k)
                                                if wo.getName() != wrap_name:
                                                        continue
                                                # Try WrapCylinder
                                                cyl = osim.WrapCylinder.safeDownCast(wo)
                                                if cyl is not None:
                                                        new_r = cyl.get_radius() + radius_step
                                                        cyl.set_radius(new_r)
                                                        adjusted_wraps.add(wrap_name)
                                                        print(f'    {muscle_name}: WrapCylinder "{wrap_name}" radius -> {new_r:.4f} m')
                                                        continue
                                                # Try WrapSphere
                                                sph = osim.WrapSphere.safeDownCast(wo)
                                                if sph is not None:
                                                        new_r = sph.get_radius() + radius_step
                                                        sph.set_radius(new_r)
                                                        adjusted_wraps.add(wrap_name)
                                                        print(f'    {muscle_name}: WrapSphere "{wrap_name}" radius -> {new_r:.4f} m')

                if not adjusted_wraps:
                        print('  No wrap objects found for the problem muscles – stopping.')
                        return

                model.printToXML(self.model_dir)
                print(f'  Model saved: {self.model_dir}')

        print(f'Max iterations ({max_iter}) reached – some discontinuities may remain.')

    def calculate_emg_activation_errors(self):
        '''Calculate errors between EMG activations and CEINMS excitations, and save to a new file.'''
        os.chdir(self.path)

        emg_data = _u.load_any_data_file(self.emg_normalised)
        ceinms_activations = _u.load_any_data_file(self.jra_forces_ceinms.replace('MuscleForces.sto', 'Activations.sto'))  
        so_activations = _u.load_any_data_file(self.so_activations)

        error_df = pd.DataFrame()

    def calculate_mean_marker_error(self):
        '''
        Load the _ik_marker_errors.sto file and calculate the mean marker error across all markers and time frames, and save to a new file.
        '''
        os.chdir(self.path)
        marker_errors = _u.load_any_data_file('.\\_ik_marker_errors.sto')
        mean_error = marker_errors.drop(columns='time').mean().mean()
        mean_error_df = pd.DataFrame({'mean_marker_error': [mean_error]})

        return mean_error_df

    def calculate_moment_errors(self, forces_type='so'):
        '''
        Calculate errors between muscle moments calculated from SO or CEINMS forces and the inverse dynamics joint moments, and save to a new file.
        '''
        os.chdir(self.path)
        
        id_moments = _u.load_any_data_file(self.id)
        muscle_forces = _u.load_any_data_file(self.so_forces) if forces_type == 'so' else _u.load_any_data_file(self.jra_forces_ceinms)
        dofNames = id_moments.columns.drop('time')

        moment_errors = pd.DataFrame(columns=['RMSE', 'RMSE %', 'R2'], index=dofNames)

        for dof_name in dofNames:
            try:
                moment_arms = _u.load_any_data_file(os.path.join(self.path,self.ma, f"_MuscleAnalysis_MomentArm_{dof_name}.sto"))
            except Exception as e:
                print(f"Error loading moment arms for {dof_name}: {e}")
                continue
            
            muscle_moments = pd.DataFrame()
            for muscle in muscle_forces.columns:
                if muscle in moment_arms.columns:
                    muscle_moments[muscle] = muscle_forces[muscle] * moment_arms[muscle]
                else:
                    print(f"Moment arm for muscle {muscle} not found in {moment_arms.columns}")
            
            total_muscle_moment = muscle_moments.sum(axis=1)
            id_moment = id_moments[dof_name]

            rmse = np.sqrt(np.mean((total_muscle_moment - id_moment) ** 2))
            rmse_pct = (rmse / np.abs(id_moment).max()) * 100
            ss_res = np.sum((id_moment - total_muscle_moment) ** 2)
            ss_tot = np.sum((id_moment - np.mean(id_moment)) ** 2)
            r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else np.nan
            
            moment_errors.loc[dof_name] = [rmse, rmse_pct, r2]
        
        return moment_errors 

    def scale_moment_arm(self, coordinate_name, muscles, factor):
        """
        Scale the moment arm of the given muscle(s) by *factor* and save a new .sto.

        Parameters
        ----------
        sto_path : path to the MomentArm .sto file (e.g. _MuscleAnalysis_MomentArm_hip_flexion_r.sto)
        muscles  : muscle name or list of muscle names matching column headers
        factor   : multiplicative scale factor (e.g. 1.5 increases moment arm by 50 %)

        Returns
        -------
        Path to the written output file.
        """
        if isinstance(muscles, str):
            muscles = [muscles]

        sto_path = os.path.join(self.ma, f"_MuscleAnalysis_MomentArm_{coordinate_name}.sto")
        data = _u.load_any_data_file(sto_path)

        missing = [m for m in muscles if m not in data.columns]
        if missing:
            available = [c for c in data.columns if c != "time"]
            raise ValueError(
                f"Muscle(s) not found in {sto_path.name}: {missing}\n"
                f"Available muscles: {available}"
            )

        data = data.copy()
        for muscle in muscles:
            data[muscle] = data[muscle] * factor

        output_path = sto_path.replace(".sto", ".sto")

        _u.write_sto_file(dataFrame=data, file_path=output_path)
        print(f"Saved scaled moment arm to: {output_path}")
        return output_path

        

    def plot_create_subplot(self, n_muscles, fig=None):
        ncols = int(math.ceil(math.sqrt(n_muscles)))
        nrows = int(math.ceil(n_muscles / ncols))
        if fig is None:
            fig, axes = plt.subplots(nrows, ncols, figsize=(ncols*5, nrows*4), constrained_layout=True)
            axes = axes.flatten()
        else:
            axes = fig.get_axes()

        # Hide any unused subplots
        for i in range(n_muscles, len(axes)):
            axes[i].axis('off')
        
        return fig, axes
      
    def plot_moment_arms(self, coord_name: str = None, fig=None):
        
        os.chdir(self.path)
        fileList = os.listdir(self.ma)
        fileList = [file for file in fileList if file.startswith('_MuscleAnalysis_MomentArm') and file.endswith('.sto')]
        
        for file in fileList:
            filepath = os.path.join(self.ma, file)
            if coord_name in file:
                break
            else:
                continue
        
        dof = file.replace('.sto','').replace('_MuscleAnalysis_MomentArm_','')
        print(f"Loading moment arms for DOF: {dof} from {file}")
        moment_arms = _u.load_any_data_file(filepath)
        muscleList,muscleIdx = self.muscles_per_coordinate(osim.Model(self.model_dir), dof)
        
        n_muscles = len(muscleList)
        if n_muscles == 0:
            print(f"No muscles found for DOF: {dof}")
            return None, None
        
        ncols = int(math.ceil(math.sqrt(n_muscles)))
        nrows = int(math.ceil(n_muscles / ncols))
        if fig is None:
            fig, axes = self.plot_create_subplot(n_muscles)
        else:
            axes = fig.get_axes()
        

        fig.suptitle(f"Moment Arms for DOF: {dof}", fontsize=16)
        line_label = f'{self.subject}_{self.session}_{self.trial}'
        for muscle in muscleList:
            ax = axes[muscleList.index(muscle)]
            ax.plot(moment_arms[muscle], label=line_label)
            ax.set_title(f"{muscle}")
            ax.set_xlabel("Time")
            ax.set_ylabel("Moment Arm")
        
        axes[0].legend()

        return fig, axes

    def plot_ik(self, columns_to_plot='all'):
        os.chdir(self.path)
        self.joint_angles = _u.load_any_data_file(self.ik)

        cols = list(self.joint_angles.columns)
        if 'time' in cols:
            cols.remove('time')
        if columns_to_plot != 'all':
            cols = [c for c in cols if c in columns_to_plot]

        # group left/right coordinates onto a single subplot per base name
        # (mirrors plot_id), e.g. hip_flexion_r + hip_flexion_l -> one subplot.
        groups, order = {}, []
        for c in cols:
            base, side = self._split_side(c)
            if base not in groups:
                groups[base] = {}
                order.append(base)
            groups[base][side or 'none'] = c

        fig, axes = self.plot_create_subplot(len(order))
        fig.suptitle("Inverse Kinematics Joint Angles", fontsize=16)
        side_style = {'r': ('tab:blue', 'right'), 'l': ('tab:red', 'left'), 'none': ('black', None)}
        t = self.joint_angles['time']
        for i, base in enumerate(order):
            ax = axes[i]
            for side, colname in groups[base].items():
                color, lab = side_style.get(side, ('black', None))
                ax.plot(t, self.joint_angles[colname], color=color, label=lab)
            ax.set_title(base)
            ax.set_xlabel("Time")
            ax.set_ylabel("Angle (degrees)")
            if any(s in groups[base] for s in ('r', 'l')):
                ax.legend(fontsize=8)

        # save figure and return
        save_path = os.path.join(self.path, f"{self.ik.replace('.mot', '.png')}")
        plt.savefig(save_path)
        print(f'Figure saved to {save_path}')

        return fig, axes
    
    @staticmethod
    def _split_side(name):
        """Return (base_name, side) where side is 'r', 'l' or None.

        Pairs e.g. 'hip_flexion_r_moment' / 'hip_flexion_l_moment' under the same
        base 'hip_flexion_moment'."""
        for tag in ('_r_', '_l_'):
            if tag in name:
                return name.replace(tag, '_'), tag[1]
        if name.endswith('_r'):
            return name[:-2], 'r'
        if name.endswith('_l'):
            return name[:-2], 'l'
        return name, None

    def plot_id(self, columns_to_plot='all'):
        self.inverse_dynamics = _u.load_any_data_file(self.id)

        cols = list(self.inverse_dynamics.columns)
        if 'time' in cols:
            cols.remove('time')
        if columns_to_plot != 'all':
            cols = [c for c in cols if c in columns_to_plot]

        # group left/right coordinates onto a single subplot per base name
        groups, order = {}, []
        for c in cols:
            base, side = self._split_side(c)
            if base not in groups:
                groups[base] = {}
                order.append(base)
            groups[base][side or 'none'] = c

        fig, axes = self.plot_create_subplot(len(order))
        fig.suptitle("Inverse Dynamics Joint Moments", fontsize=16)
        side_style = {'r': ('tab:blue', 'right'), 'l': ('tab:red', 'left'), 'none': ('black', None)}
        t = self.inverse_dynamics['time']
        for i, base in enumerate(order):
            ax = axes[i]
            for side, colname in groups[base].items():
                color, lab = side_style.get(side, ('black', None))
                ax.plot(t, self.inverse_dynamics[colname], color=color, label=lab)
            ax.set_title(base)
            ax.set_xlabel("Time")
            ax.set_ylabel("Moment (Nm)")
            if any(s in groups[base] for s in ('r', 'l')):
                ax.legend(fontsize=8)

        # save figure and return
        save_path = os.path.join(self.path, os.path.splitext(self.id)[0] + '.png')
        plt.savefig(save_path)
        print(f'Figure saved to {save_path}')

        return fig, axes
    
    def plot_so(self, ):
        os.chdir(self.path)
        so_forces = _u.load_any_data_file(self.so_forces)
        so_activations = _u.load_any_data_file(self.so_activations)
        emg_normalised = _u.load_any_data_file(self.emg)

        # crop to time range of the trial
        time_range = self.get_time_range()
        so_forces = so_forces[(so_forces['time'] >= time_range[0]) & (so_forces['time'] <= time_range[1])]
        so_activations = so_activations[(so_activations['time'] >= time_range[0]) & (so_activations['time'] <= time_range[1])]
        emg_normalised = emg_normalised[(emg_normalised['time'] >= time_range[0]) & (emg_normalised['time'] <= time_range[1])]


        # Coordinate names must match the OpenSim model (knee is 'knee_angle',
        # and the model has no 'knee_adduction').
        coordinates = {'hip_flexion': None, 'hip_adduction': None, 'hip_rotation': None,
                        'knee_angle': None,
                        'ankle_angle': None}
        
        muscleGroups = {}
        for coord in list(coordinates.keys()):
            for leg in ['_r', '_l']:
                coord_name = coord + leg
                try:
                    muscles, indexes = self.muscles_per_coordinate(osim.Model(self.model_dir), coord_name)
                    muscleGroups[coord_name] = muscles
                except Exception as e:
                    # remove the key from the dictionary if there is an error (e.g. coordinate not found in model)
                    print(f"Error finding muscles for coordinate {coord}: {e}")
                    coordinates.pop(coord, None)

        n_vars = len(muscleGroups)
        fig, axes = plt.subplots(n_vars//2, 2, figsize=(26, 14))
        
        fig.suptitle(f"Static Optimization Muscle Forces", fontsize=16)
        for irow, (coord, _) in enumerate(coordinates.items()):
            for icol, leg in enumerate(['_r', '_l']):
                coord_name = coord + leg
                muscles = muscleGroups.get(coord_name, [])
                if not muscles:
                    continue
                
                ax = axes[irow, icol]
                for muscle in muscles:
                    line1 = ax.plot(so_forces['time'], so_forces[muscle], label=muscle)
                    # on a secondary y-axis plot activations
                    activations = so_activations[muscle]

                ax.set_title(f"{coord_name}")
                ax.set_xlabel("Time")

                if icol == 0:
                    ax.set_ylabel("Force (N)")
        
        # Legend: collect actual handles from any subplot that has lines
        handles, labels = [], []
        for ax in axes.flat:
            for h, l in zip(*ax.get_legend_handles_labels()):
                if l not in labels:
                    handles.append(h)
                    labels.append(l)

        n_legend_cols = min(len(handles), 10)
        fig.legend(handles, labels, loc='lower center', ncol=n_legend_cols, fontsize='small',
                   bbox_to_anchor=(0.5, 0.0), bbox_transform=fig.transFigure)

        # save figure and return
        save_path = os.path.join(self.path, f"{self.trial}_SO_Muscle_Forces.png")
        plt.tight_layout(rect=[0, 0.18, 1, 1])  # reserve bottom 18% for legend
        plt.savefig(save_path, bbox_inches='tight')
        print(f'Figure saved to {save_path}')
        
        # save interactive figure
        interactive_save_path = save_path.replace('.png', '.html')
        # convert_to_interactive_fig(fig, interactive_save_path)

        return fig, axes
    
    def plot_jra(self, origin='SO'):
        os.chdir(self.path)
        if origin == 'CEINMS':
            self.jra_results = _u.load_any_data_file(self.jra_ceinms)
        else:
            self.jra_results = _u.load_any_data_file(self.jra)
        
        joints = {'Hip': ['hip_r_on_femur_r_in_femur_r_fx',         'hip_r_on_femur_r_in_femur_r_fy', 'hip_r_on_femur_r_in_femur_r_fz'],
            'Knee': ['walker_knee_r_on_tibia_r_in_tibia_r_fx', 'walker_knee_r_on_tibia_r_in_tibia_r_fy', 'walker_knee_r_on_tibia_r_in_tibia_r_fz'],
            'Ankle': ['ankle_r_on_talus_r_in_talus_r_fx', 'ankle_r_on_talus_r_in_talus_r_fy', 'ankle_r_on_talus_r_in_talus_r_fz']}

        n_vars = len(joints)
        fig, axes = self.plot_create_subplot(n_vars*4)
        
        fig.suptitle(f"Joint Reaction Analysis", fontsize=16)
        i_subplot = -1
        for row, (joint, components) in enumerate(joints.items()):
                        
            # 3d sum of reaction forces
            x = self.jra_results[components[0]]
            y = self.jra_results[components[1]]
            z = self.jra_results[components[2]]
            resultant = _u.sum3d(self.jra_results, components)
            
            i_subplot += 1  
            ax = axes[i_subplot]
            ax.plot(self.jra_results['time'], x, label='X')
            ax.set_title(f"{joint} - X Reaction Force")
            ax.set_ylabel("Reaction Force (N)")
            
            i_subplot += 1
            ax = axes[i_subplot]
            ax.plot(self.jra_results['time'], y, label='Y')
            ax.set_title(f"{joint} - Y Reaction Force")
            
            i_subplot += 1
            ax = axes[i_subplot]
            ax.plot(self.jra_results['time'], z, label='Z')
            ax.set_title(f"{joint} - Z Reaction Force")
            
            i_subplot += 1
            ax = axes[i_subplot]
            ax.plot(self.jra_results['time'], resultant, label='Resultant')
            ax.set_title(f"{joint} - Resultant Reaction Force")

            ax.set_ylabel("Reaction Force (N)")

            if row == 0:
                ax.legend(loc='upper right')
                
            if row == n_vars - 1:
                ax.set_xlabel("Time")
        
        # save figure and return
        savePath = os.path.join(self.path, f"{self.trial}_JRA_Results_{origin}.png")
        plt.savefig(savePath)
        print(f'Figure saved to {savePath}')

        return fig, axes
    
    def plot_emg(self):
        
        os.chdir(self.path)
        emg_file_path = os.path.abspath(self.emg)
        if not os.path.exists(emg_file_path):
            print(f"EMG file not found: {emg_file_path}")
            return
        
        self.emg_data = _u.load_any_data_file(emg_file_path)
        
        muscles = self.emg_data.columns

        n_vars = len(muscles)
        fig, axes = self.plot_create_subplot(n_vars)
        
        fig.suptitle(f"EMG Excitations", fontsize=16)
        for i, muscle in enumerate(muscles):
            ax = axes[i]
            ax.plot(self.emg_data['time'], self.emg_data[muscle], label=muscle)

            ax.set_title(f"{muscle}")
            ax.set_xlabel("Time")
            ax.set_ylabel("Excitation")
            # ax.set_ylim([0, 1])
            
            if i == 0:
                ax.legend(loc='upper right')
        
        # save figure and return
        savePath = emg_file_path.replace('.sto', '.png').replace('.mot', '.png')
        plt.savefig(savePath)
        print(f'Figure saved to {savePath}')

        return fig, axes
    
    def plot_summary(self):
        '''
        Plot summary of results for a trial and settings DOFs, including:

                - row 1 IK angles
                - row 2 ID moments + Muscle contributions to moments (Static Optimisation)
                - row 3 ID moments + Muscle contributions to moments (CEINMS)
                - row 4 EMG vs SO excitations vs CEINMS excitations (with RMSE and R2 metrics)
                - row 5 JRA reaction loads (SO vs CEINMS)
        '''

        def calculate_muscle_moments(muscle_forces, moment_arms):
                # Ensure muscle forces and moment arms have the same columns
                common_muscles = sorted(set(muscle_forces.columns) & set(moment_arms.columns))
                if not common_muscles:
                        raise ValueError("No common muscles found between forces and moment arms.")
                
                # Build all columns at once to avoid fragmentation warning
                cols = {muscle: muscle_forces[muscle].values * moment_arms[muscle].values for muscle in common_muscles}

                # add time column if exists in muscle_forces
                if 'time' in muscle_forces.columns:
                        cols['time'] = muscle_forces['time'].values

                return pd.DataFrame(cols, index=muscle_forces.index)
        
        def plot_emg_vs_activations(ax, analysis: Analyse, emg, muscle_activations_so, muscle_activations_ceinms, dof, colors):
                emg_mapping = _u.settings.EMG_muscle_mapping

                try:
                        muscles = analysis.muscles_per_coordinate(coord_name=dof)
                        muscles_for_coord = set(muscles[0]) if muscles and muscles[0] else set()
                except Exception:
                        muscles_for_coord = set()

                # Find EMG channels that map to muscles active in this DOF
                filtered_emg_mapping = {
                        channel: filtered
                        for channel, muscle_list in emg_mapping.items()
                        if (filtered := [m for m in muscle_list if m in muscles_for_coord])
                }

                # Plot relevant EMG envelope columns
                if emg is not None:
                    for emg_col, mapped_muscles in filtered_emg_mapping.items():
                        

                        
                        # Plot EMG col
                        emg_line, = ax.plot(emg['time'], emg[emg_col], label=f'EMG {emg_col}', color=colors['EMG'], alpha=0.6)

                        # Plot SO activations per muscle for this DOF
                        so_act_line = ax.plot(so_activations['time'], so_activations[mapped_muscles].mean(axis=1), label='SO Activations', color=colors['SO'], alpha=0.6, linestyle='-')  # placeholder for legend

                        # Plot CEINMS activations per muscle for this DOF
                        ceinms_act_line = ax.plot(ceinms_activations['time'], ceinms_activations[mapped_muscles].mean(axis=1), label='CEINMS Activations', color=colors['CEINMS'], alpha=0.6, linestyle='-')  # placeholder for legend

                # Add space in the y axis to display metrics RMSE and R2
                y_min, y_max = ax.get_ylim()
                ax.set_ylim(y_min, y_max + abs(y_max - y_min)*0.5)
                if emg is not None and (muscle_activations_so is not None or muscle_activations_ceinms is not None):
                    if muscle_activations_so is not None:
                        total_activation_so = muscle_activations_so[[m for m in muscles_for_coord if m in muscle_activations_so.columns]].mean(axis=1)
                        rmse_so = rmse(emg[emg_col], total_activation_so)
                        r2_so = _u.rsquared(emg[emg_col], total_activation_so)
                        rmse_percentage_so = (rmse_so / (y_max - y_min)) * 100 if (y_max - y_min) != 0 else 0
                        ax.text(0.05, 0.90, f'SO Activations vs EMG\nRMSE: {rmse_so:.2f} (% {rmse_percentage_so:.2f})\nR2: {r2_so:.2f}', transform=ax.transAxes, fontsize=6, verticalalignment='top')

                    if muscle_activations_ceinms is not None:
                        total_activation_ceinms = muscle_activations_ceinms[[m for m in muscles_for_coord if m in muscle_activations_ceinms.columns]].mean(axis=1)
                        rmse_ceinms = rmse(emg[emg_col], total_activation_ceinms)
                        r2_ceinms = _u.rsquared(emg[emg_col], total_activation_ceinms)
                        rmse_percentage_ceinms = (rmse_ceinms / (y_max - y_min)) * 100 if (y_max - y_min) != 0 else 0
                        ax.text(0.05, 0.80, f'CEINMS Activations vs EMG\nRMSE: {rmse_ceinms:.2f} (% {rmse_percentage_ceinms:.2f})\nR2: {r2_ceinms:.2f}', transform=ax.transAxes, fontsize=6, verticalalignment='top')
        
        dofs = _u.settings.BatchSettings.dof_list
        n_rows = 5
        n_cols = len(dofs)
        colors = {'externalBiomech':'blue','SO': 'green', 'CEINMS': 'red', 'EMG': 'gray'}

        fig, ax = plt.subplots(nrows=int(n_rows), ncols=int(n_cols), figsize=(18, 8), constrained_layout=False)
        plt.suptitle('Summary of Results', y=1.02, fontsize=16)

        ik_angles = self.load_results('ik', time_normalise=True)
        id_moments = self.load_results('id', time_normalise=True)
        so_forces = self.load_results('so_muscle_forces', time_normalise=True)
        ceinms_forces = self.load_results('ceinms_muscle_forces', time_normalise=True)

        so_activations = self.load_results('so_activations', time_normalise=True)
        ceinms_activations = self.load_results('ceinms_activations', time_normalise=True)
        emg = self.load_results('emg', time_normalise=True)

        jra_so = self.load_results('jra_so', time_normalise=True)
        jra_ceinms = self.load_results('jra_ceinms', time_normalise=True)

        # normalised fibre lengths: MuscleAnalysis (SO side) vs CEINMS NormFibreLengths
        def _load_norm_fibre(path):
                try:
                        if path and os.path.exists(path):
                                return _u.time_normalise_df(_u.load_any_data_file(path))
                except Exception:
                        pass
                return None
        fibre_so = _load_norm_fibre(os.path.join(self.path, self.ma, "_MuscleAnalysis_NormalizedFiberLength.sto"))
        fibre_ceinms = None
        _cf = getattr(self, 'jra_forces_ceinms', None)
        if _cf:
                fibre_ceinms = _load_norm_fibre(os.path.join(self.path, _cf.replace('MuscleForces.sto', 'NormFibreLengths.sto')))

        row_ylabels = ['Angle (°)', 'EMG / activation', 'Moment (Nm)', 'Norm. fibre length', 'JRA (N)']

        jra_plotted = []
        for col_idx, dof in enumerate(dofs):
                col_name = f'{dof}_angle' if ik_angles is not None and f'{dof}_angle' in ik_angles.columns else dof

                # load moment arms for this DOF
                moment_arms = _u.load_any_data_file(os.path.join(self.path, self.ma, f"_MuscleAnalysis_MomentArm_{dof}.sto"))
                moment_arms = _u.time_normalise_df(moment_arms) 

                # calculate SO muscle moments for this DOF
                try:
                        muscle_moments_so = calculate_muscle_moments(so_forces, moment_arms) if so_forces is not None and moment_arms is not None else None
                except Exception as e:
                        print(f"Failed to calculate SO muscle moments for {dof}")
                        muscle_moments_so = None

                # calculate CEINMS muscle moments for this DOF
                try:
                        muscle_moments_ceinms = calculate_muscle_moments(ceinms_forces, moment_arms) if ceinms_forces is not None and moment_arms is not None else None
                except Exception as e:
                        print(f"Failed to calculate CEINMS muscle moments for {dof}")
                        muscle_moments_ceinms = None

                # plot IK angles
                if ik_angles is not None and col_name in ik_angles.columns:
                        ax[0, col_idx].plot(ik_angles['time'], ik_angles[col_name], color='blue')
                        ax[0, col_idx].set_title(dof, fontsize=8)
                
                # row 2: EMG vs SO and CEINMS activations
                if emg is not None or so_activations is not None or ceinms_activations is not None:
                        plot_emg_vs_activations(ax[1, col_idx], self, emg, so_activations, ceinms_activations, dof, colors)

                # row 3: joint moments + muscle contributions, SO vs CEINMS (vs ID)
                ax_m = ax[2, col_idx]
                # CEINMS execution weights used (alpha/beta/gamma), shown on its label
                abg = f" (a{getattr(self, 'alpha', '?')} b{getattr(self, 'beta', '?')} g{getattr(self, 'gamma', '?')})"
                if id_moments is not None and f'{dof}_moment' in id_moments.columns:
                        ax_m.plot(id_moments['time'], id_moments[f'{dof}_moment'], color='black', linewidth=1.5, label='ID')
                for mm_src, src_color, src_label, src_ls in (
                        (muscle_moments_so, colors['SO'], 'SO', '-'),
                        (muscle_moments_ceinms, colors['CEINMS'], 'CEINMS', ':')):
                        if mm_src is None:
                                continue
                        mcols = [c for c in mm_src.columns if c != 'time']
                        for muscle in mcols:
                                ax_m.plot(mm_src['time'], mm_src[muscle], color=src_color, linewidth=0.5, alpha=0.35, linestyle=src_ls)
                        if mcols:
                                total = mm_src[mcols].sum(axis=1)
                                lbl = f'{src_label} total' + (abg if src_label == 'CEINMS' else '')
                                ax_m.plot(mm_src['time'], total, color=src_color, linewidth=1.5, linestyle='--', label=lbl)
                                if id_moments is not None and f'{dof}_moment' in id_moments.columns:
                                        try:
                                                r = rmse(id_moments[f'{dof}_moment'], total)
                                                r2 = _u.rsquared(id_moments[f'{dof}_moment'], total)
                                                ax_m.text(0.02, 0.98 - (0.10 if src_label == 'CEINMS' else 0.0),
                                                          f'{src_label}: RMSE {r:.1f}, R2 {r2:.2f}',
                                                          transform=ax_m.transAxes, fontsize=6, va='top', color=src_color)
                                        except Exception:
                                                pass
                if col_idx == len(dofs) - 1:
                        ax_m.legend(loc='upper right', fontsize=6)

                # row 4: normalised muscle-fibre lengths, SO (MuscleAnalysis) vs CEINMS
                try:
                        _mlist = self.muscles_per_coordinate(coord_name=dof)
                        _muscles = set(_mlist[0]) if _mlist and _mlist[0] else set()
                except Exception:
                        _muscles = set()
                for _src, _c, _ls, _lab in ((fibre_so, colors['SO'], '-', 'SO'),
                                            (fibre_ceinms, colors['CEINMS'], '--', 'CEINMS')):
                        if _src is None:
                                continue
                        _fcols = [c for c in _src.columns if c != 'time' and (not _muscles or c in _muscles)]
                        for _i, _m in enumerate(_fcols):
                                ax[3, col_idx].plot(_src['time'], _src[_m], color=_c, linewidth=0.7,
                                                    alpha=0.7, linestyle=_ls, label=_lab if _i == 0 else None)
                if col_idx == len(dofs) - 1:
                        ax[3, col_idx].legend(loc='upper right', fontsize=6)

                # plot JRA reaction loads (SO vs CEINMS)
                jra_groups = _u.settings.JCF_Groups
                joint = dof.split('_')[0]  # extract joint name from DOF (e.g. 'hip' from 'hip_flexion_r')
                if jra_so is not None and jra_ceinms is not None and not jra_plotted.__contains__(joint):
                        
                    current_group = jra_groups[joint]

                    x_so = jra_so[current_group[0]]
                    y_so = jra_so[current_group[1]]
                    z_so = jra_so[current_group[2]]
                    resultant_so = _u.sum3d(jra_so, current_group)
                    
                    x_ceinms = jra_ceinms[current_group[0]]
                    y_ceinms = jra_ceinms[current_group[1]]
                    z_ceinms = jra_ceinms[current_group[2]]
                    resultant_ceinms = _u.sum3d(jra_ceinms, current_group)

                    ax[4, col_idx].plot(jra_so['time'], resultant_so, label='SO Resultant', color=colors['externalBiomech'], linestyle='--')

                    ax[4, col_idx].plot(jra_ceinms['time'], resultant_ceinms, label='CEINMS Resultant', color=colors['CEINMS'], linestyle='--')
                    
                    if col_idx == 0:
                        ax[4, col_idx].set_ylabel("Reaction Load (N)")
                    
                    if col_idx == len(dofs) - 1:
                        ax[4, col_idx].legend(loc='upper right', fontsize=6)

                    ax[4, col_idx].set_xlabel("Time")

                    jra_plotted.append(joint)

        # y-labels on first column only
        for row_idx, ylabel in enumerate(row_ylabels):
                ax[row_idx, 0].set_ylabel(ylabel)

        _u.mmfn(fig, n_rows, n_cols)

        # save figure
        save_path = os.path.join(self.path, 'summary_plot.png')
        plt.savefig(save_path, bbox_inches='tight')
        print(f'Summary plot saved to: {save_path}')

      
    # ceinms
    def create_ceinms_model(self):
        os.chdir(self.path)
        if os.path.exists(self.ceinms_uncalibrated_model) and not self.replace:
            self._log(f'CEINMS uncalibrated model already exists: {os.path.abspath(self.ceinms_uncalibrated_model)}')
            return
        # Stale calibrated model must be regenerated after uncalibrated is rebuilt
        if os.path.exists(self.ceinms_calibrated_model):
            try:
                os.remove(self.ceinms_calibrated_model)
                self._log(f'Removed stale calibrated model: {self.ceinms_calibrated_model}')
            except Exception:
                pass
        try:
            _u.ceinms.create_ceinms_model(osimModelPath=self.model_dir,
                                   outputCEINMSModelPath=self.ceinms_uncalibrated_model)
            self._log(f'[Success] CEINMS uncalibrated model created: {os.path.abspath(self.ceinms_uncalibrated_model)}')
        except Exception as e:
            self._log(f'[Error] Failed to create CEINMS uncalibrated model: {e}')
    
    def _fix_emg_timestamps(self, emg_file: str) -> str:
        """
        If the EMG file has wrong timestamps (common C3D export bug), reconstruct
        the time column using BatchSettings.emg_sampling_freq and the IK start time.
        Returns the (possibly corrected) filename to use.
        """
        emg_sampling_freq = getattr(_u.settings.BatchSettings, 'emg_sampling_freq', None)
        if not emg_sampling_freq:
            return emg_file

        emg_path = os.path.join(self.path, emg_file)
        if not os.path.exists(emg_path):
            self._log(f'[Warning] EMG file not found: {emg_path}  '
                      f'-- run C3D export first (enable_c3d_export = True)', terminal=True)
            return emg_file

        try:
            df = _u.load_any_data_file(emg_path)
            if df is None or 'time' not in df.columns or len(df) < 2:
                return emg_file

            n = len(df)
            tvals = df['time'].to_numpy(dtype=float)
            diffs = np.diff(tvals)
            actual_dt = float(np.median(diffs)) if diffs.size else 0.0
            expected_dt = 1.0 / emg_sampling_freq

            self._log(f'EMG timestamps: n={n}, dt={actual_dt:.6f}s '
                      f'(configured {expected_dt:.6f}s at {emg_sampling_freq} Hz), '
                      f'time {tvals[0]:.4f}..{tvals[-1]:.4f}s', terminal=True)

            # Only reconstruct timestamps that are ACTUALLY broken — i.e. not a sane,
            # strictly increasing series (dt<=0, non-finite, or duplicated times, the
            # real C3D-export bug). A valid monotonic time column is trusted even if
            # the true sampling rate differs from emg_sampling_freq (e.g. EMG exported
            # at 200 Hz while the setting says 1000 Hz). Trusting the setting over
            # correct data squashes the EMG into the wrong (too-short) time window and
            # crops CEINMS (e.g. a 1.08 s trial collapsed to ~0.49 s).
            monotonic = bool(diffs.size) and bool(np.all(np.isfinite(diffs))) and bool(np.all(diffs > 0))
            if np.isfinite(actual_dt) and actual_dt > 0 and monotonic:
                return emg_file  # timestamps are fine — leave them untouched

            # Broken timestamps -> rebuild. Prefer the detected rate if usable, else
            # fall back to the configured emg_sampling_freq.
            fs = (1.0 / actual_dt) if (np.isfinite(actual_dt) and actual_dt > 0) else float(emg_sampling_freq)
            try:
                start_t = float(self.time_range[0]) if self.time_range else 0.0
            except Exception:
                start_t = 0.0

            df = df.copy()
            df['time'] = start_t + np.arange(n) / fs
            self._log(f'[Info] Rebuilt broken EMG timestamps -> {df["time"].iloc[0]:.4f}..{df["time"].iloc[-1]:.4f}s', terminal=True)

            # Overwrite the source file in-place — no extra emg_ceinms.mot created
            _u.emg_normalise.write_sto_file(df, emg_path)
            return emg_file
        except Exception as e:
            self._log(f'[Warning] Could not fix EMG timestamps: {e}', terminal=True)
            return emg_file

    def create_ceinms_input_data(self):
        os.chdir(self.path)
        # Prefer the session-normalised CEINMS excitations (emg_ceinms.mot): a
        # rectified, low-pass enveloped, session-max normalised signal clipped to
        # [0,1] — the only range CEINMS accepts. Fall back to older normalised /
        # filtered / raw EMG only if it hasn't been built yet.
        excitations = None
        for candidate in (self.ceinms_excitations, 'emg_ceinms.mot'):
            if candidate and os.path.exists(os.path.join(self.path, candidate)):
                excitations = candidate
                break
        if excitations is None:
            for candidate in ('emg_filtered_normalised.mot', 'emg_normalised.mot',
                              'emg_filtered.mot', self.emg):
                if os.path.exists(os.path.join(self.path, candidate)):
                    excitations = candidate
                    break
            else:
                excitations = self.emg  # absolute fallback

        self._log(f"CEINMS excitations: selected '{excitations}' "
                  f"(exists={os.path.exists(os.path.join(self.path, excitations))}), "
                  f"time_range={self.time_range}", terminal=True)

        # Fix EMG timestamps if the C3D export produced wrong time values
        excitations = self._fix_emg_timestamps(excitations)

        # Cap startStopTime to the actual EMG data range to avoid
        # "Input data does not cover CEINMS time range" warnings
        try:
            _emg_df = _u.load_any_data_file(os.path.join(self.path, excitations))
            if _emg_df is not None and 'time' in _emg_df.columns and len(_emg_df) > 0:
                _emg_start = float(_emg_df['time'].iloc[0])
                _emg_end = float(_emg_df['time'].iloc[-1])
                _tr = self.time_range if isinstance(self.time_range, (list, tuple)) else [0.0, 1e9]
                input_time_range = [max(float(_tr[0]), _emg_start), min(float(_tr[1]), _emg_end)]
            else:
                input_time_range = self.time_range
        except Exception:
            input_time_range = self.time_range

        try:
            _u.ceinms.create_input_data(MAFolder=self.ma,
                                     excitationsFile=excitations,
                                     motionFile=self.ik,
                                     externalTorquesFile=self.id,
                                     externalLoadsFile=self.setup_grf,
                                     startStopTime=input_time_range)
            self._log(f'[Success] CEINMS input data created: {os.path.abspath(self.ceinms_input_data)}', terminal=True)
        except Exception as e:
            self._log(f'[Error] Failed to create CEINMS input data: {e}', terminal=True)
    
    def create_ceinms_calibration_cfg(self, calibration_trial_names=None):
        """
        Create ceinms_cfg_calibration.xml for CEINMS calibration.
        """
        
        os.chdir(self.path)
        inputPaths = []
        for trial_name in calibration_trial_names:
            filepath = os.path.join(self.parentdir, trial_name, _u.settings.Inputs().ceinms_input_data)
            inputPaths.append(os.path.relpath(filepath, self.parentdir))
        
        _u.ceinms.create_calibrationCfg(osimModelPath=self.model_dir,
                                     inputPaths=inputPaths,
                                     outputPath=self.ceinms_calibration_cfg)

    def create_excitation_generator(self):
        import traceback as _tb
        os.chdir(self.path)
        _abs_eg = os.path.abspath(self.ceinms_excitation_generator)
        self._log(f'CEINMS excitation generator path: {_abs_eg} (exists={os.path.exists(_abs_eg)})', terminal=True)
        if os.path.exists(_abs_eg) and not self.replace:
            self._log(f'CEINMS excitation generator already exists: {_abs_eg}', terminal=True)
            return
        
        try:
            _u.ceinms.create_excitation_generator(osim_model_path=self.model_dir,
                                               emg_path=self.ceinms_excitations,
                                               save_path=self.ceinms_excitation_generator
            )
            self._log(f'[Success] CEINMS excitation generator created: {_abs_eg}', terminal=True)
        except Exception as e:
            self._log(f'[Error] Failed to create CEINMS excitation generator: {e}\n{_tb.format_exc()}', terminal=True)
                
    def create_ceinms_cfg_from_excitation_generator(self):
        """
        Create ceinms_cfg_optimise.xml based on excitationGenerator.xml
        
        Args:
            excitation_file: Path to excitationGenerator.xml
            output_file: Path for output ceinms_cfg_optimise.xml
        """
        os.chdir(self.path)
        excitation_file = self.ceinms_excitation_generator
        output_file = self.ceinms_exe_cfg
        
        # Parse the excitation generator XML
        tree = _u.ET.parse(excitation_file)
        root = tree.getroot()
        
        # Lists to store muscle names
        synth_mtus = []
        adjust_mtus = []
        
        # Find all excitation elements
        mapping = root.find('mapping')
        if mapping is not None:
            for excitation in mapping.findall('excitation'):
                muscle_id = excitation.get('id')
                
                # Check if excitation has input elements (non-empty)
                inputs = excitation.findall('input')
                if inputs and len(inputs) > 0:
                    # Has EMG input - add to adjustMTUs
                    adjust_mtus.append(muscle_id)
                else:
                    # No EMG input - add to synthMTUs
                    synth_mtus.append(muscle_id)
        
        # Sort the lists for consistent output
        synth_mtus.sort()
        adjust_mtus.sort()
        
        # Create the XML structure
        execution = _u.ET.Element('execution')
        
        # Add XML declaration attributes
        execution.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        
        nms_model = _u.ET.SubElement(execution, 'NMSmodel')
        type_elem = _u.ET.SubElement(nms_model, 'type')
        hybrid = _u.ET.SubElement(type_elem, 'hybrid')
        
        # Add hybrid parameters
        _u.ET.SubElement(hybrid, 'alpha').text = '1'
        _u.ET.SubElement(hybrid, 'beta').text = '4'
        _u.ET.SubElement(hybrid, 'gamma').text = '120'
        
        # Add DOF set (you may need to adjust this based on your model)
        dof_set = _u.ET.SubElement(hybrid, 'dofSet')
        dof_set.text = _u.settings.CEINMSSettings.dof_set
        
        # Add synthMTUs
        synth_mtus_elem = _u.ET.SubElement(hybrid, 'synthMTUs')
        synth_mtus_elem.text = ' '.join(synth_mtus)
        
        # Add adjustMTUs
        adjust_mtus_elem = _u.ET.SubElement(hybrid, 'adjustMTUs')
        adjust_mtus_elem.text = ' '.join(adjust_mtus)
        
        # Add algorithm section
        algorithm = _u.ET.SubElement(hybrid, 'algorithm')
        sim_annealing = _u.ET.SubElement(algorithm, 'simulatedAnnealing')
        _u.ET.SubElement(sim_annealing, 'noEpsilon').text = '4'
        _u.ET.SubElement(sim_annealing, 'rt').text = '0.3'
        _u.ET.SubElement(sim_annealing, 'T').text = '20000'
        _u.ET.SubElement(sim_annealing, 'NS').text = '15'
        _u.ET.SubElement(sim_annealing, 'NT').text = '5'
        _u.ET.SubElement(sim_annealing, 'epsilon').text = '0.001'
        _u.ET.SubElement(sim_annealing, 'maxNoEval').text = '200000'
        
        # Add tendon section
        tendon = _u.ET.SubElement(nms_model, 'tendon')
        equilibrium = _u.ET.SubElement(tendon, 'equilibriumElastic')
        _u.ET.SubElement(equilibrium, 'tolerance').text = '1e-09'
        
        # Add activation section
        activation = _u.ET.SubElement(nms_model, 'activation')
        _u.ET.SubElement(activation, 'exponential')
        
        # Create tree and write to file
        tree = _u.ET.ElementTree(execution)
        _u.save_pretty_xml(tree, output_file)
        
        print(f"Created {output_file}")
        print(f"synthMTUs: {len(synth_mtus)} muscles")
        print(f"adjustMTUs: {len(adjust_mtus)} muscles")
    
    def create_ceinms_calibration_setup(self):
        os.chdir(self.path)
        _u.ceinms.create_calibrationSetupXML(uncalibratedCEINMSModelPath=self.ceinms_uncalibrated_model,
                                           excitationGeneratorFile=self.ceinms_excitation_generator,
                                           calibrationCfgPath=self.ceinms_calibration_cfg,
                                           outputSubjectFile=self.ceinms_calibrated_model,
                                           outputDirectory=self.ceinms_calibration_dir,
                                           setupXMLPath=self.ceinms_calibration_setup)

    def create_ceinms_optimise_setup(self):
        os.chdir(self.path)
        
        if os.path.exists(self.ceinms_optimise_setup) and not self.replace:
            self._log(f'CEINMS optimisation setup already exists: {os.path.abspath(self.ceinms_optimise_setup)}', terminal=True)
            return
        
        _u.ceinms.create_optimise_setupFiles(ceinmsModelPath=self.ceinms_calibrated_model,
                                          inputDataFile=self.ceinms_input_data,
                                          calibrationCfgPath=self.ceinms_optimise_cfg,
                                          excitationGeneratorFilePath=self.ceinms_excitation_generator,
                                          outputDirectory=self.ceinms_optimisation_dir,
                                          setupXMLPath=self.ceinms_optimise_setup,
                                          templateCfgXMLPath=os.path.join(self.setup_dir, self.ceinms_optimise_cfg))

    def create_ceinms_exe_setup(self):

        root = _u.ET.Element('ceinms')
        _u.ET.SubElement(root, 'subjectFile').text = os.path.relpath(self.ceinms_calibrated_model, self.path)
        _u.ET.SubElement(root, 'inputDataFile').text = os.path.relpath(self.ceinms_input_data, self.path)
        _u.ET.SubElement(root, 'executionFile').text = os.path.relpath(self.ceinms_exe_cfg, self.path)
        _u.ET.SubElement(root, 'excitationGeneratorFile').text = os.path.relpath(self.ceinms_excitation_generator, self.path)
        _u.ET.SubElement(root, 'outputDirectory').text = os.path.relpath(self.ceinms_exe_dir, self.path)
        # Create tree and write to file
        tree = _u.ET.ElementTree(root)
        _u.save_pretty_xml(tree, self.ceinms_exe_setup)
        print(f"Created {os.path.abspath(self.ceinms_exe_setup)}")

    def create_ceinms_exe_cfg(self):
        os.chdir(self.path)
        
        try:
            dofSet = ' '.join(_u.settings.BatchSettings.dof_list)
            _u.ceinms.create_ceinms_cfg(ceinmsModelPath=self.ceinms_calibrated_model,
                                 alpha=self.alpha,
                                 beta=self.beta,
                                    gamma=self.gamma,
                                    dofSet=dofSet,
                                    excitationGeneratorFilePath=self.ceinms_excitation_generator,
                                    outputPath=self.ceinms_exe_cfg)
            self._log(f'[Success] CEINMS exe cfg created: {os.path.abspath(self.ceinms_exe_cfg)}')
        except Exception as e:
            self._log(f'[Error] Failed to create CEINMS executable configuration: {e}', terminal=True)

    def get_muscle_excitation_mapping(self, muscle_name):
        """
        Check if a muscle is present in the excitation mapping of the excitation generator XML.
        
        Args:
            muscle_name (str): Name of the muscle to check.
        """
        tree = _u.ET.parse(self.ceinms_excitation_generator)
        root = tree.getroot()
        
        mapping = root.find('mapping')
        if mapping is not None:
            for excitation in mapping.findall('excitation'):
                if excitation.get('id') == muscle_name:
                    inputs = excitation.findall('input')
                    if inputs:
                        return [inp.text for inp in inputs]
        return []

    # --- run ceinms analyses
    def run_ceinms_calibration(self):
        """
        Run the full CEINMS calibration pipeline for this session.

        Steps (each is idempotent — skipped if output exists and replace=False):
          1. create_ceinms_model        — build uncalibrated XML from .osim
          2. create_excitation_generator — EMG→muscle mapping XML
          3. create_ceinms_input_data   — motion/force data for this trial
          4. create_ceinms_calibration_cfg — collects all sibling trial inputs
          5. create_ceinms_calibration_setup
          6. run calibration executable
        """
        os.chdir(self.path)

        # -- Prerequisites --
        self._log("CEINMS calibration: building prerequisites...")
        self.create_ceinms_model()
        if not os.path.exists(self.ceinms_uncalibrated_model):
            self._log("[Error] CEINMS calibration aborted: uncalibrated model could not be created.", terminal=True)
            return
        self.create_excitation_generator()
        self.create_ceinms_input_data()

        # Collect all sibling trial directories that have input data
        allowed = getattr(_u.settings.CEINMSSettings, 'calibration_trial_names', None)
        calib_trials = []
        input_data_name = _u.settings.Inputs().ceinms_input_data
        for entry in sorted(os.listdir(self.parentdir)):
            if allowed and entry not in allowed:
                continue
            candidate = os.path.join(self.parentdir, entry, input_data_name)
            if os.path.exists(candidate):
                calib_trials.append(entry)
        if not calib_trials:
            self._log("[Warning] No CEINMS input data found — calibrating with current trial only.")
            calib_trials = [self.trial]

        self._log(f"CEINMS calibration trials: {calib_trials}")
        self.create_ceinms_calibration_cfg(calibration_trial_names=calib_trials)
        self.create_ceinms_calibration_setup()

        # -- Run calibration --
        start_time = _u.time.time()
        os.chdir(self.path)

        if os.path.exists(self.ceinms_uncalibrated_model):
            _u.ceinms.plot_ceinms_model_parameters(self.ceinms_uncalibrated_model)

        calibrationSetupPath = os.path.abspath(self.ceinms_calibration_setup)

        _u.edit_xml_tag_value(calibrationSetupPath, 'outputDirectory', 'calibrationOutput')
        _u.ceinms.calibrate(setupXML_path=calibrationSetupPath)

        # update calibrated model from setupXML
        setupXML = _u.ET.parse(calibrationSetupPath).getroot()
        self.ceinms_calibrated_model = os.path.join(os.path.dirname(calibrationSetupPath), setupXML.find('outputSubjectFile').text)
        self._to_xml()

        # if date modified of calibrated model is after start time, assume success
        os.chdir(self.path)
        if not os.path.exists(self.ceinms_calibrated_model):
            self._log(f'[ERROR] CEINMS calibration failed: calibrated model not found at {self.ceinms_calibrated_model}. Check calibrationOutput/out.txt for details.', terminal=True)
            raise FileNotFoundError(f'Calibrated model not produced: {self.ceinms_calibrated_model}')
        mod_time = os.path.getmtime(self.ceinms_calibrated_model)
        if mod_time >= start_time:
            self._log(f'CEINMS calibration completed successfully in {mod_time - start_time:.2f} seconds.')
            _u.ceinms.plot_ceinms_model_parameters(self.ceinms_calibrated_model)
            
            # plot moments vs ceinms results
            try:
                ceinmsTorquesFile = os.path.join(self.ceinms_calibration_dir, 'Moments_inputData.csv')
                _u.ceinms.plot_moments_calibration_results(momentResultsCSV=ceinmsTorquesFile)
                self._log(f'[Success] Plotted moments vs CEINMS results.')
            except:
                self._log(f'[ERROR] Could not plot moments vs CEINMS results.')
            
            # plot emg vs ceinms excitations using uncalibrated model as reference
            try:
                _u.ceinms.plot_compare_ceinms_models(uncalibratedModelPath=self.ceinms_uncalibrated_model,calibratedModelPath=self.ceinms_calibrated_model)
                self._log(f'[Success] Plotted EMG vs CEINMS results for calibrated model: {self.ceinms_calibrated_model}')
            except:
                self._log(f'[ERROR] Could not plot EMG vs CEINMS results for calibrated model: {self.ceinms_calibrated_model}')
        else:
            self._log(f'[WARNING] CEINMS calibration may have failed: calibrated model not updated.')
            
    def run_ceinms_exe(self):
        os.chdir(self.path)
        self.load_settings(settingsXML=self.settingsXML)

        # Ensure per-trial prerequisites exist
        self.create_ceinms_input_data()
        if not os.path.exists(self.ceinms_exe_cfg) or self.replace:
            self.create_ceinms_exe_cfg()
        if not os.path.exists(self.ceinms_exe_setup):
            self.create_ceinms_exe_setup()

        if not os.path.exists(self.ceinms_exe_cfg):
            self._log(f"[Error] CEINMS execution aborted: {self.ceinms_exe_cfg} not found "
                      f"(run calibration first to produce a calibrated model).", terminal=True)
            return
        if not os.path.exists(self.ceinms_exe_setup):
            self._log(f"[Error] CEINMS execution aborted: {self.ceinms_exe_setup} not found.", terminal=True)
            return

        cfg = _u.ET.parse(self.ceinms_exe_cfg).getroot()
        setup = _u.ET.parse(self.ceinms_exe_setup).getroot()

        setup.find('outputDirectory').text = f'{self.ceinms_exe_dir}_a{self.alpha}_b{self.beta}_g{self.gamma}'

        _u.save_pretty_xml(_u.ET.ElementTree(setup), self.ceinms_exe_setup)

        # replace alpha, beta, gamma in cfg from settings file
        _u.ceinms.replace_ceinms_cfg_parameter(cfgXML_path=self.ceinms_exe_cfg,parameter_name='alpha',new_value=str(self.alpha))
        _u.ceinms.replace_ceinms_cfg_parameter(cfgXML_path=self.ceinms_exe_cfg,parameter_name='beta',new_value=str(self.beta))
        _u.ceinms.replace_ceinms_cfg_parameter(cfgXML_path=self.ceinms_exe_cfg,parameter_name='gamma',new_value=str(self.gamma))

        # run ceinms executable
        try:
            _u.ceinms.executable(setupXML_path=os.path.abspath(self.ceinms_exe_setup))
            self._log(f'CEINMS executable run completed for trial: {self.trial}')
        except Exception as e:
            self._log(f'[Error] during CEINMS executable run: {e}')

        # update jra ceinms forces path from setup output directory
        self.update_trial_attribute('jra_forces_ceinms', os.path.join(setup.find('outputDirectory').text, 'MuscleForces.sto'))

        # check if ceinms forces file exists before trying to add so columns
        if not os.path.exists(self.jra_forces_ceinms):
            self._log(f'[Error] CEINMS forces file not found: {self.jra_forces_ceinms}')
            return

        # add so columns to ceinms forces
        try:
            self.add_so_columns_to_ceinms_results()
            self._log(f'Added SO columns to CEINMS forces for trial: {self.trial}')
        except Exception as e:
            self._log(f'[Error] during adding SO columns to CEINMS forces: {e}')

    def run_ceinms_optimise(self):
        
        os.chdir(self.path)
        setupAbsPath = os.path.abspath(self.ceinms_optimise_setup)
        _u.ceinms.optimise(setupXML_path=setupAbsPath)

        try:    
            adjustedEMG_path = os.path.join(self.ceinms_optimisation_dir, 'AdjustedEmgs.sto')
            torqueCEINMS_path = os.path.join(self.ceinms_optimisation_dir, 'Torques.sto')
            _u.ceinms.plot_experimental_vs_ceinms(emgFile=self.emg_normalised,
                                               ceinmsExcitationsFile=adjustedEMG_path,
                                               excitationGeneratorFile=self.ceinms_excitation_generator,
                                                externalMomentsFile=self.id,
                                                ceinmsTorquesFile=torqueCEINMS_path)
            self._log(f'Plotted Experimental vs CEINMS results {self.path}')
        except:
            self._log(f'Could not plot EMG vs CEINMS results {self.path}')
    
    def run_ceinms_exe_loop(self):        
        
        os.chdir(self.path)
        if not os.path.exists(self.ceinms_exe_setup):
            self.create_ceinms_exe_setup()
        
        if not os.path.exists(self.ceinms_exe_cfg):
            _u.ceinms.create_ceinms_cfg(ceinmsModelPath=self.ceinms_calibrated_model, alpha=self.alpha, beta=self.beta, gamma=self.gamma, dofSet=' '.join(self.DofSet),excitationGeneratorFilePath=self.ceinms_excitation_generator, outputPath=self.ceinms_exe_cfg)
        
        try:
            self.load_settings(settingsXML=self.settingsXML)
            alpha_values = [int(x) for x in self.alphas.split(' ')]
            beta_values = [int(x) for x in self.betas.split(' ')]
            gamma_values = [int(x) for x in self.gammas.split(' ')]

            # change output directory in setup to match base name
            setup = _u.ET.parse(self.ceinms_exe_setup).getroot()
            setup.find('outputDirectory').text = self.ceinms_exe_dir
            
            # run ceinms executable loop
            _u.ceinms.executable_loop(setupXML_path=os.path.abspath(self.ceinms_exe_setup), cfgXML_path=os.path.abspath(self.ceinms_exe_cfg), alphas =alpha_values, betas=beta_values, gammas=gamma_values)

        except Exception as e:
                self._log(f'[Error] during CEINMS executable loop: {e}')

    def check_best_ceinms_results(self):
        ''' loop through ceinms exe results and find best alpha, beta, gamma based on RMS error for joint moments and EMG vs CEINMS excitations '''
        os.chdir(self.path)

        self.load_settings(settingsXML=self.settingsXML)
        best_params_csv = os.path.join(self.path, 'best_ceinms_parameters.csv')

        if os.path.exists(best_params_csv) and not self.replace:
            self._log(f'Loading existing best CEINMS parameters from {best_params_csv}')
            best_params_df = pd.read_csv(best_params_csv)
        else:
            best_params_df = pd.DataFrame(columns=['alpha', 'beta', 'gamma', 'moment_rms_error', 'emg_rms_error'])
            best_params_df.to_csv(best_params_csv, index=False)
            self._log(f'Saved best CEINMS parameters to {best_params_csv}')

    def add_so_columns_to_ceinms_results(self):

        try:
            so_forces = _u.load_any_data_file(self.jra_forces)
            ceinms_forces = _u.load_any_data_file(self.jra_forces_ceinms)
        except Exception as e:
            self._log(f'[Error] loading SO or CEINMS forces for adding columns: {e}')
            return

        # Find columns in SO forces that are not in CEINMS forces
        missing_columns = [col for col in so_forces.columns if col not in ceinms_forces.columns]

        # Create new dataframe starting with CEINMS forces
        updated_forces = ceinms_forces.copy()

        # Add missing columns from SO forces
        for col in missing_columns:
            updated_forces[col] = so_forces[col]

        # Save to new .sto file
        _u.write_sto_file(updated_forces, self.jra_forces_ceinms)
        self._log(f'[Success] Added SO columns to CEINMS forces for trial: {self.trial}')
        print(f"Updated forces saved to: {self.jra_forces_ceinms}")
        print(f"Added {len(missing_columns)} columns from SO forces")

    #--- Plot ceinms
    def plot_ceinms_calibration_results(self):

        try:
            ceinmsTorquesFile = os.path.join(self.ceinms_calibration_dir, 'Moments_inputData.csv')
            _u.ceinms.plot_mom