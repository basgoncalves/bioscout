"""Batch C3D Export Widget - Process multiple C3D files at once."""

import customtkinter as ctk
import tkinter                      # Text + Scrollbar: the max-EMG table
from pathlib import Path
import threading
from typing import List, Callable, Optional
import sys
import importlib.util
import shutil
import csv
import numpy as np
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.logger import logger
from utils.xml_utils import save_pretty_xml
from .c3d_export import C3DExportTab
from ..gui_settings import gui_settings, font_size, register_tk_font

# Try to import Inputs class and settings from settings module
try:
    from settings import Inputs, BatchSettings
    BATCH_C3D_EMG_LABEL_DEFAULT = BatchSettings.emg_label_default
    BATCH_C3D_EMG_LOWPASS_DEFAULT = BatchSettings.emg_lowpass_default
    BATCH_C3D_EMG_HIGHPASS_DEFAULT = BatchSettings.emg_highpass_default
    BATCH_C3D_EMG_NOTCH_DEFAULT = BatchSettings.emg_notch_default
    HAS_INPUTS = True
except ImportError:
    HAS_INPUTS = False
    # Fallback defaults if settings import fails
    BATCH_C3D_EMG_LABEL_DEFAULT = "emg"
    BATCH_C3D_EMG_LOWPASS_DEFAULT = "500"
    BATCH_C3D_EMG_HIGHPASS_DEFAULT = "10"
    BATCH_C3D_EMG_NOTCH_DEFAULT = "50"
    logger.warning("Could not import Inputs class from settings")

# Import exportC3D utilities (same as C3D Export tab)
try:
    code_dir = Path(__file__).parent.parent.parent
    exportc3d_path = code_dir / 'utils' / 'exportC3D.py'
    if exportc3d_path.exists():
        spec = importlib.util.spec_from_file_location("exportC3D", exportc3d_path)
        exportC3D = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(exportC3D)
        HAS_EXPORTC3D = True
    else:
        HAS_EXPORTC3D = False
except Exception as e:
    logger.warning("Could not import exportC3D: " + str(e))
    HAS_EXPORTC3D = False

# Try to import c3d for reading timing information
try:
    import c3d
    HAS_C3D = True
except ImportError:
    HAS_C3D = False

# Optional: scipy (filtering) and matplotlib (preview plot) — resolved LAZILY.
# This module is imported when the app starts, and importing scipy+matplotlib
# here put ~2s of scientific-stack start-up cost on every launch, paid before
# the window even painted, for features used only once this tab is open.
_sps = None
Figure = None
FigureCanvasTkAgg = None


def _load_scipy():
    global _sps
    if _sps is None:
        try:
            import scipy.signal as _m
            _sps = _m
        except ImportError:
            _sps = False
    return _sps


def _load_mpl():
    global Figure, FigureCanvasTkAgg
    if Figure is None:
        try:
            from matplotlib.figure import Figure as _F
            from matplotlib.backends.backend_tkagg import (
                FigureCanvasTkAgg as _C)
            Figure, FigureCanvasTkAgg = _F, _C
        except Exception:
            Figure = FigureCanvasTkAgg = False
    return bool(Figure)


class _Avail:
    """Truthy availability flag that does the import on FIRST CHECK, so the
    module-level names HAS_SCIPY / HAS_MPL keep working unchanged."""

    def __init__(self, loader):
        self._loader = loader

    def __bool__(self):
        return bool(self._loader())


HAS_SCIPY = _Avail(_load_scipy)
HAS_MPL = _Avail(_load_mpl)

# ============================================================================
# DEFAULT FOOT MARKER PATTERNS - EDIT THESE TO CUSTOMIZE MARKER DETECTION
# ============================================================================
# These lists define which markers are considered "foot markers" and will be
# auto-checked when "Load Channels" is clicked. Markers not in these lists
# will appear unchecked by default.

def _same_path(a, b):
    """Whether two path strings name the same folder, slashes and case aside."""
    try:
        if not a or not b:
            return False
        return Path(str(a)).resolve() == Path(str(b)).resolve()
    except Exception:                                          # noqa: BLE001
        return str(a).strip().rstrip("\\/") == str(b).strip().rstrip("\\/")


class _NullBar:
    """Stands in for the removed CTkProgressBar so ``progress_bar.set(x)``
    stays a no-op instead of an AttributeError in the export thread."""

    def set(self, _value):
        return None

    def configure(self, **_kw):
        return None


def interpolate_marker_position(marker_data, frame_idx, max_gap=10):
    """
    Interpolate missing marker position using neighboring frames.

    Args:
        marker_data: Array of marker positions (frames x 3 for x,y,z)
        frame_idx: Frame index to interpolate
        max_gap: Maximum gap size to interpolate across

    Returns:
        Interpolated position or None if can't interpolate
    """
    if marker_data is None or len(marker_data) == 0:
        return None

    # Find nearest frames with valid data
    before_idx = None
    after_idx = None

    # Search backwards
    for i in range(frame_idx - 1, max(0, frame_idx - max_gap), -1):
        if marker_data[i] is not None and not np.all(np.isnan(marker_data[i])):
            before_idx = i
            break

    # Search forwards
    for i in range(frame_idx + 1, min(len(marker_data), frame_idx + max_gap)):
        if marker_data[i] is not None and not np.all(np.isnan(marker_data[i])):
            after_idx = i
            break

    # Linear interpolation between valid frames
    if before_idx is not None and after_idx is not None:
        w1 = (after_idx - frame_idx) / (after_idx - before_idx)
        w2 = (frame_idx - before_idx) / (after_idx - before_idx)
        return w1 * marker_data[before_idx] + w2 * marker_data[after_idx]

    # Use nearest valid frame if interpolation not possible
    if before_idx is not None:
        return marker_data[before_idx]
    if after_idx is not None:
        return marker_data[after_idx]

    return None


LEFT_FOOT_MARKER_PATTERNS = [
    # Heel
    "LHEE", "HEEL_L", "L_HEEL", "LHEEL", "HeelL",
    # Toe
    "LTOE", "TOE_L", "L_TOE", "LTOE", "ToeL", "LTIP",
    # Metatarsal heads
    "LMT1", "LMT2", "LMT3", "LMT4", "LMT5",
    "LMET1", "LMET2", "LMET3", "LMET4", "LMET5",
    "MT1_L", "MT2_L", "MT3_L", "MT4_L", "MT5_L",
    "MET1_L", "MET2_L", "MET3_L", "MET4_L", "MET5_L",
    # Big toe and small toe
    "LBIG", "LSMALL", "L_BIG", "L_SMALL", "LHLY",
    # Ankle variations
    "LANK", "ANKLE_L", "L_ANKLE",
]

RIGHT_FOOT_MARKER_PATTERNS = [
    # Heel
    "RHEE", "HEEL_R", "R_HEEL", "RHEEL", "HeelR",
    # Toe
    "RTOE", "TOE_R", "R_TOE", "RToE", "ToeR", "RTIP",
    # Metatarsal heads
    "RMT1", "RMT2", "RMT3", "RMT4", "RMT5",
    "RMET1", "RMET2", "RMET3", "RMET4", "RMET5",
    "MT1_R", "MT2_R", "MT3_R", "MT4_R", "MT5_R",
    "MET1_R", "MET2_R", "MET3_R", "MET4_R", "MET5_R",
    # Big toe and small toe
    "RBIG", "RSMALL", "R_BIG", "R_SMALL", "RHLY",
    # Ankle variations
    "RANK", "ANKLE_R", "R_ANKLE",
]
# ============================================================================


class BatchC3DExport(ctk.CTkFrame):
    """Batch processor for multiple C3D files."""

    def __init__(self, parent, config_manager=None, status_callback=None):
        """Initialize Batch C3D Export widget.

        ``config_manager``/``status_callback`` are the pair every other tab
        takes. This one used to be constructed with neither, which is why it
        was the only tab that could not report status and had nowhere to
        remember anything between launches."""
        super().__init__(parent)

        self.config_manager = config_manager
        self.status_callback = status_callback
        self.gui_settings = gui_settings()

        self.source_folder = None
        self.dest_folder = None
        self.project_dir = None  # set by main_window.broadcast_project_dir
        self.c3d_files: List[Path] = []
        self.selected_files: List[bool] = []
        self.is_processing = False
        self.current_progress = 0
        self.total_files = 0
        self.session_dir = None  # Track session directory
        self.all_detected_markers = set()  # Store all markers detected across trials
        self._all_analog_channels: list = []  # All analog channels found (unfiltered)
        self.max_emg_per_trial: dict = {}    # channel -> {trial: peak}
        self._emg_scale_entries: dict = {}   # channel -> StringVar (per-muscle)
        #: The last destination this tab filled in by itself. Anything else in
        #: the box was put there by the user and is never overwritten.
        self._auto_dest = ""

        self._create_widgets()
        self._restore_ui_state()

    # ------------------------------------------------------------------
    # Where a file dialog should open
    # ------------------------------------------------------------------
    def set_project_dir(self, project_dir):
        """Called by ``main_window.broadcast_project_dir`` on every project
        load. This tab did not implement it, so it never learned what project
        was open — which is why Browse opened wherever Windows last happened to
        be, often in an unrelated study."""
        try:
            self.project_dir = Path(project_dir) if project_dir else None
        except Exception:                                      # noqa: BLE001
            self.project_dir = None
        if self.project_dir:
            self.gui_settings.remember_path("paths.last_project",
                                            str(self.project_dir))
            logger.debug(f"Batch C3D: project dir set to {self.project_dir}")

    def _start_dir(self, kind="source"):
        """Best guess at where a folder picker should open, most specific first.

        1. what is already typed in that field   — you are correcting a path
        2. the other field                       — source and dest are siblings
        3. the last folder used for this purpose — per machine, not per project
        4. <project>/simulations, then <project> — the project that is open
        5. home                                  — anything but someone else's study
        """
        candidates = []
        typed = (self.source_folder_var.get() if kind == "source"
                 else self.dest_entry.get())
        other = (self.dest_entry.get() if kind == "source"
                 else self.source_folder_var.get())
        candidates += [typed, other]
        candidates.append(self.gui_settings.get(
            "paths.last_c3d_source" if kind == "source" else "paths.last_c3d_dest", ""))
        if self.session_dir:
            candidates.append(str(self.session_dir))
        if self.project_dir:
            candidates.append(str(Path(self.project_dir) / "simulations"))
            candidates.append(str(self.project_dir))
        candidates.append(self.gui_settings.get("paths.last_project", ""))
        candidates.append(str(Path.home()))
        for c in candidates:
            try:
                if c and Path(c).is_dir():
                    return str(c)
            except Exception:                                  # noqa: BLE001
                continue
        return ""

    # ------------------------------------------------------------------
    # Remembering what you typed last time
    # ------------------------------------------------------------------
    #: Everything worth restoring, as {settings key: attribute holding a
    #: StringVar}. Folders are NOT in here — they live under `paths.*` so the
    #: Settings tab can show and clear them in one place.
    _PERSISTED_VARS = {
        "c3d_export.emg_label": "emg_label_var",
        "c3d_export.emg_lowpass": "emg_lowpass_var",
        "c3d_export.emg_highpass": "emg_highpass_var",
        "c3d_export.emg_notch": "emg_notch_var",
        "c3d_export.maxemg_window": "maxemg_window_var",
        "c3d_export.marker_remove": "marker_remove_var",
        "c3d_export.emg_scale_uniform": "emg_scale_value_var",
    }

    def _save_ui_state(self):
        """Write the current form to the per-machine GUI settings.

        Per-MACHINE on purpose. These are working preferences, not a record of
        how the data was produced — what actually processed a trial is written
        into that trial's own settings at export time, where it stays true even
        if the form is changed afterwards."""
        try:
            data = {}
            for key, attr in self._PERSISTED_VARS.items():
                var = getattr(self, attr, None)
                if var is not None:
                    data[key] = var.get()
            data["c3d_export.emg_scale_enabled"] = bool(
                getattr(self, "emg_scale_enabled_var", None)
                and self.emg_scale_enabled_var.get())
            for key, attr in (("c3d_export.post_session", "post_session_var"),
                              ("c3d_export.post_detect", "post_detect_var")):
                var = getattr(self, attr, None)
                if var is not None:
                    data[key] = bool(var.get())
            data["c3d_export.emg_scale_mode"] = (
                self.emg_scale_mode_var.get()
                if getattr(self, "emg_scale_mode_var", None) else "uniform")
            # Remembering WHICH dest was auto-filled is what lets the next
            # launch keep following the source folder, while still leaving a
            # deliberately chosen destination alone.
            data["c3d_export.auto_dest"] = getattr(self, "_auto_dest", "")
            data["c3d_export.emg_scale_per_channel"] = {
                ch: v.get() for ch, v in self._emg_scale_entries.items()
                if str(v.get()).strip() not in ("", "1", "1.0")}
            left, right = self._get_selected_markers()
            data["c3d_export.left_markers"] = list(left)
            data["c3d_export.right_markers"] = list(right)
            data["c3d_export.emg_channels"] = list(self._get_selected_emg_channels())
            self.gui_settings.update(data)
        except Exception as exc:                               # noqa: BLE001
            logger.debug(f"Batch C3D: could not save UI state: {exc}")

    def _restore_ui_state(self):
        """Put back what was typed last time. Best-effort and silent: a stale
        settings file must never stop the tab from opening."""
        try:
            for key, attr in self._PERSISTED_VARS.items():
                var = getattr(self, attr, None)
                stored = self.gui_settings.get(key, None)
                if var is not None and stored not in (None, ""):
                    var.set(stored)
            if getattr(self, "emg_scale_enabled_var", None) is not None:
                self.emg_scale_enabled_var.set(
                    bool(self.gui_settings.get("c3d_export.emg_scale_enabled", False)))
            for key, attr, dflt in (
                    ("c3d_export.post_session", "post_session_var", True),
                    ("c3d_export.post_detect", "post_detect_var", True)):
                var = getattr(self, attr, None)
                if var is not None:
                    var.set(bool(self.gui_settings.get(key, dflt)))
            if getattr(self, "emg_scale_mode_var", None) is not None:
                self.emg_scale_mode_var.set(
                    self.gui_settings.get("c3d_export.emg_scale_mode", "uniform"))
            # DEST FIRST, then source. Validating the source auto-fills the
            # destination, and it must be able to see a remembered path in the
            # box to know it is not allowed to replace it.
            self._auto_dest = str(self.gui_settings.get("c3d_export.auto_dest", "") or "")
            dst = self.gui_settings.get("paths.last_c3d_dest", "")
            if dst and Path(dst).is_dir() and not self.dest_entry.get():
                self.dest_entry.insert(0, dst)
                self._validate_dest_folder()
            src = self.gui_settings.get("paths.last_c3d_source", "")
            if src and Path(src).is_dir() and not self.source_folder_var.get():
                self.source_folder_var.set(src)
                self._validate_source_folder()
        except Exception as exc:                               # noqa: BLE001
            logger.debug(f"Batch C3D: could not restore UI state: {exc}")

    def _remembered_selection(self, kind):
        """Marker/EMG names ticked last time, as a set (empty when none)."""
        try:
            return set(self.gui_settings.get(f"c3d_export.{kind}", []) or [])
        except Exception:                                      # noqa: BLE001
            return set()

    def set_session_dir(self, session_dir: str):
        """Set the session directory - called by main window."""
        self.session_dir = Path(session_dir) if session_dir else None
        if self.session_dir and self.session_dir.exists():
            # A session keeps its raw C3Ds in 1_c3dfiles, not loose in the
            # session folder — point at that when it is there.
            src = self.session_dir
            for _name in ("1_c3dfiles", "c3dfiles"):
                if (self.session_dir / _name).is_dir():
                    src = self.session_dir / _name
                    break
            self.source_folder_var.set(str(src))
            self.source_folder = src

            dest = self._default_dest_for(src) or src
            self._auto_dest = str(dest)
            self.dest_entry.delete(0, "end")
            self.dest_entry.insert(0, str(dest))
            self.dest_folder = dest

            self._scan_for_c3d_files()

            # Auto-populate markers from C3D files
            self._update_markers_from_c3d()

            logger.debug(f"Batch C3D: Session directory set to {self.session_dir}")

    def _create_widgets(self):
        """Create UI widgets - compact layout with file list on left."""
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        # 1:8, not 3:7 — the file list is a fixed-width list of short names,
        # the settings column holds the plot that actually needs room.
        self.grid_columnconfigure(0, weight=1, minsize=190)
        self.grid_columnconfigure(1, weight=8)

        # ===== FOLDER SELECTION SECTION (spans both columns) =====
        folder_frame = ctk.CTkFrame(self)
        folder_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=(2, 2))
        folder_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(folder_frame, text="Batch C3D Export", font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=5, pady=(3, 5)
        )

        # C3D source folder (visible row)
        self.source_folder_var = ctk.StringVar(value="")
        self.source_folder_var.trace("w", lambda *args: self._validate_source_folder())
        ctk.CTkLabel(folder_frame, text="C3D Folder:", font=("Segoe UI", 9)).grid(
            row=1, column=0, sticky="w", padx=5, pady=(2, 1)
        )
        self.source_entry = ctk.CTkEntry(
            folder_frame,
            textvariable=self.source_folder_var,
            placeholder_text="Folder containing .c3d files...",
            font=("Segoe UI", 9))
        self.source_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=(2, 1))
        ctk.CTkButton(
            folder_frame,
            text="Browse",
            width=80,
            font=("Segoe UI", 9),
            command=self._select_source_folder,
        ).grid(row=1, column=2, sticky="ew", padx=5, pady=(2, 1))
        self.source_error = ctk.CTkLabel(folder_frame, text="", text_color="#dc3545", font=("Segoe UI", 8))

        # Destination folder
        ctk.CTkLabel(folder_frame, text="Dest. Folder:", font=("Segoe UI", 9)).grid(
            row=2, column=0, sticky="w", padx=5, pady=(2, 1)
        )
        self.dest_entry = ctk.CTkEntry(folder_frame, placeholder_text="Paste folder path or browse...", font=("Segoe UI", 9))
        self.dest_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=(2, 1))
        self.dest_entry.bind("<KeyRelease>", lambda e: self._validate_dest_folder())

        ctk.CTkButton(
            folder_frame,
            text="Browse",
            width=80,
            font=("Segoe UI", 9),
            command=self._select_dest_folder,
        ).grid(row=2, column=2, sticky="ew", padx=5, pady=(2, 1))

        self.dest_error = ctk.CTkLabel(folder_frame, text="", text_color="#dc3545", font=("Segoe UI", 8))
        self.dest_error.grid(row=3, column=0, columnspan=3, sticky="w", padx=5, pady=(0, 2))

        # ===== LEFT COLUMN: FILE SELECTION SECTION =====
        files_frame = ctk.CTkFrame(self)
        files_frame.grid(row=1, column=0, sticky="nsew", padx=(5, 2), pady=(2, 2))
        files_frame.grid_rowconfigure(1, weight=1)
        files_frame.grid_columnconfigure(0, weight=1)

        # File list header
        header_frame = ctk.CTkFrame(files_frame)
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 3))
        header_frame.grid_columnconfigure(0, weight=1)

        files_found_label = ctk.CTkLabel(header_frame, text="C3D Files:", font=("Segoe UI", 8, "bold"))
        files_found_label.pack(side="left", padx=5)

        self.file_count_label = ctk.CTkLabel(header_frame, text="0", text_color="gray", font=("Segoe UI", 8))
        self.file_count_label.pack(side="left", padx=2)

        # File selection buttons
        button_frame = ctk.CTkFrame(header_frame)
        button_frame.pack(side="right", padx=5)

        ctk.CTkButton(
            button_frame,
            text="Select All",
            width=55,
            font=("Segoe UI", 8),
            command=self._select_all_files,
        ).pack(side="left", padx=1)

        ctk.CTkButton(
            button_frame,
            text="Deselect",
            width=55,
            font=("Segoe UI", 8),
            command=self._deselect_all_files,
        ).pack(side="left", padx=1)

        # File list with checkboxes
        self.files_scroll_frame = ctk.CTkScrollableFrame(files_frame, width=175)
        self.files_scroll_frame.grid(row=1, column=0, sticky="nsew")
        self.files_scroll_frame.grid_columnconfigure(0, weight=1)

        self.file_checkboxes: List[ctk.CTkCheckBox] = []
        self.file_vars: List[ctk.BooleanVar] = []

        # ===== RIGHT COLUMN: EMG SETTINGS & MARKERS SECTION =====
        settings_frame = ctk.CTkFrame(self)
        settings_frame.grid(row=1, column=1, sticky="nsew", padx=(2, 5), pady=(2, 2))
        settings_frame.grid_rowconfigure(0, weight=1)
        # 5:1 — the marker lists are two narrow name columns; everything that
        # needs width (filters, channel list, preview plot) is on the left.
        settings_frame.grid_columnconfigure(0, weight=5)
        settings_frame.grid_columnconfigure(1, weight=1, minsize=230)

        # Each side gets a single container frame that manages its own internal
        # grid. This keeps the EMG column (filters + live preview + channels +
        # max-EMG) and the markers column independent so they can each fill the
        # full height of the panel.
        emg_col = ctk.CTkFrame(settings_frame)
        emg_col.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        emg_col.grid_columnconfigure(0, weight=1)
        # Row 3 holds channels-beside-preview; row 5 the max-EMG table. The
        # old layout stacked preview, channel list and results vertically and
        # the channel list was the row that lost — it collapsed to nothing.
        emg_col.grid_rowconfigure(2, minsize=0)  # freed: filters moved into row 1
        emg_col.grid_rowconfigure(3, weight=10)  # channels | preview plot
        emg_col.grid_rowconfigure(5, weight=1)   # max-EMG results

        markers_col = ctk.CTkFrame(settings_frame)
        markers_col.grid(row=0, column=1, sticky="nsew")
        markers_col.grid_columnconfigure(0, weight=1)
        markers_col.grid_rowconfigure(2, weight=1)  # marker columns extend down

        # ----- EMG column: header -----
        header_frame2 = ctk.CTkFrame(emg_col)
        header_frame2.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 3))
        header_frame2.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header_frame2, text="EMG Settings:", font=("Segoe UI", 8, "bold")).pack(side="left", anchor="w", padx=5)

        # "Update Markers" named the side effect nobody was looking at: the
        # button's job is to READ the ticked C3D file and fill in the EMG
        # channel list (the markers come along with it).
        ctk.CTkButton(
            header_frame2,
            text="⟳ Load Channels",
            width=140, height=28,
            font=("Segoe UI", 12, "bold"),
            command=self._update_markers_from_c3d,
        ).pack(side="right", padx=4, pady=2)

        # ----- EMG column: ONE settings bar -----
        # Label+Search and Low/High/Notch used to be two stacked frames, each
        # with its own heading row — ~110 px of chrome above a plot that had
        # none to spare. Everything here is a short numeric field, so it all
        # fits on one line and the plot gets the height back.
        bar = ctk.CTkFrame(emg_col)
        bar.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 3))
        bar.grid_columnconfigure(1, weight=1)     # only the label box stretches

        ctk.CTkLabel(bar, text="Label:", font=("Segoe UI", 11)).grid(
            row=0, column=0, sticky="w", padx=(6, 2), pady=4)
        self.emg_label_var = ctk.StringVar(value=BATCH_C3D_EMG_LABEL_DEFAULT)
        self.emg_label_entry = ctk.CTkEntry(
            bar, textvariable=self.emg_label_var,
            placeholder_text=BATCH_C3D_EMG_LABEL_DEFAULT, height=26)
        self.emg_label_entry.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        self.emg_label_entry.bind("<Return>", lambda e: self._filter_emg_channels())
        ctk.CTkButton(
            bar, text="Search", width=64, height=26,
            command=self._filter_emg_channels,
        ).grid(row=0, column=2, padx=(0, 10), pady=4)

        # Low / High / Notch — label above value would cost a second line, so
        # the unit lives in the label beside the box.
        ctk.CTkLabel(bar, text="Band (Hz):", font=("Segoe UI", 11)).grid(
            row=0, column=3, sticky="e", padx=(0, 3), pady=4)
        self.emg_highpass_var = ctk.StringVar(value=BATCH_C3D_EMG_HIGHPASS_DEFAULT)
        hp_entry = ctk.CTkEntry(bar, textvariable=self.emg_highpass_var,
                                height=26, width=56)
        hp_entry.grid(row=0, column=4, padx=(0, 2), pady=4)
        ctk.CTkLabel(bar, text="–", font=("Segoe UI", 11)).grid(
            row=0, column=5, padx=1, pady=4)
        self.emg_lowpass_var = ctk.StringVar(value=BATCH_C3D_EMG_LOWPASS_DEFAULT)
        lp_entry = ctk.CTkEntry(bar, textvariable=self.emg_lowpass_var,
                                height=26, width=56)
        lp_entry.grid(row=0, column=6, padx=(2, 10), pady=4)

        ctk.CTkLabel(bar, text="Notch:", font=("Segoe UI", 11)).grid(
            row=0, column=7, sticky="e", padx=(0, 3), pady=4)
        self.emg_notch_var = ctk.StringVar(value=BATCH_C3D_EMG_NOTCH_DEFAULT)
        notch_entry = ctk.CTkEntry(bar, textvariable=self.emg_notch_var,
                                   height=26, width=56)
        notch_entry.grid(row=0, column=8, padx=(0, 10), pady=4)

        # Analog frame rate, read from the C3D — the number every cut-off above
        # has to stay under half of.
        self.analog_fps = None
        self.fps_label = ctk.CTkLabel(bar, text="FPS: --", font=("Segoe UI", 10),
                                      text_color="#888888")
        self.fps_label.grid(row=0, column=9, sticky="e", padx=(0, 8), pady=4)

        # Pressing Enter in any filter field refreshes the live preview
        for _e in (lp_entry, hp_entry, notch_entry):
            _e.bind("<Return>", lambda e: self._update_filter_preview())

        # ----- EMG column: channels BESIDE the preview -----
        # One row, two columns: the tick list of channels on the left (under
        # the Low/High/Notch fields, where the eye already is after setting a
        # filter) and the preview plot on the right. Stacked vertically these
        # fought for height and the channel list always lost.
        mid = ctk.CTkFrame(emg_col, fg_color="transparent")
        mid.grid(row=3, column=0, sticky="nsew", padx=5, pady=(0, 3))
        mid.grid_rowconfigure(1, weight=1, minsize=300)
        mid.grid_columnconfigure(0, minsize=175)   # channels — never collapses
        # minsize: a plot narrower than this is a smear, not a preview.
        mid.grid_columnconfigure(1, weight=1, minsize=430)

        # -- left: EMG channel tick list --
        ch_head = ctk.CTkFrame(mid, fg_color="transparent")
        ch_head.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkLabel(ch_head, text="EMG Channels:",
                     font=("Segoe UI", 10, "bold")).pack(side="left", padx=2)
        ctk.CTkButton(ch_head, text="All", width=40, height=22,
                      font=("Segoe UI", 9),
                      command=self._select_all_emg).pack(side="right", padx=1)
        ctk.CTkButton(ch_head, text="None", width=44, height=22,
                      font=("Segoe UI", 9),
                      command=self._deselect_all_emg).pack(side="right", padx=1)

        self.emg_channels_scroll = ctk.CTkScrollableFrame(mid)
        self.emg_channels_scroll.grid(row=1, column=0, sticky="nsew",
                                      padx=(0, 4), pady=(2, 0))
        self.emg_channels_scroll.grid_columnconfigure(0, weight=1)
        self.emg_channel_vars = {}
        self.emg_channel_checkboxes = []

        # -- right: preview controls + plot --
        preview_ctrl = ctk.CTkFrame(mid)
        preview_ctrl.grid(row=0, column=1, sticky="ew")
        preview_ctrl.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(preview_ctrl, text="Preview ch:", font=("Segoe UI", 7, "bold")).grid(row=0, column=0, sticky="w", padx=(2, 4))
        self.preview_channel_var = ctk.StringVar(value="")
        self.preview_channel_menu = ctk.CTkOptionMenu(
            preview_ctrl, variable=self.preview_channel_var, values=["(no channels)"],
            font=("Segoe UI", 8), height=24,
            command=lambda _v: self._update_filter_preview(),
        )
        self.preview_channel_menu.grid(row=0, column=1, sticky="ew", padx=(0, 4))
        ctk.CTkButton(
            preview_ctrl, text="Preview", width=70, height=24, font=("Segoe UI", 8),
            command=self._update_filter_preview,
        ).grid(row=0, column=2, padx=0)

        # ----- EMG column: live filter preview plot -----
        self.preview_plot_frame = ctk.CTkFrame(mid)
        self.preview_plot_frame.grid(row=1, column=1, sticky="nsew", pady=(2, 0))
        self.preview_plot_frame.grid_rowconfigure(0, weight=1)
        self.preview_plot_frame.grid_columnconfigure(0, weight=1)

        self.preview_canvas = None  # FigureCanvasTkAgg, created lazily
        self.preview_fig = None
        self._preview_placeholder = ctk.CTkLabel(
            self.preview_plot_frame,
            text=("Tick a C3D file, click 'Load Channels', then 'Preview' to\n"
                  "visualise the filter effect on the EMG signal."
                  if (HAS_MPL and HAS_SCIPY) else
                  "Live preview needs matplotlib + scipy installed."),
            text_color="#888888", font=("Segoe UI", 8), justify="center",
        )
        self._preview_placeholder.grid(row=0, column=0, sticky="nsew")

        # (The b2 "hide the preview" block is gone: the preview no longer costs
        # the channel list its space — they share row 3 side by side — so the
        # reason for hiding it no longer exists.)

        # ----- EMG column: max-EMG calculator -----
        maxemg_ctrl = ctk.CTkFrame(emg_col)
        maxemg_ctrl.grid(row=4, column=0, sticky="ew", padx=5, pady=(6, 2))
        maxemg_ctrl.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(maxemg_ctrl, text="Max EMG", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w", padx=(2, 6))
        ctk.CTkLabel(maxemg_ctrl, text="Window (frames):", font=("Segoe UI", 10)).grid(row=0, column=1, sticky="e", padx=(0, 2))
        self.maxemg_window_var = ctk.StringVar(value="100")
        ctk.CTkEntry(maxemg_ctrl, textvariable=self.maxemg_window_var, height=28,
                     width=70, font=("Segoe UI", 11)).grid(row=0, column=2, sticky="w", padx=(0, 6))
        self.maxemg_button = ctk.CTkButton(
            maxemg_ctrl, text="Compute", width=90, height=28, font=("Segoe UI", 11),
            command=self._on_compute_max_emg,
        )
        self.maxemg_button.grid(row=0, column=4, sticky="e", padx=0)

        # RESULTS TABLE — a Text widget, not a stack of labels.
        # The table is now one column per trial (peak as % of that channel's
        # own maximum), which is far wider than the panel. A Text widget with
        # wrap="none" scrolls in BOTH directions for free, keeps the monospace
        # columns aligned, and lets the whole table be selected and copied —
        # none of which a column of CTkLabels can do.
        maxemg_table = ctk.CTkFrame(emg_col)
        maxemg_table.grid(row=5, column=0, sticky="nsew", padx=5, pady=(0, 3))
        maxemg_table.grid_rowconfigure(0, weight=1)
        maxemg_table.grid_columnconfigure(0, weight=1)
        # font_size(): plain tkinter.Text does not follow CTk widget scaling,
        # so the table takes the UI scale explicitly or stays small forever.
        self.maxemg_text = tkinter.Text(
            maxemg_table, wrap="none", height=5,
            background="#1e1e1e", foreground="#dcdcdc",
            insertbackground="#dcdcdc", relief="flat", borderwidth=0,
            highlightthickness=0,
        )
        register_tk_font(self.maxemg_text, "Consolas", 11)
        self.maxemg_text.grid(row=0, column=0, sticky="nsew")
        _mv = tkinter.Scrollbar(maxemg_table, orient="vertical",
                                command=self.maxemg_text.yview)
        _mv.grid(row=0, column=1, sticky="ns")
        _mh = tkinter.Scrollbar(maxemg_table, orient="horizontal",
                                command=self.maxemg_text.xview)
        _mh.grid(row=1, column=0, sticky="ew")
        self.maxemg_text.configure(yscrollcommand=_mv.set, xscrollcommand=_mh.set)
        self.maxemg_text.tag_configure("head", foreground="#9fc5e8")
        self.maxemg_text.configure(state="disabled")
        self.maxemg_result_labels = []            # kept: older code appends here
        self.max_emg_results = {}                 # channel -> (max_value, trial_name)
        self.max_emg_per_trial = {}               # channel -> {trial: peak}

        # ----- EMG column: export scaling -----
        # Applied to the exported EMG, after filtering. Two modes because both
        # are real: one gain for the whole rig, or one per electrode when the
        # channels were not matched.
        scale_frame = ctk.CTkFrame(emg_col)
        scale_frame.grid(row=6, column=0, sticky="ew", padx=5, pady=(0, 4))
        scale_frame.grid_columnconfigure(3, weight=1)

        self.emg_scale_enabled_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(scale_frame, text="Scale EMG", font=("Segoe UI", 11, "bold"),
                        variable=self.emg_scale_enabled_var,
                        command=self._on_emg_scale_toggle
                        ).grid(row=0, column=0, sticky="w", padx=(4, 8), pady=4)

        self.emg_scale_mode_var = ctk.StringVar(value="uniform")
        ctk.CTkSegmentedButton(
            scale_frame, values=["uniform", "per muscle"],
            variable=self.emg_scale_mode_var, font=("Segoe UI", 10),
            command=lambda _v: self._on_emg_scale_toggle()
        ).grid(row=0, column=1, sticky="w", padx=(0, 8), pady=4)

        self.emg_scale_value_var = ctk.StringVar(value="1.0")
        self.emg_scale_entry = ctk.CTkEntry(
            scale_frame, textvariable=self.emg_scale_value_var, width=80,
            height=28, font=("Segoe UI", 11))
        self.emg_scale_entry.grid(row=0, column=2, sticky="w", pady=4)
        self.emg_scale_entry.bind("<FocusOut>", lambda _e: self._save_ui_state())

        self.emg_scale_hint = ctk.CTkLabel(
            scale_frame, text="factor applied to every selected channel",
            font=("Segoe UI", 10), text_color="#8a8a8a")
        self.emg_scale_hint.grid(row=0, column=3, sticky="w", padx=8)

        ctk.CTkButton(scale_frame, text="From Max EMG", width=110, height=28,
                      font=("Segoe UI", 10), command=self._fill_scales_from_max_emg
                      ).grid(row=0, column=4, sticky="e", padx=4, pady=4)

        self.emg_scale_per_frame = ctk.CTkScrollableFrame(scale_frame, height=84)
        self.emg_scale_per_frame.grid(row=1, column=0, columnspan=5, sticky="ew",
                                      padx=4, pady=(0, 4))
        self.emg_scale_per_frame.grid_columnconfigure(1, weight=1)
        self.emg_scale_per_frame.grid_remove()      # shown only in per-muscle mode

        # ----- Markers column: header -----
        ctk.CTkLabel(markers_col, text="All Markers:", font=("Segoe UI", 8, "bold")).grid(
            row=0, column=0, sticky="w", padx=5, pady=(0, 2)
        )

        # ----- Markers column: remove-substrings input -----
        marker_remove_frame = ctk.CTkFrame(markers_col)
        marker_remove_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 3))
        marker_remove_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(marker_remove_frame, text="Remove (; sep):", font=("Segoe UI", 7, "bold")).grid(
            row=0, column=0, sticky="w", padx=(2, 4)
        )
        self.marker_remove_var = ctk.StringVar(value="")
        marker_remove_entry = ctk.CTkEntry(
            marker_remove_frame, textvariable=self.marker_remove_var,
            placeholder_text="e.g. Athlete_20:;Bar:", height=24, font=("Segoe UI", 8),
        )
        marker_remove_entry.grid(row=0, column=1, sticky="ew", padx=(0, 4))
        marker_remove_entry.bind("<Return>", lambda e: self._update_markers_from_c3d())
        ctk.CTkButton(
            marker_remove_frame, text="Apply", width=60, height=24, font=("Segoe UI", 8),
            command=self._update_markers_from_c3d,
        ).grid(row=0, column=2, padx=0)

        # ----- Markers column: left/right marker lists -----
        markers_frame = ctk.CTkFrame(markers_col)
        markers_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=(0, 3))
        markers_frame.grid_columnconfigure(0, weight=1)
        markers_frame.grid_columnconfigure(1, weight=1)
        markers_frame.grid_rowconfigure(0, weight=1)

        # Left foot markers (ALL markers, not just L-prefixed)
        left_foot_frame = ctk.CTkFrame(markers_frame)
        left_foot_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 2))
        left_foot_frame.grid_rowconfigure(2, weight=1)
        left_foot_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(left_foot_frame, text="Left Foot", font=("Segoe UI", 7, "bold")).grid(row=0, column=0, sticky="w", padx=2, pady=(0, 1))

        # All/None buttons for left foot
        left_btn_frame = ctk.CTkFrame(left_foot_frame)
        left_btn_frame.grid(row=1, column=0, sticky="ew", padx=0, pady=(0, 2))
        ctk.CTkButton(left_btn_frame, text="All", width=35, font=("Segoe UI", 7), command=self._select_all_left_markers).pack(side="left", padx=1)
        ctk.CTkButton(left_btn_frame, text="None", width=35, font=("Segoe UI", 7), command=self._deselect_all_left_markers).pack(side="left", padx=1)

        self.left_markers_scroll = ctk.CTkScrollableFrame(left_foot_frame, width=105)
        self.left_markers_scroll.grid(row=2, column=0, sticky="nsew")
        self.left_markers_scroll.grid_columnconfigure(0, weight=1)

        self.left_marker_vars = {}
        self.left_marker_checkboxes = []

        # Right foot markers (ALL markers, not just R-prefixed)
        right_foot_frame = ctk.CTkFrame(markers_frame)
        right_foot_frame.grid(row=0, column=1, sticky="nsew", padx=(2, 0))
        right_foot_frame.grid_rowconfigure(2, weight=1)
        right_foot_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right_foot_frame, text="Right Foot", font=("Segoe UI", 7, "bold")).grid(row=0, column=0, sticky="w", padx=2, pady=(0, 1))

        # All/None buttons for right foot
        right_btn_frame = ctk.CTkFrame(right_foot_frame)
        right_btn_frame.grid(row=1, column=0, sticky="ew", padx=0, pady=(0, 2))
        ctk.CTkButton(right_btn_frame, text="All", width=35, font=("Segoe UI", 7), command=self._select_all_right_markers).pack(side="left", padx=1)
        ctk.CTkButton(right_btn_frame, text="None", width=35, font=("Segoe UI", 7), command=self._deselect_all_right_markers).pack(side="left", padx=1)

        self.right_markers_scroll = ctk.CTkScrollableFrame(right_foot_frame, width=105)
        self.right_markers_scroll.grid(row=2, column=0, sticky="nsew")
        self.right_markers_scroll.grid_columnconfigure(0, weight=1)

        self.right_marker_vars = {}
        self.right_marker_checkboxes = []

        # Initialize with empty markers (will be populated when files are scanned)
        # All markers start unchecked by default
        self._populate_marker_checkboxes([], [])

        # Initialize with default EMG channels (empty, will be populated when files are scanned)
        default_emg_channels = []
        self._populate_emg_channels(default_emg_channels)

        # ===== PROGRESS SECTION (spans both columns) =====
        progress_frame = ctk.CTkFrame(self)
        progress_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=(2, 2))
        self.grid_rowconfigure(2, weight=0)  # Progress row should not expand
        progress_frame.grid_columnconfigure(1, weight=1)

        # No progress BAR. It was a full-width strip of chrome duplicating what
        # the console below already prints line by line — and the console says
        # WHICH file, which is the part you actually need when one fails. What
        # is left is a single status line; _NullBar keeps the old .set() calls
        # working so the export code did not have to be rewritten around it.
        self.progress_bar = _NullBar()

        self.progress_label = ctk.CTkLabel(
            progress_frame,
            text="Ready",
            text_color="gray",
            font=("Segoe UI", 11)
        )
        self.progress_label.grid(row=2, column=0, columnspan=2, sticky="w", padx=5, pady=(2, 2))

        # What happens AFTER the trials are exported. Ticked by default: an
        # export whose session.yaml does not know about it, and whose trials
        # have no detected type, is only half an export — every downstream
        # stage reads both.
        post_frame = ctk.CTkFrame(progress_frame, fg_color="transparent")
        post_frame.grid(row=4, column=0, columnspan=2, sticky="w", padx=5, pady=(4, 0))
        self.post_session_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(post_frame,
                        text="After export: update session.yaml",
                        variable=self.post_session_var, font=("Segoe UI", 10),
                        command=self._save_ui_state
                        ).pack(side="left", padx=(0, 14))
        self.post_detect_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(post_frame,
                        text="run movement detection",
                        variable=self.post_detect_var, font=("Segoe UI", 10),
                        command=self._save_ui_state
                        ).pack(side="left")

        # Export and cancel buttons
        button_frame_bottom = ctk.CTkFrame(progress_frame)
        button_frame_bottom.grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=(8, 0))
        button_frame_bottom.grid_columnconfigure(0, weight=1)

        self.export_button = ctk.CTkButton(
            button_frame_bottom,
            text="Export Batch",
            font=("Segoe UI", 10),
            command=self._on_export_batch,
        )
        self.export_button.grid(row=0, column=0, sticky="ew", padx=(0, 5), pady=5)

        self.cancel_button = ctk.CTkButton(
            button_frame_bottom,
            text="Cancel",
            font=("Segoe UI", 10),
            state="disabled",
            command=self._on_cancel,
        )
        self.cancel_button.grid(row=0, column=1, sticky="ew", padx=(0, 0), pady=5)

    def _progress(self, text):
        """One status line, and the same line into the console.

        The progress BAR is gone; the console is now where progress is read,
        so every message that used to only tint a label must reach it."""
        try:
            self.progress_label.configure(text=text)
        except Exception:                                      # noqa: BLE001
            pass
        logger.info(str(text))
        if self.status_callback:
            try:
                self.status_callback(str(text))
            except Exception:                                  # noqa: BLE001
                pass

    #: Where the exported trials belong, relative to the session folder. A
    #: session is laid out <session>/1_c3dfiles, 2_experimental, 3_iterations —
    #: exporting the C3Ds back INTO 1_c3dfiles (the old default: "same folder
    #: as the source") mixes inputs with outputs in the one folder the next
    #: stage globs for raw C3Ds.
    _DEST_SIBLINGS = ("2_experimental", "experimental")

    def _default_dest_for(self, source):
        """The folder an export from ``source`` should land in.

        Only ever returns a folder that EXISTS — guessing a name and creating
        it would quietly scatter half-sessions across the project. Falls back
        to the source folder, which is what it always did."""
        try:
            src = Path(source)
            if not src.is_dir():
                return None
            # source is <session>/1_c3dfiles → look at its siblings
            for name in self._DEST_SIBLINGS:
                cand = src.parent / name
                if cand.is_dir():
                    return cand
            # source IS the session folder → look inside it
            for name in self._DEST_SIBLINGS:
                cand = src / name
                if cand.is_dir():
                    return cand
            # anything else ending in _experimental, in either place
            for base in (src.parent, src):
                for cand in sorted(base.glob("*experimental*")):
                    if cand.is_dir():
                        return cand
        except Exception:                                      # noqa: BLE001
            pass
        return None

    def _validate_source_folder(self):
        """Validate source folder path."""
        path_str = self.source_folder_var.get().strip()
        if not path_str:
            self.source_error.configure(text="")
            self.source_folder = None
            return

        try:
            path = Path(path_str)
            if path.exists() and path.is_dir():
                self.source_folder = path
                self.source_error.configure(text="")

                # Auto-fill the destination, but only while it is still
                # untouched or still pointing at the source — never overwrite a
                # path that was typed or browsed to on purpose.
                # Compared as PATHS, not strings: the two boxes disagree on
                # slash direction (one is typed, one comes from a picker), so
                # string equality reported "the user chose this" for a dest the
                # tab had filled in itself.
                dest_str = self.dest_entry.get().strip()
                if (not dest_str) or _same_path(dest_str, path) or \
                        _same_path(dest_str, self._auto_dest):
                    auto = self._default_dest_for(path) or path
                    self._auto_dest = str(auto)
                    self.dest_entry.delete(0, "end")
                    self.dest_entry.insert(0, str(auto))
                    self._validate_dest_folder()

                self._scan_for_c3d_files()
            else:
                self.source_folder = None
                self.source_error.configure(text="❌ Directory not found")
        except Exception as e:
            self.source_folder = None
            self.source_error.configure(text="❌ Invalid path")

    def _validate_dest_folder(self):
        """Validate destination folder path."""
        path_str = self.dest_entry.get().strip()
        if not path_str:
            self.dest_error.configure(text="")
            self.dest_folder = None
            return

        try:
            path = Path(path_str)
            if path.exists() and path.is_dir():
                self.dest_folder = path
                self.dest_error.configure(text="")
            else:
                self.dest_folder = None
                self.dest_error.configure(text="❌ Directory not found")
        except Exception as e:
            self.dest_folder = None
            self.dest_error.configure(text="❌ Invalid path")

    def _select_source_folder(self):
        """Select source folder with C3D files."""
        try:
            import tkinter.filedialog as filedialog
            folder = filedialog.askdirectory(
                title="Select source folder with C3D files",
                initialdir=self._start_dir("source"))
            if folder:
                self.source_entry.delete(0, "end")
                self.source_entry.insert(0, folder)
                self._validate_source_folder()
                self.gui_settings.remember_path("paths.last_c3d_source", folder)
                self._save_ui_state()
        except Exception as e:
            logger.error(f"Error selecting source folder: {str(e)}")

    def _select_dest_folder(self):
        """Select destination folder for exports."""
        try:
            import tkinter.filedialog as filedialog
            folder = filedialog.askdirectory(
                title="Select destination folder",
                initialdir=self._start_dir("dest"))
            if folder:
                self.dest_entry.delete(0, "end")
                self.dest_entry.insert(0, folder)
                self._validate_dest_folder()
                self.gui_settings.remember_path("paths.last_c3d_dest", folder)
                self._save_ui_state()
        except Exception as e:
            logger.error(f"Error selecting destination folder: {str(e)}")

    def _scan_for_c3d_files(self):
        """Scan source folder for C3D files."""
        try:
            if not self.source_folder or not self.source_folder.exists():
                return

            self.c3d_files = sorted(list(self.source_folder.glob("*.c3d")))
            self.selected_files = [True] * len(self.c3d_files)

            # Clear existing checkboxes
            for checkbox in self.file_checkboxes:
                checkbox.destroy()
            self.file_checkboxes.clear()
            self.file_vars.clear()

            # Create checkboxes for each file
            for i, c3d_file in enumerate(self.c3d_files):
                file_size = c3d_file.stat().st_size / (1024 * 1024)  # MB
                var = ctk.BooleanVar(value=True)
                self.file_vars.append(var)

                checkbox = ctk.CTkCheckBox(
                    self.files_scroll_frame,
                    text=f"{c3d_file.name}  ({file_size:.1f} MB)",
                    variable=var,
                    font=("Segoe UI", 9),
                    command=lambda idx=i, v=var: self._on_file_toggle(idx, v),
                )
                checkbox.pack(anchor="w", padx=5, pady=2)
                self.file_checkboxes.append(checkbox)

            self.file_count_label.configure(text=str(len(self.c3d_files)))
            logger.debug(f"Found {len(self.c3d_files)} C3D files")

        except Exception as e:
            logger.error(f"Error scanning for C3D files: {str(e)}")

    def _on_file_toggle(self, index: int, var: ctk.BooleanVar):
        """Handle file checkbox toggle."""
        if index < len(self.selected_files):
            self.selected_files[index] = var.get()

    def _select_all_files(self):
        """Select all C3D files."""
        for var in self.file_vars:
            var.set(True)
        self.selected_files = [True] * len(self.c3d_files)

    def _deselect_all_files(self):
        """Deselect all C3D files."""
        for var in self.file_vars:
            var.set(False)
        self.selected_files = [False] * len(self.c3d_files)

    def _populate_marker_checkboxes(self, left_markers, right_markers, checked_left=None, checked_right=None):
        """Populate marker checkboxes in scrollable frames.

        Args:
            left_markers: List of left foot marker names to display
            right_markers: List of right foot marker names to display
            checked_left: Set of left marker names that should be checked (default: None = all unchecked)
            checked_right: Set of right marker names that should be checked (default: None = all unchecked)
        """
        if checked_left is None:
            checked_left = set()
        if checked_right is None:
            checked_right = set()

        # What you ticked last time wins over the auto-detected guess, but only
        # for markers this capture actually has. Auto-detection is a heuristic
        # over name patterns; a deliberate choice is not, and re-making it on
        # every launch was the complaint.
        remembered_l = self._remembered_selection("left_markers") & set(left_markers)
        remembered_r = self._remembered_selection("right_markers") & set(right_markers)
        if remembered_l:
            checked_left = remembered_l
        if remembered_r:
            checked_right = remembered_r

        # Clear existing checkboxes
        for checkbox in self.left_marker_checkboxes:
            checkbox.destroy()
        self.left_marker_checkboxes.clear()
        self.left_marker_vars.clear()

        for checkbox in self.right_marker_checkboxes:
            checkbox.destroy()
        self.right_marker_checkboxes.clear()
        self.right_marker_vars.clear()

        # Create left foot checkboxes
        for marker in sorted(left_markers):
            # Check if marker matches any of the left foot patterns
            should_check = marker in checked_left
            var = ctk.BooleanVar(value=should_check)
            self.left_marker_vars[marker] = var
            checkbox = ctk.CTkCheckBox(
                self.left_markers_scroll,
                text=marker,
                variable=var,
                font=("Segoe UI", 9),
                command=self._save_ui_state,
            )
            checkbox.pack(anchor="w", padx=5, pady=2)
            self.left_marker_checkboxes.append(checkbox)

        # Create right foot checkboxes
        for marker in sorted(right_markers):
            # Check if marker matches any of the right foot patterns
            should_check = marker in checked_right
            var = ctk.BooleanVar(value=should_check)
            self.right_marker_vars[marker] = var
            checkbox = ctk.CTkCheckBox(
                self.right_markers_scroll,
                text=marker,
                variable=var,
                font=("Segoe UI", 9),
                command=self._save_ui_state,
            )
            checkbox.pack(anchor="w", padx=5, pady=2)
            self.right_marker_checkboxes.append(checkbox)

    def _label_patterns(self):
        """The Label field as a list of substrings — ";"-separated so one rig's
        "Voltage" channels and another's "EMG" channels can both be caught in
        one session (e.g. ``voltage;emg;sensor``). Empty list = no filter."""
        return [p.strip().lower()
                for p in str(self.emg_label_var.get()).split(";")
                if p.strip()]

    def _filter_emg_channels(self) -> None:
        """Re-populate the EMG channel list from the Label field.

        A channel is shown when its name contains ANY of the ";"-separated
        patterns (case-insensitive). Empty label = every detected channel.
        """
        patterns = self._label_patterns()
        if patterns:
            filtered = [ch for ch in self._all_analog_channels
                        if any(p in ch.lower() for p in patterns)]
        else:
            filtered = list(self._all_analog_channels)
        self._populate_emg_channels(filtered)
        logger.info(f"EMG filter {patterns}: "
                    f"{len(filtered)}/{len(self._all_analog_channels)} channels shown")

    def _select_all_emg(self):
        """Select all EMG channels."""
        for var in self.emg_channel_vars.values():
            var.set(True)

    def _deselect_all_emg(self):
        """Deselect all EMG channels."""
        for var in self.emg_channel_vars.values():
            var.set(False)

    def _select_all_left_markers(self):
        """Select all left foot markers."""
        for var in self.left_marker_vars.values():
            var.set(True)

    def _deselect_all_left_markers(self):
        """Deselect all left foot markers."""
        for var in self.left_marker_vars.values():
            var.set(False)

    def _select_all_right_markers(self):
        """Select all right foot markers."""
        for var in self.right_marker_vars.values():
            var.set(True)

    def _deselect_all_right_markers(self):
        """Deselect all right foot markers."""
        for var in self.right_marker_vars.values():
            var.set(False)

    def _populate_emg_channels(self, channels: List[str]):
        """Populate EMG channel checkboxes."""
        # Clear existing checkboxes
        for checkbox in self.emg_channel_checkboxes:
            checkbox.destroy()
        self.emg_channel_checkboxes.clear()
        self.emg_channel_vars.clear()

        # Default is everything ticked; a remembered selection narrows it, but
        # only when at least one of the remembered channels is present — a
        # remembered set from a different rig must not leave the list empty.
        remembered = self._remembered_selection("emg_channels") & set(channels)

        for channel in sorted(channels):
            var = ctk.BooleanVar(value=(channel in remembered) if remembered else True)
            self.emg_channel_vars[channel] = var
            checkbox = ctk.CTkCheckBox(
                self.emg_channels_scroll,
                text=channel,
                variable=var,
                font=("Segoe UI", 9),
                command=self._on_emg_channel_toggle,
            )
            checkbox.pack(anchor="w", padx=5, pady=2)
            self.emg_channel_checkboxes.append(checkbox)

        # Keep the live-preview channel dropdown in sync with available channels
        self._refresh_preview_channel_menu(sorted(channels))
        self._on_emg_channel_toggle()

    def _on_emg_channel_toggle(self):
        """Channel selection changed: remember it, and keep the per-muscle
        scale rows in step with what is actually selected."""
        try:
            if (getattr(self, "emg_scale_enabled_var", None) is not None
                    and self.emg_scale_enabled_var.get()
                    and self.emg_scale_mode_var.get() == "per muscle"):
                self._rebuild_scale_rows()
            self._save_ui_state()
        except Exception as exc:                               # noqa: BLE001
            logger.debug(f"EMG channel toggle: {exc}")

    def _refresh_preview_channel_menu(self, channels):
        """Populate the filter-preview channel dropdown with the given channels."""
        if not hasattr(self, "preview_channel_menu"):
            return
        values = list(channels) if channels else ["(no channels)"]
        try:
            self.preview_channel_menu.configure(values=values)
            current = self.preview_channel_var.get()
            if current not in values:
                self.preview_channel_var.set(values[0])
        except Exception as e:
            logger.debug(f"Could not refresh preview channel menu: {e}")

    def _get_marker_remove_list(self):
        """Parse the ';'-separated 'Remove from marker names' input into a list.

        Returns a list of non-empty substrings to strip from marker labels.
        """
        raw = self.marker_remove_var.get() if hasattr(self, "marker_remove_var") else ""
        return [s.strip() for s in raw.split(";") if s.strip()]

    def _clean_marker_name(self, name: str) -> str:
        """Remove user-specified substrings from a marker name (for display)."""
        for sub in self._get_marker_remove_list():
            name = name.replace(sub, "")
        return name.strip()

    def _get_selected_markers(self):
        """Get list of selected left and right markers."""
        selected_left = [marker for marker, var in self.left_marker_vars.items() if var.get()]
        selected_right = [marker for marker, var in self.right_marker_vars.items() if var.get()]
        return selected_left, selected_right

    def _get_selected_emg_channels(self):
        """Get list of selected EMG channels."""
        return [channel for channel, var in self.emg_channel_vars.items() if var.get()]

    def _update_markers_from_c3d(self):
        """Scan selected C3D files and update marker/EMG checkboxes with detected data.

        Finds ALL labeled markers across all trials and warns about missing markers per trial.
        """
        try:
            if not self.c3d_files:
                logger.warning("No C3D files found to scan for markers")
                return

            # Get selected files
            selected_c3d_files = [f for f, selected in zip(self.c3d_files, self.selected_files) if selected]
            if not selected_c3d_files:
                logger.warning("No C3D files selected for marker detection")
                return

            # Scan for markers and EMG channels across all selected files
            all_markers = set()
            emg_channels = set()
            trial_markers = {}  # Track markers per file for warnings

            try:
                import c3d
                HAS_C3D = True
            except ImportError:
                HAS_C3D = False
                logger.warning("c3d module not available, cannot detect markers")
                return

            # EMG label pattern for detection
            emg_pattern = self.emg_label_var.get().strip().lower()

            logger.info(f"\n{'='*80}")
            logger.info("MARKER DETECTION REPORT")
            logger.info(f"{'='*80}")
            logger.info(f"Scanning {len(selected_c3d_files)} trials for labeled markers...\n")

            # Scan ALL selected files to find all labeled markers AND numbered markers
            for c3d_file in selected_c3d_files:
                file_markers = set()
                try:
                    with open(str(c3d_file), 'rb') as f:
                        reader = c3d.Reader(f)

                        # Extract analog frame rate from first file
                        if self.analog_fps is None and hasattr(reader, 'analog_rate'):
                            self.analog_fps = reader.analog_rate
                            self.fps_label.configure(text=f"FPS: {self.analog_fps}")
                            logger.info(f"Analog frame rate (EMG): {self.analog_fps} Hz")

                        # Detect LABELED markers first
                        found_labeled = False
                        if hasattr(reader, 'point_labels'):
                            for label in reader.point_labels:
                                if label and label.strip():
                                    # Strip user-specified substrings for display
                                    marker = self._clean_marker_name(label.strip())
                                    if not marker:
                                        continue
                                    all_markers.add(marker)
                                    file_markers.add(marker)
                                    found_labeled = True

                        # If no labeled markers found, use numbered markers (*1, *2, etc.)
                        if not found_labeled:
                            # Use point count to generate numbered markers
                            if hasattr(reader, 'point_used'):
                                num_markers = reader.point_used
                                for i in range(1, num_markers + 1):
                                    marker = f"*{i}"
                                    all_markers.add(marker)
                                    file_markers.add(marker)
                                logger.info(f"No labeled markers found in {c3d_file.name}, using {num_markers} numbered markers")

                        # Detect analog channels — collect ALL, filter later
                        if hasattr(reader, 'analog_labels'):
                            for label in reader.analog_labels:
                                if label and label.strip():
                                    channel_label = label.strip()
                                    emg_channels.add(channel_label)  # store all
                        else:
                            logger.warning(f"No analog_labels attribute in C3D file {c3d_file.name}")

                    trial_markers[c3d_file.name] = file_markers

                except Exception as e:
                    logger.debug(f"Could not read markers from {c3d_file.name}: {e}")
                    trial_markers[c3d_file.name] = set()
                    continue

            # Log marker report per trial with warnings
            if all_markers:
                sorted_markers = sorted(list(all_markers))
                # Store all detected markers for export use
                self.all_detected_markers = all_markers
                logger.info(f"Total unique labeled markers found: {len(all_markers)}")
                logger.info(f"Markers: {sorted_markers}\n")

                # Check each trial for missing markers
                logger.info(f"{'TRIAL MARKER SUMMARY':^80}")
                logger.info(f"{'-'*80}")

                for trial_name, file_markers in trial_markers.items():
                    missing = all_markers - file_markers
                    if missing:
                        missing_list = sorted(list(missing))
                        logger.warning(f"[WARN] {trial_name}: Missing {len(missing)} markers")
                        logger.warning(f"        Missing: {missing_list}")
                    else:
                        logger.info(f"[OK] {trial_name}: All {len(file_markers)} markers present")

                logger.info(f"{'-'*80}\n")

                # Separate markers into foot markers and others
                left_foot_markers = set()
                right_foot_markers = set()

                # Match markers that *contain* a foot pattern (case-insensitive),
                # so variations like "Athlete_20:RHEE" or "R_Heel_1" are caught,
                # not only labels exactly equal to a pattern.
                left_patterns = [p.lower() for p in LEFT_FOOT_MARKER_PATTERNS]
                right_patterns = [p.lower() for p in RIGHT_FOOT_MARKER_PATTERNS]
                for marker in sorted_markers:
                    m_low = marker.lower()
                    if any(p in m_low for p in left_patterns):
                        left_foot_markers.add(marker)
                    if any(p in m_low for p in right_patterns):
                        right_foot_markers.add(marker)

                # Show all markers in both columns, but only auto-check foot markers
                self._populate_marker_checkboxes(
                    sorted_markers,
                    sorted_markers,
                    checked_left=left_foot_markers,
                    checked_right=right_foot_markers
                )
                logger.info(f"Marker checkboxes updated: {len(all_markers)} total markers available")
                logger.info(f"Left foot markers auto-checked: {sorted(left_foot_markers)}")
                logger.info(f"Right foot markers auto-checked: {sorted(right_foot_markers)}")
                logger.info(f"{'='*80}\n")
            else:
                logger.warning("No markers detected in selected C3D files")

            # Store all analog channels and show the filtered subset
            self._all_analog_channels = sorted(emg_channels)
            if self._all_analog_channels:
                logger.info(f"Analog channels found: {len(self._all_analog_channels)}")
                self._filter_emg_channels()  # apply current label filter
            else:
                logger.info("No analog channels detected in selected C3D files")

        except Exception as e:
            logger.error(f"Error updating markers from C3D files: {e}")
            logger.debug(f"Exception details: {e}", exc_info=True)

    # ========================================================================
    # EMG LIVE FILTER PREVIEW  +  MAX-EMG CALCULATION
    # ========================================================================
    def _get_emg_filter_params(self):
        """Return (highpass, lowpass, notch) cutoffs in Hz from the GUI fields.

        In this UI the 'High (Hz)' field is the band-pass *low* cutoff
        (high-pass), and 'Low (Hz)' is the band-pass *high* cutoff (low-pass),
        matching the existing export filter semantics.
        """
        def _f(var, default):
            try:
                return float(str(var.get()).strip())
            except Exception:
                return float(default)
        highpass = _f(self.emg_highpass_var, BATCH_C3D_EMG_HIGHPASS_DEFAULT)
        lowpass = _f(self.emg_lowpass_var, BATCH_C3D_EMG_LOWPASS_DEFAULT)
        notch = _f(self.emg_notch_var, BATCH_C3D_EMG_NOTCH_DEFAULT)
        return highpass, lowpass, notch

    def _compute_emg_envelope(self, sig, fs, highpass, lowpass, notch, env_lp=6.0):
        """Band-pass + notch + rectify + low-pass envelope of a 1-D EMG signal.

        Returns (band, envelope). Falls back gracefully if cutoffs are invalid
        or the signal is too short for filtfilt.
        """
        sig = np.asarray(sig, dtype=float)
        sig = sig[~np.isnan(sig)] if np.isnan(sig).any() else sig
        if sig.size < 10 or fs <= 0:
            return sig, np.abs(sig)
        if not _load_scipy():
            return sig, np.abs(sig)
        sig = sig - np.mean(sig)
        nyq = 0.5 * fs
        out = sig

        # Band-pass (or low-pass only if high-pass cutoff invalid)
        lo = max(highpass, 0.0) / nyq
        hi = min(lowpass, nyq * 0.99) / nyq
        try:
            if 0 < lo < hi < 1.0:
                b, a = _sps.butter(4, [lo, hi], btype='band')
                out = _sps.filtfilt(b, a, out)
            elif 0 < hi < 1.0:
                b, a = _sps.butter(4, hi, btype='low')
                out = _sps.filtfilt(b, a, out)
        except Exception as e:
            logger.debug(f"Bandpass preview failed: {e}")

        # Notch
        if notch and 0 < notch < nyq:
            try:
                b, a = _sps.iirnotch(notch / nyq, Q=30.0)
                out = _sps.filtfilt(b, a, out)
            except Exception as e:
                logger.debug(f"Notch preview failed: {e}")

        band = out
        rect = np.abs(band)
        env = rect
        el = env_lp / nyq
        if 0 < el < 1.0:
            try:
                b, a = _sps.butter(4, el, btype='low')
                env = _sps.filtfilt(b, a, rect)
            except Exception as e:
                logger.debug(f"Envelope preview failed: {e}")
        return band, env

    def _read_c3d_emg(self, c3d_file, wanted=None):
        """Read full-resolution analog signals from a C3D file.

        Args:
            c3d_file: Path to the .c3d file.
            wanted: optional set of channel labels to keep (None = all).

        Returns:
            (data, fs) where data maps channel label -> 1-D numpy array, and
            fs is the analog sampling rate in Hz.
        """
        import warnings as _warnings
        with open(str(c3d_file), 'rb') as f:
            reader = c3d.Reader(f)
            labels = [str(l or "").strip() for l in reader.analog_labels]
            try:
                fs = float(reader.analog_rate)
            except Exception:
                fs = float(getattr(reader, 'point_rate', 1000.0))
            keep_idx = [i for i, lab in enumerate(labels)
                        if (wanted is None or lab in wanted)]
            cols = {labels[i]: [] for i in keep_idx}
            with _warnings.catch_warnings():
                _warnings.filterwarnings('ignore', message='No point data found',
                                         category=UserWarning)
                for _fno, _pts, analog in reader.read_frames():
                    for i in keep_idx:
                        cols[labels[i]].append(np.asarray(analog[i]).ravel())
        data = {lab: (np.concatenate(v) if v else np.array([]))
                for lab, v in cols.items()}
        return data, fs

    def _update_filter_preview(self):
        """Plot raw vs filtered EMG for the first ticked C3D + selected channel."""
        if not (HAS_MPL and HAS_SCIPY and HAS_C3D):
            self._show_preview_message("Live preview needs matplotlib + scipy + c3d installed.")
            return
        selected = [f for f, s in zip(self.c3d_files, self.selected_files) if s]
        if not selected:
            self._show_preview_message("Tick at least one C3D file to preview.")
            return
        ch = self.preview_channel_var.get()
        if not ch or ch == "(no channels)":
            self._show_preview_message("Click 'Update Markers' to load EMG channels first.")
            return

        c3d_file = selected[0]
        try:
            data, fs = self._read_c3d_emg(c3d_file, wanted={ch})
        except Exception as e:
            self._show_preview_message(f"Could not read EMG: {str(e)[:60]}")
            return

        sig = data.get(ch)
        if sig is None or sig.size < 10:
            self._show_preview_message(f"No usable data for channel '{ch}'.")
            return

        highpass, lowpass, notch = self._get_emg_filter_params()
        band, env = self._compute_emg_envelope(sig, fs, highpass, lowpass, notch)
        t = np.arange(sig.size) / fs if fs > 0 else np.arange(sig.size)

        try:
            self._render_preview_plot(c3d_file.name, ch, t, sig, band, env,
                                      fs, highpass, lowpass, notch)
        except Exception as e:
            logger.error(f"Preview plot error: {e}", exc_info=True)
            self._show_preview_message(f"Plot error: {str(e)[:60]}")

    def _show_preview_message(self, msg):
        """Show a placeholder message in the preview area (clears any plot)."""
        if self.preview_canvas is not None:
            try:
                self.preview_canvas.get_tk_widget().destroy()
            except Exception:
                pass
            self.preview_canvas = None
        if self.preview_fig is not None:
            try:
                import matplotlib.pyplot as _plt
                _plt.close(self.preview_fig)
            except Exception:
                pass
            self.preview_fig = None
        try:
            self._preview_placeholder.configure(text=msg)
            self._preview_placeholder.grid(row=0, column=0, sticky="nsew")
        except Exception:
            pass

    def _render_preview_plot(self, fname, ch, t, raw, band, env,
                             fs, highpass, lowpass, notch):
        """Draw the raw vs filtered EMG figure into the preview frame."""
        # Remove placeholder + any previous canvas
        try:
            self._preview_placeholder.grid_forget()
        except Exception:
            pass
        if self.preview_canvas is not None:
            try:
                self.preview_canvas.get_tk_widget().destroy()
            except Exception:
                pass
            self.preview_canvas = None
        if self.preview_fig is not None:
            try:
                import matplotlib.pyplot as _plt
                _plt.close(self.preview_fig)
            except Exception:
                pass

        bg = "#2b2b2b"
        fg = "#dddddd"
        _load_mpl()
        fig = Figure(figsize=(5, 3), dpi=100, facecolor=bg)
        self.preview_fig = fig

        ax1 = fig.add_subplot(2, 1, 1)
        ax2 = fig.add_subplot(2, 1, 2, sharex=ax1)
        for ax in (ax1, ax2):
            ax.set_facecolor(bg)
            ax.tick_params(colors=fg, labelsize=7)
            for spine in ax.spines.values():
                spine.set_color("#555555")
            ax.grid(True, alpha=0.2)

        ax1.plot(t, raw, color="#5da9e9", linewidth=0.6)
        ax1.set_title(f"{ch}  —  {fname}", color=fg, fontsize=8, pad=3)
        ax1.set_ylabel("Raw", color=fg, fontsize=7)

        ax2.plot(t, band, color="#888888", linewidth=0.5, alpha=0.6, label="band-pass")
        ax2.plot(t, env, color="#ff8c42", linewidth=1.2, label="envelope")
        ax2.set_ylabel("Filtered", color=fg, fontsize=7)
        ax2.set_xlabel(
            f"Time (s)   |   {fs:.0f} Hz   band {highpass:g}-{lowpass:g} Hz   notch {notch:g} Hz",
            color=fg, fontsize=7)
        ax2.legend(loc="upper right", fontsize=6, facecolor=bg, edgecolor="#555555",
                   labelcolor=fg)

        fig.tight_layout(pad=0.6)

        self.preview_canvas = FigureCanvasTkAgg(fig, master=self.preview_plot_frame)
        self.preview_canvas.draw()
        self.preview_canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

    def _on_compute_max_emg(self):
        """Compute per-channel max EMG (moving-averaged) across selected trials."""
        if not (HAS_SCIPY and HAS_C3D):
            self._render_max_emg_message("Max EMG needs scipy + c3d installed.")
            return
        selected = [f for f, s in zip(self.c3d_files, self.selected_files) if s]
        if not selected:
            self._render_max_emg_message("Tick at least one C3D file.")
            return
        channels = self._get_selected_emg_channels()
        if not channels:
            self._render_max_emg_message("Select at least one EMG channel.")
            return
        try:
            window = max(1, int(float(self.maxemg_window_var.get())))
        except Exception:
            window = 1

        self.maxemg_button.configure(state="disabled", text="Working…")
        self._render_max_emg_message("Computing…")
        thread = threading.Thread(
            target=self._compute_max_emg_worker,
            args=(list(selected), list(channels), window),
            daemon=True,
        )
        thread.start()

    def _compute_max_emg_worker(self, files, channels, window):
        """Background worker: scan trials, build per-channel max envelope table."""
        results = {}    # channel -> (max_value, trial_name)
        per_trial = {}  # channel -> {trial: peak}  — every trial, not just the winner
        wanted = set(channels)
        try:
            highpass, lowpass, notch = self._get_emg_filter_params()
            for c3d_file in files:
                try:
                    data, fs = self._read_c3d_emg(c3d_file, wanted=wanted)
                except Exception as e:
                    logger.warning(f"Max EMG: could not read {c3d_file.name}: {e}")
                    continue
                for ch in channels:
                    sig = data.get(ch)
                    if sig is None or sig.size < 10:
                        continue
                    _band, env = self._compute_emg_envelope(sig, fs, highpass, lowpass, notch)
                    if window > 1 and env.size >= window:
                        env = np.convolve(env, np.ones(window) / window, mode="valid")
                    if env.size == 0:
                        continue
                    peak = float(np.nanmax(env))
                    per_trial.setdefault(ch, {})[c3d_file.stem] = peak
                    if (ch not in results) or (peak > results[ch][0]):
                        results[ch] = (peak, c3d_file.stem)
            self.max_emg_results = results
            self.max_emg_per_trial = per_trial
            logger.info(f"Max EMG computed for {len(results)} channels "
                        f"across {len(files)} trials (window={window} frames)")
        except Exception as e:
            logger.error(f"Max EMG worker error: {e}", exc_info=True)
        finally:
            # Marshal UI updates back onto the Tk main thread
            try:
                self.after(0, self._render_max_emg_results)
                self.after(0, lambda: self.maxemg_button.configure(
                    state="normal", text="Compute"))
            except Exception:
                self._render_max_emg_results()

    def _set_max_emg_text(self, lines):
        """Replace the table contents. ``lines`` is [(text, tag_or_None)]."""
        try:
            self.maxemg_text.configure(state="normal")
            self.maxemg_text.delete("1.0", "end")
            for text, tag in lines:
                self.maxemg_text.insert("end", text + "\n", tag or ())
            self.maxemg_text.configure(state="disabled")
        except Exception as exc:                               # noqa: BLE001
            logger.debug(f"Max EMG render failed: {exc}")

    def _render_max_emg_message(self, msg):
        """Clear the max-EMG results area and show a single status message."""
        self._set_max_emg_text([(msg, None)])

    def _render_max_emg_results(self):
        """Per-channel max EMG, plus every trial's peak as a % of it.

        The percentage column is the useful one: an absolute millivolt peak
        says nothing on its own, but "this trial reached 96 % of the biggest
        contraction I have for that muscle" tells you immediately whether the
        max is real or whether one artefact is setting the normalisation for
        the whole session. The table is wide by design — it scrolls sideways.
        """
        if not self.max_emg_results:
            self._render_max_emg_message("No results.")
            return

        # Trials in the order they were scanned, so the columns line up with
        # the file list rather than being alphabetised away from it.
        trials = []
        for ch in self.max_emg_per_trial:
            for t in self.max_emg_per_trial[ch]:
                if t not in trials:
                    trials.append(t)

        w_ch = max([len(str(c)) for c in self.max_emg_results] + [7]) + 2
        w_tr = max([len(t) for t in trials] + [10]) + 2 if trials else 12
        col = max([len(t) for t in trials] + [8]) + 2 if trials else 10

        head = (f"{'Channel':<{w_ch}}{'Max':>12}  {'Best trial':<{w_tr}}"
                + "".join(f"{t:>{col}}" for t in trials))
        lines = [(head, "head"),
                 ("-" * len(head), "head")]

        for ch in sorted(self.max_emg_results):
            peak, best = self.max_emg_results[ch]
            per = self.max_emg_per_trial.get(ch, {})
            cells = ""
            for t in trials:
                v = per.get(t)
                # A dash, not 0.0 %, when a channel is absent from a trial —
                # zero is a measurement, "not recorded here" is not.
                cells += (f"{'-':>{col}}" if v is None or not peak
                          else f"{100.0 * v / peak:>{col - 1}.1f}%")
            lines.append((f"{str(ch):<{w_ch}}{peak:>12.4g}  {best:<{w_tr}}{cells}",
                          None))
        self._set_max_emg_text(lines)

    # ------------------------------------------------------------------
    # EMG scaling on export
    # ------------------------------------------------------------------
    def _on_emg_scale_toggle(self):
        """Show the right control for the chosen mode and remember the choice."""
        try:
            enabled = bool(self.emg_scale_enabled_var.get())
            per_muscle = self.emg_scale_mode_var.get() == "per muscle"
            self.emg_scale_entry.configure(
                state="normal" if enabled and not per_muscle else "disabled")
            self.emg_scale_hint.configure(
                text=("one factor for every selected channel" if not per_muscle
                      else "one factor per channel — blank or 1 means unchanged"))
            if enabled and per_muscle:
                self._rebuild_scale_rows()
                self.emg_scale_per_frame.grid()
            else:
                self.emg_scale_per_frame.grid_remove()
            self._save_ui_state()
        except Exception as exc:                               # noqa: BLE001
            logger.debug(f"EMG scale toggle failed: {exc}")

    def _rebuild_scale_rows(self):
        """One factor entry per selected EMG channel, keeping typed values."""
        for child in list(self.emg_scale_per_frame.winfo_children()):
            try:
                child.destroy()
            except Exception:                                  # noqa: BLE001
                pass
        stored = self.gui_settings.get("c3d_export.emg_scale_per_channel", {}) or {}
        kept = {ch: v.get() for ch, v in self._emg_scale_entries.items()}
        self._emg_scale_entries = {}
        channels = self._get_selected_emg_channels()
        if not channels:
            ctk.CTkLabel(self.emg_scale_per_frame,
                         text="Select EMG channels first.",
                         font=("Segoe UI", 10), text_color="#8a8a8a"
                         ).grid(row=0, column=0, sticky="w", padx=6, pady=4)
            return
        for i, ch in enumerate(channels):
            ctk.CTkLabel(self.emg_scale_per_frame, text=ch, font=("Segoe UI", 10),
                         anchor="w").grid(row=i, column=0, sticky="w",
                                          padx=(6, 8), pady=2)
            var = ctk.StringVar(value=str(kept.get(ch, stored.get(ch, "1.0"))))
            entry = ctk.CTkEntry(self.emg_scale_per_frame, textvariable=var,
                                 width=90, height=26, font=("Segoe UI", 10))
            entry.grid(row=i, column=1, sticky="w", pady=2)
            entry.bind("<FocusOut>", lambda _e: self._save_ui_state())
            self._emg_scale_entries[ch] = var

    def _fill_scales_from_max_emg(self):
        """Set each channel's factor to 1 / its max, i.e. normalise every muscle
        to its own session peak. Needs Compute to have been run first."""
        if not self.max_emg_results:
            self._render_max_emg_message("Run Compute first — no max EMG yet.")
            return
        self.emg_scale_enabled_var.set(True)
        self.emg_scale_mode_var.set("per muscle")
        self._on_emg_scale_toggle()
        for ch, var in self._emg_scale_entries.items():
            peak = (self.max_emg_results.get(ch) or (0.0, ""))[0]
            var.set(f"{1.0 / peak:.6g}" if peak else "1.0")
        self._save_ui_state()

    def _get_emg_scale_factors(self, channels):
        """``{channel: factor}`` for the export, or ``{}`` when scaling is off.

        A blank, zero or unparseable entry means 1.0 — a typo must not silently
        wipe a channel to zeros in an exported file."""
        try:
            if not self.emg_scale_enabled_var.get():
                return {}
        except Exception:                                      # noqa: BLE001
            return {}

        def _f(text, default=1.0):
            try:
                v = float(str(text).strip())
                return v if v != 0 else default
            except (TypeError, ValueError):
                return default

        if self.emg_scale_mode_var.get() == "per muscle":
            return {ch: _f(self._emg_scale_entries[ch].get())
                    for ch in channels if ch in self._emg_scale_entries}
        factor = _f(self.emg_scale_value_var.get())
        return {ch: factor for ch in channels}

    # ------------------------------------------------------------------
    # Writing the filtered EMG
    # ------------------------------------------------------------------
    @staticmethod
    def _read_mot(path):
        """``(header_lines, column_names, ndarray)`` from a .mot/.sto."""
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
        end = next((i for i, x in enumerate(lines)
                    if x.strip().lower() == "endheader"), None)
        if end is None:
            raise ValueError(f"{Path(path).name}: no endheader")
        cols = [c.strip() for c in lines[end + 1].split("\t") if c.strip()]
        rows = []
        for ln in lines[end + 2:]:
            f = [x for x in ln.split("\t") if x.strip()]
            if len(f) != len(cols):
                continue
            try:
                rows.append([float(x) for x in f])
            except ValueError:
                continue
        return lines[:end + 1], cols, np.asarray(rows, dtype=float)

    @staticmethod
    def _write_mot(path, name, cols, data):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"{name}\nversion=1\nnRows={data.shape[0]}\n"
                     f"nColumns={data.shape[1]}\ninDegrees=no\nendheader\n")
            fh.write("\t".join(cols) + "\n")
            for row in data:
                fh.write("\t".join(f"{v:.8f}" for v in row) + "\n")

    @staticmethod
    def _match_channel(column, channels):
        """The selected channel a .mot column corresponds to, or None.

        `export_emg` does not always keep the c3d's analog label verbatim, so
        an exact match is tried first, then case-insensitively, then either
        name containing the other. Without this the scale factors would look
        applied and quietly do nothing."""
        c = str(column).strip()
        for ch in channels:
            if c == ch:
                return ch
        low = c.lower()
        for ch in channels:
            if low == str(ch).strip().lower():
                return ch
        for ch in channels:
            cl = str(ch).strip().lower()
            if cl and (cl in low or low in cl):
                return ch
        return None

    def _write_filtered_emg(self, src, dst, channels):
        """Filter (and optionally scale) ``src`` into ``dst``.

        The maths is `_compute_emg_envelope` — the SAME function that draws the
        preview — so what is written is what you were shown: band-pass, notch,
        rectify, low-pass envelope. Anything that cannot be filtered is copied
        through unchanged rather than dropped, so a bad channel costs you that
        channel and not the file.
        """
        header, cols, data = self._read_mot(src)
        if data.size == 0 or len(cols) < 2:
            shutil.copy(str(src), str(dst))
            logger.warning(f"{Path(src).name}: nothing to filter, copied as-is")
            return dst

        time_idx = next((i for i, c in enumerate(cols)
                         if str(c).strip().lower() == "time"), 0)
        t = data[:, time_idx]
        fs = 0.0
        if t.size > 1:
            dt = float(np.median(np.diff(t)))
            fs = 1.0 / dt if dt > 0 else 0.0
        highpass, lowpass, notch = self._get_emg_filter_params()
        scales = self._get_emg_scale_factors(channels)

        out = data.copy()
        n_filtered, n_scaled = 0, 0
        for i, col in enumerate(cols):
            if i == time_idx:
                continue
            sig = np.asarray(data[:, i], dtype=float)
            # NaNs are zeroed rather than dropped: _compute_emg_envelope drops
            # them, which would return a shorter array than the time column and
            # silently misalign every sample after the first gap.
            sig = np.nan_to_num(sig, nan=0.0, posinf=0.0, neginf=0.0)
            try:
                _band, env = self._compute_emg_envelope(sig, fs, highpass,
                                                        lowpass, notch)
                if env.size == sig.size:
                    out[:, i] = env
                    n_filtered += 1
                else:
                    logger.debug(f"{col}: envelope length mismatch, left raw")
            except Exception as exc:                           # noqa: BLE001
                logger.debug(f"{col}: filter failed ({exc}), left raw")
            match = self._match_channel(col, scales.keys()) if scales else None
            if match is not None:
                out[:, i] *= float(scales[match])
                n_scaled += 1

        self._write_mot(dst, Path(dst).stem, cols, out)
        msg = (f"[OK] emg_filtered.mot — {n_filtered} channel(s) filtered "
               f"({highpass:g}-{lowpass:g} Hz, notch {notch:g} Hz"
               f"{f', {n_scaled} scaled' if n_scaled else ''})")
        print(msg)
        logger.info(msg)
        return dst

    def _on_export_batch(self):
        """Start batch export."""
        try:
            # Validate selections
            if not self.source_folder or not self.source_folder.exists():
                self._progress("Error: Source folder not selected")
                return

            if not self.dest_folder or not self.dest_folder.exists():
                self._progress("Error: Destination folder not selected")
                return

            selected_count = sum(self.selected_files)
            if selected_count == 0:
                self._progress("Error: No files selected")
                return

            # Check that at least one marker is selected
            selected_left, selected_right = self._get_selected_markers()
            if not selected_left or not selected_right:
                self._progress("Error: Select at least one left and right foot marker")
                return

            # Start export in background thread
            self.is_processing = True
            self.export_button.configure(state="disabled")
            self.cancel_button.configure(state="normal")

            export_thread = threading.Thread(
                target=self._export_batch_worker,
                args=(selected_count,)
            )
            export_thread.daemon = True
            export_thread.start()

        except Exception as e:
            logger.error(f"Error starting batch export: {str(e)}")
            self._progress(f"Error: {str(e)[:40]}")

    def _export_batch_worker(self, total_selected: int):
        """Worker thread for batch export."""
        try:
            # Snapshot the form as it was when Export was pressed, so the next
            # launch opens on the settings that produced the last export.
            self._save_ui_state()
            self.total_files = total_selected
            self.current_progress = 0

            # Get selected markers and EMG channels for logging
            selected_left, selected_right = self._get_selected_markers()
            selected_emg = self._get_selected_emg_channels()

            # Only log to file, not to console
            logger.info(f"Batch export started - Left markers: {selected_left}, Right: {selected_right}")
            logger.info(f"EMG channels ({len(selected_emg)}): {selected_emg}")

            # Process each selected file
            for i, (c3d_file, is_selected) in enumerate(zip(self.c3d_files, self.selected_files)):
                if not self.is_processing:
                    break

                if not is_selected:
                    continue

                self.current_progress += 1
                progress_pct = (self.current_progress / self.total_files) * 100

                # Update progress display
                self.progress_bar.set(progress_pct / 100.0)
                self._progress(f"Processing {c3d_file.name} ({self.current_progress}/{self.total_files})"
                )

                # Create trial subfolder with just the C3D filename (no trial prefix)
                trial_folder = self.dest_folder / c3d_file.stem
                trial_folder.mkdir(parents=True, exist_ok=True)

                # Export C3D file to trial folder
                self._export_single_c3d(
                    c3d_file,
                    trial_folder,
                    selected_left,
                    selected_right,
                    selected_emg
                )

                self.progress_bar.set(progress_pct / 100.0)

            if self.is_processing:
                self._progress(f"[OK] Completed: {self.current_progress} files exported"
                )
                logger.info(f"Batch export completed: {self.current_progress} files")
                # Same worker thread, on purpose: session.yaml and detection
                # describe the files just written, so they run after the last
                # trial and before the buttons re-enable — an export the user
                # immediately acts on should already be described.
                self._post_export_session_update()
            else:
                self._progress("Cancelled by user")

        except Exception as e:
            logger.error(f"Error in batch export worker: {str(e)}")
            self._progress(f"Error: {str(e)[:40]}")

        finally:
            self.is_processing = False
            self.export_button.configure(state="normal")
            self.cancel_button.configure(state="disabled")

    # ------------------------------------------------------------------
    # After the export: session.yaml + movement detection
    # ------------------------------------------------------------------
    def _session_root_for_dest(self):
        """The session folder the export landed in, or None.

        The 2.x layout is ``<session>/{1_c3dfiles, 2_experimental,
        3_iterations, session.yaml}`` and trials are exported into
        ``2_experimental`` — so when the destination is (or contains) an
        experimental folder, the session is right there. An arbitrary
        destination outside any session resolves to None, and the post-step
        says so instead of scaffolding a session.yaml in a random folder.
        """
        dest = Path(self.dest_folder) if self.dest_folder else None
        if not dest:
            return None
        if dest.name.lower() in ("2_experimental", "experimental"):
            return dest.parent
        for cand in (dest, dest.parent):
            if (cand / "session.yaml").exists():
                return cand
        for sub in ("2_experimental", "experimental"):
            if (dest / sub).is_dir():
                return dest
        return None

    def _post_export_session_update(self):
        """Make the export self-describing: session.yaml knows the filter that
        produced it, and every trial gets a detected movement type.

        Everything here is guarded per step — the trials on disk are already
        exported and correct, so a failure in the bookkeeping must degrade to
        a message, never to a failed export.
        """
        want_yaml = bool(getattr(self, "post_session_var", None)
                         and self.post_session_var.get())
        want_detect = bool(getattr(self, "post_detect_var", None)
                           and self.post_detect_var.get())
        if not (want_yaml or want_detect):
            return

        root = self._session_root_for_dest()
        if root is None:
            msg = ("[INFO] destination is not inside a bioscout session — "
                   "skipped session.yaml/detection (export itself is complete)")
            print(msg)
            logger.info(msg)
            return

        if want_yaml:
            try:
                self._progress("Updating session.yaml…")
            except Exception:                                  # noqa: BLE001
                pass
            try:
                if not (root / "session.yaml").exists():
                    # scaffold_session_yaml builds the trial list from the
                    # session's own c3ds — the one blessed way to create the
                    # file (utils/session.py). It returns None when it cannot.
                    from utils.session import scaffold_session_yaml
                    made = scaffold_session_yaml(str(root))
                    if made:
                        print(f"[OK] Created {made}")
                        logger.info(f"Scaffolded session.yaml at {made}")
                    else:
                        print("[WARN] Could not scaffold session.yaml "
                              f"(no c3ds found under {root})")
                if (root / "session.yaml").exists():
                    # SURGICAL writes only (SessionForm patches value spans) —
                    # a re-dump would wipe the hand-written comments, which is
                    # the File Editor's cardinal rule too.
                    from utils.session_form import SessionForm
                    form = SessionForm(str(root))
                    highpass, lowpass, _notch = self._get_emg_filter_params()
                    # GUI naming vs session.yaml naming: the 'High (Hz)' field
                    # is the band-pass LOW cutoff and 'Low (Hz)' the HIGH one
                    # (see _get_emg_filter_params) — mapped here, once.
                    form.set_emg_filter(bandpass_low=highpass,
                                        bandpass_high=lowpass)
                    if form.dirty():
                        form.save(backup=True)
                        print("[OK] session.yaml: emg_filter updated "
                              f"({highpass:g}-{lowpass:g} Hz)")
                    else:
                        print("[OK] session.yaml already up to date")
            except Exception as e:                             # noqa: BLE001
                print(f"[WARN] session.yaml update failed: {str(e)[:80]}")
                logger.warning(f"session.yaml update failed: {e}")

        if want_detect:
            try:
                self._progress("Detecting movements… (this reads every trial)")
            except Exception:                                  # noqa: BLE001
                pass
            try:
                # numpy-only (movement_detector imports no scipy/OpenSim), so
                # this runs wherever the export itself ran. write_session_yaml
                # backs the old file up before correcting trial types.
                from movement_detector.session import classify_session
                classify_session(str(root), quiet=True, no_plots=False,
                                 write_session_yaml=want_yaml)
                print(f"[OK] Movement detection written under {root}")
                logger.info(f"Movement detection complete for {root}")
            except Exception as e:                             # noqa: BLE001
                print(f"[WARN] movement detection failed: {str(e)[:80]}")
                logger.warning(f"movement detection failed: {e}")

    def _export_single_c3d(self, c3d_file: Path, output_folder: Path, selected_left, selected_right, selected_emg):
        """Export a single C3D file using the same logic as C3D Export tab."""
        try:
            # Extract trial name from output folder or C3D file
            trial_name = output_folder.name if output_folder.name else c3d_file.stem

            # Only log to file, not to console
            logger.debug(f"Exporting {c3d_file.name} to {output_folder}")
            exported_files = []

            # Copy C3D file to output folder so exports happen directly there
            c3d_copy = output_folder / c3d_file.name
            try:
                shutil.copy2(str(c3d_file), str(c3d_copy))
                logger.debug(f"Copied C3D to output folder: {c3d_copy}")
            except Exception as e:
                logger.error(f"Failed to copy C3D file: {e}")
                return

            # Use exportC3D utilities if available
            if not HAS_EXPORTC3D:
                logger.warning("exportC3D module not available - skipping export")
            else:

                # Export markers (now from copy in output folder) with all markers
                try:
                    exportC3D.export_markers(str(c3d_copy), strings_to_remove=self._get_marker_remove_list())
                    marker_file = output_folder / "marker_experimental.trc"
                    if marker_file.exists():
                        # Ensure ALL markers are in the TRC file
                        logger.info(f"Marker completion: detected_markers={len(self.all_detected_markers)}, markers={sorted(self.all_detected_markers)[:5]}...")
                        if False:  # Marker completion disabled - needs proper TRC format handling
                            pass  # self._ensure_all_markers_in_trc(marker_file, self.all_detected_markers)
                            logger.info(f"✓ Markers completed: TRC now has all {len(self.all_detected_markers)} markers")
                        else:
                            logger.warning(f"⚠ No detected markers stored - marker completion skipped")
                        exported_files.append(("Markers", marker_file))
                except Exception as e:
                    logger.error(f"Markers export error: {e}", exc_info=True)

                # Export GRF (now from copy in output folder)
                try:
                    exportC3D.export_grf(str(c3d_copy))
                    grf_file = output_folder / "grf.mot"
                    if grf_file.exists():
                        exported_files.append(("GRF", grf_file))
                        self._create_grf_xml(output_folder)
                except Exception as e:
                    logger.error(f"GRF export error: {e}")

                # Export EMG (now from copy in output folder)
                try:
                    if selected_emg:
                        # The Label field's ";"-separated patterns drive the
                        # export directly. Deriving a single pattern from the
                        # first selected channel (the old behaviour, kept as
                        # the fallback for an empty label) could not represent
                        # two naming schemes in one capture.
                        emg_patterns = self._label_patterns() or \
                            [selected_emg[0].split('.')[0].split('_')[0]]
                        logger.debug(f"Using EMG pattern: {emg_patterns} from selected channels: {selected_emg[:3]}...")
                        exportC3D.export_emg(str(c3d_copy), emg_strings_list=emg_patterns)

                        # Check for both emg.mot and analog.csv created by export_emg
                        emg_file = output_folder / "emg.mot"
                        analog_file = output_folder / "analog.csv"

                        # Analog.csv should already be in output folder now
                        if analog_file.exists():
                            try:
                                print(f"[OK] Exported analog.csv ({analog_file.stat().st_size / 1024:.2f} KB)")
                                logger.info(f"[OK] Exported analog.csv")
                                exported_files.append(("Analog CSV", analog_file))
                            except Exception as e:
                                print(f"[WARN] Could not access analog.csv: {str(e)[:60]}")
                                logger.warning(f"Could not access analog.csv: {e}")

                        # EMG file should already be in output folder now
                        if emg_file.exists():
                            print(f"[OK] EMG exported ({len(selected_emg)} channels)")
                            logger.info(f"[OK] EMG exported ({len(selected_emg)} channels)")
                            exported_files.append(("EMG", emg_file))
                        else:
                            print(f"[WARN] EMG file not created by export_emg")
                            logger.warning("EMG file (emg.mot) not created by exportC3D")
                    else:
                        print(f"[INFO] No EMG channels selected, skipping EMG export")
                        logger.info("No EMG channels selected")
                except Exception as e:
                    print(f"[FAIL] EMG export error: {str(e)[:60]}")
                    logger.error(f"EMG export error: {e}")

                # Generate emg_filtered.mot — ACTUALLY FILTERED.
                #
                # This used to be `shutil.copy(emg.mot, emg_filtered.mot)`: a
                # byte-for-byte copy under a name that promises otherwise. The
                # Low/High/Notch fields above only ever drove the on-screen
                # preview, so every exported "filtered" EMG in every session
                # was raw. Nothing downstream could tell.
                try:
                    emg_file = output_folder / "emg.mot"
                    if emg_file.exists():
                        emg_filtered_file = output_folder / "emg_filtered.mot"
                        self._write_filtered_emg(emg_file, emg_filtered_file,
                                                 selected_emg)
                        exported_files.append(("EMG filtered", emg_filtered_file))
                except Exception as e:
                    print(f"[WARN] Could not generate emg_filtered.mot: {str(e)[:60]}")
                    logger.warning(f"Could not generate emg_filtered.mot: {e}")

            # Check if analog.csv already exists from export_emg (it should)
            # If not, generate it as fallback
            analog_csv_path = output_folder / "analog.csv"
            if not analog_csv_path.exists():
                try:
                    if HAS_C3D:
                        print(f"[INFO] analog.csv not found from export_emg, generating fallback...")
                        with open(str(c3d_file), 'rb') as f:
                            reader = c3d.Reader(f)
                            frames_data = []
                            for frame_num, point_data, analog_data in reader.read_frames():
                                if analog_data is not None:
                                    if isinstance(analog_data, np.ndarray):
                                        frames_data.append(analog_data)

                            if frames_data:
                                all_analog = np.hstack(frames_data).T
                                np.savetxt(str(analog_csv_path), all_analog, delimiter=',', fmt='%.6f')
                                if ("Analog CSV", analog_csv_path) not in exported_files:
                                    exported_files.append(("Analog CSV", analog_csv_path))
                except Exception as e:
                    logger.error(f"Fallback analog.csv error: {e}")
            else:
                logger.debug("Using analog.csv from export_emg")

            # Time window (Start/End) for this trial, read straight from the c3d.
            # Persisted into the <events> subtree of trial_settings.xml — no
            # separate events file.
            _evt_start, _evt_end = 0.0, 1.0
            try:
                if HAS_C3D:
                    with open(str(c3d_file), 'rb') as f:
                        reader = c3d.Reader(f)
                        frame_rate = getattr(reader, 'point_rate', 1.0) or 1.0
                        frame_count = 0
                        for frame_num, point_data, analog_data in reader.read_frames():
                            frame_count = frame_num + 1
                        if frame_count > 0 and frame_rate > 0:
                            _evt_end = frame_count / frame_rate
            except Exception as e:
                logger.warning(f"Could not read time window from c3d: {e}")

            def _add_events_subtree(root_el):
                """Write <events> (Start/End window) into the trial_settings root."""
                ev_el = root_el.find("events")
                if ev_el is None:
                    ev_el = ET.SubElement(root_el, "events")
                for _e in list(ev_el):
                    ev_el.remove(_e)
                for _nm, _tv in (("Start", _evt_start), ("End", _evt_end)):
                    _ee = ET.SubElement(ev_el, "event")
                    _ee.set("name", _nm)
                    _ee.set("time", f"{float(_tv):.4f}")
                start_elem = root_el.find('start_time')
                if start_elem is None:
                    start_elem = ET.SubElement(root_el, 'start_time')
                start_elem.text = f"{_evt_start:.4f}"
                end_elem = root_el.find('end_time')
                if end_elem is None:
                    end_elem = ET.SubElement(root_el, 'end_time')
                end_elem.text = f"{_evt_end:.4f}"

            # Create trial_settings.xml using Inputs class
            try:
                settings_file = output_folder / "trial_settings.xml"

                # Create Inputs instance for this trial
                if HAS_INPUTS:
                    inputs = Inputs(parentdir=str(output_folder))

                    # Update file references for batch export
                    inputs.c3d = c3d_file.name
                    # emg_filtered.mot, not emg_filtered_normalised.mot:
                    # nothing in this tab has ever written the latter, so
                    # every trial_settings.xml pointed at a file that does
                    # not exist. Session-wide normalisation happens later
                    # (iteration.run(export=True)); it writes its own name.
                    inputs.emg = "emg_filtered.mot"
                    inputs.grf_mot = "grf.mot"
                    inputs.markers = "marker_experimental.trc"

                    # Update with batch export settings
                    inputs.alpha = "10"  # Default values
                    inputs.beta = "1"
                    inputs.gamma = "1000"

                    # Remove deprecated model_name attribute if it exists
                    if hasattr(inputs, 'model_name'):
                        delattr(inputs, 'model_name')

                    # Create XML from Inputs class attributes
                    root = ET.Element("TrialSettings")

                    # Remove any existing model_name elements (deprecated attribute)
                    for elem in list(root):
                        if elem.tag == 'model_name':
                            root.remove(elem)

                    # Convert all paths to be relative to the settings file
                    logger.info(f"Converting paths to relative (settings file: {settings_file})")
                    logger.debug(f"Original setup_dir: {inputs.setup_dir}")
                    logger.debug(f"Original model_dir: {inputs.model_dir}")

                    relative_attrs = inputs.to_relative_paths(str(settings_file))

                    logger.debug(f"Converted setup_dir: {relative_attrs.get('setup_dir', 'N/A')}")
                    logger.debug(f"Converted model_dir: {relative_attrs.get('model_dir', 'N/A')}")

                    # Add all attributes from Inputs
                    for attr, value in relative_attrs.items():
                        if value is not None:
                            # Skip internal attributes and deprecated model_name
                            if attr.startswith('_') or attr == 'model_name':
                                continue
                            # DEBUG: Log path values before writing
                            if attr in ['setup_dir', 'model_dir']:
                                print(f"[DEBUG] Writing {attr}: {value}")
                            child = ET.SubElement(root, attr)
                            child.text = str(value)

                    # Add batch-specific metadata
                    replace_elem = root.find("replace")
                    if replace_elem is not None:
                        replace_elem.text = "False"
                    else:
                        ET.SubElement(root, "replace").text = "False"

                    path_elem = root.find("path")
                    if path_elem is not None:
                        path_elem.text = "."
                    else:
                        ET.SubElement(root, "path").text = "."

                    settings_elem = root.find("settingsXML")
                    if settings_elem is not None:
                        settings_elem.text = "trial_settings.xml"
                    else:
                        ET.SubElement(root, "settingsXML").text = "trial_settings.xml"

                    subject_elem = root.find("subject")
                    if subject_elem is not None:
                        subject_elem.text = self.session_dir.parent.name if self.session_dir else "Unknown"
                    else:
                        ET.SubElement(root, "subject").text = self.session_dir.parent.name if self.session_dir else "Unknown"

                    session_elem = root.find("session")
                    if session_elem is not None:
                        session_elem.text = self.session_dir.name if self.session_dir else "Unknown"
                    else:
                        ET.SubElement(root, "session").text = self.session_dir.name if self.session_dir else "Unknown"

                    trial_elem = root.find("trial")
                    if trial_elem is not None:
                        trial_elem.text = trial_name
                    else:
                        ET.SubElement(root, "trial").text = trial_name

                    # Add EMG settings info
                    ET.SubElement(root, "emg_lowpass_hz").text = self.emg_lowpass_var.get()
                    ET.SubElement(root, "emg_highpass_hz").text = self.emg_highpass_var.get()
                    ET.SubElement(root, "emg_notch_hz").text = self.emg_notch_var.get()
                    ET.SubElement(root, "emg_label_pattern").text = self.emg_label_var.get()

                    # Add marker selection
                    ET.SubElement(root, "left_foot_markers").text = ", ".join(selected_left)
                    ET.SubElement(root, "right_foot_markers").text = ", ".join(selected_right)

                    # Write Start/End window into the <events> subtree
                    _add_events_subtree(root)

                    # Save with pretty formatting
                    tree = ET.ElementTree(root)
                    save_pretty_xml(tree, str(settings_file))
                    logger.info(f"Created trial_settings.xml with full Inputs structure")
                else:
                    # Fallback if Inputs class not available
                    logger.warning("Inputs class not available, creating minimal trial_settings.xml")
                    root = ET.Element("TrialSettings")
                    ET.SubElement(root, "replace").text = "False"
                    ET.SubElement(root, "path").text = "."
                    ET.SubElement(root, "settingsXML").text = "trial_settings.xml"
                    ET.SubElement(root, "subject").text = self.session_dir.parent.name if self.session_dir else "Unknown"
                    ET.SubElement(root, "session").text = self.session_dir.name if self.session_dir else "Unknown"
                    ET.SubElement(root, "trial").text = trial_name
                    ET.SubElement(root, "c3d").text = c3d_file.name
                    ET.SubElement(root, "emg").text = "emg_filtered.mot"
                    ET.SubElement(root, "grf_mot").text = "grf.mot"
                    ET.SubElement(root, "markers").text = "marker_experimental.trc"
                    ET.SubElement(root, "emg_lowpass_hz").text = self.emg_lowpass_var.get()
                    ET.SubElement(root, "emg_highpass_hz").text = self.emg_highpass_var.get()
                    ET.SubElement(root, "emg_notch_hz").text = self.emg_notch_var.get()
                    ET.SubElement(root, "emg_label_pattern").text = self.emg_label_var.get()
                    ET.SubElement(root, "left_foot_markers").text = ", ".join(selected_left)
                    ET.SubElement(root, "right_foot_markers").text = ", ".join(selected_right)

                    # Write Start/End window into the <events> subtree
                    _add_events_subtree(root)

                    tree = ET.ElementTree(root)
                    tree.write(str(settings_file), encoding='utf-8', xml_declaration=True)
            except Exception as e:
                logger.warning(f"Could not create trial_settings.xml: {e}")
                logger.debug(f"Exception details: {e}", exc_info=True)

            # Clean up the temporary C3D copy from output folder
            try:
                if c3d_copy.exists():
                    c3d_copy.unlink()
                    logger.debug(f"Cleaned up temporary C3D copy")
            except Exception as e:
                logger.warning(f"Could not clean up C3D copy: {e}")

            # QC figures — the SAME ones export_session writes for every trial
            # (emg_processing.png + grf_events.png). This tab skipped them, so
            # GUI-exported trials had no EMG figure while pipeline-exported
            # trials did, and the folders could not be compared at a glance.
            try:
                exportC3D._qc_figures(str(output_folder))
                print("[OK] QC figures (emg_processing.png, grf_events.png)")
            except Exception as e:                             # noqa: BLE001
                print(f"[WARN] QC figures failed: {str(e)[:60]}")
                logger.warning(f"QC figures failed for {trial_name}: {e}")

            # Export completed successfully
            logger.info(f"Export completed for {c3d_file.name}")

        except Exception as e:
            logger.error(f"Export error: {e}", exc_info=True)

    def _interpolate_markers_in_trc(self, trc_file: Path):
        """Apply interpolation to TRC marker file to fill missing values."""
        try:
            # Read TRC file
            with open(str(trc_file), 'r') as f:
                lines = f.readlines()

            # Parse header (first 2 lines)
            if len(lines) < 3:
                return

            header = lines[:2]
            data_lines = lines[2:]

            # Parse data
            data = []
            for line in data_lines:
                if line.strip():
                    data.append(line.strip().split())

            if not data:
                return

            # Convert to numeric (skip frame/time columns)
            num_cols = len(data[0])
            num_frames = len(data)

            # Apply interpolation to each marker column
            for col in range(2, num_cols):  # Skip frame/time
                marker_data = []

                # Extract column values
                for row in range(num_frames):
                    try:
                        val = float(data[row][col])
                        marker_data.append(val if not (val == 0 and col > 2) else None)
                    except:
                        marker_data.append(None)

                # Interpolate missing values
                for frame_idx in range(num_frames):
                    if marker_data[frame_idx] is None:
                        # Find surrounding valid values
                        before_idx = None
                        after_idx = None

                        for i in range(frame_idx - 1, -1, -1):
                            if marker_data[i] is not None:
                                before_idx = i
                                break

                        for i in range(frame_idx + 1, num_frames):
                            if marker_data[i] is not None:
                                after_idx = i
                                break

                        # Linear interpolation
                        if before_idx is not None and after_idx is not None:
                            w1 = (after_idx - frame_idx) / (after_idx - before_idx)
                            w2 = (frame_idx - before_idx) / (after_idx - before_idx)
                            interpolated = w1 * marker_data[before_idx] + w2 * marker_data[after_idx]
                            data[frame_idx][col] = f"{interpolated:.6f}"
                        elif before_idx is not None:
                            data[frame_idx][col] = f"{marker_data[before_idx]:.6f}"
                        elif after_idx is not None:
                            data[frame_idx][col] = f"{marker_data[after_idx]:.6f}"

            # Write interpolated data back
            with open(str(trc_file), 'w') as f:
                f.writelines(header)
                for row in data:
                    f.write('\t'.join(row) + '\n')

            logger.info(f"Applied interpolation to marker file: {trc_file.name}")

        except Exception as e:
            logger.warning(f"Could not apply marker interpolation: {e}")

    def _ensure_all_markers_in_trc(self, trc_file: Path, all_markers: set):
        """
        Ensure all markers are in the TRC file.

        Adds missing markers with zero/interpolated values to match the full marker set.
        This ensures consistent marker output across all trials even when some
        markers don't exist in individual trials.

        Args:
            trc_file: Path to the marker_experimental.trc file
            all_markers: Set of all markers that should be present
        """
        try:
            # Read TRC file and add missing markers
            # TRC files have a specific header structure
            with open(str(trc_file), 'r') as f:
                lines = f.readlines()

            if len(lines) < 4:
                logger.warning(f"TRC file too short: {trc_file}")
                return

            # Save header lines for later
            header_line_0 = lines[0]
            header_line_1 = lines[1]
            header_line_2 = lines[2]  # Marker names
            header_line_3 = lines[3] if len(lines) > 3 else ""  # X Y Z labels

            # Parse marker names from line 2
            header_parts = header_line_2.strip().split('\t')
            existing_marker_names = []

            # Skip first two columns (Frame# and Time)
            i = 2
            while i < len(header_parts):
                marker_name = header_parts[i].strip()
                # Check if it's a marker name (not X, Y, Z)
                if marker_name and marker_name not in ['X', 'Y', 'Z']:
                    existing_marker_names.append(marker_name)
                    i += 3  # Skip X, Y, Z
                else:
                    i += 1

            existing_markers = set(existing_marker_names)
            missing_markers = sorted(all_markers - existing_markers)

            if not missing_markers:
                logger.info(f"All {len(all_markers)} markers already present in TRC file")
                return

            logger.info(f"Adding {len(missing_markers)} missing markers to TRC: {missing_markers}")

            # Read data rows
            data_rows = []
            for i in range(4, len(lines)):
                if lines[i].strip():
                    data_rows.append(lines[i].rstrip('\n').split('\t'))

            # For each missing marker, add 3 zero-valued columns (X, Y, Z)
            for missing_marker in missing_markers:
                for row in data_rows:
                    # Add three columns for X, Y, Z with zero values
                    row.append("0.000000")
                    row.append("0.000000")
                    row.append("0.000000")

            # Reconstruct the marker names header with all markers in sorted order
            all_markers_sorted = sorted(all_markers)
            new_header_parts = header_parts[:2]  # Keep Frame# and Time

            for marker in all_markers_sorted:
                new_header_parts.append(marker)
                new_header_parts.append("X")
                new_header_parts.append("Y")
                new_header_parts.append("Z")

            # Write updated TRC file
            with open(str(trc_file), 'w') as f:
                f.write(header_line_0)
                f.write(header_line_1)
                f.write('\t'.join(new_header_parts) + '\n')

                # Write coordinate labels line if it existed
                if header_line_3.strip():
                    new_coord_line_parts = header_line_3.strip().split('\t')[:2]
                    for _ in all_markers_sorted:
                        new_coord_line_parts.extend(['X', 'Y', 'Z'])
                    f.write('\t'.join(new_coord_line_parts) + '\n')

                # Write data rows
                for row in data_rows:
                    f.write('\t'.join(row) + '\n')

            logger.info(f"Updated TRC file with all {len(all_markers)} markers ({len(missing_markers)} added)")

        except Exception as e:
            logger.error(f"Error ensuring all markers in TRC: {e}")

    @staticmethod
    def _create_grf_xml(output_folder: Path) -> None:
        """Create GRF.xml (OpenSim ExternalLoads) referencing grf.mot.

        Reads the grf.mot header to discover force-plate IDs and writes one
        ExternalForce block per plate.  Plate 1 defaults to right calcaneus,
        plate 2 to left calcaneus; additional plates use a generic body name.
        """
        try:
            grf_mot = output_folder / "grf.mot"
            if not grf_mot.exists():
                logger.warning("grf.mot not found – skipping GRF.xml creation")
                return

            # ── discover plate IDs from grf.mot column headers ────────────
            import re as _re
            plate_ids = []
            with open(str(grf_mot), 'r', errors='replace') as fh:
                for line in fh:
                    if 'ground_force' in line.lower():
                        plate_ids = sorted(set(
                            _re.findall(r'ground_force_(\d+)_v', line)))
                        break

            if not plate_ids:
                # Fall back to two plates if we couldn't parse
                plate_ids = ['1', '2']

            # Default body assignments (user can edit in OpenSim)
            _default_bodies = {0: 'calcn_r', 1: 'calcn_l'}

            # ── build XML ─────────────────────────────────────────────────
            root = ET.Element('OpenSimDocument')
            root.set('Version', '40000')

            ext_loads = ET.SubElement(root, 'ExternalLoads')
            ext_loads.set('name', 'externalloads')

            objects = ET.SubElement(ext_loads, 'objects')

            for idx, pid in enumerate(plate_ids):
                body = _default_bodies.get(idx, f'calcn_{idx}')
                ef = ET.SubElement(objects, 'ExternalForce')
                ef.set('name', f'grf_plate{pid}')
                ET.SubElement(ef, 'applied_to_body').text          = body
                ET.SubElement(ef, 'force_expressed_in_body').text  = 'ground'
                ET.SubElement(ef, 'point_expressed_in_body').text  = 'ground'
                ET.SubElement(ef, 'force_identifier').text         = f'ground_force_{pid}_v'
                ET.SubElement(ef, 'point_identifier').text         = f'ground_force_{pid}_p'
                ET.SubElement(ef, 'torque_identifier').text        = f'ground_moment_{pid}_m'
                ET.SubElement(ef, 'data_source_name').text         = ''

            ET.SubElement(ext_loads, 'groups')
            ET.SubElement(ext_loads, 'datafile').text = 'grf.mot'
            ET.SubElement(ext_loads, 'external_loads_model_kinematics_file').text = ''
            ET.SubElement(ext_loads, 'lowpass_cutoff_frequency_for_load_kinematics').text = '6'

            # ── pretty-print ──────────────────────────────────────────────
            from xml.dom import minidom as _md
            xml_str = _md.parseString(ET.tostring(root)).toprettyxml(indent='   ')
            xml_str = '\n'.join(l for l in xml_str.splitlines() if l.strip())

            grf_xml = output_folder / 'GRF.xml'
            with open(str(grf_xml), 'w', encoding='utf-8') as fh:
                fh.write(xml_str)

            print(f"[OK] Created GRF.xml ({len(plate_ids)} force plate(s))")
            logger.info(f"GRF.xml created: {grf_xml}")

        except Exception as exc:
            logger.warning(f"Could not create GRF.xml: {exc}")

    def _on_cancel(self):  # noqa: D401
        """Cancel batch export."""
        self.is_processing = False
        self._progress("Cancelling...")
        self.cancel_button.configure(state="disabled")
