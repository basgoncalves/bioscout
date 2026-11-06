"""MRI2MSK GUI - BioScout-style (dark CustomTkinter).

Start with:  bioscout model mri2msk gui

Left sidebar (logo, pages, logos), participant bar, page area and a console.
Pages: Model Warping (steps 1-8) and Post-Warp Pipeline (BioScout session:
export C3D, scale, IK, ID, SO, JRA, JCF contributions).
Steps run in a background thread; a timer re-checks the participant folder
every few seconds (landmarks saved, warped model exported, ...).
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    import customtkinter as ctk
except ImportError as e:  # pragma: no cover
    raise SystemExit("The MRI2MSK GUI needs CustomTkinter:  pip install customtkinter") from e

from . import __version__
from . import pipeline as pl
from . import ui_theme as T

PKG_DIR = Path(__file__).resolve().parent
REPO_DIR = PKG_DIR                       # the docs (README.md, WORKFLOW.md) sit beside this file
# the generic base model: MRI2MSK_BASE_MODEL, else the MRI2MSK (MATLAB) folder next to the
# current folder / on the Desktop (the package now lives inside bioscout, not beside MRI2MSK)
_BM = Path("BaseModel_Lernagopal") / "LernagopalLaiUhlrich2025_CGM2.osim"
_BASE_CANDIDATES = ([Path(os.environ["MRI2MSK_BASE_MODEL"])] if os.environ.get("MRI2MSK_BASE_MODEL") else []) + [
    Path.cwd() / _BM, Path.cwd() / "MRI2MSK" / _BM, Path.cwd().parent / "MRI2MSK" / _BM,
    Path.home() / "Desktop" / "WilliOSC" / _BM, Path.home() / "Desktop" / "WilliOSC" / "MRI2MSK" / _BM]
DEFAULT_BASE_MODEL = next((p for p in _BASE_CANDIDATES if p.is_file()), _BASE_CANDIDATES[-1])
CONFIG_NAME = "warpingConfig.json"
AUTO_CHECK_MS = 3000


# =========================================================================== OpenSim Creator
def find_opensim_creator() -> str | None:
    cands = []
    if sys.platform.startswith("win"):
        cands = [Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "OpenSimCreator" / "bin" / "osc.exe",
                 Path(os.environ.get("PROGRAMFILES", "")) / "OpenSimCreator" / "bin" / "osc.exe",
                 Path(r"C:\Program Files\OpenSimCreator\bin\osc.exe")]
    elif sys.platform == "darwin":
        cands = [Path("/Applications/OpenSimCreator.app/Contents/MacOS/osc"),
                 Path.home() / "Applications/OpenSimCreator.app/Contents/MacOS/osc"]
    else:
        cands = [Path("/usr/local/bin/osc"), Path("/opt/OpenSimCreator/bin/osc")]
    for c in cands:
        if c.is_file():
            return str(c)
    return shutil.which("osc")


def open_path(p):
    p = str(p)
    if sys.platform.startswith("win"):
        os.startfile(p)  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", p])
    else:
        subprocess.Popen(["xdg-open", p])


# =========================================================================== log redirection
class _QueueWriter(io.TextIOBase):
    def __init__(self, q: queue.Queue):
        self.q = q

    def write(self, s):
        if s.strip():
            for line in s.rstrip().splitlines():
                self.q.put(("log", line))
        return len(s)


# =========================================================================== steps
# key, label, button text, kind ('auto' | 'user'), optional flag
STEPS = [
    ("s1", "1  Rescale & align bones", "Run", "auto", None),
    ("s2", "2  Align skin & add to base model", "Run", "auto", "skin"),
    ("s3", "3  Create landmarks (Mesh Warper)", "Helper", "user", None),
    ("s4", "4  Create warp setup", "Run", "auto", None),
    ("s5", "5  Warp model", "Run", "auto", None),
    ("s6", "6  Replace skin in warped model", "Run", "auto", "skin"),
    ("s7", "7  Correct torsion & mass centres", "Run", "auto", None),
    ("s8", "8  Set mechanical knee axis", "Run", "auto", "mka"),
]
PREREQ = {"s1": [], "s2": ["s1"], "s3": ["s1"], "s4": ["s1", "s3"], "s5": ["s4"],
          "s6": ["s5"], "s7": ["s5"], "s8": ["s7"]}
PAGES = (("warp", "Model Warping"), ("post", "Post-Warp Pipeline"), ("help", "Help"))


class MRI2MSKApp:
    def __init__(self, root):
        self.root = root
        self.q: queue.Queue = queue.Queue()
        self.busy = False
        self._chain = None
        self._lm_counts: dict[str, int] = {}
        root.title("MRI2MSK")
        root.geometry("1360x880")
        root.minsize(1120, 720)
        root.configure(fg_color=T.BG)
        T.set_app_icon(root)
        T.style_treeview(root)

        self.var_folder = tk.StringVar()
        self.var_name = tk.StringVar()
        self.var_model = tk.StringVar(value=str(DEFAULT_BASE_MODEL) if DEFAULT_BASE_MODEL.is_file() else "")
        self.var_basefolder = tk.StringVar()
        self.var_template = tk.StringVar()
        self.var_skin = tk.BooleanVar(value=False)
        self.var_mka = tk.BooleanVar(value=True)

        self._build()
        self.var_model.trace_add("write", lambda *_: self._refresh())
        self.show_page("warp")
        self._refresh()
        self.root.after(100, self._poll_queue)
        self.root.after(AUTO_CHECK_MS, self._auto_check)
        self.log("Ready. Select a participant folder to start.")

    # ------------------------------------------------------------------ layout
    def _build(self):
        r = self.root
        r.grid_columnconfigure(1, weight=1)
        r.grid_rowconfigure(1, weight=1)

        # ---- sidebar
        sb = ctk.CTkFrame(r, fg_color=T.SIDEBAR, corner_radius=0, width=210)
        sb.grid(row=0, column=0, rowspan=3, sticky="nsw")
        sb.grid_propagate(False)
        logo = T.image("icon_64.png")
        head = ctk.CTkFrame(sb, fg_color="transparent")
        head.pack(fill="x", padx=14, pady=(18, 6))
        if logo:
            ctk.CTkLabel(head, image=logo, text="").pack(side="left")
        tbox = ctk.CTkFrame(head, fg_color="transparent")
        tbox.pack(side="left", padx=(10, 0))
        T.label(tbox, "MRI2MSK", 20, weight="bold").pack(anchor="w")
        T.label(tbox, "MRI → MSK model", 11, T.MUTED).pack(anchor="w")
        ctk.CTkFrame(sb, height=1, fg_color=T.CARD_BORDER).pack(fill="x", padx=14, pady=(10, 10))
        self.nav = {}
        for key, text in PAGES:
            b = ctk.CTkButton(sb, text=text, anchor="w", height=36, corner_radius=8, font=T.f(13),
                              fg_color="transparent", hover_color=T.NEUTRAL, text_color=T.TEXT,
                              command=lambda k=key: self.show_page(k))
            b.pack(fill="x", padx=10, pady=2)
            self.nav[key] = b
        ctk.CTkFrame(sb, fg_color="transparent").pack(fill="both", expand=True)
        lg = ctk.CTkFrame(sb, fg_color="#f2f2f2", corner_radius=8)
        lg.pack(fill="x", padx=12, pady=(0, 8))
        for name in ("univie_h40.png", "osc_logo_h40.png"):
            im = T.image(name, 34)
            if im:
                ctk.CTkLabel(lg, image=im, text="").pack(side="left", padx=8, pady=6)
        T.label(sb, f"v{__version__}  ·  Python", 10, T.MUTED).pack(anchor="w", padx=16, pady=(0, 12))

        # ---- participant bar
        tb = ctk.CTkFrame(r, fg_color=T.TOPBAR, corner_radius=0, height=56)
        tb.grid(row=0, column=1, sticky="ew")
        tb.grid_columnconfigure(1, weight=1)
        T.label(tb, "Participant", 12, T.MUTED).grid(row=0, column=0, padx=(16, 8), pady=12)
        T.entry(tb, self.var_folder, 400).grid(row=0, column=1, sticky="ew", pady=12)
        T.button(tb, "Browse", self._browse_folder, "primary", 80).grid(row=0, column=2, padx=6)
        T.label(tb, "Name", 12, T.MUTED).grid(row=0, column=3, padx=(14, 6))
        T.entry(tb, self.var_name, 110).grid(row=0, column=4)
        T.button(tb, "Load config", self._load_config, "neutral", 96).grid(row=0, column=5, padx=(14, 4))
        T.button(tb, "Save config", self._save_config, "neutral", 96).grid(row=0, column=6, padx=(0, 16))

        # ---- pages
        self.page_host = ctk.CTkFrame(r, fg_color=T.BG, corner_radius=0)
        self.page_host.grid(row=1, column=1, sticky="nsew", padx=14, pady=(12, 6))
        self.page_host.grid_columnconfigure(0, weight=1)
        self.page_host.grid_rowconfigure(0, weight=1)
        self.pages = {}
        for key, _ in PAGES:
            pg = ctk.CTkFrame(self.page_host, fg_color="transparent")
            pg.grid(row=0, column=0, sticky="nsew")
            self.pages[key] = pg
        self._build_warp_page(self.pages["warp"])
        from .gui_postwarp import PostWarpTab
        self.post = PostWarpTab(self, self.pages["post"])
        self._build_help_page(self.pages["help"])

        # ---- console
        con = ctk.CTkFrame(r, fg_color=T.SIDEBAR, corner_radius=10)
        con.grid(row=2, column=1, sticky="nsew", padx=14, pady=(0, 12))
        con.grid_columnconfigure(0, weight=1)
        hdr = ctk.CTkFrame(con, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=10, pady=(6, 0))
        T.label(hdr, "Console Output", 12, weight="bold").pack(side="left")
        T.button(hdr, "Clear", self._clear_log, "neutral", 60).pack(side="right")
        self.txt = ctk.CTkTextbox(con, height=150, fg_color=T.BG, text_color=T.TEXT, corner_radius=6,
                                  font=ctk.CTkFont(family=T.MONO, size=11), wrap="word")
        self.txt.grid(row=1, column=0, sticky="nsew", padx=10, pady=(4, 10))
        self.txt.tag_config("err", foreground=T.ST_ERR)
        self.txt.tag_config("ok", foreground=T.ST_DONE)
        self.txt.tag_config("ts", foreground=T.MUTED)
        self.txt.configure(state="disabled")

    def _build_warp_page(self, pg):
        pg.grid_columnconfigure(0, weight=1)
        pg.grid_rowconfigure(1, weight=1)
        # configuration card
        cfgc = T.card(pg, "Configuration")
        cfgc.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        b = cfgc.body
        b.grid_columnconfigure(1, weight=1)
        rows = [("Base model (.osim)", self.var_model, self._browse_model),
                ("Base folder", self.var_basefolder, None),
                ("Warp template", self.var_template, None)]
        for i, (lab, var, cmd) in enumerate(rows):
            T.label(b, lab, 12, T.MUTED).grid(row=i, column=0, sticky="w", padx=(0, 10), pady=3)
            T.entry(b, var, readonly=cmd is None).grid(row=i, column=1, sticky="ew", pady=3)
            if cmd:
                T.button(b, "Browse", cmd, "primary", 80).grid(row=i, column=2, padx=(8, 0))
        opt = ctk.CTkFrame(b, fg_color="transparent")
        opt.grid(row=len(rows), column=1, sticky="w", pady=(6, 0))
        ctk.CTkSwitch(opt, text="Include skin", variable=self.var_skin, command=self._refresh,
                      font=T.f(12), progress_color=T.ACCENT).pack(side="left")
        ctk.CTkSwitch(opt, text="Set mechanical knee axis", variable=self.var_mka, command=self._refresh,
                      font=T.f(12), progress_color=T.ACCENT).pack(side="left", padx=20)

        # steps + preview
        lower = ctk.CTkFrame(pg, fg_color="transparent")
        lower.grid(row=1, column=0, sticky="nsew")
        lower.grid_columnconfigure(0, weight=1)
        lower.grid_rowconfigure(0, weight=1)
        wf = T.card(lower, "Workflow Steps")
        wf.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        g = wf.body
        g.grid_columnconfigure(0, weight=1)
        self.rows = {}
        for i, (key, text, btn, kind, _) in enumerate(STEPS):
            T.label(g, text, 13).grid(row=i, column=0, sticky="w", pady=4)
            run = T.button(g, btn, lambda k=key: self._run_step(k), "primary", 84)
            run.grid(row=i, column=1, padx=4)
            view = T.button(g, "View model", lambda k=key: self._view(k), "neutral", 96)
            view.grid(row=i, column=2, padx=4)
            st = T.label(g, "Not started", 12, T.ST_IDLE, width=150)
            st.grid(row=i, column=3, sticky="w", padx=(8, 0))
            self.rows[key] = dict(run=run, view=view, status=st)
        T.button(g, "▶  Run all automatic steps up to the next user step", self._run_until_user,
                 "success", 340).grid(row=len(STEPS), column=0, columnspan=4, sticky="w", pady=(12, 0))

        pv = T.card(lower, "Warped model")
        pv.grid(row=0, column=1, sticky="ns")
        im = T.image("warped_preview.png", 300)
        if im:
            ctk.CTkLabel(pv.body, image=im, text="").pack(padx=6, pady=(0, 6))
        T.label(pv.body, "MRI bones → personalised\nOpenSim model", 11, T.MUTED, justify="center").pack()

    def _build_help_page(self, pg):
        c = T.card(pg, "Help")
        c.pack(fill="both", expand=True)
        T.label(c.body, "Step-by-step guide: WORKFLOW.md (button below; in bioscout/model/mri2msk).\n"
                        "Model Warping: steps 1-8 build the MRI-personalised model.\n"
                        "Post-Warp Pipeline: BioScout session - export C3D, scale, IK, ID, SO, JRA, "
                        "JCF muscle contributions.", 12, justify="left").pack(anchor="w", pady=(0, 10))
        row = ctk.CTkFrame(c.body, fg_color="transparent")
        row.pack(anchor="w")
        T.button(row, "Open WORKFLOW.md", lambda: self._open_doc("WORKFLOW.md"), "primary", 150).pack(side="left")
        T.button(row, "Open README", lambda: self._open_doc("README.md"), "neutral", 120).pack(side="left", padx=8)

    def show_page(self, key):
        self.pages[key].tkraise()
        for k, b in self.nav.items():
            b.configure(fg_color=T.ACCENT if k == key else "transparent")
        if key == "post":
            self.post.refresh()

    # ------------------------------------------------------------------ logging
    def log(self, msg, tag=None):
        self.txt.configure(state="normal")
        self.txt.insert("end", f"[{datetime.now():%H:%M:%S}] ", "ts")
        self.txt.insert("end", f"{msg}\n", tag)
        self.txt.see("end")
        self.txt.configure(state="disabled")

    def _clear_log(self):
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.configure(state="disabled")

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log":
                    self.log(payload)
                elif kind == "done":
                    key, ok, msg = payload
                    self.busy = False
                    self.log(msg, "ok" if ok else "err")
                    self._refresh()
                    if ok and self._chain:
                        self._continue_chain()
                    else:
                        self._chain = None
                    if not ok:
                        messagebox.showerror("MRI2MSK", msg.splitlines()[0])
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    # ------------------------------------------------------------------ config
    def cfg(self) -> pl.Config | None:
        folder, model = self.var_folder.get().strip(), self.var_model.get().strip()
        if not folder or not model:
            return None
        return pl.Config(folder, model, participant_name=self.var_name.get().strip() or None,
                         include_skin=self.var_skin.get())

    def _browse_folder(self):
        d = filedialog.askdirectory(title="Select participant folder")
        if d:
            self.set_participant(d)

    def set_participant(self, d):
        self.var_folder.set(d)
        self.var_name.set(Path(d).name)
        cfgfile = Path(d) / CONFIG_NAME
        if cfgfile.is_file():
            self._apply_config(json.loads(cfgfile.read_text()))
            self.log(f"Loaded {CONFIG_NAME} from participant folder.")
        self.var_skin.set((Path(d) / "stls" / "skin").is_dir() or self.var_skin.get())
        self.post.autodetect(quiet=True)
        self._refresh()
        self.log(f"Participant folder: {d}")

    def _browse_model(self):
        f = filedialog.askopenfilename(title="Select base model", filetypes=[("OpenSim model", "*.osim")])
        if f:
            self.var_model.set(f)

    def _config_dict(self):
        d = dict(participantFolder=self.var_folder.get(), participantName=self.var_name.get(),
                 baseModelFile=self.var_model.get(), includeSkin=self.var_skin.get(),
                 includeMKA=self.var_mka.get())
        d.update(self.post.config_dict())
        return d

    def _apply_config(self, d):
        self.var_folder.set(d.get("participantFolder", self.var_folder.get()))
        self.var_name.set(d.get("participantName", self.var_name.get()))
        self.var_model.set(d.get("baseModelFile", self.var_model.get()))
        self.var_skin.set(bool(d.get("includeSkin", self.var_skin.get())))
        self.var_mka.set(bool(d.get("includeMKA", self.var_mka.get())))
        if hasattr(self, "post"):
            self.post.apply_config(d)

    def _save_config(self):
        init = self.var_folder.get() or "."
        f = filedialog.asksaveasfilename(initialdir=init, initialfile=CONFIG_NAME,
                                         defaultextension=".json", filetypes=[("JSON", "*.json")])
        if f:
            Path(f).write_text(json.dumps(self._config_dict(), indent=2))
            self.log(f"Configuration saved: {f}")

    def _load_config(self):
        f = filedialog.askopenfilename(filetypes=[("Config", "*.json *.mat")])
        if not f:
            return
        if f.endswith(".mat"):  # MATLAB warpingConfig.mat
            from scipy.io import loadmat
            raw = loadmat(f, squeeze_me=True, struct_as_record=False)
            c = raw.get("cfgSave", raw.get("cfg"))
            d = {k: getattr(c, k) for k in ("participantFolder", "participantName", "baseModelFile",
                                             "includeSkin", "includeMKA") if hasattr(c, k)}
        else:
            d = json.loads(Path(f).read_text())
        self._apply_config(d)
        self._refresh()
        self.log(f"Configuration loaded: {f}")

    # ------------------------------------------------------------------ status
    def _status(self) -> dict[str, bool]:
        cfg = self.cfg()
        if cfg is None or not cfg.participant_folder.is_dir():
            return {k: False for k, *_ in STEPS}
        s = pl.detect_completed_steps(cfg)
        return {"s1": s["step1"], "s2": s["step2"] and (cfg.participant_folder / "BaseModelWithSkin").is_dir(),
                "s3": s["step3_landmarks"], "s4": s["step4"], "s5": s["step5_warped"],
                "s6": s["step6"], "s7": s["step7b"], "s8": s["step8"]}

    def _enabled(self, opt) -> bool:
        return opt is None or (opt == "skin" and self.var_skin.get()) or (opt == "mka" and self.var_mka.get())

    def _refresh(self):
        cfg = self.cfg()
        if cfg:
            self.var_basefolder.set(str(cfg.base_folder))
            t = pl.resolve_warp_template(cfg)
            self.var_template.set(str(t) if t.is_file() else "(template not found)")
        done = self._status()
        opts = {k: o for k, *_, o in STEPS}
        for key, _, _, kind, opt in STEPS:
            row = self.rows[key]
            enabled = self._enabled(opt)
            prereq = all(done[p] or not self._enabled(opts[p]) for p in PREREQ[key])
            if not enabled:
                row["status"].configure(text="Skipped (optional)", text_color=T.ST_IDLE)
            elif done[key]:
                row["status"].configure(text="✓  Done", text_color=T.ST_DONE)
            elif kind == "user" and prereq:
                row["status"].configure(text="Waiting for you…", text_color=T.ST_WAIT)
            elif prereq:
                row["status"].configure(text="Ready", text_color=T.ST_READY)
            else:
                row["status"].configure(text="Not started", text_color=T.ST_IDLE)
            T.set_enabled(row["run"], enabled and prereq and cfg is not None and not self.busy)
            T.set_enabled(row["view"], self._model_for(key) is not None)
        if hasattr(self, "post"):
            if not self.post.var_model.get() and cfg is not None:
                self.post.autodetect(quiet=True)
            self.post.refresh()

    def _auto_check(self):
        if not self.busy:
            before = getattr(self, "_last_status", None)
            now = self._status()
            if now != before:
                if before is not None:
                    if now.get("s3") and not before.get("s3"):
                        self.log("All landmark files detected.", "ok")
                    if now.get("s5") and not before.get("s5"):
                        self.log("Warped model detected (warpedModel.osim).", "ok")
                self._refresh()
            self._last_status = now
        self.root.after(AUTO_CHECK_MS, self._auto_check)

    # ------------------------------------------------------------------ viewer
    def _model_for(self, key) -> Path | None:
        cfg = self.cfg()
        if cfg is None:
            return None
        w = cfg.warped_dir

        def latest(pattern):
            hits = sorted(w.glob(pattern)) if w.is_dir() else []
            return hits[-1] if hits else None

        cand = {
            "s2": cfg.participant_folder / "BaseModelWithSkin" / f"{cfg.participant_name}_unscaled_withSkin.osim",
            "s4": cfg.base_model_file,
            "s5": w / "warpedModel.osim",
            "s6": w / "warpedModel_skinUpd.osim",
            "s7": latest("*_massCentersCorrected.osim"),
            "s8": latest("*_MKA.osim"),
        }.get(key)
        return cand if cand is not None and Path(cand).is_file() else None

    def _open_osc(self, target: Path | None = None):
        osc = find_opensim_creator()
        if not osc:
            messagebox.showwarning("MRI2MSK", "OpenSim Creator not found. Install it from opensimcreator.com "
                                              "or add osc to your PATH.")
            return
        subprocess.Popen([osc] + ([str(target)] if target else []))
        self.log("Opening OpenSim Creator" + (f": {target}" if target else ""))

    def _view(self, key):
        m = self._model_for(key)
        if m:
            self._open_osc(m)

    def _open_doc(self, name):
        for p in (REPO_DIR / name, REPO_DIR.parent / "MRI2MSK" / name):
            if p.is_file():
                try:
                    open_path(p)
                except Exception:  # noqa: BLE001
                    webbrowser.open(p.as_uri())
                return

    # ------------------------------------------------------------------ dialogs
    def _toplevel(self, title, geometry=None):
        win = ctk.CTkToplevel(self.root)
        win.title(title)
        win.configure(fg_color=T.BG)
        if geometry:
            win.geometry(geometry)
        win.after(150, win.lift)
        win.after(200, win.focus_force)
        T.set_app_icon(win)
        return win

    def _mesh_warper_helper(self, cfg):
        try:
            info = pl.prepare_mesh_warper_files(cfg)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("MRI2MSK", str(e))
            return
        self.log(f"Meshes for the Mesh Warper copied to {cfg.landmark_dir / 'meshes'}")
        win = self._toplevel("Mesh Warper helper - landmarks")
        c = T.card(win, "Landmarks for the Mesh Warper")
        c.pack(fill="both", expand=True, padx=12, pady=12)
        frm = c.body
        T.label(frm, "Automatic: set the number of landmarks per bone and click 'Auto-generate landmarks', then "
                     "check them in OpenSim Creator.\nManual: per bone open a Mesh Warping tab in OSC, import the "
                     "SOURCE / DESTINATION meshes (buttons copy the paths)\nand export the landmarks to the CSV "
                     "names below. All meshes are in landmarks/meshes.", 11, T.MUTED, justify="left").grid(
            row=0, column=0, columnspan=7, sticky="w", pady=(0, 10))
        for j, h in enumerate(("Bone", "", "", "", "", "Status", "# landmarks")):
            if h:
                T.label(frm, h, 11, T.MUTED, weight="bold").grid(row=1, column=j, sticky="w", padx=4)

        def copy(text):
            self.root.clipboard_clear()
            self.root.clipboard_append(str(text))
            self.log(f"Copied: {text}")

        status, counts = {}, {}
        for r, (key, d) in enumerate(info.items(), start=2):
            T.label(frm, key, 12, weight="bold").grid(row=r, column=0, sticky="w", padx=4)
            for j, (txt, k) in enumerate((("Source mesh", "source"), ("Destination mesh", "destination"),
                                          ("Source CSV", "base_csv"), ("Destination CSV", "participant_csv")),
                                         start=1):
                T.button(frm, txt, lambda p=d[k]: copy(p), "neutral", 118).grid(row=r, column=j, padx=3, pady=3)
            st = T.label(frm, "", 12, width=110)
            st.grid(row=r, column=5, padx=6)
            nvar = tk.StringVar(value=str(self._lm_counts.get(key, 25)))
            T.entry(frm, nvar, 60).grid(row=r, column=6, padx=4)
            status[key] = (st, d)
            counts[key] = nvar

        allvar = tk.StringVar(value="25")
        arow = ctk.CTkFrame(frm, fg_color="transparent")
        arow.grid(row=len(info) + 2, column=4, columnspan=3, sticky="e", pady=(8, 0))
        T.label(arow, "set all to", 11, T.MUTED).pack(side="left", padx=4)
        T.entry(arow, allvar, 60).pack(side="left")
        T.button(arow, "Apply", lambda: [v.set(allvar.get()) for v in counts.values()], "neutral", 60).pack(
            side="left", padx=4)

        def run_auto():
            try:
                n = {k: int(v.get()) for k, v in counts.items()}
            except ValueError:
                messagebox.showerror("MRI2MSK", "Landmark counts must be whole numbers.", parent=win)
                return
            bad = [k for k, v in n.items() if v < 4]
            if bad:
                messagebox.showerror("MRI2MSK", f"Use at least 4 landmarks ({', '.join(bad)}).", parent=win)
                return
            existing = [k for k, (_, d) in status.items() if d["base_csv"].is_file() or d["participant_csv"].is_file()]
            if existing and not messagebox.askyesno(
                    "MRI2MSK", "Landmark CSVs already exist for: " + ", ".join(existing) +
                    "\nOverwrite them with automatic landmarks?", parent=win):
                return
            self._lm_counts.update(n)
            from . import landmarks as lm
            self._start("s3", [lambda c: lm.auto_landmarks_for_participant(info, n)], cfg)

        bar = ctk.CTkFrame(frm, fg_color="transparent")
        bar.grid(row=len(info) + 3, column=0, columnspan=7, sticky="w", pady=(14, 0))
        T.button(bar, "Auto-generate landmarks", run_auto, "success", 190).pack(side="left", padx=(0, 6))
        T.button(bar, "Open OpenSim Creator", self._open_osc, "primary", 170).pack(side="left")
        T.button(bar, "Open meshes folder", lambda: open_path(cfg.landmark_dir / "meshes"), "neutral", 150).pack(
            side="left", padx=6)
        T.button(bar, "Close", win.destroy, "neutral", 70).pack(side="left")

        def tick():
            if not win.winfo_exists():
                return
            for key, (st, d) in status.items():
                b, p = d["base_csv"].is_file(), d["participant_csv"].is_file()
                if b and p:
                    st.configure(text="✓  saved", text_color=T.ST_DONE)
                elif b or p:
                    st.configure(text="1 of 2 saved", text_color=T.ST_READY)
                else:
                    st.configure(text="to do", text_color=T.ST_IDLE)
            win.after(2000, tick)

        tick()

    # ------------------------------------------------------------------ running
    def _run_step(self, key):
        cfg = self.cfg()
        if cfg is None or self.busy:
            return
        if key == "s3":
            self._mesh_warper_helper(cfg)
            return
        if key == "s5" and (cfg.warped_dir / "warpedModel.osim").is_file():
            if not messagebox.askyesno("MRI2MSK", "warpedModel/warpedModel.osim already exists.\n"
                                                  "Overwrite it with a new warp?"):
                return
        if key == "s8":
            self._run_mka(cfg)
            return
        funcs = {"s1": [pl.step1_rescale_and_align],
                 "s2": [pl.step2_align_skin, pl.step2b_add_skin_to_base_model],
                 "s4": [pl.step4_create_warp_setup],
                 "s5": [pl.step5_warp_model],
                 "s6": [pl.step6_replace_skin],
                 "s7": [pl.step7a_correct_torsion, pl.step7b_correct_mass_centers]}[key]
        self._start(key, funcs, cfg)

    def run_in_background(self, label, work, on_status=None):
        """Run ``work()`` in a thread with stdout routed to the console."""
        self.busy = True
        if on_status:
            on_status()
        self._refresh()
        self.log(f"--- {label} ---")

        def runner():
            writer = _QueueWriter(self.q)
            try:
                with contextlib.redirect_stdout(writer):
                    out = work()
                    if isinstance(out, (str, Path)):
                        print(f"-> {out}")
                self.q.put(("done", (label, True, f"{label}: done.")))
            except Exception as e:  # noqa: BLE001
                self.q.put(("log", traceback.format_exc()))
                self.q.put(("done", (label, False, f"{label} failed: {e}")))

        threading.Thread(target=runner, daemon=True).start()

    def _start(self, key, funcs, cfg):
        label = dict((k, t) for k, t, *_ in STEPS)[key].split("  ", 1)[-1]

        def work():
            out = None
            for fn in funcs:
                out = fn(cfg)
                if isinstance(out, (str, Path)):
                    print(f"-> {out}")
            return None

        self.run_in_background(label, work,
                               lambda: self.rows[key]["status"].configure(text="Running…", text_color=T.ST_RUN))

    def _run_mka(self, cfg):
        """Plot + confirm on the main thread, then apply in the worker."""
        try:
            pre = pl.load_prealignment(cfg.stl_dir)
            mka = pl.compute_mechanical_knee_axis(pre)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("MRI2MSK", str(e))
            return
        win = self._toplevel("Mechanical knee axis", "1000x860")
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
            fig = pl.plot_mka(pre, mka, bones=pl.participant_bone_meshes(cfg))
            canvas = FigureCanvasTkAgg(fig, master=win)
            canvas.draw()
            NavigationToolbar2Tk(canvas, win)
            canvas.get_tk_widget().pack(fill="both", expand=True)
        except Exception as e:  # noqa: BLE001
            T.label(win, f"(plot unavailable: {e})").pack()
        msg = (f"Left:  {abs(mka['l']):.2f}°  ({pl.mka_label('l', mka['l'])})      "
               f"Right:  {abs(mka['r']):.2f}°  ({pl.mka_label('r', mka['r'])})\n"
               "Do you want to implement these values in the model?")
        T.label(win, "MECHANICAL KNEE AXIS", 14, weight="bold").pack(pady=(8, 0))
        T.label(win, msg, 12, justify="center").pack(pady=4)
        bar = ctk.CTkFrame(win, fg_color="transparent")
        bar.pack(pady=(0, 12))

        def go():
            win.destroy()
            self._start("s8", [lambda c: pl.step8_mechanical_knee_axis(c, confirm=True, show_plot=False)], cfg)

        def cancel():
            win.destroy()
            corr = {s: -a for s, a in mka.items()}
            self.log(f"MKA not applied. Suggested values: left = {corr['l']:.4g} deg; right = {corr['r']:.4g} deg")

        T.button(bar, "Continue", go, "success", 110).pack(side="left", padx=6)
        T.button(bar, "Cancel", cancel, "neutral", 110).pack(side="left", padx=6)

    # ---- run consecutive automatic steps until a user step
    def _run_until_user(self):
        self._chain = True
        self._continue_chain()

    def _continue_chain(self):
        done = self._status()
        for key, text, _, kind, opt in STEPS:
            if not self._enabled(opt) or done[key]:
                continue
            if kind == "user" or key == "s8":
                self._chain = None
                self.log(f"Next: {text.split('  ', 1)[-1]} (needs you).")
                return
            if not T.is_enabled(self.rows[key]["run"]):
                self._chain = None
                return
            self._run_step(key)
            return
        self._chain = None
        self.log("All steps done.", "ok")


def main():
    T.set_windows_app_id()
    T.setup()
    root = ctk.CTk()
    MRI2MSKApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
