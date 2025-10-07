"""Comparison and diff output utilities."""
from __future__ import annotations

from .. import compare as compare_mod
from ..run_model import Run


def format_comparison(
    current: Run,
    baseline: Run,
    baseline_name: str,
    *,
    use_color: bool = True,
    fail_on: str | None = None,
) -> tuple[str, int]:
    """Format comparison output and return (output, exit_code).

    Returns:
        (formatted_output, exit_code)
        exit_code: 0 = passed, 2 = thresholds violated
    """
    report = compare_mod.diff(current, baseline)
    policy = compare_mod.parse_fail_policy(fail_on or "")
    violated = compare_mod.violates_policy(report, policy)

    reset = "\033[0m" if use_color else ""
    green = "\033[32m" if use_color else ""
    red = "\033[31m" if use_color else ""
    yellow = "\033[33m" if use_color else ""

    lines = [f"\n📊 Comparing against: {baseline_name}\n"]

    for d in report.compared:
        if d.status == "better":
            symbol = f"{green}🚀 faster{reset}" if use_color else "✓ faster"
            color = green
        elif d.status == "worse":
            symbol = f"{red}🐌 slower{reset}" if use_color else "✗ slower"
            color = red
        else:
            symbol = f"{yellow}≈ same{reset}" if use_color else "≈ same"
            color = yellow

        if use_color:
            delta_str = f"{color}{d.delta_pct:+.2f}%{reset}"
        else:
            delta_str = f"{d.delta_pct:+.2f}%"
        p_str = f"p={d.p_value:.3f}" if d.p_value is not None else "p=n/a"

        lines.append(f"  {d.group}/{d.name}: {delta_str} | {p_str} | {symbol}")

    if report.suite_changed:
        if use_color:
            change_msg = f"\n{yellow}⚠️  Suite changed (partial diff){reset}"
        else:
            change_msg = "\n⚠️  Suite changed (partial diff)"
        lines.append(change_msg)

    if violated:
        if use_color:
            violation_msg = f"\n{red}❌ Thresholds violated{reset}"
        else:
            violation_msg = "\n❌ Thresholds violated"
        lines.append(violation_msg)
        exit_code = 2
    else:
        if use_color:
            success_msg = f"\n{green}✅ All checks passed{reset}"
        else:
            success_msg = "\n✅ All checks passed"
        lines.append(success_msg)
        exit_code = 0

    return "\n".join(lines), exit_code


__all__ = ["format_comparison"]
