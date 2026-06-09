"""C3D GRF Viewer Widget - Enhanced with marker detection and grf.xml export."""

import customtkinter as ctk
import numpy as np
import pandas as pd
import re
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.config_manager import ConfigManager
from utils.logger import logger
from .grf_phase_detector import GRFPhaseDetector

try:
    import opensim
    HAS_OPENSIM = True
except ImportError:
    HAS_OPENSIM = False


class C3DGRFViewer(ctk.CTkFrame):
    """Enhanced GRF Viewer with marker detection and plate assignment."""

    def __init__(self, parent):
        """Initialize GRF Viewer."""
        super().__init__(parent)

        self.c3d_file = None
        self.grf_data = None
        self.marker_data = None
        self.grf_channels = {}
        self.force_plates = {}
        self.selected_grfs = {}
        self.plate_toggles = {}
        self.crop_start = 0
        self.crop_end = 100

        # Marker and plate assignment
        self.left_foot_markers = []
        self.right_foot_markers = []
        self.selected_left_marker = None
        self.selected_right_marker = None
        self.plate_assignment = {}  # {plate_id: 'left' or 'right'}

        # Distinct colors for each force plate (tab10 colormap)
        self.plate_colors = {
            1: '#1f77b4',  # Blue
            2: '#ff7f0e',  # Orange
            3: '#2ca02c',  # Green
            4: '#d62728',  # Red
            5: '#9467bd',  # Purple
            6: '#8c564b',  # Brown
            7: '#e377c2',  # Pink
            8: '#7f7f7f',  # Gray
            9: '#bcbd22',  # Olive
            10: '#17becf', # Cyan
        }

        self._create_widgets()

    def _create_widgets(self):
        """Create UI widgets with marker selection."""
        # Main layout: 2 columns, 2 rows
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=0, minsize=300)
        self.grid_columnconfigure(1, weight=1)

        # ========== LEFT PANEL ==========
        left_panel = ctk.CTkFrame(self)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        left_panel.grid_rowconfigure(6, weight=1)
        left_panel.grid_columnconfigure(0, weight=1)

        # ===== MARKER SELECTION SECTION =====
        marker_section = ctk.CTkFrame(left_panel)
        marker_section.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        marker_section.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(marker_section, text="Marker Selection:", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, sticky="w", padx=5, pady=5
        )

        # Left foot marker selection
        ctk.CTkLabel(marker_section, text="Left Foot Marker:", font=("Segoe UI", 9)).grid(
            row=1, column=0, sticky="w", padx=5, pady=(5, 2)
        )
        self.left_marker_var = ctk.StringVar(value="LHEE")
        self.left_marker_dropdown = ctk.CTkOptionMenu(
            marker_section,
            variable=self.left_marker_var,
            values=["LHEE", "LTOE", "LANK", "LKNEE", "LHIP"],
            font=("Segoe UI", 9),
            command=self._on_marker_changed
        )
        self.left_marker_dropdown.grid(row=1, column=1, sticky="ew", padx=5, pady=(5, 2))
        marker_section.grid_columnconfigure(1, weight=1)

        # Right foot marker selection
        ctk.CTkLabel(marker_section, text="Right Foot Marker:", font=("Segoe UI", 9)).grid(
            row=2, column=0, sticky="w", padx=5, pady=2
        )
        self.right_marker_var = ctk.StringVar(value="RHEE")
        self.right_marker_dropdown = ctk.CTkOptionMenu(
            marker_section,
            variable=self.right_marker_var,
            values=["RHEE", "RTOE", "RANK", "RKNEE", "RHIP"],
            font=("Segoe UI", 9),
            command=self._on_marker_changed
        )
        self.right_marker_dropdown.grid(row=2, column=1, sticky="ew", padx=5, pady=2)

        # Re-run detection button
        ctk.CTkButton(
            marker_section,
            text="Re-run Detection",
            font=("Segoe UI", 9),
            command=self._on_rerun_detection,
        ).grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=(8, 2))

        # ===== AUTO-CROP SECTION =====
        autocrop_section = ctk.CTkFrame(left_panel)
        autocrop_section.grid(row=0, column=0, sticky="ew", pady=(5, 0))
        autocrop_section.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(autocrop_section, text="Auto-Crop by Movement:", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, sticky="w", padx=5, pady=5
        )

        # Movement type selection
        ctk.CTkLabel(autocrop_section, text="Movement Type:", font=("Segoe UI", 9)).grid(
            row=1, column=0, sticky="w", padx=5, pady=(5, 2)
        )
        self.movement_type_var = ctk.StringVar(value="Running")
        self.movement_dropdown = ctk.CTkOptionMenu(
            autocrop_section,
            variable=self.movement_type_var,
            values=["Running", "Squatting", "Jumping", "Walking"],
            font=("Segoe UI", 9),
        )
        self.movement_dropdown.grid(row=1, column=1, sticky="ew", padx=5, pady=(5, 2))
        autocrop_section.grid_columnconfigure(1, weight=1)

        # Force threshold
        ctk.CTkLabel(autocrop_section, text="Force Threshold (% BW):", font=("Segoe UI", 9)).grid(
            row=2, column=0, sticky="w", padx=5, pady=2
        )
        self.threshold_var = ctk.DoubleVar(value=50)
        self.threshold_slider = ctk.CTkSlider(
            autocrop_section, from_=5, to=95, variable=self.threshold_var
        )
        self.threshold_slider.grid(row=2, column=1, sticky="ew", padx=5, pady=2)

        # Threshold value display
        self.threshold_label = ctk.CTkLabel(autocrop_section, text="50%", text_color="gray", font=("Segoe UI", 8))
        self.threshold_label.grid(row=3, column=0, columnspan=2, sticky="e", padx=5, pady=2)
        self.threshold_slider.configure(command=lambda v: self._update_threshold_label(v))

        # Auto-detect button
        ctk.CTkButton(
            autocrop_section,
            text="Auto-Detect Phases",
            font=("Segoe UI", 9),
            command=self._on_auto_detect_phases,
        ).grid(row=4, column=0, columnspan=2, sticky="ew", padx=5, pady=(8, 5))

        # Detected phases display
        self.phases_label = ctk.CTkLabel(
            autocrop_section,
            text="No phases detected",
            text_color="gray",
            font=("Segoe UI", 8),
            wraplength=280
        )
        self.phases_label.grid(row=5, column=0, columnspan=2, sticky="ew", padx=5, pady=2)

        # Initialize phase detector
        self.phase_detector = GRFPhaseDetector()
        self.detected_phases = {}

        # ===== FORCE PLATES SECTION =====
        header_frame = ctk.CTkFrame(left_panel)
        header_frame.grid(row=1, column=0, sticky="ew", pady=(5, 5))
        header_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header_frame, text="Force Plates:", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, sticky="w", padx=5, pady=5
        )

        button_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        button_frame.grid(row=0, column=1, sticky="e", padx=5)

        ctk.CTkButton(
            button_frame,
            text="All",
            width=40,
            font=("Segoe UI", 9),
            command=self._select_all_channels,
        ).grid(row=0, column=0, padx=2)

        ctk.CTkButton(
            button_frame,
            text="None",
            width=50,
            font=("Segoe UI", 9),
            command=self._deselect_all_channels,
        ).grid(row=0, column=1, padx=2)

        # Scrollable channels frame
        self.channels_scroll_frame = ctk.CTkScrollableFrame(left_panel)
        self.channels_scroll_frame.grid(row=2, column=0, sticky="nsew", pady=5)
        self.channels_scroll_frame.grid_columnconfigure(0, weight=1)

        # Crop controls will be placed below the plot (moved to bottom row)
        # Create crop_frame but don't grid it yet - it will be placed after the plot
        self.crop_frame = ctk.CTkFrame(self)
        self.crop_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self.crop_frame, text="Crop Range:", font=("Segoe UI", 9, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=5, pady=(5, 2)
        )

        self.time_range_label = ctk.CTkLabel(
            self.crop_frame, text="0.00 - 0.00 s", text_color="gray", font=("Segoe UI", 8)
        )
        self.time_range_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=5, pady=2)

        ctk.CTkLabel(self.crop_frame, text="Start:", font=("Segoe UI", 8)).grid(
            row=2, column=0, sticky="w", padx=5, pady=(5, 2)
        )
        self.start_slider = ctk.CTkSlider(
            self.crop_frame, from_=0, to=100, command=lambda v: self._on_crop_slider_change()
        )
        self.start_slider.grid(row=2, column=1, sticky="ew", padx=5, pady=(5, 2))
        self.start_slider.set(0)

        ctk.CTkLabel(self.crop_frame, text="End:", font=("Segoe UI", 8)).grid(
            row=3, column=0, sticky="w", padx=5, pady=2
        )
        self.end_slider = ctk.CTkSlider(
            self.crop_frame, from_=0, to=100, command=lambda v: self._on_crop_slider_change()
        )
        self.end_slider.grid(row=3, column=1, sticky="ew", padx=5, pady=2)
        self.end_slider.set(100)

        ctk.CTkLabel(self.crop_frame, text="Start (s):", font=("Segoe UI", 8)).grid(
            row=4, column=0, sticky="w", padx=5, pady=(5, 2)
        )
        self.start_entry = ctk.CTkEntry(self.crop_frame, width=80, height=24)
        self.start_entry.grid(row=4, column=1, sticky="ew", padx=5, pady=(5, 2))
        self.start_entry.bind("<Return>", lambda e: self._update_crop_from_entries())

        ctk.CTkLabel(self.crop_frame, text="End (s):", font=("Segoe UI", 8)).grid(
            row=5, column=0, sticky="w", padx=5, pady=2
        )
        self.end_entry = ctk.CTkEntry(self.crop_frame, width=80, height=24)
        self.end_entry.grid(row=5, column=1, sticky="ew", padx=5, pady=2)
        self.end_entry.bind("<Return>", lambda e: self._update_crop_from_entries())

        # Export button - moved below crop controls
        export_frame = ctk.CTkFrame(self.crop_frame)
        export_frame.grid(row=6, column=0, columnspan=2, sticky="ew", padx=5, pady=(8, 5))
        export_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            export_frame,
            text="Export GRF.xml",
            font=("Segoe UI", 9),
            command=self._export_grf_xml,
        ).grid(row=0, column=0, sticky="ew")

        # ========== RIGHT PANEL ==========
        self.plot_frame = ctk.CTkFrame(self)
        self.plot_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 5), pady=5)
        self.plot_frame.grid_rowconfigure(0, weight=1)
        self.plot_frame.grid_columnconfigure(0, weight=1)

        # Grid crop controls below the plot (row 1, column 1)
        self.crop_frame.grid(row=1, column=1, sticky="ew", padx=5, pady=(0, 5))

    def load_c3d(self, c3d_file_path):
        """Load and process C3D file using OpenSim."""
        try:
            self.c3d_file = Path(c3d_file_path)

            if not HAS_OPENSIM:
                logger.error("OpenSim module not available")
                return False

            print(f"[INFO] Loading C3D file with OpenSim: {self.c3d_file.name}")

            adapter = opensim.C3DFileAdapter()
            adapter.setLocationForForceExpression(opensim.C3DFileAdapter.ForceLocation_CenterOfPressure)

            c3d_data = adapter.read(str(self.c3d_file))
            forces_table = adapter.getForcesTable(c3d_data)

            time_column = forces_table.getIndependentColumn()
            time_array = np.array(list(time_column))

            forces_table_flat = forces_table.flatten(['x', 'y', 'z'])

            raw_labels = list(forces_table_flat.getColumnLabels())
            labels = self._transform_labels(raw_labels)

            # Extract force data
            matrix = forces_table_flat.getMatrix()
            grf_array = np.array([[matrix.getElt(i, j) for j in range(matrix.ncol())]
                                  for i in range(matrix.nrow())])

            grf_array = self._rotate_data_array(grf_array)

            self.grf_data = pd.DataFrame(grf_array, columns=labels)
            self.grf_data.insert(0, 'time', time_array)

            # Extract marker data
            self._extract_marker_data(c3d_data)

            print(f"[OK] Loaded GRF data: {len(labels)} channels, {len(time_array)} frames")
            logger.info(f"GRF data shape: {self.grf_data.shape}")

            self._organize_channels_by_plate()
            self._detect_plate_assignment()
            self._populate_channel_checkboxes_hierarchical()
            self._update_plot()

            return True

        except Exception as e:
            logger.error(f"Error loading C3D file: {str(e)}")
            print(f"[ERROR] Failed to load C3D: {str(e)}")
            return False

    def _extract_marker_data(self, c3d_data):
        """Extract marker trajectories from C3D data."""
        try:
            markers_table = opensim.C3DFileAdapter.getMarkersTable(c3d_data)
            marker_labels = list(markers_table.getColumnLabels())
            self.left_foot_markers = [m for m in marker_labels if 'L' in m.upper()]
            self.right_foot_markers = [m for m in marker_labels if 'R' in m.upper()]

            print(f"[OK] Found {len(self.left_foot_markers)} left markers, {len(self.right_foot_markers)} right markers")
        except Exception as e:
            logger.warning(f"Could not extract marker data: {str(e)}")

    def _detect_plate_assignment(self):
        """Detect which force plates belong to which foot based on marker positions."""
        try:
            left_marker = self.left_marker_var.get()
            right_marker = self.right_marker_var.get()

            # Try distance-based detection first
            if self._detect_plate_assignment_by_distance(left_marker, right_marker):
                return

            # Fallback to naive split if distance detection fails
            self._detect_plate_assignment_naive()

        except Exception as e:
            logger.warning(f"Plate detection error: {str(e)}, using fallback method")
            self._detect_plate_assignment_naive()

    def _detect_plate_assignment_by_distance(self, left_marker_name, right_marker_name):
        """
        Assign plates based on 3D distance from marker positions to force plate centers.
        Returns True if successful, False if detection failed.
        """
        try:
            if not HAS_OPENSIM or not self.c3d_file:
                return False

            # Re-read C3D to get marker data with force plate info
            adapter = opensim.C3DFileAdapter()
            c3d_data = adapter.read(str(self.c3d_file))

            # Get markers table
            markers_table = adapter.getMarkersTable(c3d_data)
            marker_labels = list(markers_table.getColumnLabels())

            # Check if selected markers exist
            left_exists = any(left_marker_name in label for label in marker_labels)
            right_exists = any(right_marker_name in label for label in marker_labels)

            if not left_exists or not right_exists:
                logger.warning(f"Markers {left_marker_name} or {right_marker_name} not found in C3D")
                return False

            # Get marker trajectories (use first frame as reference)
            left_marker_idx = next((i for i, l in enumerate(marker_labels) if left_marker_name in l), None)
            right_marker_idx = next((i for i, l in enumerate(marker_labels) if right_marker_name in l), None)

            if left_marker_idx is None or right_marker_idx is None:
                return False

            # Extract positions from markers table
            markers_matrix = markers_table.getMatrix()
            # Get first valid frame (skip NaN frames)
            left_pos = None
            right_pos = None

            for frame_idx in range(min(100, markers_matrix.nrow())):  # Check first 100 frames
                left_x = markers_matrix.getElt(frame_idx, left_marker_idx * 3)
                left_y = markers_matrix.getElt(frame_idx, left_marker_idx * 3 + 1)
                left_z = markers_matrix.getElt(frame_idx, left_marker_idx * 3 + 2)

                right_x = markers_matrix.getElt(frame_idx, right_marker_idx * 3)
                right_y = markers_matrix.getElt(frame_idx, right_marker_idx * 3 + 1)
                right_z = markers_matrix.getElt(frame_idx, right_marker_idx * 3 + 2)

                # Skip if NaN (marker occluded)
                if all(v == v for v in [left_x, left_y, left_z, right_x, right_y, right_z]):
                    left_pos = np.array([left_x, left_y, left_z])
                    right_pos = np.array([right_x, right_y, right_z])
                    break

            if left_pos is None or right_pos is None:
                logger.warning("Could not find valid marker frames for distance calculation")
                return False

            # Get force plate centers (approximate as middle of plate)
            # For now, estimate based on plate IDs - ideally read from C3D metadata
            plate_ids = sorted(self.force_plates.keys())
            plate_positions = {}

            # Simple heuristic: plates arranged along Y axis
            for i, pid in enumerate(plate_ids):
                # Estimate plate Y position based on plate index
                plate_positions[pid] = np.array([0, i * 0.4, 0])

            # Assign plates based on closest marker
            self.plate_assignment = {}
            plate_ids_left = []
            plate_ids_right = []

            for pid in plate_ids:
                plate_pos = plate_positions[pid]
                dist_left = np.linalg.norm(left_pos - plate_pos)
                dist_right = np.linalg.norm(right_pos - plate_pos)

                if dist_left < dist_right:
                    self.plate_assignment[pid] = 'left'
                    plate_ids_left.append(pid)
                else:
                    self.plate_assignment[pid] = 'right'
                    plate_ids_right.append(pid)

            logger.info(f"Distance-based assignment: Left={plate_ids_left}, Right={plate_ids_right}")
            return True

        except Exception as e:
            logger.warning(f"Distance-based detection failed: {str(e)}")
            return False

    def _detect_plate_assignment_naive(self):
        """Fallback: assign plates 1,3,5 to left and 2,4,6 to right."""
        plate_ids = sorted(self.force_plates.keys())
        mid_point = len(plate_ids) // 2

        for i, plate_id in enumerate(plate_ids):
            if i < mid_point:
                self.plate_assignment[plate_id] = 'left'
            else:
                self.plate_assignment[plate_id] = 'right'

        logger.info(f"Naive plate assignment: {self.plate_assignment}")

    def _on_marker_changed(self):
        """Handle marker selection change."""
        self._detect_plate_assignment()
        self._populate_channel_checkboxes_hierarchical()
        self._update_plot()

    def _update_threshold_label(self, value: float):
        """Update threshold label display."""
        self.threshold_label.configure(text=f"{int(float(value))}%")

    def _on_rerun_detection(self):
        """Handle re-run detection button click."""
        left_marker = self.left_marker_var.get()
        right_marker = self.right_marker_var.get()
        self._detect_plate_assignment_by_distance(left_marker, right_marker)
        self._populate_channel_checkboxes_hierarchical()
        self._update_plot()
        logger.info("Re-ran plate detection using distance-based algorithm")

    def _on_auto_detect_phases(self):
        """Handle auto-detect phases button click."""
        try:
            if self.grf_data is None or len(self.grf_data) == 0:
                logger.warning("No GRF data loaded for phase detection")
                self.phases_label.configure(text="Error: No GRF data loaded")
                return

            movement_type = self.movement_type_var.get()
            threshold = float(self.threshold_var.get()) / 100.0  # Convert % to fraction

            # Get vertical GRF (Z component) - sum of all plates
            z_columns = [col for col in self.grf_data.columns if col.endswith('_vz')]
            if not z_columns:
                logger.warning("No vertical force columns found")
                self.phases_label.configure(text="Error: No Z-axis data")
                return

            # Sum vertical forces from all plates
            total_vertical = np.zeros(len(self.grf_data))
            for col in z_columns:
                total_vertical += self.grf_data[col].values

            # Detect phases
            if movement_type == "Walking" and len(self.force_plates) >= 2:
                # For walking, need separate left/right data
                # Get left and right vertical forces (based on plate assignment)
                left_vertical = np.zeros(len(self.grf_data))
                right_vertical = np.zeros(len(self.grf_data))

                for plate_id, leg in self.plate_assignment.items():
                    col_name = f"ground_force_{plate_id}_vz"
                    if col_name in self.grf_data.columns:
                        if leg == 'left':
                            left_vertical += self.grf_data[col_name].values
                        else:
                            right_vertical += self.grf_data[col_name].values

                self.detected_phases = self.phase_detector.detect_phases(
                    movement_type, left_vertical, right_vertical, threshold
                )
            else:
                self.detected_phases = self.phase_detector.detect_phases(
                    movement_type, total_vertical, threshold=threshold
                )

            # Display detected phases
            if self.detected_phases:
                phase_text = f"{movement_type}: "
                for phase_type, phases in self.detected_phases.items():
                    if phases:
                        phase_text += f"\n{phase_type}: {len(phases)} detected"
                self.phases_label.configure(text=phase_text)
                logger.info(f"Detected phases for {movement_type}: {self.detected_phases}")
            else:
                self.phases_label.configure(text="No phases detected")

            # Update plot with phase markers
            self._update_plot()

        except Exception as e:
            logger.error(f"Error detecting phases: {str(e)}")
            self.phases_label.configure(text=f"Error: {str(e)[:30]}")

    def _transform_labels(self, labels):
        """Transform labels from compact format to descriptive format."""
        transformed = []
        mapping = {
            'f': ('ground_force', 'v'),
            'p': ('ground_force', 'p'),
            'm': ('ground_moment', 'm'),
        }

        for label in labels:
            if len(label) >= 3 and label[0] in mapping and label[-1] in 'xyz':
                original_prefix = label[0]
                number = label[1:-1]
                axis = label[-1]

                new_prefix, new_suffix = mapping[original_prefix]
                new_label = f'{new_prefix}_{number}_{new_suffix}{axis}'
                transformed.append(new_label)
            else:
                transformed.append(label)

        return transformed

    def _rotate_data_array(self, data_array, axis='x', degrees=180):
        """Rotate force/moment data around specified axis."""
        try:
            radians = np.radians(degrees)
            cos_a = np.cos(radians)
            sin_a = np.sin(radians)

            if axis.lower() == 'x':
                rotation_matrix = np.array([
                    [1, 0, 0],
                    [0, cos_a, -sin_a],
                    [0, sin_a, cos_a]
                ])
            elif axis.lower() == 'y':
                rotation_matrix = np.array([
                    [cos_a, 0, sin_a],
                    [0, 1, 0],
                    [-sin_a, 0, cos_a]
                ])
            elif axis.lower() == 'z':
                rotation_matrix = np.array([
                    [cos_a, -sin_a, 0],
                    [sin_a, cos_a, 0],
                    [0, 0, 1]
                ])
            else:
                return data_array

            rotated_array = data_array.copy()
            for col_start in range(0, data_array.shape[1], 3):
                if col_start + 3 <= data_array.shape[1]:
                    vec_data = data_array[:, col_start:col_start+3]
                    rotated_vec = vec_data @ rotation_matrix.T
                    rotated_array[:, col_start:col_start+3] = rotated_vec

            return rotated_array

        except Exception as e:
            logger.warning(f"Could not rotate data: {str(e)}")
            return data_array

    def _organize_channels_by_plate(self):
        """Organize channels by force plate and axis."""
        self.force_plates = {}
        self.selected_grfs = {}

        if self.grf_data is None or len(self.grf_data) == 0:
            logger.warning("No GRF data loaded")
            return

        force_pattern = re.compile(r"ground_force_(\d+)_v([xyz])$")

        for col in self.grf_data.columns:
            if col == 'time':
                continue

            match = force_pattern.match(col)
            if match:
                plate_id = int(match.group(1))
                axis = match.group(2).upper()

                if plate_id not in self.force_plates:
                    self.force_plates[plate_id] = {}
                    self.plate_toggles[plate_id] = True

                self.force_plates[plate_id][axis] = {
                    'data': self.grf_data[col].values,
                    'label': col
                }
                self.selected_grfs[col] = True

        logger.info(f"Organized {len(self.force_plates)} force plates")

    def _populate_channel_checkboxes_hierarchical(self):
        """Create hierarchical checkboxes with left/right foot labels."""
        for widget in self.channels_scroll_frame.winfo_children():
            widget.destroy()

        if not self.force_plates:
            msg = ctk.CTkLabel(self.channels_scroll_frame, text="No GRF channels", text_color="gray")
            msg.pack(anchor="w", padx=5, pady=10)
            return

        for plate_id in sorted(self.force_plates.keys()):
            leg_label = self.plate_assignment.get(plate_id, 'unknown').capitalize()
            plate_var = ctk.BooleanVar(value=self.plate_toggles.get(plate_id, True))
            plate_checkbox = ctk.CTkCheckBox(
                self.channels_scroll_frame,
                text=f"Force Plate {plate_id} ({leg_label})",
                variable=plate_var,
                font=("Segoe UI", 10, "bold"),
                command=lambda pid=plate_id, var=plate_var: self._on_plate_toggle(pid, var),
            )
            plate_checkbox.pack(anchor="w", padx=5, pady=(8, 2))

            for axis in sorted(self.force_plates[plate_id].keys()):
                col_label = self.force_plates[plate_id][axis]['label']
                axis_var = ctk.BooleanVar(value=self.selected_grfs.get(col_label, True))

                axis_checkbox = ctk.CTkCheckBox(
                    self.channels_scroll_frame,
                    text=f"  Axis {axis}",
                    variable=axis_var,
                    font=("Segoe UI", 9),
                    command=lambda cn=col_label, var=axis_var: self._on_channel_toggle(cn, var),
                )
                axis_checkbox.pack(anchor="w", padx=20, pady=1)

                self.selected_grfs[col_label] = axis_var

    def _on_plate_toggle(self, plate_id, var):
        """Handle plate-level checkbox toggle."""
        self.plate_toggles[plate_id] = var.get()
        for axis in self.force_plates[plate_id].keys():
            col_label = self.force_plates[plate_id][axis]['label']
            if col_label in self.selected_grfs:
                self.selected_grfs[col_label].set(var.get())
        self._update_plot()

    def _on_channel_toggle(self, channel_name, var):
        """Handle channel-level checkbox toggle."""
        self.selected_grfs[channel_name] = var.get()
        self._update_plot()

    def _select_all_channels(self):
        """Select all channels."""
        for var in self.selected_grfs.values():
            if hasattr(var, 'set'):
                var.set(True)
        for plate_id in self.plate_toggles:
            self.plate_toggles[plate_id] = True
        self._update_plot()

    def _deselect_all_channels(self):
        """Deselect all channels."""
        for var in self.selected_grfs.values():
            if hasattr(var, 'set'):
                var.set(False)
        for plate_id in self.plate_toggles:
            self.plate_toggles[plate_id] = False
        self._update_plot()

    def _on_crop_slider_change(self):
        """Handle crop slider change."""
        self.crop_start = int(self.start_slider.get())
        self.crop_end = int(self.end_slider.get())
        self._update_time_display()
        self._update_plot()

    def _update_time_display(self):
        """Update time display."""
        if self.grf_data is None or len(self.grf_data) == 0:
            return

        time_values = self.grf_data['time'].values
        total_time = time_values[-1] - time_values[0]

        if total_time <= 0:
            total_time = 1.0

        start_time = (self.crop_start / 100.0) * total_time
        end_time = (self.crop_end / 100.0) * total_time

        self.time_range_label.configure(text="{:.2f} - {:.2f} s".format(start_time, end_time))
        self.start_entry.delete(0, "end")
        self.start_entry.insert(0, "{:.2f}".format(start_time))
        self.end_entry.delete(0, "end")
        self.end_entry.insert(0, "{:.2f}".format(end_time))

    def _update_crop_from_entries(self):
        """Update crop from entries."""
        try:
            if self.grf_data is None or len(self.grf_data) == 0:
                return

            time_values = self.grf_data['time'].values
            total_time = time_values[-1] - time_values[0]

            if total_time <= 0:
                total_time = 1.0

            start_s = float(self.start_entry.get())
            end_s = float(self.end_entry.get())
            start_pct = int((start_s / total_time) * 100)
            end_pct = int((end_s / total_time) * 100)

            if 0 <= start_pct < end_pct <= 100:
                self.crop_start = start_pct
                self.crop_end = end_pct
                self.start_slider.set(self.crop_start)
                self.end_slider.set(self.crop_end)
                self._update_plot()
        except:
            pass

    def _update_plot(self):
        """Update GRF plot with 3 subplots (X, Y, Z)."""
        for widget in self.plot_frame.winfo_children():
            widget.destroy()

        selected = [ch for ch, var in self.selected_grfs.items()
                   if hasattr(var, 'get') and var.get()]

        if not selected or not self.force_plates or self.grf_data is None:
            label = ctk.CTkLabel(self.plot_frame, text="No channels selected", text_color="gray")
            label.grid(row=0, column=0, sticky="nsew")
            return

        try:
            time_values = self.grf_data['time'].values
            total_samples = len(time_values)

            start_idx = int((self.crop_start / 100.0) * total_samples)
            end_idx = int((self.crop_end / 100.0) * total_samples)

            start_idx = max(0, min(start_idx, total_samples - 1))
            end_idx = max(start_idx + 1, min(end_idx, total_samples))

            time_crop = time_values[start_idx:end_idx]

            # Create 3 subplots (X, Y, Z)
            fig, axes = plt.subplots(3, 1, figsize=(13, 10), dpi=80)
            axes = np.atleast_1d(axes)

            axes_specs = [
                ('X', 'vx', 0, 'Lateral Force'),
                ('Y', 'vy', 1, 'Anterior-Posterior Force'),
                ('Z', 'vz', 2, 'Vertical Force'),
            ]

            plate_ids = sorted(self.force_plates.keys())

            for axis_letter, column_suffix, subplot_idx, axis_label in axes_specs:
                ax = axes[subplot_idx]

                # Add shading for cropped regions (before and after crop range)
                if start_idx > 0:
                    # Shade the region before the crop start
                    ax.axvspan(time_values[0], time_crop[0], alpha=0.1, color='gray', zorder=0)

                if end_idx < len(time_values):
                    # Shade the region after the crop end
                    ax.axvspan(time_crop[-1], time_values[-1], alpha=0.1, color='gray', zorder=0)

                for pid in plate_ids:
                    column_name = f"ground_force_{pid}_{column_suffix}"

                    if column_name in self.grf_data.columns and column_name in selected:
                        data = self.grf_data[column_name].iloc[start_idx:end_idx].values

                        # Color based on force plate ID (unique color per plate)
                        color = self.plate_colors.get(pid, '#000000')  # Default to black if > 10 plates
                        leg = self.plate_assignment.get(pid, 'unknown')

                        ax.plot(
                            time_crop, data,
                            linewidth=2.0,
                            color=color,
                            label=f'Plate {pid} ({leg.capitalize()})',
                            alpha=0.8
                        )

                # Add phase markers if detected
                if self.detected_phases:
                    for phase_type, phases in self.detected_phases.items():
                        if phases and isinstance(phases, list) and len(phases) > 0:
                            # phases is a list of (start_idx, end_idx) tuples
                            for phase_start_idx, phase_end_idx in phases:
                                # Check if phase overlaps with current crop range
                                if phase_end_idx >= start_idx and phase_start_idx <= end_idx:
                                    # Add light shaded region for each phase
                                    phase_color = self._get_phase_color(phase_type)
                                    # Map indices to time values
                                    phase_start_idx_cropped = max(0, phase_start_idx - start_idx)
                                    phase_end_idx_cropped = min(len(time_crop), phase_end_idx - start_idx)
                                    if phase_start_idx_cropped < len(time_crop) and phase_end_idx_cropped > 0:
                                        time_start = time_crop[phase_start_idx_cropped] if phase_start_idx_cropped < len(time_crop) else time_crop[0]
                                        time_end = time_crop[min(phase_end_idx_cropped - 1, len(time_crop) - 1)]
                                        if time_end > time_start:
                                            ax.axvspan(time_start, time_end, alpha=0.15, color=phase_color)

                # Format
                ax.set_ylabel(axis_label + ' (N)', fontsize=9, fontweight='bold')
                ax.grid(True, alpha=0.3, linestyle='--')
                ax.axhline(y=0, color='gray', linestyle='-', alpha=0.5, linewidth=0.8)
                ax.legend(fontsize=8, loc='upper left')

            axes[0].set_title('Ground Reaction Forces - By Component and Leg', fontsize=11, fontweight='bold')
            axes[-1].set_xlabel('Time (s)', fontsize=10, fontweight='bold')

            fig.tight_layout()
            canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
            canvas.draw()
            canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        except Exception as e:
            logger.error(f"Error updating plot: {str(e)}")
            label = ctk.CTkLabel(
                self.plot_frame,
                text=f"Error rendering plot: {str(e)[:50]}",
                text_color="red"
            )
            label.grid(row=0, column=0, sticky="nsew")

    def _get_phase_color(self, phase_type: str) -> str:
        """Get a color for phase visualization."""
        phase_colors = {
            'contact': '#1f77b4',      # Blue
            'flight': '#ff7f0e',       # Orange
            'descent': '#2ca02c',      # Green
            'bottom': '#d62728',       # Red
            'ascent': '#9467bd',       # Purple
            'landing': '#8c564b',      # Brown
            'propulsion': '#e377c2',   # Pink
            'takeoff': '#7f7f7f',      # Gray
            'double_support': '#bcbd22',  # Olive
            'single_support_l': '#17becf', # Cyan
            'single_support_r': '#ff9896', # Light red
            'swing': '#c5b0d5'         # Light purple
        }
        return phase_colors.get(phase_type.lower(), '#cccccc')

    def _export_grf_xml(self):
        """Export grf.xml with proper plate assignments."""
        try:
            if not self.c3d_file or not self.force_plates:
                print("[ERROR] No C3D file loaded or no force plates detected")
                return

            # Create ExternalForces XML
            external_loads = ET.Element('ExternalLoads')
            external_loads.set('name', 'externalloads')

            objects = ET.SubElement(external_loads, 'objects')

            # Map body names for calcn (calcaneus) bodies
            body_mapping = {
                'left': 'calcn_l',
                'right': 'calcn_r'
            }

            grf_count = {}
            for leg in ['left', 'right']:
                grf_count[leg] = 0

            for plate_id in sorted(self.force_plates.keys()):
                leg = self.plate_assignment.get(plate_id, 'unknown')
                if leg not in body_mapping:
                    continue

                grf_count[leg] += 1
                body_name = body_mapping[leg]
                name_suffix = f"{leg[0].upper()}_{plate_id}"

                external_force = ET.SubElement(objects, 'ExternalForce')
                external_force.set('name', f'grf_{name_suffix}')

                # Add child elements
                applied_to_body = ET.SubElement(external_force, 'applied_to_body')
                applied_to_body.text = body_name

                force_expr = ET.SubElement(external_force, 'force_expressed_in_body')
                force_expr.text = 'ground'

                point_expr = ET.SubElement(external_force, 'point_expressed_in_body')
                point_expr.text = 'ground'

                force_id = ET.SubElement(external_force, 'force_identifier')
                force_id.text = f'ground_force_{plate_id}_v'

                point_id = ET.SubElement(external_force, 'point_identifier')
                point_id.text = f'ground_force_{plate_id}_p'

                torque_id = ET.SubElement(external_force, 'torque_identifier')
                torque_id.text = f'ground_moment_{plate_id}_m'

                data_source = ET.SubElement(external_force, 'data_source_name')
                data_source.text = ''

            groups = ET.SubElement(external_loads, 'groups')

            datafile = ET.SubElement(external_loads, 'datafile')
            datafile.text = 'grf.mot'

            kinem_file = ET.SubElement(external_loads, 'external_loads_model_kinematics_file')
            kinem_file.text = ''

            cutoff = ET.SubElement(external_loads, 'lowpass_cutoff_frequency_for_load_kinematics')
            cutoff.text = '6'

            # Pretty print
            xml_str = minidom.parseString(ET.tostring(external_loads)).toprettyxml(indent="   ")
            xml_str = '\n'.join([line for line in xml_str.split('\n') if line.strip()])

            # Add XML declaration
            xml_output = '<?xml version="1.0" encoding="utf-8"?>\n<OpenSimDocument Version="40000">\n'
            xml_output += xml_str.replace('<?xml version="1.0" ?>\n', '').replace('<ExternalLoads', '   <ExternalLoads')
            xml_output += '\n</OpenSimDocument>'

            # Save
            output_file = self.c3d_file.parent / 'grf.xml'
            with open(output_file, 'w') as f:
                f.write(xml_output)

            print(f"[OK] Exported grf.xml to {output_file}")
            logger.info(f"GRF XML export: {len(self.force_plates)} force plates assigned")

        except Exception as e:
            logger.error(f"Error exporting grf.xml: {str(e)}")
            print(f"[ERROR] Export failed: {str(e)}")
