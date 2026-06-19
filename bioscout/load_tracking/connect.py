"""
Cloud-credentials loading + helpers for pulling sessions into a LoadTracker.

Credentials live in a small JSON file (default
``~/.bioscout/load_credentials.json``) so secrets stay out of the codebase and
the command line:

    {
      "zepp":   { "token": "DQVBQE…WHtrY", "region": "de2" },
      "strava": { "client_id": "12345",
                  "client_secret": "abc…",
                  "refresh_token": "def…" }
    }

Either block is optional — include only the source(s) you use.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional


def default_credentials_path() -> Path:
    return Path(os.path.expanduser("~")) / ".bioscout" / "load_credentials.json"


def load_credentials(path: Optional[str] = None) -> dict:
    """Load the credentials JSON. Returns {} if the file is missing."""
    p = Path(path) if path else default_credentials_path()
    if not p.is_file():
        return {}
    with open(p, "r", encoding="utf-8") as fh:
        return json.load(fh)


def pull_into_tracker(tracker, creds: dict, *, zepp: bool = True,
                      strava: bool = True, limit: Optional[int] = None) -> dict:
    """Pull from whichever sources are present in *creds*. Returns counts/errors."""
    result = {"zepp": 0, "strava": 0, "errors": []}
    if zepp and creds.get("zepp", {}).get("token"):
        z = creds["zepp"]
        try:
            result["zepp"] = tracker.add_zepp(
                z["token"], region=z.get("region", "de2"), limit=limit)
        except Exception as e:  # noqa: BLE001
            result["errors"].append(f"Zepp: {e}")
    if strava and all(creds.get("strava", {}).get(k)
                      for k in ("client_id", "client_secret", "refresh_token")):
        s = creds["strava"]
        try:
            result["strava"] = tracker.add_strava(
                s["client_id"], s["client_secret"], s["refresh_token"], limit=limit)
        except Exception as e:  # noqa: BLE001
            result["errors"].append(f"Strava: {e}")
    return result
