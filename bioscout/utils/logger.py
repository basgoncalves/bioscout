"""Logging utility for the Powerlifting Model Analysis App."""

import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
import threading


class _TeeStream:
    """Writes to two streams simultaneously (stdout/stderr → terminal + log file)."""

    def __init__(self, original, log_file_stream):
        self._orig = original
        self._log = log_file_stream

    def write(self, data):
        self._orig.write(data)
        try:
            self._log.write(data)
            self._log.flush()
        except Exception:
            pass

    def flush(self):
        self._orig.flush()
        try:
            self._log.flush()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._orig, name)


class AppLogger:
    """Custom logger for the application."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize logger (singleton pattern)."""
        if self._initialized:
            return

        self._initialized = True

        # Set log directory - prefer app/logs if it exists, otherwise use home directory
        app_dir = Path(__file__).parent.parent  # app directory
        preferred_log_dir = app_dir / "logs"
        fallback_log_dir = Path.home() / ".powerlifting_app" / "logs"

        # Use app/logs if app directory is writable, otherwise use home directory
        try:
            preferred_log_dir.mkdir(parents=True, exist_ok=True)
            self.log_dir = preferred_log_dir
        except (PermissionError, OSError):
            self.log_dir = fallback_log_dir
            self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create logger
        self.logger = logging.getLogger("PowerliftingAnalysis")
        self.logger.setLevel(logging.DEBUG)

        # Remove existing handlers
        self.logger.handlers.clear()

        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        simple_formatter = logging.Formatter('%(levelname)s: %(message)s')

        # One log file per run, with a single consistent name pattern for both
        # GUI and batch (no separate app_/batch_ split). The timestamp keeps each
        # run's log distinct so nothing is overwritten; the contents differ by
        # what ran (batch headings/prints vs GUI logs).
        import sys
        self._batch_mode = '-b' in sys.argv or '--batch' in sys.argv
        log_file = self.log_dir / f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(
            log_file, encoding='utf-8', errors='replace')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(detailed_formatter)
        self.logger.addHandler(file_handler)
        self.file_handler = file_handler
        self.current_log_file = str(log_file)

        # A header line makes it obvious which kind of run produced this log.
        _mode = "BATCH" if self._batch_mode else "GUI"
        self.logger.info(f"===== msk_modelling_python — {_mode} run — "
                         f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====")

        # Console handler with UTF-8 encoding and error handling
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(simple_formatter)
        if hasattr(console_handler.stream, 'reconfigure'):
            try:
                console_handler.stream.reconfigure(encoding='utf-8', errors='replace')
            except Exception:
                pass
        self.logger.addHandler(console_handler)

        # Tee stdout/stderr so print() calls also appear in the log file
        if self.file_handler is not None:
            import sys as _sys
            _sys.stdout = _TeeStream(_sys.stdout, self.file_handler.stream)
            _sys.stderr = _TeeStream(_sys.stderr, self.file_handler.stream)

    def debug(self, message: str) -> None:
        """Log debug message."""
        self.logger.debug(message)

    def info(self, message: str) -> None:
        """Log info message."""
        self.logger.info(message)

    def warning(self, message: str) -> None:
        """Log warning message."""
        self.logger.warning(message)

    def error(self, message: str) -> None:
        """Log error message."""
        self.logger.error(message)

    def critical(self, message: str) -> None:
        """Log critical message."""
        self.logger.critical(message)

    def set_console_level(self, level: int) -> None:
        """
        Set console handler log level.

        Args:
            level: logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        for handler in self.logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                handler.setLevel(level)

    def get_log_file(self) -> str:
        """Get path to current log file."""
        return self.current_log_file

    def list_logs(self, limit: int = 10) -> list:
        """
        List recent log files.

        Args:
            limit: Maximum number of logs to return

        Returns:
            List of log file paths
        """
        if not self.log_dir.exists():
            return []

        logs = sorted(self.log_dir.glob("*.log"), reverse=True)[:limit]
        return [str(log) for log in logs]

    def set_project_log_dir(self, project_log_dir) -> None:
        """Redirect the file handler to a project-level log directory.

        Call this from __main__.py after the settings file is loaded in batch
        mode so that analysis logs land in PROJECT_ROOT/logs rather than the
        app install directory.

        Args:
            project_log_dir: Path or str — the target log directory
                             (typically settings.LOG_DIR).
        """
        project_log_dir = Path(project_log_dir)
        try:
            project_log_dir.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError) as exc:
            self.warning(f"Could not create project log dir {project_log_dir}: {exc}")
            return

        if self.file_handler is None:
            return

        # Close and remove the current file handler
        old_path = self.current_log_file
        self.logger.removeHandler(self.file_handler)
        try:
            self.file_handler.close()
        except Exception:
            pass

        # Open a new handler in the project directory, keeping the same timestamp
        log_stem = Path(old_path).name  # e.g. app_20260611_143200.log
        new_log_file = project_log_dir / log_stem
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        new_handler = logging.FileHandler(new_log_file, encoding='utf-8', errors='replace')
        new_handler.setLevel(logging.INFO)
        new_handler.setFormatter(detailed_formatter)
        self.logger.addHandler(new_handler)
        self.file_handler = new_handler
        self.log_dir = project_log_dir
        self.current_log_file = str(new_log_file)

        # Redirect the tee streams to the new file
        import sys as _sys
        from utils.logger import _TeeStream
        if isinstance(_sys.stdout, _TeeStream):
            _sys.stdout._log = new_handler.stream
        if isinstance(_sys.stderr, _TeeStream):
            _sys.stderr._log = new_handler.stream

        self.info(f"Log redirected to project dir: {new_log_file}")

    def clear_old_logs(self, days: int = 7) -> None:
        """
        Clear log files older than specified days.

        Args:
            days: Number of days to keep
        """
        from datetime import timedelta
        import time

        cutoff_time = time.time() - (days * 86400)

        if not self.log_dir.exists():
            return

        for log_file in self.log_dir.glob("*.log"):
            if log_file.stat().st_mtime < cutoff_time:
                try:
                    log_file.unlink()
                except Exception as e:
                    self.warning(f"Failed to delete old log: {e}")


# Create global logger instance
logger = AppLogger()
