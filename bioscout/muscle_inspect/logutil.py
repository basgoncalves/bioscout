"""Timestamped logging + simple timing helpers (no OpenSim dependency)."""
from __future__ import annotations

import contextlib
import logging
import time

LOG = logging.getLogger("muscle_inspect")


def setup_logging(level: int = logging.INFO, quiet_opensim: bool = True) -> logging.Logger:
    """Configure a single clean stream handler. Returns the package logger."""
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
    LOG.handlers[:] = [handler]
    LOG.setLevel(level)
    LOG.propagate = False

    if quiet_opensim:
        try:  # hide the harmless "Couldn't find file '*.vtp'" geometry warnings
            import opensim
            opensim.Logger.setLevelString("error")
        except Exception:
            pass
    return LOG


@contextlib.contextmanager
def timed(label: str, logger: logging.Logger = LOG):
    """Log start/end of a block and the elapsed seconds."""
    logger.info("START  %s", label)
    t0 = time.perf_counter()
    try:
        yield
    finally:
        logger.info("DONE   %s  (%.2fs)", label, time.perf_counter() - t0)


def fmt_hms(seconds: float) -> str:
    m, s = divmod(int(round(seconds)), 60)
    h, m = divmod(m, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:d}:{s:02d}"


def add_file_handler(path, logger: logging.Logger = LOG):
    """Also write the log to `path` (same format as the console handler)."""
    h = logging.FileHandler(path, mode="w", encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
    logger.addHandler(h)
    return h
