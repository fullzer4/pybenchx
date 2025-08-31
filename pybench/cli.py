from __future__ import annotations

import argparse
import time
import statistics as _stats
from pathlib import Path
from typing import List, Optional

from .timing import BenchContext
from .bench_model import all_cases
from .runner import run_single_repeat as _run_single_repeat
from .run_model import Run, RunMeta, VariantResult, StatSummary  # type: ignore
from .suite_sig import suite_signature_from_cases  # type: ignore
from . import run_store
from . import compare as compare_mod
from .reporters import json as rep_json
from .reporters import markdown as rep_md
from .reporters import csv as rep_csv
from .reporters.table import format_table as fmt_table_model
from .discovery import discover, load_module_from_path
from .meta import collect_git, tool_version, runtime_strings, env_strings
from .utils import parse_ns as _parse_ns
from .utils import prepare_variants as _prepare_variants
from .overrides import parse_overrides, apply_overrides
from .params import make_variants as _make_variants
from .profiles import apply_profile as _apply_profile
from .utils import percentile as _percentile


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

    # Collect VariantResult directly
    variants: List[VariantResult] = []

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

        for _ in range(max(0, case.warmup)):
            try:
                for _vname, vargs, vkwargs in _make_variants(case):
                    if kw is not None and (kw not in _vname.lower()):
                        continue
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
            # keyword filter
            if kw is not None and (kw not in vname.lower()):
                continue
            per_call_ns: List[float] = []
            for _ in range(case.repeat):
                per_call_ns.append(
                    _run_single_repeat(case, vname, vargs, vkwargs, used_ctx, local_n)
                )
            svals = sorted(per_call_ns)
            stats = StatSummary(
                mean=(_stats.fmean(per_call_ns) if hasattr(_stats, "fmean") else (sum(per_call_ns) / len(per_call_ns) if per_call_ns else float("nan"))),
                median=_stats.median(per_call_ns) if per_call_ns else float("nan"),
                stdev=_stats.pstdev(per_call_ns) if per_call_ns else float("nan"),
                min=(svals[0] if svals else float("nan")),
                max=(svals[-1] if svals else float("nan")),
                p75=_percentile(svals, 75),
                p99=_percentile(svals, 99),
                p995=_percentile(svals, 99.5),
            )
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

    elapsed = time.perf_counter() - start_ts

    # Build Run object (contract)
    branch, sha, dirty = collect_git()
    py_ver, os_str = env_strings()
    meta = RunMeta(
        tool_version=tool_version(),
        started_at=started_at_iso,
        duration_s=elapsed,
        profile=(profile or "smoke"),
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
    profile_label = (profile or "smoke")
    budget_label = f"{budget_ns / 1e9}s" if budget_ns else "-"
    print(
        "time: {:.3f}s | profile: {}, budget={}, max-n={}, sequential".format(
            elapsed, profile_label, budget_label, max_n
        )
    )
    print(
        fmt_table_model(
            LAST_RUN.results if LAST_RUN else [], use_color=use_color, sort=sort, desc=desc, brief=brief
        )
    )

    rc = 0

    # Save run
    if LAST_RUN and save is not None:
        path = run_store.save_run(LAST_RUN, label=save)
        print(f"saved run: {path}")

    # Save baseline
    if LAST_RUN and save_baseline:
        bpath = run_store.save_baseline(LAST_RUN, save_baseline)
        print(f"saved baseline: {bpath}")

    # Compare against baseline or path
    if LAST_RUN and compare:
        name, base = run_store.load_baseline(compare)
        print(f"comparing against: {name}")
        report = compare_mod.diff(LAST_RUN, base)
        policy = compare_mod.parse_fail_policy(fail_on or "")
        violated = compare_mod.violates_policy(report, policy)
        # Simple diff summary to stdout
        for d in report.compared:
            print(f"{d.group}/{d.name}: Δ={d.delta_pct:+.2f}% p={d.p_value if d.p_value is not None else 'n/a'} [{d.status}]")
        if report.suite_changed:
            print("⚠️  suite changed (partial diff)")
        if violated:
            print("❌ thresholds violated")
            rc = 2

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
        choices=["thorough", "smoke"],
        help="Presets: thorough (1s, repeat=30); smoke (no calibration, repeat=3, warmup=0). Default is smoke.",
    )
    parser.add_argument(
        "--brief",
        action="store_true",
        help="Brief output: only benchmark, time(avg), and vs base columns.",
    )

    # New flags (contract only)
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
        "--fail-on",
        metavar="POLICY",
        help='Failure policy, e.g. "mean:7%,p99:12%" (similar to pytest-benchmark).',
    )
    parser.add_argument(
        "--export",
        metavar="FMT[:PATH]",
        help="Export final report as json|md|csv, optionally with a path.",
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
        save=args.save,
        save_baseline=args.save_baseline,
        compare=args.compare,
        fail_on=args.fail_on,
        export=args.export,
    )


if __name__ == "__main__":
    raise SystemExit(main())
