"""Video Analysis Tab - Generate MOT files and joint angle data from pre-recorded video."""

import customtkinter as ctk
from pathlib import Path
import sys
import os
import threading
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    import cv2
except ImportError as _cv2_err:
    raise ImportError(f"VideoAnalysisTab requires opencv-python: {_cv2_err}") from _cv2_err

try:
    from PIL import Image, ImageTk
except ImportError as _pil_err:
    raise ImportError(f"VideoAnalysisTab requires Pillow: {_pil_err}") from _pil_err

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
import tempfile
from typing import Dict, Optional, Tuple
from utils.logger import logger



class _Tooltip:
    """Lightweight tooltip shown on widget hover."""
    def __init__(self, widget, text: str):
        self._widget = widget
        self._text = text
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _show(self, event=None):
        if self._tip or not self._text:
            return
        x = self._widget.winfo_rootx() + 10
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        self._tip = tw = tk.Toplevel(self._widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)
        lbl = tk.Label(
            tw, text=self._text, justify="left",
            background="#222222", foreground="#eeeeee",
            relief="flat", borderwidth=0,
            font=("Segoe UI", 9),
            wraplength=260, padx=6, pady=4,
        )
        lbl.pack()

    def _hide(self, event=None):
        if self._tip:
            self._tip.destroy()
            self._tip = None


def _download_file(url: str, dest: Path, progress_cb=None, timeout: int = 20) -> None:
    """Download *url* to *dest* with chunked progress reporting and connect timeout."""
    import urllib.request as _ur
    req = _ur.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with _ur.urlopen(req, timeout=timeout) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        dest.parent.mkdir(parents=True, exist_ok=True)
        downloaded = 0
        chunk = 1 << 16  # 64 KB
        with open(dest, "wb") as fh:
            while True:
                buf = resp.read(chunk)
                if not buf:
                    break
                fh.write(buf)
                downloaded += len(buf)
                if progress_cb and total:
                    progress_cb(downloaded, total)


# Lazy-import to avoid hard crash if mediapipe/cv2 missing
AVAILABLE_MODELS = {}
try:
    from record.video import AVAILABLE_MODELS
except Exception as _e:
    logger.warning(f"VideoAnalysisTab: could not import AVAILABLE_MODELS: {_e}")

# Canvas display dimensions - used only as fallback before the widget is realised
_CANVAS_W = 840
_CANVAS_H = 473


class VideoAnalysisTab(ctk.CTkFrame):
    """Tab for analysing a pre-recorded video and generating OpenSim MOT files."""

    def __init__(self, parent, config_manager=None, update_status_callback=None):
        super().__init__(parent)

        self.config_manager = config_manager
        self.update_status = update_status_callback or (lambda x: None)

        self._video_path: Optional[Path] = None
        self._process: Optional[subprocess.Popen] = None
        self._running = False

        # First-frame image (PIL) at original resolution - needed for coord scaling
        self._frame_img: Optional[Image.Image] = None
        self._frame_photo: Optional[ImageTk.PhotoImage] = None

        # Time trim (seconds); None = use full video
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None
        self._video_duration: float = 0.0
        self._video_fps: float = 30.0

        # Video display transform (correct phone-captured portrait/rotated video)
        self._video_rotation: int = 0   # CW degrees: 0, 90, 180, 270
        self._video_flip_h: bool = False

        # Canvas zoom/pan — viewport in transformed-video pixel coords; None = fit
        self._view: Optional[Tuple[float, float, float, float]] = None
        self._pan_start: Optional[Tuple[int, int]] = None
        self._pan_view0: Optional[Tuple[float, float, float, float]] = None

        # Timeline canvas drag state
        self._tl_drag_target: Optional[str] = None   # 'in', 'out', 'scrub', 'region'
        self._tl_drag_x0: int = 0
        self._tl_drag_in0: float = 0.0
        self._tl_drag_out0: float = 0.0

        # Player bounding rect in VIDEO pixel coords: (x1, y1, x2, y2)
        self._player_rect: Optional[Tuple[int, int, int, int]] = None

        # Per-frame rect anchors: {frame_idx: (x1,y1,x2,y2)} in VIDEO pixels.
        self._frame_rects: Dict[int, Tuple[int, int, int, int]] = {}

        # Frames the user has manually placed/moved
        self._user_anchors: set = set()

        # Current frame index being previewed (updated by scrubber)
        self._current_frame_idx: int = 0

        # Auto-tracking state
        self._tracking: bool = False

        # Cached pose landmarks per frame for preview overlay
        self._frame_poses: Dict[int, dict] = {}
        self._previewing: bool = False

        self._calib_points: list = []        # calibration click points [(vx,vy), ...]
        self._scale_px_per_m: Optional[float] = None  # px per metre after calibration
        self._locked_frames: set = set()           # frame indices whose poses are manually locked
        self._custom_connections: list = []
        self._active_landmark: Optional[str] = None

        # Interaction mode: None | 'player' | 'move_rect' | 'resize_rect' | 'drag_point' | 'calibrate'
        self._interact_mode: Optional[str] = None
        self._drag_start: Optional[Tuple[int, int]] = None
        self._move_rect_canvas: Optional[Tuple[int, int, int, int]] = None
        self._resize_corner: Optional[str] = None
        self._drag_point_name: Optional[str] = None

        self._create_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _create_ui(self):
        # PanedWindow gives a draggable sash so the user can resize controls vs video
        self._paned = tk.PanedWindow(
            self, orient=tk.HORIZONTAL,
            sashwidth=6, sashcursor="sb_h_double_arrow",
            background="#444444", bd=0, relief="flat",
            sashrelief="flat",
        )
        self._paned.pack(fill="both", expand=True)

        # ===== LEFT PANEL =====
        left = ctk.CTkFrame(self._paned, fg_color="transparent")
        self._paned.add(left, minsize=220, width=450, sticky="nsew")

        ctk.CTkLabel(left, text="Video Analysis", font=("Segoe UI", 13, "bold")).pack(
            anchor="w", padx=10, pady=(0, 4)
        )

        scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=0, pady=0)

        # --- Video file ---
        self._section(scroll, "\U0001f3ac Input Video")
        self.video_entry = ctk.CTkEntry(scroll, placeholder_text="Select a video file…")
        self.video_entry.pack(fill="x", padx=10, pady=(0, 3))

        vbtn_row = ctk.CTkFrame(scroll, fg_color="transparent")
        vbtn_row.pack(fill="x", padx=10, pady=(0, 4))
        ctk.CTkButton(vbtn_row, text="Browse…", width=90, command=self._browse_video).pack(side="left")
        self.video_info_label = ctk.CTkLabel(vbtn_row, text="", text_color="#aaaaaa",
                                              font=("Segoe UI", 10))
        self.video_info_label.pack(side="left", padx=(8, 0))

        # --- Video transform row (rotate / flip / zoom) ---
        xform_row = ctk.CTkFrame(scroll, fg_color="transparent")
        xform_row.pack(fill="x", padx=10, pady=(0, 4))
        _xs = dict(height=22, fg_color="#333355", hover_color="#444477",
                   font=("Segoe UI", 11), width=32)
        ctk.CTkButton(xform_row, text="↺", command=lambda: self._rotate_video(-90),
                      **_xs).pack(side="left", padx=1)
        ctk.CTkButton(xform_row, text="↻", command=lambda: self._rotate_video(90),
                      **_xs).pack(side="left", padx=1)
        ctk.CTkButton(xform_row, text="⇔", command=self._flip_video_h,
                      **_xs).pack(side="left", padx=1)
        ctk.CTkLabel(xform_row, text="  AR:",
                     font=("Segoe UI", 10), text_color="#888888").pack(side="left")
        _ar = dict(height=22, fg_color="#335533", hover_color="#446644",
                   font=("Segoe UI", 10), width=36)
        ctk.CTkButton(xform_row, text="16:9",
                      command=lambda: self._crop_to_aspect_ratio(16, 9),
                      **_ar).pack(side="left", padx=1)
        ctk.CTkButton(xform_row, text="9:16",
                      command=lambda: self._crop_to_aspect_ratio(9, 16),
                      **_ar).pack(side="left", padx=1)
        ctk.CTkButton(xform_row, text="1:1",
                      command=lambda: self._crop_to_aspect_ratio(1, 1),
                      **_ar).pack(side="left", padx=1)
        ctk.CTkButton(xform_row, text="Fit", command=self._reset_zoom,
                      **_xs).pack(side="left", padx=(4, 1))
        self.zoom_label = ctk.CTkLabel(xform_row, text="100%",
                                        font=("Segoe UI", 9), text_color="#888888", width=36)
        self.zoom_label.pack(side="left", padx=4)
        _Tooltip(xform_row.winfo_children()[0],
                 "Rotate video 90° counter-clockwise")
        _Tooltip(xform_row.winfo_children()[1],
                 "Rotate video 90° clockwise")
        _Tooltip(xform_row.winfo_children()[2],
                 "Flip video horizontally (mirror)")

        # Hidden entries - values kept in sync with the trim sliders on the right
        self.start_entry = ctk.CTkEntry(scroll)   # not packed
        self.end_entry   = ctk.CTkEntry(scroll)   # not packed
        self.trim_status = ctk.CTkLabel(scroll, text="")  # not packed

        # --- Player Selection + Options ---
        self._section(scroll, "\U0001f3af Player & Detection")

        sel_frame = ctk.CTkFrame(scroll, fg_color="#2d2d2d", corner_radius=8)
        sel_frame.pack(fill="x", padx=10, pady=(0, 4))

        ctk.CTkLabel(sel_frame,
                     text="Draw a box around the player, then click Auto-Track.",
                     font=("Segoe UI", 10), text_color="#ffaa44",
                     wraplength=410, justify="left").pack(
            anchor="w", padx=10, pady=(4, 4))

        self.player_btn = ctk.CTkButton(
            sel_frame, text="➕ Draw Player Box",
            fg_color="#555555", hover_color="#666666",
            height=26, command=self._toggle_player_mode
        )
        self.player_btn.pack(fill="x", padx=10, pady=(0, 3))

        self.track_btn = ctk.CTkButton(
            sel_frame, text="\U0001f504 Auto-Track",
            fg_color="#225577", hover_color="#2a6699",
            height=28, command=self._auto_track, state="disabled"
        )
        self.track_btn.pack(fill="x", padx=10, pady=(0, 3))

        self.preview_btn = ctk.CTkButton(
            sel_frame, text="\U0001f9b4 Estimate Poses",
            fg_color="#334433", hover_color="#446644",
            height=28, command=lambda: self._preview_pose(single_frame=True), state="disabled"
        )
        self.preview_btn.pack(fill="x", padx=10, pady=(0, 3))

        self.clear_sel_btn = ctk.CTkButton(
            sel_frame, text="✖ Clear Selection",
            fg_color="#3a3a3a", hover_color="#4a4a4a",
            height=28, command=self._clear_selection
        )
        self.clear_sel_btn.pack(fill="x", padx=10, pady=(0, 4))

        # Hover tooltips
        _Tooltip(self.player_btn,
                 "Click then drag on the video to draw a box around the player.")
        _Tooltip(self.track_btn,
                 "Auto-Track: propagates the ROI from the current frame to the end "
                 "using the CSRT tracker. Locked frames are not changed.")
        _Tooltip(self.preview_btn,
                 "Estimate Poses: runs MediaPipe pose estimation on the current frame "
                 "only, seeding from the previous frame's pose if available.")
        _Tooltip(self.clear_sel_btn,
                 "Clear Selection: removes the player box and pose for the current frame only. Other frames are unchanged.")

        self.manual_edit_btn = ctk.CTkButton(
            sel_frame, text="\u270f Manual Edit",
            fg_color="#3a3355", hover_color="#4a4477",
            height=28, command=self._toggle_manual_edit
        )
        self.manual_edit_btn.pack(fill="x", padx=10, pady=(0, 4))
        _Tooltip(self.manual_edit_btn,
                 "Manual Edit: select a landmark from the right panel, then click on the video to place it.")

        # ROI resize buttons (visible once a player is selected)
        roi_resize_row = ctk.CTkFrame(sel_frame, fg_color="transparent")
        roi_resize_row.pack(fill="x", padx=10, pady=(0, 4))
        for col in range(4):
            roi_resize_row.grid_columnconfigure(col, weight=1)
        _btn_style = dict(height=24, fg_color="#333355", hover_color="#444466",
                          font=("Segoe UI", 10))
        ctk.CTkButton(roi_resize_row, text="◀ W",  **_btn_style,
                      command=lambda: self._resize_roi(-20, 0, 0, 0)
                      ).grid(row=0, column=0, padx=1, sticky="ew")
        ctk.CTkButton(roi_resize_row, text="W ▶",  **_btn_style,
                      command=lambda: self._resize_roi(0, 0, 20, 0)
                      ).grid(row=0, column=1, padx=1, sticky="ew")
        ctk.CTkButton(roi_resize_row, text="▲ H",  **_btn_style,
                      command=lambda: self._resize_roi(0, -20, 0, 0)
                      ).grid(row=0, column=2, padx=1, sticky="ew")
        ctk.CTkButton(roi_resize_row, text="H ▼",  **_btn_style,
                      command=lambda: self._resize_roi(0, 0, 0, 20)
                      ).grid(row=0, column=3, padx=1, sticky="ew")

        self.track_progress_label = ctk.CTkLabel(
            sel_frame, text="",
            font=("Segoe UI", 9), text_color="#aaaaaa",
            wraplength=410, justify="left"
        )
        self.track_progress_label.pack(anchor="w", padx=10, pady=(0, 2))

        self.sel_status_label = ctk.CTkLabel(
            sel_frame, text="⚠ No player selected — draw a box for best results",
            font=("Segoe UI", 9), text_color="#ffaa44",
            wraplength=410, justify="left"
        )
        self.sel_status_label.pack(anchor="w", padx=10, pady=(0, 3))

        ctk.CTkLabel(sel_frame, text="Pose detect interval (frames):",
                     font=("Segoe UI", 10)).pack(anchor="w", padx=10, pady=(0, 1))
        interval_row = ctk.CTkFrame(sel_frame, fg_color="transparent")
        interval_row.pack(fill="x", padx=10, pady=(0, 4))
        self.interval_var = ctk.IntVar(value=1)
        self.interval_label = ctk.CTkLabel(interval_row, text="1", width=30)
        self.interval_label.pack(side="right")
        ctk.CTkSlider(
            interval_row, from_=1, to=10, number_of_steps=9,
            variable=self.interval_var,
            command=lambda v: self.interval_label.configure(text=str(int(v)))
        ).pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(sel_frame, text="Pose smoothing — max Δpx per frame:",
                     font=("Segoe UI", 10)).pack(anchor="w", padx=10, pady=(0, 1))
        delta_row = ctk.CTkFrame(sel_frame, fg_color="transparent")
        delta_row.pack(fill="x", padx=10, pady=(0, 4))
        try:
            from settings import RecordingSettings as _RS2
            _default_delta = int(_RS2.DEFAULT_POSE_MAX_DELTA_PX)
        except Exception:
            _default_delta = 50
        self.delta_var = ctk.IntVar(value=_default_delta)
        self.delta_label = ctk.CTkLabel(delta_row, text=str(_default_delta), width=36)
        self.delta_label.pack(side="right")
        ctk.CTkSlider(
            delta_row, from_=0, to=200, number_of_steps=40,
            variable=self.delta_var,
            command=lambda v: self.delta_label.configure(
                text="off" if int(v) == 0 else str(int(v)))
        ).pack(side="left", fill="x", expand=True)

        self.lock_btn = ctk.CTkButton(
            sel_frame, text="🔓 Lock this frame",
            fg_color="#3a3322", hover_color="#4a4433",
            height=26, command=self._toggle_lock_frame, state="disabled"
        )
        self.lock_btn.pack(fill="x", padx=10, pady=(0, 6))

        # --- Scale Calibration ---
        self._section(scroll, "\U0001f4cf Scale Calibration")
        calib_frame = ctk.CTkFrame(scroll, fg_color="#1c1c2e", corner_radius=6)
        calib_frame.pack(fill="x", padx=10, pady=(0, 6))
        self.calib_status_label = ctk.CTkLabel(
            calib_frame, text="Not calibrated",
            font=("Segoe UI", 9), text_color="#888888"
        )
        self.calib_status_label.pack(anchor="w", padx=8, pady=(6, 2))
        calib_btn_row = ctk.CTkFrame(calib_frame, fg_color="transparent")
        calib_btn_row.pack(fill="x", padx=8, pady=(0, 6))
        calib_btn_row.grid_columnconfigure(0, weight=1)
        calib_btn_row.grid_columnconfigure(1, weight=1)
        self.calib_btn = ctk.CTkButton(
            calib_btn_row, text="\U0001f4cf Set 2-Point Scale",
            fg_color="#334455", hover_color="#445566",
            height=26, font=("Segoe UI", 10),
            command=self._start_calibration
        )
        self.calib_btn.grid(row=0, column=0, padx=(0, 2), sticky="ew")
        ctk.CTkButton(
            calib_btn_row, text="❌ Clear",
            fg_color="#442222", hover_color="#663333",
            height=26, font=("Segoe UI", 10),
            command=self._clear_calibration
        ).grid(row=0, column=1, padx=(2, 0), sticky="ew")

        # --- Model selection ---
        self._section(scroll, "\U0001f9b4 OpenSim Model")
        model_names = list(AVAILABLE_MODELS.keys()) if AVAILABLE_MODELS else ["(no models found)"]
        try:
            from settings import RecordingSettings as _RS
            _default_model = _RS.DEFAULT_VIDEO_ANALYSIS_MODEL
        except Exception:
            _default_model = ""
        _initial = _default_model if _default_model in model_names else model_names[0]
        self.model_var = ctk.StringVar(value=_initial)
        self.model_menu = ctk.CTkOptionMenu(scroll, variable=self.model_var, values=model_names)
        self.model_menu.pack(fill="x", padx=10, pady=(0, 4))

        # --- Output directory ---
        self._section(scroll, "\U0001f4be Output Directory")
        self.output_entry = ctk.CTkEntry(scroll, placeholder_text="Default: same folder as video")
        self.output_entry.pack(fill="x", padx=10, pady=(0, 3))
        ctk.CTkButton(scroll, text="Browse…", width=80, height=26, command=self._browse_output).pack(
            anchor="w", padx=10, pady=(0, 4)
        )

        # --- Export / Cancel ---
        self.run_btn = ctk.CTkButton(
            scroll, text="\U0001f4e4  Export Outputs",
            fg_color="#28a745", hover_color="#218838",
            height=30, command=self._run_analysis
        )
        self.run_btn.pack(fill="x", padx=10, pady=(3, 3))
        self.export_poses_btn = ctk.CTkButton(
            scroll, text="\U0001f4ca  Export All Poses CSV",
            fg_color="#1a4a6a", hover_color="#1e5a80",
            height=26, command=self._export_poses_csv
        )
        self.export_poses_btn.pack(fill="x", padx=10, pady=(0, 3))
        self.cancel_btn = ctk.CTkButton(
            scroll, text="⏹  Cancel",
            fg_color="#dc3545", hover_color="#c82333",
            height=26, state="disabled", command=self._cancel_analysis
        )
        self.cancel_btn.pack(fill="x", padx=10, pady=(0, 4))

        # --- Output files list ---
        self._section(scroll, "\U0001f4c2 Output Files")
        self.files_frame = ctk.CTkScrollableFrame(scroll, height=80, fg_color="#1a1a1a",
                                                   corner_radius=8)
        self.files_frame.pack(fill="x", padx=10, pady=(0, 4))
        self._files_empty_label = ctk.CTkLabel(
            self.files_frame, text="(no output files found)",
            text_color="#666666", font=("Segoe UI", 10))
        self._files_empty_label.pack(padx=8, pady=8)

        # ===== RIGHT PANEL =====
        right = ctk.CTkFrame(self._paned, fg_color="transparent")
        self._paned.add(right, minsize=400, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_columnconfigure(1, weight=0)
        right.grid_rowconfigure(0, weight=1)

        canvas_frame = ctk.CTkFrame(right, fg_color="#1a1a1a", corner_radius=8)
        canvas_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 0))
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(canvas_frame,
                                bg="#1a1a1a", highlightthickness=0, cursor="crosshair")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self._canvas_placeholder = self.canvas.create_text(
            _CANVAS_W // 2, _CANVAS_H // 2,
            text="No video selected", fill="#555555", font=("Segoe UI", 12)
        )
        self.canvas.bind("<ButtonPress-1>",   self._on_canvas_press)
        self.canvas.bind("<B1-Motion>",       self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<Double-Button-1>", self._on_canvas_double)
        self.canvas.bind("<Configure>",       self._on_canvas_resize)
        self.canvas.bind("<Escape>",          self._on_canvas_escape)
        self.canvas.bind("<Return>",          self._on_canvas_escape)
        self.canvas.bind("<Delete>",          self._on_canvas_escape)
        self.canvas.bind("<BackSpace>",       self._on_canvas_escape)
        self.canvas.bind("<Button-3>",        self._on_canvas_escape)
        # Zoom (scroll wheel) + pan (middle button or Ctrl+drag)
        self.canvas.bind("<MouseWheel>",            self._on_canvas_scroll)
        self.canvas.bind("<Button-4>",              self._on_canvas_scroll)   # Linux up
        self.canvas.bind("<Button-5>",              self._on_canvas_scroll)   # Linux down
        self.canvas.bind("<Button-2>",              self._on_canvas_mid_press)
        self.canvas.bind("<B2-Motion>",             self._on_canvas_mid_drag)
        self.canvas.bind("<ButtonRelease-2>",       self._on_canvas_mid_release)
        self.canvas.bind("<Control-ButtonPress-1>", self._on_canvas_mid_press)
        self.canvas.bind("<Control-B1-Motion>",     self._on_canvas_mid_drag)
        self.canvas.bind("<Control-ButtonRelease-1>", self._on_canvas_mid_release)
        self.canvas.focus_set()

        # --- Under-video controls: step buttons + timeline bar ---
        controls = ctk.CTkFrame(right, fg_color="#1a1a1a", corner_radius=8)
        controls.grid(row=1, column=0, sticky="ew", pady=(2, 2))
        controls.grid_columnconfigure(4, weight=1)

        # Row 0 — step buttons + Set In/Out + time readout
        ctk.CTkButton(
            controls, text="◀", width=28, height=24,
            fg_color="#2a2a2a", hover_color="#444444",
            font=("Segoe UI", 11, "bold"),
            command=lambda: self._step_frame(-1)
        ).grid(row=0, column=0, padx=(8, 2), pady=(8, 4))
        ctk.CTkButton(
            controls, text="▶", width=28, height=24,
            fg_color="#2a2a2a", hover_color="#444444",
            font=("Segoe UI", 11, "bold"),
            command=lambda: self._step_frame(1)
        ).grid(row=0, column=1, padx=(0, 6), pady=(8, 4))
        ctk.CTkButton(
            controls, text="[ In", width=42, height=24,
            fg_color="#1a3a22", hover_color="#2a5a33",
            text_color="#44cc44", font=("Segoe UI", 10, "bold"),
            command=self._tl_set_in_here
        ).grid(row=0, column=2, padx=(0, 2), pady=(8, 4))
        ctk.CTkButton(
            controls, text="Out ]", width=42, height=24,
            fg_color="#3a1a1a", hover_color="#5a2a2a",
            text_color="#ee4444", font=("Segoe UI", 10, "bold"),
            command=self._tl_set_out_here
        ).grid(row=0, column=3, padx=(0, 6), pady=(8, 4))
        # spacer
        ctk.CTkFrame(controls, fg_color="transparent").grid(
            row=0, column=4, sticky="ew")
        self.scrub_time_label = ctk.CTkLabel(
            controls, text="0.0 s", width=52,
            font=("Segoe UI", 10), text_color="#aaaaaa"
        )
        self.scrub_time_label.grid(row=0, column=5, padx=(0, 4), pady=(8, 4))
        self.tl_dur_label = ctk.CTkLabel(
            controls, text="", width=80,
            font=("Segoe UI", 10), text_color="#888888"
        )
        self.tl_dur_label.grid(row=0, column=6, padx=(0, 8), pady=(8, 4))

        # Row 1 — timeline canvas
        self._timeline = tk.Canvas(
            controls, height=52, bg="#111111",
            bd=0, highlightthickness=0
        )
        self._timeline.grid(row=1, column=0, columnspan=7,
                            sticky="ew", padx=8, pady=(0, 8))
        self._timeline.bind("<Configure>",       lambda e: self._tl_redraw())
        self._timeline.bind("<Button-1>",        self._tl_press)
        self._timeline.bind("<B1-Motion>",       self._tl_drag)
        self._timeline.bind("<ButtonRelease-1>", self._tl_release)

        # Hidden backing sliders — keep API compat (fire callbacks when .set() is called)
        self.scrub_slider = ctk.CTkSlider(
            controls, from_=0, to=100, number_of_steps=1000,
            command=self._on_scrub_slider
        )
        self.start_slider = ctk.CTkSlider(
            controls, from_=0, to=100, number_of_steps=1000,
            button_color="#44cc44", command=self._on_start_slider
        )
        self.end_slider = ctk.CTkSlider(
            controls, from_=0, to=100, number_of_steps=1000,
            button_color="#ee4444", command=self._on_end_slider
        )
        self.scrub_slider.set(0)
        self.start_slider.set(0)
        self.end_slider.set(100)
        # Hidden labels kept for backward compat
        self.start_time_display = ctk.CTkLabel(controls, text="0.0 s")
        self.end_time_display   = ctk.CTkLabel(controls, text="– s")

        # --- Mode hint + progress bar ---
        hint_row = ctk.CTkFrame(right, fg_color="transparent")
        hint_row.grid(row=2, column=0, sticky="ew", pady=(0, 2))
        hint_row.grid_columnconfigure(0, weight=1)
        self.mode_hint = ctk.CTkLabel(hint_row, text="", font=("Segoe UI", 10),
                                      text_color="#ffcc44")
        self.mode_hint.grid(row=0, column=0, sticky="w")
        self.progress_bar = ctk.CTkProgressBar(hint_row)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, sticky="ew")

        # ===== LANDMARK EDIT PANEL (right of canvas) =====
        lm_panel = ctk.CTkFrame(right, width=140, fg_color="#161620",
                                 corner_radius=6)
        lm_panel.grid(row=0, column=1, rowspan=3, sticky="nsew",
                      padx=(4, 0), pady=0)
        lm_panel.grid_propagate(False)
        lm_panel.grid_rowconfigure(1, weight=1)
        lm_panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(lm_panel, text="Landmarks",
                     font=("Segoe UI", 10, "bold"),
                     text_color="#aaaaaa").grid(
            row=0, column=0, pady=(6, 2), padx=6, sticky="w")

        self._lm_scroll = ctk.CTkScrollableFrame(
            lm_panel, fg_color="transparent", corner_radius=0)
        self._lm_scroll.grid(row=1, column=0, sticky="nsew", padx=2, pady=0)
        self._lm_scroll.grid_columnconfigure(0, weight=1)

        self._lm_buttons: dict = {}
        for lm_name in self._EDIT_LANDMARKS:
            disp = lm_name.replace("_", " ").title()
            btn = ctk.CTkButton(
                self._lm_scroll, text=disp,
                height=22, font=("Segoe UI", 9),
                fg_color="#2a2a2a", hover_color="#3a3a4a",
                text_color="#888888", anchor="w",
                command=lambda n=lm_name: self._set_active_landmark(n)
            )
            btn.pack(fill="x", padx=2, pady=1)
            self._lm_buttons[lm_name] = btn

        self._lm_auto_advance_var = tk.BooleanVar(value=True)
        self._lm_auto_advance_cb = ctk.CTkCheckBox(
            lm_panel, text="Auto-advance",
            variable=self._lm_auto_advance_var,
            font=("Segoe UI", 9), height=20,
            checkbox_width=14, checkbox_height=14,
        )
        self._lm_auto_advance_cb.grid(row=2, column=0, sticky="w",
                                       padx=6, pady=(2, 0))

        self._lm_clear_btn = ctk.CTkButton(
            lm_panel, text="\u274c Clear point",
            height=22, font=("Segoe UI", 9),
            fg_color="#3a2222", hover_color="#5a3333",
            command=self._clear_active_landmark
        )
        self._lm_clear_btn.grid(row=3, column=0, sticky="ew",
                                 padx=4, pady=(2, 6))

    # ------------------------------------------------------------------
    # Canvas resize
    # ------------------------------------------------------------------

    @property
    def _cw(self) -> int:
        w = self.canvas.winfo_width()
        return w if w > 1 else _CANVAS_W

    @property
    def _ch(self) -> int:
        h = self.canvas.winfo_height()
        return h if h > 1 else _CANVAS_H

    def _on_canvas_resize(self, event):
        if hasattr(self, '_resize_after_id'):
            self.after_cancel(self._resize_after_id)
        self._resize_after_id = self.after(60, self._redraw_canvas_from_cache)

    def _redraw_canvas_from_cache(self):
        cw, ch = self._cw, self._ch
        self.canvas.delete("all")
        if self._frame_img:
            thumb = self._get_display_thumb()
            if thumb:
                self._frame_photo = thumb
                self.canvas.create_image(0, 0, anchor="nw", image=self._frame_photo)
                self._draw_pose_overlay(self._current_frame_idx)
                self._redraw_rect()
                self._draw_zoom_indicator()
        else:
            self._canvas_placeholder = self.canvas.create_text(
                cw // 2, ch // 2,
                text="No video selected", fill="#555555", font=("Segoe UI", 12)
            )

    # ------------------------------------------------------------------
    # Single-player colour
    # ------------------------------------------------------------------

    _PLAYER_COLOUR = "#00cccc"

    _EDIT_LANDMARKS = [
        "head",
        "right_shoulder",  "left_shoulder",
        "right_elbow",     "left_elbow",
        "right_hand",      "left_hand",
        "right_hip",       "left_hip",
        "right_knee",      "left_knee",
        "right_ankle",     "left_ankle",
        "right_heel",      "left_heel",
        "right_foot_index","left_foot_index",
    ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _section(self, parent, title: str):
        ctk.CTkLabel(parent, text=title, font=("Segoe UI", 11, "bold")).pack(
            anchor="w", padx=10, pady=(6, 2)
        )

    def _log(self, text: str):
        print(text)

    def _set_running(self, running: bool):
        self._running = running
        self.after(0, lambda: self.run_btn.configure(state="disabled" if running else "normal"))
        self.after(0, lambda: self.cancel_btn.configure(state="normal" if running else "disabled"))
        if running:
            self.after(0, lambda: self.progress_bar.configure(mode="indeterminate"))
            self.after(0, self.progress_bar.start)
        else:
            self.after(0, self.progress_bar.stop)
            self.after(0, lambda: self.progress_bar.configure(mode="determinate"))
            self.after(0, lambda: self.progress_bar.set(1.0))

    # ------------------------------------------------------------------
    # Trim / scrub
    # ------------------------------------------------------------------

    def _update_trim_status(self):
        t0 = self.start_entry.get().strip()
        t1 = self.end_entry.get().strip()
        parts = []
        if t0:
            parts.append(f"from {t0}s")
        if t1:
            parts.append(f"to {t1}s")
        self.trim_status.configure(text=" ".join(parts) if parts else "Full video")

    def _on_scrub_slider(self, value: float):
        t = round(value, 2)
        self.scrub_time_label.configure(text=f"{t:.2f} s")
        fps = self._video_fps
        if self._video_path and fps > 0:
            self._current_frame_idx = int(t * fps)
        self._show_frame_at_time(t)
        self._tl_redraw()

    def _step_frame(self, delta: int):
        """Advance or rewind by exactly `delta` frames."""
        if not self._video_path or not self._video_path.exists():
            return
        fps   = self._video_fps or 30.0
        total = int(self._video_duration * fps) if self._video_duration > 0 else 1
        new_fi = max(0, min(total - 1, self._current_frame_idx + delta))
        t = new_fi / fps
        self._current_frame_idx = new_fi
        self.scrub_time_label.configure(text=f"{t:.2f} s")
        self._show_frame_at_time(t)
        self._tl_redraw()

    def _on_start_slider(self, value: float):
        t = round(value, 2)
        self.start_entry.delete(0, "end")
        if t > 0:
            self.start_entry.insert(0, str(t))
        self._start_time = t if t > 0 else None
        self.start_time_display.configure(text=f"{t:.2f} s")
        self._update_trim_status()
        self._tl_redraw()

    def _on_end_slider(self, value: float):
        t = round(value, 2)
        self.end_entry.delete(0, "end")
        dur = self._video_duration
        if dur <= 0 or abs(t - dur) > 0.2:
            self.end_entry.insert(0, str(t))
        self._end_time = t if (dur <= 0 or abs(t - dur) > 0.2) else None
        self.end_time_display.configure(text=f"{t:.2f} s")
        self._update_trim_status()
        self._tl_redraw()

    # ------------------------------------------------------------------
    # Timeline canvas
    # ------------------------------------------------------------------

    _TL_PAD   = 8    # horizontal padding inside canvas
    _TL_TY    = 22   # y-centre of the track bar
    _TL_TH    = 10   # half-height of track bar
    _TL_HH    = 18   # half-height of IN/OUT handles
    _TL_HTOL  = 10   # horizontal hit-tolerance for handles (px)

    def _tl_t_to_px(self, t: float) -> int:
        w   = self._timeline.winfo_width() or 400
        dur = self._video_duration if self._video_duration > 0 else 100.0
        frac = max(0.0, min(1.0, t / dur))
        return int(self._TL_PAD + frac * (w - 2 * self._TL_PAD))

    def _tl_px_to_t(self, x: int) -> float:
        w   = self._timeline.winfo_width() or 400
        dur = self._video_duration if self._video_duration > 0 else 100.0
        frac = max(0.0, min(1.0, (x - self._TL_PAD) / max(1, w - 2 * self._TL_PAD)))
        return frac * dur

    def _tl_redraw(self):
        c = self._timeline
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 20:
            return
        c.delete("all")

        dur    = self._video_duration if self._video_duration > 0 else 100.0
        t_in   = self._start_time if self._start_time is not None else 0.0
        t_out  = self._end_time   if self._end_time   is not None else dur
        t_cur  = (self._current_frame_idx / self._video_fps
                  if self._video_fps > 0 else 0.0)
        px_in  = self._tl_t_to_px(t_in)
        px_out = self._tl_t_to_px(t_out)
        px_cur = self._tl_t_to_px(t_cur)
        ty, th, hh = self._TL_TY, self._TL_TH, self._TL_HH
        pad = self._TL_PAD

        # Background track
        c.create_rectangle(pad, ty - th, w - pad, ty + th,
                           fill="#2a2a2a", outline="", tags="bg")

        # Selected region
        c.create_rectangle(px_in, ty - th, px_out, ty + th,
                           fill="#1e3d28", outline="", tags="region")

        # Frame ticks (every 5 s for long videos, every 1 s for short)
        tick_interval = 1.0 if dur <= 30 else (5.0 if dur <= 120 else 10.0)
        t_tick = 0.0
        while t_tick <= dur + 0.01:
            px = self._tl_t_to_px(t_tick)
            c.create_line(px, ty + th - 2, px, ty + th + 4,
                          fill="#444444", width=1, tags="tick")
            if t_tick > 0:
                c.create_text(px, ty + th + 12, text=f"{t_tick:.0f}",
                              fill="#555555", font=("Segoe UI", 7), tags="tick")
            t_tick += tick_interval

        # IN handle (green)
        c.create_rectangle(px_in - 2, ty - hh, px_in + 2, ty + hh,
                           fill="#44cc44", outline="", tags="in_h")
        c.create_polygon(px_in - 5, ty - hh - 1,
                         px_in + 5, ty - hh - 1,
                         px_in,     ty - hh + 7,
                         fill="#44cc44", outline="", tags="in_h")
        c.create_text(px_in, ty + hh + 3,
                      text=f"{t_in:.2f}s", fill="#44cc44",
                      font=("Segoe UI", 7), anchor="n", tags="in_h")

        # OUT handle (red)
        c.create_rectangle(px_out - 2, ty - hh, px_out + 2, ty + hh,
                           fill="#ee4444", outline="", tags="out_h")
        c.create_polygon(px_out - 5, ty - hh - 1,
                         px_out + 5, ty - hh - 1,
                         px_out,     ty - hh + 7,
                         fill="#ee4444", outline="", tags="out_h")
        c.create_text(px_out, ty + hh + 3,
                      text=f"{t_out:.2f}s", fill="#ee4444",
                      font=("Segoe UI", 7), anchor="n", tags="out_h")

        # Scrubber (white vertical line + downward arrowhead)
        c.create_line(px_cur, 2, px_cur, ty + th,
                      fill="#ffffff", width=2, tags="scrub")
        c.create_polygon(px_cur - 5, 2, px_cur + 5, 2, px_cur, 9,
                         fill="#ffdd44", outline="", tags="scrub")

        # Duration label
        sel_dur = t_out - t_in
        self.tl_dur_label.configure(
            text=f"◀ {sel_dur:.2f}s ▶" if sel_dur > 0 else "")

    def _tl_press(self, event):
        t_in  = self._start_time if self._start_time is not None else 0.0
        t_out = self._end_time   if self._end_time   is not None else self._video_duration
        t_cur = (self._current_frame_idx / self._video_fps
                 if self._video_fps > 0 else 0.0)
        px_in  = self._tl_t_to_px(t_in)
        px_out = self._tl_t_to_px(t_out)
        px_cur = self._tl_t_to_px(t_cur)
        tol = self._TL_HTOL

        # Scrub handle has highest priority so any click can scrub
        if abs(event.x - px_cur) <= tol:
            self._tl_drag_target = 'scrub'
        elif abs(event.x - px_in) <= tol:
            self._tl_drag_target = 'in'
        elif abs(event.x - px_out) <= tol:
            self._tl_drag_target = 'out'
        elif (px_in < event.x < px_out
              and (self._start_time is not None or self._end_time is not None)):
            # Region drag only when a real trim window is set; otherwise scrub
            self._tl_drag_target = 'region'
            self._tl_drag_x0    = event.x
            self._tl_drag_in0   = t_in
            self._tl_drag_out0  = t_out
        else:
            # Click anywhere → scrub to that position
            self._tl_drag_target = 'scrub'
            t = self._tl_px_to_t(event.x)
            self._on_scrub_slider(t)   # direct call — hidden sliders are unreliable

    def _tl_drag(self, event):
        dur = self._video_duration if self._video_duration > 0 else 100.0
        t   = self._tl_px_to_t(event.x)

        if self._tl_drag_target == 'in':
            t_out = self._end_time if self._end_time is not None else dur
            t = max(0.0, min(t, t_out - 0.05))
            self._on_start_slider(t)

        elif self._tl_drag_target == 'out':
            t_in = self._start_time if self._start_time is not None else 0.0
            t = max(t_in + 0.05, min(t, dur))
            self._on_end_slider(t)

        elif self._tl_drag_target == 'scrub':
            self._on_scrub_slider(t)

        elif self._tl_drag_target == 'region':
            dx   = event.x - self._tl_drag_x0
            dt   = self._tl_px_to_t(self._TL_PAD + dx) - self._tl_px_to_t(self._TL_PAD)
            new_in  = max(0.0, self._tl_drag_in0  + dt)
            new_out = min(dur, self._tl_drag_out0 + dt)
            if new_out - new_in >= 0.05:
                self._on_start_slider(new_in)
                self._on_end_slider(new_out)

    def _tl_release(self, _event):
        self._tl_drag_target = None

    def _tl_set_in_here(self):
        """Snap the IN point to the current frame."""
        fps = self._video_fps or 30.0
        t   = self._current_frame_idx / fps
        self._on_start_slider(t)

    def _tl_set_out_here(self):
        """Snap the OUT point to the current frame."""
        fps = self._video_fps or 30.0
        t   = self._current_frame_idx / fps
        self._on_end_slider(t)

    # ------------------------------------------------------------------

    def _apply_transform(self, img: Image.Image) -> Image.Image:
        """Apply current rotation and flip to a PIL image."""
        if self._video_rotation == 90:
            img = img.rotate(-90, expand=True)
        elif self._video_rotation == 180:
            img = img.rotate(180, expand=True)
        elif self._video_rotation == 270:
            img = img.rotate(90, expand=True)
        if self._video_flip_h:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        return img

    def _show_frame_at_time(self, t: float):
        if not self._video_path or not self._video_path.exists():
            return
        try:
            cap = cv2.VideoCapture(str(self._video_path))
            fps = cap.get(cv2.CAP_PROP_FPS) or 30
            frame_idx = int(t * fps)
            self._current_frame_idx = frame_idx
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            cap.release()
            if not ret:
                return
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self._frame_img = self._apply_transform(Image.fromarray(frame_rgb))
            thumb = self._get_display_thumb()
            if thumb is None:
                return
            self._frame_photo = thumb
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self._frame_photo)
            self._draw_pose_overlay(frame_idx)
            self._redraw_rect()
            self._refresh_landmark_panel()
            self._update_lock_btn_state(frame_idx)
        except Exception as e:
            logger.debug(f"Frame seek error: {e}")

    def _update_lock_btn_state(self, frame_idx: int):
        """Reflect whether current frame is locked in the lock button."""
        if not hasattr(self, 'lock_btn'):
            return
        if frame_idx in self._locked_frames:
            self.lock_btn.configure(
                text="🔒 Frame locked",
                fg_color="#665500", hover_color="#776611")
        else:
            self.lock_btn.configure(
                text="🔓 Lock this frame",
                fg_color="#3a3322", hover_color="#4a4433")

    def _sync_sliders_from_entries(self):
        dur = self._video_duration if self._video_duration > 0 else 100
        t0_str = self.start_entry.get().strip()
        t1_str = self.end_entry.get().strip()
        if t0_str:
            try:
                self.start_slider.set(min(float(t0_str), dur))
            except ValueError:
                pass
        else:
            self.start_slider.set(0)
        if t1_str:
            try:
                self.end_slider.set(min(float(t1_str), dur))
            except ValueError:
                pass
        else:
            self.end_slider.set(dur)
        self._update_trim_status()

    # ------------------------------------------------------------------
    # Canvas interaction
    # ------------------------------------------------------------------

    def _toggle_player_mode(self):
        if self._interact_mode == 'player':
            self._interact_mode = None
            self.player_btn.configure(fg_color="#555555")
            self.mode_hint.configure(text="")
        else:
            self._interact_mode = 'player'
            self._drag_start = None
            self.player_btn.configure(fg_color="#cc6600")
            self.mode_hint.configure(text="Draw a box to add a new player")

    # ------------------------------------------------------------------
    # Manual landmark editing
    # ------------------------------------------------------------------

    def _toggle_manual_edit(self):
        if self._interact_mode == 'landmark':
            # Exit manual edit
            self._interact_mode = None
            self._active_landmark = None
            self.manual_edit_btn.configure(
                fg_color="#3a3355", text="\u270f Manual Edit")
            self.mode_hint.configure(text="")
            self.canvas.config(cursor="")
            self._refresh_landmark_panel()
        else:
            self._interact_mode = 'landmark'
            self.manual_edit_btn.configure(
                fg_color="#6644aa", text="\u270f Editing — click to exit")
            self.mode_hint.configure(
                text="Manual edit: select a landmark, then click on video",
                text_color="#ffcc44")
            self.canvas.config(cursor="crosshair")
            self._refresh_landmark_panel()
            # Auto-select first unset landmark for current frame
            poses_fi = self._frame_poses.get(self._current_frame_idx, {})
            for lm_name in self._EDIT_LANDMARKS:
                if lm_name not in poses_fi:
                    self._set_active_landmark(lm_name)
                    break
            else:
                self._set_active_landmark(self._EDIT_LANDMARKS[0])

    def _set_active_landmark(self, name: str):
        self._active_landmark = name
        self._refresh_landmark_panel()

    def _clear_active_landmark(self):
        if not self._active_landmark:
            return
        fi = self._current_frame_idx
        if fi in self._frame_poses:
            self._frame_poses[fi].pop(self._active_landmark, None)
            if not self._frame_poses[fi]:
                del self._frame_poses[fi]
        self._redraw_rect()
        self._refresh_landmark_panel()

    def _refresh_landmark_panel(self):
        """Update landmark button colours to reflect current frame's pose data."""
        if not hasattr(self, '_lm_buttons'):
            return
        fi = self._current_frame_idx
        poses_fi = self._frame_poses.get(fi, {})
        in_edit = (self._interact_mode == 'landmark')
        for lm_name, btn in self._lm_buttons.items():
            is_active = (lm_name == self._active_landmark and in_edit)
            is_set    = lm_name in poses_fi
            if is_active:
                btn.configure(fg_color="#6644aa", text_color="#ffffff")
            elif is_set:
                btn.configure(fg_color="#224422", text_color="#66cc66")
            else:
                btn.configure(fg_color="#2a2a2a",
                              text_color="#888888" if in_edit else "#555555")

    def _clear_selection(self):
        """Clear the player box and pose for the current frame only."""
        fi = self._current_frame_idx
        self._frame_rects.pop(fi, None)
        self._frame_poses.pop(fi, None)
        self._user_anchors.discard(fi)
        self._locked_frames.discard(fi)

        # If no rects remain at all, also wipe the fallback rect and reset UI
        if not self._frame_rects:
            self._player_rect = None
            self._drag_start = None
            self._move_rect_canvas = None
            self._interact_mode = None
            self._custom_connections.clear()
            self.player_btn.configure(fg_color="#555555")
            self.canvas.delete("player_rect")
            self.canvas.delete("player_label")

        self.mode_hint.configure(text="")
        self.canvas.delete("pose_overlay")
        self.canvas.config(cursor="")
        self._redraw_rect()
        self._update_sel_status()
        self._update_lock_btn_state(fi)

    def _get_view(self) -> Tuple[float, float, float, float]:
        """Return viewport (x0, y0, x1, y1) in transformed-video pixel coords."""
        if self._frame_img is None:
            return (0.0, 0.0, float(_CANVAS_W), float(_CANVAS_H))
        vw, vh = self._frame_img.size
        if self._view is None:
            return (0.0, 0.0, float(vw), float(vh))
        return self._view

    def _get_display_thumb(self) -> Optional[ImageTk.PhotoImage]:
        """Crop frame to current viewport and resize to canvas dims."""
        if self._frame_img is None:
            return None
        cw, ch = self._cw, self._ch
        x0, y0, x1, y1 = self._get_view()
        vw, vh = self._frame_img.size
        ix0 = max(0, int(x0)); iy0 = max(0, int(y0))
        ix1 = min(vw, int(x1)); iy1 = min(vh, int(y1))
        if ix1 <= ix0 or iy1 <= iy0 or cw < 1 or ch < 1:
            return None
        cropped = self._frame_img.crop((ix0, iy0, ix1, iy1))
        return ImageTk.PhotoImage(cropped.resize((cw, ch), Image.LANCZOS))

    def _canvas_to_video(self, cx: int, cy: int):
        x0, y0, x1, y1 = self._get_view()
        vw_v = x1 - x0; vh_v = y1 - y0
        cw, ch = self._cw, self._ch
        if vw_v <= 0 or vh_v <= 0 or cw <= 0 or ch <= 0:
            return int(cx), int(cy)
        return int(x0 + cx * vw_v / cw), int(y0 + cy * vh_v / ch)

    def _video_to_canvas(self, vx: int, vy: int):
        x0, y0, x1, y1 = self._get_view()
        vw_v = x1 - x0; vh_v = y1 - y0
        cw, ch = self._cw, self._ch
        if vw_v <= 0 or vh_v <= 0:
            return int(vx), int(vy)
        return int((vx - x0) * cw / vw_v), int((vy - y0) * ch / vh_v)

    def _rect_canvas_coords(self):
        rect = self._frame_rects.get(self._current_frame_idx, self._player_rect)
        if rect is None:
            return None
        vx0, vy0, vx1, vy1 = rect
        cx0, cy0 = self._video_to_canvas(vx0, vy0)
        cx1, cy1 = self._video_to_canvas(vx1, vy1)
        return cx0, cy0, cx1, cy1

    def _on_canvas_press(self, event):
        ex, ey = event.x, event.y

        # --- Calibration mode: collect 2 points then prompt for distance ---
        if self._interact_mode == 'calibrate':
            vx, vy = self._canvas_to_video(ex, ey)
            self._calib_points.append((vx, vy))
            # Draw a marker
            r = 6
            self.canvas.create_oval(ex - r, ey - r, ex + r, ey + r,
                                    fill="#ffdd00", outline="#ffffff", width=1,
                                    tags="calib_mark")
            if len(self._calib_points) == 2:
                self._finish_calibration()
            else:
                self.calib_status_label.configure(
                    text="Click 2nd point…", text_color="#ffcc44")
            return

        if self._interact_mode == 'landmark':
            if self._active_landmark:
                vx, vy = self._canvas_to_video(ex, ey)
                fi = self._current_frame_idx
                if fi not in self._frame_poses:
                    self._frame_poses[fi] = {}
                self._frame_poses[fi][self._active_landmark] = (float(vx), float(vy))
                self._redraw_rect()
                self._refresh_landmark_panel()
                # Auto-advance to next unset landmark (when checkbox is on)
                if getattr(self, '_lm_auto_advance_var', None) and \
                        self._lm_auto_advance_var.get():
                    poses_fi = self._frame_poses.get(fi, {})
                    cur_idx = self._EDIT_LANDMARKS.index(self._active_landmark)
                    for offset in range(1, len(self._EDIT_LANDMARKS) + 1):
                        nxt = self._EDIT_LANDMARKS[(cur_idx + offset) % len(self._EDIT_LANDMARKS)]
                        if nxt not in poses_fi:
                            self._set_active_landmark(nxt)
                            break
            return

        if self._interact_mode == 'player':
            self._drag_start = (ex, ey)
            self.canvas.delete("player_rect")
            self.canvas.delete("player_label")
            return

        # ---- Check current selection FIRST (corners, landmarks, body) ----
        # This must come before the detected-player box check so that clicking
        # on a corner handle of the selected box is never hijacked by a
        # detected-player box that happens to overlap the same screen position.
        rc = self._rect_canvas_coords()
        if rc:
            cx0, cy0, cx1, cy1 = rc

            # 1. Pose landmarks
            lm = self._frame_poses.get(self._current_frame_idx, {})
            for name, pt in lm.items():
                pcx, pcy = self._video_to_canvas(int(pt[0]), int(pt[1]))
                if abs(ex - pcx) <= 15 and abs(ey - pcy) <= 15:
                    self._interact_mode = 'drag_point'
                    self._drag_point_name = name
                    self.canvas.config(cursor="crosshair")
                    return

            # 2. Corner resize handles
            corners = {'tl': (cx0, cy0), 'tr': (cx1, cy0),
                       'bl': (cx0, cy1), 'br': (cx1, cy1)}
            for cname, (ccx, ccy) in corners.items():
                if abs(ex - ccx) <= 16 and abs(ey - ccy) <= 16:
                    self._interact_mode = 'resize_rect'
                    self._resize_corner = cname
                    self._drag_start = (ex, ey)
                    self._move_rect_canvas = (cx0, cy0, cx1, cy1)
                    self.canvas.config(cursor="sizing")
                    return

            # 3. Body move (inside box with a small pad)
            pad = 8
            if cx0 - pad <= ex <= cx1 + pad and cy0 - pad <= ey <= cy1 + pad:
                self._interact_mode = 'move_rect'
                self._drag_start = (ex, ey)
                self._move_rect_canvas = (cx0, cy0, cx1, cy1)
                self.canvas.config(cursor="fleur")
                return


    def _on_canvas_drag(self, event):
        if self._interact_mode == 'player' and self._drag_start:
            x0, y0 = self._drag_start
            self.canvas.delete("player_rect")
            self.canvas.create_rectangle(
                x0, y0, event.x, event.y,
                outline="#ff6600", width=2, dash=(4, 2), tags="player_rect"
            )
        elif self._interact_mode == 'drag_point' and self._drag_point_name:
            fi = self._current_frame_idx
            if fi in self._frame_poses:
                vx, vy = self._canvas_to_video(event.x, event.y)
                self._frame_poses[fi][self._drag_point_name] = (float(vx), float(vy))
                self._redraw_rect()
        elif self._interact_mode == 'resize_rect' and self._drag_start and self._move_rect_canvas:
            ox0, oy0, ox1, oy1 = self._move_rect_canvas
            ex, ey = event.x, event.y
            corner = self._resize_corner
            if corner == 'tl':   nx0, ny0, nx1, ny1 = ex, ey, ox1, oy1
            elif corner == 'tr': nx0, ny0, nx1, ny1 = ox0, ey, ex, oy1
            elif corner == 'bl': nx0, ny0, nx1, ny1 = ex, oy0, ox1, ey
            else:                nx0, ny0, nx1, ny1 = ox0, oy0, ex, ey
            self.canvas.delete("player_rect")
            self.canvas.delete("player_label")
            self.canvas.create_rectangle(
                min(nx0, nx1), min(ny0, ny1), max(nx0, nx1), max(ny0, ny1),
                outline="#00cccc", width=2, dash=(4, 2), tags="player_rect"
            )
        elif self._interact_mode == 'move_rect' and self._drag_start and self._move_rect_canvas:
            dx = event.x - self._drag_start[0]
            dy = event.y - self._drag_start[1]
            cx0, cy0, cx1, cy1 = self._move_rect_canvas
            self.canvas.delete("player_rect")
            self.canvas.delete("player_label")
            self.canvas.create_rectangle(
                cx0 + dx, cy0 + dy, cx1 + dx, cy1 + dy,
                outline="#00cccc", width=2, dash=(4, 2), tags="player_rect"
            )

    def _on_canvas_release(self, event):
        if self._interact_mode == 'player' and self._drag_start:
            x0, y0 = self._drag_start
            x1, y1 = event.x, event.y
            cx0, cy0 = min(x0, x1), min(y0, y1)
            cx1, cy1 = max(x0, x1), max(y0, y1)
            if cx1 - cx0 < 5 or cy1 - cy0 < 5:
                self._drag_start = None
                return
            vx0, vy0 = self._canvas_to_video(cx0, cy0)
            vx1, vy1 = self._canvas_to_video(cx1, cy1)
            new_rect = (vx0, vy0, vx1, vy1)
            self._player_rect = new_rect
            self._frame_rects[self._current_frame_idx] = new_rect
            self._user_anchors.add(self._current_frame_idx)
            self._finalize_rect_draw()
            self._finalize_rect_draw()
        elif self._interact_mode == 'drag_point' and self._drag_point_name:
            fi = self._current_frame_idx
            if fi in self._frame_poses:
                vx, vy = self._canvas_to_video(event.x, event.y)
                self._frame_poses[fi][self._drag_point_name] = (float(vx), float(vy))
            self._drag_point_name = None
            self._interact_mode = None
            self.canvas.config(cursor="crosshair")
            self._redraw_rect()
        elif self._interact_mode == 'resize_rect' and self._drag_start and self._move_rect_canvas:
            ox0, oy0, ox1, oy1 = self._move_rect_canvas
            ex, ey = event.x, event.y
            corner = self._resize_corner
            if corner == 'tl':   nx0, ny0, nx1, ny1 = ex, ey, ox1, oy1
            elif corner == 'tr': nx0, ny0, nx1, ny1 = ox0, ey, ex, oy1
            elif corner == 'bl': nx0, ny0, nx1, ny1 = ex, oy0, ox1, ey
            else:                nx0, ny0, nx1, ny1 = ox0, oy0, ex, ey
            vx0, vy0 = self._canvas_to_video(min(nx0, nx1), min(ny0, ny1))
            vx1, vy1 = self._canvas_to_video(max(nx0, nx1), max(ny0, ny1))
            if vx1 - vx0 > 5 and vy1 - vy0 > 5:
                new_rect = (vx0, vy0, vx1, vy1)
                self._frame_rects[self._current_frame_idx] = new_rect
                self._user_anchors.add(self._current_frame_idx)
                if self._player_rect is None:
                    self._player_rect = new_rect
            self.canvas.config(cursor="")
            self._interact_mode = None
            self._resize_corner = None
            self._drag_start = None
            self._move_rect_canvas = None
            self._redraw_rect()
            self._update_sel_status()
        elif self._interact_mode == 'move_rect' and self._drag_start and self._move_rect_canvas:
            dx = event.x - self._drag_start[0]
            dy = event.y - self._drag_start[1]
            cx0, cy0, cx1, cy1 = self._move_rect_canvas
            vx0, vy0 = self._canvas_to_video(cx0 + dx, cy0 + dy)
            vx1, vy1 = self._canvas_to_video(cx1 + dx, cy1 + dy)
            new_rect = (vx0, vy0, vx1, vy1)
            self._frame_rects[self._current_frame_idx] = new_rect
            self._user_anchors.add(self._current_frame_idx)
            if self._player_rect is None:
                self._player_rect = new_rect
            self.canvas.config(cursor="")
            self._interact_mode = None
            self._drag_start = None
            self._move_rect_canvas = None
            self._redraw_rect()
            self._update_sel_status()

    def _on_canvas_escape(self, event=None):
        """Cancel any active interaction without deselecting the player."""
        if self._interact_mode in ('resize_rect', 'move_rect', 'drag_point', 'player'):
            self._interact_mode = None
            self._drag_start = None
            self._move_rect_canvas = None
            self._resize_corner = None
            self._drag_point_name = None
            self.player_btn.configure(fg_color="#555555")
            self.mode_hint.configure(text="")
            self.canvas.config(cursor="crosshair")
            self._redraw_rect()

    def _on_canvas_double(self, event):
        """Cancel any active interaction on double-click."""
        if self._interact_mode is not None:
            self._on_canvas_escape()

    # ------------------------------------------------------------------
    # Zoom / pan
    # ------------------------------------------------------------------

    def _on_canvas_scroll(self, event):
        """Zoom in/out centered on the mouse position."""
        if self._frame_img is None:
            return
        # Normalise delta across platforms
        if event.num == 4 or (hasattr(event, 'delta') and event.delta > 0):
            factor = 0.8   # zoom in — viewport shrinks
        else:
            factor = 1.25  # zoom out — viewport grows

        x0, y0, x1, y1 = self._get_view()
        vw_v, vh_v = x1 - x0, y1 - y0
        vw_img, vh_img = float(self._frame_img.size[0]), float(self._frame_img.size[1])
        cw, ch = self._cw, self._ch

        # Video coord under mouse
        vx = x0 + event.x * vw_v / cw
        vy = y0 + event.y * vh_v / ch

        new_vw = max(80.0, min(vw_img, vw_v * factor))
        new_vh = max(80.0, min(vh_img, vh_v * factor))

        # Preserve aspect ratio of current view
        ar = vw_v / vh_v if vh_v > 0 else 1.0
        if new_vw / new_vh > ar:
            new_vw = new_vh * ar
        else:
            new_vh = new_vw / ar

        # Keep the point under the mouse fixed
        nx0 = vx - event.x * new_vw / cw
        ny0 = vy - event.y * new_vh / ch
        nx1, ny1 = nx0 + new_vw, ny0 + new_vh

        # Clamp to image bounds
        if nx0 < 0:        nx0, nx1 = 0.0, new_vw
        elif nx1 > vw_img: nx1, nx0 = vw_img, vw_img - new_vw
        if ny0 < 0:        ny0, ny1 = 0.0, new_vh
        elif ny1 > vh_img: ny1, ny0 = vh_img, vh_img - new_vh

        if new_vw >= vw_img and new_vh >= vh_img:
            self._view = None
        else:
            self._view = (nx0, ny0, nx1, ny1)

        self._redraw_canvas_from_cache()
        self._update_zoom_label()

    def _on_canvas_mid_press(self, event):
        """Start panning (middle button or Ctrl+left drag)."""
        if self._frame_img is None:
            return
        self._pan_start = (event.x, event.y)
        self._pan_view0 = self._get_view()
        self.canvas.config(cursor="fleur")

    def _on_canvas_mid_drag(self, event):
        """Pan the view."""
        if not self._pan_start or not self._pan_view0:
            return
        x0, y0, x1, y1 = self._pan_view0
        vw_v, vh_v = x1 - x0, y1 - y0
        cw, ch = self._cw, self._ch
        dvx = -(event.x - self._pan_start[0]) * vw_v / cw
        dvy = -(event.y - self._pan_start[1]) * vh_v / ch
        vw_img = float(self._frame_img.size[0]) if self._frame_img else float(_CANVAS_W)
        vh_img = float(self._frame_img.size[1]) if self._frame_img else float(_CANVAS_H)
        nx0 = max(0.0, min(vw_img - vw_v, x0 + dvx))
        ny0 = max(0.0, min(vh_img - vh_v, y0 + dvy))
        self._view = (nx0, ny0, nx0 + vw_v, ny0 + vh_v)
        self._redraw_canvas_from_cache()

    def _on_canvas_mid_release(self, event):
        """End pan."""
        self._pan_start = None
        self._pan_view0 = None
        self.canvas.config(cursor="crosshair" if self._interact_mode != 'landmark' else "crosshair")

    def _reset_zoom(self):
        """Reset to fit-full-frame view."""
        self._view = None
        self._redraw_canvas_from_cache()
        self._update_zoom_label()

    def _crop_to_aspect_ratio(self, ar_w: float, ar_h: float):
        """Center-crop the viewport to the given aspect ratio (e.g. 16:9, 9:16, 1:1)."""
        if self._frame_img is None:
            return
        vw, vh = float(self._frame_img.size[0]), float(self._frame_img.size[1])
        target = ar_w / ar_h
        video  = vw / vh
        if abs(target - video) < 0.01:
            self._view = None  # already matches — show full frame
        elif target > video:
            # Wider target → full width, crop height symmetrically
            new_vh = vw / target
            y0 = (vh - new_vh) / 2
            self._view = (0.0, y0, vw, y0 + new_vh)
        else:
            # Narrower target → full height, crop width symmetrically
            new_vw = vh * target
            x0 = (vw - new_vw) / 2
            self._view = (x0, 0.0, x0 + new_vw, vh)
        self._redraw_canvas_from_cache()
        self._update_zoom_label()

    def _update_zoom_label(self):
        if not hasattr(self, 'zoom_label'):
            return
        if self._frame_img is None or self._view is None:
            self.zoom_label.configure(text="100%")
            return
        vw_img = self._frame_img.size[0]
        x0, _y0, x1, _y1 = self._view
        pct = int(vw_img / max(1.0, x1 - x0) * 100)
        self.zoom_label.configure(text=f"{pct}%")

    def _draw_zoom_indicator(self):
        """Draw a subtle zoom-level badge in the bottom-right corner of the canvas."""
        if self._view is None:
            return
        vw_img = self._frame_img.size[0] if self._frame_img else 1
        x0, _y0, x1, _y1 = self._view
        pct = int(vw_img / max(1.0, x1 - x0) * 100)
        if pct == 100:
            return
        cw, ch = self._cw, self._ch
        txt = f"{pct}%"
        self.canvas.create_rectangle(cw - 46, ch - 20, cw - 2, ch - 2,
                                     fill="#00000088", outline="", tags="zoom_badge")
        self.canvas.create_text(cw - 24, ch - 11, text=txt,
                                fill="#ffffffcc", font=("Segoe UI", 8, "bold"),
                                tags="zoom_badge")

    # ------------------------------------------------------------------
    # Video transform (rotation / flip)
    # ------------------------------------------------------------------

    def _rotate_video(self, delta_cw: int):
        """Rotate display CW by delta_cw degrees (±90)."""
        self._video_rotation = (self._video_rotation + delta_cw) % 360
        self._view = None   # reset zoom — dimensions may change
        self._clear_transform_dependent_state()
        self._reload_current_frame()

    def _flip_video_h(self):
        """Toggle horizontal flip."""
        self._video_flip_h = not self._video_flip_h
        self._clear_transform_dependent_state()
        self._reload_current_frame()

    def _clear_transform_dependent_state(self):
        """Clear landmarks / rects whose coords were in the old orientation."""
        if self._frame_poses or self._frame_rects:
            self._frame_poses.clear()
            self._frame_rects.clear()
            self._player_rect = None
            self._user_anchors.clear()
            self._locked_frames.clear()

    def _reload_current_frame(self):
        """Re-read and display the current frame with the new transform applied."""
        if self._video_path and self._video_path.exists():
            fps = self._video_fps or 30.0
            t = self._current_frame_idx / fps
            self._show_frame_at_time(t)
            self._update_zoom_label()

    def _finalize_rect_draw(self):
        self._drag_start = None
        self._interact_mode = None
        self.player_btn.configure(fg_color="#555555")
        self.mode_hint.configure(text="")
        self._redraw_rect()
        self._update_sel_status()

    def _resize_roi(self, dx0: int, dy0: int, dx1: int, dy1: int):
        """Expand/shrink the current ROI by adjusting each edge by the given delta."""
        rect = self._frame_rects.get(self._current_frame_idx, self._player_rect)
        if rect is None:
            return
        vx0, vy0, vx1, vy1 = rect
        if self._frame_img:
            vw, vh = self._frame_img.size
        else:
            vw, vh = 9999, 9999
        # dx0/dy0 shift the left/top edge; dx1/dy1 shift the right/bottom edge
        # Convert pixel deltas on canvas to video-pixel space
        scale_x = vw / self._cw if self._cw > 0 else 1
        scale_y = vh / self._ch if self._ch > 0 else 1
        new_vx0 = max(0,  vx0 + int(dx0 * scale_x))
        new_vy0 = max(0,  vy0 + int(dy0 * scale_y))
        new_vx1 = min(vw, vx1 + int(dx1 * scale_x))
        new_vy1 = min(vh, vy1 + int(dy1 * scale_y))
        if new_vx1 - new_vx0 < 10 or new_vy1 - new_vy0 < 10:
            return
        new_rect = (new_vx0, new_vy0, new_vx1, new_vy1)
        self._player_rect = new_rect
        self._frame_rects[self._current_frame_idx] = new_rect
        self._user_anchors.add(self._current_frame_idx)
        self._redraw_rect()
        self._update_sel_status()

    _HANDLE_R = 7

    def _redraw_rect(self):
        self.canvas.delete("player_rect")
        self.canvas.delete("player_label")
        self.canvas.delete("pose_overlay")
        self._draw_pose_overlay(self._current_frame_idx)
        rc = self._rect_canvas_coords()
        if rc is None:
            return
        cx0, cy0, cx1, cy1 = rc
        colour = "#00cccc" if self._current_frame_idx in self._frame_rects else "#ff6600"
        label  = self._get_player_label()
        self.canvas.create_rectangle(cx0, cy0, cx1, cy1,
                                     outline=colour, width=2, tags="player_rect")
        self.canvas.create_text(cx0 + 4, cy0 + 2, text=label,
                                fill=colour, font=("Segoe UI", 10, "bold"),
                                anchor="nw", tags="player_rect")
        r = self._HANDLE_R
        for hx, hy in ((cx0, cy0), (cx1, cy0), (cx0, cy1), (cx1, cy1)):
            self.canvas.create_rectangle(hx - r, hy - r, hx + r, hy + r,
                                         fill=colour, outline="#ffffff",
                                         width=1, tags="player_rect")

    def _update_sel_status(self):
        n_user = len(self._user_anchors)
        n_auto = len(self._frame_rects) - n_user
        if self._player_rect:
            parts = []
            if n_user:
                parts.append(f"{n_user} manual anchor{'s' if n_user!=1 else ''}")
            if n_auto > 0:
                parts.append(f"{n_auto} auto-tracked")
            _parts_str = ", ".join(parts)
            note = f"  ({_parts_str})" if parts else ""
            self.sel_status_label.configure(
                text=f"\u2705 Player selected{note} — drag to reposition",
                text_color="#44cc44")
            self.track_btn.configure(state="normal")
            self.preview_btn.configure(state="normal")
            self.lock_btn.configure(state="normal")
        else:
            self.sel_status_label.configure(
                text="\u26a0 No player selected — draw a box first",
                text_color="#ffaa44")
            self.track_btn.configure(state="disabled")
            self.preview_btn.configure(state="disabled")
            self.lock_btn.configure(state="disabled")

    def _auto_track(self, from_frame: Optional[int] = None):
        if not self._player_rect and not self._frame_rects:
            messagebox.showwarning("No ROI", "Draw a box around the player first.")
            return
        if not self._video_path or not self._video_path.exists():
            return
        if self._tracking or self._running:
            return
        self._tracking = True
        ff = from_frame if from_frame is not None else self._current_frame_idx
        label = f"Tracking from frame {ff}…" if from_frame is not None else "Starting…"
        self.track_btn.configure(state="disabled", text="Tracking…")
        self.track_progress_label.configure(text=label)
        threading.Thread(target=self._run_tracking, args=(ff,), daemon=True).start()

    def _run_tracking(self, from_frame: int = 0):
        try:
            cap = cv2.VideoCapture(str(self._video_path))
            fps   = cap.get(cv2.CAP_PROP_FPS) or 30
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            try:
                end_t = float(self.end_entry.get().strip() or 0)
            except ValueError:
                end_t = 0.0
            start_frame = from_frame
            end_frame   = min(int(end_t * fps) if end_t else total - 1, total - 1)

            # Seed the start frame: use existing rect at from_frame, then user anchors forward
            if start_frame not in self._frame_rects:
                # Find the nearest known rect at or before start_frame
                best_fi = max(
                    (fi for fi in self._frame_rects if fi <= start_frame),
                    default=None
                )
                seed_rect = self._frame_rects.get(best_fi, self._player_rect)
                if seed_rect:
                    self._frame_rects[start_frame] = seed_rect
                    self._user_anchors.add(start_frame)
            user_in_range = sorted(
                fi for fi in self._user_anchors
                if start_frame <= fi <= end_frame
            )
            if not user_in_range:
                self._frame_rects[start_frame] = self._player_rect
                self._user_anchors.add(start_frame)
                user_in_range = [start_frame]

            class _TemplateTracker:
                def __init__(self):
                    self._tmpl = None
                    self._bbox = None

                def init(self, frame, bbox):
                    x, y, w, h = (int(v) for v in bbox)
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    self._tmpl = gray[y:y + h, x:x + w].copy()
                    self._bbox = (x, y, w, h)

                def update(self, frame):
                    if self._tmpl is None or self._tmpl.size == 0:
                        return False, self._bbox
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    x0, y0, tw, th = self._bbox
                    pad_x, pad_y = tw, th
                    sx = max(0, x0 - pad_x)
                    sy = max(0, y0 - pad_y)
                    ex = min(gray.shape[1], x0 + tw + pad_x)
                    ey = min(gray.shape[0], y0 + th + pad_y)
                    roi = gray[sy:ey, sx:ex]
                    if roi.shape[0] < th or roi.shape[1] < tw:
                        return True, self._bbox
                    res = cv2.matchTemplate(roi, self._tmpl, cv2.TM_CCOEFF_NORMED)
                    _, _, _, max_loc = cv2.minMaxLoc(res)
                    nx = sx + max_loc[0]
                    ny = sy + max_loc[1]
                    self._bbox = (nx, ny, tw, th)
                    return True, (nx, ny, tw, th)

            def _make_tracker():
                for factory in (
                    lambda: cv2.TrackerCSRT_create(),
                    lambda: cv2.legacy.TrackerCSRT_create(),
                    lambda: cv2.legacy.TrackerKCF_create(),
                ):
                    try:
                        t = factory()
                        _ = t.init
                        return t
                    except (AttributeError, cv2.error):
                        pass
                return _TemplateTracker()

            # Only clear auto-tracked rects >= from_frame; keep older frames intact
            for fi in list(self._frame_rects.keys()):
                if fi not in self._user_anchors and fi >= start_frame:
                    del self._frame_rects[fi]

            anchor_queue = list(user_in_range)
            first_fi     = anchor_queue.pop(0)
            next_anchor  = anchor_queue.pop(0) if anchor_queue else None

            def _read_transformed(cap):
                ret, frame = cap.read()
                if not ret:
                    return False, None
                if self._video_rotation or self._video_flip_h:
                    import numpy as _np
                    _pil = self._apply_transform(
                        Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
                    frame = cv2.cvtColor(_np.array(_pil), cv2.COLOR_RGB2BGR)
                return True, frame

            cap.set(cv2.CAP_PROP_POS_FRAMES, first_fi)
            ret, frame = _read_transformed(cap)
            if not ret:
                cap.release()
                return

            x1, y1, x2, y2 = self._frame_rects[first_fi]
            _roi_w, _roi_h = x2 - x1, y2 - y1   # fixed size — never let tracker shrink it
            tracker = _make_tracker()
            tracker.init(frame, (x1, y1, _roi_w, _roi_h))
            n_frames = max(end_frame - first_fi, 1)

            for frame_idx in range(first_fi + 1, end_frame + 1):
                if next_anchor is not None and frame_idx == next_anchor:
                    rx1, ry1, rx2, ry2 = self._frame_rects[next_anchor]
                    _roi_w, _roi_h = rx2 - rx1, ry2 - ry1  # update size from new anchor
                    tracker = _make_tracker()
                    cap.set(cv2.CAP_PROP_POS_FRAMES, next_anchor)
                    ret, frame = _read_transformed(cap)
                    if ret:
                        tracker.init(frame, (rx1, ry1, _roi_w, _roi_h))
                    next_anchor = anchor_queue.pop(0) if anchor_queue else None
                    continue

                # Don't overwrite manually locked frames
                if frame_idx in self._locked_frames:
                    cap.read()  # advance capture position
                    continue

                ret, frame = _read_transformed(cap)
                if not ret:
                    break
                ok, bbox = tracker.update(frame)
                if ok:
                    bx, by = int(bbox[0]), int(bbox[1])
                    # Use fixed dimensions — only the position is tracked
                    self._frame_rects[frame_idx] = (bx, by, bx + _roi_w, by + _roi_h)

                if (frame_idx - first_fi) % 15 == 0:
                    pct = int((frame_idx - first_fi) / n_frames * 100)
                    self.after(0, lambda p=pct, f=frame_idx:
                               self.track_progress_label.configure(
                                   text=f"Tracking… frame {f}  ({p}%)"))

            cap.release()
            n_tracked = len(self._frame_rects) - len(self._user_anchors)
            self.after(0, lambda n=n_tracked, sf=start_frame: self._on_tracking_done(n, sf))

        except Exception as e:
            self.after(0, lambda err=str(e):
                       self.track_progress_label.configure(
                           text=f"Error: {err}", text_color="#ff4444"))
            self.after(0, lambda: self.track_btn.configure(
                state="normal", text="\U0001f504 Auto-Track"))
            self._tracking = False

    def _on_tracking_done(self, n_tracked: int, start_frame: int = 0):
        self._tracking = False
        self.track_btn.configure(state="normal", text="\U0001f504 Auto-Track")
        self.track_progress_label.configure(
            text=f"\u2705 {n_tracked} frames auto-tracked — detecting poses…",
            text_color="#44cc44")
        self._update_sel_status()
        self._redraw_rect()
        # Estimate poses for all frames in the trim range (using player_rect
        # as fallback for any frames before the tracking start point)
        self._preview_pose(from_frame=None)

    # ------------------------------------------------------------------
    # Pose preview
    # ------------------------------------------------------------------

    _PREVIEW_CONNECTIONS = [
        ("head",           "left_shoulder"),  ("head",          "right_shoulder"),
        ("left_shoulder",  "right_shoulder"),
        ("left_shoulder",  "left_elbow"),    ("left_elbow",    "left_hand"),
        ("right_shoulder", "right_elbow"),   ("right_elbow",   "right_hand"),
        ("left_shoulder",  "left_hip"),      ("right_shoulder","right_hip"),
        ("left_hip",       "right_hip"),
        ("left_hip",       "left_knee"),     ("left_knee",     "left_ankle"),
        ("right_hip",      "right_knee"),    ("right_knee",    "right_ankle"),
        ("left_ankle",     "left_heel"),     ("left_ankle",    "left_foot_index"),
        ("right_ankle",    "right_heel"),    ("right_ankle",   "right_foot_index"),
    ]

    def _preview_pose(self, from_frame=None, single_frame=False):
        if not self._video_path or not self._video_path.exists():
            return
        if self._previewing or self._tracking or self._running:
            return
        self._previewing = True
        self.preview_btn.configure(state="disabled", text="Detecting\u2026")
        label = "Estimating from here\u2026" if from_frame is not None else "Running pose estimation\u2026"
        self.track_progress_label.configure(text=label, text_color="#aaaaaa")
        threading.Thread(target=self._run_pose_preview,
                         kwargs=dict(from_frame=from_frame, single_frame=single_frame),
                         daemon=True).start()

    def _toggle_lock_frame(self):
        fi = self._current_frame_idx
        if fi in self._locked_frames:
            self._locked_frames.discard(fi)
            self.lock_btn.configure(
                text="🔓 Lock this frame",
                fg_color="#3a3322", hover_color="#4a4433")
        else:
            self._locked_frames.add(fi)
            self.lock_btn.configure(
                text="🔒 Frame locked",
                fg_color="#665500", hover_color="#776611")
        self._redraw_rect()

    def _run_pose_preview(self, from_frame: Optional[int] = None, single_frame: bool = False):
        try:
            import mediapipe as mp
            from pathlib import Path as _Path
            model_path = _Path(__file__).parent.parent / "record" / "pose_landmarker_full.task"
            if not model_path.exists():
                model_path = _Path(__file__).parent.parent / "record" / "pose_landmarker_lite.task"
            if not model_path.exists():
                model_path = _Path(__file__).parent.parent / "record" / "pose_landmarker_full.task"
                _URL = (
                    "https://storage.googleapis.com/mediapipe-models/"
                    "pose_landmarker/pose_landmarker_full/float16/latest/"
                    "pose_landmarker_full.task"
                )
                def _prog3(dl, tot):
                    pct = int(dl / tot * 100)
                    mb = dl / 1_048_576
                    self.after(0, lambda p=pct, m=mb: self.track_progress_label.configure(
                        text=f"Downloading model… {p}% ({m:.1f} MB)", text_color="#ffcc44"))
                self.after(0, lambda: self.track_progress_label.configure(
                    text="Downloading pose model (~30 MB)…", text_color="#ffcc44"))
                _download_file(_URL, model_path, progress_cb=_prog3)
                self.after(0, lambda: self.track_progress_label.configure(
                    text="Model downloaded \u2705", text_color="#44cc44"))

            BaseOptions = mp.tasks.BaseOptions
            PoseLandmarker = mp.tasks.vision.PoseLandmarker
            PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
            VisionRunningMode = mp.tasks.vision.RunningMode

            _pose_kwargs = dict(
                base_options=BaseOptions(model_asset_path=str(model_path)),
                running_mode=VisionRunningMode.IMAGE,
                num_poses=2,
                min_pose_detection_confidence=0.3,
                min_tracking_confidence=0.3,
            )
            try:
                opts = PoseLandmarkerOptions(**_pose_kwargs, min_pose_presence_score=0.3)
            except TypeError:
                opts = PoseLandmarkerOptions(**_pose_kwargs)

            cap = cv2.VideoCapture(str(self._video_path))
            fps   = cap.get(cv2.CAP_PROP_FPS) or 30
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            try:
                start_t = float(self.start_entry.get().strip() or 0)
            except ValueError:
                start_t = 0.0
            try:
                end_t = float(self.end_entry.get().strip() or 0)
            except ValueError:
                end_t = 0.0
            start_fi = int(start_t * fps)
            end_fi   = min(int(end_t * fps) if end_t else total - 1, total - 1)

            interval = max(1, self.interval_var.get())
            all_frames = list(range(start_fi, end_fi + 1, interval))
            if not all_frames:
                all_frames = [self._current_frame_idx]

            # Build target frame list
            if single_frame:
                target_frames = [self._current_frame_idx]
            elif from_frame is not None:
                target_frames = [f for f in all_frames if f >= from_frame]
                if not target_frames:
                    target_frames = [from_frame]
            else:
                target_frames = all_frames

            max_delta = self.delta_var.get()  # 0 = disabled

            n = len(target_frames)
            total_new = 0

            _LANDMARK_NAMES = [
                "nose","left_eye_inner","left_eye","left_eye_outer",
                "right_eye_inner","right_eye","right_eye_outer",
                "left_ear","right_ear","mouth_left","mouth_right",
                "left_shoulder","right_shoulder","left_elbow","right_elbow",
                "left_wrist","right_wrist","left_pinky","right_pinky",
                "left_index","right_index","left_thumb","right_thumb",
                "left_hip","right_hip","left_knee","right_knee",
                "left_ankle","right_ankle","left_heel","right_heel",
                "left_foot_index","right_foot_index",
            ]

            # Seed prev_landmarks from frames before the target range
            prev_landmarks: dict = {}
            if target_frames:
                seed_fi = target_frames[0] - 1
                while seed_fi >= 0 and not prev_landmarks:
                    prev_landmarks = dict(self._frame_poses.get(seed_fi, {}))
                    seed_fi -= 1

            new_poses = {}
            with PoseLandmarker.create_from_options(opts) as landmarker:
                for i, fi in enumerate(target_frames):
                    if fi in self._locked_frames:
                        if fi in self._frame_poses:
                            prev_landmarks = dict(self._frame_poses[fi])
                        continue
                    cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
                    ret, frame = cap.read()
                    if not ret:
                        continue

                    # Apply display transform so landmarks are in transformed-video space
                    if self._video_rotation or self._video_flip_h:
                        import numpy as _np
                        _pil = self._apply_transform(
                            Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
                        frame = cv2.cvtColor(_np.array(_pil), cv2.COLOR_RGB2BGR)

                    rect = self._frame_rects.get(fi, self._player_rect)
                    h_f, w_f = frame.shape[:2]
                    if rect:
                        rx1 = max(0, rect[0]); ry1 = max(0, rect[1])
                        rx2 = min(w_f, rect[2]); ry2 = min(h_f, rect[3])
                        crop = frame[ry1:ry2, rx1:rx2]
                        off_x, off_y = rx1, ry1
                    else:
                        crop = frame
                        off_x, off_y = 0, 0

                    if crop.size == 0:
                        continue

                    h_c, w_c = crop.shape[:2]
                    mp_img = mp.Image(
                        image_format=mp.ImageFormat.SRGB,
                        data=cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                    )
                    import math as _math
                    result = landmarker.detect(mp_img)
                    _accepted = None  # landmarks accepted for this frame

                    if result.pose_landmarks:
                        # --- Candidate selection ---
                        # Seed reference from previous centroid (crop-normalised),
                        # fall back to crop centre when no prior pose exists.
                        if prev_landmarks:
                            _pvx = sum(x for x, y in prev_landmarks.values()) / len(prev_landmarks)
                            _pvy = sum(y for x, y in prev_landmarks.values()) / len(prev_landmarks)
                            ref_cx = (_pvx - off_x) / w_c
                            ref_cy = (_pvy - off_y) / h_c
                        else:
                            ref_cx, ref_cy = 0.5, 0.5

                        _KEY_IDX = {_LANDMARK_NAMES.index(k)
                                    for k in ('left_hip', 'right_hip',
                                              'left_shoulder', 'right_shoulder',
                                              'left_knee', 'right_knee')
                                    if k in _LANDMARK_NAMES}

                        def _score(p_idx):
                            cand = result.pose_landmarks[p_idx]
                            mx = sum(lm.x for lm in cand) / len(cand)
                            my = sum(lm.y for lm in cand) / len(cand)
                            dist2 = (mx - ref_cx) ** 2 + (my - ref_cy) ** 2
                            vis = sum((cand[i].visibility or 0.0) for i in _KEY_IDX
                                      if i < len(cand)) / max(1, len(_KEY_IDX))
                            return dist2 - 0.3 * vis

                        best = min(range(len(result.pose_landmarks)), key=_score)
                        chosen = result.pose_landmarks[best]

                        # Map to full-frame coordinates
                        landmarks = {
                            name: (lm.x * w_c + off_x, lm.y * h_c + off_y)
                            for name, lm in zip(_LANDMARK_NAMES, chosen)
                            if (lm.visibility or 0.0) >= 0.3
                        }

                        # Reject if too many landmarks are outside the ROI
                        _outside = sum(
                            1 for (x, y) in landmarks.values()
                            if x < off_x or x > off_x + w_c
                            or y < off_y or y > off_y + h_c
                        )

                        # Reject if centroid jumped > 40% of ROI size relative to
                        # previous frame — prevents snapping to a nearby player.
                        _centroid_ok = True
                        if prev_landmarks and landmarks:
                            _ncx = sum(x for x, y in landmarks.values()) / len(landmarks)
                            _ncy = sum(y for x, y in landmarks.values()) / len(landmarks)
                            _pcx = sum(x for x, y in prev_landmarks.values()) / len(prev_landmarks)
                            _pcy = sum(y for x, y in prev_landmarks.values()) / len(prev_landmarks)
                            _jump = _math.hypot(_ncx - _pcx, _ncy - _pcy)
                            if _jump > 0.4 * max(w_c, h_c):
                                _centroid_ok = False

                        if _outside <= 3 and _centroid_ok and landmarks:
                            # Temporal smoothing
                            if max_delta > 0 and prev_landmarks:
                                smoothed = {}
                                for name, (nx, ny) in landmarks.items():
                                    if name in prev_landmarks:
                                        px, py = prev_landmarks[name]
                                        dist = _math.hypot(nx - px, ny - py)
                                        if dist > max_delta:
                                            scale = max_delta / dist
                                            nx = px + (nx - px) * scale
                                            ny = py + (ny - py) * scale
                                    smoothed[name] = (nx, ny)
                                landmarks = smoothed

                            # Consolidate head landmarks
                            _HEAD_SRC = [
                                "nose","left_eye_inner","left_eye","left_eye_outer",
                                "right_eye_inner","right_eye","right_eye_outer",
                                "left_ear","right_ear","mouth_left","mouth_right",
                            ]
                            _head_pts = [landmarks[k] for k in _HEAD_SRC if k in landmarks]
                            if _head_pts:
                                landmarks["head"] = (
                                    sum(p[0] for p in _head_pts) / len(_head_pts),
                                    sum(p[1] for p in _head_pts) / len(_head_pts),
                                )
                            for k in _HEAD_SRC:
                                landmarks.pop(k, None)

                            # Consolidate hand landmarks
                            _LHAND_SRC = ["left_wrist","left_pinky","left_index","left_thumb"]
                            _RHAND_SRC = ["right_wrist","right_pinky","right_index","right_thumb"]
                            for _hand_key, _srcs in [("left_hand", _LHAND_SRC),
                                                      ("right_hand", _RHAND_SRC)]:
                                _pts = [landmarks[k] for k in _srcs if k in landmarks]
                                if _pts:
                                    landmarks[_hand_key] = (
                                        sum(p[0] for p in _pts) / len(_pts),
                                        sum(p[1] for p in _pts) / len(_pts),
                                    )
                                for k in _srcs:
                                    landmarks.pop(k, None)

                            _accepted = landmarks

                    # Store result: new detection, or fall back to previous frame
                    if _accepted is not None:
                        new_poses[fi] = _accepted
                        prev_landmark