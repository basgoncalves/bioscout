"""Logs Tab - View application logs."""

import customtkinter as ctk
from pathlib import Path
import sys
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.config_manager import ConfigManager
from utils.logger import logger


class LogsTab(ctk.CTkFrame):
    """Tab for viewing application logs."""

    def __init__(self, parent, config_manager: ConfigManager, status_callback):
        """Initialize Logs Tab."""
        super().__init__(parent)
        self.config_manager = config_manager
        self.status_callback = status_callback

        self._create_widgets()
        self._load_logs()

    def _create_widgets(self) -> None:
        """Create UI widgets."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Title
        title = ctk.CTkLabel(self, text="Application Logs", font=("Segoe UI", 16, "bold"))
        title.grid(row=0, column=0, padx=20, pady=20, sticky="ew")

        # Control frame
        control_frame = ctk.CTkFrame(self)
        control_frame.grid(row=0, column=1, padx=20, pady=20, sticky="ew")

        ctk.CTkButton(
            control_frame,
            text="Refresh",
            command=self._load_logs
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            control_frame,
            text="Clear",
            fg_color="#ffc107",
            hover_color="#e0a800",
            command=self._clear_logs
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            control_frame,
            text="Open Log Folder",
            command=self._open_log_folder
        ).pack(side="left", padx=5)

        # Log display
        self.log_text = ctk.CTkTextbox(self, wrap="word")
        self.log_text.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=20, pady=(0, 20))

        # Status bar
        status_frame = ctk.CTkFrame(self)
        status_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 20))

        self.status_label = ctk.CTkLabel(status_frame, text="", text_color="#b0b0b0", font=("Segoe UI", 9))
        self.status_label.pack(anchor="w")

    def _load_logs(self) -> None:
        """Load and display logs."""
        try:
            log_file = logger.get_log_file()
            if Path(log_file).exists():
                with open(log_file, 'r') as f:
                    content = f.read()
                    self.log_text.delete("1.0", "end")
                    self.log_text.insert("1.0", content)
                    self.log_text.see("end")

                self.status_label.configure(
                    text=f"Current log: {Path(log_file).name} ({len(content)} characters)"
                )
            else:
                self.log_text.insert("1.0", "No log file found")
                self.status_label.configure(text="No log file available")

        except Exception as e:
            self.log_text.delete("1.0", "end")
            self.log_text.insert("1.0", f"Error loading logs: {str(e)}")
            self.status_callback(f"Error loading logs: {e}", "error")

    def _clear_logs(self) -> None:
        """Clear log display."""
        self.log_text.delete("1.0", "end")
        self.status_label.configure(text="Log cleared")

    def _open_log_folder(self) -> None:
        """Open log folder in file explorer."""
        try:
            log_dir = Path.home() / ".powerlifting_app" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)

            import platform
            import subprocess

            if platform.system() == "Windows":
                subprocess.Popen(['explorer', str(log_dir)])
            elif platform.system() == "Darwin":  # macOS
                subprocess.Popen(['open', str(log_dir)])
            else:  # Linux
                subprocess.Popen(['xdg-open', str(log_dir)])

            self.status_callback("Log folder opened", "success")
        except Exception as e:
            self.status_callback(f"Could not open log folder: {e}", "error")
