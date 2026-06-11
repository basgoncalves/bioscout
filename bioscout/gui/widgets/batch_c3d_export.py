"""Batch C3D Export Widget - Process multiple C3D files at once."""

import customtkinter as ctk
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

# ============================================================================
# DEFAULT FOOT MARKER PATTERNS - EDIT THESE TO CUSTOMIZE MARKER DETECTION
# ============================================================================
# These lists define which markers are considered "foot markers" and will be
# auto-checked when "Update Markers" is clicked. Markers not in these lists
# will appear unchecked by default.

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

    def __init__(self, parent):
        """Initialize Batch C3D Export widget."""
        super().__init__(parent)

        self.source_folder = None
        self.dest_folder = None
        self.c3d_files: List[Path] = []
        self.selected_files: List[bool] = []
        self.is_processing = False
        self.current_progress = 0
        self.total_files = 0
        self.session_dir = None  # Track session directory
        self.all_detected_markers = set()  # Store all markers detected across trials

        self._create_widgets()

    def set_session_dir(self, session_dir: str):
        """Set the session directory - called by main window."""
        self.session_dir = Path(session_dir) if session_dir else None
        if self.session_dir and self.session_dir.exists():
            # Auto-populate source folder with session directory
            self.source_folder_var.set(str(self.session_dir))
            self.source_folder = self.session_dir  # Directly set source_folder

            # Also auto-populate destination folder with same directory
            self.dest_entry.delete(0, "end")
            self.dest_entry.insert(0, str(self.session_dir))
            self.dest_folder = self.session_dir  # Directly set dest_folder

            self._scan_for_c3d_files()

            # Auto-populate markers from C3D files
            self._update_markers_from_c3d()

            logger.debug(f"Batch C3D: Session directory set to {self.session_dir}")

    def _create_widgets(self):
        """Create UI widgets - compact layout with file list on left."""
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_columnconfigure(0, weight=3)   # Files column (narrower)
        self.grid_columnconfigure(1, weight=7)   # Settings column (wider)

        # ===== FOLDER SELECTION SECTION (spans both columns) =====
        folder_frame = ctk.CTkFrame(self)
        folder_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=(2, 2))
        folder_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(folder_frame, text="Batch C3D Export", font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=5, pady=(3, 5)
        )

        # Source folder (hidden - auto-populated from session)
        self.source_folder_var = ctk.StringVar(value="")
        self.source_folder_var.trace("w", lambda *args: self._validate_source_folder())
        self.source_error = ctk.CTkLabel(folder_frame, text="", text_color="#dc3545", font=("Segoe UI", 8))

        # Destination folder (keep only destination, remove source from display)
        ctk.CTkLabel(folder_frame, text="Dest. Folder:", font=("Segoe UI", 9)).grid(
            row=1, column=0, sticky="w", padx=5, pady=(2, 1)
        )
        self.dest_entry = ctk.CTkEntry(folder_frame, placeholder_text="Paste folder path or browse...", font=("Segoe UI", 9))
        self.dest_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=(2, 1))
        self.dest_entry.bind("<KeyRelease>", lambda e: self._validate_dest_folder())

        ctk.CTkButton(
            folder_frame,
            text="Browse",
            width=80,
            font=("Segoe UI", 9),
            command=self._select_dest_folder,
        ).grid(row=1, column=2, sticky="ew", padx=5, pady=(2, 1))

        self.dest_error = ctk.CTkLabel(folder_frame, text="", text_color="#dc3545", font=("Segoe UI", 8))
        self.dest_error.grid(row=2, column=0, columnspan=3, sticky="w", padx=5, pady=(0, 2))

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
        self.files_scroll_frame = ctk.CTkScrollableFrame(files_frame)
        self.files_scroll_frame.grid(row=1, column=0, sticky="nsew")
        self.files_scroll_frame.grid_columnconfigure(0, weight=1)

        self.file_checkboxes: List[ctk.CTkCheckBox] = []
        self.file_vars: List[ctk.BooleanVar] = []

        # ===== RIGHT COLUMN: EMG SETTINGS & MARKERS SECTION =====
        settings_frame = ctk.CTkFrame(self)
        settings_frame.grid(row=1, column=1, sticky="nsew", padx=(2, 5), pady=(2, 2))
        settings_frame.grid_rowconfigure(2, weight=0)
        settings_frame.grid_columnconfigure(0, weight=1)  # EMG settings
        settings_frame.grid_columnconfigure(1, weight=1)  # Markers (side by side)

        # Header
        header_frame2 = ctk.CTkFrame(settings_frame)
        header_frame2.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 3))
        header_frame2.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header_frame2, text="EMG Settings:", font=("Segoe UI", 8, "bold")).pack(side="left", anchor="w", padx=5)

        ctk.CTkButton(
            header_frame2,
            text="Update Markers",
            width=100,
            font=("Segoe UI", 8),
            command=self._update_markers_from_c3d,
        ).pack(side="right", padx=0)

        # EMG Label Pattern
        emg_pattern_frame = ctk.CTkFrame(settings_frame)
        emg_pattern_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 3))
        emg_pattern_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(emg_pattern_frame, text="Label:", font=("Segoe UI", 8)).grid(row=0, column=0, sticky="w", padx=0)
        self.emg_label_var = ctk.StringVar(value=BATCH_C3D_EMG_LABEL_DEFAULT)
        self.emg_label_entry = ctk.CTkEntry(emg_pattern_frame, textvariable=self.emg_label_var, placeholder_text=BATCH_C3D_EMG_LABEL_DEFAULT, height=24)
        self.emg_label_entry.grid(row=0, column=1, sticky="ew", padx=5)

        # EMG Filter Settings (side by side)
        filter_frame = ctk.CTkFrame(settings_frame)
        filter_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=(3, 3))
        filter_frame.grid_columnconfigure(0, weight=1)
        filter_frame.grid_columnconfigure(1, weight=1)
        filter_frame.grid_columnconfigure(2, weight=1)
        filter_frame.grid_columnconfigure(3, weight=0)

        ctk.CTkLabel(filter_frame, text="Filters:", font=("Segoe UI", 8, "bold")).grid(row=0, column=0, sticky="w", padx=0, pady=(0, 5))

        # FPS display (analog frame rate from C3D)
        self.analog_fps = None
        self.fps_label = ctk.CTkLabel(filter_frame, text="FPS: --", font=("Segoe UI", 7), text_color="#888888")
        self.fps_label.grid(row=0, column=3, sticky="e", padx=5, pady=(0, 5))

        # Low Pass Filter
        ctk.CTkLabel(filter_frame, text="Low (Hz)", font=("Segoe UI", 7, "bold")).grid(row=1, column=0, sticky="w", padx=0, pady=(0, 2))
        self.emg_lowpass_var = ctk.StringVar(value=BATCH_C3D_EMG_LOWPASS_DEFAULT)
        ctk.CTkEntry(filter_frame, textvariable=self.emg_lowpass_var, height=24, width=50).grid(row=2, column=0, sticky="ew", padx=0, pady=(0, 5))

        # High Pass Filter
        ctk.CTkLabel(filter_frame, text="High (Hz)", font=("Segoe UI", 7, "bold")).grid(row=1, column=1, sticky="w", padx=5, pady=(0, 2))
        self.emg_highpass_var = ctk.StringVar(value=BATCH_C3D_EMG_HIGHPASS_DEFAULT)
        ctk.CTkEntry(filter_frame, textvariable=self.emg_highpass_var, height=24, width=50).grid(row=2, column=1, sticky="ew", padx=5, pady=(0, 5))

        # Notch Filter
        ctk.CTkLabel(filter_frame, text="Notch (Hz)", font=("Segoe UI", 7, "bold")).grid(row=1, column=2, sticky="w", padx=5, pady=(0, 2))
        self.emg_notch_var = ctk.StringVar(value=BATCH_C3D_EMG_NOTCH_DEFAULT)
        ctk.CTkEntry(filter_frame, textvariable=self.emg_notch_var, height=24, width=50).grid(row=2, column=2, sticky="ew", padx=5, pady=(0, 5))

        # EMG Channels Header
        ctk.CTkLabel(settings_frame, text="EMG Channels:", font=("Segoe UI", 8, "bold")).grid(
            row=3, column=0, sticky="w", padx=5, pady=(8, 2)
        )

        # EMG Channels Frame (taller, expanded)
        emg_channels_frame = ctk.CTkFrame(settings_frame)
        emg_channels_frame.grid(row=4, column=0, sticky="nsew", padx=5, pady=(0, 3))
        emg_channels_frame.grid_rowconfigure(1, weight=1)  # Make scrollable area expandable
        emg_channels_frame.grid_columnconfigure(0, weight=1)

        # Set minimum height for emg_channels_frame and markers frame
        settings_frame.grid_rowconfigure(4, weight=1, minsize=250)
        settings_frame.grid_rowconfigure(1, weight=1, minsize=250)  # Markers frame height

        # EMG Channels buttons
        emg_btn_frame = ctk.CTkFrame(emg_channels_frame)
        emg_btn_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 2))
        emg_btn_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(emg_btn_frame, text="All", width=40, font=("Segoe UI", 7), command=self._select_all_emg).pack(side="left", padx=1)
        ctk.CTkButton(emg_btn_frame, text="None", width=40, font=("Segoe UI", 7), command=self._deselect_all_emg).pack(side="left", padx=1)

        self.emg_channels_scroll = ctk.CTkScrollableFrame(emg_channels_frame, height=120)
        self.emg_channels_scroll.grid(row=1, column=0, sticky="nsew")
        self.emg_channels_scroll.grid_columnconfigure(0, weight=1)

        self.emg_channel_vars = {}
        self.emg_channel_checkboxes = []

        # Markers Header (RIGHT COLUMN, at same level as EMG Settings header)
        ctk.CTkLabel(settings_frame, text="All Markers:", font=("Segoe UI", 8, "bold")).grid(
            row=0, column=1, sticky="w", padx=5, pady=(0, 2)
        )

        # Markers Frame (RIGHT COLUMN, spans same rows as EMG content, side by side layout)
        markers_frame = ctk.CTkFrame(settings_frame)
        markers_frame.grid(row=1, column=1, rowspan=4, sticky="nsew", padx=5, pady=(0, 3))
        markers_frame.grid_columnconfigure(0, weight=1)
        markers_frame.grid_columnconfigure(1, weight=1)

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

        self.left_markers_scroll = ctk.CTkScrollableFrame(left_foot_frame)
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

        self.right_markers_scroll = ctk.CTkScrollableFrame(right_foot_frame)
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

        ctk.CTkLabel(progress_frame, text="Progress:", font=("Segoe UI", 9, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=5, pady=(2, 1)
        )

        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=2)
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(
            progress_frame,
            text="Ready",
            text_color="gray",
            font=("Segoe UI", 8)
        )
        self.progress_label.grid(row=2, column=0, columnspan=2, sticky="w", padx=5, pady=2)

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

    def _validate_source_folder(self):
        """Validate source folder path."""
        path_str = self.source_entry.get().strip()
        if not path_str:
            self.source_error.configure(text="")
            self.source_folder = None
            return

        try:
            path = Path(path_str)
            if path.exists() and path.is_dir():
                self.source_folder = path
                self.source_error.configure(text="")

                # Auto-populate destination folder with same path if empty
                dest_str = self.dest_entry.get().strip()
                if not dest_str:
                    self.dest_entry.delete(0, "end")
                    self.dest_entry.insert(0, str(path))
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
            folder = filedialog.askdirectory(title="Select source folder with C3D files")
            if folder:
                self.source_entry.delete(0, "end")
                self.source_entry.insert(0, folder)
                self._validate_source_folder()
        except Exception as e:
            logger.error(f"Error selecting source folder: {str(e)}")

    def _select_dest_folder(self):
        """Select destination folder for exports."""
        try:
            import tkinter.filedialog as filedialog
            folder = filedialog.askdirectory(title="Select destination folder")
            if folder:
                self.dest_entry.delete(0, "end")
                self.dest_entry.insert(0, folder)
                self._validate_dest_folder()
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
                font=("Segoe UI", 9)
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
                font=("Segoe UI", 9)
            )
            checkbox.pack(anchor="w", padx=5, pady=2)
            self.right_marker_checkboxes.append(checkbox)

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

        # Create checkboxes for each EMG channel
        for channel in sorted(channels):
            var = ctk.BooleanVar(value=True)
            self.emg_channel_vars[channel] = var
            checkbox = ctk.CTkCheckBox(
                self.emg_channels_scroll,
                text=channel,
                variable=var,
                font=("Segoe UI", 9)
            )
            checkbox.pack(anchor="w", padx=5, pady=2)
            self.emg_channel_checkboxes.append(checkbox)

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
                                    marker = label.strip()
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

                        # Detect EMG channels
                        if hasattr(reader, 'analog_labels'):
                            for label in reader.analog_labels:
                                if label and label.strip():
                                    channel_label = label.strip()
                                    # Check if matches EMG pattern
                                    if emg_pattern and emg_pattern.lower() in channel_label.lower():
                                        emg_channels.add(channel_label)
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

                for marker in sorted_markers:
                    if marker in LEFT_FOOT_MARKER_PATTERNS:
                        left_foot_markers.add(marker)
                    if marker in RIGHT_FOOT_MARKER_PATTERNS:
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

            # Update EMG channel checkboxes
            if emg_channels:
                sorted_emg = sorted(list(emg_channels))
                self._populate_emg_channels(sorted_emg)
                logger.info(f"Updated EMG channels: {len(emg_channels)} channels detected")
                logger.info(f"EMG channels: {sorted_emg}")
            else:
                logger.info("No EMG channels detected matching pattern")

        except Exception as e:
            logger.error(f"Error updating markers from C3D files: {e}")
            logger.debug(f"Exception details: {e}", exc_info=True)

    def _on_export_batch(self):
        """Start batch export."""
        try:
            # Validate selections
            if not self.source_folder or not self.source_folder.exists():
                self.progress_label.configure(text="Error: Source folder not selected")
                return

            if not self.dest_folder or not self.dest_folder.exists():
                self.progress_label.configure(text="Error: Destination folder not selected")
                return

            selected_count = sum(self.selected_files)
            if selected_count == 0:
                self.progress_label.configure(text="Error: No files selected")
                return

            # Check that at least one marker is selected
            selected_left, selected_right = self._get_selected_markers()
            if not selected_left or not selected_right:
                self.progress_label.configure(text="Error: Select at least one left and right foot marker")
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
            self.progress_label.configure(text=f"Error: {str(e)[:40]}")

    def _export_batch_worker(self, total_selected: int):
        """Worker thread for batch export."""
        try:
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
                self.progress_label.configure(
                    text=f"Processing {c3d_file.name} ({self.current_progress}/{self.total_files})"
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
                self.progress_label.configure(
                    text=f"[OK] Completed: {self.current_progress} files exported"
                )
                logger.info(f"Batch export completed: {self.current_progress} files")
            else:
                self.progress_label.configure(text="Cancelled by user")

        except Exception as e:
            logger.error(f"Error in batch export worker: {str(e)}")
            self.progress_label.configure(text=f"Error: {str(e)[:40]}")

        finally:
            self.is_processing = False
            self.export_button.configure(state="normal")
            self.cancel_button.configure(state="disabled")

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
                    exportC3D.export_markers(str(c3d_copy), strings_to_remove=[])
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
                except Exception as e:
                    logger.error(f"GRF export error: {e}")

                # Export EMG (now from copy in output folder)
                try:
                    if selected_emg:
                        # Extract EMG pattern from selected channels (e.g., "Voltage" from "Voltage.1-VM")
                        # Use the first selected channel to determine the pattern
                        emg_pattern = selected_emg[0].split('.')[0].split('_')[0]  # Get prefix before . or _
                        emg_patterns = [emg_pattern]
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

                # Generate emg_filtered.mot (copy of emg.mot)
                try:
                    emg_file = output_folder / "emg.mot"
                    if emg_file.exists():
                        emg_filtered_file = output_folder / "emg_filtered.mot"
                        shutil.copy(str(emg_file), str(emg_filtered_file))
                        print(f"[OK] Generated emg_filtered.mot")
                        logger.info(f"[OK] Generated emg_filtered.mot")
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

            # Create trial_settings.xml using Inputs class
            try:
                settings_file = output_folder / "trial_settings.xml"

                # Create Inputs instance for this trial
                if HAS_INPUTS:
                    inputs = Inputs(parentdir=str(output_folder))

                    # Update file references for batch export
                    inputs.c3d = c3d_file.name
                    inputs.emg = "emg_filtered_normalised.mot"
                    inputs.grf_mot = "grf.mot"
                    inputs.markers = "marker_experimental.trc"
                    inputs.events = "events.csv"

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

                    # Update time range from events.csv if it exists
                    events_file = output_folder / "events.csv"
                    if events_file.exists():
                        try:
                            import pandas as pd
                            events_df = pd.read_csv(str(events_file), header=None)

                            start_time = None
                            end_time = None

                            for _, row in events_df.iterrows():
                                event_name = str(row[0]).lower().strip()
                                try:
                                    event_time = float(row[1])
                                except (ValueError, TypeError):
                                    continue

                                if 'start' in event_name:
                                    start_time = event_time
                                elif 'end' in event_name:
                                    end_time = event_time

                            # Update time range elements if found
                            if start_time is not None and end_time is not None:
                                # Update start_time
                                start_elem = root.find('start_time')
                                if start_elem is None:
                                    start_elem = ET.SubElement(root, 'start_time')
                                start_elem.text = f"{start_time:.4f}"

                                # Update end_time
                                end_elem = root.find('end_time')
                                if end_elem is None:
                                    end_elem = ET.SubElement(root, 'end_time')
                                end_elem.text = f"{end_time:.4f}"

                                logger.info(f"Updated time range from events.csv: {start_time:.4f} - {end_time:.4f}")
                        except Exception as e:
                            logger.warning(f"Could not update time range from events.csv: {e}")

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
                    ET.SubElement(root, "emg").text = "emg_filtered_normalised.mot"
                    ET.SubElement(root, "grf_mot").text = "grf.mot"
                    ET.SubElement(root, "markers").text = "marker_experimental.trc"
                    ET.SubElement(root, "events").text = "events.csv"
                    ET.SubElement(root, "emg_lowpass_hz").text = self.emg_lowpass_var.get()
                    ET.SubElement(root, "emg_highpass_hz").text = self.emg_highpass_var.get()
                    ET.SubElement(root, "emg_notch_hz").text = self.emg_notch_var.get()
                    ET.SubElement(root, "emg_label_pattern").text = self.emg_label_var.get()
                    ET.SubElement(root, "left_foot_markers").text = ", ".join(selected_left)
                    ET.SubElement(root, "right_foot_markers").text = ", ".join(selected_right)

                    # Update time range from events.csv if it exists
                    events_file = output_folder / "events.csv"
                    if events_file.exists():
                        try:
                            import pandas as pd
                            events_df = pd.read_csv(str(events_file), header=None)

                            start_time = None
                            end_time = None

                            for _, row in events_df.iterrows():
                                event_name = str(row[0]).lower().strip()
                                try:
                                    event_time = float(row[1])
                                except (ValueError, TypeError):
                                    continue

                                if 'start' in event_name:
                                    start_time = event_time
                                elif 'end' in event_name:
                                    end_time = event_time

                            # Update time range elements if found
                            if start_time is not None and end_time is not None:
                                ET.SubElement(root, 'start_time').text = f"{start_time:.4f}"
                                ET.SubElement(root, 'end_time').text = f"{end_time:.4f}"
                                logger.info(f"Updated time range from events.csv: {start_time:.4f} - {end_time:.4f}")
                        except Exception as e:
                            logger.warning(f"Could not update time range from events.csv: {e}")

                    tree = ET.ElementTree(root)
                    tree.write(str(settings_file), encoding='utf-8', xml_declaration=True)
            except Exception as e:
                logger.warning(f"Could not create trial_settings.xml: {e}")
                logger.debug(f"Exception details: {e}", exc_info=True)

            # Create events.csv with trial timing
            try:
                if HAS_C3D:
                    with open(str(c3d_file), 'rb') as f:
                        reader = c3d.Reader(f)
                        frame_count = 0
                        frame_rate = 1.0

                        if hasattr(reader, 'point_rate'):
                            frame_rate = reader.point_rate

                        # Count frames using read_frames()
                        for frame_num, point_data, analog_data in reader.read_frames():
                            frame_count = frame_num + 1

                        # Calculate timing
                        trial_start = 0.0
                        trial_end = frame_count / frame_rate if frame_count > 0 and frame_rate > 0 else 1.0

                        events_file = output_folder / "events.csv"
                        with open(str(events_file), 'w', newline='') as f:
                            writer = csv.writer(f, lineterminator='\n')
                            writer.writerow(["Start", f"{trial_start:.3f}"])
                            writer.writerow(["End", f"{trial_end:.3f}"])
            except Exception as e:
                logger.warning(f"Could not create events.csv: {e}")

            # Clean up the temporary C3D copy from output folder
            try:
                if c3d_copy.exists():
                    c3d_copy.unlink()
                    logger.debug(f"Cleaned up temporary C3D copy")
            except Exception as e:
                logger.warning(f"Could not clean up C3D copy: {e}")

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

    def _on_cancel(self):
        """Cancel batch export."""
        self.is_processing = False
        self.progress_label.configure(text="Cancelling...")
        self.cancel_button.configure(state="disabled")
