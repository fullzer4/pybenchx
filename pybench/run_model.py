# Placeholder schema definitions for future implementation.
# This module defines the JSON-serializable "Run" model and helpers.

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class StatSummary:
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
    name: str
    group: str
    n: int
    repeat: int
    baseline: bool
    stats: StatSummary
    samples_ns: Optional[List[float]] = None


@dataclass
class RunMeta:
    tool_version: str
    started_at: str
    duration_s: float
    profile: Optional[str]
    budget_ns: Optional[int]
    git: Dict[str, Any]
    python_version: str
    os: str
    cpu: str
    perf_counter_resolution: float
    gc_enabled: bool


@dataclass
class Run:
    meta: RunMeta
    suite_signature: str
    results: List[VariantResult] = field(default_factory=list)


__all__ = [
    "Run",
    "RunMeta",
    "VariantResult",
    "StatSummary",
]
