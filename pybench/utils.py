"""Utility helpers shared across discovery, execution, and reporting."""

from __future__ import annotations

import hashlib
import os

from .bench_model import Case
from .params import make_variants as _make_variants
from .profiles import DEFAULT_BUDGET_NS
from .run_model import VariantResult
from .runner import calibrate_n as _calibrate_n
from .runner import detect_used_ctx as _detect_used_ctx


def _module_name_for_path(path: str) -> str:
    """Return a stable synthetic module name for ``path``."""
    p = os.path.abspath(path)
    h = hashlib.sha1(p.encode("utf-8")).hexdigest()[:12]
    stem = os.path.splitext(os.path.basename(p))[0]
    return f"pybenchx_{stem}_{h}"


def parse_ns(s: str) -> int:
    """Parse human-friendly time strings into nanoseconds."""
    s = s.strip().lower()
    if s.endswith("ms"):
        return int(float(s[:-2]) * 1e6)
    if s.endswith("s"):
        return int(float(s[:-1]) * 1e9)
    return int(float(s))


def fmt_time_ns(ns: float) -> str:
    """Format nanoseconds into a human-readable string."""
    if ns != ns:  # NaN
        return "-"
    if ns < 1_000:
        return f"{ns:.2f} ns"
    us = ns / 1_000.0
    if us < 1_000:
        return f"{us:.2f} µs"
    ms = us / 1_000.0
    if ms < 1_000:
        return f"{ms:.2f} ms"
    s = ms / 1_000.0
    return f"{s:.2f} s"


def percentile(sorted_vals: list[float], q: float) -> float:
    """Return the ``q`` percentile from ``sorted_vals`` (0-100)."""
    if not sorted_vals:
        return float("nan")
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    pos = (q / 100.0) * (n - 1)
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def compute_speedups(results: list[VariantResult]) -> dict[int, float]:
    """Compute per-variant speedups relative to detected baselines."""
    by_group: dict[str, list[VariantResult]] = {}
    for r in results:
        if r.group == "-":
            continue
        by_group.setdefault(r.group, []).append(r)

    speedups: dict[int, float] = {}
    for _, items in by_group.items():
        base_r: VariantResult | None = next((r for r in items if r.baseline), None)
        if base_r is None:
            for r in items:
                nl = r.name.lower()
                if "baseline" in nl or nl.startswith("base") or nl.endswith("base"):
                    base_r = r
                    break
        if base_r is None:
            continue
        base_mean = base_r.stats.mean
        speedups[id(base_r)] = float("nan")
        for r in items:
            if r is base_r:
                continue
            if base_mean > 0 and r.stats.mean > 0:
                pct_diff = abs((r.stats.mean - base_mean) / base_mean)
                if pct_diff <= 0.01:
                    speedups[id(r)] = 1.0
                    continue
            speedups[id(r)] = (
                (base_mean / r.stats.mean)
                if (r.stats.mean and base_mean)
                else float("nan")
            )
    return speedups


def prepare_variants(
    case: Case,
    *,
    budget_ns: int | None,
    max_n: int,
    smoke: bool,
):
    """Prepare (vname, vargs, vkwargs, used_ctx, local_n) for each variant.

    - used_ctx is computed only for context mode
    - local_n is calibrated per-variant unless smoke=True

    Fast-path optimization: skip context detection and calibration for simple cases.
    """
    variants = _make_variants(case)
    prepared = []

    is_simple = smoke and not case.params and case.mode == "func"

    for vname, vargs, vkwargs in variants:
        if is_simple:
            prepared.append((vname, vargs, vkwargs, False, case.n))
            continue

        if case.mode == "context":
            try:
                used_ctx = _detect_used_ctx(case.func, vargs, vkwargs)
            except Exception:
                used_ctx = False
        else:
            used_ctx = False

        if smoke:
            local_n = case.n
        else:
            target_total = budget_ns if budget_ns is not None else DEFAULT_BUDGET_NS
            target = max(1_000_000, int(target_total) // max(1, case.repeat))
            try:
                calib_n, calib_used_ctx = _calibrate_n(
                    case.func,
                    case.mode,
                    vargs,
                    vkwargs,
                    target_ns=target,
                    max_n=max_n,
                )
                local_n = max(case.n, calib_n)  # never reduce n
                if case.mode == "context":
                    used_ctx = calib_used_ctx
            except Exception:
                local_n = case.n
        prepared.append((vname, vargs, vkwargs, used_ctx, local_n))
    return prepared


__all__ = [
    "parse_ns",
    "prepare_variants",
    "fmt_time_ns",
    "percentile",
    "compute_speedups",
    "_module_name_for_path",
]
