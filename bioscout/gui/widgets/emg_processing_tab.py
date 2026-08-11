"""EMG Processing tab — filter, normalise and inspect a session's EMG.

Was "EMG Normalization", which described one step of what it does. The tab now
owns the whole chain, each step independently switchable:

    band-pass → notch → rectify → envelope low-pass → amplitude normalise

Normalisation stays SESSION-level and that is deliberate: an MVC reference
computed from one trial is not an MVC. The left list picks which trials the
reference spans; the right list picks which trials are drawn. The two are
separate because the trials you normalise *against* (a maximal effort) are
usually not the trials you want to *look at*.

Input/output are named per trial rather than as absolute paths, for the same
reason: the tab operates on every ticked trial at once. Picking an input file
sets the name used in each trial folder, and the output name follows it as
``<stem>_processed<ext>`` so the source file is never overwritten.

The plot panel mirrors the Results viewer: channels are ticked individually,
only the first non-time channel is on by default, and they can be drawn on one
axes or split into subplots. A frequency-spectrum view is available for
choosing filter cut-offs — that is what a band-pass setting should be argued
from, rather than a default nobody has looked behind.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Dict, List, Optional

import customtkinter as ctk
from tkinter import filedialog
from .. import simulations_root as _simulations_root

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    from matplotlib.figure import Figure
    import numpy as np
    HAS_MPL = True
except Exception:                                       # pragma: no cover
    HAS_MPL = False

try:
    import pandas as pd
    HAS_PD = True
except Exception:                                       # pragma: no cover
    HAS_PD = False

DEFAULT_EMG_NAME = "emg.mot"
MAX_GRID_SUBPLOTS = 36
MAX_LEGEND_ENTRIES = 24
_PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
            "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
            "#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5"]


def processed_name(input_name: str, suffix: str = "_processed") -> str:
    """``emg.mot`` -> ``emg_processed.mot`` — extension preserved.

    Never returns the input name, so a mis-set suffix cannot make the tab
    overwrite the raw recording.
    """
    p = Path(str(input_name).strip() or DEFAULT_EMG_NAME)
    stem, ext = p.stem, p.suffix
    if stem.endswith(suffix):
        return p.name
    return f"{stem}{suffix}{ext}"


def _layout():
    from bioscout.utils import session_layout as _L
    return _L


def write_table(df, path) -> None:
    """Write *df* in the format the OUTPUT extension asks for.

    The output name is user-editable, so it can end in ``.csv`` — writing an
    OpenSim .sto header into a file called .csv would produce something neither
    pandas nor OpenSim reads. ``.sto``/``.mot`` go through bioscout's writer
    when it is importable, and fall back to an inline header otherwise, so a
    broken import cannot lose a whole processing run.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".csv":
        df.to_csv(path, index=False)
        return
    try:
        from bioscout.utils.emg_normalise import write_sto_file
        write_sto_file(df, str(path))
        return
    except Exception:
        pass
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{path.name}\nversion=1\nnRows={len(df)}\n"
                f"nColumns={len(df.columns)}\ninDegrees=no\nendheader\n")
        f.write("\t".join(str(c) for c in df.columns) + "\n")
        for row in df.itertuples(index=False):
            f.write("\t".join(f"{v:.8f}" if isinstance(v, float) else str(v)
                              for v in row) + "\n")


def _defaults() -> dict:
    """Filter defaults from settings.py, falling back to standard sEMG values."""
    d = dict(bp_low=20.0, bp_high=450.0, bp_order=4,
             notch=50.0, env_low=6.0, env_order=4)
    try:
        import settings as S
        B = getattr(S, "BatchSettings", None)
        if B is not None:
            d["bp_low"] = float(getattr(B, "emg_bandpass_low_hz", d["bp_low"]))
            hi = getattr(B, "emg_bandpass_high_hz", d["bp_high"])
            d["bp_high"] = float(hi) if hi else d["bp_high"]
            d["bp_order"] = int(getattr(B, "emg_bandpass_order", d["bp_order"]))
            d["env_low"] = float(getattr(B, "emg_envelope_lowpass_hz", d["env_low"]))
            d["env_order"] = int(getattr(B, "emg_envelope_order", d["env_order"]))
            d["notch"] = float(getattr(B, "emg_notch_default", d["notch"]) or d["notch"])
    except Exception:
        pass
    return d


class EMGProcessingTab(ctk.CTkFrame):
    """Session-level EMG filtering, normalisation and inspection."""

    def __init__(self, parent, config_manager=None, status_callback=None):
        super().__init__(parent, fg_color="transparent")
        self.config_manager = config_manager
        self.status_callback = status_callback or (lambda *a, **k: None)
        self._project_root: Optional[Path] = None
        self._session_dir: Optional[Path] = None
        self._ref_vars: Dict[str, ctk.BooleanVar] = {}      # trials in the MVC reference
        self._plot_vars: Dict[str, ctk.BooleanVar] = {}     # trials drawn
        self._ch_vars: Dict[str, ctk.BooleanVar] = {}
        self._loaded: Dict[str, "pd.DataFrame"] = {}
        self._fig = None
        self._running = False
        self._d = _defaults()
        self._build()

    # ------------------------------------------------------------- layout
    def _build(self):
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(self, fg_color="#161620", corner_radius=8)
        head.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        head.grid_columnconfigure(3, weight=1)
        ctk.CTkLabel(head, text="EMG Processing",
                     font=("Segoe UI", 14, "bold")).grid(row=0, column=0,
                                                         padx=12, pady=8, sticky="w")
        self._sess_label = ctk.CTkLabel(head, text="Session: not set",
                                        font=("Segoe UI", 11), text_color="#e5b567")
        self._sess_label.grid(row=0, column=1, padx=8, sticky="w")

        # -- input / output naming ---------------------------------------- #
        io = ctk.CTkFrame(self, fg_color="#161620", corner_radius=8)
        io.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 4))
        io.grid_columnconfigure(1, weight=1)
        io.grid_columnconfigure(4, weight=1)

        ctk.CTkLabel(io, text="input EMG", font=("Segoe UI", 11),
                     text_color="#aaaaaa").grid(row=0, column=0, padx=(12, 6),
                                                pady=8, sticky="w")
        self._in_var = ctk.StringVar(value=DEFAULT_EMG_NAME)
        ctk.CTkEntry(io, textvariable=self._in_var, height=28,
                     font=("Consolas", 11)).grid(row=0, column=1, sticky="ew")
        ctk.CTkButton(io, text="…", width=30, height=28, command=self._browse_input
                      ).grid(row=0, column=2, padx=(4, 12))
        ctk.CTkLabel(io, text="output", font=("Segoe UI", 11),
                     text_color="#aaaaaa").grid(row=0, column=3, padx=(0, 6),
                                                sticky="e")
        self._out_var = ctk.StringVar(value=processed_name(DEFAULT_EMG_NAME))
        ctk.CTkEntry(io, textvariable=self._out_var, height=28,
                     font=("Consolas", 11)).grid(row=0, column=4, sticky="ew",
                                                 padx=(0, 12))
        # Output tracks input until the user types their own; after that it is
        # left alone, so a deliberate name is never clobbered by a re-pick.
        self._out_touched = False
        self._out_var.trace_add("write", lambda *_: self._note_out_edit())
        self._in_var.trace_add("write", lambda *_: self._sync_out())

        ctk.CTkLabel(io, text="(names inside each trial folder — the raw file is "
                              "never overwritten)",
                     font=("Segoe UI", 10), text_color="#777777"
                     ).grid(row=1, column=0, columnspan=5, sticky="w",
                            padx=12, pady=(0, 8))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 8))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, minsize=190)
        body.grid_columnconfigure(1, minsize=250)
        body.grid_columnconfigure(2, weight=1)
        body.grid_columnconfigure(3, minsize=180)

        self._build_trials(body)
        self._build_settings(body)
        self._build_plot(body)
        self._build_channels(body)

    # -- left: the two trial lists ----------------------------------------- #
    def _build_trials(self, parent):
        col = ctk.CTkFrame(parent, fg_color="#12121a", corner_radius=8)
        col.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        col.grid_rowconfigure(1, weight=1)
        col.grid_rowconfigure(3, weight=1)
        col.grid_columnconfigure(0, weight=1)

        self._ref_frame = self._trial_list(
            col, 0, "Trials in normalisation",
            "the MVC reference spans these", self._ref_vars)
        self._plot_frame_list = self._trial_list(
            col, 2, "Trials to plot", "drawn in the panel on the right",
            self._plot_vars)

    def _trial_list(self, parent, row, title, hint, store):
        ctk.CTkLabel(parent, text=title, font=("Segoe UI", 11, "bold")).grid(
            row=row, column=0, sticky="w", padx=10, pady=(8, 0))
        ctk.CTkLabel(parent, text=hint, font=("Segoe UI", 9),
                     text_color="#777777").grid(row=row, column=0, sticky="w",
                                                padx=10, pady=(20, 0))
        bar = ctk.CTkFrame(parent, fg_color="transparent")
        bar.grid(row=row, column=0, sticky="e", padx=8, pady=(6, 0))
        ctk.CTkButton(bar, text="All", width=42, height=20, font=("Segoe UI", 10),
                      fg_color="#2a3a4a", hover_color="#3a4a5a",
                      command=lambda s=store: self._set_all(s, True)
                      ).grid(row=0, column=0, padx=2)
        ctk.CTkButton(bar, text="None", width=48, height=20, font=("Segoe UI", 10),
                      fg_color="#2a3a4a", hover_color="#3a4a5a",
                      command=lambda s=store: self._set_all(s, False)
                      ).grid(row=0, column=1, padx=2)
        f = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        f.grid(row=row + 1, column=0, sticky="nsew", padx=6, pady=(4, 6))
        f.grid_columnconfigure(0, weight=1)
        return f

    # -- middle: the processing chain -------------------------------------- #
    def _build_settings(self, parent):
        col = ctk.CTkScrollableFrame(parent, fg_color="#12121a", corner_radius=8)
        col.grid(row=0, column=1, sticky="nsew", padx=(0, 6))
        col.grid_columnconfigure(0, weight=1)
        d = self._d
        r = 0

        ctk.CTkLabel(col, text="Processing chain",
                     font=("Segoe UI", 12, "bold")).grid(row=r, column=0,
                                                         sticky="w", padx=10,
                                                         pady=(8, 2))
        r += 1

        self._do_bp = ctk.BooleanVar(value=True)
        r = self._step(col, r, self._do_bp, "Band-pass", [
            ("low (Hz)", "_bp_low", d["bp_low"]),
            ("high (Hz)", "_bp_high", d["bp_high"]),
            ("order", "_bp_order", d["bp_order"])])

        self._do_notch = ctk.BooleanVar(value=False)
        r = self._step(col, r, self._do_notch, "Notch (mains hum)", [
            ("freq (Hz)", "_notch_hz", d["notch"]),
            ("quality Q", "_notch_q", 30)])

        self._do_rect = ctk.BooleanVar(value=True)
        r = self._step(col, r, self._do_rect, "Rectify", [])

        self._do_env = ctk.BooleanVar(value=True)
        r = self._step(col, r, self._do_env, "Envelope (low-pass)", [
            ("cutoff (Hz)", "_env_low", d["env_low"]),
            ("order", "_env_order", d["env_order"])])

        self._do_norm = ctk.BooleanVar(value=True)
        r = self._step(col, r, self._do_norm, "Amplitude normalise", [])
        meth = ctk.CTkFrame(col, fg_color="transparent")
        meth.grid(row=r, column=0, sticky="ew", padx=26, pady=(0, 4))
        r += 1
        self._norm_method = ctk.StringVar(value="max")
        for i, (lbl, val) in enumerate([("Max", "max"),
                                        ("Window average", "window")]):
            ctk.CTkRadioButton(meth, text=lbl, variable=self._norm_method,
                               value=val, font=("Segoe UI", 10),
                               command=self._sync_window_box
                               ).grid(row=0, column=i, sticky="w", padx=(0, 12))
        self._win_row = ctk.CTkFrame(col, fg_color="transparent")
        self._win_row.grid(row=r, column=0, sticky="ew", padx=26, pady=(0, 6))
        r += 1
        ctk.CTkLabel(self._win_row, text="window (ms)",
                     font=("Segoe UI", 10)).grid(row=0, column=0, padx=(0, 6))
        self._win_ms = ctk.StringVar(value="200")
        ctk.CTkEntry(self._win_row, textvariable=self._win_ms, width=70,
                     height=24, font=("Consolas", 11)).grid(row=0, column=1)
        self._sync_window_box()

        self._apply_btn = ctk.CTkButton(col, text="▶  Apply to ticked trials",
                                        height=32, font=("Segoe UI", 12),
                                        fg_color="#28a745", hover_color="#218838",
                                        command=self._apply)
        self._apply_btn.grid(row=r, column=0, sticky="ew", padx=10, pady=(10, 4))
        r += 1
        self._status = ctk.CTkLabel(col, text="Ready", font=("Segoe UI", 10),
                                    text_color="#8a8a8a", anchor="w",
                                    justify="left", wraplength=220)
        self._status.grid(row=r, column=0, sticky="ew", padx=10, pady=(0, 10))

    def _step(self, parent, row, var, title, fields):
        ctk.CTkCheckBox(parent, text=title, variable=var, font=("Segoe UI", 11),
                        command=self._refresh_plot).grid(row=row, column=0,
                                                         sticky="w", padx=10,
                                                         pady=(8, 2))
        row += 1
        if not fields:
            return row
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.grid(row=row, column=0, sticky="ew", padx=26, pady=(0, 2))
        for i, (label, attr, default) in enumerate(fields):
            ctk.CTkLabel(box, text=label, font=("Segoe UI", 10),
                         text_color="#999999").grid(row=i // 2, column=(i % 2) * 2,
                                                    sticky="w", padx=(0, 4), pady=1)
            v = ctk.StringVar(value=str(default))
            setattr(self, attr, v)
            ctk.CTkEntry(box, textvariable=v, width=64, height=24,
                         font=("Consolas", 11)).grid(row=i // 2,
                                                     column=(i % 2) * 2 + 1,
                                                     sticky="w", padx=(0, 10),
                                                     pady=1)
        return row + 1

    def _sync_window_box(self):
        try:
            if self._norm_method.get() == "window":
                self._win_row.grid()
            else:
                self._win_row.grid_remove()
        except Exception:
            pass

    # -- plot -------------------------------------------------------------- #
    def _build_plot(self, parent):
        col = ctk.CTkFrame(parent, fg_color="#12121a", corner_radius=8)
        col.grid(row=0, column=2, sticky="nsew", padx=(0, 6))
        col.grid_rowconfigure(1, weight=1)
        col.grid_columnconfigure(0, weight=1)

        bar = ctk.CTkFrame(col, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        bar.grid_columnconfigure(3, weight=1)
        self._view = ctk.CTkSegmentedButton(
            bar, values=["Signal", "Spectrum"], command=lambda _v: self._refresh_plot(),
            font=("Segoe UI", 11))
        self._view.set("Signal")
        self._view.grid(row=0, column=0, sticky="w")
        self._split_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(bar, text="split into subplots", variable=self._split_var,
                        font=("Segoe UI", 10), command=self._refresh_plot
                        ).grid(row=0, column=1, padx=(10, 0))
        self._raw_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(bar, text="show raw behind", variable=self._raw_var,
                        font=("Segoe UI", 10), command=self._refresh_plot
                        ).grid(row=0, column=2, padx=(10, 0))
        ctk.CTkButton(bar, text="↻ Preview", width=90, height=26,
                      font=("Segoe UI", 11), command=self._refresh_plot
                      ).grid(row=0, column=4, padx=(6, 0))

        self._plot_frame = ctk.CTkFrame(col, fg_color="#111118")
        self._plot_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self._plot_frame.grid_rowconfigure(0, weight=1)
        self._plot_frame.grid_columnconfigure(0, weight=1)
        self._placeholder = ctk.CTkLabel(
            self._plot_frame,
            text="Tick a trial under 'Trials to plot' and press Preview.",
            text_color="#555555", font=("Segoe UI", 12))
        self._placeholder.grid(row=0, column=0)

    # -- channels ---------------------------------------------------------- #
    def _build_channels(self, parent):
        col = ctk.CTkFrame(parent, fg_color="#161620", corner_radius=8)
        col.grid(row=0, column=3, sticky="nsew")
        col.grid_rowconfigure(2, weight=1)
        col.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(col, text="Channels", font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(8, 2))
        bar = ctk.CTkFrame(col, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 4))
        bar.grid_columnconfigure(0, weight=1)
        bar.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(bar, text="All", height=22, fg_color="#2a3a4a",
                      hover_color="#3a4a5a",
                      command=lambda: self._set_all_channels(True)
                      ).grid(row=0, column=0, sticky="ew", padx=(0, 2))
        ctk.CTkButton(bar, text="None", height=22, fg_color="#2a3a4a",
                      hover_color="#3a4a5a",
                      command=lambda: self._set_all_channels(False)
                      ).grid(row=0, column=1, sticky="ew", padx=(2, 0))
        self._ch_scroll = ctk.CTkScrollableFrame(col, fg_color="transparent")
        self._ch_scroll.grid(row=2, column=0, sticky="nsew", padx=4, pady=(0, 6))
        self._ch_scroll.grid_columnconfigure(0, weight=1)

    # ------------------------------------------------------------- wiring
    def set_project_dir(self, project_dir: str) -> None:
        if project_dir:
            self._project_root = Path(project_dir)
            self._autopick_session()

    def set_session_dir(self, session_dir: str) -> None:
        if session_dir:
            self._session_dir = Path(session_dir)
            self._scan_trials()

    def _autopick_session(self):
        """Use the first session under simulations/ so the tab is never blank."""
        sims = _simulations_root(self._project_root,
                                 getattr(self, 'config_manager', None))
        if not sims or not sims.is_dir():
            return
        for subj in sorted(p for p in sims.iterdir() if p.is_dir()):
            for sess in sorted(p for p in subj.iterdir() if p.is_dir()):
                self._session_dir = sess
                self._scan_trials()
                return

    def _trial_dirs(self) -> List[Path]:
        if not self._session_dir:
            return []
        try:
            exp = Path(_layout().experimental_root(str(self._session_dir)))
        except Exception:
            return []
        if not exp.is_dir():
            return []
        return sorted(p for p in exp.iterdir() if p.is_dir())

    def _scan_trials(self):
        for f in (self._ref_frame, self._plot_frame_list):
            for w in f.winfo_children():
                w.destroy()
        self._ref_vars.clear()
        self._plot_vars.clear()

        dirs = self._trial_dirs()
        name = self._in_var.get().strip() or DEFAULT_EMG_NAME
        withemg = [d for d in dirs if (d / name).is_file()]
        self._sess_label.configure(
            text=(f"Session: {self._session_dir.name}  ·  "
                  f"{len(withemg)}/{len(dirs)} trials have {name}")
            if self._session_dir else "Session: not set",
            text_color="#4cc46a" if withemg else "#e5b567")

        for d in dirs:
            has = (d / name).is_file()
            # Reference defaults to every trial that HAS an EMG file: the MVC
            # should span the session unless you say otherwise.
            rv = ctk.BooleanVar(value=has)
            self._ref_vars[d.name] = rv
            ctk.CTkCheckBox(self._ref_frame, text=d.name, variable=rv,
                            font=("Segoe UI", 10),
                            state="normal" if has else "disabled"
                            ).pack(anchor="w", padx=4, pady=1)
            # Plotting defaults to the FIRST such trial only — drawing 14 trials
            # x 16 channels on open is the thing that made this tab feel stuck.
            first = has and not any(v.get() for v in self._plot_vars.values())
            pv = ctk.BooleanVar(value=first)
            self._plot_vars[d.name] = pv
            ctk.CTkCheckBox(self._plot_frame_list, text=d.name, variable=pv,
                            font=("Segoe UI", 10),
                            state="normal" if has else "disabled",
                            command=self._on_plot_trials_changed
                            ).pack(anchor="w", padx=4, pady=1)
        self._loaded.clear()
        self._rebuild_channels()

    def _set_all(self, store, state: bool):
        for v in store.values():
            v.set(state)
        if store is self._plot_vars:
            self._on_plot_trials_changed()

    def _browse_input(self):
        start = self._session_dir or self._project_root or Path(".")
        p = filedialog.askopenfilename(title="Pick an EMG file",
                                       initialdir=str(start),
                                       filetypes=[("EMG", "*.mot *.sto *.csv"),
                                                  ("All files", "*.*")])
        if p:
            # Only the NAME is kept: the tab runs over every ticked trial, so an
            # absolute path would silently pin it to one of them.
            self._in_var.set(Path(p).name)

    def _note_out_edit(self):
        if getattr(self, "_syncing", False):
            return
        self._out_touched = True

    def _sync_out(self):
        if not self._out_touched:
            self._syncing = True
            try:
                self._out_var.set(processed_name(self._in_var.get()))
            finally:
                self._syncing = False
        self._scan_trials()

    # ------------------------------------------------------------ channels
    def _on_plot_trials_changed(self):
        self._loaded.clear()
        self._rebuild_channels()

    def _plot_trials(self) -> List[str]:
        return [t for t, v in self._plot_vars.items() if v.get()]

    def _load(self, trial: str):
        if trial in self._loaded:
            return self._loaded[trial]
        try:
            exp = Path(_layout().experimental_root(str(self._session_dir)))
            from bioscout.gui.widgets.results_viewer import _load_file
            df = _load_file(exp / trial / (self._in_var.get().strip()
                                           or DEFAULT_EMG_NAME))
        except Exception:
            df = None
        self._loaded[trial] = df
        return df

    def _rebuild_channels(self):
        for w in self._ch_scroll.winfo_children():
            w.destroy()
        prev = {c: v.get() for c, v in self._ch_vars.items()}
        self._ch_vars.clear()

        cols: List[str] = []
        for t in self._plot_trials():
            df = self._load(t)
            if df is not None:
                for c in df.columns:
                    if c not in cols:
                        cols.append(c)
        if not cols:
            return
        try:
            from bioscout.gui.widgets.results_viewer import default_channel, is_time_column
        except Exception:
            def is_time_column(n): return str(n).strip().lower().startswith("time")
            def default_channel(cs): return next((c for c in cs if not is_time_column(c)), None)

        auto = default_channel(cols)
        for c in cols:
            v = ctk.BooleanVar(value=prev.get(c, c == auto))
            self._ch_vars[c] = v
            ctk.CTkCheckBox(self._ch_scroll, text=c, variable=v,
                            font=("Segoe UI", 10), command=self._refresh_plot
                            ).pack(anchor="w", padx=4, pady=1)

    def _set_all_channels(self, state: bool):
        try:
            from bioscout.gui.widgets.results_viewer import is_time_column
        except Exception:
            def is_time_column(n): return str(n).strip().lower().startswith("time")
        for c, v in self._ch_vars.items():
            v.set(state and not is_time_column(c))
        self._refresh_plot()

    # ------------------------------------------------------------ processing
    def _f(self, var, default):
        try:
            return float(getattr(self, var).get())
        except (AttributeError, TypeError, ValueError):
            return default

    def _i(self, var, default):
        try:
            return int(float(getattr(self, var).get()))
        except (AttributeError, TypeError, ValueError):
            return default

    def chain_summary(self) -> str:
        bits = []
        if self._do_bp.get():
            bits.append(f"band-pass {self._f('_bp_low', 20):g}–"
                        f"{self._f('_bp_high', 450):g} Hz "
                        f"(order {self._i('_bp_order', 4)})")
        if self._do_notch.get():
            bits.append(f"notch {self._f('_notch_hz', 50):g} Hz")
        if self._do_rect.get():
            bits.append("rectify")
        if self._do_env.get():
            bits.append(f"envelope {self._f('_env_low', 6):g} Hz")
        if self._do_norm.get():
            m = self._norm_method.get()
            bits.append("normalise to session max" if m == "max"
                        else f"normalise to {self._win_ms.get()} ms window average")
        return " → ".join(bits) or "(no steps selected)"

    def _process(self, df, fs: float):
        """Apply the ticked chain to every non-time column. Returns a new frame."""
        import numpy as _np
        from scipy import signal as _sig
        out = df.copy()
        try:
            from bioscout.gui.widgets.results_viewer import is_time_column
        except Exception:
            def is_time_column(n): return str(n).strip().lower().startswith("time")
        nyq = fs / 2.0
        cols = [c for c in df.columns if not is_time_column(c)]
        for c in cols:
            y = df[c].values.astype(float)
            if self._do_bp.get():
                lo = max(self._f("_bp_low", 20.0), 0.01) / nyq
                hi = min(self._f("_bp_high", 450.0) / nyq, 0.99)
                if 0 < lo < hi < 1:
                    b, a = _sig.butter(self._i("_bp_order", 4), [lo, hi], btype="band")
                    y = _sig.filtfilt(b, a, y)
            if self._do_notch.get():
                f0 = self._f("_notch_hz", 50.0)
                if 0 < f0 < nyq:
                    b, a = _sig.iirnotch(f0 / nyq, self._f("_notch_q", 30.0))
                    y = _sig.filtfilt(b, a, y)
            if self._do_rect.get():
                y = _np.abs(y)
            if self._do_env.get():
                lp = min(self._f("_env_low", 6.0) / nyq, 0.99)
                if 0 < lp < 1:
                    b, a = _sig.butter(self._i("_env_order", 4), lp, btype="low")
                    y = _sig.filtfilt(b, a, y)
            out[c] = y
        return out

    @staticmethod
    def _fs_of(df) -> float:
        try:
            t = df[df.columns[0]].values.astype(float)
            dt = float(np.median(np.diff(t)))
            return 1.0 / dt if dt > 0 else 1000.0
        except Exception:
            return 1000.0

    def _reference_max(self) -> Dict[str, float]:
        """Per-channel max across every trial ticked for normalisation."""
        ref: Dict[str, float] = {}
        exp = Path(_layout().experimental_root(str(self._session_dir)))
        name = self._in_var.get().strip() or DEFAULT_EMG_NAME
        from bioscout.gui.widgets.results_viewer import _load_file, is_time_column
        for t, v in self._ref_vars.items():
            if not v.get():
                continue
            df = _load_file(exp / t / name)
            if df is None or df.empty:
                continue
            proc = self._process(df, self._fs_of(df))
            for c in proc.columns:
                if is_time_column(c):
                    continue
                try:
                    m = float(np.nanmax(np.abs(proc[c].values.astype(float))))
                except Exception:
                    continue
                if np.isfinite(m):
                    ref[c] = max(ref.get(c, 0.0), m)
        return ref

    # ---------------------------------------------------------------- apply
    def _apply(self):
        if self._running:
            return
        if not self._session_dir:
            self.status_callback("No session selected", "warning")
            return
        ref_trials = [t for t, v in self._ref_vars.items() if v.get()]
        if self._do_norm.get() and not ref_trials:
            self._set_status("Normalisation is on but no trials are ticked for "
                             "the reference — tick at least one.", "#e06c75")
            return
        self._running = True
        self._apply_btn.configure(state="disabled", text="working…")
        self._set_status(f"{self.chain_summary()}\nreference: "
                         f"{len(ref_trials)} trial(s)", "#8a8a8a")

        def work():
            err, written = None, []
            try:
                exp = Path(_layout().experimental_root(str(self._session_dir)))
                name = self._in_var.get().strip() or DEFAULT_EMG_NAME
                out_name = self._out_var.get().strip() or processed_name(name)
                from bioscout.gui.widgets.results_viewer import _load_file, is_time_column
                ref = self._reference_max() if self._do_norm.get() else {}
                win = None
                if self._do_norm.get() and self._norm_method.get() == "window":
                    win = float(self._win_ms.get() or 200)
                targets = sorted(set(ref_trials) | set(self._plot_trials())) \
                    if self._do_norm.get() else self._plot_trials()
                for t in targets:
                    df = _load_file(exp / t / name)
                    if df is None or df.empty:
                        continue
                    fs = self._fs_of(df)
                    proc = self._process(df, fs)
                    if self._do_norm.get():
                        for c in proc.columns:
                            if is_time_column(c):
                                continue
                            denom = ref.get(c, 0.0)
                            if win:
                                k = max(int(fs * win / 1000.0), 1)
                                y = np.abs(proc[c].values.astype(float))
                                if len(y) >= k:
                                    kern = np.ones(k) / k
                                    denom = float(np.nanmax(np.convolve(y, kern, "valid")))
                            if denom > 0:
                                proc[c] = proc[c].values.astype(float) / denom
                    write_table(proc, exp / t / out_name)
                    written.append(t)
            except Exception:
                import traceback
                err = traceback.format_exc()
            self.after(0, lambda: self._applied(err, written))

        threading.Thread(target=work, daemon=True).start()

    def _applied(self, err, written):
        self._running = False
        self._apply_btn.configure(state="normal", text="▶  Apply to ticked trials")
        if err:
            self._set_status("FAILED\n" + err.strip().splitlines()[-1], "#e06c75")
            self.status_callback("EMG processing failed", "error")
            return
        out = self._out_var.get().strip()
        self._set_status(f"Wrote {out} in {len(written)} trial(s):\n"
                         + ", ".join(written), "#4cc46a")
        self.status_callback(f"EMG processed — {len(written)} trial(s)", "success")
        self._loaded.clear()
        self._refresh_plot()

    def _set_status(self, text, colour="#8a8a8a"):
        try:
            self._status.configure(text=text, text_color=colour)
        except Exception:
            pass

    # ----------------------------------------------------------------- plot
    def _refresh_plot(self, *_):
        if not HAS_MPL or not self._session_dir:
            return
        trials = self._plot_trials()
        channels = [c for c, v in self._ch_vars.items() if v.get()]
        if not trials or not channels:
            self._clear_plot("Tick a trial and a channel to preview.")
            return
        threading.Thread(target=self._render, args=(trials, channels),
                         daemon=True).start()

    def _clear_plot(self, msg):
        for w in self._plot_frame.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._plot_frame, text=msg, text_color="#555555",
                     font=("Segoe UI", 12)).grid(row=0, column=0)

    def _render(self, trials, channels):
        try:
            spectrum = self._view.get() == "Spectrum"
            split = self._split_var.get()
            panels = channels if split else ["all"]
            n = len(panels)
            if n > MAX_GRID_SUBPLOTS:
                panels = panels[:MAX_GRID_SUBPLOTS]
                n = len(panels)
            ncols = min(3, n)
            nrows = (n + ncols - 1) // ncols
            fig = Figure(figsize=(max(8, ncols * 3.6), max(4.5, nrows * 2.6)),
                         dpi=96, facecolor="#111118")
            fig.subplots_adjust(hspace=0.5, wspace=0.3, left=0.09, right=0.98,
                                top=0.91, bottom=0.12)
            axes = []
            for i, p in enumerate(panels):
                ax = fig.add_subplot(nrows, ncols, i + 1)
                ax.set_facecolor("#1a1a28")
                ax.tick_params(colors="#888888", labelsize=7)
                for sp in ax.spines.values():
                    sp.set_edgecolor("#333344")
                ax.grid(True, color="#222233", linewidth=0.5)
                if split:
                    ax.set_title(p, fontsize=8, color="#cccccc", pad=3)
                axes.append(ax)

            styles = ["-", "--", ":", "-."]
            lines = 0
            for ti, t in enumerate(trials):
                df = self._load(t)
                if df is None or df.empty:
                    continue
                fs = self._fs_of(df)
                proc = self._process(df, fs)
                x = df[df.columns[0]].values.astype(float)
                for ci, c in enumerate(channels):
                    if c not in proc.columns:
                        continue
                    ax = axes[channels.index(c)] if split else axes[0]
                    colour = _PALETTE[ci % len(_PALETTE)]
                    y = proc[c].values.astype(float)
                    label = f"{c} — {t}" if len(trials) > 1 else c
                    if spectrum:
                        yy = y - np.mean(y)
                        freq = np.fft.rfftfreq(len(yy), d=1.0 / fs)
                        mag = np.abs(np.fft.rfft(yy)) / max(len(yy), 1)
                        ax.semilogy(freq, np.maximum(mag, 1e-12), linewidth=0.9,
                                    color=colour, linestyle=styles[ti % 4],
                                    label=label)
                    else:
                        if self._raw_var.get():
                            ax.plot(x, df[c].values.astype(float), linewidth=0.6,
                                    color="#555566", alpha=0.7)
                        ax.plot(x, y, linewidth=1.1, color=colour,
                                linestyle=styles[ti % 4], label=label)
                    lines += 1

            for ax in axes:
                if spectrum:
                    ax.set_xlabel("frequency (Hz)", fontsize=7, color="#888888")
                    ax.set_ylabel("magnitude", fontsize=7, color="#888888")
                else:
                    ax.set_xlabel("time (s)", fontsize=7, color="#888888")
            if lines and lines <= MAX_LEGEND_ENTRIES:
                axes[0].legend(fontsize=6, loc="best", facecolor="#1e1e2e",
                               labelcolor="#cccccc", edgecolor="#333344")
            fig.suptitle(self.chain_summary(), fontsize=8, color="#8a8a8a", y=0.99)
            self._fig = fig
            self.after(0, lambda: self._show(fig))
        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            self.after(0, lambda: self._clear_plot(
                f"Plot error: {type(exc).__name__}: {exc}"))
            self.after(0, lambda: self._set_status(tb.strip().splitlines()[-1],
                                                   "#e06c75"))

    def _show(self, fig):
        for w in self._plot_frame.winfo_children():
            w.destroy()
        canvas = FigureCanvasTkAgg(fig, master=self._plot_frame)
        canvas.draw()
        canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        try:
            bar = ctk.CTkFrame(self._plot_frame, fg_color="transparent")
            bar.grid(row=1, column=0, sticky="ew")
            NavigationToolbar2Tk(canvas, bar).update()
        except Exception:
            pass


#: Old name, so anything still importing it keeps working.
EMGNormalizationTab = EMGProcessingTab
