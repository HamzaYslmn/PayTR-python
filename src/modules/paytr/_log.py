"""Logging for the library — configured automatically, zero extra deps.

On import we attach a single handler to the dedicated ``paytr`` logger (never
the root logger) with propagation off, so PayTR logs render nicely out of the
box without the host app calling anything, and without double-printing through
the app's own logging. Only the ``paytr`` namespace is touched, so this is safe
to sit alongside any other application's logging config.

To take control:

* ``PAYTR_LOG=off`` (env, before import) — don't auto-install anything.
* ``PAYTR_LOG=debug`` / ``info`` / ``warning`` … — set the level.
* :func:`setup_logging` — reconfigure the level / colors at runtime.
* Or just configure the ``paytr`` logger yourself; we never touch root.

The output style mimics uvicorn (``[PAYTR] INFO:     message``) but is
implemented here so the base library needs no server dependency.
"""

from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger("paytr")

_RESET = "\033[0m"
_LEVEL_COLORS = {
    "DEBUG": "\033[36m",     # cyan
    "INFO": "\033[32m",      # green
    "WARNING": "\033[33m",   # yellow
    "ERROR": "\033[31m",     # red
    "CRITICAL": "\033[1;31m",  # bold red
}


class _Formatter(logging.Formatter):
    """``[PAYTR] LEVEL:    message`` with optional ANSI colors."""

    def __init__(self, use_colors: bool | None = None) -> None:
        super().__init__()
        self.use_colors = sys.stderr.isatty() if use_colors is None else use_colors

    def format(self, record: logging.LogRecord) -> str:
        prefix = f"{record.levelname}:".ljust(9)
        if self.use_colors:
            prefix = f"{_LEVEL_COLORS.get(record.levelname, '')}{prefix}{_RESET}"
        text = f"[PAYTR] {prefix} {record.getMessage()}"
        if record.exc_info:
            text += "\n" + self.formatException(record.exc_info)
        return text


def _coerce_level(level: int | str) -> int:
    if isinstance(level, str):
        return logging.getLevelName(level.upper())  # name -> int
    return level


def setup_logging(
    level: int | str = logging.INFO,
    *,
    use_colors: bool | None = None,
    force: bool = False,
) -> logging.Logger:
    """Configure the ``paytr`` logger and return it.

    Runs automatically on import (unless ``PAYTR_LOG=off``); call it yourself
    only to change the level or force colors on/off. Idempotent: it won't stack
    handlers. Pass ``force=True`` to replace existing handlers.
    """
    if force:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)

    has_real_handler = any(
        not isinstance(h, logging.NullHandler) for h in logger.handlers
    )
    if not has_real_handler:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(_Formatter(use_colors=use_colors))
        logger.addHandler(handler)
        logger.propagate = False  # our handler owns output; don't double-log

    logger.setLevel(_coerce_level(level))
    return logger


# Auto-install on import so logs work out of the box. Opt out with PAYTR_LOG=off.
_env = os.environ.get("PAYTR_LOG", "").strip().lower()
if _env not in ("off", "0", "false", "none", "disable"):
    setup_logging(level=_env.upper() if _env else logging.INFO)
