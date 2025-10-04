from __future__ import annotations

from typing import List, Optional


DEFAULT_BUDGET_NS = int(300e6)


def apply_profile(profile: Optional[str], propairs: List[str], budget_ns: Optional[int]) -> tuple[list[str], Optional[int], bool]:
    """Return (propairs_out, budget_ns_out, smoke).

    - smoke True disables calibration.
    - Profiles: 
      - quick (n=10, repeat=1, warmup=0) - DEFAULT: ultra fast for rapid iteration
      - smoke (repeat=3, warmup=0) - balanced mode
      - thorough (~1s, repeat=30) - deep analysis
    """
    smoke = False
    props = list(propairs)
    
    # Default is now "quick" for fast microbenchmarking
    if profile is None or profile == "quick":
        smoke = True
        props = ["n=10", "repeat=1", "warmup=0"] + props
        return props, budget_ns, smoke
    
    if profile == "smoke":
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
