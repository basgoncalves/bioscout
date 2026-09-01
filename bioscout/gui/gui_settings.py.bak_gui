"""bioscout.gui.gui_settings — how the app LOOKS on this machine.

Two kinds of setting get confused constantly, so this module holds exactly one
of them:

* **Project settings** — body mass, trial windows, EMG map, filter cut-offs.
  These describe the DATA. They live in ``session.yaml`` and travel with it, so
  a collaborator re-running the study gets the same numbers.
* **GUI settings** — window size, UI scale, which folder the file picker opens
  in. These describe THIS INSTALL on THIS MACHINE. They must not travel: a
  window size committed to a repository is noise, and a remembered folder from
  someone else's disk is worse than none.

Only the second kind lives here, in ``~/.bioscout/gui_settings.json``.

WHY NOT ConfigManager
    ``ConfigManager.save()`` writes back to ``bioscout/config/default_config.yaml``
    — a file INSIDE the installed package. Putting per-machine state there
    dirties a version-controlled file, is wiped by ``pip install -U``, and fails
    outright when the install directory is read-only. So GUI state gets its own
    per-user file. ConfigManager keeps doing what it is for: analysis defaults
    that ship with the code.

Reads never raise: a missing, empty or corrupt file gives the defaults, because
losing your window size is not a reason to fail to start.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

#: Every key this module knows about, with its default. A key not listed here
#: still works — the store is a plain dict — but listing it is what makes it
#: discoverable from the Settings tab.
DEFAULTS = {
    # -- appearance -------------------------------------------------------
    "ui.scale": 1.0,            # customtkinter widget+font scaling, 0.8 – 2.0
    "ui.appearance": "dark",    # dark | light | system
    # -- window -----------------------------------------------------------
    "window.remember": True,    # restore last size/position on launch
    "window.geometry": "",      # "WxH+X+Y", written on close
    "window.start_maximised": True,
    # -- last-used paths (per machine, never per project) ------------------
    "paths.last_project": "",
    "paths.last_c3d_source": "",
    "paths.last_c3d_dest": "",
}

SCALE_MIN, SCALE_MAX = 0.7, 2.0


def settings_path() -> Path:
    """``~/.bioscout/gui_settings.json``, or ``$BIOSCOUT_GUI_SETTINGS``.

    The env var exists so a test — or a second instance driving a demo — can
    point somewhere disposable without touching the real user's file."""
    env = os.environ.get("BIOSCOUT_GUI_SETTINGS")
    return Path(env) if env else Path.home() / ".bioscout" / "gui_settings.json"


class GuiSettings:
    """A tiny JSON-backed key/value store with dot-notation keys.

        s = GuiSettings()
        s.get("ui.scale")               # 1.0
        s.set("ui.scale", 1.25)         # written to disk immediately
    """

    def __init__(self, path=None):
        self.path = Path(path) if path else settings_path()
        self._data = {}
        self.load()

    # -- io ---------------------------------------------------------------
    def load(self):
        """Re-read from disk. Never raises."""
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self._data = data if isinstance(data, dict) else {}
        except Exception:                                      # noqa: BLE001
            self._data = {}
        return self

    def save(self):
        """Write to disk. Returns True on success — callers may ignore it, but
        the Settings tab reports a failure rather than pretending it saved."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Write-and-rename: a half-written JSON file would make every later
            # load() silently fall back to defaults, which reads as "the app
            # forgot my settings" rather than as the disk error it is.
            tmp = self.path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, sort_keys=True)
            os.replace(tmp, self.path)
            return True
        except Exception:                                      # noqa: BLE001
            return False

    # -- access -----------------------------------------------------------
    def get(self, key, default=None):
        """Stored value, else the module default, else the caller's default.

        In that order deliberately: `get("window.remember", False)` must still
        return the stored/DEFAULTS value, not the caller's fallback. A caller's
        default only applies to a key this module has never heard of."""
        if key in self._data:
            return self._data[key]
        if key in DEFAULTS:
            return DEFAULTS[key]
        return default

    def set(self, key, value, save=True):
        self._data[key] = value
        if save:
            self.save()
        return value

    def update(self, mapping, save=True):
        self._data.update(mapping)
        if save:
            self.save()

    def reset(self, save=True):
        self._data = {}
        if save:
            self.save()

    def as_dict(self):
        d = dict(DEFAULTS)
        d.update(self._data)
        return d

    # -- convenience used by the shell ------------------------------------
    def scale(self):
        """UI scale, clamped. A settings file hand-edited to 12 instead of 1.2
        would otherwise open a window whose buttons are off-screen, with no way
        back to the Settings tab to undo it."""
        try:
            return max(SCALE_MIN, min(SCALE_MAX, float(self.get("ui.scale", 1.0))))
        except (TypeError, ValueError):
            return 1.0

    def remember_path(self, key, path):
        """Store a last-used folder, ignoring blanks and non-existent paths."""
        try:
            p = str(path or "")
            if p and Path(p).exists():
                self.set(key, p)
        except Exception:                                      # noqa: BLE001
            pass


#: Process-wide instance. The GUI is a single window; passing this object down
#: through five constructors bought nothing.
_ACTIVE = None


def gui_settings() -> GuiSettings:
    global _ACTIVE
    if _ACTIVE is None:
        _ACTIVE = GuiSettings()
    return _ACTIVE


def apply_appearance(settings=None):
    """Push the stored scale + appearance mode into customtkinter.

    ``set_widget_scaling`` is how "make the text bigger" is done in this
    toolkit: it scales widget geometry AND font sizes together, so the hundreds
    of ``font=("Segoe UI", 9)`` literals across the tabs do not have to be
    touched, and nothing goes out of proportion. ``set_window_scaling`` goes
    with it or every ``.geometry("1400x900")`` call stays in unscaled pixels
    and the enlarged widgets overflow a window that did not grow.

    WHAT THIS CANNOT DO, so the Settings tab must say it plainly: only CTk
    widgets rescale live. Plain-tkinter widgets (the console, table Text
    widgets, scrollbars) take their size from :func:`font_size` at CREATION —
    they follow the scale after an app reload, not while running. Changing
    scale mid-session is therefore a preview; Reload App is the clean apply.
    """
    s = settings or gui_settings()
    try:
        import customtkinter as ctk
        mode = str(s.get("ui.appearance", "dark")).lower()
        if mode in ("dark", "light", "system"):
            ctk.set_appearance_mode(mode)
        ctk.set_widget_scaling(s.scale())
        try:
            ctk.set_window_scaling(s.scale())
        except Exception:                                      # noqa: BLE001
            pass
    except Exception:                                          # noqa: BLE001
        pass
    return s


def font_size(base):
    """A font size in points at the current UI scale, for PLAIN tkinter
    widgets. CTk widgets scale their own fonts; ``tkinter.Text``, listboxes
    and scrollbars do not, and were the parts left small when everything else
    grew — pass their sizes through here at construction."""
    try:
        return max(7, int(round(float(base) * gui_settings().scale())))
    except Exception:                                          # noqa: BLE001
        return int(base)


__all__ = ["DEFAULTS", "SCALE_MIN", "SCALE_MAX", "GuiSettings", "gui_settings",
           "settings_path", "apply_appearance", "font_size"]
