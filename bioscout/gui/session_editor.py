"""The session editor behind ``bioscout session new`` and ``bioscout session edit``.

Opens on a session folder, and does the obvious right thing:

* **there is already a ``session.yaml``** — load it and edit in place, rather than
  offering to create the file that is already there
* **``1_c3dfiles/`` is empty** — say so in red at the top, because every other
  field is meaningless until captures exist
* everything else the session declares is editable, with the widget the field
  deserves: a dropdown for the static trial and each trial's type, tick boxes for
  the calibration and normalisation sets

The trial table is one row per trial rather than three separate lists. Static
trial, calibration set and normalisation set are all *choices about the same
trials*, and splitting them across three panes makes the one question you
actually ask — "what is this trial for?" — need three lookups.

Saving goes through :class:`bioscout.utils.session_form.SessionForm`, which
patches character spans. It never re-dumps the YAML, so the comment block
explaining the study survives, and so does every line you did not touch.

Iterations get a block each — the model files, the calibration selector, the
prescaled/linear_scaling pair, and add / duplicate / remove. Duplicating an arm
and changing one model path is the whole two-arm comparison workflow, and it was
being done by hand in a text editor.

``emg_map`` stays read-only with a count. It is a two-level mapping of electrode
to muscle list; the File Editor tab already edits arbitrary YAML surgically, and
pretending that fits a checkbox row would be worse than saying where to go.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

__all__ = ["open_session_editor", "ask_new_session", "gui_available"]

_RED = "#c0392b"
_BLUE = "#2a78d6"
_MUTED = "gray40"
#: Every second trial row is tinted. With sixty trials and five ungrouped
#: tick columns, "which checkbox belongs to which trial" is a real question;
#: a band is the cheapest answer. Dark-theme-safe (CTk's own surface colours
#: sit either side of it, so it reads as a tint in both modes).
_ROW_TINT = "#2b3138"


def gui_available() -> bool:
    try:
        import tkinter
        root = tkinter.Tk()
        root.withdraw()
        root.destroy()
        return True
    except Exception:
        return False


def _widgets():
    """(tk, filedialog, messagebox, themed) — customtkinter when it is installed."""
    import tkinter as tk
    from tkinter import filedialog, messagebox
    try:
        import customtkinter as ctk
        ctk.set_appearance_mode("system")
        return tk, filedialog, messagebox, ctk
    except Exception:
        return tk, filedialog, messagebox, None


def open_session_editor(session_dir=None) -> int:                 # noqa: C901 — a form
    """Show the editor. Returns a process exit code."""
    from bioscout.utils.session_form import (EMG_FILTER_FIELDS, ITERATION_FIELDS,
                                             SCALAR_FIELDS, TRIAL_TYPES, SessionForm)

    tk, filedialog, messagebox, ctk = _widgets()
    try:
        root = (ctk.CTk() if ctk else tk.Tk())
    except Exception:
        return 1

    Frame = ctk.CTkFrame if ctk else tk.Frame
    Label = ctk.CTkLabel if ctk else tk.Label
    Entry = ctk.CTkEntry if ctk else tk.Entry
    Button = ctk.CTkButton if ctk else tk.Button
    Check = ctk.CTkCheckBox if ctk else tk.Checkbutton
    Combo = ctk.CTkComboBox if ctk else None

    def colour(widget_kw, value):
        widget_kw["text_color" if ctk else "fg"] = value
        return widget_kw

    root.title("bioscout — session")
    root.geometry("980x760")

    state = {"form": None, "dir": Path(session_dir).resolve() if session_dir else None}
    v_dir = tk.StringVar(value=str(state["dir"] or ""))
    v_status = tk.StringVar(value="")
    trial_vars: dict = {}
    scalar_vars: dict = {}
    ceinms_vars: dict = {}
    emg_vars: dict = {}
    iter_vars: dict = {}
    v_static = tk.StringVar(value="")
    v_calibrated = tk.BooleanVar(value=True)
    v_default_cal = tk.StringVar(value="")

    outer = Frame(root)
    outer.pack(fill="both", expand=True, padx=14, pady=12)

    # -- folder row --------------------------------------------------------- #
    top = Frame(outer)
    top.pack(fill="x")
    Label(top, text="session folder").pack(side="left")
    Entry(top, textvariable=v_dir, width=520 if ctk else 70).pack(
        side="left", fill="x", expand=True, padx=8)

    def browse():
        chosen = filedialog.askdirectory(title="Session folder", mustexist=True)
        if chosen:
            v_dir.set(chosen)
            load()

    Button(top, text="browse", command=browse, **({"width": 70} if ctk else {})).pack(side="left")
    Button(top, text="reload", command=lambda: load(), **({"width": 70} if ctk else {})).pack(
        side="left", padx=(8, 0))

    # -- red flags ---------------------------------------------------------- #
    flags = Frame(outer)
    flags.pack(fill="x", pady=(10, 0))

    # -- scrolling body ----------------------------------------------------- #
    if ctk:
        body = ctk.CTkScrollableFrame(outer)
        body.pack(fill="both", expand=True, pady=10)
    else:
        canvas = tk.Canvas(outer, highlightthickness=0)
        bar = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        body = tk.Frame(canvas)
        body.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=bar.set)
        canvas.pack(side="left", fill="both", expand=True, pady=10)
        bar.pack(side="right", fill="y")

    footer = Frame(outer)
    footer.pack(fill="x")
    Label(footer, textvariable=v_status, **colour({}, _BLUE)).pack(side="left")

    def clear(frame):
        for w in frame.winfo_children():
            w.destroy()

    # -- rendering ---------------------------------------------------------- #
    def render_flags(form):
        clear(flags)
        problems = form.problems()
        if not problems:
            Label(flags, text="no problems found", **colour({}, _BLUE)).pack(anchor="w")
            return
        for p in problems:
            Label(flags, text="!  " + p, justify="left", wraplength=900,
                  **colour({}, _RED)).pack(anchor="w")

    def section(title):
        Label(body, text=title, **colour({}, _MUTED)).grid(
            row=section.row, column=0, columnspan=6, sticky="w", pady=(14, 4))
        section.row += 1
    section.row = 0

    def render(form):
        clear(body)
        section.row = 0
        trial_vars.clear(); scalar_vars.clear(); ceinms_vars.clear()
        emg_vars.clear(); iter_vars.clear()

        section("SESSION")
        for key, label, _kind in SCALAR_FIELDS:
            var = tk.StringVar(value="" if form.value(key) is None else str(form.value(key)))
            scalar_vars[key] = var
            Label(body, text=label).grid(row=section.row, column=0, sticky="w", pady=2)
            Entry(body, textvariable=var, width=340 if ctk else 46).grid(
                row=section.row, column=1, columnspan=3, sticky="w", pady=2)
            section.row += 1

        section("CEINMS")
        cee = form.value("ceinms") or {}
        for i, key in enumerate(("alpha", "beta", "gamma")):
            var = tk.StringVar(value="" if cee.get(key) is None else str(cee.get(key)))
            ceinms_vars[key] = var
            Label(body, text=key).grid(row=section.row, column=i * 2, sticky="e", padx=(0, 6))
            Entry(body, textvariable=var, width=80 if ctk else 10).grid(
                row=section.row, column=i * 2 + 1, sticky="w")
        section.row += 1

        # `calibrated: false` is the switch whose output never differed until
        # 2026-08-12 — every "uncalibrated" result before that was calibrated.
        # It belongs on screen, not buried in a nested block.
        v_calibrated.set(bool(cee.get("calibrated", True)))
        Check(body, text="calibrated  (off = execute against the uncalibrated model)",
              variable=v_calibrated).grid(row=section.row, column=0, columnspan=4,
                                          sticky="w", pady=(6, 0))
        section.row += 1
        named = form.calibration_configs()
        if named:
            v_default_cal.set(str(form.value("default_calibration") or ""))
            Label(body, text="default calibration").grid(row=section.row, column=0,
                                                         sticky="w")
            if ctk:
                Combo(body, values=[""] + named, variable=v_default_cal,
                      width=200).grid(row=section.row, column=1, sticky="w")
            else:
                from tkinter import ttk
                ttk.Combobox(body, values=[""] + named, textvariable=v_default_cal,
                             width=22).grid(row=section.row, column=1, sticky="w")
            Label(body, text=f"named configs: {', '.join(named)}",
                  **colour({}, _MUTED)).grid(row=section.row, column=2, columnspan=3,
                                             sticky="w")
            section.row += 1

        section("EMG FILTER   —   blank means the default; only changed values are written")
        eff = form.emg_filter()
        for i, (key, label, default) in enumerate(EMG_FILTER_FIELDS):
            var = tk.StringVar(value="" if eff.get(key) == default else str(eff.get(key)))
            emg_vars[key] = var
            col = (i % 3) * 2
            if i % 3 == 0 and i:
                section.row += 1
            Label(body, text=f"{label} [{default:g}]").grid(
                row=section.row, column=col, sticky="e", padx=(0, 6))
            Entry(body, textvariable=var, width=80 if ctk else 10).grid(
                row=section.row, column=col + 1, sticky="w")
        section.row += 1

        trials = form.trials()
        types = form.trial_types()
        # Per-trial flags first, legacy lists second — same rule the runtime
        # uses, so the ticks show what a run would actually do.
        cal = set(form.trial_role("calibration"))
        nor = set(form.trial_role("emg_normalisation"))
        v_static.set(form.value("static_trial") or "")

        section(f"TRIALS ({len(trials)})   —   static · calibration · normalisation · type")
        header = ("trial", "static", "calib", "norm", "type", "")
        for c, text in enumerate(header):
            Label(body, text=text, **colour({}, _MUTED)).grid(
                row=section.row, column=c, sticky="w", padx=(0, 10))
        section.row += 1

        c3ds = set(form.c3d_trials())
        for _i, name in enumerate(trials):
            r = section.row
            missing = name not in c3ds
            kw = colour({}, _RED) if missing else {}
            # Alternating row tint: sixty checkboxes in five ungrouped columns
            # is a place to lose your line. CTk takes a per-widget fg_color;
            # plain Tk takes bg, and a Label with no bg inherits the frame's,
            # so the stripe has to be set on every widget in the row.
            _band = (_ROW_TINT if (_i % 2) else None)
            _rowkw = ({"fg_color": _band} if (ctk and _band)
                      else ({"bg": _band} if (_band and not ctk) else {}))
            Label(body, text=name + ("  (no c3d)" if missing else ""),
                  **kw, **_rowkw).grid(
                row=r, column=0, sticky="ew", padx=(0, 10))

            rb = (ctk.CTkRadioButton if ctk else tk.Radiobutton)
            rb(body, text="", variable=v_static, value=name).grid(row=r, column=1)

            v_cal = tk.BooleanVar(value=name in cal)
            v_nor = tk.BooleanVar(value=name in nor)
            Check(body, text="", variable=v_cal).grid(row=r, column=2)
            Check(body, text="", variable=v_nor).grid(row=r, column=3)

            # A trial in the yaml with no c3d cannot be exported or solved —
            # usually a copy-paste leftover from another session. Offer to
            # drop it here rather than making the user hand-edit the file.
            if missing:
                Button(body, text="delete",
                       command=lambda n=name: trial_drop(n),
                       **({"width": 60} if ctk else {})).grid(
                    row=r, column=5, sticky="w", padx=(8, 0))

            v_type = tk.StringVar(value=types.get(name, ""))
            if ctk:
                Combo(body, values=list(TRIAL_TYPES), variable=v_type, width=150).grid(
                    row=r, column=4, sticky="w")
            else:
                from tkinter import ttk
                ttk.Combobox(body, values=list(TRIAL_TYPES), textvariable=v_type,
                             width=14).grid(row=r, column=4, sticky="w")

            trial_vars[name] = (v_cal, v_nor, v_type)
            section.row += 1

        section(f"ITERATIONS ({len(form.iterations())})   —   one runnable model arm each")
        for name, block in form.iterations().items():
            head = Frame(body)
            head.grid(row=section.row, column=0, columnspan=6, sticky="w", pady=(8, 2))
            Label(head, text=name, **colour({}, _BLUE)).pack(side="left", padx=(0, 12))
            Button(head, text="duplicate",
                   command=lambda n=name: iteration_copy(n),
                   **({"width": 80} if ctk else {})).pack(side="left")
            Button(head, text="remove",
                   command=lambda n=name: iteration_drop(n),
                   **({"width": 70} if ctk else {})).pack(side="left", padx=(6, 0))
            section.row += 1
            vars_for = {}
            for i, (key, label, kind, default) in enumerate(ITERATION_FIELDS):
                col = (i % 2) * 3
                if i % 2 == 0 and i:
                    section.row += 1
                cur = block.get(key, default)
                if kind == "bool":
                    var = tk.BooleanVar(value=bool(cur))
                    Check(body, text=label, variable=var).grid(
                        row=section.row, column=col, columnspan=2, sticky="w")
                else:
                    var = tk.StringVar(value="" if cur is None else str(cur))
                    Label(body, text=label).grid(row=section.row, column=col, sticky="e",
                                                 padx=(0, 6))
                    Entry(body, textvariable=var, width=200 if ctk else 26).grid(
                        row=section.row, column=col + 1, sticky="w")
                vars_for[key] = (var, kind)
            iter_vars[name] = vars_for
            section.row += 1

        Button(body, text="+ add iteration", command=iteration_add).grid(
            row=section.row, column=0, columnspan=2, sticky="w", pady=(8, 0))
        section.row += 1

        emg = form.value("emg_map") or {}
        its = form.value("iterations") or {}
        section("NOT EDITED HERE")
        Label(body, justify="left", wraplength=900,
              text=(f"emg_map: {len(emg)} channel(s). Nested structure — edit it in "
                    f"the GUI's File Editor tab, which patches YAML the same "
                    f"surgical way this form does."),
              **colour({}, _MUTED)).grid(row=section.row, column=0, columnspan=6, sticky="w")
        section.row += 1

    # -- iteration actions -------------------------------------------------- #
    def _ask_name(title, initial=""):
        from tkinter import simpledialog
        return simpledialog.askstring(title, "iteration name:", initialvalue=initial,
                                      parent=root)

    def iteration_add():
        form = state["form"]
        if not form or not form.exists:
            return
        name = _ask_name("bioscout — new iteration")
        if not name:
            return
        try:
            form.add_iteration(name.strip())
            form.save()
            v_status.set(f"added iteration {name}")
            load()
        except Exception as exc:                                  # noqa: BLE001
            messagebox.showerror("bioscout", f"{type(exc).__name__}: {exc}")

    def iteration_copy(name):
        form = state["form"]
        new = _ask_name("bioscout — duplicate iteration", f"{name}_copy")
        if not new:
            return
        try:
            form.duplicate_iteration(name, new.strip())
            form.save()
            v_status.set(f"duplicated {name} -> {new}")
            load()
        except Exception as exc:                                  # noqa: BLE001
            messagebox.showerror("bioscout", f"{type(exc).__name__}: {exc}")

    def iteration_drop(name):
        form = state["form"]
        if not messagebox.askyesno(
                "bioscout", f"Remove iteration '{name}' from session.yaml?\n\n"
                            f"Its folder under 3_iterations/ is NOT deleted."):
            return
        try:
            form.delete_iteration(name)
            form.save()
            v_status.set(f"removed iteration {name}")
            load()
        except Exception as exc:                                  # noqa: BLE001
            messagebox.showerror("bioscout", f"{type(exc).__name__}: {exc}")

    def trial_drop(name):
        """Remove a trial from session.yaml (offered only for trials with no
        c3d — nothing can export or solve them)."""
        form = state["form"]
        if not messagebox.askyesno(
                "bioscout", f"Remove trial '{name}' from session.yaml?\n\n"
                            f"It has no c3d, so nothing can export or solve "
                            f"it. Any folder it may have on disk is NOT "
                            f"deleted, and the file is backed up first."):
            return
        try:
            form.delete_trial(name)
            form.save()
            v_status.set(f"removed trial {name}")
            load()
        except Exception as exc:                                  # noqa: BLE001
            messagebox.showerror("bioscout", f"{type(exc).__name__}: {exc}")

    # -- load / create ------------------------------------------------------ #
    def load():
        d = Path(v_dir.get().strip() or ".")
        state["dir"] = d
        if not d.is_dir():
            clear(body); clear(flags)
            Label(flags, text=f"!  {d} does not exist", **colour({}, _RED)).pack(anchor="w")
            return
        form = SessionForm(d)
        state["form"] = form
        if not form.exists:
            clear(body); render_flags(form)
            Label(body, justify="left", wraplength=900,
                  text=("No session.yaml here yet. Trial names and the static trial "
                        "come from the c3d filenames; a template session can supply "
                        "the lab constants (markerset, emg_map, ceinms).")
                  ).grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 8))
            tmpl = tk.StringVar()
            Label(body, text="copy settings from").grid(row=1, column=0, sticky="w")
            Entry(body, textvariable=tmpl, width=340 if ctk else 46).grid(
                row=1, column=1, columnspan=3, sticky="w")

            def create():
                written = form.scaffold(template=tmpl.get().strip() or None)
                if not written:
                    messagebox.showerror("bioscout", "could not scaffold session.yaml")
                    return
                v_status.set(f"created {written}")
                load()

            Button(body, text="Create session.yaml", command=create).grid(
                row=2, column=0, columnspan=2, sticky="w", pady=10)
            return
        render_flags(form)
        render(form)
        v_status.set(f"editing {form.path}")

    # -- saving ------------------------------------------------------------- #
    def _collect(form):
        """Stage every widget's value onto the form.

        Split out of ``save`` so "Show changes" sees the SAME edits Save
        would write. It used to call ``form.diff()`` on a form that had never
        been told what the widgets hold — so the preview said "(no unsaved
        changes)" no matter what you had typed, which reads as "my edits were
        lost". Staging is in-memory; nothing reaches disk until ``form.save``.
        """
        for key, var in scalar_vars.items():
            text = var.get().strip()
            if text != ("" if form.value(key) is None else str(form.value(key))):
                form.set_scalar(key, text)

        if v_static.get() and v_static.get() != form.value("static_trial"):
            form.set_scalar("static_trial", v_static.get())

        # Ticking a box writes the PER-TRIAL flag (the schema going forward),
        # which is how a session migrates itself the first time it is edited.
        for _role, _idx in (("calibration", 0), ("emg_normalisation", 1)):
            was = set(form.trial_role(_role))
            for name, vs in trial_vars.items():
                want = bool(vs[_idx].get())
                if want != (name in was):
                    form.set_trial_role(name, _role, want)

        types = form.trial_types()
        for name, (_, _, v_type) in trial_vars.items():
            want = v_type.get().strip()
            if want and want != types.get(name, ""):
                form.set_trial_type(name, want)

        cee = form.value("ceinms") or {}
        changed = {k: v.get().strip() for k, v in ceinms_vars.items()
                   if v.get().strip() and v.get().strip() != str(cee.get(k, ""))}
        if changed:
            form.set_ceinms(**changed)
        if bool(cee.get("calibrated", True)) != v_calibrated.get():
            form.set_ceinms(calibrated="true" if v_calibrated.get() else "false")
        if v_default_cal.get() and v_default_cal.get() != str(
                form.value("default_calibration") or ""):
            form.set_scalar("default_calibration", v_default_cal.get())

        emg_now = {}
        for key, var in emg_vars.items():
            text = var.get().strip()
            if text:
                emg_now[key] = float(text)
        if emg_now:
            form.set_emg_filter(**emg_now)

        blocks = form.iterations()
        for name, fields in iter_vars.items():
            block = blocks.get(name, {})
            for key, (var, kind) in fields.items():
                want = var.get() if kind == "bool" else var.get().strip()
                if kind == "bool":
                    if bool(block.get(key, want)) != want or key not in block:
                        form.set_iteration_field(name, key, want)
                elif want and want != str(block.get(key, "")):
                    form.set_iteration_field(name, key, want)

    def save():
        form = state["form"]
        if not form or not form.exists:
            return
        try:
            _collect(form)
            if not form.dirty():
                v_status.set("nothing changed")
                return
            out = form.save()
            v_status.set(f"saved {out}  (previous version kept as a backup)")
            load()
        except Exception as exc:                                  # noqa: BLE001
            messagebox.showerror("bioscout — save failed",
                                 f"{type(exc).__name__}: {exc}\n\n"
                                 f"Nothing was written.")

    def show_diff():
        form = state["form"]
        if not form or not form.exists:
            return
        try:
            _collect(form)          # the whole point: preview what SAVE would do
        except Exception as exc:                                  # noqa: BLE001
            messagebox.showerror("bioscout", f"{type(exc).__name__}: {exc}")
            return
        save_preview = form.diff() or "(no unsaved changes)"
        win = tk.Toplevel(root)
        win.title("bioscout — unsaved changes")
        text = tk.Text(win, wrap="none", width=110, height=30)
        text.insert("1.0", save_preview)
        text.configure(state="disabled")
        text.pack(fill="both", expand=True)

    Button(footer, text="Close", command=root.destroy,
           **({"width": 90} if ctk else {})).pack(side="right", padx=(8, 0))
    Button(footer, text="Save", command=save,
           **({"width": 90} if ctk else {})).pack(side="right")
    Button(footer, text="Show changes", command=show_diff,
           **({"width": 120} if ctk else {})).pack(side="right", padx=(0, 8))

    load()
    root.mainloop()
    return 0


def ask_new_session(path: Optional[str] = None, template: Optional[str] = None,
                    body_mass: Optional[float] = None) -> Optional[dict]:
    """Backwards-compatible entry used by ``bioscout session new``.

    The editor writes the file itself, so there is nothing to hand back: a
    non-None return would make the caller scaffold a second time.
    """
    open_session_editor(path)
    return None
