"""
player_registry.py
------------------
Manages the per-project players.json file.

Each project has one players.json at its root (next to settings.py).
The registry enforces unique player IDs and stores all anthropometric /
demographic / clinical data so settings.py stays thin.

Schema for each player entry
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

REGISTRY_FILENAME = "players.json"

# On-disk schema version. Bump when the per-player record gains/changes fields
# so old files can be migrated forward (see PlayerRegistry._migrate).
#   v1 : flat dict {player_id: record}  (no schema_version key)
#   v2 : {"schema_version": 2, "players": {player_id: record}} + "tracking" field
SCHEMA_VERSION = 2

# Canonical field order written to the file (human-readable grouping).
_FIELD_ORDER = [
    "name", "group", "sex", "age", "height_m", "mass_kg",
    "dominant_leg", "affected_side", "injury_type", "surgery_date",
    "static_trial", "generic_model", "notes", "extra", "tracking", "added",
]

# Default values for a fresh player record.
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
    # Training-load tracking (load_tracking module). Holds per-player cloud
    # credentials and a lightweight cache of imported session summaries.
    # Raw per-sample traces are cached on disk (see load_tracking.tracking_store),
    # not inlined here, to keep players.json small.
    "tracking": {
        "credentials": {},      # {"zepp": {"token","region"}, "strava": {...}}
        "sessions": [],         # list of session-summary dicts
    },
    "added":         str(date.today()),
}


def _default_tracking() -> dict:
    return {"credentials": {}, "sessions": []}


class PlayerRegistry:
    """Load, query, and persist players.json for a project.

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

        # Detect format: versioned {"schema_version", "players"} vs old flat dict.
        if isinstance(raw, dict) and "players" in raw and "schema_version" in raw:
            self.file_version = int(raw.get("schema_version", 1))
            players = raw.get("players", {}) or {}
        else:
            self.file_version = 1            # legacy flat format
            players = raw or {}

        migrated = self._migrate(players, self.file_version)
        # Merge defaults so older files without new fields still work.
        self._data = {pid: self._merge_defaults(rec) for pid, rec in migrated.items()}

        # Persist forward-migration so the file is upgraded on first touch.
        if self.file_version < SCHEMA_VERSION and self._data:
            self.file_version = SCHEMA_VERSION
            self.save()

    @staticmethod
    def _merge_defaults(record: dict) -> dict:
        # deepcopy so the mutable defaults ("extra", "tracking") are never shared
        # between player records (otherwise edits to one leak into all others).
        merged = {**copy.deepcopy(_DEFAULTS), **record}
        # tracking is a nested dict — ensure its sub-keys exist without clobbering.
        tr = {**_default_tracking(), **(record.get("tracking") or {})}
        tr.setdefault("credentials", {})
        tr.setdefault("sessions", [])
        merged["tracking"] = copy.deepcopy(tr)
        return merged

    @staticmethod
    def _migrate(players: dict, from_version: int) -> dict:
        """Apply forward migrations to the players dict (in-place-safe copy)."""
        out = {pid: dict(rec) for pid, rec in players.items()}
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
        payload = {"schema_version": SCHEMA_VERSION, "players": ordered}
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def __contains__(self, player_id: str) -> bool:
        return player_id in self._data

    def __len__(self) -> int:
        return len(self._data)

    def get(self, player_id: str) -> dict:
        """Return a copy of the player record, raising KeyError if not found."""
        if player_id not in self._data:
            raise KeyError(
                f"Player '{player_id}' not found in {self.path}.\n"
                f"Run: python -m bioscout --add_player  to add them."
            )
        return dict(self._data[player_id])

    def all_ids(self) -> list[str]:
        return sorted(self._data.keys())

    def all_players(self) -> dict[str, dict]:
        return {pid: dict(rec) for pid, rec in self._data.items()}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add(self, player_id: str, fields: dict) -> dict:
        """Add a new player.  Raises ValueError if the ID already exists."""
        if player_id in self._data:
            raise ValueError(
                f"Player ID '{player_id}' already exists in {self.path}. "
                "IDs must be unique. Use update() to modify an existing player."
            )
        record = self._merge_defaults(dict(fields))
        record["added"] = str(date.today())
        self._data[player_id] = record
        self.save()
        return dict(record)

    def update(self, player_id: str, fields: dict) -> dict:
        """Update fields on an existing player."""
        if player_id not in self._data:
            raise KeyError(f"Player '{player_id}' not found.")
        self._data[player_id].update(fields)
        self.save()
        return dict(self._data[player_id])

    def remove(self, player_id: str) -> None:
        """Delete a player from the registry."""
        if player_id not in self._data:
            raise KeyError(f"Player '{player_id}' not found.")
        del self._data[player_id]
        self.save()

    # ------------------------------------------------------------------
    # Training-load tracking helpers (used by load_tracking / GUI)
    # ------------------------------------------------------------------
    def _tracking(self, player_id: str) -> dict:
        if player_id not in self._data:
            raise KeyError(f"Player '{player_id}' not found.")
        tr = self._data[player_id].setdefault("tracking", _default_tracking())
        tr.setdefault("credentials", {})
        tr.setdefault("sessions", [])
        return tr

    def get_credentials(self, player_id: str) -> dict:
        """Return this player's cloud credentials ({zepp:{...}, strava:{...}})."""
        return dict(self._tracking(player_id).get("credentials", {}))

    def set_credentials(self, player_id: str, credentials: dict) -> None:
        """Replace this player's cloud credentials and persist."""
        self._tracking(player_id)["credentials"] = dict(credentials)
        self.save()

    def get_sessions(self, player_id: str) -> list:
        """Return this player's cached session summaries (list of dicts)."""
        return [dict(s) for s in self._tracking(player_id).get("sessions", [])]

    def set_sessions(self, player_id: str, sessions: list) -> None:
        """Replace this player's cached session summaries and persist."""
        self._tracking(player_id)["sessions"] = list(sessions)
        self.save()

    # ------------------------------------------------------------------
    # Pretty print
    # ------------------------------------------------------------------

    def summary(self, player_id: Optional[str] = None) -> str:
        """Return a human-readable summary (one player or all)."""
        targets = {player_id: self._data[player_id]} if player_id else self._data
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
# Interactive prompt helper (used by --add_player CLI)
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


def prompt_add_player(registry: PlayerRegistry) -> Optional[str]:
    """Interactively collect player data and add to registry.

    Returns the new player ID on success, None if the user aborted.
    """
    print("\n── Add new player ──────────────────────────────────────")
    print(f"  Registry: {registry.path}\n")

    # Player ID
    while True:
        pid = input("  Player ID (unique, e.g. '012'): ").strip()
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
    print(f"  Adding player '{pid}'…")
    registry.add(pid, fields)
    print(f"  ✓ Saved to {registry.path}")
    print(f"\n{registry.summary(pid)}")
    return pid
