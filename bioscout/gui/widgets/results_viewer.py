"""Results Viewer Tab — multi-subject, multi-trial plot builder.

Layout
------
Left panel  : project folder + cascading dropdowns (participant → session → trial → file)
              + colour picker + "Add to Plot" + series queue + Clear All
Centre      : matplotlib grid of subplots (one per selected channel)
              + NavigationToolbar + Save / Clear buttons
Right panel : channel tick-boxes (union across all loaded series)
              + Select All / None
Bottom bar  : Time Normalise toggle (0-100 %)
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
        left.grid_rowconfigure(6, weight=1)
        left.grid_columnconfigure(0, weight=1)

        row = 0
        def _lbl(text):
            nonlocal row
            ctk.CTkLabel(left, text=text, font=("Segoe UI", 9, "bold"),
                         text_color="#aaaaaa").grid(row=row, column=0,
                         sticky="w", padx=10, pady=(8, 1))
            row += 1

        def _menu(var, values=("—",)):
            nonlocal row
            m = ctk.CTkOptionMenu(left, variable=var, values=list(values),
                                  height=26, font=("Segoe UI", 10))
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

        _lbl("File")
        self._file_var  = ctk.StringVar(value="—")
        self._file_menu = _menu(self._file_var)

        # colour + add button
        colour_row = ctk.CTkFrame(left, fg_color="transparent")
        colour_row.grid(row=row, column=0, sticky="ew", padx=10, pady=(8, 2))
        colour_row.grid_columnconfigure(1, weight=1)
        row += 1
        self._colour_btn = ctk.CTkButton(colour_row, text="■", width=32, height=26,
                                         fg_color=_PALETTE[0], hover_color=_PALETTE[0],
                                         command=self._pick_colour)
        self._colour_btn.grid(row=0, column=0, padx=(0, 4))
        ctk.CTkLabel(colour_row, text="Colour", font=("Segoe UI", 10)).grid(
            row=0, column=1, sticky="w")

        self._cur_colour = _PALETTE[0]

        ctk.CTkButton(left, text="➕  Add to Plot", height=28,
                      fg_color="#28a745", hover_color="#218838",
                      command=self._add_series).grid(row=row, column=0,
                      sticky="ew", padx=10, pady=(4, 6))
        row += 1

        # series list (scrollable)
        ctk.CTkLabel(left, text="Series", font=("Segoe UI", 9, "bold"),
                     text_color="#aaaaaa").grid(row=row, column=0,
                     sticky="w", padx=10, pady=(6, 1))
        row += 1
        self._series_frame = ctk.CTkScrollableFrame(left, fg_color="transparent",
                                                     corner_radius=0)
        self._series_frame.grid(row=row, column=0, sticky="nsew", padx=4, pady=0)
        row += 1

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

        ctk.CTkLabel(right, text="Channels", font=("Segoe UI", 10, "bold")).grid(
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
        trials = sorted(p.name for p in sess_dir.iterdir() if p.is_dir())
        opts = trials if trials else ["—"]
        self._trial_menu.configure(values=opts)
        self._trial_var.set(opts[0])

    def _on_trial_changed(self, *_):
        part  = self._part_var.get()
        sess  = self._sess_var.get()
        trial = self._trial_var.get()
        sims  = self._sims_dir()
        if not sims or "—" in (part, sess, trial):
            self._file_menu.configure(values=["—"])
            self._file_var.set("—")
            return
        trial_dir = sims / part / sess / trial
        files = sorted(f.name for f in trial_dir.iterdir()
                       if f.suffix.lower() in self._DATA_EXTS)
        opts = files if files else ["—"]
        self._file_menu.configure(values=opts)
        self._file_var.set(opts[0])

    # ── colour picker ────────────────────────────────────────────────────────

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

        file_path = sims / part / sess / trial / fname
        if not file_path.exists():
            self.status_callback(f"File not found: {file_path}", "error")
            return

        label = f"{part} / {sess} / {trial} / {fname}"

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

        # Update channel union
        new_cols = [c for c in df.columns if c not in self._ch_vars]
        self._add_channel_rows(new_cols)

        self._rebuild_series_list()
        self.status_callback(f"Added: {label}", "success")
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
            ctk.CTkLabel(row, text=s["label"], font=("Segoe UI", 9),
                         anchor="w", wraplength=160).grid(row=0, column=1, sticky="ew")
            idx = i
            ctk.CTkButton(row, text="✕", width=20, height=20,
                          fg_color="#553333", hover_color="#774444",
                          font=("Segoe UI", 9),
                          command=lambda i=idx: self._remove_series(i)
                          ).grid(row=0, column=2, padx=(2, 0))

    def _remove_series(self, idx: int):
        if 0 <= idx < len(self._series):
            self._series.pop(idx)
            self._rebuild_series_list()
            self._rebuild_channels()
            self._refresh_plot()

    # ── channel panel ────────────────────────────────────────────────────────

    def _add_channel_rows(self, cols: list[str]):
        for col in cols:
            var = ctk.BooleanVar(value=True)
            self._ch_vars[col] = var
            ctk.CTkCheckBox(
                self._ch_scroll, text=col,
                variable=var,
                font=("Segoe UI", 9),
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
                font=("Segoe UI", 9),
                command=self._refresh_plot,
            ).pack(anchor="w", padx=4, pady=1)
        self._channels = list(self._ch_vars.keys())

    def _set_all_channels(self, state: bool):
        for var in self._ch_vars.values():
            var.set(state)
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

    def _render_plot(self, channels: list[str]):
        try:
            normalise = self._norm_var.get()
            n_ch = len(channels)

            # Grid layout: max 4 columns
            n_cols = min(4, n_ch)
            n_rows = (n_ch + n_cols - 1) // n_cols

            fig_w = max(10, n_cols * 3.5)
            fig_h = max(5, n_rows * 2.8)

            fig = Figure(figsize=(fig_w, fig_h), dpi=96,
                         facecolor="#111118")
            fig.subplots_adjust(hspace=0.45, wspace=0.35,
                                left=0.07, right=0.97, top=0.93, bottom=0.08)

            axes: list = []
            for i, ch in enumerate(channels):
                ax = fig.add_subplot(n_rows, n_cols, i + 1)
                ax.set_facecolor("#1a1a28")
                ax.tick_params(colors="#888888", labelsize=7)
                for spine in ax.spines.values():
                    spine.set_edgecolor("#333344")
                ax.grid(True, color="#222233", linewidth=0.5)
                ax.set_title(ch, fontsize=8, color="#cccccc", pad=3)
                axes.append((ch, ax))

            for s in self._series:
                df = _time_normalise(s["df"]) if normalise else s["df"]
                # x axis
                if normalise:
                    x = np.linspace(0, 100, len(df))
                else:
                    # Use first column if it looks like time (values increasing)
                    first_col = df.columns[0]
                    first_vals = df[first_col].values
                    if first_vals[-1] > first_vals[0]:
                        x = first_vals
                    else:
                        x = np.arange(len(df))

                for ch, ax in axes:
                    if ch not in df.columns:
                        continue
                    try:
                        y = df[ch].values.astype(float)
                        ax.plot(x, y, linewidth=1.2, color=s["colour"],
                                alpha=0.85, label=s["label"].split(" / ")[0])
                    except Exception:
                        pass

            if normalise:
                for _, ax in axes:
                    ax.set_xlabel("% cycle", fontsize=7, color="#888888")
            else:
                for _, ax in axes:
                    ax.set_xlabel("time (s)", fontsize=7, color="#888888")

            # Legend in first subplot if multiple series
            if len(self._series) > 1 and axes:
                handles, labels = axes[0][1].get_legend_handles_labels()
                if handles:
                    axes[0][1].legend(handles, labels,
                                      fontsize=6, loc="best",
                                      facecolor="#1e1e2e",
                                      labelcolor="#cccccc",
                                      edgecolor="#333344")

            self._fig = fig
            self.after(0, lambda: self._display_figure(fig))

        except Exception as e:
            logger.error(f"Render error: {e}")
            self.status_callback(f"Plot error: {e}", "error")

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
