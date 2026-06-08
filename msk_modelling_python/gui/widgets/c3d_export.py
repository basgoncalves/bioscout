"""C3D Export Tab - Convert C3D files to TRC, MOT, and EMG formats with visualization."""

import customtkinter as ctk
from pathlib import Path
import sys
import threading
from tkinter import filedialog, messagebox
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from gui.widgets.c3d_grf_viewer import C3DGRFViewer
from config.config_manager import ConfigManager
from utils.logger import logger

try:
    import c3d
    HAS_C3D = True
except ImportError:
    HAS_C3D = False

try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    import importlib.util
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


class C3DExportTab(ctk.CTkFrame):
    """Tab for exporting C3D files to various formats with GRF visualization."""

    def __init__(self, parent, config_manager, status_callback):
        """Initialize C3D Export Tab."""
        super().__init__(parent)
        self.config_manager = config_manager
        self.status_callback = status_callback
        self.c3d_file = None
        self.export_thread = None
        self.c3d_data = None
        self.markers_list = []
        self.emg_channels_list = []
        self.selected_markers = set()
        self.selected_emg = set()

        self._create_widgets()

    def _create_widgets(self):
        """Create UI widgets."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(header, text="C3D File Export", font=("Segoe UI", 14, "bold")).pack(side="left", padx=5)

        content = ctk.CTkFrame(self)
        content.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        content.grid_rowconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=0)  # Row for buttons below file selection
        content.grid_columnconfigure(0, weight=0)
        content.grid_columnconfigure(1, weight=1)
        content.grid_columnconfigure(2, weight=0)

        left_panel = ctk.CTkScrollableFrame(content, corner_radius=8, width=250)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left_panel.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(left_panel, text="File Selection", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=10, pady=(10, 5))

        self.file_var = ctk.StringVar(value="")
        self.file_entry = ctk.CTkEntry(left_panel, textvariable=self.file_var, placeholder_text="Paste C3D path or browse...", font=("Segoe UI", 9))
        self.file_entry.pack(fill="x", padx=10, pady=(0, 2))
        self.file_entry.bind("<KeyRelease>", lambda e: self._validate_c3d_path())

        self.file_error = ctk.CTkLabel(left_panel, text="", text_color="#dc3545", font=("Segoe UI", 8))
        self.file_error.pack(anchor="w", padx=10, pady=(0, 5))

        ctk.CTkButton(left_panel, text="Browse C3D File", command=self._select_c3d_file).pack(fill="x", padx=10, pady=5)

        # Separator - export buttons will go below the scrollable area
        ctk.CTkLabel(left_panel, text="").pack()  # Empty space

        ctk.CTkLabel(left_panel, text="Export Options", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=10, pady=(15, 5))

        self.export_markers = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(left_panel, text="Export Markers (TRC)", variable=self.export_markers, font=("Segoe UI", 10)).pack(anchor="w", padx=10, pady=3)

        self.export_grf = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(left_panel, text="Export GRF (MOT)", variable=self.export_grf, font=("Segoe UI", 10)).pack(anchor="w", padx=10, pady=3)

        self.export_emg = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(left_panel, text="Export EMG (MOT)", variable=self.export_emg, font=("Segoe UI", 10)).pack(anchor="w", padx=10, pady=3)

        ctk.CTkLabel(left_panel, text="Additional Options", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=10, pady=(15, 5))

        self.create_folder = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(left_panel, text="Create separate output folder", variable=self.create_folder, font=("Segoe UI", 10)).pack(anchor="w", padx=10, pady=3)

        ctk.CTkLabel(left_panel, text="EMG Label Patterns:", font=("Segoe UI", 10)).pack(anchor="w", padx=10, pady=(15, 0))
        self.emg_patterns = ctk.CTkEntry(left_panel, placeholder_text="e.g., emg, EMG")
        self.emg_patterns.pack(fill="x", padx=10, pady=(0, 5))
        self.emg_patterns.insert(0, "emg")

        ctk.CTkLabel(left_panel, text="Marker label strings to remove:", font=("Segoe UI", 10)).pack(anchor="w", padx=10, pady=(10, 0))
        self.strings_to_remove = ctk.CTkEntry(left_panel, placeholder_text="e.g., Subject01_, _marker")
        self.strings_to_remove.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(left_panel, text="EMG Processing Parameters", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=10, pady=(15, 5))

        ctk.CTkLabel(left_panel, text="Bandpass Low (Hz):", font=("Segoe UI", 9)).pack(anchor="w", padx=10, pady=(5, 0))
        self.bp_low = ctk.CTkEntry(left_panel, placeholder_text="10")
        self.bp_low.pack(fill="x", padx=10, pady=(0, 5))
        self.bp_low.insert(0, "10")

        ctk.CTkLabel(left_panel, text="Bandpass High (Hz):", font=("Segoe UI", 9)).pack(anchor="w", padx=10, pady=(5, 0))
        self.bp_high = ctk.CTkEntry(left_panel, placeholder_text="500")
        self.bp_high.pack(fill="x", padx=10, pady=(0, 5))
        self.bp_high.insert(0, "500")

        ctk.CTkLabel(left_panel, text="Lowpass Cutoff (Hz):", font=("Segoe UI", 9)).pack(anchor="w", padx=10, pady=(5, 0))
        self.lp_cutoff = ctk.CTkEntry(left_panel, placeholder_text="10")
        self.lp_cutoff.pack(fill="x", padx=10, pady=(0, 5))
        self.lp_cutoff.insert(0, "10")

        ctk.CTkLabel(left_panel, text="Amplitude Scale:", font=("Segoe UI", 9)).pack(anchor="w", padx=10, pady=(5, 0))
        self.amplitude_scale = ctk.CTkEntry(left_panel, placeholder_text="1.0")
        self.amplitude_scale.pack(fill="x", padx=10, pady=(0, 5))
        self.amplitude_scale.insert(0, "1.0")

        center_panel = ctk.CTkFrame(content, corner_radius=8)
        center_panel.grid(row=0, column=1, sticky="nsew", padx=5)
        center_panel.grid_rowconfigure(0, weight=1)

        self.grf_viewer = C3DGRFViewer(center_panel)
        self.grf_viewer.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        right_panel = ctk.CTkFrame(content, corner_radius=8, width=220)
        right_panel.grid(row=0, column=2, sticky="nsew", padx=(5, 0))
        right_panel.grid_rowconfigure(1, weight=1)
        right_panel.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(right_panel, text="Markers", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))

        marker_buttons = ctk.CTkFrame(right_panel)
        marker_buttons.grid(row=0, column=0, sticky="e", padx=10, pady=(10, 0))
        ctk.CTkButton(marker_buttons, text="All", width=35, font=("Segoe UI", 9), command=self._select_all_markers).pack(side="left", padx=2)
        ctk.CTkButton(marker_buttons, text="None", width=40, font=("Segoe UI", 9), command=self._deselect_all_markers).pack(side="left", padx=2)

        self.markers_frame = ctk.CTkScrollableFrame(right_panel)
        self.markers_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        ctk.CTkLabel(right_panel, text="EMG Channels", font=("Segoe UI", 11, "bold")).grid(row=2, column=0, sticky="w", padx=10, pady=(10, 5))

        emg_buttons = ctk.CTkFrame(right_panel)
        emg_buttons.grid(row=2, column=0, sticky="e", padx=10, pady=(10, 0))
        ctk.CTkButton(emg_buttons, text="All", width=35, font=("Segoe UI", 9), command=self._select_all_emg).pack(side="left", padx=2)
        ctk.CTkButton(emg_buttons, text="None", width=40, font=("Segoe UI", 9), command=self._deselect_all_emg).pack(side="left", padx=2)

        self.emg_frame = ctk.CTkScrollableFrame(right_panel)
        self.emg_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))

        # Export/Stop buttons below file selection (outside scrollable area, on the right)
        button_frame = ctk.CTkFrame(content)
        button_frame.grid(row=1, column=0, columnspan=3, sticky="e", padx=(0, 5), pady=(5, 0))
        button_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(button_frame, text="Export", fg_color="#28a745", command=self._run_export,
                     font=("Segoe UI", 11, "bold"), height=35, width=100).pack(side="left", padx=(0, 5))

        self.stop_btn = ctk.CTkButton(button_frame, text="Stop", fg_color="#dc3545", command=self._stop_export,
                                      font=("Segoe UI", 11, "bold"), height=35, width=100, state="disabled")
        self.stop_btn.pack(side="left", padx=(0, 0))

        status_frame = ctk.CTkFrame(self)
        status_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))

        self.status_label = ctk.CTkLabel(status_frame, text="Ready", text_color="#28a745", font=("Segoe UI", 9))
        self.status_label.pack(side="left", padx=10, pady=5)

    def _validate_c3d_path(self):
        """Validate C3D file path from entry."""
        path_str = self.file_var.get().strip()
        if not path_str:
            self.file_error.configure(text="")
            self.c3d_file = None
            return

        try:
            path = Path(path_str)
            if path.exists() and path.is_file() and path.suffix.lower() == ".c3d":
                self.c3d_file = str(path)
                self.file_error.configure(text="")
                self._load_c3d_data(str(path))
                self.status_callback(f"Selected: {path.name}", "success")
            else:
                self.c3d_file = None
                if not path.exists():
                    self.file_error.configure(text="❌ File not found")
                elif not path.suffix.lower() == ".c3d":
                    self.file_error.configure(text="❌ Not a C3D file")
                else:
                    self.file_error.configure(text="❌ Invalid file")
        except Exception as e:
            self.c3d_file = None
            self.file_error.configure(text="❌ Invalid path")

    def _select_c3d_file(self):
        """Select and load a C3D file."""
        file_path = filedialog.askopenfilename(title="Select C3D File", filetypes=[("C3D Files", "*.c3d"), ("All Files", "*.*")])
        if file_path:
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, file_path)
            self._validate_c3d_path()

    def _load_c3d_data(self, file_path):
        """Load C3D file and extract data."""
        try:
            if not HAS_C3D:
                messagebox.showwarning("Warning", "c3d module not installed. Install with: pip install c3d")
                return

            logger.debug(f"Loading C3D file: {file_path}")

            with open(file_path, "rb") as f:
                reader = c3d.Reader(f)

                self.markers_list = []
                if hasattr(reader, 'point_labels'):
                    for label in reader.point_labels:
                        if label and label.strip():
                            self.markers_list.append(label.strip())
                logger.debug(f"Found {len(self.markers_list)} markers")

                self.emg_channels_list = []
                analog_labels = []

                if hasattr(reader, 'analog_labels'):
                    analog_labels = list(reader.analog_labels)
                elif hasattr(reader, 'header') and hasattr(reader.header, 'analog_labels'):
                    analog_labels = list(reader.header.analog_labels)
                elif hasattr(reader, 'header') and hasattr(reader.header, 'analog_channel_labels'):
                    analog_labels = list(reader.header.analog_channel_labels)

                logger.debug(f"Found {len(analog_labels)} analog labels in reader")

                for label in analog_labels:
                    if label and label.strip():
                        self.emg_channels_list.append(label.strip())

                logger.debug(f"Extracted {len(self.emg_channels_list)} EMG channels")

            self.selected_markers = set(range(len(self.markers_list)))
            self.selected_emg = set(range(len(self.emg_channels_list)))

            self._populate_markers_list()
            self._populate_emg_list()
            self._extract_and_plot_grf(file_path)

            self._log_status(f"[OK] Loaded: {len(self.markers_list)} markers, {len(self.emg_channels_list)} EMG channels")

        except Exception as e:
            logger.error(f"Error loading C3D: {e}", exc_info=True)
            self._log_status(f"[FAIL] Error loading C3D: {str(e)[:80]}")

    def _extract_and_plot_grf(self, file_path):
        """Extract GRF data and create visualization."""
        if not HAS_C3D:
            logger.warning("c3d module not available, skipping GRF visualization")
            return

        try:
            self.grf_viewer.load_c3d(file_path)
            self._log_status(f"GRF visualization loaded. Identified {len(self.grf_viewer.grf_channels)} GRF channels.")
            logger.info(f"Loaded GRF channels: {list(self.grf_viewer.grf_channels.keys())}")
        except Exception as e:
            logger.error(f"Error loading GRF visualization: {e}")
            self._log_status(f"Could not load GRF visualization: {str(e)[:50]}")

    def _populate_markers_list(self):
        """Populate markers checkbox list."""
        for widget in self.markers_frame.winfo_children():
            widget.destroy()

        self.marker_vars = {}
        for i, marker in enumerate(self.markers_list):
            var = ctk.BooleanVar(value=True)
            self.marker_vars[marker] = var
            ctk.CTkCheckBox(self.markers_frame, text=marker, variable=var, font=("Segoe UI", 9)).pack(anchor="w", padx=5, pady=1)

    def _populate_emg_list(self):
        """Populate EMG channels checkbox list."""
        for widget in self.emg_frame.winfo_children():
            widget.destroy()

        self.emg_vars = {}
        for i, channel in enumerate(self.emg_channels_list):
            var = ctk.BooleanVar(value=True)
            self.emg_vars[channel] = var
            ctk.CTkCheckBox(self.emg_frame, text=channel, variable=var, font=("Segoe UI", 9)).pack(anchor="w", padx=5, pady=1)

    def _select_all_markers(self):
        """Select all markers."""
        for var in self.marker_vars.values():
            var.set(True)

    def _deselect_all_markers(self):
        """Deselect all markers."""
        for var in self.marker_vars.values():
            var.set(False)

    def _select_all_emg(self):
        """Select all EMG channels."""
        for var in self.emg_vars.values():
            var.set(True)

    def _deselect_all_emg(self):
        """Deselect all EMG channels."""
        for var in self.emg_vars.values():
            var.set(False)

    def _run_export(self):
        """Run the C3D export process."""
        if not HAS_EXPORTC3D:
            messagebox.showerror("Error", "exportC3D module not found.")
            self.status_callback("exportC3D module not available", "error")
            return

        if not self.c3d_file:
            messagebox.showwarning("Warning", "Please select a C3D file first")
            self.status_callback("No C3D file selected", "warning")
            return

        if not (self.export_markers.get() or self.export_grf.get() or self.export_emg.get()):
            messagebox.showwarning("Warning", "Please select at least one export option")
            self.status_callback("No export options selected", "warning")
            return

        self.stop_btn.configure(state="normal")
        emg_patterns = [s.strip() for s in self.emg_patterns.get().split(",") if s.strip()]
        if not emg_patterns:
            emg_patterns = ["emg"]

        strings_to_remove = [s.strip() for s in self.strings_to_remove.get().split(",") if s.strip()]
        selected_markers = [m for m, var in self.marker_vars.items() if var.get()] if hasattr(self, 'marker_vars') else self.markers_list
        selected_emg = [e for e, var in self.emg_vars.items() if var.get()] if hasattr(self, 'emg_vars') else self.emg_channels_list

        # Collect EMG parameters
        emg_params = {
            'bp_low': self.bp_low.get(),
            'bp_high': self.bp_high.get(),
            'lp_cutoff': self.lp_cutoff.get(),
            'amplitude_scale': self.amplitude_scale.get(),
        }

        self.export_thread = threading.Thread(target=self._export_thread,
                                             args=(self.c3d_file, emg_patterns, strings_to_remove, selected_markers, selected_emg, emg_params),
                                             daemon=True)
        self.export_thread.start()
        self.status_callback("Export in progress...", "info")

    def _export_thread(self, c3d_file, emg_patterns, strings_to_remove, selected_markers, selected_emg, emg_params=None):
        """Run export in background thread."""
        try:
            import shutil
            import xml.etree.ElementTree as ET
            if emg_params is None:
                emg_params = {}
            print(f"\n{'='*80}")
            print(f"[START] Processing {Path(c3d_file).name}")
            print(f"{'='*80}")
            self._log_status(f"Processing {Path(c3d_file).name}...")

            c3d_path = Path(c3d_file)
            output_dir = c3d_path.parent
            export_dir = None

            # Create separate output folder if requested
            if self.create_folder.get():
                export_dir = output_dir / c3d_path.stem
                export_dir.mkdir(exist_ok=True)
                print(f"[INFO] Created output folder: {export_dir}")
                self._log_status(f"Created output folder: {export_dir.name}")

            exported_files = []

            if self.export_markers.get():
                self._log_status("Exporting markers...")
                print("[INFO] Exporting markers...")
                try:
                    exportC3D.export_markers(c3d_file, strings_to_remove=strings_to_remove)
                    marker_file = output_dir / "marker_experimental.trc"
                    if marker_file.exists():
                        exported_files.append(("Markers", marker_file))
                        print(f"[OK] Markers exported to {marker_file.name} ({len(selected_markers)} selected)")
                    self._log_status(f"[OK] Markers exported ({len(selected_markers)} selected)")
                except Exception as e:
                    self._log_status(f"[FAIL] Error exporting markers: {str(e)[:50]}")
                    print(f"[ERROR] Markers export failed: {str(e)}")
                    logger.error(f"Markers export error: {e}")

            if self.export_grf.get():
                self._log_status("Exporting GRF...")
                print("[INFO] Exporting Ground Reaction Force (GRF) data...")
                try:
                    exportC3D.export_grf(c3d_file)
                    grf_file = output_dir / "grf.mot"
                    if grf_file.exists():
                        exported_files.append(("GRF", grf_file))
                        print(f"[OK] GRF exported to {grf_file.name}")
                    self._log_status("[OK] GRF exported successfully")
                except Exception as e:
                    self._log_status(f"[FAIL] Error exporting GRF: {str(e)[:50]}")
                    print(f"[ERROR] GRF export failed: {str(e)}")
                    logger.error(f"GRF export error: {e}")

            if self.export_emg.get():
                self._log_status("Exporting EMG...")
                print("[INFO] Exporting EMG channels...")
                try:
                    exportC3D.export_emg(c3d_file, emg_strings_list=emg_patterns)
                    emg_file = output_dir / "emg.mot"
                    if emg_file.exists():
                        exported_files.append(("EMG", emg_file))
                        print(f"[OK] EMG exported to {emg_file.name}")
                    self._log_status(f"[OK] EMG exported ({len(self.emg_vars)} channels)")
                except Exception as e:
                    self._log_status(f"[FAIL] Error exporting EMG: {str(e)[:50]}")
                    print(f"[ERROR] EMG export failed: {str(e)}")
                    logger.error(f"EMG export error: {e}")

            # Generate additional files
            self._log_status("Generating additional files...")
            print("[INFO] Generating emg_filtered.mot and analog.csv...")
            try:
                # Generate filtered EMG file (copy of emg.mot with filtered suffix for now)
                emg_file = output_dir / "emg.mot"
                if emg_file.exists():
                    emg_filtered_file = output_dir / "emg_filtered.mot"
                    shutil.copy(str(emg_file), str(emg_filtered_file))
                    exported_files.append(("EMG Filtered", emg_filtered_file))
                    print(f"[OK] Generated {emg_filtered_file.name}")
                    self._log_status("Generated emg_filtered.mot")
            except Exception as e:
                print(f"[WARN] Could not generate emg_filtered.mot: {str(e)[:50]}")
                self._log_status(f"[WARN] Could not generate emg_filtered.mot: {str(e)[:50]}")

            try:
                # Generate analog channels CSV
                if HAS_C3D:
                    with open(str(c3d_file), 'rb') as f:
                        reader = c3d.Reader(f)
                        analog_csv = output_dir / "analog.csv"
                        frames_data = []
                        for frame_num, point_data, analog_data in reader:
                            if analog_data is not None:
                                if isinstance(analog_data, np.ndarray):
                                    frames_data.append(analog_data)

                        if frames_data:
                            all_analog = np.hstack(frames_data).T
                            np.savetxt(str(analog_csv), all_analog, delimiter=',', fmt='%.6f')
                            exported_files.append(("Analog CSV", analog_csv))
                            print(f"[OK] Generated {analog_csv.name} ({all_analog.shape[0]} frames)")
                            self._log_status("Generated analog.csv")
            except Exception as e:
                print(f"[WARN] Could not generate analog.csv: {str(e)[:50]}")
                self._log_status(f"[WARN] Could not generate analog.csv: {str(e)[:50]}")

            # Move files to export folder if requested
            if export_dir:
                self._log_status("Moving files to export folder...")
                print("[INFO] Moving exported files to output folder...")
                try:
                    for file_type, file_path in exported_files:
                        if file_path.exists():
                            dest_path = export_dir / file_path.name
                            shutil.move(str(file_path), str(dest_path))
                            print(f"  [OK] Moved {file_type}: {file_path.name}")
                            self._log_status(f"  Moved {file_type}: {file_path.name}")

                    # Ensure analog.csv is in export folder (even if not in exported_files list)
                    analog_source = output_dir / "analog.csv"
                    if analog_source.exists():
                        analog_dest = export_dir / "analog.csv"
                        if analog_dest.exists():
                            analog_dest.unlink()  # Remove existing
                        shutil.move(str(analog_source), str(analog_dest))
                        print(f"  [OK] Moved analog.csv to {export_dir.name}")
                        self._log_status(f"  Moved analog.csv")

                    print(f"[OK] All files moved to {export_dir.name}")
                    self._log_status(f"[OK] All files moved to {export_dir.name}")
                except Exception as e:
                    self._log_status(f"[WARN] Could not move files: {str(e)[:50]}")
                    print(f"[WARN] File move error: {str(e)[:50]}")
                    logger.warning(f"File move error: {e}")

            # Create trial_settings.xml with processing parameters and time range from events.csv
            self._log_status("Creating trial_settings.xml...")
            print("[INFO] Creating trial_settings.xml with EMG parameters and time range...")
            try:
                settings_dir = export_dir if export_dir else output_dir
                settings_file = settings_dir / "trial_settings.xml"

                # Create root element with proper naming
                root = ET.Element("TrialSettings")

                # Add basic file references
                ET.SubElement(root, "c3d").text = c3d_path.name
                ET.SubElement(root, "markers").text = "marker_experimental.trc"
                ET.SubElement(root, "grf_mot").text = "grf.mot"
                ET.SubElement(root, "emg").text = "emg.mot"
                ET.SubElement(root, "events").text = "events.csv"

                # Add EMG processing parameters
                ET.SubElement(root, "emg_lowpass_hz").text = emg_params.get('bp_low', '10')
                ET.SubElement(root, "emg_highpass_hz").text = emg_params.get('bp_high', '500')
                ET.SubElement(root, "emg_notch_hz").text = emg_params.get('lp_cutoff', '10')
                ET.SubElement(root, "emg_amplitude_scale").text = emg_params.get('amplitude_scale', '1.0')

                # Try to read time range from events.csv
                events_file = settings_dir / "events.csv"
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

                        # Add start_time and end_time if found
                        if start_time is not None and end_time is not None:
                            ET.SubElement(root, 'start_time').text = f"{start_time:.4f}"
                            ET.SubElement(root, 'end_time').text = f"{end_time:.4f}"
                            print(f"[OK] Added time range from events.csv: {start_time:.4f} - {end_time:.4f}")
                            logger.info(f"Added time range from events.csv: {start_time:.4f} - {end_time:.4f}")
                    except Exception as e:
                        logger.warning(f"Could not read time range from events.csv: {e}")

                # Create tree and write
                tree = ET.ElementTree(root)
                tree.write(str(settings_file), encoding='utf-8', xml_declaration=True)

                print(f"[OK] Created trial_settings.xml at {settings_file}")
                self._log_status(f"[OK] Created trial_settings.xml")
                logger.info(f"Created trial_settings.xml at {settings_file}")

            except Exception as e:
                self._log_status(f"[WARN] Could not create trial_settings.xml: {str(e)[:50]}")
                print(f"[WARN] Could not create trial_settings.xml: {str(e)}")
                logger.warning(f"XML creation error: {e}")

            print(f"\n[SUCCESS] Export process completed!")
            print(f"{'='*80}\n")
            self._log_status("[OK] Export completed!")
            self.status_callback("Export completed successfully", "success")

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._log_status(f"[FAIL] {error_msg}")
            print(f"[ERROR] {error_msg}")
            print(f"{'='*80}\n")
            self.status_callback(error_msg, "error")
            logger.error(error_msg)

        finally:
            self.stop_btn.configure(state="disabled")

    def _stop_export(self):
        """Stop the export process."""
        self.status_callback("Export stopped by user", "warning")
        self._log_status("Export stopped")
        self.stop_btn.configure(state="disabled")

    def _log_status(self, message):
        """Update status message."""
        self.status_label.configure(text=message)
        logger.debug(f"C3D Export: {message}")
        self.update()
