"""Results Viewer Tab - View and analyze results with checkbox selection and session integration."""

import customtkinter as ctk
from pathlib import Path
import sys
import numpy as np
import threading

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.config_manager import ConfigManager
from utils.logger import logger

try:
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    from utils import load_any_data_file
    HAS_UTILS = True
except ImportError:
    HAS_UTILS = False


class ResultsViewerTab(ctk.CTkFrame):
    """Tab for viewing and analyzing analysis results with session-level support."""

    def __init__(self, parent, config_manager: ConfigManager, status_callback):
        """Initialize Results Viewer Tab."""
        super().__init__(parent)
        self.config_manager = config_manager
        self.status_callback = status_callback
        self.session_dir = None
        self.trials_files = {}  # trial_name -> [file_paths]
        self.file_vars = {}  # file_path -> BooleanVar
        self.canvas = None
        self.fig = None
        self.toolbar = None

        self._create_widgets()

    def set_session_dir(self, session_dir: str):
        """Receive session directory from main window."""
        self.session_dir = Path(session_dir) if session_dir else None
        if self.session_dir and self.session_dir.exists():
            self.session_label.configure(text=f"Session: {self.session_dir.name}")
            self._scan_trials_and_files()
            logger.info(f"Results Viewer: Session set to {self.session_dir}")
        else:
            self.session_label.configure(text="Session: Not set")
            self._clear_files()

    def _create_widgets(self) -> None:
        """Create UI widgets."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # TOP: Session Info
        top_frame = ctk.CTkFrame(self)
        top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        top_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top_frame, text="Results Viewer", font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )

        self.session_label = ctk.CTkLabel(top_frame, text="Session: Not set", font=("Segoe UI", 10, "bold"), text_color="#28a745")
        self.session_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 5))

        # MAIN: Content
        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=0, minsize=300)
        main_frame.grid_columnconfigure(1, weight=1)

        # LEFT: Trial and File Selection
        left_panel = ctk.CTkFrame(main_frame, corner_radius=8)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=5)
        left_panel.grid_rowconfigure(1, weight=1)
        left_panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(left_panel, text="Select File to Plot", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 5)
        )

        # File selection frame (scrollable)
        self.files_frame = ctk.CTkScrollableFrame(left_panel)
        self.files_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        # Plot options
        options_frame = ctk.CTkFrame(left_panel)
        options_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        options_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(options_frame, text="Plot Options", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(5, 5))

        self.subplot_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            options_frame,
            text="Separate Subplots",
            variable=self.subplot_var,
            font=("Segoe UI", 10)
        ).pack(anchor="w", padx=5, pady=2)

        ctk.CTkButton(
            options_frame,
            text="Load & Plot",
            fg_color="#28a745",
            command=self._load_and_plot
        ).pack(fill="x", padx=0, pady=(10, 0))

        # RIGHT: Plot display
        right_panel = ctk.CTkFrame(main_frame, corner_radius=8)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=5)
        right_panel.grid_rowconfigure(0, weight=1)
        right_panel.grid_rowconfigure(1, weight=0)
        right_panel.grid_columnconfigure(0, weight=1)

        # Plot area
        self.plot_frame = ctk.CTkFrame(right_panel)
        self.plot_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.plot_frame.grid_rowconfigure(0, weight=1)
        self.plot_frame.grid_columnconfigure(0, weight=1)

        self.plot_label = ctk.CTkLabel(self.plot_frame, text="Load a file to view plot", text_color="gray")
        self.plot_label.grid(row=0, column=0, sticky="nsew")

        # Control buttons below plot
        button_frame = ctk.CTkFrame(right_panel)
        button_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 5))
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            button_frame,
            text="Save Figure",
            fg_color="#0084ff",
            command=self._save_figure,
            width=100
        ).grid(row=0, column=0, sticky="ew", padx=(0, 5))

        ctk.CTkButton(
            button_frame,
            text="Clear",
            fg_color="#666666",
            command=self._clear_plot,
            width=100
        ).grid(row=0, column=1, sticky="ew", padx=(5, 0))

    def _scan_trials_and_files(self):
        """Scan session for trials and their data files."""
        self._clear_files()

        if not self.session_dir:
            return

        try:
            # Scan for trial folders
            for trial_folder in sorted(self.session_dir.iterdir()):
                if trial_folder.is_dir() and not trial_folder.name.startswith('.'):
                    # Find data files in trial
                    data_files = self._find_data_files(trial_folder)
                    if data_files:
                        trial_name = trial_folder.name
                        self.trials_files[trial_name] = sorted(data_files)

            # Populate checkboxes
            for trial_name in sorted(self.trials_files.keys()):
                # Trial label
                trial_label = ctk.CTkLabel(
                    self.files_frame,
                    text=f"📊 {trial_name}",
                    font=("Segoe UI", 10, "bold")
                )
                trial_label.pack(anchor="w", padx=5, pady=(10, 3))

                # Files for this trial
                for file_path in self.trials_files[trial_name]:
                    var = ctk.BooleanVar(value=False)
                    checkbox = ctk.CTkCheckBox(
                        self.files_frame,
                        text=f"  📄 {file_path.name}",
                        variable=var,
                        font=("Segoe UI", 9),
                        command=lambda fp=file_path, v=var: self._on_file_selected(fp, v)
                    )
                    checkbox.pack(anchor="w", padx=10, pady=2)
                    self.file_vars[str(file_path)] = var

            self.status_callback(f"Found {len(self.trials_files)} trials with data files", "success")

        except Exception as e:
            logger.error(f"Error scanning trials: {e}")
            self.status_callback(f"Error: {str(e)[:50]}", "error")

    def _find_data_files(self, folder: Path) -> list:
        """Find all data files in a folder."""
        data_extensions = {'.mot', '.sto', '.csv', '.trc'}
        files = []

        try:
            for file in folder.glob('*'):
                if file.suffix.lower() in data_extensions:
                    files.append(file)
        except Exception as e:
            logger.error(f"Error finding files in {folder}: {e}")

        return files

    def _clear_files(self):
        """Clear file list."""
        for widget in self.files_frame.winfo_children():
            widget.destroy()
        self.file_vars.clear()
        self.trials_files.clear()

    def _on_file_selected(self, file_path: Path, var: ctk.BooleanVar):
        """Handle file selection - allows multiple files."""
        # Allow multiple selection - don't deselect others
        selected_files = [p for p, v in self.file_vars.items() if v.get()]

        if selected_files:
            self.status_callback(f"Selected: {len(selected_files)} file(s)", "success")
        else:
            self.status_callback("No files selected", "info")

    def _load_and_plot(self) -> None:
        """Load files and generate plot."""
        selected_files = [Path(p) for p, v in self.file_vars.items() if v.get()]

        if not selected_files:
            self.status_callback("Please select at least one file", "warning")
            return

        if not HAS_MATPLOTLIB:
            self.status_callback("Matplotlib not installed", "error")
            return

        # Run in background thread
        thread = threading.Thread(target=self._load_and_plot_thread, args=(selected_files,), daemon=True)
        thread.start()

    def _load_and_plot_thread(self, selected_files: list) -> None:
        """Load and plot multiple files in background thread."""
        try:
            if not HAS_UTILS:
                self.status_callback("Utils module not available", "error")
                return

            self.status_callback(f"Loading {len(selected_files)} file(s)...", "info")

            # Load all selected files
            all_data = {}  # file_name -> (data, labels)
            all_labels = {}

            for file_path in selected_files:
                try:
                    # Try different loading methods based on file type
                    if file_path.suffix.lower() == '.mot':
                        plot_data, labels = self._load_mot_file(file_path)
                    else:
                        # Use generic loader
                        data = load_any_data_file(str(file_path))
                        if isinstance(data, dict) and 'data' in data:
                            plot_data = data['data']
                            labels = data.get('labels', [])
                        else:
                            self.status_callback(f"Could not parse {file_path.name}", "error")
                            continue

                    if plot_data is None or plot_data.size == 0:
                        self.status_callback(f"{file_path.name} contains no data", "warning")
                        continue

                    all_data[file_path.name] = plot_data
                    all_labels[file_path.name] = labels

                except Exception as e:
                    logger.error(f"Error loading {file_path.name}: {e}")
                    self.status_callback(f"Error loading {file_path.name}: {str(e)[:30]}", "error")

            if not all_data:
                self.status_callback("No files loaded successfully", "error")
                return

            # Find common columns
            common_labels = self._find_common_columns(all_labels)

            if not common_labels:
                self.status_callback("No common columns found - displaying sad platypus", "warning")
                self._show_sad_platypus()
                return

            # Create plot with common columns
            use_subplots = self.subplot_var.get()
            self._plot_data(all_data, all_labels, common_labels, use_subplots)
            self.status_callback(f"Plot generated with {len(common_labels)} common columns", "success")

        except Exception as e:
            self.status_callback(f"Load error: {str(e)[:50]}", "error")
            logger.error(f"Load and plot error: {e}")

    def _load_mot_file(self, mot_file: Path) -> tuple:
        """Load MOT file and return (data, labels)."""
        try:
            data = []
            labels = []
            in_data = False

            with open(mot_file, 'r') as f:
                for line in f:
                    line = line.strip()

                    # Skip empty lines and comments
                    if not line:
                        continue

                    # Check for end of header
                    if line.lower().startswith("endheader"):
                        in_data = True
                        continue

                    # Extract labels from line before data starts (if present)
                    if in_data and not any(c.isdigit() or c in '.-e' for c in line.split()[0]):
                        # This might be a label line
                        labels = line.split()
                        continue

                    # Parse data lines
                    if in_data:
                        try:
                            values = [float(x) for x in line.split()]
                            if len(values) > 1:
                                # Skip first column (time)
                                data.append(values[1:])
                        except (ValueError, IndexError):
                            # Skip malformed lines
                            continue

            if data:
                return np.array(data), labels[1:] if labels else []
            return None, []

        except Exception as e:
            logger.error(f"Error loading MOT file: {e}")
            return None, []

    def _find_common_columns(self, all_labels: dict) -> list:
        """Find common column labels across all loaded files."""
        if not all_labels:
            return []

        # Convert all labels to sets and find intersection
        label_sets = []
        for labels in all_labels.values():
            # Clean labels (remove empty strings, convert to lowercase for comparison)
            clean_labels = [str(l).strip() for l in labels if l]
            if clean_labels:
                label_sets.append(set(clean_labels))

        if not label_sets:
            return []

        # Find common labels (case-insensitive intersection)
        common = label_sets[0]
        for label_set in label_sets[1:]:
            common = common.intersection(label_set)

        # Return sorted list for consistent ordering
        return sorted(list(common))

    def _show_sad_platypus(self) -> None:
        """Display sad platypus image when no common columns exist."""
        try:
            # Clear previous plot
            for widget in self.plot_frame.winfo_children():
                if isinstance(widget, ctk.CTkLabel) and widget == self.plot_label:
                    continue
                widget.destroy()

            platypus_path = Path("C:\\Git\\powerlifing_model_clean\\code\\tests\\app\\utils\\platypus_sad.jpg")

            if not platypus_path.exists():
                self.plot_label.configure(text="❌ No common columns found\n(sad platypus image not found)")
                self.plot_label.grid(row=0, column=0, sticky="nsew")
                return

            # Try to load and display the image using PIL
            try:
                from PIL import Image, ImageTk
                img = Image.open(platypus_path)

                # Scale image to fit the plot area (max 800x600)
                img.thumbnail((800, 600), Image.Resampling.LANCZOS)

                # Convert to PhotoImage
                photo = ImageTk.PhotoImage(img)

                # Display in label
                label = ctk.CTkLabel(self.plot_frame, image=photo, text="")
                label.image = photo  # Keep a reference
                label.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

            except ImportError:
                self.plot_label.configure(text="❌ No common columns found\n(PIL not available for image display)")
                self.plot_label.grid(row=0, column=0, sticky="nsew")

        except Exception as e:
            logger.error(f"Error displaying sad platypus: {e}")
            self.plot_label.configure(text=f"❌ No common columns found\n(Error: {str(e)[:30]})")
            self.plot_label.grid(row=0, column=0, sticky="nsew")

    def _plot_data(self, all_data: dict, all_labels: dict, common_labels: list, use_subplots: bool = False) -> None:
        """Plot multiple files with common columns and zoom support."""
        try:
            # Clear previous plot
            for widget in self.plot_frame.winfo_children():
                if isinstance(widget, ctk.CTkLabel) and widget == self.plot_label:
                    continue
                widget.destroy()

            num_cols = len(common_labels)
            num_files = len(all_data)

            # Better figure sizing based on number of plots and files
            if use_subplots:
                # Each column gets its own subplot (3 per row)
                num_rows = max(1, (num_cols + 2) // 3)
                # Increase height based on rows AND number of files
                fig_height = max(6, num_rows * 2.5 + (num_files - 1) * 0.5)
                fig_width = max(14, 12)
                fig = Figure(figsize=(fig_width, fig_height), dpi=100)

                for idx, col_label in enumerate(common_labels):
                    ax = fig.add_subplot(num_rows, 3, idx + 1)
                    time_samples = None

                    # Plot data from all files
                    colors = plt.cm.tab10(np.linspace(0, 1, num_files))
                    for file_idx, (file_name, data) in enumerate(all_data.items()):
                        # Find column index in this file
                        file_labels = all_labels[file_name]
                        try:
                            col_idx = [str(l).strip().lower() for l in file_labels].index(str(col_label).strip().lower())
                            time = np.arange(data.shape[0])
                            ax.plot(time, data[:, col_idx], linewidth=1.5, label=file_name, color=colors[file_idx], alpha=0.8)
                            if time_samples is None:
                                time_samples = len(time)
                        except (ValueError, IndexError):
                            logger.debug(f"Column {col_label} not in {file_name}")
                            continue

                    ax.set_title(str(col_label), fontsize=10, fontweight='bold')
                    ax.grid(True, alpha=0.3)
                    ax.set_xlabel("Sample", fontsize=9)
                    ax.set_ylabel("Value", fontsize=9)

                    # Add legend to first subplot only
                    if idx == 0 and num_files > 1:
                        ax.legend(fontsize=8, loc='best')

            else:
                # All columns on single plot
                fig_height = max(6, 5 + (num_files - 1) * 0.5)
                fig = Figure(figsize=(14, fig_height), dpi=100)
                ax = fig.add_subplot(111)

                colors = plt.cm.tab10(np.linspace(0, 1, num_files * num_cols))
                color_idx = 0

                for file_name, data in all_data.items():
                    file_labels = all_labels[file_name]
                    time = np.arange(data.shape[0])

                    for col_label in common_labels:
                        try:
                            col_idx = [str(l).strip().lower() for l in file_labels].index(str(col_label).strip().lower())
                            label = f"{file_name}: {col_label}"
                            ax.plot(time, data[:, col_idx], linewidth=1.5, label=label, color=colors[color_idx], alpha=0.8)
                            color_idx += 1
                        except (ValueError, IndexError):
                            continue

                ax.set_xlabel("Sample", fontsize=11)
                ax.set_ylabel("Value", fontsize=11)
                ax.set_title(f"{num_files} file(s) - {num_cols} common columns", fontsize=12, fontweight='bold')
                ax.grid(True, alpha=0.3)

                # Add legend
                if num_files <= 3 and num_cols <= 5:
                    ax.legend(fontsize=9, loc='best', ncol=min(2, num_cols))

            fig.tight_layout()

            # Store figure reference
            self.fig = fig

            # Display in frame with zoom support
            self.canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
            self.canvas.draw()

            # Configure plot_frame for canvas and toolbar
            self.plot_frame.grid_rowconfigure(0, weight=1)
            self.plot_frame.grid_rowconfigure(1, weight=0)
            self.plot_frame.grid_columnconfigure(0, weight=1)

            # Add canvas
            self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

            # Enable zoom and pan tools
            try:
                from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
                self.toolbar = NavigationToolbar2Tk(self.canvas, self.plot_frame)
                self.toolbar.update()
                self.toolbar.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 5))
            except Exception as e:
                logger.debug(f"Could not add navigation toolbar: {e}")

        except Exception as e:
            self.plot_label.configure(text=f"Error rendering plot: {str(e)[:50]}")
            self.plot_label.grid(row=0, column=0, sticky="nsew")
            logger.error(f"Plot error: {e}")

    def _save_figure(self) -> None:
        """Save current figure to file."""
        if self.fig is None:
            self.status_callback("No plot to save", "warning")
            return

        try:
            from tkinter import filedialog
            file_path = filedialog.asksaveasfilename(
                title="Save Figure As",
                defaultextension=".png",
                filetypes=[
                    ("PNG Files", "*.png"),
                    ("PDF Files", "*.pdf"),
                    ("SVG Files", "*.svg"),
                ]
            )

            if file_path:
                self.fig.savefig(file_path, dpi=300, bbox_inches='tight')
                self.status_callback(f"Figure saved: {Path(file_path).name}", "success")
                logger.info(f"Figure saved to {file_path}")

        except Exception as e:
            self.status_callback(f"Save error: {str(e)[:50]}", "error")
            logger.error(f"Save figure error: {e}")

    def _clear_plot(self) -> None:
        """Clear the current plot."""
        # Clear all widgets in plot frame
        for widget in self.plot_frame.winfo_children():
            widget.destroy()

        self.plot_label.grid(row=0, column=0, sticky="nsew")
        self.fig = None
        self.canvas = None
        self.toolbar = None
        self.status_callback("Plot cleared", "info")
