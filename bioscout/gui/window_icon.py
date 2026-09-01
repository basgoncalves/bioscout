"""One place that puts the BioScout logo on a window and its taskbar button.

`main_window` did this correctly and every other window did not, so a dialog
launched on its own -- `bioscout session edit`, the model editor, any future
standalone tool -- came up wearing the generic Python feather.

Two separate things have to happen, and only one of them is obvious:

  * `iconbitmap(default=...)` sets the TITLE-BAR icon, and `default=True`
    makes child windows inherit it.
  * the TASKBAR button is grouped by AppUserModelID, and a Python process
    inherits python.exe's. Until an explicit ID is claimed, Windows groups the
    window with every other Python program and shows their icon, however good
    the .ico is. `SetCurrentProcessExplicitAppUserModelID` is what separates it.

On Linux/macOS `iconbitmap` is ignored and `wm_iconphoto` is what the window
manager reads, so both are set.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

APP_ID = "Anthropic.BioScout.GUI"        # any stable unique string
_LOGO = Path(__file__).resolve().parent.parent / "utils" / "logo.png"
_keep: list = []                          # PhotoImage refs; Tk does not own them


def claim_app_id(app_id: str = APP_ID) -> None:
    """Windows: group this process's taskbar button under our own identity."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:                                          # noqa: BLE001
        pass


def ico_path() -> Path | None:
    """logo.png -> a multi-resolution .ico in the temp dir, built once."""
    if not _LOGO.exists():
        return None
    out = Path(tempfile.gettempdir()) / "bioscout_icon.ico"
    if out.exists():
        return out
    try:
        from PIL import Image
        Image.open(_LOGO).convert("RGBA").save(
            str(out), format="ICO",
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                   (64, 64), (128, 128), (256, 256)])
        return out
    except Exception:                                          # noqa: BLE001
        return None


def apply(win, *, app_id: str = APP_ID) -> None:
    """Icon + taskbar identity for `win`. Never raises: a missing logo or a
    Pillow that cannot write .ico must not stop a window from opening."""
    claim_app_id(app_id)
    try:
        p = ico_path()
        if p is not None:
            win.iconbitmap(default=str(p))     # default -> child windows too
    except Exception:                                          # noqa: BLE001
        pass
    try:
        from PIL import Image, ImageTk
        if _LOGO.exists():
            img = ImageTk.PhotoImage(
                Image.open(_LOGO).convert("RGBA").resize((64, 64)))
            _keep.append(img)
            win.wm_iconphoto(True, img)
    except Exception:                                          # noqa: BLE001
        pass
