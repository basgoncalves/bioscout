"""session.yaml — the per-session configuration, read and written.

Everything that turns the YAML file into Python and back: :class:`SessionSpec`
/ :class:`Model`, ``read_session_yaml`` / ``write_session_yaml`` /
``scaffold_session_yaml``, the strict loader that refuses duplicate keys, and
the resolvers for the named blocks inside it (EMG maps, EMG gains, CEINMS
calibration configs, per-iteration settings).

No OpenSim, no Analyse: importing this is cheap.
"""
from __future__ import annotations

import os
import re
import glob
import shutil
import time
import json
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
from xml.etree import ElementTree as ET
from pathlib import Path

try:
    import yaml  # PyYAML
except Exception:
    yaml = None

# ===========================================================================
# CONFIG  (inlined from utils/session_config.py)
# ===========================================================================
"""Session-centric data model (BioScout 2.x restructuring).

A **session** owns its raw motion data (``c3dfiles/``) and one or more **model
iterations** (``models/*.osim``). Every model is analysed over the SAME trials
and compared, so a session is the unit of organisation — NOT the model.

  * ``Model``       — one model iteration + its (optional) scale recipe.
  * ``SessionSpec`` — subject/session/path + shared config + ``models[]`` + per-trial windows.
  * ``read_session_yaml`` / ``write_session_yaml`` — the single ``session.yaml`` per session.

This module is ADDITIVE: it does not change the existing pipeline. Phases 2+
wire it into ``Analyse`` / ``run_pipeline``.
"""

import os
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from xml.etree import ElementTree as ET


# ---------------------------------------------------------------------------
@dataclass
class Model:
    """One model iteration within a session: ONE scaled model.

    Field names are session.yaml's iteration keys (see ``ITERATION_KEYS``).
    File fields are stored as written -- relative to the iteration folder."""
    name: str
    model_generic: Optional[str] = None    # generic .osim that gets scaled
    model_scaled: Optional[str] = None     # THE scaled model (CEINMS as is; SO x mvic_factor)
    markerset: Optional[str] = None        # marker set .xml this model is scaled with
    so_actuators: Optional[str] = None     # SO actuator .xml (replaces the model ones)
    so_residuals_from_id: bool = False     # raise pelvis residual optimal_force to the peak ID residual
    engine: str = "opensim"                # opensim | pyosim: what runs scaling, IK, ID, MA, SO and JRA
    label: Optional[str] = None
    color: str = "black"
    group: Optional[str] = None
    # --- scale recipe (model creation only) ---
    muscle_opt: bool = True                # Modenese2015 muscle-parameter optimisation
    static_trial: Optional[str] = None
    marker_weights: Dict[str, float] = field(default_factory=dict)
    ik_weights: Dict[str, float] = field(default_factory=dict)   # IK weights {marker or body: w}
    preserve_mass_distribution: bool = True
    linear_scaling: bool = True            # ScaleTool ModelScaler (dimensional scaling)
    marker_placer: bool = False            # ScaleTool MarkerPlacer (place markers to static)
    mvic_factor: Optional[float] = None
    fmax_scaling: Optional[str] = None     # "handsfield" | "handsfield_sprinter"
    height: Optional[float] = None         # m, for fmax_scaling
    opt_neval: Optional[int] = None
    emg_map: Optional[str] = None          # NAME of a mapping under the session-wide
                                           # emg_map; only needed when several exist
    calibration: Optional[str] = None      # NAME of a config under the session-wide
                                           # calibration block; same rules as emg_map

    def __post_init__(self):
        if self.label is None:
            self.label = self.name


# ---------------------------------------------------------------------------
@dataclass
class SessionSpec:
    """One session: identity + shared config + its model iterations + per-trial
    windows. Built from a ``session.yaml`` (see ``read_session_yaml``)."""
    subject: str
    session: str = ""
    path: Optional[str] = None             # absolute session folder
    project_dir: Optional[str] = None      # as written: relative to the session folder
    body_mass: Optional[float] = None
    static_trial: Optional[str] = None     # session-wide static trial (scale + body mass)
    setup_folder: Optional[str] = None
    markerset: Optional[str] = None
    c3d_source: Optional[str] = None       # reference c3d folder to import trials FROM
    models: List[Model] = field(default_factory=list)
    emg_muscle_mapping: Dict[str, list] = field(default_factory=dict)  # the session DEFAULT map
    emg_muscle_mappings: Dict[str, Dict[str, list]] = field(default_factory=dict)
                                           # every NAMED map, {} when the file is flat
    default_emg_map: Optional[str] = None  # which name iterations get when silent
    calibrations: Dict[str, Dict[str, str]] = field(default_factory=dict)
                                           # named CEINMS calibration configs
    default_calibration: Optional[str] = None
    ceinms: Dict[str, str] = field(default_factory=dict)   # alpha/beta/gamma...
    # session-wide trial selections (which trials drive session-level steps)
    normalisation_trials: List[str] = field(default_factory=list)  # EMG MVC normalisation
    calibration_trials: List[str] = field(default_factory=list)    # CEINMS calibration
    trials: Dict[str, dict] = field(default_factory=dict)  # {trial: {time_range, events}}

    # -- convenience --------------------------------------------------------
    def get_model(self, name) -> Optional[Model]:
        return next((m for m in self.models if m.name == name), None)

    def emg_map_for(self, model=None) -> Dict[str, list]:
        """``{channel: [muscles]}`` for one model iteration.

        Named a model, this raises when that model's selector is missing or
        unknown. Named nothing it returns the SESSION default — the same value
        as ``emg_muscle_mapping``, falling back to the first map rather than
        raising, because the strict gate is ``load_session_yaml`` and this is
        a convenience view over an already-validated spec.
        """
        if not self.emg_muscle_mappings:
            return dict(self.emg_muscle_mapping)
        m = self.get_model(model) if model else None
        name = (m.emg_map if m and m.emg_map else
                self.default_emg_map or
                ("default" if "default" in self.emg_muscle_mappings else None) or
                (next(iter(self.emg_muscle_mappings))
                 if len(self.emg_muscle_mappings) == 1 else None))
        if name is None:
            if model is None:
                return dict(next(iter(self.emg_muscle_mappings.values())))
            raise ValueError(
                f"emg_map defines {sorted(self.emg_muscle_mappings)} and model "
                f"{model!r} does not select one.")
        if name not in self.emg_muscle_mappings:
            raise ValueError(f"emg_map {name!r} is not defined. Available: "
                             f"{sorted(self.emg_muscle_mappings)}.")
        return dict(self.emg_muscle_mappings[name])

    def model_names(self) -> List[str]:
        return [m.name for m in self.models]

    @property
    def c3d_dir(self) -> Optional[str]:
        from .layout import c3d_root
        return c3d_root(self.path) if self.path else None

    @property
    def models_dir(self) -> Optional[str]:
        return os.path.join(self.path, "models") if self.path else None

    def trial_dir(self, trial, model=None) -> Optional[str]:
        """Trial folder, or the per-MODEL sub-folder inside it."""
        if not self.path:
            return None
        base = os.path.join(self.path, trial)
        return os.path.join(base, model) if model else base


# =========================================================================
# YAML  (inlined from utils/session_yaml.py)
# =========================================================================
"""YAML session configuration for BioScout (2.x session-centric layout).

Human-authored config is YAML; the tool-facing files (OpenSim/CEINMS setups,
.osim) stay XML because those are *generated*, never hand-edited. This module
reads/writes a ``session.yaml`` into the SAME :class:`SessionSpec` / :class:`Model`
dataclasses. ``session.yaml`` is the only session config format.

A session owns its RAW data once (``trials/``) and one or more ITERATIONS (model
variants) analysed over the same trials. Each iteration carries its own scale
recipe (generic model, muscle-optimiser N, MVIC factor, marker weights) so it can
be rebuilt and labelled by the summary.

Example ``session.yaml``::

    subject: Athlete_03
    session: "25_03_31"
    project_dir: ../../..                # relative to this file
    body_mass: 89.9
    static_trial: Static_01
    calibration_trials: [Walking_02, Squat_BW_01]
    normalisation_trials: all            # or an explicit list
    emg_map:
      EMG_Channels_EMG01_vast_lat_l: [vaslat_l, vasmed_l, vasint_l]
      # Keys are the EXPORTED column names of inputs/emg.mot -- the c3d's ANALOG
      # labels with '.' and spaces replaced by '_'. A session captured with
      # 'Voltage.EMG1_vast_lat_l' therefore uses 'Voltage_EMG1_vast_lat_l'.
      # Since 2.4.1 this map is authoritative for the session's trials and
      # overrides settings.BatchSettings.emg_muscle_mapping, so two sessions
      # with different electrode sets can live in one project.
    emg_gain:                            # optional, applied AFTER normalisation
      EMG_Channels_EMG09_gast_med_l: 0.70
      # A per-channel multiplier on the SESSION-NORMALISED excitation. Scaling
      # the raw emg.mot instead is an exact no-op -- the session max scales with
      # it. Flat and session-wide on purpose: it rewrites one file that every
      # iteration reads, so it cannot vary per iteration. A channel name not in
      # the data raises rather than passing the signal through unscaled.
    ceinms: {alpha: 10, beta: 1, gamma: 1000}
    trials:
      Walking_02: {type: walking, time_range: [0.10, 1.91]}
      Squat_BW_01: {type: squat}
    iterations:
      cateli:
        # files: relative to the iteration folder <session>/3_iterations/cateli
        model_generic: ../../../../../generic models/Catelli.osim
        model_scaled: ../../../../../models/personalised/Athlete_03/25_03_31/cateli_scaled_opt_N10.osim
        markerset: ../../../../../setup/markers_powerlifter.xml
        opt_neval: 10
        mvic_factor: 3.0
        static_trial: Static_01
        marker_weights: {pelvis: 10.0, femur_r: 1.0}
        label: "Scaled (Cateli)"
        color: green
        group: generic

``emg_map`` may instead hold SEVERAL NAMED maps, with each iteration naming
the one it runs with. How electrodes are grouped onto muscles is a modelling
choice, like the generic model is, so it belongs in an iteration rather than
in a whole duplicated session::

    emg_map:
      narrow:
        EMG_Channels_EMG09_gast_med_l: [gasmed_l, gaslat_l]
        # ... plus the other nine channels
      triceps:
        EMG_Channels_EMG09_gast_med_l: [gasmed_l, gaslat_l, soleus_l]
      wide:
        EMG_Channels_EMG09_gast_med_l: [gasmed_l, gaslat_l, soleus_l, perlong_l]
    default_emg_map: narrow      # optional: what iterations that stay silent get
    iterations:
      cateli_narrow:  {generic: Catelli.osim, emg_map: narrow,  ...}
      cateli_triceps: {generic: Catelli.osim, emg_map: triceps, ...}

The two forms are told apart by value type — a channel maps to a LIST of
muscles, a named map to a MAPPING of channels — so every existing flat file
keeps working untouched. With more than one map and no way to pick (no
iteration selector, no ``default_emg_map``, no map called ``default``) loading
FAILS rather than guessing: a silently wrong electrode set leaves no trace in
the output. See :func:`emg_maps` / :func:`resolve_emg_map`.

``calibration`` works the same way for CEINMS's parameter bounds, which used to
be one global value in ``settings.py`` — so sweeping a bound meant copied
sessions plus a runtime monkeypatch of the settings module::

    calibration:
      wide:  {optimalFiberLength: "0.5 3", tendonSlackLength: "0.5 3"}
      tight: {optimal_fiber_length: [0.75, 1.25], tendon_slack_length: "0.75 1.25"}
    default_calibration: wide
    iterations:
      cateli__tight: {generic: Catelli.osim, calibration: tight, ...}

Both spellings of every parameter are accepted and canonicalised — settings.py
declared ``optimal_fiber_length`` while the XML writer read
``optimalFiberLength``, so four of the six ranges were unreachable and editing
them silently did nothing. An override is PARTIAL: a config naming one bound
leaves the rest to settings.py. See :func:`calibration_configs` /
:func:`resolve_calibration`.
"""

import os
from typing import Optional

try:
    import yaml  # PyYAML
except Exception as _e:                      # pragma: no cover
    yaml = None
    _YAML_IMPORT_ERROR = _e



# ---------------------------------------------------------------------------
def _require_yaml():
    if yaml is None:
        raise ImportError(
            "PyYAML is required for session.yaml support. Install it with "
            "`pip install pyyaml` (or `conda install pyyaml`)."
        ) from _YAML_IMPORT_ERROR


def _as_list(v):
    """Accept 'a b c', ['a','b'], or None -> list[str]. 'all'/None -> []."""
    if v is None:
        return []
    if isinstance(v, str):
        if v.strip().lower() == "all":
            return []                        # empty = "all trials" by convention
        return v.replace(",", " ").split()
    return [str(x) for x in v]


#: Strings a human writes in YAML meaning "no". PyYAML already turns bare
#: `false`/`no`/`off` into a bool, but a QUOTED "false" -- or a value that
#: reached us from an XML round-trip -- arrives as a string, and `bool("false")`
#: is True. A silent True there would run a calibration the session asked to
#: skip, so the string spellings are handled explicitly.
_FALSEY = ("false", "0", "no", "off", "none", "", "uncalibrated")


def yaml_bool(v, default=True):
    """A session.yaml flag as a bool, tolerating quoted strings."""
    if v is None:
        return default
    if isinstance(v, str):
        return v.strip().lower() not in _FALSEY
    return bool(v)


# ---------------------------------------------------------------------------
# What is each trial FOR? — per-trial flags, with the legacy lists as fallback
# ---------------------------------------------------------------------------
#: The per-trial keys that replaced the top-level ``calibration_trials:`` and
#: ``normalisation_trials:`` lists (2026-08-19)::
#:
#:     trials:
#:       HAB1:
#:         type: emg_only
#:         emg_normalisation: true
#:       SquatNorm4:
#:         type: squat
#:         calibration: true
#:
#: A trial's facts belong in the trial's own block. The lists could name a
#: trial that had no block at all — a dangling reference the session editor
#: has a red flag for precisely because the schema allowed it — and answering
#: "what is this trial for?" meant reading three places. Both forms are
#: accepted for one release: where a trial says nothing, the lists still
#: decide, so no session breaks on the day this lands.
TRIAL_ROLE_KEYS = {"calibration": "calibration_trials",
                   "emg_normalisation": "normalisation_trials"}


def _trial_role(cfg, role):
    """Trials with ``role`` (``"calibration"`` / ``"emg_normalisation"``).

    Per-trial flags win where present; the legacy top-level list supplies the
    rest. Order follows ``trials:`` for flagged trials and the list's own
    order for legacy ones — calibration order matters (the first trial is the
    driver), which is the one thing the lists were genuinely better at.
    """
    trials = cfg.get("trials") or {}
    flagged, refused = [], set()
    for name, meta in trials.items():
        v = (meta or {}).get(role)
        if v is None:
            continue
        (flagged.append(name) if yaml_bool(v) else refused.add(name))
    legacy = [n for n in _as_list(cfg.get(TRIAL_ROLE_KEYS[role]))
              if n not in refused and n not in flagged]
    return flagged + legacy


def calibration_trial_names(cfg):
    """Trials that calibrate CEINMS, per-trial `calibration:` first."""
    return _trial_role(cfg, "calibration")


def normalisation_trial_names(cfg):
    """Trials that feed the session EMG maximum, per-trial
    `emg_normalisation:` first."""
    return _trial_role(cfg, "emg_normalisation")


# ---------------------------------------------------------------------------
# emg_map: one flat map, or several NAMED maps selected per iteration
# ---------------------------------------------------------------------------
#: session.yaml key naming which mapping iterations use when they don't say.
DEFAULT_EMG_MAP_KEY = "default_emg_map"


def _raw_emg_map(cfg):
    """The `emg_map` block as authored (legacy alias `emg_muscle_mapping`)."""
    if not isinstance(cfg, dict):
        return {}
    raw = cfg.get("emg_map", cfg.get("emg_muscle_mapping"))
    return raw if isinstance(raw, dict) else {}


def _iteration_blocks(cfg) -> Dict[str, dict]:
    """``{name: block}`` for `iterations` in either authored shape.

    `iterations` (alias `models`) may be a mapping or a list of blocks each
    carrying their own `name`, exactly as ``read_session_yaml`` accepts them.
    """
    if not isinstance(cfg, dict):
        return {}
    its = cfg.get("iterations", cfg.get("models")) or {}
    if isinstance(its, dict):
        return {str(k): (v if isinstance(v, dict) else {}) for k, v in its.items()}
    out = {}
    for m in its or []:
        if isinstance(m, dict) and m.get("name") is not None:
            out[str(m["name"])] = m
    return out


# ---------------------------------------------------------------------------
# Iteration keys — ONE set of names, used by session.yaml AND by Iteration
# ---------------------------------------------------------------------------
#: The iteration keys that are FILES (relative to the iteration folder).
ITERATION_FILE_KEYS = ("model_generic", "model_scaled", "markerset", "so_actuators",
                       "so_actuators_template", "scale_tool")

#: Old spellings, still read (with a warning) and renamed to the key above.
#: The two old model keys collapse into ``model_scaled`` (see normalise_iterations).
ITERATION_KEY_RENAMES: Dict[str, str] = {
    "generic": "model_generic",
    "generic_model": "model_generic",
    "ceinms_model": "model_scaled",
    "model_ceinms": "model_scaled",
    "so_model": "model_scaled",
    "model": "model_scaled",
    "session_model": "model_scaled",
}

#: Keys that no longer mean anything, and what replaces them.
ITERATION_KEYS_REMOVED: Dict[str, str] = {
    "prescaled": "leave out model_generic and set model_scaled to the given model",
}


def yaml_key_line(path, key):
    """1-based line of ``key`` in a YAML file, or None. ``key`` is dotted for
    nested keys: ``"body_mass"``, ``"iterations.gpk.mvic_factor"``,
    ``"trials.Walking_01.time_range"``. Stops at the deepest key that exists."""
    _require_yaml()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            node = yaml.compose(fh, Loader=yaml.SafeLoader)
    except Exception:                                          # noqa: BLE001
        return None
    line = None
    for part in str(key).split("."):
        if node is None or not isinstance(node, yaml.MappingNode):
            break
        hit = next(((k, v) for k, v in node.value if str(k.value) == part), None)
        if hit is None:
            break
        line, node = hit[0].start_mark.line + 1, hit[1]
    return line



# ---------------------------------------------------------------------------
# The Python face of session.yaml. Each class below lists the keys of one part
# of the file, one line per key, in the file's own words: the name, its type
# and default, what it means. Session / Iteration inherit them and fill them
# from the file when it is read, so ``session.body_mass`` is the ``body_mass:``
# line of that session's session.yaml, and Ctrl+click on it lands HERE.
# ``.source(key)`` gives the clickable ``<path>/session.yaml:<line>`` of a value.
# Add a key: one line here. It is then read, documented and autocompleted.
# ---------------------------------------------------------------------------
def measured_side_of(cfg) -> str:
    """``"l"``, ``"r"`` or ``"both"``: the leg a session is about.

    session.yaml ``measured_side: l|r|both``. It says which leg the session's
    question is asked of -- the instrumented implant, the leg carrying the EMG,
    the injured leg -- not why. ``l`` / ``r`` restricts movement detection
    (strides, plate validity) and every per-leg analysis to that leg; ``both``
    (the default, also when the key is absent) keeps the two.

    ``implanted_side`` is the old name of the same key and is still read, so a
    session written before the rename behaves as it did.
    """
    cfg = cfg or {}
    v = cfg.get("measured_side")
    if v in (None, ""):
        v = cfg.get("implanted_side")
    v = str(v or "").strip().lower()
    if v in ("l", "left"):
        return "l"
    if v in ("r", "right"):
        return "r"
    return "both"


def session_measured_side(session_dir) -> str:
    """:func:`measured_side_of` straight from ``<session_dir>/session.yaml``."""
    try:
        import yaml as _yaml
        with open(os.path.join(str(session_dir), "session.yaml"), encoding="utf-8") as _f:
            return measured_side_of(_yaml.safe_load(_f) or {})
    except Exception:
        return "both"


class SessionKeys:
    """session.yaml, top level. ``session.<key>``; any other key in the file
    works too (``session.implanted_side``), just not autocompleted."""

    subject: str = ""                        # subject id (default: folder above the session)
    session: str = ""                        # session id (default: the session folder name)
    project_dir: str = ""                    # the project, ABSOLUTE (written relative to this file)
    body_mass: Optional[float] = None        # kg
    height: Optional[float] = None           # m (session default for fmax_scaling)
    static_trial: Optional[str] = None       # trial every iteration scales from
    setup_folder: Optional[str] = None       # OLD name of setup_dir (still read)
    models_dir: Optional[str] = None         # models root, relative to project_dir (ABSOLUTE once read);
                                             # iterations' model_generic / model_scaled are relative to it
    setup_dir: Optional[str] = None          # setup-files root, relative to project_dir (ABSOLUTE once
                                             # read); iterations' markerset / so_actuators are relative to it
    c3d_source: Optional[str] = None         # where the c3d files are imported from
    trials: dict = {}                        # {trial: {type, side, time_range, events, ...}}
    calibration_trials: list = []            # CEINMS calibrates on these (per-trial flags, then list)
    normalisation_trials: list = []          # EMG is normalised over these (idem)
    emg_map: dict = {}                       # channel -> muscles (one map, or several named ones)
    ceinms: dict = {}                        # alpha/beta/gamma, mode, calibrated ...
    ik_weights: dict = {}                    # IK (motion) weights {marker or body: w}; 0 = not tracked
    marker_aliases: dict = {}                # expected marker name -> this lab's name
    measured_side: str = "both"              # l | r | both: the leg this session is about (the
                                             # instrumented one, the one with EMG, the injured
                                             # one...). l/r = detection and analysis for that leg only
    scale_measurements: list = []            # ScaleTool MeasurementSet (replaces bioscout's default spec)

    # -- filled from the file ------------------------------------------------
    @property
    def _cfg(self) -> dict:
        return self.__dict__.get("_cfg_data") or {}

    @_cfg.setter
    def _cfg(self, value):
        self.__dict__["_cfg_data"] = value or {}
        self._fill_keys()

    def _fill_keys(self):
        cfg, d = self._cfg, self.__dict__
        sdir = os.path.abspath(str(self.session_dir))
        for k in SESSION_KEYS:
            v = cfg.get(k)
            d[k] = dict(v or {}) if isinstance(getattr(type(self), k), dict) else v
        d["measured_side"] = measured_side_of(cfg)
        d["subject"] = str(cfg.get("subject") or os.path.basename(os.path.dirname(sdir)))
        d["session"] = str(cfg.get("session") or os.path.basename(sdir))
        d["body_mass"] = float(cfg["body_mass"]) if cfg.get("body_mass") is not None else None
        d["calibration_trials"] = list(calibration_trial_names(cfg))
        d["normalisation_trials"] = list(normalisation_trial_names(cfg))
        pd = (d.get("_project_dir_given")
              or (os.path.join(sdir, str(cfg["project_dir"])) if cfg.get("project_dir") else None)
              or os.path.join(sdir, os.pardir, os.pardir, os.pardir))
        d["project_dir"] = os.path.abspath(str(pd))
        for k in ("models_dir", "setup_dir"):
            if cfg.get(k):
                d[k] = os.path.abspath(os.path.join(d["project_dir"], str(cfg[k])))

    def __getattr__(self, name):
        """Any other top-level session.yaml key: ``session.implanted_side``."""
        cfg = self.__dict__.get("_cfg_data") or {}
        if not name.startswith("_") and name in cfg:
            return cfg[name]
        raise AttributeError(
            f"{type(self).__name__!r} has no attribute {name!r}, and session.yaml has no "
            f"top-level key {name!r}" + (f" ({self.yaml_path})" if "session_dir" in self.__dict__
                                          else ""))

    # -- the file ------------------------------------------------------------
    @property
    def yaml_path(self):
        """This session's session.yaml."""
        return os.path.join(self.session_dir, "session.yaml")

    @property
    def config(self) -> dict:
        """The whole session.yaml (iteration keys normalised)."""
        return dict(self._cfg)

    def source(self, key):
        """``<path>/session.yaml:<line>`` of ``key`` -- click it in the output to
        open the file at that line. Dotted for nested keys:
        ``session.source("iterations.gpk.mvic_factor")``."""
        line = yaml_key_line(self.yaml_path, key)
        return f"{self.yaml_path}:{line}" if line else self.yaml_path


class IterationKeys:
    """session.yaml, ``iterations.<name>:``. ``it.<key>``. File keys come back as
    absolute paths. They are written relative to the session's ``models_dir``
    (model_generic, model_scaled) or ``setup_dir`` (markerset, so_actuators)
    when the session sets that root, else relative to the iteration folder
    (<session>/3_iterations/<name>). ``<subject>``, ``<session>`` and
    ``<iteration>`` in a path are replaced by this iteration's values. One iteration = ONE scaled model: CEINMS uses
    ``model_scaled``, everything else ``it.model_so`` (x mvic_factor, derived)."""

    # files
    model_generic: Optional[str] = None      # generic .osim that gets scaled (absent: model_scaled is given)
    model_scaled: Optional[str] = None       # THE scaled model of this iteration
    markerset: Optional[str] = None          # marker set .xml used to scale it
    so_actuators: Optional[str] = None       # SO actuator .xml; replaces the model ones (unset: model ones).
                                             # OR `percent_XX` (not a file): built per trial, every reserve at
                                             # XX % of that trial's peak |ID moment| of its coordinate
    so_actuators_template: Optional[str] = None  # with `percent_XX`: the .xml naming the actuators (reserves =
                                             # CoordinateActuators called *_reserve; the rest is kept as is)
    scale_tool: Optional[str] = None         # ScaleTool setup TEMPLATE .xml (MeasurementSet, scaling order,
                                             # preserve_mass_distribution); bioscout fills its paths/mass/time
    so_residuals_from_id: bool = False       # before SO: pelvis FX..MZ optimal_force >= peak |ID residual|
    engine: str = "opensim"                  # opensim | pyosim: OpenSim's tools, or bioscout.pyosim (pure
                                             # numpy/scipy, same files and layout) for scale/IK/ID/MA/SO/JRA
    # scaling recipe
    static_trial: Optional[str] = None       # default: the session's static_trial
    linear_scaling: bool = True              # ScaleTool: scale the segments
    marker_placer: bool = False              # ScaleTool: move the markers onto the static
    muscle_opt: bool = True                  # Modenese2015 muscle-parameter optimisation
    opt_neval: int = 10                      # its number of evaluations
    mvic_scaling: Optional[str] = None       # muscle strength: a number (SO force x it), handsfield | handsfield_sprinter, or both ("handsfield x 1.5")
    mvic_factor: float = 1.0                 # SO only: max isometric force x this
    fmax_scaling: Optional[str] = None       # "handsfield" | "handsfield_sprinter": max isometric
                                             # force from Handsfield 2014 (x 2017 sprinter %), applied
                                             # to model_scaled at scale time (bioscout.model.scale_muscle_forces)
    height: Optional[float] = None           # subject height (m), for fmax_scaling="handsfield*"
    marker_weights: dict = {}                # marker -> IK weight while scaling
    ik_weights: dict = {}                    # IK (motion) weights {marker or body: w}, over the session's; 0 = not tracked
    marker_aliases: dict = {}                # expected -> lab marker name (over the session's)
    scale_measurements: list = []            # OLD: [{name, pairs, bodies}] (over the session's) -- use scale_tool
    body_mass: Optional[float] = None        # kg; overrides the session's body_mass for THIS iteration (e.g. a prescaled model of known mass)
    preserve_mass_distribution: bool = True
    # EMG / CEINMS
    emg_map: Optional[str] = None            # NAME of the session emg_map this iteration uses
    calibration: Optional[str] = None        # NAME of the CEINMS calibration config
    ceinms: dict = {}                        # alpha/beta/gamma, mode, calibrated for THIS iteration (over the session's)
    calibrated: bool = True                  # False: execute with the uncalibrated subject
    # display
    label: Optional[str] = None              # legend label (default: the iteration name)
    color: str = "black"
    group: Optional[str] = None

    # -- filled from the file ------------------------------------------------
    @property
    def _cfg(self) -> dict:
        return self.__dict__.get("_cfg_data") or {}

    @_cfg.setter
    def _cfg(self, value):
        self.__dict__["_cfg_data"] = value or {}
        self._fill_keys()

    def _fill_keys(self):
        block, d, cls = self.config, self.__dict__, type(self)
        for k in ITERATION_KEYS:
            if k in ITERATION_FILE_KEYS:
                d[k] = self._file(k)
                continue
            default, v = getattr(cls, k), block.get(k)
            if v is None:
                v = dict(default) if isinstance(default, dict) else default
            elif isinstance(default, bool):
                v = yaml_bool(v)
            elif isinstance(default, (int, float)) and not isinstance(v, bool):
                v = type(default)(v)
            d[k] = v
        d["static_trial"] = block.get("static_trial") or self._cfg.get("static_trial")
        d["label"] = block.get("label") or self.iteration
        d["marker_aliases"] = {**(self._cfg.get("marker_aliases") or {}),
                               **(block.get("marker_aliases") or {})}
        # The iteration's own measurement list REPLACES the session's (a spec is
        # a whole protocol, so merging two half-protocols would be meaningless).
        d["scale_measurements"] = list(block.get("scale_measurements")
                                       or self._cfg.get("scale_measurements") or [])
        d["calibrated"] = iteration_is_calibrated(self._cfg, self.iteration)
        try:
            d["emg_map"] = emg_map_name_for(self._cfg, self.iteration)
        except ValueError:
            d["emg_map"] = None              # reported where it matters (trial_config)
        try:
            d["calibration"] = (calibration_name_for(self._cfg, self.iteration)
                                if d["calibrated"] else None)
        except ValueError:
            d["calibration"] = None

    # -- the file ------------------------------------------------------------
    @property
    def config(self) -> dict:
        """This iteration's block from session.yaml (key names normalised)."""
        return dict(_iteration_blocks(self._cfg).get(self.iteration) or {})

    def _rel(self, key):
        return self.config.get(key)

    #: which session-level root each file key is relative to
    FILE_KEY_ROOT = {"model_generic": "models_dir", "model_scaled": "models_dir",
                     "markerset": "setup_dir", "so_actuators": "setup_dir",
                     "so_actuators_template": "setup_dir",
                     "scale_tool": "setup_dir"}

    def _file_root(self, key):
        """Absolute folder ``key`` is written relative to: the session's
        ``models_dir`` / ``setup_dir`` (relative to project_dir) when set,
        else this iteration's folder."""
        rk = self.FILE_KEY_ROOT.get(key)
        rv = self._cfg.get(rk) if rk else None
        if not rv:
            return self.path
        if os.path.isabs(str(rv)):
            return os.path.normpath(str(rv))
        try:
            pd = self._project_dir()
        except Exception:                                      # noqa: BLE001
            pd = os.path.join(self.session_dir, os.pardir, os.pardir, os.pardir)
        return os.path.abspath(os.path.join(pd, str(rv)))

    def _expand(self, rel):
        """``<subject>`` / ``<session>`` / ``<iteration>`` placeholders."""
        subj = getattr(self, "subject_name", None) or os.path.basename(
            os.path.dirname(os.path.abspath(self.session_dir)))
        sess = getattr(self, "session_name", None) or os.path.basename(
            os.path.abspath(self.session_dir))
        return (str(rel).replace("<subject>", str(subj)).replace("<session>", str(sess))
                .replace("<iteration>", str(self.iteration)))

    def _file(self, key):
        """Absolute path of a file key, or None when it is not set.

        session.yaml paths are relative to THIS iteration's folder (or
        absolute) -- no search, what the file says is where it is. A value
        written the old way (a bare name found by searching the project) is
        still found, with a warning naming the path to write instead;
        ``Session.migrate()`` rewrites the file. A path that does not exist
        is returned as is (``model_scaled`` before scaling, or MISSING)."""
        rel = self.config.get(key)
        if not rel:
            return None
        if key == "so_actuators":
            # `percent_XX` is a recipe, not a path: the file is built per trial
            from bioscout.simulate.so_actuators import percent_spec as _pct
            _p = _pct(rel)
            if _p is not None:
                return f"percent_{_p:g}"
        rel = self._expand(rel)
        p = os.path.normpath(rel if os.path.isabs(rel) else os.path.join(self._file_root(key), rel))
        if os.path.exists(p):
            return p
        old = self._legacy_search(rel, key)
        if old:
            _warn_once(f"[session.yaml WARNING] {self.tag}: {key}: {rel!r} is not relative "
                       f"to {self._file_root(key)}; found by search at {old}. Write "
                       f"`{key}: {self.relpath(old, key)}` (session.migrate() does it).")
            return old
        return p

    def _legacy_search(self, rel, key):
        """Where the pre-2026-09-10 search found a bare name, or None."""
        try:
            if key == "model_scaled":
                return self.resolve_model_file(rel)
            got = self._resolve_model_file(rel, "generic" if key == "model_generic" else key,
                                           quiet=True)
            return got if got and os.path.exists(str(got)) else None
        except Exception:                                      # noqa: BLE001
            return None

    def relpath(self, path, key=None):
        """``path`` as session.yaml writes it for ``key``: relative to that key's
        root (models_dir / setup_dir, see ``_file_root``; the iteration folder
        when ``key`` is None or the root is unset), forward slashes, ``./``-led
        when under the root."""
        root = self._file_root(key) if key else self.path
        r = os.path.relpath(os.path.abspath(str(path)), root).replace(os.sep, "/")
        return r if r.startswith(("../", "./")) or key is None or \
            not self._cfg.get(self.FILE_KEY_ROOT.get(key, "")) else "./" + r

    def source(self, key=None):
        """``<path>/session.yaml:<line>`` of ``iterations.<name>.<key>`` (or of
        the iteration block) -- click it in the output to open that line."""
        ypath = os.path.join(self.session_dir, "session.yaml")
        line = yaml_key_line(ypath, f"iterations.{self.iteration}" + (f".{key}" if key else ""))
        return f"{ypath}:{line}" if line else ypath

    @property
    def model_so(self):
        """The SO model: ``model_scaled`` with every max isometric force x
        ``mvic_factor``, written next to it as ``<name>_mvicx<f>.osim``. The
        same file when ``mvic_factor`` is 1. Derived -- never in session.yaml."""
        m = self.model_scaled
        if not m or self.mvic_factor == 1.0:
            return m
        stem, ext = os.path.splitext(m)
        return f"{stem}_mvicx{self.mvic_factor:.2f}{ext or '.osim'}"


#: The key tables, read off the classes above (one list, not two to keep in step).
SESSION_KEYS = tuple(SessionKeys.__annotations__)
ITERATION_KEYS: Dict[str, object] = {k: getattr(IterationKeys, k)
                                     for k in IterationKeys.__annotations__}

_WARNED = set()


def _warn_once(msg):
    """print() each distinct warning once per process -- an Iteration is
    rebuilt often, and the same file should not repeat itself."""
    if msg not in _WARNED:
        _WARNED.add(msg)
        print(msg)


#: Force-scaling OPTIONS accepted by `mvic_scaling` besides a number.
MVIC_SCALING_OPTIONS = ("handsfield", "handsfield_sprinter")


def parse_mvic_scaling(v):
    """``mvic_scaling`` -> (mvic_factor or None, fmax_scaling or None).

    One key for how strong the muscles are, in either of two ways:

      mvic_scaling: 3.0                     SO model = max isometric force x 3
      mvic_scaling: handsfield              Fmax from Handsfield 2014 muscle
      mvic_scaling: handsfield_sprinter     volumes (x 2017 sprinter %), applied
                                            to model_scaled at scale time
      mvic_scaling: handsfield x 1.5        both: Handsfield, then SO x 1.5
                    [handsfield, 1.5]       (same, as a list)

    Raises ValueError for anything else."""
    if v is None or v == "":
        return None, None
    if isinstance(v, bool):
        raise ValueError(f"mvic_scaling: {v!r} is not a number or "
                         f"{' | '.join(MVIC_SCALING_OPTIONS)}")
    if isinstance(v, (int, float)):
        return float(v), None
    parts = (list(v) if isinstance(v, (list, tuple))
             else [p for p in re.split(r"[\s,x*×]+", str(v).strip()) if p])
    fac = opt = None
    for p in parts:
        if isinstance(p, (int, float)) and not isinstance(p, bool):
            fac = float(p); continue
        t = str(p).strip().lower()
        try:
            fac = float(t); continue
        except ValueError:
            pass
        if t in MVIC_SCALING_OPTIONS:
            opt = t; continue
        raise ValueError(f"mvic_scaling: {v!r} -- expected a number, "
                         f"{' | '.join(MVIC_SCALING_OPTIONS)}, or both "
                         f"(e.g. 'handsfield x 1.5')")
    return fac, opt


def _mvic_scaling(b, name, where, warn):
    """`mvic_scaling` (one key, 2026-10-01) -> the internal `mvic_factor` /
    `fmax_scaling`. The two old keys still work on their own."""
    if "mvic_scaling" not in b:
        return
    fac, opt = parse_mvic_scaling(b.pop("mvic_scaling"))
    if ("mvic_factor" in b or "fmax_scaling" in b):
        warn(f"[session.yaml WARNING] iterations.{name}{where}: mvic_scaling is set, "
             f"so mvic_factor / fmax_scaling are ignored -- delete them.")
        b.pop("mvic_factor", None); b.pop("fmax_scaling", None)
    if fac is not None:
        b["mvic_factor"] = fac
    if opt is not None:
        b["fmax_scaling"] = opt


def normalise_iterations(cfg, path=None, warn=_warn_once):
    """Return ``cfg`` with every iteration block in the canonical shape.

    * ``models:`` -> ``iterations:``, a list of blocks -> ``{name: block}``
    * old key spellings are renamed (``generic`` -> ``model_generic``) and the
      two old model keys (``so_model``, ``ceinms_model``) collapse into
      ``model_scaled`` -- an error if they named different models
    * a session-level ``markerset`` is copied into every iteration that has
      none, and dropped from the top level — the marker set belongs to the
      model it scales
    * unknown iteration keys are reported (a typo is otherwise just ignored)

    Each fix prints one warning naming the file, so the file can be updated.
    The input is not modified.
    """
    if not isinstance(cfg, dict):
        return cfg
    where = f" in {path}" if path else ""
    out = dict(cfg)
    if "iterations" not in out and "models" in out:
        warn(f"[session.yaml WARNING] `models:`{where} is now `iterations:` — rename it.")
    blocks = _iteration_blocks(out)
    out.pop("models", None)
    its = {}
    for name, block in blocks.items():
        b = {k: v for k, v in dict(block or {}).items() if k != "name"}
        # the two old model keys -> ONE model. The SO model used to be named in
        # the file as a separate .osim; it is now derived from model_scaled.
        so = b.pop("so_model", None) or b.pop("model", None)
        ce = b.pop("ceinms_model", None) or b.pop("model_ceinms", None)
        if (so or ce) and "model_scaled" in b:
            warn(f"[session.yaml WARNING] iterations.{name}{where}: so_model/ceinms_model "
                 f"ignored -- model_scaled is set. Delete them.")
        elif so or ce:
            if so and ce and str(so) != str(ce):
                raise ValueError(
                    f"iterations.{name}{where}: so_model ({so}) and ceinms_model ({ce}) "
                    f"are different models. One iteration is ONE model for every stage "
                    f"(SO, JRA and CEINMS) -- for another model add another iteration "
                    f"(session.add_iteration).")
            b["model_scaled"] = ce or so
            warn(f"[session.yaml WARNING] iterations.{name}{where}: so_model/ceinms_model "
                 f"are now ONE key, `model_scaled` (SO uses it x mvic_factor) — "
                 f"session.migrate() rewrites the file.")
        for old, new in ITERATION_KEY_RENAMES.items():
            if old in b:
                warn(f"[session.yaml WARNING] iterations.{name}.{old}{where} is now "
                     f"`{new}` — session.migrate() rewrites the file.")
                b.setdefault(new, b[old])
                b.pop(old)
        _mvic_scaling(b, name, where, warn)
        for old, why in ITERATION_KEYS_REMOVED.items():
            if old in b:
                b.pop(old)
                warn(f"[session.yaml WARNING] iterations.{name}.{old}{where} is gone: {why}.")
        unknown = sorted(k for k in b if k not in ITERATION_KEYS)
        if unknown:
            warn(f"[session.yaml WARNING] iterations.{name}{where}: unknown key(s) "
                 f"{unknown} — ignored. Known: {', '.join(ITERATION_KEYS)}")
        its[name] = b
    ms = out.pop("markerset", None)
    if ms:
        missing = [n for n, b in its.items() if not b.get("markerset")]
        for n in missing:
            its[n]["markerset"] = ms
        if its:
            warn(f"[session.yaml WARNING] `markerset:` is set for the whole session{where}; "
                 f"it belongs to each iteration — move it into "
                 + ", ".join(f"iterations.{n}" for n in (missing or its)) + ".")
        else:
            out["markerset"] = ms        # no iteration yet: kept for add_iteration
    if its or "iterations" in cfg or "models" in cfg:
        out["iterations"] = its
    return out


def _is_named(raw, key, leaf) -> bool:
    """Is `raw` a block of NAMED sub-blocks, or one flat block?

    Told apart by value TYPE, and nothing else: a leaf entry never maps to a
    mapping, a named sub-block always does. `leaf` names what a leaf is, for
    the error. Shared by `emg_map` and `calibration` so the two cannot drift
    into behaving differently.

    A block mixing the two is a typo, not a third form, so it raises rather
    than guessing — half a block silently dropped is exactly the failure these
    features exist to make impossible.
    """
    if not raw:
        return False
    dicts = [k for k, v in raw.items() if isinstance(v, dict)]
    if not dicts:
        return False
    if len(dicts) != len(raw):
        others = [k for k in raw if k not in set(dicts)]
        raise ValueError(
            f"{key} mixes named sub-blocks with bare {leaf}s: "
            f"{sorted(dicts)} are sub-blocks but {sorted(others)} are not. "
            f"Either give every {leaf} a name to sit under, or use a single "
            f"flat {key} block.")
    return True


def _select_name(cfg, iteration, *, blocks, named, key, default_key, what):
    """Which named block `iteration` runs with, or a ValueError saying why not.

    The order is: the iteration's own selector, the session-wide default key, a
    block literally called ``default``, the only block if there is one. Shared
    by `emg_map` and `calibration`.
    """
    if not blocks:
        return None
    it = _iteration_blocks(cfg).get(iteration) or {} if iteration else {}
    want = it.get(key)

    if want is not None:
        if not isinstance(want, str):
            raise ValueError(
                f"iteration {iteration!r}: {key} must be the NAME of a "
                f"{what} under the session-wide {key} (a string), not "
                f"{type(want).__name__}. The {what}s themselves belong at the "
                "top level, not inside an iteration.")
        if not named:
            raise ValueError(
                f"iteration {iteration!r} selects {key} {want!r} but the "
                f"session-wide {key} is a single flat block with no names to "
                "choose from. Nest it under a name first.")
        if want not in blocks:
            raise ValueError(
                f"iteration {iteration!r} selects {key} {want!r}, which is "
                f"not defined. Available: {sorted(blocks)}.")
        return want

    dflt = cfg.get(default_key) if isinstance(cfg, dict) else None
    if not named:
        # A default only means something when there is a set to choose from.
        # Accepting it silently on a flat block would let a typo'd name sit in
        # session.yaml looking effective, and a rewrite would drop it.
        if dflt is not None and str(dflt) != "default":
            raise ValueError(
                f"{default_key}: {dflt!r} is set, but {key} is a single flat "
                "block with no names to choose from. Nest it under a name, or "
                "drop the key.")
        return "default"

    if dflt is not None:
        if str(dflt) not in blocks:
            raise ValueError(
                f"{default_key}: {dflt!r} is not a defined {key}. "
                f"Available: {sorted(blocks)}.")
        return str(dflt)
    if "default" in blocks:
        return "default"
    if len(blocks) == 1:
        return next(iter(blocks))
    where = f"iteration {iteration!r}" if iteration else "this session"
    raise ValueError(
        f"{key} defines {len(blocks)} {what}s ({sorted(blocks)}) and {where} "
        f"does not say which to use. Add `{key}: <name>` to the iteration, or "
        f"a session-wide `{default_key}: <name>`. Guessing here would run the "
        "wrong one without any sign in the output.")


def is_named_emg_map(cfg) -> bool:
    """True when `emg_map` holds NAMED sub-maps rather than channels.

        emg_map: {EMG01_vast_lat_l: [vaslat_l, ...]}        -> flat  (legacy)
        emg_map: {narrow: {EMG01_vast_lat_l: [...]}, ...}   -> named
    """
    return _is_named(_raw_emg_map(cfg), "emg_map", "channel")


def emg_maps(cfg) -> Dict[str, Dict[str, list]]:
    """``{name: {channel: [muscles]}}`` for every mapping in a session config.

    A legacy flat `emg_map` comes back as a single entry under the name
    ``'default'``, so callers never need to branch on the form. Insertion
    order follows the YAML.
    """
    raw = _raw_emg_map(cfg)
    if not raw:
        return {}
    if not is_named_emg_map(cfg):
        return {"default": {str(k): _as_list(v) for k, v in raw.items()}}
    return {str(name): {str(k): _as_list(v) for k, v in (block or {}).items()}
            for name, block in raw.items()}


def emg_map_name_for(cfg, iteration=None) -> Optional[str]:
    """Which named mapping `iteration` runs with — see :func:`resolve_emg_map`."""
    return _select_name(cfg, iteration, blocks=emg_maps(cfg),
                        named=is_named_emg_map(cfg), key="emg_map",
                        default_key=DEFAULT_EMG_MAP_KEY, what="mapping")


def resolve_emg_map(cfg, iteration=None, *, strict=True) -> Dict[str, list]:
    """The ``{channel: [muscles]}`` map one iteration should actually run with.

    Resolution order: the iteration's own ``emg_map: <name>`` selector, then
    the session-wide ``default_emg_map``, then a mapping literally called
    ``default``, then the only mapping if there is exactly one. Anything left
    over is ambiguous and raises.

    With ``strict=False`` an ambiguous or unknown selection falls back to the
    first mapping in YAML order instead of raising — for read-only consumers
    (plots, reports) where a missing figure is worse than an approximate one.
    """
    try:
        maps = emg_maps(cfg)
        if not maps:
            return {}
        name = emg_map_name_for(cfg, iteration)
    except Exception:
        # Lenient callers get the first map rather than nothing: a malformed
        # block is the strict path's problem, and it has already refused the
        # file by the time anything runs.
        if strict:
            raise
        try:
            raw = _raw_emg_map(cfg)
            vals = list(raw.values())
            if not vals:
                return {}
            if all(isinstance(v, dict) for v in vals):
                first = vals[0]                       # named: the first map
            elif not any(isinstance(v, dict) for v in vals):
                first = raw                           # flat: the map itself
            else:                                     # mixed: first sub-map
                first = next(v for v in vals if isinstance(v, dict))
            return {str(k): _as_list(v) for k, v in (first or {}).items()}
        except Exception:
            return {}
    return dict(maps.get(name) or {})


# ---------------------------------------------------------------------------
# emg_gain: a per-channel multiplier applied AFTER session-max normalisation
# ---------------------------------------------------------------------------
#: session.yaml key holding ``{channel: factor}``.
EMG_GAIN_KEY = "emg_gain"


def raw_emg_gain(cfg):
    """The ``emg_gain`` block as authored, or ``{}``."""
    if not isinstance(cfg, dict):
        return {}
    raw = cfg.get(EMG_GAIN_KEY)
    return dict(raw) if isinstance(raw, dict) else {}


def resolve_emg_gain(cfg, channels=None, *, strict=True) -> Dict[str, float]:
    """``{channel: factor}`` to multiply the session-normalised EMG by.

    WHY IT IS APPLIED AFTER NORMALISATION, NOT TO THE RAW SIGNAL
        ``run_emg_normalise`` divides every channel by its own maximum across
        the session's trials. Scaling the raw ``emg.mot`` is therefore an exact
        no-op: the session maximum scales with the signal and divides the
        factor straight back out. The gain has to land on the normalised
        signal, which also means a hand-edited
        ``emg_filtered_normalised.mot`` cannot survive -- every calibration and
        every uncalibrated preparation regenerates that file from the raw EMG.

    WHY THERE IS NO NAMED FORM
        Unlike ``emg_map`` and ``calibration``, this block is deliberately FLAT
        and session-wide. It changes
        ``2_experimental/<trial>/emg_filtered_normalised.mot``, ONE file shared
        by every iteration of the session, so a per-iteration gain would
        promise something the folder layout cannot deliver: the last iteration
        to normalise would win and every other iteration would silently read
        its excitations. To compare gains, copy the session -- see
        ``tests/GPKv3/t26_gastroc_emg_scale`` in the Powerlifting project.

    ``channels`` is the set of channel names actually present in the data. A
    gain naming a channel that is not there RAISES, because a typo is otherwise
    invisible: the run finishes normally hours later with the unscaled signal,
    which is exactly the failure this key exists to rule out.
    """
    raw = raw_emg_gain(cfg)
    if not raw:
        return {}
    gains, bad = {}, []
    for ch, v in raw.items():
        try:
            f = float(v)
        except (TypeError, ValueError):
            bad.append("%s: %r is not a number" % (ch, v))
            continue
        if not (f > 0.0):
            bad.append("%s: gain must be > 0, got %g" % (ch, f))
            continue
        gains[str(ch)] = f
    if channels is not None:
        known = {str(c) for c in channels}
        absent = sorted(c for c in gains if c not in known)
        if absent:
            shown = sorted(known)
            bad.append("no such EMG channel: %s. present: %s%s"
                       % (", ".join(absent), ", ".join(shown[:8]),
                          " ..." if len(shown) > 8 else ""))
    if bad:
        msg = "session.yaml emg_gain is invalid:\n  " + "\n  ".join(bad)
        if strict:
            raise ValueError(msg)
        print("[warn] " + msg)
        if channels is not None:
            known = {str(c) for c in channels}
            gains = {c: g for c, g in gains.items() if c in known}
    return gains


# ---------------------------------------------------------------------------
# calibration: CEINMS parameter bounds, one flat block or several NAMED ones
# ---------------------------------------------------------------------------
#: session.yaml key naming which calibration config iterations use by default.
DEFAULT_CALIBRATION_KEY = "default_calibration"

#: What CEINMS's calibrationCfg.xml calls each parameter, keyed by every
#: spelling seen in the wild. `configs.py` reads the camelCase names while
#: settings.py has always declared snake_case ones, so four of the six ranges
#: were silently unreadable and editing them did nothing. Accept both here and
#: emit the name CEINMS actually wants.
CALIBRATION_PARAM_NAMES = {
    "c1": "c1",
    "c2": "c2",
    "shapefactor": "shapefactor",
    "shape_factor": "shapefactor",
    "optimalfiberlength": "optimalFiberLength",
    "optimal_fiber_length": "optimalFiberLength",
    "optimalfibrelength": "optimalFiberLength",
    "optimal_fibre_length": "optimalFiberLength",
    "tendonslacklength": "tendonSlackLength",
    "tendon_slack_length": "tendonSlackLength",
    "strengthcoefficient": "strengthCoefficient",
    "strength_coefficient": "strengthCoefficient",
}

#: The `<optimiser>` knobs a `calibration:` block may ALSO carry — how the
#: search runs, rather than the bounds it runs inside. Added 2026-08-10 for
#: t25 (calibration variance / learning rate): sweeping the learning rate used
#: to mean monkeypatching `settings.CEINMSSettings` at runtime, which left no
#: record in the session of which arm ran under which rate.
#:
#: `configs.py` owns the emission and the same alias table in
#: `_OPTIMISER_ALIASES`; this mapping exists so `_check_calibration` does not
#: warn about a key that IS honoured, and so both spellings survive
#: canonicalisation. Keep the two in step.
CALIBRATION_OPTIMISER_NAMES = {
    "hybridcalibration": "hybridCalibration",
    "hybrid_calibration": "hybridCalibration",
    "learningrate": "learningRate",
    "learning_rate": "learningRate",
    "maxiterations": "maxIterations",
    "max_iterations": "maxIterations",
    "minimprovement": "minImprovement",
    "early_stopping_min_improvement": "minImprovement",
    "patience": "patience",
    "early_stopping_patience": "patience",
    "numberofsynergies": "numberOfSynergies",
    "num_synergies": "numberOfSynergies",
    "number_of_synergies": "numberOfSynergies",
    # <learningRateDecay>'s two children. Unproven in this CEINMS build — the
    # shipped reference cfg has the block commented out.
    "decay": "decay",
    "learningratedecay": "decay",
    "learning_rate_decay": "decay",
    "decayfactor": "decay",
    "decay_factor": "decay",
    "minlearningrate": "minLearningRate",
    "min_learning_rate": "minLearningRate",
}


def _cal_param(key):
    """Canonical calibrationCfg name for an authored key — bound or optimiser."""
    k = str(key).strip().lower()
    if k in CALIBRATION_PARAM_NAMES:
        return CALIBRATION_PARAM_NAMES[k]
    return CALIBRATION_OPTIMISER_NAMES.get(k, str(key))


def _cal_value(v):
    """``[0.5, 3]``, ``"0.5 3"`` and ``0.5`` all become the string CEINMS wants."""
    if isinstance(v, (list, tuple)):
        return " ".join(str(x) for x in v)
    return str(v)


def ceinms_for(cfg, iteration=None) -> dict:
    """CEINMS settings for ONE iteration: the iteration's own ``ceinms:`` block
    over the session-wide one (2026-10-01: alpha/beta/gamma, mode and
    ``calibrated`` belong to the iteration -- two arms of one session can
    differ). Without an iteration, the session-wide block."""
    if not isinstance(cfg, dict):
        return {}
    out = dict(cfg.get("ceinms") or {}) if isinstance(cfg.get("ceinms"), dict) else {}
    if iteration:
        it = _iteration_blocks(cfg).get(iteration) or {}
        if isinstance(it.get("ceinms"), dict):
            out.update(it["ceinms"])
    return out


def _ceinms_block(cfg) -> dict:
    """The ``ceinms:`` mapping, or ``{}``."""
    if not isinstance(cfg, dict):
        return {}
    ce = cfg.get("ceinms")
    return ce if isinstance(ce, dict) else {}


def _raw_calibration(cfg):
    """The calibration block, from ``ceinms.calibration`` or the legacy top level.

    CANONICAL LOCATION IS ``ceinms.calibration`` (2026-08-24). These are
    CEINMS's parameter bounds and nothing else reads them, so a top-level key
    sat them beside ``subject`` and ``body_mass`` as though they were session
    facts. ``ceinms.alpha/beta/gamma`` were already nested; the calibration
    configs had simply not followed.

    The top-level spelling still LOADS, because a reader that refused it could
    not be used to migrate the files that need migrating. It is deprecated,
    reported once per file by :func:`_check_calibration`, and rewritten by
    :func:`migrate_calibration_block`.
    """
    if not isinstance(cfg, dict):
        return {}
    ce = _ceinms_block(cfg)
    raw = ce.get("calibration", ce.get("calibration_params"))
    if isinstance(raw, dict):
        return raw
    raw = cfg.get("calibration", cfg.get("calibration_params"))
    return raw if isinstance(raw, dict) else {}


def _default_calibration_name(cfg):
    """``default_calibration``, nested first — same precedence as the block."""
    ce = _ceinms_block(cfg)
    if DEFAULT_CALIBRATION_KEY in ce:
        return ce.get(DEFAULT_CALIBRATION_KEY)
    return cfg.get(DEFAULT_CALIBRATION_KEY) if isinstance(cfg, dict) else None


def uses_legacy_calibration(cfg) -> bool:
    """True when the calibration block is still at the top level.

    Having both is NOT an error and NOT a merge: the nested one wins outright,
    exactly as :func:`_raw_calibration` reads it. Silently merging two blocks
    that disagree is how you end up with bounds nobody wrote.
    """
    if not isinstance(cfg, dict):
        return False
    ce = _ceinms_block(cfg)
    if isinstance(ce.get("calibration", ce.get("calibration_params")), dict):
        return False
    return isinstance(cfg.get("calibration",
                              cfg.get("calibration_params")), dict) or \
        DEFAULT_CALIBRATION_KEY in cfg


def is_named_calibration(cfg) -> bool:
    """True when `calibration` holds NAMED configs rather than bare parameters.

        calibration: {optimalFiberLength: "0.5 3"}          -> flat
        calibration: {tight: {optimalFiberLength: "0.75 1.25"}, ...}   -> named
    """
    return _is_named(_raw_calibration(cfg), "calibration", "parameter")


def calibration_configs(cfg) -> Dict[str, Dict[str, str]]:
    """``{name: {parameter: "min max"}}`` for every calibration config.

    A flat block comes back under the name ``'default'``. Parameter names are
    canonicalised, so `optimal_fiber_length` and `optimalFiberLength` are the
    same knob and both actually reach the XML.
    """
    raw = _raw_calibration(cfg)
    if not raw:
        return {}
    if not is_named_calibration(cfg):
        return {"default": {_cal_param(k): _cal_value(v) for k, v in raw.items()}}
    return {str(name): {_cal_param(k): _cal_value(v)
                        for k, v in (block or {}).items()}
            for name, block in raw.items()}


def calibration_name_for(cfg, iteration=None) -> Optional[str]:
    """Which named calibration config `iteration` runs with."""
    # _select_name reads `default_calibration` off the top level. Overlay the
    # nested one when it is there so the selector follows the block it selects
    # from — a nested `calibration:` with a top-level `default_calibration:`
    # would otherwise name a config out of the block it is not in.
    view = cfg
    ce = _ceinms_block(cfg)
    if DEFAULT_CALIBRATION_KEY in ce and isinstance(cfg, dict):
        view = dict(cfg)
        view[DEFAULT_CALIBRATION_KEY] = ce[DEFAULT_CALIBRATION_KEY]
    return _select_name(view, iteration, blocks=calibration_configs(cfg),
                        named=is_named_calibration(cfg), key="calibration",
                        default_key=DEFAULT_CALIBRATION_KEY, what="config")


def resolve_calibration(cfg, iteration=None, *, strict=True) -> Dict[str, str]:
    """The CEINMS calibration parameter bounds one iteration should run with.

    Same shape and the same rules as :func:`resolve_emg_map`: an iteration
    names its config with ``calibration: <name>``, or the session names a
    ``default_calibration``, or there is only one. Ambiguity raises.

    Anything the config does not mention is left to settings.py — a config
    naming only ``optimalFiberLength`` overrides that bound and nothing else.
    """
    try:
        blocks = calibration_configs(cfg)
        if not blocks:
            return {}
        name = calibration_name_for(cfg, iteration)
    except Exception:
        if strict:
            raise
        try:
            raw = _raw_calibration(cfg)
            vals = list(raw.values())
            if not vals:
                return {}
            if all(isinstance(v, dict) for v in vals):
                first = vals[0]
            elif not any(isinstance(v, dict) for v in vals):
                first = raw
            else:
                first = next(v for v in vals if isinstance(v, dict))
            return {_cal_param(k): _cal_value(v)
                    for k, v in (first or {}).items()}
        except Exception:
            return {}
    return dict(blocks.get(name) or {})


def iteration_is_calibrated(cfg, iteration=None) -> bool:
    """Does `iteration` calibrate at all?

    `calibrated: false` on the iteration, or session-wide, means execution runs
    against `subjectUncalibrated.xml` and no calibration happens — so the
    iteration has no calibration CONFIG to name, and demanding one would force
    a selector that is never read into every uncalibrated arm.
    """
    if not isinstance(cfg, dict):
        return True
    it = _iteration_blocks(cfg).get(iteration) or {} if iteration else {}
    ce = ceinms_for(cfg, iteration)
    return yaml_bool(it.get("calibrated", ce.get("calibrated", True)))


#: Files whose legacy top-level `calibration:` has already been reported. One
#: line per FILE — this check runs on every load, and a session is loaded many
#: times in a batch.
_LEGACY_CALIBRATION_WARNED = set()


def _check_calibration(data, path):
    """Load-time validation of `calibration` and every iteration's selector."""
    if uses_legacy_calibration(data) and str(path) not in _LEGACY_CALIBRATION_WARNED:
        _LEGACY_CALIBRATION_WARNED.add(str(path))
        print(f"[session.yaml] DEPRECATED: `calibration:` / "
              f"`{DEFAULT_CALIBRATION_KEY}:` at the top level of {path}. "
              f"They are CEINMS parameter bounds and belong under `ceinms:`. "
              f"Still read for now; migrate with "
              f"`bioscout session migrate-calibration`.")
    try:
        blocks = calibration_configs(data)
    except ValueError as e:
        raise ValueError(f"{e} (in {path})") from None
    if not blocks:
        return {}
    seen = {}
    for n in blocks:
        key = str(n).strip().lower()
        if key in seen:
            raise ValueError(
                f"calibration names {seen[key]!r} and {n!r} in {path} differ "
                "only by case or whitespace — pick distinct names.")
        seen[key] = n
    known = (set(CALIBRATION_PARAM_NAMES.values())
             | set(CALIBRATION_OPTIMISER_NAMES.values()))
    unknown = {p for b in blocks.values() for p in b if p not in known}
    if unknown:
        # Not fatal -- CEINMS may grow parameters -- but a typo'd bound that
        # silently does nothing is the exact bug this feature exists to end.
        print(f"[session.yaml] WARNING: calibration parameter(s) "
              f"{sorted(unknown)} in {path} are not ones bioscout writes to "
              f"calibrationCfg.xml. Known bounds: "
              f"{sorted(set(CALIBRATION_PARAM_NAMES.values()))}; optimiser: "
              f"{sorted(set(CALIBRATION_OPTIMISER_NAMES.values()))}")
    for name in _iteration_blocks(data):
        if not iteration_is_calibrated(data, name):
            continue          # nothing to calibrate -> nothing to select
        try:
            calibration_name_for(data, name)
        except ValueError as e:
            raise ValueError(f"{e} (in {path})") from None
    if not _iteration_blocks(data):
        try:
            calibration_name_for(data)
        except ValueError as e:
            raise ValueError(f"{e} (in {path})") from None
    return blocks


def _check_emg_maps(data, path):
    """Load-time validation of `emg_map` and every iteration's selector."""
    try:
        maps = emg_maps(data)
    except ValueError as e:
        raise ValueError(f"{e} (in {path})") from None
    if not maps:
        return {}
    seen = {}
    for n in maps:
        key = str(n).strip().lower()
        if key in seen:
            raise ValueError(
                f"emg_map names {seen[key]!r} and {n!r} in {path} differ only "
                "by case or whitespace — pick distinct names.")
        seen[key] = n
    # every DECLARED iteration must resolve -- under either authored shape
    # (mapping or list) and either key (`iterations` or the `models` alias).
    for name in _iteration_blocks(data):
        try:
            emg_map_name_for(data, name)
        except ValueError as e:
            raise ValueError(f"{e} (in {path})") from None
    if not _iteration_blocks(data):
        # No iterations to pin a choice to. Only the session-level default can
        # disambiguate, and without one every session-level reader would be
        # guessing -- so say so here rather than in each of them.
        try:
            emg_map_name_for(data)
        except ValueError as e:
            raise ValueError(f"{e} (in {path})") from None
    return maps


# ---------------------------------------------------------------------------
# session.yaml  ->  SessionSpec
# ---------------------------------------------------------------------------
def read_session_yaml(path) -> SessionSpec:
    """Parse a ``session.yaml`` into a :class:`SessionSpec`. ``path`` may be the
    yaml file or the session folder containing it."""
    _require_yaml()
    if os.path.isdir(path):
        for name in ("session.yaml", "session.yml"):
            cand = os.path.join(path, name)
            if os.path.isfile(cand):
                path = cand
                break
        else:
            path = os.path.join(path, "session.yaml")
    data = normalise_iterations(load_session_yaml(path), path)

    spec = SessionSpec(
        subject=str(data.get("subject", "") or ""),
        session=str(data.get("session", "") or ""),
        path=os.path.dirname(os.path.abspath(path)),
        project_dir=data.get("project_dir"),
        body_mass=(float(data["body_mass"]) if data.get("body_mass") is not None else None),
        static_trial=data.get("static_trial"),
        setup_folder=data.get("setup_folder"),
        markerset=data.get("markerset"),
        c3d_source=data.get("c3d_source"),
    )

    # iterations, already {name: block} with canonical keys (normalise_iterations)
    for name, m in (data.get("iterations") or {}).items():
        m = dict(m or {})
        spec.models.append(Model(
            name=name,
            model_generic=m.get("model_generic"),
            model_scaled=m.get("model_scaled"),
            markerset=m.get("markerset"),
            so_actuators=m.get("so_actuators") or None,
            so_residuals_from_id=yaml_bool(m.get("so_residuals_from_id", False)),
            engine=str(m.get("engine") or "opensim").strip().lower(),
            label=m.get("label"),
            color=m.get("color", "black"),
            group=m.get("group"),
            muscle_opt=yaml_bool(m.get("muscle_opt", True)),
            static_trial=m.get("static_trial"),
            marker_weights={str(k): float(v) for k, v in (m.get("marker_weights") or {}).items()},
            ik_weights={str(k): float(v) for k, v in (m.get("ik_weights") or {}).items()},
            preserve_mass_distribution=bool(m.get("preserve_mass_distribution", True)),
            linear_scaling=bool(m.get("linear_scaling", True)),
            marker_placer=bool(m.get("marker_placer", False)),
            mvic_factor=(float(m["mvic_factor"]) if m.get("mvic_factor") is not None else None),
            fmax_scaling=(str(m["fmax_scaling"]) if m.get("fmax_scaling") else None),
            height=(float(m["height"]) if m.get("height") is not None else None),
            opt_neval=(int(m["opt_neval"]) if m.get("opt_neval") is not None else None),
            emg_map=(str(m["emg_map"]) if m.get("emg_map") is not None else None),
            calibration=(str(m["calibration"])
                         if m.get("calibration") is not None else None),
        ))

    # emg_map is either one flat channel map or several named ones. Keep both
    # views: `emg_muscle_mapping` stays the session DEFAULT so every existing
    # caller is unaffected, `emg_muscle_mappings` holds the named set.
    _named = emg_maps(data)
    if is_named_emg_map(data):
        spec.emg_muscle_mappings = _named
        _dflt = data.get(DEFAULT_EMG_MAP_KEY)
        spec.default_emg_map = str(_dflt) if _dflt is not None else None
        spec.emg_muscle_mapping = resolve_emg_map(data, strict=False)
    else:
        spec.emg_muscle_mapping = dict(_named.get("default") or {})

    if is_named_calibration(data):
        spec.calibrations = calibration_configs(data)
        _dc = data.get(DEFAULT_CALIBRATION_KEY)
        spec.default_calibration = str(_dc) if _dc is not None else None
    spec.ceinms = {str(k): str(v) for k, v in (data.get("ceinms") or {}).items()}
    # Per-trial `calibration:` / `emg_normalisation:` flags win; the legacy
    # top-level lists fill in the rest (see TRIAL_ROLE_KEYS).
    spec.normalisation_trials = normalisation_trial_names(data)
    spec.calibration_trials = calibration_trial_names(data)

    for tname, entry in (data.get("trials") or {}).items():
        entry = dict(entry or {})
        out = {}
        if entry.get("type"):
            out["type"] = entry["type"]
        if entry.get("time_range") is not None:
            out["time_range"] = [float(x) for x in entry["time_range"]]
        if entry.get("events") is not None:
            out["events"] = [float(x) for x in entry["events"]]
        # Per-trial role flags — carried through so a round-trip does not
        # quietly drop them back onto the legacy lists.
        for _role in TRIAL_ROLE_KEYS:
            if entry.get(_role) is not None:
                out[_role] = yaml_bool(entry[_role])
        spec.trials[str(tname)] = out
    return spec


# ---------------------------------------------------------------------------
# SessionSpec  ->  session.yaml
# ---------------------------------------------------------------------------
def _spec_to_dict(spec: SessionSpec) -> dict:
    d: dict = {}
    if spec.subject:      d["subject"] = spec.subject
    if spec.session:      d["session"] = spec.session
    if spec.project_dir:  d["project_dir"] = spec.project_dir
    if spec.body_mass is not None: d["body_mass"] = spec.body_mass
    if spec.static_trial: d["static_trial"] = spec.static_trial
    if spec.setup_folder: d["setup_folder"] = spec.setup_folder
    # markerset belongs to each iteration; session-level only while there is none
    if spec.markerset and not spec.models:
        d["markerset"] = spec.markerset
    if spec.c3d_source:   d["c3d_source"] = spec.c3d_source
    if spec.calibration_trials:   d["calibration_trials"] = list(spec.calibration_trials)
    if spec.normalisation_trials: d["normalisation_trials"] = list(spec.normalisation_trials)
    if spec.emg_muscle_mappings:
        d["emg_map"] = {name: {k: list(v) for k, v in (block or {}).items()}
                        for name, block in spec.emg_muscle_mappings.items()}
        if spec.default_emg_map:
            d[DEFAULT_EMG_MAP_KEY] = spec.default_emg_map
    elif spec.emg_muscle_mapping:
        d["emg_map"] = {k: list(v) for k, v in spec.emg_muscle_mapping.items()}
    if spec.calibrations:
        d["calibration"] = {n: dict(b or {}) for n, b in spec.calibrations.items()}
        if spec.default_calibration:
            d[DEFAULT_CALIBRATION_KEY] = spec.default_calibration
    if spec.ceinms:
        d["ceinms"] = dict(spec.ceinms)
    if spec.trials:
        d["trials"] = {}
        for tname, entry in spec.trials.items():
            e = {}
            if entry.get("type"):       e["type"] = entry["type"]
            if entry.get("time_range"): e["time_range"] = list(entry["time_range"])
            if entry.get("events"):     e["events"] = list(entry["events"])
            d["trials"][tname] = e
    if spec.models:
        d["iterations"] = {}
        for m in spec.models:
            it: dict = {}
            # uniform key order across every iteration
            if m.model_generic:   it["model_generic"] = m.model_generic
            if m.model_scaled:    it["model_scaled"] = m.model_scaled
            if m.markerset or spec.markerset:
                it["markerset"] = m.markerset or spec.markerset
            if not m.linear_scaling: it["linear_scaling"] = False
            if m.marker_placer:      it["marker_placer"] = True
            if not m.muscle_opt:     it["muscle_opt"] = False
            if m.so_actuators: it["so_actuators"] = m.so_actuators
            if m.so_residuals_from_id: it["so_residuals_from_id"] = True
            it["engine"] = m.engine or "opensim"   # always written: which engine ran is part of the result
            if m.opt_neval is not None:   it["opt_neval"] = m.opt_neval
            if m.mvic_factor is not None: it["mvic_factor"] = m.mvic_factor
            if m.fmax_scaling: it["fmax_scaling"] = m.fmax_scaling
            if m.height is not None: it["height"] = m.height
            if m.static_trial:  it["static_trial"] = m.static_trial
            if m.marker_weights: it["marker_weights"] = dict(m.marker_weights)
            if m.ik_weights: it["ik_weights"] = dict(m.ik_weights)
            if not m.preserve_mass_distribution:
                it["preserve_mass_distribution"] = False
            if m.emg_map:      it["emg_map"] = m.emg_map
            if m.calibration:  it["calibration"] = m.calibration
            if m.label and m.label != m.name: it["label"] = m.label
            if m.color and m.color != "black": it["color"] = m.color
            if m.group:         it["group"] = m.group
            d["iterations"][m.name] = it
    return d


def _yamlable(v):
    """Coerce values PyYAML's SafeDumper refuses into ones it accepts.

    A project's settings.py holds paths as ``pathlib.Path``, which is the right
    type there and an unrepresentable object here. Coercing at the boundary is
    better than making every caller remember to str() — the failure mode
    otherwise is a half-written session.yaml and a traceback from deep inside
    the yaml library, which is what it was.
    """
    import pathlib
    if isinstance(v, pathlib.PurePath):
        return str(v)
    if isinstance(v, dict):
        return {str(k): _yamlable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [_yamlable(x) for x in v]
    if isinstance(v, (bool, int, float, str)) or v is None:
        return v
    return str(v)


def write_session_yaml(spec: SessionSpec, path=None) -> str:
    """Serialise a :class:`SessionSpec` to ``session.yaml``. Returns the path."""
    _require_yaml()
    if path is None:
        path = os.path.join(spec.path, "session.yaml")
    elif os.path.isdir(path):
        path = os.path.join(path, "session.yaml")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    # Serialise FIRST, write second. Dumping straight to an open file left a
    # truncated session.yaml behind when the dump raised — and a zero-byte
    # session.yaml is worse than none, because the next command believes it.
    text = yaml.safe_dump(_yamlable(_spec_to_dict(spec)), sort_keys=False,
                          default_flow_style=False, allow_unicode=True)
    # A writer must never emit a file that lies when read back: YAML keeps
    # the LAST of two duplicate keys in silence, so a duplicate here becomes
    # someone else's wrong result later. safe_dump from a dict cannot
    # normally produce one — this guards the merge/patch paths that build
    # the spec from several sources, which is where the FAIS duplicates
    # actually came from.
    try:
        from bioscout.devtools import run_check as _rc
        _dups = _rc.duplicate_yaml_keys(text)
        if _dups:
            raise ValueError(
                "refusing to write session.yaml with duplicate keys: "
                + ", ".join(f"{k!r} (lines {a}/{b})" for k, a, b in _dups))
    except ImportError:
        pass
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path



def _find_project_settings(start_dir, levels=6):
    """The nearest ``settings.py`` above ``start_dir``, or None."""
    d = os.path.abspath(start_dir)
    for _ in range(levels):
        p = os.path.join(d, "settings.py")
        if os.path.isfile(p):
            return p
        up = os.path.dirname(d)
        if up == d:
            break
        d = up
    return None


def _load_batch_settings(settings_py):
    """Import a project's ``settings.py`` and hand back its ``BatchSettings``.

    Imported under a private module name so it cannot collide with anything
    the caller has already loaded, and failures are reported rather than
    raised — a scaffold that dies because a project file has an unrelated
    problem is worse than one that falls back to defaults.
    """
    try:
        import importlib.util as _ilu, sys as _sys
        spec_ = _ilu.spec_from_file_location("_bs_project_settings", settings_py)
        mod = _ilu.module_from_spec(spec_)
        _d = os.path.dirname(settings_py)
        if _d not in _sys.path:
            _sys.path.insert(0, _d)
        spec_.loader.exec_module(mod)
        return getattr(mod, "BatchSettings", None)
    except Exception as e:
        print(f"[new-session] {settings_py} not usable "
              f"({type(e).__name__}: {e}); using defaults")
        return None


def body_mass_from_static(session_dir, static_trial=None, gravity=9.80665):
    """Body mass in kg, weighed on the force plates during the static trial.

    The scale in the corner of the lab and the plates under the participant
    disagree — on Athlete_03 by 2.6% (617 N measured against 601 N from the
    entered 61.3 kg), which was enough to double a computed jump height once
    it had been integrated over a two-second task. Everything downstream is
    normalised by this number, so it should come from the instrument the rest
    of the analysis uses.

    Needs the session exported (it reads ``2_experimental/<trial>/grf.mot``).
    When ``static_trial`` is not given, the trial with the steadiest total
    vertical force is used — which is what a static trial IS.
    Returns None when there is nothing to weigh.
    """
    import glob as _glob
    import numpy as _np
    from .movement_detector.mocap import read_grf, _quiet_body_weight

    exp = os.path.join(session_dir, "2_experimental")
    if not os.path.isdir(exp):
        return None

    def _total(trial):
        gm = os.path.join(exp, trial, "grf.mot")
        if not os.path.isfile(gm):
            return None, None
        gt, cols = read_grf(gm)
        vy = [v for c, v in cols.items() if c.endswith("_vy")]
        if not gt.size or not vy:
            return None, None
        return gt, _np.nansum(_np.stack(vy, axis=0), axis=0)

    cands = [static_trial] if static_trial else         sorted(os.path.basename(os.path.dirname(p))
               for p in _glob.glob(os.path.join(exp, "*", "grf.mot")))
    best, best_var = None, None
    for tr in cands:
        if not tr:
            continue
        gt, tot = _total(tr)
        if tot is None or not _np.isfinite(tot).any():
            continue
        # a plate reading nothing is not a person standing on it
        if float(_np.nanmedian(tot)) < 200.0:
            continue
        var = float(_np.nanstd(tot))
        if best_var is None or var < best_var:
            best, best_var = (tr, gt, tot), var
    if best is None:
        return None
    tr, gt, tot = best
    bw = _quiet_body_weight(gt, tot, float(_np.nanmedian(tot)))
    mass = float(bw) / gravity
    print(f"[body-mass] weighed on the plates during {tr!r}: "
          f"{bw:.1f} N -> {mass:.1f} kg")
    return round(mass, 1)


def scaffold_session_yaml(session_dir, template=None, body_mass=None,
                          static_trial=None, overwrite=False):
    """Write a first ``session.yaml`` for a session that has only c3d files.

    A new session arrives as a folder of ``1_c3dfiles/*.c3d`` and nothing else,
    and every downstream step — export included — needs a ``session.yaml`` to
    exist. Hand-writing one invites the small errors that are expensive later
    (a trial missing from ``trials``, a static trial that is not the static
    trial), so it is built here from what is actually on disk and written
    through :func:`write_session_yaml`, the same serialiser the rest of
    bioscout uses.

    * trial names come from the c3d FILENAMES
    * ``static_trial`` is the trial whose name starts with "static", unless
      given
    * ``template`` is an existing session.yaml (or its folder) to copy the
      lab-constant parts from — markerset, EMG map, CEINMS weights. These are
      properties of the laboratory, not of the participant, so copying them is
      right; ``body_mass`` is deliberately NOT copied.

    Trial ``type`` is left unset. Guessing it from the filename would put a
    guess where the pipeline expects a fact — run
    ``bioscout --classifier <session> --write-session-yaml`` afterwards and
    the types come from the data instead.

    Returns the path written, or None if a session.yaml already exists and
    ``overwrite`` is False.
    """
    import glob as _glob
    from .layout import c3d_root

    session_dir = os.path.abspath(session_dir)
    dst = os.path.join(session_dir, "session.yaml")
    # A zero-byte session.yaml is a crash leftover, not a session config, and
    # refusing to overwrite it strands the folder: every later command believes
    # a session.yaml exists and nothing can create a real one.
    if os.path.exists(dst) and os.path.getsize(dst) == 0:
        print(f"[new-session] {dst} is empty (a previous run died) — replacing it.")
        overwrite = True
    if os.path.exists(dst) and not overwrite:
        print(f"[new-session] {dst} already exists — not overwriting.")
        return None

    c3d_dir = c3d_root(session_dir)
    c3ds = sorted(_glob.glob(os.path.join(c3d_dir, "*.c3d")))
    if not c3ds:
        print(f"[new-session] no .c3d files under {c3d_dir}")
        return None
    trials = [os.path.splitext(os.path.basename(p))[0] for p in c3ds]

    if static_trial is None:
        static_trial = next((t for t in trials if t.lower().startswith("static")),
                            None)
        if static_trial is None:
            print("[new-session] no trial named Static* — set --static-trial, or "
                  "edit static_trial afterwards. Scaling needs it.")

    spec = SessionSpec(
        subject=os.path.basename(os.path.dirname(session_dir)),
        session=os.path.basename(session_dir),
        path=session_dir,
        body_mass=body_mass,
        static_trial=static_trial,
        trials={t: {} for t in trials},
    )
    # Where the project is, relative to this file: <project>/simulations/<subject>/<session>
    # unless a settings.py further up says otherwise. Relative, so the session
    # keeps working when the project is copied to another machine.
    _ps = _find_project_settings(session_dir)
    _proj = os.path.dirname(_ps) if _ps else os.path.dirname(os.path.dirname(
        os.path.dirname(session_dir)))
    spec.project_dir = os.path.relpath(_proj, session_dir).replace(os.sep, "/")

    # Lab constants — markerset, EMG map, CEINMS weights — are properties of
    # the LABORATORY, and the project already states them in settings.py. Read
    # them from there first; needing a sibling session to copy from is an
    # accident of history, not a requirement.
    if not template:
        _proj = _find_project_settings(session_dir)
        if _proj:
            _bs = _load_batch_settings(_proj)
            if _bs is not None:
                spec.markerset = getattr(_bs, "markerset", None) or spec.markerset
                spec.setup_folder = (getattr(_bs, "setup_files_folder", None)
                                     or spec.setup_folder)
                _emg = getattr(_bs, "emg_muscle_mapping", None)
                if _emg:
                    spec.emg_muscle_mapping = dict(_emg)
                print(f"[new-session] lab constants from {_proj}")

    if template:
        tpl = template if os.path.isfile(template) \
            else os.path.join(template, "session.yaml")
        if os.path.isfile(tpl):
            src = read_session_yaml(tpl)
            # Lab constants only. Body mass, static trial and trial list belong
            # to THIS session and are never inherited.
            spec.markerset = src.markerset
            spec.setup_folder = src.setup_folder
            spec.emg_muscle_mapping = {k: list(v) for k, v in
                                       (src.emg_muscle_mapping or {}).items()}
            spec.emg_muscle_mappings = {
                n: {k: list(v) for k, v in (b or {}).items()}
                for n, b in (src.emg_muscle_mappings or {}).items()}
            # The template's iterations are NOT copied, so a template with
            # several maps and no default would scaffold a session that cannot
            # be loaded. Pin the template's own default (its first map when it
            # has none) so the new file is valid before any iteration exists.
            spec.default_emg_map = src.default_emg_map
            if spec.emg_muscle_mappings and not spec.default_emg_map:
                spec.default_emg_map = next(iter(spec.emg_muscle_mappings))
            spec.ceinms = dict(src.ceinms or {})
            spec.normalisation_trials = list(src.normalisation_trials or [])
            print(f"[new-session] copied markerset/EMG map/CEINMS from {tpl}")
        else:
            print(f"[new-session] template not found: {tpl} — continuing without")

    path = write_session_yaml(spec, dst)
    print(f"[new-session] wrote {path}")
    print(f"[new-session] {len(trials)} trial(s); static_trial={static_trial!r}; "
          f"body_mass={body_mass!r}")
    if body_mass is None:
        print("[new-session] SET body_mass — anything normalised to body weight "
              "is wrong until you do.")
    print(f"[new-session] next:  bioscout --c3d-export \"{session_dir}\"")
    return path

# ---------------------------------------------------------------------------
# migration helper
# ---------------------------------------------------------------------------
def migrate_calibration_block(yaml_path, *, apply=True, backup=True):
    """Move a top-level ``calibration:`` / ``default_calibration:`` under ``ceinms:``.

    -> ``(changed: bool, note: str)``. Idempotent: a file already nested (or
    with no calibration at all) reports ``(False, ...)`` and is not touched.

    Done with the SURGICAL patcher, not a safe_load/dump round trip: these
    files are hand-written and full of comments explaining why a bound is what
    it is, and re-dumping would silently delete every one of them. The block's
    source text is lifted verbatim, re-indented one level, and re-inserted —
    so a migrated file diffs as a move, which is what it is.
    """
    from bioscout.utils.file_edit import load_document

    _require_yaml()
    doc = load_document(yaml_path)
    with open(yaml_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not uses_legacy_calibration(data):
        return False, f"{yaml_path}: already nested (or no calibration block)"

    def _value_src(key):
        """The VALUE's own source span for a top-level key, or None.

        NOT ``Document.entry_source``: that returns the whole entry — the
        ``key:`` line and any comment attached above it — so feeding it back in
        as a value nests the block under a second copy of its own name.
        Slicing the value node is what ``set_iteration_field`` does, and it is
        the only thing that gives the value alone.
        """
        for knode, vnode in (doc.ynode.value or []):
            if str(knode.value) != str(key):
                continue
            src = doc.text[vnode.start_mark.index:vnode.end_mark.index]
            # The slice begins at the value's COLUMN, so its first line carries
            # no leading spaces while every later line keeps its original
            # indent. Measuring the block's indentation from that would read 0
            # and shift the rest by too much — `prod:` landing at 4 while its
            # sibling `lit:` lands at 6, which is not valid YAML. Pad line one
            # back to where it really starts so all lines are comparable.
            return " " * vnode.start_mark.column + src
        return None

    def _comment_lines_above(key):
        """1-based line numbers of the comment block directly above `key:`.

        Contiguous `#` lines only, stopping at the first blank or code line —
        a comment separated by a blank line is about the file, not about this
        key, and claiming otherwise would be a guess.
        """
        import re as _re
        m = _re.search(rf"^{_re.escape(str(key))}[ \t]*:", doc.text, _re.M)
        if not m:
            return []
        upto = doc.text[:m.start()].splitlines()
        out = []
        for i in range(len(upto) - 1, -1, -1):
            if upto[i].lstrip().startswith("#"):
                out.append(i + 1)
            else:
                break
        return sorted(out)

    moved = []
    key = ("calibration" if "calibration" in data
           else "calibration_params" if "calibration_params" in data else None)
    orphans = sorted(set(
        (_comment_lines_above(key) if key else [])
        + (_comment_lines_above(DEFAULT_CALIBRATION_KEY)
           if DEFAULT_CALIBRATION_KEY in data else [])))

    # Read BOTH sources before writing anything: every mutation reparses the
    # document, which invalidates node objects and shifts every offset. Capture
    # first, then mutate, re-fetching the root each time.
    block_src = _value_src(key) if key else None
    dflt_src = (_value_src(DEFAULT_CALIBRATION_KEY)
                if DEFAULT_CALIBRATION_KEY in data else None)

    if key is not None:
        if block_src is None:
            return False, f"{yaml_path}: could not read the `{key}:` block"
        doc.set_entry_source(doc.ensure_mapping("ceinms"), "calibration",
                             _reindent_value(block_src, 4))
        doc.delete_entry(doc.ynode, key)
        moved.append(key)

    if DEFAULT_CALIBRATION_KEY in data:
        src = dflt_src if dflt_src is not None else str(
            data[DEFAULT_CALIBRATION_KEY])
        # add_entry writes "key: {src}" — it supplies the space itself, so a
        # leading one here produces "default_calibration:  prod".
        doc.set_entry_source(doc.ensure_mapping("ceinms"),
                             DEFAULT_CALIBRATION_KEY,
                             src if "\n" in src else src.strip())
        doc.delete_entry(doc.ynode, DEFAULT_CALIBRATION_KEY)
        moved.append(DEFAULT_CALIBRATION_KEY)

    if not moved:
        return False, f"{yaml_path}: nothing to move"
    if not apply:
        return True, doc.diff()
    doc.save(backup=backup)
    _LEGACY_CALIBRATION_WARNED.discard(str(yaml_path))

    note = f"{yaml_path}: moved {', '.join(moved)} under `ceinms:`"
    if orphans:
        # The keys move; a comment written ABOVE them does not — Document's
        # entry bounds stop at the key line. Nothing is lost, but a paragraph
        # explaining why a bound is what it is now sits above whatever follows
        # it, which is worse than useless if nobody is told. Name the lines.
        note += (f"\n  NOTE: {len(orphans)} comment line(s) that sat above the "
                 f"moved key(s) stayed put — line(s) "
                 f"{', '.join(str(n) for n in orphans)} of the ORIGINAL file. "
                 f"Move them next to `ceinms.calibration` by hand.")
    return True, note


def _reindent_value(src: str, indent: int) -> str:
    """Re-indent a mapping value's source so it sits `indent` spaces deep.

    A block value's source arrives with the indentation it had at its old
    depth. Shifting by the DIFFERENCE (rather than prepending a fixed pad)
    keeps the block's internal structure — a nested `prod:` two levels down
    stays two levels below its parent.
    """
    lines = src.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        return src
    body = [ln for ln in lines if ln.strip()]
    if not body:
        return src
    cur = min(len(ln) - len(ln.lstrip(" ")) for ln in body)
    shift = indent - cur
    if shift == 0:
        return "\n" + "\n".join(lines)
    out = []
    for ln in lines:
        if not ln.strip():
            out.append(ln)
        elif shift > 0:
            out.append(" " * shift + ln)
        else:
            out.append(ln[min(-shift, len(ln) - len(ln.lstrip(" "))):])
    return "\n" + "\n".join(out)


__all__ = ["read_session_yaml", "write_session_yaml",
           "ITERATION_KEYS", "ITERATION_KEY_RENAMES", "ITERATION_FILE_KEYS",
           "SESSION_KEYS", "yaml_key_line", "SessionKeys", "IterationKeys", "ceinms_for",
           "ITERATION_KEYS_REMOVED",
           "normalise_iterations",
           "emg_maps", "resolve_emg_map", "emg_map_name_for",
           "is_named_emg_map", "DEFAULT_EMG_MAP_KEY",
           "calibration_configs", "resolve_calibration",
           "calibration_name_for", "is_named_calibration",
           "DEFAULT_CALIBRATION_KEY", "CALIBRATION_PARAM_NAMES",
           "migrate_calibration_block", "uses_legacy_calibration",
           "CALIBRATION_OPTIMISER_NAMES", "yaml_bool"]




try:                                     # available whenever pyyaml is
    from yaml import SafeLoader as _yaml_SafeLoader, resolver as _yaml_resolver
except Exception:                        # pyyaml optional -> _require_yaml() reports it
    _yaml_SafeLoader, _yaml_resolver = object, None


class _StrictLoader(_yaml_SafeLoader):
    """SafeLoader that refuses duplicate mapping keys.

    PyYAML's default silently keeps the LAST value for a repeated key. In a
    session.yaml that means two iterations called `gpk` collapse into one with
    no warning — the first block's generic model, colour and CEINMS settings
    just vanish, and the run looks fine. This turns that into an error naming
    the key and the line.
    """


def _no_duplicate_keys(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            mark = key_node.start_mark
            raise ValueError(
                f"duplicate key {key!r} in {mark.name} at line {mark.line + 1}. "
                "YAML would silently keep only the last one — rename or merge "
                "the entries."
            )
        mapping[key] = True
    return _yaml_SafeLoader.construct_mapping(loader, node, deep=deep)


_StrictLoader.add_constructor(
    _yaml_resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicate_keys
)


def load_session_yaml(path):
    """Parse a session.yaml, rejecting duplicate keys and colliding iterations.

    Two failure modes YAML itself will not catch:
      * a repeated key (two `gpk:` blocks) — silently last-wins;
      * iteration names differing only by case (`GPK` and `gpk`) — distinct in
        YAML but the same folder on Windows, so they overwrite each other's
        results.

    It also resolves every iteration's `emg_map` selector, so a typo'd or
    ambiguous mapping name fails here rather than several hours into a run
    with the wrong electrode set.
    """
    _require_yaml()
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.load(f, Loader=_StrictLoader) or {}
    _check_iteration_names(data, path)
    _check_emg_maps(data, path)
    _check_calibration(data, path)
    return data


def _check_iteration_names(data, path):
    names = list((data or {}).get("iterations") or {})
    seen = {}
    for n in names:
        key = str(n).strip().lower()
        if key in seen:
            raise ValueError(
                f"iterations {seen[key]!r} and {n!r} in {path} differ only by "
                "case or whitespace — on Windows they are the same folder and "
                "would overwrite each other. Give them distinct names."
            )
        seen[key] = n
    return names
