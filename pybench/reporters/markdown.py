"""Render benchmark runs as GitHub-flavored Markdown tables."""

from __future__ import annotations

from ..run_model import Run
from ..utils import compute_speedups, fmt_time_ns


def render(run: Run, *, include_pvalues: bool = False) -> str:
    """Return a Markdown table describing the run."""
    headers = ["group", "benchmark", "time (avg)", "p99", "vs base"]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join([" --- "] * len(headers)) + "|",
    ]
    sp = compute_speedups(run.results)
    for r in run.results:
        name = r.name + ("  ★" if r.baseline else "")
        mean = fmt_time_ns(r.stats.mean)
        p99 = fmt_time_ns(r.stats.p99)
        sid = id(r)
        if sid in sp:
            s = sp[sid]
            if s != s:  # NaN
                vs = "baseline"
            elif s == 1.0:
                vs = "≈ same"
            else:
                vs = f"{s:.2f}× faster" if s > 1.0 else f"{(1.0 / s):.2f}× slower"
        else:
            vs = "-"
        lines.append(f"| {r.group} | {name} | {mean} | {p99} | {vs} |")
    return "\n".join(lines)


__all__ = ["render"]
