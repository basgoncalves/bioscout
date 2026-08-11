"""Configuration Tab - Manage application settings."""

import customtkinter as ctk
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.config_manager import ConfigManager
from settings import RecordingSettings


class ConfigurationTab(ctk.CTkFrame):
    """Tab for managing application configuration."""

    def __init__(self, parent, config_manager: ConfigManager, status_callback):
        """Initialize Configuration Tab."""
        super().__init__(parent)
        self.config_manager = config_manager
        self.status_callback = status_callback

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create UI widgets."""
        # Title
        title = ctk.CTkLabel(self, text="Configuration", font=("Segoe UI", 16, "bold"))
        title.pack(padx=20, pady=20, anchor="w")

        # Main container with scrollable frame
        container = ctk.CTkScrollableFrame(self)
        container.pack(padx=20, pady=10, fill="both", expand=True)

        # Section: Project Paths — the ONE setting the app reads.
        self._create_section(container, "Project Paths", self._create_paths_section)

        # Section: what this project actually resolved to (read-only).
        self._create_section(container, "Resolved for this project",
                             self._create_resolved_section)

        # REMOVED (2.0.0b12): Analysis Pipeline, CEINMS Parameters, Processing
        # Options, GUI Settings, Recording Settings. Every key in them was read
        # by nothing outside this file — leftovers from the settings.xml era.
        # Stage flags are now arguments to Iteration.run(); alpha/beta/gamma
        # live per session in session.yaml. The old checkboxes looked
        # authoritative and did nothing, which is the worst kind of control.
        # The section builders are kept below, unused, so the history is
        # readable and re-wiring one is a two-line change.

        # Buttons
        button_frame = ctk.CTkFrame(self)
        button_frame.pack(padx=20, pady=20, fill="x")

        ctk.CTkButton(
            button_frame,
            text="Save Configuration",
            fg_color="#28a745",
            hover_color="#218838",
            command=self._save_config
        ).pack(side="left", padx=5, fill="x", expand=True)

        ctk.CTkButton(
            button_frame,
            text="Reset to Defaults",
            fg_color="#ffc107",
            hover_color="#e0a800",
            command=self._reset_defaults
        ).pack(side="left", padx=5, fill="x", expand=True)

        ctk.CTkButton(
            button_frame,
            text="Load Configuration",
            command=self._load_config
        ).pack(side="left", padx=5, fill="x", expand=True)

    def _create_section(self, parent, title: str, creator_func) -> None:
        """Create a configuration section."""
        section_frame = ctk.CTkFrame(parent, corner_radius=8)
        section_frame.pack(fill="x", pady=10)

        # Section title
        title_label = ctk.CTkLabel(section_frame, text=title, font=("Segoe UI", 12, "bold"))
        title_label.pack(padx=15, pady=(15, 10), anchor="w")

        # Content frame
        content_frame = ctk.CTkFrame(section_frame)
        content_frame.pack(padx=15, pady=(0, 15), fill="x")

        # Call creator function to populate section
        creator_func(content_frame)

    def _create_paths_section(self, parent) -> None:
        """Create project paths section."""
        # The folder holding <subject>/<session>. Leave blank to take it from
        # the project's settings.py (SIMULATIONS_DIR), which is where a project
        # states it already. Set it to work on a side tree such as
        # simulations_test/ without editing settings.py.
        self._add_path_entry(parent, "Simulations Directory",
                             "project.simulations_dir", "")
        _hint = ctk.CTkLabel(
            parent,
            text=("blank = read SIMULATIONS_DIR from the project's settings.py; "
                  "a name that does not exist is ignored"),
            font=("Segoe UI", 9), text_color="#888888", wraplength=560,
            justify="left")
        _hint.grid(row=parent.grid_size()[1], column=0, columnspan=2,
                   sticky="w", pady=(0, 6))

    def _create_resolved_section(self, parent) -> None:
        """Show what the app resolved, rather than what someone typed.

        The Simulations Directory field said "simulations2" for a project with
        no such folder, and nothing on screen said it was being ignored. This
        row shows the path actually in use.
        """
        try:
            from .. import simulations_root as _sim_root
        except Exception:                                          # noqa: BLE001
            _sim_root = None

        proj = getattr(self, "_project_root", None)
        if proj is None:
            proj = self.config_manager.get("project.root", None)

        rows = []
        if proj and _sim_root is not None:
            try:
                _p = _sim_root(proj, self.config_manager)
                rows.append(("sessions read from", str(_p)))
                if _p is not None and not _p.is_dir():
                    rows.append(("", "that folder does not exist"))
                else:
                    try:
                        subs = sorted(d.name for d in _p.iterdir() if d.is_dir())
                        rows.append(("subjects found",
                                     ", ".join(subs) if subs else "(none)"))
                    except Exception:                              # noqa: BLE001
                        pass
            except Exception as _e:                                # noqa: BLE001
                rows.append(("could not resolve", str(_e)))
        else:
            rows.append(("", "load a project to see what it resolves to"))

        for i, (label, value) in enumerate(rows):
            ctk.CTkLabel(parent, text=(f"{label}:" if label else ""),
                         font=("Segoe UI", 10)).grid(row=i, column=0,
                                                     sticky="w", pady=3)
            ctk.CTkLabel(parent, text=value, font=("Consolas", 10),
                         text_color="#9ecbff", wraplength=760,
                         justify="left").grid(row=i, column=1, sticky="w",
                                              padx=(10, 0), pady=3)

    def _create_analysis_section(self, parent) -> None:
        """Create analysis pipeline section."""
        self._add_checkbox(parent, "Reset Settings XML", "analysis.reset_settings_xml")
        self._add_checkbox(parent, "Replace Existing", "analysis.replace_existing")
        self._add_checkbox(parent, "Inverse Kinematics", "analysis.inverse_kinematics")
        self._add_checkbox(parent, "Inverse Dynamics", "analysis.inverse_dynamics")
        self._add_checkbox(parent, "Muscle Analysis", "analysis.muscle_analysis")
        self._add_checkbox(parent, "Static Optimization", "analysis.static_optimization")
        self._add_checkbox(parent, "Joint Reaction Analysis", "analysis.joint_reaction_analysis")

    def _create_ceinms_section(self, parent) -> None:
        """Create CEINMS parameters section."""
        self._add_number_entry(parent, "Alpha", "ceinms.alpha", 10)
        self._add_number_entry(parent, "Beta", "ceinms.beta", 1)
        self._add_number_entry(parent, "Gamma", "ceinms.gamma", 1000)

    def _create_processing_section(self, parent) -> None:
        """Create processing options section."""
        # Mode
        mode_label = ctk.CTkLabel(parent, text="Execution Mode:", font=("Segoe UI", 10))
        mode_label.grid(row=0, column=0, sticky="w", pady=5)

        mode_var = ctk.StringVar(value=self.config_manager.get("processing.mode", "sequential"))
        mode_menu = ctk.CTkOptionMenu(
            parent,
            variable=mode_var,
            values=["sequential", "parallel"],
            command=lambda v: self.config_manager.set("processing.mode", v)
        )
        mode_menu.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=5)

        # Max workers
        self._add_number_entry(parent, "Max Workers", "processing.max_workers", 4, row=1)

        self._add_checkbox(parent, "Push to Git", "processing.push_subject_to_git", row=2)

    def _create_gui_section(self, parent) -> None:
        """Create GUI settings section."""
        # Theme
        theme_label = ctk.CTkLabel(parent, text="Theme:", font=("Segoe UI", 10))
        theme_label.grid(row=0, column=0, sticky="w", pady=5)

        theme_var = ctk.StringVar(value=self.config_manager.get("gui.theme", "dark"))
        theme_menu = ctk.CTkOptionMenu(
            parent,
            variable=theme_var,
            values=["dark", "light"],
            command=lambda v: self.config_manager.set("gui.theme", v)
        )
        theme_menu.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=5)

        self._add_checkbox(parent, "Auto-save Configuration", "gui.auto_save_config", row=1)
        self._add_checkbox(parent, "Verbose Logging", "gui.verbose_logging", row=2)

    def _create_recording_section(self, parent) -> None:
        """Create recording settings section."""
        row = 0

        # Output Directory Template
        label_widget = ctk.CTkLabel(parent, text="Output Directory Template:", font=("Segoe UI", 10))
        label_widget.grid(row=row, column=0, sticky="w", pady=5)

        output_dir_var = ctk.StringVar(value=RecordingSettings.OUTPUT_DIR_TEMPLATE)
        entry = ctk.CTkEntry(
            parent,
            textvariable=output_dir_var
        )
        entry.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=5)

        def update_output_dir(v):
            RecordingSettings.OUTPUT_DIR_TEMPLATE = output_dir_var.get()

        entry.bind("<FocusOut>", lambda e: update_output_dir(output_dir_var.get()))

        # Default Duration
        row += 1
        label_widget = ctk.CTkLabel(parent, text="Default Duration (seconds):", font=("Segoe UI", 10))
        label_widget.grid(row=row, column=0, sticky="w", pady=5)

        duration_var = ctk.StringVar(value=str(RecordingSettings.DEFAULT_DURATION_SECONDS))
        entry = ctk.CTkEntry(
            parent,
            textvariable=duration_var,
            width=100
        )
        entry.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=5)

        def update_duration(v):
            try:
                RecordingSettings.DEFAULT_DURATION_SECONDS = int(duration_var.get())
            except ValueError:
                pass

        entry.bind("<FocusOut>", lambda e: update_duration(duration_var.get()))

        # Default Video Source
        row += 1
        label_widget = ctk.CTkLabel(parent, text="Default Video Source:", font=("Segoe UI", 10))
        label_widget.grid(row=row, column=0, sticky="w", pady=5)

        video_source_var = ctk.StringVar(value=RecordingSettings.DEFAULT_VIDEO_SOURCE)
        source_menu = ctk.CTkOptionMenu(
            parent,
            variable=video_source_var,
            values=["webcam", "ip"],
            command=lambda v: setattr(RecordingSettings, 'DEFAULT_VIDEO_SOURCE', v)
        )
        source_menu.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=5)

        # IP Camera Address
        row += 1
        label_widget = ctk.CTkLabel(parent, text="IP Camera Address:", font=("Segoe UI", 10))
        label_widget.grid(row=row, column=0, sticky="w", pady=5)

        ip_camera_var = ctk.StringVar(value=RecordingSettings.IP_CAMERA_ADDRESS)
        entry = ctk.CTkEntry(
            parent,
            textvariable=ip_camera_var
        )
        entry.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=5)

        def update_ip_camera(v):
            RecordingSettings.IP_CAMERA_ADDRESS = ip_camera_var.get()

        entry.bind("<FocusOut>", lambda e: update_ip_camera(ip_camera_var.get()))

        # Default OpenSim Model
        row += 1
        label_widget = ctk.CTkLabel(parent, text="Default OpenSim Model:", font=("Segoe UI", 10))
        label_widget.grid(row=row, column=0, sticky="w", pady=5)

        # Import available models
        from record.video import AVAILABLE_MODELS
        available_models = list(AVAILABLE_MODELS.keys()) if AVAILABLE_MODELS else ["arm26_ball"]

        model_var = ctk.StringVar(value=RecordingSettings.DEFAULT_OSIM_MODEL)
        model_menu = ctk.CTkOptionMenu(
            parent,
            variable=model_var,
            values=available_models,
            command=lambda v: setattr(RecordingSettings, 'DEFAULT_OSIM_MODEL', v)
        )
        model_menu.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=5)

    def _add_checkbox(self, parent, label: str, key: str, row: int = None) -> None:
        """Add checkbox configuration entry."""
        if row is None:
            row = parent.grid_size()[1]

        value = self.config_manager.get(key, False)
        var = ctk.BooleanVar(value=value)

        def on_change(v):
            self.config_manager.set(key, v)

        checkbox = ctk.CTkCheckBox(
            parent,
            text=label,
            variable=var,
            command=lambda: on_change(var.get())
        )
        checkbox.grid(row=row, column=0, columnspan=2, sticky="w", pady=5)

    def _add_number_entry(self, parent, label: str, key: str, default: int, row: int = None) -> None:
        """Add number entry configuration field."""
        if row is None:
            row = parent.grid_size()[1]

        label_widget = ctk.CTkLabel(parent, text=f"{label}:", font=("Segoe UI", 10))
        label_widget.grid(row=row, column=0, sticky="w", pady=5)

        value = self.config_manager.get(key, default)
        var = ctk.StringVar(value=str(value))

        def on_change(v):
            try:
                self.config_manager.set(key, int(v))
            except ValueError:
                pass

        entry = ctk.CTkEntry(
            parent,
            textvariable=var,
            width=100
        )
        entry.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=5)
        entry.bind("<FocusOut>", lambda e: on_change(var.get()))

    def _add_path_entry(self, parent, label: str, key: str, default: str) -> None:
        """Add path entry configuration field."""
        row = parent.grid_size()[1]

        label_widget = ctk.CTkLabel(parent, text=f"{label}:", font=("Segoe UI", 10))
        label_widget.grid(row=row, column=0, sticky="w", pady=5)

        value = self.config_manager.get(key, default)
        var = ctk.StringVar(value=str(value))

        entry = ctk.CTkEntry(
            parent,
            textvariable=var
        )
        entry.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=5)
        entry.bind("<FocusOut>", lambda e: self.config_manager.set(key, var.get()))

    def _save_config(self) -> None:
        """Save configuration."""
        try:
            self.config_manager.save()
            self.status_callback("Configuration saved", "success")
        except Exception as e:
            self.status_callback(f"Failed to save configuration: {e}", "error")

    def _load_config(self) -> None:
        """Load configuration."""
        self.status_callback("Loading configuration...", "info")

    def _reset_defaults(self) -> None:
        """Reset to default configuration."""
        self.config_manager.reset_to_defaults()
        self.status_callback("Configuration reset to defaults", "warning")
