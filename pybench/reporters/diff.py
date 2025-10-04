"""Comparison and diff output utilities."""
from __future__ import annotations

from typing import Optional

from .. import compare as compare_mod
from ..run_model import Run


def format_comparison(
    current: Run,
    baseline: Run,
    baseline_name: str,
    *,
    use_color: bool = True,
    fail_on: Optional[str] = None,
) -> tuple[str, int]:
    """Format comparison output and return (output, exit_code).
    
    Returns:
        (formatted_output, exit_code)
        exit_code: 0 = passed, 2 = thresholds violated
    """
    report = compare_mod.diff(current, baseline)
    policy = compare_mod.parse_fail_policy(fail_on or "")
    violated = compare_mod.violates_policy(report, policy)
    
    # ANSI colors
    RESET = "\033[0m" if use_color else ""
    GREEN = "\033[32m" if use_color else ""
    RED = "\033[31m" if use_color else ""
    YELLOW = "\033[33m" if use_color else ""
    
    lines = [f"\n📊 Comparing against: {baseline_name}\n"]
    
    for d in report.compared:
        # Status symbol
        if d.status == "better":
            symbol = f"{GREEN}🚀 faster{RESET}" if use_color else "✓ faster"
            color = GREEN
        elif d.status == "worse":
            symbol = f"{RED}🐌 slower{RESET}" if use_color else "✗ slower"
            color = RED
        else:
            symbol = f"{YELLOW}≈ same{RESET}" if use_color else "≈ same"
            color = YELLOW
        
        # Format delta with sign and color
        delta_str = f"{color}{d.delta_pct:+.2f}%{RESET}" if use_color else f"{d.delta_pct:+.2f}%"
        p_str = f"p={d.p_value:.3f}" if d.p_value is not None else "p=n/a"
        
        lines.append(f"  {d.group}/{d.name}: {delta_str} | {p_str} | {symbol}")
    
    if report.suite_changed:
        lines.append(f"\n{YELLOW}⚠️  Suite changed (partial diff){RESET}" if use_color else "\n⚠️  Suite changed (partial diff)")
    
    if violated:
        lines.append(f"\n{RED}❌ Thresholds violated{RESET}" if use_color else "\n❌ Thresholds violated")
        exit_code = 2
    else:
        lines.append(f"\n{GREEN}✅ All checks passed{RESET}" if use_color else "\n✅ All checks passed")
        exit_code = 0
    
    return "\n".join(lines), exit_code


__all__ = ["format_comparison"]
