"""Batch Processor Tab - Process multiple trials."""

import customtkinter as ctk
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.config_manager import ConfigManager


class BatchProcessorTab(ctk.CTkFrame):
    """Tab for batch processing multiple trials."""

    def __init__(self, parent, config_manager: ConfigManager, status_callback):
        """Initialize Batch Processor Tab."""
        super().__init__(parent)
        self.config_manager = config_manager
        self.status_callback = status_callback

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create UI widgets."""
        # Title
        title = ctk.CTkLabel(self, text="Batch Processor", font=("Segoe UI", 16, "bold"))
        title.pack(padx=20, pady=20, anchor="w")

        # Info text
        info = ctk.CTkLabel(
            self,
            text="Configure and run batch processing for multiple trials.\n"
                 "• Auto-discovery: Automatically find all trials\n"
                 "• Sequential/Parallel: Choose execution mode\n"
                 "• Progress tracking: Monitor all tasks in real-time",
            justify="left",
            font=("Segoe UI", 11)
        )
        info.pack(padx=20, pady=10, anchor="w")

        # Options frame
        options_frame = ctk.CTkFrame(self, corner_radius=8)
        options_frame.pack(padx=20, pady=20, fill="both")

        # Auto-discovery
        auto_discover_label = ctk.CTkLabel(options_frame, text="Auto-Discovery", font=("Segoe UI", 11, "bold"))
        auto_discover_label.pack(padx=15, pady=(15, 5), anchor="w")

        self.auto_discover_var = ctk.BooleanVar(
            value=self.config_manager.get("batch.auto_discover", True)
        )
        ctk.CTkCheckBox(
            options_frame,
            text="Automatically discover trials in simulations directory",
            variable=self.auto_discover_var
        ).pack(padx=30, pady=5, anchor="w")

        # Execution mode
        exec_label = ctk.CTkLabel(options_frame, text="Execution Mode", font=("Segoe UI", 11, "bold"))
        exec_label.pack(padx=15, pady=(15, 5), anchor="w")

        mode_frame = ctk.CTkFrame(options_frame)
        mode_frame.pack(padx=30, pady=5, anchor="w")

        self.mode_var = ctk.StringVar(value=self.config_manager.get("processing.mode", "sequential"))

        ctk.CTkRadioButton(
            mode_frame,
            text="Sequential (one at a time)",
            variable=self.mode_var,
            value="sequential"
        ).pack(anchor="w", pady=5)

        ctk.CTkRadioButton(
            mode_frame,
            text="Parallel (multiple workers)",
            variable=self.mode_var,
            value="parallel"
        ).pack(anchor="w", pady=5)

        # Workers
        workers_label = ctk.CTkLabel(options_frame, text="Max Workers", font=("Segoe UI", 10))
        workers_label.pack(padx=30, pady=(10, 2), anchor="w")

        workers_frame = ctk.CTkFrame(options_frame)
        workers_frame.pack(padx=30, pady=5, anchor="w")

        self.workers_var = ctk.IntVar(value=self.config_manager.get("processing.max_workers", 4))
        workers_spinbox = ctk.CTkOptionMenu(
            workers_frame,
            variable=self.workers_var,
            values=["1", "2", "4", "8"]
        )
        workers_spinbox.pack(side="left", padx=(0, 10))

        # Action buttons
        button_frame = ctk.CTkFrame(self)
        button_frame.pack(padx=20, pady=20, fill="x")

        ctk.CTkButton(
            button_frame,
            text="Start Batch Processing",
            fg_color="#28a745",
            hover_color="#218838",
            command=self._start_batch
        ).pack(side="left", padx=5, fill="x", expand=True)

        ctk.CTkButton(
            button_frame,
            text="Pause",
            command=self._pause_batch
        ).pack(side="left", padx=5, fill="x", expand=True)

        ctk.CTkButton(
            button_frame,
            text="Cancel",
            fg_color="#dc3545",
            hover_color="#c82333",
            command=self._cancel_batch
        ).pack(side="left", padx=5, fill="x", expand=True)

    def _start_batch(self) -> None:
        """Start batch processing."""
        self.status_callback("Batch processing started", "info")

    def _pause_batch(self) -> None:
        """Pause batch processing."""
        self.status_callback("Batch processing paused", "warning")

    def _cancel_batch(self) -> None:
        """Cancel batch processing."""
        self.status_callback("Batch processing cancelled", "error")
