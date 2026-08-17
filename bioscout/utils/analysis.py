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
# Canonical trial file/folder layout — inline (bioscout 2.0). There is no
# separate Inputs class anymore: Analyse owns the layout directly via
# _default_layout_paths() below, and each trial gets these paths applied in
# _apply_inputs_layout(). A project may still OVERRIDE the layout by defining an
# ``Inputs`` class in its settings.py (back-compat) — see Analyse._layout_paths.
# ===========================================================================
# Stage subfolders (inputs separated from each stage's outputs).
LAYOUT_DIRS = {
    "inputs": "inputs",
    "extbio": "external_biomechanics",   # IK + ID
    "muscle_analysis": "muscle_analysis",
    "static_optimisation": "static_optimisation",
    "ceinms": "ceinms",
    "joint_contact_forces": "joint_contact_forces",  # JRA
}


def _default_layout_paths():
    """Canonical ``{field: relative_path}`` for a trial (inline replacement for
    the old settings.Inputs class). ``field`` is the terse attribute name kept
    for back-compat (ik, id, so_forces, ...); Analyse exposes readable aliases
    (joint_angles, inverse_dynamics, ...) on top of these."""
    j = os.path.join
    I = LAYOUT_DIRS["inputs"]; E = LAYOUT_DIRS["extbio"]
    M = LAYOUT_DIRS["muscle_analysis"]; S = LAYOUT_DIRS["static_optimisation"]
    C = LAYOUT_DIRS["ceinms"]; JCF = LAYOUT_DIRS["joint_contact_forces"]
    C_CAL = j("..", "ceinms_calibration")   # session-level CEINMS calibration
    d = {
        # non-path defaults (kept for parity with the old Inputs.__init__)
        "setup_dir": "", "model_dir": "", "start_time": "0.0000", "end_time": "1.0000",
        "alpha": "10", "beta": "1", "gamma": "1000",
        # raw experimental inputs
        "c3d": j(I, "c3dfile.c3d"), "markers": j(I, "marker_experimental.trc"),
        "markerset": j(I, "markers_FAIS.xml"), "grf_mot": j(I, "grf.mot"),
        "setup_grf": j(I, "GRF.xml"), "emg": j(I, "emg.mot"), "analog": j(I, "analog.csv"),
        # external biomechanics: IK + ID
        "setup_ik": j(E, "setup_IK.xml"), "ik": j(E, "joint_angles.mot"),
        "model_markers": j(E, "_ik_model_marker_locations.sto"),
        "setup_id": j(E, "setup_ID.xml"), "id": j(E, "inverse_dynamics.sto"),
        # muscle analysis
        "setup_ma": j(M, "setup_MA.xml"), "ma": M,
        # static optimisation
        "actuators_so": j(S, "actuators_so.xml"), "setup_so": j(S, "setup_SO.xml"),
        "so_forces": j(S, "SO_StaticOptimization_force.sto"),
        "so_activations": j(S, "SO_StaticOptimization_activation.sto"),
        # JRA / joint contact forces
        "setup_jra": j(JCF, "setup_JRA_SO.xml"),
        "jra": j(JCF, "Analyse_JRA_ReactionLoads_SO.sto"),
        # CEINMS (trial level)
        "emg_filtered_normalised": j(I, "emg_filtered_normalised.mot"),
        "ceinms_input_data": j(C, "inputData.xml"), "ceinms_exe_cfg": j(C, "ceinms_cfg.xml"),
        "ceinms_exe_setup": j(C, "ceinms_setup.xml"),
        "ceinms_optimise_setup": j(C, "ceinms_setup_optimise.xml"),
        "ceinms_optimise_cfg": j(C, "ceinms_cfg_optimise.xml"),
        "ceinms_exe_dir": j(C, "Execution"), "ceinms_optimisation_dir": j(C, "Optimised"),
        "setup_jra_ceinms": j(JCF, "setup_JRA_CEINMS.xml"),
        "jra_ceinms": j(JCF, "Analyse_JRA_ReactionLoads_CEINMS.sto"),
        # CEINMS calibration (session level)
        "ceinms_uncalibrated_model": j(C_CAL, "subjectUncalibrated.xml"),
        "ceinms_calibrated_model": j(C_CAL, "subjectCalibrated.xml"),
        "ceinms_calibration_cfg": j(C_CAL, "calibrationCfg.xml"),
        "ceinms_calibration_setup": j(C_CAL, "calibrationSetup.xml"),
        "ceinms_excitation_generator": j(C_CAL, "excitationGenerator.xml"),
        "ceinms_calibration_dir": j(C_CAL, "output"),
    }
    d["jra_forces"] = d["so_forces"]
    d["ceinms_excitations"] = d["emg_filtered_normalised"]
    return d


# ===========================================================================
# Subject
# ===========================================================================

# ---------------------------------------------------------------------------
# Empty-export detection
# ---------------------------------------------------------------------------
# A C3D with no 3D point data (e.g. an MVIC/strength capture recorded for EMG
# only) still produces a marker_experimental.trc — just a header with no rows.
# The same goes for grf.mot when no force plate was recorded. Those husk files
# are worse than nothing: they make every "does this trial have inputs?" check
# answer yes, so IK/ID start and then fail deep inside OpenSim. Detect them so
# export can drop them and the solve steps can skip cleanly.
_EXPORT_ARTIFACTS = ("marker_experimental.trc", "grf.mot", "GRF.xml", "grf_events.png")


def _numeric_rows(path, need=1):
    """True when a .trc/.mot/.sto holds at least ``need`` numeric data rows.

    Deliberately forgiving: any read problem returns True so this can only ever
    skip a file we are confident is empty, never one we failed to parse.
    """
    try:
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            return False
        seen = 0
        with open(path, 'r', errors='ignore') as fh:
            for line in fh:
                tok = line.split()
                # A data row is ALL numeric. This rejects TRC/MOT header lines
                # that merely START with a number, e.g. the TRC rate line
                # "200.00  200.00  1000  40  mm  200.00  1  1000" (the "mm"
                # disqualifies it) and "nRows=1000".
                if len(tok) < 3:
                    continue
                try:
                    for x in tok:
                        float(x)
                except ValueError:
                    continue
                seen += 1
                if seen >= need:
                    return True
        return False
    except Exception:
        return True


def _grf_xml_has_forces(path):
    """True when a GRF.xml declares at least one ExternalForce."""
    try:
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            return False
        return next(_u.ET.parse(path).getroot().iter('ExternalForce'), None) is not None
    except Exception:
        return True


def has_markers(trial) -> bool:
    """True when this trial has a marker TRC with real data (IK is possible)."""
    return _numeric_rows(getattr(trial, 'markers', '') or '')


def has_grf(trial) -> bool:
    """True when this trial has usable ground reaction forces (ID is possible)."""
    return _numeric_rows(getattr(trial, 'grf_mot', '') or '')


def _is_ceinms(force_type) -> bool:
    return str(force_type).upper().startswith("CEIN")


@dataclass
class Subject:
    """One SUBJECT-SESSION config: the identity (``subject``/``name``) plus the
    models/paths used for ONE session. Because scaled models are session-specific,
    each registry row is a single (subject, session) — a subject analysed across
    several sessions has one row per session (same ``subject``, different
    ``session``/models). ``subject`` is an alias for ``name`` (settings may alias
    the class itself to ``Session`` for readability)."""
    name: Optional[str] = None                 # subject id = folder under simulations/<name>/ & models/<name>/
    subject: Optional[str] = None              # alias for name (session-config ergonomics)
    label: Optional[str] = None                # display name on plots (defaults to name)
    session: Optional[str] = None              # the session this row configures, e.g. "25_03_31"
    static_trial: Optional[str] = None         # static/MVC trial folder for this session (scaling)
    generic_model: Optional[str] = None        # unscaled template .osim this session scales FROM
    model_so: Optional[str] = None             # .osim used for static optimisation (scaling OUTPUT)
    model_ceinms: Optional[str] = None         # .osim used for CEINMS (defaults to model_so)
    setup_folder: Optional[str] = None         # subfolder of setupFiles/ with the OpenSim setup XMLs
    color: str = "black"                       # plot colour
    line_style_so: str = "-"                   # plot line style for SO curves
    line_style_ceinms: str = "--"              # plot line style for CEINMS curves
    group: Optional[str] = None                # optional grouping tag (e.g. "generic" / "MRI")
    body_mass: Optional[float] = None          # optional, kg
    # Scaling stage toggles (map to OpenSim ScaleTool ModelScaler / MarkerPlacer).
    # MRI/TPS iterations use linear_scaling=False (geometry already personalised);
    # marker_placer can still be True to align markers to the static trial.
    linear_scaling: bool = True                # ModelScaler (dimensional scaling)
    marker_placer: bool = False                # MarkerPlacer (place markers to static)
    prescaled_model: Optional[str] = None      # provided .osim to use INSTEAD of geometric scaling
    meta: dict = field(default_factory=dict)   # free-form extras

    def __post_init__(self):
        # subject <-> name are aliases; accept either.
        if self.name is None:
            self.name = self.subject
        if self.subject is None:
            self.subject = self.name
        if not self.name:
            raise ValueError("Subject/Session needs name= (or subject=)")
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

    def generic_model_path(self) -> Optional[str]:
        """Absolute path to this subject's unscaled generic/template .osim.

        ``generic_model`` may be an absolute path or a relative name/sub-path.
        A relative value is resolved against, in order: ``models/<name>/``,
        ``models/``, ``<project>/generic models/``, then the project root — so
        templates kept in a ``generic models/`` folder resolve without an
        absolute path. Returns None if the subject has no generic model set.
        """
        gm = self.generic_model
        if not gm:
            return None
        if os.path.isabs(gm):
            return gm
        from bioscout import utils
        md = str(utils.MODELS_DIR)
        pd = str(getattr(utils, "PROJECT_DIR", os.path.dirname(md)))
        cands = [os.path.join(md, self.name, gm),
                 os.path.join(md, gm),
                 os.path.join(pd, "generic models", gm),
                 os.path.join(pd, gm)]
        for c in cands:
            if os.path.exists(c):
                return c
        return cands[0]

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
        from bioscout.utils.session import Iteration as _S, find_session_dir as _fsd
        _it = self._iteration()
        out = []
        for _n in names:
            try:
                out.append(_S(_fsd(_n), _it))
            except Exception as _e:
                print(f'[Subject] {self.name}: session {_n} -> {_e}')
        return out

    def get_session(self, name):
        """Session by name."""
        from bioscout.utils.session import Iteration as _S, find_session_dir as _fsd
        return _S(_fsd(name), self._iteration())

    def trials(self, session=None, force_type="SO"):
        """List of Trial objects for one session (default: self.session)."""
        return self.get_session(session or self.session).trials

    def _iteration(self):
        """On-disk model-iteration folder for this subject: settings.SUBJECT_GROUP
        (name -> iteration), else self.group / lowercased name."""
        from bioscout import utils as _u
        s = getattr(_u, "settings", None)
        sg = (getattr(s, "SUBJECT_GROUP", None)
              or getattr(getattr(s, "BatchSettings", None), "SUBJECT_GROUP", None) or {})
        return sg.get(self.name) or getattr(self, "group", None) or str(self.name).lower()

    def make_trial(self, trial_path, force_type="SO", configure=True):
        """Return a Trial (an Analyse) for an absolute trial path, with this
        subject's model + setup folder wired in for the chosen solver."""
        Trial = _trial_class()
        t = Trial(trial_path)
        if configure:
            try:
                _, _sess = subject_session_for_trial(trial_path)
                t.subject = self.name
                t.session = _sess or self.session
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
    ``all_subjects``) into a set of subject names. ``None``/empty -> empty set.

    A bare string is treated as a SINGLE name (``"Athlete_03_GPK"``), never
    iterated character-by-character. The literal ``"all"`` is handled by
    ``select_subjects`` before this is called."""
    if selection is None:
        return set()
    if isinstance(selection, str):
        selection = [selection]        # a lone name, not a char sequence
    names = []
    for x in selection:
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

    Selection semantics for ``run``:
      * ``"all"`` (case-insensitive) -> every subject (explicit, recommended).
      * ``None`` / ``[]``            -> also every subject (back-compat default).
      * a name or list of names/indices -> just those.
    ``skip`` removes; skip wins over run.
    """
    if isinstance(run, str) and run.strip().lower() == "all":
        run = None                     # explicit "all" -> keep everyone
    keep = resolve_subject_selection(run, all_subjects)
    drop = resolve_subject_selection(skip, all_subjects)
    out = list(all_subjects)
    if keep:
        out = [s for s in out if s.name in keep]
    if drop:
        out = [s for s in out if s.name not in drop]
    return out


def discover_sessions(simulations_dir, groups, subject_group=None,
                      default_group=None, overrides=None,
                      subjects=None, sessions=None, session_is_dir=True):
    """Build ``Subject`` rows for many (subject, session) pairs from GROUP
    templates — avoids hand-listing every row.

    Subjects come from ``subject_group`` keys if given (deterministic, works
    BEFORE any simulations/ folders exist — e.g. before c3d ingest); otherwise
    the ``simulations/`` folder is scanned. Sessions come from the explicit
    ``sessions`` list if given (product with each subject); otherwise each
    subject's on-disk session folders are scanned.

    Args:
      groups: ``{group_name: {field: value}}`` templates, e.g.
        ``{"ctrl": dict(generic_model="X.osim", model_so="scaled_opt_N10_mvicx3.00.osim",
                        model_ceinms="scaled_opt_N10.osim", static_trial="Static_01",
                        setup_folder=SETUP_DIR, color="green")}``.
      subject_group: ``{subject_name: group_name}`` (else ``default_group``).
      default_group: group used for subjects not in ``subject_group`` (None=skip).
      overrides: ``{(subject, session): {field: value}}`` per-row tweaks.
      subjects / sessions: explicit allow-lists (also used as the source when set).
      session_is_dir: when scanning, only treat sub-folders as sessions.

    Returns ``list[Subject]`` (one per (subject, session), template-matched)."""
    subject_group = subject_group or {}
    overrides = overrides or {}
    sim = str(simulations_dir)
    rows = []

    # --- resolve the SUBJECT list: explicit map/list first, else scan disk ---
    if subject_group:
        subj_names = sorted(subject_group.keys())
    elif subjects:
        subj_names = sorted(subjects)
    elif os.path.isdir(sim):
        subj_names = sorted(d for d in os.listdir(sim)
                            if os.path.isdir(os.path.join(sim, d)))
    else:
        subj_names = []
    if subjects:                                   # further restrict
        subj_names = [s for s in subj_names if s in set(subjects)]

    for subj in subj_names:
        grp = subject_group.get(subj, default_group)
        tmpl = groups.get(grp)
        if tmpl is None:
            continue                               # no template -> skip subject
        # --- resolve this subject's SESSIONS: explicit list, else scan disk ---
        if sessions:
            sess_names = list(sessions)
        else:
            sroot = os.path.join(sim, subj)
            sess_names = (sorted(d for d in os.listdir(sroot)
                                 if (not session_is_dir)
                                 or os.path.isdir(os.path.join(sroot, d)))
                          if os.path.isdir(sroot) else [])
        for sess in sess_names:
            fields = dict(tmpl)
            fields.update(overrides.get((subj, sess), {}))
            fields.setdefault("group", grp)
            rows.append(Subject(subject=subj, session=sess, **fields))
    return rows


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


def load_project_subjects(settings=None, force=False):
    """Build ``Subject`` objects + derived config on ``BatchSettings`` from RAW
    subject DATA declared in a project's settings.py.

    This lets settings.py be a **pure-data** file (no ``import bioscout``, no
    ``Subject(...)`` calls, no import cycle). Declare subjects as plain dicts::

        class BatchSettings:
            subjects = [dict(name="Athlete_03_Cateli", label="...", session="25_03_31",
                             model_so="...", model_ceinms="...", color="green", group="generic"),
                        ...]
            run_subjects  = None      # None/[] = all
            skip_subjects = []

    bioscout calls this on project load: it converts each dict to a ``Subject``,
    applies run/skip selection, builds ``model_config`` etc., and writes
    ``SUBJECTS`` / ``SUBJECTS_BY_NAME`` / ``model_config`` / ``MODEL_FILES`` /
    ``SETUP_FOLDERS`` / ``sessions`` back onto ``BatchSettings`` — so every
    existing consumer of ``settings.BatchSettings.SUBJECTS`` keeps working.

    Legacy settings that still declare ``ALL_SUBJECTS = [Subject(...)]`` (or set
    ``SUBJECTS`` themselves) keep working: those objects are used as-is. Idempotent."""

    import bioscout.utils as _u
    BS = _u.settings.BatchSettings
    
    # if settings is None:
    #     from bioscout import utils as _u
    #     settings = getattr(_u, "settings", None)
    #  = getattr(settings, "BatchSettings", None)
    # if BS is None:
    #     return None
    # if getattr(BS, "_subjects_loaded", False) and not force:
    #     return getattr(BS, "SUBJECTS", [])

    # 1. gather the raw subject list: prefer new `subjects` (dicts), else legacy
    #    `ALL_SUBJECTS` (already Subject objects).
    raw = getattr(BS, "subjects", None)
    if raw is None:
        raw = getattr(BS, "ALL_SUBJECTS", None)
    if not raw:
        return getattr(BS, "SUBJECTS", [])

    valid_fields = set(Subject.__dataclass_fields__)
    subs = []
    for item in raw:
        if isinstance(item, Subject):
            subs.append(item); continue
        d = dict(item)
        unknown = set(d) - valid_fields
        if unknown:
            raise ValueError(
                f"[settings] subject {d.get('name', '?')!r}: unknown field(s) "
                f"{sorted(unknown)}. Valid fields: {sorted(valid_fields)}")
        subs.append(Subject(**d))

    # 2. run/skip selection (accept both new lower_case and legacy UPPER_CASE)
    run  = getattr(BS, "run_subjects",  getattr(BS, "RUN_SUBJECTS", None))
    skip = getattr(BS, "skip_subjects", getattr(BS, "SKIP_SUBJECTS", None)) or []
    sim_dir = getattr(BS, "SIMULATIONS_DIR", None)

    # 3. derive + write back onto BatchSettings (what settings.py used to compute)
    BS.ALL_SUBJECTS     = subs
    BS.SUBJECTS         = select_subjects(subs, run, skip)
    BS.SUBJECTS_BY_NAME = {s.name: s for s in BS.SUBJECTS}
    BS.model_config     = build_model_config(BS.SUBJECTS, force_types=("SO", "CEINMS"))
    BS.MODEL_FILES      = {s.name: s.model_ceinms for s in BS.SUBJECTS}
    BS.SETUP_FOLDERS    = {s.name: s.setup_folder for s in BS.SUBJECTS}
    try:
        BS.sessions     = sessions_from_subjects(BS.SUBJECTS, sim_dir)
    except Exception as e:
        print(f"[settings] could not build sessions map: {e}")
    BS._subjects_loaded = True
    return BS.SUBJECTS


# ===========================================================================
# Hierarchy: Subject -> Session -> Trial (a Trial IS an Analyse)
# ===========================================================================

def _sim_dir():
    from bioscout import utils
    return str(getattr(utils, "SIMULATIONS_DIR", ""))


_TRIAL_CLS = None


def _trial_class():
    """Return the Trial class — which is now just ``Analyse`` itself.

    ``Analyse`` absorbed the old ``run_*(replace=...)`` convenience, so a trial IS
    an Analyse. This factory is kept only so existing Session/Subject call sites
    (``Trial = _trial_class(); Trial(path)``) keep working unchanged."""
    return Analyse


# NOTE: the Session class now lives in bioscout.utils.session

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

        # Auto-start a run log (once per process) in <project>/logs/ so every
        # bioscout run is logged without the caller doing anything.
        try:
            _u.start_logging  # ensure utils.shared is loaded
            _u.shared.ensure_logging(name=f"Project {os.path.basename(str(self.dir))}",
                                     log_dir=os.path.join(str(self.dir), "logs"))
        except Exception:
            pass

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
            # Build Subject objects + derived config from raw settings data, so a
            # project's settings.py can be pure data (no bioscout import / no cycle).
            try:
                load_project_subjects(mod, force=True)
            except Exception as e:
                print(f"[bioscout] subject loading failed: {e}")
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
    if name in ("Session", "Iteration", "open_session"):
        # Session (session-level) + Iteration (runnable) live in
        # bioscout.utils.session. Re-export lazily so legacy
        # `from bioscout.utils.analysis import Session` keeps working, without a
        # module-load import cycle (session imports Analyse).
        from bioscout.utils import session as _s
        return getattr(_s, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Subject", "Session", "Project",
    "Analyse", "Plot",
    "build_model_config", "discover_subjects", "init_project",
    "sessions_from_subjects", "subjects_from_subjects",
    "check_settings_version", "migrate_settings", "ensure_editor_paths",
]

# Proximal -> distal subplot ordering for the ID / IK figures (trunk & pelvis,
# down the leg, then the arm chain). Coordinate stems (no _moment/_force suffix).
_ID_PROX_DISTAL = [
    'pelvis_tilt', 'pelvis_list', 'pelvis_rotation', 'pelvis_tx', 'pelvis_ty', 'pelvis_tz',
    'lumbar_extension', 'lumbar_bending', 'lumbar_rotation',
    'hip_flexion', 'hip_adduction', 'hip_rotation', 'knee_angle', 'knee_angle_beta',
    'ankle_angle', 'subtalar_angle', 'mtp_angle',
    'arm_flex', 'arm_add', 'arm_rot', 'elbow_flex', 'pro_sup', 'wrist_flex', 'wrist_dev',
]


# ---------------------------------------------------------------------------
# Trial-type-aware gait/task event handling.
#
# A trial's *type* is metadata (stored as <trial_type> in trial_settings.xml or
# inferred from the trial name); the event *timestamps* live in the <events>
# subtree of trial_settings.xml as `name, time` entries. EVENT_SCHEMAS says, per
# type, how to interpret those
# labels: which canonical landmarks exist, the label synonyms that map onto each,
# which two landmarks bound the 0-100% normalisation window, which landmarks are
# drawn as vertical marks, the axis label, and whether literature contact-force
# curves (which are gait-based) may be overlaid for this type.
# ---------------------------------------------------------------------------
_TRIAL_TYPE_ALIASES = {
    'walk': 'walking', 'walking': 'walking', 'gait': 'walking',
    'run': 'running', 'running': 'running', 'sprint': 'running', 'jog': 'running',
    'squat': 'squat', 'squatting': 'squat',
    'jump': 'jump', 'jumping': 'jump', 'cmj': 'jump', 'sj': 'jump', 'hop': 'jump',
    'generic': 'generic', 'static': 'generic', 'trial': 'generic',
}

EVENT_SCHEMAS = {
    'generic': {
        'landmarks': ['start', 'end'],
        'synonyms': {'start': ['start', 'begin'], 'end': ['end', 'stop', 'finish']},
        'cycle': ('start', 'end'), 'marks': [], 'axis': '% trial', 'gait_like': False,
    },
    'walking': {
        'landmarks': ['foot_contact', 'foot_off'],
        'synonyms': {
            'foot_contact': ['foot_contact', 'contact', 'heel', 'strike', 'fc', 'ic', 'hs'],
            'foot_off': ['foot_off', 'toe_off', 'toe', 'off', 'to'],
        },
        'cycle': ('foot_contact', 'foot_contact'), 'marks': ['foot_off'],
        'axis': '% gait cycle', 'gait_like': True,
    },
    'running': {
        'landmarks': ['foot_contact', 'foot_off'],
        'synonyms': {
            'foot_contact': ['foot_contact', 'contact', 'strike', 'fc', 'ic'],
            'foot_off': ['foot_off', 'toe_off', 'toe', 'off', 'to'],
        },
        'cycle': ('foot_contact', 'foot_contact'), 'marks': ['foot_off'],
        'axis': '% stride', 'gait_like': True,
    },
    'squat': {
        'landmarks': ['initial_descent', 'bottom', 'initial_ascent', 'stand'],
        'synonyms': {
            'initial_descent': ['initial_descent', 'descent', 'descend', 'start', 'top_start'],
            'bottom': ['bottom', 'hold', 'deep', 'bottom_hold'],
            'initial_ascent': ['initial_ascent', 'ascent', 'ascend', 'rise'],
            'stand': ['stand', 'end', 'top_end', 'lockout'],
        },
        'cycle': ('initial_descent', 'stand'), 'marks': ['bottom', 'initial_ascent'],
        'axis': '% squat', 'gait_like': False,
    },
    'jump': {
        'landmarks': ['start', 'take_off', 'landing', 'end'],
        'synonyms': {
            'start': ['start', 'begin'],
            'take_off': ['take_off', 'takeoff', 'to', 'push_off'],
            'landing': ['landing', 'land', 'contact', 'ic'],
            'end': ['end', 'stop', 'finish'],
        },
        'cycle': ('start', 'end'), 'marks': ['take_off', 'landing'],
        'axis': '% jump', 'gait_like': False,
    },
}


def _canonical_trial_type(s):
    """Map a free-form type/name string to a canonical EVENT_SCHEMAS key."""
    s = (s or '').strip().lower()
    if not s:
        return 'generic'
    if s in _TRIAL_TYPE_ALIASES:
        return _TRIAL_TYPE_ALIASES[s]
    for key, canon in _TRIAL_TYPE_ALIASES.items():
        if key in s:
            return canon
    return 'generic'


# ===========================================================================
# Analyse - per-trial OpenSim/CEINMS pipeline (moved here from utils/analyse.py).
# ===========================================================================
def subject_session_for_trial(trial_path):
    """``(subject, session)`` for a trial folder, in either session layout.

    Trial folders sit at::

        <subject>/<session>/<iteration>/<trial>                  (flat)
        <subject>/<session>/3_iterations/<iteration>/<trial>     (numbered)

    Several call sites used to read these by fixed position (``parts[-3]``,
    ``parts[-2]``), which picked up ``<session>/<iteration>`` in the flat
    layout and ``3_iterations/<iteration>`` in the numbered one — wrong in
    both, and the reason empty ``models/25_03_31/`` and ``models/3_iterations/``
    folders appeared. Walk the structure instead.

    Returns ``(None, None)`` when the path is too shallow to interpret.
    """
    from bioscout.utils.session_layout import ITERATIONS_DIRS

    iteration_dir = os.path.dirname(os.path.normpath(trial_path))
    parent = os.path.dirname(iteration_dir)
    session_dir = (os.path.dirname(parent)
                   if os.path.basename(parent) in ITERATIONS_DIRS else parent)
    session = os.path.basename(session_dir)
    subject = os.path.basename(os.path.dirname(session_dir))
    return (subject or None), (session or None)


class Analyse:
    '''
    Contains paths from the user settings and functions to implement in the OpenSim/Ceinms analysis
    
    subject_name: Name of the subject (or the trial path if session_name and trial_name are None)

    Usage:
        - Create an instance of the Analyse class with the trial path:


    '''

    # ---- semantic aliases -------------------------------------------------
    # Readable names for the terse layout fields inherited from settings.Inputs,
    # so call sites can say ``trial.joint_angles`` instead of ``trial.ik``. Each
    # is a read/write proxy onto the underlying field; the short names remain the
    # canonical serialised keys (trial_settings.xml / _LAYOUT_FIELDS unchanged).
    @property
    def model_path(self): return self.model_dir
    @model_path.setter
    def model_path(self, v): self.model_dir = v

    @property
    def joint_angles(self): return self.ik
    @joint_angles.setter
    def joint_angles(self, v): self.ik = v

    @property
    def inverse_dynamics(self): return self.id
    @inverse_dynamics.setter
    def inverse_dynamics(self, v): self.id = v

    @property
    def static_optimisation_forces(self): return self.so_forces
    @static_optimisation_forces.setter
    def static_optimisation_forces(self, v): self.so_forces = v

    @property
    def static_optimisation_activations(self): return self.so_activations
    @static_optimisation_activations.setter
    def static_optimisation_activations(self, v): self.so_activations = v

    @property
    def grf(self): return self.grf_mot
    @grf.setter
    def grf(self, v): self.grf_mot = v

    @property
    def joint_reaction_so(self): return self.jra
    @joint_reaction_so.setter
    def joint_reaction_so(self, v): self.jra = v

    @property
    def joint_reaction_ceinms(self): return self.jra_ceinms
    @joint_reaction_ceinms.setter
    def joint_reaction_ceinms(self, v): self.jra_ceinms = v

    # ---- structural layout fields ----------------------------------------
    # File/dir layout fields — always taken from the CURRENT settings.Inputs,
    # never from a (possibly stale) trial_settings.xml (see _apply_inputs_layout).
    # Only non-structural *values* (setup_dir, model_dir, start/end_time, alpha,
    # beta, gamma, body_mass, time_range, ...) are allowed to persist per-trial.
    _LAYOUT_FIELDS = (
        'c3d', 'markers', 'markerset', 'grf_mot', 'setup_grf', 'emg', 'analog',
        'setup_ik', 'ik', 'model_markers', 'setup_id', 'id', 'setup_ma', 'ma',
        'actuators_so', 'setup_so', 'so_forces', 'so_activations', 'jra_forces',
        'setup_jra', 'jra', 'emg_filtered_normalised',
        'ceinms_input_data', 'ceinms_exe_cfg', 'ceinms_exe_setup', 'ceinms_optimise_setup',
        'ceinms_optimise_cfg', 'ceinms_exe_dir', 'ceinms_optimisation_dir',
        'setup_jra_ceinms', 'jra_ceinms',
        'ceinms_uncalibrated_model', 'ceinms_calibrated_model', 'ceinms_calibration_cfg',
        'ceinms_calibration_setup', 'ceinms_excitation_generator', 'ceinms_calibration_dir',
    )

    def _legacy_model_dir(self):
        """``MODELS_DIR/<subject>/<session>`` for the pre-YAML layout, or None.

        Older projects kept each subject's scaled models under
        ``models/<subject>/<session>/``; session-centric projects keep them in
        the iteration folder instead. This used to be derived by slicing fixed
        positions off the trial path::

            os.path.join(MODELS_DIR, *normpath(self.path).split(os.sep)[-3:-1])

        which silently produced whatever happened to sit two and three levels
        up. In the flat layout that was ``<session>/<iteration>`` (already the
        wrong pair — the convention is subject/session, so it created
        ``models/<session>/``); with the numbered layout the trial sits one
        level deeper and it became ``models/3_iterations/<iteration>/``.

        Now the session folder is located structurally, and the directory is
        only created when the project actually uses this convention — i.e.
        ``models/<subject>/`` already exists. A session-centric project gets
        None and nothing is created.
        """
        subject, session = subject_session_for_trial(self.path)
        if not session or not subject:
            return None
        subject_dir = os.path.join(str(_u.MODELS_DIR), subject)
        if not os.path.isdir(subject_dir):
            return None                 # not this project's convention
        return os.path.join(subject_dir, session)

    def __init__(self, trialPath=None):

        if trialPath is None:
            trialPath = input("Enter the path to the trial directory: ").strip('"')  # Remove quotes if the path is copied with them
        
        self.replace = getattr(_u.settings.BatchSettings, 'replace_existing', False)
        self.path = os.path.abspath(trialPath)
        self.trial = os.path.basename(self.path)  # set early so _log works before settings load
        self.settingsXML = 'trial_settings.xml'
        # Session-centric layout: when set (absolute path to experimental/<trial>/),
        # raw model-INDEPENDENT inputs are read from there instead of self.path/inputs,
        # so a single shared export feeds every model iteration. Re-applied on every
        # load_settings via _apply_inputs_layout(). None = classic per-trial inputs.
        self.experimental_dir = None

        # Auto-start a run log (once per process) so a bare Analyse(...) call — not
        # just Project / the CLI — also writes <project>/logs/bioscout_<ts>.log.
        try:
            _u.shared.ensure_logging(name=f"Analyse {self.trial}")
        except Exception:
            pass

        if not os.path.exists(trialPath):
            self._log(f"Trial path not found: {trialPath}")
            os.makedirs(trialPath)
            self._reset_settings_xml()
            model_dir = self._legacy_model_dir()
            if model_dir and not os.path.exists(model_dir):
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
        
    def _reset_settings_xml(self):
        '''Create a settings xml for the trial at the specified path'''
        os.chdir(self.path)
        # delete existing settings xml if it exists
        if os.path.exists(self.settingsXML):
            os.remove(self.settingsXML)
            self._log(f"Existing settings XML deleted: {self.settingsXML}")
        
        # Layout-aware: fixed positions gave <session>/<iteration> on the flat
        # layout and 3_iterations/<iteration> on the numbered one.
        _subj, _sess = subject_session_for_trial(self.path)
        self.subject = _subj
        self.session = _sess
        self.trial = os.path.basename(os.path.normpath(self.path))

        self.parentdir = os.path.dirname(self.path)

        self._update_model()
        
        self.body_mass = None # Placeholder, will be updated from the model if possible
        self.time_range = 'None' # Placeholder, will be updated from data if possible
        # trial type drives event interpretation + literature overlays; inferred
        # from the trial name here, editable in trial_settings.xml afterwards.
        self.trial_type = self.get_trial_type()
        
        # add each Input to the trial settings
        inputs = self._layout_paths()
        for varInput in inputs.items():
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
        _inputs_dir = LAYOUT_DIRS.get("inputs", "inputs")
        for _k, _v in (inputs.items() if getattr(self, "_scaffold_output_dirs", True) else ()):
            if _k.startswith("_") or not isinstance(_v, str):
                continue
            _d = os.path.dirname(_v)
            # Never auto-create an empty inputs/ folder: raw inputs either already
            # exist (classic layout) or live in the shared experimental/ folder
            # (session-centric layout). Export creates inputs/ itself when needed.
            if _d == _inputs_dir:
                continue
            if _d and not _d.startswith(".."):
                try:
                    os.makedirs(os.path.join(self.path, _d), exist_ok=True)
                except Exception:
                    pass

        # Update body mass and time range from data available (.trc, .c3d, <events> in XML)
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
        # trial_settings.xml is now an optional scratch cache — session.yaml is
        # the source of truth (Session injects config via _overrides). Skip the
        # write entirely when settings.BatchSettings.write_trial_settings_xml is
        # False, so trial folders stay clean of per-trial XML.
        try:
            _bs = getattr(getattr(_u, 'settings', None), 'BatchSettings', None)
            if getattr(_bs, 'write_trial_settings_xml', True) is False:
                return
        except Exception:
            pass
        os.chdir(self.path)
        # The analysis window is persisted ONLY as start_time / end_time (scalars),
        # kept in sync with the working self.time_range; the redundant time_range
        # tag is not serialized (avoids two disagreeing representations).
        try:
            if isinstance(self.time_range, (list, tuple)) and len(self.time_range) == 2:
                self.start_time = f"{float(self.time_range[0]):.4f}"
                self.end_time   = f"{float(self.time_range[1]):.4f}"
        except Exception:
            pass
        root = _u.ET.Element("TrialSettings")
        for attr, value in self.__dict__.items():
            if attr == 'time_range':
                continue   # persisted as start_time / end_time only
            if attr == 'events_list':
                continue   # events go into the <events> subtree below (self-contained)
            if attr == 'settingsXML':
                continue   # it IS this file — no need to store its own name
            if attr == 'trial_type':
                continue   # carried by the <events type=".."> attribute below
            if attr in ('model_name', 'ceinms_muscle_forces', 'ceinms_activations'):
                continue   # derived/unused: model_name = basename(model_dir);
                           # the CEINMS force/activation files live in the Execution
                           # dir derived from jra_forces_ceinms — not read from here
            if attr in ('parentdir', '_parentdir'):
                continue   # derived from the trial path; rebuilt on load
            if attr in ('_log_tag', '_session_setup_dir', 'experimental_dir',
                        '_overrides'):
                continue   # transient runtime hooks (log prefix / session I/O redirects);
                           # set per-run by the driver, never persisted — otherwise a stale
                           # _log_tag reloads and mis-labels every later log line
            if attr in self._LAYOUT_FIELDS:
                continue   # structural file/dir paths are code-driven (settings.Inputs)
                           # and rebuilt on load by _apply_inputs_layout — not persisted,
                           # so trial_settings.xml stays small and never mirrors the folders

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
                
        # Events subtree — self-contained in trial_settings.xml (no separate CSV).
        # Carries the trial type and every (name, time) landmark:
        #   <events type="walking">
        #       <event name="Right Foot Contact" time="0.1750"/>
        #       <event name="Right Foot Off"     time="0.8000"/>
        #   </events>
        ev_el = _u.ET.SubElement(root, "events")
        try:
            ev_el.set("type", self.get_trial_type())
        except Exception:
            pass
        # Number events in time order so the XML tags match the numbered labels
        # on grf_events.png (easier cross-checking).
        _evs = sorted((getattr(self, "events_list", None) or []),
                      key=lambda e: float(e.get("time", 0)))
        for _i, _e in enumerate(_evs, start=1):
            try:
                ee = _u.ET.SubElement(ev_el, "event")
                ee.set("n", str(_i))
                ee.set("name", str(_e["name"]))
                ee.set("time", f"{float(_e['time']):.4f}")
            except Exception:
                continue

        tree = _u.ET.ElementTree(root)
        _u.save_pretty_xml(tree, self.settingsXML)
        print(f"Trial settings saved to: {os.path.abspath(self.settingsXML)}")
    
    # Legacy flat-layout files named after the trial (<trial>.mot/.trc/.c3d) sitting
    # at the trial root, and where the subfoldered layout expects each to live.
    _LEGACY_TRIAL_FILES = (('.mot', 'grf_mot'), ('.trc', 'markers'), ('.c3d', 'c3d'))

    def _update_input_files(self):
        '''Relocate legacy trial-root <trial>.mot/.trc/.c3d into the subfoldered layout.

        Idempotent by design. This runs on EVERY settings save, so it has to
        cope with a trial that was already migrated: a bare os.rename() raises
        FileExistsError on Windows when the destination is present (POSIX would
        silently clobber it), and because _apply_inputs_layout() calls this for
        every Analyse, one stale trial-root copy used to fail export, IK, ID,
        MA and JRA for that trial — every stage, every run.

        When the destination already exists the trial-root file is a leftover
        from the flat layout, so it is discarded rather than allowed to
        overwrite a current export.
        '''
        for ext, attr in self._LEGACY_TRIAL_FILES:
            src = os.path.join(self.path, self.trial + ext)
            if not os.path.exists(src):
                continue
            dst = os.path.join(self.path, getattr(self, attr))
            if os.path.abspath(src) == os.path.abspath(dst):
                continue
            try:
                if os.path.exists(dst):
                    os.remove(src)
                    self._log(f"[layout] dropped stale trial-root "
                              f"{self.trial + ext} (already at {attr})")
                    continue
                os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
                os.replace(src, dst)          # atomic; never FileExistsError
                print(f"Renamed {self.trial + ext} to {getattr(self, attr)}")
            except OSError as e:
                self._log(f"[layout] could not relocate {self.trial + ext}: "
                          f"{type(e).__name__}: {e}")

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
            emg_name = self._layout_paths()['emg']

        self.update_trial_attribute('emg', emg_name)
        self.update_trial_attribute('ceinms_excitations', emg_name)

    def _remove_outputs(self):
        '''Remove existing output files from the trial directory to ensure a clean slate for the analysis'''
        input_files = [self.emg, self.c3d, self.grf_mot, self.markers]
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
        # No trial_settings.xml? That's fine — session.yaml (+ the Session-injected
        # _overrides) is the source of truth. Rebuild the code-driven folder layout,
        # resolve the model, apply the overrides, and return (no XML required).
        if not settingsXML or not os.path.exists(settingsXML):
            self.settingsXML = settingsXML
            self._apply_inputs_layout()
            try:
                self._resolve_model_dir()
            except Exception:
                pass
            _ov = getattr(self, '_overrides', None)
            if isinstance(_ov, dict):
                for _k, _v in _ov.items():
                    setattr(self, _k, _v)
            return

        tree = _u.ET.parse(settingsXML)
        root = tree.getroot()
        
        self.settingsXML = settingsXML
        
        for variable in root:
            var_name = variable.tag
            var_value = variable.text

            if var_name == 'events':
                continue   # <events> subtree parsed after this loop (not a scalar)

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

        # Events live entirely in the <events> subtree of trial_settings.xml
        # (self-contained — there is no separate events file).
        self.events_list = []
        _ev_node = root.find('events')
        if _ev_node is not None:
            # trial type is carried on the <events type=".."> attribute (no
            # separate <trial_type> tag). Fall back to any legacy <trial_type>
            # already loaded above, else name inference in get_trial_type().
            _ttype_attr = _ev_node.get('type')
            if _ttype_attr and str(_ttype_attr).strip():
                self.trial_type = str(_ttype_attr).strip()
            for _e in _ev_node.findall('event'):
                _nm, _tv = _e.get('name'), _e.get('time')
                if _nm and _tv not in (None, ''):
                    try:
                        self.events_list.append({'name': str(_nm).strip(), 'time': float(_tv)})
                    except (ValueError, TypeError):
                        pass

        # The folder LAYOUT is code-driven (settings.Inputs), not persisted. A
        # trial_settings.xml written before the subfolder refactor still holds the
        # old flat paths (grf.mot, GRF.xml, MuscleAnalysis, ...); loading them above
        # would override the new inputs/ external_biomechanics/ muscle_analysis/ ...
        # layout and break ID/SO/CEINMS. Re-apply the current Inputs layout so
        # structural paths always match the code, while *values* (time_range,
        # model_dir, alpha/beta/gamma, body_mass, ...) loaded above are preserved.
        # Reconstruct the working self.time_range from the persisted start/end
        # scalars (time_range itself is no longer serialized).
        try:
            self.time_range = [float(self.start_time), float(self.end_time)]
        except Exception:
            pass

        # parentdir/_parentdir are derived from the trial path (not persisted).
        self.parentdir = os.path.dirname(self.path)
        self._parentdir = self.path

        self._apply_inputs_layout()
        self._resolve_model_dir()

        # Session-injected config (session.yaml is the single source of truth)
        # is applied LAST so it wins over anything loaded from trial_settings.xml
        # — the two can therefore never desync. Set by Session.trial(); values
        # are the model-independent per-trial fields (time_range, side, body_mass,
        # alpha/beta/gamma, trial_type). Migration step towards removing the XML.
        _ov = getattr(self, '_overrides', None)
        if isinstance(_ov, dict):
            for _k, _v in _ov.items():
                setattr(self, _k, _v)

        print(f"Settings loaded from: {os.path.abspath(self.settingsXML)}")

    def _layout_paths(self):
        """Canonical ``{field: path}`` for this trial.

        Default is the inline package layout (``_default_layout_paths``). A
        project may OVERRIDE it (back-compat) by defining an ``Inputs`` class in
        its settings.py; if present, its instance ``__dict__`` is used instead."""
        proj = getattr(getattr(_u, 'settings', None), 'Inputs', None)
        if proj is not None:
            try:
                return {k: v for k, v in vars(proj(parentdir=self.path)).items()
                        if not k.startswith('_')}
            except Exception as e:
                self._log(f"[Warning] project Inputs override failed ({e}); "
                          f"using inline layout")
        return _default_layout_paths()

    def _apply_inputs_layout(self):
        """Force the structural file/dir paths to match the canonical (inline)
        layout, overriding any stale values loaded from trial_settings.xml. Makes
        the folder layout code-driven, so pre-refactor trials automatically pick up
        the inputs/ external_biomechanics/ muscle_analysis/ static_optimisation/
        ceinms/ structure. Non-layout values are left untouched."""
        try:
            layout = self._layout_paths()
        except Exception as e:
            self._log(f"[Warning] could not apply layout: {e}")
            return
        for f in self._LAYOUT_FIELDS:
            if f in layout:
                setattr(self, f, layout[f])
        # Session-centric layout: raw, model-INDEPENDENT inputs live ONCE under
        # <session>/experimental/<trial>/ and are shared by every iteration. If
        # experimental_dir is set, redirect those input files there (absolute),
        # leaving every DERIVED output under self.path. Runs AFTER the layout
        # reset above so it survives load_settings.
        exp = getattr(self, "experimental_dir", None)
        if exp:
            _raw = {"markers": "marker_experimental.trc", "grf_mot": "grf.mot",
                    "setup_grf": "GRF.xml", "emg": "emg.mot", "analog": "analog.csv",
                    "emg_filtered": "emg_filtered.mot",
                    "emg_filtered_normalised": "emg_filtered_normalised.mot",
                    "ceinms_excitations": "emg_filtered_normalised.mot"}
            for _attr, _fn in _raw.items():
                if hasattr(self, _attr):
                    setattr(self, _attr, os.path.join(exp, _fn))
            # The c3d itself is raw input too, and it already lives ONCE in
            # 1_c3dfiles/<trial>.c3d. Leaving it pointing at
            # <iteration>/<trial>/inputs/c3dfile.c3d meant every export copied
            # a multi-megabyte file per model per trial into a folder nothing
            # downstream reads — the same duplication prune_legacy_inputs was
            # written to clean up after the fact. Point at the original.
            try:
                from .session_layout import c3d_root as _c3d_root
                _sd = os.path.dirname(os.path.dirname(os.path.normpath(exp)))
                _cand = os.path.join(_c3d_root(_sd),
                                     os.path.basename(os.path.normpath(exp)) + ".c3d")
                if os.path.isfile(_cand):
                    self.c3d = _cand
            except Exception:
                pass
        # setup_dir is a layout field reset to "" above; in the session-centric
        # layout it must point at the shared setup templates (setup_JRA.xml, etc.).
        # Restore a pinned value so it survives every load_settings.
        _sd = getattr(self, "_session_setup_dir", None)
        if _sd:
            self.setup_dir = _sd
        # Recreate the output subfolders referenced by the layout so setup/result
        # writes don't fail after a reset that stripped them.
        _inputs_dir = LAYOUT_DIRS.get("inputs", "inputs")
        for _v in (list(layout.values()) if getattr(self, "_scaffold_output_dirs", True) else ()):
            if not isinstance(_v, str):
                continue
            _d = os.path.dirname(_v)
            # In the session-centric layout raw inputs live in experimental/, so
            # never create an empty inputs/ folder inside the iteration trial dir.
            if _d == _inputs_dir:
                continue
            if _d and not _d.startswith("..") and not os.path.isabs(_d):
                try:
                    os.makedirs(os.path.join(self.path, _d), exist_ok=True)
                except Exception:
                    pass

    def _resolve_model_dir(self):
        """Choose the OpenSim model. A muscle_force_factor model
        (scaled_opt_N10_mvicx<factor>.osim) takes PRECEDENCE when it exists, so
        changing BatchSettings.muscle_force_factor switches the model. Otherwise
        keep the configured model if present, else fall back to the base scaled
        model."""
        try:
            subject, session = subject_session_for_trial(self.path)
            if not subject or not session:
                return
            models_dir = os.path.join(_u.MODELS_DIR, subject, session)
            avail = ([f for f in os.listdir(models_dir) if f.lower().endswith('.osim')]
                     if os.path.isdir(models_dir) else [])
            factor = getattr(_u.settings.BatchSettings, 'muscle_force_factor', None)
            preferred = (f"scaled_opt_N10_mvicx{float(factor):.2f}.osim"
                         if factor else None)
            cur = getattr(self, 'model_dir', '') or ''
            cur_abs = cur if os.path.isabs(cur) else os.path.join(self.path, cur)
            # 1) muscle_force_factor model wins if it exists (code-driven).
            if preferred and preferred in avail:
                new = os.path.relpath(os.path.join(models_dir, preferred), self.path)
                if os.path.abspath(os.path.join(self.path, new)) != os.path.abspath(cur_abs):
                    self.model_dir = new
                    self._log(f"[Info] using muscle_force_factor={factor} model: {preferred}")
                return
            # 2) keep the configured model if it is present.
            if cur and os.path.exists(cur_abs):
                return
            # 3) fall back to the base scaled model.
            if not avail:
                return
            pick = (next((p for p in ("scaled_opt_N10.osim", "scaled.osim") if p in avail), None)
                    or sorted(avail)[0])
            self.model_dir = os.path.relpath(os.path.join(models_dir, pick), self.path)
            self._log(f"[Info] model_dir '{cur}' missing; using {pick}")
        except Exception as e:
            self._log(f"[Warning] model_dir resolve failed: {e}")

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

        # session.yaml is authoritative: if the Session injected a time_range via
        # _overrides, return it so the auto-derived event/marker span never wins
        # (survives every load_settings reload).
        _ov = getattr(self, '_overrides', None)
        _win = _ov.get('time_range') if isinstance(_ov, dict) else None
        if isinstance(_win, (list, tuple)) and len(_win) == 2:
            try:
                self.time_range = [float(_win[0]), float(_win[1])]
                return self.time_range
            except Exception:
                pass

        # Use the trial's events (the <events> subtree in trial_settings.xml).
        # For gait-like trials this uses the schema window (first->last foot
        # contact); otherwise the full span of the event times.
        try:
            _te = self.get_task_events()
            if _te and _te.get('window'):
                self.time_range = list(_te['window'])
                return self.time_range
        except Exception:
            pass

        try:
            pairs = self._raw_event_pairs()
            if pairs:
                _t = [t for _, t in pairs]
                self.time_range = [min(_t), max(_t)]
                return self.time_range
        except Exception:
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
                # Use the robust OpenSim C3D reader (exportC3D) for the time range.
                # io.load_c3d's `c3d` library fails on some c3d (large analog blocks),
                # printing a spurious "Could not read ...inputs\c3dfile.c3d" during export.
                import exportC3D
                _tr = exportC3D.get_time_range_from_c3d(os.path.abspath(self.c3d))
                if _tr and len(_tr) == 2:
                    self.time_range = [float(_tr[0]), float(_tr[1])]
                    return self.time_range
        except Exception:
            pass
    
    def get_trial_type(self):
        """Canonical trial type for event interpretation and overlays.

        Priority: an explicit ``<trial_type>`` in trial_settings.xml, then the
        detector hint (``_trial_type``), then inference from the trial name.
        Always one of EVENT_SCHEMAS' keys (falls back to 'generic').
        """
        t = getattr(self, 'trial_type', None)
        if isinstance(t, str) and t.strip() and t.strip().lower() != 'none':
            return _canonical_trial_type(t)
        try:
            hint = self._trial_type()
        except Exception:
            hint = None
        return _canonical_trial_type(hint or self.trial)

    def _raw_event_pairs(self):
        """``[(name, time_float)]`` for this trial.

        Reads ``self.events_list`` (the ``<events>`` subtree in trial_settings.xml,
        the single source of truth). Returns ``[]`` if there are no usable rows.
        """
        out = []
        for e in (getattr(self, 'events_list', None) or []):
            try:
                out.append((str(e['name']), float(e['time'])))
            except (KeyError, ValueError, TypeError):
                continue
        return out

    def set_events(self, events, save=True):
        """Set the trial's gait/task events and persist them in trial_settings.xml.

        ``events`` may be a list of ``(name, time)`` tuples / ``{'name','time'}``
        dicts, or a ``{name: time}`` mapping. Times are seconds. Writes the
        ``<events>`` subtree (no separate CSV needed).
        """
        items = events.items() if isinstance(events, dict) else events
        norm = []
        for it in items:
            nm, tv = (it.get('name'), it.get('time')) if isinstance(it, dict) else it
            try:
                norm.append({'name': str(nm).strip(), 'time': float(tv)})
            except (ValueError, TypeError):
                continue
        self.events_list = norm
        if save:
            self._to_xml()
        return self.events_list

    def get_task_events(self):
        """Task landmarks from the trial's events, using the trial-type schema.

        Events come from the ``<events>`` subtree in trial_settings.xml
        (the single source of truth). Returns a dict:
          ``type``        canonical trial type (EVENT_SCHEMAS key)
          ``schema``      the schema used
          ``landmarks``   {canonical_name: [sorted times]}
          ``window``      (t0, t1) that maps to 0-100% of the normalised axis
          ``marks``       [times] to draw as vertical lines (e.g. foot_off, take_off)
          ``axis``        axis label (e.g. '% gait cycle')
          ``gait_like``   whether gait-based literature curves may be overlaid
        Returns None if the trial has no events.
        """
        os.chdir(self.path)
        pairs = self._raw_event_pairs()
        if not pairs:
            return None

        ttype = self.get_trial_type()
        schema = EVENT_SCHEMAS.get(ttype, EVENT_SCHEMAS['generic'])

        # classify each event label onto a canonical landmark via the schema
        # synonyms. Labels are normalised (spaces/hyphens -> underscore) and matched
        # by exact string first, then by whole underscore-token overlap (so 'off'
        # matches 'left_foot_off' but not 'bottom'). Exact matches win.
        landmarks = {name: [] for name in schema['landmarks']}
        for lab, t in pairs:
            if not np.isfinite(t):
                continue
            norm = re.sub(r'[\s\-]+', '_', str(lab).strip().lower())
            toks = set(norm.split('_'))
            best = None
            for name, syns in schema['synonyms'].items():
                sset = set(syns)
                if norm in sset:            # exact match wins
                    best = name
                    break
                if sset & toks:             # whole-token overlap
                    best = best or name
            if best is not None:
                landmarks[best].append(float(t))
        for name in landmarks:
            landmarks[name].sort()

        # cycle window from the schema's two bounding landmarks.
        lo_name, hi_name = schema['cycle']
        lo_times, hi_times = landmarks.get(lo_name, []), landmarks.get(hi_name, [])
        window = None
        if lo_name == hi_name:
            if len(lo_times) >= 2:
                window = (lo_times[0], lo_times[-1])
        elif lo_times and hi_times:
            window = (lo_times[0], hi_times[-1])
        if window is None:  # fall back to the full span of every event time
            allt = [t for _, t in pairs if np.isfinite(t)]
            window = (min(allt), max(allt)) if allt else None

        # Explicit Start/End events are the window control (set by export_c3d to
        # the first/last event, editable to simulate a different time range) and
        # override the schema cycle when both are present.
        _start = _end = None
        for lab, tt in pairs:
            _toks = set(re.sub(r'[\s\-]+', '_', str(lab).strip().lower()).split('_'))
            if 'start' in _toks or 'begin' in _toks:
                _start = tt if _start is None else min(_start, tt)
            if 'end' in _toks or 'stop' in _toks or 'finish' in _toks:
                _end = tt if _end is None else max(_end, tt)
        if _start is not None and _end is not None and _end > _start:
            window = (_start, _end)

        marks = sorted(t for name in schema.get('marks', []) for t in landmarks.get(name, []))
        return {'type': ttype, 'schema': schema, 'landmarks': landmarks,
                'window': window, 'marks': marks, 'axis': schema['axis'],
                'gait_like': schema.get('gait_like', False)}

    def get_gait_events(self):
        """Back-compat wrapper: gait landmarks in the old shape.

        Prefer get_task_events(). Returns
        ``{'window': (t0,t1), 'foot_contact': [...], 'toe_off': [...]}``.
        """
        ev = self.get_task_events()
        if ev is None:
            return None
        lm = ev['landmarks']
        return {'window': ev['window'],
                'foot_contact': lm.get('foot_contact', []),
                'toe_off': lm.get('foot_off', []) or ev['marks']}

    def detect_events_from_grf(self, threshold=20.0, min_stance_s=0.05, write=False):
        """Detect foot-contact / foot-off events from the vertical GRF.

        Force-plate equivalent of the kinematic detector in movement_detector.
        Reads inputs/grf.mot and the plate->foot map from the GRF ExternalLoads
        (self.setup_grf: calcn_r / calcn_l), sums the vertical force per foot,
        and marks each stance onset (contact) and offset (foot off) where Fy
        crosses ``threshold`` N for at least ``min_stance_s`` seconds.

        Returns a time-sorted list of ``{'name','time'}`` (e.g. 'Right Foot
        Contact'). With ``write=True`` they are persisted via set_events(). Note
        this returns EVERY detected step; pick a single stride for a gait cycle.
        """
        os.chdir(self.path)
        try:
            grf = _u.load_any_data_file(self.grf_mot)
        except Exception as e:
            self._log(f'[detect_events] could not read {self.grf_mot}: {e}')
            return []
        t = pd.to_numeric(grf['time'], errors='coerce').to_numpy(float)

        foot = {}   # plate index -> 'r'/'l'
        try:
            root = _u.ET.parse(os.path.join(self.path, self.setup_grf)).getroot()
            for ef in root.iter('ExternalForce'):
                body = (ef.findtext('applied_to_body') or '').strip()
                fid = (ef.findtext('force_identifier') or '').strip()
                m = re.search(r'(\d+)', fid)
                if m and body.startswith('calcn_'):
                    foot[int(m.group(1))] = body.split('_')[-1]
        except Exception as e:
            self._log(f'[detect_events] could not parse {self.setup_grf}: {e}')
            return []

        def _runs(mask):
            out, i, n = [], 0, len(mask)
            while i < n:
                if mask[i]:
                    j = i
                    while j < n and mask[j]:
                        j += 1
                    out.append((i, j - 1)); i = j
                else:
                    i += 1
            return out

        def _cross(i_lo, i_hi, vy):
            # exact time where vy crosses `threshold` between two frames (linear),
            # so events sit ON the threshold rather than at the frame the loading
            # spike has already overshot it.
            y0, y1 = vy[i_lo], vy[i_hi]
            if y1 == y0:
                return float(t[i_hi])
            return float(t[i_lo] + (threshold - y0) / (y1 - y0) * (t[i_hi] - t[i_lo]))

        events = []
        n = len(t)
        for side, label in (('r', 'Right'), ('l', 'Left')):
            cols = [f'ground_force_{p}_vy' for p, s in foot.items()
                    if s == side and f'ground_force_{p}_vy' in grf.columns]
            if not cols:
                continue
            vy = np.sum([pd.to_numeric(grf[cN], errors='coerce').to_numpy(float)
                         for cN in cols], axis=0)
            for a, b in _runs(vy > threshold):
                if (t[b] - t[a]) < min_stance_s:
                    continue
                if a > 0:        # contact = crossing between a-1 (below) and a (above)
                    events.append({'name': f'{label} Foot Contact', 'time': round(_cross(a - 1, a, vy), 3)})
                if b < n - 1:    # off = crossing between b (above) and b+1 (below); skip if foot still down at end
                    events.append({'name': f'{label} Foot Off', 'time': round(_cross(b, b + 1, vy), 3)})
        events.sort(key=lambda e: e['time'])
        if write:
            self.set_events(events)
        return events

    def detect_events_from_kinematics(self, heel=None, toe=None, ref=None,
                                      min_step_s=0.35, write=False):
        """Detect foot contacts/offs from marker kinematics (no force plates).

        Coordinate method of Zeni et al. (2008, Gait Posture): along the walking
        (progression) axis, relative to a pelvis/sacrum reference, Foot Strike =
        heel marker most anterior, Foot Off = toe marker most posterior.
        Parameter-free and robust; works overground or on a treadmill and for
        trials with no / only partial force plates. Validated on this project to
        match the GRF events within a few frames (toe-offs almost exactly).

        For a velocity / "degrees-of-freedom" variant that is more robust across
        pathologies — and that transfers to the markerless video pipeline via
        foot keypoints — see the Multi-Condition algorithm (Duret et al. 2025,
        J NeuroEng Rehabil; github.com/FDuRPC/GaitEvent_MultiCondition_algo).

        heel/toe: {'r':name,'l':name} marker names (default RHEE/RTOE, LHEE/LTOE).
        ref: pelvis reference marker names (default SACR*/PSIS).
        Returns time-sorted [{'name','time'}]; write=True persists via set_events.
        """
        os.chdir(self.path)
        try:
            trc = _u.load_any_data_file(self.markers)
        except Exception as e:
            self._log(f'[detect_events_kin] could not read {self.markers}: {e}')
            return []
        t = np.asarray(trc['time'].values, float).flatten()
        names = list({(c[0] if isinstance(c, tuple) else c) for c in trc.columns})

        def _mx(name):
            if not name:
                return None
            try:
                return np.asarray(trc[name].values, float).reshape(len(t), -1)[:, :3]
            except Exception:
                return None

        def _first(cands):
            return next((c for c in cands if c in names), None)

        heel = heel or {'r': _first(['RHEE', 'RHeel', 'R_Heel', 'RCAL']),
                        'l': _first(['LHEE', 'LHeel', 'L_Heel', 'LCAL'])}
        toe = toe or {'r': _first(['RTOE', 'RToe', 'R_Toe']),
                      'l': _first(['LTOE', 'LToe', 'L_Toe'])}
        if ref is None:
            ref = ([n for n in names if str(n).upper().startswith('SACR')]
                   or [n for n in names if str(n).upper().startswith(('RPSI', 'LPSI'))]
                   or [n for n in names if 'PELV' in str(n).upper()])
        refs = [_mx(r) for r in (ref or []) if _mx(r) is not None]
        if not refs:
            self._log('[detect_events_kin] no pelvis/sacrum reference markers found.')
            return []
        ref_pos = np.nanmean(refs, axis=0)
        fps = 1.0 / np.median(np.diff(t)) if len(t) > 1 else 100.0
        ap = int(np.argmax(np.ptp(ref_pos, axis=0)))          # progression axis
        sgn = np.sign(ref_pos[-1, ap] - ref_pos[0, ap]) or 1.0  # travel direction

        def _peaks(y, dist):
            try:
                from scipy.signal import find_peaks
                idx, _ = find_peaks(y, distance=max(1, int(dist)))
                return list(idx)
            except Exception:
                out = []
                for i in range(1, len(y) - 1):
                    if y[i] >= y[i - 1] and y[i] > y[i + 1]:
                        if out and i - out[-1] < dist:
                            if y[i] > y[out[-1]]:
                                out[-1] = i
                        else:
                            out.append(i)
                return out

        dist = max(1, int(min_step_s * fps))
        events = []
        for side, label in (('r', 'Right'), ('l', 'Left')):
            h, to = _mx(heel[side]), _mx(toe[side])
            if h is None or to is None:
                continue
            hr = sgn * (h[:, ap] - ref_pos[:, ap])            # heel, forward+
            tr = sgn * (to[:, ap] - ref_pos[:, ap])           # toe, forward+
            for i in _peaks(hr, dist):
                events.append({'name': f'{label} Foot Contact', 'time': round(float(t[i]), 3)})
            for i in _peaks(-tr, dist):
                events.append({'name': f'{label} Foot Off', 'time': round(float(t[i]), 3)})
        events.sort(key=lambda e: e['time'])
        if write:
            self.set_events(events)
        return events

    def detect_events(self, method='auto', write=False, **kw):
        """Detect gait events via 'grf', 'kinematics', or 'auto'.

        'auto' tries force plates first (true L/R via GRF.xml) and falls back to
        marker kinematics (Zeni) when there is no / partial GRF — e.g. overground
        trials where the feet miss the plates. Returns time-sorted
        [{'name','time'}]; write=True persists via set_events().
        """
        m = (method or 'auto').lower()
        ev = []
        if m in ('grf', 'force', 'auto'):
            try:
                ev = self.detect_events_from_grf(**kw)
            except Exception as e:
                self._log(f'[detect_events] GRF detection failed: {e}')
                ev = []
        if not ev and m in ('kin', 'kinematic', 'kinematics', 'marker', 'auto'):
            try:
                ev = self.detect_events_from_kinematics(**kw)
            except Exception as e:
                self._log(f'[detect_events] kinematic detection failed: {e}')
                ev = []
        if write and ev:
            self.set_events(ev)
        return ev

    def plot_grf_events(self, save=True, threshold=40.0):
        """Plot per-foot vertical GRF with the trial's gait events, into inputs/.

        Uses the trial's events (events_list / <events> subtree) if present, else
        detects them with detect_events_from_grf(). Saves inputs/grf_events.png.
        """
        os.chdir(self.path)
        grf = _u.load_any_data_file(self.grf_mot)
        t = pd.to_numeric(grf['time'], errors='coerce').to_numpy(float)
        foot = {}
        try:
            root = _u.ET.parse(os.path.join(self.path, self.setup_grf)).getroot()
            for ef in root.iter('ExternalForce'):
                body = (ef.findtext('applied_to_body') or '').strip()
                fid = (ef.findtext('force_identifier') or '').strip()
                m = re.search(r'(\d+)', fid)
                if m and body.startswith('calcn_'):
                    foot[int(m.group(1))] = body.split('_')[-1]
        except Exception:
            pass

        def _sum(side):
            cols = [f'ground_force_{p}_vy' for p, s in foot.items()
                    if s == side and f'ground_force_{p}_vy' in grf.columns]
            return (np.sum([pd.to_numeric(grf[cN], errors='coerce').to_numpy(float)
                            for cN in cols], axis=0) if cols else np.zeros_like(t))

        vyR, vyL = _sum('r'), _sum('l')
        ev = getattr(self, 'events_list', None) or self.detect_events_from_grf()

        fig, ax = plt.subplots(figsize=(11, 5.2))
        ax.plot(t, vyR, color='tab:red', lw=1.8, label='Right foot Fy')
        ax.plot(t, vyL, color='tab:blue', lw=1.8, label='Left foot Fy')
        ax.axhline(threshold, color='0.6', ls=':', lw=1, label=f'{threshold:.0f} N')
        ymax = float(max(vyR.max(), vyL.max()) or 1.0)
        ax.set_ylim(-40, ymax * 1.28)
        for i, e in enumerate(sorted(ev, key=lambda x: float(x['time']))):
            nm = str(e['name']); tt = float(e['time'])
            low = nm.lower()
            is_foot = ('contact' in low) or ('foot off' in low) or ('toe' in low)
            red = 'right' in low
            contact = 'contact' in low
            num = i + 1
            if is_foot:
                # true foot event: colour by side, ▲ contact / ▼ toe-off, marker
                # placed on that foot's curve AT the event time.
                side = 'tab:red' if red else 'tab:blue'
                yv = float(np.interp(tt, t, (vyR if red else vyL)))
                ax.axvline(tt, color=side, ls='-' if contact else '--', lw=1.0, alpha=0.5)
                ax.plot(tt, yv, marker='^' if contact else 'v', color=side, ms=11,
                        mec='k', mew=0.6, zorder=6)
            else:
                # generic landmark (Start/End/…): a single black dashed line, no
                # marker — NOT a toe-off triangle on a force peak.
                side = 'k'
                ax.axvline(tt, color=side, ls='--', lw=1.0, alpha=0.7)
            ax.annotate(f"{num}. {nm} ({tt:.2f}s)", (tt, ymax * (1.02 + 0.075 * (i % 3))),
                        ha='center', va='bottom', fontsize=7.2, color=side,
                        bbox=dict(boxstyle='round,pad=0.2', fc='white', ec=side, alpha=0.9))
        ax.set_xlabel("Time (s)"); ax.set_ylabel("Vertical GRF Fy (N)")
        ax.set_title(f"{self.trial} — vertical GRF per foot + gait events "
                     f"(▲ contact, ▼ toe-off)")
        ax.legend(loc='center right', fontsize=8); ax.grid(alpha=0.25); ax.margins(x=0.01)
        fig.tight_layout()
        if save:
            _dir = os.path.join(self.path, os.path.dirname(self.grf_mot) or "")
            os.makedirs(_dir, exist_ok=True)
            out = os.path.join(_dir, "grf_events.png")
            fig.savefig(out, dpi=140)
            self._log(f'Saved GRF events figure: {out}')
        return fig, ax

    def inspect_moment_arms(self, dofs=None, side=None, out_dir=None, **kw):
        """Standalone QC of the model's moment arms over THIS trial's MOTION: plots
        each spanning muscle's moment arm vs its joint-angle coordinate over the
        recorded pose trajectory and flags wrap discontinuities. Reads the
        MuscleAnalysis output (run :meth:`run_ma` first) + the IK joint angles — no
        OpenSim, no literature. This is the motion-driven counterpart to the
        ``muscle_inspect`` model validation (which sweeps each coordinate over its
        full ROM). Saves ``moment_arm_motion_check.png`` next to the IK, and returns
        ``{"figure", "flagged", "dofs"}``.

            it.trial('Deadlift_35kg_01').inspect_moment_arms()
        """
        from bioscout.muscle_inspect.moment_arm_motion import inspect_moment_arms_over_motion
        ma_dir = os.path.join(self.path, self.ma)
        ik = os.path.join(self.path, self.ik)
        if not os.path.isdir(ma_dir):
            self._log(f"[inspect_moment_arms] no muscle_analysis/ at {ma_dir} — run run_ma first.",
                      terminal=True)
            return None
        if side is None:
            _s = str(getattr(self, 'side', 'r') or 'r').lower()
            side = '_l' if _s.startswith('l') else '_r'
        out_dir = out_dir or os.path.join(self.path, os.path.dirname(self.ik) or "")
        return inspect_moment_arms_over_motion(ma_dir, ik, out_dir=out_dir,
                                               dofs=dofs, side=side, **kw)

    def recrop_to_events(self, redetect=False):
        """Re-derive the analysis window (start/end time) from the trial's events
        and persist it — WITHOUT re-exporting the raw inputs.

        Use this after you have edited the ``<events>`` in trial_settings.xml (or
        want them re-detected) so a plain re-run of IK/ID/MA/SO/JRA solves only
        within the NEW window. A normal re-run does NOT pick up edited events on
        its own, because start_time/end_time already exist in the XML and take
        precedence; this method refreshes them. Also rewrites inputs/grf_events.png.

        ``redetect=True`` first re-detects the events from the GRF and overwrites
        them; otherwise the current (possibly hand-edited) events are used as-is.
        """
        os.chdir(self.path)
        self.load_settings(self.settingsXML)
        if redetect:
            self.detect_events(method='auto', write=True)
        # get_time_range() reads the events window (schema window for gait, else
        # min..max event time); force a re-derivation regardless of stored scalars.
        self.time_range = 'None'
        win = self.get_time_range()
        if win and len(win) == 2:
            self.time_range = [float(win[0]), float(win[1])]
            self.start_time = f"{self.time_range[0]:.4f}"
            self.end_time   = f"{self.time_range[1]:.4f}"
            self._to_xml()
            self._log(f'[recrop] analysis window set to {self.time_range} '
                      f'from events (no re-export).', terminal=True)
        else:
            self._log('[recrop] could not derive a window from events.', terminal=True)
        try:
            self.plot_grf_events()
        except Exception as e:
            self._log(f'[recrop] grf_events plot failed: {e}')
        return self.time_range

    def redetect_events(self):
        """Force-re-detect gait events from the GRF (overwriting existing events),
        then re-derive/persist the analysis window and refresh grf_events.png.

        Use after the forces changed — a plain export/re-run KEEPS existing foot
        events and will not re-detect. CLI-friendly (no args): equivalent to
        ``recrop_to_events(redetect=True)``."""
        return self.recrop_to_events(redetect=True)

    def plot_emg_processing(self, save=True, channels=None, ncol=3, norm_source=None):
        """Per-channel EMG figure: raw signal vs filtered + session-normalised.

        Reads inputs/emg.mot (raw bipolar) and inputs/emg_filtered_normalised.mot
        (the [0-1] CEINMS excitation). Saves inputs/emg_processing.png. The
        normalised file is written by the session EMG normalisation, so run that
        first (Session.run_emg_normalise / prepare_ceinms).

        ``norm_source`` (optional) is a ``{channel: trial_name}`` map of which
        trial provided the session max (MVC reference) for each channel; when
        given it is shown in red under each subplot title."""
        os.chdir(self.path)
        raw = _u.load_any_data_file(self.emg)
        try:
            norm = _u.load_any_data_file(self.emg_filtered_normalised)
        except Exception:
            norm = None
        tr = pd.to_numeric(raw['time'], errors='coerce').to_numpy(float)
        tn = (pd.to_numeric(norm['time'], errors='coerce').to_numpy(float)
              if norm is not None else None)

        def _emg_cols(df):
            return [c for c in df.columns if c.lower() != 'time' and 'emg' in c.lower()
                    and any(k.isalpha() for k in str(c).split('EMG')[-1])]

        chans = channels or _emg_cols(raw) or [c for c in raw.columns if c.lower() != 'time']
        if norm is not None:
            chans = [c for c in chans if c in norm.columns] or chans
        nrow = int(np.ceil(len(chans) / ncol))
        fig, axg = plt.subplots(nrow, ncol, figsize=(4.6 * ncol, 2.4 * nrow), squeeze=False)
        for i, ch in enumerate(chans):
            a = axg[i // ncol][i % ncol]
            a.plot(tr, pd.to_numeric(raw[ch], errors='coerce'), color='0.6', lw=0.4)
            if norm is not None and ch in norm.columns:
                a2 = a.twinx()
                a2.plot(tn, pd.to_numeric(norm[ch], errors='coerce'), color='tab:red', lw=1.5)
                a2.set_ylim(-0.05, 1.05)
                a2.tick_params(labelsize=7, colors='tab:red')
                a2.set_ylabel('norm', fontsize=7, color='tab:red')
            _ref = norm_source.get(ch) if isinstance(norm_source, dict) else None
            a.set_title(str(ch).replace('EMG_Channels_', ''), fontsize=8,
                        pad=13 if _ref else 6)   # black muscle name
            if _ref:
                a.text(0.5, 1.005, f"(norm: {_ref})", transform=a.transAxes,
                       ha='center', va='bottom', fontsize=6.5, color='tab:red')
            a.tick_params(labelsize=7); a.set_ylabel('raw', fontsize=7); a.margins(x=0)
        for j in range(len(chans), nrow * ncol):
            axg[j // ncol][j % ncol].axis('off')
        h = [plt.Line2D([], [], color='0.6', lw=1, label='raw EMG'),
             plt.Line2D([], [], color='tab:red', lw=1.5,
                        label='filtered + session-normalised (0-1)')]
        fig.legend(handles=h, loc='lower center', ncol=2, fontsize=10, frameon=False)
        fig.suptitle(f"{self.trial} — EMG: raw vs filtered-normalised", fontsize=13)
        fig.tight_layout(rect=[0, 0.03, 1, 0.98])
        if save:
            _dir = os.path.join(self.path, os.path.dirname(self.emg) or "")
            os.makedirs(_dir, exist_ok=True)
            out = os.path.join(_dir, "emg_processing.png")
            fig.savefig(out, dpi=130)
            self._log(f'Saved EMG processing figure: {out}')
        return fig, axg

    def get_markers(self):
        '''
        return a dataFrame with the name of each marker in the model and it's parent body
        '''

        os.chdir(self.path)
        try:
            model = self.load_model()
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
            'trial_settings.xml','EMG_filtered_normalised.sto','EMG_filtered_normalised_scaled_0.70.sto','marker_experimental.trc','c3dfile.c3d','GRF.xml', 'grf.mot'
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
        # Strength-scaled model name: <base>_mvicx<ratio>.osim (mvic = max
        # voluntary isometric contraction; ratio = the max-isometric-force factor).
        new_model_path = model_path.replace('.osim', f'_mvicx{factor:.2f}.osim')


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
        model = self.load_model()
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
        model = self.load_model()
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
        model = self.load_model()
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
        """Log with a prefix. Normally the trial name; during session-level
        steps (e.g. CEINMS calibration) a temporary ``_log_tag`` overrides it so
        the messages read as a session operation, not a single trial."""
        _u.print_to_log(message, trial=getattr(self, "_log_tag", None) or self.trial,
                        terminal=terminal)

    def export_c3d(self, create_folder=None, emg_string_list=None,
                   event_method='auto'):
        '''
        Export C3D file using the exportC3D script, which extracts EMG data and saves it in a format compatible with CEINMS.

            create_folder: True/False to force subfolder creation; None (default) = auto-detect:
                           uses create_folder=True when the C3D is outside self.path so that
                           outputs land in the trial subdir regardless of where the C3D lives.

            emg_string_list: list of strings to identify EMG channels in the C3D file.
        '''
        if emg_string_list is None:
            emg_string_list = _u.settings.BatchSettings.emg_string_list
        import exportC3D

        print("Exporting C3D file...")

        os.chdir(self.path)
        c3d_abs = os.path.abspath(self.c3d)
        if not os.path.exists(c3d_abs):
            print(f"C3D file not found: {c3d_abs}")
            return

        if create_folder is None:
            # Write the exported inputs NEXT TO the c3d (no stem subfolder). With the
            # subfoldered layout the c3d lives in <trial>/inputs/, so markers/grf/emg/
            # GRF.xml land in inputs/ alongside it. (Flat layout: c3d at the trial root,
            # so they land at the root — unchanged behaviour.)
            create_folder = False

        # Session-centric layout: the raw, model-independent inputs (markers/GRF/EMG)
        # live ONCE under <session>/experimental/<trial>/ (self.experimental_dir) and
        # are shared by every iteration — NOT next to the c3d. IK/ID/MA/CEINMS READ
        # from experimental/, so export must WRITE there too (otherwise the inputs land
        # in inputs/ and every downstream stage fails "file not found"). Falls back to
        # next-to-the-c3d when experimental_dir is unset (flat/legacy layout).
        _exp_out = getattr(self, "experimental_dir", None)
        full_range = exportC3D.main(c3d_filepath=c3d_abs, emg_string_list=emg_string_list,
                                    create_folder=create_folder, output_dir=_exp_out)

        # --- Auto gait/task events from the vertical GRF ------------------------
        # Detect foot contacts/offs (needs the plate->foot map in GRF.xml — create
        # it here if the export hasn't yet), then add Start/End window markers set
        # to the first/last event. Start/End control the simulated time window and
        # can be edited afterwards to run a different range. Best-effort: export
        # must never fail because events couldn't be detected.
        # Event source priority: (1) mocap-labelled foot events already loaded
        # into the trial's <events> subtree — the gold standard; (2) for gait
        # trials with none, auto-detect from GRF/kinematics; (3) non-gait trials
        # (squat/jump/static) just get an editable Start/End window over the full
        # recording (GRF foot detection is meaningless when the feet never leave
        # the plates).
        _c3d_ev = list(getattr(self, 'events_list', None) or [])
        _foot = [e for e in _c3d_ev
                 if any(k in e['name'].lower()
                        for k in ('contact', 'strike', 'off', 'heel', 'toe'))]

        events, _is_gait = [], False
        try:
            _is_gait = EVENT_SCHEMAS.get(self.get_trial_type(),
                                         EVENT_SCHEMAS['generic']).get('gait_like', False)
            if _foot:
                events = _foot                    # trust the mocap-labelled events
            elif _is_gait:
                if not os.path.exists(self.setup_grf):
                    _os = self._get_openSim()
                    _os.create_grf_xml(
                        grf_mot_path=self.grf_mot, output_xml_path=self.setup_grf,
                        marker_trc_path=self.markers,
                        right_foot_markers=getattr(_u.settings.BatchSettings, 'right_foot_markers', None),
                        left_foot_markers=getattr(_u.settings.BatchSettings, 'left_foot_markers', None),
                        right_foot_body='calcn_r', left_foot_body='calcn_l',
                        vert_force_threshold=10.0, filter_cutoff=6, datafile=None)
                events = self.detect_events(method=event_method)
        except Exception as e:
            self._log(f'[export] gait-event detection skipped: {e}')

        t0 = t1 = None
        if events:
            t0 = min(e['time'] for e in events)
            t1 = max(e['time'] for e in events)
            events = events + [{'name': 'Start', 'time': round(float(t0), 4)},
                               {'name': 'End',   'time': round(float(t1), 4)}]
        elif full_range is not None:
            t0, t1 = float(full_range[0]), float(full_range[1])
            events = [{'name': 'Start', 'time': round(t0, 4)},
                      {'name': 'End', 'time': round(t1, 4)}]

        if t0 is not None:
            self.set_events(events, save=False)   # events_list; persisted by _to_xml
            self.time_range = [float(t0), float(t1)]
        self._to_xml()

        # Drop a per-foot vertical-GRF QC figure for EVERY trial: gait trials also get
        # foot-contact/toe-off markers; non-gait (deadlift/squat/jump) just show the
        # force profile (feet never leave the plates). Build GRF.xml first if the export
        # hasn't — the plate->foot map is needed for the plot AND for ID/CEINMS anyway,
        # and it applies the CoP-distance guard (drops e.g. a barbell resting on a plate).
        _ng = len([e for e in events if e['name'] not in ('Start', 'End')])
        try:
            if not os.path.exists(self.setup_grf) and os.path.exists(self.grf_mot):
                self._get_openSim().create_grf_xml(
                    grf_mot_path=self.grf_mot, output_xml_path=self.setup_grf,
                    marker_trc_path=self.markers,
                    right_foot_markers=getattr(_u.settings.BatchSettings, 'right_foot_markers', None),
                    left_foot_markers=getattr(_u.settings.BatchSettings, 'left_foot_markers', None),
                    right_foot_body='calcn_r', left_foot_body='calcn_l',
                    vert_force_threshold=10.0, filter_cutoff=6, datafile=None)
            if _numeric_rows(self.grf_mot):
                self.plot_grf_events()
        except Exception as _e:
            self._log(f'[export] grf plot skipped: {_e}')

        # Drop the husk files this trial never really had (see _numeric_rows).
        # Keeping them would make every downstream "has inputs?" check lie.
        if getattr(_u.settings.BatchSettings, 'prune_empty_exports', True):
            self.prune_empty_exports()
        try:
            print(f"[{self.trial}] Analysis window: {self.start_time} – {self.end_time} s "
                  f"({_ng} gait events)")
        except Exception:
            pass

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

    def load_model(self, path=None):
        """Load an OpenSim model with its printBasicInfo() dump suppressed.

        ``osim.Model(...)`` writes a fixed "MODEL: / coordinates: N / forces: N
        / ..." block to std::cout on construction. That bypasses OpenSim's
        logger entirely, so opensim_log_level has no effect on it — only the
        fd-level redirect in _osim_quiet_ctx() can swallow it. Several helpers
        (get_body_mass, get_muscle_list, get_markers, ...) load the model
        per call, so a single trial printed the block several times.

        Deliberately NOT cached: callers such as increase_muscle_force() and
        adjust_moment_arms() mutate the model they are handed, so handing back a
        shared instance would let one stage's edits leak into another's.
        """
        mp = path or self.model_dir
        _os = self._get_openSim()
        import opensim as osim
        _ctx = getattr(_os, "_osim_quiet_ctx", None)
        if _ctx is None:
            return osim.Model(mp)
        with _ctx():
            return osim.Model(mp)

    def _set_replace(self, replace):
        """Set self.replace (persisted) when an explicit replace= is passed to a
        run_* step. Lets ``Analyse(path).run_ik(replace=True)`` work directly —
        Analyse absorbed the old Trial convenience, so the two are now one class."""
        if replace is not None:
            self.update_trial_attribute("replace", replace)

    def prune_empty_exports(self):
        """Delete exported inputs that contain no data, and say so once.

        A marker-only or EMG-only capture legitimately produces some of
        marker_experimental.trc / grf.mot / GRF.xml / grf_events.png with
        nothing in them. Removing them keeps the trial folder honest: the
        session runner's "no experimental inputs" check then correctly skips
        the trial instead of failing inside IK/ID.
        """
        out_dir = getattr(self, 'experimental_dir', None) or self.path
        dropped = []
        for name in _EXPORT_ARTIFACTS:
            fp = os.path.join(out_dir, name)
            if not os.path.exists(fp):
                continue
            if name.endswith('.png'):
                # only meaningful alongside real GRF
                empty = not _numeric_rows(os.path.join(out_dir, 'grf.mot'))
            elif name.endswith('.xml'):
                empty = not _grf_xml_has_forces(fp)
            else:
                empty = not _numeric_rows(fp)
            if empty:
                try:
                    os.remove(fp)
                    dropped.append(name)
                except OSError:
                    pass
        if dropped:
            self._log(f'[export] {self.trial}: no data in {", ".join(dropped)} '
                      f'— not written')
        return dropped

    def run_ik(self, replace=None):
        self._set_replace(replace)
        os.chdir(os.path.abspath(self.path))
        self.load_settings(self.settingsXML)

        # Guard: IK requires a TRC file. If marker export failed (e.g. C3D has no 3D point data),
        # skip IK rather than hanging on an input() prompt or crashing inside osim.Storage().
        if not _numeric_rows(self.markers):
            why = 'not found' if not os.path.exists(self.markers) else 'has no marker data'
            self._log(f'[SKIP] IK skipped — marker TRC {why}: {self.markers}')
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
        
        # Marker errors only — the joint-angle figure is now produced together
        # with moments by plot_kin_mom_summary() in run_id().
        try:
            self.compare_marker_locations()
            self._log(f'[Success] IK marker comparison saved in {self.path}')
        except Exception as e:
            self._log(f'[Error] during IK plotting: {e}')

    def run_id(self, replace=None):
        self._set_replace(replace)
        os.chdir(self.path)

        # Guard: ID is external-load driven — without ground reaction forces there
        # is nothing to solve. Skip rather than building a GRF.xml around an empty
        # grf.mot and failing inside OpenSim.
        if not _numeric_rows(self.grf_mot):
            why = 'not found' if not os.path.exists(self.grf_mot) else 'has no force data'
            self._log(f'[SKIP] ID skipped — grf.mot {why}: {self.grf_mot}')
            return
        # IK must have produced joint angles for ID to consume.
        if not _numeric_rows(self.ik):
            self._log(f'[SKIP] ID skipped — no IK output to solve from: {self.ik}')
            return

        _os = self._get_openSim()
        # GRF ExternalLoads XML is an EXPORT-time artifact (created in export_c3d
        # next to the grf.mot). Here it's only a last-resort fallback: build it
        # ONLY if it is missing — never regenerate it on --REPLACE during ID.
        if not os.path.exists(self.setup_grf):
            try:
                _os.create_grf_xml(grf_mot_path=self.grf_mot,
                        output_xml_path=self.setup_grf,
                        marker_trc_path=self.markers,
                        right_foot_markers=getattr(_u.settings.BatchSettings, 'right_foot_markers', None),
                        left_foot_markers=getattr(_u.settings.BatchSettings, 'left_foot_markers', None),
                        right_foot_body='calcn_r', left_foot_body='calcn_l',
                        vert_force_threshold=10.0, filter_cutoff=6, datafile=None)
            except Exception as e:
                self._log(f'[Warning] create_grf_xml failed ({type(e).__name__}: {e}); '
                          f'falling back to template copy', terminal=True)
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

        # Compact kinematics+moments summary figure (kinematics_moments.png) …
        try:
            self.plot_kin_mom_summary()
            self._log(f'[Success] kinematics+moments figure saved in {self.path}')
        except Exception as e:
            self._log(f'[Error] during kin/mom plotting: {e}')
        # … plus the classic full ID figure (inverse_dynamics.png) and residuals.
        try:
            self.plot_id()
        except Exception as e:
            self._log(f'[Warning] inverse_dynamics.png plot failed: {e}')
        try:
            self.plot_residuals()
        except Exception as e:
            self._log(f'[Warning] residuals plot failed: {e}')

    def run_ma(self, replace=None):
        self._set_replace(replace)
        os.chdir(self.path)
        # self.ma is a DIRECTORY (always exists after layout setup) — check for an
        # actual MA output file instead, or we'd always skip.
        _ma_len = os.path.join(self.path, self.ma, "_MuscleAnalysis_Length.sto")
        if os.path.exists(_ma_len) and not self.replace:
            self._log(f'[skip] Muscle Analysis output already exists: '
                      f'{os.path.abspath(_ma_len)}', terminal=True)
            return

        _os = self._get_openSim()
        try:
            _os.run_ma(osim_modelPath=self.model_dir,
                        ik_output=os.path.join(self.path, self.ik),
                        grf_xml=os.path.join(self.path, self.setup_grf),
                        results_dir=os.path.join(self.path, self.ma))
            _ma_abs = os.path.abspath(os.path.join(self.path, self.ma))
            self._log(f'[Success] Muscle Analysis completed. Results saved in:\n'
                      f'   dir   : {_ma_abs}\n'
                      f'   length: {os.path.abspath(_ma_len)}', terminal=True)
        except Exception as e:
            self._log(f'[Error] during Muscle Analysis: {e}')
            raise
    
    def run_so(self, replace=None):
        self._set_replace(replace)
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
            # Templates in setupFiles/ are flat — look up by BASENAME (self.actuators_so
            # now carries the static_optimisation/ subfolder prefix).
            template_actuators_path = os.path.join(template_dir, os.path.basename(self.actuators_so))
            os.makedirs(os.path.dirname(actuators_abs), exist_ok=True)
            if os.path.exists(template_actuators_path):
                shutil.copyfile(template_actuators_path, actuators_abs)
            else:
                # Not fatal any more. The reserve actuators may be in the model
                # instead, in which case no force-set file is wanted at all.
                # openSim.reserve_actuator_plan() raises if neither has them.
                self._log(f'[Note] no actuators template at '
                          f'{template_actuators_path} -- expecting the reserve '
                          f'actuators to be in the model itself', terminal=True)

        if os.path.exists(os.path.join(self.path, self.so_forces)) and not self.replace:
            self._log(f'Static Optimization output already exists: '
                      f'{os.path.abspath(os.path.join(self.path, self.so_forces))}', terminal=True)
            return

        try:
            # SO outputs belong in the static_optimisation/ subfolder (dir of
            # self.so_forces), not the trial root.
            so_results_dir = os.path.join(self.path, os.path.dirname(self.so_forces)) \
                if os.path.dirname(self.so_forces) else self.path
            os.makedirs(so_results_dir, exist_ok=True)
            _os.run_so(osim_modelPath=self.model_dir,
                    ik_output=ik_abs,
                    grf_xml=grf_abs,
                    setup_xml=setup_so_abs,
                    actuators=actuators_abs,
                    resultsDir=so_results_dir)
            
            def _abs(rel):
                try:
                    return os.path.abspath(os.path.join(self.path, rel)) if rel else "(n/a)"
                except Exception:
                    return str(rel)
            self._log(
                "[Success] Static Optimization completed. Results saved in:\n"
                f"   dir        : {os.path.abspath(so_results_dir)}\n"
                f"   forces     : {_abs(self.so_forces)}\n"
                f"   activations: {_abs(self.so_activations)}", terminal=True)
        except Exception as e:
            self._log(f'[Error] during Static Optimization: {e}')
            raise
        
        # Plot SO results
        try:
            self.plot_so()
            self._log(f'   plots      : {os.path.abspath(so_results_dir)}', terminal=True)
        except Exception as e:
            self._log(f'[Error] during SO plotting: {e}')
        try:
            self.plot_so_reserves()
        except Exception as e:
            self._log(f'[Warning] SO reserves plot failed: {e}')

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

    def run_jra(self, replace=None):
        self._set_replace(replace)
        os.chdir(self.path)
        self.load_settings(self.settingsXML)
        _os = self._get_openSim()

        if not os.path.exists(self.setup_jra):
            template_jra_path = os.path.join(self.setup_dir, "setup_JRA.xml")
            os.makedirs(os.path.dirname(self.setup_jra) or ".", exist_ok=True)
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

        # SO-only JCF figure so joint_contact_forces/ always has a plot straight
        # after SO's JRA — independent of whether CEINMS runs.
        try:
            self.plot_jra_comparison(
                so_only=True, save_name="JRA_SO.png",
                title="Joint Reaction (Contact) Forces: Static Optimisation")
        except Exception as e:
            self._log(f'[Warning] SO JRA figure failed: {e}')

        # Concise SO RESULT line for the run log (peak joint contact forces) — this
        # is bioscout-logged, so it survives opensim_log_level='off' when OpenSim's
        # own SO output is muted.
        try:
            self._log(self.so_result_summary(), terminal=True)
        except Exception as e:
            self._log(f'[Warning] SO summary failed: {e}')

    def so_result_summary(self):
        """One-line SO result summary for the log: peak |resultant| joint reaction
        (contact) force at hip / knee / ankle, in body-weights when body_mass is
        known (else N). Best-effort, reads the SO JRA output on disk."""
        import numpy as _np, re as _re
        jpath = self.jra if os.path.isabs(self.jra) else os.path.join(self.path, self.jra)
        d = _u.load_any_data_file(jpath)
        if d is None:
            return "[SO result] JRA not found — no summary"
        bm = None
        try:
            bm = float(getattr(self, "body_mass", None))
        except Exception:
            bm = None
        bw = bm * 9.81 if bm else None
        cols = [c for c in d.columns if str(c).lower() != "time"]
        # group force columns (…fx/…fy/…fz) by their joint-reaction prefix
        groups = {}
        for c in cols:
            m = _re.search(r"(.*?)_?f([xyz])$", str(c).lower())
            if m:
                groups.setdefault(m.group(1), {})[m.group(2)] = c
        parts = []
        for jname in ("hip", "knee", "ankle"):
            keys = [k for k in groups if jname in k]
            if not keys:
                continue
            g = groups[sorted(keys, key=len)[0]]        # shortest/most-direct match
            comps = [d[g[a]].astype(float).to_numpy() for a in ("x", "y", "z") if a in g]
            if len(comps) < 2:
                continue
            peak = float(_np.nanmax(_np.sqrt(sum(v ** 2 for v in comps))))
            parts.append(f"{jname} {peak/bw:.1f} BW" if bw else f"{jname} {peak:.0f} N")
        return "[SO result] peak JCF: " + (", ".join(parts) if parts else "n/a")

        # End-of-analysis validation for this trial (muscle lengths + literature).
        # Opt-out via settings.BatchSettings.enable_trial_validation = False.
        if getattr(_u.settings.BatchSettings, 'enable_trial_validation', True):
            try:
                self.validate_trial()
            except Exception as e:
                self._log(f'[Warning] trial validation failed: {e}')

    def run_jra_ceinms(self, replace=None):
        self._set_replace(replace)
        os.chdir(self.path)
        self.load_settings(self.settingsXML)

        # CEINMS JRA gets its OWN setup in joint_contact_forces/ (separate from SO).
        if not os.path.exists(self.setup_jra_ceinms):
            template_jra_path = os.path.join(self.setup_dir, "setup_JRA.xml")
            os.makedirs(os.path.dirname(self.setup_jra_ceinms) or ".", exist_ok=True)
            shutil.copyfile(template_jra_path, self.setup_jra_ceinms)

        if os.path.exists(self.jra_ceinms) and not self.replace:
            self._log(f'JRA CEINMS output already exists: {self.jra_ceinms} and replace is set to False.')
            return

        # ALWAYS ensure the CEINMS forces file carries the SO reserve/residual/GRF
        # columns before JRA — the JointReaction needs the FULL actuator set to
        # balance, else the contact force blows up ~100x. Idempotent (only adds
        # columns that are missing), so it's safe even if execution already did it.
        try:
            _balanced = self.add_so_columns_to_ceinms_results()
        except Exception as e:
            self._log(f'[Warning] could not add SO residual columns before CEINMS JRA: {e}', terminal=True)
            _balanced = False
        # REFUSE rather than write a JRA that is known to be wrong. Without the
        # residual/reserve/GRF columns the JointReaction cannot balance: the
        # contact force blows up ~100x AND stops depending on the muscle forces
        # at all, so every arm of a comparison gets the SAME wrong answer and
        # the file looks perfectly ordinary. That has now cost two tests
        # (t14's 353 BW hip; t25's 32 BW, byte-identical across four arms).
        # No file is recoverable; a plausible wrong file is not.
        if not _balanced and not getattr(self, 'jra_allow_unbalanced', False):
            # Remove any earlier output too: a stale file here is worse than a
            # missing one, because everything downstream reads it happily.
            _prev = self.jra_ceinms
            if _prev:
                _prev = _prev if os.path.isabs(_prev) else os.path.join(self.path, _prev)
                if os.path.exists(_prev):
                    os.remove(_prev)
            self._log('[Error] REFUSING to run CEINMS JRA: the SO '
                      'residual/reserve/GRF columns could not be added, so the '
                      'contact force would be unbalanced (~100x) and identical '
                      'whatever the muscle forces. Copy '
                      'static_optimisation/SO_StaticOptimization_force.sto into '
                      'this trial, or set jra_allow_unbalanced=True if you '
                      'really want the unbalanced number.', terminal=True)
            return

        try:
            _u.openSim.run_jra(osim_modelPath=self.model_dir,
                     ik_output=self.ik,
                     grf_xml=self.setup_grf,
                     setup_xml=self.setup_jra_ceinms,
                     actuators=None,
                     muscle_force_path=self.jra_forces_ceinms,
                     saveFileName=self.jra_ceinms)
            
            self._log(f"JRA CEINMS analysis complete. Results saved {os.path.abspath(self.jra_ceinms)}")
        except Exception as e:
            self._log(f'[Error] during Joint Reaction Analysis CEINMS: {e}')

        # Both JRAs now exist -> build the SO-vs-CEINMS comparison figure.
        try:
            self.plot_jra_comparison()
        except Exception as e:
            self._log(f'[Warning] JRA comparison figure failed: {e}')

    def plot_jra_comparison(self, so_only=False,
                            save_name="JRA_SO_vs_CEINMS.png",
                            title="Joint Reaction (Contact) Forces: SO vs CEINMS"):
        """SO vs CEINMS joint reaction (contact) forces for the joints in
        settings.BatchSettings.JRA_COLUMNS. Layout: one JOINT per row showing its
        Fx/Fy/Fz across columns, plus a final row of each joint's |resultant|.
        Saved into joint_contact_forces/.

        so_only=True ignores any CEINMS output and produces an SO-only figure
        (used right after run_jra so a JCF plot exists even when CEINMS has not
        run / produced no output)."""
        os.chdir(self.path)
        so = _u.load_any_data_file(self.jra) if os.path.exists(self.jra) else None
        ce = (None if so_only else
              (_u.load_any_data_file(self.jra_ceinms) if os.path.exists(self.jra_ceinms) else None))
        if so is None and ce is None:
            # terminal=True: a silent return here leaves joint_contact_forces/
            # holding the .sto with no figure and no explanation anywhere the
            # user is actually looking.
            self._log('[Warning] no JRA results to compare.', terminal=True); return

        # Which contact-force columns to plot (per joint) — from settings.
        # New layout: .../<session>/<iteration>/<trial>; the model/iteration that
        # decides the knee-joint naming is the PARENT of the trial folder ([-2]).
        _subject = os.path.normpath(self.path).split(os.sep)[-2]
        _side = str(getattr(self, "side", "r")).lower()   # per-trial leg (from session.yaml)
        # Legs to draw: 'both' -> R (solid) + L (dashed); else the single leg solid.
        if _side.startswith("b"):
            _sides = [("r", "-", "R"), ("l", "--", "L")]
        elif _side.startswith("l"):
            _sides = [("l", "-", "")]
        else:
            _sides = [("r", "-", "")]
        try:
            jcols_by = {sd: _u.settings.BatchSettings.JRA_COLUMNS(_subject, sd)
                        for sd, _, _ in _sides}
        except Exception as e:
            self._log(f'[Warning] JRA_COLUMNS unavailable ({e}); skipping JRA '
                      f'comparison — no JRA figure will be written. Define a '
                      f'JRA_COLUMNS(model_name, side) staticmethod on '
                      f'settings.BatchSettings returning '
                      f'{{"hip": [...fx,fy,fz], "knee": [...], "ankle": [...]}}.',
                      terminal=True); return

        # Self-heal: if a joint's configured columns aren't in the JRA output
        # (e.g. a model names its knee reaction differently than JRA_COLUMNS
        # expects — walker_knee vs Lerner_knee), find the actual reaction columns
        # by joint keyword + side + f{x,y,z} from the data itself.
        _data_cols = set(so.columns if so is not None else []) | set(ce.columns if ce is not None else [])
        def _find_cols(joint, sd):
            hit = [c for c in _data_cols
                   if joint in c.lower() and c.lower().endswith(("fx", "fy", "fz"))
                   and f"_{sd}_" in c.lower()]
            hit.sort(key=lambda c: {"fx": 0, "fy": 1, "fz": 2}.get(c.lower()[-2:], 9))
            return hit[:3]
        for sd, _, _ in _sides:
            for j in list(jcols_by[sd].keys()):
                if not all(c in _data_cols for c in jcols_by[sd][j]):
                    alt = _find_cols(j, sd)
                    if len(alt) == 3:
                        jcols_by[sd][j] = alt

        _ref = jcols_by[_sides[0][0]]
        joints = [j for j in _ref
                  if any((so is not None and c in so.columns) or
                         (ce is not None and c in ce.columns)
                         for sd, _, _ in _sides for c in jcols_by[sd][j])]
        if not joints:
            self._log('[Warning] none of JRA_COLUMNS found in the JRA outputs.'); return

        def _get(df, col):
            return (pd.to_numeric(df[col], errors='coerce').values
                    if (df is not None and col in df.columns) else None)

        # Normalise to body weight (body_mass [kg] in trial_settings.xml) if available.
        def _resolve_body_mass():
            # 1) the loaded attribute, when it is a usable number
            try:
                bm = float(self.body_mass)
                if bm and bm > 0:
                    return bm
            except Exception:
                pass
            # 2) fall back to reading <body_mass> straight from trial_settings.xml
            try:
                xml = os.path.join(self.path, getattr(self, 'settingsXML', 'trial_settings.xml'))
                if os.path.exists(xml):
                    node = _u.ET.parse(xml).getroot().find('body_mass')
                    if node is not None and node.text:
                        bm = float(node.text)
                        if bm and bm > 0:
                            return bm
            except Exception:
                pass
            return None

        _bm = _resolve_body_mass()
        _bw = _bm * 9.81 if _bm else None
        _unit = 'x BW' if _bw else 'N'
        _norm = (lambda a: (a / _bw if a is not None else a)) if _bw else (lambda a: a)
        self._log(f"[JRA] body_mass={_bm} kg -> unit={_unit}; "
                  f"literature overlay {'ON' if (_bw and getattr(self, 'overlay_literature_jcf', True)) else 'OFF'}",
                  terminal=True)

        # Task-cycle window (for mapping literature % gait cycle) + event marks.
        # Literature contact-force curves are gait-based, so only overlay them for
        # gait-like trial types (walking/running); other types still get their
        # event marks drawn but no literature bands.
        _gait_win, _marks, _gait_like = None, [], False
        try:
            _te = self.get_task_events()
            if _te:
                _gait_win = _te.get('window')
                _marks = _te.get('marks') or []
                _gait_like = _te.get('gait_like', False)
                self._log(f"[JRA] trial_type={_te.get('type')} "
                          f"window={_gait_win} marks={_marks}", terminal=True)
        except Exception:
            pass

        # Layout: one JOINT per row; columns = Fx, Fy, Fz, |resultant|.
        _axis = ['Fx', 'Fy', 'Fz']
        nrows = len(joints)
        ncols = 4
        fig, axg = plt.subplots(nrows, ncols, figsize=(ncols * 5.4, nrows * 3.8),
                                squeeze=False)
        _legtxt = ("both legs (R solid, L dashed)" if len(_sides) > 1
                   else ("left leg" if _sides[0][0] == "l" else "right leg"))
        fig.suptitle(f"{title}  —  {_legtxt}", fontsize=18)
        for r in range(nrows):
            for c in range(ncols):
                axg[r][c].axis('off')

        for r, j in enumerate(joints):
            # columns 0..2: Fx/Fy/Fz — one line per side (leg) x source (SO/CEINMS)
            for c in range(3):
                ax = axg[r][c]; ax.axis('on')
                for sd, lsty, slab in _sides:
                    col = jcols_by[sd][j][c]
                    sfx = f" {slab}" if slab else ""
                    s, e = _norm(_get(so, col)), _norm(_get(ce, col))
                    if s is not None: ax.plot(so['time'].values, s, color='tab:blue', ls=lsty, label=f'SO{sfx}')
                    if e is not None: ax.plot(ce['time'].values, e, color='tab:red', ls=lsty, label=f'CEINMS{sfx}')
                ax.set_title(f"{j} {_axis[c]}"); ax.set_xlabel("time normalised (s)"); ax.set_ylabel(f"Force ({_unit})")
                ax.legend(fontsize=8)

            # column 3: |resultant| = sqrt(Fx^2+Fy^2+Fz^2) — per side
            ax = axg[r][3]; ax.axis('on')
            def _mag(df, cols3):
                comps = [_get(df, col) for col in cols3]
                return (np.sqrt(comps[0]**2 + comps[1]**2 + comps[2]**2)
                        if all(x is not None for x in comps) else None)
            for sd, lsty, slab in _sides:
                _cols3 = jcols_by[sd][j][:3]
                sfx = f" {slab}" if slab else ""
                sm, em = _norm(_mag(so, _cols3)), _norm(_mag(ce, _cols3))
                if sm is not None: ax.plot(so['time'].values, sm, color='tab:blue', ls=lsty, label=f'SO{sfx}')
                if em is not None: ax.plot(ce['time'].values, em, color='tab:red', ls=lsty, label=f'CEINMS{sfx}')
            ax.set_title(f"{j} |resultant|"); ax.set_xlabel("time normalised (s)"); ax.set_ylabel(f"|F| ({_unit})")

            # Overlay literature joint-contact-force bands (xBW) on the resultant
            # subplot when the model is normalised to body weight and a matching
            # literature entity exists (hip/knee/ankle). Literature 0-100 % gait
            # cycle is mapped onto the EXACT plotted data span so the two share an
            # identical time axis. Shade only (no central line), extra transparent.
            # Event marks (toe-off etc.) drawn as vertical dashed lines.
            if _bw and getattr(self, 'overlay_literature_jcf', True):
                _jl = j.lower()
                _entity = next((e for e in ('hip', 'knee', 'ankle') if e in _jl), None)
                _t = (so['time'].values if so is not None else ce['time'].values)
                _win = (float(_t[0]), float(_t[-1]))   # == data span (one gait cycle)
                for _m in _marks:
                    if _win[0] <= _m <= _win[1]:
                        ax.axvline(_m, color='0.4', ls=':', lw=1, zorder=0)
                # Stance sub-window (heel-strike -> ipsilateral toe-off) for
                # stance-only literature curves. Toe-off = the last foot-off mark
                # before ~90% of the cycle (ipsilateral); fallback ~62% of cycle.
                _cyc = _win[1] - _win[0]
                _offs = [m for m in _marks if _win[0] < m < _win[0] + 0.9 * _cyc]
                _stance_win = (_win[0], max(_offs) if _offs else _win[0] + 0.62 * _cyc)
                if _entity is not None and _gait_like:
                    try:
                        from ..muscle_inspect import literature_jcf as _ljcf
                        _S = _u.settings.BatchSettings
                        _ljcf.overlay_joint_contact_force(
                            ax, entity=_entity, gait_window=_win,
                            stance_window=_stance_win, central=False,
                            band_alpha=getattr(_S, 'literature_band_alpha', 0.18),
                            line_alpha=getattr(_S, 'literature_line_alpha', 0.60),
                            line_width=getattr(_S, 'literature_line_width', 1.8))
                    except Exception as _e:
                        self._log(f'[Warning] literature JCF overlay failed: {_e}')
            ax.legend(fontsize=7)

        fig.tight_layout(rect=[0, 0, 1, 0.97])
        _dir = os.path.join(self.path, os.path.dirname(self.jra) or "")
        os.makedirs(_dir, exist_ok=True)
        save_path = os.path.join(_dir, save_name)
        plt.savefig(save_path, dpi=150)
        print(f"    JRA comparison figure saved: {save_path}", flush=True)
        return fig, axg

    def run_emg_filter(self):
        """Per-trial: filter raw EMG -> emg_filtered.mot."""
        os.chdir(self.path)
        emg_path = os.path.join(self.path, self.emg)
        if not os.path.exists(emg_path):
            self._log(f"[Warning] EMG file not found: {emg_path}")
            return
        out_path = os.path.join(self.path, os.path.dirname(self.emg) or "", 'emg_filtered.mot')
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
            prefix = _u.emg_normalise.emg_prefix_for(emg_cols)

            _lp = float(getattr(_u.settings.BatchSettings, 'emg_envelope_lowpass_hz', 6.0))
            filtered = _u.emg_normalise.filter_emg(data, emg_prefix=prefix,
                                                   lowcut_lp=_lp, sampling_freq=fs)
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
        raw EMG channel, base-named (e.g. ``EMG_Channels_EMG09_gast_med_l``, or
        ``Voltage_EMG9_gast_med_l`` on a session that labels its channels that
        way). The naming convention is DETECTED (emg_normalise.emg_prefix_for),
        never assumed -- assuming it silently returned None and left CEINMS with
        no excitations.
        Always reads the RAW emg.mot so it never compounds a previously
        normalised/filtered file. Returns ``None`` if no EMG is available.
        """
        # Prefer the configured raw-EMG path (self.emg -> inputs/emg.mot in the
        # subfoldered layout), then fall back to common flat/subfolder names.
        raw = None
        for cand in (self.emg, os.path.join("inputs", "emg.mot"), "emg.mot"):
            p = os.path.join(self.path, cand)
            if os.path.exists(p):
                raw = p
                break
        if raw is None:
            return None
        data = _u.load_any_data_file(raw)
        if data is None or 'time' not in data.columns:
            return None
        emg_cols = _u.emg_normalise.emg_channel_columns(data.columns)
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
        _lp = float(getattr(_u.settings.BatchSettings, 'emg_envelope_lowpass_hz', 6.0))
        _pre = _u.emg_normalise.emg_prefix_for(data.columns)
        filtered = _u.emg_normalise.filter_emg(data, emg_prefix=_pre,
                                               lowcut_lp=_lp, sampling_freq=fs)
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
            osimModel = self.load_model()

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

        # so_forces / jra_forces_ceinms are stored TRIAL-ROOT-relative, so anchor
        # them to self.path — reading the bare relative path fails (-> None ->
        # len(None)) whenever cwd isn't the trial root (e.g. right after CEINMS
        # execution, which chdirs into the ceinms/ output dir).
        _forces_rel = self.so_forces if forces_type == 'so' else self.jra_forces_ceinms
        _forces_abs = _forces_rel if os.path.isabs(_forces_rel) else os.path.join(self.path, _forces_rel)
        muscle_forces = _u.load_any_data_file(_forces_abs)
        if muscle_forces is None:
            raise FileNotFoundError(
                f"[calculate_muscle_moments] {forces_type} muscle forces not readable: "
                f"{_forces_abs} (CEINMS/SO produced no output, or path is wrong).")

        dofNames = _u.settings.BatchSettings.dof_list

        # Bound before the loop: every DOF can `continue` (no moment-arm file at
        # all when Muscle Analysis never ran for this trial), and `return
        # muscle_moments` below would then raise UnboundLocalError -- which reads
        # like a bug in this function instead of "MA is missing".
        muscle_moments = None
        _done = []

        for dof_name in dofNames:
            _ma_path = os.path.join(self.path, self.ma, f"_MuscleAnalysis_MomentArm_{dof_name}.sto")
            # A DOF the model doesn't have (e.g. knee_adduction on a 1-DOF-knee
            # model) produces no moment-arm file — skip it instead of crashing.
            if not os.path.exists(_ma_path):
                continue
            moment_arms = _u.load_any_data_file(_ma_path)
            if moment_arms is None:
                continue

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
            _done.append(dof_name)
            print(f"Muscle moments saved to: {os.path.abspath(moments_file_path)}")

        if not _done:
            raise FileNotFoundError(
                f"[calculate_muscle_moments] no moment-arm files under "
                f"{os.path.join(self.path, self.ma)} -- Muscle Analysis has not run "
                f"for this trial, so muscle moments cannot be computed. Re-run with "
                f"do_muscle_analysis=True (settings.py: DO_MA).")
        return muscle_moments

    #--- Valid
    def compare_marker_locations(self):
        os.chdir(self.path)
        try:
            # IK writes the model marker locations to self.model_markers
            # (external_biomechanics/_ik_model_marker_locations.sto), not the
            # trial root — use that path, with a trial-root legacy fallback.
            _virtual = os.path.abspath(self.model_markers)
            if not os.path.exists(_virtual):
                _virtual = os.path.abspath('_ik_model_marker_locations.sto')
            _u.openSim.compare_marker_locations(marker_experimental_path=os.path.abspath(self.markers),marker_virtual_path=_virtual)
        
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

                model = self.load_model()
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
        muscleList,muscleIdx = self.muscles_per_coordinate(self.load_model(), dof)
        
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
        ik_df = _u.load_any_data_file(self.ik)

        cols = list(ik_df.columns)
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

        # Order subplots proximal -> distal (same convention as plot_id).
        _stem = lambda b: b.replace('_moment', '').replace('_force', '')
        order.sort(key=lambda b: (_ID_PROX_DISTAL.index(_stem(b))
                                  if _stem(b) in _ID_PROX_DISTAL else len(_ID_PROX_DISTAL), b))

        fig, axes = self.plot_create_subplot(len(order))
        fig.suptitle("Inverse Kinematics Joint Angles", fontsize=16)
        side_style = {'r': ('tab:blue', 'right'), 'l': ('tab:red', 'left'), 'none': ('black', None)}
        t = ik_df['time']
        for i, base in enumerate(order):
            ax = axes[i]
            for side, colname in groups[base].items():
                color, lab = side_style.get(side, ('black', None))
                ax.plot(t, ik_df[colname], color=color, label=lab)
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
        id_df = _u.load_any_data_file(self.id)

        cols = list(id_df.columns)
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

        # Order subplots proximal -> distal (pelvis/trunk, down the leg, then arm).
        _stem = lambda b: b.replace('_moment', '').replace('_force', '')
        order.sort(key=lambda b: (_ID_PROX_DISTAL.index(_stem(b))
                                  if _stem(b) in _ID_PROX_DISTAL else len(_ID_PROX_DISTAL), b))

        # Resultant GRF magnitude vs time (for the pelvis-force % second axis).
        _grf_t = _grf_mag = None
        try:
            _g = _u.load_any_data_file(os.path.join(self.path, self.grf_mot))
            def _sumax(sfx):
                cc = [c for c in _g.columns if str(c).lower().endswith(sfx)]
                return (_g[cc].apply(pd.to_numeric, errors='coerce').fillna(0).sum(axis=1).values
                        if cc else np.zeros(len(_g)))
            _grf_mag = np.sqrt(_sumax('vx')**2 + _sumax('vy')**2 + _sumax('vz')**2)
            _grf_t = pd.to_numeric(_g['time'], errors='coerce').values
        except Exception:
            _grf_t = _grf_mag = None

        # One ROW per joint (top->bottom: lumbar, pelvis, hip, knee, ankle, ...);
        # each joint's DOFs fill its row left->right.
        def _joint_of(stem):
            for key in ('lumbar', 'pelvis', 'hip', 'knee', 'ankle', 'subtalar',
                        'mtp', 'elbow', 'wrist'):
                if stem.startswith(key):
                    return key
            if stem.startswith('arm'):
                return 'shoulder'
            if stem.startswith('pro_sup'):
                return 'radioulnar'
            return 'other'
        _row_order = ['lumbar', 'pelvis', 'hip', 'knee', 'ankle', 'subtalar',
                      'mtp', 'shoulder', 'elbow', 'radioulnar', 'wrist', 'other']
        joint_bases = {}
        for base in order:                       # order already DOF-sorted
            joint_bases.setdefault(_joint_of(_stem(base)), []).append(base)
        row_joints = [j for j in _row_order if j in joint_bases]
        ncols = max(len(v) for v in joint_bases.values())
        nrows = len(row_joints)

        fig, axgrid = plt.subplots(nrows, ncols, figsize=(ncols * 4.0, nrows * 2.7),
                                   squeeze=False)
        fig.suptitle("Inverse Dynamics Joint Moments", fontsize=16)
        for r in range(nrows):
            for c in range(ncols):
                axgrid[r][c].axis('off')      # hide unused cells

        side_style = {'r': ('tab:blue', 'right'), 'l': ('tab:red', 'left'), 'none': ('black', None)}
        t = id_df['time']
        for r, jname in enumerate(row_joints):
            for c, base in enumerate(joint_bases[jname]):
                ax = axgrid[r][c]
                ax.axis('on')
                for side, colname in groups[base].items():
                    color, lab = side_style.get(side, ('black', None))
                    ax.plot(t, id_df[colname], color=color, label=lab)
                ax.set_title(base)
                ax.set_xlabel("Time")
                ax.set_ylabel("Moment (Nm)" if not base.endswith('_force') else "Force (N)")
                if any(s in groups[base] for s in ('r', 'l')):
                    ax.legend(fontsize=8)
                # Pelvis residual forces: second axis = % of instantaneous |GRF|.
                if _stem(base).startswith('pelvis_t') and base.endswith('_force') and _grf_mag is not None:
                    _col = next(iter(groups[base].values()))
                    _f = pd.to_numeric(id_df[_col], errors='coerce').values
                    _gm = np.interp(t.values, _grf_t, _grf_mag)
                    with np.errstate(divide='ignore', invalid='ignore'):
                        _pct = np.where(np.abs(_gm) > 1e-6, 100.0 * _f / _gm, np.nan)
                    ax2 = ax.twinx()
                    ax2.axhspan(-10, 10, color='green', alpha=0.12, zorder=0)
                    ax2.axhspan(10, 25, color='gold', alpha=0.12, zorder=0)
                    ax2.axhspan(-25, -10, color='gold', alpha=0.12, zorder=0)
                    ax2.plot(t.values, _pct, color='tab:purple', ls='--', lw=0.9, alpha=0.85, zorder=3)
                    ax2.set_ylabel('% of |GRF|', color='tab:purple', fontsize=8)
                    ax2.tick_params(axis='y', labelcolor='tab:purple', labelsize=7)
                    _lim = max(30.0, float(np.nanmax(np.abs(_pct))) * 1.1) if np.isfinite(_pct).any() else 30.0
                    ax2.set_ylim(-_lim, _lim)

        # Crop every panel to the SAME analysed window used by plot_residuals
        # (get_time_range) so the pelvis residual curves line up between
        # inverse_dynamics.png and residuals.png.
        try:
            _t0, _t1 = self.get_time_range()
            if _t0 is not None and _t1 is not None:
                for r in range(nrows):
                    for c in range(ncols):
                        _ax = axgrid[r][c]
                        if _ax.axison:
                            _ax.set_xlim(_t0, _t1); _ax.margins(x=0)
        except Exception as _e:
            self._log(f'[plot_id] could not apply time-range crop: {_e}')

        # save figure and return
        fig.tight_layout(rect=[0, 0, 1, 0.98])
        save_path = os.path.join(self.path, os.path.splitext(self.id)[0] + '.png')
        plt.savefig(save_path)
        print(f'Figure saved to {save_path}')

        return fig, axgrid

    def plot_ik_id_summary(self, columns_to_plot='all'):
        """Combined IK+ID inspection figure: one panel per coordinate showing the
        joint ANGLE (solid line, left axis, deg) and the matching ID MOMENT /
        residual (dashed line, right axis, Nm or N) overlaid. Right leg blue,
        left leg red. Uses the same proximal->distal joint-row layout as plot_id.
        Saved next to the ID result as ``<id>_summary.png``."""
        os.chdir(self.path)
        ang = _u.load_any_data_file(self.ik)
        mom = _u.load_any_data_file(self.id)

        acols = [c for c in ang.columns if c != 'time']
        if columns_to_plot != 'all':
            acols = [c for c in acols if c in columns_to_plot]

        # coordinate -> ID column (strip the _moment / _force suffix)
        id_map = {}
        for c in mom.columns:
            if c == 'time':
                continue
            key = c[:-7] if c.endswith('_moment') else (c[:-6] if c.endswith('_force') else c)
            id_map[key] = c

        # merge left/right onto one base panel (mirrors plot_id)
        groups, order = {}, []
        for c in acols:
            base, side = self._split_side(c)
            if base not in groups:
                groups[base] = {}
                order.append(base)
            groups[base][side or 'none'] = c

        _stem = lambda b: b.replace('_moment', '').replace('_force', '')
        order.sort(key=lambda b: (_ID_PROX_DISTAL.index(_stem(b))
                                  if _stem(b) in _ID_PROX_DISTAL else len(_ID_PROX_DISTAL), b))

        # one row per joint, DOFs across the row (same layout as plot_id)
        def _joint_of(stem):
            for key in ('lumbar', 'pelvis', 'hip', 'knee', 'ankle', 'subtalar',
                        'mtp', 'elbow', 'wrist'):
                if stem.startswith(key):
                    return key
            if stem.startswith('arm'):
                return 'shoulder'
            if stem.startswith('pro_sup'):
                return 'radioulnar'
            return 'other'
        _row_order = ['lumbar', 'pelvis', 'hip', 'knee', 'ankle', 'subtalar',
                      'mtp', 'shoulder', 'elbow', 'radioulnar', 'wrist', 'other']
        joint_bases = {}
        for base in order:
            joint_bases.setdefault(_joint_of(_stem(base)), []).append(base)
        row_joints = [j for j in _row_order if j in joint_bases]
        if not row_joints:
            self._log('[plot_ik_id_summary] no coordinates to plot.'); return None, None
        ncols = max(len(v) for v in joint_bases.values())
        nrows = len(row_joints)

        fig, axg = plt.subplots(nrows, ncols, figsize=(ncols * 4.0, nrows * 2.7), squeeze=False)
        fig.suptitle("IK + ID summary   —   angle (solid, left axis)  |  moment (dashed, right axis)",
                     fontsize=15)
        for r in range(nrows):
            for c in range(ncols):
                axg[r][c].axis('off')

        ta = ang['time'].values
        tm = mom['time'].values
        side_col = {'r': 'tab:blue', 'l': 'tab:red', 'none': 'black'}
        for r, jname in enumerate(row_joints):
            for c, base in enumerate(joint_bases[jname]):
                ax = axg[r][c]; ax.axis('on')
                ax2 = ax.twinx()
                has_mom = False
                for side, acol in groups[base].items():
                    col = side_col.get(side, 'black')
                    ax.plot(ta, pd.to_numeric(ang[acol], errors='coerce'), color=col, lw=1.3)
                    idcol = id_map.get(acol)
                    if idcol is not None:
                        ax2.plot(tm, pd.to_numeric(mom[idcol], errors='coerce'),
                                 color=col, ls='--', lw=1.0, alpha=0.8)
                        has_mom = True
                ax.set_title(base, fontsize=9)
                ax.set_xlabel("Time", fontsize=8)
                ax.set_ylabel("Angle (deg)", fontsize=8)
                ax.tick_params(labelsize=7)
                _idc = id_map.get(next(iter(groups[base].values())))
                ax2.set_ylabel("Force (N)" if (_idc or '').endswith('_force') else "Moment (Nm)",
                               fontsize=8)
                ax2.tick_params(labelsize=7)
                if not has_mom:
                    ax2.set_yticks([])

        h = [plt.Line2D([], [], color='tab:blue', lw=1.5, label='right'),
             plt.Line2D([], [], color='tab:red', lw=1.5, label='left'),
             plt.Line2D([], [], color='0.3', lw=1.5, ls='-', label='angle (left axis)'),
             plt.Line2D([], [], color='0.3', lw=1.2, ls='--', label='moment (right axis)')]
        fig.legend(handles=h, loc='lower center', ncol=4, fontsize=9, frameon=False)
        fig.tight_layout(rect=[0, 0.03, 1, 0.97])
        save_path = os.path.join(self.path, os.path.splitext(self.id)[0] + '_summary.png')
        plt.savefig(save_path, dpi=140)
        print(f"    IK+ID summary figure saved: {save_path}", flush=True)
        return fig, axg

    def plot_kin_mom_summary(self, dofs=None):
        """Compact kinematics+moments figure for the summary DOFs only.

        Two rows: TOP = joint angles (deg), BOTTOM = ID moments (Nm). One column
        per DOF base (left/right merged onto the same column: right=blue, left=red).
        DOFs come from SummarySettings.dofs unless overridden. Saved to the
        external_biomechanics folder as ``kinematics_moments.png``. Replaces the
        old joint_angles.png / inverse_dynamics.png / inverse_dynamics_summary.png."""
        os.chdir(self.path)
        # Name the model this figure describes. Four printBasicInfo blocks used
        # to sit here saying it in 52 lines; one line says it better, and says
        # WHICH model -- which is the part that actually varies between runs.
        print(f"    kinematics+moments running with: {self.model_dir}", flush=True)
        if dofs is None:
            dofs = list(getattr(_u.settings.SummarySettings, 'dofs', []))
        if not dofs:
            self._log('[plot_kin_mom_summary] no DOFs configured.'); return None, None

        # Which leg(s) to include for THIS trial. Per-trial <analysis_leg> in
        # trial_settings.xml wins; else the SummarySettings default; else "both".
        # "r"/"l" keep that side (+ midline pelvis/lumbar/trunk DOFs); "both" keeps all.
        leg = (getattr(self, 'analysis_leg', None)
               or getattr(_u.settings.SummarySettings, 'analysis_leg', 'both'))
        leg = str(leg).strip().lower()
        if leg in ('r', 'right', 'l', 'left'):
            want = 'r' if leg.startswith('r') else 'l'
            def _keep(d):
                _b, _s = self._split_side(d)
                return _s in (None, want)      # keep the chosen side + midline DOFs
            dofs = [d for d in dofs if _keep(d)]

        ang = _u.load_any_data_file(self.ik)
        mom = _u.load_any_data_file(self.id)

        # moment column lookup keyed by coordinate name
        mom_map = {}
        for c in mom.columns:
            if c == 'time':
                continue
            key = c[:-7] if c.endswith('_moment') else (c[:-6] if c.endswith('_force') else c)
            mom_map[key] = c

        # group requested DOFs by base stem, merging left/right onto one column
        groups, order = {}, []
        for d in dofs:
            base, side = self._split_side(d)
            if base not in groups:
                groups[base] = {}
                order.append(base)
            groups[base][side or 'none'] = d

        # ---- per-joint IK marker error (mm) for annotation ------------------
        # Prefer the per-marker file (_ik_marker_errors_all.sto) so the error can
        # be split by joint/side; otherwise fall back to the aggregate RMS file
        # (_ik_marker_errors.sto) and stamp one global value on every panel.
        _ext = os.path.join(self.path, os.path.dirname(self.ik))
        _jm = (getattr(_u.settings.SummarySettings, 'joint_marker_patterns', None)
               or {
                   'pelvis': ['ASI', 'PSI', 'SACR'],
                   'hip':    ['ASI', 'PSI', 'SACR', 'THI', 'TH'],
                   'knee':   ['THI', 'FC', 'KNE', 'TIB', 'SHA', 'TH'],
                   'ankle':  ['MAL', 'ANK', 'HEE', 'TOE', 'MT', 'M5', 'SHA', 'TIB'],
               })
        marker_err, global_rms = {}, None
        try:
            _allp = os.path.join(_ext, '_ik_marker_errors_all.sto')
            if os.path.isfile(_allp):
                _me = _u.load_any_data_file(_allp)
                _cols = [c for c in _me.columns if str(c).lower() != 'time']

                def _rms(sel):
                    v = _me[sel].apply(pd.to_numeric, errors='coerce').values
                    v = v[np.isfinite(v)]
                    return float(np.sqrt(np.mean(v ** 2)) * 1000.0) if v.size else None

                for jk in {b.split('_')[0] for b in order}:
                    pats = _jm.get(jk)
                    if not pats:
                        continue
                    per = {}
                    for side, letter in (('r', 'R'), ('l', 'L')):
                        sel = [c for c in _cols
                               if any(p.upper() in str(c).upper() for p in pats)
                               and (str(c).upper().startswith(letter)
                                    or not str(c).upper().startswith(('L', 'R')))]
                        r = _rms(sel) if sel else None
                        if r is not None:
                            per[side] = r
                    if per:
                        marker_err[jk] = per
            else:
                _aggp = os.path.join(_ext, '_ik_marker_errors.sto')
                if os.path.isfile(_aggp):
                    _agg = _u.load_any_data_file(_aggp)
                    if 'marker_error_RMS' in _agg.columns:
                        rms = pd.to_numeric(_agg['marker_error_RMS'],
                                            errors='coerce').values
                        rms = rms[np.isfinite(rms)]
                        if rms.size:
                            global_rms = float(np.sqrt(np.mean(rms ** 2)) * 1000.0)
                    self._log('[plot_kin_mom_summary] per-marker error file '
                              '(_ik_marker_errors_all.sto) not found; using global '
                              'IK RMS. Run the per-marker error calc to get '
                              'per-joint values.')
        except Exception as _e:
            self._log(f'[plot_kin_mom_summary] marker-error annotation skipped: {_e}')

        ncols = len(order)
        fig, axes = plt.subplots(2, ncols, figsize=(max(3.0 * ncols, 6), 6),
                                 squeeze=False)
        fig.suptitle('Kinematics (top) & Moments (bottom)', fontsize=15)
        side_style = {'r': ('tab:blue', 'right'), 'l': ('tab:red', 'left'),
                      'none': ('black', None)}
        ta = ang['time'].values
        tm = mom['time'].values
        for j, base in enumerate(order):
            ax_ang, ax_mom = axes[0][j], axes[1][j]
            for side, dof in groups[base].items():
                color, lab = side_style.get(side, ('black', None))
                if dof in ang.columns:
                    ax_ang.plot(ta, pd.to_numeric(ang[dof], errors='coerce'),
                                color=color, label=lab)
                mcol = mom_map.get(dof)
                if mcol is not None:
                    ax_mom.plot(tm, pd.to_numeric(mom[mcol], errors='coerce'),
                                color=color, label=lab)
            ax_ang.set_title(base, fontsize=10)
            # marker-error text box (per-joint RMS if available, else global)
            jk = base.split('_')[0]
            note = None
            if jk in marker_err:
                parts = [f"{s.upper()} {marker_err[jk][s]:.1f}"
                         for s in ('r', 'l') if s in marker_err[jk]]
                if parts:
                    note = 'mk err (mm): ' + ', '.join(parts)
            elif global_rms is not None:
                note = f'IK RMS(all mk): {global_rms:.1f} mm'
            if note:
                ax_ang.text(0.02, 0.97, note, transform=ax_ang.transAxes,
                            fontsize=6.5, va='top', ha='left',
                            bbox=dict(boxstyle='round,pad=0.25', fc='white',
                                      ec='0.6', alpha=0.85))
            ax_ang.set_ylabel('Angle (deg)', fontsize=9)
            ax_mom.set_ylabel('Moment (Nm)', fontsize=9)
            ax_mom.set_xlabel('Time (s)', fontsize=9)
            for ax in (ax_ang, ax_mom):
                ax.tick_params(labelsize=8)
            if any(s in groups[base] for s in ('r', 'l')):
                ax_ang.legend(fontsize=7)

        fig.tight_layout(rect=[0, 0, 1, 0.96])
        save_path = os.path.join(self.path, os.path.dirname(self.ik),
                                 'kinematics_moments.png')
        fig.savefig(save_path, dpi=140)
        print(f"    kinematics+moments summary saved: {save_path}", flush=True)
        # Drop it from pyplot's global registry. This runs once per trial per
        # iteration; at ~22 MB retained per figure an unclosed one costs about
        # a gigabyte per 48 trials, which is what makes long runs crawl. The
        # returned Figure stays usable -- close() only unregisters it.
        try:
            plt.close(fig)
        except Exception:
            pass
        return fig, axes

    def plot_so(self):
        """Static-Optimization results — one figure, one subplot per muscle.

        Per muscle: force (red, N), activation (grey line, 0-1 on a twin axis),
        and — for muscles with a measured EMG channel (via
        CEINMSSettings.emg_muscle_mapping) — the normalised EMG shaded grey in the
        background. Uses the model's real muscle set, so pelvis residuals
        (FX/FY/..) and reserve actuators are excluded. Saved as SO_results.png
        (no trial name) next to the SO results."""
        os.chdir(self.path)
        so_forces = _u.load_any_data_file(self.so_forces)
        so_activations = _u.load_any_data_file(self.so_activations)
        try:
            emg = _u.load_any_data_file(self.emg_filtered_normalised)
        except Exception:
            emg = None

        tr = self.get_time_range()

        def _crop(df):
            return df[(df['time'] >= tr[0]) & (df['time'] <= tr[1])]

        so_forces = _crop(so_forces)
        so_activations = _crop(so_activations)
        tf = pd.to_numeric(so_forces['time'], errors='coerce').to_numpy(float)
        ta = pd.to_numeric(so_activations['time'], errors='coerce').to_numpy(float)
        te = (pd.to_numeric(emg['time'], errors='coerce').to_numpy(float)
              if emg is not None else None)
        t0, t1 = float(tf.min()), float(tf.max())

        # real muscles from the model (excludes residual/reserve actuators)
        try:
            muscles = [m for m in self.get_muscle_list() if m in so_forces.columns]
        except Exception:
            muscles = [c for c in so_forces.columns if c != 'time']
        if not muscles:
            self._log('[plot_so] no muscles in SO force file.')
            return None, None

        # reverse EMG map: muscle -> channel (for the shaded-EMG background)
        rev = self._emg_reverse_map()

        ncol = 8
        nrow = int(np.ceil(len(muscles) / ncol))
        fig, axg = plt.subplots(nrow, ncol, figsize=(2.6 * ncol, 1.7 * nrow), squeeze=False)
        for i, mu in enumerate(muscles):
            a = axg[i // ncol][i % ncol]
            a.plot(tf, pd.to_numeric(so_forces[mu], errors='coerce'),
                   color='tab:red', lw=1.0, zorder=3)
            a.tick_params(axis='y', labelsize=5, colors='tab:red')
            # activation (and EMG) share a twin axis on the RIGHT (0-1)
            a2 = a.twinx()
            act = (pd.to_numeric(so_activations[mu], errors='coerce').to_numpy(float)
                   if mu in so_activations.columns else None)
            ch = rev.get(mu)
            r2 = None
            if emg is not None and ch and ch in emg.columns:
                y = pd.to_numeric(emg[ch], errors='coerce').to_numpy(float)
                mask = (te >= t0) & (te <= t1)
                a2.fill_between(te[mask], 0, y[mask], color='0.6', alpha=0.35, zorder=1)
                # R^2 between measured EMG and SO activation (EMG resampled onto
                # the activation time grid over the shared window).
                if act is not None:
                    ei = np.interp(ta, te, y)
                    v = np.isfinite(ei) & np.isfinite(act)
                    if v.sum() > 3 and np.std(ei[v]) > 1e-9 and np.std(act[v]) > 1e-9:
                        r2 = float(np.corrcoef(ei[v], act[v])[0, 1] ** 2)
            if act is not None:
                a2.plot(ta, act, color='0.35', lw=1.0, zorder=2)
            a2.set_ylim(0, 1.05)
            a2.tick_params(axis='y', labelsize=5, colors='0.35')
            ttl = mu if r2 is None else f"{mu}  R²={r2:.2f}"
            a.set_title(ttl, fontsize=6.5); a.set_xlim(t0, t1)
            a.tick_params(axis='x', labelsize=5); a.margins(x=0)
        for j in range(len(muscles), nrow * ncol):
            axg[j // ncol][j % ncol].axis('off')

        h = [plt.Line2D([], [], color='tab:red', lw=1.5, label='muscle force (N, left axis)'),
             plt.Line2D([], [], color='0.35', lw=1.5, label='activation (0-1, right axis)'),
             plt.Line2D([], [], color='0.6', lw=6, alpha=0.4, label='EMG (shaded, if measured)'),
             plt.Line2D([], [], color='none', label='R² = EMG vs activation')]
        fig.legend(handles=h, loc='lower center', ncol=4, fontsize=9, frameon=False)
        fig.suptitle("Static Optimization results", fontsize=14)
        fig.tight_layout(rect=[0, 0.02, 1, 0.985])
        _so_dir = os.path.join(self.path, os.path.dirname(self.so_forces) or "")
        os.makedirs(_so_dir, exist_ok=True)
        out = os.path.join(_so_dir, "SO_results.png")
        fig.savefig(out, dpi=130)
        self._log(f'Saved SO results figure: {out}')

        # companion muscle-group summary (EMG-mapped groups only)
        try:
            self._plot_muscle_groups(
                [('SO', so_forces, so_activations, '-')], emg,
                os.path.join(_so_dir, 'SO_muscle_groups.png'),
                'Static Optimization — muscle groups (EMG-mapped)')
        except Exception as _e:
            self._log(f'[Warning] SO muscle-groups plot failed: {_e}')
        return fig, axg

    def emg_channel_map(self):
        """{emg_channel: [model_muscles]} for this trial.

        session.yaml's ``emg_map`` (injected as ``self.emg_map`` by
        Session._apply_session_config) wins, then CEINMSSettings, then
        BatchSettings. The session must win: two sessions of the same study can
        have different electrode sets and channel names.

        When the session defines several NAMED maps, ``self.emg_map`` is
        already the one THIS iteration selected — the resolution happens in
        ``Iteration.trial_config``, so every consumer here sees one flat map.
        """
        own = getattr(self, 'emg_map', None)
        if own:
            return dict(own)
        cs = getattr(_u.settings, 'CEINMSSettings', None) or _u.settings.BatchSettings
        return dict((getattr(cs, 'emg_muscle_mapping', None)
                     or getattr(_u.settings.BatchSettings, 'emg_muscle_mapping', {}) or {}))

    def _emg_reverse_map(self):
        """{model_muscle: emg_channel} from :meth:`emg_channel_map`."""
        return {mu: ch for ch, mus in self.emg_channel_map().items() for mu in mus}

    def _plot_muscle_groups(self, sources, emg_df, out_path, title):
        """Per muscle-GROUP panel (settings.BatchSettings.MUSCLE_GROUPS).

        For the muscles in each group that HAVE an EMG channel: summed muscle
        FORCE (red, N left axis) and mean ACTIVATION (grey, 0-1 right axis), with
        that channel's normalised EMG shaded grey. ``sources`` is a list of
        (label, forces_df, acts_df, linestyle) so several models (e.g. CEINMS
        solid, SO dashed) overlay in the same panels. Only groups with >=1
        EMG-mapped muscle present are drawn. Returns the saved path or None."""
        rev = self._emg_reverse_map()
        groups = getattr(_u.settings.BatchSettings, 'MUSCLE_GROUPS', {}) or {}
        if not groups or not sources:
            return None
        # Use the trial's SIMULATION window (persisted crop), not the full-trial
        # data span, so the plot matches the analysed time range.
        _tr = getattr(self, "time_range", None)
        if isinstance(_tr, (list, tuple)) and len(_tr) == 2:
            t0, t1 = float(_tr[0]), float(_tr[1])
        else:
            t0, t1 = self.get_time_range()
        # Per-trial leg filter: walking trials set side left/right -> keep only that
        # leg's muscles; squats (side unset / 'both') keep BOTH legs.
        _s = str(getattr(self, "side", "both")).lower()
        def _leg_ok(mus):
            if _s.startswith('l'):
                return not mus.endswith('_r')
            if _s.startswith('r'):
                return not mus.endswith('_l')
            return True
        te = (pd.to_numeric(emg_df['time'], errors='coerce').to_numpy(float)
              if emg_df is not None else None)

        panels = []  # (group_name, [muscles_with_emg], channel)
        for gname, gmuscles in groups.items():
            mm = [m for m in gmuscles
                  if m in rev and _leg_ok(m) and any(m in s[1].columns for s in sources)]
            if mm:
                panels.append((gname, mm, rev.get(mm[0])))
        if not panels:
            self._log('[muscle_groups] no EMG-mapped groups to plot.')
            return None

        ncol = min(5, len(panels))
        nrow = int(np.ceil(len(panels) / ncol))
        fig, axg = plt.subplots(nrow, ncol, figsize=(3.0 * ncol, 2.2 * nrow), squeeze=False)
        for i, (gname, mm, ch) in enumerate(panels):
            a = axg[i // ncol][i % ncol]; a2 = a.twinx()
            emg_y = emg_t = None
            if emg_df is not None and ch and ch in emg_df.columns:
                emg_y = pd.to_numeric(emg_df[ch], errors='coerce').to_numpy(float)
                emg_t = te
                m = (te >= t0) & (te <= t1)
                a2.fill_between(te[m], 0, emg_y[m], color='0.6', alpha=0.30, zorder=1)
            _stats = []   # (label, r2, rmse) EMG vs mean activation per source
            for (lbl, fdf, adf, ls) in sources:
                fcols = [m for m in mm if m in fdf.columns]
                if fcols:
                    tf = pd.to_numeric(fdf['time'], errors='coerce').to_numpy(float)
                    fsum = fdf[fcols].apply(pd.to_numeric, errors='coerce').sum(axis=1).to_numpy(float)
                    a.plot(tf, fsum, color='tab:red', ls=ls, lw=1.0, zorder=3)
                acols = [m for m in mm if m in adf.columns]
                if acols:
                    tacts = pd.to_numeric(adf['time'], errors='coerce').to_numpy(float)
                    amean = adf[acols].apply(pd.to_numeric, errors='coerce').mean(axis=1).to_numpy(float)
                    a2.plot(tacts, amean, color='0.35', ls=ls, lw=1.0, zorder=2)
                    # R2/RMSE: measured EMG vs mean activation over the window
                    if emg_y is not None:
                        w = (tacts >= t0) & (tacts <= t1)
                        ei = np.interp(tacts, emg_t, emg_y)
                        v = w & np.isfinite(ei) & np.isfinite(amean)
                        if v.sum() > 3 and np.std(ei[v]) > 1e-9 and np.std(amean[v]) > 1e-9:
                            _stats.append((lbl, _u.rsquared(ei[v], amean[v]),
                                           _u.rmse(ei[v], amean[v])))
            a2.set_ylim(0, 1.05)
            a.tick_params(axis='y', labelsize=6, colors='tab:red')
            a2.tick_params(axis='y', labelsize=6, colors='0.35')
            a.set_title(gname, fontsize=8); a.set_xlim(t0, t1)
            a.tick_params(axis='x', labelsize=6); a.margins(x=0)
            if _stats:
                # single source: compact title suffix; multiple: stacked text box
                if len(_stats) == 1:
                    _, r2, rm = _stats[0]
                    a.set_title(f"{gname}  R²={r2:.2f}  RMSE={rm:.2f}", fontsize=7)
                else:
                    txt = "\n".join(f"{l}: R²={r2:.2f} RMSE={rm:.2f}"
                                    for l, r2, rm in _stats)
                    a.text(0.03, 0.97, txt, transform=a.transAxes, fontsize=5.5,
                           va='top', ha='left',
                           bbox=dict(boxstyle='round', fc='white', ec='0.7', alpha=0.7))
        for j in range(len(panels), nrow * ncol):
            axg[j // ncol][j % ncol].axis('off')

        handles = [plt.Line2D([], [], color='tab:red', lw=1.5, label='∑ force (N, left)'),
                   plt.Line2D([], [], color='0.35', lw=1.5, label='mean activation (right)'),
                   plt.Line2D([], [], color='0.6', lw=6, alpha=0.4, label='EMG (shaded)'),
                   plt.Line2D([], [], color='none', label='R²/RMSE = EMG vs activation')]
        if len(sources) > 1:
            handles += [plt.Line2D([], [], color='0.2', lw=1.3, ls=s[3], label=s[0]) for s in sources]
        fig.legend(handles=handles, loc='lower center', ncol=len(handles), fontsize=9, frameon=False)
        fig.suptitle(title, fontsize=13)
        fig.tight_layout(rect=[0, 0.05, 1, 0.96])
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        fig.savefig(out_path, dpi=130); plt.close(fig)
        self._log(f'Saved muscle-groups figure: {out_path}')
        return out_path

    def plot_so_reserves(self):
        """Reserve-actuator inspection for Static Optimization.

        One panel per coordinate that has a ``<coord>_reserve`` column in the SO
        force file. Each reserve is plotted as a PERCENTAGE of that coordinate's
        Inverse-Dynamics moment (100·reserve/ID_moment), with green (±10%) and
        gold (±25%) shaded acceptance bands — small reserves mean the muscles are
        carrying the joint moment. Saved to the SO folder as
        ``SO_reserves_inspection.png``."""
        os.chdir(self.path)
        so = _u.load_any_data_file(self.so_forces)
        idm = _u.load_any_data_file(self.id)
        t0, t1 = self.get_time_range()

        reserves = [c for c in so.columns if str(c).endswith('_reserve')]
        if not reserves:
            self._log('[plot_so_reserves] no reserve columns in SO force file.')
            return None, None

        ts = pd.to_numeric(so['time'], errors='coerce').to_numpy(float)
        ti = pd.to_numeric(idm['time'], errors='coerce').to_numpy(float)
        # order proximal->distal where known
        def _key(c):
            base = c[:-len('_reserve')]
            return (_ID_PROX_DISTAL.index(base) if base in _ID_PROX_DISTAL
                    else len(_ID_PROX_DISTAL), c)
        reserves.sort(key=_key)

        ncol = min(5, len(reserves))
        nrow = int(np.ceil(len(reserves) / ncol))
        fig, axg = plt.subplots(nrow, ncol, figsize=(3.0 * ncol, 2.3 * nrow),
                                squeeze=False)
        for i, rc in enumerate(reserves):
            a = axg[i // ncol][i % ncol]
            base = rc[:-len('_reserve')]
            res = pd.to_numeric(so[rc], errors='coerce').to_numpy(float)
            mcol = base + '_moment'
            a.axhspan(-10, 10, color='green', alpha=0.12, zorder=0)
            a.axhspan(10, 25, color='gold', alpha=0.12, zorder=0)
            a.axhspan(-25, -10, color='gold', alpha=0.12, zorder=0)
            if mcol in idm.columns:
                mom = pd.to_numeric(idm[mcol], errors='coerce').to_numpy(float)
                mom_i = np.interp(ts, ti, mom)
                with np.errstate(divide='ignore', invalid='ignore'):
                    pct = np.where(np.abs(mom_i) > 1e-6, 100.0 * res / mom_i, np.nan)
                a.plot(ts, pct, color='tab:purple', lw=1.1, zorder=3)
                mp = np.nanmax(np.abs(pct)) if np.isfinite(pct).any() else 30.0
                peak = f"  peak={mp:.0f}%"
                # show the FULL curve — symmetric limit at least ±30 (so the
                # ±10/±25% bands stay visible) but expand to the data peak.
                _lim = max(30.0, float(mp) * 1.1)
                a.set_ylim(-_lim, _lim)
            else:
                a.plot(ts, res, color='tab:purple', lw=1.1, zorder=3)
                peak = "  (no ID moment)"   # absolute reserve; let it auto-scale
            a.axhline(0, color='0.5', lw=0.6)
            a.set_title(base + peak, fontsize=7)
            a.set_xlim(t0, t1); a.tick_params(labelsize=6); a.margins(x=0)
            a.set_ylabel('reserve (% of ID moment)', fontsize=6)
        for j in range(len(reserves), nrow * ncol):
            axg[j // ncol][j % ncol].axis('off')

        h = [plt.Line2D([], [], color='tab:purple', lw=1.5, label='reserve (% of ID moment)'),
             plt.Line2D([], [], color='green', lw=6, alpha=0.3, label='±10%'),
             plt.Line2D([], [], color='gold', lw=6, alpha=0.3, label='±25%')]
        fig.legend(handles=h, loc='lower center', ncol=3, fontsize=9, frameon=False)
        fig.suptitle('SO reserve actuators — % of Inverse-Dynamics moment', fontsize=13)
        fig.tight_layout(rect=[0, 0.05, 1, 0.96])
        _so_dir = os.path.join(self.path, os.path.dirname(self.so_forces) or "")
        os.makedirs(_so_dir, exist_ok=True)
        out = os.path.join(_so_dir, 'SO_reserves_inspection.png')
        fig.savefig(out, dpi=130); plt.close(fig)
        self._log(f'Saved SO reserves inspection figure: {out}')
        return fig, axg

    def plot_residuals(self):
        """Pelvis residual inspection for Inverse Dynamics.

        Six panels: the three pelvis residual FORCES (pelvis_tx/ty/tz_force) and
        three residual MOMENTS (pelvis_tilt/list/rotation_moment), each plotted as
        a PERCENTAGE of the instantaneous resultant |GRF| (forces) or |GRF|·h
        proxy (moments use |GRF| too), with green (±10%) and gold (±25%) shaded
        bands — the standard residual-acceptance thresholds. Saved to the
        external_biomechanics folder as ``residuals.png``."""
        os.chdir(self.path)
        idm = _u.load_any_data_file(self.id)
        t0, t1 = self.get_time_range()
        ti = pd.to_numeric(idm['time'], errors='coerce').to_numpy(float)

        # resultant |GRF| magnitude vs time from the grf.mot
        grf_t = grf_mag = None
        try:
            g = _u.load_any_data_file(os.path.join(self.path, self.grf_mot))
            def _sumax(sfx):
                cc = [c for c in g.columns if str(c).lower().endswith(sfx)]
                return (g[cc].apply(pd.to_numeric, errors='coerce').fillna(0)
                        .sum(axis=1).to_numpy(float) if cc else np.zeros(len(g)))
            grf_mag = np.sqrt(_sumax('vx')**2 + _sumax('vy')**2 + _sumax('vz')**2)
            grf_t = pd.to_numeric(g['time'], errors='coerce').to_numpy(float)
        except Exception as e:
            self._log(f'[plot_residuals] could not load GRF for normalisation: {e}')

        panels = [('pelvis_tx_force', 'FX residual force'),
                  ('pelvis_ty_force', 'FY residual force'),
                  ('pelvis_tz_force', 'FZ residual force'),
                  ('pelvis_tilt_moment', 'tilt residual moment'),
                  ('pelvis_list_moment', 'list residual moment'),
                  ('pelvis_rotation_moment', 'rotation residual moment')]
        fig, axg = plt.subplots(2, 3, figsize=(13, 6.4), squeeze=False)
        for i, (col, label) in enumerate(panels):
            a = axg[i // 3][i % 3]                      # LEFT axis: absolute (N / Nm)
            is_force = col.endswith('_force')
            a.axhline(0, color='0.5', lw=0.6, zorder=1)
            present = col in idm.columns
            if present:
                res = pd.to_numeric(idm[col], errors='coerce').to_numpy(float)
                a.plot(ti, res, color='tab:purple', lw=1.3, zorder=3)  # absolute (left)
            a.set_ylabel('Residual force (N)' if is_force else 'Residual moment (Nm)',
                         fontsize=7, color='tab:purple')
            a.tick_params(axis='y', labelsize=6, colors='tab:purple')
            a.tick_params(axis='x', labelsize=6); a.set_xlim(t0, t1); a.margins(x=0)

            # RIGHT axis: % of instantaneous |GRF| — shaded ±10 / ±25 % bands here.
            a2 = a.twinx()
            a2.axhspan(-10, 10, color='green', alpha=0.12, zorder=0)
            a2.axhspan(10, 25, color='gold', alpha=0.12, zorder=0)
            a2.axhspan(-25, -10, color='gold', alpha=0.12, zorder=0)
            a2.set_ylim(-30, 30); a2.set_ylabel('% of |GRF|', fontsize=7, color='0.4')
            a2.tick_params(axis='y', labelsize=6, colors='0.4')
            if present and grf_mag is not None:
                gm = np.interp(ti, grf_t, grf_mag)
                with np.errstate(divide='ignore', invalid='ignore'):
                    pct = np.where(np.abs(gm) > 1e-6, 100.0 * res / gm, np.nan)
                a2.plot(ti, pct, color='0.45', ls='--', lw=0.9, zorder=2)  # % (right)
                mp = np.nanmax(np.abs(pct)) if np.isfinite(pct).any() else 0.0
                a.set_title(f"{label}  peak={mp:.0f}% |GRF|", fontsize=8)
            elif present:
                a.set_title(f"{label} (no GRF for %)", fontsize=8)
            else:
                a.set_title(f"{label} (missing)", fontsize=8)

        h = [plt.Line2D([], [], color='tab:purple', lw=1.5, label='residual (N/Nm, left axis)'),
             plt.Line2D([], [], color='0.45', lw=1.3, ls='--', label='% of |GRF| (right axis)'),
             plt.Line2D([], [], color='green', lw=6, alpha=0.3, label='±10%'),
             plt.Line2D([], [], color='gold', lw=6, alpha=0.3, label='±25%')]
        fig.legend(handles=h, loc='lower center', ncol=4, fontsize=9, frameon=False)
        fig.suptitle('Inverse-Dynamics pelvis residuals — absolute (left) & % of |GRF| (right)',
                     fontsize=13)
        fig.tight_layout(rect=[0, 0.05, 1, 0.96])
        _e_dir = os.path.join(self.path, os.path.dirname(self.id) or "")
        os.makedirs(_e_dir, exist_ok=True)
        out = os.path.join(_e_dir, 'residuals.png')
        fig.savefig(out, dpi=130); plt.close(fig)
        self._log(f'Saved residuals figure: {out}')
        return fig, axg

    def muscle_inspect(self, motion=None, coordinate_names=None, muscle_filter=None,
                       filter_freq=6.0, max_iterations=3, min_jump_mm=1.0,
                       make_plots=True):
        """Motion-driven muscle-path check of this trial's model over its kinematics.

        Runs ``bioscout.muscle_inspect`` on ``self.model_dir`` (the trial's OpenSim
        model) driven by ``motion`` (default: this trial's IK joint_angles, i.e.
        ``self.ik``). It detects muscle path points inside wrap cylinders that make
        moment arms / muscle lengths discontinuous, projects them out, and writes a
        corrected ``<model>_modWO.osim`` next to the original model plus before/after
        length-waveform figures.

        Outputs go to ``<trial>/muscle_inspect/``. Returns
        ``(success, corrected_model_path, log_path)``. Needs the `opensim` package.
        """
        os.chdir(self.path)
        from ..muscle_inspect import muscle_checker as _mc

        model = os.path.abspath(self.model_path)          # alias of model_dir
        motion = os.path.abspath(motion or self.joint_angles)   # alias of ik (joint_angles.mot)
        for _p in (model, motion):
            if not os.path.isfile(_p):
                self._log(f'[muscle_inspect] not found: {_p}', terminal=True)
                return False, model, None

        out_dir = os.path.join(self.path, 'muscle_inspect')
        os.makedirs(out_dir, exist_ok=True)
        self._log(f'[muscle_inspect] model={os.path.basename(model)} '
                  f'motion={os.path.basename(motion)} -> {out_dir}', terminal=True)

        # BEFORE muscle lengths (for the comparison plots)
        before = None
        if make_plots:
            try:
                before = _mc.compute_lengths(model, motion, coordinate_names,
                                             muscle_filter, filter_freq)
            except Exception as e:
                self._log(f'[muscle_inspect] before-lengths failed: {e}')

        # run the detect-and-fix pipeline (corrected model written next to the model)
        success, corrected, log_path = _mc.check_and_fix_muscle_paths(
            model, motion, coordinate_names=coordinate_names, muscle_filter=muscle_filter,
            filter_freq=filter_freq, max_iterations=max_iterations,
            min_jump_mm=min_jump_mm, out_dir=os.path.dirname(model), verbose=False)

        # AFTER lengths + before/after waveform figure
        if make_plots and before is not None:
            try:
                tvec, names, Lb = before
                _, _, La = _mc.compute_lengths(corrected, motion, coordinate_names,
                                               muscle_filter, filter_freq)
                _mc.plot_length_waveforms(tvec, names, Lb, La, out_dir,
                                          tag=os.path.splitext(os.path.basename(model))[0],
                                          dk=dict(min_jump_m=min_jump_mm / 1000.0))
            except Exception as e:
                self._log(f'[muscle_inspect] length plot failed: {e}')

        self._log(f'[muscle_inspect] {"OK" if success else "max-iter"}; '
                  f'corrected={os.path.basename(corrected)}; log={log_path}',
                  terminal=True)
        return success, corrected, log_path

    def validate_trial(self, side="_r"):
        """End-of-analysis model validation for this trial → ``<trial>/validation/``.

        Runs ``bioscout.muscle_inspect`` over THIS trial's kinematics and against
        the literature:
          1. muscle-path check over the trial's joint_angles (flags/repairs path
             points inside wrap cylinders that give discontinuous moment arms),
          2. moment-arm / fibre-length validation vs digitised literature bands,
          3. joint-contact-force literature bands for the trial TYPE (gait) if any.

        Everything is best-effort (wrapped) so it never breaks the pipeline."""
        os.chdir(self.path)
        out = os.path.join(self.path, "validation")
        os.makedirs(out, exist_ok=True)
        model = os.path.abspath(self.model_dir)
        motion = os.path.abspath(self.ik)
        self._log(f'[validate] {os.path.basename(model)} over '
                  f'{os.path.basename(motion)} -> {out}', terminal=True)

        # 1. muscle LENGTHS over the trial kinematics + discontinuity flags.
        #    (Lightweight: compute once and plot — no multi-iteration path CORRECTION,
        #    which is expensive. To run the full detect-and-fix, call muscle_inspect().)
        try:
            from ..muscle_inspect import muscle_checker as _mc
            tvec, names, L = _mc.compute_lengths(model, motion, None, None, 6.0)
            _mc.plot_length_waveforms(tvec, names, L, None, out,
                                      tag=os.path.splitext(os.path.basename(model))[0])
        except Exception as e:
            self._log(f'[validate] muscle-length check failed: {e}')

        # 2. moment-arm vs literature bands — over the ACTUAL TRIAL MOTION
        #    (validation_moment_arms_motion.png), i.e. moment arms evaluated at
        #    the poses the task really used, not a synthetic ROM sweep. The old
        #    static ROM sweep is still available via run_validation() if wanted.
        try:
            from ..muscle_inspect import muscle_length_validation as _mlv, paths as _mpaths
            _mot = _u.load_any_data_file(motion)
            _mlv.run_validation_motion(model, _mot, _mpaths.resolve_literature_csv(),
                                       out, side=side)
        except Exception as e:
            self._log(f'[validate] motion moment-arm validation failed: {e}')

        # 2b. joint ISOMETRIC and ISOKINETIC strength vs literature bands.
        try:
            from ..muscle_inspect import strength as _mstr, paths as _mpaths
            if os.path.exists(_mpaths.LITERATURE_STRENGTH_CSV) and \
               os.path.exists(_mpaths.MUSCLE_FUNCTIONS_CSV):
                _mstr.run_strength(model, _mpaths.LITERATURE_STRENGTH_CSV,
                                   _mpaths.MUSCLE_FUNCTIONS_CSV, out, side=side)
                _mstr.run_isokinetic(model, _mpaths.LITERATURE_STRENGTH_CSV,
                                     _mpaths.MUSCLE_FUNCTIONS_CSV,
                                     _mpaths.LITERATURE_STRENGTH_CSV, out, side=side)
            else:
                self._log('[validate] strength literature CSVs not found; skipping strength validation')
        except Exception as e:
            self._log(f'[validate] joint-strength validation failed: {e}')

        # 3. THIS trial's joint-contact force vs the literature bands (gait trials).
        #    Overlays the trial's |resultant| JCF (÷ body weight, over 0-100% cycle)
        #    on the digitised literature bands for hip & knee.
        try:
            from ..muscle_inspect import literature_jcf as _ljcf
            is_gait = EVENT_SCHEMAS.get(self.get_trial_type(),
                                        EVENT_SCHEMAS.get('generic', {})).get('gait_like')
            if is_gait:
                jra_path = os.path.join(self.path, self.jra)
                jra = _u.load_any_data_file(jra_path) if os.path.exists(jra_path) else None
                bw = (float(self.body_mass) * 9.81) if getattr(self, 'body_mass', None) else None
                # iteration folder (parent of trial) decides knee-joint naming
                _subj = os.path.normpath(self.path).split(os.sep)[-2]
                jcols = (_u.settings.BatchSettings.JRA_COLUMNS(_subj, getattr(self, "side", "r"))
                         if hasattr(_u.settings.BatchSettings, 'JRA_COLUMNS') else {})
                xpct = np.linspace(0, 100, 101)
                for _ent in ('hip', 'knee'):
                    model_curve = None
                    if jra is not None and bw and _ent in jcols:
                        cc = [c for c in jcols[_ent] if c in jra.columns]
                        if cc:
                            comp = [pd.to_numeric(jra[c], errors='coerce').to_numpy(float)
                                    for c in cc]
                            resultant = np.sqrt(np.sum([c ** 2 for c in comp], axis=0))
                            y = np.interp(xpct, np.linspace(0, 100, len(resultant)),
                                          resultant / bw)
                            model_curve = (xpct, y)
                    _ljcf.plot_jcf_validation(
                        os.path.join(out, f'jcf_{_ent}_literature.png'),
                        entity=_ent, model=model_curve,
                        title=f"{self.trial} — {_ent} JCF vs literature")
        except Exception as e:
            self._log(f'[validate] JCF vs literature failed: {e}')

        self._log(f'[Success] trial validation written to {out}', terminal=True)
        return out

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
                # THIS iteration's channel map (session.yaml emg_map, resolved
                # per iteration when the session defines several named maps).
                # It used to read `_u.settings.EMG_muscle_mapping`, which no
                # settings.py has ever defined -- so this panel raised, was
                # swallowed upstream, and silently drew nothing.
                emg_mapping = analysis.emg_channel_map()

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

                # Channels actually present in this trial's EMG file. A DOF can
                # legitimately have none (pelvis_tilt, lumbar_extension, any
                # un-instrumented joint) -- then there is nothing to draw and,
                # below, nothing to score against.
                emg_cols = ([c for c in filtered_emg_mapping if c in emg.columns]
                            if emg is not None else [])

                def _present(df, muscles):
                    if df is None:
                        return []
                    return [m for m in muscles if m in df.columns]

                for emg_col in emg_cols:
                    mapped_muscles = filtered_emg_mapping[emg_col]
                    ax.plot(emg['time'], emg[emg_col], label=f'EMG {emg_col}',
                            color=colors['EMG'], alpha=0.6)
                    for _act, _key, _lab in ((so_activations, 'SO', 'SO Activations'),
                                             (ceinms_activations, 'CEINMS', 'CEINMS Activations')):
                        _cols = _present(_act, mapped_muscles)
                        if _cols:
                            ax.plot(_act['time'], _act[_cols].mean(axis=1),
                                    label=_lab, color=colors[_key], alpha=0.6, linestyle='-')

                # Add space in the y axis to display metrics RMSE and R2
                y_min, y_max = ax.get_ylim()
                ax.set_ylim(y_min, y_max + abs(y_max - y_min)*0.5)
                if emg_cols:
                    # Score against the MEAN of every mapped channel, not the
                    # last one the plotting loop happened to leave behind.
                    emg_ref = emg[emg_cols].mean(axis=1)
                    for _act, _key, _lab, _y in (
                            (muscle_activations_so, 'SO', 'SO Activations vs EMG', 0.90),
                            (muscle_activations_ceinms, 'CEINMS', 'CEINMS Activations vs EMG', 0.80)):
                        _cols = _present(_act, muscles_for_coord)
                        if not _cols:
                            continue
                        total = _act[_cols].mean(axis=1)
                        _rmse = rmse(emg_ref, total)
                        _r2 = _u.rsquared(emg_ref, total)
                        _pct = (_rmse / (y_max - y_min)) * 100 if (y_max - y_min) != 0 else 0
                        ax.text(0.05, _y,
                                f'{_lab}\nRMSE: {_rmse:.2f} (% {_pct:.2f})\nR2: {_r2:.2f}',
                                transform=ax.transAxes, fontsize=6, verticalalignment='top')
        
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
                      f'time {tvals[0]:.4f}..{tvals[-1]:.4f}s', terminal=False)

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
        for candidate in (self.ceinms_excitations, self.emg_filtered_normalised):
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
                  f"time_range={self.time_range}", terminal=False)

        # Fix EMG timestamps if the C3D export produced wrong time values
        excitations = self._fix_emg_timestamps(excitations)

        # The session.yaml window (self.time_range) is authoritative: write it into
        # inputData.xml VERBATIM wherever it already sits strictly INSIDE the data.
        # We still measure the intersection of every CEINMS input file's own time
        # span, but only pull an END inward (by epsilon) when the requested bound
        # falls on/outside a data boundary — otherwise CEINMS's strict is_contained()
        # in check_input_times aborts ("Input data 'muscleTendonLength' does not
        # cover the CEINMS time range!" with no .sto). The MuscleAnalysis _Length.sto
        # is run over the IK window and is usually the NARROWEST file, so it drives
        # the clamp when it does happen.
        _tr = self.time_range if isinstance(self.time_range, (list, tuple)) else [0.0, 1e9]
        _req_lo, _req_hi = float(_tr[0]), float(_tr[1])
        _data_lo, _data_hi = -float('inf'), float('inf')
        _ma_len = os.path.join(self.path, self.ma, '_MuscleAnalysis_Length.sto')
        _cap_files = [os.path.join(self.path, excitations), _ma_len,
                      os.path.join(self.path, self.ik),
                      os.path.join(self.path, self.id)]
        for _f in _cap_files:
            try:
                if not os.path.exists(_f):
                    continue
                _df = _u.load_any_data_file(_f)
                if _df is not None and 'time' in _df.columns and len(_df) > 0:
                    _t = pd.to_numeric(_df['time'], errors='coerce')
                    _data_lo = max(_data_lo, float(_t.iloc[0]))
                    _data_hi = min(_data_hi, float(_t.iloc[-1]))
            except Exception as _e:
                self._log(f'[Warning] time-cap skipped {os.path.basename(_f)}: {_e}')
        # Start from the session.yaml window; clamp+nudge ONLY the ends that need it.
        _lo, _hi = _req_lo, _req_hi
        if math.isfinite(_data_lo) and math.isfinite(_data_hi) and _data_hi > _data_lo:
            _eps = max(1e-4, 0.002 * (_data_hi - _data_lo))
            if _req_lo <= _data_lo:          # bound sits on/below first sample
                _lo = _data_lo + _eps
            if _req_hi >= _data_hi:          # bound sits on/above last sample
                _hi = _data_hi - _eps
        input_time_range = [_lo, _hi] if _hi > _lo else list(self.time_range)
        if [_lo, _hi] != [_req_lo, _req_hi]:
            self._log(f"[CEINMS] session.yaml window [{_req_lo:.3f}, {_req_hi:.3f}] "
                      f"exceeds available data [{_data_lo:.4f}, {_data_hi:.4f}]; "
                      f"using {input_time_range} to satisfy CEINMS coverage check.",
                      terminal=True)
        else:
            self._log(f"[CEINMS] input startStopTime = {input_time_range} "
                      f"(session.yaml window, within data span)", terminal=False)

        try:
            _abs = lambda rel: os.path.join(self.path, rel)  # trial-relative -> absolute
            _u.ceinms.create_input_data(MAFolder=_abs(self.ma),
                                     excitationsFile=_abs(excitations),
                                     motionFile=_abs(self.ik),
                                     externalTorquesFile=_abs(self.id),
                                     externalLoadsFile=_abs(self.setup_grf),
                                     startStopTime=input_time_range,
                                     output_path=_abs(self.ceinms_input_data))
            self._log(f'    [created inputs]  {os.path.abspath(self.ceinms_input_data)}, '
                      f'time_range [{input_time_range[0]:.3f}, {input_time_range[1]:.3f}]', terminal=True)
        except Exception as e:
            self._log(f'[Error] Failed to create CEINMS input data: {e}', terminal=True)
    
    def create_ceinms_calibration_cfg(self, calibration_trial_names=None):
        """
        Create ceinms_cfg_calibration.xml for CEINMS calibration.
        """
        
        os.chdir(self.path)
        # trialSet paths in the cfg are resolved relative to the cfg's OWN folder
        # (ceinms_calibration/), so compute them relative to that, not the session.
        _cfg_dir = os.path.dirname(os.path.abspath(os.path.join(self.path, self.ceinms_calibration_cfg)))
        inputPaths = []
        _ceinms_input_rel = self._layout_paths()['ceinms_input_data']
        for trial_name in calibration_trial_names:
            filepath = os.path.join(self.parentdir, trial_name, _ceinms_input_rel)
            inputPaths.append(os.path.relpath(filepath, _cfg_dir))

        # This ITERATION's calibration bounds, if session.yaml named a
        # `calibration:` config for it (injected as `calibration_params` by
        # Iteration.trial_config). Absent, settings.py decides as before.
        _u.ceinms.create_calibrationCfg(osimModelPath=self.model_dir,
                                     inputPaths=inputPaths,
                                     outputPath=self.ceinms_calibration_cfg,
                                     params_override=getattr(
                                         self, 'calibration_params', None))

    def create_excitation_generator(self):
        import traceback as _tb
        os.chdir(self.path)
        _abs_eg = os.path.abspath(self.ceinms_excitation_generator)
        self._log(f'CEINMS excitation generator path: {_abs_eg} (exists={os.path.exists(_abs_eg)})', terminal=False)
        if os.path.exists(_abs_eg) and not self.replace:
            self._log(f'CEINMS excitation generator already exists: {_abs_eg}', terminal=True)
            return
        
        try:
            _u.ceinms.create_excitation_generator(osim_model_path=self.model_dir,
                                               emg_path=self.ceinms_excitations,
                                               save_path=self.ceinms_excitation_generator,
                                               mapping=self.emg_channel_map()
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
        
        # The template lives FLAT in setupFiles/ (setupFiles/ceinms_cfg_optimise.xml).
        # self.ceinms_optimise_cfg is a TRIAL-relative path ("ceinms/ceinms_cfg_optimise.xml"),
        # so joining it onto setup_dir looked for setupFiles/ceinms/... and raised
        # FileNotFoundError. Try the flat name first, keep the nested one as a fallback.
        _tpl_candidates = [
            os.path.join(self.setup_dir, os.path.basename(self.ceinms_optimise_cfg)),
            os.path.join(self.setup_dir, self.ceinms_optimise_cfg),
        ]
        _tpl = next((c for c in _tpl_candidates if os.path.exists(c)), None)
        if _tpl is None:
            raise FileNotFoundError(
                "CEINMS optimise cfg template not found. Looked for:\n  "
                + "\n  ".join(os.path.abspath(c) for c in _tpl_candidates))

        _u.ceinms.create_optimise_setupFiles(ceinmsModelPath=self.ceinms_calibrated_model,
                                          inputDataFile=self.ceinms_input_data,
                                          calibrationCfgPath=self.ceinms_optimise_cfg,
                                          excitationGeneratorFilePath=self.ceinms_excitation_generator,
                                          outputDirectory=self.ceinms_optimisation_dir,
                                          setupXMLPath=self.ceinms_optimise_setup,
                                          templateCfgXMLPath=_tpl)

    # ---- executing against the UNCALIBRATED subject model -----------------
    # `ceinms: {calibrated: false}` is resolved in session.py, which sets
    # `ceinms_calibrated` on the trial, builds subjectUncalibrated.xml, skips
    # the calibration and logs that execution will use it. Until 2026-08-12
    # nothing DOWNSTREAM read that flag: every writer here hard-coded
    # `ceinms_calibrated_model`, so the setup named subjectCalibrated.xml
    # regardless -- a file an uncalibrated arm does not even have. CEINMS then
    # produced no output, surfacing as "MuscleForces.sto not readable" rather
    # than as a wiring error. Worse is when a calibrated subject DOES sit in
    # the folder from an earlier run: the arm silently executes CALIBRATED,
    # agrees with the calibrated arms, and reads as "calibration changes
    # nothing" -- the strongest possible wrong conclusion an uncalibrated
    # control can produce.
    # The names below are the ones bioscout/tests/test_uncalibrated_execution.py
    # was written against.

    @property
    def ceinms_is_calibrated(self):
        """Does EXECUTION use the calibrated subject model?

        `_overrides` FIRST: session.yaml lands there and is authoritative -- the
        lesson `ceinms.modes._set_weights` records after a bounds run silently
        solved every arm at one gamma. Reading the plain attribute alone would
        report `calibrated` for an iteration session.yaml had switched off.

        Default True: trials built outside `Session.trial()` never carry the
        flag and must keep the existing behaviour.
        """
        _ov = getattr(self, '_overrides', None)
        if isinstance(_ov, dict) and 'ceinms_calibrated' in _ov:
            _v = _ov['ceinms_calibrated']
        else:
            _v = getattr(self, 'ceinms_calibrated', True)
        # yaml_bool, not bool(): PyYAML gives a bool for bare `false` but a
        # STRING for `"false"`, and bool("false") is True -- which would run
        # the calibration the session asked to skip, silently.
        from bioscout.utils.session import yaml_bool
        return yaml_bool(_v)

    @property
    def ceinms_execution_subject(self):
        """The subject XML CEINMS execution must read for this trial."""
        return (self.ceinms_calibrated_model if self.ceinms_is_calibrated
                else self.ceinms_uncalibrated_model)

    @property
    def ceinms_exe_tag(self):
        """`_uncal` for an uncalibrated solve, else ''.

        Without it a calibrated and an uncalibrated solve of the same trial and
        weights both write `Execution_a1_b1_g30` and one overwrites the other,
        leaving a result that reads as calibrated whichever ran last.
        """
        return "" if self.ceinms_is_calibrated else "_uncal"

    def ceinms_exe_out_rel(self):
        """Trial-root-relative execution output folder, tag and weights included.

        One definition: the setup XML, the JRA forces path and every reader go
        through this, so the folder cannot be named two different ways.
        Still matches `Execution_*`, which is how `ceinms.modes` finds a solve.
        """
        return (f'{self.ceinms_exe_dir}{self.ceinms_exe_tag}'
                f'_a{self.alpha}_b{self.beta}_g{self.gamma}')

    def create_ceinms_exe_setup(self):
        # ceinms_setup.xml lives in ceinms/; CEINMS resolves its inner paths
        # relative to THAT dir. Compute every path relative to the setup file's
        # own folder (not the trial root) so we don't get ceinms\ceinms\... .
        _abs = lambda rel: os.path.abspath(os.path.join(self.path, rel))
        _base = os.path.dirname(_abs(self.ceinms_exe_setup))
        _rel = lambda rel: os.path.relpath(_abs(rel), _base)
        os.makedirs(_base, exist_ok=True)

        root = _u.ET.Element('ceinms')
        _u.ET.SubElement(root, 'subjectFile').text = _rel(self.ceinms_execution_subject)
        _u.ET.SubElement(root, 'inputDataFile').text = _rel(self.ceinms_input_data)
        _u.ET.SubElement(root, 'executionFile').text = _rel(self.ceinms_exe_cfg)
        _u.ET.SubElement(root, 'excitationGeneratorFile').text = _rel(self.ceinms_excitation_generator)
        _u.ET.SubElement(root, 'outputDirectory').text = _rel(self.ceinms_exe_dir)
        # Create tree and write to file
        tree = _u.ET.ElementTree(root)
        _u.save_pretty_xml(tree, self.ceinms_exe_setup)
        print(f"Created {os.path.abspath(self.ceinms_exe_setup)}")

    def create_ceinms_exe_cfg(self):
        os.chdir(self.path)
        
        try:
            dofSet = ' '.join(_u.settings.BatchSettings.dof_list)
            _u.ceinms.create_ceinms_cfg(ceinmsModelPath=self.ceinms_execution_subject,
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

        # Session-level CEINMS files live in ceinms_calibration/. If a previous
        # VALID calibration is already there, archive the whole folder as
        # ceinms_calibration_backup_<old_time> (old_time = mtime of the previous
        # subjectCalibrated.xml) and start fresh — so the live folder always keeps
        # the same fixed names and downstream paths never change.
        _cal_dir = os.path.abspath(os.path.join(self.path, os.path.dirname(self.ceinms_calibration_cfg)))
        _prev = os.path.join(_cal_dir, os.path.basename(self.ceinms_calibrated_model))
        if os.path.isdir(_cal_dir) and os.path.exists(_prev):
            _old = _u.time.strftime('%y_%m_%d_%H_%M', _u.time.localtime(os.path.getmtime(_prev)))
            _bak = f"{_cal_dir}_backup_{_old}"
            try:
                if os.path.exists(_bak):
                    shutil.rmtree(_bak)
                shutil.move(_cal_dir, _bak)
                self._log(f"[Info] archived previous calibration -> {os.path.basename(_bak)}", terminal=True)
            except Exception as _e:
                self._log(f"[Warning] could not archive previous calibration: {_e}")
        os.makedirs(_cal_dir, exist_ok=True)

        # Session-level log tag: these are SESSION operations, so log them as
        # "[CEINMS-cal <session>]" (calibration), distinct from execution.
        self._log_tag = f"CEINMS-cal {os.path.basename(self.parentdir)}"

        # -- Prerequisites (steps 1-4 of the CEINMS pipeline) --
        self._log("[CEINMS 1/6] create model — uncalibrated subject XML from the OpenSim model", terminal=True)
        self.create_ceinms_model()
        if not os.path.exists(self.ceinms_uncalibrated_model):
            self._log("[Error] CEINMS calibration aborted: uncalibrated model could not be created.", terminal=True)
            return
        self._log("[CEINMS 2/6] create excitation generator — EMG -> muscle mapping", terminal=True)
        self.create_excitation_generator()
        self._log("[CEINMS 3/6] create inputData XML for all calibration trials in the session", terminal=True)
        self.create_ceinms_input_data()

        # Also build CEINMS input data for every OTHER configured calibration
        # trial that has muscle analysis but no inputData yet. Otherwise the
        # collection below only finds the current (often STATIC) reference trial
        # and falls back to calibrating on it alone — the cause of calibration
        # silently using Static_01. create_ceinms_input_data() needs only a
        # trial's own MA/IK/ID/EMG (no model), so a bare sibling Trial suffices.
        _allowed = getattr(_u.settings.CEINMSSettings, 'calibration_trial_names', None) or []
        _input_rel = self._layout_paths()['ceinms_input_data']
        _ma_rel = os.path.join(LAYOUT_DIRS["muscle_analysis"], "_MuscleAnalysis_Length.sto")
        _Trial = type(self)
        for _entry in _allowed:
            if _entry == self.trial:
                continue                                   # current trial: already built above
            _tdir = os.path.join(self.parentdir, _entry)
            if not os.path.isdir(_tdir):
                continue
            if os.path.exists(os.path.join(_tdir, _input_rel)) and not self.replace:
                continue                                   # input data already present (rebuilt when replace=True)
            if not os.path.exists(os.path.join(_tdir, _ma_rel)):
                continue                                   # no muscle analysis — unusable for calib
            try:
                _sib = _Trial(_tdir)
                _sib._log_tag = self._log_tag
                # Mirror the host trial's experimental-input binding so the sibling's
                # EMG/GRF resolve to the shared experimental/<trial>/ folder (the
                # session-normalised emg_filtered_normalised.mot + GRF.xml), NOT the
                # per-trial inputs/ folder — which is empty in the session-centric
                # layout and made inputData.xml point at a non-existent ..\inputs\emg.mot.
                if getattr(self, "experimental_dir", None):
                    _sib.experimental_dir = os.path.join(
                        os.path.dirname(self.experimental_dir), _entry)
                    if getattr(self, "_session_setup_dir", None):
                        _sib._session_setup_dir = self._session_setup_dir
                    _sib._apply_inputs_layout()
                _sib.create_ceinms_input_data()
                self._log(f"[Info] CEINMS: built input data for calibration trial '{_entry}'")
            except Exception as _e:
                self._log(f"[Warning] CEINMS: could not build input data for "
                          f"calibration trial '{_entry}': {_e}", terminal=True)

        # Collect all sibling trial directories that have input data. A trial is
        # only usable for calibration if it ALSO has the MuscleAnalysis length
        # file CEINMS reads (Lmt) — static/quiet trials get EMG input data from
        # normalise but never run MA, so including them makes ceinms-calibrate
        # abort with "Error opening file ..._MuscleAnalysis_Length.sto".
        allowed = getattr(_u.settings.CEINMSSettings, 'calibration_trial_names', None)
        calib_trials = []
        input_data_name = self._layout_paths()['ceinms_input_data']
        ma_dir_name = LAYOUT_DIRS["muscle_analysis"]
        for entry in sorted(os.listdir(self.parentdir)):
            if allowed and entry not in allowed:
                continue
            candidate = os.path.join(self.parentdir, entry, input_data_name)
            ma_len = os.path.join(self.parentdir, entry, ma_dir_name,
                                  "_MuscleAnalysis_Length.sto")
            if os.path.exists(candidate) and os.path.exists(ma_len):
                calib_trials.append(entry)
            elif os.path.exists(candidate):
                self._log(f"[Info] CEINMS: skipping '{entry}' as a calibration "
                          f"trial (no muscle_analysis length file).")
        if not calib_trials:
            self._log("[Warning] No CEINMS input data found — calibrating with current trial only.")
            calib_trials = [self.trial]

        self._log(f"[CEINMS 4/6] create calibration setup + cfg (trials={calib_trials})", terminal=True)
        self.create_ceinms_calibration_cfg(calibration_trial_names=calib_trials)
        self.create_ceinms_calibration_setup()

        _out_txt = os.path.join(_cal_dir, "output", "out.txt")
        self._log(f"[CEINMS 5/6] run calibration (session level) — solver output -> {_out_txt}", terminal=True)
        self._log(f"   watch live:  tail -f \"{_out_txt}\"", terminal=True)

        # -- Run calibration --
        start_time = _u.time.time()
        os.chdir(self.path)

        if os.path.exists(self.ceinms_uncalibrated_model):
            _u.ceinms.plot_ceinms_model_parameters(self.ceinms_uncalibrated_model)

        calibrationSetupPath = os.path.abspath(self.ceinms_calibration_setup)

        _u.edit_xml_tag_value(calibrationSetupPath, 'outputDirectory', 'output')
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

        # CEINMS's calibrator drops <opensimModelFile> from the calibrated subject,
        # so CEINMS EXECUTION later fails with "No OpenSim model associated to the
        # subject" (and a cascade of muscle/excitation name mismatches). Re-inject
        # it from the uncalibrated subject — both live in ceinms_calibration/, so
        # the uncalibrated file's relative .osim path is valid for the calibrated one.
        try:
            _cal_tree = _u.ET.parse(self.ceinms_calibrated_model)
            _cal_root = _cal_tree.getroot()
            if _cal_root.find('opensimModelFile') is None:
                _osim_el = _u.ET.parse(self.ceinms_uncalibrated_model).getroot().find('opensimModelFile')
                if _osim_el is not None and (_osim_el.text or '').strip():
                    _new = _u.ET.Element('opensimModelFile')
                    _new.text = _osim_el.text
                    # Schema requires opensimModelFile LAST:
                    # (mtuDefault, mtuSet, dofSet, calibrationInfo, contactModelFile?, opensimModelFile?)
                    _cal_root.append(_new)
                    _cal_tree.write(self.ceinms_calibrated_model, encoding='utf-8', xml_declaration=True)
                    self._log('[Info] re-injected <opensimModelFile> into calibrated subject '
                              '(CEINMS calibrator drops it, breaking execution).', terminal=True)
        except Exception as _e:
            self._log(f'[Warning] could not inject opensimModelFile into calibrated subject: {_e}', terminal=True)

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
        """Run CEINMS execution in whatever MODE this session asks for.

        The mode decides how many solves happen and what the result IS -- one
        curve, a curve plus a sensitivity band, a range with a median, or a
        weighting taken from an L-curve knee. See
        ``bioscout.utils.ceinms.modes`` for the definitions and
        ``ceinms.mode`` in session.yaml for how to pick one.

        This is a dispatcher only. `single` (the default, and what every
        project did before modes existed) calls straight through to
        ``run_ceinms_exe_single`` -- same solve, same folder name, same
        outputs. Every other mode drives that same method once per arm, so
        there is exactly one code path that actually runs CEINMS.
        """
        try:
            from bioscout.utils.ceinms import modes as _modes
        except ImportError:                                  # pragma: no cover
            return self.run_ceinms_exe_single()
        mode = str(getattr(self, "ceinms_mode", None)
                   or getattr(self, "mode", None)
                   or _modes.DEFAULT_MODE).strip().lower()
        if mode in ("single", "optimise"):
            # `optimise` is executed by the CEINMSoptimise path, not here; a
            # trial that reaches execution under that mode still needs its one
            # solve, so it behaves as `single` rather than silently doing
            # nothing.
            return self.run_ceinms_exe_single()
        try:
            return _modes.run(self, self.run_ceinms_exe_single,
                              log=lambda m: self._log(m, terminal=True))
        except _modes.ModeError as e:
            self._log("[Error] CEINMS mode: %s" % e, terminal=True)
            raise

    def run_ceinms_exe_single(self):
        os.chdir(self.path)
        self.load_settings(settingsXML=self.settingsXML)
        # Tag execution logs distinctly from calibration ("CEINMS-exe <trial>"
        # vs "CEINMS-cal <session>"). Set AFTER load_settings so it isn't reset.
        self._log_tag = f"CEINMS-exe {self.trial}"

        # inputData.xml is built once in the CEINMS SETUP stage (create_ceinms_input_data
        # for every trial); only build it here if this trial doesn't have it yet.
        try:
            _inp = os.path.join(self.path, self._layout_paths()['ceinms_input_data'])
        except Exception:
            _inp = os.path.join(self.path, "ceinms", "inputData.xml")
        if not os.path.exists(_inp) or self.replace:
            self.create_ceinms_input_data()
        else:
            self._log("inputData.xml already present (from CEINMS setup) — reusing", terminal=True)

        # Log the analysis window + input files (clickable absolute paths).
        try:
            _tr = self.get_time_range()
        except Exception:
            _tr = None
        self._log(
            f"CEINMS execution — time_range={_tr}\n"
            f"   inputData    : {os.path.abspath(_inp)}\n"
            f"   subject model: {os.path.abspath(os.path.join(self.path, self.ceinms_execution_subject)) if not os.path.isabs(str(self.ceinms_execution_subject)) else self.ceinms_execution_subject}\n"
            f"   EMG (excit.) : {os.path.abspath(os.path.join(self.path, self.emg_filtered_normalised)) if not os.path.isabs(str(self.emg_filtered_normalised)) else self.emg_filtered_normalised}",
            terminal=True)

        if not os.path.exists(self.ceinms_exe_cfg) or self.replace:
            self.create_ceinms_exe_cfg()
        if not os.path.exists(self.ceinms_exe_setup) or self.replace:
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

        # outputDirectory is resolved relative to the setup file (in ceinms/), so
        # use the basename, not the trial-root-relative self.ceinms_exe_dir.
        setup.find('outputDirectory').text = os.path.basename(self.ceinms_exe_out_rel())

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

        # update jra ceinms forces path — TRIAL-ROOT-relative (ceinms/Execution_...),
        # not the setup's outputDirectory text which is relative to ceinms/.
        _exe_out_rel = self.ceinms_exe_out_rel()
        self.update_trial_attribute('jra_forces_ceinms', os.path.join(_exe_out_rel, 'MuscleForces.sto'))

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

        # compare muscle forces & activations across SO / CEINMS / EMG
        try:
            self.plot_ceinms_execution_comparison()
            self._log(f'Plotted CEINMS vs SO vs EMG comparison for trial: {self.trial}')
        except Exception as e:
            self._log(f'[Error] during CEINMS execution comparison plot: {e}')

        # per-channel EMG excitation vs CEINMS muscle activations
        try:
            self.plot_ceinms_emg_activations()
        except Exception as e:
            self._log(f'[Error] during EMG-vs-activations plot: {e}')

    def plot_ceinms_emg_activations(self, save=True, ncol=3):
        """CEINMS validation: per EMG channel, the normalised EMG excitation vs
        the CEINMS activations of the muscles driven by that channel.

        For each channel in ``CEINMSSettings.emg_muscle_mapping`` (channel ->
        [muscles]): gray thick = the normalised EMG excitation; blue = CEINMS
        activations (thin per muscle, thick = mean); red = SO activations (thin
        per muscle, thick = mean). All on a 0-1 axis over the analysis window.
        Colours follow settings.PlottingSettings (utils.plot_style): EMG, CEINMS,
        static_optimisation. Saved to ceinms/emg_vs_activations.png."""
        os.chdir(self.path)
        _c_emg = _u.plot_style('emg')['color']
        _c_ce  = _u.plot_style('ceinms')['color']
        _c_so  = _u.plot_style('static_optimisation')['color']
        emg = _u.load_any_data_file(self.emg_filtered_normalised)
        exe_dir = os.path.dirname(os.path.join(self.path, self.jra_forces_ceinms))
        act = _u.load_any_data_file(os.path.join(exe_dir, 'Activations.sto'))
        te = pd.to_numeric(emg['time'], errors='coerce').to_numpy(float)
        ta = pd.to_numeric(act['time'], errors='coerce').to_numpy(float)
        t0, t1 = float(np.nanmin(ta)), float(np.nanmax(ta))
        try:   # static-optimisation activations (optional overlay, green)
            so = _u.load_any_data_file(self.so_activations)
            ts = pd.to_numeric(so['time'], errors='coerce').to_numpy(float)
        except Exception:
            so, ts = None, None

        mapping = self.emg_channel_map()
        chans = [c for c in mapping if c in emg.columns]
        if not chans:
            self._log('[plot_ceinms_emg_activations] no mapped EMG channels found.')
            return None, None

        nrow = int(np.ceil(len(chans) / ncol))
        fig, axg = plt.subplots(nrow, ncol, figsize=(4.7 * ncol, 2.5 * nrow), squeeze=False)
        for i, ch in enumerate(chans):
            a = axg[i // ncol][i % ncol]
            m = (te >= t0) & (te <= t1)
            a.plot(te[m], pd.to_numeric(emg[ch], errors='coerce').to_numpy(float)[m],
                   color=_c_emg, lw=2.0, zorder=4)
            muses = [mu for mu in mapping[ch] if mu in act.columns]
            acts = []
            for mu in muses:
                y = pd.to_numeric(act[mu], errors='coerce').to_numpy(float)
                acts.append(y)
                a.plot(ta, y, color=_c_ce, lw=0.6, alpha=0.35, zorder=2)
            if acts:
                a.plot(ta, np.mean(acts, axis=0), color=_c_ce, lw=2.0, zorder=4)
            if so is not None:   # SO activations for the same muscles
                sos = [pd.to_numeric(so[mu], errors='coerce').to_numpy(float)
                       for mu in mapping[ch] if mu in so.columns]
                for y in sos:
                    a.plot(ts, y, color=_c_so, lw=0.6, alpha=0.3, zorder=1)
                if sos:
                    a.plot(ts, np.mean(sos, axis=0), color=_c_so, lw=2.0, zorder=3)
            # 'EMG_Channels_EMG09_gast_med_l' and 'Voltage_EMG9_gast_med_l'
            # both -> 'gast_med_l'
            label = re.sub(r'^.*?EMG_?\d+_', '', str(ch))
            a.set_title(label, fontsize=8, pad=11)
            a.text(0.5, 1.005, f"({len(muses)} muscles)", transform=a.transAxes,
                   ha='center', va='bottom', fontsize=6.3, color='0.35')
            a.set_ylim(-0.03, 1.03); a.set_xlim(t0, t1)
            a.tick_params(labelsize=7); a.margins(x=0)
        for j in range(len(chans), nrow * ncol):
            axg[j // ncol][j % ncol].axis('off')
        h = [plt.Line2D([], [], color=_c_emg, lw=2, label='EMG excitation (normalised)'),
             plt.Line2D([], [], color=_c_so, lw=2, label='SO activation (mean; thin = muscles)'),
             plt.Line2D([], [], color=_c_ce, lw=2, label='CEINMS activation (mean; thin = muscles)')]
        fig.legend(handles=h, loc='lower center', ncol=3, fontsize=9, frameon=False)
        fig.suptitle(f"{self.trial} — EMG excitation vs CEINMS & SO muscle activations", fontsize=13)
        fig.tight_layout(rect=[0, 0.04, 1, 0.98])
        if save:
            os.makedirs(exe_dir if os.path.isdir(exe_dir) else os.path.dirname(exe_dir), exist_ok=True)
            _cdir = os.path.join(self.path, os.path.dirname(self.ceinms_exe_dir) or self.ceinms_exe_dir)
            os.makedirs(_cdir, exist_ok=True)
            out = os.path.join(_cdir, "emg_vs_activations.png")
            fig.savefig(out, dpi=130)
            self._log(f'Saved EMG-vs-activations figure: {out}')
        return fig, axg

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
            _u.ceinms.create_ceinms_cfg(ceinmsModelPath=self.ceinms_execution_subject, alpha=self.alpha, beta=self.beta, gamma=self.gamma, dofSet=' '.join(self.DofSet),excitationGeneratorFilePath=self.ceinms_excitation_generator, outputPath=self.ceinms_exe_cfg)
        
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
        """Append the SO force file's NON-muscle columns (pelvis residuals
        FX..MZ, coordinate reserves, GRF) to the CEINMS MuscleForces file, so the
        JointReaction `forces_file` has the FULL actuator set. Without the
        residual/reserve actuators the JRA can't balance the dynamics and dumps the
        imbalance into the hip (blowing the contact force up ~100x). Reads the SO
        force file explicitly (self.so_forces) — NOT self.jra_forces, which on a
        CEINMS-loaded trial resolves to the CEINMS forces (=> nothing to add)."""
        def _abs(p):
            return p if os.path.isabs(p) else os.path.join(self.path, p)
        try:
            so_forces = _u.load_any_data_file(_abs(self.so_forces))
            ceinms_forces = _u.load_any_data_file(_abs(self.jra_forces_ceinms))
        except Exception as e:
            self._log(f'[Error] loading SO or CEINMS forces for adding columns: {e}', terminal=True)
            return False
        if so_forces is None or ceinms_forces is None:
            self._log(f'[Error] SO ({_abs(self.so_forces)}) or CEINMS forces not readable; '
                      f'JRA residual/reserve columns NOT added (JCF will be wrong).', terminal=True)
            return False

        # Non-muscle SO columns missing from the CEINMS forces (residuals/reserves/GRF).
        missing_columns = [c for c in so_forces.columns
                           if c != 'time' and c not in ceinms_forces.columns]
        n = min(len(so_forces), len(ceinms_forces))
        updated_forces = ceinms_forces.iloc[:n].copy()
        for col in missing_columns:
            updated_forces[col] = so_forces[col].to_numpy()[:n]

        _u.write_sto_file(updated_forces, _abs(self.jra_forces_ceinms))
        self._log(f'[Success] added {len(missing_columns)} SO reserve/residual/GRF columns '
                  f'to CEINMS forces (for balanced JRA)', terminal=True)
        return True

    def plot_ceinms_execution_comparison(self):
        """CEINMS-vs-SO muscle results in the SO_results.png layout.

        One subplot per muscle: FORCE in red (CEINMS solid, SO dashed; N on the
        left axis) and ACTIVATION in grey (CEINMS solid, SO dashed; 0-1 on the
        right axis), with the normalised EMG shaded grey for muscles that have a
        measured channel. R² of each model's activation vs EMG is shown in the
        title (C=CEINMS, S=SO). Saved into ``ceinms/`` as
        ``a{alpha}_b{beta}_g{gamma}_results.png`` plus a companion muscle-groups
        figure ``a{alpha}_b{beta}_g{gamma}_muscle_groups.png``.
        """
        os.chdir(self.path)
        exe_dir = os.path.dirname(os.path.join(self.path, self.jra_forces_ceinms))
        ce_f = _u.load_any_data_file(os.path.join(exe_dir, 'MuscleForces.sto'))
        ce_a = _u.load_any_data_file(os.path.join(exe_dir, 'Activations.sto'))
        so_f = _u.load_any_data_file(self.so_forces)
        so_a = _u.load_any_data_file(self.so_activations)
        try:
            emg = _u.load_any_data_file(self.emg_filtered_normalised)
        except Exception:
            emg = None

        tr = self.get_time_range()

        def _crop(df):
            return (df[(df['time'] >= tr[0]) & (df['time'] <= tr[1])]
                    if (df is not None and 'time' in df.columns) else df)

        ce_f, ce_a, so_f, so_a, emg = map(_crop, (ce_f, ce_a, so_f, so_a, emg))

        try:
            muscles = [m for m in self.get_muscle_list()
                       if m in ce_f.columns and m in so_f.columns]
        except Exception:
            muscles = [c for c in ce_f.columns if c != 'time' and c in so_f.columns]
        if not muscles:
            self._log('[plot_ceinms_execution_comparison] no common muscles.')
            return None, None

        rev = self._emg_reverse_map()
        te = pd.to_numeric(emg['time'], errors='coerce').to_numpy(float) if emg is not None else None
        tcf = pd.to_numeric(ce_f['time'], errors='coerce').to_numpy(float)
        tsf = pd.to_numeric(so_f['time'], errors='coerce').to_numpy(float)
        tca = pd.to_numeric(ce_a['time'], errors='coerce').to_numpy(float)
        tsa = pd.to_numeric(so_a['time'], errors='coerce').to_numpy(float)
        t0, t1 = tr

        def _r2(t_act, act, y):
            ei = np.interp(t_act, te, y)
            v = np.isfinite(ei) & np.isfinite(act)
            if v.sum() > 3 and np.std(ei[v]) > 1e-9 and np.std(act[v]) > 1e-9:
                return float(np.corrcoef(ei[v], act[v])[0, 1] ** 2)
            return None

        ncol = 8
        nrow = int(np.ceil(len(muscles) / ncol))
        fig, axg = plt.subplots(nrow, ncol, figsize=(2.6 * ncol, 1.7 * nrow), squeeze=False)
        for i, mu in enumerate(muscles):
            a = axg[i // ncol][i % ncol]; a2 = a.twinx()
            ch = rev.get(mu); r2c = r2s = None
            if emg is not None and ch and ch in emg.columns:
                y = pd.to_numeric(emg[ch], errors='coerce').to_numpy(float)
                m = (te >= t0) & (te <= t1)
                a2.fill_between(te[m], 0, y[m], color='0.6', alpha=0.35, zorder=1)
                if mu in ce_a.columns:
                    r2c = _r2(tca, pd.to_numeric(ce_a[mu], errors='coerce').to_numpy(float), y)
                if mu in so_a.columns:
                    r2s = _r2(tsa, pd.to_numeric(so_a[mu], errors='coerce').to_numpy(float), y)
            # forces (red): CEINMS solid, SO dashed
            a.plot(tcf, pd.to_numeric(ce_f[mu], errors='coerce'), color='tab:red', lw=1.0, zorder=3)
            if mu in so_f.columns:
                a.plot(tsf, pd.to_numeric(so_f[mu], errors='coerce'),
                       color='tab:red', ls='--', lw=0.9, zorder=3)
            a.tick_params(axis='y', labelsize=5, colors='tab:red')
            # activations (grey): CEINMS solid, SO dashed
            if mu in ce_a.columns:
                a2.plot(tca, pd.to_numeric(ce_a[mu], errors='coerce'), color='0.35', lw=1.0, zorder=2)
            if mu in so_a.columns:
                a2.plot(tsa, pd.to_numeric(so_a[mu], errors='coerce'),
                        color='0.35', ls='--', lw=0.9, zorder=2)
            a2.set_ylim(0, 1.05); a2.tick_params(axis='y', labelsize=5, colors='0.35')
            _rt = ''
            if r2c is not None or r2s is not None:
                _rt = '  R²' + (f' C={r2c:.2f}' if r2c is not None else '') \
                             + (f' S={r2s:.2f}' if r2s is not None else '')
            a.set_title(mu + _rt, fontsize=6.0); a.set_xlim(t0, t1)
            a.tick_params(axis='x', labelsize=5); a.margins(x=0)
        for j in range(len(muscles), nrow * ncol):
            axg[j // ncol][j % ncol].axis('off')

        h = [plt.Line2D([], [], color='tab:red', lw=1.5, label='force (N, left axis)'),
             plt.Line2D([], [], color='0.35', lw=1.5, label='activation (0-1, right axis)'),
             plt.Line2D([], [], color='0.6', lw=6, alpha=0.4, label='EMG (shaded, if measured)'),
             plt.Line2D([], [], color='0.2', lw=1.3, ls='-', label='CEINMS (solid)'),
             plt.Line2D([], [], color='0.2', lw=1.3, ls='--', label='SO (dashed)')]
        fig.legend(handles=h, loc='lower center', ncol=5, fontsize=9, frameon=False)
        _tag = f"a{self.alpha}_b{self.beta}_g{self.gamma}"
        fig.suptitle(f"CEINMS vs SO results  ({_tag})", fontsize=14)
        fig.tight_layout(rect=[0, 0.02, 1, 0.985])
        _ceinms_dir = os.path.join(self.path,
                                   os.path.dirname(self.ceinms_exe_dir) or self.ceinms_exe_dir)
        os.makedirs(_ceinms_dir, exist_ok=True)
        out = os.path.join(_ceinms_dir, f"{_tag}_results.png")
        fig.savefig(out, dpi=130); plt.close(fig)
        self._log(f'Saved CEINMS results figure: {out}', terminal=True)

        # companion muscle-groups figure (CEINMS solid + SO dashed + EMG shaded)
        try:
            self._plot_muscle_groups(
                [('CEINMS', ce_f, ce_a, '-'), ('SO', so_f, so_a, '--')], emg,
                os.path.join(_ceinms_dir, f"{_tag}_muscle_groups.png"),
                f"CEINMS vs SO — muscle groups ({_tag})")
        except Exception as _e:
            self._log(f'[Warning] CEINMS muscle-groups plot failed: {_e}')
        return out

    #--- Plot ceinms
    def plot_ceinms_calibration_results(self):

        try:
            ceinmsTorquesFile = os.path.join(self.ceinms_calibration_dir, 'Moments_inputData.csv')
            _u.ceinms.plot_moments_calibration_results(momentResultsCSV=ceinmsTorquesFile)
            self._log(f'[Success] Plotted CEINMS calibration results for trial: {self.trial}')
        except Exception as e:
            self._log(f'[Error] during plotting CEINMS calibration results: {e}')

    def plot_ceinms_vs_so_muscle_moments(self):
        from plotly.subplots import make_subplots
        import plotly.graph_objects as go

        ik_columns = ['hip_flexion_r', 'hip_adduction_r', 'hip_rotation_r', 'knee_angle_r', 'ankle_angle_r']
        id_columns = ['hip_flexion_r_moment', 'hip_adduction_r_moment', 'hip_rotation_r_moment', 'knee_angle_r_moment', 'ankle_angle_r_moment']

        id = _u.load_any_data_file(os.path.join(self.path, self.id))
        so_forces = _u.load_any_data_file(os.path.join(self.path, self.so_forces))
        ceinms_forces = _u.load_any_data_file(os.path.join(self.path, self.jra_forces_ceinms))

        fig, ax = plt.subplots(nrows=len(ik_columns), ncols=2, figsize=(28, 16))
        fontsize = 25

        fig_int = make_subplots(rows=len(ik_columns), cols=2, shared_xaxes=True,
                                subplot_titles=[f"{dof} - SO" if i % 2 == 0 else f"{dof} - CEINMS"
                                                for dof in ik_columns for i in range(2)])

        for count, dof in enumerate(ik_columns):
            ma = _u.load_any_data_file(os.path.join(self.path, self.ma, f'_MuscleAnalysis_MomentArm_{dof}.sto'))

            muscle_list = [col for col in so_forces.columns if col != 'time']
            muscles = _u.openSim.find_non_zero_mom_arm_muscles(ma, muscle_list)
            print(f"Non-zero moment arm muscles for {dof}: {muscles}")


# --- subject video/anthropometry profile (defined in subject_profile.py) ------
# Co-located with Subject so every subject-side model is reachable straight from
# the analysis module, e.g. `from bioscout.utils.analysis import SubjectProfile`.
# (Distinct data model from Subject: anthropometry, segment fractions, pose
# calibration and per-task detection settings for the video pipeline.)
from .subject_profile import (  # noqa: E402,F401
    SubjectProfile, SubjectStore, ProjectSubjectStore, DEFAULT_SEGMENT_FRACTIONS,
)
