"""
Session-Level Analysis Control Tab - Allows session-wide analysis with automatic trial discovery.
Version: 2.1.0
"""

import customtkinter as ctk
from pathlib import Path
import sys
import threading
from tkinter import filedialog, messagebox
import os

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.config_manager import ConfigManager
from core.analysis_runner import AnalysisRunner, AnalysisStep, AnalysisConfig
from core.session_manager import SessionManager, TrialValidator
from utils.logger import logger
from utils import SIMULATIONS_DIR
from utils.xml_utils import save_pretty_xml
from version import get_version


class AnalysisControlSessionTab(ctk.CTkFrame):
    """Session-level analysis control tab."""

    VERSION = "2.1.0"

    def __init__(self, parent, config_manager: ConfigManager, status_callback):
        """Initialize Session Analysis Control Tab."""
        super().__init__(parent)
        self.config_manager = config_manager
        self.status_callback = status_callback
        self.session_manager = None
        self.runner = AnalysisRunner(progress_callback=self._on_progress)
        self.analysis_thread = None

        # State
        self.current_session = None
        self.selected_trials = {}
        self.trial_vars = {}
        self.session_label = None  # Will be set in _create_widgets

        self._create_widgets()

    def set_session_dir(self, session_dir: str):
        """Receive session directory from main window."""
        if session_dir:
            self._load_session(session_dir)

    def _create_widgets(self) -> None:
        """Create UI widgets."""
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # TOP SECTION: Session Label (shows current session from main window)
        top_frame = ctk.CTkFrame(self)
        top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        top_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top_frame, text="Session-Level Analysis", font=("Segoe UI", 14, "bold")).pack(
            anchor="w", pady=(0, 5)
        )

        self.session_label = ctk.CTkLabel(top_frame, text="Session: Not set", font=("Segoe UI", 10, "bold"), text_color="#28a745")
        self.session_label.pack(anchor="w")

        # PATHS SECTION: Template Folder and Model Path
        paths_frame = ctk.CTkFrame(self)
        paths_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        paths_frame.grid_columnconfigure(1, weight=1)
        paths_frame.grid_columnconfigure(3, weight=1)

        # Template Folder Row
        ctk.CTkLabel(paths_frame, text="Template Folder:", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, sticky="w", padx=(0, 5)
        )

        self.template_path_var = ctk.StringVar(value="")
        self.template_path_var.trace_add("write", lambda *args: self._validate_template_path())
        self.template_path_entry = ctk.CTkEntry(paths_frame, textvariable=self.template_path_var, placeholder_text="Path to templates folder")
        self.template_path_entry.grid(row=0, column=1, sticky="ew", padx=5)

        ctk.CTkButton(
            paths_frame,
            text="Browse",
            width=80,
            command=self._browse_template_folder
        ).grid(row=0, column=2, sticky="ew", padx=5)

        self.template_status = ctk.CTkLabel(paths_frame, text="⚠️ Not found", text_color="#ffc107", font=("Segoe UI", 9))
        self.template_status.grid(row=0, column=3, sticky="w", padx=5)

        # Model Path Row
        ctk.CTkLabel(paths_frame, text="Model Path:", font=("Segoe UI", 10, "bold")).grid(
            row=1, column=0, sticky="w", padx=(0, 5), pady=(10, 0)
        )

        self.model_path_var = ctk.StringVar(value="")
        self.model_path_var.trace_add("write", lambda *args: self._validate_model_path())
        self.model_path_entry = ctk.CTkEntry(paths_frame, textvariable=self.model_path_var, placeholder_text="Path to OpenSim model (.osim)")
        self.model_path_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=(10, 0))

        ctk.CTkButton(
            paths_frame,
            text="Browse",
            width=80,
            command=self._browse_model_file
        ).grid(row=1, column=2, sticky="ew", padx=5, pady=(10, 0))

        self.model_status = ctk.CTkLabel(paths_frame, text="⚠️ Not found", text_color="#ffc107", font=("Segoe UI", 9))
        self.model_status.grid(row=1, column=3, sticky="w", padx=5, pady=(10, 0))

        # Update Trial Settings Button
        ctk.CTkButton(
            paths_frame,
            text="Update Trial Settings",
            fg_color="#0084ff",
            command=self._update_trial_settings,
            font=("Segoe UI", 10, "bold"),
            height=30
        ).grid(row=2, column=0, columnspan=4, sticky="ew", pady=(10, 0))

        # MIDDLE SECTION: Trial Selection & Analysis Steps
        middle_frame = ctk.CTkFrame(self)
        middle_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        middle_frame.grid_rowconfigure(0, weight=1)
        middle_frame.grid_columnconfigure(0, weight=1)
        middle_frame.grid_columnconfigure(1, weight=1)

        # Trial Selection Panel
        left_panel = ctk.CTkFrame(middle_frame, corner_radius=8)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left_panel.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(left_panel, text="Available Trials", font=("Segoe UI", 11, "bold")).pack(
            padx=10, pady=(10, 5), anchor="w"
        )

        self.trials_frame = ctk.CTkScrollableFrame(left_panel)
        self.trials_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Trial Selection Controls
        trial_ctrl_frame = ctk.CTkFrame(left_panel)
        trial_ctrl_frame.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkButton(trial_ctrl_frame, text="Select All", height=28, command=self._select_all_trials).pack(fill="x", pady=(0, 3))
        ctk.CTkButton(trial_ctrl_frame, text="Deselect All", height=28, command=self._deselect_all_trials).pack(fill="x")

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

        # Define analysis step groups - with Reset Settings at the top
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
        }

        self._populate_analysis_steps()

        # BOTTOM SECTION: Progress & Controls
        bottom_frame = ctk.CTkFrame(self)
        bottom_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=10)
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
            button_frame, text="[RUN] Run Pipeline", fg_color="#28a745", hover_color="#218838",
            font=("Segoe UI", 11, "bold"), height=40, command=self._run_analysis
        )
        self.run_btn.pack(side="left", padx=5, expand=True, fill="both")

        self.stop_btn = ctk.CTkButton(
            button_frame, text="[STOP] Stop", fg_color="#dc3545", hover_color="#c82333",
            font=("Segoe UI", 11), height=40, command=self._stop_analysis, state="disabled"
        )
        self.stop_btn.pack(side="left", padx=5, expand=True, fill="both")


    def _load_session(self, session_path: str) -> None:
        """Load session and discover trials."""
        try:
            self.current_session = Path(session_path)
            self.session_manager = SessionManager(session_path)

            # Discover trials
            trials = self.session_manager.discover_trials()
            if not trials:
                self.status_callback("No valid trials found in session", "warning")
                return

            # Update UI
            if self.session_label:
                self.session_label.configure(text=f"Session: {self.current_session.name}")
            self._populate_trial_list()

            # Auto-populate template and model paths from first trial if empty
            self._auto_populate_paths_from_first_trial()

            self.status_callback(f"[OK] Session loaded: {self.current_session.name} ({len(trials)} trials)", "success")
            logger.info(f"Session loaded: {session_path}")

        except Exception as e:
            self.status_callback(f"[FAIL] Failed to load session: {e}", "error")
            logger.error(f"Session load error: {e}")

    def _populate_trial_list(self) -> None:
        """Populate trial list with status indicators."""
        # Clear existing widgets
        for widget in self.trials_frame.winfo_children():
            widget.destroy()
        self.trial_vars = {}

        if not self.session_manager:
            return

        trial_list = self.session_manager.get_trial_list()

        for trial_info in trial_list:
            frame = ctk.CTkFrame(self.trials_frame)
            frame.pack(fill="x", pady=3)

            # Checkbox
            var = ctk.BooleanVar(value=False)
            checkbox = ctk.CTkCheckBox(
                frame,
                text=trial_info['name'],
                variable=var,
                onvalue=True,
                offvalue=False,
                font=("Segoe UI", 10)
            )
            checkbox.pack(side="left", padx=5)
            self.trial_vars[trial_info['name']] = var

            # Status indicator
            if trial_info['basic_complete']:
                status_color = "#28a745"  # Green
                status_text = "[OK]"
            else:
                status_color = "#dc3545"  # Red
                status_text = "[FAIL]"

            status_label = ctk.CTkLabel(
                frame,
                text=status_text,
                text_color=status_color,
                font=("Segoe UI", 12, "bold"),
                width=20
            )
            status_label.pack(side="right", padx=5)

    def _auto_populate_paths_from_first_trial(self) -> None:
        """Auto-populate template folder and model path from first trial's settings if fields are empty."""
        try:
            trial_list = self.session_manager.get_trial_list()
            if not trial_list:
                return

            first_trial_path = self.session_manager.get_trial_by_name(trial_list[0]['name'])
            if not first_trial_path:
                return

            settings_file = first_trial_path / "trial_settings.xml"
            if not settings_file.exists():
                return

            import xml.etree.ElementTree as ET
            tree = ET.parse(str(settings_file))
            root = tree.getroot()

            # Extract setup_dir and model_dir from first trial
            # (Also check legacy 'template_folder' and 'model' for backward compatibility)
            template_folder = None
            model_path = None

            for elem in root:
                if elem.tag == 'setup_dir' and elem.text:
                    template_folder = elem.text
                elif elem.tag == 'template_folder' and elem.text and not template_folder:
                    # Fallback for older XML format
                    template_folder = elem.text
                elif elem.tag == 'model_dir' and elem.text:
                    model_path = elem.text
                elif elem.tag == 'model' and elem.text and not model_path:
                    # Fallback for older XML format
                    model_path = elem.text

            # Convert relative paths to absolute
            if template_folder:
                if not Path(template_folder).is_absolute():
                    # Resolve relative path from TRIAL directory (where the XML file is)
                    resolved_path = (first_trial_path / template_folder).resolve()
                    template_folder = str(resolved_path)
                # Only set if current field is empty
                if not self.template_path_var.get().strip():
                    self.template_path_var.set(template_folder)
                    self._validate_template_path()
                    logger.info(f"Auto-populated setup_dir from XML: {template_folder}")

            if model_path:
                if not Path(model_path).is_absolute():
                    # Resolve relative path from TRIAL directory (where the XML file is)
                    resolved_path = (first_trial_path / model_path).resolve()
                    model_path = str(resolved_path)
                # Only set if current field is empty
                if not self.model_path_var.get().strip():
                    self.model_path_var.set(model_path)
                    self._validate_model_path()
                    logger.info(f"Auto-populated model_dir from XML: {model_path}")

            logger.info(f"Auto-populated paths from first trial: {trial_list[0]['name']}")

        except Exception as e:
            logger.warning(f"Could not auto-populate paths from first trial: {e}")

    def _populate_analysis_steps(self) -> None:
        """Populate analysis step checkboxes."""
        for group_name, steps in self.step_groups.items():
            # Group label
            ctk.CTkLabel(self.steps_frame, text=group_name, font=("Segoe UI", 10, "bold")).pack(
                padx=10, pady=(10, 5), anchor="w"
            )

            # Step checkboxes
            for step in steps:
                var = ctk.BooleanVar(value=False)

                # Handle custom steps (strings) vs AnalysisStep enums
                if isinstance(step, str):
                    step_name = step
                    display_text = step.replace('_', ' ').title()
                else:
                    step_name = step.value
                    display_text = step.value.replace('_', ' ').title()

                checkbox = ctk.CTkCheckBox(
                    self.steps_frame,
                    text=display_text,
                    variable=var,
                    font=("Segoe UI", 9)
                )
                checkbox.pack(padx=20, pady=2, anchor="w")
                self.step_vars[step_name] = var

    def _select_all_trials(self) -> None:
        """Select all trials."""
        for var in self.trial_vars.values():
            var.set(True)

    def _deselect_all_trials(self) -> None:
        """Deselect all trials."""
        for var in self.trial_vars.values():
            var.set(False)

    def _run_analysis(self) -> None:
        """Run analysis on selected trials."""
        if not self.current_session:
            self.status_callback("No session loaded", "error")
            return

        # Get selected trials
        selected = [name for name, var in self.trial_vars.items() if var.get()]
        if not selected:
            self.status_callback("No trials selected", "warning")
            return

        # Get selected steps (filter out RESET_SETTINGS which is handled separately)
        selected_step_names = [name for name, var in self.step_vars.items() if var.get()]
        reset_settings = "RESET_SETTINGS" in selected_step_names
        analysis_step_names = [name for name in selected_step_names if name != "RESET_SETTINGS"]

        enabled_steps = [self._string_to_step(name) for name in analysis_step_names]
        if not enabled_steps and not reset_settings:
            self.status_callback("No analysis steps selected", "warning")
            return

        # Disable buttons
        self.run_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")

        # Run analysis in background thread
        self.analysis_thread = threading.Thread(
            target=self._run_analysis_thread,
            args=(selected, enabled_steps, reset_settings),
            daemon=True
        )
        self.analysis_thread.start()
        self.status_callback("Analysis running...", "info")

    def _run_analysis_thread(self, selected_trials: list, enabled_steps: list, reset_settings: bool = False) -> None:
        """Run analysis in background thread."""
        successful = 0
        failed = 0

        # Check if C3D export is enabled
        c3d_export_enabled = any(
            isinstance(s, str) and s == "C3D_EXPORT"
            for s in enabled_steps
        )

        # Filter out C3D_EXPORT from OpenSim analysis steps
        analysis_steps = [
            step.value for step in enabled_steps
            if not isinstance(step, str)
        ]

        for trial_name in selected_trials:
            trial_path = self.session_manager.get_trial_by_name(trial_name)
            if not trial_path:
                failed += 1
                continue

            self.status_callback(f"Analyzing {trial_name}...", "info")

            # Validate trial
            is_valid, msg = self.session_manager.validate_for_analysis(trial_name)
            if not is_valid:
                self.status_callback(f"Trial {trial_name}: {msg}", "warning")
                failed += 1
                continue

            try:
                # Step 1: Export C3D if enabled
                if c3d_export_enabled:
                    c3d_file = trial_path / "c3dfile.c3d"
                    if c3d_file.exists():
                        self.status_callback(f"Exporting C3D for {trial_name}...", "info")
                        from utils.openSim import export_c3d
                        success, message = export_c3d(str(c3d_file))
                        if not success:
                            logger.warning(f"C3D export warning for {trial_name}: {message}")
                            self.status_callback(f"[WARN] C3D export: {message}", "warning")
                    else:
                        logger.warning(f"C3D file not found for {trial_name}: {c3d_file}")

                # Step 2: Run OpenSim analysis (including reset_settings) if anything is enabled
                if analysis_steps or reset_settings:
                    config = AnalysisConfig(
                        trial_path=str(trial_path),
                        steps=analysis_steps,
                        parameters={},
                        replace_existing=True,
                        reset_settings=reset_settings
                    )

                    success, error = self.runner.run_analysis(config)
                    if not success:
                        failed += 1
                        self.status_callback(f"[FAIL] {trial_name} failed: {error}", "error")
                        continue

                successful += 1
                self.status_callback(f"[OK] {trial_name} completed", "success")

            except Exception as e:
                failed += 1
                self.status_callback(f"[FAIL] {trial_name} error: {e}", "error")
                logger.error(f"Analysis error for {trial_name}: {e}")

        # Final status
        total = len(selected_trials)
        if failed == 0:
            self.status_callback(f"[OK] Session complete - All {successful} trials analyzed", "success")
        else:
            self.status_callback(f"[WARN] Session complete ({successful}/{total} successful)", "warning")

        self.run_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def _stop_analysis(self) -> None:
        """Stop running analysis."""
        self.runner.stop_analysis()
        self.status_callback("Analysis stopped", "warning")
        self.run_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def _on_progress(self, progress_info: dict) -> None:
        """Handle progress updates from runner."""
        step = progress_info.get('step', '')
        status = progress_info.get('status', '')
        progress = progress_info.get('progress', 0)

        if progress is not None:
            self.progress_bar.set(progress / 100)

        status_msg = f"{step}: {status}" if step else status
        self.status_label.configure(text=status_msg)
        logger.debug(f"Progress: {status_msg}")

    def _browse_template_folder(self) -> None:
        """Browse for template folder."""
        folder = filedialog.askdirectory(title="Select Template Folder")
        if folder:
            self.template_path_var.set(folder)
            self._validate_template_path()

    def _browse_model_file(self) -> None:
        """Browse for OpenSim model file."""
        file = filedialog.askopenfilename(
            title="Select OpenSim Model File",
            filetypes=[("OpenSim Models", "*.osim"), ("All Files", "*.*")]
        )
        if file:
            self.model_path_var.set(file)
            self._validate_model_path()

    def _validate_template_path(self) -> None:
        """Validate template folder path."""
        path = self.template_path_var.get()
        if not path:
            self.template_status.configure(text="⚠️ Not set", text_color="#ffc107")
            return

        if Path(path).exists() and Path(path).is_dir():
            self.template_status.configure(text="✅ Found", text_color="#28a745")
        else:
            self.template_status.configure(text="❌ Not found", text_color="#dc3545")

    def _validate_model_path(self) -> None:
        """Validate model file path."""
        path = self.model_path_var.get()
        if not path:
            self.model_status.configure(text="⚠️ Not set", text_color="#ffc107")
            return

        if Path(path).exists() and Path(path).is_file():
            self.model_status.configure(text="✅ Found", text_color="#28a745")
        else:
            self.model_status.configure(text="❌ Not found", text_color="#dc3545")

    def _update_trial_settings(self) -> None:
        """Update trial_settings.xml files with new model and template paths."""
        if not self.current_session:
            self.status_callback("No session loaded", "error")
            return

        template_path = self.template_path_var.get()
        model_path = self.model_path_var.get()

        if not template_path and not model_path:
            self.status_callback("Please set at least template folder or model path", "warning")
            return

        # Validate paths
        if template_path and not Path(template_path).exists():
            self.status_callback("Template folder not found", "error")
            return

        if model_path and not Path(model_path).exists():
            self.status_callback("Model file not found", "error")
            return

        # Run update in background thread
        import threading
        thread = threading.Thread(
            target=self._update_trial_settings_thread,
            args=(template_path, model_path),
            daemon=True
        )
        thread.start()

    def _update_trial_settings_thread(self, template_path: str, model_path: str) -> None:
        """Update trial settings in background thread."""
        try:
            import xml.etree.ElementTree as ET

            if not self.session_manager:
                self.status_callback("Session manager not initialized", "error")
                return

            trial_list = self.session_manager.get_trial_list()
            success_count = 0
            failed_count = 0

            for trial_info in trial_list:
                trial_name = trial_info['name']
                trial_path = self.session_manager.get_trial_by_name(trial_name)

                if not trial_path:
                    failed_count += 1
                    continue

                try:
                    settings_file = trial_path / "trial_settings.xml"

                    if not settings_file.exists():
                        # Create new trial_settings.xml
                        root = ET.Element("trial_settings")
                    else:
                        # Parse existing file
                        tree = ET.parse(str(settings_file))
                        root = tree.getroot()

                    # Update template path (use relative path from trial folder)
                    if template_path:
                        try:
                            # Use os.path.relpath for more robust relative path conversion
                            rel_template = os.path.relpath(str(template_path), str(trial_path)).replace('\\', '/')
                        except (ValueError, TypeError):
                            # If relative path not possible, use absolute (normalize separators)
                            rel_template = str(template_path).replace('\\', '/')

                        # Update setup_dir (Inputs class attribute)
                        setup_dir_elem = root.find('setup_dir')
                        if setup_dir_elem is None:
                            setup_dir_elem = ET.SubElement(root, 'setup_dir')
                        setup_dir_elem.text = rel_template

                    # Update model path (use relative path from trial folder)
                    if model_path:
                        try:
                            # Use os.path.relpath for more robust relative path conversion
                            rel_model = os.path.relpath(str(model_path), str(trial_path)).replace('\\', '/')
                        except (ValueError, TypeError):
                            # If relative path not possible, use absolute (normalize separators)
                            rel_model = str(model_path).replace('\\', '/')

                        # Update model_dir (Inputs class attribute)
                        model_dir_elem = root.find('model_dir')
                        if model_dir_elem is None:
                            model_dir_elem = ET.SubElement(root, 'model_dir')
                        model_dir_elem.text = rel_model

                    # Update time range from events.csv if it exists
                    events_file = trial_path / "events.csv"
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

                            # Update start_time and end_time elements if we found valid times
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

                                # Note: time_range is managed by the C3D export pipeline
                                logger.info(f"Updated start_time and end_time for {trial_name}: {start_time:.4f} - {end_time:.4f}")

                        except Exception as e:
                            logger.warning(f"Could not update time range from events.csv for {trial_name}: {e}")

                    # Write updated XML with proper formatting
                    tree = ET.ElementTree(root)
                    save_pretty_xml(tree, str(settings_file), encoding='utf-8', xml_declaration=True)

                    success_count += 1
                    self.status_callback(f"Updated {trial_name}", "success")
                    logger.info(f"Updated trial settings for {trial_name}")

                except Exception as e:
                    failed_count += 1
                    self.status_callback(f"Failed to update {trial_name}: {str(e)[:40]}", "error")
                    logger.error(f"Error updating trial settings for {trial_name}: {e}")

            # Final summary
            total = len(trial_list)
            if failed_count == 0:
                self.status_callback(f"[OK] Updated all {success_count} trials successfully", "success")
            else:
                self.status_callback(
                    f"[WARN] Updated {success_count}/{total} trials ({failed_count} failed)",
                    "warning" if success_count > 0 else "error"
                )

        except Exception as e:
            self.status_callback(f"Error updating trial settings: {str(e)[:50]}", "error")
            logger.error(f"Trial settings update error: {e}", exc_info=True)

    def _string_to_step(self, step_name: str) -> AnalysisStep:
        """Convert step name string to AnalysisStep enum."""
        for step in AnalysisStep:
            if step.value == step_name:
                return step
        raise ValueError(f"Unknown step: {step_name}")
