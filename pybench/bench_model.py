"""Core data structures representing benchmark suites and cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Sequence

_ALL_BENCHES: list[Bench] = []


# Simple dataclass factory without slots for 3.7–3.9 compatibility
_dataclass = dataclass


@_dataclass
class Case:
    """A concrete benchmark variant definition."""

    name: str
    func: Callable[..., Any]
    mode: str  # "func" or "context"
    group: str | None = None
    n: int = 100
    repeat: int = 20
    warmup: int = 2
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = None
    params: dict[str, Iterable[Any]] | None = None
    baseline: bool = False

    def __post_init__(self) -> None:
        """Set default mutable attributes after dataclass init."""
        if self.kwargs is None:
            self.kwargs = {}


class Bench:
    """Registry that collects decorated benchmark functions into cases."""

    def __init__(
        self,
        suite_name: str | None = None,
        *,
        group: str | None = None,
    ) -> None:
        """Create a new bench registry optionally scoped to ``suite_name``."""
        self.suite_name = suite_name or "bench"
        self.default_group = (
            group
            if group is not None
            else (
                suite_name
                if suite_name and suite_name not in {"bench", "default"}
                else None
            )
        )
        self._cases: list[Case] = []
        _ALL_BENCHES.append(self)

    def __call__(
        self,
        *,
        name: str | None = None,
        params: dict[str, Iterable[Any]] | None = None,
        args: Sequence[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        n: int = 100,
        repeat: int = 20,
        warmup: int = 2,
        group: str | None = None,
        baseline: bool = False,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator entrypoint mirroring :meth:`bench` for convenience."""
        return self.bench(
            name=name,
            params=params,
            args=args,
            kwargs=kwargs,
            n=n,
            repeat=repeat,
            warmup=warmup,
            group=group,
            baseline=baseline,
        )

    def bench(
        self,
        *,
        name: str | None = None,
        params: dict[str, Iterable[Any]] | None = None,
        args: Sequence[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        n: int = 100,
        repeat: int = 20,
        warmup: int = 2,
        group: str | None = None,
        baseline: bool = False,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register ``fn`` as a case using optional parameter overrides."""
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            from .runner import infer_mode
            mode = infer_mode(fn)
            case = Case(
                name=name or fn.__name__,
                func=fn,
                mode=mode,
                group=group or self.default_group,
                n=n,
                repeat=repeat,
                warmup=warmup,
                args=tuple(args or ()),
                kwargs=dict(kwargs or {}) if kwargs else {},
                params=dict(params) if params else None,
                baseline=baseline,
            )
            self._cases.append(case)
            return fn
        return decorator

    @property
    def cases(self) -> list[Case]:
        """Return a copy of the registered cases for this bench."""
        return list(self._cases)


DEFAULT_BENCH = Bench("default")


def bench(**kwargs):
    """Convenience decorator using the global ``DEFAULT_BENCH`` instance."""
    return DEFAULT_BENCH.__call__(**kwargs)


def all_cases() -> list[Case]:
    """Return all registered cases across all benches."""
    cases: list[Case] = []
    for b in list(_ALL_BENCHES):
        cases.extend(b.cases)
    # ensure uniqueness in case multiple imports or aliases occur
    seen = set()
    unique: list[Case] = []
    for c in cases:
        key = (id(c.func), c.name, c.group)
        if key in seen:
            continue
        seen.add(key)
        unique.append(c)
    return unique


__all__ = ["Bench", "Case", "DEFAULT_BENCH", "bench", "all_cases"]
