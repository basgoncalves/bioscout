"""Load Tracking Tab — import fitness-tracker sessions, estimate muscle load & fatigue."""

import os
import sys
import threading
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog, messagebox

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.config_manager import ConfigManager
from utils.logger import logger


class LoadTrackingTab(ctk.CTkFrame):
    """Import workout files from a fitness tracker and build a load/fatigue report.

    Supports Amazfit/Zepp, Garmin, Strava etc. exports (.fit/.tcx/.gpx/.csv).
    Uses bioscout.load_tracking under the hood.
    """

    def __init__(self, parent, config_manager: ConfigManager, status_callback):
        super().__init__(parent)
        self.config_manager = config_manager
        self.status_callback = status_callback
        self._input_paths = []          # list of files
        self._input_folder = None
        self._creds_path = None         # cloud credentials JSON
        self._last_pdf = None
        self._create_widgets()

    # ------------------------------------------------------------------ UI --
    def _create_widgets(self) -> None:
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(self, text="Load Tracking — muscle load & fatigue",
                             font=("Segoe UI", 16, "bold"))
        title.grid(row=0, column=0, columnspan=2, padx=20, pady=(18, 4), sticky="w")
        sub = ctk.CTkLabel(
            self, text="Import sessions from your watch (Zepp ⋯ → export GPX/TCX/FIT), "
                       "estimate per-muscle load & fatigue, export a PDF report.",
            font=("Segoe UI", 10), text_color="#9aa0a6")
        sub.grid(row=1, column=0, columnspan=2, padx=20, pady=(0, 10), sticky="w")

        # ---- controls (left) ----
        ctrl = ctk.CTkScrollableFrame(self, width=320)
        ctrl.grid(row=2, column=0, padx=(20, 10), pady=10, sticky="nsw")

        ctk.CTkLabel(ctrl, text="1. Sessions", font=("Segoe UI", 12, "bold")
                     ).pack(anchor="w", pady=(4, 4))
        ctk.CTkButton(ctrl, text="Add files…", command=self._pick_files
                      ).pack(fill="x", pady=2)
        ctk.CTkButton(ctrl, text="Add folder…", command=self._pick_folder
                      ).pack(fill="x", pady=2)
        ctk.CTkButton(ctrl, text="Clear", fg_color="#6c757d",
                      hover_color="#5a6268", command=self._clear_inputs
                      ).pack(fill="x", pady=2)
        self.input_label = ctk.CTkLabel(ctrl, text="No sessions added",
                                        font=("Segoe UI", 9), text_color="#9aa0a6",
                                        wraplength=290, justify="left")
        self.input_label.pack(anchor="w", pady=(2, 6))

        ctk.CTkLabel(ctrl, text="…or pull from cloud (Zepp / Strava)",
                     font=("Segoe UI", 10, "italic"), text_color="#9aa0a6"
                     ).pack(anchor="w", pady=(2, 2))
        ctk.CTkButton(ctrl, text="Cloud credentials…", fg_color="#1971c2",
                      hover_color="#155fa0", command=self._pick_creds
                      ).pack(fill="x", pady=2)
        self.creds_label = ctk.CTkLabel(ctrl, text="No credentials loaded",
                                        font=("Segoe UI", 9), text_color="#9aa0a6",
                                        wraplength=290, justify="left")
        self.creds_label.pack(anchor="w", pady=(2, 10))

        ctk.CTkLabel(ctrl, text="2. Athlete", font=("Segoe UI", 12, "bold")
                     ).pack(anchor="w", pady=(4, 4))
        self.age_var = ctk.StringVar(value="")
        self.hrmax_var = ctk.StringVar(value="")
        self.hrrest_var = ctk.StringVar(value="")
        self.sex_var = ctk.StringVar(value="M")
        self._labeled_entry(ctrl, "Age", self.age_var, "e.g. 30")
        self._labeled_entry(ctrl, "Max HR (bpm)", self.hrmax_var, "blank → 220-age")
        self._labeled_entry(ctrl, "Resting HR (bpm)", self.hrrest_var, "default 60")
        row = ctk.CTkFrame(ctrl, fg_color="transparent"); row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text="Sex", width=110, anchor="w").pack(side="left")
        ctk.CTkSegmentedButton(row, values=["M", "F"], variable=self.sex_var,
                               width=120).pack(side="left")

        ctk.CTkLabel(ctrl, text="3. Report", font=("Segoe UI", 12, "bold")
                     ).pack(anchor="w", pady=(12, 4))
        self.run_btn = ctk.CTkButton(ctrl, text="▶  Build report",
                                     fg_color="#2f9e44", hover_color="#268038",
                                     command=self._run)
        self.run_btn.pack(fill="x", pady=2)
        self.open_btn = ctk.CTkButton(ctrl, text="Open last PDF", state="disabled",
                                      command=self._open_pdf)
        self.open_btn.pack(fill="x", pady=2)

        # ---- results (right) ----
        right = ctk.CTkFrame(self)
        right.grid(row=2, column=1, padx=(10, 20), pady=10, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(right, text="Summary", font=("Segoe UI", 12, "bold")
                     ).grid(row=0, column=0, padx=12, pady=(10, 4), sticky="w")
        self.output = ctk.CTkTextbox(right, wrap="word", font=("Consolas", 11))
        self.output.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.output.insert("1.0",
                           "Add sessions, set your HR profile, then Build report.\n\n"
                           "Tip: for gym sessions without GPS, use a manifest CSV with "
                           "columns: date, sport, duration_min, rpe, notes "
                           "(tag notes like 'leg day', 'push', 'deadlift').")
        self.output.configure(state="disabled")

    def _labeled_entry(self, parent, label, var, placeholder):
        row = ctk.CTkFrame(parent, fg_color="transparent"); row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=label, width=110, anchor="w").pack(side="left")
        ctk.CTkEntry(row, textvariable=var, placeholder_text=placeholder, width=120
                     ).pack(side="left")

    # ------------------------------------------------------------- actions --
    def _pick_files(self):
        files = filedialog.askopenfilenames(
            title="Select workout exports",
            filetypes=[("Workout files", "*.fit *.tcx *.gpx *.csv"), ("All", "*.*")])
        if files:
            self._input_paths.extend(files)
            self._refresh_input_label()

    def _pick_folder(self):
        folder = filedialog.askdirectory(title="Select folder of workout exports")
        if folder:
            self._input_folder = folder
            self._refresh_input_label()

    def _pick_creds(self):
        path = filedialog.askopenfilename(
            title="Select cloud credentials JSON (Zepp / Strava)",
            filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if path:
            self._creds_path = path
            self.creds_label.configure(text=f"Credentials: {os.path.basename(path)}")

    def _clear_inputs(self):
        self._input_paths = []
        self._input_folder = None
        self._creds_path = None
        self.creds_label.configure(text="No credentials loaded")
        self._refresh_input_label()

    def _refresh_input_label(self):
        parts = []
        if self._input_folder:
            parts.append(f"Folder: {os.path.basename(self._input_folder)}")
        if self._input_paths:
            parts.append(f"{len(self._input_paths)} file(s)")
        self.input_label.configure(text="\n".join(parts) or "No sessions added")

    def _athlete_kwargs(self):
        def _num(v, cast):
            v = v.strip()
            return cast(v) if v else None
        try:
            return dict(age=_num(self.age_var.get(), int),
                        hr_max=_num(self.hrmax_var.get(), float),
                        hr_rest=_num(self.hrrest_var.get(), float),
                        sex=self.sex_var.get())
        except ValueError:
            messagebox.showerror("Invalid input",
                                 "Age / HR values must be numbers.")
            return None

    def _run(self):
        inputs = list(self._input_paths)
        if self._input_folder:
            inputs.append(self._input_folder)
        if not inputs and not self._creds_path:
            messagebox.showwarning(
                "No sessions",
                "Add workout files/folder, or load a cloud credentials file first.")
            return
        ak = self._athlete_kwargs()
        if ak is None:
            return
        out = filedialog.asksaveasfilename(
            title="Save report as", defaultextension=".pdf",
            initialfile="load_report.pdf", filetypes=[("PDF", "*.pdf")])
        if not out:
            return

        self.run_btn.configure(state="disabled", text="Working…")
        self._set_output("Building report…")
        threading.Thread(target=self._worker,
                         args=(inputs, self._creds_path, ak, out),
                         daemon=True).start()

    def _worker(self, inputs, creds_path, ak, out):
        try:
            from load_tracking import (LoadTracker, AthleteProfile,
                                        load_credentials, pull_into_tracker)
            tracker = LoadTracker(athlete=AthleteProfile(name="Athlete", **ak))
            n = tracker.add_files(inputs) if inputs else 0
            if creds_path:
                creds = load_credentials(creds_path)
                res = pull_into_tracker(tracker, creds)
                n += res["zepp"] + res["strava"]
                for err in res["errors"]:
                    logger.warning(f"Cloud pull: {err}")
            if n == 0:
                self.after(0, lambda: self._finish(
                    None, "No sessions could be loaded.\n\nCheck your files "
                          "(.fit/.tcx/.gpx/.csv) or cloud credentials."))
                return
            tracker.compute()
            summary = tracker.summary_text()
            tracker.report(out)
            self.after(0, lambda: self._finish(out, summary))
        except Exception as e:   # noqa: BLE001
            logger.error(f"Load report failed: {e}", exc_info=True)
            self.after(0, lambda: self._finish(None, f"Error: {e}"))

    def _finish(self, pdf, summary):
        self.run_btn.configure(state="normal", text="▶  Build report")
        self._set_output(summary)
        if pdf:
            self._last_pdf = pdf
            self.open_btn.configure(state="normal")
            if self.status_callback:
                self.status_callback(f"Load report saved: {os.path.basename(pdf)}")

    def _open_pdf(self):
        if not self._last_pdf or not os.path.exists(self._last_pdf):
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(self._last_pdf)   # noqa: S606
            elif sys.platform == "darwin":
                os.system(f'open "{self._last_pdf}"')
            else:
                os.system(f'xdg-open "{self._last_pdf}"')
        except Exception as e:   # noqa: BLE001
            messagebox.showerror("Open failed", str(e))

    def _set_output(self, text):
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", text)
        self.output.configure(state="disabled")
