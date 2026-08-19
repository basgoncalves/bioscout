"""bioscout.utils.session — the single home for everything session-related.

Consolidates what used to live in utils/session_config.py, utils/session_yaml.py,
utils/session_layout.py and core/session_manager.py, plus the canonical
path-based :class:`Session` (was bioscout/session.py + utils/analysis.Session).

Layout the Session understands::

    simulations/<athlete>/<session>/<iteration>/<trial>/...

Raw model-INDEPENDENT inputs (markers / grf / emg / GRF.xml) are SHARED across
iterations and read from ``<session>/experimental/<trial>/``.
"""
from __future__ import annotations

import os
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

from bioscout.utils.analysis import Analyse

# ===========================================================================
# CONFIG  (inlined from utils/session_config.py)
# ===========================================================================
"""Session-centric data model (BioScout 2.x restructuring).

A **session** owns its raw motion data (``c3dfiles/``) and one or more **model
iterations** (``models/*.osim``). Every model is analysed over the SAME trials
and compared, so a session is the unit of organisation — NOT the model.

  * ``Model``       — one model iteration + its (optional) scale recipe.
  * ``SessionSpec`` — subject/session/path + shared config + ``models[]`` + per-trial windows.
  * ``read_session_xml`` / ``write_session_xml`` — the single ``session.xml`` per session.
  * ``discover_session_specs`` — walk ``simulations/`` and build ``SessionSpec`` objects.

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
    """One model iteration within a session.

    ``model`` / ``model_ceinms`` are the .osim used for analysis (paths relative
    to the session folder, e.g. ``models/scaled_opt_N10_mvicx3.00.osim``). The
    remaining fields are the SCALE RECIPE — inputs to the standalone ``scale``
    step that PRODUCES the .osim; analysis ignores them."""
    name: str
    model: Optional[str] = None            # analysis/SO model (rel. to session)
    model_ceinms: Optional[str] = None     # CEINMS model (defaults to ``model``)
    label: Optional[str] = None
    color: str = "black"
    group: Optional[str] = None
    # --- scale recipe (model creation only) ---
    generic_model: Optional[str] = None
    session_model: Optional[str] = None    # provided, already-personalised .osim (MRI/TPS);
                                           # present -> skip geometric scaling (use this instead)
    static_trial: Optional[str] = None
    marker_weights: Dict[str, float] = field(default_factory=dict)
    preserve_mass_distribution: bool = True
    linear_scaling: bool = True            # ScaleTool ModelScaler (dimensional scaling)
    marker_placer: bool = False            # ScaleTool MarkerPlacer (place markers to static)
    prescaled: bool = False                # use session_model AS-IS: no scaling, no marker
                                           # placement, no muscle-opt. CEINMS = the model,
                                           # SO = the model with isometric force x mvic_factor
    mvic_factor: Optional[float] = None
    opt_neval: Optional[int] = None
    emg_map: Optional[str] = None          # NAME of a mapping under the session-wide
                                           # emg_map; only needed when several exist
    calibration: Optional[str] = None      # NAME of a config under the session-wide
                                           # calibration block; same rules as emg_map

    def __post_init__(self):
        if self.label is None:
            self.label = self.name
        if self.model_ceinms is None:
            self.model_ceinms = self.model


# ---------------------------------------------------------------------------
@dataclass
class SessionSpec:
    """One session: identity + shared config + its model iterations + per-trial
    windows. Built from a ``session.xml`` (see ``read_session_xml``)."""
    subject: str
    session: str = ""
    path: Optional[str] = None             # absolute session folder
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
        from .session_layout import c3d_root
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


# ---------------------------------------------------------------------------
# session.xml  <-> SessionSpec
# ---------------------------------------------------------------------------
def _to_floats(text):
    return [float(x) for x in str(text).split()] if text else []


def read_session_xml(path) -> SessionSpec:
    """Parse a ``session.xml`` into a :class:`SessionSpec`. ``path`` may be the
    xml file or the session folder containing it."""
    if os.path.isdir(path):
        path = os.path.join(path, "session.xml")
    root = ET.parse(path).getroot()
    sess = SessionSpec(
        subject=root.get("subject", ""),
        session=root.get("session", ""),
        path=os.path.dirname(os.path.abspath(path)),
        body_mass=(float(root.findtext("body_mass")) if root.findtext("body_mass") else None),
        static_trial=root.findtext("static_trial") or root.get("static_trial"),
        setup_folder=root.findtext("setup_folder"),
        markerset=root.findtext("markerset"),
        c3d_source=root.findtext("c3d_source"),
    )
    # models
    for m in root.findall("./models/model"):
        mw = {}
        for w in m.findall("./marker_weights/weight"):
            try:
                mw[w.get("segment")] = float(w.get("value"))
            except (TypeError, ValueError):
                pass
        sess.models.append(Model(
            name=m.get("name"),
            model=m.get("file"),
            model_ceinms=m.get("ceinms"),
            label=m.get("label"),
            color=m.get("color", "black"),
            group=m.get("group"),
            generic_model=m.get("generic"),
            static_trial=m.get("static_trial"),
            emg_map=m.get("emg_map"),
            marker_weights=mw,
            preserve_mass_distribution=(m.get("preserve_mass_distribution", "true").lower()
                                        not in ("false", "0", "no")),
            mvic_factor=(float(m.get("mvic")) if m.get("mvic") else None),
            opt_neval=(int(m.get("opt_neval")) if m.get("opt_neval") else None),
        ))
    # session-wide EMG mapping
    for ch in root.findall("./emg_muscle_mapping/channel"):
        sess.emg_muscle_mapping[ch.get("id")] = (ch.text or "").split()
    # CEINMS params (attributes)
    ce = root.find("ceinms")
    if ce is not None:
        sess.ceinms = dict(ce.attrib)
    # session-wide trial selections. Accept either a `trials="a b c"` attribute
    # or nested <trial name="a"/> children; whitespace/comma separated.
    def _trial_names(elem):
        if elem is None:
            return []
        names = []
        attr = elem.get("trials")
        if attr:
            names += [n for n in attr.replace(",", " ").split()]
        names += [t.get("name") for t in elem.findall("./trial") if t.get("name")]
        # de-dup, preserve order
        seen, out = set(), []
        for n in names:
            if n not in seen:
                seen.add(n); out.append(n)
        return out
    sess.normalisation_trials = _trial_names(root.find("normalisation"))
    sess.calibration_trials = _trial_names(root.find("calibration"))
    # per-trial windows/events
    for t in root.findall("./trials/trial"):
        entry = {}
        if t.get("type"):
            entry["type"] = t.get("type")
        if t.get("time_range"):
            entry["time_range"] = _to_floats(t.get("time_range"))
        if t.get("events"):
            entry["events"] = _to_floats(t.get("events"))
        sess.trials[t.get("name")] = entry
    return sess


def write_session_xml(spec: SessionSpec, path=None) -> str:
    """Serialise a :class:`SessionSpec` to ``session.xml``. Returns the path."""
    if path is None:
        path = os.path.join(spec.path, "session.xml")
    elif os.path.isdir(path):
        path = os.path.join(path, "session.xml")
    root = ET.Element("session", subject=spec.subject or "", session=spec.session or "")
    if spec.body_mass is not None:
        ET.SubElement(root, "body_mass").text = repr(spec.body_mass)
    if spec.static_trial:
        ET.SubElement(root, "static_trial").text = spec.static_trial
    if spec.setup_folder:
        ET.SubElement(root, "setup_folder").text = spec.setup_folder
    if spec.markerset:
        ET.SubElement(root, "markerset").text = spec.markerset
    if spec.c3d_source:
        ET.SubElement(root, "c3d_source").text = spec.c3d_source
    ms = ET.SubElement(root, "models")
    for m in spec.models:
        attrs = {"name": m.name or ""}
        if m.model:        attrs["file"] = m.model
        if m.model_ceinms: attrs["ceinms"] = m.model_ceinms
        if m.label:        attrs["label"] = m.label
        if m.color:        attrs["color"] = m.color
        if m.group:        attrs["group"] = m.group
        if m.generic_model:attrs["generic"] = m.generic_model
        if m.static_trial: attrs["static_trial"] = m.static_trial
        if m.mvic_factor is not None:  attrs["mvic"] = f"{m.mvic_factor}"
        if m.opt_neval is not None:    attrs["opt_neval"] = f"{m.opt_neval}"
        if m.emg_map:      attrs["emg_map"] = m.emg_map
        attrs["preserve_mass_distribution"] = "true" if m.preserve_mass_distribution else "false"
        me = ET.SubElement(ms, "model", attrs)
        if m.marker_weights:
            mw = ET.SubElement(me, "marker_weights")
            for seg, val in m.marker_weights.items():
                ET.SubElement(mw, "weight", segment=str(seg), value=str(val))
    if spec.emg_muscle_mapping:
        # session.xml is the legacy format and has no place for NAMED maps, so
        # only the default survives the trip. Say so rather than writing a file
        # that looks complete and quietly lost two thirds of the config.
        if len(spec.emg_muscle_mappings or {}) > 1:
            print(f"[session.xml] WARNING: {sorted(spec.emg_muscle_mappings)} "
                  "named emg_maps cannot be represented in XML — writing only "
                  f"{spec.default_emg_map or 'the first'}. Keep session.yaml as "
                  "the source of truth.")
        em = ET.SubElement(root, "emg_muscle_mapping")
        for ch, muscles in spec.emg_muscle_mapping.items():
            ET.SubElement(em, "channel", id=str(ch)).text = " ".join(muscles)
    if spec.ceinms:
        ET.SubElement(root, "ceinms", {k: str(v) for k, v in spec.ceinms.items()})
    # session-wide trial selections
    if spec.normalisation_trials:
        ET.SubElement(root, "normalisation", {"trials": " ".join(spec.normalisation_trials)})
    if spec.calibration_trials:
        ET.SubElement(root, "calibration", {"trials": " ".join(spec.calibration_trials)})
    if spec.trials:
        ts = ET.SubElement(root, "trials")
        for tname, entry in spec.trials.items():
            attrs = {"name": tname}
            if entry.get("type"):
                attrs["type"] = str(entry["type"])
            if entry.get("time_range"):
                attrs["time_range"] = " ".join(str(x) for x in entry["time_range"])
            if entry.get("events"):
                attrs["events"] = " ".join(str(x) for x in entry["events"])
            ET.SubElement(ts, "trial", attrs)
    try:
        ET.indent(root)  # py3.9+
    except Exception:
        pass
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return path


# ---------------------------------------------------------------------------


def body_mass_from_static(grf_mot, g=9.81, vertical_suffix="vy", window=None):
    """Body mass (kg) from a STATIC trial's ground-reaction file: mean total
    vertical force / g over a quiet window. ``vertical_suffix`` matches the
    vertical GRF columns (default ``vy``; all matching plates are summed).
    ``window`` optionally restricts to ``(t0, t1)`` seconds. Returns None if the
    file/columns are unreadable."""
    try:
        import numpy as np
    except Exception:
        return None
    if not grf_mot or not os.path.isfile(grf_mot):
        return None
    # Parse a simple OpenSim .mot / .sto (header ending at 'endheader', then a
    # column-name row, then whitespace-separated numeric rows).
    with open(grf_mot, "r", errors="replace") as f:
        lines = f.read().splitlines()
    hdr = next((i for i, l in enumerate(lines) if l.strip().lower() == "endheader"), None)
    start = (hdr + 1) if hdr is not None else 0
    while start < len(lines) and not lines[start].strip():
        start += 1
    if start >= len(lines):
        return None
    cols = lines[start].split()
    data = []
    for l in lines[start + 1:]:
        if not l.strip():
            continue
        try:
            data.append([float(x) for x in l.split()])
        except ValueError:
            continue
    if not data:
        return None
    arr = np.array(data, dtype=float)
    cl = [c.lower() for c in cols]
    tcol = cl.index("time") if "time" in cl else 0
    vcols = [i for i, c in enumerate(cl) if c.endswith(vertical_suffix.lower())]
    if not vcols:
        return None
    if window and tcol is not None:
        t = arr[:, tcol]
        m = (t >= window[0]) & (t <= window[1])
        if m.any():
            arr = arr[m]
    total_vert = arr[:, vcols].sum(axis=1)
    mean_force = float(np.nanmean(total_vert))
    mass = mean_force / g
    return mass if mass > 0 else None




# =========================================================================
# YAML  (inlined from utils/session_yaml.py)
# =========================================================================
"""YAML session configuration for BioScout (2.x session-centric layout).

Human-authored config is YAML; the tool-facing files (OpenSim/CEINMS setups,
.osim) stay XML because those are *generated*, never hand-edited. This module
reads/writes a ``session.yaml`` into the SAME :class:`SessionSpec` / :class:`Model`
dataclasses used by :mod:`bioscout.utils.session_config`, so YAML is a drop-in
alternative to ``session.xml`` — nothing else in the pipeline needs to change.

A session owns its RAW data once (``trials/``) and one or more ITERATIONS (model
variants) analysed over the same trials. Each iteration carries its own scale
recipe (generic model, muscle-optimiser N, MVIC factor, marker weights) so it can
be rebuilt and labelled by the summary.

Example ``session.yaml``::

    subject: Athlete_03
    session: "25_03_31"
    body_mass: 89.9
    static_trial: Static_01
    markerset: setup/markers_powerlifter.xml
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
        generic: Catelli.osim
        model: models/cateli/scaled_opt_N10_mvicx3.00.osim
        model_ceinms: models/cateli/scaled_opt_N10.osim
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


def _raw_calibration(cfg):
    if not isinstance(cfg, dict):
        return {}
    raw = cfg.get("calibration", cfg.get("calibration_params"))
    return raw if isinstance(raw, dict) else {}


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
    return _select_name(cfg, iteration, blocks=calibration_configs(cfg),
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
    ce = cfg.get("ceinms") or {}
    return yaml_bool(it.get("calibrated", ce.get("calibrated", True)))


def _check_calibration(data, path):
    """Load-time validation of `calibration` and every iteration's selector."""
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
    data = load_session_yaml(path)

    spec = SessionSpec(
        subject=str(data.get("subject", "") or ""),
        session=str(data.get("session", "") or ""),
        path=os.path.dirname(os.path.abspath(path)),
        body_mass=(float(data["body_mass"]) if data.get("body_mass") is not None else None),
        static_trial=data.get("static_trial"),
        setup_folder=data.get("setup_folder"),
        markerset=data.get("markerset"),
        c3d_source=data.get("c3d_source"),
    )

    # iterations (aka models) — accept a mapping {name: {...}} or a list [{name:..}]
    iterations = data.get("iterations", data.get("models", {})) or {}
    items = (iterations.items() if isinstance(iterations, dict)
             else [(m.get("name"), m) for m in iterations])
    for name, m in items:
        m = dict(m or {})
        spec.models.append(Model(
            name=name or m.get("name"),
            # explicit output model filenames (as authored, like the old GROUPS):
            #   so_model     -> Model.model        (strength-increased, used by SO)
            #   ceinms_model -> Model.model_ceinms (base, used by CEINMS)
            model=m.get("so_model", m.get("model")),
            model_ceinms=m.get("ceinms_model", m.get("model_ceinms")),
            label=m.get("label"),
            color=m.get("color", "black"),
            group=m.get("group"),
            generic_model=m.get("generic", m.get("generic_model")),
            # uniform: every iteration may declare a provided model
            # (session-relative, already personalised).
            session_model=m.get("session_model"),
            static_trial=m.get("static_trial"),
            marker_weights={str(k): float(v) for k, v in (m.get("marker_weights") or {}).items()},
            preserve_mass_distribution=bool(m.get("preserve_mass_distribution", True)),
            linear_scaling=bool(m.get("linear_scaling", True)),
            marker_placer=bool(m.get("marker_placer", False)),
            prescaled=bool(m.get("prescaled", False)),   # use session_model AS-IS (no scale/opt)
            mvic_factor=(float(m["mvic_factor"]) if m.get("mvic_factor") is not None else None),
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
    spec.normalisation_trials = _as_list(data.get("normalisation_trials"))
    spec.calibration_trials = _as_list(data.get("calibration_trials"))

    for tname, entry in (data.get("trials") or {}).items():
        entry = dict(entry or {})
        out = {}
        if entry.get("type"):
            out["type"] = entry["type"]
        if entry.get("time_range") is not None:
            out["time_range"] = [float(x) for x in entry["time_range"]]
        if entry.get("events") is not None:
            out["events"] = [float(x) for x in entry["events"]]
        spec.trials[str(tname)] = out
    return spec


# ---------------------------------------------------------------------------
# SessionSpec  ->  session.yaml
# ---------------------------------------------------------------------------
def _spec_to_dict(spec: SessionSpec) -> dict:
    d: dict = {}
    if spec.subject:      d["subject"] = spec.subject
    if spec.session:      d["session"] = spec.session
    if spec.body_mass is not None: d["body_mass"] = spec.body_mass
    if spec.static_trial: d["static_trial"] = spec.static_trial
    if spec.setup_folder: d["setup_folder"] = spec.setup_folder
    if spec.markerset:    d["markerset"] = spec.markerset
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
            if m.generic_model:   it["generic"] = m.generic_model
            if m.session_model:   it["session_model"] = m.session_model
            if not m.linear_scaling: it["linear_scaling"] = False
            if m.marker_placer:      it["marker_placer"] = True
            if m.opt_neval is not None:   it["opt_neval"] = m.opt_neval
            if m.mvic_factor is not None: it["mvic_factor"] = m.mvic_factor
            if m.static_trial:  it["static_trial"] = m.static_trial
            if m.marker_weights: it["marker_weights"] = dict(m.marker_weights)
            if not m.preserve_mass_distribution:
                it["preserve_mass_distribution"] = False
            if m.emg_map:      it["emg_map"] = m.emg_map
            if m.calibration:  it["calibration"] = m.calibration
            if m.model_ceinms: it["ceinms_model"] = m.model_ceinms
            if m.model:        it["so_model"] = m.model
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
        from . import run_check as _rc
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
    from ..movement_detector.mocap import read_grf, _quiet_body_weight

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
    from .session_layout import c3d_root

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
def convert_session_xml_to_yaml(xml_path, yaml_path=None, keep_xml=True) -> str:
    """Read an existing ``session.xml`` and write the equivalent ``session.yaml``
    next to it (unless ``yaml_path`` is given). Non-destructive: the xml is left
    in place unless ``keep_xml=False``. Returns the yaml path."""
    spec = read_session_xml(xml_path)
    if yaml_path is None:
        base = xml_path if os.path.isfile(xml_path) else os.path.join(xml_path, "session.xml")
        yaml_path = os.path.splitext(base)[0] + ".yaml"
    out = write_session_yaml(spec, yaml_path)
    if not keep_xml:
        src = xml_path if os.path.isfile(xml_path) else os.path.join(xml_path, "session.xml")
        try:
            os.remove(src)
        except OSError:
            pass
    return out


def read_session(path) -> SessionSpec:
    """Load a session config, preferring YAML then falling back to XML. ``path``
    may be a session folder or a specific file."""
    if os.path.isdir(path):
        for name in ("session.yaml", "session.yml"):
            if os.path.isfile(os.path.join(path, name)):
                return read_session_yaml(os.path.join(path, name))
        return read_session_xml(path)          # xml fallback
    return (read_session_yaml(path) if str(path).lower().endswith((".yaml", ".yml"))
            else read_session_xml(path))


__all__ = ["read_session_yaml", "write_session_yaml",
           "convert_session_xml_to_yaml", "read_session",
           "emg_maps", "resolve_emg_map", "emg_map_name_for",
           "is_named_emg_map", "DEFAULT_EMG_MAP_KEY",
           "calibration_configs", "resolve_calibration",
           "calibration_name_for", "is_named_calibration",
           "DEFAULT_CALIBRATION_KEY", "CALIBRATION_PARAM_NAMES",
           "CALIBRATION_OPTIMISER_NAMES", "yaml_bool"]

# canonical reader alias (fixes a broken import in the old session_layout)
read_session = read_session_yaml


# =========================================================================
# LAYOUT  (inlined from utils/session_layout.py)
# =========================================================================
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

import os
import shutil
import time



def grf_events_cropped(session_path, trials=None):
    """For each trial with a ``time_range`` in session.yaml, write a
    ``experimental/<trial>/grf_events_cropped.png`` = per-foot vertical GRF
    limited to that window (full-trial trace greyed, window shaded/coloured).
    Returns the list of figures written."""
    import numpy as _np, pandas as _pd, xml.etree.ElementTree as _ET, re as _re
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as _plt
    from bioscout import utils as _u
    session_path = os.path.abspath(session_path)
    spec = read_session(session_path)
    made = []
    for tn, meta in (spec.trials or {}).items():
        tr = (meta or {}).get("time_range")
        if not (isinstance(tr, (list, tuple)) and len(tr) == 2):
            continue
        tdir = experimental_dir(session_path, tn)
        gp = os.path.join(tdir, "grf.mot")
        if not os.path.exists(gp) or (trials and tn not in trials):
            continue
        try:
            grf = _u.load_any_data_file(gp)
            t = _pd.to_numeric(grf["time"], errors="coerce").to_numpy(float)
            foot = {}
            try:
                root = _ET.parse(os.path.join(tdir, "GRF.xml")).getroot()
                for ef in root.iter("ExternalForce"):
                    body = (ef.findtext("applied_to_body") or "").strip()
                    m = _re.search(r"(\d+)", (ef.findtext("force_identifier") or ""))
                    if m and body.startswith("calcn_"):
                        foot[int(m.group(1))] = body.split("_")[-1]
            except Exception:
                pass
            def _sum(side):
                cols = [f"ground_force_{p}_vy" for p, s in foot.items()
                        if s == side and f"ground_force_{p}_vy" in grf.columns]
                return (_np.sum([_pd.to_numeric(grf[c], errors="coerce").to_numpy(float)
                                 for c in cols], axis=0) if cols else _np.zeros_like(t))
            vyR, vyL = _sum("r"), _sum("l")
            t0, t1 = float(tr[0]), float(tr[1])
            fig, ax = _plt.subplots(figsize=(11, 5.2))
            ax.plot(t, vyR, color="0.75", lw=1.0); ax.plot(t, vyL, color="0.85", lw=1.0)
            _in = (t >= t0) & (t <= t1)
            ax.plot(t[_in], vyR[_in], color="tab:red", lw=2.0, label="Right foot Fy")
            ax.plot(t[_in], vyL[_in], color="tab:blue", lw=2.0, label="Left foot Fy")
            ax.axvspan(t0, t1, color="tab:green", alpha=0.10, label=f"analysis window [{t0:.2f}, {t1:.2f}] s")
            ax.axvline(t0, color="tab:green", ls="--", lw=1); ax.axvline(t1, color="tab:green", ls="--", lw=1)
            ax.set_xlim(max(t.min(), t0 - 0.15), min(t.max(), t1 + 0.15))
            ax.set_xlabel("Time (s)"); ax.set_ylabel("Vertical GRF Fy (N)")
            ax.set_title(f"{tn} — vertical GRF (analysis window {t0:.2f}-{t1:.2f} s)")
            ax.legend(fontsize=9)
            fig.tight_layout()
            out = os.path.join(tdir, "grf_events_cropped.png")
            fig.savefig(out, dpi=130); _plt.close(fig); made.append(out)
            print(f"  [ok] {tn} grf_events_cropped saved: {out}", flush=True)
        except Exception as e:
            print(f"  [grf_events_cropped] {tn}: warn — {e}", flush=True)
    return made


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
# Folder names are resolved through `session_layout`, which understands both the
# numbered layout (1_c3dfiles / 2_experimental / 3_iterations/<name>) and the
# older flat one, preferring whatever exists on disk. Never join these names by
# hand — that is what keeps the two layouts from drifting apart.
from . import session_layout as _layout

# Which experimental subfolder the runners read raw inputs from. Normally the
# session's own (1_/2_-numbered or plain); a downsample run points this at e.g.
# "experimental_ds10", which is then used verbatim.
_EXP_SUBDIR = None

def experimental_dir(session_dir, trial):
    return os.path.join(_layout.experimental_root(session_dir, _EXP_SUBDIR), trial)

def c3d_path(session_dir, trial):
    return os.path.join(_layout.c3d_root(session_dir), f"{trial}.c3d")

def iteration_dir(session_dir, iteration):
    return _layout.iteration_path(session_dir, iteration)

def derived_trial_dir(session_dir, iteration, trial):
    return os.path.join(_layout.iteration_path(session_dir, iteration), trial)

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




# ---------------------------------------------------------------------------
# scaling: build one iteration's model.osim / model_so.osim from its recipe
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# run one iteration over all trials (SO stage), reading shared experimental/
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# import already-scaled models from the OLD models/<subject>/<session>/ layout
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# CEINMS for one iteration over all trials (new layout)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# top-level driver
# ---------------------------------------------------------------------------




__all__ = ["summarise_session",
           "grf_events_cropped", "downsample_experimental",
           "bind_experimental", "experimental_dir", "iteration_dir",
           "derived_trial_dir", "c3d_path", "resolve_generic", "resolve_session_model",
           "load_session_yaml"]


# =========================================================================
# VALIDATION  (inlined from core/session_manager.py)
# =========================================================================
"""
Session Manager - Handles session-level operations and trial discovery.
Version: 1.0.0
"""

import os
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import json


class TrialValidator:
    """Validates trial folders for required input files."""

    # Required files for different analysis types
    BASIC_REQUIREMENTS = {
        'c3d': 'c3dfile.c3d',
        'markers': 'marker_experimental.trc',
        'grf': 'grf.mot',
    }

    CEINMS_REQUIREMENTS = {
        'c3d': 'c3dfile.c3d',
        'markers': 'marker_experimental.trc',
        'grf': 'grf.mot',
        'grf_xml': 'GRF.xml',
        'model': 'scaled_*.osim',  # Pattern match for scaled model
    }

    EMG_REQUIREMENTS = {
        'emg_filtered': 'EMG_filtered_normalised*.sto',
    }

    @staticmethod
    def has_file(trial_dir: Path, filename: str, session_dir: Path = None) -> bool:
        """Check if a file exists in trial directory or session root (supports glob patterns)."""
        if '*' in filename:
            # Pattern matching
            import glob
            pattern = os.path.join(str(trial_dir), filename)
            return len(glob.glob(pattern)) > 0
        else:
            # Check trial folder first
            if (trial_dir / filename).exists():
                return True

            # For C3D files, also check session root with trial name
            if filename == 'c3dfile.c3d' and session_dir:
                trial_name = trial_dir.name
                c3d_file = session_dir / f"{trial_name}.c3d"
                if c3d_file.exists():
                    return True

            return False

    @staticmethod
    def validate_trial(trial_dir: Path, requirements: Dict[str, str], session_dir: Path = None) -> Dict[str, bool]:
        """Validate if trial has all required files."""
        results = {}
        for req_name, filename in requirements.items():
            results[req_name] = TrialValidator.has_file(trial_dir, filename, session_dir)
        return results

    @staticmethod
    def is_valid_trial(trial_dir: Path, session_dir: Path = None) -> bool:
        """Check if folder is a valid trial (has C3D or TRC file)."""
        # Check for TRC file in trial folder
        if TrialValidator.has_file(trial_dir, 'marker_experimental.trc', session_dir):
            return True

        # Check for C3D file in session root with trial name
        if session_dir:
            trial_name = trial_dir.name
            c3d_file = session_dir / f"{trial_name}.c3d"
            if c3d_file.exists():
                return True

        # Check for C3D file in trial folder (backward compatibility)
        return TrialValidator.has_file(trial_dir, 'c3dfile.c3d', session_dir)

    @staticmethod
    def get_trial_status(trial_dir: Path, session_dir: Path = None) -> Dict[str, any]:
        """Get complete validation status for a trial."""
        trial_name = trial_dir.name
        basic_valid = TrialValidator.validate_trial(trial_dir, TrialValidator.BASIC_REQUIREMENTS, session_dir)
        ceinms_valid = TrialValidator.validate_trial(trial_dir, TrialValidator.CEINMS_REQUIREMENTS, session_dir)
        emg_valid = TrialValidator.validate_trial(trial_dir, TrialValidator.EMG_REQUIREMENTS, session_dir)

        basic_complete = all(basic_valid.values())
        ceinms_complete = all(ceinms_valid.values())
        emg_complete = all(emg_valid.values())

        return {
            'name': trial_name,
            'path': str(trial_dir),
            'is_valid_trial': TrialValidator.is_valid_trial(trial_dir, session_dir),
            'basic_complete': basic_complete,
            'ceinms_complete': ceinms_complete,
            'emg_complete': emg_complete,
            'basic_files': basic_valid,
            'ceinms_files': ceinms_valid,
            'emg_files': emg_valid,
            'status_color': 'green' if ceinms_complete else 'red',
        }


class SessionManager:
    """Manages session-level operations and trial discovery."""

    VERSION = "1.0.0"

    def __init__(self, session_path: Optional[str] = None):
        """Initialize session manager."""
        self.session_path = Path(session_path) if session_path else None
        self.trials = []
        self.session_name = self.session_path.name if self.session_path else None

    def discover_trials(self) -> List[Path]:
        """Discover all trial folders in session (containing C3D or TRC files)."""
        if not self.session_path or not self.session_path.exists():
            return []

        trials = []
        for item in sorted(self.session_path.iterdir()):
            if item.is_dir() and TrialValidator.is_valid_trial(item, self.session_path):
                trials.append(item)

        self.trials = trials
        return trials

    def get_trial_list(self) -> List[Dict]:
        """Get list of trials with their status information."""
        if not self.trials:
            self.discover_trials()

        trial_list = []
        for trial_path in self.trials:
            status = TrialValidator.get_trial_status(trial_path, self.session_path)
            trial_list.append(status)

        return trial_list

    def get_trial_by_name(self, trial_name: str) -> Optional[Path]:
        """Get trial path by name."""
        if not self.trials:
            self.discover_trials()

        for trial_path in self.trials:
            if trial_path.name == trial_name:
                return trial_path
        return None

    def validate_for_analysis(self, trial_name: str) -> Tuple[bool, str]:
        """Validate if trial is ready for analysis."""
        trial_path = self.get_trial_by_name(trial_name)
        if not trial_path:
            return False, f"Trial '{trial_name}' not found"

        status = TrialValidator.get_trial_status(trial_path, self.session_path)
        if status['basic_complete']:
            return True, "Trial ready for analysis"
        else:
            missing = [k for k, v in status['basic_files'].items() if not v]
            return False, f"Trial missing required files: {', '.join(missing)}"

    def validate_for_ceinms(self, trial_name: str) -> Tuple[bool, str]:
        """Validate if trial is ready for CEINMS calibration."""
        trial_path = self.get_trial_by_name(trial_name)
        if not trial_path:
            return False, f"Trial '{trial_name}' not found"

        status = TrialValidator.get_trial_status(trial_path, self.session_path)
        if status['ceinms_complete']:
            return True, "Trial ready for CEINMS calibration"
        else:
            missing = [k for k, v in status['ceinms_files'].items() if not v]
            return False, f"Trial missing CEINMS files: {', '.join(missing)}"

    def get_session_summary(self) -> Dict:
        """Get summary of session with trial statuses."""
        trials = self.get_trial_list()
        ready_for_analysis = sum(1 for t in trials if t['basic_complete'])
        ready_for_ceinms = sum(1 for t in trials if t['ceinms_complete'])

        return {
            'session_name': self.session_name,
            'session_path': str(self.session_path),
            'total_trials': len(trials),
            'ready_for_analysis': ready_for_analysis,
            'ready_for_ceinms': ready_for_ceinms,
            'trials': trials,
        }


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        session_path = sys.argv[1]
        manager = SessionManager(session_path)
        summary = manager.get_session_summary()
        print(json.dumps(summary, indent=2))



# ---------------------------------------------------------------------------
# Does the CEINMS stage repair its own inputs?
#
# False (default): `do_ceinms` runs CEINMS and NOTHING else. If a calibration
# trial's IK/ID/MA are missing or stale it reports an error naming the trial and
# what to run, then skips calibration. A stage that silently runs three other
# stages is a stage you cannot time, cannot reason about, and cannot use in a
# sandbox -- a t10 calibration sweep re-solved IK->ID->MA before every
# configuration, minutes each, for outputs that could not change.
#
# True: the previous behaviour -- re-solve IK->ID->MA for any stale calibration
# trial before calibrating. Set it if you have a caller that relies on
# `do_ceinms` self-healing after a re-scale.
#
# The staleness TEST is unchanged either way, and it is the right test: never
# reuse a stale IK/ID solved over a DIFFERENT window than MA, because the CEINMS
# inputData window then inherits that span, has no muscle-length data there, and
# calibration dies silently -- reads its inputs, writes no subjectCalibrated.xml.
CEINMS_AUTOPREP = False



# ===========================================================================
# The runnable Iteration  —  ONE model iteration of a recording session on disk.
#
# Layout:  simulations/<athlete>/<session>/<iteration>/<trial>/...
# An Iteration is scoped to ONE model iteration; trials are discovered from the
# session's session.yaml. Raw model-INDEPENDENT inputs (markers/grf/emg) are
# SHARED across iterations and live in <session>/experimental/<trial>/.
# It is the runnable unit: scale_model / run / plot_summary all live here. Get
# one from a Session:  Session.open(path).iteration("gpk_mri").
# ===========================================================================
class Iteration:
    """One (model-iteration, recording-session) on disk — the RUNNABLE unit.

    ``session_dir`` is the athlete/session folder holding ``session.yaml``
    (e.g. ``simulations/Athlete_03/25_03_31``); ``iteration`` is the model
    sub-folder (``gpk``, ``gpk_mri``, ``cateli`` ...). Trials come from
    ``session.yaml`` (``type: static`` entries skipped), restricted to those
    present under this iteration.

    Roles:
      * navigation — ``.path``, ``.trials``, ``.trial(name)``
      * analysis — ``scale_model``, session-wide EMG normalisation, CEINMS
        calibration, ``plot_summary``, and the ``run()`` orchestrator
        (export -> external biomechanics -> SO -> CEINMS).

    Usually obtained from a :class:`Session` rather than built directly::

        s  = Session.open(r"...\\simulations\\Athlete_03\\25_03_31")
        it = s.iteration("gpk_mri")
        it.run(trials=["Squat_BW_01", "Walking_02"],
               do_exbiomec=True, do_so=True, do_ceinms=True, replace=True)
    """

    def __init__(self, session_dir, iteration):
        self.session_dir = os.path.abspath(session_dir)
        self.iteration = iteration
        self.name = os.path.basename(self.session_dir)      # session id, e.g. "25_03_31"
        self._cfg = self._read_yaml(os.path.join(self.session_dir, "session.yaml"))
        self._setup_dir = self._resolve_setup_dir()

    @staticmethod
    def _read_yaml(path):
        if not os.path.exists(path):
            return {}
        try:
            import yaml
        except Exception:
            return {}
        # Duplicate keys are checked on the TEXT: by the time the loader has
        # run they are gone — yaml.safe_load keeps the last value in silence,
        # which is how a generated file with `Voltage_1:` twice calibrated on
        # the wrong data without a word (IMPLEMENTATIONS §1).
        try:
            from . import run_check as _rc
            with open(path, "r", encoding="utf-8", errors="replace") as _fh:
                _dups = _rc.duplicate_yaml_keys(_fh.read())
            for _k, _a, _b in _dups:
                print(f"[session.yaml WARNING] {path}: duplicate key {_k!r} "
                      f"(lines {_a} and {_b}) — YAML silently keeps line {_b} "
                      f"and DISCARDS line {_a}. Fix the file.")
        except Exception:                                      # noqa: BLE001
            pass
        return load_session_yaml(path)

    @staticmethod
    def _resolve_setup_dir():
        """Absolute path to the shared OpenSim setup templates (setupFiles/), from
        settings.SETUP_DIR / BatchSettings.SETUP_DIR when available."""
        try:
            from bioscout import utils as _u
            s = getattr(_u, "settings", None)
            for obj in (getattr(s, "BatchSettings", None), s):
                v = getattr(obj, "SETUP_DIR", None) or getattr(obj, "SETUP_FILES", None)
                if v:
                    return str(v)
        except Exception:
            pass
        return None

    # -- navigation ---------------------------------------------------------
    @property
    def path(self):
        return _layout.iteration_path(self.session_dir, self.iteration)

    @property
    def label(self):
        return f"{self.name}/{self.iteration}"

    @classmethod
    def open(cls, iteration, session=None, project_dir=None, verbose=False,
             subject=None):
        """Back-compat: open ONE iteration by (iteration, session-id).

        Prefer ``Session.open(path).iteration(iteration)`` in new code. Resolves
        ``simulations/*/<session>/`` under the project, starts session-folder
        logging and bootstraps ``bioscout.Project``::

            it = Iteration.open("gpk_mri", "25_03_31")
        """
        from bioscout import utils
        if session is None:
            _s = getattr(utils, "settings", None)
            session = getattr(getattr(_s, "BatchSettings", None), "SESSION", None) \
                or getattr(_s, "SESSION", None)
        # Resolve the session folder from project_dir/cwd DIRECTLY — Project()
        # hasn't run yet, so utils.SIMULATIONS_DIR still points at the bioscout
        # package, not this project. (Falls back to find_session_dir after
        # bootstrap for non-standard layouts.)
        _root = os.path.abspath(project_dir or os.getcwd())
        _hits = sorted(glob.glob(os.path.join(
            _root, "simulations", str(subject) if subject else "*",
            session, "session.yaml")))
        # A session NAME is only unique within a participant. "pre" belongs to
        # everyone, so taking sorted(hits)[0] quietly opened the lowest id that
        # had one — the run was labelled 022 and solved 009. Refuse instead.
        if len(_hits) > 1 and not subject:
            _who = [os.path.basename(os.path.dirname(os.path.dirname(h))) for h in _hits]
            raise ValueError(
                f"session={session!r} is ambiguous — {len(_hits)} participants "
                f"have one: {', '.join(_who[:8])}{' ...' if len(_who) > 8 else ''}. "
                f"Pass subject=, or open the folder directly with "
                f"Session.open(<path>).iteration({iteration!r}).")
        session_dir = os.path.dirname(_hits[0]) if _hits else None
        _run_name = f"{os.path.basename(session_dir) if session_dir else session}/{iteration}"
        _bootstrap_project(session_dir, _run_name, project_dir, verbose)
        if session_dir is None:      # non-standard layout: retry now SIMULATIONS_DIR is set
            session_dir = find_session_dir(session, project_dir, subject=subject)
        it = cls(session_dir, iteration)
        if not os.path.isdir(it.path):
            raise FileNotFoundError(
                f"iteration folder not found: {it.path}\n"
                f"  known iterations for this session: "
                f"{it.iterations or '(none in session.yaml)'}")
        return it

    def _trial_names(self):
        """Non-static trials for this iteration.

        session.yaml is the source of truth, so a configured trial counts even
        when its folder does not exist yet — export creates it on demand. That
        keeps a project from having to carry thousands of empty placeholder
        directories just to be enumerable. Falls back to what is on disk when
        session.yaml lists no trials (legacy sessions with only
        trial_settings.xml).
        """
        trials_cfg = (self._cfg.get("trials") or {})
        out = [tr for tr, meta in trials_cfg.items()
               if str((meta or {}).get("type", "")).lower() != "static"]
        if out:
            return out
        if not os.path.isdir(self.path):
            return []
        return sorted(d for d in os.listdir(self.path)
                      if os.path.isdir(os.path.join(self.path, d))
                      and (os.path.exists(os.path.join(self.path, d, "trial_settings.xml"))
                           or os.path.isdir(os.path.join(self.path, d, "inputs"))))

    def trial(self, name, force_type="SO"):
        """Return an Analyse for one trial, with shared experimental inputs bound.

        Raw inputs (markers/grf/emg/GRF.xml) live once in
        ``<session>/experimental/<trial>/`` and are shared by every iteration.
        Setting ``experimental_dir`` makes Analyse redirect them there on every
        settings reload; derived outputs still write under this iteration's own
        trial folder."""
        _tp = os.path.join(self.path, name)
        # session.yaml is the trial list, so a configured trial may have no folder
        # yet (see _trial_names). Create it on demand — Analyse chdir's into it.
        if not os.path.isdir(_tp):
            try:
                from bioscout import utils as _u
                _auto = getattr(_u.settings.BatchSettings, 'auto_create_dirs', True)
            except Exception:
                _auto = True
            if _auto:
                os.makedirs(_tp, exist_ok=True)
        t = Analyse(_tp)
        t.experimental_dir = experimental_dir(self.session_dir, name)
        if self._setup_dir:
            t._session_setup_dir = self._setup_dir
        # EMG-only normalisation trials never produce iteration outputs — they
        # only feed the session MVC maximum from experimental/. Suppress the
        # output-stage scaffolding for them and prune anything the Analyse
        # constructor already created, so 20+ MVIC captures do not each leave
        # an empty {external_biomechanics, ceinms, ...} tree per iteration
        # (reported 2026-08-17, FAIS 022).
        _norm_only = (name in set(self._cfg.get("normalisation_trials") or [])
                      and name not in set(self._cfg.get("calibration_trials") or []))
        t._scaffold_output_dirs = not _norm_only
        t._apply_inputs_layout()
        self._apply_session_config(t, name, force_type)     # session.yaml is the source of truth
        if _norm_only:
            try:
                from .analysis import LAYOUT_DIRS as _LD
                os.chdir(self.session_dir)          # cannot rmdir the cwd on Windows
                for _d in _LD.values():
                    _p2 = os.path.join(_tp, _d)
                    if os.path.isdir(_p2) and not os.listdir(_p2):
                        os.rmdir(_p2)
                if os.path.isdir(_tp) and not os.listdir(_tp):
                    os.rmdir(_tp)
            except OSError:
                pass
        return t

    def get_trial(self, name, force_type="SO"):
        """The Analyse (trial) object for the session trial ``name`` — explicit
        alias for :meth:`trial`::

            a = Session.open(session_path).iteration("gpk_mri").get_trial("Walking_02")
            a.run_ik(); a.plot_jra_comparison()
        """
        return self.trial(name, force_type=force_type)

    def plot_summary(self, trials=None, dofs=None, figures=None, **opts):
        """Regenerate the per-trial summary figures for this iteration's trials
        from data already on disk (no re-solve):

          * ``kinematics_moments.png``     — plot_kin_mom_summary (IK angles + ID moments)
          * ``summary``                    — plot_summary (angles + SO/CEINMS muscle moments)
          * ``JRA_SO_vs_CEINMS.png``       — plot_jra_comparison (joint contact forces)

        Defaults come from ``settings.SummarySettings`` (dofs, analysis_leg,
        algorithms, joints, ...). ``figures`` selects which to make — any of
        ``{"kin_mom", "summary", "jra"}`` (default: kin_mom + jra). ``trials``
        defaults to every trial in this iteration. Extra ``SummarySettings``
        keywords are accepted and ignored where they only apply to the
        cross-model overlay figure (that multi-model comparison is
        ``summary_figures.py`` / a future session-level overlay).

            it = Session.open(session_path).iteration("gpk_mri")
            it.plot_summary(trials=["Walking_03", "Squat_BW_01", "Squat_BW_02"])
        """
        from bioscout import utils as _u
        ss = getattr(getattr(_u, "settings", None), "SummarySettings", None)
        if dofs is None and ss is not None:
            dofs = list(getattr(ss, "dofs", []) or []) or None
        if figures is None:
            figures = getattr(ss, "figures", None) or ("kin_mom", "jra")
        figs = {str(x).lower() for x in figures}
        trial_names = ([trials] if isinstance(trials, str)
                 else list(trials)) if trials else self._trial_names()
        made = []
        for tn in trial_names:
            try:
                t = self.trial(tn)
                os.chdir(t.path)
                if figs & {"kin_mom", "kinematics", "kin_mom_summary"}:
                    try:
                        t.plot_kin_mom_summary(dofs=dofs)
                    except Exception as e:
                        print(f"[Session] {self.label}/{tn} kin_mom: {e}")
                if "summary" in figs:
                    try:
                        t.plot_summary()
                    except Exception as e:
                        print(f"[Session] {self.label}/{tn} summary: {e}")
                if figs & {"jra", "jcf"}:
                    try:
                        t.plot_jra_comparison()
                    except Exception as e:
                        print(f"[Session] {self.label}/{tn} jra: {e}")
                made.append(tn)
                print(f"[Session] {self.label}: plotted {tn}")
            except Exception as e:
                print(f"[Session] {self.label}: plot failed for {tn}: {e}")
        return made

    def resolve_model_file(self, mfile):
        """Find a configured model file. -> absolute path or None.

        Search order (2026-08-17 — models used to HAVE to be copied into every
        iteration folder, so the same scaled model existed 3x per subject):
          1. an absolute path, as given
          2. relative to THIS iteration folder        (the classic location)
          3. relative to the session folder            (explicit ../ paths)
          4. the project models library, in order:
             ``<project>/<mfile>`` verbatim (project-relative paths),
             ``models/personalised/<subject>/<name>``,
             ``models/generic/<name>`` and one level of family subfolders,
             ``models/<name>`` (flat legacy layout, kept working)
        A session.yaml can therefore keep just the filename and store the model
        once in the project's models/ folder, shared by every session and
        iteration of that subject.
        """
        if not mfile:
            return None
        if os.path.isabs(mfile):
            return mfile if os.path.exists(mfile) else None
        for base in (self.path, self.session_dir):
            p = os.path.normpath(os.path.join(base, mfile))
            if os.path.exists(p):
                return p
        try:
            from bioscout import utils as _u
            roots = [getattr(_u, "PROJECT_DIR", None)]
        except Exception:
            roots = []
        # session assumed at <project>/simulations/<subject>/<session>
        roots.append(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(self.session_dir)))))
        subject = os.path.basename(os.path.dirname(
            os.path.abspath(self.session_dir)))
        name = os.path.basename(mfile)
        for root in roots:
            if not root:
                continue
            root = str(root)
            # 4a. A project-relative path, verbatim — session.yaml can say
            #     models/personalised/021/021_Rajagopal2015_FAI.osim and mean
            #     exactly that, whichever session reads it.
            p = os.path.normpath(os.path.join(root, mfile))
            if os.path.exists(p):
                return p
            # 4b. Bare filename against the ORGANISED library:
            #     personalised/<subject>/ first (a subject model belongs to a
            #     subject), then generic/ and one level of family subfolders
            #     (generic/Rajagopal_FAIS/, generic/Catelli/, ...), then the
            #     flat legacy models/ root last so old projects keep working.
            candidates = [
                os.path.join(root, "models", "personalised", subject, name),
                os.path.join(root, "models", "generic", name),
            ]
            gen_dir = os.path.join(root, "models", "generic")
            if os.path.isdir(gen_dir):
                try:
                    for fam in sorted(os.listdir(gen_dir)):
                        candidates.append(os.path.join(gen_dir, fam, name))
                except OSError:
                    pass
            candidates.append(os.path.join(root, "models", name))
            for p in candidates:
                if os.path.exists(p):
                    return p
        return None

    def trial_config(self, name, force_type="SO"):
        """FULL config for one (trial, iteration) from session.yaml + iteration
        model config — everything trial_settings.xml used to hold. side/time_range/
        type from trials[name]; body_mass + alpha/beta/gamma session-wide; model
        file + setup dir from the iteration."""
        meta = (self._cfg.get("trials") or {}).get(name) or {}
        ce = (self._cfg.get("ceinms") or {})
        cfg = {}
        tr = meta.get("time_range")
        if isinstance(tr, (list, tuple)) and len(tr) == 2:
            try:
                cfg["time_range"] = [float(tr[0]), float(tr[1])]
            except Exception:
                pass
        if meta.get("side") is not None:
            cfg["side"] = str(meta["side"])
            # FAIS patch 2026-08-12: session.yaml's `side` is the LOADED limb,
            # and that is the limb the per-trial figures should show. But
            # plot_kin_mom_summary reads `analysis_leg`, which only ever came
            # from trial_settings.xml (disabled here) or the project-wide
            # SummarySettings default of "both" — so every single-leg squat was
            # plotted with both legs. Derive it from `side`; "both" stays both.
            _s = cfg["side"].strip().lower()
            if _s.startswith(("r", "l")):
                cfg["analysis_leg"] = _s[0]
        if meta.get("type") is not None:
            cfg["trial_type"] = str(meta["type"])
        if self._cfg.get("body_mass") is not None:
            cfg["body_mass"] = self._cfg["body_mass"]
        # Channel -> muscles for THIS session's electrode set. Sessions captured
        # months apart label and place channels differently, so the session file
        # outranks the project-wide settings.BatchSettings.emg_muscle_mapping.
        # A session may carry SEVERAL named maps (`emg_map: {narrow: {...}}`)
        # with each iteration naming the one it runs with — that is how three
        # electrode-grouping variants share one set of experimental inputs
        # instead of three copied sessions.
        try:
            _emn = emg_map_name_for(self._cfg, self.iteration)
        except ValueError as e:
            if self.iteration in _iteration_blocks(self._cfg):
                raise
            raise ValueError(
                f"{e} (iteration {self.iteration!r} is a folder on disk but is "
                "not declared in session.yaml, so it has no emg_map selector "
                "-- add it to `iterations:`)") from None
        if _emn is not None:
            # set even when the selected map is EMPTY: "this iteration has no
            # channels" must not silently fall back to the project-wide map.
            cfg["emg_map"] = resolve_emg_map(self._cfg, self.iteration)
            cfg["emg_map_name"] = _emn
        # CEINMS calibration bounds, same shape as emg_map: several named
        # configs with each iteration naming one, so a bound sweep becomes
        # iterations of one session rather than copied sessions plus a runtime
        # monkeypatch of settings.CEINMSSettings.
        _caln = None
        try:
            if iteration_is_calibrated(self._cfg, self.iteration):
                _caln = calibration_name_for(self._cfg, self.iteration)
        except ValueError as e:
            if self.iteration in _iteration_blocks(self._cfg):
                raise
            raise ValueError(
                f"{e} (iteration {self.iteration!r} is a folder on disk but is "
                "not declared in session.yaml, so it has no calibration "
                "selector -- add it to `iterations:`)") from None
        if _caln is not None:
            cfg["calibration_params"] = resolve_calibration(self._cfg,
                                                            self.iteration)
            cfg["calibration_name"] = _caln
        # Execution weights, and everything the CEINMS execution MODE needs.
        # `mode` is copied under the name `ceinms_mode`: a trial already has a
        # `mode` attribute in other contexts, and a silent collision here would
        # select the wrong execution strategy without raising.
        for k in ("alpha", "beta", "gamma"):
            if ce.get(k) is not None:
                cfg[k] = ce[k]
        if ce.get("mode") is not None:
            cfg["ceinms_mode"] = str(ce["mode"])
        # `calibrated: false` drives EXECUTION with the UNCALIBRATED subject
        # model (subjectUncalibrated.xml, written straight from the .osim).
        # Declared in session.yaml rather than passed at the call site so the
        # session that produced a result records which subject model made it --
        # the same reason `calibration:` and `emg_map` live there.
        if ce.get("calibrated") is not None:
            cfg["ceinms_calibrated"] = yaml_bool(ce["calibrated"])
        # ...and per ITERATION, so an uncalibrated CONTROL can sit in the same
        # session as the calibrated arms it is the control for. Session-level
        # `ceinms.calibrated` sets the default; the iteration overrides it. A
        # separate copied session for the control would reintroduce exactly the
        # drift `emg_map` and `calibration:` were moved into the file to end.
        _itb = _iteration_blocks(self._cfg).get(self.iteration) or {}
        if _itb.get("calibrated") is not None:
            cfg["ceinms_calibrated"] = yaml_bool(_itb["calibrated"])
        for k in ("gamma_bounds", "alpha_range", "beta_range", "gamma_range",
                  "lcurve_betas", "lcurve_gammas"):
            if ce.get(k) is not None:
                cfg[k] = ce[k]
        # _iteration_blocks, not a raw .get: `iterations` may be authored as a
        # LIST of blocks, which read_session_yaml accepts and this line used to
        # crash on with AttributeError before reaching any model file.
        it = _itb
        mkey = "ceinms_model" if str(force_type).upper().startswith("C") else "so_model"
        # Prefer the requested model; fall back to the other, then the plain
        # marker-registered scaled.osim — enough for external biomechanics
        # (IK/ID/MA) before the slow muscle-opt has produced scaled_opt_*.
        _tried = []
        for mfile in (it.get(mkey), it.get("so_model"), it.get("ceinms_model"), "scaled.osim"):
            # dedupe: when mkey IS "so_model" (or the two keys share a value)
            # the same candidate would be tried — and reported — twice.
            if not mfile or str(mfile) in _tried:
                continue
            _tried.append(str(mfile))
            mpath = self.resolve_model_file(mfile)
            if mpath:
                cfg["model_dir"] = mpath
                break
        else:
            if _tried:               # a model WAS configured but none resolved
                print(f"[Session] {self.label}: [warn] no model file found for "
                      f"{name} — tried {', '.join(_tried)} in the iteration "
                      f"folder, the session folder, "
                      f"<project>/models/personalised/<subject>/ and "
                      f"<project>/models/generic/")
                # Still set model_dir — to the model the session ASKED for.
                # Without this the trial keeps whatever stale value sits in its
                # trial_settings.xml (often a legacy ../../models/<subj>/<sess>/
                # relative path from a pre-reorg run), and the downstream
                # "Model file not found" error names THAT ghost instead of the
                # configured model, sending the reader to the wrong place.
                cfg["model_dir"] = _tried[0]
        if self._setup_dir:
            cfg["setup_dir"] = self._setup_dir
        return cfg

    def _apply_session_config(self, t, name, force_type="SO"):
        """Inject session.yaml config onto the Analyse as authoritative overrides
        (_overrides), plus pin + persist the analysis window."""
        cfg = self.trial_config(name, force_type)
        t._overrides = cfg
        for k, v in cfg.items():
            setattr(t, k, v)
        tr = cfg.get("time_range")
        if isinstance(tr, (list, tuple)) and len(tr) == 2:
            t0, t1 = float(tr[0]), float(tr[1])
            # window authority now comes from _overrides (get_time_range reads it)
            try:
                t.update_trial_attribute("start_time", f"{t0:.4f}")
                t.update_trial_attribute("end_time", f"{t1:.4f}")
            except Exception:
                t.start_time, t.end_time = f"{t0:.4f}", f"{t1:.4f}"

    @property
    def trials(self):
        return [self.trial(n) for n in self._trial_names()]

    @property
    def iterations(self):
        """Model-iteration folders configured for this session (session.yaml)."""
        return list((self._cfg.get("iterations") or {}).keys())

    # -- analysis / orchestration -----------------------------------------
    def _project_dir(self):
        """Project root (holds settings.py + simulations/) = 3 levels above the
        session dir (simulations/<subject>/<session>)."""
        return os.path.abspath(os.path.join(self.session_dir, os.pardir, os.pardir, os.pardir))

    # -- CEINMS / EMG / model-scaling (single-iteration operations) --------
    # These operate on THIS iteration's own folder (self.path) and its shared
    # experimental/ inputs. They used to live on a combined god-class; they are
    # Iteration methods now (the pipeline in run()/scale_model() calls them
    # directly — no session_layout indirection).
    @property
    def calibration_trials(self):
        """CEINMS calibration trial names (settings.CEINMSSettings) present here."""
        from bioscout import utils
        cs = getattr(getattr(utils, "settings", None), "CEINMSSettings", None)
        names = getattr(cs, "calibration_trial_names", None) or []
        here = set(self._trial_names())
        return [n for n in names if n in here]

    def _resolve_calibration_trials(self):
        """Calibration trial folders for THIS session: settings names matched to
        real folders (case-insensitive); falls back to squats, then all trials."""
        here = self._trial_names()
        lower = {t.lower(): t for t in here}
        from bioscout import utils
        cs = getattr(getattr(utils, "settings", None), "CEINMSSettings", None)
        wanted = list(getattr(cs, "calibration_trial_names", None) or [])
        matched = [lower[w.lower()] for w in wanted if w.lower() in lower]
        if matched:
            return matched
        if wanted:
            print(f"[Session] {self.label}: calibration trials {wanted} not found; falling back.")
        squats = [t for t in here if "squat" in t.lower()]
        return squats or here

    def ingest_c3d(self, source=None, dry_run=False, trials=None):
        """Distribute loose ``*.c3d`` into per-trial ``<trial>/inputs/c3dfile.c3d``
        under this iteration. ``source`` defaults to the session folder. ``trials``
        (name or list) restricts distribution to those c3d (matched by file stem), so
        only the selected trials' folders are touched; default: every loose ``*.c3d``."""
        import shutil
        from .session_layout import c3d_root as _c3d_root
        src = source or self.session_dir
        _tset = ({trials} if isinstance(trials, str) else set(trials)) if trials else None
        # In the session-centric layout the c3d already lives at its canonical
        # address, 1_c3dfiles/<trial>.c3d, and the trial reads it from there.
        # Copying it into <iteration>/<trial>/inputs/ is pure duplication.
        try:
            _canon = _c3d_root(self.session_dir)
        except Exception:
            _canon = None
        made = []
        for c in sorted(glob.glob(os.path.join(src, "*.c3d"))):
            stem = os.path.splitext(os.path.basename(c))[0]
            if _tset is not None and stem not in _tset:
                continue
            if _canon and os.path.isfile(os.path.join(_canon, stem + ".c3d")):
                continue                      # already canonical — do not copy
            dst = os.path.join(self.path, stem, "inputs", "c3dfile.c3d")
            if os.path.exists(dst):
                continue
            made.append(stem)
            if dry_run:
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(c, dst)
        if made:
            print(f"[Session] {self.label}: "
                  f"{'would ingest' if dry_run else 'ingested'} "
                  f"{len(made)} c3d -> trial folders")
        return made

    def run_emg_normalise(self, replace=None, write_trials=None):
        """Session-wide EMG normalisation. The per-channel session-max (MVC-style)
        reference is computed across ALL of the session's trials; then each written
        trial's inputs/emg_filtered_normalised.mot is scaled into [0, 1]. ``write_trials``
        (name or list) restricts which trials have their normalised file (re)written
        and their ``replace`` flag touched — the MVC reference STILL spans every trial.
        Default: write all."""
        from bioscout import utils as _u
        _wset = ({write_trials} if isinstance(write_trials, str)
                 else set(write_trials)) if write_trials else None
        envelopes = {}
        for t in self.trials:
            try:
                env = t._emg_envelope()
            except Exception as e:
                print(f"[Session] {self.label}: EMG envelope failed for "
                      f"{os.path.basename(t.path)}: {e}")
                env = None
            if env is not None:
                envelopes[t] = env
        if not envelopes:
            print(f"[Session] {self.label}: no EMG to normalise.")
            return []
        chans = set()
        for env in envelopes.values():
            chans |= {c for c in env.columns if c != 'time'}

        # -- VALIDATE the emg_map against the labels that actually exist.
        # The FAIS trap: every electrode exported twice (bare Voltage_N + the
        # conditioned Voltage_N-VM); a map keyed on the bare names normalised
        # and CALIBRATED CEINMS on the raw columns without one warning. A
        # mapped channel that exists nowhere is a hard refusal — normalising
        # would silently produce nothing for it; a bare name shadowed by a
        # tagged sibling is a loud warning, because only the rig's owner
        # knows which column is the signal.
        try:
            from . import run_check as _rc
        except Exception:                                      # noqa: BLE001
            _rc = None
        if _rc is not None:
            try:
                _map = resolve_emg_map(self._cfg,
                                       getattr(self, "iteration", None),
                                       strict=False) or {}
            except Exception:                                  # noqa: BLE001
                _map = {}
            if _map:
                _v = _rc.validate_emg_map(_map.keys(), chans)
                for _bare, _tag in _v["suspicious"]:
                    print(f"[Session] {self.label}: EMG MAP WARNING — map "
                          f"keys {_bare!r} but the recording also has "
                          f"{_tag!r}; if the tagged column is the "
                          f"conditioned signal, the map normalises the RAW "
                          f"one. Check session.yaml's emg_map.")
                if _v["missing"]:
                    raise RuntimeError(
                        f"emg_map channels not present in any trial's EMG: "
                        f"{_v['missing']} — available: {sorted(chans)[:12]}"
                        f"{'...' if len(chans) > 12 else ''}. Fix "
                        f"session.yaml's emg_map; refusing to normalise "
                        f"against columns that do not exist.")
        session_max, session_max_trial = {}, {}
        for c in chans:
            best_m, best_t = 0.0, None
            for t, env in envelopes.items():
                if c in env:
                    m = float(env[c].max())
                    if m > best_m:
                        best_m, best_t = m, os.path.basename(t.path)
            session_max[c] = best_m if best_m > 1e-9 else 1.0
            session_max_trial[c] = best_t
        done = []
        chans_sorted = sorted(chans)      # canonical EMG order for CEINMS
        # session.yaml `emg_gain`, applied AFTER the session-max division --
        # scaling the RAW signal would be an exact no-op (see resolve_emg_gain).
        # Raises on a channel name that is not in the data.
        gains = resolve_emg_gain(self._cfg, channels=chans)
        if gains:
            print(f"[Session] {self.label}: emg_gain "
                  + ", ".join(f"{c} x{g:g}" for c, g in sorted(gains.items())))
        for t, env in envelopes.items():
            if _wset is not None and os.path.basename(t.path) not in _wset:
                continue                  # reference-only: feeds session-max, not (re)written
            if replace is not None:
                t.update_trial_attribute("replace", replace)
            out = env[['time']].copy()
            for c in chans_sorted:
                if c in env:
                    out[c] = (env[c] / session_max[c]).clip(0.0, 1.0)
                    g = gains.get(c, 1.0)
                    if g != 1.0:
                        # clipped again: CEINMS only accepts [0, 1], and a gain
                        # above 1 would otherwise hand it excitations > 1.
                        out[c] = (out[c] * g).clip(0.0, 1.0)
            try:
                _exc_rel = t.emg_filtered_normalised
                _exc_abs = os.path.join(t.path, _exc_rel)
                os.makedirs(os.path.dirname(_exc_abs), exist_ok=True)
                _u.emg_normalise.write_sto_file(out, _exc_abs)
                t.update_trial_attribute('ceinms_excitations', _exc_rel)
                done.append(t)
            except Exception as e:
                print(f"[Session] {self.label}: EMG normalise failed for "
                      f"{os.path.basename(t.path)}: {e}")
        print(f"[Session] {self.label}: wrote emg_filtered_normalised.mot for "
              f"{len(done)} trials (session-max normalised, [0,1]).")
        for t in done:
            try:
                t.plot_emg_processing(norm_source=session_max_trial)
            except Exception as e:
                print(f"[Session] EMG figure failed for {os.path.basename(t.path)}: {e}")
        return done

    # clean alias
    def normalise_emg(self, replace=None, write_trials=None):
        return self.run_emg_normalise(replace=replace, write_trials=write_trials)

    def run_ceinms_calibration(self, replace=None, prefer_trial=None):
        """Calibrate CEINMS once for THIS session, driven off the first
        calibration trial (dynamic, never the static trial)."""
        names = self._resolve_calibration_trials()
        here = self._trial_names()
        if prefer_trial and prefer_trial in here:
            names = [prefer_trial] + [n for n in names if n != prefer_trial]
        names = [n for n in names if n in here]
        if not names:
            print(f"[Session] {self.label}: no calibration trials to calibrate.")
            return None
        host = self.trial(names[0], force_type="CEINMS")
        if host is None:
            print(f"[Session] {self.label}: could not load calibration trial {names[0]!r}.")
            return None
        if replace is not None:
            host.update_trial_attribute("replace", replace)
        print(f"[Session] {self.label}: CEINMS calibration (driver={names[0]}, trials={names})")
        return host.run_ceinms_calibration()

    def calibrate(self, replace=None, calibration_trials=None):
        """Calibrate CEINMS for THIS session (settings names, or explicit ones)."""
        names = list(calibration_trials) if calibration_trials else self._resolve_calibration_trials()
        if not names:
            print(f"[Session] {self.label}: no calibration trials found.")
            return None
        from bioscout import utils
        cs = getattr(getattr(utils, "settings", None), "CEINMSSettings", None)
        old = getattr(cs, "calibration_trial_names", None) if cs is not None else None
        try:
            if cs is not None:
                cs.calibration_trial_names = names
            print(f"[Session] {self.label}: calibrating CEINMS on {names}")
            return self.run_ceinms_calibration(replace=replace, prefer_trial=names[0])
        finally:
            if cs is not None:
                cs.calibration_trial_names = old

    def prepare_ceinms(self, replace=None, calibration_trials=None):
        """Session EMG normalisation, then CEINMS calibration. ``calibration_trials``
        restricts which trials the calibration objective uses (e.g. walking-only
        when you'll execute on walking); default = settings.CEINMSSettings."""
        self.normalise_emg(replace=replace)
        return self.calibrate(replace=replace, calibration_trials=calibration_trials)

    def prepare_uncalibrated_ceinms(self, replace=None, host_trial=None):
        """Everything CEINMS execution needs EXCEPT a calibration.

        Calibration produces three things execution depends on: the session's
        normalised EMG, the excitation generator, and a subject XML. An
        UNCALIBRATED run still needs the first two -- excitations are what
        execution solves against, calibrated or not. The third is the
        uncalibrated subject: optimal fibre lengths, tendon slack lengths,
        pennation angles and max isometric forces exactly as the OpenSim model
        states them, nothing fitted.

        This builds those three and stops. No calibration executable runs, so
        an uncalibrated arm costs execution time only.

        -> the uncalibrated subject XML path, or None.
        """
        self.normalise_emg(replace=replace)
        here = self._trial_names()
        order = ([host_trial] if host_trial else []) \
            + list(self._resolve_calibration_trials() or []) + here
        names = [n for n in order if n in here]
        if not names:
            print(f"[Session] {self.label}: no trials to build an uncalibrated "
                  f"CEINMS model from.")
            return None
        host = self.trial(names[0], force_type="CEINMS")
        if host is None:
            print(f"[Session] {self.label}: could not load {names[0]!r}.")
            return None
        if replace is not None:
            host.update_trial_attribute("replace", replace)
        print(f"[Session] {self.label}: building UNCALIBRATED CEINMS subject "
              f"model (driver={names[0]})")
        host.create_ceinms_model()
        host.create_excitation_generator()
        return host.ceinms_uncalibrated_model

    # -- model scaling ------------------------------------------------------
    def _resolve_model_file(self, rel, key="so_model"):
        """Resolve a session.yaml path through the one shared rule.

        ``key`` selects the base order (see :mod:`bioscout.utils.session_paths`).
        It matters: a markerset is a project asset and a model is searched from
        the iteration folder outward. Everything used to go through the model
        search, so ``markerset: setup_files/markers_FAIS.xml`` resolved
        correctly only because that search's last fallback happened to be the
        project root — right answer, wrong reason, and no way to tell.

        Unresolvable values are returned unchanged, as before, so a caller that
        wants to raise its own error still can.
        """
        if not rel:
            return None
        from bioscout import utils as _u
        from bioscout.utils.session_paths import resolve as _resolve_path
        md = str(getattr(_u, "MODELS_DIR", "") or "")
        pd = str(getattr(_u, "PROJECT_DIR", None)
                 or (os.path.dirname(md) if md else os.getcwd()))
        got = _resolve_path(key, rel, session_dir=self.session_dir, project_dir=pd,
                            iteration_dir=iteration_dir(self.session_dir, self.iteration))
        note = got.note()
        if note:
            print(f"[paths] {note}")
        return str(got) if got.ok else rel

    def link_geometry(self, generic_model_path, name="Geometry"):
        """Link the generic model's ``Geometry/`` beside the scaled model.

        A scaled .osim keeps the generic's relative mesh references
        (``r_femur.vtp`` ...), but it is written into the iteration folder,
        which has no ``Geometry/``. OpenSim's GUI then loads the model with no
        bones and no muscle paths — "Couldn't find file 'r_femur.vtp'" — and
        the model looks broken when it is fine.

        A LINK, not a copy: the mesh set is tens of megabytes and identical for
        every iteration and every subject that shares the generic, so copying
        it would multiply it across the whole simulations tree. On Windows this
        is a directory JUNCTION, which needs no elevation and no developer
        mode, unlike a true symlink. Never fails the scaling — if the link
        cannot be made, it says so and moves on, because a missing mesh affects
        only what you can SEE, never what is computed.

        Returns the link path, or None.
        """
        if not generic_model_path:
            return None
        src_geo = os.path.join(os.path.dirname(os.path.abspath(generic_model_path)), name)
        if not os.path.isdir(src_geo):
            # Some model families keep the meshes one level up, shared by
            # several .osim in sibling folders.
            _up = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(generic_model_path))), name)
            if os.path.isdir(_up):
                src_geo = _up
            else:
                return None
        dst = os.path.join(self.path, name)
        if os.path.isdir(dst) or os.path.islink(dst):
            return dst                      # already linked (or a real folder)
        try:
            if os.name == "nt":
                import _winapi
                _winapi.CreateJunction(src_geo, dst)
            else:
                os.symlink(src_geo, dst, target_is_directory=True)
            print(f"[Session] {self.label}: linked {name}/ -> {src_geo}")
            return dst
        except Exception as e:
            print(f"[Session] {self.label}: could not link {name}/ "
                  f"({type(e).__name__}: {e}). The model still runs; the GUI "
                  f"will show it without bones. Link it by hand with:\n"
                  f'    mklink /J "{dst}" "{src_geo}"')
            return None

    def scale_model(self, static_trial="Static_01", n_eval=None, mvic_factor=None,
                    mass=None, replace=True, muscle_opt=True, marker_placer=None,
                    linear_scaling=None, increase_mvic=None):
        """Scale THIS iteration's model into its folder, driven by session.yaml.

        Pipeline (each keyword overrides the matching ``session.yaml`` value)::

            generic + static  --ScaleTool-->  scaled.osim
                                   (MarkerPlacer registers markers to the static
                                    pose; dimensional scaling only if linear_scaling)
                              --Modenese2015 muscle-opt-->  scaled_opt_N<n>.osim   (= CEINMS model)
                              --isometric force x mvic_factor-->  <so_model>

        Parameters
        ----------
        static_trial : str
            Name of the static trial whose markers drive scaling/registration.
            Read from the SHARED ``experimental/<static_trial>/marker_experimental.trc``.
        n_eval : int, optional
            Number of Modenese2015 muscle-optimisation evaluations. Defaults to
            this iteration's ``opt_neval`` in session.yaml (or 10). Ignored when
            ``muscle_opt=False``.
        mvic_factor : float, optional
            Isometric-force multiplier applied to build the SO model
            (``maxIsometricForce x mvic_factor``). The CEINMS model is NEVER
            boosted. Defaults to session.yaml ``mvic_factor`` (or 1.0 = no boost).
            e.g. ``mvic_factor=3.0``.
        mass : float, optional
            Target total body mass (kg) for ScaleTool. Defaults to session.yaml
            ``body_mass``.
        replace : bool
            If False and both output models already exist, skip and return the SO
            model path. If True, rebuild.
        muscle_opt : bool
            True  -> run the (slow, minutes) Modenese2015 muscle-parameter
                     optimisation, producing ``scaled_opt_N<n>.osim`` as the force
                     model. Needed for SO/CEINMS.
            False -> stop after ``scaled.osim`` and use it directly as the force
                     model (keeps the generic's OFL/TSL — right for a validated
                     MRI/personalised model). Fast; enough for external
                     biomechanics (IK/ID/MA).
        marker_placer : bool, optional
            Override ScaleTool's MarkerPlacer stage. Default: session.yaml
            ``marker_placer`` (else False).
        linear_scaling : bool, optional
            Override dimensional (segment) scaling. Default: session.yaml
            ``linear_scaling`` (else True). Set False to keep MRI segment geometry.
        increase_mvic : float, optional
            DEPRECATED alias for ``mvic_factor`` (kept for back-compat). Used only
            if ``mvic_factor`` is None.

        Returns
        -------
        str or None
            Absolute path to the SO model (``None`` if the generic/static is
            missing). Outputs land in this iteration's folder where the pipeline
            reads them."""
        import shutil
        from bioscout.utils import get_openSim as _get_os; _os = _get_os()
        it = (self._cfg.get("iterations") or {}).get(self.iteration) or {}
        generic = self._resolve_model_file(it.get("generic"), "generic")
        if not generic or not os.path.exists(generic):
            print(f"[Session] [ERROR] {self.label}: generic model not found: "
                  f"{it.get('generic')!r} — nothing downstream can run.")
            return None
        trc = os.path.join(experimental_dir(self.session_dir, static_trial),
                           "marker_experimental.trc")
        if not os.path.exists(trc):
            try:
                self.trial(static_trial).export_c3d()
            except Exception as e:
                print(f"[Session] {self.label}: static export failed: {e}")
        if not os.path.exists(trc):
            print(f"[Session] [ERROR] {self.label}: static TRC not found: {trc}\n"
                  f"[Session]         Export the static trial FIRST — it is usually "
                  f"absent from the analysis trial list:\n"
                  f"[Session]         Session.export(trials=['{static_trial}'] + TRIALS, "
                  f"export_src=<abs 1_c3dfiles>)\n"
                  f"[Session]         Without a scaled model, IK/MA/SO/CEINMS will all "
                  f"fail for every trial.")
            return None

        # Per-ITERATION marker set, falling back to the session-level one.
        # Two models can need different marker sets: GPK_v3 is lower-limb only,
        # so the pyCGM set's four torso markers (T10/T2/CLAV/RBAK) reference a
        # body it does not have. Session-level only would force one set on every
        # model. The `or` keeps every existing session.yaml working unchanged.
        markerset = self._resolve_model_file(
            it.get("markerset") or self._cfg.get("markerset"), "markerset")
        linear = bool(it.get("linear_scaling", True) if linear_scaling is None else linear_scaling)
        mplace = bool(it.get("marker_placer", False) if marker_placer is None else marker_placer)
        n_eval = int(n_eval if n_eval is not None else (it.get("opt_neval", 10) or 10))
        # MVIC isometric-force multiplier for the SO model. Precedence:
        # mvic_factor (explicit) > increase_mvic (deprecated alias) > session.yaml
        # mvic_factor > 1.0.
        _mvic = mvic_factor if mvic_factor is not None else increase_mvic
        mvic_factor = float(_mvic if _mvic is not None else (it.get("mvic_factor", 1.0) or 1.0))
        if mass is None:
            mass = self._cfg.get("body_mass")
            # The force plates measured this subject on this day. Prefer that over a
            # typed-in body_mass, which drifts (Athlete_03: 89.9 typed vs 91.0
            # measured) and silently biases every mass-normalised result. Opt out
            # with `body_mass_from_grf: false` in session.yaml.
            if self._cfg.get("body_mass_from_grf", True):
                try:
                    from bioscout.utils import scale_measurements as _sm
                    _grf = os.path.join(experimental_dir(self.session_dir, static_trial),
                                        "grf.mot")
                    _m = _sm.mass_from_static_grf(_grf, verbose=False)
                except Exception:
                    _m = None
                if _m:
                    if mass and abs(_m - float(mass)) > 0.05:
                        print(f"[Session] {self.label}: body mass from the static GRF is "
                              f"{_m:.2f} kg; session.yaml says {float(mass):.2f} kg. "
                              f"Using the measured value.")
                    mass = _m

        os.makedirs(self.path, exist_ok=True)
        scaled = os.path.join(self.path, "scaled.osim")

        # Config-driven output names (fall back to conventional names). CEINMS uses
        # the force model as-is; SO uses it with isometric force x mvic_factor.
        ceinms_name = it.get("ceinms_model") or (
            f"scaled_opt_N{n_eval}.osim" if muscle_opt else "scaled.osim")
        so_name = it.get("so_model") or (
            f"scaled_opt_N{n_eval}_mvicx{mvic_factor:.2f}.osim" if muscle_opt
            else f"scaled_mvicx{mvic_factor:.2f}.osim")
        ceinms_path = os.path.join(self.path, ceinms_name)
        so_path = os.path.join(self.path, so_name)

        if os.path.exists(ceinms_path) and os.path.exists(so_path) and not replace:
            print(f"[Session] {self.label}: models exist: CEINMS={ceinms_name} SO={so_name}")
            return so_path

        # 1) ScaleTool -> scaled.osim (marker registration; dimensional scaling only
        #    if linear_scaling).
        print(f"[Session] {self.label}: scale {os.path.basename(generic)} "
              f"(linear_scaling={linear}, marker_placer={mplace}) + static '{static_trial}'")
        # Make the meshes reachable from the iteration folder before anything
        # tries to open the scaled model.
        self.link_geometry(generic)
        _os.scale_model(generic, trc, scaled, scale_setup_output_dir=self.path,
                        mass=(float(mass) if mass else None), marker_set_file=markerset,
                        linear_scaling=linear, marker_placer=mplace)

        # Name the model after what it IS. OpenSim's ScaleTool names its output
        # after the tool, and openSim.scale_model calls the tool "ModelScaling",
        # so every scaled model in every project ends up as
        # <Model name="ModelScaling">. Load two in the GUI to compare and the
        # Navigator shows the same word twice. The linear_scaling=False branch is
        # no better: it copies the generic through, so all subjects inherit the
        # generic's name instead. Rewrite the attribute on the written file, which
        # covers both branches and the marker-placer pass.
        #
        # Cosmetic ONLY - nothing reads this name. It appears in a couple of log
        # lines and in the Navigator; JRA_COLUMNS keys off the SUBJECT, not the
        # model name. Failure here must never sink a scaling run, hence the
        # blanket except.
        try:
            import re as _re
            _mname = "%s_scaled_%s_%s" % (
                os.path.splitext(os.path.basename(generic))[0],
                os.path.basename(os.path.dirname(self.session_dir)),
                os.path.basename(self.session_dir))
            # BYTES, not text. These models are CRLF; text mode would turn
            # every CRLF into LF on read and write them back as LF, so a
            # 33-character rename would also rewrite ~15000 line endings and
            # shrink the file by ~15 kB. surrogateescape round-trips anything
            # the decoder dislikes, so only the name attribute changes.
            with open(scaled, "rb") as _fh:
                _txt = _fh.read().decode("utf-8", "surrogateescape")
            _txt, _n = _re.subn(r'(<Model\s+name=")([^"]*)(")',
                               lambda m: m.group(1) + _mname + m.group(3),
                               _txt, count=1)
            if _n:
                with open(scaled, "wb") as _fh:
                    _fh.write(_txt.encode("utf-8", "surrogateescape"))
                print("[Session] %s: model named '%s'" % (self.label, _mname))
        except Exception as _e:
            print("[Session] %s: [WARNING] could not name the scaled model: %s"
                  % (self.label, _e))

        # 2) Force model = Modenese2015 muscle-opt output, OR (muscle_opt=False) the
        #    marker-registered scaled.osim itself — use the latter when the generic
        #    already carries personalised muscle-tendon parameters (validated MRI
        #    model), so its OFL/TSL are kept instead of being re-fit to a reference.
        if muscle_opt:
            print(f"[Session] {self.label}: muscle optimisation (Modenese2015, N={n_eval}) — slow ...")
            base = os.path.join(self.path, f"scaled_opt_N{n_eval}.osim")
            _os.muscle_optimimizer_Modenese2015(scaled, save_path=base,
                                                ref_model_path=generic, N_eval=n_eval)
        else:
            base = scaled
            print(f"[Session] {self.label}: muscle-opt skipped — scaled.osim is the force "
                  f"model (generic's muscle-tendon params kept).")

        # 3) CEINMS model = base (copy to the configured name if different). Do this
        #    BEFORE the isometric boost so the CEINMS model is never boosted.
        if os.path.abspath(ceinms_path) != os.path.abspath(base):
            shutil.copyfile(base, ceinms_path)

        # 4) SO model = base with isometric force x mvic_factor. increase_isometric_force
        #    writes <base>_increased_X.osim and leaves base untouched.
        if mvic_factor and mvic_factor != 1.0:
            _os.increase_isometric_force(base, muscleList="all", factor=mvic_factor)
            produced = base.replace(".osim", f"_increased_{mvic_factor:.2f}.osim")
            src = produced if os.path.exists(produced) else base
            if os.path.abspath(src) != os.path.abspath(so_path):
                shutil.copyfile(src, so_path)
            # drop the raw increase_isometric_force byproduct — the SO model is so_path
            if (os.path.exists(produced)
                    and os.path.abspath(produced) != os.path.abspath(so_path)):
                try:
                    os.remove(produced)
                except OSError:
                    pass
        else:                                   # no boost: SO model == CEINMS/base
            so_path = ceinms_path if os.path.exists(ceinms_path) else base
            so_name = os.path.basename(so_path)

        print(f"[Session] {self.label}: scaled models saved:")
        print(f"   CEINMS      : {os.path.abspath(ceinms_path)}")
        print(f"   SO (mvic x{mvic_factor:.2f}): {os.path.abspath(so_path)}")
        return so_path

    def export_trials(self, trials=None, export_src=None, *,
                      replace=False, normalise=True, detect=True, log=print):
        """Model-INDEPENDENT c3d export for this session's trials: ingest loose c3d ->
        markers/GRF/EMG into the SHARED ``experimental/<trial>/`` folder, filter EMG,
        then (``normalise``) run the session-wide EMG normalise. The raw inputs are
        shared by every iteration, so this writes ONCE regardless of which iteration
        anchors it — prefer :meth:`Session.export` over per-iteration ``run(export=True)``.

        ``detect`` (default True) then runs movement detection over what was just
        exported, writing ``movement_detection.yaml`` and ``movement_detection.png``
        into each trial folder, beside the data they describe. It reads the markers
        and GRF the export just wrote, so this is the moment where it is cheapest —
        and it never touches ``session.yaml``: a disagreement is reported, not
        applied. Set ``detect=False`` to skip it. Returns the list of trials
        exported."""
        names = ([trials] if isinstance(trials, str)
                 else list(trials)) if trials else self._trial_names()
        if export_src:
            self.ingest_c3d(source=export_src, trials=names)
        done = []
        for tn in names:
            try:
                t = self.trial(tn)
                t.export_c3d()
                os.chdir(t.path)
                tr = t.get_time_range()
                if tr:
                    t.time_range = tr
                    t.update_trial_attribute('time_range', tr)
                try:
                    t.run_emg_filter()
                except Exception as ee:
                    log(f"  [export] EMG filter warn {tn}: {ee}")
                done.append(tn)
                log(f"  [export ok] {tn}")
            except Exception as e:
                log(f"  [export ERROR] {tn}: {e}")
        if normalise:
            try:
                self.run_emg_normalise(replace=replace, write_trials=names)
            except Exception as e:
                log(f"  [emg normalise ERROR]: {e}")
        if detect and done:
            # Weigh the participant BEFORE classifying. The detector's force
            # thresholds are in body weights; with body_mass unset it falls back
            # to a fraction of peak, which is weaker. The static trial has only
            # just been exported, so this is the first moment the plates can be
            # read — and the last moment before anything needs the number.
            try:
                import yaml as _y
                _yp = os.path.join(self.session_dir, "session.yaml")
                _c = _y.safe_load(open(_yp, encoding="utf-8")) or {}
                if _c.get("body_mass") in (None, "", 0):
                    _m = body_mass_from_static(self.session_dir,
                                               _c.get("static_trial"))
                    if _m:
                        _c["body_mass"] = _m
                        _ORDER = ["subject", "session", "static_trial", "body_mass"]
                        _o = {_k: _c[_k] for _k in _ORDER if _k in _c}
                        _o.update({_k: _v for _k, _v in _c.items() if _k not in _o})
                        with open(_yp, "w", encoding="utf-8") as _fh:
                            _y.safe_dump(_o, _fh, sort_keys=False, allow_unicode=True)
                        log(f"  [export] body_mass was unset -> {_m} kg "
                            f"(weighed on the plates, not entered)")
                    else:
                        log("  [export] body_mass unset and not measurable from "
                            "the static trial — detection thresholds will be "
                            "relative, not in body weights.")
            except Exception as e:
                log(f"  [export] body_mass warn: {type(e).__name__}: {e}")
            # Movement detection is part of the export, not a separate command
            # you have to remember to run: it needs exactly the markers and GRF
            # that were just written, and its answer belongs in the trial folder
            # next to them. A failure here warns — the export itself succeeded
            # and the pipeline can run without a classification.
            try:
                os.chdir(self.session_dir)      # the loop above chdir'd into a trial
            except Exception:
                pass
            try:
                from bioscout.movement_detector.session import classify_session
                classify_session(self.session_dir, per_trial=True, quiet=True)
            except Exception as e:
                log(f"  [detect WARN] movement detection skipped: "
                    f"{type(e).__name__}: {e}")
        return done

    def run(self, trials=None,
            export=False, export_src=None, *,
            detect=True,
            do_scale=False,
            do_exbiomec=False,
            do_muscle_analysis=False,
            do_so=False,
            do_ceinms=False,
            calibrate=False, calibration_trials=None,
            replace=False, skip_done=None,
            log=print, **_ignored):
        """Run the pipeline for THIS iteration.

        Stages (each optional, run in this order):
          do_scale    : build this iteration's scaled models first (delegates to
                        :meth:`scale_model`, reading session.yaml). Does not need
                        trials. Use when you want scale + analysis in one call.
          export      : (re)build inputs from c3d + refresh window + filter EMG,
                        then session-wide EMG normalise, then movement detection
                        into each ``2_experimental/<trial>/`` (``detect=False``
                        skips that last part). ``export_src`` first distributes
                        loose ``*.c3d`` into each trial's inputs/.
          do_exbiomec : external biomechanics only (IK -> ID). Muscle Analysis
                        is its own stage — see ``do_muscle_analysis``.
          do_muscle_analysis : Muscle Analysis (muscle lengths + moment arms).
                        Required by ``do_so``; when do_so runs without it, any
                        missing MA output is filled in without overwriting.
          do_so       : SO stage (SO -> muscle moments -> JRA), needs IK/ID/MA.
          do_ceinms   : CEINMS calibration (once) + per-trial execution -> JRA.

        ``replace`` overwrites existing outputs. ``trials`` defaults to all trials.
        ``calibrate`` (default True) — when do_ceinms is on, calibrate once first;
        set ``calibrate=False`` to SKIP calibration and run only execution -> JRA
        against the existing ``ceinms_calibration/subjectCalibrated.xml``.

        ``ceinms: {calibrated: false}`` in session.yaml overrides both: the
        iteration executes against ``subjectUncalibrated.xml`` (built straight
        from the .osim, nothing fitted), no calibration runs whatever
        ``calibrate`` says, and every execution folder is tagged ``_uncal`` so
        it cannot be mistaken for — or overwrite — a calibrated result. The same
        key on an ITERATION overrides the session-wide one, so an uncalibrated
        control can live beside the calibrated arms it is the control for.

        Unknown keyword arguments are ignored (forward-compat). Returns a dict
        of trials that completed each stage.
        """
        # Back-compat: this parameter was misspelled `do_muscle_analsysis` until
        # 2.0.1. Because unknown kwargs land in **_ignored, callers passing the
        # *correct* spelling were silently ignored — the flag never did anything.
        # Accept the old spelling explicitly so both work and neither is dropped.
        if "do_muscle_analsysis" in _ignored:
            do_muscle_analysis = _ignored.pop("do_muscle_analsysis")

        if skip_done is None:
            skip_done = not replace
        if do_scale:
            try:
                self.scale_model(replace=replace)
            except Exception as e:
                log(f"  [scale ERROR] {self.label}: {e}")
        # The analysis stages os.chdir() into each trial folder and never restore.
        # Capture the caller's cwd now and restore it on EVERY exit (finally at the
        # end) so a run never leaves the process cwd inside a trial dir — otherwise
        # a later relative path (e.g. Session.open("simulations/...")) resolves
        # against the trial folder and fails.
        _cwd0 = os.getcwd()
        try:                                    # start (and keep) the run quiet
            from bioscout.utils import get_openSim as _get_os; _os = _get_os()
            _os._quiet_osim()
        except Exception:
            pass
        names = ([trials] if isinstance(trials, str)
                 else list(trials)) if trials else self._trial_names()
        res = {"export": [], "exbiomec": [], "muscle_analysis": [], "so": [],
               "ceinms": [], "skipped": []}
        log(f"=== {self.label}  trials={names}  export={export} exbiomec={do_exbiomec} "
            f"ma={do_muscle_analysis} so={do_so} ceinms={do_ceinms} "
            f"replace={replace} ===")

        # -- Preflight: drop "ghost" trials with no raw experimental inputs. The
        # marker TRC is the fundamental input every stage (IK/ID/MA/SO/CEINMS)
        # depends on; without it there is nothing to run, and proceeding only
        # creates empty output folders and a garbage inputData.xml before failing.
        # The C3D export stage is exempt — it is what CREATES those inputs.
        if not export:
            _marker = _RAW_ATTR_FILES["markers"]
            _real = []
            for tn in names:
                if os.path.exists(os.path.join(experimental_dir(self.session_dir, tn), _marker)):
                    _real.append(tn)
                else:
                    res["skipped"].append(tn)
                    log(f"  [skip] {tn} — no experimental inputs "
                        f"({_marker} not found); nothing to run.")
            names = _real
            if not names:
                log("  [run] no trials with experimental inputs — nothing to do.")
                os.chdir(_cwd0)
                return res

        # -- Preflight: Windows MAX_PATH. Session trees + CEINMS execution
        # folder names blow past 260 chars at ~220-char roots, and the
        # failure surfaces as "file not found" deep inside OpenSim, hours in
        # (IMPLEMENTATIONS §1). Warn NOW, with the worst offenders named.
        if os.name == "nt":
            try:
                from . import run_check as _rc
                _hits = _rc.long_paths(self.path)
                if _hits:
                    log(f"  [preflight WARNING] {len(_hits)}+ path(s) within "
                        f"~40 chars of the Windows 260-char limit — CEINMS "
                        f"execution folders WILL exceed it. Worst: "
                        f"({_hits[0][0]} chars) {_hits[0][1]}")
                    log("  [preflight] shorten the project root path or "
                        "enable Windows long paths.")
            except Exception:                                  # noqa: BLE001
                pass

        _itc = (self._cfg.get("iterations") or {}).get(self.iteration, {}) or {}
        _ce = (self._cfg.get("ceinms") or {})

        def _model_disp(*names):
            """Resolved path of the model a stage will use, for the stage banner.

            session.yaml stores a bare filename; it is resolved against THIS
            iteration's folder (see Iteration.trial_config). Showing the full
            path makes it obvious which .osim actually drove the analysis —
            falls back to the bare name when the file is not there yet.
            """
            for n in names:
                if not n:
                    continue
                p = os.path.join(self.path, n)
                return p if os.path.exists(p) else f"{n}  (NOT FOUND in {self.path})"
            return "scaled.osim"

        def _stage(title, **info):
            """Log a section header for a pipeline stage + the settings it uses."""
            log("")
            log("=" * 72)
            log(f"=== STAGE — {title}   [{self.label}]")
            for k, v in info.items():
                if v not in (None, "", [], {}):
                    log(f"       {k}: {v}")
            log("=" * 72)

        if export:
            _stage("C3D export -> EMG filter -> session EMG normalise -> "
                   "movement detection", trials=names)
            res["export"] = self.export_trials(names, export_src=export_src,
                                               replace=replace, log=log,
                                               detect=detect)

        def _close_figs():
            """Drop every pyplot figure created by the last trial.

            pyplot keeps a global registry, so a figure that is savefig'd but
            never closed is retained for the life of the process. Ten plotting
            helpers in analysis/openSim/ceinms savefig without closing, and a
            full 6-iteration run writes ~1600 figures — measured at ~22 MB of
            retained memory each, i.e. gigabytes, which is what makes a long run
            crawl. Closing at the trial boundary bounds it regardless of which
            helper leaked. Figures stay usable after close; nothing in the batch
            path reads them back.
            """
            try:
                import matplotlib.pyplot as _plt
                _plt.close("all")
            except Exception:
                pass

        def _exbio(t, force=None):
            # ``force`` overrides ``replace``: prerequisite runs (before SO/CEINMS)
            # pass force=False so IK/ID are only computed when MISSING and are
            # reused otherwise — ``replace`` overwrites only the requested stage.
            from bioscout.utils.analysis import Analyse
            _r = replace if force is None else force
            if not isinstance(t, Analyse):
                print(f"[Session] {self.label}: _exbio expects an Analyse, got {type(t)}")
                return
                
            t.run_ik(replace=_r)
            _warn_frozen_ik(t)
            t.run_id(replace=_r)

        def _warn_frozen_ik(t):
            """Loud warning if IK produced near-static kinematics (broken marker
            registration / stale result) — else SO/CEINMS/JRA are garbage."""
            try:
                import numpy as _np
                p = os.path.join(t.path, "external_biomechanics", "joint_angles.mot")
                if not os.path.exists(p):
                    return
                L = open(p, errors="replace").read().splitlines()
                i = next(k for k, l in enumerate(L) if l.strip().lower() == "endheader")
                hdr = L[i + 1].split()
                d = _np.array([[float(x) for x in ln.split()] for ln in L[i + 2:]
                               if len(ln.split()) == len(hdr)])
                bad = {}
                for c in ("knee_angle_r", "hip_flexion_r", "knee_angle_l", "hip_flexion_l"):
                    if c in hdr:
                        v = d[:, hdr.index(c)]
                        rom = float(v.max() - v.min())
                        if rom < 5.0:
                            bad[c] = round(rom, 1)
                if bad:
                    log(f"  [WARN] {os.path.basename(t.path)}: IK looks FROZEN (ROM° {bad}) — "
                        f"kinematics broken; SO/CEINMS/JRA will be garbage. Re-run exbiomec / "
                        f"check marker registration for this model.")
            except Exception:
                pass

        def _log_inputs(tn, t, stage):
            """Indented per-trial line listing the input files/window for this stage,
            logged BEFORE the results."""
            def _b(attr):
                v = getattr(t, attr, None)
                return os.path.basename(str(v)) if v else "-"
            try:
                tr = t.get_time_range()
            except Exception:
                tr = None
            log(f"    [{tn}] inputs — model={_b('model_dir')}  markers={_b('markers')}  "
                f"grf={_b('setup_grf')}  time_range={tr}")

        if do_exbiomec:
            _stage("External biomechanics (IK -> ID)",
                   trials=names,
                   model=_model_disp(_itc.get("so_model"), _itc.get("ceinms_model"),
                                     "scaled.osim"))
            for tn in names:
                try:
                    log(f"  [exbiomec] {tn} — running (IK -> ID) ...")
                    _t = self.trial(tn)
                    _log_inputs(tn, _t, "exbiomec")
                    _exbio(_t)
                    res["exbiomec"].append(tn)
                    log(f"  [exbiomec ok] {tn}")
                    _close_figs()
                except Exception as e:
                    log(f"  [exbiomec ERROR] {tn}: {e}")

        if do_muscle_analysis:
            _stage("Muscle Analysis",
                   trials=names,
                   model=_model_disp(_itc.get("so_model"), _itc.get("ceinms_model"),
                                     "scaled.osim"))
            for tn in names:
                try:
                    log(f"  [MA] {tn} — running (Muscle Analysis) ...")
                    t = self.trial(tn)
                    _log_inputs(tn, t, "MA")
                    t.run_ma(replace=replace)
                    res["muscle_analysis"].append(tn)
                    # Say WHERE, per trial. The old line was just "[MA ok] <trial>",
                    # so a stage that wrote eight folders named none of them.
                    _ma_dir = os.path.abspath(os.path.join(t.path, t.ma))
                    log(f"  [MA ok] {tn} -> {_ma_dir}")
                    _close_figs()
                except Exception as e:
                    log(f"  [MA ERROR] {tn}: {e}")

        if do_so:
            _stage("Static Optimisation (SO -> muscle moments -> JRA)",
                   trials=names,
                   so_model=_model_disp(_itc.get("so_model"), _itc.get("ceinms_model"),
                                        "scaled.osim"))
            for tn in names:
                try:
                    log(f"  [SO] {tn} — running (SO -> muscle moments -> JRA) ...")
                    t = self.trial(tn)
                    _log_inputs(tn, t, "SO")
                    if not do_exbiomec:
                        _exbio(t, force=False)      # reuse existing IK/ID; only fill gaps
                    if not do_muscle_analysis:
                        # SO's muscle moments need moment arms, and exbiomec no
                        # longer produces them — fill the gap without overwriting.
                        t.run_ma(replace=False)
                    t.run_so(replace=replace)
                    t.calculate_muscle_moments(forces_type="so")
                    t.run_jra(replace=replace)
                    res["so"].append(tn)
                    log(f"  [SO ok] {tn}")
                    _close_figs()
                except Exception as e:
                    log(f"  [SO ERROR] {tn}: {e}")

        if do_ceinms:
            try:
                # An UNCALIBRATED iteration has nothing to calibrate. `calibrate`
                # is forced off HERE rather than left to the caller because
                # calibrating and then executing against subjectUncalibrated.xml
                # would burn the calibration entirely -- ten minutes producing a
                # file nothing downstream reads, and a run that looks like a
                # calibrated one in every log.
                # the iteration's own flag wins over the session default
                _uncal = not yaml_bool(
                    _itc.get("calibrated", _ce.get("calibrated", True)))
                if _uncal:
                    if calibrate:
                        log("  [CEINMS] ceinms.calibrated=false — SKIPPING "
                            "calibration; execution uses the uncalibrated "
                            "subject model")
                    calibrate = False
                    _stage("CEINMS uncalibrated setup (session level)",
                           ceinms_model=_model_disp(_itc.get("ceinms_model"),
                                                    _itc.get("so_model"), "scaled.osim"),
                           subject="subjectUncalibrated.xml")
                    self.prepare_uncalibrated_ceinms(replace=replace)
                if calibrate:
                    cal = (list(calibration_trials) if calibration_trials
                           else (self._resolve_calibration_trials() or []))
                    _stage("CEINMS calibration (session level)",
                           calibration_trials=cal, ceinms_model=_model_disp(_itc.get("ceinms_model"),
                                                    _itc.get("so_model"), "scaled.osim"),
                           alpha=_ce.get("alpha"), beta=_ce.get("beta"), gamma=_ce.get("gamma"))
                    _prep_failed = []
                    for cn in cal:
                        try:
                            ct = self.trial(cn)
                            ma_len = os.path.join(ct.path, ct.ma, "_MuscleAnalysis_Length.sto")
                            # Recompute IK->ID->MA when the muscle-length file is MISSING
                            # or STALE. Never reuse a stale IK/ID that was solved over a
                            # DIFFERENT window than MA: the CEINMS inputData window then
                            # inherits the stale IK/ID span, which has no muscle-length
                            # data, and calibration dies SILENTLY (reads inputs, writes no
                            # subjectCalibrated.xml). Keep all three consistent over the
                            # trial's current window.
                            #
                            # Staleness is a MTIME question, not a flag question. Keying
                            # this off `replace` alone re-solved IK/ID/MA on every CEINMS
                            # run even when the stages earlier in the SAME run had just
                            # produced them -- identical output, minutes per iteration. The
                            # model is the thing MA is derived from, so compare against it.
                            # (so_model vs ceinms_model differ only in max_isometric_force;
                            # force enters neither IK, ID nor moment arms, so either is a
                            # valid reference.)
                            _mdl = os.path.join(
                                self.path, _itc.get("ceinms_model", "scaled.osim"))
                            _stale = (not os.path.exists(ma_len)) or (
                                os.path.exists(_mdl)
                                and os.path.getmtime(ma_len) < os.path.getmtime(_mdl))
                            if _stale and not CEINMS_AUTOPREP:
                                _why = ("missing" if not os.path.exists(ma_len)
                                        else "older than " + os.path.basename(_mdl))
                                log(f"  [CEINMS ERROR] calibration trial {cn}: "
                                    f"{os.path.basename(ma_len)} is {_why}. "
                                    f"do_ceinms does not solve IK/ID/MA -- run that "
                                    f"stage first:")
                                log(f"      it.run(trials=['{cn}'], do_exbiomec=True, "
                                    f"do_muscle_analysis=True)")
                                log(f"    (or set bioscout.utils.session.CEINMS_AUTOPREP "
                                    f"= True to restore the old self-repairing behaviour)")
                                _prep_failed.append(cn)
                            elif _stale:
                                log(f"  [CEINMS prep] IK->ID->MA for calibration trial {cn}"
                                    f"  (CEINMS_AUTOPREP is on)")
                                ct.run_ik(replace=replace)
                                ct.run_id(replace=replace)
                                ct.run_ma(replace=replace)
                            else:
                                log(f"  [CEINMS prep] reusing IK/ID/MA for {cn} "
                                    f"(muscle lengths newer than the model)")
                        except Exception as e:
                            log(f"  [CEINMS prep ERROR] {cn}: {e}")
                    if _prep_failed:
                        # Calibrating on a trial whose inputs are stale is the
                        # silent-failure path this guard exists to close: it reads
                        # the inputs, writes no subjectCalibrated.xml, and the run
                        # continues against whatever calibration was there before.
                        raise RuntimeError(
                            "CEINMS calibration aborted: "
                            + ", ".join(_prep_failed)
                            + " lack usable IK/ID/MA. Run that stage first, or set "
                              "CEINMS_AUTOPREP = True.")
                    log(f"  [CEINMS] calibrating (trials={calibration_trials or cal}) — slow ...")
                    self.prepare_ceinms(replace=replace, calibration_trials=calibration_trials)
                elif _uncal:
                    _unc_subj = os.path.join(self.path, "ceinms_calibration",
                                             "subjectUncalibrated.xml")
                    if not os.path.exists(_unc_subj):
                        log(f"  [CEINMS ERROR] uncalibrated run but no subject at "
                            f"{_unc_subj}; the model could not be built from the .osim.")
                        os.chdir(_cwd0)
                        return res
                    log(f"  [CEINMS] executing against the UNCALIBRATED "
                        f"{os.path.basename(_unc_subj)} — output folders are tagged _uncal")
                else:
                    _cal_subj = os.path.join(self.path, "ceinms_calibration", "subjectCalibrated.xml")
                    if not os.path.exists(_cal_subj):
                        log(f"  [CEINMS ERROR] calibrate=False but no calibrated subject at {_cal_subj}; "
                            f"run once with calibrate=True first.")
                        os.chdir(_cwd0)
                        return res
                    log(f"  [CEINMS] skipping calibration; using existing {os.path.basename(_cal_subj)}")
                _stage("CEINMS execution (per trial -> muscle moments -> JRA)",
                       trials=names, ceinms_model=_model_disp(_itc.get("ceinms_model"),
                                                    _itc.get("so_model"), "scaled.osim"),
                       alpha=_ce.get("alpha"), beta=_ce.get("beta"), gamma=_ce.get("gamma"),
                       calibrate=calibrate)
                for tn in names:
                    try:
                        log(f"  [CEINMS 6/6] {tn} — execution -> muscle moments -> JRA ...")
                        t = self.trial(tn, force_type="CEINMS")
                        t.run_ceinms_exe()
                        t.calculate_muscle_moments(forces_type="ceinms")
                        t.run_jra_ceinms(replace=replace)
                        res["ceinms"].append(tn)
                        log(f"  [CEINMS ok] {tn}")
                        _close_figs()
                    except Exception as e:
                        log(f"  [CEINMS ERROR] {tn}: {e}")
            except Exception as e:
                log(f"  [CEINMS calibration ERROR]: {e}")

        # -- VERIFY: did every requested stage actually produce output?
        # A run used to be able to end "[settings] done" with export failed on
        # every trial — the errors scrolled past and later stages just found
        # nothing to do (IMPLEMENTATIONS §1). The log says what was ATTEMPTED;
        # this says what EXISTS, per trial per stage, and the difference is
        # printed as a table that cannot scroll past unnoticed.
        try:
            from . import run_check as _rc
            _req = [st for st, on in (("export", export),
                                      ("exbiomec", do_exbiomec),
                                      ("muscle_analysis", do_muscle_analysis),
                                      ("so", do_so), ("ceinms", do_ceinms))
                    if on]
            if _req and names:
                _rep = _rc.verify_run(
                    self.path, names, _req,
                    experimental_dir=os.path.join(self.session_dir,
                                                  "2_experimental"))
                log("  [verify] stage outputs on disk:")
                for _ln in _rc.format_report(_rep):
                    log("  " + _ln)
                _rc.write_report(_rep, os.path.join(self.path,
                                                    "run_report.json"))
                res["report"] = _rep
                res["ok"] = _rep["ok"]
                if not _rep["ok"]:
                    log(f"  [verify] RUN INCOMPLETE — {len(_rep['missing'])} "
                        f"trial-stage(s) produced no output (see "
                        f"run_report.json). Fix and re-run those stages.")
        except Exception as _ve:                               # noqa: BLE001
            log(f"  [verify] could not verify stage outputs: {_ve}")

        os.chdir(_cwd0)
        return res


# ---------------------------------------------------------------------------
# Session — the session-level setup object that holds runnable Iterations
# ---------------------------------------------------------------------------
def _bootstrap_project(session_dir, run_name, project_dir=None, verbose=False):
    """Start PROJECT-folder logging BEFORE Project's own auto-logging fires,
    then bootstrap ``bioscout.Project`` once so trials resolve their models.
    Shared by ``Session.open`` and ``Iteration.open``.

    2026-08-17: logs used to go into ``<session>/logs`` — one folder per
    subject x session made runs impossible to audit. Everything now lands in
    ``<project>/logs`` (session assumed at ``<project>/simulations/<pid>/<name>``,
    else the session's grandparent-of-grandparent), with the subject/session
    baked into the FILENAME so one folder still says which run is which.
    ``BIOSCOUT_LOG_DIR`` overrides the folder either way."""
    import bioscout
    from bioscout import utils
    if session_dir is not None:
        try:
            sd = os.path.abspath(str(session_dir))
            root = project_dir or os.path.dirname(os.path.dirname(os.path.dirname(sd)))
            utils.shared.start_logging(name=run_name,
                                       log_dir=os.path.join(str(root), "logs"))
        except Exception:
            pass
    bioscout.Project(project_dir, verbose=verbose)
    # Project bootstrap / first model loads can leave OpenSim's logger at 'info';
    # apply the configured level now so the run starts quiet.
    try:
        utils.openSim._quiet_osim()
    except Exception:
        pass


class Session:
    """A recording session (e.g. ``25_03_31``) — the setup object that unifies
    one session's config (``session.yaml``) and its model iterations. Iterations
    are the runnable units::

        s  = Session.open(r"...\\simulations\\Athlete_03\\25_03_31")
        s.iterations                     # ['cateli', 'gpk', 'gpk_mri', ...]
        it = s.iteration("gpk_mri")      # -> Iteration (runnable)
        it.run(trials=["Walking_02"], do_so=True)
        it.scale_model(muscle_opt=False)
        it.plot_summary(trials=["Walking_02"])
    """

    def __init__(self, session_dir):
        self.session_dir = os.path.abspath(session_dir)
        self.name = os.path.basename(self.session_dir)      # session id, e.g. "25_03_31"
        self._cfg = Iteration._read_yaml(os.path.join(self.session_dir, "session.yaml"))

    @classmethod
    def open(cls, session_path, *, project_dir=None, verbose=False):
        """Open a recording session by its FOLDER PATH (the directory holding
        ``session.yaml``, e.g. ``.../simulations/Athlete_03/25_03_31``).

        Starts logging into ``<session>/logs`` and bootstraps ``bioscout.Project``
        so its iterations resolve their models. Path-only — use ``.iteration(name)``
        to get a runnable :class:`Iteration`."""
        session_dir = os.path.abspath(session_path)
        if not os.path.exists(os.path.join(session_dir, "session.yaml")):
            raise FileNotFoundError(
                f"no session.yaml in {session_dir!r}. Pass the SESSION FOLDER path "
                f"(the dir holding session.yaml), e.g. "
                f".../simulations/Athlete_03/25_03_31.")
        _bootstrap_project(session_dir, os.path.basename(session_dir), project_dir, verbose)
        return cls(session_dir)

    # session-level folders that are NOT model iterations (shared inputs, raw c3d,
    # outputs, logs) — never treated, anchored on, or run as a model.
    _NON_ITERATION_DIRS = _layout.NON_ITERATION_DIRS

    @property
    def iterations(self):
        """Model-iteration folders present on disk (the ground truth), unioned
        with any ``session.yaml`` ``iterations`` keys — excluding shared dirs
        (``experimental``, ``logs``) and dotfiles. ``session.yaml`` need not list
        every iteration; the folders do."""
        root = _layout.iterations_root(self.session_dir)
        # A session that has only just been ingested has no 3_iterations yet —
        # it is created when the first model is scaled. Listing it raised
        # FileNotFoundError and took export down with it, which is backwards:
        # the raw export is model-INDEPENDENT and is exactly the step you run
        # before there is any model at all.
        if not os.path.isdir(root):
            on_disk = set()
        else:
            on_disk = {d for d in os.listdir(root)
                       if os.path.isdir(os.path.join(root, d))
                       and d not in self._NON_ITERATION_DIRS
                       and not d.startswith(".")
                       and "_backup_" not in d}
        # A half-migrated session may still have iterations directly under the
        # session folder; pick those up too rather than silently losing them.
        # But ONLY when the session is not already in the numbered layout: a
        # numbered session keeps its iterations in 3_iterations by definition,
        # so scanning its top level just collects whatever else is lying there.
        # It collected `_to_delete`, called it an iteration, and exported 11
        # trials into it.
        if root != self.session_dir and not _layout.is_numbered_layout(self.session_dir):
            on_disk |= {d for d in os.listdir(self.session_dir)
                        if os.path.isdir(os.path.join(self.session_dir, d))
                        and d not in self._NON_ITERATION_DIRS
                        and not d.startswith(".") and not d.startswith("_")
                        and "_backup_" not in d}
        cfg = {it for it in (self._cfg.get("iterations") or {})
               if os.path.isdir(_layout.iteration_path(self.session_dir, it))}
        return sorted(on_disk | cfg)

    def iteration(self, name):
        """Return the runnable :class:`Iteration` for model ``name``.

        An iteration DECLARED in session.yaml but not yet on disk is created
        here. Declaring it was previously not enough — the folder only appeared
        as a side effect of some earlier step, so adding a model to session.yaml
        and calling ``s.iteration(name)`` raised FileNotFoundError and listed
        the very name you had just declared as "available". A name that is not
        declared still raises, so a typo is still an error.
        """
        _p = _layout.iteration_path(self.session_dir, name)
        if not os.path.isdir(_p):
            _declared = (self._cfg.get("iterations") or {})
            if name in _declared:
                os.makedirs(_p, exist_ok=True)
                print(f"[Session] {self.name}: created iteration folder "
                      f"{os.path.relpath(_p, self.session_dir)} "
                      f"(declared in session.yaml)")
            else:
                raise FileNotFoundError(
                    f"iteration {name!r} not found under {self.session_dir} and "
                    f"not declared in session.yaml. available: {self.iterations}")
        return Iteration(self.session_dir, name)

    def run(self, iterations=None, *, do_scale=False, **kw):
        """Run several iterations with the same stage flags. ``iterations``
        defaults to every iteration present on disk. ``do_scale`` builds each
        iteration's scaled models first (delegates to :meth:`Iteration.scale_model`,
        reading ``session.yaml``); the remaining keyword args forward verbatim to
        :meth:`Iteration.run` (``trials``, ``do_exbiomec``, ``do_so``, ``do_ceinms``,
        ``replace`` ...)::

            Session.open(path).run(iterations=["gpk", "gpk_mri"], do_so=True)
            Session.open(path).run(do_scale=True, do_so=True)   # scale + analyse
        """
        out = {}
        for name in (iterations or self.iterations):
            out[name] = self.iteration(name).run(do_scale=do_scale, **kw)
        return out

    def export(self, trials=None, export_src=None, *, replace=False,
               normalise=True, detect=True):
        """Session-level c3d export, done ONCE. The raw markers/GRF/EMG are model-
        INDEPENDENT and shared by every iteration (they live in ``experimental/<trial>/``),
        so exporting per-iteration just repeats identical work. This ingests loose c3d
        -> markers/GRF/EMG -> filters EMG -> runs the session-wide EMG normalise ->
        classifies each trial (``detect``, writing ``movement_detection.yaml`` and
        ``.png`` into the trial folder), once.
        Prefer this over per-iteration ``run(export=True)``::

            s = Session.open(path)
            s.export(trials=["Deadlift_35kg_01", "Deadlift_35kg_02"], export_src="c3dfiles")
            for name in ("cateli", "gpk"):
                s.iteration(name).run(trials=[...], do_ceinms=True, calibrate=False)
        """
        its = self.iterations
        if not its:
            # Export writes markers/GRF/EMG into 2_experimental/, which no model
            # owns. The Iteration object is only being borrowed for its file
            # plumbing, so borrow a scratch one rather than refusing to run.
            _scratch = "_export"
            _p = _layout.iteration_path(self.session_dir, _scratch)
            os.makedirs(_p, exist_ok=True)
            print(f"[Session] {self.name}: no model iterations yet — exporting "
                  f"the raw trials anyway (they are model-independent).")
            try:
                return Iteration(self.session_dir, _scratch).export_trials(
                    trials=trials, export_src=export_src, replace=replace,
                    normalise=normalise, detect=detect)
            finally:
                # Remove the scratch anchor completely. Deleting it only when
                # empty left `3_iterations/_export/<trial>/{ceinms,inputs,...}`
                # behind, which then LOOKS like a model iteration on the next
                # run. Only empty scaffolding is removed — if anything actually
                # wrote a file in there, keep it and say so, because that means
                # an output landed somewhere it should not have.
                try:
                    _files = [os.path.join(_r, _f)
                              for _r, _, _fs in os.walk(_p) for _f in _fs]
                    if not _files:
                        import shutil as _sh
                        _sh.rmtree(_p, ignore_errors=True)
                    else:
                        print(f"[Session] {self.name}: scratch export folder "
                              f"{_p} holds {len(_files)} file(s) — kept for "
                              f"inspection, delete it once checked.")
                except OSError:
                    pass
        return self.iteration(its[0]).export_trials(
            trials=trials, export_src=export_src, replace=replace,
            normalise=normalise, detect=detect)

    def scale_model(self, iterations=None, **kw):
        """Convenience: scale EVERY iteration's model (scaling only, no analysis).
        The real implementation lives on :meth:`Iteration.scale_model`; this just
        loops it over ``iterations`` (default: all). For scale + analysis in one
        call, prefer ``run(do_scale=True, ...)``."""
        out = {}
        for name in (iterations or self.iterations):
            out[name] = self.iteration(name).scale_model(**kw)
        return out

    @property
    def results_dir(self):
        """Flat output folder for cross-model summaries:
        ``<project>/results/<subject>/<session>`` (no subfolders)."""
        from bioscout import utils as _u
        subject = os.path.basename(os.path.dirname(self.session_dir))
        proj = str(getattr(_u, "PROJECT_DIR", None)
                   or os.path.dirname(os.path.dirname(os.path.dirname(self.session_dir))))
        return os.path.join(proj, "results", subject, self.name)

    def summarise(self, trials=None, iterations=None, out_dir=None,
                  figures=("kinematics", "moments", "jcf"), leg="r"):
        """Cross-model comparison figures for this session: overlay EVERY model
        iteration (cateli/gpk/gpk_mri/...) on the same axes, one figure per trial
        TYPE, written FLAT into ``results_dir`` (``<project>/results/<subject>/
        <session>``). Reuses each iteration's on-disk kinematics / ID moments /
        JRA (no re-solve). Colours/labels come from ``session.yaml`` iterations;
        SO = solid, CEINMS = dashed.

            Session.open(path).summarise()
        """
        import numpy as np, pandas as pd, re
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from bioscout import utils as _u
        ss = getattr(getattr(_u, "settings", None), "SummarySettings", None)
        npts = int(getattr(ss, "npts", 101) or 101)
        dofs = [d for d in (getattr(ss, "dofs", None) or
                            ["hip_flexion_r", "knee_angle_r", "ankle_angle_r"]) if d.endswith("_" + leg) or d.startswith("pelvis")]
        joints = list(getattr(ss, "joints", None) or ["hip", "knee", "ankle"])
        iters = [m for m in (iterations or self.iterations)
                 if os.path.isdir(_layout.iteration_path(self.session_dir, m))]
        # FAIS patch 2026-08-12: `_trial_names` lives on Iteration, not Session,
        # so summarise() without an explicit `trials=` always raised
        # AttributeError. Take the session.yaml trial list directly, minus the
        # static trial and the marker-less EMG-only captures.
        if trials:
            names = [trials] if isinstance(trials, str) else list(trials)
        else:
            _emg_only = set(self._cfg.get("normalisation_trials") or [])
            _static = self._cfg.get("static_trial")
            names = [tn for tn, meta in (self._cfg.get("trials") or {}).items()
                     if tn != _static and tn not in _emg_only
                     and str((meta or {}).get("type", "")).lower() != "static"]
        icfg = (self._cfg.get("iterations") or {})
        color = {m: (icfg.get(m, {}) or {}).get("color", None) for m in iters}
        label = {m: (icfg.get(m, {}) or {}).get("label", m) for m in iters}
        bm = self._cfg.get("body_mass")
        bw = float(bm) * 9.81 if bm else None
        out = out_dir or self.results_dir
        os.makedirs(out, exist_ok=True)

        # group trials by TYPE (strip trailing _NN):  Walking, Squat_BW, ...
        types = {}
        for tn in names:
            types.setdefault(re.sub(r"_\d+$", "", tn), []).append(tn)

        def _load(model, trial, rel):
            p = os.path.join(_layout.iteration_path(self.session_dir, model), trial, rel)
            try:
                return _u.load_any_data_file(p) if os.path.exists(p) else None
            except Exception:
                return None

        def _tnorm(y):
            y = np.asarray(y, float); y = y[~np.isnan(y)]
            return (np.interp(np.linspace(0, 100, npts), np.linspace(0, 100, y.size), y)
                    if y.size > 1 else np.full(npts, np.nan))

        def _band(model, ttype, getter):
            """mean±sd across reps of one trial-type for one model."""
            curves = [getter(model, tn) for tn in types[ttype]]
            curves = [c for c in curves if c is not None]
            if not curves:
                return None, None
            a = np.vstack(curves)
            return np.nanmean(a, 0), np.nanstd(a, 0)

        made = []
        # ---- kinematics / moments : one panel per DOF ------------------------
        for kind, rel, suffix, unit in (("kinematics", "external_biomechanics/joint_angles.mot", "", "deg"),
                                        ("moments", "external_biomechanics/inverse_dynamics.sto", "_moment", "N·m")):
            if kind not in figures:
                continue
            cols = [d + suffix for d in dofs]
            for ttype in types:
                def getter_factory(col):
                    def g(model, tn):
                        df = _load(model, tn, rel)
                        if df is None or col not in df.columns:
                            return None
                        return _tnorm(df[col].to_numpy())
                    return g
                ncol = 3; nrow = int(np.ceil(len(cols) / ncol))
                fig, ax = plt.subplots(nrow, ncol, figsize=(4.2 * ncol, 2.4 * nrow), squeeze=False)
                for i, col in enumerate(cols):
                    a = ax[i // ncol][i % ncol]; g = getter_factory(col)
                    for m in iters:
                        mean, sd = _band(m, ttype, g)
                        if mean is None:
                            continue
                        a.plot(np.linspace(0, 100, npts), mean, color=color[m], lw=1.6, label=label[m])
                        a.fill_between(np.linspace(0, 100, npts), mean - sd, mean + sd, color=color[m], alpha=0.15)
                    a.set_title(col, fontsize=8); a.tick_params(labelsize=7)
                for j in range(len(cols), nrow * ncol):
                    ax[j // ncol][j % ncol].axis("off")
                h, l = ax[0][0].get_legend_handles_labels()
                fig.legend(h, l, loc="lower center", ncol=min(len(iters), 5), fontsize=8, frameon=False)
                fig.suptitle(f"{self.name} — {ttype} — {kind} ({unit})", fontsize=12)
                fig.tight_layout(rect=[0, 0.05, 1, 0.97])
                p = os.path.join(out, f"summary_{kind}_{ttype}.png")
                fig.savefig(p, dpi=int(getattr(ss, "dpi", 200) or 200)); plt.close(fig); made.append(p)

        # ---- JCF : resultant per joint, SO (solid) vs CEINMS (dashed) --------
        if "jcf" in figures:
            def resultant(df, joint):
                if df is None:
                    return None
                fc = [c for c in df.columns if joint in c.lower() and c.lower().endswith(("fx", "fy", "fz"))
                      and (f"_{leg}_" in c.lower() or c.lower().endswith(leg + "_fx"))]
                # fall back: any columns for the joint if leg-specific not found
                if len(fc) < 2:
                    fc = [c for c in df.columns if joint in c.lower() and c.lower().endswith(("fx", "fy", "fz"))]
                if len(fc) < 2:
                    return None
                comp = {c[-2:]: df[c].to_numpy(float) for c in fc[:3]}
                r = np.sqrt(sum(v ** 2 for v in comp.values()))
                r = r / bw if bw else r
                # FAIS patch 2026-08-12: the kinematics/moments getters return
                # _tnorm(...) but this one returned the RAW column, so _band
                # vstacked native-length curves and the plot below hit
                # "x and y must have same first dimension, shapes (101,) and
                # (234,)" for every trial that is not exactly npts frames long.
                return _tnorm(r)
            for ttype in types:
                fig, ax = plt.subplots(1, len(joints), figsize=(4.6 * len(joints), 3.4), squeeze=False)
                for k, joint in enumerate(joints):
                    a = ax[0][k]
                    for algo, rel, ls in (("SO", "joint_contact_forces/Analyse_JRA_ReactionLoads_SO.sto", "-"),
                                          ("CEINMS", "joint_contact_forces/Analyse_JRA_ReactionLoads_CEINMS.sto", "--")):
                        def g(model, tn, _rel=rel, _j=joint):
                            return resultant(_load(model, tn, _rel), _j)
                        for m in iters:
                            mean, sd = _band(m, ttype, g)
                            if mean is None:
                                continue
                            a.plot(np.linspace(0, 100, npts), mean, color=color[m], ls=ls, lw=1.5,
                                   label=f"{label[m]} {algo}")
                    a.set_title(f"{joint} |JCF|", fontsize=9); a.set_xlabel("% task", fontsize=8)
                    a.set_ylabel("x BW" if bw else "N", fontsize=8); a.tick_params(labelsize=7)
                h, l = ax[0][0].get_legend_handles_labels()
                fig.legend(h, l, loc="lower center", ncol=min(len(iters) * 2, 6), fontsize=7, frameon=False)
                fig.suptitle(f"{self.name} — {ttype} — joint contact forces (SO solid, CEINMS dashed)", fontsize=12)
                fig.tight_layout(rect=[0, 0.08, 1, 0.95])
                p = os.path.join(out, f"summary_jcf_{ttype}.png")
                fig.savefig(p, dpi=int(getattr(ss, "dpi", 200) or 200)); plt.close(fig); made.append(p)

        # ---- MUSCLE SHARE : who is loading each joint, per TASK ------------
        # FAIS addition 2026-08-12. NOT an induced-acceleration analysis: JRA
        # writes only the resultant contact force, so a muscle's true induced
        # contribution would need one JRA run per muscle. What this shows is each
        # muscle's force as a SHARE OF THE TOTAL MUSCLE FORCE crossing that joint
        # — the dominant term in the contact force, and the one that is free to
        # compute from files already on disk. Label it as such in any manuscript.
        if "muscle_share" in figures:
            TOPN = int(getattr(ss, "muscle_share_top_n", 5) or 5)
            COORD = {"hip": "hip_flexion", "knee": "knee_angle",
                     "ankle": "ankle_angle"}

            # "task" = session.yaml `type`, NOT the `types` dict above: that one
            # strips a trailing _NN, which for FAIS names (RunL1, SLSback_post2)
            # leaves every trial in a group of its own.
            tasks = {}
            for tn in names:
                k = str(((self._cfg.get("trials") or {}).get(tn) or {})
                        .get("type", "other")).lower()
                tasks.setdefault(k, []).append(tn)

            def _muscles_spanning(model, tn, joint):
                """Muscles with a non-zero moment arm about `joint` in this trial."""
                ma = _load(model, tn, os.path.join(
                    "muscle_analysis",
                    f"_MuscleAnalysis_MomentArm_{COORD[joint]}_{leg}.sto"))
                if ma is None:
                    return []
                keep = []
                for c in ma.columns:
                    if str(c).lower() == "time":
                        continue
                    v = pd.to_numeric(ma[c], errors="coerce").to_numpy(float)
                    if np.isfinite(v).any() and np.nanmax(np.abs(v)) > 1e-4:
                        keep.append(str(c))
                return keep

            def _forces(model, tn):
                for rel in ("static_optimisation/SO_StaticOptimization_force.sto",
                            "ceinms/Execution_a%s_b%s_g%s/MuscleForces.sto" % (
                                (self._cfg.get("ceinms") or {}).get("alpha", 10),
                                (self._cfg.get("ceinms") or {}).get("beta", 1),
                                (self._cfg.get("ceinms") or {}).get("gamma", 1000))):
                    df = _load(model, tn, rel)
                    if df is not None:
                        return df
                return None

            for task, tns in sorted(tasks.items()):
                if task in ("static", "generic", "other"):
                    continue
                fig, ax = plt.subplots(1, len(joints),
                                       figsize=(4.8 * len(joints), 3.6),
                                       squeeze=False)
                drew = False
                for k, joint in enumerate(joints):
                    a = ax[0][k]
                    per_muscle = {}          # muscle -> list of % curves
                    for m in iters:
                        for tn in tns:
                            span = _muscles_spanning(m, tn, joint)
                            df = _forces(m, tn)
                            if df is None or not span:
                                continue
                            cols = [c for c in df.columns if str(c) in span]
                            if not cols:
                                continue
                            arr = np.vstack([_tnorm(pd.to_numeric(df[c],
                                             errors="coerce").to_numpy(float))
                                             for c in cols])
                            tot = np.nansum(np.abs(arr), axis=0)
                            tot[tot <= 0] = np.nan
                            for c, row in zip(cols, arr):
                                per_muscle.setdefault(str(c), []).append(
                                    100.0 * np.abs(row) / tot)
                    if not per_muscle:
                        a.text(0.5, 0.5, "no muscle_analysis /\nforce data",
                               ha="center", va="center", transform=a.transAxes,
                               color="0.6", fontsize=8)
                        a.set_title(f"{joint}", fontsize=9)
                        continue
                    mean_of = {c: np.nanmean(np.vstack(v), axis=0)
                               for c, v in per_muscle.items()}
                    top = sorted(mean_of, key=lambda c: np.nanmax(mean_of[c]),
                                 reverse=True)[:TOPN]
                    xs = np.linspace(0, 100, npts)
                    for c in top:
                        a.plot(xs, mean_of[c], lw=1.6, label=c)
                        drew = True
                    rest = [c for c in mean_of if c not in top]
                    if rest:
                        a.plot(xs, np.nansum(np.vstack([mean_of[c] for c in rest]),
                                             axis=0),
                               lw=1.0, ls=":", color="0.5",
                               label=f"other ({len(rest)})")
                    a.set_title(f"{joint} — top {len(top)} of "
                                f"{len(mean_of)} muscles", fontsize=9)
                    a.set_xlabel("% task", fontsize=8)
                    a.set_ylabel("% of muscle force at the joint", fontsize=8)
                    a.set_xlim(0, 100); a.tick_params(labelsize=7)
                    a.grid(color="0.92", lw=0.5)
                    a.legend(fontsize=6, ncol=2, frameon=False)
                if not drew:
                    plt.close(fig)
                    print(f"[Session] muscle_share: no data for task {task!r}")
                    continue
                fig.suptitle(f"{self.name} — {task} — muscle share of the force "
                             f"crossing each joint ({leg} limb, "
                             f"{len(tns)} trial(s))", fontsize=12)
                fig.tight_layout(rect=[0, 0.02, 1, 0.93])
                pth = os.path.join(out, f"summary_muscle_share_{task}.png")
                fig.savefig(pth, dpi=int(getattr(ss, "dpi", 200) or 200))
                plt.close(fig); made.append(pth)

        # ---- MUSCLE CONTRIBUTIONS TO THE JOINT MOMENTS ----------------------
        # Method of:
        #   Maniar N, Schache AG, Cole MH, Opar DA (2019). Lower-limb muscle
        #   function during sidestep cutting. Journal of Biomechanics 82:186-192.
        #   https://doi.org/10.1016/j.jbiomech.2018.10.021
        # Their section 2.6: "Muscle-derived joint moments (computed from the
        # predicted muscle forces and their respective moment arms) were well
        # matched with the experimental joint moments (R^2 = 1.0 +/- 0.0;
        # nRMSE = 2.0e-2 +/- 0.03%)". So, for muscle i about coordinate q:
        #
        #       M_i(t) = F_i(t) * r_iq(t)
        #
        # with F from static optimisation (or CEINMS) and r from the OpenSim
        # MuscleAnalysis moment arms. Muscles are pooled into the functional
        # groups of their Fig. 3, and the net inverse-dynamics moment is drawn
        # shaded behind, exactly as they present it. Summing every muscle should
        # reproduce the ID moment to within the reserve/residual actuators —
        # that identity is the built-in check, reported per panel as R^2.
        if "muscle_moment" in figures:
            MANIAR_GROUPS = {
                "HAM":       ("bflh", "bfsh", "semimem", "semiten"),
                "RECFEM":    ("recfem",),
                "VASTI":     ("vasmed", "vaslat", "vasint"),
                "GMAX":      ("glmax1", "glmax2", "glmax3"),
                "GMED":      ("glmed1", "glmed2", "glmed3"),
                "GMIN":      ("glmin1", "glmin2", "glmin3"),
                "ILIOPSOAS": ("iliacus", "psoas"),
                "PIRI":      ("piri",),
                "ADD":       ("addbrev", "addlong", "addmagDist", "addmagIsch",
                              "addmagMid", "addmagProx"),
                "GAS":       ("gasmed", "gaslat"),
                "SOLEUS":    ("soleus",),
                "TIBANT":    ("tibant",),
            }
            MOM_COORDS = [("hip_flexion", "Hip flexion"),
                          ("hip_adduction", "Hip adduction"),
                          ("hip_rotation", "Hip rotation"),
                          ("knee_angle", "Knee flexion"),
                          ("ankle_angle", "Ankle plantarflexion")]

            def _grp_of(muscle):
                base = re.sub(r"_[rl]$", "", str(muscle))
                for g, mem in MANIAR_GROUPS.items():
                    if base in mem:
                        return g
                return None

            def _forces_df(model, tn):
                for rel in ("static_optimisation/SO_StaticOptimization_force.sto",
                            "ceinms/Execution_a%s_b%s_g%s/MuscleForces.sto" % (
                                (self._cfg.get("ceinms") or {}).get("alpha", 10),
                                (self._cfg.get("ceinms") or {}).get("beta", 1),
                                (self._cfg.get("ceinms") or {}).get("gamma", 1000))):
                    df = _load(model, tn, rel)
                    if df is not None:
                        return df
                return None

            tasks2 = {}
            for tn in names:
                k = str(((self._cfg.get("trials") or {}).get(tn) or {})
                        .get("type", "other")).lower()
                tasks2.setdefault(k, []).append(tn)

            for task, tns in sorted(tasks2.items()):
                if task in ("static", "generic", "other"):
                    continue
                fig, ax = plt.subplots(1, len(MOM_COORDS),
                                       figsize=(3.6 * len(MOM_COORDS), 3.6),
                                       squeeze=False)
                drew = False
                for k, (coord, nice) in enumerate(MOM_COORDS):
                    a = ax[0][k]
                    per_grp, nets, checks = {}, [], []
                    for m in iters:
                        for tn in tns:
                            ma = _load(model=m, trial=tn, rel=os.path.join(
                                "muscle_analysis",
                                f"_MuscleAnalysis_MomentArm_{coord}_{leg}.sto"))
                            fdf = _forces_df(m, tn)
                            idf = _load(m, tn,
                                        "external_biomechanics/inverse_dynamics.sto")
                            if ma is None or fdf is None:
                                continue
                            shared = [c for c in ma.columns
                                      if str(c).lower() != "time" and c in fdf.columns]
                            if not shared:
                                continue
                            tot = np.zeros(npts)
                            acc = {}
                            for c in shared:
                                r_ = _tnorm(pd.to_numeric(ma[c], errors="coerce")
                                            .to_numpy(float))
                                f_ = _tnorm(pd.to_numeric(fdf[c], errors="coerce")
                                            .to_numpy(float))
                                mi = f_ * r_                     # Maniar eq: F * r
                                g = _grp_of(c)
                                if g:
                                    acc[g] = acc.get(g, 0.0) + mi
                                tot = tot + np.nan_to_num(mi)
                            for g, v in acc.items():
                                per_grp.setdefault(g, []).append(v)
                            if idf is not None:
                                ncol = next((c for c in idf.columns
                                             if str(c).lower().startswith(
                                                 f"{coord}_{leg}")), None)
                                if ncol is not None:
                                    net = _tnorm(pd.to_numeric(idf[ncol],
                                                 errors="coerce").to_numpy(float))
                                    nets.append(net)
                                    ok = np.isfinite(net) & np.isfinite(tot)
                                    if ok.sum() > 2 and np.ptp(net[ok]) > 0:
                                        checks.append(1.0 - np.sum((net[ok]-tot[ok])**2)
                                                      / np.sum((net[ok]-net[ok].mean())**2))
                    if not per_grp:
                        a.text(0.5, 0.5, "no moment-arm /\nforce data", ha="center",
                               va="center", transform=a.transAxes, color="0.6",
                               fontsize=8)
                        a.set_title(nice, fontsize=9); continue
                    xs = np.linspace(0, 100, npts)
                    if nets:
                        a.fill_between(xs, 0, np.nanmean(np.vstack(nets), 0),
                                       color="0.82", zorder=1,
                                       label="net (inverse dynamics)")
                    order = sorted(per_grp,
                                   key=lambda g: np.nanmax(np.abs(
                                       np.nanmean(np.vstack(per_grp[g]), 0))),
                                   reverse=True)
                    for g in order[:6]:
                        a.plot(xs, np.nanmean(np.vstack(per_grp[g]), 0), lw=1.6,
                               label=g, zorder=3)
                        drew = True
                    a.axhline(0, color="0.5", lw=0.6, zorder=2)
                    ttl = nice + (f"  (R²={np.mean(checks):.2f})" if checks else "")
                    a.set_title(ttl, fontsize=9)
                    a.set_xlabel("% task", fontsize=8)
                    if k == 0:
                        a.set_ylabel("Moment (N·m)", fontsize=8)
                    a.set_xlim(0, 100); a.tick_params(labelsize=7)
                    a.legend(fontsize=6, frameon=False, ncol=2)
                if not drew:
                    plt.close(fig)
                    print(f"[Session] muscle_moment: no data for task {task!r}")
                    continue
                fig.suptitle(f"{self.name} — {task} — muscle contributions to the "
                             f"net joint moments ({leg} limb, {len(tns)} trial(s))"
                             f"   [method: Maniar et al. 2019, J Biomech 82:186-192]",
                             fontsize=11)
                fig.tight_layout(rect=[0, 0.02, 1, 0.92])
                pth = os.path.join(out, f"summary_muscle_moment_{task}.png")
                fig.savefig(pth, dpi=int(getattr(ss, "dpi", 200) or 200))
                plt.close(fig); made.append(pth)

        print(f"[Session] {self.name}: wrote {len(made)} summary figures -> {out}")
        return made

    # -- batch (project-wide) ---------------------------------------------
    @classmethod
    def batch_sessions(cls, project_dir=None, *, subjects=None, sessions=None,
                       iterations=None, trials=None, do_scale=False,
                       do_exbiomec=False, do_so=True, do_ceinms=True,
                       export=False, replace=False, verbose=True):
        """Batch-run the pipeline across a whole project — the session-centric
        replacement for the old ``pipeline.run_subject`` / ``run_pipeline`` batch
        layer. Discovers every ``simulations/<subject>/<session>/session.yaml`` and
        runs each through :meth:`run` (which loops the session's model iterations and
        drives :meth:`Iteration.run`). The per-session / per-iteration work already
        lives on ``Iteration.run`` — this only adds the outer subject/session loop.

        Filters (name or list; ``None`` = all): ``subjects`` (athlete folder),
        ``sessions`` (session id). ``iterations`` / ``trials`` restrict what each
        session runs. Stage flags (``do_scale``, ``do_exbiomec``, ``do_so``,
        ``do_ceinms``, ``export``, ``replace``) forward to :meth:`Iteration.run`::

            Session.batch_sessions("path/to/project", subjects="Athlete_03",
                                   do_scale=True, do_so=True, do_ceinms=True)

        Returns ``{subject: {session: {iteration: <Iteration.run result>}}}``.
        """
        import bioscout
        log = print if verbose else (lambda *a, **k: None)
        project_dir = os.path.abspath(project_dir or os.getcwd())
        proj = bioscout.Project(project_dir)      # bootstraps SIMULATIONS_DIR / logging
        sim = str(getattr(getattr(proj, "utils", None), "SIMULATIONS_DIR", None)
                  or os.path.join(project_dir, "simulations"))

        def _as_set(x):
            return None if x is None else ({x} if isinstance(x, str) else set(x))
        subj_f, sess_f = _as_set(subjects), _as_set(sessions)

        results = {}
        yaml_paths = sorted(glob.glob(os.path.join(sim, "*", "*", "session.yaml")))
        log(f"[batch_sessions] {len(yaml_paths)} session.yaml under {sim}")
        for yaml_path in yaml_paths:
            session_dir = os.path.dirname(yaml_path)
            sess_name = os.path.basename(session_dir)
            subj_name = os.path.basename(os.path.dirname(session_dir))
            if subj_f is not None and subj_name not in subj_f:
                continue
            if sess_f is not None and sess_name not in sess_f:
                continue
            log(f"\n=== batch_sessions: {subj_name}/{sess_name} ===")
            try:
                s = cls.open(session_dir, project_dir=project_dir, verbose=False)
                res = s.run(iterations=iterations, trials=trials, do_scale=do_scale,
                            do_exbiomec=do_exbiomec, do_so=do_so, do_ceinms=do_ceinms,
                            export=export, replace=replace)
            except Exception as e:
                log(f"  [batch ERROR] {subj_name}/{sess_name}: {e}")
                res = {"error": str(e)}
            results.setdefault(subj_name, {})[sess_name] = res
        return results

    # -- prune legacy per-iteration inputs/ --------------------------------
    #: Raw files that belong in the shared experimental folder, not per model.
    _LEGACY_INPUT_FILES = {
        "c3dfile.c3d", "marker_experimental.trc", "grf.mot", "GRF.xml",
        "emg.mot", "analog.csv", "emg_filtered.mot",
        "emg_filtered_normalised.mot",
    }

    def prune_legacy_inputs(self, iterations=None, trials=None, *,
                            dry_run=True, archive_dir=None, verbose=True):
        """Remove pre-YAML ``<iteration>/<trial>/inputs/`` folders.

        Before the session-centric layout, every model iteration kept its own
        copy of the raw inputs under ``<iteration>/<trial>/inputs/``. They are
        now exported once into the shared experimental folder, so those copies
        are dead weight — but nothing ever deleted them, so old sessions carry
        hundreds of MB of duplicated c3d/trc/GRF/EMG per model.

        This is the opposite of :meth:`reset`, which *keeps* ``inputs/`` and
        deletes derived output. Use ``reset`` to re-run a trial from its raw
        inputs; use this once, after migrating, to drop the raw inputs a
        migrated session no longer reads.

        **Safety.** A trial's ``inputs/`` is only removed when the shared
        experimental folder for that trial actually exists and holds the marker
        TRC — so this can never delete the last copy of something. Trials that
        fail the check are reported and left alone. Note that a legacy
        ``inputs/`` file is not necessarily byte-identical to the shared one
        (it may be an earlier export), so this discards an older version rather
        than a duplicate: pass ``archive_dir`` to move them aside instead of
        deleting.

        Defaults to ``dry_run=True`` — call it once to see the report, then
        again with ``dry_run=False``.

        Returns ``{"removed", "kept", "bytes", "skipped"}``.
        """
        import shutil
        log = print if verbose else (lambda *a, **k: None)
        it_scope = iterations if iterations is not None else self.iterations
        it_scope = [it_scope] if isinstance(it_scope, str) else list(it_scope)
        tfilter = ({trials} if isinstance(trials, str)
                   else set(trials) if trials else None)
        info = {"removed": [], "kept": [], "bytes": 0, "skipped": []}

        for it in it_scope:
            idir = _layout.iteration_path(self.session_dir, it)
            if not os.path.isdir(idir):
                continue
            for trial in sorted(os.listdir(idir)):
                if tfilter is not None and trial not in tfilter:
                    continue
                inp = os.path.join(idir, trial, "inputs")
                if not os.path.isdir(inp):
                    continue
                rel = os.path.relpath(inp, self.session_dir)

                # the shared copy must exist before we touch anything
                shared = experimental_dir(self.session_dir, trial)
                if os.listdir(inp) and not os.path.exists(
                        os.path.join(shared, _RAW_ATTR_FILES["markers"])):
                    info["skipped"].append(rel)
                    log(f"[prune] SKIP {rel}: no shared export at "
                        f"{os.path.relpath(shared, self.session_dir)} — this may "
                        f"be the only copy")
                    continue

                size = sum(os.path.getsize(os.path.join(inp, f))
                           for f in os.listdir(inp)
                           if os.path.isfile(os.path.join(inp, f)))
                info["bytes"] += size
                info["removed"].append(rel)
                mb = size / 1e6
                if dry_run:
                    log(f"[prune] would remove {rel} ({mb:.1f} MB)")
                    continue
                if archive_dir:
                    dst = os.path.join(archive_dir, rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.move(inp, dst)
                    log(f"[prune] archived {rel} ({mb:.1f} MB)")
                else:
                    shutil.rmtree(inp, ignore_errors=True)
                    log(f"[prune] removed {rel} ({mb:.1f} MB)")

        log(f"[prune] {'DRY-RUN ' if dry_run else ''}{self.name}: "
            f"{len(info['removed'])} inputs/ folder(s) "
            f"{'to free' if dry_run else 'freed'} {info['bytes'] / 1e6:.0f} MB"
            + (f"; {len(info['skipped'])} skipped (no shared export)"
               if info["skipped"] else ""))
        return info

    # -- reset (strip a session back to inputs-only) ----------------------
    _TRIAL_KEEP = {"inputs", "trial_settings.xml",
                   "c3dfile.c3d", "marker_experimental.trc", "grf.mot",
                   "GRF.xml", "emg.mot", "analog.csv"}
    _RAW_INPUTS = {"c3dfile.c3d"}

    @staticmethod
    def _is_trial_dir(path):
        """A trial folder holds raw inputs (flat) OR an ``inputs/`` subfolder OR a
        ``trial_settings.xml`` manifest."""
        return (os.path.isdir(os.path.join(path, "inputs"))
                or os.path.exists(os.path.join(path, "trial_settings.xml"))
                or os.path.exists(os.path.join(path, "c3dfile.c3d"))
                or os.path.exists(os.path.join(path, "marker_experimental.trc")))

    def reset(self, trials=None, iterations=None, *, backup=True, dry_run=False,
              trial_keep=None, raw_inputs=False, verbose=True):
        """Strip THIS session's trial folders back to inputs-only.

        Walks each model-iteration folder (``<session>/<iteration>/<trial>/``) and,
        as a fallback, any flat trial folders directly under the session; each trial
        is reduced to ``trial_keep`` (``inputs/`` + ``trial_settings.xml`` by default)
        and every generated output — IK/ID/MA/SO/JRA results, ``setup_*.xml``,
        ``MuscleAnalysis/``, ``Execution*/``, plots, filtered EMG ... — is deleted.
        Shared session dirs (``experimental/``, ``logs/``) are never touched.

        With ``backup`` (default) the whole session folder is first copied to a
        timestamped sibling ``<session>_backup_<YYYYmmdd_HHMMSS>``. Use ``dry_run=True``
        to PREVIEW without deleting (recommended first). ``raw_inputs=True`` also prunes
        each ``inputs/`` down to just the raw c3d. ``trials`` / ``iterations`` (name or
        list) scope the reset. Returns ``{"timestamp","backup","trials_reset","removed"}``.
        """
        import shutil, datetime
        log = print if verbose else (lambda *a, **k: None)
        tkeep = set(trial_keep) if trial_keep is not None else set(self._TRIAL_KEEP)
        tfilter = ({trials} if isinstance(trials, str)
                   else set(trials) if trials else None)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        info = {"timestamp": ts, "backup": None, "trials_reset": 0, "removed": 0}

        if backup and not dry_run:
            dst = f"{self.session_dir}_backup_{ts}"
            log(f"[reset] backup {self.name} -> {os.path.basename(dst)} (can take a while)")
            shutil.copytree(self.session_dir, dst)
            info["backup"] = dst
        elif backup:
            log(f"[reset] (dry-run) would back up {self.name} with ts={ts}")

        def _remove(p):
            info["removed"] += 1
            if dry_run:
                log(f"    would remove {os.path.relpath(p, self.session_dir)}")
                return
            try:
                shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
            except Exception as e:
                log(f"    [warn] could not remove {p}: {e}")

        # Scopes to search for trial folders: each requested iteration dir, plus the
        # session dir itself (legacy flat layout). De-dup by absolute path.
        it_scope = iterations if iterations is not None else self.iterations
        it_scope = [it_scope] if isinstance(it_scope, str) else list(it_scope)
        scopes = [os.path.join(self.session_dir, it) for it in it_scope]
        scopes.append(self.session_dir)
        seen = set()
        for scope in scopes:
            if not os.path.isdir(scope):
                continue
            for entry in sorted(os.listdir(scope)):
                p = os.path.join(scope, entry)
                ap = os.path.abspath(p)
                if ap in seen or entry in self._NON_ITERATION_DIRS or entry.startswith("."):
                    continue
                if not (os.path.isdir(p) and self._is_trial_dir(p)):
                    continue
                if tfilter is not None and entry not in tfilter:
                    continue
                seen.add(ap)
                keep_eff = ({"inputs", "trial_settings.xml"}
                            if trial_keep is None and os.path.isdir(os.path.join(p, "inputs"))
                            else tkeep)
                kept = 0
                for item in sorted(os.listdir(p)):
                    if item in keep_eff:
                        kept += 1
                    else:
                        _remove(os.path.join(p, item))
                if raw_inputs:
                    inp = os.path.join(p, "inputs")
                    if os.path.isdir(inp):
                        for item in sorted(os.listdir(inp)):
                            if item not in self._RAW_INPUTS:
                                _remove(os.path.join(inp, item))
                info["trials_reset"] += 1
                log(f"[reset] {os.path.relpath(p, self.session_dir)}: kept {kept} input(s)"
                    f"{' (raw c3d only)' if raw_inputs else ''}")
        log(f"[reset] {'DRY-RUN ' if dry_run else ''}{self.name}: "
            f"{info['trials_reset']} trials reset, {info['removed']} item(s) "
            f"{'to remove' if dry_run else 'removed'}; backup={info['backup']}")
        return info

    @classmethod
    def reset_project(cls, project_dir=None, *, subjects=None, sessions=None,
                      trials=None, backup=True, dry_run=False, verbose=True):
        """Reset every ``simulations/<subject>/<session>`` in a project back to
        inputs-only (see :meth:`reset`) — the session-centric replacement for the old
        ``pipeline.reset_simulations``. Optionally scoped by ``subjects`` / ``sessions``
        / ``trials``. Each session is backed up individually first (timestamped).
        Returns ``{subject: {session: <reset info>}}``."""
        import bioscout
        log = print if verbose else (lambda *a, **k: None)
        project_dir = os.path.abspath(project_dir or os.getcwd())
        proj = bioscout.Project(project_dir)
        sim = str(getattr(getattr(proj, "utils", None), "SIMULATIONS_DIR", None)
                  or os.path.join(project_dir, "simulations"))

        def _as_set(x):
            return None if x is None else ({x} if isinstance(x, str) else set(x))
        subj_f, sess_f = _as_set(subjects), _as_set(sessions)

        out = {}
        for yaml_path in sorted(glob.glob(os.path.join(sim, "*", "*", "session.yaml"))):
            session_dir = os.path.dirname(yaml_path)
            sess_name = os.path.basename(session_dir)
            subj_name = os.path.basename(os.path.dirname(session_dir))
            if subj_f is not None and subj_name not in subj_f:
                continue
            if sess_f is not None and sess_name not in sess_f:
                continue
            try:
                s = cls.open(session_dir, project_dir=project_dir, verbose=False)
                res = s.reset(trials=trials, backup=backup, dry_run=dry_run, verbose=verbose)
            except Exception as e:
                log(f"  [reset ERROR] {subj_name}/{sess_name}: {e}")
                res = {"error": str(e)}
            out.setdefault(subj_name, {})[sess_name] = res
        return out

    # s["gpk_mri"] is sugar for s.iteration("gpk_mri")
    def __getitem__(self, name):
        return self.iteration(name)

    def __iter__(self):
        return (self.iteration(n) for n in self.iterations)

    def __repr__(self):
        return f"<Session {self.name} — iterations={self.iterations}>"


# ---------------------------------------------------------------------------
# open_session / find_session_dir — locate a session on disk (back-compat)
# ---------------------------------------------------------------------------
def find_session_dir(session, project_dir=None, subject=None):
    """Locate the athlete/session folder holding session.yaml for ``session``
    (layout: ``simulations/<athlete>/<session>/session.yaml``).

    ``subject`` scopes the search to one participant, and you almost always want
    it: a session NAME like "pre" is not unique — every participant in the study
    has one. Without a subject this used to glob ``*/pre/session.yaml`` and
    return ``sorted(hits)[0]``, i.e. the lowest participant id that happens to
    have a folder by that name. Asking for subject 022's "pre" therefore solved
    009's data, under 022's name, silently. An ambiguous name with no subject is
    now an error rather than a coin toss.
    """
    from bioscout import utils
    sim = str(getattr(utils, "SIMULATIONS_DIR", "")
              or os.path.join(project_dir or os.getcwd(), "simulations"))
    if os.path.isabs(session) and os.path.exists(os.path.join(session, "session.yaml")):
        return session                      # already a session folder
    if subject:
        cand = os.path.join(sim, str(subject), session)
        if os.path.exists(os.path.join(cand, "session.yaml")):
            return cand
        raise FileNotFoundError(
            f"no session.yaml for subject={subject!r} session={session!r} "
            f"(looked for {os.path.join(sim, str(subject), session, 'session.yaml')})")
    hits = sorted(glob.glob(os.path.join(sim, "*", session, "session.yaml")))
    if not hits:
        cand = session if os.path.isabs(session) else os.path.join(sim, session)
        if os.path.exists(os.path.join(cand, "session.yaml")):
            return cand
        raise FileNotFoundError(
            f"no session.yaml for session={session!r} under {sim} "
            f"(looked for */{session}/session.yaml)")
    if len(hits) > 1:
        _who = [os.path.basename(os.path.dirname(os.path.dirname(h))) for h in hits]
        raise ValueError(
            f"session={session!r} is ambiguous — {len(hits)} participants have "
            f"one: {', '.join(_who[:8])}{' ...' if len(_who) > 8 else ''}. "
            f"Pass subject= (or an absolute session path); picking the first "
            f"would silently solve the wrong participant's data.")
    return os.path.dirname(hits[0])


def open_session(iteration, session=None, project_dir=None, verbose=False,
                 subject=None):
    """Back-compat: open ONE iteration by (iteration, session-id), returning a
    runnable :class:`Iteration`.

    Prefer ``Session.open(path).iteration("gpk_mri")`` in new code.
    """
    return Iteration.open(iteration, session=session, project_dir=project_dir,
                          verbose=verbose, subject=subject)


# batch orchestrator (loops subjects/sessions) is defined in bioscout.pipeline;
# re-exported here so bioscout.utils.session is the single session surface.
try:
    from bioscout.pipeline import run_subject
except Exception:      # pragma: no cover - avoid import cycle at module load
    run_subject = None


__all__ = [
    "Session", "Iteration", "open_session", "find_session_dir", "run_subject",
    "Model", "SessionSpec", "read_session_xml", "write_session_xml",
    "read_session_yaml", "write_session_yaml", "read_session", "convert_session_xml_to_yaml",
    "layout", "experimental_dir", "bind_experimental", "iteration_dir",
    "derived_trial_dir", "c3d_path", "SessionManager", "TrialValidator", "Analyse",
]
