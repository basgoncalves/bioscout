"""
PDF report for the load-tracking module.

Renders a multi-page matplotlib PDF (same backend/approach as
``utils/summary.py``):

    Page 1 — Overview: KPI banner (ACWR, weekly load, monotony, fatigue),
             daily-load timeline coloured by activity, ACWR band chart.
    Page 2 — Fitness/fatigue (Banister) curves + per-muscle fatigue ranking.
    Page 3 — Per-muscle weekly load heatmap + session log + recovery notes.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle

from . import metrics
from .muscle_map import MUSCLE_GROUPS, MUSCLE_LABELS

_ACTIVITY_COLORS = {
    "running": "#e8590c", "walking": "#f08c00", "hiking": "#c2a000",
    "cycling": "#1971c2", "strength": "#6741d9", "rowing": "#0c8599",
    "swimming": "#1098ad", "elliptical": "#2f9e44", "generic": "#868e96",
}


def _kpi_box(ax, x, label, value, sub="", color="#2f9e44"):
    ax.add_patch(Rectangle((x, 0.1), 0.22, 0.8, transform=ax.transAxes,
                           facecolor=color, alpha=0.12, edgecolor=color, lw=1.5))
    ax.text(x + 0.11, 0.66, value, transform=ax.transAxes, ha="center",
            va="center", fontsize=17, fontweight="bold", color=color)
    ax.text(x + 0.11, 0.34, label, transform=ax.transAxes, ha="center",
            va="center", fontsize=8.5, color="#333333")
    if sub:
        ax.text(x + 0.11, 0.2, sub, transform=ax.transAxes, ha="center",
                va="center", fontsize=7, color="#666666")


def _page_overview(pdf, athlete, r):
    fig = plt.figure(figsize=(11.69, 8.27))   # A4 landscape
    fig.suptitle(f"BioScout — Training Load & Fatigue Report",
                 fontsize=16, fontweight="bold", x=0.5, y=0.97)
    span = f"{r.sessions[0].date}  →  {r.sessions[-1].date}"
    fig.text(0.5, 0.935, f"{athlete.name}    •    {len(r.sessions)} sessions    "
             f"•    {span}", ha="center", fontsize=10, color="#555555")

    gs = fig.add_gridspec(3, 1, height_ratios=[0.7, 1.4, 1.0],
                          left=0.07, right=0.96, top=0.88, bottom=0.08, hspace=0.45)

    # --- KPI banner ---
    axk = fig.add_subplot(gs[0]); axk.axis("off")
    acwr = r.acwr.get("latest_acwr")
    acwr_lbl, acwr_col = metrics.acwr_status(acwr)
    _kpi_box(axk, 0.02, "Acute:Chronic (ACWR)",
             f"{acwr:.2f}" if acwr is not None else "n/a", acwr_lbl, acwr_col)
    wk = r.mono_strain.get("weekly_load")
    _kpi_box(axk, 0.27, "7-day load",
             f"{wk:.0f}" if wk is not None else "n/a", "internal load (AU)", "#1971c2")
    mono = r.mono_strain.get("monotony")
    mono_col = "#e03131" if (mono and mono > 2.0) else "#2f9e44"
    _kpi_box(axk, 0.52, "Monotony",
             f"{mono:.2f}" if mono is not None else "n/a",
             "↑ = under-varied", mono_col)
    fat = r.ff.get("latest_fatigue")
    _kpi_box(axk, 0.77, "Fatigue (Banister)",
             f"{fat:.0f}" if fat is not None else "n/a", "7-day decay", "#f59f00")

    # --- daily load timeline, stacked by activity ---
    axd = fig.add_subplot(gs[1])
    days = [d.day for d in r.daily]
    activities = sorted({a for d in r.daily for a in d.by_activity})
    bottoms = np.zeros(len(days))
    for a in activities:
        vals = np.array([d.by_activity.get(a, 0.0) for d in r.daily])
        axd.bar(days, vals, bottom=bottoms, width=0.9,
                color=_ACTIVITY_COLORS.get(a, "#868e96"), label=a)
        bottoms += vals
    axd.set_title("Daily training load by activity", fontsize=11, loc="left")
    axd.set_ylabel("Internal load (AU)")
    axd.legend(loc="upper left", fontsize=7, ncol=min(len(activities), 5),
               frameon=False)
    axd.grid(axis="y", alpha=0.25)
    for sp in ("top", "right"):
        axd.spines[sp].set_visible(False)

    # --- ACWR band chart ---
    axa = fig.add_subplot(gs[2])
    adays = r.acwr.get("days", [])
    if adays:
        acwr_series = np.array(r.acwr["acwr"])
        axa.axhspan(0.8, 1.3, color="#2f9e44", alpha=0.12, label="optimal 0.8–1.3")
        axa.axhspan(1.3, 1.5, color="#f59f00", alpha=0.12)
        axa.axhspan(1.5, max(2.0, float(np.nanmax(acwr_series)) + 0.2),
                    color="#e03131", alpha=0.10)
        axa.plot(adays, acwr_series, color="#212529", lw=1.8)
        axa.set_ylim(0, max(2.0, float(np.nanmax(acwr_series)) + 0.2))
        axa.axhline(1.0, color="#666", ls=":", lw=0.8)
    axa.set_title("Acute:chronic workload ratio (injury-risk bands)",
                  fontsize=11, loc="left")
    axa.set_ylabel("ACWR")
    axa.legend(loc="upper left", fontsize=7, frameon=False)
    axa.grid(axis="y", alpha=0.25)
    for sp in ("top", "right"):
        axa.spines[sp].set_visible(False)

    fig.text(0.5, 0.02,
             "Internal load from heart-rate TRIMP / session-RPE. ACWR per Williams "
             "et al. 2017 (EWMA). Heuristic estimates — not measured muscle forces.",
             ha="center", fontsize=6.5, color="#999999")
    pdf.savefig(fig); plt.close(fig)


def _page_fatigue(pdf, athlete, r):
    fig = plt.figure(figsize=(11.69, 8.27))
    fig.suptitle("Fitness · Fatigue · Per-muscle loading", fontsize=14,
                 fontweight="bold", y=0.97)
    gs = fig.add_gridspec(2, 1, height_ratios=[1, 1.2],
                          left=0.17, right=0.95, top=0.9, bottom=0.08, hspace=0.4)

    # --- Banister fitness/fatigue/form ---
    axf = fig.add_subplot(gs[0])
    ffdays = r.ff.get("days", [])
    if ffdays:
        axf.plot(ffdays, r.ff["fitness"], color="#1971c2", lw=1.8, label="Fitness (τ≈42d)")
        axf.plot(ffdays, r.ff["fatigue"], color="#e03131", lw=1.8, label="Fatigue (τ≈7d)")
        axf.fill_between(ffdays, r.ff["form"], 0,
                         where=np.array(r.ff["form"]) >= 0, color="#2f9e44",
                         alpha=0.18, label="Form (positive)")
        axf.fill_between(ffdays, r.ff["form"], 0,
                         where=np.array(r.ff["form"]) < 0, color="#f59f00", alpha=0.18)
        axf.axhline(0, color="#666", lw=0.8)
    axf.set_title("Banister fitness–fatigue model", fontsize=11, loc="left")
    axf.set_ylabel("Arbitrary units")
    axf.legend(loc="upper left", fontsize=7, frameon=False)
    axf.grid(alpha=0.25)
    for sp in ("top", "right"):
        axf.spines[sp].set_visible(False)

    # --- per-muscle fatigue ranking ---
    axm = fig.add_subplot(gs[1])
    states = [s for s in r.muscle_states if s.fatigue_index > 0]
    if states:
        labels = [s.label for s in states][::-1]
        vals = [s.fatigue_index for s in states][::-1]
        cols = [s.color for s in states][::-1]
        bars = axm.barh(labels, vals, color=cols)
        for b, s in zip(bars, states[::-1]):
            txt = f"{s.fatigue_index:.0f}"
            if s.acwr:
                txt += f"  (ACWR {s.acwr:.2f})"
            axm.text(b.get_width() + 1, b.get_y() + b.get_height() / 2, txt,
                     va="center", fontsize=7.5, color="#333")
        axm.set_xlim(0, 108)
        axm.axvspan(70, 108, color="#e03131", alpha=0.06)
    axm.set_title("Per-muscle-group fatigue index (0–100, athlete-relative)",
                  fontsize=11, loc="left")
    axm.set_xlabel("Fatigue index")
    for sp in ("top", "right"):
        axm.spines[sp].set_visible(False)
    pdf.savefig(fig); plt.close(fig)


def _page_heatmap(pdf, athlete, r):
    fig = plt.figure(figsize=(11.69, 8.27))
    fig.suptitle("Per-muscle weekly load · session log · recovery", fontsize=14,
                 fontweight="bold", y=0.97)
    gs = fig.add_gridspec(2, 1, height_ratios=[1.25, 1.0],
                          left=0.16, right=0.97, top=0.9, bottom=0.06, hspace=0.45)

    # --- weekly per-muscle heatmap ---
    axh = fig.add_subplot(gs[0])
    if r.sessions:
        start = r.sessions[0].date
        # bucket each session's muscle load into ISO-ish weeks from start
        n_weeks = ((r.sessions[-1].date - start).days // 7) + 1
        mat = np.zeros((len(MUSCLE_GROUPS), n_weeks))
        for s, mload in zip(r.sessions, r.muscle_loads):
            w = (s.date - start).days // 7
            for mi, m in enumerate(MUSCLE_GROUPS):
                mat[mi, w] += mload.get(m, 0.0)
        im = axh.imshow(mat, aspect="auto", cmap="YlOrRd")
        axh.set_yticks(range(len(MUSCLE_GROUPS)))
        axh.set_yticklabels([MUSCLE_LABELS[m] for m in MUSCLE_GROUPS], fontsize=8)
        week_labels = [(start + timedelta(weeks=w)).strftime("%b %d")
                       for w in range(n_weeks)]
        axh.set_xticks(range(n_weeks))
        axh.set_xticklabels(week_labels, fontsize=7, rotation=45, ha="right")
        cb = fig.colorbar(im, ax=axh, fraction=0.025, pad=0.01)
        cb.set_label("Weekly load (AU)", fontsize=8)
    axh.set_title("Accumulated load per muscle group, by week", fontsize=11, loc="left")

    # --- session log (left) + recovery notes (right), side by side ---
    sub = gs[1].subgridspec(1, 2, width_ratios=[1.05, 1.0], wspace=0.08)
    axl = fig.add_subplot(sub[0]); axl.axis("off")
    axr = fig.add_subplot(sub[1]); axr.axis("off")

    recent = list(zip(r.sessions, r.session_loads))[-10:]
    lines = [f"{'Date':<11}{'Activity':<10}{'Dur':>5}{'HR':>5}{'Load':>7} Basis"]
    for s, sl in recent:
        dur = f"{s.duration_min:.0f}m" if s.duration_min else "—"
        hr = f"{s.avg_hr:.0f}" if s.avg_hr else "—"
        basis = sl['basis'].replace('banister_trimp', 'TRIMP').replace(
            'edwards_trimp', 'Edwards').replace('estimated_srpe', 'est.sRPE')
        lines.append(f"{str(s.date):<11}{s.activity:<10}{dur:>5}{hr:>5}"
                     f"{sl['load']:>7.0f} {basis}")
    axl.text(0.0, 1.0, "Recent sessions (last 10)", fontsize=10,
             fontweight="bold", transform=axl.transAxes, va="top")
    axl.text(0.0, 0.9, "\n".join(lines), fontsize=7.5, family="monospace",
             transform=axl.transAxes, va="top")

    import textwrap as _tw
    axr.text(0.0, 1.0, "Recovery notes", fontsize=10, fontweight="bold",
             transform=axr.transAxes, va="top")
    y = 0.88
    for n in r.recommendations:
        wrapped = _tw.fill(n, width=54)
        axr.text(0.0, y, "• " + wrapped, fontsize=8, transform=axr.transAxes,
                 va="top")
        y -= 0.07 * (wrapped.count("\n") + 1) + 0.04
    pdf.savefig(fig); plt.close(fig)


def build_report(athlete, results, output_path: str,
                 title: Optional[str] = None) -> str:
    """Render the full PDF report. Returns the output path."""
    if not results.sessions:
        raise ValueError("No sessions to report.")
    with PdfPages(output_path) as pdf:
        _page_overview(pdf, athlete, results)
        _page_fatigue(pdf, athlete, results)
        _page_heatmap(pdf, athlete, results)
        d = pdf.infodict()
        d["Title"] = title or "BioScout Load & Fatigue Report"
        d["Author"] = "BioScout"
    return output_path
