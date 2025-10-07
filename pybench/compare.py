"""Stateless helpers for comparing two benchmark runs.

Implements Mann–Whitney U significance testing and a thin domain model for
reporting structured comparison results, plus helpers for policy-driven
threshold evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass

try:
    from math import comb  # py3.8+
except Exception:
    comb = None

from .run_model import Run


@dataclass
class VariantDiff:
    """Per-variant comparison metrics between a baseline and current run."""
    name: str
    group: str
    base_mean: float
    curr_mean: float
    delta_pct: float
    p_value: float | None
    status: str  # "better" | "same" | "worse"
    base_p99: float = float("nan")
    curr_p99: float = float("nan")
    delta_p99_pct: float = float("nan")


@dataclass
class DiffReport:
    """Aggregate comparison result for an entire suite."""
    suite_changed: bool
    compared: list[VariantDiff]


def _mann_whitney_u(x: list[float], y: list[float]) -> float | None:
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


def _index_results(run: Run) -> dict[tuple[str, str], object]:
    idx: dict[tuple[str, str], object] = {}
    for r in run.results:
        idx[(r.group, r.name)] = r
    return idx


def diff(current: Run, baseline: Run, alpha: float = 0.05) -> DiffReport:
    """Compare two runs and compute distribution deltas.

    Args:
        current: Run produced by the latest benchmark execution.
        baseline: Run to compare against.
        alpha: Significance threshold for the Mann–Whitney test.

    Returns:
        DiffReport describing per-variant changes and suite shape differences.
    """
    base_idx = _index_results(baseline)
    curr_idx = _index_results(current)

    keys = sorted(set(base_idx.keys()) & set(curr_idx.keys()))
    suite_changed = (set(base_idx.keys()) != set(curr_idx.keys())) or (
        current.suite_signature != baseline.suite_signature
    )

    compared: list[VariantDiff] = []
    for key in keys:
        b = base_idx[key]
        c = curr_idx[key]
        base_mean = b.stats.mean
        curr_mean = c.stats.mean
        delta_pct = (
            (curr_mean - base_mean) / base_mean * 100.0
        ) if base_mean > 0 else 0.0

        base_p99 = getattr(b.stats, "p99", float("nan"))
        curr_p99 = getattr(c.stats, "p99", float("nan"))
        if base_p99 and base_p99 == base_p99 and base_p99 > 0 and curr_p99 == curr_p99:
            delta_p99_pct = ((curr_p99 - base_p99) / base_p99 * 100.0)
        else:
            delta_p99_pct = float("nan")

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


def parse_fail_policy(policy: str) -> dict[str, float]:
    """Parse ``metric:percent`` strings into a numeric policy mapping."""
    out: dict[str, float] = {}
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


def violates_policy(
    report: DiffReport,
    policy: dict[str, float],
    alpha: float = 0.05,
) -> bool:
    """Return True when the diff violates the given policy thresholds."""
    if not policy and not report.suite_changed:
        return False
    for d in report.compared:
        # Check p-value first: only treat significant regressions as violations
        significant = (d.p_value is not None and d.p_value < alpha)
        if d.status == "worse" and significant:

            if policy.get("mean") is not None and d.delta_pct > policy["mean"]:
                return True

            if (
                policy.get("p99") is not None
                and (d.delta_p99_pct == d.delta_p99_pct)
                and d.delta_p99_pct > policy["p99"]
            ):
                return True
    return False


__all__ = [
    "VariantDiff",
    "DiffReport",
    "diff",
    "parse_fail_policy",
    "violates_policy",
]
