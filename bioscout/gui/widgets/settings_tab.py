"""bioscout.gui.widgets.settings_tab — how the app looks on this machine.

Deliberately narrow. This tab edits ``~/.bioscout/gui_settings.json`` and
nothing else: appearance, window behaviour, and the folders the file pickers
start in. Anything that describes the DATA — body mass, trial windows, EMG map,
filter cut-offs — belongs to the session and is edited in the File Editor, not
here. Keeping the two apart is the whole point; a UI scale that ended up in a
project file would follow the data onto someone else's screen.
"""
import logging
import tkinter.filedialog as filedialog
from pathlib import Path

import customtkinter as ctk

from ..gui_settings import (ACCENTS, BASE_SCALE, DEFAULTS, SCALE_MAX,
                            SCALE_MIN, apply_appearance, gui_settings,
                            settings_path)

logger = logging.getLogger(__name__)


class SettingsTab(ctk.CTkFrame):
    """GUI settings. Takes the standard (config_manager, status_callback) pair
    so it registers like every other tab, but uses neither for its own state."""

    def __init__(self, parent, config_manager=None, status_callback=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.status_callback = status_callback
        self.settings = gui_settings()
        self._build()

    # ------------------------------------------------------------------ ui
    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 2))
        ctk.CTkLabel(header, text="Settings", font=("Segoe UI", 16, "bold")
                     ).pack(side="left")
        ctk.CTkLabel(header, text=f"  {settings_path()}", font=("Segoe UI", 10),
                     text_color="#888888").pack(side="left", padx=(8, 0))

        body = ctk.CTkScrollableFrame(self)
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(4, 8))
        body.grid_columnconfigure(0, weight=1)

        self._appearance_section(body)
        self._window_section(body)
        self._paths_section(body)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 10))
        # Every change ALREADY writes to disk immediately — this button exists
        # because an auto-saving page with no Save button reads as an
        # unsaveable page. It re-writes the file and says where it went.
        ctk.CTkButton(footer, text="💾 Save settings", width=150,
                      command=self._save_now).pack(side="left", padx=(0, 8))
        ctk.CTkButton(footer, text="Reset to defaults", width=150,
                      fg_color="#5a3a00", hover_color="#7a5000",
                      command=self._reset).pack(side="left")
        self.status = ctk.CTkLabel(footer, text="", font=("Segoe UI", 11),
                                   text_color="#28a745")
        self.status.pack(side="left", padx=12)

    def _card(self, parent, title, subtitle=""):
        card = ctk.CTkFrame(parent)
        card.pack(fill="x", pady=(0, 12))
        card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(card, text=title, font=("Segoe UI", 13, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(12, 2))
        if subtitle:
            ctk.CTkLabel(card, text=subtitle, font=("Segoe UI", 11),
                         text_color="#8a8a8a", justify="left", wraplength=760
                         ).grid(row=1, column=0, columnspan=3, sticky="w",
                                padx=14, pady=(0, 8))
        return card

    # ------------------------------------------------------- appearance
    def _appearance_section(self, parent):
        card = self._card(
            parent, "Appearance",
            "UI scale resizes widgets AND text together. 100 % is what used "
            "to be 120 % — the size most people ran the app at. Widgets, the "
            "console and the tables all follow it immediately; use 'Apply "
            "cleanly' only if a panel ends up mid-layout.")

        ctk.CTkLabel(card, text="UI scale", font=("Segoe UI", 12)).grid(
            row=2, column=0, sticky="w", padx=14, pady=6)
        self.scale_value = ctk.CTkLabel(card, text="", font=("Segoe UI", 12, "bold"),
                                        width=60)
        self.scale_value.grid(row=2, column=2, sticky="e", padx=14)
        self.scale_slider = ctk.CTkSlider(
            card, from_=SCALE_MIN, to=SCALE_MAX,
            number_of_steps=int((SCALE_MAX - SCALE_MIN) * 20),
            command=self._on_scale_slide)
        self.scale_slider.set(self.settings.scale())
        self.scale_slider.grid(row=2, column=1, sticky="ew", padx=14, pady=6)
        self._show_scale(self.settings.scale())
        # Commit on RELEASE only. The first version re-scaled the whole widget
        # tree live on every slider step — dozens of full re-layouts per drag,
        # which is exactly the flicker "scaling doesn't work very well" names.
        self.scale_slider.bind("<ButtonRelease-1>", lambda _e: self._commit_scale())

        ctk.CTkLabel(card, text="Quick sizes", font=("Segoe UI", 12)).grid(
            row=3, column=0, sticky="w", padx=14, pady=(0, 10))
        quick = ctk.CTkFrame(card, fg_color="transparent")
        quick.grid(row=3, column=1, columnspan=2, sticky="w", padx=14, pady=(0, 10))
        # Rebased: "100 %" now means BASE_SCALE (1.2) in toolkit units, so
        # these are the readable steps either side of it, not the old ones.
        for label, value in (("Smaller 85%", 0.85), ("Small 92%", 0.92),
                             ("Normal 100%", 1.0), ("Large 115%", 1.15),
                             ("Larger 130%", 1.3)):
            ctk.CTkButton(quick, text=label, width=96, height=28,
                          font=("Segoe UI", 11),
                          command=lambda v=value: self._set_scale(v)
                          ).pack(side="left", padx=(0, 6))
        # A live re-scale leaves plain-Tk widgets (console, tables) at the old
        # size and can leave grids mid-layout; a relaunch rebuilds everything
        # at the stored scale, which is the clean path.
        ctk.CTkButton(quick, text="Apply cleanly (reload)", width=150, height=28,
                      font=("Segoe UI", 11),
                      fg_color="#5a3a00", hover_color="#7a5000",
                      command=self._reload_app).pack(side="left", padx=(12, 0))

        ctk.CTkLabel(card, text="Theme", font=("Segoe UI", 12)).grid(
            row=4, column=0, sticky="w", padx=14, pady=(0, 6))
        self.appearance_var = ctk.StringVar(
            value=str(self.settings.get("ui.appearance", "dark")))
        ctk.CTkSegmentedButton(
            card, values=["dark", "light", "system"],
            variable=self.appearance_var, command=self._on_appearance
        ).grid(row=4, column=1, sticky="w", padx=14, pady=(0, 6))

        ctk.CTkLabel(card, text="Base colour", font=("Segoe UI", 12)).grid(
            row=5, column=0, sticky="w", padx=14, pady=(0, 12))
        accent_row = ctk.CTkFrame(card, fg_color="transparent")
        accent_row.grid(row=5, column=1, columnspan=2, sticky="w",
                        padx=14, pady=(0, 12))
        self.accent_var = ctk.StringVar(value=self.settings.accent())
        # Swatches, not a dropdown: the choice IS the colour, and a name in a
        # list does not tell you what "teal" looks like on this theme.
        self._accent_btns = {}
        for name, (fg, hover) in ACCENTS.items():
            b = ctk.CTkButton(accent_row, text=name, width=74, height=28,
                              font=("Segoe UI", 11),
                              fg_color=fg, hover_color=hover,
                              command=lambda n=name: self._pick_accent(n))
            b.pack(side="left", padx=(0, 5))
            self._accent_btns[name] = b
        self._mark_accent(self.accent_var.get())

    def _show_scale(self, value):
        self.scale_value.configure(text=f"{float(value) * 100:.0f}%")

    def _on_scale_slide(self, value):
        # While dragging: update the NUMBER only. Re-scaling the widget tree on
        # every step was the jank — one apply on release is the fix.
        self._show_scale(value)

    def _commit_scale(self):
        self._set_scale(self.scale_slider.get())

    def _set_scale(self, value):
        value = max(SCALE_MIN, min(SCALE_MAX, float(value)))
        self.scale_slider.set(value)
        self._show_scale(value)
        self.settings.set("ui.scale", round(value, 2))
        # live=True: widget scaling + plain-tk fonts only. Re-applying WINDOW
        # scaling to a live window is what made it jump and un-maximise.
        apply_appearance(self.settings, live=True)
        self._saved(f"UI scale {value * 100:.0f}%")

    def _pick_accent(self, name):
        self.accent_var.set(name)
        self._mark_accent(name)
        self._on_accent(name)

    def _mark_accent(self, name):
        """A border on the chosen swatch — with seven same-sized buttons there
        is otherwise nothing on screen saying which one is active."""
        for n, b in getattr(self, "_accent_btns", {}).items():
            b.configure(border_width=(2 if n == name else 0),
                        border_color="#ffffff")

    def _reload_app(self):
        """Relaunch through the main window's own restart, so the whole tree is
        rebuilt at the stored scale (this is what makes plain-Tk parts follow)."""
        top = self.winfo_toplevel()
        restart = getattr(top, "_restart_app", None)
        if callable(restart):
            restart()
        else:
            self._saved("use the Reload App button in the sidebar")

    def _on_appearance(self, value):
        self.settings.set("ui.appearance", value)
        apply_appearance(self.settings, live=True)
        self._saved(f"theme: {value}")

    def _on_accent(self, value):
        """Base colour. customtkinter reads widget colours when the widget is
        CREATED, so existing widgets keep the old accent — say so and offer
        the reload rather than pretending it applied."""
        self.settings.set("ui.accent", value)
        self._saved(f"base colour: {value} — reload to apply everywhere")

    # ----------------------------------------------------------- window
    def _window_section(self, parent):
        card = self._card(
            parent, "Window",
            "Remembering the window puts it back where you left it — including "
            "on a second monitor that may not be attached next time. Turn it "
            "off if the app ever opens off-screen.")

        self.remember_var = ctk.BooleanVar(
            value=bool(self.settings.get("window.remember", True)))
        ctk.CTkCheckBox(card, text="Remember window size and position",
                        variable=self.remember_var, font=("Segoe UI", 12),
                        command=lambda: self._flag("window.remember",
                                                   self.remember_var.get())
                        ).grid(row=2, column=0, columnspan=3, sticky="w",
                               padx=14, pady=6)

        self.maximised_var = ctk.BooleanVar(
            value=bool(self.settings.get("window.start_maximised", True)))
        ctk.CTkCheckBox(card, text="Start maximised",
                        variable=self.maximised_var, font=("Segoe UI", 12),
                        command=lambda: self._flag("window.start_maximised",
                                                   self.maximised_var.get())
                        ).grid(row=3, column=0, columnspan=3, sticky="w",
                               padx=14, pady=(0, 6))

        geom = self.settings.get("window.geometry", "") or "not saved yet"
        self.geom_label = ctk.CTkLabel(card, text=f"Saved geometry: {geom}",
                                       font=("Segoe UI", 11), text_color="#8a8a8a")
        self.geom_label.grid(row=4, column=0, columnspan=2, sticky="w",
                             padx=14, pady=(0, 12))
        ctk.CTkButton(card, text="Forget", width=90, font=("Segoe UI", 11),
                      command=self._forget_geometry
                      ).grid(row=4, column=2, sticky="e", padx=14, pady=(0, 12))

    def _forget_geometry(self):
        self.settings.set("window.geometry", "")
        self.geom_label.configure(text="Saved geometry: not saved yet")
        self._saved("window geometry cleared")

    # ------------------------------------------------------------ paths
    def _paths_section(self, parent):
        card = self._card(
            parent, "Starting folders",
            "Where the file pickers open. These are remembered per machine and "
            "never written into a project — a path from someone else's disk is "
            "worse than no path at all.")
        self._path_rows = {}
        rows = (("paths.last_project", "Project"),
                ("paths.last_c3d_source", "C3D source"),
                ("paths.last_c3d_dest", "C3D destination"))
        for i, (key, label) in enumerate(rows):
            r = 2 + i
            ctk.CTkLabel(card, text=label, font=("Segoe UI", 12)).grid(
                row=r, column=0, sticky="w", padx=14, pady=6)
            var = ctk.StringVar(value=str(self.settings.get(key, "")))
            entry = ctk.CTkEntry(card, textvariable=var, font=("Segoe UI", 11))
            entry.grid(row=r, column=1, sticky="ew", padx=8, pady=6)
            entry.bind("<FocusOut>", lambda _e, k=key, v=var:
                       self._set_path(k, v.get()))
            ctk.CTkButton(card, text="Browse", width=90, font=("Segoe UI", 11),
                          command=lambda k=key, v=var: self._browse(k, v)
                          ).grid(row=r, column=2, sticky="e", padx=14, pady=6)
            self._path_rows[key] = var
        card.grid_rowconfigure(len(rows) + 2, minsize=8)

    def _browse(self, key, var):
        start = var.get() or str(Path.home())
        folder = filedialog.askdirectory(title=f"Select folder", initialdir=start)
        if folder:
            var.set(folder)
            self._set_path(key, folder)

    def _set_path(self, key, value):
        self.settings.set(key, value)
        self._saved(key.split(".")[-1].replace("_", " "))

    # ---------------------------------------------------------- plumbing
    def _flag(self, key, value):
        self.settings.set(key, bool(value))
        self._saved(key.split(".")[-1].replace("_", " "))

    def _reset(self):
        self.settings.reset()
        apply_appearance(self.settings, live=True)
        self.scale_slider.set(self.settings.scale())
        self._show_scale(self.settings.scale())
        self.appearance_var.set(str(self.settings.get("ui.appearance")))
        self._mark_accent(self.settings.accent())
        self.remember_var.set(bool(self.settings.get("window.remember")))
        self.maximised_var.set(bool(self.settings.get("window.start_maximised")))
        for key, var in getattr(self, "_path_rows", {}).items():
            var.set(str(self.settings.get(key, "")))
        self.geom_label.configure(text="Saved geometry: not saved yet")
        self._saved("reset to defaults")

    def _save_now(self):
        ok = self.settings.save()
        self.status.configure(
            text=(f"✓ all settings saved to {settings_path()}" if ok
                  else f"✗ could not write {settings_path()}"),
            text_color=("#28a745" if ok else "#dc3545"))
        self.after(4000, lambda: self.status.configure(text=""))

    def _saved(self, what):
        # The store writes on every set(), so "saved" is a statement of fact —
        # but say so only when it is: a failed write must not read as success.
        ok = self.settings.save()
        self.status.configure(
            text=(f"✓ saved — {what}" if ok else f"✗ could not write {settings_path()}"),
            text_color=("#28a745" if ok else "#dc3545"))
        if self.status_callback:
            try:
                self.status_callback(f"Settings: {what}")
            except Exception:                                  # noqa: BLE001
                pass
        self.after(2500, lambda: self.status.configure(text=""))

    # main_window broadcasts these to every tab that has them
    def set_project_dir(self, project_dir):
        if project_dir:
            self.settings.remember_path("paths.last_project", project_dir)
            var = getattr(self, "_path_rows", {}).get("paths.last_project")
            if var is not None:
                var.set(str(project_dir))


__all__ = ["SettingsTab"]
