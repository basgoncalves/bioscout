"""
Per-player tracking store.

Bridges the load_tracking engine and the project's ``players.json`` (managed by
``utils.player_registry.PlayerRegistry``). Responsibilities:

    * Build an :class:`AthleteProfile` from a player's registry record.
    * Import sessions (files / Zepp / Strava) for a player, compute load metrics,
      store lightweight **summaries** in players.json and cache the raw per-sample
      traces on disk under ``<project>/Models/<player_id>/tracking/<id>.json``.
    * Reload cached sessions as :class:`SessionData` for the dashboard.
    * Export a player's sessions to CSV.

players.json stays small (summaries only); the bulky HR/GPS arrays live in the
per-player cache files.
"""

from __future__ import annotations

import json
import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

from .importers import SessionData, AthleteProfile
from . import metrics

_ARRAY_FIELDS = ("time_s", "hr", "speed_ms", "cadence", "power_w", "altitude_m")
_SCALAR_FIELDS = ("activity", "raw_sport", "source_file", "duration_s", "distance_m",
                  "avg_hr", "max_hr", "elevation_gain_m", "calories", "rpe", "notes")


# --------------------------------------------------------------------------- #
#  SessionData (de)serialisation
# --------------------------------------------------------------------------- #
def serialize_session(s: SessionData) -> dict:
    d = {"start_time": s.start_time.isoformat()}
    for f in _SCALAR_FIELDS:
        d[f] = getattr(s, f)
    for f in _ARRAY_FIELDS:
        arr = getattr(s, f)
        d[f] = arr.tolist() if getattr(arr, "size", 0) else []
    return d


def deserialize_session(d: dict) -> SessionData:
    try:
        start = datetime.fromisoformat(d["start_time"])
    except Exception:
        start = datetime.now(timezone.utc)
    s = SessionData(start_time=start)
    for f in _SCALAR_FIELDS:
        if f in d:
            setattr(s, f, d[f])
    for f in _ARRAY_FIELDS:
        setattr(s, f, np.array(d.get(f, []), float))
    return s


def session_id(s: SessionData) -> str:
    """Stable id for caching/dedup: source basename or activity+epoch."""
    if s.source_file:
        base = s.source_file.replace(":", "_").replace("/", "_").replace("\\", "_")
        return base
    return f"{s.activity}_{int(s.start_time.timestamp())}"


# --------------------------------------------------------------------------- #
#  Store
# --------------------------------------------------------------------------- #
class TrackingStore:
    def __init__(self, registry, project_root):
        self.reg = registry
        self.root = Path(project_root)

    # ----- paths ----------------------------------------------------------- #
    def tracking_dir(self, player_id: str) -> Path:
        d = self.root / "Models" / player_id / "tracking"
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ----- athlete --------------------------------------------------------- #
    def athlete_for(self, player_id: str) -> AthleteProfile:
        rec = self.reg.get(player_id)
        tr = rec.get("tracking", {}) or {}
        hr = tr.get("hr", {}) if isinstance(tr.get("hr"), dict) else {}
        return AthleteProfile(
            name=rec.get("name") or player_id,
            age=rec.get("age"),
            sex=(rec.get("sex") or "M")[:1].upper() or "M",
            hr_max=hr.get("max"),
            hr_rest=hr.get("rest"),
            body_mass_kg=rec.get("mass_kg"),
        )

    # ----- raw cache ------------------------------------------------------- #
    def save_raw(self, player_id: str, s: SessionData) -> str:
        sid = session_id(s)
        path = self.tracking_dir(player_id) / f"{sid}.json"
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(serialize_session(s), fh)
        return sid

    def load_raw(self, player_id: str, sid: str) -> Optional[SessionData]:
        path = self.tracking_dir(player_id) / f"{sid}.json"
        if not path.is_file():
            return None
        with open(path, "r", encoding="utf-8") as fh:
            return deserialize_session(json.load(fh))

    def load_all_sessions(self, player_id: str) -> list[SessionData]:
        """Reconstruct all cached SessionData for a player (sorted by time)."""
        out = []
        for summ in self.reg.get_sessions(player_id):
            sid = summ.get("id")
            if not sid:
                continue
            s = self.load_raw(player_id, sid)
            if s is not None:
                out.append(s)
        out.sort(key=lambda s: s.start_time)
        return out

    # ----- summaries ------------------------------------------------------- #
    def _summary(self, s: SessionData, athlete: AthleteProfile, sid: str) -> dict:
        sl = metrics.session_load(s, athlete)
        return {
            "id": sid,
            "date": str(s.date),
            "activity": s.activity,
            "raw_sport": s.raw_sport,
            "source": s.source_file,
            "duration_min": round(s.duration_min, 1),
            "distance_m": s.distance_m,
            "avg_hr": s.avg_hr,
            "max_hr": s.max_hr,
            "load": round(sl["load"], 1),
            "trimp": round(sl["banister_trimp"], 1) if sl["banister_trimp"] else None,
            "basis": sl["basis"],
        }

    # ----- import ---------------------------------------------------------- #
    def import_sessions(self, player_id: str, sessions: list) -> int:
        """Cache raw traces + merge session summaries into players.json.

        De-duplicates by session id (re-importing the same workout updates it).
        Returns the number of new/updated sessions.
        """
        athlete = self.athlete_for(player_id)
        existing = {s["id"]: s for s in self.reg.get_sessions(player_id)}
        n = 0
        for s in sessions:
            sid = self.save_raw(player_id, s)
            existing[sid] = self._summary(s, athlete, sid)
            n += 1
        merged = sorted(existing.values(), key=lambda d: d.get("date", ""))
        self.reg.set_sessions(player_id, merged)
        return n

    def import_files(self, player_id: str, paths) -> int:
        from .importers import load_sessions
        return self.import_sessions(player_id, load_sessions(paths))

    def import_zepp(self, player_id: str, token: str, region: str = "de2",
                    limit: Optional[int] = None) -> int:
        from .zepp_cloud import pull_zepp
        return self.import_sessions(player_id, pull_zepp(token, region=region, limit=limit))

    def import_strava(self, player_id: str, client_id, client_secret,
                      refresh_token, limit: Optional[int] = None) -> int:
        from .strava_api import pull_strava
        return self.import_sessions(
            player_id, pull_strava(client_id, client_secret, refresh_token, limit=limit))

    # ----- export ---------------------------------------------------------- #
    def export_csv(self, player_id: str, path) -> str:
        rows = self.reg.get_sessions(player_id)
        cols = ["id", "date", "activity", "raw_sport", "source", "duration_min",
                "distance_m", "avg_hr", "max_hr", "load", "trimp", "basis"]
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow(r)
        return str(path)
