from __future__ import annotations

import argparse
import importlib.util
import platform
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

from .core import (
    BenchContext,
    Case,
    Result,
    _calibrate_n,
    _detect_used_ctx,
    _make_variants,
    _run_single_repeat,
    all_cases,
    apply_overrides,
    filter_results,
    format_table,
    parse_overrides,
)


GLOB = "**/*bench.py"


def _parse_ns(s: str) -> int:
    s = s.strip().lower()
    if s.endswith("ms"):
        return int(float(s[:-2]) * 1e6)
    if s.endswith("s"):
        return int(float(s[:-1]) * 1e9)
    return int(float(s))


def discover(paths: List[str]) -> List[Path]:
    files: List[Path] = []
    for p in paths:
        path = Path(p)
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(path.glob(GLOB)))
    return files


def load_module_from_path(path: Path) -> None:
    # Load the file as a module so decorators execute and register cases
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        sys.modules[path.stem] = module
        spec.loader.exec_module(module)  # type: ignore[assignment]


def _prepare_variants(
    case: Case,
    *,
    budget_ns: Optional[int],
    max_n: int,
    smoke: bool,
) -> List[Tuple[str, Tuple[object, ...], dict, bool, int]]:
    """For a case, produce variant tuples with (name, args, kwargs, used_ctx, local_n).

    Performs light warmup and calibration based on budget when not in smoke mode.
    """
    variants_info: List[Tuple[str, Tuple[object, ...], dict, bool, int]] = []
    for vname, vargs, vkwargs in _make_variants(case):
        # Light warmup (single call) when requested
        if case.warmup > 0:
            try:
                if case.mode == "context":
                    ctx = BenchContext()
                    case.func(ctx, *vargs, **vkwargs)
                else:
                    case.func(*vargs, **vkwargs)
            except Exception:
                pass

        # Calibration and used_ctx detection
        if smoke:
            calib_n = case.n
            used_ctx = (
                _detect_used_ctx(case.func, vargs, vkwargs)
                if case.mode == "context"
                else False
            )
        else:
            try:
                target = max(
                    1_000_000, (budget_ns or 300_000_000) // max(1, case.repeat)
                )
                calib_n, used_ctx = _calibrate_n(
                    case.func, case.mode, vargs, vkwargs, target_ns=target, max_n=max_n
                )
            except Exception:
                calib_n = case.n
                used_ctx = (
                    _detect_used_ctx(case.func, vargs, vkwargs)
                    if case.mode == "context"
                    else False
                )
        local_n = max(case.n, calib_n)
        variants_info.append((vname, vargs, vkwargs, used_ctx, local_n))
    return variants_info


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
) -> int:
    files = discover(paths)
    if not files:
        print("No benchmark files found.")
        return 1

    for f in files:
        load_module_from_path(f)

    smoke = False
    if profile == "fast":
        # budget 150ms, repeat 10
        propairs = list(propairs) + ["repeat=10"]
        if budget_ns is None:
            budget_ns = int(150e6)
    elif profile == "thorough":
        # budget 1s, repeat 30
        propairs = list(propairs) + ["repeat=30"]
        if budget_ns is None:
            budget_ns = int(1e9)
    elif profile == "smoke":
        smoke = True
        propairs = list(propairs) + ["repeat=3", "warmup=0"]

    overrides = parse_overrides(propairs)
    cases = [apply_overrides(c, overrides) for c in all_cases()]

    start_ts = time.perf_counter()

    prepared = []
    for case in cases:
        prepared.append(
            (
                case,
                _prepare_variants(case, budget_ns=budget_ns, max_n=max_n, smoke=smoke),
            )
        )

    work = []
    max_repeats = 0
    for case, varlist in prepared:
        max_repeats = max(max_repeats, case.repeat)
        for vname, vargs, vkwargs, used_ctx, local_n in varlist:
            work.append(
                {
                    "case": case,
                    "name": vname,
                    "vargs": vargs,
                    "vkwargs": vkwargs,
                    "used_ctx": used_ctx,
                    "local_n": local_n,
                    "per_call_ns": [],
                }
            )

    cpu = platform.processor() or platform.machine()
    runtime = f"python {platform.python_version()} ({platform.machine()}-{platform.system().lower()})"
    print(f"cpu: {cpu}")
    ci = time.get_clock_info("perf_counter")
    print(
        f"runtime: {runtime} | perf_counter: res={ci.resolution:.1e}s, mono={ci.monotonic}"
    )

    if use_color is None:
        use_color = sys.stdout.isatty()

    import gc

    gc_was_enabled = gc.isenabled()
    gc.collect()
    if gc_was_enabled:
        gc.disable()
    try:
        for _round in range(max_repeats):
            for item in work:
                case: Case = item["case"]
                if len(item["per_call_ns"]) >= case.repeat:
                    continue
                res = _run_single_repeat(
                    case,
                    item["name"],
                    item["vargs"],
                    item["vkwargs"],
                    item["used_ctx"],
                    item["local_n"],
                )
                item["per_call_ns"].append(res)
    finally:
        if gc_was_enabled:
            gc.enable()

    elapsed = time.perf_counter() - start_ts

    all_results: List[Result] = []
    for item in work:
        case: Case = item["case"]
        all_results.append(
            Result(
                name=item["name"],
                group=case.group or "-",
                n=case.n,
                repeat=case.repeat,
                per_call_ns=item["per_call_ns"],
                baseline=case.baseline,
            )
        )

    all_results = filter_results(all_results, keyword)

    profile_label = profile or "default"
    budget_label = f"{budget_ns/1e9:.3f}s" if budget_ns else "-"
    print(f"time: {elapsed:.3f}s | mode: {profile_label}, budget={budget_label}, max-n={max_n}, smoke={smoke}")

    print(format_table(all_results, use_color=use_color, sort=sort, desc=desc))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pybench", description="Run Python microbenchmarks."
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="File(s) or directory(ies) to search for *bench.py files.",
    )
    parser.add_argument(
        "-k", dest="keyword", help="Filter by keyword in case/file name."
    )
    parser.add_argument(
        "-P",
        dest="props",
        action="append",
        default=[],
        help="Override parameters (key=value). Repeatable.",
    )
    parser.add_argument(
        "--no-color", action="store_true", help="Disable ANSI colors in output."
    )
    parser.add_argument(
        "--sort",
        choices=["group", "time"],
        help="Sort within groups by time, or sort groups alphabetically.",
    )
    parser.add_argument("--desc", action="store_true", help="Sort descending.")
    parser.add_argument(
        "--budget",
        default="300ms",
        help="Total target time per variant, e.g. 300ms, 1s, or ns.",
    )
    parser.add_argument(
        "--max-n", type=int, default=1_000_000, help="Maximum calibrated n per repeat."
    )
    parser.add_argument(
        "--profile",
        choices=["fast", "thorough", "smoke"],
        help="Preset: fast (150ms, repeat=10), thorough (1s, repeat=30), smoke (no calibration, repeat=3)",
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
    )


if __name__ == "__main__":
    raise SystemExit(main())
