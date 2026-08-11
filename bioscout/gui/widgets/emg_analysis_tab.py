"""EMG Analysis tab — frequency content and muscle synergies, on chosen channels.

A viewer over ``bioscout.utils.emg_analysis``; the maths lives there so it can
be scripted and tested without a display.

* **Frequency** — power spectrum per channel, mains band shaded red, sub-20 Hz
  amber, median frequency dashed. A channel is flagged when too much power sits
  in either. Run this before CEINMS: contamination survives normalisation and
  then distorts every excitation.
* **Synergies** — NMF on the linear envelopes: the VAF-against-count curve, the
  weights, and the activation profiles. The curve is shown because VAF rises
  with count by construction, so a count on its own says very little.

Channel selection matters more than it looks. A raw ``emg.mot`` carries the
force-plate voltages and unused inputs alongside the muscles, and feeding those
to NMF factorises the force plates together with the EMG — the synergies come
out meaningless. The default selection is therefore muscle-looking channels
that actually vary, and the rest have to be ticked on deliberately.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import customtkinter as ctk
from .. import simulations_root as _simulations_root

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import numpy as np
    HAS_MPL = True
except Exception:                                    # pragma: no cover
    HAS_MPL = False

_EMG_FILES = ("emg_filtered_normalised.mot", "emg_filtered.mot", "emg.mot")

#: Substrings that mark a column as not-a-muscle. Force-plate voltages and
#: spare inputs live in the same file as the EMG and must not reach NMF.
_NON_MUSCLE = ("voltage", "not_used", "notused", "force", "moment", "fx", "fy",
               "fz", "mx", "my", "mz", "cop", "sync", "trigger")


def _looks_like_muscle(name: str) -> bool:
    low = name.lower()
    return not any(tok in low for tok in _NON_MUSCLE)


class EMGAnalysisTab(ctk.CTkFrame):
    def __init__(self, parent, config_manager=None, status_callback=None):
        super().__init__(parent, fg_color="transparent")
        self.config_manager = config_manager
        self.status_callback = status_callback or (lambda *a, **k: None)
        self._project_root: Optional[Path] = None
        self._channels: Dict[str, "np.ndarray"] = {}
        self._file_map: Dict[str, Path] = {}
        self._chan_vars: Dict[str, ctk.BooleanVar] = {}
        self._fs = 1000.0
        self._build()

    # ------------------------------------------------------------- layout
    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        bar = ctk.CTkFrame(self, fg_color="#161620", corner_radius=8)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 4))
        for c in (1, 3, 5, 7):
            bar.grid_columnconfigure(c, weight=1)

        def combo(col, label):
            ctk.CTkLabel(bar, text=label, font=("Segoe UI", 11, "bold"),
                         text_color="#aaaaaa").grid(row=0, column=col,
                                                    padx=(10, 4), pady=8, sticky="e")
            var = ctk.StringVar(value="—")
            m = ctk.CTkOptionMenu(bar, variable=var, values=["—"], height=28,
                                  font=("Segoe UI", 12))
            m.grid(row=0, column=col + 1, padx=(0, 8), pady=8, sticky="ew")
            return var, m

        self._subj_var, self._subj_menu = combo(0, "Subject")
        self._sess_var, self._sess_menu = combo(2, "Session")
        self._trial_var, self._trial_menu = combo(4, "Trial")
        self._file_var, self._file_menu = combo(6, "File")
        self._subj_var.trace_add("write", lambda *_: self._on_subject())
        self._sess_var.trace_add("write", lambda *_: self._on_session())
        self._trial_var.trace_add("write", lambda *_: self._on_trial())
        self._file_var.trace_add("write", lambda *_: self._on_file())

        # ---- plot holder --------------------------------------------------
        holder = ctk.CTkFrame(self, fg_color="#12121a", corner_radius=8)
        holder.grid(row=1, column=0, sticky="nsew", padx=(8, 4), pady=(0, 4))
        holder.grid_rowconfigure(0, weight=1)
        holder.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        if HAS_MPL:
            self._fig = Figure(figsize=(9, 5), dpi=100, facecolor="#12121a")
            # NOT self._canvas: CTkFrame uses that attribute for its own drawing
            # surface, and shadowing it made every redraw raise
            # "'FigureCanvasTkAgg' object has no attribute 'winfo_exists'".
            self._mpl_canvas = FigureCanvasTkAgg(self._fig, master=holder)
            self._mpl_canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        else:
            self._mpl_canvas = None
            ctk.CTkLabel(holder, text="matplotlib not available",
                         font=("Segoe UI", 13)).grid(row=0, column=0)

        # ---- channel selector --------------------------------------------
        side = ctk.CTkFrame(self, fg_color="#161620", corner_radius=8, width=230)
        side.grid(row=1, column=1, sticky="nsew", padx=(0, 8), pady=(0, 4))
        side.grid_rowconfigure(2, weight=1)
        side.grid_propagate(False)
        ctk.CTkLabel(side, text="Channels", font=("Segoe UI", 12, "bold"),
                     text_color="#dddddd").grid(row=0, column=0, sticky="w",
                                                padx=10, pady=(10, 2))
        btns = ctk.CTkFrame(side, fg_color="transparent")
        btns.grid(row=1, column=0, sticky="ew", padx=8)
        for txt, fn in (("All", lambda: self._set_all(True)),
                        ("None", lambda: self._set_all(False)),
                        ("Muscles", self._select_muscles)):
            ctk.CTkButton(btns, text=txt, width=64, height=24,
                          font=("Segoe UI", 11), command=fn).pack(side="left", padx=2)
        self._chan_frame = ctk.CTkScrollableFrame(side, fg_color="transparent")
        self._chan_frame.grid(row=2, column=0, sticky="nsew", padx=6, pady=6)

        # ---- actions ------------------------------------------------------
        act = ctk.CTkFrame(self, fg_color="transparent")
        act.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))
        ctk.CTkButton(act, text="Frequency", width=140, height=30,
                      font=("Segoe UI", 12),
                      command=self._run_frequency).pack(side="left", padx=4)
        ctk.CTkButton(act, text="Synergies (NMF)", width=160, height=30,
                      font=("Segoe UI", 12),
                      command=self._run_synergies).pack(side="left", padx=4)
        ctk.CTkLabel(act, text="VAF target", font=("Segoe UI", 11)).pack(
            side="left", padx=(16, 4))
        self._vaf_var = ctk.StringVar(value="0.90")
        ctk.CTkEntry(act, textvariable=self._vaf_var, width=60,
                     font=("Segoe UI", 12)).pack(side="left")
        self._msg = ctk.CTkLabel(act, text="", font=("Segoe UI", 11),
                                 text_color="#aaaaaa", anchor="w")
        self._msg.pack(side="left", padx=16, fill="x", expand=True)

    # ---------------------------------------------------------- selection
    def set_project_dir(self, project_dir: str) -> None:
        if project_dir:
            self._project_root = Path(project_dir)
            sims = self._sims()
            opts = sorted(p.name for p in sims.iterdir() if p.is_dir()) if sims else []
            self._subj_menu.configure(values=opts or ["—"])
            self._subj_var.set((opts or ["—"])[0])

    def _sims(self) -> Optional[Path]:
        if not self._project_root:
            return None
        p = _simulations_root(self._project_root,
                              getattr(self, 'config_manager', None))
        return p if p.is_dir() else None

    def _on_subject(self, *_):
        sims, s = self._sims(), self._subj_var.get()
        opts = sorted(p.name for p in (sims / s).iterdir() if p.is_dir()) \
            if sims and s != "—" else []
        self._sess_menu.configure(values=opts or ["—"])
        self._sess_var.set((opts or ["—"])[0])

    def _session_dir(self) -> Optional[Path]:
        sims = self._sims()
        s, ss = self._subj_var.get(), self._sess_var.get()
        if not sims or "—" in (s, ss):
            return None
        d = sims / s / ss
        return d if d.is_dir() else None

    def _on_session(self, *_):
        d = self._session_dir()
        opts = []
        if d:
            try:
                from bioscout.gui.widgets.results_viewer import _layout_trials
                opts = _layout_trials(d)
            except Exception:
                pass
        self._trial_menu.configure(values=opts or ["—"])
        self._trial_var.set((opts or ["—"])[0])

    def _on_trial(self, *_):
        d, trial = self._session_dir(), self._trial_var.get()
        self._file_map = {}
        if d and trial != "—":
            try:
                from bioscout.utils import session_layout as L
                exp = Path(L.experimental_root(str(d))) / trial
                for name in _EMG_FILES:
                    f = exp / name
                    if f.is_file():
                        self._file_map[name] = f
            except Exception:
                pass
        opts = list(self._file_map) or ["—"]
        self._file_menu.configure(values=opts)
        self._file_var.set(opts[0])

    def _on_file(self, *_):
        """Load on selection so the channel list is populated before a run."""
        if self._load():
            self._build_channel_list()

    # ------------------------------------------------------------ loading
    def _load(self) -> bool:
        from bioscout.utils.emg_analysis import read_emg_mot
        f = self._file_map.get(self._file_var.get())
        if not f:
            return False
        try:
            time, chans = read_emg_mot(f)
        except Exception as exc:
            self._msg.configure(text=f"{type(exc).__name__}: {exc}")
            return False
        if len(time) < 2:
            self._msg.configure(text="file has fewer than 2 samples")
            return False
        dt = float(np.median(np.diff(time)))
        self._fs = 1.0 / dt if dt > 0 else 1000.0
        self._channels = chans
        return True

    def _build_channel_list(self):
        for w in self._chan_frame.winfo_children():
            w.destroy()
        self._chan_vars = {}
        for i, name in enumerate(self._channels):
            sig = self._channels[name]
            flat = not np.any(np.isfinite(sig)) or float(np.nanstd(sig)) <= 0
            v = ctk.BooleanVar(value=_looks_like_muscle(name) and not flat)
            self._chan_vars[name] = v
            ctk.CTkCheckBox(self._chan_frame,
                            text=name + ("  (flat)" if flat else ""),
                            variable=v, font=("Segoe UI", 11),
                            checkbox_width=16, checkbox_height=16).grid(
                row=i, column=0, sticky="w", pady=1)
        n_on = sum(v.get() for v in self._chan_vars.values())
        self._msg.configure(text=f"{len(self._channels)} channels @ {self._fs:.0f} Hz "
                                 f"— {n_on} selected (muscle-looking, non-flat)")

    def _set_all(self, on: bool):
        for v in self._chan_vars.values():
            v.set(on)

    def _select_muscles(self):
        for n, v in self._chan_vars.items():
            sig = self._channels.get(n)
            flat = sig is None or float(np.nanstd(sig)) <= 0
            v.set(_looks_like_muscle(n) and not flat)

    def _selected(self) -> Dict[str, "np.ndarray"]:
        return {n: self._channels[n] for n, v in self._chan_vars.items()
                if v.get() and n in self._channels}

    def _axes(self, n):
        self._fig.clear()
        ncol = min(4, max(1, n))
        nrow = int(np.ceil(n / ncol))
        axes = self._fig.subplots(nrow, ncol, squeeze=False)
        return axes.ravel()

    def _style(self):
        for ax in self._fig.get_axes():
            ax.set_facecolor("#12121a")
            ax.tick_params(colors="#aaaaaa", labelsize=7)
            for sp in ax.spines.values():
                sp.set_color("#444444")

    # ---------------------------------------------------------- analyses
    def _run_frequency(self):
        if not HAS_MPL or not self._channels:
            self._msg.configure(text="load a file first")
            return
        sel = self._selected()
        if not sel:
            self._msg.configure(text="no channel selected")
            return
        from bioscout.utils.emg_analysis import frequency_report
        rep = frequency_report(sel, self._fs)
        if not rep:
            self._msg.configure(text="no channel produced a spectrum")
            return
        axes = self._axes(len(rep))
        bad = []
        for ax, (name, r) in zip(axes, sorted(rep.items())):
            ax.semilogy(r.freqs, np.maximum(r.power, 1e-20), lw=0.9, color="#4da3ff")
            ax.axvspan(48, 62, color="#ff5555", alpha=0.18)
            ax.axvspan(0, 20, color="#ffaa00", alpha=0.12)
            ax.axvline(r.median_hz, color="#ffffff", lw=0.8, ls="--")
            flag = ("  MAINS" if r.mains_flag else "") + \
                   ("  ARTEFACT" if r.artefact_flag else "")
            if flag:
                bad.append(name)
            ax.set_title(f"{name}   med {r.median_hz:.0f} Hz{flag}", fontsize=8,
                         color="#ff8888" if flag else "#dddddd")
            ax.set_xlim(0, min(500, self._fs / 2))
        for ax in axes[len(rep):]:
            ax.axis("off")
        self._fig.suptitle("EMG power spectra — red = mains, amber = below the "
                           "EMG band, dashed = median frequency",
                           color="#cccccc", fontsize=9)
        self._style()
        self._fig.tight_layout(rect=(0, 0, 1, 0.95))
        self._mpl_canvas.draw()
        self._msg.configure(text=f"{len(rep)} channels; "
                                 f"flagged: {', '.join(bad) if bad else 'none'}")

    def _run_synergies(self):
        if not HAS_MPL or not self._channels:
            self._msg.configure(text="load a file first")
            return
        sel = self._selected()
        # NMF needs at least 2 channels to have anything to factorise, and a
        # flat channel makes the normalisation step divide by zero.
        sel = {n: s for n, s in sel.items() if float(np.nanstd(s)) > 0}
        if len(sel) < 2:
            self._msg.configure(text="select at least 2 non-flat channels")
            return
        from bioscout.utils.emg_analysis import synergy_report
        try:
            target = float(self._vaf_var.get())
        except ValueError:
            target = 0.90
        try:
            rep = synergy_report(sel, self._fs, vaf_target=target)
        except Exception as exc:
            self._msg.configure(text=f"{type(exc).__name__}: {exc}")
            return
        best, curve = rep["best"], rep["curve"]
        if best is None:
            self._msg.configure(text="synergy extraction produced nothing")
            return

        self._fig.clear()
        ncol = max(2, best.n_synergies)
        gs = self._fig.add_gridspec(2, ncol)
        ax0 = self._fig.add_subplot(gs[0, 0])
        ax0.plot([r.n_synergies for r in curve], [r.vaf for r in curve], "o-",
                 color="#4da3ff")
        ax0.axhline(target, color="#ff5555", ls="--", lw=0.8)
        ax0.set_title(f"VAF vs count — chose {rep['n_chosen']}", fontsize=9,
                      color="#dddddd")
        ax0.set_xlabel("synergies", fontsize=8)
        ax0.set_ylabel("VAF", fontsize=8)

        ax1 = self._fig.add_subplot(gs[0, 1:])
        w, x = best.weights, np.arange(len(best.channels))
        width = 0.8 / max(1, best.n_synergies)
        for k in range(best.n_synergies):
            ax1.bar(x + k * width, w[:, k], width, label=f"S{k + 1}")
        ax1.set_xticks(x + 0.4 - width / 2)
        ax1.set_xticklabels(best.channels, rotation=60, ha="right", fontsize=7)
        ax1.set_title("synergy weights — which muscles group together",
                      fontsize=9, color="#dddddd")
        ax1.legend(fontsize=7, frameon=False)

        for k in range(best.n_synergies):
            ax = self._fig.add_subplot(gs[1, k])
            ax.plot(best.activations[k], lw=1.0, color="#4da3ff")
            ax.set_title(f"S{k + 1} activation", fontsize=8, color="#dddddd")

        self._style()
        self._fig.tight_layout()
        self._mpl_canvas.draw()
        self._msg.configure(
            text=f"{rep['n_chosen']} synergies reach VAF {best.vaf:.3f} "
                 f"(target {target:.2f}) over {len(sel)} channels; seed fixed at 0")
