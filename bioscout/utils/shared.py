"""
bioscout.utils.shared — small, dependency-light helpers needed across several
utils modules (analyse, analysis, emg, plotting, …).

Keeping them here (rather than in ``utils/__init__``) avoids import-order and
circular-import headaches: every module can do ``from bioscout.utils import
shared`` (or rely on the re-exports from ``utils/__init__``) without pulling in
the whole package.

Functions that depend on project-level globals (CODE_DIR, PRINT_TERMINAL, …)
read them lazily from ``bioscout.utils`` at call time, so they stay correct
after ``bioscout.Project`` re-points those globals at the active project.
"""
import os
import re
import sys
import time
import datetime

import numpy as np
import pandas as pd

# Trials are named "<type>_<number>" (e.g. Squat_35kg_01); this strips the
# trailing number so repetitions of the same task can be grouped/averaged.
DEFAULT_TRIAL_TYPE_PATTERN = r"(.+?)_(\d+)$"


def updir(path, levels=1):
    """Move up a directory path by a specified number of levels."""
    for _ in range(levels):
        path = os.path.dirname(path)
    return path


def print_to_log(message, terminal=None, trial=None):
    """Print a message to the console and append it to the package log file.

    Args:
        message (str): The message to print and log.
        terminal (bool|None): Force console echo; ``None`` falls back to
            ``utils.PRINT_TERMINAL``.
        trial (str): Optional trial name shown before the message.
    """
    from bioscout import utils as _u  # lazy: globals are re-pointed at runtime
    if terminal is None:
        terminal = getattr(_u, 'PRINT_TERMINAL', False)
    code_dir = getattr(_u, 'CODE_DIR', os.path.dirname(os.path.abspath(__file__)))

    timestamp = time.strftime('%d.%m.%Y_%H:%M:%S', time.localtime()) + f":{int((time.time() % 1) * 1000):03d}"
    prefix = f'[{trial}] ' if trial else ''

    with open(os.path.join(code_dir, 'log.txt'), 'a', encoding='utf-8') as log_file:
        log_file.write(f'{timestamp}: {prefix}{message}\n')

    if terminal:
        print(f'{prefix}{message}')


# --- verbosity-aware line filtering (settings.LOG_TYPE) --------------------
# Noisy per-trial / per-tool chatter dropped in "minimal"; only errors, section
# headers and the final summary kept in "quiet". Lines matching _ALWAYS are
# never dropped regardless of level.
# "minimal" is a WHITELIST: keep only meaningful lines (section headers, stage
# markers, per-trial results, successes, skips, warnings and errors); everything
# else (OpenSim tool chatter, per-channel/plate detection, file-saved notices,
# CEINMS iteration dumps, etc.) is dropped. "quiet" keeps the same set minus the
# routine progress markers (so essentially errors + headers + final summary).
_KEEP_MINIMAL = re.compile(
    r"(\[ERROR\]|\bERROR\b|Error:|Traceback|Exception|FAILED|\[Warning\]|"
    r"\[Success\]|\[skip\]|\[ok\]|\[pipeline\]|\[plan |\bstarting\b|\bsaved:|\[run_sessions\]|\[scale|\[CEINMS|"
    # Maintenance commands the user invoked ON PURPOSE. Their whole output is
    # the answer, so dropping it in "minimal" makes the command look like it
    # did nothing at all — which is exactly how prune/reset reports vanished.
    r"\[prune\]|\[reset\]|\[settings\]|\[tps\]|\[ma\]|\[model-edit\]|"
    # Per-trial stage progress: "[MA] <trial> - running", "[MA ok] <trial>
    # -> <dir>", "[SO ok] ...", and the indented "inputs -" line. These were
    # dropped in "minimal", so a stage that ran eight trials showed ONE line
    # (the first, and only because it followed the kept banner) and never said
    # where anything was written.
    r"\[(?:MA|SO|IK|ID|JRA|exbiomec|CEINMS)[^\]]*\]|\binputs\s+[\u2014-]|"

    # [Session]/[Iteration] carry scale_model's and export_trials' verdicts —
    # including "static TRC not found", the one line that explains a whole run
    # of IK/MA/SO/CEINMS failures. [export is per-trial export progress.
    r"\[Session\]|\[Iteration\]|\[export|"
    r"\[bioscout\]|^BioScout |PIPELINE DONE|SESSIONS DONE|CEINMS-ONLY DONE|"
    r"^\s*={3,}|^\s*-{3,}\s)")
# Progress-only markers dropped further in "quiet".
_QUIET_DROP = re.compile(r"(\[ok\]|\[skip\]|\[Success\]|^\s*-{3,}\s|\[Warning\]|"
                         r"\[(?:MA|SO|IK|ID|JRA|exbiomec) ok\]|\binputs\s+[\u2014-])")


def _log_verbosity():
    try:
        from bioscout import utils as _u
        return str(getattr(getattr(_u, "settings", None), "LOG_TYPE", "detailed")).lower()
    except Exception:
        return "detailed"


def _keep_line(line, level):
    if level not in ("minimal", "quiet"):
        return True                       # "detailed" -> everything
    if not _KEEP_MINIMAL.search(line):
        return False                      # not whitelisted -> drop
    if level == "quiet" and _QUIET_DROP.search(line):
        return False                      # quiet: also drop routine progress
    return True


class _Tee:
    """Write to several streams at once (console AND log), filtering whole lines
    by settings.LOG_TYPE ("detailed" | "minimal" | "quiet")."""
    def __init__(self, *streams):
        self.streams = streams
        self._buf = ""
        self._in_tb = False        # inside a Python traceback block (keep every line)
        self._kept_prev = False    # previous line survived the filter

    def _emit(self, text):
        for s in self.streams:
            try:
                s.write(text); s.flush()
            except Exception:
                pass

    #: lines that get a [HH:MM:SS] timestamp prefix (warnings / errors / assembly)
    _TS_LINE = re.compile(r"(\bWarning\b|\[Warning\]|\[ERROR\]|\bError\b|Traceback|"
                          r"assemble|tolerance)", re.IGNORECASE)

    def _stamp(self, line):
        if self._TS_LINE.search(line):
            return f"[{time.strftime('%H:%M:%S')}] {line}"
        return line

    def write(self, data):
        level = _log_verbosity()
        if level not in ("minimal", "quiet"):
            # detailed: still timestamp warning/error lines, but keep everything.
            self._buf += data
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                self._emit(self._stamp(line) + "\n")
            return
        self._buf += data
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            # Keep the WHOLE Python traceback (header + indented body + final error
            # line), not just the "Traceback" header — otherwise the actual error is
            # dropped in minimal/quiet mode and crashes are undiagnosable.
            if "Traceback (most recent call last)" in line:
                self._in_tb = True
            if self._in_tb:
                self._emit(self._stamp(line) + "\n")
                # The block ends at the first NON-indented, non-empty line that is
                # not the header — the exception message (e.g. "ValueError: ...").
                if line.strip() and not line[:1].isspace() \
                        and "Traceback (most recent call last)" not in line:
                    self._in_tb = False
                continue
            keep = _keep_line(line, level)
            # A multi-line message only whitelists its FIRST line, so the
            # indented continuation lines were dropped and the header survived
            # with its content stripped — e.g. SO printing
            #     [Success] Static Optimization completed. Results saved in:
            # and nothing after it, which reads as though nothing was written.
            # The stage banners lost their "trials:" / "model:" lines the same
            # way. Keep an indented line whenever the line above it was kept.
            if not keep and self._kept_prev and line[:1].isspace() and line.strip():
                keep = True
            if keep:
                self._emit(self._stamp(line) + "\n")
            self._kept_prev = keep

    def flush(self):
        for s in self.streams:
            try:
                s.flush()
            except Exception:
                pass


LOG_DISCLAIMER = (
    "DISCLAIMER: BioScout is research software provided \"as is\", without warranty "
    "of any kind. The user is solely responsible for correct usage and for "
    "validating all inputs, settings and results; the authors accept no liability "
    "for misuse or for any decisions or conclusions based on its output. See LICENSE."
)

# Set once the first time file logging starts in a process, so auto-logging
# (ensure_logging, called from Project/Analyse) never opens a second log.
_LOG_STARTED = False
_LOG_HANDLE = None
_LOG_START = None       # run start time (time.time()) for the completion banner
_LOG_NAME = "run"
_OSIM_SINK = None       # per-run OpenSim native-output sidecar, folded in at exit
_LOG_FINISHED = False   # guard: _log_finish must run its body only once


def _strip_printbasicinfo(txt):
    """Drop OpenSim ``Model::printBasicInfo()`` dumps from native-output text.

    printBasicInfo writes a fixed ``MODEL: … / coordinates: N / … / misc
    modelcomponents: N`` block through OpenSim's ``[cout]`` logger channel, which
    the file sink captures even when the console fd-redirect suppresses it. These
    blocks are pure noise, so strip the ``[cout]`` header line plus the whole
    block. Genuine [warning]/[error] lines are left untouched."""
    try:
        _pat = re.compile(
            r"^[^\n]*\[cout\][^\n]*\n\s*MODEL:.*?misc modelcomponents:\s*\d+[^\n]*\n?",
            re.DOTALL | re.MULTILINE,
        )
        return _pat.sub("", txt)
    except Exception:
        return txt


def _log_finish():
    """atexit hook: fold OpenSim's native (C++) output into the run log and write
    the completion banner (time finished + duration) at the very end.

    Idempotent — if ``start_logging`` was called more than once, ``_log_finish``
    is registered more than once too; the ``_LOG_FINISHED`` guard makes only the
    first invocation write, so the banner never double-prints."""
    global _LOG_FINISHED
    f = _LOG_HANDLE
    if not f or _LOG_FINISHED:
        return
    _LOG_FINISHED = True
    try:
        # Flush + close OpenSim's file sink FIRST so the sidecar is complete and
        # unlocked, then fold it into the main log and remove it — so a finished
        # run leaves exactly ONE complete log.
        if _OSIM_SINK:
            try:
                import opensim as _osim
                _osim.Logger.removeFileSink()
            except Exception:
                pass
        if _OSIM_SINK and os.path.exists(_OSIM_SINK):
            try:
                with open(_OSIM_SINK, encoding="utf-8", errors="replace") as _o:
                    _txt = _o.read()
                _txt = _strip_printbasicinfo(_txt)   # drop printBasicInfo noise
                if _txt.strip():
                    f.write(f"\n{'-' * 72}\n--- OpenSim native output ---\n{_txt}\n")
                os.remove(_OSIM_SINK)          # folded in — drop the sidecar
            except Exception:
                pass
        dur = time.time() - (_LOG_START or time.time())
        h, rem = divmod(int(dur), 3600)
        m, s = divmod(rem, 60)
        f.write(f"\n{'=' * 72}\n"
                f"=== {_LOG_NAME} — completed {datetime.datetime.now():%Y-%m-%d %H:%M:%S}"
                f"   (duration {h:d}h {m:02d}m {s:02d}s)\n"
                f"{'=' * 72}\n")
        f.flush()
    except Exception:
        pass


def quiet_opensim(level=None):
    """Raise OpenSim's log level to quiet its C++ [info]/[warning] spam (missing
    display geometry, etc.). ``level`` defaults to
    ``settings.BatchSettings.opensim_log_level`` (e.g. "Error"). No-op if no level
    is configured or OpenSim isn't importable. Call this from any entry point that
    loads OpenSim models outside the logging pipeline (e.g. muscle_inspect)."""
    try:
        if level is None:
            from bioscout import utils as _u
            _bs = getattr(getattr(_u, "settings", None), "BatchSettings", None)
            level = getattr(_bs, "opensim_log_level", None)
        if not level:
            return
        import opensim as _osim
        # OpenSim expects LOWERCASE level strings ('off','error','warning','info',
        # ...) — 'Error' is silently ignored, so normalise here.
        _osim.Logger.setLevelString(str(level).lower())
    except Exception:
        pass


def ensure_logging(name="bioscout", log_dir=None):
    """Start file logging ONCE per process (idempotent).

    Called automatically whenever a Project or Analyse/Trial is created, so any
    bioscout run writes ``<project>/logs/bioscout_<timestamp>.log`` without the
    caller doing anything. No-op if logging was already started (e.g. an explicit
    ``start_logging`` or the CLI). Returns the log handle, or None if already on."""
    if _LOG_STARTED:
        return _LOG_HANDLE
    try:
        return start_logging(name=name, log_dir=log_dir)
    except Exception:
        return None


def start_logging(name="run", log_dir=None, filename=None, append=False):
    """Tee stdout+stderr to a timestamped project log file, with a run heading.

    Every run writes to ``<log_dir>/bioscout_<YYYYmmdd_HHMMSS>.txt`` — one naming
    scheme (``bioscout_…``) for all runs, with the timestamp in the filename so
    runs never collide, and a heading inside identifying what was done (``name``
    + time + disclaimer)::

        from bioscout import utils
        utils.start_logging("export Athlete_03_Cateli/25_03_31")

    ``log_dir`` defaults to ``<project>/logs`` (``utils.PROJECT_DIR``). Pass an
    explicit ``filename=`` to override, or ``append=True`` to append. Captures
    Python-level output; OpenSim's C++ ``[info]`` lines are fd-level — pipe
    ``... 2>&1 | tee`` to capture those too. Returns the open log file handle.
    """
    # BIOSCOUT_LOG=0 disables file logging entirely — for runs whose parent
    # process already tees ALL output to its own log (e.g. a runner script);
    # without this, every run produced two near-identical log files.
    if os.environ.get("BIOSCOUT_LOG", "1").lower() in ("0", "false", "off"):
        return None
    # BIOSCOUT_LOG_DIR wins over everything: one folder for every log of a
    # project, wherever the caller wanted to put it (2026-08-17 — session-folder
    # logs scattered per subject/state made runs hard to audit).
    env_dir = os.environ.get("BIOSCOUT_LOG_DIR")
    if env_dir:
        log_dir = env_dir
    elif log_dir is None:
        from bioscout import utils as _u
        log_dir = os.path.join(getattr(_u, "PROJECT_DIR", os.getcwd()), "logs")
    os.makedirs(log_dir, exist_ok=True)
    if filename is None:
        # ONE naming scheme for every log: bioscout_<date>_<time>.txt.
        # No subject/session in the name (2026-08-17) — the heading inside
        # the file says what was run.
        filename = f"bioscout_{datetime.datetime.now():%Y%m%d_%H%M%S}.txt"
    path = os.path.join(log_dir, filename)
    f = open(path, "a" if append else "w", encoding="utf-8")
    f.write(f"\n{'=' * 72}\n"
            f"=== {name}   {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n"
            f"{LOG_DISCLAIMER}\n"
            f"{'=' * 72}\n")
    f.flush()
    global _LOG_STARTED, _LOG_HANDLE, _LOG_START, _LOG_NAME, _OSIM_SINK, _LOG_FINISHED
    _LOG_STARTED, _LOG_HANDLE = True, f   # mark started so auto-logging won't re-open
    _LOG_FINISHED = False                 # fresh run — allow the finish hook to write
    _LOG_START, _LOG_NAME = time.time(), name
    sys.stdout = _Tee(sys.__stdout__, f)
    sys.stderr = _Tee(sys.__stderr__, f)
    # OpenSim's C++ [info]/[warning] lines are fd-level, so the Python tee above
    # misses them. Send them to a per-run sidecar in the TEMP dir (its own handle
    # — no conflict with this log's), folded into THIS log at exit. Keeping the
    # sidecar out of logs/ means the run folder only ever shows the single
    # bioscout_*.log, even if Windows hasn't released the sink handle in time for
    # the delete (the leftover, if any, stays invisibly in temp).
    import tempfile as _tempfile
    _stem = os.path.splitext(os.path.basename(path))[0]
    _OSIM_SINK = os.path.join(_tempfile.gettempdir(),
                              f"{_stem}_osim_{os.getpid()}.log")
    try:
        import opensim as _osim
        _osim.Logger.addFileSink(_OSIM_SINK)
        quiet_opensim()          # honor settings.BatchSettings.opensim_log_level
    except Exception:
        _OSIM_SINK = None
    import atexit as _atexit
    _atexit.register(_log_finish)
    print(f"[bioscout] logging '{name}' -> {path}")
    return f


def trial_type(trial_name, pattern=DEFAULT_TRIAL_TYPE_PATTERN):
    """Strip a trailing ``_<number>`` so reps of a task share a type.

    ``'Squat_35kg_02' -> 'Squat_35kg'``; names without a trailing number are
    returned unchanged.
    """
    m = re.match(pattern, str(trial_name))
    return m.group(1) if m else str(trial_name)


def get_mean_across_trial_dfs(df_list, mode='mean') -> pd.DataFrame:
    """Reduce a list of per-trial DataFrames across trials, aligned by row index.

    ``mode`` = 'mean' | 'median' | 'stdev'. Each input is one trial; the result
    is a single DataFrame of the per-row reduction (drops the internal trial id).
    """
    processed_dfs = []
    for i, df in enumerate(df_list):
        temp_df = df.copy()
        temp_df['trial_id'] = i
        temp_df['sample_index'] = range(len(temp_df))
        processed_dfs.append(temp_df)
    combined_df = pd.concat(processed_dfs, axis=0)
    if mode == 'mean':
        result_df = combined_df.groupby('sample_index').mean().drop(columns=['trial_id'], errors='ignore')
    elif mode == 'median':
        result_df = combined_df.groupby('sample_index').median().drop(columns=['trial_id'], errors='ignore')
    elif mode == 'stdev':
        result_df = combined_df.groupby('sample_index').std().drop(columns=['trial_id'], errors='ignore')
    else:
        raise ValueError("Invalid mode. Choose from 'mean', 'median', or 'stdev'.")
    return result_df.reset_index(drop=True)


def time_normalise_df(df, fs=''):
    """Resample every column of ``df`` to 101 points over its time range."""
    if not type(df) == pd.core.frame.DataFrame:
        raise Exception('Input must be a pandas DataFrame')

    if 'time' not in df.columns:
        raise Exception('Input DataFrame must contain a column named "time"')

    normalised_df = pd.DataFrame(columns=df.columns)
    timeTrial = df['time'].values
    Tnorm = np.linspace(timeTrial[0], timeTrial[-1], 101)

    for column in df.columns:
        normalised_df[column] = np.zeros(101)
        currentData = df[column].values.astype(float)

        # replace NaNs with interpolated values where possible, else 0
        nan_mask = np.isnan(currentData)
        if nan_mask.all():
            currentData = np.zeros(len(timeTrial))
        elif nan_mask.any():
            currentData[nan_mask] = np.interp(
                timeTrial[nan_mask], timeTrial[~nan_mask], currentData[~nan_mask]
            )

        normalised_df[column] = np.interp(Tnorm, timeTrial, currentData)

    return normalised_df


# ===========================================================================
# Central plotting style (reads settings.PlottingSettings, else these defaults)
# ===========================================================================
#: default {source: {color, ls, lw}} — overridden per-project by
#: settings.PlottingSettings.sources (any omitted source falls back to here).
DEFAULT_PLOT_STYLE = {
    "inverse_dynamics":    {"color": "black",    "ls": "-", "lw": 2.0},
    "ceinms":              {"color": "tab:blue", "ls": "-", "lw": 1.8},
    "static_optimisation": {"color": "tab:red",  "ls": "-", "lw": 1.8},
    "emg":                 {"color": "0.5",      "ls": "-", "lw": 1.5},
    "activation":          {"color": "0.35",     "ls": "-", "lw": 1.2},
    "muscle_force":        {"color": "tab:red",  "ls": "-", "lw": 1.2},
}


def _to_mpl_color(c):
    """Normalise a colour spec for matplotlib. Accepts an (R,G,B[,A]) tuple in
    0-255 or 0-1, a hex string, or a named colour (returned unchanged)."""
    if isinstance(c, (tuple, list)):
        vals = list(c)
        if any(isinstance(v, (int, float)) and v > 1 for v in vals[:3]):
            rgb = [max(0.0, min(1.0, float(v) / 255.0)) for v in vals[:3]]
        else:
            rgb = [float(v) for v in vals[:3]]
        alpha = [float(vals[3])] if len(vals) > 3 else []
        return tuple(rgb + alpha)
    return c


def _plotting_settings():
    try:
        from bioscout import utils as _u
        return getattr(getattr(_u, "settings", None), "PlottingSettings", None)
    except Exception:
        return None


def plot_style(source):
    """Return ``{'color','ls','lw'}`` for a plot SOURCE. Merges the project's
    ``settings.PlottingSettings.sources[source]`` over ``DEFAULT_PLOT_STYLE``;
    the colour is normalised for matplotlib."""
    style = dict(DEFAULT_PLOT_STYLE.get(source, {"color": "black", "ls": "-", "lw": 1.5}))
    ps = _plotting_settings()
    src = getattr(ps, "sources", None) or {}
    if isinstance(src.get(source), dict):
        style.update(src[source])
    style["color"] = _to_mpl_color(style.get("color", "black"))
    style.setdefault("ls", "-")
    style.setdefault("lw", 1.5)
    return style


def side_color(side):
    """Body-side colour convention used across bioscout figures: right = blue,
    left = red. Accepts 'r'/'right'/'_r' or 'l'/'left'/'_l'."""
    s = str(side).lower().lstrip("_")
    if s in ("r", "right"):
        return "tab:blue"
    if s in ("l", "left"):
        return "tab:red"
    return "black"


def fig_size(nrows, ncols):
    """Figure size (inches) for an ``nrows x ncols`` subplot grid, scaled by
    ``settings.PlottingSettings.scale_per_subplot`` = (row_mult, col_mult) and
    ``fig_scale``. Defaults to a sensible per-subplot size if unset."""
    ps = _plotting_settings()
    spp = getattr(ps, "scale_per_subplot", None) or (2, 3)
    try:
        row_mult, col_mult = float(spp[0]), float(spp[1])
    except Exception:
        row_mult, col_mult = 2.0, 3.0
    fs = float(getattr(ps, "fig_scale", 1.0) or 1.0)
    return (max(1, int(ncols)) * col_mult * fs,
            max(1, int(nrows)) * row_mult * fs)
