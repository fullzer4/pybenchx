from __future__ import annotations

import gc
import itertools
import math
import re
import statistics as stats
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple


PerfCounter = time.perf_counter_ns

# Global registry of Bench instances
_GLOBAL_BENCHES: List["Bench"] = []

RESET = "\x1b[0m"
YELLOW = "\x1b[33;1m"
CYAN = "\x1b[36;1m"
MAGENTA = "\x1b[35;1m"
DIM = "\x1b[2m"

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(s: str) -> str:
    return ANSI_RE.sub("", s)


def _vis_len(s: str) -> int:
    return len(_strip_ansi(s))


def _pad(cell: str, width: int, align: str) -> str:
    length = _vis_len(cell)
    if length >= width:
        return cell
    pad = " " * (width - length)
    if align == "<":
        return cell + pad
    return pad + cell


def _parse_value(v: str) -> Any:
    s = v.strip()
    if s.lower() in {"true", "false"}:
        return s.lower() == "true"
    if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
        try:
            return int(s)
        except ValueError:
            pass
    try:
        f = float(s)
        return f
    except ValueError:
        pass
    if (s.startswith("'") and s.endswith("'")) or (
        s.startswith('"') and s.endswith('"')
    ):
        return s[1:-1]
    return s


def _fmt_time_ns(ns: float) -> str:
    # Human-friendly time with 2 decimals
    if ns < 1_000:
        return f"{ns:.2f} ns"
    us = ns / 1_000
    if us < 1_000:
        return f"{us:.2f} µs"
    ms = us / 1_000
    if ms < 1_000:
        return f"{ms:.2f} ms"
    s = ms / 1_000
    return f"{s:.2f} s"


def _percentile(values: List[float], q: float) -> float:
    # Inclusive linear interpolation between closest ranks
    if not values:
        return float("nan")
    xs = sorted(values)
    n = len(xs)
    if n == 1:
        return xs[0]
    pos = (q / 100.0) * (n - 1)
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return xs[lo] * (1 - frac) + xs[hi] * frac


@dataclass
class BenchContext:
    """Explicit timing control for a single benchmark iteration.

    Use start()/end() around the critical section.
    """

    _running: bool = field(default=False, init=False)
    _t0: int = field(default=0, init=False)
    _accum: int = field(default=0, init=False)

    def start(self, _pc=PerfCounter) -> None:
        if self._running:
            # Nested starts are ignored to avoid double count
            return
        self._running = True
        self._t0 = _pc()

    def end(self, _pc=PerfCounter) -> None:
        if not self._running:
            return
        self._accum += _pc() - self._t0
        self._running = False

    # Internal API used by runner
    def _reset(self) -> None:
        self._running = False
        self._t0 = 0
        self._accum = 0

    def _elapsed_ns(self) -> int:
        return self._accum


@dataclass
class Case:
    name: str
    func: Callable[..., Any]
    mode: str  # "func" or "context"
    group: Optional[str] = None
    n: int = 100
    repeat: int = 20
    warmup: int = 2
    args: Tuple[Any, ...] = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    params: Optional[Dict[str, Iterable[Any]]] = None
    baseline: bool = False


class Bench:
    def __init__(self, suite_name: str | None = None, *, group: Optional[str] = None) -> None:
        self.suite_name = suite_name or "bench"
        # If an explicit group is provided, use it; otherwise use suite_name as the default group
        # except when it's a generic name ("bench" or "default").
        self.default_group: Optional[str] = (
            group
            if group is not None
            else (
                suite_name
                if suite_name and suite_name not in {"bench", "default"}
                else None
            )
        )
        self._cases: List[Case] = []
        _GLOBAL_BENCHES.append(self)

    # Make Bench callable so it can be used as @bench(...)
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
        """Decorator to register a benchmarked function.

        If the function takes a BenchContext as the first argument (by annotation
        type name or parameter name 'b'/'_b'), it is treated as a 'context' mode
        benchmark; otherwise the whole function call is measured ('func' mode).
        """

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            mode = _infer_mode(fn)
            case = Case(
                name=name or fn.__name__,
                func=fn,
                mode=mode,
                group=group or self.default_group,
                n=n,
                repeat=repeat,
                warmup=warmup,
                args=tuple(args or ()),
                kwargs=dict(kwargs or {}),
                params=dict(params) if params else None,
                baseline=baseline,
            )
            self._cases.append(case)
            return fn

        return decorator

    @property
    def cases(self) -> List[Case]:
        return list(self._cases)


def all_benches() -> List[Bench]:
    return list(_GLOBAL_BENCHES)


def all_cases() -> List[Case]:
    seen = set()
    out: List[Case] = []
    for b in _GLOBAL_BENCHES:
        for c in b.cases:
            if id(c) not in seen:
                seen.add(id(c))
                out.append(c)
    return out


def _infer_mode(fn: Callable[..., Any]) -> str:
    try:
        import inspect

        sig = inspect.signature(fn)
        params = list(sig.parameters.values())
        if not params:
            return "func"
        first = params[0]
        ann = str(first.annotation)
        if "BenchContext" in ann:
            return "context"
        if first.name in {"b", "_b", "ctx", "context"}:
            return "context"
    except Exception:
        pass
    return "func"


DEFAULT_BENCH = Bench("default")


def bench(**kwargs):  # type: ignore[override]
    return DEFAULT_BENCH.__call__(**kwargs)


@dataclass
class Result:
    name: str
    group: str
    n: int
    repeat: int
    per_call_ns: List[float]
    baseline: bool = False

    @property
    def median(self) -> float:
        return stats.median(self.per_call_ns)

    @property
    def mean(self) -> float:
        return stats.fmean(self.per_call_ns)

    @property
    def stdev(self) -> float:
        return stats.pstdev(self.per_call_ns)

    @property
    def min(self) -> float:
        return min(self.per_call_ns) if self.per_call_ns else float("nan")

    @property
    def max(self) -> float:
        return max(self.per_call_ns) if self.per_call_ns else float("nan")

    def p(self, q: float) -> float:
        return _percentile(self.per_call_ns, q)


def _make_variants(case: Case) -> List[Tuple[str, Tuple[Any, ...], Dict[str, Any]]]:
    """Produce (name, args, kwargs) for each variant of a case.

    - Params override kwargs when keys overlap.
    - If no params, return a single variant with case.args/kwargs.
    """
    base_args = case.args
    base_kwargs = dict(case.kwargs)
    if not case.params:
        return [(case.name, base_args, base_kwargs)]

    keys = sorted(case.params.keys())
    value_lists = [list(case.params[k]) for k in keys]
    variants = []
    for values in itertools.product(*value_lists):
        kw = dict(base_kwargs)
        for k, v in zip(keys, values):
            kw[k] = v
        label_parts = [f"{k}={_fmt_value(v)}" for k, v in zip(keys, values)]
        vname = f"{case.name}[{','.join(label_parts)}]"
        variants.append((vname, base_args, kw))
    return variants


def _fmt_value(v: Any) -> str:
    if isinstance(v, str):
        return repr(v)
    return str(v)


def apply_overrides(case: Case, overrides: Dict[str, Any]) -> Case:
    if not overrides:
        return case
    c = Case(
        name=case.name,
        func=case.func,
        mode=case.mode,
        group=case.group,
        n=case.n,
        repeat=case.repeat,
        warmup=case.warmup,
        args=tuple(case.args),
        kwargs=dict(case.kwargs),
        params=dict(case.params) if case.params else None,
        baseline=case.baseline,
    )
    for k, v in overrides.items():
        if k in {"n", "repeat", "warmup"}:
            setattr(c, k, int(v))
        elif k == "group":
            c.group = str(v)
        elif k == "baseline":
            c.baseline = (
                bool(v)
                if isinstance(v, bool)
                else str(v).lower() in {"1", "true", "yes", "on"}
            )
        else:
            # If it's in params grid, override; else treat as kwarg override
            if c.params and k in c.params:
                c.params[k] = [v]
            else:
                c.kwargs[k] = v
    return c


def _detect_used_ctx(
    func: Callable[..., Any], vargs: Tuple[Any, ...], vkwargs: Dict[str, Any]
) -> bool:
    ctx = BenchContext()
    func(ctx, *vargs, **vkwargs)
    return ctx._elapsed_ns() > 0


def _calibrate_n(
    func: Callable[..., Any],
    mode: str,
    vargs: Tuple[Any, ...],
    vkwargs: Dict[str, Any],
    *,
    target_ns: int = 200_000_000,
    max_n: int = 1_000_000,
) -> tuple[int, bool]:
    """Calibrate iteration count n so that one repeat runs for ~target_ns.

    Returns (n, used_ctx) where used_ctx indicates whether BenchContext timing was used.
    """
    pc = PerfCounter

    if mode == "context":
        used_ctx = _detect_used_ctx(func, vargs, vkwargs)

        def run(k: int) -> int:
            if used_ctx:
                total = 0
                ctx = BenchContext()
                for _ in range(k):
                    ctx._reset()
                    func(ctx, *vargs, **vkwargs)
                    total += ctx._elapsed_ns()
                return total
            else:
                t0 = pc()
                ctx = BenchContext()
                for _ in range(k):
                    func(ctx, *vargs, **vkwargs)
                return pc() - t0

    else:
        used_ctx = False

        def run(k: int) -> int:
            t0 = pc()
            for _ in range(k):
                func(*vargs, **vkwargs)
            return pc() - t0

    # Use 1-2-5 decades to scale n without overshooting badly
    n = 1
    while True:
        for m in (1, 2, 5):
            candidate = n * m
            dt = run(candidate)
            if dt >= target_ns or candidate >= max_n:
                return candidate, used_ctx
        n *= 10


def run_case(case: Case) -> List[Result]:
    # Prepare GC and timing environment
    gc_was_enabled = gc.isenabled()
    try:
        # Warmup phase (not measured)
        for _ in range(max(0, case.warmup)):
            _run_case_once(case)

        # Measurement repeats
        variants = _make_variants(case)
        results: List[Result] = []
        for vname, vargs, vkwargs in variants:
            per_call_ns: List[float] = []

            # Calibrate n and preflight context usage once per variant
            try:
                calib_n, used_ctx = _calibrate_n(case.func, case.mode, vargs, vkwargs)
            except Exception:
                calib_n = case.n
                used_ctx = (
                    _detect_used_ctx(case.func, vargs, vkwargs)
                    if case.mode == "context"
                    else False
                )
            local_n = max(case.n, calib_n)  # only increase n, never decrease

            # Ensure clean GC state per variant
            gc.collect()
            if gc_was_enabled:
                gc.disable()
            try:
                for _ in range(case.repeat):
                    per_call_ns.append(
                        _run_single_repeat(
                            case, vname, vargs, vkwargs, used_ctx, local_n
                        )
                    )
            finally:
                if gc_was_enabled:
                    gc.enable()
            results.append(
                Result(
                    name=vname,
                    group=(case.group or "-") if case.group is not None else "-",
                    n=case.n,
                    repeat=case.repeat,
                    per_call_ns=per_call_ns,
                    baseline=case.baseline,
                )
            )
        return results
    finally:
        if gc_was_enabled and not gc.isenabled():
            gc.enable()


def _run_case_once(case: Case) -> None:
    variants = _make_variants(case)
    for _vname, vargs, vkwargs in variants:
        if case.mode == "context":
            # Create context and call the function n times (no timing)
            ctx = BenchContext()
            func = case.func
            n = case.n
            for _ in range(n):
                ctx._reset()
                func(ctx, *vargs, **vkwargs)
        else:
            # func mode: just call the function n times (no timing)
            func = case.func
            n = case.n
            for _ in range(n):
                func(*vargs, **vkwargs)


def _run_single_repeat(
    case: Case,
    vname: str,
    vargs: Tuple[Any, ...],
    vkwargs: Dict[str, Any],
    used_ctx: bool = False,
    local_n: Optional[int] = None,
) -> float:
    func = case.func
    n = local_n or case.n
    pc = PerfCounter
    if case.mode == "context":
        if used_ctx:
            total = 0
            ctx = BenchContext()
            for _ in range(n):
                ctx._reset()
                func(ctx, *vargs, **vkwargs)
                total += ctx._elapsed_ns()
            return total / n
        # fallback: measure the entire loop once and reuse a single ctx
        t0 = pc()
        ctx = BenchContext()
        for _ in range(n):
            func(ctx, *vargs, **vkwargs)
        return (pc() - t0) / n
    else:
        t0 = pc()
        for _ in range(n):
            func(*vargs, **vkwargs)
        return (pc() - t0) / n


def _speedups_by_group(results: List[Result]) -> Dict[int, float]:
    # Returns mapping id(result)->speedup vs baseline; baseline is NaN; groups without explicit baseline are skipped
    by_group: Dict[str, List[Result]] = {}
    for r in results:
        if r.group == "-":
            continue
        by_group.setdefault(r.group, []).append(r)

    speedups: Dict[int, float] = {}
    for group, items in by_group.items():
        # Prefer explicit baseline flag
        base_r: Optional[Result] = next((r for r in items if r.baseline), None)
        # Fallback to name matching
        if base_r is None:
            for r in items:
                nl = r.name.lower()
                if "baseline" in nl or nl.startswith("base") or nl.endswith("base"):
                    base_r = r
                    break
        if base_r is None:
            continue
        base_mean = base_r.mean
        speedups[id(base_r)] = float("nan")  # mark baseline
        for r in items:
            if r is base_r:
                continue
            speed = (base_mean / r.mean) if r.mean and base_mean else float("nan")
            speedups[id(r)] = speed
    return speedups


def format_table(
    results: List[Result],
    *,
    use_color: bool = True,
    sort: Optional[str] = None,  # 'time' | 'group'
    desc: bool = False,
) -> str:
    speedups = _speedups_by_group(results)

    headers = [
        ("benchmark", 28, "<"),
        ("time (avg)", 16, ">"),
        ("iter/s", 12, ">"),
        ("(min … max)", 24, ">"),
        ("p75", 12, ">"),
        ("p99", 12, ">"),
        ("p995", 12, ">"),
        ("vs base", 12, ">"),
    ]

    def colorize(text: str, code: str) -> str:
        return text if not use_color else f"{code}{text}{RESET}"

    def fmt_head() -> str:
        parts = []
        for h, w, align in headers:
            parts.append(_pad(h, w, align))
        return " ".join(parts)

    def fmt_iters_per_sec(mean_ns: float) -> str:
        if mean_ns <= 0:
            return "-"
        ips = 1e9 / mean_ns
        if ips >= 1_000_000:
            return f"{ips / 1_000_000:.1f} M"
        if ips >= 1_000:
            return f"{ips / 1_000:.1f} K"
        return f"{ips:.1f}"

    grouped: Dict[str, List[Result]] = {}
    for r in results:
        grouped.setdefault(r.group, []).append(r)

    if sort == "group":
        group_keys = sorted(grouped.keys(), reverse=desc)
    else:
        # preserve input order of first occurrence
        seen: List[str] = []
        for r in results:
            if r.group not in seen:
                seen.append(r.group)
        group_keys = seen

    def sort_items(items: List[Result]) -> List[Result]:
        if sort in {"group", "time"}:
            return sorted(items, key=lambda r: r.mean, reverse=desc)
        return items

    lines = [fmt_head()]
    total_width = sum(w for _, w, _ in headers)
    for g in group_keys:
        items = sort_items(grouped[g])
        if g != "-":
            lines.append(colorize(_pad(f"group: {g}", total_width, "<"), DIM))
        for r in items:
            avg = _fmt_time_ns(r.mean)
            lo = _fmt_time_ns(r.min)
            hi = _fmt_time_ns(r.max)
            p75 = _fmt_time_ns(r.p(75))
            p99 = _fmt_time_ns(r.p(99))
            p995 = _fmt_time_ns(r.p(99.5))
            vs = "-"
            sid = id(r)
            if sid in speedups:
                s = speedups[sid]
                if math.isnan(s):
                    vs = "baseline"
                elif s > 0:
                    # Treat near-equal within 1% as same
                    if abs(s - 1.0) < 0.01:
                        vs = "≈ same"
                    else:
                        pct = abs(s - 1.0) * 100.0
                        if s > 1.0:
                            vs = f"{s:.2f}× faster ({pct:.1f}%)"
                        else:
                            vs = f"{(1/s):.2f}× slower ({pct:.1f}%)"
            name = r.name + ("  ★" if r.baseline else "")
            cells = [
                name,
                colorize(f"{avg}", YELLOW),
                fmt_iters_per_sec(r.mean),
                f"{colorize(lo, CYAN)} … {colorize(hi, MAGENTA)}",
                colorize(p75, MAGENTA),
                colorize(p99, MAGENTA),
                colorize(p995, MAGENTA),
                vs,
            ]
            fmt_cells: List[str] = []
            for (h, w, align), cell in zip(headers, cells):
                fmt_cells.append(_pad(cell, w, align))
            lines.append(" ".join(fmt_cells))
    return "\n".join(lines)


def filter_results(results: List[Result], keyword: Optional[str]) -> List[Result]:
    if not keyword:
        return results
    k = keyword.lower()
    return [r for r in results if k in r.name.lower()]


def parse_overrides(pairs: List[str]) -> Dict[str, Any]:
    overrides: Dict[str, Any] = {}
    for p in pairs:
        if "=" not in p:
            continue
        k, v = p.split("=", 1)
        overrides[k.strip()] = _parse_value(v)
    return overrides
