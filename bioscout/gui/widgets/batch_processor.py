"""Batch Video Analysis Tab - Run full pose + MOT pipeline on multiple videos."""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
import sys
import os
import threading
import subprocess

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.config_manager import ConfigManager
from utils.logger import logger

_AVAILABLE_MODELS: dict = {}
try:
    from record.video import AVAILABLE_MODELS as _AVAILABLE_MODELS
except Exception as _e:
    logger.warning(f"BatchProcessor: could not import AVAILABLE_MODELS: {_e}")


class BatchProcessorTab(ctk.CTkFrame):
    """Tab for unattended batch video analysis."""

    def __init__(self, parent, config_manager: ConfigManager, status_callback):
        super().__init__(parent)
        self.config_manager = config_manager
        self.status_callback = status_callback

        self._videos: list = []
        self._running = False
        self._cancel_flag = threading.Event()
        self._process = None

        self._create_widgets()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _create_widgets(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="Batch Video Analysis",
                     font=("Segoe UI", 15, "bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            hdr,
            text="Add videos, choose a model, then Run. "
                 "Each video is processed fully automatically (auto-track -> pose -> MOT).",
            font=("Segoe UI", 10), text_color="#888888", wraplength=680,
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        # Body: settings left, queue right
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=4)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        # --- Settings panel ---
        cfg = ctk.CTkFrame(body, corner_radius=6)
        cfg.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        cfg.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(cfg, text="Settings",
                     font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(8, 4))

        # Model
        ctk.CTkLabel(cfg, text="OpenSim Model", font=("Segoe UI", 10),
                     text_color="#aaaaaa").grid(row=1, column=0, sticky="w", padx=10, pady=(6, 0))
        model_names = list(_AVAILABLE_MODELS.keys()) if _AVAILABLE_MODELS else ["(no models found)"]
        try:
            from settings import RecordingSettings as _RS
            _default = _RS.DEFAULT_VIDEO_ANALYSIS_MODEL
        except Exception:
            _default = ""
        _initial = _default if _default in model_names else model_names[0]
        self.model_var = ctk.StringVar(value=_initial)
        ctk.CTkOptionMenu(cfg, variable=self.model_var, values=model_names).grid(
            row=2, column=0, sticky="ew", padx=10, pady=(2, 6))

        # Detect interval
        ctk.CTkLabel(cfg, text="Pose detect interval (frames)", font=("Segoe UI", 10),
                     text_color="#aaaaaa").grid(row=3, column=0, sticky="w", padx=10, pady=(6, 0))
        self.interval_var = ctk.IntVar(value=1)
        ctk.CTkSlider(cfg, from_=1, to=10, number_of_steps=9,
                      variable=self.interval_var).grid(
            row=4, column=0, sticky="ew", padx=10, pady=(2, 0))
        self._interval_label = ctk.CTkLabel(cfg, text="1", font=("Segoe UI", 10))
        self._interval_label.grid(row=5, column=0, sticky="w", padx=10)

        def _upd_interval(*_):
            self._interval_label.configure(text=str(self.interval_var.get()))
        self.interval_var.trace_add("write", _upd_interval)

        # Output directory
        ctk.CTkLabel(cfg, text="Output Directory", font=("Segoe UI", 10),
                     text_color="#aaaaaa").grid(row=6, column=0, sticky="w", padx=10, pady=(10, 0))
        ctk.CTkLabel(cfg, text="(blank = same folder as each video)",
                     font=("Segoe UI", 9), text_color="#666666").grid(
            row=7, column=0, sticky="w", padx=10)
        self.output_entry = ctk.CTkEntry(cfg, placeholder_text="Leave blank = next to video")
        self.output_entry.grid(row=8, column=0, sticky="ew", padx=10, pady=(2, 2))
        ctk.CTkButton(cfg, text="Browse...", height=24,
                      fg_color="#444444", hover_color="#555555",
                      command=self._browse_output).grid(
            row=9, column=0, sticky="w", padx=10, pady=(0, 8))

        # Action buttons
        btn_row = ctk.CTkFrame(cfg, fg_color="transparent")
        btn_row.grid(row=10, column=0, sticky="ew", padx=10, pady=(4, 10))
        btn_row.grid_columnconfigure((0, 1), weight=1)

        self.run_btn = ctk.CTkButton(
            btn_row, text="Run Batch",
            fg_color="#28a745", hover_color="#218838",
            command=self._start_batch)
        self.run_btn.grid(row=0, column=0, padx=(0, 3), sticky="ew")

        self.cancel_btn = ctk.CTkButton(
            btn_row, text="Cancel",
            fg_color="#dc3545", hover_color="#c82333",
            state="disabled", command=self._cancel_batch)
        self.cancel_btn.grid(row=0, column=1, padx=(3, 0), sticky="ew")

        # --- Queue panel ---
        qpanel = ctk.CTkFrame(body, corner_radius=6)
        qpanel.grid(row=0, column=1, sticky="nsew")
        qpanel.grid_columnconfigure(0, weight=1)
        qpanel.grid_rowconfigure(1, weight=1)

        qhdr = ctk.CTkFrame(qpanel, fg_color="transparent")
        qhdr.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        qhdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(qhdr, text="Video Queue",
                     font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")

        btns = ctk.CTkFrame(qhdr, fg_color="transparent")
        btns.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(btns, text="+ Add Videos", height=26,
                      fg_color="#1a4a6a", hover_color="#1e5a80",
                      command=self._add_videos).pack(side="left", padx=2)
        ctk.CTkButton(btns, text="+ Add Folder", height=26,
                      fg_color="#1a4a6a", hover_color="#1e5a80",
                      command=self._add_folder).pack(side="left", padx=2)
        ctk.CTkButton(btns, text="Clear All", height=26,
                      fg_color="#442222", hover_color="#663333",
                      command=self._clear_queue).pack(side="left", padx=2)

        self._queue_scroll = ctk.CTkScrollableFrame(
            qpanel, fg_color="#0d0d12", corner_radius=4)
        self._queue_scroll.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        self._queue_scroll.grid_columnconfigure(0, weight=1)

        self._queue_rows = {}
        self._queue_empty_label = ctk.CTkLabel(
            self._queue_scroll,
            text="No videos added yet.\nClick '+ Add Videos' or '+ Add Folder'.",
            font=("Segoe UI", 10), text_color="#555555")
        self._queue_empty_label.pack(pady=20)

        # Log / progress
        log_frame = ctk.CTkFrame(self, corner_radius=6)
        log_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 10))
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)

        log_hdr = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_hdr.grid(row=0, column=0, sticky="ew", padx=8, pady=(6, 2))
        log_hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(log_hdr, text="Console Output",
                     font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(log_hdr, text="Clear", height=22, width=50,
                      fg_color="#333333", hover_color="#444444",
                      command=self._clear_log).grid(row=0, column=1, sticky="e")

        self._log_box = ctk.CTkTextbox(log_frame, font=("Consolas", 9),
                                       fg_color="#080810", state="disabled")
        self._log_box.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))

        self._progress_label = ctk.CTkLabel(
            self, text="", font=("Segoe UI", 10), text_color="#aaaaaa")
        self._progress_label.grid(row=3, column=0, sticky="w", padx=14, pady=(0, 6))

    # ------------------------------------------------------------------
    # Queue management
    # ------------------------------------------------------------------

    def _add_videos(self):
        paths = filedialog.askopenfilenames(
            title="Select video files",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv *.MP4 *.AVI"),
                       ("All files", "*.*")])
        for p in paths:
            self._enqueue(Path(p))

    def _add_folder(self):
        folder = filedialog.askdirectory(title="Select folder containing videos")
        if not folder:
            return
        exts = {".mp4", ".avi", ".mov", ".mkv"}
        for p in sorted(Path(folder).iterdir()):
            if p.suffix.lower() in exts:
                self._enqueue(p)

    def _enqueue(self, path: Path):
        if path in self._queue_rows:
            return
        if self._queue_empty_label.winfo_ismapped():
            self._queue_empty_label.pack_forget()

        row = ctk.CTkFrame(self._queue_scroll, fg_color="#1a1a22", corner_radius=4)
        row.pack(fill="x", padx=2, pady=2)
        row.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(row, text=path.name, font=("Segoe UI", 10), anchor="w").grid(
            row=0, column=0, sticky="ew", padx=8, pady=2)
        ctk.CTkLabel(row, text=str(path.parent), font=("Segoe UI", 8),
                     text_color="#555555", anchor="w").grid(
            row=1, column=0, sticky="ew", padx=8, pady=(0, 2))

        status_lbl = ctk.CTkLabel(row, text="queued", font=("Segoe UI", 9),
                                  text_color="#666666", width=90, anchor="e")
        status_lbl.grid(row=0, column=1, rowspan=2, padx=(4, 4))

        rm_btn = ctk.CTkButton(row, text="x", width=24, height=24,
                               fg_color="#3a1010", hover_color="#5a2020",
                               command=lambda p=path: self._remove_video(p))
        rm_btn.grid(row=0, column=2, rowspan=2, padx=(0, 4))

        row._status_lbl = status_lbl
        row._rm_btn = rm_btn
        self._queue_rows[path] = row
        self._videos.append(path)

    def _remove_video(self, path: Path):
        if self._running:
            return
        row = self._queue_rows.pop(path, None)
        if row:
            row.destroy()
        if path in self._videos:
            self._videos.remove(path)
        if not self._videos:
            self._queue_empty_label.pack(pady=20)

    def _clear_queue(self):
        if self._running:
            return
        for row in self._queue_rows.values():
            row.destroy()
        self._queue_rows.clear()
        self._videos.clear()
        self._queue_empty_label.pack(pady=20)

    def _set_video_status(self, path: Path, text: str, colour: str):
        row = self._queue_rows.get(path)
        if row:
            self.after(0, lambda r=row, t=text, c=colour: r._status_lbl.configure(
                text=t, text_color=c))

    # ------------------------------------------------------------------
    # Batch run
    # ------------------------------------------------------------------

    def _browse_output(self):
        d = filedialog.askdirectory(title="Select output directory")
        if d:
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, d)

    def _start_batch(self):
        if not self._videos:
            self._log("No videos queued. Add videos first.")
            return
        if self._running:
            return
        self._running = True
        self._cancel_flag.clear()
        self.run_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.status_callback("Batch running...")
        for p in self._videos:
            self._set_video_status(p, "queued", "#666666")
        threading.Thread(target=self._batch_thread, daemon=True).start()

    def _cancel_batch(self):
        self._cancel_flag.set()
        if self._process and self._process.poll() is None:
            self._process.terminate()
        self._log("\nCancelled by user.")
        self._on_batch_done(cancelled=True)

    def _on_batch_done(self, cancelled=False):
        self._running = False
        self._process = None
        msg = "Batch cancelled." if cancelled else "Batch complete."
        self.after(0, lambda: self.run_btn.configure(state="normal"))
        self.after(0, lambda: self.cancel_btn.configure(state="disabled"))
        self.after(0, lambda: self.status_callback(msg))
        self.after(0, lambda: self._progress_label.configure(text=msg))

    def _batch_thread(self):
        total = len(self._videos)
        analyzer = Path(__file__).parent.parent.parent / "record" / "video_analyzer.py"
        model = self.model_var.get()
        interval = self.interval_var.get()
        out_root = self.output_entry.get().strip()
        n_ok = 0

        for idx, video in enumerate(list(self._videos)):
            if self._cancel_flag.is_set():
                break

            self.after(0, lambda i=idx, t=total, v=video.name:
                       self._progress_label.configure(
                           text=f"Processing {i+1}/{t}: {v}"))
            self._set_video_status(video, "running...", "#ffcc44")
            self._log(f"\n{'─'*60}")
            self._log(f"[{idx+1}/{total}] {video.name}")

            output_dir = Path(out_root) if out_root else video.parent
            cmd = [
                sys.executable, str(analyzer),
                "--video",           str(video),
                "--model",           model,
                "--output-dir",      str(output_dir),
                "--detect-interval", str(interval),
            ]

            try:
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace", bufsize=1,
                )
                for line in self._process.stdout:
                    self._log(line.rstrip())
                self._process.wait()
                rc = self._process.returncode
            except Exception as exc:
                self._log(f"  Error launching subprocess: {exc}")
                rc = -1
            finally:
                self._process = None

            if self._cancel_flag.is_set():
                self._set_video_status(video, "cancelled", "#888888")
                break

            if rc == 0:
                n_ok += 1
                self._set_video_status(video, "done", "#44cc44")
                self._log(f"  Complete -> {output_dir}")
            else:
                self._set_video_status(video, f"failed ({rc})", "#ff5555")
                self._log(f"  Failed (exit {rc})")

        if not self._cancel_flag.is_set():
            self._log(f"\n{'='*60}")
            self._log(f"Batch finished: {n_ok}/{total} succeeded.")
            self._on_batch_done(cancelled=False)

    # ------------------------------------------------------------------
    # Log helpers
    # ------------------------------------------------------------------

    def _log(self, text: str):
        def _append():
            self._log_box.configure(state="normal")
            self._log_box.insert("end", text + "\n")
            self._log_box.see("end")
            self._log_box.configure(state="disabled")
        self.after(0, _append)

    def _clear_log(self):
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")
