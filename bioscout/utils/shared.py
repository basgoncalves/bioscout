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
import contextlib as _contextlib

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


def in_notebook():
    """True when stdout belongs to a Jupyter/IPython cell rather than a console.

    ``ipykernel`` in ``sys.modules`` is the cheap, dependency-free test: it is
    imported by the kernel itself and by nothing else. Used for two decisions in
    ``start_logging`` — both about not stealing a notebook's own output."""
    return "ipykernel" in sys.modules


class _Tee:
    """Write to several streams at once (console AND log), filtering whole lines
    by settings.LOG_TYPE ("detailed" | "minimal" | "quiet").

    ``raw=True`` turns the filter off entirely and passes writes straight
    through. The filter exists to keep an hours-long batch log readable; applied
    in a notebook it silently eats the user's own ``print()`` calls, because
    nothing they write is on the whitelist ``_KEEP_MINIMAL`` matches.
    """
    def __init__(self, *streams, raw=False):
        self.streams = streams
        self.raw = bool(raw)
        self._buf = ""
        self._in_tb = False        # inside a Python traceback block (keep every line)
        self._kept_prev = False    # previous line survived the filter

    # Some libraries probe the stream they are writing to (tqdm asks isatty,
    # anything doing encoding work asks encoding). Answer for the first stream
    # rather than raising AttributeError from a tee nobody asked for.
    def isatty(self):
        try:
            return bool(self.streams[0].isatty())
        except Exception:
            return False

    @property
    def encoding(self):
        # `or`, not a getattr default: io.StringIO HAS an `encoding` attribute
        # and it is None, so the default never fires and callers that do
        # `codecs.lookup(stream.encoding)` get a TypeError instead of a name.
        return getattr(self.streams[0], "encoding", None) or "utf-8"

    def __getattr__(self, name):
        # Anything the tee does not define goes to the stream underneath —
        # above all ipykernel's ``set_parent``. At every new cell ipykernel
        # runs ``if hasattr(sys.stdout, "set_parent"): sys.stdout.set_parent(..)``
        # to point output at THAT cell. A tee without this hid the method, so
        # the real stream stayed bound to the cell that started logging and
        # every later print() was addressed to a finished cell: the frontend
        # dropped it, the log file kept it (reproduced on ipykernel 7.3,
        # 2026-09-10). Only called for attributes normal lookup cannot find.
        streams = self.__dict__.get("streams")
        if not streams or name.startswith("__"):
            raise AttributeError(name)
        return getattr(streams[0], name)

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
        if self.raw:
            self._emit(data)
            return
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
_LOG_PATH = None        # path of the open run log
_SAVED_STREAMS = None   # (stdout, stderr) replaced by _capture_streams, else None


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
    ``start_logging`` or the CLI). Returns the log handle, or None if already on.

    Library use (notebook, script) opens the file but does NOT capture stdout —
    see ``start_logging(capture=...)``."""
    if _LOG_STARTED:
        return _LOG_HANDLE
    try:
        return start_logging(name=name, log_dir=log_dir)
    except Exception:
        return None


def _console_owned():
    """True when bioscout's own CLI/GUI is the program running this process.

    Only then may bioscout touch ``sys.stdout``/``sys.stderr`` on its own
    initiative. ``__main__`` marks the process by setting
    ``BIOSCOUT_LOG_FILTER=1``; imported as a library -- a notebook, a user's
    script, ``python -c`` -- that is unset and the streams belong to the caller.
    A notebook never counts as owned, even if the variable leaked into the
    kernel's environment."""
    return (os.environ.get("BIOSCOUT_LOG_FILTER") == "1"
            and not in_notebook())


def _pid_alive(pid):
    """Is process ``pid`` still running? (Windows: OpenProcess/GetExitCodeProcess,
    never os.kill, which TERMINATES there.)"""
    try:
        pid = int(pid)
    except Exception:
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            k = ctypes.windll.kernel32
            h = k.OpenProcess(0x1000, False, pid)          # QUERY_LIMITED_INFORMATION
            if not h:
                return False
            code = ctypes.c_ulong()
            ok = k.GetExitCodeProcess(h, ctypes.byref(code))
            k.CloseHandle(h)
            return bool(ok) and code.value == 259          # STILL_ACTIVE
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except Exception:
        return False


_LIVE_SLOT = None          # k of the run log's live_<k>.log, when it has one


def _live_log_alias(path, max_slots=8):
    """Hard-link the run log as ``<log dir>/live_<k>.log`` in the first slot no
    RUNNING process owns, and return that alias (or None).

    The editor is pointed at the alias, so successive runs reuse the same tab
    (VS Code reloads the file when the link is re-pointed) and the open tabs
    never outnumber the runs going at once. The timestamped bioscout_<time>.log
    stays the record; the alias is the same file under a second name."""
    d = os.path.dirname(os.path.abspath(path))
    for k in range(1, max_slots + 1):
        alias = os.path.join(d, f"live_{k}.log")
        owner = alias + ".pid"
        try:
            with open(owner, encoding="utf-8") as fh:
                pid = fh.read().strip()
        except Exception:
            pid = ""
        if pid and pid != str(os.getpid()) and _pid_alive(pid):
            continue                                        # slot busy: another live run
        try:
            if os.path.lexists(alias):
                os.remove(alias)
            os.link(path, alias)
            with open(owner, "w", encoding="utf-8") as fh:
                fh.write(str(os.getpid()))
            global _LIVE_SLOT
            _LIVE_SLOT = k
            return alias
        except Exception:
            return None                                     # no hard links here: per-run tab
    return None


def _open_log_viewer(path):
    """Open the run log in the user's text editor as soon as it exists.

    Which editor, in order:
      1. ``BIOSCOUT_LOG_VIEWER`` -- a command; the log path is appended
         (e.g. ``code -r``, ``notepad++``, ``notepad``).
      2. VS Code, when its ``code`` command is on PATH -- opened as a tab in the
         current window (``-r``). VS Code reloads a file that changes on disk,
         so the tab follows the run as bioscout writes it.
      3. The system default app for ``.log`` files.

    Every ``Session(...)`` starts a new ``bioscout_<time>.log``; the editor is
    pointed at a reusable hard link ``live_<k>.log`` to it (see _live_log_alias),
    so finished runs do not pile up tabs (BIOSCOUT_LOG_TABS=per-run: one tab per log).
    Off with ``BIOSCOUT_OPEN_LOG=0``. Never in a notebook, a test run or a
    child process (multiprocessing workers start logs of their own).
    """
    try:
        if os.environ.get("BIOSCOUT_OPEN_LOG", "1").strip().lower() in (
                "0", "false", "off", "no"):
            return
        if in_notebook() or "pytest" in sys.modules:
            return
        import multiprocessing as _mp
        if _mp.parent_process() is not None:
            return
        import shlex
        import shutil
        import subprocess
        # one reusable tab per concurrently running bioscout, not one per run
        # (VS Code cannot close a tab from its CLI). BIOSCOUT_LOG_TABS=per-run
        # restores a new tab for every log.
        if os.environ.get("BIOSCOUT_LOG_TABS", "reuse").strip().lower() != "per-run":
            path = _live_log_alias(path) or path
        _open_in_editor(path)
    except Exception:
        pass


def _open_in_editor(path):
    """Open ``path`` in BIOSCOUT_LOG_VIEWER, else VS Code (``code -r``), else the system app."""
    try:
        import shlex
        import shutil
        import subprocess
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)   # no flashing console
        custom = os.environ.get("BIOSCOUT_LOG_VIEWER", "").strip()
        if custom:
            cmd = shlex.split(custom, posix=(os.name != "nt")) + [path]
            exe = shutil.which(cmd[0]) or cmd[0]
            subprocess.Popen([exe] + cmd[1:], creationflags=flags, close_fds=True)
            return
        code = shutil.which("code")
        if code:
            subprocess.Popen([code, "-r", path], creationflags=flags, close_fds=True)
        elif os.name == "nt":
            os.startfile(path)                                # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path], close_fds=True)
        elif shutil.which("xdg-open"):
            subprocess.Popen(["xdg-open", path], close_fds=True)
    except Exception:
        pass          # opening the log is a convenience; never fail a run over it


def start_logging(name="run", log_dir=None, filename=None, append=False,
                  capture=None):
    """Open a timestamped project log file, with a run heading.

    Every run writes to ``<log_dir>/bioscout_<YYYYmmdd_HHMMSS>.log`` — one naming
    scheme (``bioscout_…``) for all runs, with the timestamp in the filename so
    runs never collide, and a heading inside identifying what was done (``name``
    + time + disclaimer)::

        from bioscout import utils
        utils.start_logging("export Athlete_03_Cateli/25_03_31")

    What goes into the file:

    * always -- the heading, OpenSim's native C++ output and the completion
      banner (both written when the process exits or :func:`stop_logging` runs);
    * ``print()`` output, but only while stdout/stderr are *captured*.

    ``capture`` decides whether ``sys.stdout``/``sys.stderr`` are teed into the
    file. ``None`` (the default) captures ONLY when bioscout's own CLI/GUI owns
    the process (see :func:`_console_owned`). Imported as a library -- a
    notebook, your own script -- bioscout leaves the streams alone, as a Python
    library should: replacing them silently changes where every other print in
    the session goes. Pass ``capture=True`` to opt in explicitly, or use
    :func:`capture_output` to capture just one block; :func:`stop_logging`
    puts the original streams back.

    ``log_dir`` defaults to ``<project>/logs`` (``utils.PROJECT_DIR``). Pass an
    explicit ``filename=`` to override, or ``append=True`` to append. Returns
    the open log file handle.
    """
    global _LOG_STARTED, _LOG_HANDLE, _LOG_START, _LOG_NAME, _OSIM_SINK, _LOG_FINISHED
    global _LOG_PATH
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
        # ONE naming scheme for every log: bioscout_<date>_<time>.log.
        # .log rather than .txt so editors and log viewers syntax-highlight
        # it, and so a `*.txt` glob in a project folder does not sweep up
        # run logs alongside real text files.
        # No subject/session in the name (2026-08-17) — the heading inside
        # the file says what was run.
        filename = f"bioscout_{datetime.datetime.now():%Y%m%d_%H%M%S}.log"
        # 2026-11-04: + the command (bioscout_<time>_simulate_so_gpkv4.log), so runs a
        # few seconds apart can be told apart without opening them
        _tag = _command_tag()
        if _tag:
            filename = filename[:-4] + "_" + _tag + ".log"
    path = os.path.join(log_dir, filename)
    # Two runs in the same second must not overwrite each other's log.
    if not append and os.path.exists(path):
        _stem, _ext = os.path.splitext(path)
        _n = 2
        while os.path.exists(f"{_stem}_{_n}{_ext}"):
            _n += 1
        path = f"{_stem}_{_n}{_ext}"
    # A log already open (an earlier start_logging in this process) is
    # finished and closed first, instead of leaking its handle.
    if _LOG_STARTED and _LOG_HANDLE is not None:
        _prev = _LOG_HANDLE
        _log_finish()
        try:
            _prev.close()
        except Exception:
            pass
    f = open(path, "a" if append else "w", encoding="utf-8")
    f.write(f"\n{'=' * 72}\n"
            f"=== {name}   {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n"
            f"{LOG_DISCLAIMER}\n"
            f"{'=' * 72}\n")
    f.flush()
    _LOG_STARTED, _LOG_HANDLE = True, f   # mark started so auto-logging won't re-open
    _LOG_FINISHED = False                 # fresh run — allow the finish hook to write
    _LOG_START, _LOG_NAME, _LOG_PATH = time.time(), name, path
    _open_log_viewer(path)

    if capture is None:
        # Tee by default: the run log is the record, and a tee leaves every
        # line on the terminal as well, so a user's script or `python -c` loses
        # nothing. Library callers used to get a header-only log here ("print
        # output not captured") -- the opposite of what a log is for. Only a
        # notebook stays opt-in (capture_output), since ipykernel owns its
        # streams; BIOSCOUT_LOG_CAPTURE=0 turns the tee off for anything else.
        capture = (QUIET_CONSOLE or _console_owned()
                   or (not in_notebook()
                       and os.environ.get("BIOSCOUT_LOG_CAPTURE", "1").lower()
                       not in ("0", "false", "off")))
    if capture or _SAVED_STREAMS is not None:   # (re-)point any live tee here
        _capture_streams(f)

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
    if capture or _SAVED_STREAMS is not None:
        print(f"[bioscout] logging '{name}' -> {path}",
              file=(console_stream() if QUIET_CONSOLE else sys.stdout))
        if QUIET_CONSOLE:
            _argv = list(sys.argv)
            _argv[0] = os.path.splitext(os.path.basename(_argv[0]))[0] or "bioscout"
            _cmd = " ".join(_argv)
            if "--verbose" not in _cmd and " -v" not in _cmd:
                _cmd += " --verbose"
            print(f"[bioscout] to watch live output in terminal add --verbose:\n"
                  f"           {_cmd}", file=console_stream())
            # Redirecting the process's own descriptors catches OpenSim's C++
            # output, but leaving them redirected at interpreter teardown
            # corrupts the parent terminal (Git Bash loses its prompt). It is
            # opt-in until that is handled properly, and always restored.
            if os.environ.get("BIOSCOUT_QUIET_FD") == "1":
                _redirect_fds(f)
                import atexit as _at
                _at.register(_restore_fds)
    else:
        print(f"[bioscout] logging '{name}' -> {path} "
              f"(print output not captured: notebook, or BIOSCOUT_LOG_CAPTURE=0; "
              f"see bioscout.utils.capture_output)")
    return f


#: True -> the tee writes to the LOG ONLY, and the terminal keeps just the
#: header and the log path. A solve prints hundreds of OpenSim lines that
#: nobody reads live and that scroll the one line you wanted out of reach; the
#: log is the record. `bioscout ... --verbose` restores the stream.
QUIET_CONSOLE = False


class _NullStream:
    """A sink that swallows writes, for the console side of a quiet tee."""

    def write(self, *_a):
        return 0

    def flush(self):
        pass

    def isatty(self):
        return False


#: (saved stdout fd, saved stderr fd) while the console is redirected
_SAVED_FDS = None
_CONSOLE_FILE = None


def set_quiet_console(quiet=True):
    global QUIET_CONSOLE
    QUIET_CONSOLE = bool(quiet)


def _redirect_fds(f):
    """Point the PROCESS's stdout/stderr file descriptors at the log.

    Swapping sys.stdout only catches Python's print(). OpenSim's C++ side
    writes the model summary (coordinates/forces/muscles...) straight to fd 1,
    so it sailed past the tee and kept landing in the terminal. Duplicating the
    real descriptors is the only thing that catches it. The originals are kept
    so the header can still reach the terminal.
    """
    global _SAVED_FDS, _CONSOLE_FILE
    if _SAVED_FDS is not None or f is None:
        return
    try:
        _SAVED_FDS = (os.dup(1), os.dup(2))
        _CONSOLE_FILE = os.fdopen(os.dup(_SAVED_FDS[0]), "w", buffering=1,
                                  errors="replace")
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(f.fileno(), 1)
        os.dup2(f.fileno(), 2)
    except Exception:                      # no real fds (notebooks, pytest)
        _SAVED_FDS = _CONSOLE_FILE = None


def _restore_fds():
    global _SAVED_FDS, _CONSOLE_FILE
    if _SAVED_FDS is None:
        return
    try:
        sys.stdout.flush(); sys.stderr.flush()
        os.dup2(_SAVED_FDS[0], 1)
        os.dup2(_SAVED_FDS[1], 2)
        for fd in _SAVED_FDS:
            os.close(fd)
    except Exception:
        pass
    _SAVED_FDS = _CONSOLE_FILE = None


def console_stream():
    """The REAL terminal, even while a quiet tee / fd redirect is in place."""
    if _CONSOLE_FILE is not None:
        return _CONSOLE_FILE
    if _SAVED_STREAMS is not None:
        return _SAVED_STREAMS[0]
    return sys.stdout or sys.__stdout__


def _capture_streams(f):
    """Tee sys.stdout/sys.stderr into the open log ``f`` (idempotent).

    Tees onto the CURRENT streams, never sys.__stdout__. In a Jupyter kernel
    ipykernel has already replaced sys.stdout with the stream that routes output
    INTO the cell; sys.__stdout__ is still the kernel PROCESS's stdout — the
    terminal nobody is looking at. In a normal console the two are the same
    object, so this changes nothing there.

    ``raw`` unless bioscout's own CLI/GUI owns the console: the LOG_TYPE line
    filter is for batch logs. A user's own print() matches no whitelist entry,
    so under the default LOG_TYPE="minimal" it would be dropped."""
    global _SAVED_STREAMS
    if _SAVED_STREAMS is not None:           # already capturing: re-point only
        for s in (sys.stdout, sys.stderr):
            if isinstance(s, _Tee) and len(s.streams) > 1:
                s.streams = (s.streams[0], f)
        return
    _raw = not _console_owned()
    _SAVED_STREAMS = (sys.stdout, sys.stderr)
    _out = sys.stdout or sys.__stdout__
    _err = sys.stderr or sys.__stderr__
    if QUIET_CONSOLE:
        _out = _err = _NullStream()
    sys.stdout = _Tee(_out, f, raw=_raw)
    sys.stderr = _Tee(_err, f, raw=_raw)


def _release_streams():
    """Undo :func:`_capture_streams`. If something else wrapped our tee after
    us, it is left in place and our tee just stops copying to the file."""
    global _SAVED_STREAMS
    if _SAVED_STREAMS is None:
        return
    out, err = _SAVED_STREAMS
    _SAVED_STREAMS = None
    for attr, orig in (("stdout", out), ("stderr", err)):
        cur = getattr(sys, attr)
        if isinstance(cur, _Tee):
            try:
                cur.flush()
            except Exception:
                pass
            if cur.streams and cur.streams[0] is orig:
                setattr(sys, attr, orig)
                continue
        # someone wrapped on top of us -- make our tee a pass-through
        for s in _iter_tees(cur):
            s.streams = s.streams[:1]


def _iter_tees(stream, _depth=0):
    """Our _Tee objects reachable from ``stream`` (a few wrappers deep)."""
    if _depth > 5 or stream is None:
        return []
    if isinstance(stream, _Tee):
        return [stream]
    inner = stream.__dict__.get("_orig") if hasattr(stream, "__dict__") else None
    return _iter_tees(inner, _depth + 1)


def stop_logging():
    """Close the current run log and give stdout/stderr back.

    Writes the completion banner (and OpenSim's native output) into the file
    and restores the streams if they were captured. Safe to call when logging
    never started. Afterwards the next ``Project``/``Session`` opens a fresh
    log."""
    global _LOG_STARTED, _LOG_HANDLE
    _release_streams()
    f = _LOG_HANDLE
    _log_finish()
    try:
        if f:
            f.close()
    except Exception:
        pass
    _LOG_STARTED, _LOG_HANDLE = False, None


@_contextlib.contextmanager
def capture_output(name="block", log_dir=None):
    """Copy ``print()`` output into the run log for the duration of a block.

    For notebooks and scripts, where bioscout otherwise leaves stdout alone::

        from bioscout.utils import capture_output
        with capture_output():
            session.run()          # prints show in the cell AND in the log

    Opens a log first if none is running. The streams are restored on exit,
    even on error, so the next cell behaves normally."""
    started_here = not _LOG_STARTED
    if started_here:
        f = start_logging(name=name, log_dir=log_dir, capture=True)
    else:
        f = _LOG_HANDLE
    if f is None:                          # logging disabled (BIOSCOUT_LOG=0)
        yield None
        return
    # Someone (the CLI, or an explicit capture=True) is already capturing:
    # leave their capture alone rather than ending it at the end of the block.
    ours = started_here or _SAVED_STREAMS is None
    if not started_here and ours:
        _capture_streams(f)
    try:
        yield f
    finally:
        if ours:
            _release_streams()


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


# --- per-step logs (2026-11-04) ----------------------------------------------
#: The run log (logs/bioscout_<time>_<command>.log) keeps the stage banners and ONE
#: line per trial and step (ok / FAILED, time, warnings, where the details are).
#: Everything a step prints goes to its own log beside its results, e.g.
#: <trial>/static_optimisation/so.log. BIOSCOUT_STEP_LOGS=0 puts it all back in the
#: run log.
_STEP_DEPTH = 0


def step_logs_on():
    return (_SAVED_STREAMS is not None and _LOG_STARTED
            and os.environ.get("BIOSCOUT_STEP_LOGS", "1").lower() not in ("0", "false", "off"))


@_contextlib.contextmanager
def step_log(path, label=""):
    """Send everything printed inside the block to ``path`` (and to the terminal with
    --verbose) instead of the run log. Yields a dict filled on exit with
    ``warnings`` (lines with WARNING/Warning) and ``path`` (None when not redirected:
    library use, a nested step, or BIOSCOUT_STEP_LOGS=0)."""
    global _STEP_DEPTH
    info = {"path": None, "warnings": 0, "skipped": False}
    if _STEP_DEPTH or not step_logs_on():
        yield info
        return
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    # appended, one block per run: a step that only finds its results already there
    # (e.g. IK reused by SO) must not wipe the details of the run that made them
    fh = open(path, "a", encoding="utf-8", errors="replace")
    _start = fh.tell()
    fh.write(f"\n=== {label}   {datetime.datetime.now():%Y-%m-%d %H:%M:%S}   (run log: {_LOG_PATH})\n")
    old = (sys.stdout, sys.stderr)
    try:
        old[0].flush()
    except Exception:
        pass
    fh.flush()
    # say where the details go BEFORE the step runs, in the run log, and show the step
    # log live: logs/live_<k>_step.log is re-pointed at each step's log (one editor tab
    # that follows the run step by step; opened with the first step)
    try:
        _who, _, _what = label.partition(": ")
        _head = f"  [{_who}] {_what:<27}" if _what else f"  {label:<38}"
        print(f"{_head} running ...    -> {os.path.abspath(path)}", file=old[0], flush=True)
    except Exception:
        pass
    _live_step_alias(path)
    streams = (fh,) if QUIET_CONSOLE else (console_stream(), fh)
    sys.stdout = _Tee(*streams, raw=True)
    sys.stderr = _Tee(*streams, raw=True)
    _STEP_DEPTH += 1
    info["path"] = os.path.abspath(path)
    try:
        yield info
    finally:
        _STEP_DEPTH -= 1
        try:
            sys.stdout.flush(); sys.stderr.flush()
        except Exception:
            pass
        sys.stdout, sys.stderr = old
        fh.close()
        try:
            with open(path, encoding="utf-8", errors="replace") as _f:
                _f.seek(_start)                                  # this run's block only
                _blk = _f.read().splitlines()[2:]
            info["warnings"] = sum(1 for l in _blk if re.search(r"warning", l, re.IGNORECASE))
            # a step that only found its results: "kept" / "already exists" / "[skip]"
            _txt = [l for l in _blk if l.strip()]
            info["skipped"] = (not _txt) or (len(_txt) <= 3 and any(
                re.search(r"\bkept\b|already exists|\[skip\]|skipped", l, re.IGNORECASE) for l in _txt))
        except Exception:
            pass


_STEP_ALIAS_OPENED = False


def _live_step_alias(path):
    global _STEP_ALIAS_OPENED
    if _LOG_PATH is None or os.environ.get("BIOSCOUT_OPEN_LOG", "1").strip().lower() in ("0", "false", "off", "no"):
        return
    try:
        alias = os.path.join(os.path.dirname(_LOG_PATH), f"live_{_LIVE_SLOT or 1}_step.log")
        if os.path.lexists(alias):
            os.remove(alias)
        os.link(os.path.abspath(path), alias)
    except Exception:
        return
    if not _STEP_ALIAS_OPENED:
        _STEP_ALIAS_OPENED = True
        try:
            import multiprocessing as _mp
            if _mp.parent_process() is None and not in_notebook() and "pytest" not in sys.modules:
                _open_in_editor(alias)
        except Exception:
            pass


def _command_tag():
    """'simulate_cmc_gpkv4' from `bioscout simulate cmc <session> --iteration gpkv4 ...`, so
    the run log says which command it is; '' when not run from the bioscout CLI."""
    a = list(sys.argv[1:])
    if not a or not os.path.basename(sys.argv[0]).lower().startswith("bioscout"):
        return ""
    words = [w for w in a[:2] if re.fullmatch(r"[A-Za-z][\w-]*", w)]
    for flag in ("--iteration", "--trial"):
        if flag in a and a.index(flag) + 1 < len(a):
            words.append(a[a.index(flag) + 1].replace(",", "+")[:40])
    tag = "_".join(words)
    return re.sub(r"[^\w+-]", "", tag)[:80]
