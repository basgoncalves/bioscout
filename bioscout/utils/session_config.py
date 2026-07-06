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
from __future__ import annotations

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
def discover_session_specs(simulations_dir, filename="session.xml",
                           subjects=None, sessions=None, require_session_xml=True):
    """Walk ``simulations/`` and return a :class:`SessionSpec` per session.

    Supports BOTH layouts:
      * ``<subject>/<session>/session.xml``  (session-based)
      * ``<subject>/session.xml``            (session-less; ``session=""``)

    ``require_session_xml`` skips folders without one. ``subjects`` / ``sessions``
    are optional name allow-lists."""
    sim = str(simulations_dir)
    out = []
    if not os.path.isdir(sim):
        return out
    subj_names = sorted(d for d in os.listdir(sim)
                        if os.path.isdir(os.path.join(sim, d)))
    if subjects:
        subj_names = [s for s in subj_names if s in set(subjects)]
    for subj in subj_names:
        sroot = os.path.join(sim, subj)
        # session-less: a session.xml directly under the subject folder
        if os.path.isfile(os.path.join(sroot, filename)):
            spec = read_session_xml(os.path.join(sroot, filename))
            # Folder name is the source of truth for identity — a stale/wrong
            # subject attribute in the xml must not override it.
            spec.subject = subj
            out.append(spec)
            continue
        # session-based: one level down
        for sess in sorted(d for d in os.listdir(sroot)
                           if os.path.isdir(os.path.join(sroot, d))):
            if sessions and sess not in set(sessions):
                continue
            xml = os.path.join(sroot, sess, filename)
            if os.path.isfile(xml):
                spec = read_session_xml(xml)
                # Folder names are authoritative for identity.
                spec.subject = subj
                spec.session = sess
                out.append(spec)
            elif not require_session_xml:
                out.append(SessionSpec(subject=subj, session=sess,
                                       path=os.path.join(sroot, sess)))
    return out


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


def migrate_to_session_xml(models, simulations_dir, athlete, session,
                           out_dir=None, c3d_source=None, reference_folder=None,
                           dry_run=True):
    """Build a ``session.xml`` from the OLD 'model-as-subject' layout.

    ``models``: list of dicts, one per model variant, e.g.::
        {"name": "Cateli", "folder": "Athlete_03_Cateli",
         "model": "models/Athlete_03_Cateli/25_03_31/scaled_opt_N10_mvicx3.00.osim",
         "model_ceinms": "...", "generic": "...", "static_trial": "Static_01",
         "color": "green", "group": "generic", "label": "Scaled (Cateli)"}

    Per-trial windows (``body_mass`` / ``time_range`` / event ``type``) are read
    from the FIRST variant's ``<trial>/trial_settings.xml``. Returns the built
    :class:`SessionSpec`; writes ``session.xml`` under ``out_dir`` (default
    ``simulations/<athlete>/<session>/``) unless ``dry_run``."""
    sim = str(simulations_dir)
    # Trial list + windows are SHARED across models, so read them from a
    # reference folder that has been analysed (has trial_settings.xml), not from
    # each model's own (possibly empty) folder.
    ref_folder = reference_folder or (models[0]["folder"] if models else None)
    trials, masses = {}, {}
    static_name = models[0].get("static_trial") if models else None
    ref_sess = os.path.join(sim, ref_folder, session) if ref_folder else None
    if ref_sess and os.path.isdir(ref_sess):
        for tr in sorted(os.listdir(ref_sess)):
            ts = os.path.join(ref_sess, tr, "trial_settings.xml")
            if not os.path.isfile(ts):
                continue
            try:
                r = ET.parse(ts).getroot()
            except Exception:
                continue
            entry = {}
            st, en = r.findtext("start_time"), r.findtext("end_time")
            if st and en:
                try:
                    entry["time_range"] = [float(st), float(en)]
                except ValueError:
                    pass
            ev = r.find("events")
            if ev is not None and ev.get("type"):
                entry["type"] = ev.get("type")
            trials[tr] = entry
            if r.findtext("body_mass"):
                try:
                    masses[tr] = float(r.findtext("body_mass"))
                except ValueError:
                    pass
            if static_name is None and entry.get("type") in ("generic", "static"):
                static_name = tr
    # Session body mass = the STATIC trial's value (quiet standing = true mass,
    # no barbell load); fall back to the first trial that recorded one.
    body_mass = masses.get(static_name) if static_name else None
    if body_mass is None and masses:
        body_mass = next(iter(masses.values()))
    spec = SessionSpec(subject=athlete, session=session,
                       path=out_dir or os.path.join(sim, athlete, session),
                       body_mass=body_mass, trials=trials, c3d_source=c3d_source)
    for m in models:
        spec.models.append(Model(
            name=m.get("name"), model=m.get("model"), model_ceinms=m.get("model_ceinms"),
            label=m.get("label"), color=m.get("color", "black"), group=m.get("group"),
            generic_model=m.get("generic"), static_trial=m.get("static_trial")))
    if not dry_run:
        write_session_xml(spec)
    return spec
