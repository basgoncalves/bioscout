"""
subject_profile.py — per-subject profiles for video analysis.

A *subject profile* stores everything we know about an athlete that helps the
pipeline: anthropometry (height, mass, sex, age), limb-segment proportions used
to sanity-check pose detection, a saved pixel-per-metre calibration, paths to
the subject's OpenSim / CEINMS model files, and per-subject detection settings.

Storage layout (scales to hundreds of subjects, dozens of tasks each)::

    <root>/                              ~/.powerlifting_app/subjects  by default
        <subject_id>/
            profile.json                 the data below
            models/                       subject-specific .osim / CEINMS files
            tasks/<task_name>/...         (reserved for per-task outputs)

One folder per subject keeps a subject's models and results together and avoids a
single giant registry file that would be slow/fragile at that scale. The
dropdown index is built by globbing ``<root>/*/profile.json`` (cheap, lazy).

The module is pure-stdlib so it can be imported and unit-tested without the GUI.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional


SCHEMA_VERSION = 1


def _slugify(name: str) -> str:
    """Filesystem-safe, stable id from a display name."""
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", name.strip()).strip("_").lower()
    return slug or f"subject_{int(time.time())}"


# ---------------------------------------------------------------------------
# Default limb-segment proportions (fraction of standing height).
# Approximate Winter/Drillis-Contini anthropometry — used as a fallback when a
# subject has no measured proportions yet. Keys are segment names; values are
# segment length / stature.
# ---------------------------------------------------------------------------
DEFAULT_SEGMENT_FRACTIONS: Dict[str, float] = {
    "head_neck": 0.182,
    "trunk": 0.288,
    "upper_arm": 0.186,
    "forearm": 0.146,
    "hand": 0.108,
    "thigh": 0.245,
    "shank": 0.246,
    "foot": 0.152,
}


@dataclass
class SubjectProfile:
    """All persisted data for one subject."""

    # Identity
    id: str = ""
    name: str = ""
    sex: str = ""                 # "M" | "F" | "" (unknown)
    age: Optional[float] = None

    # Anthropometry
    height_m: Optional[float] = None
    mass_kg: Optional[float] = None
    # Measured segment lengths / stature (overrides DEFAULT_SEGMENT_FRACTIONS).
    segment_fractions: Dict[str, float] = field(default_factory=dict)

    # Saved calibration (pixels per metre). Reused across that subject's videos.
    px_per_m: Optional[float] = None

    # Group / study classification (for group analysis and comparisons).
    group: str = ""               # e.g. "fais", "control", "athlete_a"

    # MoCap session folder names for this subject (relative to SIMULATIONS_DIR).
    # Used by project_analysis.py to load data across multiple sessions.
    # If empty, project_analysis falls back to settings.SUBJECTS[subject_id].sessions.
    mocap_sessions: List[str] = field(default_factory=list)

    # OpenSim / CEINMS model files for this subject (absolute or relative paths).
    template_model: str = ""      # AVAILABLE_MODELS key used as scaling template
    opensim_model: str = ""       # subject-specific scaled .osim
    ceinms_model: str = ""        # subject-specific CEINMS calibrated model

    # Detection helpers (feed the Video Analysis tab / analyzer).
    detect_settings: Dict[str, float] = field(default_factory=lambda: {
        "detect_interval": 1,
        "pose_max_delta_px": 50,
        "min_visibility": 0.3,
        # ratio of subject pixel-height to frame height when standing — helps
        # size the ROI box; 0 = unknown.
        "expected_height_frac": 0.0,
    })

    notes: str = ""
    schema_version: int = SCHEMA_VERSION

    # ---- derived helpers -------------------------------------------------
    def effective_segment_fractions(self) -> Dict[str, float]:
        """Measured proportions where available, else population defaults."""
        out = dict(DEFAULT_SEGMENT_FRACTIONS)
        out.update(self.segment_fractions or {})
        return out

    def expected_segment_px(self, segment: str) -> Optional[float]:
        """Expected length of a body segment in pixels, if height + scale known."""
        if not self.height_m or not self.px_per_m:
            return None
        frac = self.effective_segment_fractions().get(segment)
        if frac is None:
            return None
        return frac * self.height_m * self.px_per_m

    # ---- (de)serialisation ----------------------------------------------
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SubjectProfile":
        known = {f for f in cls.__dataclass_fields__}          # type: ignore[attr-defined]
        clean = {k: v for k, v in (d or {}).items() if k in known}
        prof = cls(**clean)
        # Merge any missing default detect_settings keys forward-compatibly.
        base = cls().detect_settings
        base.update(prof.detect_settings or {})
        prof.detect_settings = base
        return prof


class SubjectStore:
    """Directory-backed collection of subject profiles."""

    def __init__(self, root: Optional[Path] = None):
        if root is None:
            root = Path.home() / ".powerlifting_app" / "subjects"
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    # ---- paths -----------------------------------------------------------
    def subject_dir(self, subject_id: str) -> Path:
        return self.root / subject_id

    def profile_path(self, subject_id: str) -> Path:
        return self.subject_dir(subject_id) / "profile.json"

    def models_dir(self, subject_id: str) -> Path:
        d = self.subject_dir(subject_id) / "models"
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ---- index / listing -------------------------------------------------
    def list_ids(self) -> List[str]:
        if not self.root.exists():
            return []
        return sorted(
            p.parent.name for p in self.root.glob("*/profile.json")
        )

    def list_names(self) -> List[str]:
        """{id: display name} for populating a dropdown — cheap header read."""
        out = []
        for pid in self.list_ids():
            try:
                d = json.loads(self.profile_path(pid).read_text(encoding="utf-8"))
                out.append(d.get("name") or pid)
            except Exception:
                out.append(pid)
        return out

    def index(self) -> Dict[str, str]:
        """Return {display_name: id} for the dropdown (names are unique-ified)."""
        result: Dict[str, str] = {}
        for pid in self.list_ids():
            try:
                d = json.loads(self.profile_path(pid).read_text(encoding="utf-8"))
                name = d.get("name") or pid
            except Exception:
                name = pid
            label = name
            n = 2
            while label in result:           # disambiguate duplicate names
                label = f"{name} ({n})"
                n += 1
            result[label] = pid
        return result

    # ---- CRUD ------------------------------------------------------------
    def load(self, subject_id: str) -> Optional[SubjectProfile]:
        p = self.profile_path(subject_id)
        if not p.exists():
            return None
        try:
            return SubjectProfile.from_dict(
                json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            return None

    def save(self, profile: SubjectProfile) -> Path:
        if not profile.id:
            profile.id = _slugify(profile.name or "subject")
        self.subject_dir(profile.id).mkdir(parents=True, exist_ok=True)
        path = self.profile_path(profile.id)
        path.write_text(json.dumps(profile.to_dict(), indent=2), encoding="utf-8")
        return path

    def create(self, name: str, **kwargs) -> SubjectProfile:
        pid = _slugify(name)
        # Avoid clobbering an existing subject with the same slug.
        base, n = pid, 2
        while self.profile_path(pid).exists():
            pid = f"{base}_{n}"
            n += 1
        prof = SubjectProfile(id=pid, name=name, **kwargs)
        self.save(prof)
        return prof

    def delete(self, subject_id: str) -> bool:
        import shutil
        d = self.subject_dir(subject_id)
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
            return True
        return False


# ---------------------------------------------------------------------------
# Project-scoped store backed by the project's subjects.json
# ---------------------------------------------------------------------------
#
# This is the SINGLE source of truth for subjects, shared with the
# `python -m bioscout --add_subject` CLI (which writes the same subjects.json via
# utils.subject_registry.SubjectRegistry), so subjects added in the CLI appear in
# the GUI dropdown and vice-versa. It exposes the same public API the Video
# Analysis tab uses (index / load / save / create / delete).
#
# Field mapping (SubjectProfile  <->  subjects.json record):
#   native columns : name, group, sex, age, height_m, mass_kg, notes
#   everything else (template_model, opensim_model, ceinms_model, px_per_m,
#   segment_fractions, mocap_sessions, detect_settings, schema_version) is
#   stored under the record's "extra" dict so nothing is lost on round-trip,
#   while registry-only columns (dominant_leg, affected_side, injury_type,
#   surgery_date, static_trial, generic_model, added) are preserved untouched.
# ---------------------------------------------------------------------------

# SubjectProfile fields persisted inside the subjects.json "extra" blob.
_EXTRA_KEYS = (
    "template_model", "opensim_model", "ceinms_model", "px_per_m",
    "segment_fractions", "mocap_sessions", "detect_settings", "schema_version",
)


class ProjectSubjectStore:
    """`SubjectStore`-compatible facade over a project's subjects.json."""

    def __init__(self, project_root: Optional[Path] = None):
        from utils.subject_registry import SubjectRegistry
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self._registry = SubjectRegistry(self.project_root)

    # ---- mapping helpers -------------------------------------------------
    @staticmethod
    def _record_to_profile(pid: str, rec: dict) -> SubjectProfile:
        extra = dict(rec.get("extra") or {})
        data = {
            "id": pid,
            "name": rec.get("name", "") or "",
            "group": rec.get("group", "") or "",
            "sex": rec.get("sex", "") or "",
            "age": rec.get("age"),
            "height_m": rec.get("height_m"),
            "mass_kg": rec.get("mass_kg"),
            "notes": rec.get("notes", "") or "",
        }
        for k in _EXTRA_KEYS:
            if k in extra:
                data[k] = extra[k]
        if not data.get("opensim_model") and rec.get("generic_model"):
            data["opensim_model"] = rec.get("generic_model")
        return SubjectProfile.from_dict(data)

    @staticmethod
    def _profile_to_fields(prof: SubjectProfile, existing_extra: dict) -> dict:
        extra = dict(existing_extra or {})
        for k in _EXTRA_KEYS:
            extra[k] = getattr(prof, k)
        return {
            "name": prof.name,
            "group": prof.group,
            "sex": prof.sex,
            "age": prof.age,
            "height_m": prof.height_m,
            "mass_kg": prof.mass_kg,
            "notes": prof.notes,
            "extra": extra,
        }

    # ---- index / listing -------------------------------------------------
    def index(self) -> Dict[str, str]:
        """Return {display_name: id} for the dropdown (names unique-ified)."""
        result: Dict[str, str] = {}
        for pid, rec in sorted(self._registry.all_subjects().items()):
            name = (rec.get("name") or "").strip() or pid
            label, n = name, 2
            while label in result:
                label = f"{name} ({n})"
                n += 1
            result[label] = pid
        return result

    @property
    def _profiles(self) -> Dict[str, SubjectProfile]:
        """{id: SubjectProfile} — kept for callers that introspect the store."""
        return {pid: self._record_to_profile(pid, rec)
                for pid, rec in self._registry.all_subjects().items()}

    # ---- CRUD ------------------------------------------------------------
    def load(self, subject_id: str) -> Optional[SubjectProfile]:
        try:
            rec = self._registry.get(subject_id)
        except KeyError:
            return None
        return self._record_to_profile(subject_id, rec)

    def save(self, profile: SubjectProfile) -> Path:
        if not profile.id:
            profile.id = _slugify(profile.name or "subject")
        existing_extra = {}
        if profile.id in self._registry:
            existing_extra = (self._registry.get(profile.id).get("extra") or {})
        fields = self._profile_to_fields(profile, existing_extra)
        if profile.id in self._registry:
            self._registry.update(profile.id, fields)
        else:
            self._registry.add(profile.id, fields)
        return self._registry.path

    def create(self, name: str, **kwargs) -> SubjectProfile:
        pid = _slugify(name)
        base, n = pid, 2
        while pid in self._registry:
            pid = f"{base}_{n}"
            n += 1
        prof = SubjectProfile(id=pid, name=name, **kwargs)
        self.save(prof)
        return prof

    def delete(self, subject_id: str) -> bool:
        if subject_id in self._registry:
            self._registry.remove(subject_id)
            return True
        return False


    def models_dir(self, subject_id: str) -> Path:
        d = self.project_root / "Models" / subject_id
        d.mkdir(parents=True, exist_ok=True)
        return d
