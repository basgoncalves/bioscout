"""Training Tracking tab — per-player load & fatigue dashboard.

Player → session tree, import from files / Zepp / Strava (with a per-player
credentials editor stored in players.json), an embedded dashboard, and PDF+CSV
export. Built on the bioscout.load_tracking engine + utils.player_registry.

players.json lives in the project's ``Models/`` folder (copied there by --init);
raw per-session traces are cached under ``Models/<player_id>/tracking/``.
"""

import os
import sys
import threading
from pathlib import Path

import customtkinter as ctk
from tkinter import ttk, filedialog, messagebox

import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.config_manager import ConfigManager
from utils.logger import logger
from utils.player_registry import PlayerRegistry


def _resolve_project_root() -> Path:
    """Project root that holds the Models/ folder with players.json."""
    try:
        import settings as _s
        pr = getattr(_s, "PROJECT_ROOT", None)
        if pr and Path(pr).is_dir():
            return Path(pr)
    except Exception:
        pass
    # Fallback: the package directory (so Models = bioscout/models in dev).
    return Path(__file__).parent.parent.parent


def _models_dir(root: Path) -> Path:
    for name in ("Models", "models"):
        if (root / name).is_dir():
            return root / name
    return root / "Models"


class TrainingTrackingTab(ctk.CTkFrame):
    def __init__(self, parent, config_manager: ConfigManager, status_callback):
        super().__init__(parent)
        self.config_manager = config_manager
        self.status_callback = status_callback

        self.project_root = _resolve_project_root()
        self.models_dir = _models_dir(self.project_root)
        try:
            self.registry = PlayerRegistry(self.models_dir)
        except Exception as e:   # noqa: BLE001
            logger.error(f"players.json load failed: {e}")
            self.registry = PlayerRegistry(self.models_dir)  # fresh empty

        self._store = None          # lazily created TrackingStore
        self._tracker = None        # last computed LoadTracker
        self._canvases = {}         # panel_name -> (fig, canvas)

        self._create_widgets()
        self._refresh_players()

    # ------------------------------------------------------------------ store
    def _get_store(self):
        if self._store is None:
            from load_tracking.tracking_store import TrackingStore
            self._store = TrackingStore(self.registry, self.project_root)
        return self._store

    @property
    def player(self):
        return self.player_var.get() or None

    # ------------------------------------------------------------------ UI
    def _create_widgets(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Training Tracking", font=("Segoe UI", 16, "bold")
                     ).grid(row=0, column=0, columnspan=2, padx=20, pady=(16, 6), sticky="w")

        # ---- left control column ----
        ctrl = ctk.CTkScrollableFrame(self, width=300)
        ctrl.grid(row=1, column=0, padx=(20, 10), pady=10, sticky="nsw")

        ctk.CTkLabel(ctrl, text="Player", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.player_var = ctk.StringVar(value="")
        self.player_menu = ctk.CTkOptionMenu(ctrl, variable=self.player_var, values=[""],
                                             command=lambda _v: self._on_player_change())
        self.player_menu.pack(fill="x", pady=2)
        prow = ctk.CTkFrame(ctrl, fg_color="transparent"); prow.pack(fill="x", pady=2)
        ctk.CTkButton(prow, text="Add player…", width=130, command=self._add_player_dialog
                      ).pack(side="left", padx=(0, 4))
        ctk.CTkButton(prow, text="Credentials…", width=130, fg_color="#1971c2",
                      hover_color="#155fa0", command=self._credentials_dialog
                      ).pack(side="left")

        ctk.CTkLabel(ctrl, text="Import sessions", font=("Segoe UI", 12, "bold")
                     ).pack(anchor="w", pady=(12, 2))
        ctk.CTkButton(ctrl, text="Import files…", command=self._import_files).pack(fill="x", pady=2)
        ctk.CTkButton(ctrl, text="Import from Zepp", command=lambda: self._import_cloud("zepp")
                      ).pack(fill="x", pady=2)
        ctk.CTkButton(ctrl, text="Import from Strava", command=lambda: self._import_cloud("strava")
                      ).pack(fill="x", pady=2)

        ctk.CTkLabel(ctrl, text="Sessions", font=("Segoe UI", 12, "bold")
                     ).pack(anchor="w", pady=(12, 2))
        # session table (ttk.Treeview — customtkinter has no table widget)
        style = ttk.Style()
        try:
            style.configure("Track.Treeview", background="#2b2b2b",
                            fieldbackground="#2b2b2b", foreground="#e0e0e0",
                            rowheight=22)
        except Exception:
            pass
        self.tree = ttk.Treeview(ctrl, columns=("date", "activity", "load"),
                                 show="headings", height=10, style="Track.Treeview")
        for c, w in (("date", 80), ("activity", 80), ("load", 55)):
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="x", pady=2)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._on_session_select())

        ctk.CTkLabel(ctrl, text="Export", font=("Segoe UI", 12, "bold")
                     ).pack(anchor="w", pady=(12, 2))
        ctk.CTkButton(ctrl, text="Export report (PDF + CSV)", fg_color="#2f9e44",
                      hover_color="#268038", command=self._export).pack(fill="x", pady=2)
        self.status_lbl = ctk.CTkLabel(ctrl, text="", font=("Segoe UI", 9),
                                       text_color="#9aa0a6", wraplength=280, justify="left")
        self.status_lbl.pack(anchor="w", pady=(8, 0))

        # ---- right dashboard ----
        right = ctk.CTkFrame(self)
        right.grid(row=1, column=1, padx=(10, 20), pady=10, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        self.kpi_lbl = ctk.CTkLabel(right, text="Select or add a player to begin.",
                                    font=("Segoe UI", 11), justify="left", anchor="w")
        self.kpi_lbl.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))

        self.tabs = ctk.CTkTabview(right)
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        for name in ("Overview", "Muscles", "Session HR"):
            self.tabs.add(name)
            frame = self.tabs.tab(name)
            frame.grid_rowconfigure(0, weight=1)
            frame.grid_columnconfigure(0, weight=1)
            fig = Figure(figsize=(7, 4.2), dpi=100)
            fig.patch.set_facecolor("#2b2b2b")
            canvas = FigureCanvasTkAgg(fig, master=frame)
            canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
            self._canvases[name] = (fig, canvas)

    # ------------------------------------------------------------------ players
    def _refresh_players(self):
        ids = self.registry.all_ids()
        self.player_menu.configure(values=ids or [""])
        if ids and not self.player_var.get():
            self.player_var.set(ids[0])
        self._on_player_change()

    def _on_player_change(self):
        self._refresh_session_table()
        self._recompute_and_draw()

    def _add_player_dialog(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Add player"); dlg.geometry("400x540")
        dlg.transient(self); dlg.grab_set()
        dlg.grid_rowconfigure(0, weight=1); dlg.grid_columnconfigure(0, weight=1)

        # scrollable fields + a fixed bottom bar (button always visible)
        body = ctk.CTkScrollableFrame(dlg)
        body.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        bar = ctk.CTkFrame(dlg, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))

        fields, entries = {}, {}

        def add_field(label, key, default=""):
            ctk.CTkLabel(body, text=label).pack(anchor="w", padx=16, pady=(8, 0))
            var = ctk.StringVar(value=default)
            ent = ctk.CTkEntry(body, textvariable=var)
            ent.pack(fill="x", padx=16)
            fields[key] = var; entries[key] = ent
            return var, ent

        id_var, id_ent = add_field("Player ID (unique)", "id")
        add_field("Name", "name")
        age_var, _ = add_field("Age", "age")
        add_field("Sex (M/F)", "sex", "M")
        add_field("Mass (kg)", "mass_kg")
        hrmax_var, hrmax_ent = add_field("Max HR (bpm) — auto from age, editable", "hr_max")
        add_field("Resting HR (bpm) — default 60, editable", "hr_rest", "60")

        default_border = id_ent.cget("border_color")
        msg = ctk.CTkLabel(bar, text="", font=("Segoe UI", 9), text_color="#e03131")
        msg.pack(anchor="w")
        add_btn = ctk.CTkButton(bar, text="Add")
        add_btn.pack(fill="x", pady=(4, 0))

        # --- Max HR auto-prediction from age (Tanaka 208 - 0.7·age), until edited ---
        state = {"hrmax_manual": bool(hrmax_var.get().strip())}
        hrmax_ent.bind("<KeyRelease>", lambda _e: state.update(hrmax_manual=True))

        def predict_hrmax(*_):
            if state["hrmax_manual"]:
                return
            a = age_var.get().strip()
            if a.isdigit() and int(a) > 0:
                hrmax_var.set(str(int(round(208 - 0.7 * int(a)))))
        age_var.trace_add("write", predict_hrmax)

        # --- live ID validation: red border + disabled Add if taken/empty ---
        def validate_id(*_):
            pid = id_var.get().strip()
            taken = pid in self.registry
            id_ent.configure(border_color="#e03131" if (taken or not pid) else default_border)
            if taken:
                msg.configure(text=f"ID '{pid}' already exists — choose another.")
                add_btn.configure(state="disabled")
            elif not pid:
                msg.configure(text=""); add_btn.configure(state="disabled")
            else:
                msg.configure(text=""); add_btn.configure(state="normal")
        id_var.trace_add("write", validate_id)
        validate_id()

        def save():
            pid = id_var.get().strip()
            if not pid or pid in self.registry:
                return
            rec = {"name": fields["name"].get().strip(),
                   "sex": (fields["sex"].get().strip() or "M")[:1].upper()}
            a = fields["age"].get().strip()
            rec["age"] = int(a) if a.isdigit() else None
            v = fields["mass_kg"].get().strip()
            try: rec["mass_kg"] = float(v) if v else None
            except ValueError: rec["mass_kg"] = None
            hr = {}
            for k, kk in (("hr_max", "max"), ("hr_rest", "rest")):
                v = fields[k].get().strip()
                try: hr[kk] = float(v) if v else None
                except ValueError: hr[kk] = None
            try:
                self.registry.add(pid, rec)
                tr = self.registry.get(pid)["tracking"]; tr["hr"] = hr
                self.registry.update(pid, {"tracking": tr})
            except Exception as e:   # noqa: BLE001
                messagebox.showerror("Error", str(e)); return
            dlg.destroy()
            self.player_var.set(pid); self._refresh_players()

        add_btn.configure(command=save)

    def _credentials_dialog(self):
        pid = self.player
        if not pid:
            messagebox.showinfo("No player", "Select or add a player first."); return
        creds = self.registry.get_credentials(pid)
        z = creds.get("zepp", {}); s = creds.get("strava", {})
        dlg = ctk.CTkToplevel(self)
        dlg.title(f"Cloud credentials — {pid}"); dlg.geometry("420x430")
        dlg.transient(self); dlg.grab_set()
        ctk.CTkLabel(dlg, text="Zepp / Amazfit (captured apptoken)",
                     font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(12, 2))
        zt = ctk.StringVar(value=z.get("token", "")); zr = ctk.StringVar(value=z.get("region", "de2"))
        ctk.CTkLabel(dlg, text="apptoken").pack(anchor="w", padx=16)
        ctk.CTkEntry(dlg, textvariable=zt).pack(fill="x", padx=16)
        ctk.CTkLabel(dlg, text="region (de2 / us2 …)").pack(anchor="w", padx=16)
        ctk.CTkEntry(dlg, textvariable=zr).pack(fill="x", padx=16)

        ctk.CTkLabel(dlg, text="Strava (OAuth app)", font=("Segoe UI", 12, "bold")
                     ).pack(anchor="w", padx=16, pady=(12, 2))
        sc = ctk.StringVar(value=s.get("client_id", ""))
        ss = ctk.StringVar(value=s.get("client_secret", ""))
        sr = ctk.StringVar(value=s.get("refresh_token", ""))
        for lbl, var in (("client_id", sc), ("client_secret", ss), ("refresh_token", sr)):
            ctk.CTkLabel(dlg, text=lbl).pack(anchor="w", padx=16)
            ctk.CTkEntry(dlg, textvariable=var).pack(fill="x", padx=16)

        def save():
            new = {}
            if zt.get().strip():
                new["zepp"] = {"token": zt.get().strip(), "region": zr.get().strip() or "de2"}
            if sc.get().strip() and ss.get().strip() and sr.get().strip():
                new["strava"] = {"client_id": sc.get().strip(),
                                 "client_secret": ss.get().strip(),
                                 "refresh_token": sr.get().strip()}
            self.registry.set_credentials(pid, new)
            self._set_status(f"Saved credentials for {pid}.")
            dlg.destroy()

        ctk.CTkButton(dlg, text="Save", command=save).pack(pady=14)

    # ------------------------------------------------------------------ import
    def _import_files(self):
        if not self._require_player():
            return
        files = filedialog.askopenfilenames(
            title="Select workout exports",
            filetypes=[("Workout files", "*.fit *.tcx *.gpx *.csv"), ("All", "*.*")])
        if not files:
            return
        self._run_bg(lambda: self._get_store().import_files(self.player, list(files)),
                     "Importing files…")

    def _import_cloud(self, source):
        pid = self.player
        if not self._require_player():
            return
        creds = self.registry.get_credentials(pid)
        if source == "zepp":
            z = creds.get("zepp", {})
            if not z.get("token"):
                messagebox.showinfo("No Zepp credentials",
                                    "Add a Zepp apptoken via Credentials… first."); return
            fn = lambda: self._get_store().import_zepp(pid, z["token"], z.get("region", "de2"))
        else:
            s = creds.get("strava", {})
            if not all(s.get(k) for k in ("client_id", "client_secret", "refresh_token")):
                messagebox.showinfo("No Strava credentials",
                                    "Add Strava client_id/secret/refresh_token via Credentials… first.")
                return
            fn = lambda: self._get_store().import_strava(
                pid, s["client_id"], s["client_secret"], s["refresh_token"])
        self._run_bg(fn, f"Importing from {source}…")

    def _run_bg(self, fn, msg):
        self._set_status(msg)
        def worker():
            try:
                n = fn()
                self.after(0, lambda: self._after_import(n))
            except Exception as e:   # noqa: BLE001
                logger.error(f"Import failed: {e}", exc_info=True)
                self.after(0, lambda: self._set_status(f"Import failed: {e}"))
        threading.Thread(target=worker, daemon=True).start()

    def _after_import(self, n):
        self._set_status(f"Imported {n} session(s).")
        self._refresh_session_table()
        self._recompute_and_draw()

    # ------------------------------------------------------------------ sessions
    def _refresh_session_table(self):
        self.tree.delete(*self.tree.get_children())
        pid = self.player
        if not pid:
            return
        for s in self.registry.get_sessions(pid):
            self.tree.insert("", "end", iid=s.get("id"),
                             values=(s.get("date", ""), s.get("activity", ""),
                                     f"{s.get('load', 0):.0f}"))

    def _on_session_select(self):
        self._draw_session_hr()

    # ------------------------------------------------------------------ compute + draw
    def _recompute_and_draw(self):
        pid = self.player
        self._tracker = None
        if not pid:
            self.kpi_lbl.configure(text="Select or add a player to begin.")
            self._clear_all_panels(); return
        try:
            from load_tracking import LoadTracker
            store = self._get_store()
            sessions = store.load_all_sessions(pid)
            if not sessions:
                self.kpi_lbl.configure(text=f"{pid}: no sessions yet — import some.")
                self._clear_all_panels(); return
            tracker = LoadTracker(athlete=store.athlete_for(pid))
            tracker.sessions = sessions
            tracker.compute()
            self._tracker = tracker
        except Exception as e:   # noqa: BLE001
            logger.error(f"Compute failed: {e}", exc_info=True)
            self.kpi_lbl.configure(text=f"Compute error: {e}"); return
        self._draw_kpis(); self._draw_overview(); self._draw_muscles(); self._draw_session_hr()

    def _clear_all_panels(self):
        for name, (fig, canvas) in self._canvases.items():
            fig.clear(); canvas.draw()

    def _draw_kpis(self):
        r = self._tracker.results
        acwr = r.acwr.get("latest_acwr")
        from load_tracking import metrics as _m
        lbl = _m.acwr_status(acwr)[0] if acwr is not None else "n/a"
        wk = r.mono_strain.get("weekly_load")
        fat = r.ff.get("latest_fatigue")
        txt = (f"Sessions: {len(r.sessions)}    "
               f"ACWR: {acwr:.2f} ({lbl})    " if acwr is not None else
               f"Sessions: {len(r.sessions)}    ACWR: n/a    ")
        txt += f"7-day load: {wk:.0f}    " if wk is not None else ""
        txt += f"Fatigue: {fat:.0f}" if fat is not None else ""
        self.kpi_lbl.configure(text=txt)

    def _style_ax(self, ax):
        ax.set_facecolor("#2b2b2b")
        ax.tick_params(colors="#cccccc", labelsize=7)
        for sp in ax.spines.values():
            sp.set_color("#555555")
        ax.title.set_color("#e0e0e0"); ax.yaxis.label.set_color("#cccccc")

    def _draw_overview(self):
        fig, canvas = self._canvases["Overview"]
        fig.clear(); r = self._tracker.results
        ax1 = fig.add_subplot(211); ax2 = fig.add_subplot(212)
        days = [d.day for d in r.daily]
        ax1.bar(days, [d.load for d in r.daily], color="#e8590c", width=0.9)
        ax1.set_title("Daily training load", fontsize=9, loc="left"); self._style_ax(ax1)
        adays = r.acwr.get("days", [])
        if adays:
            import numpy as np
            a = np.array(r.acwr["acwr"])
            ax2.axhspan(0.8, 1.3, color="#2f9e44", alpha=0.15)
            ax2.axhspan(1.5, max(2.0, float(np.nanmax(a)) + 0.2), color="#e03131", alpha=0.10)
            ax2.plot(adays, a, color="#74c0fc", lw=1.6)
        ax2.set_title("Acute:chronic workload ratio", fontsize=9, loc="left"); self._style_ax(ax2)
        fig.tight_layout(); canvas.draw()

    def _draw_muscles(self):
        fig, canvas = self._canvases["Muscles"]
        fig.clear(); r = self._tracker.results
        ax1 = fig.add_subplot(121); ax2 = fig.add_subplot(122)
        states = [s for s in r.muscle_states if s.fatigue_index > 0]
        if states:
            labels = [s.label.split(" (")[0] for s in states][::-1]
            ax1.barh(labels, [s.fatigue_index for s in states][::-1],
                     color=[s.color for s in states][::-1])
        ax1.set_title("Fatigue index", fontsize=9, loc="left"); self._style_ax(ax1)
        # contraction work breakdown
        from load_tracking import contraction
        agg = contraction.aggregate_work(r.sessions, r.muscle_loads)
        pm = agg["per_muscle"]
        if pm:
            import numpy as np
            from load_tracking.muscle_map import MUSCLE_LABELS
            muscles = sorted(pm, key=lambda m: pm[m]["total"], reverse=True)[:8][::-1]
            names = [MUSCLE_LABELS.get(m, m).split(" (")[0] for m in muscles]
            conc = [pm[m]["concentric"] for m in muscles]
            iso = [pm[m]["isometric"] for m in muscles]
            ecc = [pm[m]["eccentric"] for m in muscles]
            y = np.arange(len(muscles))
            ax2.barh(y, conc, color="#2f9e44", label="concentric")
            ax2.barh(y, iso, left=conc, color="#f59f00", label="isometric")
            ax2.barh(y, ecc, left=np.array(conc) + np.array(iso), color="#e03131", label="eccentric")
            ax2.set_yticks(y); ax2.set_yticklabels(names)
            p = agg["percent"]
            ax2.set_title(f"Work: {p['concentric']:.0f}% conc / {p['isometric']:.0f}% iso / "
                          f"{p['eccentric']:.0f}% ecc", fontsize=8, loc="left")
            ax2.legend(fontsize=6, loc="lower right", facecolor="#2b2b2b",
                       labelcolor="#cccccc", framealpha=0.3)
        self._style_ax(ax2)
        fig.tight_layout(); canvas.draw()

    def _draw_session_hr(self):
        fig, canvas = self._canvases["Session HR"]
        fig.clear(); ax = fig.add_subplot(111); self._style_ax(ax)
        pid = self.player
        sel = self.tree.selection()
        if pid and sel:
            s = self._get_store().load_raw(pid, sel[0])
            if s is not None and s.hr.size and s.time_s.size == s.hr.size:
                import numpy as np
                t = s.time_s / 60.0
                ax.plot(t, s.hr, color="#ff6b6b", lw=1.2)
                hrmax = self._get_store().athlete_for(pid).resolved_hr_max()
                for frac, col in zip((0.6, 0.7, 0.8, 0.9),
                                     ("#3b8ed0", "#2f9e44", "#f59f00", "#e03131")):
                    ax.axhline(hrmax * frac, color=col, ls=":", lw=0.7, alpha=0.6)
                ax.set_title(f"{s.activity} — {s.date} (HR over minutes)",
                             fontsize=9, loc="left")
                ax.set_xlabel("min", color="#cccccc")
            else:
                ax.set_title("No HR trace for this session", fontsize=9, loc="left")
        else:
            ax.set_title("Select a session to see its heart-rate trace",
                         fontsize=9, loc="left")
        fig.tight_layout(); canvas.draw()

    # ------------------------------------------------------------------ export
    def _export(self):
        pid = self.player
        if not self._require_player() or self._tracker is None:
            messagebox.showinfo("Nothing to export", "Import sessions for a player first.")
            return
        out_dir = self.models_dir / pid
        out_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = out_dir / "load_report.pdf"
        csv_path = out_dir / "sessions.csv"
        try:
            self._tracker.report(str(pdf_path), title=f"BioScout — {pid}")
            self._get_store().export_csv(pid, str(csv_path))
        except Exception as e:   # noqa: BLE001
            logger.error(f"Export failed: {e}", exc_info=True)
            messagebox.showerror("Export failed", str(e)); return
        self._set_status(f"Exported:\n{pdf_path}\n{csv_path}")
        if self.status_callback:
            self.status_callback(f"Tracking report saved for {pid}")

    # ------------------------------------------------------------------ misc
    def _require_player(self) -> bool:
        if not self.player:
            messagebox.showinfo("No player", "Select or add a player first."); return False
        return True

    def _set_status(self, text):
        self.status_lbl.configure(text=text)
