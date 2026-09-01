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
    "ui.scale": 1.0,            # user scale, RELATIVE to BASE_SCALE (see below)
    "ui.appearance": "dark",    # dark | light | system
    "ui.accent": "blue",        # base colour, see ACCENTS
    "ui.scale_rebased": False,  # one-time migration marker, see _rebase()
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

#: What "100 %" means in toolkit units. The old 100 % was too small to read on
#: a high-DPI screen and everyone ran the app at 120 %, so 120 % IS the new
#: 100 % — every other size is relative to it (old 140 % ≈ new 117 %).
BASE_SCALE = 1.2

#: Minimum point size for BUTTON text. Dozens of buttons were written with
#: font=("Segoe UI", 7..9), which is unreadable at any window size; rather than
#: chase every literal, CTkButton is patched once (see _patch_button_fonts).
MIN_BUTTON_FONT = 11

#: Selectable base colours. fg / hover / a light-mode pair, in the shape
#: customtkinter's theme dict wants: [light, dark].
ACCENTS = {
    "blue":   ("#1f6aa5", "#144870"),
    "teal":   ("#0e7c86", "#0a5b63"),
    "green":  ("#2e7d32", "#1b5e20"),
    "purple": ("#6a3fa0", "#4b2c73"),
    "orange": ("#c2610a", "#8f4707"),
    "red":    ("#b13030", "#802020"),
    "grey":   ("#4a4a4a", "#333333"),
}


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

    def effective_scale(self):
        """What actually goes into customtkinter: the user scale times
        :data:`BASE_SCALE`. Keeping the two apart is what lets the Settings tab
        keep saying "100 %" while the app is really drawn at 120 %."""
        return self.scale() * BASE_SCALE

    def accent(self):
        name = str(self.get("ui.accent", "blue")).lower()
        return name if name in ACCENTS else "blue"

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


def _patch_button_fonts():
    """Raise every too-small BUTTON font, once, at the class level.

    The alternative was editing ~120 ``font=("Segoe UI", 7)`` literals across
    the tabs and re-editing them every time a widget is added. Buttons only:
    labels and entries are free to be small, an unreadable BUTTON is the thing
    that was actually reported."""
    global _FONTS_PATCHED
    if _FONTS_PATCHED:
        return
    try:
        import customtkinter as ctk
        orig = ctk.CTkButton.__init__

        def patched(self, *a, **kw):
            f = kw.get("font")
            if isinstance(f, (tuple, list)) and len(f) >= 2:
                try:
                    if float(f[1]) < MIN_BUTTON_FONT:
                        f = tuple(f)
                        kw["font"] = (f[0], MIN_BUTTON_FONT) + tuple(f[2:])
                except (TypeError, ValueError):
                    pass
            return orig(self, *a, **kw)

        ctk.CTkButton.__init__ = patched
        _FONTS_PATCHED = True
    except Exception:                                          # noqa: BLE001
        pass


def _apply_accent(ctk, name):
    """Recolour the theme's accent-coloured widgets in place.

    customtkinter only ships blue/green/dark-blue themes and reads colours out
    of ``ThemeManager.theme`` when a widget is CREATED — so this must run
    before the window is built, and a change mid-session needs a reload. Said
    plainly in the Settings tab rather than pretended away."""
    fg, hover = ACCENTS.get(name, ACCENTS["blue"])
    t = ctk.ThemeManager.theme
    pairs = [fg, fg]
    hpairs = [hover, hover]
    for widget, keys in (
            ("CTkButton", ("fg_color", "hover_color")),
            ("CTkCheckBox", ("fg_color", "hover_color")),
            ("CTkRadioButton", ("fg_color", "hover_color")),
            ("CTkSwitch", ("progress_color",)),
            ("CTkProgressBar", ("progress_color",)),
            ("CTkSlider", ("button_color", "button_hover_color", "progress_color")),
            ("CTkOptionMenu", ("fg_color", "button_color", "button_hover_color")),
            ("CTkComboBox", ("button_color", "button_hover_color")),
            ("CTkSegmentedButton", ("selected_color", "selected_hover_color")),
            ("CTkEntry", ()),
    ):
        d = t.get(widget)
        if not isinstance(d, dict):
            continue
        for k in keys:
            if k in d:
                d[k] = hpairs if "hover" in k else pairs


def apply_appearance(settings=None, live=False):
    """Push the stored scale, accent and appearance mode into customtkinter.

    ``set_widget_scaling`` is how "make the text bigger" is done in this
    toolkit: it scales widget geometry AND font sizes together, so the hundreds
    of ``font=("Segoe UI", 9)`` literals across the tabs do not have to be
    touched, and nothing goes out of proportion.

    ``live=True`` is the mid-session call from the Settings tab. It deliberately
    does NOT touch ``set_window_scaling``: doing that on an existing window
    makes CTk re-apply the geometry through deferred callbacks, which is what
    made the window jump, un-maximise and leave half-laid-out grids — the
    "scaling is buggy" report. Window scaling is set once, before the window
    exists (``live=False``).

    Plain-tkinter widgets (console, tables) do not follow CTk scaling at all;
    they are re-fonted explicitly by :func:`refresh_tk_fonts`.
    """
    s = settings or gui_settings()
    _rebase(s)
    try:
        import customtkinter as ctk
        mode = str(s.get("ui.appearance", "dark")).lower()
        if mode in ("dark", "light", "system"):
            ctk.set_appearance_mode(mode)
        if not live:
            _patch_button_fonts()
            _apply_accent(ctk, s.accent())
        ctk.set_widget_scaling(s.effective_scale())
        if not live:
            try:
                ctk.set_window_scaling(s.effective_scale())
            except Exception:                                  # noqa: BLE001
                pass
    except Exception:                                          # noqa: BLE001
        pass
    if live:
        refresh_tk_fonts()
    return s


def _rebase(s):
    """One-time migration to the new 100 %. Someone running at the old 120 %
    means "normal size" — after rebasing, normal size IS 120 %, so their stored
    1.2 must become 1.0 or the app doubles up to 144 %."""
    try:
        if bool(s.get("ui.scale_rebased", False)):
            return
        old = float(s.get("ui.scale", 1.0))
        s.set("ui.scale", round(max(SCALE_MIN, min(SCALE_MAX, old / BASE_SCALE)), 2),
              save=False)
        s.set("ui.scale_rebased", True)
    except Exception:                                          # noqa: BLE001
        pass


def font_size(base):
    """A font size in points at the current UI scale, for PLAIN tkinter
    widgets. CTk widgets scale their own fonts; ``tkinter.Text``, listboxes
    and scrollbars do not, and were the parts left small when everything else
    grew — pass their sizes through here at construction."""
    try:
        return max(7, int(round(float(base) * gui_settings().effective_scale())))
    except Exception:                                          # noqa: BLE001
        return int(base)


#: Plain-tk widgets that asked to follow the UI scale live.
#: (widget, family, base_size, extra) — weak-ish: dead widgets are dropped on
#: the next refresh rather than tracked, which is enough for a single window.
_TK_FONTS = []
_FONTS_PATCHED = False


def register_tk_font(widget, family, base, *extra):
    """Set ``widget``'s font at the current scale AND keep following it.

    This is the other half of the scaling fix: ``font_size()`` alone was
    applied at CREATION only, so the console and the tables stayed at the size
    they were born at until the app was relaunched — which is most of what
    "the rescaling is buggy" looked like."""
    _TK_FONTS.append((widget, family, float(base), tuple(extra)))
    try:
        widget.configure(font=(family, font_size(base)) + tuple(extra))
    except Exception:                                          # noqa: BLE001
        pass
    return widget


def refresh_tk_fonts():
    """Re-font every registered plain-tk widget at the current scale."""
    alive = []
    for w, fam, base, extra in _TK_FONTS:
        try:
            w.configure(font=(fam, font_size(base)) + extra)
            alive.append((w, fam, base, extra))
        except Exception:                                      # noqa: BLE001
            pass                                # widget destroyed — drop it
    _TK_FONTS[:] = alive


__all__ = ["DEFAULTS", "SCALE_MIN", "SCALE_MAX", "BASE_SCALE", "ACCENTS",
           "GuiSettings", "gui_settings", "settings_path", "apply_appearance",
           "font_size", "register_tk_font", "refresh_tk_fonts"]
