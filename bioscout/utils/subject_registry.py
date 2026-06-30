"""
subject_registry.py
------------------
Manages the per-project subjects.json file.

Each project has one subjects.json at its root (next to settings.py).
The registry enforces unique subject IDs and stores all anthropometric /
demographic / clinical data so settings.py stays thin.

Schema for each subject entry
-----------------------------
{
    "name": "",
    "group": "fais",          # experimental group label
    "sex": "M",               # M / F / Other
    "age": null,              # years (int)
    "height_m": null,         # metres (float)
    "mass_kg": null,          # kilograms (float)
    "dominant_leg": "right",  # right / left / bilateral
    "affected_side": "",      # right / left / bilateral / "" (none)
    "injury_type": "",        # free text, e.g. "FAIS cam"
    "surgery_date": null,     # ISO-8601 string or null
    "static_trial": "static1",
    "notes": "",
    "extra": {},              # any future / project-specific fields
    "added": "YYYY-MM-DD"
}
"""

from __future__ import annotations

import copy
import json
import os
from datetime import date
from pathlib import Path
from typing import Any, Optional

REGISTRY_FILENAME = "subjects.json"

# On-disk schema version. Bump when the per-subject record gains/changes fields
# so old files can be migrated forward (see SubjectRegistry._migrate).
#   v1 : flat dict {subject_id: record}  (no schema_version key)
#   v2 : {"schema_version": 2, "subjects": {subject_id: record}} + "tracking" field
SCHEMA_VERSION = 2

# Canonical field order written to the file (human-readable grouping).
_FIELD_ORDER = [
    "name", "group", "sex", "age", "height_m", "mass_kg",
    "dominant_leg", "affected_side", "injury_type", "surgery_date",
    "static_trial", "generic_model", "notes", "extra", "tracking", "added",
]

# Default values for a fresh subject record.
_DEFAULTS: dict[str, Any] = {
    "name":          "",
    "group":         "",
    "sex":           "",
    "age":           None,
    "height_m":      None,
    "mass_kg":       None,
    "dominant_leg":  "right",
    "affected_side": "",
    "injury_type":   "",
    "surgery_date":  None,
    "static_trial":  "static1",
    # Path to the generic (unscaled) OpenSim model, relative to project root.
    # Scaled model will be written alongside it as <id>_scaled.osim.
    "generic_model": "Models/GPK_generic.osim",
    "notes":         "",
    "extra":         {},
    # Training-load tracking (load_tracking module). Holds per-subject cloud
    # credentials and a lightweight cache of imported session summaries.
    # Raw per-sample traces are cached on disk (see load_tracking.tracking_store),
    # not inlined here, to keep subjects.json small.
    "tracking": {
        "credentials": {},      # {"zepp": {"token","region"}, "strava": {...}}
        "sessions": [],         # list of session-summary dicts
    },
    "added":         str(date.today()),
}


def _default_tracking() -> dict:
    return {"credentials": {}, "sessions": []}


class SubjectRegistry:
    """Load, query, and persist subjects.json for a project.

    Parameters
    ----------
    project_root:
        Path to the project folder (the one that contains settings.py).
        If None, defaults to the current working directory.
    """

    def __init__(self, project_root: Optional[str | Path] = None):
        root = Path(project_root) if project_root else Path.cwd()
        self.path: Path = root / REGISTRY_FILENAME
        self._data: dict[str, dict] = {}
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        self.file_version = SCHEMA_VERSION
        if not self.path.is_file():
            return
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            raise RuntimeError(f"Could not read {self.path}: {exc}") from exc

        # Detect format: versioned {"schema_version", "subjects"} vs old flat dict.
        if isinstance(raw, dict) and "subjects" in raw and "schema_version" in raw:
            self.file_version = int(raw.get("schema_version", 1))
            subjects = raw.get("subjects", {}) or {}
        else:
            self.file_version = 1            # legacy flat format
            subjects = raw or {}

        migrated = self._migrate(subjects, self.file_version)
        # Merge defaults so older files without new fields still work.
        self._data = {pid: self._merge_defaults(rec) for pid, rec in migrated.items()}

        # Persist forward-migration so the file is upgraded on first touch.
        if self.file_version < SCHEMA_VERSION and self._data:
            self.file_version = SCHEMA_VERSION
            self.save()

    @staticmethod
    def _merge_defaults(record: dict) -> dict:
        # deepcopy so the mutable defaults ("extra", "tracking") are never shared
        # between subject records (otherwise edits to one leak into all others).
        merged = {**copy.deepcopy(_DEFAULTS), **record}
        # tracking is a nested dict — ensure its sub-keys exist without clobbering.
        tr = {**_default_tracking(), **(record.get("tracking") or {})}
        tr.setdefault("credentials", {})
        tr.setdefault("sessions", [])
        merged["tracking"] = copy.deepcopy(tr)
        return merged

    @staticmethod
    def _migrate(subjects: dict, from_version: int) -> dict:
        """Apply forward migrations to the subjects dict (in-place-safe copy)."""
        out = {pid: dict(rec) for pid, rec in subjects.items()}
        # v1 → v2: add the tracking section.
        if from_version < 2:
            for rec in out.values():
                rec.setdefault("tracking", _default_tracking())
        return out

    def save(self) -> None:
        """Write the registry to disk in the current versioned format."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        ordered = {
            pid: {k: record.get(k, _DEFAULTS.get(k)) for k in _FIELD_ORDER}
            for pid, record in sorted(self._data.items())
        }
        payload = {"schema_version": SCHEMA_VERSION, "subjects": ordered}
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def __contains__(self, subject_id: str) -> bool:
        return subject_id in self._data

    def __len__(self) -> int:
        return len(self._data)

    def get(self, subject_id: str) -> dict:
        """Return a copy of the subject record, raising KeyError if not found."""
        if subject_id not in self._data:
            raise KeyError(
                f"Subject '{subject_id}' not found in {self.path}.\n"
                f"Run: python -m bioscout --add_subject  to add them."
            )
        return dict(self._data[subject_id])

    def all_ids(self) -> list[str]:
        return sorted(self._data.keys())

    def all_subjects(self) -> dict[str, dict]:
        return {pid: dict(rec) for pid, rec in self._data.items()}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add(self, subject_id: str, fields: dict) -> dict:
        """Add a new subject.  Raises ValueError if the ID already exists."""
        if subject_id in self._data:
            raise ValueError(
                f"Subject ID '{subject_id}' already exists in {self.path}. "
                "IDs must be unique. Use update() to modify an existing subject."
            )
        record = self._merge_defaults(dict(fields))
        record["added"] = str(date.today())
        self._data[subject_id] = record
        self.save()
        return dict(record)

    def update(self, subject_id: str, fields: dict) -> dict:
        """Update fields on an existing subject."""
        if subject_id not in self._data:
            raise KeyError(f"Subject '{subject_id}' not found.")
        self._data[subject_id].update(fields)
        self.save()
        return dict(self._data[subject_id])

    def remove(self, subject_id: str) -> None:
        """Delete a subject from the registry."""
        if subject_id not in self._data:
            raise KeyError(f"Subject '{subject_id}' not found.")
        del self._data[subject_id]
        self.save()

    # ------------------------------------------------------------------
    # Training-load tracking helpers (used by load_tracking / GUI)
    # ------------------------------------------------------------------
    def _tracking(self, subject_id: str) -> dict:
        if subject_id not in self._data:
            raise KeyError(f"Subject '{subject_id}' not found.")
        tr = self._data[subject_id].setdefault("tracking", _default_tracking())
        tr.setdefault("credentials", {})
        tr.setdefault("sessions", [])
        return tr

    def get_credentials(self, subject_id: str) -> dict:
        """Return this subject's cloud credentials ({zepp:{...}, strava:{...}})."""
        return dict(self._tracking(subject_id).get("credentials", {}))

    def set_credentials(self, subject_id: str, credentials: dict) -> None:
        """Replace this subject's cloud credentials and persist."""
        self._tracking(subject_id)["credentials"] = dict(credentials)
        self.save()

    def get_sessions(self, subject_id: str) -> list:
        """Return this subject's cached session summaries (list of dicts)."""
        return [dict(s) for s in self._tracking(subject_id).get("sessions", [])]

    def set_sessions(self, subject_id: str, sessions: list) -> None:
        """Replace this subject's cached session summaries and persist."""
        self._tracking(subject_id)["sessions"] = list(sessions)
        self.save()

    # ------------------------------------------------------------------
    # Pretty print
    # ------------------------------------------------------------------

    def summary(self, subject_id: Optional[str] = None) -> str:
        """Return a human-readable summary (one subject or all)."""
        targets = {subject_id: self._data[subject_id]} if subject_id else self._data
        lines = []
        for pid, rec in sorted(targets.items()):
            lines.append(f"  [{pid}]")
            for k in _FIELD_ORDER:
                v = rec.get(k)
                if k == "extra" and not v:
                    continue
                lines.append(f"    {k:15s}: {v}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Interactive prompt helper (used by --add_subject CLI)
# ---------------------------------------------------------------------------

def _ask(prompt: str, default: Any = None, cast=str) -> Any:
    """Prompt the user for a value, applying an optional type cast."""
    default_str = f" [{default}]" if default not in (None, "") else ""
    raw = input(f"  {prompt}{default_str}: ").strip()
    if not raw:
        return default
    if cast is float:
        try:
            return float(raw)
        except ValueError:
            print(f"    → invalid number, keeping default ({default})")
            return default
    if cast is int:
        try:
            return int(raw)
        except ValueError:
            print(f"    → invalid integer, keeping default ({default})")
            return default
    return raw


def prompt_add_subject(registry: SubjectRegistry) -> Optional[str]:
    """Interactively collect subject data and add to registry.

    Returns the new subject ID on success, None if the user aborted.
    """
    print("\n── Add new subject ──────────────────────────────────────")
    print(f"  Registry: {registry.path}\n")

    # Subject ID
    while True:
        pid = input("  Subject ID (unique, e.g. '012'): ").strip()
        if not pid:
            print("  ID cannot be empty.")
            continue
        if pid in registry:
            print(f"  ✗ ID '{pid}' already exists. Use a different ID.")
            continue
        break

    print()
    fields: dict[str, Any] = {}
    fields["name"]          = _ask("Name (optional)",                  default="")
    fields["group"]         = _ask("Group  (e.g. fais / control)",     default="")
    fields["sex"]           = _ask("Sex    (M / F / Other)",            default="")
    fields["age"]           = _ask("Age    (years)",                    default=None, cast=int)
    fields["height_m"]      = _ask("Height (metres, e.g. 1.75)",        default=None, cast=float)
    fields["mass_kg"]       = _ask("Mass   (kg, e.g. 70.0)",            default=None, cast=float)
    fields["dominant_leg"]  = _ask("Dominant leg (right / left)",       default="right")
    fields["affected_side"] = _ask("Affected side (right/left/bilateral/none)", default="")
    fields["injury_type"]   = _ask("Injury type   (e.g. FAIS cam)",     default="")
    fields["surgery_date"]  = _ask("Surgery date  (YYYY-MM-DD or blank)", default=None)
    fields["static_trial"]  = _ask("Static trial name",                 default="static1")
    fields["notes"]         = _ask("Notes",                             default="")

    print()
    print(f"  Adding subject '{pid}'…")
    registry.add(pid, fields)
    print(f"  ✓ Saved to {registry.path}")
    print(f"\n{registry.summary(pid)}")
    return pid
