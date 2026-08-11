"""Collings-style rank-shift figures for muscle force.

    python -m bioscout --collings <session path>
    python -m bioscout --collings <session path> --skip gpk_mri lernagopal
    python -m bioscout --collings <session path> --trial Walking_03 --metric impulse

After Collings et al. (2025), Med Sci Sports Exerc — "Comparison of exercise
ranking from highest to lowest based on peak normalized muscle force and peak
normalized EMG amplitude". Their figure ranks a list of exercises twice, once
by each measure, and draws a connector between the two rankings so the
DISAGREEMENT is the thing you read, not either ranking on its own.

WHAT IS BORROWED, AND WHAT IS NOT
    Borrowed: the paired ranked-bar layout, the connectors, and — the part that
    makes it legible — COLOUR ANCHORED ON THE FIRST COLUMN. Each item is
    coloured by its rank in the leftmost panel and keeps that colour in every
    panel to its right. A dark bar sitting low on the right is then instantly
    "this one dropped", with no need to trace a line.

    Not borrowed: their columns are two MEASURES of the same exercises (force
    vs EMG) on one model. Here the columns are usually MODELS or CALIBRATION
    VARIANTS of the same muscles. The grammar is identical; the question is
    not. Do not describe output from this function as a replication of
    Collings et al.

WHY COLOUR-BY-FIRST-COLUMN AND NOT A FIXED PALETTE
    A fixed per-muscle palette is comparable across figures but throws away the
    light-to-dark gradient, and it is the gradient that carries the signal: in
    the anchored scheme the leftmost panel is always a clean dark-to-pale ramp,
    so ANY colour disorder further right is a re-ranking. With a fixed palette
    every panel looks equally shuffled and you are back to tracing lines.

THE ARROW CONVENTION IS THE PAPER'S, AND IT IS EASY TO INVERT BY ACCIDENT
    An arrow runs from an item's rank in one column to its rank in the column
    IMMEDIATELY RIGHT of it.

        blue   ranked HIGHER by the right-hand column  (it over-rates this one)
        red    ranked LOWER  by the right-hand column  (it under-rates it)
        grey   no change
        dotted it left the top-N entirely

    Collings phrase this as "red = underestimated, blue = overestimated by
    EMG", EMG being their right-hand column. Same rule, stated by position so
    it stays correct when the columns are models rather than measures.
"""
import glob
import io
import os
import re

# Grouped rather than per-muscle because the claim is about FUNCTION: a
# ranking that splits soleus from the gastrocnemii is answering a question
# nobody asked. Lifted from results.py so this figure and the supplementary
# rank figures group identically.
WORK_GROUPS = {
    "Gluteus maximus": ("glmax1", "glmax2", "glmax3"),
    "Gluteus medius":  ("glmed1", "glmed2", "glmed3"),
    "Gluteus minimus": ("glmin1", "glmin2", "glmin3"),
    "Adductor magnus": ("addmagDist", "addmagIsch", "addmagMid", "addmagProx"),
    "Hamstrings":      ("bflh", "bfsh", "semimem", "semiten"),
    "Vasti":           ("vasint", "vaslat", "vasmed"),
    "Rectus femoris":  ("recfem",),
    "Iliopsoas":       ("iliacus", "psoas"),
    "Triceps surae":   ("soleus", "gaslat", "gasmed"),
    "Peroneals":       ("perlong", "perbrev"),
}
_GROUP_OF = {m: g for g, ms in WORK_GROUPS.items() for m in ms}
PRETTY = {
    "glmax": "Gluteus max", "glmed": "Gluteus med", "glmin": "Gluteus min",
    "addmag": "Adductor magnus", "addlong": "Adductor longus",
    "addbrev": "Adductor brevis", "bflh": "Biceps fem. long head",
    "bfsh": "Biceps fem. short head", "semimem": "Semimembranosus",
    "semiten": "Semitendinosus", "recfem": "Rectus femoris",
    "vasint": "Vastus intermedius", "vaslat": "Vastus lateralis",
    "vasmed": "Vastus medialis", "soleus": "Soleus",
    "gaslat": "Gastroc. lateralis", "gasmed": "Gastroc. medialis",
    "tibant": "Tibialis anterior", "tibpost": "Tibialis posterior",
    "iliacus": "Iliacus", "psoas": "Psoas", "grac": "Gracilis",
    "sart": "Sartorius", "tfl": "TFL", "perlong": "Peroneus longus",
    "perbrev": "Peroneus brevis", "piri": "Piriformis",
}
SO_LABEL = "static opt"
# The connector palette, named so a caller building its own legend cannot get
# it subtly wrong. Blue/red are the ColorBrewer RdBu extremes Collings use;
# grey is "no change" and is deliberately weak, because a rank that did not
# move is the boring case.
UP_COLOUR = "#2166ac"       # ranked HIGHER by the column to the right
DOWN_COLOUR = "#b2182b"     # ranked LOWER  by the column to the right
SAME_COLOUR = "0.65"        # unchanged rank
_NON_ITERATION = {"experimental", "logs", "outputs", "raw", "1_raw",
                  "2_experimental", "4_outputs", "_to_delete"}


# ------------------------------------------------------------------ reading
def _read_sto(path):
    """(header, rows) from an OpenSim/CEINMS .sto. Plain text on purpose —
    this figure must work without OpenSim on the path."""
    L = io.open(path, encoding="utf-8", errors="replace").read().splitlines()
    hits = [k for k, x in enumerate(L) if x.strip().lower() == "endheader"]
    if not hits:
        return [], []
    i = hits[0]
    h = [c.strip() for c in L[i + 1].replace("\r", "").split("\t") if c.strip()]
    R = []
    for ln in L[i + 2:]:
        f = [x for x in ln.replace("\r", "").split("\t") if x.strip()]
        if len(f) != len(h):
            continue
        try:
            R.append([float(x) for x in f])
        except ValueError:
            pass
    return h, R


def muscle_label(name):
    stem = str(name)[:-2] if str(name).endswith(("_r", "_l")) else str(name)
    for k in sorted(PRETTY, key=len, reverse=True):
        if stem.startswith(k):
            suffix = stem[len(k):]
            return PRETTY[k] + ((" %s" % suffix) if suffix else "")
    return stem


def work_group(name):
    stem = str(name)[:-2] if str(name).endswith(("_r", "_l")) else str(name)
    return _GROUP_OF.get(stem, muscle_label(name))


def group_values(h, R, metric="peak", side="_r", allowed=None):
    """{group: value} for one force table.

    metric='peak'    the maximum over time of the group's SUMMED force. Summed
                     before the max, not after: three muscles peaking at
                     different instants are not a group that peaked three
                     times. This is the Collings measure.
    metric='impulse' time-integral of that same summed force.
    """
    if not R:
        return {}
    cols = {}
    for c in h[1:]:
        if side and not c.endswith(side):
            continue
        if allowed is not None and c not in allowed:
            continue
        cols.setdefault(work_group(c), []).append(h.index(c))
    tt = [r[0] for r in R]
    out = {}
    for g, idx in cols.items():
        series = [sum(r[j] for j in idx) for r in R]
        if metric == "impulse":
            out[g] = sum(0.5 * (series[k] + series[k + 1]) * (tt[k + 1] - tt[k])
                         for k in range(len(series) - 1))
        else:
            out[g] = max(series)
    return out


# ------------------------------------------------------------ session layout
def iterations_root(session):
    numbered = os.path.join(session, "3_iterations")
    return numbered if os.path.isdir(numbered) else session


def find_iterations(session, skip=()):
    root = iterations_root(session)
    if not os.path.isdir(root):
        return []
    skip = {s.lower() for s in (skip or ())}
    out = []
    for d in sorted(os.listdir(root)):
        p = os.path.join(root, d)
        if not os.path.isdir(p) or d.startswith(".") or d.startswith("_"):
            continue
        if d in _NON_ITERATION or "_backup_" in d or d.lower() in skip:
            continue
        out.append(d)
    return out


def find_trials(session, iteration):
    p = os.path.join(iterations_root(session), iteration)
    if not os.path.isdir(p):
        return []
    return sorted(d for d in os.listdir(p)
                  if os.path.isdir(os.path.join(p, d))
                  and not d.startswith(("_", "."))
                  and d not in ("ceinms_calibration", "static_optimisation"))


def ceinms_forces(session, iteration, trial):
    """The CEINMS execution force file, newest Execution_* wins."""
    base = os.path.join(iterations_root(session), iteration, trial, "ceinms")
    hits = [f for f in glob.glob(os.path.join(base, "Execution_*",
                                              "MuscleForces.sto"))
            if os.path.exists(f)]
    return max(hits, key=os.path.getmtime) if hits else None


def so_forces(session, iteration, trial):
    hits = glob.glob(os.path.join(iterations_root(session), iteration, trial,
                                  "static_optimisation", "*force.sto"))
    return max(hits, key=os.path.getmtime) if hits else None


# ------------------------------------------------------------------ drawing
def _ramp(n):
    """Collings' light-to-dark ladder: dark blue-violet at rank 1 down to pale
    yellow at rank n. YlGnBu reversed matches the published figure closely."""
    import matplotlib
    import numpy as np
    # `matplotlib.cm.get_cmap` was REMOVED in matplotlib 3.9, and
    # `matplotlib.colormaps` does not exist before 3.5. Try the modern one
    # first so this keeps working on both sides of that break.
    try:
        m = matplotlib.colormaps["YlGnBu"]
    except (AttributeError, KeyError):
        import matplotlib.cm as cm
        m = cm.get_cmap("YlGnBu")
    # 0.18..0.95 rather than 0..1: the extreme pale end is invisible on white
    # and the extreme dark end swallows the label text.
    return [m(x) for x in np.linspace(0.95, 0.18, max(n, 1))]


def _text_colour(rgba):
    """Black or white label, by luminance. A fixed colour is unreadable at one
    end of the ramp or the other."""
    r, g, b = rgba[0], rgba[1], rgba[2]
    return "white" if (0.299 * r + 0.587 * g + 0.114 * b) < 0.55 else "#111111"


def _text_width_pt(s, fs):
    """Width of `s` in POINTS at font size `fs`, from the actual font metrics.

    The version this replaced estimated ~0.62 em per character against a fixed
    panel width, and it was wrong in both directions at once: too generous for
    'edl', too mean for 'Gluteus minimus', which it declared a fit and then
    matplotlib clipped at the panel edge. Character counting cannot work — 'i'
    and 'G' are not the same width — so measure the string.

    TextToPath, not a renderer: the caller may not have drawn the figure yet,
    and anything that needs a renderer would have to run after the layout is
    settled, which is exactly when this decision is too late to act on.
    """
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextToPath
    try:
        w, _h, _d = TextToPath().get_text_width_height_descent(
            str(s), FontProperties(size=fs), False)
        return w
    except Exception:                                          # noqa: BLE001
        return 0.62 * fs * len(str(s))          # last-resort estimate


def _label_fits(A, fig, w, text, fs):
    """Is there room for `text` INSIDE a bar `w` data-units wide? -> bool

    The x axis is always 0..100 data units, so a point width converts through
    the axes' width on the page. That width is read from the axes POSITION,
    which is known before the first draw — unlike the window extent.

    The 1.12 margin absorbs a later tight_layout: it usually widens these axes,
    but a caller that narrows them slightly should degrade to 'label goes
    outside', which is merely less pretty, rather than to a clipped label,
    which looks like a bug in the figure.
    """
    ax_pt = A.get_position().width * fig.get_figwidth() * 72.0
    if ax_pt <= 0:
        return False
    need_units = 100.0 * (1.12 * _text_width_pt(text, fs)) / ax_pt
    return w > 1.5 + need_units + 1.0           # 1.5 inset + a little air


def rank_colours(vals, top=12):
    """The colour map `rank_shift_axes` would anchor on `vals`. -> {item: rgba}

    Exposed so a caller drawing SEVERAL rows can anchor them all on one panel.
    Stacked rows each anchored on their own leftmost column are internally
    consistent but not comparable BETWEEN rows: a muscle is dark in one row and
    pale in the other purely because the two rows rank it differently, which is
    exactly the comparison the reader is trying to make by eye.
    """
    order = sorted(vals, key=lambda k: vals[k], reverse=True)
    ramp = _ramp(max(len(order), top))
    return {m: ramp[i] if i < len(ramp) else ramp[-1]
            for i, m in enumerate(order)}


def rank_shift_axes(fig, axes, columns, top=12, xlabel="% of the top group",
                    label_fs=7.5, tick_fs=7.0, title_fs=9.0, colour=None,
                    measured=(), measured_colour="#c1272d"):
    """Draw one Collings-style row.

    `columns` is an ordered list of (title, {item: value}). COLOUR IS ANCHORED
    ON columns[0]: every item takes the colour of its rank there and keeps it
    all the way right. An item absent from column 0 — it can happen, a muscle
    with no force in the reference — falls back to neutral grey rather than
    being given a rank it never had.

    The three font sizes are ARGUMENTS because this function is also embedded
    as one row of a taller grid (results.py's supplementary rank figures stack
    a static-optimisation row over a CEINMS row, at a larger print size). The
    obvious alternative — let the caller restyle the text afterwards — breaks
    the label-fits-inside test below, which is decided at draw time from
    `label_fs`: bump the font after the fact and the longest in-bar labels
    overrun their bars. Pass the size in and the fit follows it.
    """
    from matplotlib.patches import ConnectionPatch

    orders = []
    for _, vals in columns:
        orders.append(sorted(vals, key=lambda k: vals[k], reverse=True))
    # `colour` lets the caller supply the map instead (see rank_colours), so a
    # multi-row figure can anchor every row on ONE panel. Default is unchanged:
    # anchor on this row's own leftmost column.
    if colour is None:
        colour = rank_colours(columns[0][1], top)
    MISSING = (0.80, 0.80, 0.80, 1.0)
    # `measured` names the groups a recorded EMG channel actually drove. Their
    # force is informed by measurement; every other group's is an estimate the
    # calibration made. Marked on the BAR (a red rule at its left edge) and
    # after the label, not by recolouring the text: a red label is unreadable
    # inside a dark bar, and the label colour already carries in/out-of-bar.
    measured = {str(m).strip().lower() for m in (measured or ())}

    for c, (title, vals) in enumerate(columns):
        A = axes[c]
        order = orders[c]
        if not order:
            A.axis("off")
            continue
        topv = vals[order[0]] or 1.0
        for k, m in enumerate(order[:top]):
            col = colour.get(m, MISSING)
            w = 100.0 * vals[m] / topv
            A.barh(k, w, height=0.78, color=col, zorder=2,
                   edgecolor="white", linewidth=0.5)
            is_measured = m.strip().lower() in measured
            if is_measured:
                A.plot([0.6, 0.6], [k - 0.39, k + 0.39], color=measured_colour,
                       lw=2.2, solid_capstyle="butt", zorder=4,
                       clip_on=False)
            # Label INSIDE the bar when it fits, otherwise just past its end.
            # Collings can always put it inside because their bars are long;
            # here the tail of the ranking is often under 20 % of the top, and
            # a label pinned to x=1.5 on a 6 %-wide bar gets clipped at the
            # axes edge.
            tag = " *" if is_measured else ""
            if _label_fits(A, fig, w, m + tag, label_fs):
                A.text(2.6 if is_measured else 1.5, k, m + tag, va="center",
                       ha="left", fontsize=label_fs, zorder=3,
                       color=_text_colour(col))
            else:
                # Outside the bar the asterisk was positioned by space
                # padding, which lands wrong at any font size. The red rule at
                # the bar's own edge already marks these, so the label is left
                # alone and only in-bar labels carry the asterisk.
                A.text(w + 1.5, k, m, va="center", ha="left", fontsize=label_fs,
                       zorder=3, color="#222222", clip_on=False)
        A.set_ylim(top - 0.4, -0.6)
        # Headroom on the right so an overrunning label has somewhere to go.
        # The connectors still leave from x=100, so the geometry is unchanged.
        A.set_xlim(0, 100)
        A.set_xticks([0, 20, 40, 60, 80, 100])
        A.set_yticks([])
        A.tick_params(labelsize=tick_fs)
        A.set_title(title, fontsize=title_fs)
        A.set_xlabel(xlabel, fontsize=label_fs)
        for s in ("top", "right"):
            A.spines[s].set_visible(False)

    for c in range(len(columns) - 1):
        oA, oB = orders[c], orders[c + 1]
        for k, m in enumerate(oA[:top]):
            if m in oB[:top]:
                k2 = oB.index(m)
                col = (SAME_COLOUR if k2 == k else
                       (UP_COLOUR if k2 < k else DOWN_COLOUR))
                style = "-"
            else:
                k2, col, style = top - 0.2, DOWN_COLOUR, ":"
            fig.add_artist(ConnectionPatch(
                (100, k), (0, k2), "data", "data",
                axesA=axes[c], axesB=axes[c + 1], lw=0.9, color=col,
                linestyle=style, alpha=0.85, zorder=1,
                arrowstyle="-|>", mutation_scale=8))
    return colour


def rank_shift_figure(columns, path, title="", subtitle="", top=12,
                      xlabel="% of the top group"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    n = len(columns)
    # Height is driven by `top`, so the title band must be a FIXED number of
    # inches rather than a fraction — a fraction that looks right at top=12
    # leaves half the canvas empty at top=6.
    body_h = 0.30 * top + 1.1
    head_h = 0.95
    fig, axes = plt.subplots(1, n, squeeze=False,
                             figsize=(4.15 * n, body_h + head_h))
    rank_shift_axes(fig, axes[0], columns, top=top, xlabel=xlabel)
    head = title
    if subtitle:
        head += "\n" + subtitle
    fig.suptitle(head, fontsize=10, y=0.995, va="top")
    fig.text(0.5, 1 - (head_h - 0.16) / (body_h + head_h),
             "blue = ranked higher by the column on its right,  red = lower,  "
             "dotted = leaves the top %d      |      bar colour = rank in the "
             "FIRST column, carried right" % top,
             ha="center", va="top", fontsize=7.5, color="0.35")
    # w_pad, not subplots_adjust: tight_layout would overwrite the latter. The
    # gutter has to be wide enough to read the connectors, which are the point.
    fig.tight_layout(rect=(0, 0, 1, 1 - head_h / (body_h + head_h)), w_pad=3.2)
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return path


# -------------------------------------------------------------- entry point
def collings_session(session, skip=(), trials=None, iterations=None,
                     metric="peak", side="_r", top=12, out_dir=None,
                     include_so=True, log=print):
    """One rank-shift figure per trial: columns are static opt, then each
    model iteration. Returns the list of files written.

    `include_so` puts static optimisation FIRST on purpose. It uses no EMG, so
    it is identical whatever the EMG-informed columns do, and it is the only
    no-EMG reference available — which makes it the right thing to anchor the
    colours on. Without it the leftmost column is just whichever model sorted
    first alphabetically, and the whole colour scheme inherits that accident.
    """
    session = os.path.abspath(session)
    if not os.path.isdir(session):
        raise NotADirectoryError(session)
    its = [i for i in (iterations or find_iterations(session, skip))
           if i.lower() not in {s.lower() for s in (skip or ())}]
    if not its:
        log("[collings] no iterations under %s" % session)
        return []
    out_dir = out_dir or os.path.join(session, "4_outputs", "collings")
    os.makedirs(out_dir, exist_ok=True)

    want = list(trials) if trials else None
    seen, written = [], []
    for it in its:
        for t in find_trials(session, it):
            if (want is None or t in want) and t not in seen:
                seen.append(t)

    for trial in seen:
        columns = []
        if include_so:
            for it in its:
                p = so_forces(session, it, trial)
                if not p:
                    continue
                # Restrict SO to the muscles CEINMS also reports: an SO force
                # file carries reserve and residual actuators too, and those
                # are not muscles. Without this the SO column ranks a reserve.
                q = ceinms_forces(session, it, trial)
                allowed = set(_read_sto(q)[0]) if q else None
                h, R = _read_sto(p)
                v = group_values(h, R, metric, side, allowed)
                if v:
                    columns.append((SO_LABEL, v))
                break
        for it in its:
            p = ceinms_forces(session, it, trial)
            if not p:
                log("[collings] %-14s %-16s no CEINMS forces" % (trial, it))
                continue
            h, R = _read_sto(p)
            v = group_values(h, R, metric, side)
            if v:
                columns.append((it, v))
        if len(columns) < 2:
            log("[collings] %s: need at least two columns, got %d — skipped"
                % (trial, len(columns)))
            continue
        f = os.path.join(out_dir, "collings_ranks_%s.png" % trial)
        rank_shift_figure(
            columns, f,
            title="Muscle ranking by %s force — %s"
                  % ("peak" if metric == "peak" else "impulse", trial),
            subtitle="%s limb; after Collings et al. 2025 Med Sci Sports Exerc"
                     % ("right" if side == "_r" else "left"),
            top=top,
            xlabel="%% of the top group (%s force)"
                   % ("peak" if metric == "peak" else "impulse"))
        log("[collings] %s  (%d columns)" % (os.path.relpath(f, session),
                                             len(columns)))
        written.append(f)
    if not written:
        log("[collings] nothing written — no trial had two comparable columns")
    return written
