from __future__ import annotations

import gc
import hashlib
import itertools
import math
import os
import re
import statistics as _stats
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple


# Monotonic clock with fallback for very old Pythons
if hasattr(time, "perf_counter_ns"):
    def _pc_ns() -> int:
        return time.perf_counter_ns()
else:  # pragma: no cover
    def _pc_ns() -> int:
        return int(time.perf_counter() * 1e9)


# Dataclass wrapper that adds slots when available (Python 3.10+)
try:
    from dataclasses import dataclass as _dataclass
    import inspect as _inspect

    _HAS_SLOTS = "slots" in _inspect.signature(_dataclass).parameters

    def _dc(*args, **kwargs):
        if _HAS_SLOTS:
            kwargs.setdefault("slots", True)
        else:
            kwargs.pop("slots", None)
        return _dataclass(*args, **kwargs)
except Exception:  # pragma: no cover
    raise


# fmean fallback for Python 3.7
try:
    _fmean = _stats.fmean  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    def _fmean(xs: List[float]) -> float:
        n = len(xs)
        return sum(xs) / n if n else float("nan")


_GLOBAL_BENCHES: List["Bench"] = []

RESET = "\x1b[0m"
YELLOW = "\x1b[33;1m"
CYAN = "\x1b[36;1m"
MAGENTA = "\x1b[35;1m"
DIM = "\x1b[2m"
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi_codes(s: str) -> str:
    return _ANSI_RE.sub("", s)


def _visible_len(s: str) -> int:
    return len(_strip_ansi_codes(s))


def _pad_cell(cell: str, width: int, align: str) -> str:
    length = _visible_len(cell)
    if length >= width:
        return cell
    pad = " " * (width - length)
    return (pad + cell) if align != "<" else (cell + pad)


def _parse_value(v: str) -> Any:
    s = v.strip()
    if s.lower() in {"true", "false"}:
        return s.lower() == "true"
    if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
        try:
            return int(s)
        except Exception:
            pass
    try:
        return float(s)
    except Exception:
        pass
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        return s[1:-1]
    return s


def _fmt_time_ns(ns: float) -> str:
    if ns < 1_000:
        return "{:.2f} ns".format(ns)
    us = ns / 1_000.0
    if us < 1_000:
        return "{:.2f} µs".format(us)
    ms = us / 1_000.0
    if ms < 1_000:
        return "{:.2f} ms".format(ms)
    s = ms / 1_000.0
    return "{:.2f} s".format(s)


def _module_name_for_path(path: str) -> str:
    """Stable unique module name for importing standalone files."""
    p = os.path.abspath(path)
    h = hashlib.sha1(p.encode("utf-8")).hexdigest()[:12]
    stem = os.path.splitext(os.path.basename(p))[0]
    return "pybenchx_{}_{}".format(stem, h)


@_dc(slots=True)
class BenchContext:
    """Per-iteration manual timing helper (call start()/end() around the hot region)."""
    _running: bool = False
    _t0: int = 0
    _accum: int = 0

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._t0 = _pc_ns()

    def end(self) -> None:
        if not self._running:
            return
        self._accum += _pc_ns() - self._t0
        self._running = False

    def _reset(self) -> None:
        self._running = False
        self._t0 = 0
        self._accum = 0

    def _elapsed_ns(self) -> int:
        return self._accum


@_dc(slots=True)
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
    """Suite/registry of benchmarked callables (also usable as a decorator factory)."""
    def __init__(self, suite_name: Optional[str] = None, *, group: Optional[str] = None) -> None:
        self.suite_name = suite_name or "bench"
        self.default_group = (
            group
            if group is not None
            else (suite_name if suite_name and suite_name not in {"bench", "default"} else None)
        )  # type: Optional[str]
        self._cases: List[Case] = []
        _GLOBAL_BENCHES.append(self)

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


def all_benches() -> List[Bench]:
    return list(_GLOBAL_BENCHES)


def all_cases() -> List[Case]:
    seen: Dict[int, bool] = {}
    out: List[Case] = []
    for b in _GLOBAL_BENCHES:
        for c in b.cases:
            if id(c) not in seen:
                seen[id(c)] = True
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
        if "BenchContext" in ann or first.name in {"b", "_b", "ctx", "context"}:
            return "context"
    except Exception:
        pass
    return "func"


DEFAULT_BENCH = Bench("default")


def bench(**kwargs):  # type: ignore[override]
    return DEFAULT_BENCH.__call__(**kwargs)


@_dc(slots=True)
class Result:
    name: str
    group: str
    n: int
    repeat: int
    per_call_ns: List[float]
    baseline: bool = False
    _sorted_per_call_ns: Optional[List[float]] = None

    def _get_sorted(self) -> List[float]:
        if self._sorted_per_call_ns is None:
            self._sorted_per_call_ns = sorted(self.per_call_ns)
        return self._sorted_per_call_ns

    @property
    def median(self) -> float:
        return _stats.median(self.per_call_ns)

    @property
    def mean(self) -> float:
        return _fmean(self.per_call_ns)

    @property
    def stdev(self) -> float:
        return _stats.pstdev(self.per_call_ns)

    @property
    def min(self) -> float:
        if not self.per_call_ns:
            return float("nan")
        return self._get_sorted()[0]

    @property
    def max(self) -> float:
        if not self.per_call_ns:
            return float("nan")
        return self._get_sorted()[-1]

    def p(self, q: float) -> float:
        s = self._get_sorted()
        if not s:
            return float("nan")
        n = len(s)
        if n == 1:
            return s[0]
        pos = (q / 100.0) * (n - 1)
        lo = int(pos)
        hi = min(lo + 1, n - 1)
        frac = pos - lo
        return s[lo] * (1.0 - frac) + s[hi] * frac


def _make_variants(case: Case) -> List[Tuple[str, Tuple[Any, ...], Dict[str, Any]]]:
    base_args = case.args
    base_kwargs = dict(case.kwargs)
    if not case.params:
        return [(case.name, base_args, base_kwargs)]

    keys = sorted(case.params.keys())
    value_lists = [list(case.params[k]) for k in keys]
    variants: List[Tuple[str, Tuple[Any, ...], Dict[str, Any]]] = []
    for values in itertools.product(*value_lists):
        kw = dict(base_kwargs)
        for k, v in zip(keys, values):
            kw[k] = v
        label = ",".join("{}={}".format(k, _fmt_value(v)) for k, v in zip(keys, values))
        vname = "{}[{}]".format(case.name, label)
        variants.append((vname, base_args, kw))
    return variants


def _fmt_value(v: Any) -> str:
    return repr(v) if isinstance(v, str) else str(v)


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
            if isinstance(v, bool):
                c.baseline = v
            else:
                c.baseline = str(v).lower() in {"1", "true", "yes", "on"}
        else:
            if c.params and k in c.params:
                c.params[k] = [v]
            else:
                c.kwargs[k] = v
    return c


def _detect_used_ctx(func: Callable[..., Any], vargs: Tuple[Any, ...], vkwargs: Dict[str, Any]) -> bool:
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
) -> Tuple[int, bool]:
    """Pick n so one repeat runs for ~target_ns (exponential growth + light refinement)."""
    if mode == "context":
        used_ctx = _detect_used_ctx(func, vargs, vkwargs)
        ctx = BenchContext()
        bound_ctx = (lambda: func(ctx, *vargs, **vkwargs))
        if used_ctx:
            def run(k: int) -> int:
                total = 0
                for _ in range(k):
                    ctx._reset()
                    bound_ctx()
                    total += ctx._elapsed_ns()
                return total
        else:
            def run(k: int) -> int:
                t0 = _pc_ns()
                for _ in range(k):
                    bound_ctx()
                return _pc_ns() - t0
    else:
        used_ctx = False
        bound = (lambda: func(*vargs, **vkwargs))
        def run(k: int) -> int:
            t0 = _pc_ns()
            for _ in range(k):
                bound()
            return _pc_ns() - t0

    n = 1
    dt = run(n) or 1
    while dt < target_ns and n < max_n:
        n = min(n * 2, max_n)
        dt = run(n) or 1

    if n >= max_n:
        return max_n, used_ctx

    est = max(1, min(max_n, int(round(n * (float(target_ns) / float(dt))))))
    candidates = {est, max(1, int(round(est * 0.8))), min(max_n, int(round(est * 1.2)))}

    best_n, best_err = est, float("inf")
    for c in sorted(candidates):
        d = run(c)
        err = abs(float(d) - float(target_ns))
        if err < best_err:
            best_n, best_err = c, err

    return best_n, used_ctx


def _run_case_once(case: Case) -> None:
    variants = _make_variants(case)
    n = case.n
    rn = range
    for _vname, vargs, vkwargs in variants:
        if case.mode == "context":
            ctx = BenchContext()
            bound = (lambda: case.func(ctx, *vargs, **vkwargs))
            for _ in rn(n):
                ctx._reset()
                bound()
        else:
            bound = (lambda: case.func(*vargs, **vkwargs))
            for _ in rn(n):
                bound()


def _run_single_repeat(
    case: Case,
    vname: str,
    vargs: Tuple[Any, ...],
    vkwargs: Dict[str, Any],
    used_ctx: bool = False,
    local_n: Optional[int] = None,
) -> float:
    n = local_n or case.n
    rn = range

    if case.mode == "context":
        ctx = BenchContext()
        bound_ctx = (lambda: case.func(ctx, *vargs, **vkwargs))
        if used_ctx:
            total = 0
            for _ in rn(n):
                ctx._reset()
                bound_ctx()
                total += ctx._elapsed_ns()
            return float(total) / float(n)
        else:
            t0 = _pc_ns()
            for _ in rn(n):
                bound_ctx()
            return float(_pc_ns() - t0) / float(n)
    else:
        bound = (lambda: case.func(*vargs, **vkwargs))
        t0 = _pc_ns()
        for _ in rn(n):
            bound()
        return float(_pc_ns() - t0) / float(n)


def run_case(case: Case) -> List[Result]:
    gc_was_enabled = gc.isenabled()
    try:
        gc.collect()
        if gc_was_enabled:
            gc.disable()

        for _ in range(max(0, case.warmup)):
            _run_case_once(case)

        results: List[Result] = []
        for vname, vargs, vkwargs in _make_variants(case):
            per_call_ns: List[float] = []
            try:
                calib_n, used_ctx = _calibrate_n(case.func, case.mode, vargs, vkwargs)
            except Exception:
                calib_n = case.n
                used_ctx = _detect_used_ctx(case.func, vargs, vkwargs) if case.mode == "context" else False

            local_n = max(case.n, calib_n)
            for _ in range(case.repeat):
                per_call_ns.append(_run_single_repeat(case, vname, vargs, vkwargs, used_ctx, local_n))

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


def _compute_speedups(results: List[Result]) -> Dict[int, float]:
    """id(Result) -> speedup vs baseline (nan for baseline, 1.0 ≈ same)."""
    by_group: Dict[str, List[Result]] = {}
    for r in results:
        if r.group == "-":
            continue
        by_group.setdefault(r.group, []).append(r)

    speedups: Dict[int, float] = {}
    for _, items in by_group.items():
        base_r: Optional[Result] = next((r for r in items if r.baseline), None)
        if base_r is None:
            for r in items:
                nl = r.name.lower()
                if "baseline" in nl or nl.startswith("base") or nl.endswith("base"):
                    base_r = r
                    break
        if base_r is None:
            continue
        base_mean = base_r.mean
        speedups[id(base_r)] = float("nan")
        for r in items:
            if r is base_r:
                continue
            if base_mean > 0 and r.mean > 0:
                pct_diff = abs((r.mean - base_mean) / base_mean)
                if pct_diff <= 0.01:
                    speedups[id(r)] = 1.0
                    continue
            speedups[id(r)] = (base_mean / r.mean) if (r.mean and base_mean) else float("nan")
    return speedups


def format_table(
    results: List[Result],
    *,
    use_color: bool = True,
    sort: Optional[str] = None,  # 'time' | 'group'
    desc: bool = False,
    brief: bool = False,
) -> str:
    speedups = _compute_speedups(results)

    headers = (
        [("benchmark", 28, "<"), ("time (avg)", 16, ">"), ("vs base", 12, ">")]
        if brief
        else [
            ("benchmark", 28, "<"),
            ("time (avg)", 16, ">"),
            ("iter/s", 12, ">"),
            ("(min … max)", 24, ">"),
            ("p75", 12, ">"),
            ("p99", 12, ">"),
            ("p995", 12, ">"),
            ("vs base", 12, ">"),
        ]
    )

    def colorize(text: str, code: str) -> str:
        return text if not use_color else "{}{}{}".format(code, text, RESET)

    def fmt_head() -> str:
        return " ".join(_pad_cell(h, w, a) for h, w, a in headers)

    def fmt_ips(mean_ns: float) -> str:
        if mean_ns <= 0:
            return "-"
        ips = 1e9 / mean_ns
        if ips >= 1_000_000:
            return "{:.1f} M".format(ips / 1_000_000.0)
        if ips >= 1_000:
            return "{:.1f} K".format(ips / 1_000.0)
        return "{:.1f}".format(ips)

    grouped: Dict[str, List[Result]] = {}
    for r in results:
        grouped.setdefault(r.group, []).append(r)

    if sort == "group":
        group_keys = sorted(grouped.keys(), reverse=desc)
    else:
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
            lines.append(colorize(_pad_cell("group: {}".format(g), total_width, "<"), DIM))
        for r in items:
            avg = _fmt_time_ns(r.mean)
            sid = id(r)
            vs = "-"
            if sid in speedups:
                s = speedups[sid]
                if math.isnan(s):
                    vs = "baseline"
                elif s == 1.0:
                    vs = "≈ same"
                elif s > 0:
                    vs = "{:.2f}× faster".format(s) if s > 1.0 else "{:.2f}× slower".format(1.0 / s)

            name = r.name + ("  ★" if r.baseline else "")
            if brief:
                cells = [name, colorize(avg, YELLOW), vs]
            else:
                lo = _fmt_time_ns(r.min)
                hi = _fmt_time_ns(r.max)
                p75 = _fmt_time_ns(r.p(75))
                p99 = _fmt_time_ns(r.p(99))
                p995 = _fmt_time_ns(r.p(99.5))
                cells = [
                    name,
                    colorize(avg, YELLOW),
                    fmt_ips(r.mean),
                    "{} … {}".format(colorize(lo, CYAN), colorize(hi, MAGENTA)),
                    colorize(p75, MAGENTA),
                    colorize(p99, MAGENTA),
                    colorize(p995, MAGENTA),
                    vs,
                ]
            lines.append(" ".join(_pad_cell(c, w, a) for (h, w, a), c in zip(headers, cells)))
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


__all__ = [
    "BenchContext",
    "Case",
    "Result",
    "Bench",
    "DEFAULT_BENCH",
    "bench",
    "_module_name_for_path",
    "_make_variants",
    "_calibrate_n",
    "_detect_used_ctx",
    "_run_single_repeat",
    "all_benches",
    "all_cases",
    "apply_overrides",
    "filter_results",
    "format_table",
    "parse_overrides",
]
