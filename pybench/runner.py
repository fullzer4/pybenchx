"""Low-level execution engine powering benchmark calibration and runs."""

from __future__ import annotations

import gc
import statistics as _stats
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from . import timing as _timing
from .bench_model import Case
from .params import make_variants as _make_variants
from .run_model import StatSummary, VariantResult


def infer_mode(fn: Callable[..., Any]) -> str:
    """Infer whether ``fn`` expects a :class:`BenchContext` argument."""
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


def detect_used_ctx(
    func: Callable[..., Any],
    vargs: tuple[Any, ...],
    vkwargs: dict[str, Any],
) -> bool:
    """Return True when a context-mode function recorded measurements."""
    ctx = _timing.BenchContext()
    func(ctx, *vargs, **vkwargs)
    return ctx._elapsed_ns() > 0


def calibrate_n(
    func: Callable[..., Any],
    mode: str,
    vargs: tuple[Any, ...],
    vkwargs: dict[str, Any],
    *,
    target_ns: int = 200_000_000,
    max_n: int = 1_000_000,
) -> tuple[int, bool]:
    """Calibrate iterations to approximate ``target_ns`` total runtime."""
    if mode == "context":
        used_ctx = detect_used_ctx(func, vargs, vkwargs)
        ctx = _timing.BenchContext()

        def run(k: int) -> int:
            if used_ctx:
                total = 0
                for _ in range(k):
                    ctx._reset()
                    func(ctx, *vargs, **vkwargs)
                    total += ctx._elapsed_ns()
                return total
            t0 = _timing._pc_ns()
            for _ in range(k):
                func(ctx, *vargs, **vkwargs)
            return _timing._pc_ns() - t0
    else:
        used_ctx = False

        def run(k: int) -> int:
            t0 = _timing._pc_ns()
            for _ in range(k):
                func(*vargs, **vkwargs)
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
    """Execute a case once per variant (used for warmup)."""
    variants = _make_variants(case)
    n = case.n
    rn = range
    for _vname, vargs, vkwargs in variants:
        if case.mode == "context":
            ctx = _timing.BenchContext()
            for _ in rn(n):
                ctx._reset()
                case.func(ctx, *vargs, **vkwargs)
        else:
            for _ in rn(n):
                case.func(*vargs, **vkwargs)


def run_single_repeat(
    case: Case,
    vname: str,
    vargs: tuple[Any, ...],
    vkwargs: dict[str, Any],
    used_ctx: bool = False,
    local_n: int | None = None,
) -> float:
    """Return mean nanoseconds for a single calibrated repeat."""
    n = local_n or case.n
    rn = range

    if case.mode == "context":
        ctx = _timing.BenchContext()
        if used_ctx:
            total = 0
            for _ in rn(n):
                ctx._reset()
                case.func(ctx, *vargs, **vkwargs)
                total += ctx._elapsed_ns()
            return float(total) / float(n)
        else:
            t0 = _timing._pc_ns()
            for _ in rn(n):
                case.func(ctx, *vargs, **vkwargs)
            return float(_timing._pc_ns() - t0) / float(n)
    else:
        t0 = _timing._pc_ns()
        for _ in rn(n):
            case.func(*vargs, **vkwargs)
        return float(_timing._pc_ns() - t0) / float(n)


def run_case(case: Case) -> list[float]:
    """Execute a case and return per-variant mean durations."""
    gc_was_enabled = gc.isenabled()
    try:
        gc.collect()
        if gc_was_enabled:
            gc.disable()

        for _ in range(max(0, case.warmup)):
            _run_case_once(case)

        per_variant_means: list[float] = []
        for vname, vargs, vkwargs in _make_variants(case):
            try:
                calib_n, used_ctx = calibrate_n(
                    case.func,
                    case.mode,
                    vargs,
                    vkwargs,
                )
            except Exception:
                calib_n = case.n
                used_ctx = (
                    detect_used_ctx(case.func, vargs, vkwargs)
                    if case.mode == "context"
                    else False
                )
            local_n = max(case.n, calib_n)
            per_variant_means.append(
                run_single_repeat(
                    case,
                    vname,
                    vargs,
                    vkwargs,
                    used_ctx,
                    local_n,
                )
            )
        return per_variant_means
    finally:
        if gc_was_enabled and not gc.isenabled():
            gc.enable()


def _create_stats(per_call_ns: list[float]) -> StatSummary:
    """Create StatSummary from samples."""
    from .utils import percentile as _percentile
    svals = sorted(per_call_ns)
    return StatSummary(
        mean=(
            _stats.fmean(per_call_ns)
            if hasattr(_stats, "fmean")
            else (
                sum(per_call_ns) / len(per_call_ns)
                if per_call_ns
                else float("nan")
            )
        ),
        median=_stats.median(per_call_ns) if per_call_ns else float("nan"),
        stdev=_stats.pstdev(per_call_ns) if per_call_ns else float("nan"),
        min=(svals[0] if svals else float("nan")),
        max=(svals[-1] if svals else float("nan")),
        p75=_percentile(svals, 75),
        p99=_percentile(svals, 99),
        p995=_percentile(svals, 99.5),
    )


def run_warmup(case: Case, kw: str | None = None) -> None:
    """Run warmup iterations for a case."""
    for _ in range(case.warmup):
        try:
            for _vname, vargs, vkwargs in _make_variants(case):
                if kw is not None and (kw not in _vname.lower()):
                    continue
                try:
                    if case.mode == "context":
                        ctx = _timing.BenchContext()
                        case.func(ctx, *vargs, **vkwargs)
                    else:
                        case.func(*vargs, **vkwargs)
                except Exception:
                    pass
        except Exception:
            pass


def execute_case_sequential(
    case: Case,
    *,
    budget_ns: int | None,
    max_n: int,
    smoke: bool,
    profile: str | None,
    kw: str | None = None,
) -> list[VariantResult]:
    """Execute a case sequentially (original behavior)."""
    from .utils import prepare_variants as _prepare_variants
    prepared = _prepare_variants(case, budget_ns=budget_ns, max_n=max_n, smoke=smoke)
    variants: list[VariantResult] = []

    for vname, vargs, vkwargs, used_ctx, local_n in prepared:
        # keyword filter
        if kw is not None and (kw not in vname.lower()):
            continue

        per_call_ns: list[float] = []
        for _ in range(case.repeat):
            per_call_ns.append(
                run_single_repeat(case, vname, vargs, vkwargs, used_ctx, local_n)
            )

        stats = _create_stats(per_call_ns)
        variants.append(
            VariantResult(
                name=vname,
                group=(case.group or "-") if case.group is not None else "-",
                n=case.n,
                repeat=case.repeat,
                baseline=case.baseline,
                stats=stats,
                samples_ns=(per_call_ns if (profile == "thorough") else None),
            )
        )

    return variants


def execute_case_parallel(
    case: Case,
    *,
    budget_ns: int | None,
    max_n: int,
    smoke: bool,
    profile: str | None,
    kw: str | None = None,
    max_workers: int = 4,
) -> list[VariantResult]:
    """Execute a case with parallel variant execution."""
    from .utils import prepare_variants as _prepare_variants
    prepared = _prepare_variants(case, budget_ns=budget_ns, max_n=max_n, smoke=smoke)

    def run_variant(variant_data):
        vname, vargs, vkwargs, used_ctx, local_n = variant_data
        if kw is not None and (kw not in vname.lower()):
            return None

        per_call_ns: list[float] = []
        for _ in range(case.repeat):
            per_call_ns.append(
                run_single_repeat(case, vname, vargs, vkwargs, used_ctx, local_n)
            )

        stats = _create_stats(per_call_ns)
        return VariantResult(
            name=vname,
            group=(case.group or "-") if case.group is not None else "-",
            n=case.n,
            repeat=case.repeat,
            baseline=case.baseline,
            stats=stats,
            samples_ns=(per_call_ns if (profile == "thorough") else None),
        )

    variants: list[VariantResult] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(run_variant, v) for v in prepared]
        for future in as_completed(futures):
            result = future.result()
            if result:
                variants.append(result)

    return variants


def execute_case(
    case: Case,
    *,
    budget_ns: int | None,
    max_n: int,
    smoke: bool,
    profile: str | None,
    parallel: bool = False,
    kw: str | None = None,
) -> list[VariantResult]:
    """Execute a case and return results.

    Args:
        case: The benchmark case to run
        budget_ns: Time budget for calibration
        max_n: Maximum iterations per repeat
        smoke: Whether smoke mode is enabled
        profile: Profile name (affects sample storage)
        parallel: Enable parallel execution for variants
        kw: Optional keyword filter

    Returns:
        List of VariantResult objects
    """
    from .utils import prepare_variants as _prepare_variants
    prepared = _prepare_variants(case, budget_ns=budget_ns, max_n=max_n, smoke=smoke)

    # Heuristic: parallel only helps with many variants (>5)
    # For quick profiles with few variants, sequential is faster
    use_parallel = parallel and len(prepared) > 5

    if use_parallel:
        return execute_case_parallel(
            case,
            budget_ns=budget_ns,
            max_n=max_n,
            smoke=smoke,
            profile=profile,
            kw=kw,
        )
    else:
        return execute_case_sequential(
            case,
            budget_ns=budget_ns,
            max_n=max_n,
            smoke=smoke,
            profile=profile,
            kw=kw,
        )


__all__ = [
    "infer_mode",
    "detect_used_ctx",
    "calibrate_n",
    "run_single_repeat",
    "run_case",
    "execute_case",
    "run_warmup",
]
