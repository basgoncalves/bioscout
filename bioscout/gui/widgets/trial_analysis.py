"""Trial Analysis tab — one trial: what exists, what it's configured as, and re-run it.

The Session tab is "run these stages over these trials". This is the other
question, the one you ask when a session finishes and one trial looks wrong:
*for this trial, which stages produced output, for which models, what is it
configured as, and can I re-run just this one?*

Three panels:

* **Status grid** — stages down the side, iterations across the top, read from
  the files on disk. No state file, so nothing can claim a stage ran when it
  didn't. Click a cell to list what it found.
* **Trial settings** — this trial's block from ``session.yaml`` (type, side,
  time_range), editable and saved back in place. That block is what decides
  which part of the capture every downstream stage sees, so it belongs next to
  the status rather than three folders away.
* **Run** — re-run chosen stages for this trial alone, on one iteration.

Stage detection keys on the trial's SUBFOLDER first and the filename second.
The folders (``external_biomechanics``, ``muscle_analysis``,
``static_optimisation``, ``joint_contact_forces``, ``ceinms``) are stable, and
matching on them avoids the mistake the first version made — guessing that IK
writes something called ``*_ik.mot`` when it actually writes
``joint_angles.mot``, which showed Inverse Kinematics as never-run on a trial
that had run it.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import customtkinter as ctk

#: (key, label, subdirectory or None for the trial root, filename fragments).
#: An empty fragment tuple means "any file in that subdirectory counts".
STAGES: List[Tuple[str, str, Optional[str], Tuple[str, ...]]] = [
    ("export",  "Export (markers/GRF)", None, ("marker_experimental.trc", "grf.mot")),
    ("emg",     "EMG normalised",       None, ("emg_filtered_normalised.mot",
                                               "emg_filtered.mot")),
    ("ik",      "Inverse Kinematics",   "external_biomechanics",
     ("joint_angles.mot", "_ik_marker_errors")),
    ("id",      "Inverse Dynamics",     "external_biomechanics",
     ("inverse_dynamics.sto",)),
    ("ma",      "Muscle Analysis",      "muscle_analysis",      ()),
    ("so",      "Static Optimisation",  "static_optimisation",  ()),
    ("jra",     "Joint Reaction",       "joint_contact_forces", ()),
    ("ceinms",  "CEINMS",               "ceinms",               ()),
]

#: Which stage keys the Run panel can actually drive, and the Iteration.run()
#: keyword each maps to. Export and EMG are session-level, not per-iteration,
#: so they are deliberately absent — running them for one trial from here would
#: silently skip the session-wide EMG normalisation reference.
RUNNABLE = [
    ("ik",     "Inverse Kinematics + ID", "do_exbiomec"),
    ("ma",     "Muscle Analysis",         "do_muscle_analysis"),
    ("so",     "Static Optimisation",     "do_so"),
    ("ceinms", "CEINMS",                  "do_ceinms"),
]


def _layout():
    from bioscout.utils import session_layout as _L
    return _L


def _files(d: Path) -> List[Path]:
    try:
        return [p for p in d.iterdir() if p.is_file()] if d.is_dir() else []
    except OSError:
        return []


def stage_status(session_dir, trial: str) -> Dict[str, Dict[str, List[Path]]]:
    """``{iteration: {stage_key: [files]}}`` for one trial.

    ``2_experimental`` appears as a pseudo-iteration because export and EMG are
    model-independent: they run once per session, not once per model.
    """
    L = _layout()
    session_dir = Path(session_dir)
    cols: Dict[str, Dict[str, List[Path]]] = {}

    def scan(label: str, root: Path):
        if not root.is_dir():
            return
        per_stage: Dict[str, List[Path]] = {}
        for key, _lbl, sub, frags in STAGES:
            d = root / sub if sub else root
            found = _files(d)
            if frags:
                found = [f for f in found
                         if any(fr in f.name.lower() for fr in frags)]
            per_stage[key] = found
        cols[label] = per_stage

    try:
        exp_root = Path(L.experimental_root(str(session_dir)))
        scan(exp_root.name, exp_root / trial)
    except Exception:
        pass
    try:
        itr = Path(L.iterations_root(str(session_dir)))
        if itr.is_dir():
            for it in sorted(itr.iterdir()):
                if it.is_dir() and it.name not in L.NON_ITERATION_DIRS:
                    scan(it.name, it / trial)
    except Exception:
        pass
    return cols


class TrialAnalysisTab(ctk.CTkFrame):
    def __init__(self, parent, config_manager=None, status_callback=None):
        super().__init__(parent, fg_color="transparent")
        self.config_manager = config_manager
        self.status_callback = status_callback or (lambda *a, **k: None)
        self._project_root: Optional[Path] = None
        self._running = False
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

        self._grid_frame = ctk.CTkScrollableFrame(mid, fg_color="#12121a",
                                                  corner_radius=8)
        self._grid_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        right = ctk.CTkFrame(mid, fg_color="#12121a", corner_radius=8)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(8, weight=1)
        right.grid_columnconfigure(0, weight=1)

        # ---- trial settings (session.yaml) -------------------------------
        ctk.CTkLabel(right, text="Trial settings  (session.yaml)",
                     font=("Segoe UI", 12, "bold"), text_color="#dddddd").grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 2))

        # Named fields rather than raw YAML only: a trial whose block has no
        # time_range line had nowhere to type one, and time_range is the key
        # that decides what every downstream stage sees.
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

        # Fills the fields, does not save: a detection you disagree with costs
        # one glance, and the Save button stays the only thing that writes.
        ctk.CTkButton(fields, text="⤢  Detect from motion", height=26,
                      font=("Segoe UI", 11), fg_color="#2f6f9f",
                      hover_color="#3a86bd",
                      command=self._detect_time_range).grid(
            row=2, column=0, columnspan=4, sticky="ew", pady=(6, 2))
        self._detect_note = ctk.CTkLabel(fields, text="", font=("Segoe UI", 10),
                                         text_color="#888888", anchor="w")
        self._detect_note.grid(row=3, column=0, columnspan=4, sticky="ew")

        ctk.CTkLabel(right, text="other keys (YAML)", font=("Segoe UI", 10),
                     text_color="#888888").grid(row=7, column=0, sticky="w",
                                                padx=10, pady=(4, 0))
        self._yaml_box = ctk.CTkTextbox(right, font=("Consolas", 12), height=90)
        self._yaml_box.grid(row=8, column=0, sticky="nsew", padx=10, pady=(0, 6))
        ctk.CTkButton(right, text="Save to session.yaml", height=28,
                      font=("Segoe UI", 12),
                      command=self._save_trial_settings).grid(
            row=2, column=0, sticky="ew", padx=10, pady=(0, 10))

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

        self._stage_vars = {}
        stages_frame = ctk.CTkFrame(right, fg_color="transparent")
        stages_frame.grid(row=5, column=0, sticky="ew", padx=10, pady=(4, 0))
        for i, (key, label, _kw) in enumerate(RUNNABLE):
            v = ctk.BooleanVar(value=(key == "ik"))
            self._stage_vars[key] = v
            ctk.CTkCheckBox(stages_frame, text=label, variable=v,
                            font=("Segoe UI", 11)).grid(row=i // 2, column=i % 2,
                                                        sticky="w", padx=4, pady=2)
        self._replace_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(stages_frame, text="overwrite existing",
                        variable=self._replace_var,
                        font=("Segoe UI", 11)).grid(row=2, column=0, columnspan=2,
                                                    sticky="w", padx=4, pady=2)
        self._run_btn = ctk.CTkButton(right, text="▶  Run selected stages",
                                      height=32, font=("Segoe UI", 12),
                                      fg_color="#28a745", hover_color="#218838",
                                      command=self._run)
        self._run_btn.grid(row=6, column=0, sticky="ew", padx=10, pady=(6, 10))

        self._detail = ctk.CTkTextbox(self, height=130, font=("Consolas", 11))
        self._detail.grid(row=3, column=0, sticky="ew", padx=8, pady=(0, 8))
        self._detail.insert("1.0", "Pick a trial, then click a cell to list its files.\n")

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
        p = self._project_root / "simulations"
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
        self.refresh()
        self._load_trial_settings()

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
        f, trial = self._session_yaml(), self._trial_var.get()
        if not f or trial == "—":
            self.status_callback("No session.yaml / trial selected", "warning")
            return
        try:
            import yaml
            block = yaml.safe_load(self._yaml_box.get("1.0", "end")) or {}
            if not isinstance(block, dict):
                raise ValueError("the extra-keys box must be a mapping (key: value)")
            if self._type_var.get().strip():
                block["type"] = self._type_var.get().strip()
            block["side"] = self._side_var.get()
            t0, t1 = self._t0_var.get().strip(), self._t1_var.get().strip()
            if t0 or t1:
                try:
                    a, b = float(t0), float(t1)
                except ValueError:
                    raise ValueError("time start and end must both be numbers")
                if b <= a:
                    raise ValueError(f"end ({b}) must be after start ({a})")
                block["time_range"] = [a, b]
            else:
                # Explicitly dropped rather than left stale: an empty pair means
                # "use the whole capture", and keeping the old numbers would
                # crop silently.
                block.pop("time_range", None)
            cfg = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            cfg.setdefault("trials", {})[trial] = block
            # Written via a temp file then replaced, so an exception midway
            # cannot leave the session with a half-written session.yaml.
            tmp = f.with_suffix(".yaml.tmp")
            tmp.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
            tmp.replace(f)
            self.status_callback(f"Saved {trial} to session.yaml", "success")
            self._detail.delete("1.0", "end")
            self._detail.insert("1.0", f"session.yaml updated: trials.{trial}\n")
        except Exception as exc:
            self.status_callback(f"{type(exc).__name__}: {exc}", "error")
            self._detail.delete("1.0", "end")
            self._detail.insert("1.0", f"NOT saved — {type(exc).__name__}: {exc}\n")

    # ------------------------------------------------------------- table
    def refresh(self, *_):
        for w in self._grid_frame.winfo_children():
            w.destroy()
        d, trial = self._session_dir(), self._trial_var.get()
        if not d or trial == "—":
            return
        cols = stage_status(d, trial)
        iters = [c for c in cols if not c.startswith(("2_", "experimental"))]
        self._iter_menu.configure(values=iters or ["—"])
        if self._iter_var.get() not in iters:
            self._iter_var.set((iters or ["—"])[0])
        if not cols:
            ctk.CTkLabel(self._grid_frame, text=f"No folders for trial '{trial}'.",
                         font=("Segoe UI", 12)).grid(row=0, column=0, padx=12, pady=12)
            return

        names = list(cols)
        ctk.CTkLabel(self._grid_frame, text="Stage", font=("Segoe UI", 11, "bold"),
                     text_color="#aaaaaa").grid(row=0, column=0, sticky="w",
                                                padx=8, pady=6)
        for j, n in enumerate(names, start=1):
            ctk.CTkLabel(self._grid_frame, text=n, font=("Segoe UI", 11, "bold"),
                         text_color="#dddddd").grid(row=0, column=j, padx=8, pady=6)

        for i, (key, label, _sub, _fr) in enumerate(STAGES, start=1):
            ctk.CTkLabel(self._grid_frame, text=label, font=("Segoe UI", 12),
                         anchor="w").grid(row=i, column=0, sticky="w", padx=8, pady=3)
            for j, n in enumerate(names, start=1):
                files = cols[n].get(key) or []
                done = bool(files)
                ctk.CTkButton(
                    self._grid_frame,
                    text=f"✓ {len(files)}" if done else "–",
                    width=70, height=26, font=("Segoe UI", 11),
                    fg_color="#1f6f3f" if done else "#2a2a33",
                    hover_color="#28874e" if done else "#3a3a44",
                    command=lambda f=files, t=f"{n} / {label}": self._show(t, f)
                ).grid(row=i, column=j, padx=6, pady=3)

    def _show(self, title, files):
        self._detail.delete("1.0", "end")
        if not files:
            self._detail.insert("1.0", f"{title}\n  (nothing on disk)\n")
            return
        lines = [title, ""]
        for f in sorted(files):
            try:
                kb = f.stat().st_size / 1024.0
            except OSError:
                kb = float("nan")
            lines.append(f"  {f.name:<52s} {kb:>9.1f} kB")
        lines += ["", f"  {files[0].parent}"]
        self._detail.insert("1.0", "\n".join(lines) + "\n")

    # --------------------------------------------------------------- run
    def _run(self):
        if self._running:
            self.status_callback("Already running", "warning")
            return
        d, trial, it_name = self._session_dir(), self._trial_var.get(), self._iter_var.get()
        if not d or "—" in (trial, it_name):
            self.status_callback("Pick a session, trial and iteration first", "warning")
            return
        kwargs = {kw: self._stage_vars[k].get() for k, _l, kw in RUNNABLE}
        if not any(kwargs.values()):
            self.status_callback("No stage selected", "warning")
            return
        kwargs["replace"] = self._replace_var.get()
        # CEINMS needs a calibrated subject; calibrating from here would
        # recalibrate the whole model off one trial, which is not what a
        # single-trial re-run means. Reuse the existing calibration instead.
        kwargs["calibrate"] = False

        self._running = True
        self._run_btn.configure(state="disabled", text="running…")
        self._detail.delete("1.0", "end")
        self._detail.insert("1.0", f"Running {it_name} / {trial}: "
                                   f"{', '.join(k for k, v in kwargs.items() if v is True)}\n"
                                   f"(CEINMS calibration is reused, not re-run)\n")

        def work():
            err = None
            try:
                from bioscout import Session
                s = Session.open(str(d))
                s.iteration(it_name).run(trials=[trial], **kwargs)
            except Exception as exc:      # surfaced in the panel, never raised
                import traceback
                err = traceback.format_exc()
            self.after(0, lambda: self._done(err))

        threading.Thread(target=work, daemon=True).start()

    def _done(self, err):
        self._running = False
        self._run_btn.configure(state="normal", text="▶  Run selected stages")
        if err:
            self._detail.insert("end", "\nFAILED\n" + err)
            self.status_callback("Trial run failed — see the panel", "error")
        else:
            self._detail.insert("end", "\nDone.\n")
            self.status_callback("Trial run finished", "success")
        self.refresh()
