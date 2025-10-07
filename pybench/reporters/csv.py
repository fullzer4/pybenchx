"""Render benchmark runs as CSV strings."""

from __future__ import annotations

from io import StringIO

from ..run_model import Run


def render(run: Run) -> str:
    """Return a CSV representation of ``run`` results."""
    out = StringIO()
    out.write("benchmark,group,mean_ns,p99_ns,baseline\n")
    for r in run.results:
        out.write(f"{r.name},{r.group},{r.stats.mean:.6f},{r.stats.p99:.6f},{int(r.baseline)}\n")
    return out.getvalue()


__all__ = ["render"]
