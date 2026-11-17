# `bioscout.lab.load_tracking.report`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/report.py)

PDF report for the load-tracking module.

Renders a multi-page matplotlib PDF (same backend/approach as  
``utils/summary.py``):

    Page 1 — Overview: KPI banner (ACWR, weekly load, monotony, fatigue),  
             daily-load timeline coloured by activity, ACWR band chart.  
    Page 2 — Fitness/fatigue (Banister) curves + per-muscle fatigue ranking.  
    Page 3 — Per-muscle weekly load heatmap + session log + recovery notes.

## Contents

- [`build_report`](#build_report) — Render the full PDF report. Returns the output path.

### `build_report`

```python
build_report(athlete, results, output_path: str, title: Optional[str] = None) -> str
```

| input | type | default |
|---|---|---|
| `athlete` | – | required |
| `results` | – | required |
| `output_path` | str | required |
| `title` | Optional[str] | `None` |

**returns** `str`

Render the full PDF report. Returns the output path.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/report.py#L231)</sub>
