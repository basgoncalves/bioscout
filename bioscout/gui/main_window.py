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

from importlib.metadata import version as _pkg_version
try:
    APP_VERSION = _pkg_version("bioscout")
except Exception:
    APP_VERSION = "dev"

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
from gui.widgets.training_tracking import TrainingTrackingTab
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
            # Start maximized to avoid graphics glitches and use the whole screen.
            # 'zoomed' maximizes the window (keeps the title bar / taskbar) on
            # Windows; '-zoomed' is the Linux equivalent. Try each safely so a
            # platform that doesn't support one doesn't crash startup.
            maximized = False
            try:
                self.state("zoomed")  # Windows / most platforms
                maximized = True
            except Exception:
                pass
            if not maximized:
                try:
                    self.attributes("-zoomed", True)  # Linux (X11)
                    maximized = True
                except Exception:
                    pass
            if not maximized:
                # Last resort: size to the full screen geometry.
                try:
                    sw = self.winfo_screenwidth()
                    sh = self.winfo_screenheight()
                    self.geometry(f"{sw}x{sh}+0+0")
                except Exception:
                    self.geometry("1400x900+0+0")
            self.minsize(1200, 700)
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
        # Ctrl+R reloads the app (shows the same confirmation popup as the button)
        self.bind_all("<Control-r>", lambda _e: self._restart_app())
        self.bind_all("<Control-R>", lambda _e: self._restart_app())

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
            ("Training Tracking", 11),
            ("Settings", 12),
            ("Logs", 13)
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
        status_frame.grid(row=14, column=0, padx=10, pady=10, sticky="ew")

        ctk.CTkLabel(status_frame, text="Status:", font=("Segoe UI", 10, "bold")).pack(padx=10, pady=(10, 5), anchor="w")
        self.status_label = ctk.CTkLabel(status_frame, text="Ready", text_color="#28a745", font=("Segoe UI", 10))
        self.status_label.pack(padx=10, pady=(0, 10), anchor="w")

        # Utility buttons row (Help + Screen Record)
        button_frame = ctk.CTkFrame(sidebar)
        button_frame.grid(row=15, column=0, padx=10, pady=10, sticky="ew")
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(button_frame, text="Help", width=60,
                      command=self.show_help).grid(row=0, column=0, padx=(0, 2), sticky="ew")
        ctk.CTkButton(button_frame, text="📹 Record",
                      fg_color="#1a3a5a", hover_color="#2a4a6a",
                      width=60, command=self._open_screen_recorder
                      ).grid(row=0, column=1, padx=(2, 0), sticky="ew")
        # Reload: relaunch the app to pick up the latest code (no manual restart)
        ctk.CTkButton(button_frame, text="🔄 Reload App",
                      fg_color="#5a3a00", hover_color="#7a5000",
                      command=self._restart_app
                      ).grid(row=1, column=0, columnspan=2, padx=0, pady=(4, 0),
                             sticky="ew")

        version_label = ctk.CTkLabel(sidebar, text=f"v{APP_VERSION}", text_color="#666666", font=("Segoe UI", 8))
        version_label.grid(row=16, column=0, padx=10, pady=5, sticky="ew")

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
            "Session Analysis": {"class": AnalysisControlSessionTab, "args": (self.config_manager, self.update_status, self.broadcast_session_dir)},
            "C3D Export": {"class": C3DExportTab, "args": (self.config_manager, self.update_status)},
            "Batch C3D": {"class": BatchC3DExport, "args": ()},
            "EMG Normalization": {"class": EMGNormalizationTab, "args": (self.config_manager, self.update_status)},
            "Model Scaling": {"class": ModelScalingTab, "args": (self.config_manager, self.update_status)},
            "CEINMS Calibration": {"class": CEINMSCalibrationSessionTab, "args": (self.config_manager, self.update_status)},
            "Batch": {"class": BatchProcessorTab, "args": (self.config_manager, self.update_status)},
            "Results": {"class": ResultsViewerTab, "args": (self.config_manager, self.update_status)},
            "Training Tracking": {"class": TrainingTrackingTab, "args": (self.config_manager, self.update_status)},
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
        """Create top bar with project selector and version status indicator."""
        topbar = ctk.CTkFrame(self.main_frame, corner_radius=8)
        topbar.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 10))
        topbar.grid_columnconfigure(2, weight=1)

        # Title label (current tab)
        self.title_label = ctk.CTkLabel(topbar, text="", font=("Segoe UI", 14, "bold"))
        self.title_label.pack(side="left", padx=15, pady=10)

        # ── Project path selector ──────────────────────────────────────────
        proj_frame = ctk.CTkFrame(topbar, fg_color="transparent")
        proj_frame.pack(side="left", padx=10, pady=8, fill="x", expand=True)

        ctk.CTkLabel(proj_frame, text="Project:", font=("Segoe UI", 11, "bold")).pack(side="left", padx=(0, 6))

        from tkinter import filedialog

        self._project_dir = ctk.StringVar(value="")
        proj_entry = ctk.CTkEntry(
            proj_frame,
            textvariable=self._project_dir,
            placeholder_text="Select project folder…",
            width=420,
        )
        proj_entry.pack(side="left", padx=4)

        # Status icon: shown after the entry
        self._proj_status = ctk.CTkLabel(
            proj_frame, text="", font=("Segoe UI", 11), width=26
        )
        self._proj_status.pack(side="left", padx=(2, 6))

        def _browse_project():
            folder = filedialog.askdirectory(title="Select Project Folder")
            if folder:
                self._project_dir.set(folder)
                self._load_project(folder)

        ctk.CTkButton(proj_frame, text="Browse", width=76,
                      command=_browse_project).pack(side="left", padx=3)
        ctk.CTkButton(proj_frame, text="Load", width=56,
                      command=lambda: self._load_project(self._project_dir.get())
                      ).pack(side="left", padx=3)

        self._update_settings_btn = ctk.CTkButton(
            proj_frame, text="↑ Update Settings", width=130,
            fg_color="#5a3a00", hover_color="#7a5000",
            font=("Segoe UI", 10),
            command=self._update_project_settings,
            state="disabled",
        )
        self._update_settings_btn.pack(side="left", padx=(8, 3))

    def _load_project(self, project_dir: str) -> None:
        """Validate project settings.py version and broadcast to tabs."""
        if not project_dir:
            return
        p = Path(project_dir)
        self._project_dir.set(str(p))

        # ── Version check (AST-only — avoids executing the file, which can
        #    fail if the project's settings.py references names like PlayerConfig
        #    that are no longer in the template's global scope) ────────────────
        settings_file = p / "settings.py"
        ok = False
        needs_update = False
        tooltip = ""
        if not settings_file.exists():
            tooltip = "⚠  No settings.py — run: python -m bioscout --init"
        else:
            try:
                import ast as _ast
                src = settings_file.read_text(encoding="utf-8", errors="replace")
                tree = _ast.parse(src)
                proj_ver = None
                for node in tree.body:
                    if (isinstance(node, _ast.Assign) and
                            any(isinstance(t, _ast.Name) and t.id == "__version__"
                                for t in node.targets)):
                        if isinstance(node.value, _ast.Constant):
                            proj_ver = node.value.value
                        break
                from settings import __version__ as _SRC_VER
                if proj_ver is None:
                    tooltip = "⚠  settings.py has no __version__ — click ↑ Update Settings"
                    needs_update = True
                elif proj_ver != _SRC_VER:
                    tooltip = f"⚠  settings v{proj_ver} ≠ src v{_SRC_VER} — click ↑ Update Settings"
                    needs_update = True
                else:
                    ok = True
                    tooltip = f"✓  settings v{proj_ver}"
            except Exception as e:
                tooltip = f"⚠  Could not read settings.py: {e}"
                needs_update = True

        if ok:
            self._proj_status.configure(text="✓", text_color="#28a745")
            self._update_settings_btn.configure(state="disabled",
                                                fg_color="#5a3a00")
        else:
            self._proj_status.configure(text="⚠", text_color="#dc3545")
            if needs_update:
                self._update_settings_btn.configure(
                    state="normal",
                    fg_color="#c87000", hover_color="#e08800")
            else:
                self._update_settings_btn.configure(state="disabled",
                                                    fg_color="#5a3a00")

        self.update_status(tooltip, "success" if ok else "warning")

        # Redirect log file into the project folder — only when the project
        # actually changes to avoid opening multiple handlers on re-validate.
        if str(p) != getattr(self, "_last_logged_project", None):
            self._last_logged_project = str(p)
            logger.set_project_log_dir(p / "logs")

        self.broadcast_project_dir(project_dir)

    def _update_project_settings(self) -> None:
        """Preview and apply a settings.py migration for the current project."""
        project_dir = self._project_dir.get().strip()
        if not project_dir:
            messagebox.showwarning("No Project", "Load a project folder first.", parent=self)
            return
        settings_file = Path(project_dir) / "settings.py"
        if not settings_file.exists():
            messagebox.showerror("Missing settings.py",
                                 "No settings.py found in this folder.\n"
                                 "Run: python -m bioscout --init", parent=self)
            return

        try:
            from utils.settings_updater import build_updated_settings
            new_text, preserved = build_updated_settings(settings_file)
        except Exception as e:
            messagebox.showerror("Migration Error", str(e), parent=self)
            return

        # ── Preview dialog ────────────────────────────────────────────────
        dlg = tkinter.Toplevel(self)
        dlg.title("Update Settings — Preview")
        dlg.geometry("820x680")
        dlg.grab_set()
        dlg.configure(bg="#1a1a2a")

        ctk.CTkLabel(dlg, text="Settings Update Preview",
                     font=("Segoe UI", 14, "bold")).pack(padx=16, pady=(14, 4))
        ctk.CTkLabel(dlg,
                     text="The values below will be preserved from your current settings.py.\n"
                          "All other fields will be updated to the latest schema.\n"
                          "A backup (settings.py.bak_<timestamp>) will be created automatically.",
                     font=("Segoe UI", 10), justify="left", text_color="#aaaaaa"
                     ).pack(padx=16, pady=(0, 8), anchor="w")

        # ── Buttons at the top so they are always visible ─────────────────
        def _apply():
            try:
                from utils.settings_updater import write_updated_settings
                write_updated_settings(settings_file)
                dlg.destroy()
                messagebox.showinfo("Settings Updated",
                                    "settings.py has been updated.\n"
                                    "A backup was saved alongside it.",
                                    parent=self)
                self._load_project(project_dir)   # re-validate
            except Exception as e:
                messagebox.showerror("Write Error", str(e), parent=self)

        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(0, 10))
        ctk.CTkButton(btn_row, text="✓  Apply Update", fg_color="#28a745",
                      hover_color="#218838", width=150,
                      command=_apply).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="Cancel", fg_color="#555555",
                      hover_color="#666666", width=100,
                      command=dlg.destroy).pack(side="left")

        # ── Preserved values (scrollable, capped height) ──────────────────
        pf_outer = ctk.CTkFrame(dlg, fg_color="#111118", corner_radius=6)
        pf_outer.pack(fill="x", padx=16, pady=(0, 6))
        ctk.CTkLabel(pf_outer, text="Preserved values:", font=("Segoe UI", 10, "bold"),
                     anchor="w").pack(anchor="w", padx=10, pady=(6, 2))
        pf_scroll = ctk.CTkScrollableFrame(pf_outer, fg_color="transparent", height=140)
        pf_scroll.pack(fill="x", padx=6, pady=(0, 6))
        for line in preserved:
            ctk.CTkLabel(pf_scroll, text=line, font=("Courier New", 9),
                         text_color="#aaddaa", anchor="w").pack(anchor="w", padx=8, pady=1)

        # ── New file preview ──────────────────────────────────────────────
        ctk.CTkLabel(dlg, text="New settings.py (preview):",
                     font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=16)
        txt_frame = ctk.CTkFrame(dlg, fg_color="#111118")
        txt_frame.pack(fill="both", expand=True, padx=16, pady=(4, 14))

        import tkinter as _tk
        txt = _tk.Text(txt_frame, bg="#111118", fg="#cccccc",
                       font=("Courier New", 9), wrap="none",
                       insertbackground="#cccccc")
        sb_y = _tk.Scrollbar(txt_frame, orient="vertical",   command=txt.yview)
        sb_x = _tk.Scrollbar(txt_frame, orient="horizontal", command=txt.xview)
        txt.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)
        sb_y.pack(side="right", fill="y")
        sb_x.pack(side="bottom", fill="x")
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", new_text)
        txt.configure(state="disabled")

    def broadcast_project_dir(self, project_dir: str) -> None:
        """Broadcast project directory to all tabs that support set_project_dir()."""
        if not project_dir:
            return
        for tab_name, tab in self.tabs.items():
            if hasattr(tab, "set_project_dir"):
                try:
                    tab.set_project_dir(project_dir)
                except Exception as e:
                    logger.error(f"Error setting project dir for {tab_name}: {e}")

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

    def _restart_app(self) -> None:
        """Relaunch BioScout so the latest code is loaded.

        Python can't reliably hot-swap a running tkinter GUI, so 'Reload'
        spawns a fresh instance with the same interpreter, arguments, and
        working directory, then closes this one. The new process picks up any
        edited source files (and the active project, since cwd is preserved).
        """
        import os
        import subprocess
        if not messagebox.askyesno(
                "Reload BioScout",
                "Restart the app to load the latest code?\n\n"
                "Any unsaved state in the tabs will be lost.",
                parent=self):
            return
        cmd = [sys.executable, "-m", "bioscout"] + sys.argv[1:]
        try:
            logger.info(f"Reloading BioScout: {' '.join(cmd)} (cwd={os.getcwd()})")
            subprocess.Popen(cmd, cwd=os.getcwd())
        except Exception as e:
            logger.error(f"Reload failed to launch new instance: {e}")
            messagebox.showerror(
                "Reload failed",
                f"Could not start a new instance:\n{e}", parent=self)
            return
        # Close this window and hard-exit so the two instances don't clash.
        try:
            self.destroy()
        finally:
            os._exit(0)

    def _open_screen_recorder(self) -> None:
        """Launch the screen recorder as a floating panel."""
        try:
            from record.screen_record import ScreenRecorder
            rec = ScreenRecorder()
            rec.open_panel(parent=self)
        except ImportError as e:
            from tkinter import messagebox
            messagebox.showerror(
                "Screen Recorder",
                f"Could not load screen recorder:\n{e}\n\n"
                "Make sure pyautogui and opencv-python are installed:\n"
                "  pip install pyautogui opencv-python",
                parent=self)
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Screen Recorder", str(e), parent=self)

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
