"""Console and Python terminal widget for the application."""

import customtkinter as ctk

from ..gui_settings import register_tk_font
import tkinter as tk
from tkinter import scrolledtext
import sys
import io
from contextlib import redirect_stdout, redirect_stderr
import traceback
from pathlib import Path
import logging

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.logger import logger


class ConsoleHandler(logging.Handler):
    """Custom logging handler that writes to GUI console widget."""

    def __init__(self, console_widget):
        """Initialize handler with console widget reference."""
        super().__init__()
        self.console_widget = console_widget

    def emit(self, record):
        """Emit a log record to the console widget."""
        try:
            msg = self.format(record)

            # Map log level to console message type
            level_map = {
                logging.DEBUG: "info",
                logging.INFO: "info",
                logging.WARNING: "warning",
                logging.ERROR: "error",
                logging.CRITICAL: "error"
            }
            msg_type = level_map.get(record.levelno, "info")

            # Write to console
            self.console_widget.write(msg, msg_type)
        except Exception:
            self.handleError(record)


class StdoutRedirector:
    """Tee stdout/stderr into the console widget AND the real stream.

    It used to only write to the widget. That is fine once the window is up,
    but it is installed DURING ``MainWindow._setup_ui`` — so any exception
    raised by a later tab printed its traceback into a widget belonging to a
    window that never appeared, and the app exited with nothing on the
    terminal but "[main_window] Creating MainWindow...". A startup failure
    must always be readable where the user launched the app, so every write
    goes to both places and the widget half is best-effort.
    """

    def __init__(self, console_widget, stream=None):
        """Initialize redirector with console widget reference.

        ``stream`` is the real stream to keep echoing to; it defaults to the
        interpreter's original stdout so a tee is never chained onto a tee.
        """
        self.console_widget = console_widget
        self.stream = stream if stream is not None else sys.__stdout__
        self.buffer = ""

    def _echo(self, message: str) -> None:
        """Write through to the real stream, never raising."""
        if not message:
            return
        try:
            if self.stream is not None:
                self.stream.write(message)
                self.stream.flush()
        except Exception:                                          # noqa: BLE001
            pass

    def write(self, message: str) -> None:
        """Write message to console widget and to the real stream."""
        if message:
            self._echo(message)
            # Buffer until newline
            self.buffer += message
            if '\n' in self.buffer:
                lines = self.buffer.split('\n')
                for line in lines[:-1]:
                    try:
                        self.console_widget.write(line, "info")
                    except Exception:                              # noqa: BLE001
                        # Widget not built yet, already destroyed, or called
                        # off the Tk thread — the terminal copy still went out.
                        pass
                self.buffer = lines[-1]

    def flush(self) -> None:
        """Flush buffered content."""
        try:
            if self.stream is not None:
                self.stream.flush()
        except Exception:                                          # noqa: BLE001
            pass
        if self.buffer:
            try:
                self.console_widget.write(self.buffer, "info")
            except Exception:                                      # noqa: BLE001
                pass
            self.buffer = ""

    def isatty(self) -> bool:
        """Return False to indicate not a TTY."""
        return False


class ConsoleTerminal(ctk.CTkFrame):
    """Resizable console and Python terminal widget."""

    def __init__(self, parent, height=150):
        """Initialize console terminal."""
        super().__init__(parent)
        self.height = height
        self.output_lines = []
        self.max_lines = 1000  # Keep last 1000 lines

        self._create_widgets()

        # Store original stdout/stderr. If a console was built before (a
        # second ConsoleTerminal, or a reload) sys.stdout is already one of
        # our tees — unwrap it so we never chain a tee onto a dead widget.
        self.original_stdout = getattr(sys.stdout, "stream", None) \
            if isinstance(sys.stdout, StdoutRedirector) else sys.stdout
        self.original_stderr = getattr(sys.stderr, "stream", None) \
            if isinstance(sys.stderr, StdoutRedirector) else sys.stderr
        if self.original_stdout is None:
            self.original_stdout = sys.__stdout__
        if self.original_stderr is None:
            self.original_stderr = sys.__stderr__

        # Tee stdout and stderr into this console. The second argument is the
        # stream to keep echoing to, so the launching terminal still sees
        # everything — without it, a crash during the rest of _setup_ui is
        # completely silent (see StdoutRedirector's docstring).
        sys.stdout = StdoutRedirector(self, self.original_stdout)
        sys.stderr = StdoutRedirector(self, self.original_stderr)

        # Add custom logging handler
        self._setup_logging_handler()

    def _create_widgets(self) -> None:
        """Create UI widgets."""
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 0))
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(header, text="Console Output", font=("Segoe UI", 10, "bold")).pack(
            side="left", padx=5
        )

        ctk.CTkButton(
            header,
            text="Clear",
            width=60,
            height=24,
            command=self._clear_console,
            font=("Segoe UI", 9)
        ).pack(side="right", padx=5)

        # Output text area
        self.output_text = scrolledtext.ScrolledText(
            self,
            height=8,
            bg="#2b2b2b",
            fg="#e0e0e0",
            insertbackground="#e0e0e0",
            wrap=tk.WORD,
            state="disabled"
        )
        # register_tk_font, not font=(): plain tk ignores CTk widget scaling,
        # so the console was the one panel that stayed small when everything
        # else grew, and only caught up after a full app restart.
        register_tk_font(self.output_text, "Courier New", 10)
        self.output_text.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.grid_rowconfigure(1, weight=1)

        # Configure text tags for different message types
        self.output_text.tag_configure("info", foreground="#e0e0e0")
        self.output_text.tag_configure("success", foreground="#28a745")
        self.output_text.tag_configure("warning", foreground="#ffc107")
        self.output_text.tag_configure("error", foreground="#dc3545")
        self.output_text.tag_configure("python", foreground="#00d4ff")

        # Input section
        input_frame = ctk.CTkFrame(self)
        input_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=(0, 5))
        input_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(input_frame, text="Python >>", font=("Courier New", 9)).pack(
            side="left", padx=(0, 5)
        )

        self.input_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Type Python command here...",
            font=("Courier New", 9)
        )
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.input_entry.bind("<Return>", lambda e: self._execute_command())

        ctk.CTkButton(
            input_frame,
            text="Execute",
            width=70,
            height=24,
            command=self._execute_command,
            font=("Segoe UI", 9)
        ).pack(side="left")

    def write(self, message: str, msg_type: str = "info") -> None:
        """
        Write message to console.

        Args:
            message: Message to display
            msg_type: Type of message (info, success, warning, error, python)
        """
        if not message:
            return

        self.output_text.config(state="normal")

        # Add timestamp-like prefix for logging
        if msg_type != "python":
            self.output_text.insert("end", message, msg_type)
        else:
            self.output_text.insert("end", message, msg_type)

        # Add newline if not already present
        if not message.endswith('\n'):
            self.output_text.insert("end", "\n")

        # Keep only last max_lines
        line_count = int(self.output_text.index("end").split(".")[0])
        if line_count > self.max_lines:
            self.output_text.delete("1.0", f"{line_count - self.max_lines}.0")

        # Auto-scroll to bottom
        self.output_text.see("end")
        self.output_text.config(state="disabled")

    def _setup_logging_handler(self) -> None:
        """Set up custom logging handler for the logger."""
        try:
            # Get the PowerlifitngAnalysis logger
            powerlifting_logger = logging.getLogger("PowerliftingAnalysis")

            # Remove existing console handlers (from stderr)
            for handler in powerlifting_logger.handlers[:]:
                if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                    powerlifting_logger.removeHandler(handler)

            # Add custom GUI handler
            gui_handler = ConsoleHandler(self)
            gui_handler.setLevel(logging.INFO)
            formatter = logging.Formatter('%(levelname)s: %(message)s')
            gui_handler.setFormatter(formatter)
            powerlifting_logger.addHandler(gui_handler)
        except Exception as e:
            self.write(f"Failed to set up logging handler: {e}", "error")

    def _clear_console(self) -> None:
        """Clear console output."""
        self.output_text.config(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.config(state="disabled")
        self.write("Console cleared.", "info")

    def _execute_command(self) -> None:
        """Execute Python command from input entry."""
        command = self.input_entry.get().strip()
        if not command:
            return

        # Clear input
        self.input_entry.delete(0, "end")

        # Display the command
        self.write(f">>> {command}", "python")

        try:
            # Capture output
            captured_output = io.StringIO()
            captured_error = io.StringIO()

            # One PERSISTENT namespace for the whole session. eval/exec with
            # no globals ran every line in a fresh scope, so `a = 2` followed
            # by `a` was a NameError — a REPL that forgets its variables.
            if not hasattr(self, "_py_namespace"):
                self._py_namespace = {"__builtins__": __builtins__}
            ns = self._py_namespace

            # Execute command
            with redirect_stdout(captured_output), redirect_stderr(captured_error):
                try:
                    # Try to evaluate as expression first
                    result = eval(command, ns)
                    if result is not None:
                        print(result)
                        ns["_"] = result       # like the real REPL
                except SyntaxError:
                    # If it fails, try to execute as statement
                    exec(command, ns)

            # Display output
            output = captured_output.getvalue()
            error = captured_error.getvalue()

            if output:
                self.write(output.rstrip(), "info")
            if error:
                self.write(error.rstrip(), "error")

            if not output and not error:
                self.write("(No output)", "info")

        except Exception as e:
            error_msg = f"Error: {str(e)}\n{traceback.format_exc()}"
            self.write(error_msg, "error")
            logger.error(f"Console error: {error_msg}")

    def log(self, message: str, level: str = "info") -> None:
        """
        Log message (called by logger).

        Args:
            message: Message to log
            level: Log level (info, debug, warning, error, critical)
        """
        msg_type_map = {
            "debug": "info",
            "info": "info",
            "warning": "warning",
            "error": "error",
            "critical": "error"
        }
        msg_type = msg_type_map.get(level, "info")
        self.write(message, msg_type)

    def restore_stdout_stderr(self) -> None:
        """Restore original stdout and stderr (for cleanup)."""
        try:
            if hasattr(self, 'original_stdout'):
                sys.stdout = self.original_stdout
            if hasattr(self, 'original_stderr'):
                sys.stderr = self.original_stderr
        except Exception as e:
            if hasattr(self, 'original_stdout'):
                sys.stdout.write(f"Failed to restore stdout/stderr: {e}\n")

    def __del__(self):
        """Cleanup on destruction."""
        try:
            self.restore_stdout_stderr()
        except:
            pass


class ResizablePanelSplitter(ctk.CTkFrame):
    """Frame that holds main content and resizable console panel."""

    def __init__(self, parent):
        """Initialize splitter."""
        super().__init__(parent)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_columnconfigure(0, weight=1)

        # Main content frame
        self.content_frame = ctk.CTkFrame(self)
        self.content_frame.grid(row=0, column=0, sticky="nsew")
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        # Splitter handle
        self.splitter = ctk.CTkFrame(
            self,
            height=4,
            fg_color="#404040",
            cursor="sb_v_double_arrow"
        )
        self.splitter.grid(row=1, column=0, sticky="ew")
        self.splitter.bind("<B1-Motion>", self._on_splitter_drag)
        self.splitter.bind("<Button-1>", self._on_splitter_start)
        self.splitter.bind("<ButtonRelease-1>", self._on_splitter_end)

        # Console frame
        self.console_frame = ctk.CTkFrame(self)
        self.console_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        self.console_frame.grid_rowconfigure(0, weight=1)
        self.console_frame.grid_columnconfigure(0, weight=1)

        # Console
        self.console = ConsoleTerminal(self.console_frame)
        self.console.grid(row=0, column=0, sticky="nsew")

        # Dragging state
        self._drag_start_y = 0
        self._initial_console_height = 150

    def _on_splitter_start(self, event):
        """Handle splitter drag start."""
        self._drag_start_y = event.y_root

    def _on_splitter_drag(self, event):
        """Handle splitter drag."""
        delta = event.y_root - self._drag_start_y
        new_height = max(50, self._initial_console_height - delta)
        self.grid_rowconfigure(2, minsize=new_height)
        self.update_idletasks()

    def _on_splitter_end(self, event):
        """Handle splitter drag end."""
        self._initial_console_height = int(
            self.grid_slaves(row=2, column=0)[0].winfo_height()
        )
