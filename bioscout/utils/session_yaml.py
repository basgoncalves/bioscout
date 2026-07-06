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
from __future__ import annotations

import os
from typing import Optional

try:
    import yaml  # PyYAML
except Exception as _e:                      # pragma: no cover
    yaml = None
    _YAML_IMPORT_ERROR = _e

from .session_config import SessionSpec, Model, read_session_xml


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
            # uniform: every iteration may declare a provided model. Accept
            # session_model / prescaled (session-relative, already personalised).
            session_model=m.get("session_model", m.get("prescaled")),
            static_trial=m.get("static_trial"),
            marker_weights={str(k): float(v) for k, v in (m.get("marker_weights") or {}).items()},
            preserve_mass_distribution=bool(m.get("preserve_mass_distribution", True)),
            linear_scaling=bool(m.get("linear_scaling", True)),
            marker_placer=bool(m.get("marker_placer", False)),
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
