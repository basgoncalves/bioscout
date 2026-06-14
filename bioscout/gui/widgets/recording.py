"""Enhanced screen and video recording tab widget for the main application."""

import customtkinter as ctk
from pathlib import Path
import threading
import subprocess
import sys
from tkinter import filedialog, messagebox
from datetime import datetime
import cv2
from PIL import Image, ImageTk
import io
import time

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from settings import RecordingSettings
from record.video import AVAILABLE_MODELS, MovementTracker
from utils.resource_cleanup import get_running_apps, get_system_memory_info, close_applications

# Suppress ffmpeg warnings for MJPEG streams (harmless content-length warnings)
import logging
logging.getLogger('ffmpeg').setLevel(logging.ERROR)


class RecordingTab(ctk.CTkFrame):
    """Advanced recording tab with webcam/IP camera and OpenSim model integration."""

    def __init__(self, parent, config_manager=None, update_status_callback=None):
        """Initialize the recording tab.

        Args:
            parent: Parent widget
            config_manager: Configuration manager instance
            update_status_callback: Callback function to update app status
        """
        super().__init__(parent)

        self.config_manager = config_manager
        self.update_status = update_status_callback or (lambda x: None)
        self.recorder_process = None

        # Load settings from RecordingSettings in settings.py
        self.output_dir = Path(RecordingSettings.OUTPUT_DIR_TEMPLATE)
        self.recording_duration = RecordingSettings.DEFAULT_DURATION_SECONDS
        self.camera_source = RecordingSettings.DEFAULT_VIDEO_SOURCE
        self.ip_address = RecordingSettings.IP_CAMERA_ADDRESS
        self.selected_model = RecordingSettings.DEFAULT_OSIM_MODEL

        # Camera preview attributes
        self.camera_preview_label = None
        self.camera_thread = None
        self.camera_running = False
        self.camera_cap = None
        self.camera_recording = False
        self.blink_visible = True
        self.blink_counter = 0

        self._create_ui()

        # Auto-start camera only when enabled=True in settings
        if RecordingSettings.enabled:
            self._start_camera_thread()

    def __del__(self):
        """Cleanup when tab is destroyed."""
        self.camera_running = False
        if self.camera_cap is not None:
            self.camera_cap.release()
            self.camera_cap = None

    def _start_camera_thread(self):
        """Start the background camera capture thread (idempotent)."""
        if self.camera_running:
            return
        self.camera_running = True
        self.camera_thread = threading.Thread(target=self._camera_capture_loop, daemon=True)
        self.camera_thread.start()

    def _stop_camera_thread(self):
        """Stop the capture thread and release the capture device."""
        self.camera_running = False
        if self.camera_cap is not None:
            self.camera_cap.release()
            self.camera_cap = None

    def _reload_settings(self):
        """Reload settings from RecordingSettings when tab is shown."""
        self.output_dir = Path(RecordingSettings.OUTPUT_DIR_TEMPLATE)
        self.recording_duration = RecordingSettings.DEFAULT_DURATION_SECONDS
        self.camera_source = RecordingSettings.DEFAULT_VIDEO_SOURCE
        self.ip_address = RecordingSettings.IP_CAMERA_ADDRESS
        self.selected_model = RecordingSettings.DEFAULT_OSIM_MODEL

        # Update UI if widgets exist
        if hasattr(self, 'dir_entry'):
            self.dir_entry.delete(0, "end")
            self.dir_entry.insert(0, str(self.output_dir))

        if hasattr(self, 'duration_entry'):
            self.duration_entry.delete(0, "end")
            self.duration_entry.insert(0, str(self.recording_duration))

        if hasattr(self, 'camera_var'):
            self.camera_var.set(self.camera_source)

        if hasattr(self, 'model_var'):
            self.model_var.set(self.selected_model)

    def _camera_capture_loop(self):
        """Continuously capture camera frames and display them."""
        frame_skip = 0
        frame_display_interval = 3  # Update display every 3 frames for smooth playback

        while self.camera_running:
            try:
                frame = self._capture_frame()
                if frame is not None:
                    frame_skip += 1
                    if frame_skip >= frame_display_interval:
                        frame_skip = 0
                        # Update the preview
                        self.after(0, lambda f=frame: self._display_frame(f))

                    # Handle blinking recording indicator
                    if self.camera_recording:
                        self.blink_counter += 1
                        if self.blink_counter >= 10:  # Blink every 10 frames
                            self.blink_visible = not self.blink_visible
                            self.blink_counter = 0
                else:
                    # If frame capture fails, wait and retry
                    threading.Event().wait(0.1)

            except Exception as e:
                print(f"Error in camera capture loop: {e}")
                threading.Event().wait(0.5)

    def _capture_frame(self):
        """Capture a frame from the current camera source."""
        try:
            if self.camera_cap is None:
                self._init_camera()

            if self.camera_cap is None:
                return None

            ret, frame = self.camera_cap.read()
            if ret:
                # Rotate IP camera frames 90 degrees counter-clockwise to fix rotation
                if self.camera_var.get() == "ip":
                    frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
                return frame
            else:
                # Try to reinitialize camera if read fails
                self._init_camera()
                return None

        except Exception as e:
            print(f"Error capturing frame: {e}")
            return None

    # ── IP camera helpers ────────────────────────────────────────────────────

    def _ip_status(self, text: str, ok: bool = False):
        """Thread-safe update of the IP status label."""
        if hasattr(self, "ip_status_label"):
            self.after(0, lambda: self.ip_status_label.configure(
                text=text,
                text_color="#44ff44" if ok else "#ff4444",
            ))

    @staticmethod
    def _http_reachable(url: str, timeout: float = 3.0) -> tuple[bool, str]:
        """Return (ok, message).  Does a quick HTTP GET to check reachability."""
        try:
            import urllib.request
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", "BioScout/1.0")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                code = resp.getcode()
                ct   = resp.headers.get("Content-Type", "")
                return True, f"HTTP {code}  ({ct})"
        except OSError as e:
            # Connection refused / timeout / no route
            msg = str(e)
            if "timed out" in msg.lower():
                return False, "Connection timed out — phone not on same network or app not running"
            if "refused" in msg.lower():
                return False, "Connection refused — app may be running but on a different port"
            if "no route" in msg.lower() or "network" in msg.lower():
                return False, "No route to host — check phone IP address"
            return False, f"Network error: {msg[:80]}"
        except Exception as e:
            return False, str(e)[:80]

    @staticmethod
    def _candidate_urls(base: str) -> list[str]:
        """Return a list of MJPEG endpoint candidates for common IP-camera apps."""
        base = base.rstrip("/")
        # Already looks like a full endpoint — try it first, then common variants
        candidates = [base]
        # IP Webcam (Android) — the standard endpoints
        for ep in ("/video", "/video?dummy=.mjpg", "/?action=stream",
                   "/shot.jpg", "/stream", "/mjpeg"):
            url = base.split("?")[0].split("#")[0].rstrip("/")
            # Strip any existing endpoint path before adding a new one
            if not url.endswith(ep):
                candidates.append(url + ep)
        # Deduplicate while preserving order
        seen: set = set()
        out: list = []
        for u in candidates:
            if u not in seen:
                seen.add(u)
                out.append(u)
        return out

    def _init_camera(self):
        """Initialize camera capture (webcam or IP MJPEG stream)."""
        try:
            if self.camera_cap is not None:
                self.camera_cap.release()
                self.camera_cap = None

            src = self.camera_var.get()
            if src == "none":
                return

            if src == "webcam":
                self.camera_cap = cv2.VideoCapture(0)
                self.camera_cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.camera_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                self.camera_cap.set(cv2.CAP_PROP_FPS, 30)
            else:
                # ── IP camera ────────────────────────────────────────────
                ip_addr = self.ip_entry.get().strip().rstrip("/")
                if not ip_addr:
                    self._ip_status("⚠  No URL configured")
                    return

                self._ip_status("⏳ Testing connection…")

                # 1. Quick HTTP reachability check
                ok, http_msg = self._http_reachable(ip_addr)
                if not ok:
                    self._ip_status(f"✗ {http_msg}")
                    print(f"⚠  IP camera unreachable: {http_msg}")
                    print(f"   URL tried: {ip_addr}")
                    print(f"   • Is the phone on the same Wi-Fi network?")
                    print(f"   • Is the IP Webcam app running on the phone?")
                    print(f"   • Try opening {ip_addr} in a browser on this PC")
                    self.camera_cap = None
                    return

                # 2. Try candidate MJPEG endpoints until one streams frames
                import os
                os.environ.setdefault("FFLAGS", "-hide_banner -loglevel warning")

                working_url = None
                for url in self._candidate_urls(ip_addr):
                    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    ret, _ = cap.read()
                    if ret:
                        working_url = url
                        self.camera_cap = cap
                        break
                    cap.release()

                if working_url is None:
                    tried = ", ".join(self._candidate_urls(ip_addr)[:4])
                    self._ip_status("✗ Server reachable but no video stream found")
                    print(f"⚠  No MJPEG stream found at {ip_addr}")
                    print(f"   Tried: {tried}")
                    print(f"   • In the IP Webcam app tap  Video preferences → Enable MJPEG")
                    print(f"   • Or open {ip_addr} in a browser and copy the /video URL")
                    return

                # 3. Update the URL entry if we found a better endpoint
                if working_url != ip_addr:
                    self.after(0, lambda u=working_url: (
                        self.ip_entry.delete(0, "end"),
                        self.ip_entry.insert(0, u),
                    ))
                    print(f"ℹ  Auto-detected stream URL: {working_url}")

                self.camera_cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.camera_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                self._ip_status(f"✓  Connected — {working_url}", ok=True)

        except Exception as e:
            print(f"Error initializing camera: {e}")
            self.camera_cap = None
            self._ip_status(f"✗ Error: {str(e)[:60]}")

    def _display_frame(self, frame):
        """Display a frame in the camera preview label."""
        try:
            if frame is None:
                return

            # Resize frame to fit preview area (approximately 720x400)
            frame = cv2.resize(frame, (720, 400))

            # Draw blinking recording indicator if recording
            if self.camera_recording and self.blink_visible:
                # Draw red circle in top-right corner
                cv2.circle(frame, (680, 30), 25, (0, 0, 255), -1)  # BGR format, red
                # Add "REC" text
                cv2.putText(
                    frame,
                    "REC",
                    (655, 38),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2
                )

            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Convert to PIL Image
            pil_image = Image.fromarray(frame_rgb)

            # Convert to PhotoImage
            photo_image = ImageTk.PhotoImage(image=pil_image)

            # Update label
            if self.camera_preview_label:
                self.camera_preview_label.configure(image=photo_image, text="")
                self.camera_preview_label.image = photo_image  # Keep a reference

        except Exception as e:
            print(f"Error displaying frame: {e}")

    def _create_ui(self):
        """Create the user interface with horizontal layout (left settings, right camera preview)."""
        # Main container with two columns
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # ========== LEFT PANEL (SETTINGS) ==========
        left_panel = ctk.CTkFrame(main_frame, fg_color="transparent")
        left_panel.pack(side="left", fill="both", expand=False, padx=(0, 10))

        # Title
        title_label = ctk.CTkLabel(
            left_panel,
            text="Video Recording & Analysis",
            font=("Segoe UI", 14, "bold")
        )
        title_label.pack(padx=10, pady=(0, 10), anchor="w")

        # Scrollable settings area
        settings_scroll = ctk.CTkScrollableFrame(left_panel, width=300, fg_color="transparent")
        settings_scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # ===== OUTPUT DIRECTORY =====
        output_frame = ctk.CTkFrame(settings_scroll, fg_color="#2d2d2d", corner_radius=8)
        output_frame.pack(fill="x", pady=5)

        output_title = ctk.CTkLabel(
            output_frame,
            text="💾 Output Directory",
            font=("Segoe UI", 11, "bold"),
            text_color="#ffffff"
        )
        output_title.pack(padx=15, pady=(10, 5), anchor="w")

        dir_button_frame = ctk.CTkFrame(output_frame, fg_color="transparent")
        dir_button_frame.pack(padx=15, pady=5, fill="x")

        self.dir_entry = ctk.CTkEntry(
            dir_button_frame,
            placeholder_text="C:\\Videos\\Recordings",
            font=("Consolas", 9),
            width=200
        )
        self.dir_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.dir_entry.insert(0, str(self.output_dir))

        browse_btn = ctk.CTkButton(
            dir_button_frame,
            text="Browse",
            command=self._choose_directory,
            width=80,
            font=("Segoe UI", 9)
        )
        browse_btn.pack(side="right", padx=0)

        # ===== VIDEO SOURCE =====
        source_frame = ctk.CTkFrame(settings_scroll, fg_color="#2d2d2d", corner_radius=8)
        source_frame.pack(fill="x", pady=5)

        source_title = ctk.CTkLabel(
            source_frame,
            text="📹 Video Source",
            font=("Segoe UI", 11, "bold"),
            text_color="#ffffff"
        )
        source_title.pack(padx=15, pady=(10, 5), anchor="w")

        # When enabled=True: auto-select configured source.
        # When enabled=False: start with nothing selected; user must choose.
        if RecordingSettings.enabled:
            default_camera = "ip" if (self.ip_address and self.ip_address.strip()) else "webcam"
        else:
            default_camera = "none"
        self.camera_var = ctk.StringVar(value=default_camera)

        webcam_btn = ctk.CTkRadioButton(
            source_frame,
            text="Webcam (USB Camera)",
            variable=self.camera_var,
            value="webcam",
            command=self._on_camera_changed,
            font=("Segoe UI", 10)
        )
        webcam_btn.pack(padx=15, pady=2, anchor="w")

        ip_btn = ctk.CTkRadioButton(
            source_frame,
            text="IP Camera",
            variable=self.camera_var,
            value="ip",
            command=self._on_camera_changed,
            font=("Segoe UI", 10)
        )
        ip_btn.pack(padx=15, pady=2, anchor="w")

        # IP Address input (full width below IP Camera button)
        self.ip_frame = ctk.CTkFrame(source_frame, fg_color="transparent")
        self.ip_frame.pack(padx=15, pady=(10, 5), fill="x")

        ip_label = ctk.CTkLabel(
            self.ip_frame,
            text="📍 IP Camera URL:",
            font=("Segoe UI", 10, "bold"),
            text_color="#ffffff"
        )
        ip_label.pack(anchor="w", pady=(0, 5))

        # Entry + Connect button row
        ip_row = ctk.CTkFrame(self.ip_frame, fg_color="transparent")
        ip_row.pack(fill="x", pady=0)
        ip_row.grid_columnconfigure(0, weight=1)

        self.ip_entry = ctk.CTkEntry(
            ip_row,
            placeholder_text="http://192.168.x.x:8080/video",
            font=("Segoe UI", 10),
            height=35,
        )
        self.ip_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.ip_entry.insert(0, self.ip_address)
        self.ip_entry.bind("<Return>", lambda e: self._init_camera())

        ctk.CTkButton(
            ip_row,
            text="🔗 Connect",
            width=90,
            height=35,
            font=("Segoe UI", 10),
            fg_color="#1a4a1a",
            hover_color="#2a6a2a",
            command=self._init_camera,
        ).grid(row=0, column=1)

        # Connection status indicator
        self.ip_status_label = ctk.CTkLabel(
            self.ip_frame,
            text="",
            font=("Segoe UI", 9),
            text_color="#ff4444"
        )
        self.ip_status_label.pack(anchor="w", pady=(3, 0))

        # Help text
        help_label = ctk.CTkLabel(
            self.ip_frame,
            text="Examples: http://77.80.25.194:8080/video  |  http://192.168.1.100:8080/?action=stream",
            font=("Segoe UI", 8),
            text_color="#666666"
        )
        help_label.pack(anchor="w", pady=(3, 0))

        # Show IP frame if IP camera is the default, otherwise hide it
        if default_camera == "ip":
            self.ip_frame.pack(padx=15, pady=(10, 5), fill="x")
        else:
            self.ip_frame.pack_forget()

        # ===== OPENSIM MODEL =====
        model_frame = ctk.CTkFrame(settings_scroll, fg_color="#2d2d2d", corner_radius=8)
        model_frame.pack(fill="x", pady=5)

        model_title = ctk.CTkLabel(
            model_frame,
            text="🦴 OpenSim Model",
            font=("Segoe UI", 11, "bold"),
            text_color="#ffffff"
        )
        model_title.pack(padx=15, pady=(10, 5), anchor="w")

        # Get available models and set default
        available_model_keys = list(AVAILABLE_MODELS.keys())
        default_model = "arm26_ball" if "arm26_ball" in available_model_keys else available_model_keys[0]
        self.model_var = ctk.StringVar(value=default_model)

        # Create radio buttons for each available model
        for model_name in sorted(available_model_keys):
            radio = ctk.CTkRadioButton(
                model_frame,
                text=model_name,
                variable=self.model_var,
                value=model_name,
                font=("Segoe UI", 10)
            )
            radio.pack(padx=15, pady=2, anchor="w")

        # ===== RECORDING DURATION =====
        duration_frame = ctk.CTkFrame(settings_scroll, fg_color="#2d2d2d", corner_radius=8)
        duration_frame.pack(fill="x", pady=5)

        duration_title = ctk.CTkLabel(
            duration_frame,
            text="⏱ Recording Duration",
            font=("Segoe UI", 11, "bold"),
            text_color="#ffffff"
        )
        duration_title.pack(padx=15, pady=(10, 5), anchor="w")

        duration_input_frame = ctk.CTkFrame(duration_frame, fg_color="transparent")
        duration_input_frame.pack(padx=15, pady=5, fill="x", anchor="w")

        duration_label = ctk.CTkLabel(
            duration_input_frame,
            text="Seconds:",
            font=("Segoe UI", 10),
            text_color="#aaaaaa"
        )
        duration_label.pack(side="left", padx=(0, 10))

        self.duration_entry = ctk.CTkEntry(
            duration_input_frame,
            placeholder_text="10",
            font=("Segoe UI", 10),
            width=80
        )
        self.duration_entry.pack(side="left", padx=5)
        self.duration_entry.insert(0, str(self.recording_duration))

        # ===== STATUS =====
        self.status_label = ctk.CTkLabel(
            settings_scroll,
            text="Ready to record",
            font=("Segoe UI", 10),
            text_color="#666666"
        )
        self.status_label.pack(padx=15, pady=(20, 10), anchor="w")

        # ===== ANALYZE BUTTON =====
        analyze_btn = ctk.CTkButton(
            settings_scroll,
            text="📊 Analyze Recording",
            command=self._analyze_recording,
            font=("Segoe UI", 11),
            height=35
        )
        analyze_btn.pack(fill="x", padx=15, pady=5)

        # ===== RESOURCE CLEANUP BUTTON =====
        cleanup_btn = ctk.CTkButton(
            settings_scroll,
            text="🧹 Free Up Resources",
            command=self._show_resource_cleanup_dialog,
            font=("Segoe UI", 11),
            height=35,
            fg_color="#ff9800",
            hover_color="#f57c00"
        )
        cleanup_btn.pack(fill="x", padx=15, pady=5)

        # ========== RIGHT PANEL (CAMERA PREVIEW + RECORD BUTTON) ==========
        right_panel = ctk.CTkFrame(main_frame, fg_color="transparent")
        right_panel.pack(side="right", fill="both", expand=True, padx=(10, 0))

        # Camera preview area
        camera_frame = ctk.CTkFrame(right_panel, fg_color="#1e1e1e", corner_radius=8, border_width=2, border_color="#404040")
        camera_frame.pack(fill="both", expand=True, pady=(0, 10))

        _init_text = ("📷 Camera Preview\nWebcam Ready"
                      if RecordingSettings.enabled
                      else "📷 Select a camera source to begin")
        self.camera_preview_label = ctk.CTkLabel(
            camera_frame,
            text=_init_text,
            text_color="#888888",
            font=("Segoe UI", 14),
            fg_color="#1e1e1e"
        )
        self.camera_preview_label.pack(fill="both", expand=True, padx=20, pady=20)

        # Recording controls frame
        controls_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        controls_frame.pack(fill="x")

        # Start Recording button (large and prominent)
        record_btn = ctk.CTkButton(
            controls_frame,
            text="🔴 Start Recording",
            command=self._start_recording,
            font=("Segoe UI", 14, "bold"),
            height=50,
            fg_color="#c62828",
            hover_color="#7f0000"
        )
        record_btn.pack(fill="x", pady=5)

        # Initialize camera preview
        self._update_camera_preview()
        self._refresh_output_list()

    def _on_camera_changed(self):
        """Handle camera source change."""
        src = self.camera_var.get()
        if src == "ip":
            self.ip_frame.pack(padx=15, pady=5, fill="x")
        else:
            self.ip_frame.pack_forget()

        if src == "none":
            self._stop_camera_thread()
            self.camera_preview_label.configure(
                image="",
                text="📷 Select a camera source to begin",
                text_color="#666666",
            )
            return

        # Start capture thread on first real selection, then reinit camera
        if not self.camera_running:
            self._start_camera_thread()
        else:
            self._stop_camera_thread()
            self._start_camera_thread()

        self._update_camera_preview()

    def _update_camera_preview(self):
        """Update camera preview label with current camera info."""
        if self.camera_var.get() == "webcam":
            self.camera_preview_label.configure(
                text="📹 Webcam Preview\n(USB Camera)\nReady to record",
                text_color="#88aa88"
            )
        else:
            ip_addr = self.ip_entry.get().strip() or "Not configured"
            self.camera_preview_label.configure(
                text=f"📹 IP Camera Preview\n{ip_addr}\nReady to record",
                text_color="#88aa88"
            )

    def _choose_directory(self):
        """Choose output directory."""
        directory = filedialog.askdirectory(
            title="Choose Recording Output Directory",
            initialdir=str(self.output_dir)
        )
        if directory:
            self.output_dir = Path(directory)
            self.dir_entry.delete(0, "end")
            self.dir_entry.insert(0, str(self.output_dir))
            self.update_status(f"Output directory set to: {self.output_dir}")

    def _start_recording(self):
        """Start video recording session."""
        try:
            # Update output directory from entry field
            dir_path = self.dir_entry.get().strip()
            if not dir_path:
                messagebox.showerror("Error", "Please enter a valid output directory path")
                return
            self.output_dir = Path(dir_path)

            # Update IP address from entry field
            if self.camera_var.get() == "ip":
                self.ip_address = self.ip_entry.get()
                if not self.ip_address.strip():
                    messagebox.showerror("Error", "Please enter a valid IP address")
                    return

            # Get recording duration from entry field
            try:
                duration_str = self.duration_entry.get().strip()
                self.recording_duration = int(duration_str) if duration_str else 10
                if self.recording_duration <= 0:
                    messagebox.showerror("Error", "Recording duration must be greater than 0 seconds")
                    return
            except ValueError:
                messagebox.showerror("Error", "Recording duration must be a valid number (e.g., 10)")
                return

            self.update_status("Starting video recording...")
            self.status_label.configure(
                text="Recording in progress... (will auto-analyze when done)",
                text_color="#ff6b00"
            )

            # Set recording flag for camera preview
            self.camera_recording = True
            self.blink_visible = True
            self.blink_counter = 0

            # Create timestamped session folder
            base_output_dir = Path(dir_path)
            base_output_dir.mkdir(parents=True, exist_ok=True)

            # Create session folder: movement_YYYYMMDD_HHMMSS
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_folder = base_output_dir / f"movement_{timestamp}"
            session_folder.mkdir(parents=True, exist_ok=True)

            # Prepare arguments for recording script
            args = [
                sys.executable,
                str(Path(__file__).parent.parent.parent / "record" / "video_recorder.py"),
                "--output-dir", str(session_folder),
                "--camera", self.camera_var.get(),
                "--model", self.model_var.get(),
                "--duration", str(self.recording_duration),
            ]

            if self.camera_var.get() == "ip":
                args.extend(["--ip-address", self.ip_address])

            # Launch recording in background thread
            threading.Thread(
                target=self._run_recording,
                args=(args, session_folder, base_output_dir),
                daemon=True
            ).start()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to start recording: {e}")
            self.status_label.configure(text=f"Error: {e}", text_color="#dc3545")
            self.update_status(f"Error: {e}")

    def _run_recording(self, args, session_folder, base_output_dir):
        """Run recording directly (no subprocess) to preserve camera access."""
        try:
            # ========== STEP 0: Pause Camera Preview ==========
            # Release camera so tracker can open it exclusively
            was_running = self.camera_running
            self.camera_running = False
            if self.camera_cap is not None:
                self.camera_cap.release()
                self.camera_cap = None
            print("Camera preview paused for recording")

            # ========== STEP 1: Record Video ==========
            self.status_label.configure(
                text="Recording video...",
                text_color="#ff6b00"
            )
            self.update_status("Recording video...")

            # Initialize tracker
            try:
                tracker = MovementTracker()
                print(f"✓ MovementTracker initialized successfully")
            except Exception as e:
                print(f"ERROR: Failed to initialize MovementTracker: {e}")
                self.status_label.configure(
                    text=f"Recording error: Failed to initialize tracker",
                    text_color="#dc3545"
                )
                self.update_status(f"Recording error: {e}")
                # Resume camera preview even on error
                self.camera_running = was_running
                return

            # Record video directly (not in subprocess) - camera context preserved
            try:
                # Use values directly from GUI (already validated in _start_recording)
                camera_type = self.camera_var.get()
                duration = self.recording_duration
                model_name = self.model_var.get()
                ip_address = self.ip_address if camera_type == "ip" else None

                print(f"Starting direct recording (camera: {camera_type}, model: {model_name}, duration: {duration}s)")
                if camera_type == "ip" and ip_address:
                    print(f"Using IP camera: {ip_address}")

                video_path = tracker.record_video(
                    duration_seconds=duration,
                    camera_type=camera_type,
                    ip_address=ip_address,  # Pass IP address for IP cameras
                    output_dir=session_folder,
                    target_fps=None,
                    detection_interval=1
                )
                print(f"Recording complete. Video path: {video_path}")
            except Exception as e:
                print(f"ERROR: Exception during record_video: {e}")
                import traceback
                traceback.print_exc()
                self.status_label.configure(
                    text=f"Recording error: Failed to record video",
                    text_color="#dc3545"
                )
                self.update_status(f"Recording error: {e}")
                # Resume camera preview even on error
                self.camera_running = was_running
                return

            # Reset recording flag when done
            self.camera_recording = False
            self.blink_visible = True

            if video_path is None:
                self.status_label.configure(
                    text=f"Recording error: No video file generated",
                    text_color="#dc3545"
                )
                self.update_status("Recording error: No video file generated")
                return

            # ========== STEP 2: Verify Video File ==========
            # video_path is already known from record_video() call
            if not Path(video_path).exists():
                self.status_label.configure(
                    text="Recording completed but video file not found",
                    text_color="#dc3545"
                )
                self.update_status("Video file not found")
                return

            latest_video = Path(video_path)
            file_size_mb = latest_video.stat().st_size / (1024*1024)
            print(f"Recorded video: {latest_video}")
            print(f"Video file size: {file_size_mb:.1f} MB")

            if file_size_mb < 0.1:
                print(f"⚠ WARNING: Video file is very small ({file_size_mb:.3f} MB) - frames may not have been captured")
                print(f"           This suggests camera access issue - check diagnostics above")

            # ========== STEP 3: Run Analysis ==========
            self.status_label.configure(
                text="Running pose detection and analysis...",
                text_color="#ff6b00"
            )
            self.update_status("Analyzing video for joint angles...")

            selected_model = self.model_var.get()
            print(f"\n[Analysis Configuration]")
            print(f"  Selected model: {selected_model}")
            print(f"  Video path: {latest_video}")
            print(f"  Output directory: {session_folder}")

            analysis_args = [
                sys.executable,
                str(Path(__file__).parent.parent.parent / "record" / "video_analyzer.py"),
                "--video", str(latest_video),
                "--model", selected_model,
                "--output-dir", str(session_folder),
            ]

            analysis_process = subprocess.Popen(
                analysis_args,
                cwd=str(Path(__file__).parent.parent.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            analysis_stdout, analysis_stderr = analysis_process.communicate()

            if analysis_process.returncode == 0:
                # ========== STEP 4: Success ==========
                self.status_label.configure(
                    text="Recording & analysis complete! MOT file generated.",
                    text_color="#28a745"
                )
                self.update_status("Recording and analysis completed successfully")

                # Print analysis results
                if analysis_stdout:
                    print("Analysis Output:")
                    print(analysis_stdout)

                self.after(1000, self._refresh_output_list)
            else:
                # ========== STEP 4: Analysis Error ==========
                error_msg = analysis_stderr or analysis_stdout
                self.status_label.configure(
                    text=f"Video recorded but analysis failed. Check logs.",
                    text_color="#ff9800"
                )
                self.update_status(f"Analysis error: {error_msg[:200]}")

                # Print error details
                if analysis_stderr:
                    print("Analysis Error:")
                    print(analysis_stderr)

        except Exception as e:
            self.camera_recording = False
            self.status_label.configure(
                text=f"Error: {e}",
                text_color="#dc3545"
            )
            self.update_status(f"Error: {e}")
        finally:
            # Always resume camera preview
            print("Resuming camera preview...")
            self.camera_running = was_running if 'was_running' in locals() else True
            self._init_camera()

    def _analyze_recording(self):
        """Open file dialog to select and analyze a recording."""
        try:
            # Update output directory from entry field
            dir_path = self.dir_entry.get().strip()
            if dir_path:
                self.output_dir = Path(dir_path)

            video_file = filedialog.askopenfilename(
                title="Select video file to analyze",
                initialdir=str(self.output_dir),
                filetypes=[("MP4 files", "*.mp4"), ("All files", "*.*")]
            )

            if not video_file:
                return

            self.update_status("Starting analysis...")
            self.status_label.configure(text="Analyzing video...", text_color="#ff6b00")

            args = [
                sys.executable,
                str(Path(__file__).parent.parent.parent / "record" / "video_analyzer.py"),
                "--video", video_file,
                "--model", self.model_var.get(),
                "--output-dir", str(Path(video_file).parent),
            ]

            threading.Thread(
                target=self._run_analysis,
                args=(args,),
                daemon=True
            ).start()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to start analysis: {e}")
            self.status_label.configure(text=f"Error: {e}", text_color="#dc3545")

    def _run_analysis(self, args):
        """Run analysis subprocess."""
        try:
            self.status_label.configure(
                text="Extracting frames and detecting poses...",
                text_color="#ff6b00"
            )
            self.update_status("Running pose detection on video...")

            process = subprocess.Popen(
                args,
                cwd=str(Path(__file__).parent.parent.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate()

            if process.returncode == 0:
                self.status_label.configure(
                    text="Analysis complete! MOT file generated. Check output directory.",
                    text_color="#28a745"
                )
                self.update_status("Analysis completed successfully")

                # Print analysis results
                if stdout:
                    print("Analysis Output:")
                    print(stdout)

                self.after(1000, self._refresh_output_list)
            else:
                error_msg = stderr or stdout
                self.status_label.configure(
                    text=f"Analysis error: {error_msg[:100]}",
                    text_color="#dc3545"
                )
                self.update_status(f"Analysis error: {error_msg[:200]}")

                # Print error details
                if stderr:
                    print("Analysis Error:")
                    print(stderr)

        except Exception as e:
            self.status_label.configure(
                text=f"Error: {e}",
                text_color="#dc3545"
            )
            self.update_status(f"Error: {e}")

    def _refresh_output_list(self):
        """Refresh settings from RecordingSettings."""
        try:
            # Reload settings from RecordingSettings in case they were changed
            self._reload_settings()

            # Update output directory from entry field
            dir_path = self.dir_entry.get().strip()
            if dir_path:
                self.output_dir = Path(dir_path)

        except Exception as e:
            self.update_status(f"Error refreshing settings: {e}")

    def _show_resource_cleanup_dialog(self):
        """Show dialog for closing resource-heavy applications."""
        try:
            # Get running apps
            running_apps = get_running_apps()
            memory = get_system_memory_info()

            if not running_apps:
                messagebox.showinfo(
                    "System Resources",
                    f"System Memory:\n"
                    f"  Available: {memory['available_mb']:.0f} MB\n"
                    f"  Used: {memory['used_mb']:.0f} MB ({memory['percent']:.1f}%)\n\n"
                    f"No resource-heavy applications detected.\n"
                    f"System is ready for recording!"
                )
                return

            # Create custom dialog with app list
            dialog = ctk.CTkToplevel(self)
            dialog.title("Free Up System Resources")
            dialog.geometry("500x400")
            dialog.resizable(True, True)

            # Memory info
            info_text = (
                f"System Memory Usage:\n"
                f"  Available: {memory['available_mb']:.0f} MB / {memory['total_mb']:.0f} MB\n"
                f"  Used: {memory['percent']:.1f}%\n\n"
                f"Close unnecessary applications to free up memory:"
            )

            info_label = ctk.CTkLabel(
                dialog,
                text=info_text,
                font=("Segoe UI", 10),
                justify="left"
            )
            info_label.pack(padx=15, pady=10)

            # Scrollable frame for app list
            scroll_frame = ctk.CTkScrollableFrame(dialog)
            scroll_frame.pack(fill="both", expand=True, padx=15, pady=10)

            # Checkboxes for each app
            checked_vars = {}
            for app_name, (pid, memory_mb) in sorted(
                running_apps.items(),
                key=lambda x: x[1][1],
                reverse=True
            ):
                var = ctk.BooleanVar(value=False)
                checked_vars[app_name] = var

                frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
                frame.pack(fill="x", pady=2)

                checkbox = ctk.CTkCheckBox(
                    frame,
                    text=f"{app_name} ({memory_mb:.1f} MB)",
                    variable=var,
                    font=("Segoe UI", 10)
                )
                checkbox.pack(side="left", fill="x", expand=True)

            # Button frame
            button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
            button_frame.pack(fill="x", padx=15, pady=10)

            def close_selected():
                """Close selected applications."""
                apps_to_close = [
                    app_name
                    for app_name, var in checked_vars.items()
                    if var.get()
                ]

                if not apps_to_close:
                    messagebox.showinfo("No Apps Selected", "Please select apps to close.")
                    return

                # Confirm before closing
                confirm = messagebox.askyesno(
                    "Confirm Close",
                    f"Close {len(apps_to_close)} application(s)?\n\n" +
                    "\n".join(f"  • {app}" for app in apps_to_close)
                )

                if not confirm:
                    return

                # Close apps
                results = close_applications(apps_to_close)
                success_count = sum(1 for v in results.values() if v)
                failed_count = len(results) - success_count

                message = f"Closed {success_count} application(s)"
                if failed_count > 0:
                    message += f"\nFailed to close {failed_count} application(s)"

                messagebox.showinfo("Complete", message)

                # Refresh memory info
                new_memory = get_system_memory_info()
                freed_mb = memory['used_mb'] - new_memory['used_mb']
                if freed_mb > 0:
                    messagebox.showinfo(
                        "Memory Freed",
                        f"Freed approximately {freed_mb:.0f} MB of memory!\n\n"
                        f"Now available: {new_memory['available_mb']:.0f} MB"
                    )

                dialog.destroy()

            close_btn = ctk.CTkButton(
                button_frame,
                text="Close Selected Applications",
                command=close_selected,
                fg_color="#c62828",
                hover_color="#7f0000",
                font=("Segoe UI", 11)
            )
            close_btn.pack(side="left", fill="x", expand=True, padx=5)

            cancel_btn = ctk.CTkButton(
                button_frame,
                text="Cancel",
                command=dialog.destroy,
                font=("Segoe UI", 11)
            )
            cancel_btn.pack(side="left", fill="x", expand=True, padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to show resource cleanup dialog: {e}")
            print(f"Error in resource cleanup: {e}")
            import traceback
            traceback.print_exc()
