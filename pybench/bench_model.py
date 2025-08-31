from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple


# Global registry of all Bench instances
_ALL_BENCHES: List["Bench"] = []


# Simple dataclass factory without slots for 3.7–3.9 compatibility
_dataclass = dataclass


@_dataclass
class Case:
    name: str
    func: Callable[..., Any]
    mode: str  # "func" or "context"
    group: Optional[str] = None
    n: int = 100
    repeat: int = 20
    warmup: int = 2
    args: Tuple[Any, ...] = ()
    kwargs: Dict[str, Any] = None  # type: ignore[assignment]
    params: Optional[Dict[str, Iterable[Any]]] = None
    baseline: bool = False

    def __post_init__(self) -> None:
        if self.kwargs is None:
            self.kwargs = {}


class Bench:
    def __init__(self, suite_name: Optional[str] = None, *, group: Optional[str] = None) -> None:
        self.suite_name = suite_name or "bench"
        self.default_group = (
            group
            if group is not None
            else (suite_name if suite_name and suite_name not in {"bench", "default"} else None)
        )
        self._cases: List[Case] = []
        # register this bench
        _ALL_BENCHES.append(self)

    def __call__(
        self,
        *,
        name: Optional[str] = None,
        params: Optional[Dict[str, Iterable[Any]]] = None,
        args: Optional[Sequence[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        n: int = 100,
        repeat: int = 20,
        warmup: int = 2,
        group: Optional[str] = None,
        baseline: bool = False,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
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
        name: Optional[str] = None,
        params: Optional[Dict[str, Iterable[Any]]] = None,
        args: Optional[Sequence[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        n: int = 100,
        repeat: int = 20,
        warmup: int = 2,
        group: Optional[str] = None,
        baseline: bool = False,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            from .runner import infer_mode  # lazy import to avoid cycles
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
    def cases(self) -> List[Case]:
        return list(self._cases)


DEFAULT_BENCH = Bench("default")


def bench(**kwargs):  # type: ignore[override]
    return DEFAULT_BENCH.__call__(**kwargs)


def all_cases() -> List[Case]:
    cases: List[Case] = []
    for b in list(_ALL_BENCHES):
        cases.extend(b.cases)
    # ensure uniqueness in case multiple imports or aliases occur
    seen = set()
    unique: List[Case] = []
    for c in cases:
        key = (id(c.func), c.name, c.group)
        if key in seen:
            continue
        seen.add(key)
        unique.append(c)
    return unique


__all__ = ["Bench", "Case", "DEFAULT_BENCH", "bench", "all_cases"]
