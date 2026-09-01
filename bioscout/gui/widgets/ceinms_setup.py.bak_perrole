"""bioscout.gui.widgets.ceinms_setup — prepare a session for CEINMS.

Everything CEINMS needs BEFORE calibration can run lives in ``session.yaml``,
and until now the only ways to put it there were the File Editor (raw YAML) or
a text editor. This tab is the form for it, in the Data curation section, with
sub-tabs on the left:

    EMG map        — which recorded channel drives which OpenSim muscles.
                     The single most consequential mapping in the pipeline: a
                     channel mapped to the wrong muscle calibrates the wrong
                     muscle, silently.
    Calibration    — which trials calibrate, which normalise, which of the
                     named calibration configs is the default, and the CEINMS
                     alpha/beta/gamma weights.
    Files          — read-only inventory: which CEINMS inputs/outputs exist
                     per iteration, so "why did calibration not run" starts
                     here instead of in an explorer window.

Every write goes through ``SessionForm`` — surgical span patches with a backup,
never a YAML re-dump — so hand-written comments in session.yaml survive. The
diff is shown before anything is saved.
"""
import os
from pathlib import Path

import customtkinter as ctk

from utils.logger import logger

#: session-level folders that are not model iterations
_NON_ITER = {"1_c3dfiles", "2_experimental", "3_iterations", "experimental",
             "movement_detection", "logs", "outputs", "_to_delete"}


class CEINMSSetupTab(ctk.CTkFrame):
    def __init__(self, parent, config_manager=None, status_callback=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.status_callback = status_callback or (lambda *a, **k: None)
        self.project_dir = None
        self.form = None                # the open SessionForm
        self._map_rows = []             # [(channel_var, muscles_var)]
        self._cal_vars = {}             # trial -> BooleanVar (calibration)
        self._norm_vars = {}            # trial -> BooleanVar (normalisation)
        self._build()

    # ---------------------------------------------------------------- shell
    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # -- top: session picker (shared by every sub-tab) -----------------
        top = ctk.CTkFrame(self)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 4))
        top.grid_columnconfigure(5, weight=1)
        ctk.CTkLabel(top, text="CEINMS Setup", font=("Segoe UI", 14, "bold")
                     ).grid(row=0, column=0, padx=(8, 16), pady=8)
        ctk.CTkLabel(top, text="Subject", font=("Segoe UI", 11)).grid(
            row=0, column=1, padx=(0, 4))
        self.subject_var = ctk.StringVar(value="")
        self.subject_menu = ctk.CTkOptionMenu(
            top, variable=self.subject_var, values=["—"], width=110,
            font=("Segoe UI", 11), command=lambda _v: self._fill_sessions())
        self.subject_menu.grid(row=0, column=2, padx=(0, 10))
        ctk.CTkLabel(top, text="Session", font=("Segoe UI", 11)).grid(
            row=0, column=3, padx=(0, 4))
        self.session_var = ctk.StringVar(value="")
        self.session_menu = ctk.CTkOptionMenu(
            top, variable=self.session_var, values=["—"], width=110,
            font=("Segoe UI", 11), command=lambda _v: self._open_session())
        self.session_menu.grid(row=0, column=4, padx=(0, 10))
        self.session_state = ctk.CTkLabel(top, text="no session loaded",
                                          font=("Segoe UI", 10),
                                          text_color="#8a8a8a")
        self.session_state.grid(row=0, column=5, sticky="w")

        # -- left rail ------------------------------------------------------
        rail = ctk.CTkFrame(self, width=150, corner_radius=0)
        rail.grid(row=1, column=0, sticky="nsw", padx=(8, 0), pady=(0, 8))
        rail.grid_propagate(False)
        self._buttons = {}
        for name in ("EMG map", "Calibration", "Files"):
            btn = ctk.CTkButton(rail, text=name, height=32, anchor="w",
                                fg_color="#2d2d2d", hover_color="#3d3d3d",
                                border_width=1, border_color="#404040",
                                command=lambda n=name: self.show(n))
            btn.pack(fill="x", padx=8, pady=3)
            self._buttons[name] = btn

        # -- content panes ---------------------------------------------------
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=1, column=1, sticky="nsew", padx=8, pady=(0, 8))
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)
        self.panes = {
            "EMG map": self._build_map_pane(),
            "Calibration": self._build_cal_pane(),
            "Files": self._build_files_pane(),
        }
        self.show("EMG map")

    def show(self, name):
        for n, pane in self.panes.items():
            (pane.grid if n == name else pane.grid_remove)()
        for n, btn in self._buttons.items():
            btn.configure(fg_color="#1f538d" if n == name else "#2d2d2d")
        if name == "Files":
            self._refresh_files()

    # ------------------------------------------------------------ session io
    def set_project_dir(self, project_dir):
        try:
            self.project_dir = Path(project_dir) if project_dir else None
        except Exception:                                      # noqa: BLE001
            self.project_dir = None
        self._fill_subjects()

    def _sim_dir(self):
        return (Path(self.project_dir) / "simulations") if self.project_dir else None

    def _fill_subjects(self):
        sim = self._sim_dir()
        subs = sorted(p.name for p in sim.iterdir()
                      if p.is_dir() and any(
                          (q / "session.yaml").exists()
                          for q in p.iterdir() if q.is_dir())) if sim and sim.is_dir() else []
        self.subject_menu.configure(values=subs or ["—"])
        if subs:
            self.subject_var.set(subs[0])
            self._fill_sessions()
        else:
            self.session_state.configure(
                text="load a project first (top bar)", text_color="#e5b567")

    def _fill_sessions(self):
        sim = self._sim_dir()
        pid = self.subject_var.get()
        sess = sorted(p.name for p in (sim / pid).iterdir()
                      if p.is_dir() and (p / "session.yaml").exists()) \
            if sim and pid and (sim / pid).is_dir() else []
        self.session_menu.configure(values=sess or ["—"])
        if sess:
            self.session_var.set(sess[0])
            self._open_session()

    def _open_session(self):
        sim = self._sim_dir()
        pid, st = self.subject_var.get(), self.session_var.get()
        if not (sim and pid and st):
            return
        path = sim / pid / st
        try:
            from utils.session_form import SessionForm
            self.form = SessionForm(str(path))
            self.session_state.configure(
                text=f"{path}  ·  {len(self.form.trials())} trials",
                text_color="#4cc46a")
            self._load_map_rows()
            self._load_cal_pane()
            self._refresh_files()
        except Exception as exc:                               # noqa: BLE001
            self.form = None
            logger.error(f"CEINMS setup: cannot open {path}: {exc}")
            self.session_state.configure(text=f"cannot open: {exc}",
                                         text_color="#dc3545")

    def _save(self, what):
        """Preview the diff in the console, save with backup, report."""
        if self.form is None:
            return
        try:
            if not self.form.dirty():
                self._flash(f"{what}: nothing changed")
                return
            diff = self.form.diff()
            if diff:
                print(f"--- session.yaml changes ({what}) ---\n{diff}")
            out = self.form.save(backup=True)
            self._flash(f"{what} saved -> {out}")
        except Exception as exc:                               # noqa: BLE001
            logger.error(f"CEINMS setup save failed: {exc}")
            self._flash(f"save FAILED: {exc}", error=True)

    def _flash(self, msg, error=False):
        self.session_state.configure(text=str(msg),
                                     text_color="#dc3545" if error else "#4cc46a")
        self.status_callback(f"CEINMS setup: {msg}")

    # ------------------------------------------------------------ EMG map
    def _build_map_pane(self):
        pane = ctk.CTkFrame(self.content)
        pane.grid(row=0, column=0, sticky="nsew")
        pane.grid_rowconfigure(1, weight=1)
        pane.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            pane, font=("Segoe UI", 11), justify="left", anchor="w",
            text=("Which recorded channel drives which OpenSim muscles. "
                  "Muscles are comma-separated model names (vasmed_r, vasint_r). "
                  "A channel mapped to the wrong muscle calibrates the wrong "
                  "muscle — silently."),
        ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(8, 4))
        self.map_scroll = ctk.CTkScrollableFrame(pane)
        self.map_scroll.grid(row=1, column=0, columnspan=2, sticky="nsew",
                             padx=10, pady=4)
        self.map_scroll.grid_columnconfigure(1, weight=1)
        bar = ctk.CTkFrame(pane, fg_color="transparent")
        bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(4, 8))
        ctk.CTkButton(bar, text="+ Add channel", width=120, height=28,
                      font=("Segoe UI", 11), command=self._add_map_row
                      ).pack(side="left")
        ctk.CTkButton(bar, text="Save EMG map", width=140, height=28,
                      font=("Segoe UI", 11, "bold"),
                      fg_color="#28a745", hover_color="#218838",
                      command=self._save_map).pack(side="right")
        pane.grid_remove()
        return pane

    def _load_map_rows(self):
        for w in list(self.map_scroll.winfo_children()):
            w.destroy()
        self._map_rows = []
        if self.form is None:
            return
        header = ("Channel", "Muscles (comma-separated)")
        for c, text in enumerate(header):
            ctk.CTkLabel(self.map_scroll, text=text,
                         font=("Segoe UI", 10, "bold"), text_color="#9fc5e8"
                         ).grid(row=0, column=c, sticky="w", padx=6, pady=(0, 4))
        for ch, muscles in self.form.emg_map().items():
            self._add_map_row(ch, ", ".join(muscles))

    def _add_map_row(self, channel="", muscles=""):
        r = len(self._map_rows) + 1
        ch_var = ctk.StringVar(value=str(channel))
        mu_var = ctk.StringVar(value=str(muscles))
        ctk.CTkEntry(self.map_scroll, textvariable=ch_var, width=190,
                     font=("Consolas", 11)).grid(row=r, column=0, sticky="w",
                                                 padx=6, pady=2)
        ctk.CTkEntry(self.map_scroll, textvariable=mu_var,
                     font=("Consolas", 11)).grid(row=r, column=1, sticky="ew",
                                                 padx=6, pady=2)
        self._map_rows.append((ch_var, mu_var))

    def _save_map(self):
        """Stage every row, drop entries whose row was emptied, save once."""
        if self.form is None:
            return
        try:
            rows = {}
            for ch_var, mu_var in self._map_rows:
                ch = ch_var.get().strip()
                if not ch:
                    continue
                rows[ch] = [m.strip() for m in mu_var.get().split(",")
                            if m.strip()]
            existing = set(self.form.emg_map())
            for ch in existing - set(rows):
                self.form.delete_emg_map_entry(ch)
            for ch, muscles in rows.items():
                self.form.set_emg_map_entry(ch, muscles)
            self._save("EMG map")
            self._load_map_rows()
        except Exception as exc:                               # noqa: BLE001
            self._flash(f"EMG map FAILED: {exc}", error=True)

    # --------------------------------------------------------- calibration
    def _build_cal_pane(self):
        pane = ctk.CTkFrame(self.content)
        pane.grid(row=0, column=0, sticky="nsew")
        pane.grid_rowconfigure(1, weight=1)
        for c in (0, 1):
            pane.grid_columnconfigure(c, weight=1)

        head = ctk.CTkFrame(pane, fg_color="transparent")
        head.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(8, 4))
        ctk.CTkLabel(head, text="Default calibration", font=("Segoe UI", 11)
                     ).pack(side="left", padx=(0, 6))
        self.default_cal_var = ctk.StringVar(value="")
        self.default_cal_menu = ctk.CTkOptionMenu(
            head, variable=self.default_cal_var, values=["—"], width=120,
            font=("Segoe UI", 11))
        self.default_cal_menu.pack(side="left", padx=(0, 18))
        self._ceinms_vars = {}
        for key in ("alpha", "beta", "gamma"):
            ctk.CTkLabel(head, text=key, font=("Segoe UI", 11)
                         ).pack(side="left", padx=(6, 2))
            var = ctk.StringVar(value="")
            ctk.CTkEntry(head, textvariable=var, width=64,
                         font=("Consolas", 11)).pack(side="left")
            self._ceinms_vars[key] = var

        self.cal_list = self._trial_list(pane, 0, "Calibration trials",
                                         "CEINMS calibrates on these")
        self.norm_list = self._trial_list(pane, 1, "Normalisation trials",
                                          "MVC reference — EMG is normalised "
                                          "to its maximum across these")

        ctk.CTkButton(pane, text="Save calibration settings", height=30,
                      font=("Segoe UI", 11, "bold"),
                      fg_color="#28a745", hover_color="#218838",
                      command=self._save_cal
                      ).grid(row=2, column=0, columnspan=2, sticky="ew",
                             padx=10, pady=(4, 8))
        pane.grid_remove()
        return pane

    def _trial_list(self, parent, col, title, hint):
        box = ctk.CTkFrame(parent)
        box.grid(row=1, column=col, sticky="nsew", padx=10, pady=4)
        box.grid_rowconfigure(2, weight=1)
        box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(box, text=title, font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w", padx=8, pady=(6, 0))
        ctk.CTkLabel(box, text=hint, font=("Segoe UI", 9),
                     text_color="#8a8a8a").grid(row=1, column=0, sticky="w",
                                                padx=8)
        scroll = ctk.CTkScrollableFrame(box, fg_color="transparent")
        scroll.grid(row=2, column=0, sticky="nsew", padx=4, pady=4)
        return scroll

    def _load_cal_pane(self):
        if self.form is None:
            return
        configs = self.form.calibration_configs() or []
        self.default_cal_menu.configure(values=configs or ["—"])
        self.default_cal_var.set(str(self.form.value("default_calibration")
                                     or (configs[0] if configs else "")))
        ce = self.form.value("ceinms") or {}
        for key, var in self._ceinms_vars.items():
            var.set(str(ce.get(key, "")))
        cal = set(self.form.list_value("calibration_trials"))
        norm = set(self.form.list_value("normalisation_trials"))
        for scroll, store, ticked in ((self.cal_list, self._cal_vars, cal),
                                      (self.norm_list, self._norm_vars, norm)):
            for w in list(scroll.winfo_children()):
                w.destroy()
            store.clear()
            for t in self.form.trials():
                var = ctk.BooleanVar(value=t in ticked)
                store[t] = var
                ctk.CTkCheckBox(scroll, text=t, variable=var,
                                font=("Segoe UI", 10)
                                ).pack(anchor="w", padx=4, pady=1)

    def _save_cal(self):
        if self.form is None:
            return
        try:
            self.form.set_list("calibration_trials",
                               [t for t, v in self._cal_vars.items() if v.get()])
            self.form.set_list("normalisation_trials",
                               [t for t, v in self._norm_vars.items() if v.get()])
            if self.default_cal_var.get() not in ("", "—"):
                self.form.set_scalar("default_calibration",
                                     self.default_cal_var.get())
            ce = {}
            for key, var in self._ceinms_vars.items():
                txt = var.get().strip()
                if txt:
                    try:
                        ce[key] = float(txt) if "." in txt else int(txt)
                    except ValueError:
                        raise ValueError(f"ceinms {key} is not a number: {txt!r}")
            if ce:
                self.form.set_ceinms(**ce)
            self._save("calibration settings")
        except Exception as exc:                               # noqa: BLE001
            self._flash(f"calibration FAILED: {exc}", error=True)

    # ---------------------------------------------------------------- files
    def _build_files_pane(self):
        pane = ctk.CTkFrame(self.content)
        pane.grid(row=0, column=0, sticky="nsew")
        pane.grid_rowconfigure(0, weight=1)
        pane.grid_columnconfigure(0, weight=1)
        import tkinter
        from gui.gui_settings import font_size
        self.files_text = tkinter.Text(
            pane, wrap="none", font=("Consolas", font_size(11)),
            background="#1e1e1e", foreground="#dcdcdc", relief="flat",
            borderwidth=0, highlightthickness=0)
        self.files_text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        sb = tkinter.Scrollbar(pane, orient="vertical",
                               command=self.files_text.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.files_text.configure(yscrollcommand=sb.set, state="disabled")
        pane.grid_remove()
        return pane

    def _refresh_files(self):
        """What CEINMS will find on disk, per iteration — found or MISSING."""
        lines = []
        sim = self._sim_dir()
        pid, st = self.subject_var.get(), self.session_var.get()
        sess = sim / pid / st if (sim and pid and st) else None
        if not (sess and sess.is_dir()):
            lines = ["no session loaded"]
        else:
            iroot = sess / "3_iterations"
            iters = sorted(p for p in iroot.iterdir() if p.is_dir()) \
                if iroot.is_dir() else []
            if not iters:
                lines.append("no 3_iterations/ — run the export/pipeline first")
            for it in iters:
                lines.append(f"[{it.name}]")
                cal = it / "ceinms_calibration"
                checks = [
                    ("calibrated subject", cal / "subjectCalibrated.xml"),
                    ("uncalibrated subject", cal / "subjectUncalibrated.xml"),
                    ("excitation generator",
                     cal / "excitationGenerator.xml"),
                ]
                for label, path in checks:
                    mark = "ok     " if path.exists() else "MISSING"
                    lines.append(f"  {mark}  {label:<24} {path.name}")
                trials = [d for d in it.iterdir() if d.is_dir()
                          and d.name not in ("ceinms_calibration",
                                             "static_optimisation")]
                n_exec = sum(1 for d in trials
                             if any((d / "ceinms").glob("Execution_*")))
                lines.append(f"  {len(trials)} trial folders, "
                             f"{n_exec} with CEINMS executions")
                lines.append("")
        try:
            self.files_text.configure(state="normal")
            self.files_text.delete("1.0", "end")
            self.files_text.insert("end", "\n".join(lines))
            self.files_text.configure(state="disabled")
        except Exception:                                      # noqa: BLE001
            pass


__all__ = ["CEINMSSetupTab"]
