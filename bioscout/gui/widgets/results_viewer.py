"""Results Viewer Tab — multi-subject, multi-trial plot builder.

Layout
------
Left panel  : project folder + cascading dropdowns (participant → session → trial → file)
              + colour picker + "Add to Plot" + series queue + Clear All
Centre      : matplotlib grid of subplots (one per selected channel)
              + NavigationToolbar + Save / Clear buttons
Right panel : channel tick-boxes (union across all loaded series)
              + Select All / None
Bottom bar  : Time Normalise toggle (0-100 %) + Single plot toggle

Adding a series ticks exactly ONE channel — the first non-time column — and
leaves the rest loaded but unticked. Ticking everything by default meant a
126-channel static-optimisation file opened as a 126-subplot figure roughly
1300x8600 px, which takes seconds to draw and reads as a hang.
"""

from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Optional
import sys

import customtkinter as ctk
import tkinter as tk

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.config_manager import ConfigManager
from utils.logger import logger

try:
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    from matplotlib.figure import Figure
    import numpy as np
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

try:
    import pandas as pd
    HAS_PD = True
except ImportError:
    HAS_PD = False

# ── colour palette (cycles) ─────────────────────────────────────────────────
_PALETTE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
    "#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5",
]

#: Column names that are an x-axis, not a signal. These are never the channel
#: auto-ticked when a series loads, and never counted as data.
_TIME_NAMES = {"time", "t", "times", "frame", "frame#", "frames", "index",
               "percent", "%", "% cycle", "cycle"}

#: Above this many subplots the grid figure gets tall enough to take seconds to
#: rasterise. Past it the grid is capped and the count is reported — see
#: _render_plot. Single-plot mode has no such limit.
MAX_GRID_SUBPLOTS = 64

#: Beyond this many lines a legend is more noise than key, so it is dropped and
#: the count goes in the title instead.
MAX_LEGEND_ENTRIES = 24

#: Series are told apart by line style when several share one axes.
_SERIES_STYLES = ["-", "--", ":", "-."]


def is_time_column(name: str) -> bool:
    """True for a column that is an x-axis rather than a signal."""
    n = str(name).strip().lower()
    return n in _TIME_NAMES or n.startswith("time")


def default_channel(columns) -> Optional[str]:
    """The channel to tick when a series is first added: first non-time column.

    Falls back to the first column outright for a file that is somehow all
    time-like, so adding a series always plots *something* rather than
    silently showing an empty figure.
    """
    cols = list(columns)
    for c in cols:
        if not is_time_column(c):
            return c
    return cols[0] if cols else None


# ── file parsers ─────────────────────────────────────────────────────────────

def _load_file(path: Path) -> Optional["pd.DataFrame"]:
    """Return a DataFrame (time as first column if present) or None."""
    if not HAS_PD:
        return None
    suf = path.suffix.lower()
    try:
        if suf in (".mot", ".sto"):
            return _parse_mot(path)
        if suf == ".trc":
            return _parse_trc(path)
        if suf == ".csv":
            return pd.read_csv(path)
    except Exception as e:
        logger.warning(f"Could not load {path.name}: {e}")
    return None


def _parse_mot(path: Path) -> Optional["pd.DataFrame"]:
    """Parse OpenSim .mot / .sto (header ends at 'endheader')."""
    lines = path.read_text(errors="replace").splitlines()
    header_end = next((i for i, l in enumerate(lines)
                       if l.strip().lower() == "endheader"), None)
    if header_end is None:
        return None
    data_lines = [l for l in lines[header_end + 1:] if l.strip()]
    if not data_lines:
        return None
    # First non-empty line after endheader may be the column header
    col_line = data_lines[0]
    # Heuristic: if it contains letters it's a header row
    if re.search(r"[a-zA-Z_]", col_line):
        cols = col_line.split()
        rows = data_lines[1:]
    else:
        cols = None
        rows = data_lines
    parsed = []
    for r in rows:
        try:
            parsed.append([float(x) for x in r.split()])
        except ValueError:
            continue
    if not parsed:
        return None
    df = pd.DataFrame(parsed, columns=cols if cols and len(cols) == len(parsed[0]) else None)
    return df


def _parse_trc(path: Path) -> Optional["pd.DataFrame"]:
    """Parse OpenSim .trc marker file."""
    lines = path.read_text(errors="replace").splitlines()
    # TRC has 4 header lines; line 3 (0-indexed 2) is the marker names,
    # line 4 (0-indexed 3) is X/Y/Z sub-labels; data starts at line 5.
    if len(lines) < 6:
        return None
    try:
        marker_names = lines[3].split("\t")
        sub_labels   = lines[4].split("\t")
        col_names: list[str] = []
        mi = 0
        for sub in sub_labels:
            sub = sub.strip()
            if not sub:
                col_names.append(f"col{len(col_names)}")
                continue
            if sub.upper() in ("FRAME#", "TIME"):
                col_names.append(sub)
            else:
                marker = marker_names[mi].strip() if mi < len(marker_names) else f"M{mi}"
                col_names.append(f"{marker}_{sub}")
                if sub.upper() == "Z":
                    mi += 1
        rows = []
        for l in lines[5:]:
            if not l.strip():
                continue
            try:
                rows.append([float(x) for x in l.split("\t") if x.strip()])
            except ValueError:
                continue
        if not rows:
            return None
        max_cols = max(len(r) for r in rows)
        while len(col_names) < max_cols:
            col_names.append(f"col{len(col_names)}")
        rows = [r + [float("nan")] * (max_cols - len(r)) for r in rows]
        return pd.DataFrame(rows, columns=col_names[:max_cols])
    except Exception as e:
        logger.warning(f"TRC parse error: {e}")
        return None


def _time_normalise(df: "pd.DataFrame") -> "pd.DataFrame":
    """Interpolate all columns to 101 evenly-spaced points (0-100%)."""
    import numpy as np
    n = len(df)
    if n < 2:
        return df
    old_x = np.linspace(0, 100, n)
    new_x = np.linspace(0, 100, 101)
    result = {}
    for col in df.columns:
        try:
            result[col] = np.interp(new_x, old_x, df[col].values.astype(float))
        except Exception:
            result[col] = np.full(101, float("nan"))
    return pd.DataFrame(result)


# ── main widget ──────────────────────────────────────────────────────────────

# --------------------------------------------------------------- session layout
# The Results tab has to answer "what trials does this session have?" without
# assuming where they live: a session is either the numbered layout
# (1_c3dfiles / 2_experimental / 3_iterations/<iteration>/<trial>) or the older
# flat one (<session>/<iteration>/<trial>). bioscout.utils.session_layout knows
# the difference, so ask it rather than globbing directories and hoping.

def _layout():
    from bioscout.utils import session_layout as _L
    return _L


def _layout_trials(sess_dir):
    """Trial names for a session, from the c3d files and from what is on disk.

    The c3d files are the authoritative list — they exist before any processing
    has run, so a fresh session still populates. Trials that only exist as
    output folders (an export from an earlier capture, a renamed c3d) are
    unioned in, so nothing already processed disappears from the dropdown.
    """
    L = _layout()
    sess_dir = Path(sess_dir)
    names = set()
    try:
        c3d = Path(L.c3d_root(str(sess_dir)))
        if c3d.is_dir():
            names |= {f.stem for f in c3d.glob("*.c3d")}
    except Exception:
        pass
    try:
        exp = Path(L.experimental_root(str(sess_dir)))
        if exp.is_dir():
            names |= {d.name for d in exp.iterdir() if d.is_dir()}
    except Exception:
        pass
    try:
        itr = Path(L.iterations_root(str(sess_dir)))
        if itr.is_dir():
            for it in itr.iterdir():
                if it.is_dir() and it.name not in L.NON_ITERATION_DIRS:
                    names |= {d.name for d in it.iterdir() if d.is_dir()}
    except Exception:
        pass
    return sorted(names)


def _layout_trial_sources(sess_dir, trial):
    """``[(label, directory)]`` holding data for one trial.

    A trial's files are split across the shared export and every model
    iteration that has run it, so a single "trial folder" does not exist. Each
    location is labelled, and the label is what disambiguates two files with
    the same name from different models.
    """
    L = _layout()
    sess_dir = Path(sess_dir)
    out = []
    try:
        exp = Path(L.experimental_root(str(sess_dir))) / trial
        if exp.is_dir():
            out.append((Path(L.experimental_root(str(sess_dir))).name, exp))
    except Exception:
        pass
    try:
        itr = Path(L.iterations_root(str(sess_dir)))
        if itr.is_dir():
            for it in sorted(itr.iterdir()):
                if not it.is_dir() or it.name in L.NON_ITERATION_DIRS:
                    continue
                d = it / trial
                if d.is_dir():
                    out.append((it.name, d))
    except Exception:
        pass
    legacy = sess_dir / trial          # pre-layout sessions
    if legacy.is_dir():
        out.append(("(session)", legacy))
    return out


# ------------------------------------------------------------------ filtering
#: Filter name -> what its numeric parameter means. "none" is first so it is
#: the default in the dropdown.
FILTERS = ("none", "butterworth low-pass", "moving average", "savitzky-golay")


def apply_filter(y, kind, cutoff, order, fs):
    """Filter one signal. Returns the input unchanged on any failure.

    Deliberately never raises: this runs inside the draw loop, where a bad
    parameter must not take the whole plot down.
    """
    y = np.asarray(y, float)
    if kind == "none" or y.size < 4 or not np.any(np.isfinite(y)):
        return y
    try:
        if kind == "butterworth low-pass":
            from scipy.signal import butter, filtfilt
            wn = min(max(cutoff / (fs / 2.0), 1e-6), 0.999)
            b, a = butter(max(1, int(order)), wn, btype="low")
            return filtfilt(b, a, y)
        if kind == "moving average":
            w = max(1, int(cutoff))
            if w >= y.size:
                return y
            return np.convolve(y, np.ones(w) / w, mode="same")
        if kind == "savitzky-golay":
            from scipy.signal import savgol_filter
            w = max(3, min(int(cutoff) | 1, (y.size - 1) | 1))   # odd, in range
            return savgol_filter(y, w, int(min(max(1, order), w - 1)))
    except Exception:
        return y
    return y


# --------------------------------------------------------------- file grouping
#: Trial subfolder -> the pipeline stage it belongs to, in pipeline order.
#: Anything not listed keeps its own folder name, so a new stage shows up as
#: itself rather than being silently filed under "Other".
GROUPS = (
    ("",                     "Experimental"),      # files at the trial root
    ("external_biomechanics", "Kinematics / Dynamics"),
    ("muscle_analysis",       "Muscle Analysis"),
    ("static_optimisation",   "Static Optimisation"),
    ("static_optimization",   "Static Optimisation"),
    ("joint_contact_forces",  "Joint Reaction"),
    ("ceinms",                "CEINMS"),
)
_GROUP_LABEL = dict(GROUPS)
_GROUP_ORDER = [lbl for _k, lbl in GROUPS]


def group_of(rel_path):
    """Stage label for a file's path relative to its trial folder."""
    parts = str(rel_path).replace("\\", "/").split("/")
    top = parts[0] if len(parts) > 1 else ""
    return _GROUP_LABEL.get(top, top or "Experimental")


def sort_groups(labels):
    """Pipeline order first, then anything unrecognised alphabetically."""
    known = [g for g in _GROUP_ORDER if g in labels]
    return known + sorted(l for l in labels if l not in _GROUP_ORDER)


class ResultsViewerTab(ctk.CTkFrame):
    """Results viewer with project-tree dropdowns, channel tickboxes, and grid subplots."""

    _DATA_EXTS = {".mot", ".sto", ".csv", ".trc"}

    def __init__(self, parent, config_manager: ConfigManager, status_callback):
        super().__init__(parent)
        self.config_manager  = config_manager
        self.status_callback = status_callback

        self._project_root: Optional[Path] = None
        self._series: list[dict] = []          # added plot lines
        self._channels: list[str] = []         # union of all channels
        self._ch_vars:  dict[str, ctk.BooleanVar] = {}
        self._fig: Optional[Figure] = None
        self._canvas_widget = None
        self._toolbar = None
        self._colour_idx = 0

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        root = ctk.CTkFrame(self, fg_color="transparent")
        root.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(1, weight=1)

        # ── left panel: selection + series ─────────────────────────────
        left = ctk.CTkFrame(root, width=240, fg_color="#161620", corner_radius=8)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        left.grid_propagate(False)
        # The stretchy row is set AFTER the widgets are built (see below):
        # hard-coding an index here put the weight on the 'File' label.
        left.grid_columnconfigure(0, weight=1)

        row = 0
        def _lbl(text):
            nonlocal row
            ctk.CTkLabel(left, text=text, font=("Segoe UI", 11, "bold"),
                         text_color="#aaaaaa").grid(row=row, column=0,
                         sticky="w", padx=10, pady=(8, 1))
            row += 1

        def _menu(var, values=("—",)):
            nonlocal row
            m = ctk.CTkOptionMenu(left, variable=var, values=list(values),
                                  height=28, font=("Segoe UI", 12))
            m.grid(row=row, column=0, sticky="ew", padx=10, pady=(0, 2))
            row += 1
            return m

        _lbl("Participant")
        self._part_var  = ctk.StringVar(value="—")
        self._part_menu = _menu(self._part_var)
        self._part_var.trace_add("write", lambda *_: self._on_part_changed())

        _lbl("Session / Date")
        self._sess_var  = ctk.StringVar(value="—")
        self._sess_menu = _menu(self._sess_var)
        self._sess_var.trace_add("write", lambda *_: self._on_sess_changed())

        _lbl("Trial")
        self._trial_var  = ctk.StringVar(value="—")
        self._trial_menu = _menu(self._trial_var)
        self._trial_var.trace_add("write", lambda *_: self._on_trial_changed())

        # Source and Group narrow the file list before it is shown: a trial
        # with four iterations has ~200 outputs, which as one dropdown is a
        # list taller than the screen.
        _lbl("Source  (model / experimental)")
        self._source_var = ctk.StringVar(value="—")
        self._source_menu = _menu(self._source_var)
        self._source_var.trace_add("write", lambda *_: self._on_source_changed())

        _lbl("Group  (pipeline stage)")
        self._group_var = ctk.StringVar(value="—")
        self._group_menu = _menu(self._group_var)
        self._group_var.trace_add("write", lambda *_: self._on_group_changed())

        # File sits directly under Group with its label on the same line: it is
        # the narrowest choice on the panel and a full-width label above it
        # wasted a row for no gain.
        file_row = ctk.CTkFrame(left, fg_color="transparent")
        file_row.grid(row=row, column=0, sticky="ew", padx=10, pady=(8, 2))
        file_row.grid_columnconfigure(1, weight=1)
        row += 1
        ctk.CTkLabel(file_row, text="File", font=("Segoe UI", 11, "bold"),
                     text_color="#aaaaaa").grid(row=0, column=0, sticky="w",
                                                padx=(0, 6))
        self._file_var  = ctk.StringVar(value="—")
        self._file_menu = ctk.CTkOptionMenu(file_row, variable=self._file_var,
                                            values=["—"], height=28,
                                            font=("Segoe UI", 12))
        self._file_menu.grid(row=0, column=1, sticky="ew")
        #: display name -> absolute path, filled by _on_trial_changed
        self._file_map = {}

        # colour + add button
        colour_row = ctk.CTkFrame(left, fg_color="transparent")
        colour_row.grid(row=row, column=0, sticky="ew", padx=10, pady=(8, 2))
        colour_row.grid_columnconfigure(1, weight=1)
        row += 1
        self._colour_btn = ctk.CTkButton(colour_row, text="■", width=32, height=26,
                                         fg_color=_PALETTE[0], hover_color=_PALETTE[0],
                                         command=self._pick_colour)
        self._colour_btn.grid(row=0, column=0, padx=(0, 4))
        ctk.CTkLabel(colour_row, text="Colour", font=("Segoe UI", 12)).grid(
            row=0, column=1, sticky="w")

        self._cur_colour = _PALETTE[0]

        ctk.CTkButton(left, text="➕  Add to Plot", height=28,
                      fg_color="#28a745", hover_color="#218838",
                      command=self._add_series).grid(row=row, column=0,
                      sticky="ew", padx=10, pady=(4, 6))
        row += 1

        # series list (scrollable)
        ctk.CTkLabel(left, text="Series", font=("Segoe UI", 11, "bold"),
                     text_color="#aaaaaa").grid(row=row, column=0,
                     sticky="w", padx=10, pady=(6, 1))
        row += 1
        self._series_frame = ctk.CTkScrollableFrame(left, fg_color="transparent",
                                                     corner_radius=0)
        self._series_frame.grid(row=row, column=0, sticky="nsew", padx=4, pady=0)
        left.grid_rowconfigure(row, weight=1)     # the list absorbs the slack
        row += 1

        # ---- filter bar --------------------------------------------------
        fbar = ctk.CTkFrame(left, fg_color="#1b1b26", corner_radius=6)
        fbar.grid(row=row, column=0, sticky="ew", padx=6, pady=(6, 2))
        fbar.grid_columnconfigure(1, weight=1)
        row += 1
        ctk.CTkLabel(fbar, text="Filter", font=("Segoe UI", 11, "bold"),
                     text_color="#aaaaaa").grid(row=0, column=0, columnspan=2,
                                                sticky="w", padx=6, pady=(6, 2))
        self._filter_var = ctk.StringVar(value="none")
        ctk.CTkOptionMenu(fbar, variable=self._filter_var, values=list(FILTERS),
                          height=26, font=("Segoe UI", 11),
                          command=lambda *_: self._on_filter_kind()).grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 2))
        self._cut_lbl = ctk.CTkLabel(fbar, text="cutoff (Hz)",
                                     font=("Segoe UI", 10), text_color="#aaaaaa")
        self._cut_lbl.grid(row=2, column=0, sticky="w", padx=6)
        self._cut_var = ctk.StringVar(value="6")
        ctk.CTkEntry(fbar, textvariable=self._cut_var, width=64, height=24,
                     font=("Segoe UI", 11)).grid(row=2, column=1, sticky="e",
                                                 padx=6)
        ctk.CTkLabel(fbar, text="order", font=("Segoe UI", 10),
                     text_color="#aaaaaa").grid(row=3, column=0, sticky="w", padx=6)
        self._ord_var = ctk.StringVar(value="4")
        ctk.CTkEntry(fbar, textvariable=self._ord_var, width=64, height=24,
                     font=("Segoe UI", 11)).grid(row=3, column=1, sticky="e",
                                                 padx=6, pady=(0, 2))
        self._filter_note = ctk.CTkLabel(fbar, text="", font=("Segoe UI", 9),
                                         text_color="#888888", wraplength=195,
                                         justify="left")
        self._filter_note.grid(row=4, column=0, columnspan=2, sticky="w",
                               padx=6, pady=(0, 2))
        ctk.CTkButton(fbar, text="Apply", height=24, font=("Segoe UI", 11),
                      command=self._refresh_plot).grid(row=5, column=0,
                                                       sticky="ew", padx=(6, 3),
                                                       pady=(2, 6))
        ctk.CTkButton(fbar, text="Save…", height=24, font=("Segoe UI", 11),
                      fg_color="#2f6f9f", hover_color="#3a86bd",
                      command=self._save_filtered).grid(row=5, column=1,
                                                        sticky="ew", padx=(3, 6),
                                                        pady=(2, 6))

        ctk.CTkButton(left, text="Clear All", height=24,
                      fg_color="#555555", hover_color="#666666",
                      command=self._clear_all).grid(row=row, column=0,
                      sticky="ew", padx=10, pady=(4, 8))

        # ── centre: plot ─────────────────────────────────────────────────
        centre = ctk.CTkFrame(root, fg_color="#111118", corner_radius=8)
        centre.grid(row=0, column=1, sticky="nsew", padx=4)
        centre.grid_rowconfigure(0, weight=1)
        centre.grid_columnconfigure(0, weight=1)

        self._plot_frame = ctk.CTkFrame(centre, fg_color="#111118", corner_radius=0)
        self._plot_frame.grid(row=0, column=0, sticky="nsew")
        self._plot_frame.grid_rowconfigure(0, weight=1)
        self._plot_frame.grid_columnconfigure(0, weight=1)

        self._plot_placeholder = ctk.CTkLabel(
            self._plot_frame,
            text="Add a series and select channels to plot",
            text_color="#555555", font=("Segoe UI", 12))
        self._plot_placeholder.grid(row=0, column=0)

        # bottom control bar
        bot = ctk.CTkFrame(centre, fg_color="#1a1a2a", corner_radius=0, height=38)
        bot.grid(row=1, column=0, sticky="ew")
        bot.grid_propagate(False)
        bot.grid_columnconfigure(1, weight=1)

        self._norm_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(bot, text="Normalise time 0-100%", variable=self._norm_var,
                        font=("Segoe UI", 10), command=self._refresh_plot
                        ).grid(row=0, column=0, padx=10, pady=6, sticky="w")
        # One axes for everything vs one subplot per channel. Overlaying is the
        # right view when the channels share units (comparing muscle forces);
        # the grid is right when they do not.
        self._single_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(bot, text="Single plot (overlay channels)",
                        variable=self._single_var,
                        font=("Segoe UI", 10), command=self._refresh_plot
                        ).grid(row=0, column=1, padx=(4, 10), pady=6, sticky="w")
        ctk.CTkButton(bot, text="💾 Save", width=70, height=26,
                      command=self._save_figure
                      ).grid(row=0, column=2, padx=(4, 4), pady=6)
        ctk.CTkButton(bot, text="🗑 Clear", width=70, height=26,
                      fg_color="#555555", hover_color="#666666",
                      command=self._clear_plot
                      ).grid(row=0, column=3, padx=(0, 10), pady=6)

        # ── right panel: channels ────────────────────────────────────────
        right = ctk.CTkFrame(root, width=190, fg_color="#161620", corner_radius=8)
        right.grid(row=0, column=2, sticky="nsew", padx=(4, 0))
        right.grid_propagate(False)
        right.grid_rowconfigure(2, weight=1)
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right, text="Channels", font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(8, 2))

        sel_row = ctk.CTkFrame(right, fg_color="transparent")
        sel_row.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 4))
        sel_row.grid_columnconfigure(0, weight=1)
        sel_row.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(sel_row, text="All", height=22, width=50,
                      fg_color="#2a3a4a", hover_color="#3a4a5a",
                      command=lambda: self._set_all_channels(True)
                      ).grid(row=0, column=0, sticky="ew", padx=(0, 2))
        ctk.CTkButton(sel_row, text="None", height=22, width=50,
                      fg_color="#2a3a4a", hover_color="#3a4a5a",
                      command=lambda: self._set_all_channels(False)
                      ).grid(row=0, column=1, sticky="ew", padx=(2, 0))

        self._ch_scroll = ctk.CTkScrollableFrame(right, fg_color="transparent",
                                                  corner_radius=0)
        self._ch_scroll.grid(row=2, column=0, sticky="nsew", padx=4, pady=(0, 6))
        self._ch_scroll.grid_columnconfigure(0, weight=1)

    # ── project folder ───────────────────────────────────────────────────────

    def set_project_dir(self, project_dir: str) -> None:
        """Called by main window when global project path changes."""
        if project_dir:
            self._set_project(Path(project_dir))

    def _set_project(self, path: Path):
        settings_py = path / "settings.py"
        if not settings_py.exists():
            self.status_callback(
                "Results: No settings.py found. Use: python -m bioscout --init <folder>",
                "warning")
        self._project_root = path
        self._clear_all()
        self._populate_participants()

    def _sims_dir(self) -> Optional[Path]:
        if not self._project_root:
            return None
        p = self._project_root / "simulations"
        return p if p.exists() else None

    # ── cascading dropdowns ──────────────────────────────────────────────────

    def _populate_participants(self):
        sims = self._sims_dir()
        if not sims:
            self._part_menu.configure(values=["—"])
            self._part_var.set("—")
            return
        parts = sorted(p.name for p in sims.iterdir() if p.is_dir())
        opts = parts if parts else ["—"]
        self._part_menu.configure(values=opts)
        self._part_var.set(opts[0])

    def _on_part_changed(self, *_):
        part = self._part_var.get()
        sims = self._sims_dir()
        if not sims or part == "—":
            self._sess_menu.configure(values=["—"])
            self._sess_var.set("—")
            return
        part_dir = sims / part
        sessions = sorted(p.name for p in part_dir.iterdir() if p.is_dir())
        opts = sessions if sessions else ["—"]
        self._sess_menu.configure(values=opts)
        self._sess_var.set(opts[0])

    def _on_sess_changed(self, *_):
        part = self._part_var.get()
        sess = self._sess_var.get()
        sims = self._sims_dir()
        if not sims or part == "—" or sess == "—":
            self._trial_menu.configure(values=["—"])
            self._trial_var.set("—")
            return
        sess_dir = sims / part / sess
        trials = _layout_trials(sess_dir)
        opts = trials if trials else ["—"]
        self._trial_menu.configure(values=opts)
        self._trial_var.set(opts[0])

    def _on_trial_changed(self, *_):
        part  = self._part_var.get()
        sess  = self._sess_var.get()
        trial = self._trial_var.get()
        sims  = self._sims_dir()
        if not sims or "—" in (part, sess, trial):
            self._tree = {}
            for m, v in ((self._source_menu, self._source_var),
                         (self._group_menu, self._group_var),
                         (self._file_menu, self._file_var)):
                m.configure(values=["—"])
                v.set("—")
            return
        # {source: {group: {display name: path}}} — built once per trial, then
        # the two dropdowns just index into it.
        self._tree = {}
        for label, d in _layout_trial_sources(sims / part / sess, trial):
            for f in sorted(d.rglob("*")):
                if not f.is_file() or f.suffix.lower() not in self._DATA_EXTS:
                    continue
                rel = f.relative_to(d).as_posix()
                g = group_of(rel)
                # Show the leaf name; the source and group are already chosen
                # above, so repeating them in every row is noise. CEINMS keeps
                # its execution-parameter folder, which distinguishes runs.
                name = rel if g == "CEINMS" else Path(rel).name
                self._tree.setdefault(label, {}).setdefault(g, {})[name] = f
        sources = list(self._tree) or ["—"]
        self._source_menu.configure(values=sources)
        self._source_var.set(sources[0])
        self._on_source_changed()

    def _on_source_changed(self, *_):
        groups = sort_groups(self._tree.get(self._source_var.get(), {}))
        self._group_menu.configure(values=groups or ["—"])
        self._group_var.set((groups or ["—"])[0])
        self._on_group_changed()

    def _on_group_changed(self, *_):
        files = self._tree.get(self._source_var.get(), {}).get(
            self._group_var.get(), {})
        self._file_map = dict(files)
        opts = sorted(self._file_map) or ["—"]
        self._file_menu.configure(values=opts)
        self._file_var.set(opts[0])

    # ── colour picker ────────────────────────────────────────────────────────

    # ------------------------------------------------------------- filtering
    def _on_filter_kind(self):
        kind = self._filter_var.get()
        notes = {
            "none": "",
            "butterworth low-pass":
                "zero-lag (filtfilt): no phase shift, effective order 2x",
            "moving average":
                "simple, but shifts and blunts peaks",
            "savitzky-golay":
                "preserves peak height and width",
        }
        self._cut_lbl.configure(
            text="window (samples)" if kind in ("moving average", "savitzky-golay")
            else "cutoff (Hz)")
        self._filter_note.configure(text=notes.get(kind, ""))
        self._refresh_plot()

    def _filter_params(self):
        try:
            cut = float(self._cut_var.get())
        except (ValueError, AttributeError):
            cut = 6.0
        try:
            order = int(float(self._ord_var.get()))
        except (ValueError, AttributeError):
            order = 4
        kind = getattr(self, "_filter_var", None)
        return (kind.get() if kind else "none"), cut, order

    @staticmethod
    def _fs_from_x(x):
        """Sampling rate from the time column; 100 Hz when it cannot be read."""
        try:
            dt = float(np.median(np.diff(np.asarray(x, float))))
            if dt > 0:
                return 1.0 / dt
        except Exception:
            pass
        return 100.0

    def _apply_filter(self, y, x):
        kind, cut, order = self._filter_params()
        if kind == "none":
            return y
        return apply_filter(y, kind, cut, order, self._fs_from_x(x))

    def _save_filtered(self):
        """Write every loaded series, filtered, to one CSV."""
        kind, cut, order = self._filter_params()
        if kind == "none":
            self.status_callback("Filter is 'none' — nothing to save", "warning")
            return
        if not self._series:
            self.status_callback("No series loaded", "warning")
            return
        try:
            from tkinter.filedialog import asksaveasfilename
            out = asksaveasfilename(parent=self, defaultextension=".csv",
                                    filetypes=[("CSV", "*.csv")],
                                    initialfile="filtered.csv")
        except Exception:
            out = None
        if not out:
            return
        import csv
        try:
            with open(out, "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                # Parameters go IN the file: the filename alone does not say
                # what was done, and a filtered CSV that cannot be reproduced
                # is not a result.
                w.writerow([f"# filter={kind}", f"cutoff={cut}", f"order={order}"])
                for srs in self._series:
                    df = srs["df"]
                    cols = list(df.columns)
                    x = df[cols[0]].values
                    w.writerow([f"# series: {srs['label']}"])
                    w.writerow(cols)
                    filtered = [x] + [
                        self._apply_filter(df[c].values.astype(float), x)
                        for c in cols[1:]
                    ]
                    for i in range(len(df)):
                        w.writerow([col[i] for col in filtered])
                    w.writerow([])
            self.status_callback(f"Saved filtered data to {out}", "success")
        except Exception as exc:
            self.status_callback(f"{type(exc).__name__}: {exc}", "error")

    def _pick_colour(self):
        try:
            from tkinter.colorchooser import askcolor
            result = askcolor(color=self._cur_colour, title="Pick line colour", parent=self)
            if result and result[1]:
                self._cur_colour = result[1]
                self._colour_btn.configure(fg_color=self._cur_colour,
                                           hover_color=self._cur_colour)
        except Exception:
            # cycle through palette
            self._colour_idx = (self._colour_idx + 1) % len(_PALETTE)
            self._cur_colour = _PALETTE[self._colour_idx]
            self._colour_btn.configure(fg_color=self._cur_colour,
                                       hover_color=self._cur_colour)

    # ── add / remove series ──────────────────────────────────────────────────

    def _add_series(self):
        sims  = self._sims_dir()
        part  = self._part_var.get()
        sess  = self._sess_var.get()
        trial = self._trial_var.get()
        fname = self._file_var.get()

        if not sims or "—" in (part, sess, trial, fname):
            self.status_callback("Select participant / session / trial / file first", "warning")
            return

        file_path = self._file_map.get(fname) or (sims / part / sess / trial / fname)
        if not file_path.exists():
            self.status_callback(f"File not found: {file_path}", "error")
            return

        # The source belongs in the legend: two series from the same
        # trial and different models would otherwise read identically.
        label = (f"{part} / {sess} / {trial} / "
                 f"{self._source_var.get()} / {fname}")

        # Don't add duplicates
        if any(s["label"] == label for s in self._series):
            self.status_callback("Already added", "warning")
            return

        colour = self._cur_colour
        # Advance colour suggestion for next add
        self._colour_idx = (self._colour_idx + 1) % len(_PALETTE)
        self._cur_colour = _PALETTE[self._colour_idx]
        self._colour_btn.configure(fg_color=self._cur_colour,
                                   hover_color=self._cur_colour)

        # Load data in background
        self.status_callback(f"Loading {fname}…", "info")

        def _load():
            df = _load_file(file_path)
            self.after(0, lambda: self._on_series_loaded(label, file_path, colour, df))

        threading.Thread(target=_load, daemon=True).start()

    def _on_series_loaded(self, label, file_path, colour, df):
        if df is None or df.empty:
            self.status_callback(f"Could not load {file_path.name}", "error")
            return

        series = {"label": label, "file": file_path, "colour": colour, "df": df}
        self._series.append(series)

        # Update channel union. Only the FIRST series to arrive gets a channel
        # ticked for it — a second series added to compare against the first
        # must not disturb whatever is currently plotted.
        new_cols = [c for c in df.columns if c not in self._ch_vars]
        nothing_plotted = not any(v.get() for v in self._ch_vars.values())
        auto = default_channel(df.columns) if nothing_plotted else None
        self._add_channel_rows(new_cols, auto_select=auto)

        self._rebuild_series_list()
        n_new = len(new_cols)
        if auto:
            self.status_callback(
                f"Added: {label} — plotting '{auto}'; "
                f"{max(n_new - 1, 0)} more channels loaded, tick to add",
                "success")
        else:
            self.status_callback(f"Added: {label} ({n_new} new channels)", "success")
        self._refresh_plot()

    def _rebuild_series_list(self):
        for w in self._series_frame.winfo_children():
            w.destroy()
        for i, s in enumerate(self._series):
            row = ctk.CTkFrame(self._series_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            row.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(row, text="■", text_color=s["colour"],
                         font=("Segoe UI", 12)).grid(row=0, column=0, padx=(2, 4))
            ctk.CTkLabel(row, text=s["label"], font=("Segoe UI", 11),
                         anchor="w", wraplength=160).grid(row=0, column=1, sticky="ew")
            idx = i
            ctk.CTkButton(row, text="✕", width=20, height=20,
                          fg_color="#553333", hover_color="#774444",
                          font=("Segoe UI", 11),
                          command=lambda i=idx: self._remove_series(i)
                          ).grid(row=0, column=2, padx=(2, 0))

    def _remove_series(self, idx: int):
        if 0 <= idx < len(self._series):
            self._series.pop(idx)
            self._rebuild_series_list()
            self._rebuild_channels()
            self._refresh_plot()

    # ── channel panel ────────────────────────────────────────────────────────

    def _add_channel_rows(self, cols: list[str], auto_select: Optional[str] = None):
        """Add tick-boxes for *cols*, ticking only *auto_select* (if given)."""
        for col in cols:
            var = ctk.BooleanVar(value=(col == auto_select))
            self._ch_vars[col] = var
            ctk.CTkCheckBox(
                self._ch_scroll, text=col,
                variable=var,
                font=("Segoe UI", 11),
                command=self._refresh_plot,
            ).pack(anchor="w", padx=4, pady=1)
        self._channels = list(self._ch_vars.keys())

    def _rebuild_channels(self):
        """Recompute channel union from remaining series."""
        # Keep only vars for columns still present in at least one series
        live_cols: set[str] = set()
        for s in self._series:
            live_cols.update(s["df"].columns)

        # Remove stale
        for col in list(self._ch_vars.keys()):
            if col not in live_cols:
                del self._ch_vars[col]

        # Rebuild widget list
        for w in self._ch_scroll.winfo_children():
            w.destroy()
        for col in list(self._ch_vars.keys()):
            ctk.CTkCheckBox(
                self._ch_scroll, text=col,
                variable=self._ch_vars[col],
                font=("Segoe UI", 11),
                command=self._refresh_plot,
            ).pack(anchor="w", padx=4, pady=1)
        self._channels = list(self._ch_vars.keys())

    def _set_all_channels(self, state: bool):
        """All / None. 'All' skips time columns — a time-vs-time subplot is
        never what anyone wanted, and it cost a panel in a 126-channel grid.
        The tick-box stays, so it can still be selected by hand."""
        for col, var in self._ch_vars.items():
            var.set(state and not is_time_column(col))
        self._refresh_plot()

    # ── plotting ─────────────────────────────────────────────────────────────

    def _refresh_plot(self):
        if not HAS_MPL:
            self.status_callback("matplotlib not installed", "error")
            return
        if not self._series:
            self._clear_plot()
            return

        selected = [c for c, v in self._ch_vars.items() if v.get()]
        if not selected:
            self._clear_plot()
            return

        threading.Thread(target=self._render_plot, args=(selected,), daemon=True).start()

    def _style_axes(self, ax):
        ax.set_facecolor("#1a1a28")
        ax.tick_params(colors="#888888", labelsize=7)
        for spine in ax.spines.values():
            spine.set_edgecolor("#333344")
        ax.grid(True, color="#222233", linewidth=0.5)

    def _series_x(self, df, normalise: bool):
        """x values for one series' dataframe."""
        if normalise:
            return np.linspace(0, 100, len(df))
        first_vals = df[df.columns[0]].values
        # First column is time in every format we parse — but only trust it if
        # it actually increases, otherwise fall back to sample index.
        if len(first_vals) > 1 and first_vals[-1] > first_vals[0]:
            return first_vals
        return np.arange(len(df))

    def _render_plot(self, channels: list[str]):
        try:
            if self._single_var.get():
                fig, note = self._render_single(channels)
            else:
                fig, note = self._render_grid(channels)
            self._fig = fig
            self.after(0, lambda: self._display_figure(fig))
            if note:
                self.after(0, lambda: self.status_callback(note, "warning"))
        except Exception as e:
            logger.error(f"Render error: {e}")
            self.status_callback(f"Plot error: {e}", "error")

    # -- one subplot per channel -------------------------------------------- #
    def _render_grid(self, channels: list[str]):
        normalise = self._norm_var.get()
        note = ""
        if len(channels) > MAX_GRID_SUBPLOTS:
            # Say what was dropped. A silently truncated grid reads as "these
            # are all the channels", which is exactly the wrong impression.
            note = (f"{len(channels)} channels ticked — showing the first "
                    f"{MAX_GRID_SUBPLOTS}. Use 'Single plot (overlay channels)' "
                    f"to see them all on one axes.")
            channels = channels[:MAX_GRID_SUBPLOTS]

        n_ch = len(channels)
        n_cols = min(4, n_ch)
        n_rows = (n_ch + n_cols - 1) // n_cols
        fig_w = max(10, n_cols * 3.5)
        fig_h = max(5, n_rows * 2.8)

        fig = Figure(figsize=(fig_w, fig_h), dpi=96, facecolor="#111118")
        fig.subplots_adjust(hspace=0.45, wspace=0.35,
                            left=0.07, right=0.97, top=0.93, bottom=0.08)

        axes: list = []
        for i, ch in enumerate(channels):
            ax = fig.add_subplot(n_rows, n_cols, i + 1)
            self._style_axes(ax)
            ax.set_title(ch, fontsize=8, color="#cccccc", pad=3)
            axes.append((ch, ax))

        for s in self._series:
            df = _time_normalise(s["df"]) if normalise else s["df"]
            x = self._series_x(df, normalise)
            for ch, ax in axes:
                if ch not in df.columns:
                    continue
                try:
                    y = self._apply_filter(df[ch].values.astype(float), x)
                    ax.plot(x, y, linewidth=1.2, color=s["colour"],
                            alpha=0.85, label=s["label"].split(" / ")[0])
                except Exception:
                    pass

        xlabel = "% cycle" if normalise else "time (s)"
        for _, ax in axes:
            ax.set_xlabel(xlabel, fontsize=7, color="#888888")

        if len(self._series) > 1 and axes:
            handles, labels = axes[0][1].get_legend_handles_labels()
            if handles:
                axes[0][1].legend(handles, labels, fontsize=6, loc="best",
                                  facecolor="#1e1e2e", labelcolor="#cccccc",
                                  edgecolor="#333344")
        return fig, note

    # -- everything on one axes --------------------------------------------- #
    def _render_single(self, channels: list[str]):
        """All selected channels overlaid on one axes.

        Colour identifies the CHANNEL here and line style the series, which is
        the opposite of the grid — there, every subplot is one channel already,
        so colour is free to mean series. Keeping colour=series in overlay mode
        would draw every channel of a series in one colour, i.e. an
        indistinguishable bundle.
        """
        normalise = self._norm_var.get()
        multi_series = len(self._series) > 1

        fig = Figure(figsize=(12, 6.5), dpi=96, facecolor="#111118")
        fig.subplots_adjust(left=0.08, right=0.98, top=0.92, bottom=0.11)
        ax = fig.add_subplot(1, 1, 1)
        self._style_axes(ax)
        ax.tick_params(labelsize=9)

        colours = {ch: _PALETTE[i % len(_PALETTE)] for i, ch in enumerate(channels)}
        n_lines = 0
        for si, s in enumerate(self._series):
            df = _time_normalise(s["df"]) if normalise else s["df"]
            x = self._series_x(df, normalise)
            style = _SERIES_STYLES[si % len(_SERIES_STYLES)]
            for ch in channels:
                if ch not in df.columns:
                    continue
                try:
                    y = self._apply_filter(df[ch].values.astype(float), x)
                except Exception:
                    continue
                label = f"{ch} — {s['label'].split(' / ')[0]}" if multi_series else ch
                ax.plot(x, y, linewidth=1.3, color=colours[ch], alpha=0.9,
                        linestyle=style, label=label)
                n_lines += 1

        ax.set_xlabel("% cycle" if normalise else "time (s)",
                      fontsize=9, color="#999999")
        ax.set_ylabel("value", fontsize=9, color="#999999")

        note = ""
        if 0 < n_lines <= MAX_LEGEND_ENTRIES:
            ax.legend(fontsize=7, loc="best", ncol=max(1, n_lines // 12 + 1),
                      facecolor="#1e1e2e", labelcolor="#cccccc",
                      edgecolor="#333344")
            ax.set_title(f"{len(channels)} channel(s)", fontsize=10,
                         color="#cccccc", pad=6)
        else:
            ax.set_title(f"{n_lines} lines — legend hidden above "
                         f"{MAX_LEGEND_ENTRIES}", fontsize=10,
                         color="#cccccc", pad=6)
            if n_lines:
                note = (f"{n_lines} lines on one axes; legend hidden. "
                        f"Y axis mixes units unless the channels share them.")
        return fig, note

    def _display_figure(self, fig: Figure):
        # Remove old canvas
        for w in self._plot_frame.winfo_children():
            w.destroy()

        self._plot_frame.grid_rowconfigure(0, weight=1)
        self._plot_frame.grid_rowconfigure(1, weight=0)
        self._plot_frame.grid_columnconfigure(0, weight=1)

        canvas = FigureCanvasTkAgg(fig, master=self._plot_frame)
        canvas.draw()
        canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self._canvas_widget = canvas

        try:
            tb = NavigationToolbar2Tk(canvas, self._plot_frame)
            tb.update()
            tb.grid(row=1, column=0, sticky="ew")
            self._toolbar = tb
        except Exception:
            pass

        n = sum(1 for v in self._ch_vars.values() if v.get())
        self.status_callback(f"Plotted {n} channel(s) × {len(self._series)} series", "success")

    def _clear_plot(self):
        for w in self._plot_frame.winfo_children():
            w.destroy()
        self._plot_placeholder = ctk.CTkLabel(
            self._plot_frame,
            text="Add a series and select channels to plot",
            text_color="#555555", font=("Segoe UI", 12))
        self._plot_placeholder.grid(row=0, column=0)
        self._fig = None
        self._canvas_widget = None
        self._toolbar = None

    def _clear_all(self):
        self._series.clear()
        for w in self._series_frame.winfo_children():
            w.destroy()
        for w in self._ch_scroll.winfo_children():
            w.destroy()
        self._ch_vars.clear()
        self._channels.clear()
        self._clear_plot()

    # ── save ────────────────────────────────────────────────────────────────

    def _save_figure(self):
        if self._fig is None:
            self.status_callback("No plot to save", "warning")
            return
        from tkinter.filedialog import asksaveasfilename
        path = asksaveasfilename(
            title="Save Figure",
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("PDF", "*.pdf"), ("SVG", "*.svg")],
            parent=self)
        if path:
            self._fig.savefig(path, dpi=200, bbox_inches="tight",
                              facecolor=self._fig.get_facecolor())
            self.status_callback(f"Saved → {Path(path).name}", "success")
