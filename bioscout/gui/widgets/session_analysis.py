"""Session Analysis tab — one session: what it declares, what has actually run,
and re-running any part of it.

Trial Analysis answers *"this one trial looks wrong — what will the stage read
and can I re-run it?"*. This tab answers the level above, which had no GUI at
all even though :class:`bioscout.Session` has the API for it:

* **Overview** — what the session DECLARES. Subject, body mass, static trial,
  markerset, every trial grouped by type and badged where it has a role
  (static / calibration / normalisation), the emg_map, and each iteration with
  the model it names. This is ``Session.describe()`` as a panel; the terminal
  version is still one button away for the parts that need the model resolver.
* **Coverage** — what has actually RUN. The trial × stage ok/MISS grid from
  ``run_check.verify_run`` — the same table that ends a run, but live, for any
  iteration, without running anything. "Which of my 11 trials never got a
  static optimisation?" is a question the GUI could not previously answer.
* **Run this session** — pick iterations, pick trials, tick stages, go.
  ``Session.run`` / ``Session.export`` behind checkboxes.

Two deliberate choices about cost:

* Overview and Coverage read **session.yaml and the filesystem only**. No
  ``Session.open``, so no Project bootstrap and no OpenSim import — the panel
  fills instantly and works on a machine where bioscout cannot solve at all.
  ``run_check`` is standard-library by design, which is what makes the
  coverage grid free.
* Anything that needs the model resolver (does ``so_model`` actually exist?)
  or that runs a stage is explicit, on a button, and on a worker thread.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import customtkinter as ctk
from tkinter import messagebox

from .. import simulations_root as _simulations_root

#: (verify key, column heading, Iteration.run kwarg or None).
#:
#: The verify keys are ``run_check.STAGE_OUTPUTS``' keys — deliberately NOT a
#: second spelling of them. ``export`` has no run kwarg because it is
#: session-level (``Session.export``), and ``scale`` is absent entirely: it
#: produces a MODEL, not a per-trial output, so it has nothing to show in a
#: trial × stage grid. It still appears in the run panel below.
#:
#: docs/IMPLEMENTATIONS.md §2.10 argues this table should be generated from a
#: single ``bioscout/stages.py`` registry rather than written out again here.
#: When that lands, this constant is one of the things that should disappear.
STAGES: List[Tuple[str, str, Optional[str]]] = [
    ("export",          "export",   None),
    ("exbiomec",        "IK + ID",  "do_exbiomec"),
    ("muscle_analysis", "MA",       "do_muscle_analysis"),
    ("so",              "SO",       "do_so"),
    ("ceinms",          "CEINMS",   "do_ceinms"),
]

#: Where each stage's output lives, so a cell in the Summary grid can open it.
#: ``export`` is the odd one out — it writes into the session's model-INDEPENDENT
#: experimental folder, which is exactly why ``verify_run`` checks it there.
STAGE_DIRS = {
    "export":          ("exp", ""),
    "exbiomec":        ("iter", "external_biomechanics"),
    "muscle_analysis": ("iter", "muscle_analysis"),
    "so":              ("iter", "static_optimisation"),
    "ceinms":          ("iter", "ceinms"),
}


def _open_in_explorer(path: Path) -> Optional[str]:
    """Show `path` in the OS file manager. -> None on success, else a message.

    Falls back to the parent when the path itself is absent, so clicking a
    MISS cell still lands you somewhere useful rather than doing nothing.
    """
    import subprocess
    import sys as _sys
    p = Path(path)
    if not p.exists():
        p = p.parent
    if not p.exists():
        return f"{path} does not exist"
    try:
        if _sys.platform == "win32":
            import os as _os
            _os.startfile(str(p))                          # noqa: S606
        elif _sys.platform == "darwin":
            subprocess.Popen(["open", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])
        return None
    except Exception as exc:                                   # noqa: BLE001
        return f"{type(exc).__name__}: {exc}"

#: Extra run-panel entries that are not per-trial stages.
EXTRA_RUN = [("scale", "scale model(s)", "do_scale")]

_OK, _MISS, _NA = "#4cc46a", "#e06c75", "#4a4a55"


def _layout():
    from bioscout.utils import session_layout as _L
    return _L


def _run_check():
    from bioscout.utils import run_check as _rc
    return _rc


def _read_yaml(path: Path) -> dict:
    """session.yaml as a plain dict, or {} — never raises.

    Uses bioscout's strict loader when it imports (it refuses duplicate keys,
    the trap from §1), and falls back to plain safe_load so a panel that is
    only READING a file still fills on a machine where the package cannot.
    """
    try:
        from bioscout.utils.session import load_session_yaml
        return load_session_yaml(str(path)) or {}
    except Exception:                                          # noqa: BLE001
        pass
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:                                          # noqa: BLE001
        return {}


def _is_all(v) -> bool:
    """Is this role's value the "every trial" sentinel?

    ``normalisation_trials: all`` is how a session says "the EMG maximum spans
    the whole session" — the real sessions in this repo use it. Reading it as a
    trial NAME makes the panel report a calibration trial called "all" that is
    not on disk, which is a false alarm about the one thing this panel exists
    to make trustworthy.
    """
    return isinstance(v, str) and v.strip().lower() == "all"


def _as_list(v) -> List[str]:
    """Mirror of ``bioscout.utils.session._as_list``: 'a b c' / ['a','b'] /
    None -> list[str], with 'all' and None both meaning "every trial" ([]).

    Kept faithful deliberately — a panel that parses session.yaml differently
    from the code that RUNS it is worse than no panel.
    """
    if v is None or _is_all(v):
        return []
    if isinstance(v, str):
        return v.replace(",", " ").split()
    try:
        return [str(x) for x in v]
    except TypeError:
        return []


class SessionAnalysisTab(ctk.CTkFrame):
    """Session-level counterpart to the Trial Analysis tab."""

    def __init__(self, parent, config_manager=None, status_callback=None):
        super().__init__(parent, fg_color="transparent")
        self.config_manager = config_manager
        self.status_callback = status_callback or (lambda *a, **k: None)
        self._project_root: Optional[Path] = None
        self._running = False
        self._cfg: dict = {}
        self._iter_vars: Dict[str, ctk.BooleanVar] = {}
        self._trial_vars: Dict[str, ctk.BooleanVar] = {}
        self._stage_vars: Dict[str, ctk.BooleanVar] = {}
        self._build()

    # ------------------------------------------------------------- layout
    def _build(self):
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        pick = ctk.CTkFrame(self, fg_color="#161620", corner_radius=8)
        pick.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        pick.grid_columnconfigure(1, weight=1)
        pick.grid_columnconfigure(3, weight=1)

        def combo(col, label):
            ctk.CTkLabel(pick, text=label, font=("Segoe UI", 11, "bold"),
                         text_color="#aaaaaa").grid(row=0, column=col,
                                                    padx=(10, 4), pady=8,
                                                    sticky="e")
            var = ctk.StringVar(value="—")
            m = ctk.CTkOptionMenu(pick, variable=var, values=["—"], height=28,
                                  font=("Segoe UI", 12))
            m.grid(row=0, column=col + 1, padx=(0, 10), pady=8, sticky="ew")
            return var, m

        self._subj_var, self._subj_menu = combo(0, "Subject")
        self._sess_var, self._sess_menu = combo(2, "Session")
        self._subj_var.trace_add("write", lambda *_: self._on_subject())
        self._sess_var.trace_add("write", lambda *_: self._on_session())

        ctk.CTkButton(self, text="↻  Refresh", height=28, width=110,
                      font=("Segoe UI", 12), command=self.refresh
                      ).grid(row=1, column=0, sticky="e", padx=10, pady=(0, 4))

        mid = ctk.CTkFrame(self, fg_color="transparent")
        mid.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 4))
        mid.grid_rowconfigure(0, weight=1)
        mid.grid_columnconfigure(0, weight=3)
        mid.grid_columnconfigure(1, weight=2)
        self._build_left(mid)
        self._build_right(mid)

        self._detail = ctk.CTkTextbox(self, height=130, font=("Consolas", 11))
        self._detail.grid(row=3, column=0, sticky="ew", padx=8, pady=(0, 8))
        self._detail.insert("1.0", "Pick a subject and a session.\n")

    # -- left: overview / coverage ----------------------------------------
    def _build_left(self, parent):
        left = ctk.CTkFrame(parent, fg_color="#12121a", corner_radius=8)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(left, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        head.grid_columnconfigure(1, weight=1)
        self._view = ctk.CTkSegmentedButton(
            head, values=["Overview", "Coverage", "Iteration", "Trial"],
            command=self._switch_view, font=("Segoe UI", 11))
        self._view.set("Overview")
        self._view.grid(row=0, column=0, sticky="w")
        self._note = ctk.CTkLabel(head, text="", font=("Segoe UI", 10),
                                  text_color="#8a8a8a", anchor="e")
        self._note.grid(row=0, column=1, sticky="ew", padx=8)

        self._stack = ctk.CTkFrame(left, fg_color="transparent")
        self._stack.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 8))
        self._stack.grid_rowconfigure(0, weight=1)
        self._stack.grid_columnconfigure(0, weight=1)

        self._overview = ctk.CTkScrollableFrame(self._stack,
                                                fg_color="transparent")
        self._overview.grid_columnconfigure(0, weight=1)

        self._coverage = ctk.CTkFrame(self._stack, fg_color="transparent")
        self._coverage.grid_rowconfigure(1, weight=1)
        self._coverage.grid_columnconfigure(0, weight=1)

        covbar = ctk.CTkFrame(self._coverage, fg_color="transparent")
        covbar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        covbar.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(covbar, text="Iteration", font=("Segoe UI", 11)).grid(
            row=0, column=0, padx=(4, 6))
        self._cov_iter = ctk.StringVar(value="—")
        self._cov_menu = ctk.CTkOptionMenu(covbar, variable=self._cov_iter,
                                           values=["—"], width=200, height=28,
                                           font=("Segoe UI", 12))
        self._cov_menu.grid(row=0, column=1)
        self._cov_iter.trace_add("write", lambda *_: self._render_coverage())
        self._cov_note = ctk.CTkLabel(covbar, text="", font=("Segoe UI", 10),
                                      text_color="#8a8a8a", anchor="w")
        self._cov_note.grid(row=0, column=2, sticky="ew", padx=10)

        self._cov_grid = ctk.CTkScrollableFrame(self._coverage,
                                                fg_color="transparent")
        self._cov_grid.grid(row=1, column=0, sticky="nsew")

        self._build_iteration_editor()
        self._build_trial_view()
        self._show(self._overview)

    @property
    def _panes(self):
        return (self._overview, self._coverage, self._editor, self._trial_pane)

    def _show(self, pane):
        for p in self._panes:
            p.grid_forget()
        pane.grid(row=0, column=0, sticky="nsew")

    def _switch_view(self, name: str):
        if name == "Coverage":
            self._show(self._coverage)
            self._render_coverage()
        elif name == "Iteration":
            self._show(self._editor)
            self._load_iteration()
        elif name == "Trial":
            self._show(self._trial_pane)
            self._sync_trial_view()
        else:
            self._show(self._overview)

    # -- Trial sub-view: the real Trial Analysis widget, embedded ----------
    def _build_trial_view(self):
        """Mount TrialAnalysisTab itself rather than reimplementing it.

        Everything that tab does — resolving a stage's inputs, overriding one,
        the GRF window picker, editing time_range, re-running a single stage —
        is exactly what you want on a trial that looks wrong, and none of it
        is worth having twice. It is a CTkFrame, so it re-parents; `embedded`
        hides its subject/session pickers and the host drives them.
        """
        self._trial_pane = ctk.CTkFrame(self._stack, fg_color="transparent")
        self._trial_pane.grid_rowconfigure(0, weight=1)
        self._trial_pane.grid_columnconfigure(0, weight=1)
        self._trial_view = None
        try:
            from .trial_analysis import TrialAnalysisTab
            self._trial_view = TrialAnalysisTab(
                self._trial_pane, self.config_manager, self.status_callback,
                embedded=True)
            self._trial_view.grid(row=0, column=0, sticky="nsew")
        except Exception as exc:                               # noqa: BLE001
            ctk.CTkLabel(self._trial_pane,
                         text=f"Trial view unavailable: "
                              f"{type(exc).__name__}: {exc}",
                         font=("Segoe UI", 11), text_color=_MISS
                         ).grid(row=0, column=0, sticky="w", padx=10, pady=10)

    def _sync_trial_view(self):
        """Point the embedded trial view at whatever this tab has selected."""
        if self._trial_view is None:
            return
        s, ss = self._subj_var.get(), self._sess_var.get()
        if "—" in (s, ss):
            return
        try:
            if self._project_root:
                self._trial_view.set_project_dir(str(self._project_root))
            self._trial_view.set_selection(s, ss)
        except Exception as exc:                               # noqa: BLE001
            self.status_callback(f"Trial view: {type(exc).__name__}: {exc}",
                                 "warning")

    # -- Iteration sub-view: edit one model arm ---------------------------
    def _build_iteration_editor(self):
        """Edit one iteration's block in session.yaml.

        Writes go through ``SessionForm.set_iteration_field``, which patches
        the file surgically — comments, key order and formatting survive. Never
        re-dump the YAML: a round-trip through safe_load/dump silently strips
        every comment in the file (see the File Editor's notes).
        """
        self._editor = ctk.CTkFrame(self._stack, fg_color="transparent")
        self._editor.grid_rowconfigure(1, weight=1)
        self._editor.grid_columnconfigure(0, weight=1)

        bar = ctk.CTkFrame(self._editor, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        bar.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(bar, text="Iteration", font=("Segoe UI", 11)).grid(
            row=0, column=0, padx=(4, 6))
        self._ed_iter = ctk.StringVar(value="—")
        self._ed_menu = ctk.CTkOptionMenu(bar, variable=self._ed_iter,
                                          values=["—"], width=200, height=28,
                                          font=("Segoe UI", 12))
        self._ed_menu.grid(row=0, column=1)
        self._ed_iter.trace_add("write", lambda *_: self._load_iteration())
        self._ed_note = ctk.CTkLabel(bar, text="", font=("Segoe UI", 10),
                                     text_color="#8a8a8a", anchor="w")
        self._ed_note.grid(row=0, column=2, sticky="ew", padx=10)

        self._ed_body = ctk.CTkScrollableFrame(self._editor,
                                               fg_color="transparent")
        self._ed_body.grid(row=1, column=0, sticky="nsew")
        self._ed_body.grid_columnconfigure(1, weight=1)

        btns = ctk.CTkFrame(self._editor, fg_color="transparent")
        btns.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        btns.grid_columnconfigure(2, weight=1)
        ctk.CTkButton(btns, text="Save to session.yaml", height=28, width=170,
                      font=("Segoe UI", 12), fg_color="#28a745",
                      hover_color="#218838", command=self._save_iteration
                      ).grid(row=0, column=0, padx=(4, 6))
        ctk.CTkButton(btns, text="Show changes", height=28, width=120,
                      font=("Segoe UI", 12), fg_color="#3a3a4a",
                      hover_color="#4a4a5a", command=self._diff_iteration
                      ).grid(row=0, column=1)
        ctk.CTkButton(btns, text="Reload", height=28, width=90,
                      font=("Segoe UI", 12), fg_color="#3a3a4a",
                      hover_color="#4a4a5a", command=self._load_iteration
                      ).grid(row=0, column=3, padx=(0, 4))

    #: The fields this editor offers, grouped. Keys and kinds come from
    #: ``session_form.ITERATION_FIELDS`` — label/colour/group are deliberately
    #: left out: they only affect how a figure names this arm, and belong with
    #: the plotting code rather than in a panel about what will be solved.
    ED_GROUPS = (
        ("models", (("generic", "generic model", "text"),
                    ("so_model", "SO model", "text"),
                    ("ceinms_model", "CEINMS model", "text"))),
        ("scaling", (("prescaled", "prescaled", "bool"),
                     ("linear_scaling", "linear scaling", "bool"),
                     ("marker_placer", "marker placer", "bool"),
                     ("opt_neval", "opt_neval", "number"),
                     ("mvic_factor", "mvic_factor", "number"))),
        ("CEINMS", (("calibration", "calibration config", "text"),
                    ("calibrated", "calibrated", "bool"))),
    )

    def _resolve_model(self, key: str, value: str) -> Optional[Path]:
        """Where this model value points for the iteration being EDITED, or None.

        `generic` resolves against the shared library; `so_model` /
        `ceinms_model` are iteration-relative (they are what scaling WRITES).
        A value that resolves nowhere is the single most common way to lose an
        afternoon, so the editor answers it as you type rather than at solve
        time. One implementation, in `_resolve_model_in`, shared with the
        checker — two path resolvers that disagree would be worse than none.
        """
        return self._resolve_model_in(self._ed_iter.get(), key, value)

    def _load_iteration(self, *_):
        for w in self._ed_body.winfo_children():
            w.destroy()
        self._ed_vars: Dict[str, tuple] = {}
        d, it = self._session_dir(), self._ed_iter.get()
        if not d or it == "—":
            ctk.CTkLabel(self._ed_body, text="Pick a session and an iteration.",
                         font=("Segoe UI", 11), text_color="#888888"
                         ).grid(row=0, column=0, sticky="w", padx=8, pady=10)
            self._ed_note.configure(text="")
            return
        block = (self._cfg.get("iterations") or {}).get(it) or {}
        row = 0
        for group, fields in self.ED_GROUPS:
            ctk.CTkLabel(self._ed_body, text=group, font=("Segoe UI", 11, "bold"),
                         text_color="#7fb2e5").grid(row=row, column=0,
                                                    columnspan=3, sticky="w",
                                                    padx=6, pady=(10, 4))
            row += 1
            for key, label, kind in fields:
                ctk.CTkLabel(self._ed_body, text=label, font=("Segoe UI", 11),
                             anchor="w", width=150, text_color="#aaaaaa"
                             ).grid(row=row, column=0, sticky="w",
                                    padx=(14, 6), pady=3)
                cur = block.get(key)
                if kind == "bool":
                    var = ctk.BooleanVar(value=bool(cur) if cur is not None
                                         else False)
                    ctk.CTkCheckBox(self._ed_body, text="", variable=var,
                                    checkbox_width=18, checkbox_height=18
                                    ).grid(row=row, column=1, sticky="w", pady=3)
                    mark = None
                else:
                    var = ctk.StringVar(value="" if cur is None else str(cur))
                    ctk.CTkEntry(self._ed_body, textvariable=var, height=26,
                                 font=("Consolas", 11)).grid(
                        row=row, column=1, sticky="ew", pady=3)
                    mark = None
                    if key in ("generic", "so_model", "ceinms_model"):
                        mark = ctk.CTkLabel(self._ed_body, text="",
                                            font=("Segoe UI", 12, "bold"),
                                            width=22)
                        mark.grid(row=row, column=2, padx=4)
                        var.trace_add(
                            "write",
                            lambda *_a, k=key, v=var, m=mark:
                            self._mark_model(k, v, m))
                self._ed_vars[key] = (var, kind, cur, mark)
                if mark is not None:
                    self._mark_model(key, var, mark)
                row += 1

        extra = sorted(set(block) - {k for _g, fs in self.ED_GROUPS
                                     for k, _l, _kd in fs})
        if extra:
            # Anything this editor does not offer is still IN the file, and a
            # form that hides keys it will not touch invites "I changed it and
            # it did nothing". Named, read-only.
            ctk.CTkLabel(self._ed_body, text="other keys (not edited here)",
                         font=("Segoe UI", 11, "bold"), text_color="#7a7a86"
                         ).grid(row=row, column=0, columnspan=3, sticky="w",
                                padx=6, pady=(12, 4))
            row += 1
            for key in extra:
                ctk.CTkLabel(self._ed_body, text=f"{key}: {block[key]}",
                             font=("Consolas", 11), anchor="w",
                             text_color="#777777").grid(
                    row=row, column=0, columnspan=3, sticky="w",
                    padx=(14, 6), pady=1)
                row += 1

        self._ed_note.configure(
            text=f"{len(block)} key(s) in this block",
            text_color="#8a8a8a")

    def _mark_model(self, key: str, var, mark):
        p = self._resolve_model(key, var.get().strip())
        if not var.get().strip():
            mark.configure(text="·", text_color="#777777")
        elif p:
            mark.configure(text="✓", text_color=_OK)
        else:
            # so_model / ceinms_model legitimately do not exist until scaling
            # has run, so a miss there is amber, not red. `generic` is an
            # INPUT — if that is missing, nothing can run.
            mark.configure(text="⚠",
                           text_color=_MISS if key == "generic" else "#e5b567")

    def _save_iteration(self):
        d, it = self._session_dir(), self._ed_iter.get()
        if not d or it == "—":
            return
        changed = []
        try:
            from bioscout.utils.session_form import SessionForm
            form = SessionForm(str(d))
            for key, (var, kind, old, _m) in self._ed_vars.items():
                if kind == "bool":
                    new = bool(var.get())
                    if old is not None and bool(old) == new:
                        continue
                    if old is None and new is False:
                        continue          # don't write a default nobody set
                else:
                    raw = var.get().strip()
                    if raw == ("" if old is None else str(old)):
                        continue
                    if raw == "":
                        continue          # clearing a key is a delete, not a set
                    if kind == "number":
                        try:
                            new = float(raw) if "." in raw else int(raw)
                        except ValueError:
                            self.status_callback(
                                f"{key}: '{raw}' is not a number", "error")
                            return
                    else:
                        new = raw
                form.set_iteration_field(it, key, new)
                changed.append(f"{key}: {old!r} -> {new!r}")
            if not changed:
                self.status_callback("Nothing changed", "info")
                return
            # Show what is about to be written BEFORE writing it — the same
            # habit the CEINMS Setup tab uses, and the reason a bad edit here
            # has never silently reached disk.
            self._dump(f"{d / 'session.yaml'}  —  iteration '{it}'\n\n"
                       + "\n".join("  " + c for c in changed)
                       + "\n\n" + (form.diff() or "(no textual diff)"))
            form.save(backup=True)
        except Exception as exc:                               # noqa: BLE001
            self.status_callback(f"{type(exc).__name__}: {exc}", "error")
            return
        self.refresh()
        self._load_iteration()
        self.status_callback(f"Saved {len(changed)} change(s) to '{it}'",
                             "success")

    def _diff_iteration(self):
        d, it = self._session_dir(), self._ed_iter.get()
        if not d or it == "—":
            return
        try:
            from bioscout.utils.session_form import SessionForm
            form = SessionForm(str(d))
            for key, (var, kind, old, _m) in self._ed_vars.items():
                if kind == "bool":
                    new = bool(var.get())
                    if (old is not None and bool(old) == new) or \
                            (old is None and new is False):
                        continue
                else:
                    raw = var.get().strip()
                    if raw == ("" if old is None else str(old)) or raw == "":
                        continue
                    new = (float(raw) if kind == "number" and "." in raw
                           else int(raw) if kind == "number" else raw)
                form.set_iteration_field(it, key, new)
            self._dump(form.diff() or "No changes.")
        except Exception as exc:                               # noqa: BLE001
            self._dump(f"{type(exc).__name__}: {exc}")

    # -- right: run --------------------------------------------------------
    def _build_right(self, parent):
        right = ctk.CTkFrame(parent, fg_color="#12121a", corner_radius=8)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_rowconfigure(3, weight=1)
        right.grid_columnconfigure(0, weight=1)

        # ---- iterations ---------------------------------------------------
        hdr = ctk.CTkFrame(right, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 2))
        hdr.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(hdr, text="Iterations", font=("Segoe UI", 12, "bold"),
                     text_color="#dddddd").grid(row=0, column=0, sticky="w")
        ctk.CTkButton(hdr, text="all", width=40, height=22,
                      font=("Segoe UI", 10), fg_color="#3a3a4a",
                      hover_color="#4a4a5a",
                      command=lambda: self._set_all(self._iter_vars, True)
                      ).grid(row=0, column=2, padx=2)
        ctk.CTkButton(hdr, text="none", width=48, height=22,
                      font=("Segoe UI", 10), fg_color="#3a3a4a",
                      hover_color="#4a4a5a",
                      command=lambda: self._set_all(self._iter_vars, False)
                      ).grid(row=0, column=3)
        self._iter_box = ctk.CTkScrollableFrame(right, fg_color="#161620",
                                                height=110)
        self._iter_box.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 6))

        # ---- trials -------------------------------------------------------
        hdr2 = ctk.CTkFrame(right, fg_color="transparent")
        hdr2.grid(row=2, column=0, sticky="ew", padx=10, pady=(4, 2))
        hdr2.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(hdr2, text="Trials", font=("Segoe UI", 12, "bold"),
                     text_color="#dddddd").grid(row=0, column=0, sticky="w")
        ctk.CTkButton(hdr2, text="all", width=40, height=22,
                      font=("Segoe UI", 10), fg_color="#3a3a4a",
                      hover_color="#4a4a5a",
                      command=lambda: self._set_all(self._trial_vars, True)
                      ).grid(row=0, column=2, padx=2)
        ctk.CTkButton(hdr2, text="none", width=48, height=22,
                      font=("Segoe UI", 10), fg_color="#3a3a4a",
                      hover_color="#4a4a5a",
                      command=lambda: self._set_all(self._trial_vars, False)
                      ).grid(row=0, column=3)
        self._trial_box = ctk.CTkScrollableFrame(right, fg_color="#161620",
                                                 height=140)
        self._trial_box.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 6))

        # ---- stages -------------------------------------------------------
        ctk.CTkLabel(right, text="Stages", font=("Segoe UI", 12, "bold"),
                     text_color="#dddddd").grid(row=4, column=0, sticky="w",
                                                padx=10, pady=(4, 2))
        stages = ctk.CTkFrame(right, fg_color="transparent")
        stages.grid(row=5, column=0, sticky="ew", padx=10)
        stages.grid_columnconfigure(0, weight=1)
        stages.grid_columnconfigure(1, weight=1)
        entries = ([(k, lab) for k, lab, kw in STAGES if kw] +
                   [(k, lab) for k, lab, kw in EXTRA_RUN])
        # export first, it is the one that is session-level
        entries = [("export", "export c3d")] + entries
        for i, (key, label) in enumerate(entries):
            v = ctk.BooleanVar(value=False)
            self._stage_vars[key] = v
            ctk.CTkCheckBox(stages, text=label, variable=v,
                            font=("Segoe UI", 11), checkbox_width=18,
                            checkbox_height=18).grid(
                row=i // 2, column=i % 2, sticky="w", pady=2)

        self._replace_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(right, text="overwrite existing", variable=self._replace_var,
                        font=("Segoe UI", 11)).grid(row=6, column=0, sticky="w",
                                                    padx=14, pady=(8, 0))

        self._run_btn = ctk.CTkButton(right, text="▶  Run this session",
                                      height=32, font=("Segoe UI", 12),
                                      fg_color="#28a745", hover_color="#218838",
                                      command=self._run)
        self._run_btn.grid(row=7, column=0, sticky="ew", padx=10, pady=(8, 4))

        self._check_btn = ctk.CTkButton(
            right, text="✓  Check (no run, no output)", height=28,
            font=("Segoe UI", 11), fg_color="#2f6f9f", hover_color="#3a86bd",
            command=self._check)
        self._check_btn.grid(row=8, column=0, sticky="ew", padx=10, pady=(0, 10))

    @staticmethod
    def _set_all(varmap: Dict[str, ctk.BooleanVar], state: bool):
        for v in varmap.values():
            v.set(state)

    # ---------------------------------------------------------- selection
    def set_project_dir(self, project_dir: str) -> None:
        if project_dir:
            self._project_root = Path(project_dir)
            sims = self._sims()
            opts = sorted(p.name for p in sims.iterdir() if p.is_dir()) \
                if sims else []
            self._subj_menu.configure(values=opts or ["—"])
            self._subj_var.set((opts or ["—"])[0])
            # The embedded trial view is not in main_window.tabs, so the
            # project broadcast never reaches it — forward it here or its
            # pickers stay empty forever.
            if getattr(self, "_trial_view", None) is not None:
                try:
                    self._trial_view.set_project_dir(project_dir)
                except Exception:                              # noqa: BLE001
                    pass

    def _sims(self) -> Optional[Path]:
        if not self._project_root:
            return None
        p = _simulations_root(self._project_root,
                              getattr(self, "config_manager", None))
        return p if p and Path(p).is_dir() else None

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
        self.refresh()

    def refresh(self, *_):
        d = self._session_dir()
        self._cfg = _read_yaml(d / "session.yaml") if d else {}
        self._fill_iterations()
        self._fill_trials()
        self._render_overview()
        view = self._view.get()
        if view == "Coverage":
            self._render_coverage()
        elif view == "Iteration":
            self._load_iteration()
        elif view == "Trial":
            self._sync_trial_view()

    # --------------------------------------------------------- inventory
    def _iterations(self) -> List[str]:
        """On disk ∪ declared — the same union Session.iterations does.

        A declared-but-not-yet-scaled iteration must appear, or adding a model
        arm to session.yaml looks like it did nothing.
        """
        d = self._session_dir()
        found: List[str] = []
        if d:
            try:
                L = _layout()
                root = Path(L.iterations_root(str(d)))
                if root.is_dir():
                    found = sorted(p.name for p in root.iterdir()
                                   if p.is_dir()
                                   and p.name not in L.NON_ITERATION_DIRS
                                   and not p.name.startswith(".")
                                   and "_backup_" not in p.name)
            except Exception:                                  # noqa: BLE001
                pass
        for name in (self._cfg.get("iterations") or {}):
            if name not in found:
                found.append(name)
        return found

    def _trials(self) -> List[str]:
        d = self._session_dir()
        if not d:
            return []
        try:
            from bioscout.gui.widgets.results_viewer import _layout_trials
            return list(_layout_trials(d))
        except Exception:                                      # noqa: BLE001
            return sorted(self._cfg.get("trials") or {})

    def _exp_root(self) -> Optional[Path]:
        d = self._session_dir()
        if not d:
            return None
        try:
            return Path(_layout().experimental_root(str(d)))
        except Exception:                                      # noqa: BLE001
            return None

    def _fill_iterations(self):
        for w in self._iter_box.winfo_children():
            w.destroy()
        self._iter_vars = {}
        names = self._iterations()
        for i, name in enumerate(names):
            v = ctk.BooleanVar(value=(i == 0))
            self._iter_vars[name] = v
            ctk.CTkCheckBox(self._iter_box, text=name, variable=v,
                            font=("Segoe UI", 11), checkbox_width=18,
                            checkbox_height=18).grid(row=i, column=0,
                                                     sticky="w", pady=1, padx=4)
        if not names:
            ctk.CTkLabel(self._iter_box, text="no iterations yet",
                         font=("Segoe UI", 11), text_color="#777777"
                         ).grid(row=0, column=0, sticky="w", padx=6, pady=6)
        self._cov_menu.configure(values=names or ["—"])
        if self._cov_iter.get() not in names:
            self._cov_iter.set((names or ["—"])[0])
        self._ed_menu.configure(values=names or ["—"])
        if self._ed_iter.get() not in names:
            self._ed_iter.set((names or ["—"])[0])

    def _fill_trials(self):
        for w in self._trial_box.winfo_children():
            w.destroy()
        self._trial_vars = {}
        names = self._trials()
        for i, name in enumerate(names):
            v = ctk.BooleanVar(value=True)
            self._trial_vars[name] = v
            ctk.CTkCheckBox(self._trial_box, text=name, variable=v,
                            font=("Segoe UI", 11), checkbox_width=18,
                            checkbox_height=18).grid(row=i, column=0,
                                                     sticky="w", pady=1, padx=4)
        if not names:
            ctk.CTkLabel(self._trial_box, text="no trials found",
                         font=("Segoe UI", 11), text_color="#777777"
                         ).grid(row=0, column=0, sticky="w", padx=6, pady=6)

    # ---------------------------------------------------------- overview
    def _card(self, row: int, title: str) -> ctk.CTkFrame:
        box = ctk.CTkFrame(self._overview, fg_color="#161620", corner_radius=8)
        box.grid(row=row, column=0, sticky="ew", pady=(0, 8), padx=2)
        box.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(box, text=title, font=("Segoe UI", 11, "bold"),
                     text_color="#7fb2e5").grid(row=0, column=0, columnspan=2,
                                                sticky="w", padx=10, pady=(8, 4))
        return box

    @staticmethod
    def _kv(box, row: int, key: str, value: str, colour="#dddddd"):
        ctk.CTkLabel(box, text=key, font=("Segoe UI", 11), anchor="w",
                     text_color="#8a8a8a", width=130).grid(
            row=row, column=0, sticky="w", padx=(14, 6), pady=1)
        ctk.CTkLabel(box, text=value, font=("Consolas", 11), anchor="w",
                     text_color=colour, justify="left").grid(
            row=row, column=1, sticky="w", pady=1, padx=(0, 10))

    def _render_overview(self):
        for w in self._overview.winfo_children():
            w.destroy()
        d = self._session_dir()
        if not d:
            ctk.CTkLabel(self._overview,
                         text="Pick a subject and a session.",
                         font=("Segoe UI", 11), text_color="#888888"
                         ).grid(row=0, column=0, sticky="w", padx=8, pady=10)
            self._note.configure(text="")
            return
        cfg = self._cfg

        # ---- the session itself -------------------------------------------
        box = self._card(0, "session")
        r = 1
        self._kv(box, r, "path", str(d)); r += 1
        for key in ("subject", "body_mass", "static_trial", "markerset"):
            if cfg.get(key) is not None:
                self._kv(box, r, key, str(cfg[key])); r += 1
        if not cfg:
            self._kv(box, r, "session.yaml", "MISSING or unreadable", _MISS)
            r += 1
        emg = cfg.get("emg_map") or {}
        self._kv(box, r, "emg_map",
                 f"{len(emg)} entry(ies)" if emg else "none",
                 "#dddddd" if emg else "#777777")
        r += 1
        ctk.CTkLabel(box, text="", height=4).grid(row=r, column=0)

        # ---- trials by type ------------------------------------------------
        trials_cfg = cfg.get("trials") or {}
        on_disk = self._trials()
        raw_cal, raw_nrm = (cfg.get("calibration_trials"),
                            cfg.get("normalisation_trials"))
        cal = set(_as_list(raw_cal))
        nrm = set(_as_list(raw_nrm))
        # "all" means every trial has the role. Badging all 11 of them says
        # nothing; one line does.
        all_cal, all_nrm = _is_all(raw_cal), _is_all(raw_nrm)
        static = str(cfg.get("static_trial") or "")

        by_type: Dict[str, List[str]] = {}
        for name in on_disk:
            meta = trials_cfg.get(name) or {}
            t = str(meta.get("type") or "?")
            by_type.setdefault(t, []).append(name)

        box = self._card(1, f"trials — {len(on_disk)} on disk, "
                            f"{len(trials_cfg)} declared")
        r = 1
        for t in sorted(by_type):
            names = by_type[t]
            self._kv(box, r, f"{t}  ×{len(names)}", "", "#dddddd"); r += 1
            for name in names:
                roles = []
                if name == static:
                    roles.append("static")
                if name in cal:
                    roles.append("calibration")
                if name in nrm:
                    roles.append("normalisation")
                declared = name in trials_cfg
                txt = "   " + name + (f"   [{', '.join(roles)}]" if roles else "")
                if not declared:
                    # On disk but with no session.yaml block: it has no type
                    # and no time_range, so every stage will take the whole
                    # capture for it. Worth seeing here rather than finding out
                    # from a 40-second IK.
                    txt += "   (not in session.yaml)"
                ctk.CTkLabel(box, text=txt, font=("Consolas", 11), anchor="w",
                             text_color=("#e5b567" if not declared
                                         else "#9ad0f5" if roles else "#bbbbbb")
                             ).grid(row=r, column=0, columnspan=2, sticky="w",
                                    padx=(14, 10), pady=1)
                r += 1
        if not on_disk:
            self._kv(box, r, "", "no trials found", "#777777"); r += 1
        for label, is_all in (("calibration_trials", all_cal),
                              ("normalisation_trials", all_nrm)):
            if is_all:
                self._kv(box, r, label, "all trials", "#9ad0f5"); r += 1
        # A role naming a trial that does not exist is silent until the stage
        # that needs it finds nothing — say it here.
        for label, names in (("calibration_trials", cal),
                             ("normalisation_trials", nrm)):
            ghosts = sorted(n for n in names if n not in on_disk)
            if ghosts:
                self._kv(box, r, label,
                         f"names {len(ghosts)} trial(s) not on disk: "
                         + ", ".join(ghosts[:4]), _MISS)
                r += 1
        ctk.CTkLabel(box, text="", height=4).grid(row=r, column=0)

        # ---- iterations ----------------------------------------------------
        its = self._iterations()
        box = self._card(2, f"iterations — {len(its)}")
        r = 1
        iters_cfg = cfg.get("iterations") or {}
        for name in its:
            block = iters_cfg.get(name) or {}
            models = [str(block[k]) for k in ("so_model", "ceinms_model")
                      if block.get(k)]
            folder = None
            try:
                folder = Path(_layout().iteration_path(str(d), name))
            except Exception:                                  # noqa: BLE001
                pass
            bits = []
            if not block:
                bits.append("on disk, NOT declared")
            elif folder is not None and not folder.is_dir():
                bits.append("declared, no folder yet")
            self._kv(box, r, name,
                     ("  ".join(models) if models else "no model named")
                     + (f"   [{'; '.join(bits)}]" if bits else ""),
                     "#e5b567" if bits else "#bbbbbb")
            r += 1
        if not its:
            self._kv(box, r, "", "none — scale a model first", "#777777")
            r += 1
        ctk.CTkLabel(box, text="", height=4).grid(row=r, column=0)

        self._note.configure(
            text=f"{len(on_disk)} trial(s) · {len(its)} iteration(s)",
            text_color="#8a8a8a")

    # ---------------------------------------------------------- coverage
    def _render_coverage(self):
        for w in self._cov_grid.winfo_children():
            w.destroy()
        d, it = self._session_dir(), self._cov_iter.get()
        if not d or it == "—":
            ctk.CTkLabel(self._cov_grid,
                         text="Pick a session and an iteration.",
                         font=("Segoe UI", 11), text_color="#888888"
                         ).grid(row=0, column=0, sticky="w", padx=8, pady=10)
            self._cov_note.configure(text="")
            return
        trials = self._trials()
        if not trials:
            ctk.CTkLabel(self._cov_grid, text="No trials in this session.",
                         font=("Segoe UI", 11), text_color="#888888"
                         ).grid(row=0, column=0, sticky="w", padx=8, pady=10)
            return
        try:
            rc = _run_check()
            it_dir = Path(_layout().iteration_path(str(d), it))
            rep = rc.verify_run(str(it_dir), trials,
                                [k for k, _l, _kw in STAGES],
                                experimental_dir=str(self._exp_root() or ""))
        except Exception as exc:                               # noqa: BLE001
            ctk.CTkLabel(self._cov_grid,
                         text=f"{type(exc).__name__}: {exc}",
                         font=("Segoe UI", 11), text_color=_MISS
                         ).grid(row=0, column=0, sticky="w", padx=8, pady=10)
            return

        # header
        ctk.CTkLabel(self._cov_grid, text="trial", font=("Segoe UI", 10, "bold"),
                     text_color="#8a8a8a", anchor="w", width=210
                     ).grid(row=0, column=0, sticky="w", padx=(6, 4), pady=(2, 6))
        for c, (_key, label, _kw) in enumerate(STAGES, start=1):
            ctk.CTkLabel(self._cov_grid, text=label,
                         font=("Segoe UI", 10, "bold"), text_color="#8a8a8a",
                         width=70).grid(row=0, column=c, padx=2, pady=(2, 6))

        # The static trial has no kinetics by definition: it exists to scale a
        # model, and IK/ID/MA/SO/CEINMS are never run on it. Reporting four
        # MISSes for it is a false alarm, and a grid that cries wolf on every
        # session is a grid nobody reads. Marked n/a and left out of the count.
        static = str(self._cfg.get("static_trial") or "")
        na = 0

        for r, tn in enumerate(trials, start=1):
            row = rep["trials"].get(tn, {})
            is_static = bool(static) and tn == static
            ctk.CTkLabel(self._cov_grid, text=tn + ("  (static)" if is_static else ""),
                         font=("Consolas", 11), anchor="w",
                         text_color="#9ad0f5" if is_static else "#cccccc",
                         width=210).grid(row=r, column=0, sticky="w",
                                         padx=(6, 4), pady=1)
            for c, (key, _label, _kw) in enumerate(STAGES, start=1):
                if is_static and key != "export":
                    txt, col = "–", _NA
                    na += 1
                    ctk.CTkLabel(self._cov_grid, text=txt,
                                 font=("Consolas", 11), text_color=col,
                                 width=70).grid(row=r, column=c, padx=2, pady=1)
                    continue
                ok = row.get(key)
                txt = "ok" if ok else "MISS"
                col = _OK if ok else _MISS
                # Clickable: the cell already knows exactly which folder it is
                # asserting about, so making you navigate there by hand is
                # asking the question and withholding the answer. A MISS opens
                # the parent, which is where you look to see what IS there.
                ctk.CTkButton(
                    self._cov_grid, text=txt, width=70, height=22,
                    font=("Consolas", 11), text_color=col,
                    fg_color="transparent", hover_color="#2a2a38",
                    command=lambda t=tn, k=key: self._open_stage_dir(t, k)
                ).grid(row=r, column=c, padx=2, pady=1)

        n_missing = len([m for m in rep["missing"]
                         if not (static and m[0] == static and m[1] != "export")])
        total = len(trials) * len(STAGES) - na
        self._cov_note.configure(
            text=("every stage produced output" if not n_missing
                  else f"{n_missing} of {total} missing — this iteration is "
                       f"NOT complete"),
            text_color=_OK if not n_missing else "#e5b567")

    def _open_stage_dir(self, trial: str, stage: str):
        """Open the folder the Summary grid just reported on."""
        d, it = self._session_dir(), self._cov_iter.get()
        if not d:
            return
        where, sub = STAGE_DIRS.get(stage, ("iter", ""))
        if where == "exp":
            base = self._exp_root()
            if base is None:
                self.status_callback("No experimental folder for this session",
                                     "warning")
                return
            target = base / trial
        else:
            if it == "—":
                return
            try:
                target = Path(_layout().iteration_path(str(d), it)) / trial
            except Exception as exc:                           # noqa: BLE001
                self.status_callback(f"{type(exc).__name__}: {exc}", "error")
                return
        if sub:
            target = target / sub
        err = _open_in_explorer(target)
        self.status_callback(err or f"Opened {target}",
                             "error" if err else "info")

    # --------------------------------------------------------------- run
    def _check(self):
        """A ghost run: everything the stages would READ, verified, nothing written.

        This is docs/IMPLEMENTATIONS.md §2.2 "preflight as a first-class stage",
        scoped to what is ticked on the right. It replaced a Describe button
        that dumped the whole session inventory — an inventory answers "what is
        here", which is not the question you have before pressing Run. The
        question is "will this fail, and on what", and the only useful answer
        is a short list of problems or silence.

        Reports PROBLEMS ONLY. A clean session prints one line.
        """
        if self._running:
            self.status_callback("A run is in progress", "warning")
            return
        d = self._session_dir()
        if not d:
            self.status_callback("Pick a session first", "warning")
            return
        iters = [k for k, v in self._iter_vars.items() if v.get()]
        trials = [k for k, v in self._trial_vars.items() if v.get()]
        stages = [k for k, v in self._stage_vars.items() if v.get()]
        self._check_btn.configure(state="disabled", text="checking…")
        what = ", ".join(stages) or "(none ticked — checking inputs only)"
        self._dump(f"Checking {d}\n"
                   f"  {len(trials)} trial(s), {len(iters)} iteration(s), "
                   f"stages: {what}\n")

        def work():
            try:
                out = self._collect_problems(d, iters, trials, stages)
            except Exception:
                import traceback
                out = [("ERROR", "check itself failed:\n" + traceback.format_exc())]
            self.after(0, lambda: self._check_done(out))

        threading.Thread(target=work, daemon=True).start()

    def _collect_problems(self, d: Path, iters: List[str], trials: List[str],
                          stages: List[str]) -> List[Tuple[str, str]]:
        """-> [(severity, message)] where severity is BLOCK / WARN.

        BLOCK = this cannot work. WARN = it will run but probably not mean what
        you think. Runs on a worker thread; touches nothing but the filesystem
        and the yaml.
        """
        out: List[Tuple[str, str]] = []
        yml = d / "session.yaml"

        # -- the file itself -------------------------------------------------
        if not yml.is_file():
            return [("BLOCK", f"no session.yaml in {d}")]
        try:
            rc = _run_check()
            dups = rc.duplicate_yaml_keys(yml.read_text(encoding="utf-8"))
            for key, a, b in dups:
                out.append(("BLOCK", f"session.yaml: duplicate key '{key}' on "
                                     f"lines {a} and {b} — YAML keeps only the "
                                     f"last, so the run reads the wrong value"))
        except Exception as exc:                               # noqa: BLE001
            out.append(("WARN", f"could not scan session.yaml for duplicate "
                                f"keys: {type(exc).__name__}: {exc}"))

        # -- everything SessionForm already knows how to complain about ------
        try:
            from bioscout.utils.session_form import SessionForm
            for p in SessionForm(str(d)).problems():
                # problems() SHOUTS the ones that stop a run ("NO C3D FILES",
                # "DUPLICATE emg_map key(s)") and phrases the rest in lower
                # case. Reusing its own convention beats re-classifying its
                # messages here and drifting from it.
                out.append(("BLOCK" if p[:2].isupper() else "WARN", p))
        except Exception as exc:                               # noqa: BLE001
            out.append(("WARN", f"session form checks skipped: "
                                f"{type(exc).__name__}: {exc}"))

        cfg = self._cfg or {}
        tcfg = cfg.get("trials") or {}
        exp = self._exp_root()

        # -- per-trial inputs -------------------------------------------------
        for tn in trials:
            block = tcfg.get(tn)
            if block is None:
                out.append(("WARN", f"{tn}: no block in session.yaml — it has "
                                    f"no type and no time_range, so every "
                                    f"stage takes the whole capture"))
                block = {}
            if not block.get("time_range"):
                out.append(("WARN", f"{tn}: no time_range — the whole capture "
                                    f"will be solved"))
            if exp is not None and (exp / tn).is_dir():
                for need, why in (("marker_experimental.trc", "IK has no markers"),
                                  ("grf.mot", "ID has no ground reaction"),
                                  ("GRF.xml", "ID has no external loads")):
                    if not (exp / tn / need).is_file():
                        out.append(("BLOCK", f"{tn}: {need} missing — {why}. "
                                             f"Run export first."))
            elif "export" not in stages:
                out.append(("BLOCK", f"{tn}: nothing exported "
                                     f"(2_experimental/{tn}/ absent) and export "
                                     f"is not ticked"))

        # -- per-iteration models ---------------------------------------------
        icfg = cfg.get("iterations") or {}
        needs_model = any(s in stages for s in
                          ("exbiomec", "muscle_analysis", "so", "ceinms"))
        for it in iters:
            block = icfg.get(it)
            if block is None:
                out.append(("WARN", f"iteration '{it}' is on disk but not in "
                                    f"session.yaml — it names no model"))
                continue
            if "scale" in stages and not block.get("generic"):
                out.append(("BLOCK", f"{it}: no 'generic' model, so scaling "
                                     f"has nothing to scale"))
            if "scale" in stages and block.get("generic"):
                if self._resolve_model_for(it, "generic",
                                           str(block["generic"])) is None:
                    out.append(("BLOCK", f"{it}: generic model "
                                         f"'{block['generic']}' resolves "
                                         f"nowhere"))
            if not needs_model:
                continue
            for key in ("so_model", "ceinms_model"):
                if key == "ceinms_model" and "ceinms" not in stages:
                    continue
                if key == "so_model" and not any(
                        s in stages for s in ("exbiomec", "muscle_analysis", "so")):
                    continue
                val = block.get(key)
                if not val:
                    out.append(("BLOCK", f"{it}: no '{key}' named"))
                    continue
                if self._resolve_model_for(it, key, str(val)) is None:
                    out.append(("BLOCK", f"{it}: {key} '{val}' does not exist "
                                         f"— scale this iteration first"))

        # -- EMG, only when CEINMS is actually wanted -------------------------
        if "ceinms" in stages:
            emg_map = cfg.get("emg_map") or {}
            if not emg_map:
                out.append(("BLOCK", "CEINMS is ticked but session.yaml has no "
                                     "emg_map"))
            else:
                labels = self._analog_labels(exp, trials)
                if labels:
                    try:
                        v = _run_check().validate_emg_map(list(emg_map), labels)
                        for m in v["missing"]:
                            out.append(("BLOCK", f"emg_map channel '{m}' exists "
                                                 f"in no exported EMG"))
                        for bare, better in v["suspicious"]:
                            out.append(("WARN", f"emg_map uses '{bare}' but "
                                                f"'{better}' also exists — the "
                                                f"tagged column is usually the "
                                                f"conditioned signal"))
                    except Exception:                          # noqa: BLE001
                        pass
                else:
                    out.append(("WARN", "no exported EMG found to check the "
                                        "emg_map against"))
            if not _as_list(cfg.get("calibration_trials")) and \
                    not _is_all(cfg.get("calibration_trials")):
                out.append(("WARN", "no calibration_trials — CEINMS will use "
                                    "whatever the default calibration names"))

        # -- Windows MAX_PATH -------------------------------------------------
        # PREDICTED, not measured. run_check.long_paths walks the whole session
        # tree — 11,630 files and 11 s on the real Powerlifting session, and it
        # grows with every result written, so a check that promises to fail in
        # seconds cannot use it. It also answers the wrong question: what
        # matters is the longest path this run WILL CREATE, which by definition
        # is not on disk yet. Composing it costs nothing and is exact.
        try:
            import os as _os
            try:
                it_root = str(Path(_layout().iterations_root(str(d))))
            except Exception:                                  # noqa: BLE001
                it_root = str(d / "3_iterations")
            deepest = _os.path.join("ceinms", "Execution_a10_b1_g1000",
                                    "MuscleForces.sto")
            worst = _os.path.join(it_root,
                                  max(iters, key=len) if iters else "",
                                  max(trials, key=len) if trials else "",
                                  deepest)
            if len(worst) > 260:
                out.append(("BLOCK", f"the deepest output this run would write "
                                     f"is {len(worst)} chars, over the Windows "
                                     f"260 limit — it will fail as "
                                     f"'file not found' inside OpenSim: "
                                     f"…{worst[-70:]}"))
            elif len(worst) > 220:
                out.append(("WARN", f"the deepest output this run would write "
                                    f"is {len(worst)} chars — within 40 of the "
                                    f"Windows 260 limit: …{worst[-70:]}"))
        except Exception:                                      # noqa: BLE001
            pass

        # -- can the solver even load? -----------------------------------------
        if stages and stages != ["export"]:
            try:
                import importlib.util
                if importlib.util.find_spec("opensim") is None:
                    out.append(("BLOCK", "opensim is not importable — no "
                                         "solving stage can run in this "
                                         "environment (`bioscout --env`)"))
            except Exception:                                  # noqa: BLE001
                pass
        return out

    def _resolve_model_for(self, it: str, key: str, value: str) -> Optional[Path]:
        """Alias kept for readability at the call sites in the checker."""
        return self._resolve_model_in(it, key, value)

    def _resolve_model_in(self, it: str, key: str, value: str) -> Optional[Path]:
        d = self._session_dir()
        if not value or not d:
            return None
        p = Path(value)
        if p.is_absolute():
            return p if p.exists() else None
        if key == "generic":
            root = self._project_root
            if not root:
                return None
            for base in (root / "generic models", root / "generic_models",
                         root / "models", root):
                if (base / value).exists():
                    return base / value
            return None
        try:
            cand = Path(_layout().iteration_path(str(d), it)) / value
            if cand.exists():
                return cand
        except Exception:                                      # noqa: BLE001
            pass
        return (d / value) if (d / value).exists() else None

    @staticmethod
    def _analog_labels(exp: Optional[Path], trials: List[str]) -> List[str]:
        """Column names from the exported EMG .mot files — the labels an
        emg_map has to match. Header-only read; no pandas, no full parse."""
        labels: set = set()
        if exp is None:
            return []
        for tn in trials:
            for name in ("emg_filtered.mot", "emg.mot",
                         "emg_filtered_normalised.mot"):
                f = exp / tn / name
                if not f.is_file():
                    continue
                try:
                    with open(f, "r", encoding="utf-8", errors="replace") as fh:
                        for line in fh:
                            if line.strip().lower() == "endheader":
                                head = fh.readline()
                                labels |= {c for c in head.split()
                                           if c.lower() != "time"}
                                break
                except Exception:                              # noqa: BLE001
                    pass
                break
        return sorted(labels)

    def _check_done(self, problems: List[Tuple[str, str]]):
        self._check_btn.configure(state="normal",
                                  text="✓  Check (no run, no output)")
        blocks = [m for s, m in problems if s == "BLOCK"]
        warns = [m for s, m in problems if s != "BLOCK"]
        lines = []
        if blocks:
            lines.append(f"{len(blocks)} BLOCKER(S) — this will not work:")
            lines += [f"  ✗ {m}" for m in blocks]
        if warns:
            if blocks:
                lines.append("")
            lines.append(f"{len(warns)} warning(s) — it will run, "
                         f"check it means what you think:")
            lines += [f"  ! {m}" for m in warns]
        if not problems:
            lines.append("No problems found. Everything the ticked stages "
                         "would read is present and resolves.")
        self._dump("\n".join(lines))
        if blocks:
            self.status_callback(f"{len(blocks)} blocker(s) — see the panel",
                                 "error")
        elif warns:
            self.status_callback(f"{len(warns)} warning(s) — see the panel",
                                 "warning")
        else:
            self.status_callback("Check passed", "success")

    def _dump(self, text: str):
        self._detail.delete("1.0", "end")
        self._detail.insert("1.0", text + "\n")

    def _run(self):
        if self._running:
            self.status_callback("Already running", "warning")
            return
        d = self._session_dir()
        if not d:
            self.status_callback("Pick a session first", "warning")
            return
        iters = [k for k, v in self._iter_vars.items() if v.get()]
        trials = [k for k, v in self._trial_vars.items() if v.get()]
        stages = [k for k, v in self._stage_vars.items() if v.get()]
        if not stages:
            self.status_callback("Tick at least one stage", "warning")
            return
        if not trials:
            self.status_callback("Tick at least one trial", "warning")
            return
        want_export = "export" in stages
        per_iter = [s for s in stages if s != "export"]
        if per_iter and not iters:
            self.status_callback("Tick at least one iteration", "warning")
            return

        n = len(trials) * max(len(iters), 1)
        if not messagebox.askyesno(
                "Run session",
                f"{', '.join(stages)}\n\n"
                f"{len(trials)} trial(s) × {len(iters) or 1} iteration(s) "
                f"= up to {n} unit(s) of work.\n"
                f"overwrite existing: {self._replace_var.get()}\n\nProceed?",
                parent=self):
            return

        kwargs = {kw: (key in stages)
                  for key, _l, kw in STAGES + EXTRA_RUN if kw}
        kwargs["replace"] = self._replace_var.get()
        # As in Trial Analysis: re-running CEINMS here executes against the
        # calibration that exists. Calibrating is its own tab, because doing it
        # implicitly from a batch re-run is how an arm silently gets a
        # calibration built from a different trial set than the one it reports.
        kwargs["calibrate"] = False

        self._running = True
        self._run_btn.configure(state="disabled", text="running…")
        self._dump(f"session : {d}\n"
                   f"stages  : {', '.join(stages)}\n"
                   f"trials  : {len(trials)}\n"
                   f"models  : {', '.join(iters) or '(export only)'}\n"
                   f"(CEINMS calibration is reused, not re-run)\n")

        def work():
            err = None
            try:
                from bioscout import Session
                s = Session.open(str(d))
                if want_export:
                    s.export(trials=trials, replace=self._replace_var.get())
                if per_iter and iters:
                    s.run(iterations=iters, trials=trials, **kwargs)
            except Exception:          # surfaced in the panel, never raised
                import traceback
                err = traceback.format_exc()
            self.after(0, lambda: self._done(err))

        threading.Thread(target=work, daemon=True).start()

    def _done(self, err: Optional[str]):
        self._running = False
        self._run_btn.configure(state="normal", text="▶  Run this session")
        if err:
            self._detail.insert("end", "\n" + err)
            self.status_callback("Session run failed — see the panel", "error")
        else:
            self.status_callback("Session run finished", "success")
        # Whatever just ran changed what is on disk, so the grid that claims to
        # show what is on disk must be rebuilt. Refreshing only the coverage
        # view is the point of it being a filesystem check.
        self._render_coverage()
        self._render_overview()
