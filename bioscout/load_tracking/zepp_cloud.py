"""
Zepp / Huami cloud importer.

Pulls workouts straight from your Zepp (Amazfit) cloud account — no manual
per-workout export. Because the GTR 3 Pro has no USB data link, "automatic" means
reading the cloud, not the device.

Auth note (important for SSO logins)
------------------------------------
The Huami API authenticates with an ``apptoken`` header. If you sign in to Zepp
with Google / Apple / Xiaomi (SSO), there is no email/password the API can use, so
you must capture the token **once**:

    * Rooted Android: read
      ``/data/data/com.huami.watch.hmwatchmanager/shared_prefs/hm_id_sdk_android.xml``
    * Not rooted: run HTTP Toolkit / Fiddler / mitmproxy, open the Zepp app, and
      copy the ``apptoken`` header from any request to ``api-mifit-*.huami.com``.

The token is long-lived; paste it into your credentials file (see ``connect`` /
README). Region is the server suffix in that host, e.g. ``de2`` (EU), ``us2`` (US).

API shape (reverse-engineered; credit: rolandsz/Mi-Fit-and-Zepp-workout-exporter):
    GET https://api-mifit-{region}.huami.com/v1/sport/run/history.json
        header apptoken, param source=run.mifit.huami.com  → data.summary[ {...} ]
    GET https://api-mifit-{region}.huami.com/v1/sport/run/detail.json
        header apptoken, params trackid, source            → data{ time, heart_rate, ... }

This is an unofficial API and may change without notice.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import numpy as np

from .importers import SessionData, normalize_activity

DEFAULT_SOURCE = "run.mifit.huami.com"

# Huami sport-mode integer → canonical activity. Values vary by firmware; unknown
# types fall back to "generic". Tune as you confirm your own watch's codes.
HUAMI_SPORT_TYPES = {
    1: "running",     # outdoor running
    8: "running",     # treadmill
    6: "walking",
    9: "cycling",     # outdoor cycling
    10: "cycling",    # indoor cycling
    12: "elliptical",
    14: "swimming",   # pool
    15: "swimming",   # open water
    16: "strength",   # free / strength training
    21: "hiking",
    60: "strength",   # functional / HIIT (approx)
}


def _huami_activity(sport_type) -> tuple[str, str]:
    """Return (canonical_activity, raw_label)."""
    try:
        t = int(sport_type)
    except (TypeError, ValueError):
        return normalize_activity(str(sport_type)), str(sport_type)
    return HUAMI_SPORT_TYPES.get(t, "generic"), f"huami_type_{t}"


def _f(x, default=None):
    try:
        v = float(x)
        return v
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------------- #
#  Pure decoders / parsers (unit-tested without network)
# --------------------------------------------------------------------------- #
def decode_heart_rate(hr_str: Optional[str]) -> tuple[np.ndarray, np.ndarray]:
    """Decode Huami ``heart_rate`` string ("t,v;t,v;…", delta-encoded).

    Each ``t,v`` pair is (time-delta seconds, HR-delta bpm); both accumulate.
    Returns (time_s, hr_bpm) arrays. Empty arrays if unparseable.
    """
    if not hr_str:
        return np.array([]), np.array([])
    t = 0.0
    v = 0.0
    ts, hrs = [], []
    for pair in hr_str.split(";"):
        if not pair:
            continue
        try:
            a, b = pair.split(",")
            t += float(a)
            v += float(b)
        except ValueError:
            continue
        ts.append(t)
        hrs.append(v)
    return np.array(ts, float), np.array(hrs, float)


def huami_summary_to_session(summary: dict) -> SessionData:
    """Build a SessionData from one Huami history summary dict (no detail trace)."""
    trackid = summary.get("trackid") or summary.get("track_id") or "0"
    try:
        start = datetime.fromtimestamp(int(trackid), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        start = datetime.now(timezone.utc)

    activity, raw = _huami_activity(summary.get("type", summary.get("sport_mode")))
    sess = SessionData(start_time=start, activity=activity, raw_sport=raw,
                       source_file=f"zepp:{trackid}")

    rt = _f(summary.get("run_time"))
    sess.duration_s = rt if rt else None
    avg = _f(summary.get("avg_heart_rate"))
    sess.avg_hr = avg if avg and avg > 0 else None
    mx = _f(summary.get("max_heart_rate"))
    sess.max_hr = mx if mx and mx > 0 else None
    dis = _f(summary.get("dis"))
    sess.distance_m = dis if dis else None
    cal = _f(summary.get("calorie"))
    sess.calories = cal if cal else None
    return sess


def enrich_session_with_detail(session: SessionData, detail: dict) -> SessionData:
    """Attach the HR time series from a Huami detail dict, if present."""
    data = detail.get("data", detail)
    ts, hr = decode_heart_rate(data.get("heart_rate"))
    if ts.size:
        session.time_s = ts
        session.hr = hr
        session.finalize()   # recompute avg/max/duration from the trace
    return session


# --------------------------------------------------------------------------- #
#  HTTP client
# --------------------------------------------------------------------------- #
class ZeppCloudClient:
    """Minimal client for the Huami workout API using a captured apptoken."""

    def __init__(self, token: str, region: str = "de2",
                 source: str = DEFAULT_SOURCE, timeout: float = 30.0):
        if not token:
            raise ValueError("A Huami 'apptoken' is required (see module docstring).")
        self.token = token
        self.region = region
        self.source = source
        self.timeout = timeout
        self.base = f"https://api-mifit-{region}.huami.com/v1/sport/run"

    def _requests(self):
        try:
            import requests
            return requests
        except ImportError as e:  # pragma: no cover
            raise ImportError("Zepp cloud import needs 'requests' (pip install requests).") from e

    def get_history(self) -> list[dict]:
        requests = self._requests()
        r = requests.get(f"{self.base}/history.json",
                         headers={"apptoken": self.token},
                         params={"source": self.source}, timeout=self.timeout)
        r.raise_for_status()
        payload = r.json()
        if payload.get("code") != 1:
            raise RuntimeError(f"Zepp history error: {payload.get('message')!r} "
                               "(token may be expired or region wrong).")
        return payload.get("data", {}).get("summary", []) or []

    def get_detail(self, trackid, source: Optional[str] = None) -> dict:
        requests = self._requests()
        r = requests.get(f"{self.base}/detail.json",
                         headers={"apptoken": self.token},
                         params={"trackid": trackid, "source": source or self.source},
                         timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def pull(self, limit: Optional[int] = None, enrich: bool = True) -> list[SessionData]:
        """Pull workouts → SessionData. ``enrich`` adds the HR trace per workout."""
        summaries = self.get_history()
        summaries.sort(key=lambda s: int(s.get("trackid", 0)))
        if limit:
            summaries = summaries[-limit:]
        sessions = []
        for s in summaries:
            sess = huami_summary_to_session(s)
            if enrich:
                try:
                    detail = self.get_detail(s.get("trackid"),
                                             s.get("source", self.source))
                    enrich_session_with_detail(sess, detail)
                except Exception as e:  # noqa: BLE001 — keep batch alive
                    print(f"[zepp] detail fetch failed for {s.get('trackid')}: {e}")
            sessions.append(sess)
        return sessions


def pull_zepp(token: str, region: str = "de2", source: str = DEFAULT_SOURCE,
              limit: Optional[int] = None, enrich: bool = True) -> list[SessionData]:
    """Convenience: build a client and pull sessions in one call."""
    return ZeppCloudClient(token, region=region, source=source).pull(limit=limit,
                                                                      enrich=enrich)
