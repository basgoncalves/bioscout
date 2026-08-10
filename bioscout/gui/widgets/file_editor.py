"""File Editor tab — edit session.yaml, OpenSim XML and JSON config in the GUI.

Before this, changing a trial's ``time_range`` or an ExternalForce body meant
leaving BioScout for a text editor and hand-editing YAML — where a bad indent
or a stringified number surfaces three pipeline stages later as an unrelated
OpenSim error.

Three panes:

* **Files** — the config files of the loaded project, grouped, plus Open… for
  anything else.
* **Structure** — the document tree. Containers are rows; scalars are fields on
  their parent, so editing a value is one click, not a drill-down.
* **Form / Text / Changes** — a typed form (switches for booleans, dropdowns
  for enumerations), the raw source, and a diff of what saving would do.

Editing YAML never re-dumps the file — see :mod:`bioscout.utils.file_edit`.
Comments, key order and formatting survive because untouched lines are never
rewritten. Every save is atomic and keeps a ``.bak``.

The widget is reusable: :class:`FileEditorFrame` embeds anywhere, and
:func:`open_file_editor_window` pops it out for one file, so other tabs can
offer "edit this file" without duplicating any of it.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List, Optional

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from bioscout.utils.file_edit import (
    BIG_FILE_BYTES, Document, EDITABLE_SUFFIXES, Field, Node,
    UnsupportedFormat, describe_format, load_document,
)

MONO = ("Consolas", 11)
MONO_SMALL = ("Consolas", 10)

#: Where to look for a project's config files, and what to call each group.
QUICK_GROUPS: List[tuple] = [
    ("Sessions",   "simulations/*/*/session.yaml"),
    ("Sessions",   "inputData/*/*/session.yaml"),
    ("Setup XML",  "simulations/*/*/setupFiles/*.xml"),
    ("Setup XML",  "simulations/*/*/2_experimental/*/*.xml"),
    ("Models",     "generic models/*/*.osim"),
    ("Project",    "*.json"),
    ("Project",    "*.yaml"),
]
MAX_PER_GROUP = 40


class FileEditorFrame(ctk.CTkFrame):
    """Structure tree + properties form + raw text, for one file at a time."""

    def __init__(self, parent, path=None, status_callback: Optional[Callable] = None,
                 show_file_list: bool = True, **kw):
        super().__init__(parent, fg_color="transparent", **kw)
        self.status_callback = status_callback or (lambda *a, **k: None)
        self._show_file_list = show_file_list
        self._project_root: Optional[Path] = None
        self.doc: Optional[Document] = None
        self._node_by_iid: Dict[str, Node] = {}
        self._current_node: Optional[Node] = None
        self._widgets: List[tuple] = []      # (Field, kind, getter)
        self._text_mode = False              # raw text is authoritative right now
        self._suspend = False

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._build_toolbar()
        self._build_panes()
        self._style_tree()
        if path:
            self.open_path(path)
        else:
            self._set_note("Open a file to start editing.", "muted")

    # ------------------------------------------------------------------ setup
    def set_project_dir(self, project_dir: str) -> None:
        """Called by the main window when the project folder changes."""
        if not project_dir:
            return
        self._project_root = Path(project_dir)
        self._refresh_file_list()

    def _build_toolbar(self) -> None:
        bar = ctk.CTkFrame(self)
        bar.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 8))
        bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(bar, text="File Editor",
                     font=("Segoe UI", 15, "bold")).grid(
            row=0, column=0, padx=(12, 10), pady=8, sticky="w")

        self._path_label = ctk.CTkLabel(bar, text="no file open",
                                        text_color="#888888", font=MONO_SMALL,
                                        anchor="w")
        self._path_label.grid(row=0, column=1, sticky="ew", padx=4)

        btns = ctk.CTkFrame(bar, fg_color="transparent")
        btns.grid(row=0, column=2, padx=(4, 10), pady=6, sticky="e")
        for i, (text, cmd, colour) in enumerate([
            ("Open…",   self.open_dialog, None),
            ("Reload",  self.reload,      None),
            ("Revert",  self.revert,      None),
            ("Save As…", self.save_as,    None),
            ("Save",    self.save,        "#2fa84f"),
        ]):
            b = ctk.CTkButton(btns, text=text, width=78, command=cmd,
                              font=("Segoe UI", 11))
            if colour:
                b.configure(fg_color=colour, hover_color="#268a41")
            b.grid(row=0, column=i, padx=3)
            if text == "Save":
                self._save_btn = b

    def _build_panes(self) -> None:
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, minsize=190)
        body.grid_columnconfigure(1, minsize=240)
        body.grid_columnconfigure(2, weight=1)

        # -- files ------------------------------------------------------- #
        if self._show_file_list:
            left = ctk.CTkFrame(body)
            left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
            left.grid_rowconfigure(1, weight=1)
            left.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(left, text="Project files",
                         font=("Segoe UI", 11, "bold")).grid(
                row=0, column=0, sticky="w", padx=10, pady=(8, 4))
            self._file_list = ctk.CTkScrollableFrame(left, fg_color="transparent")
            self._file_list.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 8))
            self._file_list.grid_columnconfigure(0, weight=1)
        else:
            self._file_list = None

        # -- structure --------------------------------------------------- #
        mid = ctk.CTkFrame(body)
        mid.grid(row=0, column=1, sticky="nsew", padx=(0, 6))
        mid.grid_rowconfigure(1, weight=1)
        mid.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(mid, text="Structure",
                     font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(8, 4))

        tree_wrap = tk.Frame(mid, bg="#2b2b2b", highlightthickness=0)
        tree_wrap.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 4))
        tree_wrap.grid_rowconfigure(0, weight=1)
        tree_wrap.grid_columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(tree_wrap, show="tree", selectmode="browse",
                                 style="BioScout.Treeview")
        vsb = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<<TreeviewSelect>>", self._on_select_node)

        self._struct_bar = ctk.CTkFrame(mid, fg_color="transparent")
        self._struct_bar.grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 8))
        for i, (t, cmd) in enumerate([("+ Add", self._add_entry),
                                      ("Duplicate", self._duplicate_entry),
                                      ("Delete", self._delete_entry)]):
            ctk.CTkButton(self._struct_bar, text=t, width=64, height=24,
                          font=("Segoe UI", 10), command=cmd
                          ).grid(row=0, column=i, padx=2)

        # -- editor ------------------------------------------------------ #
        right = ctk.CTkFrame(body)
        right.grid(row=0, column=2, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(right, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        head.grid_columnconfigure(1, weight=1)
        self._view = ctk.CTkSegmentedButton(
            head, values=["Form", "Text", "Changes"], command=self._switch_view,
            font=("Segoe UI", 11))
        self._view.set("Form")
        self._view.grid(row=0, column=0, sticky="w")
        self._where = ctk.CTkLabel(head, text="", font=MONO_SMALL,
                                   text_color="#7fb2e5", anchor="e")
        self._where.grid(row=0, column=1, sticky="ew", padx=8)

        self._stack = ctk.CTkFrame(right, fg_color="transparent")
        self._stack.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 4))
        self._stack.grid_rowconfigure(0, weight=1)
        self._stack.grid_columnconfigure(0, weight=1)

        self._form = ctk.CTkScrollableFrame(self._stack, fg_color="transparent")
        self._form.grid_columnconfigure(1, weight=1)

        self._text_pane = ctk.CTkFrame(self._stack, fg_color="transparent")
        self._text_pane.grid_rowconfigure(0, weight=1)
        self._text_pane.grid_columnconfigure(0, weight=1)
        self._text = ctk.CTkTextbox(self._text_pane, font=MONO, wrap="none",
                                    undo=True)
        self._text.grid(row=0, column=0, sticky="nsew")
        tb = ctk.CTkFrame(self._text_pane, fg_color="transparent")
        tb.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        ctk.CTkButton(tb, text="Check syntax", width=100, height=26,
                      font=("Segoe UI", 10), command=self._check_text
                      ).grid(row=0, column=0, padx=(0, 6))
        ctk.CTkButton(tb, text="Apply to form", width=100, height=26,
                      font=("Segoe UI", 10), command=self._apply_text
                      ).grid(row=0, column=1)
        ctk.CTkLabel(tb, text="Edits here are the whole file. "
                             "Apply to form re-reads the structure.",
                     font=("Segoe UI", 10), text_color="#888888"
                     ).grid(row=0, column=2, padx=10, sticky="w")

        self._changes = ctk.CTkTextbox(self._stack, font=MONO, wrap="none")

        self._note = ctk.CTkLabel(right, text="", font=("Segoe UI", 11),
                                  anchor="w", justify="left")
        self._note.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 8))
        self._show_pane(self._form)

    def _style_tree(self) -> None:
        """ttk.Treeview has no CustomTkinter equivalent, so match it by hand."""
        try:
            style = ttk.Style()
            style.theme_use("default")
            style.configure("BioScout.Treeview",
                            background="#2b2b2b", fieldbackground="#2b2b2b",
                            foreground="#dcdcdc", borderwidth=0,
                            rowheight=22, font=("Segoe UI", 10))
            style.map("BioScout.Treeview",
                      background=[("selected", "#1f6aa5")],
                      foreground=[("selected", "#ffffff")])
            style.layout("BioScout.Treeview", [
                ("BioScout.Treeview.treearea", {"sticky": "nswe"})])
        except Exception:
            pass

    # ------------------------------------------------------------- file list
    def _refresh_file_list(self) -> None:
        if self._file_list is None:
            return
        for w in self._file_list.winfo_children():
            w.destroy()
        if not self._project_root or not self._project_root.is_dir():
            ctk.CTkLabel(self._file_list, text="Load a project folder\nto list its config files.",
                         font=("Segoe UI", 10), text_color="#888888",
                         justify="left").grid(row=0, column=0, sticky="w", padx=6, pady=6)
            return

        groups: Dict[str, List[Path]] = {}
        for label, pattern in QUICK_GROUPS:
            try:
                hits = sorted(self._project_root.glob(pattern))
            except Exception:
                hits = []
            for h in hits:
                if h.is_file():
                    groups.setdefault(label, [])
                    if h not in groups[label]:
                        groups[label].append(h)

        row = 0
        if not groups:
            ctk.CTkLabel(self._file_list, text="No config files found\nin this project.",
                         font=("Segoe UI", 10), text_color="#888888",
                         justify="left").grid(row=0, column=0, sticky="w", padx=6, pady=6)
            return
        for label, paths in groups.items():
            ctk.CTkLabel(self._file_list, text=label.upper(),
                         font=("Segoe UI", 9, "bold"), text_color="#7f7f7f"
                         ).grid(row=row, column=0, sticky="w", padx=6, pady=(8, 2))
            row += 1
            shown = paths[:MAX_PER_GROUP]
            for p in shown:
                try:
                    rel = p.relative_to(self._project_root)
                except ValueError:
                    rel = p
                text = self._short(rel)
                ctk.CTkButton(self._file_list, text=text, anchor="w", height=24,
                              font=MONO_SMALL, fg_color="transparent",
                              hover_color="#3a3a3a",
                              command=lambda q=p: self.open_path(q)
                              ).grid(row=row, column=0, sticky="ew", padx=2)
                row += 1
            if len(paths) > len(shown):
                # Say what was hidden — a silently clipped list reads as
                # "that's all of them".
                ctk.CTkLabel(self._file_list,
                             text=f"  +{len(paths) - len(shown)} more (use Open…)",
                             font=("Segoe UI", 9), text_color="#7f7f7f"
                             ).grid(row=row, column=0, sticky="w", padx=6)
                row += 1

    @staticmethod
    def _short(rel: Path) -> str:
        parts = rel.parts
        if len(parts) <= 3:
            return str(rel)
        return ".../" + "/".join(parts[-3:])

    # ------------------------------------------------------------------ open
    def open_dialog(self) -> None:
        initial = str(self._project_root) if self._project_root else None
        path = filedialog.askopenfilename(
            title="Open a configuration file", initialdir=initial,
            filetypes=[("Config files", "*.yaml *.yml *.xml *.json *.osim"),
                       ("YAML", "*.yaml *.yml"), ("XML / OpenSim", "*.xml *.osim"),
                       ("JSON", "*.json"), ("All files", "*.*")])
        if path:
            self.open_path(path)

    def open_path(self, path) -> None:
        """Load *path*, or offer text-only editing when it has no structure."""
        path = Path(path)
        if not self._confirm_discard():
            return
        if not path.is_file():
            self._set_note(f"Not a file: {path}", "error")
            return

        self._path_label.configure(text=str(path), text_color="#c8c8c8")
        size = path.stat().st_size
        fmt = describe_format(path)

        if fmt is None:
            self._open_as_text(path, f"No structured editor for "
                                     f"'{path.suffix or 'this file'}' — "
                                     f"editing as plain text.")
            return
        if size > BIG_FILE_BYTES:
            # A 40 MB .osim builds a 10k-row tree and freezes the window.
            self._open_as_text(path, f"{size / 1e6:.1f} MB is too large for the "
                                     f"structure tree — editing as plain text.")
            return
        try:
            self.doc = load_document(path)
        except UnsupportedFormat as exc:
            self._open_as_text(path, str(exc))
            return
        except Exception as exc:
            self.doc = None
            self._open_as_text(path, f"Could not parse: {type(exc).__name__}: {exc}"
                                     f"  —  fix it here and press Apply to form.")
            return

        self._text_mode = False
        self._populate_tree()
        self._load_text_pane()
        self._view.set("Form")
        self._switch_view("Form")
        self._report_problems(f"Opened {path.name}")
        self.status_callback(f"Opened {path.name}", "success")

    def _open_as_text(self, path: Path, why: str) -> None:
        self.doc = None
        self._text_mode = True
        self._text_path = path
        self.tree.delete(*self.tree.get_children())
        self._node_by_iid.clear()
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            self._set_note(f"Cannot read: {exc}", "error")
            return
        self._text.delete("1.0", "end")
        self._text.insert("1.0", content)
        self._view.set("Text")
        self._switch_view("Text")
        self._set_note(why, "warning")

    def reload(self) -> None:
        p = self._current_path()
        if p:
            self._force_discard = True
            try:
                self.open_path(p)
            finally:
                self._force_discard = False

    def revert(self) -> None:
        if self.doc is None:
            return self.reload()
        if not self.doc.dirty:
            return self._set_note("Nothing to revert.", "muted")
        self.doc.revert()
        self._populate_tree()
        self._load_text_pane()
        self._render_form(self._current_node or self.doc.root)
        self._report_problems("Reverted to the saved file.")

    def _current_path(self) -> Optional[Path]:
        if self.doc is not None:
            return self.doc.path
        return getattr(self, "_text_path", None)

    # ------------------------------------------------------------------ tree
    def _populate_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._node_by_iid.clear()
        if self.doc is None or self.doc.root is None:
            return
        self._insert_node("", self.doc.root, open_it=True)
        kids = self.tree.get_children("")
        if kids:
            self.tree.selection_set(kids[0])
            self.tree.focus(kids[0])

    def _insert_node(self, parent_iid: str, node: Node, open_it: bool = False) -> None:
        label = node.label
        if node.summary:
            label += f"   ({node.summary})"
        iid = self.tree.insert(parent_iid, "end", text=" " + label, open=open_it)
        self._node_by_iid[iid] = node
        for child in node.children:
            self._insert_node(iid, child)

    def _on_select_node(self, _evt=None) -> None:
        if self._suspend:
            return
        sel = self.tree.selection()
        if not sel:
            return
        node = self._node_by_iid.get(sel[0])
        if node is None:
            return
        self._flush_form()
        self._current_node = node
        self._render_form(node)

    # ------------------------------------------------------------------ form
    def _render_form(self, node: Optional[Node]) -> None:
        for w in self._form.winfo_children():
            w.destroy()
        self._widgets = []
        if self.doc is None or node is None:
            return

        self._where.configure(text=node.path_str())
        try:
            fields = self.doc.fields_for(node)
        except Exception as exc:
            ctk.CTkLabel(self._form, text=f"{type(exc).__name__}: {exc}",
                         text_color="#e06c75").grid(row=0, column=0, sticky="w")
            return

        if not fields:
            ctk.CTkLabel(self._form,
                         text="No values on this node — pick a child on the left.",
                         font=("Segoe UI", 11), text_color="#888888"
                         ).grid(row=0, column=0, sticky="w", padx=6, pady=8)
            return

        for row, f in enumerate(fields):
            self._add_field_row(row * 2, f)
        self._form.grid_columnconfigure(1, weight=1)

    def _add_field_row(self, row: int, f: Field) -> None:
        lbl = ctk.CTkLabel(self._form, text=f.label, font=MONO, anchor="w",
                           width=190)
        lbl.grid(row=row, column=0, sticky="w", padx=(6, 8), pady=(6, 0))

        if f.kind == "bool":
            var = tk.BooleanVar(value=str(f.value).strip().lower()
                                in ("true", "yes", "on"))
            w = ctk.CTkSwitch(self._form, text="", variable=var, width=44,
                              command=self._on_change)
            w.grid(row=row, column=1, sticky="w", padx=4, pady=(6, 0))
            self._widgets.append((f, "bool", var.get))

        elif f.kind == "choice":
            var = tk.StringVar(value=f.value)
            w = ctk.CTkComboBox(self._form, values=list(f.choices), variable=var,
                                font=MONO, command=lambda _v: self._on_change())
            w.grid(row=row, column=1, sticky="ew", padx=4, pady=(6, 0))
            w.bind("<FocusOut>", lambda _e: self._on_change())
            self._widgets.append((f, "str", var.get))

        elif f.kind == "multiline":
            box = ctk.CTkTextbox(self._form, height=76, font=MONO, wrap="word")
            box.insert("1.0", f.value)
            box.grid(row=row, column=1, sticky="ew", padx=4, pady=(6, 0))
            box.bind("<FocusOut>", lambda _e: self._on_change())
            self._widgets.append((f, "str", lambda b=box: b.get("1.0", "end").rstrip("\n")))

        else:
            var = tk.StringVar(value=f.value)
            w = ctk.CTkEntry(self._form, textvariable=var, font=MONO)
            w.grid(row=row, column=1, sticky="ew", padx=4, pady=(6, 0))
            w.bind("<FocusOut>", lambda _e: self._on_change())
            w.bind("<Return>", lambda _e: self._on_change())
            self._widgets.append((f, "str", var.get))

        hint = f.help or ""
        if f.comment:
            hint = f"{hint}   # {f.comment}" if hint else f"# {f.comment}"
        if hint:
            ctk.CTkLabel(self._form, text=hint, font=("Segoe UI", 10),
                         text_color="#8a8a8a", anchor="w", justify="left",
                         wraplength=520
                         ).grid(row=row + 1, column=1, sticky="ew", padx=6,
                                pady=(0, 2))

    def _flush_form(self) -> None:
        """Push every widget's value into the document."""
        if self.doc is None:
            return
        for f, kind, getter in self._widgets:
            try:
                f.set(getter())
            except Exception as exc:
                self._set_note(f"{f.label}: {exc}", "error")

    def _on_change(self) -> None:
        if self._suspend or self.doc is None:
            return
        self._flush_form()
        self._load_text_pane()
        self._report_problems()

    # ------------------------------------------------------- structural edits
    def _selected_map(self):
        node = self._current_node
        if self.doc is None or node is None:
            self._set_note("Select something in Structure first.", "warning")
            return None
        if self.doc.format != "yaml":
            self._set_note("Add / Duplicate / Delete are YAML-only for now — "
                           "use the Text view for XML and JSON.", "warning")
            return None
        return node

    def _add_entry(self) -> None:
        node = self._selected_map()
        if node is None:
            return
        name = _ask(self, "Add entry", f"New key under {node.path_str()}:")
        if not name:
            return
        self._flush_form()
        try:
            self.doc.add_entry(node.ref, name.strip(), "{}")
        except Exception as exc:
            return self._set_note(f"{type(exc).__name__}: {exc}", "error")
        self._after_structural(f"Added {name}")

    def _duplicate_entry(self) -> None:
        node = self._current_node
        if node is None or node.parent is None or self.doc is None:
            return self._set_note("Select the entry to duplicate.", "warning")
        if self.doc.format != "yaml":
            return self._set_note("Duplicate is YAML-only for now.", "warning")
        new = _ask(self, "Duplicate", f"Copy '{node.label}' as:")
        if not new:
            return
        self._flush_form()
        try:
            self.doc.duplicate_entry(node.parent.ref, node.key, new.strip())
        except Exception as exc:
            return self._set_note(f"{type(exc).__name__}: {exc}", "error")
        self._after_structural(f"Duplicated {node.label} → {new}")

    def _delete_entry(self) -> None:
        node = self._current_node
        if node is None or node.parent is None or self.doc is None:
            return self._set_note("Select the entry to delete.", "warning")
        if self.doc.format != "yaml":
            return self._set_note("Delete is YAML-only for now.", "warning")
        if not messagebox.askyesno(
                "Delete entry",
                f"Remove '{node.path_str()}' from {self.doc.path.name}?\n\n"
                f"Not written to disk until you press Save.", parent=self):
            return
        self._flush_form()
        try:
            self.doc.delete_entry(node.parent.ref, node.key)
        except Exception as exc:
            return self._set_note(f"{type(exc).__name__}: {exc}", "error")
        self._after_structural(f"Deleted {node.label}")

    def _after_structural(self, msg: str) -> None:
        self._current_node = None
        self._populate_tree()
        self._load_text_pane()
        self._render_form(self._current_node)
        self._report_problems(msg)

    # ------------------------------------------------------------- text pane
    def _load_text_pane(self) -> None:
        if self.doc is None:
            return
        self._suspend = True
        try:
            at = self._text.index("@0,0")
            self._text.delete("1.0", "end")
            self._text.insert("1.0", self.doc.dumps())
            try:
                self._text.see(at)
            except Exception:
                pass
        finally:
            self._suspend = False

    def _check_text(self) -> Optional[str]:
        content = self._text.get("1.0", "end-1c")
        path = self._current_path()
        fmt = describe_format(path) if path else None
        if fmt is None:
            self._set_note("Plain text — nothing to check.", "muted")
            return None
        from bioscout.utils.file_edit import _CLASSES
        err = _CLASSES[fmt](path or "x").validate_text(content)
        if err:
            self._set_note(f"Invalid {fmt}: {err}", "error")
        else:
            self._set_note(f"Valid {fmt}.", "ok")
        return err

    def _apply_text(self) -> None:
        """Adopt the text pane as the document and re-read the structure."""
        path = self._current_path()
        if path is None:
            return
        if self._check_text():
            return
        content = self._text.get("1.0", "end-1c")
        fmt = describe_format(path)
        if fmt is None:
            self._set_note("Plain text — press Save to write it.", "muted")
            return
        try:
            from bioscout.utils.file_edit import _CLASSES
            doc = _CLASSES[fmt](path)
            doc._disk_text = content
            doc._rebuild(content)
            # Keep the on-disk text as the diff baseline so the Changes pane
            # still shows what saving would do, not an empty diff.
            if self.doc is not None:
                doc._baseline = self.doc._baseline
                doc._disk_text = self.doc._disk_text
            else:
                doc._baseline = path.read_text(encoding="utf-8")
                doc._disk_text = doc._baseline
            self.doc = doc
            self._text_mode = False
        except Exception as exc:
            return self._set_note(f"{type(exc).__name__}: {exc}", "error")
        self._current_node = None
        self._populate_tree()
        self._render_form(self._current_node)
        self._report_problems("Structure re-read from the text.")

    # ------------------------------------------------------------------ save
    def save(self) -> None:
        path = self._current_path()
        if path is None:
            return self._set_note("Nothing open.", "warning")
        if self._text_mode or self.doc is None:
            if self._check_text():
                return
            content = self._text.get("1.0", "end-1c")
            try:
                _atomic_write(path, content)
            except Exception as exc:
                return self._set_note(f"NOT saved — {type(exc).__name__}: {exc}", "error")
            self._set_note(f"Saved {path.name} (plain text).", "ok")
            self.status_callback(f"Saved {path.name}", "success")
            return

        self._flush_form()
        if not self.doc.dirty:
            return self._set_note("No changes to save.", "muted")
        try:
            self.doc.save()
        except Exception as exc:
            self._set_note(f"NOT saved — {type(exc).__name__}: {exc}", "error")
            self.status_callback(f"Save failed: {exc}", "error")
            return
        self._current_node = None
        self._populate_tree()
        self._load_text_pane()
        self._render_form(self._current_node)
        self._report_problems(f"Saved {self.doc.path.name}  "
                              f"(previous version kept as {self.doc.path.name}.bak)")
        self.status_callback(f"Saved {self.doc.path.name}", "success")

    def save_as(self) -> None:
        path = self._current_path()
        if path is None:
            return
        target = filedialog.asksaveasfilename(
            title="Save as", initialdir=str(path.parent),
            initialfile=path.name, defaultextension=path.suffix)
        if not target:
            return
        try:
            if self._text_mode or self.doc is None:
                _atomic_write(Path(target), self._text.get("1.0", "end-1c"))
            else:
                self._flush_form()
                self.doc.save(path=target)
        except Exception as exc:
            return self._set_note(f"NOT saved — {type(exc).__name__}: {exc}", "error")
        self._path_label.configure(text=target)
        self._set_note(f"Saved as {target}", "ok")

    def _confirm_discard(self) -> bool:
        if getattr(self, "_force_discard", False):
            return True
        if self.doc is None or not self.doc.dirty:
            return True
        return messagebox.askyesno(
            "Unsaved changes",
            f"{self.doc.path.name} has unsaved changes. Discard them?",
            parent=self)

    # ----------------------------------------------------------------- views
    def _switch_view(self, name: str) -> None:
        if name == "Form":
            self._flush_form() if self.doc else None
            self._show_pane(self._form)
        elif name == "Text":
            if self.doc is not None:
                self._flush_form()
                self._load_text_pane()
            self._show_pane(self._text_pane)
        else:
            self._render_changes()
            self._show_pane(self._changes)

    def _show_pane(self, pane) -> None:
        for p in (self._form, self._text_pane, self._changes):
            p.grid_forget()
        pane.grid(row=0, column=0, sticky="nsew")

    def _render_changes(self) -> None:
        self._changes.configure(state="normal")
        self._changes.delete("1.0", "end")
        if self.doc is None:
            self._changes.insert("1.0", "(plain-text mode — no structured diff)")
            return
        self._flush_form()
        diff = self.doc.diff()
        problems = self.doc.problems()
        body = diff or "No unsaved changes.\n"
        if problems:
            body += "\n\nChecks:\n" + "\n".join(f"  !  {p}" for p in problems)
        else:
            body += "\n\nChecks: nothing to flag.\n"
        self._changes.insert("1.0", body)

    def _report_problems(self, prefix: str = "") -> None:
        if self.doc is None:
            return
        try:
            problems = self.doc.problems()
        except Exception:
            problems = []
        dirty = self.doc.dirty
        bits = []
        if prefix:
            bits.append(prefix)
        if dirty:
            bits.append("unsaved changes")
        if problems:
            bits.append(f"{len(problems)} check(s) to look at — see Changes")
        self._set_note("  ·  ".join(bits) or "No changes.",
                       "warning" if problems else ("ok" if dirty else "muted"))
        try:
            self._save_btn.configure(
                fg_color="#2fa84f" if dirty else "#39603f",
                text="Save *" if dirty else "Save")
        except Exception:
            pass

    def _set_note(self, text: str, level: str = "muted") -> None:
        colour = {"ok": "#4cc46a", "warning": "#e5b567", "error": "#e06c75",
                  "muted": "#8a8a8a"}.get(level, "#8a8a8a")
        self._note.configure(text=text, text_color=colour)


# --------------------------------------------------------------------------- #
# tab + pop-out wrappers
# --------------------------------------------------------------------------- #
class FileEditorTab(FileEditorFrame):
    """Sidebar tab. Signature matches the other tabs so lazy loading works."""

    def __init__(self, parent, config_manager=None, status_callback=None):
        self.config_manager = config_manager
        super().__init__(parent, path=None, status_callback=status_callback,
                         show_file_list=True)


def open_file_editor_window(master, path, status_callback=None, title=None):
    """Pop out a one-file editor, so any tab can offer 'edit this file'."""
    win = ctk.CTkToplevel(master)
    win.title(title or f"Edit — {Path(path).name}")
    win.geometry("1100x700")
    win.grid_rowconfigure(0, weight=1)
    win.grid_columnconfigure(0, weight=1)
    frame = FileEditorFrame(win, path=path, status_callback=status_callback,
                            show_file_list=False)
    frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
    try:
        win.after(200, win.lift)
        win.after(250, win.focus_force)
    except Exception:
        pass
    return frame


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _atomic_write(path: Path, content: str) -> None:
    import os
    import shutil
    path = Path(path)
    if path.is_file():
        try:
            shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        except Exception:
            pass
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8", newline="")
    os.replace(tmp, path)


def _ask(parent, title: str, prompt: str) -> Optional[str]:
    """A themed one-line prompt — tkinter's simpledialog renders light-on-dark."""
    dlg = ctk.CTkToplevel(parent)
    dlg.title(title)
    dlg.geometry("420x150")
    dlg.transient(parent.winfo_toplevel())
    dlg.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(dlg, text=prompt, font=("Segoe UI", 12), anchor="w",
                 wraplength=390).grid(row=0, column=0, sticky="ew", padx=16,
                                      pady=(16, 6))
    var = tk.StringVar()
    entry = ctk.CTkEntry(dlg, textvariable=var, font=MONO)
    entry.grid(row=1, column=0, sticky="ew", padx=16)
    out = {"value": None}

    def ok(*_):
        out["value"] = var.get().strip() or None
        dlg.destroy()

    row = ctk.CTkFrame(dlg, fg_color="transparent")
    row.grid(row=2, column=0, sticky="e", padx=16, pady=14)
    ctk.CTkButton(row, text="Cancel", width=80, fg_color="#4a4a4a",
                  hover_color="#5a5a5a", command=dlg.destroy).grid(row=0, column=0, padx=4)
    ctk.CTkButton(row, text="OK", width=80, command=ok).grid(row=0, column=1, padx=4)
    entry.bind("<Return>", ok)
    try:
        dlg.after(120, lambda: (dlg.lift(), dlg.grab_set(), entry.focus_force()))
    except Exception:
        pass
    dlg.wait_window()
    return out["value"]
