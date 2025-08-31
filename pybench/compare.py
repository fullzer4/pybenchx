# Placeholder for compare/diff logic including Mann–Whitney U tests.

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

try:
    from math import comb  # py3.8+
except Exception:  # pragma: no cover
    comb = None  # type: ignore

from .run_model import Run


@dataclass
class VariantDiff:
    name: str
    group: str
    base_mean: float
    curr_mean: float
    delta_pct: float  # positive = regression (slower)
    p_value: Optional[float]
    status: str  # "better" | "same" | "worse"
    # Additional metrics
    base_p99: float = float("nan")
    curr_p99: float = float("nan")
    delta_p99_pct: float = float("nan")


@dataclass
class DiffReport:
    suite_changed: bool
    compared: List[VariantDiff]


def _mann_whitney_u(x: List[float], y: List[float]) -> Optional[float]:
    # Very small n fallback: return None to signal low power / skip
    n1, n2 = len(x), len(y)
    if n1 < 2 or n2 < 2:
        return None
    # Rank-sum approximation by pairwise comparison (ties ignored best-effort)
    gt = 0
    ties = 0
    for a in x:
        for b in y:
            if a > b:
                gt += 1
            elif a == b:
                ties += 1
    u1 = gt + ties * 0.5
    # Normal approximation for p-value (two-sided) using large-sample
    import math

    mu = n1 * n2 / 2.0
    sigma = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12.0)
    if sigma == 0:
        return None
    z = (u1 - mu) / sigma
    # two-sided
    try:
        from math import erfc
        p = erfc(abs(z) / math.sqrt(2.0))
    except Exception:
        # crude fallback
        p = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0))))
    return p


def _index_results(run: Run) -> Dict[Tuple[str, str], object]:
    idx: Dict[Tuple[str, str], object] = {}
    for r in run.results:
        idx[(r.group, r.name)] = r
    return idx


def diff(current: Run, baseline: Run, alpha: float = 0.05) -> DiffReport:
    base_idx = _index_results(baseline)
    curr_idx = _index_results(current)

    keys = sorted(set(base_idx.keys()) & set(curr_idx.keys()))
    suite_changed = (set(base_idx.keys()) != set(curr_idx.keys())) or (
        current.suite_signature != baseline.suite_signature
    )

    compared: List[VariantDiff] = []
    for key in keys:
        b = base_idx[key]
        c = curr_idx[key]
        base_mean = b.stats.mean
        curr_mean = c.stats.mean
        delta_pct = ((curr_mean - base_mean) / base_mean * 100.0) if base_mean > 0 else 0.0
        # p99 deltas
        base_p99 = getattr(b.stats, "p99", float("nan"))
        curr_p99 = getattr(c.stats, "p99", float("nan"))
        if base_p99 and base_p99 == base_p99 and base_p99 > 0 and curr_p99 == curr_p99:
            delta_p99_pct = ((curr_p99 - base_p99) / base_p99 * 100.0)
        else:
            delta_p99_pct = float("nan")
        # Use samples if available, else approximate with repeated mean values
        xs = b.samples_ns if b.samples_ns else [b.stats.mean] * b.repeat
        ys = c.samples_ns if c.samples_ns else [c.stats.mean] * c.repeat
        p = _mann_whitney_u(xs, ys)
        status = (
            "worse" if delta_pct > 1.0 and (p is None or p < alpha) else
            "better" if delta_pct < -1.0 and (p is None or p < alpha) else
            "same"
        )
        compared.append(
            VariantDiff(
                name=c.name,
                group=c.group,
                base_mean=base_mean,
                curr_mean=curr_mean,
                delta_pct=delta_pct,
                p_value=p,
                status=status,
                base_p99=base_p99,
                curr_p99=curr_p99,
                delta_p99_pct=delta_p99_pct,
            )
        )

    return DiffReport(suite_changed=suite_changed, compared=compared)


def parse_fail_policy(policy: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    if not policy:
        return out
    parts = [p.strip() for p in policy.split(",") if p.strip()]
    for p in parts:
        if ":" not in p:
            continue
        k, v = p.split(":", 1)
        k = k.strip().lower()
        v = v.strip().rstrip("%")
        try:
            out[k] = float(v)
        except Exception:
            pass
    return out


def violates_policy(report: DiffReport, policy: Dict[str, float], alpha: float = 0.05) -> bool:
    if not policy and not report.suite_changed:
        return False
    for d in report.compared:
        # Check p-value first: if significant and regression exceeds any metric threshold
        significant = (d.p_value is not None and d.p_value < alpha)
        if d.status == "worse" and significant:
            # mean policy
            if policy.get("mean") is not None and d.delta_pct > policy["mean"]:
                return True
            # p99 policy
            if policy.get("p99") is not None and (d.delta_p99_pct == d.delta_p99_pct) and d.delta_p99_pct > policy["p99"]:
                return True
    return False


__all__ = [
    "VariantDiff",
    "DiffReport",
    "diff",
    "parse_fail_policy",
    "violates_policy",
]
