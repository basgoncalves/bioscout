"""BioScout-style look for the MRI2MSK GUI (dark CustomTkinter).

Palette sampled from the BioScout app: near-black window, dark-grey sidebar and
cards, blue primary buttons, green success, muted status colours.
"""
from __future__ import annotations

import sys
from pathlib import Path

import customtkinter as ctk

ASSETS = Path(__file__).resolve().parent / "assets"

BG = "#1a1a1a"          # window / content
SIDEBAR = "#2b2b2b"
TOPBAR = "#333333"
CARD = "#29292e"
CARD_BORDER = "#3a3a40"
FIELD = "#202024"
ACCENT = "#1f6aa5"
ACCENT_HOVER = "#144870"
SUCCESS = "#25a845"
SUCCESS_HOVER = "#1c8236"
DANGER = "#a83232"
NEUTRAL = "#3d3d44"
NEUTRAL_HOVER = "#4b4b54"
TEXT = "#e8e8e8"
MUTED = "#9a9aa2"

ST_DONE = "#4cc36a"
ST_READY = "#f0a030"
ST_WAIT = "#4aa3ff"
ST_IDLE = "#8a8a92"
ST_RUN = "#f0a030"
ST_ERR = "#ff6b6b"

FONT = "Segoe UI" if sys.platform.startswith("win") else "Helvetica"
MONO = "Consolas" if sys.platform.startswith("win") else "DejaVu Sans Mono"


def setup():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")


def f(size=12, weight="normal"):
    return ctk.CTkFont(family=FONT, size=size, weight=weight)


def card(parent, title: str | None = None, **kw) -> ctk.CTkFrame:
    """Rounded dark panel with an optional bold title; returns the frame.
    Put content into ``frame.body``."""
    fr = ctk.CTkFrame(parent, fg_color=CARD, border_color=CARD_BORDER, border_width=1, corner_radius=10, **kw)
    if title:
        ctk.CTkLabel(fr, text=title, font=f(14, "bold"), text_color=TEXT, anchor="w").pack(
            fill="x", padx=14, pady=(10, 2))
    body = ctk.CTkFrame(fr, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=12, pady=(4, 12))
    fr.body = body
    return fr


def button(parent, text, command=None, kind="primary", width=90, **kw) -> ctk.CTkButton:
    colors = {"primary": (ACCENT, ACCENT_HOVER), "success": (SUCCESS, SUCCESS_HOVER),
              "neutral": (NEUTRAL, NEUTRAL_HOVER), "danger": (DANGER, "#842626")}[kind]
    return ctk.CTkButton(parent, text=text, command=command, width=width, height=30, corner_radius=6,
                         fg_color=colors[0], hover_color=colors[1], text_color=TEXT,
                         text_color_disabled="#6c6c74", font=f(12), **kw)


def entry(parent, var, width=200, readonly=False) -> ctk.CTkEntry:
    e = ctk.CTkEntry(parent, textvariable=var, width=width, height=30, corner_radius=6,
                     fg_color=FIELD, border_color=CARD_BORDER, text_color=TEXT if not readonly else MUTED,
                     font=f(12))
    if readonly:
        e.configure(state="readonly")
    return e


def label(parent, text="", size=12, color=TEXT, weight="normal", **kw) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=text, font=f(size, weight), text_color=color, anchor="w", **kw)


def set_enabled(widget, on: bool):
    try:
        widget.configure(state="normal" if on else "disabled")
    except Exception:  # noqa: BLE001
        pass


def is_enabled(widget) -> bool:
    try:
        return widget.cget("state") != "disabled"
    except Exception:  # noqa: BLE001
        return True


def image(name: str, height: int | None = None):
    """CTkImage from assets/ (None if missing)."""
    p = ASSETS / name
    if not p.is_file():
        return None
    from PIL import Image
    im = Image.open(p)
    if height:
        im = im.resize((round(im.width * height / im.height), height))
    return ctk.CTkImage(light_image=im, dark_image=im, size=im.size)


def style_treeview(root):
    """Dark ttk.Treeview matching the CTk theme."""
    from tkinter import ttk
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except Exception:  # noqa: BLE001
        pass
    st.configure("Dark.Treeview", background=SIDEBAR, fieldbackground=SIDEBAR, foreground=TEXT,
                 rowheight=24, borderwidth=0, font=(FONT, 10))
    st.configure("Dark.Treeview.Heading", background=TOPBAR, foreground=TEXT, relief="flat",
                 font=(FONT, 10, "bold"))
    st.map("Dark.Treeview", background=[("selected", ACCENT)], foreground=[("selected", "white")])
    st.map("Dark.Treeview.Heading", background=[("active", NEUTRAL)])
    st.configure("Dark.Vertical.TScrollbar", background=NEUTRAL, troughcolor=SIDEBAR, borderwidth=0,
                 arrowcolor=TEXT)


def set_app_icon(root):
    """Window + Windows-taskbar icon from assets/icon.ico / icon_64.png."""
    ico, png = ASSETS / "icon.ico", ASSETS / "icon_64.png"
    if sys.platform.startswith("win") and ico.is_file():
        try:
            root.iconbitmap(str(ico))
            # CustomTkinter resets the icon ~200 ms after start; set it again afterwards
            root.after(300, lambda: root.iconbitmap(str(ico)))
        except Exception:  # noqa: BLE001
            pass
    if png.is_file():
        try:
            from PIL import Image, ImageTk
            ph = ImageTk.PhotoImage(Image.open(png))
            root.iconphoto(True, ph)
            root._mri2msk_icon = ph  # keep a reference
        except Exception:  # noqa: BLE001
            pass


def set_windows_app_id(app_id="univie.neuromechanics.mri2msk"):
    """Own taskbar entry/icon instead of python.exe's (call before creating the window)."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:  # noqa: BLE001
            pass
