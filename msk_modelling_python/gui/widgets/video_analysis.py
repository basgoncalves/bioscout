"""Video Analysis Tab - Generate MOT files and joint angle data from pre-recorded video."""

import customtkinter as ctk
from pathlib import Path
import sys
import os
import threading
import subprocess
from tkinter import filedialog, messagebox
import cv2
from PIL import Image, ImageTk

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import Optional
from utils.logger import logger

# Lazy-import to avoid hard crash if mediapipe/cv2 missing
AVAILABLE_MODELS = {}
try:
    from record.video import AVAILABLE_MODELS
except Exception as _e:
    logger.warning(f"VideoAnalysisTab: could not import AVAILABLE_MODELS: {_e}")


class VideoAnalysisTab(ctk.CTkFrame):
    """Tab for analysing a pre-recorded video and generating OpenSim MOT files."""

    def __init__(self, parent, config_manager=None, update_status_callback=None):
        super().__init__(parent)

        self.config_manager = config_manager
        self.update_status = update_status_callback or (lambda x: None)

        self._video_path: Optional[Path] = None
        self._process: Optional[subprocess.Popen] = None
        self._running = False

        self._create_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _create_ui(self):
        """Build the two-column layout: left settings, right preview + log."""
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ===== LEFT PANEL =====
        left = ctk.CTkFrame(self, width=320, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        left.grid_propagate(False)

        ctk.CTkLabel(left, text="Video Analysis", font=("Segoe UI", 14, "bold")).pack(
            anchor="w", padx=10, pady=(0, 10)
        )

        scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=0, pady=0)

        # --- Video file ---
        self._section(scroll, "🎬 Input Video")

        self.video_entry = ctk.CTkEntry(scroll, placeholder_text="Select a video file…")
        self.video_entry.pack(fill="x", padx=10, pady=(0, 4))

        btn_row = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=(0, 8))
        ctk.CTkButton(btn_row, text="Browse…", width=90, command=self._browse_video).pack(side="left")
        self.video_info_label = ctk.CTkLabel(btn_row, text="", text_color="#aaaaaa",
                                              font=("Segoe UI", 10))
        self.video_info_label.pack(side="left", padx=(8, 0))

        # --- Model selection ---
        self._section(scroll, "🦴 OpenSim Model")

        model_names = list(AVAILABLE_MODELS.keys()) if AVAILABLE_MODELS else ["(no models found)"]
        self.model_var = ctk.StringVar(value=model_names[0])
        self.model_menu = ctk.CTkOptionMenu(scroll, variable=self.model_var, values=model_names)
        self.model_menu.pack(fill="x", padx=10, pady=(0, 8))

        # --- Output directory ---
        self._section(scroll, "💾 Output Directory")

        self.output_entry = ctk.CTkEntry(scroll, placeholder_text="Default: same folder as video")
        self.output_entry.pack(fill="x", padx=10, pady=(0, 4))
        ctk.CTkButton(scroll, text="Browse…", width=90, command=self._browse_output).pack(
            anchor="w", padx=10, pady=(0, 8)
        )

        # --- Options ---
        self._section(scroll, "⚙️ Options")

        opt_frame = ctk.CTkFrame(scroll, fg_color="#2d2d2d", corner_radius=8)
        opt_frame.pack(fill="x", padx=10, pady=(0, 8))

        ctk.CTkLabel(opt_frame, text="Pose detect interval (frames):",
                     font=("Segoe UI", 10)).pack(anchor="w", padx=12, pady=(10, 2))

        interval_row = ctk.CTkFrame(opt_frame, fg_color="transparent")
        interval_row.pack(fill="x", padx=12, pady=(0, 10))

        self.interval_var = ctk.IntVar(value=1)
        self.interval_label = ctk.CTkLabel(interval_row, text="1", width=30)
        self.interval_label.pack(side="right")

        ctk.CTkSlider(
            interval_row, from_=1, to=10, number_of_steps=9,
            variable=self.interval_var,
            command=lambda v: self.interval_label.configure(text=str(int(v)))
        ).pack(side="left", fill="x", expand=True)

        # --- Run / Cancel ---
        self.run_btn = ctk.CTkButton(
            scroll, text="▶  Run Analysis",
            fg_color="#28a745", hover_color="#218838",
            command=self._run_analysis
        )
        self.run_btn.pack(fill="x", padx=10, pady=(4, 4))

        self.cancel_btn = ctk.CTkButton(
            scroll, text="⏹  Cancel",
            fg_color="#dc3545", hover_color="#c82333",
            state="disabled",
            command=self._cancel_analysis
        )
        self.cancel_btn.pack(fill="x", padx=10, pady=(0, 8))

        # --- Output files list ---
        self._section(scroll, "📂 Output Files")
        self.files_frame = ctk.CTkScrollableFrame(scroll, height=100, fg_color="#1a1a1a",
                                                   corner_radius=8)
        self.files_frame.pack(fill="x", padx=10, pady=(0, 8))
        self._files_empty_label = ctk.CTkLabel(self.files_frame, text="(run analysis to see outputs)",
                                                text_color="#666666", font=("Segoe UI", 10))
        self._files_empty_label.pack(padx=8, pady=8)

        # ===== RIGHT PANEL =====
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        # Video thumbnail
        self.preview_label = ctk.CTkLabel(right, text="No video selected",
                                           width=480, height=270,
                                           fg_color="#1a1a1a", corner_radius=8)
        self.preview_label.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(right)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, sticky="ew", pady=(0, 4))

        # Log output
        log_frame = ctk.CTkFrame(right, fg_color="transparent")
        log_frame.grid(row=2, column=0, sticky="nsew")
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(log_frame, text="Log", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )

        self.log_text = ctk.CTkTextbox(log_frame, font=("Courier New", 10),
                                        fg_color="#111111", text_color="#cccccc",
                                        wrap="word")
        self.log_text.grid(row=1, column=0, sticky="nsew")

        btn_row2 = ctk.CTkFrame(log_frame, fg_color="transparent")
        btn_row2.grid(row=2, column=0, sticky="e", pady=(4, 0))
        ctk.CTkButton(btn_row2, text="Clear log", width=80,
                       fg_color="#444444", hover_color="#555555",
                       command=lambda: self.log_text.delete("1.0", "end")).pack()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _section(self, parent, title: str):
        ctk.CTkLabel(parent, text=title, font=("Segoe UI", 11, "bold")).pack(
            anchor="w", padx=10, pady=(10, 4)
        )

    def _log(self, text: str):
        """Append text to the log box (thread-safe)."""
        def _append():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", text + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.after(0, _append)

    def _set_running(self, running: bool):
        """Toggle button states."""
        self._running = running
        self.after(0, lambda: self.run_btn.configure(state="disabled" if running else "normal"))
        self.after(0, lambda: self.cancel_btn.configure(state="normal" if running else "disabled"))
        if running:
            self.after(0, lambda: self.progress_bar.configure(mode="indeterminate"))
            self.after(0, self.progress_bar.start)
        else:
            self.after(0, self.progress_bar.stop)
            self.after(0, lambda: self.progress_bar.configure(mode="determinate"))
            self.after(0, lambda: self.progress_bar.set(1.0))

    # ------------------------------------------------------------------
    # Browsing
    # ------------------------------------------------------------------

    def _browse_video(self):
        path = filedialog.askopenfilename(
            title="Select video file",
            filetypes=[
                ("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv *.m4v"),
                ("All files", "*.*"),
            ]
        )
        if not path:
            return
        self._video_path = Path(path)
        self.video_entry.delete(0, "end")
        self.video_entry.insert(0, path)
        self._load_thumbnail(self._video_path)
        self._update_video_info(self._video_path)

    def _browse_output(self):
        path = filedialog.askdirectory(title="Select output directory")
        if path:
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, path)

    def _load_thumbnail(self, video_path: Path):
        """Show the first frame of the video as a preview."""
        try:
            cap = cv2.VideoCapture(str(video_path))
            ret, frame = cap.read()
            cap.release()
            if not ret:
                return
            frame = cv2.resize(frame, (480, 270))
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = ImageTk.PhotoImage(Image.fromarray(frame_rgb))
            self.preview_label.configure(image=img, text="")
            self.preview_label.image = img  # keep reference
        except Exception as e:
            logger.debug(f"Thumbnail error: {e}")

    def _update_video_info(self, video_path: Path):
        """Show fps / duration next to Browse button."""
        try:
            cap = cv2.VideoCapture(str(video_path))
            fps = cap.get(cv2.CAP_PROP_FPS) or 0
            frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            duration = frames / fps if fps > 0 else 0
            size_mb = video_path.stat().st_size / 1_048_576
            self.video_info_label.configure(
                text=f"{frames} frames · {fps:.0f} fps · {duration:.1f}s · {size_mb:.1f} MB"
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Run / Cancel
    # ------------------------------------------------------------------

    def _run_analysis(self):
        video_str = self.video_entry.get().strip()
        if not video_str:
            messagebox.showwarning("No video", "Please select a video file first.")
            return
        video_path = Path(video_str)
        if not video_path.exists():
            messagebox.showerror("File not found", f"Cannot find:\n{video_path}")
            return

        output_str = self.output_entry.get().strip()
        output_dir = Path(output_str) if output_str else video_path.parent

        model = self.model_var.get()
        detect_interval = self.interval_var.get()

        self._log(f"=== Starting analysis ===")
        self._log(f"Video : {video_path}")
        self._log(f"Model : {model}")
        self._log(f"Output: {output_dir}")
        self._log(f"Detect interval: {detect_interval}")
        self._log("")

        self._set_running(True)
        self.update_status("Analysing video…")
        self._clear_output_files()

        thread = threading.Thread(
            target=self._run_subprocess,
            args=(video_path, model, output_dir, detect_interval),
            daemon=True
        )
        thread.start()

    def _run_subprocess(self, video_path: Path, model: str,
                        output_dir: Path, detect_interval: int):
        """Run video_analyzer.py as a subprocess and stream stdout to the log."""
        analyzer_script = Path(__file__).parent.parent.parent / "record" / "video_analyzer.py"

        cmd = [
            sys.executable, str(analyzer_script),
            "--video", str(video_path),
            "--model", model,
            "--output-dir", str(output_dir),
            "--detect-interval", str(detect_interval),
        ]

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )

            for line in self._process.stdout:
                self._log(line.rstrip())

            self._process.wait()
            rc = self._process.returncode

            if rc == 0:
                self._log("\n✅ Analysis complete.")
                self.after(0, lambda: self.update_status("Analysis complete"))
                self.after(0, lambda: self._show_output_files(output_dir))
            else:
                self._log(f"\n❌ Analysis failed (exit code {rc}).")
                self.after(0, lambda: self.update_status("Analysis failed"))

        except Exception as e:
            self._log(f"\n❌ Error: {e}")
            logger.error(f"VideoAnalysisTab subprocess error: {e}")
        finally:
            self._process = None
            self._set_running(False)

    def _cancel_analysis(self):
        if self._process and self._process.poll() is None:
            self._process.terminate()
            self._log("\n⏹ Cancelled.")
        self._set_running(False)
        self.update_status("Cancelled")

    # ------------------------------------------------------------------
    # Output files panel
    # ------------------------------------------------------------------

    def _clear_output_files(self):
        for w in self.files_frame.winfo_children():
            w.destroy()
        self._files_empty_label = ctk.CTkLabel(
            self.files_frame, text="(running…)", text_color="#666666",
            font=("Segoe UI", 10)
        )
        self._files_empty_label.pack(padx=8, pady=8)

    def _show_output_files(self, output_dir: Path):
        """List generated output files with open buttons."""
        for w in self.files_frame.winfo_children():
            w.destroy()

        interesting = list(output_dir.glob("*.mot")) + \
                      list(output_dir.glob("*.png")) + \
                      list(output_dir.glob("*.trc"))

        if not interesting:
            ctk.CTkLabel(self.files_frame, text="(no output files found)",
                          text_color="#666666", font=("Segoe UI", 10)).pack(padx=8, pady=8)
            return

        for f in sorted(interesting):
            row = ctk.CTkFrame(self.files_frame, fg_color="transparent")
            row.pack(fill="x", padx=4, pady=2)
            ctk.CTkLabel(row, text=f.name, font=("Segoe UI", 10),
                          anchor="w").pack(side="left", fill="x", expand=True)
            ctk.CTkButton(
                row, text="Open", width=55,
                fg_color="#444444", hover_color="#555555",
                command=lambda p=f: os.startfile(p)
            ).pack(side="right")
