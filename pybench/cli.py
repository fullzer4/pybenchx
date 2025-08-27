from __future__ import annotations

import argparse
import importlib.util
import platform
import sys
import time
from pathlib import Path
from typing import List, Optional, Sequence

from .core import (
    BenchContext,
    Case,
    Result,
    _calibrate_n,
    _detect_used_ctx,
    _make_variants,
    _module_name_for_path,
    _run_single_repeat,
    all_cases,
    apply_overrides,
    filter_results,
    format_table,
    parse_overrides,
)


GLOB = "**/*bench.py"


def _parse_ns(s: str) -> int:
    """Parse human-friendly time strings into nanoseconds."""
    s = s.strip().lower()
    if s.endswith("ms"):
        return int(float(s[:-2]) * 1e6)
    if s.endswith("s"):
        return int(float(s[:-1]) * 1e9)
    return int(float(s))


def discover(paths: Sequence[str]) -> List[Path]:
    """Return a list of files to load (single files or *bench.py discovered in dirs)."""
    files: List[Path] = []
    for p in paths:
        path = Path(p)
        if path.is_file():
            files.append(path.resolve())
        elif path.is_dir():
            base = path.resolve()
            files.extend(sorted(base.glob(GLOB)))
    return files


def load_module_from_path(path: Path) -> None:
    """Import a file as a uniquely-named module so decorators can register cases."""
    path = path.resolve()
    modname = _module_name_for_path(str(path))
    spec = importlib.util.spec_from_file_location(modname, str(path))
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        sys.modules[modname] = module
        # type: ignore[arg-type]
        spec.loader.exec_module(module)  # noqa: E501


def _prepare_variants(case: Case, *, budget_ns: Optional[int], max_n: int, smoke: bool):
    """
    Prepare (vname, vargs, vkwargs, used_ctx, local_n) for each variant.

    - used_ctx is computed only for context mode
    - local_n is calibrated per-variant unless smoke=True
    """
    variants = _make_variants(case)
    prepared = []
    for vname, vargs, vkwargs in variants:
        if case.mode == "context":
            try:
                used_ctx = _detect_used_ctx(case.func, vargs, vkwargs)
            except Exception:
                used_ctx = False
        else:
            used_ctx = False

        if smoke:
            local_n = case.n
        else:
            target = max(1_000_000, (budget_ns or int(300e6)) // max(1, case.repeat))
            try:
                calib_n, _ = _calibrate_n(
                    case.func,
                    case.mode,
                    vargs,
                    vkwargs,
                    target_ns=target,
                    max_n=max_n,
                )
                local_n = max(case.n, calib_n)  # never reduce n
            except Exception:
                local_n = case.n
        prepared.append((vname, vargs, vkwargs, used_ctx, local_n))
    return prepared


def run(
    paths: List[str],
    keyword: Optional[str],
    propairs: List[str],
    *,
    use_color: Optional[bool],
    sort: Optional[str],
    desc: bool,
    budget_ns: Optional[int],
    profile: Optional[str],
    max_n: int,
    brief: bool = False,
) -> int:
    files = discover(paths)
    if not files:
        print("No benchmark files found.")
        return 1

    for f in files:
        load_module_from_path(f)

    import gc

    gc.collect()
    try:
        if hasattr(gc, "freeze"):
            gc.freeze()
    except Exception:
        pass

    smoke = False
    if profile == "fast":
        propairs = list(propairs) + ["repeat=10"]
        if budget_ns is None:
            budget_ns = int(150e6)
    elif profile == "thorough":
        propairs = list(propairs) + ["repeat=30"]
        if budget_ns is None:
            budget_ns = int(1e9)
    elif profile == "smoke":
        smoke = True
        propairs = list(propairs) + ["repeat=3", "warmup=0"]

    overrides = parse_overrides(propairs)
    cases = [apply_overrides(c, overrides) for c in all_cases()]

    start_ts = time.perf_counter()
    cpu = platform.processor() or platform.machine()
    runtime = "python {} ({}-{})".format(
        platform.python_version(), platform.machine(), platform.system().lower()
    )
    print("cpu: {}".format(cpu))
    ci = time.get_clock_info("perf_counter")
    print(
        "runtime: {} | perf_counter: res={:.1e}s, mono={}".format(
            runtime, ci.resolution, ci.monotonic
        )
    )

    if use_color is None:
        use_color = sys.stdout.isatty()

    results: List[Result] = []

    for case in cases:
        for _ in range(max(0, case.warmup)):
            try:
                for _vname, vargs, vkwargs in _make_variants(case):
                    if case.mode == "context":
                        ctx = BenchContext()
                        def fn():
                            return case.func(ctx, *vargs, **vkwargs)
                    else:
                        def fn():
                            return case.func(*vargs, **vkwargs)
                    try:
                        fn()
                    except Exception:
                        pass
            except Exception:
                pass

        prepared = _prepare_variants(case, budget_ns=budget_ns, max_n=max_n, smoke=smoke)
        for vname, vargs, vkwargs, used_ctx, local_n in prepared:
            per_call_ns: List[float] = []
            for _ in range(case.repeat):
                per_call_ns.append(
                    _run_single_repeat(case, vname, vargs, vkwargs, used_ctx, local_n)
                )
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

    elapsed = time.perf_counter() - start_ts
    all_results = filter_results(results, keyword)
    profile_label = profile or "default"
    budget_label = "{}s".format(budget_ns / 1e9) if budget_ns else "-"
    print(
        "time: {:.3f}s | mode: {}, budget={}, max-n={}, smoke={}, sequential".format(
            elapsed, profile_label, budget_label, max_n, smoke
        )
    )
    print(
        format_table(
            all_results, use_color=use_color, sort=sort, desc=desc, brief=brief
        )
    )
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="pybench", description="Run Python microbenchmarks.")
    parser.add_argument("paths", nargs="+", help="File(s) or dir(s) to search for *bench.py files.")
    parser.add_argument("-k", dest="keyword", help="Filter by keyword in case/file name.")
    parser.add_argument(
        "-P", dest="props", action="append", default=[], help="Override parameters (key=value). Repeatable."
    )
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors in output.")
    parser.add_argument("--sort", choices=["group", "time"], help="Sort within groups by time, or sort groups A→Z.")
    parser.add_argument("--desc", action="store_true", help="Sort descending.")
    parser.add_argument("--budget", default="300ms", help="Target time per variant, e.g. 300ms, 1s, or ns.")
    parser.add_argument("--max-n", type=int, default=1_000_000, help="Maximum calibrated n per repeat.")
    parser.add_argument(
        "--profile",
        choices=["fast", "thorough", "smoke"],
        help="Presets: fast (150ms, repeat=10), thorough (1s, repeat=30), smoke (no calibration, repeat=3)",
    )
    parser.add_argument(
        "--brief",
        action="store_true",
        help="Brief output: only benchmark, time(avg), and vs base columns.",
    )

    args = parser.parse_args(argv)
    budget_ns = _parse_ns(args.budget) if args.budget else None

    return run(
        args.paths,
        args.keyword,
        args.props,
        use_color=False if args.no_color else None,
        sort=args.sort,
        desc=args.desc,
        budget_ns=budget_ns,
        profile=args.profile,
        max_n=args.max_n,
        brief=args.brief,
    )


if __name__ == "__main__":
    raise SystemExit(main())
