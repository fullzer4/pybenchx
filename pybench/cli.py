"""Entry points and helpers backing the ``pybench`` command-line tool.

The module exposes :func:`run` for programmatic execution plus the
sub-command handlers wired in :func:`main`. Handlers orchestrate
benchmark discovery, execution, reporting, and housekeeping tasks such as
listing stored runs or cleaning old artifacts.
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

from . import run_store
from .bench_model import all_cases
from .discovery import discover, load_module_from_path
from .meta import collect_git, env_strings, runtime_strings, tool_version
from .overrides import apply_overrides, parse_overrides
from .params import make_variants as _make_variants
from .profiles import apply_profile as _apply_profile
from .reporters import csv as rep_csv
from .reporters import json as rep_json
from .reporters import markdown as rep_md
from .reporters.charts import render_run_chart as _render_run_chart
from .reporters.diff import format_comparison
from .reporters.table import format_table as fmt_table_model
from .run_model import Run, RunMeta
from .runner import execute_case, run_warmup
from .suite_sig import suite_signature_from_cases
from .utils import parse_ns as _parse_ns

# Expose last built run for downstream tooling/tests if needed
LAST_RUN: Run | None = None

def run(
    paths: list[str],
    keyword: str | None,
    propairs: list[str],
    *,
    use_color: bool | None,
    sort: str | None,
    desc: bool,
    budget_ns: int | None,
    profile: str | None,
    max_n: int,
    brief: bool = False,
    minimal: bool = False,
    parallel: bool = False,
    save: str | None = None,
    save_baseline: str | None = None,
    compare: str | None = None,
    fail_on: str | None = None,
    export: list[str] | str | None = None,
) -> int:
    """Execute benchmarks discovered in ``paths`` and render results.

    Args:
        paths: Files or directories to search for ``*_bench.py`` modules.
        keyword: Optional substring filter applied to variant names.
        propairs: Key/value overrides applied to loaded cases.
        use_color: Force ANSI color usage; ``None`` auto-detects from TTY.
        sort: Sort strategy for the rendered table.
        desc: Whether to sort descending when ``sort`` is provided.
        budget_ns: Calibration time budget in nanoseconds.
        profile: Named profile preset (``quick``, ``smoke``, ``thorough``).
        max_n: Upper bound on calibrated iterations per repeat.
        brief: Hide extended columns in the table output.
        minimal: Skip metadata prints for a terse output mode.
        parallel: Enable parallel execution when a case has many variants.
        save: Persist the run under ``.pybenchx/runs`` with an optional label.
        save_baseline: Persist the run as a named baseline for comparisons.
        compare: Baseline label or path to compare against.
        fail_on: Threshold policy string (``metric:percent``) for comparisons.
        export: Optional export specifiers (``json``, ``markdown``, ``csv``, ``chart``).

    Returns:
        Process exit code semantics (``0`` success, ``1`` when no files, ``>0`` on
        comparison policy violations).
    """
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

    propairs, budget_ns, smoke = _apply_profile(profile, list(propairs), budget_ns)

    overrides = parse_overrides(propairs)
    cases = [apply_overrides(c, overrides) for c in all_cases()]

    start_ts = time.perf_counter()
    started_at_iso = datetime.now(timezone.utc).isoformat()

    # Quick mode: skip expensive system info for fast iterations
    # Only load when needed for save/compare operations
    need_full_meta = save or save_baseline or compare

    effective_profile = profile or "quick"

    if (effective_profile == "quick" and not need_full_meta) or minimal:
        if not minimal:
            print("⚡ quick mode | fast iteration")
        cpu = "n/a"
        ci = None
    else:
        cpu, runtime = runtime_strings()
        print(f"cpu: {cpu}")
        ci = time.get_clock_info("perf_counter")
        print(
            "runtime: "
            f"{runtime} | perf_counter: res={ci.resolution:.1e}s, mono={ci.monotonic}"
        )

    import sys as _sys
    if use_color is None:
        use_color = _sys.stdout.isatty()

    variants = []

    kw = (keyword or "").lower() or None

    for case in cases:
        if kw is not None:
            try:
                any_match = any(
                    kw in vname.lower() for (vname, _, _) in _make_variants(case)
                )
            except Exception:
                any_match = True
            if not any_match:
                continue

        should_warmup = case.warmup > 0 and not (
            effective_profile == "quick" and case.n <= 10
        )

        if should_warmup:
            run_warmup(case, kw=kw)

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
        gc_enabled=gc.isenabled(),
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
            "time: "
            f"{elapsed:.3f}s | profile: {profile_label}, budget={budget_label}, "
            f"max-n={max_n}, {mode_label}"
        )

    print(
        fmt_table_model(
            LAST_RUN.results if LAST_RUN else [],
            use_color=use_color,
            sort=sort,
            desc=desc,
            brief=brief or minimal,
        )
    )

    rc = 0

    auto_saved_path: Path | None = None
    if LAST_RUN:
        try:
            auto_saved_path = run_store.auto_save_run(LAST_RUN)
        except Exception:
            auto_saved_path = None  # Silent fail - don't break flow for save errors

    if LAST_RUN and save is not None:
        path = run_store.save_run(LAST_RUN, label=save)
        if not minimal:
            print(f"saved run: {path}")

    if LAST_RUN and save_baseline:
        bpath = run_store.save_baseline(LAST_RUN, save_baseline)
        if not minimal:
            print(f"saved baseline: {bpath}")

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

    export_specs: list[str] = []
    if isinstance(export, str):
        export_specs = [export]
    elif isinstance(export, list):
        export_specs = [e for e in export if e]

    if LAST_RUN and export_specs:
        base_name = (
            auto_saved_path.stem
            if auto_saved_path is not None
            else run_store.run_basename(LAST_RUN)
        )

        def _expand_spec(spec: str) -> list[str]:
            val = spec.strip()
            if not val:
                return []
            if val.lower() == "all":
                return ["json", "markdown", "csv", "chart"]
            return [val]

        expanded: list[str] = []
        for spec in export_specs:
            expanded.extend(_expand_spec(spec))

        seen: set[tuple[str, str]] = set()
        for spec in expanded:
            fmt_part, sep, path_part = spec.partition(":")
            fmt_key = fmt_part.strip().lower()
            dest_spec = path_part.strip() if sep else ""
            key = (fmt_key, dest_spec)
            if key in seen:
                continue
            seen.add(key)

            if fmt_key in {"md"}:
                fmt_key = "markdown"
            if fmt_key not in {"json", "markdown", "csv", "chart"}:
                print(f"unknown export format: {fmt_part}")
                continue

            write_to_stdout = dest_spec == "-"
            target_path: Path | None
            if write_to_stdout:
                target_path = None
            elif dest_spec:
                target_path = Path(dest_spec)
                if not target_path.is_absolute():
                    target_path = Path.cwd() / target_path
                target_path.parent.mkdir(parents=True, exist_ok=True)
            else:
                target_path = run_store.default_export_path(
                    LAST_RUN, fmt_key, base_name=base_name
                )
                target_path.parent.mkdir(parents=True, exist_ok=True)

            if fmt_key == "json":
                if target_path is None:
                    print(rep_json.render(LAST_RUN))
                else:
                    rep_json.write(LAST_RUN, target_path)
                    if not minimal:
                        print(f"exported JSON: {target_path}")
            elif fmt_key == "markdown":
                md_txt = rep_md.render(LAST_RUN)
                if target_path is None:
                    print(md_txt)
                else:
                    target_path.write_text(md_txt, encoding="utf-8")
                    if not minimal:
                        print(f"exported Markdown: {target_path}")
            elif fmt_key == "csv":
                csv_txt = rep_csv.render(LAST_RUN)
                if target_path is None:
                    print(csv_txt)
                else:
                    target_path.write_text(csv_txt, encoding="utf-8")
                    if not minimal:
                        print(f"exported CSV: {target_path}")
            elif fmt_key == "chart":
                html_doc = _render_run_chart(LAST_RUN)
                if target_path is None:
                    print(html_doc)
                else:
                    target_path.write_text(html_doc, encoding="utf-8")
                    if not minimal:
                        print(f"exported chart: {target_path}")

    return rc


def _run_command(args: argparse.Namespace) -> int:
    """Adapter that maps parsed arguments to :func:`run`."""
    budget_ns = _parse_ns(args.budget) if args.budget else None
    compare_target = args.compare

    if args.vs:
        if args.vs == "last":
            latest = run_store.get_latest_run()
            if latest:
                temp_name = f"_last_{int(time.time())}"
                run_store.save_baseline(latest, temp_name)
                compare_target = temp_name
                print("🔍 comparing against: last run")
            else:
                print("⚠️  no previous runs found in .pybenchx/runs/")
        else:
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
        parallel=args.parallel,
        save=args.save,
        save_baseline=args.save_baseline,
        compare=compare_target,
        fail_on=args.fail_on,
        export=args.export,
    )


def main(argv: list[str] | None = None) -> int:
    """Entry-point for the ``pybench`` command-line tool."""
    parser = argparse.ArgumentParser(
        prog="pybench",
        description="Run Python microbenchmarks.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run benchmarks")
    run_parser.add_argument(
        "paths",
        nargs="+",
        help="File or directory paths containing *bench.py files.",
    )
    run_parser.add_argument(
        "-k",
        dest="keyword",
        help="Filter by keyword in case or file name.",
    )
    run_parser.add_argument(
        "-P",
        dest="props",
        action="append",
        default=[],
        help="Override parameters (key=value). Repeatable.",
    )
    run_parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors in output.",
    )
    run_parser.add_argument(
        "--sort",
        choices=["group", "time"],
        help="Sort within groups by time, or sort groups alphabetically.",
    )
    run_parser.add_argument("--desc", action="store_true", help="Sort descending.")
    run_parser.add_argument(
        "--budget",
        default="300ms",
        help="Target time per variant, e.g. 300ms, 1s, or raw nanoseconds.",
    )
    run_parser.add_argument(
        "--max-n",
        type=int,
        default=1_000_000,
        help="Maximum calibrated iteration count per repeat.",
    )
    run_parser.add_argument(
        "--profile",
        choices=["quick", "smoke", "thorough"],
        help="Preset: quick (n=10, repeat=1); smoke (repeat=3); thorough (≈1s).",
    )
    run_parser.add_argument("--brief", action="store_true", help="Trim table columns.")
    run_parser.add_argument(
        "--minimal",
        action="store_true",
        help="Skip metadata for a terse output.",
    )
    run_parser.add_argument(
        "--parallel",
        action="store_true",
        help="Enable multi-variant parallel execution when beneficial.",
    )
    run_parser.add_argument(
        "--save",
        metavar="LABEL",
        help="Persist run under .pybenchx/runs with an optional label.",
    )
    run_parser.add_argument(
        "--save-baseline",
        metavar="NAME",
        help="Store run as a named baseline (e.g., main).",
    )
    run_parser.add_argument(
        "--compare",
        metavar="BASELINE|PATH",
        help="Compare against a baseline name or run JSON file.",
    )
    run_parser.add_argument(
        "--vs",
        metavar="REF",
        help="Shortcut: baseline name or 'last'.",
    )
    run_parser.add_argument(
        "--fail-on",
        metavar="POLICY",
        help='Policy like "mean:7%,p99:12%" for comparisons.',
    )
    run_parser.add_argument(
        "--export",
        metavar="FMT[:PATH]",
        action="append",
        nargs="?",
        const="all",
        default=[],
        help="Export as json|md|csv|chart. Repeatable.",
    )
    run_parser.set_defaults(handler=_run_command)

    list_parser = subparsers.add_parser("list", help="List saved runs and baselines")
    list_parser.add_argument(
        "--baselines",
        action="store_true",
        help="List only baselines",
    )
    list_parser.add_argument("--runs", action="store_true", help="List only runs")
    list_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum run entries to display (default: 10).",
    )
    list_parser.set_defaults(handler=handle_list_command)

    stats_parser = subparsers.add_parser("stats", help="Show storage statistics")
    stats_parser.set_defaults(handler=lambda _args: handle_stats_command())

    clean_parser = subparsers.add_parser("clean", help="Clean old auto-saved runs")
    clean_parser.add_argument(
        "--keep",
        type=int,
        default=100,
        help="Number of recent auto-saved runs to retain.",
    )
    clean_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview deletions without touching files.",
    )
    clean_parser.set_defaults(handler=handle_clean_command)

    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.error("No command handler registered")
    return handler(args)


def handle_list_command(args) -> int:
    """Handle 'pybench list' command."""
    if args.baselines or (not args.runs and not args.baselines):
        print("\n📊 Baselines:")
        baselines = run_store.list_baselines()
        if not baselines:
            print("  (no baselines saved)")
        else:
            for name in baselines:
                print(f"  • {name}")

    if args.runs or (not args.runs and not args.baselines):
        print("\n📝 Recent runs:")
        runs = run_store.list_recent_runs(limit=args.limit)
        if not runs:
            print("  (no runs saved)")
        else:
            for i, path in enumerate(runs, 1):
                size_kb = path.stat().st_size / 1024
                mtime = path.stat().st_mtime
                from datetime import datetime
                time_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                print(f"  {i:2d}. {path.name} ({size_kb:.1f}KB, {time_str})")

    return 0


def handle_stats_command() -> int:
    """Handle 'pybench stats' command."""
    stats = run_store.get_storage_stats()

    print("\n📈 Storage Statistics")
    print(f"  Total runs:     {stats['total_runs']}")
    print(f"  Labeled runs:   {stats['labeled_runs']}")
    print(f"  Baselines:      {stats['baselines']}")
    print(f"  Total size:     {stats['total_size_mb']:.2f} MB")

    if stats['oldest_run']:
        print(f"  Oldest run:     {stats['oldest_run']}")
    if stats['newest_run']:
        print(f"  Newest run:     {stats['newest_run']}")

    pybenchx_path = run_store.get_root()
    print(f"\n  Location:       {pybenchx_path}")

    return 0


def handle_clean_command(args) -> int:
    """Handle 'pybench clean' command."""
    if args.dry_run:
        root = run_store.get_root()
        runs_dir = root / "runs"
        if not runs_dir.exists():
            print("No runs directory found.")
            return 0

        run_files = sorted(
            [p for p in runs_dir.glob("*.json")],
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        labeled = [p for p in run_files if len(p.stem.split(".")) > 1]
        auto_saved = [p for p in run_files if p not in labeled]

        if len(auto_saved) <= args.keep:
            print(
                "✓ Only "
                f"{len(auto_saved)} auto-saved runs found "
                f"(keeping all, threshold is {args.keep})"
            )
            return 0

        to_delete = auto_saved[args.keep:]
        total_size = sum(p.stat().st_size for p in to_delete) / (1024 * 1024)

        print(f"Would delete {len(to_delete)} runs ({total_size:.2f} MB):")
        for path in to_delete[:10]:
            print(f"  • {path.name}")
        if len(to_delete) > 10:
            print(f"  ... and {len(to_delete) - 10} more")

        print("\nRun without --dry-run to actually delete these files.")
        return 0

    deleted = run_store.clean_old_runs(keep=args.keep)

    if deleted == 0:
        print(f"✓ No old runs to clean (keeping last {args.keep})")
    else:
        print(f"✓ Cleaned {deleted} old runs (kept last {args.keep})")

    return 0


