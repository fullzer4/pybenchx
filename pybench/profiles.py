"""Profiles converting CLI shorthands into benchmark configurations."""

from __future__ import annotations

DEFAULT_BUDGET_NS = int(300e6)


def apply_profile(
    profile: str | None,
    propairs: list[str],
    budget_ns: int | None,
) -> tuple[list[str], int | None, bool]:
    """Return overrides and calibration hints for a profile.

    Args:
        profile: Preset name (``quick``, ``smoke``, ``thorough``) or ``None``.
        propairs: Existing ``key=value`` overrides from the CLI.
        budget_ns: Calibration budget in nanoseconds.

    Returns:
        Tuple ``(propairs_out, budget_ns_out, smoke)`` where ``smoke`` flags
        whether calibration should be skipped.
    """
    smoke = False
    props = list(propairs)

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
