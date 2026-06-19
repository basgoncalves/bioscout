# BioScout — Load Tracking

Import training sessions from a fitness tracker (Amazfit / Zepp, Garmin, Strava,
Wahoo …), estimate musculoskeletal **load** and **fatigue**, and export a PDF report.

This is the **hybrid** design from the project goals: validated heuristic
sports-science metrics ship today, behind a pluggable estimator interface so the
real ML / OpenSim / CEINMS muscle-force pipeline can replace the muscle layer later
without touching the report or GUI.

## Getting your data out of an Amazfit GTR 3 Pro (Zepp)

In the Zepp app: open a workout → tap the **⋯** menu → **export** as **GPX**, **TCX**, or **FIT**.
GPS workouts export directly. For gym sessions without GPS, log them in a small
**manifest CSV** instead (see below).

Supported inputs: `.fit` (needs `pip install fitparse`), `.tcx`, `.gpx`, `.csv`.

## Use it

CLI:

```bash
python -m bioscout --load-report C:/path/to/zepp_exports/ \
    --age 30 --hr-max 190 --hr-rest 55 --sex M --load-out my_report.pdf
```

GUI: launch BioScout → **Load Tracking** tab → add files/folder → set HR profile → Build report.

Python:

```python
from bioscout.load_tracking import LoadTracker, AthleteProfile

tr = LoadTracker(athlete=AthleteProfile(name="Bas", age=30, hr_max=190, hr_rest=55))
tr.add_files("zepp_exports/")     # folder, glob, or list of files
tr.compute()
print(tr.summary_text())
tr.report("load_report.pdf")
```

A worked example lives in `example_data/load_tracking/` (synthetic 4-week block +
`example_load_report.pdf`). Regenerate with `python -m bioscout.load_tracking.sample_data out_dir/`.

## Pulling automatically from the cloud (no manual export)

The GTR 3 Pro's USB is **charge-only** — it has no data link, so nothing can read
the watch over a cable. "Automatic" therefore means pulling from your account in
the cloud. Two routes are supported; put secrets in a credentials JSON
(default `~/.bioscout/load_credentials.json`):

```json
{
  "zepp":   { "token": "DQVBQE…WHtrY", "region": "de2" },
  "strava": { "client_id": "12345", "client_secret": "abc…", "refresh_token": "def…" }
}
```

Then:

```bash
python -m bioscout --zepp-pull   --age 30 --hr-max 190 --hr-rest 55 --load-out report.pdf
python -m bioscout --strava-pull --age 30 --hr-max 190 --hr-rest 55 --load-out report.pdf
# (both flags together merge sources; --creds points at a non-default file)
```

In the GUI: **Load Tracking** tab → *Cloud credentials…* → pick the JSON → Build report.

### Zepp / Huami (works even with Google/Apple/Xiaomi SSO)

There's no email/password with SSO, so capture the API token **once**:

- Rooted Android: read `apptoken` from
  `/data/data/com.huami.watch.hmwatchmanager/shared_prefs/hm_id_sdk_android.xml`.
- Not rooted: run HTTP Toolkit / Fiddler / mitmproxy, open the Zepp app, and copy
  the `apptoken` header from any request to `api-mifit-*.huami.com`.

Paste it as `zepp.token`. `region` is the server suffix in that host (`de2` = EU,
`us2` = US, etc.). This is an unofficial API and can change without notice.

### Strava (most robust, official API)

Set Zepp → Profile → add **Strava** so workouts auto-sync. Then create a Strava API
app at https://www.strava.com/settings/api (Client ID + Secret) and do the OAuth
flow once with scope `activity:read_all` to get a `refresh_token`. BioScout refreshes
the short-lived access token itself on every run. Once set up, Amazfit workouts flow
Zepp → Strava → BioScout with zero manual steps.

## Strength-session manifest CSV

For gym work, one row per session. `notes` tags (`leg`, `push`, `pull`, `squat`,
`deadlift`, `upper`, `core`) refine the per-muscle split.

```csv
date,sport,duration_min,rpe,notes
2026-06-01,strength,55,8,leg day - squat focus
2026-06-03,strength,45,7,push day - bench + shoulders
```

## What it computes

- **Internal load** per session — Banister TRIMP (HR-reserve weighted) when an HR
  trace is present; Edwards zone TRIMP or session-RPE (`RPE × min`) as fallback.
- **ACWR** — acute:chronic workload ratio (EWMA, Williams 2017). Bands: optimal
  0.8–1.3, caution 1.3–1.5, high-risk >1.5.
- **Monotony / strain** (Foster) and a **Banister fitness–fatigue** model.
- **Per-muscle-group load & fatigue** — each session's load is distributed across
  12 muscle groups by activity type (`muscle_map.py`), then a 0–100 athlete-relative
  fatigue index + recovery notes are produced (`fatigue.py`).

The PDF has 3 pages: overview (KPIs, daily-load timeline, ACWR bands),
fitness/fatigue curves + per-muscle ranking, and a weekly per-muscle heatmap +
session log + recovery notes.

## Extending to real muscle forces

`ml_interface.py` defines `MuscleForceEstimator`. The default
`HeuristicMuscleEstimator` distributes load by activity. To plug in the real
pipeline, subclass it (see the `OpenSimMuscleEstimator` stub) and pass it in:

```python
tr = LoadTracker(athlete, estimator=MyOpenSimEstimator(...))
```

## Notes / limitations

A wrist tracker has no muscle sensors — these are **interpretable estimates of
training load**, not measured muscle forces. Per-muscle distribution weights are an
evidence-informed first approximation; tune `muscle_map._DISTRIBUTION` to your
athletes. The ACWR warm-up period (~first 28 days) is unreliable until a chronic
baseline accumulates.
