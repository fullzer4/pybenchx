"""Serializable data structures representing benchmark run outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StatSummary:
    """Aggregate statistics for a variant repeat set."""
    mean: float
    median: float
    stdev: float
    min: float
    max: float
    p75: float
    p99: float
    p995: float


@dataclass
class VariantResult:
    """Measured results for a concrete benchmark variant."""
    name: str
    group: str
    n: int
    repeat: int
    baseline: bool
    stats: StatSummary
    samples_ns: list[float] | None = None


@dataclass
class RunMeta:
    """Metadata captured once per benchmark run."""
    tool_version: str
    started_at: str
    duration_s: float
    profile: str | None
    budget_ns: int | None
    git: dict[str, Any]
    python_version: str
    os: str
    cpu: str
    perf_counter_resolution: float
    gc_enabled: bool


@dataclass
class Run:
    """Logical grouping of metadata and variant results."""
    meta: RunMeta
    suite_signature: str
    results: list[VariantResult] = field(default_factory=list)


__all__ = [
    "Run",
    "RunMeta",
    "VariantResult",
    "StatSummary",
]
