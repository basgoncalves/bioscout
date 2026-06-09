"""
Session-Level CEINMS Calibration Tab - Multi-trial selection with status indicators.
Version: 1.1.0
"""

import customtkinter as ctk
from pathlib import Path
import sys
import threading
from tkinter import filedialog, messagebox
import os

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.config_manager import ConfigManager
from core.session_manager import SessionManager, TrialValidator
from utils.logger import logger
from utils import SIMULATIONS_DIR


class CEINMSCalibrationSessionTab(ctk.CTkFrame):
    """Session-level CEINMS Calibration tab with trial selection."""

    VERSION = "1.1.0"

    def __init__(self, parent, config_manager: ConfigManager, status_callback):
        """Initialize CEINMS Calibration Session Tab."""
        super().__init__(parent)
        self.config_manager = config_manager
        self.status_callback = status_callback
        self.session_manager = None
        self.current_session = None

        # State
        self.trial_vars = {}
        self.trial_info = {}

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create UI widgets."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # TOP SECTION: Session Selection
        top_frame = ctk.CTkFrame(self)
        top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        top_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top_frame, text="CEINMS Calibration - Select Session & Trials", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 10)
        )

        ctk.CTkLabel(top_frame, text="Session Directory:", font=("Segoe UI", 10)).grid(
            row=1, column=0, sticky="w", padx=(0, 5)
        )

        self.session_var = ctk.StringVar(value="Select session...")
        self.session_entry = ctk.CTkEntry(
            top_frame,
            textvariable=self.session_var,
            placeholder_text="Browse or paste session path"
        )
        self.session_entry.grid(row=1, column=1, sticky="ew", padx=(0, 10))
        self.session_entry.bind("<Return>", lambda e: self._load_session_from_entry())

        ctk.CTkButton(top_frame, text="Browse", width=80, command=self._browse_session).grid(
            row=1, column=2, sticky="w", padx=(0, 5)
        )

        ctk.CTkButton(top_frame, text="Load", width=50, command=self._load_session_from_entry).grid(
            row=1, column=3, sticky="w"
        )

        # MIDDLE SECTION: Trial List with Status
        middle_frame = ctk.CTkFrame(self)
        middle_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        middle_frame.grid_rowconfigure(1, weight=1)
        middle_frame.grid_columnconfigure(0, weight=1)

        # Instructions
        ctk.CTkLabel(
            middle_frame,
            text="Trials ready for calibration are marked in GREEN. Missing inputs are marked in RED.",
            font=("Segoe UI", 9),
            text_color="#888888"
        ).grid(row=0, column=0, sticky="w", pady=(0, 5))

        # Trial list frame
        self.trials_frame = ctk.CTkScrollableFrame(middle_frame)
        self.trials_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=5)

        # Trial selection controls
        ctrl_frame = ctk.CTkFrame(middle_frame)
        ctrl_frame.grid(row=2, column=0, sticky="ew", padx=0, pady=(10, 0))

        ctk.CTkButton(ctrl_frame, text="Select All Ready Trials", height=28, command=self._select_ready_trials).pack(fill="x", pady=(0, 3))
        ctk.CTkButton(ctrl_frame, text="Select All", height=28, command=self._select_all_trials).pack(fill="x", pady=(0, 3))
        ctk.CTkButton(ctrl_frame, text="Deselect All", height=28, command=self._deselect_all_trials).pack(fill="x")

        # BOTTOM SECTION: CEINMS Settings & Controls
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

        self.calibrate_btn = ctk.CTkButton(
            button_frame,
            text="▶ Run CEINMS Calibration",
            fg_color="#28a745",
            hover_color="#218838",
            font=("Segoe UI", 11, "bold"),
            height=40,
            command=self._run_calibration
        )
        self.calibrate_btn.pack(side="left", padx=5, expand=True, fill="both")

        self.stop_btn = ctk.CTkButton(
            button_frame,
            text="⏹ Stop",
            fg_color="#dc3545",
            hover_color="#c82333",
            font=("Segoe UI", 11),
            height=40,
            command=self._stop_calibration,
            state="disabled"
        )
        self.stop_btn.pack(side="left", padx=5, expand=True, fill="both")

    def _browse_session(self) -> None:
        """Browse for session directory."""
        path = filedialog.askdirectory(title="Select Session Directory")
        if path:
            self._load_session(path)

    def _load_session_from_entry(self) -> None:
        """Load session from entry field."""
        session_str = self.session_var.get().strip()
        if not session_str or session_str == "Select session...":
            self.status_callback("⚠ Please enter a valid session path", "warning")
            return

        session_str = session_str.replace("/", "\\").strip('"').strip("'")
        session_path = Path(session_str)

        if not session_path.exists():
            self.status_callback(f"✗ Path does not exist: {session_str}", "error")
            messagebox.showerror("Error", f"Path not found:\n{session_str}")
            return

        if not session_path.is_dir():
            self.status_callback("✗ Path is not a directory", "error")
            return

        self._load_session(str(session_path))

    def _load_session(self, session_path: str) -> None:
        """Load session and discover trials."""
        try:
            self.current_session = Path(session_path)
            self.session_manager = SessionManager(session_path)

            # Discover trials
            trials = self.session_manager.discover_trials()
            if not trials:
                self.status_callback("No valid trials found in session", "warning")
                messagebox.showwarning("Warning", "No valid trials found in session")
                return

            # Update UI
            self.session_var.set(session_path)
            self._populate_trial_list()
            self.status_callback(f"✓ Session loaded: {self.current_session.name} ({len(trials)} trials)", "success")
            logger.info(f"CEINMS Calibration session loaded: {session_path}")

        except Exception as e:
            self.status_callback(f"✗ Failed to load session: {e}", "error")
            logger.error(f"Session load error: {e}")

    def _populate_trial_list(self) -> None:
        """Populate trial list with CEINMS readiness indicators."""
        # Clear existing widgets
        for widget in self.trials_frame.winfo_children():
            widget.destroy()
        self.trial_vars = {}
        self.trial_info = {}

        if not self.session_manager:
            return

        trial_list = self.session_manager.get_trial_list()

        for trial_info in trial_list:
            trial_name = trial_info['name']
            is_ready = trial_info['ceinms_complete']

            # Create trial frame
            frame = ctk.CTkFrame(self.trials_frame)
            frame.pack(fill="x", pady=3, padx=5)

            # Checkbox
            var = ctk.BooleanVar(value=False)
            checkbox = ctk.CTkCheckBox(
                frame,
                text=trial_name,
                variable=var,
                onvalue=True,
                offvalue=False,
                font=("Segoe UI", 10)
            )
            checkbox.pack(side="left", padx=5, fill="x", expand=True)
            self.trial_vars[trial_name] = var
            self.trial_info[trial_name] = trial_info

            # Status indicator
            if is_ready:
                status_color = "#28a745"  # Green
                status_text = "✓ Ready"
                checkbox.configure(state="normal")
            else:
                status_color = "#dc3545"  # Red
                status_text = "✗ Missing Files"
                checkbox.configure(state="disabled")

            status_label = ctk.CTkLabel(
                frame,
                text=status_text,
                text_color=status_color,
                font=("Segoe UI", 10, "bold"),
                width=150
            )
            status_label.pack(side="right", padx=5)

            # Show missing files on hover
            def show_missing(trial_name=trial_name):
                info = self.trial_info.get(trial_name, {})
                missing = [k for k, v in info.get('ceinms_files', {}).items() if not v]
                if missing:
                    messagebox.showinfo(
                        "Missing Files",
                        f"Trial '{trial_name}' is missing:\n" + "\n".join(missing)
                    )

            # Right-click for more info
            frame.bind("<Button-3>", lambda e, tn=trial_name: show_missing(tn))

    def _select_ready_trials(self) -> None:
        """Select only trials that are ready for CEINMS calibration."""
        for trial_name, var in self.trial_vars.items():
            info = self.trial_info.get(trial_name, {})
            if info.get('ceinms_complete', False):
                var.set(True)
            else:
                var.set(False)

    def _select_all_trials(self) -> None:
        """Select all trials (including those not ready)."""
        for var in self.trial_vars.values():
            var.set(True)

    def _deselect_all_trials(self) -> None:
        """Deselect all trials."""
        for var in self.trial_vars.values():
            var.set(False)

    def _run_calibration(self) -> None:
        """Run CEINMS calibration on selected trials."""
        if not self.current_session:
            self.status_callback("No session loaded", "error")
            return

        # Get selected trials
        selected = [name for name, var in self.trial_vars.items() if var.get()]
        if not selected:
            self.status_callback("No trials selected", "warning")
            return

        # Validate selected trials
        invalid = []
        for trial_name in selected:
            info = self.trial_info.get(trial_name, {})
            if not info.get('ceinms_complete', False):
                invalid.append(trial_name)

        if invalid:
            response = messagebox.askyesno(
                "Warning",
                f"Some selected trials are missing required inputs:\n" +
                "\n".join(invalid) + "\n\nContinue anyway?"
            )
            if not response:
                return

        # Disable buttons
        self.calibrate_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")

        # Run calibration in background thread
        calibration_thread = threading.Thread(
            target=self._run_calibration_thread,
            args=(selected,),
            daemon=True
        )
        calibration_thread.start()
        self.status_callback("CEINMS calibration running...", "info")

    def _run_calibration_thread(self, selected_trials: list) -> None:
        """Run CEINMS calibration in background thread."""
        # TODO: Implement actual CEINMS calibration logic
        # This is a placeholder for the actual calibration process

        successful = 0
        failed = 0

        for trial_name in selected_trials:
            try:
                self.status_callback(f"Calibrating {trial_name}...", "info")
                trial_path = self.session_manager.get_trial_by_name(trial_name)

                # TODO: Call actual CEINMS calibration function
                # For now, just simulate completion
                successful += 1
                self.status_callback(f"✓ {trial_name} calibration complete", "success")

            except Exception as e:
                failed += 1
                self.status_callback(f"✗ {trial_name} calibration failed: {e}", "error")
                logger.error(f"Calibration error for {trial_name}: {e}")

        # Final status
        total = len(selected_trials)
        if failed == 0:
            self.status_callback(f"✓ Calibration complete - All {successful} trials processed", "success")
        else:
            self.status_callback(f"⚠ Calibration complete ({successful}/{total} successful)", "warning")

  