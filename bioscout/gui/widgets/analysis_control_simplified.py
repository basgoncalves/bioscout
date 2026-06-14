"""Simplified Analysis Control Tab - Single trial analysis only."""

import customtkinter as ctk
from pathlib import Path
import sys
import threading
from tkinter import filedialog, messagebox
import xml.etree.ElementTree as ET
import xml.dom.minidom
import os
import shutil

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.config_manager import ConfigManager
from core.analysis_runner import AnalysisRunner, AnalysisStep, AnalysisConfig
from utils.logger import logger
from utils import SIMULATIONS_DIR, Analyse


class AnalysisControlTabV2(ctk.CTkFrame):
    """Simplified tab for controlling single trial analysis."""

    def __init__(self, parent, config_manager: ConfigManager, status_callback):
        """Initialize Analysis Control Tab V2."""
        super().__init__(parent)
        self.config_manager = config_manager
        self.status_callback = status_callback
        self.runner = AnalysisRunner(progress_callback=self._on_progress)
        self.analysis_thread = None

        # State
        self.current_path = None
        self.input_files = {}
        self.selected_files = {}
        self.file_vars = {}

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create UI widgets."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # TOP SECTION: Path Selection
        top_frame = ctk.CTkFrame(self)
        top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        top_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top_frame, text="Single Trial Analysis", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 10)
        )

        ctk.CTkLabel(top_frame, text="Trial Directory:", font=("Segoe UI", 10)).grid(
            row=1, column=0, sticky="w", padx=(0, 5)
        )

        self.path_var = ctk.StringVar(value="Paste path or browse...")
        self.path_entry = ctk.CTkEntry(
            top_frame,
            textvariable=self.path_var,
            placeholder_text="Paste path or use Browse button"
        )
        self.path_entry.grid(row=1, column=1, sticky="ew", padx=(0, 10))
        self.path_entry.bind("<Return>", lambda e: self._validate_pasted_path())
        self.path_entry.bind("<Control-v>", lambda e: self.after(10, self._validate_pasted_path))

        ctk.CTkButton(top_frame, text="Browse", width=80, command=self._browse_path).grid(
            row=1, column=2, sticky="w", padx=(0, 5)
        )
        ctk.CTkButton(top_frame, text="Load", width=50, command=self._validate_pasted_path).grid(
            row=1, column=3, sticky="w", padx=(0, 5)
        )

        # Copy input files button
        ctk.CTkButton(
            top_frame,
            text="Copy from Trial",
            width=120,
            command=self._copy_input_files_dialog,
            fg_color="#666666",
            hover_color="#777777"
        ).grid(row=1, column=4, sticky="w")

        # MIDDLE SECTION: Input Files & Steps
        middle_frame = ctk.CTkFrame(self)
        middle_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        middle_frame.grid_rowconfigure(0, weight=1)
        middle_frame.grid_columnconfigure(0, weight=1)
        middle_frame.grid_columnconfigure(1, weight=1)

        # Input Files Panel
        left_panel = ctk.CTkFrame(middle_frame, corner_radius=8)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left_panel.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(left_panel, text="Input Files", font=("Segoe UI", 11, "bold")).pack(
            padx=10, pady=(10, 5), anchor="w"
        )

        self.files_frame = ctk.CTkScrollableFrame(left_panel)
        self.files_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Quick Actions
        quick_frame = ctk.CTkFrame(left_panel)
        quick_frame.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkButton(quick_frame, text="Reload Files", height=28, command=self._reload_files_and_settings).pack(fill="x", pady=(0, 3))
        ctk.CTkButton(quick_frame, text="Edit Settings", height=28, command=self._edit_settings_file).pack(fill="x", pady=(0, 3))
        ctk.CTkButton(quick_frame, text="Save Settings", height=28, fg_color="#28a745", hover_color="#218838", command=self._save_settings_file).pack(fill="x")

        # Analysis Steps Panel
        right_panel = ctk.CTkFrame(middle_frame, corner_radius=8)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        right_panel.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(right_panel, text="Analysis Steps", font=("Segoe UI", 11, "bold")).pack(
            padx=10, pady=(10, 5), anchor="w"
        )

        self.step_vars = {}
        self.steps_frame = ctk.CTkScrollableFrame(right_panel)
        self.steps_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Define analysis step groups for trial-level analysis only - with Reset Settings at the top
        self.step_groups = {
            "Settings": [
                "RESET_SETTINGS",
            ],
            "Core (OpenSim)": [
                AnalysisStep.INVERSE_KINEMATICS,
                AnalysisStep.INVERSE_DYNAMICS,
                AnalysisStep.STATIC_OPTIMIZATION,
            ],
            "Extended": [
                AnalysisStep.MUSCLE_ANALYSIS,
                AnalysisStep.JOINT_REACTION_ANALYSIS,
            ],
            "Advanced Dynamics": [
                AnalysisStep.RRA,
                AnalysisStep.CMC,
                AnalysisStep.ENERGETICS,
                AnalysisStep.BODY_KINEMATICS,
            ],
            "CEINMS": [
                AnalysisStep.CEINMS_CALIBRATION,
                AnalysisStep.CEINMS_EXECUTION,
            ],
        }

        self._populate_analysis_steps()

        # BOTTOM SECTION: Progress & Controls
        bottom_frame = ctk.CTkFrame(self)
        bottom_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        bottom_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(bottom_frame, text="Status:", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, sticky="w"
        )

        self.status_label = ctk.CTkLabel(bottom_frame, text="Ready", text_color="#28a745")
        self.status_label.grid(row=0, column=1, sticky="w", padx=10)

        self.progress_bar = ctk.CTkProgressBar(bottom_frame, height=6)
        self.progress_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        self.progress_bar.set(0)

        button_frame = ctk.CTkFrame(bottom_frame)
        button_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        self.run_btn = ctk.CTkButton(
            button_frame, text="▶ Run Pipeline", fg_color="#28a745", hover_color="#218838",
            font=("Segoe UI", 11, "bold"), height=40, command=self._run_analysis
        )
        self.run_btn.pack(side="left", padx=5, expand=True, fill="both")

        self.stop_btn = ctk.CTkButton(
            button_frame, text="⏹ Stop", fg_color="#dc3545", hover_color="#c82333",
            font=("Segoe UI", 11), height=40, command=self._stop_analysis, state="disabled"
        )
        self.stop_btn.pack(side="left", padx=5, expand=True, fill="both")

    def _browse_path(self) -> None:
        """Browse for trial directory."""
        path = filedialog.askdirectory(title="Select Trial Directory")
        if path:
            self._load_path(path)

    def _validate_pasted_path(self) -> None:
        """Validate and load a pasted path."""
        path_str = self.path_var.get().strip()
        if not path_str or path_str == "Paste path or browse...":
            self.status_callback("⚠ Please enter a valid path", "warning")
            return

        path_str = path_str.replace("/", "\\").strip('"').strip("'")
        path = Path(path_str)

        if not path.exists():
            self.status_callback(f"✗ Path does not exist: {path_str}", "error")
            messagebox.showerror("Error", f"Path not found:\n{path_str}")
            return

        if not path.is_dir():
            self.status_callback(f"✗ Not a directory: {path_str}", "error")
            messagebox.showerror("Error", f"Not a directory:\n{path_str}")
            return

        self._load_path(str(path))

    def _load_path(self, path: str) -> None:
        """Load and display files from the trial directory."""
        self.current_path = Path(path)
        self.path_var.set(str(self.current_path))

        # Load settings from trial_settings.xml
        self._load_settings_file()

        # Scan for available files
        self._scan_files()

        self.status_callback(f"Trial loaded: {self.current_path.name}", "success")
        logger.info(f"Trial path loaded: {self.current_path}")

    def _scan_files(self) -> None:
        """Scan trial directory for available files."""
        self.input_files = {}
        self.file_vars = {}

        # Clear existing file entries
        for widget in self.files_frame.winfo_children():
            widget.destroy()

        if not self.current_path:
            return

        # Define file patterns to search for
        file_patterns = {
            "C3D": ("*.c3d",),
            "Markers": ("marker*.trc", "markers*.trc"),
            "GRF": ("grf*.mot", "forces*.mot"),
            "EMG": ("*emg*.mot", "*emg*.sto", "*EMG*.mot", "*EMG*.sto"),
            "Model": ("*.osim",),
        }

        # Find files
        for category, patterns in file_patterns.items():
            found_files = []
            for pattern in patterns:
                found_files.extend(self.current_path.glob(pattern))

            if found_files:
                # Create category label
                ctk.CTkLabel(
                    self.files_frame,
                    text=category,
                    font=("Segoe UI", 9, "bold"),
                    text_color="#0084ff"
                ).pack(anchor="w", pady=(10, 5))

                # Create file selection
                var = ctk.StringVar()
                self.file_vars[category] = var
                self.input_files[category] = [f.name for f in found_files]

                combo = ctk.CTkComboBox(
                    self.files_frame,
                    values=self.input_files[category],
                    variable=var,
                    state="readonly"
                )
                combo.pack(fill="x", pady=(0, 10))

                if found_files:
                    var.set(found_files[0].name)

    def _populate_analysis_steps(self) -> None:
        """Populate analysis steps based on trial-level configuration."""
        # Clear existing steps
        for widget in self.steps_frame.winfo_children():
            widget.destroy()

        self.step_vars = {}

        for group_name, steps in self.step_groups.items():
            # Group label
            ctk.CTkLabel(
                self.steps_frame,
                text=group_name,
                font=("Segoe UI", 9, "bold"),
                text_color="#0084ff"
            ).pack(anchor="w", pady=(10, 5))

            # Step checkboxes
            for step in steps:
                var = ctk.BooleanVar(value=False)
                self.step_vars[step.value] = var

                checkbox = ctk.CTkCheckBox(
                    self.steps_frame,
                    text=step.value.replace("_", " ").title(),
                    variable=var,
                    font=("Segoe UI", 9)
                )
                checkbox.pack(anchor="w", pady=2)

    def _load_settings_file(self) -> None:
        """Load analysis settings from trial_settings.xml."""
        if not self.current_path:
            return

        settings_file = self.current_path / "trial_settings.xml"
        if not settings_file.exists():
            logger.debug(f"No settings file found: {settings_file}")
            return

        try:
            tree = ET.parse(settings_file)
            root = tree.getroot()

            # Load step configurations
            for step_elem in root.findall(".//step"):
                step_name = step_elem.get("name")
                enabled = step_elem.get("enabled", "false").lower() == "true"

                if step_name in self.step_vars:
                    self.step_vars[step_name].set(enabled)

            logger.info(f"Settings loaded from: {settings_file}")

        except Exception as e:
            logger.error(f"Failed to load settings file: {e}")

    def _save_settings_file(self) -> None:
        """Save current analysis settings to trial_settings.xml."""
        if not self.current_path:
            self.status_callback("No trial loaded", "warning")
            return

        try:
            settings_file = self.current_path / "trial_settings.xml"

            # Create root element
            root = ET.Element("trial_settings")

            # Add selected files
            files_elem = ET.SubElement(root, "input_files")
            for category, var in self.file_vars.items():
                file_elem = ET.SubElement(files_elem, "file")
                file_elem.set("type", category)
                file_elem.set("name", var.get())

            # Add analysis steps
            steps_elem = ET.SubElement(root, "analysis_steps")
            for step_name, var in self.step_vars.items():
                step_elem = ET.SubElement(steps_elem, "step")
                step_elem.set("name", step_name)
                step_elem.set("enabled", "true" if var.get() else "false")

            # Pretty print and save
            xml_str = xml.dom.minidom.parseString(ET.tostring(root)).toprettyxml()
            with open(settings_file, "w") as f:
                f.write(xml_str)

            self.status_callback("Settings saved successfully", "success")
            logger.info(f"Settings saved to: {settings_file}")

        except Exception as e:
            self.status_callback(f"Failed to save settings: {e}", "error")
            logger.error(f"Settings save error: {e}")

    def _reload_files_and_settings(self) -> None:
        """Reload files and settings from current trial."""
        if not self.current_path:
            self.status_callback("No trial loaded", "warning")
            return

        self._scan_files()
        self._load_settings_file()
        self.status_callback("Files and settings reloaded", "success")

    def _edit_settings_file(self) -> None:
        """Open settings file in default text editor."""
        if not self.current_path:
            self.status_callback("No trial loaded", "warning")
            return

        settings_file = self.current_path / "trial_settings.xml"
        if settings_file.exists():
            os.startfile(str(settings_file))
        else:
            self.status_callback("Settings file not found", "warning")

    def _get_available_subjects(self) -> list:
        """Get list of available subjects in SIMULATIONS_DIR."""
        if not os.path.exists(SIMULATIONS_DIR):
            return []

        subjects = []
        try:
            for item in os.listdir(SIMULATIONS_DIR):
                item_path = os.path.join(SIMULATIONS_DIR, item)
                if os.path.isdir(item_path):
                    subjects.append(item)
        except Exception as e:
            logger.error(f"Error reading subjects directory: {e}")

        return sorted(subjects)

    def _get_available_trials(self, subject: str, session: str) -> list:
        """Get list of available trials for a given subject and session."""
        trials = []
        try:
            subject_session_path = os.path.join(SIMULATIONS_DIR, subject, session)
            if os.path.exists(subject_session_path):
                for item in os.listdir(subject_session_path):
                    item_path = os.path.join(subject_session_path, item)
                    if os.path.isdir(item_path):
                        trials.append(item)
        except Exception as e:
            logger.error(f"Error reading trials directory: {e}")

        return sorted(trials)

    def _copy_input_files_dialog(self) -> None:
        """Open dialog to select source trial and copy input files."""
        if not self.current_path:
            self.status_callback("No trial loaded", "warning")
            messagebox.showwarning("No Trial Loaded", "Please load a trial first")
            return

        # Create dialog window
        dialog = ctk.CTkToplevel(self)
        dialog.title("Copy Input Files from Trial")
        dialog.geometry("600x250")
        dialog.grab_set()

        # Source trial selection
        ctk.CTkLabel(dialog, text="Source Trial Directory:", font=("Segoe UI", 11, "bold")).pack(
            anchor="w", padx=10, pady=(10, 5)
        )

        # Frame for textbox and browse button
        trial_frame = ctk.CTkFrame(dialog)
        trial_frame.pack(fill="x", padx=10, pady=(0, 10))
        trial_frame.grid_columnconfigure(0, weight=1)

        source_trial_var = ctk.StringVar(value="")
        trial_entry = ctk.CTkEntry(
            trial_frame,
            textvariable=source_trial_var,
            placeholder_text="Enter path or use Browse button"
        )
        trial_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        def browse_source_trial():
            """Browse for source trial directory."""
            path = filedialog.askdirectory(title="Select Source Trial Directory")
            if path:
                source_trial_var.set(path)

        ctk.CTkButton(
            trial_frame,
            text="Browse",
            width=80,
            command=browse_source_trial
        ).grid(row=0, column=1, sticky="w")

        # Replace checkbox
        replace_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            dialog,
            text="Replace existing files",
            variable=replace_var,
            font=("Segoe UI", 10)
        ).pack(anchor="w", padx=10, pady=10)

        # Info label
        info_label = ctk.CTkLabel(
            dialog,
            text="Files to copy: trial_settings.xml, EMG files, markers, GRF, model, events, C3D",
            font=("Segoe UI", 9),
            text_color="#888888"
        )
        info_label.pack(anchor="w", padx=10, pady=5)

        # Buttons
        button_frame = ctk.CTkFrame(dialog)
        button_frame.pack(fill="x", padx=10, pady=10)

        def on_copy():
            """Execute the copy operation."""
            source_path = source_trial_var.get().strip()
            if not source_path:
                messagebox.showwarning("Error", "Please specify a source trial path")
                return

            if not os.path.exists(source_path):
                messagebox.showerror("Error", f"Source path does not exist:\n{source_path}")
                return

            # Extract subject name from source path
            try:
                parts = Path(source_path).parts
                if "simulations" in parts:
                    idx = parts.index("simulations")
                    if len(parts) > idx + 1:
                        src_subject = parts[idx + 1]
                    else:
                        messagebox.showerror("Error", "Cannot extract subject from source path")
                        return
                else:
                    messagebox.showerror("Error", "Source path does not contain 'simulations' directory")
                    return
            except Exception as e:
                messagebox.showerror("Error", f"Failed to parse source path: {e}")
                logger.error(f"Path parsing error: {e}")
                return

            # Perform copy in background thread
            thread = threading.Thread(
                target=self._perform_copy_input_files,
                args=(src_subject, replace_var.get()),
                daemon=True
            )
            thread.start()
            dialog.destroy()

        ctk.CTkButton(
            button_frame,
            text="Copy",
            fg_color="#28a745",
            hover_color="#218838",
            command=on_copy
        ).pack(side="left", padx=5, expand=True, fill="x")

        ctk.CTkButton(
            button_frame,
            text="Cancel",
            fg_color="#555555",
            command=dialog.destroy
        ).pack(side="left", padx=5, expand=True, fill="x")

    def _perform_copy_input_files(self, src_subject: str, replace: bool) -> None:
        """Perform the actual file copy operation."""
        try:
            self.status_callback("Copying input files...", "info")

            # Create Analyse instance for current trial to use copy_input_files method
            analyser = Analyse(str(self.current_path))
            analyser.copy_input_files(src_subject, replace=replace)

            # Reload files after copy
            self.after(500, self._reload_files_and_settings)

            self.status_callback("Input files copied successfully", "success")
            messagebox.showinfo("Success", "Input files copied successfully")
            logger.info(f"Copied input files from {src_subject}")

        except Exception as e:
            self.status_callback(f"Failed to copy files: {e}", "error")
            messagebox.showerror("Error", f"Failed to copy files:\n{e}")
            logger.error(f"Copy input files error: {e}")

    def _run_analysis(self) -> None:
        """Start analysis in background thread."""
        if not self.current_path:
            self.status_callback("No trial loaded", "error")
            return

        # Get enabled steps
        # Get selected steps (filter out RESET_SETTINGS which is handled separately)
        selected_step_names = [name for name, var in self.step_vars.items() if var.get()]
        reset_settings = "RESET_SETTINGS" in selected_step_names
        analysis_step_names = [name for name in selected_step_names if name != "RESET_SETTINGS"]

        enabled_steps = [
            self._string_to_step(name).value
            for name in analysis_step_names
        ]

        if not enabled_steps and not reset_settings:
            self.status_callback("No analysis steps selected", "warning")
            return

        # Disable run button, enable stop button
        self.run_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")

        # Create analysis config
        config = AnalysisConfig(
            trial_path=str(self.current_path),
            steps=enabled_steps,
            parameters={},
            replace_existing=True,
            reset_settings=reset_settings
        )

        # Run in background thread
        self.analysis_thread = threading.Thread(
            target=self._run_analysis_thread,
            args=(config,),
            daemon=True
        )
        self.analysis_thread.start()
        self.status_callback("Analysis running...", "info")

    def _run_analysis_thread(self, config: AnalysisConfig) -> None:
        """Run analysis in background thread."""
        try:
            success, error = self.runner.run_analysis(config)

            if success:
                self.status_callback("Analysis completed successfully", "success")
                logger.info("Analysis completed successfully")
            else:
                self.status_callback(f"Analysis failed: {error}", "error")
                logger.error(f"Analysis failed: {error}")

        except Exception as e:
            self.status_callback(f"Unexpected error: {e}", "error")
            logger.error(f"Analysis error: {e}")

        finally:
            self.run_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")

    def _stop_analysis(self) -> None:
        """Stop the running analysis."""
        self.runner.stop_analysis()
        self.status_callback("Analysis stopped", "warning")
        self.run_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def _on_progress(self, progress_info: dict) -> None:
        """Handle progress updates from analysis runner."""
        step = progress_info.get("step", "")
        status = progress_info.get("status", "")
        progress = progress_info.get("progress", 0)

        if progress is not None:
            self.progress_bar.set(progress / 100)

        status_msg = f"{step}: {status}" if step else status
        self.status_label.configure(text=status_msg)

        logger.debug(f"Progress: {status_msg}")

    def _string_to_step(self, step_name: str) -> AnalysisStep:
        """Convert step name string to AnalysisStep enum."""
        for step in AnalysisStep:
            if step.value == step_name:
                return step
        raise ValueError(f"Unknown step: {step_name}")
