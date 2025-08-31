from __future__ import annotations

import gc
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from . import timing as _timing
from .bench_model import Case
from .params import make_variants as _make_variants


def infer_mode(fn: Callable[..., Any]) -> str:
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


def detect_used_ctx(func: Callable[..., Any], vargs: Tuple[Any, ...], vkwargs: Dict[str, Any]) -> bool:
    ctx = _timing.BenchContext()
    func(ctx, *vargs, **vkwargs)
    return ctx._elapsed_ns() > 0


def calibrate_n(
    func: Callable[..., Any],
    mode: str,
    vargs: Tuple[Any, ...],
    vkwargs: Dict[str, Any],
    *,
    target_ns: int = 200_000_000,
    max_n: int = 1_000_000,
) -> Tuple[int, bool]:
    if mode == "context":
        used_ctx = detect_used_ctx(func, vargs, vkwargs)
        ctx = _timing.BenchContext()
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
                t0 = _timing._pc_ns()
                for _ in range(k):
                    bound_ctx()
                return _timing._pc_ns() - t0
    else:
        used_ctx = False
        bound = (lambda: func(*vargs, **vkwargs))
        def run(k: int) -> int:
            t0 = _timing._pc_ns()
            for _ in range(k):
                bound()
            return _timing._pc_ns() - t0

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
            ctx = _timing.BenchContext()
            bound = (lambda: case.func(ctx, *vargs, **vkwargs))
            for _ in rn(n):
                ctx._reset()
                bound()
        else:
            bound = (lambda: case.func(*vargs, **vkwargs))
            for _ in rn(n):
                bound()


def run_single_repeat(
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
        ctx = _timing.BenchContext()
        bound_ctx = (lambda: case.func(ctx, *vargs, **vkwargs))
        if used_ctx:
            total = 0
            for _ in rn(n):
                ctx._reset()
                bound_ctx()
                total += ctx._elapsed_ns()
            return float(total) / float(n)
        else:
            t0 = _timing._pc_ns()
            for _ in rn(n):
                bound_ctx()
            return float(_timing._pc_ns() - t0) / float(n)
    else:
        bound = (lambda: case.func(*vargs, **vkwargs))
        t0 = _timing._pc_ns()
        for _ in rn(n):
            bound()
        return float(_timing._pc_ns() - t0) / float(n)


def run_case(case: Case) -> List[float]:
    gc_was_enabled = gc.isenabled()
    try:
        gc.collect()
        if gc_was_enabled:
            gc.disable()

        for _ in range(max(0, case.warmup)):
            _run_case_once(case)

        per_variant_means: List[float] = []
        for vname, vargs, vkwargs in _make_variants(case):
            try:
                calib_n, used_ctx = calibrate_n(case.func, case.mode, vargs, vkwargs)
            except Exception:
                calib_n = case.n
                used_ctx = detect_used_ctx(case.func, vargs, vkwargs) if case.mode == "context" else False
            local_n = max(case.n, calib_n)
            per_variant_means.append(run_single_repeat(case, vname, vargs, vkwargs, used_ctx, local_n))
        return per_variant_means
    finally:
        if gc_was_enabled and not gc.isenabled():
            gc.enable()


__all__ = [
    "infer_mode",
    "detect_used_ctx",
    "calibrate_n",
    "run_single_repeat",
    "run_case",
]
