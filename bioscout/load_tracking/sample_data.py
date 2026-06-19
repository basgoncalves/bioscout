"""
Synthetic sample-data generator for the load-tracking module.

Generates a few weeks of realistic-looking TCX workout files (HR trace, GPS-free
is fine for load) plus a strength-session manifest CSV — useful for trying the
module without a real Zepp/Amazfit export.

    python -m bioscout.load_tracking.sample_data  out_dir/
"""

from __future__ import annotations

import os
import sys
import random
import csv
from datetime import datetime, timedelta, timezone

import numpy as np

_TCX_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<TrainingCenterDatabase '
    'xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">\n'
    '  <Activities>\n'
)
_TCX_FOOTER = '  </Activities>\n</TrainingCenterDatabase>\n'


def _write_tcx(path, start, sport, dur_min, hr_base, hr_amp):
    n = int(dur_min)  # one sample per minute is enough for load
    lines = [_TCX_HEADER, f'    <Activity Sport="{sport}">\n',
             f'      <Id>{start.isoformat()}</Id>\n', '      <Lap>\n',
             '        <Track>\n']
    for i in range(n):
        t = start + timedelta(minutes=i)
        hr = int(hr_base + hr_amp * np.sin(i / max(n, 1) * np.pi)
                 + random.gauss(0, 3))
        hr = max(70, min(195, hr))
        lines.append(
            '          <Trackpoint>\n'
            f'            <Time>{t.isoformat()}</Time>\n'
            '            <HeartRateBpm><Value>'
            f'{hr}</Value></HeartRateBpm>\n'
            '          </Trackpoint>\n')
    lines += ['        </Track>\n', '      </Lap>\n', '    </Activity>\n', _TCX_FOOTER]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("".join(lines))


def generate(out_dir: str, weeks: int = 4, seed: int = 7) -> str:
    random.seed(seed); np.random.seed(seed)
    os.makedirs(out_dir, exist_ok=True)

    start = datetime.now(timezone.utc) - timedelta(weeks=weeks)
    plan = [  # (weekday, sport, dur_min, hr_base, hr_amp)
        (0, "Running", 45, 150, 20),
        (1, "Strength", 50, 115, 15),
        (3, "Cycling", 70, 135, 18),
        (5, "Running", 80, 145, 22),
    ]
    made = 0
    for w in range(weeks):
        for wd, sport, dur, hb, ha in plan:
            # progressive overload + a deload-ish final week
            scale = 1.0 + 0.08 * w - (0.25 if w == weeks - 1 else 0)
            day = start + timedelta(weeks=w, days=wd, hours=7)
            fname = os.path.join(out_dir,
                                 f"{day.strftime('%Y%m%d')}_{sport.lower()}.tcx")
            _write_tcx(fname, day, sport, max(15, dur * scale), hb, ha)
            made += 1

    # a strength manifest CSV (gym sessions with tags + RPE, no HR)
    csv_path = os.path.join(out_dir, "gym_manifest.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        wtr = csv.writer(fh)
        wtr.writerow(["date", "sport", "duration_min", "rpe", "notes"])
        for w in range(weeks):
            day = (start + timedelta(weeks=w, days=2, hours=18)).strftime("%Y-%m-%d")
            wtr.writerow([day, "strength", 55, 8, "leg day - squat focus"])
            day2 = (start + timedelta(weeks=w, days=4, hours=18)).strftime("%Y-%m-%d")
            wtr.writerow([day2, "strength", 45, 7, "push day - bench + shoulders"])

    print(f"[sample_data] wrote {made} TCX files + 1 manifest CSV to {out_dir}")
    return out_dir


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "sample_sessions"
    generate(out)
