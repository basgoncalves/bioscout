"""EMG Normalization Tab - Simple normalization with trial selection."""

import customtkinter as ctk
from pathlib import Path
import sys
import numpy as np
import threading

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.config_manager import ConfigManager
from utils.logger import logger


class EMGNormalizationTab(ctk.CTkFrame):
    """Tab for session-level EMG normalization with trial selection."""

    def __init__(self, parent, config_manager: ConfigManager, status_callback):
        """Initialize EMG Normalization Tab."""
        super().__init__(parent)
        self.config_manager = config_manager
        self.status_callback = status_callback

        # Session management
        self.session_dir = None
        self.trials_with_emg = {}  # trial_name -> emg_file_path
        self.ref_trial_vars = {}  # Reference trials for max calculation
        self.norm_trial_vars = {}  # Trials to normalize

        self._create_widgets()

    def set_session_dir(self, session_dir: str):
        """Receive session directory from main window."""
        self.session_dir = Path(session_dir) if session_dir else None
        if self.session_dir and self.session_dir.exists():
            self.session_label.configure(text=f"Session: {self.session_dir.name}")
            self._scan_trials()
            logger.info(f"EMG Normalization: Session set to {self.session_dir}")
        else:
            self.session_label.configure(text="Session: Not set")
            self._clear_trials()

    def _create_widgets(self) -> None:
        """Create UI widgets."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # TOP: Session Info
        top_frame = ctk.CTkFrame(self)
        top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        top_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top_frame, text="EMG Normalization", font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )

        self.session_label = ctk.CTkLabel(top_frame, text="Session: Not set", font=("Segoe UI", 10, "bold"), text_color="#28a745")
        self.session_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 5))

        # MAIN: Content with 3 columns
        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)  # LEFT: Reference trials
        main_frame.grid_columnconfigure(1, weight=1)  # MIDDLE: Normalization method
        main_frame.grid_columnconfigure(2, weight=1)  # RIGHT: Trials to normalize

        # LEFT: Trials for Max Calculation
        left_frame = ctk.CTkScrollableFrame(main_frame, corner_radius=8)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        ctk.CTkLabel(left_frame, text="Trials for Max Calculation", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=10, pady=(10, 5))

        ref_button_frame = ctk.CTkFrame(left_frame)
        ref_button_frame.pack(anchor="w", padx=10, pady=(0, 5), fill="x")

        ctk.CTkButton(
            ref_button_frame,
            text="All",
            width=50,
            height=25,
            font=("Segoe UI", 9),
            command=self._select_all_ref_trials
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            ref_button_frame,
            text="None",
            width=50,
            height=25,
            font=("Segoe UI", 9),
            command=self._deselect_all_ref_trials
        ).pack(side="left", padx=2)

        self.ref_trials_frame = ctk.CTkScrollableFrame(left_frame, height=200)
        self.ref_trials_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # MIDDLE: Normalization Method and Action
        middle_frame = ctk.CTkFrame(main_frame, corner_radius=8)
        middle_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 5))
        middle_frame.grid_rowconfigure(5, weight=1)
        middle_frame.grid_columnconfigure(0, weight=1)

        # Normalization Method Section
        ctk.CTkLabel(middle_frame, text="Normalization Method", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 5)
        )

        self.norm_var = ctk.StringVar(value="Max")

        norm_frame = ctk.CTkFrame(middle_frame)
        norm_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))

        methods = [
            ("Max", "Max"),
            ("Window Average", "WindowAverage")
        ]

        for label, value in methods:
            ctk.CTkRadioButton(
                norm_frame,
                text=label,
                variable=self.norm_var,
                value=value,
                font=("Segoe UI", 10),
                command=self._on_norm_method_change
            ).pack(anchor="w", padx=5, pady=3)

        # Window time input (shown only for Window Average)
        self.window_frame = ctk.CTkFrame(middle_frame)
        self.window_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 15))

        ctk.CTkLabel(self.window_frame, text="Window Time (ms):", font=("Segoe UI", 9)).pack(anchor="w")
        self.window_ms_var = ctk.StringVar(value="200")
        self.window_entry = ctk.CTkEntry(
            self.window_frame,
            textvariable=self.window_ms_var,
            placeholder_text="Enter window time in ms",
            width=150,
            height=30
        )
        self.window_entry.pack(anchor="w", pady=(3, 0))

        # Initially hide window frame
        self._on_norm_method_change()

        # Apply Normalization Button (below normalization method, with more spacing)
        ctk.CTkButton(
            middle_frame,
            text="Apply Normalization",
            command=self._apply_normalization,
            fg_color="#0084ff",
            hover_color="#0066cc",
            height=40,
            font=("Segoe UI", 11, "bold")
        ).grid(row=3, column=0, sticky="ew", padx=10, pady=(20, 15))

        # Status
        ctk.CTkLabel(middle_frame, text="Status", font=("Segoe UI", 10, "bold")).grid(
            row=4, column=0, sticky="w", padx=10, pady=(15, 5)
        )

        self.status_label = ctk.CTkLabel(
            middle_frame,
            text="Ready",
            text_color="#28a745",
            font=("Segoe UI", 9),
            justify="left"
        )
        self.status_label.grid(row=5, column=0, sticky="nsew", padx=10, pady=(0, 10))

        # RIGHT: Trials to Normalize
        right_frame = ctk.CTkScrollableFrame(main_frame, corner_radius=8)
        right_frame.grid(row=0, column=2, sticky="nsew", padx=(5, 0))

        ctk.CTkLabel(right_frame, text="Trials to Normalize", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=10, pady=(10, 5))

        norm_button_frame = ctk.CTkFrame(right_frame)
        norm_button_frame.pack(anchor="w", padx=10, pady=(0, 5), fill="x")

        ctk.CTkButton(
            norm_button_frame,
            text="All",
            width=50,
            height=25,
            font=("Segoe UI", 9),
            command=self._select_all_norm_trials
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            norm_button_frame,
            text="None",
            width=50,
            height=25,
            font=("Segoe UI", 9),
            command=self._deselect_all_norm_trials
        ).pack(side="left", padx=2)

        self.norm_trials_frame = ctk.CTkScrollableFrame(right_frame, height=200)
        self.norm_trials_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _scan_trials(self):
        """Scan session directory for trials with EMG files."""
        self._clear_trials()

        if not self.session_dir:
            return

        try:
            # Look for trial folders
            for item in self.session_dir.iterdir():
                if item.is_dir():
                    # Check if it has emg.mot file
                    emg_file = item / "emg.mot"
                    if emg_file.exists():
                        trial_name = item.name
                        self.trials_with_emg[trial_name] = emg_file

                        # Add checkbox for reference trials (first section)
                        ref_var = ctk.BooleanVar(value=True)
                        self.ref_trial_vars[trial_name] = ref_var

                        checkbox_ref = ctk.CTkCheckBox(
                            self.ref_trials_frame,
                            text=trial_name,
                            variable=ref_var,
                            font=("Segoe UI", 10)
                        )
                        checkbox_ref.pack(anchor="w", padx=5, pady=3)

                        # Add checkbox for normalization trials (second section)
                        norm_var = ctk.BooleanVar(value=True)
                        self.norm_trial_vars[trial_name] = norm_var

                        checkbox_norm = ctk.CTkCheckBox(
                            self.norm_trials_frame,
                            text=trial_name,
                            variable=norm_var,
                            font=("Segoe UI", 10)
                        )
                        checkbox_norm.pack(anchor="w", padx=5, pady=3)

            if self.trials_with_emg:
                self.status_callback(f"Found {len(self.trials_with_emg)} trials with EMG data", "success")
                self.status_label.configure(
                    text=f"Ready - {len(self.trials_with_emg)} trials",
                    text_color="#28a745"
                )
            else:
                self.status_callback("No trials with EMG data found in session", "warning")
                self.status_label.configure(
                    text="No EMG trials found",
                    text_color="#ffc107"
                )

        except Exception as e:
            self.status_callback(f"Error scanning trials: {str(e)[:50]}", "error")
            logger.error(f"Error scanning trials: {e}")
            self.status_label.configure(text=f"Error: {str(e)[:40]}", text_color="#dc3545")

    def _clear_trials(self):
        """Clear all trial checkboxes."""
        for widget in self.ref_trials_frame.winfo_children():
            widget.destroy()
        for widget in self.norm_trials_frame.winfo_children():
            widget.destroy()
        self.ref_trial_vars.clear()
        self.norm_trial_vars.clear()
        self.trials_with_emg.clear()

    def _select_all_ref_trials(self):
        """Select all reference trials."""
        for var in self.ref_trial_vars.values():
            var.set(True)

    def _deselect_all_ref_trials(self):
        """Deselect all reference trials."""
        for var in self.ref_trial_vars.values():
            var.set(False)

    def _select_all_norm_trials(self):
        """Select all normalization trials."""
        for var in self.norm_trial_vars.values():
            var.set(True)

    def _deselect_all_norm_trials(self):
        """Deselect all normalization trials."""
        for var in self.norm_trial_vars.values():
            var.set(False)

    def _on_norm_method_change(self):
        """Handle normalization method change."""
        if self.norm_var.get() == "WindowAverage":
            # Show window time input for Window Average
            if not self.window_frame.winfo_ismapped():
                self.window_frame.pack(anchor="w", padx=10, pady=(0, 15), fill="x")
        else:
            # Hide window time input for other methods
            if self.window_frame.winfo_ismapped():
                self.window_frame.pack_forget()

    def _apply_normalization(self):
        """Apply normalization to selected trials."""
        ref_trials = [name for name, var in self.ref_trial_vars.items() if var.get()]
        norm_trials = [name for name, var in self.norm_trial_vars.items() if var.get()]

        if not ref_trials:
            self.status_callback("[WARN] Select reference trials for max calculation", "warning")
            self.status_label.configure(text="Select reference trials first", text_color="#ffc107")
            return

        if not norm_trials:
            self.status_callback("[WARN] Select trials to normalize", "warning")
            self.status_label.configure(text="Select trials to normalize", text_color="#ffc107")
            return

        norm_method = self.norm_var.get()
        window_ms = None

        if norm_method == "WindowAverage":
            try:
                window_ms = float(self.window_ms_var.get())
                if window_ms <= 0:
                    self.status_callback("[WARN] Window time must be > 0", "warning")
                    return
            except ValueError:
                self.status_callback("[WARN] Invalid window time value", "warning")
                return

        msg = f"\n[START] Calculating max from {len(ref_trials)} reference trials, normalizing {len(norm_trials)} trials using {norm_method} method"
        self.status_callback(msg, "info")

        # Run in background thread
        thread = threading.Thread(
            target=self._normalize_in_thread,
            args=(ref_trials, norm_trials, norm_method, window_ms),
            daemon=True
        )
        thread.start()

    def _normalize_in_thread(self, ref_trials: list, norm_trials: list, norm_method: str, window_ms: float = None):
        """Run normalization in background thread.

        First calculates max from reference trials, then applies to normalization trials.
        Batches status updates to avoid excessive UI redraws.
        """
        try:
            # Schedule status label update safely from main thread
            self.after(0, lambda: self.status_label.configure(text="Processing...", text_color="#0084ff"))

            # STEP 1: Calculate max from reference trials
            self.status_callback(f"[STEP 1] Calculating normalization factor from {len(ref_trials)} reference trials", "info")

            max_vals = None
            n_channels = None
            ref_errors = []

            for i, trial_name in enumerate(ref_trials):
                try:
                    emg_file = self.trials_with_emg[trial_name]
                    emg_data = self._load_mot_file(emg_file)

                    if emg_data is None or emg_data.shape[0] == 0:
                        ref_errors.append(f"  {trial_name}: Could not read EMG file")
                        logger.debug(f"Could not read EMG file for {trial_name}")
                        continue

                    # Get number of channels from first trial
                    if n_channels is None:
                        n_channels = emg_data.shape[1]
                    elif emg_data.shape[1] != n_channels:
                        ref_errors.append(f"  {trial_name}: Channel count mismatch ({emg_data.shape[1]} vs {n_channels})")
                        logger.debug(f"Channel count mismatch for {trial_name}")
                        continue

                    # Calculate max for this trial
                    try:
                        if norm_method == "Max":
                            trial_max = np.max(np.abs(emg_data), axis=0, keepdims=True)
                        elif norm_method == "WindowAverage":
                            smoothed = self._get_window_average_envelope(emg_data, window_ms)
                            trial_max = np.max(smoothed, axis=0, keepdims=True)
                        else:
                            trial_max = np.ones((1, emg_data.shape[1]))

                        # Initialize or update overall maximum
                        if max_vals is None:
                            max_vals = trial_max.astype(np.float64)
                        else:
                            # Ensure both arrays are same shape before comparison
                            if max_vals.shape != trial_max.shape:
                                ref_errors.append(f"  {trial_name}: Shape mismatch in max calculation")
                                logger.debug(f"Shape mismatch for {trial_name}")
                                continue
                            max_vals = np.maximum(max_vals, trial_max.astype(np.float64))

                        logger.debug(f"Max calculated for {trial_name} (shape: {emg_data.shape})")

                    except Exception as e:
                        ref_errors.append(f"  {trial_name}: Error in max calculation - {str(e)[:40]}")
                        logger.error(f"Error calculating max from {trial_name}: {e}", exc_info=True)
                        continue

                except Exception as e:
                    ref_errors.append(f"  {trial_name}: ERROR - {str(e)[:50]}")
                    logger.error(f"Error processing reference trial {trial_name}: {e}", exc_info=True)

            if max_vals is None or n_channels is None:
                # Report all errors at once
                for error_msg in ref_errors:
                    self.status_callback(error_msg, "error")
                self.status_callback("[ERROR] Could not calculate valid normalization factor - no valid reference trials", "error")
                self.after(0, lambda: self.status_label.configure(text="Error: No valid reference trials", text_color="#dc3545"))
                return

            # Report reference trial errors after completion
            if ref_errors:
                for error_msg in ref_errors:
                    self.status_callback(error_msg, "error")

            # Only report success summary
            successful_ref = len(ref_trials) - len(ref_errors)
            self.status_callback(f"[STEP 1 DONE] Used {successful_ref}/{len(ref_trials)} reference trials to calculate normalization factor", "success")

            # Avoid division by zero
            max_vals[max_vals == 0] = 1.0
            max_vals = np.maximum(max_vals, 1e-10)  # Add small epsilon to avoid division by very small numbers

            self.status_callback(f"[STEP 2] Applying normalization to {len(norm_trials)} trials", "info")

            # STEP 2: Apply normalization to target trials
            success_count = 0
            norm_errors = []

            for i, trial_name in enumerate(norm_trials):
                try:
                    emg_file = self.trials_with_emg[trial_name]

                    # Load EMG data
                    emg_data = self._load_mot_file(emg_file)
                    if emg_data is None or emg_data.shape[0] == 0:
                        norm_errors.append(f"  {trial_name}: Could not read EMG file")
                        logger.debug(f"Could not read EMG file for {trial_name}")
                        continue

                    # Validate channel count
                    if emg_data.shape[1] != n_channels:
                        norm_errors.append(f"  {trial_name}: Channel count mismatch ({emg_data.shape[1]} vs {n_channels})")
                        logger.debug(f"Channel count mismatch for {trial_name}")
                        continue

                    # Normalize using calculated max_vals
                    try:
                        normalized_data = emg_data.astype(np.float64) / max_vals
                    except Exception as e:
                        norm_errors.append(f"  {trial_name}: Error dividing data - {str(e)[:40]}")
                        logger.error(f"Error normalizing data for {trial_name}: {e}")
                        continue

                    # Save normalized data to new file: emg_filtered_normalised.mot
                    output_file = emg_file.parent / "emg_filtered_normalised.mot"
                    self._save_mot_file(emg_file, output_file, normalized_data)

                    # Update trial_settings.xml to point to normalized EMG file
                    self._update_trial_settings_emg(emg_file.parent, "emg_filtered_normalised.mot")

                    logger.debug(f"Normalized and saved {trial_name} (shape: {normalized_data.shape})")
                    success_count += 1

                except Exception as e:
                    norm_errors.append(f"  {trial_name}: ERROR - {str(e)[:50]}")
                    logger.error(f"Error normalizing {trial_name}: {e}", exc_info=True)

            # Report any normalization errors
            if norm_errors:
                for error_msg in norm_errors:
                    self.status_callback(error_msg, "error")

            # Final summary
            self.status_callback(f"[SUCCESS] Normalization completed: {success_count}/{len(norm_trials)} trials successfully normalized", "success")
            self.after(0, lambda: self.status_label.configure(text=f"Done - {success_count}/{len(norm_trials)} trials", text_color="#28a745"))

        except Exception as e:
            self.status_callback(f"[ERROR] Normalization failed: {e}", "error")
            self.after(0, lambda: self.status_label.configure(text="Error during normalization", text_color="#dc3545"))
            logger.error(f"Normalization error: {e}", exc_info=True)

    def _update_trial_settings_emg(self, trial_dir: Path, emg_filename: str):
        """Update trial_settings.xml to point to normalized EMG file."""
        try:
            import xml.etree.ElementTree as ET

            settings_file = trial_dir / "trial_settings.xml"
            if not settings_file.exists():
                return  # File doesn't exist yet, skip

            # Parse existing XML
            tree = ET.parse(str(settings_file))
            root = tree.getroot()

            # Find or create 'emg' tag
            emg_elem = root.find('emg')
            if emg_elem is None:
                emg_elem = ET.SubElement(root, 'emg')

            emg_elem.text = emg_filename

            # Write back
            tree.write(str(settings_file), encoding='utf-8', xml_declaration=True)
            logger.debug(f"Updated trial_settings.xml EMG tag to: {emg_filename}")

        except Exception as e:
            logger.warning(f"Could not update trial_settings.xml: {e}")

    def _get_window_average_envelope(self, data: np.ndarray, window_ms: float) -> np.ndarray:
        """Get moving window average envelope for EMG data.

        Args:
            data: EMG data array (samples x channels)
            window_ms: Window time in milliseconds

        Returns:
            Envelope data (samples x channels)
        """
        if data.shape[0] == 0 or data.shape[1] == 0:
            return np.zeros_like(data)

        # Estimate sampling frequency (assume 1000 Hz if not specified)
        fs = 1000.0  # Default sampling frequency in Hz

        # Calculate window size in samples
        window_samples = int(np.ceil(window_ms * fs / 1000.0))
        window_samples = max(1, min(window_samples, data.shape[0]))  # Cap at data length

        envelope = np.zeros_like(data, dtype=np.float64)

        # Apply moving window average for each channel
        for ch in range(data.shape[1]):
            try:
                channel_data = np.abs(data[:, ch]).astype(np.float64)
                window = np.ones(window_samples, dtype=np.float64) / window_samples

                # Use convolve with proper mode
                convolved = np.convolve(channel_data, window, mode='same')

                # Ensure output matches input size
                if len(convolved) == len(channel_data):
                    envelope[:, ch] = convolved
                else:
                    # Fallback: use direct moving average
                    for i in range(data.shape[0]):
                        start = max(0, i - window_samples // 2)
                        end = min(data.shape[0], i + window_samples // 2 + 1)
                        envelope[i, ch] = np.mean(channel_data[start:end])
            except Exception as e:
                logger.warning(f"Error in window average for channel {ch}: {e}")
                envelope[:, ch] = np.abs(data[:, ch])

        return envelope

    def _normalize_window_average(self, data: np.ndarray, window_ms: float) -> np.ndarray:
        """Normalize EMG data using moving window average.

        Args:
            data: EMG data array (samples x channels)
            window_ms: Window time in milliseconds

        Returns:
            Normalized data (samples x channels)
        """
        envelope = self._get_window_average_envelope(data, window_ms)
        normalized_data = np.zeros_like(data)

        # Normalize by the envelope maximum for each channel
        for ch in range(data.shape[1]):
            max_val = np.max(envelope[:, ch])
            if max_val > 0:
                normalized_data[:, ch] = data[:, ch] / max_val
            else:
                normalized_data[:, ch] = data[:, ch]

        return normalized_data

    def _load_mot_file(self, mot_file: Path) -> np.ndarray:
        """Load EMG data from MOT file (OpenSim format)."""
        try:
            # Simple MOT file reading - skip header lines
            data = []
            in_data = False
            label_line_skipped = False

            with open(str(mot_file), 'r') as f:
                for line_num, line in enumerate(f):
                    line = line.strip()

                    if not line:  # Skip empty lines
                        continue

                    if line.startswith("endheader"):
                        in_data = True
                        continue

                    if in_data:
                        # Skip the label line (contains column headers like "time\tEMG01\tEMG02...")
                        if not label_line_skipped:
                            if "\t" in line or line.startswith("time"):
                                label_line_skipped = True
                                continue

                        # Parse data lines
                        try:
                            values = [float(x) for x in line.split()]
                            if len(values) > 1:
                                data.append(values[1:])  # Skip time column
                        except (ValueError, IndexError) as e:
                            logger.debug(f"Skipping line {line_num}: {e}")
                            continue

            if data:
                data_array = np.array(data, dtype=np.float64)
                if data_array.size > 0:
                    return data_array

            logger.warning(f"No data read from {mot_file}")
            return None

        except Exception as e:
            logger.error(f"Error loading MOT file {mot_file}: {e}")
            return None

    def _save_mot_file(self, input_file: Path, output_file: Path, data: np.ndarray):
        """Save normalized EMG data to a new MOT file.

        Args:
            input_file: Path to original EMG file (for reading header)
            output_file: Path to output normalized file
            data: Normalized data array
        """
        try:
            # Read original file to extract header and column labels
            labels = ["time"]
            n_rows = data.shape[0]
            n_cols = data.shape[1] + 1  # +1 for time column

            with open(str(input_file), 'r') as f:
                found_header = False
                for line in f:
                    line_stripped = line.strip()

                    if line_stripped.startswith("endheader"):
                        found_header = True
                        continue

                    # After finding endheader, the next line should have column labels
                    if found_header:
                        if "\t" in line_stripped or line_stripped.startswith("time"):
                            labels = line_stripped.split("\t")
                        break

            # Ensure output directory exists
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Write normalized data to output file
            with open(str(output_file), 'w') as f:
                # Write header metadata
                f.write("emg\n")
                f.write("version=1\n")
                f.write(f"nRows={n_rows}\n")
                f.write(f"nColumns={n_cols}\n")
                f.write("inDegrees=no\n")
                f.write("endheader\n")

                # Write column labels
                f.write("\t".join(labels) + "\n")

                # Write data rows
                for i, row in enumerate(data):
                    # Time column: use simple incremental time (0.005s intervals = 200 Hz)
                    time_val = i * 0.005  # Assuming 200 Hz sampling
                    row_values = [f"{time_val:.8f}"] + [f"{val:.8f}" for val in row]
                    f.write("\t".join(row_values) + "\n")

            logger.debug(f"Saved normalized EMG to {output_file}")

        except Exception as e:
            logger.error(f"Error saving MOT file: {e}")
            raise

