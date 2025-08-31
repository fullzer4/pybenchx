from __future__ import annotations

from typing import List, Optional


DEFAULT_BUDGET_NS = int(300e6)


def apply_profile(profile: Optional[str], propairs: List[str], budget_ns: Optional[int]) -> tuple[list[str], Optional[int], bool]:
    """Return (propairs_out, budget_ns_out, smoke).

    - smoke True disables calibration.
    - Profiles: thorough (~1s, repeat=30), smoke (repeat=3, warmup=0)
    - Default: smoke
    """
    smoke = False
    props = list(propairs)
    if profile is None or profile == "smoke":
        smoke = True
        props = ["repeat=3", "warmup=0"] + props
        return props, budget_ns, smoke
    if profile == "thorough":
        props = ["repeat=30"] + props
        if budget_ns is None:
            budget_ns = int(1e9)
        return props, budget_ns, smoke
    # Fallback: treat unknown as smoke
    smoke = True
    props = ["repeat=3", "warmup=0"] + props
    return props, budget_ns, smoke


__all__ = ["apply_profile", "DEFAULT_BUDGET_NS"]
