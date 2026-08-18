"""Deprecated shim — the dialog became :mod:`bioscout.gui.session_editor`.

The original asked three questions and wrote a file. It now needs to edit an
existing session as well as create one, so it grew into a form; this module
stays so that any caller importing the old names keeps working.
"""
from .session_editor import ask_new_session, gui_available, open_session_editor  # noqa: F401

__all__ = ["ask_new_session", "gui_available", "open_session_editor"]
