"""Centralised logging.

The original pipeline used bare ``print`` calls scattered through the code,
which made it impossible to silence output or capture it in a host application
(e.g. the BioScout GUI console). Here every module obtains a named logger via
:func:`get_logger`; the host can configure handlers/levels once.
"""
from __future__ import annotations

import logging
from pathlib import Path

_CONFIGURED = False
_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def add_file_handler(path: str | Path, name: str = "tps_personalise") -> Path:
    """Also write the package's logs to ``path``. Idempotent per path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    resolved = str(path.resolve())
    for h in logger.handlers:
        if isinstance(h, logging.FileHandler) and getattr(h, "_tps_path", None) == resolved:
            return path  # already attached
    fh = logging.FileHandler(path, mode="w", encoding="utf-8")
    fh.setFormatter(logging.Formatter(_FORMAT))
    fh._tps_path = resolved  # type: ignore[attr-defined]
    logger.addHandler(fh)
    return path


def get_logger(name: str = "tps_personalise") -> logging.Logger:
    """Return a package logger. Adds a default handler once, only if the host
    application has not configured logging itself."""
    global _CONFIGURED
    logger = logging.getLogger(name)
    if not _CONFIGURED and not logging.getLogger().handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        _CONFIGURED = True
    return logger
