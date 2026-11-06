"""Post-Warp Pipeline page (BioScout session) for the MRI2MSK GUI."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from . import postwarp as pw
from . import ui_theme as T

COLS = ("export",) + pw.TRIAL_STEPS


def _open_path(p: Path):
    p = str(p)
    if sys.platform.startswith("win"):
        os.startfile(p)  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", p])
    else:
        subprocess.Popen(["xdg-open", p])


class PostWarpTab:
    def __init__(self, app, parent):
        self.app = app
        self.var_session = tk.StringVar()
        self.var_model = tk.StringVar()
        self.var_mass = tk.StringVar()
        self.var_static = tk.StringVar(value="–")
        self.var_placer = tk.BooleanVar(value=True)
        self.trials: list[str] = []
        self._sig = None
        self._build(parent)

    # ------------------------------------------------------------------ layout
    def _build(self, pg):
        pg.grid_columnconfigure(0, weight=1)
        pg.grid_rowconfigure(1, weight=1)

        # ---- session + model card
        sc = T.card(pg, "BioScout session")
        sc.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        b = sc.body
        b.grid_columnconfigure(1, weight=1)
        T.label(b, "Session folder", 12, T.MUTED).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=3)
        T.entry(b, self.var_session).grid(row=0, column=1, sticky="ew", pady=3)
        T.button(b, "Browse", self._browse_session, "primary", 80).grid(row=0, column=2, padx=(8, 4))
        self.btn_create = T.button(b, "Create session", self._create_session, "success", 120)
        self.btn_create.grid(row=0, column=3, padx=(4, 0))
        T.label(b, "Warped model", 12, T.MUTED).grid(row=1, column=0, sticky="w", padx=(0, 10), pady=3)
        T.entry(b, self.var_model).grid(row=1, column=1, sticky="ew", pady=3)
        T.button(b, "Browse", self._browse_model, "primary", 80).grid(row=1, column=2, padx=(8, 4))
        T.button(b, "Auto-detect", self.autodetect, "neutral", 120).grid(row=1, column=3, padx=(4, 0))
        row = ctk.CTkFrame(b, fg_color="transparent")
        row.grid(row=2, column=1, columnspan=3, sticky="w", pady=(6, 0))
        T.label(row, "Body mass (kg)", 12, T.MUTED).pack(side="left", padx=(0, 6))
        T.entry(row, self.var_mass, 70).pack(side="left", padx=(0, 18))
        T.label(row, "Static trial", 12, T.MUTED).pack(side="left", padx=(0, 6))
        T.label(row, "", 12, textvariable=self.var_static).pack(side="left", padx=(0, 18))
        ctk.CTkSwitch(row, text="Place markers on static trial", variable=self.var_placer, font=T.f(12),
                      progress_color=T.ACCENT).pack(side="left")
        self.lbl_info = T.label(b, "", 11, T.MUTED)
        self.lbl_info.grid(row=3, column=0, columnspan=4, sticky="w", pady=(6, 0))

        # ---- steps + trials
        lower = ctk.CTkFrame(pg, fg_color="transparent")
        lower.grid(row=1, column=0, sticky="nsew")
        lower.grid_columnconfigure(1, weight=1)
        lower.grid_rowconfigure(0, weight=1)

        stc = T.card(lower, "Post-Warp Steps")
        stc.grid(row=0, column=0, sticky="nsw", padx=(0, 10))
        g = stc.body
        self.rows = {}
        for i, key in enumerate(pw.POST_STEPS):
            T.label(g, pw.POST_LABELS[key], 13).grid(row=i, column=0, sticky="w", pady=4)
            bt = T.button(g, "Run", lambda k=key: self.run([k]), "primary", 70)
            bt.grid(row=i, column=1, padx=6)
            st = T.label(g, "", 12, T.ST_IDLE, width=110)
            st.grid(row=i, column=2, sticky="w")
            self.rows[key] = (bt, st)
        T.button(g, "▶  Run all steps (selected trials)", lambda: self.run(list(pw.POST_STEPS)),
                 "success", 260).grid(row=len(pw.POST_STEPS), column=0, columnspan=3, sticky="w", pady=(12, 4))
        brow = ctk.CTkFrame(g, fg_color="transparent")
        brow.grid(row=len(pw.POST_STEPS) + 1, column=0, columnspan=3, sticky="w", pady=2)
        T.button(brow, "View scaled model", self._view_scaled, "neutral", 128).pack(side="left")
        T.button(brow, "Edit session.yaml", self._open_yaml, "neutral", 128).pack(side="left", padx=(4, 0))

        tc = T.card(lower, "Trials  (click to select · Ctrl/Shift for several)")
        tc.grid(row=0, column=1, sticky="nsew")
        tb = tc.body
        tb.grid_columnconfigure(0, weight=1)
        tb.grid_rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(tb, columns=("trial",) + COLS, show="headings", selectmode="extended",
                                 height=9, style="Dark.Treeview")
        for c in ("trial",) + COLS:
            self.tree.heading(c, text="Trial" if c == "trial" else c.upper())
            self.tree.column(c, width=170 if c == "trial" else 72, anchor="w" if c == "trial" else "center",
                             stretch=c == "trial")
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(tb, command=self.tree.yview, style="Dark.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")
        rb = ctk.CTkFrame(tb, fg_color="transparent")
        rb.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
        T.button(rb, "Select all", lambda: self.tree.selection_set(self.tree.get_children()), "neutral", 90).pack(
            side="left")
        T.button(rb, "Open trial folder", self._open_results, "neutral", 130).pack(side="left", padx=6)
        T.button(rb, "JCF contributions", self._show_jcf, "primary", 140).pack(side="left")
        T.button(rb, "All plots", self._show_plots, "neutral", 90).pack(side="left", padx=6)

    # ------------------------------------------------------------------ config
    def config_dict(self) -> dict:
        return dict(postSession=self.var_session.get(), postModel=self.var_model.get(),
                    postMass=self.var_mass.get(), postMarkerPlacer=self.var_placer.get())

    def apply_config(self, d: dict):
        for key, var in (("postSession", self.var_session), ("postModel", self.var_model),
                         ("postMass", self.var_mass)):
            if d.get(key):
                var.set(str(d[key]))
        if "postMarkerPlacer" in d:
            self.var_placer.set(bool(d["postMarkerPlacer"]))
        self.refresh(force=True)

    def participant(self) -> Path | None:
        f = self.app.var_folder.get().strip()
        return Path(f) if f and Path(f).is_dir() else None

    def autodetect(self, quiet=False):
        p = self.participant()
        if p is None:
            if not quiet:
                messagebox.showinfo("MRI2MSK", "Select a participant folder first (top bar).")
            return
        m = pw.latest_warped_model(p)
        if m and (not quiet or not self.var_model.get()):
            self.var_model.set(str(m))
        sess = pw.find_sessions(p)
        if sess and (not quiet or not self.var_session.get()):
            self.var_session.set(str(sess[0]))
        if not quiet or not self.var_mass.get().strip():
            self._detect_mass(quiet=True)
        self.refresh(force=True)

    def _detect_mass(self, quiet=False):
        p = self.participant()
        if p is None:
            return
        sd = self.var_session.get().strip() or None
        m = pw.detect_body_mass(p, sd, log=self.app.log)
        if m:
            self.var_mass.set(f"{m:g}")
        elif not quiet:
            messagebox.showinfo("MRI2MSK", "No body mass found in the static C3D (PROCESSING:BODYMASS) or a "
                                           "participant spreadsheet - enter it manually.")

    def _browse_session(self):
        d = filedialog.askdirectory(title="Session folder (e.g. TD13/session1)",
                                    initialdir=str(self.participant() or "."))
        if d:
            self.var_session.set(d)
            self.refresh(force=True)

    def _browse_model(self):
        f = filedialog.askopenfilename(filetypes=[("OpenSim model", "*.osim")])
        if f:
            self.var_model.set(f)
            self.refresh(force=True)

    def mass(self) -> float | None:
        try:
            return float(self.var_mass.get()) if self.var_mass.get().strip() else None
        except ValueError:
            return None

    def session(self) -> pw.PostWarpSession | None:
        p, s = self.participant(), self.var_session.get().strip()
        if p is None or not s:
            return None
        return pw.PostWarpSession(s, p, self.var_model.get() or None, self.mass(),
                                  self.var_placer.get(), log=print)

    def _create_session(self):
        p = self.participant()
        if p is None:
            messagebox.showinfo("MRI2MSK", "Select a participant folder first (top bar).")
            return
        if not pw.bioscout_available():
            messagebox.showerror("MRI2MSK", "BioScout is not installed:  pip install bioscout")
            return
        sd = self.var_session.get().strip()
        if not sd:
            sd = filedialog.askdirectory(title="Choose or create the session folder", initialdir=str(p))
            if not sd:
                return
            self.var_session.set(sd)
        ps = pw.PostWarpSession(sd, p, self.var_model.get() or None, self.mass(), log=self.app.log)
        sources = []
        if not ps.c3d_files():
            sources = filedialog.askopenfilenames(title="Select the C3D captures (static + dynamic trials)",
                                                  filetypes=[("C3D", "*.c3d")], initialdir=str(p))
            if not sources:
                return
        if ps.exists() and not messagebox.askyesno(
                "MRI2MSK", "session.yaml already exists.\nKeep its settings and only add/refresh the MRI "
                           f"iteration '{pw.ITERATION}'?"):
            return
        try:
            ps.create([Path(s) for s in sources])
            self.app.log(f"Session ready: {ps.yaml}", "ok")
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("MRI2MSK", str(e))
        self.refresh(force=True)

    # ------------------------------------------------------------------ status
    def refresh(self, force=False):
        ps = self.session()
        ok_bs = pw.bioscout_available()
        if not ok_bs:
            self.lbl_info.configure(text="BioScout not installed in this environment:  pip install bioscout",
                                    text_color=T.ST_ERR)
        elif ps is None:
            self.lbl_info.configure(text="Pick the session folder (e.g. TD13/session1) or create one.",
                                    text_color=T.MUTED)
        elif not ps.exists():
            n = len(ps.c3d_files())
            self.lbl_info.configure(text=f"No session.yaml yet ({n} C3D file(s) in 1_c3dfiles) - click "
                                         f"'Create session'.", text_color=T.ST_READY)
        else:
            self.lbl_info.configure(text=f"BioScout session  ·  iteration '{pw.ITERATION}'  ·  "
                                         f"{ps.yaml}", text_color=T.ST_DONE)
        self.btn_create.configure(text="Update session" if ps and ps.exists() else "Create session")
        trials = ps.trials() if ps and (ps.exists() or ps.c3d_files()) else []
        self.var_static.set((ps.static_trial() or "–") if ps else "–")
        stat = {t: ps.trial_status(t) for t in trials} if ps else {}
        sig = (tuple(trials), tuple(tuple(sorted(v.items())) for v in stat.values()))
        if force or sig != self._sig:
            self._sig = sig
            sel = {self.tree.item(i, "values")[0] for i in self.tree.selection()}
            self.tree.delete(*self.tree.get_children())
            for t in trials:
                iid = self.tree.insert("", "end", values=(t,) + tuple("✓" if stat[t][k] else "·" for k in COLS))
                if not sel or t in sel:
                    self.tree.selection_add(iid)
        self.trials = trials
        busy, n = self.app.busy, len(trials)
        have_yaml = bool(ps and ps.exists())
        for key, (bt, st) in self.rows.items():
            if key == "scale":
                done = bool(ps and ps.scaled_model.is_file())
                st.configure(text="✓  Done" if done else ("Ready" if have_yaml else "–"),
                             text_color=T.ST_DONE if done else (T.ST_READY if have_yaml else T.ST_IDLE))
            else:
                c = sum(stat[t][key] for t in trials) if trials else 0
                st.configure(text=f"{c}/{n} trials" if n else "no trials",
                             text_color=T.ST_DONE if n and c == n else (T.ST_READY if c else T.ST_IDLE))
            T.set_enabled(bt, ok_bs and have_yaml and not busy)

    def selected_trials(self) -> list[str]:
        names = {self.tree.item(i, "values")[0] for i in self.tree.selection()}
        return [t for t in self.trials if t in names]

    # ------------------------------------------------------------------ run
    def run(self, steps: list[str]):
        ps = self.session()
        if ps is None or self.app.busy:
            return
        trials = self.selected_trials()
        if any(s in pw.TRIAL_STEPS for s in steps) and not trials:
            messagebox.showinfo("MRI2MSK", "Select at least one trial.")
            return
        if "scale" in steps and (not ps.mass or not ps.warped_model):
            messagebox.showerror("MRI2MSK", "Scaling needs the warped model and the body mass (kg).")
            return
        if "scale" not in steps and any(s in pw.TRIAL_STEPS for s in steps) and not ps.scaled_model.is_file():
            messagebox.showerror("MRI2MSK", "Run step 1 (scale) first - the iteration uses the scaled model.")
            return
        label = "Post-Warp: " + ", ".join(steps) + (f" ({len(trials)} trial(s))" if trials else "")

        def work():
            if "export" in steps:
                ps.run_export()
            if "scale" in steps:
                ps.run_scale()
            for t in trials:
                for s in steps:
                    if s in pw.TRIAL_STEPS:
                        print(f"[{t}] {pw.POST_LABELS[s].split('  ', 1)[-1]} ...")
                        ps.run_trial(s, t)
            return None

        self.app.run_in_background(label, work, lambda: self.refresh(force=True))

    # ------------------------------------------------------------------ results
    def _view_scaled(self):
        ps = self.session()
        if ps and ps.scaled_model.is_file():
            self.app._open_osc(ps.scaled_model)
        else:
            messagebox.showinfo("MRI2MSK", "No scaled model yet (step 1).")

    def _open_yaml(self):
        ps = self.session()
        if ps and ps.exists():
            _open_path(ps.yaml)
        else:
            messagebox.showinfo("MRI2MSK", "No session.yaml yet - click 'Create session'.")

    def _sel_dir(self) -> Path | None:
        ps = self.session()
        tr = self.selected_trials()
        if ps is None:
            return None
        return ps.trial_dir(tr[0]) if tr else ps.iter_dir

    def _open_results(self):
        d = self._sel_dir()
        if d and d.exists():
            _open_path(d)
        else:
            messagebox.showinfo("MRI2MSK", "No results for this trial yet.")

    def _show_jcf(self):
        d = self._sel_dir()
        png = d / "joint_contact_forces" / "contributions_so.png" if d else None
        if png and png.is_file():
            _open_path(png)
        else:
            messagebox.showinfo("MRI2MSK", "No JCF contribution figure for this trial yet (step 6).")

    def _show_plots(self):
        d = self._sel_dir()
        pngs = sorted(d.rglob("*.png")) if d and d.exists() else []
        if not pngs:
            messagebox.showinfo("MRI2MSK", "No figures for this trial yet.")
            return
        win = self.app._toplevel(f"Figures - {d.name}", "620x460")
        c = T.card(win, f"Figures in {d.name}  (double-click to open)")
        c.pack(fill="both", expand=True, padx=10, pady=10)
        lb = tk.Listbox(c.body, bg=T.SIDEBAR, fg=T.TEXT, selectbackground=T.ACCENT, borderwidth=0,
                        highlightthickness=0, font=(T.FONT, 11))
        for p in pngs:
            lb.insert("end", str(p.relative_to(d)))
        lb.pack(fill="both", expand=True)
        lb.bind("<Double-Button-1>", lambda _e: _open_path(pngs[lb.curselection()[0]]))
