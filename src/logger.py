"""
logger.py
---------
Simple structured logger for the Lyra pipeline.

Design: minimal, zero-dependency, module-level loggers with consistent
formatting.  Writes to stderr so stdout stays clean for CLI output.

Each module gets its own logger instance::

    from logger import get_logger
    _log = get_logger("planner", enabled=os.getenv("LYRA_PLANNER_DEBUG", "0") == "1")

Global debug mode (``LYRA_DEBUG=1``) enables all loggers.
"""

import os
import sys
import time
from typing import Dict, Optional

# Global override — when LYRA_DEBUG=1, ALL loggers are enabled regardless
# of their individual module-level settings.
_GLOBAL_DEBUG = os.getenv("LYRA_DEBUG", "0") == "1"


class Logger:
    """Minimal structured logger with timing support."""

    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self._enabled = enabled
        self._timers: Dict[str, float] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def debug(self, msg: str) -> None:
        """Log a debug message (suppressed when disabled)."""
        if _GLOBAL_DEBUG or self._enabled:
            self._write("DEBUG", msg)

    def info(self, msg: str) -> None:
        """Log an informational message (always visible)."""
        self._write("INFO", msg)

    def warn(self, msg: str) -> None:
        """Log a warning."""
        self._write("WARN", msg)

    def error(self, msg: str) -> None:
        """Log an error."""
        self._write("ERROR", msg)

    def start_timer(self, label: str) -> None:
        """Record the start time for *label*."""
        self._timers[label] = time.time()

    def end_timer(self, label: str) -> float:
        """End the timer for *label* and return elapsed seconds.

        If *label* was never started, returns 0.0.
        """
        start = self._timers.pop(label, None)
        if start is None:
            return 0.0
        elapsed = time.time() - start
        self.debug(f"{label}: {elapsed:.3f}s")
        return elapsed

    @property
    def enabled(self) -> bool:
        return _GLOBAL_DEBUG or self._enabled

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _write(self, level: str, msg: str) -> None:
        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] [{self.name}] {level} {msg}", file=sys.stderr)


def get_logger(name: str, enabled: bool = True) -> Logger:
    """Create a module-level logger.

    Parameters
    ----------
    name : str
        Short module name shown in log prefix (e.g. ``"planner"``).
    enabled : bool
        Whether debug messages from this logger are shown when
        ``LYRA_DEBUG`` is not set.  Info/warn/error messages are
        always shown regardless.
    """
    return Logger(name, enabled)
