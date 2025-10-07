"""Render benchmark results as ANSI-aware tables."""

from __future__ import annotations

import math

from ..run_model import VariantResult
from ..utils import compute_speedups, fmt_time_ns
from ._ansi import CYAN, DIM, MAGENTA, RESET, YELLOW, pad_cell


def format_table(
    results: list[VariantResult],
    *,
    use_color: bool = True,
    sort: str | None = None,
    desc: bool = False,
    brief: bool = False,
) -> str:
    """Return a formatted table for ``results`` suitable for console output."""
    speedups = compute_speedups(results)

    headers = (
        [("benchmark", 28, "<"), ("time (avg)", 16, ">"), ("vs base", 12, ">")]
        if brief
        else [
            ("benchmark", 28, "<"),
            ("time (avg)", 16, ">"),
            ("iter/s", 12, ">"),
            ("(min … max)", 24, ">"),
            ("p75", 12, ">"),
            ("p99", 12, ">"),
            ("p995", 12, ">"),
            ("vs base", 12, ">"),
        ]
    )

    def colorize(text: str, code: str) -> str:
        return text if not use_color else f"{code}{text}{RESET}"

    def fmt_head() -> str:
        return " ".join(pad_cell(h, w, a) for h, w, a in headers)

    def fmt_ips(mean_ns: float) -> str:
        if mean_ns <= 0:
            return "-"
        ips = 1e9 / mean_ns
        if ips >= 1_000_000:
            return f"{ips / 1_000_000.0:.1f} M"
        if ips >= 1_000:
            return f"{ips / 1_000.0:.1f} K"
        return f"{ips:.1f}"

    grouped: dict[str, list[VariantResult]] = {}
    for r in results:
        grouped.setdefault(r.group, []).append(r)

    if sort == "group":
        group_keys = sorted(grouped.keys(), reverse=desc)
    else:
        seen: list[str] = []
        for r in results:
            if r.group not in seen:
                seen.append(r.group)
        group_keys = seen

    def sort_items(items: list[VariantResult]) -> list[VariantResult]:
        if sort in {"group", "time"}:
            return sorted(items, key=lambda r: r.stats.mean, reverse=desc)
        return items

    lines = [fmt_head()]
    total_width = sum(w for _, w, _ in headers)
    for g in group_keys:
        items = sort_items(grouped[g])
        if g != "-":
            lines.append(colorize(pad_cell(f"group: {g}", total_width, "<"), DIM))
        for r in items:
            avg = fmt_time_ns(r.stats.mean)
            sid = id(r)
            vs = "-"
            if sid in speedups:
                s = speedups[sid]
                if math.isnan(s):
                    vs = "baseline"
                elif s == 1.0:
                    vs = "≈ same"
                elif s > 0:
                    vs = f"{s:.2f}× faster" if s > 1.0 else f"{1.0 / s:.2f}× slower"

            name = r.name + ("  ★" if r.baseline else "")
            if brief:
                cells = [name, colorize(avg, YELLOW), vs]
            else:
                lo = fmt_time_ns(r.stats.min)
                hi = fmt_time_ns(r.stats.max)
                p75 = fmt_time_ns(r.stats.p75)
                p99 = fmt_time_ns(r.stats.p99)
                p995 = fmt_time_ns(r.stats.p995)
                cells = [
                    name,
                    colorize(avg, YELLOW),
                    fmt_ips(r.stats.mean),
                    f"{colorize(lo, CYAN)} … {colorize(hi, MAGENTA)}",
                    colorize(p75, MAGENTA),
                    colorize(p99, MAGENTA),
                    colorize(p995, MAGENTA),
                    vs,
                ]
            lines.append(
                " ".join(pad_cell(c, w, a) for (h, w, a), c in zip(headers, cells))
            )
    return "\n".join(lines)


__all__ = ["format_table", "compute_speedups"]
