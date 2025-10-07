"""Timing helpers with optional high-resolution context support."""

from __future__ import annotations

import time

# Monotonic clock with fallback for very old Pythons
if hasattr(time, "perf_counter_ns"):
    def _pc_ns() -> int:
        """Return a monotonic timestamp in nanoseconds."""
        return time.perf_counter_ns()


else:
    def _pc_ns() -> int:
        """Fallback conversion to nanoseconds when ``perf_counter_ns`` is missing."""
        return int(time.perf_counter() * 1e9)


class BenchContext:
    """Per-iteration manual timing helper (call start()/end() around the hot region).

    Implemented without dataclasses/slots to support Python 3.7–3.9.
    """
    __slots__ = ("_running", "_t0", "_accum")

    def __init__(self) -> None:
        self._running: bool = False
        self._t0: int = 0
        self._accum: int = 0

    def start(self) -> None:
        """Begin measuring a region if not already running."""
        if self._running:
            return
        self._running = True
        self._t0 = _pc_ns()

    def end(self) -> None:
        """Record elapsed time since :meth:`start` when running."""
        if not self._running:
            return
        self._accum += _pc_ns() - self._t0
        self._running = False

    def _reset(self) -> None:
        """Reset internal timing state."""
        self._running = False
        self._t0 = 0
        self._accum = 0

    def _elapsed_ns(self) -> int:
        """Return accumulated nanoseconds."""
        return self._accum


__all__ = ["BenchContext", "_pc_ns"]
