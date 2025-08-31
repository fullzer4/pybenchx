# Changelog

## v1.1.3 — new outputs, and modular refactor

### Summary
This release delivers new output capabilities (export and compare), and a refactor that reduces duplication (DRY) and improves maintainability.

### Highlights
- New run management: save runs, define baselines, compare, and export reports.
- Report parity: Markdown now mirrors the CLI table (baseline ★, “≈ same”, vs base).
- DRY: shared utilities for time formatting, percentiles, and speedups.
- Default profile is `smoke` (no calibration); “fast” was removed.

---

### Python 3.7+ compatibility (improvements and caveats)
- Fallback to `perf_counter() * 1e9` when `perf_counter_ns` is not available.
- Fallback for `statistics.fmean` (use sum/n) on versions lacking `fmean` (3.7).
- Fallback for `importlib.metadata.version` (falls back to `0.0.0` when unavailable).
- BenchContext reimplemented as a simple class with explicit `__slots__` — 3.7-friendly.

Known caveats on 3.7:
- Clock precision can vary by OS, slightly affecting percentiles/p-values.
- Without dataclass `slots=True`, memory overhead is marginally higher.
- In environments without Git, branch/sha metadata may be empty (handled gracefully).

---

### New output features and run management
- Report export via CLI:
  - `--export json|md|csv[:PATH]` (to stdout or a file).
  - Markdown includes: group, baseline ★, mean, p99, and “vs base” (shows “≈ same” when ≤1%).
- Saving and baselines:
  - `--save LABEL` stores the run under `.pybenchx/runs/`.
  - `--save-baseline NAME` stores it under `.pybenchx/baselines/`.
- Run comparison:
  - `--compare BASE|PATH` compares current run with a baseline; p-values via Mann–Whitney U (approx).
  - Failure policies via `--fail-on mean:%[,p99:%]`; `p99` uses the actual P99 delta.

Quick examples:
```bash
pybench examples/ --save latest
pybench examples/ --save-baseline main
pybench examples/ --export md:bench.md
pybench examples/ --compare main --fail-on mean:7%,p99:12%
```

---

### UX and execution
- `-k` filtering happens before warmup/measurement (avoids unnecessary work).
- CLI header shows `profile` and calibration budget.
- Stable suite signature (case hash) highlights changes between runs.

---

### Refactor and DRY (no breaking changes for end users)
- Core modularization: `bench_model`, `runner`, `timing`, `params`, `overrides`, `discovery`, `suite_sig`.
- New modules: `run_model`, `run_store`, `compare`, `meta`, `reporters/*`.
- Shared utilities in `pybench.utils`:
  - `fmt_time_ns`, `percentile`, `compute_speedups`.
- Reporters (table/markdown) now use the shared utilities.

---

### Behavior changes
- Removed `--profile fast`; `smoke` is the default; `thorough` remains ~1s with `repeat=30`.
- Unified “vs base” between table and markdown; shows “≈ same” at ≤1% difference.
- `p99` failure policy now uses the actual P99 delta (previously could proxy mean in some paths).

---

### Notes for contributors
- Cleaner, non-duplicated code: helpers centralized in `utils`.
- Reporters and comparators share the same baseline/speedups logic.
- Documentation updated (CLI, Getting Started, Examples, Internals) to match behavior.
