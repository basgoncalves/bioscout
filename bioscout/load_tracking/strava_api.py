"""
Strava importer.

The robust, official path: set Zepp to auto-sync workouts to Strava
(Zepp app → Profile → Add account → Strava), then pull everything through
Strava's stable API. Once configured, new Amazfit workouts flow Zepp → Strava
→ BioScout with no manual export.

One-time setup
--------------
1. Create a Strava API application: https://www.strava.com/settings/api
   → note the ``Client ID`` and ``Client Secret``.
2. Do the OAuth dance once to get a **refresh token** with ``activity:read_all``
   scope (any helper works; e.g. open in a browser:
   ``https://www.strava.com/oauth/authorize?client_id=ID&response_type=code&
   redirect_uri=http://localhost&approval_prompt=force&scope=activity:read_all``
   then exchange the ``code`` at ``https://www.strava.com/oauth/token``).
3. Put client_id / client_secret / refresh_token in your credentials file
   (see ``connect`` / README). BioScout refreshes the short-lived access token
   automatically on each run.

API:  GET /api/v3/athlete/activities  and  /api/v3/activities/{id}/streams
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import numpy as np

from .importers import SessionData, normalize_activity

_TOKEN_URL = "https://www.strava.com/oauth/token"
_API = "https://www.strava.com/api/v3"
_STREAM_KEYS = ["time", "heartrate", "velocity_smooth", "cadence", "altitude"]


def _parse_iso(s: str) -> datetime:
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        dt = datetime.now(timezone.utc)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
#  Pure parser (unit-tested without network)
# --------------------------------------------------------------------------- #
def strava_activity_to_session(act: dict,
                               streams: Optional[dict] = None) -> SessionData:
    """Convert a Strava activity (+ optional streams dict) to SessionData.

    ``streams`` is the key_by_type response: ``{"heartrate": {"data": [...]}, ...}``.
    """
    sport = act.get("sport_type") or act.get("type") or ""
    start = _parse_iso(act.get("start_date") or act.get("start_date_local"))
    sess = SessionData(
        start_time=start,
        activity=normalize_activity(sport),
        raw_sport=str(sport),
        source_file=f"strava:{act.get('id', '')}",
        notes=act.get("name", "") or "",
    )
    sess.duration_s = act.get("elapsed_time") or act.get("moving_time")
    sess.distance_m = act.get("distance")
    if act.get("average_heartrate"):
        sess.avg_hr = float(act["average_heartrate"])
    if act.get("max_heartrate"):
        sess.max_hr = float(act["max_heartrate"])
    if act.get("total_elevation_gain") is not None:
        sess.elevation_gain_m = float(act["total_elevation_gain"])
    if act.get("calories"):
        sess.calories = float(act["calories"])

    if streams:
        def arr(key):
            d = streams.get(key)
            return np.array(d["data"], float) if d and d.get("data") else np.array([])
        sess.time_s = arr("time")
        sess.hr = arr("heartrate")
        sess.speed_ms = arr("velocity_smooth")
        sess.cadence = arr("cadence")
        sess.altitude_m = arr("altitude")
    return sess.finalize()


# --------------------------------------------------------------------------- #
#  HTTP client
# --------------------------------------------------------------------------- #
class StravaClient:
    def __init__(self, client_id, client_secret, refresh_token,
                 access_token: Optional[str] = None, timeout: float = 30.0):
        if not (client_id and client_secret and refresh_token):
            raise ValueError("client_id, client_secret and refresh_token are required.")
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.access_token = access_token
        self.timeout = timeout

    def _requests(self):
        try:
            import requests
            return requests
        except ImportError as e:  # pragma: no cover
            raise ImportError("Strava import needs 'requests' (pip install requests).") from e

    def refresh(self) -> str:
        requests = self._requests()
        r = requests.post(_TOKEN_URL, data={
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }, timeout=self.timeout)
        r.raise_for_status()
        tok = r.json()
        self.access_token = tok["access_token"]
        # Strava rotates refresh tokens — keep the latest.
        self.refresh_token = tok.get("refresh_token", self.refresh_token)
        return self.access_token

    def _headers(self):
        if not self.access_token:
            self.refresh()
        return {"Authorization": f"Bearer {self.access_token}"}

    def get_activities(self, after: Optional[int] = None,
                       per_page: int = 100, max_pages: int = 10) -> list[dict]:
        requests = self._requests()
        out, page = [], 1
        while page <= max_pages:
            params = {"per_page": per_page, "page": page}
            if after:
                params["after"] = after
            r = requests.get(f"{_API}/athlete/activities", headers=self._headers(),
                             params=params, timeout=self.timeout)
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            out.extend(batch)
            page += 1
        return out

    def get_streams(self, activity_id) -> dict:
        requests = self._requests()
        r = requests.get(f"{_API}/activities/{activity_id}/streams",
                         headers=self._headers(),
                         params={"keys": ",".join(_STREAM_KEYS),
                                 "key_by_type": "true"}, timeout=self.timeout)
        if r.status_code != 200:
            return {}
        return r.json()

    def pull(self, after: Optional[int] = None, limit: Optional[int] = None,
             with_streams: bool = True) -> list[SessionData]:
        acts = self.get_activities(after=after)
        acts.sort(key=lambda a: a.get("start_date", ""))
        if limit:
            acts = acts[-limit:]
        sessions = []
        for a in acts:
            streams = None
            if with_streams:
                try:
                    streams = self.get_streams(a["id"])
                except Exception as e:  # noqa: BLE001
                    print(f"[strava] streams failed for {a.get('id')}: {e}")
            sessions.append(strava_activity_to_session(a, streams))
        return sessions


def pull_strava(client_id, client_secret, refresh_token,
                after: Optional[int] = None, limit: Optional[int] = None,
                with_streams: bool = True) -> list[SessionData]:
    """Convenience: build a client and pull sessions in one call."""
    return StravaClient(client_id, client_secret, refresh_token).pull(
        after=after, limit=limit, with_streams=with_streams)
