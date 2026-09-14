"""Logging: rotating file in the app-data dir plus stderr. User actions,
errors and crashes all go through the "heaterapp" logger hierarchy."""
from __future__ import annotations

import logging
import logging.handlers
import platform
import sys
from typing import Optional

from . import settings

LOGGER_NAME = "heaterapp"
_file_handler: Optional[logging.Handler] = None
_enabled = True


def setup(enabled: bool = True) -> logging.Logger:
    global _file_handler
    root = logging.getLogger(LOGGER_NAME)
    root.setLevel(logging.DEBUG)
    root.propagate = False
    if _file_handler is None:
        fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
        path = settings.log_dir() / "heaterapp.log"
        fh = logging.handlers.RotatingFileHandler(path, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
        _file_handler = fh
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(fmt)
        sh.setLevel(logging.WARNING)
        root.addHandler(sh)
    set_enabled(enabled)
    root.info("---- session start: python %s, %s %s ----", platform.python_version(),
              platform.system(), platform.release())
    return root


def set_enabled(enabled: bool) -> None:
    """Enable/disable writing to the log file at runtime."""
    global _enabled
    _enabled = enabled
    if _file_handler is not None:
        _file_handler.setLevel(logging.DEBUG if enabled else logging.CRITICAL + 1)
    logging.getLogger(LOGGER_NAME).info("logging %s", "enabled" if enabled else "disabled")


def is_enabled() -> bool:
    return _enabled


def log_path() -> str:
    return str(settings.log_dir() / "heaterapp.log")


def install_excepthook(on_crash=None) -> None:
    """Route uncaught exceptions to the log (and an optional UI callback)."""
    log = logging.getLogger(LOGGER_NAME)

    def hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        log.critical("UNHANDLED EXCEPTION", exc_info=(exc_type, exc, tb))
        if on_crash is not None:
            try:
                on_crash(exc_type, exc, tb)
            except Exception:
                log.exception("crash handler failed")

    sys.excepthook = hook
