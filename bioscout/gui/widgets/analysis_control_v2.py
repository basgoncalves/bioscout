"""Improved Analysis Control Tab - Support for trial and session-level analysis with settings persistence."""

import customtkinter as ctk
from pathlib import Path
import sys
import threading
from tkinter import filedialog, messagebox
import xml.etree.ElementTree as ET
import xml.dom.minidom
import os

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.config_manager import ConfigManager
from core.analysis_runner import AnalysisRunner, AnalysisStep, AnalysisConfig
from utils.logger import logger


class AnalysisControlTabV2(ctk.CTkFrame):
    """Improved tab for controlling analysis at trial or session level."""

    def __init__(self, parent, config_manager: ConfigManager, status_callback):
        """Initialize Analysis Control Tab V2."""
        super().__init__(parent)
        self.config_manager = config_manager
        self.status_callback = status_callback
        self.runner = AnalysisRunner(progress_callback=self._on_progress)
        self.analysis_thread = None

        # State
        self.current_path = None
        self.analysis_level = "trial"
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

        ctk.CTkLabel(top_frame, text="Analysis", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 10)
        )

        ctk.CTkLabel(top_frame, text="Directory:", font=("Segoe UI", 10)).grid(
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
            row=1, column=3, sticky="w"
        )

        ctk.CTkLabel(top_frame, text="Analysis Level:", font=("Segoe UI", 10)).grid(
            row=2, column=0, sticky="w", pady=(10, 0), padx=(0, 5)
        )

        level_frame = ctk.CTkFrame(top_frame)
        level_frame.grid(row=2, column=1, columnspan=2, sticky="w", pady=(10, 0))

        self.level_var = ctk.StringVar(value="trial")
        ctk.CTkRadioButton(
            level_frame, text="Single Trial", variable=self.level_var, value="trial",
            command=self._on_level_change
        ).pack(side="left", padx=(0, 20))

        ctk.CTkRadioButton(
            level_frame, text="Entire Session", variable=self.level_var, value="session",
            command=self._on_level_change
        ).pack(side="left")

        # MIDDLE SECTION: Input Files & Steps
        middle_frame = ctk.CTkFrame(self)
        middle_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        middle_frame.grid_rowconfigure(1, weight=1)
        middle_frame.grid_columnconfigure(0, weight=1)
        middle_frame.grid_columnconfigure(1, weight=1)
        middle_frame.grid_columnconfigure(2, weight=1)

        # Input Files Panel
        left_panel = ctk.CTkFrame(middle_frame, corner_radius=8)
        left_panel.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 5))
        left_panel.grid_rowconfigure(2, weight=1)
        self.middle_frame = middle_frame  # Store reference for trial panel

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

        # Store step groups for both trial and session levels - with Reset Settings at the top
        self.trial_step_groups = {
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

        self.session_step_groups = {
            "Session-Level Analysis": [
                AnalysisStep.CEINMS_CALIBRATION,
            ],
        }

        self._populate_analysis_steps()

        # Trial Selection Panel (for session-level EMG normalisation)
        self.trial_panel = ctk.CTkFrame(middle_frame, corner_radius=8)
        self.trial_panel.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(self.trial_panel, text="Trials (EMG Normalise)", font=("Segoe UI", 11, "bold")).pack(
            padx=10, pady=(10, 5), anchor="w"
        )

        # Header with Select All / Deselect All buttons
        header_frame = ctk.CTkFrame(self.trial_panel, fg_color="transparent")
        header_frame.pack(fill="x", padx=10, pady=(0, 5))
        ctk.CTkButton(header_frame, text="All", width=40, command=self._select_all_trials, font=("Segoe UI", 9)).pack(side="left", padx=2)
        ctk.CTkButton(header_frame, text="None", width=40, command=self._deselect_all_trials, font=("Segoe UI", 9)).pack(side="left", padx=2)

        self.trials_frame = ctk.CTkScrollableFrame(self.trial_panel)
        self.trials_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.trial_vars = {}

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

        ctk.CTkLabel(self, text="Output Log", font=("Segoe UI", 10, "bold")).grid(
            row=3, column=0, sticky="w", padx=10, pady=(10, 5)
        )

        self.log_text = ctk.CTkTextbox(self, height=80, wrap="word")
        self.log_text.grid(row=4, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.grid_rowconfigure(4, weight=0)

    def _browse_path(self) -> None:
        """Browse for trial or session directory."""
        path = filedialog.askdirectory(title="Select Trial or Session Directory")
        if path:
            self._load_path(path)

    def _validate_pasted_path(self) -> None:
        """Validate and load a pasted path."""
        path_str = self.path_var.get().strip()
        if not path_str or path_str == "Paste path or browse...":
            self._log_message("⚠ Please enter a valid path")
            return

        path_str = path_str.replace("/", "\\").strip('"').strip("'")
        path = Path(path_str)

        if not path.exists():
            self._log_message(f"✗ Path does not exist: {path_str}")
            messagebox.showerror("Error", f"Path not found:\n{path_str}")
            return

        if not path.is_dir():
            self._log_message(f"✗ Not a directory: {path_str}")
            messagebox.showerror("Error", f"Not a directory:\n{path_str}")
            return

        self._load_path(str(path))

    def _load_path(self, path: str) -> None:
        """Load and process a trial/session path."""
        self.current_path = Path(path)
        self.path_var.set(str(self.current_path))
        self._load_trial_settings()
        self._reload_input_files()
        self._log_message(f"✓ Loaded: {path}")

    def _on_level_change(self) -> None:
        """Handle analysis level change."""
        self.analysis_level = self.level_var.get()
        self._log_message(f"Analysis level: {'Entire Session' if self.analysis_level == 'session' else 'Single Trial'}")
        self._populate_analysis_steps()

    def _populate_analysis_steps(self) -> None:
        """Populate analysis steps based on current level."""
        # Clear existing steps
        for widget in self.steps_frame.winfo_children():
            widget.destroy()

        step_groups = self.session_step_groups if self.analysis_level == "session" else self.trial_step_groups

        for group_name, steps in step_groups.items():
            group_label = ctk.CTkLabel(
                self.steps_frame, text=group_name, font=("Segoe UI", 9, "bold"), text_color="#0084ff"
            )
            group_label.pack(anchor="w", padx=5, pady=(8, 3))

            for step in steps:
                if step not in self.step_vars:
                    self.step_vars[step] = ctk.BooleanVar(value=False)

                checkbox = ctk.CTkCheckBox(
                    self.steps_frame, text=step.value.replace('_', ' ').title(),
                    variable=self.step_vars[step],
                    font=("Segoe UI", 9),
                    command=lambda s=step: self._on_step_selection_changed(s)
                )
                checkbox.pack(anchor="w", padx=15, pady=2)

    def _reload_files_and_settings(self) -> None:
        """Reload both settings and input files from XML."""
        self._load_trial_settings()
        self._reload_input_files()

    def _reload_input_files(self) -> None:
        """Reload and display input files for current path."""
        if not self.current_path:
            return

        for widget in self.files_frame.winfo_children():
            widget.destroy()

        self.input_files = {}
        self.file_vars = {}

        common_files = {
            'c3d': '*.c3d',
            'markers': '*marker*.trc',
            'emg': ('*emg*.mot', '*emg*.sto'),  # Support both MOT and STO formats
            'grf': '*grf*.mot',
        }

        model_files = {}
        search_dirs = [self.current_path, self.current_path.parent, self.current_path.parent.parent]
        for search_dir in search_dirs:
            if search_dir.exists():
                osim_files = list(search_dir.glob('*.osim'))
                if osim_files:
                    model_files['osim_model'] = osim_files
                    break

        for file_type, pattern in common_files.items():
            # Handle both single pattern and tuple of patterns
            if isinstance(pattern, tuple):
                files = []
                for p in pattern:
                    files.extend(list(self.current_path.glob(p)))
            else:
                files = list(self.current_path.glob(pattern))

            if files:
                self.input_files[file_type] = files
                frame = ctk.CTkFrame(self.files_frame)
                frame.pack(fill="x", pady=3)

                label = ctk.CTkLabel(frame, text=file_type.capitalize(), width=60, font=("Segoe UI", 9))
                label.pack(side="left", padx=(0, 5))

                file_options = [f.name for f in files]

                # Check if we have a saved selection for this file type
                default_value = file_options[0]
                if file_type in self.selected_files and self.selected_files[file_type]:
                    saved_name = Path(self.selected_files[file_type]).name
                    if saved_name in file_options:
                        default_value = saved_name

                selected = ctk.StringVar(value=default_value)
                self.file_vars[file_type] = selected
                dropdown = ctk.CTkOptionMenu(frame, variable=selected, values=file_options)
                dropdown.pack(side="left", expand=True, fill="x")


        if model_files:
            frame = ctk.CTkFrame(self.files_frame)
            frame.pack(fill="x", pady=3)
            label = ctk.CTkLabel(frame, text="OSIM Model", width=60, font=("Segoe UI", 9, "bold"), text_color="#ffaa00")
            label.pack(side="left", padx=(0, 5))
            file_options = [f.name for f in model_files['osim_model']]
            selected = ctk.StringVar(value=file_options[0])
            self.file_vars['osim_model'] = selected
            dropdown = ctk.CTkOptionMenu(frame, variable=selected, values=file_options)
            dropdown.pack(side="left", expand=True, fill="x")

        if not self.input_files and not model_files:
            ctk.CTkLabel(self.files_frame, text="No input files found", text_color="#ff9999").pack(pady=5)

        self._log_message(f"Found {sum(len(v) for v in self.input_files.values())} input files" + (" + OSIM model" if model_files else ""))

    def _load_trial_settings(self) -> None:
        """Load trial settings from XML file, generate if not found."""
        if not self.current_path:
            return

        settings_file = self.current_path / "trial_settings.xml"

        if not settings_file.exists():
            self._generate_default_settings(settings_file)
            return

        try:
            tree = ET.parse(settings_file)
            root = tree.getroot()

            analysis_level = root.findtext("analysis_level", "trial")
            self.level_var.set(analysis_level)
            self._on_level_change()

            analysis_steps_elem = root.find("analysis_steps")
            if analysis_steps_elem is not None:
                enabled_steps = [step.text for step in analysis_steps_elem.findall("step")]
                for step, var in self.step_vars.items():
                    var.set(step.value in enabled_steps)

            self.selected_files = {}
            for tag in ['c3d', 'markers', 'emg', 'grf_mot', 'model_dir']:
                value = root.findtext(tag)
                if value:
                    self.selected_files[tag] = value

            self._log_message(f"✓ Loaded settings from {settings_file.name}")

        except Exception as e:
            self._log_message(f"⚠ Could not load settings: {str(e)[:100]}")

    def _generate_default_settings(self, settings_file: Path) -> None:
        """Generate default trial_settings.xml from template."""
        try:
            template_path = Path(__file__).parent.parent.parent / "config" / "trial_settings_template.xml"
            if not template_path.exists():
                self._log_message(f"⚠ Template not found: {template_path}")
                return

            tree = ET.parse(template_path)
            root = tree.getroot()

            trial_name = self.current_path.name
            trial_elem = root.find("trial")
            if trial_elem is not None:
                trial_elem.text = trial_name

            path_parts = self.current_path.parts
            if len(path_parts) >= 3:
                session = path_parts[-2]
                subject = path_parts[-3]

                subject_elem = root.find("subject")
                if subject_elem is not None and subject != "simulations":
                    subject_elem.text = subject

                session_elem = root.find("session")
                if session_elem is not None:
                    session_elem.text = session

            self._save_pretty_xml(ET.ElementTree(root), str(settings_file))
            self._log_message(f"✓ Generated default settings: {settings_file.name}")

        except Exception as e:
            self._log_message(f"⚠ Could not generate settings: {str(e)[:100]}")

    def _edit_settings_file(self) -> None:
        """Edit trial_settings.xml file."""
        if not self.current_path:
            messagebox.showwarning("Warning", "Please select a trial directory first")
            return

        settings_file = self.current_path / "trial_settings.xml"

        if not settings_file.exists():
            response = messagebox.askyesno("Create Settings", f"Settings file not found.\nCreate one at:\n{settings_file}?")
            if response:
                self._generate_default_settings(settings_file)
            else:
                return

        import subprocess
        import platform
        try:
            if platform.system() == "Windows":
                subprocess.Popen(['notepad', str(settings_file)])
            elif platform.system() == "Darwin":
                subprocess.Popen(['open', '-a', 'TextEdit', str(settings_file)])
            else:
                subprocess.Popen(['gedit', str(settings_file)])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open file: {e}")

    def _save_settings_file(self) -> None:
        """Save current settings to trial_settings.xml file."""
        if not self.current_path:
            messagebox.showwarning("Warning", "Please select a trial directory first")
            return

        settings_file = self.current_path / "trial_settings.xml"

        try:
            root = None
            if settings_file.exists():
                try:
                    tree = ET.parse(settings_file)
                    root = tree.getroot()
                except:
                    pass

            if root is None:
                self._generate_default_settings(settings_file)
                tree = ET.parse(settings_file)
                root = tree.getroot()

            # Save analysis level
            level_elem = root.find("analysis_level")
            if level_elem is None:
                level_elem = ET.SubElement(root, "analysis_level")
            level_elem.text = self.level_var.get()

            # Save analysis steps
            steps_elem = root.find("analysis_steps")
            if steps_elem is None:
                steps_elem = ET.SubElement(root, "analysis_steps")
            else:
                for step in steps_elem.findall("step"):
                    steps_elem.remove(step)

            for step, var in self.step_vars.items():
                if var.get():
                    ET.SubElement(steps_elem, "step").text = step.value

            # Save file selections
            if 'c3d' in self.file_vars and self.file_vars['c3d'].get():
                c3d_elem = root.find("c3d")
                if c3d_elem is None:
                    c3d_elem = ET.SubElement(root, "c3d")
                c3d_elem.text = str(self.current_path / self.file_vars['c3d'].get())

            if 'markers' in self.file_vars and self.file_vars['markers'].get():
                markers_elem = root.find("markers")
                if markers_elem is None:
                    markers_elem = ET.SubElement(root, "markers")
                markers_elem.text = str(self.current_path / self.file_vars['markers'].get())

            if 'emg' in self.file_vars and self.file_vars['emg'].get():
                emg_elem = root.find("emg")
                if emg_elem is None:
                    emg_elem = ET.SubElement(root, "emg")
                emg_elem.text = str(self.current_path / self.file_vars['emg'].get())

            if 'grf' in self.file_vars and self.file_vars['grf'].get():
                grf_elem = root.find("grf_mot")
                if grf_elem is None:
                    grf_elem = ET.SubElement(root, "grf_mot")
                grf_elem.text = str(self.current_path / self.file_vars['grf'].get())

            self._save_pretty_xml(ET.ElementTree(root), str(settings_file))

            self._log_message(f"✓ Settings saved: {settings_file.name}")
            messagebox.showinfo("Success", f"Settings saved to:\n{settings_file.name}")

        except Exception as e:
            self._log_message(f"✗ Failed to save settings: {e}")
            messagebox.showerror("Error", f"Failed to save settings:\n{e}")

    def _save_pretty_xml(self, tree: ET.ElementTree, save_path: str) -> None:
        """Save XML tree with proper indentation."""
        rough_string = ET.tostring(tree.getroot(), 'utf-8')
        reparsed = xml.dom.minidom.parseString(rough_string)
        pretty_xml = reparsed.toprettyxml(indent="   ")
        pretty_xml_no_blanks = "\n".join([line for line in pretty_xml.splitlines() if line.strip()])
        with open(save_path, 'w') as file:
            file.write(pretty_xml_no_blanks)

    def _run_analysis(self) -> None:
        """Start analysis."""
        if not self.current_path:
            messagebox.showerror("Error", "Please select a trial or session directory")
            return

        # Filter out RESET_SETTINGS (it's a string, not an AnalysisStep enum)
        enabled_steps = {step: var.get() for step, var in self.step_vars.items() if step != "RESET_SETTINGS"}
        reset_settings = self.step_vars.get("RESET_SETTINGS", ctk.BooleanVar(value=False)).get()

        if not any(enabled_steps.values()) and not reset_settings:
            messagebox.showwarning("Warning", "Select at least one analysis step")
            return

        self.run_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")

        self.analysis_thread = threading.Thread(
            target=self._run_analysis_thread,
            args=(enabled_steps, reset_settings),
            daemon=True
        )
        self.analysis_thread.start()

    def _run_analysis_thread(self, enabled_steps: dict, reset_settings: bool = False) -> None:
        """Run analysis in background thread."""
        try:
            if self.analysis_level == "session":
                self._run_session_analysis(enabled_steps, reset_settings)
            else:
                self._run_trial_analysis(enabled_steps, reset_settings)
        finally:
            self.run_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")

    def _run_trial_analysis(self, enabled_steps: dict, reset_settings: bool = False) -> None:
        """Run analysis on single trial."""
        self._log_message("="*60)
        self._log_message(f"Starting trial analysis: {self.current_path.name}")
        self._log_message("="*60)

        config = AnalysisConfig(
            trial_path=str(self.current_path),
            steps=enabled_steps,
            parameters=self.config_manager.get_section("analysis"),
            reset_settings=reset_settings
        )

        success, error = self.runner.run_analysis(config)

        if success:
            self._log_message("="*60)
            self._log_message("✓ Analysis completed successfully!")
            self._log_message("="*60)
            self.status_callback("Analysis completed", "success")
        else:
            self._log_message("="*60)
            self._log_message(f"✗ Analysis failed: {error}")
            self._log_message("="*60)
            self.status_callback("Analysis failed", "error")

    def _run_session_analysis(self, enabled_steps: dict, reset_settings: bool = False) -> None:
        """Run analysis on entire session (all trials)."""
        self._log_message("="*60)
        self._log_message(f"Starting session analysis: {self.current_path.name}")
        self._log_message("="*60)

        trial_dirs = [d for d in self.current_path.iterdir() if d.is_dir()]

        if not trial_dirs:
            self._log_message("No trial directories found in session")
            self.status_callback("No trials found", "error")
            return

        self._log_message(f"Found {len(trial_dirs)} trials")

        successful = 0
        failed = 0

        for i, trial_dir in enumerate(trial_dirs, 1):
            self._log_message(f"\n[{i}/{len(trial_dirs)}] Analyzing: {trial_dir.name}")

            config = AnalysisConfig(
                trial_path=str(trial_dir),
                steps=enabled_steps,
                parameters=self.config_manager.get_section("analysis"),
                reset_settings=reset_settings
            )

            success, error = self.runner.run_analysis(config)

            if success:
                successful += 1
                self._log_message(f"✓ {trial_dir.name} completed")
            else:
                failed += 1
                self._log_message(f"✗ {trial_dir.name} failed: {error}")

            progress = (i / len(trial_dirs))
            self.progress_bar.set(progress)

        self._log_message("\n" + "="*60)
        self._log_message(f"Session analysis complete: {successful}/{len(trial_dirs)} successful")
        self._log_message("="*60)

        if failed == 0:
            self.status_callback(f"Session complete ({successful} trials)", "success")
        else:
            self.status_callback(f"Session complete ({successful}/{len(trial_dirs)})", "warning")

    def _stop_analysis(self) -> None:
        """Stop running analysis."""
        self.runner.stop_analysis()
        self._log_message("Analysis stopped by user")
        self.status_callback("Stopped", "warning")

    def _on_progress(self, progress_info: dict) -> None:
        """Update progress from runner."""
        step = progress_info.get('step', '')
        status = progress_info.get('status', '')
        progress = progress_info.get('progress')

        self.status_label.configure(text=f"{step}: {status}")

        if progress is not None:
            self.progress_bar.set(progress / 100)

        self._log_message(f"[{step}] {status}")

    def _on_step_selection_changed(self, step: AnalysisStep) -> None:
        """Handle step selection change - show/hide trial panel for CEINMS Calibration."""
        # Trial panel display is now handled by CEINMS_CALIBRATION if needed
        # This method is kept for future extensibility
        pass

    def _populate_trial_list(self) -> None:
        """Populate list of trials with EMG files in current session."""
        if not self.current_path or self.analysis_level != "session":
            return

        # Clear existing trial checkboxes
        for widget in self.trials_frame.winfo_children():
            widget.destroy()
        self.trial_vars = {}

        # Find all trial directories with EMG files in the session folder
        try:
            session_folder = self.current_path.parent  # Parent of current trial
            trial_dirs = sorted([d for d in session_folder.iterdir() if d.is_dir()])
            trials_with_emg = []

            for trial_dir in trial_dirs:
                # Check if trial has EMG file (*.mot or *.sto with "emg" in filename)
                emg_files = list(trial_dir.glob("*emg*.mot")) + list(trial_dir.glob("*emg*.sto"))
                if emg_files:
                    trials_with_emg.append((trial_dir.name, trial_dir))

            if not trials_with_emg:
                ctk.CTkLabel(self.trials_frame, text="No trials with EMG files", text_color="#ff9999").pack(pady=5)
                return

            for trial_name, trial_path in trials_with_emg:
                var = ctk.BooleanVar(value=True)  # Select all by default
                self.trial_vars[trial_name] = var
                ctk.CTkCheckBox(
                    self.trials_frame, text=trial_name, variable=var,
                    font=("Segoe UI", 9)
                ).pack(anchor="w", padx=10, pady=2)

            self._log_message(f"Found {len(trials_with_emg)} trial(s) with EMG files in session")

        except Exception as e:
            self._log_message(f"Error populating trial list: {str(e)[:100]}")

    def _select_all_trials(self) -> None:
        """Select all trials."""
        for var in self.trial_vars.values():
            var.set(True)
        self._log_message(f"Selected all {len(self.trial_vars)} trials")

    def _deselect_all_trials(self) -> None:
        """Deselect all trials."""
        for var in self.trial_vars.values():
            var.set(False)
        self._log_message("Deselected all trials")

    def _log_message(self, message: str) -> None:
        """Add message to log."""
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.update()
