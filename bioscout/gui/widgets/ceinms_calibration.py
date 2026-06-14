"""CEINMS Calibration settings widget."""

import customtkinter as ctk
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.config_manager import ConfigManager
from utils.logger import logger


class CEINMSCalibrationTab(ctk.CTkFrame):
    """Tab for CEINMS calibration settings."""

    def __init__(self, parent, config_manager: ConfigManager, status_callback):
        """Initialize CEINMS Calibration Tab."""
        super().__init__(parent)
        self.config_manager = config_manager
        self.status_callback = status_callback
        self.settings = {}

        self._create_widgets()
        self._load_settings()

    def _create_widgets(self) -> None:
        """Create UI widgets."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header,
            text="CEINMS Calibration Settings",
            font=("Segoe UI", 14, "bold")
        ).pack(side="left", padx=5)

        # Main content
        content = ctk.CTkScrollableFrame(self)
        content.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        content.grid_columnconfigure(0, weight=1)

        # Calibration Trials Section
        trials_frame = self._create_section(content, "Calibration Trials")
        trials_frame.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(trials_frame, text="Trials to use for calibration (comma-separated):",
                     font=("Segoe UI", 10)).pack(anchor="w", pady=(10, 5))

        self.calibration_trials = ctk.CTkTextbox(trials_frame, height=60)
        self.calibration_trials.pack(fill="both", expand=True, pady=(0, 10))

        # Model Parameters Section
        model_frame = self._create_section(content, "Model Parameters")
        model_frame.pack(fill="x", padx=5, pady=5)

        self.model_params = {}
        params = [
            ("Model file", "model_file", "path"),
            ("Muscle set file", "muscle_set_file", "path"),
            ("Excitation file", "excitation_file", "path"),
        ]

        for label, key, widget_type in params:
            ctk.CTkLabel(model_frame, text=f"{label}:", font=("Segoe UI", 10)).pack(
                anchor="w", pady=(10, 0)
            )
            entry = ctk.CTkEntry(model_frame, placeholder_text=f"Enter {label}")
            entry.pack(fill="x", pady=(0, 5))
            self.model_params[key] = entry

        # Optimization Parameters Section
        opt_frame = self._create_section(content, "Optimization Parameters")
        opt_frame.pack(fill="x", padx=5, pady=5)

        self.opt_params = {}
        params = [
            ("Number of iterations", "iterations", "100"),
            ("Convergence tolerance", "tolerance", "0.01"),
            ("Optimization method", "method", "Levenberg-Marquardt"),
            ("Max function calls", "max_calls", "5000"),
        ]

        for label, key, default in params:
            ctk.CTkLabel(opt_frame, text=f"{label}:", font=("Segoe UI", 10)).pack(
                anchor="w", pady=(10, 0)
            )
            entry = ctk.CTkEntry(opt_frame, placeholder_text=default)
            entry.insert(0, default)
            entry.pack(fill="x", pady=(0, 5))
            self.opt_params[key] = entry

        # Output Options Section
        output_frame = self._create_section(content, "Output Options")
        output_frame.pack(fill="x", padx=5, pady=5)

        self.output_options = {}
        options = [
            ("Save calibration results", "save_results"),
            ("Generate plots", "generate_plots"),
            ("Save optimization log", "save_log"),
            ("Verbose output", "verbose"),
        ]

        for label, key in options:
            var = ctk.BooleanVar(value=True)
            ctk.CTkCheckBox(
                output_frame,
                text=label,
                variable=var,
                font=("Segoe UI", 10)
            ).pack(anchor="w", pady=5)
            self.output_options[key] = var

        # Advanced Settings Section
        advanced_frame = self._create_section(content, "Advanced Settings")
        advanced_frame.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(advanced_frame, text="Additional XML settings:",
                     font=("Segoe UI", 10)).pack(anchor="w", pady=(10, 5))

        self.advanced_settings = ctk.CTkTextbox(advanced_frame, height=100)
        self.advanced_settings.pack(fill="both", expand=True, pady=(0, 10))
        self.advanced_settings.insert("1.0", "# Add custom XML configuration here\n# Example:\n# <setting name='key'>value</setting>")

        # Bottom buttons
        button_frame = ctk.CTkFrame(self)
        button_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        button_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            button_frame,
            text="Reset to Defaults",
            command=self._reset_defaults,
            fg_color="#555555"
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            button_frame,
            text="Load Settings",
            command=self._load_settings,
            fg_color="#555555"
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            button_frame,
            text="Save Settings",
            command=self._save_settings,
            fg_color="#28a745"
        ).pack(side="right", padx=5)

    def _create_section(self, parent, title: str) -> ctk.CTkFrame:
        """Create a collapsible section frame."""
        main_frame = ctk.CTkFrame(parent, corner_radius=8, fg_color="#2d2d2d")

        # Title
        title_frame = ctk.CTkFrame(main_frame, fg_color="#1f1f1f")
        title_frame.pack(fill="x")

        ctk.CTkLabel(
            title_frame,
            text=title,
            font=("Segoe UI", 11, "bold"),
            text_color="#0084ff"
        ).pack(anchor="w", padx=15, pady=10)

        # Content frame
        content = ctk.CTkFrame(main_frame)
        content.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        return content

    def _load_settings(self) -> None:
        """Load settings from config."""
        try:
            ceinms_config = self.config_manager.get("ceinms", {})

            # Load calibration trials
            trials = ceinms_config.get("calibration_trials", [])
            self.calibration_trials.delete("1.0", "end")
            self.calibration_trials.insert("1.0", ", ".join(trials))

            # Load model parameters
            model = ceinms_config.get("model", {})
            for key, entry in self.model_params.items():
                value = model.get(key, "")
                entry.delete(0, "end")
                entry.insert(0, value)

            # Load optimization parameters
            opt = ceinms_config.get("optimization", {})
            for key, entry in self.opt_params.items():
                value = opt.get(key, entry.cget("placeholder_text") or "")
                entry.delete(0, "end")
                entry.insert(0, str(value))

            # Load output options
            output = ceinms_config.get("output", {})
            for key, var in self.output_options.items():
                var.set(output.get(key, True))

            # Load advanced settings
            advanced = ceinms_config.get("advanced_settings", "")
            self.advanced_settings.delete("1.0", "end")
            self.advanced_settings.insert("1.0", advanced)

            self.status_callback("Settings loaded successfully", "success")
            logger.info("CEINMS settings loaded")

        except Exception as e:
            logger.error(f"Failed to load CEINMS settings: {e}")
            self.status_callback(f"Failed to load settings: {e}", "error")

    def _save_settings(self) -> None:
        """Save settings to config."""
        try:
            ceinms_config = {}

            # Save calibration trials
            trials_text = self.calibration_trials.get("1.0", "end").strip()
            ceinms_config["calibration_trials"] = [t.strip() for t in trials_text.split(",") if t.strip()]

            # Save model parameters
            ceinms_config["model"] = {}
            for key, entry in self.model_params.items():
                ceinms_config["model"][key] = entry.get()

            # Save optimization parameters
            ceinms_config["optimization"] = {}
            for key, entry in self.opt_params.items():
                try:
                    value = float(entry.get())
                except ValueError:
                    value = entry.get()
                ceinms_config["optimization"][key] = value

            # Save output options
            ceinms_config["output"] = {}
            for key, var in self.output_options.items():
                ceinms_config["output"][key] = var.get()

            # Save advanced settings
            ceinms_config["advanced_settings"] = self.advanced_settings.get("1.0", "end").strip()

            # Update config manager
            self.config_manager.set("ceinms", ceinms_config)

            self.status_callback("Settings saved successfully", "success")
            logger.info("CEINMS settings saved")

        except Exception as e:
            logger.error(f"Failed to save CEINMS settings: {e}")
            self.status_callback(f"Failed to save settings: {e}", "error")

    def _reset_defaults(self) -> None:
        """Reset all settings to defaults."""
        self.calibration_trials.delete("1.0", "end")

        for entry in self.model_params.values():
            entry.delete(0, "end")

        defaults = {
            "iterations": "100",
            "tolerance": "0.01",
            "method": "Levenberg-Marquardt",
            "max_calls": "5000"
        }

        for key, entry in self.opt_params.items():
            entry.delete(0, "end")
            entry.insert(0, defaults.get(key, ""))

        for var in self.output_options.values():
            var.set(True)

        self.advanced_settings.delete("1.0", "end")

        self.status_callback("Settings reset to defaults", "info")
        logger.info("CEINMS settings reset to defaults")
