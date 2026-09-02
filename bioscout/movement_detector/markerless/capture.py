"""
capture.py -- get a video file to analyse, on Android or on the desktop.

Android path uses the system camera app via ACTION_VIDEO_CAPTURE rather than a
custom camera preview: the OS app handles focus, orientation, codecs and
storage, which is a large amount of fragile code not to have to write, and it
hands back a normal mp4 that MediaPipe can read.
"""
from __future__ import annotations

import os

try:  # pragma: no cover - only true inside an APK
    from android import activity as android_activity  # noqa: F401
    from android.permissions import Permission, request_permissions
    from jnius import autoclass, cast
    ON_ANDROID = True
except Exception:
    ON_ANDROID = False

REQUEST_VIDEO = 0x5501


def ensure_permissions(callback=None):
    """Ask for camera + storage. No-op off Android."""
    if not ON_ANDROID:
        if callback:
            callback(True)
        return
    perms = [Permission.CAMERA, Permission.RECORD_AUDIO,
             Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE]

    def _on_result(permissions, grants):
        if callback:
            callback(all(grants))

    request_permissions(perms, _on_result)


def app_storage_dir():
    """A writable directory for videos and results."""
    if ON_ANDROID:
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        ctx = PythonActivity.mActivity
        base = ctx.getExternalFilesDir(None)
        path = base.getAbsolutePath() if base else ctx.getFilesDir().getAbsolutePath()
    else:
        path = os.path.join(os.path.expanduser("~"), "pullup_sessions")
    os.makedirs(path, exist_ok=True)
    return path


def record_video(on_done, max_seconds=30, quality=1):
    """Launch the system camera in video mode; on_done(path_or_None) when back.

    quality: 0 = low (smaller file, faster pose pass), 1 = high.
    """
    if not ON_ANDROID:
        on_done(None)
        return

    from android import activity
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Intent = autoclass("android.content.Intent")
    MediaStore = autoclass("android.provider.MediaStore")

    intent = Intent(MediaStore.ACTION_VIDEO_CAPTURE)
    intent.putExtra(MediaStore.EXTRA_DURATION_LIMIT, int(max_seconds))
    intent.putExtra(MediaStore.EXTRA_VIDEO_QUALITY, int(quality))

    def _on_activity_result(request_code, result_code, data):
        if request_code != REQUEST_VIDEO:
            return
        activity.unbind(on_activity_result=_on_activity_result)
        if result_code != -1 or data is None:  # -1 == RESULT_OK
            on_done(None)
            return
        try:
            on_done(_copy_uri_to_file(data.getData()))
        except Exception:
            on_done(None)

    activity.bind(on_activity_result=_on_activity_result)
    PythonActivity.mActivity.startActivityForResult(intent, REQUEST_VIDEO)


def _copy_uri_to_file(uri):
    """Content URIs are not file paths -- stream the bytes to our own file."""
    import time
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    ctx = PythonActivity.mActivity
    stream = ctx.getContentResolver().openInputStream(uri)
    out_path = os.path.join(app_storage_dir(), "pullup_%d.mp4" % int(time.time()))
    buf = bytearray(64 * 1024)
    with open(out_path, "wb") as f:
        while True:
            n = stream.read(buf)
            if n <= 0:
                break
            f.write(bytes(buf[:n]))
    stream.close()
    return out_path


def pick_video_desktop():
    """Desktop fallback: a plain file dialog, or None if unavailable."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        path = filedialog.askopenfilename(
            title="Choose a pull-up video",
            filetypes=[("Video", "*.mp4 *.mov *.webm *.avi"), ("All", "*.*")])
        root.destroy()
        return path or None
    except Exception:
        return None
