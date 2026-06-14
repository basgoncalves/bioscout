"""EMG Processing Tab - Advanced EMG signal processing with visualization."""

import customtkinter as ctk
from pathlib import Path
import sys
import numpy as np
import os
from tkinter import filedialog, messagebox

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.config_manager import ConfigManager

try:
    from scipy import signal
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


class EMGProcessingTab(ctk.CTkFrame):
    """Tab for advanced EMG signal processing with live visualization."""

    def __init__(self, parent, config_manager: ConfigManager, status_callback):
        """Initialize EMG Processing Tab."""
        super().__init__(parent)
        self.config_manager = config_manager
        self.status_callback = status_callback

        # Data storage
        self.emg_data = None
        self.emg_file_path = None
        self.original_data = None
        self.processed_data = None
        self.sampling_rate = 1000
        self.channel_names = []
        self.processing_history = []
        self.selected_channels = set()  # Track which channels to display

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create UI widgets."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # TOP: File Selection
        top_frame = ctk.CTkFrame(self)
        top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        top_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top_frame, text="EMG File", font=("Segoe UI", 11, "bold")).pack(side="left", padx=(0, 10))

        self.file_var = ctk.StringVar(value="No file selected")
        file_entry = ctk.CTkEntry(top_frame, textvariable=self.file_var, state="readonly")
        file_entry.pack(side="left", expand=True, fill="x", padx=(0, 10))

        ctk.CTkButton(top_frame, text="Load EMG", width=80, command=self._load_emg_file).pack(side="left", padx=(0, 5))
        ctk.CTkButton(top_frame, text="Help", width=50, command=self._show_help).pack(side="left")

        # MIDDLE: Main content
        middle_frame = ctk.CTkFrame(self)
        middle_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        middle_frame.grid_rowconfigure(0, weight=1)
        middle_frame.grid_columnconfigure(2, weight=1)

        # LEFT: Processing Controls
        left_panel = ctk.CTkScrollableFrame(middle_frame, corner_radius=8)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # Bandpass Filter
        bp_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        bp_frame.pack(padx=10, pady=(10, 5), anchor="w")
        self.bp_enabled = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(bp_frame, text="Bandpass Filter", variable=self.bp_enabled, font=("Segoe UI", 10, "bold")).pack(anchor="w")

        ctk.CTkLabel(left_panel, text="Low (Hz):", font=("Segoe UI", 9)).pack(padx=15, anchor="w")
        self.bp_low_var = ctk.StringVar(value="10")
        ctk.CTkEntry(left_panel, textvariable=self.bp_low_var, width=100).pack(padx=15, pady=2, anchor="w")

        ctk.CTkLabel(left_panel, text="High (Hz):", font=("Segoe UI", 9)).pack(padx=15, anchor="w", pady=(10, 0))
        self.bp_high_var = ctk.StringVar(value="500")
        ctk.CTkEntry(left_panel, textvariable=self.bp_high_var, width=100).pack(padx=15, pady=2, anchor="w")

        # Low-pass Filter
        lp_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        lp_frame.pack(padx=10, pady=(15, 5), anchor="w")
        self.lp_enabled = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(lp_frame, text="Low-pass Filter", variable=self.lp_enabled, font=("Segoe UI", 10, "bold")).pack(anchor="w")

        ctk.CTkLabel(left_panel, text="Cutoff (Hz):", font=("Segoe UI", 9)).pack(padx=15, anchor="w")
        self.lp_var = ctk.StringVar(value="10")
        ctk.CTkEntry(left_panel, textvariable=self.lp_var, width=100).pack(padx=15, pady=2, anchor="w")

        # Amplitude Scaling
        scale_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        scale_frame.pack(padx=10, pady=(15, 5), anchor="w")
        self.scale_enabled = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(scale_frame, text="Amplitude Scaling", variable=self.scale_enabled, font=("Segoe UI", 10, "bold")).pack(anchor="w")

        ctk.CTkLabel(left_panel, text="Scale Factor:", font=("Segoe UI", 9)).pack(padx=15, anchor="w")
        self.scale_var = ctk.StringVar(value="1.0")
        ctk.CTkEntry(left_panel, textvariable=self.scale_var, width=100).pack(padx=15, pady=2, anchor="w")

        # Normalization
        norm_frame_header = ctk.CTkFrame(left_panel, fg_color="transparent")
        norm_frame_header.pack(padx=10, pady=(15, 5), anchor="w")
        self.norm_enabled = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(norm_frame_header, text="Normalize", variable=self.norm_enabled, font=("Segoe UI", 10, "bold")).pack(anchor="w")

        self.norm_var = ctk.StringVar(value="none")
        norm_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        norm_frame.pack(padx=15, pady=5, anchor="w")
        ctk.CTkRadioButton(norm_frame, text="None", variable=self.norm_var, value="none").pack(anchor="w")
        ctk.CTkRadioButton(norm_frame, text="Max", variable=self.norm_var, value="max").pack(anchor="w")
        ctk.CTkRadioButton(norm_frame, text="RMS", variable=self.norm_var, value="rms").pack(anchor="w")

        # Buttons
        ctk.CTkButton(left_panel, text="Apply", fg_color="#28a745", command=self._apply_processing).pack(fill="x", padx=10, pady=(20, 5))
        ctk.CTkButton(left_panel, text="Reset", fg_color="#dc3545", command=self._reset_processing).pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(left_panel, text="Undo", fg_color="#ffc107", command=self._undo_processing).pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(left_panel, text="Save", fg_color="#0084ff", command=self._save_processed_emg).pack(fill="x", padx=10, pady=5)

        # CENTER: Signal Selection Panel
        center_panel_outer = ctk.CTkFrame(middle_frame, corner_radius=8)
        center_panel_outer.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        center_panel_outer.grid_rowconfigure(1, weight=1)

        # Header with Select All / Deselect All buttons
        header_frame = ctk.CTkFrame(center_panel_outer, fg_color="transparent")
        header_frame.pack(fill="x", padx=10, pady=(10, 5))
        ctk.CTkLabel(header_frame, text="Select Signals", font=("Segoe UI", 11, "bold")).pack(side="left", padx=(0, 10))
        ctk.CTkButton(header_frame, text="All", width=40, command=self._select_all_signals, font=("Segoe UI", 9)).pack(side="right", padx=2)
        ctk.CTkButton(header_frame, text="None", width=40, command=self._deselect_all_signals, font=("Segoe UI", 9)).pack(side="right", padx=2)

        center_panel = ctk.CTkScrollableFrame(center_panel_outer, corner_radius=8)
        center_panel.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.signal_checkboxes = []
        self.signal_check_vars = []
        self.signals_frame = center_panel  # Store reference for later population

        # RIGHT: Visualization
        right_panel = ctk.CTkFrame(middle_frame, corner_radius=8)
        right_panel.grid(row=0, column=2, sticky="nsew")
        self.canvas_frame = ctk.CTkFrame(right_panel)
        self.canvas_frame.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(self.canvas_frame, text="Load an EMG file to visualize", text_color="#888888").pack(expand=True)
        self.matplotlib_canvas = None
        self.toolbar_frame = None

        # Status
        status_frame = ctk.CTkFrame(self)
        status_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.status_label = ctk.CTkLabel(status_frame, text="Ready", text_color="#28a745", font=("Segoe UI", 9))
        self.status_label.pack(side="left", padx=10, pady=5)

    def _load_emg_file(self) -> None:
        """Load EMG file - supports MOT, STO, CSV."""
        file_path = filedialog.askopenfilename(
            title="Select EMG File",
            filetypes=[("All Supported", "*.mot *.sto *.csv"), ("MOT", "*.mot"), ("STO", "*.sto"), ("CSV", "*.csv"), ("All", "*.*")]
        )
        if not file_path:
            return

        try:
            self.emg_file_path = file_path
            self.file_var.set(Path(file_path).name)

            with open(file_path, 'r') as f:
                lines = f.readlines()

            data_start = 0
            channel_names = []
            for i, line in enumerate(lines):
                if line.strip().startswith('time'):
                    channel_names = line.strip().split()
                    data_start = i + 1
                    break

            data = []
            for line in lines[data_start:]:
                if line.strip():
                    try:
                        values = [float(x) for x in line.strip().split()]
                        data.append(values)
                    except ValueError:
                        continue

            data_array = np.array(data)
            self.original_data = data_array[:, 1:]
            self.emg_data = self.original_data.copy()
            self.processed_data = self.original_data.copy()
            self.channel_names = channel_names[1:] if len(channel_names) > 1 else [f"CH{i+1}" for i in range(self.emg_data.shape[1])]
            self.processing_history = []
            self.selected_channels = set(range(len(self.channel_names)))  # Select all by default

            # Update signal selection checkboxes
            self._populate_signal_checkboxes()

            if HAS_MATPLOTLIB:
                self._update_visualization()
            else:
                messagebox.showwarning("Warning", "Install matplotlib for visualization:\npip install matplotlib\n\nYou can still use all processing features (filtering, scaling, normalization).")

            self._log_status(f"Loaded {self.emg_data.shape[1]} channels, {self.emg_data.shape[0]} samples")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load:\n{str(e)}")
            self._log_status(f"Error: {str(e)[:50]}")

    def _populate_signal_checkboxes(self) -> None:
        """Populate signal selection checkboxes."""
        # Clear existing checkboxes
        for widget in self.signals_frame.winfo_children():
            widget.destroy()
        self.signal_checkboxes = []
        self.signal_check_vars = []

        # Create checkboxes for each channel
        for i, ch_name in enumerate(self.channel_names):
            var = ctk.BooleanVar(value=True)
            self.signal_check_vars.append(var)

            checkbox = ctk.CTkCheckBox(
                self.signals_frame,
                text=ch_name,
                variable=var,
                command=self._on_signal_selection_changed,
                font=("Segoe UI", 9)
            )
            checkbox.pack(anchor="w", padx=10, pady=2)
            self.signal_checkboxes.append(checkbox)

    def _on_signal_selection_changed(self) -> None:
        """Update visualization when signal selection changes."""
        self.selected_channels = {i for i, var in enumerate(self.signal_check_vars) if var.get()}
        if HAS_MATPLOTLIB and self.emg_data is not None:
            self._update_visualization()

    def _apply_processing(self) -> None:
        """Apply processing steps - only applies enabled filters."""
        if self.emg_data is None:
            messagebox.showwarning("Warning", "Load an EMG file first")
            return

        if not HAS_SCIPY and (self.bp_enabled.get() or self.lp_enabled.get()):
            messagebox.showinfo("Info", "Install scipy for filtering:\npip install scipy")
            return

        try:
            self.processed_data = self.original_data.copy()
            steps = []

            # Bandpass Filter (scipy only, if enabled)
            if self.bp_enabled.get() and HAS_SCIPY:
                try:
                    bp_low = float(self.bp_low_var.get())
                    bp_high = float(self.bp_high_var.get())
                    if 0 < bp_low < bp_high < self.sampling_rate / 2:
                        sos = signal.butter(4, [bp_low, bp_high], btype='band', fs=self.sampling_rate, output='sos')
                        for i in range(self.processed_data.shape[1]):
                            self.processed_data[:, i] = signal.sosfilt(sos, self.processed_data[:, i])
                        steps.append(f"Bandpass {bp_low}-{bp_high}Hz")
                except (ValueError, AttributeError) as e:
                    messagebox.showerror("Error", f"Bandpass filter error: {str(e)}")

            # Low-pass Filter (scipy only, if enabled)
            if self.lp_enabled.get() and HAS_SCIPY:
                try:
                    lp_freq = float(self.lp_var.get())
                    if 0 < lp_freq < self.sampling_rate / 2:
                        sos = signal.butter(4, lp_freq, btype='low', fs=self.sampling_rate, output='sos')
                        for i in range(self.processed_data.shape[1]):
                            self.processed_data[:, i] = signal.sosfilt(sos, self.processed_data[:, i])
                        steps.append(f"Lowpass {lp_freq}Hz")
                except (ValueError, AttributeError) as e:
                    messagebox.showerror("Error", f"Lowpass filter error: {str(e)}")

            # Scaling (if enabled)
            if self.scale_enabled.get():
                try:
                    scale = float(self.scale_var.get())
                    if scale != 0 and scale != 1.0:
                        self.processed_data *= scale
                        steps.append(f"Scale x{scale}")
                except ValueError:
                    messagebox.showerror("Error", "Invalid scale factor")

            # Normalization (if enabled)
            if self.norm_enabled.get():
                norm_type = self.norm_var.get()
                if norm_type == "max":
                    for i in range(self.processed_data.shape[1]):
                        max_val = np.max(np.abs(self.processed_data[:, i]))
                        if max_val > 0:
                            self.processed_data[:, i] /= max_val
                    steps.append("Max normalize")
                elif norm_type == "rms":
                    for i in range(self.processed_data.shape[1]):
                        rms_val = np.sqrt(np.mean(self.processed_data[:, i]**2))
                        if rms_val > 0:
                            self.processed_data[:, i] /= rms_val
                    steps.append("RMS normalize")

            if steps:
                self.processing_history.append(self.processed_data.copy())
                if HAS_MATPLOTLIB:
                    self._update_visualization()
                self._log_status(f"Applied: {', '.join(steps)}")
            else:
                self._log_status("No processing applied (enable options and try again)")

        except Exception as e:
            messagebox.showerror("Error", f"Processing error:\n{str(e)}")

    def _reset_processing(self) -> None:
        """Reset processed data to original."""
        self.processed_data = self.original_data.copy()
        self.processing_history = []
        self.bp_enabled.set(False)
        self.lp_enabled.set(False)
        self.scale_enabled.set(False)
        self.norm_enabled.set(False)
        if HAS_MATPLOTLIB:
            self._update_visualization()
        self._log_status("Reset to original data")

    def _undo_processing(self) -> None:
        """Undo last step."""
        if self.processing_history:
            self.processing_history.pop()
            self.processed_data = self.processing_history[-1].copy() if self.processing_history else self.original_data.copy()
            if HAS_MATPLOTLIB:
                self._update_visualization()
            self._log_status("Undo applied")
        else:
            self._log_status("Nothing to undo")

    def _select_all_signals(self) -> None:
        """Select all signals."""
        for var in self.signal_check_vars:
            var.set(True)
        self._on_signal_selection_changed()
        self._log_status(f"Selected all {len(self.signal_check_vars)} signals")

    def _deselect_all_signals(self) -> None:
        """Deselect all signals."""
        for var in self.signal_check_vars:
            var.set(False)
        self._on_signal_selection_changed()
        self._log_status("Deselected all signals")

    def _save_processed_emg(self) -> None:
        """Save processed EMG in MOT or STO format (selected columns only)."""
        if self.processed_data is None:
            messagebox.showwarning("Warning", "No processed data")
            return

        if not self.selected_channels:
            messagebox.showwarning("Warning", "Select at least one signal to save")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".mot",
            filetypes=[("MOT", "*.mot"), ("STO", "*.sto"), ("CSV", "*.csv")],
            initialfile=f"EMG_processed_{Path(self.emg_file_path).stem}.mot" if self.emg_file_path else "EMG_processed.mot"
        )

        if not file_path:
            return

        try:
            # Get file extension
            ext = Path(file_path).suffix.lower()

            if ext == ".sto":
                self._write_sto_file(file_path)
            elif ext == ".mot":
                self._write_mot_file(file_path)
            else:  # .csv or other
                self._write_csv_file(file_path)

            num_selected = len(self.selected_channels)
            messagebox.showinfo("Success", f"Saved {num_selected} signals:\n{Path(file_path).name}")
            self._log_status(f"Saved {num_selected} signals: {Path(file_path).name}")

        except Exception as e:
            messagebox.showerror("Error", f"Save error:\n{str(e)}")

    def _write_mot_file(self, file_path: str) -> None:
        """Write MOT file with proper formatting (selected columns only)."""
        num_samples = self.processed_data.shape[0]
        sorted_channels = sorted(self.selected_channels)
        selected_names = [self.channel_names[i] for i in sorted_channels]
        labels = ['time'] + selected_names
        num_columns = len(labels)

        with open(file_path, 'w') as f:
            # Write header
            f.write(f"{Path(file_path).name}\n")
            f.write("version=1\n")
            f.write(f"nRows={num_samples}\n")
            f.write(f"nColumns={num_columns}\n")
            f.write("in_degrees=yes\n")
            f.write("endheader\n")

            # Write column labels
            f.write("\t".join(labels) + "\n")

            # Write data rows
            for i in range(num_samples):
                time_val = i * (1.0 / self.sampling_rate)
                row_values = [f"{time_val:.6f}"] + [f"{self.processed_data[i, ch]:.6f}" for ch in sorted_channels]
                f.write("\t".join(row_values) + "\n")

    def _write_sto_file(self, file_path: str) -> None:
        """Write STO file with proper formatting (selected columns only)."""
        num_samples = self.processed_data.shape[0]
        sorted_channels = sorted(self.selected_channels)
        selected_names = [self.channel_names[i] for i in sorted_channels]
        labels = ['time'] + selected_names
        num_columns = len(labels)

        with open(file_path, 'w') as f:
            # Write header
            f.write(f"{Path(file_path).name}\n")
            f.write("version=1\n")
            f.write(f"nRows={num_samples}\n")
            f.write(f"nColumns={num_columns}\n")
            f.write("in_degrees=yes\n")
            f.write("endheader\n")

            # Write column labels
            f.write("\t".join(labels) + "\n")

            # Write data rows
            for i in range(num_samples):
                time_val = i * (1.0 / self.sampling_rate)
                row_values = [f"{time_val:.6f}"] + [f"{self.processed_data[i, ch]:.6f}" for ch in sorted_channels]
                f.write("\t".join(row_values) + "\n")

    def _write_csv_file(self, file_path: str) -> None:
        """Write CSV file (selected columns only)."""
        num_samples = self.processed_data.shape[0]
        sorted_channels = sorted(self.selected_channels)
        selected_names = [self.channel_names[i] for i in sorted_channels]
        labels = ['time'] + selected_names

        with open(file_path, 'w') as f:
            # Write header
            f.write(",".join(labels) + "\n")

            # Write data rows
            for i in range(num_samples):
                time_val = i * (1.0 / self.sampling_rate)
                row_values = [f"{time_val:.6f}"] + [f"{self.processed_data[i, ch]:.6f}" for ch in sorted_channels]
                f.write(",".join(row_values) + "\n")

    def _update_visualization(self) -> None:
        """Update plot visualization with selected channels only."""
        if self.emg_data is None or not HAS_MATPLOTLIB:
            return

        try:
            # Clear existing widgets
            for widget in self.canvas_frame.winfo_children():
                widget.destroy()

            if not self.selected_channels:
                ctk.CTkLabel(self.canvas_frame, text="Select at least one signal", text_color="#888888").pack(expand=True)
                return

            num_selected = len(self.selected_channels)
            height = max(2 * num_selected, 4)
            fig = Figure(figsize=(10, height), dpi=100)

            sorted_channels = sorted(self.selected_channels)
            for plot_idx, ch_idx in enumerate(sorted_channels):
                ax = fig.add_subplot(num_selected, 1, plot_idx + 1)
                time = np.arange(self.original_data.shape[0]) / self.sampling_rate
                ax.plot(time, self.original_data[:, ch_idx], label='Original', alpha=0.6, linewidth=1)
                ax.plot(time, self.processed_data[:, ch_idx], label='Processed', alpha=0.8, linewidth=1.5, color='orange')

                # Show channel name as title instead of y-label
                ax.set_title(self.channel_names[ch_idx], fontsize=10, fontweight='bold', pad=5)
                ax.legend(loc='upper right', fontsize=8)
                ax.grid(True, alpha=0.3)
                if plot_idx == num_selected - 1:
                    ax.set_xlabel('Time (s)', fontsize=9)

            fig.tight_layout()

            # Create canvas with toolbar
            self.matplotlib_canvas = FigureCanvasTkAgg(fig, master=self.canvas_frame)
            self.matplotlib_canvas.draw()
            self.matplotlib_canvas.get_tk_widget().pack(fill="both", expand=True)

            # Add toolbar for zoom/pan
            if self.toolbar_frame:
                self.toolbar_frame.destroy()
            self.toolbar_frame = ctk.CTkFrame(self.canvas_frame)
            self.toolbar_frame.pack(side="bottom", fill="x")
            NavigationToolbar2Tk(self.matplotlib_canvas, self.toolbar_frame)

        except Exception as e:
            self._log_status(f"Viz error: {str(e)[:40]}")

    def _log_status(self, message: str) -> None:
        """Update status."""
        self.status_label.configure(text=message)
        self.update()

    def _show_help(self) -> None:
        """Show help."""
        msg = "1. Load EMG file (MOT, STO, CSV)\n"
        msg += "2. Select signals from the list\n"
        msg += "3. Configure filters/scaling\n"
        msg += "4. Click Apply\n"
        msg += "5. Use Undo/Save\n\n"
        msg += "Plot Controls:\n"
        msg += "- Pan: Click and drag\n"
        msg += "- Zoom: Box select with zoom tool\n"
        msg += "- Reset: Home button\n\n"
        msg += "Missing dependencies:\n"
        if not HAS_MATPLOTLIB:
            msg += "- pip install matplotlib\n"
        if not HAS_SCIPY:
            msg += "- pip install scipy\n"
        messagebox.showinfo("Help", msg)
