"""Model Scaling Tab - OpenSim Scale Tool interface with marker weight adjustment."""

import customtkinter as ctk
from pathlib import Path
import sys
import os
import threading
from tkinter import filedialog, messagebox
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.config_manager import ConfigManager
from utils.logger import logger
from utils.model_scaler import ModelScaler
from settings import BatchSettings
marker_weights = BatchSettings.marker_weights


class ModelScalingTab(ctk.CTkFrame):
    """Tab for OpenSim model scaling with marker weight configuration."""

    def __init__(self, parent, config_manager: ConfigManager, status_callback):
        """Initialize Model Scaling Tab."""
        super().__init__(parent)
        self.config_manager = config_manager
        self.status_callback = status_callback

        # State
        self.template_model_path = None
        self.markerset_path = None
        self.trc_file_path = None
        self.destination_path = None
        self.markers_from_trc = {}  # marker_name -> frame_count
        self.marker_weight_vars = {}  # marker_name -> CTkVariable

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create UI widgets."""
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ===== TOP: Title and Session Info =====
        top_frame = ctk.CTkFrame(self)
        top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        top_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top_frame, text="Model Scaling", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )

        # ===== INPUT PATHS SECTION =====
        input_frame = ctk.CTkFrame(self)
        input_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        input_frame.grid_columnconfigure(1, weight=1)

        # Template Model Path
        ctk.CTkLabel(input_frame, text="Template Model (.osim):", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, sticky="w", padx=(0, 5), pady=(10, 5)
        )
        self.template_model_var = ctk.StringVar(value="")
        template_entry = ctk.CTkEntry(input_frame, textvariable=self.template_model_var, placeholder_text="Select template model")
        template_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=(10, 5))

        ctk.CTkButton(
            input_frame,
            text="Browse",
            width=80,
            command=self._browse_template_model
        ).grid(row=0, column=2, padx=5, pady=(10, 5))

        # Markerset Path (Optional)
        ctk.CTkLabel(input_frame, text="Markerset (.xml) [Optional]:", font=("Segoe UI", 10, "bold")).grid(
            row=1, column=0, sticky="w", padx=(0, 5), pady=(0, 5)
        )
        self.markerset_var = ctk.StringVar(value="")
        markerset_entry = ctk.CTkEntry(input_frame, textvariable=self.markerset_var, placeholder_text="Select markerset or use model's default")
        markerset_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=(0, 5))

        ctk.CTkButton(
            input_frame,
            text="Browse",
            width=80,
            command=self._browse_markerset
        ).grid(row=1, column=2, padx=5, pady=(0, 5))

        # TRC File for Scaling
        ctk.CTkLabel(input_frame, text="TRC File for Scaling:", font=("Segoe UI", 10, "bold")).grid(
            row=2, column=0, sticky="w", padx=(0, 5), pady=(0, 5)
        )
        self.trc_var = ctk.StringVar(value="")
        trc_entry = ctk.CTkEntry(input_frame, textvariable=self.trc_var, placeholder_text="Select TRC file for scaling")
        trc_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=(0, 5))

        ctk.CTkButton(
            input_frame,
            text="Browse",
            width=80,
            command=self._browse_trc_file
        ).grid(row=2, column=2, padx=5, pady=(0, 5))

        # Destination Path (Full file path with .osim filename)
        ctk.CTkLabel(input_frame, text="Output Model (.osim):", font=("Segoe UI", 10, "bold")).grid(
            row=3, column=0, sticky="w", padx=(0, 5), pady=(0, 10)
        )
        self.destination_var = ctk.StringVar(value="")
        dest_entry = ctk.CTkEntry(input_frame, textvariable=self.destination_var, placeholder_text="Path for output model (e.g., /folder/scaled_model.osim)")
        dest_entry.grid(row=3, column=1, sticky="ew", padx=5, pady=(0, 10))

        ctk.CTkButton(
            input_frame,
            text="Browse",
            width=80,
            command=self._browse_destination
        ).grid(row=3, column=2, padx=5, pady=(0, 10))

        # Load TRC Button
        ctk.CTkButton(
            input_frame,
            text="Load Markers from TRC",
            fg_color="#0084ff",
            command=self._load_trc_markers,
            font=("Segoe UI", 10, "bold"),
            height=28
        ).grid(row=4, column=0, columnspan=3, sticky="ew", pady=(5, 10))

        # ===== MARKERS PANEL =====
        markers_label_frame = ctk.CTkFrame(self)
        markers_label_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 5))
        markers_label_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(markers_label_frame, text="Marker Weights", font=("Segoe UI", 12, "bold")).pack(side="left", anchor="w")

        # Reset Button
        ctk.CTkButton(
            markers_label_frame,
            text="Reset to Default",
            width=120,
            height=24,
            font=("Segoe UI", 9),
            command=self._reset_weights
        ).pack(side="right", anchor="e", padx=5)

        # Markers scrollable frame
        self.markers_frame = ctk.CTkScrollableFrame(self, corner_radius=8)
        self.markers_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.markers_frame.grid_columnconfigure(0, weight=1)

        # Empty state message
        self.empty_label = ctk.CTkLabel(
            self.markers_frame,
            text="Load a TRC file to see available markers",
            text_color="#888888",
            font=("Segoe UI", 9)
        )
        self.empty_label.pack(pady=20)

        # ===== BOTTOM: Action Buttons =====
        button_frame = ctk.CTkFrame(self)
        button_frame.grid(row=4, column=0, sticky="ew", padx=10, pady=10)
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        self.scale_btn = ctk.CTkButton(
            button_frame,
            text="[RUN] Scale Model",
            fg_color="#28a745",
            hover_color="#218838",
            font=("Segoe UI", 11, "bold"),
            height=40,
            command=self._run_scaling
        )
        self.scale_btn.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self.stop_btn = ctk.CTkButton(
            button_frame,
            text="[STOP] Cancel",
            fg_color="#dc3545",
            hover_color="#c82333",
            font=("Segoe UI", 11),
            height=40,
            command=self._stop_scaling,
            state="disabled"
        )
        self.stop_btn.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        # Status label
        self.status_label = ctk.CTkLabel(button_frame, text="Ready", text_color="#28a745", font=("Segoe UI", 9))
        self.status_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 0))

    def _browse_template_model(self) -> None:
        """Browse for template model file."""
        file = filedialog.askopenfilename(
            title="Select Template OpenSim Model",
            filetypes=[("OpenSim Models", "*.osim"), ("All Files", "*.*")]
        )
        if file:
            self.template_model_var.set(file)
            logger.info(f"Template model selected: {file}")

    def _browse_markerset(self) -> None:
        """Browse for markerset file."""
        file = filedialog.askopenfilename(
            title="Select Markerset File",
            filetypes=[("XML Files", "*.xml"), ("All Files", "*.*")]
        )
        if file:
            self.markerset_var.set(file)
            logger.info(f"Markerset selected: {file}")

    def _browse_trc_file(self) -> None:
        """Browse for TRC file."""
        file = filedialog.askopenfilename(
            title="Select TRC File for Scaling",
            filetypes=[("TRC Files", "*.trc"), ("All Files", "*.*")]
        )
        if file:
            self.trc_var.set(file)
            logger.info(f"TRC file selected: {file}")

    def _browse_destination(self) -> None:
        """Browse for destination file path."""
        # Get current template model name to suggest output name
        template_path = self.template_model_var.get()
        initial_name = "scaled_model.osim"
        initial_dir = ""

        if template_path and os.path.exists(template_path):
            initial_dir = os.path.dirname(template_path)
            base_name = os.path.splitext(os.path.basename(template_path))[0]
            initial_name = f"{base_name}_scaled.osim"

        file_path = filedialog.asksaveasfilename(
            title="Select Output Model Path",
            initialdir=initial_dir,
            initialfile=initial_name,
            defaultextension=".osim",
            filetypes=[("OpenSim Models", "*.osim"), ("All Files", "*.*")]
        )
        if file_path:
            self.destination_var.set(file_path)
            logger.info(f"Destination file selected: {file_path}")

    def _load_trc_markers(self) -> None:
        """Load markers from TRC file."""
        trc_path = self.trc_var.get()
        if not trc_path or not os.path.exists(trc_path):
            messagebox.showwarning("Error", "Please select a valid TRC file")
            return

        try:
            markers = self._parse_trc_file(trc_path)
            if not markers:
                messagebox.showwarning("Error", "No markers found in TRC file")
                return

            self.markers_from_trc = markers
            self._populate_markers_panel()
            self.status_callback(f"Loaded {len(markers)} markers from TRC", "success")
            logger.info(f"Loaded {len(markers)} markers from {trc_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to parse TRC file: {str(e)}")
            logger.error(f"TRC parsing error: {e}", exc_info=True)

    def _parse_trc_file(self, trc_path: str) -> dict:
        """
        Parse TRC file and extract marker names.

        Args:
            trc_path: Path to TRC file

        Returns:
            Dictionary of marker_name -> frame_count
        """
        markers = {}
        try:
            with open(trc_path, 'r') as f:
                lines = f.readlines()

            # Find header line with marker names (usually line 3)
            for i, line in enumerate(lines):
                if line.strip().startswith('Frame#'):
                    # Next line has marker names
                    marker_line = lines[i + 1].strip()
                    # Parse marker names (X Y Z for each marker)
                    parts = marker_line.split()
                    current_marker = None
                    for part in parts:
                        if part in ['X', 'Y', 'Z']:
                            continue
                        if part != 'Frame#' and part != 'Time':
                            if current_marker != part:
                                current_marker = part
                                markers[current_marker] = 0
                    break

            return markers

        except Exception as e:
            logger.error(f"Error parsing TRC file: {e}")
            raise

    def _populate_markers_panel(self) -> None:
        """Populate markers panel with marker weights."""
        # Clear existing widgets
        for widget in self.markers_frame.winfo_children():
            widget.destroy()

        self.marker_weight_vars = {}

        if not self.markers_from_trc:
            self.empty_label.pack(pady=20)
            return

        # Remove empty label if present
        if hasattr(self, 'empty_label'):
            self.empty_label.pack_forget()

        # Create header
        header_frame = ctk.CTkFrame(self.markers_frame)
        header_frame.pack(fill="x", padx=10, pady=(10, 5))
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_columnconfigure(1, weight=0)

        ctk.CTkLabel(header_frame, text="Marker Name", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", padx=5)
        ctk.CTkLabel(header_frame, text="Weight", font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="e", padx=5)

        # Create marker entries
        for i, marker_name in enumerate(sorted(self.markers_from_trc.keys())):
            marker_frame = ctk.CTkFrame(self.markers_frame)
            marker_frame.pack(fill="x", padx=10, pady=2)
            marker_frame.grid_columnconfigure(0, weight=1)
            marker_frame.grid_columnconfigure(1, weight=0)

            # Marker name label
            ctk.CTkLabel(marker_frame, text=marker_name, font=("Segoe UI", 9)).grid(
                row=0, column=0, sticky="w", padx=5
            )

            # Weight input
            default_weight = marker_weights.get(marker_name, 1.0)
            weight_var = ctk.DoubleVar(value=default_weight)
            self.marker_weight_vars[marker_name] = weight_var

            weight_entry = ctk.CTkEntry(
                marker_frame,
                textvariable=weight_var,
                width=80,
                font=("Segoe UI", 9)
            )
            weight_entry.grid(row=0, column=1, sticky="e", padx=5)

    def _reset_weights(self) -> None:
        """Reset all weights to default values."""
        for marker_name, weight_var in self.marker_weight_vars.items():
            default_weight = marker_weights.get(marker_name, 1.0)
            weight_var.set(default_weight)
        self.status_callback("Weights reset to default", "success")
        logger.info("Marker weights reset to default")

    def _run_scaling(self) -> None:
        """Run the scaling process."""
        # Validation
        if not self.template_model_var.get() or not os.path.exists(self.template_model_var.get()):
            messagebox.showerror("Error", "Please select a valid template model")
            return

        if not self.trc_var.get() or not os.path.exists(self.trc_var.get()):
            messagebox.showerror("Error", "Please select a valid TRC file")
            return

        if not self.destination_var.get():
            messagebox.showerror("Error", "Please specify an output model path (.osim file)")
            return

        # Validate destination path ends with .osim
        dest_path = self.destination_var.get()
        if not dest_path.lower().endswith('.osim'):
            messagebox.showerror("Error", "Output path must end with .osim")
            return

        # Check that destination directory exists
        dest_dir = os.path.dirname(dest_path)
        if dest_dir and not os.path.exists(dest_dir):
            messagebox.showerror("Error", f"Destination directory does not exist: {dest_dir}")
            return

        if not self.marker_weight_vars:
            messagebox.showerror("Error", "Please load markers from TRC first")
            return

        # Disable buttons
        self.scale_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")

        # Get weights dictionary
        weights_dict = {name: var.get() for name, var in self.marker_weight_vars.items()}

        # Run in background thread
        self.scaling_thread = threading.Thread(
            target=self._run_scaling_thread,
            args=(
                self.template_model_var.get(),
                self.markerset_var.get() or None,
                self.trc_var.get(),
                self.destination_var.get(),
                weights_dict
            ),
            daemon=True
        )
        self.scaling_thread.start()
        self.status_callback("Scaling in progress...", "info")

    def _run_scaling_thread(self, template_model, markerset, trc_file, output_file_path, weights):
        """Run scaling in background thread."""
        try:
            self.status_label.configure(text="Initializing scaler...", text_color="#ffc107")
            self.status_callback("Initializing model scaler...", "info")

            # Extract directory and filename from the full output path
            destination_dir = os.path.dirname(output_file_path)
            if not destination_dir:
                destination_dir = os.getcwd()

            # Initialize ModelScaler with destination directory
            scaler = ModelScaler(template_model, trc_file, destination_dir)
            # Store the desired output filename
            scaler.output_model_filename = os.path.basename(output_file_path)

            # Step 1: Calculate scale factors
            self.status_label.configure(text="Calculating scale factors...", text_color="#ffc107")
            self.status_callback("Calculating scale factors from markers...", "info")
            logger.info(f"Using marker weights: {weights}")

            scale_factors = scaler.calculate_scale_factors(weights, markerset)
            logger.info(f"Calculated scale factors: {scale_factors}")

            # Step 2: Create setup XML
            self.status_label.configure(text="Creating setup files...", text_color="#ffc107")
            self.status_callback("Creating OpenSim Scale Tool setup...", "info")

            setup_xml = scaler.create_scale_setup_xml(weights, scale_factors, markerset, output_filename=os.path.basename(output_file_path))
            logger.info(f"Created setup XML: {setup_xml}")

            # Step 3: Run scaling
            self.status_label.configure(text="Running scale tool...", text_color="#ffc107")
            self.status_callback("Running OpenSim Scale Tool...", "info")

            scaled_model, final_factors = scaler.run_scale(weights, markerset)
            logger.info(f"Scaling completed: {scaled_model}")
            logger.info(f"Final scale factors: {final_factors}")

            # Verify output file exists at the specified location
            if not os.path.exists(output_file_path):
                logger.warning(f"Output file not at specified path {output_file_path}, checking {scaled_model}")

            # Success!
            self.status_callback("✓ Model scaling completed successfully", "success")
            self.status_label.configure(text="Scaling complete!", text_color="#28a745")
            logger.info(f"Scaled model saved to: {output_file_path}")

            result_msg = f"""Scaling completed successfully!

Scaled Model: {scaled_model}

Scale Factors:
"""
            for segment, factor in sorted(final_factors.items()):
                result_msg += f"  {segment}: {factor:.4f}\n"

            messagebox.showinfo("Success", result_msg)

        except Exception as e:
            error_msg = f"Scaling failed: {str(e)}"
            self.status_callback(error_msg, "error")
            self.status_label.configure(text=f"Error: {str(e)[:50]}", text_color="#dc3545")
            logger.error(f"Scaling error: {e}", exc_info=True)
            messagebox.showerror("Error", f"Model scaling failed:\n\n{str(e)}")

        finally:
            self.scale_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")

    def _stop_scaling(self) -> None:
        """Stop the scaling process."""
        self.status_callback("Scaling cancelled", "warning")
        self.status_label.configure(text="Cancelled", text_color="#ffc107")
        logger.info("Model scaling cancelled by user")
        self.scale_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
