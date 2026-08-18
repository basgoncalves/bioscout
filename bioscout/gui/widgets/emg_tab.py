"""bioscout.gui.widgets.emg_tab — one EMG tab, sub-tabs on the left.

"EMG Processing" and "EMG Analysis" were two top-level tabs doing halves of the
same job: look at the signals, filter them, then ask what is in them. Merged
here under one entry in the Data curation section, with a small left rail of
sub-tabs:

    Filtering    — EMGProcessingTab in its slim ``show_mvc=False`` shape:
                   plot, filter and inspect channels. The MVC/normalisation
                   side is deliberately absent — normalisation is a
                   session-level decision the export/pipeline makes, and
                   offering it here too invited two different answers.
    Analysis     — the existing EMGAnalysisTab (frequency report + NMF
                   synergies)

The children are the UNCHANGED existing widgets — this module is only the
frame around them. Each is created lazily on first visit (EMGProcessing pulls
matplotlib + scipy machinery; paying that on app start bought nothing), and a
child that fails to import degrades to a message in its pane rather than
taking the whole tab down.

Why a left rail and not CTkTabview: the main window already navigates with a
left column of buttons, and sub-navigation that mirrors it reads as one system.
CTkTabview puts a segmented button on top, which at this tab's density collides
with the children's own toolbars.
"""
import customtkinter as ctk

from utils.logger import logger


class _LazyPane:
    """One sub-tab: a loader that runs once, and the frame it fills."""

    def __init__(self, title, loader):
        self.title = title
        self.loader = loader     # (parent) -> widget, or raises
        self.widget = None
        self.failed = None


class EMGTab(ctk.CTkFrame):
    """The merged EMG tab. Standard (parent, config_manager, status_callback)
    signature so it registers like every other tab."""

    def __init__(self, parent, config_manager=None, status_callback=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.status_callback = status_callback
        self.project_dir = None

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # -- left rail ----------------------------------------------------
        rail = ctk.CTkFrame(self, width=150, corner_radius=0)
        rail.grid(row=0, column=0, sticky="nsw")
        rail.grid_propagate(False)
        ctk.CTkLabel(rail, text="EMG", font=("Segoe UI", 13, "bold"),
                     anchor="w").pack(fill="x", padx=12, pady=(12, 6))

        # -- content ------------------------------------------------------
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self.panes = {
            "Filtering": _LazyPane("Filtering", self._make_filtering),
            "Analysis": _LazyPane("Analysis", self._make_analysis),
        }
        self._buttons = {}
        for name in self.panes:
            btn = ctk.CTkButton(
                rail, text=name, height=32, anchor="w",
                fg_color="#2d2d2d", hover_color="#3d3d3d",
                border_width=1, border_color="#404040",
                command=lambda n=name: self.show(n))
            btn.pack(fill="x", padx=8, pady=3)
            self._buttons[name] = btn

        ctk.CTkLabel(
            rail, wraplength=130, justify="left", font=("Segoe UI", 9),
            text_color="#7a8290",
            text="Filtering: plot, filter and inspect channels.\n\n"
                 "Analysis: frequency content and NMF synergies.\n\n"
                 "EMG normalisation lives in C3D Export / the pipeline.",
        ).pack(fill="x", padx=10, pady=(12, 8))

        self._current = None
        self.show("Filtering")

    # ------------------------------------------------------------ children
    def _make_filtering(self, parent):
        from gui.widgets.emg_processing_tab import EMGProcessingTab
        return EMGProcessingTab(parent, self.config_manager,
                                self.status_callback, show_mvc=False)

    def _make_analysis(self, parent):
        from gui.widgets.emg_analysis_tab import EMGAnalysisTab
        return EMGAnalysisTab(parent, self.config_manager,
                              self.status_callback)

    # ------------------------------------------------------------- switching
    def show(self, name):
        pane = self.panes.get(name)
        if pane is None:
            return
        if pane.widget is None and pane.failed is None:
            try:
                pane.widget = pane.loader(self.content)
                pane.widget.grid(row=0, column=0, sticky="nsew")
                # a child created after the project was broadcast still needs it
                if self.project_dir and hasattr(pane.widget, "set_project_dir"):
                    try:
                        pane.widget.set_project_dir(self.project_dir)
                    except Exception:                          # noqa: BLE001
                        pass
            except Exception as exc:                           # noqa: BLE001
                pane.failed = str(exc)
                logger.error(f"EMG sub-tab '{name}' failed to load: {exc}")
                pane.widget = ctk.CTkLabel(
                    self.content, text=f"{name} unavailable:\n{exc}",
                    font=("Segoe UI", 11), text_color="#dc3545")
                pane.widget.grid(row=0, column=0)
        for other in self.panes.values():
            if other.widget is not None and other is not pane:
                other.widget.grid_remove()
        if pane.widget is not None:
            pane.widget.grid()
        for n, btn in self._buttons.items():
            btn.configure(fg_color="#1f538d" if n == name else "#2d2d2d")
        self._current = name

    # ------------------------------------------------------------ broadcast
    def set_project_dir(self, project_dir):
        """Forward the project to whichever children exist (and remember it
        for the ones not built yet — see show())."""
        self.project_dir = project_dir
        for pane in self.panes.values():
            w = pane.widget
            if w is not None and hasattr(w, "set_project_dir"):
                try:
                    w.set_project_dir(project_dir)
                except Exception:                              # noqa: BLE001
                    pass


__all__ = ["EMGTab"]
