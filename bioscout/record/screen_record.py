"""Screen recording utility with area selection, trimming, and preview capabilities."""

import cv2
import numpy as np
import pyautogui
from datetime import datetime
from pathlib import Path
import threading
import tkinter as tk
from tkinter import ttk
import ctypes


class ScreenRecorder:
    """Screen recording tool with interactive area selection and video trimming."""

    def __init__(self):
        self.recording = False
        self.record_thread = None
        self.area = None          # (left, top, width, height) in real screen coords
        self.root = None          # control panel Tk root
        self.area_overlay = None  # Toplevel showing dashed red border

        # StringVars — created when root is built
        self._area_label_var = None
        self._status_var = None

        # Button refs for enable/disable
        self._btn_start = None
        self._btn_stop = None
        self._fps_var = None
        self._audio_var = None  # StringVar: 'Off' / 'System audio' / 'Microphone'

    # ------------------------------------------------------------------ #
    #  Virtual screen helpers                                              #
    # ------------------------------------------------------------------ #
    def _get_virtual_screen(self):
        """Get virtual screen dimensions across all monitors."""
        u = ctypes.windll.user32
        return (
            u.GetSystemMetrics(76),  # SM_XVIRTUALSCREEN  (left edge, may be negative)
            u.GetSystemMetrics(77),  # SM_YVIRTUALSCREEN  (top edge)
            u.GetSystemMetrics(78),  # SM_CXVIRTUALSCREEN (total width across all monitors)
            u.GetSystemMetrics(79),  # SM_CYVIRTUALSCREEN (total height)
        )

    # ------------------------------------------------------------------ #
    #  Dashed red border overlay                                          #
    # ------------------------------------------------------------------ #
    def _show_area_overlay(self):
        """Draw a dashed red border over the selected area (always on top)."""
        self._hide_area_overlay()
        left, top, width, height = self.area

        ov = tk.Toplevel(self.root)
        ov.overrideredirect(True)
        ov.geometry(f"{width}x{height}+{left}+{top}")
        ov.attributes('-topmost', True)
        ov.attributes('-transparentcolor', 'black')   # black pixels become fully transparent
        ov.configure(bg='black')
        ov.lift()

        c = tk.Canvas(ov, bg='black', highlightthickness=0)
        c.pack(fill=tk.BOTH, expand=True)
        # Interior stays black (transparent); only the red outline is visible
        c.create_rectangle(2, 2, width - 3, height - 3,
                            outline='red', width=3, dash=(10, 5))
        self.area_overlay = ov

    def _hide_area_overlay(self):
        """Hide the area selection overlay."""
        if self.area_overlay:
            try:
                self.area_overlay.destroy()
            except Exception:
                pass
            self.area_overlay = None

    # ------------------------------------------------------------------ #
    #  Full-screen selection overlay                                       #
    # ------------------------------------------------------------------ #
    def _on_select(self):
        """Show a dark overlay across all monitors; click-drag to pick area."""
        self._hide_area_overlay()
        self.root.withdraw()           # hide control panel while selecting

        vx, vy, vw, vh = self._get_virtual_screen()
        result = [None]
        sx, sy = [0], [0]
        rect_id = [None]
        label_id = [None]

        sel = tk.Toplevel(self.root)
        sel.overrideredirect(True)
        sel.geometry(f"{vw}x{vh}+{vx}+{vy}")
        sel.attributes('-alpha', 0.40)
        sel.attributes('-topmost', True)
        sel.configure(bg='black')
        sel.lift()
        sel.focus_force()

        canvas = tk.Canvas(sel, bg='black', cursor='crosshair', highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        canvas.create_text(
            vw // 2, 28,
            text='Click and drag to select area   |   Esc to cancel',
            fill='white', font=('Arial', 13))

        def _clear():
            for item in (rect_id[0], label_id[0]):
                if item:
                    canvas.delete(item)

        def on_press(e):
            sx[0], sy[0] = e.x, e.y
            _clear()

        def on_drag(e):
            _clear()
            x0, y0, x1, y1 = sx[0], sy[0], e.x, e.y
            rect_id[0] = canvas.create_rectangle(
                x0, y0, x1, y1, outline='cyan', width=2)
            w, h = abs(x1 - x0), abs(y1 - y0)
            lx = (x0 + x1) // 2
            ly = (min(y0, y1) - 14) if min(y0, y1) > 20 else (max(y0, y1) + 14)
            label_id[0] = canvas.create_text(
                lx, ly, text=f'{w} × {h} px',
                fill='cyan', font=('Arial', 11, 'bold'))

        def on_release(e):
            left  = min(sx[0], e.x) + vx
            top   = min(sy[0], e.y) + vy
            right = max(sx[0], e.x) + vx
            bot   = max(sy[0], e.y) + vy
            w, h  = right - left, bot - top
            if w > 10 and h > 10:
                result[0] = (left, top, w, h)
            sel.destroy()

        canvas.bind('<ButtonPress-1>',   on_press)
        canvas.bind('<B1-Motion>',       on_drag)
        canvas.bind('<ButtonRelease-1>', on_release)
        sel.bind('<Escape>', lambda e: sel.destroy())

        self.root.wait_window(sel)     # nested event loop until overlay closes
        self.root.deiconify()          # bring control panel back

        if result[0]:
            self.area = result[0]
            left, top, w, h = self.area
            self._area_label_var.set(f"Area: ({left}, {top})   {w} × {h} px")
            self._btn_start.config(state=tk.NORMAL)
            self._status_var.set("Ready — press Start to record")
            self._show_area_overlay()
        else:
            # Keep previous area if one was already selected
            if self.area:
                self._show_area_overlay()
            else:
                self._area_label_var.set("No area selected")
                self._status_var.set("Select an area to begin")

    # ------------------------------------------------------------------ #
    #  Recording                                                           #
    # ------------------------------------------------------------------ #
    def _record(self):
        """Recording loop — runs in a daemon background thread."""
        left, top, width, height = self.area

        output_dir = Path.home() / "Videos"
        output_dir.mkdir(exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"screen_record_{ts}.mp4"

        fps = float(self._fps_var.get())
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

        audio_stream = None
        audio_data = []
        audio_samplerate = 44100
        audio_source = self._audio_var.get()

        if audio_source != 'Off':
            try:
                import sounddevice as sd

                def _audio_cb(indata, _frames, _time, _status):
                    audio_data.append(indata.copy())

                if audio_source == 'System audio':
                    # WASAPI loopback — captures whatever is playing on the default output
                    out_idx = sd.default.device[1]
                    out_info = sd.query_devices(out_idx)
                    audio_samplerate = int(out_info['default_samplerate'])
                    audio_stream = sd.InputStream(
                        device=out_idx,
                        samplerate=audio_samplerate,
                        channels=2,
                        dtype='float32',
                        callback=_audio_cb,
                        extra_settings=sd.WasapiSettings(loopback=True))
                else:  # Microphone
                    in_idx = sd.default.device[0]
                    in_info = sd.query_devices(in_idx)
                    audio_samplerate = int(in_info['default_samplerate'])
                    channels = min(2, max(1, int(in_info['max_input_channels'])))
                    audio_stream = sd.InputStream(
                        samplerate=audio_samplerate,
                        channels=channels,
                        dtype='float32',
                        callback=_audio_cb)

                audio_stream.start()
            except ImportError:
                self.root.after(0, self._status_var.set,
                                "Audio unavailable — pip install sounddevice")
            except Exception as exc:
                self.root.after(0, self._status_var.set, f"Audio error: {exc}")

        try:
            while self.recording:
                img = pyautogui.screenshot(region=(left, top, width, height))
                frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                out.write(frame)
        finally:
            out.release()
            if audio_stream is not None:
                audio_stream.stop()
                audio_stream.close()

        final_path = output_path
        if audio_data:
            self.root.after(0, self._status_var.set, "Merging audio…")
            wav_path = output_dir / f"screen_record_{ts}_audio.wav"
            self._write_wav(wav_path, audio_data, audio_samplerate)
            merged_path = output_dir / f"screen_record_{ts}_final.mp4"
            if self._merge_audio_video(output_path, wav_path, merged_path):
                output_path.unlink(missing_ok=True)
                wav_path.unlink(missing_ok=True)
                final_path = merged_path
            else:
                # no merger available — keep WAV alongside video
                wav_path.replace(output_dir / f"screen_record_{ts}.wav")

        self.root.after(0, self._on_recording_done, final_path)

    @staticmethod
    def _write_wav(path, audio_data, samplerate):
        """Write captured float32 audio chunks to a 16-bit WAV file."""
        import wave
        audio_array = np.concatenate(audio_data, axis=0)
        audio_int16 = (np.clip(audio_array, -1.0, 1.0) * 32767).astype(np.int16)
        channels = audio_array.shape[1] if audio_array.ndim > 1 else 1
        with wave.open(str(path), 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(2)
            wf.setframerate(samplerate)
            wf.writeframes(audio_int16.tobytes())

    @staticmethod
    def _merge_audio_video(video_path, wav_path, out_path):
        """Merge silent video with WAV audio. Returns True on success."""
        import subprocess
        try:
            result = subprocess.run(
                ['ffmpeg', '-y',
                 '-i', str(video_path), '-i', str(wav_path),
                 '-c:v', 'copy', '-c:a', 'aac', '-shortest',
                 str(out_path)],
                capture_output=True, timeout=300)
            if result.returncode == 0:
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        try:
            from moviepy.editor import VideoFileClip, AudioFileClip
            video = VideoFileClip(str(video_path))
            audio = AudioFileClip(str(wav_path))
            video.set_audio(audio).write_videofile(str(out_path), logger=None)
            video.close()
            audio.close()
            return True
        except ImportError:
            pass

        return False

    def _on_recording_done(self, path):
        """Handle completion of recording."""
        self._status_var.set(f"Saved → {path.name}")
        self._btn_start.config(state=tk.NORMAL)
        self._btn_stop.config(state=tk.DISABLED)
        self._show_area_overlay()   # restore red border after recording stops

    # ------------------------------------------------------------------ #
    #  Button handlers                                                     #
    # ------------------------------------------------------------------ #
    def _on_start(self):
        """Start recording."""
        if self.recording or self.area is None:
            return
        self._hide_area_overlay()   # don't capture the red border in the video
        self.recording = True
        self._btn_start.config(state=tk.DISABLED)
        self._btn_stop.config(state=tk.NORMAL)
        left, top, w, h = self.area
        self._status_var.set(f"Recording {w}×{h}…")
        self.record_thread = threading.Thread(target=self._record, daemon=True)
        self.record_thread.start()

    def _on_stop(self):
        """Stop recording."""
        if not self.recording:
            return
        self.recording = False
        self._status_var.set("Stopping…")
        self._btn_stop.config(state=tk.DISABLED)

    def _on_trim(self):
        """Open trim dialog with video preview and frame-level trim sliders."""
        from tkinter import filedialog, messagebox
        try:
            from PIL import Image, ImageTk
        except ImportError:
            messagebox.showerror(
                "Missing dependency",
                "Pillow is required for video preview.\nInstall with:  pip install Pillow",
                parent=self.root)
            return

        PREV_W, PREV_H = 560, 315   # 16:9 preview size

        dlg = tk.Toplevel(self.root)
        dlg.title("Trim Video")
        dlg.resizable(True, False)
        dlg.attributes('-topmost', True)
        dlg.grab_set()

        # ---- internal state ----
        _cap   = [None]
        _total = [1]
        _fps   = [20.0]
        _photo = [None]   # strong ref — prevents GC

        def _release():
            if _cap[0]:
                _cap[0].release()
                _cap[0] = None

        def _show_frame(idx):
            if not _cap[0]:
                return
            idx = max(0, min(idx, _total[0] - 1))
            _cap[0].set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = _cap[0].read()
            if not ret:
                return
            h, w = frame.shape[:2]
            scale = min(PREV_W / w, PREV_H / h, 1.0)
            nw, nh = int(w * scale), int(h * scale)
            rgb = cv2.cvtColor(cv2.resize(frame, (nw, nh)), cv2.COLOR_BGR2RGB)
            _photo[0] = ImageTk.PhotoImage(Image.fromarray(rgb))
            preview_canvas.delete('all')
            preview_canvas.create_image(PREV_W // 2, PREV_H // 2,
                                        anchor='center', image=_photo[0])
            t = idx / _fps[0]
            total_t = _total[0] / _fps[0]
            frame_info_var.set(
                f"Frame  {idx + 1} / {_total[0]}   ·   {t:.2f}s  /  {total_t:.1f}s total")

        def _update_trim_bar(*_):
            s = scrub_start_var.get()
            e = scrub_end_var.get()
            n = max(1, _total[0])
            W = trim_bar_canvas.winfo_width() or 560
            H = 24
            trim_bar_canvas.delete('all')
            # full bar
            trim_bar_canvas.create_rectangle(0, 5, W, H - 5, fill='#555', outline='')
            # selected region
            x0 = int(s / n * W)
            x1 = int(e / n * W)
            trim_bar_canvas.create_rectangle(x0, 3, x1, H - 3, fill='#1976d2', outline='')
            # scrub cursor
            xc = int(scrub_var.get() / n * W)
            trim_bar_canvas.create_line(xc, 0, xc, H, fill='white', width=2)
            # time labels
            s_t, e_t = s / _fps[0], e / _fps[0]
            trim_bar_canvas.create_text(
                x0 + 4, H // 2, text=f"{s_t:.1f}s", anchor='w',
                fill='white', font=('Arial', 7))
            trim_bar_canvas.create_text(
                max(x1 - 4, x0 + 30), H // 2, text=f"{e_t:.1f}s", anchor='e',
                fill='white', font=('Arial', 7))
            trim_bar_canvas.create_text(
                W // 2, H // 2, text=f"Δ {e_t - s_t:.2f}s",
                anchor='center', fill='white', font=('Arial', 7, 'bold'))

        def _load_video(path):
            _release()
            c = cv2.VideoCapture(str(path))
            if not c.isOpened():
                frame_info_var.set("Could not open video.")
                return
            _cap[0]   = c
            _total[0] = max(1, int(c.get(cv2.CAP_PROP_FRAME_COUNT)))
            _fps[0]   = c.get(cv2.CAP_PROP_FPS) or 20.0
            n = _total[0] - 1
            for sl in (scrub_slider, start_slider, end_slider):
                sl.config(to=n)
            scrub_var.set(0)
            scrub_start_var.set(0)
            scrub_end_var.set(n)
            start_time_var.set("0.00s")
            end_time_var.set(f"{n / _fps[0]:.2f}s")
            trim_btn.config(state=tk.NORMAL)
            _show_frame(0)
            dlg.after(60, _update_trim_bar)

        # ---- file row ----
        fr = tk.Frame(dlg)
        fr.pack(fill='x', padx=8, pady=4)
        tk.Label(fr, text="File:").pack(side='left')
        file_var = tk.StringVar()
        tk.Entry(fr, textvariable=file_var, width=46).pack(side='left', padx=4)

        def browse():
            p = filedialog.askopenfilename(
                title="Select video", parent=dlg,
                initialdir=str(Path.home() / "Videos"),
                filetypes=[("MP4 files", "*.mp4"), ("All files", "*.*")])
            if p:
                file_var.set(p)
                _load_video(p)

        tk.Button(fr, text="Browse…", command=browse).pack(side='left')

        # ---- preview canvas ----
        preview_canvas = tk.Canvas(dlg, width=PREV_W, height=PREV_H,
                                   bg='#111', highlightthickness=0)
        preview_canvas.pack(padx=8, pady=(0, 2))

        frame_info_var = tk.StringVar(value="No video loaded — browse to a file above")
        tk.Label(dlg, textvariable=frame_info_var,
                 font=('Arial', 9), fg='gray').pack()

        # ---- scrub row ----
        scrub_row = tk.Frame(dlg)
        scrub_row.pack(fill='x', padx=8, pady=(4, 0))

        def prev_frame():
            v = max(0, scrub_var.get() - 1)
            scrub_var.set(v); _show_frame(v); _update_trim_bar()

        def next_frame():
            v = min(_total[0] - 1, scrub_var.get() + 1)
            scrub_var.set(v); _show_frame(v); _update_trim_bar()

        tk.Button(scrub_row, text="◄", width=3, command=prev_frame).pack(side='left')

        scrub_var = tk.IntVar(value=0)
        scrub_slider = tk.Scale(scrub_row, variable=scrub_var, from_=0, to=100,
                                orient='horizontal', showvalue=False, length=1,
                                command=lambda v: (
                                    _show_frame(int(float(v))), _update_trim_bar()))
        scrub_slider.pack(side='left', fill='x', expand=True)
        tk.Button(scrub_row, text="►", width=3, command=next_frame).pack(side='left')

        # ---- trim sliders ----
        start_time_var  = tk.StringVar(value="0.00s")
        end_time_var    = tk.StringVar(value="0.00s")
        scrub_start_var = tk.IntVar(value=0)
        scrub_end_var   = tk.IntVar(value=100)

        def _clamp_start(v):
            f = int(float(v))
            if f > scrub_end_var.get():
                scrub_start_var.set(scrub_end_var.get()); f = scrub_end_var.get()
            start_time_var.set(f"{f / _fps[0]:.2f}s")
            _update_trim_bar()

        def _clamp_end(v):
            f = int(float(v))
            if f < scrub_start_var.get():
                scrub_end_var.set(scrub_start_var.get()); f = scrub_start_var.get()
            end_time_var.set(f"{f / _fps[0]:.2f}s")
            _update_trim_bar()

        # Start row
        sr = tk.Frame(dlg)
        sr.pack(fill='x', padx=8, pady=(6, 0))
        tk.Label(sr, text="▶ Start:", width=8, anchor='w').pack(side='left')
        start_slider = tk.Scale(sr, variable=scrub_start_var, from_=0, to=100,
                                orient='horizontal', showvalue=False, length=1,
                                command=_clamp_start)
        start_slider.pack(side='left', fill='x', expand=True)
        tk.Label(sr, textvariable=start_time_var, width=7, anchor='e',
                 font=('Arial', 9, 'bold')).pack(side='left', padx=2)
        tk.Button(sr, text="Set ◄", width=6,
                  command=lambda: (
                      scrub_start_var.set(scrub_var.get()),
                      start_time_var.set(f"{scrub_var.get() / _fps[0]:.2f}s"),
                      _update_trim_bar())
                  ).pack(side='left', padx=4)

        # End row
        er = tk.Frame(dlg)
        er.pack(fill='x', padx=8, pady=(2, 4))
        tk.Label(er, text="⏹ End:", width=8, anchor='w').pack(side='left')
        end_slider = tk.Scale(er, variable=scrub_end_var, from_=0, to=100,
                              orient='horizontal', showvalue=False, length=1,
                              command=_clamp_end)
        end_slider.pack(side='left', fill='x', expand=True)
        tk.Label(er, textvariable=end_time_var, width=7, anchor='e',
                 font=('Arial', 9, 'bold')).pack(side='left', padx=2)
        tk.Button(er, text="Set ►", width=6,
                  command=lambda: (
                      scrub_end_var.set(scrub_var.get()),
                      end_time_var.set(f"{scrub_var.get() / _fps[0]:.2f}s"),
                      _update_trim_bar())
                  ).pack(side='left', padx=4)

        # ---- timeline bar ----
        trim_bar_canvas = tk.Canvas(dlg, height=24, bg='#333', highlightthickness=0)
        trim_bar_canvas.pack(fill='x', padx=8, pady=2)
        trim_bar_canvas.bind('<Configure>', _update_trim_bar)

        # ---- status + action buttons ----
        trim_status_var = tk.StringVar(value="")
        tk.Label(dlg, textvariable=trim_status_var,
                 fg='gray', font=('Arial', 9)).pack(pady=(4, 0))

        act = tk.Frame(dlg)
        act.pack(pady=6)

        def do_trim():
            if not _cap[0]:
                return
            in_path = Path(file_var.get().strip())
            start_f = scrub_start_var.get()
            end_f   = scrub_end_var.get()
            if end_f <= start_f:
                trim_status_var.set("End must be after start.")
                return
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = in_path.parent / f"{in_path.stem}_trim_{ts}.mp4"
            trim_btn.config(state=tk.DISABLED)
            trim_status_var.set("Trimming…")
            threading.Thread(
                target=self._do_trim,
                args=(in_path, start_f / _fps[0], end_f / _fps[0],
                      out_path, trim_status_var, trim_btn),
                daemon=True).start()

        trim_btn = tk.Button(act, text="✂  Trim", width=12, command=do_trim,
                             state=tk.DISABLED, bg='#1565c0', fg='white',
                             activebackground='#0d47a1', activeforeground='white')
        trim_btn.pack(side='left', padx=6)
        tk.Button(act, text="Close", width=8,
                  command=lambda: (_release(), dlg.destroy())).pack(side='left', padx=6)

        dlg.protocol("WM_DELETE_WINDOW", lambda: (_release(), dlg.destroy()))

    def _do_trim(self, in_path, start_s, end_s, out_path, status_var, btn):
        """Trim in_path [start_s, end_s) and write to out_path (background thread)."""
        cap = cv2.VideoCapture(str(in_path))
        fps   = cap.get(cv2.CAP_PROP_FPS) or 20.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        w     = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h     = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        start_f = int(start_s * fps)
        end_f   = int(end_s * fps) if end_s is not None else total
        end_f   = min(end_f, total)

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(out_path), fourcc, fps, (w, h))
        try:
            for _ in range(max(0, end_f - start_f)):
                ret, frame = cap.read()
                if not ret:
                    break
                out.write(frame)
        finally:
            cap.release()
            out.release()

        self.root.after(0, status_var.set, f"Saved → {out_path.name}")
        self.root.after(0, btn.config, {'state': tk.NORMAL})

    def _on_quit(self):
        """Quit the recorder."""
        self.recording = False
        self._hide_area_overlay()
        self.root.destroy()

    # ------------------------------------------------------------------ #
    #  Main entry point                                                    #
    # ------------------------------------------------------------------ #
    def run(self):
        """Launch the screen recorder control panel."""
        self.root = tk.Tk()
        self.root.title("Screen Recorder")
        self.root.resizable(False, False)
        self.root.attributes('-topmost', True)

        self._area_label_var = tk.StringVar(value="No area selected")
        self._status_var     = tk.StringVar(value="Select an area to begin")

        pad = dict(padx=12, pady=5)

        tk.Label(self.root, textvariable=self._area_label_var,
                 font=('Arial', 10, 'bold')).pack(**pad)

        # FPS row
        fps_frame = tk.Frame(self.root)
        fps_frame.pack(padx=12, pady=(0, 2))
        tk.Label(fps_frame, text="FPS:", font=('Arial', 9)).pack(side=tk.LEFT)
        self._fps_var = tk.StringVar(value='20')
        fps_spin = tk.Spinbox(fps_frame, textvariable=self._fps_var,
                              values=(5, 10, 15, 20, 24, 30, 60),
                              width=5, font=('Arial', 9), state='readonly')
        fps_spin.pack(side=tk.LEFT, padx=4)

        tk.Label(fps_frame, text="Audio:", font=('Arial', 9)).pack(side=tk.LEFT, padx=(12, 0))
        self._audio_var = tk.StringVar(value='Off')
        ttk.Combobox(fps_frame, textvariable=self._audio_var,
                     values=['Off', 'System audio', 'Microphone'],
                     width=13, state='readonly').pack(side=tk.LEFT, padx=4)

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(padx=12, pady=4)

        tk.Button(btn_frame, text="Select Area", width=13,
                  command=self._on_select).grid(row=0, column=0, padx=4)

        self._btn_start = tk.Button(btn_frame, text="▶  Start", width=11,
                                    state=tk.DISABLED, command=self._on_start,
                                    bg='#2e7d32', fg='white',
                                    activebackground='#1b5e20', activeforeground='white')
        self._btn_start.grid(row=0, column=1, padx=4)

        self._btn_stop = tk.Button(btn_frame, text="■  Stop", width=11,
                                   state=tk.DISABLED, command=self._on_stop,
                                   bg='#c62828', fg='white',
                                   activebackground='#7f0000', activeforeground='white')
        self._btn_stop.grid(row=0, column=2, padx=4)

        tk.Button(btn_frame, text="Quit", width=8,
                  command=self._on_quit).grid(row=0, column=3, padx=4)

        tk.Button(btn_frame, text="✂  Trim Video", width=15,
                  command=self._on_trim).grid(row=1, column=0, columnspan=4, pady=(6, 0))

        tk.Label(self.root, textvariable=self._status_var,
                 font=('Arial', 9), fg='gray').pack(**pad)

        self.root.protocol("WM_DELETE_WINDOW", self._on_quit)
        self.root.mainloop()


if __name__ == "__main__":
    recorder = ScreenRecorder()
    recorder.run()
