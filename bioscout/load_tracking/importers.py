"""
Session importers for the load-tracking module.

Parses fitness-tracker exports into a unified :class:`SessionData` object.

Supported formats
-----------------
    * ``.fit``  — Garmin/ANT FIT (Amazfit/Zepp export, Garmin, Wahoo …). Needs the
                  optional ``fitparse`` package; install with ``pip install fitparse``.
    * ``.tcx``  — Training Center XML (Zepp export, Garmin Connect, Strava …).
    * ``.gpx``  — GPS Exchange (Zepp export, most apps). HR/cadence via the
                  Garmin TrackPointExtension namespace when present.
    * ``.csv``  — Two flavours auto-detected:
                    1. Per-sample CSV with a timestamp + heart-rate column.
                    2. A "manifest" CSV: one row per session (date, sport,
                       duration_min, avg_hr, rpe, …) — useful for gym sessions and
                       for Zepp's GDPR data export.

Amazfit GTR 3 Pro: in the Zepp app open a workout → ⋯ menu → export as
GPX / TCX / FIT. Non-GPS sessions (e.g. strength) can be entered via a manifest CSV.
"""

from __future__ import annotations

import csv
import os
import glob
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

SUPPORTED_EXTENSIONS = (".fit", ".tcx", ".gpx", ".csv")


# --------------------------------------------------------------------------- #
#  Canonical activity types
# --------------------------------------------------------------------------- #
# Everything funnels into one of these so the muscle map has a stable key set.
ACTIVITY_TYPES = (
    "running",
    "walking",
    "cycling",
    "strength",
    "rowing",
    "swimming",
    "elliptical",
    "hiking",
    "generic",
)

# Map raw sport labels (FIT sport enum names, Zepp/Strava/TCX sport strings,
# free-text) onto a canonical activity type. Matching is case-insensitive and
# substring-based, longest key first.
_ACTIVITY_ALIASES = {
    "trail_run": "running",
    "trail run": "running",
    "treadmill": "running",
    "running": "running",
    "run": "running",
    "jog": "running",
    "walk": "walking",
    "walking": "walking",
    "nordic": "walking",
    "hike": "hiking",
    "hiking": "hiking",
    "mountaineer": "hiking",
    "road_biking": "cycling",
    "mountain_biking": "cycling",
    "indoor_cycling": "cycling",
    "virtual_ride": "cycling",
    "ebike_ride": "cycling",
    "gravel_ride": "cycling",
    "spinning": "cycling",
    "cycling": "cycling",
    "cycle": "cycling",
    "biking": "cycling",
    "bike": "cycling",
    "ride": "cycling",
    "strength_training": "strength",
    "strength": "strength",
    "weight": "strength",
    "gym": "strength",
    "resistance": "strength",
    "crossfit": "strength",
    "functional": "strength",
    "rowing": "rowing",
    "row": "rowing",
    "kayak": "rowing",
    "paddle": "rowing",
    "open_water": "swimming",
    "lap_swimming": "swimming",
    "swimming": "swimming",
    "swim": "swimming",
    "elliptical": "elliptical",
    "cross_trainer": "elliptical",
}


def normalize_activity(raw: Optional[str]) -> str:
    """Map an arbitrary sport label to a canonical activity type."""
    if not raw:
        return "generic"
    s = str(raw).strip().lower().replace("-", "_")
    if s in _ACTIVITY_ALIASES:
        return _ACTIVITY_ALIASES[s]
    for key in sorted(_ACTIVITY_ALIASES, key=len, reverse=True):
        if key.replace("_", " ") in s.replace("_", " "):
            return _ACTIVITY_ALIASES[key]
    return "generic"


# --------------------------------------------------------------------------- #
#  Athlete profile
# --------------------------------------------------------------------------- #
@dataclass
class AthleteProfile:
    """Per-athlete parameters needed for HR-based load metrics."""

    name: str = "Athlete"
    age: Optional[int] = None
    sex: str = "M"                      # "M" or "F" — affects Banister TRIMP constant
    hr_rest: Optional[float] = None     # resting HR (bpm)
    hr_max: Optional[float] = None      # max HR (bpm); falls back to 220 - age
    body_mass_kg: Optional[float] = None

    def resolved_hr_max(self) -> float:
        if self.hr_max:
            return float(self.hr_max)
        if self.age:
            return 220.0 - float(self.age)
        return 190.0  # generic adult fallback

    def resolved_hr_rest(self) -> float:
        return float(self.hr_rest) if self.hr_rest else 60.0


# --------------------------------------------------------------------------- #
#  Unified session model
# --------------------------------------------------------------------------- #
@dataclass
class SessionData:
    """One training session, normalised across source formats."""

    start_time: datetime
    activity: str = "generic"           # canonical activity type
    raw_sport: str = ""                 # original sport label from the file
    source_file: str = ""

    # Time series (numpy arrays, sample-aligned where present)
    time_s: np.ndarray = field(default_factory=lambda: np.array([]))
    hr: np.ndarray = field(default_factory=lambda: np.array([]))          # bpm
    speed_ms: np.ndarray = field(default_factory=lambda: np.array([]))    # m/s
    cadence: np.ndarray = field(default_factory=lambda: np.array([]))     # rpm/spm
    power_w: np.ndarray = field(default_factory=lambda: np.array([]))     # watts
    altitude_m: np.ndarray = field(default_factory=lambda: np.array([]))

    # Session-level scalars (filled by the parser if available, else derived)
    duration_s: Optional[float] = None
    distance_m: Optional[float] = None
    avg_hr: Optional[float] = None
    max_hr: Optional[float] = None
    elevation_gain_m: Optional[float] = None
    calories: Optional[float] = None
    rpe: Optional[float] = None         # session RPE 0-10 (manual; optional)
    notes: str = ""

    # ----- derived helpers -------------------------------------------------- #
    @property
    def date(self):
        return self.start_time.date()

    @property
    def duration_min(self) -> float:
        if self.duration_s:
            return self.duration_s / 60.0
        if self.time_s.size >= 2:
            return float(self.time_s[-1] - self.time_s[0]) / 60.0
        return 0.0

    def finalize(self) -> "SessionData":
        """Fill missing session scalars from the time series."""
        if self.hr.size:
            valid = self.hr[self.hr > 0]
            if valid.size:
                if self.avg_hr is None:
                    self.avg_hr = float(np.mean(valid))
                if self.max_hr is None:
                    self.max_hr = float(np.max(valid))
        if self.duration_s is None and self.time_s.size >= 2:
            self.duration_s = float(self.time_s[-1] - self.time_s[0])
        if self.distance_m is None and self.speed_ms.size and self.time_s.size:
            dt = np.diff(self.time_s)
            v = self.speed_ms[1:]
            self.distance_m = float(np.nansum(dt * v))
        if self.elevation_gain_m is None and self.altitude_m.size > 1:
            d = np.diff(self.altitude_m)
            self.elevation_gain_m = float(np.nansum(d[d > 0]))
        return self


# --------------------------------------------------------------------------- #
#  XML namespace helpers
# --------------------------------------------------------------------------- #
def _localname(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _parse_dt(text: str) -> datetime:
    text = text.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        # common TCX/GPX fallbacks
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                    "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        else:
            dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# --------------------------------------------------------------------------- #
#  TCX
# --------------------------------------------------------------------------- #
def _parse_tcx(path: str) -> list[SessionData]:
    tree = ET.parse(path)
    root = tree.getroot()
    sessions: list[SessionData] = []

    activities = [e for e in root.iter() if _localname(e.tag) == "Activity"]
    for act in activities:
        sport = act.get("Sport", "")
        times, hrs, speeds, cads, alts, dists = [], [], [], [], [], []
        for tp in (e for e in act.iter() if _localname(e.tag) == "Trackpoint"):
            t = hr = sp = cad = alt = dist = None
            for child in tp.iter():
                ln = _localname(child.tag)
                txt = (child.text or "").strip()
                if ln == "Time" and txt:
                    t = _parse_dt(txt)
                elif ln == "HeartRateBpm":
                    val = child.find("./{*}Value")
                    if val is not None and val.text:
                        hr = float(val.text)
                elif ln == "Value" and tp.find(".//{*}HeartRateBpm") is not None and hr is None:
                    try:
                        hr = float(txt)
                    except ValueError:
                        pass
                elif ln == "Speed" and txt:
                    sp = float(txt)
                elif ln in ("RunCadence", "Cadence") and txt:
                    cad = float(txt)
                elif ln == "AltitudeMeters" and txt:
                    alt = float(txt)
                elif ln == "DistanceMeters" and txt:
                    dist = float(txt)
            if t is None:
                continue
            times.append(t)
            hrs.append(hr if hr is not None else np.nan)
            speeds.append(sp if sp is not None else np.nan)
            cads.append(cad if cad is not None else np.nan)
            alts.append(alt if alt is not None else np.nan)
            dists.append(dist if dist is not None else np.nan)
        if not times:
            continue
        t0 = times[0]
        sess = SessionData(
            start_time=t0,
            activity=normalize_activity(sport),
            raw_sport=sport,
            source_file=os.path.basename(path),
            time_s=np.array([(t - t0).total_seconds() for t in times], float),
            hr=np.array(hrs, float),
            speed_ms=np.array(speeds, float),
            cadence=np.array(cads, float),
            altitude_m=np.array(alts, float),
        )
        d = np.array(dists, float)
        if np.isfinite(d).any():
            sess.distance_m = float(np.nanmax(d))
        sessions.append(sess.finalize())
    return sessions


# --------------------------------------------------------------------------- #
#  GPX
# --------------------------------------------------------------------------- #
def _parse_gpx(path: str) -> list[SessionData]:
    tree = ET.parse(path)
    root = tree.getroot()

    sport = ""
    typ = root.find(".//{*}trk/{*}type")
    if typ is not None and typ.text:
        sport = typ.text

    times, hrs, cads, alts, lats, lons = [], [], [], [], [], []
    for pt in (e for e in root.iter() if _localname(e.tag) == "trkpt"):
        lat = pt.get("lat")
        lon = pt.get("lon")
        t = hr = cad = alt = None
        for child in pt.iter():
            ln = _localname(child.tag)
            txt = (child.text or "").strip()
            if ln == "time" and txt:
                t = _parse_dt(txt)
            elif ln == "ele" and txt:
                alt = float(txt)
            elif ln == "hr" and txt:
                hr = float(txt)
            elif ln == "cad" and txt:
                cad = float(txt)
        if t is None:
            continue
        times.append(t)
        hrs.append(hr if hr is not None else np.nan)
        cads.append(cad if cad is not None else np.nan)
        alts.append(alt if alt is not None else np.nan)
        lats.append(float(lat) if lat else np.nan)
        lons.append(float(lon) if lon else np.nan)
    if not times:
        return []

    t0 = times[0]
    time_s = np.array([(t - t0).total_seconds() for t in times], float)
    sess = SessionData(
        start_time=t0,
        activity=normalize_activity(sport),
        raw_sport=sport,
        source_file=os.path.basename(path),
        time_s=time_s,
        hr=np.array(hrs, float),
        cadence=np.array(cads, float),
        altitude_m=np.array(alts, float),
    )
    # speed/distance from lat/lon via haversine
    lat = np.array(lats); lon = np.array(lons)
    if np.isfinite(lat).sum() > 1:
        speed = np.full(time_s.shape, np.nan)
        R = 6371000.0
        for i in range(1, len(time_s)):
            if not (np.isfinite(lat[i]) and np.isfinite(lat[i - 1])):
                continue
            dlat = np.radians(lat[i] - lat[i - 1])
            dlon = np.radians(lon[i] - lon[i - 1])
            a = (np.sin(dlat / 2) ** 2
                 + np.cos(np.radians(lat[i - 1])) * np.cos(np.radians(lat[i]))
                 * np.sin(dlon / 2) ** 2)
            d = 2 * R * np.arcsin(np.sqrt(a))
            dt = time_s[i] - time_s[i - 1]
            if dt > 0:
                speed[i] = d / dt
        sess.speed_ms = speed
    return [sess.finalize()]


# --------------------------------------------------------------------------- #
#  FIT  (optional dependency: fitparse)
# --------------------------------------------------------------------------- #
def _parse_fit(path: str) -> list[SessionData]:
    try:
        from fitparse import FitFile
    except ImportError as e:
        raise ImportError(
            "Reading .fit files needs the 'fitparse' package. "
            "Install it with:  pip install fitparse\n"
            "Alternatively export the workout as .tcx or .gpx from the Zepp app."
        ) from e

    fit = FitFile(path)
    sport = ""
    for msg in fit.get_messages("sport"):
        v = msg.get_value("sport")
        if v:
            sport = str(v)
            break
    if not sport:
        for msg in fit.get_messages("session"):
            v = msg.get_value("sport")
            if v:
                sport = str(v)
                break

    times, hrs, speeds, cads, powers, alts = [], [], [], [], [], []
    for rec in fit.get_messages("record"):
        d = {f.name: f.value for f in rec}
        if "timestamp" not in d or d["timestamp"] is None:
            continue
        ts = d["timestamp"]
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        times.append(ts)
        hrs.append(float(d["heart_rate"]) if d.get("heart_rate") is not None else np.nan)
        speeds.append(float(d["speed"]) if d.get("speed") is not None else np.nan)
        cads.append(float(d["cadence"]) if d.get("cadence") is not None else np.nan)
        powers.append(float(d["power"]) if d.get("power") is not None else np.nan)
        alts.append(float(d["altitude"]) if d.get("altitude") is not None else np.nan)
    if not times:
        return []

    t0 = times[0]
    sess = SessionData(
        start_time=t0,
        activity=normalize_activity(sport),
        raw_sport=sport,
        source_file=os.path.basename(path),
        time_s=np.array([(t - t0).total_seconds() for t in times], float),
        hr=np.array(hrs, float),
        speed_ms=np.array(speeds, float),
        cadence=np.array(cads, float),
        power_w=np.array(powers, float),
        altitude_m=np.array(alts, float),
    )
    # session-level scalars if present
    for msg in fit.get_messages("session"):
        d = {f.name: f.value for f in msg}
        if d.get("total_timer_time"):
            sess.duration_s = float(d["total_timer_time"])
        if d.get("total_distance"):
            sess.distance_m = float(d["total_distance"])
        if d.get("total_calories"):
            sess.calories = float(d["total_calories"])
        break
    return [sess.finalize()]


# --------------------------------------------------------------------------- #
#  CSV  (per-sample OR session manifest)
# --------------------------------------------------------------------------- #
def _parse_csv(path: str) -> list[SessionData]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        return []
    cols = {c.lower().strip(): c for c in rows[0].keys()}

    def col(*names):
        for n in names:
            if n in cols:
                return cols[n]
        return None

    ts_col = col("timestamp", "time", "datetime")
    hr_col = col("heart_rate", "heartrate", "hr", "bpm")

    # ----- manifest flavour: one session per row ----- #
    dur_col = col("duration_min", "duration", "minutes")
    if dur_col and not (ts_col and hr_col and len(rows) > 5):
        sessions = []
        date_col = col("date", "start_time", "day", "timestamp")
        sport_col = col("sport", "activity", "type", "mode")
        avghr_col = col("avg_hr", "average_hr", "mean_hr", "hr")
        maxhr_col = col("max_hr", "maximum_hr")
        rpe_col = col("rpe", "perceived_exertion", "borg")
        dist_col = col("distance_m", "distance", "distance_km")
        cal_col = col("calories", "kcal")
        for r in rows:
            dstr = r.get(date_col, "") if date_col else ""
            try:
                start = _parse_dt(dstr) if "T" in dstr or ":" in dstr else \
                    datetime.strptime(dstr.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception:
                continue
            sport = r.get(sport_col, "") if sport_col else ""
            sess = SessionData(
                start_time=start,
                activity=normalize_activity(sport),
                raw_sport=sport,
                source_file=os.path.basename(path),
            )
            sess.duration_s = _f(r.get(dur_col)) * 60.0 if _f(r.get(dur_col)) else None
            sess.avg_hr = _f(r.get(avghr_col)) if avghr_col else None
            sess.max_hr = _f(r.get(maxhr_col)) if maxhr_col else None
            sess.rpe = _f(r.get(rpe_col)) if rpe_col else None
            if dist_col:
                dv = _f(r.get(dist_col))
                if dv is not None:
                    sess.distance_m = dv * 1000.0 if "km" in dist_col else dv
            sess.calories = _f(r.get(cal_col)) if cal_col else None
            sessions.append(sess)
        return sessions

    # ----- per-sample flavour ----- #
    if not (ts_col and hr_col):
        raise ValueError(
            f"Could not interpret CSV '{os.path.basename(path)}'. Expected either a "
            "per-sample file (timestamp + heart_rate columns) or a session manifest "
            "(date, sport, duration_min, avg_hr, rpe …)."
        )
    sport_col = col("sport", "activity", "type", "mode")
    sport = rows[0].get(sport_col, "") if sport_col else ""
    times, hrs = [], []
    for r in rows:
        try:
            times.append(_parse_dt(r[ts_col]))
            hrs.append(_f(r[hr_col]) or np.nan)
        except Exception:
            continue
    if not times:
        return []
    t0 = times[0]
    sess = SessionData(
        start_time=t0,
        activity=normalize_activity(sport),
        raw_sport=sport,
        source_file=os.path.basename(path),
        time_s=np.array([(t - t0).total_seconds() for t in times], float),
        hr=np.array(hrs, float),
    )
    return [sess.finalize()]


def _f(x):
    try:
        return float(str(x).strip())
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
#  Public dispatch
# --------------------------------------------------------------------------- #
_PARSERS = {
    ".tcx": _parse_tcx,
    ".gpx": _parse_gpx,
    ".fit": _parse_fit,
    ".csv": _parse_csv,
}


def load_session_file(path: str) -> list[SessionData]:
    """Parse one file into a list of :class:`SessionData` (usually length 1)."""
    ext = Path(path).suffix.lower()
    if ext not in _PARSERS:
        raise ValueError(f"Unsupported file type '{ext}'. "
                         f"Supported: {', '.join(SUPPORTED_EXTENSIONS)}")
    return _PARSERS[ext](path)


def load_sessions(paths) -> list[SessionData]:
    """Load sessions from a folder, a glob, or a list of files/folders.

    Sessions are returned sorted by start time. Files that fail to parse are
    skipped with a warning printed to stdout (so one bad file doesn't abort a batch).
    """
    if isinstance(paths, (str, os.PathLike)):
        paths = [paths]

    files: list[str] = []
    for p in paths:
        p = str(p)
        if os.path.isdir(p):
            for ext in SUPPORTED_EXTENSIONS:
                files.extend(glob.glob(os.path.join(p, f"**/*{ext}"), recursive=True))
        elif any(ch in p for ch in "*?[]"):
            files.extend(glob.glob(p, recursive=True))
        else:
            files.append(p)

    sessions: list[SessionData] = []
    for f in sorted(set(files)):
        try:
            sessions.extend(load_session_file(f))
        except Exception as e:  # noqa: BLE001 — keep batch alive
            print(f"[load_tracking] skipped '{os.path.basename(f)}': {e}")
    sessions.sort(key=lambda s: s.start_time)
    return sessions
