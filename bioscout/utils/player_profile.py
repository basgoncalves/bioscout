"""
player_profile.py — per-player profiles for video analysis.

A *player profile* stores everything we know about an athlete that helps the
pipeline: anthropometry (height, mass, sex, age), limb-segment proportions used
to sanity-check pose detection, a saved pixel-per-metre calibration, paths to
the player's OpenSim / CEINMS model files, and per-player detection settings.

Storage layout (scales to hundreds of players, dozens of tasks each)::

    <root>/                              ~/.powerlifting_app/players  by default
        <player_id>/
            profile.json                 the data below
            models/                       player-specific .osim / CEINMS files
            tasks/<task_name>/...         (reserved for per-task outputs)

One folder per player keeps a player's models and results together and avoids a
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
    return slug or f"player_{int(time.time())}"


# ---------------------------------------------------------------------------
# Default limb-segment proportions (fraction of standing height).
# Approximate Winter/Drillis-Contini anthropometry — used as a fallback when a
# player has no measured proportions yet. Keys are segment names; values are
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
class PlayerProfile:
    """All persisted data for one player."""

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

    # Saved calibration (pixels per metre). Reused across that player's videos.
    px_per_m: Optional[float] = None

    # Group / study classification (for group analysis and comparisons).
    group: str = ""               # e.g. "fais", "control", "athlete_a"

    # MoCap session folder names for this player (relative to SIMULATIONS_DIR).
    # Used by project_analysis.py to load data across multiple sessions.
    # If empty, project_analysis falls back to settings.PLAYERS[player_id].sessions.
    mocap_sessions: List[str] = field(default_factory=list)

    # OpenSim / CEINMS model files for this player (absolute or relative paths).
    template_model: str = ""      # AVAILABLE_MODELS key used as scaling template
    opensim_model: str = ""       # player-specific scaled .osim
    ceinms_model: str = ""        # player-specific CEINMS calibrated model

    # Detection helpers (feed the Video Analysis tab / analyzer).
    detect_settings: Dict[str, float] = field(default_factory=lambda: {
        "detect_interval": 1,
        "pose_max_delta_px": 50,
        "min_visibility": 0.3,
        # ratio of player pixel-height to frame height when standing — helps
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
    def from_dict(cls, d: dict) -> "PlayerProfile":
        known = {f for f in cls.__dataclass_fields__}          # type: ignore[attr-defined]
        clean = {k: v for k, v in (d or {}).items() if k in known}
        prof = cls(**clean)
        # Merge any missing default detect_settings keys forward-compatibly.
        base = cls().detect_settings
        base.update(prof.detect_settings or {})
        prof.detect_settings = base
        return prof


class PlayerStore:
    """Directory-backed collection of player profiles."""

    def __init__(self, root: Optional[Path] = None):
        if root is None:
            root = Path.home() / ".powerlifting_app" / "players"
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    # ---- paths -----------------------------------------------------------
    def player_dir(self, player_id: str) -> Path:
        return self.root / player_id

    def profile_path(self, player_id: str) -> Path:
        return self.player_dir(player_id) / "profile.json"

    def models_dir(self, player_id: str) -> Path:
        d = self.player_dir(player_id) / "models"
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
    def load(self, player_id: str) -> Optional[PlayerProfile]:
        p = self.profile_path(player_id)
        if not p.exists():
            return None
        try:
            return PlayerProfile.from_dict(
                json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            return None

    def save(self, profile: PlayerProfile) -> Path:
        if not profile.id:
            profile.id = _slugify(profile.name or "player")
        self.player_dir(profile.id).mkdir(parents=True, exist_ok=True)
        path = self.profile_path(profile.id)
        path.write_text(json.dumps(profile.to_dict(), indent=2), encoding="utf-8")
        return path

    def create(self, name: str, **kwargs) -> PlayerProfile:
        pid = _slugify(name)
        # Avoid clobbering an existing player with the same slug.
        base, n = pid, 2
        while self.profile_path(pid).exists():
            pid = f"{base}_{n}"
            n += 1
        prof = PlayerProfile(id=pid, name=name, **kwargs)
        self.save(prof)
        return prof

    def delete(self, player_id: str) -> bool:
        import shutil
        d = self.player_dir(player_id)
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
            return True
        return False


# ---------------------------------------------------------------------------
# Project-scoped store backed by the project's players.json
# ---------------------------------------------------------------------------
#
# This is the SINGLE source of truth for players, shared with the
# `python -m bioscout --add_player` CLI (which writes the same players.json via
# utils.player_registry.PlayerRegistry), so players added in the CLI appear in
# the GUI dropdown and vice-versa. It exposes the same public API the Video
# Analysis tab uses (index / load / save / create / delete).
#
# Field mapping (PlayerProfile  <->  players.json record):
#   native columns : name, group, sex, age, height_m, mass_kg, notes
#   everything else (template_model, opensim_model, ceinms_model, px_per_m,
#   segment_fractions, mocap_sessions, detect_settings, schema_version) is
#   stored under the record's "extra" dict so nothing is lost on round-trip,
#   while registry-only columns (dominant_leg, affected_side, injury_type,
#   surgery_date, static_trial, generic_model, added) are preserved untouched.
# ---------------------------------------------------------------------------

# PlayerProfile fields persisted inside the players.json "extra" blob.
_EXTRA_KEYS = (
    "template_model", "opensim_model", "ceinms_model", "px_per_m",
    "segment_fractions", "mocap_sessions", "detect_settings", "schema_version",
)


class ProjectPlayerStore:
    """`PlayerStore`-compatible facade over a project's players.json."""

    def __init__(self, project_root: Optional[Path] = None):
        from utils.player_registry import PlayerRegistry
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self._registry = PlayerRegistry(self.project_root)

    # ---- mapping helpers -------------------------------------------------
    @staticmethod
    def _record_to_profile(pid: str, rec: dict) -> PlayerProfile:
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
        return PlayerProfile.from_dict(data)

    @staticmethod
    def _profile_to_fields(prof: PlayerProfile, existing_extra: dict) -> dict:
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
        for pid, rec in sorted(self._registry.all_players().items()):
            name = (rec.get("name") or "").strip() or pid
            label, n = name, 2
            while label in result:
                label = f"{name} ({n})"
                n += 1
            result[label] = pid
        return result

    @property
    def _profiles(self) -> Dict[str, PlayerProfile]:
        """{id: PlayerProfile} — kept for callers that introspect the store."""
        return {pid: self._record_to_profile(pid, rec)
                for pid, rec in self._registry.all_players().items()}

    # ---- CRUD ------------------------------------------------------------
    def load(self, player_id: str) -> Optional[PlayerProfile]:
        try:
            rec = self._registry.get(player_id)
        except KeyError:
            return None
        return self._record_to_profile(player_id, rec)

    def save(self, profile: PlayerProfile) -> Path:
        if not profile.id:
            profile.id = _slugify(profile.name or "player")
        existing_extra = {}
        if profile.id in self._registry:
            existing_extra = (self._registry.get(profile.id).get("extra") or {})
        fields = self._profile_to_fields(profile, existing_extra)
        if profile.id in self._registry:
            self._registry.update(profile.id, fields)
        else:
            self._registry.add(profile.id, fields)
        return self._registry.path

    def create(self, name: str, **kwargs) -> PlayerProfile:
        pid = _slugify(name)
        base, n = pid, 2
        while pid in self._registry:
            pid = f"{base}_{n}"
            n += 1
        prof = PlayerProfile(id=pid, name=name, **kwargs)
        self.save(prof)
        return prof

    def delete(self, player_id: str) -> bool:
        if player_id in self._registry:
            self._registry.remove(player_id)
            return True
        return False

    def models_dir(self, player_id: str) -> Path:
        d = self.project_root / "Models" / player_id
        d.mkdir(parents=True, exist_ok=True)
        return d
lf._registry:
            self._registry.remove(player_id)
            return True
        return False

    def models_dir(self, player_id: str) -> Path:
        d = self.project_root / "Models" / player_id
        d.mkdir(parents=True, exist_ok=True)
        return d
