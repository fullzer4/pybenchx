from __future__ import annotations

from typing import List, Optional, Tuple, Dict

from .bench_model import Case
from .runner import calibrate_n as _calibrate_n, detect_used_ctx as _detect_used_ctx
from .params import make_variants as _make_variants
from .profiles import DEFAULT_BUDGET_NS
from .run_model import VariantResult


def parse_ns(s: str) -> int:
    """Parse human-friendly time strings into nanoseconds."""
    s = s.strip().lower()
    if s.endswith("ms"):
        return int(float(s[:-2]) * 1e6)
    if s.endswith("s"):
        return int(float(s[:-1]) * 1e9)
    return int(float(s))


# Shared formatting helper

def fmt_time_ns(ns: float) -> str:
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


# Percentile with linear interpolation; expects a pre-sorted list

def percentile(sorted_vals: List[float], q: float) -> float:
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


# Compute speedups vs baseline per group (shared by reporters)

def compute_speedups(results: List[VariantResult]) -> Dict[int, float]:
    by_group: Dict[str, List[VariantResult]] = {}
    for r in results:
        if r.group == "-":
            continue
        by_group.setdefault(r.group, []).append(r)

    speedups: Dict[int, float] = {}
    for _, items in by_group.items():
        base_r: Optional[VariantResult] = next((r for r in items if r.baseline), None)
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
            speedups[id(r)] = (base_mean / r.stats.mean) if (r.stats.mean and base_mean) else float("nan")
    return speedups


def prepare_variants(case: Case, *, budget_ns: Optional[int], max_n: int, smoke: bool):
    """
    Prepare (vname, vargs, vkwargs, used_ctx, local_n) for each variant.

    - used_ctx is computed only for context mode
    - local_n is calibrated per-variant unless smoke=True
    """
    variants = _make_variants(case)
    prepared = []
    for vname, vargs, vkwargs in variants:
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
            # budget per repeat to split across repeats
            target = max(1_000_000, int(target_total) // max(1, case.repeat))
            try:
                calib_n, _ = _calibrate_n(
                    case.func,
                    case.mode,
                    vargs,
                    vkwargs,
                    target_ns=target,
                    max_n=max_n,
                )
                local_n = max(case.n, calib_n)  # never reduce n
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
]
