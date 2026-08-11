"""Model Scaling Tab - OpenSim Scale Tool interface with marker weight adjustment."""

import customtkinter as ctk
from pathlib import Path
import sys
import os
import io
import threading
from tkinter import filedialog, messagebox
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.config_manager import ConfigManager
from utils.logger import logger
from utils.model_scaler import ModelScaler
from settings import BatchSettings
marker_weights = BatchSettings.marker_weights


def _opensim_utils():
    """bioscout.utils.openSim, however this process happens to be importing.

    The GUI runs both as `python -m bioscout` (package importable) and with the
    package directory itself on sys.path (see the insert above), so neither
    import form works everywhere.
    """
    try:
        from bioscout.utils import openSim as _m
    except ImportError:
        from utils import openSim as _m           # type: ignore[no-redef]
    return _m


class ModelScalingTab(ctk.CTkFrame):
    """Tab for OpenSim model scaling with marker weight configuration."""

    def __init__(self, parent, config_manager: ConfigManager, status_callback):
        """Initialize Model Scaling Tab."""
        super().__init__(parent)
        self.config_manager = config_manager
        self.status_callback = status_callback

        # State
        self.template_model_path = None
        self.markerset_path = None
        self.trc_file_path = None
        self.destination_path = None
        self.markers_from_trc = {}  # marker_name -> frame_count
        self.marker_weight_vars = {}  # marker_name -> CTkVariable
        self.marker_use_vars = {}     # marker_name -> BooleanVar (scale with it)
        self.marker_fixed_vars = {}   # marker_name -> BooleanVar (fixed to parent)
        self._project_root = None

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create UI widgets."""
        # Row 3 is the marker panel: give it ALL the slack so it fills the
        # tab instead of leaving a screen of empty grey above the buttons.
        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ===== TOP: Title and Session Info =====
        top_frame = ctk.CTkFrame(self)
        top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        top_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top_frame, text="Model Scaling", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )

        # ===== SESSION SELECTOR =========================================
        # Everything below is DERIVED from session.yaml. The four paths used to
        # be typed, which is how a markerset from another project and an output
        # written outside the iteration both got in — the two mistakes that
        # produce a model the pipeline then quietly ignores.
        sess_frame = ctk.CTkFrame(self)
        sess_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(46, 6))
        for _c in (1, 3, 5):
            sess_frame.grid_columnconfigure(_c, weight=1)

        ctk.CTkLabel(sess_frame, text="Subject:",
                     font=("Segoe UI", 10, "bold")).grid(row=0, column=0,
                                                         sticky="w", padx=(8, 4), pady=8)
        self.subject_var = ctk.StringVar(value="")
        self.subject_menu = ctk.CTkOptionMenu(sess_frame, variable=self.subject_var,
                                              values=["—"], command=self._on_subject)
        self.subject_menu.grid(row=0, column=1, sticky="ew", padx=4, pady=8)

        ctk.CTkLabel(sess_frame, text="Session:",
                     font=("Segoe UI", 10, "bold")).grid(row=0, column=2,
                                                         sticky="w", padx=(12, 4), pady=8)
        self.session_var = ctk.StringVar(value="")
        self.session_menu = ctk.CTkOptionMenu(sess_frame, variable=self.session_var,
                                              values=["—"], command=self._on_session)
        self.session_menu.grid(row=0, column=3, sticky="ew", padx=4, pady=8)

        ctk.CTkLabel(sess_frame, text="Iteration:",
                     font=("Segoe UI", 10, "bold")).grid(row=0, column=4,
                                                         sticky="w", padx=(12, 4), pady=8)
        self.iteration_var = ctk.StringVar(value="")
        self.iteration_menu = ctk.CTkOptionMenu(sess_frame, variable=self.iteration_var,
                                                values=["—"], command=self._on_iteration)
        self.iteration_menu.grid(row=0, column=5, sticky="ew", padx=4, pady=8)

        self.derived_label = ctk.CTkLabel(sess_frame, text="", font=("Segoe UI", 9),
                                          text_color="#888888", anchor="w",
                                          justify="left", wraplength=1200)
        self.derived_label.grid(row=1, column=0, columnspan=6, sticky="w",
                                padx=8, pady=(0, 6))

        # ===== INPUT PATHS SECTION =====
        input_frame = ctk.CTkFrame(self)
        input_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
        input_frame.grid_columnconfigure(1, weight=1)

        # Template Model Path
        ctk.CTkLabel(input_frame, text="Template Model (.osim):", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, sticky="w", padx=(0, 5), pady=(10, 5)
        )
        self.template_model_var = ctk.StringVar(value="")
        template_entry = ctk.CTkEntry(input_frame, textvariable=self.template_model_var, placeholder_text="Select template model")
        template_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=(10, 5))

        ctk.CTkButton(
            input_frame,
            text="Browse",
            width=80,
            command=self._browse_template_model
        ).grid(row=0, column=2, padx=5, pady=(10, 5))

        # Markerset Path (Optional)
        ctk.CTkLabel(input_frame, text="Markerset (.xml) [Optional]:", font=("Segoe UI", 10, "bold")).grid(
            row=1, column=0, sticky="w", padx=(0, 5), pady=(0, 5)
        )
        self.markerset_var = ctk.StringVar(value="")
        markerset_entry = ctk.CTkEntry(input_frame, textvariable=self.markerset_var, placeholder_text="Select markerset or use model's default")
        markerset_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=(0, 5))

        ctk.CTkButton(
            input_frame,
            text="Browse",
            width=80,
            command=self._browse_markerset
        ).grid(row=1, column=2, padx=5, pady=(0, 5))

        # TRC File for Scaling
        ctk.CTkLabel(input_frame, text="TRC File for Scaling:", font=("Segoe UI", 10, "bold")).grid(
            row=2, column=0, sticky="w", padx=(0, 5), pady=(0, 5)
        )
        self.trc_var = ctk.StringVar(value="")
        trc_entry = ctk.CTkEntry(input_frame, textvariable=self.trc_var, placeholder_text="Select TRC file for scaling")
        trc_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=(0, 5))

        ctk.CTkButton(
            input_frame,
            text="Browse",
            width=80,
            command=self._browse_trc_file
        ).grid(row=2, column=2, padx=5, pady=(0, 5))

        # Destination Path (Full file path with .osim filename)
        ctk.CTkLabel(input_frame, text="Output Model (.osim):", font=("Segoe UI", 10, "bold")).grid(
            row=3, column=0, sticky="w", padx=(0, 5), pady=(0, 10)
        )
        self.destination_var = ctk.StringVar(value="")
        dest_entry = ctk.CTkEntry(input_frame, textvariable=self.destination_var, placeholder_text="Path for output model (e.g., /folder/scaled_model.osim)")
        dest_entry.grid(row=3, column=1, sticky="ew", padx=5, pady=(0, 10))

        ctk.CTkButton(
            input_frame,
            text="Browse",
            width=80,
            command=self._browse_destination
        ).grid(row=3, column=2, padx=5, pady=(0, 10))

        # Load TRC Button — kept explicit. Reading the TRC and rebuilding the
        # marker rows is the slow part of this tab, so it happens when asked.
        self.load_btn = ctk.CTkButton(
            input_frame,
            text="Load Markers from TRC",
            fg_color="#0084ff",
            command=self._load_trc_markers,
            font=("Segoe UI", 13, "bold"),
            height=36
        )
        self.load_btn.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(5, 6))

        # ScaleTool stages, both real switches in openSim.scale_model.
        stage_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        stage_frame.grid(row=5, column=0, columnspan=3, sticky="w", pady=(0, 8))
        self.linear_var = ctk.BooleanVar(value=True)
        self.placer_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(stage_frame, text="dimensional scaling (ModelScaler)",
                        variable=self.linear_var,
                        font=("Segoe UI", 11)).pack(side="left", padx=(0, 18))
        ctk.CTkCheckBox(stage_frame, text="register markers to the static pose",
                        variable=self.placer_var,
                        font=("Segoe UI", 11)).pack(side="left")

        # ===== MARKERS PANEL =====
        markers_label_frame = ctk.CTkFrame(self)
        markers_label_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 5))
        markers_label_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(markers_label_frame, text="Marker Weights", font=("Segoe UI", 12, "bold")).pack(side="left", anchor="w")

        # Reset Button
        ctk.CTkButton(
            markers_label_frame,
            text="Reset to Default",
            width=150,
            height=30,
            font=("Segoe UI", 12, "bold"),
            command=self._reset_weights
        ).pack(side="right", anchor="e", padx=5)

        # Two panes: what the marker does DURING scaling on the left, what it
        # becomes in the OUTPUT MODEL on the right. They are different
        # questions and were sharing one column with nothing in it.
        panes = ctk.CTkFrame(self, fg_color="transparent")
        panes.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 8))
        panes.grid_rowconfigure(1, weight=1)
        panes.grid_columnconfigure(0, weight=3)
        panes.grid_columnconfigure(1, weight=2)

        ctk.CTkLabel(panes, text="Scaling — weight, and whether to use the marker",
                     font=("Segoe UI", 10, "bold")).grid(row=0, column=0,
                                                          sticky="w", padx=6, pady=(0, 4))
        ctk.CTkLabel(panes, text="Output model — fix marker to its parent frame",
                     font=("Segoe UI", 10, "bold")).grid(row=0, column=1,
                                                          sticky="w", padx=6, pady=(0, 4))

        self.markers_frame = ctk.CTkScrollableFrame(panes, corner_radius=8)
        self.markers_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 4))
        self.markers_frame.grid_columnconfigure(0, weight=1)

        self.fixed_frame = ctk.CTkScrollableFrame(panes, corner_radius=8)
        self.fixed_frame.grid(row=1, column=1, sticky="nsew", padx=(4, 0))
        self.fixed_frame.grid_columnconfigure(0, weight=1)

        # Empty state message
        self.empty_label = ctk.CTkLabel(
            self.markers_frame,
            text="Load a TRC file to see available markers",
            text_color="#888888",
            font=("Segoe UI", 9)
        )
        self.empty_label.pack(pady=20)

        # ===== BOTTOM: Action Buttons =====
        button_frame = ctk.CTkFrame(self)
        button_frame.grid(row=4, column=0, sticky="ew", padx=10, pady=10)
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        self.scale_btn = ctk.CTkButton(
            button_frame,
            text="RUN  Scale Model",
            fg_color="#28a745",
            hover_color="#218838",
            text_color="#000000",
            font=("Segoe UI", 16, "bold"),
            height=48,
            command=self._run_scaling
        )
        self.scale_btn.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self.stop_btn = ctk.CTkButton(
            button_frame,
            text="STOP  Cancel",
            fg_color="#dc3545",
            hover_color="#c82333",
            text_color="#000000",
            font=("Segoe UI", 16, "bold"),
            height=48,
            command=self._stop_scaling,
            state="disabled"
        )
        self.stop_btn.grid(row=0, column=3, sticky="ew", padx=(5, 0))

        # Writing the setup without running it is how you check what the Scale
        # Tool was actually told, which a log after the fact cannot show.
        self.view_setup_btn = ctk.CTkButton(
            button_frame,
            text="View setup XML",
            fg_color="#3a3a3a", hover_color="#4a4a4a",
            font=("Segoe UI", 16, "bold"), height=48,
            command=self._view_setup_xml
        )
        self.view_setup_btn.grid(row=0, column=1, sticky="ew", padx=5)

        self.save_setup_btn = ctk.CTkButton(
            button_frame,
            text="Save setup XML",
            fg_color="#0084ff", hover_color="#0069cc",
            font=("Segoe UI", 16, "bold"), height=48,
            command=self._save_setup_xml
        )
        self.save_setup_btn.grid(row=0, column=2, sticky="ew", padx=5)
        button_frame.grid_columnconfigure(2, weight=1)
        button_frame.grid_columnconfigure(3, weight=1)

        # Status label
        self.status_label = ctk.CTkLabel(button_frame, text="Ready", text_color="#28a745", font=("Segoe UI", 9))
        self.status_label.grid(row=1, column=0, columnspan=4, sticky="w", pady=(5, 0))

        # Show something the moment the tab exists. The tab is created lazily,
        # often AFTER the main window has broadcast the project, so waiting to
        # be told is how it ended up opening with four empty boxes.
        self._seed_from_settings()
        try:
            self._refresh_subjects()
        except Exception:                                          # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # session -> paths
    # ------------------------------------------------------------------
    def set_project_dir(self, project_dir) -> None:
        """Called by the main window whenever a project is loaded."""
        self._project_root = Path(project_dir) if project_dir else None
        self._refresh_subjects()

    # the main window may broadcast under either name
    on_project_dir = set_project_dir
    update_project_dir = set_project_dir

    def _seed_from_settings(self) -> None:
        """Fill the template model and markerset from the project's settings.py.

        These two are project-wide, not per session: every iteration of every
        subject scales from the same generic model and the same markerset. The
        tab used to open with both blank and no hint of where they live, so the
        first thing anyone did was browse — and browsing is how a markerset
        from another project gets in. A session+iteration selection overrides
        them; this is only what to show before one is made.
        """
        if self._project_root is None:
            # The GUI is normally started from inside the project
            # (python -m bioscout --gui), which is also where settings.py was
            # imported from — so cwd is the project until told otherwise.
            try:
                _cwd = Path.cwd()
                if (_cwd / "settings.py").is_file():
                    self._project_root = _cwd
            except Exception:                                      # noqa: BLE001
                pass
        try:
            gen = getattr(BatchSettings, "generic_model", "") or ""
            if gen and not self.template_model_var.get():
                self.template_model_var.set(str(gen))
        except Exception:                                          # noqa: BLE001
            pass
        try:
            ms = getattr(BatchSettings, "markerset", "") or ""
            if ms and not self.markerset_var.get():
                self.markerset_var.set(str(ms))
        except Exception:                                          # noqa: BLE001
            pass

    def _sims(self):
        if not self._project_root:
            return None
        try:
            from .. import simulations_root as _sim_root
        except Exception:                                          # noqa: BLE001
            return None
        try:
            p = _sim_root(self._project_root, getattr(self, "config_manager", None))
        except Exception:                                          # noqa: BLE001
            return None
        return p if (p and p.is_dir()) else None

    def _refresh_subjects(self) -> None:
        sims = self._sims()
        try:
            opts = sorted(d.name for d in sims.iterdir() if d.is_dir()) if sims else []
        except Exception:                                          # noqa: BLE001
            opts = []
        self.subject_menu.configure(values=opts or ["—"])
        self.subject_var.set((opts or ["—"])[0])
        self._on_subject()

    def _on_subject(self, *_):
        sims, s = self._sims(), self.subject_var.get()
        opts = []
        if sims and s and s != "—":
            d = sims / s
            if d.is_dir():
                try:
                    opts = sorted(x.name for x in d.iterdir() if x.is_dir())
                except Exception:                                  # noqa: BLE001
                    opts = []
        self.session_menu.configure(values=opts or ["—"])
        self.session_var.set((opts or ["—"])[0])
        self._on_session()

    def _session_dir(self):
        sims = self._sims()
        s, ss = self.subject_var.get(), self.session_var.get()
        if not sims or "—" in (s, ss) or not s or not ss:
            return None
        d = sims / s / ss
        return d if d.is_dir() else None

    def _on_session(self, *_):
        d = self._session_dir()
        opts = []
        if d:
            try:
                from .. import scaling_defaults
                opts = scaling_defaults(str(d)).get("iterations") or []
            except Exception:                                      # noqa: BLE001
                opts = []
        self.iteration_menu.configure(values=opts or ["—"])
        self.iteration_var.set((opts or ["—"])[0])
        self._on_iteration()

    def _on_iteration(self, *_):
        """Fill the four path fields from session.yaml."""
        d = self._session_dir()
        it = self.iteration_var.get()
        if not d or not it or it == "—":
            self.derived_label.configure(
                text="pick a subject, session and iteration — "
                     "model and markerset below come from settings.py",
                text_color="#888888")
            return
        try:
            from .. import scaling_defaults
            info = scaling_defaults(str(d), it)
        except Exception as e:                                     # noqa: BLE001
            self.derived_label.configure(text=f"could not read session.yaml: {e}",
                                         text_color="#dc3545")
            return

        # Only overwrite a field the session actually states — a session that
        # names no markerset should leave the settings.py one in place rather
        # than blanking it.
        if info.get("template_model"):
            self.template_model_var.set(info["template_model"])
        if info.get("markerset"):
            self.markerset_var.set(info["markerset"])
        if info.get("trc"):
            self.trc_var.set(info["trc"])
        if info.get("output"):
            self.destination_var.set(info["output"])

        if info["errors"]:
            self.derived_label.configure(
                text="from session.yaml — " + "; ".join(info["errors"]),
                text_color="#c9a227")
        else:
            self.derived_label.configure(
                text=(f"from session.yaml — static trial {info['static_trial']}, "
                      f"output {os.path.basename(info['output'])} in "
                      f"3_iterations/{it}/"),
                text_color="#28a745")

        # NOT loading the markers here on purpose. Parsing the TRC and
        # rebuilding ~150 widgets takes long enough to feel like a hang, and
        # changing the iteration dropdown is not a request to do it. The button
        # says what is waiting to happen.
        self._mark_markers_stale()

    def _mark_markers_stale(self) -> None:
        """Say the loaded markers no longer match the selected TRC."""
        try:
            trc = self.trc_var.get()
            n = len(self.marker_weight_vars)
            if not trc:
                self.load_btn.configure(text="Load Markers from TRC")
            elif n:
                self.load_btn.configure(
                    text=f"Reload Markers from TRC  ({n} loaded from another trial)")
            else:
                self.load_btn.configure(
                    text=f"Load Markers from TRC  ({os.path.basename(os.path.dirname(trc))})")
        except Exception:                                          # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    def _scale_kwargs(self):
        """Arguments shared by Run, Save setup and View — one source, so the
        XML you inspect is the one that runs."""
        return dict(
            generic_opensim_model_path=self.template_model_var.get(),
            static_trc_path=self.trc_var.get(),
            scaled_model_path=self.destination_var.get(),
            marker_set_file=self.markerset_var.get() or None,
            linear_scaling=bool(self.linear_var.get()),
            marker_placer=bool(self.placer_var.get()),
            ik_weights=self._weights_dict(),
        )

    def _ready(self) -> bool:
        if not (self.template_model_var.get() and self.trc_var.get()
                and self.destination_var.get()):
            messagebox.showwarning(
                "Not ready",
                "Model, TRC and output are needed first.", parent=self)
            return False
        if not self.marker_weight_vars:
            messagebox.showwarning(
                "Not ready", "Press 'Load Markers from TRC' first.", parent=self)
            return False
        return True

    def _write_setup(self, path=None) -> str:
        """Build the ScaleTool and write its setup WITHOUT scaling."""
        _os_utils = _opensim_utils()
        kw = self._scale_kwargs()
        dest_dir = os.path.dirname(kw["scaled_model_path"]) or os.getcwd()
        os.makedirs(dest_dir, exist_ok=True)
        return _os_utils.scale_model(
            setup_xml_path=path or os.path.join(dest_dir, "scale_setup.xml"),
            run=False, **kw)

    def _view_setup_xml(self) -> None:
        """Show the setup that Run would use, before anything is written."""
        if not self._ready():
            return
        import tempfile
        try:
            tmp = os.path.join(tempfile.mkdtemp(prefix="bioscout_scale_"),
                               "scale_setup.xml")
            path = self._write_setup(tmp) or tmp
            text = io.open(path, encoding="utf-8", errors="replace").read()
        except Exception as e:                                     # noqa: BLE001
            logger.error(f"could not build the setup: {e}", exc_info=True)
            messagebox.showerror("Error", f"Could not build the setup:\n\n{e}",
                                 parent=self)
            return

        win = ctk.CTkToplevel(self)
        win.title("ScaleTool setup (preview — not saved)")
        win.geometry("1000x700")
        win.transient(self)
        box = ctk.CTkTextbox(win, font=("Consolas", 11), wrap="none")
        box.pack(fill="both", expand=True, padx=10, pady=(10, 4))
        box.insert("1.0", text)
        box.configure(state="disabled")

        bar = ctk.CTkFrame(win, fg_color="transparent")
        bar.pack(fill="x", padx=10, pady=(0, 10))

        def _save_it():
            win.destroy()
            self._save_setup_xml()

        ctk.CTkButton(bar, text="Save to the iteration folder",
                      font=("Segoe UI", 13, "bold"), height=38,
                      command=_save_it).pack(side="left", padx=4)
        ctk.CTkButton(bar, text="Close", font=("Segoe UI", 13, "bold"),
                      height=38, fg_color="#555555", hover_color="#444444",
                      command=win.destroy).pack(side="right", padx=4)

    # ------------------------------------------------------------------
    def _save_setup_xml(self) -> None:
        """Write the Scale Tool setup into the iteration folder without running."""
        if not self._ready():
            return
        try:
            path = self._write_setup()
            if not path:
                raise RuntimeError("scale_model returned no setup path")
            self.status_callback(f"setup written: {path}", "success")
            self.status_label.configure(text=f"setup XML: {path}",
                                        text_color="#28a745")
            logger.info(f"scale setup written to {path}")
        except Exception as e:                                     # noqa: BLE001
            logger.error(f"could not write setup XML: {e}", exc_info=True)
            messagebox.showerror("Error", f"Could not write setup XML:\n\n{e}",
                                 parent=self)

    def _weights_dict(self) -> dict:
        """Weights for the Scale Tool — an unticked marker contributes 0.

        One control, not two: a "use" tick and a weight box are the same knob,
        and letting both exist lets them disagree.
        """
        out = {}
        for name, var in self.marker_weight_vars.items():
            use = self.marker_use_vars.get(name)
            if use is not None and not use.get():
                out[name] = 0.0
            else:
                try:
                    out[name] = float(var.get())
                except Exception:                                  # noqa: BLE001
                    out[name] = 1.0
        return out

    def fixed_markers(self) -> list:
        """Markers ticked as fixed to their parent frame in the output model."""
        return [n for n, v in self.marker_fixed_vars.items() if v.get()]

    def _apply_fixed_markers(self, model_path) -> int:
        """Write ``<fixed>`` into the scaled model's MarkerSet.

        A marker left free is re-registered by the MarkerPlacer at every
        subsequent scaling; a fixed one keeps the offset the generic model
        states. Which it should be is a decision about THIS model, so it is
        made here and written into the file — not carried in the GUI where it
        would be lost the moment the tab closes.

        Returns how many markers were changed. Never raises: a marker flag is
        cosmetic to the mechanics, and losing a finished scaled model over it
        would be absurd.
        """
        try:
            fixed = set(self.fixed_markers())
            if not os.path.isfile(model_path):
                return 0
            tree = ET.parse(model_path)
            root = tree.getroot()
            n = 0
            for mk in root.iter("Marker"):
                name = mk.get("name")
                if name is None:
                    continue
                want = "true" if name in fixed else "false"
                node = mk.find("fixed")
                if node is None:
                    node = ET.SubElement(mk, "fixed")
                if (node.text or "").strip().lower() != want:
                    node.text = want
                    n += 1
            if n:
                tree.write(model_path, encoding="utf-8", xml_declaration=True)
                logger.info(f"set <fixed> on {n} marker(s) in "
                            f"{os.path.basename(model_path)}")
            return n
        except Exception as e:                                     # noqa: BLE001
            logger.warning(f"could not write marker <fixed> flags: {e}")
            return 0

    def _link_geometry(self, model_path, template_model) -> None:
        """Link the generic model's Geometry/ beside the scaled model.

        A scaled .osim keeps the generic's relative mesh names, but it is
        written into the iteration folder, which has none — so the OpenSim GUI
        opens it with no bones and no muscle paths and it looks broken when it
        is fine. A LINK, not a copy: the meshes are tens of megabytes and
        identical for every iteration.
        """
        try:
            src_geo = os.path.join(os.path.dirname(os.path.abspath(template_model)),
                                   "Geometry")
            if not os.path.isdir(src_geo):
                up = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(template_model))),
                    "Geometry")
                if not os.path.isdir(up):
                    return
                src_geo = up
            dst = os.path.join(os.path.dirname(os.path.abspath(model_path)), "Geometry")
            if os.path.isdir(dst) or os.path.islink(dst):
                return
            if os.name == "nt":
                import _winapi
                _winapi.CreateJunction(src_geo, dst)
            else:
                os.symlink(src_geo, dst, target_is_directory=True)
            logger.info(f"linked Geometry/ -> {src_geo}")
        except Exception as e:                                     # noqa: BLE001
            logger.warning(f"could not link Geometry/: {e}")

    def _browse_template_model(self) -> None:
        """Browse for template model file."""
        file = filedialog.askopenfilename(
            title="Select Template OpenSim Model",
            filetypes=[("OpenSim Models", "*.osim"), ("All Files", "*.*")]
        )
        if file:
            self.template_model_var.set(file)
            logger.info(f"Template model selected: {file}")

    def _browse_markerset(self) -> None:
        """Browse for markerset file."""
        file = filedialog.askopenfilename(
            title="Select Markerset File",
            filetypes=[("XML Files", "*.xml"), ("All Files", "*.*")]
        )
        if file:
            self.markerset_var.set(file)
            logger.info(f"Markerset selected: {file}")

    def _browse_trc_file(self) -> None:
        """Browse for a TRC, opening where the current one lives.

        The dialog used to open at the process working directory, which after a
        scaling run is somewhere inside the last iteration — several clicks
        from the session you are actually working on.
        """
        _cur = self.trc_var.get()
        if _cur and os.path.isfile(_cur):
            _start = os.path.dirname(_cur)
        else:
            _sd = self._session_dir()
            _exp = (_sd / "2_experimental") if _sd else None
            _start = str(_exp) if (_exp and _exp.is_dir()) else (
                str(self._sims() or "") or os.getcwd())
        file = filedialog.askopenfilename(
            title="Select TRC File for Scaling",
            initialdir=_start,
            filetypes=[("TRC Files", "*.trc"), ("All Files", "*.*")]
        )
        if file:
            self.trc_var.set(file)
            logger.info(f"TRC file selected: {file}")

    def _browse_destination(self) -> None:
        """Browse for destination file path."""
        # Get current template model name to suggest output name
        template_path = self.template_model_var.get()
        initial_name = "scaled_model.osim"
        initial_dir = ""

        if template_path and os.path.exists(template_path):
            initial_dir = os.path.dirname(template_path)
            base_name = os.path.splitext(os.path.basename(template_path))[0]
            initial_name = f"{base_name}_scaled.osim"

        file_path = filedialog.asksaveasfilename(
            title="Select Output Model Path",
            initialdir=initial_dir,
            initialfile=initial_name,
            defaultextension=".osim",
            filetypes=[("OpenSim Models", "*.osim"), ("All Files", "*.*")]
        )
        if file_path:
            self.destination_var.set(file_path)
            logger.info(f"Destination file selected: {file_path}")

    def _load_trc_markers(self) -> None:
        """Load markers from TRC file."""
        trc_path = self.trc_var.get()
        if not trc_path or not os.path.exists(trc_path):
            messagebox.showwarning("Error", "Please select a valid TRC file")
            return

        try:
            markers = self._parse_trc_file(trc_path)
            if not markers:
                messagebox.showwarning("Error", "No markers found in TRC file")
                return

            self.markers_from_trc = markers
            self._populate_markers_panel()
            self.load_btn.configure(
                text=f"Reload Markers from TRC  ({len(markers)} loaded)")
            self.status_callback(f"Loaded {len(markers)} markers from TRC", "success")
            logger.info(f"Loaded {len(markers)} markers from {trc_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to parse TRC file: {str(e)}")
            logger.error(f"TRC parsing error: {e}", exc_info=True)

    def _parse_trc_file(self, trc_path: str) -> dict:
        """
        Parse TRC file and extract marker names.

        Args:
            trc_path: Path to TRC file

        Returns:
            Dictionary of marker_name -> frame_count
        """
        markers = {}
        try:
            with open(trc_path, 'r') as f:
                lines = f.readlines()

            # A TRC header is two lines:
            #
            #   Frame#<tab>Time<tab>GLAB<tab><tab><tab>RFHD<tab><tab><tab>...
            #   <tab><tab>X1<tab>Y1<tab>Z1<tab>X2<tab>Y2<tab>Z2<tab>...
            #
            # The MARKER NAMES are on the Frame# line — one name then two empty
            # columns, because each marker owns three data columns. The second
            # line holds the component labels.
            #
            # This read lines[i + 1], i.e. the component line, so a 73-marker
            # file produced 219 "markers" called X1, Y1, Z1, X2 ... and the
            # weights panel filled with names no model has. Splitting on TAB
            # (not whitespace) is what keeps the empty columns from collapsing.
            for i, line in enumerate(lines):
                if line.strip().startswith('Frame#'):
                    parts = line.rstrip('\r\n').split('\t')
                    if len(parts) < 3:                 # space-aligned variant
                        parts = line.split()
                    for part in parts:
                        name = part.strip()
                        if not name or name in ('Frame#', 'Time'):
                            continue
                        markers.setdefault(name, 0)
                    break

            return markers

        except Exception as e:
            logger.error(f"Error parsing TRC file: {e}")
            raise

    def _populate_markers_panel(self) -> None:
        """Fill both panes: scaling weights on the left, fixed flags on the right.

        Two questions, two columns. The left one is about THIS scaling run —
        how much a marker pulls, and whether it takes part at all. The right
        one is about the model that comes OUT — whether the marker stays where
        the generic model puts it instead of being re-registered. They used to
        share one column, which is why the tab had a screen of empty grey next
        to a cramped list.
        """
        for widget in self.markers_frame.winfo_children():
            widget.destroy()
        for widget in self.fixed_frame.winfo_children():
            widget.destroy()

        self.marker_weight_vars = {}
        prev_use = dict(getattr(self, "marker_use_vars", {}) or {})
        prev_fixed = dict(getattr(self, "marker_fixed_vars", {}) or {})
        self.marker_use_vars = {}
        self.marker_fixed_vars = {}

        if not self.markers_from_trc:
            self.empty_label = ctk.CTkLabel(
                self.markers_frame,
                text="Load a TRC file to see available markers",
                text_color="#888888", font=("Segoe UI", 9))
            self.empty_label.pack(pady=20)
            ctk.CTkLabel(self.fixed_frame, text="", font=("Segoe UI", 9)).pack(pady=20)
            return

        names = sorted(self.markers_from_trc.keys())

        # ---- left pane header ------------------------------------------
        head = ctk.CTkFrame(self.markers_frame, fg_color="transparent")
        head.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(head, text="use", font=("Segoe UI", 9, "bold"),
                     width=40).pack(side="left")
        ctk.CTkLabel(head, text="marker", font=("Segoe UI", 9, "bold"),
                     anchor="w").pack(side="left", padx=(4, 0))
        ctk.CTkLabel(head, text="weight", font=("Segoe UI", 9, "bold"),
                     width=80).pack(side="right")

        # ---- right pane header -----------------------------------------
        fhead = ctk.CTkFrame(self.fixed_frame, fg_color="transparent")
        fhead.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(fhead, text="fixed", font=("Segoe UI", 9, "bold"),
                     width=48).pack(side="left")
        ctk.CTkLabel(fhead, text="marker", font=("Segoe UI", 9, "bold"),
                     anchor="w").pack(side="left", padx=(4, 0))

        _all_fixed = ctk.BooleanVar(value=False)

        def _toggle_all_fixed():
            for _v in self.marker_fixed_vars.values():
                _v.set(_all_fixed.get())

        ctk.CTkCheckBox(fhead, text="all", variable=_all_fixed, width=40,
                        font=("Segoe UI", 9),
                        command=_toggle_all_fixed).pack(side="right", padx=4)

        for marker_name in names:
            # ---------------- left: use + weight
            row = ctk.CTkFrame(self.markers_frame)
            row.pack(fill="x", padx=8, pady=1)

            default_weight = marker_weights.get(marker_name, 1.0)
            use_var = ctk.BooleanVar(
                value=bool(prev_use[marker_name].get())
                if marker_name in prev_use else True)
            self.marker_use_vars[marker_name] = use_var

            weight_var = ctk.DoubleVar(value=default_weight)
            self.marker_weight_vars[marker_name] = weight_var

            weight_entry = ctk.CTkEntry(row, textvariable=weight_var, width=80,
                                        font=("Segoe UI", 9))

            def _sync(name=marker_name, entry=weight_entry, v=use_var):
                # An unused marker's weight is not a number you can edit — it
                # is zero. Greying the box says so without a second control.
                entry.configure(state="normal" if v.get() else "disabled")

            ctk.CTkCheckBox(row, text="", variable=use_var, width=28,
                            command=_sync).pack(side="left", padx=(6, 2))
            ctk.CTkLabel(row, text=marker_name, font=("Segoe UI", 9),
                         anchor="w").pack(side="left", padx=4)
            weight_entry.pack(side="right", padx=6, pady=2)

            # ---------------- right: fixed to parent frame
            frow = ctk.CTkFrame(self.fixed_frame)
            frow.pack(fill="x", padx=8, pady=1)
            fixed_var = ctk.BooleanVar(
                value=bool(prev_fixed[marker_name].get())
                if marker_name in prev_fixed else False)
            self.marker_fixed_vars[marker_name] = fixed_var
            ctk.CTkCheckBox(frow, text="", variable=fixed_var,
                            width=28).pack(side="left", padx=(6, 2))
            ctk.CTkLabel(frow, text=marker_name, font=("Segoe UI", 9),
                         anchor="w").pack(side="left", padx=4)

    def _reset_weights(self) -> None:
        """Reset all weights to default values."""
        for marker_name, weight_var in self.marker_weight_vars.items():
            default_weight = marker_weights.get(marker_name, 1.0)
            weight_var.set(default_weight)
            use = self.marker_use_vars.get(marker_name)
            if use is not None:
                use.set(True)
        self.status_callback("Weights reset to default", "success")
        logger.info("Marker weights reset to default")

    def _run_scaling(self) -> None:
        """Run the scaling process."""
        # Validation
        if not self.template_model_var.get() or not os.path.exists(self.template_model_var.get()):
            messagebox.showerror("Error", "Please select a valid template model")
            return

        if not self.trc_var.get() or not os.path.exists(self.trc_var.get()):
            messagebox.showerror("Error", "Please select a valid TRC file")
            return

        if not self.destination_var.get():
            messagebox.showerror("Error", "Please specify an output model path (.osim file)")
            return

        # Validate destination path ends with .osim
        dest_path = self.destination_var.get()
        if not dest_path.lower().endswith('.osim'):
            messagebox.showerror("Error", "Output path must end with .osim")
            return

        # Create the destination directory rather than refusing. The output
        # normally lands in 3_iterations/<name>/, which does not exist until
        # something writes there — so a freshly added iteration failed this
        # check and the only way forward was to go and make the folder by hand.
        dest_dir = os.path.dirname(dest_path)
        if dest_dir and not os.path.exists(dest_dir):
            try:
                os.makedirs(dest_dir, exist_ok=True)
                logger.info(f"created destination directory {dest_dir}")
            except Exception as e:
                messagebox.showerror(
                    "Error", f"Could not create destination directory:\n{dest_dir}\n\n{e}")
                return

        if not self.marker_weight_vars:
            messagebox.showerror("Error", "Please load markers from TRC first")
            return

        # Disable buttons
        self.scale_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")

        # Get weights dictionary
        weights_dict = self._weights_dict()

        # Run in background thread
        self.scaling_thread = threading.Thread(
            target=self._run_scaling_thread,
            args=(
                self.template_model_var.get(),
                self.markerset_var.get() or None,
                self.trc_var.get(),
                self.destination_var.get(),
                weights_dict
            ),
            daemon=True
        )
        self.scaling_thread.start()
        self.status_callback("Scaling in progress...", "info")

    def _run_scaling_thread(self, template_model, markerset, trc_file, output_file_path, weights):
        """Scale through openSim.scale_model — the same call the pipeline makes.

        The tab used to drive its own ModelScaler, which meant the GUI and the
        pipeline could hand you two different models from the same inputs. This
        one builds the MeasurementSet from marker pairs, adds the *WK joint
        centres to a scaling-only copy of the static TRC (the model has them,
        no TRC does), drops markers the MarkerPlacer segfaults on, and verifies
        afterwards that the segments actually changed size.
        """
        try:
            _os_utils = _opensim_utils()

            self.status_label.configure(text="Building ScaleTool setup...",
                                        text_color="#ffc107")
            self.status_callback("Building ScaleTool setup...", "info")

            dest_dir = os.path.dirname(output_file_path) or os.getcwd()
            os.makedirs(dest_dir, exist_ok=True)

            self.status_label.configure(text="Running ScaleTool...",
                                        text_color="#ffc107")
            self.status_callback("Running OpenSim ScaleTool...", "info")

            _os_utils.scale_model(
                generic_opensim_model_path=template_model,
                static_trc_path=trc_file,
                scaled_model_path=output_file_path,
                marker_set_file=markerset,
                linear_scaling=bool(self.linear_var.get()),
                marker_placer=bool(self.placer_var.get()),
                ik_weights=weights,
                setup_xml_path=os.path.join(dest_dir, "scale_setup.xml"),
            )

            if not os.path.exists(output_file_path):
                raise RuntimeError(
                    f"ScaleTool ran but wrote no model at {output_file_path}")

            # Two things the scaled model needs before it is usable, both cheap
            # and both easy to forget by hand.
            self._apply_fixed_markers(output_file_path)
            self._link_geometry(output_file_path, template_model)

            self.status_callback("✓ Model scaling completed successfully", "success")
            self.status_label.configure(text=f"Scaled: {output_file_path}",
                                        text_color="#28a745")
            logger.info(f"Scaled model saved to: {output_file_path}")
            messagebox.showinfo(
                "Success",
                f"Scaling completed.\n\nModel:  {output_file_path}\n"
                f"Setup:  {os.path.join(dest_dir, 'scale_setup.xml')}\n"
                f"Factors: {os.path.join(dest_dir, 'scale_factors.xml')}\n\n"
                f"This is the ScaleTool only — the muscle-optimised and MVIC "
                f"models the pipeline also builds are not made here.",
                parent=self)

        except Exception as e:
            error_msg = f"Scaling failed: {str(e)}"
            self.status_callback(error_msg, "error")
            self.status_label.configure(text=f"Error: {str(e)[:70]}",
                                        text_color="#dc3545")
            logger.error(f"Scaling error: {e}", exc_info=True)
            messagebox.showerror("Error", f"Model scaling failed:\n\n{str(e)}")

        finally:
            self.scale_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")

    def _stop_scaling(self) -> None:
        """Stop the scaling process."""
        self.status_callback("Scaling cancelled", "warning")
        self.status_label.configure(text="Cancelled", text_color="#ffc107")
        logger.info("Model scaling cancelled by user")
        self.scale_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
