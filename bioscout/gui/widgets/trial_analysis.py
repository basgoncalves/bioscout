"""Trial Analysis tab — one trial: configure it, see what a stage will read, re-run it.

The question this tab answers is the one you ask when a session finishes and one
trial looks wrong: *for this trial and this model, what is the analysis actually
going to read, is it all there, where should the trial be cut, and can I re-run
just this one?*

Three panels:

* **Trial settings** — this trial's block from ``session.yaml`` (type, side,
  time_range), editable and saved back in place. That block decides which part
  of the capture every downstream stage sees, so it belongs next to the run
  button rather than three folders away.
* **Inputs / GRF window** (left) — the selected stage's inputs, resolved to real
  paths, editable, each marked present or missing. Switch the view to plot the
  trial's ground reaction and drag out the window to cut on.
* **Run** — re-run one stage for this trial on one iteration.

The left panel used to be a stage-by-iteration grid of ✓counts. It was removed
in 2.0.0b10: a count of files in a folder tells you a stage produced *something*,
not whether it produced the right thing, and it cost the whole panel. Knowing
which file a stage is about to read — and being able to point it somewhere else —
is the thing that actually unblocks a bad trial.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import customtkinter as ctk
from tkinter import filedialog, messagebox
from .. import simulations_root as _simulations_root

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    from matplotlib.widgets import SpanSelector
    import numpy as np
    HAS_MPL = True
except Exception:                                        # pragma: no cover
    HAS_MPL = False

#: Stage key -> (label, Iteration.run kwarg, inputs, outputs).
#:
#: Each input is ``(label, where, relative)`` where *where* is:
#:   ``exp``   — the session's model-INDEPENDENT export (2_experimental/<trial>/)
#:   ``iter``  — this iteration's folder for this trial (3_iterations/<it>/<trial>/)
#:   ``model`` — a key in the iteration's session.yaml block naming an .osim
#:
#: Export and EMG normalisation are deliberately absent: they are session-level,
#: and running them for one trial would skip the session-wide MVC reference.
STAGES_IO: Dict[str, tuple] = {
    "ik": (
        "Inverse Kinematics + ID", "do_exbiomec",
        [("markers (.trc)",          "exp",   "marker_experimental.trc"),
         ("ground reaction (.mot)",  "exp",   "grf.mot"),
         ("external loads (.xml)",   "exp",   "GRF.xml"),
         ("model (.osim)",           "model", "so_model")],
        ["external_biomechanics/joint_angles.mot",
         "external_biomechanics/inverse_dynamics.sto"],
    ),
    "ma": (
        "Muscle Analysis", "do_muscle_analysis",
        [("model (.osim)",           "model", "so_model"),
         ("joint angles (.mot)",     "iter",  "external_biomechanics/joint_angles.mot")],
        ["muscle_analysis/"],
    ),
    "so": (
        "Static Optimisation", "do_so",
        [("model (.osim)",           "model", "so_model"),
         ("joint angles (.mot)",     "iter",  "external_biomechanics/joint_angles.mot"),
         ("ground reaction (.mot)",  "exp",   "grf.mot"),
         ("external loads (.xml)",   "exp",   "GRF.xml")],
        ["static_optimisation/", "joint_contact_forces/"],
    ),
    "ceinms": (
        "CEINMS", "do_ceinms",
        [("CEINMS model (.osim)",    "model", "ceinms_model"),
         ("normalised EMG (.mot)",   "exp",   "emg_filtered_normalised.mot"),
         ("muscle analysis",         "iter",  "muscle_analysis"),
         ("inverse dynamics (.sto)", "iter",  "external_biomechanics/inverse_dynamics.sto")],
        ["ceinms/"],
    ),
}
STAGE_ORDER = ["ik", "ma", "so", "ceinms"]
STAGE_LABELS = [STAGES_IO[k][0] for k in STAGE_ORDER]

#: A new iteration copied from nothing starts from this block.
NEW_ITERATION_TEMPLATE = {
    "generic": "", "ceinms_model": "scaled_opt_N10.osim",
    "so_model": "scaled_opt_N10_mvicx3.00.osim",
    "linear_scaling": True, "marker_placer": True,
    "opt_neval": 10, "mvic_factor": 3.0, "label": "", "color": "black",
    "group": "generic",
}


def _layout():
    from bioscout.utils import session_layout as _L
    return _L


class TrialAnalysisTab(ctk.CTkFrame):
    def __init__(self, parent, config_manager=None, status_callback=None):
        super().__init__(parent, fg_color="transparent")
        self.config_manager = config_manager
        self.status_callback = status_callback or (lambda *a, **k: None)
        self._project_root: Optional[Path] = None
        self._running = False
        self._input_rows: List[tuple] = []     # (label, StringVar, marker widget)
        self._grf_df = None
        self._span = None
        self._build()

    # ------------------------------------------------------------- layout
    def _build(self):
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        pick = ctk.CTkFrame(self, fg_color="#161620", corner_radius=8)
        pick.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        for c in (1, 3, 5):
            pick.grid_columnconfigure(c, weight=1)

        def combo(col, label):
            ctk.CTkLabel(pick, text=label, font=("Segoe UI", 11, "bold"),
                         text_color="#aaaaaa").grid(row=0, column=col,
                                                    padx=(10, 4), pady=8, sticky="e")
            var = ctk.StringVar(value="—")
            m = ctk.CTkOptionMenu(pick, variable=var, values=["—"], height=28,
                                  font=("Segoe UI", 12))
            m.grid(row=0, column=col + 1, padx=(0, 10), pady=8, sticky="ew")
            return var, m

        self._subj_var, self._subj_menu = combo(0, "Subject")
        self._sess_var, self._sess_menu = combo(2, "Session")
        self._trial_var, self._trial_menu = combo(4, "Trial")
        self._subj_var.trace_add("write", lambda *_: self._on_subject())
        self._sess_var.trace_add("write", lambda *_: self._on_session())
        self._trial_var.trace_add("write", lambda *_: self._on_trial())

        ctk.CTkButton(self, text="↻  Refresh", height=28, width=110,
                      font=("Segoe UI", 12),
                      command=self.refresh).grid(row=1, column=0, sticky="e",
                                                 padx=10, pady=(0, 4))

        mid = ctk.CTkFrame(self, fg_color="transparent")
        mid.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 4))
        mid.grid_rowconfigure(0, weight=1)
        mid.grid_columnconfigure(0, weight=3)
        mid.grid_columnconfigure(1, weight=2)

        self._build_left(mid)
        self._build_right(mid)

        self._detail = ctk.CTkTextbox(self, height=130, font=("Consolas", 11))
        self._detail.grid(row=3, column=0, sticky="ew", padx=8, pady=(0, 8))
        self._detail.insert("1.0", "Pick a subject, session and trial.\n")

    # -- left: inputs / GRF window ---------------------------------------- #
    def _build_left(self, parent):
        left = ctk.CTkFrame(parent, fg_color="#12121a", corner_radius=8)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(left, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        head.grid_columnconfigure(1, weight=1)
        self._left_view = ctk.CTkSegmentedButton(
            head, values=["Inputs", "GRF window"], command=self._switch_left,
            font=("Segoe UI", 11))
        self._left_view.set("Inputs")
        self._left_view.grid(row=0, column=0, sticky="w")
        self._left_note = ctk.CTkLabel(head, text="", font=("Segoe UI", 10),
                                       text_color="#8a8a8a", anchor="e")
        self._left_note.grid(row=0, column=1, sticky="ew", padx=8)

        self._stack = ctk.CTkFrame(left, fg_color="transparent")
        self._stack.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 8))
        self._stack.grid_rowconfigure(0, weight=1)
        self._stack.grid_columnconfigure(0, weight=1)

        self._inputs_pane = ctk.CTkScrollableFrame(self._stack, fg_color="transparent")
        self._inputs_pane.grid_columnconfigure(1, weight=1)

        self._grf_pane = ctk.CTkFrame(self._stack, fg_color="transparent")
        self._grf_pane.grid_rowconfigure(0, weight=1)
        self._grf_pane.grid_columnconfigure(0, weight=1)
        self._grf_canvas_frame = ctk.CTkFrame(self._grf_pane, fg_color="#12121a")
        self._grf_canvas_frame.grid(row=0, column=0, sticky="nsew")
        self._grf_canvas_frame.grid_rowconfigure(0, weight=1)
        self._grf_canvas_frame.grid_columnconfigure(0, weight=1)
        # Sliders, because dragging a span is fine for roughing out a window
        # and useless for nudging an edge 20 ms. Each one moves its dashed line
        # live, so the number, the slider and the plot can never disagree.
        sliders = ctk.CTkFrame(self._grf_pane, fg_color="transparent")
        sliders.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        sliders.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(sliders, text="start", font=("Segoe UI", 11),
                     text_color="#4cc46a", width=40, anchor="w").grid(
            row=0, column=0, sticky="w", padx=(2, 6))
        self._t0_slider = ctk.CTkSlider(
            sliders, from_=0.0, to=1.0, number_of_steps=1000,
            progress_color="#2f6f4f", button_color="#4cc46a",
            button_hover_color="#6cd486",
            command=lambda v: self._on_slider("start", v))
        self._t0_slider.grid(row=0, column=1, sticky="ew", pady=2)
        self._t0_read = ctk.CTkLabel(sliders, text="—", font=("Consolas", 11),
                                     width=90, anchor="e")
        self._t0_read.grid(row=0, column=2, sticky="e", padx=(6, 2))

        ctk.CTkLabel(sliders, text="end", font=("Segoe UI", 11),
                     text_color="#e06c75", width=40, anchor="w").grid(
            row=1, column=0, sticky="w", padx=(2, 6))
        self._t1_slider = ctk.CTkSlider(
            sliders, from_=0.0, to=1.0, number_of_steps=1000,
            progress_color="#6f3f3f", button_color="#e06c75",
            button_hover_color="#f08c95",
            command=lambda v: self._on_slider("end", v))
        self._t1_slider.grid(row=1, column=1, sticky="ew", pady=2)
        self._t1_read = ctk.CTkLabel(sliders, text="—", font=("Consolas", 11),
                                     width=90, anchor="e")
        self._t1_read.grid(row=1, column=2, sticky="e", padx=(6, 2))

        grfbar = ctk.CTkFrame(self._grf_pane, fg_color="transparent")
        grfbar.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        grfbar.grid_columnconfigure(3, weight=1)
        ctk.CTkButton(grfbar, text="Use dragged window", width=150, height=26,
                      font=("Segoe UI", 11), command=self._apply_span
                      ).grid(row=0, column=0, padx=(0, 6))
        ctk.CTkButton(grfbar, text="Whole capture", width=110, height=26,
                      font=("Segoe UI", 11), fg_color="#3a3a4a",
                      hover_color="#4a4a5a", command=self._span_full
                      ).grid(row=0, column=1, padx=(0, 6))
        # Save is here as well as in the settings panel: the window is chosen
        # on this plot, and having to look away to commit it is how you end up
        # running a trial on numbers you thought you had saved.
        ctk.CTkButton(grfbar, text="✓ Update session.yaml", width=170, height=26,
                      font=("Segoe UI", 11), fg_color="#28a745",
                      hover_color="#218838", command=self._save_trial_settings
                      ).grid(row=0, column=2, padx=(0, 6))
        self._grf_note = ctk.CTkLabel(grfbar, text="Drag across the plot to pick "
                                                   "a window.",
                                      font=("Segoe UI", 10), text_color="#8a8a8a",
                                      anchor="w")
        self._grf_note.grid(row=0, column=2, sticky="ew")
        self._show_left(self._inputs_pane)

    # -- right: settings + run --------------------------------------------- #
    def _build_right(self, parent):
        right = ctk.CTkFrame(parent, fg_color="#12121a", corner_radius=8)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(9, weight=1)
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right, text="Trial settings  (session.yaml)",
                     font=("Segoe UI", 12, "bold"), text_color="#dddddd").grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 2))

        fields = ctk.CTkFrame(right, fg_color="transparent")
        fields.grid(row=1, column=0, sticky="new", padx=10, pady=(0, 4))
        fields.grid_columnconfigure(1, weight=1)
        fields.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(fields, text="type", font=("Segoe UI", 11)).grid(
            row=0, column=0, sticky="w", padx=(0, 6), pady=3)
        self._type_var = ctk.StringVar(value="")
        ctk.CTkEntry(fields, textvariable=self._type_var, height=26,
                     font=("Segoe UI", 12)).grid(row=0, column=1, sticky="ew", pady=3)

        ctk.CTkLabel(fields, text="side", font=("Segoe UI", 11)).grid(
            row=0, column=2, sticky="w", padx=(10, 6), pady=3)
        self._side_var = ctk.StringVar(value="both")
        ctk.CTkOptionMenu(fields, variable=self._side_var,
                          values=["both", "left", "right"], height=26,
                          font=("Segoe UI", 12)).grid(row=0, column=3,
                                                      sticky="ew", pady=3)

        ctk.CTkLabel(fields, text="time start (s)", font=("Segoe UI", 11)).grid(
            row=1, column=0, sticky="w", padx=(0, 6), pady=3)
        self._t0_var = ctk.StringVar(value="")
        ctk.CTkEntry(fields, textvariable=self._t0_var, height=26,
                     font=("Segoe UI", 12)).grid(row=1, column=1, sticky="ew", pady=3)

        ctk.CTkLabel(fields, text="end (s)", font=("Segoe UI", 11)).grid(
            row=1, column=2, sticky="w", padx=(10, 6), pady=3)
        self._t1_var = ctk.StringVar(value="")
        ctk.CTkEntry(fields, textvariable=self._t1_var, height=26,
                     font=("Segoe UI", 12)).grid(row=1, column=3, sticky="ew", pady=3)

        detect = ctk.CTkFrame(fields, fg_color="transparent")
        detect.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(6, 2))
        detect.grid_columnconfigure(0, weight=1)
        detect.grid_columnconfigure(1, weight=1)
        # Both fill the fields and neither saves: a window you disagree with
        # costs one glance, and Save stays the only thing that writes.
        ctk.CTkButton(detect, text="⤢  Detect from motion", height=26,
                      font=("Segoe UI", 11), fg_color="#2f6f9f",
                      hover_color="#3a86bd", command=self._detect_time_range
                      ).grid(row=0, column=0, sticky="ew", padx=(0, 3))
        ctk.CTkButton(detect, text="⤢  Pick from GRF", height=26,
                      font=("Segoe UI", 11), fg_color="#2f6f9f",
                      hover_color="#3a86bd", command=self._goto_grf
                      ).grid(row=0, column=1, sticky="ew", padx=(3, 0))
        self._detect_note = ctk.CTkLabel(fields, text="", font=("Segoe UI", 10),
                                         text_color="#888888", anchor="w")
        self._detect_note.grid(row=3, column=0, columnspan=4, sticky="ew")

        save_row = ctk.CTkFrame(right, fg_color="transparent")
        save_row.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        save_row.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(save_row, text="Save to session.yaml", height=28,
                      font=("Segoe UI", 12),
                      command=self._save_trial_settings).grid(row=0, column=0,
                                                              sticky="ew")
        ctk.CTkButton(save_row, text="Edit whole file…", height=28, width=120,
                      font=("Segoe UI", 12), fg_color="#3a3a4a",
                      hover_color="#4a4a5a",
                      command=self._open_session_yaml_in_editor).grid(
            row=0, column=1, sticky="e", padx=(6, 0))

        # ---- run panel ----------------------------------------------------
        ctk.CTkLabel(right, text="Run this trial", font=("Segoe UI", 12, "bold"),
                     text_color="#dddddd").grid(row=3, column=0, sticky="w",
                                                padx=10, pady=(6, 2))
        runbar = ctk.CTkFrame(right, fg_color="transparent")
        runbar.grid(row=4, column=0, sticky="ew", padx=10)
        runbar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(runbar, text="Iteration", font=("Segoe UI", 11)).grid(
            row=0, column=0, padx=(0, 6), sticky="w")
        self._iter_var = ctk.StringVar(value="—")
        self._iter_menu = ctk.CTkOptionMenu(runbar, variable=self._iter_var,
                                            values=["—"], height=28,
                                            font=("Segoe UI", 12))
        self._iter_menu.grid(row=0, column=1, sticky="ew")
        ctk.CTkButton(runbar, text="+", width=30, height=28,
                      font=("Segoe UI", 14), command=self._add_iteration
                      ).grid(row=0, column=2, padx=(4, 0))
        ctk.CTkButton(runbar, text="–", width=30, height=28,
                      font=("Segoe UI", 14), fg_color="#553333",
                      hover_color="#774444", command=self._remove_iteration
                      ).grid(row=0, column=3, padx=(3, 0))
        self._iter_var.trace_add("write", lambda *_: self._render_inputs())

        stagebar = ctk.CTkFrame(right, fg_color="transparent")
        stagebar.grid(row=5, column=0, sticky="ew", padx=10, pady=(6, 0))
        stagebar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(stagebar, text="Stage", font=("Segoe UI", 11)).grid(
            row=0, column=0, padx=(0, 6), sticky="w")
        self._stage_var = ctk.StringVar(value=STAGE_LABELS[0])
        ctk.CTkOptionMenu(stagebar, variable=self._stage_var,
                          values=STAGE_LABELS, height=28,
                          font=("Segoe UI", 12)).grid(row=0, column=1, sticky="ew")
        self._stage_var.trace_add("write", lambda *_: self._render_inputs())

        self._replace_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(right, text="overwrite existing", variable=self._replace_var,
                        font=("Segoe UI", 11)).grid(row=6, column=0, sticky="w",
                                                    padx=14, pady=(6, 0))

        self._run_btn = ctk.CTkButton(right, text="▶  Run this stage",
                                      height=32, font=("Segoe UI", 12),
                                      fg_color="#28a745", hover_color="#218838",
                                      command=self._run)
        self._run_btn.grid(row=7, column=0, sticky="ew", padx=10, pady=(6, 4))

        ctk.CTkLabel(right, text="other keys (YAML)", font=("Segoe UI", 10),
                     text_color="#888888").grid(row=8, column=0, sticky="w",
                                                padx=10, pady=(4, 0))
        self._yaml_box = ctk.CTkTextbox(right, font=("Consolas", 12), height=80)
        self._yaml_box.grid(row=9, column=0, sticky="nsew", padx=10, pady=(0, 8))

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
        self._refresh_iterations()

    def _on_trial(self, *_):
        self._load_trial_settings()
        self._render_inputs()
        self._grf_df = None
        if self._left_view.get() == "GRF window":
            self._render_grf()

    def refresh(self, *_):
        self._refresh_iterations()
        self._load_trial_settings()
        self._render_inputs()
        if self._left_view.get() == "GRF window":
            self._grf_df = None
            self._render_grf()

    def _refresh_iterations(self):
        d = self._session_dir()
        iters: List[str] = []
        if d:
            try:
                L = _layout()
                root = Path(L.iterations_root(str(d)))
                if root.is_dir():
                    iters = sorted(p.name for p in root.iterdir()
                                   if p.is_dir() and p.name not in L.NON_ITERATION_DIRS)
            except Exception:
                pass
            for name in self._yaml_iterations():
                if name not in iters:
                    iters.append(name)          # declared but not yet scaled
        self._iter_menu.configure(values=iters or ["—"])
        if self._iter_var.get() not in iters:
            self._iter_var.set((iters or ["—"])[0])

    def _yaml_iterations(self) -> List[str]:
        f = self._session_yaml()
        if not f:
            return []
        try:
            import yaml
            cfg = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            return list((cfg.get("iterations") or {}).keys())
        except Exception:
            return []

    # ------------------------------------------------- stage input editor
    def _stage_key(self) -> str:
        label = self._stage_var.get()
        for k in STAGE_ORDER:
            if STAGES_IO[k][0] == label:
                return k
        return STAGE_ORDER[0]

    def _exp_dir(self) -> Optional[Path]:
        d, trial = self._session_dir(), self._trial_var.get()
        if not d or trial == "—":
            return None
        try:
            return Path(_layout().experimental_root(str(d))) / trial
        except Exception:
            return None

    def _iter_dir(self) -> Optional[Path]:
        d, trial, it = self._session_dir(), self._trial_var.get(), self._iter_var.get()
        if not d or "—" in (trial, it):
            return None
        try:
            return Path(_layout().iteration_path(str(d), it)) / trial
        except Exception:
            return None

    def _model_path(self, key: str) -> Optional[Path]:
        """Resolve ``iterations.<it>.<key>`` to a real .osim under the iteration."""
        d, it = self._session_dir(), self._iter_var.get()
        f = self._session_yaml()
        if not d or it == "—" or not f:
            return None
        try:
            import yaml
            cfg = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            blk = (cfg.get("iterations") or {}).get(it) or {}
            rel = blk.get(key) or blk.get("so_model") or blk.get("model")
            if not rel:
                return None
            return Path(_layout().iteration_path(str(d), it)) / str(rel)
        except Exception:
            return None

    def _resolve_inputs(self) -> List[Tuple[str, Optional[Path]]]:
        key = self._stage_key()
        _label, _kw, inputs, _out = STAGES_IO[key]
        exp, itd = self._exp_dir(), self._iter_dir()
        out = []
        for label, where, rel in inputs:
            if where == "exp":
                p = (exp / rel) if exp else None
            elif where == "iter":
                p = (itd / rel) if itd else None
            else:
                p = self._model_path(rel)
            out.append((label, p))
        return out

    def _render_inputs(self, *_):
        for w in self._inputs_pane.winfo_children():
            w.destroy()
        self._input_rows = []

        trial, it = self._trial_var.get(), self._iter_var.get()
        key = self._stage_key()
        label, _kw, _inp, outputs = STAGES_IO[key]
        if "—" in (trial, it):
            ctk.CTkLabel(self._inputs_pane,
                         text="Pick a trial and an iteration to see what "
                              "this stage will read.",
                         font=("Segoe UI", 11), text_color="#888888"
                         ).grid(row=0, column=0, columnspan=4, sticky="w",
                                padx=8, pady=10)
            self._left_note.configure(text="")
            return

        ctk.CTkLabel(self._inputs_pane,
                     text=f"{label}   ·   {it} / {trial}",
                     font=("Segoe UI", 12, "bold"), text_color="#7fb2e5"
                     ).grid(row=0, column=0, columnspan=4, sticky="w",
                            padx=6, pady=(4, 8))

        row, missing = 1, 0
        for name, path in self._resolve_inputs():
            ctk.CTkLabel(self._inputs_pane, text=name, font=("Segoe UI", 11),
                         anchor="w", width=170).grid(row=row, column=0,
                                                     sticky="w", padx=(6, 6), pady=3)
            var = ctk.StringVar(value=str(path) if path else "")
            ctk.CTkEntry(self._inputs_pane, textvariable=var,
                         font=("Consolas", 10), height=26).grid(
                row=row, column=1, sticky="ew", pady=3)
            exists = bool(path and path.exists())
            if not exists:
                missing += 1
            mark = ctk.CTkLabel(self._inputs_pane, text="✓" if exists else "⚠",
                                font=("Segoe UI", 13, "bold"),
                                text_color="#4cc46a" if exists else "#e5b567",
                                width=20)
            mark.grid(row=row, column=2, padx=4)
            ctk.CTkButton(self._inputs_pane, text="…", width=28, height=24,
                          font=("Segoe UI", 11),
                          command=lambda v=var: self._browse_into(v)
                          ).grid(row=row, column=3, padx=(0, 6))
            self._input_rows.append((name, var, mark))
            row += 1

        ctk.CTkLabel(self._inputs_pane, text="writes", font=("Segoe UI", 10, "bold"),
                     text_color="#8a8a8a").grid(row=row, column=0, sticky="w",
                                                padx=6, pady=(12, 2))
        row += 1
        itd = self._iter_dir()
        for rel in outputs:
            p = (itd / rel) if itd else None
            present = bool(p and p.exists())
            ctk.CTkLabel(self._inputs_pane,
                         text=("✓  " if present else "·  ") + rel,
                         font=("Consolas", 10), anchor="w",
                         text_color="#4cc46a" if present else "#777777"
                         ).grid(row=row, column=0, columnspan=4, sticky="w",
                                padx=14, pady=1)
            row += 1

        self._left_note.configure(
            text="all inputs present" if not missing
            else f"{missing} input(s) missing",
            text_color="#4cc46a" if not missing else "#e5b567")

    def _browse_into(self, var):
        start = Path(var.get()).parent if var.get() else (self._project_root or Path("."))
        p = filedialog.askopenfilename(title="Choose input file",
                                       initialdir=str(start))
        if p:
            var.set(p)
            self.status_callback("Input overridden for this run", "warning")

    def _show_left(self, pane):
        for p in (self._inputs_pane, self._grf_pane):
            p.grid_forget()
        pane.grid(row=0, column=0, sticky="nsew")

    def _switch_left(self, name: str):
        if name == "GRF window":
            self._show_left(self._grf_pane)
            self._render_grf()
        else:
            self._show_left(self._inputs_pane)
            self._render_inputs()

    def _goto_grf(self):
        self._left_view.set("GRF window")
        self._switch_left("GRF window")

    # --------------------------------------------------------- GRF window
    def _render_grf(self):
        for w in self._grf_canvas_frame.winfo_children():
            w.destroy()
        self._span = None
        if not HAS_MPL:
            self._grf_note.configure(text="matplotlib not installed.")
            return
        exp, trial = self._exp_dir(), self._trial_var.get()
        if not exp or trial == "—":
            self._grf_note.configure(text="Pick a trial first.")
            return
        grf = exp / "grf.mot"
        if not grf.is_file():
            self._grf_note.configure(
                text=f"No grf.mot in 2_experimental/{trial} — run Export first.")
            return
        if self._grf_df is None:
            try:
                from bioscout.gui.widgets.results_viewer import _load_file
                self._grf_df = _load_file(grf)
            except Exception as exc:
                self._grf_note.configure(text=f"{type(exc).__name__}: {exc}")
                return
        df = self._grf_df
        if df is None or df.empty:
            self._grf_note.configure(text="grf.mot is empty.")
            return

        t = df[df.columns[0]].values
        # Vertical force per plate is what tells you when the athlete is on it;
        # the horizontal and CoP columns just crowd the picture.
        vy = [c for c in df.columns if c.lower().endswith("vy")] or \
             [c for c in df.columns[1:] if "force" in c.lower()][:6]

        fig = Figure(figsize=(7, 4.2), dpi=96, facecolor="#111118")
        fig.subplots_adjust(left=0.10, right=0.98, top=0.92, bottom=0.14)
        ax = fig.add_subplot(1, 1, 1)
        ax.set_facecolor("#1a1a28")
        ax.tick_params(colors="#888888", labelsize=8)
        for sp in ax.spines.values():
            sp.set_edgecolor("#333344")
        ax.grid(True, color="#222233", linewidth=0.5)
        for c in vy:
            try:
                ax.plot(t, df[c].values.astype(float), linewidth=1.1, label=c)
            except Exception:
                pass
        ax.set_xlabel("time (s)", fontsize=9, color="#999999")
        ax.set_ylabel("vertical force (N)", fontsize=9, color="#999999")
        ax.set_title(f"{trial} — drag to select the window", fontsize=10,
                     color="#cccccc")
        if 0 < len(vy) <= 8:
            ax.legend(fontsize=6, loc="upper right", facecolor="#1e1e2e",
                      labelcolor="#cccccc", edgecolor="#333344")

        # Show the window currently in the fields, so the plot and the numbers
        # never disagree about what is configured. Keep the Line2D handles: a
        # slider then moves them with set_xdata + draw_idle instead of
        # rebuilding the whole figure on every pixel of drag.
        tmin, tmax = float(t[0]), float(t[-1])
        self._grf_tmin, self._grf_tmax = tmin, tmax
        try:
            a = float(self._t0_var.get())
        except (TypeError, ValueError):
            a = tmin
        try:
            b = float(self._t1_var.get())
        except (TypeError, ValueError):
            b = tmax
        a = min(max(a, tmin), tmax)
        b = min(max(b, tmin), tmax)
        self._grf_line0 = ax.axvline(a, color="#4cc46a", linewidth=1.4,
                                     linestyle="--", alpha=0.95)
        self._grf_line1 = ax.axvline(b, color="#e06c75", linewidth=1.4,
                                     linestyle="--", alpha=0.95)
        self._grf_shade = ax.axvspan(a, b, color="#4cc46a", alpha=0.08)

        canvas = FigureCanvasTkAgg(fig, master=self._grf_canvas_frame)
        canvas.draw()
        canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self._grf_canvas, self._grf_ax = canvas, ax
        self._grf_span = None

        # Slider travel is the capture; 1 ms steps unless that needs more than
        # 4000 of them, which is finer than anyone can aim anyway.
        span_s = max(tmax - tmin, 1e-6)
        steps = int(min(max(span_s / 0.001, 50), 4000))
        for sl in (self._t0_slider, self._t1_slider):
            sl.configure(from_=tmin, to=tmax, number_of_steps=steps)
        self._sync_sliders()

        def on_select(a, b):
            self._grf_span = (float(a), float(b))
            self._grf_note.configure(
                text=f"selected {a:.3f} – {b:.3f} s  ({b - a:.2f} s) — "
                     f"press 'Use dragged window'")

        try:
            self._span = SpanSelector(ax, on_select, "horizontal", useblit=False,
                                      props=dict(alpha=0.25, facecolor="#4cc46a"),
                                      interactive=True)
        except TypeError:      # matplotlib < 3.5 spelt it rectprops
            self._span = SpanSelector(ax, on_select, "horizontal", useblit=False,
                                      rectprops=dict(alpha=0.25, facecolor="#4cc46a"))
        self._grf_note.configure(text=f"{len(vy)} vertical force channel(s). "
                                      f"Drag across the plot to pick a window.")

    def _sync_sliders(self):
        """Push the entry values onto the sliders, lines and readouts."""
        if getattr(self, "_slider_busy", False):
            return
        tmin = getattr(self, "_grf_tmin", None)
        if tmin is None:
            return
        tmax = self._grf_tmax
        try:
            a = float(self._t0_var.get())
        except (TypeError, ValueError):
            a = tmin
        try:
            b = float(self._t1_var.get())
        except (TypeError, ValueError):
            b = tmax
        a = min(max(a, tmin), tmax)
        b = min(max(b, tmin), tmax)
        self._slider_busy = True
        try:
            self._t0_slider.set(a)
            self._t1_slider.set(b)
        finally:
            self._slider_busy = False
        self._redraw_window(a, b)

    def _on_slider(self, which: str, value):
        """Move one edge. The other is pushed along rather than crossed."""
        if getattr(self, "_slider_busy", False):
            return
        tmin = getattr(self, "_grf_tmin", None)
        if tmin is None:
            return
        v = float(value)
        try:
            a = float(self._t0_var.get())
        except (TypeError, ValueError):
            a = tmin
        try:
            b = float(self._t1_var.get())
        except (TypeError, ValueError):
            b = self._grf_tmax
        # A zero-length window is not a window; keep at least one slider step
        # between the edges so end is always strictly after start.
        gap = max((self._grf_tmax - tmin) / 1000.0, 1e-3)
        if which == "start":
            a = v
            if b - a < gap:
                b = min(a + gap, self._grf_tmax)
        else:
            b = v
            if b - a < gap:
                a = max(b - gap, tmin)

        self._slider_busy = True
        try:
            self._t0_var.set(f"{a:.3f}")
            self._t1_var.set(f"{b:.3f}")
            self._t0_slider.set(a)
            self._t1_slider.set(b)
        finally:
            self._slider_busy = False
        self._redraw_window(a, b)
        self._detect_note.configure(
            text=f"{b - a:.2f}s selected — press Update session.yaml to keep")

    def _redraw_window(self, a: float, b: float):
        """Move the two dashed lines and the shaded band, cheaply."""
        try:
            self._t0_read.configure(text=f"{a:8.3f} s")
            self._t1_read.configure(text=f"{b:8.3f} s")
        except Exception:
            pass
        line0 = getattr(self, "_grf_line0", None)
        if line0 is None:
            return
        try:
            self._grf_line0.set_xdata([a, a])
            self._grf_line1.set_xdata([b, b])
            shade = getattr(self, "_grf_shade", None)
            if shade is not None:
                # axvspan returns a Rectangle on matplotlib >= 3.10 and a
                # Polygon before it. Rectangle.set_xy takes a 2-tuple corner, so
                # handing it a polygon path raised "too many values to unpack",
                # and because this whole block is defensive the exception was
                # swallowed — the numbers moved and the lines silently did not.
                if hasattr(shade, "set_bounds"):
                    shade.set_bounds(a, 0, b - a, 1)          # Rectangle
                else:
                    shade.set_xy([[a, 0], [a, 1], [b, 1], [b, 0], [a, 0]])
            self._grf_canvas.draw_idle()
        except Exception:
            pass

    def _apply_span(self):
        span = getattr(self, "_grf_span", None)
        if not span:
            self.status_callback("Drag a window on the GRF plot first", "warning")
            return
        a, b = span
        self._t0_var.set(f"{a:.3f}")
        self._t1_var.set(f"{b:.3f}")
        self._sync_sliders()
        self._detect_note.configure(
            text=f"{b - a:.2f}s from the GRF plot — press Update session.yaml "
                 f"to keep")
        self.status_callback(f"Window {a:.3f}–{b:.3f}s — not saved yet", "info")

    def _span_full(self):
        if self._grf_df is None or self._grf_df.empty:
            return
        t = self._grf_df[self._grf_df.columns[0]].values
        self._t0_var.set(f"{float(t[0]):.3f}")
        self._t1_var.set(f"{float(t[-1]):.3f}")
        self._sync_sliders()
        self._detect_note.configure(text="Whole capture — press Update "
                                         "session.yaml to keep")

    # -------------------------------------------------- trial settings I/O
    def _session_yaml(self) -> Optional[Path]:
        d = self._session_dir()
        if not d:
            return None
        f = d / "session.yaml"
        return f if f.is_file() else None

    def _load_trial_settings(self):
        self._yaml_box.delete("1.0", "end")
        f, trial = self._session_yaml(), self._trial_var.get()
        if not f or trial == "—":
            self._yaml_box.insert("1.0", "(no session.yaml)")
            return
        try:
            import yaml
            cfg = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            block = (cfg.get("trials") or {}).get(trial)
            if block is None:
                # On disk but unconfigured: the pipeline would fall back to
                # defaults, so say so rather than showing an empty panel.
                self._yaml_box.insert(
                    "1.0", f"# '{trial}' has no entry in session.yaml — fill the\n"
                           f"# fields above and save to create one.\n")
                self._type_var.set("")
                self._side_var.set("both")
                self._t0_var.set("")
                self._t1_var.set("")
                return
            self._type_var.set(str(block.get("type", "")))
            self._side_var.set(str(block.get("side", "both")))
            tr = block.get("time_range") or []
            self._t0_var.set("" if len(tr) < 1 else str(tr[0]))
            self._t1_var.set("" if len(tr) < 2 else str(tr[1]))
            rest = {k: v for k, v in block.items()
                    if k not in ("type", "side", "time_range")}
            self._yaml_box.insert("1.0", yaml.safe_dump(rest, sort_keys=False)
                                  if rest else "")
        except Exception as exc:
            self._yaml_box.insert("1.0", f"# {type(exc).__name__}: {exc}")

    def _detect_time_range(self):
        """Detect this trial's movement window and put it in the fields."""
        d, trial = self._session_dir(), self._trial_var.get()
        if not d or trial == "—":
            self.status_callback("Pick a trial first", "warning")
            return
        try:
            from bioscout.utils.motion_detect import detect_time_range
            from bioscout.utils import session_layout as L
            exp = Path(L.experimental_root(str(d))) / trial
        except Exception as exc:
            self._detect_note.configure(text=f"{type(exc).__name__}: {exc}")
            return
        if not exp.is_dir():
            self._detect_note.configure(
                text=f"no export at 2_experimental/{trial} — run Export first")
            return
        tr = detect_time_range(exp)
        self._t0_var.set(f"{tr.start:.3f}")
        self._t1_var.set(f"{tr.end:.3f}")
        self._sync_sliders()
        if tr.detected:
            self._detect_note.configure(
                text=f"{tr.duration:.2f}s via {tr.method} ({tr.reference}) — "
                     f"press Save to keep")
        else:
            # Say so loudly: this is the whole capture, not a detection.
            self._detect_note.configure(
                text=f"NOT DETECTED — {tr.note}. These are the full capture "
                     f"bounds, i.e. no cropping.")

    def _save_trial_settings(self):
        """Write this trial's block back, touching only that block's line.

        This used to ``yaml.safe_dump`` the WHOLE file, which silently deleted
        every comment in session.yaml — including the block recording why
        Walking_02 must not be re-enabled — and reordered keys and reformatted
        numbers on every save. ``file_edit`` patches the value span instead, so
        one trial edit is a one-line diff.
        """
        f, trial = self._session_yaml(), self._trial_var.get()
        if not f or trial == "—":
            self.status_callback("No session.yaml / trial selected", "warning")
            return
        try:
            import yaml
            from bioscout.utils.file_edit import flow_map, load_document

            block = yaml.safe_load(self._yaml_box.get("1.0", "end")) or {}
            if not isinstance(block, dict):
                raise ValueError("the extra-keys box must be a mapping (key: value)")
            ordered = {}
            if self._type_var.get().strip():
                ordered["type"] = self._type_var.get().strip()
            ordered["side"] = self._side_var.get()
            t0, t1 = self._t0_var.get().strip(), self._t1_var.get().strip()
            if t0 or t1:
                try:
                    a, b = float(t0), float(t1)
                except ValueError:
                    raise ValueError("time start and end must both be numbers")
                if b <= a:
                    raise ValueError(f"end ({b}) must be after start ({a})")
                ordered["time_range"] = [a, b]
            # An empty pair means "use the whole capture"; time_range is simply
            # left out rather than kept stale, which would crop silently.
            for k, v in block.items():
                if k not in ("type", "side", "time_range"):
                    ordered[k] = v

            doc = load_document(f)
            trials = doc.ensure_mapping("trials")
            doc.set_entry_source(trials, trial, flow_map(ordered))
            doc.save()                       # atomic; keeps session.yaml.bak

            self.status_callback(f"Saved {trial} to session.yaml", "success")
            self._detail.delete("1.0", "end")
            self._detail.insert("1.0", f"session.yaml updated: trials.{trial}\n"
                                       f"  {trial}: {flow_map(ordered)}\n"
                                       f"Comments and other trials untouched; "
                                       f"previous file kept as {f.name}.bak\n")
        except Exception as exc:
            self.status_callback(f"{type(exc).__name__}: {exc}", "error")
            self._detail.delete("1.0", "end")
            self._detail.insert("1.0", f"NOT saved — {type(exc).__name__}: {exc}\n")

    def _open_session_yaml_in_editor(self):
        """Pop out the full editor for this session's session.yaml."""
        f = self._session_yaml()
        if not f:
            self.status_callback("No session.yaml for this session", "warning")
            return
        try:
            from bioscout.gui.widgets.file_editor import open_file_editor_window
            open_file_editor_window(self, f, status_callback=self.status_callback)
        except Exception as exc:
            self.status_callback(f"Could not open editor: {exc}", "error")

    # ----------------------------------------------------- iterations CRUD
    def _add_iteration(self):
        """Add an iteration to session.yaml, optionally copying an existing one.

        Adding one used to mean hand-editing session.yaml, which is why every
        session had the same six: the cost of a seventh was a text editor and a
        chance of breaking the file.
        """
        f = self._session_yaml()
        if not f:
            self.status_callback("No session.yaml for this session", "warning")
            return
        existing = self._yaml_iterations()
        name = _ask(self, "Add iteration", "Name for the new iteration:")
        if not name:
            return
        name = name.strip()
        if name in existing:
            self.status_callback(f"'{name}' already exists", "error")
            return
        copy_from = None
        if existing:
            copy_from = _ask(self, "Copy from",
                             "Copy settings from which iteration?\n"
                             f"({', '.join(existing)})  — leave blank for a "
                             f"blank template.")
            if copy_from:
                copy_from = copy_from.strip()
                if copy_from not in existing:
                    self.status_callback(f"'{copy_from}' is not an iteration", "error")
                    return
        try:
            from bioscout.utils.file_edit import flow_map, load_document
            doc = load_document(f)
            iters = doc.ensure_mapping("iterations")
            if copy_from:
                doc.duplicate_entry(iters, copy_from, name)
            else:
                blk = dict(NEW_ITERATION_TEMPLATE, label=name)
                # A session with several NAMED emg_maps and no
                # `default_emg_map` refuses to load the moment an iteration
                # exists that picks none -- so a blank template has to pick.
                try:
                    from bioscout.utils import session as _sess
                    _cfg = _sess.load_session_yaml(str(f))
                    if _sess.is_named_emg_map(_cfg) and not _cfg.get(
                            _sess.DEFAULT_EMG_MAP_KEY):
                        blk["emg_map"] = next(iter(_sess.emg_maps(_cfg)))
                except Exception:
                    pass
                doc.set_entry_source(iters, name, flow_map(blk))
            doc.save()
        except Exception as exc:
            self.status_callback(f"{type(exc).__name__}: {exc}", "error")
            return
        # Create the folder too, so the iteration shows up in every other tab
        # that lists directories rather than reading the yaml.
        try:
            d = self._session_dir()
            Path(_layout().iteration_path(str(d), name)).mkdir(parents=True,
                                                               exist_ok=True)
        except Exception:
            pass
        self._refresh_iterations()
        self._iter_var.set(name)
        src = f"copied from {copy_from}" if copy_from else "blank template"
        self.status_callback(f"Added iteration '{name}' ({src})", "success")
        self._detail.delete("1.0", "end")
        self._detail.insert("1.0",
                            f"session.yaml: iterations.{name} added ({src}).\n"
                            f"Set its 'generic' model, then run Model Scaling "
                            f"before analysing with it.\n")

    def _remove_iteration(self):
        f, it = self._session_yaml(), self._iter_var.get()
        if not f or it == "—":
            return
        if not messagebox.askyesno(
                "Remove iteration",
                f"Remove '{it}' from session.yaml?\n\n"
                f"Any results it has produced stay on disk — only the "
                f"configuration entry is removed (and its folder, if empty).",
                parent=self):
            return
        try:
            from bioscout.utils.file_edit import load_document
            doc = load_document(f)
            iters = doc.map_node("iterations")
            if iters is None:
                raise KeyError("no 'iterations' section")
            doc.delete_entry(iters, it)
            doc.save()
        except Exception as exc:
            self.status_callback(f"{type(exc).__name__}: {exc}", "error")
            return
        # Drop the folder ONLY when it holds nothing. Otherwise the iteration
        # keeps showing in every dropdown that lists directories, so removing it
        # looks like it silently failed — but a folder with results in it is
        # never deleted from a config edit.
        note = ""
        try:
            folder = Path(_layout().iteration_path(str(self._session_dir()), it))
            if folder.is_dir() and not any(folder.iterdir()):
                folder.rmdir()
            elif folder.is_dir():
                note = f"  Its results remain in {folder}."
        except Exception:
            pass
        self._refresh_iterations()
        self.status_callback(f"Removed iteration '{it}' from session.yaml" + note,
                             "success")

    # --------------------------------------------------------------- run
    def _run(self):
        if self._running:
            self.status_callback("Already running", "warning")
            return
        d, trial, it_name = self._session_dir(), self._trial_var.get(), self._iter_var.get()
        if not d or "—" in (trial, it_name):
            self.status_callback("Pick a session, trial and iteration first", "warning")
            return
        key = self._stage_key()
        label, kwarg, _inp, _out = STAGES_IO[key]

        missing = [n for n, p in self._resolve_inputs() if not (p and p.exists())]
        if missing:
            # Better to say which file is absent now than to read a traceback
            # from inside OpenSim in two minutes' time.
            if not messagebox.askyesno(
                    "Missing inputs",
                    f"{label} is missing:\n\n  " + "\n  ".join(missing) +
                    "\n\nRun anyway?", parent=self):
                return

        kwargs = {kw: (k == key) for k, (_l, kw, _i, _o) in STAGES_IO.items()}
        kwargs["replace"] = self._replace_var.get()
        # CEINMS needs a calibrated subject; calibrating from here would
        # recalibrate the whole model off one trial, which is not what a
        # single-trial re-run means. Reuse the existing calibration instead.
        kwargs["calibrate"] = False

        self._running = True
        self._run_btn.configure(state="disabled", text="running…")
        self._detail.delete("1.0", "end")
        self._detail.insert("1.0", f"Running {label} for {it_name} / {trial}\n"
                                   f"(CEINMS calibration is reused, not re-run)\n")

        def work():
            err = None
            try:
                from bioscout import Session
                s = Session.open(str(d))
                s.iteration(it_name).run(trials=[trial], **kwargs)
            except Exception:      # surfaced in the panel, never raised
                import traceback
                err = traceback.format_exc()
            self.after(0, lambda: self._done(err))

        threading.Thread(target=work, daemon=True).start()

    def _done(self, err):
        self._running = False
        self._run_btn.configure(state="normal", text="▶  Run this stage")
        if err:
            self._detail.insert("end", "\nFAILED\n" + err)
            self.status_callback("Trial run failed — see the panel", "error")
        else:
            self._detail.insert("end", "\nDone.\n")
            self.status_callback("Trial run finished", "success")
            self._render_inputs()


def _ask(parent, title: str, prompt: str) -> Optional[str]:
    """A themed one-line prompt — tkinter's simpledialog renders light-on-dark."""
    import tkinter as tk
    dlg = ctk.CTkToplevel(parent)
    dlg.title(title)
    dlg.geometry("460x180")
    dlg.transient(parent.winfo_toplevel())
    dlg.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(dlg, text=prompt, font=("Segoe UI", 12), anchor="w",
                 justify="left", wraplength=420).grid(row=0, column=0, sticky="ew",
                                                      padx=16, pady=(16, 6))
    var = tk.StringVar()
    entry = ctk.CTkEntry(dlg, textvariable=var, font=("Consolas", 11))
    entry.grid(row=1, column=0, sticky="ew", padx=16)
    out = {"value": None}

    def ok(*_):
        out["value"] = var.get().strip() or None
        dlg.destroy()

    row = ctk.CTkFrame(dlg, fg_color="transparent")
    row.grid(row=2, column=0, sticky="e", padx=16, pady=14)
    ctk.CTkButton(row, text="Cancel", width=80, fg_color="#4a4a4a",
                  hover_color="#5a5a5a", command=dlg.destroy).grid(row=0, column=0,
                                                                   padx=4)
    ctk.CTkButton(row, text="OK", width=80, command=ok).grid(row=0, column=1, padx=4)
    entry.bind("<Return>", ok)
    try:
        dlg.after(120, lambda: (dlg.lift(), dlg.grab_set(), entry.focus_force()))
    except Exception:
        pass
    dlg.wait_window()
    return out["value"]
