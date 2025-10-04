from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import List, Optional

from .bench_model import all_cases
from .run_model import Run, RunMeta
from .suite_sig import suite_signature_from_cases
from . import run_store
from .reporters import json as rep_json
from .reporters import markdown as rep_md
from .reporters import csv as rep_csv
from .reporters.table import format_table as fmt_table_model
from .reporters.diff import format_comparison
from .discovery import discover, load_module_from_path
from .meta import collect_git, tool_version, runtime_strings, env_strings
from .utils import parse_ns as _parse_ns
from .overrides import parse_overrides, apply_overrides
from .params import make_variants as _make_variants
from .profiles import apply_profile as _apply_profile
from .runner import execute_case, run_warmup


# Expose last built run for downstream tooling/tests if needed
LAST_RUN: Optional[Run] = None


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
    minimal: bool = False,
    parallel: bool = False,  # Disabled by default - overhead not worth it for quick benchmarks
    save: Optional[str] = None,
    save_baseline: Optional[str] = None,
    compare: Optional[str] = None,
    fail_on: Optional[str] = None,
    export: Optional[str] = None,
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

    # Apply profile preset and detect smoke
    propairs, budget_ns, smoke = _apply_profile(profile, list(propairs), budget_ns)

    overrides = parse_overrides(propairs)
    cases = [apply_overrides(c, overrides) for c in all_cases()]

    start_ts = time.perf_counter()
    started_at_iso = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    
    # Quick mode: skip expensive system info for fast iterations
    # Only load when needed for save/compare operations
    need_full_meta = save or save_baseline or compare
    
    # Default is quick mode (profile=None becomes "quick")
    effective_profile = profile or "quick"
    
    if (effective_profile == "quick" and not need_full_meta) or minimal:
        if not minimal:
            print("⚡ quick mode | fast iteration")
        cpu = "n/a"
        ci = None
    else:
        cpu, runtime = runtime_strings()
        print("cpu: {}".format(cpu))
        ci = time.get_clock_info("perf_counter")
        print(
            "runtime: {} | perf_counter: res={:.1e}s, mono={}".format(
                runtime, ci.resolution, ci.monotonic
            )
        )

    import sys as _sys
    if use_color is None:
        use_color = _sys.stdout.isatty()

    # Collect VariantResult directly from execution module
    variants = []

    # Precompile keyword lower for filtering
    kw = (keyword or "").lower() or None

    for case in cases:
        # Skip cases with no variant matching -k
        if kw is not None:
            try:
                any_match = any((kw in vname.lower()) for (vname, _, _) in _make_variants(case))
            except Exception:
                any_match = True
            if not any_match:
                continue

        # Optimize warmup: skip for quick mode with small n (already fast)
        should_warmup = case.warmup > 0 and not (effective_profile == "quick" and case.n <= 10)
        
        if should_warmup:
            run_warmup(case, kw=kw)

        # Execute case using new execution module
        case_results = execute_case(
            case,
            budget_ns=budget_ns,
            max_n=max_n,
            smoke=smoke,
            profile=profile,
            parallel=parallel,
            kw=kw,
        )
        variants.extend(case_results)

    elapsed = time.perf_counter() - start_ts

    # Build Run object (contract) - lazy load meta info if needed
    if need_full_meta:
        branch, sha, dirty = collect_git()
        py_ver, os_str = env_strings()
        if cpu == "n/a":  # wasn't loaded earlier
            cpu, _ = runtime_strings()
            ci = time.get_clock_info("perf_counter")
    else:
        # Minimal metadata for quick runs
        branch, sha, dirty = None, None, False
        py_ver, os_str = env_strings()
        if cpu == "n/a":
            cpu = "quick-mode"
            ci = time.get_clock_info("perf_counter")
    
    meta = RunMeta(
        tool_version=tool_version(),
        started_at=started_at_iso,
        duration_s=elapsed,
        profile=(profile or "quick"),
        budget_ns=budget_ns,
        git={"branch": branch, "sha": sha, "dirty": dirty},
        python_version=py_ver,
        os=os_str,
        cpu=cpu,
        perf_counter_resolution=ci.resolution,
        gc_enabled=__import__("gc").isenabled(),
    )
    suite_sig = suite_signature_from_cases(cases)

    global LAST_RUN
    LAST_RUN = Run(meta=meta, suite_signature=suite_sig, results=variants)

    # Now that LAST_RUN is built, render the table
    profile_label = (profile or "quick")
    budget_label = f"{budget_ns / 1e9}s" if budget_ns else "-"
    mode_label = "parallel" if parallel else "sequential"
    
    if not minimal:
        print(
            "time: {:.3f}s | profile: {}, budget={}, max-n={}, {}".format(
                elapsed, profile_label, budget_label, max_n, mode_label
            )
        )
    
    print(
        fmt_table_model(
            LAST_RUN.results if LAST_RUN else [], use_color=use_color, sort=sort, desc=desc, brief=brief or minimal
        )
    )

    rc = 0

    # Auto-save every run for history tracking (enables easy comparisons)
    if LAST_RUN:
        try:
            run_store.auto_save_run(LAST_RUN)
        except Exception:
            pass  # Silent fail - don't break flow for save errors

    # Save labeled run
    if LAST_RUN and save is not None:
        path = run_store.save_run(LAST_RUN, label=save)
        if not minimal:
            print(f"saved run: {path}")

    # Save baseline
    if LAST_RUN and save_baseline:
        bpath = run_store.save_baseline(LAST_RUN, save_baseline)
        if not minimal:
            print(f"saved baseline: {bpath}")

    # Compare against baseline or path (now using new diff_output module)
    if LAST_RUN and compare:
        name, base = run_store.load_baseline(compare)
        output, exit_code = format_comparison(
            LAST_RUN,
            base,
            name,
            use_color=use_color,
            fail_on=fail_on,
        )
        print(output)
        if exit_code != 0:
            rc = exit_code

    # Export report
    if LAST_RUN and export:
        fmt, _, path = export.partition(":")
        fmt = fmt.strip().lower()
        path = path.strip()
        if fmt == "json":
            if path:
                rep_json.write(LAST_RUN, Path(path))
                print(f"exported JSON: {path}")
            else:
                print(rep_json.render(LAST_RUN))
        elif fmt == "md" or fmt == "markdown":
            md = rep_md.render(LAST_RUN)
            if path:
                p = Path(path)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(md, encoding="utf-8")
                print(f"exported Markdown: {path}")
            else:
                print(md)
        elif fmt == "csv":
            csv_txt = rep_csv.render(LAST_RUN)
            if path:
                p = Path(path)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(csv_txt, encoding="utf-8")
                print(f"exported CSV: {path}")
            else:
                print(csv_txt)
        else:
            print(f"unknown export format: {fmt}")

    return rc


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
        choices=["quick", "smoke", "thorough"],
        help="Presets: quick (n=10, repeat=1, DEFAULT); smoke (repeat=3, warmup=0); thorough (1s, repeat=30).",
    )
    parser.add_argument(
        "--brief",
        action="store_true",
        help="Brief output: only benchmark, time(avg), and vs base columns.",
    )
    parser.add_argument(
        "--minimal",
        action="store_true",
        help="Minimal output: brief table, no metadata, perfect for quick checks.",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Enable parallel execution for multiple variants (useful for parameterized benchmarks with >5 variants).",
    )

    # Storage & comparison flags
    parser.add_argument("--save", metavar="LABEL", help="Save this run under .pybenchx/runs with an optional label.")
    parser.add_argument(
        "--save-baseline",
        metavar="NAME",
        help="Save/copy this run as a named baseline under .pybenchx/baselines (e.g., main).",
    )
    parser.add_argument(
        "--compare",
        metavar="BASELINE|PATH",
        help="Compare this run against a baseline name or a JSON file; fail policy via --fail-on.",
    )
    parser.add_argument(
        "--vs",
        metavar="REF",
        help="Quick compare shortcut: --vs main, --vs test-branch, or --vs last (compare against last run).",
    )
    parser.add_argument(
        "--fail-on",
        metavar="POLICY",
        help='Failure policy, e.g. "mean:7%%,p99:12%%" (similar to pytest-benchmark).',
    )
    parser.add_argument(
        "--export",
        metavar="FMT[:PATH]",
        help="Export final report as json|md|csv, optionally with a path.",
    )

    args = parser.parse_args(argv)
    budget_ns = _parse_ns(args.budget) if args.budget else None
    
    # Handle --vs shortcut: simple store-based comparisons
    compare_target = args.compare
    if args.vs:
        # --vs last: compare against most recent run
        if args.vs == "last":
            latest = run_store.get_latest_run()
            if latest:
                # Save as temp baseline
                temp_name = f"_last_{int(time.time())}"
                run_store.save_baseline(latest, temp_name)
                compare_target = temp_name
                print("🔍 comparing against: last run")
            else:
                print("⚠️  no previous runs found in .pybenchx/runs/")
        else:
            # Assume it's a baseline name (e.g., main, test-branch, etc)
            compare_target = args.vs

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
        minimal=args.minimal,
        parallel=args.parallel,  # Now opt-in with --parallel flag
        save=args.save,
        save_baseline=args.save_baseline,
        compare=compare_target,
        fail_on=args.fail_on,
        export=args.export,
    )


if __name__ == "__main__":
    raise SystemExit(main())
