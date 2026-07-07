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
    emg_muscle_mapping: Dict[str, list] = field(default_factory=dict)
    ceinms: Dict[str, str] = field(default_factory=dict)   # alpha/beta/gamma...
    # session-wide trial selections (which trials drive session-level steps)
    normalisation_trials: List[str] = field(default_factory=list)  # EMG MVC normalisation
    calibration_trials: List[str] = field(default_factory=list)    # CEINMS calibration
    trials: Dict[str, dict] = field(default_factory=dict)  # {trial: {time_range, events}}

    # -- convenience --------------------------------------------------------
    def get_model(self, name) -> Optional[Model]:
        return next((m for m in self.models if m.name == name), None)

    def model_names(self) -> List[str]:
        return [m.name for m in self.models]

    @property
    def c3d_dir(self) -> Optional[str]:
        return os.path.join(self.path, "c3dfiles") if self.path else None

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
        attrs["preserve_mass_distribution"] = "true" if m.preserve_mass_distribution else "false"
        me = ET.SubElement(ms, "model", attrs)
        if m.marker_weights:
            mw = ET.SubElement(me, "marker_weights")
            for seg, val in m.marker_weights.items():
                ET.SubElement(mw, "weight", segment=str(seg), value=str(val))
    if spec.emg_muscle_mapping:
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
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

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
        ))

    spec.emg_muscle_mapping = {str(k): _as_list(v)
                               for k, v in (data.get("emg_map", data.get("emg_muscle_mapping")) or {}).items()}
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
    if spec.emg_muscle_mapping:
        d["emg_map"] = {k: list(v) for k, v in spec.emg_muscle_mapping.items()}
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
            if m.model_ceinms: it["ceinms_model"] = m.model_ceinms
            if m.model:        it["so_model"] = m.model
            if m.label and m.label != m.name: it["label"] = m.label
            if m.color and m.color != "black": it["color"] = m.color
            if m.group:         it["group"] = m.group
            d["iterations"][m.name] = it
    return d


def write_session_yaml(spec: SessionSpec, path=None) -> str:
    """Serialise a :class:`SessionSpec` to ``session.yaml``. Returns the path."""
    _require_yaml()
    if path is None:
        path = os.path.join(spec.path, "session.yaml")
    elif os.path.isdir(path):
        path = os.path.join(path, "session.yaml")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(_spec_to_dict(spec), f, sort_keys=False, default_flow_style=False,
                       allow_unicode=True)
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
           "convert_session_xml_to_yaml", "read_session"]

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
           "derived_trial_dir", "c3d_path", "resolve_generic", "resolve_session_model"]


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
        with open(path, errors="replace") as f:
            return yaml.safe_load(f) or {}

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
        return os.path.join(self.session_dir, self.iteration)

    @property
    def label(self):
        return f"{self.name}/{self.iteration}"

    @classmethod
    def open(cls, iteration, session=None, project_dir=None, verbose=False):
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
        _hits = glob.glob(os.path.join(_root, "simulations", "*", session, "session.yaml"))
        session_dir = os.path.dirname(sorted(_hits)[0]) if _hits else None
        _run_name = f"{os.path.basename(session_dir) if session_dir else session}/{iteration}"
        _bootstrap_project(session_dir, _run_name, project_dir, verbose)
        if session_dir is None:      # non-standard layout: retry now SIMULATIONS_DIR is set
            session_dir = find_session_dir(session, project_dir)
        it = cls(session_dir, iteration)
        if not os.path.isdir(it.path):
            raise FileNotFoundError(
                f"iteration folder not found: {it.path}\n"
                f"  known iterations for this session: "
                f"{it.iterations or '(none in session.yaml)'}")
        return it

    def _trial_names(self):
        """Non-static trials from session.yaml that exist under this iteration."""
        trials_cfg = (self._cfg.get("trials") or {})
        out = [tr for tr, meta in trials_cfg.items()
               if str((meta or {}).get("type", "")).lower() != "static"
               and os.path.isdir(os.path.join(self.path, tr))]
        if out:
            return out
        if not os.path.isdir(self.path):
            return []
        return sorted(d for d in os.listdir(self.path)
                      if os.path.exists(os.path.join(self.path, d, "trial_settings.xml")))

    def trial(self, name, force_type="SO"):
        """Return an Analyse for one trial, with shared experimental inputs bound.

        Raw inputs (markers/grf/emg/GRF.xml) live once in
        ``<session>/experimental/<trial>/`` and are shared by every iteration.
        Setting ``experimental_dir`` makes Analyse redirect them there on every
        settings reload; derived outputs still write under this iteration's own
        trial folder."""
        t = Analyse(os.path.join(self.path, name))
        t.experimental_dir = experimental_dir(self.session_dir, name)
        if self._setup_dir:
            t._session_setup_dir = self._setup_dir
        t._apply_inputs_layout()
        self._apply_session_config(t, name, force_type)     # session.yaml is the source of truth
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
        if meta.get("type") is not None:
            cfg["trial_type"] = str(meta["type"])
        if self._cfg.get("body_mass") is not None:
            cfg["body_mass"] = self._cfg["body_mass"]
        for k in ("alpha", "beta", "gamma"):
            if ce.get(k) is not None:
                cfg[k] = ce[k]
        it = (self._cfg.get("iterations") or {}).get(self.iteration) or {}
        mkey = "ceinms_model" if str(force_type).upper().startswith("C") else "so_model"
        # Prefer the requested model; fall back to the other, then the plain
        # marker-registered scaled.osim — enough for external biomechanics
        # (IK/ID/MA) before the slow muscle-opt has produced scaled_opt_*.
        for mfile in (it.get(mkey), it.get("so_model"), it.get("ceinms_model"), "scaled.osim"):
            if not mfile:
                continue
            mpath = os.path.join(self.path, mfile)
            if os.path.exists(mpath):
                cfg["model_dir"] = mpath
                break
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

    def ingest_c3d(self, source=None, dry_run=False):
        """Distribute loose ``*.c3d`` into per-trial ``<trial>/inputs/c3dfile.c3d``
        under this iteration. ``source`` defaults to the session folder."""
        import shutil
        src = source or self.session_dir
        made = []
        for c in sorted(glob.glob(os.path.join(src, "*.c3d"))):
            stem = os.path.splitext(os.path.basename(c))[0]
            dst = os.path.join(self.path, stem, "inputs", "c3dfile.c3d")
            if os.path.exists(dst):
                continue
            made.append(stem)
            if dry_run:
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(c, dst)
        print(f"[Session] {self.label}: {'would ingest' if dry_run else 'ingested'} "
              f"{len(made)} c3d -> trial folders")
        return made

    def run_emg_normalise(self, replace=None):
        """Session-wide EMG normalisation: per-channel session-max (MVC-style),
        writing each trial's inputs/emg_filtered_normalised.mot in [0, 1]."""
        from bioscout import utils as _u
        envelopes = {}
        for t in self.trials:
            if replace is not None:
                t.update_trial_attribute("replace", replace)
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
        for t, env in envelopes.items():
            out = env[['time']].copy()
            for c in chans_sorted:
                if c in env:
                    out[c] = (env[c] / session_max[c]).clip(0.0, 1.0)
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
    def normalise_emg(self, replace=None):
        return self.run_emg_normalise(replace=replace)

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

    # -- model scaling ------------------------------------------------------
    def _resolve_model_file(self, rel):
        """Resolve a session.yaml model path (models/ , generic models/ , project root)."""
        if not rel:
            return None
        if os.path.isabs(rel):
            return rel
        from bioscout import utils as _u
        md = str(getattr(_u, "MODELS_DIR", "") or "")
        pd = str(getattr(_u, "PROJECT_DIR", None) or (os.path.dirname(md) if md else os.getcwd()))
        for base in (md, os.path.join(pd, "generic models"), pd):
            cand = os.path.join(base, rel)
            if os.path.exists(cand):
                return cand
        return rel

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
        from bioscout.utils import openSim as _os
        it = (self._cfg.get("iterations") or {}).get(self.iteration) or {}
        generic = self._resolve_model_file(it.get("generic"))
        if not generic or not os.path.exists(generic):
            print(f"[Session] {self.label}: generic model not found: {it.get('generic')!r}")
            return None
        trc = os.path.join(experimental_dir(self.session_dir, static_trial),
                           "marker_experimental.trc")
        if not os.path.exists(trc):
            try:
                self.trial(static_trial).export_c3d()
            except Exception as e:
                print(f"[Session] {self.label}: static export failed: {e}")
        if not os.path.exists(trc):
            print(f"[Session] {self.label}: static TRC not found: {trc}")
            return None

        markerset = self._resolve_model_file(self._cfg.get("markerset"))
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
        _os.scale_model(generic, trc, scaled, scale_setup_output_dir=self.path,
                        mass=(float(mass) if mass else None), marker_set_file=markerset,
                        linear_scaling=linear, marker_placer=mplace)

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
        else:                                   # no boost: SO model == CEINMS/base
            so_path = ceinms_path if os.path.exists(ceinms_path) else base
            so_name = os.path.basename(so_path)

        print(f"[Session] {self.label}: scaled models saved:")
        print(f"   CEINMS      : {os.path.abspath(ceinms_path)}")
        print(f"   SO (mvic x{mvic_factor:.2f}): {os.path.abspath(so_path)}")
        return so_path

    def run(self, trials=None,
            export=False, export_src=None, *,
            do_scale=False,
            do_exbiomec=False,
            do_muscle_analsysis=False,
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
                        then session-wide EMG normalise. ``export_src`` first
                        distributes loose ``*.c3d`` into each trial's inputs/.
          do_exbiomec : external biomechanics only (IK -> ID -> muscle analysis).
          do_so       : SO stage (IK -> ID -> MA -> SO -> muscle moments -> JRA).
          do_ceinms   : CEINMS calibration (once) + per-trial execution -> JRA.

        ``replace`` overwrites existing outputs. ``trials`` defaults to all trials.
        ``calibrate`` (default True) — when do_ceinms is on, calibrate once first;
        set ``calibrate=False`` to SKIP calibration and run only execution -> JRA
        against the existing ``ceinms_calibration/subjectCalibrated.xml``. Unknown
        keyword arguments are ignored (forward-compat). Returns a dict of trials
        that completed each stage.
        """
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
            from bioscout.utils import openSim as _os
            _os._quiet_osim()
        except Exception:
            pass
        names = ([trials] if isinstance(trials, str)
                 else list(trials)) if trials else self._trial_names()
        res = {"export": [], "exbiomec": [], "so": [], "ceinms": [], "skipped": []}
        log(f"=== {self.label}  trials={names}  export={export} exbiomec={do_exbiomec} "
            f"so={do_so} ceinms={do_ceinms} replace={replace} ===")

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

        _itc = (self._cfg.get("iterations") or {}).get(self.iteration, {}) or {}
        _ce = (self._cfg.get("ceinms") or {})

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
            _stage("C3D export -> EMG filter -> session EMG normalise", trials=names)
            if export_src:
                self.ingest_c3d(source=export_src)
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
                    res["export"].append(tn)
                    log(f"  [export ok] {tn}")
                except Exception as e:
                    log(f"  [export ERROR] {tn}: {e}")
            try:
                self.run_emg_normalise(replace=replace)
            except Exception as e:
                log(f"  [emg normalise ERROR]: {e}")

        def _exbio(t, force=None):
            # ``force`` overrides ``replace``: prerequisite runs (before SO/CEINMS)
            # pass force=False so IK/ID/MA are only computed when MISSING and are
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
            _stage("External biomechanics (IK -> ID -> Muscle Analysis)",
                   trials=names,
                   model=_itc.get("so_model") or _itc.get("ceinms_model") or "scaled.osim")
            for tn in names:
                try:
                    log(f"  [exbiomec] {tn} — running (IK -> ID -> MA) ...")
                    _t = self.trial(tn)
                    _log_inputs(tn, _t, "exbiomec")
                    _exbio(_t)
                    res["exbiomec"].append(tn)
                    log(f"  [exbiomec ok] {tn}")
                except Exception as e:
                    log(f"  [exbiomec ERROR] {tn}: {e}")

        if do_muscle_analsysis:
            _stage("Muscle Analysis",
                   trials=names,
                   model=_itc.get("so_model") or _itc.get("ceinms_model") or "scaled.osim")
            for tn in names:
                try:
                    log(f"  [MA] {tn} — running (IK -> ID -> MA) ...")
                    t = self.trial(tn)
                    _log_inputs(tn, t, "MA")
                    t.run_ma()
                    res["exbiomec"].append(tn)
                    log(f"  [MA ok] {tn}")
                except Exception as e:
                    log(f"  [MA ERROR] {tn}: {e}")

        if do_so:
            _stage("Static Optimisation (SO -> muscle moments -> JRA)",
                   trials=names, so_model=_itc.get("so_model", "scaled_opt_N10_mvicx3.00.osim"))
            for tn in names:
                try:
                    log(f"  [SO] {tn} — running (SO -> muscle moments -> JRA) ...")
                    t = self.trial(tn)
                    _log_inputs(tn, t, "SO")
                    if not do_exbiomec:
                        _exbio(t, force=False)      # reuse existing IK/ID/MA; only fill gaps
                    t.run_so(replace=replace)
                    t.calculate_muscle_moments(forces_type="so")
                    t.run_jra(replace=replace)
                    res["so"].append(tn)
                    log(f"  [SO ok] {tn}")
                except Exception as e:
                    log(f"  [SO ERROR] {tn}: {e}")

        if do_ceinms:
            try:
                if calibrate:
                    cal = (list(calibration_trials) if calibration_trials
                           else (self._resolve_calibration_trials() or []))
                    _stage("CEINMS calibration (session level)",
                           calibration_trials=cal, ceinms_model=_itc.get("ceinms_model", "scaled.osim"),
                           alpha=_ce.get("alpha"), beta=_ce.get("beta"), gamma=_ce.get("gamma"))
                    for cn in cal:
                        try:
                            ct = self.trial(cn)
                            ma_len = os.path.join(ct.path, ct.ma, "_MuscleAnalysis_Length.sto")
                            if not os.path.exists(ma_len):     # only compute if missing — reuse existing
                                log(f"  [CEINMS prep] muscle analysis for calibration trial {cn}")
                                ct.run_ik(replace=False)
                                ct.run_id(replace=False)
                                ct.run_ma(replace=False)
                        except Exception as e:
                            log(f"  [CEINMS prep ERROR] {cn}: {e}")
                    log(f"  [CEINMS] calibrating (trials={calibration_trials or cal}) — slow ...")
                    self.prepare_ceinms(replace=replace, calibration_trials=calibration_trials)
                else:
                    _cal_subj = os.path.join(self.path, "ceinms_calibration", "subjectCalibrated.xml")
                    if not os.path.exists(_cal_subj):
                        log(f"  [CEINMS ERROR] calibrate=False but no calibrated subject at {_cal_subj}; "
                            f"run once with calibrate=True first.")
                        os.chdir(_cwd0)
                        return res
                    log(f"  [CEINMS] skipping calibration; using existing {os.path.basename(_cal_subj)}")
                _stage("CEINMS execution (per trial -> muscle moments -> JRA)",
                       trials=names, ceinms_model=_itc.get("ceinms_model", "scaled.osim"),
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
                    except Exception as e:
                        log(f"  [CEINMS ERROR] {tn}: {e}")
            except Exception as e:
                log(f"  [CEINMS calibration ERROR]: {e}")

        os.chdir(_cwd0)
        return res


# ---------------------------------------------------------------------------
# Session — the session-level setup object that holds runnable Iterations
# ---------------------------------------------------------------------------
def _bootstrap_project(session_dir, run_name, project_dir=None, verbose=False):
    """Start session-folder logging (into ``<session>/logs``) BEFORE Project's
    own auto-logging fires — so every line lands in the session log, not
    ``<project>/logs`` — then bootstrap ``bioscout.Project`` once so trials
    resolve their models. Shared by ``Session.open`` and ``Iteration.open``."""
    import bioscout
    from bioscout import utils
    if session_dir is not None:
        try:
            utils.shared.start_logging(name=run_name,
                                       log_dir=os.path.join(session_dir, "logs"))
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

    # session-level folders that are NOT model iterations
    _NON_ITERATION_DIRS = {"experimental", "logs"}

    @property
    def iterations(self):
        """Model-iteration folders present on disk (the ground truth), unioned
        with any ``session.yaml`` ``iterations`` keys — excluding shared dirs
        (``experimental``, ``logs``) and dotfiles. ``session.yaml`` need not list
        every iteration; the folders do."""
        on_disk = {d for d in os.listdir(self.session_dir)
                   if os.path.isdir(os.path.join(self.session_dir, d))
                   and d not in self._NON_ITERATION_DIRS and not d.startswith(".")}
        cfg = {it for it in (self._cfg.get("iterations") or {})
               if os.path.isdir(os.path.join(self.session_dir, it))}
        return sorted(on_disk | cfg)

    def iteration(self, name):
        """Return the runnable :class:`Iteration` for model ``name``."""
        if not os.path.isdir(os.path.join(self.session_dir, name)):
            raise FileNotFoundError(
                f"iteration {name!r} not found under {self.session_dir}. "
                f"available: {self.iterations}")
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
        import numpy as np, re
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
                 if os.path.isdir(os.path.join(self.session_dir, m))]
        names = ([trials] if isinstance(trials, str) else list(trials)) if trials else self._trial_names()
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
            p = os.path.join(self.session_dir, model, trial, rel)
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
                return r / bw if bw else r
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
def find_session_dir(session, project_dir=None):
    """Locate the athlete/session folder holding session.yaml for ``session``
    (layout: ``simulations/<athlete>/<session>/session.yaml``)."""
    from bioscout import utils
    sim = str(getattr(utils, "SIMULATIONS_DIR", "")
              or os.path.join(project_dir or os.getcwd(), "simulations"))
    hits = glob.glob(os.path.join(sim, "*", session, "session.yaml"))
    if not hits:
        cand = session if os.path.isabs(session) else os.path.join(sim, session)
        if os.path.exists(os.path.join(cand, "session.yaml")):
            return cand
        raise FileNotFoundError(
            f"no session.yaml for session={session!r} under {sim} "
            f"(looked for */{session}/session.yaml)")
    return os.path.dirname(sorted(hits)[0])


def open_session(iteration, session=None, project_dir=None, verbose=False):
    """Back-compat: open ONE iteration by (iteration, session-id), returning a
    runnable :class:`Iteration`.

    Prefer ``Session.open(path).iteration("gpk_mri")`` in new code.
    """
    return Iteration.open(iteration, session=session, project_dir=project_dir, verbose=verbose)


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
