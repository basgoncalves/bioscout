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

import json
import os
from datetime import date
from pathlib import Path
from typing import Any, Optional

REGISTRY_FILENAME = "players.json"

# Canonical field order written to the file (human-readable grouping).
_FIELD_ORDER = [
    "name", "group", "sex", "age", "height_m", "mass_kg",
    "dominant_leg", "affected_side", "injury_type", "surgery_date",
    "static_trial", "generic_model", "notes", "extra", "added",
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
    "added":         str(date.today()),
}


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
        if self.path.is_file():
            try:
                with open(self.path, "r", encoding="utf-8") as fh:
                    raw = json.load(fh)
                # Merge defaults so older files without new fields still work.
                self._data = {
                    pid: {**_DEFAULTS, **record}
                    for pid, record in raw.items()
                }
            except (json.JSONDecodeError, OSError) as exc:
                raise RuntimeError(
                    f"Could not read {self.path}: {exc}"
                ) from exc

    def save(self) -> None:
        """Write the registry to disk (creates the file if it doesn't exist)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        ordered = {
            pid: {k: record.get(k, _DEFAULTS.get(k)) for k in _FIELD_ORDER}
            for pid, record in sorted(self._data.items())
        }
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(ordered, fh, indent=2, ensure_ascii=False)

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
        record = {**_DEFAULTS, **fields, "added": str(date.today())}
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
