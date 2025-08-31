from __future__ import annotations

import time

# Monotonic clock with fallback for very old Pythons
if hasattr(time, "perf_counter_ns"):
    def _pc_ns() -> int:
        return time.perf_counter_ns()
else:  # pragma: no cover
    def _pc_ns() -> int:
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
        if self._running:
            return
        self._running = True
        self._t0 = _pc_ns()

    def end(self) -> None:
        if not self._running:
            return
        self._accum += _pc_ns() - self._t0
        self._running = False

    def _reset(self) -> None:
        self._running = False
        self._t0 = 0
        self._accum = 0

    def _elapsed_ns(self) -> int:
        return self._accum


__all__ = ["BenchContext", "_pc_ns"]
