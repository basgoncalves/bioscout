"""Main application window for BioScout."""

import customtkinter as ctk
from tkinter import messagebox
from pathlib import Path
import sys
import platform
import threading
from concurrent.futures import ThreadPoolExecutor
import tkinter

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from version import APP_VERSION

# Patch Tkinter's exception handling to suppress non-fatal CustomTkinter scaling errors
_original_report_callback_exception = tkinter.Tk.report_callback_exception
def _patched_report_callback_exception(self, exc_type, exc_value, exc_traceback):
    """Suppress harmless CustomTkinter scaling errors."""
    error_str = str(exc_value).lower()

    # Suppress non-fatal CustomTkinter widget scaling AttributeErrors
    if exc_type == AttributeError and any(attr in error_str for attr in [
        "_canvas", "_last_geometry_manager_call", "_text_label", "_fg_color",
        "_bg_color", "_border_color", "_apply_widget_scaling", "winfo_manager",
        "_entry", "_button", "_label", "_text", "_apply_font_scaling"
    ]):
        # These are harmless CustomTkinter scaling/initialization errors
        return

    # Suppress TclError from CustomTkinter canvas coordinate issues
    if exc_type == tkinter.TclError and "coordinates" in error_str and "expected" in error_str:
        # These are canvas rendering artifacts from DPI scaling
        return

    # Call original for other exceptions
    _original_report_callback_exception(self, exc_type, exc_value, exc_traceback)

tkinter.Tk.report_callback_exception = _patched_report_callback_exception

from config.config_manager import ConfigManager
from utils.logger import logger
from gui.styles import theme
from settings import UISettings
from gui.widgets.c3d_export import C3DExportTab
from gui.widgets.emg_normalization import EMGNormalizationTab
from gui.widgets.model_scaling import ModelScalingTab
from gui.widgets.analysis_control_session import AnalysisControlSessionTab
from gui.widgets.batch_processor import BatchProcessorTab
from gui.widgets.batch_c3d_export import BatchC3DExport
from gui.widgets.results_viewer import ResultsViewerTab
from gui.widgets.logs import LogsTab
from gui.widgets.ceinms_calibration_session import CEINMSCalibrationSessionTab
from gui.widgets.configuration import ConfigurationTab
from gui.widgets.console_terminal import ResizablePanelSplitter

# Recording tab imports mediapipe/cv2 at module level — a native crash there
# would kill the whole process.  Import it lazily so any failure is catchable.
RecordingTab = None
try:
    from gui.widgets.recording import RecordingTab as _RecordingTab
    RecordingTab = _RecordingTab
except Exception as _rec_err:
    print(f"[main_window] RecordingTab unavailable: {_rec_err}", flush=True)

VideoAnalysisTab = None
try:
    from gui.widgets.video_analysis import VideoAnalysisTab as _VideoAnalysisTab
    VideoAnalysisTab = _VideoAnalysisTab
except Exception as _va_err:
    import traceback as _tb
    print(f"[main_window] VideoAnalysisTab unavailable: {_va_err}", flush=True)
    _tb.print_exc()

# Try to import libraries for better multi-monitor support
MONITOR_DETECTION_AVAILABLE = False
try:
    import pygetwindow as gw
    from screeninfo import get_monitors
    MONITOR_DETECTION_AVAILABLE = True
except ImportError:
    # Try to install silently
    try:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pygetwindow", "screeninfo", "-q"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        import pygetwindow as gw
        from screeninfo import get_monitors
        MONITOR_DETECTION_AVAILABLE = True
    except:
        pass  # Will fall back to other methods


class MainWindow(ctk.CTk):
    """Main application window."""

    def __init__(self, fullscreen=False):
        """Initialize main window."""
        # Detect terminal monitor in background thread to avoid blocking UI
        self.detected_terminal_monitor = None
        self._start_monitor_detection()

        super().__init__()

        self.title("BioScout")
        # Set window / taskbar icon
        try:
            from PIL import Image as _PILImg
            import tempfile, os
            _logo_path = Path(__file__).parent.parent / "utils" / "logo.png"
            if _logo_path.exists():
                _img = _PILImg.open(_logo_path).convert("RGBA")
                _ico_path = Path(tempfile.gettempdir()) / "bioscout_icon.ico"
                _img.save(str(_ico_path), format="ICO", sizes=[(32, 32), (48, 48), (64, 64)])
                self.iconbitmap(str(_ico_path))
        except Exception:
            pass
        self.fullscreen = fullscreen
        self.target_x = 0
        self.target_y = 0
        self.positioning_complete = False
        self._map_event_bound = False  # Prevent multiple Map event bindings

        if fullscreen:
            # Start in fullscreen mode to avoid graphics glitches
            self.attributes("-zoomed", True)  # Windows
            try:
                self.state("zoomed")  # Alternative for Windows
            except:
                pass
            try:
                self.attributes("-fullscreen", True)  # Linux
            except:
                pass
        else:
            self.geometry("1400x900+0+0")
            self.minsize(1200, 700)

        try:
            self.config_manager = ConfigManager()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load configuration: {e}")
            logger.error(f"Configuration load error: {e}")
            self.config_manager = ConfigManager()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._setup_ui()

        # Force immediate rendering
        self.update_idletasks()

        # Reposition onto the correct monitor shortly after mainloop starts
        if not fullscreen:
            self.bind("<Map>", self._on_window_mapped, add=True)

        logger.debug("Application initialized")

    def _start_monitor_detection(self):
        """Start monitor detection in background thread (non-blocking)."""
        def detect_in_thread():
            try:
                self.detected_terminal_monitor = self._detect_terminal_monitor_early()
            except Exception as e:
                logger.debug(f"Background monitor detection failed: {e}")

        # Run detection in daemon thread so it doesn't block UI
        thread = threading.Thread(target=detect_in_thread, daemon=True)
        thread.start()

    def _detect_terminal_monitor_early(self):
        """Detect which monitor the terminal window is on (called BEFORE window creation)."""
        try:
            if not MONITOR_DETECTION_AVAILABLE:
                return None

            # Get the active window (the terminal running this script)
            # This MUST be called before super().__init__() creates the window
            active_win = gw.getActiveWindow()
            if not active_win:
                logger.debug("Could not detect active window")
                return None

            # Find which monitor the terminal is on
            monitors = get_monitors()
            terminal_center_x = active_win.left + (active_win.width // 2)
            terminal_center_y = active_win.top + (active_win.height // 2)

            for i, monitor in enumerate(monitors):
                # Check if terminal center falls within this monitor's bounds
                if (monitor.x <= terminal_center_x < monitor.x + monitor.width and
                    monitor.y <= terminal_center_y < monitor.y + monitor.height):
                    logger.debug(f"Detected terminal on Monitor #{i + 1}: {monitor.width}x{monitor.height} at +{monitor.x}+{monitor.y}")
                    return monitor

            logger.debug("Could not map terminal to any monitor")
            return None

        except Exception as e:
            logger.debug(f"Terminal monitor detection failed: {e}")
            return None

    def _on_window_mapped(self, event=None) -> None:
        """Handle window map event to position it on active monitor (runs only once)."""
        # Prevent this from running multiple times during initialization
        if self.positioning_complete:
            return

        try:
            window_width = 1400
            window_height = 900
            x, y = 0, 0
            positioned = False

            # Method 1: Use pre-detected terminal monitor (detected before window creation)
            terminal_monitor = self.detected_terminal_monitor
            if terminal_monitor:
                # Center window on the detected monitor
                monitor_center_x = terminal_monitor.x + (terminal_monitor.width // 2)
                monitor_center_y = terminal_monitor.y + (terminal_monitor.height // 2)

                x = monitor_center_x - (window_width // 2)
                y = monitor_center_y - (window_height // 2)

                # Clamp to monitor bounds with margin
                margin = 10
                if x < terminal_monitor.x + margin:
                    x = terminal_monitor.x + margin
                elif x + window_width > terminal_monitor.x + terminal_monitor.width - margin:
                    x = terminal_monitor.x + terminal_monitor.width - window_width - margin

                if y < terminal_monitor.y + margin:
                    y = terminal_monitor.y + margin
                elif y + window_height > terminal_monitor.y + terminal_monitor.height - margin:
                    y = terminal_monitor.y + terminal_monitor.height - window_height - margin

                logger.debug(f"Opening window on monitor center: +{x}+{y}")
                positioned = True

            # Method 2: Fall back to mouse position if monitor detection failed
            if not positioned:
                try:
                    mouse_x = self.winfo_pointerx()
                    mouse_y = self.winfo_pointery()
                    logger.debug(f"Using mouse position fallback: ({mouse_x}, {mouse_y})")

                    x = mouse_x - (window_width // 2)
                    y = mouse_y - (window_height // 2)

                    # Get virtual screen dimensions
                    screen_width = self.winfo_screenwidth()
                    screen_height = self.winfo_screenheight()

                    try:
                        import ctypes
                        user32 = ctypes.windll.user32
                        virtual_width = user32.GetSystemMetrics(78)
                        virtual_height = user32.GetSystemMetrics(79)
                        if virtual_width > screen_width:
                            screen_width = virtual_width
                        if virtual_height > screen_height:
                            screen_height = virtual_height
                    except:
                        pass

                    margin = 10
                    x = max(margin, min(x, screen_width - window_width - margin))
                    y = max(margin, min(y, screen_height - window_height - margin))

                    positioned = True
                except Exception as e:
                    logger.debug(f"Mouse position fallback failed: {e}")

            # Apply geometry
            if positioned:
                self.geometry(f"{window_width}x{window_height}+{x}+{y}")
                self.target_x = x
                self.target_y = y
                logger.debug(f"Window positioned at +{x}+{y}")
                self.positioning_complete = True
                # Show window now that it's positioned correctly
                logger.debug("Showing window...")
                # Ensure full opacity before showing
                self.attributes("-alpha", 1.0)
                self.update_idletasks()
                self.deiconify()
                # Force rendering after deiconify
                self.after(50, lambda: self.attributes("-alpha", 1.0))
                logger.debug("Window shown")

        except Exception as e:
            logger.warning(f"Could not reposition window on map event: {e}", exc_info=True)
            self.positioning_complete = True  # Mark complete to avoid infinite loop
            # Show window anyway even if positioning failed
            self.attributes("-alpha", 1.0)
            self.update_idletasks()
            self.deiconify()
            self.after(50, lambda: self.attributes("-alpha", 1.0))


    def _start_persistent_positioning(self) -> None:
        """Disabled - persistent repositioning was causing window jitter."""
        pass

    def _setup_ui(self) -> None:
        """Setup user interface."""
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self._create_sidebar()
        self._create_main_area()

    def _create_sidebar(self) -> None:
        """Create left sidebar with navigation."""
        sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        sidebar.grid_rowconfigure(10, weight=1)

        # Logo + title at top of sidebar
        try:
            from PIL import Image as _PILImage
            _logo_path = Path(__file__).parent.parent / "utils" / "logo.png"
            _pil = _PILImage.open(_logo_path).convert("RGBA").resize((48, 48), _PILImage.LANCZOS)
            _ctk_logo = ctk.CTkImage(light_image=_pil, dark_image=_pil, size=(48, 48))
            title_label = ctk.CTkLabel(
                sidebar,
                text="BioScout",
                image=_ctk_logo,
                compound="top",
                font=("Segoe UI", 16, "bold"),
            )
        except Exception:
            title_label = ctk.CTkLabel(sidebar, text="BioScout", font=("Segoe UI", 16, "bold"))
        title_label.grid(row=0, column=0, padx=20, pady=(16, 8), sticky="ew")

        self.nav_buttons = {}
        _all_tabs = [
            ("Recording", 1),
            ("Video Analysis", 2),
            ("Session Analysis", 3),
            ("C3D Export", 4),
            ("Batch C3D", 5),
            ("EMG Normalization", 6),
            ("Model Scaling", 7),
            ("CEINMS Calibration", 8),
            ("Batch", 9),
            ("Results", 10),
            ("Settings", 11),
            ("Logs", 12)
        ]
        tabs = [(name, row) for name, row in _all_tabs
                if (name != "Recording" or RecordingTab is not None)
                and (name != "Video Analysis" or VideoAnalysisTab is not None)]

        for tab_name, row in tabs:
            btn = ctk.CTkButton(
                sidebar,
                text=tab_name,
                command=lambda t=tab_name: self.switch_tab(t),
                fg_color="#2d2d2d",
                hover_color="#3d3d3d",
                border_width=2,
                border_color="#404040"
            )
            btn.grid(row=row, column=0, padx=10, pady=6, sticky="ew")
            self.nav_buttons[tab_name] = btn

        status_frame = ctk.CTkFrame(sidebar, corner_radius=8)
        status_frame.grid(row=11, column=0, padx=10, pady=10, sticky="ew")

        ctk.CTkLabel(status_frame, text="Status:", font=("Segoe UI", 10, "bold")).pack(padx=10, pady=(10, 5), anchor="w")
        self.status_label = ctk.CTkLabel(status_frame, text="Ready", text_color="#28a745", font=("Segoe UI", 10))
        self.status_label.pack(padx=10, pady=(0, 10), anchor="w")

        # Help button (Settings removed - use system settings or preferences)
        button_frame = ctk.CTkFrame(sidebar)
        button_frame.grid(row=12, column=0, padx=10, pady=10, sticky="ew")
        button_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(button_frame, text="Help", width=60, command=self.show_help).grid(row=0, column=0, padx=2, sticky="ew")

        version_label = ctk.CTkLabel(sidebar, text=f"v{APP_VERSION}", text_color="#666666", font=("Segoe UI", 8))
        version_label.grid(row=13, column=0, padx=10, pady=5, sticky="ew")

    def _create_main_area(self) -> None:
        """Create main content area with tabs and resizable console."""
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        self._create_topbar()
        self.main_frame.grid_rowconfigure(0, weight=0)

        self.splitter = ResizablePanelSplitter(self.main_frame)
        self.splitter.grid(row=1, column=0, sticky="nsew")
        self.splitter.grid_rowconfigure(0, weight=1)

        self.tab_container = ctk.CTkFrame(self.splitter.content_frame)
        self.tab_container.grid(row=0, column=0, sticky="nsew")
        self.tab_container.grid_rowconfigure(0, weight=1)
        self.tab_container.grid_columnconfigure(0, weight=1)

        # Tab definitions for lazy loading
        self.tab_definitions = {}
        if RecordingTab is not None:
            self.tab_definitions["Recording"] = {"class": RecordingTab, "args": (self.config_manager, self.update_status)}
        if VideoAnalysisTab is not None:
            self.tab_definitions["Video Analysis"] = {"class": VideoAnalysisTab, "args": (self.config_manager, self.update_status)}
        self.tab_definitions.update({
            "Session Analysis": {"class": AnalysisControlSessionTab, "args": (self.config_manager, self.update_status)},
            "C3D Export": {"class": C3DExportTab, "args": (self.config_manager, self.update_status)},
            "Batch C3D": {"class": BatchC3DExport, "args": ()},
            "EMG Normalization": {"class": EMGNormalizationTab, "args": (self.config_manager, self.update_status)},
            "Model Scaling": {"class": ModelScalingTab, "args": (self.config_manager, self.update_status)},
            "CEINMS Calibration": {"class": CEINMSCalibrationSessionTab, "args": (self.config_manager, self.update_status)},
            "Batch": {"class": BatchProcessorTab, "args": (self.config_manager, self.update_status)},
            "Results": {"class": ResultsViewerTab, "args": (self.config_manager, self.update_status)},
            "Settings": {"class": ConfigurationTab, "args": (self.config_manager, self.update_status)},
            "Logs": {"class": LogsTab, "args": (self.config_manager, self.update_status)},
        })

        # Initialize tabs dict - will be populated on demand (lazy loading)
        self.tabs = {}
        self.tabs_loaded = set()  # Track which tabs have been created

        self.console = self.splitter.console

        # Get default tab from settings, fallback to "Recording"
        default_tab = UISettings.DEFAULT_TAB_ON_LAUNCH
        if default_tab not in self.tab_definitions:
            logger.warning(f"Default tab '{default_tab}' not found, using 'Recording'")
            default_tab = "Recording"

        self.current_tab = default_tab

        # Create only the default tab immediately with explicit grid
        logger.debug(f"Loading default tab: {default_tab}")
        self._ensure_tab_loaded(default_tab, grid_it=True)

        if default_tab in self.tabs:
            logger.debug(f"{default_tab} tab created, grid state: {self.tabs[default_tab].winfo_manager()}")
            self.tabs[default_tab].tkraise()
            logger.debug(f"{default_tab} tab raised to front")
        else:
            logger.error(f"{default_tab} tab failed to load")

        self.update()  # Force rendering
        self.update_nav_buttons()

        # Load other tabs in background to avoid blocking UI
        self._schedule_background_tab_loading()

    def _ensure_tab_loaded(self, tab_name: str, grid_it: bool = True) -> None:
        """Load a tab on demand (lazy loading). Grid it only if grid_it=True."""
        if tab_name not in self.tab_definitions:
            logger.warning(f"Tab {tab_name} not found in definitions")
            return

        # Create tab if not yet created
        if tab_name not in self.tabs_loaded:
            try:
                logger.debug(f"Attempting to load tab: {tab_name}")
                tab_def = self.tab_definitions[tab_name]
                tab_class = tab_def["class"]
                tab_args = tab_def["args"]
                logger.debug(f"Tab definition: {tab_class.__name__}, args: {len(tab_args)}")

                # Create tab with arguments
                try:
                    logger.debug(f"Creating tab instance: {tab_name}")
                    self.tabs[tab_name] = tab_class(self.tab_container, *tab_args)
                    self.tabs_loaded.add(tab_name)
                    logger.info(f"Tab created successfully: {tab_name}")
                except AttributeError as ae:
                    # Handle CustomTkinter initialization issues
                    if "_last_geometry_manager_call" in str(ae) or "_canvas" in str(ae):
                        logger.warning(f"CustomTkinter initialization issue for {tab_name}, retrying...")
                        # Defer creation to next frame
                        self.after(50, lambda t=tab_name, g=grid_it: self._ensure_tab_loaded(t, g))
                        return
                    else:
                        logger.error(f"AttributeError in {tab_name}: {ae}", exc_info=True)
                        raise
            except Exception as e:
                logger.critical(f"FAILED TO LOAD TAB '{tab_name}': {type(e).__name__}: {e}", exc_info=True)
                import traceback
                print(f"ERROR loading tab {tab_name}:")
                traceback.print_exc()
                return

        # Grid the tab if requested (even if it was created earlier without gridding)
        if grid_it and tab_name in self.tabs:
            try:
                self.tabs[tab_name].grid(row=0, column=0, sticky="nsew")
                logger.debug(f"Tab gridded: {tab_name}")
            except Exception as e:
                logger.debug(f"Could not grid {tab_name} immediately: {e}")


    def _schedule_background_tab_loading(self) -> None:
        """Schedule loading of remaining tabs in background thread (silently, without gridding)."""
        def load_tabs_in_background():
            import time
            # Load tabs in background WITHOUT gridding them (silent background creation)
            for tab_name in self.tab_definitions.keys():
                if tab_name not in self.tabs_loaded:
                    try:
                        # Load but don't grid (grid_it=False means create in memory only)
                        self._ensure_tab_loaded(tab_name, grid_it=False)
                        time.sleep(0.05)  # Small delay to spread out loading
                    except Exception as e:
                        logger.debug(f"Background load error for {tab_name}: {e}")

        # Run in daemon thread so it doesn't block
        thread = threading.Thread(target=load_tabs_in_background, daemon=True)
        thread.start()

    def _create_topbar(self) -> None:
        """Create top bar with session selector and controls."""
        topbar = ctk.CTkFrame(self.main_frame, corner_radius=8)
        topbar.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 10))
        topbar.grid_columnconfigure(1, weight=1)

        # Title shows current tab name dynamically
        self.title_label = ctk.CTkLabel(topbar, text="", font=("Segoe UI", 14, "bold"))
        self.title_label.pack(side="left", padx=15, pady=10)

        # Session-level selector
        session_frame = ctk.CTkFrame(topbar)
        session_frame.pack(side="left", padx=15, pady=10, fill="x", expand=False)

        ctk.CTkLabel(session_frame, text="Session:", font=("Segoe UI", 11, "bold")).pack(side="left", padx=(0, 10))

        from tkinter import filedialog

        self.session_dir = ctk.StringVar(value="")
        self.session_entry = ctk.CTkEntry(session_frame, textvariable=self.session_dir, placeholder_text="Select session folder...", width=400)
        self.session_entry.pack(side="left", padx=5)

        def browse_session():
            folder = filedialog.askdirectory(title="Select Session Folder")
            if folder:
                self.session_dir.set(folder)
                self.broadcast_session_dir(folder)

        ctk.CTkButton(session_frame, text="Browse", width=80, command=browse_session).pack(side="left", padx=5)
        ctk.CTkButton(session_frame, text="Load", width=60, command=lambda: self.broadcast_session_dir(self.session_dir.get())).pack(side="left", padx=5)

    def switch_tab(self, tab_name: str) -> None:
        """Switch to specified tab (with lazy loading support)."""
        if tab_name in self.tab_definitions:
            # Ensure tab is loaded before switching (grid it when accessed)
            self._ensure_tab_loaded(tab_name, grid_it=True)

            if tab_name in self.tabs:
                self.tabs[tab_name].tkraise()
                self.current_tab = tab_name
                self.update_nav_buttons()
                logger.debug(f"Switched to tab: {tab_name}")

    def update_nav_buttons(self) -> None:
        """Update navigation button states."""
        for tab_name, btn in self.nav_buttons.items():
            if tab_name == self.current_tab:
                btn.configure(border_color="#0084ff", text_color="#0084ff", fg_color="#2a2a2a")
            else:
                btn.configure(border_color="#404040", fg_color="#2d2d2d")

    def broadcast_session_dir(self, session_dir: str) -> None:
        """Broadcast session directory to all tabs that support it."""
        if not session_dir:
            return

        # Update tabs that have set_session_dir method
        for tab_name, tab in self.tabs.items():
            if hasattr(tab, 'set_session_dir'):
                try:
                    tab.set_session_dir(session_dir)
                    logger.info(f"Set session dir for {tab_name}: {session_dir}")
                except Exception as e:
                    logger.error(f"Error setting session dir for {tab_name}: {e}")

    def update_status(self, status: str, status_type: str = "info") -> None:
        """Update status bar."""
        color_map = {
            "info": "#0084ff",
            "success": "#28a745",
            "warning": "#ffc107",
            "error": "#dc3545"
        }
        color = color_map.get(status_type, color_map["info"])
        self.status_label.configure(text=status, text_color=color)
        logger.info(f"Status: {status} ({status_type})")

    def show_help(self) -> None:
        """Show help dialog."""
        help_text = "BioScout\n\n"
        help_text += "QUICK START:\n"
        help_text += "1. C3D Export - Convert motion capture files\n"
        help_text += "2. Batch C3D - Batch process multiple C3D files\n"
        help_text += "3. EMG Processing - Process session-level EMG data\n"
        help_text += "4. Session Analysis - Run biomechanical analysis\n"
        help_text += "5. CEINMS Calibration - Configure CEINMS settings\n"
        help_text += "6. View results in Results tab\n"
        messagebox.showinfo("Help", help_text)

    def on_closing(self) -> None:
        """Handle application closing."""
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            logger.info("Application closed")
            self.destroy()

    def run(self) -> None:
        """Start the application."""
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.mainloop()


def main(fullscreen=False, screen_x=None, screen_y=None):
    """Main entry point.

    Args:
        fullscreen: Start in fullscreen mode
        screen_x: Force window X position (for multi-monitor workaround)
        screen_y: Force window Y position (for multi-monitor workaround)
    """
    print("[main_window] Creating MainWindow...", flush=True)
    try:
        app = MainWindow(fullscreen=fullscreen)
    except BaseException as e:
        import traceback as _tb
        print(f"[main_window] MainWindow() FAILED ({type(e).__name__}): {e}", flush=True)
        _tb.print_exc()
        return
    print(f"[main_window] MainWindow created OK, state={app.state()}", flush=True)

    # If custom screen position provided, use it
    if screen_x is not None and screen_y is not None:
        app.after(500, lambda: app.geometry(f"1400x900+{screen_x}+{screen_y}"))
        logger.info(f"Using custom screen position: +{screen_x}+{screen_y}")

    print("[main_window] Entering mainloop...", flush=True)
    app.run()
    print("[main_window] mainloop() returned — window was closed.", flush=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="BioScout")
    parser.add_argument("--fullscreen", action="store_true", help="Start in fullscreen mode")
    parser.add_argument("--screen-x", type=int, help="Force window X position (e.g., 1920 for secondary screen)")
    parser.add_argument("--screen-y", type=int, help="Force window Y position")

    args = parser.parse_args()
    main(fullscreen=args.fullscreen, screen_x=args.screen_x, screen_y=args.screen_y)
